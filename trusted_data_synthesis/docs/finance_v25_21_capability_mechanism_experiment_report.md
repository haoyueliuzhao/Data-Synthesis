# Finance v25.21 Capability Mechanism Experiment

## 1. Scope

This experiment follows the public-benchmark capability audit with the preregistered sequence:

```text
Stage A  Development population
Stage B  deterministic structure and shortcut audit
Stage C  Flash Development localization
Stage D  mechanism and Tier freeze
Stage E  disjoint fresh Flash Confirmation
Stage F  information geometry, only when Stage E authorizes it
Stage G  sparse Pro anchors, only when Stage F authorizes them
```

FinQA and TAT-QA contributed aggregate structural statistics only. No public benchmark question,
answer, program, context, or evidence was used to materialize a task. The other public benchmarks
contributed published interaction-design metadata only.

## 2. Public Benchmark Reference

The frozen audit contains 1,147 FinQA and 1,663 TAT-QA records. FinQA has 42.98% multi-operation,
7.32% programs with at least three operations, and 50.48% multi-evidence tasks. TAT-QA has 42.03%
arithmetic, 12.63% multi-span, and 54.90% multi-evidence tasks. These results motivated seven typed
capability mechanisms rather than another entity/year resample.

## 3. Static Development

The final static population is:

- population ID: `finance_capability_mechanism_development_population:d18385c3faaf8975f9367c07f4b89bd0e02121ea6613c2af6945cc5eb076de90`
- 7 mechanisms and 84 matched groups;
- 2 Easy, 4 Bridge, 4 Frontier, and 2 Hard groups per mechanism;
- 168 task variants;
- 100% operation replay, matched contract, matched intervention, executable mechanism support,
  answer contract, and destructive mutation detection;
- disjoint Evidence, Evidence Version, and core semantics from v25.20;
- no model or GPU call.

The public answer contract was repaired before the formal run. It now exposes exact signed
operation semantics and maps internal Evidence references to the requested public entity or period.
The evidence-retrieval verifier also accepts every registered evidence-access tool rather than
hard-coding `search_archive`.

The 14-rollout answer-contract regression made 88 API calls and processed 403,013 model tokens.
Thirteen trajectories were independently replayable and all 13 were correct and valid. One
transport failure remains in the original denominator and was not promoted by offline replay.

## 4. Flash Development

The formal Stage C artifact is:

`finance_v25_21_capability_mechanism_flash_development_v2_20260814`

It contains 504/504 records in each records, outcomes, terminal outcomes, and behavior-observation
file. Results are:

| Metric | Result |
| --- | ---: |
| API transport resolution | 100% |
| Bounded JSON resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Runtime pathology | 0% |
| Semantic accuracy over Runtime-eligible records | 90.48% |
| End-to-end valid success | 89.09% |
| API calls | 3,948 |
| Model tokens | 20,606,388 |

The 48 exceptional terminations were model outcomes: 42 exhausted the frozen stop-rejection
budget and 6 exhausted the frozen failed-tool budget. They are L4 model decisions, remain in the
capability denominator, and are not retried as Provider failures.

### Selection correction

The first analyzer called a final-answer difference `matched_behavior_detected` without requiring
the mechanism-specific behavior. That could select dependent composition even though none of its
mechanism trajectories performed the required normalization. The corrected fail-closed gate now
requires both:

1. at least two matched outcome differences; and
2. at least two observed mechanism-specific behavior successes.

An immutable zero-API reanalysis selected four mechanisms:

- `finance.typed_tool_plan_and_argument_recovery`;
- `finance.candidate_verification_and_repair`;
- `finance.cross_family_failure_recovery`;
- `finance.state_dependent_control_and_stopping`.

Information acquisition was saturated. Semantic alignment did not produce enough matched outcome
differences. Dependent composition was rejected because its required behavior was never observed.

The original full run used a contract that did not hash the shared stage runner. A resume-only fix
reused an already frozen model-discovery artifact and did not alter tasks, prompts, tools, models,
or completed trajectories. Future contracts include the shared runner in the implementation
manifest. This limitation is disclosed rather than hidden by rewriting the source artifact.

## 5. Frozen Selection And Fresh Population

Stage D froze four mechanisms and the same schedule for each:

```text
Bridge, Bridge, Frontier, Frontier, Frontier
```

The freeze explicitly records `confirmation_response_access = forbidden`. Stage E then used a
separate real-finance source pool containing 4,488 public Evidence items. The resulting population
contains 20 matched groups and 40 task variants.

The static audit passed at 100% and independently verified zero overlap with Development on:

- Task artifact ID;
- Group ID;
- Evidence ID;
- Evidence Version ID;
- core semantic signature;
- mechanism signature.

The population also passed benchmark-content isolation and within-Confirmation Evidence
disjointness.

## 6. Fresh Flash Confirmation

The immutable 200-rollout contract is:

`finance_capability_mechanism_confirmation_contract:7c1e055f0f06c166cda0a62dacce8e8c0d80e288b121533788f0a4dab0248c3a`

The run completed 200/200 records:

| Metric | Result |
| --- | ---: |
| API transport resolution | 100% |
| Bounded JSON resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Runtime pathology | 0% |
| Semantic accuracy over Runtime-eligible records | 88.00% |
| End-to-end valid success | 88.00% |
| API calls | 1,606 |
| Model tokens | 8,666,929 |

Twenty-two rollouts exhausted the frozen stop-rejection budget and two exhausted the failed-tool
budget. All 24 are attributed model-control outcomes and remain in the denominator.

### Independent mechanism decisions

| Mechanism | Boundary groups | Matched differences | Behavior successes | Decision |
| --- | ---: | ---: | ---: | --- |
| Typed tool and argument recovery | 2 | 2 | 21/25 | confirmed |
| Candidate verification and repair | 0 | 1 | 25/25 | not confirmed |
| Cross-family failure recovery | 3 | 2 | 21/25 | confirmed |
| State-dependent stopping | 2 | 1 | 21/25 | not confirmed |

Candidate verification saturated in the new population. State-dependent stopping exposed model
variation but did not create enough matched task-level outcome differences. These are task-mechanism
results, not Runtime failures.

## 7. Decision

The preregistered rule required every frozen mechanism to confirm before information geometry.
Only two of four confirmed, therefore:

```text
runtime_qualification_passed = true
all_frozen_mechanisms_confirmed = false
information_geometry_authorized = false
pro_api_calls = 0
gpu_jobs = 0
next_permitted_stage = mechanism_confirmation_or_task_repair_only
```

Stage F, sparse Pro anchors, Beneficiary screening, Exact Target, GP-C, Contribution, VTDO updates,
and Student training remain blocked. The telemetry cost fields are implementation estimates, not
Provider invoices and must not be used as authoritative spending totals.

## 8. Next Repair

The confirmed tool-recovery and cross-family-recovery mechanisms are frozen as replicated findings;
they do not need another identical Development run. The next task-only repair should focus on:

1. candidate verification with nontrivial localized candidate errors, independent evidence paths,
   and cases where replay is necessary rather than merely requested;
2. stopping tasks with externally observable complete/incomplete corpus states, asymmetric redundant
   action cost, and a terminal answer that depends on the stopping decision;
3. a new Development set for only those repaired mechanisms, followed by another fully disjoint
   Confirmation set;
4. information geometry only after the repaired mechanisms independently replicate.

No threshold should be relaxed using the current Confirmation responses.
