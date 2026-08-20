# Finance v26.84-v26.85 Budget-Closed Failure And Recovery Preflight

> Historical preflight note: v26.86 completed the frozen Recovery and v26.87 independently
> retained its passing Instrument result. See
> `docs/finance_v26_84_v26_87_budget_closed_instrument_recovery_and_audit.md`.

Audit and protocol date: 2026-08-20

## Scope

This document records the fail-closed v26.84 online attempt and the only continuation permitted
by its immutable artifacts. It does not reclassify v26.78-v26.80, v26.71 Capability, v26.72
Reachability, or any diagnostic candidate. It authorizes neither Capability nor Reachability
execution.

The v26.84 attempt used exactly the v26.83 Contract and 32-Job Manifest:

- Contract:
  `finance_v26_budget_closed_instrument_contract:12c9789ccbe3d557411cf5428a15ee0e3d26337b846f47b61b830c86e1415121`;
- Manifest:
  `finance_v26_budget_closed_instrument_manifest:38f4a8f5b40c2c576c690c3069c66bc1f43a64f52ef554a16ea28a4656c2434c`;
- Provider budget Contract:
  `provider_token_budget_contract:27e7e524cb3139b9dd29b1ca7f2c7eae1956c96af8a982524f814b3ef4415150`;
- v26.84 execution Binding:
  `finance_v26_budget_closed_instrument_execution_binding:772d296b3c42aa43e786affa35f8759b47d056384719524f19fdc8c57fd6a40c`;
- v26.84 online source replay:
  `finance_v26_budget_closed_online_source_replay:14a5c9a0b5800611c6986aa581f42afb565b2cf4cca31f1efe54b2ae85c701e2`.

The online source commit was
`6f246cacbe2a8d47c19fe857063272de0179cf2c`. The worktree was clean before client construction.

## Immutable v26.84 Outcome

The Runner started all 32 Futures with 16 workers. Four short Jobs completed and freed worker
slots before the main `as_completed` loop observed the first failed Future. Four additional Jobs
therefore began before queued Futures were cancelled. The Executor then waited for the 20 already
running Futures to stop. The observed denominator is:

| Item | Immutable value |
| --- | ---: |
| Exposed Jobs | 20 |
| Unopened Jobs | 12 |
| Raw Provider calls | 152 |
| Provider-reported tokens | 1,380,628 |
| Estimated cost telemetry | USD 0.17555657840000001851 |
| HTTP-success responses | 152 |
| Exact requested/selected/response model | 152 / 152 / 152 |
| Fallbacks | 0 |
| Raw Execution Artifacts | 4 |
| Rollout checkpoint rows | 3 |
| Runner failure rows | 1 |

All 152 Provider call indices are contiguous within Job. Every actual Prompt, response payload,
Provider telemetry object, Provider call identity, and raw file was persisted before Agent
scoring. Provider call identities are globally unique. The other 12 Jobs have no Provider file
and were never opened.

The four Raw Executions are a strict superset of the three checkpoint rows. One worker had
persisted and scored its Raw Execution but the main thread encountered another failed Future
before appending that worker's rollout. This scheduling fact is retained; the fourth row is not
inserted into the historical checkpoint.

## Exact Failure Cause

The Provider budget wrapper behaved as frozen. The failed Raw Execution validator did not.

For each of 16 long Jobs, the wrapper certified and allowed the initial sequence of Provider
requests, then denied the next decision request before Provider invocation because its
conservative upper bound could not fit. The wrapper created one typed no-call terminal and froze
the Job's Provider authority. The Agent then attempted its contract-defined final-answer fallback.
The wrapper rejected that fallback immediately because a no-call terminal already existed. It did
not create another certificate and did not call the Provider.

A representative exact stream has:

```text
successful Provider calls                 = 8
permitted certificates                    = 8
denied no-call certificates                = 1
all certificates                           = 9
Host client-call attempts                  = 10
post-terminal short-circuit Prompts        = 1
Provider calls from short-circuit Prompts  = 0
```

The denied certificate had:

```text
reason_code                  = request_bound_exceeds_remaining_budget
cumulative tokens before    = 76,906
request upper bound          = 43,096
required reserves            = 8,192
projected upper total        = 128,194
rollout ceiling              = 120,000
```

The v26.84 `BudgetClosedRawExecution` validator required
`len(certificates) == len(attempted_model_prompts)`. That equality is false when the frozen
terminal short-circuits a later Host fallback before certificate construction. The correct
partition is:

```text
certificate request hashes = Host-attempt hash prefix
post-terminal short-circuit Prompts = remaining Host-attempt suffix
permitted certificate hashes = actual Provider Prompt hashes
Provider call count from short-circuit suffix = 0
```

The first reported Job therefore failed during Raw Execution model validation with
`raw execution budget accounting changed`. The Runner stopped and did not aggregate a v26.84
report. This is an Instrument assembly failure after valid budget closure, not a Provider budget
breach and not a model-outcome result.

## Zero-Generation Reconstruction

The v26.85 preflight consumed all 152 stored responses in exact per-Job order through the frozen
Agent Runtime and the same budget wrapper. It made zero API calls. All recorded Prompts and all
Provider telemetry fields before the single allowed Host augmentation matched. The reconstruction
produced:

| Terminal | Jobs |
| --- | ---: |
| Completed trajectory | 0 |
| Model-contract failure | 4 |
| Typed budget no-call | 16 |

It reconstructed 128 Observations and 16 post-terminal short-circuit Prompts. Each of the 16
short-circuit Prompts followed an already frozen typed no-call terminal and caused zero Provider
calls. The four short streams are the same four Raw Execution Artifacts persisted by v26.84; the
three checkpointed Job identities remain a strict subset.

The failed-run audit identity is:

`finance_v26_budget_failed_run_audit:9e6874b57eff45e53f0474a44d31790489d232a1c46f2937fce4f223f7796c5c`.

No reconstructed terminal is inserted into the immutable v26.84 checkpoint or treated as an
online v26.84 rollout. Reconstruction is evidence for the Recovery partition only.

## Corrected Recovery Schema

`BudgetRecoveryRawExecution` preserves three distinct ordered views:

1. actual Provider Prompts and raw Provider telemetry;
2. Host telemetry after the permitted `response_shape.prompt_component_bytes` augmentation;
3. every Host client-call attempt, partitioned into a certificate-bearing prefix and an explicit
   post-terminal short-circuit suffix.

The schema rejects a changed suffix, a certificate that does not bind the attempt prefix, a
permitted certificate without a matching Provider call, a Provider call without a Usage record,
or a short-circuit suffix without an already frozen no-call or failed budget terminal.

Raw Provider lineage, budget binding, Provider/Host telemetry equality, Runtime Replay, core
scoring, descriptive diagnostics, resources, and report aggregation retain separate failure
namespaces. A diagnostic failure cannot change the frozen core terminal.

## Frozen v26.85 Recovery Preflight

The v26.85 preflight replays 248 source and failed-execution files before any model-client
construction. It freezes this exact partition:

```text
zero-generation replay Jobs       = 20
unopened continuation Jobs         = 12
model calls permitted for replay   = 0
model calls permitted per unopened = exactly one Job execution
```

Authoritative identities are:

- failed-run audit:
  `finance_v26_budget_failed_run_audit:9e6874b57eff45e53f0474a44d31790489d232a1c46f2937fce4f223f7796c5c`;
- Recovery Contract:
  `finance_v26_budget_recovery_contract:5b3f9efe759d22b1159a3a854a3bb3f6628d80645c833e9c7c43d043ec15730f`;
- Recovery Manifest:
  `finance_v26_budget_recovery_manifest:19876887f71863af1152aa43ea9eda599a18baf3c468710b0c171b489164d3ee`;
- Recovery execution Binding:
  `finance_v26_budget_recovery_execution_binding:69de2b9a62ae0e478a79247ee2eb6d8c09706e43c87b37d59ddd59d8f6b8de8c`;
- Recovery source replay:
  `finance_v26_budget_recovery_source_replay:ec5bdd64882656596282b12b25e97d32f535c74487cb663fb0990650806450e1`;
- preflight report:
  `finance_v26_budget_recovery_preflight:f3e1af83b0b380fd14602417fd3770df7e92a532a4196fb4651bc0ab1d6ad964`.

The formal output directory is:

`artifacts/vtdo_experiment/finance_v26_85_budget_closed_recovery_preflight_20260820`.

Formal and independent builds must reproduce all eight top-level files byte for byte. Both builds
must report zero model-client construction, zero API calls, and zero GPU jobs.

## Authorized v26.86 Execution

The only permitted online transition is:

```text
zero_generation_replay_20_and_exact_unopened_12_continuation_only
```

Execution order is mandatory:

1. replay all 20 exposed streams and persist fresh Recovery Raw Execution and rollout identities;
2. verify exact Prompt, payload, telemetry, budget, and original-byte lineage for all 152 calls;
3. only then construct the exact DeepSeek V4-Flash client;
4. execute each of the 12 unopened Jobs once;
5. retain all model-invalid and typed no-call outcomes in the 32-Job denominator;
6. independently score Replay and non-Replay Gates and aggregate only after all 32 terminals exist.

If continuation Provider files exist without a Recovery Raw Execution, the Runner may consume
those files in zero-generation mode. It may not call the Provider again for that Job. If the
stored stream cannot reach a terminal without requesting an unobserved response, execution must
fail closed for a new raw-only audit.

The aggregate resource gate includes both the immutable v26.84 telemetry and the 12 continuation
Jobs. Total estimated cost must remain at or below USD 2.00. Every Job remains subject to the
120,000-token rollout ceiling and the frozen per-request bounds.

## Verification

Before formal preflight materialization, the focused recovery suite passed:

```text
4 passed, 1 formal-artifact test skipped
```

Coverage includes:

- exact 20/12 Job partition and 152-call replay;
- 4 Raw Execution versus 3 checkpoint scheduling lineage;
- certificate-prefix and short-circuit-suffix mutation rejection;
- full 32-Job fixture Recovery;
- exact-byte replay of all 152 original Provider files;
- completed-run replay with zero model-client construction and byte-identical report.

Ruff and Mypy pass for the Recovery implementation and focused tests.

## Authorization Boundary

A passing v26.86 Instrument Recovery may authorize only fresh Capability and Reachability
protocol design. It does not authorize either empirical denominator.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and production Contribution remain forbidden. Production Contribution is
zero. The 0/36 State Support Freeze remains authoritative. Compiler Witnesses remain static
fixtures and contribute zero empirical rows.
