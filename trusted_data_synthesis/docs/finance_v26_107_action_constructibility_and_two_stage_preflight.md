# v26.107 Action Constructibility And True Two-Stage Protocol Preflight

Audit and build date: 2026-08-22

## Decision

Finance v26.107 completed the credential-free design and static preflight authorized by the
v26.106 post-run transition. It repairs the prospective unavailable-tool Replay contract,
separates model-owned semantic decisions from deterministic low-level call serialization, closes
the model-visible action interface, repairs Final Rescue semantic sufficiency, and freezes a
prospective failure taxonomy.

The stage passed, but it is deliberately not execution-authorizing. It materialized no model
profile, Completion or Usage bound, dynamic rollout-budget Contract, TaskPackage, empirical
Contract, Manifest, Job, execution identity, or online Runner. It looked up no credential,
constructed no model client, made zero Provider calls, used zero GPU jobs, and produced zero
empirical rows.

The only permitted transition is:

```text
fresh_two_stage_profiles_taskpackage_contract_manifest_and_runner_preflight_only
```

No 32K single-stage candidate, empirical calibration, role experiment, State Mapping, release,
or production Contribution is authorized.

## Frozen Predecessor

The predecessor is the authoritative v26.106 v2 report:

```text
finance_v26_exact_16k_postrun_audit_report:
ba83dc516a0d4dbdf527cd9f630fd2e1ea513c1855c566c751aad86235cd1fd8
```

Its transition Contract is:

```text
finance_v26_exact_16k_postrun_transition:
3b521a4324e067c94fa19b219514a7b9666e4638b8f31b5d8472dd673564ee90
```

v26.107 retains every v26.105 terminal and every v26.106 conclusion. It reran zero v26.105 Jobs,
recovered zero historical Jobs, changed zero Raw artifacts, and reclassified zero historical
terminals. The immutable v26.105 denominator remains:

| Terminal | Jobs |
| --- | ---: |
| `completion_unusable` | 14 |
| top-level `typed_budget_no_call` | 15 |
| `instrument_failure` | 2 |
| `model_invalid_trajectory` | 1 |

Typed no-call Raw terminals remain present in 17 Jobs. The single exact-bound reasoning-only
length failure continues to end the single-stage Completion-bound ladder.

## Source Replay

Before diagnostics, profile logic, or any possible client construction, the formal build replayed
1,872 files:

| Source kind | Files |
| --- | ---: |
| v26.106 transitive bindings | 1,860 |
| exact v26.106 outputs | 9 |
| exact v26.107 implementation files | 3 |
| total | 1,872 |

All expected and observed SHA-256 values matched. The source replay identity is:

```text
finance_v26_action_constructibility_source_replay:
d12be309b26e0ce2bec13c7f455b8d59b2869b87c12af3a6c41d456902b81d99
```

Formal and independent builds then reproduced all ten v26.107 outputs byte for byte.

## Historical Interface Audit

The uploaded audit correctly identified the dominant prospective engineering gap: the old static
Witness could read exact `expected_arguments`, while the model-visible Prompt omitted the full
tool input grammar, public symbol bindings, operand-reference serialization, and frozen
parameters. The Runtime still compared model calls against the exact low-level contract. Thus the
old 48/48 Compiler-path result established executable Runtime paths given exact calls, but did not
establish that those calls were constructible from the model-visible interface.

v26.107 independently reparsed all 32 v26.105 Raw Executions and all 572 Provider artifacts. The
historical Calculator Observation denominator is:

| Calculator result | Count |
| --- | ---: |
| Runtime Calculator Observations | 382 |
| Jobs containing Calculator Observations | 30 |
| succeeded | 1 |
| failed | 381 |
| Jobs with a success | 1 |

One additional retained Provider response mentioned Calculator but used the unregistered
`action=calculate`; it never became a Runtime Calculator Observation. This explains a possible
383 response-payload count versus the authoritative 382 Observation count.

The exact Runtime call-shape partition is:

| Observed shape relative to the ready public node | Count |
| --- | ---: |
| bare operands | 188 |
| operand objects with wrong fields | 158 |
| wrong operand type or count | 22 |
| frozen-parameter mismatch | 12 |
| reference, order, or operator mismatch | 1 |
| exact argument match | 1 |
| total | 382 |

This strongly supports `model_visible_action_contract_not_wire_complete` as the dominant
prospective engineering root. It does not prove that Flash would succeed after the repair; early
answers, repeated failed calls, path errors, and other model-owned behavior remain unresolved.

### Correction To The Uploaded Audit

The uploaded analysis reported 93 Calculator calls with no ready Calculator node. That count was
not reproduced. v26.107 evaluated `public_operation_progress()` immediately before every one of
the 382 immutable Calculator Observations. Every call had at least one code-defined ready
Calculator node with no unresolved public symbols; the not-ready count was zero.

This correction does not mean the calls matched the ready node. Only one exact call succeeded,
and the shape partition above shows why the other 381 failed. The likely source of the 93 count is
that the old model-visible compact progress intentionally omitted `tool_id`, so a scanner using
that projection cannot identify ready Calculator nodes. The authoritative statement is therefore:

```text
382/382 Calculator Observations had a code-defined ready Calculator node.
1/382 exactly matched and succeeded.
```

The historical interface audit identity is:

```text
finance_v26_historical_action_interface:
ea44d16a6a2ca3925af22a7f154998fd9a238b6afea506059597c263c89ff25b
```

## Tool Affordance And Replay

The old Prompt had an independent consistency defect. Across 79 Provider Prompts in 12 Jobs,
public variables advertised `open_document` while the current stage's top-level public tool list
did not expose that tool. The prospective action state now computes effective acquisition tools
as the intersection of:

```text
resolution-rule tools
intersection environment model-selectable tools
intersection current-stage tools
```

Every variable-level acquisition tool must be a subset of the public tool grammars in the same
serialized state.

v26.107 freezes exactly one gate for Verifier v3 and the future prospective Runtime:

```python
resolve_model_selectable_tool_or_typed_failure()
```

Verifier v3 calls it before tool-spec validation, and every successor Runtime must call the same
entry point. A missing or unselectable tool yields the exact public Runtime failure:

```text
unknown_or_unselectable_tool
```

Verifier v3 replayed all 32 historical Raw Executions and every Observation. Both historical
unavailable `open_document` calls reproduced the exact typed failure. The result was 32/32
Replay passes, two exact unavailable-tool failures, zero prospective Replay failures, zero
inserted or Host-selected actions, and zero historical reclassifications.

The authoritative Verifier identities are:

```text
finance_v26_authority_verifier_contract_v3:
478f7b6cd880f68865d94046bd66ff6e339f03814dec2b94f27d93d0a32bacfa

finance_v26_verifier_v3_replay_audit:
25d1ce7460889438e749c75e350a0be83253bdb4e0d7e99350fd3cec7595d547
```

These are prospective qualification results. They do not alter the two historical v26.105
`instrument_failure` terminals.

## Public Action Constructibility

v26.107 introduces a content-addressed `PublicActionState`. It contains only model-visible
public information:

- complete input contracts for currently relevant model-selectable tools;
- effective variable acquisition affordances;
- resolved public `source_symbol -> evidence_id` bindings;
- resolved public `output_symbol -> operation_ref` bindings;
- ready nodes, tools, operator choices, operand slots, reference kinds, selectors, and fixed
  public serialization parameters;
- current unresolved symbols and selected public Evidence;
- bounded public failure summaries;
- terminal Operation and final-answer source projections when available.

It rejects private and Oracle keys, including Gold Evidence, `expected_arguments`, Oracle
Programs, hidden correct actions, and private reasoning. Public action identities change whenever
the public state changes.

Failed-action history no longer retains full failed argument values. It retains only the latest
failure per public Tool/error category, a public blocked-call signature hash, and an argument-shape
summary. The fixture audit found zero exact Evidence or Operation-reference values inside the new
failure shapes.

## True Two-Stage Boundary

The prospective protocol has a narrow two-stage boundary.

### Stage 1: Thinking Semantic Decision Proposal

Stage 1 remains model-owned and must use `thinking.type=enabled`. The public proposal selects:

- decision kind;
- Tool;
- ready Node;
- Operator when applicable;
- ordered public operand source symbols;
- acquisition arguments when applicable;
- public Evidence for terminal verification.

Only this public proposal crosses the stage boundary. Private reasoning content and hashes may not
cross, persist, or enter the identity.

### Stage 2: Deterministic Decision Commit Compilation

Stage 2 makes no Provider call and may not choose a Tool, Node, Operator, operand source, Evidence,
or answer. It only maps the model-selected public source symbols through the exposed binding table
and serializes the exact low-level `AgentToolCall`.

For example, a model-owned proposal selecting two public normalized source symbols is compiled to
ordered `operation_ref` and `selector` operand objects plus the frozen public parameters.
Changing the proposal must change the Commit. An unresolved symbol, unknown Tool, unready Node,
unregistered Operator, reordered source list, or unavailable Evidence fails closed.

Every compiled call must decompile to the exact same semantic proposal. This reversibility check
prevents the compiler from silently repairing a wrong model decision.

The protocol identity is:

```text
finance_v26_action_constructibility_protocol:
4044cdfbb3aa6526c5a9f8cc608a745ec55f3151cbd5e79a8e5af575737851e0
```

This stage freezes the boundary, not a model configuration or online execution route.

## Constructibility Fixtures

Two complementary zero-generation controls were used.

### Compiler Round Trip

All 48 preserved Compiler paths were projected into the new public action state. Their 276 public
tool calls were decompiled into model-owned semantic proposals and deterministically recompiled:

| Proposal kind | Calls |
| --- | ---: |
| acquisition | 156 |
| Operation execution | 72 |
| terminal verification | 48 |
| total | 276 |

All 276 calls were byte-semantically identical after the round trip. The controls covered 147
unique public action states, and all 276 states passed the variable-tool subset invariant. The
largest rendered action Prompt was 6,345 UTF-8 bytes, below the historical 60,000-byte ceiling.

### Exact Serialized Prompt-Only Reference Policy

The second control did not read TaskPackages, `public_operation_progress.expected_arguments`,
Oracle state, or Verifier bindings. It received the exact final rendered Prompt text, reparsed the
serialized `PublicActionState`, produced a semantic proposal, compiled it, and executed only the
resulting public call.

Across 24 unique tasks it made 138 Prompt-only decisions:

| Prompt-only outcome | Count |
| --- | ---: |
| compiled public tool calls | 114 |
| expected typed selector refinements | 6 |
| final-ready decisions | 24 |
| other failures | 0 |

All 24 tasks reached exact public Final Ready. These remain deterministic implementation
fixtures, not model outcomes and not empirical capability evidence.

The fixture identity is:

```text
finance_v26_action_constructibility_fixture:
9b522aea28428f77261c5443da0b835f104f66f30506a0ba9847a847f1a04481
```

## Final Rescue Semantic Sufficiency

The prospective Final Rescue retains only the public terminal answer source:

- `terminal_operation_ref`;
- privacy-redacted `terminal_result_projection`;
- public `answer_source_fields`;
- selected public Evidence;
- exact final response schema.

It does not reuse previous final content or private reasoning.

All 48 Compiler paths produced semantically sufficient Rescue Prompts. The maximum was 2,515
UTF-8 bytes, below the frozen 6,144-byte absolute ceiling.

The historical completed Raw row
`raw_execution/7a8f36f5fe3b2b80e72b.json` was also exercised without a Provider call.
Its terminal public value was `0.4107`; the old Primary emitted scalar `0.4107`, and the old
Rescue lost that source and emitted `0.1`. The repaired 2,323-byte Rescue retained the public
terminal value `0.4107`. This proves semantic sufficiency of the new fixture Prompt; it does not
reclassify the historical model-invalid trajectory or claim a future model will answer correctly.

The Final Rescue audit identity is:

```text
finance_v26_final_rescue_semantic_audit:
91c2b0db10989862cb88ff26120ca1fb017ea678a6959ec1ddfa975fc05d8f8c
```

## Prospective Failure Taxonomy

All 33 historical `invalid_response_contract` Provider responses retained valid public JSON.
The exact immutable split is:

| Prospective diagnostic subtype | Count |
| --- | ---: |
| Decision-stage answer or non-action payload | 22 |
| public Prompt/state echo | 7 |
| unregistered Decision action enum | 3 |
| Final-answer scalar instead of object | 1 |
| total | 33 |

The uploaded audit's 23/7/3 grouping combined the one Final-answer scalar Schema failure with 22
Decision-stage premature-answer failures. v26.107 separates them because they occur at different
request kinds and require different prospective controls.

The prospective families are:

- channel or JSON parse failure;
- response serialization failure;
- Decision phase-control failure;
- Prompt-echo instruction failure;
- semantic Tool/argument failure;
- Runtime failure;
- Instrument failure.

This taxonomy is future-only. The historical Completion failure count and all historical Job
terminals remain unchanged. Its identity is:

```text
finance_v26_prospective_failure_taxonomy:
714e59685cac8f2c4d309406db773abd7ec07caafa7bf7fe86f63b48564e02c8
```

## Destructive Preflight

All 30 destructive mutations failed before any Provider behavior. They cover:

- stale public-state, proposal, Commit, Contract, and content identities;
- variable tools outside public grammars;
- duplicate or private bindings;
- private `expected_arguments` exposure;
- proposal/state parent mismatch;
- unknown Tool, unready Node, unregistered Operator, changed operand order, and missing source;
- Operation before public binding, verification before terminal, and final answer before readiness;
- unavailable Evidence and wrong verification Tool;
- acquisition through an Operation Tool or missing required fields;
- non-reversible and semantics-changing Commit calls;
- changed unavailable-tool typed failure;
- Final Rescue without source JSON or terminal progress;
- exact failed Evidence values in bounded history;
- missing model semantic authority or compiler semantic selection.

The destructive audit identity is:

```text
finance_v26_action_constructibility_destructive:
4dea87ade53b8a56041b23810dea1fdb26515c5953963e7845d3d317339ef219
```

## Validation

The final integrated source passed:

| Check | Result |
| --- | --- |
| formal source replay | 1,872/1,872 |
| formal and independent output comparison | 10/10 byte-identical |
| focused v26.107 tests | 9 passed |
| v26.97-v26.107 adjacent regression | 73 passed |
| focused Ruff format and check | passed |
| focused Mypy | 4 source files, zero diagnostics |
| package-wide Mypy | 414 source files; one retained historical v26.70 diagnostic; v26.107 adds zero |
| real Provider calls | 0 |
| model-client constructions | 0 |
| GPU jobs | 0 |
| empirical rows | 0 |

The authoritative report identity is:

```text
finance_v26_action_constructibility_preflight_report:
ff0eb5409a770fb72381f93a83fff3726fa8f547d994796f247682c9f0516e19
```

## Interpretation Boundary

v26.107 supports the engineering statement that the historical model-visible action contract was
not wire-complete and that the prospective public interface is statically action-constructible.
It also demonstrates an exact prospective repair for the two unavailable-tool Replay rows and the
historical Final Rescue semantic omission.

It does not establish:

- empirical two-stage Completion usability;
- sufficient Stage 1 Completion or rollout bounds;
- model success under the repaired interface;
- Capability, Reachability, State Mapping, or State Support;
- a Thinking role protocol;
- a sufficient fresh task Population;
- Exact Target, GP-C, or production Contribution.

The next stage must materialize fresh Stage 1 Thinking profile and request identities, explicit
Stage 2 zero-generation Commit semantics, fresh Completion/Usage and dynamic resource Contracts,
fresh TaskPackage/Contract/Manifest/Job identities, and an exact Runner. That Runner must pass a
complete credential-free preflight before any Provider call can be considered. Historical
v26.105 Jobs remain permanently ineligible for rerun or reclassification.

## Authoritative Files

- `src/trusted_synthesis/runtime/agent/prospective_action_constructibility.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_authority_preserving_verifier_replay_v3.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_action_constructibility_two_stage_preflight.py`
- `tests/test_v26_action_constructibility_two_stage_preflight.py`
- `artifacts/vtdo_experiment/finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822/report.json`
- `artifacts/vtdo_experiment/finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822/historical_action_interface_audit.json`
- `artifacts/vtdo_experiment/finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822/failure_taxonomy_audit.json`
- `artifacts/vtdo_experiment/finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822/verifier_v3_contract.json`
- `artifacts/vtdo_experiment/finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822/verifier_v3_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822/action_constructibility_protocol.json`
- `artifacts/vtdo_experiment/finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822/action_constructibility_fixture_audit.json`
- `artifacts/vtdo_experiment/finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822/final_rescue_semantic_audit.json`
- `artifacts/vtdo_experiment/finance_v26_107_action_constructibility_two_stage_preflight_v1_20260822/destructive_preflight_audit.json`
