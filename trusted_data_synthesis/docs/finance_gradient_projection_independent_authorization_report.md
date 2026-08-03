# Finance Gradient Projection Independent Authorization

## Decision

The preregistered production candidate did not pass the independent internal gate.

```text
GP-C primary internal authorization gate: failed
Authorization objective accessed:           no
ContributionApproximationAuthorization:      not issued
Production credential:                       not issued
Real Finance C+N rounds:                     remain blocked
```

This is a valid fail-closed result, not an incomplete run. The experiment implemented the
production-matched contract requested by the preceding A/B/C audit and stopped before the untouched
Authorization objective because GP-C failed on the Estimation and Validation objectives.

The earlier A/B/C result remains mechanism evidence on its original population. It did not
replicate strongly enough on this strictly fresh population to authorize Contribution-driven VTDO.

## Frozen estimand

The experiment froze one engineering contract before any finite target was evaluated:

```text
optimizer:                 one-step cold-start AdamW
learning rate:             2e-4
betas:                     (0.9, 0.999)
epsilon:                   1e-8
weight decay:              0
maximum gradient norm:     1
optimizer state policy:    reinitialize per state intervention
batch estimand:            E_pi[U_AdamW(g_z)]
mixed-state batches:       disallowed
state sampling:            one state record per optimizer step
required trainer contract: state_homogeneous_cold_start_adamw
```

The distinction between `E_pi[U(g_z)]` and `U(E_pi[g_z])` is part of the immutable plan. This
experiment provides no evidence for optimizer continuation, mixed-state batches, multi-step
training, or a different beneficiary checkpoint.

Estimator roles were preregistered as follows:

| Estimator | Role |
| --- | --- |
| GP-C, AdamW update projection | Primary |
| GP-B, centered gradient dot product | Secondary |
| GP-A, centered cosine | Historical diagnostic only |

No post-hoc estimator substitution is permitted.

## Independent population

The authorization population was rebuilt from the pinned real Finance KG
`kg_20260711_062123_bc4b4394`.

| Population stage | Count |
| --- | ---: |
| Tasks requested | 100 |
| Tasks attempted | 105 |
| Tasks accepted | 100 |
| Tasks rejected for state capacity | 5 |
| Verified trajectories | 468 |
| Mean states per task | 4.68 |
| Tasks with at least three states | 100 |

Independent verification and semantic separation both passed at `1.0`. The accepted pool contains
468 distinct Evidence lineages and Operation Graph identities.

Freshness was replayed against the prior A population at three levels:

| Freshness layer | Result |
| --- | ---: |
| Candidate tasks | 100 |
| Rejected by any overlap rule | 30 |
| Evidence-Version overlap | 30 |
| Task identity overlap | 2 |
| Semantic-signature overlap | 2 |
| Strictly fresh tasks retained | 70 |

The authorization experiment then froze 30 tasks with exactly three states each, for 90 state
directions. Task identity, semantic signature, and Evidence-Version overlap are all disallowed.

## Objective isolation

The beneficiary support was split into mutually exclusive objective partitions:

| Partition | Records | Use |
| --- | ---: | --- |
| Estimation | 4 | Fit the positive robust scale and contribution temperature |
| Validation | 4 | Freeze the internal decision |
| Authorization | 8 | Untouched final authorization objective |

The Estimation and Validation records contain 19,161 supervised tokens with negative log
likelihood `0.077400`. The untouched Authorization records contain 18,742 supervised tokens with
negative log likelihood `0.079116`. They were measured when the support set was frozen, but their
objective gradients and finite intervention target were not opened by this experiment.

The frozen beneficiary identities are:

```text
beneficiary model state:
  beneficiary_model_state:a3bc8640037e389c411bc1ee21e4df9aae9f335c2f7960c6050966ecb849b7a7
beneficiary checkpoint:
  qwen_beneficiary_checkpoint:4cb8b6730b3299ddb31a0b3b08c85443867c8597f9786f8b9fb557488f2c3a4e
base model content manifest:
  base_model_content_manifest:4f4c5ef32b56dd571576aff219ae78ab1cd6a1895b6c77202b930067a3c70f6a
```

## Numerical preflight

Before finite interventions, the implementation replayed the intended AdamW descent vector and
the serialized direction artifacts.

| Check | Result |
| --- | ---: |
| Formula-vs-optimizer cosine | 0.9999999999998 |
| Formula relative error | 6.46e-7 |
| Minimum serialized-vector cosine | 0.9999999996 |
| Median serialized-vector relative error | 2.75e-5 |
| Maximum serialized-vector relative error | 2.87e-5 |
| Serialized direction observations | 128 |

All preflight checks passed. The finite target therefore tests estimator validity rather than an
unverified optimizer or storage approximation.

## Finite target

Each internal split executed a frozen 64-row Sylvester-Hadamard design plus four numeric replay
rows. The design reconstructs 60 zero-sum task contrast coordinates while keeping task marginals,
state support, and update mass fixed.

| Split | Evaluations | Reconstruction relative error | Numeric replay range | Status |
| --- | ---: | ---: | ---: | --- |
| Estimation | 68 | 0.343488 | 0 | passed |
| Validation | 68 | 0.151125 | 0 | passed |

Both values are below the preregistered maximum reconstruction error of `0.5`.

## Calibration and gates

Only Estimation target values fit the scale:

```text
scale = median(abs(target)) / median(abs(proxy))
T_C   = median(abs(estimation target))
```

The frozen `T_C` is `0.0007357071`. The robust scales are `0.0397490` for GP-A, `0.753128`
for GP-B, and `1.025849` for GP-C. Validation and Authorization data cannot tune either quantity.

The distribution gate compares proxy- and finite-target-induced local VTDO updates. For this
authorization control the reference distribution equals the current uniform conditional
distribution. The thresholds were frozen before target execution:

| Metric | Gate |
| --- | ---: |
| Mean total variation | <= 0.10 |
| P95 total variation | <= 0.20 |
| Mean Jensen-Shannon divergence | <= 0.02 |
| P95 Jensen-Shannon divergence | <= 0.05 |
| Update-direction agreement | >= 0.75 |
| Mean normalized target regret | <= 0.25 |
| P95 normalized target regret | <= 0.60 |

## Primary result

### Rank evidence

| Split | Estimator | Spearman [95% CI] | Concordance [95% CI] | Winner agreement | Rank gate |
| --- | --- | ---: | ---: | ---: | --- |
| Estimation | GP-C | 0.150 [-0.100, 0.400] | 0.556 [0.433, 0.667] | 0.467 | failed |
| Validation | GP-C | 0.300 [0.067, 0.550] | 0.656 [0.556, 0.767] | 0.467 | failed |

The Validation confidence bounds are positive, but the preregistered winner-agreement requirement
still fails. The Estimation confidence bounds also cross their null thresholds.

GP-B and GP-A cannot replace GP-C. Both failed the complete internal gate, although their Validation
rank evidence was individually positive.

### Distribution evidence

| Split | Mean TV | P95 TV | Mean JS | Direction agreement | Mean normalized regret | P95 normalized regret | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Estimation | 0.0797 | 0.1425 | 0.00521 | 0.544 | 3.867 | 11.323 | failed |
| Validation | 0.0785 | 0.1469 | 0.00561 | 0.589 | 3.010 | 11.280 | failed |

TV and JS alone look small because the three-state updates are local. They are not sufficient:
GP-C frequently moves individual state probabilities in the wrong direction, and its target
variational regret is several times the gain attainable by the target update. This is why the
authorization contract includes direction and regret rather than relying only on distance.

## Diagnostic follow-ups

### Objective replicate stability

The four objective records were evaluated separately against the finite target. Estimation record
results were identical at the reported resolution: Spearman `0.0833`, concordance `0.5444`, and
winner agreement `0.4000`. Validation records ranged only from Spearman `0.3000` to `0.3333`.

The failure therefore is not explained by one noisy objective record dominating a four-record mean.

### Post-global-update objective gradient

A sealed internal-only diagnostic recomputed objective gradients at the beneficiary parameters after
the global `pi` update, which is the finite intervention's linearization point. It did not access
the Authorization objective.

| Split | GP-C Spearman | GP-C direction agreement | GP-C normalized regret | Distribution gate |
| --- | ---: | ---: | ---: | --- |
| Estimation | 0.167 | 0.611 | 3.813 | failed |
| Validation | 0.233 | 0.600 | 3.674 | failed |

Moving the objective-gradient evaluation point did not recover the estimator. The result rules out
a simple pre-update versus post-update linearization-point explanation.

## Authorization state

The following files intentionally do not exist:

```text
authorization_proxy.json
targets/authorization.json
authorization.json
authorization_credential.json
```

The staged runner rejects `build-authorization-gradient` until the internal calibration status is
`passed`. The Authorization proxy must freeze before the final target can be opened, and the
credential can only be emitted after the preregistered GP-C rank and distribution gates both pass.

The correct production state is:

```text
Contribution = 0
Novelty and validity remain available under their independent contracts
C+N Finance VTDO rounds are not permitted
```

## Interpretation

This result narrows the earlier claim:

1. Gradient Projection can correlate with a matched cold-start AdamW target on one diagnostic
   population.
2. That evidence is not yet robust across a strictly fresh task population and disjoint objective
   support.
3. GP-C currently fails both state-ranking reliability and distribution-update fidelity.
4. No evidence supports GP-C superiority over GP-B, optimizer continuation, mixed-state batching,
   multi-step training gain, or production C+N use.

The negative authorization result must be reported alongside the earlier positive A/B/C result.
Reporting only the earlier point estimates would overstate the empirical support for Scheme 3.

## Next experiment

The next preregistered version must remain separate from this failed run and cannot tune on the
sealed Authorization set.

1. Repeat the full experiment with a new population seed to estimate between-pool stability.
2. Freeze broader Estimation and Validation objective support before any finite intervention. The
   current per-record diagnostic tests objective-domain coverage, not repair of a noisy mean.
3. Compare finite effects with first-order GP-C predictions at multiple preregistered radii.
4. Keep GP-C as Primary only if the trainer remains exactly
   `state_homogeneous_cold_start_adamw`; otherwise define a new estimator contract.
5. Open a new Authorization objective only after all new internal gates pass.

No threshold should be relaxed based on the current result. Any change to the normalized-regret gate
requires a separate preregistered methods experiment.

## Immutable artifacts

```text
population:
  artifacts/vtdo_experiment/finance_phase18_authorization_pool_b_v1
evaluation support:
  artifacts/vtdo_experiment/finance_phase18_authorization_support_v1
state gradients:
  artifacts/vtdo_experiment/finance_phase18_gradient_projection_30task_v1
authorization experiment:
  artifacts/vtdo_experiment/finance_phase18_contribution_authorization_v1
```

Key identities:

```text
support plan:
  finance_contribution_evaluation_support_plan:0b1d1d52c259386bcafb51a2b7112db8f6c91db32e79da88aebfd3506ffd3253
gradient plan:
  finance_contribution_gradient_plan:6a375966dda36d9c787ff85a588f9f1aaceb48c9ea77b80487b58223a5f75c2c
gradient report:
  finance_contribution_gradient_report:a4c710ca0bd1b1b32427c8d2515ca56fd0dc0768e8fc86b474a120051da29438
authorization plan:
  finance_contribution_authorization_plan:7f722de1ce624d12ec71bbe3807315ed93e8cbec13f8dd361f3e4069c94b65c7
preflight:
  finance_contribution_authorization_preflight:2fe6bf49cf022c09ae02dd046368ba6dc4706a44b14f2d87f27656ce865712d8
calibration:
  finance_contribution_authorization_calibration:704700fef2aee958f1ecaef5bf34688bac7bc069e343e1ffb3e7e927fc09286e
post-update diagnostic:
  finance_post_update_objective_diagnostic:d2462479bb9486399045b9d1e43df71a1e2b18333b364ef7c09e246f15ee6e2a
```

## Verification

```text
Ruff:                       passed
Mypy:                       220 source files passed
Pytest:                     251 passed
git diff --check:           passed
Generalization Contract:    129 files, zero Core domain violations
```

The staged Authorization transition was also exercised directly after the failed calibration. It
exited with `authorization objective remains sealed before calibration passes` and created none of
the proxy, target, authorization, or credential artifacts.

The state-gradient workers used eight GPUs and processed 90 states. The largest recorded state
gradient worker allocation was about 71.4 GB. Estimation and Validation finite-target runs each used
eight workers; their maximum recorded allocations were about 48.6 GB and 50.4 GB respectively. The
post-update diagnostic used a two-GPU sharded model and left unrelated GPU workloads untouched.
