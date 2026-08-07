# Finance v20 Finite Target Identifiability Report

Date: 2026-08-06

Final status: `failed`

Scientific transition:

```text
retain Contribution = 0
-> redesign target measurement
```

This report records a development-only identifiability study. It does not evaluate GP-C, open the
Authorization objective, authorize a Contribution estimate, update VTDO, train a Student, or
support a downstream performance claim.

## Executive Conclusion

v20 implemented every target-measurement repair preregistered after the v19 audit:

- Objective Support increased from 4 to 16 records per Estimation and Validation role;
- perturbations were normalized by measured parameter-step norm;
- seven direct-coordinate anchors were added;
- each role was divided into four mutually exclusive Objective micro-splits;
- direct, block-2, block-4, and block-7 designs were compared;
- a local odd-cubic model separated first-order slope from finite-radius nonlinearity.

The execution contract passed, but the finite target remained unidentifiable. All seven direct
coordinates had 95% slope intervals crossing zero in both roles. Estimation and Validation both
failed anchor identifiability, local linearity, and design reconstruction. Only four of seven
direct-coordinate signs agreed across roles, for cross-role agreement of `0.5714` against the
frozen requirement of `1.0`.

The supported conclusion is therefore:

```text
The current finite Objective target is not reliably observable under the tested first-order
parameter perturbation protocol. This result neither validates nor falsifies GP-C.
```

## Audit-to-Experiment Mapping

| v19 audit requirement | Frozen v20 implementation | Outcome |
| --- | --- | --- |
| Increase Objective Support | 16 Estimation, 16 Validation, 16 sealed Authorization records | implemented |
| Normalize actual parameter movement | target ratios `0.01/0.005/0.0025` of the measured global update norm | passed |
| Add direct-coordinate gold subset | seven frozen direct coordinates | all unidentifiable |
| Repeat on independent Objective subsets | four disjoint micro-splits per role | implemented |
| Compare block sizes | direct, block-2, block-4, block-7 | all block families failed |
| Fit local slope and odd nonlinearity | `delta J = a1*s + a3*s^3` | local-linearity gate failed |
| Preserve fail-closed gate order | Target gate precedes GP-C and Authorization | passed |

## Immutable Inputs

### Population and real-Agent trajectories

The target population was selected from predecessor-unused reserve tasks before target outcomes
were observed:

| Item | Value |
| --- | ---: |
| Finance tasks | 6 |
| Task families | 6 |
| Trajectory states | 20 |
| Realizations per state | 3 |
| Released realizations | 60/60 |
| Evidence versions | 63 |
| Predecessor partition overlap | 0 |

The task families were comparison, derived growth comparison, registered ratio, temporal absolute
change, temporal growth, and temporal average.

Real-Agent generation used 271 successful DeepSeek-V4-Pro calls and 1,983,016 tokens across the
initial-distribution and state-realization stages. JSON-contract success was 271/271, fallback use
was zero, and provider-reported cost telemetry summed to `0.427015865`. This is provider telemetry,
not an invoice. The numeric target study itself made no API calls.

### Objective partitions

The frozen support contains:

```text
Estimation:   16 records
Validation:   16 records
Authorization: 16 records, identity frozen, Objective access forbidden
```

Estimation and Validation each contain four disjoint four-record micro-splits. The aggregate
replays every record identity, token count, micro-split assignment, record-level loss, and
token-weighted Objective value. Authorization observation count remained zero.

### Direction design

The quotient design contains 14 coordinates and 31 direction rows:

| Design family | Rows |
| --- | ---: |
| Direct coordinate | 7 |
| Block size 2 | 7 |
| Block size 4 | 8 |
| Block size 7 | 8 |
| Null replay | 1 |

Each direction was evaluated at three target parameter-step ratios and both signs. This produced
`31 * 3 * 2 = 186` observations per Objective role and 372 formal observations overall.

## Numeric Prerequisite

The inherited strict-FP32 execution path passed again on the new population:

| Metric | Observed | Frozen threshold |
| --- | ---: | ---: |
| Maximum loss-identity error | `4.2960e-8` | `<= 1e-6` |
| Maximum gradient recomposition relative error | `0.0073369` | `<= 0.027` |
| Minimum gradient recomposition cosine | `0.9999732` | `>= 0.99967` |
| Maximum GP score delta | `0.0005243` | `<= 0.0023` |
| Maximum update total variation | `3.2569e-5` | `<= 0.00023` |
| Minimum task rank agreement | `1.0` | `>= 1.0` |

This passes only the execution prerequisite. The Gradient report remains `partial` by design
because GP-C and the independent local distribution intervention were not run.

## Formal Execution

The formal study used two partitions per Objective role. Each partition produced exactly 93 rows.
All four worker reports completed with the same measured global parameter-step norm,
`0.597611554714901`. Maximum parameter-step ratio relative error was `4.3255e-7`, well below the
frozen `5e-5` bound.

| Objective role | Partition | Assigned | Resumed | Added | Runtime hours | Peak GPU GiB | Requested GPUs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Estimation | 0 | 93 | 0 | 93 | `6.749` | `25.793` | `0,2,3` |
| Estimation | 1 | 93 | 0 | 93 | `7.980` | `21.413` | `1,4,7` |
| Validation | 0 | 93 | 8 | 85 | `6.531` | `24.326` | `5,6,0` |
| Validation | 1 | 93 | 6 | 87 | `8.046` | `21.698` | `2,4,5` |

One earlier single-partition run was stopped after one observation per role solely to estimate
scheduling cost. It is a superseded scheduling probe and is not included in any formal aggregate.
During the formal run, two Validation workers were checkpointed briefly to test resource
contention, then resumed from immutable checkpoints after no throughput benefit was observed. No
scientific input, threshold, observation, or role assignment changed.

## Frozen Gate Results

| Metric | Estimation | Validation | Frozen requirement |
| --- | ---: | ---: | ---: |
| Observation count | 186 | 186 | 186 |
| Parameter-step ratio relative error, max | `4.3255e-7` | `4.3255e-7` | `<= 5e-5` |
| Direct anchor identifiable rate | `0.0000` | `0.0000` | `>= 1.0000` |
| Direct slope CV, max | `34.5470` | `4.3135` | `<= 0.5` |
| p95 nonlinearity ratio, max | `16.0095` | `63.3579` | `<= 0.25` |
| Block reconstruction error, max | `1.8606` | `1.8830` | `<= 0.15` |
| Block direction agreement | `0.6522` | `0.5652` | `>= 0.8` |
| Null Objective delta, max | `0.0` | `0.0` | `<= 1e-10` |

Both roles passed:

- numeric replay;
- parameter-scale replay;
- Objective measurement integrity;
- null replay.

Both roles failed:

- direct-anchor identifiability;
- local linearity;
- block-design reconstruction.

The combined report also failed cross-role direct-sign agreement: `4/7 = 0.5714`, against the
frozen requirement of `7/7 = 1.0`.

## Block-Size Diagnosis

| Role | Family | Mean reconstruction error | Max reconstruction error | Direction agreement |
| --- | --- | ---: | ---: | ---: |
| Estimation | block-2 | `0.9930` | `1.8493` | `0.4286` |
| Estimation | block-4 | `0.7595` | `1.5841` | `0.7500` |
| Estimation | block-7 | `0.8272` | `1.8606` | `0.7500` |
| Validation | block-2 | `0.8183` | `1.6165` | `0.5714` |
| Validation | block-4 | `1.1234` | `1.8830` | `0.5000` |
| Validation | block-7 | `0.8671` | `1.3114` | `0.6250` |

Reconstruction error does not increase monotonically with block size. Smaller blocks therefore do
not isolate the failure. Because direct anchors are also unidentifiable, the primary blocker is
Objective-level slope observability rather than only combined-direction interaction.

## Direct-Anchor Diagnosis

All seven Estimation and all seven Validation 95% slope intervals contain zero. Three coordinate
signs reverse across roles: one comparison coordinate, derived growth comparison, and temporal
growth. The other four signs agree, but none has a role-wise identifiable interval under the
frozen gates.

The direct-anchor result is decisive for interpretation: block reconstruction cannot be treated as
the sole cause when its supposed direct-coordinate gold values are themselves unstable.

## Scientific Decision

The combined fail-closed decision is:

```text
status                                  failed
gp_c_evaluated                          false
authorization_objective_access          forbidden
authorization_objective_observation_count 0
contribution_approximation_authorized   false
production_authorization_eligible       false
next_transition                         retain_contribution_zero_and_redesign_target_measurement
```

No threshold was changed after observing outcomes. A successor experiment must preregister a new
measurement target and use fresh support. The v20 result must not be reinterpreted as evidence for
or against GP-C, nor may its Estimation or Validation records be reused as an Authorization set.

## Integrity and Reproducibility

The implementation independently reconstructs the task distributions, quotient coordinates,
direct-anchor selection, direction design, micro-split assignments, baseline record content,
token-weighted objectives, parameter scales, null adapter identity, and all artifact hashes.
Unknown or modified semantics fail closed even if an attacker recomputes an outer JSON hash.

Authoritative identities:

- target population: `finance_target_identifiability_population:5ef341074777e31cfdda5ffd40edd797bb1301329021c502e860ba5296b410e4`;
- target contract: `finance_target_identifiability_contract:0289e1a4f6878df0350fa799a859e00b90f01dbdbb7299839422997f15c81250`;
- Objective Support report: `finance_contribution_evaluation_support_report:3eb38945a3d44f6049a8bfc8441b2f1d9a8a267a81533d4e3d8a529f6b51e27a`;
- Gradient report: `finance_contribution_gradient_report:e1cbec4a44ab28e78795d3593a54a1b706a4a511a1854cf65a9c3ee4ea3534e3`;
- local update manifest: `finance_gp_c_local_update_manifest:1ae5e2e2b31d81a92a1f1c220f3bbab9463e7b0cce1e1d7b4276040869733141`;
- direction manifest: `finance_gp_c_finite_target_directions:696830a7595f049fc99440ae439b15f06f8e78ab2875a15d26f94ae73e959249`;
- direction-scale manifest: `finance_target_identifiability_direction_scale:f7f3ee8cff83dfa8df2f1c12b8d74f991a76e6097f713d3aa2bfcc0217b5200c`;
- formal plan: `finance_target_identifiability_plan:455f58ea6150ab542ba84e340e0b51e642b0c5eb985acbb99867dbc89508c09d`;
- Estimation report: `finance_target_identifiability_report:b5596172ddaaf20faa5b9c45a0c08de07809b746039599a5e88fd9071a888d4b`;
- Validation report: `finance_target_identifiability_report:93ad30d89157c63431ff499d66c323f394cee85d9275cb79e2ea76c1b557c2d5`;
- combined report: `finance_target_identifiability_combined_report:4d87c20695ca020b157d78c4f710485159d91fb5abd18452848b7a991d9120d5`.

Primary artifact directory:

`artifacts/vtdo_experiment/finance_v20_target_identifiability_study_p2_v1_20260806`

## Software Verification

- Ruff: passed;
- Mypy: passed for 242 source files;
- Pytest: 401 passed in 119.27 seconds;
- the completed experiment left no v20 GPU worker process;
- the only observed remaining GPU process belonged to another user and was not modified.
