# Finance v26.100 Thinking 8K Completion Calibration Runner Preflight

Date: 2026-08-22

## Decision

Finance v26.100 completed the only transition authorized by v26.99:

```text
thinking_8k_completion_calibration_runner_and_preflight_only
```

The stage implements the exact Runner for the v26.99 8K Contract and 32-Job Manifest and
qualifies that Runner with credential-free scripted fixtures. The preflight passed. The exact
v26.101 8K engineering calibration is now the only permitted online transition:

```text
thinking_8k_completion_calibration_execution_only
```

The authoritative preflight report is:

```text
finance_v26_exact_8k_runner_preflight_report:da74cbc040525571bb636986bbdf198a24948f5967f027cf42422537372968f0
```

This is an execution-Instrument preflight, not an online result. It establishes neither 8K
Completion usability nor online dynamic resource adequacy. It made zero real Provider calls,
read no credential, constructed no real model client, launched no GPU job, and produced zero
empirical rows.

## Frozen Scope

v26.100 consumes the exact v26.99 identity chain without changing its scientific design:

- the exact 8K profile and `AgentModelConfig`;
- the prospective Thinking policy and 8K Thinking binding;
- all 24 TaskPackages and 48 Path Audits;
- the exact 8K Completion Contract and 8K-only Manifest;
- all 32 Job identities, assignments, and seed values;
- the four-Mechanism by three-Path layout;
- the 8,192-token Completion and 160,000-token rollout bounds;
- the 60,000-byte Primary and 6,144-byte Rescue ceilings;
- the bounded Rescue renderer and one global Rescue per Job;
- the response protocol, telemetry boundary, and zero-failure Gates;
- the 16K fallback registration with zero Jobs and no automatic escalation.

The 24 sources remain repeated engineering-calibration sources. Twenty-two were model-exposed in
v26.95 and two were not. No source, Compiler fixture, scripted fixture, or future v26.101 row is
eligible for Capability, Reachability, State Mapping, State Support, or release evidence.

No v26.95, v26.97, or v26.99 Job was rerun, continued, recovered, or reclassified.

## Source Replay

Before profile parsing, credential lookup, or client construction, v26.100 replayed 770 files:

| Source class | Files |
| --- | ---: |
| v26.99 transitive source bindings | 755 |
| v26.99 outputs | 11 |
| v26.100 implementation files | 4 |
| **Total** | **770** |

The eleven predecessor outputs are the ten v26.99 detail artifacts plus its report. Every detail
hash matches the v26.99 report, and the report matches its separately frozen SHA-256
`aa96c001199c1f725bc9b0f8ab8a588aa207ddda0506d9d893bd6b7754829dc3`.

The implementation binding contains:

- `src/trusted_synthesis/runtime/agent/prospective_thinking_8k_client.py`;
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_8k_completion_calibration_contracts.py`;
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_8k_completion_calibration_execution.py`;
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_8k_completion_calibration_execution_preflight.py`.

The replay identity is:

```text
finance_v26_exact_8k_runner_source_replay:23d77dfbe0261d96474d6ebd4a7bdc9d08ae4d692b3b539cfcb7ca7cf8a9c9b1
```

The online `--prepare-only` entrypoint independently replays the same 770 files and the complete
v26.99 Contract/Manifest binding before any possible client construction.

## Exact Client And Request Binding

The dedicated client accepts only the persisted profile:

```text
agent_model_config:c07d13207cba89d1e1cc3790151e2b5a32b7bf06f0ee6974f8e761fce5562b2e
prospective_thinking_model_binding:9ed92eb9c7326eaf8b083633cda2e10cbfdb454322bcffffcd0d2f5e1329ac57
```

Before each completion call, the Runner constructs a content-addressed request-body certificate.
The certificate and the HTTP client share one request-body builder. The actual canonical request
body must contain:

| Field | Frozen value |
| --- | --- |
| Provider | `deepseek` |
| Model | `deepseek-v4-flash` |
| `max_tokens` | `8192` |
| `thinking.type` | `enabled` |
| response format | `json_object` |
| fallback | forbidden |

The client rejects its ordinary uncertified `complete_json` entrypoint. The Runner must call the
certificate-bearing entrypoint, which reconstructs the canonical body and compares its hash
immediately before creating the HTTP request.

The profile retains its tracked `auto_discover_models` value, but this exact execution route makes
zero model-discovery calls. The configured exact model is already identity-bound, fallback is
forbidden, and an unjournaled discovery HTTP request would not carry the required Completion
certificates. This Runner-level exact-route closure changes neither profile bytes nor model
selection.

The client-binding audit is:

```text
finance_v26_exact_8k_client_binding_fixture:1110f24314f925f2a092a7661e5aa0518096bd87b79cdbc15f7d1dd68a1ffbe7
```

## Pre-Call Ordering

The Runner separates request preparation from Provider invocation. For every permitted call, the
order is:

1. render the actual dynamic Primary Prompt;
2. infer and certify the actual request kind from that Prompt;
3. for Rescue, render from the actual Primary and enforce the 6,144-byte absolute ceiling;
4. construct the dynamic Prompt and resource certificate;
5. construct the exact 8K canonical request-body certificate;
6. construct the Provider budget certificate;
7. authorize one invocation token for that exact prepared request;
8. invoke the scripted or real exact-route client once;
9. persist the privacy-redacted Provider artifact before Completion projection;
10. parse the public Completion and continue the Host Runtime.

A prepared request is content addressed and single-use. Reusing it, calling without it, changing
the Prompt, changing request kind, changing `max_tokens`, or invoking before all certificates
fails closed.

This ordering repairs the v26.96 root cause. Unlike v26.95, v26.100 never invokes a Rescue and then
checks its contract. The relative 10% reduction Gate is absent. Only the frozen absolute Rescue
ceiling applies.

## Resource Closure

The Provider budget Contract is:

```text
provider_token_budget_contract:6a9c9af8289e372a25af7f052e66e118a78f6282d618856174dc7597b67a80ad
```

It freezes:

| Quantity | Value |
| --- | ---: |
| Rollout ceiling | 160,000 tokens |
| Prompt ceiling | 60,000 UTF-8 bytes |
| Completion ceiling | 8,192 tokens |
| Provider chat envelope | 256 tokens |
| Completion Rescue reserve | 8,192 tokens |
| Final-answer reserve | 8,192 tokens |

The dynamic Completion certificate additionally retains the v26.97 64-token static request
margin. It uses actual cumulative Provider Usage before the request, the actual request Prompt,
the 8,192-token Completion bound, and the applicable future Completion reserves. The Provider
budget certificate independently checks the same actual Prompt against the 160,000-token ceiling.

The reserve policy preserves the prior distinction between a current request upper bound and
future Completion reserves. It does not claim online path completion in advance. If a later
request cannot fit, the Runner emits one typed no-call terminal before invocation. The separately
frozen exact-denominator Gate still requires zero typed no-call Jobs, so a pre-call denial cannot
be hidden by semantic success.

## Persistence And Recovery

Each HTTP-success or transport-attempt artifact is persisted before public Completion projection.
It contains only:

- the public Prompt and its hash;
- dynamic Completion certificate;
- exact 8K request-body certificate and canonical body hash;
- Provider budget certificate identity;
- public parsed payload when available;
- privacy-redacted response telemetry;
- typed failure artifact when available.

The client captures response model, finish reason, public content hash and length, explicit
Provider-native-tool presence, reasoning presence and length, and Usage before strict envelope or
content parsing. It never persists private reasoning content, a private reasoning hash, a raw HTTP
body, or a raw request body.

Recovery remains raw-only. A complete Raw Execution is reparsed and returned with zero Provider
calls. Any Provider artifact without a complete Raw Execution is an orphan and blocks automatic
retry pending a fresh Recovery Contract.

## Scripted Runner Qualification

All 32 exact v26.99 Jobs were executed against their preserved Compiler trajectories with a local
scripted client:

| Direct fixture quantity | Result |
| --- | ---: |
| Jobs | 32 |
| Logical requests | 224 |
| Scripted Provider calls | 224 |
| Public Observations | 192 |
| Dynamic pre-call certificates | 224 |
| Exact 8K request certificates | 224 |
| Verifier v2 Replay passes | 32/32 |
| Independent-valid fixtures | 32/32 |
| Mechanism-success fixtures | 32/32 |
| Mechanism x Path cells | 12/12 |

Every direct Primary Prompt matched its v26.94 registered hash through the v26.99 lineage. The
complete aggregate contains 32 Raw Executions plus 224 Provider artifacts, all 256 canonical
files. Its execution report passes and reaches the prospective pass transition
`thinking_role_protocol_freeze_only`.

These are implementation fixtures. They are not model outcomes and contribute zero empirical
rows.

## Rescue And Failure Controls

Each frozen Completion failure type was injected once and recovered with exactly one bounded
Rescue:

| Failure | Provider calls | Rescue bytes |
| --- | ---: | ---: |
| `empty_final_content` | 6 | 3,596 |
| `invalid_json` | 6 | 3,589 |
| `invalid_response_contract` | 6 | 3,602 |
| `length_truncated_content` | 6 | 3,601 |
| `reasoning_only_length_truncation` | 6 | 3,609 |

Every Rescue was dynamically precertified and exact-8K request-bound before its scripted call. A
second Completion failure after the global Rescue ended `completion_unusable` without a second
Rescue. A malformed response envelope ended `instrument_failure` with zero Rescue.

The interpretation controls reproduced:

```text
length or reasoning-only Completion failure -> fresh_16k_completion_preflight_only
non-length Completion failure              -> completion_contract_root_cause_audit_only
telemetry-only failure                      -> thinking_response_telemetry_wrapper_repair_only
fully passing execution denominator        -> thinking_role_protocol_freeze_only
```

The 16K branch is never selected or executed automatically.

## Off-Compiler Root-Cause Control

The historical v26.96 root-cause state was replayed directly:

| Quantity | Value |
| --- | ---: |
| Actual Primary Prompt | 7,914 bytes |
| Historical v26.95 Rescue | 7,176 bytes |
| v26.100 bounded Rescue | 3,888 bytes |
| Provider calls before all certificates | 0 |
| Scripted calls after all certificates | 1 |

The bounded Rescue passed actual-kind, actual-Primary, absolute Rescue, dynamic resource, exact
profile, and exact request-body checks before the single scripted call. This fixture exercises the
off-Compiler public state that invalidated v26.95 rather than only replaying registered Compiler
states.

## Budget And Recovery Controls

The preflight also verified:

- a complete Raw Execution recovers byte-identically with zero Provider calls;
- an orphan Provider artifact blocks automatic execution;
- a 60,001-byte Primary is denied before the scripted delegate;
- insufficient remaining rollout budget is denied before the scripted delegate;
- a declared final-answer kind on an actual decision Prompt is rejected before the delegate;
- a prepared request cannot be invoked twice;
- no failure control constructs a real model client.

The audit identity is:

```text
finance_v26_exact_8k_precall_recovery_fixture:c19f049a861dad6e2d5d3e653c1e1d337f0a495bdf0e62eff6eb8a44f1d41f94
```

## Destructive Controls

All 25 mutations failed closed. They cover:

- changed replay bytes;
- 4K or 16K Completion substitution;
- 240K rollout substitution;
- the historical 7,176-byte Rescue ceiling;
- a second Rescue, Provider Plan call, model-discovery call, or transient retry;
- automatic 16K escalation;
- Provider invocation before certificate closure;
- removal of request-body, request-kind, or Rescue certificates;
- disabling raw-only recovery or permitting orphan retry;
- private reasoning or raw HTTP body persistence;
- duplicate Job identity;
- a derived 16K model configuration;
- request `max_tokens=16384` or disabled Thinking;
- zero-failure threshold relaxation;
- semantic rescue of Completion or Budget failure.

The destructive audit is:

```text
finance_v26_exact_8k_runner_destructive:f8e3aaaa6650a9000ef8db6960e8502c332d45a4eae75e7b29f6630dfe5629a5
```

## Determinism And Validation

Formal and independent builds reproduced all nine outputs byte for byte. Each build replayed 770
files, ran all 32 direct Jobs, all five Rescue types, Rescue exhaustion, telemetry failure,
off-Compiler, budget, orphan, and recovery controls, and rejected all 25 mutations. Both made zero
real API calls and used zero GPU jobs.

Validation at initial artifact freeze:

```text
Ruff focused checks: passed
Ruff format for all four new implementation files and focused tests: passed
Focused Mypy: 4 source files checked, no issues
v26.100 focused regression: 8 passed in 13.79 seconds
formal/independent artifact comparison: 9/9 byte-identical
v26.101 --prepare-only: 770/770 replayed, 32 expected Jobs, no client or Provider call
```

Adjacent and repository-wide validation are rerun from integrated `main`, whose canonical package
root contains the Git-ignored immutable historical artifacts required by legacy tests. Those
results are recorded in `docs/current_project_status.md` and the final validation commit; they do
not alter the nine source-bound scientific outputs.

## Interpretation

v26.100 establishes:

- exact profile and actual request `max_tokens=8192` closure;
- dynamic request-kind, Primary, Rescue, and resource closure before every permitted call;
- a bounded off-Compiler Rescue for the exact historical root-cause state;
- one global Rescue, raw-first persistence, raw-only recovery, and orphan rejection;
- complete scripted direct, Rescue, exhaustion, telemetry, budget, and recovery controls;
- an exact v26.101 execution identity and Runner;
- zero real Provider, GPU, and empirical exposure.

It does not establish:

- empirical 8K Completion usability;
- online dynamic resource adequacy;
- empirical typed-no-call or Completion failure rates;
- Program closure or semantic validity under the model;
- 16K usability or permission for automatic fallback;
- Capability, Reachability, State Mapping, State Support, or release evidence;
- a Thinking-enabled role protocol;
- production Contribution.

## Next Stage

Only the exact v26.101 32-Job engineering calibration may execute. It must use this v26.100
preflight, Contract, exact client, profile, Manifest, Jobs, Prompts, Rescue renderer, certificates,
recovery rules, and persistence schemas. The Runner must complete `--prepare-only` against the
authoritative preflight immediately before any credential lookup.

The authoritative execution Contract is:

```text
finance_v26_exact_8k_execution_contract:bd01f5da28c20b33d693d5c7036bd7f77732a4995829e92773b1a205aced99ce
```

Its frozen online identities are:

```text
finance_v26_101_thinking_8k_completion_calibration_execution_v1_20260822
finance_v26_101_thinking_8k_completion_calibration_execution_report_v1_20260822
```

If any complete-denominator Job has a length or reasoning-only Completion failure, only a fresh
16K Runner/preflight is permitted. A non-length Completion failure permits only a Completion
Contract root-cause audit. A typed no-call, transport failure, or Instrument failure follows its
separate frozen audit branch. A fully passing execution and Completion denominator may authorize
only a Thinking role-protocol freeze on a fresh role Population. Low Program closure or semantic
validity remains descriptive and stops Completion tuning.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and Contribution remain forbidden. Production Contribution remains zero.

## Authoritative Artifacts

- `src/trusted_synthesis/runtime/agent/prospective_thinking_8k_client.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_8k_completion_calibration_contracts.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_8k_completion_calibration_execution.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_8k_completion_calibration_execution_preflight.py`
- `artifacts/vtdo_experiment/finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822/report.json`
- `artifacts/vtdo_experiment/finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822/outcome_interpretation_contract.json`
- `artifacts/vtdo_experiment/finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822/provider_token_budget_contract.json`
- `artifacts/vtdo_experiment/finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822/execution_contract.json`
- `artifacts/vtdo_experiment/finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822/client_request_binding_audit.json`
- `artifacts/vtdo_experiment/finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822/runner_fixture_audit.json`
- `artifacts/vtdo_experiment/finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822/precall_recovery_audit.json`
- `artifacts/vtdo_experiment/finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822/destructive_preflight_audit.json`
