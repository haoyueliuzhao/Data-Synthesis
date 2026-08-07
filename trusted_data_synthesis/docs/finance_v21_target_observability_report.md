# Finance v21 Direct Target Observability Study

Status date: 2026-08-07

Current status: `cancelled_after_partial_execution`. The frozen design remains auditable, but the
run was stopped by operator request on 2026-08-07 for a protocol redesign. Estimation and Validation
each contain 9 of 32 planned observations; no aggregate scientific result was produced.

## Scientific Question

v20 established that strict FP32 execution was reliable but could not distinguish a stable local
effect from Objective-support noise. v21 asks a narrower question:

> Can a fresh, larger Objective population resolve each preregistered Direct Coordinate as either
> a meaningful nonzero effect or a practically equivalent effect?

This is a target-observability study. It does not evaluate GP-C, does not read Objective gradients,
does not open Authorization, and cannot authorize a VTDO Contribution value.

## Frozen Population And Support

The study was created before v21 target outcomes were observed.

| Component | Frozen support |
| --- | ---: |
| Fresh candidate population | 420 accepted from 454 attempts |
| Candidate quotient states | 1,454 |
| Target tasks | 6, one per required Finance task family |
| Target states | 20 |
| Public Evidence versions | 58 |
| Initial Explorer trajectories | 24 valid observations |
| Initial distributions | 6 nonuniform, full-support distributions |
| State-conditioned realizations | 60, exactly 3 per state |
| Estimation Objective | 128 records |
| Validation Objective | 128 records |
| Sealed Authorization Objective | 128 record identities, content access forbidden |

The target tasks are fresh relative to the development population, mutually distinct, and have
disjoint public Evidence. Estimation, Validation, and Authorization record sets are pairwise
disjoint. Runtime role files contain only Estimation or Validation records; no Authorization role
file is materialized in the study directory.

## Preregistered Measurement

The design contains seven Direct Coordinates and one deterministic Null replay. One coordinate is
selected for each of the six required Finance task families, with a seventh coordinate from the
largest state support. Block/Hadamard reconstruction is excluded.

Each Objective role is partitioned into 32 immutable micro-splits of four records. The frozen
parameter-step ratios are `0.01` and `0.005`, normalized against the measured global one-step
parameter norm. The primary ratio is `0.005`.

The engineering minimum practical effect is `0.005` in raw Objective-slope units. It is not a
business effect, downstream accuracy threshold, or theoretical Contribution magnitude. A
coordinate is resolved only when the primary-radius interval supports either:

- a statistically nonzero mean whose absolute point estimate is at least the MPE; or
- a confidence interval fully contained inside `[-MPE, +MPE]`.

The secondary radius must yield the same resolution and a mean slope within one MPE. Both roles
must resolve all seven coordinates, and Estimation/Validation resolutions must agree exactly.

## Objective-Blind Local Updates

All 60 local training gradients were computed without opening any Objective partition. They were
aggregated into 20 state means, 20 state updates, 60 leave-one-realization-out updates, and one
global update. The local-update report passed its registered structural contract.

Realization diagnostics remain descriptive in this study. The observed worst tails were:

- minimum pairwise realization-gradient cosine: `0.634887`;
- minimum pairwise update cosine: `0.564861`;
- maximum within-state gradient variance ratio: `0.281741`;
- minimum effective sample size: `2.3406`.

These values were not used to tune v21 target-observability thresholds after outcome access.

## Fail-Closed Implementation

The v21 runner now enforces:

- exact plan, Objective-role file, direction, scale, and numeric-seed identities;
- exact registered direction and radius key coverage;
- content hashes for every direction artifact;
- immutable, hash-replayed baseline checkpoints for safe resume;
- strict absolute-tolerance replay of aggregate and micro-split losses;
- independent plan-to-observation checks for design role and coordinate identities;
- complete 32-observation matrices per Objective role;
- zero Authorization observations, no Objective-gradient access, and `gp_c_evaluated=false`.

The baseline checkpoint can be reconstructed from a previously verified observation created by an
older runner, allowing interrupted long-context execution to resume without changing scientific
identity.

## Code Validation Before Outcomes

The following checks completed while both real Objective baselines were still running and before
the first v21 observation was emitted:

| Check | Result |
| --- | --- |
| Focused v21 population/gradient/observability suite | 77 passed |
| Synthetic Direct-target and sealed-boundary tests | passed |
| Ruff | passed |
| Mypy | passed, 246 source files |
| Full Pytest | 425 passed in 116.34 seconds |

## Cancellation State

The Estimation and Validation workers were stopped after each role wrote 9 of 32 planned
observations. No v21 worker remains running. The partial rows are retained only as cancelled-run
provenance and cannot be aggregated, promoted into Development, reused as Validation, or used to
tune v22. Authorization was never opened and GP-C was never evaluated.

## Permitted Transitions

If and only if all target-observability gates pass, the next permitted action is to freeze a new,
independent GP-C comparison protocol. A pass still does not open Authorization or authorize
Contribution.

Because the run was cancelled before either role completed, it supports neither a pass nor a
scientific failure. The only valid transition is to retain `Contribution=0` and preregister a fresh
Development variance and power study. Threshold relaxation, post-outcome coordinate
replacement, Authorization access, and direct GP-C execution are forbidden.

## Immutable References

- `artifacts/vtdo_experiment/finance_v21_target_observability_preregistration_v1_20260807/preregistration.json`
- `artifacts/vtdo_experiment/finance_v21_target_observability_population420_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v21_target_observability_population6_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v21_target_observability_objective_support_128x128x128_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v21_target_observability_contract_v1_20260807/contract.json`
- `artifacts/vtdo_experiment/finance_v21_target_observability_local_updates_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v21_direct_target_observability_study_v1_20260807/`
