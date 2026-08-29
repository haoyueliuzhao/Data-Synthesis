# Finance v26.174 Joint Presentation, Mechanism Semantics, Receipt, And Runner Parent Hardening

Audit date: 2026-08-29

## Decision

Finance v26.174 consumed only:

```text
capability_observation_joint_presentation_mechanism_semantics_receipt_and_runner_parent_hardening_only
```

The stage made zero Provider calls, zero Stage 2 Provider calls, zero Development Jobs, zero
Confirmation payload reads, zero GPU jobs, zero Mapper or State operations, and zero empirical
frequency, Contribution, VTDO, Student, training, release, or production rows.

The v26.173 Runner-preflight transition was blocked before execution. This stage repairs the four
surfaces authorized by the external audit:

1. joint model-visible presentation;
2. family-specific Mechanism semantics;
3. exact pre-Prompt Failure Receipt lifecycle;
4. Development Contract and Runner denominator parent closure.

The resulting evidence is credential-free static and local Runtime evidence. It is not a Runner
preflight, model result, empirical capability boundary, or universal noninterference proof.

## Authorization And Predecessor Freeze

The external review is bound at exactly 24,817 bytes and SHA-256:

```text
2126448be1e81aacb52a02f3c31515cb7f5c6547d92a656b99a16e9da8e6aa56
```

All 21 authoritative v26.173 files remain immutable. Before loading the replacement design,
v26.174 independently rebuilt all 21 files into an empty temporary directory and matched each
file byte for byte. Historical mutation, reclassification, and Runner execution counts are zero.

## Independent v26.173 Defect Reproduction

The formal defect audit independently reproduces the external review rather than treating it as an
outcome oracle.

### Joint presentation leak

```text
target States                                             80
six-Replica presentations                                480
three-Choice States                                       66
two-Choice States                                         14
three-Choice presentations                               396
(action rank + Candidate position) mod 3 recovery    396/396
(display rank + Legend position) mod 3 recovery      396/396
```

### Mechanism regression

All 146 legal single-Choice nonreference executions were rerun through the frozen v26.173
Runtime:

```text
rejected / Base false / Mechanism false                    20
accepted / Base false / Mechanism false                   102
accepted / Base true / Mechanism false                     24
nonreference Mechanism-qualified                            0
```

The 24 Base-valid/Mechanism-false rows split into six Context, four Reconciliation, fourteen
Recovery, and zero Stopping rows. The same-Rule noncanonical Recovery surface is 20 rows, with
14 Retry successes and 14 Base-valid outcomes, but zero old Mechanism or Qualified outcomes.

### Failure Receipt mismatch

```text
Recovery Prompts                                         120
Prompt receipts with rule_handle                           0
Prompt receipt identity equal to Runtime receipt            0
Runtime-internal failure/retry receipt lineage            120
```

Across twenty reference Recovery Components, deleting the old receipt, changing its hash, or
changing its error remains accepted 20/20 under v26.173. Explicitly inserting a wrong Rule is
accepted 0/20.

### Parent and denominator gaps

The old validators accept six fully rehashed Development parent replacements, seven fully
rehashed Runner parent replacements, and one 32-row Runner duplicate/drop denominator with only
31 unique Package and source identities.

These are historical validator diagnostics. No v26.173 artifact or label is changed.

## Joint Presentation Hardening

The replacement public table assigns one Replica-local opaque alias to every exact
`Choice x field`. Equal semantic values may have distinct honest aliases that decode to the same
semantic value. This removes the old coupling created when repeated semantic values were forced to
share one visible rank.

Candidate position, action-ID rank, Legend position, display-handle rank, and each visible value
rank use fixed pre-outcome schedules. The schedules were selected without model outcomes and are
checked for every exact six-Replica State stratum.

The registered Gate covers:

- every univariate rank constant;
- all pairwise affine rules modulo Choice count;
- all pairwise less-than, equality, and greater-than relations;
- visible pair cross-order minima and maxima;
- value-rank sum, range, and median minima and maxima;
- every 1-4 visible value-field prefix present in the exact Catalog.

The exact audit is:

```text
State strata                                             80
presentations                                           480
displayed Candidate rows                              1,356
registered rule evaluations                          23,918
univariate evaluations                                1,452
pairwise evaluations                                 21,986
value-vector evaluations                                480
strata above 6 / Choice-count baseline                    0
```

Both previously perfect joint rules fall from 396/396 to 0/396. Marginal rank imbalance,
stable cross-Replica value vectors, unique encoded-operation lengths, and visible padding counts
are zero.

This is a registered low-order structural control. It does not claim independence from every
possible function of the full Prompt.

## Mechanism Semantics Restoration

`reference_path_match` remains an exact diagnostic. It is not a Mechanism Gate.

The Runtime now applies family-specific causal predicates:

- Context requires a real current-state decision and task closure; immaterial record order is not
  a mechanism failure.
- Reconciliation requires real normalized-reference emission and consumption plus task closure.
  Fixed support operations are attributed to an exact target Component only when that Component
  exists; lower-depth nuisance support remains unassigned.
- Recovery requires the same Rule and exact Failure Receipt, a changed selector, a successful
  Retry, correct temporal order, and task closure. It does not require one canonical selector.
- Stopping requires Runtime-derived readiness, verified stop, and no postcompletion call.

The complete new 146-row nonreference surface is:

```text
accepted nonreference rows                              126
Base-valid nonreference rows                             24
Mechanism-qualified nonreference rows                    32
Qualified-valid nonreference rows                        24
Base-valid but Mechanism-false rows                       0
```

The 32 semantic Mechanism rows comprise the 24 Base-valid rows plus eight task-invalid
mechanism-occurrence diagnostics. All six Context, four Reconciliation, and fourteen Recovery
Base-valid noncanonical rows are Mechanism-qualified. On the twenty same-Rule noncanonical
Recovery rows, fourteen Retry, fourteen are Base-valid, fourteen are Mechanism-qualified, and
fourteen are Qualified-valid. All twenty wrong-current-Rule rows still reject before Retry.

All 192 local reference executions remain Base-, Mechanism-, and Qualified-valid.

## Exact Failure Receipt Lifecycle

For every Recovery Component, the Runtime order is now:

```text
initialize or reached predecessor state
  -> execute the real coarse selector
  -> persist exact typed failure event
  -> derive exact public Failure Receipt
  -> render the current Prompt with that Receipt
  -> validate the selected revision against the same Receipt
  -> Retry on the retained Runtime
```

The exact receipt binds:

```text
receipt_id
rule_handle
failed_selector_hash
error_code
source_tool_id
failure_event_id
```

Missing fields receive no defaults. A mismatched receipt emits typed rejection and no Retry.

Across all 120 Recovery Prompts:

```text
real failure before Prompt                               120
complete model-visible exact Receipt                     120
Prompt / Runtime receipt identity match                  120
failure / Retry receipt identity match                   120
Rule / selector hash / error / Tool matches              120 each
```

For twenty exact source Components, missing Receipt, changed identity, error, selector hash, Tool,
or Rule each reject 20/20. Retry after those rejections is zero.

## Step Runtime

The production API remains:

```text
initialize
render_next_prompt
step
finalize
```

The local reference fixture records:

```text
Packages                                                  32
Replica executions                                       192
current Prompt renders / steps                           480
public Observations                                      480
actual Runtime events                                  1,104
predecessor-conditioned Prompts                          288
bound predecessor receipt links                          480
pre-Prompt Recovery failure events                       120
Retries consuming the exact visible Receipt              120
finalizations                                            192
Qualified reference executions                           192
```

Complete baseline Result loads, baseline-event filtering, static reference Trace inputs,
precommitted Choice vectors, future Prompt access, Provider calls, and Development Jobs are zero.

## Contract And Runner Denominator Parent Closure

Each Development Package identity now binds all exact source and prospective parents, including:

- v26.171 source Package, Package ID, group, Finance Core, capability, depth, and public Task;
- exact v26.173 predecessor Package;
- topological Component sequence and reference-path diagnostic;
- Joint Presentation, Mechanism Semantics, Failure Receipt, Step Runtime, Parent Closure, and
  Sequential Estimand Contracts.

The independent validator recomputes the Package ID from those authoritative objects before
replaying all six Results.

The Runner Input Catalog has 32 rows, 32 unique Runner Package IDs, 32 unique source artifacts,
and 32 unique source Package IDs. Its source sets equal the Development Catalog sets exactly.
Missing, duplicate, and extra counts are zero. Every Package-level Contract equals the
authoritative top-level Contract.

The parent audit independently closes:

```text
Package reconstructions                                  32
Prompt / mapping / operation / Observation rows          480 each
receipt parents                                          480
Mechanism reports                                        192
Package identity recomputations                           32
public Task identity matches                              32
authoritative Contract bindings                          192
Runner topology matches                                   32
```

Sixteen fully rehashed parent attacks all reject:

- six Development Contract replacements;
- one Development public-Task cross replacement;
- six Runner Contract replacements;
- one Runner source-Package replacement;
- one Runner source-Development-Catalog replacement;
- one Runner duplicate/drop denominator.

The complete production destructive audit rejects 31/31 mutations.

## Sequential Estimand Boundary

The future schema remains registered without empirical values:

- per-step conditional success;
- first failed target Component;
- Component-specific hazard;
- complete Package success;
- task Base plus Mechanism qualification.

D0-D3 remain bounded sequential target-decision depth. No latent ability boundary or success
monotonicity is inferred. A future Runner must report reached denominators and first-failure
locations, not only final Qualified counts.

## Formal Artifacts

The formal Root is:

```text
artifacts/vtdo_experiment/
finance_v26_174_joint_presentation_receipt_hardening_v1_20260829
```

It contains 23 files and 12,543,211 bytes. The report SHA-256 is:

```text
1d25c9744239507283ad37c99f2f554eb6de8360f64e2da3c97789524279b882
```

The transitive source Root contains 320 files with zero unresolved imports.

Authoritative identities:

- report:
  `finance_v26_joint_presentation_receipt_hardening_report:5ccb857fb6b1f7f0a90b0137162b1dd0e66f1c40970da9a5005c405d7f9ea4ae`;
- source Root:
  `finance_v26_joint_presentation_receipt_transitive_source_root:26d1400d2d16c5978e3205d040455b3e7cd0b2bb1889bcb228ae9f71bcbf7c08`;
- Joint Presentation Contract:
  `joint_presentation_contract:714a7975a85703db3313df8afe5b2c2631c89c0bc49b6decba5844c8db215be9`;
- Mechanism Semantics Contract:
  `family_specific_mechanism_semantics_contract:3e8696eba72885964206408800ec9548036392a341364a9ab17d6a4f5e4eddcf`;
- Failure Receipt Contract:
  `exact_failure_receipt_lifecycle_contract:a3dc7a12081a4eec699afc131c9809b603b5dad2846e1dde47501724a6be3263`;
- Step Runtime Contract:
  `production_step_runtime_contract:41b915f9e74b88153131f8b70faeb4cea20f04da9c89f7803c542f83d5dd34a2`;
- Parent Closure Contract:
  `contract_denominator_parent_closure_contract:8469e13b0f5283ac949b8ab4cf62749a86922c80da420a6094c4d04d5d55cd43`;
- Sequential Estimand Contract:
  `sequential_depth_estimand_contract:bfbd40cc175e39a84a6cfa63c4c28e9ab82cab460371c56c4b887132ea48190e`;
- Development Catalog:
  `finance_v26_joint_presentation_receipt_development_catalog:111c84e073354ac50ea3dab8bdbf66b3737caa3290565cf2bbadc91c22b58918`;
- zero-Prompt Runner Input Catalog:
  `finance_v26_joint_presentation_receipt_runner_input_catalog:cf80c22f28066b61693231ab1e4c613430d8439b0cdb168354759524f09b40a3`;
- Joint Shortcut audit:
  `finance_v26_joint_presentation_shortcut_audit:ba16ad4cdf9baead849bd0c79b8201b62e1cb2fc41c5d03fd678e332db1b5c08`;
- Mechanism Semantics audit:
  `finance_v26_family_specific_mechanism_semantics_audit:280c451e13764b459a2101ddf4f9139e766245d2f5065915c1c2dd8465407538`;
- Failure Receipt audit:
  `finance_v26_exact_failure_receipt_lifecycle_audit:ca84e9ab537e038619c5dc2ed0f9de44cdf2de286cb715093b98cedf7536bcc4`;
- Parent Closure audit:
  `finance_v26_contract_denominator_parent_closure_audit:e2901edc728092c849c80ccd7cae9eb2c2091a6b26755d7deb681a01a226a105`;
- static audit:
  `finance_v26_joint_presentation_receipt_static_audit:3d39c95e8229cc3825132f201dcd5373073c3b060ef32d12863f0f0097f42ce1`;
- transition:
  `finance_v26_joint_presentation_receipt_transition:de73144ef969ec641322947369e185a083875947172ffd5dfcc2a3ef58ac0592`.

## Validation

- focused v26.174 Pytest: 7/7 passed in 141.17 seconds, including one empty-directory
  23/23 byte-identical rebuild;
- adjacent v26.173 non-rebuild regression: 5 passed, 1 deselected in 10.23 seconds;
- focused PyCompile: passed on four modules and the test file;
- focused Ruff check and format check: passed;
- package-wide Ruff check over `src` and `tests`: passed;
- focused no-import-follow Mypy: passed on all four new modules;
- package-wide Mypy checked 549 source files and retained six diagnostics in four historical
  files, with zero v26.174 diagnostics.

Preliminary local attempts remain outside the formal Root. They failed closed before formal
output because of, respectively, a parent-surface cardinality typo, an invalid assumption that
Runtime events persist raw inputs, one two-field joint value-rank shortcut, two unassigned
Reconciliation support events, and a no-op public-Task mutation fixture. Each was corrected
without Provider calls, empirical rows, threshold relaxation, or deletion of a registered attack.

## Permitted Transition

The only permitted transition is:

```text
capability_observation_joint_neutral_state_bound_step_runtime_development_runner_preflight_only
```

A successor may materialize only the exact future 192-Job Development Manifest and perform a
credential-free one-current-Prompt-at-a-time Runner preflight from the exact v26.174 zero-Prompt
Runner Input Catalog. It must preserve every frozen source, Package, Component, Candidate,
Replica-local semantic alias, joint presentation schedule, exact Failure Receipt, family-specific
Mechanism predicate, Step Runtime, public Observation, validity, Contract, model/Thinking,
Grammar, Policy, resource, threshold, terminal, sealed receipt, and exact denominator binding.

Provider execution, Development outcomes, Confirmation payload loading, source/task/Component/
Candidate change, presentation or validity tuning, threshold change, historical rewrite,
Mapper, State, frequency, Contribution, VTDO, Student visibility, training, release, and
production remain forbidden.
