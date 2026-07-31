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

## Push-forward Distribution

Observed executions are mapped before counting:

```text
pi_hat_t(z | x) = ((n_z + lambda_0 * r(z | x)) / (N + lambda_0))
```

`estimate_pushforward_distribution()` records exact state exposure counts, assignment identities,
the full-support coverage prior, and prior strength. Unknown observed states are rejected until the
state catalog and its coverage prior are explicitly revised.

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
Quarantined states remain exploration/audit targets; Rejected states are excluded. The update also
rejects any non-Accepted state on positive training support. Validity is never inserted into an
energy score and therefore cannot be compensated by novelty or contribution.

## Model-state-dependent Contribution

Contribution is an empirical intervention estimate tied to:

- one beneficiary model checkpoint;
- one fixed target evaluation distribution;
- one target metric;
- one frozen probe protocol;
- one task condition and one quotient state.

`ContributionProbeObservation` stores baseline and intervention metric values, sample count, and
confidence. It does not reuse CCGR's capability-gap heuristic. The confidence-adjusted marginal
gains are centered under the current distribution:

```text
C_t(x, z) = gain_t(x, z) - E_(z~pi_t)[gain_t(x, z)]
E_(z~pi_t)[C_t(x, z)] = 0
```

The manifest fails closed if state support, beneficiary model, evaluation distribution, metric, or
probe protocol differs.

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

`StateConditionedTrajectoryExplorer` allocates a deterministic budget from `q_t`, asks a provider
to attempt each requested state, independently verifies every generated trajectory, and then maps
the realized trajectory back through `phi_x`. Requested labels are never trusted as observed
states. The batch records provider exhaustion, duplicates, verifier failures, mapping failures,
off-target realizations, and actual state counts.

The Explorer, beneficiary model used by contribution probes, and final Student are separate roles.
`VTDORoleContract` freezes all three identities. Its default `strict_distinct` mode rejects accidental
reuse; an intentional shared-model ablation must use `declared_shared` and freeze a justification
hash. Role sharing is therefore an explicit experiment choice, not an assumption in Core.

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
```

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
anchored_energy_valid_trajectory_distribution_refinement@aevtdr.v1
```

No compatibility alias is retained between these methods.

## Claim Boundary

The implementation establishes a testable engineering approximation and proof-carrying update
record. It does not yet establish convergence, unbiased causal contribution estimation, complete
state discovery, or downstream model improvement. Those claims require real Explorer trajectories,
frozen intervention experiments, repeated seeds, and held-out training-utility evaluation.

The property suite currently checks quotient invariance, false-diversity rejection, semantic state
separation, cross-domain mapping, validity triage, push-forward smoothing, centered contribution,
the exact anchored equation, non-compensable validity, fixed task marginals, and exploration
importance weights.
