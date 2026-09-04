# Finance v26.234 Fresh Exact v26.209 Unbound-Provider-Failure Recovery Online Execution Postrun Independent Audit

## Scope And Decision

Finance v26.234 consumes only
`fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_postrun_independent_audit_only`.
The exact 17,401-byte external review is bound at SHA-256
`f9331fb9310c5b29f5af5df488c10d682b8f6725c29b035eb01d744c0e08c9c0`. It classifies
v26.233 as `PASS_AS_SCOPED`, reports `BLOCKING_DEFECT=NONE_FOUND` and
`MANDATORY_REVISION=NONE`, and authorizes only this zero-Provider postrun independent audit.
The exact 42-byte operator directive `参照审计报告开展后续实验修订`, SHA-256
`e3adc8d65f07c54893d36828d8c12bdca9e83ab8a07fb94e40a259a2a18bcf73`, consumes only
that transition.

The independent decision is:

```text
v26_233_exact_33_job_recovery_attempt_execution_independently_confirmed_
terminal_evidence_set_incomplete
```

All seven noncompensatory audit Gates pass. The exact 33-Job attempted-Recovery population is
closed, but the terminal evidence population remains 16/33 and therefore incomplete. The other
17 Jobs remain fresh `unbound_provider_failure` records; none is converted to a Registry
terminal. No Provider call, credential lookup, retry, historical prefix reissue, v26.226 write,
terminal backfill, empirical row, or empirical estimate occurs during v26.234.

This result accepts the integrity and exact partition of the v26.233 execution. It does not
accept a complete scientific denominator, a Recovery success rate, a Capability estimate, or the
use of the eight `completed_qualified` rows in a frozen estimand.

## Exact Source And v26.233 Execution Freeze

The v26.234 audit implementation is bound to:

```text
source commit  515324a0ed38fea288ba934725a0671062b663ff
source tree    8b22a4e8d9251c894af2daac61f69e8a17a7ddf7
source members                                                    2
committed/current byte matches                                  2 / 2
```

The two members are the v26.234 model and audit modules. The audit also independently resolves
the exact v26.233 source commit/tree and rereads its two committed implementation members:

```text
v26.233 source commit  0c10e93a10ba85f89725be565137d8cc890d1ce4
v26.233 source tree    379083e1c04f1617a91b71828083a14ad346594e
committed/current byte matches                                2 / 2
saved ExecutionSourceIdentity member matches                  2 / 2
```

The combined source authority is
`finance_v26_234_source_authority_audit:7d8e6c4ef29bd56ed1894afd3400b2b4606f256bd409a820d0a4dffffe457123`.
The v26.234 implementation imports the v26.233 schemas but not the v26.233 executor. Its AST
boundary rejects calls to `prepare_execution`, `execute`, `_execute_job`, `_persist_chain`,
`_derive_recovery_terminal`, Provider client methods, and `urlopen`.

Before interpreting any Recovery result, the audit enumerates the actual v26.233 directory and
validates the self-excluding Manifest from its physical bytes:

```text
formal files / bytes                 381 / 12,265,007
Manifest file bytes                                80,483
Manifest file SHA-256  1044931f77953b584c4efd857629c9030d35e390b60219d0f382a9b65f5fde5d
Manifest members / bytes             380 / 12,184,524
path matches                                     380 / 380
SHA-256 matches                                  380 / 380
byte-count matches                               380 / 380
actual-byte matches                              380 / 380
```

The retained v26.224-prefixed serializer identities are:

- Manifest:
  `finance_v26_224_artifact_manifest:06d5c3d26a99e6b614c71a5791249f1ede5852244e0d66df71117609bdc9f626`;
- Root:
  `finance_v26_224_artifact_root:652730c3c535232fa99c310ca5fac3322a65778dd376751eac49107e5d5cb60b`.

The prefix is historical serializer identity, not evidence that this directory is a v26.224
execution. The audit recomputes the Manifest and Root using the v26.233 run ID and exact 380-member
set and requires the saved bytes to match.

The consumption Receipt and Run Start Receipt are parsed independently. Their preparation,
authorization, source, and recovery-set parents agree; consumption is exactly one, and both
receipts record zero credential lookups and Provider calls before the credential boundary. The
saved v26.233 Summary and Transition are frozen only as final comparison targets:

- Summary:
  `finance_v26_233_execution_summary:af4e4ceaa286a2cd93b1dcb5433104b70509918205ffb2cf457fe8745ad6b233`;
- Transition:
  `finance_v26_233_transition:475f270536c7448f8d687ce982cb55534a4862e783f63d543a2bd9a5ae04640f`.

Neither is used to select Jobs, terminals, failures, calls, token totals, or the passing Decision.
The Freeze identity is
`finance_v26_234_v233_execution_freeze_audit:0729f201240ed75800042cbe24e194dc5c401440ca72a7f91b904f40bc53ac72`.

## Independent Recovery Source, Prefix, And Handoff Audit

The audit starts from the 33 actual v26.229 `source_rows`, `recovery_candidates`, and
`recovery_jobs`, not from the v26.233 Summary. For every ordinal it:

1. validates the exact v26.229 Pydantic object and canonical bytes;
2. rereads the exact v26.226 failure file bound by the source row;
3. locates every historical Provider descriptor from the actual artifact paths;
4. validates each descriptor and its request/response-or-error/Usage artifact bytes;
5. compares the exact request and public-response hashes with the v26.229 replay row;
6. compares the first v26.233 fresh call with the captured failed request hash, byte count,
   validation certificate, and pre-transport receipt.

The result is:

```text
exact source rows / Recovery Jobs                     33 / 33
historical successful public projections                   55
historical prefix Provider reissues                           0
captured failed-request handoffs                         33 / 33
first fresh request hash matches                         33 / 33
first fresh request byte-count matches                   33 / 33
first fresh certificate / receipt matches                33 / 33, 33 / 33
Provider calls during audit                                   0
```

The exact source ordinals are:

```text
9, 10, 16, 21, 32, 58, 62, 63, 72, 78, 79, 92, 102, 103, 106, 110, 112,
114, 116, 121, 127, 129, 130, 131, 132, 135, 136, 139, 144, 147, 155, 171, 180
```

The Recovery authority Audit is
`finance_v26_234_recovery_authority_audit:2b5cbb844acaf8dca1915fdc0cf03b4f73ca2d39687c3d7fc4c7003dfe2d65c5`.
This verifies the exact historical-to-fresh handoff. It does not rerun the historical requests or
invent missing historical response bytes.

## Independent 64-Call Provider Journal Reconstruction

The audit enumerates every actual `call_*_descriptor.json` and metadata file under the v26.233
Provider-call namespace, then requires exact set equality with the descriptors embedded in the
16 terminal and 17 failure records. For every call it reparses the descriptor identity and checks:

- the request metadata's Job, call ordinal, request hash, Run Start parent, Provider permission,
  no-retry flag, and absence of raw request persistence;
- the response or error metadata's Provider-call parent, public projection or error hash, and
  absence of raw/private reasoning persistence;
- the Usage metadata's request hash and prompt/completion/total token relation;
- all three artifact paths, hashes, byte counts, and descriptor parents.

The independently reconstructed journal is:

```text
fresh Provider descriptors / artifacts                 64 / 192
succeeded / provider_error / transport_error             47 / 17 / 0
ReasoningBudgetExhaustedError / JSONDecodeError           16 / 1
first fresh captured-request handoffs                         33
input / output tokens                            464,481 / 637,076
orphan descriptors / artifacts                                0 / 0
Provider calls during audit                                    0
```

The per-Job fresh-call count distribution is:

```text
1 call: 14 Jobs
2 calls: 10 Jobs
3 calls:  6 Jobs
4 calls:  3 Jobs
```

This distribution confirms that later calls are Runtime continuation calls. It is not evidence
of retrying the captured failed request; the exact captured request occurs only as fresh call
ordinal zero in each Recovery Job. The journal Audit is
`finance_v26_234_independent_provider_journal_audit:09baae559773277aa70e61851ddd393c155e9f1fda94302160c56534a70ed91f`.

## Independent Terminal And Five-Layer Reconstruction

The audit enumerates the sixteen actual terminal-record files directly. It validates each complete
v26.209 invocation sequence, requiring contiguous invocation indices and the exact historical Job.
The initial invocation prefix is paired in order with the 55 historical public projections; the
remainder is paired with successful v26.233 fresh calls. Request hash, validation certificate,
pre-transport receipt, and public-response hash must agree at every invocation.

Observed Evidence is reparsed through the strict v26.213 evidence union. The audit reads the
actual v26.195 reachable Registry and the v26.213 Dispatcher/Persistence Bindings, and derives the
Decision without calling the v26.233 terminal helper:

```text
completed_runner and qualified_valid=true
  -> completed_qualified
  -> exact reachable v26.195 policy

completed_runner and qualified_valid=false
  -> completed_invalid
  -> exact reachable v26.195 policy

final_parser_rejection
  -> final_response_abi_invalid
  -> exact reachable v26.195 policy
```

All sixteen derived Decision bytes equal their Raw-embedded Decision bytes. Starting from the
independently validated Evidence, Decisions, invocations, calls, source rows, and persistence
Binding, the audit constructs each payload and descriptor in order:

```text
Raw -> Result -> Trace -> Outcome -> checkpoint
```

It recomputes each Recovery namespace, exact payload SHA-256 and byte count, descriptor identity,
parent descriptor set, Provider-call parent set, and persistence sequence. The resulting partition
is:

```text
terminal records                                           16
completed_qualified / completed_invalid                     8 / 1
final_response_abi_invalid                                      7
derived terminal / Decision matches                       16 / 16
five-layer files / actual-byte matches                    80 / 80
parent / namespace matches                                80 / 80
historical reclassifications / empirical rows               0 / 0
```

The sixteen terminal ordinals are:

```text
16, 21, 62, 78, 103, 106, 116, 121, 127, 130, 131, 132, 136, 139, 147, 155
```

The terminal Audit is
`finance_v26_234_independent_terminal_reconstruction_audit:65fb405fb323cf6e37b16853f0ea982ad062a173d9b88ee84e6512bb75e82d09`.
The eight qualified outcomes remain descriptive Recovery execution records. v26.234 does not
place them in an empirical numerator.

## Independent Failure Reconstruction

The other seventeen files are parsed as strict `RecoveryFailureRecord` objects. For every Job,
all prior fresh calls must be successful, the last descriptor must be a Provider failure, and no
unreferenced later descriptor may exist in the exact Provider-call file set. The failure record is
then rebuilt from the Recovery source row, candidate, Job, exact phase, complete fresh-call tuple,
and source-bound outer error hash; only after construction are its canonical bytes compared with
the saved record.

```text
failure records / unbound Provider failures               17 / 17
Host failures                                                    0
ReasoningBudgetExhaustedError / JSONDecodeError             16 / 1
last-call failure matches                                  17 / 17
no-later-call matches                                      17 / 17
terminal-evidence / five-layer admission                     0 / 0
historical reclassification / empirical estimate             0 / 0
```

The failure ordinals are:

```text
9, 10, 32, 58, 63, 72, 79, 92, 102, 110, 112, 114, 129, 135, 144, 171, 180
```

Sixteen final errors have `ReasoningBudgetExhaustedError`; one, ordinal 102, has
`JSONDecodeError`. Those metadata labels describe observed Provider-call failures. They are not
authorized terminal mappings, and v26.234 does not map them to `thinking_integrity_failure`,
`resource_budget_exhausted`, `completed_invalid`, or any other Registry terminal. The failure
Audit is
`finance_v26_234_independent_failure_reconstruction_audit:4e026bab37508cb6c1d7fee053357770b9c275d6a82d767a43f63d0bb27073cc`.

## Exact Noncompensatory Partition And Saved-Target Comparison

After the terminal and failure rows are independently reconstructed, the audit combines them and
derives all counts and token sums. The Job sets are disjoint and their union equals the exact 33
v26.229 Recovery ordinals.

```text
attempted Jobs                                      33 / 33
terminal / failure records                           16 / 17
fresh Provider calls                                     64
failed-request phase partition       first/subsequent/final = 3 / 25 / 5
execution status                                     incomplete
scientific denominator complete                          false
historical mutation / backfill / estimate                0 / 0 / 0
```

Only at this point does the audit construct a complete v26.233 `ExecutionSummary` from the
independent record tuples and compare it byte for byte with `execution_summary.json`. It then
constructs the exact v26.233 incomplete Transition and compares it with the saved Transition.
Both actual-byte comparisons pass. This avoids using either target as an outcome oracle.

The exact partition Audit is
`finance_v26_234_exact_recovery_partition_audit:7378f4ac47ad218add4023fdc1101976c69805403aa2777124212811b9c9a351`.

## Noncompensatory Audit Gates

```text
A0 exact external scope and source authority                 PASS
A1 actual Manifest and all 380 members                       PASS
A2 33 source rows, 55 prefixes, and 33 handoffs              PASS
A3 64 actual Provider descriptors and artifacts              PASS
A4 16 terminals and 80 five-layer files                      PASS
A5 17 failures and exact 33-record partition                 PASS
A6 zero Provider, mutation, backfill, and estimate           PASS
passed / failed                                               7 / 0
```

No Gate compensates for another. A source mismatch, Manifest member mismatch, crossed Recovery
row, prefix or handoff mismatch, orphan Provider artifact, non-source-derived terminal, changed
layer byte or parent, hidden later call, terminalized Provider failure, Summary-oracle use, or
scope expansion prevents the passing Decision. The Gate identity is
`finance_v26_234_gate_evaluation:800aafa16e5fd5da16e1c2251bec4a9961030ce8b31e0a186aab04b73ae086bc`.

The scope Audit is
`finance_v26_234_scope_boundary_audit:70dee789d944bcb6ff4e754b9a3dd9ef617f7adc4bfa2b023574a7bca55cbdd0`.

## Authoritative Identities

The principal v26.234 identities are:

- external authorization / source authority:
  `finance_v26_234_external_independent_audit_authorization:74d4cb93e9b8fae2f7bbdc9dd765d21e79dcd1af2421d47dd5f6ef2292431e1e` /
  `finance_v26_234_source_authority_audit:7d8e6c4ef29bd56ed1894afd3400b2b4606f256bd409a820d0a4dffffe457123`;
- v26.233 Freeze / Recovery authority:
  `finance_v26_234_v233_execution_freeze_audit:0729f201240ed75800042cbe24e194dc5c401440ca72a7f91b904f40bc53ac72` /
  `finance_v26_234_recovery_authority_audit:2b5cbb844acaf8dca1915fdc0cf03b4f73ca2d39687c3d7fc4c7003dfe2d65c5`;
- Provider journal / terminal reconstruction:
  `finance_v26_234_independent_provider_journal_audit:09baae559773277aa70e61851ddd393c155e9f1fda94302160c56534a70ed91f` /
  `finance_v26_234_independent_terminal_reconstruction_audit:65fb405fb323cf6e37b16853f0ea982ad062a173d9b88ee84e6512bb75e82d09`;
- failure reconstruction / exact partition:
  `finance_v26_234_independent_failure_reconstruction_audit:4e026bab37508cb6c1d7fee053357770b9c275d6a82d767a43f63d0bb27073cc` /
  `finance_v26_234_exact_recovery_partition_audit:7378f4ac47ad218add4023fdc1101976c69805403aa2777124212811b9c9a351`;
- Gate / Decision / Transition:
  `finance_v26_234_gate_evaluation:800aafa16e5fd5da16e1c2251bec4a9961030ce8b31e0a186aab04b73ae086bc` /
  `finance_v26_234_postrun_independent_audit_decision:972e0e0a46b38508eb0e7528a796724a5f204b60ca4bcd53aed2d5fc6d209818` /
  `finance_v26_234_transition:f2c8da32f39fdf4b7de3a72f70b4fbe03bf5f96e23090429c9069c2ef3c2645b`;
- report:
  `finance_v26_234_postrun_independent_audit_report:e73e4477310135c6244f980166875dd50e0120cd9ddf6e7f0642ff198e3901fd`;
- Artifact Manifest / Root:
  `finance_v26_234_artifact_manifest:290028fd3341c3b1800c1f08ccb8b62a203a860707c0ee87e0aad72f18d1bcfb` /
  `finance_v26_234_artifact_root:0739bc9fa30e25b34d5a089b9ddb3ae0a0f4303a201598a04702152bb5198537`.

## Reproducibility And Verification

The formal v26.234 directory contains sixteen files and 215,941 bytes. Its self-excluding
Manifest binds fifteen members and 213,237 bytes. The 2,704-byte Manifest file has SHA-256
`2042833374bef0bd4989f2c124a345c4ea21e1532a7df70f13d102fad03d7b1c`.

A complete second build into an empty directory reproduces all sixteen paths and actual bytes.
Focused v26.234 tests pass 9/9. The process-local v26.229-v26.234 adjacent partition passes 56/56.
Focused PyCompile, Ruff check/format, and no-import-follow Mypy pass.

Package-wide Ruff continues to report one pre-existing import-order diagnostic in the immutable
v26.233 model module. v26.234 does not rewrite that source because its exact committed/current
bytes are part of the execution source authority. The diagnostic does not affect the focused
v26.234 or adjacent runtime results and is retained rather than misreported as a package-wide
pass.

## Claim Boundary And Transition

The evidence establishes only:

- exact-byte integrity of all 380 v26.233 Manifest members;
- exact source authority for v26.233 and the v26.234 independent implementation;
- exact 33-row Recovery source population, 55 local historical projections, and 33 first-fresh
  captured-request handoffs;
- independent reconstruction of all 64 fresh Provider descriptors and 192 metadata artifacts;
- independent derivation of sixteen terminals and byte reconstruction of all eighty layers;
- independent reconstruction of seventeen unbound Provider failures ending at the final fresh
  call with no later descriptor;
- exact confirmation of the noncompensatory 16-terminal/17-failure partition and incomplete
  scientific denominator.

It does not establish a 33/33 terminalized Recovery set, a complete 192-Job empirical evidence
set, a Recovery rate, Capability, the contribution of qualified Recovery rows to an estimand, a
Registry terminal for the seventeen Provider failures, or permission to retry them.

The independent audit is complete and grants no successor authority:

```text
no_further_experiment_authorized_without_new_audit_decision
```

Provider execution, failed-Job retry, another Recovery run, historical response reuse, v26.226
mutation or terminal backfill, condition change, empirical estimation, QA integration, Mapper,
State, frequency, Contribution, VTDO, training, release, and production remain forbidden. Any
future evidence-set integration or treatment of the seventeen failures requires a separate new
external audit decision.
