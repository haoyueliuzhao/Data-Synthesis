# Finance v26.161 Mapper v2 Reachability Frequency Execution

Date: 2026-08-27

## Decision Summary

Finance v26.161 consumed only the transition authorized by v26.160:

```text
fresh_mapper_v2_reachability_frequency_execution_only
```

It executed the exact frozen 360-Job Manifest with no source reselection and no change to the
TaskPackages, Paths, strong Task-condition Cells, bounded generation policy, Tool schemas,
Measurement Support, resources, Mapper v2, Assignment, estimand, Verifier, outcome, model,
Thinking, recovery, Detour, Grammar, or Runner contracts.

All 360 Jobs produced complete Results and Raw Executions in 3,134 exact Stage 1 Provider calls.
One conditioned State-dependent Stopping Hard Job selected a second successful Ordinary Detour
and ended with the typed terminal `ordinary_detour_allowance_exhausted`. The exact complete
Measurement Gate therefore failed:

```text
complete Raw Executions                         360 / 360
model endpoints                                 359 / 360
validity-evaluable rows                         359 / 360
Measurement Support exits                               1
formal Instrument failures                              1
Privacy failures                                        0
exact-model / Thinking / Usage failures                 0
typed budget no-calls                                    0
unresolved Transport failures                            0
Gate passed                                          false
```

The formal Instrument count and Support-exit count refer to the same Job. Its immutable Raw row
records `instrument_integrity=true`; the inherited online projection records
`instrument_integrity=false`. This overlap does not create a second causal failure and does not
change the failed Gate. It is frozen as a projection diagnostic for the required independent
postrun audit.

All exact frequency estimands remain null. Production Mapper v2, independent Reference Mapper,
formal Assignment, structural State, and empirical Route Signature counts are zero. All 48
strong-cell reports have `distribution=null` and `null_reason=measurement_gate_failed`.

## Review Reconciliation

The supplied v26.160 audit approved exact execution while identifying online denominator
completeness as the main risk. v26.161 followed that review as follows:

| Review condition | v26.161 evidence | Decision |
| --- | --- | --- |
| Execute only the frozen 360 Jobs | Exact v26.160 Manifest ID and 360 distinct Job IDs | Passed |
| Preserve 144 Unconditional and 216 conditioned rows | Preexecution binding records 144 and 216 | Passed |
| Preserve 48 strong Cells and separate conditioned Paths | 12 tasks, 48 Cells, 36 Paths | Passed |
| Do not use empirical Route as a condition | Frozen statistics key and zero Route-conditioned regrouping | Passed |
| Require 360 complete Raw rows | 360 Results, 360 Raw, 360 checkpoint rows | Passed |
| Require zero Support exit | One second-Detour Support exit | Failed |
| Fail all frequency estimands noncompensatorily | 48/48 reports null | Passed |
| Do not delete or replace the failed row | Exact denominator remains 360 | Passed |
| Do not map Qualified subsets after a failed Gate | 139 descriptive Qualified rows, zero Assignments | Passed |
| Keep no-Qualified distinct from zero probability | Eight descriptive zero-Qualified Cells, no imputation | Passed |
| Require an independent postrun audit | Fresh audit-only transition frozen | Pending successor |

The review also distinguished a bounded measurement-support condition from an unrestricted
natural-agent policy. v26.161 retains the frozen contract name but claims only behavior under the
bounded measurement condition. It makes no unrestricted natural-agent distribution claim.

Two review clarifications remain deliberately outside this execution change. First, the frozen
v26.160 source-selection artifact records a 36-task prior-selection registry and 58 eligible
candidates but does not add separate fields for registry size, overlap with the 70-task Frame,
and actual removals from that Frame. The supplied audit reconstructs the effective overlap as
12. v26.161 verifies and preserves the frozen bytes rather than revising a predecessor artifact
or reselecting a source.

Second, the frozen Estimand Contract names the Unconditional and Path-conditioned estimands,
separates all denominators, makes tasks primary and rollouts secondary, forbids Route
conditioning and State imputation, and requires all distributions to be null after a failed
Gate. It does not itself encode a confidence-interval method, minimum Qualified sample size, or
non-degeneracy threshold. v26.161 therefore reports `N_total` and `N_qualified` only as
cell diagnostics and explicitly claims no confidence interval or probability. The failed Gate
means no frequency formula is evaluated.

## Frozen Authorization

The exact v26.160 parents are:

- preflight report:
  `finance_v26_frequency_preflight_report:014007ba585d6315ee68dc001a13381b7c742e1468ba4b66a58ef3b938fb5b69`;
- reproducibility root:
  `finance_v26_frequency_reproducibility_root:b5987b716c0019a0a8cc706ecb39d232fdfb1ce400b3c07cdc34d39a35c4a069`;
- source Population:
  `finance_v26_frequency_source_population:fe954fe355847ef429aa50603fea12f4bba53af59e4d875e8051e76c94dcc301`;
- strong Cell Catalog:
  `mapper_v2_task_condition_cell_catalog:4a734a3ace027c43a711d00b646a4155e7ba6b04d6f6ab5a18cb8b9931875740`;
- bounded generation policy:
  `bounded_reachability_generation_policy:ba06af1fbfc013688ecb6c253401fe5c0d12be1d211bf727a3dd64db5cd15aaa`;
- Mapper-v2 protocol:
  `finance_v26_mapper_v2_frequency_protocol:fbfb314cfea3e693a34be778b62f7c3a510f4393a1638ae91c18794c328e5007`;
- Assignment Contract:
  `finance_v26_frequency_assignment_contract:5156e9e92addda1482f53e4f8fdedcb3c9857f6dd1796354b70a0e4b40d8ceb7`;
- estimand Contract:
  `finance_v26_frequency_estimand_contract:d434124bba9775355f2f16f61c2b432fdae051d751a21437809e7065ffc559c5`;
- execution Contract:
  `finance_v26_frequency_execution_contract:69e958c2118dc91891796a82a90e1c03b90a75c1d186609a3acb3d5dbfcd3149`;
- Manifest:
  `finance_v26_frequency_manifest:9cdd5be51f2e9dfd815d43f691987790b60ce5f435227409058bdbe00a69c3e4`;
- outcome Contract:
  `finance_v26_frequency_outcome_contract:d02dfa25cdc1002f5c6a05e62be771cffa090082fb1d96a53b981122f1d4d1bd`;
- Runner Contract:
  `finance_v26_frequency_runner_contract:41f2eb1a60a78631df97e2ff2836712571e72a9bb42c9da76eec42fd54ecd64c`;
- authorizing transition:
  `finance_v26_frequency_transition:b71a815575a0ddd247098e300037709451fe3aa2a72abe492b2230e5855c81b2`.

The frozen prospective execution identity is
`finance_v26_mapper_v2_frequency_execution:e87a7ae3fe9d9d0ade030fbb270b3ca7219fff27a94e8ffc814099ec93e95d22`.

## Preliminary Zero-Call Attempts

The preliminary v1 directory is retained at:

```text
artifacts/vtdo_experiment/
finance_v26_161_mapper_v2_reachability_frequency_execution_v1_20260827
```

It contains only frozen inputs and credential-free preexecution/source-audit files. It contains
no checkpoint, Raw Execution, Provider artifact, online Result, aggregate report, formal
Assignment, or frequency row. It was not admitted because its source audit self-bound only one
implementation file and an isolated worktree lacked one ignored current-stage dependency that
was available in the canonical artifact root.

The first authoritative-v2 preparation then failed local model validation because a prefixed
implementation-bundle identity was placed in a field requiring a raw 64-character SHA-256. That
failure occurred after local rebuilding but before credential lookup, client construction,
Provider invocation, Raw creation, or empirical-row creation. The final source uses the raw
bundle digest and rematerializes the authoritative preparation.

Neither preliminary failure contributes a Job, model call, endpoint, or scientific result.

## Authoritative Credential-Free Preparation

The authoritative output directory is:

```text
artifacts/vtdo_experiment/
finance_v26_161_mapper_v2_reachability_frequency_execution_authoritative_v2_20260827
```

Before credential lookup or client construction, the Runner:

- matched 35/35 inputs required by the current stage;
- matched all 33 frozen v26.160 direct outputs byte for byte;
- independently rebuilt and matched the same 33 outputs;
- bound both v26.161 implementation files;
- preserved the unavailable v25.44 historical snapshot limitation;
- retained `v26_158_full_transitive_rebuild_claimed=false`;
- observed an unopened denominator with zero Raw rows, Provider artifacts, checkpoint rows,
  reports, and formal Assignments;
- confirmed 360 Jobs, 12 tasks, 48 strong Cells, 36 conditioned Paths, 144 Unconditional Jobs,
  and 216 conditioned Jobs.

The implementation bundle SHA-256 is
`25952d22d718cf44f40ee9cd82e0930221a01490204360defa55432cd68920e3`.

The authoritative preparation identities are:

- source replay:
  `finance_v26_mapper_v2_frequency_execution_source_replay:396cc608e103fd2e552e3c1273c1b6445c9fa4fd54d46d7aed10489b62e1cccc`;
- preexecution binding:
  `finance_v26_mapper_v2_frequency_preexecution_binding:7ccbe158aef4213380f7df3ad8e76b9590912440a329f1a441f6a056fac85f65`.

## Online Denominator

The exact online execution completed all 360 Jobs with eight workers. No Job was deleted,
substituted, reopened under a changed Contract, or pooled with a historical denominator.

The terminal partition is:

```text
completed_model_endpoint                       197
model_result_failure                           162
measurement_support_exit                         1
total                                           360
```

Every Provider call used the exact frozen model and retained complete positive Thinking and
Usage telemetry. Across all rows:

```text
Stage 1 Provider calls                         3,134
transport-inclusive invocations                3,134
complete Envelope / public Projection pairs    3,134
Stage 2 Provider calls                             0
exact-model failures                               0
Thinking continuity failures                       0
Usage completeness failures                        0
Privacy failures                                   0
Provider-native Tool rows                          0
fallback rows                                      0
typed budget no-calls                              0
unresolved Transport failures                      0
```

Artifact-backed Usage and cost telemetry are:

```text
Prompt tokens                              16,455,506
Completion tokens                          14,314,802
Reasoning tokens                           13,830,042
total tokens                               30,770,308
estimated cost USD           5.45044867360000047422
```

Reasoning tokens remain part of Completion Usage. No private reasoning payload or hash, invalid
public payload, Raw HTTP body, or Raw request body is persisted.

## Sole Measurement Support Exit

The sole exit is Job:

```text
finance_v26_frequency_job:
53e29a176c06a64c701928ec7d2e958de595de83261e9abe95a45d63def57857
```

Its frozen design fields are:

```text
mechanism                 state_dependent_stopping
tier                      hard_control
sampling mode             reachability_conditioned
requested Path            search_then_open
terminal                  measurement_support_exit
terminal failure type     ordinary_detour_allowance_exhausted
```

The Raw row records two observed Ordinary Detours. The second one crosses the frozen
`T_dyn^(1)` measurement-support boundary and emits the typed terminal before any later Provider
invocation. It records three Stage 1 calls, three transport-inclusive invocations, 40,041 tokens,
zero Stage 2 calls, zero later calls after the Support exit, zero task-Verifier calls, and zero
State Mapping rows. Privacy is compliant and Raw-native Instrument integrity is true.

This is direct confirmation of the online risk identified in the supplied audit. The static
preflight established support for the registered Paths and the qualified one-Detour class, not
for every legal model-selected trajectory.

## Support And Instrument Projection Boundary

The inherited online measurement projector records the same Support-exit row with:

```text
measurement_support_available = false
model_endpoint_observed        = false
validity_evaluable             = false
instrument_integrity           = false
rollout_budget_passed          = false
```

The immutable Raw row instead records:

```text
measurement_support_available = false
model_endpoint_observed        = false
instrument_integrity           = true
ordinary_detour_count          = 2
later_provider_calls           = 0
calls / invocations / tokens   within the frozen bounds
```

Consequently, the formal v26.161 Gate counts one Support exit and one Instrument failure, but
both are projections of the same Job. The strongest supported interpretation is one
Measurement Support boundary exit with Raw-native Instrument integrity, plus one inherited
projection overlap. It is not evidence for two failures and not evidence for a budget overrun.

The execution artifacts and online labels remain immutable. The required postrun audit must
independently reproject all Raw rows and report Support, Instrument, endpoint, and resource
components separately without using the online projector as an outcome oracle. This prospective
audit may diagnose the overlap but may not repair the failed Gate, delete the Job, create a model
endpoint, or authorize frequency.

## Validity And Cell Diagnostics

The 359 evaluable model endpoints contain the following descriptive counts:

```text
Base-valid                                    139
Mechanism-qualified                           270
Qualified-valid                               139
```

By sampling stratum:

| Stratum | Rows | Evaluable | Base-valid | Mechanism-qualified | Qualified-valid |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unconditional | 144 | 144 | 64 | 115 | 64 |
| Path-conditioned | 216 | 215 | 75 | 155 | 75 |

By mechanism, the descriptive Qualified-valid counts are Context-conditioned Action 28/90,
Failure Recovery 49/90, Semantic Reconciliation 24/90, and State-dependent Stopping 38/90. The
last mechanism contains the one validity-unevaluable Support exit.

Across the 48 strong Cells, descriptive `N_total` sums to 360 and descriptive `N_qualified`
sums to 139. Eight Cells have zero Qualified rows, split into one Unconditional and seven
conditioned Cells; the observed per-Cell Qualified count ranges from zero to ten.

These counts are diagnostics only. Because the complete Gate failed, they do not enter a formal
Assignment or frequency denominator. The top-level `no_qualified_cell_count` is zero because
that report field counts only `no_qualified_rows` outcomes after a passing complete Gate. It must
not be read as saying that all Cells contain Qualified rows; the Cell diagnostics show eight
zero-Qualified Cells directly.

## Mapper And Frequency Outcome

The failed complete Gate blocks the complete Mapper and frequency branch:

```text
descriptive Qualified rows                       139
Production Mapper v2 invocations                   0
independent Reference Mapper invocations            0
Production / Reference exact matches                0
formal Mapper-v2 Assignments                         0
structural States                                    0
empirical Route Signatures                           0
strong-cell frequency reports                       48
null strong-cell reports                            48
imputed State vectors                                0
```

All reports use `null_reason=measurement_gate_failed`. None uses
`no_qualified_rows`, because that branch is reachable only after the complete Gate passes. The
139 Qualified-valid rows cannot be promoted into a selected clean subset, and no approximate
359-row frequency is reported.

v26.161 therefore establishes no state frequency, State probability, mechanism-level
distribution, Tier distribution, cross-task probability, confidence interval, non-degeneracy,
causal Path effect, unrestricted natural-agent distribution, or VTDO update.

## Raw Lineage And Privacy

The Raw lineage audit binds:

```text
Raw descriptors                                  360
Provider artifact descriptors                  9,402
exact byte replay passes                       9,762
complete Provider artifact triples             3,134
private reasoning payloads                         0
invalid public payload persistence                 0
Raw HTTP body persistence                          0
Raw request body persistence                       0
Stage 2 Provider calls                             0
```

Each Provider call contributes one privacy-redacted Envelope, one public Projection, and one
transport invocation certificate. The complete checkpoint contains exactly 360 unique Job rows.

## Authoritative Outputs

The authoritative report is:

```text
finance_v26_mapper_v2_frequency_execution_report:
152679635b6d16da3ae3723bcbf827c322a859cbcd782025022de8dfc0eafd06
```

Its SHA-256 is
`53f24149e5f981c67ad438060cf1826b2efaf74430633f5973b20b527c24165e`.

The principal outcome identities are:

- Measurement Gate:
  `mapper_v2_frequency_measurement_gate:93a07ac068af312b20254589aabd509f661cd34a2d50c3e43111a0f91c335551`;
- Raw Lineage:
  `finance_v26_mapper_v2_frequency_raw_lineage:48e34e4dbaa0818376bee5723ad7760938f7e1e54de65024c0c5bbe7e86a368d`;
- Mapper execution audit:
  `finance_v26_mapper_v2_frequency_mapper_execution:6807c2f5ebda098061b83797d03acba35ac36281c5e25d07c37ce81ca67914dc`;
- Assignment Catalog:
  `finance_v26_mapper_v2_frequency_assignment_catalog:28e3a485de152edaeefaafb29115e38133265bac67170aaca1917618916c4dd2`;
- frequency summary:
  `mapper_v2_reachability_frequency_summary:0cdca6e5a5e1f8de518d59f8910a55a5b5dc989e10affff30a4f55a35890c1b4`;
- Cell denominator diagnostics:
  `finance_v26_mapper_v2_frequency_cell_denominator_catalog:518f0c36ab68600cd371df285f3401ace8d012c71fb5276f8056f9ea385fd5bb`;
- postrun transition:
  `finance_v26_mapper_v2_frequency_execution_transition:5184ef787f6579dccfc92f20bc19ddb4f9a63042bb897b27ccf566f65b1aeb93`.

## Verification

The focused v26.161 artifact, Gate, Mapper, null-frequency, and Support-boundary tests pass 4/4
in 4.18 seconds. The selected v26.159-v26.161 adjacent regression passes 9/9 in 24.52 seconds,
with only the already completed v26.160 full-rebuild test deselected. A separate completed-run
replay explicitly removes `DEEPSEEK_API_KEY`, independently rebuilds all 33 v26.160 outputs, and
returns the exact existing report at 360/360 without a client or new Provider call.

PyCompile, focused Ruff check and format, focused Mypy, and package-wide Ruff pass. Package-wide
Mypy checks 504 source files and retains only four pre-existing diagnostics in v26.70, v26.129,
and the byte-frozen v26.154 online source; the v26.161 implementation and tests contribute zero.

## Current Transition

The only permitted transition is:

```text
fresh_mapper_v2_reachability_frequency_postrun_audit_only
```

The successor must independently parse all 360 Raw rows and all 3,134 privacy-first Provider
artifact triples, reconstruct every public trajectory and joint validity result, separate
Raw-native Instrument integrity from Measurement Support and resource classifications, and
reproduce the failed complete Gate and all-null frequency decision without using the v26.161
projector, Gate, Mapper, or summary helpers as outcome oracles.

It may not make a Provider or Stage 2 Provider call, delete or replace a Job, infer the missing
model endpoint, repair the denominator, change any frozen Contract or threshold, materialize an
Assignment or State from the failed denominator, report a frequency or State probability, update
VTDO, train, release, or make a production Contribution claim.
