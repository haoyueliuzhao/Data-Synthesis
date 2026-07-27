# v0.8 Training Utility MVP

## Purpose

This experiment asks one narrow causal question:

> With the model, task pool, domain mix, training budget, and evaluation set fixed, does the
> data-quality construction policy change the learned evidence-agent behavior?

It is an executable feasibility test, not a statistically powered utility claim. Finance remains
the reference domain, while Legal and Science each occupy one third of every cohort and the hidden
evaluation set.

## Frozen Contract

| Item | Value |
| --- | --- |
| Base model | Qwen/Qwen2.5-7B-Instruct |
| Model revision | a09a35458c702b33eeacc393d103063234e8bc28 |
| Training | BF16 LoRA SFT |
| Train records | 24 per cohort, 8 per domain |
| Hidden evaluation | 18 tasks, 6 per domain |
| Context | 8,192 tokens; truncation forbidden |
| Optimizer budget | 32 steps, batch 1, accumulation 4 |
| Seed | 20260726 |
| Retrieval/planning track | resolved / plan-given |

The tokenizer preflight covers 48 deterministic reference and evaluation tasks. Complete sequences
range from 3,891 to 6,540 tokens; the longest supervised response is 586 tokens. No record is
truncated.

## D1-D5 Construction

| Dataset | Construction | Intended contrast |
| --- | --- | --- |
| D1 Random Synthetic | Domain-balanced random mixture of unfiltered real-Agent responses and typed counterfactual wrong responses | No quality selection |
| D2 Reference Workflow | Deterministic Oracle-backed typed operation response | Upper-quality synthetic teacher |
| D3 Quality Contract Filter | Real-Agent candidates accepted by the authoritative Quality Contract | Deterministic quality filtering |
| D4 Contract + Counterfactual Calibration | Half accepted direct responses; half typed-counterfactual repair prompts targeting the accepted response | Explicit error-boundary calibration |
| D5 Quality Critic Selection | Contract-accepted candidates ranked within each domain by the advisory DeepSeek Quality Critic | Quality-aware selection after hard gates |

D1 intentionally treats sampled erroneous candidate responses as SFT targets. It is a noisy-data
baseline, not a recommended training recipe. D4 never trains the erroneous response as the target;
the model receives the attempted response and must return the independently accepted repair.

## Leakage and Identity Gates

Preparation fails closed unless:

- the real-Agent artifacts cover exactly the 30 candidate task IDs;
- there is exactly one real candidate per candidate task;
- at least 24 candidates pass the Quality Contract;
- at least 24 accepted candidates have a Quality Critic prediction;
- every D1-D5 cohort contains exactly eight Finance, eight Legal, and eight Science records;
- all 18 evaluation task IDs are disjoint from every training task ID;
- every data, model, Agent run, Critic dataset, and evaluation identity is content hashed.

## Evaluation

All six model conditions use the same hidden evaluation records:

~~~text
D0 untrained base
D1 adapter
D2 adapter
D3 adapter
D4 adapter
D5 adapter
~~~

Generation is deterministic. The evaluator requires a strict JSON object and independently checks:

- AgentResponseContract validity;
- evidence recall and precision;
- exact typed operation DAG, inputs, parameters, and node results;
- exact structured answer;
- exact source citations;
- exact verification result;
- multi-hop end-to-end correctness;
- distractor-resistant evidence selection;
- complete end-to-end correctness.

The current track is evidence-given and plan-given, so tool_success_rate is deliberately reported
as not applicable. Open retrieval utility is a later experiment and must not be inferred from this
MVP.

## Execution

Credentials are environment-only. The repository contains the environment variable name, never a
secret value.

~~~bash
export DEEPSEEK_API_KEY=...

trusted-synthesis validate-agents \
  --agent-config config/deepseek_v4_pro_training_utility_candidates.json \
  --output-dir artifacts/agent_validation/v08_training_utility_candidates

trusted-synthesis audit-training-utility-readiness \
  --training-config config/training_utility_mvp.json \
  --agent-artifacts artifacts/agent_validation/v08_training_utility_candidates

trusted-synthesis prepare-training-utility \
  --training-config config/training_utility_mvp.json \
  --agent-artifacts artifacts/agent_validation/v08_training_utility_candidates \
  --output-dir artifacts/training_utility_mvp/pilot/data
~~~

The readiness audit runs before cohort materialization and reports capacity separately for each
domain and each D1-D5 role. Missing real candidates, accepted candidates, representable typed
counterfactuals, repair pairs, or Critic-reviewed candidates block the experiment before training.

The model/runtime path can be tested without pretending that D1-D5 data exist:

~~~bash
trusted-synthesis prepare-training-utility-reference \
  --training-config config/training_utility_mvp_smoke.json \
  --output-dir artifacts/training_utility_mvp/preflight/data

trusted-synthesis train-training-utility \
  --training-config config/training_utility_mvp_smoke.json \
  --cohort D2_reference_workflow \
  --dataset artifacts/training_utility_mvp/preflight/data/D2_reference_workflow.jsonl \
  --output-dir artifacts/training_utility_mvp/preflight/model_D2
~~~

This preflight is explicitly a D2 resource and integration check. It is not a substitute for the
five-cohort utility experiment.

Train each cohort in an isolated process:

~~~bash
trusted-synthesis train-training-utility \
  --training-config config/training_utility_mvp.json \
  --cohort D2_reference_workflow \
  --dataset artifacts/training_utility_mvp/pilot/data/D2_reference_workflow.jsonl \
  --output-dir artifacts/training_utility_mvp/pilot/models/D2_reference_workflow
~~~

Then evaluate D0 and every adapter with evaluate-training-utility, and combine the five training
results and six evaluation results with summarize-training-utility. Commands are intentionally
resumable: a failed cohort does not erase completed adapters or predictions.

## Interpretation Boundary

The MVP has one seed, 24 examples per cohort, 18 evaluation tasks, and three task families. A higher
D5 score is evidence that the end-to-end experiment works and motivates a larger study; it is not
enough to claim general superiority. A production study needs multiple seeds, larger task-family
coverage, plan-hidden and retrieval tracks, confidence intervals, and a held-out external benchmark.
