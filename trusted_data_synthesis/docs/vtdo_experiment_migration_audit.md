# VTDO Experiment Migration Audit

## Active Protocol

The repository has one active paper experiment contract:

```text
vtdo_experiment.v6
```

Historical v0.8/v0.9 utility cohorts and v1-v5 VTDO outputs are not accepted as v6 inputs. The
active chain is:

```text
trajectory-state validation
-> fixed-potential operator control
-> exogenous and endogenous moving-potential tracking
-> recorded Explorer and cold-start Probe compilation and Round replay
-> paired local-Probe/finite-Intervention validation
-> paired beneficiary M0/M1 Probe
-> fixed-task-marginal causal arms
-> equal-supervised-token multi-seed training
-> immutable native FinQA/TAT-QA prediction and evaluation
```

## v6 Corrections

The v6 revision preserves the v5 three-level Contribution approximation and removes the remaining
single-task, single-round, and mutable-evaluation assumptions. Contribution identity is now
task-round scoped, validation is gated by confidence-interval lower bounds, exact Probe sets are
round-specific while their protocol family remains frozen, and benchmark evaluation requires a
complete typed manifest bound to training inputs, base-model contents, adapter contents, generation
configuration, and benchmark snapshot. It intentionally has no compatibility alias for an earlier
schema.

| Audited risk | Active treatment |
|---|---|
| The theoretical derivative was conflated with an empirical score | Synthetic Oracle, finite Intervention, and production local Probe are separate typed artifacts |
| A finite Intervention could be consumed as production Contribution | only a complete local-Probe manifest may update `pi`; Intervention is validation-only |
| Contribution validation compared two fields from one record | validation pairs an independently executed Probe and 5% Intervention on the same `(task, state, seed)` |
| Probe adaptation could inherit optimizer history | Probe uses a new zero-state SGD/AdamW optimizer for one to three steps; main optimizer state is forbidden |
| Validation/test identities were not structurally isolated | baseline training, per-state update sets, internal validation, and untouched final test are pairwise audited |
| Confidence changed the estimand | confidence and standard error are diagnostic only; raw gains are centered without shrinkage |
| Arm task marginals varied with states per task | every fixed-marginal arm has per-task weight exactly one |
| CCGR was interpreted as a strict causal arm | CCGR is explicitly a nonuniform task-distribution baseline |
| Production dynamics were ranked by an initial fixed target | the initial target is diagnostic-only; moving targets use tracking error and regret |
| Stability used raw `C x N` | the stop score uses current-round expected log potential and projective potential drift |
| Negative Contribution correlation could pass | signed positive thresholds are fail-closed |
| Global Contribution rank mixed tasks | within-task macro rank, pairwise concordance, centering, and task bootstrap are used |
| Contribution observations could mix identities | task-state-seed observations use a frozen seed-set hash and are aggregated with variance |
| Moving potential was induced only by VTDO exposure | exogenous shared is primary; VTDO-induced and method-specific tracks are supplementary |
| Real Round support had only a reader | recorded Explorer/probe inputs are independently replayed into immutable Round artifacts |
| Contribution model-state dependence was untested | a paired `M0 -> M1` probe freezes support and evaluation identity |
| Synthetic headline used raw `C x N` | expected log potential and anchored objective are primary; `C x N` is diagnostic |
| B5 silently selected the latest Round | the primary Round is explicit; Round 1/3 train and Round 5 is analysis-only |
| Equal compute was claimed without control | only equal supervised tokens are claimed; prompt/processed tokens, steps, and repetition are reported |
| Host-instrumented targets contained host outputs | targets contain model decisions and final answer, never observations or execution results |
| External snapshots only had hash checks | native FinQA/TAT-QA context, answer/program metrics, immutable predictions, and graded leakage are implemented |
| Quotient probes were incomplete | surface, independent-order, and semantic-separation probes are reported |
| `no_quotient` mixed fragmentation and noise | exact and noisy no-quotient ablations are separate |
| `no_anchor` had ambiguous semantics | no-global-anchor and no-coverage-prior ablations are separate |
| Five-seed intervals used a normal approximation | aggregate metrics use two-sided Student-t intervals |
| Main training used one seed | the frozen primary contract requires three explicit seeds |

The primary causal matrix is now:

```text
B2_validity
B2_contribution_only
B2_novelty_only
B4_random_state
B5_vtdo
```

B1 is a controlled-corruption lower bound. B3 is the historical CCGR task-distribution baseline.
They remain useful comparisons but do not identify the effect of changing only `pi(z|x)`.

## Historical v3 Baseline

The archive-backed v3 run below predates the active v6 contract. Its numbers remain historical
regression evidence, not evidence that the v4 feedback and benchmark components have run:

```text
artifacts/vtdo_experiment/finance_v3/
```

Validation completed on 2026-08-01:

```text
full pytest: 175 passed
Ruff:       passed
Mypy:       196 source files passed
diff check: passed
```

The real Finance state funnel is:

```text
accepted-task quota:                 100
candidate tasks attempted:           105
accepted tasks:                      100
accepted canonical trajectories:     468
states per task:                     3-5
mean states per task:                4.68
```

The quotient-state probes report:

```text
raw probe sequences:                 1,356
canonical states:                      468
surface invariance:                  100%
independent-order invariance:        100%
semantic mutation separation:       100%
false merges:                            0
```

The fixed-potential operator control verifies:

```text
configured history exponent:        0.5
observed contraction factor:        0.4999999999999995
maximum absolute factor error:      1.20e-14
projective contraction verified:    true
```

The five-seed moving-potential control verifies all 25 proximal transitions. Mean cumulative
dynamic regret is `1.6043` for VTDO, `11.7174` for static one-shot optimization, and `22.7642`
for no feedback. Mean tracking error is `0.3209`, `2.3435`, and `4.5528`, respectively. These
results support update direction and moving-target tracking under the controlled potential
sequence. They do not establish real-model downstream gain.

No controlled seed satisfied the strict two-transition stabilization threshold within five
rounds. The report records `0/5`, rather than converting finite-horizon movement into a convergence
claim.

## Historical v4 Component Run

The canonical v4 CPU-side experiment completed on 2026-08-01:

```text
artifacts/vtdo_experiment/finance_v4/
manifest status: partial
manifest hash:
vtdo_experiment_manifest:41250b37e8999aa892260081f7a431d0cc0220dac6f148789420ddd37e0c34e0
```

The `partial` status is intentional. It means the controlled and data-construction components
completed, while unavailable empirical feedback and downstream training remained blocked. The run
materialized 100 accepted Finance tasks from 105 attempts, 468 independently verified canonical
states, 525/525 accepted-strategy verifier passes, 100/100 rejected adversarial answer mutations,
and zero quotient false merges.

The primary method-neutral `exogenous_shared` moving-potential track produced:

```text
                         cumulative regret    mean tracking error
No feedback                    32.6155               6.5231
Static one-shot                17.8614               3.5723
Full VTDO                       1.6110               0.3222
```

All 25 proximal transitions passed exact objective replay. The minimum variational-objective gain
was `2.5991`, and the maximum KL to the analytic proximal optimizer was `1.61e-16`. The lower
95% confidence bounds of VTDO's regret advantage were positive against both no feedback
(`30.2094`) and static one-shot optimization (`15.8889`). The VTDO-induced shared and
method-specific closed-loop tracks also passed, but remain supplementary.

Practical stabilization was not observed for any of the five seeds within the five-round horizon.
The run therefore completed `finite_step_refinement_diagnostics`, not
`practical_refinement_stabilization_observed`.

The frozen evaluation contract loaded 2,810 FinQA/TAT-QA examples and found zero hard or soft
training collisions for the 100 task state pool. `B1_raw`, `B2_validity`, and
`B4_random_state` met their individual capacity and task-marginal contracts. The primary causal
matrix remained blocked because empirical multi-seed Contribution observations and real VTDO Round
artifacts were not configured.

The production smoke test also exposed a fail-closed reporting defect: an unavailable
within-state Contribution variance was formatted as a float. The renderer now emits `n/a` for
missing optional metrics, with a dedicated regression test.

## Current Readiness

The v6 code and canonical configuration are ready for new runs. The component-level manifest below
is a historical v4 artifact, not a v6 result and not a completed downstream-training result.

Ready now:

```text
fixed-potential operator verification
three separated moving-potential tracks with an exogenous primary control
synthetic headline metrics aligned to log potential and anchored objective
multi-seed Contribution observation and beneficiary-shift contracts
recorded real-feedback compiler with independent replay
native FinQA/TAT-QA context, metrics, leakage, and prediction contracts
frozen FinQA/TAT-QA snapshots: 2,810 evaluation-only examples
replayed v4 component manifest with an explicit partial status
```

Still blocked:

```text
paired Probe/Intervention observations: not configured
recorded Explorer/local-Probe outputs:     not configured
real lineage-linked VTDO Rounds:      not configured
paired M0/M1 Probe observations:       not configured
Contribution-only/Novelty-only arms:  require those Rounds
B5 VTDO and Round 1/3 arms:            require those Rounds
current CCGR task distribution:        not configured
GPU downstream training:               preflight is not formally ready
immutable trained-model predictions:   not generated
shared benchmark document identity map: not configured
```

The checkpoint preflight freezes analysis rounds `(1, 3, 5)` but permits training materialization
only for rounds `(1, 3)`. Round 5 cannot silently enter the training comparison.

## Claim Boundary

The current v6 implementation, frozen benchmark snapshots, and historical v4 component artifact
support claims about implementation correctness, native evaluation availability,
stationary-potential contraction, and controlled moving-optimum tracking. Historical v3 artifacts separately support the archived state-construction
claims above. Neither source supports empirical Contribution validity, real feedback stabilization,
or downstream model improvement. Those claims remain blocked until immutable multi-seed
observations, lineage-linked Rounds, trained adapters, and prediction manifests exist.
