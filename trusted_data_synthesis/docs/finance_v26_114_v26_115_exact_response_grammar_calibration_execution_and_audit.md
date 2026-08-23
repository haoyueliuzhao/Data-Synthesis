# Finance v26.114-v26.115 Exact Response Grammar Calibration Execution And Audit

Audit and execution date: 2026-08-23

## Scope

Finance v26.114 consumed exactly the online transition authorized by v26.113:

```text
exact_response_grammar_calibration_execution_only
```

The experiment held fixed the exact `deepseek-v4-flash` model, Thinking-enabled Stage 1
profile, 16,384-token Completion request, 260,000-token rollout ceiling, one global Rescue,
complete `PublicActionState`, 24 repeated engineering sources, 48 Compiler paths, 32 Job
assignments, all 32 seeds, deterministic reversible Stage 2 compiler, and zero Stage 2 Provider
calls. It did not rerun v26.110 or change a historical artifact.

The only protocol change relative to v26.110 was already frozen by v26.112-v26.113: Stage 1 used
the exact v2 ten-field response Grammar compiled from the same strong Schema used by the Parser.
v26.114 measured that frozen interface. v26.115 then independently audited the complete
execution without a credential, model client, Provider call, GPU job, historical
reclassification, or empirical-row promotion.

## Frozen Source And Final Preparation

The v26.114 online driver is
`phase1_v26_exact_response_grammar_calibration_execution.py`, committed before the online run
at source commit `8d740e1`. It wraps the exact single-Job implementation already bound by
v26.113; it does not modify that Runner.

Immediately before credential lookup and client construction, the final formal
`--prepare-only` replay passed 2,049/2,049 files:

- 2,041 v26.113 transitive source bindings;
- all seven v26.113 output files;
- the exact v26.114 online driver.

The replay identity is
`finance_v26_exact_grammar_execution_source_replay:63cb2efd20984b27f19bfdd3e3db79aca577987441ccaee16e50079fad183237`.
It reproduced the exact Runner Contract
`finance_v26_two_stage_runner_contract:02340ee6c14e53831b6057e92c8d2e694572cfbfb9e7432835cb7e6f28053506`,
the exact 32-Job denominator, and the scripted 256-call positive path. It constructed no model
client and made zero Provider calls.

The online run then started at 0/32 with eight workers and zero Raw recovery. A completed-run
replay later returned the identical report without a credential in the process environment,
without client construction, and without a new Provider call.

## Online Denominator And Provider Telemetry

All 32 frozen Jobs completed. Their formal terminal category is
`model_invalid_trajectory`; transport, Completion-unusable, typed no-call, and Instrument
terminals are all zero.

| Online quantity | Result |
| --- | ---: |
| Jobs | 32/32 |
| Stage 1 Provider calls | 81 |
| HTTP-success calls | 81 |
| Primary calls | 62 |
| Rescue calls | 19 |
| Stage 2 Provider calls | 0 |
| Prompt tokens | 147,995 |
| Completion tokens | 429,083 |
| Reasoning tokens | 410,643 |
| Total tokens | 577,078 |
| Estimated cost telemetry | USD 0.1398790904000000131 |
| Per-Job Provider calls | 1-5 |
| Per-Job total tokens | 7,287-42,008 |

Aggregate Reasoning/Completion fraction was `0.957024631598`. Primary used 360,028 Completion
tokens with fraction `0.961000255536`; Rescue used 69,055 with fraction
`0.936297154442`.

Every call requested, selected, and returned exact `deepseek-v4-flash`, requested
`thinking.type=enabled`, bound `max_tokens=16384`, retained complete Usage, explicitly
reported no Provider-native tool call, and had dynamic public-state, exact request-body, and
cumulative resource certificates before invocation. Fallback, discovery, transport failure,
one-token accounting-margin calls, larger accounting excesses, and private reasoning
persistence were zero.

## Empirical Response Funnel

v26.114-v26.115 is the first online two-stage denominator in which Stage 1 Proposals crossed the
exact response interface. The independently reconstructed funnel is:

```text
81 Provider calls / HTTP successes / public JSON payloads
-> 81 exact ten-field top-level Key Sets
-> 81 registered protocols
-> 81 exact public-state bindings
-> 81 registered Decision Kinds and conditional semantic-field rules
-> 54 exact stage constants and strong-Schema passes
-> 54 Parser-accepted semantic Proposals
-> 30 reversible Stage 2 Commits
-> 30 public Observations
-> 0 Program closures
-> 0 independently valid trajectories
```

The independent ABI implementation agreed with the Runner classification for 81/81 payloads.
This replaces the v26.110 zero-Proposal denominator with a measured 54 accepted Proposals and 30
committed semantic actions. Online semantic behavior is therefore measured and negative, not
unmeasured.

## Residual Mechanical ABI Failure

All 81 payloads had the exact registered top-level fields:

```text
stage
state_id
decision_kind
tool_id
node_id
operator_id
operand_sources
direct_arguments
evidence_ids
protocol
```

All 81 used the exact response protocol, copied the exact current `state_id`, selected a
registered Decision Kind, and passed the conditional semantic-field rules. The 27 rejected ABI
payloads failed only the fixed `stage` constant:

| Public `stage` value | Count |
| --- | ---: |
| `semantic_decision_proposal` | 54 |
| `stage_1` | 16 |
| numeric `1` | 6 |
| `stage_one` | 3 |
| `stage_01` | 1 |
| `prospective_two_stage_stage_one_exact_response.v2` | 1 |

ABI failures occurred at logical request positions 0/1/2/3 with counts 9/12/3/3. No payload
failed because of a missing field, extra field, wrapper, wrong `protocol`, stale
`state_id`, wrong Decision enum, semantic conditional-field mismatch, or wrong null/empty
default.

This establishes a narrow residual mechanical serialization issue. It does not reopen the
v26.111 hidden-Grammar diagnosis: the exact Grammar was visible, and 54 payloads followed it
completely. It also must not be merged with Tool, Node, Operator, Operand, or Evidence choice.

## Semantic Proposal And Runtime Result

The 54 ABI-accepted Proposals split into 30 committed actions and 24 accepted-but-uncommitted
Proposals. The latter are exactly 21 semantic compile rejections and three duplicate failed
Proposals.

The 21 semantic compile rejections independently reproduce as:

| Public semantic rejection | Jobs |
| --- | ---: |
| Compiled public call violates exposed Tool grammar | 10 |
| Proposal selects an unresolved public Operation | 7 |
| Proposal changes registered public operand sources | 4 |

These are model semantic choices under a complete public action interface. Response Grammar
optimization must stop for this partition.

All 30 Stage 2 Commit records independently decompiled to the exact same model Proposal. Host
semantic insertion, irreversible mapping, and Stage 2 Provider calls were zero. Committed
Decision Kinds were 29 `acquire_public_input` and one `execute_public_operation`.

The 30 public Observations were:

| Tool and status | Count |
| --- | ---: |
| `query_structured_fact` succeeded | 20 |
| `query_structured_fact` failed | 7 |
| `search_archive` succeeded | 2 |
| `normalize_metric_unit_period` succeeded | 1 |

The seven failures split into four `typed_selector_requires_refinement` and three
`structured_query_no_match`. Three Jobs then repeated a failed Proposal and terminated under
the frozen duplicate policy.

Verifier v3 Replay passed 32/32. There were two local mechanism successes and five requested-path
adherences, but no Program closure, terminal verification, final answer, or independently valid
trajectory. These diagnostics do not rescue any Job and create zero Capability, Reachability,
State Mapping, release, or production rows.

## Rescue And Resource Result

Thirteen Jobs required no Rescue. Nineteen used the one global Rescue:

- twelve Rescues returned an ABI-accepted Proposal;
- seven Rescues failed the same fixed `stage` constant;
- one Job recovered through Rescue and later encountered a second rescuable ABI failure after
  the global Rescue had been consumed.

Primary contained 20 ABI failures and Rescue contained seven. The observed result therefore
supports Rescue as an occasional correction in part of the denominator, but one global Rescue
still exposes multi-step survival loss.

No Job approached the 260,000-token rollout ceiling. Observed rollout headroom ranged from
217,992 to 252,713 tokens. Typed no-call and Completion-unusable Jobs were both 0/32, with their
one-sided 95% zero-failure upper bound retained as `0.0893681989862648`. The observed run does
not authorize a larger Completion bound, rollout bound, or additional Rescue.

## Independent v26.115 Audit

The v26.115 implementation was committed at `3bfd4b3` before the formal audit build. It replayed
2,172/2,172 files before execution parsing:

- all 2,049 v26.114 transitive source bindings;
- all 122 v26.114 execution files;
- the exact v26.115 implementation.

The execution files contain 121 canonical JSON files and one canonical 32-row checkpoint JSONL:

- 32 final Job results;
- 32 Raw Executions;
- 81 Raw Provider artifacts;
- 113 Raw descriptors;
- all top-level contracts, source replay, manifest, aggregate, and report files.

All parent bindings, 81 certificate triples, descriptor hashes and byte counts, unique Provider
identities, Usage sums, privacy fields, and Stage 2 zero-call counts reproduced. The checkpoint
and final result arrays matched 32/32. Formal and independent v26.115 builds produced all eight
files byte for byte. All 20 computed destructive mutations failed with zero Provider and Stage 2
Provider calls.

No v26.114 empirical value or terminal was reclassified.

Focused v26.112-v26.115 validation passed 8/8 tests. The adjacent v26.103-v26.115
Thinking/16K/two-stage/Exact-Grammar regression passed 63/63 tests against the canonical
immutable artifact root. Both v26.114-v26.115 implementation modules passed focused Ruff
format/check and Mypy.

## Interpretation And Permitted Transition

The result contains two distinct negative components:

1. Residual mechanical serialization: 27/81 public payloads used the wrong fixed `stage`
   constant, while every semantic field, field set, protocol, and state binding passed.
2. Measured semantic Proposal quality: after Exact ABI acceptance, 21 Jobs selected
   semantically uncompilable actions and three repeated a failed Proposal; no Job closed its
   Program.

The minimal prospective response to the first component is to move only the fixed `stage`
metadata outside the model-owned semantic payload into a Host-bound immutable envelope. This is
not permission for Host alias normalization, missing semantic-field insertion, Tool selection,
Node selection, Operator selection, operand repair, Evidence choice, or any other semantic
action.

The only permitted transition is:

```text
fresh_host_bound_stage_metadata_semantic_proposal_preflight_only
```

The successor must use fresh response protocol, Prompt, TaskPackage, Contract, Manifest, Job,
Runner, execution, and report identities. It may only bind the fixed `stage` metadata at the
Host envelope and must retain model ownership of all semantic fields. It must complete an exact
credential-free Runner preflight before any Provider call.

No v26.114 rerun, model/profile/Completion/rollout change, additional Rescue, role experiment,
State Mapping, release, or production Contribution is authorized.

## Authoritative Identities

- v26.114 execution report:
  `finance_v26_exact_grammar_execution_report:7b531b1887f1a244ecb0154975946f6e3739d1773bb850e1e5c91a9aa72a5ca3`;
- v26.114 Raw Lineage:
  `finance_v26_exact_grammar_raw_lineage:f5f1dd8204bdcf0b2c00d9560ad4dd4642f957bf17100b4b746268d9fe55c51d`;
- v26.115 report:
  `finance_v26_exact_grammar_postrun_audit_report:853fba47e8c1c00a3f189dc2fe6a9114167a4422e5751527f5f6a488466e0eaf`;
- response Funnel:
  `finance_v26_exact_response_funnel:b6ed1e5a50bddf7d40e2df39a805117d88d243c9753da9902359eccc7a069686`;
- semantic Runtime audit:
  `finance_v26_semantic_runtime_audit:01a3fcf01e3b621ce7decc689a480b0b1167287eba0b7d87ebb8e2b3b3b6fc3b`;
- Rescue/resource audit:
  `finance_v26_rescue_resource_audit:c4cf19a2849f24f8cb48c893d2020df873b29f74f5628f91d9440d85e7095a73`;
- transition Contract:
  `finance_v26_exact_grammar_postrun_transition:7389b693abde8c07640925497c43768c017a50eefd9433deef67547b1e3ffbb2`.
