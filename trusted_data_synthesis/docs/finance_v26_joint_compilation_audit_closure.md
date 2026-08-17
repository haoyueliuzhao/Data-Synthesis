# Finance v26 Joint Compilation Audit Closure

Date: 2026-08-17

## Scope

This revision closes the static engineering findings from the independent Joint Compilation and
Compiler-Assisted Bridge audit and materializes the typed Development/Confirmation task roots. It
deliberately does not run a model API, allocate a GPU, claim per-task Joint/Scaffold admission, or
authorize a VTDO/Student experiment.

The implementation is intentionally incompatible with the earlier permissive serialized
contracts. Old admission, scaffold, Bridge, and stage-ledger payloads must be recompiled from their
frozen source artifacts. They are not upgraded by filling default fields.

## Evidence-derived admission

Joint Compilation and Capability Scaffold admission no longer trust caller-provided aggregate
booleans. Each hard check is represented by an `AtomicAuditCaseResult` that binds:

- the exact check and subject identities;
- input and output artifact identities;
- primary and independent replay implementation manifests, their artifact URIs, and SHA-256;
- a canonical result hash and byte-level SHA-256;
- the replay result hash.

The Joint admission embeds the compiled proof-carrying artifacts, state-space compilation,
runtime-specific authority policies, typed verifier/materializer manifests, and all three audit
families. Its gates are re-derived during deserialization. Scaffold admission similarly embeds its
ladder and 28 atomic gate results per ladder and re-derives every level/gate decision.

Changing an outer ID or recomputing an outer hash cannot make a changed atomic result admissible.

## Exact compiled task condition

`compiled_task_condition_id` now binds the effective public condition rather than only a level
label. Its identity includes the Joint/Omega roots, runtime authority policy, base runtime
projection, state-mapping contract, dependency graph, scaffold policy, and a hash of the complete
scaffold payload.

`CompiledTaskConditionLineage` carries this identity through Bridge rollouts and mainline support.
The lineage additionally freezes the projection, ladder, scaffold admission, Joint admission,
Joint Compilation, Omega context/manifest, runtime projection/policy, summary spec, dependency
graph, state mapper, and scaffold level.

## Deterministic scaffold and runtime artifacts

The ladder validator reconstructs all four projections from the admitted Joint root and requires
exact equality. A rehashed projection with a changed Omega root is rejected. `gamma_2` nodes expose
ordered prerequisite node keys; `gamma_3` additionally exposes the public edge list.

The public-state summary is now executable. Ordered public observations are content addressed,
the compiler accepts only registered public source kinds and fields, and the compiled summary
stores its source-observation hash. Deserialization independently recomputes the latest-value
projection. Hidden action, argument, program, Host-event, and Oracle markers remain forbidden.

Runtime projections bind explicit scheduler, tool-selection, repair, stopping, and visible-field
authority policies. Scripted and autonomous runtimes therefore cannot differ only by a string ID.

## Atomic Bridge accounting

Every Bridge cell is derived from exactly 48 immutable rollout observations. Each rollout binds the
exact compiled task condition, optional compiled public summary, terminal category, decision trace,
state assignment, mechanism-specific Estimands, and raw artifact URI/SHA/hash. It also embeds a
content-addressed execution manifest for model invocation parameters, Provider route, Prompt
template, Runtime/Authority, and canonical allowed tools. Credential-like keys are rejected. Unique
Provider Call IDs are part of the raw identity, and the Stage Router independently derives Bridge
API-call counts from them.

Terminal categories are mutually exclusive:

```text
model_valid_trajectory
model_invalid_trajectory
runtime_failure
instrument_failure
```

The capability denominator contains model outcomes only. Runtime and instrument failures are
reported separately, and all categories must sum to 48. The independent aggregator recomputes
counts, Estimands, state diversity, interference, leakage, and failures from the atomic rows.

The six-rollout Bridge remains a boundary experiment. Three-to-five-state support is evaluated only
after mechanism-level freeze and fresh confirmation by the separate State-support Discovery
contract.

## Typed fresh Population boundary

`finance_v26_fresh_task_population.v1` replaces the former arbitrary JSON entry. Every 24-task
Population freezes the protocol, phase, independently generated source Population, deterministic
selection policy, task family and mechanism, target capability, allowed tools, and exact hashes of
the Task Package, Public/Oracle contracts, Evidence Bundle, Public Corpus, and Proof Graph.

The router rejects historical `finance_v25_*` task promotion. Development and Fresh Confirmation
must use distinct source Population identities and disjoint task IDs. Joint Compilation must then
reproduce every frozen semantic root before any admission can proceed. Scaffold target capability,
static authorization grouping, and rollout `mechanism_id` are checked against the same Population.

Two real no-API source compilations were produced from the frozen 420-record public financial
Evidence archive. Each contains 70 structurally admitted tasks. They yielded 24 Development and 24
Fresh Confirmation tasks with exact 8/8/8 mechanism quotas and zero task overlap.

## Fail-closed stage router

`finance_v26_stage_router.v4` and the top-level CLI now enforce this ordered artifact chain:

```text
Fresh Development Population
Joint Compilation
Joint Atomic Audit
Joint Admission
Scaffold Compilation
Scaffold Atomic Audit
Scaffold Admission
Bridge Development Static Authorization
Bridge Development Rollouts
Bridge Development Aggregation
Bridge Support Freeze
Fresh Confirmation Population
Fresh Confirmation Complete Compilation/Audit/Admission
Bridge Confirmation Authorization
Bridge Confirmation Rollouts
Bridge Confirmation Aggregation
Bridge Confirmation
State-support Contract
State-support Observations
State-support Freeze
```

Protocol and preflight references are typed and independently replayed on every transition and
on direct ledger deserialization. Deserialization also replays all completed-stage file hashes,
typed roles, cardinalities, and cross-stage identities. Audit cardinality is derived from
population size: three Joint audit records per compiled task and 28
Scaffold gate records per ladder. The router checks exact cross-stage identities, fresh-task
disjointness, six-replicate coverage, authorization IDs, atomic rollout partitioning, and embedded
freeze inputs.

Only rollout stages may report model API calls. This pre-training router rejects all GPU jobs;
training receives a separate post-State-support-freeze route. No skipped or reordered stage is
accepted.

CLI entry points:

```text
trusted-synthesis v26-build-fresh-population
trusted-synthesis v26-stage-init
trusted-synthesis v26-stage-advance
trusted-synthesis v26-stage-status
```

## Regression boundary

The focused v26 suite contains 55 passing tests; the full repository suite contains 817. It
includes negative cases for forged aggregate
gates, changed atomic result payloads, detached state/Omega roots, scaffold payload drift, cyclic
prerequisites, unknown public fields, incomplete atomic rollout sets, forged denominators, raw
rollout tampering, changed mainline task conditions, duplicate trajectory content, and stage
reordering/content mutation.


## Audit finding disposition

| Audit finding | Current disposition |
| --- | --- |
| P0-1 Joint gates caller-derived | Closed: deserialization re-derives gates from atomic Evidence |
| P0-2 Scaffold gates caller-derived | Closed: all 28 level/gate results are re-derived |
| P0-3 condition ID omitted scaffold content | Closed: complete payload and executable lineage are bound |
| P0-4 detached Omega projection | Closed: deterministic four-level recompilation rejects drift |
| P0-5 no executable v26 entry | Partially closed: typed Population builder and Stage Router run; per-task producer/audit execution remains next |
| P0-6 six-rollout three-state conflict | Closed: occupancy moved to independent State-support Discovery |
| Boolean-only audit tables | Closed at schema/replay boundary; real 24-task audits are not yet executed |
| String-only verifier/materializer | Closed: typed executable manifests and independent replay cases |
| Runtime projection not runtime-specific | Closed: scheduler/tool/repair/stop authority is explicit |
| `gamma_2` prerequisites absent | Closed: prerequisite node keys are public and ordered |
| Public summary compiler absent | Closed: deterministic compiler and replayable summary artifact |
| Generic Bridge Estimand | Closed: five mechanism-specific Bernoulli Estimands |
| Withdrawal naming | Closed: static readiness separated from post-training transfer |
| Minimality naming | Closed: incremental necessity plus mechanism-level minimum passing level |
| Aggregate-only Bridge lineage | Closed: 48 atomic rollout records per cell |
| Bridge denominator leak | Closed: mutually exclusive terminal categories and model-only denominator |
| Scaffold-invariant mapping absent | Closed: behavior canonicalization and scaffold audit side channel |
| Mainline omitted exact `x_tilde` | Closed: complete `CompiledTaskConditionLineage` and trajectory hash |
| Fresh Confirmation absent | Contract and disjoint Population closed; empirical execution remains blocked |
| State-support discovery absent | Typed contract/router closed; empirical observations remain blocked |

A fresh immutable static preflight now freezes this implementation:

```text
artifact directory = artifacts/vtdo_experiment/
                     finance_v26_0_capability_heterogeneous_mainline_protocol_v10_20260817/
protocol_id        = finance_v26_capability_heterogeneous_vtdo_mainline:
                     d1323269e4ec89773d104a4f72d6292b9449b9404d5bcb4fe65976e12b824407
preflight_id       = finance_v26_mainline_preflight:
                     df410a0c3bb1b4e63313fce7c61c55f5cd03a5a08ad5c2dbf69dfc80cdea3602
preflight checks   = 24/24 passed
implementation files frozen = 14
stage ledger       = finance_v26_stage_ledger:
                     f491186f902c4f3df065e0e13e0d9a988e8d8fcd2e13c3fe65d9fd2ea7e5da8f
completed stage    = fresh_task_population
next stage         = joint_compilation
API calls / GPU jobs = 0 / 0
```

The static chain is now executable and fail-closed, but empirical authorization remains unchanged:

```text
v26 Development Population: 24 typed tasks, materialized
v26 Fresh Confirmation Population: 24 typed tasks, reserved and disjoint
per-task Joint/Scaffold admission: absent
Bridge API calls: 0
GPU jobs: 0
State-support freeze: absent
No-C VTDO: blocked
Student training: blocked
Contribution: 0 and unauthorized
```

The Development Population has crossed the first Stage Router step. The next permitted operation
is exact per-task Joint Compilation followed by atomic Joint and Scaffold audits. API credentials
must not be instantiated before Scaffold Admission.
