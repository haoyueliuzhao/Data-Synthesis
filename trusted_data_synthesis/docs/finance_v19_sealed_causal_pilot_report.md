# Finance v19 Sealed Causal Pilot Report

Date: 2026-08-06

## Executive conclusion

Finance v19 completed the first sealed causal pilot permitted by the v18 numeric authorization.
The strict-FP32 Gradient Projection execution path passed on the complete six-task pilot. The
independent finite-intervention target then failed its preregistered identifiability gates on both
Estimation and Validation before GP-C could be evaluated.

The resulting decision is fail-closed:

```text
numeric execution                         passed
finite-target identifiability             failed
GP-C rank/distribution/regret evaluation  not run
Authorization objective                   unopened
Contribution approximation                unauthorized
real VTDO update                          forbidden
Contribution used by real rounds          0
```

This result does **not** show that Gradient Projection is invalid. It shows that the current
multi-radius finite-intervention target cannot provide stable independent causal supervision at
the tested radii and objective support.

## 1. Frozen scope

The pilot consumed the exact inherited v17/v18 sealed population and froze a new v19 execution
contract before opening any new measurements:

| Item | Frozen value |
| --- | --- |
| Tasks | 6 |
| States | 20 |
| Realizations | 60, exactly 3 per state |
| Objective Support | 4 Estimation + 4 Validation + 4 unopened Authorization records |
| Numeric profile | `fp32_activation_strict` |
| Required GPUs | exact three-device placement |
| Estimator candidate | GP-C, contingent on target identifiability |
| Finite radii | `0.1`, `0.05`, `0.025` |
| Finite design | two-level Richardson, block size 7, two Hadamard designs |
| Success transition | fresh 30-task independent authorization study |
| Failure transition | retain Contribution zero and investigate estimator bias |

The execution contract hash is:

```text
finance_contribution_numeric_execution_contract:0addd481a94efe702ee999b8e112b5a3c365bdf77149c331da484c384535e337
```

The Authorization partition remained inaccessible throughout the run. The pilot was never
production-authorization eligible, even under a successful outcome.

## 2. Engineering corrections

The v19 implementation adds three explicit fail-closed layers:

1. `phase1_contribution_numeric_execution.py` rebases the inherited sealed population into a
   content-addressed six-task causal-pilot contract without changing the v18 profile or thresholds.
2. `phase1_contribution_causal_pilot.py` accepts GP-C evidence only after both Estimation and
   Validation finite targets pass. It can also materialize an immutable prerequisite-failure
   report without opening GP-C or Authorization.
3. `phase1_finite_radius_diagnostic.py` permits a post-failure radius diagnostic while marking all
   outputs non-authorizing and binding them to their failed source reports.

During integration, downstream finite-target and GP-C replay expected the abstract objective mode
`eval`, while the executable gradient artifact correctly froze the exact mode
`deterministic_eval_with_checkpoint_wrappers`. The implementation now propagates and verifies the
exact execution-mode identity throughout the gradient, finite-target, and GP-C chain. The contract
was not weakened to the abstract alias.

An initial execution directory records an out-of-memory diagnostic attempt. It produced no
scientific evidence and is not part of the successful contract. The final run used exact
three-device sharding, model offload, and efficient SDPA under the frozen strict-FP32 semantics.

## 3. Gradient execution evidence

All 60 state realizations completed and passed numeric and sampling-stability gates.

| Metric | Result | Frozen bound |
| --- | ---: | ---: |
| Maximum loss-identity absolute error | `5.3101e-8` | `<= 1e-6` |
| Maximum token-gradient recomposition relative error | `0.0068513` | `<= 0.027` |
| Minimum token-gradient recomposition cosine | `0.9999770` | `>= 0.99967` |
| Maximum GP-score absolute delta | `0.0007361` | `<= 0.0023` |
| Minimum task-rank agreement | `1.0` | `>= 1.0` |
| Maximum update total variation | `3.8020e-5` | `<= 2.3e-4` |
| Maximum update Jensen-Shannon divergence | `2.2476e-9` | `<= 1e-6` |

The gradient plan and report are:

```text
finance_contribution_gradient_plan:50fec1cd00a251913f96aec0976d30be1ebfdfc2f0387bc6ed0f69c97ba4c9c8
finance_contribution_gradient_report:7b9d3f28241921bf0a9529c68e8c67afcd8438b92f8fd2bfa27c70e0f84307a1
```

These measurements reproduce the v18 conclusion on a larger causal-pilot workload: numeric
execution is no longer the blocker.

## 4. Independent finite-target result

Estimation and Validation each completed 204 observations: 34 non-null intervention directions,
three radii, and both signs. No observation was borrowed across objective roles.

| Metric | Estimation | Validation | Gate |
| --- | ---: | ---: | ---: |
| Observation count | 204 | 204 | complete |
| Coordinate count | 14 | 14 | frozen |
| Design count | 2 | 2 | frozen |
| Reconstruction relative error | `0.5065` | `0.3774` | `<= 0.1` |
| Mean radius instability | `0.7305` | `0.6162` | diagnostic |
| p95 radius instability | `1.5420` | `1.4557` | `<= 0.25` |
| Signal RMS | `2.7160e-4` | `3.9363e-4` | diagnostic |
| Null replay RMS | `0` | `0` | diagnostic |

Both reports failed the same two gates:

```text
reconstruction_relative_error_exceeded
p95_radius_instability_exceeded
```

The finite reports are immutable:

```text
Estimation: finance_finite_target_report:b524fe4e2404ab770638ff9f182c7c76d7a43628e0e9628c71c393b89a6affaf
Validation: finance_finite_target_report:c6252234be78426abea49364f7322189cd595e09f2425bc9b53b67dba4ac37e9
```

The very large signal-to-null ratios are caused by deterministic zero null replay and must not be
read as evidence of target validity. Directional derivatives were nonzero, but their magnitude and
often their sign were unstable across radii. The target therefore failed before any comparison to
GP-C was scientifically admissible.

## 5. Prerequisite closure

The causal-pilot controller materialized a blocked prerequisite report rather than synthesizing a
partial GP-C result:

```text
finance_contribution_causal_pilot_prerequisite_report:3c7ab2672ad88b23a939a96201b9bf737faa47c685fafd5c94318110e51cbfa8
```

It records:

```text
status                                blocked_prerequisite
gp_c_executed                         false
authorization_objective_access        forbidden
contribution_approximation_authorized false
production_authorization_eligible     false
allowed_next_stage                    retain_contribution_zero_and_investigate_estimator_bias
```

This closes a loophole in which a failed target stage could otherwise leave the experiment without
an auditable terminal artifact.

## 6. Smaller-radius diagnostic

After the immutable failure decision, a separate diagnostic selected the lexicographically first
eight non-null directions in each objective role. Selection did not use outcome values. It reused
the `0.025` anchor and evaluated `0.0125` and `0.00625`, yielding 32 new observations per role.

| Metric | Estimation source | Estimation smaller | Validation source | Validation smaller |
| --- | ---: | ---: | ---: | ---: |
| Median radius instability | `0.6258` | `0.6680` | `0.5014` | `0.9350` |
| p95 radius instability | `1.7424` | `1.8578` | `1.2972` | `1.7024` |
| Sign-consistency rate | `0.625` | `0.250` | `0.750` | `0.375` |
| Direction improvement rate | - | `0.375` | - | `0.125` |

Both diagnostics conclude:

```text
smaller_radius_does_not_restore_local_linearity
```

Their report hashes are:

```text
Estimation: finance_finite_radius_diagnostic_report:f92fb476f8401654ee765da95045b4d073e04d1b0ccb592950f8a34015d04edb
Validation: finance_finite_radius_diagnostic_report:22a9214e2a001467b79bdfb61aa5e7fe1325f2973fc48a16448a9169151ef4e9
```

These measurements are post-selection diagnostics. They cannot alter the failed v19 decision or
serve as authorization evidence.

## 7. Scientific interpretation

The experiment separates three claims that were previously easy to conflate:

1. **Execution claim:** the strict-FP32 path computes the frozen gradients and updates reliably.
   v19 supports this claim.
2. **Target claim:** the selected finite intervention protocol exposes a stable local directional
   target. v19 rejects this claim at the tested radii and support.
3. **Proxy claim:** GP-C tracks a valid independent target. v19 provides no evidence either way,
   because the target prerequisite failed and GP-C was not run.

The result narrows the next research problem from generic numeric reliability to target
identifiability. It does not justify moving directly to Hessian, influence, or hypergradient
methods before a trustworthy target measurement exists; those estimators would face the same
validation ambiguity.

## 8. Next-stage protocol

The current Authorization population and thresholds must remain immutable. A successor experiment
requires a new preregistered identity and should first improve target observability, not retune the
existing failed population.

Recommended order:

1. Increase objective support and report repeated objective-loss measurement variance before
   estimating any derivative.
2. Normalize intervention radii by actual parameter-step norm and verify parameter-space movement
   independently of the nominal contrast radius.
3. Add repeated symmetric measurements per direction and a noise-aware slope model with confidence
   intervals rather than relying on one deterministic slope at each radius.
4. Predefine an identifiability-only development study with disjoint tasks; freeze the resulting
   target protocol before opening a fresh validation population.
5. Only after both target partitions pass should GP-C be computed and compared on rank,
   distribution movement, and target regret.
6. A fresh 30-task Authorization study may be planned only after the six-task causal pilot succeeds
   under that new target protocol.

Until then:

```text
Contribution = 0
production_authorized = false
real VTDO Contribution update = forbidden
```

## 9. Artifact locations

Primary artifact root:

```text
artifacts/vtdo_experiment/finance_v19_sealed_causal_pilot_fp32_alg_v2_20260806/
```

Important files:

```text
execution_contract.json
gradient/plan.json
gradient/report.json
local_updates/local_update_manifest.json
estimation/plan.json
estimation/report.json
validation/plan.json
validation/report.json
prerequisite_failure_report.json
estimation_radius_diagnostic/report.json
validation_radius_diagnostic/report.json
```

The initial out-of-memory diagnostic is retained separately at:

```text
artifacts/vtdo_experiment/finance_v19_sealed_causal_pilot_fp32_v1_20260806/
```

It is operational telemetry only and is not included in any scientific gate.


## 10. Software verification

The implementation was validated after the final artifact and documentation updates:

```text
Ruff:          passed
Mypy:          240 source files, no issues
Pytest:        393 passed in 119.78 seconds
git diff check: passed
```

These checks establish implementation consistency. They do not change the failed scientific gate
or authorize any Contribution use.
