# Finance v26.143 Orphan Support-Exit Recovery Preflight

Date: 2026-08-24

## Decision

Finance v26.143 consumes only the credential-free transition authorized by the independent
v26.142 failed-lineage audit. It binds the three v26.141 Provider-artifact orphans to fresh
Recovery Candidate, Contract, Job, Manifest, Outcome, Runner, future execution, and future report
identities. It then proves with local fixtures that each exact persisted public prefix terminates
as `ordinary_replan_reference_unavailable` before any later Provider preparation.

This stage makes zero Provider calls, zero Stage 2 Provider calls, and zero GPU calls. It creates
no historical Raw Execution or terminal, does not rerun or reclassify a historical Job, and does
not treat a fixture as an empirical recovery result.

## Source And Predecessor Replay

Before role inputs are loaded, v26.143 replays 7,242/7,242 files:

```text
v26.142 transitive source files       7,234
v26.142 formal output files               7
v26.143 implementation                    1
total                                  7,242
```

The stage then independently rebuilds all seven v26.142 formal files. It reprojects all 93
complete Raw Executions, validates all 858 Provider artifact triples, and reproduces all three
orphan root-cause rows. Every rebuilt v26.142 file is byte-identical to its formal predecessor.
No historical terminal changes.

## Recovery Candidates

Each Candidate binds the exact historical Job, first Envelope, public Projection, Transport
certificate, public payload hash, initial Prompt and salted Candidate presentation, selected
Action, reversible Commit record, failed public Observation, Choice and Progress records,
successor State, successor Prompt and salted presentation, and reproduced reference-policy
failure. Every binding is independently reconstructed rather than copied from the Candidate under
test.

The three rows are:

| Tier | Replica | Historical Job suffix | Prefix tokens | Successor Prompt bytes |
| --- | ---: | --- | ---: | ---: |
| Easy | 2 | `e3ac0be4a8a1` | 10,045 | 11,591 |
| Easy | 4 | `9b354e7884df` | 10,770 | 11,591 |
| Hard | 0 | `ef32ef59e0f7` | 13,126 | 21,728 |

All three public payloads select a visible `acquire_public_input` Candidate and preserve the exact
model Action. All three compile a reversible `query_structured_fact` Commit. Their public
Observations fail with `typed_selector_requires_refinement`, after which the exact successor
Prompt is reconstructed with zero classifier-sensitive Keys. No second Transport invocation
exists.

The Candidate identities are:

- `finance_v26_orphan_support_exit_candidate:26cad0b627c3bc0bb26f7f905432c1c5a7d322a7cf9573b2c047f723d1f52ed2`;
- `finance_v26_orphan_support_exit_candidate:299d4b565974d2e02382e6196b4359ce7b5311b244abde9c33138be45832e4e4`;
- `finance_v26_orphan_support_exit_candidate:4ea31774c781a68c91a762e1fbc4d93ec79aff7a02579b9a7a074ab61ea5da15`.

## Fresh Identity Chain

The exact fresh RecoveryJob identities are:

- `finance_v26_orphan_support_exit_recovery_job:5293d8f4733422688c9173bf924c7fa7cb03a5ce9299735920ed6328b867dd6a`;
- `finance_v26_orphan_support_exit_recovery_job:7b8324126b262be4a553bffa1a4cfb2e197bdd7093219f8dd6a7c18196551835`;
- `finance_v26_orphan_support_exit_recovery_job:81f1377df0328ebaac17cf25c66314ecb38c939a471cc78037c745666a71e976`.

They have zero identity overlap with the three historical Capability Jobs. Historical Job
identities are retained only as parents. Prefix Provider calls authorized for replay, later
Provider calls authorized, and Stage 2 Provider calls authorized are all zero.

The Runner has no credential lookup route, model-client route, Host reference fallback, or model
Action replacement path. A mismatched orphan artifact fails closed. Completed recovery is
raw-only and cannot mutate the v26.141 directory.

## Runner Fixture

The local Runner fixture reconstructs all three Candidates a second time and matches each exact
RecoveryJob. It emits exactly three typed fixture rows:

```text
fixture Jobs                                 3
exact persisted-prefix replays               3
typed support exits                          3
historical Provider calls reissued           0
new Provider calls                           0
later Provider calls                         0
Stage 2 Provider calls                       0
historical Raw or terminals created          0
```

The terminal is `ordinary_replan_reference_unavailable` with failure type
`reference_policy_unavailable` and the exact reproduced error
`Prompt-only acquisition policy cannot satisfy its public route`. The model Action, Commit,
Observation, successor State, and successor Prompt remain bound. The terminal is emitted before
later Provider preparation.

## Outcome Boundary

The prospective Outcome Contract closes the future lineage as:

```text
frozen complete-Raw model outcomes           93
fresh recovery support exits                  3
exact lineage endpoints                      96
frozen independently valid model outcomes    17
```

The three support exits are measurement-support boundary rows. They are neither model-invalid
trajectories nor Instrument failures. The 17/93 complete-Raw value remains descriptive, no exact
task-weighted Capability estimate is available, and the exact Capability Gate remains failed.
Reachability remains unauthorized.

Eighteen destructive controls reject historical identity reuse, Job deletion or duplication,
prefix-call reissue, later Provider authorization, Host reference fallback, model Action or
Observation change, successor Prompt change, historical Raw or terminal creation, terminal
reclassification, prior-attempt pooling, exact-estimate promotion, Reachability, State Mapping,
and private-reasoning hashing.

Focused Ruff, Mypy, and Python compilation pass. Focused Pytest passes 2/2 in 349.75 seconds and
independently reproduces all thirteen formal files byte for byte.

## Authoritative Identities

- report:
  `finance_v26_orphan_support_exit_preflight_report:ee6af1ef4e1462316a953fb247347792b1a04e017a371f9ba756801ce90de0ac`;
- source replay:
  `finance_v26_orphan_recovery_source_replay:6f57246215f1310516c7d197e7226d5e0c03135f337895def336d06204272bff`;
- predecessor rebuild:
  `finance_v26_orphan_recovery_predecessor_rebuild:51938379c3bc2547d4e9bd462a38f25033f2dd17f9d00ae1e8bb486990833cc0`;
- Candidate catalog:
  `finance_v26_orphan_support_exit_candidate_catalog:ca6a295ff2ea0ef4e635efa35310321eb38621bef356c09ee4c6ec99f7117428`;
- Recovery Contract:
  `finance_v26_orphan_support_exit_recovery_contract:95e4d0de4c1c0aded5bfaae0704f79af47d013fa8f360f3ca9406de84797a8fa`;
- Recovery Manifest:
  `finance_v26_orphan_support_exit_recovery_manifest:9ecaa1ab2e16c937fef67fa024be42f2f3d5a69338fc7be27812135a49583244`;
- Outcome Contract:
  `finance_v26_orphan_support_exit_outcome_contract:91f65d4c0ed677aee782d222169437db4e2180be6f384fd37829ee2b7fd5e29d`;
- Runner Contract:
  `finance_v26_orphan_support_exit_runner_contract:5d6ffa0344dec1f7798e1d5f4ac7dfa8da158d7d73c8c137c40748bcb2d25be4`;
- prospective execution:
  `finance_v26_orphan_support_exit_recovery_execution:de3a15652e87723cca7c6d241c808bf74532fa04c512e21312959a92ebf5c504`;
- prospective report:
  `finance_v26_orphan_support_exit_recovery_report:6f666c17ae2ece4dfb3ff09dbb3286ea5778f8a2c3bda900da48f7fcd81f6c6c`;
- Runner fixture:
  `finance_v26_orphan_support_exit_runner_fixture:e3861ac1ae8c8f4062577491ca219ca3ac75a63f408f67ef7f1ebbfc9e67a3a6`;
- destructive audit:
  `finance_v26_orphan_support_exit_destructive:48ac1f131189b7f96171d151254d85ebc3c8c9d629239dd0a6a23387f466c597`;
- transition:
  `finance_v26_orphan_support_exit_transition:b437327598149b20e0829e7946e729eb5830a987276e9f01f4c20f47a32f25c0`.

## Permitted Transition

The only permitted transition is:

```text
orphan_reference_unavailable_support_exit_recovery_execution_only
```

The successor may execute only the exact three-Job Recovery Manifest under the exact Runner,
Outcome, future execution, and future report identities above. It must replay each persisted
prefix, emit the exact typed support exit, write fresh recovery Raw and result artifacts, and make
zero Provider or Stage 2 Provider calls.

Capability continuation, historical Job rerun or reclassification, historical Raw or terminal
creation, Host Action selection/replacement/repair, S1/Candidate/Prompt/Grammar/classifier/model/
Thinking/resource change, Reachability identity or execution, State Mapping, training, release,
and production Contribution remain forbidden.
