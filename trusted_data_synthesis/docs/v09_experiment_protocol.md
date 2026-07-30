# v0.9 Canonical Experiment Protocol

Protocol ID: `quality_feedback_closed_loop.finance_primary.v1`

This document is the canonical interpretation contract for v0.9 artifacts. Code and generated
manifests must carry the same protocol ID. Historical v0.8 D1-D5 artifacts remain useful for
engineering regression, but they are not the causal cohort labels of this experiment.

## Research Questions

| ID | Question | Primary evidence |
| --- | --- | --- |
| RQ1 | Can executable Quality Contracts produce reliable, localized feedback? | counterfactual detection, root-cause, and closure metrics across Finance, Legal, and Science |
| RQ2 | Does structured feedback improve the next synthesis policy? | Cell distribution shift, targeted failure reduction, and diversity preservation |
| RQ3 | Does feedback-refined data improve a trained financial agent? | equal-budget C3/C4 training and held-out financial evaluation |

RQ1 is cross-domain. RQ2 and RQ3 use Finance as the primary synthesis and training domain.

## Domain Roles

| Domain | Contract/calibration validation | Round-0 feedback validation | C1-C4 training |
| --- | --- | --- | --- |
| Finance | yes | yes | yes, 100% |
| Legal | yes | yes | no |
| Science | yes | yes | no |

Legal and Science constrain Core generality and test feedback transfer. They are not mixed into the
primary training cohorts. Evaluation may retain their held-out Contract suites, but cross-domain
results must be reported separately from the Finance training-utility claim.

## Causal Cohorts

The only primary cohort IDs are:

| ID | Definition |
| --- | --- |
| C1 | conventional synthetic |
| C2 | evidence-grounded |
| C3 | verified static policy |
| C4 | feedback-refined verified policy |

`co_compilation` (C1/C2/C3) remains exploratory because its compilation contracts differ. The
identified CCGR contrast is `C4 - C3`: identical model, tokens, seed, compiler, candidate pool,
Finance quota, and training format; only the calibrated allocation policy differs.

Historical `D1` through `D5` identify v0.8 engineering regression datasets only. They must never be
renamed into, substituted for, or pooled with C1-C4.

## Feedback Ablations

Seven policy controls are frozen:

| ID | Interpretation |
| --- | --- |
| `static_verified` | no policy update (`eta=0`) |
| `score_only_feedback` | Cell mean scalar quality `q_cell`; utility `-(1-q_cell)+gamma*U`; Clause routes and binding tightening are unavailable |
| `raw_failure_reweighting` | no calibration (`kappa=1`) |
| `no_defect_suppression` | remove the `- beta D` term |
| `no_coverage_regularization` | remove the `gamma U` term |
| `random_same_shift` | matched random shift at Full CCGR total variation |
| `full_ccgr` | calibrated, localized `G - beta D + gamma U` |

The score-only control tests whether structured feedback adds value beyond an authoritative scalar
quality signal. In the real-Agent path, `q_cell` is the mean of
`AgentValidationSample.quality_vector.overall_score` for tasks bound to the Cell. The score source,
QualityVector policy hash, task-score manifest hash, and score count are frozen. Missing scores,
mixed policies, or incomplete Cell coverage fail closed. The offline pilot uses a separately named
binary clean-Contract score only to verify interface, hashing, and policy execution. Because those
clean scores are normally all one, the offline pilot does not validate the statistical effect of
the score-only ablation and cannot be presented as real-Agent score evidence. This control cannot
see Clause roots or route ownership and cannot tighten a Binding. `raw_failure_reweighting` remains
the no-calibration control; it is not a second score-only variant.

## Validation And Refinement Populations

Every v5 refinement manifest records two populations independently:

- RQ1 validation: all Finance, Legal, and Science task, exposure, signal, and domain counts;
- RQ2 refinement: Finance-only task, exposure, signal, Cell, Clause feedback, and policy updates.

The historical `feedback_*` totals alias the RQ1 validation totals for compatibility. A passed
online gate still requires accepted samples in all three validation domains. Runtime allocation and
materialization use only nonzero active quotas (`finance=N`); published cohort manifests retain the
zero-filled declared contract (`finance=N, legal=0, science=0`).

Only C3 and C4 are required training cohorts in the first causal run. Other ablations are policy
artifacts until separately materialized with equal token and compiler controls.

## Frozen Execution Order

```text
cross-domain counterfactual calibration
  -> real Finance/Legal/Science Round-0 Contract validation
  -> Finance-only CCGR policy compilation
  -> new, disjoint C3/C4 materialization
  -> equal-token C1-C4 Finance training
  -> internal Finance evaluation
  -> external Finance benchmarks
  -> separate Legal/Science contract-transfer reporting
```

External benchmark status remains `not_executed` until native task adapters and results exist.
Passing the offline pilot proves pipeline executability only. A training-utility claim requires a
passed real-Agent gate, newly compiled C3/C4 data, completed training, and held-out evaluation.

## Benchmark Contract

The planned primary Finance evaluation is limited to FinQA, TAT-QA, and FinanceBench, alongside
the frozen internal Finance Contract suite. LegalBench and SciFact may be used only as separately
reported Legal/Science contract-transfer subsets; they are not additional training domains. A
benchmark remains a plan, not evidence, until its native adapter, dataset version, contamination
check, scoring contract, and result artifact are pinned. The first experiment must not add more
benchmarks post hoc in response to model results.

## Version Compatibility

`training_utility_v09.v5` is the first schema release carrying this protocol explicitly. Historical
`training_utility_v09.v4` manifests remain loadable with their original six-ablation and 80/10/10
contracts; they must not be silently relabeled as v5 or used as evidence for the Finance-only
primary experiment.
