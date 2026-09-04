# Finance v26.231 Fresh Exact v26.209 Unbound Provider-Failure Recovery-Population-Bound Online Execution Authorization

## Post-Review Scope Correction

The subsequent exact 10,544-byte review at SHA-256
`04a5e36142abc3ecde5706c19f9277ee1315beb6f2b5e023863aad0ab963b5bc` reclassifies v26.231
as `FAIL_NARROWLY_AT_G0`. The implementation verified the parsed self-excluding v26.229 and
v26.230 Manifests and all of their members, but did not independently bind the actual bytes of
either `artifact_manifest.json` file. A same-length top-level key reordering therefore preserved
the parsed objects and the old authorization identity while changing predecessor Manifest bytes.

The 33 Recovery Jobs, 55 historical successful-prefix calls, 33 failed requests, `3/25/5` phase
partition, continuation semantics, and residual budgets remain retained at their scoped meanings.
The historical Gate, Decision, Transition, and every formal byte remain immutable. The current
scoped decision is:

```text
v26_231_constructed_a_33_job_recovery_authorization_candidate_with_retained_
semantics_and_budget_but_did_not_bind_the_actual_bytes_of_the_v26_229_and_
v26_230_self_excluding_manifests_so_the_authorization_is_not_consumable
```

The v26.231 authorization must not be consumed. The later v26.232 repair binds both exact
Manifest byte counts and SHA-256 values before parsing, rejects both semantic-equivalent reorder
attacks, and issues a distinct unconsumed authorization. See
`docs/finance_v26_232_fresh_exact_v209_recovery_online_authorization_predecessor_manifest_actual_byte_authority_repair.md`.

## Scope And Decision

Finance v26.231 consumes only
`fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_only`.
The exact 12,817-byte external review is bound at SHA-256
`a7a93482dbd8a7944f105b670ca9eb35a042fcc87f790940ca4c8910c3a6b5e4`. It classifies
v26.230 as `PASS_AS_SCOPED`, reports `BLOCKING_DEFECT=NONE_FOUND` and
`MANDATORY_REVISION=NONE`, closes Recovery-Population authority, and identifies
`RECOVERY_ONLINE_AUTHORIZATION` as the first unclosed Gate. The exact 30-byte operator directive
`参照审计报告继续实验`, SHA-256
`2310d8996483f5f0d431940d98cbfc56a53e23aca61b59306de2d9bf61b9ec1a`, is admitted only
for this authorization-only stage.

The resulting decision is:

```text
fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_
execution_authorization_issued_not_consumed
```

One fresh one-time authorization is issued and zero authorizations are consumed. This stage
performs no Provider call, credential lookup, model-client construction, Recovery execution,
historical-prefix reissue, Run Start Receipt, empirical projection, or historical v26.226 write.
The v26.226 empirical set therefore remains incomplete.

## Exact v26.230 Independent-Audit Freeze

Before creating any authorization object, v26.231 validates every byte of the v26.230 formal
directory and its self-excluding Manifest:

```text
v26.230 source commit          bb056e0def4a7ceec4f07797b5e559ff7067f848
v26.230 source tree            413c52ab220393d6ff63855ce9735b248915c6b6
formal files / bytes           20 / 308,132
Manifest members / bytes       19 / 304,982
Manifest                      finance_v26_230_artifact_manifest:
                              8a48e037f821085a2a90934b2cac68dd739c0eefd110291f8cf03a910fd8cdf5
Root                          finance_v26_230_artifact_root:
                              3144ae72addc83cfcf2924a3ff5a70032a5e7aec07b48e2a897f6f30ad76cd64
```

The Freeze binds the exact v26.230 Report, eight-pass Gate, Decision, Transition, and ten
component Audit identities. It requires the independently reconstructed 33-source population,
55 successful-prefix calls, 33 captured failed requests, 31/2 failure partition, zero Recovery
execution, zero online authorization, and zero Provider calls. It also requires v26.230's
historical `next_stage_authorized=false`; the new authority is derived only from the new external
review and operator directive and does not rewrite that Transition.

The Freeze identity is
`finance_v26_231_v230_independent_audit_freeze:d3a56377498e167eea275da7582145f8677894847a2f4f7bd93b194e97a81fc1`.

## Exact v26.229 Recovery Parent Binding

v26.231 separately revalidates the complete 117-file, 1,105,367-byte v26.229 directory and all
116 Manifest members over 1,088,415 bytes. The new parent Binding admits the exact:

- Recovery Contract
  `finance_v26_229_recovery_contract:5313f77c0284420e5ee8a23d34f418a52b517ffb8fcf24d1efb49608dda81202`;
- Recovery Population
  `finance_v26_229_recovery_population:f7b9e21a46abd8efbace595d10ef4d479973eb5631542ee80f5a191e48979821`;
- 33 Recovery Candidate identities;
- 33 fresh Recovery Job identities;
- 33 source-row identities and 33 failed-request hashes;
- v26.230 independent replay and Recovery-Population Audits.

Every saved Candidate and Recovery Job is reparsed with its strict v26.229 model and compared
with the nested Population object byte for byte. Historical and Recovery Job identity overlap is
zero. The phase partition is independently read from v26.230 replay rows:

```text
exact Recovery Jobs                         33
first_action failures                        3
subsequent_action failures                  25
final failures                               5
successful historical prefix calls          55
reasoning-budget / JSON-decode rows      31 / 2
Candidate / Recovery Job byte matches   33 / 33
```

The 55 successful calls remain historical public-projection evidence only. Their actual saved
Usage totals are independently summed from the v26.229 source rows:

```text
historical successful-prefix input tokens     351,522
historical successful-prefix output tokens    314,076
historical successful-prefix total tokens     665,598
```

The exact prefix-call distribution is `{0:3, 1:11, 2:13, 3:6}`. No successful prefix call is
authorized for reissue. The resulting parent Binding is
`fresh_v26_231_exact_recovery_parent_binding:9a67201347027bd2dc147bebf39ec2825616c6a3ead1acc6db7c8b038df95665`.

## Recovery Execution Semantics

The authorization chooses the complete continuation interpretation required by the review:

```text
locally replay exact saved successful public projections
  -> reach the exact frozen failed current State
  -> issue the exact captured failed request once
  -> if successful, continue the exact v26.209 current-State Runner
  -> stop only at a fresh Recovery terminal or source-bound Recovery failure
  -> persist fresh Recovery evidence
```

This is not a 33-call request-only retry. The five Final failures can complete after the first
online response, but the three first-Action and 25 subsequent-Action failures may require later
Action, Correction, or Final calls. Consequently the authorization binds both the first 33
failed-request calls and all allowed continuation calls.

The first online request for every Recovery Job must have actual canonical bytes equal to its
captured failed request. The model and request route remain:

```text
model                 deepseek-v4-flash
thinking.type         enabled
response_format.type  json_object
max_tokens            16,384
```

`max_tokens` is deliberately unchanged. The stage therefore makes no unsupported claim that a
larger Completion bound would repair the 31 reasoning-budget failures, and it does not disguise
a Completion-bound change as the v26.226 condition. Success, repeated reasoning exhaustion,
JSON validity, later Runtime completion, and the final terminal partition remain unmeasured.

## Explicit Residual Resource And Call Budget

For each Recovery Job, historical successful-prefix accounting is retained in the trajectory
ledger but starts at zero in the new Provider billing ledger. Original failed-call Usage is not
imputed into the continued trajectory. The residual limits are exact arithmetic from the v26.209
per-Job Contract:

```text
remaining primary requests       21 - successful_prefix_call_count
remaining Provider calls         23 - successful_prefix_call_count
remaining transport invocations  24 - successful_prefix_call_count
remaining rollout tokens         1,120,000 - successful_prefix_usage_tokens
```

The resulting per-Job Provider limit distribution is `{20:6, 21:13, 22:11, 23:3}`. The complete
Population limits are:

```text
exact failed-request first online calls          33
maximum online Primary requests                 638
maximum online Provider calls                   704
maximum online transport invocations            737
maximum online rollout tokens            36,294,402
maximum Prompt bytes per invocation          60,000
```

The 704-call value is a noncompensatory worst-case ceiling, not an expected call count, estimate,
or instruction to consume all available calls. A repeated Provider failure is not eligible for
an ad hoc replacement retry. The Runner must stop at its typed Recovery boundary and preserve
the observed result for independent postrun audit.

The Execution Contract identity is
`fresh_v26_231_recovery_execution_contract:48705123b548e499afb2f3553d10ee454d15975e54b8a275ce3b732f107f70e0`.

## Source-Bound Future Composition

The exact future order is:

```text
exact fresh authorization bytes
  -> precredential parent/scope/budget Guard
  -> consume authorization exactly once
  -> durable consumption Receipt
  -> durable Recovery Run Start Receipt
  -> credential lookup and Provider construction
  -> local replay of 55 historical successful public projections
  -> exact failed-request dispatch once per Recovery Job
  -> exact v26.209 current-State continuation to fresh terminal
  -> fresh Recovery terminal or source-bound failure persistence
  -> Raw before Result -> Trace -> Outcome -> checkpoint
```

Historical successful responses cannot be presented as fresh Provider responses. Historical Job
IDs remain parents only. The composition forbids a replacement 192-Job run, v26.226 terminal
backfill, historical mutation, Recovery-Population expansion, and empirical estimation during
execution. Its identity is
`fresh_v26_231_recovery_online_execution_composition:cf18a6134e0dea327460a28deae4ecb4e314d3aef655074b2ed97ae6fa6561a7`.

## Fresh Authorization And Precredential Admission

The new authorization is
`fresh_v26_231_exact_recovery_online_execution_authorization:d54c68b13db02db4582f7e587973b61af431efa714f1ba3d6473939f4b12c06d`.
It binds the exact external decision, v26.230 Freeze, v26.229 parent Binding, Recovery Execution
Contract, Composition, sorted 33-Job set and its set hash. It permits at most one future
consumption for exactly:

```text
fresh_exact_v209_unbound_provider_failure_recovery_population_bound_
online_execution_only
```

One legal request passes only as a diagnostic nonconsuming probe. Eighteen invalid controls reject
before consumption, Receipt, credential, client, writer, or Provider activity. They cover missing
or modified authorization bytes; changed stage, Freeze, parent, Contract, Composition, or Job
set; missing Provider or continuation intent; historical-prefix reissue; historical mutation or
terminal backfill; replacement run; extra Recovery Job; `max_tokens` change; empirical
estimation; and QA integration.

```text
legal / invalid controls             1 / 18
authorization consumptions                0
Run Start Receipts                        0
post-Guard probes                         0
credential lookups / Provider calls   0 / 0
```

The Admission Audit is
`finance_v26_231_precredential_admission_audit:e305c7630802ca725b6be6cbd8e05dd55ad9421788722188bdc7fa19308b8f1a`.

## Fully Rehashed Parent Attacks

Ten attacks replace the external-decision, v26.230 Freeze, Recovery parent, Execution Contract,
Composition, or one of five exact Recovery Job members. Each candidate Authorization is fully
rehashed and schema-valid. Every candidate still rejects at the expected-byte Guard before any
post-Guard probe.

```text
attacks / rejected / accepted          10 / 10 / 0
fully rehashed Authorization objects           10
post-Guard probes / Provider calls           0 / 0
```

The attack Audit is
`finance_v26_231_parent_attack_audit:4387ed3fbef09365d181bbe7d19028bcc2fba251f3e3666a1892ac4916a78a24`.

## Noncompensatory Gates

```text
G0 external scope and exact v26.230 Freeze                         PASS
G1 exact v26.229 Contract, Population, and 33 Jobs                 PASS
G2 exact 55-prefix and 33 failed-request authority                 PASS
G3 continue-from-failure-to-terminal semantics                     PASS
G4 explicit residual resource and call budget                      PASS
G5 fresh one-time online authorization                             PASS
G6 precredential Guard and fully rehashed parent attacks           PASS
G7 zero-Provider/Recovery/empirical current-stage boundary         PASS
passed / failed                                                     8 / 0
```

No Gate compensates for another. The Gate identity is
`finance_v26_231_gate_evaluation:713932e60414c905a5e602013372d13522d9b90ed76431ddbec452e0d7e03527`.

## Authoritative Identities

The principal v26.231 identities are:

- external decision / v26.230 Freeze:
  `finance_v26_231_external_online_authorization_decision:3a5beaeea1c70ec319f477f94af0d59654b36971138c42fcb5f0ab7698e483dc` /
  `finance_v26_231_v230_independent_audit_freeze:d3a56377498e167eea275da7582145f8677894847a2f4f7bd93b194e97a81fc1`;
- parent / Execution Contract / Composition:
  `fresh_v26_231_exact_recovery_parent_binding:9a67201347027bd2dc147bebf39ec2825616c6a3ead1acc6db7c8b038df95665` /
  `fresh_v26_231_recovery_execution_contract:48705123b548e499afb2f3553d10ee454d15975e54b8a275ce3b732f107f70e0` /
  `fresh_v26_231_recovery_online_execution_composition:cf18a6134e0dea327460a28deae4ecb4e314d3aef655074b2ed97ae6fa6561a7`;
- authorization / Admission / parent attacks:
  `fresh_v26_231_exact_recovery_online_execution_authorization:d54c68b13db02db4582f7e587973b61af431efa714f1ba3d6473939f4b12c06d` /
  `finance_v26_231_precredential_admission_audit:e305c7630802ca725b6be6cbd8e05dd55ad9421788722188bdc7fa19308b8f1a` /
  `finance_v26_231_parent_attack_audit:4387ed3fbef09365d181bbe7d19028bcc2fba251f3e3666a1892ac4916a78a24`;
- implementation / scope / Gate:
  `fresh_v26_231_recovery_online_authorization_implementation_binding:1cb9a095e27da79f3d812f8bd2a036a3a6ff928033510f38751b7d338501da98` /
  `finance_v26_231_scope_boundary_audit:2928966adc1283895338a9a2062819e18946e8ea7b0b99afe71f568a36bc96a6` /
  `finance_v26_231_gate_evaluation:713932e60414c905a5e602013372d13522d9b90ed76431ddbec452e0d7e03527`;
- Decision / Transition / Report:
  `finance_v26_231_online_authorization_decision:9be1b0912f6bb4f6d5cfee7af5d4185d593ae54e482edd7517e3e6d0e48c47d3` /
  `finance_v26_231_transition:bfd9754ad862373eaf427f445e3e8760920a506cd60b6df399abdecef4ff64da` /
  `finance_v26_231_online_authorization_report:09e2894fbc945ccb28d53f1e60ba84769ed60fad75b59f562f8fadbe56aa48ed`;
- Artifact Manifest / Root:
  `finance_v26_231_artifact_manifest:92c0f3baaeaeb278e9037ebf4dd85c3e86b760bd1d624681379857700f134308` /
  `finance_v26_231_artifact_root:a9d1d137adcdb3552fcfc5eaf8c979a6f0ab2906b7165a690144c53adb1c24d1`.

## Source And Reproducibility

The exact source freeze is:

```text
commit  d74406041cabb1ea61df22b99f8a96affdae2ea0
tree    3cdbb7cbdbc79ec01726ba262b8833d4e013d058
```

The two source members contain 73,536 bytes and both committed/current byte checks pass. The
formal directory contains 18 files and 103,759 bytes. Its self-excluding Manifest binds seventeen
members and 100,870 bytes. A complete second build produces exact path and actual-byte equality.
Focused tests pass 9/9. The adjacent v26.226-v26.231 partition passes 69/69. Focused PyCompile,
Ruff check/format, and no-import-follow Mypy pass; package-wide Ruff passes.

## Transition And Prohibitions

The fresh authorization exists but remains unconsumed. The only permitted successor is:

```text
fresh_exact_v209_unbound_provider_failure_recovery_population_bound_
online_execution_only
```

That successor must present the exact v26.231 authorization bytes, pass the precredential Guard,
consume it exactly once, durably persist the consumption Receipt and Recovery Run Start Receipt,
and only then cross the credential boundary. It may execute only the exact 33 Recovery Jobs under
the frozen continuation semantics and residual limits. The 55 historical successful calls must
remain local replay inputs and cannot be reissued.

A larger `max_tokens`, a different model or request body, request-only retry semantics, an added
Recovery Job, a replacement 192-Job run, or a second recovery attempt requires a new condition
and is not covered. Historical v26.226 mutation or terminal backfill, empirical estimation before
an independent postrun audit, QA, Mapper, State, frequency, Contribution, VTDO, training, release,
and production remain forbidden.
