# Finance v26.98 Thinking 8K Execution-Profile Binding Preflight

Date: 2026-08-22

## Decision

Finance v26.98 began the credential-free transition authorized by v26.97:

```text
thinking_8k_completion_calibration_runner_and_preflight_only
```

The execution preflight failed closed before Runner implementation. The v26.97 Manifest requires
an 8,192-token Completion bound, but all 24 v26.97 Completion-bound TaskPackages still bind the
4,096-token `AgentModelConfig` and its corresponding prospective Thinking binding. Because the
Completion bound participates in the content-addressed model-configuration identity, neither a
request-level override nor a newly derived 8K profile can satisfy those frozen TaskPackage
bindings.

No execution Runner or execution Contract was materialized. There was no credential lookup,
model-client construction, Provider call, GPU job, historical rerun, or empirical outcome.

The authoritative report is:

```text
finance_v26_8k_execution_binding_preflight_report:61d98194329348a5d0e6e915025276f524aec4b25a13807bed08644b34e6ebc4
```

The only permitted transition is:

```text
fresh_8k_model_profile_taskpackage_contract_manifest_rematerialization_only
```

## Why The Runner Was Not Implemented

The v26.97 audit correctly required an exact Runner to prove dynamic request-kind, Primary,
Rescue, and resource certification before every Provider call. Before implementing that Runner,
v26.98 added the prerequisite cross-artifact check that the selected Completion candidate is
actually bound by the TaskPackage model configuration used to construct a client.

That check is earlier than credential lookup and stricter than comparing a Job field with a
candidate field. A model-bearing Job is executable only when its TaskPackage, model profile,
prospective Thinking binding, Completion candidate, Contract, and Manifest form one exact
content-addressed identity chain.

The check found that the v26.97 Job and TaskPackage layers disagree:

| Layer | Frozen value |
| --- | --- |
| Selected candidate | 8,192 Completion tokens |
| 32 Manifest Jobs | 8,192 Completion tokens |
| 24 TaskPackage model configurations | 4,096 maximum output tokens |
| Exact 8K TaskPackage bindings | 0/24 |
| Jobs with a closed execution binding | 0/32 |

Implementing a Runner against this chain would either fail at client construction or silently
execute a model configuration different from the one bound by the TaskPackage. Both outcomes are
forbidden. The preflight therefore stops before creating a nominal Runner that could not execute
the exact frozen design.

## Source Replay

Before reconstructing either model identity, v26.98 replayed 746 files:

| Source class | Files |
| --- | ---: |
| v26.97 transitive source replay | 733 |
| v26.97 output files | 12 |
| v26.98 implementation source | 1 |
| **Total** | **746** |

The eleven v26.97 detail outputs were checked against the SHA-256 values bound by the
authoritative v26.97 report. The report itself was checked against the fixed SHA-256
`b9c4407710ce3e3f886c2273a51e80405aef6da3a0f3277e891de233d36a8b24` and reparsed under its
strong schema. All 733 transitive files matched their predecessor bindings. The replay passed
746/746 before profile reconstruction, without credential lookup or client construction.

The source replay identity is:

```text
finance_v26_8k_execution_binding_source_replay:ce9889497ce89bec9a48cce2b900ca931cb5e5620f747f09d8becf31b0dc34dd
```

## Exact Profile Reconstruction

The tracked Thinking profile remains:

```text
config/deepseek_v4_flash_agent_thinking_v1.json
```

Its exact frozen model values include:

| Field | Value |
| --- | --- |
| Provider | `deepseek` |
| Model | `deepseek-v4-flash` |
| Thinking type | `enabled` |
| Maximum output tokens | 4,096 |

The resulting identities are:

```text
agent_model_config:727b3867544c4eac844eb260b9673dee41be7b8787b07ea2e3d6c69113e68bd1
prospective_thinking_model_binding:51315bb03b5df2751c0cfada843fc75627c45b544d26efdd9ddac746a780f77d
```

All 24 v26.97 TaskPackages bind exactly those two identities. v26.98 then derived, in memory
only, the otherwise identical configuration with `max_output_tokens=8192`. That one-field
change produces:

```text
agent_model_config:c07d13207cba89d1e1cc3790151e2b5a32b7bf06f0ee6974f8e761fce5562b2e
prospective_thinking_model_binding:9ed92eb9c7326eaf8b083633cda2e10cbfdb454322bcffffcd0d2f5e1329ac57
```

The 8K configuration matches the selected candidate but matches zero frozen TaskPackage model
bindings. The 4K configuration matches every frozen TaskPackage but matches neither the 8K
candidate nor any 8K Job.

| Binding diagnostic | Count |
| --- | ---: |
| TaskPackages audited | 24 |
| Bound to exact 4K configuration | 24 |
| Bound to exact 8K configuration | 0 |
| Exact 8K execution binding closed | 0 |

The profile-binding audit is:

```text
finance_v26_8k_execution_profile_binding_audit:a435cff41ebcd91e07d5381c57f774bfa086457169b8092f0cc3c5b93dee6dfc
```

The derived 8K identities are diagnostics only. v26.98 did not persist a new model profile or
claim that deriving an identity rematerializes any TaskPackage.

## Job-Level Effect

The exact v26.97 Manifest was traversed in frozen order. All 32 Jobs require the initial 8K
candidate and the 160,000-token rollout ceiling. Each Job references one of the 24 TaskPackages
whose model configuration remains 4K.

| Job diagnostic | Count |
| --- | ---: |
| Manifest Jobs | 32 |
| Jobs requiring 8K Completion | 32 |
| Jobs with an exact 8K TaskPackage profile | 0 |
| Jobs blocked by profile-binding mismatch | 32 |
| Jobs authorized for a Provider call | 0 |
| 16K fallback Jobs | 0 |
| Historical Job reruns | 0 |

Every row records the exact 4,096-token difference between its Job Completion bound and its
TaskPackage model configuration. No Job was opened and no seed was consumed by a model call.

The Job audit is:

```text
finance_v26_8k_job_execution_binding_audit:7da4433af38be002acccdc0fe89b64bf8822f61ff73d515a0611c25881a333fe
```

## Root Cause

The frozen root cause is:

```text
completion_candidate_not_bound_to_taskpackage_model_config
```

Its audit identity is:

```text
finance_v26_8k_execution_binding_root_cause:4f8a9a02abfa86c7e72bf05890d3c667ab0af581daa22785ba7351fd66b0c35f
```

Three apparent shortcuts are invalid:

1. Setting the Provider request to 8K while retaining the 4K `AgentModelConfig` executes an
   unbound request surface and breaks exact-model-configuration lineage.
2. Constructing the derived 8K profile while retaining old TaskPackage identities breaks the
   TaskPackage model-config and Thinking-binding references.
3. Editing the v26.97 TaskPackages in place would mutate immutable evidence and invalidate their
   Contract, path, Manifest, and Job identities.

The failure is therefore an execution-Instrument binding failure, not evidence against 8K
Completion usability and not a model outcome.

## Relationship To v26.97

v26.98 does not invalidate the correctly scoped static findings from v26.97:

- the 8K and 16K candidate ladder remains prospectively registered;
- the 6,144-byte absolute Rescue ceiling remains unchanged;
- all 480 known dynamic states and 2,400 Rescue projections retain their local pass;
- all 48 static paths retain their published 8K and 16K budget arithmetic;
- the repeated-source engineering boundary remains unchanged;
- the zero-failure Completion and typed-no-call Gates remain unchanged.

It narrows one v26.97 interpretation: the 8K Manifest is a valid static design artifact but is
not yet an executable exact-profile Manifest. The statement that an exact Runner may be
implemented directly from the existing TaskPackages is withdrawn prospectively. Historical
v26.97 files and identities remain immutable.

No v26.95 outcome is rerun or reclassified. No v26.97 Compiler projection, dynamic-state
fixture, TaskPackage, path, or Job enters an empirical denominator.

## Prospective Rebinding Contract

The repair Contract is:

```text
finance_v26_8k_execution_binding_transition:5aa2371756e3478f862a172d83d61b21291e8cfe11c9d100db0a448ab448fd58
```

The next stage must rematerialize the complete affected identity chain:

| Required fresh object | Count |
| --- | ---: |
| Exact persisted 8K model profile | 1 |
| Prospective Thinking binding | 1 |
| Completion-bound TaskPackages | 24 |
| Static path-audit identities | 48 |
| Completion-bound Contract | 1 |
| 8K-only Manifest | 1 |
| Job identities | 32 |
| Future execution identity | 1 |
| Future report identity | 1 |

The 32 v26.97 seed values were never exposed online. The successor must preserve those values,
the exact Job assignments, source-task selection, path selection, and Mechanism x Path cell
layout. New Job identities arise from the corrected TaskPackage and Contract lineage, not from
resampling.

The following values are also frozen unchanged:

- the 8,192-token initial candidate and 160,000-token rollout ceiling;
- the separately registered 16,384-token fallback with zero executable Jobs;
- the 60,000-byte Prompt ceiling, 256-token chat envelope, and 64-token margin;
- the bounded Rescue renderer and 6,144-byte absolute ceiling;
- the one-Rescue limit and prospective interpretation tree;
- exact `thinking.type=enabled`;
- the privacy-redacted response-telemetry envelope;
- the repeated-source engineering-only eligibility boundary;
- the zero-failure execution and Completion Gates.

All 48 paths must be replayed and rebound to the new TaskPackage identities even when their
Prompt bytes and arithmetic remain unchanged. A Runner may not be implemented until this
rebinding preflight passes. Provider calls and 16K execution remain forbidden.

## Destructive Controls

All twelve identity-shortcut mutations failed closed:

- allowing the Completion candidate to override model-config identity;
- claiming that the 4K profile matches the 8K candidate;
- claiming an exact 8K TaskPackage binding;
- assigning the old model-config identity to the derived 8K profile;
- assigning the old Thinking binding to the derived 8K profile;
- authorizing a blocked Job for a Provider call;
- reusing old TaskPackage identities;
- reusing old path-audit identities;
- reusing old Contract, Manifest, or Job identities;
- materializing a Runner before rebinding passes;
- inserting 16K fallback Jobs;
- authorizing semantic evidence from the engineering calibration.

The destructive audit is:

```text
finance_v26_8k_execution_binding_destructive:9eff0a047fd723a09631bed53a1d74b71d9c27a23d04fb8d87f4eeaebd5dd0d5
```

## Determinism And Validation

Formal and independent builds reproduced all seven output files byte for byte. Both replayed
746 files, audited 24 TaskPackages and 32 Jobs, constructed no model client, made zero API calls,
and used zero GPU jobs.

Validation at artifact freeze:

```text
Ruff focused and repository-wide checks: passed
Ruff format for both new Python files: passed
Mypy focused source check: passed
Package-wide Mypy: 399 files checked; one retained v26.70 diagnostic
v26.98 focused tests: 6 passed in 2.34 seconds
```

Adjacent and full-suite validation are recorded in the project status after integration. No
historical source-bound file was reformatted or modified.

## Interpretation And Next Stage

This is a negative credential-free execution preflight with a fully localized binding root
cause. It establishes:

- exact replay of the v26.97 source and output denominator;
- distinct, reproducible 4K and derived 8K model and Thinking identities;
- 24/24 TaskPackage mismatches and 32/32 blocked Jobs;
- pre-client, pre-credential, and pre-call failure closure;
- a narrow repair transition that preserves all unexposed scientific design choices.

It does not establish:

- empirical 8K or 16K Completion usability;
- online Budget Adequacy;
- dynamic pre-call Runner correctness;
- control of Provider-private reasoning length;
- Program closure, Capability, Reachability, or State Support;
- a Thinking-enabled role protocol;
- production Contribution.

The next stage may only persist the exact 8K model profile and rematerialize the affected
TaskPackage, path, Contract, Manifest, and Job identities under a new credential-free preflight.
It may not implement or execute the Runner in the same stage, change candidates or Prompts,
resample Jobs or seeds, or create 16K Jobs.

Capability Development, State Reachability, Fresh Confirmation, No-C VTDO, Student training,
Exact Target, GP-C, and Contribution remain forbidden. Production Contribution remains zero.

## Authoritative Artifacts

- `artifacts/vtdo_experiment/finance_v26_98_thinking_8k_execution_binding_preflight_v1_20260822/report.json`
- `artifacts/vtdo_experiment/finance_v26_98_thinking_8k_execution_binding_preflight_v1_20260822/source_replay_audit.json`
- `artifacts/vtdo_experiment/finance_v26_98_thinking_8k_execution_binding_preflight_v1_20260822/execution_profile_binding_audit.json`
- `artifacts/vtdo_experiment/finance_v26_98_thinking_8k_execution_binding_preflight_v1_20260822/job_execution_binding_audit.json`
- `artifacts/vtdo_experiment/finance_v26_98_thinking_8k_execution_binding_preflight_v1_20260822/execution_binding_root_cause_audit.json`
- `artifacts/vtdo_experiment/finance_v26_98_thinking_8k_execution_binding_preflight_v1_20260822/prospective_rebinding_contract.json`
- `artifacts/vtdo_experiment/finance_v26_98_thinking_8k_execution_binding_preflight_v1_20260822/destructive_preflight_audit.json`
