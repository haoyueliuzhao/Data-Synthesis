# Current Project Status

Audit date: 2026-08-05

This status is reconstructed only from the current Git tree, immutable experiment artifacts,
credential-redacted recovery records, and checks rerun on the migrated server. Missing chat messages
are not treated as experimental evidence.

## Repository Identity

- Active repository: `/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis`
- Branch: `main`
- Base HEAD: `5573dbc4f1f75fa25cd36ece3f51864ee884537c`
- Worktree: contains the intentional v16 implementation, tests, and documentation described here
- Credentials remain process-environment inputs and are not tracked or serialized

The base commit contains the v14 real-Agent Gradient Projection candidate. The current worktree adds
a disjoint numeric recalibration population, shared-forward gradient decomposition, independent
validation, strict checkpoint replay, and fail-closed aggregate authorization.

## Runtime And Data

The migrated environment remains operational with Python 3.12, PyTorch 2.7.1+cu128, CUDA 12.8, and
eight NVIDIA A100-SXM4-80GB GPUs. At the end of this audit no Finance v16 experiment process was
running. Unrelated processes retained approximately 22 GB per GPU; this observation is not a future
resource reservation.

The read-only Finance Archive remains the active data dependency:

| Item | Verified value |
| --- | ---: |
| KG build | `kg_20260711_062123_bc4b4394` |
| Graph schema | `3.0` |
| Nodes | 913,475 |
| Edges | 5,734,348 |
| Fact nodes | 658,535 |
| DerivedFact nodes | 135,990 |

The newest DB-only build from the previous server is still unavailable, but the immutable archive
required by the active experiment is present and readable.

## Revalidated Code State

| Check | Result |
| --- | --- |
| Ruff | passed |
| Mypy | passed, 235 source files |
| Pytest | passed, 355 tests in 114.58 seconds |
| Git whitespace audit | passed |
| Core generalization boundary | retained by the full test suite |
| Legal and Science contracts | retained by the full test suite |

The v16 checkpoint tests prove exact resume and reject altered plans, profiles, splits, jobs, and
row identities. Failed aggregation also rejects a stale frozen numeric contract; no compatibility
path converts a failed v5 validation into the older v3 contract.

## v14 Historical Boundary

The v14 production candidate remains immutable historical evidence:

- 30 real Finance tasks;
- 100 quotient trajectory states;
- 300 fresh state-conditioned realizations;
- 1,065/1,065 gradient artifact content hashes verified;
- stable realization sampling and positive internal proxy association;
- seven raw numeric-tail violations and three strict task-order reversals.

It remains a holdout and was not reused to tune v16. Its status remains `partial` with
`production_authorized=false`.

## v16 Numeric Recalibration

### Population and generation

v16 constructed development, validation, and sealed-candidate partitions with six balanced task
families each. Every partition contains 63 Evidence versions. Cross-partition task, Evidence, and
semantic overlap are zero. The sealed-candidate outcome flag remains false.

Development and validation each produced 24/24 valid initial Agent trajectories, 20 states, and
60/60 released realizations. Across the four DeepSeek-V4-Pro generation stages:

- API calls: 518;
- total tokens: 3,770,538;
- fallback calls: 0;
- provider-reported cost-estimate sum: `0.95538615` in the provider telemetry unit.

The cost value is telemetry, not a billing invoice, and no currency is inferred from it.

### Numeric calibration

The shared-forward algorithm uses one causal CE vector and three VJPs. Both development profiles
passed. The preregistered selector froze `bf16_checkpoint_tf32_v10_control` before validation.

| Development metric | TF32 control | Strict accumulation |
| --- | ---: | ---: |
| Maximum GP delta | 0.00152472 | 0.00178094 |
| Maximum relative error | 0.02121472 | 0.02296097 |
| Minimum cosine | 0.99977505 | 0.99973922 |
| Maximum update TV | 0.00015072 | 0.00019001 |
| Resolvable pair direction | 22/22 | 24/24 |

### Independent validation

The frozen TF32 profile failed independent raw numeric validation:

| Metric | Observed | Frozen threshold | Result |
| --- | ---: | ---: | --- |
| Maximum GP delta | 0.00282111 | <= 0.0023 | failed |
| Maximum relative error | 0.03005580 | <= 0.027 | failed |
| Minimum cosine | 0.99954834 | >= 0.99967 | failed |
| Maximum loss identity error | 4.16e-8 | <= 1e-6 | passed |
| Maximum update JS | 3.11e-8 | <= 1e-6 | passed |
| Maximum update TV | 0.00015587 | <= 0.00023 | passed |

Failure localization found one `temporal_growth` relative-error violation, two cosine violations in
the same state, and one `comparison` GP-delta violation. In contrast, validation retained 100%
direction agreement on 23 resolvable pairs, 6/6 winner agreement, and 6/6 strict task-permutation
agreement. Those diagnostics do not override the raw gate.

Aggregate identity:
`finance_gradient_precision_v5_report:23a368bfb49741f7b3063fd4e467175232766b39544f601885267964a1f8e97a`.

A separate integrity replay verified 185 canonical identities, all 180 checkpoints, and zero
pairwise task/Evidence/semantic overlap. Audit identity:
`finance_v16_numeric_integrity_audit:f13b93b180eb23a40805729bd575bca021c460f22442a255812998e7b293ecfc`.

## Authorization State

The scientifically correct state is:

- aggregate status: `failed`;
- failure: `raw_numeric_precision_failed`;
- `production_authorized=false`;
- no `frozen_numeric_contract.json` exists;
- no v16 Contribution credential exists;
- sealed candidate unopened;
- GP-C and independent intervention not run;
- Student training and benchmark effects cannot be attributed to v16 Contribution optimization.

The unused strict profile cannot be run on the already-opened validation population as a post-hoc
alternate. Thresholds cannot be relaxed after observing validation.

## Recovery-Safe Next Step

The next experiment must be a newly preregistered, development-only numerical root-cause study. It
should isolate loss accumulation, sparse-projection dtype, token-region reduction, and VJP
recomposition on a new population. Any algorithm change requires a new version, new independent
validation tasks, and newly frozen thresholds. The current sealed candidate and v14 holdout remain
closed.

Higher-order Hessian or Richardson Contribution approximations are premature: the first-order
numeric fidelity gate has not yet passed independent validation.

## Authoritative References

- `docs/finance_v14_real_agent_gradient_projection_report.md`
- `docs/finance_v16_numeric_contract_validation_report.md`
- `docs/vtdo_experiment_protocol.md`
- `docs/valid_trajectory_distribution_optimization.md`
- `docs/server_recovery.md`
- `artifacts/vtdo_experiment/finance_v16_numeric_recalibration_partitions_6x6x6_v3_20260804/report.json`
- `artifacts/vtdo_experiment/finance_v16_gradient_precision_calibration_v5_dev6_val6_v1_20260804/report.json`
