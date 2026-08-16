# Finance v26 Compiler-Assisted Capability Bridge

Date: 2026-08-17

## Scientific Role

Joint Compilation now has a second, explicitly bounded responsibility. In addition to preserving
one semantic source across Oracle, Public, Runtime, Verifier, State Mapper, and Materialization,
it may compile the minimum public scaffold needed to move a weak-capability task from an
unreachable floor into a measurable, non-saturated boundary region.

This does not alter VTDO. The compiler determines the reachable support; VTDO later redistributes
probability mass on a frozen support. A scaffold level is part of the experimental condition:

```text
x_tilde = (task, runtime, target_capability, scaffold_level, scaffold_policy_version)
```

Two methods may be compared causally only when they receive the same `x_tilde`.

## Core Compilation Objects

The domain-neutral Core adds:

```text
CapabilityPrerequisiteGraph
MinimalPublicStateSummarySpec
CapabilityAwarePublicProjection
CapabilityScaffoldLadderCompilation
CapabilityScaffoldGateEvidence
CapabilityScaffoldAdmissionArtifact
```

The capability graph records model-owned decisions and their prerequisites. Host-only completion
evaluators remain outside every model-visible projection. The state summary is deterministic,
action-neutral, and parameter-neutral. It may summarize only registered public fields such as
completed operation types, unresolved public preconditions, typed failure categories, and
remaining budget.

## Scaffold Ladder

Each admitted task/runtime/capability condition compiles four cumulative levels:

| Level | Public assistance |
| --- | --- |
| `gamma_0` | Original admitted public task and runtime projection |
| `gamma_1` | Typed minimum public state summary |
| `gamma_2` | Summary plus capability prerequisites and action-effect categories |
| `gamma_3` | Summary, capability contracts, and public subgoal DAG |

No level may expose the correct action, correct arguments, hidden Program path, Gold Evidence,
reference answer, Host event, mechanism activation, or internal completion label. The model keeps
authority over the target decision at every level.

## Admission Gates

All four levels independently require:

```text
oracle_consistency
public_sufficiency
target_authority_preservation
recursive_noninterference
minimality
scaffold_withdrawal
```

The gates bind content-addressed audit cases to the exact ladder, projection, Joint Compilation,
evaluator, and version. Any missing or failed level/gate pair blocks the ladder and permits only:

```text
capability_scaffold_repair_only
```

Legal and Science contract tests use this same Core API. Finance supplies mechanisms and task
semantics, not Core branches.

## Development Pilot

The Finance v26 Bridge Development population is frozen before any model call:

| Mechanism | Tasks |
| --- | ---: |
| Context-conditioned action | 8 |
| Semantic reconciliation | 8 |
| Recovery and stopping | 8 |

Each task is evaluated at `gamma_0..gamma_3` with six Flash rollouts per level:

```text
24 tasks x 4 levels x 6 rollouts = 576 Development rollouts
```

The model outcome is not a Runtime-validity gate. Instrument-valid successes and model failures
remain in the complete capability denominator. Runtime or Host failures are recorded separately.

The preregistered scaffold cell criteria are:

```text
target success rate in [0.15, 0.85]
valid trajectory rate >= 0.20
at least 75% of tasks expose >= 3 reachable valid quotient states
counterfactual fidelity >= 0.95
gain over fixed-policy baseline >= 0.05
instrument valid rate = 1.00
Host interference count = 0
Oracle leakage count = 0
```

These thresholds identify a measurable boundary; they are not an objective for maximizing
correctness.

## Support Freeze And Fresh Confirmation

The minimum passing scaffold is selected once per mechanism. Per-task outcome-conditioned
selection, failed-task deletion, quota reallocation, and inverse-success weighting are forbidden.
All scaffold levels within a mechanism must use the same eight Development tasks, and mechanisms
must use disjoint task identities.

After the mechanism-level support freeze, 24 completely fresh tasks receive only the selected
level, with six rollouts per task:

```text
24 tasks x 6 rollouts = 144 confirmation rollouts
```

Only a fresh confirmation may authorize Agent state discovery and materialization under the
frozen scaffold condition.

## Scaffold Withdrawal

Student evaluation freezes four conditions:

```text
unassisted train -> unassisted eval
scaffold train   -> scaffold eval
scaffold train   -> unassisted eval
scaffold train   -> weaker-scaffold eval
```

The primary transfer estimand is the unassisted held-out gain after scaffolded training relative
to the unassisted baseline. Improvement only under the training scaffold is interface adaptation,
not evidence of capability transfer.

## Current Boundary

This revision implements contracts, compilation, support selection, and fail-closed tests. It has
not built the 24-task population and has made no Bridge API call or GPU job. The next permitted
stage remains per-task Joint Compilation and capability-scaffold admission.

The immutable scaffold-aware v26 preflight is stored under:

```text
artifacts/vtdo_experiment/
finance_v26_0_capability_heterogeneous_mainline_protocol_v5_20260817/
```

It passed all 18 checks with zero API calls and zero GPU jobs. Its frozen identities are:

```text
protocol_id = finance_v26_capability_heterogeneous_vtdo_mainline:
              722dcc720f3d2c5a46fee2fa57bcb74286795f70d57231e58ac3f1f576735b66
report_id   = finance_v26_mainline_preflight:
              9b3d340cdaac1b8434175d9045d8c11b9f36afa4197876a94fc19db896a918a8
```
