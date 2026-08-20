# Finance v26.84-v26.87 Budget-Closed Instrument Recovery And Audit

Experiment and audit date: 2026-08-20

## Scope

This report records the complete online Instrument transition authorized by v26.83, including
the fail-closed v26.84 attempt, the v26.85 Recovery preflight, the v26.86 bounded continuation,
and the independent credential-free v26.87 post-run audit. Historical artifacts are not rewritten
or reclassified.

The empirical denominator is exactly the frozen v26.83 design:

```text
4 mechanisms x 2 fresh tasks x 4 unconditional replicas = 32 Jobs
```

The authoritative frozen inputs are:

- Contract:
  `finance_v26_budget_closed_instrument_contract:12c9789ccbe3d557411cf5428a15ee0e3d26337b846f47b61b830c86e1415121`;
- Job Manifest:
  `finance_v26_budget_closed_instrument_manifest:38f4a8f5b40c2c576c690c3069c66bc1f43a64f52ef554a16ea28a4656c2434c`;
- Provider token budget Contract:
  `provider_token_budget_contract:27e7e524cb3139b9dd29b1ca7f2c7eae1956c96af8a982524f814b3ef4415150`;
- qualified Verifier v2 report:
  `finance_v26_authority_verifier_qualification:f61be6be022c2c8506e818e3bb9690e71fa316c6820fec69458c7ab7c8fa7bb1`.

No v26.78-v26.80 Job was repeated or reclassified. No v26.81 prospective-valid candidate or
Compiler Witness entered task selection, the empirical denominator, Capability support, State
Mapping, or release counts.

## v26.84 Fail-Closed Attempt

v26.84 used the exact v26.83 Contract and Manifest. It exposed 20 Jobs and left 12 Jobs unopened.
Before the Runner stopped, it persisted 152 successful raw Provider calls, 1,380,628
provider-reported tokens, and USD 0.17555657840000001851 estimated cost telemetry. All responses
used exact `deepseek-v4-flash`, fallback was zero, and every actual Prompt and raw response was
persisted before parsing or scoring.

The Provider budget wrapper behaved as frozen. Sixteen long Jobs received a denied pre-call
certificate and a typed `budget_exhausted_no_call` terminal before Provider invocation. A later
Host final-answer fallback was correctly short-circuited after that terminal and created neither
a certificate nor a Provider call.

The online Raw Execution schema incorrectly required the number of certificates to equal all Host
call attempts. It did not account for the explicit post-terminal short-circuit suffix. The first
observed Future therefore failed during Raw Execution assembly. This is an Instrument assembly
failure after valid budget closure, not a budget breach or a model-capability result.

The immutable v26.84 denominator remains:

| Item | Value |
| --- | ---: |
| Exposed Jobs | 20 |
| Unopened Jobs | 12 |
| Provider calls | 152 |
| Provider-reported tokens | 1,380,628 |
| Estimated cost telemetry | USD 0.17555657840000001851 |
| Raw Execution Artifacts | 4 |
| Checkpoint rows | 3 |
| Runner failure rows | 1 |

The fourth Raw Execution had completed before the main thread observed a different failed Future,
but it was not appended to the historical checkpoint. That scheduling fact remains unchanged.

## v26.85 Recovery Contract

A zero-generation audit consumed all 152 stored responses in exact Job and call order. It
reconstructed 4 model-contract failures, 16 typed no-call terminals, 128 Observations, and 16
post-terminal short-circuit Prompts. It made no API call and did not insert reconstructed rows into
the v26.84 checkpoint.

The corrected Recovery Raw Execution schema freezes three ordered views:

1. actual Provider Prompts and raw Provider telemetry;
2. Host telemetry after the permitted prompt-component augmentation;
3. every Host call attempt, partitioned into a certificate-bearing prefix and a post-terminal
   short-circuit suffix.

The v26.85 Recovery preflight replayed 248 source and failed-run files and froze exactly this
partition before client construction:

```text
zero-generation replay Jobs       = 20
unopened continuation Jobs         = 12
Provider calls allowed for replay  = 0
execution allowed per unopened Job = exactly once
```

Its authoritative identities are:

- failed-run audit:
  `finance_v26_budget_failed_run_audit:9e6874b57eff45e53f0474a44d31790489d232a1c46f2937fce4f223f7796c5c`;
- Recovery Contract:
  `finance_v26_budget_recovery_contract:5b3f9efe759d22b1159a3a854a3bb3f6628d80645c833e9c7c43d043ec15730f`;
- Recovery Manifest:
  `finance_v26_budget_recovery_manifest:19876887f71863af1152aa43ea9eda599a18baf3c468710b0c171b489164d3ee`;
- Recovery execution Binding:
  `finance_v26_budget_recovery_execution_binding:69de2b9a62ae0e478a79247ee2eb6d8c09706e43c87b37d59ddd59d8f6b8de8c`;
- preflight report:
  `finance_v26_budget_recovery_preflight:f3e1af83b0b380fd14602417fd3770df7e92a532a4196fb4651bc0ab1d6ad964`.

Formal and independent v26.85 builds reproduced all eight top-level files byte for byte with zero
model-client construction, zero API calls, and zero GPU jobs.

## v26.86 Recovery Execution

v26.86 first replayed all 20 exposed Jobs and verified all 152 original Provider files before
constructing the model client. It then executed each of the 12 unopened Jobs exactly once. The
continuation made 89 Provider calls, used 823,541 provider-reported tokens, and recorded USD
0.093130273600000008853 estimated cost telemetry.

The complete 32-Job denominator is:

| Item | Complete denominator |
| --- | ---: |
| Zero-generation replay Jobs | 20 |
| First-execution continuation Jobs | 12 |
| Terminal rows | 32 |
| Provider calls | 241 |
| Provider-reported tokens | 2,204,169 |
| Estimated cost telemetry | USD 0.268686852000000027363 |
| Maximum single-rollout tokens | 79,489 |
| Fallbacks | 0 |
| Runtime failures | 0 |
| Instrument failures | 0 |
| Report-completeness failures | 0 |

All 32 Jobs have exactly one retained terminal:

| Terminal | Jobs |
| --- | ---: |
| `budget_exhausted_no_call` | 24 |
| `model_invalid_trajectory` | 8 |
| Completed trajectory | 0 |

The corresponding core terminals are 24 `model_invalid_resource_terminal` and 8
`invalid_trajectory`. All 24 typed no-call rows ended during the rollout, made zero Provider calls
for the denied request, retained the Job in the denominator, and passed the frozen pre-call and
reserve checks. Every rollout remained below 120,000 tokens; the observed maximum was 79,489.
The aggregate cost remained below USD 2.00.

All 32 rows used exact `deepseek-v4-flash` with zero fallback. All 241 Provider call identities are
unique. The raw-lineage audit passed 32/32 Raw Executions, 152/152 original exact-byte Provider
files, 89 continuation Provider files, all prompt partitions, all budget bindings, and all
pre-Host versus post-Host telemetry comparisons.

Verifier v2 Replay passed 32/32, and 32/32 independent non-Replay Gate audits were present. Repair
neutrality, terminal-target binding, public progress, and Stop Readiness remained instrument-valid
for every row. There were no completed trajectories, so the shared completed-trajectory scorer and
schema-closed sidecar had an online denominator of zero. Their prospective implementation remains
qualified by the v26.82 Compiler Witnesses; this run supplies no completed-model trajectory that
could exercise or empirically support that path.

The descriptive model result is negative:

```text
independently valid trajectories = 0 / 32
full Program lineage             = 1 / 32
local mechanism success          = 5 / 32
state-mapping-eligible rows       = 0 / 32
```

These descriptive counts do not weaken or rescue any Instrument Gate. They also do not constitute
balanced Capability support or empirical State Reachability.

The authoritative v26.86 report is:

`finance_v26_budget_recovery_report:4afbad8525b598269630912e79048490dbe4e3235d8789aad0f10b922798c4ea`.

A completed-run replay resumed at 32/32 without loading credentials, constructed no model client,
executed zero Jobs, and reproduced the report byte for byte.

## v26.87 Independent Post-Run Audit

v26.87 is a separate credential-free implementation. It does not call the v26.86 aggregate
builders. It independently replays source bytes, scans raw Provider lineage, reconstructs budget
and terminal rows, replays Verifier v2, recomputes non-Replay Gate and mechanism vectors, and
reconstructs the aggregate report vector.

The source audit replayed 538 files. The independent audit reproduced:

- 32/32 Raw Execution identities and bytes;
- 152/152 original Provider files exactly and all 89 continuation files;
- 241/241 unique Provider call identities and telemetry bindings;
- 24 typed no-call and 8 model-invalid terminal classifications;
- 32/32 per-rollout resource passes and exact-model rows;
- 32/32 Verifier v2 Replay passes;
- 32/32 non-Replay Gate, mechanism, and terminal reconstructions;
- 32/32 Instrument admissions;
- the complete v26.86 aggregate vector with zero mismatched fields.

The formal and independent v26.87 builds reproduced all six output files byte for byte. Both made
zero API calls, constructed no model client, and used zero GPU jobs.

Authoritative v26.87 identities are:

- source replay:
  `finance_v26_budget_postrun_source_replay:4834d467963c327d0ccd8aeca247700fcffdb74a339c58ca887371cc3df2f367`;
- Provider lineage:
  `finance_v26_budget_postrun_provider_lineage:038b37a470d9bee151d070d7edeba1e0beac14cb09acb685646eccfcde7f21ca`;
- budget and terminal audit:
  `finance_v26_budget_postrun_terminal_audit:3cf98cd39f884bed0a3b70dbe0b1d04594a711c00b1659864d0c730c15ed1317`;
- Verifier and scoring audit:
  `finance_v26_budget_postrun_verifier_audit:acadd85292b7f56a155cea93926e4c5ee57735d4b45ca74ebca231de0cd32d84`;
- aggregate reconstruction:
  `finance_v26_budget_postrun_aggregate_reconstruction:848825593e7fd0a3ca76468022f92bc0367ddc2c0ed818aba5a0cbff69c4d9e4`;
- report:
  `finance_v26_budget_closed_postrun_audit:a7318da72819ce66bdc93ab5117faec5f9f59b32aebd33f5324f2198bd705939`.

## Decision

The online Instrument result is retained as passed. This means the raw-first Provider capture,
pre-call budget closure, typed no-call semantics, exact-model binding, Verifier v2 Replay,
independent non-Replay scoring, failure namespaces, and complete report aggregation operated
without a Runtime or Instrument failure over the frozen 32-Job denominator.

It does not establish model Capability or State Reachability. Twenty-four Jobs exhausted their
certified prospective budget before another call, eight ended as model-invalid trajectories, and
no Job completed the full independently valid trajectory contract. The zero completed-trajectory
denominator also means this run is not empirical evidence for the completed-trace sidecar path.

The only permitted transition is:

```text
fresh_capability_and_reachability_protocol_design_only
```

This authorizes credential-free design and preflight work only. It does not authorize Capability
Development execution or State Reachability execution. A successor protocol must use fresh
identities and must account prospectively for the observed budget-closure distribution without
changing the frozen v26.86 outcome or treating typed no-call rows as valid trajectories.

Fresh Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and production Contribution
remain forbidden. Production Contribution remains zero, and the historical 0/36 State Support
Freeze remains authoritative.

## Artifacts

- `artifacts/vtdo_experiment/finance_v26_84_budget_closed_verifier_bound_instrument_requalification_20260820/`
- `artifacts/vtdo_experiment/finance_v26_85_budget_closed_recovery_preflight_20260820/`
- `artifacts/vtdo_experiment/finance_v26_86_budget_closed_verifier_bound_instrument_recovery_20260820/`
- `artifacts/vtdo_experiment/finance_v26_87_budget_closed_postrun_audit_20260820/`
