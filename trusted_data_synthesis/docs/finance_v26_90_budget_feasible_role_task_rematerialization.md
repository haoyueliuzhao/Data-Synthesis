# Finance v26.90 Budget-Feasible Role Task Rematerialization

Date: 2026-08-21

## Decision

Finance v26.90 completed the only transition authorized by the v26.89 Budget
Adequacy Contract:

```text
fresh_budget_feasible_role_task_rematerialization_only
```

The stage materialized a fresh, role-separated static Population containing 12
Capability tasks and 12 Reachability tasks. It proved one complete public path for
every Capability task and three complete public paths for every Reachability task
under the unchanged 120,000-token rollout ceiling. It did not construct a model
client, make a Provider call, run a GPU job, freeze an empirical role Contract, or
materialize a Job Manifest.

The authoritative result is:

```text
status                          = passed
fresh role TaskPackages         = 24
Capability tasks                = 12
Reachability tasks              = 12
budget-qualified public paths   = 48 / 48
model API calls                 = 0
GPU jobs                        = 0
empirical rows                  = 0
next permitted stage            = thinking_budget_calibration_preflight_only
```

The report identity is
`finance_v26_budget_feasible_role_rematerialization_report:9d6e1de192bf267aa45dfbf7b49c1270c0ec995e03b734f208663763a01ef17e`.

## Authorization Boundary

v26.89 separated three resource claims that must remain distinct:

1. Budget Compliance means that actual Provider calls cannot exceed the frozen
   resource contract.
2. Static Budget Feasibility means that every prefix of a complete public path has
   a certified upper bound at or below the rollout ceiling.
3. Empirical Budget Adequacy means that typed no-call terminals are sufficiently
   rare in a prospectively frozen independent calibration.

v26.86 established Budget Compliance, but its 24/32 typed no-calls rejected Budget
Adequacy. v26.89 then found that 0/8 exposed Compiler paths were statically
budget-qualified: their conservative bounds ranged from 366,569 to 575,686 tokens.
Those values were not Usage estimates and did not authorize a larger budget.

v26.90 addresses only the second claim on fresh tasks. It does not establish
empirical adequacy or model capability. The historical v26.71, v26.72, v26.78,
v26.80, v26.84, and v26.86 outcomes remain immutable and are not rerun, rescored,
pooled, or reclassified.

## Source Replay And Pre-Outcome Selection

The build replayed 57 source, contract, model-profile, verifier, task-record, and
historical Job-manifest files before producing the Population. The replay includes:

- four immutable, zero-API Finance source Populations;
- the frozen v26 Development source and exposure-clean receipts;
- all nine historical operational-task record files used by the exclusion audit;
- all 22 historical Job and Recovery-Job manifests used by the Job-identity audit;
- the v26.75 Verifier v2 qualification and Replay Contract;
- the v26.89 Budget Adequacy Contract and Provider budget contract; and
- the prospective exact-Flash thinking-enabled model profile.

Selection loaded no source-task outcome, historical model result, v26.81 diagnostic
candidate, or Compiler fixture result. It used only immutable source structure and a
frozen selection salt. Eligible source capacity after historical exclusions was:

| Mechanism | Eligible source tasks | Selected Capability | Selected Reachability |
| --- | ---: | ---: | ---: |
| Context-conditioned Action | 11 | 3 | 3 |
| Failure Recovery | 15 | 3 | 3 |
| Semantic Reconciliation | 30 | 3 | 3 |
| State-dependent Stopping | 14 | 3 | 3 |

The source-capacity audit identity is
`finance_v26_budget_feasible_role_capacity:ed5a8712cf16943840b99d43e16e92b19273583a743e7897a4be90e6b2f59da5`.

## Freshness And Role Isolation

The Population is zero-overlap against the historical exclusion set and between
the Capability and Reachability roles on all nine v26.89 channels:

```text
source_task_artifact_id
source_task_semantic_signature
source_task_hash
evidence_id
evidence_version_id
source_record_id
semantic_source_id
task_package_id
job_id
```

The exclusion audit covers 156 historical task records and 1,200 historical Job or
Recovery-Job identities. The selected Population contains zero Jobs because this is
a static task-rematerialization stage. It also has zero Evidence, Evidence Version,
or source-record reuse across the two new roles.

The freshness audit identity is
`finance_v26_budget_feasible_role_freshness:d5f55e5bfed81134bbc6d88204ff7738d38245ccadb175c8b8668146a2b45f50`.

## Prospective Task Redesign

The v26.89 static failure reflected the combination of long Program dependencies,
repeated public context, Observation projection, and conservative request bounds.
It did not identify any one factor as the sole cause. v26.90 therefore makes a
prospective dependency-shape change under fresh identities instead of patching an
exposed task.

For each selected source task, the builder chooses an independently executable
leaf Operation with exactly two public Evidence inputs and no Program dependency.
It then:

- binds only those two Evidence records into a fresh Evidence Bundle and Public
  Corpus;
- independently executes and verifies the one-node Program;
- derives a closed Answer Projection and exact output schema;
- reconstructs the mechanism-specific public and private state contracts;
- builds the Public Operation, action-neutral repair, Stop Readiness, exact
  terminal-verification target, Environment, and Verifier v2 binding; and
- freezes the role TaskPackage identity only after all required static path proofs
  pass.

The source task identity remains part of the new package lineage and all source
freshness channels remain enforced. The dependency reduction is a new experimental
object, not a retrospective reinterpretation of an exposed task.

## Compact Public Prompt Contract

The new `compact_budget_prompt.v1` representation preserves the public semantic
contract while avoiding full transcript replay on every decision. It retains:

- the task instruction, answer schema, and public retrieval selectors;
- public symbolic variables and their record semantics;
- remaining Program nodes, dependencies, operators, and output schemas;
- public action-neutral repair and exact terminal-verification contracts;
- selected public facts, operation outputs and references, typed failures, and the
  current unresolved public state; and
- exact Stop Readiness and final-answer permission.

The projection removes content-addressing and replay telemetry from the model view,
drops superseded search candidates after acquisition, and omits consumed
acquisitions once the dependency-bound operation frontier is reached. It does not
expose Oracle state, target Evidence, expected arguments, required next tools,
correct operators, repair patches, or private mechanism fields.

The compact representation is statically executable because the Compiler paths
close and Replay. It is not yet empirically shown to be usable by the thinking model.
That distinction is the reason the next stage is a calibration preflight rather than
Capability or Reachability execution.

## Thinking-Mode Binding

Every prospective model-bearing identity is bound to the future-only policy:

```text
thinking.type = enabled
```

The bindings are:

- policy:
  `prospective_thinking_mode_policy:b9ba7be1e8ee2ab343e31fe57b3c50cbbd604abf26b3da4297f5ad76dfbb158f`;
- model configuration:
  `agent_model_config:727b3867544c4eac844eb260b9673dee41be7b8787b07ea2e3d6c69113e68bd1`;
- policy/model binding:
  `prospective_thinking_model_binding:51315bb03b5df2751c0cfada843fc75627c45b544d26efdd9ddac746a780f77d`.

The build verifies this binding before any hypothetical client construction. No
client is permitted in v26.90. Future reasoning tokens remain completion Usage and
must fit the unchanged 4,096-token completion bound. Private reasoning content may
not be persisted; only presence, length, and Usage telemetry may be retained.

## Static Budget Certification

Every rendered request uses the exact frozen v26.89 arithmetic:

```text
prompt_upper_bound  = UTF-8 prompt bytes + 256
request_upper_bound = prompt_upper_bound + 4,096
prefix_bound(k)     = sum(request_upper_bound[0:k]) + current_required_reserve(k)
```

The current required reserve is the unchanged 4,096-token Contract-repair reserve
plus the 4,096-token final-answer reserve where the request kind requires both. A
path passes only when every Prompt is at most 60,000 bytes and every prefix bound is
at most 120,000 tokens.

All 48 paths pass. The cell-level certified ranges are:

| Role | Mechanism | Public path | Requests | Certified upper bound |
| --- | --- | --- | ---: | ---: |
| Capability | Context | structured_direct | 6 | 58,397-58,649 |
| Capability | Recovery | structured_direct | 7 | 71,071-71,495 |
| Capability | Reconciliation | structured_direct | 8 | 88,696-88,700 |
| Capability | Stopping | structured_direct | 6 | 57,634-58,093 |
| Reachability | Context | structured_direct | 6 | 59,796-59,991 |
| Reachability | Context | search_then_structured | 8 | 82,392-82,707 |
| Reachability | Context | search_then_open | 8 | 82,916-83,231 |
| Reachability | Recovery | structured_direct | 7 | 71,639-71,798 |
| Reachability | Recovery | search_then_structured | 9 | 94,364-94,548 |
| Reachability | Recovery | search_then_open | 9 | 94,453-94,637 |
| Reachability | Reconciliation | structured_direct | 8 | 89,412-89,816 |
| Reachability | Reconciliation | search_then_structured | 10 | 114,250-114,814 |
| Reachability | Reconciliation | search_then_open | 10 | 115,048-115,612 |
| Reachability | Stopping | structured_direct | 6 | 58,495-58,696 |
| Reachability | Stopping | search_then_structured | 8 | 80,468-80,710 |
| Reachability | Stopping | search_then_open | 8 | 80,992-81,234 |

Across all paths, the minimum certified upper bound is 57,634, the maximum is
115,612, and the smallest headroom is 4,388 tokens. The largest rendered Prompt is
8,438 bytes. These are conservative certification bounds under the frozen method,
not expected Provider Usage, observed model behavior, or permission to weaken the
resource contract.

## Compiler, Verifier, And Admission Controls

The 48 static paths produced 48 Compiler Witnesses and 276 deterministic local
Observations. All paths passed:

- complete public execution and exact terminal verification;
- Verifier v2 Replay;
- independently assembled non-Replay checks;
- the shared completed-trajectory scorer and trace sidecar;
- Operation Closure and mechanism necessity; and
- role-specific operational admission.

The 24 task-level Operation Closure, mechanism-necessity, authority, and admission
audits all pass. The Compiler artifacts are model-hidden static fixtures and
contribute zero empirical rows, zero State Mapping rows, and zero releases.

## Destructive Preflight

All 11 prospective mutations fail closed:

- four thinking-policy mutations: missing, disabled, differently cased, and
  structurally extended values;
- four Prompt-projection mutations: Oracle, target Evidence, expected arguments,
  and an action-binding exposure flag; and
- three role-package mutations: Reachability role swap, path ablation, and stale
  content-addressed identity.

The destructive audit identity is
`finance_v26_role_destructive_preflight:fe227323dea3dbee5debe86f02f419ec3257258fa95252ea9e7971bd4187add6`.

## Determinism And Validation

Formal and independent builds used the same frozen run identity and selection salt
in separate output directories. All 25 output files, including the report, are
byte-identical. Both builds replayed the same 57 source files and made zero API calls
and zero GPU jobs.

The initial v1 static build remains immutable and is superseded. Package-wide Mypy
found seven local inference diagnostics because one selector variable name was
reused for two differently typed dictionaries after the focused source check had
passed. The v2 successor gives the dictionaries distinct local names and changes no
runtime value. All 24 scientific detail files are byte-identical across v1 and v2;
only the source-bound report identity changes. Package-wide Mypy then returns to the
single pre-existing v26.70 source-bound diagnostic.

The focused regression contains nine tests covering dual-build determinism, static
authorization boundaries, pre-outcome source capacity, nine-channel freshness,
role/path denominators, exact request arithmetic, Prompt noninterference, thinking
binding, destructive mutations, and the 32-Job Clopper-Pearson boundary. Adjacent
thinking, budget-closed, and Budget Adequacy regressions also pass. Final validation
is 9 focused tests in 16.69 seconds, 32 adjacent tests in 55.21 seconds, and 1,053
passed plus four expected skips in the 803.23-second full suite. Repository-wide
Ruff passes. Mypy checks 386 source files and reports only the retained v26.70
source-bound local-list annotation diagnostic.

## Interpretation

v26.90 establishes:

```text
Budget Compliance                       retained
fresh role task capacity                passed
static Capability path feasibility      12 / 12
static Reachability path feasibility    36 / 36
thinking-mode identity binding          passed
empirical Budget Adequacy                not established
model completion usability              unmeasured
Capability / Reachability execution     forbidden
production Contribution                 0
```

The result does not show that the model will follow the compact grammar, stay within
the certified path, avoid failed-action loops, complete the Program, or produce a
valid answer. It only establishes that the registered complete public paths can be
certified within the unchanged resource contract before a model call.

## Next Permitted Stage

The only permitted transition is:

```text
thinking_budget_calibration_preflight_only
```

That stage may freeze a fresh, disjoint, thinking-enabled budget-calibration
Population, Contract, and Job Manifest and run credential-free preflight checks. It
may not execute the calibration. A later authorized execution must contain at least
32 independent Jobs and satisfy a one-sided 95% Clopper-Pearson typed no-call upper
bound at or below 0.10. At the minimum denominator of 32 Jobs, zero no-calls passes
with an upper bound of approximately 0.08937, while one no-call fails with an upper
bound of approximately 0.13985.

The calibration Population and Jobs must be disjoint from both v26.90 role
Populations and all historical empirical identities. Calibration rows cannot enter
Capability, Reachability, State Mapping, release, or production denominators.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student
training, Exact Target, GP-C, and production Contribution remain forbidden.

## Authoritative Artifacts

- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/report.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/source_capacity_audit.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/source_freshness_audit.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/budget_feasible_role_task_packages.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/compact_prompt_contracts.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/budget_qualified_path_audits.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/thinking_mode_binding.json`
- `artifacts/vtdo_experiment/finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/destructive_preflight_audit.json`
