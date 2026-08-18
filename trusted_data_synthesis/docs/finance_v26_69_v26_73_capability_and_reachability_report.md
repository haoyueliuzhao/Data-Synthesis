# Finance v26.69-v26.73 Capability Development and State Reachability

Audit date: 2026-08-19

## Summary

Finance v26.69-v26.73 executes the two empirical roles designed in v26.68 after first supplying
their missing prerequisites. It creates a fully fresh balanced Capability Population, implements
one authority-preserving Runner for both frozen denominators, executes Capability Development and
State Reachability separately, and independently replays both completed runs.

| Stage | Purpose | Result | Provider calls / GPU |
| --- | --- | --- | ---: |
| v26.69 | Fresh balanced Capability Population | 12/12 static pass | 0 / 0 |
| v26.70 | Separate authority-preserving role preflights | 96 and 360 jobs frozen | 0 / 0 |
| v26.71 | Capability Development | 4/96 independently valid | 811 / 0 |
| v26.72 | State Reachability | 21/360 independently valid; 0/36 states admitted | 3,415 / 0 |
| v26.73 | Independent post-run replay and isolation audit | Passed | 0 / 0 |

The authoritative post-run audit is:

~~~text
finance_v26_authority_role_postrun_audit:
2b3cdbec5671c1cdc38c3f978cca1eb5ef07ed59afcda91298625976edf1331e
~~~

The final state-support decision is:

~~~text
valid Capability trajectories          4 / 96
mechanisms with a valid trajectory      1 / 4
valid Reachability trajectories        21 / 360
natural on-state hits                    5
conditioned on-target hits               2
released realizations                    2
admitted states                         0 / 36
admitted VTDO tasks                     0 / 12
State Support Freeze                    blocked
next permitted stage                    capability_task_or_reachability_condition_redesign_only
production Contribution                 0
~~~

The authority-preserving instrument remains established. The empirical result does not establish
balanced Capability support or VTDO state support. Fresh Confirmation, No-C VTDO, Student
training, Exact Target, GP-C, and production Contribution remain forbidden.

## Scientific Boundary

The experiment preserves the role separation frozen by v26.68:

~~~text
Capability Development
  fresh 12-task Population
  8 unconditional replicas per task
  task and mechanism response measurement

State Reachability
  unopened v26.65 VTDO candidates
  12 natural attempts per task
  6 conditioned attempts per registered state
  valid-only Quotient mapping
~~~

The two roles have separate task sources, contracts, Job Manifests, raw artifacts, Provider call
identities, trajectories, estimands, and reports. Capability outcomes were not used to select or
alter Reachability tasks, paths, conditions, or thresholds.

The experiment asks two distinct questions:

1. Does the fresh balanced Capability distribution produce independently valid outcomes across
   all four registered mechanisms?
2. Do the previously unopened VTDO candidates have natural hits and affordable conditioned
   realization yield for all three registered states per task?

A local mechanism success is not an independently valid trajectory. A valid conditioned
trajectory that maps to a different state is not an on-target realization. Compiler Witnesses
remain static fixtures and contribute zero empirical observations.

## v26.69 Fresh Capability Population

### Fresh source construction

v26.69 excludes all task and Evidence inputs used by v26.42 Development, v26.56, v26.65, and the
v26.66 real-model instrument run before selecting any new input. It does not combine the four
unopened v26.65 capability tasks with eight post-outcome additions.

The resulting Population contains:

~~~text
4 mechanisms x 3 fresh capability-only tasks = 12 tasks
~~~

| Mechanism | Tasks |
| --- | ---: |
| Context-conditioned action | 3 |
| Semantic reconciliation | 3 |
| Failure recovery | 3 |
| State-dependent stopping | 3 |

Freshness is zero-overlap on all audited channels:

| Channel | Selected | Prior | Overlap |
| --- | ---: | ---: | ---: |
| Source task Artifact ID | 9 | 61 | 0 |
| Source semantic signature | 9 | 60 | 0 |
| Source task hash | 9 | 60 | 0 |
| Evidence ID | 73 | 421 | 0 |
| Evidence Version ID | 73 | 421 | 0 |
| Source record ID | 73 | 421 | 0 |
| Semantic Source ID | 12 | 48 | 0 |
| TaskPackage ID | 12 | 48 | 0 |

Reconciliation is built from the immutable v25.44 Snapshot after replaying the v26.29 exposure
receipt and the larger Development exclusion union. The capacity audit found 14 eligible
Definition pairs, enough for seven tasks, and materialized a six-task candidate pool before the
balanced three-task selection. No historical model outcome entered selection, and no trajectory
was generated during construction.

### Authority-preserving contracts

Every new TaskPackage binds the v26.65 contract family before identity freeze:

- action-neutral failed-action repair;
- one typed Public Terminal Verification Target;
- Public Operation closure and semantic Progress;
- Runtime and Verifier bindings;
- Answer Projection, Evidence Support, and Citation contracts;
- target-matched Mechanism Necessity.

All tasks are registered only for `capability_measurement`. Their static path catalogs have status
`not_required`; no compiler path is promoted to a VTDO state.

### Static result

| Gate | Result |
| --- | ---: |
| Fresh TaskPackages | 12 / 12 |
| Public Runtime Witnesses | 12 / 12 |
| Operation Closure audits | 12 / 12 |
| Authority/terminal audits | 12 / 12 |
| Mechanism Necessity | 12 / 12 |
| Capability admission | 12 / 12 |
| Legacy destructive Operation mutations | 98 / 98 failed closed |
| Authority/verification mutations | 60 / 60 failed closed |
| Public Witness Observations | 126 |
| API calls / GPU jobs | 0 / 0 |

The report identity is:

~~~text
finance_v26_fresh_capability_population_report:
8b7aeb2a9d9044640d41b73eb17d13780cc4bcf5229a1794b751bceee4b12f1e
~~~

The report SHA-256 is
`8b1c3a3bd19a5a0de690a70bc5c05b11e3c9634034bea9de899865ecc67f0490`.
Two complete builds reproduced all fourteen detail files and `report.json` byte for byte.

## v26.70 Authority-Preserving Role Runner

### Common execution contract

The v26.70 Runner supports exactly two roles while retaining role-specific contracts and
denominators. Before model-client construction it verifies:

- every source Artifact byte and source report identity;
- the exact TaskPackage, Runtime, repair, terminal-target, Verifier, condition, and mapper binding;
- the exact source-design Job identity set;
- implementation source hashes;
- raw-path uniqueness;
- public-condition noninterference for conditioned jobs.

During execution it persists the actual Prompt and Provider response before parsing or scoring.
Every rollout receives raw-byte, Job identity, Prompt hash, recursive noninterference,
action-neutral repair, terminal-target, and condition-noninterference audits. Only independently
valid model-generated trajectories may enter State Mapping. Invalid model outcomes remain in the
frozen denominator.

Both roles request exact `deepseek-v4-flash`, require requested-model equality, and have an empty
fallback list. The per-rollout model-token ceiling is 120,000. The separate aggregate estimated
cost ceilings are USD 8.00 for Capability and USD 25.00 for Reachability.

### Preflight result

| Item | Capability | Reachability |
| --- | ---: | ---: |
| Expected jobs | 96 | 360 |
| Source files replayed | 15 / 15 | 16 / 16 |
| Task/Runtime bindings | 12 / 12 | 12 / 12 |
| Repair bindings | 12 / 12 | 12 / 12 |
| Terminal-target bindings | 12 / 12 | 12 / 12 |
| Verifier bindings | 12 / 12 | 12 / 12 |
| Source-design bindings | 96 / 96 | 360 / 360 |
| Condition noninterference | not applicable | 216 / 216 |
| Historical Job overlap | 0 | 0 |
| Model client constructed | false | false |
| API calls / GPU jobs | 0 / 0 | 0 / 0 |

Frozen identities:

~~~text
Capability Contract =
finance_v26_authority_preserving_role_contract:
8e1218ade8867d94998c58a7045484c92f52292455875e42f98b55f434a476f8

Capability Job Manifest =
finance_v26_authority_preserving_role_manifest:
21265e75c04c15ebeaa81907d3ffc529bee14d58cc3facbcc26c8bb650d09a49

Reachability Contract =
finance_v26_authority_preserving_role_contract:
33a5dd40d655a6d4215981cb5c3dc0702d5312954f0a41f64d95f3d9498b3d16

Reachability Job Manifest =
finance_v26_authority_preserving_role_manifest:
d026915a0f3afe0b516145295c4204f2f2d99f229171a6c2ea9baaa68d5e9c37
~~~

Independent preflights reproduced all four files for each role byte for byte and made no model or
GPU call.

## v26.71 Capability Development

### Execution integrity and resources

The frozen design executed:

~~~text
4 mechanisms x 3 tasks x 8 unconditional replicas = 96 jobs
~~~

| Metric | Result |
| --- | ---: |
| Completed jobs / model outcomes | 96 / 96 |
| Runtime failures / instrument failures | 0 / 0 |
| Exact requested model | 96 / 96 |
| Fallback | 0 |
| Raw byte / identity / Prompt hash | 96 / 96 |
| Recursive noninterference | 96 / 96 |
| Repair neutrality / terminal target | 96 / 96 |
| Provider call identities unique | true |
| Provider calls | 811 |
| Provider-reported tokens | 7,755,553 |
| Estimated cost telemetry | USD 0.8699810616 |
| Resource ceiling | passed |
| GPU jobs | 0 |

The run recorded 249 failed-action repair Prompts and 288 failed tool Observations. Zero exposed an
action-bearing Tool, Operator, parameter, expected argument, or repair patch. Stop-readiness false
positive and false negative counts are both zero.

### Capability outcomes

Eighteen trajectories completed the full Program, terminal Operation, and post-terminal
verification. Four were independently valid.

| Mechanism | Rollouts | Local mechanism success | Independently valid | Boundary tasks |
| --- | ---: | ---: | ---: | ---: |
| Context-conditioned action | 24 | 8 | 4 | 3 |
| Semantic reconciliation | 24 | 2 | 0 | 2 |
| Failure recovery | 24 | 12 | 0 | 3 |
| State-dependent stopping | 24 | 8 | 0 | 2 |

Only Context-conditioned Action produced independently valid trajectories. Recovery has the
largest local mechanism count but zero complete valid trajectory, so local mechanism behavior
cannot be promoted to complete Capability support.

The result is a complete balanced Development measurement, not a positive balanced-support
result. It does not authorize Capability Confirmation or post-hoc task selection.

The authoritative report is:

~~~text
finance_v26_authority_preserving_role_report:
bc6f3343190334d7b91ea81dc9a9d5c40cc67c353aa28e0b7f5f1efed572a319
~~~

Its SHA-256 is
`784f98405d62679f07949e89c823d8928e7ff33cae5554c7d010db8e19ea8e15`.

## v26.72 State Reachability

### Frozen denominator

All twelve v26.65 VTDO-candidate tasks and all 36 static states were unopened before this run. The
v26.68 design was preserved exactly:

~~~text
natural attempts:
  12 tasks x 12 unconditional attempts = 144

conditioned attempts:
  12 tasks x 3 registered states x 6 attempts = 216

total = 360
~~~

Natural jobs contain no requested state or condition. Conditioned jobs bind one public condition
to one frozen static path and target Quotient State. The two denominators remain separate in every
summary and gate.

### Execution integrity and resources

| Metric | Result |
| --- | ---: |
| Completed jobs / model outcomes | 360 / 360 |
| Runtime failures / instrument failures | 0 / 0 |
| Exact requested model | 360 / 360 |
| Fallback | 0 |
| Raw byte / identity / Prompt hash | 360 / 360 |
| Recursive noninterference | 360 / 360 |
| Repair neutrality / terminal target | 360 / 360 |
| Condition noninterference | 360 / 360 |
| Provider call identities unique | true |
| Provider calls | 3,415 |
| Provider-reported tokens | 32,960,134 |
| Estimated cost telemetry | USD 3.4768128360 |
| Resource ceiling | passed |
| GPU jobs | 0 |

The run recorded 1,166 repair Prompts and 1,372 failed tool Observations. Action-bearing counts are
zero for both. Stop-readiness false positive and false negative counts are also zero.

Forty-six trajectories completed the full Program and terminal Operation; 42 completed the typed
post-terminal verification. Twenty-one trajectories were independently valid, and all 21 were
mapped. This is a positive valid-trajectory observation, but state admission requires stronger
state-specific evidence.

### Reachability and yield

| State-support component | Result |
| --- | ---: |
| Registered states | 36 |
| Natural on-state hits | 5 hits across 3 states |
| Conditioned on-target hits | 2 hits across 2 states |
| Released conditioned realizations | 2 across 2 states |
| Positive conditioned LCB states | 2 |
| Budget-passing states | 2 |
| Three-realization yield-passing states | 0 |
| Admitted states | 0 / 36 |
| Tasks with all three states admitted | 0 / 12 |

Every state lacks the required three independent released realizations. Thirty-four states also
fail the positive conditioned-acceptance lower bound and materialization budget; 33 lack a natural
hit. The two released states each contain only one realization and therefore cannot pass the
yield contract.

The conditioned acquisition diagnostics are:

| Requested path | Adherence | Independently valid | On-target valid |
| --- | ---: | ---: | ---: |
| `structured_direct` | 52 / 72 | 2 / 72 | 2 / 72 |
| `search_then_structured` | 6 / 72 | 6 / 72 | 0 / 72 |
| `search_then_open` | 7 / 72 | 8 / 72 | 0 / 72 |

Most conditioned attempts for the two search-based targets instead used a structured-direct
acquisition route. This supports a condition-adherence and route-realization problem as a concrete
redesign target. It does not establish that condition adherence is the sole cause of every invalid
or off-target outcome.

The valid Reachability outcomes are also mechanism-imbalanced:

| Mechanism | Local mechanism success | Independently valid |
| --- | ---: | ---: |
| Context-conditioned action | 18 | 5 |
| Semantic reconciliation | 2 | 0 |
| Failure recovery | 37 | 0 |
| State-dependent stopping | 16 | 16 |

Reconciliation and Recovery again have no independently valid trajectory. The 21 valid outcomes
therefore cannot be interpreted as broad support across mechanisms.

The content-addressed State Support Freeze is:

~~~text
finance_v26_empirical_state_support_freeze:
4b451c2d3d94937331c46ae5c7089f13f86f6b67c8ea62a26b3c4ab8c897f6ed
~~~

It is `blocked`, admits no state or task, and freezes
`capability_task_or_reachability_condition_redesign_only` as the next transition.

The authoritative run report is:

~~~text
finance_v26_authority_preserving_role_report:
0f2e58fa42fb3ae80f3ef082153139520f2571da2f00fe836fe6cecf3890b016
~~~

Its SHA-256 is
`0098e146e61719607037316d3cc5675704233ad1fd10ca834b80e3e262ba7ec1`.

## v26.73 Independent Post-run Audit

v26.73 is credential-free and read-only. It replays the two execution Contracts and Job
Manifests against their preflights, replays every contract source and all 13 frozen implementation
sources per role, independently reconstructs the raw-integrity audits and rollout diagnostics,
and regenerates both reports.

The initial zero-API v1 audit remains immutable at
`finance_v26_73_authority_role_postrun_audit_20260819` but is superseded. Final review found that
v1 called the Runner's private diagnostic, raw-audit, and report-aggregation functions. It checked
byte replay but could not independently detect a shared aggregation defect. v2 removed those
calls and separately implemented Prompt/Observation replay, Capability aggregation, state-level
Wilson intervals, realization deduplication, and the global State Support Freeze. A package-wide
Mypy pass then required explicit local dictionary annotations in that new independent code. v3
adds only those type declarations and is authoritative. No empirical outcome, threshold, or
derived scientific value changed across the three zero-API audits.

| Replay | Capability | Reachability |
| --- | ---: | ---: |
| Frozen Contract / Manifest / preflight bytes | identical | identical |
| Contract source replay | 15 / 15 | 16 / 16 |
| Implementation source replay | 13 / 13 | 13 / 13 |
| Raw rollout replay | 96 / 96 | 360 / 360 |
| Diagnostics reproduced | true | true |
| Raw-integrity audit reproduced | true | true |
| Report reproduced | true | true |

The cross-role isolation audit found zero overlap in:

- TaskPackage identity;
- Semantic Source identity;
- Evidence identity;
- Evidence Version identity;
- source record identity;
- source-design Job identity;
- execution Job identity;
- Provider call identity;
- trajectory identity.

The audit records 456 rollout-level replay rows, three condition-adherence summaries, two role
summaries, and one cross-role isolation record. Formal and independent builds reproduced all five
JSON files byte for byte. The audit made zero API calls and used zero GPU jobs.

The report SHA-256 is
`7925eb44b2f9cad84e9f7627fee672e29e24c550e543a004d2b80d1da3a88f50`.

## Aggregate Resource Telemetry

Across the two empirical roles:

| Item | Total |
| --- | ---: |
| Model jobs | 456 |
| Provider calls | 4,226 |
| Provider-reported tokens | 40,715,687 |
| Estimated cost telemetry | USD 4.3467938976 |
| Local GPU jobs | 0 |

The cost values are provider-derived telemetry under the frozen pricing configuration, not an
invoice. Both role-specific resource gates passed.

## Immutable Outputs

| Stage | Artifact root | Report SHA-256 |
| --- | --- | --- |
| v26.69 | `artifacts/vtdo_experiment/finance_v26_69_fresh_capability_population_20260819/` | `8b1c3a3bd19a...` |
| v26.70 Capability | `artifacts/vtdo_experiment/finance_v26_70_capability_development_preflight_20260819/` | `54bff94f156d...` |
| v26.70 Reachability | `artifacts/vtdo_experiment/finance_v26_70_state_reachability_preflight_20260819/` | `1f7bdee7917e...` |
| v26.71 | `artifacts/vtdo_experiment/finance_v26_71_capability_development_20260819/` | `784f98405d62...` |
| v26.72 | `artifacts/vtdo_experiment/finance_v26_72_state_reachability_20260819/` | `0098e146e617...` |
| v26.73 v3 | `artifacts/vtdo_experiment/finance_v26_73_authority_role_postrun_audit_v3_20260819/` | `7925eb44b2f9...` |

Credential-free completed-run replay resumed v26.71 at 96/96 and v26.72 at 360/360, executed zero
jobs, constructed no model client, and retained both report identities. Historical artifacts were
not rescored or rewritten.

## Validation

| Check | Result |
| --- | ---: |
| New source and tests, Ruff format/check | passed |
| v26.69-v26.73 focused regression | 46 passed |
| Repository-wide Pytest | 951 passed in 569.38 seconds |
| v26.69 independent rebuild | 15 / 15 files byte-identical |
| v26.70 independent preflights | 8 / 8 files byte-identical |
| v26.73 independent rebuild | 5 / 5 files byte-identical |
| Credential-free completed-run replay | 96/96 and 360/360 resumed; zero jobs |

Repository-wide Mypy checked 367 source files and reported one `var-annotated` diagnostic for the
local `provider_ids` list in the exact v26.70 Runner source. Adding `list[str]` would not alter a
runtime value, but it would change source bytes already bound to the executed Contracts and the
v26.73 source replay. The exact executed source is retained, and no Mypy rule is relaxed. Direct
checks of the three new modules otherwise pass.

The full Pytest run emits one existing Pydantic serializer warning from a destructive mutation
test that deliberately supplies dict-valued public node bindings. It does not affect an immutable
experiment output or test result.

## Interpretation and Limits

Supported conclusions:

- a fresh balanced 12-task Capability Population can be built under the v26.65
  authority-preserving contracts;
- the same v3 Runner can execute both roles while preserving their separate identities,
  denominators, telemetry, and estimands;
- the authority-preserving Runtime and audit instrument remained intact for all 456 outcomes;
- Flash produced four independently valid Capability trajectories and 21 independently valid,
  mapped Reachability trajectories;
- natural and conditioned state hits are nonzero but sparse;
- the frozen state reachability and realization-yield contract admits zero state and zero task;
- search-based public conditions have low observed route adherence in this Population.

Unsupported conclusions:

- all four mechanisms have usable Capability support;
- local mechanism success is equivalent to complete trajectory validity;
- any one of the 36 static states has sufficient independent realization yield;
- the three states of any VTDO task are jointly reachable;
- changing only Prompt wording would repair the observed support failures;
- Flash is incapable of these mechanisms in general;
- Fresh Confirmation, No-C VTDO, Student training, Exact Target, GP-C, or Contribution is ready.

The route-adherence finding is an observed diagnostic. It is a plausible engineering contributor
to the search-path failure, but it is not asserted as the sole causal explanation. Reconciliation
and Recovery also retain complete-validity deficits that a route-only repair may not resolve.

## Next Step

Do not relax the three-realization requirement, pool states, promote off-target valid outcomes,
reuse compiler Witnesses, or combine local mechanism successes with independently valid rows. Do
not open Capability Confirmation or State-support Confirmation.

The only permitted transition is:

~~~text
capability_task_or_reachability_condition_redesign_only
~~~

The Capability branch may redesign fresh task support for Reconciliation, Recovery, and Stopping,
where complete independent validity is absent despite local mechanism activity. A new Population
must use fresh identities and must not select tasks from v26.71 outcomes post hoc.

The Reachability branch may redesign the public condition and route-realization interface,
especially for `search_then_structured` and `search_then_open`. Any successor must use fresh
condition, Job, and execution-contract identities, preserve natural versus conditioned
denominators, retain all invalid model outcomes, and pass a static authority/noninterference
preflight before another API call.

Capability Confirmation, State-support Confirmation, No-C VTDO, Student training, Exact Target,
GP-C, and production Contribution remain forbidden. Production Contribution remains zero.
