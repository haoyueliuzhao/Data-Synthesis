# Finance v26.105-v26.106 Thinking 16K Completion Calibration Execution And Audit

Audit date: 2026-08-22

## Decision Summary

Finance v26.105 executed the exact 32-Job engineering-calibration Manifest authorized by
v26.104. It used the persisted exact-16K profile, exact `deepseek-v4-flash`, explicit
`thinking.type=enabled`, `max_tokens=16384`, the 240,000-token rollout ceiling, the one-Rescue
limit, and the corrected Provider Usage semantics Contract. No source, TaskPackage, Path, Job,
assignment, seed, Prompt, Rescue, Gate, or resource value was changed after authorization.

The complete execution made 572 HTTP-success Provider calls and used 4,780,636
provider-reported tokens. The exact-model, request-body, dynamic pre-call, Provider Usage,
response-telemetry, privacy, and Raw Lineage controls passed. The empirical Completion and
dynamic Budget Adequacy Gates failed, and two historical Job terminals remained
`instrument_failure` because Verifier v2 could not Replay a Runtime-defined typed rejection of an
unavailable tool.

Finance v26.106 then independently replayed the complete source and execution lineage with no
credential lookup, model-client construction, Provider call, or GPU job. It localized the two
Instrument failures, reconstructed all Completion and resource denominators, and retained every
historical terminal unchanged.

The authoritative result is blocked. A single 16,384-token reasoning-only length failure ends the
single-stage Completion-bound ladder under the frozen v26.104 rule. A 32K single-stage profile,
same-protocol 16K rerun, role protocol, Capability execution, Reachability execution, State
Mapping, release, and production Contribution are not authorized.

The only permitted transition is:

```text
authority_preserving_unknown_tool_replay_repair_and_true_two_stage_protocol_preflight_only
```

That transition is credential-free design and preflight only. It must repair the prospective
Verifier Replay semantics, define a real two-stage Thinking/Decision protocol under fresh
identities, and close fresh per-stage Completion, Usage, and dynamic rollout bounds before any
future Provider call.

## Exact Authorization And Execution

The online run used execution Contract
`finance_v26_exact_16k_execution_contract:2c093dae01b7125ba3321e6efdc61de445b57fbc373b9338fa9d2a94a1d10abc`
and Manifest
`finance_v26_exact_16k_manifest:d429395f73668418bbb5734b574ac52c059b2ed3c7e4988ce12be7b472aa3bdb`.

Immediately before credential lookup, `--prepare-only` replayed the full v26.104 binding,
confirmed all 32 expected Jobs, and constructed no model client. The online run then started from
0/32 with eight workers. It did not rerun, recover, or reclassify any v26.95 or v26.101 Job.

The execution completed as follows:

| Item | Observed value |
| --- | ---: |
| Exact Jobs | 32/32 |
| Provider calls | 572 |
| HTTP-success calls | 572 |
| Prompt tokens | 1,675,536 |
| Completion tokens | 3,105,100 |
| Reasoning tokens | 3,001,271 |
| Total tokens | 4,780,636 |
| Estimated cost telemetry | USD 0.98291580800000008797 |
| Local GPU jobs | 0 |
| Logical requests | 566 |
| Request attempts | 589 |
| Rescue Provider calls | 23 |

Every Provider call requested, selected, and returned exact `deepseek-v4-flash`. Fallback,
Provider-native tool calls, model discovery, transport failure, response-model gaps, Thinking
telemetry gaps, and Usage gaps were zero. All 572 calls had a dynamic pre-call certificate and an
exact `max_tokens=16384` request-body certificate before invocation.

The final terminal denominator was:

| Historical terminal category | Jobs |
| --- | ---: |
| `completion_unusable` | 14 |
| `typed_budget_no_call` | 15 |
| `instrument_failure` | 2 |
| `model_invalid_trajectory` | 1 |

The two Instrument Jobs also contain valid typed budget no-call terminals in their Raw
Executions. Therefore the independently reconstructed typed-no-call Job count is 17, while only
15 top-level historical terminals are named `typed_budget_no_call`. These are different counts
and are not interchangeable.

After completion, the exact Runner was invoked again without the Provider credential. It resumed
at 32/32, constructed no client, made zero Provider calls, and returned the same report bytes.
The Provider file count remained 572 and the report SHA-256 remained
`94e461401add1ce315494383454fb1ad9f70ad4ce922eec33d3291136f1b2406`.

## Provider Usage Semantics

v26.106 paired every Provider artifact with its exact Raw request attempt. The requested
Completion bound remained 16,384 on every call. The requested audit of
`reported Completion - request max_tokens` produced:

| Usage delta class | Calls | Finish reason | Completion projection |
| --- | ---: | --- | --- |
| `< 0` | 535 | `stop` | usable |
| `< 0` | 33 | `stop` | invalid response Contract |
| `< 0` | 2 | `stop` | invalid JSON |
| `< 0` | 1 | `stop` | empty final content |
| `= 0` | 1 | `length` | reasoning-only length truncation |
| `= 1` | 0 | none | none |
| `>= 2` | 0 | none | none |

Thus 571 calls reported less than the request bound, one reported exactly the request bound, and
none exercised the one-token accounting margin. No call reported two or more excess Completion
tokens. This run provides no evidence that a one-token margin is a stable Provider convention;
it only confirms that the prospective Contract remained available and was not misused.

All Provider-reported Total Usage was charged without clipping. Every per-Job Usage audit sums
its counted tokens exactly to the persisted Provider totals, and no Job exceeded 240,000 tokens
after a response.

## Reasoning And Completion

Reasoning consumed 3,001,271 of 3,105,100 Completion tokens, an aggregate fraction of
`0.966561785450`. The non-Reasoning Completion total was 103,829 tokens.

| Per-call metric | Observed value |
| --- | ---: |
| Minimum Reasoning fraction | 0.033678756477 |
| Median Reasoning fraction | 0.975892584681 |
| p95 Reasoning fraction | 0.993100000000 |
| Maximum Reasoning fraction | 1.000000000000 |
| Minimum Completion tokens | 349 |
| Median Completion tokens | 5,323 |
| p95 Completion tokens | 11,031 |
| Maximum Completion tokens | 16,384 |

The aggregate fraction is descriptive. It does not by itself prove that the Provider Thinking
kernel always expands with the bound. The decisive frozen observation is narrower: one call used
the exact 16,384-token bound, returned `finish_reason=length`, contained positive Reasoning
telemetry, and exposed no usable public final content. Its typed classification is
`reasoning_only_length_truncation`.

The 37 Completion-failure attempts were:

| Failure type | Calls |
| --- | ---: |
| Invalid response Contract | 33 |
| Invalid JSON | 2 |
| Empty final content | 1 |
| Reasoning-only length truncation | 1 |
| Partial length truncation | 0 |

Thirty-six failures occurred on decision requests and one invalid response Contract occurred on a
final-answer request. All 37 were Primary attempts.

Twenty-three first Completion failures consumed the single bounded Rescue. All 23 Rescue calls
were usable: 20 repaired invalid response Contracts, two repaired invalid JSON, and one repaired
empty final content. No Rescue response itself failed Completion. Fourteen Jobs later encountered
a second Primary Completion failure after their one Rescue had already been consumed; thirteen
ended on invalid response Contracts and one ended on the reasoning-only length failure. All
fourteen correctly terminated `completion_unusable` without a second Rescue.

The Completion-unusable Job count was 14/32. Its independently recomputed one-sided 95%
Clopper-Pearson upper bound is `0.5968316155208788`, so the frozen zero-failure Completion Gate
failed. Semantic behavior cannot rescue this Gate.

## Dynamic Budget Audit

Seventeen Jobs reached a typed pre-call denial. Every denial occurred before a decision request,
made no Provider call for the denied request, and used reason
`required_reserve_not_available`. No denial occurred at a final-answer request and no Prompt
exceeded the 60,000-byte ceiling.

| Diagnostic | Observed range or count |
| --- | ---: |
| Denied request indices | 17-24 |
| Cumulative Provider Usage before denial | 171,114-199,811 |
| Remaining rollout tokens before denial | 40,189-68,886 |
| Frozen next-request-plus-reserve deficit | 733-14,912 |
| Jobs with unused Rescue reserve, 32,770 tokens required | 9 |
| Jobs with Rescue consumed, 16,385 tokens required | 8 |
| Provider calls for denied requests | 0 |
| Jobs exceeding rollout ceiling after a response | 0 |

At denial, the frozen projection was:

```text
cumulative actual Usage
+ next request upper bound
+ still-required Rescue/final-answer reserve
> 240,000
```

All seventeen trajectories had 17-23 public Observations and 15-20 failed Observations. Fourteen
had completed zero Program nodes and three had completed two; none had closed Program, completed
the terminal node, or completed post-terminal verification. The rows contained thirteen repeated
call signatures, all of which were repeated failed signatures.

These values localize the observable no-call condition to
`decision_request_plus_required_reserve_exceeded_remaining_rollout_budget`. They do not prove
that adding 733-14,912 tokens would complete any trajectory: those deficits qualify only the next
request and required reserve, not the unknown suffix of a model-generated trajectory. v26.106
therefore authorizes no budget increase. A future two-stage design must freeze and preflight a new
dynamic resource Contract rather than patching the historical 240K Contract.

The typed-no-call count was 17/32, with one-sided 95% Clopper-Pearson upper bound
`0.6845587338890586`. The zero-failure Budget Adequacy Gate failed independently of Completion
and Verifier Replay.

## Instrument Root Cause

The two historical Instrument terminals have the same observable mismatch:

| Job | Raw file | Unreplayed Observation | Mechanism |
| --- | --- | ---: | --- |
| `finance_v26_exact_16k_job:56f712f2b68df1a57f838563e346bc0477fb075ff88ef2665e1289901ef04ba1` | `raw_execution/c3fd3fda9e6a8a0f6c18.json` | 7 | State-dependent Stopping |
| `finance_v26_exact_16k_job:7435b2e21439a972dc9dc0803f5ed50998b1fe6509753285f39fb8d24ad34a22` | `raw_execution/fb20f5e2e680a7c6c103.json` | 2 | Context-conditioned Action |

Each model selected `open_document`. The exact frozen environments contained only
`query_structured_fact`, `calculator`, and `cross_check_evidence`, so `open_document` was absent.
The Runner deliberately converted that model choice into a public failed Observation with empty
result, error code `unknown_or_unselectable_tool`, and message that the selected tool was not
available.

Verifier v2 instead looked up the tool before reproducing the Runner rejection. On lookup failure
it appended `observation:<index>:unknown_tool`, retained the observed row, and continued without
replaying the typed result. The two Replay results therefore covered 16/17 and 18/19
Observations and failed. Response telemetry, Provider Usage, dynamic pre-call binding, and the
typed budget terminal were valid in both Jobs.

The localized root cause is:

```text
runtime_unknown_or_unselectable_tool_observation_not_replayed_by_verifier_v2
```

This is a prospective Verifier contract defect, not permission to relabel the historical model
choice or the historical terminal. A future repair must reconstruct the same deterministic typed
failure, preserve model ownership of the selected tool and arguments, and reject any Host action
insertion. The v26.105 two Job terminals remain `instrument_failure` forever.

The Completion and Budget Gates fail independently even if a prospective Replay repair would
admit both typed resource terminals. No prospective diagnostic can rescue the v26.105 denominator.

## Descriptive Behavior

The complete denominator contains one Program closure, one completed terminal node, one completed
post-terminal verification, nine mechanism successes, twelve requested-path adherences, and zero
independently valid trajectories. Thirty-one actual routes were `structured_direct`; one was
mixed or unresolved.

These are descriptive engineering-calibration outcomes. The 24 sources are repeated engineering
sources, including 22 previously model-exposed sources. No v26.105 row is eligible for Capability,
Reachability, State Mapping, State Support, release, or production evidence. Low behavior metrics
cannot rescue Completion, Budget, or Instrument Gates, and high behavior metrics would not create
role evidence from this Population.

## Independent v26.106 Audit

Before diagnostics, v26.106 replayed 1,860 files:

| Source class | Files |
| --- | ---: |
| v26.104 transitive bound sources | 1,237 |
| v26.104 output files | 10 |
| v26.105 execution files | 612 |
| Exact v26.106 implementation | 1 |

The execution partition contains 611 canonical JSON files and one canonical JSONL checkpoint with
32 rows. The Raw Lineage contains 32 Raw Executions, 572 Provider artifacts, and 604 exact-byte
descriptors. Checkpoint, final result, Raw parent, Provider parent, request certificate, dynamic
certificate, Usage record, and persisted descriptor identities all reproduced.

Private reasoning content and hashes, raw HTTP bodies, and raw request bodies remain absent. The
audit retained only Reasoning presence, length, and token telemetry. Formal and independent
builds produced all nine v26.106 output files byte for byte. All 30 destructive mutations failed
before any model-client construction or Provider call. The focused v26.106 suite passes 9/9
tests, the adjacent v26.97-v26.106 Completion-bound/8K/16K suite passes 64/64 tests, and focused
Ruff and Mypy checks pass.

## Prospective Contract

The next stage may only design and credential-free preflight a fresh protocol satisfying all of
the following:

1. Verifier Replay reconstructs the exact Runtime-defined unavailable-tool typed failure and does
   not choose, insert, or repair a model action.
2. Thinking and Decision are explicit stages with fresh identities, separate per-stage Completion
   and Usage bounds, and a fresh dynamic rollout resource Contract.
3. Every Provider call still requests exact `thinking.type=enabled` before credential lookup and
   client construction.
4. Private reasoning content is never persisted, hashed, or transferred between stages. Only a
   separately validated public stage output may cross the stage boundary.
5. Static coverage, exact client/request binding, dynamic pre-call certification, Raw-first
   persistence, raw-only recovery, orphan rejection, privacy, and destructive controls all pass
   before any Provider call.
6. No v26.105 Job is rerun, recovered, or reclassified. New identities arise from the new protocol
   lineage, not from resampling to evade the completed negative denominator.

No empirical execution is currently authorized by this transition.

## Authoritative Identities

- v26.105 execution report:
  `finance_v26_exact_16k_execution_report:fa01ca877d5f6c50861c6f145a6c3f2ee8ef22a372f57884a8d5714f283658d0`;
- v26.105 Raw Lineage:
  `finance_v26_exact_16k_raw_lineage:dcc992eb0d2bc23853233e6007e279964366f42f6b07863027d503becf3baff4`;
- v26.106 report:
  `finance_v26_exact_16k_postrun_audit_report:c32d1c5bd8aee46d444a2a6f4e82352179a71fa83c87be7dbae8e805e44805f2`;
- v26.106 execution-lineage audit:
  `finance_v26_exact_16k_execution_lineage_audit:2ad93603b048022a7a36b5d77d8e82473488759a529a244c1fcce70412a14a35`;
- v26.106 Provider telemetry audit:
  `finance_v26_exact_16k_provider_telemetry_audit:6d9a44f05d534559fd90637a7b825be9f749ba4301dbd0c9b4a55f05f7c98727`;
- v26.106 Completion outcome audit:
  `finance_v26_exact_16k_completion_outcome_audit:2da029d88d90c0a8dbb075ea47ec2f262464831bea4cc2c40b6427dc9819fda3`;
- v26.106 dynamic-budget audit:
  `finance_v26_exact_16k_dynamic_budget_audit:669bede793c026ba29ecd302b534a96ef237226baa4b3ff4c29c4629a9df0eb5`;
- v26.106 Instrument root cause:
  `finance_v26_exact_16k_instrument_root_cause:6bf1ed0afd63196998a80b48c6fc41b559c597749d7e6371499fb29e809adcdb`;
- v26.106 prospective transition:
  `finance_v26_exact_16k_postrun_transition:3b521a4324e067c94fa19b219514a7b9666e4638b8f31b5d8472dd673564ee90`.

## Authoritative Files

- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_16k_completion_calibration_execution.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_16k_completion_calibration_postrun_audit.py`
- `tests/test_v26_thinking_16k_completion_calibration_postrun_audit.py`
- `artifacts/vtdo_experiment/finance_v26_105_thinking_16k_completion_calibration_execution_v1_20260822/`
- `artifacts/vtdo_experiment/finance_v26_106_thinking_16k_completion_calibration_postrun_audit_v1_20260822/`
