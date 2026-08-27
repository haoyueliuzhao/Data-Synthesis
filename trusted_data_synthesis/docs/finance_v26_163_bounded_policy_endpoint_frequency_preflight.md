# Finance v26.163 Route B Bounded-Policy Endpoint Frequency Preflight

Date: 2026-08-27

## Decision Summary

Finance v26.163 consumed only:

```text
fresh_bounded_policy_endpoint_frequency_preflight_only
```

It implements the operator-selected Route B as a prospective, fully specified bounded generation
policy. Reaching the frozen policy horizon now creates a complete observable
`policy_horizon_exhausted` endpoint under the new policy identity. That endpoint is
task-incomplete, Base-invalid, Qualified-invalid, and mapping-ineligible. It is neither a
Measurement Support exit nor a model semantic error.

The stage selected a fresh model-unexposed twelve-task Population before loading Path,
compatibility, policy, resource, Mapper, or outcome values. It then materialized fresh
TaskPackage, Path, strong Cell, generation-policy, Assignment, estimand, execution, Manifest,
outcome, Runner, prospective execution, and report identities. The exact Manifest contains:

```text
fresh tasks                              12
conditioned Paths                       36
strong Task-condition Cells             48
fresh Jobs                             360
  Unconditional                        144
  Path-conditioned                     216
formal Assignments at preflight          0
formal frequency reports at preflight    0
real Provider calls                       0
Stage 2 Provider calls                    0
```

All credential-free controls pass. This is a preflight and defines no empirical frequency,
State probability, VTDO update, training evidence, release decision, or production Contribution.

## Review Reconciliation

The supplied v26.161 audit required an independent postrun audit followed by a prospective choice
between broader Measurement Support and a complete bounded policy. v26.162 completed the audit,
and the user selected Route B. v26.163 addresses each prospective correction:

| Audit requirement | v26.163 implementation | Decision |
| --- | --- | --- |
| Do not repair v26.161 | Historical Raw, formal projection, terminal, and null reports remain immutable | Passed |
| Use a new estimand | Fresh bounded-policy generation and estimand IDs | Passed |
| Make the horizon observable | `policy_horizon_exhausted` is a complete policy endpoint | Passed |
| Do not call the horizon a model error | Explicitly false in Policy and Outcome Contracts | Passed |
| Do not call the horizon a Support exit | Exact second-Detour fixture retains Support availability | Passed |
| Separate Instrument, Support, Resource, and endpoint | Orthogonal projection schema and fixture | Passed |
| Freeze a Gate before execution | Global integrity plus fixed per-Cell endpoint Gate | Passed |
| Report success support and conditional State frequency | `q_c` and `pi_c` frozen separately | Passed |
| Define uncertainty | 95% Wilson for `q`; marginal 95% Wilson for each `pi(z)` | Passed |
| Define zero-Qualified behavior | `q=0` with interval; `pi=null`; no State imputation | Passed |
| Define non-degeneracy | At least two Qualified rows and two observed States | Passed |
| Avoid stable-population overclaim | Only bounded-policy empirical frequencies authorized prospectively | Passed |
| Use a fresh Population | Twelve first-exposure tasks with eight-channel zero overlap | Passed |
| Re-preflight exact Runner | 360 Jobs and 4,158 local calls close with zero real calls | Passed |

The one-Detour numerical limit remains one. It is not relaxed to two after observing v26.161.
Its scientific role changes prospectively: exhaustion is part of the new generation policy's
outcome language.

## Preliminary Zero-Call Candidates

Several preliminary source candidates failed closed before formal output:

1. Reusing the v26.150 70-task frame after excluding all four prior role Populations left no
   eligible Context-conditioned Action Hard source.
2. Combining the frozen v26.129 and v26.150 frames found Context Hard rows, but every such row
   had prior model exposure under one of the four excluded Populations.
3. Regenerating a new clean frame from the migrated checkout failed because its bound v25.44
   stopping snapshot is absent there.
4. The exact original snapshot was then located at its historical `/data1` path and verified by
   byte count and SHA-256 before source construction.

The rejected candidates created no formal Population, TaskPackage, Path, Policy, Manifest, Job,
Raw row, Assignment, or report and made zero Provider calls. The authoritative directory was
materialized from empty after the exact source snapshot became available.

## Snapshot Recovery Boundary

The migrated checkout still does not contain the bound v25.44 snapshot. v26.163 therefore
preserves:

```text
historical_snapshot_limitation_preserved = true
v26_158_full_transitive_rebuild_claimed   = false
```

The original source artifact is available at:

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/
vtdo_experiment/finance_v25_44_hardened_stopping_evidence_snapshot_v3_20260816/
finance_stopping_evidence_snapshot.jsonl
```

Its binding is:

```text
bytes    604,998,387
SHA-256 c6ac2b985607a0f964cb919010bd9a7c9eee9ac57534983e4ab09a7b10c3f17e
```

v26.163 uses this exact externally recovered content for current-stage source construction. It
also independently reproduces the v26.129 historical exclusion registry from the original
artifact root. This is current-stage content recovery, not a claim that the migrated checkout or
the earlier v26.158/v26.160 transitive chain was always complete.

The predecessor audit independently rebuilds and byte-matches all nine direct v26.162 outputs.
It binds 27 current-stage inputs, including the recovered snapshot and eight implementation
files, and performs no credential lookup.

## Fresh Source Selection

The new source frame is generated from the exact recovered snapshot under fixed salt
`finance-v26.163-bounded-policy-source-selection-v1`. The effective exclusions contain 27,173
historical Evidence identities plus 300 Evidence identities from the four prior v26.129,
v26.150, and v26.160 role Populations, for 27,473 Evidence identities.

The clean frame contains 70 tasks before and after exclusion and has zero overlap with the
registry. A role-neutral fixed-salt rank selects one task in every Mechanism x Tier cell:

```text
frame tasks before exclusion              70
frame tasks after exclusion               70
prior selected source tasks               48
selected source tasks                     12
selected Evidence identities              75
model outcomes used for selection          0
compatibility values used for selection    0
```

Selected overlap is zero on all eight channels:

| Freshness channel | Excluded | Selected | Overlap |
| --- | ---: | ---: | ---: |
| task ID | 512 | 12 | 0 |
| source-task ID | 203 | 12 | 0 |
| Evidence ID | 27,473 | 75 | 0 |
| Evidence Version ID | 1,261 | 75 | 0 |
| core semantic signature | 202 | 12 | 0 |
| task signature | 333 | 12 | 0 |
| mechanism-instance signature | 202 | 12 | 0 |
| source-record ID | 1,261 | 75 | 0 |

Selection is persisted before loading Policy, Mapper, Path, resource, compatibility, Verifier, or
outcome data.

## Route B Generation Policy

The new policy is
`bounded_policy_endpoint_generation_policy:481664d9ed21cb7f610754ff290021b7fb6ce5451ff57600b572224bff60bbe2`.
It freezes:

```text
maximum Primary requests                  21
maximum Stage 1 Provider calls             23
maximum transport-inclusive invocations   24
maximum rollout tokens              1,120,000
maximum Ordinary Detours                    1
```

Its declared horizon reasons are Ordinary-Detour, Primary-request, Provider-call,
transport-invocation, and rollout-token limits. A reached horizon has:

```text
policy endpoint observed       true
task completion                false
Base validity                  false
Qualified validity             false
State Mapping eligibility      false
Measurement Support exit       false
model semantic error           false
```

This policy claims no unrestricted natural-agent distribution. Every later frequency must remain
conditioned on this exact policy, Kernel, Verifier, Mapper, TaskPackage, and experimental
Condition.

## Orthogonal Endpoint Projection

The future Runner projects Raw Instrument, Measurement Support, Resource, Provider response and
identity, Thinking/Usage, Privacy, Transport, model/policy endpoint, task completion, Base
validity, Mechanism qualification, Qualified validity, and mapping eligibility as separate
fields.

The exact second-Detour fixture starts from the old local shape
`measurement_support_exit/ordinary_detour_allowance_exhausted` and projects it prospectively
as:

```text
policy terminal                       policy_horizon_exhausted
policy reason                         ordinary_detour_limit
policy endpoint observed              true
Measurement Support available         true
Raw Instrument integrity              true
resource-accounting integrity         true
task completion                       false
Base validity                         false
Qualified validity                    false
State Mapping eligible                false
task-Verifier calls                   0
later Provider calls                  0
```

The one-Detour fixture still closes as a Qualified-valid completed endpoint. Neither fixture
changes a historical Raw row.

## Gate And Frequency Contract

The global integrity Gate requires:

```text
360/360 complete Raw
360/360 bounded-policy endpoints
zero Raw Instrument failures
zero Resource-accounting failures
zero Privacy failures
zero Provider identity / Thinking / Usage failures
zero unresolved Transport failures
zero unsupported Measurement Support exits
```

Each Unconditional Cell must independently contain its exact twelve endpoints, and each
Path-conditioned Cell its exact six endpoints. Outcome-dependent Cell selection, Path pooling,
conditioned-to-Unconditional pooling, and empirical Route conditioning are forbidden.

For each complete Cell `c`, the contract freezes:

```text
N_c+              = sum_r 1[V_qualified(c,r) = true]
N_c,z             = sum_r 1[V_qualified(c,r) = true and Z(c,r) = z]
q_hat_c           = N_c+ / N_total_c
pi_hat_c(z)       = N_c,z / N_c+       when N_c+ > 0
```

`q_c` is bounded-policy Qualified-success support. `pi_c(z)` is the State frequency
conditional on Qualified success under the same bounded policy. They are never substituted for
one another.

The uncertainty and low-support rules are:

- `q_hat_c` receives a two-sided 95% Wilson score interval;
- each emitted `pi_hat_c(z)` receives a marginal two-sided 95% Wilson interval;
- no simultaneous multinomial coverage is claimed;
- a complete Cell with zero Qualified rows emits `q=0` with its interval and `pi=null`;
- an incomplete Cell emits both `q` and `pi` as null;
- a failed global integrity Gate makes every Cell null;
- one Qualified row permits an empirical `pi` but no stable-population claim;
- empirical non-degeneracy requires at least two Qualified rows and at least two observed States;
- zero vectors and synthetic States are forbidden.

The API fixture passes failed-global-Gate, incomplete-Cell, zero-Qualified, one-Qualified, and
multi-State cases. It produces three `q` Wilson and three marginal `pi` Wilson controls, zero
imputed States, and zero simultaneous-coverage or stable-population claims.

## Support And Resource Qualification

Across the 36 fresh Paths, the complete Support closure reaches:

```text
unique typed states                         756
Candidate events                          2,581
failed Observations                          90
successful no-progress Observations         482
Ordinary Detour candidates                  362
typed Support exits                           0
Host exceptions                               0
```

Failed and progress Observations make zero Baseline calls. Every successful no-progress event
invokes Baseline exactly once.

The 362 Detour candidates split into 159 ordinary-replan-closed rows and 203 class-external
diagnostics. The 159 closed rows cover all 36 Paths. Their global maxima are:

```text
Primary requests                            21
Provider calls with recovery reserves       23
transport-inclusive invocations             24
maximum Prompt bytes                    53,015
conservative tokens                  1,074,977
headroom under 1.12M                     45,023
```

The unchanged resource shape contains all reference Paths and all qualified one-Detour rows:

```text
Prompt ceiling                           60,000 bytes
reference maximum Prompt                 52,816 bytes
reference maximum path bound          1,021,830 tokens
one-Detour maximum                    1,074,977 tokens
rollout ceiling                       1,120,000 tokens
```

No observed Usage average or post-outcome threshold relaxation is used.

## Mapper And Runner Preflight

The exact six Tool schemas equal the environment, reachable Candidate, and reference Commit Tool
sets. The five temporal Gold pairs pass, all six within-Cell State pairs have difference
witnesses, and Production and independent Reference Mapper match one valid-only local fixture in
each of the 48 strong Cells.

The exact scripted Runner closes:

```text
Jobs                                      360
local calls                             4,158
Action payloads                        3,798
Support decisions                      3,798
public Observations                    3,438
qualified Final payloads                 360
joint task-Verifier calls                360
Qualified-valid fixture outcomes         360
Raw recovery passes                      360
real Provider calls                        0
Stage 2 Provider calls                     0
formal State Mapping rows                  0
```

The endpoint, frequency API, Runner, Raw recovery, privacy, resource, Mapper, and independent
Reference Mapper controls all pass. All 26 destructive mutations fail closed, including horizon
reclassification, second-Detour admission, later Provider invocation after horizon, Route
conditioning, zero-State imputation, historical reclassification, Job deletion, seed reuse,
early mapping, early VTDO, and Stage 2 Provider routing.

## Authoritative Identities

- report:
  `finance_v26_bounded_policy_preflight_report:93af17282d46c1114f3d568978b92ae63b017680d952b1b19890e2fe83e9ec06`;
- report SHA-256:
  `78e91be467f17388c64a2bc6ed573a98fe13eecc328611db2392beacb0607f7d`;
- predecessor replay:
  `finance_v26_bounded_policy_predecessor_replay:3b2e254ed316eaae157d75bd8521aa9ae14e98aec8837692591e9c4c99112e35`;
- fresh Source Population:
  `finance_v26_frequency_source_population:3443b578cf293dda451ff822a681abc6dbb502c24fcafac00b9cdab77ff49bc4`;
- source selection:
  `finance_v26_bounded_policy_source_selection:2d522be3ae43eca15d7631433de4bbb505667edea3ef9ef1b20c495b67497c5f`;
- TaskPackage catalog:
  `finance_v26_fresh_reachability_task_catalog:468343551326133e89f1576ede569d58b5835247dab084dbe1c8ca8316d42509`;
- Path catalog:
  `finance_v26_fresh_reachability_path_catalog:d47d6115019ee9184947825391114f25692926d409fd61d114caf6a6ed4d92f0`;
- bounded generation policy:
  `bounded_policy_endpoint_generation_policy:481664d9ed21cb7f610754ff290021b7fb6ce5451ff57600b572224bff60bbe2`;
- resource Contract:
  `finance_v26_fresh_reachability_resource_contract:64507d067b2842c93da2d622b18d7b27973bf23396968994dda6e50fe06ef0e5`;
- Mapper-v2 Contract:
  `valid_only_state_mapper_contract_v2:af984e1acc450f34fed741dd88790322e84db3098f0aad4c8329fb70a1311982`;
- strong Cell Catalog:
  `mapper_v2_task_condition_cell_catalog:d0d306a6c550cc6cf37ab4f670e7f05adb3c4091f6015164f16a9856cf8fb8da`;
- estimand Contract:
  `finance_v26_bounded_policy_estimand_contract:ad923ed5024db84733618f50218baeae39705b12ccffc002478cd623172bb221`;
- execution Contract:
  `finance_v26_frequency_execution_contract:014e22dca706d22b102eb69195de37a9362c5cf06138fe98e3d4250c8f7fa950`;
- Manifest:
  `finance_v26_frequency_manifest:5d4d25a257b1e5cb4de613f79bc97f8c2c346642a93883e47b98b49e9941933d`;
- outcome Contract:
  `finance_v26_bounded_policy_outcome_contract:8b4f38bfe2a2af4060f076afb4b06eea81431c3fdff7f55532c64fe509bcaf57`;
- Runner Contract:
  `finance_v26_bounded_policy_runner_contract:f79d0d54670b5c13024a353f5ddf38d69f554988e6c50f8139c4d3717cb5d8e7`;
- Runner preflight:
  `finance_v26_bounded_policy_runner_preflight:57375ecb6d8c841ed60906f7b8c8afb55d41c039ddef18f040647e03cd95376b`;
- transition:
  `finance_v26_bounded_policy_transition:bb2fd59f49bbbf2ff5aa8e89b5499fe07cc8011823b9f7317b7d7868d10c155c`.

The frozen prospective execution and report identities are:

```text
finance_v26_bounded_policy_frequency_execution:
a05757fbceccb300af43c867c65d220fdb75a5734af33d1966fe1b24bc96e05e

finance_v26_bounded_policy_frequency_execution_report:
d80e3536f4acb40aa30238aa662b2e79287c1680917211314e499ae8ddd330c0
```

## Verification And Current Transition

The new focused tests pass 4/4 across the fast and byte-rebuild invocations. The complete
independent build test passes 1/1 in 1,205.12 seconds and reproduces all 34 v26.163 files byte
for byte. The fast v26.160-v26.163 adjacent regression passes 10/10 in 4.56 seconds. Focused and
package-wide Ruff pass. Focused Mypy passes; package-wide Mypy checks 509 source files and retains
only the four pre-existing v26.70/v26.129/v26.154 diagnostics, with zero v26.162 or v26.163
diagnostics. The stage performs zero real Provider calls, Stage 2 Provider calls, GPU jobs,
formal Assignments, and frequency reports.

The only permitted transition is:

```text
fresh_bounded_policy_endpoint_frequency_execution_only
```

The successor may execute only the exact fresh 360-Job Manifest under every frozen v26.163
source, TaskPackage, Path, strong Cell, bounded generation policy, Tool, Support, resource,
Mapper, Assignment, estimand, Verifier, outcome, and Runner identity. Source reselection; Policy,
Condition, Tool, Support, resource, Mapper, model/Thinking, recovery, Detour, Grammar, or Verifier
change; historical rerun or reclassification; post-hoc Job deletion; outcome-dependent Cell
selection; current-denominator frequency; State probability; VTDO; training; release; and
production Contribution remain forbidden.
