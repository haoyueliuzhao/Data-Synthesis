# Finance v26.190 Exact-route HTTP 400 Request-contract Root-cause Audit

Audit date: 2026-08-31

## Decision

Finance v26.190 performs only the operator-selected, zero-Provider stage:

```text
exact_route_http_400_request_contract_root_cause_audit_only
```

The attached v26.189 review itself retained
`no_further_experiment_authorized_without_new_audit_decision` and named the stage above only as
the unique recommended next decision. The current operator instruction
`参照审计开展后续实验` is therefore persisted separately and consumed only as selection of that
unique recommended zero-Provider stage. It does not authorize Provider execution, construction of
a Provider client, credential reading, RecoveryJobs, request-route repair, replacement of any
v26.188 Job, or downstream empirical work.

The audit passes its declared scope. Its scientific result is:

```text
v26.188 exact request reconstruction                    PASS
historical exact-route HTTP-success comparison          PASS
deterministic fixed request-contract difference         NONE_FOUND
unique HTTP 400 root cause                              NOT_LOCALIZABLE_FROM_PERSISTED_ARTIFACTS
Provider calls / Provider clients / credential reads    0 / 0 / 0
```

This is a negative localization result, not a claim that the request was acceptable at the
Provider on 2026-08-31 and not a claim that the Provider was at fault.

## Bound authorization

The exact external v26.189 review contains 9,199 bytes at SHA-256
`92b26fcccaf79a13423a1f1c392c996227a60c8a9a15167bb20e98adeea297dc`.
The audit persists those bytes and the current operator instruction as distinct provenance
objects. The authorization explicitly records that the external review's prior decision was
`no further experiment`, that the current instruction is the new selection event, and that only
the unique recommended zero-call stage is consumed.

## Frozen predecessors

The audit binds the exact v26.188 online source and artifact commits and the complete v26.189
post-run audit source and artifact commits. It validates the v26.189 Report, formal Artifact Root,
and independently defined v26.188 directory Manifest before loading any request evidence.

The frozen identities include:

```text
v26.188 source commit    53d0128f22043a88efb612af835aa99bdc78ede4
v26.188 source Tree      38456681dfd2e3d18fa65b1268245affc1e34d39
v26.188 artifact commit  da40cb1512d86296cbeb14b127ace4c20cfd076e
v26.188 artifact Tree    ac3371743c1ec3d010bf27dea6afb860e7297530
v26.189 source commit    bca20b7857bdda89523c94ee40ea1fbc22fb7404
v26.189 source Tree      4a39b83ceb5acf67fda52c084802f3c6763fb867
v26.189 artifact commit  a8002297fc498842e79ee8fde5382ec898a2738f
v26.189 artifact Tree    658cd2e8c7c2b0401d5df61c65a93d279411dde2
```

The exact v26.188 directory remains 1,350 files and 3,618,348 bytes. Its independently defined
sorted-path content Root remains
`finance_v26_188_independent_directory_content_root:a1cdb58c4eda548ece6060e68126ab1b9750848850c5aa69ca739a6356653196`.
The v26.188 directory and all historical comparison Envelope files are rehashed before and after
the audit. Historical mutation and reclassification counts are zero.

## Exact v26.188 request reconstruction

For each of the exact 192 Manifest Jobs, the audit independently reloads its frozen Runner
Package, initializes the state-bound Runtime, renders only the first current Prompt, and rebuilds
the exact canonical request body. It does not instantiate
`StageOneProspectiveThinkingJsonClient` and never enters `urllib.request.urlopen`.

The independently reconstructed request body is exactly:

```json
{
  "max_tokens": 16384,
  "messages": [{"role": "user", "content": "<exact current Prompt>"}],
  "model": "deepseek-v4-flash",
  "response_format": {"type": "json_object"},
  "temperature": 0.6,
  "thinking": {"type": "enabled"},
  "top_p": 0.9
}
```

Canonical JSON uses UTF-8, sorted keys, compact separators, and no trailing request byte. Across
all 192 rows, independently recomputed Prompt SHA-256, request-body SHA-256, request-body byte
count, field set, request kind, phase, and exact request-shape identity match the persisted
pre-call certificate. The exact results are:

```text
Jobs / reconstructed requests                       192 / 192
exact request-certificate matches                   192 / 192
Prompt UTF-8 bytes                              12,053 .. 17,069
canonical request-body bytes                    13,418 .. 18,770
forbidden control characters / surrogate codepoints     0 / 0
request kind / phase                         semantic_proposal / primary
HTTP status                                               400 x 192
response Envelope / HTTP error body persisted               0 / 0
```

The Prompt schema has exactly `public_prompt` and `response_abi` at its top level. Each request
contains one user message. The reconstruction establishes what was serialized and passed to the
HTTP request constructor; it does not recover the secret Authorization value or the Provider's
discarded HTTP error body.

## Historical same-route HTTP-success corpus

The comparison denominator contains every persisted Provider Envelope from five complete
exact-Flash online executions:

```text
v26.134    197 / 197 HTTP 200
v26.138    191 / 191 HTTP 200
v26.151    879 / 879 HTTP 200
v26.154  3,043 / 3,043 HTTP 200
v26.164  2,919 / 2,919 HTTP 200
total    7,229 / 7,229 HTTP 200
```

Every row has an admitted response Envelope with `response_model=deepseek-v4-flash` and the same
content-addressed request shape as v26.188. The formal corpus persists a sorted
`relative_path / sha256 / byte_count` preimage for all 7,229 Envelope files and a separate corpus
Root.

Historical successful canonical request bodies range from 3,759 to 55,126 bytes. The complete
v26.188 range of 13,418 to 18,770 bytes is strictly contained inside that successful range, and
1,811 historical HTTP-success requests fall inside the exact v26.188 interval. Request byte size
is therefore not a deterministic separator between these failure and success corpora.

## Request-contract comparison

The exact persisted comparison is:

| Surface | v26.188 HTTP 400 | Historical HTTP 200 | Result |
| --- | --- | --- | --- |
| endpoint | `https://api.deepseek.com/v1/chat/completions` | same | match |
| model | `deepseek-v4-flash` | same | match |
| `max_tokens` | 16,384 | same | match |
| Thinking | `{"type":"enabled"}` | same | match |
| response format | `{"type":"json_object"}` | same | match |
| body fields | seven exact fields | same | match |
| model-config identity | exact frozen identity | same | match |
| Thinking binding | exact frozen identity | same | match |
| messages wrapper | one user message | same serializer | match |
| nonsecret Headers | Authorization + Content-Type names | same serializer | match |
| serializer | canonical sorted compact UTF-8 | same source | match |
| body-size envelope | 13,418–18,770 | 3,759–55,126 | contained |

The Stage 1 serializer source last changed at commit
`bc3a9ba8d109ccd63fdf563a609611bfc5cba797`; the base Header/client source last changed at
`6b7243bfd886fe7845ffd4182f57af2ba03f050b`. Both current files match the exact v26.188 source
commit bytes. The historical successes postdate both source changes and carry the exact same
request certificate schema and shape identity.

The comparison finds zero deterministic differences in the frozen fixed request contract and
zero Prompt/body encoding defects. This does not prove that all inputs to Provider acceptance
were equal: the Authorization header value was neither read nor persisted, and Provider-side
state is outside the local artifacts.

## Root-cause boundary

The available evidence rules out a persisted deterministic difference in:

- endpoint URL;
- requested model;
- Completion bound;
- Thinking value;
- response-format value;
- request-body field set;
- model profile and model-config identities;
- Thinking binding identity;
- messages wrapper shape;
- nonsecret Header schema;
- canonical JSON serializer source;
- request byte-size envelope;
- Prompt UTF-8 encoding.

Three causal surfaces remain unevaluable:

1. the exact Authorization header value, account, or account-to-route binding used during
   v26.188;
2. Provider server-side contract, deployment state, and exact model availability at the execution
   time;
3. the HTTP 400 response body, which the frozen privacy-first client did not persist.

Consequently the only supported root-cause result is:

```text
not_localizable_from_persisted_artifacts
```

It would be an overclaim to name model availability, credential/account routing, prompt content,
or any fixed request field as the unique cause.

## Controls and Gates

Thirteen production controls change endpoint, model, max tokens, Thinking, response format,
request fields, profile SHA-256, model-config identity, Thinking-binding identity, exact-route
flag, fallback policy, secret-header visibility, or HTTP-error-body visibility. All thirteen
reject under exact fixed-shape or persisted-evidence validation. Accepted mutations are zero.

Seventeen static Gates pass, covering authorization provenance, predecessor freeze, exact request
reconstruction, certificate bytes, Prompt encoding, the 7,229-row HTTP-success corpus, one exact
request shape, body-size overlap, serializer lineage, Header-schema comparison, null handling for
unobservable factors, non-overclaiming, destructive controls, zero Provider calls, zero
historical reclassification, zero repair/recovery, and zero downstream admission.

Focused v26.190 tests pass 7/7. Focused PyCompile, Ruff check/format, and no-import-follow Mypy
pass. Final source identities, adjacent regression counts, formal artifact identities, and byte
geometry are recorded after source freeze and immutable formal construction.

## Transition

The audit does not repair the route and does not authorize an online diagnostic. The resulting
decision is:

```text
no_further_experiment_authorized_without_new_audit_decision
```

Because existing artifacts cannot localize the unique cause, the only recommended future subject
is:

```text
fresh_identity_minimal_exact_route_diagnostic_contract_preflight_only
```

That future stage may design a fresh-identity, credential-free, minimal-denominator diagnostic
Contract that preserves the v26.188 history and captures a safe error-classification surface. It
is not authorized now. Provider execution, old-Job rerun, RecoveryJobs, route repair, Mapper,
State, frequency, Contribution, VTDO, Student, training, release, and production remain forbidden.
