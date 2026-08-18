# Finance v26.60 Public Operation Closure and v26.61 Regression Preflight

Audit date: 2026-08-18

## Execution Update

This document remains the historical v26.60 static and v26.61 preflight record. The frozen v26.61
Manifest was subsequently executed, failed its instrument gate, and was repaired only under fresh
v26.62 identities. A fresh v26.63 requalification passed the preregistered instrument gate, while
the credential-free v26.64 post-run audit restricted the current transition to
`public_repair_and_postterminal_verification_contract_hardening_only`. See
`docs/finance_v26_61_v26_64_operation_instrument_repair_and_requalification.md` for the current
decision. The historical identities and preflight observations below are unchanged.

## Summary

Finance v26.60 implements the only transition authorized by v26.59:

```text
fresh_public_operation_contract_rematerialization_only
```

It creates a fresh, identity-incompatible 24-task Finance Population after Joint Compilation
binds a model-visible Public Operation Execution Contract, public progress semantics, terminal
Operation requirements, and Host stop readiness to the same Semantic Source, Program DAG,
Verifier DAG, Answer Projection, Evidence Support Lattice, Citation Contract, and Runtime.

All credential-free static gates pass:

| Gate | Result |
| --- | ---: |
| Fresh operational task identities | 24 / 24 |
| Public Operation Execution Contracts | 24 / 24 |
| Operation-closure audits | 24 / 24 |
| Primary Public Runtime Witnesses | 24 / 24 |
| All compiler Witness paths | 48 / 48 |
| Target-matched Mechanism Necessity | 24 / 24 |
| Operational capability prerequisites | 24 / 24 |
| Operational VTDO-candidate prerequisites | 12 / 12 |
| Static model-authority paths | 36 |
| Destructive Operation mutations | 192 |
| Public Runtime tool Observations | 588 |

The authoritative report identity is:

```text
finance_v26_public_operation_rematerialization_report:1b82fb0bcc1c3be058b48789e1e7c7cb65c46c7e8e968bef66186ae540a0907f
```

The initial zero-API v26.60 build remains immutable at
`finance_v26_60_public_operation_rematerialization_20260818`, but it is superseded. A
repository-wide Mypy pass required an explicit type guard for malformed terminal operands in the
Witness verifier. The guard does not alter any accepted Witness: all eleven detail artifacts are
byte-identical between v1 and v2. It does change a source byte bound by the implementation
manifest, so v2 received a new report identity rather than rewriting v1. Neither build made an API
call or used a GPU.

This is a positive operational-static result. It does not show that Flash reaches any valid path,
that a Quotient State has positive probability, or that Capability or VTDO support is empirically
admitted.

Finance v26.61 then freezes the small, outcome-blind Operation-closure Regression requested by the
audit:

```text
4 mechanisms x 2 capability-only tasks x 4 unconditional rollouts = 32 jobs
```

The credential-free preflight passes and authorizes only `model_execution_only`. No model client
was constructed, no API call or GPU job occurred, and no empirical result exists yet. The migrated
process environment and the documented project activation path currently contain no
`DEEPSEEK_API_KEY`, so the 32 jobs were not started.

## Scientific Boundary

v26.56 established static public executability:

```text
Z_static exists
```

v26.57-v26.59 showed that the old Runtime did not expose or enforce full Program closure:

```text
Z_operational was not established
```

v26.60 tests the missing middle layer:

```text
Program DAG
  -> public semantic nodes
  -> public progress
  -> terminal Operation
  -> post-terminal verification
  -> Host stop readiness
```

v26.61 is limited to an instrument regression over that layer. It is not a capability comparison,
task-selection experiment, state-support experiment, or VTDO experiment.

## Fresh Identity And Source Discipline

v26.60 does not add fields to v26.56 task identities. Every final TaskPackage receives a new
identity only after the Public Operation, Stop Readiness, Runtime Projection, and operational
Verifier bindings are frozen.

The new Population has six tasks per mechanism:

| Mechanism | Tasks | Capability role | VTDO-candidate role |
| --- | ---: | ---: | ---: |
| Context-conditioned action | 6 | 3 | 3 |
| Semantic reconciliation | 6 | 3 | 3 |
| Failure recovery | 6 | 3 | 3 |
| State-dependent stopping | 6 | 3 | 3 |
| Total | 24 | 12 | 12 |

Three previously frozen, no-API source populations supply fresh semantic inputs. Freshness is
checked against the v26.42 Development Population and all v26.56 tasks on six identity channels:

| Freshness channel | Selected count | Prior count | Overlap |
| --- | ---: | ---: | ---: |
| Source task Artifact ID | 18 | 43 | 0 |
| Source semantic signature | 18 | 42 | 0 |
| Source task hash | 18 | 42 | 0 |
| Evidence ID | 136 | 285 | 0 |
| Evidence Version ID | 136 | 285 | 0 |
| Source record ID | 136 | 285 | 0 |

Reconciliation reuses one immutable read-only Snapshot container but shares zero selected source
records. Container reuse is explicitly separated from row-level task identity:

```text
source_container_reuse_policy =
immutable_container_shared_rows_must_be_identity_disjoint
```

The tertiary source report binds zero model API calls and zero GPU jobs. No historical model
outcome is used for v26.60 task selection.

## Public Operation Contract

Each `PublicOperationExecutionContract` contains a public view and a private binding.

The public view contains:

- semantic Operation nodes;
- public symbolic variables and resolution predicates;
- node dependencies;
- a terminal node;
- symmetric registered operators for model-choice nodes;
- public input and output schemas;
- an explicit statement that no exact tool sequence is required.

The model-visible view does not expose:

- Gold Evidence IDs;
- Oracle Program node IDs;
- Program or Verifier DAG hashes;
- Verifier binding IDs;
- the correct choice inside a model-choice node;
- a unique complete tool sequence.

The private binding maps every public semantic node to exactly one frozen Program node and binds
the source Program and Verifier DAG hashes. The package validator rejects a missing mapping, a
foreign Program, a foreign Verifier, or a contract compiled from another Semantic Source.

## Public Progress And Stop Readiness

The Runtime derives public Operation progress only from public task metadata and replayable public
tool Observations. It reports:

- resolved and unresolved public variables;
- completed node IDs;
- dependency-ready nodes;
- one `next_required_step` only when exactly one node is ready;
- the terminal Operation reference;
- post-terminal verification status;
- post-completion violation status;
- final stop readiness.

The Host invariant is:

```text
StopReady =
  all required public nodes completed
  and terminal node completed
  and verification completed after the terminal node
  and no post-completion action
```

A successful calculation count is no longer sufficient. Calculation calls whose public
dependencies are incomplete fail before tool execution. An action after complete public closure
also fails and permanently marks the trajectory as having a post-completion violation.

The Runtime retains acquisition freedom. A task can use `structured_direct`,
`search_then_structured`, or `search_then_open` where registered; these paths converge on the
same semantic closure without exposing one canonical tool sequence.

## Runtime Witness Upgrade

The v26.60 Reference Policy uses the same public task, public progress function, tool-argument
gate, Operation step gate, post-completion gate, and Host stop-readiness contract as the Agent
Runtime.

It does not ask the Oracle Program for the next action. Public variables are resolved from public
predicates over successful public Observations. Model-choice operators are selected by matching
the public required output schema against the symmetric registered operator schemas.

Compiler Witnesses remain hidden verifier fixtures:

```text
model_generated = false
empirical_state_count = 0
```

The 48 Witness paths are:

| Path strategy | Witnesses |
| --- | ---: |
| `structured_direct` | 24 |
| `search_then_structured` | 12 |
| `search_then_open` | 12 |

Every Witness reaches the same task-specific terminal closure and passes the full independent
Verifier. No Witness is evidence of model reachability.

## Destructive Static Audit

Every task is replayed under all registered destructive mutations:

| Mutation | Cases | Result |
| --- | ---: | --- |
| Required-node ablation | 72 | all fail closed |
| Terminal before prerequisite | 24 | all fail closed |
| First calculation only | 24 | all fail closed |
| Premature verification | 24 | all fail closed |
| Terminal missing | 24 | all fail closed |
| Post-completion action | 24 | all fail closed |
| Total | 192 | all fail closed |

The existing target-matched Mechanism Necessity audit separately rejects wrong-mechanism
counterfactuals for 24/24 tasks. All registered acquisition paths close the same terminal answer
without an exact tool sequence being exposed.

## v26.61 Frozen Regression Design

### Selection

v26.61 selects exactly two of the three intended capability-only tasks in each mechanism. Ranking
is deterministic, pre-outcome, and salted by the frozen TaskPackage identity. It excludes all
VTDO-candidate tasks and creates no natural or conditioned state target.

The frozen identities are:

```text
contract =
finance_v26_operation_closure_regression_contract:367a02811efc1e7f8f691a23a1cd3b4babfd33f8935638947b2d7ee1b6266591

job manifest =
finance_v26_operation_closure_regression_jobs:6f20f39d997642239cb69722a0145388edb982e79becca3db69ceb34c51160f1
```

Each of eight tasks receives four unconditional replicas. The exact model is
`deepseek-v4-flash`, fallback is empty, requested-model equality is mandatory, the per-rollout
model-token limit is 120,000, and the aggregate estimated-cost limit is USD 2.00.

### Instrument estimands

The regression records, per rollout:

- complete Program-node lineage;
- terminal-node completion;
- post-terminal verification;
- premature verification;
- early final-answer rejection;
- Stop-ready false positive;
- Stop-ready false negative;
- post-completion violation;
- initial Public Operation contract visibility;
- Public Progress projection on every observed decision Prompt;
- private-identity absence in the initial Prompt;
- independent full-trajectory validity as a descriptive outcome.

Every stop attempt is replayed against the Observation prefix that existed at that decision.
Answer-schema or citation rejection after valid Operation closure is not mislabeled as a
Stop-ready false negative.

A rollout with no decision Prompt because the model failed its initial plan contract remains a
model outcome. Public Progress projection is checked conditionally on observed decision Prompts,
and `decision_prompt_observed_count` is reported separately. This prevents model failure from
being reclassified as instrument failure.

### Frozen pass rule

The instrument gate requires:

- 32/32 completed jobs;
- a passing raw-byte, identity, Prompt-hash, recursive-noninterference, and Provider-call
  uniqueness audit;
- 32/32 model outcomes;
- zero Runtime failure;
- zero instrument failure;
- exact requested model for 32/32 and zero fallback;
- the Public Operation contract in 32/32 initial Prompts;
- a passing Public Progress projection audit for 32/32 rollouts;
- private-identity absence in 32/32 initial Prompts;
- zero Stop-ready false positive;
- zero Stop-ready false negative.

Independent validity is not an instrument gate. All invalid model outcomes remain in the
denominator. The USD 2.00 resource ceiling is a separate frozen gate.

A pass still authorizes only:

```text
capability_development_and_state_reachability_protocol_only
```

It does not directly authorize either empirical stage. A new protocol must first freeze their
separate denominators and preserve valid-only state mapping.

## v26.61 Preflight Result

The authoritative preflight is:

```text
artifacts/vtdo_experiment/
  finance_v26_61_operation_closure_regression_preflight_v2_20260818/
```

Its report identity is:

```text
finance_v26_operation_closure_regression_report:b566a595464c5cb0549a208f37acc8b1dd00f36e319644c01ca41f4e552c9f93
```

The earlier preflight directory without the `v2` suffix remains immutable and superseded. It
used the stale v26.60 v1 source report and preceded the final v26.61 implementation manifest. It
also had a zero denominator and made no model or GPU call; it is not an empirical experiment.

Observed preflight state:

```text
completed_rollouts       = 0 / 32
Provider calls           = 0
Provider tokens          = 0
estimated cost           = USD 0
GPU jobs                 = 0
status                   = preflight
next_permitted_stage     = model_execution_only
production_contribution  = 0
```

The raw-integrity audit is correctly `partial` at a zero denominator; it is not treated as a
failure or pass. The preflight constructed no model client. Two independent builds produced
byte-identical execution contract, Job Manifest, and report files.

The API execution has not started because `DEEPSEEK_API_KEY` is absent from both the inherited
process environment and the documented project activation path, and the documented archive
`.env` is absent on this migrated server. This is a current execution-environment blocker, not
a scientific result and not evidence about Flash, Operation closure, state reachability, or VTDO.

## Immutable Outputs

### v26.60

Artifact root:

```text
artifacts/vtdo_experiment/
  finance_v26_60_public_operation_rematerialization_v2_20260818/
```

The report SHA-256 is:

```text
1c6dcf069890986fe3398e351bab767af3594bcf0b7077b00fdbee9b405d91e9
```

The report binds eleven detail artifacts, including 24 task records, 24 admissions, 24 closure
audits, 24 Necessity artifacts, 48 Witnesses, 48 mechanism counterfactuals, 588 public tool
Observations, 24 tool environments, 24 path catalogs, one freshness audit, and one Definition-pair
capacity audit.

### v26.61 preflight

| Artifact | SHA-256 |
| --- | --- |
| `execution_contract.json` | `2d9411c74348851b4d75b3e6ed018fba2b9159f1f3292c0a10d63acf3245ca98` |
| `job_manifest.json` | `059f15f1319b6775de0d933f21939e23932bda4f822006a998775ebbd15167f5` |
| `report.json` | `e82f58a748f800793e09bc28f8e540a96e5532b7cf6f2c8f552ecc49d15cf033` |

## Validation

Focused checks completed before the API stage:

| Check | Result |
| --- | ---: |
| v26.61 contract and preflight tests | 6 passed |
| Public Operation Runtime tests | 5 passed |
| v26.60 rematerialization tests | 8 passed |
| Iterative Agent Runtime tests | 41 passed |
| Focused total | 60 passed |
| Ruff | passed |
| Mypy for v26.60-v26.61 implementation | passed |
| v26.60 independent rebuild | all 12 JSON files byte-identical |
| v26.61 independent preflight | all 3 JSON files byte-identical |

One existing Pydantic serializer warning is emitted by a destructive test that intentionally
constructs a dict-valued node-binding mutation. It does not affect a production artifact or test
result.

## Interpretation

Supported conclusions:

- the v26.59 public Operation-contract omission is repaired in a fresh task identity;
- the real Agent Runtime can carry a complete public semantic solution without Oracle next-action
  access;
- Host stop readiness now requires full Program closure and post-terminal verification;
- all required-node, ordering, early-stop, missing-terminal, and post-completion mutations fail
  closed;
- three acquisition strategies remain statically available for VTDO candidates;
- a small, outcome-blind 32-job instrument regression is fully frozen and replayable.

Unsupported conclusions:

- Flash reaches any valid v26.60 trajectory;
- the Public Operation contract improves model validity;
- a valid model-generated Quotient State exists;
- any state has positive natural or conditioned probability;
- capability information geometry is adequate;
- Capability Development, State Reachability, Confirmation, No-C VTDO, Student training, Exact
  Target, GP-C, or Contribution is authorized.

## Next Step

Restore `DEEPSEEK_API_KEY` in the process environment and execute exactly the frozen 32-job
v26.61 Manifest. Do not change selected tasks, replica counts, Prompt or Runtime bytes, thresholds,
model identity, or fallback policy.

If and only if the v26.61 instrument and resource gates pass, the next permitted work is to freeze
a new protocol for separate Capability Development and State Reachability denominators. Full
validity remains descriptive for the instrument regression, but only independently valid
model-generated trajectories may enter future State Mapping.

Until then:

```text
capability_development_authorized = false
state_reachability_authorized     = false
fresh_confirmation_authorized    = false
no_c_vtdo_authorized             = false
student_training_authorized      = false
exact_target_authorized          = false
gp_c_authorized                  = false
production_contribution          = 0
```
