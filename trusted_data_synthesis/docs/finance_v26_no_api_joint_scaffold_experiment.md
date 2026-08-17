# Finance v26.20 No-API Joint/Scaffold Experiment

Date: 2026-08-17

## Purpose and boundary

This experiment executes the first real 24-task v26 Development chain that was left open by the
Joint Compilation audit closure:

```text
Fresh Development Population
-> Joint Compilation and State-space Compilation
-> atomic Joint Audit
-> Joint Admission
-> four-level Scaffold Compilation
-> atomic Scaffold Audit
-> Scaffold Admission
-> Bridge static Development Authorization
```

It deliberately stops before `bridge_rollout`. No model client was initialized, no public task or
financial Evidence was sent to an external provider, and no GPU job was created. The result
authorizes the next experimental stage; it is not a Bridge efficacy, State-support, VTDO,
Contribution, or Student result.

## Frozen artifacts

The successful immutable run is:

```text
protocol directory = artifacts/vtdo_experiment/
                     finance_v26_20_no_api_protocol_20260817/
run directory      = artifacts/vtdo_experiment/
                     finance_v26_20_no_api_joint_scaffold_20260817/
report              = .../finance_v26_20_no_api_joint_scaffold_20260817/report.json
```

Key identities:

```text
report_id = finance_v26_no_api_joint_scaffold_report:
            119d87b86d46e43e8fe89ac891d2eb4f50e5be0fbd01493fa1ff9afb2e3f4a46
protocol_id = finance_v26_capability_heterogeneous_vtdo_mainline:
              67be018215638fe576b0963da5f834092f58c6f3307fc103cfd58a088ddd9343
development_population_id = finance_v26_fresh_task_population:
                            db25214d364d5455a9414112174cc46b75db6c509c3c1ddc6e2977f3aa6849dd
confirmation_population_id = finance_v26_fresh_task_population:
                             b7c43c83190a141d45a672213acbb706b0b9b74b77296220d5cbd8bb1c223487
freshness_audit_id = finance_v26_cross_population_freshness_audit:
                     bfdd92862195ef70c93ee4d7dc4864a8a869430170d90881dc25f335780cdd92
bridge_authorization_id = finance_bridge_development_authorization:
                          6c1dcbf87bebdd40a992f3bcddb0a9b740db82b1831b4317627a930410ff971d
final_ledger_id = finance_v26_stage_ledger:
                  53feb55f0e63618dbc4338e92f34361461531f3bf16cac99a1caf7be29fcd2a8
```

The report freezes 22 immutable JSON files with relative path, byte count, and SHA-256.

## Cross-population freshness

Development and Fresh Confirmation were replayed from separate typed source Populations. The
audit computes all eight preregistered identity channels from the selected source tasks rather
than inferring freshness from Population IDs.

| Channel | Development intersection Fresh Confirmation |
| --- | ---: |
| Task ID | 0 |
| Source Task ID | 0 |
| Evidence ID | 0 |
| Evidence Version ID | 0 |
| Core Semantic Signature | 0 |
| Task Signature | 0 |
| Mechanism-instance Signature | 0 |
| Source Record ID | 0 |

Any nonzero overlap is rejected before Joint Compilation. Source bytes, canonical payloads,
Population identities, and every selected task root are replayed independently.

## Real execution results

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

The 72 Joint audit records are three audit families per task. Their 384 atomic cases execute real
public-sufficiency, executable-closure, and destructive-mutation checks. Gold Evidence ablation is
verified by replaying the task program and Oracle contract; it is not inferred from distractor
cardinality.

Each Scaffold ladder contains `gamma_0..gamma_3`. The 672 gate records contain 3,024 atomic checks,
including ordered Summary history, action and parameter neutrality, recursive noninterference,
incremental necessity, withdrawal readiness, and state-mapping invariance. The 96 history cases
show that two traces with the same latest state but different failure/completion histories remain
distinguishable. The 96 cross-level cases show that identical model behavior at all four scaffold
levels maps to one quotient-state identity while retaining a separate scaffold audit trace.

The three mechanism-level Bridge static audits all achieved construct fidelity `1.0`. Their
authorization embeds the frozen hierarchical inference contract: tasks are the primary sampling
unit, bootstrap resampling is task-first and rollout-second, scaffold levels are paired within
task, mechanism-level confidence intervals are required, and rollout-level pseudoreplication is
forbidden.

## Failure-to-fix trace

Earlier immutable attempts are retained as diagnostics and are not relabeled as successful runs.

| Run | Observed failure | Repair |
| --- | --- | --- |
| v26.11 | Router expected a top-level schema version that compiled artifacts do not own | Resolve the schema from the embedded Joint Compilation root |
| v26.12 | Router referenced a nonexistent state-space `joint_compilation_id` field | Validate the typed `joint_compilation_artifact_id` |
| v26.13 | Public-sufficiency audit treated distractor presence as a prerequisite for Gold ablation | Execute actual Gold Evidence ablation and Oracle replay |
| v26.14 | Post-report replay depended on JSON dictionary insertion order | Validate the exact freshness key set, independent of serialization order |
| v26.15 | Functional replay passed, but full Mypy found the frozen Provider incompatible with its mutable Protocol | Make the internal Provider satisfy the Core Protocol without changing its values |
| v26.16 | Functional replay passed, but report counts were constants and two replay paths reused the same boolean result | Derive every count from persisted artifacts and separate the typed replay implementations |
| v26.17 | Independent typed replay exposed tuple/list drift in serialized Summary history | Upgrade Summary to v3 and make ordered histories JSON-stable lists |
| v26.18 | The independent replay helper still expected the old tuple representation | Align the independent expectation with the v3 wire contract without weakening comparison |
| v26.19 | Passed, but subsequent formatting changed the current runner content hash | Preserve v26.19 as immutable history and rerun instead of reinterpreting its manifest |
| v26.20 | No blocker | Completed strict accounting and replay against the exact final source manifest |

No gate threshold was relaxed in these repairs.

## Credential-free replay

A child process replayed the complete immutable chain with:

```text
credential-like environment keys = 0
CUDA_VISIBLE_DEVICES              = ""
return code                       = 0
model API calls                   = 0
GPU jobs                          = 0
```

It reproduced the same final Ledger ID and the same next stage, `bridge_rollout`. The replay also
recomputed report counts from the 22 persisted JSON files, required exact immutable-path coverage,
round-tripped Joint and Scaffold artifacts through typed schemas, independently reconstructed the
ordered-history and cross-level mapping checks, and separately replayed all Bridge static checks.
This establishes that the result is not a cached success flag and that the static chain does not
depend on an API credential, hidden process state, or GPU runtime.

## Repository verification

The final implementation and report were checked together:

| Check | Result |
| --- | --- |
| Ruff | passed |
| Mypy | passed, 340 source files |
| Full Pytest | 830 passed in 162.41 seconds |
| Core generalization contract | 134 files, zero violations |
| Tracked credential-pattern scan | zero matching files |
| Post-report credential-free replay | exit code 0, identical Ledger ID |
| `git diff --check` | passed |

## Interpretation and next boundary

The audit finding "real per-task Joint/Scaffold execution absent" is now closed for the 24-task
Development Population. The valid conclusion is:

```text
No-API Joint/Scaffold chain       passed
Bridge Development static gate   authorized
Bridge Development rollouts      not run
Fresh Confirmation execution     not run
State-support freeze             absent
No-C VTDO                        blocked
Student training                 blocked
Contribution                     0 and unauthorized
```

The next permitted operation is the preregistered 576-observation Flash Development rollout. Its
runner must replay this Ledger and Bridge authorization before model-client construction, persist
raw immutable observations before aggregation, and apply the frozen hierarchical inference
contract. This report does not itself claim that the rollout should pass.
