# Finance v14 Real-Agent Gradient Projection Report

Date: 2026-08-04

## Decision

Finance Gradient Projection v14 completed the real-agent production-candidate path over
30 tasks, 100 trajectory states, and 300 independent trajectory realizations. Sampling
stability passed, all immutable identities replayed, and all 1,065 referenced gradient
artifacts passed an independent content-hash audit.

The frozen numeric precision contract failed. The run therefore remains `partial`, with
`production_authorized=false`. GP-C and the independent local distribution intervention
were deliberately not run. No threshold was changed after observing this population.

## Frozen Lineage

| Artifact | Immutable identity |
| --- | --- |
| Initial distribution | `finance_initial_distribution_report:5a3654a82b7d0d27d6076fc4c22afd758a1d2d9d9e3542c15d92e73b54f7d6b7` |
| State realizations | `finance_state_realization_report:89b9e0ef86207fe3bc9003792146b010aa9fb919467885a39cfc52cfb86cba2f` |
| Gradient plan | `finance_contribution_gradient_plan:bb343c008047a3ea863b621fcb2b4e0ea4c36f4bcb9b1d1b5fe404f5cd323c77` |
| Numeric contract | `finance_gradient_precision_contract:526e1c39d202b0168bede2e2df0ca08eeec5d0cc4587949bba554e0cef91396c` |
| Evaluation gradients | `finance_contribution_evaluation_gradient_manifest:3ce446be9642ce82b9893abeb77aa79c590c4624faa8d6776c528456ba69c217` |
| Gradient report | `finance_contribution_gradient_report:937b4637e92917958c6e63a3abe20a5ca2b4a922824013c0d51e79b62a26fe9b` |
| Tail analysis | `finance_gradient_projection_tail_analysis:9e2a8e6859f9e7e6a7d614b4e1a219639c676cdcde59d4974d8c2bfd027f0b7f` |

The exact state realization policy was
`independent_trajectory_draws`: all 300 trajectory IDs and hashes are unique. The 201
unique decision traces yield a decision-trace diversity rate of 0.67; repeated decision
structures are valid independent draws and are not treated as identity collisions.

## Real-Agent Generation

The initial-distribution run produced 120 valid catalog observations over all 30 tasks,
with full state support and no off-catalog valid trajectories. The state-realization run
requested and released exactly 300 realizations. It made 304 generation attempts: 302
returned successful generation records, two API attempts failed, and two generated
trajectories were rejected as invalid.

All selected calls used DeepSeek-V4-Pro; no model fallback occurred.

| Stage | API calls | Total tokens | Provider telemetry estimate |
| --- | ---: | ---: | ---: |
| Initial distribution | 363 | 2,128,893 | 0.575247915 |
| State realizations | 943 | 7,788,930 | 1.551701956 |

The last column is the provider telemetry estimate recorded by the client. It is not an
invoice, billing statement, or reliable measurement of actual monetary cost.

## Contract Repair

The v14 token-region contract uses aligned common-subsequence decomposition v2. Every
realization must have non-empty common and differential supervised-token regions, while
the hard coverage gate is evaluated at the task-pooled level. This avoids rejecting a
valid task because one independently generated surface realization has a small lexical
differential.

Observed coverage was:

| Level | Minimum differential supervised-token fraction | Role |
| --- | ---: | --- |
| Record | 0.013973 | Diagnostic |
| State pooled | 0.017908 | Diagnostic |
| Task pooled | 0.063309 | Hard gate, threshold 0.05 |

The typed authorization verifier independently replays every record partition, state
aggregate, task aggregate, manifest minimum, and the task-pooled gate. It rejects a
re-sealed manifest if any pooled statistic changes.

## Compute And Integrity

The 32 objective records were split into 16 estimation and 16 validation records. Their
gradients were built on one A100-80GB in 251.31 seconds with a 32.34 GB peak allocation.

The 300 state-gradient jobs ran as eight immutable partitions on eight A100-80GB GPUs.
Worker runtimes ranged from 740.04 to 790.16 seconds; aggregate GPU time was 6,111.87
seconds and maximum per-worker allocation was 42.82 GB. The active experiment directory
uses about 89 GB, including an 8.2 GB non-production archive from the stopped one-GPU
partition experiment.

The tail analyzer independently replayed:

- the plan, aggregate report, and evaluation manifest hashes;
- all 300 worker result hashes and the exact frozen job set;
- 300 unique job IDs and 300 unique result hashes;
- existence and full SHA-256 content of 1,065 referenced gradient artifacts.

All checks passed. Full content rehashing took 82.84 seconds with no mismatch. The failure
is numerical and contractual, not an incomplete run or corrupted artifact.

## Numeric Precision

The record-level tail was:

| Metric | Frozen gate | P50 | P95 | P99 | Worst | Violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Loss identity absolute error | <= 1e-6 | 2.78e-17 | 5.55e-17 | 1.11e-16 | 1.11e-16 | 0/300 |
| Token recomposition relative error | <= 0.022 | 0.015908 | 0.019218 | 0.023555 | 0.025139 | 5/300 |
| Token recomposition cosine | >= 0.99975 | 0.999875 | 0.999913 | 0.999942 | 0.999685 minimum | 5/300 |
| GP score absolute delta | <= 0.0023 | 0.000469 | 0.001663 | 0.002107 | 0.002974 | 3/300 |

The relative-error and cosine violations are the same five realizations. One of those
also violates the GP score gate; two additional realizations violate only the GP score
gate. The union is seven realizations (2.33%) across six states.

Task-type concentration was not uniform:

| Task type | Realizations | Any numeric-tail violation |
| --- | ---: | ---: |
| Comparison | 75 | 0 |
| Derived growth comparison | 90 | 5 |
| Registered ratio | 45 | 1 |
| Temporal absolute change | 27 | 1 |
| Temporal average | 27 | 0 |
| Temporal growth | 36 | 0 |

Five of seven violations occurred when the differential supervised-token fraction was at
least 0.20. The tail is therefore not explained by an empty or near-empty differential
region.

At task level, total variation and Jensen-Shannon distance both passed for all 30 tasks:
the worst values were 0.0001544 and 3.45e-8 against limits of 0.00027 and 1e-6. Strict
permutation rank agreement failed for 3/30 tasks, all five-state comparison tasks. Their
minimum adjacent full-score margins were 0.000219, 0.000426, and 0.000661, while maximum
state-mean recomposition deltas were 0.000734, 0.000934, and 0.000697. Thus small score
perturbations changed an interior ordering even though the induced distributions remained
well inside the frozen distance gates.

This observation does not retroactively invalidate the rank gate. Under the immutable
contract, any one of these failures is sufficient to block authorization.

## Sampling Stability

Sampling stability passed independently of numeric precision. Key aggregate diagnostics
were:

| Metric | Observed | Gate |
| --- | ---: | ---: |
| Mean within-state gradient variance ratio | 0.0593 | <= 1.0 |
| Mean gradient effective sample size | 2.8422 | >= 1.5 |
| Mean pairwise gradient cosine | 0.9221 | >= 0.25 |
| Mean split-half gradient cosine | 0.9394 | >= 0.25 |
| Mean sign agreement | 0.9223 | >= 0.55 |
| Mean update-vector cosine | 0.8524 | >= 0.25 |
| Mean state differential-gradient ratio | 0.4060 | >= 0.01 |
| Minimum differential-gradient fraction | 0.2636 | >= 0.05 |

This supports the narrower conclusion that three independent realizations per state are
adequate for the current sampling-stability criteria. It does not override the failed
finite-precision contract.

## Contribution Signal

Estimation-to-validation contribution agreement was positive and statistically distinct
from the permutation null:

| Metric | Estimate | 95% cluster bootstrap interval | Permutation p-value |
| --- | ---: | ---: | ---: |
| Macro task Spearman | 0.6467 | [0.4733, 0.7900] | 9.999e-5 |
| Macro pairwise concordance | 0.7833 | [0.6944, 0.8611] | 9.999e-5 |

Winner agreement was 0.7667. Heterogeneity remains material: derived growth comparison
had mean Spearman 0.45 and winner agreement 0.60 over ten tasks; temporal absolute change
had 0.333 and 0.333 over only three tasks. Comparison and temporal growth were stronger,
with mean Spearman 0.88 and 0.875 and winner agreement 1.0. These slices require larger,
balanced task populations before making task-family claims.

## Fail-Closed Outcome

The aggregate blockers are:

1. `gradient_numeric_precision_failed`
2. `post_global_update_gp_c_not_run`
3. `independent_local_distribution_intervention_not_run`

The latter two are intentional consequences of the first. This plan must not be used to
authorize VTDO updates or downstream training comparisons.

## Next Experiment

The next run must be an independently frozen calibration experiment, not a threshold
adjustment on these 300 observations.

1. Preserve this population as a production-validation holdout.
2. Build a new, task-family-balanced calibration population with disjoint task IDs,
   realization seeds, and evaluation records.
3. Pre-register both raw numerical tolerances and a margin-aware ordering rule. The latter
   should require order preservation only for score pairs whose separation exceeds an
   independently calibrated numerical uncertainty envelope, while retaining hard TV and
   Jensen-Shannon gates.
4. Freeze a new numeric contract before evaluating another production candidate.
5. Re-run GP-C and the independent distribution intervention only if every new immutable
   gate passes.

This keeps the current negative result scientifically useful: v14 demonstrates that the
real-agent Gradient Projection signal is stable enough to measure, but the selected
finite-precision authorization contract is not yet validated for production use.
