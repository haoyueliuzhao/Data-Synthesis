# Finance v26.88-v26.89 Budget Adequacy Audit And Contract Preflight

Experiment and audit date: 2026-08-20

## Scope

This report records the credential-free transition authorized after the passing v26.86 online
Instrument result and the independent v26.87 audit. It answers two separate questions:

1. why 24 of the 32 v26.86 Jobs ended at a correctly enforced
   budget_exhausted_no_call terminal; and
2. what static Budget Adequacy and Runner-completion prerequisites must hold before fresh
   Capability or Reachability role protocols can be materialized.

The work does not rerun, rescore, or reclassify any historical Job. It does not use historical
model outcomes to select a task. It makes no model API call, constructs no online model client,
and uses no GPU. The eight v26.82 tasks are used only as already exposed compiler fixtures. They
remain ineligible for future empirical task selection and contribute zero empirical rows.

The authoritative inputs are:

- v26.86 Recovery report:
  finance_v26_budget_recovery_report:4afbad8525b598269630912e79048490dbe4e3235d8789aad0f10b922798c4ea;
- v26.87 independent audit:
  finance_v26_budget_closed_postrun_audit:a7318da72819ce66bdc93ab5117faec5f9f59b32aebd33f5324f2198bd705939;
- v26.82 compiler-fixture Population:
  finance_v26_budget_closed_verifier_bound_instrument_population_report:9f60f8d7c7522a1fd934bb5a7cdfefb2c91becc73f7e68b2f815dea352ad6484;
- Provider budget Contract:
  provider_token_budget_contract:27e7e524cb3139b9dd29b1ca7f2c7eae1956c96af8a982524f814b3ef4415150;
- qualified Verifier v2 report:
  finance_v26_authority_verifier_qualification:f61be6be022c2c8506e818e3bb9690e71fa316c6820fec69458c7ab7c8fa7bb1.

## v26.88 Root-Cause Audit

### Method

v26.88 replays 545 source and experiment files before computing diagnostics. It consumes the
frozen v26.86 Raw Executions, rollout aggregate, rollout diagnostics, task records, and Provider
budget Contract. For every one of the 32 Jobs it reconstructs:

- Provider Usage before denial;
- every attempted request kind;
- Prompt UTF-8 bytes and certified Prompt token upper bound;
- completion, Contract-repair, and final-answer reserves;
- projected request total, headroom, and deficit;
- Program nodes completed before the terminal;
- successful and failed Observation counts;
- repeated call signatures and repeated failed-call signatures;
- mechanism, task, and Recovery role.

The audit treats Prompt reset and reserve removal only as arithmetic diagnostics. Neither is a
causal intervention, and neither can authorize a budget or contract change.

### Denial Anatomy

The complete denominator remains 24 typed no-calls and 8 model-invalid trajectories. Every denied
request is a decision request:

| Denial attribution | Jobs |
| --- | ---: |
| Required reserve unavailable | 16 |
| Next request upper bound exceeds remaining budget | 8 |
| Prompt byte ceiling | 0 |

The observed ranges are:

| Diagnostic | Minimum | Median | P90 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Provider tokens before denial | 72,689 | 76,881 | - | 79,489 |
| Denied Prompt bytes | 35,859 | 37,528 | - | 39,494 |
| Prompt growth from initial Prompt | 16,716 | 17,947 | - | 20,490 |
| Certified headroom deficit | 1,755 | 7,503 | 9,082 | 9,333 |

Sixteen denied requests would fit if required reserves were removed. All 24 would fit under the
diagnostic counterfactual that replaces the denied Prompt byte count with the initial Prompt byte
count. These arithmetic observations do not show that reserve removal or Prompt reset would
complete a trajectory. The frozen Runtime required the reserves, and a successful next call would
not imply Program completion.

The smallest common ceiling that would fit only the observed next denied requests is 129,333
tokens. It is not a completion budget, a causal estimate, or authorization to increase the
120,000-token ceiling.

### Program Position

The no-call rows were generally not one final answer away from completion:

| Program position at denial | Jobs |
| --- | ---: |
| Zero registered Program nodes completed | 21 |
| Positive but incomplete Program progress | 3 |
| Terminal node completed but unverified | 1 |
| Verified and Stop-ready | 0 |
| Final-answer-only candidate | 0 |

The 24 no-call rows contain 57 failed Observations, 43 repeated call signatures, and 25 repeated
failed-call signatures. These counts are descriptive. They support studying Prompt growth,
failure-loop structure, and task dependency shape, but do not establish a single causal mechanism.

The mechanism partition is:

| Mechanism | No-call / 8 | Request-bound | Reserve-bound | Zero-progress no-call |
| --- | ---: | ---: | ---: | ---: |
| Context-conditioned Action | 7 | 5 | 2 | 5 |
| Semantic Reconciliation | 8 | 3 | 5 | 7 |
| Failure Recovery | 1 | 0 | 1 | 1 |
| State-dependent Stopping | 8 | 0 | 8 | 8 |

This is a strong mechanism-dependent pattern in the observed tasks. It is not a general
mechanism-level estimate because the Population has only two exposed tasks per mechanism.

### v26.88 Decision

v26.88 retains the passing v26.86 budget-compliance result but rejects budget adequacy:

~~~text
budget_compliance_retained = true
budget_adequacy_established = false
direct_budget_increase_authorized = false
prompt_compression_authorized = false
reserve_reduction_authorized = false
next_permitted_stage = fresh_budget_adequacy_contract_and_static_role_preflight_only
~~~

Its authoritative identities are:

- source replay:
  finance_v26_budget_adequacy_source_replay:07249627d9ee2d16462a67267a4a20c7c29ec57c573427595b043837d2cc7cd9;
- root-cause audit:
  finance_v26_budget_adequacy_root_cause:7b925454b3335cec4f0a7c4fe5baf4a78bdb8004b9714ecbc0d068637c7bbd5e;
- group audit:
  finance_v26_budget_adequacy_group_audit:96b99a5dae319c37fcc5cf9a663288b6b913ce703e7ab200dcc03f5a513b93c6;
- decision:
  finance_v26_budget_adequacy_decision:ad12e014992c31e995e981af1de3cfabf0425595491f5b31ad0e29a9465927a6;
- report:
  finance_v26_budget_adequacy_root_cause_report:bfc54e2c179a475e6f7e6996d844cf4df2e162094668e51e701dd4ce8385ae3f.

Formal and independent v26.88 builds reproduce all five files byte for byte.

## v26.89 Budget Adequacy Contract

v26.89 freezes a prospective Contract without changing the Provider budget:

| Bound | Frozen value |
| --- | ---: |
| Rollout token ceiling | 120,000 |
| Prompt byte ceiling | 60,000 |
| Completion upper bound | 4,096 |
| Provider chat-envelope upper bound | 256 |
| Contract-repair reserve | 4,096 |
| Final-answer reserve | 4,096 |

The Contract requires one Budgeted Public Witness for every Capability task and three
budget-qualified public paths for every Reachability task. All three Reachability paths must use
the same Provider budget Contract. A resource terminal remains in its role denominator and remains
ineligible for independent validity, State Mapping, or release.

Static full-path accounting is:

~~~text
prefix_bound(k)
  = sum(request_token_upper_bound[0:k])
  + required_reserve_tokens[k]
~~~

A path qualifies only if every Prompt is below 60,000 bytes and every prefix bound is at most
120,000 tokens. Synthetic fixture Usage is excluded from this calculation.

The Contract prospectively selects a maximum no-call rate of 0.10. Admission requires the
one-sided 95% Clopper-Pearson upper confidence bound to be at most 0.10 on an independent
calibration Population with at least 32 Jobs. This threshold is a normative operational design
choice made without using the v26.86 no-call outcomes. At the minimum denominator, zero no-calls
would have an upper bound of approximately 0.08937. No such calibration has been run.

The Contract explicitly forbids:

- direct increase of the 120,000-token ceiling;
- relaxation of the 60,000-byte Prompt ceiling;
- reduction of the completion bound or required reserves;
- combining Capability and Reachability denominators;
- historical-outcome task selection;
- empirical use of Compiler fixtures.

Its identity is:

finance_v26_budget_adequacy_contract:e3f16d80ca6953dcb77c7e153df5b8881c16fd1bec60240e3285168543db3cfe.

## Complete Runner Controls

The v26.86 online run had no completed trajectory, so v26.89 adds a credential-free completed
Runner control. Each of the eight exposed v26.82 Compiler Witnesses drives the actual
IterativeAgentSolver, public Finance Runtime, pre-call budget wrapper, and Raw Execution
persistence under a fresh control identity. Raw Execution is written and reloaded before Replay
or scoring.

The frozen control order is:

~~~text
Compiler Witness
-> Raw Execution persistence
-> Verifier v2 Replay
-> independent non-Replay scoring
-> shared completed-trajectory scorer
-> schema-closed trace sidecar
-> report aggregation
~~~

The local fixture Usage rule is a deterministic byte-derived test value. It exists only to drive
the control path and is explicitly excluded from budget-adequacy evidence and empirical counts.

The results are:

| Control item | Passed |
| --- | ---: |
| Raw Execution persistence and reload | 8 / 8 |
| Verifier v2 Replay | 8 / 8 |
| Independent non-Replay Gate agreement | 8 / 8 |
| Shared completed scorer | 8 / 8 |
| Schema-closed trace sidecar | 8 / 8 |
| Report aggregation | 8 / 8 |

The controls contain 96 local fixture calls, 10 to 13 per task. All tool calls and public results
match the corresponding Compiler Witness. Every completed score is a valid compiler_fixture, is
Instrument-admitted as a control, and is excluded from empirical denominators. Historical
empirical Job overlap and empirical row contribution are both zero.

The authoritative Runner control audit is:

finance_v26_budget_adequacy_runner_control_audit:3275551e0df1085131e107fc17a240a8699e8b10ee9d0e339a8adcc8a56e034d.

## Static Witness Budget Result

All eight control Prompts remain individually below the 60,000-byte ceiling. None of the eight
complete paths satisfies the new conservative full-path bound:

| Mechanism | Tasks qualified | Static path upper-bound range |
| --- | ---: | ---: |
| Context-conditioned Action | 0 / 2 | 569,189 to 575,686 |
| Semantic Reconciliation | 0 / 2 | 366,569 to 366,574 |
| Failure Recovery | 0 / 2 | 547,890 to 553,491 |
| State-dependent Stopping | 0 / 2 | 495,845 to 498,667 |

The overall result is:

~~~text
individual_prompt_ceiling_pass = 8 / 8
complete_static_witness_budget_pass = 0 / 8
minimum_complete_path_upper_bound = 366569
maximum_complete_path_upper_bound = 575686
inherited_120k_budget_adequacy_established = false
~~~

These path bounds are deliberately conservative diagnostics under the frozen accounting rule.
They are not estimates of expected Provider Usage and do not authorize increasing the rollout
ceiling to any observed value. The current tasks are already exposed and are not candidates for a
future role Population in any case.

The authoritative static audit is:

finance_v26_budgeted_public_witness_audit:a202dbd97e1959d4bdf671d81188233934c090aa5aa8501a057e7adc7b797ccb.

## Role Protocol Preflight

v26.89 retains separate prospective role denominators:

| Role | Fresh tasks | Static paths | Prospective Jobs |
| --- | ---: | ---: | ---: |
| Capability Development | 12 | at least 1 per task | 96 |
| State Reachability | 12 | exactly 3 per task | 360 |

Capability remains four mechanisms, three fresh tasks per mechanism, and eight unconditional
replicas per task. Reachability remains 36 static States, 144 natural attempts, and 216
state-conditioned attempts. These are design denominators only.

No fresh task has been materialized. No independent 32-Job budget calibration has been run. The
v26.82 Instrument-only fixture catalogs contain zero Reachability paths. Therefore neither role
Contract nor role Manifest is materialized, and the role preflight is blocked.

The role preflight identity is:

finance_v26_budget_adequacy_role_protocol_preflight:c10c62c9d0c9af295503ce4514d7bf17ba29a54b07839d31ecb38f3c6fbd2ca3.

## Decision

v26.88 localizes the observed budget denial structure. v26.89 closes the previously unexercised
completed Runner control path, but independently shows that the inherited 120,000-token Contract
does not qualify any complete current Compiler Witness under the new static full-path accounting
rule.

This combination supports one narrow transition:

~~~text
fresh_budget_feasible_role_task_rematerialization_only
~~~

A successor may materialize fresh, identity-incompatible Capability and Reachability task
Populations. Before any role Contract or Manifest is frozen, every Capability task must pass its
Budgeted Public Witness, every Reachability task must pass three same-budget public paths, and the
freshness audit must show zero overlap on source task, semantic signature, source hash, Evidence,
Evidence Version, source record, Semantic Source, TaskPackage, and Job identity.

The successor may redesign task dependencies, public Prompt representation, observation
projection, and certified token-bound methodology. It may not relax a frozen bound or use an
empirical result to select among post-outcome designs. A later independent budget calibration is
required before Capability or Reachability execution can be authorized.

Capability Development execution, State Reachability execution, Fresh Confirmation, No-C VTDO,
Student training, Exact Target, GP-C, and production Contribution remain forbidden. Production
Contribution remains zero. Objective Support remains a separate unresolved bottleneck.

The authoritative v26.89 report is:

finance_v26_budget_adequacy_contract_preflight_report:805432345e0fb8db286daaa80bbbf49b509857eb89861af88086db20ccc8c71f.

Formal and independent v26.89 builds reproduce all fourteen files - five detail files, eight Raw
control files, and the report - byte for byte. Both replay 551 source and experiment files and use
zero API calls and zero GPU jobs.

## Artifacts

- artifacts/vtdo_experiment/finance_v26_88_budget_adequacy_root_cause_audit_20260820/
- artifacts/vtdo_experiment/finance_v26_89_budget_adequacy_contract_and_static_role_preflight_20260820/
