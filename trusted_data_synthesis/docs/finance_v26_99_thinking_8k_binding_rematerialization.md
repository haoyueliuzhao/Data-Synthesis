# Finance v26.99 Thinking 8K Binding Rematerialization

Date: 2026-08-22

## Decision

Finance v26.99 completed the only credential-free repair authorized by v26.98:

```text
fresh_8k_model_profile_taskpackage_contract_manifest_rematerialization_only
```

The stage persisted the exact 8K DeepSeek V4-Flash Thinking profile and rebuilt the affected
content-addressed identity chain in dependency order:

```text
exact 8K AgentModelConfig
-> exact prospective Thinking binding
-> 24 TaskPackages
-> 48 static Path Audits
-> Completion Contract
-> 8K-only Manifest
-> 32 Jobs
```

The resulting static chain is closed. Every TaskPackage, Path, Contract, Manifest, and Job binds
the same 8K model configuration, Thinking binding, selected candidate, profile bytes, Completion
bound, and rollout bound. Contract membership and the Path-to-Task and
Job-to-Contract/Task/Path parent references also close exactly.

This is a positive static rematerialization result. It is not an online result and does not
establish 8K Completion usability, dynamic resource adequacy, Program closure, or model
capability. No Runner was implemented, no credential was read, no model client was constructed,
and no Provider or GPU job was launched.

The authoritative report is:

```text
finance_v26_exact_8k_rematerialization_report:fb21fa81d33db5e7b4622007598bcef27d226e9804385176eb12509ac5069b3f
```

The only permitted transition is:

```text
thinking_8k_completion_calibration_runner_and_preflight_only
```

## Scope

v26.99 repairs only the execution-profile lineage found incomplete by v26.98. It does not
reconsider or resample the v26.97 design. The following remained frozen:

- all 24 source-task selections and source roles;
- all 48 path selections and Compiler state rows;
- all 32 Job assignments and seed values;
- the four-Mechanism by three-Path cell layout;
- the 8,192-token Completion and 160,000-token rollout initial candidate;
- the 16,384-token Completion and 240,000-token rollout fallback with zero Jobs;
- the 60,000-byte Prompt and 6,144-byte Rescue ceilings;
- the bounded Rescue renderer and maximum one Rescue per Job;
- the response protocol, privacy-redacted telemetry Contract, and interpretation tree;
- the separately frozen typed-no-call and Completion zero-failure Gates.

No v26.95 or v26.97 Job was rerun, continued, recovered, or reclassified. Semantic outcomes were
not loaded for selection or rematerialization. The 24 repeated sources remain engineering
calibration sources: 22 were model-exposed in v26.95 and two were not. Neither the source tasks,
Compiler fixtures, nor any future rows from this calibration can enter Capability,
Reachability, State Mapping, State Support, or release evidence.

## Source Replay

Before rematerializing an identity, v26.99 replayed 755 files:

| Source class | Files |
| --- | ---: |
| v26.98 transitive source bindings | 746 |
| v26.98 output files | 7 |
| v26.99 implementation source | 1 |
| persisted exact 8K profile | 1 |
| **Total** | **755** |

The 746 transitive entries already cover the 733 v26.97 transitive bindings, all twelve v26.97
outputs, and the exact v26.98 implementation. The six v26.98 detail files were checked against
the hashes bound by its report, and the v26.98 report was checked against its separately frozen
SHA-256. All entries matched before profile parsing or TaskPackage construction.

The source replay made no credential lookup, client construction, Provider call, or GPU job. Its
identity is:

```text
finance_v26_exact_8k_source_replay:4cf0a43d6a1e1e7445b3f0f872c0c5dae9f4949a7bf1de15a88b1d84b2160a68
```

## Persisted Exact 8K Profile

The new tracked profile is:

```text
config/deepseek_v4_flash_agent_thinking_8k_v1.json
```

Its SHA-256 is:

```text
efef0545f4a5467956ecdbcc3442341af1b4f158558d41f0b8e607859ef7d256
```

The profile differs from the tracked 4K Thinking profile in exactly one
`AgentModelConfig` field:

| Field | v26.90-v26.98 profile | v26.99 profile |
| --- | ---: | ---: |
| `max_output_tokens` | 4,096 | 8,192 |

Provider, exact model, endpoint, Thinking request, temperature, `top_p`, retry limits, model
selection, and pricing telemetry fields are unchanged. The exact persisted values include:

| Field | Value |
| --- | --- |
| Provider | `deepseek` |
| Model | `deepseek-v4-flash` |
| Thinking type | `enabled` |
| Maximum output tokens | 8,192 |
| Initial rollout ceiling | 160,000 |

The content-addressed identities are:

```text
agent_model_config:c07d13207cba89d1e1cc3790151e2b5a32b7bf06f0ee6974f8e761fce5562b2e
prospective_thinking_model_binding:9ed92eb9c7326eaf8b083633cda2e10cbfdb454322bcffffcd0d2f5e1329ac57
```

The profile binding also fixes the initial candidate identity. It does not construct a client.
Its audit identity is:

```text
finance_v26_exact_8k_profile_binding:b7922047d9630556d5dc154568d39a79468a7effbdcc8adb87e0d4376b60c292
```

## TaskPackage Rematerialization

All 24 v26.97 TaskPackages were traversed without task selection. Each successor preserves the
same repair TaskPackage, role TaskPackage, source task, source role, mechanism, operational
record and package, Environment, Semantic Source, compact Prompt Contract, Completion-bound
protocol, selected candidate, and source-exposure classification.

Each successor additionally binds the exact persisted 8K profile and the frozen response
surfaces:

- exact 8K model-configuration identity;
- exact 8K prospective Thinking binding;
- prospective Thinking policy identity;
- response Completion protocol identity;
- Completion-bound protocol and selected candidate identities;
- response-telemetry repair Contract identity;
- 8,192-token Completion and 160,000-token rollout bounds;
- 6,144-byte Rescue ceiling and one-Rescue limit.

The semantic projections match 24/24. All 24 TaskPackage identities are fresh and have zero
identity overlap with v26.97. The source task identities are intentionally unchanged and are not
claimed fresh.

## Path Rebinding

All 48 Path Audits were rebound to the new TaskPackage and 8K profile identities. Their public
Compiler state rows, Prompt byte counts, Rescue byte counts, candidate budgets, and path
selection are unchanged.

| Static quantity | Preserved result |
| --- | ---: |
| Paths | 48/48 |
| Largest Primary Prompt | 8,369 bytes |
| Largest bounded Rescue | 5,702 / 6,144 bytes |
| 8K full-path bounds | 76,817 to 151,653 tokens |
| Minimum 8K rollout headroom | 8,347 tokens |
| 16K fallback full-path bounds | 125,969 to 233,573 tokens |
| Minimum fallback headroom | 6,427 tokens |

These are the same conservative static calculations as v26.97. They are not expected Usage or
online dynamic-resource evidence. All 48 Path identities are fresh because their TaskPackage and
profile lineage changed.

## Contract, Manifest, And Jobs

The new Completion Contract is:

```text
finance_v26_exact_8k_completion_contract:2f752e61533e3a358d7e9ab02c4cb825b9c32ee9340a1310e5f533b53656365d
```

It binds all 24 TaskPackage identities, all 48 Path identities, the exact profile bytes and
model/Thinking identities, both candidate identities, the dynamic Rescue coverage audit, the
response protocol and telemetry Contract, and all frozen resource and outcome rules.

The new 8K-only Manifest is:

```text
finance_v26_exact_8k_manifest:e50b85b55d76fe3f9e74b24cfde98d40d2c4a1f1608a85fcead6eebe6bd1c118
```

It contains 32 fresh Job identities and zero 16K Jobs. Every Job binds its new Contract,
TaskPackage, and Path identity plus the exact 8K profile, model configuration, Thinking binding,
candidate, Completion bound, rollout bound, and unchanged seed.

| Layout | Jobs |
| --- | ---: |
| Context-conditioned Action | 8 |
| Semantic Reconciliation | 8 |
| Failure Recovery | 8 |
| State-dependent Stopping | 8 |
| `structured_direct` | 12 |
| `search_then_structured` | 8 |
| `search_then_open` | 12 |

All twelve Mechanism x Path cells retain two or three Jobs. The Manifest covers 24 distinct
TaskPackages. All 32 seed values and all 32 ordered Job assignments match v26.97 exactly; only
the corrected parent lineage changes their Job identities.

The frozen future run identities are:

```text
finance_v26_100_thinking_8k_completion_calibration_runner_preflight_v1_20260822
finance_v26_101_thinking_8k_completion_calibration_execution_v1_20260822
finance_v26_101_thinking_8k_completion_calibration_execution_report_v1_20260822
```

The first identity is for the next credential-free Runner preflight. The latter two remain
prospective and cannot be opened by v26.99.

## Unified Cross-Artifact Gate

v26.99 persists one independently reparsable 104-row binding audit:

| Bound artifact | Passing rows |
| --- | ---: |
| TaskPackage | 24 |
| Path Audit | 48 |
| Job | 32 |
| **Total** | **104** |

Every row records the selected candidate, profile SHA-256, model-configuration identity,
Thinking-binding identity, Completion bound, and rollout bound. Path rows also bind their
TaskPackage parent. Job rows bind their Contract, TaskPackage, and Path parents.

The aggregate independently verifies:

- Contract TaskPackage membership equals the exact 24 TaskPackage row identities;
- Contract Path membership equals the exact 48 Path row identities;
- every Path references one known TaskPackage;
- the Manifest references the exact Contract;
- every Job references one known TaskPackage and one known Path;
- every Job TaskPackage equals its Path TaskPackage;
- the Manifest Job order equals the exact 32 Job row identities;
- candidate, profile, model, Thinking, Completion, and rollout values agree at every layer.

The actual client configuration and request `max_tokens` cannot be observed without a Runner.
They are explicitly deferred to the next Runner preflight, which must bind
`agent_model_config:c07d...62b2e` and 8,192 tokens before credential lookup and client
construction.

The cross-artifact audit is:

```text
finance_v26_exact_8k_cross_artifact_binding:8be2fa5e586165f19a2b9f740bf3efac39e71bb1031ca732769631533ea40c3c
```

## Design Preservation And Freshness

The preservation audit compares content projections rather than labels:

| Check | Result |
| --- | ---: |
| TaskPackage semantic projections | 24/24 |
| Path Prompt and budget projections | 48/48 |
| Ordered Job seed and assignment projections | 32/32 |
| Source-task selection changes | 0 |
| Path-selection changes | 0 |
| Job-assignment changes | 0 |
| Seed changes | 0 |
| Mechanism x Path layout changes | 0 |
| Prompt or Rescue changes | 0 |
| Response-telemetry changes | 0 |

The preservation audit identity is:

```text
finance_v26_exact_8k_design_preservation:deb46e48c8875d2730380d08dc61507f4724d5a4faadf2a7bd07c49021720e72
```

Freshness applies to the corrected identity chain, not to the repeated sources:

| Fresh identity class | Count |
| --- | ---: |
| TaskPackages | 24 |
| Path Audits | 48 |
| Jobs | 32 |
| Contract | 1 |
| Manifest | 1 |

Overlap with the corresponding v26.97 identities is zero. The v26.97 future execution identity
is not reused. The 22 model-exposed and two model-unexposed source-task partition remains
unchanged. The freshness audit is:

```text
finance_v26_exact_8k_freshness:41b4ea1cb1538544755f88e9adfb334ec625fa8806a6f1f00c75e79f755748e5
```

## Destructive Controls

All 25 mutations failed closed. They cover:

- restoring the 4K profile bound, model identity, or Thinking binding;
- restoring 4K Completion at the profile, Task, or Path layer, or changing Contract rollout;
- changing the selected candidate, Job seed, or Job mechanism assignment;
- reusing predecessor TaskPackage or Path identities;
- inserting a 16K fallback Job;
- materializing a Runner or Provider call;
- mismatching a Contract TaskPackage membership set;
- mismatching a Path-to-Task parent after recomputing the Path identity;
- mismatching a Job-to-Path parent after recomputing Job and Manifest identities;
- mismatching the Manifest-to-Contract parent after recomputing the Manifest identity;
- changing one TaskPackage profile hash after recomputing its identity.

The last five controls exercise the unified cross-artifact Gate after the changed child or parent
has a valid content-addressed identity. Rejection therefore does not rely only on detecting a
stale hash.

The destructive audit is:

```text
finance_v26_exact_8k_destructive:bbcc1c3e5b4028ab8be9674cdde7c1d3496470f049513375139bcf3895f465b4
```

## Determinism And Validation

Formal and independent builds reproduced all eleven JSON outputs byte for byte. Each replayed
755 files, rematerialized the exact 24/48/32 identity chain, rejected all 25 mutations,
constructed no client, made zero API calls, and used zero GPU jobs.

Validation at artifact freeze:

```text
Ruff focused and repository-wide checks: passed
Ruff format for both new Python files: passed
Mypy focused source check: passed
Package-wide Mypy: 400 files checked; one retained v26.70 diagnostic
v26.99 focused tests on integrated main: 8 passed in 2.35 seconds
v26.88-v26.99 adjacent Thinking/Budget tests: 104 passed
formal/independent artifact comparison: 11/11 byte-identical
Full Pytest: 1,125 passed, 4 expected skips, 1 retained warning in 863.73 seconds
```

The repository-wide formatter would rewrite 118 historical baseline files under the currently
installed Ruff version. Those unrelated files were not reformatted. No historical source-bound
file was modified.

## Interpretation

v26.99 establishes:

- a persisted exact 8K model profile with reproducible model and Thinking identities;
- 24 fresh exact-8K-bound TaskPackages and 48 fresh Path identities;
- a fresh Contract, 8K-only Manifest, and 32 fresh Jobs;
- exact preservation of source, path, assignment, seed, Prompt, Rescue, telemetry, and Gate
  choices;
- closure of the static execution identity chain through Job lineage;
- zero Runner, credential, Provider, GPU, and empirical exposure.

It does not establish:

- empirical 8K or 16K Completion usability;
- online or off-Compiler dynamic resource adequacy;
- actual client or request binding;
- Provider-private reasoning control;
- Program closure or semantic validity;
- Capability, Reachability, State Mapping, State Support, or release evidence;
- a Thinking-enabled role protocol;
- production Contribution.

The v26.98 root cause is repaired at the static identity layer. The 8K design is now eligible for
Runner implementation and credential-free Runner preflight, but the Manifest remains
non-executable until that separate preflight proves actual request-kind, Primary, Rescue,
resource, client-profile, recovery, and persistence behavior before every Provider call.

## Next Stage

The next stage may only implement the exact Runner for this v26.99 Contract and Manifest and
complete a credential-free preflight. It must replay all v26.99 bindings before credential
lookup, bind the exact persisted 8K profile during client construction, and verify actual request
`max_tokens=8192` before invocation. It must preserve raw-only recovery, privacy-redacted
pre-parse telemetry, one global Rescue, the 6,144-byte Rescue ceiling, all resource certificates,
and the frozen interpretation tree.

No Provider call is authorized by v26.99. The 16K fallback cannot be materialized or selected
automatically. If a later complete 8K denominator has any length or reasoning-only Completion
failure, only a fresh 16K Runner/preflight is permitted. A non-length Completion failure permits
only a Completion-Contract root-cause audit. A fully passing execution and Completion denominator
may authorize only a Thinking role-protocol freeze. Low Program closure or semantic validity must
remain descriptive and stop Completion tuning.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and Contribution remain forbidden. Production Contribution remains zero.

## Authoritative Artifacts

- `config/deepseek_v4_flash_agent_thinking_8k_v1.json`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_thinking_8k_binding_rematerialization.py`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/report.json`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/exact_8k_profile_binding.json`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/exact_8k_task_packages.json`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/exact_8k_path_audits.json`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/exact_8k_completion_contract.json`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/exact_8k_job_manifest.json`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/design_preservation_audit.json`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/cross_artifact_binding_audit.json`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/freshness_audit.json`
- `artifacts/vtdo_experiment/finance_v26_99_thinking_8k_binding_rematerialization_v1_20260822/destructive_preflight_audit.json`
