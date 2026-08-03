# Finance Gradient Projection Contribution Validation

> Historical cached-SGD target report. The later optimizer-matched GP-A/B/C comparison is
> documented in `docs/finance_gradient_projection_abc_validation_report.md`. The two reports use
> different frozen target contracts and must not be merged into one cross-optimizer conclusion.

## 1. Decision

The requested Scheme 3, Gradient Projection Contribution, is implemented and has
completed a 30-task, 90-state real-GPU validation. It is **not authorized** as a
production VTDO Contribution signal.

This decision is fail-closed for two independent reasons:

1. the original one-task-at-a-time distribution intervention was below the numerical
   resolution of the actual float32 LoRA parameter update; and
2. a preregistered, numerically identifiable batch symmetric intervention produced a
   deterministic and approximately linear target, but neither the estimation nor the
   held-out validation Gradient Projection rankings passed the independent rank gate.

The VTDO energy update must therefore keep the empirical Contribution component at
zero. The experiment tests an engineering approximation, not the theoretical
functional derivative, so this result does not falsify the VTDO definition of
Contribution.

## 2. Scheme 3 estimand

For a state training-loss gradient `g_z` and an objective-loss gradient `g_v`, the
implemented score is their normalized alignment:

```text
C_hat_grad(z) = <g_z, g_v> / (||g_z|| ||g_v||)
```

The positive sign is intentional. With `J=-L_v` and one SGD update
`theta'=theta-eta*g_z`, the first-order utility gain is
`eta*<g_z,g_v>`. Four estimation records and four disjoint validation records provide
independent objective-gradient replicates. State scores are uncertainty-penalized and
centered under the frozen conditional state distribution before ranking.

The production-candidate support contains:

| Item | Count |
| --- | ---: |
| Finance tasks | 30 |
| Verified states per task | 3 |
| State gradients | 90 |
| Estimation objective records | 4 |
| Validation objective records | 4 |

The task-adaptive state policy selects exactly three independently verified quotient
states. It permits `compact_verify_frontier` when a task cannot support
`broad_full_lineage`; it does not weaken state verification or duplicate a quotient
state.

## 3. Internal gradient evidence

The frozen Gradient Projection report is:

```text
artifacts/vtdo_experiment/finance_phase15_gradient_projection_30task_v1/report.json
```

Its identity is:

```text
finance_contribution_gradient_report:
179b618034e8094be6a40daf85d584769c01c2028c2da844d611e557297b51b8
```

Estimation-versus-validation evidence is strong:

| Metric | Estimate | 95% CI |
| --- | ---: | --- |
| Macro task Spearman | 0.717 | [0.517, 0.883] |
| Pairwise concordance | 0.844 | [0.744, 0.922] |
| Winner agreement | 0.900 | - |

This establishes cross-split stability of the proxy. It does not establish that the
proxy predicts an independent distribution intervention.

## 4. Single-task distribution intervention

The first independent validation used the exact cached full-distribution gradient:

```text
g' = g + mu(x) * epsilon * (g_z - E_pi[g_z])
```

It ran 30 tasks, 90 states, and four deterministic numeric replays, for 360
observations. Both Gradient Projection splits failed the rank gate. For the estimation
split, macro Spearman was -0.133 and pairwise concordance was 0.444. For the validation
split, they were -0.233 and 0.400.

The report is:

```text
artifacts/vtdo_experiment/
  finance_phase15_distribution_intervention_30task_v1/report.json
```

Its identity is:

```text
finance_distribution_intervention_report:
2386ee9debb7d5b3e0ac62144db3d0ccf80b6d4c407ce85136d2311d35c744d6
```

### Parameter-resolution audit

An exact tensor-level replay then compared the intended real-valued directional step
with the actual float32 parameter difference. Across the 90 states:

| Fidelity metric | Median |
| --- | ---: |
| Parameter-step cosine | 0.244 |
| Relative error | 3.960 |
| Norm ratio | 4.084 |
| Nonzero recovery | 0.0255 |
| Intended-gradient energy recovery | 0.430 |

The intervention is below parameter numeric resolution. Its failed rank gate remains
part of the audit trail, but it is not valid evidence against Scheme 3.

## 5. Batch symmetric intervention

To obtain a numerically identifiable target without observing final-test outcomes, a
second validation froze:

```text
30 tasks x 2 zero-sum contrast coordinates = 60 coordinates
64 x 60 Sylvester-Hadamard design
4 exact numeric replay rows
epsilon = 0.4
```

For every task and design row, both `pi+epsilon*v` and `pi-epsilon*v` remain positive
and sum to one. The minimum state probability is 0.0333. Task marginals, total compute,
state support, model checkpoint, final-test membership, and cached-gradient policy are
fixed.

The learning-rate ladder `[5e-5, 1e-4, 2e-4, 5e-4]` was preregistered. Selection used
only parameter-step fidelity and could not access final-test utility. The original
`5e-5` scale failed numeric fidelity. The smallest passing scale was `5e-4`:

| Metric at selected scale | Value |
| --- | ---: |
| Median parameter-step cosine | 0.979 |
| Minimum cosine | 0.974 |
| Median relative error | 0.208 |
| Maximum relative error | 0.235 |
| Median intended-gradient energy recovery | 0.995 |

Because the selected scale differs from the source training scale, this experiment can
only test the mechanism. It cannot authorize the original production configuration.

The six-GPU run completed 68 central-difference rows, or 136 final-test evaluations.
All four replays were bitwise stable. Hadamard reconstruction relative error was 0.132,
below the frozen 0.50 limit.

The immutable artifacts are:

```text
artifacts/vtdo_experiment/finance_phase16_batch_symmetric_30task_v1/
  plan.json
  preflight.json
  report.json
```

Their identities are:

```text
finance_batch_distribution_intervention_plan:
695067b29b5d6dc0675e50487c33dcfa958491f641b68f18c7de61d809dc83c8

finance_batch_distribution_preflight:
b25337a91d017daef2cec8c60b698bcdc330c4e6cdec2364ffba91fd8adc7d34

finance_batch_distribution_intervention_report:
0a14ac3efed0a2655dde46d7ec4e2995db0f19f31a1757d4968aac38378b4a14
```

### Independent rank result

| Proxy | Spearman | 95% CI | Concordance | 95% CI | Winner |
| --- | ---: | --- | ---: | --- | ---: |
| Estimation conservative | 0.117 | [-0.150, 0.367] | 0.556 | [0.433, 0.667] | 0.333 |
| Validation conservative | 0.117 | [-0.133, 0.350] | 0.556 | [0.456, 0.667] | 0.400 |

Both confidence intervals cross their null thresholds and both permutation tests are
non-significant. Row-level Pearson correlations are 0.128 and 0.074. The result is not
a near miss under the frozen gate.

## 6. Post-hoc mechanism localization

After the independent failure, a diagnostic directly differentiated the untouched
final-test objective at the selected batch baseline. This is deliberately prohibited
from becoming an estimator or promotion gate.

| Metric | Value |
| --- | ---: |
| Coordinate Pearson | -0.082 |
| Hadamard-row Pearson | -0.074 |
| Macro task Spearman | -0.017 |
| Pairwise concordance | 0.511 |
| Winner agreement | 0.300 |

The direct final-test gradient also fails to predict the finite central difference.
The observed failure therefore cannot be repaired merely by replacing the eight proxy
objective records with final-test records. At the numerically identifiable `5e-4`
scale, the finite update is not a reliable first-order target for Gradient Projection,
or the mixed-precision forward objective still dominates the expected first-order
signal.

The diagnostic identity is:

```text
finance_batch_linearization_diagnostic:
37374ae89fc247129d22fcbe0bcea28d0d7278ce9c5c4490dc00f4fe590693e8
```

## 7. Resource and reproducibility audit

| Stage | Hardware | Peak allocation | Runtime |
| --- | --- | ---: | ---: |
| Single-state direct-gradient diagnostic | 1 x A100 80GB | 69.3 GB | 136 s |
| Batch parameter preflight | 1 x A100 80GB | 20.9 GB | 189 s |
| Batch central intervention | 6 x A100 80GB | 50.37 GB/GPU | 434-474 s/worker |
| Batch direct-gradient diagnostic | 1 x A100 80GB | 69.1 GB | 103 s |

The experiment made no LLM API calls. GPUs occupied by unrelated processes were not used. All
experiment workers exited and released their GPU allocations.

## 8. Scientific boundary and next permitted experiment

The evidence supports these statements:

1. Gradient Projection is reproducible across two independent proxy-objective splits.
2. The original single-task finite intervention is numerically unidentifiable.
3. The batch intervention is parameter-identifiable, deterministic, and reconstructible.
4. Gradient Projection does not predict that batch target under the frozen gate.

It does not support a production Contribution signal, an anchored-energy update using
this proxy, or a downstream Student-training claim.

The next valid work is a new preregistered numerical-analysis experiment, not another
horizon or outcome-selected scale sweep. It should first separate mixed-precision
forward quantization from finite-step curvature, for example with paired token-level
float32 loss accumulation and a source-scale grouped perturbation whose parameter and
objective signal-to-resolution ratios are fixed before evaluation. Only after a local
first-order target is independently identifiable should Scheme 3 be tested again. Until
then, VTDO continues with `Contribution=0` for real finance rounds.
