# QA Production Funnel Reporting

The final release pass rate and the end-to-end production yield are separate metrics.

## Required stages

| Stage | Denominator |
|---|---|
| candidate_attempted | Persisted rows in qa_candidates |
| candidate_eligible | Persisted candidate attempts |
| candidate_binding_succeeded | Eligible candidates |
| operation_replay_passed | Eligible candidates with an Operation Plan |
| canonical_qa_materialized | Eligible candidates |
| llm_rewrite_passed | Samples submitted to controlled LLM rewriting |
| parser_validation_passed | Materialized canonical QA samples |
| evidence_validation_passed | Materialized canonical QA samples |
| final_validation_passed | Materialized canonical QA samples |
| final_released | Materialized canonical QA samples |

Candidates without an Operation Plan are not_applicable, not failures. API requests including retries are reported separately from LLM sample attempts.

## Mandatory summary metrics

- final_sample_validation_rate = final_validation_passed / canonical_qa_materialized
- end_to_end_release_yield = final_released / candidate_attempted

A report may say “1,000/1,000 released samples passed validation” only when it also reports how many candidates were attempted upstream.

candidate_attempted begins at persisted candidates. Graph roots, motif observations, Proposal bindings, and compiler scans occur earlier and retain their own denominators in mining and pattern-compilation reports.

## Persistence

split_qa_samples() writes production_funnel to:

- qa_split_report.json;
- qa_builds.notes.build_gate;
- the returned split/build report.

The funnel also records candidate rejection reasons, Operation Plan applicability, controlled-LLM retries and fallbacks, parser/evidence check sets, and the graph Pattern Compiler subfunnel.
