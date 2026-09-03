# Finance v26.226 Fresh Exact v26.209 Parent-Bound Post-Response Serializer Repair Replacement Online Execution

## Scope And Decision

Finance v26.226 consumes only the v26.225 v3 authorization for
`fresh_exact_v209_parent_bound_postresponse_serializer_repair_exact_192_job_replacement_online_execution_only`.
It follows the exact operator sequence:

```text
修正后执行独立审计，然后重跑
如果修订后的审计无误，重跑在线测试，我授予权限
继续任务
```

Two credential-free reviews passed before execution. They independently rebuilt v26.225 v3 and
v26.224, executed the mock success/error routes, and rejected single and jointly replaced
execution parents at the internal consumption boundary. Neither review read a credential or
called the Provider.

The one-shot replacement then attempted all 192 exact v26.209 Jobs. It completed the execution
process and sealed an immutable directory, but 36 Jobs did not produce terminal evidence. The
decision is therefore:

```text
v26_226_whole_condition_replacement_execution_completed_
artifact_relations_closed_but_36_jobs_failed_
execution_incomplete_postrun_independent_audit_required
```

This is not a completed 192-Job empirical evidence set and creates no Capability estimate. The
v26.225 v3 authorization is consumed and cannot authorize a replacement, rerun, or recovery.

## Authorization Consumption And Run Start

Immediately before execution the live path independently reloaded all fixed v26.225 v3 formal
bytes twice: once at the outer entry and again inside `_consume`. It compared every execution
parent and resolved path, then validated the exact 30,219-byte authorization at SHA-256
`a5832b12d20e1dd63be31d544463e2c5b2566658b4bcc5859843e06ad3089c7a`.

The global no-replace ledger was created before the output directory. The output copy of the
consumption Receipt is byte-identical to the ledger. The Run Start Receipt was then durably
written before `.env` loading, credential lookup, or client construction:

- authorization:
  `finance_v26_225_repaired_replacement_execution_authorization:819e35f1d63d05a32aa0cfefc55ce750a92330b2788ab19b23833aa0ebab51c7`;
- consumption Receipt:
  `finance_v26_226_replacement_authorization_consumption_receipt:39f7768a9dab2a8ce219c9d7a6b6d3168e49f4280d50e5ba517f1e4f2ae01b9a`;
- Run Start Receipt:
  `finance_v26_226_replacement_run_start_receipt:e9875feb97ee1cc66b0c0228c22494f02d89c5489a3332a5aa3584a8d8801197`.

The Receipt timestamps are `2026-09-03T17:31:10.405787Z` and
`2026-09-03T17:31:10.406718Z`. The execution source commit/tree bound by Run Start are:

```text
commit  a52df3e215f681a855bfdc94aafe9d699f08a59c
tree    6600c26140eafe5581f3ca727281638df07b5d14
```

The exact Job-set SHA-256 remains
`153ad4c7089e75954a223263a183bc969d2c7d57e2081c49bed9096b11bd60f7`.
Replacement Jobs are 192; selective rerun and recovery Jobs are zero.

## Provider Journal And Usage

The run used eight workers and issued 611 calls. Every pre-call intent closes with exactly one
descriptor, one Usage metadata object, and one response or error metadata object:

```text
request intents / descriptors                   611 / 611
response / error metadata                       578 / 33
Usage metadata                                       611
orphan intents / descriptors                       0 / 0
invalid relations                                     0
relation closed                                     true
```

The Provider tree contains 2,444 files. All 611 calls returned HTTP 200 from exact requested,
selected, and response model `deepseek-v4-flash`; Thinking is present in all 611 Usage rows.
There are 578 succeeded descriptors and 33 typed `provider_error` descriptors. The error
partition is:

```text
ReasoningBudgetExhaustedError                         31
  finish=length, public content length zero           31
  completion/reasoning tokens 16,384 / 16,384         28
  completion/reasoning tokens 16,383 / 16,383          3
JSONDecodeError                                        2
  finish=length / finish=stop                        1 / 1
```

Usage arithmetic is exact in 611/611 rows:

```text
Prompt tokens       3,585,599
Completion tokens   3,480,837
Reasoning tokens    3,422,511
total tokens        7,066,436
estimated cost USD  1.33152428080000012119
```

The cost is the sum of persisted Provider-cache-breakdown estimates, not a billing invoice.
Credentials, Prompt bodies, raw request bodies, raw Provider responses, and private reasoning
content are not persisted. All corresponding presence flags are false.

The Provider Census identity is
`finance_v26_226_provider_intent_census:bc758841db428bcd89d8b3f0a91adf83c5716b13d2529c2bafcd1ebfe5e45024`.

## Job And Terminal Partition

All 192 Job identities were attempted exactly once. There are 156 complete Job records and 36
failure records:

```text
completed records / failures                      156 / 36
Raw / Result / Trace / Outcome              156 each
checkpoints                                             156
exception escapes from top-level execution                0
```

The complete terminal partition is:

```text
completed_qualified                                    126
final_response_abi_invalid                              26
completed_invalid                                        2
first_response_abi_invalid                               2
other source-bound terminal kinds                        0
```

Complete Jobs use one through five Provider calls. The observed terminal/call distribution is:

```text
completed_qualified: calls 2/3/4/5       37 / 35 / 28 / 26
final_response_abi_invalid: 2/3/4/5        9 / 7 / 4 / 6
completed_invalid: calls 3/4                       1 / 1
first_response_abi_invalid: call 1                     2
```

The 126 qualified terminals are descriptive model outcomes inside an incomplete denominator.
No empirical estimate is materialized, and no weighting, confidence interval, QA, Mapper, State,
frequency, Contribution, or VTDO object is created.

## Failure Partition

Thirty-three Jobs end as `unbound_provider_failure`. Their Job-level failure digest partition is
one exact digest,
`bf06dd05d7431b80d5a218229dd0c1b6251b7e801ba4ade9e745d4a61ae3ca2f`,
while the Provider Journal retains three typed error digests corresponding to the 31 reasoning
budget exits and two JSON decode exits described above. Independent reconstruction confirms that
all 33 Job hashes bind the exact fail-closed exception
`UnboundExecutionFailure: Provider failure has no admitted v26.209 source terminal`. This is not
missing Journal evidence: each failed call has a complete request/error/Usage/descriptor chain.
The two JSON response texts were deliberately not persisted, so their precise syntax defects
cannot be reconstructed and are not guessed.

Three Jobs end as `host_failure` after two or three successful Provider calls. Their persisted
failure digest partition is:

```text
cb7d691ac6f6cae0152642ce267c69106719c43b812d6860ecd57955785e4ee2  2
62b6b9b098a85e0666673231c87d0f60f4197e44279869843dc01151e077726c  1
```

The execution record intentionally stores only these one-way exception digests. The postrun audit
replayed the saved public projections through the exact v26.209 Runner without a Provider call and
reproduced the full exception hashes:

```text
ordinals 6 and 22
  UnboundExecutionFailure:
  v26.213 parser evidence cannot bind a subsequent_action record

ordinal 149
  UnboundExecutionFailure:
  v26.213 reference evidence cannot bind a subsequent_action record
```

The deterministic Host blocker is therefore
`SUBSEQUENT_ACTION_PARSER_REFERENCE_EVIDENCE_DOMAIN_NOT_CLOSED`. No historical terminal is
assigned to these three failed Jobs.

## Artifact Geometry And Identities

The immutable execution directory contains 3,428 files and 99,765,014 bytes. Its self-excluding
Manifest contains 3,427 members and 99,047,004 bytes. Direct inspection finds zero missing,
additional, SHA-mismatched, or byte-count-mismatched Manifest members.

Principal identities are:

- Summary:
  `finance_v26_226_execution_summary:459c05325e7d8b1201b4ee9c5cca903876c8bd70f331b97db5d3245b59d82bbd`;
- Transition:
  `finance_v26_226_transition:e5b3a3b173cf91c5bf6150c3279fa053608c09d2f3d4679084d54cc4f32207b7`;
- Artifact Manifest / Root:
  `finance_v26_226_artifact_manifest:19cef807ae34c71c13d526c09c385163d1b30b2ced05322e3ec7e6f0e803d217` /
  `finance_v26_226_artifact_root:7ac11713bf70dbd57297b6d87db0e6982ce5ad8222849e3a4826020904f95280`.

The Manifest file itself is 718,010 bytes at SHA-256
`d6cc9799114ad0015fe8e781317e1b0eae498a09fc109f8ead199c1b11e38ee1`.
The 3,611,241-byte Summary is SHA-256
`337b5156fc86f5159a1c7081c9978105351dfc5217b12e7254669c37d6728122`.

## Independent Postrun Audit

Two independent, credential-free audits read the immutable record commit `bb70da41` and did not
use the saved Census, Summary, or Transition as outcome oracles. Both return:

```text
SCOPED_ARTIFACT_COMPLETENESS       PASS
EXACT_192_JOB_EXECUTION_COMPLETION FAIL / INCOMPLETE
```

The audits independently establish:

- all 3,427 Manifest members and all 3,426 JSON-file canonical encodings match actual bytes;
- authorization, source, global ledger, consumption Receipt, Run Start Receipt, and ingress are
  exact, with filesystem order ledger/Receipt -> Run Start -> first Provider intent;
- all 611 Provider relationships reconstruct with exact paths, Jobs, ordinals, request hashes,
  token parents, artifact identities, and descriptor identities, and every descriptor is
  referenced by exactly one Job record;
- all 192 authorization Jobs and ordinals occur once, split 156 execution and 36 failure records;
- all 780 Raw/Result/Trace/Outcome/checkpoint files have exact content identities, paths,
  persisted sequences, embedded parent links, terminal joins, and actual write order;
- the four Raw/Result/Trace/Outcome namespace sets remain unique; and
- independently rebuilt Census, Summary, Transition, Manifest, and Root match the saved objects
  byte for byte only after the underlying checks pass.

The first blocking seam is the subsequent-Action evidence-domain gap above. The second incomplete
partition is 33 fail-closed Provider response errors with no admitted v26.209 source terminal.
Neither permits downstream estimation. The audit makes zero Provider calls, reads no credential,
and writes no experiment artifact.

## Transition And Prohibitions

The immutable execution Transition is `INCOMPLETE_AWAITING_POSTRUN_INDEPENDENT_AUDIT` and named:

```text
fresh_exact_v209_parent_bound_replacement_execution_
postrun_independent_audit_only
```

That read-only transition has now been consumed by the two audits above. Their current decision is
`v26_226_artifact_complete_execution_incomplete_at_subsequent_action_evidence_domain_and_unbound_provider_response_failures`.
No successor is authorized. Any repair of the subsequent-Action composition, or any fresh
recovery Population for the 33 Provider failures, requires a separate external audit decision,
fresh identities, preflight, independent audit, and authorization. Replacement, rerun, recovery,
empirical estimation, QA, Mapper, State, frequency, Contribution, VTDO, training, release, and
production remain forbidden.
