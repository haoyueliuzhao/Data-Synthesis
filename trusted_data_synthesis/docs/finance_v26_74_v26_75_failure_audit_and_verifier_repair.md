# Finance v26.74-v26.75 Failure Audit And Authority-Preserving Verifier Repair

Audit date: 2026-08-19

## Summary

Finance v26.74 performed the read-only root-cause audit requested after the balanced v26.71
Capability Development and v26.72 State Reachability runs. It replayed all 456 immutable raw
Artifacts, produced no model generation, did not rescore a historical outcome, and retained the
blocked 0/36 State Support Freeze.

The audit confirmed the expected Capability and route-control findings, but it also found a prior
instrument interpretation blocker that precedes task or condition redesign. The Agent Runtime
applied the v26.65 public Operation gates and action-neutral failed-result projection, while the
frozen v1 independent Verifier Replay still reconstructed the legacy failed-action result. Eighteen
completed trajectories therefore had `runtime_replay_passed=false` under a Replay that did not
mirror the executed Runtime.

The affected historical rows are:

| Role | Completed rows | Frozen Replay failures | Replay-only blockers |
| --- | ---: | ---: | ---: |
| Capability Development | 14 | 10 | 8 |
| State Reachability | 31 | 8 | 7 |
| Total | 45 | 18 | 15 |

All 18 pass an independent diagnostic Replay that uses the authority-preserving public gate set,
action-neutral failed-result projection, and canonical JSON semantic comparison. This diagnostic
does not reclassify the 15 rows whose only historical failure was Replay. The v26.71 and v26.72
reports, mappings, and Freeze remain immutable.

The authoritative v26.74 report is:

```text
finance_v26_capability_reachability_failure_audit:aa3787b164a9df684f05744110a44001dfcf01cea9cabff54a1c4532c6cc0e95
```

Its transition is:

```text
authority_preserving_verifier_replay_repair_only
```

Finance v26.75 implemented that prospective repair as Verifier v2. It mirrors the Agent Runtime's
failed-action and public Operation composition, applies the same action-neutral projection, and
compares replayed and recorded results after canonical JSON normalization. It then qualified the
new Verifier against all 45 completed historical trajectories strictly as frozen diagnostic
fixtures.

Verifier v2 passed 45/45 Replay checks, retained every non-Replay Gate value for 45/45 rows, and
rejected 108/108 destructive mutations. Fifteen rows become prospective v2-valid candidates: eight
Capability Stopping rows and seven Reachability Context rows. They remain historical-invalid and
create no state support.

The authoritative v26.75 report is:

```text
finance_v26_authority_verifier_qualification:f61be6be022c2c8506e818e3bb9690e71fa316c6820fec69458c7ab7c8fa7bb1
```

It authorizes only:

```text
fresh_verifier_bound_task_rematerialization_and_instrument_preflight_only
```

Neither stage made an API call or used a GPU.

The initial zero-API v26.74 and v26.75 directories without the `v2` suffix remain immutable and
are superseded. Package-wide Mypy exposed one local optional-result narrowing in the new v26.74
diagnostic Replay, and a final dependency audit added the imported v26.74 source to the v26.75
implementation manifest. The v26.74 seven scientific detail files are byte-identical between v1
and v2; v26.75 retains the same 45-row, 15-candidate, and 108-mutation result. New report identities
were issued instead of rewriting the earlier source-bound reports.

## Scientific Boundary

The v26.74-v26.75 result changes the interpretation boundary, not the historical data:

```text
historical Capability valid count    = 4 / 96
historical Reachability valid count  = 21 / 360
historical admitted states           = 0 / 36
historical admitted VTDO tasks       = 0 / 12
historical outcomes rescored         = false
historical path assignments changed  = false
historical State Support Freeze      = unchanged, blocked
```

The 15 prospective candidates answer only this counterfactual engineering question:

> Would the same completed trace pass the newly implemented Replay component while every other
> frozen Verifier Gate remains unchanged?

They do not answer whether a fresh model trajectory generated under a v2-bound TaskPackage is
valid. They cannot enter Capability support, State Mapping, realization release, Confirmation,
VTDO, or training.

The supported conclusion is narrower than historical rescoring and stronger than a source-code
guess:

```text
executed Runtime semantics
  != frozen v1 Verifier Replay semantics

executed Runtime semantics
  == prospective v2 Verifier Replay semantics on 45 / 45 completed fixtures
```

## v26.74 Read-Only Failure Audit

### Source replay

The audit binds the exact v26.71, v26.72, and authoritative v26.73 reports, task records,
environments, execution Contracts, Job Manifests, rollout aggregates, diagnostics, state summaries,
and State Support Freeze. It independently replays the SHA-256 and canonical JSON bytes of all 456
raw Artifacts.

No historical outcome is passed through a replacement acceptance rule. Existing verification
checks are read as frozen observations. Program closure, terminal completion, and typed
post-terminal verification are independently reconstructed from public Observations.

### Capability conversion

The full Capability denominator remains:

| Quantity | Result |
| --- | ---: |
| Rollouts | 96 |
| Independently valid | 4 |
| Invalid | 92 |
| Local mechanism success | 30 |
| Valid and local-success | 4 |
| `P(V=1 | Y=1)` | 4/30 |
| `P(Y=1 | V=1)` | 4/4 |

The 92 invalid rows split into 82 model-contract failures and 10 frozen Runtime Replay failures.
Evidence Support and Answer Projection were evaluated for 14 completed trajectories and passed in
all 14. They were correctly recorded as `not_evaluated`, rather than failed, for the 82 rows that
never entered the independent Verifier.

Mechanism conversion is:

| Mechanism | Local success | Historical valid | Program closed among local-invalid | Exact post-terminal verification among local-invalid | Verifier evaluated among local-invalid |
| --- | ---: | ---: | ---: | ---: | ---: |
| Context-conditioned Action | 8 | 4 | 1 | 1 | 0 |
| Semantic Reconciliation | 2 | 0 | 2 | 2 | 2 |
| Failure Recovery | 12 | 0 | 1 | 1 | 0 |
| State-dependent Stopping | 8 | 0 | 8 | 8 | 8 |

Recovery's twelve local successes fail to convert for directly observed reasons:

| Frozen terminal reason | Count |
| --- | ---: |
| Failed-tool budget exhausted | 7 |
| Unavailable `open_document` selected | 3 |
| Model-token budget exhausted | 2 |

Eleven of the twelve Recovery rows fail before full public Program closure. One reaches complete
Program and exact terminal verification, then exceeds the model-token budget before producing an
accepted final trajectory. None enters the independent Verifier, so Evidence and Answer validity
are not inferred for these rows.

The two Reconciliation local-success rows complete Program and exact terminal verification but
fail frozen Replay plus Verification and Citation checks. Verifier v2 repairs Replay only; they are
not prospective validity candidates.

All eight Stopping local-success rows complete Program, terminal Operation, exact typed
post-terminal verification, Evidence Support, Answer Projection, Citation, mechanism, and
post-completion control. Their only frozen failed check is Runtime Replay. Therefore the historical
0/24 Stopping result cannot support a task-capability interpretation until a fresh v2-bound run is
observed.

### Stopping role contrast

Capability and Reachability use disjoint task and Semantic Source identities and share zero exact
structural signatures under the audit profile. They also differ in role and conditioning:

| Role | Tasks | Rollouts | Local success | Program closed | Post-terminal verified | Frozen Replay failures | Historical valid |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Capability | 3 | 24 | 8 | 8 | 8 | 8 | 0 |
| Reachability | 3 | 90 | 16 | 19 | 16 | 0 | 16 |

This contrast remains descriptive. Population, task structure, and condition exposure are
confounded, and the Capability role contains the Replay defect. The audit therefore rejects both
"Stopping capability is zero" and "task structure alone caused the difference."

### Reachability mapping

All 21 frozen valid trajectories remain mapped under the existing Mapper. The audit reproduces the
Mapper from successful pre-calculation tool milestones and reports every Requested/Actual State
pair, route, static path, Decision Trace, content identity, and release status.

The conditioned route result is:

| Requested route | Attempts | Condition adherence | Historical valid | Actual route among valid | On-target valid | Off-target valid |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| `structured_direct` | 72 | 52 | 2 | 2 direct | 2 | 0 |
| `search_then_structured` | 72 | 6 | 6 | 6 direct | 0 | 6 |
| `search_then_open` | 72 | 7 | 8 | 8 direct | 0 | 8 |

Thus all fourteen historical-valid rows requested under a search route actually map to
`structured_direct`. This retains the route-control redesign signal, but route redesign is not the
next executable stage because Verifier repair now precedes it.

Four states have at least one natural or conditioned valid hit:

- two Context `structured_direct` states each have one natural hit and no conditioned On-target
  realization;
- one Stopping `structured_direct` state has one conditioned On-target release and no natural hit;
- one Stopping `structured_direct` state has three natural hits and one conditioned On-target
  release.

Each released state still has only one independent release, two short of the frozen minimum. The
State Support Freeze therefore remains 0/36 states and 0/12 tasks.

## v26.75 Prospective Verifier v2

### Replay contract

The new content-addressed Replay Contract fixes the exact composition boundary:

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

Canonical JSON comparison is required because persisted JSON represents tuple-like payload members
as arrays. Python container-type equality is not an accepted replay criterion.

Verifier v2 uses this Replay result for `runtime_replay_passed` and preserves the remaining nine
frozen checks:

- model-input noninterference;
- allowed-tool closure;
- operation lineage;
- Evidence Support;
- Verification Support;
- Answer Projection;
- Citation Support;
- target mechanism completion;
- no post-completion violation.

It receives a new implementation identity and version:

```text
core.authority_preserving_executable_task_verifier
authority_preserving_executable_task_verifier.v2
```

Future TaskPackages must bind this identity before their own identities are frozen.

### Qualification fixtures

All 45 historical completed trajectories are used only as immutable diagnostic fixtures:

| Check | Result |
| --- | ---: |
| v2 Replay pass | 45 / 45 |
| Non-Replay Gate vector byte/value identity | 45 / 45 |
| Historical Replay pass | 27 / 45 |
| Historical Replay fail, v2 Replay pass | 18 / 45 |
| Prospective v2-valid candidate | 15 / 45 |
| Historical validity reclassification | 0 |
| Historical mapping change | 0 |

Prospective candidates are distributed as:

| Role | Mechanism | Count |
| --- | --- | ---: |
| Capability | State-dependent Stopping | 8 |
| Reachability | Context-conditioned Action | 7 |

The other three Replay-repaired rows retain non-Replay failures: two Capability Reconciliation rows
retain Verification/Citation failures, and one Reachability Context row retains an Operation
lineage failure.

### Destructive mutations

Verifier v2 rejects the complete prospective mutation matrix:

| Mutation | Rejected |
| --- | ---: |
| Environment identity changed | 45 / 45 |
| Recorded result payload changed | 45 / 45 |
| Action-bearing payload injected into an affected failed Observation | 18 / 18 |
| Total | 108 / 108 |

Mutated Observations receive internally valid content-addressed identities before Replay. They are
rejected by the repaired semantic contract, not merely by stale hashes.

## Immutable Outputs

### v26.74

Artifact root:

```text
artifacts/vtdo_experiment/
  finance_v26_74_capability_reachability_failure_audit_v2_20260819/
```

| Artifact | SHA-256 |
| --- | --- |
| `capability_conversion_summaries.json` | `d6ba36121723da0b184aa5644076f04cf625956e6720e03e34ba83fcc62a261f` |
| `capability_failure_diagnostics.json` | `18d4417d53d9f397c4a3bfca462325754c07b1da856fd4295a4048029845ecb7` |
| `reachability_route_summaries.json` | `8af4bdba3005b51a08888aa5ab76da3a456807fb4105a15a3c0223c892f88fd2` |
| `reachability_valid_mapping_diagnostics.json` | `bc41c105bbca0d2527e728392709536a9a5b74a5fcee0fb162c95ea29d92c082` |
| `state_support_diagnostics.json` | `21388e7c7cc5aa8113a79b5fa4a562fd05fd7c0d1259a2782e64c23aa6ecf7d3` |
| `stopping_role_contrast.json` | `50c7c618446cbec75988bc6335e851ed18a28bebe5e652e7d539c6ca457ce20b` |
| `verifier_replay_differentials.json` | `91daeefeeacb5daf4548966cbb614d2ab34d05c9804c4fd851a5593e2f4c6c8b` |
| `report.json` | `1d1206235ef851b38ad7ca1497718af30d991b43b86495064df5b40252087052` |

### v26.75

Artifact root:

```text
artifacts/vtdo_experiment/
  finance_v26_75_authority_preserving_verifier_qualification_v2_20260819/
```

| Artifact | SHA-256 |
| --- | --- |
| `replay_contract.json` | `e2e7acfdc32d601a9dfe85e850ee80d1921211f43f2ebac07881aaa136e12076` |
| `historical_verifier_diagnostics.json` | `039525682aff2e30be848447f2eb4b4230a2632fbde7624d1d5637a683acb9b4` |
| `destructive_mutation_audits.json` | `735ede051319b0038fb3f40d4b2c45b57e2ebebb0540bc729bc9e1c33816ff8e` |
| `report.json` | `8925c151f6cf5383ebb68376e45a16805e70666032f08489a1fef13983117f32` |

Formal and independent builds reproduced every file byte for byte.

## Validation

Focused validation completed before documentation finalization:

| Check | Result |
| --- | ---: |
| v26.74 focused tests | 7 passed |
| v26.75 focused tests | 6 passed |
| Combined focused total | 13 passed |
| Repository-wide Pytest | 964 passed in 597.18 seconds; one expected destructive-test warning |
| Repository-wide Ruff | passed |
| Ruff for new source and tests | passed |
| Mypy for new source and tests | passed |
| Package-wide Mypy | one retained source-bound v26.70 local-list diagnostic |
| v26.74 formal/independent/duplicate builds | byte-identical |
| v26.75 formal/independent/duplicate builds | byte-identical |
| Model API calls | 0 |
| GPU jobs | 0 |

## Interpretation

Supported conclusions:

- Recovery local success usually fails to propagate to Program closure under the current tasks;
- the search-based Public Conditions do not reliably control the frozen Acquisition Route;
- the v1 Verifier Replay omitted authority-preserving public gate and failed-result semantics;
- Capability Stopping's historical zero-valid result is not interpretable as a clean task-support
  result;
- Verifier v2 mirrors Runtime semantics on every completed diagnostic fixture and fails closed
  under the registered mutations;
- fresh v2-bound task identities and a new Instrument qualification are required.

Unsupported conclusions:

- any historical-invalid trajectory is now valid;
- any additional historical trajectory may be mapped or released;
- Capability support is balanced after the repair;
- any state has three independent releases;
- a search route is empirically controllable;
- Confirmation, No-C VTDO, Student training, Exact Target, GP-C, or Contribution is authorized.

## Next Step

Materialize fresh TaskPackages only after binding the v2 Verifier implementation, Replay Contract,
public Operation Contract, action-neutral repair Contract, terminal target, Runtime, and independent
Verifier to the same Semantic Source. All dependent Contract, Job, trajectory, and report identities
must be fresh.

Before any API call, freeze a small balanced Instrument Job Manifest and pass:

- exact v2 Verifier and Replay source binding;
- complete compiler Runtime Witnesses;
- action-neutral repair and private-field isolation;
- wrong environment, changed result, action-bearing repair, wrong/missing/extra terminal reference,
  early verification, and post-completion mutations;
- source and implementation manifest replay;
- an independent byte rebuild.

The fresh Instrument must not reuse the 15 diagnostic candidates as outcomes, Confirmation data, or
state support. A passing static preflight may authorize only a small fresh model Instrument
requalification. Capability Development, State Reachability, Fresh Confirmation, No-C VTDO,
Student training, Exact Target, GP-C, and production Contribution remain forbidden.
