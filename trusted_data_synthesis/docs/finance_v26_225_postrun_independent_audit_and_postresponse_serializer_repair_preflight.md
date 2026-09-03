# Finance v26.225 Postrun Independent Audit And Post-Response Serializer Repair Preflight

## Authoritative v2 Correction And Current Boundary

The first formal v26.225 directory remains immutable, but a subsequent independent review failed
it before authorization consumption. That review found three execution-boundary defects and one
documentation error:

1. the deterministic preflight controls read and temporarily overwrote the configured credential
   environment key before a consumption Receipt or Run Start Receipt existed;
2. live refresh compared only five preflight objects while execution still consumed caller-held
   copies of the Catalog, Manifest, implementation, frozen parents, Runtime, model configuration,
   bindings, package path, output path, and ledger path;
3. HTTP 4xx/5xx Journal classification used `http_success` while the relation audit used
   `http_status`, so an HTTP error could become relation-invalid;
4. the v1 report incorrectly said import-following Mypy passed. Only the focused
   no-import-follow check passed; an ordinary import-following run contains historical
   transitive diagnostics, including five local union-inference diagnostics in the frozen v26.224
   executor.

The v1 authorization was never consumed. It is permanently superseded and cannot authorize an
online run.

The authoritative v2 implementation removes all environment access from pre-consumption
controls. Its injected credential-free control client validates the exact frozen model
configuration and exercises the inherited request, HTTP, redaction, Journal, transport, Runner,
and persistence implementation using only a literal synthetic header and local HTTP stubs. The
HTTP Journal now classifies any non-null HTTP status as `provider_error`, matching the independent
relation projection.

Before `_consume` can create the global ledger, v2 reconstructs the fixed formal preflight and
requires exact equality for every execution-bearing object and path:

```text
formal authorization / bytes / preparation
postrun Audit / repair-control Audit
Catalog / Manifest / implementation / frozen parents
Runtime / AgentModelConfig / bindings
resolved package root / output directory / derived ledger path
```

Any caller-side dataclass replacement fails at
`replacement refreshed execution parent admission rejected`. Tests cover changed model
configuration, equal-cardinality reordered Manifest Jobs, changed output path, fully rehashed
authorization parents, and second ledger consumption. Rejection precedes the ledger, output
directory, credential lookup, client construction, and Provider call.

The authoritative v2 source freeze is:

```text
commit  4df1dc598a0b73484eff8c5cfa082d86834bf2b4
tree    0e688f2d2cadddf8edf2665b93292b996c98bf17
```

Principal v2 identities are:

- source / postrun / repair-control Audits:
  `finance_v26_225_repair_source_identity:7748431ea9fb7971ddd8b8a3c267a5f286c847c6e7a8374571cc5db2befd4f8c` /
  `finance_v26_225_postrun_repair_audit:7fc06cabbaccd9726741d7dd04725733b8b0991834aa5f2ff6a237f9c223ef42` /
  `finance_v26_225_repair_control_audit:308e8a4db1954706055202f9e46e065e86cf94873e2d2f2137f14569d8796498`;
- authorization / preparation:
  `finance_v26_225_repaired_replacement_execution_authorization:b4d43c2c0ee8c747003a0bd1c5a7f48bfb994d9d47181a88597546517ab6b282` /
  `finance_v26_225_repair_preparation:909d37530a55664be9a67988b00fa4460daf38b7f6f9493d978acad844b15df0`;
- attack / Gate / Decision / Transition:
  `finance_v26_225_authorization_attack_audit:060b5443347764dd681bd1f6021cd7be8835917e3158c22f8393affc1fd44ac5` /
  `finance_v26_225_repair_gate_evaluation:524dd53bd6d931c8e82343d166f48a2574b66845a50fc313a3c10b718f72d182` /
  `finance_v26_225_repair_decision:e3b09b50d5d502e257026d04a17e2cc67fd654d2354f0656992dc27a190ec0d8` /
  `finance_v26_225_repair_transition:31eecaf65aa001ada19a4ac9877bbc0c9fd66042ab0c729ec8bf06608d5f0147`;
- Manifest / Root:
  `finance_v26_225_repair_artifact_manifest:97e6fc5cf87fd8528fe60bf649a3c838a74ad6d4ff5e7bc0ccb49d5773dc00f3` /
  `finance_v26_225_repair_artifact_root:83bdade0b60d41e14701c36a213d77059f4a3db5a144a121ee417bafc0697c98`.

The fixed newline-terminated v2 authorization remains 30,219 bytes and has SHA-256
`5ca3a89da4a50b31ce9170241f17a2380cdc21e12e0e1940fcd72d52d272c7e7`.
The formal directory contains twelve files and 67,886 bytes; its self-excluding Manifest binds
eleven members and 65,831 bytes. The Manifest file has SHA-256
`e4882f73ae57b87977de257f910c0d6ea6bfd682ebffcefba7c43f20067b6c58`.
Focused repair tests pass 9/9 and the adjacent v26.221-v26.225 partition passes 52/52. PyCompile,
Ruff check/format, package-wide Ruff, and focused no-import-follow Mypy pass. Import-following
diagnostics are retained rather than misreported.

At this record point the v2 candidate remains unconsumed and requires a new independent review.
The operative decision is therefore:

```text
v26_225_v1_independent_audit_failed_and_authorization_superseded_
v26_225_v2_repair_preflight_materialized_independent_audit_required_
online_replacement_execution_blocked
```

The v26.226 output directory and v2 ledger do not exist. Only a passing independent review of the
exact committed v2 directory may activate the already operator-authorized one-shot replacement.

## Historical v1 Scope And Decision (Superseded)

Everything below this heading records the first formal directory's original self-evaluation. Its
passing interpretation, authorization, current-decision wording, transition, and Mypy statement
are superseded by the authoritative v2 correction above. Its artifact bytes are retained only as
historical evidence.

Finance v26.225 consumes only the exact operator sequence:

```text
修正后执行独立审计，然后重跑
如果修订后的审计无误，重跑在线测试，我授予权限
```

The two UTF-8 directives contain 42 and 69 bytes and have SHA-256 values
`61d7416f9e9886eb4c374f2aa7bb7993696f31a928c3559cc20f053e6c1023d8` and
`9d2d804d662735bf0b9dc539be16a89e5dc22a515f11df2e55eaa7eea5de3929`.
They authorize a replacement execution only after the failed v26.224 lineage is independently
reconstructed and the repair preflight passes. v26.225 itself is credential-free and makes no
real Provider call.

The decision is:

```text
postresponse_serializer_repair_independent_audit_passed_
replacement_online_execution_authorization_issued_not_consumed
```

The authorization exists but remains unconsumed. No v26.226 output directory, consumption
Receipt, Run Start Receipt, empirical row, QA read, Mapper, State, frequency, Contribution, or
VTDO row is created by this stage.

## Exact v26.224 Postrun Reconstruction

The audit reads all 398 immutable v26.224 files and rebuilds the self-excluding Manifest from
actual bytes. It binds:

```text
formal files / bytes                 398 / 680,947
Manifest members / member bytes      397 / 609,062
exact Jobs / request intents         192 / 192
Job failure records                       192
response / error / Usage metadata      0 / 0 / 0
Provider descriptors                       0
five-layer evidence files                  0
```

All 192 failures have digest
`651fb4b608ea3f399df980361cfa585307bf865e2a24eb03dbf00fbbcfa0aa6a`,
which is the digest of the exact frozen failure text
`builtins:AttributeError:'dict' object has no attribute 'model_dump'`.
The v26.224 source contains two calls to
`redacted.model_dump(mode="json", warnings=False)`; the repaired source contains neither and
uses `dict(redacted)` in both the success and exception paths.

The stored v26.224 Summary's zero Provider-call field is retained as an immutable
descriptor-count value. It is not interpreted as proof of zero outbound calls. Request intent is
written before HTTP and therefore is generally an upper bound on attempts if the process stops
before descriptor completion. A closed descriptor is the lower bound. For the exact v26.224
failure, the source locus proves that the HTTP response reached post-response redaction, but
discarded HTTP/model/Thinking/Usage/token/cost details remain unavailable and are not guessed.

The reconstructed Audit is
`finance_v26_225_postrun_repair_audit:7fc06cabbaccd9726741d7dd04725733b8b0991834aa5f2ff6a237f9c223ef42`.

## Executed Credential-Free Repair Controls

The formal preparation does not accept default Boolean claims. It temporarily supplies a
synthetic in-process key value and replaces only the HTTP function with deterministic local
responses. The exact frozen model configuration and actual
`ExactRequestBodyDeepSeekClient -> ProviderJournal -> LiveV209Transport -> v26.209 Runner`
route remain in use. The temporary key and HTTP function are restored in `finally`; neither
control reads a credential or calls the real endpoint.

The success control returns one HTTP-200 object with public content `{}`, Thinking presence,
and complete synthetic Usage. The actual v26.209 Runner derives
`first_response_abi_invalid`, writes exactly one request, response, Usage, and descriptor file,
then writes Raw -> Result -> Trace -> Outcome -> checkpoint. The error control raises a local
`URLError`; it writes exactly one request, error, Usage, and descriptor file, returns an
unbound-Provider failure record, and writes no five-layer terminal chain.

```text
synthetic HTTP calls success / error               1 / 1
Provider descriptors success / error               1 / 1
Provider journal files success / error              4 / 4
five-layer files success / error                    5 / 0
real Provider calls / credential lookups            0 / 0
```

Each control reparses every Provider descriptor and actual artifact. It requires the exact path
`provider_calls/<sha256(job_id)>/call_<ordinal>`, canonical bytes, artifact kind, SHA-256, byte
count, Provider-call identity, Job, ordinal, request-intent hash, response-or-error exclusive
partition, Usage request hash and token counts. The success five-layer control additionally
rereads every payload and verifies embedded Raw, Result, Trace, Outcome, and checkpoint parents.

The control Audit is
`finance_v26_225_repair_control_audit:308e8a4db1954706055202f9e46e065e86cf94873e2d2f2137f14569d8796498`.
Timing-derived record IDs are deliberately excluded from this formal identity; the semantic
checks are rerun on every independent reconstruction.

## Frozen Source And Expected-Byte Authorization

The authoritative implementation source is:

```text
commit  2e7c7cc488af42e10b6bb998b7fd47bdeb96551c
tree    3983bf1ce99a0fe5ced8a3e067ee86ed3635b7f7
```

The Source Identity binds actual committed bytes for the repaired v26.224 executor, v26.225/v26.226
orchestrator, independent replacement models, and focused tests. Its identity is
`finance_v26_225_repair_source_identity:a44806c7041015d58f9d71de6e7da3e5f1582585087b1c0e9de3c286c8bcd6b3`.

The new authorization binds that source, the v26.224 Manifest/Root/Summary/Transition/consumption
and Run Start identities, the exact v26.223 authorization ID and file SHA-256, its Composition,
the exact v26.209 Manifest/Root, and all 192 sorted Job IDs. It permits only a whole-condition
fresh-identity replacement; selective failed-Job recovery, rerun, condition change, historical
response reuse, caller terminal input, and QA integration are false.

The fixed newline-terminated authorization member is 30,219 bytes at SHA-256
`8f509454dc8e617070aac201feda9036d3446dbc68df1cac891e117dd8659caa`.
Its identity is
`finance_v26_225_repaired_replacement_execution_authorization:0b616131fe08f060bce25f179978ccc516a148bd8bad707b8aa28807a954f9f3`.
Live preparation reads these formal bytes; it does not mint a new authorization. It independently
reconstructs every expected object from the frozen source and parents and requires exact actual
bytes before creating a prepared execution. Consumption repeats this Guard and derives the
global no-replace ledger path only from the fixed authorization ID.

Eight model-valid candidates alter audit/source parents or commit/tree fields and fully recompute
their authorization IDs. All eight differ from the expected bytes and reject before a post-Guard
probe, credential lookup, or Provider call. The Attack Audit is
`finance_v26_225_authorization_attack_audit:b4bd117e42fd7132760ab02441a9f4cce514b8219cffca20fa1da8ff04806be2`.

## Noncompensatory Gates

```text
P0 exact v26.224 failure reconstruction                         PASS
P1 TypedDict post-response serialization repair                 PASS
P2 mock-success Provider journal and five-layer closure         PASS
P3 mock-error Provider journal closure                          PASS
P4 exact parents and 192-Job condition                          PASS
P5 expected-byte and fully rehashed attack rejection            PASS
P6 zero-real-Provider and credential boundary                   PASS
passed / failed                                                  7 / 0
```

Principal identities are:

- Preparation:
  `finance_v26_225_repair_preparation:e8a43f7168a06850a582fa70a374c5006bc3ec73d2604dc823d92448f61b4f4e`;
- Gate:
  `finance_v26_225_repair_gate_evaluation:b29e8ce67fc96f7ee1b45494298fc41b533e4ce38f3b8c212af946c3f50db46e`;
- Decision:
  `finance_v26_225_repair_decision:2136a6748cdcf4c2031a5149df9289dc7a35e257b2f3c2f57546102992ee2280`;
- Transition:
  `finance_v26_225_repair_transition:a393e48ca45e59f3f3bf78c5f9475667143410f7617f801625f29e7607851563`;
- Manifest / Root:
  `finance_v26_225_repair_artifact_manifest:f927f642ad737569aedb83a1ee511f2af7b0193801521a012335d08102f297da` /
  `finance_v26_225_repair_artifact_root:656e2faaac619e4f6034ea711ef7e17597ebefebdd910e6bdba8a2e8f2c56467`.

The formal directory contains twelve files and 67,886 bytes. Its self-excluding Manifest binds
eleven members and 65,831 bytes; the Manifest file SHA-256 is
`b6e943ad5d3afb8a731c515d4821b272aa12b6a8fe3314798c74124193fccacf`.
The fixed preparation was independently reconstructed in a second process with exact byte
equality. Focused original-plus-repair tests pass 27/27; PyCompile, focused and package-wide Ruff,
no-import-follow Mypy, and import-following Mypy pass.

## Transition

The sole permitted successor is:

```text
fresh_exact_v209_parent_bound_postresponse_serializer_repair_
exact_192_job_replacement_online_execution_only
```

It must validate the complete fixed v26.225 formal directory, present the exact authorization
bytes, consume them once in a fresh global ledger, durably write the consumption and Run Start
receipts, and only then cross the credential boundary. It must execute all 192 Jobs as a new
whole-condition replacement and preserve v26.224 unchanged.

After the execution, downstream interpretation remains blocked pending a credential-free
independent postrun audit. Further replacement, selective rerun, recovery, condition change,
empirical estimation outside that audit, QA, Mapper, State, frequency, Contribution, VTDO,
training, release, and production remain forbidden.
