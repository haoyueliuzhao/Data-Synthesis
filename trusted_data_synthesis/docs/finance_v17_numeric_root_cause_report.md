# Finance v17 Numeric Root-Cause Validation

Experiment date: 2026-08-05

## Decision

Finance v17 completed the preregistered numerical root-cause study requested after the v16
independent-validation failure. The result is positive at the numeric-contract layer:

- all eight development profiles completed on the same 20-realization diagnostic subset;
- only `fp32_activation_strict` passed every frozen raw-numeric and ordering gate;
- selection was frozen before any validation result existed;
- the selected profile passed all gates on a disjoint 20-realization validation subset;
- the v17 numeric contract was emitted for exactly one inherited sealed-candidate run.

The actionable root cause under the frozen implementation is BF16 forward-activation precision,
not sparse-projection precision, loss accumulation, TF32, activation checkpointing, separate
forwards, or functional VJP extraction. This is an engineering conclusion for the tested
Qwen2.5-7B/LoRA execution contract, not a universal claim about Gradient Projection.

The result does not authorize Contribution, GP-C, a VTDO update, Student training, or a downstream
effect claim. `production_authorized` remains false, and the sealed candidate remains unopened.

## Evidence Boundary

The authoritative experiment directory is:

`artifacts/vtdo_experiment/finance_v17_numeric_root_cause_dev20_val20_temp02_v13_20260805/`

Earlier v17 directories are engineering diagnostics. In particular, the v12 plan became stale
after the saved-tensor implementation was hardened and correctly failed the implementation
manifest check. No v12 result or checkpoint was mixed into v13. One duplicate control launch was
stopped by the concurrent-checkpoint guard and retained only under `failed_attempts/`; it did not
enter selection or aggregation.

Authoritative identities:

| Artifact | Identity |
| --- | --- |
| Population | `finance_gradient_calibration_population:9a019738f37bbcbdd35df8171709def13ef31d712d7c5336f88562233aa5b4c8` |
| Root-cause plan | `finance_gradient_numeric_root_cause_plan:8bc01deae493ebcc2d55ed7084fe954f87119d4a536b54c8bef3880417634662` |
| Implementation manifest | `finance_gradient_numeric_root_cause_implementation:c6e971cba1232dc688f0f4893bf019150d028a0739ba7af7d3247076cf12c707` |
| Frozen selection | `finance_gradient_numeric_root_cause_selection:5518e72d2b46e9ab134ad216422ad3dc9d5eebb130292d782db2840bb11a126a` |
| Aggregate report | `finance_gradient_numeric_root_cause_report:8f9db5c9249904f9846cb7482ad428f0181407a3580d7a00437fa885be57306c` |
| Numeric contract | `finance_gradient_numeric_contract:e2a1c890af575f477389b0bfb1475810aeecec3e5f4bf3a6213c552a82fa86b7` |

## Population And Leakage Control

Development, validation, and sealed candidate each contain six tasks, one from every active task
family:

- `comparison`
- `derived_growth_comparison`
- `registered_ratio`
- `temporal_absolute_change`
- `temporal_average`
- `temporal_growth`

Each partition binds 63 Evidence versions and six semantic signatures. Across partitions, task,
Evidence-version, and semantic overlap are all zero. The partition identities are:

| Partition | Task-set identity |
| --- | --- |
| Development | `finance_gradient_calibration_task_set:e59c23d6c00c17829b7ea16043ffe760789dc23902ef41d62dfb421945ce5f25` |
| Validation | `finance_gradient_calibration_task_set:21d4d86bd3efc37fddc7246f91132954d483f8b96a51a85ac2d1e6813e4c3986` |
| Sealed candidate | `finance_gradient_calibration_task_set:884e85bc9a8f531c8fe36aab2920dc0ff1432428b1c0efca61122b92767cf034` |

The population report records `sealed_candidate_outcomes_observed=false`. The root-cause plan also
declares `sealed_candidate_is_not_a_root_cause_input`.

## Real-Agent Input Funnel

Both open partitions used real DeepSeek-V4-Pro trajectories. Initial-distribution generation
produced 24/24 valid trajectories for each split. State-conditioned materialization produced 20
states and 60/60 released realizations per split.

| Stage | API calls | Total tokens | Released output | Provider estimate |
| --- | ---: | ---: | ---: | ---: |
| Development initial distribution | 72 | 400,487 | 24/24 trajectories | 0.118171926 |
| Validation initial distribution | 72 | 395,803 | 24/24 trajectories | 0.081359616 |
| Development state realizations | 212 | 1,713,873 | 60/60 realizations | 0.142469315 |
| Validation state realizations | 198 | 1,582,292 | 60/60 realizations | 0.142360391 |
| Total | 554 | 4,092,455 | 168 released records | 0.484361248 |

All 554 calls succeeded and satisfied the JSON contract; fallback calls were zero. The provider
estimate is telemetry, not an invoice, and no currency interpretation is asserted. The numerical
experiment reused these frozen inputs and made no additional API calls.

The root-cause matrix intentionally uses one lowest-index realization per task-state: 20 of the 60
realizations in each open split. This is a preregistered diagnostic subset, not a claim that all 60
realizations have passed the new execution profile.

## Numeric Implementation

`finance_gradient_numeric_root_cause.v3` freezes the following execution behavior:

1. causal token losses are partitioned into common and differential regions;
2. full, common, and differential gradients are independently extracted and recomposed;
3. saved tensors use stride-preserving pinned-CPU round trips with synchronous restoration;
4. GQA repeats KV tensors explicitly before fused efficient SDPA;
5. model inputs follow the input-embedding device;
6. every realization writes a content-bound atomic checkpoint;
7. unknown, stale, foreign, duplicate, or partially completed artifacts fail closed.

The multi-GPU loader reserves the first selected device for long-sequence activations and excludes
all unselected devices. The resolved Hugging Face device map, trainable-parameter manifest,
implementation dependencies, source plans, and objective records are all hashed into results.

## Development Root-Cause Matrix

The frozen thresholds were inherited unchanged from the v16 failure analysis. No observed v16 or
v17 validation value was used to relax them.

| Profile | Max relative error | Min cosine | Max GP delta | Max TV | Envelope | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| BF16 checkpoint TF32 control | 0.034362 | 0.999526 | 0.002129 | 0.000126 | 0.0043 | failed |
| Projection FP32 only | 0.034144 | 0.999521 | 0.002824 | 0.000251 | 0.0057 | failed |
| Accumulation FP64 only | 0.035031 | 0.999504 | 0.001951 | 0.000140 | 0.0040 | failed |
| TF32 off only | 0.031287 | 0.999605 | 0.002769 | 0.000246 | 0.0056 | failed |
| Checkpoint on, separate forward | 0.035370 | 0.999493 | 0.001930 | 0.000153 | 0.0039 | failed |
| Checkpoint off, separate forward | 0.036154 | 0.999476 | 0.002067 | 0.000209 | 0.0042 | failed |
| Checkpoint off, functional call | 0.034892 | 0.999513 | 0.002291 | 0.000126 | 0.0046 | failed |
| FP32 activation strict | 0.006416 | 0.999979 | 0.000525 | 0.000041 | 0.0011 | passed |

Only `fp32_activation_strict` was eligible. It differs from `tf32_off_only` in model activation
dtype while retaining the same checkpointed shared-VJP structure and BF16 projection execution.
The paired 20-job, task-cluster bootstrap contrast was:

| Improvement metric | Mean | Positive jobs | Task-cluster bootstrap 95% |
| --- | ---: | ---: | ---: |
| Relative-error reduction | 0.014519 | 20/20 | [0.011827, 0.018466] |
| Cosine improvement | 0.000178 | 20/20 | [0.000134, 0.000244] |
| GP-delta reduction | 0.000859 | 16/20 | [0.000406, 0.001366] |

No other intervention crossed the joint numeric gate. Checkpointing and functional-call contrasts
were centered near zero; projection FP32, FP64 accumulation, and TF32 changes alone did not resolve
the tail.

The BF16 control's worst record was a `derived_growth_comparison` state with 5,126 supervised
tokens, of which only 474 (9.25%) were differential. Its relative recomposition error was 0.034362.
For the same frozen job, FP32 activation reduced the error to 0.003634 and raised cosine from
0.999526 to 0.999994. This supports the mechanism that low-mass differential regions amplify BF16
activation rounding in long, mostly common trajectories.

## Frozen Selection

The selector observed all eight development results, found exactly one eligible profile, and froze:

- profile: `fp32_activation_strict`;
- pairwise uncertainty envelope: `0.0011`;
- validation GPU contract: three GPUs with at least 64 GiB free each;
- validation policy: the selected profile only.

At selection time, no validation result existed. The frozen selection explicitly records
`validation_observed=false` and `sealed_candidate_outcomes_observed=false`.

## Independent Validation

The selected profile completed 20/20 fresh validation checkpoints without resume, retry, or failed
result. All frozen raw-numeric gates passed:

| Metric | Observed | Frozen threshold | Result |
| --- | ---: | ---: | --- |
| Maximum GP-score delta | 0.00068376 | <= 0.0023 | passed |
| Maximum relative error | 0.00602399 | <= 0.027 | passed |
| Minimum cosine | 0.99998186 | >= 0.99967 | passed |
| Maximum loss-identity error | 5.95e-8 | <= 1e-6 | passed |
| Maximum update JS | 5.86e-9 | <= 1e-6 | passed |
| Maximum update TV | 0.00005472 | <= 0.00023 | passed |

Ordering also passed:

- 25/25 pairs were resolvable;
- resolvable-pair direction agreement was 100%;
- all six task winners agreed;
- all six strict task permutations agreed;
- ordering violations were zero.

The validation result is
`finance_gradient_numeric_root_cause_result:e4f07239cc74e41c87d9cfca021e1b3fef2be414cf448932ad4ce3c617b67888`.

Development FP32 runtime was 2,767.78 seconds and validation runtime was 2,712.96 seconds. The
maximum validation PyTorch allocated-memory peak was 33.36 GB on the largest shard device. The
eight-profile development runtime sum was 8,052.47 seconds; profiles were run with their frozen
one- or three-GPU resource contracts.

## Authorization State

Aggregation replayed the plan, all selected lineage, result summaries, and canonical hashes before
writing `frozen_numeric_contract.json`.

The exact authorization state is:

- aggregate status: `passed`;
- `numeric_contract_authorized=true`;
- `production_authorized=false`;
- allowed next role: `independent_sealed_candidate`;
- production effect: `none_until_sealed_candidate_passes`;
- sealed candidate: unopened;
- GP-C, Contribution intervention, VTDO update, and Student training: not authorized.

The next scientific step is one inherited sealed-candidate run under the frozen
`fp32_activation_strict` profile, thresholds, envelope, task set, and implementation manifest. Its
outcome may decide whether the numeric layer can authorize the later Contribution experiment. It
must not be replaced by another profile or used to tune this contract.

## Verification

After the experiment:

- focused numeric and Gradient Projection tests: 65 passed;
- Ruff: passed;
- Mypy: passed for 236 source files;
- full Pytest: 373 passed in 116.00 seconds;
- Core generalization, Legal contracts, and Science contracts remained covered by the full suite.
