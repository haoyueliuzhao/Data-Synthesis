# Finance v26.122-v26.123 Exact Final Grammar And Privacy-First Runner Preflight

Audit date: 2026-08-23

## Evidence Boundary

Finance v26.122 and v26.123 consume only the credential-free repair and preflight transition
authorized by v26.121. They do not rerun, continue, recover, or reclassify any v26.120 Job. The
32 v26.120 Job identities remain retired, and its incomplete empirical denominator remains
unchanged.

The successor preserves the exact Semantic Action protocol, complete Candidate authority,
Candidate presentation behavior, `deepseek-v4-flash` Thinking-enabled Stage 1 profile, 16,384-
token request bound, one-token Provider accounting margin, 400,000-token rollout ceiling, one
global ABI Rescue, one separately bounded Semantic Recovery, and zero-Provider Stage 2. It does
not use a v26.120 outcome to select a source, Path, assignment, seed, Candidate, model, resource
bound, or recovery limit.

v26.122 replayed 2,534/2,534 files before Grammar or identity construction: all 2,523 v26.121
transitive bindings, all nine v26.121 outputs, and two exact implementation files. It performed no
credential lookup, constructed no model client, made zero Provider or Stage 2 Provider calls, used
zero GPU jobs, and created zero empirical rows.

v26.123 then replayed 2,549/2,549 files before profile parsing, credential lookup, or client
construction: all 2,534 v26.122 transitive bindings, all thirteen v26.122 outputs, and two exact
Runner implementation files. It likewise made zero real Provider or Stage 2 Provider calls, used
zero GPU jobs, and created zero empirical rows.

## Shared Exact Final Grammar

One strong Schema now compiles the model-visible Final Grammar, Primary Prompt contract, Rescue
Prompt contract, parser, and typed response rejection. The model payload contains exactly:

```json
{
  "answer": {"result": {}, "citations": []},
  "rationale_summary": "public concise rationale"
}
```

`answer` is a nonempty object and `rationale_summary` is a nonempty string. Both fields are always
present. Missing fields, extra fields, wrappers, multiple objects, and recursively detected
private-reasoning fields fail closed. The Grammar permits no alias normalization and no Host
insertion of either answer or rationale.

The fixed metadata fields `stage`, `protocol`, `terminal_state_id`, and `terminal_commit_id` are
bound in a content-addressed Host Envelope. They are not model-generated fields. Every Final
pre-call certificate binds the exact Host Envelope identity and terminal public-state identity
before Provider invocation. Primary and Rescue use the same Grammar and the same Host Envelope.

The exact identities are:

- response protocol: `prospective_exact_final_response.v1`;
- Grammar:
  `prospective_exact_final_response_grammar:5b1207394aa4088b6e561243580d45997feca8156185d452f21d738683833403`.

Both Prompt renderers include an explicit case-insensitive `JSON` lexical cue required by the
frozen Provider JSON response mode. Rescue receives only the public Final context and one typed
response failure. It does not receive the previous response content, private reasoning, a
reasoning hash, an expected answer, or a Host repair.

## Final Constructibility Control

The credential-free constructibility control traversed all 48 frozen Compiler Paths and their 48
terminal public states. It rendered 48 Primary and 48 Rescue Prompts and then used a fixture that
read only each final serialized Prompt. The fixture did not read an internal expected payload or
the parser Schema.

The control produced:

| Check | Result |
| --- | ---: |
| Final public states | 48 |
| Prompt-only Primary parses | 48/48 |
| Prompt-only Rescue parses | 48/48 |
| Primary/Rescue public semantic projection matches | 48/48 |
| Compiler answer matches | 96/96 |
| Host Envelopes | 48/48 |
| Rescue JSON lexical cues | 48/48 |
| Host answer/rationale insertions | 0 |
| Model-generated stage/protocol/parent fields | 0 |

The largest Primary and Rescue Prompts are 5,152 and 5,286 UTF-8 bytes. All 48 missing-field,
extra-field, wrapper, and private-reasoning mutations fail. Separately, 48 schema-valid wrong
answers pass only the response ABI. They are not treated as semantically valid. This keeps Final
serialization and independent answer validity as distinct measurements.

## Semantic Action Preservation

The Final repair does not alter the action-selection experiment. Across the complete 324-state
static space:

- 324/324 exact action Prompt hashes are unchanged;
- 324/324 exact Candidate presentation orders are unchanged;
- 324/324 Prompt-only reference actions compile to the same reversible Commit;
- the Semantic Action protocol and four-field response Grammar are unchanged;
- Candidate authority remains
  `finance_v26_candidate_space_authority:58dd1803e6802e48a39884097884c5f4f77d606537b31359e1e192c0515c315d`;
- Stage 2 retains the exact same-action reversal requirement and zero Provider route;
- one ABI Rescue and one separate Semantic Recovery remain the only recovery channels.

Source projections pass 24/24, Path projections pass 48/48, and Job assignment plus seed
projections pass 32/32. The model/profile/resource/Final bindings pass across all 104
TaskPackage/Path/Job rows. Selection reads no v26.120 semantic or Final outcome.

## Fresh Identity Chain

v26.122 materializes 24 TaskPackages, 48 Paths, one resource Contract, one execution Contract, one
Manifest, and 32 Jobs under fresh content-addressed identities. TaskPackage, Path, and Job overlap
with v26.118 is zero. Freshness arises from the corrected Final Grammar lineage; no source or Job
is resampled merely to obtain a different identifier.

All 24 Task parent bindings, 48 Path parent bindings, and 32 Job parent bindings pass. The exact
source, Path assignment, Job assignment, and seed projections remain fixed. Twenty destructive
Grammar, identity, authority, resource, recovery, and Stage 2 mutations fail before any Provider
or Stage 2 Provider behavior.

## Resource Qualification

The 16,384-token exact request bound and 400,000-token rollout ceiling are preserved. The resource
Contract charges actual Provider Usage without clipping, admits only the existing one-token
accounting margin, and treats 16,386 or more reported Completion tokens as Instrument failure.

Complete-path qualification includes every Semantic Action Primary, the applicable action ABI
Rescue, one Semantic Recovery, the exact Final Primary, and the exact Final Rescue. The largest
conservative complete-path bound is 366,799 tokens, leaving 33,201 tokens of minimum headroom.
The maximum qualified Prompt sizes are:

| Request | Maximum UTF-8 bytes |
| --- | ---: |
| Action Primary | 17,720 |
| Action ABI Rescue | 17,824 |
| Semantic Recovery | 19,067 |
| Final Primary | 5,152 |
| Final Rescue | 5,286 |

The Runner permits at most eleven Primary logical requests and twelve total Stage 1 Provider
calls. The twelfth position is the one global ABI Rescue; Semantic Recovery replaces an ordinary
Primary phase and does not create a second recovery allowance.

## Privacy-First Capture

v26.123 separates every Provider call into two content-addressed artifacts.

The `PrivacyFirstProviderEnvelope` is atomically persisted first. It contains the exact Job and
request parents, Prompt hash, dynamic request certificate, exact request certificate, resource
certificate identity, response model, status and finish telemetry, complete Usage, Thinking
presence/length/token telemetry, public response content hash, and public response content length.
It contains no response payload, private reasoning content, private reasoning hash, raw HTTP body,
or raw request body.

Only after Envelope persistence does the Runner evaluate the public payload. It then writes one
separate `PublicPayloadProjection` with exactly one of three statuses:

- `validated_public_payload`, containing the validated public payload;
- `privacy_rejected`, containing no payload and only the generic typed rejection
  `public_payload_omitted_after_privacy_rejection`;
- `provider_failure_no_payload`, containing no payload and a generic Provider/Completion failure.

The exact rejected key and rejected payload are not serialized. A privacy rejection is a complete
model-result Raw terminal rather than a deleted call or an Instrument orphan. Its call and resource
denominators remain present. A complete Raw Execution binds exactly one Envelope and one Projection
descriptor per Provider call.

Raw recovery reparses and hashes every referenced Envelope and Projection and makes zero calls.
When a Raw Execution is absent, any existing Envelope or Projection is an orphan and blocks retry
before Provider behavior. This preserves fail-closed recovery while removing the v26.120 case in
which payload privacy rejection itself erased the call telemetry.

## Runner Controls

The 32-Job direct control made 256 scripted Stage 1 calls. These are local fixtures, not Provider
calls or empirical rows. It produced:

| Funnel item | Count |
| --- | ---: |
| Exact four-field Semantic Action payloads | 224 |
| Accepted semantic choices | 224 |
| Reversible Stage 2 Commits | 224 |
| Public Observations | 192 |
| Exact two-field Final payloads | 32 |
| Privacy-first Provider Envelopes | 256 |
| Public Payload Projections | 256 |
| Envelope-before-Projection passes | 256 |
| Program closures | 32 |
| Terminal verifications | 32 |
| Independent-validity passes | 32 |
| Mechanism passes | 32 |

All 256 Envelope/Projection pairs bind the same Provider call, Job, Runner Contract, Prompt,
certificates, model telemetry, Usage, and public content hash/length. Stage 2 Provider calls are
zero.

## Final And Privacy Fault Controls

One Final-interface control deliberately emits a malformed Final Primary. The one global ABI
Rescue receives the same Host Envelope, includes the JSON lexical cue, emits the exact two-field
payload, and completes with independent validity. Host answer/rationale insertion and
model-generated stage/protocol/parent metadata remain zero.

A separate exact-schema wrong-answer control crosses the parser and then fails independent
validity. This proves that ABI admission does not imply answer correctness and that the Host does
not repair a model answer.

One privacy control injects a successful public JSON payload containing a reasoning-classified
key. It produces one privacy-redacted Envelope, one generic privacy-rejected Projection, one
complete model-result Raw Execution, and one zero-call Raw recovery. Response model, finish reason,
Usage, and public content hash/length are retained. Rejected payload content, the exact rejected
key, private reasoning content, and private reasoning hashes remain absent. A separate orphan
fixture is rejected before any call.

The combined recovery control first emits a malformed Semantic Action Primary, uses one ABI
Rescue, then emits an exact four-field but unknown action. That first semantic failure remains a
typed nonterminal rejection. A separate Semantic Recovery selects a different visible action,
Commits, and completes. Immediately before that recovery both counters equal one. The control
exposes no correct action or argument patch.

Usage controls admit 16,384 and 16,385 Completion tokens, fully charge 16,385, reject 16,386 as an
Instrument failure, and block later calls. Oversized Prompt, insufficient remaining budget, reused
preparation, changed certificates, missing Raw parents, payload insertion into the Envelope,
private-reasoning hashes, Host answer insertion, resource/model/recovery changes, and a Stage 2
Provider route all fail closed. All 20 Runner mutations are rejected with zero Provider and Stage
2 Provider calls. Selected Candidate, Grammar, profile, Envelope, Projection-parent, and Job-parent
mutations recompute their content identities before the independent binding check rejects them.

## Outcome Measurement

The prospective online Funnel keeps the following quantities separate:

- exact Semantic Action ABI;
- visible action match and first-choice acceptance;
- reversible Commit and public Observation;
- legal no-progress action and typed semantic rejection;
- first choice and eventual bounded recovery;
- Program closure and terminal verification;
- exact Final ABI and Final answer semantics;
- privacy rejection, Instrument failure, and model outcome;
- terminal independent validity.

A schema-valid wrong answer remains a model outcome. A privacy rejection retains the call and
resource denominator. Eventual recovery cannot erase the first-choice failure. The successor may
not be reported as the same response distribution as v26.120 or v26.114, and this repair alone is
not evidence of a general model-ability increase.

## Reproducibility And Validation

Formal and independent v26.122 builds produced all thirteen outputs byte for byte. Formal and
independent v26.123 builds produced all twelve outputs byte for byte. The focused test module
passed 3/3 tests in 51.33 seconds. The selected v26.117-v26.123 adjacent regression passed 11/11
tests in 186.66 seconds. Focused Ruff and Mypy pass for all four implementation modules and the
new test module.

Both stages made zero real Provider calls, zero Stage 2 Provider calls, zero GPU jobs, and zero
empirical rows. The 256 scripted calls and all injected faults are implementation fixtures only.

## Authoritative Identities

- v26.122 report:
  `finance_v26_final_grammar_rematerialization_report:d33708c242c6b6779c1f3e3c3911f4235abad570363478ab79e82617a37a971c`;
- Exact Final Grammar:
  `prospective_exact_final_response_grammar:5b1207394aa4088b6e561243580d45997feca8156185d452f21d738683833403`;
- Final constructibility:
  `finance_v26_final_grammar_constructibility:cee6e8a2ee9c7eb852f8414a17402b025fd91139a399cc2ee746e1b9eaa15b2f`;
- Semantic Action preservation:
  `finance_v26_semantic_action_preservation:3cfeb8de71713b0a190bbce88edbebe30c6dcc422dae154da2a1ecd7ee15f262`;
- resource Contract:
  `finance_v26_final_grammar_resource_contract:381e18dff5a538c50cc06aaae9c6c81d110d8214b8c7d3800820d4eb3f09e43c`;
- execution Contract:
  `finance_v26_final_grammar_execution_contract:5532a1f1ca600979f7541770606e7ce0a3b65c4a93f88a659e52e14ff7d6e27e`;
- Manifest:
  `finance_v26_final_grammar_manifest:fd4d78efa9374fc3de91ccca1a8242b7a6bee4bdcf4052ac8bbf6428bd95a5ee`;
- v26.123 report:
  `finance_v26_privacy_first_runner_preflight_report:85733321a455b6fe48d7065e85b3e0a77eb40de5a33f9673a41b9b1c2dd808f8`;
- Runner Contract:
  `finance_v26_privacy_first_runner_contract:a1d2c225906c57742340cf34c07e6d8643bbc4ef293bcf357cecd29b13221a66`;
- Final-interface control:
  `finance_v26_exact_final_interface_control:eebc7a11619063b655d9df389ab58b8c61abb657b3d141ae9b7eabf3ad6f9c5b`;
- privacy-first capture control:
  `finance_v26_privacy_first_capture_control:f4d82d980e8a774261222e6dfdeb6aa665cc99e3490b70b4eb329eae485ad4c3`;
- outcome measurement Contract:
  `finance_v26_exact_final_outcome_measurement:60d018f6f0e9701cc2e5860ddad2649882bacbc4b30b30405fa9a764b1e975e9`;
- transition:
  `finance_v26_privacy_first_runner_transition:60ff3fae5eba80f5a2ae7e27a20378e2ac5f1b950fa267a6cdb910df9c640c50`.

## Decision

At the v26.122 freeze, the only permitted transition was:

```text
privacy_first_exact_final_runner_preflight_only
```

v26.123 has consumed that transition. The current and only permitted transition is:

```text
exact_final_semantic_action_calibration_execution_only
```

This authorizes only the exact fresh 32-Job Manifest bound above. It does not authorize a
historical v26.120 rerun, recovery, continuation, or reclassification; another TaskPackage,
Manifest, Job, Runner, or response protocol; a Semantic Action, Candidate, model, Thinking,
Completion, rollout, or recovery change; Host semantic choice, answer insertion, or repair; role
experiments; State Mapping; training; release; or production Contribution.

The positive result is exact static Final constructibility and Runner-Instrument readiness. It is
not an online Flash result, measured Final-answer success rate, privacy-fault prevalence estimate,
capability result, role result, State-support result, release decision, or production evidence.
Production Contribution remains zero.
