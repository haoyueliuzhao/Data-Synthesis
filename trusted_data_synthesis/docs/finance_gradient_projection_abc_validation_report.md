# Finance Gradient Projection A/B/C Validation

## 1. Decision

The three preregistered Scheme 3 variants were evaluated on the same frozen Finance
population: 30 tasks, three trajectory states per task, and 90 state gradients.

All three formula variants passed the frozen rank gate against the new optimizer-matched
one-step cold-start AdamW target:

| Estimator | Estimation vs target Spearman | Validation vs target Spearman |
| --- | ---: | ---: |
| GP-A: centered cosine | 0.417 [0.183, 0.633] | 0.450 [0.217, 0.667] |
| GP-B: centered dot | 0.483 [0.250, 0.700] | 0.467 [0.233, 0.683] |
| GP-C: AdamW update projection | 0.517 [0.317, 0.700] | 0.517 [0.317, 0.700] |

This validates the Scheme 3 approximation family under the frozen diagnostic optimizer
contract. It does **not** authorize a production Contribution signal. The beneficiary's
original optimizer continuation state was not retained, and the new target intentionally
represents a one-step cold-start AdamW contract rather than an unavailable continuation.
Production Finance VTDO rounds therefore continue to use `Contribution=0`.

The paired task-level intervals do not establish GP-C as significantly better than GP-B.
For validation-vs-target Spearman, `GP-C - GP-B` is `0.050` with a 95% bootstrap interval
of `[-0.083, 0.200]`. GP-C is the best point estimate, not a proven winner.

## 2. Frozen estimators

For state loss gradient `g_z`, objective loss gradient `g_v`, current probabilities
`pi_t(z|x)`, and an optimizer descent map `U`, the tested formulas were:

```text
GP-A raw:  cosine(g_v, g_z)
GP-A:      GP-A raw - E_pi[GP-A raw]

GP-B:      <g_v, g_z - E_pi[g_z]>

u_z:       U(g_z)
GP-C:      <g_v, u_z - E_pi[u_z]>
```

GP-C used the frozen source optimizer constants:

```text
optimizer       AdamW
learning rate   2e-4
betas           (0.9, 0.999)
epsilon         1e-8
weight decay    0
gradient clip   1.0
state policy    independent cold-start one-step update
trainable space LoRA parameters only
```

At the first cold-start AdamW step with zero weight decay, the descent direction is:

```text
u_z = lr * clipped(g_z) / (abs(clipped(g_z)) + epsilon)
```

The code independently replayed this expression against a real PyTorch AdamW step before
the target was evaluated.

## 3. Frozen support and isolation

The experiment reused, without resampling:

- the 30-task, 90-state population;
- state-specific update-set gradients;
- four estimation objective records;
- four disjoint validation objective records;
- the untouched final-test records;
- the 60 zero-sum task contrast coordinates;
- the 64-row Sylvester-Hadamard design plus four deterministic replay rows;
- distribution epsilon `0.4`.

The plan was frozen before the final-test objective was loaded. No learning rate, epsilon,
threshold, state, task, objective record, or design row was selected using final outcomes.

The optimizer target prebound every possible state update. It formed the current expected
update and two zero-sum contrasts per task, then evaluated symmetric finite perturbations:

```text
D_h = [J(theta - (u_bar + epsilon * H_h U))
       - J(theta - (u_bar - epsilon * H_h U))] / (2 * epsilon)
```

All 1,920 task-design probability replays preserved support and mass. The minimum perturbed
probability was `0.0333333`; maximum mass error was `1.11e-16`.

## 4. Numeric preflight

The preflight passed before final-test evaluation:

| Check | Result |
| --- | ---: |
| AdamW formula cosine | 0.9999999999998 |
| AdamW formula relative error | 6.46e-7 |
| Direction observations | 128 |
| Minimum stored-step cosine | 0.9999999995 |
| Maximum stored-step relative error | 3.05e-5 |
| Median nonzero recovery | 0.9945 |
| Preflight status | passed |

The orthogonal target had deterministic replays (`maximum range = 0`) and reconstruction
relative error `0.07448`, below the frozen `0.5` limit.

All 68 worker rows replayed one plan hash, one preflight hash, one baseline Adapter hash,
one baseline loss, and one final-token count. Every direction hash matched the preflight
manifest, and every symmetric pair produced distinct Adapter hashes.

## 5. Main results

### 5.1 Cross-objective stability

| Estimator | Spearman [95% CI] | Pairwise [95% CI] | Winner | Sign | Permutation p |
| --- | ---: | ---: | ---: | ---: | ---: |
| GP-A | 0.950 [0.883, 1.000] | 0.967 [0.922, 1.000] | 1.000 | 0.889 | <0.001 |
| GP-B | 0.983 [0.950, 1.000] | 0.989 [0.967, 1.000] | 1.000 | 0.967 | <0.001 |
| GP-C | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 | 0.878 | <0.001 |

These formula scores use aggregate objective gradients and no uncertainty penalty.

The historical production-candidate GP-A additionally subtracted one sample standard
deviation before centering. Its frozen result was replayed separately:

```text
cross-split Spearman       0.717 [0.517, 0.883]
cross-split pairwise       0.844 [0.744, 0.922]
estimation vs AdamW target 0.333 [0.083, 0.550]
validation vs AdamW target 0.283 [0.033, 0.517]
```

This distinction explains why the formula-level GP-A result is not numerically identical to
the earlier `0.717` report.

### 5.2 Independent AdamW target

| Estimator/split | Spearman [95% CI] | Pairwise [95% CI] | Winner | Sign | Spearman p |
| --- | ---: | ---: | ---: | ---: | ---: |
| GP-A estimation | 0.417 [0.183, 0.633] | 0.678 [0.567, 0.778] | 0.567 | 0.689 | 0.0012 |
| GP-A validation | 0.450 [0.217, 0.667] | 0.689 [0.578, 0.789] | 0.567 | 0.689 | 0.0003 |
| GP-B estimation | 0.483 [0.250, 0.700] | 0.733 [0.622, 0.833] | 0.633 | 0.689 | 0.0002 |
| GP-B validation | 0.467 [0.233, 0.683] | 0.722 [0.622, 0.822] | 0.633 | 0.722 | 0.0004 |
| GP-C estimation | 0.517 [0.317, 0.700] | 0.722 [0.622, 0.811] | 0.633 | 0.700 | <0.0001 |
| GP-C validation | 0.517 [0.317, 0.700] | 0.722 [0.622, 0.811] | 0.633 | 0.733 | <0.0001 |

All six estimator-target comparisons passed the frozen lower-bound, winner, and permutation
requirements.

### 5.3 Paired estimator comparisons

Task-level paired bootstrap intervals show that the point-estimate ordering is uncertain:

| Difference | Estimation Spearman delta [95% CI] | Validation Spearman delta [95% CI] |
| --- | ---: | ---: |
| GP-B minus GP-A | 0.067 [-0.117, 0.267] | 0.017 [-0.183, 0.233] |
| GP-C minus GP-A | 0.100 [0.000, 0.250] | 0.067 [-0.083, 0.233] |
| GP-C minus GP-B | 0.033 [-0.100, 0.183] | 0.050 [-0.083, 0.200] |

The data support the family and the relevance of magnitude/optimizer geometry, but they do
not justify selecting GP-C over GP-B from final-test performance.

### 5.4 Gradient magnitude

State-gradient norm alone had:

```text
AdamW target Spearman  0.400 [0.167, 0.633]
old SGD target Spearman -0.100 [-0.350, 0.167]
```

Magnitude contains signal for the optimizer-matched target, but it is not a sufficient
Contribution estimator by itself.

## 6. Cross-optimizer control

Against the older cached-gradient SGD target at its numerically identifiable `5e-4` scale,
none of GP-A, GP-B, or AdamW GP-C passed the target rank gate. Estimation Spearman values
were `0.067`, `-0.017`, and `0.017`, respectively.

The source SGD learning rate was `5e-5`, but float32 parameter-step preflight failed at that
scale (`median relative error = 0.608`, `median nonzero recovery = 0.236`). It was therefore
not evaluated on the final target. The report records this as
`not_evaluated_due_numeric_fidelity_failure`, not as a zero correlation.

Under plain SGD, GP-C is exactly a positive scalar rescaling of GP-B. All 180 state/split
comparisons had zero scaling residual and identical rankings. Consequently, an SGD version
of GP-C is not independent evidence for GP-B.

The disagreement between the AdamW-matched and old SGD targets demonstrates optimizer
dependence. It is not evidence that one target is universally correct.

## 7. Scope limits

- GP-C matches a newly frozen one-step cold-start AdamW contract, not retained historical
  continuation state.
- Only four task families are represented: 12 growth comparisons, nine comparisons, five
  temporal-growth tasks, and four registered ratios. Family-level slices are too small for
  separate claims.
- The finite target uses the same optimizer geometry as GP-C by design but independent final
  objective records and measured finite outcomes.
- The experiment validates first-order ranking association, not downstream multi-step training
  utility.
- No estimator was inserted into a real VTDO energy update.

## 8. Execution and immutable artifacts

```text
GP plan hash
finance_gp_abc_plan:981369cb7c537350391379b6898f5630ae1ce94be7eb03cb0ad77acddebb04aa

preflight hash
finance_gp_abc_preflight:4962e93a3d0735ef1c7f40826d43bd444e1cfaee723d64d2644ca91a617fa67a

report hash
finance_gp_abc_report:fcafc5907063b3fb8ac6d0e002951c89ebaebe0a2297f310d71a23a2744db358

artifact directory
artifacts/vtdo_experiment/finance_phase17_gp_abc_30task_v1
```

The target used eight A100 80 GB GPUs. The 68 final evaluations required approximately
`360.6` seconds wall-clock, `2,698.5` aggregate GPU-seconds, and `50.37 GB` peak allocated
memory per worker. Frozen artifacts occupy approximately `9.5 GB`.

## 9. Resulting policy

```text
Scheme 3 family mechanism: supported for the frozen cold-start AdamW diagnostic
GP-C superiority over GP-B: not established
cross-optimizer transfer: not supported
production Contribution authorization: not issued
real Finance VTDO Contribution: 0
```

The next production-oriented test must begin from a checkpoint that retains and freezes the
actual optimizer state, or must preregister cold-start AdamW as the real next-round training
contract. It must then validate multi-step downstream utility on a fresh target without using
this final-test outcome to select estimator, scale, or threshold.
