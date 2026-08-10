# Current Project Status

Audit date: 2026-08-11

This status is reconstructed only from the current Git tree, immutable experiment artifacts,
credential-redacted recovery records, and checks rerun on the migrated server. Missing chat
messages are not treated as experimental evidence.

## Repository Identity

- Active repository: `/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis`
- Branch: `main`
- v22 exact-target measurement source commit: `3aa1b0c39d040f79f11bba6166573ec82d729377`
- v22 exact-target source tree: `b61605018f35ed9550aa02d6c89e164bbe7252c8`
- Credentials remain process-environment inputs and are not tracked or serialized

The current change set completes the v22 Development-only exact one-step target study and adds a
separately hashed v22.1 design analysis. The original 4,000 target observations and target report
are preserved unchanged. Validation and Authorization remain inaccessible, GP-C remains
unevaluated, and production Contribution remains zero.

The post-v22 plan now inserts a capability-sensitive Agent Runtime Pilot before any fresh
Validation. Domain-neutral tool and iterative Host-execution contracts, the three-arm Pilot gate,
and a Finance six-tool manifest are implemented. The real Archive tool executors, API Pilot,
frontier screening, and new exact-target measurements have not run.

## Runtime And Data

The migrated environment is operational with Python 3.12, PyTorch 2.7.1+cu128, CUDA 12.8, and
eight NVIDIA A100-SXM4-80GB GPUs. No sealed experiment process remained after aggregation.

After all v22 workers had exited, a separate root-owned process
`/opt/venv/render/bin/python3 --coin pearl` appeared at 10:22 and occupied GPUs 0, 1, 3, 4, 6, and
7. It is not a project process and was not terminated. At the same time, `/usr/bin/nvidia-smi` had
an invalid mixed-case ELF interpreter path; read-only inspection remained possible through the
system loader. Future GPU experiments should not start until the server operator reviews this
external workload and binary change. Neither event occurred during the completed v22 target
workers or changes their content-hashed artifacts.

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

## v21 Cancellation And v22 Development Expansion

v21 was stopped by operator request after Estimation and Validation each wrote 9 of 32 planned
observations. No aggregate was created, no GP-C evaluation occurred, and the partial rows are not
scientific evidence for target identifiability. All v21 workers are stopped.

v22 froze a pre-outcome Development-only population from the 420-task real Finance pool: 30 tasks
balanced across six families, 100 accepted states, and 312 public Evidence versions with zero
Evidence overlap across target tasks. A separate 64-record Objective role is task-, signature-, and
Evidence-disjoint from the targets and was frozen into eight micro-splits of eight. DeepSeek v4 Pro
completed 300 unconditioned Explorer draws and 500/500 state-conditioned realizations.

The exact target then completed 500/500 strict-FP32 state gradients and 8/8 Objective-gradient
micro-splits on two parallel three-GPU workers. It produced 4,000 crossed observations under one
shared global cold-start AdamW update. Maximum FP32/FP64 target delta was `1.0551e-11` and maximum
simplex-centering error was `1.1699e-11`.

Post-measurement dual-axis inference found that 26/30 primary coordinates were statistically
nonzero, while 30/30 primary coordinates and 100/100 total state coordinates were practically
equivalent under their update-derived MPE. No coordinate was meaningfully beyond MPE. Objective
micro-split variation accounted for `99.9443%` of nested measurement variance; realization
variation accounted for approximately `0.0005%`.

## Revalidated Code State

| Check | Result |
| --- | --- |
| Development target/design focus | 10 passed |
| Agent runtime/Pilot focus | 14 passed |
| Ruff check | passed |
| Ruff format, changed files | passed |
| Mypy | passed, 252 source files |
| Pytest | passed, 460 tests in 135.97 seconds |
| Core generalization boundary | 131 files, zero imports/branches/field accesses/violations |
| Tracked production-key pattern scan | zero `sk-...` hits; one explicit `test-secret` fixture |
| v22.1 deterministic replay | identical SHA-256 `a19bcc303026...` |
| Legal and Science contracts | retained by full suite |

The repository-wide formatter would rewrite 67 historical files under the currently installed
Ruff version. Those unrelated files were deliberately not reformatted; all changed Python files
pass the formatter and lint checks.

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


## v19 Sealed Causal Pilot

v19 used six fresh Finance tasks, 20 states, and 60 state-conditioned realizations. The strict-FP32
Gradient execution contract passed, but the independent finite target failed before GP-C was
evaluated. Estimation/Validation reconstruction error was `0.5065/0.3774` against `0.1`, and p95
radius instability was `1.5420/1.4557` against `0.25`. A smaller-radius diagnostic did not restore
local linearity. Authorization remained unopened and `Contribution=0`.

## v20 Finite Target Identifiability Study

v20 implemented the target-measurement redesign requested by the v19 audit. It used six new tasks,
20 states, 60 fresh real-Agent realizations, 16 Estimation records, 16 Validation records, and a
frozen but unopened 16-record Authorization partition. Estimation and Validation were each split
into four mutually exclusive Objective micro-splits.

The frozen direction design contained 14 quotient coordinates and 31 rows: seven direct anchors,
seven block-2 rows, eight block-4 rows, eight block-7 rows, and one null row. Three perturbation
ratios were normalized against the measured global parameter-step norm and evaluated in both
directions. The formal study completed 186 observations per role and 372 overall.

Execution integrity passed again. Maximum parameter-step ratio relative error was `4.3255e-7`,
maximum Gradient recomposition relative error was `0.0073369`, minimum recomposition cosine was
`0.9999732`, and null Objective delta was exactly zero.

Finite-target identifiability nevertheless failed:

| Metric | Estimation | Validation | Frozen requirement |
| --- | ---: | ---: | ---: |
| Direct anchor identifiable rate | `0.0000` | `0.0000` | `>= 1.0000` |
| Maximum direct slope CV | `34.5470` | `4.3135` | `<= 0.5` |
| Maximum p95 nonlinearity ratio | `16.0095` | `63.3579` | `<= 0.25` |
| Maximum block reconstruction error | `1.8606` | `1.8830` | `<= 0.15` |
| Block direction agreement | `0.6522` | `0.5652` | `>= 0.8` |

All fourteen role-wise direct-anchor confidence intervals crossed zero. Only four of seven direct
coordinate signs agreed across Estimation and Validation, so the combined `0.5714` agreement also
failed its frozen `1.0` gate. Block-size error was not monotonic, and direct anchors themselves
were unstable; the evidence therefore localizes the blocker to Objective-level slope
observability, not only to Hadamard-style direction interaction.

The combined status is `failed`; GP-C was not evaluated; Authorization observation count is zero;
and the only valid transition is `retain_contribution_zero_and_redesign_target_measurement`.

## Authorization State

The scientifically correct state is:

- strict-FP32 numeric execution status: `passed`;
- v20 finite-target identifiability status: `failed`;
- v22 Development exact-target execution status: `passed`;
- v22 primary practical-equivalence status: `30/30`;
- v22 all-state practical-equivalence status: `100/100`;
- v22 meaningful-beyond-MPE count: `0/100`;
- `gp_c_evaluated=false`;
- `authorization_objective_access=forbidden`;
- `authorization_objective_observation_count=0`;
- `production_authorized=false`;
- `contribution_authorized=false`;
- allowed next stage: `freeze_agent_runtime_pilot_after_capacity_audit`;
- VTDO updates, Student training, and downstream claims remain unauthorized.

The current evidence establishes reliable strict-FP32 execution and a precise exact one-step target
on Development. It also shows that every observed Development coordinate is materially below the
current MPE. This neither validates nor falsifies GP-C or theoretical Contribution: a proxy cannot
be meaningfully ranked against a Development target with no practically meaningful coordinates,
and no fresh Validation result exists.

## Next Step

Do not rerun GP-C, open Authorization, or issue the 60-task Validation contract. First implement the
real frozen-Archive tool executors, run a capacity audit, and freeze the 24-30 task Direct/Bare vs
Scripted Tool vs Autonomous Agent Pilot before any API outcome. A passing Pilot may advance only to
Beneficiary frontier screening and a new Agent population. Re-estimate Development variance under
that new generation kernel before freezing any Validation size. Do not reuse v20, cancelled v21,
or v22 tasks, Evidence, semantic signatures, trajectories, or Objective records.

## Authoritative References

- `docs/finance_v20_target_identifiability_report.md`
- `docs/finance_v22_development_power_plan.md`
- `docs/finance_v22_development_exact_target_report.md`
- `docs/finance_v23_capability_sensitive_agent_plan.md`
- `docs/finance_v19_sealed_causal_pilot_report.md`
- `docs/finance_v18_sealed_numeric_authorization_report.md`
- `docs/finance_v17_numeric_root_cause_report.md`
- `docs/finance_v16_numeric_contract_validation_report.md`
- `docs/finance_v14_real_agent_gradient_projection_report.md`
- `docs/vtdo_experiment_protocol.md`
- `docs/valid_trajectory_distribution_optimization.md`
- `docs/server_recovery.md`
- `artifacts/vtdo_experiment/finance_v20_target_identifiability_study_p2_v1_20260806/combined_report.json`
- `artifacts/vtdo_experiment/finance_v20_target_identifiability_study_p2_v1_20260806/estimation_report.json`
- `artifacts/vtdo_experiment/finance_v20_target_identifiability_study_p2_v1_20260806/validation_report.json`
- `artifacts/vtdo_experiment/finance_v17_sealed_numeric_candidate_retry_v2_20260806/report.json`
- `artifacts/vtdo_experiment/finance_v17_numeric_root_cause_dev20_val20_temp02_v13_20260805/report.json`
- `artifacts/vtdo_experiment/finance_v17_numeric_root_cause_dev20_val20_temp02_v13_20260805/frozen_numeric_contract.json`
