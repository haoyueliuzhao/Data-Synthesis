# Finance v26.179 Job-Bound Multistep Outcome And Runner Preflight

Audit date: 2026-08-30

## Decision And Scope

Finance v26.179 consumed only:

```text
capability_observation_job_bound_multistep_outcome_contract_
and_192_job_runner_preflight_only
```

The bound external review is exactly 19,996 bytes with SHA-256
`fac64d597640109f965cfd4acea6ffa25a6891909113d62053bd570debb10601`.
It audits exact commit `b8a728e3e3342abc1ec8d2002c738cfdbcfddc21`.

This stage materializes one prospective 192-Job Development Manifest and one
credential-free Runner Contract. It executes only scripted local Runtime controls.
Credential lookup, Provider-client construction, Stage 1 and Stage 2 Provider calls,
Development model outcomes, sealed Confirmation payload access, GPU jobs, Mapper calls,
State Assignments, frequency rows, Contribution, VTDO, Student visibility, training,
release, and production counts are zero.

The v26.178 decision
`no_further_experiment_authorized_without_new_audit_decision` is not silently bypassed.
The new external review is content-addressed as the required new decision. It authorizes
only this preflight, not online Development execution.

## Frozen v26.178 Boundary

All fourteen authoritative v26.178 files remain immutable. Before constructing a
v26.179 object, the stage rebuilds v26.178 in an empty temporary directory and matches
all fourteen files byte for byte.

The new review narrows two v26.178 descriptions without changing any historical object:

```text
old Outcome interpretation
  -> outcome payload fixture and denominator-geometry closure

old exact-Catalog scan interpretation
  -> complete reference-prefix component/candidate acceptance scan
```

The frozen v26.178 surface remains:

```text
reference-prefix State x Replica rows                 480
displayed Candidate reports                         1,356
local CapabilityOutcomeRow fixtures                     5
exact future Job identities                             0
empirical Outcome rows                                  0
multi-Component correction rows                         0
historical rewrites / reclassifications             0 / 0
```

No v26.178 mechanism result is relabeled false. The narrower statement only prevents
five fixture rows and a numeric `32 x 6` declaration from being mistaken for an exact
empirical denominator.

## Frozen Generation Profile

The generation profile is extracted from the exact v26.167 Development Group Catalog,
whose file bytes are bound directly. All eight Development nuisance signatures contain
one identical generation configuration. The compiled Action and Final Grammars match
their frozen identities.

```text
source nuisance signatures                              8
unique generation configurations                        1
fixed Development generation conditions                 1
Action Grammar compile matches                        true
Final Grammar compile matches                         true
model / Thinking / Grammar changes                 0 / 0 / 0
Policy / resource changes                               0
```

The profile retains:

```text
prompt contract
  capability_observation_prompt_contract:
  ddf543dbd56f119c89a5dc84e9ee8118f120af4b8ec86c858d3a9c778b68a84e

Action Grammar
  prospective_semantic_action_response_grammar:
  bbda30254855071bc024f6217cea4eec57512eaa50c8e5e0f7755c6e92d07e82

Final Grammar
  prospective_qualified_final_response_grammar:
  2370b603f1243c500e19ef0b45e6bdfa32434a7b4242b0c884ee977dd169d3fc

model configuration
  agent_model_config:
  05eb110b4269f3a569d24918f356cb905d871aace45b9024c4575295b05a1015

Thinking binding
  prospective_thinking_model_binding:
  5afdd81c4318c89d5c31f9398e77b28822eb338578c2bc3533ed77d6291d33c8

bounded generation Policy
  bounded_policy_endpoint_generation_policy:
  481664d9ed21cb7f610754ff290021b7fb6ce5451ff57600b572224bff60bbe2

resource Contract
  finance_v26_fresh_reachability_resource_contract:
  64507d067b2842c93da2d622b18d7b27973bf23396968994dda6e50fe06ef0e5
```

The domain-specific current-State Decision kind remains visible and unchanged. For the
already frozen four-field Action ABI, the Runner projection uses
`decision_kind=execute_public_operation`, because every selected target Choice is
committed through the production public-operation step. This is an explicit projection
inside the Runner prompt binding, not a rewrite of the domain State or Grammar.

## Exact 192-Job Manifest

The Manifest contains exactly one Job for each authoritative v26.176 Runner Package x
Replica pair:

```text
authoritative Runner Packages                           32
Replicas per Package                                     6
prospective Jobs                                       192
unique Job IDs                                         192
unique Raw namespaces                                  192
unique Result namespaces                               192
Package x Replica cells                                192
Packages with exact Replica set {0,1,2,3,4,5}           32
missing / duplicate / extra Jobs                   0 / 0 / 0
```

Each Job binds at least:

```text
Runner Package identity
execution Package identity
authoritative Development Package artifact
v26.171 source Package artifact
source Package and Group
Finance Core
capability family and depth
fixed generation condition
Replica index
ordered State-local Schedule IDs
frozen generation profile
v26.179 Outcome Contract
v26.177 Public Feedback Contract
v26.177 production rejection Surface
prospective Raw and Result namespaces
deterministic seed identity
```

Jobs do not contain `manifest_id`, avoiding a circular content address. Every future
Outcome row must bind both its exact `job_id` and the independently content-addressed
`manifest_id`.

## Multistep Outcome Contract

The old fixture-only `CapabilityOutcomeRow` remains unchanged. v26.179 adds a new object
chain:

```text
ComponentAttemptOutcome
  -> ordered JobBoundOutcomePayload
  -> ScriptedPreflightOutcomeRow or EmpiricalCapabilityOutcomeRow
```

Each Component attempt binds the reached State token, first-response ABI status, Action
acceptance evaluability, selected Action, State-precondition result, rejection code,
Observation receipt, correction Feedback, correction ABI and Action disposition, terminal
reason, and commit status. Attempt indices must be contiguous, Component keys unique, and
a terminal attempt must be last.

The Job payload derives rather than trusts:

```text
reached Component count
committed Component count
correction count
ordered correction Feedback IDs
first uncommitted Component
first-policy Qualified validity
bounded-policy endpoint and Qualified validity
Final ABI and Verifier fields
```

The correction bound remains one correction per reached Component. Different Components
may each use that bound, so a D2 or D3 Job can contain multiple corrections without losing
lineage.

ABI invalidity is orthogonal to Action acceptance and Verifier validity:

```text
first response ABI invalid
  -> Action acceptance not evaluable
  -> Action accepted = false
  -> State-precondition value = null
  -> no correction Feedback
  -> task Verifier not invoked
  -> Base / Mechanism / Qualified = null
  -> bounded-policy Qualified = false
```

An ABI-valid stale or foreign Action reference is separately represented as
Action-reference-invalid with Action acceptance not evaluable. It is not conflated with
a typed current-State precondition rejection.

## Estimands And Exact Denominator Gate

The two prospective Job-level estimands are now unambiguous:

```text
q_first
  = complete Jobs that are Qualified with zero Component corrections
    / exact Manifest Job count

q_bounded_correction
  = complete Jobs that are Qualified under one correction per reached Component
    / exact Manifest Job count
```

A first Action is not a complete first-policy Job outcome. Per-Component first responses
remain in the attempt trace and can later support reached-Component conditional summaries,
but they do not replace the Job-level estimand.

The empirical estimator accepts only `EmpiricalCapabilityOutcomeRow`. It rejects fixture
and scripted rows at runtime, requires 192 unique row IDs and Job IDs, checks exact Job-ID
set equality against the Manifest, and verifies every Package, Replica, namespace, and
source-artifact parent. Length equality alone is insufficient.

The formal v26.179 build invokes that empirical estimator zero times. Test-only synthetic
wrappers exercise its constructibility and duplicate/missing rejection paths; they are not
formal empirical rows and are not persisted.

## One-Current-Prompt Runner

The Runner receives only one exact source Task, current Runtime State, current Prompt,
current presentation mapping, and prior public observations/Feedback already reached by
production execution. It does not receive a reference Trace, complete baseline, saved
Replica Result, precommitted Choice vector, future Prompt, or sealed Confirmation payload.

Every Action fixture passes through the frozen exact four-field parser before production
`step()`. Every completed local trajectory passes through the frozen qualified Final parser
and production `finalize()`. The Final payloads are scripted Grammar controls built after
the local trace; they are not model responses, answer-quality evidence, or Development
outcomes.

The exact Manifest reference control executes:

```text
scripted Outcome rows                                  192
unique Job / row IDs                              192 / 192
exact Job-set matches                                  192
current Prompt renders                                 480
Action ABI parses                                      480
accepted production Actions                            480
Final ABI parses                                       192
production Runtime finalizations                       192
component corrections                                    0
first-policy Qualified controls                        192
bounded-policy Qualified controls                      192
empirical Outcome rows / estimates                   0 / 0
Provider calls / Development model outcomes          0 / 0
```

The `192/192` values are deterministic reference-path preflight controls. They are not an
empirical Capability estimate, model success rate, depth boundary, or monotonicity result.

## Complete Accepted-Prefix Surface

To close the narrow scope of the v26.178 reference-prefix scan, v26.179 executes every
declared source-Choice vector under all six Replicas. A trajectory stops when its selected
Action typed-rejects; every State reached through an accepted predecessor prefix is audited.

```text
declared Package Choice combinations                    772
local Replica trajectory executions                   4,632
reached accepted-prefix States                       14,388
Candidate acceptance evaluations                     41,124
accepted selected Actions                             13,308
typed-rejected Candidate evaluations                  3,240
Package x Component x Replica summary rows               480
rows with exactly one acceptance signature               480
history-dependent acceptance rows                          0
Runtime exceptions                                          0
```

This is complete for the frozen declared Choice surface and accepted predecessor prefixes.
It is not a theorem about arbitrary future tasks, mutated Candidates, or unregistered
histories.

## Executed Branch Controls

Eleven scripted controls are projected from actual Runtime traces:

```text
direct first-attempt Qualified                            exact
ABI-invalid first response                               exact
accepted first Action, downstream task invalid           exact
one Component corrected once                             exact
two different Components each corrected once             exact
valid nonreference correction                            exact
same-current-invalid second response                     exact
different-current-invalid second response          diagnostic
stale Action second response                             exact
foreign Action second response                           exact
terminal forbids a third Prompt                          exact
```

The exact frozen Catalog has only one typed-invalid Candidate in each reached Recovery
Prompt. Therefore `different-current-invalid` cannot be honestly labeled exact. Its control
uses one fully content-rematerialized Reconciliation Component with two distinct grounded,
executable, current-State-invalid Actions. The source Package, presentations, Prompt
Binding, reference baseline, artifact, and Schedules are all rebuilt. The diagnostic object
enters no Manifest Job or empirical denominator.

Observed local dispositions are:

```text
direct first-policy Qualified                              1
ABI-invalid terminal, Verifier not invoked                 1
accepted downstream-invalid completed endpoint             1
one-Component correction, final Qualified                  1
two-Component corrections, final Qualified                 1
valid nonreference correction, final Qualified             1
invalid second-response typed/reference terminals          4
terminal third-Prompt rejection                            1
```

These controls establish Runtime and projection behavior. They do not estimate how often a
model will emit any branch.

## Destructive And Static Controls

All 21 fully rehashed destructive mutations fail closed. They include duplicate, missing,
and extra Jobs; duplicate Package x Replica cells and Raw/Result namespaces; crossed source
parents; ABI-invalid accepted Actions; accepted State-precondition failures; deleted
Feedback; swapped multi-Component attempts; truncated correction counts; corrected Jobs
promoted to first-policy success; unevaluable terminals promoted to Qualified; scripted rows
promoted to empirical; missing Raw identity; scripted or duplicate rows entering the
estimator; complete-baseline loading; exact relabeling of the diagnostic different-invalid
control; and a deleted Transition evidence parent.

All 39 noncompensatory static Gates pass. The transitive source closure contains 341 files
with zero unresolved imports.

## Reproducibility And Tooling

The authoritative formal Root contains 18 files and 1,802,473 exact file bytes. Report
SHA-256 is `e110a179f07391147bf746cf55dbcdd6d0d5103bfbfaa1cd38b0a02a048c0007`.

Fast formal tests pass 7/7 in 3.43 seconds. The complete warning-as-error suite passes 8/8
in 652.48 seconds and performs an empty-directory 18/18 byte-identical rebuild. Focused
PyCompile, Ruff, format, and no-import-follow Mypy pass. Package-wide Ruff passes.
Package-wide no-import-follow Mypy checks 569 source files and retains six historical
diagnostics in four files, with zero v26.179 diagnostics.

## Authoritative Identities

- report:
  `finance_v26_job_bound_multistep_outcome_preflight_report:2f2984578a50a8ef9288af67a1a4dd7062ac9f61d10eb3223c7620ce32bf3ba8`;
- external Authorization:
  `finance_v26_job_bound_outcome_external_authorization:ab9f812a8faeeb2c2947fb11afe46da7b98d8be9a8b4691cff29f2f6e1df928b`;
- transitive source Root:
  `finance_v26_job_bound_outcome_transitive_source_root:437797ffafc5673f8e2d56a1c9206b30323e1ddf48275f10eef405ca3016314f`;
- v26.178 predecessor Freeze:
  `finance_v26_v178_predecessor_freeze_audit:0c25bbb4bb3980c0707666d78d3922e463edfc1a885ebddb1914a9607bdecb9c`;
- v26.178 scope narrowing:
  `finance_v26_v178_outcome_scope_narrowing_audit:d9ccb28fb488f7ab0148c1f912697eb76098eacc322a10c23c2330f087855bf7`;
- generation profile Binding Audit:
  `finance_v26_job_bound_generation_profile_binding_audit:33fcf99c64e2832318252c46b9e166f5b517400b313ccff1259072f6c984e25f`;
- frozen generation profile:
  `capability_job_bound_generation_profile:442d3d1e6fc87ccd491205c46dc394faa003533dbc2df96e9e9defe037210a97`;
- Job-bound multistep Outcome Contract:
  `capability_job_bound_multistep_outcome_contract:08a8cdf22b0c51d063fd9668a473aa305881efeced4b946b72a6fa648f2a26f7`;
- Development Manifest:
  `capability_job_bound_development_manifest:ab33e14cb0dbf81ab38682bfa4785cc1dc8eb5031b696d738a12acc9a97b203a`;
- exact Job-set Audit:
  `finance_v26_exact_192_job_set_audit:29ad14b7b2a3ffc3d0ea002de2817945b5bfec561e5c7e46ebc3d6c23564774e`;
- Runner Contract:
  `capability_job_bound_multistep_runner_contract:11e3e81775a4c38e2c888957cb704c0a718213b25db52a376efbe6f3f4f52238`;
- accepted-prefix Surface Audit:
  `finance_v26_accepted_prefix_action_surface_audit:a6ea7829f12c70bc49c4722d66d9117a53e776d5e10717bb141409efc6adb0a8`;
- scripted denominator Preflight Audit:
  `finance_v26_scripted_192_job_denominator_preflight_audit:d39f29626771393e018e46865e20f0cb9acc9abc14865381538fb20263537941`;
- Runner branch Control Audit:
  `finance_v26_job_bound_runner_branch_control_audit:f3e357f806535f08e10bb820875cf413f75ab82ad23ebf970e2563de001b7f35`;
- empirical Outcome Schema Audit:
  `finance_v26_empirical_job_bound_outcome_schema_audit:b7d7de5af211ef5abe224497e175504605fde58d641cc79fae1d39a3f957efbc`;
- destructive Audit:
  `finance_v26_job_bound_outcome_production_destructive_audit:052f25dc95f8be9bafbf520049ab329e461029f6d33e1f9553c90f837713c5b4`;
- static Audit:
  `finance_v26_job_bound_outcome_static_audit:359cb96c692d4eefcd679487142aac5d64e895a88021c38e7ffb0153baf17826`;
- transition:
  `finance_v26_job_bound_outcome_preflight_transition:9df22a6cd940a0693a20d2c38c0cb34a37b6da9e46a0320900bd1d6415eaad35`.

## Scientific Boundary And Next Transition

v26.179 establishes an exact prospective 192-Job identity set, lossless multi-Component
attempt traces, strict ABI/Action/Verifier separation, exact-set empirical estimator gates,
complete accepted-prefix local coverage, and a credential-free one-current-Prompt Runner
preflight.

It does not establish model readability, model success, empirical Capability Depth,
success monotonicity, Confirmation, frequency, State Mapping, Contribution, VTDO, Student
visibility, training, release, or production evidence.

The only permitted transition is:

```text
capability_observation_job_bound_multistep_outcome_192_job_
runner_preflight_independent_audit_only
```

A successor may only independently rebuild and audit the exact v26.179 Manifest, Runner,
all-prefix surface, scripted Outcome projection, branch controls, exact-set estimator gates,
and parent identities with zero Provider calls. Online Development execution remains
unauthorized until that independent audit makes a new explicit decision. Source, Task,
Component, Candidate, Schedule, presentation, correction bound, threshold, model/Thinking,
Grammar, Policy, resource, terminal, Manifest Job set, or Outcome semantics changes;
historical rewrite; Confirmation access; Mapper; State; frequency; Contribution; VTDO;
Student visibility; training; release; and production remain forbidden.
