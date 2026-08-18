# Finance v26.61-v26.64 Operation Instrument Repair and Requalification

Audit date: 2026-08-18

## Summary

Finance v26.61-v26.64 completes the real-model instrument test requested after v26.60, repairs a
Runtime composition defect under fresh identities, and then performs a credential-free post-run
audit before any Capability Development or State Reachability protocol is frozen.

The four immutable stages are:

| Stage | Role | Result | API / GPU |
| --- | --- | --- | ---: |
| v26.61 | First 32-job Operation regression | Blocked by 20 Host instrument failures | 143 calls / 0 GPU |
| v26.62 | Fresh static instrument hardening | Passed all operational-static gates | 0 / 0 |
| v26.63 | Fresh 32-job instrument requalification | Instrument and resource gates passed | 403 calls / 0 GPU |
| v26.64 | Read-only post-run contract audit | Two public contract gaps observed | 0 / 0 |

The v26.63 instrument result remains a valid positive result. All 32 jobs produced model outcomes,
all raw and Prompt audits passed, Runtime and instrument failures were zero, Public Progress was
action-neutral, and Stop Readiness produced no false positive or false negative. Independent
validity was deliberately not an instrument gate.

The model outcomes nevertheless revealed two prospective measurement defects that the frozen
v26.63 gate did not cover:

1. failed Operation calls could return exact `tool_id` and `expected_arguments` inside an
   action-bearing repair patch;
2. the public cross-check tool accepted answer-shaped claims as locally verified, while frozen
   Stop Readiness recognized only a different terminal-operation-reference shape.

The authoritative v26.64 decision is:

```text
status = public_repair_and_postterminal_verification_contract_gaps_observed
next_permitted_stage =
  public_repair_and_postterminal_verification_contract_hardening_only
```

Capability Development, State Reachability execution, Fresh Confirmation, No-C VTDO, Student
training, Exact Target, GP-C, and production Contribution remain forbidden. Production
Contribution remains zero.

## Scientific Question

v26.60 established the static and Runtime-Witness existence of operational public closure:

```text
Z_static exists
Z_operational exists under the public Runtime
```

The next question was not whether Flash was capable in aggregate. It was whether the same Runtime
could expose and enforce that closure during real model execution without leaking private identity
or silently accepting premature stopping.

The v26.61/v26.63 estimand therefore remained an instrument estimand:

```text
Public Contract visible
and Public Progress replayable
and private identities absent
and Stop Readiness exact
and every completed Job classified as model, Runtime, or instrument outcome
```

Independent validity, mechanism success, Program completion, and terminal completion were
descriptive outcomes. No task selection, model comparison, state conditioning, state mapping, or
causal accuracy comparison was permitted.

## v26.61 Historical Regression

### Frozen denominator

The first executed regression retained the v26.61 preflight design:

```text
4 mechanisms x 2 capability-only tasks x 4 unconditional replicas = 32 jobs
```

The exact model was `deepseek-v4-flash`, fallback was empty, requested-model equality was
mandatory, the per-rollout model-token ceiling was 120,000, and the aggregate estimated-cost
ceiling was USD 2.00.

### Observed result

The run completed its 32-job denominator but classified only 12 rows as model outcomes. Twenty
rows failed as instrument outcomes with the same exception:

```text
AttributeError: 'NoneType' object has no attribute 'get'
```

The immutable report is:

```text
finance_v26_operation_closure_regression_report:
1520782d212f40e9d4bc88c8eab3cbb5e2bb03a96f21957c9cd04ac9615e25b3
```

Its recorded telemetry was 143 Provider calls, 1,184,311 provider-reported tokens, and estimated
cost telemetry of USD 0.1193173296. The 20 crashed rows did not retain complete post-call telemetry,
so these totals are historical lower-bound telemetry rather than a complete cost denominator.

### Credential-free root-cause reproduction

The crash was reproduced without an API call by replaying a frozen Runtime Witness prefix. At the
failure point:

```text
len(ready_nodes) = 2
next_required_step = null
the proposed Calculator call is valid under the new public Operation gate
```

The new public gate accepted the call, but `_operation_step_rejection` then fell through into the
legacy single-step gate and evaluated `next_step.get(...)`. This was a composition defect between
new and historical Host gates, not a model error and not a failure of the static Operation
contract.

The same audit found two prospective Prompt issues:

- action-bearing fields were still present in the old `next_required_step` projection;
- the public stop payload still serialized `semantic_source_id`.

These findings authorized only an incompatible Runtime and public-contract repair. The 12 model
outcomes were not promoted, and the 20 failed rows were not retried under the historical task
identity.

## v26.62 Fresh Instrument Hardening

v26.62 created a fresh 24-task identity-incompatible Population. It did not patch v26.60 or
reinterpret v26.61.

### Runtime and contract changes

The hardening introduced:

- a public stop-readiness view with no Semantic Source binding identity;
- a semantic-only Progress projection for ready and next nodes;
- explicit `action_binding_fields_exposed=false` telemetry;
- new-gate precedence, so a public Operation decision cannot fall through to the legacy
  single-step gate;
- recursive private-field checks covering Semantic Source, Program, Verifier, and target binding
  fields;
- raw-first Provider telemetry and Prompt retention before downstream Host aggregation.

The semantic-only Progress node contains only:

```text
node_id
node_kind
semantic_role
dependency_node_ids
unresolved_symbols
```

It contains no `tool_id`, operator, parameters, argument contract, or expected arguments.

### Static result

All static gates passed:

| Gate | Result |
| --- | ---: |
| Fresh TaskPackages | 24 / 24 |
| Public Operation contracts | 24 / 24 |
| Operation-closure audits | 24 / 24 |
| Primary Public Witnesses | 24 / 24 |
| All compiler Witness paths | 48 / 48 |
| Target-matched Mechanism Necessity | 24 / 24 |
| Operational capability prerequisites | 24 / 24 |
| Operational VTDO-candidate prerequisites | 12 / 12 |
| Static model-authority paths | 36 |
| Destructive Operation mutations | 192 |

The authoritative report is:

```text
finance_v26_public_operation_rematerialization_report:
0a73cb6e9d90313bdeafd4dd7b42c455c25a1bcfab8300a943d49ed0f157fba3
```

The report SHA-256 is
`1d2927507f1ec063695d2edb559b77ff95e42812bb6baf1b585ba64efc4f5f26`.
An independent build reproduced all twelve JSON files byte for byte. Both builds used zero model
API calls and zero GPU jobs.

## v26.63 Instrument Requalification

### Frozen identities

v26.63 selected two capability-only tasks per mechanism from v26.62 before observing outcomes and
froze four unconditional replicas per task.

```text
contract =
finance_v26_operation_closure_regression_contract:
3dca1017f418794d299a4531ef96e174bafcc825360291312c17f55d2228df32

Job Manifest =
finance_v26_operation_closure_regression_jobs:
5cd6886869ef3113376378ea35494b112c837427a020534b606613ff83e42f5c
```

The gate remained instrument-only. In particular, independent validity was outside the pass rule,
and state mapping was forbidden.

### Instrument result

All frozen gates passed:

| Gate | Result |
| --- | ---: |
| Completed jobs | 32 / 32 |
| Model outcomes | 32 / 32 |
| Runtime failures | 0 |
| Instrument failures | 0 |
| Exact requested model | 32 / 32 |
| Fallback | 0 |
| Public Contract in initial Prompt | 32 / 32 |
| Public Progress audit | 32 / 32 |
| Initial Prompt private-identity free | 32 / 32 |
| Stop-ready false positives | 0 |
| Stop-ready false negatives | 0 |
| Raw byte / identity / Prompt / recursive audit | 32 / 32 each |
| Unique Provider call identities | passed |
| Resource ceiling | passed |

The run made 403 Provider calls, used 3,930,087 provider-reported tokens, and recorded estimated
cost telemetry of USD 0.4368207872. Every call used the exact requested Flash identity, fallback
was zero, and no local GPU job ran.

The authoritative report is:

```text
finance_v26_operation_closure_regression_report:
04cd426a734f4fe6fcbf90e4e07ee750bc19ed6b17809ad43bac5fa4a107a599
```

Its report SHA-256 is
`7a9739675ae7637ab5743656b36f24fbf2f52344479335fcf7db36907262401f`.
A credential-free completed-run replay resumed 32/32 rows, executed zero jobs, and left all seven
top-level artifact hashes and the report identity unchanged.

### Descriptive closure funnel

The frozen model outcomes were all independently invalid, but the new Operation contract moved
the structural failure point:

```text
all required Program nodes complete      24 / 32
terminal Operation complete              24 / 32
frozen post-terminal verification         0 / 32
independently valid trajectory             0 / 32
early final-answer rejection observed     21 / 32
premature verification observed            0 / 32
```

The mechanism-specific post-run replay is:

| Mechanism | Full Program | Terminal | Local verified calls after terminal | Frozen post-terminal verified | Mechanism estimand success |
| --- | ---: | ---: | ---: | ---: | ---: |
| Context-conditioned action | 4 / 8 | 4 / 8 | 24 | 0 / 8 | 8 / 8 |
| Semantic reconciliation | 8 / 8 | 8 / 8 | 13 | 0 / 8 | 8 / 8 |
| Failure recovery | 4 / 8 | 4 / 8 | 10 | 0 / 8 | 8 / 8 |
| State-dependent stopping | 8 / 8 | 8 / 8 | 26 | 0 / 8 | 0 / 8 |

These local mechanism and verification counts are diagnostics. They do not satisfy complete
validity and do not create a Quotient State.

## v26.64 Credential-free Post-run Audit

### Source and replay discipline

v26.64 binds and replays 51 immutable source files:

```text
7 v26.63 top-level execution files
12 v26.62 source/report files bound by the execution Contract
32 raw rollout Artifacts
```

It checks the v26.63 execution Contract, Job Manifest, aggregate, append-order checkpoint, raw
integrity audit, frozen diagnostics, current implementation hashes, task-source hashes, and all 32
raw bytes. Checkpoint comparison is by exact Job identity because concurrent completion order is
not Manifest order.

The audit made no model call, did no state mapping, selected no task, compared no model, rescored no
historical outcome, and used no GPU.

### Public Progress and failed-action repair

All observed Public Progress projections were action-neutral:

```text
action-bearing ready/next Progress Prompts = 0
```

However, a separate failed-action path remained action-bearing. Twenty-seven failed Operation
Observations returned a repair patch containing fields such as `tool_id` and
`expected_arguments`; these covered 22/32 rollouts. Twenty-seven such patches entered a later
model Prompt, covering 21/32 rollouts. One final failed result did not enter a later Prompt before
the model-token budget ended.

This does not retroactively fail the preregistered v26.63 gate, whose Prompt estimand was the
Operation Progress projection. It does prevent the same Runtime from supporting a prospective
claim that repaired trajectories remain fully model-owned.

### Post-terminal verification mismatch

Twenty-four trajectories completed their terminal node. Twenty-three then produced 73 successful
`cross_check_evidence` calls with `verified=true`; one terminal-complete Reconciliation trajectory
ended at its model-token budget without a later cross-check.

The 73 locally successful post-terminal calls had the following argument shapes:

| Claim shape | Calls |
| --- | ---: |
| Answer payload without `operation_ref` | 66 |
| Matching terminal `operation_ref` plus extra fields | 7 |
| Exact `{operation_ref: terminal_ref}` | 0 |
| Other / wrong reference | 0 |

The frozen Stop Readiness predicate therefore recorded 0/32 post-terminal verification
completions. The evidence supports a public contract mismatch between tool-local verification and
terminal-operation binding. It does not support the stronger claim that Flash performed no useful
verification behavior.

Historical v26.63 outcomes are not rescored under a more permissive rule. Any future rule must be
frozen prospectively and bound into a fresh TaskPackage identity.

### Trace and acquisition diagnostics

Across 32 model outcomes, successful-tool sequences contained 15 unique traces, effective count
12.563884, and maximum trace share 0.21875. This rejects a single successful-trace-template
explanation.

All 32 observed pre-calculation acquisition routes classified as `structured_direct`. These were
unconditional capability-only tasks with no requested VTDO path target, so the result is not a
test of the three registered VTDO acquisition paths and cannot establish path collapse or
multiroute support. It is retained only as a design diagnostic for the future Reachability
protocol.

### Authoritative output

Artifact root:

```text
artifacts/vtdo_experiment/
  finance_v26_64_operation_closure_postrun_audit_20260818/
```

| Artifact | Records | SHA-256 |
| --- | ---: | --- |
| Rollout post-run diagnostics | 32 | `eb1ab07bf0e9cda07c87f1f997a8f03f394d3762b65531e6211e2ecf40050730` |
| Mechanism summaries | 4 | `23c3c8fd752b861fcfab987f356b7dae165b5db3a6cc3d4f4cfc3d3bd8624e2d` |
| Report | 1 | `255fbee3482b9e223b1fa1bd0ab03f8941c8e32b8a07519e91fe28e0b395e593` |

The report identity is:

```text
finance_v26_operation_closure_postrun_audit:
75ba366bac4afba3efc7784029b5e53aadd855cbab9509ed2489b7cdc71f030e
```

An independent `/tmp` build reproduced all three files byte for byte.

## Validation

Final repository validation completed after the historical-contract test was updated to freeze
the v27 incompatibility boundary:

| Check | Result |
| --- | ---: |
| v26.64 focused audit tests | 7 passed |
| Iterative Runtime, v26.63 regression, and v26.64 audit focus | 55 passed |
| Ruff over `src` and `tests` | passed |
| Mypy | passed, 361 source files |
| Full Pytest | 919 passed in 464.56 seconds |
| Core generalization boundary | 138 files, zero violations |
| Tracked `sk-` plus 32-alphanumeric scan | zero hits |
| v26.62 independent build | all twelve JSON files byte-identical |
| v26.63 completed-run replay | zero jobs; seven top-level hashes unchanged |
| v26.64 independent build | all three JSON files byte-identical |

The full suite emitted one expected Pydantic serializer warning from a destructive test that
intentionally inserts dict-valued node bindings. It does not occur in a production artifact and
does not change a test result.

## Interpretation

Supported conclusions:

- v26.63 is a valid positive Operation-instrument result under its frozen gate;
- the v26.61 new-gate/legacy-gate crash is closed under fresh identities;
- Public Progress itself no longer leaks a concrete next tool or arguments;
- real model execution now reaches full Program and terminal closure in 24/32 rows;
- failed-action repair can still expose exact action bindings outside Public Progress;
- tool-local verification and frozen terminal-reference verification are not aligned;
- successful trace variation exists, but natural VTDO path support remains unevaluated.

Unsupported conclusions:

- v26.63 proves a positive valid-trajectory probability;
- the 24 local mechanism successes are valid trajectories;
- the 73 local verification passes satisfy frozen Stop Readiness;
- Flash cannot perform terminal verification under a coherent public contract;
- all future acquisition paths collapse to `structured_direct`;
- Capability Development or State Reachability execution is ready;
- any Quotient State, VTDO update, training effect, GP-C result, or Contribution exists.

No causal validity comparison with v26.57 is performed because the task identities, public
contracts, Runtime bytes, and support object changed.

## Next Permitted Experiment

The next work is credential-free contract hardening only.

First, failed-action repair must preserve error information without supplying the target action.
It may expose the failed tool, typed error, unchanged public semantic requirement, and which
public variables remain unresolved. It must not expose a ready node's concrete tool, correct
operator, parameters, Evidence identities, or complete expected arguments. Recovery tasks must
retain genuine model authority over how to satisfy the retry contract.

Second, the verification tool and Stop Readiness must share one typed public verification target.
That target must bind the model-observed terminal operation reference, define whether additional
claim fields are allowed, and reject a wrong or missing terminal reference. The exact predicate
must be frozen before task identity and replayed by both the Runtime Witness and the independent
Verifier.

The repaired design must receive fresh TaskPackage, Operation Contract, Stop Contract, Runtime
projection, and Verifier identities. Before another model call it must pass:

- action-neutral Progress and repair-Prompt audits;
- exact public/private isolation;
- positive Runtime Witnesses through terminal verification and stopping;
- wrong-reference, missing-reference, extra-field, early-verification, and post-completion
  destructive mutations;
- target-matched Mechanism Necessity;
- independent byte replay and source-manifest validation.

Only that static result may authorize another small instrument requalification. It may not reuse
v26.63 model outcomes as fresh evidence. Capability Development, State Reachability execution,
Fresh Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and production Contribution
remain forbidden.
