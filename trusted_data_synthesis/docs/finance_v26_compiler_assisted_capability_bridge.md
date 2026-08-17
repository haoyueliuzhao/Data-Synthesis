# Finance v26 Compiler-Assisted Capability Bridge v2

Date: 2026-08-17

## Scientific Boundary

Joint Compilation may compile the minimum public scaffold needed to move a weak-capability task
from an unreachable floor into a measurable boundary region. It does not create a new valid
behavior space and it does not optimize the VTDO state distribution.

For every task `x`, the valid quotient-state space is invariant across scaffold levels:

```text
Z_valid(x, gamma_0) = ... = Z_valid(x, gamma_3) = Z_valid(x)
```

Only model reachability may change:

```text
Z_reach(x, model, runtime, gamma) is a subset of Z_valid(x)
```

The frozen experimental condition is:

```text
x_tilde = (task, runtime, target_capability, scaffold_level, scaffold_policy_version)
```

VTDO compares trajectory-state distributions only after one `gamma*` is frozen for a mechanism.
Changing `gamma` is a Compiler Bridge intervention, not a VTDO distribution intervention.

## Core Contracts

The domain-neutral Core owns:

```text
CapabilityPrerequisiteGraph
MinimalPublicStateSummarySpec
CapabilityAwarePublicProjection
ScaffoldInvariantStateMappingContract
ScaffoldSeparatedTrajectoryView
CapabilityScaffoldLadderCompilation
CapabilityScaffoldGateEvidence
CapabilityScaffoldAdmissionArtifact
```

Finance owns the three mechanisms and their outcome definitions. Core contains no Finance branch.

### Scaffold-invariant state mapping

The state mapper strips scaffold-only fields before creating a quotient-state identity:

```text
scaffold_level
scaffold_policy_version
public_state_summary
capability_contract
action_effect_contract
public_subgoal_dag
```

It retains actual model decisions:

```text
tool_choice
tool_arguments
evidence_selection
recovery_action
verification_action
stop_decision
```

The stripped scaffold trace is preserved in a separate content-addressed audit side channel. Two
cross-level trajectories with the same decisions must therefore have the same behavior-state
identity and different scaffold-trace identities. Scaffold text cannot manufacture novelty.

## Scaffold Ladder And Static Admission

| Level | Incremental public assistance |
| --- | --- |
| `gamma_0` | Original admitted public task and runtime projection |
| `gamma_1` | Typed minimum public state summary |
| `gamma_2` | Summary plus capability prerequisites and action-effect categories |
| `gamma_3` | Summary, capability contracts, and public subgoal DAG |

Every level shares one Evidence, Program, Answer, Proof Graph, Quality Contract, Runtime, valid
state-space compilation, and base State Mapper. Each level must pass seven gates:

```text
oracle_consistency
public_sufficiency
target_authority_preservation
recursive_noninterference
incremental_necessity
withdrawal_readiness
state_mapping_invariance
```

`incremental_necessity` tests only the aid added relative to the predecessor. It does not call all
four cumulative levels globally minimal. The minimum passing level is selected later from the
complete ladder.

`withdrawal_readiness` is a static pretraining gate: `gamma_0` exists, removal preserves the
semantic root, scaffold fields are absent from Answer and Gold identities, and unassisted
evaluation is independently executable. It is not evidence of post-training transfer.

Finance additionally freezes six construct checks for every Bridge task before any model call.
They cover mechanism-specific Estimand definition and replay, non-target semantic preservation,
Oracle/Host leakage rejection, and exact static construct fidelity. Development and Fresh
Confirmation have distinct static authorizations. A new confirmation task cannot reuse the
Development authorization.

## Mechanism-specific Estimands

A generic `counterfactual_fidelity` scalar is forbidden. The Bridge records Bernoulli outcomes for
each registered mechanism-specific Estimand:

| Mechanism | Estimands |
| --- | --- |
| Context-conditioned action | `context_action_alignment`, `counterfactual_branch_flip` |
| Semantic reconciliation | `semantic_reconciliation` |
| Recovery and stopping | `failure_recovery`, `stopping_calibration` |

The Estimands preserve the definitions from the audit: correct first action under public Context,
correct paired branch flip, relation-aware normalization with non-target semantics preserved,
root-cause recovery followed by success, and continue/stop calibration without post-completion
violations. Each is reported separately and compared with its fixed-policy baseline.

Static construct fidelity is exactly `1.0`; it is not mixed with model behavior. A mechanism-level
cell passes only when every registered Estimand is in `[0.15, 0.85]`, each has at least `0.05`
fixed-policy gain, valid trajectory rate is at least `0.20`, instrument validity is `1.0`, and Host
interference and Oracle leakage are zero.

## Bridge And State-support Phases

### Phase 0-1: Joint Compilation and static audit

Every task first receives ordinary Joint Compilation admission, all four scaffold projections,
the seven Core gates, and the Finance static construct audit. Failure permits only repair and
records zero API calls and zero GPU jobs.

### Phase 2: Bridge Development

```text
24 tasks x 4 levels x 6 rollouts = 576 Flash rollouts
```

These observations estimate mechanism-specific boundary response, valid trajectory rate,
fixed-policy gain, Runtime integrity, and preliminary state diversity. State count and entropy are
diagnostics only. Six rollouts do not prove complete three-state support.

### Phase 3: Mechanism-level freeze

The globally minimum passing scaffold is frozen once per mechanism. Per-task scaffold selection,
task deletion, task reallocation, and inverse-success weighting are forbidden. Higher passing
levels remain diagnostic only. Across levels, the task set and state-mapping contract remain
identical; compiled task-condition IDs must differ because scaffold level is part of `x_tilde`.

### Phase 4: Fresh Bridge Confirmation

The 24 confirmation tasks are disjoint from Development and receive their own static authorization:

```text
24 fresh tasks x 6 rollouts = 144 Flash rollouts
```

They use only the frozen mechanism-level scaffold. Passing confirmation authorizes exactly
`state_support_discovery`; it does not authorize VTDO, state materialization, or Contribution.

### Phase 5: State-support discovery

The same 24 confirmed task conditions receive 12 additional unconditional rollouts, bringing the
total to 18 per task:

```text
24 tasks x 12 additional rollouts = 288 additional Flash rollouts
```

Only this phase enforces 3-5 independently accepted quotient states. Every state records:

```text
unconditional hit count and rate
Wilson 95% lower confidence bound
state-conditioned attempts and accepts
conditioned acceptance rate and lower bound
target realization quota
estimated attempts needed at the lower bound
independent verification status
```

The lower bounds must be positive and the estimated cost of three realizations must not exceed 60
attempts per state. Failed state quota cannot move to another state, and failed task quota cannot
move to another task. State mapping and scaffold-trace separation are replayed for every task.

A complete passing freeze authorizes compilation of a fixed-condition No-C population. Production
Contribution remains zero and unauthorized.

## Two Separate Causal Experiments

### Compiler Bridge efficacy

This changes `gamma` and asks whether scaffolding expands reachable valid support and transfers
after training. The post-training Withdrawal Transfer matrix is:

```text
unassisted train -> unassisted eval
scaffold train   -> scaffold eval
scaffold train   -> unassisted eval
scaffold train   -> weaker-scaffold eval
```

The primary transfer Estimand is unassisted held-out gain after scaffolded training relative to
unassisted training. Benefit only under the scaffold is interface adaptation, not transfer.

### VTDO distribution efficacy

This keeps `x_tilde`, including `gamma*`, identical across arms and compares:

```text
validity
random
novelty
aevtdr_no_c
```

Only the trajectory-state distribution changes. The Bridge result cannot be used as evidence that
VTDO works, and a VTDO result cannot be used as a withdrawal-transfer claim.

## Current Boundary

The implementation now provides evidence-derived Joint/Scaffold admission, executable public
summary compilation, runtime authority policies, atomic Bridge rollouts, exact condition lineage,
and the incompatible `finance_v26_stage_router.v4` chain through State-support freeze. This closes
the static execution route; it does not create empirical evidence.

Disjoint 24-task Development and Fresh Confirmation Population roots now exist. No per-task
Joint/Scaffold admission, Bridge rollout, API call, GPU job, Student run, or Contribution result
exists. The next permitted stage is per-task Joint Compilation and static scaffold admission
through the Stage Router. The v26.10 immutable preflight freezes the typed Population, atomic
admission, scaffold, Bridge, audit-artifact, and Stage Router source hashes. It passed 24/24 checks,
froze 14 implementation files, and advanced a zero-call ledger through `fresh_task_population` to
`joint_compilation`:

```text
artifacts/vtdo_experiment/
finance_v26_0_capability_heterogeneous_mainline_protocol_v10_20260817/
```

Earlier v26 preflights, including v6, remain historical and are stale against this implementation.
No model client may be instantiated until the corresponding task has crossed Joint and Scaffold
admission through this ledger. See `docs/finance_v26_joint_compilation_audit_closure.md`.
