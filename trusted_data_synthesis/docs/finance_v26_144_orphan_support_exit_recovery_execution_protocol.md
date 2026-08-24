# Finance v26.144 Orphan Support-Exit Recovery Execution Protocol

Date: 2026-08-25

## Decision

Finance v26.144 will execute only the exact three-Job zero-call Recovery Manifest authorized by
v26.143. Each fresh RecoveryJob replays one immutable v26.141 orphan prefix and writes one fresh
Recovery Raw plus one fresh result with terminal
`ordinary_replan_reference_unavailable`.

This execution has no credential lookup path, model-client path, Provider invocation path, Stage
2 Provider path, or Host reference fallback. It cannot modify the v26.141 failed execution or
assign a historical terminal. The three new rows are measurement-support boundary exits under
fresh identities, not reconstructed historical Raw rows.

## Exact Authorization

The execution binds:

- preflight report:
  `finance_v26_orphan_support_exit_preflight_report:ee6af1ef4e1462316a953fb247347792b1a04e017a371f9ba756801ce90de0ac`;
- Recovery Manifest:
  `finance_v26_orphan_support_exit_recovery_manifest:9ecaa1ab2e16c937fef67fa024be42f2f3d5a69338fc7be27812135a49583244`;
- Runner Contract:
  `finance_v26_orphan_support_exit_runner_contract:5d6ffa0344dec1f7798e1d5f4ac7dfa8da158d7d73c8c137c40748bcb2d25be4`;
- Outcome Contract:
  `finance_v26_orphan_support_exit_outcome_contract:91f65d4c0ed677aee782d222169437db4e2180be6f384fd37829ee2b7fd5e29d`;
- prospective execution:
  `finance_v26_orphan_support_exit_recovery_execution:de3a15652e87723cca7c6d241c808bf74532fa04c512e21312959a92ebf5c504`;
- prospective report identity:
  `finance_v26_orphan_support_exit_recovery_report:6f666c17ae2ece4dfb3ff09dbb3286ea5778f8a2c3bda900da48f7fcd81f6c6c`;
- v26.143 transition:
  `finance_v26_orphan_support_exit_transition:b437327598149b20e0829e7946e729eb5830a987276e9f01f4c20f47a32f25c0`.

The exact RecoveryJobs are `5293d8f47334`, `7b8324126b26`, and `81f1377df032` by suffix. Their
historical parents remain the v26.141 orphan Jobs `9b354e7884df`, `e3ac0be4a8a1`, and
`ef32ef59e0f7`. Fresh and historical identity overlap is zero.

## Preexecution Closure

Before loading Recovery inputs, the committed execution source must replay 7,256/7,256 files:

```text
v26.143 transitive source files       7,242
v26.143 formal output files              13
v26.144 implementation                    1
total                                  7,256
```

It then independently rebuilds all thirteen v26.143 formal files. That reconstruction includes
the complete v26.142 failed-lineage replay, all three Candidate prefixes, both Candidate
construction passes, all Contracts, the Manifest, future identities, Runner fixtures, destructive
audit, and transition. All thirteen files must be byte-identical before a Recovery Raw can be
written.

`--prepare-only` writes the source replay, preexecution binding, and thirteen frozen v26.143 files
to the durable v26.144 directory. It writes no Raw, result, checkpoint, lineage, endpoint, or
execution report.

## Exact Raw Construction

For each RecoveryJob, the execution independently reconstructs and matches its Candidate. The new
Raw binds:

- exact historical Envelope, public Projection, and Transport certificate identities;
- exact selected model Action and reversible Commit record;
- exact failed `typed_selector_requires_refinement` Observation;
- exact successor State and successor Prompt hash;
- reproduced reference-policy failure;
- terminal `ordinary_replan_reference_unavailable`;
- zero reissued historical calls, zero new calls, zero later calls, and zero Stage 2 calls;
- no historical Raw creation and no historical terminal assignment.

The terminal is a measurement-support boundary exit. It is explicitly neither a model-invalid
trajectory nor an Instrument failure. Each Raw and result receives a fresh content-addressed
identity and is persisted only in the v26.144 directory.

The execution writes one sorted three-row checkpoint JSONL. Existing complete v26.144 Raw/result
pairs may be reloaded without any call. A one-sided Raw/result orphan fails closed.

## Endpoint Interpretation

The pre-registered endpoint partition is:

```text
frozen complete-Raw model outcomes           93
fresh measurement-support exits               3
exact lineage endpoints                      96
frozen model-valid trajectories              17
frozen model-invalid trajectories            76
```

The three support exits do not fill missing model outcomes. The 17/93 model subset remains
descriptive, no exact task-weighted Capability estimate is available, and the exact Capability
Gate remains failed. A completed v26.144 run authorizes only an independent credential-free
postrun audit. Reachability and State Mapping remain unauthorized.

## Durable Output

Formal execution output is written only to:

```text
/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis/artifacts/vtdo_experiment/finance_v26_144_orphan_support_exit_recovery_execution_v1_20260825
```

The directory is persistent and independent of `/tmp`. The implementation and this protocol are
committed before formal prepare-only or execution.

## Pre-Run Verification

Focused Ruff, Mypy, and Python compilation pass. Focused Pytest passes 2/2 in 353.96 seconds. It
performs the full 7,256-file source and thirteen-file preflight rebuild in a temporary directory,
executes all three RecoveryJobs, validates all new Raw/result/checkpoint files, and reconstructs
the exact 96-endpoint Outcome and postrun transition with zero Provider calls.

## Current Boundary

The current authorization remains:

```text
orphan_reference_unavailable_support_exit_recovery_execution_only
```

Capability continuation, historical Job rerun or reclassification, historical Raw or terminal
creation, Host Action selection/replacement/repair, S1/Candidate/Prompt/Grammar/classifier/model/
Thinking/resource change, Provider calls, Reachability identity or execution, State Mapping,
training, release, and production Contribution remain forbidden.

## Formal Execution Outcome

The committed implementation at `d5c5a70` completed formal prepare-only with source replay
`finance_v26_orphan_recovery_execution_source_replay:326f86258387c9fade6eb5a5711d83ee73fe389966dfce0449460288512259db`
and preexecution binding
`finance_v26_orphan_recovery_execution_binding:559ee4f29eaadabd3e0225f0ee7584f81d28c32ca1c44e0e3a08d3b85980c94d`.
All 7,256 source entries and all thirteen v26.143 outputs passed. Prepare-only wrote fifteen files
and zero Raw, result, checkpoint, lineage, endpoint, or report files.

The exact three-Job execution then completed with three fresh Recovery Raw Executions, three fresh
results, and one three-row checkpoint. The Raw identities are:

- `finance_v26_orphan_support_exit_recovery_raw:b0eb2e14b3f90c5af95cb9ff078b3ae973ede33d61c290b32666b5c3268ee771`;
- `finance_v26_orphan_support_exit_recovery_raw:af4b49e5c4f8828f47f0cf574f1c72fcc38808acc659f39158a71ad16667e2dd`;
- `finance_v26_orphan_support_exit_recovery_raw:c8f74a153c8289eb95ea76deceed7bc5423b327bf10c5cdb468cf6e94f903456`.

Each Raw retains the exact historical first-call parents, model Action, Commit, failed
`typed_selector_requires_refinement` Observation, successor State, successor Prompt, and
reference-policy failure. Each terminates `ordinary_replan_reference_unavailable`. Historical
prefix calls reissued, new Provider calls, later Provider calls, Stage 2 Provider calls,
credential lookups, client constructions, historical Raw creations, and historical terminal
assignments are all zero.

The complete endpoint partition is 93 frozen model outcomes plus three fresh measurement-support
boundary exits, totaling 96 lineage endpoints. The frozen model outcomes remain seventeen valid
and 76 invalid trajectories. The three support exits are neither model-invalid trajectories nor
Instrument failures. The exact Capability Gate remains failed, no exact task-weighted Capability
estimate is available, and Reachability remains unauthorized.

The authoritative execution identities are:

- report:
  `finance_v26_orphan_support_exit_recovery_execution_report:41e274f0986e9064ab68d6b3fac286a70da7793d4b7c1d72b27cd8503e433e22`;
- Raw Lineage:
  `finance_v26_orphan_support_exit_raw_lineage:bd1adb9f644f30e8d142b971eb6c5525d18ba69c111eaf95e02f28c7cd1fe8c1`;
- endpoint outcome:
  `finance_v26_orphan_support_exit_endpoint_outcome:00cdc80a7076d4d9a62506df5c06bfe33a25a4167e62d7a761551404413092cb`;
- postrun transition:
  `finance_v26_orphan_support_exit_postrun_transition:68eb384bd0ce63142ceed87ff7ecbca2cc909ae3b89b22dc4052ba954a55514c`.

The only permitted transition is now:

```text
orphan_support_exit_recovery_postrun_audit_only
```

The successor may only independently replay and audit the frozen v26.144 lineage with zero
Provider calls. Capability continuation, historical reclassification, Reachability, State
Mapping, training, release, and production Contribution remain forbidden.
