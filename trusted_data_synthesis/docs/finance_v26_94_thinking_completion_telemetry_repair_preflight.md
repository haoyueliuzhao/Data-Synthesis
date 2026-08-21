# Finance v26.94 Thinking Completion And Response-Telemetry Repair Preflight

Date: 2026-08-21

## Decision

Finance v26.94 completed the credential-free transition authorized by the v26.93 post-run
audit:

```text
fresh_thinking_completion_and_response_telemetry_repair_preflight_only
```

The preflight passed. It materialized fresh Completion-repair TaskPackage, Contract,
Manifest, Job, and prospective execution identities, but it did not materialize an execution
Runner and did not authorize execution. It made zero model API calls and used zero GPU jobs.

The authoritative report is:

```text
finance_v26_thinking_completion_telemetry_repair_preflight_report:efae8ea77b8b67a48cb0cfd90559df7fd77b313855a6088ee778ab1dc8926689
```

The only permitted transition is:

```text
thinking_completion_telemetry_repair_execution_runner_and_preflight_only
```

## Evidence Boundary

v26.94 treats the v26.92 result as two independent findings:

- the 120,000-token rollout design was empirically adequate for its exact 32-Job denominator,
  with zero typed no-calls;
- the 4,096-token Completion channel was empirically unusable under the v26.92 Thinking and
  Host-JSON protocol, with 30/32 Completion-unusable Jobs.

The preflight does not rerun or reclassify any v26.92 Job. It does not infer the 79 missing
historical response-model values, reinterpret the 30 Completion failures as semantic failures,
or use the six local mechanism successes as empirical support.

The redesign keeps all resource limits unchanged:

| Bound | Frozen value |
| --- | ---: |
| Completion | 4,096 tokens |
| Rollout | 120,000 tokens |
| Prompt | 60,000 UTF-8 bytes |
| Chat envelope | 256 tokens |
| Static per-request margin | 64 tokens |

## Source Replay

Before freezing a new Contract or Manifest, the builder replayed 485 distinct files:

| Source class | Files |
| --- | ---: |
| v26.93 report | 1 |
| v26.93 detail outputs | 6 |
| v26.93 transitive execution/source replay | 371 |
| v26.90 report | 1 |
| v26.90 detail outputs | 24 |
| v26.90 source bindings | 56 |
| v26.90 implementation bindings | 22 |
| v26.94 profile and implementation | 4 |
| **Total** | **485** |

All expected and observed SHA-256 values matched. This replay occurs without credential lookup
or model-client construction.

## Fresh Task Identities

The historical-exclusion pool has no remaining fully fresh Context or Stopping source capacity
after v26.91. v26.94 therefore uses the 24 v26.90 role TaskPackages as model-unexposed static
sources:

- 12 Capability and 12 Reachability sources;
- three sources per role and mechanism;
- zero v26.92 overlap in source task, Semantic Source, and operational TaskPackage identity;
- zero v26.90 empirical Jobs and zero v26.90 Provider calls.

Each source receives a new Completion-repair TaskPackage identity that binds the new Completion
protocol and the v26.93 telemetry-repair Contract. All 24 v26.90 role sources are prospectively
retired from Capability and Reachability execution. They cannot later be used to populate a role
denominator.

This reuse is static-source rematerialization, not historical outcome reuse. No v26.92 model
outcome or Compiler fixture outcome entered task or Job selection.

## Completion Redesign

The new content-addressed Completion protocol is:

```text
prospective_thinking_completion_protocol:4fd11877d7a7ed795efc80e07382cea4dd2ba7c3915bfe05439665301084f5f1
```

### Primary request

The primary request preserves the full v26.90 action-neutral public Context, Operation,
Progress, History, Repair, Stop, verification, tool, and path-condition fields. It changes only
the response surface:

- a decision returns exactly `action`, `tool_id`, and `arguments`;
- a final answer returns exactly `answer`;
- free-text rationale, analysis, and plan summaries are not required.

The Provider Plan call is removed. It is not replaced by a Host-selected plan: the Host plan
attestation has zero Provider calls, zero action-bearing fields, and no materialized Host plan.
The model retains tool, argument, and answer choice.

### Single public decision terminal phase

At most one rescue call is allowed for the entire Job. It is a separately rendered public
decision-terminal phase for one of five typed failures:

- `reasoning_only_length_truncation`;
- `length_truncated_content`;
- `empty_final_content`;
- `invalid_json`;
- `invalid_response_contract`.

The rescue receives the same public state and the typed failure only. It does not receive the
previous final content, private reasoning, a reasoning hash, an action patch, an expected
argument, or a Host-selected next action. It requests immediate compact JSON and explicitly
forbids repeated planning or deliberation.

Its state projection is request-sensitive:

- decision rescue retains instruction, path, unresolved Operation, Progress, selected
  acquisitions, pending search, failures, allowed tools, and any currently required Repair or
  terminal-verification contract;
- final-answer rescue retains the already admitted final Context and answer Observation;
- superseded Operation replay and unrelated Stop metadata are omitted.

Every rescue Prompt is at least 10% shorter than its matching primary Prompt. Across all 324
registered requests, the actual reduction ranges from 730 to 2,959 UTF-8 bytes, or 11.54% to
64.39%. Rescue Prompt sizes range from 1,532 to 6,976 bytes.

This is a prospective protocol condition, not evidence that the Provider will limit private
reasoning. Every rescue call still binds exact `thinking.type=enabled`; its empirical
Completion usability remains unresolved.

## Authority Preservation

The public Compiler trajectories contain 276 decision projections and 48 final-answer
projections. All 324 projections retain the exact Compiler-selected tool, arguments, or answer.
No Host action field is inserted.

Projection rejects:

- early `emit_final` in a decision request;
- unknown response fields;
- Oracle or target fields;
- missing action, tool, arguments, or answer;
- dropping any field outside the three registered non-authority summary fields.

These Compiler projections are static contract fixtures. They contribute zero empirical
Completion, Capability, Reachability, State Mapping, or release rows.

## Response Telemetry Repair

The future-only `ProspectiveThinkingJsonClient` captures a privacy-redacted field set
immediately after parsing the HTTP-success response object and before strict response-envelope
validation or final-content parsing.

The allowed response fields are:

- response model;
- finish reason;
- public final-content SHA-256 and length;
- explicit Provider-native-tool presence;
- reasoning presence and length;
- reasoning-token and Completion-token telemetry.

Private reasoning content, private reasoning hashes, and raw HTTP bodies are not persisted.

The capture has two stages:

1. a nullable redacted capture retains every allowed field that was actually observed;
2. the strict response envelope requires all mandatory values and exact model, no native tool,
   and positive Thinking telemetry.

Thus malformed Usage still fails the strict envelope, while an already observed response model
or Native Tool flag is not discarded. A missing model remains missing and is never inferred.

Reasoning-only truncation, invalid JSON, malformed response envelope, and Provider-native-tool
fixtures all preserve the allowed telemetry. Three typed failure artifacts validate before
serialization. The synthetic private-reasoning string appears zero times in both serialized
failure artifacts and malformed-Usage capture.

The telemetry fixture identity is:

```text
finance_v26_thinking_telemetry_fixture:7fd64ef18be0996c60af31a8a8c378de30439446d8d8e563f7650ea5f5f46566
```

## Static Budget Qualification

All 48 v26.90 paths were replayed byte for byte before the new Prompts were rendered. The path
set contains 324 post-Plan requests:

| Request kind | Count |
| --- | ---: |
| Decision | 276 |
| Final answer | 48 |
| **Total** | **324** |

Every primary request, including the new 64-token static margin, is no larger than its frozen
v26.90 predecessor request bound. The removed Plan request plus the retained historical repair
reserve fund one worst-case rescue. No larger Completion, rollout, or Prompt bound is used.

| Static diagnostic | Result |
| --- | ---: |
| Qualified paths | 48/48 |
| Compiler projections | 324/324 |
| Full-path upper-bound range | 52,898 to 111,966 |
| Minimum rollout headroom | 8,034 |
| Maximum rollout headroom | 67,102 |
| Primary Prompt byte range | 2,776 to 8,369 |
| Maximum Prompt ceiling use | 8,369 / 60,000 |

These are conservative certification bounds, not expected Provider Usage or evidence of
Completion success.

## Contract And Manifest

The repair Contract is:

```text
finance_v26_thinking_repair_contract:573eb1493ad87832eade20407db775b093a7c4168c63bf19113ee5ceb4dd4f72
```

It directly binds all 24 repair TaskPackages, all 48 path audits, the Completion protocol,
v26.93 telemetry Contract, telemetry fixture, exact Thinking model binding, source replay,
role-population retirement, and prospective v26.95 execution identity.

The exact 32-Job Manifest is:

```text
finance_v26_thinking_repair_manifest:56ada3c9430d56c20c6611986cc0fa51f19c3f80fbee3b7b63b07dffddcf5945
```

It covers all 24 TaskPackages and all twelve Mechanism x Path cells:

| Dimension | Frozen count |
| --- | ---: |
| Jobs per mechanism | 8 |
| `structured_direct` Jobs | 12 |
| `search_then_structured` Jobs | 8 |
| `search_then_open` Jobs | 12 |
| Jobs per Mechanism x Path cell | 2 or 3 |

All Job identities and seeds are distinct. Job selection is deterministic from immutable
structure and does not use any model outcome. Each Job may be executed at most once, but
execution is not authorized by v26.94.

At the exact denominator, typed no-call and Completion-unusable remain separate zero-failure
Gates:

| Failure count | One-sided 95% upper bound | Gate at 0.10 |
| --- | ---: | --- |
| 0/32 | 0.08936819898626475 | pass |
| 1/32 | 0.139849460274226 | fail |

Provider transport remains a separate execution-integrity outcome. Semantic validity cannot
rescue either failure Gate.

## Destructive Controls

All 21 mutations failed closed:

- missing or changed response model;
- Provider-native tool call;
- missing Thinking telemetry;
- private-reasoning or raw-body persistence fields;
- a second rescue call;
- previous-content reuse;
- repeated rescue deliberation;
- rescue reduction below 10%;
- reintroduced Provider Plan call;
- unknown response field;
- early final answer;
- Host-selected tool insertion;
- Oracle response field;
- Boolean or numeric Completion-threshold relaxation;
- v26.90 role-population re-enablement;
- execution authorization without a Runner;
- one-token rollout overflow;
- historical source overlap.

The destructive audit is:

```text
finance_v26_thinking_repair_destructive:c26438a31eba3427cca5bc36291d7b1059edb49136599f11a689c6d2c69fc2d8
```

## Determinism And Validation

Formal and independent builds reproduced all eleven output files byte for byte. Both builds
replayed 485 files, made zero API calls, constructed no model client, and used zero GPU jobs.

Focused validation:

```text
Ruff check: passed
Ruff format: passed
Mypy focused source check: passed
v26.94 focused tests: 16 passed in 5.01 seconds
v26.88-v26.94 adjacent budget/Thinking tests: 66 passed in 72.86 seconds
package-wide Mypy: 393 files checked; one retained v26.70 diagnostic
full Pytest: 1,088 passed, 4 expected skips, 1 retained warning in 848.39 seconds
```

Repository-wide Ruff passes. Ruff format check passes for all five new Python files; the
historical formatter baseline is intentionally unchanged.

## Interpretation And Next Stage

This is a positive static preflight for one Completion-repair design. It establishes:

- a fresh empirical identity chain with no v26.92 source overlap;
- a response wrapper that preserves allowed identity telemetry before content parsing;
- a one-rescue protocol that is materially shorter and does not transfer private reasoning;
- static authority preservation and budget feasibility for all 48 paths;
- a balanced, frozen 32-Job prospective Manifest.

It does not establish:

- empirical Completion usability;
- control of the Provider's private reasoning length;
- exact-model integrity for a future online denominator;
- Program closure, Capability, Reachability, or State Support;
- a Thinking-enabled role protocol;
- production Contribution.

The next stage may only implement an exact execution Runner and complete another
credential-free preflight that replays this report, all eleven outputs, the 485 source bindings,
and the exact Runner implementation before credential lookup. Any change to the TaskPackages,
path selection, Prompt projection, rescue policy, response envelope, model profile, Contract,
Manifest, seed, or resource bound requires a new preflight identity.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and Contribution remain forbidden. Production Contribution remains zero.

## Authoritative Artifacts

- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/role_population_retirement_audit.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_completion_protocol.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_repair_task_packages.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_repair_path_audits.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/telemetry_fixture_audit.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_repair_contract.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_repair_job_manifest.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/thinking_repair_freshness_audit.json`
- `artifacts/vtdo_experiment/finance_v26_94_thinking_completion_telemetry_repair_preflight_v1_20260821/destructive_preflight_audit.json`
