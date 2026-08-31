# Finance v26.191 Minimal Exact-route Online Diagnostic

Audit date: 2026-08-31

## Decision

Finance v26.191 consumes only the exact external authorization:

```text
fresh_identity_minimal_exact_route_diagnostic_online_execution_only
```

The stage performs one fresh engineering diagnostic Population. It is not a v26.188 Recovery,
does not reuse any v26.188 Job identity, does not enter the old 192-Job denominator, and is not a
Capability estimate. The online result is:

```text
diagnostic decision                         prompt_specific_request_rejection
online HTTP requests / automatic retries    6 / 0
HTTP 200 / HTTP 400                         5 / 1
old v26.188 Job reruns / RecoveryJobs        0 / 0
historical Outcome reclassifications         0
all diagnostic safety Gates                  PASS
```

The current request-acceptance defect is localized: the frozen v26.188 Prompt does not contain
the case-insensitive lexical token `json`, while its request sets
`response_format={"type":"json_object"}`. The Provider's typed HTTP 400 message identifies that
exact missing Prompt requirement. A same-UTF-8-length safe synthetic Prompt that explicitly asks
for JSON succeeds under the same endpoint and full seven-field request shape.

This directly diagnoses the current rejection of the exact first v26.188 request bytes and finds
the same lexical omission in all 192 frozen v26.188 Prompts. It does not retroactively recover a
persisted HTTP error body from 2026-08-30, prove that the Provider's temporal enforcement was
unchanged, or change any historical terminal.

## Authorization and source freeze

The external review contains 10,990 bytes at SHA-256
`d8fd6ad5cda29e419737c87b5dbd3641e0b5f906a98c0f222ab0a70c40ae510c`. The operator decision
`做在线诊断` selects only its one authorized online stage. The implementation hard-codes a ceiling
of nine HTTP requests and zero automatic retries.

The exact online source is commit
`662122f4db381ef936a91f985070f42ed6bca2a8` with Tree
`834976a2ece966ef99e36db4127c9280d9ab8cee`. Before credentials are read, the embedded prepare
check validates the v26.190 Report and Artifact Root, reconstructs the first frozen v26.188
Prompt and request body, and matches their persisted pre-call certificate:

```text
first Prompt SHA-256        cbc7d15baf4f01ecd1e306a23fdf7fc89bcc5255b454e51fbcba30f7b6039312
first Prompt UTF-8 bytes    12,986
first request SHA-256       f636d832f224db08f21f3e7f0f07be7a9455574afcdb4a3cfb4eb69adbcb5092
first request bytes         14,409
certificate match          true
prepare Provider calls     0
prepare credential reads   0
```

The prepare identity is
`finance_v26_191_diagnostic_prepare:eae2aba2f145a3cee179e16471b7550c170918b0bc7578893ee87aca1ba324ac`.

The first attempted process start found no `.env` in the isolated worktree and failed before
output-directory construction, credential loading, or any HTTP request. The final source adds an
explicit credential-file input that accepts only a private file. The online process reads the
canonical project's mode-`0600` `.env` into process memory; neither its path, value, nor value
hash enters the formal artifacts.

## Exact online observations

The fixed and adaptive sequence stopped after D5:

| Step | Method and route | Request bytes | Result | Typed interpretation |
| --- | --- | ---: | ---: | --- |
| D0 | `GET /models` | 0 | 200 | current credential can list models; exact Flash ID visible |
| D1 | `POST /chat/completions` | 117 | 200 | official minimal route healthy |
| D2 | `POST /v1/chat/completions` | 117 | 200 | historical route alias also healthy |
| D3 | official route, full seven-field shape, minimal JSON Prompt | 228 | 200 | model, Thinking, JSON format, 16K, and sampling combination accepted |
| D4 | official route, exact first frozen v26.188 Prompt and body | 14,409 | 400 | typed Prompt/JSON-output contract rejection |
| D5 | official route, safe synthetic JSON Prompt with exact D4 Prompt UTF-8 length | 13,179 | 200 | long Prompt surface and full parameter shape accepted |

D1 and D2 use byte-identical bodies at SHA-256
`eb73d347013dbceb4c0e77ba2e37a7a137599fbad496cc93277d18b354ae881d`.
D3 uses SHA-256
`9851a2b15e6fb58a8f6c0ba6e8a19a09d598bbb6eddee7cc87ec671185f4d28c`.
D4 is the exact first v26.188 request body certified above. D5 uses Prompt UTF-8 length 12,986,
equal to D4; its canonical request body is shorter because the synthetic text does not require
the large number of JSON string escapes present in D4. The v26.190 size comparison already showed
that request byte size is not a deterministic separator, and D5 is used only as the authorized
same-Prompt-length content control.

The only HTTP error is a recognized JSON error object. Its persisted safe projection is:

```text
status          400
error.type      invalid_request_error
error.code      invalid_request_error
error.param     null
error.message   Prompt must contain the word 'json' in some form to use
                'response_format' of type 'json_object'.
body bytes      195
body SHA-256    cbb1efeb6634b76176ac35c8e3c591c218b9501ed5ca4d9d49fff80ad5dfdca9
```

The D4 result is consistent with the current official Chat Completions documentation, which says
that `response_format={"type":"json_object"}` requires the system or user message itself to
instruct the model to produce JSON. The current API reference still lists both
`deepseek-v4-flash` and enabled Thinking as supported request values:

- <https://api-docs.deepseek.com/api/create-chat-completion/>
- <https://api-docs.deepseek.com/api/list-models/>

## Complete frozen-Prompt lexical census

After the online result, a separate credential-free, read-only census rerenders all exact 192
v26.188 first Prompts through the frozen state-bound Runtime. It does not construct a Provider
client and writes no empirical row:

```text
frozen Prompts                                 192
case-insensitive `json` token present            0
case-insensitive `json` token absent            192
Prompt UTF-8 range                     12,053 .. 17,069
Provider calls                                     0
```

This closes the denominator-wide lexical surface: the online D4 omission is not unique to one
Job. It remains methodologically important to distinguish the following claims:

- directly observed now: the exact first frozen request is rejected for missing `json` in its
  Prompt;
- deterministic frozen-source fact: all 192 old Prompts share that omission;
- strongly supported historical explanation: this shared Prompt/response-format mismatch explains
  the old 192 x HTTP 400 partition;
- still unavailable: the original Provider error bodies and a proof that the server-side temporal
  enforcement state was byte-for-byte identical during v26.188.

Accordingly, `historical_exact_cause_recovered` remains false in the formal Report. This avoids
turning a current exact reproduction plus complete frozen-source census into a false historical
response-body recovery claim.

## Privacy-first persistence

Every response is read exactly once. Successful response content and `reasoning_content` are
discarded after computing response-body SHA-256 and byte count. Error responses retain only the
typed `error.type`, `error.code`, `error.param`, a credential-pattern-redacted `error.message`,
and optional request ID. Unrecognized errors would retain only a redacted first 4 KiB.

The formal observations persist no Authorization value, API-key hash, Cookie, complete Header
set, private reasoning, or unchecked raw response body. An independent exact-byte scan compares
the current credential against every formal file and finds zero occurrences. All eleven Artifact
Manifest members independently match their SHA-256 and byte count.

## Historical and downstream boundary

The v26.188 and v26.189 estimates remain exactly:

```text
q_job                                0/192
q_semantic_given_model_endpoint      null
```

No old Job is rerun or replaced. No RecoveryJob, historical reclassification, Confirmation
access, Mapper, State, frequency, Contribution, VTDO, Student, training, release, or production
row is created. D0--D5 are engineering diagnostics only and cannot be pooled with Capability
outcomes.

The result supports a future prospective repair subject—making the model-visible Prompt satisfy
the already frozen JSON-output request contract—but this stage does not implement or authorize
that repair. A fresh successor Population and a new explicit audit decision would be required.

## Artifacts, tests, and transition

The immutable formal directory is
`artifacts/vtdo_experiment/finance_v26_191_minimal_exact_route_online_diagnostic_v1_20260831`.
It contains twelve files: eleven Manifest members plus the Manifest itself. The eleven members
contain 24,281 bytes. Authoritative identities are:

- Report:
  `finance_v26_191_online_diagnostic_report:4bbd4b1de318271017870147065de6415a7b7f3215bf54b58ded1ac7cde9cb26`;
- Artifact Root:
  `finance_v26_191_online_diagnostic_artifact_root:47ce56c1e3ada224121b334c19fee66b485920de3bce132e0d4fea4b49672004`;
- Artifact Manifest:
  `finance_v26_191_online_diagnostic_artifact_manifest:50f4dc0d237708da12d17e971f602bf3527aa906702954e2026093143a387861`;
- Transition:
  `finance_v26_191_online_diagnostic_transition:8345c8a7528276ce88cc2f16d5906f9123b77f4e665fcdeb802360467d1bf9a1`.

Focused tests pass 7/7. The v26.190--v26.191 adjacent suite passes 14/14. Focused PyCompile,
Ruff check/format, and no-import-follow Mypy pass.

The current decision is:

```text
no_further_experiment_authorized_without_new_audit_decision
```

Provider execution, a repaired Prompt, a fresh Development Population or successor Job set,
Capability estimation, Confirmation, Mapper, State, frequency, Contribution, VTDO, Student,
training, release, and production remain unauthorized.
