# Finance v26 Prospective Thinking-Mode Policy

Policy date: 2026-08-21

## Decision

All newly materialized Provider model calls after this policy must request thinking with the
exact OpenAI-compatible request-body fragment:

```json
{
  "thinking": {
    "type": "enabled"
  }
}
```

Missing, disabled, differently cased, or structurally extended `thinking` values fail before
credential lookup and before client construction. The policy applies to future Provider calls;
deterministic local fixtures and credential-free historical replay do not make Provider calls and
are outside its empirical denominator.

The content-addressed policy identity is
`prospective_thinking_mode_policy:b9ba7be1e8ee2ab343e31fe57b3c50cbbd604abf26b3da4297f5ad76dfbb158f`.

## Historical Isolation

No historical Contract, Manifest, Job, Raw Execution, Provider response, trajectory, score, or
report is changed. In particular, the v26.83 Contract explicitly requested
`thinking.type=disabled`, and all 241 unique v26.86 Provider calls recorded no reasoning content
or reasoning-token telemetry. Those facts remain authoritative for that experiment.

This policy does not reclassify the v26.84-v26.86 result, rescue any no-call or model-invalid row,
or permit a historical Job to be rerun. Historical non-thinking outcomes and future thinking
outcomes belong to different generation kernels and may not be pooled without a prospectively
frozen comparison design.

## Enforcement

The future-only implementation is
`src/trusted_synthesis/runtime/agent/prospective_thinking.py`.

- `enable_prospective_thinking` creates a new `AgentModelConfig` identity while preserving other
  model settings.
- `require_prospective_thinking` rejects absent or non-exact request configuration.
- `bind_prospective_thinking` creates a content-addressed policy/config binding for inclusion in
  future experiment Contracts.
- `ThinkingRequiredOpenAICompatibleJsonClient` performs that binding before the underlying client
  reads its credential environment variable.

The prospective Flash profile is
`config/deepseek_v4_flash_agent_thinking_v1.json`. Its identities are:

```text
model_config_id = agent_model_config:727b3867544c4eac844eb260b9673dee41be7b8787b07ea2e3d6c69113e68bd1
binding_id = prospective_thinking_model_binding:51315bb03b5df2751c0cfada843fc75627c45b544d26efdd9ddac746a780f77d
```

Future empirical Contracts must bind both the policy identity and the exact model-config identity.
Future Runners must use the strict client entry point rather than constructing the historical
general-purpose client directly.

## Telemetry And Privacy Boundary

The request configuration is the evidence that thinking was requested. Response-side
`reasoning_content_present`, `reasoning_content_length`, and `reasoning_tokens` are independent
Provider telemetry and must be reported rather than assumed.

Private reasoning content is not persisted or inserted into Prompts, task artifacts, State
Mapping, validity scoring, or release counts. Only its presence, length, and Provider-reported
token count are retained. A response with no reasoning telemetry does not authorize silently
changing the request policy; it is an observed Provider response requiring explicit audit.

## Budget Semantics

Thinking does not relax the v26.89 Budget Adequacy Contract:

- the completion upper bound remains 4,096 tokens;
- reasoning tokens are part of completion Usage;
- completion Usage remains part of the 120,000-token rollout total;
- the 60,000-byte Prompt ceiling and both 4,096-token reserves remain unchanged;
- a response that consumes its completion allowance in reasoning without final JSON remains a
  typed model failure;
- a certified pre-call denial remains a resource terminal in the role denominator.

Consequently, enabling thinking is not evidence that the v26.86 budget-adequacy failure is fixed.
Fresh tasks must still pass full-path static accounting, and a later independently authorized
calibration must still satisfy the frozen no-call confidence gate.

## Validation And Authorization

The focused test set covers policy identity, historical-to-prospective config migration, malformed
and disabled request rejection, rejection before credential lookup, exact request-body emission,
redacted reasoning telemetry, and the concrete Flash profile. It passes 10/10 tests.

This policy implementation made zero API calls and used zero GPU jobs. It is an engineering and
prospective protocol constraint, not a task-rematerialization result, budget calibration, model
comparison, Capability result, or Reachability result. The current permitted transition remains:

```text
fresh_budget_feasible_role_task_rematerialization_only
```

No empirical Contract or Job Manifest is materialized by this policy.
