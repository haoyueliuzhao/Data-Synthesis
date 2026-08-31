# Finance v26.192 JSON-explicit Prompt Contract And Development Population Preflight

Audit date: 2026-08-31

## Decision

Finance v26.192 consumes only:

```text
fresh_identity_json_explicit_prompt_contract_and_development_population_preflight_only
```

The external v26.191 audit passes the six-request online diagnosis, preserves every v26.191
Observation, and authorizes only a credential-free repair preflight. v26.192 adds one shared
Provider-facing output-protocol envelope, materializes fresh identities, and exercises a scripted
Runner. It performs no Provider call and creates no Development model outcome.

The exact result is:

```text
JSON-explicit Prompt Contract                         PASS
fresh Runner Packages / Development Jobs          32 / 192
formal reachable Prompt Census                         792
scripted Qualified Jobs                           192 / 192
Provider / Stage 2 Provider calls                      0 / 0
online Development execution authorized               false
```

All twenty noncompensatory Gates pass. This is static identity, Prompt-contract, and local Runtime
evidence, not an online model result or a Capability estimate.

## Bound authorization and immutable predecessor

The exact external review contains 12,464 bytes at SHA-256
`18ddfcb62a8401397204a46f997ca85c738701b41c3c0cfa790f79fac6df4ccf`. The operator decision
`参照审计报告修订` selects only its unique credential-free successor.

The build rehashes all twelve v26.191 formal files and all eleven Artifact Manifest members before
loading the frozen Runner. It validates Report
`finance_v26_191_online_diagnostic_report:4bbd4b1de318271017870147065de6415a7b7f3215bf54b58ded1ac7cde9cb26`
and Artifact Root
`finance_v26_191_online_diagnostic_artifact_root:47ce56c1e3ada224121b334c19fee66b485920de3bce132e0d4fea4b49672004`.
No v26.191 Observation, v26.188 Job, or historical Outcome changes.

The predecessor Freeze is
`finance_v26_192_predecessor_freeze:5d6da75a639ea179bef43fd8d2de06d89cede3bddc694a52e72072b698f4c33f`.

## Shared JSON-explicit protocol

The new shared instruction is exactly:

```text
Return exactly one valid JSON object matching the response ABI.
Do not return Markdown or surrounding prose.
```

It is stored under one Provider-facing protocol object alongside:

```json
{"response_format":{"type":"json_object"}}
```

The finance task instruction, public State, Candidate encoding and order, response ABI, Component
Schedule, Action Grammar, Final Grammar, model, Thinking policy, bounded generation policy,
resource Contract, answer, Evidence, and Validity semantics are not edited. Every rendered Prompt
has three canonical top-level fields:

```text
prompt_core
prompt_kind
provider_output_protocol
```

For Action and Correction, `prompt_core` is byte-identical to the old
`public_prompt + response_abi` object. For Final, it is the exact old Final Prompt string, which
already contained a JSON instruction. The shared envelope therefore fixes the missing Action and
Correction requirement without rewriting task text.

Authoritative protocol identities are:

- Prompt Contract:
  `json_explicit_prompt_contract:d0094129a9f434aaa5f023d049fb9f10f300e04cc7140bf484012b41d4413afe`;
- Prompt Schema:
  `json_explicit_prompt_schema:17d41e7a1f7358bdb254fc34ce49e9638c4bdcab737af5d633474c82f0234c1b`;
- generation Profile:
  `json_explicit_generation_profile:058158afa8c23bb977cbc3b2b7c51326b271b5e32c19d1f4e39c7048ca7fa068`.

The fresh Profile preserves the exact source model-config, Thinking, Action Grammar, Final
Grammar, Policy, and resource identities. Only the Prompt Contract and Schema parents change.

## Fresh Development identity chain

The source 32 Runner Packages and 192 Jobs are used only as immutable semantic parents. v26.192
creates:

```text
32 fresh JSON-explicit Runner Package identities
  -> one fresh Runner Package Catalog
  -> 192 fresh Development Job identities
  -> 192 fresh Raw namespaces
  -> 192 fresh Result namespaces
  -> 192 fresh deterministic seed identities
  -> one fresh Development Manifest
  -> one fresh Runner Contract
```

All new identities are disjoint from their sources. Package semantic-parent hashes are recomputed
from source Runner/Execution Package, Task, group, Core, capability, depth, Component topology,
and Schedule fields. Each Job namespace is independently derived from source Job, fresh Runner
Package, fresh generation Profile, and fresh Prompt Schema. No empirical Raw or Result file is
materialized.

The authoritative identities are:

- Runner Package Catalog:
  `json_explicit_runner_package_catalog:da6102c95a1802ee55ec99d3a7a61bcb5271243fd931590f073dac314c378c26`;
- Development Manifest:
  `json_explicit_development_manifest:82ba6f1a8c3aca35ba5767c830473836e0cab638058ea3243a40cb4359a0f40b`;
- Runner Contract:
  `json_explicit_runner_contract:6e22ba95a9a00a5ba5c660534018f6ad16e7c8218cb083744d4f35154e091149`.

## Formal Prompt JSON Contract Census

The v26.191 nonblocking evidence gap is closed by the independent formal sidecar
`prompt_json_contract_census.json`. It is a 1,089,133-byte Artifact Manifest member and contains
one content-addressed row for every reachable scripted Prompt instance:

```text
first Action Prompts                         192
subsequent Action Prompts                    288
typed-rejection Correction Prompts           120
Final Prompts                                192
total                                        792
```

For every row, the Census binds fresh Job, source Job, phase, Component coordinates where
applicable, old/new Prompt SHA-256 and byte count, preserved core SHA-256, fresh Prompt identity,
and exact seven-field request-body SHA-256 and byte count.

The results are:

```text
old first Prompts containing casefold `json`       0 / 192
old first Prompts missing casefold `json`         192 / 192
new Prompts containing casefold `json`            792 / 792
exact protocol instruction present                792 / 792
`json_object` pairing                              792 / 792
Prompt core exact preservation                     792 / 792
```

The Census identity is
`prompt_json_contract_census:5b142b434c02de12d6eb7bd5a43012304f596cbbb638d7c70ce602fd5fa9017a`.
This replaces the earlier report-only 192-Prompt count with a formally bound and byte-rebuildable
sidecar; it does not alter v26.191.

## Scripted Runner preflight

Each fresh Job resolves exactly one source Job and enters the production state-bound Runtime one
current Prompt at a time. Reference execution parses the exact four-field Action ABI, commits the
selected Action, persists public Observation state locally, finalizes the actual Runtime, and
parses a model-shaped Final fixture through the exact qualified Final Grammar.

The exact local counts are:

```text
fresh/source Job resolutions                   192 / 192
primary Action Prompts / ABI parses            480 / 480
primary production step commits                480 / 480
typed-rejection Correction Prompts             120 / 120
rejection steps / correction ABI parses        120 / 120
reference correction commits                   120 / 120
Final Prompts / Final ABI parses               192 / 192
finalized Runtime Results                       192 / 192
Base / Mechanism / Qualified valid             192 / 192 / 192
Runtime exceptions                                       0
Provider calls                                            0
```

The scripted preflight identity is
`json_explicit_scripted_runner_preflight:463dee41643c408af1f77e5ab103f7cdcc77c321029a474ea9a41da8bc1dc887`.
The local Qualified values are deterministic reference controls, not model outcomes.

## Semantic preservation and pre-existing Result-ID drift

All 192 Task, execution-Package, source-artifact, Schedule, and fixed-condition parents match.
Across the 600 Action-plus-Correction Prompts, public State, Candidate order, and response ABI
cores match exactly; all 192 old Final Prompt cores match exactly. Task, Candidate, Schedule,
Grammar, and Validity change counts are zero.

The preflight also exposes a separate historical diagnostic that must not be hidden: only 144 of
192 current local reference Runtime Result IDs equal the v26.179 saved scripted Outcome parent.
The 48 differences are exactly all Semantic Reconciliation Package x Replica rows. Directly
running the unchanged frozen v26.179 `execute_trace` path produces the same 144/192 partition, so
the mismatch predates and is independent of the new JSON envelope. All 48 drift rows still pass
current Base, Mechanism, and Qualified validity.

This Result-ID comparison is therefore recorded as a class-external predecessor diagnostic, not
used as a Prompt Contract Gate, and not described as an identity-preservation pass. No historical
Result or Outcome is rewritten. The semantic preservation Audit is
`json_explicit_semantic_preservation_audit:d9c8618f78f889651ccb81b63136474e10dffe3d42dcd9484f854aee143cc308`.

## Destructive controls and Gates

Twelve controls delete or alter the JSON instruction, change response format, change Action,
Correction, or Final core, reuse the source Profile, Runner Package, Job, Raw namespace, or Result
namespace, or delete one Manifest Job. Every control executes the production Contract or fresh-
chain validator and rejects; accepted attacks are zero.

Twenty noncompensatory Gates pass. They cover exact authorization, v26.191 immutability, Prompt
Contract and Schema, fresh Profile/Package/Job/namespaces, all four Prompt phase classes, exact
response-format pairing, core preservation, the Action-to-Observation-to-Final chain, current
reference validity, destructive controls, zero Provider calls, zero historical reclassification,
and zero downstream rows. Static Audit is
`finance_v26_192_json_explicit_static_audit:9ab13d348964a175e7e1484b075d731eab0a9bf31b43cad90556a1fb85fc6bda`.

## Artifacts and quality

The exact source is commit `281abb8a2eb12434a6ade981c2a6b35b5951d98a` with Tree
`d1bf6b2f165875348e6e9bcdc54492ffa07cfc84`. The formal directory is
`artifacts/vtdo_experiment/finance_v26_192_json_explicit_prompt_contract_preflight_v1_20260831`.
It contains seventeen files: sixteen Artifact Manifest members plus the Manifest itself. The
members contain 1,643,929 bytes.

Authoritative top-level identities are:

- Report:
  `finance_v26_192_json_explicit_preflight_report:63baffe7efb1c2cab3ebd217c1ee55a67e3277cb71fb1ad8f04677bafebf4d20`;
- Artifact Root:
  `finance_v26_192_json_explicit_artifact_root:5e2970f0ec16feb9139a676e4c8277677f0fd77f259302d85a8c28629601746a`;
- Artifact Manifest:
  `finance_v26_192_json_explicit_artifact_manifest:5381b20191a2fd0801a1d5943bb96e8e0551744f7ba915aa9d3ec4b1b104b146`;
- Transition:
  `finance_v26_192_json_explicit_preflight_transition:f01022487211e680946c8f54403eb265195adc85ea6ed858e12a3104a0d2e334`.

Focused tests pass 7/7, including an empty-directory byte-identical rebuild. The v26.191-v26.192
adjacent regression passes 14/14. Focused PyCompile, Ruff check/format, no-import-follow Mypy, and
Git whitespace checks pass.

## Transition

The current decision is:

```text
no_further_experiment_authorized_without_new_audit_decision
```

The JSON-explicit repair and fresh Population now pass credential-free preflight, but this stage
does not self-authorize online execution. Repaired online Development execution, old-Job rerun,
Capability estimation, Confirmation, Mapper, State, frequency, Contribution, VTDO, Student,
training, release, and production remain forbidden.
