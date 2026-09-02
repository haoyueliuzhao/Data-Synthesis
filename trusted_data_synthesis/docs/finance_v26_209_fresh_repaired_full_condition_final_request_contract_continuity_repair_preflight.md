# Finance v26.209 Fresh Repaired Full-Condition Final Request Contract Continuity Repair Preflight

Audit date: 2026-09-02

## Decision

Finance v26.209 consumed only:

```text
fresh_repaired_full_condition_executable_runner_final_request_contract_
continuity_repair_preflight_only
```

The exact 14,180-byte review is bound at SHA-256
`aca402146bae4afd780bf0ba06e5736744aefb787f9c2064071311b53ba13902`.
It classifies v26.208 as a reproducible partial mechanism preflight that failed at frozen Final
request continuity, requires a narrow revision, and authorizes neither Provider execution nor an
online authorization. The exact 18-byte operator directive `参照审计修订` is separately bound at
SHA-256 `8a13fc4ca97304bb08362b5fbc22809e35375df599fa8866c93fb5eae69798e4`
and authorizes only this repair preflight.

The resulting decision is:

```text
fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_
repair_preflight_passed_independent_audit_required_online_execution_blocked
```

The only permitted successor is:

```text
fresh_repaired_full_condition_executable_runner_final_request_contract_continuity_
repair_preflight_independent_audit_only
```

## v26.208 Freeze And Scope Correction

All twenty v26.208 formal files and 2,596,518 bytes revalidate exactly, including all nineteen
self-excluding Manifest members and 2,593,272 bound bytes. Its formal files, identities, stored
five-pass Gate, and original Decision remain immutable historical records. The new review does not
rewrite them. It supersedes only their interpretation:

```text
stage build and artifact reproducibility                    retained
shared executable Runner route                              retained
frozen full-condition request continuity                    failed
first blocker
  frozen_final_provider_request_envelope_not_preserved
online readiness                                            failed
```

The exact v26.208 source commit/tree remain
`f9f532ea449f786dd0058b60345f04091a6f77f5` /
`3a9b1ef4e6d8c6903d903086e280e0a36ad16e52`. The formal v26.208 execution Census is used only
as a comparison input after its bytes and parents are revalidated.

The v26.209 comparison finds a wider but mechanically related downstream surface than the first
Final-only blocker named by the review. Once a typed rejection and Correction were committed into
the v26.208 main Runtime state, some later registered requests also differed from their v26.206
targets:

```text
phase                       exact match   mismatch
first Action                    192          0
subsequent Action               216         72
Correction                       48         72
Final                             0        192
```

Message and request counts have the same partition. This does not alter the review's first-blocker
classification: the direct source defect remains the missing Final JSON-explicit envelope, while
the later Action/Correction differences are downstream consequences of treating diagnostic
Correction branches as one linear reference trajectory. No v26.208 artifact or result is
reclassified as empirical.

## Narrow Repair

The only Provider-facing compilation change is the Final branch. The v26.208 path was:

```text
current dynamic raw Final Prompt
  -> direct user message
  -> canonical request
```

The v26.209 path is:

```text
current dynamic Runtime result
  -> current raw Final Prompt
  -> frozen v26.192 JSON-explicit envelope
       prompt_core
       prompt_kind = final
       provider_output_protocol
  -> canonical user message
  -> canonical request
  -> validation certificate
  -> pre-transport receipt
  -> shared injected transport seam
```

The exact frozen parents are:

- Prompt Contract:
  `json_explicit_prompt_contract:d0094129a9f434aaa5f023d049fb9f10f300e04cc7140bf484012b41d4413afe`;
- Prompt Schema:
  `json_explicit_prompt_schema:17d41e7a1f7358bdb254fc34ce49e9638c4bdcab737af5d633474c82f0234c1b`;
- v26.193 exact Prompt evidence set:
  `json_explicit_exact_prompt_evidence_set:4982ca86b6a5862c0bed33cee02bfb5a2085d4d60a6c0495b09d548584f9a371`;
- v26.206 repaired callsite Census:
  `finance_v26_206_repaired_callsite_census:b866df6946418db850369566f6c5857076c7b48d7747960bfd5faadbcbdadb4e`.

Every v26.193 evidence row binds the exact v26.192 Contract and Schema before execution begins.
Action and Correction continue to use the exact v26.206 four-field repaired compiler. Final keeps
the frozen Final Grammar and Parser.

## Registered-Callsite Control Geometry

The v26.206 authoritative evidence surface contains one primary Action callsite for every reached
reference State and 120 additional Correction callsites produced from registered rejection
side branches. It is not a single model response trajectory in which all 120 rejections happened.
v26.209 preserves that geometry explicitly:

```text
reference main paths                                          192
first / subsequent reference Action calls               192 / 288
registered Correction side-branch calls                       120
Final calls                                                    192
total injected-transport calls                                 792
single-linear-Provider-trajectory claim                      false
```

For each main State, the actual Runner sends the reference Action through the shared path and
commits it to the main state. If the frozen Catalog registers an invalid Candidate at that State,
a copy of the pre-Action state is locally rejected and the resulting current Correction Prompt is
sent through the same Runner. The side branch commits one reference Correction but does not replace
the reference main state. This supplies actual Correction route evidence while keeping the exact
registered subsequent Action and Final request set. The five separate failure controls continue to
exercise invalid model responses through the shared route.

Correction side-branch counts remain zero for 144 Jobs and one through four for twelve Jobs each.
All 192 main reference paths reach terminal State and pass frozen Base, Mechanism, and Qualified
checks. Their 192 Raw, Result, Trace, and Outcome identities per layer are scripted controls, not
empirical model outcomes.

## Exact Request Continuity Gate

Each of the 792 actual invocation records persists canonical message and request JSON, SHA-256,
and byte count. Model validation reparses each JSON string, reserializes it canonically, and checks
its recorded hash and length. Rows align by exact source v26.206 Job and invocation index; phase,
and for Action/Correction also current State and ordered Candidate IDs, must match.

The exact primary result is:

```text
Action/Correction canonical-message matches              600 / 600
Action/Correction request-body matches                    600 / 600
Final canonical-message matches                           192 / 192
Final request-body matches                                192 / 192
Final actual message bytes equal v26.193                  192 / 192
Final actual request bytes equal v26.193                  192 / 192
total registered message matches                          792 / 792
total registered request matches                          792 / 792
missing / duplicate / extra coordinates                    0 / 0 / 0
maximum message / request bytes                       34,404 / 34,565
```

The maximum values return to the exact v26.206 summaries under the same canonical measurement.
They are secondary summaries; the per-row hashes, lengths, and the 192 direct Final actual-byte
equalities are the primary Gate.

## Executable No-Bypass Route

`FinalContinuityRepairedFullConditionRunner` retains one wrapper for Action, Correction, and
Final. Each calls exactly one `_invoke_current_state`. Only that shared entry calls the single
`InjectedTransportSeam.send`:

```text
current Runtime State
  -> authoritative message compilation
  -> canonical request builder
  -> validation certificate
  -> pre-transport receipt
  -> injected transport
  -> public projection
  -> exact Parser
  -> State/Candidate or Final-envelope validation
  -> Runtime step/finalize
  -> terminal dispatch
```

Source AST and 792 dynamic records confirm one compiler, builder, validator, receipt, and transport
call in this order. Direct Provider/network calls, old-ABI routes, unrepaired routes, and
renderer/request/validator bypasses are zero.

## Dynamic Nonreference Final Control

One separate control selects a current legal nonreference Action from a three-Candidate State. It
produces a next State different from the reference successor, and its second invocation binds that
new State. The control then completes the current dynamic path and sends one Final call.

The dynamic Final message has exactly the frozen top-level fields, binds the exact v26.192 Contract,
and requests `json_object`. Its request SHA-256 differs from the same Job's registered reference
Final request because its accepted prefix and public observations differ. The control uses four
Action dispatches and one Final dispatch, for five transport dispatches in total. It enters no
Manifest or empirical denominator and makes no Provider call. This count corrects the narrative
only; the immutable formal `dynamic_nonreference_branch_audit.json` already records `4 / 1 / 5`.

## Typed Failures And Boundary

Five controls retain their actual shared-route terminal projections:

```text
invalid first Action ABI  -> first_response_abi_invalid
unknown current Action    -> first_action_reference_invalid
invalid Correction ABI    -> correction_response_abi_invalid
invalid Final ABI         -> final_response_abi_invalid
typed outer failure       -> instrument_failure
```

Each makes one injected dispatch and produces one typed diagnostic Outcome with zero exception
escape. Provider calls, credential lookups, empirical rows, estimator calls, numerators,
estimates, confidence intervals, online authorizations, QA, Mapper, State, frequency,
Contribution, and VTDO rows remain zero.

## Gates

All five noncompensatory Gates pass:

```text
R0 exact v26.208 freeze and Provider-facing condition          PASS
R1 fresh executable identity closure                            PASS
R2 shared-entry no-bypass plus frozen request continuity        PASS
R3 zero-Provider registered full-condition control              PASS
R4 typed failures and Estimand/resource boundary                PASS
passed / failed                                                   5 / 0
```

## Authoritative Identities

- authorization:
  `finance_v26_209_external_final_request_continuity_authorization:ecafe5959d8566cbe0258c21cded1056ca4680beca0205e32d3a57d463217915`;
- v26.208 Freeze:
  `finance_v26_209_v208_predecessor_freeze:ef7cf0790d7bd5a65b6a9115f5f4d3d37a450650f169345b749df5e27a893098`;
- implementation Binding:
  `fresh_repaired_final_continuity_executable_route_implementation_binding:12c518f9f8f839d6c65a67c432c4177bc8ef95cb0188036796a08fd31c1b65e7`;
- Package Catalog:
  `fresh_repaired_final_continuity_executable_full_condition_package_catalog:078c9b261f2d05cf6c9b44de7e04372886cf6c5b1f3083439c56433694141993`;
- Manifest:
  `fresh_repaired_final_continuity_executable_full_condition_manifest:f73da35ef4bbc3cfb6c4782918985ef649d89b6d6d09831f35354154d23b9621`;
- Runner:
  `fresh_repaired_final_continuity_executable_full_condition_runner:e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266`;
- Execution Contract:
  `fresh_repaired_final_continuity_executable_full_condition_execution_contract:fc10dce5cdb2a3f677c93ad0780b5aa2b2e22eb44d6a1bf3c1d43d11ac6540d4`;
- invocation Census:
  `finance_v26_209_executable_invocation_census:e93f0b9121399d37bf1ed32137437117d2aae989ab41682e09cdc0c489e72212`;
- request Continuity Audit:
  `finance_v26_209_frozen_request_continuity_audit:7c8bab5493eb123854b127c01594251c7c3099a86b952339eb3cd66567fba9f1`;
- execution control:
  `finance_v26_209_full_condition_execution_control_audit:2ddb129a094d945e1a708c8ba888ac427aac5132cd7b0821865ad61ea0aac6eb`;
- no-bypass Audit:
  `finance_v26_209_source_dynamic_no_bypass_audit:b19caeb33244bebc3e5ec0c8dfd4e1e9a72bddd5ed70bed1e7f717f0501c262f`;
- failure controls:
  `finance_v26_209_typed_failure_control_audit:97a487a0e954a837b56e525075eab844d3006399cd498c52c8de8029c806822c`;
- dynamic branch Audit:
  `finance_v26_209_dynamic_nonreference_branch_audit:19b20bada7acfdc9cba92f434e25701e79749d8ec086e22dfebe7fca5b285a73`;
- boundary Audit:
  `finance_v26_209_estimand_resource_boundary_audit:2aa009e6ed1c961f08aa745c5bf8c4cc2682af59d24e76fa192dd8adcf866e24`;
- Gate Audit:
  `finance_v26_209_final_request_continuity_gate_audit:1510a331b8895fe64d37fa06a2c3d2705c23fd39600352c1c370da95a26c2b61`;
- Transition:
  `finance_v26_209_transition:7fe53c104d1b8c6be59399a54a5b204c3d9e9fd8edaa798d1d820feadd08138d`;
- report:
  `finance_v26_209_final_request_contract_continuity_repair_preflight_report:20c805ed3991c1eeec9f11e09335359cd8b0a4788f097c9ff0ea4db1d6983e25`;
- Artifact Manifest:
  `finance_v26_209_artifact_manifest:1ec5df9edc0fb7b89921bbe3c154856e72e362cbbaee58a191bf9f275fc0bcf9`;
- Artifact Root:
  `finance_v26_209_artifact_root:76ef4cdb9cc0703f6bee2fd76c9c8ea7cbce5277337ff882ffcb44f8085e4770`.

## Source, Artifacts, And Verification

The authoritative source commit/tree are
`5809e9782515e55ee797b43730584d5d860aaa5c` /
`b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf`. The formal directory contains 21 files and
44,916,386 bytes. Its self-excluding Manifest binds twenty members and 44,912,918 bytes. The
report is 3,157 bytes at SHA-256
`88c5c110bf91601ca131bab384da01d3717a5402e24ee7355f5a78617f9eb500`.

Focused v26.209 tests pass 9/9, including a complete empty-directory 21/21 byte rebuild. The
adjacent v26.206-v26.209 suite passes 33/33. Focused PyCompile, Ruff check/format, and
no-import-follow Mypy pass; package-wide Ruff passes.

Several preliminary source commits remain ordinary immutable Git history. Before formal output,
their temporary builds failed closed while localizing the Final result-ID coordinate difference,
the downstream Action/Correction State drift, the production rejection return type, and an
overstrong v26.208 Action/Correction match assumption. No preliminary build wrote the formal
directory, made a Provider call, read a credential, or produced an empirical row. The final
formal directory binds only the authoritative source commit above.

## Remaining Boundary

This stage proves a credential-free executable and request-continuous preflight. It does not prove
model behavior, online readiness by independent review, or Capability. The full repaired 192-Job
Provider execution, online authorization, additional interface calibration, interface-factor
decomposition, Parser relaxation, historical adaptation, semantic or Runtime changes, QA,
Mapper, State frequency, Contribution, VTDO, training, release, and production remain forbidden
until a new independent audit decision.
