# Finance v26.124-v26.125 Exact Final Semantic Action Execution And Audit

Audit date: 2026-08-23

## Decision Summary

Finance v26.124 consumed exactly the online engineering-calibration authorization frozen by
v26.123. It executed the fresh 32-Job Final-Grammar Semantic Action Manifest with the frozen
Canonical Semantic Action protocol, Candidate authority, exact Flash Thinking profile, 16,384
Completion bound, 400,000-token rollout ceiling, one global ABI Rescue, one separate Semantic
Recovery, privacy-first Envelope/Projection capture, and zero-Provider Stage 2.

The run produced a complete 32/32 Raw and Job-result denominator with no orphan artifact, but it
did not produce a complete 32-Job model-outcome denominator. Ten Jobs ended Instrument failure:
eight HTTP-200 calls raised `IncompleteRead(0 bytes)` while reading the response body and two
calls raised connection-refused `URLError` before an HTTP response. The other 22 Jobs are exact
model outcomes: eleven independently valid trajectories and eleven model-invalid trajectories.

All 22 model outcomes closed the Program, completed the terminal node, succeeded at terminal
verification, and committed Final. Seventeen Jobs crossed the exact two-field Final Grammar;
eleven were independently valid. Five Jobs returned `answer` as a string in both Final Primary
and Final Rescue and remained model-invalid. The six exact-ABI but independently invalid results
split into three answer-projection failures and three target-mechanism failures. Citation,
Evidence support, operation lineage, Replay, and terminal verification passed for all six.

Finance v26.125 independently replayed the complete lineage with zero Provider calls. It freezes
ten exact failed-call recovery Candidates and preserves the 22 model outcomes unchanged. The
current transition authorizes only a fresh credential-free Recovery Contract, Manifest, Job, and
Runner preflight. It does not authorize a Provider call or any historical Job rerun,
continuation, or reclassification.

## Frozen Authorization And Preexecution

v26.124 used only the v26.123 authorization:

```text
exact_final_semantic_action_calibration_execution_only
```

Immediately before any credential lookup or model-client construction, the Runner replayed
2,562/2,562 files:

| Source partition | Files |
| --- | ---: |
| v26.123 transitive bindings | 2,549 |
| v26.123 output files | 12 |
| exact v26.124 implementation | 1 |
| total | 2,562 |

The replay bound the exact v26.123 report, Runner Contract, outcome-measurement Contract,
Manifest, 32 Jobs, model profile, Thinking policy, Action and Final Grammars, Candidate
presentation, resource Contract, recovery limits, and Stage 2 zero-call route before credential
lookup. Its identity is:

```text
finance_v26_exact_final_execution_source_replay:202f2394e2a20d2edd5062b5186f8de875b4bb621a68bc4569fe874ea64d2a01
```

A separate computed preexecution control ran all 32 exact Jobs through the scripted Runner. It
made 256 local Stage 1 calls, crossed 224 exact Action payloads, made 224 reversible same-action
Commits and 192 Observations, crossed 32 exact Final payloads, and passed 32/32 Replay,
independent validity, and mechanism checks. It made zero real Provider calls and binds:

```text
finance_v26_exact_final_preexecution_validity:52e2c4627f33a6ccbde12d72bb64aeea280c919fa92ddd4003b3bd62023583e6
```

The online run then started from 0/32 with eight workers. The API credential was read only from
the process environment loaded from `.env`; no credential value entered a request-independent
artifact, source file, report, or log.

## Online Execution Denominators

The Runner opened each of the 32 fresh Jobs exactly once and wrote one complete Raw Execution and
one Job result for every Job. A completed-run replay without a credential resumed at 32/32,
constructed no model client, made zero new calls, and returned the unchanged report.

The primary terminal partition is:

| Terminal | Jobs |
| --- | ---: |
| `model_valid_trajectory` | 11 |
| `model_invalid_trajectory` | 11 |
| `instrument_failure` | 10 |
| all other terminals | 0 |
| total | 32 |

This is a complete operational denominator, but not a complete model endpoint denominator. The
ten Instrument rows prevent an exact 32-Job Final-ABI or independent-validity rate. Ratios over
the 22 model outcomes are descriptive only and cannot replace the missing ten outcomes.

## Provider And Privacy-First Lineage

The run materialized 179 Provider Envelopes and 179 Public Payload Projections. Every Envelope
was atomically persisted before its corresponding Projection. The complete partition is:

| Provider/Projection outcome | Calls |
| --- | ---: |
| HTTP success | 177 |
| complete exact-model, Thinking, and Usage telemetry | 169 |
| validated public payload | 168 |
| `provider_failure_no_payload` | 11 |
| privacy rejected | 0 |
| Envelope-only orphan | 0 |
| Projection-only orphan | 0 |
| total Provider artifacts | 179 |

One of the eleven no-payload Projections was an invalid-JSON channel parse failure with complete
response model, Thinking, and Usage telemetry. It used the bounded ABI path and did not cause an
Instrument terminal. The remaining ten no-payload Projections are the terminal Instrument calls
localized below.

Across the 169 complete telemetry rows, all calls requested, selected, and returned exact
`deepseek-v4-flash`; Thinking presence, length, and token telemetry were positive; Usage was
complete; Provider-native tools were absent; and fallback and model discovery were zero. The ten
failed calls retained insufficient response telemetry, so the aggregate exact-model, Thinking,
native-tool, and Usage Gates correctly fail rather than inferring missing values.

Artifact-backed Provider Usage is:

| Usage | Tokens |
| --- | ---: |
| Prompt | 538,841 |
| Completion | 264,115 |
| Reasoning | 243,484 |
| total | 802,956 |

Estimated artifact-backed cost telemetry is USD `0.14938994000000001406`. These are lower bounds
on actual Provider consumption because the eight HTTP-200 incomplete-body calls retained no
Usage. The audit does not infer missing Usage or cost.

Private reasoning content and hashes, Raw HTTP bodies, Raw request bodies, rejected payload
content, and rejected payload keys remain absent. Whole-response public-content hashes retain
the privacy semantics frozen by v26.123 and are not private-reasoning field hashes.

## Instrument Failure Localization

The ten Instrument failures are separately content-addressed recovery Candidates. Every failed
call was the last persisted call of its historical Raw Execution and was a Semantic Action
Primary with both recovery counters still at zero.

| Observable failure | Jobs | HTTP status | Complete successful prefix calls |
| --- | ---: | --- | --- |
| `IncompleteRead` while reading response body | 8 | 200 | 0-2 |
| connection-refused `URLError` | 2 | none | 0 |

The failed call-index partition is four at index 0, two at index 1, and two at index 2 for the
`IncompleteRead` rows, plus two at index 0 for `URLError`. The successful prefixes retain 0 to
15,639 reported tokens and are complete, exact-model, public-payload lineages.

The eight HTTP-200 failures are not model payload failures: no response body, response model,
Thinking telemetry, Usage, or public-content hash was available to the wrapper. The two
connection-refused failures have no HTTP response. `IncompleteRead` and `URLError` are the exact
observable wrapper exceptions; the evidence does not uniquely attribute either class to the
Provider service, network, proxy, or local transport stack.

There is no orphan and no privacy-order regression. Each failed call has both its redacted
Envelope and generic no-payload Projection, and each historical Job has a complete Raw terminal.
The blocker is replacement-response authority after an exact failed call, not Raw persistence.

## Semantic Action Funnel

Across all 32 Raw Executions, including successful prefixes of Instrument Jobs, the Action funnel
is:

| Stage | Count |
| --- | ---: |
| Provider calls | 179 |
| Primary attempts | 171 |
| ABI Rescue attempts | 7 |
| Semantic Recovery attempts | 1 |
| public Semantic payloads | 141 |
| exact four-field Action payloads | 140 |
| Semantic Choices | 140 |
| visible action and Decision-kind matches | 140 |
| accepted Primary choices | 138 |
| reversible Stage 2 Commits | 139 |
| public Observations | 117 |
| successful / failed Observations | 114 / 3 |
| public-progress choices | 102 |
| Program-node-progress choices | 34 |

The one Action ABI failure used the bounded ABI Rescue. One semantic rejection used the separate
Semantic Recovery, committed, selected the same public action, and made no immediate public
progress. The first failure remains recorded. Stage 2 made zero Provider calls and inserted no
semantic choice.

Candidate counts 1/2/3/4/5/6/8 occurred in 46/16/31/14/6/19/8 choices. Ninety-nine choices
selected the Prompt-only reference and 41 selected a legal non-reference Candidate. These are
reached-state associations under one online run, not Candidate-load, position, or causal model
effects.

Within the 22 complete model outcomes, there were 134 Choices, 133 Commits, 111 Observations,
108 successful Observations, 100 public-progress choices, and 34 Program-node-progress choices.
All 22 then closed the Program, completed the terminal node, succeeded at terminal verification,
and committed Final. Thus the Canonical Semantic Action chain remains strongly positive for the
observed model-outcome subset, while no claim is made for the ten Instrument-censored Jobs.

## Exact Final Funnel

The 22 model outcomes made 22 Final Primary and five Final Rescue calls. All 27 public payloads
had exactly the top-level keys `answer` and `rationale_summary`, confirming that Primary, Rescue,
and parser now expose the same outer field set.

The decisive inner-type partition is:

| Final result | Attempts | Jobs |
| --- | ---: | ---: |
| `answer` is an object and exact Grammar passes | 17 | 17 |
| `answer` is a string and exact Grammar rejects | 10 | 5 |

The five failing Jobs returned a string-valued `answer` in both Primary and the one permitted
Final Rescue. They are model response-following failures under the aligned shared Grammar, not
the v26.120 Instrument mismatch. No Rescue response crossed the exact Final Grammar.

All 17 exact Final payloads emitted a completed answer. Independent Verifier v2 results are:

| Verifier result | Jobs |
| --- | ---: |
| fully valid | 11 |
| answer projection only failed | 3 |
| target mechanism only failed | 3 |
| citation failed | 0 |
| Evidence support failed | 0 |

For each of the six exact-ABI invalid results, exactly one frozen Verifier check failed. Runtime
Replay, model-input noninterference, Tool authority, Operation lineage, Evidence support,
terminal verification, Citation, and post-completion control passed. This preserves the intended
separation:

```text
exact Final serialization != independent semantic validity
```

The descriptive 22-model-outcome endpoint is therefore 17 Final-ABI crossings and 11 fully valid
answers. It is not an exact 32-Job endpoint estimate because the ten Instrument Jobs did not reach
a model terminal.

## Resource And Authority Results

No Job reached or exceeded the 400,000-token rollout ceiling. The 22 model outcomes used
20,846-56,702 reported tokens each and retained 343,298-379,154 tokens of headroom. Typed
budget no-calls and Completion-unusable terminals were zero. The observed result provides no
support for changing the 16,384 Completion bound, 400,000 rollout bound, Action protocol,
Candidate set, Final Grammar, model, Thinking profile, or recovery counts.

The run remains engineering calibration over repeated engineering sources. Capability,
Reachability, State Mapping, training, release, and production rows are all zero. The 11 valid
trajectories cannot enter any downstream scientific denominator.

## v26.125 Independent Audit

Before reading an execution result, v26.125 replayed 2,965/2,965 files:

| Source partition | Files |
| --- | ---: |
| v26.124 transitive source bindings | 2,562 |
| immutable v26.124 execution files | 402 |
| exact v26.125 implementation | 1 |
| total | 2,965 |

It reparsed 32 Job results, 32 checkpoint rows, 32 Raw Executions, 179 Envelopes, 179 Projections,
and every descriptor. It independently rebuilt all 32 Verifier v3 Replays and all 17 completed
Final verification reports. Parent identities, canonical bytes, Usage, cost, privacy fields,
terminal counts, and Stage 2 zero-call counts reproduced.

The audit reconstructed every Final Host Envelope from the public Final Commit, reparsed all 27
Final payloads through the frozen shared parser, and independently reproduced the 17/10
object/string partition, five Final-Grammar failure Jobs, 11 valid answers, three
answer-projection failures, and three target-mechanism failures.

Ten destructive transition mutations failed closed with zero Provider and Stage 2 Provider
calls. Formal and independent builds produced all seven v26.125 outputs byte for byte. The
focused v26.125 deterministic test passed 1/1 in 7.44 seconds. The selected v26.122-v26.125
adjacent regression passed 5/5 in 108.10 seconds; focused Ruff format/check and Mypy passed.
v26.125 made zero credential lookups, model-client constructions, Provider calls, GPU jobs,
empirical rows, or historical reclassifications.

## Authoritative Identities

The v26.124 identities are:

- execution report:
  `finance_v26_exact_final_semantic_action_execution_report:39098697c35cd453f68ddc546cb1bd8cc0d0e9e3d2c8552fc9ff49cbf9794eb3`;
- source replay:
  `finance_v26_exact_final_execution_source_replay:202f2394e2a20d2edd5062b5186f8de875b4bb621a68bc4569fe874ea64d2a01`;
- preexecution validity:
  `finance_v26_exact_final_preexecution_validity:52e2c4627f33a6ccbde12d72bb64aeea280c919fa92ddd4003b3bd62023583e6`;
- Raw Lineage:
  `finance_v26_exact_final_raw_lineage:b073a2121fc1a124dc5d59acbac6edee667ade25a59f6b3d15b183b52d993977`.

The v26.125 identities are:

- report:
  `finance_v26_exact_final_postrun_audit_report:76852aa99e92673608e44286d2545dee0062246a47d29c7254053dfb8e560c03`;
- source replay:
  `finance_v26_exact_final_postrun_source_replay:5e6503a95107ffbcd15861ae1e2f87d825782cb81b4a84a0df70b26796ead3e7`;
- Raw Lineage reaudit:
  `finance_v26_exact_final_raw_lineage_reaudit:62d7d1d8367b6fd7c2feb3757bffcaa0833f5e1c01e379df9f8dac0e880b5ab2`;
- Provider failure audit:
  `finance_v26_exact_final_provider_failure_audit:e0633b4f618be2967f5eb6b63c1e7dc8c00eac39b94d05c3804deb9613c2b20a`;
- Final outcome audit:
  `finance_v26_exact_final_outcome_audit:2b4be11014691894bf0a7f87a3575da2ff0adde9c1af770763b589dd7b9406c2`;
- destructive audit:
  `finance_v26_exact_final_postrun_destructive:91f795d8d2b34affed584aefa8c14c801802d95aa8f3ac3912b20fd28c1f5c26`;
- transition:
  `finance_v26_exact_final_postrun_transition:2ee5689a7248012a676e993f37df6bfca0a432579e5787334ae6a990d2439524`.

## Prospective Transition

The only permitted transition is:

```text
fresh_exact_failed_call_transport_recovery_contract_and_runner_preflight_only
```

The successor may materialize exactly ten fresh RecoveryJob identities, one for each frozen
failed-call Candidate. It must replay each exact successful prefix with zero Provider calls,
rebind the exact failed request and all dynamic/request/resource certificates, preserve the
historical recovery counters and remaining 400,000-token resource bound, allow at most one
replacement response for that exact failed call, and continue only under the original Action,
Final, model, Thinking, Completion, Candidate, and recovery contracts.

The preflight itself authorizes no Provider call. It must prove zero-generation recovery of every
successful prefix, exact failed-request identity, single-use replacement authority, Raw-first
Envelope/Projection persistence, complete continuation/aggregation behavior, orphan blocking,
and no Stage 2 Provider route before a later execution can be considered.

The 22 completed model outcomes are preserved and may not be rerun or reclassified. The ten
historical Instrument terminals also remain immutable; a future RecoveryJob may produce a fresh
successor outcome but cannot rewrite v26.124. Historical v26.120 or v26.124 Job rerun,
continuation under an old Job identity, Action/Final Grammar or Candidate changes,
model/Thinking/Completion/rollout/recovery changes, Host semantic repair, role experiments, State
Mapping, training, release, and production Contribution remain forbidden.

This transition addresses an Instrument recovery boundary only. It does not treat the five
string-valued Final failures or the six independently invalid exact Final answers as retryable
Instrument defects.
