# Finance v26.103-v26.104 Thinking 16K Binding And Runner Preflight

Audit date: 2026-08-22

## Decision

Finance v26.103 and v26.104 completed the only credential-free transition authorized by the
v26.102 post-run audit:

```text
fresh_16k_profile_binding_and_provider_usage_contract_runner_preflight_only
```

v26.103 persisted the exact 16,384-token DeepSeek V4-Flash Thinking profile, froze a prospective
Provider Usage semantics Contract, and rematerialized the affected TaskPackage, Path, Completion
Contract, Manifest, and Job identity chain. v26.104 implemented the exact client and Runner and
completed a credential-free preflight with direct, failure, accounting, recovery, orphan, and
destructive controls.

Both stages passed. They made zero real Provider calls, constructed no real model client, used
zero GPU jobs, and produced zero empirical rows. No 16K Completion outcome has been observed.
The only newly permitted transition is:

```text
thinking_16k_completion_calibration_execution_only
```

This authorizes only the exact v26.105 32-Job engineering calibration. It does not authorize
Capability Development, State Reachability, Fresh Confirmation, State Mapping, Student training,
Exact Target, GP-C, or production Contribution.

## Predecessor Evidence

The transition is rooted in the immutable v26.101 execution and v26.102 post-run audit.

The v26.101 exact 8K calibration completed all 32 Jobs after 391 HTTP-success Provider calls. Its
typed-no-call, exact-request, dynamic pre-call, empirical Budget Adequacy, and response-telemetry
Gates passed. Its Completion Usability Gate failed with 28/32 Completion-unusable Jobs. One
additional Job ended as an Instrument failure after an exact 8,192-token request returned
Provider-reported Completion and reasoning Usage of 8,193 tokens.

v26.102 independently reproduced the complete denominator and froze the observable Instrument
root cause:

```text
provider_reported_completion_usage_one_token_over_exact_request_bound
```

The audit did not identify whether this arose from Provider generation semantics or Usage
accounting semantics. It required a narrow future-only Contract that separates the exact request
bound from Provider-reported accounting, charges actual reported Usage, admits only the observed
one-token margin at the Instrument layer, preserves Completion failure classification, and rejects
two or more excess tokens.

The v26.102 transition also selected the already registered 16K candidate:

- candidate:
  `prospective_completion_bound_candidate:6dfb2358d92a7b1e39a8cf741033e43974dad1a77114d01533ef673115a59dc2`;
- exact request Completion bound: 16,384 tokens;
- rollout ceiling: 240,000 tokens;
- Thinking type: `enabled`;
- automatic escalation: forbidden.

No v26.101 Job, response, terminal, or semantic outcome was reused as a v26.103 or v26.104
empirical row.

## v26.103 Source Replay

Before profile parsing or rematerialization, v26.103 replayed 1,221 exact files:

| Source class | Files |
| --- | ---: |
| v26.102 transitive source binding | 1,211 |
| v26.102 output files | 8 |
| v26.103 implementation | 1 |
| persisted exact 16K profile | 1 |
| Total | 1,221 |

All expected and observed SHA-256 values matched. The replay preceded credential lookup, client
construction, task rematerialization, and artifact writing.

The authoritative source replay is
`finance_v26_exact_16k_source_replay:519d67dff2ed232e34c6fa2f2f8facb140015e51c44ebd6cfd5a7b06062f71bb`.

## Exact 16K Profile

The persisted profile is
`config/deepseek_v4_flash_agent_thinking_16k_v1.json`. It differs from the exact 8K profile only
in `max_output_tokens`:

| Field | 8K predecessor | 16K successor |
| --- | ---: | ---: |
| `max_output_tokens` | 8,192 | 16,384 |

Provider, endpoint, exact `deepseek-v4-flash` model, fallback policy, retry policy, interaction
protocol, temperature, `top_p`, pricing telemetry, and
`request_body_overrides.thinking.type=enabled` are unchanged.

The profile SHA-256 is
`f820ec425d1763c74f6a93c4511d8f4ebf37761555a1e2a50c2b032f293b5ee6`.
It materializes:

- model configuration:
  `agent_model_config:380395940dabe1a71eb175431b5c176b90e03b9c55a0c1a22a1de6cf46c1d437`;
- Thinking binding:
  `prospective_thinking_model_binding:4041c2b462023c7957e4d24e7b02b9d2968f2b686e9fef7f98799507ae87eae2`.

The Thinking policy identity remains
`prospective_thinking_mode_policy:b9ba7be1e8ee2ab343e31fe57b3c50cbbd604abf26b3da4297f5ad76dfbb158f`.

## Provider Usage Semantics Contract

v26.103 freezes
`finance_v26_provider_usage_semantics:f0578dd7dea183887b3034e6e03ef20c801d3045a102d5c3f246b8da1b28966b`.

The Contract separates two quantities:

| Quantity | Frozen value |
| --- | ---: |
| exact request-body `max_tokens` | 16,384 |
| Provider-reported accounting margin | 1 |
| maximum accounting-admissible Completion Usage | 16,385 |
| rollout ceiling | 240,000 |

The exact request certificate never changes to 16,385. The additional token exists only in the
Provider Usage certificate and reserve arithmetic.

For every HTTP-success response:

1. Prompt, Completion, and Total Usage must be present.
2. Prompt plus Completion must equal Total.
3. Prompt Usage must remain within its pre-call certificate.
4. Completion Usage up to 16,385 is accounting-admissible.
5. Actual Total Usage is charged without clipping.
6. Completion Usage of 16,386 or more fails the Instrument Contract.
7. A one-token accounting margin cannot change a length terminal, Completion failure,
   Completion usability classification, or Rescue availability.

The Contract explicitly leaves the underlying Provider semantics unresolved. It is an Instrument
repair, not an empirical threshold relaxation.

## Fresh 16K Identity Chain

v26.103 rematerialized:

| Artifact class | Count |
| --- | ---: |
| TaskPackages | 24 |
| Path Audits | 48 |
| Completion Contract | 1 |
| Job Manifest | 1 |
| Jobs | 32 |

All TaskPackage, Path, Contract, Manifest, and Job identities are fresh and have zero overlap with
their v26.99 exact-8K parents. The 32 seed values and ordered Job assignments are unchanged.

The stage preserved:

- the 24 source tasks and source roles;
- 22 model-exposed and two model-unexposed source classifications;
- all Mechanism and Path assignments;
- all Compiler state rows;
- all Primary and Rescue Prompt surfaces;
- the 6,144-byte absolute Rescue ceiling;
- one global Rescue per Job;
- the response telemetry envelope;
- the exact zero-failure typed-no-call and Completion Gates;
- the Mechanism x Path layout.

The source tasks remain repeated engineering sources. They are not fresh Capability or
Reachability sources and are ineligible for State Mapping, State Support, release, or production
evidence.

## Margin-Aware Path Arithmetic

Each potential Provider call receives a separate one-token accounting reserve. A complete path
therefore adds one token for every registered Primary request and one token for the maximum
possible Rescue.

The accounting delta is 6 to 10 tokens per Path. The 48 selected 16K path bounds are:

| Metric | Minimum | Maximum |
| --- | ---: | ---: |
| full-path upper bound | 125,975 | 233,583 |
| rollout headroom | 6,417 | 114,025 |
| maximum Rescue request bound | 20,234 | 22,407 |

All 48 Paths remain below the 240,000-token rollout ceiling. These are conservative
qualification bounds, not expected Usage estimates and not empirical Budget Adequacy.

The unified cross-artifact Gate contains 104 rows:

- 24 TaskPackage bindings;
- 48 Path bindings;
- 32 Job bindings.

Every row binds the exact candidate, profile SHA-256, model configuration, Thinking binding,
Provider Usage semantics Contract, Completion bound, rollout bound, and parent lineage. The
authoritative cross-artifact audit is
`finance_v26_exact_16k_cross_artifact_binding:2a6ec9437811af40e68c772829c52406b6ad088b54b28da322d75b4f7438f596`.

All 30 v26.103 destructive mutations failed closed. They include profile, candidate, parent,
membership, seed, Completion, rollout, Thinking, Usage margin, clipping, and Completion-rescue
mutations.

## v26.104 Source Replay

Before profile parsing, credential lookup, or any possible real client construction, v26.104
replayed 1,237 files:

| Source class | Files |
| --- | ---: |
| v26.103 transitive source binding | 1,221 |
| v26.103 output files | 12 |
| exact v26.104 implementation files | 4 |
| Total | 1,237 |

The four implementation files are the exact 16K client, shared contracts, future execution
Runner, and preflight implementation.

The source replay is
`finance_v26_exact_16k_runner_source_replay:6a3a306ffe24c0a2f79ea60534acc6abc4528b503e119e91a9f69f410debb0e2`.

## Exact Client And Request Binding

The dedicated client accepts only the new exact 16K model configuration and Thinking binding. Its
ordinary uncertified entrypoint fails closed.

The canonical request body requires:

- model `deepseek-v4-flash`;
- `max_tokens=16384`;
- `thinking.type=enabled`;
- JSON-object response format;
- exact route with no fallback;
- no model-discovery request.

Every permitted call receives a content-addressed request-body certificate immediately before
invocation. The Provider Usage accounting margin does not enter this request body.

The client-binding audit is
`finance_v26_exact_16k_client_binding_fixture:2cd546772a0312a7ba58d10ee6e21b83dca556352b631a0230ee6555d3ba6b1c`.

## Dynamic Pre-Call Closure

The Runner closes each request in this order:

1. render the actual Primary Prompt;
2. infer the actual request kind;
3. render the bounded Rescue when applicable;
4. certify the actual dynamic Prompt and resources;
5. certify the exact 16K request body;
6. certify the accounting-aware Provider budget;
7. issue one single-use invocation authorization;
8. invoke the scripted or future exact Provider route;
9. persist the privacy-redacted Raw Provider artifact;
10. project Completion usability.

The Provider certificate uses 16,385 only for accounting and resource closure. It separately
records the exact 16,384 request bound. Rescue and final-answer reserves each contain 16,384
request tokens plus one accounting token.

Actual Provider-reported Total Usage is accumulated without clipping. A failed Usage check changes
the Job to an Instrument terminal and prevents a Completion Rescue.

## Runner Controls

The zero-generation direct control executed all 32 fresh v26.103 Jobs against their preserved
Compiler paths:

| Control quantity | Count |
| --- | ---: |
| Jobs | 32 |
| logical requests | 224 |
| scripted Provider calls | 224 |
| public Observations | 192 |
| dynamic certificates | 224 |
| exact request certificates | 224 |
| Verifier Replay passes | 32 |
| independent validity passes | 32 |
| mechanism passes | 32 |

The aggregate contains 32 Raw Executions plus 224 Raw Provider artifacts, all 256 canonical files.
These are implementation fixtures and contribute zero empirical rows.

All five frozen Completion failure types recovered with exactly one bounded Rescue. A second
Completion failure ended `completion_unusable` with no second Rescue. A malformed response
envelope ended `instrument_failure` without consuming the public Completion Rescue.

## Provider Usage Controls

v26.104 directly exercised four scripted calls:

| Case | Instrument result | Completion meaning |
| --- | --- | --- |
| reported Completion 16,384 | admitted | length failure remains a Completion failure |
| reported Completion 16,385 | admitted as accounting-only | length failure remains a Completion failure |
| reported Completion 16,386 | rejected | Instrument failure; Rescue blocked |
| ordinary bounded response | admitted | request and future reserves verified |

The 16,385 case charged the complete Provider-reported Total Usage. No token was clipped or
rewritten. The request certificate remained `max_tokens=16384`.

The audit is
`finance_v26_exact_16k_usage_fixture:eb51fe1b03cd04e7570a1b992c440fb57803d554640737dbcb50284931f304f8`.

## Recovery And Off-Compiler Controls

A complete Raw Execution recovered byte-identically with zero scripted calls. An orphan Provider
artifact was rejected instead of retried. Oversized Primary, insufficient remaining rollout
budget, wrong actual request kind, and reused prepared request all failed before an unauthorized
delegate call.

The historical off-Compiler state was exercised again. Its 7,914-byte Primary rendered a
3,888-byte Rescue. No scripted call occurred before all certificates, and exactly one occurred
after authorization.

All 30 v26.104 destructive mutations failed closed. The controls include changed source bytes,
8K and 32K Completion bounds, changed rollout ceiling, second Rescue, model discovery, retry,
automatic higher-bound escalation, missing certificates, private reasoning persistence, request
max-token changes, Usage margin changes, Usage clipping, Completion reclassification, and an
extended single-stage bound ladder.

## Reproducibility And Validation

Formal and independent v26.103 builds reproduced all 12 files byte for byte. Formal and
independent v26.104 builds reproduced all 10 files byte for byte.

Validation completed with:

- 17/17 focused v26.103-v26.104 tests passed;
- the complete historical suite passed with 1,141 tests, four expected v26.78/v26.84 skips,
  and one retained destructive-test serializer warning in 878.93 seconds while importing the
  v26.104 source;
- 100/100 historical adjacent v26.88-v26.102 thinking/budget tests passed from the canonical
  immutable artifact root;
- Ruff check passed for all seven new Python source and test files;
- Ruff format check passed for all seven files;
- Mypy reported no issues in the five new implementation modules;
- zero real Provider calls;
- zero real model clients;
- zero GPU jobs.

The isolated-worktree attempt to run historical artifact-heavy tests from the worktree root was
not a scientific failure: those tests use their file location as package root, while untracked
early immutable artifacts exist only in the canonical root. Rerunning the same historical suite
from the canonical test directory while importing the new worktree source passed 100/100.

## Frozen Stop Rules

v26.104 freezes 16K as the final single-stage Thinking/JSON Completion-bound candidate.

For a future exact v26.105 denominator:

1. Any reasoning-only or partial length failure permits only
   `true_two_stage_thinking_decision_protocol_only`. It does not permit 32K.
2. Any non-length JSON or response-contract Completion failure permits only
   `completion_contract_root_cause_audit_only`.
3. A fully Completion-usable denominator with zero Program closures permits only
   `completion_tuning_stop_behavior_diagnosis_only`.
4. A fully passing Completion and execution denominator may authorize only
   `thinking_role_protocol_freeze_only`, using a fresh role Population.
5. Semantic validity cannot rescue a Completion, typed-no-call, transport, telemetry, or
   Instrument Gate.

## Authoritative Identities

- v26.103 report:
  `finance_v26_exact_16k_rematerialization_report:902ee1959e97e64fc516e927974962caf9d25dae82141e3e680e5ee5cdbd88f5`;
- exact 16K profile binding:
  `finance_v26_exact_16k_profile_binding:851df382d90ef2b6d62e960db43ff0700f6eebec59133070c4340178fe84c630`;
- Provider Usage semantics:
  `finance_v26_provider_usage_semantics:f0578dd7dea183887b3034e6e03ef20c801d3045a102d5c3f246b8da1b28966b`;
- exact 16K Completion Contract:
  `finance_v26_exact_16k_completion_contract:9c37e30fa5af06460b576d3b6df78b08235d99cb4cf636c97fb18833a312e99d`;
- exact 16K Manifest:
  `finance_v26_exact_16k_manifest:d429395f73668418bbb5734b574ac52c059b2ed3c7e4988ce12be7b472aa3bdb`;
- v26.104 report:
  `finance_v26_exact_16k_runner_preflight_report:78d00f0c3134020ba9defd41be87fe767a2903e8988a944434cf8d0ce5fb7ff1`;
- execution Contract:
  `finance_v26_exact_16k_execution_contract:2c093dae01b7125ba3321e6efdc61de445b57fbc373b9338fa9d2a94a1d10abc`;
- Runner fixture:
  `finance_v26_exact_16k_runner_fixture:b965c842b5965d58225f00e3321c9ab91bc02024b3b1dda34b4b479b71245522`;
- Provider Usage fixture:
  `finance_v26_exact_16k_usage_fixture:eb51fe1b03cd04e7570a1b992c440fb57803d554640737dbcb50284931f304f8`;
- pre-call/recovery fixture:
  `finance_v26_exact_16k_precall_recovery_fixture:df4bab1e816ea03bfdc944708435421d540217c5b8d6342c351cd7f873db0636`.

## Final Boundary

v26.103 is a positive static 16K binding and Usage-semantics result. v26.104 is a positive
execution-Instrument preflight. Neither is empirical 16K Completion usability evidence.

No Capability, Reachability, State, release, Exact Target, GP-C, Student-training, or production
row was created. Production Contribution remains zero.

The only permitted next action is the exact v26.105 32-Job 16K engineering-calibration execution.
