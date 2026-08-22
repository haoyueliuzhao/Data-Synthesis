# Finance v26.101-v26.102 Thinking 8K Completion Calibration Execution And Audit

Date: 2026-08-22

## Decision

Finance v26.101 executed the exact 32-Job engineering-calibration Manifest authorized by v26.100.
The exact denominator completed, but the experiment is blocked:

```text
completed Jobs                     = 32 / 32
Completion-unusable Jobs           = 28 / 32
Instrument failures                = 1 / 32
independently valid trajectories   = 3 / 32
typed no-call Jobs                 = 0 / 32
Provider transport failures        = 0 / 32
status                             = blocked
```

The 8K Completion Usability Gate failed with 28 failures. The separately frozen typed-no-call
Gate passed with zero failures. One additional Instrument failure prevents execution-integrity
admission even though exact request binding, dynamic pre-call binding, empirical budget adequacy,
and response-telemetry integrity otherwise passed.

Finance v26.102 then independently replayed the complete execution without a credential, model
client, Provider call, or GPU job. It localized the Instrument failure to one HTTP-success
response for which every request surface was exactly bound to 8,192 tokens but the Provider
reported 8,193 Completion and reasoning tokens.

The observed root cause is:

```text
provider_reported_completion_usage_one_token_over_exact_request_bound
```

This identifies the observable contract breach. It does not uniquely establish whether the
Provider generated one token beyond the request bound or whether its Usage accounting includes a
one-token convention outside that bound. Historical files remain unchanged and the Instrument
terminal is not reclassified.

The authoritative v26.101 execution report is:

```text
finance_v26_exact_8k_execution_report:5eb7cc814364afa4cf15a3406d31c4ff4a4919092c6c2c5468f2bdb5bf1aeb52
```

The authoritative v26.102 audit report is:

```text
finance_v26_exact_8k_postrun_audit_report:1248ac237af69c5b3657b1c70e765dbf9eedb33ad1b4e94d6580711d4cc8de0f
```

The only permitted transition is:

```text
fresh_16k_profile_binding_and_provider_usage_contract_runner_preflight_only
```

No 16K online execution is authorized.

## Exact Execution

Immediately before credential lookup, v26.101 completed `--prepare-only` against the formal
v26.100 preflight:

```text
source files replayed       = 770 / 770
expected Jobs               = 32
model client constructed    = false
Provider calls              = 0
```

The formal output identity did not previously exist. The online process loaded the ignored
credential only into its child-process environment and then started from 0/32 with zero Raw-only
recovery Jobs and eight workers. It used the exact committed:

- v26.100 Runner and execution Contract;
- v26.99 TaskPackages, Paths, Manifest, Jobs, assignments, and seeds;
- exact 8K profile, model configuration, and Thinking binding;
- `deepseek-v4-flash`, `max_tokens=8192`, and `thinking.type=enabled` request body;
- 160,000-token rollout ceiling and 60,000-byte Prompt ceiling;
- 6,144-byte absolute Rescue ceiling and one global Rescue per Job;
- privacy-redacted pre-parse telemetry envelope;
- raw-first persistence and raw-only recovery policy.

Every Job was opened once. No v26.95, v26.97, v26.99, or v26.100 Job was rerun or reclassified.
The 16K candidate was not selected or materialized.

## Provider Accounting

The complete execution made 391 HTTP-success Provider calls:

| Quantity | Result |
| --- | ---: |
| Logical Primary requests | 362 |
| Rescue Provider calls | 29 |
| HTTP-success calls | 391 / 391 |
| Exact requested model | 391 / 391 |
| Exact selected model | 391 / 391 |
| Exact returned response model | 391 / 391 |
| Fallback use | 0 |
| Provider-native tool calls | 0 |
| Model-discovery calls | 0 |
| Provider transport failures | 0 |
| Provider-reported total tokens | 2,498,889 |
| Prompt tokens | 850,715 |
| Completion tokens | 1,648,174 |
| Reasoning tokens | 1,610,137 |
| Non-reasoning Completion tokens | 38,037 |
| Reasoning share of Completion | 97.6922% |
| Estimated cost telemetry | USD 0.53245247440000004286 |

All 391 calls retained positive Thinking presence, reasoning-content length, and reasoning-token
telemetry. Every response envelope was captured before strict content parsing. Private reasoning
content and hashes, raw HTTP bodies, and raw request bodies were never persisted.

All 391 calls have complete dynamic pre-call certificates and exact 8K request-body certificates.
The exact request model, Thinking setting, Prompt hash, request kind, and resource certificate
agree at every persisted layer.

## Completion Outcome

Twenty-eight of 32 Jobs ended `completion_unusable`, an observed rate of 87.5%. The independently
reconstructed one-sided 95% Clopper-Pearson upper bound is
`0.9561545559073756`, far above the frozen 0.10 requirement.

The 58 typed Completion-failure responses are:

| Failure | Calls |
| --- | ---: |
| `reasoning_only_length_truncation` | 42 |
| `length_truncated_content` | 3 |
| `invalid_response_contract` | 12 |
| `invalid_json` | 1 |

Thirty Jobs entered a Rescue attempt. Twenty-nine made exactly one Rescue Provider call. The
remaining Job became an Instrument terminal after its Primary Usage violated the strict budget
Contract, so the Runner correctly prevented its prepared Rescue from invoking the Provider.

The zero typed-no-call outcome gives the frozen one-sided 95% upper bound
`0.0893681989862648`, so empirical Budget Adequacy passed for this denominator. This positive
resource result cannot rescue Completion usability.

The 3 independently valid trajectories, 3 Program closures, 11 mechanism successes, and 12
requested-path adherences are descriptive. They cannot reclassify a Completion or Instrument
failure and contribute zero Capability, Reachability, State Mapping, State Support, or release
rows.

## Instrument Root Cause

The unique Instrument Job is the Semantic Reconciliation `structured_direct` Job:

```text
finance_v26_exact_8k_job:a417552048053969774fce4e067c739d42e45a626e7b79a07d78f2304ba8f93a
```

Its tenth Primary call had the following exact boundary:

| Field | Value |
| --- | ---: |
| Request `max_tokens` | 8,192 |
| Request-certificate bound | 8,192 |
| Dynamic Completion bound | 8,192 |
| Provider-budget certificate bound | 8,192 |
| Provider-reported Completion tokens | 8,193 |
| Provider-reported reasoning tokens | 8,193 |
| Provider-reported Prompt tokens | 2,522 |
| Provider-reported total tokens | 10,715 |
| Observed overrun | 1 token |

The request used exact `deepseek-v4-flash`, Thinking enabled, zero fallback, and all certificates
before invocation. The HTTP-success response ended `finish_reason=length`, contained no public
content, and was typed `reasoning_only_length_truncation`. Its response envelope was schema-valid
and captured before parsing.

The strict Provider budget audit correctly recorded
`resource_budget:completion_upper_bound_respected` as failed. The Runtime then rendered a bounded
Rescue but refused to prepare or invoke it because the budget state was already terminal. This
produced one historical `instrument_failure` without an unauthorized second Provider call.

The other 390 calls reported Completion Usage no larger than their exact request bound. No other
Raw Execution has a budget-contract failure. The failure is therefore not attributable to:

- a Host request override;
- a 4K/8K profile mismatch;
- missing request-kind or dynamic certificates;
- automatic 16K escalation;
- fallback or response-model mismatch;
- response-envelope telemetry loss;
- Provider transport failure;
- private-reasoning persistence.

The v26.101 Instrument terminal remains scientifically correct under its frozen strict Contract.
Even without that row, the other 28 Completion-unusable Jobs independently fail the zero-failure
Completion Gate.

## Raw Lineage

v26.102 reparsed and independently rebound:

| Artifact class | Count |
| --- | ---: |
| Final Job results | 32 |
| Checkpoint rows | 32 |
| Raw Executions | 32 |
| Raw Provider artifacts | 391 |
| Raw-Lineage descriptors | 423 |
| Canonical JSON files | 430 |
| Canonical JSONL rows | 32 |

All 391 Provider identities are unique. Every checkpoint row matches its final result, every
result binds one exact Raw file, every Raw descriptor matches its Provider bytes, and all Job,
Contract, Manifest, TaskPackage, Path, Prompt, and certificate parents close exactly.

A completed-run replay was then invoked without `DEEPSEEK_API_KEY`. It returned the same report
identity at 32/32 before client construction and made zero new Provider calls. All historical Raw,
checkpoint, aggregate, and report bytes remained unchanged.

## Independent Audit

Before diagnostics, v26.102 replayed 1,211 files:

| Source class | Files |
| --- | ---: |
| v26.100 bound source files | 770 |
| v26.100 preflight outputs | 9 |
| v26.101 execution files | 431 |
| v26.102 implementation | 1 |
| **Total** | **1,211** |

The audit independently reconstructed terminal counts, Provider Usage, cost telemetry, Completion
failure counts, Rescue counts, both Clopper-Pearson values, behavior diagnostics, privacy counts,
and the unique one-token overrun. It did not call the Runner's private aggregation functions to
derive those results.

All 20 destructive mutations failed closed. They include dropped Jobs or Provider files, hidden
overrun or Instrument failure, historical terminal reclassification, historical Job rerun,
changed exact model or request bound, disabled Thinking, private payload persistence, Usage
clipping, semantic rescue, automatic or direct 16K execution, and a prospective accounting margin
of two tokens.

Formal and independent v2 builds reproduced all eight outputs byte for byte. Each made zero
model calls and used zero GPU jobs.

The initial v1 build remains immutable and is superseded because package-wide Mypy found 17 local
Optional-narrowing diagnostics after the focused source check had passed. The v2 source validates
and caches the same five non-null Provider Usage and Thinking telemetry values as concrete
integers. Execution lineage, Provider telemetry, Completion outcome, Instrument root cause,
prospective transition, and destructive-audit files are byte-identical across v1/v2. Only source
replay and the top-level report differ because they bind the type-complete source.

The authoritative audit identities are:

- source replay:
  `finance_v26_exact_8k_postrun_source_replay:82e087de1b384329f252673ced2f4a012d9942b66b226de366cda32cc707cb7b`;
- execution lineage:
  `finance_v26_exact_8k_execution_lineage_audit:e2d19af4c165ff2a2595c3e23e0877a91a5a5c5223a6cf18961935231fa5096c`;
- Provider telemetry:
  `finance_v26_exact_8k_provider_telemetry_audit:b37e071e6e7b59b28c2d51ce96b55c96eabb2364e9d165b6793e5a78e45e8390`;
- Completion outcome:
  `finance_v26_exact_8k_completion_outcome_audit:2f7179b115963a1a778f267a4df6cd1a02cb73a8d5ac9f777a961f18758b1666`;
- Instrument root cause:
  `finance_v26_exact_8k_instrument_root_cause:1d1980d265a8a1b612f3349c87963cb26bbe2c3a9ba0815ae7e7bde3f83b41d2`;
- prospective transition:
  `finance_v26_exact_8k_postrun_transition:3024d2507dfecc814b3ca22cdf608d8191a8f6aedcf8726b4e8c9ca5a2f43604`.

## Prospective Transition

The 42 reasoning-only and 3 partial length failures activate the preregistered 16K redesign
branch. The one-token Provider Usage overrun independently requires an Instrument repair before a
future Runner can be execution-qualified. The next stage must therefore combine both static
preconditions without making a model call.

It must:

- persist an exact 16K profile with `max_tokens=16384` and Thinking enabled;
- create fresh 16K model-config and Thinking-binding identities;
- rematerialize fresh TaskPackage, Path, Contract, Manifest, Job, Runner, execution, and report
  identities so the v26.98 binding defect cannot recur;
- preserve the source tasks, Paths, assignments, seeds, Prompt and Rescue design, and outcome
  Gates rather than resampling from v26.101 outcomes;
- freeze a prospective Provider Usage semantics Contract before Runner construction;
- keep the request bound separate from Provider-reported Usage accounting;
- charge actual Provider-reported Usage against the rollout ceiling;
- treat the observed one-token margin only as an Instrument-accounting repair and never as a
  usable Completion or semantic rescue;
- reject an accounting overrun of two or more tokens;
- complete a credential-free Runner preflight before any 16K Provider call.

The prospective one-token accounting rule is transparently selected from the v26.101 Instrument
root cause. It does not change the historical strict Contract or establish a general Provider
semantic claim. A future preflight must mechanically demonstrate that the rule cannot hide a
length failure, weaken request binding, clip billed Usage, or raise the rollout ceiling.

All 32 v26.101 Jobs are permanently exposed and ineligible for rerun. Automatic escalation and
direct 16K execution remain forbidden. Capability Development, State Reachability, Fresh
Confirmation, No-C VTDO, Student training, Exact Target, GP-C, and Contribution remain forbidden.
Production Contribution remains zero.

## Validation

Validation at final v2 freeze:

```text
Ruff focused and repository-wide checks: passed
Ruff format for the new implementation and test: passed
Focused Mypy: 1 source file checked, no issues
Package-wide Mypy: 405 source files checked; one retained v26.70 diagnostic
v26.102 v2 focused regression: 8 passed in 7.61 seconds
v26.88-v26.102 adjacent regression: 120 passed in 108.48 seconds
formal/independent v2 artifact comparison: 8/8 byte-identical
v1/v2 scientific detail comparison: 6/6 byte-identical
v26.102 v2 source replay: 1,211/1,211 passed
Full Pytest: 1,141 passed, 4 expected skips, 1 retained warning in 903.56 seconds
model API calls / GPU jobs: 0 / 0
```

Repository-wide Ruff passed. Package-wide Mypy retains only the source-bound v26.70 local-list
annotation diagnostic; v26.102 adds none. These checks do not alter the eight source-bound
scientific outputs.

## Authoritative Artifacts

- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_8k_completion_calibration_execution.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_8k_completion_calibration_postrun_audit.py`
- `artifacts/vtdo_experiment/finance_v26_101_thinking_8k_completion_calibration_execution_v1_20260822/report.json`
- `artifacts/vtdo_experiment/finance_v26_101_thinking_8k_completion_calibration_execution_v1_20260822/exact_8k_job_results.json`
- `artifacts/vtdo_experiment/finance_v26_101_thinking_8k_completion_calibration_execution_v1_20260822/raw_lineage_audit.json`
- `artifacts/vtdo_experiment/finance_v26_101_thinking_8k_completion_calibration_execution_v1_20260822/raw_execution/`
- `artifacts/vtdo_experiment/finance_v26_101_thinking_8k_completion_calibration_execution_v1_20260822/raw_provider_calls/`
- `artifacts/vtdo_experiment/finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822/report.json`
- `artifacts/vtdo_experiment/finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822/execution_lineage_audit.json`
- `artifacts/vtdo_experiment/finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822/provider_telemetry_audit.json`
- `artifacts/vtdo_experiment/finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822/completion_outcome_audit.json`
- `artifacts/vtdo_experiment/finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822/instrument_root_cause_audit.json`
- `artifacts/vtdo_experiment/finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822/prospective_transition_contract.json`
- `artifacts/vtdo_experiment/finance_v26_102_thinking_8k_completion_calibration_postrun_audit_v2_20260822/destructive_audit.json`
