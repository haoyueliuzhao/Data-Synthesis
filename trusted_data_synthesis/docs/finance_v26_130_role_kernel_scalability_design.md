# Finance v26.130 Full-Mechanism Role-Support Complexity Census And Scalability Design

## Scope And Authorization

Finance v26.130 consumes only the credential-free transition frozen by v26.129:

```text
frozen_role_population_kernel_scalability_design_only
```

It preserves the exact v26.129 Capability and Reachability source Populations and performs a
measurement-only full-mechanism complexity census. It compares exactly two prospective
Scalability Candidates:

- S0 keeps the complete v26.128 semantic-action Prompt representation and changes only capacity;
- S1 keeps the same public state, Candidate set, Candidate presentation, canonical `action_id`,
  response Grammar, interaction stages, and Stage 2 Commit, but serializes the public state and
  Candidates through a reversible compact projection.

This stage does not materialize a future Role TaskPackage, Contract, Manifest, Job, or Runner. It
does not look up a credential, construct a model client, make a Provider call, run a GPU job,
create an empirical row, reclassify a historical row, map a State, or measure Capability or
Reachability.

## Immutable Replay

The build reparses the v26.129 report, transition, source Populations, source selection, Context
compatibility audit, and Sampling Frame. It then replays:

```text
3,154 v26.129 transitive bindings
   10 v26.129 output files
    1 exact v26.130 implementation
--------------------------------
3,165 exact files
```

Every observed SHA-256 matches its binding before the full-mechanism census starts. The exact
frozen Population identities remain:

- Capability:
  `finance_v26_fresh_role_source_population:1e22847979b0927e1f772ab8b945dc4e57c2e0dc3b95f0673b1d1543470975e3`;
- Reachability:
  `finance_v26_fresh_role_source_population:cf4ff4407c4ca727c9b9c140e87261d3358c4974d92ea8605ce66bae2d316d99`.

The denominator is still 24 distinct source tasks, one task in every
Role x Mechanism x Tier cell. Historical and cross-role eight-channel overlap remains zero.
Post-hoc deletion, substitution, and Tier change counts are zero. No source Population is
regenerated and no model outcome is loaded for source or Candidate selection.

## Full-Mechanism Census

The v26.129 first Gate deliberately stopped after Context-conditioned Action failed. v26.130
disables that diagnostic fail-fast and compiles all required paths:

```text
12 Capability sources x 1 structured_direct path = 12 paths
12 Reachability sources x 3 registered paths       = 36 paths
--------------------------------------------------------------
                                                    48 paths
```

All four mechanisms contribute twelve paths:

- Context-conditioned Action;
- Semantic Reconciliation;
- Failure Recovery;
- State-dependent Stopping.

The 16 Easy, 16 Frontier, and 16 Hard paths are measured without removing a failed path. For each
path the census records source Program nodes, public and target Evidence counts, every reached
Candidate count, Candidate and public-state bytes, Primary/ABI Rescue/Semantic Recovery Prompt
bytes, Primary request count, potential Provider-call count, transport-replacement invocation
count, static complete-path upper bounds, and each failed v26.128 Kernel dimension.

The twelve Context rows reproduce v26.129 exactly on diagnostic TaskPackage and Environment
identity, action-state and public-call counts, maximum Candidate count and bytes, maximum Prompt,
request and call counts, static path bound, and compatibility classification.

### Deep Reconciliation Diagnostic Compiler

The historical one-node Reconciliation builder remains untouched and byte-bound by predecessor
replay. v26.130 contains an isolated diagnostic extension for the frozen three-node and five-node
Reconciliation sources:

1. each Program Evidence input receives one public normalization node;
2. each original Program node is retained in topological order;
3. Evidence operands consume the existing `normalized_inputs.target` selector;
4. Operation operands consume the exact preceding public Operation reference;
5. every original Program node retains one Verifier binding;
6. the original output node remains the terminal Operation.

This is a prospective diagnostic compilation fixture. It does not mutate the v26.128 Kernel,
v26.129 artifacts, or any historical task outcome.

## Frozen-Kernel Result

Under the unchanged 60,000-byte Prompt, eleven-Primary-request, twelve-Provider-call, and
400,000-token rollout bounds, the full census closes as:

```text
compatible paths    = 18 / 48
incompatible paths  = 30 / 48
```

The dimension counts are non-exclusive:

| Mechanism | Paths | Compatible | Prompt | Primary Request | Provider Call | Rollout |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Context-conditioned Action | 12 | 4 | 4 | 6 | 6 | 8 |
| Semantic Reconciliation | 12 | 4 | 0 | 8 | 8 | 8 |
| Failure Recovery | 12 | 4 | 0 | 6 | 6 | 8 |
| State-dependent Stopping | 12 | 6 | 0 | 6 | 6 | 6 |
| **Total** | **48** | **18** | **4** | **26** | **26** | **30** |

The Tier partition is:

| Tier | Paths | Compatible | Prompt | Primary Request | Provider Call | Rollout |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Easy | 16 | 16 | 0 | 0 | 0 | 0 |
| Frontier | 16 | 2 | 0 | 10 | 10 | 14 |
| Hard | 16 | 0 | 4 | 16 | 16 | 16 |

This confirms rather than assumes the full-support scale. The other mechanisms do not exceed the
Context maxima, but their additional request and rollout failures materially expand the
incompatible denominator. The v26.129 Context result was sufficient to block execution; it was
not a complete four-mechanism classification.

The global S0 maxima are:

```text
Candidate count                         63
Candidate projection bytes          57,829
Prompt bytes                         86,161
Primary requests                         20
Stage 1 Provider calls with recovery     22
Provider invocations with transport      23
Static complete-path bound         1,276,468
```

All 48 diagnostic Programs close, complete the terminal node, reach terminal verification, and
commit Final with zero Provider calls. These are local reference fixtures and create zero
Capability, Reachability, State Mapping, or empirical rows.

## S1 Lossless Compact Projection

S1 uses two deterministic representations:

- homogeneous public-state object sequences become typed columnar tables only when that
  representation is shorter than canonical full-object JSON;
- Candidates are grouped by Decision kind and retain only the fields applicable to that kind,
  plus an exact presentation index and unchanged canonical `action_id`.

The fixed public-state and Candidate contract fields are emitted once and restored before strong
Schema validation. The decoder reconstructs the exact `SemanticActionState`, canonical Candidate
set, and salted presentation order. It does not alias the model response, replace an action,
insert a semantic field, delete a Candidate, or choose a Stage 2 value.

The complete static control covers 522 reached public states. For each state, Primary, ABI Rescue,
and Semantic Recovery compact Prompts are independently parsed. The control therefore includes:

```text
522 Primary Prompt controls
522 ABI Rescue Prompt controls
522 Semantic Recovery Prompt controls
522 exact state reconstructions
522 exact Candidate-set reconstructions
522 exact Candidate-order reconstructions
522 exact Reference Proposals
522 exact reversible Stage 2 Commits
```

All controls pass. Candidate deletion, substitution, changed `action_id`, Host semantic repair,
private reasoning persistence, and Stage 2 Provider calls are zero.

The global S1 maxima are:

```text
Candidate projection bytes          30,806
Prompt bytes                         54,569
Primary requests                         20
Stage 1 Provider calls with recovery     22
Provider invocations with transport      23
Static complete-path bound         1,037,084
```

Relative to the global S0 maxima, these are descriptive static reductions of approximately
46.73% for Candidate bytes, 36.67% for Prompt bytes, and 18.75% for the conservative path bound.
They are not Provider Usage estimates or model-success measurements. S1 intentionally does not
reduce interaction depth; request and call maxima remain 20 and 22.

## Candidate Qualification And Selection

The pre-outcome qualification rule uses one 20,000-token/byte engineering quantum and requires at
least 20,000 rollout tokens of headroom above the measured maximum.

| Candidate | Prompt Ceiling | Primary Requests | Provider Calls | Transport-inclusive Invocations | Rollout Ceiling | Minimum Headroom |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| S0 capacity only | 100,000 | 20 | 22 | 23 | 1,300,000 | 23,532 |
| S1 lossless compact | 60,000 | 20 | 22 | 23 | 1,060,000 | 22,916 |

Both candidates statically qualify all 48 paths. S0 shows that capacity-only scaling is a valid
scientific control and that the role tasks themselves are not rejected. S1 preserves all
semantic and authority surfaces while requiring no larger Prompt ceiling and a lower rollout
ceiling.

The registered selection order is:

1. all frozen role paths qualify;
2. Candidate authority and reversible Commit are preserved;
3. model outcomes are not used;
4. select a statically Pareto-dominant resource vector;
5. use structural simplicity only as a tie-break.

S1 has equal request and call limits and strictly lower Prompt and rollout ceilings, so it is
selected by rule 4. No S2 or later optimization Candidate is authorized.

## Role-Support Scalability

v26.130 adds Role-support scalability as an algorithm-instance support admission condition. For
every frozen role task and registered path it requires:

```text
semantics preserved
authority preserved
maximum Prompt <= selected Prompt bound
Primary requests <= selected request bound
Provider calls <= selected call bound
static complete-path bound <= selected rollout bound with frozen headroom
```

All 48 paths satisfy this condition under S1. This does not add an Energy, Reward, Novelty, or
Contribution term. It does not update top-level VTDO theory and does not measure Capability,
Reachability, Quotient State, Contribution, or Novelty.

## Destructive Controls And Reproducibility

All 18 destructive controls fail closed with zero Provider calls and zero Role Jobs. They include
Population replacement, path deletion, failed state or Candidate reconstruction, a non-smaller
compact Prompt, Candidate deletion, model-outcome-based selection, insufficient Prompt/request/
call/rollout bounds, removal of the S1 protocol, replacement of S1 by S0 after selection, an
additional Candidate, a Stage 2 Provider route, and Provider authorization.

Formal and independent builds produce all eleven outputs byte for byte. Focused Pytest passes
2/2 in 45.45 seconds; the selected v26.122-v26.130 adjacent regression passes 11/11 in 187.84
seconds. Focused Ruff and Mypy pass. Package-wide Mypy checks 447 source files and retains exactly
three diagnostics in two byte-frozen predecessor implementations: one historical v26.70 local
annotation and two v26.129 annotations. The v26.130 implementation contributes zero package-wide
diagnostics; changing either predecessor would break immutable transitive replay.

## Authoritative Identities

- report:
  `finance_v26_role_kernel_scalability_design_report:e0747bb67e14e4850a16447d0a3bcee7a81003352bfd59d9d5bfa3af2fd5949a`;
- full complexity Census:
  `finance_v26_role_support_complexity_census:d56c84e66db54f2bf44c2df82bdf3e8776b072da3c6882e59d7476b0827122d4`;
- compact projection protocol:
  `finance_v26_compact_projection_protocol:954144af0838a31f9e164d3b83a470b7851c096de754096b78388fea98dfdf1e`;
- S0:
  `finance_v26_role_scalability_candidate:69a7cd3935286d189a9869591160a8b88cb424d07c548f56fef4c5c81db9975d`;
- S1:
  `finance_v26_role_scalability_candidate:914a3b163ae93d7dc8577fed89c53a63071cc2aaab4173e204cd31dd5ad3541b`;
- selection:
  `finance_v26_scalability_selection:4329d62464c254ca811aa17dd617e20705111abae3a8eb37e37f52463e4e9a4b`;
- Role-support scalability Contract:
  `finance_v26_role_support_scalability_contract:07679af22f286b51e522e00618c1907f936a3708f09aa816443001444d5350fa`;
- transition:
  `finance_v26_role_scalability_transition:feabd18ea7340f6340bc47003d1992a7719fd8daa356cca686946eadb82d8556`.

## Permitted Transition

The only permitted transition is:

```text
fresh_role_scalable_kernel_taskpackage_contract_manifest_and_runner_preflight_only
```

The successor must preserve the exact Capability and Reachability source Populations, bind one
fresh Role-scalable Kernel to the selected S1 protocol and resource values, create fresh
TaskPackage, Path, Contract, Manifest, Job, Runner, execution, and report identities, and pass a
complete credential-free Runner preflight before any Provider call.

Provider calls, Capability or Reachability execution, State Mapping, historical rerun or
reclassification, task deletion or substitution, Tier change, an additional Scalability
Candidate, model-outcome-based design selection, training, release, and production Contribution
remain forbidden.
