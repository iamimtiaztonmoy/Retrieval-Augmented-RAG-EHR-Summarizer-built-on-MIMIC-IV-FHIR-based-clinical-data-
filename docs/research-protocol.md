# Research protocol: query-focused retrospective encounter summaries

**Stage:** implementation and synthetic validation; proposed empirical study, not completed research.

## Question and intended use

For hospitalized encounters in MIMIC-IV, does evidence retrieval followed by a local instruction model improve clinically relevant information coverage at a controlled unsupported-claim rate, compared with an extractive baseline and the same local model with a fixed evidence-selection baseline?

The output is a query-focused research synopsis, not a full discharge summary or treatment recommendation. It covers only the supported input tables. The unit is an admission, nested within a patient. Final billing diagnoses are retrospective and must never be described as information available at admission.

## Cohort and split

Prespecify the included release, eligible hospitalizations, source completeness rules and sample size before inspection of test results. The current importer requires valid admission/discharge times; it does not require ICU care or an adult-only cohort. Report all exclusions, missing timestamps, note/core join rates and source coverage. Do not silently invent a sample size or assert representativeness.

Use the implemented patient-hash split (80/10/10 buckets, seed 42); assign all admissions for a subject to the same partition. This is a patient-level split, not a cross-patient calendar-time split: MIMIC dates are shifted. Use training/development to author prompts and labels, validation for model/context/k selection, and test once after freezing configuration. With no fine-tuning, the training portion is still a development partition. Future model pretraining contamination cannot be ruled out merely by this split.

## Evidence and leakage controls

- Index diagnoses, optional labs/orders and radiology only. No discharge-note input is implemented.
- Match both subject/admission; exclude unlinked data. Validate source IDs against the selected corpus.
- Require lab/radiology event times within the encounter and storage times no later than discharge. Missing-time records are excluded, not backfilled from later notes.
- Prescription start times do not prove order availability; billing diagnoses do not have onset/availability times here. This constrains the study to retrospective use.
- If discharge summaries are later used as a reference, keep them in a separate restricted label store, never as retriever input. They cover content unavailable to this pipeline, so treat them as incomplete/imperfect references, not unquestioned ground truth.
- Query text must not be copied from target summaries in a way that gives away answer content. Clinicians should author questions from a task rubric independently of test model outputs.

## Comparators

Implemented: BM25 + extractive evidence baseline; BM25 + local LLM with citation validation. Legacy TF-IDF/identifier lookup is retained for history, not a clinical benchmark.

Planned ablations (not implemented): same model with deterministic recency/source-budget selection; BM25 vs dense/hybrid retrieval; citations validator enabled/disabled in an offline safety analysis. Keep model, context budget and source access fixed when attributing an improvement to retrieval. A full-context comparator is only meaningful when all input fits without truncation; report truncation explicitly.

## Measurements

Implemented software evaluation consumes JSONL relevance labels, measures source Recall@k, source MRR/hit rate and negative retrieval abstention, and saves label hashes and corpus settings. Chunk duplicates are removed for source-level scoring after the chunk limit. Supply explicit negative cases; no-overlap fixture queries are easier than realistic unanswerable clinical questions.

Proposed clinical evaluation:

1. Two independent qualified reviewers, blinded to system identity; adjudicate disagreements. Define a clinically relevant atomic-fact checklist from the source encounter.
2. Label each generated claim supported/unsupported/contradicted, citation entailment, correct patient/encounter, negation, uncertainty, numeric value/unit/time correctness and severity of potential harm.
3. Measure supported-claim precision, reference-fact coverage, omission frequency, clinically significant error rate and answerability/abstention. Report denominators and abstention separately; do not improve apparent precision by silently dropping failed generations.
4. Report agreement (e.g. Cohen's kappa with its limits) and patient-cluster bootstrap confidence intervals for model comparisons. Determine sample size based on a prespecified precision or effect-size objective; no power calculation has yet been done.
5. Measure end-to-end latency, token counts, GPU/RAM and index size on the actual cohort. Report subgroups only when source definitions and sample sizes support interpretation, including source availability; do not infer missing demographics from text.

ROUGE/BERTScore, if later implemented, are secondary similarity measures and cannot replace factuality/clinical review. No LLM-as-judge clinical scores are implemented or reported.

## Reproduction record

Freeze Git commit and clean-worktree status; Python lock and OS/SQLite versions; dataset/module release and consumed-file hashes; cohort and split rules; query/label version hashes; prompt version; retrieval parameters; model digest, license, quantization and server version; hardware, context/output limits and all exclusions/failures. Keep patient-level material restricted. Publish only approved aggregates and synthetic examples.

## Claims currently supported

Only the synthetic software checks and captured extractive baseline are verified. No claim of clinical benefit, Harvard affiliation, publication readiness, full-data performance or model superiority is made. Empirical findings require authorized data access, installed local weights and human review.
