# Finance v26.147 Historical Capability Validity Decomposition Audit

Audit date: 2026-08-25

## Decision

Finance v26.147 consumed only the credential-free
`historical_capability_validity_decomposition_audit_only` transition frozen by v26.146.
It performs a read-only counterfactual diagnostic over the 93 complete v26.141 Capability Raw
model outcomes and a separate non-evaluable partition over the three v26.144 measurement-support
exits. It does not change a historical terminal, change a historical independent-validity label,
fill a missing model endpoint, modify a Verifier or Final Grammar, materialize a new Population or
identity chain, call a Provider, or create a Capability, Reachability, State Mapping, training,
release, or production row.

The audit passes its decomposition Gate. The only permitted successor is:

```text
verifier_vnext_contract_freeze_only
```

This authorizes a prospective Contract freeze only. It does not authorize Provider calls or a
new Capability experiment.

## Frozen Inputs

The exact direct predecessor is v26.146 report
`finance_v26_measurement_support_redesign_report:aa2d6a079ef8ebe97d7d10fa90a6fcfb844faa39310a26e2b4a1e8120bfa41c5`.
Its report SHA-256 is
`2df4d84df155c22a98760d831d31b0ed811d12ecdf182f1f4326881ea2d8a80d`, and its transition is
`finance_v26_measurement_support_transition:b72ddd97cb2440fea1eddb3553cefea584abc7168762c06321ba2a864ea5e982`.

Before loading a historical Raw row, v26.147 replayed 7,304/7,304 files:

```text
v26.146 transitive bindings             7,294
v26.146 direct formal outputs                9
v26.147 implementation                       1
total                                    7,304
```

It then rebuilt the complete nine-file v26.146 formal directory in an empty temporary directory.
Every file was byte-identical. The independently reconstructed predecessor still contains exactly
96 lineage endpoints, 93 historical model outcomes, seventeen historical valid labels, 76
historical invalid labels, and three support exits.

The historical model input is the immutable v26.141 execution directory. Every one of its 93 Raw
Executions was reparsed, rebound to its exact v26.140 Job and operational record, reprojected
through the historical result projector, and compared with its frozen checkpoint result. The
three non-model endpoints are the exact v26.144 Recovery results with terminal
`ordinary_replan_reference_unavailable`.

## Seven-Layer Boundary

The diagnostic keeps these scientific objects separate:

```text
M       measurement support available
O       complete model endpoint observed
R       Instrument integrity
P       privacy compliance
V_base  candidate prospective base trajectory validity
Q_mech  historical mechanism evaluator result, diagnostic only
V_qual  V_base and Q_mech
```

For all 93 complete Raw model outcomes, `M=O=R=P=true` and validity is diagnostically evaluable.
For the three support exits:

```text
measurement_support_available       false
model_endpoint_observed             false
validity_evaluable                  false
diagnostic_base_validity            null
diagnostic_mechanism_qualification  null
diagnostic_qualified_validity        null
```

The support exits do not enter any Base, Mechanism, or Qualified validity denominator. Their null
values are not converted to false.

## Historical And Diagnostic Tracks

Each complete Raw row retains both tracks:

```text
historical_terminal
historical_independent_validity
historical_verifier_report_id
historical_verifier_version

diagnostic_base_validity
diagnostic_mechanism_qualification
diagnostic_qualified_validity

historical_reclassified = false
counterfactual_diagnostic_only = true
state_mapping_eligible = false
```

The historical partition remains exactly seventeen `model_valid_trajectory` and 76
`model_invalid_trajectory`. Diagnostic values are new explanatory rows, not historical scores and
not empirical results under a new Contract.

## Diagnostic Vector

The audit independently records the requested layers.

Interface:

```text
Action ABI
Program closure
Terminal verification
Final ABI
```

Answer:

```text
exact JSON match after historical reference projection
recursive exact Decimal semantic match
reference-identity match with numeric leaves masked
prospective nested answer-schema match
```

Decimal semantics use exact `Decimal(str(value)).normalize()` behavior. No floating-point
tolerance is used. Across the 54 observed Final endpoints, 29 fail the old exact answer
projection. Eleven of those 29 become equal only after exact Decimal representation
normalization; they are representation differences, not permission to alter a historical label.

Support:

```text
operation lineage complete
required Evidence support complete
Runtime selected support complete
model Citation complete
verification support complete
```

The audit exposes a concrete historical responsibility mismatch. The old completed-result adapter
derived `cited_evidence_ids` from Runtime-selected public Evidence. All 54 observed Final rows pass
that old Runtime-derived citation check. The original model `answer` values, however, are flat
objects: 53 contain `difference` and `higher_ref`, and one contains `value`. None contains the
prospective `answer.result` plus `answer.citations` model language. Thus:

```text
old Runtime-derived citation complete     54/54
model-owned Citation complete               0/54
historical-valid rows missing model Citation 17/17
```

The audit retains the two sets as `historical_host_derived_cited_evidence_ids` and
`model_cited_evidence_ids`. Runtime support cannot satisfy model Citation.

Mechanism:

```text
context_mechanism_complete
reconciliation_mechanism_complete
recovery_mechanism_complete
stopping_mechanism_complete
```

Only the target mechanism field is non-null on a row. v26.147 recomputes the old mechanism
evaluator from each Raw Observation sequence and requires exact equality with the frozen
v26.141 mechanism outcome. The 75/93 mechanism-success count is therefore a historical-evaluator
diagnostic, not the future Verifier vNext `Q_mech` result.

Control:

```text
postcompletion_violation
noninterference_audit_bound
privacy_compliant
runtime_replay_passed
instrument_integrity
```

Noninterference is not hardcoded. Every row binds the frozen passing v26.140 artifact
`finance_v26_capability_prompt_noninterference:be222696fc6a7fa3b2a62065fd7e55020f175e8405db1e163d5f706ec1a896d8`.

## Counterfactual Candidate Result

The diagnostic candidate requires the complete interface, nested answer schema, exact Decimal
semantics, reference identity, lineage, Runtime support, model-owned Citation, verification
support, postcompletion control, noninterference binding, and privacy. Under that candidate:

```text
complete historical Raw model outcomes      93
diagnostic Base-valid                         0
historical mechanism diagnostic success      75
diagnostic Qualified-valid                    0
```

The zero Base and Qualified counts are caused in part by applying a prospective model-owned
Citation and nested answer-schema responsibility to historical outputs generated under a
different effective interface. They are counterfactual diagnostics. They do not show that model
Capability was zero, do not erase the seventeen historical valid labels, and cannot be compared
as an ability change.

Among the 76 historical invalid rows, the first diagnostic failure partition is:

```text
Action ABI                 1
Program closure           22
Terminal verification     10
Final ABI                  6
answer schema             37
total                     76
```

Every row retains all later diagnostic values even when an earlier layer fails. The partition is
a Funnel localization, not an exclusive causal attribution.

## Task-First Summary

The design contains twelve independent tasks and eight repeated rollouts per task. Task is the
primary sampling unit; rollout is a secondary repeated measure. v26.147 first reports each task
as `x/8`, while separately recording whether each of the eight design endpoints is a complete Raw
model outcome or a null support exit.

```text
Mechanism                    Tier       Raw+Exit  Hist  Base  Mech  Qualified
context_conditioned_action  easy        8+0      4/8   0/8   8/8   0/8
context_conditioned_action  frontier    8+0      4/8   0/8   8/8   0/8
context_conditioned_action  hard        8+0      0/8   0/8   6/8   0/8
failure_recovery            easy        6+2      0/8   0/8   6/8   0/8
failure_recovery            frontier    8+0      5/8   0/8   8/8   0/8
failure_recovery            hard        7+1      1/8   0/8   7/8   0/8
semantic_reconciliation     easy        8+0      0/8   0/8   5/8   0/8
semantic_reconciliation     frontier    8+0      1/8   0/8   5/8   0/8
semantic_reconciliation     hard        8+0      0/8   0/8   4/8   0/8
state_dependent_stopping    easy        8+0      0/8   0/8   7/8   0/8
state_dependent_stopping    frontier    8+0      2/8   0/8   5/8   0/8
state_dependent_stopping    hard        8+0      0/8   0/8   6/8   0/8
```

The `x/8` columns are descriptive design numerators. The three null exits are not failures and the
table is not an exact Capability estimate. The audit then aggregates task rows by Mechanism and
Tier; it never treats 96 rollouts as 96 independent tasks.

## Immutability And Destructive Controls

The historical immutability audit fixes all of the following at zero:

```text
historical terminal reclassification
historical validity reclassification
missing endpoint imputation
support exit in a validity denominator
diagnostic row promoted to empirical
prior lost attempt pooled
Verifier change
Final Grammar change
Provider and Stage 2 Provider calls
Capability, Reachability, or State Mapping rows
```

Twenty destructive mutations fail closed. They include historical relabeling, null-to-false
conversion, Runtime support used as model Citation, floating tolerance, hardcoded
noninterference, 17/93 or 17/96 as a Capability estimate, rollout-as-task aggregation, Provider
execution, new role identities, and early State Mapping.

## Reproducibility

The focused v26.147 Pytest suite passes 3/3 in 937.88 seconds. It independently rebuilds all ten
formal files and compares their exact bytes. The selected v26.146-v26.147 adjacent regression
passes 5/5 in 583.18 seconds. Focused Ruff and Mypy pass. Package-wide Mypy checks 467 source
files and retains only the three pre-existing v26.70/v26.129 diagnostics; v26.147 contributes
zero diagnostics.

Formal construction and every audit made zero Provider calls, zero Stage 2 Provider calls, and
zero GPU jobs.

## Authoritative Identities

- report:
  `finance_v26_validity_decomposition_report:fddc664b2d8e45788b0f7e55333041ed82e7dae62368e2b27d22ec8baa7a69a5`;
- source replay:
  `finance_v26_validity_decomposition_source_replay:7526462bc7b0240590b844f1dd00b26c7f9a06c245cbff9d60e40d195a0bc436`;
- predecessor integrity:
  `finance_v26_validity_decomposition_predecessor_integrity:abb2b764283a4999bbde3a0cf92268d7190c7f07e352079d7a5bd01a7f2cc4bb`;
- decomposition Catalog:
  `finance_v26_validity_decomposition_catalog:36229a89e5f7ea5e3de8b4f6453a6e0a14a4f96a10f25c6cfc4c717c1287b2d2`;
- task-level summary:
  `finance_v26_task_level_validity_summary:8fe9b61322b09cfb3880e55417aa84fab67f00d2b4307a4499c2e28c46c70d2d`;
- Mechanism/Tier summary:
  `finance_v26_mechanism_tier_validity_summary:ab608fb0e6bbfb8eaa85a944ffe31883cfbd1f85f42a2a6029665af4b744037c`;
- failure localization:
  `finance_v26_historical_failure_localization:73fa1e8e9f7c187a240f1c084e010a5d2bde0734b045cc8e9d217221dc6fcb0c`;
- historical immutability:
  `finance_v26_historical_validity_immutability:348105ea3241997448d19cb0e81ddd111abfdfa8e7e7d4c1cb09095afbaab22d`;
- destructive audit:
  `finance_v26_validity_decomposition_destructive:bbd966c94555fdfd353ff332efcee7515c894747235e237c3898976661469c86`;
- transition:
  `finance_v26_validity_decomposition_transition:e6ce3161658116772a3951f5823cada820e5bc7b911e9694dc6475d3ea43c9b2`.

## Permitted Transition

The only permitted transition is:

```text
verifier_vnext_contract_freeze_only
```

The successor may freeze a prospective answer-semantics core, the three Base/Mechanism/Qualified
Verifier reports, the exact model-owned Citation Final language, mechanism responsibility, and
artifact-bound noninterference. It must remain credential-free and must not reclassify a
historical row. Provider calls, a new Capability Population or identity chain, Capability or
Reachability execution, Reachability identity materialization, State Mapping, training, release,
and production Contribution remain forbidden.
