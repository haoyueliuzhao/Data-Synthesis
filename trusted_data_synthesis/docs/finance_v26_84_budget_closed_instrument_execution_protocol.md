# Finance v26.84 Budget-closed Instrument Execution Protocol

> Historical protocol note: the online attempt failed after 20 Jobs were exposed. The immutable
> outcome and the only authorized Recovery transition are recorded in
> `docs/finance_v26_84_v26_85_budget_closed_failure_and_recovery_preflight.md`. The Recovery was
> subsequently completed and independently audited; see
> `docs/finance_v26_84_v26_87_budget_closed_instrument_recovery_and_audit.md`.

Date: 2026-08-20

## Status

This document freezes the online implementation and execution procedure for the only transition
authorized by v26.83:

```text
fresh_budget_closed_verifier_bound_instrument_requalification_only
```

At the time of this pre-run record, the implementation and all credential-free tests pass, but the
real Provider run has not started. `DEEPSEEK_API_KEY` is absent from both the inherited subprocess
environment and the documented `scripts/activate_project.sh` path. No v26.84 Job has been exposed,
no model client has been constructed, and no empirical row exists. This is an execution-environment
blocker, not a scientific result.

## Frozen Inputs

The Runner accepts only the following authoritative identities:

- v26.82 Population report:
  `finance_v26_budget_closed_verifier_bound_instrument_population_report:9f60f8d7c7522a1fd934bb5a7cdfefb2c91becc73f7e68b2f815dea352ad6484`;
- v26.83 preflight report:
  `finance_v26_budget_closed_instrument_preflight:6c279f69cb080458952dfb000633f17c4f901aa8098dfac0cb423656ad9684a7`;
- v26.83 execution Contract:
  `finance_v26_budget_closed_instrument_contract:12c9789ccbe3d557411cf5428a15ee0e3d26337b846f47b61b830c86e1415121`;
- v26.83 Job Manifest:
  `finance_v26_budget_closed_instrument_manifest:38f4a8f5b40c2c576c690c3069c66bc1f43a64f52ef554a16ea28a4656c2434c`;
- Provider token budget Contract:
  `provider_token_budget_contract:27e7e524cb3139b9dd29b1ca7f2c7eae1956c96af8a982524f814b3ef4415150`;
- qualified Verifier v2 report:
  `finance_v26_authority_verifier_qualification:f61be6be022c2c8506e818e3bb9690e71fa316c6820fec69458c7ab7c8fa7bb1`.

The exact empirical denominator is:

```text
4 mechanisms x 2 fresh tasks x 4 unconditional replicas = 32 Jobs
```

The model is exact `deepseek-v4-flash`, fallback is empty, the per-rollout Provider ceiling is
120,000 tokens, and the aggregate estimated-cost ceiling is USD 2.00. The Runner does not permit a
different task, Job, environment, Replay binding, budget Contract, route, model, replica, or
sampling role.

## Pre-client Replay

Before model-client construction, the Runner:

1. parses the v26.82 and v26.83 reports, Contract, Manifest, and frozen source replay through their
   strict Pydantic schemas;
2. verifies every immutable v26.83 detail-file hash;
3. verifies the v26.82 report and qualified Verifier report hashes bound by the Contract;
4. loads all eight task records, environments, Verifier v2 task bindings, and authority-preserving
   task audits;
5. checks every Job against its TaskPackage, Environment, repair Contract, terminal target,
   Verifier implementation, and Replay binding;
6. replays all inherited source entries and content-binds the prospective online implementation;
7. writes the online source replay, Execution Binding, frozen Contract, and frozen Manifest before
   any credential access or model-client construction.

The final credential-free build currently yields:

```text
execution_binding_id = finance_v26_budget_closed_instrument_execution_binding:772d296b3c42aa43e786affa35f8759b47d056384719524f19fdc8c57fd6a40c
online_source_replay_audit_id = finance_v26_budget_closed_online_source_replay:14a5c9a0b5800611c6986aa581f42afb565b2cf4cca31f1efe54b2ae85c701e2
expected_job_count = 32
model_client_constructed = false
model_api_calls = 0
```

These identities remain valid only while the content-bound online source files are unchanged.

## Per-call Ordering

Each Job constructs a fresh per-rollout budget ledger around a Job-local Raw-first journal. The
logical call order is:

```text
Agent request attempt
-> frozen pre-call budget Certificate
-> allowed Provider invocation or typed no-call terminal
-> Raw Provider Prompt/payload and pre-Host telemetry persistence
-> Provider Usage validation
-> Host prompt-component telemetry augmentation
-> Agent response-contract parsing and Runtime action
```

The Runner stores both the actual Provider Prompt sequence and the complete attempted Prompt
sequence. The latter includes the final denied Prompt when a typed no-call terminal occurs. It
stores Provider telemetry before Host augmentation separately from the telemetry retained by the
Agent solve or failure Artifact. Their only permitted difference is the content-addressed
`response_shape.prompt_component_bytes` Host augmentation.

Every allowed request must have exactly one preceding Certificate and exactly one Usage record.
Every successful HTTP response must carry Prompt, completion, and total usage; Prompt plus
completion must equal total; cache hit plus cache miss must equal Prompt usage when cache telemetry
is present; all Prompt, completion, request, and cumulative bounds must pass. Requested, selected,
and Provider-response model identities must all equal `deepseek-v4-flash`.

## Typed No-call Semantics

If a request cannot fit under the frozen conservative bound and required reserves, the budget
wrapper creates `budget_exhausted_no_call` before invoking the Provider. The Runner retains the Job
in the denominator as `model_invalid_resource_terminal`, makes no Provider call for the denied
request, and records one of four descriptive phases:

```text
initial_prompt_unfit
mid_rollout_budget_exhausted
final_reserve_unavailable
repair_reserve_unavailable
```

A valid typed no-call is not an Instrument failure. A call made without a passing Certificate,
missing or inconsistent successful Usage, a bound violation, or a Provider model mismatch is an
Instrument/resource failure.

## Scoring And Failure Domains

Every completed or failed Observation sequence is replayed by Verifier v2. Non-Replay Gates are
computed independently from the raw solve/failure Artifact. A completed model trajectory then uses
the shared schema-closed scorer from v26.82:

```text
Verifier v2 Replay
-> independent non-Replay Gates
-> frozen core terminal
-> schema-closed trace Sidecar
-> Instrument/report admission
```

The shared scorer binds the current twelve-field `TrajectoryStep` schema and computes the trace
from `TrajectoryStep.observation`. A Sidecar failure cannot alter the frozen valid/invalid core
terminal, but it does block report completeness and Instrument authorization.

Failures remain in seven non-overlapping namespaces:

```text
raw_lineage:
provider_capture:
runtime_replay:
scoring_core:
diagnostic_sidecar:
resource_budget:
report_aggregation:
```

The raw-lineage aggregate is constructed independently and accepts only `raw_lineage:` failures.
Replay, scoring, Sidecar, resource, and aggregation failures cannot change its status.

## Recovery Policy

The Runner writes one canonical raw Provider Artifact per call and one canonical raw execution
Artifact per Job before Replay or scoring. A scored rollout is appended to a checkpoint only after
the raw execution exists.

- A checkpointed Job is never executed again.
- A Job with a complete raw execution but no checkpoint row is recovered with zero generation.
- A Job with orphan raw Provider calls but no raw execution is not retried automatically. It
  requires a new read-only exposure/recovery audit.
- A completed 32-Job directory is replayed without constructing a model client and must reproduce
  the same report bytes.

This policy prevents a worker, scoring, or aggregation failure from silently repeating an exposed
Job.

## Instrument Gate

The online Instrument is ready only if all of the following hold:

- exactly 32 terminal rows and one retained terminal per Job;
- the independent raw-lineage audit passes and Provider call identities are unique;
- every actual Provider call is precertified and all budget audits pass;
- exact requested, selected, and response model identity for every Provider call, with zero
  fallback;
- zero Runtime failure, zero Instrument Gate failure, and zero report-completeness failure;
- 32/32 Verifier v2 Replay passes and 32 independent non-Replay audits;
- every completed trajectory uses the shared schema-closed scorer and has a passing Sidecar;
- action-neutral repair, typed terminal target, and Stop Readiness pass per rollout;
- cumulative per-rollout tokens remain at or below 120,000 and aggregate estimated cost remains at
  or below USD 2.00.

Independent validity, Program closure, local mechanism behavior, and trace diversity are
descriptive only and cannot rescue a failed Instrument or resource Gate.

## Credential-free Validation

The pre-run implementation currently passes:

```text
Python compilation                         passed
Ruff                                       passed
Mypy, new online Runner                    passed
focused Runner and full-Manifest fixtures  6 passed, 2 formal-result tests skipped
full Fixture 32-Job Manifest               32/32 retained model-invalid outcomes
Fixture Verifier v2 Replay                 32/32 passed
Fixture raw lineage and budget Gates       passed
Fixture completed-run zero-generation      byte-identical report, no client construction
combined budget/scoring/replay regression  passed
```

The Fixture run is an engineering test and contributes zero empirical rows. It is not evidence
about DeepSeek V4-Flash capability or real Provider budget behavior.

## Authorized Command

Once `DEEPSEEK_API_KEY` is restored only in the process environment, execute:

```bash
python -m trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_requalification \
  --execution-run-id finance_v26_84_budget_closed_verifier_bound_instrument_requalification_20260820 \
  --task-source-dir artifacts/vtdo_experiment/finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820 \
  --verifier-qualification-dir artifacts/vtdo_experiment/finance_v26_75_authority_preserving_verifier_qualification_v2_20260819 \
  --preflight-dir artifacts/vtdo_experiment/finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820 \
  --output-dir artifacts/vtdo_experiment/finance_v26_84_budget_closed_verifier_bound_instrument_requalification_20260820 \
  --package-root . \
  --workers 16
```

No Capability Development, State Reachability, Confirmation, VTDO update, Student training, Exact
Target, GP-C, or production Contribution is authorized by this pre-run implementation. A passing
online result may authorize only fresh Capability and Reachability protocol design.
