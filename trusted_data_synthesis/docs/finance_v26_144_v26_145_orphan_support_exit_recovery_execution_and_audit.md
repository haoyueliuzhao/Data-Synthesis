# Finance v26.144-v26.145 Orphan Support-Exit Recovery Execution And Audit

Date: 2026-08-25

## Decision

Finance v26.144 consumed only the exact three-Job zero-call Recovery execution authorized by
v26.143. It created three fresh Recovery Raw Executions and three fresh results under the exact
pre-registered identities. Every row terminates
`ordinary_replan_reference_unavailable` before any later Provider preparation.

Finance v26.145 independently replays and rebuilds the complete v26.144 directory with zero
Provider calls. It confirms that the exact lineage now has 96 auditable endpoints but only 93
model outcomes. The three fresh rows are measurement-support boundary exits, not missing model
outcomes, model-invalid trajectories, or Instrument failures. The exact Capability Gate remains
failed, no exact task-weighted Capability estimate is available, and Reachability remains
unauthorized.

## Execution Binding

The committed v26.144 source at `d5c5a70` replayed 7,256/7,256 files before Recovery input
loading: 7,242 v26.143 transitive entries, thirteen v26.143 outputs, and the exact execution
implementation. It independently rebuilt all thirteen v26.143 formal files byte for byte.

Formal prepare-only produced:

- source replay
  `finance_v26_orphan_recovery_execution_source_replay:326f86258387c9fade6eb5a5711d83ee73fe389966dfce0449460288512259db`;
- preexecution binding
  `finance_v26_orphan_recovery_execution_binding:559ee4f29eaadabd3e0225f0ee7584f81d28c32ca1c44e0e3a08d3b85980c94d`.

Prepare-only wrote fifteen frozen-input and binding files, no Raw or result, and made zero calls.
The execution then consumed exactly:

- Manifest
  `finance_v26_orphan_support_exit_recovery_manifest:9ecaa1ab2e16c937fef67fa024be42f2f3d5a69338fc7be27812135a49583244`;
- Runner
  `finance_v26_orphan_support_exit_runner_contract:5d6ffa0344dec1f7798e1d5f4ac7dfa8da158d7d73c8c137c40748bcb2d25be4`;
- Outcome Contract
  `finance_v26_orphan_support_exit_outcome_contract:91f65d4c0ed677aee782d222169437db4e2180be6f384fd37829ee2b7fd5e29d`;
- prospective execution
  `finance_v26_orphan_support_exit_recovery_execution:de3a15652e87723cca7c6d241c808bf74532fa04c512e21312959a92ebf5c504`;
- prospective report identity
  `finance_v26_orphan_support_exit_recovery_report:6f666c17ae2ece4dfb3ff09dbb3286ea5778f8a2c3bda900da48f7fcd81f6c6c`.

## Recovery Raw Results

The three fresh Raw identities are:

- `finance_v26_orphan_support_exit_recovery_raw:b0eb2e14b3f90c5af95cb9ff078b3ae973ede33d61c290b32666b5c3268ee771`;
- `finance_v26_orphan_support_exit_recovery_raw:af4b49e5c4f8828f47f0cf574f1c72fcc38808acc659f39158a71ad16667e2dd`;
- `finance_v26_orphan_support_exit_recovery_raw:c8f74a153c8289eb95ea76deceed7bc5423b327bf10c5cdb468cf6e94f903456`.

Each Raw independently reconstructs and matches its exact v26.143 Candidate. It retains the
historical first-call Envelope, public Projection, and Transport certificate; selected model
Action; reversible Commit; failed `typed_selector_requires_refinement` Observation; successor
State; successor Prompt; and reproduced reference-policy failure. The historical model Action is
not selected, replaced, normalized, or repaired by the Host.

The execution count is:

```text
fresh RecoveryJobs                         3
fresh Recovery Raw Executions              3
fresh Recovery results                     3
checkpoint rows                            3
historical prefix calls reissued           0
new Provider calls                         0
later Provider calls                       0
Stage 2 Provider calls                     0
credential lookups                         0
model-client constructions                 0
historical Raw or terminals created        0
```

The v26.141 historical directory remains unchanged at 2,680 files. The new Raw rows exist only in
the v26.144 directory and retain the historical Job identities solely as parents.

## Endpoint Result

The formal and independently reconstructed endpoint partition is:

```text
exact lineage endpoints                   96
frozen complete-Raw model outcomes        93
frozen model-valid trajectories           17
frozen model-invalid trajectories         76
fresh measurement-support exits            3
Instrument failures                        0
```

The three support exits close artifact lineage, not the exact model-outcome denominator. They
cannot be pooled into the 93 model outcomes or labeled as failed model trajectories. Consequently:

- the 17/93 complete-Raw subset remains descriptive only;
- no exact-denominator confidence interval is reported;
- no missing model outcome is inferred or imputed;
- the exact all-96 Capability Gate remains failed;
- no Capability success claim, Reachability authorization, or State Mapping row is created.

The formal v26.144 identities are:

- execution report
  `finance_v26_orphan_support_exit_recovery_execution_report:41e274f0986e9064ab68d6b3fac286a70da7793d4b7c1d72b27cd8503e433e22`;
- Raw Lineage
  `finance_v26_orphan_support_exit_raw_lineage:bd1adb9f644f30e8d142b971eb6c5525d18ba69c111eaf95e02f28c7cd1fe8c1`;
- endpoint outcome
  `finance_v26_orphan_support_exit_endpoint_outcome:00cdc80a7076d4d9a62506df5c06bfe33a25a4167e62d7a761551404413092cb`;
- postrun transition
  `finance_v26_orphan_support_exit_postrun_transition:68eb384bd0ce63142ceed87ff7ecbca2cc909ae3b89b22dc4052ba954a55514c`.

## Independent Audit

v26.145 replays 7,283/7,283 files before loading a Recovery result: all 7,256 v26.144 transitive
source entries, all 26 execution files, and its exact implementation. It then executes v26.144
again in an empty temporary directory. All 26 rebuilt files, including source replay,
preexecution binding, frozen inputs, three Raw, three results, checkpoint, lineage, endpoint,
transition, and report, are byte-identical.

The audit independently parses and matches all three Manifest Jobs, Raw rows, results, and
checkpoint rows. It validates the exact historical prefix parents, Action, Commit, Observation,
successor State and Prompt, typed terminal, fresh/historical identity separation, Raw Lineage
descriptors, and the unchanged 2,680-file historical directory.

Fourteen destructive controls reject missing-outcome inference, support-exit deletion or
reclassification, RecoveryJob promotion to model outcome, partial-subset promotion, prior-attempt
pooling, historical reclassification, Capability or Reachability execution, new Population
materialization, State Mapping, Provider calls, and private-reasoning hashing.

Focused v26.144 Pytest passes 2/2 in 353.96 seconds. Focused v26.145 Pytest passes 2/2 in 354.56
seconds. Focused Ruff, Mypy, and compilation pass for both stages. Neither stage makes a Provider
or GPU call.
Package-wide Mypy checks 462 source files and retains only the three pre-existing v26.70/v26.129
diagnostics, with zero v26.141-v26.145 diagnostics.

The authoritative v26.145 identities are:

- report
  `finance_v26_orphan_recovery_postrun_audit_report:b89eb11ef32169e985b4f7fdb765c140440c4e1e2fdcf5b7d700736a64103602`;
- source replay
  `finance_v26_orphan_recovery_postrun_source_replay:0dfd94daa1afe73b6eb7437b8200f877c61b86753c99aa1574607a76ca9f2716`;
- independent execution rebuild
  `finance_v26_orphan_recovery_independent_rebuild:ac10dd4a17d5e9632f3dcc31631f9221d6048e293b028b0bd2345a13d5cd1d0b`;
- independent Raw reconstruction
  `finance_v26_orphan_recovery_independent_raw:347618ee5c8951bf5555c7b9245e0327ea543d7fb394bf20a4ef4379f69ce5f2`;
- Capability outcome decision
  `finance_v26_capability_support_boundary_decision:f3e11529e5bb3b19c814488bc1f11571f47967e6f0c424a36ee6278f56b4d97c`;
- destructive audit
  `finance_v26_orphan_recovery_postrun_destructive:24bf72c7efc5d0fe8c94da29b179a2303c79291b98de67e598c3f3e72a64a104`;
- transition
  `finance_v26_capability_support_boundary_transition:33a1d469b8d4493d205ef278b2671ccfa55bbc05656eebb2dfd4dc875669c2c1`.

## Permitted Transition

The only permitted transition is:

```text
capability_measurement_support_boundary_redesign_only
```

The successor may perform only credential-free design over the reference-unavailable
measurement-support classification. It may not change, pool, infer, or reclassify any v26.141 or
v26.144 outcome. It may not materialize a fresh Capability Population, TaskPackage, Manifest,
Job, Runner, or execution identity.

Provider calls, Capability execution, Reachability identity or execution, State Mapping,
training, release, and production Contribution remain forbidden.
