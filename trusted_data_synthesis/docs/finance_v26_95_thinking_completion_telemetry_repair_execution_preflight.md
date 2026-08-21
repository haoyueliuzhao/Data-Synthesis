# Finance v26.95 Thinking Completion And Telemetry Repair Execution Preflight

Date: 2026-08-21

## Decision

Finance v26.95 completed the credential-free transition authorized by v26.94:

```text
thinking_completion_telemetry_repair_execution_runner_and_preflight_only
```

The preflight passed. It implements and freezes the exact execution Runner for the v26.94
32-Job Thinking Completion and response-telemetry repair Manifest. It does not execute that
Manifest. The formal and independent preflight builds made zero model API calls, constructed no
model client, and used zero GPU jobs.

The authoritative report is:

```text
finance_v26_thinking_repair_execution_preflight_report:986591ddd3b7251cf183f52193bc3868ccec52816cb83715585d76fd4ef07ca5
```

The only permitted transition is:

```text
thinking_completion_telemetry_repair_execution_only
```

This authorizes only one execution of each exact Job in the frozen v26.94 Manifest under the
v26.95 Runner. It does not freeze a Thinking-enabled role protocol or authorize Capability,
Reachability, State Mapping, training, target measurement, or Contribution.

## Frozen Evidence Boundary

v26.95 preserves every v26.94 scientific input:

- the 24 Completion-repair TaskPackages;
- all 48 registered public paths;
- the primary and one-rescue Prompt projections;
- exact `thinking.type=enabled` DeepSeek V4-Flash binding;
- the privacy-redacted response-envelope contract;
- the repair Contract, 32-Job Manifest, Job seeds, and path assignments;
- the 4,096-token Completion bound, 120,000-token rollout ceiling, 60,000-byte Prompt ceiling,
  256-token chat envelope, and frozen reserves.

No v26.92 Job is rerun or reclassified. No v26.94 Compiler fixture is promoted into an empirical
denominator. The 24 v26.90 source role packages remain retired from future Capability and
Reachability execution.

The v26.92 findings also remain separate: zero typed no-calls passed empirical Budget Adequacy for
that historical denominator, while 30/32 Completion-unusable outcomes and the 79-call response
model telemetry gap remain failed historical Gates.

## Source Replay

Before credential lookup and model-client construction, the preflight replayed 498 exact files:

| Source class | Files |
| --- | ---: |
| v26.94 authoritative outputs | 11 |
| v26.94 source-replay bindings | 485 |
| exact v26.95 Runner and preflight implementations | 2 |
| **Total** | **498** |

All 498 expected and observed SHA-256 values matched. The online Runner repeats the same replay,
validates the v26.95 preflight report and all six bound detail-file hashes, and writes only frozen
Contract copies before an execution client can be constructed.

The replay identity is:

```text
finance_v26_thinking_repair_runner_replay:3481b564d08122b4164f6e317cd3d29fff695f6ca5bae6642eaa49527814bb1a
```

## Exact Runner State Machine

The Runner implements the v26.94 protocol directly rather than routing it through the historical
generic JSON-repair loop.

For each logical request:

1. It renders the registered v26.94 primary Prompt from the current public Runtime state.
2. It obtains an explicit request-kind budget certificate before Provider invocation.
3. It captures and persists the privacy-redacted Provider artifact before decision parsing.
4. It strictly validates the response envelope and the compact decision or answer projection.
5. If the failure is one of the five registered Completion failures and the Job has not used its
   rescue, it renders exactly one request-sensitive rescue Prompt and repeats the same pre-call
   and persistence sequence.
6. It either applies the model-selected public action, records the final answer, or emits a typed
   terminal. A second rescue is impossible.

The five rescuable failure types are unchanged:

- `reasoning_only_length_truncation`;
- `length_truncated_content`;
- `empty_final_content`;
- `invalid_json`;
- `invalid_response_contract`.

The rescue receives the current public state and typed failure only. It receives no previous
content, private reasoning, reasoning hash, Host action patch, expected argument, or Host-selected
plan. Provider Plan calls remain zero. The model remains responsible for tool, argument, and final
answer selection.

Transient Provider retries are frozen at zero. Once any Provider artifact exists for a request,
an automatic replay would violate the one-exposure contract. An orphan Provider artifact therefore
fails closed and requires an explicit recovery decision rather than an implicit network retry.

## Budget Closure

The historical budget wrapper inferred request kind from historical Prompt headers. The new
primary and rescue headers are different, so v26.95 introduces an explicit request-kind ledger
rather than silently classifying the new requests as `unknown`.

Every Provider-bearing attempt binds:

- the exact request kind and phase;
- Prompt byte count and conservative Prompt-token upper bound;
- the unchanged 4,096-token Completion bound;
- remaining rollout Usage and required final or rescue reserve;
- the content-addressed certificate preceding Provider invocation.

The fixture audit confirms that all registered request kinds receive valid certificates. An
oversized Prompt is rejected before the delegate is called, and a second rescue is rejected at
Job scope. The removed Provider Plan request remains the source of the single rescue reserve; no
resource ceiling was raised.

## Response Telemetry And Privacy

Every HTTP-success response is reduced to the v26.94 allowed envelope before content parsing:

- response model;
- finish reason;
- public final-content SHA-256 and length;
- explicit Provider-native-tool presence;
- reasoning presence and length;
- reasoning-token and Completion-token Usage.

Private reasoning content, private reasoning hashes, and raw HTTP bodies are not serialized. The
nullable capture preserves fields actually observed even if another envelope field is malformed;
the strict envelope still requires exact model identity, no Provider-native tool, positive
Thinking telemetry, and complete valid Usage. Missing values are never inferred.

Response-envelope failure is an Instrument outcome and is not eligible for Completion rescue.
This separation prevents a telemetry defect from consuming the one public decision rescue or
being misreported as model Completion behavior.

## Persistence And Recovery

Each successful Provider attempt is persisted as a canonical redacted Provider artifact before
projection. A Raw Execution binds the ordered Provider artifacts, Prompts, telemetry, logical
requests, request attempts, Observations, terminal disposition, and budget audit. The persisted
schemas retain no private reasoning payload.

Recovery is raw-only:

- if a complete Raw Execution exists, the Runner revalidates its canonical bytes and identity and
  performs zero Provider calls;
- if no Raw Execution exists but Provider artifacts do, the Runner rejects the orphan state;
- completed checkpoint rows and final aggregation must bind the same Raw Execution identity;
- a completed 32-Job run can be aggregated only after all Raw and Provider files replay.

The local recovery fixture made five first-execution scripted calls, then recovered the same Raw
Execution with zero calls and byte-identical identity. The orphan-artifact control failed closed.

## Replay, Scoring, And Aggregation

The Runner replays every Observation through the authority-preserving Verifier v2 contract. A
completed trajectory is independently scored only from public Runtime state, Observations, the
typed final result, and frozen verifier bindings. Compiler expected actions are never consulted by
the online scorer.

The aggregate keeps separate counts for:

- typed no-call, Completion-unusable, transport, and Instrument terminals;
- exact-model, native-tool, Thinking-continuity, Usage, budget, and Replay failures;
- direct and rescued usable requests and Completion-limit hits;
- repeated calls and repeated failed calls;
- requested-path adherence, Program closure, mechanism success, and independent validity;
- all twelve Mechanism x Path cells and their floor or saturation diagnostics.

All future model-generated rows remain calibration-only. They are ineligible for Capability,
Reachability, State Mapping, or release denominators even if independently valid.

## Outcome Interpretation Contract

The preflight prospectively freezes the post-execution decision rules before any model outcome is
observed. The Contract identity is:

```text
finance_v26_thinking_repair_outcome_interpretation:23f89eddd4bdeefe706134d0a2444076ea68b66a368ad389e79797568a7ad50f
```

The ordered rules are:

1. Any Provider transport failure authorizes only execution recovery or transport audit.
2. Any Instrument failure blocks the empirical interpretation. If every Instrument failure is
   solely a strict `response_envelope_invalid` telemetry failure with budget, Replay, no-native-
   tool, and no-fallback checks passing, only a response-telemetry wrapper repair is permitted.
   Every other Instrument failure requires an Instrument root-cause audit.
3. Any typed no-call authorizes only budget-deviation audit.
4. Any terminal Completion-unusable Job fails the zero-failure Completion Gate. If any length or
   reasoning-only truncation occurred, the next stage must change the Completion bound or adopt a
   true two-stage protocol. Another same-bound Prompt-only retuning is forbidden. A non-length
   Completion failure permits only a Completion-contract root-cause audit.
5. Only zero typed no-calls, zero Completion-unusable Jobs, complete telemetry, and passing
   execution integrity can authorize `thinking_role_protocol_freeze_only`.

Even under rule 5, low Program closure or validity does not reopen Completion-channel tuning. It
is descriptive evidence about behavior, task depth, tools, or Runtime support. A later role
protocol still requires a fresh role Population because all v26.90 role sources were retired by
v26.94.

At 32 Jobs, both typed no-call and Completion-unusable use the same separate zero-failure Gates:

| Failures | One-sided 95% upper bound | Gate at 0.10 |
| --- | ---: | --- |
| 0/32 | 0.08936819898626475 | pass |
| 1/32 | 0.139849460274226 | fail |

Semantic validity cannot rescue either Gate.

## Scripted Runner Controls

The zero-generation Runner audit executes all 32 exact Manifest Jobs using public Compiler paths
and a scripted response client. These are implementation fixtures, not empirical model rows.

| Control | Result |
| --- | ---: |
| Exact Manifest Jobs | 32/32 |
| Scripted Provider calls | 224 |
| Logical requests | 224 |
| Public Observations | 192 |
| Registered primary Prompt matches | 224/224 |
| Compiler-semantic Observation matches | 32/32 Jobs |
| Verifier v2 Replay passes | 32/32 |
| Independent validity controls | 32/32 |
| Mechanism-success controls | 32/32 |
| Mechanism x Path cells | 12/12 |
| Provider Plan calls | 0 |
| Rescue calls in direct controls | 0 |

The full aggregate fixture contains 32 Raw Executions and 224 Provider artifacts, for 256
canonical files. All 224 Provider identities are unique. The scripted report contains 32 valid
terminals, passes every aggregate Gate, and reaches only the prospective transition
`thinking_role_protocol_freeze_only`.

Separate representative controls recover all five Completion failure types with exactly one
rescue. Each uses six Provider calls rather than the five-call direct baseline. A Job with two
Completion failures uses one rescue, ends `completion_unusable`, and reaches the frozen length
redesign transition. A malformed response envelope uses zero rescue, ends `instrument_failure`,
and reaches the wrapper-only transition only under the strict telemetry-only conditions.

## Destructive Controls

All 17 Runner mutations failed closed:

- changed execution or predecessor identity;
- changed Job order, Job seed, or path binding;
- missing source replay or implementation binding;
- a second rescue;
- reintroduced Provider Plan call;
- enabled generic Contract-repair loop or transient retry;
- missing pre-call persistence or explicit request-kind budgeting;
- private reasoning or raw-body persistence;
- previous-content reuse in rescue;
- capability, Reachability, State Mapping, or production authorization;
- same-bound Prompt-only retuning after an observed length failure;
- role-source reuse after a later pass.

The destructive audit identity is:

```text
finance_v26_thinking_repair_runner_destructive:48d88f693fceeba56930ffd7e78d5b5906aa6d9004e3a073707fe93327a9f96a
```

## Determinism And Validation

Formal and independent builds reproduced all seven output files byte for byte. Both builds
replayed 498/498 files, made zero API calls, constructed no model client, and used zero GPU jobs.
The exact Runner also completed a formal `--prepare-only` invocation against the authoritative
preflight with 32 expected Jobs and no client construction.

Validation completed before the final repository-wide run:

```text
Ruff check: passed
Ruff format: passed
Focused Mypy: passed for both new implementation files
Package-wide Mypy: 395 source files checked; one retained v26.70 diagnostic
v26.95 focused tests: 8 passed in 11.77 seconds
v26.88-v26.95 adjacent budget/Thinking tests: 55 passed in 84.73 seconds
Full Pytest: 1,096 passed, 4 expected skips, and 1 retained warning in 856.13 seconds
formal/independent artifact comparison: all seven files byte-identical
Runner prepare-only: 498/498 replayed; zero client/API/GPU
```

## Interpretation And Next Stage

This is a positive execution-Instrument preflight. It establishes that the frozen v26.94 design
has an exact Runner with pre-call budget closure, pre-parse redacted telemetry persistence,
one-rescue enforcement, raw-only recovery, Verifier-bound scoring, complete aggregation, and
prospectively frozen outcome interpretation.

It does not establish empirical Completion usability, control Provider reasoning length, prove
future exact-model integrity, establish Program closure, freeze a role protocol, or support any
Capability, Reachability, State, target, GP-C, or Contribution claim.

The next stage may execute only the exact v26.95 execution Contract and the 32 Jobs inherited
unchanged from v26.94. Each Job may be opened at most once. Any change to a TaskPackage, path,
Prompt projection, rescue policy, response envelope, model profile, Contract, Manifest, Job seed,
resource bound, Runner source, or interpretation rule requires a fresh credential-free preflight
identity.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and Contribution remain forbidden. Production Contribution remains zero.

## Authoritative Identities

- report:
  `finance_v26_thinking_repair_execution_preflight_report:986591ddd3b7251cf183f52193bc3868ccec52816cb83715585d76fd4ef07ca5`;
- execution Contract:
  `finance_v26_thinking_repair_execution_contract:78e40804aa6fa489223991a40bd84c68935a1b4ce8aa0de311e2663538a469b2`;
- outcome interpretation Contract:
  `finance_v26_thinking_repair_outcome_interpretation:23f89eddd4bdeefe706134d0a2444076ea68b66a368ad389e79797568a7ad50f`;
- Runner fixture audit:
  `finance_v26_thinking_repair_runner_fixture:ffb29963ef99c11434d3b35499ef234ad3f6adb0f81853593969964e069bf854`;
- budget and recovery audit:
  `finance_v26_thinking_repair_budget_recovery_fixture:7329026c2d41be873a5cb46c018df06ecd22c9b850f1d6cdc0173ebc965d0b41`;
- destructive audit:
  `finance_v26_thinking_repair_runner_destructive:48d88f693fceeba56930ffd7e78d5b5906aa6d9004e3a073707fe93327a9f96a`.

## Authoritative Artifacts

- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_preflight_v1_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_preflight_v1_20260821/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_preflight_v1_20260821/outcome_interpretation_contract.json`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_preflight_v1_20260821/execution_contract.json`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_preflight_v1_20260821/runner_fixture_audit.json`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_preflight_v1_20260821/budget_recovery_audit.json`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_preflight_v1_20260821/destructive_preflight_audit.json`
