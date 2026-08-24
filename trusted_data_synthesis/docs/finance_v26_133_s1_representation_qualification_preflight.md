# Finance v26.133 S1 Model-Visible Representation Qualification Preflight

Audit date: 2026-08-24

## Decision

Finance v26.133 consumed only the credential-free transition authorized by v26.132:

```text
fresh_s1_model_visible_representation_qualification_contract_manifest_runner_preflight_only
```

The stage passes. It materializes a fresh engineering-only S1 representation-qualification
Contract, 48 S1 qualification Path audits, one exact 32-Job Manifest, one outcome interpretation
Contract, one privacy-first bounded Runner, one future execution identity, and one report
identity. It then completes a full scripted Runner preflight without credential lookup, model
client construction, real Provider calls, Stage 2 Provider calls, GPU jobs, empirical rows, or
historical reclassification.

The only newly authorized transition is:

```text
s1_model_visible_representation_qualification_execution_only
```

This authorizes only the exact fresh 32-Job engineering Manifest frozen here. Capability,
Reachability, role Job execution, State Mapping, training, release, and production Contribution
remain forbidden.

## Why Qualification Uses Repeated Engineering Sources

The v26.132 role Populations contain 24 fresh model-unexposed sources reserved for later
Capability and Reachability measurement. Sending those tasks to the model during an engineering
representation qualification would consume their model-unexposed status before role execution.

v26.133 therefore uses the already model-exposed and permanently engineering-only v26.122 source
chain:

```text
24 repeated engineering TaskPackages
48 registered engineering Paths
32 preserved engineering Job assignments and seeds
```

The qualification layer creates fresh Contract, Path-audit, Job, Manifest, Runner, execution, and
report identities around those sources. It does not create a fresh source claim and does not make
the repeated sources eligible for Capability, Reachability, State Mapping, release, or production
evidence.

An eight-channel census compares the repeated engineering sources against the exact frozen
v26.132 role sources:

| Separation channel | Engineering | Frozen role | Overlap |
| --- | ---: | ---: | ---: |
| source-task artifact ID | 24 | 24 | 0 |
| public task ID | 24 | 24 | 0 |
| Semantic Source ID | 24 | 24 | 0 |
| operational record ID | 24 | 24 | 0 |
| operational TaskPackage ID | 24 | 24 | 0 |
| Evidence ID | 48 | 78 | 0 |
| Evidence Version ID | 48 | 78 | 0 |
| source-record ID | 48 | 78 | 0 |

The resulting qualification Manifest contains zero role sources. The 24 frozen role sources have
zero new model exposure.

## Exact Source Replay

Before loading the engineering static inputs or constructing a qualification identity, v26.133
replayed 3,209/3,209 files:

```text
3,192 v26.132 transitive replay entries
   16 immutable v26.132 outputs
    1 exact v26.133 implementation
-----
3,209 total files
```

The authoritative v26.132 report and transition bytes match their separately frozen SHA-256
values. All replay entries match with zero credential lookup and zero Provider calls.

## Frozen S1 Reconstruction

The 48 repeated engineering Paths contain 324 public Semantic Action states. For every state,
v26.133 renders and inversely decodes the frozen S1 representation under three model-visible
phases:

```text
Primary
ABI Rescue
Semantic Recovery
```

All three phases retain the exact public state, complete Candidate set and presentation order,
canonical `action_id` values, reference Proposal, and reversible Stage 2 Commit. The exact static
results are:

```text
Primary state reconstructions             324/324
ABI Rescue state reconstructions          324/324
Semantic Recovery state reconstructions   324/324
Reference Proposals                       324/324
Reversible Stage 2 Commits                324/324
Full-object fallback count                      0
Provider calls                                  0
Stage 2 Provider calls                          0
```

The engineering qualification maxima are:

```text
Action Primary Prompt                    13,951 bytes
Action ABI Rescue Prompt                 14,055 bytes
Semantic Recovery Prompt                 14,051 bytes
Final Primary Prompt                      5,152 bytes
Final Rescue Prompt                       5,286 bytes
registered complete-path bound          339,504 tokens
```

These values fit inside the unchanged v26.132 role resource vector:

```text
Prompt ceiling                            60,000 bytes
Primary requests                              21
Stage 1 Provider calls                        23
transport-inclusive invocations               24
rollout upper bound                    1,120,000 tokens
Completion request bound                  16,384 tokens
ABI / Semantic / Transport / Detour       1 / 1 / 1 / 1
```

The smaller engineering maxima do not lower or replace the role Contract. The exact v26.132
resource values remain bound to the future qualification Runner.

## Public Progress Vector Contract

The audit recommendation identified a definition risk in the phrase "no public semantic
progress." v26.133 freezes the exact Progress Vector rather than broadening that phrase. Its
ordered components are:

1. unresolved public symbols;
2. ordered `(node_id, frontier_status)` Operation-frontier pairs;
3. nullable terminal Operation reference;
4. terminal-verification-completed Boolean;
5. Final-answer-allowed Boolean.

The comparison rule is canonical componentwise equality. A successful public Observation with a
changed vector is Progress. A successful public Observation with an unchanged vector is only a
Detour candidate. A failed Observation is not an Ordinary Detour.

A newly retrieved public result may change the full public state without changing those five
components. Such a result is retained as diagnostic public information. The Contract explicitly
forbids interpreting unchanged-vector status as proof that the action was useless to the task.

## Reference Baseline And Ordinary Detour

The first full scripted run exposed an important boundary before formal artifact freeze. Some
registered reference trajectories legitimately contain successful information-acquisition calls
that do not immediately change the five-component Progress Vector. Counting every such call as an
Ordinary Detour would consume two Detours on a frozen reference Path and contradict the v26.132
fact that all 48 reference Paths are admitted.

v26.133 therefore binds the definition already implied by the v26.132 dynamic census:

```text
Ordinary Detour
= successful public Observation
+ unchanged frozen Progress Vector
+ selected Action differs from the frozen public ordinary-replan reference Action
```

The reference Action is used only as a Host-side measurement classifier. It is derived from the
same public S1 state, is never inserted into the model response, never removes or reorders a
Candidate, never replaces the selected model Action, and never repairs a Proposal. Reference
no-progress calls remain part of the baseline trajectory and do not consume the additional Detour
allowance.

The Detour decision still occurs only after the model Proposal, exact ABI, same-action Commit,
Tool execution, and public Observation exist. A second qualifying non-reference Detour retains
its Proposal, Commit, and Tool Observation, then emits
`ordinary_detour_allowance_exhausted` before any later Provider invocation.

## Fresh Qualification Manifest

The fresh Manifest preserves the exact v26.122 32-Job task assignment and seed projection. It
covers all 24 engineering TaskPackages and all twelve Mechanism x Path Strategy cells. All 32 new
Job identities are distinct from the v26.122 Jobs and from the frozen v26.132 role Jobs.

The pre-registered representation Gate is engineering-operational rather than a task-validity
claim:

```text
exact denominator                              32 Jobs
minimum first-action interface-qualified       24 Jobs
required Mechanism x Path Strategy coverage    12 cells
Instrument/privacy/model/Thinking/Usage failures tolerated  0
```

A first action is interface-qualified only when it crosses the exact four-field Action ABI,
binds the current state, selects a visible Candidate with the matching Decision kind, and produces
a reversible Stage 2 Commit of that same Action. Program progress, Program closure, Final ABI,
answer validity, mechanism validity, and independent trajectory validity remain separate outcomes.

These thresholds were frozen before any online S1 qualification outcome. The scripted controls
do not count toward the future empirical denominator.

## Privacy-First Bounded Runner

Every future Provider invocation requires, before transport behavior:

1. the exact model and Thinking-enabled request binding;
2. the exact S1 or Final Prompt hash;
3. current public state and Candidate-presentation binding;
4. dynamic resource certification;
5. the four independent counter values;
6. one fresh transport-invocation certificate.

The transport certificate is persisted before the invocation. One no-telemetry transport failure
may receive one fresh replacement certificate for the exact same prepared request. Transport
Replacement does not consume ABI Rescue, Semantic Recovery, or Ordinary Detour.

On a response, a privacy-redacted Provider Envelope is persisted before the separate public
payload Projection. The Envelope retains model, finish/status, Usage, Thinking telemetry, public
content hash and length, and exact parent certificates. It retains no public payload, private
reasoning content or hash, Raw HTTP body, or Raw request body. A privacy rejection preserves the
Envelope and a generic payload-free Projection.

Stage 2 has no Provider route and makes zero Provider calls. Complete Raw recovery reparses all
Envelope, Projection, transport-certificate, and Raw bytes with zero calls. Any orphan artifact
blocks retry.

## Scripted Runner Preflight

The exact 32-Job scripted denominator completes with:

```text
completed Jobs                              32/32
first-action interface-qualified Jobs       32/32
covered Mechanism x Path cells              12/12
S1 Semantic Action payloads                    224
reversible same-action Commits                  224
public Observations                             192
exact Final payloads                             32
privacy Envelope/Projection pairs               256
complete Raw zero-call recoveries             32/32
full-object Action Prompt count                    0
real Provider calls                                0
Stage 2 Provider calls                            0
```

Thirteen additional controls pass:

1. exact S1 Action ABI Rescue;
2. separate Semantic Recovery;
3. separate Transport Replacement;
4. privacy-first rejection persistence;
5. Completion Usage at 16,384/16,385/16,386;
6. one non-reference Ordinary Detour followed by normal replanning and completion;
7. second-Detour typed measurement terminal;
8. exact Final ABI separated from answer validity;
9. complete Raw zero-call recovery;
10. orphan-artifact retry rejection;
11. S1-only execution with zero full-object fallback;
12. role class-external frequency opportunity separation;
13. exact resource and four-counter vector binding.

All 24 destructive mutations fail before unauthorized behavior. They cover source overlap, role
source insertion, false zero-frequency interpretation, Progress Vector changes, full-object
fallback, state/path deletion, resource or counter changes, second-Detour authorization, threshold
relaxation, Manifest deletion, Detour/model-failure conflation, Stage 2 Provider routing, and
preflight execution authorization.

## The 252 Role Class-External Actions

v26.132 retained 252 successful no-progress state/action pairs whose frozen ordinary replan did
not close. v26.133 binds the exact 252-pair set hash into the source-separation audit.

The engineering qualification states have zero overlap with those role state IDs. Therefore the
future 32-Job engineering qualification has no direct opportunity to select one of the exact 252
role pairs. This is reported as a zero opportunity denominator, not a measured frequency of zero.
Their empirical selection frequency remains a required role-execution diagnostic after role
execution is separately authorized. v26.133 does not expose the role sources merely to estimate
that frequency early.

## Interpretation Boundaries

This stage establishes static constructibility and Runner-Instrument readiness for a future
online S1 representation qualification. It does not establish that Flash understands S1, does not
measure S1 response usability, and does not create a Capability or Reachability result.

The future online qualification may report:

- exact Action ABI and current-state binding;
- visible Candidate and Decision-kind binding;
- reversible Commit and public Progress;
- 0/1/2+ non-reference Detour counts;
- typed Detour measurement-support exits;
- actual Prompt, request, invocation, and Usage values;
- Final ABI and answer validity as separate outcomes.

It may not use outcomes to alter the frozen role tasks, select another S1 representation, invoke a
full-object fallback, change the model/profile/Grammar/resource/counter vector, or admit any
qualification row to Capability, Reachability, State Mapping, training, release, or production.

## Authoritative Identities

- source replay:
  `finance_v26_s1_qualification_source_replay:15235e713190c1619799b1be734565c42b387c103c4e617f6279a3c2aa46cdf1`;
- report:
  `finance_v26_s1_qualification_preflight_report:9d79af8e43b93f768d615be5aa1ca22ac2f733b5171fb191b87b4f0bf1785c4a`;
- frozen predecessor binding:
  `finance_v26_s1_qualification_predecessor_binding:a2a917bbcb7723f17edf7635a21a0ca27da8dcceedc07fe81d61302a6a6bdd10`;
- engineering/role source separation:
  `finance_v26_s1_qualification_source_separation:3caad15982367a4f65aff8a15c7e9b732d2b1e801b3d6867736669dd4ae1ec4d`;
- public Progress Vector Contract:
  `finance_v26_public_progress_vector_contract:c716f6844e51e70751fba628805611223fba6775e905cfe336b78298d7ded785`;
- S1 qualification Path Catalog:
  `finance_v26_s1_qualification_path_catalog:48e21b62dc6be94a204980ccbfa186fad0f3087a8f92f37ee8b3c26856039026`;
- resource Contract:
  `finance_v26_s1_qualification_resource_contract:9ba3c63a1c7cfebe6a954eda18e0cd6e3414fcc2fc17a2ac0c95e6e7a199fba6`;
- S1 representation-qualification Contract:
  `finance_v26_s1_representation_qualification_contract:7ab0a66c595c13374380d3ec3464ebae33d7c150ee18ae87a4c3e1130e31fb82`;
- Manifest:
  `finance_v26_s1_qualification_manifest:75dd0c9a5e705225bf02063a8ab18cfaaefcc19df62a1c26b2b8c783a83e99eb`;
- outcome Contract:
  `finance_v26_s1_qualification_outcome_contract:0a276275c4878323227313658ad25642f95b40b7a60ff6f6f575e21f1cc09bdc`;
- Runner Contract:
  `finance_v26_s1_qualification_runner_contract:1aca524bc565c1157f876ad55d2f469c516dd1ff85308cf9719029f914cd750c`;
- Runner fixture:
  `finance_v26_s1_qualification_runner_fixture:bcef992f37059073ffff0991e15d1d9708ea97626c55ff8016eb324dee3d909b`;
- Runner controls:
  `finance_v26_s1_qualification_runner_control_audit:e4f2342a9c9802e9cf4736eba1c5f73271a6c57f95cb512139c5483ef12872d2`;
- destructive audit:
  `finance_v26_s1_qualification_destructive:44a96bfcf54eea47a84e8ec59507c3958a3b4ac18cea41c85aca65f887093294`;
- transition:
  `finance_v26_s1_qualification_transition:a6f63cd2e7555ceb9d73c507c844a7e4d3d91cf1805e01e196d03532b68e98fa`.

## Verification

- formal build: all 15 outputs written under the fresh v26.133 artifact directory;
- independent focused rebuild: 15/15 files byte-identical;
- focused Pytest: 2/2 passed in 55.99 seconds against the final type-complete source;
- selected v26.129-v26.133 adjacent regression: 10/10 passed in 837.94 seconds;
- focused Ruff check and format: passed;
- focused Mypy: passed;
- package-wide Mypy: 450 source files checked; only the three pre-existing diagnostics in v26.70
  and v26.129 remain, with zero v26.133 diagnostics;
- real Provider calls: zero;
- Stage 2 Provider calls: zero;
- GPU jobs: zero;
- empirical rows: zero.

## Current Transition

The only permitted transition is:

```text
s1_model_visible_representation_qualification_execution_only
```

The successor may execute only the exact fresh 32-Job engineering Manifest above under the exact
Runner and outcome Contracts. It must replay the complete v26.133 chain before credential lookup
or client construction. No role source or role Job may be exposed. Historical rerun, recovery, or
reclassification; task/Tier/S1/Candidate/model/Thinking/Grammar/resource/counter changes;
full-object fallback; Capability or Reachability execution; State Mapping; training; release; and
production Contribution remain forbidden.
