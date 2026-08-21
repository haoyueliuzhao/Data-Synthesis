# Finance v26.95-v26.96 Thinking Repair Execution And Failure Audit

Date: 2026-08-21

## Decision

Finance v26.95 attempted the exact 32-Job Thinking Completion and response-telemetry repair
Manifest authorized by the v26.95 execution preflight. The attempt failed closed after 28 Jobs
had received at least one Provider completion call. It did not produce a completed execution
report and it did not complete the exact denominator.

Finance v26.96 then performed the only permitted credential-free Instrument root-cause audit. It
made zero model calls, constructed no client, and used zero GPU jobs. It replayed all 723 bound
source, preflight, implementation, and failed-run files and independently reconstructed the
exposure partition, Raw lineage, Provider telemetry, Completion-failure lower bound, and Runtime
failure.

The v26.96 audit is authoritative:

```text
finance_v26_thinking_repair_failure_audit_report:7ee7fb7963ccaa862496a0ee1664815904fc4a009a1748a45a6920b6496d3cde
```

Its status is `blocked`. The only permitted transition is:

```text
thinking_completion_bound_or_two_stage_protocol_redesign_only
```

No v26.95 Job may be rerun. The four unopened v26.95 Job identities are retired and may not be
executed as a continuation. The current 4,096-token Completion protocol may not receive another
Prompt-only repair.

## Execution Boundary

The execution used the exact committed v26.95 Runner and preflight identities:

- source commit: `5c028acd5ee095be0cbd2cd442706544199674b2`;
- execution preflight report:
  `finance_v26_thinking_repair_execution_preflight_report:986591ddd3b7251cf183f52193bc3868ccec52816cb83715585d76fd4ef07ca5`;
- execution Contract:
  `finance_v26_thinking_repair_execution_contract:78e40804aa6fa489223991a40bd84c68935a1b4ce8aa0de311e2663538a469b2`;
- repair Contract:
  `finance_v26_thinking_repair_contract:573eb1493ad87832eade20407db775b093a7c4168c63bf19113ee5ceb4dd4f72`;
- Job Manifest:
  `finance_v26_thinking_repair_manifest:56ada3c9430d56c20c6611986cc0fa51f19c3f80fbee3b7b63b07dffddcf5945`.

Before credential lookup and client construction, the final execution directory completed the
formal `--prepare-only` phase. It replayed 498/498 source files and wrote only the online source
replay, execution Contract, repair Contract, and Manifest. It created no Raw or Provider
directory and constructed no client.

After explicit user approval to send the frozen task Prompts to the configured DeepSeek endpoint,
the Runner started at `0/32`, with zero Raw-recovery Jobs and eight workers. No historical Job was
submitted.

## Fail-Closed Event

The main Runner persisted 19 Job-result checkpoints before one worker raised a schema validation
error:

```text
rescue_prompt_reduction_basis_points = 932
frozen minimum                       = 1000
```

The failing Job was:

```text
finance_v26_thinking_repair_job:9fa6a03e7f9e692a0f14bc9488d84016a9510c79d79260ca4d104996c1064b19
```

It was a `state_dependent_stopping` Job requested on `search_then_open`. The error occurred on
logical request index 6 after the corresponding Primary and Rescue HTTP-success responses had
both been persisted. The Runner cancelled queued work, waited for already running workers to
exit, wrote one failure checkpoint, and raised the frozen Raw-only recovery error. No automatic
retry occurred.

Because concurrent workers completed after the main thread had stopped collecting futures, the
failed directory contains more complete Raw Executions than Job-result checkpoints. v26.96
reconstructed the exact partition:

| Exposure state | Jobs |
| --- | ---: |
| Checkpoint plus complete Raw | 19 |
| Complete Raw, not checkpointed | 8 |
| Provider artifacts, no complete Raw | 1 |
| Unopened | 4 |
| **Manifest total** | **32** |

Thus 28 Jobs were model-exposed, 27 have complete Raw Executions, one is a Provider-orphan state,
and four were never opened. The 28 exposed Jobs are permanently ineligible for rerun. The orphan
is not reconstructed as a historical model terminal, and the eight uncheckpointed Raw files are
not inserted into the historical checkpoint after the fact.

## Raw Lineage

The failed attempt persisted:

- 27 complete Raw Execution files;
- 184 redacted Provider completion artifacts across 28 Job directories;
- 19 schema-valid Job-result checkpoint rows;
- one schema-valid Runner failure checkpoint row;
- four frozen top-level Contract and replay files.

All 27 Raw Executions and all 184 Provider artifacts are canonical JSON and reparse under their
frozen strong schemas. All 20 JSONL rows are canonical. Every Raw Provider descriptor hash passes,
all 19 checkpoint-to-Raw bindings pass, and all 184 Provider call identities are unique.

Of the 184 Provider artifacts, 176 are bound by complete Raw Executions. The failing orphan Job
contains the remaining eight, ordered from call index 0 through 7. No Provider identity overlaps
between those two sets. No project process remained after failure.

The authoritative lineage audit is:

```text
finance_v26_thinking_repair_failed_lineage:0b21dfd1bad25d122d76104f28c2cb65f1dc85986bbf79ef1d68b29dbf24d79e
```

## Provider Telemetry

All 184 persisted completion calls returned HTTP success and retained the required pre-parse
privacy-redacted envelope:

| Provider property | Result |
| --- | ---: |
| Exact requested model | 184/184 |
| Exact selected model | 184/184 |
| Exact response model | 184/184 |
| Fallback | 0/184 |
| Provider-native tool | 0/184 |
| Positive Thinking presence/length/tokens | 184/184 |
| Complete Usage | 184/184 |
| Missing response model | 0/184 |
| Transport failure | 0/184 |

The call set contains 156 Primary and 28 Rescue completion calls. Every call was a decision
request; no Job reached a final-answer request. Client-level outcomes were 134 public JSON
payloads, 48 reasoning-only length truncations, and two partial length-truncated contents.

Provider-reported Usage was:

| Item | Value |
| --- | ---: |
| Total tokens | 775,292 |
| Completion tokens | 444,089 |
| Reasoning tokens | 433,062 |
| Estimated cost telemetry | USD 0.16411017840000001316 |

Private reasoning content, private reasoning hashes, and raw HTTP bodies occur zero times in the
persisted artifacts. This audit does not infer or reconstruct private reasoning content.

The authoritative telemetry audit is:

```text
finance_v26_thinking_repair_failed_provider:80469ef6b905faf22fc5c75d9475393b55ba8b96e9dd6fac76797c8bfafe9935
```

## Completion Result

All 27 complete Raw Executions ended `completion_unusable`. They contain:

| Raw diagnostic | Count |
| --- | ---: |
| Logical requests | 149 |
| Request attempts | 176 |
| Primary attempts | 149 |
| Rescue attempts | 27 |
| Public Observations | 122 |
| Completed final results | 0 |
| Passing per-Raw budget audits | 27/27 |
| Typed no-calls | 0/27 |

Every complete Raw Job used its single Rescue and still ended unusable. Terminal causes were 24
reasoning-only length truncations, one partial length truncation, and two invalid response
contracts. Across all attempts in those Raw files, the failure artifacts contain 46 reasoning-only
truncations, two partial length truncations, and six invalid response contracts.

The 27 conforming Rescue Prompts in complete Raw files reduced Primary bytes by 1,055 to 3,243
basis points and therefore passed the frozen 10% Gate. Their cumulative Provider Usage ranged
from 10,640 to 54,782 tokens per Raw Execution, below the 120,000-token rollout ceiling.

The orphan Job separately persisted a Primary and Rescue response with `finish_reason=length`,
4,096 reasoning tokens, zero final content, and `reasoning_only_length_truncation` on both calls.
Those observations are retained, but the Job is not reclassified as a historical
`completion_unusable` terminal because its Rescue Prompt violated the frozen reduction Gate.

The exact 32-Job denominator was not completed, so v26.96 does not report an exact-denominator
Clopper-Pearson interval. It instead freezes a formal lower bound of 27 Completion-unusable Jobs.
The frozen Gate required zero failures. Therefore the Completion Gate cannot pass even if all five
remaining nonterminal Jobs, including the orphan, were treated as nonfailures. This is an
irreversible negative Completion result, not an exact completed-denominator estimate.

The authoritative Completion audit is:

```text
finance_v26_thinking_repair_completion_lower_bound:e3fbe9341aad15c77954163ea6a24318956ab97752972e5246265ddcb48b5afa
```

## Instrument Root Cause

The static v26.94 audit registered seven requests for the failing Compiler path. Its request index
6 was a final-answer request with:

- Primary Prompt: 2,865 UTF-8 bytes;
- maximum registered Rescue Prompt: 1,609 bytes;
- minimum registered reduction: 4,383 basis points.

The online trajectory had not reached that Compiler state. At online logical request index 6 it
still required a decision:

- Primary Prompt: 7,914 UTF-8 bytes;
- Rescue Prompt: 7,176 bytes;
- reduction: 738 bytes, or 932 basis points;
- frozen requirement: 1,000 basis points;
- shortfall: 68 basis points.

The online Primary hash and request kind both differ from the registered Compiler request. This is
not evidence that the v26.94 measurements for the 324 registered Compiler requests were wrong.
Those static requests retain their passing 11.54% to 64.39% reductions. The failure shows that
the static set did not cover arbitrary model-generated, off-Compiler Runtime states.

The gap was broader than one Job. Across the 27 complete Raw Executions:

- five Primary attempts had no registered request at their logical index;
- eight registered Primary attempts had a different request kind;
- 105 registered Primary attempts had a different Prompt hash;
- eight Jobs had at least one request-kind mismatch;
- 26 Jobs had at least one registered Primary hash mismatch.

Runtime did not reject a dynamic request-kind or Primary-hash mismatch before Provider invocation.
For Rescue calls, `_request_attempt` invoked and journaled the Provider first, then computed the
byte reduction and constructed `ThinkingRepairRequestAttempt`. Pydantic correctly rejected 932
basis points, but only after the Rescue HTTP-success call and Provider artifact existed.

The supported root cause is therefore:

```text
dynamic_off_path_rescue_contract_not_precall_closed
```

It is an Instrument coverage and check-order failure, not a transport, telemetry, exact-model, or
Provider budget failure. The authoritative root-cause identity is:

```text
finance_v26_thinking_repair_instrument_root_cause:84d0c4efe7cbb3aac1bfb45d61edf31a63d6e24d546c254d18495764404c63f4
```

## Prospective Transition

v26.96 does not authorize recovery execution of the four unopened Jobs. The exact Completion Gate
is already impossible to pass, and continuing only a fragment of a failed protocol would add
Provider exposure without changing the scientific decision. All four unopened v26.95 Job
identities are retired together with the 28 exposed identities.

The next stage must prospectively select one of two engineering directions:

1. change the Completion bound under a new budget and generation Contract; or
2. implement a true two-stage protocol that separates private Thinking from the bounded public
   decision channel.

The current evidence does not uniquely select one direction. It only rejects another Prompt-only
repair under the same 4,096-token bound.

Any successor must use fresh TaskPackage, Contract, Manifest, Job, execution, and report
identities. Before any Provider call, its Runner must validate the actual dynamic request kind,
certify the actual Primary and Rescue Prompts, and reject any reduction below its frozen Gate. A
static Compiler path audit alone is insufficient; reachable off-Compiler public states require a
prospective coverage or mechanically guaranteed rendering rule.

All current model-generated rows remain calibration-only and are ineligible for Capability,
Reachability, State Mapping, or release denominators. A Thinking-enabled role protocol is not
frozen.

The authoritative transition Contract is:

```text
finance_v26_thinking_repair_failure_transition:9036133329a0b6cff0e900773b19cd4fd3f7e33b72b09bde388fd49227bea6f4
```

## Destructive Controls

All twelve mutations failed closed. They attempted to:

- rerun one of the 28 exposed Jobs;
- continue the four unopened v26.95 Jobs;
- backfill a historical execution report;
- reclassify the Provider-orphan Job;
- rescue the failed historical Completion Gate;
- permit another same-bound Prompt-only repair;
- omit dynamic request-kind pre-call validation;
- omit dynamic Rescue-reduction pre-call validation;
- freeze a role protocol;
- authorize Capability execution;
- change the measured online reduction from 932 to 1,000 basis points;
- reopen the already failed Completion Gate.

The destructive audit identity is:

```text
finance_v26_thinking_repair_failure_destructive:53cea15f4804b21d8e9a0fb6b7c13e2a8f813e30c3f9933b965ebd809783aba2
```

## Determinism And Validation

The initial v1 build remains immutable and is superseded. Package-wide Mypy found one local
set-inference diagnostic after the focused source check had passed. The v2 successor adds the
explicit `set[str]` annotation and changes no Runtime value.

The failed-lineage, Provider-telemetry, Completion-lower-bound, and Instrument-root-cause detail
files are byte-identical across v1 and v2. Source replay, the transition Contract, destructive
audit, and report bind the final type-complete source and therefore have new identities.

The formal and independent v26.96 v2 builds reproduced all eight output files byte for byte. Both
replayed 723/723 files, constructed no client, made zero model calls, and used zero GPU jobs.
The failed execution and audit inputs were frozen on 2026-08-21; v2 type hardening, independent
rebuild, repository validation, documentation, and commit completed after local midnight on
2026-08-22. The content-addressed `20260821` run date was retained.

Focused validation completed before repository-wide validation:

```text
Ruff check: passed
Ruff format: passed
Focused Mypy: passed
Package-wide Mypy: 396 source files; one retained v26.70 diagnostic
v26.96 focused tests: 7 passed in 2.56 seconds
v26.88-v26.96 adjacent regression: 82 passed in 85.49 seconds
Full Pytest: 1,103 passed, 4 expected skips, 1 retained warning in 855.86 seconds
formal/independent v2 build: all eight files byte-identical
```

The v26.95 online execution itself made 184 persisted completion calls and used zero local GPU.
No API call was made during v26.96.

## Scientific Interpretation

The historical v26.95 attempt is neither a successful 32-Job calibration nor a transport failure.
It contains a confirmed Instrument failure and an incomplete denominator. It also contains an
irreversible negative Completion lower bound: 27 complete Raw Jobs already fail a Gate that
requires zero failures.

The evidence supports two separate conclusions:

1. the v26.94 registered Compiler rescue projections remain valid static fixtures, but they did
   not certify arbitrary online Runtime states and the Runner enforced their reduction Gate too
   late;
2. exact Thinking Flash overwhelmingly consumed the 4,096-token public Completion channel in the
   exposed online trajectories, despite compact Primary responses and one compact Rescue.

The second conclusion is empirical for the exposed rows but does not create Capability or
Reachability evidence. The tasks remain shallow calibration tasks, no final-answer request was
reached, and the exact denominator was incomplete.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and Contribution remain forbidden. Production Contribution remains zero.

## Authoritative Artifacts

- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821/online_source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821/execution_contract.json`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821/frozen_repair_contract.json`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821/frozen_repair_job_manifest.json`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821/thinking_repair_job_results.checkpoint.jsonl`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821/runner_failures.checkpoint.jsonl`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821/raw_execution/`
- `artifacts/vtdo_experiment/finance_v26_95_thinking_completion_telemetry_repair_execution_v1_20260821/raw_provider_calls/`
- `artifacts/vtdo_experiment/finance_v26_96_thinking_repair_execution_failure_audit_v2_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_96_thinking_repair_execution_failure_audit_v2_20260821/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_96_thinking_repair_execution_failure_audit_v2_20260821/failed_execution_lineage_audit.json`
- `artifacts/vtdo_experiment/finance_v26_96_thinking_repair_execution_failure_audit_v2_20260821/provider_telemetry_audit.json`
- `artifacts/vtdo_experiment/finance_v26_96_thinking_repair_execution_failure_audit_v2_20260821/completion_lower_bound_audit.json`
- `artifacts/vtdo_experiment/finance_v26_96_thinking_repair_execution_failure_audit_v2_20260821/instrument_root_cause_audit.json`
- `artifacts/vtdo_experiment/finance_v26_96_thinking_repair_execution_failure_audit_v2_20260821/prospective_transition_contract.json`
- `artifacts/vtdo_experiment/finance_v26_96_thinking_repair_execution_failure_audit_v2_20260821/destructive_audit.json`
