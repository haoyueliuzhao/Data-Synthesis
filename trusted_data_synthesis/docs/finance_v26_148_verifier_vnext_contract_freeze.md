# Finance v26.148 Verifier vNext Contract Freeze

Audit date: 2026-08-25

## Decision

Finance v26.148 consumed only the credential-free
`verifier_vnext_contract_freeze_only` transition authorized by v26.147. It freezes prospective
answer semantics, validity eligibility, Final response responsibility, mechanism qualification,
noninterference binding, and separate Base/Mechanism/Qualified report contracts.

The Contract freeze passes. The only permitted successor is:

```text
measurement_support_verifier_vnext_joint_preflight_only
```

This stage does not rescore a historical row, materialize a Capability or Reachability identity,
construct a model client, call a Provider, execute State Mapping, or create a training, release,
or production row.

## Source Integrity

The exact predecessor is v26.147 report
`finance_v26_validity_decomposition_report:fddc664b2d8e45788b0f7e55333041ed82e7dae62368e2b27d22ec8baa7a69a5`,
SHA-256 `06046d8a9b2671b373366af2336df8eb2262220372ba473ecb1720081f940dc7`,
and transition
`finance_v26_validity_decomposition_transition:e6ce3161658116772a3951f5823cada820e5bc7b911e9694dc6475d3ea43c9b2`.

Before loading a Contract, v26.148 replayed 7,318/7,318 files:

```text
v26.147 transitive bindings             7,304
v26.147 direct formal outputs               10
v26.148 implementation files                 4
total                                    7,318
```

It rebuilt the complete ten-file v26.147 formal directory in an empty temporary directory. Every
file was byte-identical. The historical partition remains 93 model outcomes, three support exits,
seventeen valid labels, and 76 invalid labels, with zero reclassification.

The new implementation is isolated in four new files:

```text
core/evaluation/answer_semantics.py
core/evaluation/trajectory_validity.py
runtime/agent/prospective_qualified_final_response_grammar.py
experiments/vtdo_experiment/phase1_v26_verifier_vnext_contract_freeze.py
```

No historical bound module is edited.

## Eligibility

The Contract freezes:

```text
E_validity = M and O and R and P
```

`M`, `O`, `R`, and `P` are Measurement Support, model endpoint observation, Instrument integrity,
and privacy compliance. Only an evaluable row may invoke task verification. Support exits,
missing endpoints, Instrument failures, and Privacy rejections remain null rather than false.
The API rejects Base checks or task-level noninterference bindings on an ineligible row.

The Eligibility Contract is
`finance_v26_validity_eligibility_contract:ae18cf12332c1b3c024cc452bc7bc46ed9f0beaa00b92f69146bef802bbb7f6e`.

## Answer Semantics

The answer Contract reports exact JSON equality and canonical semantic equality separately.
Decimal comparison is field-level and Task-Schema-bound. Each declared Decimal field uses exact
`Decimal(str(value)).normalize()` semantics. Thus `0.35` and `"0.350"` are semantically equal,
while `0.35` and `0.351` differ. Non-finite values, booleans, missing paths, floating tolerance,
fuzzy equality, and aliases fail closed.

Non-Decimal fields retain exact identity. Reports include schema failures, canonical results,
reference-identity equality, and exact mismatch paths. Base validity uses canonical semantic
equality; exact JSON equality remains diagnostic. Task-specific fields and Decimal paths must be
frozen before execution and cannot be selected from outcomes.

The Answer Semantics Contract is
`finance_v26_answer_semantics_contract:0d2849e2edf093cdf405a5612a7135d9c9ed114a709a92977239bf153c2a901f`.

## Final Language

The only prospective model Final language is:

```json
{
  "answer": {
    "result": {"...": "..."},
    "citations": [{"evidence_id": "..."}]
  },
  "rationale_summary": "public concise rationale"
}
```

The outer, answer, and Citation field sets are exact. At least one unique model Citation is
required. Flat aliases, wrappers, missing or extra fields, and duplicate Citations fail closed.
The model owns result, Citations, and rationale. Runtime-selected support is reported separately
and cannot satisfy model Citation.

The Host binds only stage, protocol, terminal state, and terminal commit. Host answer, Citation,
or rationale insertion is forbidden by strong types. The Grammar is
`prospective_qualified_final_response_grammar:2370b603f1243c500e19ef0b45e6bdfa32434a7b4242b0c884ee977dd169d3fc`.

## Base Report

`BaseTrajectoryValidityReport` is separate from mechanism qualification. For an eligible row it
requires the conjunction of these fourteen checks:

```text
action_abi_complete
program_closed
operation_lineage_complete
required_evidence_support_complete
runtime_selected_support_complete
model_citation_complete
terminal_verification_complete
final_abi_complete
answer_schema_complete
answer_canonical_semantic_match
reference_identity_match
verification_support_complete
no_postcompletion_violation
noninterference_artifact_bound
```

It retains failed check IDs and cannot use the legacy `final_answer_semantically_valid` alias.

## Noninterference

Noninterference is not a Boolean default. Every evaluable Base Report binds a content-addressed
artifact containing `noninterference_contract_id`, `noninterference_audit_id`, TaskPackage ID, and
a passing audit state. A missing binding or hardcoded pass is rejected. An ineligible row has no
task-level binding because its task Verifier is not invoked.

The combined responsibility Contract is
`finance_v26_responsibility_noninterference_contract:f6793d4ff0fbd901e3841d1f7f59248b6e17469746ec083eb1b8e2418c3bc494`.

## Mechanism Report

`MechanismQualificationReport` stores required, observed, and missing events separately from
Base validity.

Context-conditioned Action requires a frozen Context difference and a target action change. Final
answer correctness alone cannot qualify it.

Semantic Reconciliation requires every Task-frozen target Evidence to produce a normalization
reference and every target reference to be consumed. Additional legal Normalize actions are
diagnostic and do not automatically fail the mechanism.

Failure Recovery requires a typed failure, a later changed selector or action, and a still-later
successful Observation. Direct bypass may be Base-valid but remains mechanism-invalid.

State-dependent Stopping requires completion verification, stopping after completion, and no
postcompletion violation. Verification, stopping, and violation are reported separately, while
related stopping failures retain one causal group.

The Mechanism Contract is
`finance_v26_mechanism_qualification_contract:8af9bfd59843b799a0d70c30d9900077b4588b5096d67a0995100d6514c4821f`.

## Qualified Report

`QualifiedTrajectoryValidityReport` binds the exact Base Report, Mechanism Report, trajectory,
Verifier Contract, and eligibility identity. It freezes:

```text
V_qualified = V_base and Q_mech
```

For the current mechanism-conditioned role, State Mapping is eligible if and only if Qualified
validity is true. Base-valid/mechanism-invalid, Base-invalid/mechanism-valid, and all null rows
cannot enter State Mapping.

The complete Verifier vNext Contract is
`finance_v26_verifier_vnext_contract:7302fab2d9c0942cddc712c3724d45c138c9f5c806b620e98976ad21eb676790`.

## Fixtures And Destructive Controls

Seventeen local fixtures pass with zero calls. They cover Decimal representation equality, true
numeric error rejection, exact model-owned Final parsing, flat/missing-Citation rejection, all
three Base/Mechanism combinations, support-exit null reports without task verification, all four
mechanism boundaries, artifact-bound noninterference, and metadata-only Host Envelope.

These are Contract consistency fixtures, not empirical Flash behavior, a Capability outcome, or
the joint Support/Verifier Runner preflight.

All 24 destructive mutations fail closed. They include float tolerance, flat aliases, Runtime
support as model Citation, Host semantic insertion, ineligible Verifier invocation,
support/instrument/privacy conversion to model-invalid, mechanism bypass, merged report objects,
legacy Boolean reuse, historical reclassification, Provider calls, and non-qualified State
Mapping.

## Reproducibility

Focused v26.148 Pytest passes 4/4 in 946.04 seconds with exact reconstruction of all twelve formal
files. The selected v26.147-v26.148 adjacent structural regression passes 5/5 in 3.26 seconds.
Focused Ruff and Mypy pass. Package-wide Mypy checks 471 source files and retains only the three
pre-existing v26.70/v26.129 diagnostics; v26.148 contributes zero diagnostics.

Formal Provider, Stage 2 Provider, and GPU counts are zero.

## Authoritative Identities

- report:
  `finance_v26_verifier_vnext_freeze_report:3d75e805997c2511626db93cafc095a2a21bf988d6269cfdb6bd9e953788ff75`;
- source replay:
  `finance_v26_verifier_vnext_source_replay:6889e9b337223a4ff3baceac66ff61e301fb20c4955721332544211b414867e8`;
- predecessor integrity:
  `finance_v26_verifier_vnext_predecessor_integrity:246ec4ad301badc22cdc7427283d88eb13887c44258e3151673495c4b22ecb70`;
- Answer Semantics Contract:
  `finance_v26_answer_semantics_contract:0d2849e2edf093cdf405a5612a7135d9c9ed114a709a92977239bf153c2a901f`;
- Eligibility Contract:
  `finance_v26_validity_eligibility_contract:ae18cf12332c1b3c024cc452bc7bc46ed9f0beaa00b92f69146bef802bbb7f6e`;
- Mechanism Contract:
  `finance_v26_mechanism_qualification_contract:8af9bfd59843b799a0d70c30d9900077b4588b5096d67a0995100d6514c4821f`;
- Responsibility Contract:
  `finance_v26_responsibility_noninterference_contract:f6793d4ff0fbd901e3841d1f7f59248b6e17469746ec083eb1b8e2418c3bc494`;
- Final Grammar:
  `prospective_qualified_final_response_grammar:2370b603f1243c500e19ef0b45e6bdfa32434a7b4242b0c884ee977dd169d3fc`;
- Verifier vNext Contract:
  `finance_v26_verifier_vnext_contract:7302fab2d9c0942cddc712c3724d45c138c9f5c806b620e98976ad21eb676790`;
- fixture audit:
  `finance_v26_verifier_vnext_fixture:ccf44a3455058dba1fdbf8bf14dcdd782150b809f0170d3a6d74707515b30289`;
- destructive audit:
  `finance_v26_verifier_vnext_destructive:8475d54257e2719ce6b6bd5e4bc55755e89c29dde499f03706b82be3e72c519c`;
- transition:
  `finance_v26_verifier_vnext_transition:eab4f37ae38bc033981ab72b2b38a4fc939a52d8e353349a540baca35b4172d9`.

## Permitted Transition

The only permitted transition is:

```text
measurement_support_verifier_vnext_joint_preflight_only
```

The successor may implement and credential-free preflight the joint state machine from Public
State through Measurement Support, eligibility, Base, Mechanism, and Qualified validity. It must
prove that support exits, missing endpoints, Instrument failures, and Privacy rejections never
invoke task verification or become model-invalid. Provider calls, new Capability or Reachability
identities, any online execution, historical reclassification, State Mapping, training, release,
and production Contribution remain forbidden.
