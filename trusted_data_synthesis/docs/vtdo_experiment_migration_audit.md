# VTDO Experiment Migration Audit

## Active Protocol

The repository has one active paper experiment contract:

```text
vtdo_experiment.v3
```

Historical v0.8/v0.9 utility cohorts and v1/v2 VTDO outputs are not accepted as v3 inputs. The
active chain is:

```text
trajectory-state validation
-> fixed-potential operator control
-> moving-potential tracking
-> real feedback Round assembly
-> fixed-task-marginal causal arms
-> equal-supervised-token multi-seed training
-> frozen internal and external evaluation
```

## v3 Corrections

The v3 revision resolves the experimental-identification problems found in the protocol audit.

| Audited risk | v3 treatment |
|---|---|
| Arm task marginals varied with states per task | every fixed-marginal arm has per-task weight exactly one |
| CCGR was interpreted as a strict causal arm | CCGR is explicitly a nonuniform task-distribution baseline |
| Production dynamics were ranked by an initial fixed target | the initial target is diagnostic-only; moving targets use tracking error and regret |
| Stability used raw `C x N` | the stop score uses current-round expected log potential and projective potential drift |
| Negative Contribution correlation could pass | signed positive thresholds are fail-closed |
| Global Contribution rank mixed tasks | within-task macro rank, pairwise concordance, centering, and task bootstrap are used |
| Contribution observations could mix identities | beneficiary, evaluation, probe, baseline, budget, seed, and snapshot identities are frozen |
| Real Round support had only a reader | immutable Explorer/probe inputs can be assembled into replayable Round artifacts |
| B5 silently selected the latest Round | the primary Round is explicit; Round 1/3 train and Round 5 is analysis-only |
| Equal compute was claimed without control | only equal supervised tokens are claimed; prompt/processed tokens, steps, and repetition are reported |
| Host-instrumented targets contained host outputs | targets contain model decisions and final answer, never observations or execution results |
| External snapshots only had hash checks | FinQA, TAT-QA, and FinanceBench adapters, metrics, intervals, and leakage audit are implemented |
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

## Canonical Validation

The archive-backed v3 run was generated at:

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

## Current Readiness

The v3 manifest is intentionally `partial`.

Ready now:

```text
B1 controlled corruption: 100 tasks, fixed task marginal
B2 validity:              100 tasks, 468 states, fixed task marginal
B4 random state:          100 tasks, 100 states, fixed task marginal
controlled theory and moving-potential experiments
real Finance multi-state and quotient validation
```

Still blocked:

```text
empirical Contribution observations: not configured
real lineage-linked VTDO Rounds:      not configured
Contribution-only/Novelty-only arms:  require those Rounds
B5 VTDO and Round 1/3 arms:            require those Rounds
current CCGR task distribution:        not configured
FinQA/TAT-QA/FinanceBench snapshots:   not configured
GPU downstream training:               preflight is not formally ready
```

The checkpoint preflight freezes analysis rounds `(1, 3, 5)` but permits training materialization
only for rounds `(1, 3)`. Round 5 cannot silently enter the training comparison.

## Claim Boundary

The current artifacts support claims about implementation correctness, real state-construction
capacity, quotient identity, stationary-potential contraction, and controlled moving-optimum
tracking. They do not yet support empirical Contribution validity, real feedback stabilization,
or downstream model improvement. Those claims remain blocked until immutable observations,
Rounds, evaluation snapshots, and multi-seed training results exist.
