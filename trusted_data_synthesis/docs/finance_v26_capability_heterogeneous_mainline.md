# Finance v26 Capability-Heterogeneous VTDO Mainline

Date: 2026-08-17

## Decision

Finance v25.47 is frozen as a local, credible Flash capability limitation under a valid
measurement instrument. It is historical hypothesis evidence only. Its tasks, decisions, and
closed authorizations are not promoted into v26.

v26 returns to the VTDO mainline under a new immutable identity:

```text
finance_v26_capability_heterogeneous_vtdo_mainline.v3
```

The experimental object is a capability-heterogeneous distribution of valid Agent behaviors.
Unequal capability success is observed and stratified; it is not removed through outcome-based
task weighting and is never substituted for Contribution.

## Phase 0: Joint Compilation Admission

No fresh task may reach a model before one semantic source deterministically binds:

```text
Oracle verification context
Runtime-specific public projections
Versioned quotient-state catalog
State mapper
Independent verifier
Materialization contract
```

The domain-neutral `JointCompilationAdmissionArtifact` binds the existing
`JointCompilationArtifact` and `TrajectoryStateSpaceCompilation` to runtime projections,
auditor identities, the state canonicalizer, and materialization lineage. Admission requires:

```text
semantic_closure
public_sufficiency
executable_closure
verifier_consistency
recursive_noninterference
state_and_lineage_closure
destructive_mutation_rejection
```

Destructive mutation evidence covers required-Evidence removal, Program mutation, operand swap,
time/unit change, Proof-edge damage, Host-field injection, State Mapper mutation, and Public
Projection replacement. Any failed gate has one transition:

```text
joint_compilation_repair_only
```

This Core contract is exercised by Legal and Science fixtures. Finance is the first production
consumer, not the specification of the admission API.

## Capability Bridge Before State Discovery

For task-capability pairs whose valid quotient states are structurally available but unreachable
to the Explorer, Joint Compilation may compile a cumulative `gamma_0..gamma_3` public scaffold
ladder. The ladder binds the target capability and scaffold policy into the task condition, keeps
the target decision under model authority, and leaves the valid quotient-state space unchanged.
It admits each level only after Oracle consistency, public sufficiency, target-authority,
recursive noninterference, incremental necessity, withdrawal readiness, and scaffold-invariant
state-mapping gates.

Finance v26 preregisters a 24-task, three-mechanism Development Pilot. Its 576 rollouts measure
mechanism-specific capability boundaries; observed state count is diagnostic. It selects the
minimum passing scaffold once per mechanism and confirms it on 24 independently admitted fresh
tasks. Passing confirmation authorizes only a separate state-support study: 12 additional
unconditional rollouts per task, 3-5 independently accepted states, Wilson lower bounds, and
state-level materialization budgets. Per-task scaffold choice and quota transfer are forbidden.
See `docs/finance_v26_compiler_assisted_capability_bridge.md`.

## Frozen Data Partitions

All partitions are disjoint on task, Evidence, Evidence Version, semantic signature, and
trajectory identity.

| Split | Tasks | Purpose |
| --- | ---: | --- |
| Synthesis / Training | 100 | Discovery, materialization, No-C rounds, Student training |
| Internal Agent Evaluation | 60 | Held-out capability-slice evaluation |
| Exact Target Development | 30 | New-state strict one-step target development |
| Exact Target Validation | 60 | Sealed validation after a meaningful coordinate |
| Objective Support | 128 | 16 micro-splits of 8 records |

The synthesis task marginal is frozen to `mu(x) = 1/100`. Model outcomes may not alter task
weights. DeepSeek V4-Flash is the sole main Explorer; eight unconditional rollouts are planned per
synthesis task. Pro remains optional and is not authorized by v26.0.

## Three Support Sets

`S_measure` contains every construct-valid, observable, interference-free, runtime-eligible
outcome, including attributed model failures.

`S_train` contains only fresh materialization trajectories that pass independent validity,
replay, quotient-state mapping, and exact decision-trace deduplication.

`S_C` is a strict subset of `S_train`. A record enters it only after a frozen Beneficiary
boundary, Exact Target beyond MPE, independent GP-C validation, a valid distribution update, and
a sealed Contribution authorization identity.

Exact Target and GP-C intermediate observations remain representable without being promoted into
`S_C`. Inverse-success weighting is forbidden.

## State Discovery And Materialization

The 24-task Bridge state-support study is a feasibility gate, not the final 100-task training
population. It may authorize compilation of that population but cannot promote its trajectories.
Each of the 100 synthesis tasks must independently support 3-5 accepted quotient states under its
frozen compiled condition. Discovery and materialization identities are separate. Every state
requires at least three fresh positive training realizations; Exact Target uses five. Failed,
off-target, and duplicate attempts remain in audit denominators and cannot be reallocated to
easier states. A task with insufficient state capacity is replaced before the task marginal is
frozen.

Scaffold fields never enter quotient-state identity or Novelty. They are preserved only in a
separate audit trace. All VTDO arms share the same compiled task condition, including the same
mechanism-level `gamma*`.

## No-C Mainline

Until Contribution is authorized, the method is named:

```text
AEVTDR-NoC / novelty-anchored VTDO
```

It is not full `C+N` VTDO. The primary coverage prior is uniform over accepted states;
reachability-weighted prior is a sensitivity analysis. Rounds 1 and 3 are materialized for Student
training. Round 5 is dynamics-only.

The frozen Student matrix is:

| Arm | Role |
| --- | --- |
| B1 Raw | Quality lower bound |
| B2 Validity | Primary causal baseline |
| B4 Random State | Primary causal baseline |
| B2 Novelty Only | Primary ablation |
| B5 No-C Round 1 | Primary experiment |
| B5 No-C Round 3 | Primary experiment |
| B3 CCGR | Secondary historical comparison |

All primary causal arms preserve `sum_z w(x,z) = 1` per task. Student training uses one frozen
Qwen2.5-7B revision, 500k assistant-supervised tokens, three seeds, and one Benchmark snapshot.
FinQA and TAT-QA are mandatory external evaluations. Internal reporting includes all seven
capability slices, strong-slice retention, weak/boundary gains, overcompensation, forgetting, and
Round 1 versus Round 3.

## Contribution Recovery Branch

Contribution recovery is isolated and does not block No-C experiments. It uses the strict FP32
one-step AdamW chain-rule target, 30 Development tasks, five realizations per state, and 128
Objective records across 16 micro-splits.

GP-C remains unevaluated unless Development contains preregistered coordinates meaningfully
beyond MPE. Full `C+N` rounds and Contribution-only training remain blocked until independent
Validation and sealed authorization pass. Production Contribution is zero.

## Current Engineering Boundary

The current revision implements and tests the protocol, support partition, typed fresh Population,
evidence-derived Joint Compilation admission, deterministic capability-scaffold compilation,
atomic Bridge accounting, Bridge/state-support separation, and fail-closed Stage Router v4. It has
materialized disjoint 24-task Development and Confirmation roots, but does not yet claim:

```text
per-task Joint Compilation admission
per-task Scaffold admission
Flash state discovery
state materialization
No-C distribution updates
Student training
Exact Target or GP-C
```

The next permitted work is exact per-task Joint Compilation, atomic audit, capability-gap
decomposition, and capability-scaffold admission. API work remains closed until the corresponding
Stage Router admissions are complete. GPU work is outside the pre-training router and remains
closed until State-support freeze. The v26.10 preflight binds Stage Router v4, the typed Population
compiler, and atomic-audit implementation manifests. Its zero-call ledger has completed
`fresh_task_population` and now stops at `joint_compilation`. Earlier preflight artifacts remain
historical and cannot be reused.

## 2026-08-28 Capability Breadth-Depth Observability Revision

The current mainline separates three concepts that earlier protocol text conflated:

```text
DifficultyTier          = historical global-complexity bundle
ObservationDepth        = prospective target-capability observability load
EmpiricalBoundaryStatus = post-execution floor, ceiling, bracket, or confounding result
```

`easy_control`, `frontier`, and `hard_control` remain valid historical labels but are not an
ability scale and cannot be renamed as D0-D3. A Capability Survival stage is an execution-failure
localizer, not a depth coordinate. Retrieval, calculation, and verification are supporting or
nuisance dimensions; the current breadth is restricted to Context-conditioned Action, Semantic
Reconciliation, Failure Recovery, and State-dependent Stopping.

The primary design unit is a fresh matched core `b_(k,g)`. Its four variants share one Finance
question, exact Evidence and Versions, result, Answer schema, Oracle Program, Verifier, Tool and
resource contracts, model/Thinking profile, and generation Policy. A single-capability overlay
`Delta_(k,d)` may change only the registered target load. D0 is a real minimum mechanism
observation; it is not a zero-load or single-candidate control. D1-D3 are constructively ordered,
while empirical success monotonicity remains an outcome to test.

Every group uses a D3-sized maximum skeleton at all depths. A shallower variant retains unused
slots as unique-action, identity-normalization, non-trigger-recovery, or explicit-nonterminal
placeholders. Deleting slots, changing nuisance load, or using source Program size as stopping
depth is forbidden. The matched group is the independent statistical unit; depth variants and
rollouts are paired repeated measures.

Development and reserved Confirmation groups are frozen together before any Provider call.
Exposure is group-wide, partial regeneration is forbidden, and Development code cannot load a
Confirmation payload. Development may only locate an observation floor, ceiling, adjacent
bracket, or nonmonotonic/confounded result. Confirmation tests a precommitted adjacent bracket;
it cannot establish a same-data VTDO effect. State support and VTDO require another fresh
Population after boundary confirmation.

v26.167 implements this theory as sixteen matched groups and 64 static D0-D3 tasks, passes all
seventeen static Gates and 22 destructive controls with zero Provider calls, and authorizes only
`capability_observation_development_runner_preflight_only`. See
`docs/finance_v26_167_capability_breadth_depth_task_synthesis_and_static_audit.md`.

## 2026-08-28 Executable Depth Reaudit

A later independent audit preserves v26.167 as a metadata-ladder static prototype. Production
replay closes only 48/64 old operational Witness variants; all sixteen Reconciliation variants
lack consumed normalization references, and every old group retains one Program, Tool set, and
Witness sequence across D0-D3. The old Development Runner preflight is therefore superseded
without execution.

v26.168 rematerializes the scientific object rather than relabeling it. It selects two old Easy
Development and two old Frontier Confirmation sources per capability before outcomes, reduces
each to a real two-Evidence, one-Program-node Finance core, and binds 64 fresh packages to typed
executable State, Candidate, Transition, event, Witness, and Verifier objects. Every variant
separately executes the production operational Witness compiler, independent TaskProgram
Verifier, depth Runtime, and mechanism event Verifier.

The resulting computed ladders are:

```text
Context-conditioned Action       2 /  4 /  8 / 14
Semantic Reconciliation          6 / 10 / 16 / 30
Failure Recovery                 5 /  6 / 12 / 21
State-dependent Stopping         5 /  7 / 11 / 16
```

All 64 variant-local verification surfaces pass, all sixteen Reconciliation variants consume
their exact references, and 128 target-delete/bypass counterfactuals fail full validity. All 32
Development variants remain within the frozen low-nuisance envelope. The separate sealed
Confirmation Root exposes only a payload-free receipt to Development. This is static executable
construct evidence, not model behavior or empirical boundary evidence.

The boundary algorithm uniquely classifies all 256 two-group-by-four-depth support patterns under
both Development 2/6 and Confirmation 3/8. A 294-file transitive source closure, 22 Gates, and
thirty real production-object mutations pass with zero Provider calls or Jobs.

The preliminary v1 and v2 sources remain immutable. v1 retains one local package-wide Mypy
diagnostic; v2 separates the two local mapping variable names. The authoritative v3 additionally
wraps one Ruff E501 expression. All scientific object bytes and the sealed Catalog remain
unchanged; v3 is authoritative.

The current mainline transition is only:

```text
capability_observation_executable_depth_development_runner_preflight_only
```

That successor remains credential-free. Provider execution, Confirmation loading, graph or
threshold changes, Mapper, State, Contribution, VTDO, training, release, and production remain
closed. See
`docs/finance_v26_168_executable_capability_depth_rematerialization_and_static_reaudit.md`.
