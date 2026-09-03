# Finance v26.224 Fresh Exact v26.209 Parent-Bound Exact 192-Job Online Execution

## Scope And Outcome

Finance v26.224 consumed only
`fresh_exact_v209_execution_condition_authoritative_parent_bound_exact_192_job_online_execution_only`.
The exact 15,248-byte external review is bound at SHA-256
`10733a734b94693194eb85ac4ab0ee4fe475b48cf2cca5724c936308ed91cbb0`.
It accepts v26.223 as `PASSED_AS_SCOPED`, reports no blocking defect or mandatory revision, and
permits only the exact one-shot execution. The 33-byte directive `参照审计，并行开展实验`,
SHA-256 `2520ed8c585242e0792249256ee8306c3d8397891589cce5bd40a20b06c641de`,
consumes that transition.

The run did not produce a valid empirical execution:

```text
execution status                                      INCOMPLETE
exact Jobs scheduled / failure records                 192 / 192
valid Job execution records                                  0
Raw / Result / Trace / Outcome / checkpoint             0 / 0 / 0 / 0 / 0
authorization consumptions / Run Start Receipts              1 / 1
replacement / rerun / recovery Jobs                         0 / 0 / 0
```

Every Job stopped after its first Provider response reached the Host's redacted-response path.
All 192 failures have the same exact error digest:

```text
651fb4b608ea3f399df980361cfa585307bf865e2a24eb03dbf00fbbcfa0aa6a
```

Under the exact frozen source this is the SHA-256 of:

```text
builtins:AttributeError:'dict' object has no attribute 'model_dump'
```

The defect is local and deterministic. `capture_redacted_provider_response_fields` returns a
`TypedDict`, while the v26.224 client calls `.model_dump()` on that dictionary in both the normal
return path and the enclosing exception path. The second call masks the first failure and escapes
before response metadata, Usage metadata, or a Provider-call descriptor can be written.

This is not a model result, terminal observation, Capability estimate, or evidence that the model
failed any frozen Action, State, Correction, or Final contract.

## Exact Ingress And One-Time Consumption

Before credential lookup or Provider-client construction, the executor validated:

- the complete 17-file, 136,590-byte v26.223 formal directory and the exact SHA-256 of its
  Manifest file;
- the exact 35,090-byte v26.223 authorization file and canonical 35,089-byte Guard input;
- the exact 21-file, 44,916,386-byte v26.209 directory and Manifest file SHA-256;
- the exact 32 Packages, 192 Jobs, v26.209 Runner and Execution Contract;
- the v26.213 main dispatcher/persistence and v26.218 source-bound failure/complement parents.

The exact preparation identity is
`finance_v26_224_execution_preparation:c9c7544161cb41c128bd349280f7e794efc3ac64d98ce76234dd2e75db64c795`.
The fresh external execution authorization is
`finance_v26_224_external_execution_authorization:950cde32a691ccab7dbd23bae1d84b37012005c82212733320e9504c940f7342`.
The v26.223 Freeze is
`finance_v26_224_v223_authorization_freeze:8f00391e265b060f4eab85b01c0bff487ecfe3a54fde65a326d4581f82a64f68`.

The source tree was clean before consumption. The run is bound to:

```text
source commit  ef0c34ea2eedf305311fa27e3e9187239307e874
source tree    697492c60255aafef727c0bd8ba45b31bfef442a
```

The global no-replace ledger was created before the run directory. Its exact ledger file is 1,181
bytes at SHA-256
`cb4cb4ab675c520514b849ac448442b826620f08ad54b682e86bc777a71adcf5`.
The consumption and start identities are:

- `finance_v26_224_authorization_consumption_receipt:e784a94f87f8b275d50fdea51b9373c503753ae661a05349431a8d2cf6621aea`;
- `finance_v26_224_run_start_receipt:00ae0af03a4fd89a840b9ac2fa39c7b38e9c63a2c95740d7dd69570ff13e3629`.

The v26.223 authorization is therefore consumed and cannot authorize another call, replacement,
rerun, or recovery.

## Provider Boundary And Evidence Loss

Each of the 192 exact Jobs durably wrote one request-intent record before entering
`urllib.request.urlopen`. There is exactly one intent per Job and no second-call intent. Every
failure record has the same post-redaction `AttributeError` digest. Given the exact source data
flow, this establishes that all 192 call paths received a JSON-object response body far enough to
construct the redacted field dictionary. However, the escaping serialization defect prevented the
following objects from being materialized:

```text
request intents                                         192
response metadata                                         0
error metadata                                            0
Usage metadata                                            0
Provider-call descriptors                                 0
retained public response projections                      0
retained private reasoning content                        0
```

Consequently, exact HTTP status, response model, Thinking telemetry, Usage, token totals, cost,
and public response bytes are unavailable. They must not be reconstructed or guessed.

The frozen `execution_summary.json` serializes `provider_call_count=0` and zero tokens because its
old model counts only completed descriptors. That field is not an accurate count of outbound or
returned Provider interactions for this failure mode. It is retained as immutable failed-run
output, while the 192 request intents and exact post-response failure digest supersede its
zero-call interpretation. No downstream audit may treat the stored zero as evidence that no
Provider interaction occurred.

## Terminal And Persistence Boundary

The defect occurs before the exact v26.209 response is returned to the injected transport.
Therefore no response reaches the current-State Runner, v26.213 observation dispatcher, v26.218
source-exit dispatcher, or v26.195 policy admission. The exact result is:

```text
main observation-derived terminals                         0
source-bound instrument/privacy terminals                  0
unbound Provider-failure terminal assignments              0
caller-selected terminal assignments                       0
terminal evidence admitted                                 0
five-layer evidence admitted                               0
empirical rows / estimates                               0 / 0
```

The 192 `JobFailureRecord` objects explicitly set `terminal_evidence_admitted=false` and
`five_layer_evidence_admitted=false`. They preserve the exact Job set and ordinals but do not
replace an Outcome denominator.

## Artifact Geometry And Identities

The immutable execution directory contains 398 files and 680,947 bytes:

```text
root ingress/summary/transition/Manifest files             14
Job failure records                                       192
Provider request-intent records                            192
total                                                      398
```

Its self-excluding Manifest binds 397 members and 609,062 bytes. Principal identities are:

- Summary:
  `finance_v26_224_execution_summary:8b88cb6cc97d9a0f57fcf3e0ab805510e960d1c80e6e7beef67fbea5f54f58b5`;
- Transition:
  `finance_v26_224_transition:1670d9b380a87d2c178a48a5b3dc9b543611b092d7d27ce7af2cffdde1e00b73`;
- Artifact Manifest:
  `finance_v26_224_artifact_manifest:16f18a3fca68d190327d9d81f39e4251a817c97f2bb573e07018846424003c59`;
- Artifact Root:
  `finance_v26_224_artifact_root:71435d07e0f486d01a4654007231ace5381465796d165f02f2e67e55ea602925`.

The Manifest file itself is 71,885 bytes at SHA-256
`f85a1ea86c4e581ad8f94bae9af9fbc8d28638cc861b1ce138639949278fade1`.

## Pre-Execution Validation Record

Before consumption, the new focused suite passed 19/19. It included a fake client driving one
actual v26.209 Runner Job through Provider journaling and all five persistence layers, but it did
not exercise `ExactRequestBodyDeepSeekClient.complete_body` against a mocked HTTP response. That
test omission allowed the TypedDict/Pydantic mismatch to escape.

Focused PyCompile, Ruff check/format, and no-import-follow Mypy passed; package-wide Ruff passed.
In the adjacent monolithic run, 131 tests passed and one frozen v26.216 complete-rebuild test
encountered its historical `id(error)` proof-lifetime nondeterminism. The exact v26.216 rebuild
control passed when isolated, and v26.217 passed 8/8 in an isolated process. These checks validate
the static and scripted surfaces only; they do not compensate for the live client defect.

## Decision And Required Successor Order

The current decision is:

```text
v26_224_exact_192_job_online_execution_incomplete_at_
post_response_redacted_typed_dict_serialization
```

The next admissible work is a credential-free independent postrun audit of the exact 398-file
directory. It must independently revalidate every byte, reconstruct the 192 Job/intent/failure
join, prove the precise source failure locus, correct the Summary's descriptor-only call-count
interpretation, and verify that no terminal or five-layer evidence exists.

A later repair must use a fresh source identity, explicitly test both HTTP-success and HTTP-error
redacted paths, and make request-intent accounting independent of descriptor completion. It may
not modify this run, reuse its authorization, or reconstruct discarded response/Usage data.

Any rerun or recovery requires a separate external audit decision and a fresh online
authorization binding the failed v26.224 lineage, the independently audited defect, the repaired
source commit, and fresh execution identities. The current operator request does not fabricate
that external decision. QA, Mapper, State, frequency, Contribution, VTDO, training, release, and
production remain forbidden.
