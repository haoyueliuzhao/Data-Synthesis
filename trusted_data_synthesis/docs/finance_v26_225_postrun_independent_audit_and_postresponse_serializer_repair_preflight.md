# Finance v26.225 Postrun Independent Audit And Post-Response Serializer Repair Preflight

## Scope And Decision

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
