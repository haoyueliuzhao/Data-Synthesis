# Finance v13 Gradient Projection v12 Target-Boundary Integration

Date: 2026-08-04

## Claim boundary

This run validates the corrected Objective-Support-to-Gradient integration on real previously
materialized Finance Agent trajectories. It is a three-task engineering smoke, not a Contribution
authorization experiment. The immutable result remains:

```text
status = partial
production_authorized = false
Contribution = 0
```

No post-global GP-C estimate or independent local distribution intervention was opened.

## Contract repair

Objective Support v5 used one ambiguous task exclusion set for two different purposes. Tasks in
the frozen Gradient target population had to be unavailable to Objective Support sampling, but
they were subsequently also treated as unavailable to Gradient task selection. A valid 30-task
target pool therefore produced zero eligible Gradient tasks.

Objective Support v6 removes that field and freezes three non-interchangeable contracts:

- `gradient_target_contract`: the only tasks Gradient Projection may consume;
- `objective_support_exclusion_contract`: source, prior, and Objective Support tasks that Gradient
  must not consume;
- `future_population_exclusion_contract`: all identities unavailable to later population mining.

Each contract contains a canonical task-set identity. Evaluation replays all three identities,
requires the target and Objective Support sets to be disjoint, and requires the future exclusion
set to cover both. Gradient Projection v12 also requires its Artifact path and SHA-256 to be one of
the target Artifacts frozen by Objective Support.

## Frozen Objective Support

Artifact directory:

```text
artifacts/vtdo_experiment/
  finance_v13_objective_support_16x16x16_v3_target_boundary_20260804/
```

Key identities and results:

| Field | Value |
| --- | --- |
| Support contract | `finance_contribution_evaluation_support.v6` |
| Plan hash | `finance_contribution_evaluation_support_plan:63e45dd90cc2b1d9c9778c088a35cd3f984211b1d10a77574dcf26445b84778a` |
| Report hash | `finance_contribution_evaluation_support_report:75eeaf0bd8358014079b65cf4e43aa1b0f8e31da4361206115b2c8b21f8efdfa` |
| Gradient target tasks | 30 |
| Estimation / validation / authorization | 16 / 16 / 16 |
| Fresh candidate tasks | 80 / 80 |
| Task, semantic, Evidence overlap | 0 / 0 / 0 |
| Numeric contract | `finance_gradient_precision_contract:526e1c39d202b0168bede2e2df0ca08eeec5d0cc4587949bba554e0cef91396c` |
| Evaluation status | passed |

All six available Finance task families occur in every Objective partition. Program depth is 1--3,
Evidence count is 2--4, and the partitions contain multiple context, state-strategy, and
verification strata. Strict A100 replay produced NLL `0.1008982882`, `0.1012763608`, and
`0.1008470002` for estimation, validation, and authorization respectively. The authorization
partition remains sealed from estimator fitting.

## Gradient Projection v12 smoke

Artifact directory:

```text
artifacts/vtdo_experiment/
  finance_v13_gradient_projection_smoke_dev3_v9_target_boundary_v12_20260804/
```

| Field | Value |
| --- | --- |
| Plan hash | `finance_contribution_gradient_plan:d6e1193f410e9638db82bef884efefffe4869af064a11dc7ef41faef7b05b739` |
| Report hash | `finance_contribution_gradient_report:5eb8ac3f2e7c78920d30584a52faa8d6a9d8336abe7f2f31220ac6d210fb43a1` |
| Tasks / states / realizations | 3 / 11 / 11 |
| Objective records per fitted split | 16 |
| Macro Spearman / concordance / winner agreement | 1.0 / 1.0 / 1.0 |
| Numeric precision gate | passed |
| Realization stability gate | failed |

The strict numerical replay stayed inside every preregistered threshold:

| Metric | Observed | Threshold |
| --- | ---: | ---: |
| Loss identity absolute error | `5.55e-17` | `<= 1e-6` |
| Gradient recomposition cosine | `0.9998197` | `>= 0.99975` |
| Gradient recomposition relative error | `0.0190101` | `<= 0.022` |
| GP score absolute delta | `0.0018040` | `<= 0.0023` |
| Task rank agreement | `1.0` | `>= 1.0` |
| Update total variation | `0.0001843` | `<= 0.00027` |
| Update Jensen-Shannon divergence | `3.45e-8` | `<= 1e-6` |

These rank values compare estimation and validation Objective partitions inside this three-task
smoke. They are not independent finite-intervention validity evidence.

## Remaining blockers

The report correctly retained three blockers:

1. `gradient_realization_sampling_instability`: every state has one realization and mean ESS is
   `1.0`, below the frozen `1.5` minimum;
2. `post_global_update_gp_c_not_run`;
3. `independent_local_distribution_intervention_not_run`.

The minimum state-differential supervised-token fraction was `0.05158`, and the minimum
state-differential gradient fraction was `0.29555`; state signal therefore remains nontrivial, but
one trajectory cannot estimate within-state variation.

## Resource record

- Objective Support replay: one A100 80 GB, peak allocated `50,285,028,352` bytes.
- Objective-gradient build: A100 GPUs 0 and 3, `252.50` seconds.
- State-gradient build: six free A100 GPUs, 11 jobs, slowest worker `144.94` seconds.
- Occupied GPUs were excluded from the worker whitelist.

## Next executable gate

The next empirical run must materialize 3--5 fresh, on-target, independently verified, and
decision-trace-distinct trajectories for every selected task-state. For the full 30-task target
pool this is expected to require roughly 300--500 released realizations plus retries. API
credentials remain environment-only inputs. No credential was present in the process environment
during this continuation, so no new external Agent call was attempted and no historical secret was
recovered into a command or Artifact.

Only after the K=3--5 realization gate passes may the experiment compute post-global GP-C and open
the independently frozen distribution intervention.
