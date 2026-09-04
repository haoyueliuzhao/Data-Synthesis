# Finance v26.232 Fresh Exact v26.209 Recovery Online Authorization Predecessor Manifest Actual-Byte Authority Repair

## Scope And Decision

Finance v26.232 consumes only
`fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_authorization_predecessor_manifest_actual_byte_authority_repair_only`.
The exact 10,544-byte external review is bound at SHA-256
`04a5e36142abc3ecde5706c19f9277ee1315beb6f2b5e023863aad0ab963b5bc`. It classifies
v26.231 as `FAIL_NARROWLY_AT_G0`, identifies
`PREDECESSOR_SELF_EXCLUDING_MANIFEST_ACTUAL_BYTE_AUTHORITY_NOT_CLOSED` as the sole blocking
defect, retains the Recovery Population authority, and authorizes only this zero-Provider narrow
repair. The exact 24-byte operator directive `参照审计修订问题`, SHA-256
`a5eccdee792d12977caf76a67107c721878efb7ae02598d987e2e86b83fcc0d8`, consumes only that
stage.

The repaired decision is:

```text
fresh_exact_v209_recovery_online_authorization_predecessor_manifest_actual_
byte_authority_repaired_new_authorization_issued_not_consumed
```

One new manifest-byte-bound authorization is issued and zero authorizations are consumed. The old
v26.231 authorization remains immutable but is explicitly non-consumable and non-reusable. This
stage performs no Provider call, credential lookup, client construction, Recovery execution,
Consumption Receipt, Run Start Receipt, empirical projection, or historical v26.226 write.

## Immutable v26.231 Scope Correction

The v26.231 formal directory remains unchanged. Its local Recovery Population, continuation
semantics, explicit budget, authorization construction, admission controls, and parent attacks are
retained at their scoped meanings. Its historical 8/0 Gate and Transition are immutable records,
but their exact predecessor-byte and online-consumability interpretations are superseded by the
external review.

The current scoped v26.231 decision is:

```text
v26_231_constructed_a_33_job_recovery_authorization_candidate_with_retained_
semantics_and_budget_but_did_not_bind_the_actual_bytes_of_the_v26_229_and_
v26_230_self_excluding_manifests_so_the_authorization_is_not_consumable
```

Before any repaired object is created, v26.232 binds the complete v26.231 directory, including
the v26.231 Manifest's own actual bytes:

```text
v26.231 files / bytes                18 / 103,759
v26.231 Manifest members / bytes     17 / 100,870
v26.231 Manifest bytes                     2,889
v26.231 Manifest SHA-256  147ac88a48a5f04321cd242fd5031d0e334abccb502eccf02cbc64fa1730039f
formal bytes modified                            0
old authorization consumable                 false
```

The v26.231 actual-byte authority and candidate Freeze identities are:

- `finance_v26_232_predecessor_manifest_actual_byte_authority:f5a7b65649499b13fb83f79a7eab789c42196cd535fb9099faf4a74c88ff864a`;
- `finance_v26_232_v231_candidate_freeze:213527a1e9e8beb79e8d3ec14e20f1b2b9e67092e07f317acb4aa115a048dc1b`.

The superseded authorization remains
`fresh_v26_231_exact_recovery_online_execution_authorization:d54c68b13db02db4582f7e587973b61af431efa714f1ba3d6473939f4b12c06d`.
It is a historical locally constructed candidate only and cannot be presented to the repaired
Guard.

## Predecessor Manifest Actual-Byte Authority

The repaired verifier reads `artifact_manifest.json` as raw bytes and checks its expected byte
count and SHA-256 before Pydantic or JSON parsing. Only then does it parse the Manifest, derive the
exact expected path set, and hash every self-excluding member.

```text
raw Manifest bytes -> exact byte-count and SHA-256 guard
  -> typed Manifest parse -> exact path-set equality
  -> every member byte-count and SHA-256
  -> directory file-count and total-byte equality
```

The exact predecessor authorities are:

| Predecessor | Manifest bytes | Manifest SHA-256 | Formal files / bytes | Members / bytes |
| --- | ---: | --- | ---: | ---: |
| v26.229 | 16,952 | `3c74bf72426c33400338e9f234a82bc342f368910a40c84d360ac3bd61b8fa72` | 117 / 1,105,367 | 116 / 1,088,415 |
| v26.230 | 3,150 | `70ad2b0afa9fac2917512e4e2d7d85cf2f42abb99e8a6a058b751f627f8605b1` | 20 / 308,132 | 19 / 304,982 |

Their new authority identities are:

- v26.229:
  `finance_v26_232_predecessor_manifest_actual_byte_authority:3a3bcbdd61196d96aea85d82a89c0cca9b6242fa7c23a7651441f73111cd65ca`;
- v26.230:
  `finance_v26_232_predecessor_manifest_actual_byte_authority:874d1c41abed1d3b0ef90534ae9d73ac101f4688a8ffd6d092081a9bafbb054c`.

The new v26.230 Freeze embeds the exact v26.230 Manifest byte count, digest, and authority parent,
while preserving every prior semantic Freeze field. Its identity is
`finance_v26_232_v230_manifest_actual_byte_freeze:cf68dcf90ee073ac7bf130a1d3306c3be1d7ef6c03c9497df01b2322d7d1ec06`.

## Same-Length Semantic-Equivalent Attacks

Two direct controls rotate the top-level JSON key order while retaining the complete parsed JSON
object and exact byte count. Neither attack writes to a predecessor directory.

```text
v26_230_manifest_same_length_key_reordering
  original / candidate bytes             3,150 / 3,150
  parsed JSON equal                                true
  original SHA-256  70ad2b0afa9fac2917512e4e2d7d85cf2f42abb99e8a6a058b751f627f8605b1
  candidate SHA-256 e4dfa25c9f394caf54e250a4cf1b8b3bede95306cff614b3ae03a3604b27d4ce

v26_229_manifest_same_length_key_reordering
  original / candidate bytes           16,952 / 16,952
  parsed JSON equal                                true
  original SHA-256  3c74bf72426c33400338e9f234a82bc342f368910a40c84d360ac3bd61b8fa72
  candidate SHA-256 1b941395b02d0811c8dcc2ea58116189bc3272b0304652315bbfd3f1c19522c1
```

Both candidates reject at `freeze.manifest_bytes` through caught `V232Error` objects. Equal byte
count, semantic JSON equality, unchanged member bytes, and unchanged parsed Manifest identity do
not substitute for exact Manifest file bytes.

```text
attacks / rejected / accepted      2 / 2 / 0
same-length candidates             2 / 2
parsed-JSON-equal candidates       2 / 2
attack writes / Provider calls     0 / 0
```

The attack row identities are:

- `finance_v26_232_manifest_byte_attack:9ab4ffc59d7aef60f4f59fc22c5b7f4594b585c35faa27d8bf808252f0a105d4`;
- `finance_v26_232_manifest_byte_attack:d8d1f5aa0cdbfc6eb42fb810ea84e7e63c8ec112e8efdb8c618ecc72f997f1ef`.

The aggregate Audit is
`finance_v26_232_manifest_byte_negative_control_audit:bb6b35f3fd900698cc24b5e68fb4116a2cc091d08acf959fb467f949fb6f32a7`.

## Retained Recovery Parent And Population

Only after both predecessor raw-byte authorities pass does v26.232 invoke the retained v26.231
semantic reconstruction. It independently rereads and compares all 33 saved Recovery Candidates,
33 Recovery Jobs, 33 source rows, 33 failed-request hashes, and all 55 historical successful
calls. The reconstructed retained v26.231 parent bytes match the saved v26.231 parent before the
fresh manifest-byte parents are added.

```text
Recovery Candidates / Jobs                         33 / 33
candidate / Job actual-byte matches                 33 / 33
historical successful-prefix calls                       55
captured failed requests                                 33
failed phase partition                         3 / 25 / 5
reasoning-budget / JSON-decode sources              31 / 2
historical Job / Recovery Job identity overlap           0
successful-prefix Provider reissues                      0
```

The retained set hashes remain:

```text
Candidate set      73cddb87872b77a3de0560f0dcd48da1cb073f87bc75bf16307dc351684d3ee6
Recovery Job set   e1a0ad2cddbb48e857cef232b11396161aa64636f44fd91bcd15915de37fb50d
source-row set     a13990b79d71db1fbbd454d5b5d846d9013a18b48b74c312a0da9b7a6ee52691
failed-request set eb4fd00e9a029d9f19b0017c611ac420769925353619af655d617ee00cb3be68
```

The repaired Parent Binding is
`fresh_v26_232_exact_manifest_byte_bound_recovery_parent_binding:30d8ae09d56969bbf76274c78b313642d022a9622316b8cf770156c042eb4069`.

## Retained Execution Semantics And Budget

The v26.231 Contract projection is loaded from its immutable artifact, validates under its exact
historical schema, and is then rebound to the repaired Parent. No execution field changes.

```text
model                              deepseek-v4-flash
thinking.type                      enabled
response_format.type               json_object
max_tokens                         16,384
maximum online Primary requests       638
maximum online Provider calls         704
maximum transport invocations         737
maximum online rollout tokens  36,294,402
```

The retained execution order remains:

```text
exact fresh authorization bytes -> precredential parent/scope/budget Guard
  -> consume exactly once -> durable Consumption Receipt
  -> durable Recovery Run Start Receipt -> credential lookup
  -> local replay of 55 persisted public projections
  -> exact captured failed request once per Recovery Job
  -> exact v26.209 current-State Runner continues to a fresh terminal
  -> fresh recovery evidence -> Raw -> Result -> Trace -> Outcome -> checkpoint
```

The fresh Contract and Composition are:

- `fresh_v26_232_manifest_byte_bound_recovery_execution_contract:256c76f87d70a2bc7c541cc8b307f0c6ab8dde8c3f9bbd01962ed5e0348b45ad`;
- `fresh_v26_232_manifest_byte_bound_recovery_online_execution_composition:4f183c6189583f26bfd41ac6cbe04d2c0c8f30d6e72d7dbd6a597c8d0df92e0c`.

The values above are worst-case ceilings, not expected usage or empirical results. A repeated
Provider failure cannot create an ad hoc retry or replacement run.

## Fresh Authorization And Precredential Guard

The new authorization is
`fresh_v26_232_exact_manifest_byte_bound_recovery_online_execution_authorization:c332e42c45bbd718a16ba65258099c9193cb84348b83f94960d3bf4bd015e371`.
It binds the external narrow-repair decision, v26.231 candidate Freeze, v26.229 and v26.230
Manifest actual-byte authorities, repaired v26.230 Freeze, complete Recovery parent, unchanged
execution Contract and Composition, and the exact 33-Job set.

It authorizes at most one future consumption for exactly
`fresh_exact_v209_unbound_provider_failure_recovery_population_bound_online_execution_only`.
No consumption occurs in v26.232.

One diagnostic request passes without consumption. Nineteen invalid controls reject before any
post-Guard probe, including direct presentation of the old v26.231 authorization. Ten fully
rehashed parent or Job-member candidates also reject at the exact-byte Guard.

```text
legal / invalid controls                   1 / 19
fully rehashed attacks / rejected          10 / 10
accepted parent attacks                          0
authorization consumptions                       0
Consumption / Run Start Receipts              0 / 0
credential lookups / Provider calls           0 / 0
```

The admission and parent-attack Audits are:

- `finance_v26_232_precredential_admission_audit:2a9b315b67f66ca5225ba8facfd15f7a9efbad067a9af257bb39816d9375b9a3`;
- `finance_v26_232_parent_attack_audit:2dd783c755e2ac87141ba421c8195dcaf4a69fe6f16946813935371d1b97da00`.

## Noncompensatory Gates

```text
G0 external scope, v26.231 candidate, exact v26.230 Manifest Freeze  PASS
G1 exact v26.229 Manifest, Contract, Population, and 33 Jobs         PASS
G2 exact 55-prefix and 33 failed-request authority                   PASS
G3 continue-from-failure-to-terminal semantics                      PASS
G4 explicit residual resource and call budget                       PASS
G5 fresh Manifest-byte-bound one-time authorization                 PASS
G6 precredential, parent, and Manifest-byte attacks                 PASS
G7 zero-Provider/recovery/empirical boundary                        PASS
passed / failed                                                      8 / 0
```

No Gate compensates for another. A changed Manifest byte, equal-length reordered Manifest,
member mismatch, changed parent or Job, old authorization, Recovery Population change, budget or
continuation change, accepted attack, credential access, Provider call, Recovery execution, or
historical mutation prevents the passing Decision. The Gate is
`finance_v26_232_gate_evaluation:16ac15c6ce15aa20471ab808e3ed086cd8a4bc2bc4bb2286c102609476c9b9bc`.

## Authoritative Identities

Principal v26.232 identities include:

- external decision / v26.231 candidate Freeze:
  `finance_v26_232_external_manifest_byte_repair_decision:3536db07cc0e7f6c878b747f3946c0d45fbb3bd9830412c1b1042db099faf8e3` /
  `finance_v26_232_v231_candidate_freeze:213527a1e9e8beb79e8d3ec14e20f1b2b9e67092e07f317acb4aa115a048dc1b`;
- v26.229 / v26.230 Manifest authorities:
  `finance_v26_232_predecessor_manifest_actual_byte_authority:3a3bcbdd61196d96aea85d82a89c0cca9b6242fa7c23a7651441f73111cd65ca` /
  `finance_v26_232_predecessor_manifest_actual_byte_authority:874d1c41abed1d3b0ef90534ae9d73ac101f4688a8ffd6d092081a9bafbb054c`;
- repaired Freeze / parent / Contract / Composition:
  `finance_v26_232_v230_manifest_actual_byte_freeze:cf68dcf90ee073ac7bf130a1d3306c3be1d7ef6c03c9497df01b2322d7d1ec06` /
  `fresh_v26_232_exact_manifest_byte_bound_recovery_parent_binding:30d8ae09d56969bbf76274c78b313642d022a9622316b8cf770156c042eb4069` /
  `fresh_v26_232_manifest_byte_bound_recovery_execution_contract:256c76f87d70a2bc7c541cc8b307f0c6ab8dde8c3f9bbd01962ed5e0348b45ad` /
  `fresh_v26_232_manifest_byte_bound_recovery_online_execution_composition:4f183c6189583f26bfd41ac6cbe04d2c0c8f30d6e72d7dbd6a597c8d0df92e0c`;
- authorization / manifest attack / scope:
  `fresh_v26_232_exact_manifest_byte_bound_recovery_online_execution_authorization:c332e42c45bbd718a16ba65258099c9193cb84348b83f94960d3bf4bd015e371` /
  `finance_v26_232_manifest_byte_negative_control_audit:bb6b35f3fd900698cc24b5e68fb4116a2cc091d08acf959fb467f949fb6f32a7` /
  `finance_v26_232_scope_boundary_audit:c229e2e85ba389abee4efc1fdd5677cbbb6393c1a1f8859c95ef69024b44274d`;
- Gate / Decision / Transition:
  `finance_v26_232_gate_evaluation:16ac15c6ce15aa20471ab808e3ed086cd8a4bc2bc4bb2286c102609476c9b9bc` /
  `finance_v26_232_online_authorization_decision:26719b53de105c05de9624becd060ccec06a74930ec53135d6d2533a20133b66` /
  `finance_v26_232_transition:125313bc1aeeac08f0b0675c9cb9d0f6aac7851893858c8fc645eb6ad7ed1014`;
- Report / Manifest / Root:
  `finance_v26_232_manifest_byte_repair_report:ff17a8bbca96517f9e6ae9a1865361a7edafa28f10b55f0a13b00e5f2e8a2935` /
  `finance_v26_232_artifact_manifest:f0c46ed0882f33033496f0dbb542e304167ca767ed3290bc25142a8b4228b02e` /
  `finance_v26_232_artifact_root:7f49da2bf737dcb50ca975780301647c6128a62248622d63109b6c363c343cf8`.

## Source And Reproducibility

The source identity binds both new repair files and the two retained v26.231 implementation files:

```text
source commit  5de7ba42d254cfba2c7c422371668391672b2a52
source tree    5087ecaf2e47b262eec4fab79746ecf8d12aaf5a
source members / bytes                         4 / 145,364
committed/current actual-byte matches                4 / 4
member-set SHA-256  fb80088dfcbef7140acfcfd89643f7b6c9ceca218de12ddb2e608526a9af20f2
```

The formal directory contains 23 files and 115,377 bytes. Its self-excluding Manifest binds 22
members and 111,695 bytes. The Manifest itself is 3,682 bytes at SHA-256
`2dcd59f100cb31d973c87248d5ac198a0f257cf62759b5d7a2be8efeea25dc2c`.
A complete second build into an empty directory reproduces every path and actual byte.

Focused tests pass 9/9. The adjacent v26.226-v26.232 suite passes 87/87. Focused PyCompile, Ruff
check/format, no-import-follow Mypy, and package-wide Ruff pass.

## Transition And Prohibitions

The new authorization exists and remains unconsumed. The only permitted successor is:

```text
fresh_exact_v209_unbound_provider_failure_recovery_population_bound_
online_execution_only
```

That successor must present the exact v26.232 authorization bytes, pass the repaired
precredential Guard, consume it exactly once, persist a durable Consumption Receipt and Recovery
Run Start Receipt, and only then cross the credential boundary. The v26.231 authorization cannot
be substituted or consumed.

Recovery Population change, historical successful-prefix Provider reissue, failed-request body or
`max_tokens` change, replacement run, additional Recovery Job, historical v26.226 mutation or
terminal backfill, empirical estimation before an independent postrun audit, QA, Mapper, State,
frequency, Contribution, VTDO, training, release, and production remain forbidden.
