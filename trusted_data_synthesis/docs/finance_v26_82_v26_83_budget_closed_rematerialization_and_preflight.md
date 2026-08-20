# Finance v26.82-v26.83 Budget-Closed Rematerialization And Preflight

Audit date: 2026-08-20

## Scope

This report records the only transition authorized by the v26.81 post-run audit. It repairs the
completed-trajectory scoring path and Provider-token resource contract under fresh source
identities, materializes a fully fresh eight-task Instrument Population, and freezes a new
32-job Instrument-only Contract and Job Manifest.

Both stages are credential-free static work:

- model API calls: 0;
- GPU jobs: 0;
- model-generated trajectories: 0;
- empirical Instrument rows: 0;
- Capability Development and State Reachability rows: 0.

The v26.78-v26.80 Jobs and all eight v26.76 TaskPackages remain immutable and exposed. The six
v26.81 prospective-valid candidates remain diagnostic only. They did not enter selection,
Capability support, State Mapping, release counts, or any v26.82-v26.83 denominator.

## Audit Requirements

The v26.81 audit required four prospective changes before another online Instrument attempt:

1. completed trajectories must be scored using only fields in the current `TrajectoryStep`
   schema;
2. complete Compiler trajectories must traverse the same post-Replay scoring path as future
   model trajectories;
3. raw-lineage, Replay, core scoring, diagnostic sidecar, resource, and aggregation failures must
   remain separate;
4. every token-bearing Provider request must receive a conservative pre-call upper-bound
   certificate, with a typed no-call terminal when the request cannot fit inside 120,000 tokens.

The successor must also use fresh TaskPackage, Contract, Manifest, Job, execution, trajectory,
and report identities. It cannot reuse an empirical task exposed by v26.78-v26.80.

## Prospective Implementation

### Schema-closed completed scoring

The new scorer binds the current twelve-field `TrajectoryStep` schema:

```text
step_index
action
tool_name
tool_input
observation
evidence_ids
program_node_id
operator_id
input_refs
output_ref
rationale_summary
status
```

There is no `observation_id` field. The descriptive sidecar uses the established
`trajectory_decision_trace_hash()` implementation and a schema hash over the exact field list.
The trajectory content identity is computed from the schema-validated JSON representation, not
from Python object string representations. Consequently, an in-memory Compiler trajectory and
the same trajectory reloaded from JSON reproduce the same content identity.

The scoring order is frozen:

```text
Verifier v2 Replay
  -> independently computed non-Replay Gate vector
  -> core terminal classification
  -> schema-closed descriptive trace sidecar
  -> Instrument/report admission
```

The core terminal is one of `valid_trajectory`, `invalid_trajectory`, or `instrument_failure` and
is frozen before the descriptive sidecar. A sidecar exception cannot convert a valid trajectory
to an invalid trajectory or alter raw lineage. It does block report completeness and therefore
blocks Instrument admission.

### Failure namespaces

The successor separates seven content-addressed channels:

| Channel | Prefix |
| --- | --- |
| Raw lineage | `raw_lineage:` |
| Raw Provider capture | `provider_capture:` |
| Runtime/Verifier Replay | `runtime_replay:` |
| Core scoring | `scoring_core:` |
| Diagnostic sidecar | `diagnostic_sidecar:` |
| Resource budget | `resource_budget:` |
| Report aggregation | `report_aggregation:` |

Cross-channel contamination, duplicate failure identities, and noncanonical ordering fail model
validation. In particular, downstream scoring failures cannot make a passing raw-lineage audit
report `failed`, which repairs the interpretation coupling found in v26.81.

### Certified pre-call Provider bound

The frozen Provider-token Contract is:

```text
Provider                                  deepseek
Model                                     deepseek-v4-flash
Fallback                                  forbidden
Maximum model attempts per client call    1
Maximum rollout Provider tokens            120,000
Maximum Prompt UTF-8 bytes                  60,000
Maximum completion tokens per request       4,096
Provider chat-envelope upper bound             256
Contract-repair reserve                      4,096
Final-answer reserve                         4,096
```

For each request, before the underlying client is called, the Host computes:

```text
prompt_upper  = len(prompt.encode("utf-8")) + 256
request_upper = prompt_upper + 4,096
projected     = cumulative_provider_usage + request_upper + required_reserves
```

The UTF-8 byte count is a conservative content-token bound; the additional 256-token allowance
is the frozen Provider-specific chat-envelope bound for the one-user-message request shape. This
is a protocol upper-bound algorithm, not an exact tokenizer estimate. The online experiment must
still compare every successful Provider response against the certificate.

Reserve policy is request dependent:

| Request | Repair reserve | Final reserve |
| --- | ---: | ---: |
| Plan, decision, scripted tool, or unknown | 4,096 | 4,096 |
| Final answer | 4,096 | 0 |
| Repair of a non-final request | 0 | 4,096 |
| Repair of a final request | 0 | 0 |

The call is forbidden if the Prompt itself exceeds 60,000 bytes, if the request upper bound does
not fit, or if a required repair/final reserve does not fit. Denial creates a content-addressed
`budget_exhausted_no_call` terminal before Provider invocation. That terminal remains in the Job
denominator as a model-invalid resource terminal and is not an Instrument failure.

Every HTTP-success response must provide Prompt, completion, and total usage. The Prompt plus
completion sum must equal total usage; Prompt, completion, request, and rollout bounds must all
hold; and cache-hit plus cache-miss Prompt tokens must equal Prompt tokens whenever either cache
partition is present. The inherited v26.58 policy continues to count an HTTP-unsuccessful attempt
as zero Provider tokens while retaining its raw failure telemetry.

## v26.82 Fresh Population

### Source capacity and selection

The first capacity probe used the three still-available source Populations from the v26.76 design
and failed before writing an output because it could not supply two fresh Failure Recovery tasks.
No quota or freshness gate was relaxed. The final prospective source pool added the unopened,
zero-API v26.36 Confirmation source and retained the same fixed selection policy.

The final source set contains four frozen source Populations:

- v26.42 Development source;
- v26.42 Confirmation source;
- v26.40 Confirmation source;
- v26.36 Confirmation source.

Selection used only task structure, source grounding, freshness identities, and the fixed salt
`finance_v26_82_budget_closed_verifier_bound_instrument_population_v1`. No historical model
outcome or v26.81 diagnostic candidate was consulted.

After the exposure receipt and all historical exclusions, Reconciliation capacity was:

| Item | Count |
| --- | ---: |
| Source Evidence | 151,114 |
| Exposure-excluded Evidence | 26,290 |
| Additional historical/freshness exclusions | 579 |
| Eligible Evidence | 124,284 |
| Eligible Definition pairs | 4 |
| Eligible Reconciliation-task capacity | 2 |
| Selected Definition pairs | 4 |
| Selected Reconciliation tasks | 2 |

The exact capacity is sufficient for the frozen two-task quota and leaves no unused eligible
Definition pair under this exclusion set.

### Eight-channel freshness

The final eight TaskPackages have zero overlap against the v26.42 Development and v26.56,
v26.65, v26.69, and v26.76 empirical inputs:

| Channel | Prior | Selected | Overlap |
| --- | ---: | ---: | ---: |
| Source task artifact | 76 | 6 | 0 |
| Source semantic signature | 75 | 6 | 0 |
| Source task hash | 75 | 6 | 0 |
| Evidence | 541 | 46 | 0 |
| Evidence Version | 541 | 46 | 0 |
| Source record | 541 | 46 | 0 |
| Semantic Source | 68 | 8 | 0 |
| TaskPackage | 68 | 8 | 0 |

All eight v26.76 TaskPackage identities were explicitly excluded. The resulting Population is
balanced at two tasks for each of Context-conditioned Action, Semantic Reconciliation, Failure
Recovery, and State-dependent Stopping.

### Compiler qualification

Every fresh task binds the qualified Verifier v2 Replay Contract, Semantic Source, Public
Operation, action-neutral Repair, typed terminal target, Runtime, Stop Readiness, Answer
Projection, Evidence Support, Citation, Mechanism Contract, Program DAG, Verifier DAG, and tool
Environment before TaskPackage identity freeze.

The static result is:

| Check | Result |
| --- | ---: |
| Fresh TaskPackages | 8/8 |
| Compiler Runtime Witnesses | 8/8 |
| Verifier v2 Compiler Replays | 8/8 |
| Shared completed-score passes | 8/8 |
| Schema-closed trace-sidecar passes | 8/8 |
| Compiler Observations | 80 |
| Operation Closure | 8/8 |
| Mechanism Necessity | 8/8 |
| Operational admission | 8/8 |
| Legacy Operation mutations rejected | 64/64 |
| Authority/terminal mutations rejected | 40/40 |
| Compiler empirical rows | 0 |

The authoritative v26.82 report is:

```text
finance_v26_budget_closed_verifier_bound_instrument_population_report:
9f60f8d7c7522a1fd934bb5a7cdfefb2c91becc73f7e68b2f815dea352ad6484
```

Its Provider-token Contract is:

```text
provider_token_budget_contract:
27e7e524cb3139b9dd29b1ca7f2c7eae1956c96af8a982524f814b3ef4415150
```

v26.82 writes eighteen detail files plus the report. A separate build from the frozen inputs
reproduced all nineteen files byte for byte.

## v26.83 Instrument Preflight

v26.83 replays the complete v26.82 task source, the qualified Verifier v2 source, current
implementation bytes, and six historical Job Manifests before any model client construction.
The source replay passed 67/67 files.

It independently reconstructs all eight Compiler trajectories from Task records, Environments,
Witnesses, and Observations, then runs Verifier v2 and the shared completed-trajectory scorer. The
frozen and reconstructed trajectory identities and completed-score identities agree for 8/8
tasks. All 80 Compiler Observations remain fixtures and contribute zero empirical rows.

### Frozen 32-Job design

The Manifest contains:

```text
4 mechanisms x 2 fresh tasks x 4 unconditional replicas = 32 Jobs
```

All 32 Job identities are fresh. The recursive historical audit found 584 Job or Recovery-Job
identities across the v26.63, v26.66, v26.71, v26.72, v26.77, and v26.79 Manifests and found zero
overlap. Raw-first Prompt/Provider paths also have zero collision.

The Contract freezes exact `deepseek-v4-flash`, no fallback, one model attempt per client call,
the existing Host-instrumented route, 4,096 maximum output tokens, the pre-call budget Contract,
a USD 2.00 aggregate estimated-cost ceiling, Verifier v2, schema-closed completed scoring, strict
failure namespaces, raw-first telemetry, and retention of invalid model outcomes.

### Destructive mutations

All static mutation families failed closed:

| Mutation family | Rejected |
| --- | ---: |
| Wrong Environment Replay | 8/8 |
| Changed-result Replay | 8/8 |
| Action-bearing failed-result Replay | 8/8 |
| Exact boundary positive control | 1/1 allowed |
| One token over | 1/1 typed no-call |
| Changed successful Usage | 1/1 budget Contract failure |
| Missing successful Usage | 1/1 budget Contract failure |
| Oversized Prompt | 1/1 typed no-call |
| Missing final reserve | 1/1 typed no-call |
| Missing repair reserve | 1/1 typed no-call |
| Legacy `observation_id` sidecar access | 1/1 report blocked, core retained |
| TrajectoryStep schema mutation | 1/1 rejected |
| Failure-namespace cross-contamination | 1/1 rejected |

The four typed no-call cases made zero Provider calls. The changed- and missing-Usage cases each
used one fixture response and then permanently failed the budget Contract. The exact-boundary
positive control made exactly one allowed fixture call.

The legacy sidecar mutation preserves the already-frozen `valid_trajectory` core terminal and
passing raw lineage while making report completeness false. This is the prospective behavior
required by the v26.81 diagnosis; it does not reclassify any v26.80 row.

### Reproducibility and identities

v26.83 writes nine detail files plus the report. A separate build replayed the same source and
reproduced all ten files byte for byte. The focused implementation, deterministic-build, mutation,
and authorization suite passed 11/11 tests.

The initial zero-API v1 builds remain immutable. Package-wide Mypy subsequently found that the
budget Usage implementation relied on boolean aliases to narrow optional telemetry fields; the
focused file invocation had accepted the same code, but package-wide analysis did not. The v2
successor caches those telemetry fields in local variables before applying the identical checks.
No condition, serialized budget value, selected task, Witness, mutation, or scientific count
changed.

All eighteen v26.82 detail files are byte-identical between v1 and v2; only the source-bound report
changed. Six v26.83 scientific audit files are byte-identical between v1 and v2; only source
replay, Contract, Job Manifest, and report identities changed to bind the type-complete source and
the v2 task report. The v2 reports below are authoritative.

Repository-wide validation on the final v2 source passed Ruff. Mypy checked 378 source files and
retained only the pre-existing v26.70 local-list annotation diagnostic whose executed source bytes
are contract-bound. Pytest passed 1,006 tests, skipped the two expected immutable v26.78
success-state tests, and retained one existing destructive-test serializer warning.

Authoritative identities:

```text
Preflight report
  finance_v26_budget_closed_instrument_preflight:
  6c279f69cb080458952dfb000633f17c4f901aa8098dfac0cb423656ad9684a7

Execution Contract
  finance_v26_budget_closed_instrument_contract:
  12c9789ccbe3d557411cf5428a15ee0e3d26337b846f47b61b830c86e1415121

Job Manifest
  finance_v26_budget_closed_instrument_manifest:
  38f4a8f5b40c2c576c690c3069c66bc1f43a64f52ef554a16ea28a4656c2434c

Source replay audit
  finance_v26_verifier_bound_source_replay:
  9f41787b75086d2465006a8a7075df5f30bf812c4a4e5d9349e32d4888182ba6
```

## Scientific Decision

The formal result is:

```text
fresh_budget_closed_population_ready = true
schema_closed_completed_scoring_ready = true
pre_call_provider_budget_contract_ready = true
failure_namespace_separation_ready = true
instrument_static_preflight_passed = true
online_instrument_result_available = false
capability_support_available = false
state_support_available = false
model_api_calls = 0
gpu_jobs = 0
production_contribution = 0
next_permitted_stage = fresh_budget_closed_verifier_bound_instrument_requalification_only
```

This is a positive static Instrument precondition. It is not evidence that the online Runtime will
pass, that a model trajectory will be valid, that any Capability mechanism is supported, or that
any VTDO state is reachable. The 0/36 historical State Support Freeze remains authoritative.

## Next Permitted Stage

The only permitted transition is execution of the exact frozen v26.83 32-Job Manifest as a fresh,
small Instrument requalification.

The online Runner must:

- replay the v26.83 Contract, Manifest, source files, task files, and implementation hashes before
  client construction;
- use exact `deepseek-v4-flash`, no fallback, and the frozen Provider route and model settings;
- persist each actual Prompt and raw Provider payload before parsing or scoring;
- issue a passing pre-call certificate before every token-bearing Provider request;
- emit the frozen typed no-call terminal without constructing a Provider call when a bound does
  not fit;
- require complete and internally consistent Usage for every HTTP-success response;
- retain every invalid model outcome and every typed no-call outcome in the 32-Job denominator;
- replay every completed Observation sequence through Verifier v2;
- compute all non-Replay Gates independently and pass completed trajectories through the shared
  schema-closed scorer;
- keep raw lineage and all downstream Instrument failure channels separate;
- require unique Provider call identities, zero Runtime failure, zero Instrument failure, and a
  USD 2.00 aggregate estimated-cost ceiling.

A passing online result may authorize only fresh Capability and Reachability protocol design. It
cannot authorize either empirical denominator, Confirmation, No-C VTDO, Student training, Exact
Target, GP-C, or Contribution.

## Authoritative Artifacts

- `artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820/source_freshness_audit.json`
- `artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820/provider_token_budget_contract.json`
- `artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820/compiler_trajectories.json`
- `artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820/completed_compiler_trajectory_scores.json`
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/report.json`
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/execution_contract.json`
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/job_manifest.json`
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/compiler_completed_scoring_audits.json`
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/budget_closure_mutation_audits.json`
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820/scoring_failure_channel_mutation_audits.json`

Historical references:

- `artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_20260820/report.json` (superseded immutable v1)
- `artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_20260820/report.json` (superseded immutable v1)
- `docs/finance_v26_78_v26_81_verifier_bound_instrument_recovery_and_audit.md`
- `artifacts/vtdo_experiment/finance_v26_81_verifier_bound_postrun_audit_20260820/report.json`
- `docs/finance_v26_76_v26_77_verifier_bound_rematerialization_and_preflight.md`
- `artifacts/vtdo_experiment/finance_v26_75_authority_preserving_verifier_qualification_v2_20260819/report.json`
