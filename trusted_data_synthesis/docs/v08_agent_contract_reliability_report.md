# v0.8 Agent Contract Reliability Report

> Historical full-response protocol report. Superseded by `docs/v08_audit_remediation_report.md`.

Generated: 2026-07-27

## 1. Scope

This iteration addresses five blockers observed in the first real DeepSeek calibration:

1. exact Agent response and operation output contracts;
2. plugin-owned Legal execution guidance;
3. redacted failure telemetry for invalid model responses;
4. bounded concurrent Agent and Critic execution;
5. atomic incremental checkpoints with deterministic resume.

The framework remains domain-neutral. Core and runtime code consume public task metadata and
typed operation manifests; Legal and Science semantics are supplied by their domain plugins.

## 2. Exact Response Contract

`agent_response.v3` replaces the free-form `final_answer` dictionary with a strict envelope:

```text
final_answer
├── result
├── citations[]
├── status     optional and task-controlled
└── claims[]   optional and task-controlled
```

Before trajectory normalization, the Agent boundary now checks:

- task-specific required and allowed result fields;
- exact citation coverage of selected evidence;
- exact source ID and source locator copies;
- operation output Pydantic schemas;
- exact registered tool capability, including `null` for lookup;
- public program node, operator, parameters, and output-node binding;
- `verification_result == output execution observation.result` when verification is required.

The prompt contains only operations relevant to the current public task. It also includes a
machine-readable task execution contract, final-answer contract, and evidence identifier
contract. Raw evidence IDs remain unchanged in lineage and citations; only `input_refs` add the
`evidence:` reference prefix.

## 3. Domain Prompt Contracts

### Legal

The Legal plugin publishes exact field semantics for:

- `legal_apply_rule`;
- `legal_resolve_authority`;
- missing conditions;
- triggered exceptions;
- authority priority;
- the no-eligible-rule result.

The model may organize its rationale, but it may not invent conditions, exceptions, authority,
or legal effect strings.

### Science

The Science plugin now freezes:

- the protocol mismatch vocabulary;
- top-level mismatch names rather than nested paths;
- effect comparison reference semantics;
- plain decimal numeric fields;
- registered qualified-conclusion enums;
- the descriptive-synthesis conclusion enum.

These are plugin contracts, not Core branches.

## 4. Failure Telemetry

Every failed model call can now preserve the following redacted diagnostics:

```text
error_type
error_message
contract_errors[]
response_shape
request_hash
response_hash
token and latency telemetry
```

`response_shape` contains only object keys, types, array lengths, and shallow child shapes. It
does not persist the raw response, model credential, authorization header, or complete prompt.
Failed Agent samples retain their own telemetry, and the aggregate report counts failure types
and contract errors.

## 5. Concurrency and Checkpoints

Agent and Critic jobs use bounded thread pools controlled by `maximum_concurrency`. Results are
reordered by their deterministic job index before report construction, so concurrency cannot
change sample order or stable IDs.

Each completed job is written immediately through an atomic temporary-file replacement. Resume
requires all of the following to match:

- validation config hash;
- validation, solver, prompt, and response-schema versions;
- complete public task contract;
- operation registry manifest;
- checkpoint payload hash.

Critic checkpoints additionally bind the Critic prompt version and complete critic example. A
prompt or domain-contract change therefore invalidates stale checkpoints automatically.

## 6. First 10-Pattern Real Regression

The initial post-implementation run used `deepseek-v4-pro`, four concurrent workers, one repair
attempt, and ten distinct patterns:

| Domain | Attempted | Normalized | Normalization rate |
| --- | ---: | ---: | ---: |
| Finance | 4 | 2 | 50.00% |
| Legal | 3 | 0 | 0.00% |
| Science | 3 | 2 | 66.67% |
| Total | 10 | 4 | 40.00% |

The previous 36-sample Prompt v3 calibration normalized 25.00%, so the strict envelope and
task-specific contract improved normalization without silently repairing model semantics.

The run consumed 108,750 prompt tokens and 40,238 completion tokens. Provider prices were not
configured, so the report correctly leaves monetary cost unknown. All ten Agent checkpoints
were written.

No normalized sample passed the deterministic Quality Contract. The new telemetry and replay
localized the remaining failures:

- internal tuple parameters were compared directly with model JSON arrays;
- the `input_ref` evidence prefix was incorrectly copied into raw lineage IDs;
- reference fields used subject names or double-prefixed IDs instead of evidence IDs;
- numeric machine values included `%`, units, or rounded display text;
- Science protocol mismatch paths and conclusion text replaced registered enums.

## 7. Feedback Fixes After the Run

The identified issues were fed back into the generating components:

| Observed issue | Fix |
| --- | --- |
| tuple/list parameter mismatch | compare canonical JSON semantics |
| raw ID versus input-ref ambiguity | explicit identifier contract and examples |
| units or prose in machine outputs | generic operation field rules |
| nested Science mismatch paths | plugin-owned closed vocabulary |
| free-form Science conclusions | plugin-owned enum contract |
| stale checkpoints after prompt edits | prompt/task/registry compatibility hash |

These changes pass offline contract tests. A second real API run was requested, but the execution
environment requires renewed explicit authorization before sending the ten public fixture tasks
to `api.deepseek.com`. No post-fix real success rate is claimed yet.

## 8. Verification

Completed offline checks:

- strict envelope and final-answer schema rejection;
- exact citation and tool binding;
- verification-result equality;
- redacted response-shape telemetry;
- Legal plugin prompt contract;
- JSON array versus internal tuple parameter equivalence;
- concurrent Agent checkpoint write and zero-call resume;
- Critic checkpoint write and zero-call resume;
- stale checkpoint invalidation inputs;
- full project tests, Ruff, and MyPy.

## 9. Readiness Decision

The architecture and failure observability are ready for another small calibration, but not for
the 2,000-sample real Agent materialization. Promotion requires a post-fix run showing:

```text
normalized trajectory rate >= 80%
Legal normalized rate > 0%
deterministic contract acceptance rate >= 60%
checkpoint resume API calls = 0
unknown-cost fields explicitly reported as unknown
```

Scale should increase only after these thresholds are met.
