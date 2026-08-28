# Finance v26.168 Executable Capability Depth Rematerialization And Static Reaudit

Audit date: 2026-08-28

## Decision

Finance v26.168 consumes only the externally authorized transition:

```text
capability_observation_executable_depth_rematerialization_and_static_reaudit_only
```

The external joint review is bound at exactly 25,940 bytes and SHA-256
`89ed58d566df56edc1dc54087cb722dc5a485ee48068a543aa15d79850a10dbb`. The stage
reads no credential, constructs no Provider client, makes zero Stage 1 or Stage 2 Provider calls,
uses zero GPU jobs, creates zero Development Jobs, and performs zero Mapper, State, Contribution,
or VTDO operations.

The static result passes. It replaces only the prospective v26.167 executable-depth design and
does not rewrite a v26.167 artifact. v26.167 remains immutable evidence for a metadata-ladder
static prototype. Its stale `capability_observation_development_runner_preflight_only`
authorization is blocked rather than consumed.

v26.168 establishes a content-addressed executable depth construct for 64 local task variants.
It does not preflight a model Runner, expose a role task to a model, measure model behavior,
estimate an empirical boundary, open Confirmation, map a State, or authorize VTDO or training.

## Independent v26.167 Defect Reproduction

Before selecting a v26.168 source, the stage binds and replays the complete v26.167 formal
directory. It then independently rebuilds the sixteen v26.167 source groups and invokes the
production `compile_operational_witness(..., strategy="structured_direct")` path.

The exact reproduced partition is:

```text
v26.167 source groups                              16
v26.167 static variants                            64
actual full-valid production Witness variants      48
actual failed production Witness variants          16
failed Semantic Reconciliation variants            16
```

All sixteen Reconciliation failures include the missing consumed-normalization-reference
boundary identified by the review. Within every v26.167 matched group, D0-D3 retain one unique
Program hash, one Tool set, and one production Witness sequence. This reproduction changes no
v26.167 report, label, identity, static Gate, or artifact byte. It narrows the interpretation:
v26.167 proved metadata, grouping, exposure, and identity management, but not executable depth.

## Pre-Outcome Source Construction

Source selection reads the frozen v26.163 70-task frame and prior exposed source Population
before loading any model outcome. Exactly seven eligible unexposed sources remain in each target
capability. A fixed v26.168 salt selects:

```text
Development:          two old Easy sources per capability       8 groups
sealed Confirmation:  two old Frontier sources per capability   8 groups
total:                                                        16 groups
```

The sixteen source bindings have zero overlap on every registered freshness channel: task,
source task, Evidence, Evidence Version, source record, core semantic signature, task semantic
signature, and mechanism-instance signature. Selection uses no v26.164-v26.166 result, current
27-Cell support set, Verifier passability, resource observation, or model output.

Each selected source is rematerialized into a low-nuisance Finance core from its first real
Evidence-only Program node. The core contains exactly two Evidence items, one Program node, and
zero Program edges. It is executed through `TaskProgramExecutor`, independently replayed through
`TaskProgramOracleVerifier`, compiled through the existing Role task compiler, and closed by the
production operational Witness compiler. A changed answer, Evidence, Program, Tool environment,
TaskPackage, or Verifier binding changes or invalidates the core identity.

## Executable Depth Graphs

Every variant owns an `ExecutableCapabilityDepthGraph` containing typed public States, visible
model-owned Candidates, one exact reference Candidate per nonterminal State, typed Transitions,
required mechanism-event multiplicities, and one answer-ready terminal. State, Candidate,
Transition, Graph, Witness, target-load, prompt-binding, and package identities are separately
content-addressed.

The three-slot maximum skeleton remains fixed. Inactive slots are executable inert States with
one visible legal action; they are not deleted. Active slots create the following real Runtime
burdens:

| Capability | D0 | D1 | D2 | D3 |
| --- | --- | --- | --- | --- |
| Context-conditioned Action | 1 decision, 2 Candidates | 1 decision, 3 Candidates | 2 dependent decisions | 3 dependent decisions |
| Semantic Reconciliation | 1 nonidentity normalization, 1 consumption | 1 normalization, 2 consumptions | 2 normalizations, 3 consumptions | 3 normalizations, 6 consumptions |
| Failure Recovery | 1 typed failure/revision | 1 failure with more retry ambiguity | 2 typed failure/revision slots | 3 typed failure/revision slots |
| State-dependent Stopping | 1 checkpoint and visible continuation | 1 delayed-readiness checkpoint | 2 checkpoints | 3 checkpoints |

The actual graph and reference-path sizes are:

| Capability | Depth | States | Candidates | Reference calls | Computed load |
| --- | --- | ---: | ---: | ---: | ---: |
| Context | D0 / D1 / D2 / D3 | 4 / 4 / 4 / 4 | 4 / 5 / 6 / 9 | 3 / 3 / 3 / 3 | 2 / 4 / 8 / 14 |
| Reconciliation | D0 / D1 / D2 / D3 | 5 / 6 / 7 / 10 | 6 / 8 / 11 / 18 | 4 / 5 / 6 / 9 | 6 / 10 / 16 / 30 |
| Recovery | D0 / D1 / D2 / D3 | 5 / 5 / 6 / 7 | 6 / 7 / 11 / 18 | 4 / 4 / 5 / 6 | 5 / 6 / 12 / 21 |
| Stopping | D0 / D1 / D2 / D3 | 5 / 5 / 5 / 5 | 6 / 7 / 9 / 11 | 4 / 4 / 4 / 4 | 5 / 7 / 11 / 16 |

These load totals are sums of capability-specific dimensions computed from the final graph and
Runtime Witness. No declared v26.167 `primary_load`, old Tier, source Program size, or empirical
success enters the calculation. Totals are constructively ordered only within a capability and
are not a common cross-capability score.

## Variant-Local Verification

Every one of the 64 variants separately executes all four local verification surfaces:

```text
production compile_operational_witness
TaskProgram execution plus independent TaskProgramOracleVerifier
CapabilityDepthRuntime reference replay
mechanism event and terminal Verifier
```

The actual returned `BoundPublicExecutableWitness` and `ProgramVerification` are embedded in the
variant package and bound into its executable signature. They are not inherited booleans from a
group-level core. An empty-directory test instruments the variant-local verification entry and
observes exactly 64 invocations.

All 64 operational Witnesses, 64 Program Verifications, 64 depth Runtime Witnesses, and 64
mechanism verifications pass. All 16 Reconciliation variants emit and consume every normalized
reference; their consumed-event counts are recomputed from exact Runtime Observations and close
at 1, 2, 3, and 6 for D0-D3.

## Target-Matched Necessity

Mechanism necessity is no longer inferred from a metadata key. Each of the 64 production graphs
receives two target-matched counterfactuals:

1. Delete the first required target action while retaining its event Contract. The production
   Graph validator rejects the missing reference action.
2. Execute the visible target bypass Candidate, continue through the unchanged graph, and rerun
   mechanism event verification. The Runtime reaches its typed path without the exact required
   mechanism-event vector.

All 128 counterfactuals fail full validity and all 64 variants pass the paired necessity rule.
No Candidate is Host-selected, inserted, repaired, or hidden for this audit.

## Computed Nuisance And D0 Envelope

Nuisance is recomputed from bound operational records, environments, Witnesses, and rendered
prompts. Within every matched group, all four depth variants have one exact nuisance measurement
identity and one exact prompt-byte burden. Across all sixteen groups the observed frozen ranges
are:

| Nuisance dimension | Minimum | Maximum |
| --- | ---: | ---: |
| Evidence count | 2 | 2 |
| Program nodes | 1 | 1 |
| Program edges | 0 | 0 |
| Tool count | 3 | 4 |
| non-target Candidate count | 0 | 1 |
| verification obligations | 2 | 4 |
| Prompt bytes | 24,736 | 42,525 |
| base reference calls | 4 | 6 |
| resource token ceiling | 1,120,000 | 1,120,000 |

The Development `ObservabilityFloorNuisanceEnvelope` admits exactly the 32 Development variants.
It permits at most two Evidence items, one Program node, zero Program edges, six Tools, two
non-target Candidates, four verification obligations, 60,000 Prompt bytes, six base calls, and
the unchanged 1.12M token ceiling. Unrelated recovery and retrieval branching remain zero.
No old Hard source enters Development.

## Fixed Development Condition

The future condition is named `fixed_development_generation_condition`. Its implementation path
remains `structured_direct`, but v26.168 does not call it capability-neutral. The static prompt
binding reconstructs every Development Candidate set and Transition graph with zero condition
cue injection and zero static reference-path exposure. Actual Runner prompt consumption and
behavioral noninterference remain unmeasured and must be tested in the authorized successor.

## Boundary Selection Totality

The exact algorithm accepts two groups by four depths and a registered threshold/denominator
pair. It validates all counts before classification. The only pairs are Development 2/6 and
Confirmation 3/8. For either pair:

- a within-group unsupported-to-supported reversal is `nonmonotonic_or_confounded`;
- both D0 unsupported is `below_observation_floor`;
- both D3 supported is `above_observation_ceiling`;
- any group disagreement is `nonmonotonic_or_confounded`;
- exactly one shared supported-to-unsupported adjacent pair with every later depth unsupported is
  `boundary_bracketed`;
- every other pattern is `nonmonotonic_or_confounded`.

All 256 Boolean two-group-by-four-depth support patterns are classified under each threshold,
for 512/512 total protocol cases. Eight threshold equality and neighboring-value controls pass.
No post-outcome interpretation branch remains.

## Confirmation Isolation

The 32 Confirmation packages are written to an independent sealed artifact Root. The Development
Root and `BuildProducts` contain only a `SealedConfirmationReceipt`: sealed Catalog identity,
content-root SHA-256, byte count, and exposure policy. They contain no Confirmation payload or
payload path. The prospective Development transition accepts the receipt identity and explicitly
forbids Confirmation payload loading.

This is an artifact-interface isolation claim, not a claim that a repository administrator or
the static construction process cannot inspect the separate Root. The Host static build creates
and audits both roots; a future Development Runner may receive only the Development Catalog and
receipt.

## Source Closure And Production Mutations

An AST-resolved static import closure begins at all four v26.168 implementation modules and binds
294 `trusted_synthesis` source files. It includes the Role compiler, operation builder, production
Witness compiler, source-freshness helpers, TaskProgram executor and Verifier, Runtime models,
and all their reachable local imports. Unresolved local imports are zero.

Thirty production-object mutations fail closed. They traverse Pydantic or Runtime validators for
the Boundary Contract, Development Catalog, executable Graph, Finance core, nuisance measurement,
Role TaskPackage, operational Witness, prompt binding, Runtime Observation and trace, sealed
receipt, source root, TaskProgram, task Verifier binding, and depth Verifier Contract. The set
includes target Candidate deletion/rebinding, missing Transition target, changed reference
Candidate, postterminal action, nonvisible action, altered Program output node, rebound
TaskPackage, changed Verifier DAG hash, deleted operational Witness step, changed depth event
count, and disclosed sealed path. Abstract summary-dictionary mutations are zero.

## Static Gates

All 22 noncompensatory Gates pass:

```text
Boundary algorithm totality                 512/512
Computed nuisance stability                   64/64
Computed target-load monotonicity              16/16
Confirmation access isolation                   1/1
D0 real mechanism                              16/16
Development floor envelope                     32/32
Executable Candidate delta                     16/16
Executable Graph delta                         16/16
Executable Transition delta                    16/16
Fixed-condition static noninterference         32/32
Historical v26.167 freeze                        1/1
Low-nuisance operational Witness               64/64
Mechanism event multiplicity                   64/64
Mechanism necessity                            64/64
Provider zero                                    1/1
Public depth Witness                           64/64
Reconciliation reference consumption           16/16
Source capacity and freshness                  16/16
Stale preflight block                            1/1
TaskProgram Verifier                           64/64
Transitive source closure                     294/294
Typed Runtime terminal policy                  64/64
```

## Reproducibility And Identities

The Development Root contains 19 files and 1,912,392 bytes. The separate sealed Confirmation Root
contains one file and 1,629,452 bytes. The formal and independently rebuilt roots match every
filename and every byte. Focused Pytest passes 6/6 in 10.81 seconds; the adjacent
v26.167-v26.168 suite passes 10/10 in 12.96 seconds. Focused PyCompile, Ruff, and Mypy pass.
Provider, Stage 2 Provider, GPU, empirical Assignment, State, Mapper, Contribution, VTDO,
Development Job, and historical mutation counts are zero.

The preliminary v1 and v2 Roots remain immutable. Package-wide Mypy found one v26.168 local
variable inference in v1 from reusing `channels` for set-valued and tuple-valued mappings. The
type-complete v2 source gives those values separate names and changes only implementation-bound
run/output identities; source selection and every scientific value remain unchanged.

Package-wide `trusted_data_synthesis` Ruff then found one local E501 line after the v2
source-bound Root was materialized. The authoritative v3 wraps only that expression and changes
run/output identities. Source selection, cores, Packages, Graphs, Witnesses, Verifiers, loads,
nuisance, counterfactuals, Gates, and thresholds do not change. Fourteen of nineteen main files
are byte-identical across v2/v3, and the sealed Catalog is byte-identical. Only the transitive
source root, source replay, source-bound static audit, run-bound transition, and top-level report
change. Package-wide Mypy checks 525 source files and retains only four pre-existing diagnostics,
with zero v26.168 diagnostics. Package-wide `trusted_data_synthesis` Ruff passes. The v3 chain
below is authoritative.

The authoritative identities are:

- report:
  `finance_v26_executable_depth_rematerialization_report:fec334481435422529ccd90ce2b9df6f4de758448e25b2c0bf8f8123e4457171`;
- external authorization:
  `finance_v26_executable_depth_external_audit_authorization:25efb6f80989a283905b86301a1c8e1f13ba0fb5fa8bd2a94481a402d4b96032`;
- transitive source root:
  `finance_v26_executable_depth_transitive_source_root:39fec7ae44243f37025636ce7241b0da2ed2cd048703f3dff3b87e9faa30f01b`;
- source replay:
  `finance_v26_executable_depth_source_replay:2de5aebb9cfe4a6727165ae517fbdb4fc68e94973a2ddf63cb8f42365e762cf2`;
- v26.167 defect audit:
  `finance_v26_v167_executable_depth_defect_audit:1cf3eb3feba2e56faaa566ec7befd8827c0cb1b95b2748322a4be64312260ead`;
- source capacity audit:
  `finance_v26_executable_depth_source_capacity_audit:2fdb8f0c77849173025f73f0465a05564261a8fabd78c0a142df35db915fbfc7`;
- D0 nuisance envelope:
  `observability_floor_nuisance_envelope:8eb3386111f2268ef7ad06d2418b089f776e6c46fa95596e8470a12852b59ce7`;
- Development Catalog:
  `finance_v26_development_executable_depth_catalog:c8405b5509c74bc51509114349d28e04da5194e2f256ef9355723db3f95a93aa`;
- sealed Confirmation Catalog:
  `finance_v26_confirmation_executable_depth_catalog:c3a5930b7a4ddd788b8977240ae8f1b20d229aeaf5e0f7b2e2acc2799a74789f`;
- sealed Confirmation receipt:
  `finance_v26_sealed_confirmation_executable_depth_receipt:641c1472f4a2565106f4029407d337aac5440fff7f4eacbefee64eac18c1682b`;
- fixed Development condition:
  `fixed_development_generation_condition:9b504d79f748d94b2b44fa8cd80ae48ed2834dfbb5be9121db5d791e0450b761`;
- static condition noninterference:
  `finance_v26_target_capability_noninterference_audit:3eff66324b4d4a579e7cf43d7efb2c07bfbce63529848d657ad7bb49f990f708`;
- Boundary Algorithm Contract:
  `capability_boundary_selection_algorithm_contract:46e7ba7796fe4e3d058a232df8139bd8eaeb0b0917db6f515d9ce8e0301cbd7a`;
- Boundary totality audit:
  `finance_v26_boundary_algorithm_totality_audit:c943b80b762ff3f34b6b59be6d5e0f32bdcabf4c24514b7e00aaf4f290d1d744`;
- Mechanism Necessity Catalog:
  `finance_v26_executable_depth_mechanism_necessity_catalog:bf8f11b3125a12bdea499fa1a6edb133a5720312d78fa8fcbfc562b12f1024c1`;
- nuisance recomputation audit:
  `finance_v26_executable_depth_nuisance_recomputation_audit:8acec520f4f012fb1e3d177d1446d757874dfa39500ad717dc36abe11094e9ab`;
- static audit:
  `finance_v26_executable_depth_static_audit:5f1cb8b2b7448b85db7f68ee91968425a3e7def7b825a6443faf702fc94301f3`;
- production destructive audit:
  `finance_v26_executable_depth_production_destructive_audit:eb6384c983af1749a7cb289ade8791faca2d71933c2e6f90497c6ac75aadf30e`;
- transition:
  `finance_v26_executable_depth_transition:ff485fd462f7e0c93f695b6949e55aa48bae4726d343d7ee19b21336bb815686`.

## Transition

The only permitted transition is:

```text
capability_observation_executable_depth_development_runner_preflight_only
```

The successor may perform only a credential-free Runner preflight over the exact 32 Development
packages and may materialize only the exact future 192-Job Development Manifest. It must consume
the executable Graph, variant-local operational Witness and TaskProgram verification,
capability-specific event Contract, computed target load, exact nuisance measurement, fixed
Development condition, 2/6 threshold, terminal policy, model/Thinking profile, Grammar, bounded
generation Policy, resource Contract, and sealed receipt. It must independently prove prompt and
Runner consumption without changing any source, core, depth graph, Candidate, threshold, or
Compiler output.

Provider execution, Confirmation payload loading or execution, source reselection, threshold
tuning, depth or graph repair, v26.167 rewrite, current-27-Cell selection, historical
reclassification, Mapper, State Assignment, frequency, Contribution, VTDO, Student visibility,
training, release, and production remain forbidden.
