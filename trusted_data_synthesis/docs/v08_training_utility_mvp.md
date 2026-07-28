# v0.8.1 Training Utility MVP

## Purpose

This experiment asks one controlled question:

> With model, task pool, domain mix, training format, token budget, and evaluation set fixed,
> does the data construction policy change learned evidence-agent behavior?

It is an executable feasibility experiment, not a training-utility result. Finance is the
reference domain; Legal and Science provide non-financial contract coverage.

## Agent Boundary

New real-candidate runs use `host_instrumented` interaction:

```text
public task + bounded evidence
  -> model action plan
  -> host executes registered operations
  -> model answer decision
  -> host binds citations and immutable trajectory metadata
  -> independent Quality Contract replay
```

The model owns search constraints, evidence selection, operators, semantic inputs, parameters,
and answer content. The host owns execution IDs, tool identity, observations, source locators,
latency, and lineage. This separates task competence from transcription of internal logs.

The legacy `full_response` protocol remains loadable only for historical artifact reproduction.
Capacity reports distinguish search, action, final-answer, and legacy full-response calls so the
host protocol is not costed as one request per candidate.

## Frozen Profile

The corrected profile is `config/training_utility_v08_1_qwen2_5_7b.json`.

| Item | Value |
| --- | --- |
| Base model | Qwen/Qwen2.5-7B-Instruct |
| Revision | `a09a35458c702b33eeacc393d103063234e8bc28` |
| Training | BF16 LoRA SFT |
| Cohort size | 600 records per D1-D5 cohort |
| Candidate task capacity | Finance 1,000; Legal 500; Science 500 |
| Internal evaluation | 600 tasks; 200 per domain |
| Context | 12,288 tokens; truncation forbidden |
| Optimizer budget | 600 steps, batch 1, accumulation 4 |
| Seed | 20260728 |
| Track | resolved / plan-given |

All five cohorts use the same `solve` target format in the corrected profile. Legacy noisy and
repair mixtures are available only through explicit compatibility modes.

## D1-D5 Contract

| Dataset | Corrected construction | Role |
| --- | --- | --- |
| D1 Random Synthetic | Domain-balanced unfiltered real-Agent outputs; no engineered counterfactual targets | No quality-filter baseline |
| D2 Reference Workflow | Deterministic Oracle-backed typed execution | Synthetic teacher upper bound |
| D3 Quality Contract Filter | Real-Agent outputs accepted by authoritative hard gates | Deterministic filtering |
| D4 Contract + Counterfactual Calibration | Clean accepted `solve` targets allocated toward tasks with typed failure-family coverage | Feedback-guided clean-data allocation |
| D5 Quality Critic Selection | Contract-accepted candidates selected through `QualityAwareSelector`; Critic is advisory | Exploratory ranking after hard gates |

D1 is no longer an intentionally corrupted baseline. It remains a same-task, same-interface
unfiltered Agent baseline, not a broad conventional-synthesis benchmark. D4 changes sample
allocation, not supervision format. D5 cannot rescue a rejected candidate. Quality Vector scores
are marked `diagnostic_uncalibrated`; zero default thresholds keep them from acting as a claimed
cross-domain quality scale.

## Readiness Gates

Preparation fails closed unless:

- expected candidate task identities are complete and unique;
- every D1-D5 domain quota can be filled;
- D1 has representable real outputs;
- D3 and D4 have accepted clean outputs;
- D4 tasks have typed counterfactual feedback coverage;
- D5 has Critic-reviewed accepted outputs and an exact selector quota;
- every cohort has exact Finance/Legal/Science balance;
- the internal evaluation set is isolated from training by task, subject, Evidence ID,
  Evidence version, source record, and semantic binding identity.

Program-signature overlap is reported separately. It is expected for an IID contract track and is
not silently described as OOD generalization.

## Evaluation Boundary

The internal evaluator remains strict and intentionally format-sensitive. It reports JSON and
response-contract validity separately from evidence, execution, operation, answer, citation,
verification, distractor robustness, and end-to-end correctness.

Every data manifest records:

```text
evaluation_track = internal_iid_contract
external_benchmark_status = not_executed
```

Therefore internal gains cannot be presented as general task competence. A later experiment must
add native-format external benchmarks and OOD pattern/binding splits without requiring the
project's internal response envelope.

## Execution

Credentials are environment-only. No key may appear in config, telemetry, prompts, or artifacts.

```bash
export DEEPSEEK_API_KEY=...

trusted-synthesis audit-agent-capacity \
  --agent-config config/deepseek_v4_pro_agent_v08_host_regression.json \
  --output data/audit/v08_1_host_capacity.json

trusted-synthesis validate-agents \
  --agent-config config/deepseek_v4_pro_agent_v08_host_regression.json \
  --output-dir artifacts/agent_validation/v08_1_host_regression

trusted-synthesis audit-training-utility-readiness \
  --training-config config/training_utility_v08_1_qwen2_5_7b.json \
  --agent-artifacts artifacts/agent_validation/v08_1_candidates

trusted-synthesis prepare-training-utility \
  --training-config config/training_utility_v08_1_qwen2_5_7b.json \
  --agent-artifacts artifacts/agent_validation/v08_1_candidates \
  --output-dir artifacts/training_utility_mvp/v08_1/data
```

The 10-task-per-domain host profile is a protocol regression, not the 600-record cohort source.
Scale only after it reaches the protocol completion and acceptance thresholds below.

## Scale-up Gate

Before a credentialed production candidate run:

```text
Action protocol completion  >= 90%
Contract evaluated rate     >= 90%
Contract acceptance rate    >= 60%
Accepted examples           present in every domain and major pattern
Checkpoint resume API calls = 0 for completed jobs
```

Training starts only after readiness passes and a release-validation summary freezes commit,
tests, tools, artifacts, and online status.

## Interpretation

Historical Prompt-v1/v3/v6 artifacts remain audit evidence for earlier protocols. They do not
validate the host-instrumented protocol or the corrected D1/D4/D5 definitions. The corrected data
must be rebuilt from a pinned host-protocol Agent run before training. Until D0-D5 training and
both internal and external evaluation are complete, the repository makes no training-utility
claim.
