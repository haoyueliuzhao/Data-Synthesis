# Finance v25.25 Flash Submechanism Development

## 1. Purpose

v25.24 selected 20 structurally independent submechanisms but did not yet have an
executable Runtime population. v25.25 implements all selected Host interventions,
materializes fresh real-Finance tasks, and evaluates whether Flash responses preserve
the preregistered structural geometry.

The primary response is frozen as `valid_success`. Tool, verification, recovery, and
stopping responses are diagnostics only and cannot rescue a failed primary matrix.

## 2. Instrument implementation

The experiment adds:

- 20 typed Host intervention policies with immutable trigger and resolution events;
- scenario-specific Runtime snapshot identities;
- a submechanism-only typed output extension for Host resolution reports;
- Oracle-derived reconstruction of the exact Runtime during independent replay;
- failed-trajectory behavior analysis using the retained Host observation artifact;
- one real-Finance task per submechanism, with disjoint Evidence and passing static
  operation, Host replay, wrong-branch, and public/Oracle isolation gates;
- a Flash-only, 20-task, three-replica Development contract;
- primary and four diagnostic response-weighted geometry reports.

The base Finance toolset is not loosened. The optional
`submechanism_resolution` output is registered only in the scenario-specific
submechanism manifest.

## 3. Immutable v1 instrument failure

The first 60-rollout run is retained as an invalid-instrument artifact. It exposed
three defects:

1. failed model trajectories stored Host observations in the typed failure artifact,
   while the behavior analyzer read only completed-record observations;
2. the independent verifier replayed observations with the base Finance Runtime
   instead of the Oracle-frozen submechanism Runtime;
3. successful Host resolution results used an unregistered optional output field.

A read-only reanalysis recovers 44 trigger events from v1, whereas its old report
recorded zero. Resolution events could not be persisted because the old output
contract rejected the result before observation construction. No model or capability
claim is drawn from v1.

## 4. v2 validation

Before any new API call:

- focused Runtime/verifier/boundary tests: 36 passed;
- full Ruff: passed;
- full Mypy: 297 source files passed;
- full Pytest: 609 passed in 143.99 seconds;
- all 20 frozen contexts reconstructed the scenario-specific Runtime and typed tool
  manifest successfully.

The v2 contract froze 20 tasks, 20 bindings, 60 rollout identities, the Flash model
contract, all source hashes, and 11 implementation source hashes.

## 5. v2 result

The 60-rollout run used 12 workers and completed without API or Runtime pathology:

| Metric | Result |
| --- | ---: |
| Recorded rollouts | 60/60 |
| Runtime-eligible rollouts | 60/60 |
| Complete task denominator | 20/20 |
| API transport resolution | 100% |
| Bounded JSON resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Runtime pathology | 0% |
| Host trigger observed | 50/60 |
| Ordered Host resolution | 31/60 |
| Completed trajectories | 28/60 |
| Primary valid success | 0/60 |

All 32 failed records were attributed to model decision behavior: 26 exhausted the
frozen failed-tool budget and six exhausted the model-token budget. The 28 completed
trajectories reached deterministic verification but failed the final semantic answer
contract. The dominant verifier failures were answer correctness, complete operation
lineage, complete verification support, and exact Gold citation coverage.

The primary response is therefore saturated:

| Geometry metric | Result | Requirement |
| --- | ---: | ---: |
| Nonzero-weight tasks | 0 | >= 5 |
| Boundary task fraction | 0 | >= 0.25 |
| Residual rank | 0 | >= 4 |
| Residual effective rank | 0 | >= 3 |
| Informative axes | 0 | >= 4 |

Diagnostic behavior remains informative but cannot alter the decision. Recovery
occurred in 31/60 rollouts. Verification and stopping each had eight nonzero-weight
tasks and residual numerical rank 6, but effective rank was only 2.7567 and the
condition number was about 2052.8.

## 6. Interpretation and transition

The v25.24 structural direction design remains valid, and v25.25 establishes a
reliable executable measurement instrument. It does not establish a
capability-informative primary task distribution. Every materialized base task used
the Frontier tier: three or four Gold facts and a three-node operation DAG. The
submechanism intervention was layered on top of that workload, causing Flash
`valid_success` to saturate at zero.

The fail-closed state is:

```text
runtime_measurement_ready = true
primary_information_geometry_ready = false
fresh_submechanism_confirmation_authorized = false
pro_api_calls = 0
beneficiary_screening_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = submechanism_task_redesign_only
```

The next permitted experiment is a separately identified Development population with
fresh, disjoint Evidence and a preregistered lower base workload. It must preserve the
same 20 submechanisms, primary response, geometry thresholds, and scientific blocks.
The v2 outcomes cannot be subset or reweighted post hoc.

## 7. Cost and artifacts

The v2 run made 585 API calls and recorded 2,616,938 model tokens. The provider
telemetry estimate is USD 0.280398; it is reported as telemetry, not treated as a
billing statement.

Authoritative artifacts:

- Contract:
  `artifacts/vtdo_experiment/finance_v25_25_submechanism_flash_development_contract_v2_20260814/`
- Run:
  `artifacts/vtdo_experiment/finance_v25_25_submechanism_flash_development_v2_20260814/`
- Contract ID:
  `finance_capability_submechanism_flash_contract:5fc434104c1d1df6ac5927e0a08640e348c4cfc15c5072975b53eea42ab5b1a6`
- Report ID:
  `finance_capability_submechanism_flash_report:8a05f9f8660c6c83469ce0639ace7e47629e692ef4f7cfc0e53434f3fdcfa8d2`
