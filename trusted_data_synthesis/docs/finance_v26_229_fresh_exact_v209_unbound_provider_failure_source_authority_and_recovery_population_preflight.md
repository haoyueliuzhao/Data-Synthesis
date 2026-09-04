# Finance v26.229 Fresh Exact v26.209 Unbound Provider-Failure Source Authority And Recovery-Population Preflight

## Scope And Decision

Finance v26.229 consumes only
`fresh_exact_v209_unbound_provider_failure_source_authority_and_recovery_population_preflight_only`.
The exact 10,739-byte external review is bound at SHA-256
`0b63d855ddd8e8707f3c0bdc2ddd4231b6a16fdaa986f7acb8e092f1491b58c2`. It classifies
v26.228 as `PASS_AS_SCOPED`, reports `BLOCKING_DEFECT=NONE_FOUND` and
`MANDATORY_REVISION=NONE`, and authorizes only this credential-free source-authority and fresh
Recovery-Population preflight. The exact 24-byte operator directive `参照审计继续实验`, SHA-256
`b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb`, is admitted only
for that scope.

The resulting decision is:

```text
v26_226_exact_33_unbound_provider_failure_source_authority_and_fresh_
recovery_population_preflight_passed
```

The stage creates exactly 33 fresh, nonexecuted Recovery Jobs from the exact 33 unresolved
v26.226 Provider-failure rows. It makes zero Provider calls, performs zero credential lookups,
executes zero recovery or failed-Job reruns, creates zero empirical rows or online
authorizations, and changes no v26.226 byte or historical terminal. The v26.226 execution remains
`incomplete`: 156 complete Jobs plus 36 failure records.

This result is source-authority and future-Population constructibility evidence. It is not a
recovery result, a successful model outcome, a terminal backfill, an empirical estimate, or an
authorization to execute any Recovery Job.

## Exact v26.228 And v26.226 Freeze

Before selecting a source row, v26.229 validates the complete v26.228 directory and its
self-excluding Manifest:

```text
v26.228 source commit           e73ced617283eb69ea0c2a768368554959a5abc3
v26.228 source tree             a0bba2a647f60cb0bfbcbcc4c28a25150a80863b
saved files / bytes             17 / 45,679
Manifest members / bytes        16 / 42,978
Manifest file bytes / SHA-256   2,701 /
  42b3ded8192a175bc6a69636cc3a798073d0cc25a8785e540b903bbbc26501ae
Manifest                        finance_v26_228_artifact_manifest:
  7514b10d627fb19d3d42f1ad8f5e74e12bf0a152265d42742ab2b1b4e1391eaa
Root                            finance_v26_228_artifact_root:
  92ed34f45846d1ba8e93cf5dd2e9d972f3f97bdbc69eb110135d8976e1d68aaf
```

The exact v26.228 Decision and Transition are bound without changing their bytes. Its
`next_stage_authorized=false` records the state before this external review; the new review
authorizes only v26.229 and does not retroactively modify v26.228.

The stage then validates all 3,428 files and 99,765,014 bytes of v26.226, including every one of
the 3,427 Manifest members over 99,047,004 bytes. It requires the exact Manifest, Root, Summary,
Transition, Provider-intent Census, and unchanged partition:

```text
exact Jobs / complete Jobs       192 / 156
failure records                   36
Host / unbound Provider failures   3 / 33
historical execution status       incomplete
historical mutations / backfills  0 / 0
```

The v26.226 Manifest and Root remain
`finance_v26_226_artifact_manifest:19cef807ae34c71c13d526c09c385163d1b30b2ced05322e3ec7e6f0e803d217`
and
`finance_v26_226_artifact_root:7ac11713bf70dbd57297b6d87db0e6982ce5ad8222849e3a4826020904f95280`.

## Exact 33-Row Source Authority

The selector starts from the actual v26.226 Summary and reparses every actual failure file. It
does not use the v26.228 exclusion list as a selector. Rows are admitted only when the persisted
failure kind is exactly `unbound_provider_failure`; the independently derived projection is then
compared with v26.228.

The exact source ordinals are:

```text
9, 10, 16, 21, 32, 58, 62, 63, 72, 78, 79,
92, 102, 103, 106, 110, 112, 114, 116, 121, 127,
129, 130, 131, 132, 135, 136, 139, 144, 147, 155, 171, 180
```

The actual source projection matches
`d9243f618f547da83cae5e6698d3155030b3065058cf5372b8171bf013d3d3f0`.
The three Host ordinals 6, 22, and 149 remain excluded. For every admitted row the authority
binds its exact path, file hash and byte count, canonical record hash, record and Job identities,
ordinal, outer failure digest, Run Start Receipt, authorization, and complete ordered Provider
call prefix. All 33 historical rows retain `terminal_evidence_admitted=false`,
`five_layer_evidence_admitted=false`, and `recovery_attempted=false`.

The complete selected evidence subset contains:

```text
failure files                                            33
Provider descriptors                                     88
request metadata                                         88
response metadata for successful prefix                  55
error metadata for failed call                           33
Usage metadata                                            88
selected files / bytes                         385 / 1,014,433
```

## Provider-Journal Relation Closure

Each of the 33 Job prefixes is contiguous from call ordinal zero and ends in one
`provider_error`. The exact call geometry is:

```text
Provider descriptors / requests / Usage            88 / 88 / 88
successful prefix calls / terminal failed calls     55 / 33
response metadata / error metadata                  55 / 33
Provider-call artifact wrappers                         264
HTTP-success envelopes                               88 / 88
raw requests / raw Provider responses                 0 / 0
private reasoning bodies                                  0
orphan descriptors / invalid relations                0 / 0
```

For every call, v26.229 checks the descriptor's actual canonical bytes; the request artifact's
path, hash, bytes, Job, ordinal, request hash, certificate, and pre-transport Receipt; the Usage
request hash and token counts; and either the successful public-projection relation or the failed
error relation. A successful descriptor's `response_sha256` is the parsed public-projection
hash. Usage `response_hash` instead binds normalized public response content. Those two hashes
are intentionally kept distinct.

For a failed call the descriptor has `response_sha256=null`, while redacted Error and Usage
metadata still retain a normalized public-content hash and length. The latter is diagnostic
metadata, not a persisted raw Provider response.

## Exact Credential-Free Request Reconstruction

The source-bound replay loads the exact v26.209 Manifest, Job objects, current-State Runner,
Runtime, model configuration, implementation, and predecessor bindings. It supplies only the 55
persisted public projections from successful prefix calls.

At the terminal failed call, a dedicated capture transport validates and records the actual
`TransportDispatch`, certificate, and pre-transport Receipt, then raises a local capture-only stop
before any response projection. It supplies no response, constructs no failed-call invocation
record, derives no historical terminal, and makes no network request.

The reconstruction result is:

```text
source Jobs / reconstructed calls                         33 / 88
successful-prefix invocation records                      55
failed requests captured before response projection       33
request hash / byte-count matches                      88 / 88
certificate / pre-transport Receipt matches            88 / 88
public-prefix response projection matches              55 / 55
failed-call historical terminal records                      0
historical Provider calls reissued                           0
```

The observed failed-request phase partition is:

```text
first_action          3   ordinals 58, 116, 139
subsequent_action    25
final                 5   ordinals 16, 62, 78, 102, 136
correction            0
```

These phase labels come from the reconstructed request certificate. They are not caller inputs
and do not classify a historical terminal.

## Content Identifiability Partition

Source authority, request recoverability, and response-content identifiability are separate
properties. All 33 failed requests are exactly reconstructible and therefore eligible for a
fresh future recovery Population. Their persisted response diagnostics split 31/2:

```text
ReasoningBudgetExhaustedError                         31
JSONDecodeError                                        2
exact failed-request recovery authority               33
raw response bytes persisted                           0
raw response bytes guessed                             0
historical terminal assignments                        0
```

For the 31 reasoning-budget rows, the client-normalized public content has exact length zero and
SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
All have `finish_reason=length`; 28 report 16,384 completion/reasoning tokens and three report
16,383/16,383. This proves the normalized public string is empty. Because the raw HTTP response
is absent, it does not distinguish whether the Provider's original content field was null or an
empty string, and it does not recover private reasoning text.

The two JSON rows are:

```text
ordinal 62   finish=length  normalized public length=110
             SHA-256=83b504accbc7117d749cecd9968235d48e5a44bb7366058950c85169fb916046
ordinal 139  finish=stop    normalized public length=3,200
             SHA-256=f71276b285ebd1f80ce162d9c5bcb4460b65bef67bbdbb4b0c36c5ac1b42b718
```

The persisted decoder diagnostic localizes a parse failure, but the normalized strings and raw
envelopes are absent. v26.229 therefore does not reconstruct JSON text, claim exact historical
syntax bytes, or infer a terminal from the diagnostics.

## Fresh Recovery Contract And Population

Each source row receives one fresh Recovery Candidate and one fresh Recovery Job. The Candidate
binds the source-authority, Journal, request-replay, and identifiability Audits; the historical
Job and failure identities only as parents; the complete successful prefix; and the exact failed
request hash, bytes, certificate, Receipt, descriptor, and failure class.

The Recovery Contract requires:

```text
fresh Recovery Job identity                               true
historical Job identity retained only as parent           true
exact successful prefix and failed request binding        true
historical response reconstruction required              false
unknown JSON response invention allowed                  false
historical rerun/reclassification allowed                false
Provider / credential / recovery execution authorized  false / false / false
```

The exact Population contains 33 unique fresh Job identities with zero overlap against any
historical Job, failure-record, Provider-call, or descriptor identity. It retains the 31/2
identifiability partition. Population membership does not authorize execution and does not mark
the 33 historical failures resolved.

## Direct Negative Controls

Twelve controls construct mutated candidate admission objects and recompute each candidate's
content hash before admission. They attempt online authorization, Provider authorization,
cross-Job descriptor substitution, duplicate or missing Population membership, failed-request
hash replacement, historical identity reuse, Host-row substitution, invented JSON response
bytes, truncated call prefixes, JSON syntax reclassification, and Error/Usage artifact swaps.

```text
attacks / rejected / accepted                     12 / 12 / 0
candidate identities recomputed                          12
candidate or Recovery Job writes before rejection         0
Provider calls before rejection                           0
```

The controls reject at source partition, ordered prefix, source-parent, replay-owned-request,
persisted-content-absence, identifiability, fresh-identity, Population-set, source-owned-byte, or
scope admission. A self-consistent downstream content hash does not replace the exact persisted
source and replay authority.

## Noncompensatory Gates

```text
A0 exact v26.228 Freeze                                      PASS
A1 exact v26.226 source authority                            PASS
A2 Provider Journal relation closure                        PASS
A3 exact prefix and failed-request reconstruction            PASS
A4 identifiability and fresh Recovery Population             PASS
A5 direct negative controls and zero scope                   PASS
passed / failed                                               6 / 0
```

No Gate compensates for another. A changed predecessor byte, source row, descriptor relation,
request reconstruction, identifiability statement, fresh identity, negative-control result, or
scope boundary prevents the passing decision.

## Authoritative Identities

The principal identities are:

- authorization / source / v26.228 Freeze:
  `finance_v26_229_external_authorization:dc03c317cc86d91f9dc1edd40fe3d9870726a7965e8dd1d2cfc24eda7055451d` /
  `finance_v26_229_source_identity:07acd7547f18e5b891654dc3a5c56a92b2a1bcbae5749105f2ae93d4174b9154` /
  `finance_v26_229_v228_freeze:d980449099979f151faae0e9a6318a495a1b9e725abb66964be40e82f28bfcb5`;
- source authority / Provider Journal / request replay:
  `finance_v26_229_v226_source_authority_audit:66acdec328cb7bab260601eba8f8360707a5b518d442f551cd8afeac813a92d3` /
  `finance_v26_229_provider_journal_authority:afd0bc6cb9e1ebdb283ef4e69a92fda307b3806aebe5e8a26f0900c33e086334` /
  `finance_v26_229_request_replay_audit:5373177519eb09f98fdf5de74e452511dfc6fd8bfaf072ea1afcd09e84029ecf`;
- identifiability / Contract / Population:
  `finance_v26_229_identifiability_audit:43fd7b63182487b200fcd7345cd325c14c7f25a75e85cf739c9e9a0dd458a65a` /
  `finance_v26_229_recovery_contract:5313f77c0284420e5ee8a23d34f418a52b517ffb8fcf24d1efb49608dda81202` /
  `finance_v26_229_recovery_population:f7b9e21a46abd8efbace595d10ef4d479973eb5631542ee80f5a191e48979821`;
- negative / scope / Gate:
  `finance_v26_229_negative_control_audit:f9ec56c28aec440d79e8d06d749297762b031d1af4f9b4dbe7f1152bf1de8a48` /
  `finance_v26_229_scope_boundary_audit:62d94ce5faf1e3baa311787d9411252134ce49d7f691b0576bfcb2dde284445e` /
  `finance_v26_229_gate_evaluation:107717707d461d1d4be979ba7b7f3739d1fde755d854eb51370462fc3cefeb96`;
- Decision / Transition / Report:
  `finance_v26_229_decision:a81ff8a964d8c58bd7b444c71fc4c910c02938d0f0ce7d07f7c85bc297650e23` /
  `finance_v26_229_transition:2e2160e5568d140141aad37da5133d8904395de5c4ff284666500cba289eae80` /
  `finance_v26_229_preflight_report:bec3dbbf526d38dd566c57cb10c14235d21c21636b4c81fd8f1dd2a088d83ecc`;
- Artifact Manifest / Root:
  `finance_v26_229_artifact_manifest:968a9b5adee2a0c5011c753ec777de8bc91a768745f09943ea676cd2e9e2f863` /
  `finance_v26_229_artifact_root:0e99bbf37aff7faeb3f5adef51eeccd086d3cc760c09de6ecf236de914b6abe1`.

## Source And Reproducibility

The exact source freeze is:

```text
commit  60b17abebae106477089df365d3ddafb2dac3174
tree    040f3831fcf6bd08a9f7b9385321cfb78808acf2
```

The formal directory contains 117 files and 1,105,367 bytes. Its self-excluding Manifest binds
116 members and 1,088,415 bytes. The 16,952-byte Manifest file has SHA-256
`3c74bf72426c33400338e9f234a82bc342f368910a40c84d360ac3bd61b8fa72`.
Two complete empty-directory builds produce exact path and actual-byte equality. Focused tests
pass 15/15. The adjacent v26.226-v26.229 partition passes 50/50. Focused PyCompile, Ruff
check/format, no-import-follow Mypy, and package-wide Ruff pass.

## Transition And Prohibitions

The only permitted successor is:

```text
fresh_exact_v209_unbound_provider_failure_source_authority_and_
recovery_population_preflight_independent_audit_only
```

That stage may independently rebuild the exact directory, rederive the 33-row source population
from actual v26.226 failure files, reconstruct the 88-call Journal and failed requests, confirm
the 31/2 identifiability boundary, rebuild the 33 fresh nonexecuted Recovery Jobs, and repeat the
12 attacks. It must make zero Provider calls and cannot issue an online authorization.

Provider execution, recovery execution, replacement or failed-Job rerun, historical v26.226
mutation or Outcome backfill, empirical estimation, a new online authorization, QA, Mapper,
State, frequency, Contribution, VTDO, training, release, and production remain forbidden. Even
after a passing independent audit, actual recovery requires a separate new external decision and
fresh one-time online authorization.
