# Finance v26.117 Semantic Action Protocol Design And Static Preflight

Audit date: 2026-08-23

## Scope And Authorization

v26.117 consumes only the credential-free design transition authorized by v26.116:

```text
semantic_action_selection_protocol_design_only
```

It does not execute a model, construct a Provider client, read a credential, use a GPU, create an
empirical row, or alter any v26.114-v26.116 artifact. It does not reparse a v26.114 public model
payload, recover a historical Job, or reclassify a historical result.

The stage addresses the review finding that the 24 v26.114 accepted-without-Commit outcomes could
not all be assigned to pure Flash semantic capability. The prior interface still combined:

- semantic acquisition choice with low-level `direct_arguments` generation;
- dependency readiness with executable Operation readiness;
- source symbols and Evidence identities as competing action references;
- duplicate rejection with history that was not completely represented by the current public
  state;
- ABI Rescue and semantic recovery inside one effective failure budget.

v26.117 designs and statically tests a public Semantic Action protocol that separates those
dimensions. It does not claim that this protocol will make Flash trajectories valid.

## Source Replay

Before constructing the protocol, v26.117 replayed 2,191/2,191 exact files:

| Source group | Files |
| --- | ---: |
| v26.116 transitive source bindings | 2,181 |
| v26.116 immutable outputs | 8 |
| v26.117 implementation files | 2 |
| Total | 2,191 |

Every expected SHA-256 matched the observed file. Replay occurred before protocol construction.
Credential lookup, model-client construction, Provider calls, Stage 2 Provider calls, GPU jobs,
and empirical rows were all zero.

The two v26.117 implementation files are:

- `runtime/agent/prospective_semantic_action_protocol.py`;
- `experiments/vtdo_experiment/phase1_v26_semantic_action_protocol_preflight.py`.

## Canonical Public Action Language

### Model-Owned Selection

The only model-selectable semantic object is a content-addressed `action_id`. Each visible
candidate binds one complete public semantic choice. The semantic proposal contains exactly:

```text
state_id, action_id, decision_kind, protocol
```

It does not contain `direct_arguments`, `tool_id`, `node_id`, `operator_id`,
`operand_sources`, or `evidence_ids`. Those values are not inserted after an incomplete model
proposal. They are already part of the public candidate selected by `action_id`.

This distinction is important. The Host enumerates the actions permitted by public contracts and
current public state; the model chooses among them. Stage 2 then applies one frozen public
serialization recipe. It cannot select another Tool, Node, Operator, Operand, Evidence set, or
semantic repair.

### Acquisition Compilation

Acquisition no longer accepts an arbitrary argument object. Four public semantic modes compile
deterministically:

| Public mode | Tool | Public semantic input | Deterministic wire fields |
| --- | --- | --- | --- |
| `search_public_record` | `search_archive` | registered source symbol and public record | `limit`, `period_labels`, `query`, `source_filters`, `subject_aliases` |
| `query_source_scoped` | `query_structured_fact` | registered source symbol and source scope | `metric_alias`, `period_label`, `public_filters`, `subject_alias` |
| `query_fully_qualified` | `query_structured_fact` | registered source symbol and complete public selector | same exact four fields |
| `open_public_document` | `open_document` | content-addressed public document reference | `public_locator` |

Both structured-query modes remain model-selectable. The source-scoped form is not silently
rewritten into the fully qualified form. If a source-scoped call fails with a typed refinement
result, its exact public-call signature is blocked and the model must select another visible
candidate.

### One Reference Language

Every resolved public source has one content-addressed `PublicSourceReference`. It binds one
source symbol to exactly one public Evidence identity or public Operation reference. Operation
and verification candidates select these reference identities. Stage 2 uses their frozen public
bindings to serialize wire operands.

The model therefore no longer chooses between two syntactically different names for the same
action object. Evidence identities remain visible as the public value bound by an Evidence
reference, but they are not a second proposal language.

## Operation Frontier

The protocol replaces the old overloaded `ready_operations` interpretation with four disjoint
public statuses:

1. `blocked_dependencies`: at least one Operation dependency is incomplete;
2. `dependency_ready`: dependencies are complete, but one or more public source symbols remain
   unresolved;
3. `executable`: dependencies and all ordered source references are resolved;
4. `terminal_verifiable`: the terminal Operation is complete and exact public verification is
   pending.

Only `executable` may produce an `execute_public_operation` candidate. Terminal verification is
a separate candidate family. Final answer emission appears only after exact public verification.

Across all 324 tested public states, the frontier contained:

| Frontier status | Rows | States containing status |
| --- | ---: | ---: |
| `blocked_dependencies` | 60 | 60 |
| `dependency_ready` | 174 | 156 |
| `executable` | 102 | 90 |
| `terminal_verifiable` | 48 | 48 |

There were 114 Operation candidates because some public Context states exposed more than one
model-selectable Operator for an executable Node. All 114 came from `executable`. Candidate
counts from the other three statuses were zero.

Public Context operator selection remains model-owned. Where a Node exposes several Operators,
the state also exposes the registered Operator-output schemas, required output schema, and
selection rule. The Prompt-only fixture selects the matching public candidate; Stage 2 does not
perform that semantic choice.

## Public Sufficiency And Duplicate Blocking

Proposal acceptance is:

```text
Accept(p_t) = action_id(p_t) in S_t_public.action_candidates
              and p_t.state_id == S_t_public.state_id
              and p_t.decision_kind == candidate.decision_kind
```

The evaluator accepts only `SemanticActionState`, `CanonicalActionProposal`, and
`call_index`. It has no Observation-history or hidden-failure parameter.

All failed public-call signatures are projected into the current state as
`active_blocked_public_calls`. A blocked action is removed from `action_candidates` and
retained in `blocked_actions` with:

- its `action_id`;
- selected Decision kind and Tool;
- acquisition mode and target public source symbols when applicable;
- typed error category;
- blocked public-call signature.

Exact failed argument values are not retained. All twelve typed refinement failures in the 48
Compiler paths appeared in a subsequent state as visible blocked actions. No hidden historical
lookup was used.

For all 324 states, the visible candidate set and validator acceptance set were identical.

## Typed Semantic Rejection And Recovery

A semantic rejection is a typed, action-neutral public Observation. It may expose:

- failed Decision kind;
- selected `action_id` and selected Tool when known;
- error category;
- violated public constraint;
- unresolved public symbols;
- blocked public-call signature.

It does not expose the correct Tool, Node, Operator, Operand, Evidence, exact argument values, or
an argument patch. The rejection itself has `job_terminal=false`.

The static continuity fixture selected a currently visible blocked action and reproduced:

```text
blocked Proposal
  -> typed semantic rejection
  -> public state rebuilt with that rejection
  -> final serialized recovery Prompt parsed
  -> different model-owned action_id selected
  -> exact next frozen Compiler call committed
```

The exact next call matched 1/1. No Tool call or Provider call occurred while producing the
semantic rejection.

ABI Rescue and semantic recovery have separate one-use counters. The fixture began with ABI
Rescue already consumed:

| Counter | Before semantic rejection | After semantic rejection |
| --- | ---: | ---: |
| ABI Rescue | 1 | 1 |
| Semantic recovery | 0 | 1 |

These limits are protocol design constants for the static continuity proof. They were not fitted
to the v26.116 counts 10/7/4/3 and do not establish an empirically sufficient future recovery
budget.

## Full-Path Prompt-Only Control

The control exercised all 48 frozen Compiler paths:

| Path strategy | Paths |
| --- | ---: |
| `structured_direct` | 24 |
| `search_then_structured` | 12 |
| `search_then_open` | 12 |

At every state, the fixture received only the final serialized Prompt. It did not read a parser
Schema, internal Proposal, Oracle Program, expected arguments, or frozen next call when selecting
the candidate.

The complete result was:

| Measure | Result |
| --- | ---: |
| Serialized Prompt parses | 324/324 |
| Prompt-only semantic Proposals | 324/324 |
| Exact frozen tool-call matches | 276/276 |
| Final-ready decisions | 48/48 |
| Complete paths | 48/48 |
| Typed Runtime refinements traversed | 12 |
| Maximum Prompt size | 16,887 UTF-8 bytes |

The selected decisions were:

| Decision kind | Count |
| --- | ---: |
| Acquisition | 156 |
| Operation | 72 |
| Verification | 48 |
| Final | 48 |

The 156 acquisitions were:

| Mode | Count |
| --- | ---: |
| Search public record | 48 |
| Fully qualified structured query | 75 |
| Source-scoped structured query | 12 |
| Open public document | 21 |

There were 279 unique public-state identities, 265 unique action identities, 84 unique source
references, and 48 unique document references.

The 16,887-byte maximum is a new static observation. It is larger than the earlier exact-response
Prompt maxima and does not inherit any prior resource qualification. A successor must
rematerialize its resource, TaskPackage, Contract, Manifest, Job, and Runner identities and
recompute all Prompt and rollout bounds before any Provider call.

## Stage 2 Authority

All 324 selected actions produced reversible Commits:

| Commit kind | Count |
| --- | ---: |
| Tool-call Commit | 276 |
| Final Commit | 48 |
| Total reversible Commits | 324 |

Compiler-selected Tool, Node, Operator, Operand, Evidence, and semantic repair counts were all
zero. Stage 2 has no Provider profile, client route, or Provider call. Every tool call
decompiled to exactly the selected `action_id`.

## Destructive Controls

All 20 computed mutations failed with zero Provider and Stage 2 Provider calls. The controls
covered:

- Host insertion of Tool, Node, Operator, Operand, Evidence, and `direct_arguments`;
- Host semantic repair;
- making a dependency-ready Operation selectable;
- reinserting a blocked action into the selectable candidate set;
- using hidden old failure state in acceptance;
- exposing exact failed arguments or a required argument patch;
- turning a semantic rejection into an immediate Job terminal;
- coupling ABI and semantic recovery counters;
- adding a Stage 2 Provider route.

## Reproducibility And Validation

Formal and independent builds produced all ten output files byte for byte:

- nine detail artifacts;
- one top-level report.

Focused validation:

| Check | Result |
| --- | --- |
| v26.117 focused Pytest | 2 passed in 17.83 seconds |
| v26.117 focused Ruff format/check | passed |
| v26.117 focused Mypy | passed for both implementation modules |
| v26.97-v26.117 adjacent regression subset | 97 passed in 156.60 seconds |
| Provider calls | 0 |
| Stage 2 Provider calls | 0 |
| GPU jobs | 0 |
| Empirical rows | 0 |

## Authoritative Identities

- report:
  `finance_v26_semantic_action_preflight_report:876f4215157688cd420a1708ecd9f4f2d5527d40cd11db0e4828f920095ce362`;
- source replay:
  `finance_v26_semantic_action_source_replay:d2e3a35290b4d5428a65eaf9b7e15b9d53b5146bef7f4e645047155d84fcb28f`;
- protocol:
  `finance_v26_semantic_action_protocol:3f178cb8af42b41809ea0d1c2324bfaf2ddfcdd732ad7cb570f2ccaec4ec8984`;
- canonical action language:
  `finance_v26_canonical_action_language:cb80acd326922900c9a305180de2923df47aef4458ea7f658bba6d7f59d5fdc7`;
- Operation frontier:
  `finance_v26_operation_frontier_audit:fa1ab640016337dbef6aa9e954e080c81a2ed5c0ed3029d1068fb9dc0e8c4a8e`;
- Prompt-only path control:
  `finance_v26_prompt_only_path_control:7070e23b3eab8c194280099cebddc65edf1c578c875fa50cea94020600d917db`;
- semantic recovery:
  `finance_v26_semantic_recovery_continuity:b92c069cf441c592cd4de6982505090bfaca6d6c9316359b119b96f7dec8ca8b`;
- Stage 2 authority:
  `finance_v26_stage_two_authority_audit:17508aae9bea6791671865f102aa870cb115bccef689486783db149948251855`;
- transition:
  `finance_v26_semantic_action_transition:90567cb15885dadcd2340e394af572017118bae806d634f8cf0554841306290c`.

## Decision

v26.117 is a positive static protocol-constructibility and authority result. It is not an online
Flash result, an empirical Semantic Action usability result, a sufficient resource result, or a
causal claim that the v26.114 failures were entirely caused by the old protocol.

The only permitted transition is:

```text
fresh_semantic_action_protocol_taskpackage_contract_manifest_and_runner_preflight_only
```

The successor must use fresh TaskPackage, resource, Contract, Manifest, Job, response-protocol,
Runner, execution, and report identities. It must pass an exact credential-free Runner preflight
before any Provider call. Historical v26.114 replay, recovery, or reclassification; Host semantic
choice or repair; response-Grammar or fixed-`stage` optimization; model/profile/Completion/
rollout changes; additional Rescue; role experiments; State Mapping; training; release; and
production Contribution remain forbidden.
