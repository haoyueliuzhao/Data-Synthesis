# v0.8 Training Utility MVP Preflight Report

## Status

Run date: 2026-07-27 UTC.

The real Qwen model path is operational. A deterministic D2 reference cohort was materialized,
trained with BF16 LoRA, and compared with the untrained base model on a frozen hidden set. This is
an integration and resource preflight, not the completed D1-D5 utility experiment.

## Frozen Smoke Contract

| Item | Value |
| --- | --- |
| Base model | Qwen/Qwen2.5-7B-Instruct |
| Revision | `a09a35458c702b33eeacc393d103063234e8bc28` |
| Training cohort | D2 Reference Workflow |
| Training records | 6: Finance 2, Legal 2, Science 2 |
| Hidden records | 3: Finance 1, Legal 1, Science 1 |
| Train/evaluation task overlap | 0 |
| Method | BF16 LoRA SFT, rank 8 |
| Smoke budget | 1 step, batch 1, no accumulation |
| Maximum sequence | 8,192 tokens, truncation forbidden |

## Training Result

| Metric | Result |
| --- | ---: |
| Status | completed |
| Completed steps | 1 |
| Final training loss | 0.4340 |
| Runtime | 4.11 seconds |
| Trainable parameters | 20,185,088 |
| Total parameters | 7,635,801,600 |
| Peak allocated GPU memory | 21.73 GiB |

The GPU had a separate workload using about 45.7 GiB and over 90% compute utilization. The smoke
run still completed without an out-of-memory error, but inference latency is not representative of
an uncontended run.

## Hidden Evaluation

| Model | Valid JSON | Response contract | Operation exact | Answer exact | End-to-end |
| --- | ---: | ---: | ---: | ---: | ---: |
| D0 base | 66.7% | 0.0% | 0.0% | 0.0% | 0.0% |
| D2 after one step | 66.7% | 0.0% | 0.0% | 0.0% | 0.0% |

Two responses per model were valid top-level JSON but copied the public program skeleton instead
of producing the required executed operation objects. The Science response reached the 768-token
smoke limit before closing its JSON object. One step is intentionally insufficient for a utility
claim; the result verifies that the adapter, generation, strict parser, and scorer all run against
the same hidden records.

## Real-Agent Preflight Finding

The prior DeepSeek-V4-Pro smoke artifact attempted six candidates. Four API calls produced
normalized trajectories, but zero candidates passed the Quality Contract. The main root failures
were evidence selection and operation trace binding. Audit found a concrete contract ambiguity:
the prompt did not clearly explain that an operation evidence ref must include both the ref-kind
prefix and the full evidence ID. For example:

```text
evidence ID:  evidence:finance:item@v1
operation ref: evidence:evidence:finance:item@v1
```

The Agent prompt is now version 2, operation refs are checked against retrieved evidence before
trajectory normalization, and a failed ref receives contract-repair feedback. This fix requires a
new DeepSeek run; historical prompt-v1 artifacts are not reinterpreted as passing candidates.

## D1-D5 Readiness Gate

The experiment now audits each domain before materialization. It checks exact task coverage and
the per-domain supply of:

- unfiltered representable real candidates for D1;
- representable typed counterfactuals for D1;
- Quality Contract accepted candidates for D3;
- accepted/counterfactual repair pairs for D4;
- Critic-reviewed accepted candidates for D5.

Any missing quota blocks the run before GPU training. The complete D1-D5 experiment remains
pending because the current process does not have `DEEPSEEK_API_KEY` securely injected and the old
prompt-v1 artifact has no accepted candidates. No deterministic substitute is reported as a real
D3 or D5 cohort.

## Acceptance Boundary

The next complete run is valid only when:

1. a new prompt-v2 DeepSeek-V4-Pro Agent run covers the exact 30 candidate tasks;
2. the readiness audit reports `ready` for all three domains;
3. D1-D5 each contain 24 records with identical 8/8/8 domain balance;
4. all five adapters use the same Qwen revision and hyperparameters;
5. D0 and D1-D5 are evaluated on the same 18 disjoint hidden tasks;
6. the final report distinguishes feasibility from statistically powered utility.
