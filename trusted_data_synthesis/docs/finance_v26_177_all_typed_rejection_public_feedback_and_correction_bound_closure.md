# Finance v26.177 All-Typed-Rejection Public Feedback And Correction-Bound Closure

Audit date: 2026-08-29

## Decision And Scope

Finance v26.177 consumed only:

```text
capability_observation_all_typed_rejection_kinds_
public_feedback_and_correction_bound_closure_only
```

The bound external review is exactly 17,882 bytes with SHA-256
`44f482f292a1925e2b5942ea0ca5345565f6c4089f833c690ca8e9991be28ce0`.
The stage did not consume the v26.176 192-Job Runner-preflight transition. It
created no Manifest, Runner, Prompt denominator, Development Job, model outcome,
or empirical capability estimate. Credential lookup, Provider-client
construction, Stage 1 and Stage 2 Provider calls, sealed Confirmation payload
access, GPU jobs, Mapper calls, State Assignments, frequency rows, Contribution,
VTDO, Student visibility, training, release, and production counts are zero.

All sixteen authoritative v26.176 files remain immutable. Before constructing a
v26.177 object, the stage rebuilt those sixteen files in an empty temporary
directory and matched all sixteen byte for byte. The exact blocked predecessor
transition remains:

```text
capability_observation_authoritative_parent_closed_rejection_history_
state_bound_step_runtime_development_runner_preflight_only
```

## Source-Level Defect Reproduction

The external audit's two source-sensitive concerns are confirmed by the checked
in v26.176 implementation.

The old model-visible `TypedRejectionFeedback` schema includes these direct Host
parents:

```text
component_key
selected_operation_hash
action_acceptance_report_id
```

Its `feedback_id` and old rejection Observation receipt are also content
addresses whose preimages include those Host-bound values. The old exact
correction audit reaches only 120
`failure_recovery / revise_selector / typed_current_state_target_mismatch`
State x Replica instances. The production classifier separately implements
`typed_failure_receipt_mismatch`, `reconcile_record`,
`consume_normalized_output`, and `assess_dynamic_readiness` branches. No
historical v26.176 row, label, artifact, or narrow Failure-Recovery result is
changed.

## Strict Public Feedback Projection

The replacement `PublicTypedRejectionFeedback` has exactly these fields:

```text
feedback_id
public_rejected_action_id
public_displayed_choice_handle
public_rejection_code
public_observation_receipt_id
correction_attempt_index
correction_attempt_bound
predecessor_public_feedback_id
schema_version
```

Its Observation receipt is derived only from the current public State token,
public Action ID, displayed Choice handle, public rejection code, correction
attempt, fixed bound, and non-commit status. The Feedback identity preimage is
only the fields above. It receives no Package, Component, source Choice,
source-Operation hash, Acceptance object or identity, reference path, Schedule,
seed, nonce, source artifact, or Replica metadata.

The full `ActionAcceptanceReport`, selected source Operation, Runtime events,
Package, and Component remain in a separate `HostTypedRejectionBinding` with
`model_visible=false`. Prompt rendering accepts only the public projection.
Recursive exact-key rejection, independent public preimage reconstruction,
before/after Prompt-delta scans, and Host-counterfactual invariance all pass:

```text
public projection rows                              432
exact-Catalog rows                                  120
registered-control rows                             312
exact public-schema matches                         432
independent projection matches                      432
Host-counterfactual invariant rows                  432
public-only identity-preimage matches               432
prohibited public Keys                                0
new direct hidden scalar exposures                    0
new derived Host-identity exposures                   0
Acceptance object / identity exposures              0 / 0
```

The Prompt-delta scan is deliberate. It tests values newly introduced by the
Feedback against exact Host values and registered derived forms, while the
complete Feedback object is recursively checked against the stronger public
schema. It does not relabel a pre-existing public Task scalar as a new Feedback
leak merely because the same string also appears in a Host audit object.

## Complete Production Classifier Surface

The production classifier has four Decision kinds and five registered
Decision-kind x rejection-code rows. The exact frozen 32-Package Catalog has 52
unique Components on this surface. `revise_selector` appears in two registered
rejection-code rows, so the row-expanded component surface is 72 and the six
Replica control denominator is 432:

```text
Capability                  Decision kind               Rejection code                         Components  Controls  Exact status
Failure Recovery            revise_selector             typed_current_state_target_mismatch          20       120  reachable:120
Failure Recovery            revise_selector             typed_failure_receipt_mismatch                20       120  registered_but_unreachable
Semantic Reconciliation     reconcile_record            typed_current_state_target_mismatch          14        84  registered_but_unreachable
Semantic Reconciliation     consume_normalized_output   typed_current_state_target_mismatch           6        36  registered_but_unreachable
State-dependent Stopping    assess_dynamic_readiness    typed_current_state_target_mismatch          12        72  registered_but_unreachable
```

`registered_but_unreachable` is an exact statement about the unmodified current
Catalog Candidate surface. Those four rows are not silently dropped. Each is
also exercised through a separately identified production-classifier control:
a valid but binding-mismatched public Failure Receipt, or a publicly grounded
and executable Component-local precondition control with an independently
rematerialized diagnostic Schedule. These controls are never inserted into a
Package, Runner, Manifest, Job, or empirical denominator.

Across all 432 controls, initial rejection is public and content-addressed, the
same target Component remains current, the next Prompt binds exact public
Feedback, reference correction commits exactly once, and a second invalid
response emits a terminal before a third Prompt. Rejection-only Retry, Tool-call,
and Component-advance deltas are all zero.

## Exact Correction-Disposition Matrix

The unchanged exact Catalog contains 120 reached Recovery State x Replica
instances with one invalid current Candidate, one reference-valid Candidate,
and one valid nonreference Candidate. Seven second-response dispositions are
registered for every instance:

```text
matrix rows                                           840
executed rows                                         672
registered_but_unreachable rows                       168

reference-valid accepted                              120
valid nonreference accepted                           120
same-current-invalid typed terminals                  120
different-current-invalid unavailable                 120
stale-action terminals                                 72
stale unavailable on first reached Component           48
foreign exact-action terminals                        120
ABI-valid but unbound-action terminals                120

all executed invalid second-response terminals        432
later correction Prompts                                0
rejection-only Retry / Tool / Component advance       0 / 0 / 0
final-or-terminal lineage bindings                    672
```

The 120 `different_current_invalid` rows are explicitly unavailable because
every exact current Prompt has one and only one typed-invalid Candidate. The
Runtime correction bound is attempt-count based and contains no same-Action
identity gate, but v26.177 does not fabricate a second current Candidate to
claim exact-Catalog evidence. Stale is likewise unavailable for 48 first
Components and executed for the 72 instances with a prior public Action surface.
Foreign Actions are exact public Action IDs from another frozen Package;
ABI-valid unbound Actions are deterministic 24-hex references absent from every
registered exact current Action set. Both terminalize without a Runtime loop.

For every valid nonreference correction, the same source Choice is independently
executed from the same State without a preceding rejection. Action acceptance,
public effects, Base validity, Mechanism qualification, and Qualified validity
match 120/120. This is local deterministic Runtime equivalence. It is not model
behavior equivalence or a claim that a model will select nonreference
corrections.

## Separate Capability Estimands

The prospective Outcome Contract freezes all required first-response and final
fields:

```text
first_response_abi_valid
first_action_state_precondition_valid
first_action_accepted
first_attempt_base_valid
first_attempt_mechanism_qualified
first_attempt_qualified_valid

correction_invoked
correction_feedback_id
corrected_action_accepted
correction_terminal_reason

final_base_valid
final_mechanism_qualified
final_qualified_valid
```

It separately registers:

```text
q_first              = sum(first_attempt_qualified_valid) / eligible_job_count
q_bounded_correction = sum(final_qualified_valid) / eligible_job_count
```

First-attempt fields cannot be overwritten by corrected outcomes, correction is
post-first-response, and pooling the two estimands is forbidden. Five local
contract fixtures cover reference-valid, nonreference-valid, same-invalid,
different-invalid, and stale/foreign terminal shapes with zero missing fields or
estimand conflation. Empirical rows and estimates remain zero.

## Destructive And Static Controls

All 26 production destructive mutations fail closed. They cover direct Host
fields added to Feedback, Host-derived identity substitution, invalid attempt or
predecessor chains, Host Binding made model-visible, a terminal permitting a
later Prompt, terminal non-commit violations, missing registered rejection rows,
reachability promotion, matrix row deletion, zero-commit accepted correction,
missing terminal lineage, silent unreachable rows, nonreference-equivalence
falsification, and Outcome Contract erosion.

All 30 noncompensatory static Gates pass. The transitive source closure contains
332 files with zero unresolved imports. The authoritative formal Root contains
15 files and 1,893,458 exact bytes. Report SHA-256 is
`e0c4665858d32436c53662b634e40f7814b0771e0b3a7cf385dadffaf30285f3`.

Focused PyCompile, Ruff check, Ruff format, and no-import-follow Mypy pass. The
complete focused Pytest suite passes 7/7 in 522.41 seconds, including a warning-
as-error empty-directory 15/15 byte-identical rebuild. The adjacent v26.176-
v26.177 non-rebuild regression passes 12/12 with two rebuild tests deselected in
5.92 seconds. Package-wide Ruff passes. Package-wide Mypy checks 561 source files
and retains six diagnostics in four historical files:

```text
core/task/semantic_table_trace_hardening.py                         2
experiments/.../phase1_v26_authority_preserving_role_runner.py     1
experiments/.../phase1_v26_fresh_role_kernel_compatibility_preflight.py 2
experiments/.../phase1_v26_fresh_reachability_execution.py         1
```

The four v26.177 source modules contribute zero diagnostics.

## Preliminary v1-v2 Supersession

A successful preliminary v1 Root remains immutable. Its 432 projection rows were
complete, but the top-level `registered_control_projection_count` incorrectly
declared 192 instead of 312 and lacked the noncompensatory
`120 + 312 = 432` partition invariant. The first formal non-rebuild test caught
that mismatch. No row, Runtime outcome, Candidate, control, or scientific count
was changed. Preliminary v2 adds the exact aggregate invariant and uses a fresh
output identity. A final parent audit then found that its Transition did not bind
the Projection, destructive, static, Freeze, Defect, Authorization, or source-Root
parents; v1 and v2 consequently shared one Transition identity despite the v1
Projection defect. The authoritative v3 Transition now content-addresses every
required evidence parent. No control, row, Runtime result, Candidate, scientific
count, or empirical claim changes. Both preliminary Roots remain immutable.
Twelve of fifteen v2/v3 files are byte-identical; only the transitive source
Root, prospective Transition, and top-level Report change.

The authoritative Transition binds the exact external Authorization, source Root,
v26.176 Freeze, defect reproduction, Public Feedback Contract, production
rejection Surface, public Projection Audit, Correction Matrix, Capability Outcome
Contract, Outcome fixture, destructive Audit, and Static Audit. Its identity now
changes whenever any one of those parents changes.

## Authoritative Identities

- report:
  `finance_v26_all_typed_rejection_public_feedback_closure_report:6ffc0987f5c90f8a513c118cad1d46a9ec74f85e772bfcc9f18adadd7900ece0`;
- transitive source Root:
  `finance_v26_all_typed_rejection_transitive_source_root:50ef54df6af3a9091b602ec0ef352aa41e8a724ae29107616111a2058a618ad9`;
- v26.176 predecessor Freeze:
  `finance_v26_v176_predecessor_freeze_audit:a3e336c03d37e17f4c0d20029359bbba87dc1a2411ace3d47da61681a7605eda`;
- v26.176 defect reproduction:
  `finance_v26_v176_typed_rejection_defect_reproduction:ca5fafb2985e491cab785ae39a3addc8e36fdd5bddc12a497748f616ca10a141`;
- Public Feedback Contract:
  `public_typed_rejection_feedback_contract:73c2cafa61653563cef38e0358d9ed183aa0ad92f210919b6c5ad55851c39bee`;
- production rejection Surface:
  `finance_v26_production_typed_rejection_surface_catalog:cc4c9bc32df73b3f344caeaecf2798dfb000b313fb7bc23a0b822f0d0239170f`;
- public Feedback Projection Audit:
  `finance_v26_public_typed_rejection_feedback_projection_audit:c128510648978bbce60feff2cd113b4e402b8e1567962e83bc739a57000d8d03`;
- Correction Matrix Audit:
  `finance_v26_bounded_correction_matrix_audit:1176648bc7d5aa25b9d4c44a44b0d3a66e52b211c08c5e8e537f6ba85745e412`;
- Capability Outcome Contract:
  `capability_first_and_bounded_correction_outcome_contract:f4ed31d331ee6eb724d3a515120987625c98a90d1600a5299874f594f0d81a1a`;
- Outcome Contract fixture:
  `finance_v26_first_bounded_outcome_contract_fixture_audit:0beebc926b64e2ae29e4afa539da12087ef3ac44964394227a9169cb8f8db886`;
- destructive Audit:
  `finance_v26_all_typed_rejection_production_destructive_audit:22e0138ba38c99bcf4987c02479b72e6c68e22eef2cc2d0f7e3f9d76d8b0430e`;
- static Audit:
  `finance_v26_all_typed_rejection_static_audit:bd041df4fbef57e7c315580906ef9cc006b82c0ee23c9af3f710f74aeaad8541`;
- transition:
  `finance_v26_all_typed_rejection_public_feedback_transition:6dfc6431ee0e4a6a78dc40b05eb7aafd33c1c48969880482a7df435cde370e0a`.

## Scientific Boundary And Next Transition

v26.177 supports strict public Feedback construction, complete registered
production-classifier control coverage, exact current-Catalog correction-bound
behavior, valid nonreference correction preservation, and prospective separation
of first-attempt from bounded-correction estimands. It does not support model
readability, model success, empirical Capability Depth, success monotonicity,
Confirmation, frequency, State Mapping, Contribution, VTDO, Student visibility,
training, release, or production claims.

The only permitted transition is:

```text
capability_observation_public_feedback_closed_all_typed_rejection_
correction_bound_state_bound_step_runtime_development_runner_preflight_only
```

A successor may materialize only the exact future 192-Job Development Manifest
and perform a credential-free one-current-Prompt-at-a-time Runner preflight from
the frozen v26.176 zero-Prompt Catalog under the v26.177 Public Feedback,
all-typed-rejection, correction-bound, and separate-Outcome Contracts. Provider
execution, Development outcomes, reference Trace input, precommitted vectors,
future Prompt materialization, complete baseline loading, Confirmation payload
loading, source, Task, Component, Candidate, Schedule, presentation, validity,
correction-bound, threshold, model/Thinking, Grammar, Policy, resource, or
terminal change, historical rewrite, Mapper, State, frequency, Contribution,
VTDO, Student visibility, training, release, and production remain forbidden.
