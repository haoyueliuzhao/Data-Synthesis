# Finance v26.166 Bounded-Policy Capability Censoring And VTDO Admission Audit

Audit date: 2026-08-28

## Decision

Finance v26.166 consumes only the externally authorized zero-call decision:

```text
bounded_policy_capability_censoring_and_vtdo_admission_audit_only
```

The external review input is bound by SHA-256
`00363f92c449225c0f19cb34a510baf4c97b1857dd77f81ba240d7e53481fb0b`
and exact byte count 17,949. The audit reads the frozen v26.163 bounded-policy
preflight, the authoritative v26.164 v3 Raw-only recovery, and the authoritative v26.165
v2 independent postrun audit. It changes no predecessor artifact, reads no credential,
constructs no model client, and makes zero Provider or Stage 2 Provider calls.

The audit confirms that v26.164-v26.165 closed the finite-sample Route B frequency chain,
but only for outcomes under the exact bounded generation policy. It does not convert the
observed valid-only state distribution into a complete capability distribution, State
probability, Contribution estimate, or VTDO authorization.

The resulting exact Cell partition is:

```text
valid_support_absent                 10
single_valid_observation              8
observed_single_state_support         3
observed_multistate_support          27
total                                48
```

The 27 multistate Cells pass only the first VTDO admission tier, state-support existence.
No Cell currently passes frequency estimability, Contribution estimability,
materialization feasibility, or Student visibility.

## Frozen Inputs

The source replay binds 25 direct predecessor artifacts:

```text
v26.163 bounded-policy preflight inputs       4
v26.164 authoritative recovery outputs       13
v26.165 authoritative postrun outputs         8
```

It also binds the two exact v26.166 implementation files. The audited parent denominator
remains 360 complete bounded-policy endpoints, 106 Qualified Assignments, and 48 independently
confirmed Cell reports. The v26.163 Population, Policy, Tasks, Conditions, Jobs, Raw rows,
Provider artifacts, endpoint projections, Assignments, States, Routes, and frequency reports
remain byte-immutable.

The audit does not reopen the failed online directory or use an outcome to change a Cell,
threshold, Policy, task, or rollout count. It treats v26.165 as the independent confirmation
of the complete Route B denominator and uses the detailed v26.164 recovered measurement rows
only to recover the already frozen task-Verifier fields needed by the censoring profile.

## Terminal Schema Matrix

The online Host completed all 360 Raw rows before the two legacy-null typed semantic rejections
exposed a projection-type mismatch during aggregation. The historical execution and recovery
remain unchanged. v26.166 adds a prospective credential-free terminal-by-endpoint schema matrix
for future Runner preflights.

The matrix covers eight cases:

```text
completed endpoint
model-result failure
typed semantic rejection
policy Horizon
Measurement Support exit
Instrument endpoint
Privacy endpoint
Transport endpoint
```

Each case validates the exact null or explicit-false policy for task completion, Base validity,
Mechanism endpoint qualification, Qualified validity, State Mapping eligibility, and task-
Verifier invocation count. All eight controls close locally with zero calls. Future online
Runners must exercise this matrix before Provider execution; the matrix does not rewrite a
historical Raw terminal namespace.

## Cell Support Strata

The Cell audit joins the 48 independently reproduced v26.165 frequency reports to their exact
pre-treatment Task-condition Cells and freezes four mutually exclusive types.

`valid_support_absent` means `N_qualified=0` and zero observed States. A zero State is never
imputed. `single_valid_observation` means exactly one Qualified row and one observed State; its
empirical `pi=1` is not interpreted as population degeneracy. `observed_single_state_support`
means at least two Qualified rows but only one observed State. `observed_multistate_support`
means at least two Qualified rows and at least two observed States.

The three observed-single-state Cells are exactly:

```text
context_conditioned_action | frontier     | structured_direct  3/6, 1 State
state_dependent_stopping    | easy_control | structured_direct  3/6, 1 State
state_dependent_stopping    | easy_control | unconditional      6/12, 1 State
```

The ten support-absent Cells are all Hard-tier Cells:

```text
context_conditioned_action | hard_control | unconditional
context_conditioned_action | hard_control | structured_direct
context_conditioned_action | hard_control | search_then_structured
context_conditioned_action | hard_control | search_then_open

semantic_reconciliation    | hard_control | unconditional
semantic_reconciliation    | hard_control | structured_direct
semantic_reconciliation    | hard_control | search_then_structured
semantic_reconciliation    | hard_control | search_then_open

failure_recovery           | hard_control | structured_direct
state_dependent_stopping   | hard_control | structured_direct
```

These are results for four specific Hard tasks, their exact conditions, and the Route B policy.
Each Mechanism x Tier source Cell contains one primary task, so repeated rollouts do not establish
a general zero capability for a Mechanism or Tier.

## Capability Survival Profile

The audit constructs one typed row for every frozen endpoint and locates the first authorized
blocker along this ordered diagnostic DAG:

```text
Action Entry
Program Closure
Operation Lineage
Evidence Support
Terminal Verification
Final ABI
Answer Semantics
Reference Identity
Citation
Mechanism Qualification
Policy Horizon
```

For task-Verifier-evaluable rows, the stages are computed from the frozen first-action interface,
the fourteen Base checks, and the Mechanism event report. Evidence Support requires required-
Evidence, Runtime-selected support, and verification support. Terminal Verification also requires
no postcompletion violation. Final ABI includes the Final ABI and answer-schema checks. The
artifact-bound noninterference check remains separately retained and is passing on every
task-Verifier-evaluable row.

The first-blocker partition is:

```text
Action Entry                         22
Program Closure                     124
Operation Lineage                    54
Evidence Support                     37
Terminal Verification                 0
Final ABI                            13
Answer Semantics                      1
Reference Identity                    0
Citation                              2
Mechanism Qualification               0
Policy Horizon                        1
no blocker, Qualified survivor       106
total                                360
```

This is a deterministic localization profile, not an exclusive causal attribution. Later failed
checks remain present in each row. The one policy Horizon is not assigned to Program Closure:
after its passing Action Entry, the capability suffix is treated as censored by the frozen
generation horizon and its first authorized blocker is `policy_horizon`.

No invalid or policy-censored trajectory is mapped to a VTDO State. Historical reclassification,
new Assignment, State, Route, and Mapper invocation counts are zero.

## Typed Rejection Boundary

The two typed semantic rejections remain complete Route B failure endpoints. Their endpoint
projection has explicit false Base, Mechanism, Qualified, and Mapping fields, which is sufficient
for `q` and `pi`. That explicit Mechanism value is not a task-/Mechanism-Verifier result.

v26.166 therefore freezes, separately for both rows:

```text
mechanism_endpoint_qualification = false
mechanism_event_evaluable        = false
task_verifier_invoked            = false
legacy_mechanism_report_success  = null
```

It makes no claim that the target mechanism did not occur. The frozen aggregate count of 226
Mechanism-qualified endpoints must not be interpreted as an unconditional mechanism occurrence
rate because three endpoints have no evaluable Mechanism event report.

## VTDO Admission

The audit freezes five prospective empirical admission tiers:

```text
state-support existence
frequency estimability
Contribution estimability
materialization feasibility
Student visibility
```

Only the 27 `observed_multistate_support` Cells pass state-support existence. They were identified
from this Development denominator and have only six conditioned or twelve Unconditional
rollouts per Cell. They do not establish stable State frequency, causal Contribution, an anchored
Novelty/Energy update, fresh materialization feasibility, or Student visibility. Their current
highest passed tier is therefore exactly `state_support_existence`; all later tiers are false.

The formal sets are finite-sample diagnostics:

```text
C_absent     10 Cells
C_weak       11 Cells
C_candidate  27 Cells
```

`C_candidate` is not a selected VTDO Arm. Current VTDO-admitted Cell count is zero.

## Coverage Gaps

The Coverage Gap Registry contains the ten support-absent and eleven weak-support Cells. Every
row records that current VTDO coverage is unavailable, no State or frequency is imputed, and no
Compiler-assisted intervention occurred. If a later design combines VTDO and Compiler-assisted
coverage, a shared fixed Coverage Anchor or a separately authorized factorial design is required;
low-support supplementation cannot be added only to a VTDO Arm.

Compiler-Assisted Capability Coverage remains a separate research route. It may study compiled
demonstrations, public subgoals, scaffolded action selection, failure-recovery fragments, or
Operation-level supervision, but none of those interventions is part of the current frequency
result or v26.166 audit.

## Engineering Diagnostic

Artifact-backed Usage remains 28,539,733 Provider tokens for 106 Qualified trajectories. The
exact cross-Cell quotient is:

```text
269242.76415094339622641509433962264150943396226415
```

This is bookkeeping across heterogeneous Cells. It is not a preregistered estimand and cannot
allocate Cell budgets. In particular, a global quotient obscures the ten Cells that produced no
Qualified trajectory.

The joint valid-state yield `rho_c(z)=N_c,z/N_c` is not materialized or authorized as a training
or production decision quantity in this audit.

## Fresh Confirmation

The prospective confirmation protocol requires admission rules to be frozen before outcome
loading and requires either fresh model-unexposed tasks or a genuinely independent confirmation
denominator. Selection must be stratified prospectively by Mechanism, Tier, and generation
condition. The 27 current multistate Cells may inform the protocol but may not define its sampling
frame, be selectively continued, or establish a VTDO effect on the same data.

v26.166 creates no fresh Population, TaskPackage, Manifest, Job, Runner, Raw row, Assignment, or
State. It authorizes only a credential-free successor preflight. Provider execution, current-
denominator reuse, Contribution estimation, VTDO execution, Compiler intervention, training,
release, and production remain forbidden.

## Reproducibility

The final focused suite passes 4/4 in 4.34 seconds, including a complete empty-directory build
and byte comparison of all twelve formal files. The adjacent v26.164-v26.166 regression passes
19/19 in 77.62 seconds. Focused PyCompile, Ruff check/format, and Mypy pass. Package-wide Ruff
passes. Package-wide Mypy checks 517 source files and retains only four pre-existing diagnostics
in v26.70, v26.129, and v26.154, with zero v26.166 diagnostics. All v26.166 outputs are
content-addressed and the build reads no credential or model client.

Package-wide Mypy then exposed one local heterogeneous-dictionary inference in the v26.166
source. The type-complete source adds only the explicit annotation and rematerializes the formal
directory. Cell strata, Survival, terminal schema, typed rejection, admission, Coverage Gap,
token diagnostic, and confirmation-protocol identities remain exact; only implementation-bound
source replay, transition, and top-level report identities change.

The authoritative identities are:

- report:
  `finance_v26_bounded_policy_capability_censoring_audit_report:a1659a2e63fc264a34d18c5039e89f592f46900595ab0609aef4cbca6bff5297`;
- report SHA-256:
  `d6ef05e26a5dbaf418842b57be6a4dfd4e5cd56f4af59bb2a4dd9d16c39317c5`;
- source replay:
  `finance_v26_bounded_policy_censoring_source_replay:876cade14c6e4535357eca4275b8e06a64078cb296775d26d35a5e05e03b914f`;
- Cell support strata:
  `finance_v26_bounded_policy_cell_support_stratum_catalog:2358ddfa65070b30a8da4b9c1278d49ec639f288c2f7f4e45e10c0bff6b8c1c8`;
- Capability Survival Profile:
  `finance_v26_bounded_policy_capability_survival_profile:84215be0d688eccc6c64e090e19fbcdd97418306c7271979fe1685a962fb7e6f`;
- terminal Endpoint schema audit:
  `finance_v26_terminal_endpoint_schema_audit:20f68f84242ab88d33d9360a6c794e96130f77f83baadda1f8eaefc0f892197f`;
- typed rejection boundary:
  `finance_v26_typed_semantic_rejection_boundary_audit:5f81801d9fb45600f97ec003e5ac3de2bba05ae63e63a3369999191b4734c434`;
- VTDO admission Catalog:
  `finance_v26_vtdo_admission_catalog:82c33f687d24dbbaeb53d6fbf020478b8b30c8139f20cc837f3513b594ee4e12`;
- Coverage Gap Registry:
  `finance_v26_coverage_gap_registry:a1e956867760938b0d96a69ae08a3d69d3dcdc5eb62da517cb143757d590a0cb`;
- engineering token diagnostic:
  `finance_v26_cross_cell_token_per_qualified_diagnostic:a237ed4b2b4cde4da0c210167728b123b1a570a98fce3fdef6d4cd41cf9eb429`;
- fresh confirmation protocol:
  `finance_v26_fresh_vtdo_admission_confirmation_protocol:907cd028562a48f04927565b0c9c32e9944332a817698d1f5baa97512c972be2`;
- transition:
  `finance_v26_bounded_policy_censoring_transition:ea7582fa05f236f1cc106f18b00406d28e2e93cec6375773549a2ba2a4ba454b`.

The only permitted transition is:

```text
fresh_vtdo_admission_confirmation_preflight_only
```

The successor may perform only a credential-free, pre-outcome preflight for a fresh independent
confirmation Population stratified by Mechanism, Tier, and generation condition. It must preserve
all v26.163-v26.166 artifacts and may not use the observed current 27 Cells as an outcome-selected
sampling frame. Provider calls, current-denominator reuse, Compiler intervention, historical
reclassification, State probability, Contribution, VTDO execution, Student visibility, training,
release, and production remain forbidden.

## v26.167 Prospective Supersession

A later external joint theory, code, and task-synthesis audit retains every v26.166 historical
artifact and result but finds the prospective `FreshConfirmationProtocol` insufficient for
execution. In particular, it lacks a capability-family index, matched groups, independent
`ObservationDepth`, D0 observability anchors, constructive DepthDelta, nuisance invariance,
Development/Confirmation group counts, Role depth preservation, and group-wide exposure rules.
The v26.166 transition above is therefore historical and was not consumed.

v26.167 consumes the external replacement decision
`capability_breadth_depth_task_synthesis_and_static_audit_only`. It freezes sixteen fresh matched
groups and 64 D0-D3 static tasks with zero Provider calls, while keeping all current 27
multistate Cells outside the selection frame. It also retains the 21 historical Coverage Gap
rows but assigns every future follow-up `unassigned`; no Compiler candidate or intervention is
authorized.
