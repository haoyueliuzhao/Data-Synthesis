# Finance v26.126-v26.128 Exact Failed-Call Transport Recovery And Kernel Freeze

Audit date: 2026-08-23

## Decision Summary

Finance v26.126 consumed only the credential-free recovery-preflight transition frozen by
v26.125. It materialized exactly ten fresh RecoveryJobs, one for each v26.124 failed-call
Candidate, and implemented a continuation Runner that replays each successful historical prefix
with zero Provider calls. The first new call is bound to the exact failed Prompt, public state,
dynamic certificate, request-body certificate, resource certificate, and recovery counters. Each
RecoveryJob permits at most one such replacement; a replacement Transport failure stops the fresh
Job and cannot trigger another replacement.

The v26.126 preflight passed. All ten prefixes and exact failed requests reconstructed, all ten
scripted continuations reached independently valid Final results, the replacement-failure,
combined ABI-plus-semantic-recovery, Usage-boundary, privacy-order, Raw-only recovery, orphan, and
16 destructive controls passed, and an independent build reproduced all ten outputs byte for
byte. The stage made zero real Provider calls.

Finance v26.127 then consumed only that exact ten-RecoveryJob online authorization. All ten first
replacement calls were HTTP successes within 65 total successor Provider calls. Every RecoveryJob
reached a model terminal: eight independently valid trajectories and two model-invalid
trajectories. Transport, Instrument, Completion-unusable, typed no-call, privacy, Stage 2 Provider,
fallback, discovery, exact-model, Thinking-continuity, and Usage failures were zero.

The fresh successor calls used 291,572 Provider-reported tokens and estimated cost telemetry of
USD `0.04867940560000000394`. The successor does not impute Usage for any original failed call.
Combining only persisted v26.124 telemetry with fresh successor telemetry gives an observable
billing lower bound of 1,094,528 tokens and USD `0.19806934560000001800`; the eight historical
HTTP-200 incomplete-body calls still have unknown Usage and cost.

Finance v26.128 independently replayed 3,134 files and reconstructed all ten Recovery outcomes
with zero Provider calls. The exact model-endpoint denominator is now complete:

```text
22 frozen v26.124 model outcomes + 10 fresh v26.127 Recovery outcomes = 32 model endpoints
```

All 32 closed the Program, completed the terminal node, succeeded at terminal verification, and
committed Final. Twenty-six crossed the exact Final ABI and nineteen were independently valid.
The remaining thirteen are model-invalid results, not Instrument failures. The audit freezes the
exact engineering Kernel and authorizes only fresh, model-unexposed Capability and Reachability
Population construction, Kernel binding, and a complete credential-free role Runner preflight.
It authorizes no role Provider call, State Mapping, training, release, or production
Contribution.

## v26.126 Recovery Authorization

The predecessor transition was:

```text
fresh_exact_failed_call_transport_recovery_contract_and_runner_preflight_only
```

Before constructing a Recovery identity, v26.126 replayed 2,973/2,973 files:

| Source partition | Files |
| --- | ---: |
| v26.125 transitive source bindings | 2,965 |
| immutable v26.125 output files | 7 |
| exact v26.126 implementation | 1 |
| total | 2,973 |

No credential lookup, model-client construction, Provider call, Stage 2 Provider call, GPU job,
empirical row, or historical reclassification occurred.

The ten RecoveryJobs bind the ten exact v26.125 Candidates. RecoveryJob identity overlap with the
historical v26.124 Job identities is zero. Each RecoveryJob retains:

- the complete historical FinalGrammarJob as an immutable parent;
- the historical Raw Execution identity and exact-byte descriptor;
- the historical Job-result identity;
- the exact failed Envelope and Projection identities;
- the failed Prompt hash and old dynamic/request/resource certificate identities;
- the successful-prefix call and token counts;
- the ABI Rescue and Semantic Recovery counters before failure;
- one replacement-response authorization and zero historical-prefix call authorization.

The Recovery Contract explicitly separates trajectory accounting from Provider billing. The
continued trajectory begins with reported Usage from successful historical prefix calls. It does
not include or estimate Usage from the original failed call. The fresh successor Provider ledger
starts at zero calls and zero successor Usage while the trajectory ledger starts at the certified
prefix count and Usage.

## Successful-Prefix Replay

The historical prefix partition was:

| Successful prefix calls | RecoveryJobs | Rebuilt calls/Observations |
| ---: | ---: | ---: |
| 0 | 6 | 0 |
| 1 | 2 | 2 |
| 2 | 2 | 4 |
| total | 10 | 6 |

The six successful prefix calls retained 42,961 reported tokens. For every prefix call, v26.126
independently rebuilt the exact public state and candidate-presentation salt, rendered the exact
Primary Prompt, reparsed the historical public payload, reevaluated the selected action, rebuilt
the reversible Commit, reran the deterministic public Tool call, and matched the historical
Choice, Commit, and Observation objects exactly.

At the failed state, the audit independently rebuilt the old request-body, dynamic, and resource
certificates. All ten Prompt hashes, public-state identities, dynamic certificate identities,
request certificate identities, resource certificate identities, recovery counters, and
cumulative prefix Usage values matched the frozen Candidates. Historical prefix calls reissued,
historical failed calls reissued, and original failed Usage imputations were all zero.

## Recovery Runner Boundary

Every authorized call has two simultaneous bindings:

1. the unchanged historical request route, including the original Runner Job, public state,
   Prompt, request body, and resource arithmetic;
2. a fresh RecoveryInvocationCertificate parented to the RecoveryJob and Recovery Runner.

For the first successor call, the invocation certificate additionally requires exact equality to
the failed Candidate. Its `exact_failed_call_replacement` flag is true only at successor call
index zero. Later calls are ordinary continuation Primary, ABI Rescue, Semantic Recovery, Final
Primary, or Final ABI Rescue calls under the original limits.

The new Provider Envelope is parented to the RecoveryJob. It retains the fresh invocation
certificate, unchanged old dynamic and request certificates, resource certificate identity,
response model, finish/status telemetry, Usage, Thinking telemetry, and public content
hash/length. It retains no response payload, private reasoning content or hash, Raw HTTP body, or
Raw request body. The separate public Projection is written only after the Envelope.

A replacement Transport failure is terminal for the RecoveryJob. It is not eligible for ABI
Rescue and cannot request a second replacement. Completion or public serialization failure after
an HTTP-success replacement remains subject to the original single global ABI Rescue. Typed
semantic rejection remains subject to the separate original single Semantic Recovery. Stage 2
has no Provider route.

## v26.126 Credential-Free Controls

The ten-Job scripted control made 74 local successor calls. Every RecoveryJob used one exact
failed-call replacement, completed its preserved Compiler trajectory, crossed one exact Final
payload, and passed Replay v3, independent validity, mechanism scoring, privacy pairing, and
zero-Provider Stage 2.

The additional controls established:

| Control | Result |
| --- | --- |
| replacement Transport failure | one call, terminal failure, zero second replacement |
| malformed replacement | one original ABI Rescue only |
| subsequent unknown action | one separate Semantic Recovery only |
| Completion Usage 16,384 | admitted |
| Completion Usage 16,385 | admitted and fully charged |
| Completion Usage 16,386 | Instrument failure; no later call |
| original failed Usage | never imputed |
| Envelope/Projection order | Envelope first for every call |
| complete Raw replay | byte-identical, zero calls |
| orphan Envelope | retry blocked before client behavior |
| destructive mutations | 16/16 rejected with zero calls |

Formal and independent v26.126 builds reproduced all ten output files byte for byte. Focused Ruff
format/check and Mypy passed. The focused v26.126-v26.128 test set later passed 4/4.

The v26.126 transition was:

```text
exact_failed_call_transport_recovery_execution_only
```

It authorized only the exact ten-RecoveryJob Manifest.

## v26.127 Preexecution Replay

Before credential lookup or client construction, v26.127 replayed 2,984/2,984 files:

| Source partition | Files |
| --- | ---: |
| v26.126 transitive source bindings | 2,973 |
| immutable v26.126 output files | 10 |
| exact v26.127 implementation | 1 |
| total | 2,984 |

It then repeated all ten successful-prefix and exact failed-request checks. The preexecution audit
made zero calls and bound:

```text
finance_v26_recovery_preexecution_audit:4bd9109c35ee3a5baad5e07015ab498174f52cda4520c0fe75f850608b38200e
```

The online process started from 0/10 with eight workers, zero Raw recovery Jobs, and the exact
credential from the process environment. It opened no historical Job and sent no historical
successful-prefix request to the Provider.

## v26.127 Online Execution

All ten RecoveryJobs completed. The terminal partition is:

| Terminal | RecoveryJobs |
| --- | ---: |
| `model_valid_trajectory` | 8 |
| `model_invalid_trajectory` | 2 |
| Transport failure | 0 |
| Instrument failure | 0 |
| Completion unusable | 0 |
| typed no-call | 0 |
| total | 10 |

The successor call-count distribution was:

| Successor calls | RecoveryJobs |
| ---: | ---: |
| 5 | 2 |
| 6 | 5 |
| 7 | 1 |
| 9 | 2 |
| total calls | 65 |

All 65 calls returned HTTP success. Every call requested, selected, and returned exact
`deepseek-v4-flash`; retained positive Thinking telemetry and complete Usage; explicitly retained
Provider-native-tool absence; and used zero fallback or model discovery. Every first successor
Envelope bound the exact failed Candidate. No RecoveryJob requested a second replacement.

Fresh Provider Usage was:

| Usage | Tokens |
| --- | ---: |
| Prompt | 206,081 |
| Completion | 85,491 |
| Reasoning | 77,657 |
| total | 291,572 |

Estimated fresh cost telemetry was USD `0.04867940560000000394`.

The ten combined trajectories contain 71 attempts: six replayed historical prefix attempts and 65
fresh calls. They produced 60 Semantic Choices, 60 reversible Commits, 50 Observations, 49
successful Observations, zero semantic rejections, ten Final requests, and one ABI Rescue. The ABI
Rescue corrected one Action serialization failure. Semantic Recovery use was zero. All ten closed
the Program, completed the terminal node, succeeded at terminal verification, and committed
Final.

Nine Final payloads crossed the exact shared Grammar. Eight were independently valid. The first
model-invalid successor had already used the one global ABI Rescue on an Action serialization
failure; its later Final Primary returned exactly the two outer keys but used scalar
`answer="0.00"`. With no second global ABI Rescue available, it ended
`final_response_not_exact_shared_grammar`.

The other model-invalid successor crossed the exact Final ABI and emitted the correct normalized
answer with complete Evidence, Citation, Operation lineage, Replay, and terminal verification.
It was a Failure Recovery mechanism task, but no typed failure, selector revision, or recovery
success event occurred. The target-mechanism check therefore failed. Neither outcome is a
Transport or Instrument defect, and neither supports a Grammar, Candidate, resource, model, or
recovery-bound change.

## Billing And Resource Accounting

The billing telemetry boundary remains intentionally asymmetric:

| Partition | Observable tokens | Cost telemetry |
| --- | ---: | ---: |
| persisted v26.124 artifacts | 802,956 | USD 0.14938994000000001406 |
| fresh v26.127 successor calls | 291,572 | USD 0.04867940560000000394 |
| observable combined lower bound | 1,094,528 | USD 0.19806934560000001800 |

The eight original HTTP-200 incomplete-body calls have unknown Usage. The two original no-HTTP
calls also retain no Usage. The recovery report does not assign zero Usage to either class and
does not add an estimate to the billing lower bound.

Trajectory resource accounting is different. Each recovered trajectory starts with only its
successful prefix Usage and then charges each fresh successor response. The original failed call
is replaced for trajectory accounting and remains unknown for billing accounting. Every recovered
trajectory remained under the unchanged 400,000-token ceiling.

## v26.128 Independent Audit

Before reading an outcome as authoritative, v26.128 replayed 3,134/3,134 files:

| Source partition | Files |
| --- | ---: |
| v26.127 transitive source bindings | 2,984 |
| immutable v26.127 execution files | 149 |
| exact v26.128 implementation | 1 |
| total | 3,134 |

It independently reparsed ten checkpoint rows, ten Job results, ten Recovery Raw Executions, 65
Recovery Envelopes, 65 public Projections, all six historical prefix calls, and every descriptor.
It rebuilt all ten exact replacement bindings, Replay v3 results, Program and terminal progress,
Final ABI outcomes, independent verification outcomes, and terminal classifications.

The independent result matched 10/10 formal rows. Envelope and Projection identities were unique
65/65; privacy payloads, rejected-content persistence, rejected-key persistence, original failed
Usage imputation, and Stage 2 Provider calls were zero. All 140 Raw-lineage files matched their
content descriptors.

Formal and independent v26.128 builds reproduced all nine outputs byte for byte. Twelve
post-run destructive mutations failed with zero Provider or Stage 2 Provider calls. Focused Ruff
and Mypy passed.

## Exact 32-Endpoint Result

The independently reconstructed complete endpoint denominator is:

| Endpoint result | Historical v26.124 | Fresh v26.127 | Combined |
| --- | ---: | ---: | ---: |
| model endpoints | 22 | 10 | 32 |
| independently valid | 11 | 8 | 19 |
| model invalid | 11 | 2 | 13 |
| exact Final ABI crossed | 17 | 9 | 26 |
| exact Final ABI failed | 5 | 1 | 6 |

All 32 closed Program, completed the terminal node, succeeded at terminal verification, and
committed Final. Among the 26 exact Final ABI crossings, nineteen were independently valid and
seven were semantically invalid. The exact endpoint-valid fraction is `19/32 = 0.59375`.

This is an engineering-calibration result over repeated engineering sources. It is positive
evidence that the frozen Agent generation chain can produce complete, independently valid
trajectories and that exact failed-call Transport Recovery can close an Instrument-censored
model-endpoint denominator. It is not Capability or Reachability evidence, and none of the 32
rows is eligible for State Mapping, training, release, or production Contribution.

## Engineering Kernel Freeze

v26.128 freezes the following Kernel for fresh role preflight:

- Canonical Semantic Action protocol and exact four-field Action Grammar;
- complete Candidate authority;
- exact two-field Final Grammar and Host Envelope;
- exact `deepseek-v4-flash` Thinking-enabled 16K Stage 1 profile;
- deterministic zero-Provider Stage 2 profile;
- 16,384 request Completion bound with the one-token accounting margin;
- 400,000-token rollout ceiling;
- one global ABI Rescue and one separate Semantic Recovery;
- privacy-first Envelope then public Projection persistence;
- one exact Transport replacement only after a fresh pre-call authority certificate;
- Raw-only recovery, orphan blocking, and no private reasoning persistence.

The Kernel Freeze qualifies only fresh role Population construction, binding, and Runner
preflight. It does not make repeated engineering sources role-eligible and does not authorize a
role Provider call.

## Authoritative Identities

The v26.126 identities are:

- report:
  `finance_v26_transport_recovery_preflight_report:3728c94bbdbf5d676269f1460c07d826ad8e444693b0178d20584e4a61010c62`;
- source replay:
  `finance_v26_transport_recovery_source_replay:e901da4ebe91bdd9d846d44dac1fc8fc12a9dcfa0b46263b1fa79bb4cd9df83e`;
- Recovery Contract:
  `finance_v26_exact_failed_call_recovery_contract:b41d20f95d1c4245efc1a0468bb2d4161dfec0d2054f6812e68c2a262011048d`;
- Recovery Manifest:
  `finance_v26_exact_failed_call_recovery_manifest:2e92bca0b3afc2081f6fa8e0ad5708ce3ae9b83a8ce451a108e17888301eb857`;
- Recovery Runner Contract:
  `finance_v26_exact_failed_call_recovery_runner_contract:8278ce674c4c097d59341bab28ccf9b8820b5d464739c16e6a2bae02dc7786a6`;
- transition:
  `finance_v26_transport_recovery_runner_transition:d54808d4d5523989466f0225892f0f037dbf312e93d0b6e17a40af16d0eb1eec`.

The v26.127 identities are:

- execution report:
  `finance_v26_transport_recovery_execution_report:df1540cbc8ef04a42b45ee3e683f502ee0956d83ed7344a35ad2c4254c4c1989`;
- source replay:
  `finance_v26_recovery_execution_source_replay:15e4d107714efd56fdbd78dfb99f635a9050e33527392d88170d4e1d150ee4ff`;
- preexecution audit:
  `finance_v26_recovery_preexecution_audit:4bd9109c35ee3a5baad5e07015ab498174f52cda4520c0fe75f850608b38200e`;
- Raw Lineage:
  `finance_v26_transport_recovery_raw_lineage:c2f0001f130b61265770783e2f2a4c710c3140d2798bcde6bdef7b2817411f18`.

The v26.128 identities are:

- report:
  `finance_v26_transport_recovery_postrun_audit_report:e923f02843376424c783cb47a1e3f59f7704426f2b151f1432c65408e8c4731f`;
- source replay:
  `finance_v26_transport_recovery_postrun_source_replay:80c28ec93ffa9a698a25c6a8b99053ce504e465fff66891cf225f862605ab797`;
- Raw Lineage reaudit:
  `finance_v26_transport_recovery_raw_lineage_reaudit:6d24cf1e8df94a3ac606621e51834b03d5bc576b76fe311d8340dadfa0ab0d42`;
- Transport Recovery outcome:
  `finance_v26_transport_recovery_outcome_audit:256cef4abbbabdbedcae489ef2b46e7b8745ced6e4f07686b2a7fd7b623b57e7`;
- full endpoint outcome:
  `finance_v26_full_model_endpoint_outcome_audit:3f56aca7916ab6300202c206229add0c6f75a13bb1349b6e7e6e25b62754c5f7`;
- model-invalid localization:
  `finance_v26_recovery_model_invalid_localization:417afee76086ffd91ad92ee5e43ecce38c3043ab39f74daa63849a3fbf595a94`;
- engineering Kernel Freeze:
  `finance_v26_engineering_kernel_freeze:eab0c2d085b78e77a487077931df58009380d279f74f93fc5aebc627bb523e77`;
- transition:
  `finance_v26_transport_recovery_postrun_transition:adb995a0efd3a04313bd325f80cef2b612492b379f762aad9c88614cc394217a`.

## Prospective Transition

The only permitted transition is:

```text
fresh_unexposed_capability_and_reachability_population_kernel_binding_and_runner_preflight_only
```

The successor may select only fresh model-unexposed source tasks after excluding every historical
engineering, Capability, Reachability, and recovery source and all frozen overlap channels. It
must construct separate Capability and Reachability role Populations, bind each TaskPackage,
Path, Contract, Manifest, Job, and Runner to the exact engineering Kernel Freeze, and complete a
credential-free role Runner preflight before any Provider call.

The role preflight must preserve the exact model, Thinking profile, Semantic Action protocol,
Candidate authority, Final Grammar, Completion and rollout bounds, recovery limits, privacy-first
persistence, exact Transport replacement authority, Raw-only recovery, and zero-Provider Stage 2.
It must keep Capability and Reachability denominators and source Populations separate and permit
only independently valid model-generated trajectories to enter future State Mapping.

Capability or Reachability execution, historical Job rerun or reclassification, repeated
engineering-source reuse, threshold relaxation, post-hoc task deletion, Action/Final Grammar or
Candidate changes, model/Thinking/Completion/rollout/recovery changes, State Mapping, training,
release, and production Contribution remain forbidden.
