from copy import deepcopy
import gzip
import json
from pathlib import Path
import shutil
import sqlite3
from urllib.error import URLError

from fastapi.testclient import TestClient
import pytest

from api.main import app
from clinical_rag import store
from clinical_rag.evaluation import evaluate, subject_split
from clinical_rag.generation import Ollama, summarize, validate_output
from clinical_rag.ingest import build

FIXTURE = Path(__file__).parent / 'fixtures'


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'index.sqlite'
    build(FIXTURE / 'hosp', path, note_dir=FIXTURE / 'note',
          include_labs=True, include_prescriptions=True, synthetic=True)
    return path


def test_ingestion_provenance_and_exclusions(db):
    with store.connect(db) as conn:
        manifest = store.manifest(conn)
        assert manifest['dataset'] == 'synthetic-fixture'
        assert manifest['discharge_notes_indexed'] is False
        assert len(manifest['files']['radiology']['sha256']) == 64
        assert manifest['counts']['missing_or_invalid_time'] == 1
        assert manifest['counts']['outside_encounter_or_late'] == 2
        ids = {r[0] for r in conn.execute('SELECT source_id FROM chunks')}
        assert 'lab-valid' in ids
        assert not ids.intersection({'lab-late','lab-missing','lab-unlinked','rad-late'})
        assert conn.execute('SELECT count(*) FROM chunks').fetchone()[0] == 8


def test_patient_and_encounter_scope_before_limit(db):
    with store.connect(db) as conn:
        assert store.retrieve(conn,'syn-001','adm-001','embolism',1) == []
        own = store.retrieve(conn,'syn-001','adm-002','embolism',1)
        assert len(own) == 1 and own[0]['source_id'] == 'rad-2'
        assert store.retrieve(conn,'syn-002','adm-001','opacity') == []
        assert store.retrieve(conn,'syn-001','adm-001','unobtainium') == []
        assert store.retrieve(conn,'syn-001','adm-001','" OR * -- opacity')[0]['source_id'] == 'rad-1'
        assert store.retrieve(conn,'syn-001','adm-001','!!!') == []
        with pytest.raises(ValueError):
            store.retrieve(conn,'','adm-001','opacity')


def test_idempotence_and_no_overwrite(db, tmp_path):
    with pytest.raises(FileExistsError):
        build(FIXTURE/'hosp', db, synthetic=True)
    other = tmp_path/'other.sqlite'
    build(FIXTURE/'hosp', other, note_dir=FIXTURE/'note', include_labs=True,
          include_prescriptions=True, synthetic=True)
    with store.connect(db) as first, store.connect(other) as second:
        a = [tuple(r) for r in first.execute('SELECT * FROM chunks ORDER BY id')]
        b = [tuple(r) for r in second.execute('SELECT * FROM chunks ORDER BY id')]
        assert a == b


def test_gzip_and_subject_filter(tmp_path):
    hosp = tmp_path/'hosp';shutil.copytree(FIXTURE/'hosp',hosp)
    for f in hosp.glob('*.csv'):
        with gzip.open(f.with_suffix('.csv.gz'),'wb') as out: out.write(f.read_bytes())
        f.unlink()
    path=tmp_path/'gzip.sqlite'
    build(hosp,path,subjects={'syn-002'},synthetic=True)
    with store.connect(path) as conn:
        assert store.manifest(conn)['admissions']==1
        assert {r[0] for r in conn.execute('SELECT subject_id FROM chunks')}=={'syn-002'}


def test_invalid_schema_fails_and_removes_partial_db(tmp_path):
    hosp=tmp_path/'hosp';shutil.copytree(FIXTURE/'hosp',hosp)
    (hosp/'diagnoses_icd.csv').write_text('wrong\nvalue\n')
    path=tmp_path/'broken.sqlite'
    with pytest.raises(ValueError): build(hosp,path)
    assert not path.exists()


def test_citation_checks_and_abstention(db):
    with store.connect(db) as conn:
        evidence=store.retrieve(conn,'syn-001','adm-001','opacity')
    out=summarize(evidence,'opacity')
    assert not out['abstained']
    value={k:out[k] for k in ('abstained','claims')}
    validate_output(value,evidence)
    for mutation in ['unknown_id','invented_quote','missing_citation','extra_field']:
        bad=deepcopy(value)
        if mutation=='unknown_id': bad['claims'][0]['citations'][0]['chunk_id']='other'
        if mutation=='invented_quote': bad['claims'][0]['citations'][0]['quote']='invented evidence'
        if mutation=='missing_citation': bad['claims'][0]['citations']=[]
        if mutation=='extra_field': bad['recommendation']='treat'
        with pytest.raises(ValueError): validate_output(bad,evidence)
    assert summarize([],'unknown')['abstained']
    # Mechanical validation cannot prove entailment: this known limit is explicit.
    value['claims'][0]['text']='A claim that is NOT established by the quoted report.'
    validate_output(value,evidence)


@pytest.mark.parametrize('url', ['https://api.example.com','http://localhost:11434',
    'http://192.168.1.5:11434','http://127.0.0.1:11434/remote',
    'http://user:pass@127.0.0.1:11434','http://127.0.0.1:11434?remote=true'])
def test_remote_model_endpoints_rejected(url):
    with pytest.raises(ValueError): Ollama('local-model:tag',url)


def test_cloud_models_rejected():
    with pytest.raises(ValueError): Ollama('example:cloud')


def test_local_model_protocol_mocked(db,monkeypatch):
    with store.connect(db) as conn: evidence=store.retrieve(conn,'syn-001','adm-001','opacity')
    seen=[]
    def fake(self,path,payload=None):
        seen.append((path,payload))
        if path=='/api/tags': return {'models':[{'name':'local:test','digest':'fake-test-digest'}]}
        row=evidence[0]
        return {'done':True,'done_reason':'stop','message':{'content':json.dumps({
            'abstained':False,'claims':[{'text':'No pleural effusion is reported.',
            'citations':[{'chunk_id':row['id'],'quote':'No pleural effusion.'}]}]})}}
    monkeypatch.setattr(Ollama,'_request',fake)
    out=summarize(evidence,'opacity',backend='ollama',model='local:test')
    assert not out['abstained'] and out['model']['model_digest']=='fake-test-digest'
    assert seen[1][1]['stream'] is False
    assert seen[1][1]['options']['temperature']==0
    assert seen[1][1]['format']['type']=='object'
    def invalid(*args,**kwargs): raise ValueError('Malformed output')
    monkeypatch.setattr(Ollama,'generate',invalid)
    out=summarize(evidence,'opacity',backend='ollama',model='local:test')
    assert out['abstained'] and out['reason']=='invalid_model_response'


def test_evaluation_and_subject_split(db):
    cases=[json.loads(x) for x in (FIXTURE/'cases.jsonl').read_text().splitlines()]
    with store.connect(db) as conn:
        result=evaluate(conn,cases)
        assert result['positive_cases']==3 and result['negative_cases']==2
        assert result['source_recall_at_k']==result['source_mrr_at_k']==1
        assert result['negative_retrieval_abstention_rate']==1
        bad=deepcopy(cases);bad[0]['relevant_sources']=['radiology:rad-3']
        with pytest.raises(ValueError): evaluate(conn,bad)
    assert subject_split('syn-001')==subject_split('syn-001')
    assert {subject_split(str(i)) for i in range(100)}=={'train','validation','test'}


def test_api_auth_validation_scoping_and_failures(db,monkeypatch):
    token='t'*40
    monkeypatch.setenv('RAG_API_TOKEN',token)
    monkeypatch.setenv('RAG_DB',str(db))
    monkeypatch.setenv('RAG_BACKEND','extractive')
    headers={'Authorization':'Bearer '+token}
    request={'subject_id':'syn-001','hadm_id':'adm-001','query':'opacity'}
    with TestClient(app) as client:
        assert client.get('/health').status_code==200
        assert client.get('/ready').status_code==401
        assert client.get('/ready',headers=headers).status_code==200
        assert client.post('/v1/summarize',json=request).status_code==401
        result=client.post('/v1/summarize',json=request,headers=headers)
        assert result.status_code==200 and not result.json()['abstained']
        assert client.post('/v1/retrieve',json={**request,'query':'embolism'},headers=headers).json()['abstained']
        for bad in ({**request,'query':' '},{**request,'top_k':21},{**request,'extra':'x'}):
            assert client.post('/v1/retrieve',json=bad,headers=headers).status_code==422
        monkeypatch.setenv('RAG_DB','nonexistent.sqlite')
        assert client.get('/ready',headers=headers).status_code==503
        monkeypatch.setenv('RAG_API_TOKEN','short')
        assert client.get('/ready',headers=headers).status_code==503


def test_real_loopback_http_protocol(db):
    """Exercise urllib against a local stub, not real model weights."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    with store.connect(db) as conn:
        evidence=store.retrieve(conn,'syn-001','adm-001','opacity')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            assert self.path=='/api/tags'
            self.send_response(200);self.end_headers()
            self.wfile.write(json.dumps({'models':[{'name':'stub:test','digest':'stub-only'}]}).encode())
        def do_POST(self):
            assert self.path=='/api/chat'
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert body['model']=='stub:test' and body['stream'] is False
            row=evidence[0]
            value={'abstained':False,'claims':[{'text':row['text'],
                   'citations':[{'chunk_id':row['id'],'quote':row['text']}]}]}
            self.send_response(200);self.end_headers()
            self.wfile.write(json.dumps({'done':True,'message':{'content':json.dumps(value)}}).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        out=summarize(evidence,'opacity',backend='ollama',model='stub:test',
                      base_url=f'http://127.0.0.1:{server.server_port}')
        assert not out['abstained'] and out['model']['model_digest']=='stub-only'
    finally:
        server.shutdown();server.server_close();thread.join()


def test_invalid_model_citation_abstains(db,monkeypatch):
    with store.connect(db) as conn: evidence=store.retrieve(conn,'syn-001','adm-001','opacity')
    def bad(*args):
        return {'abstained':False,'claims':[{'text':'Invented assertion',
            'citations':[{'chunk_id':'not-in-context','quote':'made up evidence'}]}]}, {'model':'stub'}
    monkeypatch.setattr(Ollama,'generate',bad)
    out=summarize(evidence,'opacity',backend='ollama',model='stub:test')
    assert out['abstained'] and out['claims']==[]
    assert out['reason']=='citation_or_schema_validation_failed'


def test_database_failure_and_model_transport(db,monkeypatch):
    monkeypatch.setenv('RAG_API_TOKEN','t'*40)
    monkeypatch.setenv('RAG_DB',str(db))
    monkeypatch.setenv('RAG_BACKEND','ollama')
    monkeypatch.setenv('RAG_MODEL','stub:test')
    def fail(*args): raise URLError('Unavailable')
    monkeypatch.setattr(Ollama,'generate',fail)
    with TestClient(app) as client:
        response=client.post('/v1/summarize',headers={'Authorization':'Bearer '+'t'*40},
            json={'subject_id':'syn-001','hadm_id':'adm-001','query':'opacity'})
        assert response.status_code==502


def test_deterministic_chunk_boundaries_and_citation_scope(tmp_path):
    path=tmp_path/'chunks.sqlite';conn=store.create(path)
    text='alpha '+('x'*2600)+' omega'
    ids=store.add(conn,'s','h','radiology','r','',text)
    assert len(ids)==3
    store.finish(conn,{'dataset':'synthetic-fixture'})
    chunks=[dict(r) for r in conn.execute('SELECT * FROM chunks ORDER BY rowid')]
    assert chunks[0]['text'][-150:]==chunks[1]['text'][:150]
    assert chunks[0]['id']!=chunks[1]['id']
    conn.close()


def test_benchmark_keeps_failures_in_denominator(db, monkeypatch):
    from clinical_rag.benchmark import benchmark
    cases=[json.loads(x) for x in (FIXTURE/'cases.jsonl').read_text().splitlines()]
    with store.connect(db) as conn:
        base=benchmark(conn,cases)
        assert base['status_counts']=={'answered':3,'abstained':2,
            'validation_failure':0,'transport_failure':0}
        assert base['clinical_quality_evaluated'] is False
        def fail(*args): raise URLError('private detail must not be recorded')
        monkeypatch.setattr(Ollama,'generate',fail)
        out=benchmark(conn,cases,backend='ollama',model='stub:test')
        assert out['cases']==5 and out['status_counts']['transport_failure']==3
        assert out['status_counts']['abstained']==2
        assert 'private detail' not in json.dumps(out)
        assert out['answered_fraction']==0
        with pytest.raises(ValueError): benchmark(conn,cases,backend='ollama')


def test_benchmark_rejected_citations_retain_model_identity(db, monkeypatch):
    from clinical_rag.benchmark import benchmark
    case=json.loads((FIXTURE/'cases.jsonl').read_text().splitlines()[0])
    def bad(*args):
        return {'abstained':False,'claims':[{'text':'Bad', 'citations':[]}]}, {
            'model':'stub:test','model_digest':'test-only'}
    monkeypatch.setattr(Ollama,'generate',bad)
    with store.connect(db) as conn:
        out=benchmark(conn,[case],backend='ollama',model='stub:test')
    assert out['status_counts']['validation_failure']==1
    assert out['records'][0]['output']['model']['model_digest']=='test-only'
    assert out['records'][0]['output']['claims']==[]


def test_openapi_defines_success_response_contract():
    schema=app.openapi()
    response=schema['paths']['/v1/summarize']['post']['responses']['200']
    assert response['content']['application/json']['schema']['$ref'].endswith('/SummaryResponse')
    assert 'claims' in schema['components']['schemas']['SummaryResponse']['required']
    assert 'rank' in schema['components']['schemas']['Evidence']['required']
