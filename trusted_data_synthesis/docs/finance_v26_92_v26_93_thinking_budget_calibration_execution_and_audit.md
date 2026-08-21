# Finance v26.92-v26.93 Thinking Budget Calibration Execution And Audit

Audit date: 2026-08-21

## Decision Summary

Finance v26.92 executed exactly the 32 previously unopened Jobs frozen by the authoritative
v26.91 Thinking Budget Calibration Manifest. The execution made 318 successful Provider calls,
used 1,294,797 provider-reported tokens, and recorded estimated cost telemetry of USD
0.24562028400000002152. It used exact `thinking.type=enabled` requests and no local GPU job.

The empirical Budget Adequacy Gate passed: there were zero typed no-call outcomes in 32 Jobs, and
the frozen one-sided 95% Clopper-Pearson upper bound was 0.08936819898626475, below the 0.10
threshold. Thinking continuity also passed: every one of the 318 HTTP-success calls had positive
reasoning presence, reasoning length, and reasoning-token telemetry.

The separately frozen Completion Usability Gate failed decisively. Thirty of 32 Jobs ended with
an unusable Completion, giving a one-sided 95% upper bound of 0.9887805056361199. The duplicate
source sensitivity analysis found 29 failures among 31 distinct source tasks, with upper bound
0.9884146841385564. Semantic behavior cannot rescue this Gate.

Execution integrity also failed because exact response-model identity was not observable for 79
HTTP-success parse failures. All 318 calls requested and selected `deepseek-v4-flash`, all recorded
fallback flags were false, and the 239 responses with retained response-model telemetry matched
exactly. Therefore no Provider model mismatch was observed. The missing 79 values nevertheless
prevent an exact-model claim and cannot be recovered from persisted v26.92 payloads.

Finance v26.93 then independently replayed and audited the v26.92 execution without constructing a
model client, making an API call, running a GPU job, rerunning a Job, or reclassifying a historical
result. It confirmed the Completion failure, raw persistence integrity, and response-telemetry
gap, then froze a prospective repair Contract and five destructive local fixtures.

The authoritative transition is:

```text
fresh_thinking_completion_and_response_telemetry_repair_preflight_only
```

A thinking-enabled role protocol is not frozen. Capability Development, State Reachability,
Fresh Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and production Contribution
remain forbidden. Production Contribution remains zero.

## Frozen Inputs

v26.92 retained all scientific inputs frozen by v26.91:

- preflight report:
  `finance_v26_thinking_budget_calibration_preflight_report:4af68e0667d05639885b985dd7d9091ed8fba03202e6b6c4ebf1d243586a8324`;
- Calibration Contract:
  `finance_v26_thinking_budget_calibration_contract:e147742ac18e0766b84162a25f87880340f0f2c57c79883e75db03fef935973d`;
- 32-Job Manifest:
  `finance_v26_thinking_budget_calibration_manifest:3c6877014f6fdd2de41cc3e0c52983b4242942967ec674fecc3630cbccdc630b`;
- Thinking Continuity Contract:
  `thinking_continuity_contract:a4c8025741e13e38025ac6250e18d57ad5e317a2f2db23d66b54d9d8de2144e8`;
- Completion Usability Contract:
  `finance_v26_completion_usability_contract:e7ebf169c798a6af386024652e5b720d1157cd0c825c3c634bed9629cbe5498b`;
- prospective Thinking policy:
  `prospective_thinking_mode_policy:b9ba7be1e8ee2ab343e31fe57b3c50cbbd604abf26b3da4297f5ad76dfbb158f`;
- exact thinking-enabled Flash model configuration:
  `agent_model_config:727b3867544c4eac844eb260b9673dee41be7b8787b07ea2e3d6c69113e68bd1`.

The execution binding is
`finance_v26_thinking_calibration_execution_binding:bd454756a3be0e7ee578587c6ee407762c9522c27a017780429b04af7ce9e157`.
Before credential lookup and client construction, the execution replayed 160/160 files: all 31
v26.91 outputs, all 104 predecessor bindings, and 25 exact execution implementation bindings.
The frozen Contract and Job Manifest were copied byte for byte into the v26.92 execution root.

No TaskPackage, requested path, stress-padding schedule, Job seed, model profile, Thinking policy,
Prompt ceiling, completion bound, rollout ceiling, or reserve was changed. The 93 v26.91 Compiler
paths and 580 local Observations remained fixtures and entered no empirical denominator.

## Execution Denominator

The Runner completed all 32 Jobs in the frozen order-independent denominator. Each Job was opened
once. There was no recovery execution and no historical Job was rerun.

| Quantity | Result |
| --- | ---: |
| Frozen Jobs | 32 |
| Completed Jobs | 32 |
| Distinct source tasks | 31 |
| Provider calls | 318 |
| HTTP-success calls | 318 |
| Provider transport-failure Jobs | 0 |
| Typed no-call Jobs | 0 |
| Thinking-continuity-failure Jobs | 0 |
| Provider-reported total tokens | 1,294,797 |
| Estimated cost telemetry | USD 0.24562028400000002152 |
| Local GPU jobs | 0 |

All 32 persisted terminal rows are `instrument_failure`. This classification must not be read as
32 model-invalid trajectories. Each Job had at least one unrecoverable response-model telemetry
gap, so none could pass the exact-model execution-integrity Gate. Thirty Jobs independently also
failed Completion usability. Behavior summaries below are descriptive diagnostics only.

## Preregistered Gates

| Gate | Exact result | Decision |
| --- | --- | --- |
| Complete denominator | 32/32 | passed |
| Provider transport | 0/32 failures | passed |
| Typed no-call | 0/32; CP95 upper 0.08936819898626475 | passed |
| Thinking continuity | 0/32 failed; 318/318 HTTP-success calls positive | passed |
| Completion usability | 30/32 unusable; CP95 upper 0.9887805056361199 | failed |
| Unique-source sensitivity | 29/31 unusable; CP95 upper 0.9884146841385564 | failed |
| Exact response model | 239 known exact, 79 missing, 0 known mismatch | failed |
| Fallback absence | 318/318 recorded false | passed |
| Per-rollout resource contract | 32/32 | passed |
| Raw lineage | 350/350 descriptors | passed |

The typed no-call and Completion Gates are separate by design. The zero typed no-call result is
positive empirical Budget Adequacy evidence for this exact calibration denominator. It does not
imply that the 4,096-token Completion bound is adequate for a thinking-enabled decision protocol.

## Thinking And Completion Telemetry

The 318 HTTP-success calls recorded 2,937,738 reasoning characters and 682,847 reasoning tokens.
Provider completion Usage totaled 708,632 tokens, so reasoning tokens represented 96.3612989535%
of aggregate completion Usage. The unweighted per-call reasoning-token fraction had mean
0.9266932822506447, minimum 0.38271604938271603, and maximum 1.0. These are public telemetry
statistics; private reasoning text was neither persisted nor hashed.

The 199 logical decision requests expanded to 318 Provider calls because 119 Contract-repair
requests were made. Every Job required at least one repair. Of the 119 repair calls, 89 restored a
usable decision and 30 did not. The repair-request rate was 0.5979899497487438.

The Provider completion outcomes were:

| Outcome | Calls |
| --- | ---: |
| Usable structured completion | 80 |
| Usable after Contract repair | 89 |
| Reasoning-only length truncation | 27 |
| Length-truncated content | 1 |
| Invalid Decision Contract after repair | 2 |

There were 78 `finish_reason=length` calls. Fifty-three logical requests encountered at least one
length response; 23 eventually became usable after repair and 30 ended in terminal Completion
failure. Twenty-five logical requests consumed two length-limited calls. This shows that repair
recovered some individual requests but did not make the exact Job-level Completion contract
usable.

Telemetry repair alone cannot rescue this result. The 30/32 Completion failure remains valid even
if all 79 missing response-model values were prospectively observable and exact.

## Descriptive Behavior

No trajectory completed its registered Program and none was independently valid. Six Jobs had a
local mechanism success. Requested-path adherence was 10/32. The traces contained 63 failed
Observations, two repeated call signatures, and one repeated failed-call signature.

| Mechanism | Requested path | Jobs | Unusable | Requests | Path adherence | Mechanism success | Program closed | Valid |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Context | `search_then_open` | 2 | 2 | 20 | 0 | 0 | 0 | 0 |
| Context | `search_then_structured` | 2 | 2 | 24 | 0 | 0 | 0 | 0 |
| Context | `structured_direct` | 2 | 2 | 17 | 2 | 0 | 0 | 0 |
| Recovery | `search_then_open` | 3 | 3 | 24 | 0 | 2 | 0 | 0 |
| Recovery | `search_then_structured` | 3 | 2 | 37 | 0 | 3 | 0 | 0 |
| Recovery | `structured_direct` | 2 | 2 | 17 | 1 | 1 | 0 | 0 |
| Reconciliation | `search_then_open` | 4 | 4 | 22 | 0 | 0 | 0 | 0 |
| Reconciliation | `search_then_structured` | 4 | 4 | 57 | 2 | 0 | 0 | 0 |
| Reconciliation | `structured_direct` | 2 | 1 | 26 | 2 | 0 | 0 | 0 |
| Stopping | `search_then_open` | 3 | 3 | 31 | 0 | 0 | 0 | 0 |
| Stopping | `search_then_structured` | 3 | 3 | 29 | 1 | 0 | 0 | 0 |
| Stopping | `structured_direct` | 2 | 2 | 14 | 2 | 0 | 0 | 0 |

The Recovery `search_then_structured` cell had local mechanism success in 3/3 Jobs, but this is a
descriptive saturation diagnostic, not Capability support. Every cell had zero Program closure
and zero validity. The one-leaf calibration tasks also cannot establish role-task depth or
capability informativeness.

## Exact-Model Telemetry Gap

The online Runner persisted exact requested and selected model identities for 318/318 calls and a
false fallback flag for 318/318 calls. It retained exact response-model identity for the 239 calls
whose public content parsed successfully. All 239 matched `deepseek-v4-flash`.

For 79 HTTP-success calls, the shared Provider client raised a content-level exception before the
normalized telemetry artifact retained `response_body.model`:

| Parse outcome | Missing response-model calls |
| --- | ---: |
| `ReasoningBudgetExhaustedError` | 74 |
| `JSONDecodeError` | 5 |
| Total | 79 |

Seventy-eight of these responses ended with `finish_reason=length`; one ended with `stop`. The
normalized failure payload contains no redacted response envelope from which the model can be
recovered. All 32 Jobs contain at least one such call.

Therefore the scientifically supported statements are:

- zero known response-model mismatches were observed;
- no fallback was recorded;
- exact response-model identity is known for 239/318 calls;
- exact response-model identity is unobservable for 79/318 calls;
- v26.92 cannot pass the exact-model Gate;
- the missing values cannot be filled by assumption or historical reclassification.

The same normalized artifacts have no explicit
`provider_native_tool_call_observed` field. Provider-native tools were not requested and the Host
protocol forbade them, but absence was not independently captured before content parsing. v26.93
therefore records an observation gap, not an observed native-tool call.

## Raw Persistence And Replay

The v26.92 Raw Lineage audit is
`finance_v26_thinking_calibration_raw_lineage:790b22f989e99875a6044798ef5f412f9106109b88140bc5f290910f6a5b9f73`.
It binds 32 Raw Executions and 318 Provider artifacts. Every one of the 350 files is canonical
JSON, reparses under its strong schema, and has a unique Provider identity where applicable.

Checkpoint and final aggregates contain the same 32 Job results. The execution persisted 32
failure artifacts and zero solve results. Private reasoning payload count is zero. Runtime emitted
Pydantic serialization warnings while initially normalizing nested failure dictionaries, but all
persisted artifacts subsequently pass strong-schema reparse and canonical-byte validation. This
does not alter the v26.92 failure result. The prospective repair Contract requires validation of
the typed failure artifact before serialization.

A completed-run replay without credentials resumed at 32/32, executed zero Jobs, constructed no
model client, and reproduced the same report and top-level hashes. The immutable execution report
is
`finance_v26_thinking_budget_calibration_execution:f3bd9954b1c1f8e465bcca968ef5165d037a7da52b0c0f54ec87e1b9a34aec9b`.

## v26.93 Independent Audit

v26.93 uses a separate credential-free implementation. It replayed 393 exact files:

- 17 v26.92 top-level execution files;
- 350 Raw Lineage files;
- 25 v26.92 execution implementation bindings;
- its own independent audit source.

It independently reconstructed all Provider counts, Usage totals, cost telemetry, Thinking
telemetry, Completion outcomes, Job-level failures, and both Clopper-Pearson bounds. It also
verified 32/32 checkpoint/final matches, 32/32 Raw Execution schema reparses, 318/318 Provider
schema reparses, zero private reasoning payloads, and zero historical file modifications.

The authoritative v26.93 identities are:

- report:
  `finance_v26_thinking_postrun_audit_report:c6cb718b06f403e8603f4a2520bef8e374aefea2357245a16a8b982071529d44`;
- source replay:
  `finance_v26_thinking_postrun_source_replay:8936788add5e571095845c23c3fd1a4c0300fee5e503f8ce6346935fb13e3cc3`;
- persistence audit:
  `finance_v26_thinking_postrun_persistence:e51d9affef4f39694417d5c5c97e24be4712524ac6ed4a9ecfef7bd1356f516a`;
- response-model gap audit:
  `finance_v26_thinking_response_model_gap:38850771e79e863a91cf5675ea5e615ebdc1e896e81e5dff3ccc5e3e866907bd`;
- Completion root-cause audit:
  `finance_v26_thinking_completion_root_cause:c07c41851bd32bbe9738c73918b37f51e8bba244dcd02df8b83ccb9af812b96d`;
- prospective repair Contract:
  `finance_v26_thinking_telemetry_repair_contract:10f084cc4aac9172cede50ab7f0fbaf339997c9a1cac43f74aed8f107d886343`;
- destructive fixture audit:
  `finance_v26_thinking_telemetry_repair_fixture:8d0e7362800508872a23f4d0f4fda0ba6156308b3f7ada2720a3911e60894dc6`.

Formal and independent v26.93 builds reproduced all seven files byte for byte. Both made zero API
calls, zero GPU jobs, and zero historical changes.

## Prospective Repair Contract

The v26.93 repair Contract requires a future Provider wrapper to capture a privacy-redacted
response envelope immediately after HTTP success and before content parsing. The envelope retains
only:

- response model;
- finish reason;
- public final-content hash and length;
- explicit Provider-native-tool presence;
- reasoning presence and length;
- reasoning-token and completion-token telemetry.

Private reasoning content, private reasoning hashes, and raw HTTP bodies remain forbidden. Exact
response model and explicit native-tool absence must remain available even when content parsing
raises `ReasoningBudgetExhaustedError`, `JSONDecodeError`, or another typed failure. A
Provider-native tool call fails closed. Typed failure artifacts must validate before persistence.

Five local destructive mutations were rejected: missing response model, changed response model,
Provider-native tool presence, missing reasoning telemetry, and a private-reasoning persistence
field. These fixtures made zero Provider calls and are not empirical model rows.

The repair Contract does not authorize a direct rerun. A successor must first freeze a new
preflight with fresh task, Contract, Manifest, and Job identities, while retaining the 4,096-token
Completion bound, 120,000-token rollout ceiling, and 60,000-byte Prompt ceiling. It must redesign
the Completion protocol before execution and may not relax the Completion threshold to fit the
v26.92 result.

## Interpretation And Limits

The positive result is narrow: the exact v26.91 stress-shaped calibration denominator produced
zero typed no-calls under the unchanged rollout budget, and Thinking telemetry was continuously
observable. This supports Budget Adequacy for those 32 calibration Jobs only.

The negative Completion result is independently decisive. Reasoning consumed most Completion
Usage, 78 calls hit the Completion limit, all Jobs invoked Contract repair, and 30 Jobs still
ended unusable. The data support redesigning how thinking and public JSON decisions share the
fixed Completion budget. They do not by themselves identify one unique causal repair or authorize
a larger Completion bound.

The exact-model result is unresolved, not negative evidence of model substitution. All known
response identities are exact, but missing telemetry prevents proof. No response-model value may
be imputed from the request, selected model, fallback flag, or known responses.

No comparison with historical `thinking.type=disabled` rows was performed. The v26.92 behavior
rows remain separate from Capability, Reachability, State Mapping, and release denominators.
Nothing in v26.92 or v26.93 changes the historical 0/36 State Support Freeze or any prior report.

## Authorization State

```text
v26.92 completed jobs                         = 32 / 32
v26.92 typed no-call gate                     = passed
v26.92 Thinking continuity                    = passed
v26.92 Completion usability                   = failed
v26.92 exact-response-model observability     = failed
v26.92 execution status                       = blocked
v26.93 independent replay                     = passed
v26.93 telemetry repair fixtures              = passed
thinking-enabled role protocol frozen         = false
Capability Development authorized             = false
State Reachability authorized                 = false
State Mapping authorized                      = false
production Contribution                       = 0
next permitted stage                          = fresh_thinking_completion_and_response_telemetry_repair_preflight_only
```

## Validation

The final committed-source candidate passed:

- 9/9 focused v26.92-v26.93 tests in 10.31 seconds;
- 41/41 adjacent v26.88-v26.93 budget and Thinking tests in 68.71 seconds;
- repository-wide Ruff check;
- Ruff format check on the four v26.92-v26.93 implementation and test files;
- focused Mypy on those four files;
- package-wide Mypy over 390 source files with only the retained source-bound v26.70
  `provider_ids` annotation diagnostic;
- 1,072 Pytest passes, four expected v26.78/v26.84 success-state skips, and one retained
  destructive-test serialization warning in 839.74 seconds.

Formal and independent v26.93 builds remain byte-identical for all seven output files. The final
credential scan found no tracked or newly staged `sk-` plus 32-alphanumeric credential pattern.

## Authoritative Artifacts

- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_budget_calibration_execution.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_calibration_postrun_audit.py`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/raw_lineage_audit.json`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/completion_usability_classifications.json`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/thinking_history_audits.json`
- `artifacts/vtdo_experiment/finance_v26_92_thinking_budget_calibration_execution_v1_20260821/provider_budget_audits.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/completion_root_cause_audit.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/provider_telemetry_gap_audit.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/persistence_integrity_audit.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/telemetry_repair_contract.json`
- `artifacts/vtdo_experiment/finance_v26_93_thinking_calibration_postrun_audit_and_telemetry_repair_v1_20260821/repair_fixture_audit.json`
