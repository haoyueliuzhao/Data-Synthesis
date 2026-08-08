# Finance v22 Development Exact-Target And Power Report

Status date: 2026-08-08

Final status: `development_design_recommendation_ready`

## Scope

This experiment is the Development-only successor to the negative v20 finite-target study and the
operator-cancelled v21 run. It asks whether the frozen one-step beneficiary update admits a precise,
independent first-order target on a broader real Finance population, and which sampling layer
dominates target uncertainty.

It does **not** inspect Validation or Authorization data, evaluate GP-C, authorize Contribution,
update a VTDO distribution, or support Student/downstream claims. Production Contribution remains
zero.

## Immutable Identity

The measurement contract was issued before any state or Objective gradient was computed.

| Item | Identity |
| --- | --- |
| Measurement source commit | `3aa1b0c39d040f79f11bba6166573ec82d729377` |
| Source tree | `b61605018f35ed9550aa02d6c89e164bbe7252c8` |
| Contract hash | `finance_development_exact_target_contract:ce3ecc70fbc4d48efcd0480f931648208511cb147c696b7ed4a7449778ad1693` |
| Base-model manifest | `base_model_content_manifest:4f4c5ef32b56dd571576aff219ae78ab1cd6a1895b6c77202b930067a3c70f6a` |
| Beneficiary adapter SHA-256 | `76fde982cd9252e2708435c174eef20ffa372a0673679b983b0e4b2a55b7132a` |
| Numeric profile | `fp32_activation_strict` |
| State aggregate hash | `finance_development_state_gradient_aggregate:4a90f5b6d23db971ab3b85d5617690134c004f869f1433498d1805b3193ce1d0` |
| Target report hash | `finance_development_exact_target_report:4355f08a108d54ba1533ba8ab940f294a82f9099f0f5d993357c1224f3dc4a04` |
| Design-analysis hash | `finance_development_target_design_analysis:e53d1c904d940a3fd3b3a8114dadbc3526acc68e974c927b86b4ecdbc95261fe` |

The original target report and its 4,000 observations remain unchanged. The v22.1 design analysis
is a separately hashed post-measurement correction to inference and study sizing.

## Population And Measurement

| Component | Support |
| --- | ---: |
| Independent target tasks | 30 |
| Task families | 6 |
| Accepted quotient states | 100 |
| State-conditioned realizations | 500 |
| Realizations per state | 5 |
| Development Objective records | 64 |
| Objective micro-splits | 8 x 8 records |
| Exact crossed observations | 4,000 |
| Outcome-blind primary coordinates | 30 |

The exact target is evaluated under one shared global update:

```text
g(pi) = sum_x mu(x) sum_z pi(z|x) mean_r g(x,z,r)
theta' = theta - AdamW_cold_start(g(pi))

Y(x,z,m,r) = mu(x) < J_AdamW(g)^T g_objective(m),
                         g(x,z,r) - E_pi[g(x,.,r)] >
```

The task marginal is uniform and fixed. Realizations are equally weighted within a state, Objective
records are equally weighted within a micro-split, and all Objective gradients are evaluated at the
same post-global-update checkpoint. The target uses neither finite radius nor Hadamard recovery and
does not use GP-C as its own target.

## Execution

Two state workers ran concurrently on GPU groups `(0,2,3)` and `(4,5,6)`, deliberately avoiding an
unrelated process on GPU 1. Each worker completed 250/250 gradient jobs and passed its immutable
worker contract.

| Stage | Partition 0 | Partition 1 |
| --- | ---: | ---: |
| State-gradient runtime | 13,975.35 s | 14,187.92 s |
| Objective-gradient runtime | 1,997.58 s | 1,933.31 s |
| State jobs | 250 | 250 |
| Objective micro-splits | 4 | 4 |

The complete exact-target artifact occupies approximately 49 GiB. All 500 state-gradient shards,
eight Objective-gradient shards, task/state means, the shared global gradient, and the post-update
checkpoint are content hashed.

The shared gradient norm was `0.09857076`, so the frozen maximum-norm gate did not clip it
(`clip_scale=1.0`). The one-step update norm was `0.87718037`. Both Objective workers independently
produced the same post-update adapter hash.

All project GPU workers exited normally after aggregation. A separate root-owned cryptocurrency-
style process appeared afterward and occupied six GPUs; `/usr/bin/nvidia-smi` was also observed with
an invalid mixed-case ELF interpreter path. This post-run server event is not part of the experiment
and did not alter the already content-hashed artifacts. It must be reviewed before another GPU run.

## Numerical And Algebraic Integrity

| Check | Result |
| --- | ---: |
| FP32/FP64 maximum target delta | `1.0551e-11` |
| Maximum simplex-centering error | `1.1699e-11` |
| State-gradient worker status | 2/2 passed |
| Objective-gradient worker status | 2/2 passed |
| Objective post-update identity agreement | 100% |

The exact target therefore removes the finite-radius and block-reconstruction ambiguity that
blocked v20. This establishes execution precision for this one-step surrogate, not validity of a
Contribution estimator.

## Dual-Axis Inference

The frozen v22 report originally emitted one exclusive `resolution` label. Post-measurement audit
found that statistical nonzero status and practical equivalence must be reported as separate axes:

```text
statistically_nonzero := 95% CI excludes zero
practically_equivalent := 95% CI is contained in [-MPE, +MPE]
meaningful_beyond_MPE := 95% CI lies completely beyond one MPE
```

A coordinate may therefore be statistically nonzero and practically equivalent at the same time.

| Coordinate set | Statistically nonzero | Practically equivalent | Meaningful beyond MPE |
| --- | ---: | ---: | ---: |
| 30 preregistered primary coordinates | 26 | 30 | 0 |
| All 100 state coordinates | 83 | 100 | 0 |

For the 30 primary coordinates, absolute target magnitude relative to the state-specific MPE was:

| Statistic | `abs(target) / MPE` |
| --- | ---: |
| Minimum | `0.0000783` |
| Median | `0.0011811` |
| Mean | `0.0043577` |
| P75 | `0.0062927` |
| Maximum | `0.0244572` |

The median CI half-width was `0.0015726 x MPE`; the maximum was `0.0063036 x MPE`. Thus the
Development target is not merely underpowered around a one-MPE effect. Under the exact frozen
one-step surrogate, every observed state effect is precisely inside the practical-equivalence
region. This is a Development result and must be tested on fresh Validation tasks before it can be
treated as population evidence.

## Variance Decomposition

The nested measurement variance is overwhelmingly driven by Objective micro-split variation:

| Component | Raw mean variance | Share of nested measurement variance |
| --- | ---: | ---: |
| Objective micro-split | `7.9272e-10` | `99.9443%` |
| Realization | `4.0840e-15` | `0.0005%` |
| Objective-realization interaction | `4.3785e-13` | `0.0552%` |

Task-within-family variance was `6.6310e-10`, family-between variance was `1.9067e-10`, and
state-within-task variance was `2.2739e-9`. Increasing realization count beyond five has negligible
expected benefit under the current generator. Future measurement precision should be purchased
primarily with broader, disjoint Objective support.

## Power Interpretation And Correction

The original aggregate reported power `1.0` at 30 tasks for a homogeneous one-MPE population mean.
That result is mathematically expected because measured uncertainty is tiny relative to one full
MPE, but it does not determine how many task-specific coordinates are needed for a future
proxy-target agreement study. It is therefore retained only as a diagnostic and is **not** accepted
as a frozen Validation task count.

The v22.1 analysis separately evaluates per-coordinate measurement resolution over Objective and
realization grids. At the current 8-split/5-realization design, mean nonzero-detection probability
is approximately `0.937` for a true `0.005 x MPE` effect and exceeds `0.995` at `0.01 x MPE`.
Equivalence is effectively certain for a true zero effect. Doubling realizations has negligible
effect; doubling Objective micro-splits halves the dominant variance contribution, reducing its
standard-deviation contribution by a factor of `sqrt(2)`.

Cross-task GP-C agreement power cannot be estimated before a proxy-target agreement estimand and
minimum useful agreement are frozen. It must be preregistered before any future GP-C score is
opened.

## Next-Stage Recommendation

The Development analysis recommends, but does not yet instantiate or observe, a fresh Validation
design:

| Component | Recommendation |
| --- | ---: |
| Fresh tasks | 60 |
| Task families | 6 |
| Tasks per family | 10 |
| States per task | 3-5 |
| Realizations per state | 5 |
| Objective micro-splits | 16 |
| Records per micro-split | 8 |
| Total Objective records | 128 |

The 60-task choice keeps the previously preregistered 48-60 range at its balanced upper endpoint;
it is not derived from the invalid homogeneous-mean shortcut. Before the Validation contract is
issued, the project must freeze a separate target-observability and proxy-target agreement power
contract. Validation tasks, Evidence, semantic signatures, and Objective records must be disjoint
from v20, the cancelled v21 run, and v22 Development.

If fresh Validation again places all exact target intervals inside ±MPE, the supported conclusion
is that state-specific exact-target contrasts are practically negligible for this one-step
surrogate and current state space. It would still not establish that theoretical Contribution is
zero. GP-C should remain unevaluated because there is no practically meaningful target to rank. If
meaningful target coordinates exist, only then may an independently preregistered GP-C comparison
begin.

## Scientific Boundary

The supported result is:

> The exact one-step Development surrogate is numerically precise, and all 100 observed state
> coordinates are practically equivalent under the update-derived two-percentage-point MPE.
> Objective-support variation dominates the remaining measurement uncertainty.

The result does not establish that theoretical Contribution is zero, does not validate or falsify
GP-C, does not open Authorization, and does not justify full `(C+N)` VTDO or Student claims.

## Authoritative Artifacts

- `artifacts/vtdo_experiment/finance_v22_development_exact_target_v1_20260808/contract.json`
- `artifacts/vtdo_experiment/finance_v22_development_exact_target_v1_20260808/state_gradient_manifest.json`
- `artifacts/vtdo_experiment/finance_v22_development_exact_target_v1_20260808/target_observations.jsonl`
- `artifacts/vtdo_experiment/finance_v22_development_exact_target_v1_20260808/report.json`
- `artifacts/vtdo_experiment/finance_v22_development_exact_target_v1_20260808/design_analysis_v22_1.json`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_development_target.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_development_design_analysis.py`

## Verification

- focused target/design tests: 10 passed;
- full Ruff check: passed;
- changed-file Ruff formatting: passed;
- Mypy: 249 source files passed;
- full Pytest: 446 passed in 132.65 seconds;
- Core generalization audit: 130 files, zero violations;
- tracked production-key pattern scan: zero `sk-...` hits; the broader environment-assignment
  scan finds one explicit `test-secret` fixture used by the permissions tests;
- independent v22.1 analysis replay: byte-identical SHA-256
  `a19bcc3030268efc8656a030b21257f0b30753b65e64a97345545ab34f81fa2f`.
