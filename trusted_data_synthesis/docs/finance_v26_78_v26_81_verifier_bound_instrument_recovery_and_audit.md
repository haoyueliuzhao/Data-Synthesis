# Finance v26.78-v26.81 Verifier-Bound Instrument Execution, Recovery, And Audit

Audit date: 2026-08-20

## Scope

This report records the only online experiment authorized by the v26.77 preflight, the failed
first execution, the zero-generation recovery protocol, the completed recovered denominator, and
the credential-free post-run failure audit.

The scientific boundaries are unchanged:

- the frozen denominator is the exact v26.77 32-job Instrument Manifest;
- the role is Instrument requalification, not Capability Development or State Reachability;
- all invalid model outcomes remain in the denominator;
- Compiler Witnesses contribute zero empirical rows;
- no historical v26.71 or v26.72 result is rescored;
- no State Mapping or release is created;
- Capability Development, State Reachability, Confirmation, No-C VTDO, Student training,
  Exact Target, GP-C, and Contribution remain forbidden.

## Frozen Inputs

The execution retained the v26.77 identities:

```text
Task Population report
  finance_v26_verifier_bound_instrument_population_report:
  4c810296a03f0491d60b20d6e74061a269e70eb35f8054cfa34eb34ea5547cb0

Instrument preflight report
  finance_v26_verifier_bound_instrument_preflight:
  d8c88785a217da74a6772a51a658ff7a0ee40ee77d3a11ebe5454f795721b263

Instrument Contract
  finance_v26_verifier_bound_instrument_contract:
  3ecdc9bff3a2a846ede932c28763abbac1c67c345553eacfec69b2de0985afda

Job Manifest
  finance_v26_verifier_bound_instrument_manifest:
  300bc703e726e04bbf22138a01bf8e09302a54906be8e7510ffa012d7256e724
```

The Manifest contains four mechanisms, two fresh tasks per mechanism, and four unconditional
replicas per task. It requests exact `deepseek-v4-flash`, has no fallback, permits at most 120,000
provider-reported tokens per rollout, and sets a USD 2.00 aggregate estimated-cost ceiling.

## v26.78 First Execution Failure

v26.78 prepared a source-bound online Runner and began the exact 32-job Manifest with 16 workers.
Every Provider response was written before Agent contract validation. The first worker reaching
post-Provider assembly then failed at this comparison:

```text
raw Provider telemetry == Host Agent failure telemetry
```

The comparison was too strong. The raw Provider telemetry correctly lacked
`response_shape.prompt_component_bytes`; the Iterative Agent added that Host-computed field after
the Provider returned. All other telemetry fields, Prompts, response payloads, and call ordering
were equal.

The execution failed closed with the following immutable inventory:

| Item | v26.78 result |
| --- | ---: |
| Frozen Jobs | 32 |
| Jobs exposed to the model | 17 |
| Jobs never opened | 15 |
| Raw Provider call Artifacts | 146 |
| HTTP-success calls | 146 |
| JSON-contract-success calls | 146 |
| Provider-reported tokens | 1,336,075 |
| Estimated cost telemetry | USD 0.168894560800000016264 |
| Raw Execution Artifacts | 0 |
| Rollout checkpoint rows | 0 |
| Repeated Jobs | 0 |

The failed execution binding is:

```text
finance_v26_verifier_bound_instrument_execution_binding:
27250c6b577243a7c87f321c72877dd7ff3ccfaa0d5ea48a92d7a6db6eda2ae2
```

The failed Runner and all v26.78 files are retained unchanged. The absence of Raw Execution and
Rollout rows means v26.78 is an Instrument execution failure, not a 17-row empirical result.

## Zero-Generation Root-Cause Replay

A credential-free replay consumed every stored response payload in the exact saved order. It
reconstructed the original Agent interaction locally and required exact Prompt equality before
each response was supplied.

The replay established:

| Check | Result |
| --- | ---: |
| Exposed Job streams consumed exactly | 17/17 |
| Provider calls consumed exactly | 146/146 |
| Prompt equality | 146/146 |
| Telemetry equality before Host augmentation | 146/146 |
| Reconstructed completed trajectories | 5 |
| Reconstructed model-contract failures | 12 |
| Reconstructed Observations | 118 |
| API calls | 0 |
| GPU jobs | 0 |

The 17/15 partition was determined only by immutable raw Artifact presence. No model outcome,
mechanism result, or prospective validity entered the partition.

## v26.79 Recovery Preflight

v26.79 froze a new Recovery Contract, Manifest, and execution binding. The Contract imposes two
different authorities:

- the 17 exposed Jobs are `zero_generation_replay` and model calls are forbidden;
- the 15 unopened Jobs are `unopened_model_continuation` and may execute exactly once.

The comparison rule is now explicit:

```text
provider_fields_equal_before_prompt_component_bytes_augmentation
```

The formal preflight replayed 73 source and failed-run files, all 146 Provider Artifacts, and all
17 exposed Job streams before any client construction. It recorded zero API calls and zero GPU
jobs. Formal and independent builds reproduced all eight output files byte for byte.

Authoritative identities:

```text
Recovery preflight
  finance_v26_verifier_bound_recovery_preflight:
  a25d500a2ea292f2274b7b1e305d4f5bfadc9b82b8ebaa0ee59474368aff8ccc

Failed-run audit
  finance_v26_verifier_bound_failed_run_audit:
  5bbd4fd482dbef78e5a17075011e2049e4fe7289120f5a3dcbb645078689c9b1

Recovery Contract
  finance_v26_verifier_bound_recovery_contract:
  4dc98e9c6f48d101439695eb38742d8c7779ce3293bdac33fc033b12f152f4c5

Recovery Manifest
  finance_v26_verifier_bound_recovery_manifest:
  55acc0b301c3a6a653470cc77f614ef92851b2e887f3e070031a1eee9fe44cef

Recovery execution binding
  finance_v26_verifier_bound_recovery_execution_binding:
  04a9e19cbd132be2c6bf07f333e782a6f5499f84694eae349cbf7f34898a6ac6
```

## v26.80 Recovered Denominator

v26.80 first reconstructed and scored the 17 exposed Jobs without constructing a model client.
It then executed only the exact 15 unopened Jobs with 15 workers. Every Provider payload was
persisted before Agent parsing, and every Raw Execution was persisted before Verifier scoring.

### Execution and cost

| Item | Original v26.78 stream | v26.80 continuation | Combined |
| --- | ---: | ---: | ---: |
| Jobs | 17 | 15 | 32 |
| Provider calls | 146 | 123 | 269 |
| Provider-reported tokens | 1,336,075 | 1,247,381 | 2,583,456 |
| Estimated cost telemetry | 0.168894560800000016264 | 0.140205408000000015860 | 0.309099968800000032124 |

All 32 Jobs used exact `deepseek-v4-flash`; fallback count was zero; Runtime failure count was
zero; Provider usage telemetry was complete; and all 269 Provider call identities were unique.
No GPU was used.

The original 146 Provider files retain the v26.78 capture binding and are copied byte for byte.
The 123 new Provider files carry the v26.80 Recovery binding. All 32 Raw Execution Artifacts carry
the Recovery binding. This preserves capture provenance while placing the complete denominator
under one fresh scoring identity.

### Frozen v26.80 result

The v26.80 aggregate failed closed:

| Instrument field | Frozen result |
| --- | ---: |
| Completed classifications | 32/32 |
| Verifier v2 Replay passes | 32/32 |
| Frozen model-invalid trajectories | 25 |
| Frozen Instrument failures | 7 |
| Frozen model-valid trajectories | 0 |
| Runtime failures | 0 |
| Exact-model rows | 32/32 |
| Strict resource budget | failed |
| Instrument ready | false |
| Status | blocked |

The authoritative Recovery report is:

```text
finance_v26_verifier_bound_instrument_recovery:
645531ad63c93055f9a29f6a179e6bce16a65441ea7facca4f2d7e8381e52a67
```

Its nested frozen Instrument result is:

```text
finance_v26_verifier_bound_instrument_requalification:
6a2fd18fdda1e384686d3631316cbb5da809ac3bbef56c79db41caad50886275
```

The frozen transition is `resource_budget_audit_only`. The report is not rewritten by the later
audit.

## v26.81 Independent Post-Run Audit

v26.81 replayed 19 implementation files and 477 immutable experiment files, 496 files total. It
replayed all 32 Raw Executions through Verifier v2 and rebuilt the scoring, resource, and raw
lineage diagnostics without an API call or GPU job. Formal and independent builds reproduced all
five output files byte for byte.

### Completed-trace scoring defect

All seven v26.80 Instrument failures were completed trajectories. Their Verifier v2 Replay and
independently rebuilt non-Replay Gate vectors pass. They failed later while constructing a
descriptive decision-trace hash:

```text
AttributeError: 'TrajectoryStep' object has no attribute 'observation_id'
```

`TrajectoryStep` contains `observation`, not `observation_id`. The decision-trace hash is not a
Verifier Gate, but the exception was caught by the scoring failure wrapper and classified the
entire row as `instrument_failure`.

A diagnostic-only reconstruction used existing schema-valid fields and produced:

| Item | Diagnostic count |
| --- | ---: |
| Completed trajectories | 7 |
| Captured model-contract failures | 25 |
| Prospective model outcomes after only the hash-field repair | 32 |
| Prospective valid trajectories | 6 |
| Prospective invalid trajectories | 26 |
| Prospective Runtime failures | 0 |
| Prospective Instrument failures | 0 |

The six prospective valid candidates comprise two Context-conditioned Action rows and four
State-dependent Stopping rows. The remaining completed Semantic Reconciliation row is
prospectively invalid. These are diagnostic candidates only. Historical v26.80 terminal classes,
validity counts, and report identities remain unchanged.

### Independent strict resource failure

The USD 2.00 aggregate cost ceiling passed, but the per-rollout 120,000-token ceiling failed for
five Jobs:

| Mechanism | Pre-final total | Final call | Total | Overshoot |
| --- | ---: | ---: | ---: | ---: |
| Context-conditioned Action | 109,482 | 15,055 | 124,537 | 4,537 |
| Context-conditioned Action | 107,834 | 14,918 | 122,752 | 2,752 |
| Context-conditioned Action | 108,869 | 15,187 | 124,056 | 4,056 |
| State-dependent Stopping | 119,829 | 13,134 | 132,963 | 12,963 |
| Context-conditioned Action | 109,601 | 15,116 | 124,717 | 4,717 |

The Runtime checks cumulative Provider tokens after a response. The frozen profile reserves zero
tokens for contract repair and final answer, and it has no certified pre-call upper bound for the
next Provider-reported token count. Each crossing was correctly stopped after its final response,
but the consumed total had already exceeded the strict experiment ceiling.

This resource failure is independent of the seven scoring exceptions. Therefore the six
prospective validity candidates cannot rescue Instrument admission.

### Raw-lineage separation

The independent lineage-only audit passed:

| Check | Result |
| --- | ---: |
| Raw Executions under Recovery binding | 32/32 |
| Zero-generation / continuation Jobs | 17 / 15 |
| Exposed Job model calls | 0 |
| Original Provider exact-byte matches | 146/146 |
| Provider binding checks | 269/269 |
| Provider telemetry checks before Host augmentation | 269/269 |
| Unique Provider call identities | 269/269 |

The frozen v26.80 raw-lineage object reports `failed` because its `failed_artifacts` list also
received the seven independent non-Replay Gate audit failures caused by scoring. That is an
aggregation-coupling defect. It is not evidence of a raw capture, identity, or Replay-lineage
breach. The frozen object remains unchanged.

The authoritative v26.81 report is:

```text
finance_v26_verifier_bound_postrun_audit:
eb7316f9b5e9dcd09013bf3662da64b5f8290f02f1a9e966e3a0268f92d87297
```

## Scientific Decision

The final status is negative:

```text
verifier_v2_replay_passed = true
raw_lineage_only_passed = true
completed_trace_scoring_defect_observed = true
strict_resource_budget_passed = false
instrument_requalification_passed = false
historical_outcomes_reclassified = false
capability_development_execution_authorized = false
state_reachability_execution_authorized = false
production_contribution = 0
```

The only permitted transition is:

```text
fresh_budget_closed_verifier_bound_task_rematerialization_and_instrument_preflight_only
```

A successor must use fresh TaskPackage, Contract, Manifest, Job, execution, trajectory, and report
identities. All eight v26.76 tasks and all 32 Jobs are now empirically exposed and cannot be reused
for a new requalification.

Before any new API call, the successor must:

1. construct the descriptive trace hash only from fields present in the frozen Trajectory schema;
2. execute complete Compiler trajectories through the same scoring path, not only Verifier Replay;
3. separate raw-lineage failures from downstream Instrument Gate failures;
4. enforce a certified pre-call upper bound so the next Provider response cannot cross the
   120,000-token ceiling;
5. define a typed no-call budget terminal when the certified bound does not fit;
6. reject exact-boundary, one-token-over, changed-usage, missing-usage, and oversized-Prompt
   mutations;
7. rematerialize a fresh balanced eight-task Instrument Population after the repaired Runtime and
   scorer are content-bound;
8. reproduce the complete static preflight byte for byte independently.

A passing static successor may authorize only another small fresh Instrument requalification.
Capability Development and State Reachability execution remain forbidden.

## Authoritative Artifacts

- `artifacts/vtdo_experiment/finance_v26_78_verifier_bound_instrument_requalification_20260820/`
- `artifacts/vtdo_experiment/finance_v26_79_verifier_bound_recovery_preflight_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_80_verifier_bound_instrument_recovery_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_81_verifier_bound_postrun_audit_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_81_verifier_bound_postrun_audit_20260820/completed_trace_scoring_audit.json`
- `artifacts/vtdo_experiment/finance_v26_81_verifier_bound_postrun_audit_20260820/resource_budget_audit.json`
- `artifacts/vtdo_experiment/finance_v26_81_verifier_bound_postrun_audit_20260820/raw_lineage_independent_audit.json`
