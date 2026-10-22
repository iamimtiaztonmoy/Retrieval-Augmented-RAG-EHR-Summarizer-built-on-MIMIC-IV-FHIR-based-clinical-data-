# Data access and local inference

Verified source pages (October 21, 2026):

- Full structured release: https://physionet.org/content/mimiciv/3.1/
- Optional note release: https://physionet.org/content/mimic-iv-note/2.2/
- MIMIC schema: https://mimic.mit.edu/docs/iv/modules/hosp/
- LLM guidance: https://physionet.org/news/post/llm-responsible-use/
- Ollama offline/local configuration: https://docs.ollama.com/faq

## Authorized acquisition

1. Create/verify your PhysioNet account, complete credentialing and the required CITI Data or Specimens Only Research training.
2. Request access and sign the agreement on the MIMIC-IV page. Obtain separate access to the note project if using radiology text.
3. Download through the authenticated official Files interface into your approved environment. Do not put passwords, cookies or signed URLs in source code. This repository does not automate account access or accept credentials.
4. Extract the hospital tables and optional notes. Point the CLI to the actual directories, not their archive parents. Preserve download checksums, source URLs and acquisition date in a private experiment record; ingestion records SHA-256 hashes of consumed local files.
5. Begin with a prespecified patient cohort. Validate headers and join coverage. Core 3.1 and Note 2.2 do not imply identical cohorts. Excluded/unlinked rows are recorded, but a complete coverage analysis remains study work.

Full data were not downloaded in this development session. Do not interpret successful synthetic tests as a verified full-data execution. MIMIC is deidentified clinical data; the newly authored fictional fixtures are the only wholly synthetic input supplied by this update.

## Model environment

The code supports Ollama's local `/api/tags` and `/api/chat` interface, requiring an installed model digest. Choose model weights and licenses through your institutional process. The repository deliberately does not auto-pull a model or designate an untested checkpoint as clinically appropriate.

Start an Ollama version supporting `OLLAMA_NO_CLOUD=1` with that setting on the **server process**, not merely the client shell. Bind to loopback, disable external egress during restricted-data inference, and verify the model is actually served locally. Review server logging and retention. Record model name, weight digest, quantization, license, server version and hardware. The application rejects remote endpoints, proxies, redirects and cloud-named models, but cannot attest to a separately managed server's internals.

Local inference hardware was not available here. Adapter tests use a mock response; a real installation must first pass a synthetic generation/citation test. Temperature 0 and a fixed seed do not eliminate implementation or hardware nondeterminism.

## Publication and licensing

Publish code and authored synthetic fixtures. Keep real records, cohort membership, note derivatives, indexes, annotated examples and generations under the agreements. The PhysioNet source page describes treating derived datasets/models as sensitive and sharing through controlled access under the source agreement. Do not infer a right to publish derivatives from deidentification or from the public status of this GitHub repository.

No project code license has been selected in this change; that is a maintainer decision. Dataset and model licenses remain distinct. This project does not establish institutional approval, HIPAA compliance, or clinical validation.
