# Finance Gradient Projection v12 Audit Closure Report

Date: 2026-08-03  
Repository baseline: `88e10df12ed26e2d61cc3131dcf742a572013162` plus the reviewed
working-tree revision  
Active identities: `vtdo.v12`, `aevtdr.v7`,
`finance_contribution_authorization.v4`

## 1. Decision

The code-level findings in the Gradient Projection audit are closed under the new protocol.
The active path is now:

```text
fresh verified state realizations
-> state/objective gradients with token-region decomposition
-> local cold-start AdamW update map
-> post-global objective gradient
-> blockwise multi-radius finite target
-> Jackknife GP-C proxy
-> typed independent authorization
-> Core Contribution manifests
-> exact task-round VTDO update
```

This is an engineering-readiness result, not an empirical authorization result. No fresh v12 GPU
authorization has been completed. Historical GP-A/B/C and independent-authorization artifacts do
not satisfy the new schema and cannot authorize a real round.

## 2. Issue Closure Matrix

| Audit issue | Resolution | Main implementation |
| --- | --- | --- |
| GP-C authorization was disconnected from Core and Real Feedback | Added one typed Core authorization, Core manifest materialization, exact manifest/authorization replay, and Real Feedback consumption | `core/vtdo/schema.py:584`, `core/vtdo/approximation.py:212`, `phase1_contribution_materializer_v2.py:43`, `real_feedback.py:586` |
| Local diagnostic optimizer was being confused with full Student training | The contract is machine-limited to one state-homogeneous cold-start AdamW step, no inherited state, no mixed-state batch, no accumulation, no weight decay, and a post-global objective point | `core/vtdo/schema.py:448` |
| Authorization identity and claim scope were caller-controlled strings | Authorization version, estimator ID, and claim boundary are immutable Core literals; factory callers can no longer override them | `core/vtdo/schema.py:15`, `core/vtdo/approximation.py:212` |
| Three-state uniform support did not match real VTDO | Production requires the exact frozen task-round distribution, complete positive nonuniform 3-5-state support, distribution ID, round index, and probability hash | `core/vtdo/schema.py:584`, `phase1_contribution_gradient.py:930` |
| Objective gradients used only four `compact_direct` records | Production support is 16 estimation, 16 validation, and 16 sealed authorization records after 4/8/16/32 support scaling; at least three verified trajectory strategies are used | `phase1_contribution_support.py:41`, `phase1_support_scaling.py` |
| One deterministic trajectory represented each state | Production requires 3-5 fresh, independently verified, on-target, decision-trace-distinct realizations per state | `vtdo_experiment/schema.py:739`, `phase1_contribution_gradient.py:533` |
| State uncertainty was not propagated | State means are paired with leave-one-realization-out Jackknife pseudovalues; realization IDs and sample deviations are independently replayed before materialization | `phase1_gp_c_proxy.py:465`, `phase1_contribution_materializer_v2.py:43` |
| Shortest-trajectory-first task selection biased the population | Replaced by salted round-robin sampling over task type, length bucket, evidence count, program depth, and state family | `phase1_contribution_gradient.py:207`, `phase1_contribution_gradient.py:222` |
| Global 60-coordinate, radius-0.4 target was insufficiently local | Uses a complete zero-sum basis, salted blocks of 5-10 coordinates, multiple Hadamard designs, `h/h2/h4` central differences, Richardson extrapolation, reconstruction, radius-stability, and null-SNR gates | `phase1_finite_target.py:214`, `phase1_finite_target.py:338`, `phase1_finite_target.py:496` |
| GP-C used the pre-update objective gradient | The objective gradient is evaluated after the frozen global local-update vector and is bound to the resulting Adapter hash | `phase1_gp_c_proxy.py:465`, `phase1_gp_c_proxy.py:806` |
| State and objective gradient modes were ambiguous | State gradients use train mode; objective gradients use eval mode with autograd; both modes are part of the optimizer/gradient identity | `phase1_contribution_gradient.py:305`, `core/vtdo/schema.py:455` |
| Cold-start AdamW sign saturation was unmeasured | Reports saturation, gradient sign agreement, pairwise gradient/update cosine, within-state variance, ESS, and split-half stability; sign agreement is a hard gate | `phase1_contribution_gradient.py:1493`, `phase1_contribution_gradient.py:2180` |
| Shared JSON/answer tokens could dominate state differences | Every task freezes an aligned common-token and state-differential-token partition; full/common/differential gradients must recompose, and differential token/gradient mass must pass floors | `phase1_contribution_gradient.py:667`, `phase1_contribution_gradient.py:1870` |
| One global calibration scale hid task heterogeneity | Estimation alone fits the scale; validation and authorization consume it unchanged. Reports include per-task diagnostic scales, residuals, and task-type fidelity | `phase1_gp_c_proxy.py:592`, `phase1_gp_c_proxy.py:635` |
| Normalized regret could explode on a near-zero denominator | Attainable gain is no longer clamped. Low-gain tasks have no normalized regret, remain in absolute-regret reporting, and at least 80% of tasks must be normalizable | `core/vtdo/schema.py:499`, `phase1_authorization_v2.py:278` |
| Historical authorization could still appear production-capable | Legacy aggregate and v1 authorization entry points raise; package-level compatibility exports were removed and active authorization/materialization modules run directly | `phase1_mvp.py:746`, `phase1_contribution_authorization.py:1945`, `vtdo_experiment/__init__.py` |

## 3. Fail-Closed Evidence Chain

The typed authorization replays all of the following before it can exist:

```text
beneficiary model and checkpoint
exact task population and task-round distributions
complete 3-5-state support
3-5 realization identities per task-state
task sampling contract
token-region manifest and token audit
objective record IDs, hashes, counts, and split disjointness
support-scaling decision
local optimizer update artifact
finite-target plans, directions, observations, and reports
post-global objective-gradient artifacts
Jackknife realization lineage and sample deviations
rank gates for estimation, validation, and authorization
distribution gates for estimation, validation, and authorization
```

The independent authorization partition cannot select the estimator, objective support, scale,
radius, threshold, or optimizer. A changed record, realization, distribution ID, round, token
partition, gradient file, finite target, or proxy report changes identity or is rejected directly.

## 4. Claim Boundary

The active authorization can support only this claim:

> GP-C is authorized for one local, state-homogeneous, cold-start AdamW VTDO distribution update
> at the frozen beneficiary checkpoint and frozen task-round population.

It cannot support claims about:

```text
full Student training
optimizer continuation
mixed-state batches
gradient accumulation
warmup or scheduler dynamics
multi-step hypergradients
another checkpoint, population, round, or state support
```

Without a matching independent authorization, a Gradient Projection manifest is rejected. Real
experiments must use the separately defined novelty-only/zero-Contribution condition; diagnostic
Probe or finite-target values cannot silently enter the energy.

## 5. Verification Results

Final local verification on 2026-08-03:

```text
Focused authorization regressions: 28 passed
Complete project suite:            289 passed in 115.56s
Ruff:                              passed
Mypy:                              229 source files passed
git diff --check:                  passed
```

Mutation coverage includes changed distributions and rounds, early authorization access, objective
partition drift, realization reuse, changed realization IDs, changed Jackknife deviations, token
region drift, failed finite targets, reversed updates, legacy authorization versions, legacy
estimator IDs, and an expanded full-Student claim.

The complete suite also retains the cross-domain Core boundary and Legal/Science contract tests;
the Finance revision did not add a Finance import or domain branch to Core.

## 6. Remaining Empirical Work

Only the empirical question remains open. The next run must create all v12 artifacts from scratch:

1. Run 4/8/16/32 objective-support scaling on development data.
2. Use fully disjoint development-A and sealed-authorization-B task populations with 3-5
   realizations per state.
3. Freeze mutually disjoint estimation, validation, and authorization objective supports; confirm
   realization stability and common/differential token-gradient gates.
4. Run multi-radius blockwise finite targets on estimation and validation only.
5. Freeze estimator, scale, thresholds, radius, and optimizer contract.
6. Open one fresh authorization population and sealed authorization objective exactly once.
7. Materialize Core manifests only if every typed rank and distribution gate passes.

If that single fresh authorization fails, the production Finance experiment remains
novelty-anchored with `Contribution=0`. The failure must be reported as a bounded engineering
negative result; it is not evidence that the VTDO theoretical Contribution requires a Hessian or
other higher-order term.

The real-Agent population and execution preflight is recorded in
`docs/finance_v12_real_agent_preflight_report.md`.

## 7. Final Status

```text
Protocol implementation: ready
Legacy production compatibility: intentionally removed
Historical authorization validity under v12: none
Fresh v12 empirical authorization: not yet run
Real GP-C Contribution eligibility: blocked pending fresh authorization
```
