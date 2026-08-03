# Finance VTDO Phase 1.1 Population Experiment Report

> Historical experiment note: the Contribution conclusions in Sections 6 and 7 use
> the earlier single-horizon protocol. They are superseded by
> `finance_contribution_approximation_horizon_validation_report.md`, which uses
> seed-disjoint uncertainty-aware Probe estimates, matched h=1/3/5 Interventions,
> strict identity replay, and independent production authorization. The current
> production decision is to disable the Contribution component.

## 1. Executive conclusion

Phase 1.1 extends the initial single-task mechanism test with real population-level
Explorer observations, reachability-aware updates, multi-task Contribution Probes,
and independent finite Interventions.

The result is scientifically mixed and therefore useful:

- the model-visible Explorer protocol, reachability estimator, anchored update, and
  controlled materializer execute end to end;
- real unconditioned Explorer behavior remains concentrated on one strategy;
- the 3-step Contribution Probe predicts an independent 3-step final-test
  Intervention on the current ten-task sample;
- that ranking fails at 6 and 12 adaptation steps;
- the production Contribution gate remains closed, and Student-training improvement
  is not claimed.

The strongest supported statement is:

> The current Contribution Probe is a local, horizon-specific estimator. It is not a
> proxy for longer adaptation or full Student-training utility.

## 2. Experiment boundary

This follow-up evaluates the mechanism between real model feedback and distribution
refinement. It does not run the final D1-D5 Student matrix or external benchmark.

~~~text
real DeepSeek Explorer
-> empirical reachability
-> reachability-aware energy sensitivity
-> Qwen2.5-7B local Contribution Probe
-> independent final-test Interventions at h=3, 6, 12
-> production gate decision
~~~

All financial tasks derive from the archived public-data finance substrate. No API
data was treated as ground-truth evidence; the API was used only to generate Explorer
trajectories.

## 3. Real Explorer population

The DeepSeek V4 Pro run covered 20 stratified financial tasks and six task types.

| Metric | Result |
| --- | ---: |
| Selected tasks | 20 |
| Unconditioned attempts | 40 |
| Completed and valid trajectories | 43 / 43 |
| Unconditioned valid trajectories | 40 / 40 |
| Catalog hits | 43 |
| Novel valid states | 0 |
| Condition requests audited | 13 |
| Protocol-requestable conditions | 3 |
| Conditioned on-target results | 3 / 3 |
| Conditions blocked before API use | 10 |

The summary artifact originally reports 20 observed state IDs and cross-task entropy
2.983. That is an identity count over task-conditioned state IDs, not behavioral
diversity. The corrected scientific analysis finds:

| Corrected metric | Result |
| --- | ---: |
| Observed unconditioned strategy | compact_direct only |
| compact_direct observations | 40 / 40 |
| Mean within-task state entropy | 0.0 |
| Mean 95% reachability interval width | 0.6576 |

The current evidence therefore shows a strongly concentrated Explorer prior and high
reachability uncertainty. Two attempts per task are sufficient for protocol testing,
not precise support estimation.

### API telemetry

| Metric | Result |
| --- | ---: |
| API calls / HTTP successes | 89 / 89 |
| JSON-contract-success calls | 86 |
| Prompt tokens | 548,352 |
| Completion tokens | 108,306 |
| Total tokens | 656,658 |
| Model | deepseek-v4-pro |
| Fallback calls | 0 |

The provider price fields in the frozen configuration are zero. Token counts are
authoritative; the recorded zero cost is not a billing estimate.

## 4. Reachability-aware energy

The implementation now treats reachable support as an empirical object rather than
assuming every compiled state is equally generatable. Beta posterior estimates and
Wilson intervals are frozen in a StateReachabilityManifest and replayed by the update.

For the original three-state target task, the mass on the observed compact state is:

| Reachability signal | Weight | Observed-state mass | TV from pi0 | Entropy |
| --- | ---: | ---: | ---: | ---: |
| Disabled | 0 | 0.0781 | 0.8552 | 0.9131 |
| Posterior mean | 0.5 | 0.1003 | 0.8330 | 0.9493 |
| Posterior mean | 1 | 0.1279 | 0.8054 | 0.9869 |
| Posterior mean | 2 | 0.2026 | 0.7307 | 1.0567 |
| Posterior mean | 4 | 0.4326 | 0.5007 | 1.0773 |
| Confidence lower | 1 | 0.3314 | 0.6019 | 1.0986 |
| Confidence lower | 2 | 0.7436 | 0.1897 | 0.7470 |

This is sensitivity analysis, not hyperparameter selection. With two observations per
task and wide intervals, no profile is designated production-ready.

A schema defect found by this experiment was also fixed: a zero Wilson lower bound is
a valid raw reachability estimate and is floored only when entering logarithmic energy.

## 5. Controlled materialization

A reachability-aware distribution was materialized through the deterministic,
independently verified path.

| Metric | Result |
| --- | ---: |
| Requested / released | 30 / 30 |
| Quota fill | 100% |
| State hit | 100% |
| Acceptance | 100% |
| Integer target TV | 0 |
| Released compact / broad-direct / broad-full | 4 / 13 / 13 |

This proves quota realization and verifier replay. It does not prove that the real LLM
can generate the same broad-state allocation.

## 6. Multi-task local Probe stability

The Qwen2.5-7B beneficiary was evaluated on ten tasks, three states per task, and four
seeds. Estimation seeds and validation seeds are disjoint.

| Metric | Result |
| --- | ---: |
| Tasks / states / observations | 10 / 30 / 120 |
| Task-wise Spearman | 0.750 |
| 95% cluster bootstrap interval | [0.600, 0.900] |
| Pairwise concordance | 0.833 |
| 95% cluster bootstrap interval | [0.733, 0.933] |

This validates seed stability under the same 3-step local protocol. It does not by
itself validate the estimator against a different evaluation distribution or horizon.
The planned population gate is 30 tasks, leaving a gap of 20.

## 7. Independent horizon validation

Independent Intervention seeds evaluate the same 30 task-state cells on one untouched
final-test set. Only the adaptation horizon changes.

| Horizon | Task Spearman vs Probe | 95% CI | Pairwise concordance | Winner agreement | Permutation p |
| ---: | ---: | --- | ---: | ---: | ---: |
| 3 | 0.650 | [0.350, 0.900] | 0.800 | 0.700 | 0.0023 |
| 6 | -0.100 | [-0.550, 0.350] | 0.467 | 0.300 | 0.7079 |
| 12 | -0.100 | [-0.550, 0.350] | 0.433 | 0.300 | 0.7128 |

The held-out internal 3-step Probe is also aligned with the independent final-test
3-step Intervention: Spearman 0.700, pairwise concordance 0.833, and winner agreement
0.900. This makes pure evaluation-distribution shift an unlikely primary explanation.

The cross-horizon comparison is more diagnostic:

| Comparison | Spearman | Pairwise concordance | Winner agreement | Rank-flip rate |
| --- | ---: | ---: | ---: | ---: |
| 3 vs 6 | -0.100 | 0.467 | 0.300 | 0.533 |
| 6 vs 12 | 0.200 | 0.567 | 0.700 | 0.433 |
| 3 vs 12 | 0.050 | 0.500 | 0.300 | 0.500 |

The first observed unsupported horizon is 6. The maximum observed supported horizon is
3. The data therefore falsify the assumption that one local Probe ranking can be
reused unchanged for longer adaptation.

## 8. Engineering changes caused by the experiment

1. State-conditioning constraints are now model-visible and part of prompt lineage.
2. Host-controlled dimensions are audited before API use and fail closed.
3. Reachability probability, signal, manifest, and energy replay are typed artifacts.
4. Intervention v2 freezes horizon, evaluation role, final-test identity, learning
   rate, beneficiary checkpoint, and an estimand hash.
5. A standalone horizon analyzer reports cross-horizon rank flips, winner agreement,
   bootstrap intervals, permutation tests, and the first unsupported horizon.
6. Contribution-driven production update remains disabled unless all observed target
   horizons are supported and at least 30 tasks are available.

## 9. Resource use

The three independent final-test Intervention matrices each contain 60 jobs:

| Horizon | Jobs | GPUs | Peak allocated memory per worker |
| ---: | ---: | --- | ---: |
| 3 | 60 | A100 80GB, IDs 3-6 | 69.7-70.1 GB |
| 6 | 60 | A100 80GB, IDs 3-6 | 69.7-70.1 GB |
| 12 | 60 | A100 80GB, IDs 3-6 | 69.7-70.1 GB |

No additional LLM API calls were made for the horizon experiments.

## 10. Decision matrix

| Claim or gate | Status | Reason |
| --- | --- | --- |
| Model-visible state conditioning works | Passed | 3/3 requestable conditions on target |
| Real Explorer covers multiple strategies naturally | Not passed | 40/40 compact_direct |
| Reachability-aware update is executable | Passed | Typed replay and sensitivity complete |
| Reachability is precisely estimated | Not passed | Mean interval width 0.6576 |
| Local 3-step Contribution is seed-stable | Passed on pilot | Ten tasks, four seeds |
| Local 3-step Contribution transfers to final-test h=3 | Passed on pilot | Significant rank agreement |
| Contribution transfers to h=6 or h=12 | Rejected | Non-significant, near-random ordering |
| Production Contribution update | Blocked | Horizon mismatch and task count below 30 |
| Student training improvement | Not tested | Contribution target is not yet validated for training horizon |

## 11. Reproducible artifacts

~~~text
artifacts/vtdo_experiment/finance_phase11_reachability_20task_v1/
  summary.json
  scientific_analysis.json
  reachability_manifests.jsonl
  reachability_aware_update.json
  exploration_records.jsonl

artifacts/vtdo_experiment/finance_phase11_reachability_materialization_v1/
  summary.json
  materialization_report.json
  materialized_artifacts.jsonl

artifacts/vtdo_experiment/finance_phase11_contribution_population_v1/
  plan.json
  report.json
  workers/*.jsonl

artifacts/vtdo_experiment/finance_phase11_contribution_intervention_step3_v1/
artifacts/vtdo_experiment/finance_phase11_contribution_intervention_step6_v2/
artifacts/vtdo_experiment/finance_phase11_contribution_intervention_v1/

artifacts/vtdo_experiment/finance_phase11_contribution_horizon_v1/
  report.json
~~~

## 12. Next experimental gate

The next expensive experiment should not simply repeat the current matrix at larger
scale. It should first align the estimand with the intended training intervention:

1. freeze a larger, task-stratified internal-validation and untouched final-test suite;
2. define whether VTDO optimizes a 3-step local functional, a multi-horizon robust
   functional, or eventual Student utility;
3. expand the selected estimand to at least 30 independent tasks and three states;
4. only if that validation passes, run a 20-100 task real VTDO round;
5. run the D1-D5 Student matrix and external benchmarks last.

This ordering preserves the distinction between an executable refinement mechanism and
a demonstrated downstream training benefit.
