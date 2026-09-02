# Finance v26.214 Fresh Repaired Outer Typed-Exception Observation Authenticity And Single-Consumer Failure Terminalization Preflight

## Scope And Decision

Finance v26.214 consumes only
`fresh_repaired_outer_typed_exception_observation_authenticity_and_single_consumer_failure_terminalization_preflight_only`.
It binds the exact 14,653-byte external review at SHA-256
`64c6b8c6bc2a62f8205ae7007169cedfc3d9fe184b2740b3d93b398c672339a7` and the
exact 30-byte operator directive `参照审计继续实验修订` at SHA-256
`d7f0a7b9c625edb3ec4d53a21418dd0b11ec7291a0ae934b98364ea651f9d3ca`.
The directive authorizes only this credential-free repair preflight. Provider calls, credential
lookups, empirical rows, and online authorizations are zero.

The review retains v26.213 as
`VALID_SCOPED_COMPLETED_AND_PARSER_TERMINAL_PREFLIGHT` but fails its full terminal-provenance
claim at `OUTER_TYPED_EXCEPTION_EVIDENCE_AUTHENTICITY`. The retained results are:

```text
explicit terminal_kind argument removed                    PASS
192 completed Runner results -> derived terminal           PASS
parser/reference/correction-bound terminal derivation      PASS
derived terminal -> five-layer persistence                 PASS CONDITIONAL
typed exception observation -> authoritative terminal      FAIL
```

The exact v26.213 retrospective decision is:

```text
v26_213_main_completed_and_parser_terminal_paths_passed_
but_outer_typed_exception_evidence_can_be_reclassified_
by_caller_selected_evidence_subtype
```

All 1,058 v26.213 formal files and 58,565,824 bytes revalidate, including all 1,057
self-excluding Manifest members and 58,336,116 bound bytes. Its completed and parser/reference
results, durable ingress, and persistence mechanics remain immutable. Its old eight outer
typed-exception controls are retained only as honest-constructor diagnostics; their
authoritative-provenance interpretation is superseded.

v26.214 repairs only that first blocker. It does not change Prompt, model, Grammar, the frozen
192-Job condition, v26.209 request compilation, the v26.195 terminal Registry, or the five-layer
persistence structure.

The current decision is:

```text
fresh_repaired_outer_typed_exception_observation_authenticity_and_single_consumer_
failure_terminalization_preflight_passed_independent_audit_required_online_execution_blocked
```

## Root Cause And Repair

v26.213 represented the eight outer failures with eight subclasses of
`TypedExceptionEvidenceBase`. Although the explicit `terminal_kind` argument was absent, the
caller could still select a terminal by selecting an evidence subclass. Its base validator did
not compare the subclass to `ExecutableInvocationRecord.typed_terminal`, the actual caught
exception class, or the actual reason hash. The persistence pipeline could therefore consistently
rederive and persist a caller-reclassified terminal.

v26.214 removes the eight-subclass authority surface. Every outer failure now uses exactly one
public evidence shape:

```text
AuthenticatedTypedFailureEvidence
  evidence_kind = runner_owned_typed_failure
  job_id
  invocation_id
  failure_observation
```

There is no provider-, transport-, privacy-, resource-, instrument-, identity-, Thinking-, or
Usage-specific evidence subclass in the v26.214 model module. There is no caller terminal field,
expected terminal field, exception-type selector, or policy selector on the dispatcher API.

The new `ObservationAuthenticFullConditionRunner` preserves the exact v26.209 current-State
request and Runtime route. Inside its actual `except TypedTransportFailure as error` block, after
the v26.209 invocation record is constructed and before the `InvocationOutcome` is returned, it
constructs one immutable `TypedFailureObservation` containing:

```text
source v26.209 Runner identity
v26.214 Runner-observation Binding
Job and invocation IDs
request, validation-certificate, pre-transport-receipt, and transport-seam parents
actual Python exception class
actual caught terminal
SHA-256 of the actual exception reason
complete actual ExecutableInvocationRecord
```

The observation validator requires all of the following:

```text
exception class is one of the exact eight registered classes
class -> terminal mapping equals caught_terminal_kind
record.typed_terminal equals caught_terminal_kind
record Job and invocation equal observation Job and invocation
record request/certificate/receipt/transport parents equal the observation parents
public response is absent
exact response parsing and Runtime completion are false
event_sequence ends with terminal_dispatch
observation identity matches all canonical content
```

The Runner then appends the strict observation to a no-replace
`RunnerFailureObservationAuthority`. The authority is not populated by the consumer, evidence
factory, dispatcher, or build. A dispatcher request must match the Runner-owned observation
byte-for-byte by invocation ID. Self-consistent but rehashed caller objects are not authority.

The formal dispatcher API is:

```python
dispatch(evidence)
```

It reparses the generic evidence, obtains the exact observation from the authority, reparses the
embedded v26.209 invocation record, requires class/terminal/record agreement, looks up the exact
v26.195 policy, and only then creates the derived terminal decision. Evidence subtype does not
participate in this derivation.

The persistence pipeline independently reparses the evidence, repeats authority matching and
dispatch, and requires canonical equality with the supplied decision before creating a Raw file.
Raw embeds the complete observation, generic evidence, derived decision, and v26.209 invocation
record. Result, Trace, Outcome, and checkpoint remain content-addressed children of the same
authenticated facts.

## Single-Consumer Execution

One source-bound `FailureTerminalizingConsumer.execute_preflight` entry performs:

```text
exact v26.211 authorization-byte guard
  -> isolated durable preflight consumption receipt
  -> durable Run Start Receipt
  -> zero-lookup credential/factory Gate
  -> actual v26.209 current-State request route
  -> actual typed transport exception
  -> Runner catch and Runner-owned failure observation
  -> InvocationOutcome.terminal branch inside the consumer
  -> authority-bound dispatch
  -> Raw -> Result -> Trace -> Outcome -> checkpoint
```

The preflight lease is an isolated local control and does not consume the current v26.211 online
authorization. The top-level build calls the consumer exactly once. It does not call the Runner,
construct outer evidence, join a terminal, or invoke persistence separately.

Eight distinct exact v26.209 Manifest Jobs are used as diagnostic controls, one per exception
class. Each performs a real first-Action Runner invocation through the exact current-State Prompt,
request, certificate, receipt, and injected transport seam. Each injected transport raises one
actual typed exception. The consumer handles every returned terminal through its actual failure
branch without an exception escape:

```text
actual Runner invocations / transport dispatches              8 / 8
Runner-catch observations / consumer terminal branches        8 / 8
generic authenticated evidence rows                           8
exact terminal matches                                        8 / 8
distinct exception classes / terminals                        8 / 8
Raw / Result / Trace / Outcome / checkpoint files             8 each
persisted layer files                                         40
caller-selected evidence subtype / build-level failure join   0 / 0
exception escapes / empirical rows / Provider calls           0 / 0 / 0
```

The eight terminal mappings are:

```text
ProviderNoPayloadError     -> provider_failure_no_payload
ProviderTransportError     -> provider_transport_failure
PrivacyEvidenceError       -> privacy_rejection
ResourceBudgetError        -> resource_budget_exhausted
InstrumentEvidenceError    -> instrument_failure
ProviderIdentityError      -> provider_identity_failure
ThinkingIntegrityError     -> thinking_integrity_failure
UsageIntegrityError        -> usage_integrity_failure
```

These rows demonstrate terminalization mechanics for actual locally injected typed failures.
They are not claims that a Provider produced any of these failures, and they enter no empirical
denominator.

## Provenance Attacks

Four attacks fully rehash the forged observation, generic evidence, decision, and all five
prospective downstream layer identities before calling the production persistence pipeline:

```text
instrument record reclassified as provider identity          REJECT
provider-identity record reclassified as transport            REJECT
actual exception reason hash replaced                         REJECT
cross-Job failure observation substituted                     REJECT
```

The first two retain an actual invocation record whose `typed_terminal` conflicts with the
caller-selected class and terminal. The reason attack is internally valid at the Pydantic model
level but differs from the Runner-owned authority bytes. The cross-Job attack changes the Job
parent while retaining another Job's actual invocation. All four reject before any Raw write.

```text
fully rehashed attacks                                        4 / 4
prospective downstream layer identities                       20
accepted attacks                                               0
Raw writes from attacks                                        0
```

The v26.214 negative-control directory is absent after the run.

## Noncompensatory Gates

The exact Gate partition is:

```text
R0 external scope and exact v26.213 Freeze                         PASS
R1 Runner-owned catch observation                                  PASS
R2 generic evidence and authority-bound dispatch                   PASS
R3 durable ingress mechanics retained                              PASS
R4 actual failure terminal branch in one consumer                  PASS
R5 authentic terminal to five-layer persistence                    PASS
R6 four fully rehashed provenance attacks reject                   PASS
R7 zero-Provider/credential/empirical boundary                     PASS
passed / failed                                                     8 / 0
```

These Gates supersede only the failed v26.213 outer-exception interpretation. They do not
reclassify v26.213 files or turn deterministic reference controls into model outcomes.

## Authoritative Identities

- external revision authorization:
  `finance_v26_214_external_revision_authorization:7cced9906f8fb0686efebaa74ff108aad72f59acc22eb2a81f648f25b8792fbe`;
- v26.213 Freeze:
  `finance_v26_214_v213_freeze:bc703c5042d417434b2209e4c6b9abc6a9bdde1948197b6b5f5d27f84c1556b2`;
- source and implementation:
  `finance_v26_214_source_identity:35ed907b18d8a36857460c5e8f0c45d51a3cbae1ef843f384e9ce80b387ec89f` /
  `fresh_repaired_outer_typed_exception_authenticity_implementation_binding:251ffa2fee3565a087a6e57cace459b484cce7a9fbf996ed27568844ca63a103`;
- Runner observation / dispatcher / persistence:
  `fresh_repaired_runner_owned_typed_failure_observation_binding:f2c7ab1451e134098a744bd663bb6cee180ce077123daa4b3879b367fa9bb085` /
  `fresh_repaired_authentic_typed_failure_dispatcher_binding:4cbe83d0eaeea18bcd396717265e9c78723ca335345a611c0a3ef226cab7dbef` /
  `fresh_repaired_authentic_typed_failure_persistence_binding:01fbdfefb8a68d190eaeb98b91d1c909a32170cb15a50c19139c7c22aab98230`;
- consumer / composition:
  `fresh_repaired_typed_failure_terminalizing_consumer_binding:5b42c404acdff5605e200900528782c2be6cc1afaafebca860a4750822b54183` /
  `fresh_repaired_typed_failure_single_consumer_composition_contract:a61fca81e91bf6f64a17384b7fff837aa205e730b0b797f7ef0f0ec7b81a348f`;
- execution / negative-control / scope Audits:
  `finance_v26_214_single_consumer_failure_execution_audit:b8bc968db620560bca2c8feea51899418c9a65c54887eaa482847a06e59282ff` /
  `finance_v26_214_typed_failure_provenance_negative_control_audit:ecabf168a084acfcef9d1b44e56a9fdf2be0cd8781c3ac653301a328f6e4114c` /
  `finance_v26_214_scope_boundary_audit:26ad1c02fac9c195cb9a1a2df991f5e1b71934013165c04bd8cd47fb2f75b34e`;
- Gate / Decision / Transition:
  `finance_v26_214_gate_evaluation:e1e041c1477900b19810970e2b7e4194b70c9902ca351532a7d6429b231629ef` /
  `finance_v26_214_typed_failure_authenticity_decision:7a51d84606bedce428a197d38f650029d5bb46107e51898bbce07985ba06a109` /
  `finance_v26_214_transition:e6810065c961ce14a15e34597a42b4303e0f09b4a121510549363c50ce34bbf9`;
- report:
  `finance_v26_214_typed_failure_authenticity_report:eba06903fee64b2aafa5d75f56a77a7b0a701d97332e07eb827cbd40ff9b1073`;
- Artifact Manifest / Root:
  `finance_v26_214_artifact_manifest:4760d3755620c9a5553f5f46b6cc6b6c04b0b3f6fc4358355de45169c9fc364a` /
  `finance_v26_214_artifact_root:8104b6ffefb646b20cd20b3d5419fd8537c1db4cd4dd8dd787ba96f37e910c71`.

## Reproducibility

The exact source commit and tree are
`9bf04108c0b3d7d8f979246c786089927eedb16f` and
`7dfacd9eabbf8efb6f2269b362c6e2c739fcfca9`. Four source files and seven executable symbols are
bound byte-for-byte. The formal directory contains 63 files and 1,535,767 bytes; its
self-excluding Manifest binds 62 members and 1,523,563 bytes.

Focused v26.214 tests pass 8/8, including a complete byte-identical second build. Focused
PyCompile, Ruff check/format, and no-import-follow Mypy pass. The adjacent v26.209-v26.214 suite
passes 49/49, including all predecessor and v26.214 rebuild tests; package-wide Ruff passes.

## Boundary And Only Permitted Successor

The only permitted successor is:

```text
fresh_repaired_outer_typed_exception_observation_authenticity_and_single_consumer_
failure_terminalization_preflight_independent_audit_only
```

That audit may independently rebuild the exact v26.214 directory, reconstruct the eight actual
Runner exception observations and five-layer chains, and reproduce the four attacks with zero
Provider calls. It may not issue or consume an online authorization.

The v26.211 authorization remains unconsumed. Even after a passing independent audit, a separate
new online authorization must bind all v26.214 Runner-observation, dispatcher, persistence,
consumer, and composition parents. Direct v26.211 consumption, Provider execution, the repaired
192-Job online run, frozen-condition change, empirical estimation, QA, Mapper, State, frequency,
Contribution, VTDO, training, release, and production remain forbidden.
