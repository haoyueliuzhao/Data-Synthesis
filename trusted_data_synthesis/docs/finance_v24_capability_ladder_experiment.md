# Finance v24 Capability Ladder Experiment

Experiment date: 2026-08-12

## Status

Finance v24 separates Agent Runtime qualification from capability measurement. The Runtime is now
qualified on a fresh 18-task set, but the frozen semantic ladder is not a true Frontier. The
1,800-rollout capability calibration, Beneficiary screening, Exact Target, GP-C, Validation, and
Authorization were not executed.

The current fail-closed transition is:

```text
Runtime qualification: passed
Semantic Frontier audit: failed
Next permitted stage: frontier_task_construction_only
Production Contribution: 0
```

This is neither evidence for nor evidence against the Pro-Flash capability-sensitivity hypothesis.
It is evidence that protocol friction can be controlled and that the current six registered task
families do not provide a meaningful semantic difficulty ladder.

## Experimental Question

The v23 Direct control was easy for both models while Scripted and Autonomous performance fell.
v24 tests whether that pattern came from semantic and Agent capability or from protocol friction.
Difficulty is frozen as a three-component vector:

```text
d(x) = (semantic, agentic, protocol)
```

The capability score includes semantic and agentic structure only. Protocol friction is reported
separately and cannot be used to make a task look capability-sensitive.

## Registered Design

The source population contains 420 real Finance task-state artifacts from the frozen Finance
Archive. Historical target tasks and executed Explorer tasks are excluded by task and Evidence
version identity. The remaining pool is balanced over six families:

```text
finance.comparison
finance.derived_growth_comparison
finance.registered_ratio
finance.temporal_absolute_change
finance.temporal_average
finance.temporal_growth
```

Stage A uses 18 Easy-Control tasks, three per family. Pro and Flash each run Scripted Tool and
Autonomous Agent three times per task, for 216 requested rollouts. Stage B would use 30 Frontier
tasks, five per family, with Direct Fixed Retrieval, Scripted Tool, and Autonomous Agent controls.
It requires 1,800 rollouts and is authorized only when both the Runtime and semantic Frontier pass.

Direct Fixed Retrieval means a deterministic retrieval pipeline. It is not a no-tool language-model
control and must not be described as Direct/Bare in later analysis.

## Protocol Revisions

The v24 runtime revisions are domain-neutral where possible:

- public implicit plans replace an extra model planning call;
- compact observations and separate repair/final reserves limit context friction;
- stop readiness requires retrieval, selection, calculation, and verified=true in task order;
- verified=false cannot satisfy a verification requirement;
- Host verification repair is allowed only when verification is the sole unmet requirement;
- exact output fields are frozen by the public answer contract;
- raw JSON response rate and bounded logical contract resolution are reported separately;
- scripted progress exposes remaining tool identities without exposing hidden Oracle arguments.

The Finance v5 public tool contract also clarifies two generic serialization rules: selector strings
must be copied verbatim from successful public observations, and operation-reference operands must
be real JSON objects rather than encoded strings. The Host still does not inject Gold selectors or
repair semantic tool arguments.

## Semantic Ladder Audit

The frozen audit is identical for v3 and v4:

| Tier | Mean semantic score |
| --- | ---: |
| Easy Control | 4.583333333 |
| Frontier | 4.595000000 |
| Hard Control | 4.729166667 |

Frontier minus Easy is only `0.011666667`, below the preregistered minimum of `1.0`. No family meets
the required family-level gain of `0.5`; at least four of six were required. Replacing every selected
task with disjoint instances did not change any family mean. The problem is structural: instances
within a registered family share almost the same semantic program shape.

Audit identity:

```text
finance_semantic_ladder_audit:5bd0a24f3f3e78057fa56a1fbedb6825b929965a84c7c941bb71848452695817
```

## v3 Matched Protocol Regression

v3 deliberately reused the v2 task population to isolate the stop-readiness change. It completed
216 requested records with 24 workers. Host-forced verification fell from the v2 maximum of 96.3%
to zero, raw JSON and bounded JSON gates passed, and the minimum tool success rate passed. Two Pro
Scripted records did not complete, so completion, final emission, and no-budget-exhaustion gates
failed. The two failures were localized to public argument serialization:

1. an operation-reference object was encoded as a string and then repeated after failure;
2. exact period labels from search results were abbreviated, exhausting the failed-tool budget.

v3 therefore remained `protocol_repair_only`. Its API estimate was `$1.288297956`.

## v4 Fresh Runtime Qualification

v4 excluded every v1-v3 qualification rollout before sampling. Across qualification, Frontier, and
Hard controls, all 60 selected task IDs have zero overlap with v1-v3 task IDs. The frozen pool has
333 eligible tasks after 93 historical task exclusions.

Contract identity:

```text
finance_capability_ladder_contract:4022ec3826c5db9901a86af6c3cab380c6e2c68179db4722b378861be08b5904
```

Result identity:

```text
finance_capability_ladder_stage_report:43d1a089a8d5e6d63d8c6c34f6e22dc05b7c07bc516417ec96aac0828b3297cc
```

### Runtime gates

| Gate | Observed | Requirement | Result |
| --- | ---: | ---: | --- |
| Exact model discovery | 1.0000 | 1.0000 | pass |
| Minimum completion | 1.0000 | 1.0000 | pass |
| Minimum raw JSON response contract | 0.9556 | >= 0.85 | pass |
| Minimum bounded JSON resolution | 1.0000 | 1.0000 | pass |
| Minimum tool technical success | 0.9531 | >= 0.95 | pass |
| Minimum final-answer emission | 1.0000 | 1.0000 | pass |
| Budget exhaustion count | 0 | 0 | pass |
| Minimum observation replay | 1.0000 | 1.0000 | pass |
| Minimum authority integrity | 1.0000 | 1.0000 | pass |
| Maximum Host verification repair | 0.0000 | <= 0.15 | pass |

All 216 successful verification observations explicitly returned `verified=true`; no result relied
on a missing flag being interpreted as success.

### Descriptive cell results

| Model | Runtime | Completed | Valid | Answer correct | Tool success | State entropy |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Pro | Scripted | 54/54 | 51/54 | 51/54 | 369/374 | 1.0151 |
| Pro | Autonomous | 54/54 | 37/54 | 38/54 | 305/320 | 0.6714 |
| Flash | Scripted | 54/54 | 46/54 | 46/54 | 369/371 | 0.8833 |
| Flash | Autonomous | 54/54 | 47/54 | 47/54 | 303/312 | 0.8801 |

These Easy-Control rates are qualification diagnostics, not capability estimates. In particular,
Flash Autonomous exceeds Pro Autonomous on this small easy set. That cannot authorize a model
ranking or refute the Explorer hypothesis. The planned mixed-effects comparison belongs to an
independent, semantically valid Frontier.

The run made 1,614 API calls, used 6,723,826 provider-reported tokens, and recorded an estimated
API cost of `$1.4765509822`. The estimate is telemetry rather than an invoice. No GPU was required:
all model inference used the external API and local work was CPU-bound verification and artifact
assembly.

## Fail-Closed Stage B Check

After the Runtime report passed, Stage B revalidated the report, checkpoint, canonical rollout,
run identity, denominator, and semantic-audit identity. It was then invoked without credentials and
failed before model-client construction with:

```text
ValueError: capability calibration requires a true semantic Frontier
```

No Stage B checkpoint was created and no Stage B API request occurred. Validation and Authorization
objective access remain forbidden, GP-C remains unevaluated, and production Contribution remains
zero.

## Credential-Free Completed-Run Replay

The completed v4 stage was replayed with both supported credential environment variables removed.
The runner resumed `216/216`, executed zero jobs, made no model-discovery or API call, rebuilt the
canonical rollout ordering, verified the checkpoint and rollout hashes, and returned the unchanged
report ID. A changed checkpoint, rollout file, run identity, denominator, or semantic-audit hash is
rejected fail-closed.

## Scientific Interpretation

v24 supports three conclusions:

1. The v23 performance drop was materially confounded by protocol friction. A bounded, replayable
   Runtime can execute the full qualification set without completion loss or Host takeover.
2. The current task generator cannot construct a semantic Frontier from instance sampling alone.
   New companies, periods, and metrics preserve the same family-level program shape.
3. Pro-Flash capability sensitivity remains unidentified. Running 1,800 more rollouts on the current
   pseudo-Frontier would create cost without answering the scientific question.

The next permitted work is task construction only. It must add genuine structural variation such
as multi-hop cross-period joins, cross-source or definition reconciliation, distractor-dependent
evidence selection, recovery-requiring tool paths, and verification-sensitive answers. A new
semantic audit must pass before any capability calibration or Exact Target work resumes.

## Immutable Artifacts

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/vtdo_experiment/
  finance_v24_capability_ladder_v3_20260812/
  finance_v24_capability_ladder_v4_20260812/
```

Credentials were loaded only into the experiment process environment. They are absent from the
contract, rollout records, reports, and Git tree.
