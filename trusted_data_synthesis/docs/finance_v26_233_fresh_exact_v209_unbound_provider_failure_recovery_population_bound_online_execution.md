# Finance v26.233 Exact v26.209 Provider-Failure Recovery Online Execution

## Scope And Decision

Finance v26.233 consumed only
`fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_only`.
The exact 12,052-byte external review at SHA-256
`dc214719a86aaaac4526de1b247ac86438d73ae5db683514841c00eb329aec08`
classifies v26.232 as `PASS_AS_SCOPED` and directly authorizes the frozen 33-Job Recovery
Population. The exact 30-byte directive `参照审计继续实验修订` is bound at SHA-256
`d7f0a7b9c625edb3ec4d53a21418dd0b11ec7291a0ae934b98364ea651f9d3ca`.

The execution result is:

```text
exact_33_job_recovery_execution_completed_with_16_source_derived_terminals_
and_17_new_unbound_provider_failures_postrun_independent_audit_required
```

All 33 Recovery Jobs were attempted exactly once. The denominator is complete as an attempted
Recovery execution but `incomplete` as a terminalized denominator: sixteen Jobs have a fresh
source-derived terminal and five-layer chain, while seventeen have a fresh failure record. No
failed Recovery Job is retried. No historical v26.226 byte or terminal is changed or backfilled,
and no empirical estimate is created.

## Precredential Admission And Consumption

Before credential lookup, the execution revalidated the complete v26.232 and v26.229 formal
directories and every Manifest member. It reparsed the exact v26.232 authorization bytes, ran the
repaired Guard, rebuilt the 33-row v26.226 source authority, and locally reconstructed all v26.229
request-replay rows:

```text
Recovery Jobs / source rows / replay rows               33 / 33 / 33
persisted successful public projections                            55
captured failed requests                                           33
failed phases                              first 3 / subsequent 25 / final 5
request max_tokens                                             16,384
preparation credentials / Provider calls / writes              0 / 0 / 0
```

The exact authorization
`fresh_v26_232_exact_manifest_byte_bound_recovery_online_execution_authorization:c332e42c45bbd718a16ba65258099c9193cb84348b83f94960d3bf4bd015e371`
was consumed once. The durable Consumption and Run Start Receipts were written before credential
lookup:

- `finance_v26_233_authorization_consumption_receipt:592a7d02428ee121c159cff72a884aae9dd26544cb80a3c8813a8cc500394ffb`;
- `finance_v26_233_recovery_run_start_receipt:b8a80bbf2862d97da7fedd33e7c3b44960064a49f6124fa7596e1c60353189a1`.

The authorization is now non-reusable.

## Exact Replay And Online Continuation

For every Job, persisted public projections are supplied locally in exact invocation order. Their
request hashes, byte counts, certificates, receipts, phases, States, and Candidate parents must
match v26.229. These 55 dispatches make no Provider call. The next dispatch must equal the
captured failed request in body hash, byte count, certificate, receipt, and phase before it can
cross the Provider boundary.

```text
successful prefix projections replayed locally                    55
successful prefix Provider reissues                                0
captured failed requests reissued                                 33
first live request -> captured failed request matches          33 / 33
fresh Provider calls                                               64
succeeded / Provider-error calls                              47 / 17
live calls per Job                              {1:14, 2:10, 3:6, 4:3}
maximum historical-prefix + fresh-call count per Job                5
```

Historical prefix Usage remains part of each Job's 21-primary, 23-Provider-call and 1,120,000-
token bounds. Fresh accounting starts at zero only for new Provider artifacts; it does not erase
the historical trajectory prefix.

## Exact Outcome Partition

```text
completed_qualified                  8
completed_invalid                    1
final_response_abi_invalid           7
other source-derived terminals       0
terminal records                    16

unbound_provider_failure            17
host_failure                         0
ReasoningBudgetExhaustedError       16
JSONDecodeError                      1
```

The repeated reasoning-budget and JSON-decode events are fresh outcomes from the unchanged 16K
condition. They are not converted into model terminals, imputed from v26.226, or retried. A Job
may make successful continuation calls before a later call fails; therefore some failure records
contain multiple fresh Provider descriptors. This is continuation, not retry.

Every terminalized Job persists the source-derived Evidence and Decision followed by
Raw -> Result -> Trace -> Outcome -> checkpoint. The `subsequent_action` parser/reference path
derives its terminal from the actual final invocation record and complete same-Job prefix,
carrying forward the v26.227/v26.228 source rule without accepting caller terminal or policy
inputs.

```text
Raw / Result / Trace / Outcome / checkpoint              16 each
fresh five-layer files                                         80
historical v26.226 writes / backfills / estimates          0 / 0 / 0
```

## Source, Usage, And Artifacts

The exact source commit/tree are `0c10e93a10ba85f89725be565137d8cc890d1ce4` /
`379083e1c04f1617a91b71828083a14ad346594e`. Both implementation members match their
committed bytes. The source identity is
`finance_v26_233_execution_source_identity:f46d4c43edeccefacd07a5ace1b11ebf6346071ed39c52574fea5a3043e0c1b9`.

Fresh Provider Usage is 464,481 input and 637,076 output tokens; the recorded cost estimate is
USD 0.2106913592. These are engineering telemetry, not a Capability or frequency estimate.

The formal directory contains 381 files and 12,265,007 bytes. Its self-excluding Manifest binds
380 members and 12,184,524 bytes; all member hashes and byte counts revalidate. The reused generic
execution Manifest serializer retains its historical `finance_v26_224_artifact_manifest` /
`finance_v26_224_artifact_root` identity prefixes, while its `run_id`, path set, and members are
v26.233-specific.

- Summary:
  `finance_v26_233_execution_summary:af4e4ceaa286a2cd93b1dcb5433104b70509918205ffb2cf457fe8745ad6b233`;
- Transition:
  `finance_v26_233_transition:475f270536c7448f8d687ce982cb55534a4862e783f63d543a2bd9a5ae04640f`;
- Manifest / Root:
  `finance_v26_224_artifact_manifest:06d5c3d26a99e6b614c71a5791249f1ede5852244e0d66df71117609bdc9f626` /
  `finance_v26_224_artifact_root:652730c3c535232fa99c310ca5fac3322a65778dd376751eac49107e5d5cb60b`.

Focused execution tests pass 4/4 and the direct v26.232 authorization plus execution partition
passes 13/13. Focused PyCompile, Ruff format, no-import-follow Mypy, and exact Manifest member
validation pass. Ruff check reports one import-order-only `I001` diagnostic in the frozen model
module; the postrun tree preserves the executed commit bytes instead of rewriting that source.

## Transition And Prohibitions

The only prospective successor is
`fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_postrun_independent_audit_only`.
It is not authorized by v26.233. A separate external decision is required, and that audit must
make zero Provider calls.

Recovery retry, replacement execution, historical mutation/backfill, empirical estimation, QA,
Mapper, State, frequency, Contribution, VTDO, training, release, and production remain forbidden.
