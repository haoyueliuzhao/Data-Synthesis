# Finance v26.108-v26.109 Two-Stage Profile, Manifest, And Runner Preflight

Audit date: 2026-08-22

## Decision Summary

Finance v26.108 and v26.109 completed the credential-free transition authorized by v26.107.
The work materializes a fresh two-stage engineering-calibration identity chain and implements its
exact future Runner. It does not execute the online calibration.

The two stages have different authority:

1. Stage 1 is the only model-bearing stage. Exact `deepseek-v4-flash` with
   `thinking.type=enabled` selects a public semantic proposal or the final answer.
2. Stage 2 has no model profile and no Provider route. It deterministically serializes the
   Stage 1 proposal through the frozen public binding table and must reverse to the exact same
   semantic proposal.

The formal v26.109 preflight passes. It authorizes only the exact future 32-Job two-stage
engineering calibration. No role experiment, State Mapping, release, 32K single-stage
escalation, GP-C, training, or production Contribution is authorized.

## Audit Inputs And Frozen Interpretation

The predecessor is the v26.107 Action Constructibility and Verifier v3 result. The successor
preserves its corrected historical interpretation:

- all 382 immutable Calculator calls had a code-defined ready Calculator node;
- only one Calculator call matched the exact public wire contract;
- the 33 valid-JSON response failures split into 22 Decision-stage answers/non-actions, seven
  Prompt echoes, three wrong action enums, and one Final-answer scalar;
- no v26.105 terminal or Completion count is reclassified.

The uploaded design review was used as a prospective implementation review, not as experimental
evidence. The implementation follows its central requirement: fresh Stage profiles and
identities, exact resource closure, model/Instrument separation, a zero-generation Commit stage,
and a full credential-free Runner preflight before any Provider call.

## v26.108 Static Identity Rematerialization

### Source Replay

v26.108 replays 1,884/1,884 files before profile parsing:

- 1,872 v26.107 transitive source bindings;
- all ten v26.107 outputs;
- the new Stage 1 profile;
- the exact v26.108 implementation.

The source replay performs no credential lookup, client construction, Provider call, or GPU job.
Formal and independent builds reproduce all twelve output files byte for byte.

The authoritative source-replay identity is
`finance_v26_two_stage_source_replay:e92ccf8f0859df85097ee99212c0c9dca6130cc3508f77c8173012623177c937`.

### Stage Profiles

The tracked Stage 1 profile is
`config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json`. Its SHA-256 is
`2043fac92b0ef286c368091eb2ec424489dd94e5b6bdf5954810ecdca403615f`.
It freezes:

- provider `deepseek` and exact model `deepseek-v4-flash`;
- `max_output_tokens=16384`;
- exact `thinking.type=enabled`;
- JSON-object response format;
- one model attempt;
- zero generic Contract repairs;
- zero fallback models;
- zero model discovery;
- exact requested-model enforcement;
- Host-instrumented interaction.

The fresh model configuration is
`agent_model_config:05eb110b4269f3a569d24918f356cb905d871aace45b9024c4575295b05a1015`.
Its Thinking binding is
`prospective_thinking_model_binding:5afdd81c4318c89d5c31f9398e77b28822eb338578c2bc3533ed77d6291d33c8`.
The Stage 1 profile identity is
`finance_v26_stage_one_thinking_profile:9d89a504a3fee25a60ae392e10cab063b0604f36fb0672e19bc8f1ec45bb3045`.

The Stage 2 profile binds the exact v26.107 deterministic compiler bytes. It permits no Provider
profile, client construction, semantic choice, or Provider call. Its identity is
`finance_v26_stage_two_commit_profile:024f2543b11f26ebc40000c7342d6ff6b4067d78b3dc11be466514fc765734a5`.

Private reasoning cannot cross from Stage 1 to Stage 2. Stage 2 consumes only the public semantic
proposal and public action-state bindings.

### Completion And Rollout Resource Contract

The exact request remains `max_tokens=16384`. Provider-reported Completion Usage of 16,385 is
admitted only as the previously frozen one-token accounting margin and is fully charged. It does
not reclassify or rescue a length failure. Completion Usage of 16,386 or more is an Instrument
failure.

The two-stage complete-path audit found that the old 240,000-token ceiling would not contain the
deepest preserved path: its upper bound is 246,235. v26.108 therefore freezes a fresh 260,000-token
engineering ceiling from all complete Compiler paths, not from the v26.105 observed no-call
deficits. The exact static result is:

| Item | Result |
| --- | ---: |
| Qualified paths | 48/48 |
| Primary Stage 1 requests per path | 6-10 |
| Maximum Stage 1 calls with one Rescue | 7-11 |
| Maximum Stage 2 Provider calls | 0 |
| Maximum Prompt bytes | 5,317-6,345 |
| Complete-path upper bound | 150,514-246,235 |
| Minimum 260K headroom | 13,765 |

Each Primary semantic request reserves one final-answer request and, until consumed, one global
Rescue. Actual Provider Usage is charged without clipping. An oversized Prompt, request bound,
required reserve, or Stage 1 request-count breach yields a typed no-call before invocation.

The resource Contract is
`finance_v26_two_stage_resource_contract:a54be4f1c8344fc0f35eaef1a73f04136bec872cb4817273b8fb8c7e2b57a0ca`.

### Fresh Task And Job Identity Chain

v26.108 rematerializes:

- 24 TaskPackages;
- 48 Path identities;
- one static execution Contract;
- one Manifest;
- 32 Jobs.

The predecessor source tasks, roles, mechanisms, operational records, Compiler paths, path
strategies, exact Job assignments, and all 32 seeds are preserved. No task or seed is resampled.
All new TaskPackage, Path, Contract, Manifest, and Job identities are disjoint from v26.103.

Every source is already model-exposed. The complete Population is repeated engineering material,
not a fresh Capability or Reachability Population. All 24 sources and all successor Jobs are
ineligible for Capability Support, Reachability Support, State Mapping, State Support, release,
or production evidence.

The 104-row cross-artifact Gate closes 24 TaskPackage, 48 Path, and 32 Job parent chains. It binds
both Stage profiles, the resource Contract, the action protocol, Verifier v3, Contract membership,
Manifest membership, Path parentage, Job parentage, and exact Completion/rollout ceilings. All 30
static destructive mutations fail before Provider behavior.

The authoritative v26.108 identities are:

- report:
  `finance_v26_two_stage_static_preflight_report:5ec8e8c6b22463f7a77fc75cb46b3d13139e6b43c5494fb81fcf106579230c7a`;
- static execution Contract:
  `finance_v26_two_stage_execution_contract:52b63ce8293d9cbfe82f9cc54512b72706edd77ecc135e20e8f9cfce7cc8888b`;
- Manifest:
  `finance_v26_two_stage_manifest:c11af7e8a4bc20e7d136b68c564b98abd884f9310e153d009ef14b80d75d8dd2`;
- cross-artifact audit:
  `finance_v26_two_stage_cross_artifact_binding:db01107e551bc5bf349f51c6a70729fbbfceb330cd973b6ac390f3855e4ef59b`.

v26.108 is a positive static binding result only. It does not implement a Runner and does not
authorize execution by itself.

## v26.109 Exact Runner Preflight

### Source And Request Binding

v26.109 replays 1,900/1,900 files before profile parsing, credential lookup, or client
construction:

- all 1,884 v26.108 transitive bindings;
- all twelve v26.108 outputs;
- four exact v26.109 implementation files.

Its source-replay identity is
`finance_v26_two_stage_runner_source_replay:0fd81bec5ce0bdd1908f9c34e778a579c879172e3cb26bb94b4ef9ee99271e66`.

Every Stage 1 Provider request requires three pre-call certificates:

1. a dynamic certificate binding the actual public state, inferred request kind, Primary Prompt,
   and bounded Rescue when applicable;
2. an exact request-body certificate binding Stage profile, request kind, phase, Prompt hash,
   exact model, `max_tokens=16384`, `thinking.type=enabled`, and JSON response format;
3. a resource certificate binding cumulative actual Usage, current request upper bound, one
   accounting token, final-answer reserve, and remaining one-Rescue reserve.

The prepared authorization is single use. Wrong request kind, wrong phase, changed Prompt,
missing certificate, reused authorization, fallback, discovery, oversized Prompt, insufficient
remaining budget, or an orphan Provider artifact fails closed.

The dedicated Stage 1 client has no uncertified route. It persists privacy-redacted Raw Provider
telemetry before response projection. Private reasoning content and hashes, raw HTTP bodies, and
raw request bodies remain forbidden.

The client-binding audit is
`finance_v26_two_stage_client_binding:7980c5394fc7e210c49e1169b1a382fc69ccd3b27e965b848be453962078b398`.

### Model Result Versus Instrument Failure

The prospective interpretation Contract keeps model behavior and Instrument integrity separate.
The following are model-result failures:

- valid HTTP JSON that does not satisfy the exact semantic-proposal or final-answer schema;
- a final answer during the semantic stage or a proposal during the final stage;
- a public Prompt echo;
- an unknown Tool, unready Node, unavailable Operator, unavailable operand source, or other
  semantic compile rejection;
- repetition of a semantic proposal that already produced a typed public failure.

The Host may use the one global Rescue for a channel Completion failure or a serialization,
phase-control, or Prompt-echo failure. A semantic compile rejection receives no Rescue. A
successful Rescue does not erase the Primary model-failure event.

Malformed or missing Usage, wrong/missing exact model telemetry, certificate mismatch,
Provider-native Tool use, two-or-more excess Completion tokens, Raw-parent mismatch, or Stage 2
Provider behavior is an Instrument failure. Semantic success cannot rescue an Instrument failure.

The nine local model-failure controls contain two serialization, two phase, one Prompt echo,
three semantic compilation, and one duplicate-failed-proposal case. All remain model results and
zero become Instrument failures. The interpretation and audit identities are:

- `finance_v26_two_stage_outcome_interpretation:b0dbdf510758848d0a977d5b56f98dd2f25a7978951f6655408cfa73fbced859`;
- `finance_v26_two_stage_model_failure:d56ce44718909ea24c7a095896a1fdeb9c015d9ef4859a06ee45bb663db09acb`.

### Direct Runner Control

The direct control executes all 32 fresh v26.108 Jobs against preserved Compiler semantics using
a scripted Stage 1 client. It makes no real Provider call and contributes no empirical row.

The exact aggregate is:

| Item | Result |
| --- | ---: |
| Jobs completed | 32/32 |
| Stage 1 logical/scripted calls | 256/256 |
| Dynamic certificates | 256 |
| Exact request certificates | 256 |
| Resource certificates | 256 |
| Stage 2 deterministic Commits | 224 |
| Stage 2 Provider calls | 0 |
| Public Observations | 192 |
| Verifier v3 Replay passes | 32/32 |
| Independent validity controls | 32/32 |
| Mechanism-score controls | 32/32 |
| Raw Execution fixtures | 32 |
| Raw Provider fixtures | 256 |
| Total canonical fixture files | 288 |

Fresh Runtime Observation and time identities are expected. Their semantic projections match the
preserved Compiler Observations exactly, every final answer matches its Compiler answer, and every
Proposal-to-Commit mapping is reversible. These are implementation controls, not model outcomes.

The Runner fixture identity is
`finance_v26_two_stage_runner_fixture:53ea52b029b072291a0e541c6ed5768768b229cf1490aad2904c3ff389b37220`.

### Usage, Recovery, And Destructive Controls

The Usage fixture admits 16,384 and 16,385 reported Completion tokens, charges 16,385 without
clipping, preserves the rule that an accounting margin cannot rescue a length failure, rejects
16,386 as Instrument failure, and blocks Rescue after that Instrument failure. Its identity is
`finance_v26_two_stage_provider_usage_fixture:8e8a6ec6a82712403aa836dc95b8d66d4b0c651ee836a8f8406b96b408a491aa`.

A complete Raw Execution recovers byte-identically with zero Provider calls. An orphan Provider
artifact fails closed. Oversized Prompt, reused request, wrong request kind or phase, and
insufficient remaining budget controls fail before unauthorized behavior. Stage 2 constructs no
client and makes zero Provider calls. The recovery audit is
`finance_v26_two_stage_precall_recovery:b046a78c0a66cb0b7f07869985650072b34237653726b451f6947e032eaf5771`.

All 30 v26.109 destructive mutations fail with zero unauthorized Provider calls and zero Stage 2
Provider calls. The destructive audit is
`finance_v26_two_stage_runner_destructive:872911e6f085be03f9c360c2bd191887d6c492874f2f198681f49154fbce8ac7`.

Formal and independent v26.109 builds reproduce all ten output files byte for byte. The focused
v26.108-v26.109 suite passes 13/13 tests; the adjacent v26.103-v26.109 suite passes 48/48. Focused
Ruff passes for all new source and tests, and focused Mypy passes for the four v26.109 Runner
implementation files. Package-wide Mypy is not a passing Gate in the migrated environment: the
currently installed, unpinned Mypy 2.3.0 reports 6,936 diagnostics across 193 of 419 source files,
including diagnostics in historical Pydantic construction patterns and the already frozen v26.108
builder. This tool-version migration result is recorded without relaxing a rule or rewriting
source-bound evidence. The canonical-root full Pytest suite passes 1,189 tests, with four expected
historical skips and one retained Pydantic destructive-test warning, in 945.66 seconds. The formal
and independent builds perform zero credential lookup, construct zero real model clients, make
zero real Provider calls, use zero GPU jobs, and produce zero empirical rows.

The Runner Contract is
`finance_v26_two_stage_runner_contract:34c9bc91fbab6fb571127a3904b318bf33ca533fa670aa4ca3eccf1de611bac1`.
The authoritative v26.109 report is
`finance_v26_two_stage_runner_preflight_report:1b907cbb962f68dd798764a514db4a4cbf7e3091cfadd35a6702f1e85a0d633b`.

## Authorization Decision

The only permitted transition is:

```text
two_stage_semantic_proposal_calibration_execution_only
```

This authorizes only the exact fresh 32-Job engineering calibration bound by the v26.108 Manifest
and v26.109 Runner Contract. The calibration has not started. It must replay all 1,900 bound files
before credential lookup and client construction, start at 0/32 or recover only complete Raw
Executions, and preserve all source, path, seed, Stage profile, resource, failure-taxonomy,
privacy, and zero-generation Stage 2 bindings.

No historical v26.105 Job may be rerun or reclassified. No v26.108 Job may be replaced,
resampled, or silently switched to 32K. The future two-stage denominator remains engineering-only
and cannot enter Capability, Reachability, State Mapping, State Support, release, or production
evidence.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and production Contribution remain forbidden. Production Contribution
remains zero.
