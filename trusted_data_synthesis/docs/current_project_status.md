# Current Project Status

Audit date: 2026-08-06

This status is reconstructed only from the current Git tree, immutable experiment artifacts,
credential-redacted recovery records, and checks rerun on the migrated server. Missing chat
messages are not treated as experimental evidence.

## Repository Identity

- Active repository: `/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis`
- Branch: `main`
- v17 implementation parent: `7b201fd`
- sealed retry implementation SHA-256: `1e9533f4c67096874ba28aa3f28e0319ed9e8d2d609d08b92f0d2197e6ad285a`
- Credentials remain process-environment inputs and are not tracked or serialized

The current change set adds the fail-closed v17 root-cause pipeline and the one-shot inherited
sealed-candidate executor, including immutable source manifests, per-state checkpoints, explicit
pre-observation retry lineage, and claim-bounded aggregation.

## Runtime And Data

The migrated environment is operational with Python 3.12, PyTorch 2.7.1+cu128, CUDA 12.8, and
eight NVIDIA A100-SXM4-80GB GPUs. No sealed experiment process remained after aggregation.

The read-only Finance Archive remains the active data dependency:

| Item | Verified value |
| --- | ---: |
| KG build | `kg_20260711_062123_bc4b4394` |
| Graph schema | `3.0` |
| Nodes | 913,475 |
| Edges | 5,734,348 |
| Fact nodes | 658,535 |
| DerivedFact nodes | 135,990 |

The newest DB-only build from the previous server remains unavailable. The immutable archive used
by the experiment is present and readable.

## Revalidated Code State

| Check | Result |
| --- | --- |
| Sealed-candidate focus | 6 passed |
| Ruff | passed |
| Mypy | passed, 237 source files |
| Pytest | passed, 379 tests in 116.96 seconds |
| Core generalization boundary | retained by full suite |
| Legal and Science contracts | retained by full suite |

The v17 tests reject altered plans, implementation manifests, profiles, splits, source jobs,
result rows, selection lineage, uncertainty envelopes, and stale contracts. Validation cannot run
before selection or with a nonselected profile. A failed aggregate cannot retain a stale numeric
contract.

## Historical Boundaries

### v14 production candidate

The immutable v14 candidate remains historical evidence:

- 30 real Finance tasks;
- 100 quotient trajectory states;
- 300 fresh state-conditioned realizations;
- 1,065/1,065 gradient artifact content hashes verified;
- stable realization sampling and positive internal proxy association;
- seven raw numeric-tail violations and three strict task-order reversals.

It was not reused to tune v16 or v17. Its status remains `partial` with
`production_authorized=false`.

### v16 recalibration

v16 used disjoint development, validation, and sealed-candidate populations. The BF16 TF32 profile
passed development but failed independent validation on relative error, cosine, and GP-score delta.
No v16 numeric contract was issued. Margin-aware ordering remained stable, so v16 localized the
bottleneck to raw gradient-level numerical fidelity rather than sampling or task ordering.

The unused v16 profile was not substituted post hoc, and the v16 validation set was not reused for
v17 tuning.

## v17 Numeric Root-Cause Experiment

### Population and real-Agent inputs

v17 created three fresh, balanced six-task partitions. Every partition contains one task from each
of six task families and binds 63 Evidence versions. Task, Evidence-version, and semantic overlap
across development, validation, and sealed candidate are all zero.

Development and validation each produced:

- 24/24 valid initial trajectories;
- 20 trajectory states;
- 60/60 released state-conditioned realizations.

The full real-Agent input funnel used 554 DeepSeek-V4-Pro calls and 4,092,455 tokens. Every API call
and JSON contract succeeded, fallback use was zero, and the provider-reported estimate summed to
`0.484361248`. That value is telemetry rather than an invoice. The numeric experiment itself made
no additional API calls.

### Development diagnosis

The preregistered matrix evaluated 20 realization-level records under eight profiles. Seven
profiles failed the unchanged raw numeric contract. Only `fp32_activation_strict` passed:

| Metric | BF16 control | FP32 activation |
| --- | ---: | ---: |
| Maximum relative error | 0.03436155 | 0.00641550 |
| Minimum cosine | 0.99952628 | 0.99997942 |
| Maximum GP delta | 0.00212896 | 0.00052523 |
| Maximum update TV | 0.00012564 | 0.00004071 |
| Pairwise envelope | 0.0043 | 0.0011 |

The paired FP32-versus-TF32-off contrast reduced relative error in 20/20 records, with mean
reduction `0.01451894` and a task-cluster bootstrap 95% interval of
`[0.01182715, 0.01846619]`. Projection FP32, FP64 accumulation, TF32-off, checkpoint changes,
separate forwards, and functional VJP did not cross the joint gate.

The development tail was a long `derived_growth_comparison` record whose differential region was
474/5,126 supervised tokens. Its paired relative error fell from `0.03436155` to `0.00363419` under
FP32 activation. The supported engineering diagnosis is BF16 forward-activation rounding in small
differential regions.

### Frozen selection and independent validation

The selector froze `fp32_activation_strict` and an uncertainty envelope of `0.0011` before observing
validation. The independent validation then completed 20/20 fresh checkpoints and passed all gates:

| Metric | Observed | Frozen threshold |
| --- | ---: | ---: |
| Maximum GP delta | 0.00068376 | <= 0.0023 |
| Maximum relative error | 0.00602399 | <= 0.027 |
| Minimum cosine | 0.99998186 | >= 0.99967 |
| Maximum loss identity error | 5.95e-8 | <= 1e-6 |
| Maximum update JS | 5.86e-9 | <= 1e-6 |
| Maximum update TV | 0.00005472 | <= 0.00023 |

All 25 resolvable state pairs, all six task winners, and all six strict task permutations agreed.

Authoritative identities:

- report: `finance_gradient_numeric_root_cause_report:8f9db5c9249904f9846cb7482ad428f0181407a3580d7a00437fa885be57306c`;
- contract: `finance_gradient_numeric_contract:e2a1c890af575f477389b0bfb1475810aeecec3e5f4bf3a6213c552a82fa86b7`.

## v18 Inherited Sealed Numeric Candidate

The first attempt failed before any state metric was computed because the checkpoint loader read
`jobs` from the outer source manifest instead of its nested descriptor. The immutable v1 result
records `execution_failed`, `KeyError('jobs')`, zero checkpoints, and no numeric summary.

A new retry plan allowed only that source-manifest lookup repair and froze every scientific input
unchanged. It computed 20/20 fresh diagnostic checkpoints on GPUs 3-5 and passed all frozen gates:

| Metric | Observed | Frozen threshold |
| --- | ---: | ---: |
| Maximum GP delta | 0.00081042 | <= 0.0023 |
| Maximum relative error | 0.00633034 | <= 0.027 |
| Minimum cosine | 0.99997997 | >= 0.99967 |
| Maximum loss identity error | 5.31e-8 | <= 1e-6 |
| Maximum update JS | 3.37e-9 | <= 1e-6 |
| Maximum update TV | 0.00005026 | <= 0.00023 |

All 24 resolvable pairs, all six task winners, and all six strict task permutations agreed. The
result hash is
`finance_gradient_numeric_sealed_result:ed13f8f07830ad47471293a8c73c22f464844959699b1b91d7c6cc99c94721d2`.

## Authorization State

The scientifically correct state is:

- inherited sealed numeric status: `passed`;
- `sealed_numeric_contract_passed=true`;
- `numeric_contract_authorized=true`;
- `production_authorized=false`;
- `contribution_authorized=false`;
- allowed next stage: `preregister_contribution_authorization_experiment`;
- VTDO updates, Student training, and downstream claims remain unauthorized.

The pass establishes that the frozen numerical execution path generalizes to the untouched sealed
population. It does not establish that GP-C predicts independent finite intervention utility.

## Next Step

Preregister a separate Contribution authorization experiment with independent estimation and
finite-intervention targets. Reuse the frozen FP32 numeric profile without threshold tuning. Do not
promote this sealed result directly into a VTDO update or production release.

## Authoritative References

- `docs/finance_v18_sealed_numeric_authorization_report.md`
- `docs/finance_v17_numeric_root_cause_report.md`
- `docs/finance_v16_numeric_contract_validation_report.md`
- `docs/finance_v14_real_agent_gradient_projection_report.md`
- `docs/vtdo_experiment_protocol.md`
- `docs/valid_trajectory_distribution_optimization.md`
- `docs/server_recovery.md`
- `artifacts/vtdo_experiment/finance_v17_sealed_numeric_candidate_retry_v2_20260806/report.json`
- `artifacts/vtdo_experiment/finance_v17_numeric_root_cause_dev20_val20_temp02_v13_20260805/report.json`
- `artifacts/vtdo_experiment/finance_v17_numeric_root_cause_dev20_val20_temp02_v13_20260805/frozen_numeric_contract.json`
