# VTDO Experiment Migration Audit

## Decision

The active experiment surface has been reduced to one protocol:

```text
vtdo_experiment.v1
```

This migration removes ambiguity between legacy training-utility cohorts, v0.9 validation runs,
and the frozen VTDO paper method. Legacy runtime material has been permanently removed; tracked
source changes remain available only through Git history.

## Active Components

```text
src/trusted_synthesis/experiments/vtdo_experiment/
src/trusted_synthesis/experiments/finance_archive.py
src/trusted_synthesis/experiments/binding_support.py
config/vtdo_experiment_finance.json
config/vtdo_qwen2_5_7b_500k.json
tests/test_vtdo_experiment.py
tests/test_vtdo_multistate_quota.py
docs/vtdo_experiment_protocol.md
```

The current experiment owns controlled state validation, real Finance multi-state materialization,
empirical contribution validation, finite-step refinement dynamics, B1-B5 arm construction, and
fail-closed Qwen training.

## Removed Components

The following families were removed from active package, configuration, test, documentation, and
artifact discovery paths:

```text
training_utility_mvp
training_utility_v09
vtdo_validation
v0.8/v0.9 DeepSeek experiment profiles
v0.8/v0.9 training profiles and reports
legacy agent/training/VTDO generated artifacts
```

Tracked implementations were deleted from the active tree and remain recoverable only from Git
history. Ignored reports, checkpoints, and generated outputs were permanently deleted after
explicit authorization; they are not valid inputs to the current experiment.

## Semantic Migration

| Legacy concept | Active treatment |
|---|---|
| Synthesis cell as a trajectory state | rejected; no compatibility conversion |
| Singleton legacy Agent result | not evidence of a conditional state distribution |
| Surface variant | quotient/canonicalization probe only |
| Legacy D1-D5 utility cohort | replaced by B1-B5 state-distribution arms |
| Synthetic contribution oracle | removed |
| KL to contribution oracle | removed |
| Fixed moving-potential round count as convergence | replaced by finite-step stabilization score |
| Missing real feedback | blocked empirical contribution component |
| Missing real VTDO rounds | blocked B5/refinement component |
| Legacy CCGR cell distribution | rejected; B3 requires a current task distribution |

## Safety Properties

- The active package contains no legacy experiment modules.
- The current config parser rejects the legacy `real_state` section.
- Training refuses to load a model when preflight or identity checks fail.
- Missing benchmarks, contribution observations, CCGR distribution, or real round artifacts are
  explicit blockers.
- The active VTDO artifact namespace contains only the canonical `finance_v1` run.
- Git history preserves tracked-source traceability without runtime compatibility.

## Verification Contract

Before release, the migration is considered complete only when:

```text
active-tree stale-reference scan = clean
CLI exposes the canonical VTDO commands
focused VTDO tests pass
full pytest passes
Ruff passes
Mypy passes
git diff --check passes
small real Finance multi-state run completes
```

Any unavailable empirical input remains a documented blocker rather than a mocked success.

## Validation Result: 2026-07-31

The revised active tree passed:

```text
focused quota/VTDO tests:   11 passed
full active pytest suite:   169 passed
Ruff:                      passed
Mypy:                      191 source files passed
```

The canonical archive-backed preflight was written to:

```text
artifacts/vtdo_experiment/finance_v1/
```

Its full task and state funnel was:

```text
accepted-task quota:                    100
candidate tasks attempted:              105
accepted tasks:                         100
rejected tasks:                           5
strategy attempts:                      525
strategy verifier passes:               525
strategy verifier failures:               0
duplicate quotient states:               47
accepted canonical states:              468
states per accepted task:               3-5
wrong-answer mutations rejected:        100
```

All 100 accepted tasks persist complete `Omega_x`; all 468 canonical states have distinct
operation-graph and evidence-lineage identities. The five rejected tasks are retained in the
aggregate denominator under `FinanceTaskCapacityError:accepted_state_capacity=2<3`. Candidate
overprovisioning therefore fills the formal quota without hiding failed tasks.

The training preflight reports:

```text
B1_raw:          ready, 100 tasks, 468 accepted states plus 100 invalid attempts
B2_validity:     ready, 100 tasks, 468 accepted states
B3_ccgr:         blocked; current frozen CCGR distribution not configured
B4_random_state: ready, 100 tasks, one deterministic state per task
B5_vtdo:         blocked; real lineage-linked VTDO rounds not configured
benchmarks:      blocked; frozen FinQA/TAT-QA/FinanceBench snapshots not configured
```

The run status is consequently `partial`, as required by the fail-closed protocol. It validates
the controlled experiment, real multi-state construction, fixed-potential control, finite-step
diagnostics, and arm materialization; it does not claim empirical contribution validity, real
refinement convergence, or downstream training gain.

## Permanent Cleanup

After explicit authorization, the deprecated v0.8/v0.9 experiment tree, its approximately 10 GB
of ignored generated artifacts, the three-task smoke run, and the underfilled 95-task attempt were
permanently deleted. `artifacts/vtdo_experiment/finance_v1/` is the sole retained VTDO run. This
cleanup does not affect `raw_financial_data_lake`, which remains the active read-only source archive.
