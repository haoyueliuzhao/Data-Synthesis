# Finance v26.76-v26.77 Verifier-Bound Rematerialization And Instrument Preflight

Audit completion date: 2026-08-20

Experiment identities were frozen and both formal builds were started on 2026-08-19. The
independent rebuild, repository validation, documentation, and commit completed after local
midnight on 2026-08-20. Artifact directory names and content-addressed run identities retain their
pre-midnight `20260819` value; they were not renamed after observing results.

This report is reconstructed from the current Git tree, immutable experiment artifacts,
credential-redacted process records, and checks rerun on the migrated server. Missing chat
messages are not treated as experimental evidence.

## Executive Decision

Finance v26.76 and v26.77 completed the only transition authorized by v26.75:

```text
fresh_verifier_bound_task_rematerialization_and_instrument_preflight_only
```

v26.76 materialized eight entirely fresh, mechanism-balanced Instrument TaskPackages. Every
TaskPackage binds the qualified Verifier v2 implementation and Replay Contract before its
TaskPackage identity is computed. The Population is disjoint from the prior v26 empirical inputs
on all eight frozen freshness channels. All Compiler Runtime Witnesses, Operation Closure audits,
Mechanism Necessity artifacts, authority-preserving repair audits, terminal-target audits, and
capability-role admissions passed. No model trajectory was generated.

v26.77 then froze a 32-job Instrument-only Contract and Job Manifest:

```text
4 mechanisms x 2 fresh tasks x 4 unconditional replicas = 32 jobs
```

The static preflight replayed 52 source and implementation files, replayed all 81 Compiler Witness
Observations through Verifier v2, passed public/private isolation for 8/8 tasks, rejected 24/24
new Replay mutations, retained 40/40 authority/terminal mutation rejections and 64/64 legacy
Operation mutation rejections, and found zero Job identity overlap against four historical
Manifests. The model client was never constructed. API calls and GPU jobs were zero.

The passing preflight authorizes only:

```text
fresh_verifier_v2_bound_instrument_requalification_only
```

It does not authorize Capability Development, State Reachability, Fresh Confirmation, No-C VTDO,
Student training, Exact Target, GP-C, or production Contribution. Production Contribution remains
zero.

Authoritative identities:

```text
v26.76 report =
finance_v26_verifier_bound_instrument_population_report:
4c810296a03f0491d60b20d6e74061a269e70eb35f8054cfa34eb34ea5547cb0

v26.77 preflight report =
finance_v26_verifier_bound_instrument_preflight:
d8c88785a217da74a6772a51a658ff7a0ee40ee77d3a11ebe5454f795721b263

v26.77 execution Contract =
finance_v26_verifier_bound_instrument_contract:
3ecdc9bff3a2a846ede932c28763abbac1c67c345553eacfec69b2de0985afda

v26.77 Job Manifest =
finance_v26_verifier_bound_instrument_manifest:
300bc703e726e04bbf22138a01bf8e09302a54906be8e7510ffa012d7256e724
```

The report-file SHA-256 values are:

| Report | SHA-256 |
| --- | --- |
| v26.76 | `066036f99cfd77b8e60cfe2ae73d1f74c4831db42de37879ff91d0da798baca7` |
| v26.77 | `88b4bc69bb174a9291e7b32a11c14895ecdf5e0d4f5e5faf0685abd9f53ffbd2` |

## Prior Authorization And Scientific Boundary

v26.74 found that the executed Agent Runtime and frozen Verifier v1 Replay used different
failed-result semantics. v26.75 prospectively repaired Replay and qualified it on 45 completed
historical trajectory fixtures, while preserving every historical validity, path, release, and
State Support result.

The 15 prospective v2-valid diagnostic candidates remain excluded from every v26.76 selection and
v26.77 result. They are not outcomes, Confirmation data, model-owned paths, released
realizations, or State Support.

The v26.75 authorization required two things before any new model call:

1. Fresh TaskPackages whose identities bind Verifier v2 and its Replay Contract from inception.
2. A small balanced Instrument Manifest that passes static source replay, Compiler Witness,
   authority, terminal-target, isolation, mutation, and independent-build gates.

This report covers exactly those two stages. It does not contain an online model result.

## v26.76 Fresh Verifier-Bound Instrument Population

### Population role and denominator

The Population is registered only for Instrument requalification. The underlying tasks use the
`capability_measurement` operational role because the existing Runtime and admission contracts
require that role, but v26.76 does not estimate Capability support. The eight tasks are balanced:

| Mechanism | Tasks |
| --- | ---: |
| Context-conditioned Action | 2 |
| Semantic Reconciliation | 2 |
| Failure Recovery | 2 |
| State-dependent Stopping | 2 |

The two tasks per mechanism follow the most recent passing Instrument precedent. This is not a
Capability denominator and cannot be pooled with v26.66, v26.71, or another historical run.

### Frozen source exclusion

The selector uses only immutable source structure, fixed identity exclusions, a preregistered
selection salt, and content-addressed ranking. No historical response, trajectory, prospective
candidate, task-level success rate, or mechanism-level success rate enters ranking.

The exclusion union contains the v26.42 Development source tasks and every v26.56, v26.65, and
v26.69 Task/Evidence input. The selected Population passes all eight freshness channels:

| Channel | Prior identities | Selected identities | Overlap |
| --- | ---: | ---: | ---: |
| Source task Artifact ID | 70 | 6 | 0 |
| Source semantic signature | 69 | 6 | 0 |
| Source task hash | 69 | 6 | 0 |
| Evidence ID | 494 | 47 | 0 |
| Evidence Version ID | 494 | 47 | 0 |
| Source record ID | 494 | 47 | 0 |
| Semantic Source ID | 60 | 8 | 0 |
| TaskPackage ID | 60 | 8 | 0 |

The six non-Reconciliation tasks are selected from the same three independently identified source
Populations used by the preceding rematerialization chain. They must also be mutually disjoint on
Evidence ID, Evidence Version ID, and source-record identity.

### Protocol-local capacity contracts

Two development probes failed before writing an Artifact:

- the historical source selector required six eligible tasks per mechanism even though the frozen
  Instrument role requires two;
- the historical Definition-pair loader required twelve pairs for six Reconciliation tasks even
  though this role requires four pairs for two tasks.

These failures localized hard-coded historical denominators. They are not empirical outcomes and
did not cause a freshness relaxation. v26.76 introduced protocol-local selectors that preserve
the exact exclusion, grounding, semantic-equivalence, Evidence-disjointness, content-addressed
ranking, and fail-closed rules while enforcing the new frozen `2 tasks/mechanism` and `4 pairs`
denominators.

After all exclusions, the immutable Finance Snapshot result was:

| Definition-pair item | Count |
| --- | ---: |
| Eligible Evidence | 124,329 |
| Eligible Definition pairs | 8 |
| Reconciliation task capacity | 4 |
| Selected Definition pairs | 4 |
| Materialized Reconciliation tasks | 2 |

Every selected pair contains exactly two definition-distinct, frequency-distinct records in the
same semantic equivalence group with equal registered value, one daily and one monthly. The
unselected capacity is not reserved for Confirmation and receives no empirical status.

### Replay binding construction

Each new task receives a task-specific `VerifierV2TaskReplayBinding`. The binding contains:

- the exact v26.75 qualification report ID and report SHA-256;
- the exact qualified Replay Contract ID;
- all five qualified Verifier implementation source hashes;
- Semantic Source identity;
- Public Operation Contract identity;
- Action-neutral Repair Contract identity;
- typed Terminal Verification Target identity;
- Public Runtime, Stop Readiness, and Runtime Projection identities;
- Answer Projection, Evidence Support Lattice, Citation, and Mechanism Contract identities;
- Program DAG and Verifier DAG hashes;
- Tool Environment Manifest identity and hash;
- exact Runtime gate order, failed-result projection, and canonical comparison rule.

The identity construction order is:

```text
qualified Verifier v2 report + Replay Contract + implementation bytes
    -> task-specific Replay Binding Contract
    -> Operational Verifier implementation binding
    -> Oracle selection contract binding
    -> TaskPackage identity
    -> Operational Task record identity
```

The TaskPackage's `verifier_implementation_id` is the content-addressed task Replay Binding
Contract ID. Its Verifier version is exactly
`authority_preserving_executable_task_verifier.v2`. The same IDs are independently persisted in
the Oracle selection contract. The public Task does not expose them.

This avoids a circular identity: the Replay Binding depends on all semantic and Runtime contracts,
but not on the final TaskPackage ID; the TaskPackage then binds the Replay Binding before its own
identity is frozen.

### Static task result

| Gate | Result |
| --- | ---: |
| Fresh TaskPackages | 8 / 8 |
| Task-specific Verifier v2 Replay bindings | 8 / 8 |
| Public Runtime Witnesses | 8 / 8 |
| Compiler Witness Observations | 81 |
| Operation Closure audits | 8 / 8 |
| Mechanism Necessity artifacts | 8 / 8 |
| Operational capability-role admissions | 8 / 8 |
| Repair Prompt audits | 8 / 8 |
| Terminal-target audits | 8 / 8 |
| Legacy Operation mutations rejected | 64 / 64 |
| Authority/terminal mutations rejected | 40 / 40 |
| API calls / GPU jobs | 0 / 0 |

Compiler Witnesses remain model-hidden, `compiler_generated=true`, and
`model_generated=false`. They prove public executable closure only and contribute zero empirical
Capability or State observations.

The v26.76 report permits only `verifier_v2_bound_instrument_preflight_only`.

## v26.77 Static Instrument Preflight

### Source and implementation replay

Before any model-client construction, v26.77 replayed 52 distinct files:

| Source class | Files |
| --- | ---: |
| Task source | 16 |
| Task detail Artifact | 15 |
| Task implementation source | 15 |
| Verifier qualification detail | 2 |
| Historical Job Manifest | 4 |
| Total | 52 |

Every expected SHA-256 equals the observed SHA-256. Duplicate paths from nested manifests must
agree on the same expected hash. A disagreement fails before Contract or Job identity creation.

The source replay audit is:

```text
finance_v26_verifier_bound_source_replay:
29cc2f10042683d76ad60c12cc7ed6495894c1fea488ac046e9543dab611dfdb
```

### Frozen online protocol, not executed

The execution Contract freezes:

- exact `deepseek-v4-flash`;
- empty fallback list and requested-model equality;
- 4 unconditional replicas for each of 8 tasks;
- one Provider attempt and one bounded contract-repair attempt per interaction;
- 120,000 provider-reported model tokens per rollout;
- USD 2.00 aggregate estimated-cost ceiling;
- raw-first Prompt and Provider telemetry;
- per-rollout repair-neutrality, terminal-target, Stop Readiness, and Replay audits;
- independent calculation of all non-Replay Verifier Gates;
- retention of every invalid model outcome;
- explicit exclusion of historical diagnostic candidates;
- Instrument measurement only and no model comparison.

The Job Manifest contains 32 unique Job identities. Every task appears exactly four times, and
every mechanism appears exactly eight times. The new Job identity set has zero overlap against:

- v26.63 Operation-closure requalification;
- v26.66 authority-preserving Instrument requalification;
- v26.71 Capability Development;
- v26.72 State Reachability.

No raw output path is allocated twice.

### Compiler Runtime-Verifier commutativity

For each task, v26.77 reconstructs the exact ordered Observation history named by its Compiler
Witness and replays it through the qualified Verifier v2:

```text
identical failed-action gate
-> public post-completion gate
-> public tool-argument gate
-> public terminal-verification gate
-> public Operation gate
-> Finance tool Runtime
-> public action-neutral failed-result projection
-> tool output contract
-> canonical JSON semantic comparison
```

All 81/81 Observations replayed, and all 8/8 Witness histories had an empty Replay failure set.
This establishes static Runtime-Verifier semantic commutativity for the newly bound tasks. It does
not establish commutativity on a new model-generated trajectory; that is the purpose of the next
small Instrument run.

### Public/private isolation

The public Task projection was recursively checked for private field names and exact private
identity values. The following remain absent from all 8/8 public tasks:

- Semantic Source identity;
- Verifier Binding identity;
- task Replay Binding Contract identity;
- qualified Verifier report and Replay Contract identities;
- Program DAG and Verifier DAG hashes;
- source Program node and expected-operator bindings;
- private mechanism state and target Program Evidence identities.

The model continues to receive the public Operation, repair, terminal-target, Runtime, Answer, and
tool contracts needed to act. Isolation does not remove public semantics required for the task.

### Destructive Replay mutations

Every mutation first receives a valid content-addressed Observation identity. The preflight then
requires a passing unmutated baseline and a failing mutated Replay.

| Mutation | Rejected | Required Replay failure |
| --- | ---: | --- |
| Wrong Environment Manifest identity | 8 / 8 | `environment_identity` |
| Changed business-result payload | 8 / 8 | `replay_mismatch` |
| Action-bearing patch injected into failed-result projection | 8 / 8 | `replay_mismatch` |
| Total | 24 / 24 | exact typed failure |

For the action-bearing case, the Host first constructs an invalid Calculator call, applies the
same public action-neutral failed-result projection as the Runtime, and verifies that this baseline
passes Replay. It then injects `operator` and `parameters` under a suggested patch, recomputes the
Observation identity, and requires Verifier v2 to reject the changed semantics. Thus the mutation
is not rejected merely because it carries a stale hash.

### Retained authority and operation mutations

The preflight independently loads and validates all v26.76 task audits:

| Existing mutation family | Rejected |
| --- | ---: |
| Missing terminal reference | 8 / 8 |
| Wrong terminal reference | 8 / 8 |
| Extra terminal claim field | 8 / 8 |
| Verification before terminal | 8 / 8 |
| Post-completion action | 8 / 8 |
| Authority/terminal total | 40 / 40 |
| Legacy Operation mutations | 64 / 64 |

Repair Prompt audits also retain zero action-binding path for 8/8 tasks.

## Determinism And Validation

The formal and independent v26.76 builds reproduced all 15 detail files and `report.json` byte for
byte. The formal and independent v26.77 builds reproduced all six detail files and `report.json`
byte for byte. Both rebuilds used zero API calls and zero GPU jobs.

Focused validation completed:

```text
Ruff check                         passed
Ruff format                        passed
Mypy, new source and tests         passed
Focused Pytest                     13 passed in 51.77 seconds
```

The focused tests rebuild both stages, compare every output against the formal artifacts, and
reject changed Replay IDs, stale report IDs, altered resource ceilings, and mutation reports that
claim an unrelated failure reason.

Repository-wide validation then completed:

```text
Ruff check                         passed
Mypy                               371 source files; only the retained v26.70 diagnostic
Pytest                             977 passed, 1 warning in 646.95 seconds
```

The single warning is the existing Pydantic serialization warning intentionally triggered by the
v26 Public Operation destructive identity test. The repository-wide formatter would still rewrite
116 historical baseline files; only the new files were format-checked. The retained Mypy
diagnostic remains the source-bound v26.70 local `provider_ids` annotation described in
`docs/current_project_status.md`.

## Interpretation Limits

The positive results establish:

1. Fresh TaskPackages can bind Verifier v2 and Replay semantics before identity freeze.
2. The new balanced Instrument Population is statically executable under public contracts.
3. Compiler Witness Runtime histories commute with Verifier v2 Replay.
4. Source, implementation, authority, terminal, isolation, and destructive mutation preconditions
   pass for the frozen 32-job design.
5. The 32 Job identities and all dependent Contract identities are fresh.

They do not establish:

1. that any new model trajectory is independently valid;
2. that online Runtime and Verifier v2 Replay commute for all newly observed failed-action paths;
3. balanced Capability support;
4. empirical State Reachability or three independent releases;
5. a repair to Recovery closure or search-route realization;
6. support for No-C VTDO, Student training, Exact Target, GP-C, or Contribution.

No historical v26.71 or v26.72 result is rescored. The State Support Freeze remains 0/36 states
and 0/12 tasks, `blocked`.

## Next Permitted Experiment

The only newly permitted transition is:

```text
fresh_verifier_v2_bound_instrument_requalification_only
```

The next run must execute exactly the frozen 32 Jobs. Its primary gates are Instrument gates, not
Capability-accuracy gates:

- 32/32 Jobs receive one terminal classification;
- Runtime failures and Instrument failures are zero;
- exact requested-model identity holds and fallback count is zero;
- raw Prompt and Provider payloads are persisted before parsing or scoring;
- all completed Observation sequences pass Verifier v2 Replay;
- non-Replay Gates are independently computed and retained;
- action-neutral repair and terminal-target audits pass per rollout;
- Stop Readiness has zero false positive and zero false negative;
- Provider-call identities are unique and token/cost telemetry stays inside the frozen ceilings;
- model-invalid outcomes remain in the denominator;
- Compiler Witnesses and the 15 historical diagnostic candidates contribute zero empirical rows.

Independent validity, Program closure, local mechanism behavior, and trace diversity may be
reported descriptively. They cannot control Instrument admission unless the frozen Contract says
so.

A passing online Instrument result may authorize only a new design stage for fresh Capability and
Reachability protocols. It does not itself authorize either 96- or 360-row empirical denominator.

## Authoritative Artifacts

- `artifacts/vtdo_experiment/finance_v26_76_verifier_bound_instrument_population_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_76_verifier_bound_instrument_population_20260819/verifier_v2_replay_bindings.json`
- `artifacts/vtdo_experiment/finance_v26_76_verifier_bound_instrument_population_20260819/source_freshness_audit.json`
- `artifacts/vtdo_experiment/finance_v26_76_verifier_bound_instrument_population_20260819/definition_pair_capacity_audit.json`
- `artifacts/vtdo_experiment/finance_v26_77_verifier_bound_instrument_preflight_20260819/report.json`
- `artifacts/vtdo_experiment/finance_v26_77_verifier_bound_instrument_preflight_20260819/execution_contract.json`
- `artifacts/vtdo_experiment/finance_v26_77_verifier_bound_instrument_preflight_20260819/job_manifest.json`
- `artifacts/vtdo_experiment/finance_v26_77_verifier_bound_instrument_preflight_20260819/compiler_replay_audits.json`
- `artifacts/vtdo_experiment/finance_v26_77_verifier_bound_instrument_preflight_20260819/destructive_mutation_audits.json`
- `artifacts/vtdo_experiment/finance_v26_77_verifier_bound_instrument_preflight_20260819/source_replay_audit.json`

## Current Authorization State

```text
verifier_v2_fixture_qualification                 passed
fresh_verifier_bound_task_rematerialization       passed
static_instrument_preflight                        passed
fresh_online_v2_bound_instrument                   not executed
historical_outcomes_rescored                       no
historical_state_support_freeze                    unchanged, blocked
capability_development                             forbidden
state_reachability                                 forbidden
fresh_confirmation                                 forbidden
no_c_vtdo                                          forbidden
student_training                                   forbidden
exact_target                                       forbidden
gp_c                                               forbidden
production_contribution                            0
next_permitted_stage                               fresh_verifier_v2_bound_instrument_requalification_only
```
