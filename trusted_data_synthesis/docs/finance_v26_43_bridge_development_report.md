# Finance v26.43 Bridge Development Experiment

Date: 2026-08-17

## Executive decision

Finance v26.43 completed the first full compiler-assisted capability Bridge Development run over
real public Finance tasks under the v26 Joint Compilation mainline. The run executed the exact
preregistered denominator:

```text
3 mechanisms x 4 scaffold levels x 8 tasks x 6 rollouts = 576 observations
```

The execution and audit instrument passed, but the capability-support decision failed closed:

```text
Raw capture and lineage integrity      passed, 576/576
Provider HTTP execution                passed, 5,166/5,166
Model-valid trajectories               23/576 (3.9931%)
Mechanisms admitted                    0/3
Selected scaffold levels               none
Fresh confirmation                     forbidden
State-support discovery                forbidden
No-C VTDO / Student training           forbidden
Contribution                           0 and unauthorized
Authoritative next transition          capability_task_or_scaffold_redesign_only
```

This is a valid negative Bridge Development result. It is not an API outage, Runtime failure,
State-support result, Contribution result, or negative test of VTDO itself. The Development
support gate says that the current public tasks and scaffold ladder do not place all three
mechanisms inside a jointly valid and measurable capability boundary.

## Experimental boundary

The audit requested the following order:

```text
fresh source admission
-> 24-task Joint Compilation
-> atomic Joint Audit and Admission
-> four-level Scaffold Compilation
-> atomic Scaffold Audit and Admission
-> Bridge static authorization
-> raw-first Flash Development rollouts
-> task-first Bridge aggregation
-> support freeze
```

That order was preserved. Model-client construction occurred only after the no-API Stage Ledger
replayed to `bridge_rollout`. Aggregation occurred only after all raw rollout artifacts existed and
passed the raw-integrity audit. The failed support freeze prevented all downstream stages.

No local GPU was used. GPU authorization was neither needed nor exercised.

## Frozen artifact chain

### Exposure-clean source

```text
artifacts/vtdo_experiment/finance_v26_29_exposure_grounded_source_20260817/
```

Key identity:

```text
receipt_id = finance_v26_exposure_clean_population_receipt:
             c7986e19da5c9b63bf25c0af8bc6c9783c6942abe5f33db49919cc2f0478d6d7
```

### Final mainline protocol

```text
artifacts/vtdo_experiment/finance_v26_42_mainline_protocol_20260817/
```

```text
protocol_id = finance_v26_capability_heterogeneous_vtdo_mainline:
              f7a0099295d79cebd149832fd6ae6c882c91fb4419fbade1818c8c8761084f75
```

### No-API Joint/Scaffold closure

```text
artifacts/vtdo_experiment/finance_v26_42_no_api_joint_scaffold_20260817/
```

```text
report_id = finance_v26_no_api_joint_scaffold_report:
            f510a9ba6ac096a0b721981e7f0c4e2e49234fd318bb11c27b3c8a10a269b4a4
ledger_id = finance_v26_stage_ledger:
            e619c51f3d3be712f84d2c1ab0e6b8b944733a779a4f204b68c31fd32dfc1cf6
```

### Bridge Development

```text
artifacts/vtdo_experiment/finance_v26_43_bridge_development_20260817/
```

```text
execution_contract_id = finance_v26_bridge_execution_contract:
                        fa2c8265fa9908b3073e21bcadc423d64e0e26d0480b010f12d340004f4717c0
report_id = finance_v26_bridge_run_report:
            de8928aa41322f92ba4be7c0edab315f0c24ff0739e66c49cf79342859fb695d
raw_integrity_audit_id = finance_v26_bridge_raw_integrity_audit:
                         a22f3ade12679993ae1427ccb38b857034fccd1461062c42568275ee064c3bec
support_freeze_id = finance_compiler_assisted_bridge_support_freeze:
                    f6d396760cf344924a7f01649447e1bae19fe3e6a45adf60b886249afcd18306
```

The compact machine-readable result is `experiment_metrics.json`. It does not replace the raw
artifacts, typed rollout observations, cells, support freeze, or Stage Ledger.

## Source admission and contamination boundary

The source admission was performed before task resampling.

| Source-pool item | Count |
| --- | ---: |
| Source Evidence | 151,114 |
| Historical API-exposed Evidence | 1,657 |
| Source-grounding passed | 126,400 |
| Source-grounding failed | 24,714 |
| Effective union excluded | 26,290 |
| Eligible Evidence | 124,824 |
| Output capability tasks | 70 |

All 24,714 grounding failures were `source_entailment` failures under
`finance_source_grounding.v1` version `1.2.0`: 24,681 came from `fred_observations` and 33 from
`worldbank_indicators`. They were excluded rather than converted into weakly grounded tasks.
Historical exposure and grounding failure sets overlap, so their union is 26,290 rather than the
sum of both counts.

Development and reserved Fresh Confirmation Populations use disjoint identities in all eight
frozen channels:

| Freshness channel | Intersection |
| --- | ---: |
| Task ID | 0 |
| Source Task ID | 0 |
| Evidence ID | 0 |
| Evidence Version ID | 0 |
| Core Semantic Signature | 0 |
| Task Signature | 0 |
| Mechanism-instance Signature | 0 |
| Source Record ID | 0 |

The Fresh Confirmation Population remains reserved. It has not been sent to a model.

## No-API compilation and admission result

The final v26.42 prefix passed before any API client was created:

| Artifact or audit | Result |
| --- | ---: |
| Joint Compilations | 24/24 |
| Trajectory State Spaces | 24/24 |
| Joint audit Evidence records | 72 |
| Joint atomic cases | 384 |
| Joint Admissions | 24/24 |
| Scaffold ladders | 24/24 |
| Scaffold gate Evidence records | 672 |
| Scaffold atomic cases | 3,024 |
| Scaffold Admissions | 24/24 |
| Ordered-history collision cases | 96 |
| Cross-level state-mapping cases | 96 |
| Bridge static audits | 3/3 |
| Bridge static atomic cases | 144 |
| Model API calls | 0 |
| GPU jobs | 0 |

Credential-free replay removed credential-like environment keys, set `CUDA_VISIBLE_DEVICES` to an
empty value, returned code 0, reproduced the same Ledger ID, and reproduced the next stage
`bridge_rollout` with zero API calls and zero GPU jobs.

This closes the audit requirement for real per-task Joint/Scaffold execution. It does not by
itself establish Bridge efficacy.

## Frozen Bridge execution contract

The Development contract fixed:

| Contract item | Value |
| --- | --- |
| Model | `deepseek-v4-flash` |
| Fallback models | none |
| Requested-model enforcement | required |
| Tasks | 24 |
| Mechanisms | 3 |
| Scaffold levels | `gamma_0..gamma_3` |
| Replicates per task-level | 6 |
| Task-level cells | 96 |
| Rollout identities | 576 |
| Primary sampling unit | task |
| Secondary sampling unit | rollout |
| Per-task scaffold selection | forbidden |
| Maximum tool calls | 24 |
| Maximum failed tool calls | 5 |
| Maximum model tokens | 120,000 |
| Tool timeout | 30 seconds |

The four levels were paired within each task. Support inference used task-first, rollout-second
hierarchical resampling and paired `gamma_0` comparisons. The 48 rollouts within a mechanism-level
cell were not treated as 48 independent tasks.

## Provider and raw-artifact execution

| Provider measure | Result |
| --- | ---: |
| Provider calls | 5,166 |
| HTTP 200 | 5,166 |
| JSON-contract-successful calls | 5,120 |
| Fallback calls | 0 |
| Prompt tokens | 23,721,095 |
| Completion tokens | 667,136 |
| Total provider-reported tokens | 24,388,231 |
| Prompt cache-hit tokens | 11,446,400 |
| Prompt cache-miss tokens | 12,274,695 |
| Calls per rollout, p50 | 9 |
| Calls per rollout, p95 | 13 |
| Calls per rollout, maximum | 18 |
| Latency per call, p50 | 1,588 ms |
| Latency per call, p95 | 2,295.25 ms |

The telemetry contains a nominal estimated cost of `1.9373053` in the provider adapter's configured
currency convention. This is not billing truth and must not be used as an invoice or budget
reconciliation. The run did not freeze an independently verified provider bill, wall-clock duration,
or peak-memory measurement.

The raw-integrity audit passed every rollout:

| Raw check | Passed |
| --- | ---: |
| Byte SHA-256 | 576/576 |
| Rollout identity | 576/576 |
| Actual prompt hash | 576/576 |
| Scaffold payload hash | 576/576 |
| Host side-channel hash | 576/576 |
| Recursive noninterference | 576/576 |
| Provider call ID uniqueness | passed |
| Failed raw artifacts | 0 |

This supports the claim that the negative result is not caused by missing raw output, duplicate
provider identities, prompt substitution, scaffold drift, or a detected Host-side leakage path.

## Model trajectory result

| Terminal category | Count | Rate |
| --- | ---: | ---: |
| Model-valid trajectory | 23 | 3.9931% |
| Model-invalid trajectory | 553 | 96.0069% |
| Runtime failure | 0 | 0% |
| Instrument failure | 0 | 0% |
| Total | 576 | 100% |

Failure attribution is mutually exclusive at the rollout level:

| Failure category | Count |
| --- | ---: |
| Independent verification failed | 545 |
| Model contract exhausted after bounded repair | 8 |

At the provider-call level, 46 calls returned JSON that violated the typed decision contract:
26 invalid `decision_type` values, 13 over-length `plan_summary` values, and 7 excessive
`stop_conditions` lists. Bounded repair recovered most call-level defects; only 8 rollout-level
failures exhausted the contract path.

Independent verifier checks are multi-label, so the following counts do not sum to 545:

| Failed independent check | Count |
| --- | ---: |
| Answer correct | 521 |
| Operation lineage covers Gold | 321 |
| Verification support covers Gold | 297 |
| Citation exactly Gold | 183 |
| Selected Evidence covers Gold | 32 |
| Citations selected | 11 |
| Deterministic tool replay | 2 |
| Stop after successful verification | 1 |

The dominant failure is therefore semantic and evidential trajectory validity, not transport or
JSON availability.

## Mechanism and scaffold observations

### Valid trajectories by mechanism and level

| Mechanism | gamma_0 | gamma_1 | gamma_2 | gamma_3 | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Context-conditioned action | 0/48 | 0/48 | 0/48 | 0/48 | 0/192 |
| Semantic reconciliation | 5/48 | 8/48 | 4/48 | 4/48 | 21/192 |
| Recovery and stopping | 2/48 | 0/48 | 0/48 | 0/48 | 2/192 |

No monotonic validity improvement appears across scaffold levels. Semantic reconciliation has the
largest validity count at `gamma_1`, but its confidence interval lower bound remains zero and its
registered semantic-reconciliation estimand is zero at every level.

### Context-conditioned action

The `context_action_alignment` estimand was high at all levels: 46/48, 48/48, 48/48, and 47/48.
This does not admit the mechanism. The companion `counterfactual_branch_flip` estimand was 0/48 at
all four levels, and no rollout was independently valid. The inference therefore flags both
saturation of the easy alignment measure and absence of the required boundary-sensitive branch
change.

### Semantic reconciliation

The registered semantic-reconciliation estimand was 0/48 at every level. Valid-trajectory point
rates were 10.42%, 16.67%, 8.33%, and 8.33%, but every task-first confidence interval included zero.
No level improved the mechanism-specific estimand over `gamma_0`.

### Recovery and stopping

Failure-recovery successes were 2/48, 9/48, 9/48, and 8/48. Stopping-calibration successes were
0/48 at all levels. The paired gain over `gamma_0` did not have a positive lower confidence bound.
The few recovery successes therefore cannot authorize a combined recovery-and-stopping mechanism.

## Task-first support freeze

All mechanism selections are blocked:

| Mechanism | Passing levels | Selected level | Decision |
| --- | --- | --- | --- |
| Context-conditioned action | none | none | blocked |
| Semantic reconciliation | none | none | blocked |
| Recovery and stopping | none | none | blocked |

Common blocking conditions include a low valid-trajectory confidence lower bound, mechanism
estimand lower bounds below the frozen boundary, and non-positive paired gains over `gamma_0`.
Context-conditioned action additionally fails the saturation ceiling; recovery and stopping fails
both the recovery and stopping joint requirement.

The authoritative transition stored by the support freeze is:

```text
capability_task_or_scaffold_redesign_only
```

Consequently, the following stages are not permitted:

```text
Fresh Bridge Confirmation
State-support Contract or Discovery
State-support Freeze
No-C VTDO update
Student training
Exact Target or GP-C
Contribution authorization
```

## Immutable finalization recovery and permanent repair

All 576 raw and typed observations completed before final aggregation. The then-frozen runner had
three post-processing defects:

1. `bridge_rollouts.json` was emitted in job order while the Stage Router required artifact-ID
   order.
2. Support-freeze replay depended on insertion order inside `task_metric_values`; canonical JSON
   sorts mapping keys, so an in-memory object could pass while its disk round-trip failed.
3. The Stage Router compared a mechanism/level-ordered cell tuple with an observation-ID-ordered
   tuple even though both represented the same exact cell identity set.

A one-time finalization recovery canonicalized only the completed collections and reran the
original typed validators. It did not call the model and did not modify the checkpoint:

```text
checkpoint records                576
checkpoint SHA-256 before         f2cb8758e9422c70ee33251892b6ed0f81c276211893169eaa9bf900991f7434
checkpoint SHA-256 after          f2cb8758e9422c70ee33251892b6ed0f81c276211893169eaa9bf900991f7434
new trajectory generations        0
recovery_id = finance_v26_bridge_checkpoint_finalization_recovery:
              ad0c84dc301b54921e76ccafd28916b08ddd8fffd71f71ec7a48db42c2125f8b
```

The permanent implementation now:

- writes rollout and cell collections in canonical content-addressed order;
- validates metric key sets against the registered mechanism metric set, not mapping insertion
  order;
- compares exact sorted cell identity sets across stages;
- fails fast on worker exceptions, persists a runner-failure checkpoint, and cancels pending work;
- distinguishes an all-HTTP-success model contract exhaustion from a Provider/Runtime failure;
- makes the Support Freeze the single source for the final `next_transition`.

Relevant versions are Bridge Rollout observation v3, Bridge Level Inference v2, Bridge Support
Freeze v5, Bridge Runner v2, and Stage Router v6.

The immutable `report.json` predates the final single-source transition fix and contains the legacy
label `capability_scaffold_repair_only`. It is not mutated post hoc. The content-addressed Support
Freeze is authoritative and uses `capability_task_or_scaffold_redesign_only`; the permanent runner
now copies that value directly. Both labels block all downstream empirical stages, but only the
Support Freeze label should be used in future automation and scientific reporting.

## What the result establishes

The experiment establishes:

1. the 24-task Joint/Scaffold prefix is executable and credential-free replayable;
2. the 576-observation API denominator was completed without Runtime or instrument loss;
3. raw-first provenance, prompt/scaffold identity, and recursive noninterference checks passed;
4. task-first inference finds no admissible scaffold level for any of the three mechanisms;
5. the Stage Router correctly prevents confirmation, State support, VTDO, Student, and Contribution
   stages after this negative Development result.

It does not establish:

1. that compiler-assisted scaffolding is generally ineffective;
2. that DeepSeek Flash cannot express these capabilities under another task/scaffold design;
3. that valid State support is absent after a future redesigned Bridge;
4. that VTDO, GP-C, or Contribution is ineffective;
5. that increasing sample count under the unchanged design would repair the mechanism boundary.

## Diagnostic hypotheses, not experimental conclusions

The following are hypotheses suggested by the failure profile and require new preregistered tests:

- Context action alignment may be too easy and saturated while branch-flip tasks are not producing
  a valid decision boundary.
- Semantic reconciliation scaffolds may expose state without making the required definition,
  period, source, or scope conflict operationally resolvable by the current Agent contract.
- Recovery hints at a weak response to scaffold levels, but stopping remains structurally absent;
  the combined mechanism may need separate Development contracts before recombination.
- High answer and lineage failure counts may indicate that the scaffold helps local decisions but
  does not preserve end-to-end Gold Evidence closure.

These possibilities are not selected post hoc as explanations. The current evidence only supports
redesign, followed by a fresh Development Population and a new immutable run identity.

## Next permitted experiment

The next experiment must remain inside `capability_task_or_scaffold_redesign_only`:

1. revise mechanism-specific task and scaffold contracts using only Development diagnostics;
2. separate recovery and stopping during construct Development if their dependencies remain
   non-identical;
3. replace saturated context-alignment checks with paired branch-sensitive tasks whose correct
   action changes under public context while keeping Oracle and tool authority fixed;
4. make reconciliation conflicts operationally necessary and independently replayable;
5. rerun static Joint/Scaffold and summary-sufficiency audits under new version identities;
6. use a fresh API Population with all eight exposure/freshness channels replayed;
7. require a new Development support freeze before any confirmation or State-support work.

Threshold relaxation, post-hoc task deletion, reuse of the reserved Confirmation set as
Development data, and direct continuation to State support are forbidden.

## Repository verification

The implementation, tests, and report were verified together:

| Check | Result |
| --- | --- |
| Focused Bridge/Support-Freeze/Router regression | 34 passed in 88.59 seconds |
| Ruff over `src` and `tests` | passed |
| Mypy over `src` | passed, 343 source files |
| Full Pytest | 846 passed in 357.26 seconds |
| Explicit Core generalization contract | 5 passed in 9.95 seconds |
| Tracked API-key pattern scan | zero matching files |
| `git diff --check` | passed |

The full test denominator increased from the earlier no-API closure because this change adds the
raw-first Bridge runner, exposure-clean source admission, task-first support inference regressions,
Stage Router v6 checks, and the final transition single-source regression.
