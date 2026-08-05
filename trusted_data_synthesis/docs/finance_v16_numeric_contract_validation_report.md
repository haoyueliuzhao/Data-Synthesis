# Finance v16 Numeric Contract Validation

Experiment date: 2026-08-04 to 2026-08-05

## Decision

Finance v16 completed a disjoint development and independent-validation experiment for the
Gradient Projection finite-precision contract. The result is negative and fail-closed:

- development calibration passed for both preregistered profiles;
- the selector froze `bf16_checkpoint_tf32_v10_control` before validation;
- independent validation passed margin-aware ordering and induced-distribution stability;
- independent validation failed three frozen raw numeric thresholds;
- no production numeric contract was emitted;
- the sealed candidate, GP-C, and distribution intervention were not opened.

This experiment does not show that GP-C or Gradient Projection is invalid. It shows that the v5
finite-precision implementation and frozen tolerance contract did not generalize across fresh
Finance tasks well enough to authorize the next causal stage.

## Recovery And Claim Boundary

This report uses only the current Git tree, immutable artifacts, credential-redacted recovery
records, and checks rerun on the migrated server. Missing chat messages are not treated as evidence.
The v14 population remains a production-validation holdout and was not used to fit v16 thresholds.

The v5 calibration can authorize only a numeric execution profile and an ordering contract. Even a
passed v5 report would not by itself authorize Contribution, GP-C, a VTDO energy update, Student
training, or a downstream benchmark claim.

## Fresh Population Contract

The recalibration population contains three mutually disjoint six-task partitions. Every partition
contains one task from each of the following families:

- `comparison`
- `derived_growth_comparison`
- `registered_ratio`
- `temporal_absolute_change`
- `temporal_average`
- `temporal_growth`

Each partition binds 63 Evidence versions. Cross-partition task, Evidence-version, and semantic
signature overlap are all zero.

| Partition | Role | Task-set identity |
| --- | --- | --- |
| Development | fresh calibration | `finance_gradient_calibration_task_set:3dacbd17bdf365f942efb76193beb649682e461054e5165aa6df97d5ffb2f531` |
| Validation | independent validation | `finance_gradient_calibration_task_set:e8a2e99c3aeec823c7552b17b402221d5fa9fed374472fa24f7b34b84f5dff7e` |
| Sealed candidate | unopened future candidate | `finance_gradient_calibration_task_set:884e85bc9a8f531c8fe36aab2920dc0ff1432428b1c0efca61122b92767cf034` |

Population report:
`finance_gradient_calibration_population:c8c369a2661cece931e5eee888772e3232793aafced045c3a30e447aef96eec4`.
The report records `sealed_candidate_outcomes_observed=false`.

## Real-Agent Realizations

Development and validation each used real DeepSeek-V4-Pro Agent generation rather than parameterized
fixtures:

| Split | Initial trajectories | States | Released realizations | Unique decision traces |
| --- | ---: | ---: | ---: | ---: |
| Development | 24/24 | 20 | 60/60 | 40 |
| Validation | 24/24 | 20 | 60/60 | 38 |

Validation required one retry after a single `LLMClientError`; the final 60 realizations all passed
the structured generation contract. No fallback model was used.

Across both splits the provider telemetry records 518 API calls and 3,770,538 tokens. The sum of
provider-reported cost estimates is `0.95538615` in the provider's telemetry unit. This is not a
billing invoice and no currency interpretation is asserted.

## Objective And Gradient Sources

A separate 4+4+4 Objective Support plan was materialized for estimation, validation, and future
authorization. All 18 support tasks are fresh relative to the calibration funnel, with zero task,
Evidence, and semantic overlap.

- Support plan:
  `finance_contribution_evaluation_support_plan:f1dc536ef1503ff89920a6541431341efc76a84b04a1bd88e1a59bb97f7369bd`
- Support report:
  `finance_contribution_evaluation_support_report:c8f928ebae863214bd237e74872965681afa8898f9544813fc4e4d3e7c97e033`
- Target set:
  `finance_gradient_target_task_set:bb27510554b84a4288e5da1fd3f49e34861de051f81b7598362b84aa45e723d7`

Development and validation gradient sources were independently materialized. Each run used one A100
and peaked at approximately 32.22 GB allocated GPU memory.

## Numeric Algorithm

The v5 implementation uses `shared_token_loss_gradient_decomposition.v1`:

1. one model forward graph;
2. one causal cross-entropy loss vector;
3. deterministic common and differential token-region slicing;
4. three VJPs for full, common, and differential losses;
5. replay of loss identity, gradient recomposition, GP scores, and induced updates.

The immutable numeric algorithm contract is:
`finance_gradient_numeric_algorithm_contract:f5153962f4e177903a72f8c5aba09f69c71712de0cc7e427ba152ebbdd861f32`.

The runner now writes one atomic, content-bound checkpoint per realization. Checkpoints bind the
plan, source identity, split, profile, algorithm contract, job, and output row. This was added after
an unrelated eight-GPU job preempted the first profile attempts. The resumed production runs proved
that exact completed jobs can be replayed while altered or foreign checkpoints fail closed.

## Development Calibration

Both preregistered BF16 profiles passed their development gates:

| Metric | TF32 control | Strict accumulation |
| --- | ---: | ---: |
| Maximum GP-score delta | 0.00152472 | 0.00178094 |
| Maximum relative error | 0.02121472 | 0.02296097 |
| Minimum cosine | 0.99977505 | 0.99973922 |
| Maximum loss-identity error | 4.47e-8 | 1.11e-16 |
| Maximum update JS | 2.82e-8 | 3.28e-8 |
| Maximum update TV | 0.00015072 | 0.00019001 |
| Resolvable pair direction | 22/22 | 24/24 |
| Strict task permutation | 5/6 | 6/6 |

The preregistered selector chose the TF32 control by the fixed policy that minimizes update TV, then
JS and GP delta among profiles that pass all development gates. Selection was frozen before any
validation outcome was observed.

Selection identity:
`finance_gradient_precision_v5_selection:aaeeeb5fb8799e31460e78ca56ea1147bfd8055a029158410fa4bbc781397e96`.

Frozen validation thresholds:

| Metric | Threshold |
| --- | ---: |
| Maximum GP-score delta | 0.0023 |
| Maximum relative error | 0.027 |
| Minimum cosine | 0.99967 |
| Maximum loss-identity error | 1e-6 |
| Maximum update JS | 1e-6 |
| Maximum update TV | 0.00023 |

The margin-aware pairwise uncertainty envelope was frozen at `0.0026`.

## Independent Validation

The selected TF32 profile produced 60/60 completed checkpoints on the independent validation split.

| Metric | Observed | Threshold | Result |
| --- | ---: | ---: | --- |
| Maximum GP-score delta | 0.00282111 | <= 0.0023 | failed |
| Maximum relative error | 0.03005580 | <= 0.027 | failed |
| Minimum cosine | 0.99954834 | >= 0.99967 | failed |
| Maximum loss-identity error | 4.16e-8 | <= 1e-6 | passed |
| Maximum update JS | 3.11e-8 | <= 1e-6 | passed |
| Maximum update TV | 0.00015587 | <= 0.00023 | passed |

The raw failures are localized but not reducible to one metric:

- one `temporal_growth` record exceeded the relative-error threshold;
- two records from the same `temporal_growth` state fell below the cosine threshold;
- one `comparison` record exceeded the GP-score-delta threshold.

Margin-aware behavior remained stable:

- 23/25 state pairs were resolvable;
- resolvable-pair direction agreement was 100%;
- all six task winners agreed;
- all six strict task permutations agreed;
- no margin-aware ordering violation occurred.

The positive ordering diagnostics do not override the raw numeric gate. The aggregate report is
`failed` with `raw_numeric_precision_failed`.

Aggregate report identity:
`finance_gradient_precision_v5_report:23a368bfb49741f7b3063fd4e467175232766b39544f601885267964a1f8e97a`.

An independent integrity replay verified 185 canonical identities, including all 180 realization
checkpoints, and recomputed zero pairwise overlap across task, Evidence, and semantic partition
sets. Its identity is
`finance_v16_numeric_integrity_audit:f13b93b180eb23a40805729bd575bca021c460f22442a255812998e7b293ecfc`.

Validation result identity:
`finance_gradient_precision_v5_result:b9ccf9d9a57ca67187818d0e07350e5a125a7fc38ddea3ca60e00ceaa27d43f4`.

## Authorization Decision

The output directory contains `plan.json`, `selection.json`, the development results, and the
selected validation result. It does not contain `frozen_numeric_contract.json`.

Accordingly:

- `production_authorized=false`;
- no Contribution credential exists;
- no GP-C result may be interpreted under v16;
- no post-global or local distribution intervention may run;
- the sealed-candidate partition remains unopened;
- the unused strict profile may not be substituted after seeing validation.

## Next Experiment

The next step is a new preregistered numerical-algorithm diagnosis on another development-only
population. It should isolate accumulation dtype, sparse projection dtype, token-region reduction,
and VJP recomposition while keeping source gradients and model execution identities fixed. A new
validation population and new contract version are required after any algorithm change.

The following are explicitly prohibited for the current run:

- relaxing the frozen v5 thresholds;
- running the strict profile on the already-opened validation set as an alternate winner;
- opening the sealed candidate or reusing v14 for calibration;
- interpreting margin-aware agreement as production numeric authorization;
- proceeding to Hessian or Richardson Contribution corrections before first-order numeric fidelity
  passes independently.

## Immutable Artifacts

- `artifacts/vtdo_experiment/finance_v16_numeric_recalibration_partitions_6x6x6_v3_20260804/`
- `artifacts/vtdo_experiment/finance_v16_numeric_development_initial_distribution_v1_20260804/`
- `artifacts/vtdo_experiment/finance_v16_numeric_validation_initial_distribution_v1_20260804/`
- `artifacts/vtdo_experiment/finance_v16_numeric_development_state_realizations_v1_20260804/`
- `artifacts/vtdo_experiment/finance_v16_numeric_validation_state_realizations_v1_20260804/`
- `artifacts/vtdo_experiment/finance_v16_numeric_objective_support_4x4x4_v1_20260804/`
- `artifacts/vtdo_experiment/finance_v16_numeric_development_gradient_source_v1_20260804/`
- `artifacts/vtdo_experiment/finance_v16_numeric_validation_gradient_source_v1_20260804/`
- `artifacts/vtdo_experiment/finance_v16_gradient_precision_calibration_v5_dev6_val6_v1_20260804/`
