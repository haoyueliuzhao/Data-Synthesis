# Valid Trajectory Distribution Optimization

## Method Status

This document defines the canonical engineering approximation to the frozen VTDO theory. The
implementation lives in `trusted_synthesis.core.vtdo`. It supersedes the earlier approximation
that treated a `SynthesisCell` and a bucketed trajectory attribute profile as the optimization
state.

For a fixed public task condition `x`, VTDO optimizes only the conditional trajectory-state
distribution:

```text
d_t(x, z) = mu(x) * pi_t(z | x)
```

The task marginal `mu(x)` is immutable. `TaskConditionedTrajectoryPolicy` enforces this identity
and rejects partial conditional updates.

Finance remains the main reference implementation. The quotient mapper, validity regions,
distribution estimators, contribution contract, energy update, and Explorer are domain-neutral
and are exercised by both Legal and Science contract cases.

## Frozen Verification Context

Each task freezes:

```text
Omega_x = (E_x, P_x, G_x, Q_x)
```

where `E` is the pinned Evidence corpus and gold bundle, `P` is the executable TaskProgram, `G` is
the Proof Graph, and `Q` is the executable universal plus domain Quality Contract. The deterministic
Reference Workflow is one known-valid realization, not a unique gold reasoning path.

`TrajectoryValidityEvaluator` evaluates a candidate independently through the Candidate Workflow
Verifier and Quality Contract Runtime. Missing checks, runtime failures, invalid evidence,
operation errors, unsupported claims, or citation defects fail closed.

ProofCarryingSampleCompiler emits a first-class JointCompilationArtifact. It carries the complete
TrajectoryVerificationContext plus an OmegaComponentManifest that separately freezes the Task,
Evidence Bundle, public Corpus, Task Program, Proof Graph, Quality Contract, and Oracle execution
specification. The compilation identity also binds the compiler version. Downstream components
consume this artifact rather than reconstructing Omega_x from loosely related files.

## Quotient Trajectory State

The optimized state is not a raw trajectory and not an attribute bucket:

```text
z = phi_x(tau) = [tau]_(~ Omega_x)
```

`map_trajectory_to_state()` constructs a typed dependency graph containing:

- canonical Oracle operation roles and program dependencies;
- evidence identity and evidence-to-operation lineage;
- tool/operator semantics;
- selected operation results and final result semantics;
- verification and answer dependencies.

It then performs dependency-preserving multiset graph canonicalization. Execution indices,
rationale text, generator version, timestamps, and a valid reordering of independent operations do
not create a new state. Changes to evidence identity, program structure, tool semantics, operation
results, or final answer semantics do.

The current canonicalizer is a finite Weisfeiler-Lehman-style graph approximation, not a claim of
solving general graph isomorphism. Callers may provide only frozen, audited program-node and tool
equivalence maps; no equivalence is inferred from natural-language similarity.

`TrajectoryAttributes` remains an observational descriptor `m(tau)` for diagnostics. It is stored
beside a `TrajectoryStateAssignment` but is deliberately excluded from state identity.

`TrajectoryStateCatalog` freezes the finite support used by one task condition: the complete state
objects, `Omega_x` component manifest, the complete
`TrajectoryStateSpaceCompilation`, Mapper schema, canonicalizer version, parent catalog, and
revision reason. Catalog construction rejects public conditions absent from the compiled variation
manifest. Every state must also carry at least one `StateDiscoveryWitness` linking a verified
trajectory assignment to its trajectory ID, content hash, and complete content-addressed validity
report. States cannot be registered from an unverified structural description. An observed state outside that catalog fails closed. Adding,
retiring, reclassifying, or adding discovery evidence for a state creates a new catalog identity
instead of silently changing the meaning of `pi_t`.

## Trajectory State-Space Compilation

Joint Compilation freezes one immutable `Omega_x`. A thin state-space compilation step then maps
domain semantics into `AdmissibleTrajectoryVariation`; it does not rebuild Task, Evidence, Program,
Proof Graph, or Quality Contract for each state. The resulting
`TrajectoryStateSpaceCompilation` embeds the same immutable `JointCompilationArtifact`, freezes
the variation-provider identity and version, and content-addresses the complete variation/condition
manifest. The Core variation contract contains five domain-neutral axes:

```text
Evidence Acquisition
Evidence Support
Execution Realization
Verification Policy
Lineage Policy
```

Finance may interpret these axes using fiscal-period and metric semantics; Legal and Science
compile their own semantics into the same contract. Finance-specific strategy names are never Core
state kinds. Validity is deliberately absent from the condition because one quotient state may have
both valid and invalid realizations; it remains an independently estimated property
`v_t(x, z; Omega_x)`.

State-conditioned generation has a strict Host/model boundary. The Host retains `Omega_x`, the
exact quotient state, gold Evidence IDs, Oracle program and specification, Proof Graph, Quality
Contract, discovery witnesses, and reference trajectories. A model-facing provider receives only a
`PublicStateGenerationRequest`: the public task, frozen public-corpus identity, allowed tools, a
`PublicStateCondition`, budget, and seed. Every request receives a fail-closed leakage audit before
provider invocation. The public projection may be coarser than the exact quotient state, so the Host
always verifies the realized trajectory and remaps it through `phi_x`; off-target outcomes are data,
not silently relabeled successes.

## Push-forward Distribution

Observed executions are mapped before counting. For direct samples the estimator is:

```text
pi_hat_t(z | x) = (n_z + lambda_0 * r(z | x)) / (N + lambda_0)
```

For samples requested under exploration policy `q_t`, the requested-state ratio reweights the
provider transition into the realized quotient state:

```text
pi_hat_t(z | x) =
  (sum_i w_i * 1[phi_x(tau_i) = z] + lambda_0 * r(z | x))
  / (sum_i w_i + lambda_0)
```

`EmpiricalDistributionEstimate` freezes observation IDs, raw counts, weighted exposure mass,
squared weights, effective sample size, the complete coverage prior, and the resulting conditional
distribution. Its validator replays the estimator equation rather than trusting serialized
probabilities. Unknown observed states are rejected until the state catalog is explicitly revised.

## Validity Is Feasibility

For each quotient state, independently verified member trajectories estimate:

```text
v_t(x, z; Omega_x) = Pr[V(tau, Omega_x) = 1 | phi_x(tau) = z]
```

The estimator records attempts, valid executions, component validity, a Wilson interval, the
estimator version, and frozen thresholds. States are partitioned into:

```text
Accepted
Quarantined
Rejected
```

`condition_on_accepted_support()` conditions both `pi_t` and the coverage prior on Accepted states.
Quarantined states remain exploration/audit targets; Rejected states never enter positive training
support and can be removed in the next explicit catalog revision. The update also rejects any
non-Accepted state on positive training support. Validity is never inserted into an energy score and
therefore cannot be compensated by novelty or contribution.

## Model-state-dependent Contribution

The theoretical object is the centered functional directional derivative:

```text
C_t(x, z) =
    < delta J_nu / delta pi(. | x), delta_z - pi_t(. | x) >

E_(z~pi_t)[C_t(x, z)] = 0
```

It measures the first-order effect of moving probability mass from the current trajectory-state
distribution to state `z` for the **beneficiary** model. It is not an Explorer score and it is not
the CCGR capability-gap heuristic.

The engineering approximation is Scheme 3, the Gradient Projection family. For a state update-set
training-loss gradient `g_z` and an objective loss gradient `g_v`, GP-A is the directional
baseline:

```text
C_hat_grad_raw(x, z) = <g_z, g_v> / (||g_z|| ||g_v||)
```

The positive sign follows from `J=-L_v`: after one SGD step
`theta'=theta-eta*g_z`, the first-order utility gain is `eta*<g_z,g_v>`. The score
is centered under the frozen conditional distribution before it can enter a VTDO update:

```text
C_hat_grad(x, z) = C_hat_grad_raw(x, z)
                 - E_(z~pi_t)[C_hat_grad_raw(x, z)]
```

GP-B centers in gradient space, which is algebraically equivalent to a centered dot product:

```text
g_bar_x = E_(z~pi_t)[g_z]
C_hat_B(x, z) = <g_v, g_z - g_bar_x>
```

GP-C projects the actual optimizer descent map `U_t` rather than the unpreconditioned gradient:

```text
u_z = U_t(g_z)
u_bar_x = E_(z~pi_t)[u_z]
C_hat_C(x, z) = <g_v, u_z - u_bar_x>
```

An optimizer-aware score is valid only for its exact frozen local optimizer contract. The current
engineering approximation is one state-homogeneous cold-start AdamW step with zero weight decay,
no inherited optimizer state, no mixed-state batch, fixed clipping, and a frozen LoRA parameter
subspace. It is not an approximation to the full Student training trajectory. Under plain SGD with
a positive scalar learning rate, GP-C is only a rescaling of GP-B and is not independent evidence.

The approximation has four deliberately separated evidence layers:

| Layer | Permitted use |
| --- | --- |
| synthetic oracle | update-operator controls only |
| Gradient Projection on estimation objectives | production-candidate estimation |
| Gradient Projection on disjoint validation objectives | proxy stability validation |
| finite symmetric distribution intervention | independent target validation only |

Historical local-Probe and one-state finite-Intervention schemas remain readable for audit and
mechanism diagnostics. They are not the canonical production estimator. In particular, a local
Probe cannot become energy-eligible merely because it is reproducible on its own validation set.

The Contribution data-isolation contract freezes four disjoint objects per task condition:

```text
baseline training D_t
state-specific gradient update sets B_z
estimation and validation objective records nu_est, nu_val
untouched final test nu_test
```

All instance identities are content-addressed. Update sets must be pairwise disjoint, and no
training instance may occur in either objective split or `nu_test`. Estimation and validation
objective records are mutually disjoint. The untouched final test is inaccessible while gradients,
scales, perturbations, and thresholds are frozen.

Independent validation perturbs the complete conditional distribution through zero-sum contrast
coordinates. It prebinds all task-state gradients, applies symmetric `+/-` perturbations, and
reconstructs coordinate effects from a frozen orthogonal design. It is a target, never an
estimator. The target must satisfy all of the following before rank evidence is interpreted:

```text
conditional probabilities remain positive and normalized
task marginal mu(x) and state support remain fixed
actual parameter step matches the intended step
numeric replay is deterministic
orthogonal reconstruction error passes its frozen bound
learning rate and optimizer match the intended production update
```

Production authorization requires at least 30 frozen tasks, exact nonuniform 3--5-state support,
and 3--5 fresh independently verified trajectory draws per state. Draws must have unique
trajectory identities and content hashes; repeated decision structures are observed outcomes
rather than grounds for resampling. Objective support is split into 16
estimation, 16 validation, and 16 sealed authorization records after a 4/8/16/32 support-scaling
check. State targets are decomposed into aligned common and differential supervised-token regions;
the full gradient must replay as their token-weighted composition, every record must retain both
regions, and pooled task-level differential-token coverage must pass its frozen floor. Record- and
state-level token fractions remain diagnostics, while differential-gradient signal remains a
separate hard gate. Independent targets use multi-radius block-Hadamard central differences,
Richardson extrapolation, null replay, and a post-global-update objective gradient. Jackknife
pseudovalues carry realization uncertainty into materialized Contribution estimates.

Rank evidence and induced-distribution evidence are both mandatory. Normalized target regret is
defined only for tasks whose attainable target gain exceeds the preregistered floor; low-gain tasks
remain in absolute-regret reporting and cannot be hidden behind a numeric denominator clamp. At
least 80% of tasks must support normalization. The authorization partition cannot select a scale,
perturbation, objective split, threshold, or estimator.

A manifest fails closed on incomplete support, checkpoint or metric drift, split leakage,
parameter-step non-identifiability, source-scale mismatch, failed rank evidence, or absent immutable
artifacts. Consequently:

```text
Scheme 3 + matching independent authorization -> energy eligible
Scheme 3 without authorization                -> Contribution = 0
finite intervention target                     -> never energy eligible
historical local Probe                         -> diagnostic only
```

The first completed 30-task Finance experiment found strong estimation-versus-validation proxy
stability but failed both independent cached-SGD batch-intervention rank gates. A subsequent
GP-A/B/C experiment used the same 30-task support and a separately frozen one-step cold-start
AdamW target. All three formula variants passed the target rank gate; GP-C had the highest point
estimate, but its paired advantage over GP-B was not statistically established. The result
supports Scheme 3 under that diagnostic optimizer contract, not cross-optimizer transfer or the
unavailable historical optimizer continuation.

A later production-matched authorization attempt preregistered GP-C as Primary on a strictly fresh
30-task population, froze disjoint Estimation/Validation/Authorization objectives, and added
next-distribution gates. GP-C failed before Authorization access: its Estimation/Validation
Spearman was `0.150/0.300`, probability-update direction agreement was `0.544/0.589`, and normalized
target regret remained above the frozen bounds. No real Finance Contribution authorization exists.
Until a production-matched approximation passes the independent contract, real rounds must use
`Contribution=0`; novelty and validity remain available under their own contracts. The positive
diagnostic and negative authorization evidence are recorded respectively in
`docs/finance_gradient_projection_abc_validation_report.md` and
`docs/finance_gradient_projection_independent_authorization_report.md`.

The later v19 sealed causal pilot separated numeric execution from target identifiability on a
fresh six-task pilot. The v18-certified strict-FP32 gradient path replayed successfully on all 60
state realizations, but both disjoint finite-target partitions failed their preregistered
reconstruction and radius-stability gates before GP-C was evaluated. A smaller-radius diagnostic
also failed to recover local linearity. This evidence narrows the current blocker to the finite
target-estimation regime used by the authorization protocol; it is neither a GP-C validation nor a
GP-C falsification. The Authorization objective remains unopened and real rounds continue with
`Contribution=0`. See `docs/finance_v19_sealed_causal_pilot_report.md`.

The v20 target-identifiability study increased both disjoint Objective roles to 16 records, added
four independent micro-splits, normalized perturbations by measured parameter movement, compared
direct coordinates with block sizes 2/4/7, and fit odd-cubic local response models. The execution
and replay contracts passed, but every direct-coordinate confidence interval crossed zero, block
reconstruction failed in both roles, and cross-role sign agreement was only `4/7`. This result
strengthens the measurement diagnosis: the current first-order finite Objective target is not
observable with the required precision. It still does not test or falsify GP-C or the theoretical
functional derivative. Authorization remains unopened and real VTDO retains `Contribution=0`.
See `docs/finance_v20_target_identifiability_report.md`.

The v22 Development successor replaces finite-radius recovery with an exact chain derivative of a
single frozen cold-start AdamW update. It uses 30 real Finance tasks, 100 accepted quotient states,
five independent realizations per state, and eight disjoint Objective micro-splits, yielding 4,000
crossed target observations. Numeric and simplex identities passed. All 30 outcome-blind primary
coordinates and all 100 state coordinates had 95% intervals fully contained within their
state-specific update-derived MPE; no coordinate was meaningfully beyond MPE. Objective micro-split
variation accounted for `99.9443%` of nested measurement variance, while realization variation was
negligible. This is precise evidence of practical equivalence for the Development one-step
surrogate, not a claim that theoretical Contribution is globally zero and not an evaluation of
GP-C. Fresh Validation remains unopened, Authorization remains forbidden, and real VTDO retains
`Contribution=0`. See `docs/finance_v22_development_exact_target_report.md`.

The post-v22 experiment changes the trajectory kernel before attempting fresh Validation. A
three-arm Direct/Bare, Scripted Tool, and Autonomous Agent Pilot tests whether model-selected tool
planning, query reformulation, verification, recovery, and stopping create valid states with larger
exact-target contrasts. Scripted and Autonomous share one frozen tool and Evidence environment;
all Host Observations are content addressed. A passing Pilot can advance only to Beneficiary
frontier screening, not Validation or GP-C. The Agent kernel requires new Explorer, catalog,
Reachability, and initial-distribution identities. See
`docs/finance_v23_capability_sensitive_agent_plan.md`.

## Novelty, Potential, And Anchored Update

Coverage-relative novelty is exact:

```text
N_t(x, z) = max(log(r(z | x) / pi_t(z | x)), 0)
```

The bounded terms are:

```text
C_tilde = epsilon + (1 - 2*epsilon) * sigmoid(C_t / T_c)
N_tilde = epsilon + (1 - 2*epsilon) * (1 - exp(-N_t / T_n))
Phi_t   = C_tilde^alpha * N_tilde^beta
alpha + beta = 1
```

The canonical update is:

```text
pi_(t+1)(z | x) proportional_to
    pi_t(z | x)^rho
    * r(z | x)^(1-rho)
    * Phi_t(x, z)^eta

rho = lambda / (lambda + kappa)
eta = 1 / (lambda + kappa)
```

`update_valid_trajectory_distribution()` evaluates this equation in log space and records every
state potential, exact exponents, KL divergence to history and coverage, total variation, and
entropy. Both anchors require positive full support.

## Explorer And Importance Weights

Training and exploration distributions are separated:

```text
q_t(z | x) = (1 - xi) * pi_t(z | x) + xi * r(z | x)
w_t(z | x) = pi_t(z | x) / q_t(z | x)
```

The training distribution may be sparse on Accepted states while `r` has positive support over the
complete active catalog. Consequently `q_t` remains positive for Quarantined discovery states and
their training-policy importance weight is exactly zero. `ExplorationDistribution` embeds both
source distributions and independently replays `q_t` and `pi_t/q_t`.

`StateConditionedTrajectoryExplorer` allocates a deterministic budget from `q_t`, asks a provider
to attempt each requested state, independently verifies every generated trajectory, and then maps
the realized trajectory back through `phi_x`. Requested labels are never trusted as observed
states. The batch records provider exhaustion, duplicates, verifier failures, mapping failures,
off-target realizations, and actual state counts. Importance-weighted estimation refuses partial or
unmapped batches rather than conditioning silently on generation success.

The Explorer provider is called only through the public request contract; neither the Explorer nor
the Materializer receives `TrajectoryVerificationContext` or a serialized target state. The Host
performs verification, quotient mapping, and state accounting.

The Explorer, distribution Materializer, beneficiary model used by contribution probes, and final
Student have separately frozen identities. `VTDORoleContract` requires an
`independent_regeneration` materialization policy. The Materializer may deliberately use the same
generator implementation as the Explorer, but it cannot reuse a discovery trajectory and cannot
silently reuse the beneficiary or Student identity under `strict_distinct`. Any model-role sharing
ablation must use `declared_shared` and freeze a justification hash.

## Canonical Round

```text
frozen task marginal mu(x)
  -> q_t state-budget allocation
  -> state-conditioned trajectory attempts
  -> independent V(tau, Omega_x)
  -> phi_x(tau) quotient assignment
  -> smoothed push-forward estimate
  -> Accepted / Quarantined / Rejected partition
  -> beneficiary-model contribution probes on fixed evaluation data
  -> exact coverage-relative novelty
  -> anchored energy update on Accepted support
  -> next pi_(t+1)(z | x), with mu(x) unchanged
  -> independently verified on-target training trajectories
```

`VTDORoundArtifact` embeds the state catalog, `q_t`, exploration batch, weighted push-forward,
complete validity estimates, Accepted support conditioning, contribution probes, contribution
manifest, role contract, and anchored update. Loading one artifact replays every cross-object
identity and equation. Opaque IDs alone are insufficient to certify a round.

`ValidTrajectoryStateMaterializer` converts the next distribution into deterministic state quotas
through a new generation phase. Every released record carries the full Task/`Omega_x`, State Catalog,
requested `TrajectoryState`, actual trajectory, independent validity report, quotient assignment,
source distribution, provider identity, public request identity, decision-trace hash, and role
contract. Materialization is a fresh generation phase. Reuse is rejected by trajectory ID, content
hash, and a normalized decision-trace hash that erases execution IDs, timestamps, generator build,
and rationale while retaining actions, tool capabilities and parameters, evidence, program roles,
and dependencies. Invalid, unmapped, duplicate, off-target, or discovery-reused attempts cannot
enter the released dataset.

When budget is at least the positive support size, deterministic allocation gives every state a
minimum count of one before proportional remainder allocation. Smaller budgets explicitly report
finite-support truncation; quotas are never reassigned after generation failure. The report replays
per-state attempts, acceptance and off-target rates, quota fill, source/target/released distributions,
allocation and release total variation, Jensen-Shannon divergence, and decision-trace uniqueness. A
passed materialization requires exact target quotas and zero release divergence.

## Relationship To CCGR

CCGR remains a historical synthesis-cell feedback baseline. Its former
`valid_trajectory_distribution_optimization@vtdo.v1` label was incorrect: it optimized a linear
score over `SynthesisCell + TrajectoryAttributeProfile`, used validity as a compensable reward, and
had no quotient state or coverage anchor.

That baseline is now explicitly named:

```text
trajectory_attribute_profile_proxy@trajectory_profile_proxy.v1
```

and exposed as `update_trajectory_profile_proxy_policy()`. It must not be reported as VTDO. The
canonical algorithm identity is:

```text
anchored_energy_valid_trajectory_distribution_refinement@aevtdr.v2
```

No compatibility alias is retained between these methods.

## Claim Boundary

The implementation establishes a testable engineering approximation and proof-carrying round
record. It does not yet establish convergence, unbiased causal contribution estimation, complete
state discovery, or downstream model improvement. Those claims require real Explorer trajectories,
frozen intervention experiments, repeated seeds, and held-out training-utility evaluation.

The property suite currently checks quotient invariance, false-diversity rejection, semantic state
separation, public-projection leakage, decision-trace replay rejection, legal and science same-Omega
multi-state compilation, validity triage, direct and importance-weighted push-forward, centered
contribution, the exact anchored equation, non-compensable validity, fixed task marginals,
full-catalog exploration, round replay, finite-budget support handling, and on-target state
materialization.
