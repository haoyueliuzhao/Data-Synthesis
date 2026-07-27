# v0.8 Gap Closure and Prompt-v3 Calibration Report

> Superseded empirical status: `docs/v08_prompt_v3_real_calibration_report.md`.

## Decision

The v0.8 Training Utility experiment is now structurally ready for a real three-domain
Agent/Critic run. The repository has enough deterministic task capacity, pattern diversity,
counterfactual coverage, and evaluation power to construct D1-D5 without reusing evaluation
identities.

This report deliberately separates two states:

- `materialized`: records exist and have passed their required checks;
- `ready`: the compiler and source pools can produce the records, but a required external model
  run has not yet occurred.

D2 is materialized. D1, D3, D4, and D5 are ready but are not reported as materialized because the
current process does not have `DEEPSEEK_API_KEY` securely injected.

## Closed Gaps

### Candidate capacity and failure margin

The earlier 1,400-task pool was expanded to 2,000 unique tasks:

| Domain | Candidate tasks | Evaluation tasks | Pattern families |
| --- | ---: | ---: | ---: |
| Finance | 1,000 | 200 | 4 |
| Legal | 500 | 200 | 3 |
| Science | 500 | 200 | 3 |
| Total | 2,000 | 600 | 10 |

Legal and Science no longer equal the 200-record cohort quota. Each now has 500 candidates for a
200-record cohort, leaving 2.5x gross capacity before Agent, Contract, or Critic failures.

The full candidate pool contains 11 normalized Program signatures. Sampling first balances by
Pattern and then by structural group, so a high-volume Pattern cannot consume a cohort while hiding
its internal Program concentration.

### Legal reasoning diversity

Legal fixtures now cover:

1. condition application;
2. exception application;
3. authority resolution across competing rules.

These are compiled through two distinct operator-DAG families. The public task carries conditions,
exceptions, and authority priority so PLAN_HIDDEN execution does not depend on hidden Oracle fields.

### Science reasoning diversity

Science fixtures now cover:

1. protocol compatibility;
2. protocol-aligned effect comparison;
3. descriptive multi-study effect synthesis.

The synthesis operator reports a sample-size-weighted observed effect, total sample size, and an
uncertainty envelope. Its output is explicitly qualified as descriptive synthesis rather than a
formal meta-analysis or causal estimate.

### Finance reasoning diversity

The Finance pool now cycles through retrieval, cross-entity comparison, temporal growth, and
multi-period average tasks instead of producing only lookup variants.

### Evaluation power

The frozen D2 preflight contains:

- 600 training records, exactly 200 per domain;
- 600 evaluation records, exactly 200 per domain;
- zero training/evaluation task overlap;
- balanced Pattern and Program-signature distributions.

At 200 observations per domain, the worst-case normal-approximation 95% half-width is about 6.93
percentage points. The previous 50-observation design was about 13.86 points, so the new design can
detect materially smaller differences while remaining an MVP rather than a definitive utility
study.

## D1-D5 State

| Dataset | State | Remaining dependency |
| --- | --- | --- |
| D1 Random Synthetic | ready | real Prompt-v3 Agent candidates |
| D2 Reference Workflow | materialized | none for data preparation |
| D3 Contract Filter | ready | accepted real Agent candidates |
| D4 Contract + Counterfactual Calibration | ready | accepted candidates and repair pairs |
| D5 Quality Critic Selection | ready | accepted candidates with real Critic reviews |

Readiness is fail-closed per domain. D1-D5 preparation rejects missing task attempts, duplicate task
identities, insufficient representable candidates, insufficient accepted candidates, insufficient
repair pairs, insufficient Critic-reviewed candidates, and training/evaluation identity overlap.

## Prompt-v3 API Calibration

Before the 2,000-task run, use the checked-in calibration profile:

`config/deepseek_v4_pro_agent_v08_prompt_v3_calibration.json`

It freezes:

- 12 tasks per domain, 36 Agent calls total;
- all 10 Pattern families;
- 11 Program signatures;
- resolved retrieval and plan-given execution;
- up to 24 Quality Critic calls;
- typed counterfactual generation;
- exact DeepSeek-V4-Pro model identity.

The paired Training Utility calibration profile requires at least 75% real-candidate completion and
materializes 12 records per D1-D5 cohort with four records per domain. This is large enough to test
the full state transition without paying for the production candidate pool.

Run credentials from the environment only:

```bash
export DEEPSEEK_API_KEY=...

PYTHONPATH=src python -m trusted_synthesis.cli validate-agents \
  --agent-config config/deepseek_v4_pro_agent_v08_prompt_v3_calibration.json \
  --output-dir artifacts/agent_validation/v08_prompt_v3_calibration

PYTHONPATH=src python -m trusted_synthesis.cli audit-training-utility-readiness \
  --training-config config/training_utility_v08_prompt_v3_calibration.json \
  --agent-artifacts artifacts/agent_validation/v08_prompt_v3_calibration

PYTHONPATH=src python -m trusted_synthesis.cli prepare-training-utility \
  --training-config config/training_utility_v08_prompt_v3_calibration.json \
  --agent-artifacts artifacts/agent_validation/v08_prompt_v3_calibration \
  --output-dir artifacts/training_utility_mvp/v08_prompt_v3_calibration
```

The calibration is accepted only if all 36 tasks are attempted, per-domain completion is at least
75%, D1-D5 all fill their exact domain quotas, counterfactuals are rejected by the authoritative
Contract, and no training/evaluation identity overlaps.

The historical Prompt-v1/v2 run attempted six records, normalized four, and accepted zero. It is a
failure baseline only and cannot be reinterpreted under Prompt v3.

## Deterministic Validation

Run date: 2026-07-27 UTC.

| Check | Result |
| --- | ---: |
| Full test suite | 95 passed |
| Ruff | passed |
| Mypy | passed, 155 source files |
| Core domain imports | 0 |
| Core domain branches | 0 |
| Core domain field access | 0 |
| Cross-domain source tasks | 36 |
| Generated counterfactual cases | 731 |
| Counterfactual detection F1 | 1.000 |
| Mutation validity rate | 1.000 |
| Minimality pass rate | 1.000 |
| Root-cause F1 | 0.981 |
| Failure-closure F1 | 0.981 |

Trajectory mutations are always detected but sometimes activate an additional dependent root
clause, which explains the difference between perfect detection and 0.981 root-cause F1. This is
retained as a Critic-calibration slice rather than hidden by broadening the expected label.

## Audit Artifacts

- `data/audit/v08_agent_capacity_preflight_v2.json`
- `data/audit/v08_prompt_v3_calibration_capacity.json`
- `data/audit/v08_qwen3_reference_preflight_v2_summary.json`
- `data/audit/v08_counterfactual_validation_v2.json`
- `data/audit/v08_generalization_audit_v2.json`

## Remaining Boundary

The authorized 36-task Prompt-v3 calibration completed with 9 normalized trajectories and zero
Contract-accepted candidates.
D1, D3, D4, and D5 remain unmaterialized, and the 2,000-task run is blocked pending the corrective loop in the real calibration report.

