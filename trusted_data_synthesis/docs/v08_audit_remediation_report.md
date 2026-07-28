# v0.8.1 Audit Remediation Report

## Scope

This patch refines v0.8. It does not create a v0.9 feedback system and does not claim training
utility. It removes experimental confounds before another credentialed candidate run or GPU
experiment.

## Remediation Matrix

| Audit finding | Remediation | Authority boundary |
| --- | --- | --- |
| Model hand-writes execution logs | Added `host_instrumented` action and answer contracts plus a host executor | Model chooses semantics; host records execution facts |
| D1 mixes engineered wrong targets | Default D1 samples unfiltered real-Agent outputs only | No Contract selection and no typed-error injection |
| D4 mixes solve and repair formats | Default D4 emits clean `solve` targets; counterfactuals guide allocation | Feedback changes distribution, not target format |
| D5 bypasses shared selector | D5 calls `QualityAwareSelector` per domain and freezes selector identity | Contract is authoritative; Critic is advisory |
| Quality Vector appears calibrated | Vector and D5 metadata say `diagnostic_uncalibrated` | Scores are features, not universal quality truth |
| Evaluation is only task-ID isolated | Added subject, Evidence, version, source-record, and binding isolation | Any hard identity overlap fails the manifest |
| Internal evaluation can be mistaken for transfer | Manifest freezes `internal_iid_contract` and `external_benchmark_status=not_executed` | No external capability claim without native benchmark runs |
| Validation reports disagree | Added one content-addressed release-validation summary | Commit, tools, tests, artifacts, and online status are frozen together |

## Host-Instrumented Protocol

The model returns two semantic objects:

1. `agent_action_plan.v1`: selected Evidence, operators, inputs, parameters, and output step.
2. `agent_answer_decision.v1`: final result, Evidence citations, status, and optional claims.

The host validates public-plan compatibility, executes registered and allowed operations, and
creates `agent_execution_trace.v1`. Unknown Evidence, unavailable dependencies, disallowed tools,
invalid selectors, incompatible inputs, output-schema failures, and incomplete Evidence lineage
are rejected before trajectory normalization.

For plan-given tasks, operator order, arity, input kind, selector, dependency, parameters, and
output node must preserve the public skeleton. For plan-hidden tasks, the model may choose the DAG
but can use only public tool capabilities and registered operations.

The model cannot emit these host-owned fields:

```text
execution_id
tool_name
observation
source_locator
execution status
evidence lineage
```

Final citations are converted from exact selected Evidence IDs to immutable source locators by the
host. Independent candidate verification still replays the resulting trajectory.

## Cost and Provenance

`agent_capacity_audit.v3` reports separate lower bounds for search, action-plan, final-answer,
legacy full-response, and Critic calls. A resolved host-instrumented candidate therefore has a
two-call floor; semi-open/open candidates add a search call. Contract repairs remain telemetry and
are not hidden in the floor.

`agent_validation.v5` freezes the interaction protocol and search, action, final-answer, and
combined Prompt manifest hashes. Existing v4 artifacts remain readable as legacy `full_response`
artifacts, but they cannot validate the host protocol.

## Corrected Cohorts

### D1

`unfiltered_real_agent` includes accepted and rejected representable real outputs without using
Contract labels during sampling. It excludes typed counterfactual targets. The historical
engineered-noise construction is available only as `legacy_counterfactual_mix`.

This is a no-filter baseline inside the current task interface. It is not yet a broad conventional
synthesis baseline with no Program or Proof Graph, so that comparison must not be claimed.

### D4

`clean_solve_feedback` uses typed counterfactuals to identify failure families and allocate budget
among accepted clean tasks. Every target remains a normal solve record. `legacy_mixed_repair` is
retained only for historical reproduction.

### D5

Selection is Contract-accepted pool, then `QualityAwareSelector` per domain, then exact quota.
Selection IDs and policy hashes are frozen in records and manifests. Critic probability is only an
advisory ranking feature. Default Quality Vector and Critic thresholds are zero because neither is
human-calibrated. D5 remains exploratory.

## Evaluation Isolation

The data audit compares task ID, subject ID, Evidence ID, Evidence version, source record, semantic
binding identity, and Program signature. All except Program signature are hard leakage gates.
Program-signature overlap is reported because this track is IID at the operation-family level.

The checks exposed a real fixture defect: all Legal cases shared one subject ID. Legal fixtures now
use stable case-specific subject IDs. The internal evaluator remains useful but format-sensitive.
External FinQA, TAT-QA, LegalBench, and SciFact evaluation has not been added or executed here.

## Release Validation

`freeze-release-validation` writes `release_validation_summary.v1` with commit SHA, dirty state,
test command/count/status, tool versions, in-repository artifact SHA-256 values, online status, and
superseded IDs. Artifacts outside the repository are rejected. Git commands use an explicit
repository root, so invocation from another directory cannot capture an unrelated repository.

## Profiles

- `config/deepseek_v4_pro_agent_v08_host_regression.json`: 10 tasks per domain, resolved,
  plan-given, host-instrumented, no Critic; only for the next online regression.
- `config/training_utility_v08_1_qwen2_5_7b.json`: corrected 600-record D1-D5 contract using the
  frozen Qwen2.5-7B revision.

## Validation Coverage

Offline tests cover successful host execution and answer assembly, unknown Evidence rejection,
phase-aware API-call accounting, corrected D1/D4/D5 construction, selector identity, hard
train/evaluation isolation, cross-domain Legal/Science contracts, and release-summary hashing.
The exact test count and artifact hashes belong in the generated validation summary.

## Remaining Gates

Before a large candidate run:

1. Run the 30-candidate host regression with a pinned provider model.
2. Require at least 90% protocol completion and Contract evaluation, at least 60% acceptance, and
   accepted coverage in every domain and major Pattern.
3. Confirm resume performs zero calls for completed checkpoints.
4. Rebuild D1-D5 from that run; historical full-response artifacts do not validate the new path.
5. Run D0-D5 under equal supervised-token budgets.
6. Add native-format external evaluation before claiming task competence or training utility.

The deliverable is a less confounded, falsifiable v0.8 experiment contract, not a positive result
for the Agent, Critic, or training method.
