# Finance v26.170 Public Semantic Sufficiency And Task Execution Hardening

Audit date: 2026-08-28

## Decision

Finance v26.170 consumed only:

```text
capability_observation_public_semantic_sufficiency_and_task_execution_hardening_only
```

The external joint report is bound at exactly 25,632 bytes and SHA-256
`1dd7e35803ce73bfd7d9be3517399c6e416d6aa4f7504276fdad38ceb6131d85`.
Credential lookup, Provider-client construction, Stage 1 Provider calls, Stage 2 Provider calls,
Development Jobs, sealed Confirmation payload access, GPU jobs, Mapper calls, State Assignment,
Contribution, and VTDO are zero.

The stage accepts the external decision that v26.169 repaired the Host/Public split, current-State
projection, Candidate presentation shape, successor-state divergence, mechanism preconditions,
task-level counterfactuals, and most parent rehash checks. It does not rewrite or reclassify any
v26.169 artifact. It independently reproduces the remaining blockers before replacing the stale
Runner-preflight authorization.

The strongest supported result is:

```text
public_semantic_sufficiency_and_real_task_execution_static_gate_passed
```

This is a credential-free static and local-execution result. It is not evidence that the model
can read the new Prompt, choose the public action, complete a rollout, or satisfy an empirical
capability boundary.

## Reproduced v26.169 Blockers

All seventeen files in the authoritative v26.169 v2 Root are rebound with zero mutation. The
v26.168 sealed Confirmation Root is not read. The exact v26.169 diagnostic is:

```text
Development Packages                                      32
Finance Cores                                               8
original public instructions retained                    0/8
registered alias values retained                        0/23
registered period values retained                       0/14
resolution-rule semantic values retained               0/101
unique Public Task hashes                                  5
Action States                                             210
reference parameters externally grounded                   8
no Candidate parameter externally grounded                202
indexed-token States                                       68
reference index lexicographically minimum                  68
SET_EXPECTED_RESULT reference effects                      32
nonreference alternatives                                 420
task-invalid alternatives                                 420
TERMINATE_INVALID alternatives                            404
SET_ALTERNATE_RESULT effects                              404
rehashed crossed Public Task accepted                    true
future six-replica order varied                         false
```

The resolution-rule denominator is computed, not declared. Within each Finance Core, non-null
constraint values are deduplicated and then the eight per-Core counts are summed. This produces
exactly 101 registered public semantic values.

The D0 target/non-target choice-State partition is retained exactly:

```text
Context-conditioned Action                                 1 / 3
Semantic Reconciliation                                    3 / 3
Failure Recovery                                            2 / 3
State-dependent Stopping                                    1 / 4
```

These values remain a diagnostic of the frozen v26.169 design. They are not historical outcome
reclassification.

## Public Semantic Projection

The new `PublicSemanticTask` is reconstructed from each exact v26.168 low-nuisance Finance Core.
It retains:

```text
exact public instruction
allowed Tools
answer type and required fields
public aliases and period labels
source count
two public Finance records and their semantic fields
public resolution Rules and non-null constraint values
operation roles, kinds, Tools, inputs, dependencies, outputs, and completion status
public operator descriptions and output-field contracts
terminal Operation semantics
public completion and stop-readiness rules
```

The public Finance records include subject, period, frequency, metric definition and predicate,
source authority and source ID, time basis, and public payload semantics. Their handles are
content-derived from those public fields. Resolution Rule, Operation, and Operation-output handles
are similarly content-derived and appear only with their full public definitions.

The projection excludes Gold Evidence identities, Evidence Version identities, source-record
identities, the source Program identity, the source Program operator, the expected result,
reference Candidate, correct action, future State graph, required event vector, capability family,
and depth label. `program_operator_id` is explicitly forbidden on the model-visible surface.

The correct public operator is not copied from the Oracle Program. A registered public transform
intersects the terminal Operation's allowed operators with the exact public answer-field contract.
This uniquely derives `compare` for the two Context Cores and the other compare tasks, and
`difference` for the two Reconciliation Cores. The independent audit implements the same rule
separately.

The exact retention result is:

```text
exact public instructions                                  8/8
registered alias values                                  23/23
registered period values                                 14/14
resolution-rule semantic values                         101/101
unique Public Task hashes                                  8/8
model-visible Host leakage                                   0
```

## Public-Only Constructibility

There are 80 target Decision States across 32 Development Packages. The production selector
receives only one `PublicSemanticPrompt`, reads the public Task, current public State, and displayed
Candidate Operations, and returns one displayed action ID. It does not receive a Host Graph,
reference Candidate ID, semantic-choice hash, expected result, Candidate ordinal, source Oracle,
capability, or depth.

An independent selector separately implements public Rule resolution, output consumption,
selector revision, readiness, stopping, scope, projection, record, and operator semantics. It also
returns only the action ID. Host-side audit code maps that ID back to the displayed public Operation
after selection; the selector itself never reads or returns a semantic-choice hash.

The constructibility result is:

```text
production unique public-only Choices                    80/80
independent unique public-only Choices                   80/80
independent six-replica Choice matches                  480/480
action-ID or ordinal dependencies                            0
opaque-hash guess States                                     0
```

Content handles are not treated as opaque clues: every used record, Rule, Operation, and output
handle appears beside its complete public semantic object, and the selectors resolve against those
objects rather than handle order.

## Candidate Grounding

Each target State has exactly three displayed semantic Choices. Every argument scalar must occur
in the public Task, current public State, or the registered public operator catalog. Tool and
Decision-kind compatibility are checked independently. The exact result is:

```text
target Decision States                                      80
semantic Candidates                                         240
publicly grounded Candidates                            240/240
ungrounded Candidates                                         0
indexed-shortcut Candidates                                   0
random peer-hash Candidates                                   0
```

The public operator catalog keys are explicitly admitted as registered transform values. Arbitrary
JSON field names are not admitted. This keeps `compare`, `difference`, and `growth` grounded without
turning schema labels into a general value oracle.

## Real Task Execution

The Host no longer assigns `SET_EXPECTED_RESULT` or `SET_ALTERNATE_RESULT`. For each Package, the
selected public operator and selected public record handles compile a real one-node `TaskProgram`.
`TaskProgramExecutor` executes that Program against the two exact Evidence objects. The production
`TaskProgramOracleVerifier` then verifies the computed node output against the frozen source
Program. The Host records public contract checks and mechanism qualification but never inserts a
Finance result.

The exact baseline result is:

```text
Packages                                                   32
TaskProgramExecutor invocations                            32
TaskProgramOracleVerifier invocations                      32
Program-valid baselines                                 32/32
Base-valid baselines                                    32/32
Mechanism-qualified baselines                           32/32
Qualified-valid baselines                               32/32
v26.168 independently computed output matches           32/32
SET_EXPECTED_RESULT effects                                  0
SET_ALTERNATE_RESULT effects                                 0
Host-preclassified alternatives                              0
Host result assignments                                      0
```

These local executions establish constructibility and task-contract behavior. They do not measure
model behavior.

## Isolated Depth And Increment Necessity

Every D0 Package contains one real target decision and deterministic non-target execution. Each
adjacent depth adds exactly one target component while retaining the same public Finance Task.
The isolated target loads are:

```text
Depth                                        D0 / D1 / D2 / D3
target decisions per Package                  1 /  2 /  3 /  4
Packages per depth                            8 /  8 /  8 /  8
total target States                           8 / 16 / 24 / 32
```

The D0 target/non-target partition becomes `1/0` for each of Context-conditioned Action, Semantic
Reconciliation, Failure Recovery, and State-dependent Stopping. Across all 32 Packages,
non-target choice States are zero.

For every one of 24 adjacent group-depth increments, both nonreference semantic Choices of the
new component are executed through the exact target-depth Runtime. All 48 results are Base-invalid,
Mechanism-unqualified, and Qualified-invalid while retaining `result_assigned_by_host=false`.
This proves registered task-level necessity for each added component under the frozen local
Runtime. It does not prove monotonic model difficulty or a causal effect of depth on model success.

## Six-Replica Presentation

A pre-outcome fixed salt binds Candidate presentation to:

```text
variant x replica x state
```

Every target State has six presentations. Each of its three semantic Choices appears in each of
the three positions exactly twice. Semantic payload is invariant across replicas; only action ID,
order, presentation index, and equal-length padding change.

```text
target States                                                80
replicas per State                                             6
presentations                                                480
displayed Candidates                                       1,440
per-State position imbalances                                  0
semantic payload mismatches                                    0
action-ID collisions                                           0
```

This removes fixed per-Package ordering before a future six-rollout Manifest exists. No Job is
materialized in v26.170.

## Parent Reconstruction

Every Package binds the exact Finance Core, source public Task hash, source public Evidence
semantic hash, projected public Task hash, Projection Contract, Prompts, replica presentations,
target load, and local execution.

The Catalog validator reconstructs the `PublicSemanticTask` from the exact bound Finance Core and
requires canonical-byte equality. Runtime Pydantic-object equality is intentionally not used,
because serialization may change internal container representation while preserving exact
canonical content.

Thirty-two destructive controls each mutate exactly one designated Package's public instruction,
recompute that Package's Task, all Prompt and replica hashes, parent binding, target load, Package
artifact identity, Group identity, and Catalog identity, and then invoke the same reconstruction
validator used by the Catalog. The result is:

```text
semantic Task mutations                                     32
child identity recomputations                               32
Package identity recomputations                             32
Group identity recomputations                               32
Catalog identity recomputations                             32
exact-Core reconstruction rejections                        32
accepted crossed public Tasks                                0
```

## Preliminary v1-v2 And Authoritative v3

The preliminary v1 Root remains immutable. It passed the scientific Gates and all five focused
tests, but its parent-binding destructive audit kept Group Task equality by rematerializing all
four peer Packages in each designated trial. The reported count of 32 designated chains was
therefore not an exact count of Package object reconstructions.

The preliminary v2 changes only this destructive-control protocol and implementation-bound
schema, run, source-root, report, and artifact identities. Each v2 trial mutates exactly one
Package and uses the Catalog's extracted exact-Core reconstruction validator after recomputing the
aggregate identities. A final strict interface review then found that v2 still projected
`program_input_record_handles`, whose ordered tuple came from the source Oracle Program. Although
both records were public, a public-only selector was not permitted to consume an Oracle-derived
selection tuple.

The authoritative v3 removes that field and never passes the source Program into public Task
projection. Required record handles are derived recursively from public query resolution Rules,
public terminal input symbols, and public intermediate Operation output lineage. The independent
selector implements that derivation separately. The Projection Contract now freezes source Oracle
Program-input exposure as false, and the Sufficiency Audit freezes source Oracle dependency count
at zero. Finance Cores, 32-Package denominator, 80 States, 240 Candidates, 32 baseline executions,
48 increment counterfactuals, 480 presentations, all pass/fail counts, and the transition semantics
are unchanged. None of the three builds makes a Provider call or creates an empirical row.

## Reproducibility And Limits

The authoritative v3 transitive source Root starts from all four v26.170 implementation modules,
closes 302 local `trusted_synthesis` files, and has zero unresolved imports. The formal Root has
18 files and 8,033,777 bytes. Its report SHA-256 is
`404c3291547ad62267c5c148f70056980c9dd937f968ea13681b931d8db66f9c`.

Focused Pytest passes 5/5 in 24.74 seconds, including an empty-directory byte-identical rebuild of
all eighteen files. The adjacent v26.169-v26.170 regression passes 10/10 in 26.79 seconds.
Focused PyCompile, Ruff check/format, and no-cache Mypy pass. Package-wide Ruff passes. Package-
wide Mypy checks 533 source files and retains only the four pre-existing v26.70, v26.129, and
byte-frozen v26.154 diagnostics, with zero v26.170 diagnostics. No test or build reads a
credential or constructs a Provider client.

The result does not establish model readability, model success, an empirical capability boundary,
success monotonicity, Confirmation status, frequency, State probability, Contribution, VTDO,
Student visibility, training value, release quality, or production suitability. A future Runner
preflight must bind the exact authoritative v3 Catalog and may not reinterpret this static result
as a model outcome.

## Authoritative Identities

- report:
  `finance_v26_public_semantic_hardening_report:5b8fb064cdf65211db3a1b35aecf7927ec92a72d80f428ac9f878b7ce0cfc3e1`;
- external authorization:
  `finance_v26_public_semantic_external_audit_authorization:8496818b13af8aa11d1fd80e4eb5861dee7a766b7ddbe3342a4a8421169afe2f`;
- transitive source Root:
  `finance_v26_public_semantic_transitive_source_root:7500b642d64aa1599d580c28653f67b5e28c2e1011bc8841fdf4fa84b188043d`;
- predecessor integrity:
  `finance_v26_public_semantic_predecessor_integrity:a5483efc553ee23b9e28e11cfee4b98a39d46e3d648c753e1f172b506c9b9ba6`;
- v26.169 defect audit:
  `finance_v26_v169_public_semantic_execution_defect_audit:1d9388f61e67241fef400d05351d22cbb0235c303d13d265766dd1e964cbfb5c`;
- Public Semantic Projection Contract:
  `public_semantic_projection_contract:a1dbc27c5a79518fcade87b859398eca08e034daef8a10585699b638f3ee02d9`;
- Replica Presentation Policy:
  `public_semantic_replica_presentation_policy:c7751129fad16f76250f7ba574dc949d3364b89b240e8c46488a57c60e866952`;
- Development Catalog:
  `finance_v26_public_semantic_development_catalog:bc6b9cb9adfbe2026f77df8c24d181176ff09bf3cf06226a1336bc43ecc67cdb`;
- semantic sufficiency audit:
  `finance_v26_public_semantic_sufficiency_audit:754c11cda9055905f9f0a1bf9a6f3f7e73040419979e8d67531278274b97ae5e`;
- Candidate Grounding Audit:
  `finance_v26_public_candidate_grounding_audit:b3809feaa1a409ad8b4834d4fec4f6f4388fec1e37fcafacd24a4957f6ea59dd`;
- real Program execution audit:
  `finance_v26_real_program_execution_audit:790f34c771825403540c2968e7dd0a81911276c6c08c412154d4e69006d54618`;
- target isolation audit:
  `finance_v26_target_isolation_audit:d9d3803dfe80ed9197915af4b5f1f7e793881e48c41b6614943ed455ced42269`;
- Depth Increment Necessity Catalog:
  `depth_increment_necessity_catalog:5f71490a0846fd51f243b7f8a70acb065927a2227f8110bc8250933b76881c2a`;
- Prompt Parent Binding Audit:
  `finance_v26_public_task_parent_binding_audit:37c5b56b07bc0fdaca599dc78d8dd188c09d9355a0f40932f578b7e8f533bc78`;
- Replica Presentation Audit:
  `finance_v26_replica_presentation_audit:7e700fa9f3c381e973164a58ae82210f8a73a116d879dcde61345bc15fa8208c`;
- static audit:
  `finance_v26_public_semantic_static_audit:c6aad7162e697f65696a79e748a358a4a9c0a90f6e10f711717c4d926f8818c7`;
- transition:
  `finance_v26_public_semantic_transition:02fa435f910d1926bd2b6d14ac0dd03d6261de4cf0ff0abaea31e27db0709caf`.

## Only Permitted Transition

```text
capability_observation_public_semantic_execution_development_runner_preflight_only
```

The successor may materialize only the exact future 192-Job Development Manifest and perform a
credential-free Runner preflight over the authoritative v3 public semantic Development Catalog,
exact Finance Cores, isolated D0-D3 target components, public-only selector interface, Candidate
grounding, six-replica presentation policy, real TaskProgram execution path, fixed generation
condition, task and mechanism Verifiers, nuisance, model/Thinking, Grammar, Policy, resource,
threshold, terminal, and sealed-receipt bindings.

Provider execution, Development outcomes, Confirmation payload loading or execution, source or
public semantic change, target-component change, Candidate change, presentation-salt change,
threshold tuning, historical rewrite or reclassification, Mapper, State, frequency, Contribution,
VTDO, Student visibility, training, release, and production remain forbidden.

That transition has now been superseded without Runner execution by the external v26.171
validity-separation, presentation-deleak, and causal-component reaudit. Every v26.170 artifact,
identity, and static result remains immutable. The current authorization is the credential-free
Development Runner preflight over the fresh v26.171 validity-separated Catalog. See
`docs/finance_v26_171_validity_separation_presentation_deleak_and_causal_component_reaudit.md`.
