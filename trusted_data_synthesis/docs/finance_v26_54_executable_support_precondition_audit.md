# Finance v26.54 Executable-Support Precondition Audit

> Historical contract note: v26.54 remains an immutable v1 result at source commit `c67671c`.
> Finance v26.55 supersedes it for future task construction by adding explicit Citation
> completeness, correcting capability-only role admission, and checking counterfactual target
> identity. The 18/24 Witness result and all downstream blockers are unchanged. See
> `docs/finance_v26_55_executable_support_contract_hardening.md`.

Audit date: 2026-08-18

## Summary

Finance v26.54 implements the no-API compiler redesign authorized by the v26.53 statistical
audit. It does not rescore v26.43, relax any threshold, call a model API, use a GPU, or authorize a
downstream experiment. Its purpose is narrower: replace the assumption that one executable Oracle
Program implies usable Agent support with typed, content-addressed evidence for five separate
preconditions.

The audit compiles and freezes, for each of the 24 immutable v26.42 Development tasks:

1. a `TypedAnswerProjectionContract`;
2. a `PublicExecutableWitnessArtifact` plus every typed public tool Observation;
3. a `MechanismNecessityArtifact`;
4. an `AlternativeValidPathCatalog`;
5. an `EvidenceSupportLattice`;
6. one two-tier task-use decision separating capability measurement from VTDO multistate use.

The formal result is blocked:

```text
Public executable witness                 18 / 24
Typed answer projection bound              0 / 24
Evidence support lattice bound              0 / 24
Mechanism necessity proved                  0 / 24
Three model-owned valid paths proved        0 / 24
Capability-measurement eligible             0 / 24
VTDO-multistate eligible                     0 / 24
```

This is a constructive static result. Eighteen tasks have a replayable public solution, but none
of the 24 historical tasks satisfies the new complete support contract. The only permitted
transition remains:

```text
capability_task_or_scaffold_redesign_only
```

Fresh Confirmation, State-support Discovery, No-C VTDO, Student training, Exact Target, GP-C, and
production Contribution remain forbidden. Production Contribution is zero.

## Scientific Motivation

v26.53 showed that the 576 v26.43 rollouts did not globally collapse to one trace. Instead, the
system produced many distinct invalid paths and very few complete valid paths. The two dominant
first-failure stages were Operation Execution and Answer Projection. Local mechanism outcomes were
also decoupled from complete validity:

- Context alignment was frequent while branch flip and complete validity were absent;
- valid Reconciliation trajectories did not execute the registered Reconciliation Estimand;
- Recovery could improve locally without closing the full trajectory;
- Stopping remained unobserved.

The relevant prerequisite is therefore not raw trace entropy. It is executable support under a
fixed task and Scaffold condition:

```text
P(V=1)
P(Y_k=1 | V=1)
P(V=1 | Y_k=1)
H(Z | V=1,x,gamma)
```

The last quantity is undefined when a task-condition has no valid rollout. Invalid traces are not
assigned a zero-entropy state distribution and cannot create positive VTDO support.

## Frozen Inputs

The audit reads only immutable local artifacts.

| Input | Identity |
| --- | --- |
| v26.42 compiled proof artifacts | SHA-256 `43f634ec9c01a620277162e5cf41bc7060ca51240fa10eba5c0317c6eabd1959` |
| v26.42 Development Population | SHA-256 `effac9dd84012ed15dfa734b62a04dc1861c49d95938d442054cf1de0e3164fd` |
| v26.53 statistical audit | `finance_v26_bridge_statistical_audit:c7851d1487fbab1c5d4814451ea3f46aa52f54e68f01bc841cd66acfcd43c64b` |
| v26.53 report bytes | SHA-256 `feb52d559b9e0493456cac7d89edf70fff1eb3a3771b59ae667ed6b482359d95` |

The compiler refuses an incomplete source set and requires exactly 24 source tasks, 24 compiled
proof artifacts, and the complete non-authorizing 576-rollout v26.53 report.

## New Core Contracts

The new Core module is domain neutral. It contains no Finance import, Finance field, or domain
branch.

### Typed Answer Projection

One source specification binds:

```text
public_output_instruction
oracle_normalizer
human_renderer
verifier_matcher
```

Every view carries the same source-specification hash. A contract with one altered view hash fails
validation. Public output instructions expose only public labels, while the internal reference map
remains hidden.

All 24 projection contracts compile successfully. None is counted as bound because the immutable
historical tasks use the older parallel `answer_projection` representation. The audit does not
retrofit the new contract ID into an old TaskPackage or change its task hash.

### Evidence Support Lattice

The lattice separates:

- necessary Evidence coverage;
- registered sufficient support sets;
- known invalid ablations;
- semantic alternative search;
- exact-equality authorization;
- current Verifier binding.

Exact equality is rejected unless semantic-alternative search is complete, uniqueness is proved,
and exactly one sufficient set remains. The current run registers the Oracle/Public-Witness Gold
set and deterministic required-Evidence ablations, but does not claim semantic uniqueness. All
24 lattices therefore compile with `exact_equality_required=false` and
`binding_status=requires_verifier_binding`.

### Public Executable Witness

The public witness is not the existing Reference Workflow. Historical Reference Workflows use:

```text
oracle_evidence.read
operation_program.execute
operation_oracle.verify
```

Those tools are disjoint from the public Allowed Tools.

v26.54 instead executes the public Finance Runtime with public selectors, content-addresses every
tool Observation, replays the registered Operation DAG, checks Evidence lineage and verification
support, and compares the projected answer with the independently frozen source execution. The
artifact is hidden from the model and explicitly records `model_owned_path=false`.

The compiler produced 226 typed tool Observations. Eighteen of 24 tasks passed the complete
Witness check. The six failures are evenly distributed enough to reject a single-mechanism-only
explanation:

| Target mechanism | Passed | Failed |
| --- | ---: | ---: |
| Context-conditioned action | 6 | 2 |
| Semantic reconciliation | 6 | 2 |
| Failure recovery | 3 | 1 |
| State-dependent stopping | 3 | 1 |

Every failed task declares at least one Reconciliation axis but omits
`normalize_metric_unit_period` from Allowed Tools. The typed first blocker is:

```text
required_normalization_tool_not_allowed
```

This is a task/Runtime compilation defect, not an Explorer failure. The audit fails before
Operation, Verification, and Answer closure and does not manufacture a substitute normalization
step.

### Mechanism Necessity

The prospective mechanism taxonomy is now:

```text
context_conditioned_action        8 tasks
semantic_reconciliation           8 tasks
failure_recovery                  4 tasks
state_dependent_stopping          4 tasks
```

The eight historical `recovery_and_stopping` tasks are split only in the prospective audit view;
their immutable source labels are preserved. A future task must carry an explicit typed mechanism
contract and independently verified delete, replace, or bypass counterfactuals.

No historical task has that contract. Consequently:

- Context wrong-action irreparability passes `0/8`;
- Reconciliation normalized-reference emission and downstream consumption pass `0/8`;
- Recovery and Stopping remain combined in the historical Bridge contract;
- mechanism necessity passes `0/24`.

The audit does not infer necessity from a family name, a local Estimand, or a successful final
answer.

### Alternative Valid Paths

A capability-measurement task needs one Public Executable Witness and a necessary target
mechanism. A VTDO task additionally needs at least three complete valid paths with:

- distinct model-owned decision signatures;
- distinct behavior signatures;
- distinct Scaffold-invariant Quotient State identities;
- no state inflation caused only by Scaffold wording.

The deterministic compiler Witness cannot count toward this denominator because it is not a
model-owned path. The current 24 catalogs therefore contain zero admitted paths and all fail
closed. This prevents the three static State-Space variations from being misreported as three
empirically reachable valid states.

## Task-use Decision

The two task roles are now decided independently:

```text
Capability measurement:
  Answer Projection bound
  + Evidence Lattice bound
  + Public Witness passed
  + Mechanism Necessity passed

VTDO multistate:
  Capability measurement eligible
  + at least three model-owned valid paths in distinct Quotient States
```

The resulting counts are `0/24` and `0/24`. A task cannot enter VTDO merely because it is useful
for capability measurement, and a compiler-generated Witness cannot be promoted to a model-owned
state realization.

## Immutable Outputs

The authoritative report is:

```text
finance_v26_executable_support_audit:1c82f661174e1e62783272df1333fdfdaac9797422052b29c28f98f1784b7cc1
```

Artifact root:

```text
artifacts/vtdo_experiment/finance_v26_54_executable_support_audit_20260818/
```

| Artifact | Records | SHA-256 |
| --- | ---: | --- |
| Typed Answer Projection contracts | 24 | `c0aa214876f84ae46de0a8c757e7dbcaf0752079739b242b475a91841ba63338` |
| Public Executable Witnesses | 24 | `e72f2bdcb08a6507f57ba323b5964c38d689d19b6eaabf8f8278c33af620ac7c` |
| Public Witness Observations | 226 | `f66ed3b1e773d4d2fcaed432463dbb824ad50c036472d424ea9d67a505a9c84f` |
| Evidence Support Lattices | 24 | `e497832f3173cebfac9eb05330c9a6b3c45fa622b9b192a161c8b4e908f04b1b` |
| Mechanism Necessity artifacts | 24 | `3ba45c034216e794c888c403667e9b570e1eb271c5a1a1191eb6c5540d847f1b` |
| Alternative Valid Path catalogs | 24 | `3b0a6e16f054eca3c7ab8086d34c7cfd9d46804c474042445aefbff64c12f98f` |
| Task support compilations | 24 | `86a3fc6d614a2ed350a28afcebeed04cbd8ef06700bf898291f8f4434f96d845` |

The formal run used zero API calls and zero GPU jobs. A two-build test reconstructs all seven
detail files and the report byte for byte from the same immutable inputs.

## Interpretation Boundaries

The supported conclusions are:

1. a dedicated public Witness is feasible and succeeds for 18 current tasks;
2. six tasks are not publicly executable under their own Allowed Tool contract;
3. historical Answer Projection and Evidence matching are not bound to the new single-source
   contracts;
4. current tasks do not prove target-mechanism necessity;
5. current tasks do not prove three model-owned, state-distinct valid paths;
6. no current task may enter a new capability or VTDO run under the revised contract.

The following conclusions are not supported:

- v26.43 trajectories have been rescored;
- the 25 representation-only failures are now valid;
- exact-Gold matching caused the v26.43 negative result;
- Flash or VTDO is invalid;
- a compiler Witness estimates model reachability;
- the three structural State-Space variations are reachable Agent states.

## Next Experiment

The next stage remains no-API task rematerialization. It must create a fresh Population rather
than patch the 24 immutable tasks.

1. Compile Allowed Tools from actual required operations; fail before task identity freeze when a
   required normalization, verification, or recovery tool is absent.
2. Bind the typed Answer Projection and Evidence Support Lattice into the new TaskPackage identity
   and make the Runtime Verifier consume those exact contracts.
3. Compile Context tasks in which the wrong public action makes full validity irreparable.
4. Compile Reconciliation tasks whose normalization emits a typed Operation Reference consumed by
   a downstream calculator node.
5. Implement Failure Recovery and State-dependent Stopping as separate task mechanisms and
   separate Estimands.
6. Execute and freeze delete/replace/bypass mechanism counterfactuals before any API call.
7. For capability measurement, require one public Witness and mechanism necessity.
8. For VTDO, additionally require three executable paths with model-owned choice points and three
   distinct Scaffold-invariant state identities.
9. Start a fresh Development API run only after every selected task passes its declared role.

The first online report after rematerialization must report complete denominators for the four
conditional quantities above. Trace count or Trace JSD remains diagnostic and cannot authorize
support by itself.
