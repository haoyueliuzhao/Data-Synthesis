# Finance v26.213 Fresh Repaired Observation-Derived Terminal Single-Consumer-Path Repair Preflight

Audit date: 2026-09-02

## Post-Review Scope Correction

The subsequent exact 14,653-byte review at SHA-256
`64c6b8c6bc2a62f8205ae7007169cedfc3d9fe184b2740b3d93b398c672339a7` retains v26.213 as
`VALID_SCOPED_COMPLETED_AND_PARSER_TERMINAL_PREFLIGHT` but fails its stronger full-terminal
claim at `OUTER_TYPED_EXCEPTION_EVIDENCE_AUTHENTICITY`. The explicit `terminal_kind` argument
removal, all 192 completed Runner paths, parser/reference/correction-bound terminal derivation,
and conditional terminal-to-five-layer persistence remain valid.

The eight outer typed-exception evidence subclasses were not bound to
`invocation_record.typed_terminal`, the actual caught exception class, or the actual exception
reason. A caller could therefore wrap an instrument-failure record as provider-identity evidence,
fully rehash the decision and five layers, and obtain a self-consistent but false terminal. The
old eight outer rows and the old R4/R6 passes are retained only as immutable honest-constructor
diagnostics. The current scoped decision is:

```text
v26_213_main_completed_and_parser_terminal_paths_passed_
but_outer_typed_exception_evidence_can_be_reclassified_
by_caller_selected_evidence_subtype
```

The exact 30-byte directive `参照审计继续实验修订` authorized only the zero-Provider v26.214
repair. v26.214 now replaces the eight subtype authority with a Runner-owned failure observation,
one generic evidence type, authority-bound dispatch, an in-consumer failure terminal branch, and
four fully rehashed attacks. Every v26.213 formal byte and identity remains unchanged. The old
independent-audit transition below is historical and superseded; the current transition is only
v26.214's credential-free independent audit. See
`docs/finance_v26_214_fresh_repaired_outer_typed_exception_observation_authenticity_preflight.md`.

## Decision And Scope

Finance v26.213 consumed only:

```text
fresh_repaired_full_condition_observation_derived_terminal_
single_consumer_path_repair_preflight_only
```

The exact 16,582-byte external review is bound at SHA-256
`941b3137f2d0823ef1ec681c4364ee6d6aca242d9edc9d35b1b3dfdbea8396a9`.
It classifies v26.212 as
`VALID_SCOPED_DURABLE_INGRESS_AND_PERSISTENCE_MECHANICS_PREFLIGHT` but failed at
`AUTHORITATIVE_TERMINAL_PROVENANCE_AND_HANDOFF`. The exact 36-byte operator directive
`参照审计报告继续实验修订`, SHA-256
`dc2b598ec3667bd0e26354d1dac1ca447fa87acea50bd30a5fc245a9c35374e9`, authorizes only this
credential-free, zero-Provider repair preflight.

The formal decision is:

```text
fresh_repaired_observation_derived_terminal_single_consumer_path_
preflight_passed_independent_audit_required_online_execution_blocked
```

This stage closes one prospective engineering path from actual Runner/parser/typed-exception
evidence to a derived terminal and its five durable evidence layers. It is not an online
authorization, Provider execution, model result, empirical Capability row, or Capability
estimate. The exact v26.211 authorization remains unconsumed.

## v26.212 Freeze And Scope Correction

All 1,067 v26.212 formal files and 2,239,071 bytes revalidate, including all 1,066
self-excluding Manifest members and 2,017,584 bound bytes. Its source commit/tree,
`9173b16cc1340449fa18b4030b8d2c7686fa3b5f` /
`2b3562714d70b587c4ef1424e15885e5f1e92880`, and Artifact Root remain immutable.

The following v26.212 results are retained at their exact narrow scope:

```text
v26.211 exact Freeze                                      PASS
source-bound component identities                         PASS
durable consumption / Run Start Receipt / factory order  PASS
exact v26.209 192-Job Runner replay                       PASS
five-layer persistence order and byte checks              PASS
sixteen Registry labels serializable                      PASS_DIAGNOSTIC_ONLY
```

The v26.212 formal seven-pass Gate, Decision, and Transition remain unchanged historical bytes.
Their full terminal-authority interpretation is superseded. The retrospective scoped decision is:

```text
v26_212_component_level_ingress_and_persistence_controls_passed_
but_authoritative_terminal_derivation_and_single_path_handoff_failed
```

The first blocker was
`caller_supplied_terminal_kind_replaces_observation_derived_terminal_dispatch`. Its dispatcher
accepted a terminal label rather than actual Runner, parser, verifier, or typed-exception
evidence, and its build joined Runner replay to persistence after the Runner had completed.

## Observation-Derived Terminal Authority

The replacement dispatcher exposes only:

```python
dispatch(observed_evidence)
```

It accepts a strict discriminated union of thirteen observed-evidence classes and does not
accept `terminal_kind`, a terminal policy, or a caller label. The sixteen reachable terminal
decisions are derived as follows:

```text
completed_qualified                 completed Runner + Base/Mechanism conjunction
completed_invalid                   completed Runner + Base/Mechanism conjunction
first_response_abi_invalid          first-Action parser rejection
correction_response_abi_invalid     Correction parser rejection
first_action_reference_invalid      parsed first Action absent from current Candidates
correction_action_reference_invalid parsed Correction absent from current Candidates
correction_attempt_typed_invalid    actual repeated-invalid correction-bound terminal
final_response_abi_invalid          Final parser ValidationError evidence
provider_failure_no_payload         typed provider-no-payload exception
provider_transport_failure          typed transport exception
privacy_rejection                   typed privacy exception
resource_budget_exhausted           typed resource exception
instrument_failure                  typed instrument exception
provider_identity_failure           typed provider-identity exception
thinking_integrity_failure          typed Thinking-integrity exception
usage_integrity_failure             typed Usage-integrity exception
```

`CompletedRunnerEvidence` embeds the actual frozen step-Runtime Final result, exact Base,
Mechanism, and Qualified reports, public Final payload and hash, and complete v26.209 invocation
records. It independently revalidates those objects and enforces
`Qualified = Base and Mechanism`. The persistence pipeline reparses the observed-evidence union,
reruns the dispatcher, and requires canonical equality with the supplied derived decision before
writing any Raw byte.

## One Source-Bound Consumer Call Chain

The sole entry is `RepairedOnlineExecutionConsumer.execute_preflight`. Its source-bound order is:

```text
exact v26.211 authorization guard
  -> exclusive durable preflight consumption receipt
  -> exclusive durable Run Start Receipt
  -> credential/factory Gate with zero credential lookup
  -> exact v26.209 current-State Runner
  -> actual Final result or typed failure evidence
  -> observation-derived terminal dispatch
  -> Raw -> Result -> Trace -> Outcome -> checkpoint
```

The top-level build invokes this consumer once. It does not separately call the inner Runner,
terminal audit, or persistence audit, and it performs no build-level terminal join. The isolated
preflight lease reuses v26.212's durable no-replace and factory prerequisites without consuming
the v26.211 online authorization.

Authoritative source inspection records one consumer entry, one evidence-only dispatcher, zero
terminal-label input, and one Runner-to-terminal-to-persistence call chain. Direct Provider,
network, and credential-environment routes are absent.

## Exact 192-Job Actual-Runner Control

All 192 exact v26.209 Manifest Jobs execute through the one consumer entry and the actual
`FinalContinuityRepairedFullConditionRunner`. The exact registered geometry is reproduced:

```text
Jobs / completed Runner evidence                       192 / 192
actual Runner invocations / transport dispatches       792 / 792
first / subsequent reference Action                    192 / 288
registered Correction side branches                          120
Final                                                         192
observation-derived completed_qualified terminals             192
build-level terminal joins / caller terminal arguments      0 / 0
exception escapes / empirical rows / Provider calls       0 / 0 / 0
```

The 120 Corrections remain registered side-branch route controls on copies of their pre-Action
States. They are not a claim that one model trajectory simultaneously selected the reference and
invalid Action.

Each of the 192 actual Final results is Base-valid, Mechanism-qualified, and Qualified-valid.
The dispatcher derives `completed_qualified` from those exact factors. The same single consumer
path immediately writes one five-layer chain per Job:

```text
Raw / Result / Trace / Outcome / checkpoint       192 each
total persisted main-path layer files                   960
formal empirical rows                                      0
```

Every main-path Raw object retains the complete observed evidence, including the Final result and
invocation tuple. These are deterministic reference controls, not model outcomes or Capability
evidence.

## Sixteen Evidence-Triggered Terminal Controls

Sixteen controls construct actual Runner result, parser rejection, Action-reference failure,
correction-bound terminal, Final parser rejection, or typed exception evidence. Expected terminal
names are retained only as post-dispatch test oracles. No expected terminal is passed to the
Runner, dispatcher, writer, or reconstructor.

```text
actual evidence controls / reachable terminals          16 / 16
exact derived-terminal matches                          16 / 16
distinct observed-evidence classes                           13
persisted Raw/Result/Trace/Outcome/checkpoint references     80
label-only controls / caller terminal arguments             0 / 0
exception escapes / empirical rows / Provider calls      0 / 0 / 0
```

The completed-invalid evidence comes from an actual legal nonreference Runner path and retains
the full Final factorization. The Action, Correction, and Final invalid controls execute their
actual frozen parser/reference paths. The correction-bound row validates the actual public typed
terminal. The eight outer rows are separate typed exception-evidence subclasses executed through
the v26.209 Runner control route; they are diagnostic failure controls, not observed Provider
failure frequencies.

## Terminal-Provenance Negative Controls

Four noncompensatory attacks cover the audit's minimum denominator:

```text
caller terminal API absent                                  rejected
Qualified evidence relabeled as another terminal            rejected
cross-Job evidence/decision substitution                     rejected
completed-invalid factors inconsistent with Final result    rejected
```

The relabel and cross-Job attacks each construct a complete in-memory, fully rehashed
Raw/Result/Trace/Outcome/checkpoint identity chain before submitting the inconsistent evidence
and decision. The shared production validator rederives the terminal and rejects both before a
Raw write. Thus:

```text
controls / rejected / accepted                         4 / 4 / 0
fully rehashed downstream attacks                            2
fully rehashed downstream layer identities                  10
attack Raw writes / Provider calls                         0 / 0
```

The inconsistent-factor control is rejected during strict completed-evidence validation. The
dispatcher signature itself supplies the caller-label-API absence control.

## Gates And Resource Boundary

The exact noncompensatory partition is:

```text
R0 external scope and exact v26.212 Freeze                  PASS
R1 source-bound observation union and no-label API           PASS
R2 durable ingress mechanics retained                        PASS
R3 exact v26.209 Runner replay                               PASS
R4 Runner evidence -> authoritative terminal                 PASS
R5 authoritative terminal -> persistence single path         PASS
R6 sixteen evidence-triggered terminals and negative controls PASS
R7 zero-Provider/credential/empirical boundary               PASS
passed / failed                                              8 / 0
```

The stage creates one isolated preflight lease and one preflight Run Start Receipt. Current
v26.211 authorization consumption, new online authorizations, Provider calls, Provider-client
constructions, credential lookups, empirical rows, empirical estimates, QA reads, Mapper, State,
frequency, Contribution, and VTDO rows are zero.

## Authoritative Identities

- external revision authorization:
  `finance_v26_213_external_revision_authorization:06d6672ad693e5b5738f280d9fa93fcca9dd7f33dec0a5b5e25affcd604ce496`;
- v26.212 Freeze:
  `finance_v26_213_v212_freeze:ecea5a50e7dec38fded0cf4df10e8fe141df95ed2cc71b7f5300cfb686b96d02`;
- implementation Binding:
  `fresh_repaired_observation_derived_terminal_implementation_binding:171ff03d40b256076c9655868cf513e0787489cf0c6936cbcb001dafc82ba7cb`;
- observation-derived dispatcher Binding:
  `fresh_repaired_observation_derived_terminal_dispatcher_binding:10a51ef2cc7f7ce20ad63918507c201f12112e34729e1088ab272da3820b209f`;
- observation-bound persistence Binding:
  `fresh_repaired_observation_bound_persistence_binding:21f1608bceeb683c59c4421eb836404709e7136f01a2c34b634de1c95532eff9`;
- single consumer Binding / composition Contract:
  `fresh_repaired_single_online_consumer_implementation_binding:1c5923d5c9856c3c4d084ef2f05aaf88ab02cbcb3bc1b899988ee464eda7bcc2` /
  `fresh_repaired_observation_derived_single_consumer_composition_contract:f27da41c720b6041e918b5018291403b15281b990975dd411acd9eff4a1a4644`;
- isolated consumption / Run Start Receipts:
  `fresh_repaired_preflight_authorization_consumption_receipt:22da26bad83f413a08b8bff3d6b4fb960d41418a1dd35cf93b8b190072e591e3` /
  `fresh_repaired_preflight_run_start_receipt:c19e84f6927041b487bb690c8ecb174164acd62f2e4c8235743e247d4fb1b0e6`;
- single-consumer execution Audit:
  `finance_v26_213_single_consumer_execution_audit:0ae5857573950e79227e14fb47561daa60626076cb834ec2d2a841d287fdeb83`;
- terminal-evidence Audit:
  `finance_v26_213_terminal_evidence_audit:0d5ad1563251c7fc4809bc5807ea66ac6575ee7b10900183fd9ca63e82fe3794`;
- provenance negative-control Audit:
  `finance_v26_213_terminal_provenance_negative_control_audit:ff0d187f9e5b28440702945ec9d34503b53fdc073a442364a6325424bc76800b`;
- scope boundary Audit:
  `finance_v26_213_scope_boundary_audit:1e7733e1c4bacad59616c7ab6e8717ddcc6a62e2ab2841b240c6e46f6624acf2`;
- Gate Evaluation:
  `finance_v26_213_observation_terminal_gate_evaluation:fa996261fe1e546d89059906ad34bd08fcf0bba38ab74bf59bf981c7c184e536`;
- Decision / Transition:
  `finance_v26_213_observation_terminal_decision:2890a3beeb41b9379bcfd70aeb385f3911dca15e03def85bfa886355a4c59afa` /
  `finance_v26_213_transition:a62ea6bff46785dc9acbddba1690645b34f763b4f1e84ef5951ea78629022c3a`;
- report:
  `finance_v26_213_observation_terminal_report:2889dd181f71f5753018d87087af2e123b0991d72a7617a6be29938cb657d813`;
- Artifact Manifest / Root:
  `finance_v26_213_artifact_manifest:e3563bf59ba7aa8fc8d1d1cfb8a48c6e5b98f01725bc4a789f49752e9eea67bc` /
  `finance_v26_213_artifact_root:b671d9cef0322b83ea6b815736d09f54c59671e2083042822928d2f79ece01f8`.

## Reproducibility And Current Boundary

The exact source commit/tree are
`904577d81bcd83183d3aae0bab4e9f53c9907f0d` /
`c2f2e7629b29f7dfbcc27153539a1aa5be1cdf23`. The authoritative formal directory contains
1,058 files and 58,565,824 bytes. Its self-excluding Manifest binds 1,057 members and
58,336,116 bytes. Report SHA-256 is
`7ec5c270c457eb14832fecdf77aeee06b75520b04507fc114915853a6b5fd957`.

Focused tests pass 8/8, including a complete second build with all 1,058 files byte-identical.
The adjacent v26.209-v26.213 suite passes 41/41. Focused PyCompile, Ruff check/format, and
no-import-follow Mypy pass; package-wide Ruff passes. All controls are credential-free and make
zero Provider calls.

The only permitted successor is:

```text
fresh_repaired_full_condition_observation_derived_terminal_
single_consumer_path_repair_preflight_independent_audit_only
```

That successor may only independently rebuild the exact source and formal directory, reconstruct
the 192 terminals from actual persisted evidence without using the v26.213 dispatcher or saved
terminal fields as an oracle, and compare all five layers. It may not issue or consume an online
authorization or make a Provider call. The current v26.211 authorization remains permanently
unconsumed. Even after a passing audit, a separate new online authorization must bind the repaired
v26.213 implementation, consumer, dispatcher, persistence, and composition parents. Provider
execution, the 192-Job online run, source or frozen-condition change, replacement, rerun,
recovery, empirical estimation, QA, Mapper, State, frequency, Contribution, VTDO, training,
release, and production remain forbidden.

The successor above is the immutable v26.213 historical transition. The later review blocks it
at outer-exception authenticity. The only repair candidate was
`fresh_repaired_outer_typed_exception_observation_authenticity_and_single_consumer_failure_terminalization_preflight_only`,
which was consumed only by v26.214 with zero Provider calls. The current successor is v26.214's
independent-audit-only transition; the v26.211 authorization remains unconsumed.
