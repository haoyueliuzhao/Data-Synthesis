# Finance Contribution Approximation Horizon Validation

## 1. Decision

The current finite-step cold-start SGD Probe is not validated as a production
approximation of VTDO Contribution. No tested horizon may influence the anchored
energy update.

The strict replay report is:

~~~text
artifacts/vtdo_experiment/
  finance_phase14_uncertainty_estimand_h1_h3_h5_v2/report.json
~~~

Its immutable identity is:

~~~text
finance_contribution_estimand_analysis:
8b7785153c68e7a0c26a91adade77a268e5e717681896d0b8388426cc802f421
~~~

The report status is `partial`, `validated_production_horizon` is null, and the
required action is `disable_contribution_component`.

## 2. Experimental contract

The experiment follows the frozen engineering approximation rather than changing
the theoretical Contribution definition:

~~~text
task-conditioned current distribution
-> finite-step cold-start SGD Probe
-> multi-seed mean and sample standard deviation
-> mean - lambda * standard deviation
-> centering under the current conditional distribution
-> independent-seed and independent-final-test rank validation
~~~

Horizons 1 and 3 are eligible production candidates in the Core contract. Horizon 5
is diagnostic only and cannot receive a Core optimizer identity or production
authorization.

The completed run is the explicit uniform initial-distribution special case:
`state_probability_policy=uniform_over_selected_states`. The analyzer independently
replayed every task-state probability, task distribution hash, and probability-weighted
centered mean. Their frozen aggregate identity is:

~~~text
contribution_distribution_contract:
6e4f4056f483e86f74c7ec3872b6f2abf8267f7406652d5225a474a47a3c8339
~~~

The Core hashing and centering primitives accept an explicit positive normalized
current distribution. This Population planner intentionally emits only the uniform
special case; any future non-uniform run must freeze a new probability policy in its
plan rather than silently infer one during aggregation.

The validation requires all three rank gates to pass:

1. estimation seeds versus held-out Probe seeds;
2. estimation seeds versus independent final-test Intervention;
3. held-out Probe seeds versus independent final-test Intervention.

For each gate, the lower 95% Spearman bound must exceed zero, the lower 95%
pairwise-concordance bound must exceed 0.5, winner agreement must be at least 0.5,
and both permutation p-values must be below 0.05.

## 3. Real execution

The six runs used Qwen2.5-7B and four A100 80GB devices, GPU IDs 3 through 6.

| Run | Tasks | States | Seeds | Observations |
| --- | ---: | ---: | ---: | ---: |
| Probe h=1 | 10 | 30 | 4 | 120 |
| Probe h=3 | 10 | 30 | 8 | 240 |
| Probe h=5 | 10 | 30 | 4 | 120 |
| Intervention h=1 | 10 | 30 | 4 | 120 |
| Intervention h=3 | 10 | 30 | 4 | 120 |
| Intervention h=5 | 10 | 30 | 4 | 120 |
| Total | - | - | - | 840 |

The maximum observed worker allocation was 70,672,598,528 bytes, approximately
70.67 decimal GB per GPU. All workers completed and the GPUs were released. No LLM
API call was required for this horizon experiment.

## 4. Rank evidence

### Conservative signal on independent final test

| Horizon | Spearman | 95% CI | Concordance | 95% CI | Winner agreement |
| ---: | ---: | --- | ---: | --- | ---: |
| 1 | -0.150 | [-0.500, 0.200] | 0.433 | [0.300, 0.567] | 0.300 |
| 3 | -0.300 | [-0.600, 0.050] | 0.367 | [0.233, 0.500] | 0.100 |
| 5 | 0.100 | [-0.350, 0.550] | 0.533 | [0.333, 0.733] | 0.300 |

None passes even the confidence-interval requirements. The apparent positive h=5
point estimate is statistically compatible with a negative association and is not a
production candidate in any case.

### Cross-seed stability

| Horizon | Spearman | 95% CI | Concordance | 95% CI | Winner agreement |
| ---: | ---: | --- | ---: | --- | ---: |
| 1 | -0.100 | [-0.600, 0.400] | 0.467 | [0.233, 0.700] | 0.400 |
| 3 | 0.350 | [-0.100, 0.800] | 0.700 | [0.500, 0.900] | 0.600 |
| 5 | -0.350 | [-0.700, 0.000] | 0.333 | [0.167, 0.500] | 0.200 |

The h=3 point estimates look better internally, but their confidence bounds do not
pass. More importantly, the h=3 ordering reverses on the independent final test.
This is exactly the overfitting mode that the three-evidence authorization contract
is intended to catch.

### Raw versus uncertainty-penalized signal

The independent-final-test raw Spearman values for h=1, h=3, and h=5 are -0.25,
-0.15, and -0.15. The conservative values are -0.15, -0.30, and 0.10. The penalty
therefore changes individual point estimates but does not yield a robust rank signal.
No value of the penalty coefficient is selected from these final-test results.

## 5. Support limits

The frozen production policy requires at least 30 tasks. This run contains 10 tasks
and 30 task-state cells. Both evaluation sets contain six records and pass the
minimum record-count gate.

Probe h=3 has four estimation and four validation seeds. Probe h=1 and h=5 have only
two seeds in each split. The strict report therefore records h=3 as seed-qualified,
but records no rank-qualified or jointly eligible horizon. This distinction prevents
an under-replicated, higher-ranked horizon from masking a lower-ranked horizon that
does satisfy the seed contract.

The production blockers are independently reported as:

~~~text
validated_horizon_exists
joint_horizon_eligibility
task_population_sufficient
~~~

Final-test and internal-validation record support pass. The 10-task population remains
below the frozen 30-task production minimum.

## 6. Engineering changes

1. A local-Probe manifest now freezes optimizer identity and adaptation horizon.
2. Probe and Intervention estimand IDs are independently recomputed before analysis.
3. Probe final-test and independent Intervention final-test IDs are stored separately,
   while exact record membership must match.
4. A typed production authorization binds the beneficiary model, checkpoint, metric,
   optimizer, horizon, uncertainty policy, evaluation sets, task population, seeds,
   and all three rank-evidence objects.
5. Authorization task membership is frozen, hashed, and checked for every task-level
   Contribution manifest.
6. Real VTDO updates, real-round replay, and the Phase-1 aggregate command fail closed
   without a matching authorization.
7. Synthetic-oracle controls remain executable without a Probe authorization, while
   finite Interventions remain validation-only.
8. Every task now freezes its current state probabilities and distribution hash;
   the analyzer independently replays probability-weighted zero-mean centering.
9. Rank validity, seed replication, and their intersection are separate fail-closed
   gates, so no single partial success can issue a production authorization.

## 7. Scientific boundary and next experiment

This run verifies the real execution path and falsifies production use of the current
signal. It does not show that VTDO Contribution is ineffective in general, nor does it
measure downstream Student-training utility.

This recommendation has now been executed and superseded. The follow-up used 30 tasks,
three verified states per task, disjoint estimation and validation objective gradients,
and independent distribution interventions. It replaced finite-step Probe adaptation
with Scheme 3 Gradient Projection rather than tuning another horizon.

The complete follow-up is recorded in
`docs/finance_gradient_projection_contribution_validation_report.md`. Scheme 3 is
internally stable but fails the independent batch-intervention rank gates, so no
production Contribution authorization exists. Student training must continue with a
zero real Contribution component.
