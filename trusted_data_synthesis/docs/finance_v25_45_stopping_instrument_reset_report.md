# Finance v25.45 Stopping Instrument Reset

Date: 2026-08-16

## Decision

v25.45 completes the clean measurement-instrument reset required by the v25.44 audit.
The fresh run establishes Recursive Host-Agent Observation Noninterference and authorizes
Shape analysis, but obtains only partial Shape support:

```text
instrument_status                         = passed
shape_analysis_authorized                 = true
boundary_candidate_admitted_count         = 3 / 4
runtime_control_pass_count                = 2 / 2
all_shapes_admitted                       = false
next_permitted_stage                      = stopping_shape_redesign_only
historical_shape_support_transferred      = false
Pro / Beneficiary / Exact Target / GP-C   = blocked
production_contribution                   = 0
```

The result validates the repaired observation channel. It does not authorize stable Stopping
support, Contribution estimation, a VTDO update, or Student training.

## Audit Closure

The v25.44 audit found Host-only completion and scoring events nested in model-visible business
results. Deleting those fields after execution cannot recover the counterfactual trajectory, so
the affected records cannot be filtered and reaggregated.

A read-only recursive audit covered eight immutable artifacts from v25.34, v25.35, v25.36,
v25.37, v25.38, v25.43, and two v25.44 runs. All eight failed recursive isolation. They remain
diagnostic evidence only; no result, threshold, task selection, or Shape support transfers to
v25.45. Snapshot v3 remains valid because it is an upstream capacity artifact created before
model execution.

The reset implements four independent safeguards:

1. Every finance tool has a strict public result schema, including nested `extra=forbid`.
2. Host events are stored outside model-visible results in a replayable side channel.
3. Recursive scanners cover mappings, sequences, typed objects, and serialized prompts.
4. Both successful and fail-closed executions freeze actual prompts and public, Host, and
   internal result hashes.

Static mutation tests covered nested mappings, lists, Optional/Union objects, future Host aliases,
and serialized Prompt payloads. Every mutation was rejected before API access.

## Fresh Population And Execution

| Item | Value |
| --- | ---: |
| Fresh tasks | 48 |
| Rollouts per task | 8 |
| Rollout denominator | 384 |
| Explorer | `deepseek-v4-flash` |
| Parallel workers | 48 |
| API calls | 3,822 |
| Provider-reported tokens | 19,752,214 |
| Estimated provider cost | $1.8589529504 |
| Pro calls | 0 |

No API call was replayed during deterministic finalization.

## Raw Noninterference Audit

The raw audit ran before Shape aggregation:

| Check | Result |
| --- | ---: |
| Records present and auditable | 384 / 384 |
| Successful Agent outcomes | 178 |
| Fail-closed behavior outcomes | 206 |
| Tool observations | 3,284 |
| Strict public schemas | 3,284 / 3,284 |
| Public-result hashes | 3,284 / 3,284 |
| Host-side-channel hashes | 3,284 / 3,284 |
| Internal-result hashes | 3,284 / 3,284 |
| Prompt-attested records | 384 / 384 |
| Actual API request prompts | 3,822 |
| Recursive Prompt scans | 3,822 / 3,822 |
| Prompt hash matches | 3,822 / 3,822 |
| Last-Prompt hashes | 384 / 384 |
| Recursive Host-field violations | 0 |
| Recursive Host-marker violations | 0 |
| Unknown side-channel events | 0 |
| Contaminated tasks | 0 |
| Unattested tasks | 0 |
| Public-contract violation tasks | 0 |

The 206 fail-closed behavior outcomes are capability observations, not measurement failures. They
remain in the denominator. Removing them would condition measurement on model success.

## Shape Results

Admission uses only the preregistered Stopping response. Full-valid and semantic responses cannot
rescue a failed Shape.

| Shape | Role | Stop rate | Full-valid | Task range | Effective tasks | Valid trajectories | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `authority_coverage_gap` | boundary | 0.6875 | 0.421875 | 0.625 | 7.7645 | 27 | pass |
| `contextual_resolution_choice` | boundary | 0.34375 | 0.140625 | 0.875 | 6.4478 | 9 | fail |
| `partial_required_evidence` | boundary | 0.8125 | 0.390625 | 0.125 | 7.4819 | 25 | pass |
| `single_dimension_conflict` | boundary | 0.65625 | 0.546875 | 0.500 | 6.7024 | 35 | pass |
| `verified_extra_call_cost` | control | 1.0000 | 0.484375 | 0.000 | 0.0000 | 31 | pass |
| `verified_extra_call_error_risk` | control | 1.0000 | 0.625000 | 0.000 | 0.0000 | 40 | pass |

`contextual_resolution_choice` failed only `between_task_heterogeneity`. Its task-level stopping
probabilities span 0.875 and one of eight tasks has zero Stopping information. This is a
Shape-support defect, not an observation-channel or API transport failure. No pooled rescue,
historical support transfer, post-hoc task deletion, or cross-estimand rescue was used.

## Deterministic Finalization

All API and deterministic intermediate artifacts completed, but the original wrapper referenced
the obsolete Shape field `all_shapes_admitted`; the current Shape schema exposes
`all_shapes_contract_passing`. Execution stopped after writing the Shape report.

The recovery finalizer does not relax the production Contract validator and does not permit a
frozen contract to execute again. It uses a strict read-only snapshot schema, verifies source
references and the original implementation-manifest identity, reloads all records and outcomes,
recomputes every raw and Shape artifact, and requires canonical equality before writing only the
missing overall report and Manifest.

The finalizer ran twice with the same identity; the second invocation verified immutability:

```text
report_id       = finance_stopping_instrument_reset_report:9ad1eba43807940b419c9989dabb01db82ebcb24c94937809976e260bfd595c8
finalization_id = finance_stopping_instrument_reset_finalization:821384e7d9a54058def650a1d2fc51710287f09f771e8aa3be55144e2dde04fc
api_execution_replayed = false
deterministic_recomputation_passed = true
```

Formal artifacts are under:

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/vtdo_experiment/
finance_v25_45_stopping_instrument_reset_development_v3_audit_complete_20260816/
```

## Next Experiment

Only a prospective redesign of `contextual_resolution_choice` is permitted. It must be frozen
before outcomes, use fresh task/Evidence/version/signature/materializer identities, preserve the
public schemas and noninterference gates, and address task-level heterogeneity structurally. The
other five Shapes may serve only as preregistered regression controls on fresh tasks.

Only after all four boundary candidates and both controls pass within one clean population may
the project prepare three-population stability. Pro, Beneficiary, Exact Target, GP-C, VTDO
updates, Student training, and production Contribution remain forbidden until that later contract
passes.
