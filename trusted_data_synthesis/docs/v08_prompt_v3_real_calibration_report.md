# v0.8 Prompt-v3 Real DeepSeek Calibration

## Result

Run date: 2026-07-27 UTC.

The frozen 36-task Prompt-v3 calibration was executed against the exact requested model,
`deepseek-v4-pro`. The run completed with status `partial` and correctly failed the downstream
Training Utility readiness gate. No D1, D3, D4, or D5 cohort was materialized.

Run identity:

`agent_validation_run:9d0642169c81cf986ecd0ff64aeb85ae6eb20b7d7196b7fa14229cd790f59d80`

## Production Funnel

| Stage | Count | Rate |
| --- | ---: | ---: |
| Candidate tasks attempted | 36 | 100.00% |
| API responses normalized | 9 | 25.00% |
| Quality Contract evaluated | 9 | 25.00% of attempted |
| Quality Contract accepted | 0 | 0.00% of evaluated |
| Critic attempted | 9 | 100.00% of evaluated |
| Critic contract success | 6 | 66.67% of attempted |
| Final selected | 0 | 0.00% |

The 27 pre-normalization failures comprise 24 Agent response-contract failures and three exhausted
model-attempt failures. All nine normalized trajectories were rejected by the authoritative
Contract.

## Domain and Pattern Completion

| Domain | Normalized | Requested | Completion |
| --- | ---: | ---: | ---: |
| Finance | 4 | 12 | 33.33% |
| Legal | 0 | 12 | 0.00% |
| Science | 5 | 12 | 41.67% |

Pattern completion was concentrated in simple or structurally compact tasks:

- Finance fact retrieval: 3/3;
- Finance temporal average: 1/3;
- Science protocol compatibility: 3/4;
- Science protocol effect comparison: 2/4;
- all Finance comparison/growth, all Legal, and all Science synthesis: 0 normalized.

This shows that the expanded deterministic Pattern suite exists, but Prompt v3 does not yet make
the external model reliably instantiate its more complex response contracts.

## Contract Root Failures

Across the nine normalized trajectories, the root failure-family counts were:

| Family | Count |
| --- | ---: |
| Operation trace | 7 |
| Answer correctness | 2 |
| Answer schema validity | 2 |
| Citation binding | 2 |
| Tool necessity | 1 |
| Verification-step binding | 1 |

Seven samples failed exact Program-node output replay. A representative Science response returned
`protocol.seed_policy` as a mismatch path while the deterministic operator output requires the
coarser `protocol` field. The financial meaning was related, but the typed output was not equal.
This is a useful distinction: either the prompt must publish the exact enum contract more clearly,
or an independently specified semantic canonicalizer must normalize equivalent mismatch paths.
The verifier should not silently relax exact equality.

Two Finance samples returned answer payload fields at the top level instead of the required
`result` and `citations` envelope. Other direct failures included tool binding and verified-result
binding.

## Critic Finding

The Quality Critic produced six valid predictions:

- five predicted `accept`;
- one predicted `reject`;
- mean predicted accept probability: 0.8333;
- authoritative Contract acceptance: 0/6.

Model-advisory contract agreement was 0.1667, failure-family F1 was 0, and root-localization rate
was 0. This confirms the architecture boundary: the Critic cannot override deterministic Contract
failures and is not ready to select D5 data without calibration.

## Token and Runtime Audit

| Metric | Value |
| --- | ---: |
| Prompt tokens | 450,093 |
| Completion tokens | 162,013 |
| Total tokens | 612,106 |
| Contract repairs | 6 |
| Observed wall time | approximately 47 minutes |

Cost is intentionally reported as unknown because the model profile has no verified provider price
contract. A zero price in configuration would be misleading, so no currency estimate is inferred
from tokens alone.

The runtime exposed two production blockers:

1. calls are effectively serial for this workload;
2. artifacts are written only after the full run completes.

Before a 2,000-task run, the runner needs bounded concurrency, per-sample atomic checkpoints,
resume-by-stable-task-ID, and persisted failed-call telemetry. The current failed samples retain a
generic error and error class but not enough response-contract detail for every failed attempt.

## Readiness Decision

`data/audit/v08_prompt_v3_real_readiness.json` reports `blocked`:

- expected real candidates: 36;
- observed real candidates: 9;
- accepted candidates: 0;
- Critic-reviewed accepted candidates: 0;
- representable counterfactual and repair pairs: 0.

Per-domain minimum completion was 9/12. Finance produced 4, Legal 0, and Science 5. All D3-D5
minimums therefore failed closed. This behavior is correct and prevents a partial model run from
being mislabeled as a completed Training Utility experiment.

## Next Corrective Loop

Do not launch the 2,000-task pool yet. The next test should remain small and target one case per
Pattern after these changes:

1. publish exact answer and operator-output examples in the Agent contract;
2. add domain-specific contract-repair diagnostics, especially Legal;
3. canonicalize only explicitly approved semantic aliases;
4. persist failed attempt telemetry and redacted response diagnostics;
5. add bounded concurrency and incremental checkpoints;
6. recalibrate the Critic on Contract-labelled accepted and rejected examples.

The next calibration should require every Pattern to produce at least one normalized trajectory,
overall normalization of at least 75%, Contract acceptance of at least 75%, and zero Critic
authority violations before expanding candidate volume.

## Artifacts

- `artifacts/agent_validation/v08_prompt_v3_calibration/agent_validation_report.json`
- `artifacts/agent_validation/v08_prompt_v3_calibration/agent_validation_samples.jsonl`
- `artifacts/agent_validation/v08_prompt_v3_calibration/quality_critic_dataset.jsonl`
- `artifacts/agent_validation/v08_prompt_v3_calibration/manifest.json`
- `data/audit/v08_prompt_v3_real_readiness.json`

The credential was supplied only to the process environment for this run. It is not stored in the
repository, configuration, report, or generated artifacts.
