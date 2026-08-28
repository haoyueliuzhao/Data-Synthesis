# Finance v26.169 Public Projection And Causal Depth Runtime Hardening

Audit date: 2026-08-28

## Decision

Finance v26.169 consumes only the externally authorized transition:

```text
capability_observation_public_projection_and_causal_depth_runtime_hardening_only
```

The bound review input is exactly 27,021 bytes with SHA-256
`6105461d1c58f507ee5227f3b8f6867e020dedec828b7687befe1eddb108bb4e`.
Credential lookup, Provider client construction, Stage 1 and Stage 2 Provider calls, Development
Jobs, sealed Confirmation payload access, Mapper calls, VTDO rows, and GPU Jobs are zero.

The stage preserves every v26.168 byte and does not reinterpret its static pass labels. It first
reproduces the externally reported v26.168 defects, then creates a fresh Development-only causal
depth identity chain. The v26.168 executable-depth Catalog remains historical static evidence;
its old Runner-preflight authorization is blocked because its model-visible graph and Runtime do
not implement the causal object required by the external review.

The v26.169 chain passes all twenty-two static Gates. It restores only the credential-free
Development Runner-preflight transition. It is not a Runner preflight, online outcome, capability
boundary, frequency estimate, State Mapping result, Contribution result, or VTDO admission.

A preliminary v1 build passed the original audit controls and remains immutable. A separate
post-materialization Candidate-neighborhood review then found that several invalid alternatives
used visibly different placeholder vocabularies such as `alternate_operation`, `partial`, and
`unbound`, while one Reconciliation D0 choice mixed two-argument and one-argument payloads. No
Provider call, Development Job, or empirical row occurred. The authoritative v2 keeps the same
source Cores, 32-Package denominator, causal graph topology, Runtime effects, load values,
counterfactual results, and parent-mutation counts, but rematerializes every implementation-bound
identity under a stricter public Candidate schema.

## Frozen v26.168 Evidence And Reproduced Defects

The stage binds all nineteen files in the authoritative v26.168 v3 main Root, including its
report, Development Catalog, sealed receipt, and transition. It reads no file from the sealed
Confirmation Root. Exact predecessor mutation count is zero.

The reproduction audit independently obtains the following v26.168 Development surface:

```text
Development Packages                                      32
nonterminal States                                        142
States whose Candidates all share one successor           142
non-null reference_candidate_id fields                    142
reference_action=true Candidates                          142
target_capability_action=true Candidates                  244
target_bypass Candidates                                  108
tempting-continuation Candidates                           34
public capability-family fields                           174
public depth fields                                       174
required-event Keys                                        92
family-level impossible-trace controls                      4
```

This freezes the strongest supported interpretation of v26.168. Its low-nuisance Finance Core,
typed Graph construction, operational Witness replay, boundary totality, and separate sealed Root
remain useful. Its model-facing prompt and transition semantics are not sufficient for the next
Runner stage because they expose Host answer-path structure and allow rejected actions to advance
through the same successor as the reference action.

## Host And Public Separation

The new core separates `HostExecutableDepthGraph` from `PublicExecutableDepthState` and
`PublicPromptProjection`.

The Host graph retains:

- capability family and Observation depth;
- reference Candidate and reference path;
- target-capability ownership;
- required event multiplicities;
- expected Transition status and typed terminal;
- full future State graph;
- exact Finance effects and snapshots.

The model-visible projection contains exactly two top-level objects:

```text
task
state
```

`task` is a schema-selected Finance projection. It retains the public instruction, allowed Tools,
answer fields, Evidence count, visible operation sequence, dependency counts, operator options,
and retrieval summary. It omits `task_type`, capability family, depth, Oracle identities, Gold
Evidence identities, reference path, required mechanism events, and future States.

`state` contains one current state token, current public facts, public history, and currently
visible Candidate payloads. No later State is serialized. A recursive scanner rejects every
Host-only Key at any Mapping depth and every registered answer-cue scalar fragment at any list,
tuple, Mapping, or scalar position.

Across the 32 packages, the exact online-facing static surface is:

```text
current-State Prompt projections                          210
future-State projections                                    0
public Candidates                                         630
recursive Host-Key leaks                                    0
recursive answer-cue leaks                                  0
nonisomorphic Candidate-schema States                       0
Candidate argument-shape mismatch States                    0
synthetic alternative-cue Candidates                        0
capability-label exposures                                  0
depth-label exposures                                       0
reference-path exposures                                    0
full-future-graph exposures                                 0
```

## Candidate Presentation

Every public action ID is a pre-outcome 24-character hexadecimal token. It is generated from one
fixed salt, Package identity, State ordinal, and semantic-choice ordinal. Host semantic-choice
hashes do not depend on those action IDs.

Every nonterminal State exposes exactly three Candidates. Candidate descriptions are neutral and
fixed. All three options use the same Tool and canonical argument positions. Each argument slot
also uses one registered lexical shape: qualified identifiers retain the same namespace and
hexadecimal width, indexed tokens retain the same stem and numeric width, and semantic command
tokens retain the same word-sequence arity. Reconciliation D0 therefore presents two arguments in
all three options rather than only in the reference option. The old placeholder families
`alternate_operation`, `normalization_route`, `operand_route`, `partial`, `unbound`, and their
related route/probe templates are absent.

Candidate canonical JSON encodings are padded to equal byte length within the State. The reference
position rotates deterministically by Development group, depth, and State ordinal. The audit
groups positions by family, depth, Host phase, and option count; all cells differ by at most one
observation across positions. Nonopaque IDs, unequal encodings, schema mismatches, argument-shape
mismatches, synthetic alternative cues, unbalanced cells, and ID-dependent semantic-choice
failures are zero.

This removes direct identifier cues. It does not claim that future model behavior is invariant to
presentation order; that remains an empirical Runner question.

## Causal Finance Binding

Each of the eight frozen Development Finance Cores receives one exact
`CausalFinanceBinding`. The binding is content-addressed to:

- the v26.168 Finance Core and operational record;
- the exact operational TaskPackage and TaskProgram;
- the independent Program verification output;
- the two exact Evidence identities;
- the public operation nodes and terminal operation node;
- actual normalization output symbols when present;
- content-derived input, projection, selector, and readiness bindings;
- a one-to-one selector-to-typed-failure map;
- the exact expected operator and independently computed result hash.

Runtime effects update an immutable `CausalFinanceSnapshot`. It rejects an input, projection,
selector, operation node, normalization reference, failure code, or readiness check outside the
Finance binding. A normalization reference cannot be consumed before production. A selector can
be revised only after its own matching typed failure. Program closure requires every bound public
operation node. Terminal verification requires a closed Program and exact expected result. Stop
requires terminal verification, and a later call becomes a typed postcompletion violation.

The independent task-validity report invokes the frozen Program verification and checks operation
lineage, family-specific operand binding, exact expected result, Program closure, terminal
verification, and postcompletion control. Mechanism validity is separate and checks exact event
multiplicity and trace ordering. Qualified validity remains their conjunction.

## Branch-Divergent Runtime

All 210 nonterminal States have three registered Candidates and three distinct successor State
identities. The reference Candidate advances to the next causal State. Each alternative reaches a
separate typed task terminal, except the stopping alternatives, which reach separately identified
postcompletion-violation terminals. No rejected or task-invalid action advances through the
reference successor.

The complete Runtime audit is:

```text
Development Packages                                      32
nonterminal States                                        210
branch-divergent States                                   210
all-Candidates-same-successor States                        0
Finance-Program-coupled baseline Packages                  32
Base-valid baselines                                       32
Mechanism-qualified baselines                              32
Qualified-valid baselines                                  32
Context current-State choice controls                       8
unproduced Reconciliation consume rejections                8
Recovery-before-matching-failure rejections                 8
Stopping-before-verification rejections                     8
postcompletion-violation terminal Packages                  8
accepted impossible traces                                  0
```

## Computed Depth Loads

Depth is computed from each Host graph and baseline Runtime trace. No v26.167 or v26.168 declared
load is reused as a measurement. Dimensions include branch alternatives, causal nonterminal
States, reference-path Finance effects, history-dependent public updates, target choices, and
Runtime calls.

The two Development groups in each family independently reproduce these strictly increasing
totals:

```text
Context-conditioned Action       29 / 37 / 45 / 53
Semantic Reconciliation          50 / 57 / 65 / 73
Failure Recovery                 37 / 45 / 53 / 69
State-dependent Stopping         36 / 43 / 50 / 57
```

These values are v26.169 causal-Runtime engineering loads. They are not numerically comparable to
the v26.168 metadata-ladder target loads as if both were observations of one unchanged metric.

## Task-Level Counterfactuals

The old v26.168 counterfactuals deleted a required Candidate or selected an eventless bypass. That
established event-contract necessity but did not prove that a complete registered alternative
caused task failure.

v26.169 instead runs two registered alternative branches for every Package. The Host graph remains
structurally valid. The Runtime executes a visible public action, reaches a typed terminal, and
then invokes both the independent task Verifier and mechanism Verifier. The exact result is:

```text
Packages                                                   32
registered counterfactuals per Package                      2
complete counterfactual replays                             64
task-Verifier invocations                                  64
mechanism-Verifier invocations                             64
Base-invalid results                                       64
Mechanism-unqualified results                              64
Qualified-invalid results                                  64
malformed-graph rejections used as necessity evidence       0
```

This is task-level static necessity under the exact registered Host alternatives. It remains a
local construct check, not empirical evidence about model errors or unrestricted task families.

## Cross-Parent Validation

The Package validator binds every child and grandchild identity: Finance binding, Graph, Witness
and Verifier Contracts, baseline Witness, target load, nuisance binding, Prompt binding,
projection Contract, presentation Policy, all three validity reports, and Host/Public hashes.

The destructive audit applies ten mutation kinds to each of 32 Packages. Every mutation uses a
genuinely different Core, family, depth, Contract, condition, Witness, load, nuisance parent, or
Prompt projection as appropriate. After mutation it recomputes the changed child identity,
Signature identity, Package artifact identity, Group identity, and Catalog identity. Stale hashes
are never the sole rejection mechanism.

```text
mutation kinds                                             10
crossed-parent mutations                                  320
child identities recomputed                               320
Package identities recomputed                             320
Group identities recomputed                               320
Catalog identities recomputed                             320
rejections                                                320
acceptances                                                 0
```

## Operational Witness Interpretation

The v26.168 Development Catalog contains eight unique low-nuisance Finance Cores and eight unique
operational Witnesses. Each operational Witness is replayed under four depth Packages. v26.169
therefore freezes the exact interpretation:

```text
Development Packages                                      32
unique Finance Cores                                        8
unique operational Finance Witnesses                        8
operational-Witness Package replays                        32
unique causal depth Runtime Witnesses                      32
independent Finance witness surfaces claimed                8
independent causal depth surfaces claimed                  32
```

It does not claim 32 independent Finance questions or 32 independent operational witness
surfaces.

## Isolation And Negative Claims

The new Development Catalog carries only the v26.168 sealed receipt identity. It contains no
sealed Catalog payload, filename, path, group, package, Finance Core, or source. Confirmation
payload access count is zero. This is artifact-interface isolation, not a claim that a repository
administrator cannot inspect the sealed Root.

Provider, Stage 2 Provider, GPU, Development Job, model behavior, Runner-preflight, Mapper,
Assignment, State, frequency, Contribution, VTDO, Student visibility, training, release, and
production counts remain zero. No historical artifact or label is rewritten. No empirical
boundary status is produced.

## Reproducibility And Checks

The transitive source Root starts from all four v26.169 implementation modules and resolves 298
local `trusted_synthesis` files with zero unresolved import. The authoritative v2 formal Root
contains 17 files and 4,087,766 bytes.

Focused Pytest passes 5/5 in 4.99 seconds. The adjacent v26.168-v26.169 regression passes 11/11 in
12.98 seconds. Focused PyCompile, Ruff, and Mypy pass. Two independent credential-free CLI builds
each execute the complete 32-Package baseline, 64-Counterfactual, and 320-mutation audit and
compare byte for byte with `diff -qr` returning zero differences. The Pytest suite separately
checks every report-bound formal file SHA-256 and byte count. Package-wide Ruff passes. Package-
wide Mypy checks 529 source files and retains only the four pre-existing v26.70, v26.129, and
byte-frozen v26.154 diagnostics, with zero v26.169 diagnostics.

## Authoritative Identities

- report:
  `finance_v26_causal_depth_hardening_report:234772d4046e3b18f614e54e0d53d26c97fc98f041528e1092e5c2157496d622`;
- external authorization:
  `finance_v26_causal_depth_external_audit_authorization:ceb1e9842b48bcde3b2bcde0501054b45679acddda3117eb9f34f2bcec7d9c69`;
- source replay:
  `finance_v26_causal_depth_source_replay:93665867d4301c6743f6307ce641d88e12e348a8ba2701dbb8fb4d330701d3d0`;
- transitive source Root:
  `finance_v26_causal_depth_transitive_source_root:706fa2d242f4884e5d3052abc58c7197df0d13d51dabbbfe78903e7057a22847`;
- v26.168 predecessor integrity:
  `finance_v26_causal_depth_predecessor_integrity:fd6d82cf8fabaecfceec483cd36df58c3c9de39bec1b70336795465c331956bd`;
- v26.168 defect reproduction:
  `finance_v26_v168_public_projection_runtime_defect_audit:538561b4b93c3d11a2734b14209d45dccbc0b5f0e7d22e491d44fc9b8dc86334`;
- Prompt Projection Contract:
  `depth_prompt_projection_contract:ef019d8af7724df4c40c083d618e637c9f2871d1a298c9146e1be57d52bc4f7a`;
- Candidate Presentation Policy:
  `causal_depth_candidate_presentation_policy:abe7c2de9b2af2af43b8b2a4cdde42d383ea3365ead447c0c73d253cfdc9550b`;
- Development Catalog:
  `finance_v26_causal_development_catalog:8b3bfa223589d52c5cd95d181f194172fd86d8d7c16d45488b218b15b843c6c0`;
- Public Projection Leakage Audit:
  `finance_v26_public_projection_leakage_audit:c455b2f25458dac3463529927ed93a1f2645546548479335282e6a612eee415f`;
- causal Runtime Audit:
  `finance_v26_causal_runtime_audit:bb75787e018a71e4ff2dbe67a3f71745277bb2f486a55ca3abf31f85ec3668c1`;
- task-level Counterfactual Catalog:
  `finance_v26_causal_depth_counterfactual_catalog:840d9c30b80083c6b33b679ba290ab7d2ea1d8799aad1e77e7a92cdc52939a13`;
- Parent Binding Audit:
  `finance_v26_causal_depth_parent_binding_audit:4d62838879ccb4c048dff2ccdcaecb9705e12f441fd2ac33227600b3512be1b3`;
- Operational Witness Interpretation:
  `finance_v26_operational_witness_interpretation:c50e69b9edf4d53416bdb308fc3a37b1c09f6eb5686fdc49ccb4417f4e50f35f`;
- static audit:
  `finance_v26_causal_depth_static_audit:23da60d3cddab4ec755b886939c0768b9ed45ad46281789f66d1baa4bdbc58b1`;
- transition:
  `finance_v26_causal_depth_transition:37d62fb3400161f433989597fdde416ecfd45e549a2324c831a6f9f38ace7368`.

## Only Permitted Transition

```text
capability_observation_executable_depth_development_runner_preflight_only
```

The successor may materialize only the exact future 192-Job Development Manifest and perform a
credential-free Runner preflight over the exact v26.169 Development Catalog, current-State-only
Prompt Projection Contract, Candidate Presentation Policy, causal Finance binding, branch-
divergent Host Runtime, task and mechanism Verifiers, fixed v26.168 generation condition,
nuisance, model/Thinking, Grammar, resource, threshold, terminal, and sealed-receipt bindings.

Provider execution, Development outcomes, Confirmation payload loading or execution, source,
Finance Core, Graph, public projection, Candidate presentation, condition, threshold, or Verifier
change, historical rewrite or reclassification, Mapper, State, frequency, Contribution, VTDO,
Student visibility, training, release, and production remain forbidden.
