# Finance v26.171 Validity Separation, Presentation Deleak, And Causal Component Reaudit

Audit date: 2026-08-29

## Decision

Finance v26.171 consumed only:

```text
capability_observation_validity_separation_presentation_deleak_and_causal_component_reaudit_only
```

The external joint review is bound at exactly 26,048 bytes and SHA-256
`0a9e048bf1d83540185af60c64bb138a503a880689e8aeecf32efb5bec40f5b8`.
Credential lookup, Provider-client construction, Stage 1 Provider calls, Stage 2 Provider calls,
Development Jobs, sealed Confirmation payload access, GPU jobs, Mapper calls, State Assignment,
Contribution, and VTDO are zero.

The stage preserves all v26.170 bytes and independently binds all eighteen files in the
authoritative v26.170 v3 Root. It accepts the external conclusion that v26.170 repaired public
semantic sufficiency and real task execution, while reproducing the remaining validity,
presentation, causal-component, candidate-legality, and parent-binding defects before building a
fresh static Development Catalog. No v26.170 result is rewritten or reclassified.

The strongest supported result is:

```text
validity_separation_presentation_deleak_and_causal_component_static_gate_passed
```

This is a credential-free static and local-runtime result. It is not evidence that the model can
read the new representation, select the reference public choice, complete a rollout, or locate an
empirical capability boundary.

The v26.170 transition
`capability_observation_public_semantic_execution_development_runner_preflight_only` is blocked
without execution. It is not treated as consumed by a Runner, and none of its future 192 Jobs is
materialized.

## Frozen Predecessor And Reproduced Defects

The predecessor replay matches all eighteen authoritative v26.170 files and the v26.170 report,
Catalog, and transition identities. Predecessor mutation count is zero and the sealed v26.168
Confirmation payload is not loaded.

The independent v26.170 validity diagnostic reproduces:

```text
target States                                                80
old nonreference Choices                                    160
old nonreference Program-valid                              100
old Program + answer + postcompletion valid                  76
old adjacent-depth counterfactuals                            48
old adjacent-depth Program-valid                              28
old adjacent-depth task-semantic-valid                        24
compare Finance Cores exposing internal higher_ref             6
States with unique reference padding length                   34
presentations affected by unique reference padding length    204
model-visible padding fields                               1,440
```

The old Base report used reference-choice equality as an input. Consequently, a nonreference
choice could execute a locally valid Program and preserve public answer and postcompletion
semantics while still being forced Base-invalid because it was not the registered reference.
That coupling is reproduced as a v26.170 defect; no old validity field is changed.

The old six-replica envelope also carried model-visible `padding`. Thirty-four of eighty States
gave the reference choice a unique padding length, affecting 204 of 480 presentations. Padding
therefore equalized total bytes while introducing a value-correlated side channel. The old 1,440
fields remain immutable evidence and are not retrospectively declared safe.

## Validity Separation Contract

v26.171 freezes three separate content-addressed reports:

```text
StaticTaskValidityReport
StaticMechanismQualificationReport
StaticQualifiedValidityReport
```

Base validity is the conjunction of exactly these task-contract inputs:

```text
local_program_contract_valid
operation_lineage_complete
answer_projection_complete
answer_schema_valid
public_answer_semantically_valid
reference_identity_valid
citation_complete
terminal_verification_complete
postcompletion_control_passed
```

Reference-choice identity, capability label, target-component expectation, and mechanism trace do
not enter Base. Mechanism qualification receives only the capability-family-specific causal
trace. Qualified validity is frozen as:

```text
V_qualified = V_base and Q_mechanism
```

The 32 reference baselines separately pass Base, Mechanism, and Qualified validity. All 146 legal
nonreference counterfactual choices are then executed through the same public task and causal
runtime. Their exact joint matrix is:

```text
Base true,  Mechanism true                                  0
Base true,  Mechanism false                                26
Base false, Mechanism true                                  0
Base false, Mechanism false                               120
```

All 146 Qualified values equal the frozen conjunction, and Base/Mechanism report-ID overlap is
zero. The 26 Base-valid but Mechanism-unqualified rows are the required constructive witness that
task correctness and target-mechanism occurrence are not aliases. The absence of a
Base-false/Mechanism-true row on this registered alternative surface is an observed static matrix
entry, not a universal impossibility claim.

## Complete Public Answer Projection

v26.170 executed real Programs, but six compare Finance Cores retained internal Evidence IDs in
the raw `higher_ref` result field. v26.171 adds one exact public answer contract per public task.
It binds the exact required and allowed field set, Decimal-valued fields, and a public label for
each public record handle.

The full projection first selects only registered answer fields, then maps internal
`higher_ref` or `selected_ref` Evidence IDs through the exact public record handle to its public
label. Numeric fields use finite `Decimal(str(value)).normalize()` semantics, including canonical
zero. Booleans, nulls, nonfinite values, missing fields, and extra fields fail closed.

The exact result is:

```text
Finance Cores                                                8
Development Packages                                        32
compare Finance Cores                                         6
compare Packages                                             24
raw internal-reference Packages                              24
complete public-reference projections                        24
exact answer-schema passes                                   32
canonical public-semantic matches                            32
complete Citation checks                                     32
Base-valid baselines                                         32
```

The public answer projection is part of Base validity. It is not mechanism evidence and does not
read a reference choice.

## Real Causal Component Runtime

Every one of the 80 target components has a family-specific decision contract, a public current
State, legal public alternatives, dynamic dependencies, Runtime events, and a registered causal
effect. Synthetic `SET_EXPECTED_RESULT` and `SET_ALTERNATE_RESULT` effects are zero.

### Context-Conditioned Action

Context components independently select public operator, records, projection, and scope. The
selected values drive real `query_structured_fact` acquisition and a real local TaskProgram.
TaskProgram execution consumes the selected Evidence operands and projection; changing a target
component changes an executed query, Program input, Program operator, public answer, or task
validity rather than a Host-assigned result.

### Semantic Reconciliation

The Reconciliation target language contains only:

```text
reconcile_record
consume_normalized_output
```

`select_operator` is not a Reconciliation target. Each target mapping executes a real Evidence
query and a real `normalize_metric_unit_period` call. The resulting operation reference is
retained by exact handle and then consumed by the terminal calculator through its actual
`operation_ref` operand. The local TaskProgram is independently executed and verified after the
normalization lineage closes.

The exact Runtime counts are sixteen normalization calls, sixteen emitted normalized references,
and sixteen consumed normalized references. A normalization artifact that is never consumed
cannot qualify the component.

### Failure Recovery

Each Recovery component starts from a fresh Runtime, executes a selector that produces the real
typed public failure `typed_selector_requires_refinement`, exposes the resulting failure
Observation, revises the selector, and executes the revised query to success. A bypass, unchanged
selector, missing failure Observation, or absent later success fails mechanism qualification.

The exact result is twenty typed failure Observations and twenty successful recoveries. The Base
lineage remains independent from the exact target recovery selector, permitting a task-correct
but mechanism-missing counterfactual where the public task contract still closes.

### State-Dependent Stopping

Readiness is not copied from a static expected label. It is derived from actual Program execution
and Oracle-verifier output and bound in a dynamic receipt. Readiness components alter the receipt;
the final decision selects stop or continue from the resulting public readiness State. A wrong
readiness value changes the reached terminal. Continue/recompute alternatives make an actual
postcompletion invocation and therefore fail the postcompletion control.

The exact result is eight dynamic readiness receipts, 24 wrong-readiness terminal changes, and
sixteen postcompletion controls.

### Aggregate Runtime Closure

```text
Development Packages                                      32
target components                                          80
components with registered causal effect                   80
real TaskProgramExecutor baseline calls                    32
real TaskProgramOracleVerifier baseline calls              32
normalization calls / emitted / consumed references   16/16/16
typed failures / successful recoveries                20/20
dynamic readiness receipts                                  8
wrong-readiness terminal changes                           24
postcompletion controls                                    16
synthetic set-result effects                                0
```

These local calls establish executable causal consequences under the frozen Runtime. They do not
measure a model's ability to induce those consequences.

## Family Validators And Candidate Legality

Each of the four capability families has an explicit allowed decision language. Component order
and dynamic dependency receipts are validated against that family before execution. All eighty
components pass; dependency-order failures, family-validator failures, non-target model-choice
components, and Reconciliation operator targets are zero.

Candidate legality is checked against the current public State, public task, allowed Tool,
decision kind, public arguments, visible dependencies, and the task's allowed operator set.
Arbitrary operators are rejected even when their names occur elsewhere in the repository.

The fresh surface contains:

```text
target States                                               80
legal semantic Candidates                                  226
reference Candidates                                        80
legal distractors                                          146
publicly grounded Candidates                           226/226
Runtime-legal Candidates                               226/226
declared legal-action matches                          226/226
illegal operators                                             0
```

The historical 160 v26.170 nonreference choices remain frozen as the defect-reproduction
denominator. The fresh 146-row matrix is the legal v26.171 alternative surface, not a deletion or
reclassification of old rows.

## Deleaked Six-Replica Presentation

The semantic payload moves into a public `choice_legend` on the current State. Each displayed
candidate is a fixed-width envelope containing only:

```text
action_id
presentation_index
command = execute_public_choice
choice_handle = public_choice:<64 lowercase hexadecimal characters>
```

The Prompt requires equal canonical candidate byte lengths. Visible `padding` is forbidden. Each
choice handle resolves to exactly one complete public semantic operation in the State legend, so
fixed width does not make the semantics opaque.

A pre-outcome fixed salt still binds six presentations per State. Every legal choice occupies
every available position equally often for that State. The exact audit is:

```text
target States                                               80
presentations                                              480
displayed candidate rows                                 1,356
visible padding fields                                       0
padding-only unique selectors                                0
candidate-byte-length selectors                              0
semantic-argument-count selectors                            0
candidate-field-count selectors                              0
per-State position imbalances                                0
semantic choice-set mismatches                               0
action-ID collisions                                         0
```

The displayed-row count is lower than v26.170 because the new surface contains two or three legal
choices depending on the family-specific component, rather than forcing three choices for every
State.

The independent computed-evidence audit also finds zero source-Oracle dependencies, zero opaque
hash-guess States, zero Host-preclassified alternatives, and zero literal default-evidence
fields across all 480 Prompts.

## Honest Adjacent-Depth Causal Artifacts

The 24 adjacent group-depth increments each identify the newly added target component. One
counterfactual artifact is created for every legal nonreference choice of that component, giving
44 artifacts. Each artifact binds the source Package, target Package, new component, baseline
Result, and complete counterfactual Result; all 44 five-parent bindings reconstruct.

The exact necessity decomposition is:

```text
adjacent increments                                         24
counterfactual artifacts                                    44
task-level necessary                                        38
mechanism necessary                                         44
Qualified necessary                                         44
Base true / Mechanism false                                  6
five-parent binding matches                                 44
```

Only the 38 rows whose counterfactual makes Base false are called task-level necessary. The other
six remain Base-valid and are called mechanism-only necessary. All 44 remove the registered
mechanism effect and therefore make Qualified validity false. v26.171 does not repeat the old
claim that every adjacent-depth alternative is task-invalid.

These are component-level local causal artifacts under one frozen task/runtime construction.
They do not establish success monotonicity, a model-level depth effect, or an empirical boundary.

## Semantic Parent Reconstruction

Every fresh Package binds and independently reconstructs:

```text
source Finance Core
source Program Verification object and hash
source public Task hash
source public Evidence semantic hash
fresh projected public Task identity
each reference choice handle
the semantic parent-binding Contract
```

The exact reconstruction result is:

```text
Packages                                                    32
reference-choice recomputations                             80
source Program Verification recomputations                  32
source public Task recomputations                           32
source Evidence semantic recomputations                     32
projected public Task recomputations                        32
depth-increment parent matches                              44
whole-graph rehashed mutations                               6
whole-graph mutation rejections                              6
crossed-parent acceptances                                   0
```

The rehashed controls cross or forge Program Verification, source Task, source Evidence,
projected public Task, reference choice, or increment source parent, then recompute all child and
aggregate identities. The same production reconstruction path rejects every mutation.

## Static Gates And Destructive Controls

All fifteen noncompensatory Gates pass:

```text
answer projection complete
candidate legality
causal component execution
component family validation
computed evidence
Confirmation access zero
depth increment honesty
historical v26.170 freeze
parent binding reconstruction
presentation deleak
production destructive audit
Provider zero
public-only constructibility
source closure
validity separation
```

Seventeen destructive mutations of production objects fail closed. They separately cover the
required padding-only, candidate-byte-length, argument-count-only, and field-count-only selectors;
malformed fixed-width handles; variable action-ID width; crossed capability family;
Reconciliation operator reintroduction; changed Qualified formula; Prompt hash; Provider count;
reference choice; Program Verification; source Task; source Evidence; projected public Task; and
depth-increment source parent. Accepted mutations are zero.

## Reproducibility And Limits

The transitive source Root begins from the five v26.171 implementation modules, closes 307 local
`trusted_synthesis` files, and has zero unresolved imports. The formal Root contains 23 files and
9,566,182 bytes. Its report SHA-256 is
`8ba4e549905b89df93fad7cceafb76437de4ee19593d0c5dd8aa54c76433852c`.

The final candidate Root and formal Root are byte-identical. Focused Pytest passes 6/6 in 23.61
seconds, including an empty-directory byte-identical rebuild and direct reconstruction of the
exact parent surface. The adjacent v26.170-v26.171 regression passes 11/11 in 45.56 seconds.
Focused PyCompile, Ruff check/format, and Mypy pass. Package-wide Ruff passes. Package-wide Mypy
checks 538 source files and retains only the four pre-existing diagnostics in v26.70, v26.129,
and byte-frozen v26.154, with zero v26.171 diagnostics. No build or test reads a credential or
constructs a Provider client.

The result does not establish model readability, model success, a Development outcome, an
empirical capability boundary, success monotonicity, Confirmation status, frequency, State
probability, Contribution, VTDO, Student visibility, training value, release quality, or
production suitability. A future Runner preflight must bind this exact Catalog and all four new
Contracts. It may not reinterpret local static execution as a model outcome.

## Authoritative Identities

- report:
  `finance_v26_validity_causal_reaudit_report:f4c302eec26cba0ff3dfa6e6d2d435e1f935dccb75947533510c5f166652c026`;
- external authorization:
  `finance_v26_validity_causal_external_audit_authorization:9b5a4479b5f1217fd7d1cb440f26c58d317a685fa95ddf181189bfa1f3efbb50`;
- transitive source Root:
  `finance_v26_validity_causal_transitive_source_root:aef48551328622b6182c983b28100e9ebbf5cc09e733c08cb32d80960331ea01`;
- v26.170 predecessor integrity:
  `finance_v26_v170_predecessor_integrity:04e50824b63c5f1f2f0916f6ae0181c4e0be3a16cc14c4aaa4fd64c8ff0765a2`;
- v26.170 defect reproduction:
  `finance_v26_v170_validity_padding_defect_reproduction:46db1c91226446573ee8480d8a52580f2b4ddcca897773474e2b9997af051b59`;
- Validity Separation Contract:
  `validity_separation_contract:de59485ae062dd594db7cd6b8e7aa00bc080eae450ab3e5d56f891ccea3bc98e`;
- Causal Component Contract:
  `causal_component_contract:6e7066af8fb9d61cad7f59ff5e72cbbd6e6ea5790d0b885de6da1b350a10f976`;
- Presentation Policy:
  `deleaked_public_candidate_presentation_policy:de2ced9243e25eaa64cf2a1fbfa0324fe2f991556d42a18d87e36452574c15c9`;
- Semantic Parent Binding Contract:
  `semantic_parent_binding_contract:873dcd9b6868e01a1c8f5cb2542259effe400affe27790d1dca7bf13a395fc87`;
- Development Catalog:
  `finance_v26_validity_separated_development_catalog:b6ff7c04909c8ed042ed72656ef7b877ef06d0505f4f6ac4df266b0fb72c744b`;
- public answer projection:
  `finance_v26_public_answer_projection_audit:21a33783607547c4f585577c65dd0b1e25b4db7a3234e6610dba8abe1854a76a`;
- validity separation:
  `finance_v26_validity_separation_audit:4d08d0f6c323b886a97f83a7e717db4a2bf6c90331122670f8d15a42801f75b5`;
- causal component execution:
  `finance_v26_causal_component_execution_audit:3ff61defbaddf1e28f097a9aaf13968a2cca95f1fed73bc860968476b015ab89`;
- component-family validation:
  `finance_v26_component_family_validator_audit:30fc77afb8c32bbd71e9b0c7028ce2ebb39f9fc2813f7589401d46e4a404cc14`;
- Candidate legality:
  `finance_v26_candidate_legality_audit:f4726436c5fab0677fe340fd4ef0e340f5cd6d53d3ecc0cbc1ebd18386162fb3`;
- presentation deleak:
  `finance_v26_presentation_deleak_audit:561cf77caff08d77681a40db8ac6548640ccf7bc895b657fd1501ef13f054b26`;
- Depth Increment Causal Catalog:
  `depth_increment_causal_catalog:4de56365562deb0802e71d2893a4fd51e60399e01565acdc84b0b34180edda81`;
- semantic parent reconstruction:
  `finance_v26_semantic_parent_binding_audit:da07b4737645227b0a981f0e6d422cd42ca77385649cd50a37be6dbab41ec3a4`;
- computed evidence:
  `finance_v26_computed_evidence_audit:2c0002eabe4c43417abb1d3b5a6655e32da09872ea37b49482ef1358381d896d`;
- destructive audit:
  `finance_v26_validity_causal_destructive_audit:78dd79c1362e616bbe26a1eb2babe98f2e2ca1434b48229222b81cdaa5f0ec23`;
- static audit:
  `finance_v26_validity_causal_static_audit:d8f5120bce298ea3fba65a24483dc400e0c5bfbd4e71f6d93fcf016679cbd252`;
- transition:
  `finance_v26_validity_causal_transition:d1621bff89558111106f08c235690390b967d54c1518050decab03a59f431ec1`.

## Only Permitted Transition

```text
capability_observation_validity_separated_causal_deleaked_development_runner_preflight_only
```

The successor may materialize only the exact future 192-Job Development Manifest and complete a
credential-free Runner preflight over the exact v26.171 Development Catalog, separated Base,
Mechanism, and Qualified contracts, complete public answer projection, family-specific causal
runtime, legal Candidate surface, padding-free six-replica presentation, semantic parent bindings,
fixed generation condition, model/Thinking profile, Grammar, Policy, resource, threshold,
terminal, and sealed-receipt bindings.

Provider execution, Development outcomes, Confirmation payload loading or execution, source or
public-task change, component or Candidate change, presentation-salt change, validity formula or
threshold tuning, historical rewrite or reclassification, Mapper, State, frequency,
Contribution, VTDO, Student visibility, training, release, and production remain forbidden.
