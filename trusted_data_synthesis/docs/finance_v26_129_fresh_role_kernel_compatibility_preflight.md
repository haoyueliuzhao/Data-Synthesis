# Finance v26.129 Fresh Role Population And Kernel Compatibility Preflight

Date: 2026-08-24

## Decision

Finance v26.129 consumed only the credential-free transition authorized by v26.128:

```text
fresh_unexposed_capability_and_reachability_population_kernel_binding_and_runner_preflight_only
```

It froze fresh, model-unexposed Capability and Reachability source Populations before loading
the engineering Kernel or any resource value. The first fixed compatibility Gate,
Context-conditioned Action, then failed under the exact frozen Kernel. Eight of twelve
diagnostic paths are incompatible. The formal status is:

```text
role_population_kernel_incompatible
```

The failure prevents role TaskPackage, Contract, Manifest, Job, and Runner materialization.
No role Provider call is authorized or attempted. The successor may only design a
scalability repair while preserving both frozen role Populations:

```text
frozen_role_population_kernel_scalability_design_only
```

This is a negative static compatibility result. It is not a Capability or Reachability model
result, does not alter the v26.128 engineering Kernel Freeze, and does not evaluate the other
three mechanisms after the first fixed Gate failed.

## Source Replay

The preflight replayed 3,154 files before source sampling:

| Source class | Files |
|---|---:|
| v26.128 transitive bindings | 3,134 |
| v26.128 immutable outputs | 9 |
| additional historical role identity inputs | 9 |
| source Evidence Snapshot | 1 |
| v26.129 implementation | 1 |
| total | 3,154 |

The nine historical identity additions are five selected v26.36-v26.42
Development/Confirmation Population files not already present in the predecessor replay and
four v26.90-v26.91 role task files. The source Snapshot itself was also not a v26.128
transitive binding and therefore received a new explicit hash binding. All expected and
observed SHA-256 values match.

The replay binds the exact v26.128 report, engineering Kernel Freeze, and transition:

- report:
  `finance_v26_transport_recovery_postrun_audit_report:e923f02843376424c783cb47a1e3f59f7704426f2b151f1432c65408e8c4731f`;
- Kernel Freeze:
  `finance_v26_engineering_kernel_freeze:eab0c2d085b78e77a487077931df58009380d279f74f93fc5aebc627bb523e77`;
- transition:
  `finance_v26_transport_recovery_postrun_transition:adb995a0efd3a04313bd325f80cef2b612492b379f762aad9c88614cc394217a`.

Credential lookup, model-client construction, Provider calls, Stage 2 Provider calls, GPU jobs,
and empirical rows were all zero.

## Historical Exclusion

The fixed historical identity census contains 29 selected task-record, task-package, and
Development/Confirmation Population files. It names 155 historical source tasks, of which 154
map back to the four immutable broad source Populations. The one unmapped source still contributes
its Evidence, Evidence Version, source-record, task, and package identities directly through its
historical task record.

The v26.29 receipt contributes 26,290 excluded Evidence identities. Historical selected role and
engineering records contribute 961 Evidence identities. Their union contains 27,173 identities,
so 78 are present in both sets. The new source sampler applies the complete union before task
construction.

The resulting 70-task source Sampling Frame contains 401 selected Evidence identities and has
zero overlap with the 27,173-item exclusion set. It contains ten tasks for each of seven Finance
families. Every family retains the source generator's fixed 3 Easy, 5 Frontier, and 2 Hard
partition.

The source Sampling Frame was frozen on 2026-08-23 before the Kernel compatibility result under:

- run ID:
  `finance_v26_129_fresh_role_kernel_binding_source_v1_20260823`;
- sampling salt:
  `finance-v26.129-fresh-role-kernel-binding-source-v1`;
- Population:
  `finance_capability_sensitive_frontier_population:24ff4419902520486d93836aa1be25be39f9b6fb208bb3d847824e967883cef1`.

## Role Separation

Role assignment is a role-neutral hash rank within each mechanism and tier. Rank zero is assigned
to Capability and rank one to Reachability. The rank projection, role allocation, and one
Easy/Frontier/Hard quota per mechanism were frozen before loading the Kernel, its resource
Contract, or any model outcome.

The two role Populations each contain twelve source tasks:

| Role | Tasks | Per mechanism | Easy | Frontier | Hard | Evidence |
|---|---:|---:|---:|---:|---:|---:|
| Capability | 12 | 3 | 4 | 4 | 4 | 75 |
| Reachability | 12 | 3 | 4 | 4 | 4 | 75 |

The eight required freshness channels pass both historical and cross-role zero-overlap checks:

| Channel | Historical | Capability | Reachability | Historical overlap | Cross-role overlap |
|---|---:|---:|---:|---:|---:|
| task ID | 464 | 12 | 12 | 0 | 0 |
| source task ID | 155 | 12 | 12 | 0 | 0 |
| Evidence ID | 27,173 | 75 | 75 | 0 | 0 |
| Evidence Version ID | 961 | 75 | 75 | 0 | 0 |
| core semantic signature | 154 | 12 | 12 | 0 | 0 |
| task signature | 285 | 12 | 12 | 0 | 0 |
| mechanism-instance signature | 154 | 12 | 12 | 0 | 0 |
| source-record ID | 961 | 75 | 75 | 0 | 0 |

The authoritative role Population identities are:

- Capability:
  `finance_v26_fresh_role_source_population:1e22847979b0927e1f772ab8b945dc4e57c2e0dc3b95f0673b1d1543470975e3`;
- Reachability:
  `finance_v26_fresh_role_source_population:cf4ff4407c4ca727c9b9c140e87261d3358c4974d92ea8605ce66bae2d316d99`.

These are source Population identities, not executable role TaskPackages. They remain
model-unexposed and must be preserved by the authorized design successor. Deleting an
incompatible task, substituting another source, or changing the tier composition is forbidden.

## Exact Kernel Binding

Only after both role Populations and the eight-channel selection audit were persisted did v26.129
load the exact engineering Kernel and its privacy-first Runner Contract. The compatibility audit
retains:

- canonical Semantic Action protocol and exact four-field Action Grammar;
- complete Candidate authority;
- exact two-field Final Grammar and Host-bound Final metadata;
- exact Thinking-enabled Flash 16K Stage 1 profile;
- zero-Provider deterministic Stage 2;
- 16,384 requested Completion tokens plus the one-token Provider accounting margin;
- 400,000 trajectory-token upper bound;
- one global ABI Rescue and one separate Semantic Recovery;
- privacy-first Envelope and Projection persistence;
- one exact Transport replacement with fresh pre-call authority;
- no failed-Transport Usage imputation and separate Provider billing and trajectory ledgers.

The exact privacy-first Runner Contract is
`finance_v26_privacy_first_runner_contract:a1d2c225906c57742340cf34c07e6d8643bbc4ef293bcf357cecd29b13221a66`.
No field or threshold was changed for the role audit.

## Compatibility Method

The canonical mechanism order begins with Context-conditioned Action. Six selected Context
sources, three per role, were materialized only as non-executable diagnostic fixtures. Capability
has one `structured_direct` path per source. Reachability has
`structured_direct`, `search_then_structured`, and `search_then_open` for each source.
This gives twelve diagnostic paths.

Each path executes the canonical Prompt-only reference policy against the same public Runtime:

1. rebuild the current Semantic Action state;
2. prove Candidate completeness and independent enumeration equality;
3. render the exact Primary Action Prompt;
4. render one exact ABI Rescue and one typed Semantic Recovery measurement at every reached state;
5. commit the selected public action through zero-Provider Stage 2;
6. execute the public tool call and continue to a Final Commit;
7. render exact Final Primary and Final Rescue Prompts;
8. apply the v26.122 conservative resource arithmetic.

For Prompts over 60,000 bytes, a measurement-only renderer reproduces the exact canonical bytes
and then proves that the production renderer rejects those bytes with the frozen ceiling error.
It does not create a callable request or weaken the ceiling.

The conservative trajectory bound is:

```text
sum(Action Primary requests)
+ Final Primary
+ max(max(Action ABI Rescue), Final Rescue)
+ max(Semantic Recovery)
```

Each request charges UTF-8 Prompt bytes, the 256-token chat envelope, the exact 16,384-token
Completion request, and the one-token accounting margin. A Transport replacement adds one
possible Provider invocation but does not impute Usage to the failed first attempt or double
charge the trajectory ledger.

## Path Results

| Role | Tier | Path | Nodes | Evidence | Primary requests | Max Prompt bytes | Static bound | Headroom | Compatible |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Capability | Easy | structured direct | 1 | 2 | 6 | 12,847 | 212,568 | 187,432 | yes |
| Capability | Frontier | structured direct | 3 | 7 | 10 | 29,365 | 434,310 | -34,310 | no |
| Capability | Hard | structured direct | 5 | 12 | 14 | 80,915 | 822,506 | -422,506 | no |
| Reachability | Easy | structured direct | 1 | 2 | 6 | 14,409 | 220,315 | 179,685 | yes |
| Reachability | Easy | search then structured | 1 | 2 | 8 | 17,478 | 293,201 | 106,799 | yes |
| Reachability | Easy | search then open | 1 | 2 | 8 | 17,464 | 293,061 | 106,939 | yes |
| Reachability | Frontier | structured direct | 3 | 7 | 10 | 29,591 | 449,028 | -49,028 | no |
| Reachability | Frontier | search then structured | 3 | 7 | 14 | 32,715 | 660,334 | -260,334 | no |
| Reachability | Frontier | search then open | 3 | 7 | 14 | 32,701 | 659,942 | -259,942 | no |
| Reachability | Hard | structured direct | 5 | 12 | 14 | 81,502 | 854,190 | -454,190 | no |
| Reachability | Hard | search then structured | 5 | 12 | 20 | 86,161 | 1,276,468 | -876,468 | no |
| Reachability | Hard | search then open | 5 | 12 | 20 | 86,101 | 1,275,580 | -875,580 | no |

The exact partition is:

```text
compatible paths              4 / 12
incompatible paths            8 / 12
Prompt-ceiling failures       4 / 12
Primary-request failures      6 / 12
Provider-call-bound failures  6 / 12
rollout-bound failures        8 / 12
```

All four Easy paths pass. Both Frontier direct paths stay within the Prompt and request limits
but exceed 400,000 tokens. The two Frontier search paths also exceed the request and Provider-call
limits. All four Hard paths exceed 400,000; all exceed the request and Provider-call limits, and
all exceed the 60,000-byte Prompt ceiling.

The 132 reached public states contain 1,130 Candidate instances. Candidate counts range from 1 to
63. The maximum Candidate list is 57,829 bytes. Maximum Action Primary, Action ABI Rescue,
Semantic Recovery, Final Primary, and Final Rescue sizes are 84,874, 84,978, 86,161, 6,311,
and 6,445 bytes. The maximum potential Provider invocation count including both response
recoveries and one Transport replacement is 23.

This is not a marginal headroom failure. The maximum static trajectory bound is 1,276,468 and
the minimum headroom is -876,468. The frozen 400,000-token contract is already insufficient for
the two Frontier direct paths, before considering the deeper Hard and search-conditioned paths.

## Fail-Fast Boundary

The fixed first mechanism Gate is sufficient to reject role Kernel compatibility. Semantic
Reconciliation, Failure Recovery, and State-dependent Stopping therefore remain
`not_evaluated_after_first_frozen_gate_failure`. They are not classified as compatible or
incompatible by v26.129.

The six operational packages used to execute the Context controls are diagnostic fixtures only.
They are not role TaskPackages and cannot enter a future Manifest. Counts for future role
TaskPackages, Contracts, Manifests, Jobs, and Runners are all zero.

The result does not support replacing Frontier or Hard sources with Easy sources. It instead
localizes a scalability mismatch between the theory-first role Population and the engineering
Kernel qualified on shallower repeated engineering tasks.

## Destructive Controls And Reproducibility

All twelve destructive mutations failed closed with zero Provider calls. They cover role
Population relabeling or merging, freshness-channel deletion, post-result Hard-task replacement,
incompatible-path deletion, Prompt/request/rollout relabeling, failed-Transport Usage imputation,
Kernel-aware source selection, and role Manifest or Provider authorization after the failed Gate.

The formal build regenerated the source Frame from the raw Snapshot. A second full independent
build repeated the same regeneration. All ten output files are byte identical. A separate
frozen-frame rebuild also reproduced every downstream file byte for byte.

Focused validation:

```text
Pytest: 2 passed in 22.76 seconds
Adjacent v26.122-v26.129 regression: 7 passed in 83.75 seconds
Ruff:   passed
Mypy:   passed
```

Both full builds and the focused test used zero credentials, zero Provider calls, zero Stage 2
Provider calls, zero GPU jobs, zero empirical rows, and zero historical reclassifications.

## Authoritative Identities

- report:
  `finance_v26_role_kernel_compatibility_preflight_report:c7195e4ba2194a136b8d7a8c27b1148d909d1b8eb76e1214a366f696c4e66f00`;
- source replay:
  `finance_v26_fresh_role_source_replay:d9c58baad57392834c01e727380d638e12b3112c4f35cc5f48aadc0254504e31`;
- historical exclusion:
  `finance_v26_historical_exposure_exclusion:05c9cf1a180f8ebc4046c1894442c5a90784909871931c300286b0555610dd9c`;
- source Sampling Frame:
  `finance_capability_sensitive_frontier_population:24ff4419902520486d93836aa1be25be39f9b6fb208bb3d847824e967883cef1`;
- Capability Population:
  `finance_v26_fresh_role_source_population:1e22847979b0927e1f772ab8b945dc4e57c2e0dc3b95f0673b1d1543470975e3`;
- Reachability Population:
  `finance_v26_fresh_role_source_population:cf4ff4407c4ca727c9b9c140e87261d3358c4974d92ea8605ce66bae2d316d99`;
- role source selection:
  `finance_v26_role_source_selection_audit:c85191ff67118440ecf67d112406f44eee33e64b4e34d77bec88c22b72cfc9a9`;
- Kernel compatibility:
  `finance_v26_kernel_compatibility_audit:df94020f8c68e83ef25aa2f24c76f8b807b0cd9f5d2e309e4db695c9ae0bfd92`;
- destructive audit:
  `finance_v26_role_kernel_destructive:e493c0cddec63766acdd126af9bf911f5584a5d23a1af85e6002712070c99cd0`;
- transition:
  `finance_v26_role_kernel_transition:c889aaaaa31fb388ab54a2207baa2cb5e3bd0302b8510f5b8f119e09b118de55`.

## Current Authorization

The only permitted transition is:

```text
frozen_role_population_kernel_scalability_design_only
```

The successor must preserve the exact Capability and Reachability source Populations and their
eight-channel separation. It may design a fresh scalability protocol for Prompt projection,
Candidate representation, interaction staging, request accounting, or resource qualification,
but it may not use model outcomes, delete or substitute frozen tasks, relax a threshold in place,
or inherit an old executable identity.

Role TaskPackage, Contract, Manifest, Job, and Runner materialization; every Provider call;
Capability or Reachability execution; State Mapping; training; release; and production
Contribution remain forbidden.
