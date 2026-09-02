# Finance v26.207 Fresh Repaired Full-Condition Preflight Independent Audit

Audit date: 2026-09-02

## Decision

Finance v26.207 consumed only
`fresh_repaired_action_interface_full_condition_integration_preflight_independent_audit_only`.
The exact external review is 12,167 bytes with SHA-256
`c305d4092220fd02344051690445f885ae3139c25134d61be1513cfeb826677f`.
It accepted v26.206 at its stated scope, required an independent zero-Provider audit, identified
source-level repair/request/validation/transport no-bypass closure as the primary audit object,
and did not authorize an online-execution authorization or the 192-Job Provider run.

The noncompensatory result is:

```text
A0 exact authority and v26.206 freeze                              PASS
A1 detached exact-source and 17-file byte rebuild                 PASS
A2 independent fresh Package/Job/Manifest/Runner reconstruction   PASS
A3 future repair -> request -> validation -> transport no-bypass  FAIL
A4 independent 192-Job Runtime replay and five failure controls   PASS
A5 estimand/resource/boundary reconstruction and zero Provider    PASS

passed / failed Gates                                             5 / 1
online-execution authorization ready                              false
```

The formal decision is:

```text
v26_206_independent_audit_failed_at_future_online_runner_
repair_request_transport_no_bypass_closure
```

This failure does not retract the v26.206 registered-callsite, deterministic Runtime, or
scripted evidence-parent results. It narrows the readiness claim: v26.206 proves the repaired
interface on its registered and scripted surface, but it does not contain an executable future
online Runner route through which every model-selected Action or Correction must pass before an
injected transport seam. The absent route cannot pass by vacuity.

## Scope And Safety Boundary

The stage performed zero credential lookups, zero Provider-client constructions, zero Stage 1
or Stage 2 Provider calls, and zero empirical Outcome or estimate materializations. It created
no online authorization. It changed no v26.206 or earlier formal artifact.

The audit used two evidence paths:

1. exact v26.206 source commit `0266bfc027ee6ef74f4d8b3a8762ebf7cdeeccb2` was
   archived into a temporary checkout and executed with a credential-free environment against
   the already validated immutable formal parent inputs;
2. a separate v26.207 implementation rebuilt the fresh parent chain and replayed the frozen
   lower-level v26.194/v26.193 Runtime surface without importing the v26.206 construction,
   callsite, scripted-integration, failure-control, or Gate helpers.

The saved v26.206 callsite Census, Integration Audit, controls, and Estimand were comparison
targets only after the independent objects had been built. The saved v26.206 authorization and
predecessor Freeze identities remain required declared roots of the exact v26.206 identity chain;
the derived repair Profile, Package Catalog, Manifest, Runner, and Execution Contract were
rematerialized from those roots and the frozen v26.194/v26.203 sources.

## A0: Exact Authority And Predecessor Freeze

The audit admitted the exact external bytes before output creation. It then validated the
self-excluding v26.206 Manifest and every member. The exact formal geometry is:

```text
v26.206 formal files / total bytes                 17 / 2,519,097
Manifest members / member bytes                    16 / 2,516,326
path / SHA-256 / byte-count matches                16 / 16 / 16
historical mutations / Provider calls / credentials        0 / 0 / 0
```

The v26.206 Report, Transition, Gate, Census, Integration, Manifest, Runner, Execution Contract,
Estimand Contract, Artifact Manifest, Artifact Root, source commit, and source tree all match the
frozen identities.

## A1: Detached Exact-Source Rebuild

The audit obtained v26.206 code through `git archive` of exact commit
`0266bfc027ee6ef74f4d8b3a8762ebf7cdeeccb2`; its tree independently resolves to
`98afacbad5b4af207dc00d851a9937d81ce0b9f5`. The source snapshot was placed first on
`PYTHONPATH`. API- and credential-like environment inputs were omitted. Because the source
commit intentionally precedes the later formal-artifact commit, the snapshot code read the
already validated immutable formal parent tree rather than falsely claiming that those later
artifacts were members of the source commit.

The detached execution rebuilt all 17 v26.206 output paths. Path, SHA-256, byte-count, and actual
byte equality are each 17/17, with 2,519,097 rebuilt bytes. The v26.206 Report, Census,
Integration, and Gate were not used as outcome oracles for the separate A2/A4 reconstruction.

## A2: Independent Fresh Identity Reconstruction

Starting from the frozen v26.194 Package Catalog and Manifest, the v26.203 exact four-field
Action Contract, and the v26.206 declared authorization/freeze roots, the audit rematerialized:

```text
source / rebuilt Packages                              32 / 32
source / rebuilt Jobs                                192 / 192
Package canonical/object matches                       32 / 32
Job canonical/object matches                         192 / 192
Package x Replica cells                                    192
unique Raw/Result/Trace/Outcome namespaces                 768
predecessor/fresh identity collisions                         0
```

The independently reconstructed Repair Profile, Package Catalog, Manifest, Runner, and Execution
Contract exactly match their saved v26.206 objects. No source Task, Component, Candidate,
Schedule, presentation, model, Thinking, Grammar, Policy, resource, correction bound, validity,
denominator, or threshold was changed.

## A3: Source-Level No-Bypass Audit

Direct AST inspection of the exact v26.206 source confirms the registered surface:

```text
repaired-message compiler definitions                          1
callsite builder definitions                                   1
scripted-integration definitions                               1
compiler calls inside callsite builder                         1
request-builder calls inside callsite builder                  1
callsite-builder calls inside scripted integration             3
registered Action/Correction callsites repaired          600 / 600
old response_abi / unrepaired registered routes              0 / 0
direct Provider constructors / requests                      0 / 0
```

That evidence is sufficient for the exact registered callsite surface, but the stronger future
route required by the external review is absent:

```text
executable future online Runner definitions                    0
injected transport-seam definitions                            0
Action transport dispatch calls                                0
Correction transport dispatch calls                            0
future model-selected accepted-prefix route materialized   false
future online no-bypass proved                             false
```

The first unclosed seam is
`executable_future_runner_repair_request_validation_transport_route_absent`. The data-only
`RepairedRunnerContract` and the scripted `_callsite_row` path are not treated as an executable
online route. The audit does not claim enumeration of all model-reachable future States.

## A4: Independent Callsite And Runtime Replay

The independent implementation replayed the actual frozen step Runtime for all 192 Jobs. For
each reached State, it rebuilt the public Prompt core, independently compiled the exact repair
messages, built the canonical request body, parsed the four-field reference Action, verified the
current State and ordered Candidate set, executed production `step()`, exercised every registered
typed-rejection Correction branch, and crossed the frozen Final parser and independent validity
reports.

The exact reconstructed callsite surface is:

```text
Jobs / callsites                                      192 / 792
first / subsequent Action                             192 / 288
typed-rejection Correction                                  120
Final                                                        192
four-field Action compilations                               600
saved row / Prompt / Request matches                 792 / 792 / 792
maximum message / request bytes                  34,404 / 34,565
Parser relaxation / historical adaptation                   0 / 0
```

All 792 rebuilt v26.206 callsite objects and the rebuilt v26.206 Census match their saved targets.
The independent trajectory result is:

```text
first / subsequent Action parses                     192 / 288
typed rejection / Correction parses                  120 / 120
Final parses / terminal States                       192 / 192
independent validity / scripted Qualified            192 / 192
unique Raw/Result/Trace/Outcome identities                  768
saved Integration row matches                              192
exception escapes / empirical rows                         0 / 0
```

Correction counts are zero for 144 Jobs and one, two, three, or four for twelve Jobs each. The
independently rebuilt v26.206 Integration object matches its saved target exactly. These remain
deterministic reference controls, not model outcomes or Capability measurements.

Five independently executed controls cover invalid first Action ABI, ABI-valid unknown first
Action reference, invalid Correction ABI, invalid Final ABI, and one typed outer
`instrument_failure`. Each projects one typed Outcome, invokes no task Verifier, escapes no
exception, and matches its saved v26.206 control object.

## A5: Estimand, Resource, And Boundary Reconstruction

The prospective denominator remains all 192 frozen Jobs. Pre-Action-ABI and outer terminals
remain in both denominators as failures. Post-ABI conditional quantities remain null if their
denominator is zero. Numerators, estimates, intervals, and empirical rows remain unmaterialized.

The resource limits remain 21 Primary requests, 23 Provider calls, 24 transport-inclusive
invocations, 1,120,000 rollout tokens, and 60,000 Prompt bytes. The observed registered maxima
are 34,404 message bytes and 34,565 request bytes; resource-bound violations are zero. Provider,
credential, QA, Mapper, State, frequency, Contribution, and VTDO counts are all zero.

## Authoritative Identities

- external authorization:
  `finance_v26_207_external_independent_audit_authorization:15223184655ff83ddf22113840d65014ca192c24304a880f2ac9945456a11cb6`;
- v26.206 Freeze:
  `finance_v26_207_v206_preflight_freeze:a4d3115d52e369c1cca5ae29cf0ab1381f445ee63c4fa578730d46bbee45b842`;
- detached rebuild Audit:
  `finance_v26_207_detached_source_rebuild_audit:d5d0a087250bfe6801d7b641ee2cb938d4671776e71b42715f135f558bdcb72b`;
- independent parent Audit:
  `finance_v26_207_independent_parent_reconstruction_audit:9cca53c6173b35a7e5c44608011539655fdb8e956ce0f75142e2250f2ea74843`;
- source-route Audit:
  `finance_v26_207_source_route_no_bypass_audit:90fc22e5de8b7a2891825118661722ea59314a1accc50456de72bca747941fb9`;
- independent callsite Audit:
  `finance_v26_207_independent_callsite_reconstruction_audit:13ec8427b740fd914aacd1dd4bacb2fc46d1c48285a063d2d10aa88d07c3a117`;
- independent replay Audit:
  `finance_v26_207_independent_scripted_replay_audit:929e452b394d32a9f55cb7b08d94928db527ab46d56210cdfa4602c75e36f346`;
- independent failure-control Audit:
  `finance_v26_207_independent_failure_control_audit:de48841d6d1441eaab5db56af0d4add726175bdde41377a4f2370312826c4233`;
- Estimand/resource/boundary Audit:
  `finance_v26_207_estimand_resource_boundary_audit:ea298860cac7d351a73f59dd26621eb973f886212f4e51bd0b5f87ec74a302a0`;
- Gate Evaluation:
  `finance_v26_207_independent_audit_gate_evaluation:b4fa5df9edec6f78cda157a649ee043061bddb768e1149ccf7136a4bd66e56be`;
- Decision:
  `finance_v26_207_independent_audit_decision:a7340af66bc8112279aebc9224ea4700b41baf487e77085ed849f6325f7bcd66`;
- blocked Transition:
  `finance_v26_207_blocked_transition:4d6e10651925e53244e1616ac9146cf65877d2ef60a8cf2c5c84e49847c64997`;
- report:
  `finance_v26_207_independent_audit_report:563d89073ade0c7c98fee102141f6b0911b7e06b6b0598d0b43c72bf29e016c8`;
- Artifact Manifest:
  `finance_v26_207_artifact_manifest:19c802962e371cce2429fa853010589afeca42ab5da36520460d006fdd866fc0`;
- Artifact Root:
  `finance_v26_207_artifact_root:0d16fac465fea91dfed9f38e34b10894c0b99b2d5e4ca34231645d02e4e023fb`.

The exact audit source commit/tree are
`304d4a6f42b22524a34e76eda55c23235937acdb` /
`40e503fc402d337b48038d65bf22ffd90b00ed21`. The formal directory contains 16 files and
1,408,911 bytes; its self-excluding Manifest binds fifteen members and 1,406,276 bytes.

Focused v26.207 tests pass 8/8, including two complete builds with byte-identical 16-file output.
The adjacent v26.203-v26.207 suite passes 40/40. Focused PyCompile, Ruff check/format, and
no-import-follow Mypy pass; package-wide Ruff passes.

## Transition

The current status is `BLOCKED_FAILED_INDEPENDENT_AUDIT`. `next_stage` is null. A possible repair
scope is named, but explicitly not authorized:

```text
fresh_repaired_full_condition_executable_runner_route_closure_preflight_only
```

Any such successor requires a new external audit decision. Online-execution authorization, the
full repaired 192-Job Provider run, interface-factor decomposition, Parser relaxation, historical
adaptation, source/Task/Component/Candidate/Schedule/presentation/Runtime/model/Thinking/Grammar/
Policy/resource/correction-bound/validity/denominator/threshold change, QA, Mapper, State
frequency, Contribution, VTDO, training, release, and production remain forbidden.
