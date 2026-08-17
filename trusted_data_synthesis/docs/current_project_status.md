# Current Project Status

Audit date: 2026-08-18

This status is reconstructed only from the current Git tree, immutable experiment artifacts,
credential-redacted recovery records, and checks rerun on the migrated server. Missing chat
messages are not treated as experimental evidence.

## Repository Identity

- Canonical implementation repository: `/data1/zhuxinrui/projects/Data-Synthesis`
- Immutable experiment artifact root: `/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis`
- Integration branch: `main`; isolated worktrees are temporary implementation staging only
- v22 exact-target measurement source commit: `3aa1b0c39d040f79f11bba6166573ec82d729377`
- v22 exact-target source tree: `b61605018f35ed9550aa02d6c89e164bbe7252c8`
- Credentials remain process-environment inputs and are not tracked or serialized

## v26.55 Executable-Support Contract v2

Finance v26.55 is a credential-free hardening replication of v26.54. A prospective contract audit
found that v1 did not explicitly include Citation completeness in Public Witness validity and
would reject a future capability-measurement task merely because it lacked three VTDO paths. The
v2 Core contract adds sorted selected Citation support to `V=1`, admits the capability-only role
without weakening VTDO, and requires every necessity counterfactual to target its enclosing
mechanism. Historical v1 Witness identities retain their original hash semantics.

The same immutable 24-task source was rebuilt with compiler `1.1.0`. All 24 Witnesses have complete
Citation support; complete Public Witness validity remains 18/24. The same six tasks fail because
a declared Reconciliation axis has no allowed `normalize_metric_unit_period` tool. Projection and
Lattice binding, Mechanism Necessity, and three-path support remain 0/24, so both capability and
VTDO eligibility remain 0/24. This confirms that the v26.54 blocker was not caused by omitted
Citation accounting or task-role conflation.

The authoritative v2 report is
`finance_v26_executable_support_audit:9f3b34ae4fcb75fb7226ba9d5e67a20fe5e596d8fb45bdf689208d5323c9bbae`.
It used zero API calls and zero GPU jobs. Its transition remains
`capability_task_or_scaffold_redesign_only`; Fresh Confirmation, State-support Discovery, No-C
VTDO, Student training, Exact Target, GP-C, and production Contribution remain forbidden.
Production Contribution is zero. v26.54 remains immutable historical evidence at source commit
`c67671c`, while v26.55 is the required contract for all future rematerialized tasks. See
`docs/finance_v26_55_executable_support_contract_hardening.md`.

## v26.54 Executable-Support Precondition Audit

Finance v26.54 implements the credential-free compiler redesign authorized by v26.53. It adds
domain-neutral Core contracts for Typed Answer Projection, Public Executable Witness, Mechanism
Necessity, Alternative Valid Paths, Evidence Support Lattices, and separate capability/VTDO task
admission. The audit replays all 24 immutable v26.42 Development tasks without rescoring v26.43.

A new public-tool compiler produced 226 content-addressed Observations. Eighteen of 24 tasks have
a complete Public Executable Witness. The other six declare a Reconciliation axis while omitting
`normalize_metric_unit_period` from Allowed Tools; the compiler blocks them as
`required_normalization_tool_not_allowed`. Historical Oracle Reference Workflows are not counted
as Witnesses because they use Oracle-only tools, and compiler Witnesses are explicitly not counted
as model-owned VTDO paths.

All 24 Typed Answer Projection contracts and Evidence Support Lattices compile, but zero are bound
to the immutable historical TaskPackages or current Verifier. Mechanism Necessity is 0/24:
Context wrong-action irreparability is 0/8, Reconciliation normalized-reference consumption is
0/8, and the historical eight-task Recovery/Stopping mechanism remains combined. The prospective
taxonomy records 8 Context, 8 Reconciliation, 4 Recovery, and 4 Stopping tasks without relabeling
historical artifacts. No task has three independently valid, model-owned, state-distinct paths.

The role-specific result is therefore:

```text
capability_measurement_eligible = 0/24
vtdo_multistate_eligible        = 0/24
```

The authoritative report is
`finance_v26_executable_support_audit:1c82f661174e1e62783272df1333fdfdaac9797422052b29c28f98f1784b7cc1`.
The run used zero API calls and zero GPU jobs. It preserves
`capability_task_or_scaffold_redesign_only`; Fresh Confirmation, State-support Discovery, No-C
VTDO, Student training, Exact Target, GP-C, and production Contribution remain forbidden.
Production Contribution is zero. See
`docs/finance_v26_54_executable_support_precondition_audit.md`.

## v26.53 Read-only Statistical Audit

Finance v26.53 completed a credential-free, non-authorizing audit of all 576 immutable v26.43
rollouts. It produced 576 rollout diagnostics, 96 mechanism/Scaffold/task Cell summaries, and 24
task-level Scaffold influence records. Exact source and output hashes replay successfully; an
independent rebuild reproduced all three detail artifacts byte for byte. Both builds used zero
API calls and zero GPU jobs. v26.53 supersedes the uncommitted v26.50 through v26.52 development
diagnostics.

The ordered failure cascade accounts for all 553 invalid trajectories: 288 first fail at operation
execution, 198 at answer projection, 32 at Evidence selection, 24 at verification, 8 at model
contract, 2 at argument construction, and 1 at citation. The 198 answer-only failures are not all
formatting defects: 137 combine value and reference errors, 26 are numeric/scalar only, 25
exactly match the compiled human-facing Answer Projection, and 10 contain a wrong Evidence
reference or projected label.

The trajectory audit rejects a global template-collapse explanation. Across the 96 six-rollout
Cells, mean unique normalized trace count is 5.323 and mean effective trace count is 5.188.
However, this variation is carried predominantly by invalid paths. Only 23 trajectories are valid,
covering 3/24 tasks and 9/96 Cells; 21/23 come from Semantic Reconciliation. Positive state-support
inference therefore remains unsupported. All 23 valid trajectories have a Quotient State, with
21 unique states, entropy 4.3496 bits, and effective count 20.3880. No invalid trajectory is mapped;
its state entropy is undefined rather than zero.

Citation equality is not an isolated observed blocker: all 183 citation-equality failures are strict
Gold subsets, none are strict supersets, and none fail only the citation family. Semantic equivalence
of alternative non-Gold Evidence remains unevaluated. Static inspection also finds one registered
Reference Workflow per task and no dedicated Public Executable Witness, Mechanism Necessity, or
Alternative Valid Path artifact.

The final audit identity is
`finance_v26_bridge_statistical_audit:c7851d1487fbab1c5d4814451ea3f46aa52f54e68f01bc841cd66acfcd43c64b`.
It preserves `capability_task_or_scaffold_redesign_only`; no v26.43 outcome was rescored and no
downstream stage was authorized. See
`docs/finance_v26_53_failure_cascade_trace_statistical_audit.md`.

## Current v26 Mainline Decision

The latest completed model experiment is Finance v26.43 Bridge Development. It follows a new
source-exposure and grounding audit, a fresh v26.42 protocol, and a complete credential-free
24-task Joint/Scaffold prefix. It does not mutate or reauthorize v25.47.

The v26.42 no-API chain completed 24 Joint Compilations, 24 State Spaces, 72 Joint audit Evidence
records, 384 Joint atomic cases, 24 Joint Admissions, 24 Scaffold ladders, 672 Scaffold gate
Evidence records, 3,024 Scaffold atomic cases, 24 Scaffold Admissions, 96 ordered-history collision
cases, 96 cross-level mapping cases, and 3 Bridge static audits containing 144 atomic cases. All
eight Development/Confirmation freshness intersections are zero. Credential-free replay reproduced
the same Stage Ledger with zero API calls and zero GPU jobs.

The authorized v26.43 run then completed exactly 576 DeepSeek V4-Flash Development rollouts:

```text
3 mechanisms x 4 scaffold levels x 8 tasks x 6 rollouts = 576
```

All 5,166 Provider calls returned HTTP 200 with no fallback. Raw byte, identity, actual Prompt,
Scaffold, Host side-channel, and recursive noninterference checks passed for 576/576 artifacts.
There were no Runtime or instrument failures. Only 23/576 trajectories passed independent semantic
and evidential verification; 553 were model-invalid. Context-conditioned action produced 0 valid
trajectories, semantic reconciliation 21, and recovery-and-stopping 2.

Task-first, rollout-second hierarchical inference admitted no scaffold level for any mechanism.
The content-addressed Support Freeze is `blocked`, selects no scaffold, and authorizes only:

```text
capability_task_or_scaffold_redesign_only
```

Fresh Confirmation, State-support Discovery, No-C VTDO, Student training, Exact Target, GP-C, and
Contribution remain forbidden. Production Contribution is zero and unauthorized. This is a valid
negative Bridge Development result, not a Runtime failure and not evidence against VTDO itself.
See `docs/finance_v26_43_bridge_development_report.md`.

The source layer now rejects both historically API-exposed Evidence and Evidence that fails the
independent Finance source-grounding verifier before task resampling. Of 151,114 source Evidence
items, 1,657 were historically exposed, 24,714 failed source entailment, the effective exclusion
union contained 26,290 identities, and 124,824 remained eligible. The final 70-task source
Population and 24/24 Development/Confirmation selections were built from that eligible set.

The immutable v26.43 checkpoint required a zero-generation finalization recovery because the
then-frozen postprocessor had collection-order and JSON mapping-order defects. The 576-record
checkpoint SHA-256 was identical before and after recovery and no model call was repeated. The
permanent implementation uses Bridge Rollout observation v3, Bridge Level Inference v2, Bridge
Support Freeze v5, Bridge Runner v2, and Stage Router v6. It canonicalizes rollout/cell ordering,
validates registered metric key sets independently of mapping insertion order, compares exact cell
identity sets, persists raw-first failure telemetry, and derives the final report transition from
the Support Freeze.

The immutable v26.43 `report.json` retains the older blocking label
`capability_scaffold_repair_only`; it is not rewritten post hoc. The authoritative Support Freeze
uses `capability_task_or_scaffold_redesign_only`, and all future reports inherit that value
directly. Both labels block downstream stages, but only the Support Freeze label is current.

v25.47 replaced the opaque
v25.46 branch cue with one typed, action-neutral public relation state and one shared decision
policy. Its 48-task pre-API population passed every construct-validity check, including unique
public applicability, Context sufficiency, order and label invariance, Context removal and swap
mutations, action-description symmetry, deterministic replay, and lexical leakage rejection.

The 384-rollout DeepSeek V4-Flash execution was fully auditable, with zero recursive Host-field or
marker violations. The aggregate Contextual Shape was admitted, but the prospective mechanism
estimator failed: branch-balanced first-action accuracy was `0.34375`, below both the frozen
`0.625` requirement and the `0.5` constant-action baseline; contextual policy gain was `-0.15625`,
and its paired hierarchical-bootstrap LCB95 was `0.171875`. Only 3/4 matched pairs were
informative.

This is interpreted as a localized Flash contextual tool-selection limitation under sufficient
public Context, not as permission for another same-grammar Prompt repair. A separate immutable
scientific decision tightens the automatic report transition to
`contextual_tool_selection_limitation_recorded` and forbids threshold relaxation, post-hoc task
deletion, additional Flash replicas, Pro calls, Beneficiary screening, Exact Target, and GP-C.
Production Contribution remains zero. See `docs/finance_v25_47_context_sufficiency_report.md`.

## Runtime And Data

The migrated environment is operational with Python 3.12, PyTorch 2.7.1+cu128, CUDA 12.8, and
eight NVIDIA A100-SXM4-80GB GPUs. The completed v26.43 run used no local GPU. No sealed experiment process remained after aggregation.

After all v22 workers had exited, a separate root-owned process
`/opt/venv/render/bin/python3 --coin pearl` appeared at 10:22 and occupied GPUs 0, 1, 3, 4, 6, and
7. It is not a project process and was not terminated. At the same time, `/usr/bin/nvidia-smi` had
an invalid mixed-case ELF interpreter path; read-only inspection remained possible through the
system loader. Future GPU experiments should not start until the server operator reviews this
external workload and binary change. Neither event occurred during the completed v22 target
workers or changes their content-hashed artifacts.

The read-only Finance Archive remains the active data dependency:

| Item | Verified value |
| --- | ---: |
| KG build | `kg_20260711_062123_bc4b4394` |
| Graph schema | `3.0` |
| Nodes | 913,475 |
| Edges | 5,734,348 |
| Fact nodes | 658,535 |
| DerivedFact nodes | 135,990 |

The newest DB-only build from the previous server remains unavailable. The immutable archive used
by the experiment is present and readable.

## v21 Cancellation And v22 Development Expansion

v21 was stopped by operator request after Estimation and Validation each wrote 9 of 32 planned
observations. No aggregate was created, no GP-C evaluation occurred, and the partial rows are not
scientific evidence for target identifiability. All v21 workers are stopped.

v22 froze a pre-outcome Development-only population from the 420-task real Finance pool: 30 tasks
balanced across six families, 100 accepted states, and 312 public Evidence versions with zero
Evidence overlap across target tasks. A separate 64-record Objective role is task-, signature-, and
Evidence-disjoint from the targets and was frozen into eight micro-splits of eight. DeepSeek v4 Pro
completed 300 unconditioned Explorer draws and 500/500 state-conditioned realizations.

The exact target then completed 500/500 strict-FP32 state gradients and 8/8 Objective-gradient
micro-splits on two parallel three-GPU workers. It produced 4,000 crossed observations under one
shared global cold-start AdamW update. Maximum FP32/FP64 target delta was `1.0551e-11` and maximum
simplex-centering error was `1.1699e-11`.

Post-measurement dual-axis inference found that 26/30 primary coordinates were statistically
nonzero, while 30/30 primary coordinates and 100/100 total state coordinates were practically
equivalent under their update-derived MPE. No coordinate was meaningfully beyond MPE. Objective
micro-split variation accounted for `99.9443%` of nested measurement variance; realization
variation accounted for approximately `0.0005%`.

## v23 Pro--Flash Agent Runtime Qualification

v23 changes the generation kernel before attempting another exact-target study. It compares exact
`deepseek-v4-pro` and `deepseek-v4-flash` model identities across Direct/Bare, Host-scripted Tool,
and Autonomous Agent runtimes. Scripted and Autonomous share one frozen six-tool Archive
environment; all Observations are content addressed and independently replayed. The model never
receives Gold Evidence IDs, hidden programs, reference answers, Proof Graphs, or quotient targets.

Protocol-development runs v4-v8 localized output-contract, stop-correction, tool-argument,
no-match recovery, and cumulative-context-budget failures. v6, v7, and v8 each consumed a new
36-task set, and each successor excluded every earlier formal task set. No gate threshold was
relaxed. v9 was declared the final qualification and excluded 150 prior task identities before its
first API call.

v9 completed all 36 requested calibration records with 12 parallel workers. It made 265 API calls,
used 1,151,551 provider-reported tokens, and recorded an estimated API cost of `$0.2782318716`.
All calls used the requested exact model, with zero fallback, zero model-identity mismatch, and zero
HTTP failure. The six model-runtime cells were:

| Model | Runtime | Completed | Independently valid |
| --- | --- | ---: | ---: |
| Pro | Direct/Bare | 6/6 | 6/6 |
| Pro | Scripted Tool | 6/6 | 5/6 |
| Pro | Autonomous Agent | 6/6 | 4/6 |
| Flash | Direct/Bare | 6/6 | 6/6 |
| Flash | Scripted Tool | 6/6 | 4/6 |
| Flash | Autonomous Agent | 5/6 | 3/6 |

The exact-model, independent-validity-smoke, and interactive-tool gates passed. The minimum cell
completion rate was `0.8333 < 1.0`, and the minimum cell JSON-contract rate was
`0.9048 < 0.95`; both preregistered gates failed. The formal decision is
`stop_after_factorial_calibration`, with `next_permitted_stage=protocol_repair_only`. The 30-task,
1,800-rollout Discovery was not launched. No GPU, exact-target, GP-C, Validation, or Authorization
computation occurred.

## v24 Runtime Qualification And Semantic Ladder

v24 freezes semantic, Agentic, and protocol difficulty separately and requires both Runtime
qualification and a true semantic Frontier before capability measurement. Development revisions
removed premature verification, rejected `verified=false`, separated raw JSON response rate from
bounded logical resolution, and clarified exact public selector and JSON operand contracts.

The final v4 qualification excluded every v1-v3 task before sampling. It selected 60 new task IDs
with zero overlap against prior v24 qualification tasks and ran the 18 Easy-Control tasks with 24
workers. All 216 requested rollouts completed. Minimum raw JSON response rate was `0.9556`, bounded
logical resolution was `1.0`, minimum tool success was `0.9531`, final-answer emission was `1.0`,
and no budget or authority failure occurred. The run used 6,723,826 provider-reported tokens and an
estimated `$1.4765509822`; it used no local GPU.

The semantic audit failed independently: Easy, Frontier, and Hard means were `4.5833`, `4.5950`,
and `4.7292`; no family met the minimum Frontier gain. A deliberate Stage B invocation
revalidated the Stage A report, checkpoint, and canonical rollout, then failed before client
construction with `capability calibration requires a true semantic Frontier`. The formal transition is `frontier_task_construction_only`; Exact Target, GP-C, Validation, and Authorization
remain forbidden. A credential-free completed-run replay resumed `216/216`, executed zero jobs,
validated both content hashes, and returned the unchanged report identity without client
construction. See `docs/finance_v24_capability_ladder_experiment.md`.

## v25 Capability-Identifiable Frontier

v25 treats surface-balanced task labels as insufficient. It registers Retrieval, Planning,
Calculation, Reconciliation, Verification, Recovery, and Stopping as seven capability axes and
constructs an executable family for each axis. Each family contains three Easy, five Frontier, and
two Hard-Control tasks drawn from the immutable 420-task Finance source population.

All 70 composite Programs execute and independently replay, all public Corpora are mutually
Evidence-disjoint, and the same source, run ID, and sampling salt reproduce byte-identical JSON and
Markdown. The audit uses only Program and typed workflow structure to derive demand vectors; family
labels add no weight and are used only to verify expected primary-axis alignment. Equal-vector and
relabeling mutations fail closed.

The structural result authorizes construction of a v25-native boundary contract, not immediate
calibration. v25.0 and v25.1 each executed 126 Qualification attempts and failed closed with
`next_permitted_stage=protocol_repair_only`. The failures localized discarded Direct semantic
failure lineage, an incorrect Scripted retry-authority comparison, and ambiguous technical tool
success semantics. Their immutable reports remain diagnostics and are not reclassified.

v25.3 and v25.4 were unexecuted preflights. v25.5 was also retired before execution after a final
audit found that Calibration trusted a passing Qualification report without independently
replaying checkpoint, canonical records, outcomes, and the run manifest. None made an API call or
used a GPU. v25.6 uses incompatible v6 Contract, Runner, Record, Report, and empirical-audit
identities. Qualification accuracy remains descriptive; bounded JSON, typed terminal results,
bounded tool resolution, replay, authority, complete denominators, exact-model telemetry, and
resource budgets control the transition.

A passing report would unlock the balanced 28-task, 1,680-rollout Pro--Flash calibration. Model
differences are estimated with a task-cluster paired nested Bootstrap. The raw empirical
information matrix uses the preregistered uncentered demand formula; axis-specific information uses
confidence-interval lower bounds after removing the intercept and a general-difficulty factor. The
separately frozen Qwen Beneficiary identity is content-replayed; its uncertainty-aware 420-rollout
screen cannot start before the empirical audit passes and may release only explicitly selected
boundary-mass tasks.

The v25.6 contract ID is
`finance_capability_boundary_contract:45896e3eafdc2712657a83c8b0e5482d7849639485205e5f88e396313f248ef2`.
Its unchanged Population and split pass 35/35 destructive Capability Necessity probes. A
credential-free negative preflight confirmed that Calibration rejects an incomplete frozen
Qualification run before model-client construction. v25.6 has made no API call and used no GPU.

Exact Target, GP-C, Validation, Authorization Objective access, VTDO updates, and production
Contribution remain forbidden. See `docs/finance_v25_capability_sensitive_frontier_report.md` and
`docs/finance_v25_capability_boundary_revision.md`.

## v25.17-v25.18 Runtime Resolution And Information Geometry

Runtime Resolution v2 replaced the invalid `technical pass == semantic success` interpretation.
Instrument qualification now depends only on execution integrity, typed terminal resolution,
Runtime pathology, and failure-attribution coverage. Model protocol, decision, recovery, stopping,
verification, and semantic errors remain capability outcomes.

The final v25.18 source pool contains 420 accepted tasks and 1,394 states. Its 70-task Capability
Frontier covers seven capability families and passes all structural monotonicity and primary-axis
alignment audits. A Flash-only public regression excluded 133 prior task signatures and 371 prior
Evidence/Version identities, then completed 28/28 Scripted and Autonomous rollouts without a
deterministic contract defect.

Fresh Runtime Development and Held-out experiments each completed 84/84 rollouts. Held-out had
100% Runtime qualification, 73.81% Valid Success given Runtime eligibility, and 23.81% boundary
cells. Every failure was attributed to L4 Agent decision or L5 semantics; no L0-L2 failure was
observed.

The resulting Flash information audit failed closed. Scripted Final Valid had rank 3, effective
rank 2.000, 14.29% boundary mass, and 73.39% maximum family share. Autonomous Final Valid had rank
7 and effective rank 3.083, but condition number 135.21. The joint condition numbers were
237,575.79 and 167.80. Bootstrap lower bounds yielded zero informative axes in both Runtime cells.

The final transition is `capability_task_support_redesign_only`. Pro sparse anchors remain
unauthorized. See
`docs/finance_v25_17_v25_18_runtime_resolution_and_information_report.md`.

## v25.19-v25.20 Capability-Support Confirmation

v25.19 froze 14 Runtime-family rules from the v25.18 Development result. Host-controlled Scripted
Planning and Stopping were excluded from response geometry. Every model-visible family received
five independent matched groups and each selected binding received five replicas. The original
pool failed closed when it could provide only three fresh Verification groups; a disjoint
420-task real-Finance extension supplied the required capacity without lowering the contract.

The v25.20 population contains 35 groups, 105 static Tier tasks, 60 Runtime bindings, and 50 unique
selected tasks. All six freshness overlap channels are zero and all static public contracts pass.
The online run completed 300/300 Flash rollouts with 3,698 API calls and 21,388,724
provider-reported tokens. No Pro call or GPU computation occurred.

Runtime qualification passed. All 145 failures are attributable capability outcomes: 117 L4
Agent-decision and 28 L5 semantic failures. Family and Group dominance gates passed, boundary mass
rose to 56.00% for Scripted and 68.57% for Autonomous, and Autonomous became full-rank with all
seven marginal-axis Bootstrap lower bounds positive. The remaining failures are Scripted Final
and Joint condition number, plus Autonomous Final and Joint effective rank.

The experiment shows that independent groups and additional replicas improve observability, but
existing Tier selection alone cannot repair Retrieval/Calculation ceilings or the Reconciliation
floor. The next task population must change those axes' irreducible program and Evidence
dependencies. See `docs/finance_v25_19_v25_20_capability_support_confirmation_report.md`.

## v25.21 Public Benchmark Capability Audit

v25.21 deterministically audited all 1,147 frozen FinQA and 1,663 frozen TAT-QA evaluation items.
The resulting artifacts contain aggregate statistics only: no question, answer, context, program,
or Evidence text is exported. Snapshot content hash, source revision, source blob, split, adapter,
metric, and exact denominator are verified before parsing. Public Agent benchmarks are represented
only by aggregate design references for GAIA, BFCL V4, WebArena, SWE-bench, and AgentBench; their
task content was not loaded.

FinQA contains 493 multi-step programs (42.98%) and 84 programs with depth at least three (7.32%).
TAT-QA contains 699 arithmetic answers (42.03%) and 546 table-text examples (32.83%). These
statistics support financial calculation and semantic-alignment design, but both snapshots remain
static evidence-given QA and therefore cannot measure tool planning, recovery, or state-dependent
stopping.

The v25.20 response geometry was compiled into seven new primary mechanisms: disambiguating
information acquisition, typed tool planning, dependent compositional calculation, Bridge semantic
alignment, candidate verification and repair, cross-family recovery, and state-dependent control.
Every mechanism must support Easy, Bridge, Frontier, and Hard tiers. The preregistered Development
minimum is 84 matched groups, with four Bridge and four Frontier groups per mechanism. Existing
Runtime, Prompt, tool-environment, and Workflow Information thresholds remain frozen and
content-hashed.

The audit is `design_ready_population_not_materialized`; it made zero API calls and used zero GPU
jobs. See `docs/finance_v25_21_public_benchmark_capability_audit.md`.

## Revalidated Code State

| Check | Result |
| --- | --- |
| Development target/design focus | 10 passed |
| v24 Agent/runtime focus | 38 passed |
| v25 capability-identifiability focus | 11 passed |
| v25.19-v25.20 support-confirmation focus | 26 passed |
| v25.21 public-benchmark audit focus | 5 passed |
| Ruff check | passed |
| Ruff format | new v26 files passed; 127 historical baseline files remain unformatted |
| Mypy | passed, 346 source files |
| Pytest | passed, 865 tests in 355.81 seconds |
| v26.55 executable-support v2 focus | 10 passed |
| v26.55 dual build | all seven detail artifacts and report are byte-identical |
| v26.54 executable-support focus | 8 passed |
| v26.54 dual build | all seven detail artifacts and report are byte-identical |
| v26.53 statistical-audit focus | 9 passed |
| v26.53 credential-free replay | authoritative and determinism builds each replayed |
| v26.53 dual build | all three detail artifacts are byte-identical |
| Core generalization boundary | 135 files, zero imports/branches/field accesses/violations |
| Tracked credential pattern scan | zero `sk-` plus 32-alphanumeric hits |
| v25.19 policy deterministic replay | byte-identical SHA-256 `01ff658e46a6...` |
| v25.20 population deterministic replay | byte-identical SHA-256 `8ee0b10046af...` |
| v25.20 contract deterministic replay | byte-identical SHA-256 `80cf20a2e526...` |
| v25.20 completed-run replay | 300/300 resumed, zero API jobs, identical report ID |
| v25.21 audit JSON replay | byte-identical SHA-256 `15b1c8fd99d4...` |
| v25.21 audit Markdown replay | byte-identical SHA-256 `fb0c4018068b...` |
| v25.21 mechanism manifest replay | byte-identical SHA-256 `f9765dc5b622...` |
| v25.21 benchmark-content isolation | 2,810/2,810 questions and all content keys absent |
| v25.29 completed-run replay | 100/100 resumed, zero API jobs, identical report ID |
| v22.1 deterministic replay | identical SHA-256 `a19bcc303026...` |
| Legal and Science contracts | retained by full suite |

The repository-wide formatter would rewrite historical files under the currently installed Ruff
version. Those unrelated files were deliberately not reformatted. The v25.20 contract binds the
exact bytes of `phase1_multitier_capability_population.py`; its pre-run formatting is retained so
the executed contract remains reproducible. All changed Python files pass lint, while the new
non-manifest-bound source and tests also pass the formatter.

The v17 tests reject altered plans, implementation manifests, profiles, splits, source jobs,
result rows, selection lineage, uncertainty envelopes, and stale contracts. Validation cannot run
before selection or with a nonselected profile. A failed aggregate cannot retain a stale numeric
contract.

## Historical Boundaries

### v14 production candidate

The immutable v14 candidate remains historical evidence:

- 30 real Finance tasks;
- 100 quotient trajectory states;
- 300 fresh state-conditioned realizations;
- 1,065/1,065 gradient artifact content hashes verified;
- stable realization sampling and positive internal proxy association;
- seven raw numeric-tail violations and three strict task-order reversals.

It was not reused to tune v16 or v17. Its status remains `partial` with
`production_authorized=false`.

### v16 recalibration

v16 used disjoint development, validation, and sealed-candidate populations. The BF16 TF32 profile
passed development but failed independent validation on relative error, cosine, and GP-score delta.
No v16 numeric contract was issued. Margin-aware ordering remained stable, so v16 localized the
bottleneck to raw gradient-level numerical fidelity rather than sampling or task ordering.

The unused v16 profile was not substituted post hoc, and the v16 validation set was not reused for
v17 tuning.

## v17 Numeric Root-Cause Experiment

### Population and real-Agent inputs

v17 created three fresh, balanced six-task partitions. Every partition contains one task from each
of six task families and binds 63 Evidence versions. Task, Evidence-version, and semantic overlap
across development, validation, and sealed candidate are all zero.

Development and validation each produced:

- 24/24 valid initial trajectories;
- 20 trajectory states;
- 60/60 released state-conditioned realizations.

The full real-Agent input funnel used 554 DeepSeek-V4-Pro calls and 4,092,455 tokens. Every API call
and JSON contract succeeded, fallback use was zero, and the provider-reported estimate summed to
`0.484361248`. That value is telemetry rather than an invoice. The numeric experiment itself made
no additional API calls.

### Development diagnosis

The preregistered matrix evaluated 20 realization-level records under eight profiles. Seven
profiles failed the unchanged raw numeric contract. Only `fp32_activation_strict` passed:

| Metric | BF16 control | FP32 activation |
| --- | ---: | ---: |
| Maximum relative error | 0.03436155 | 0.00641550 |
| Minimum cosine | 0.99952628 | 0.99997942 |
| Maximum GP delta | 0.00212896 | 0.00052523 |
| Maximum update TV | 0.00012564 | 0.00004071 |
| Pairwise envelope | 0.0043 | 0.0011 |

The paired FP32-versus-TF32-off contrast reduced relative error in 20/20 records, with mean
reduction `0.01451894` and a task-cluster bootstrap 95% interval of
`[0.01182715, 0.01846619]`. Projection FP32, FP64 accumulation, TF32-off, checkpoint changes,
separate forwards, and functional VJP did not cross the joint gate.

The development tail was a long `derived_growth_comparison` record whose differential region was
474/5,126 supervised tokens. Its paired relative error fell from `0.03436155` to `0.00363419` under
FP32 activation. The supported engineering diagnosis is BF16 forward-activation rounding in small
differential regions.

### Frozen selection and independent validation

The selector froze `fp32_activation_strict` and an uncertainty envelope of `0.0011` before observing
validation. The independent validation then completed 20/20 fresh checkpoints and passed all gates:

| Metric | Observed | Frozen threshold |
| --- | ---: | ---: |
| Maximum GP delta | 0.00068376 | <= 0.0023 |
| Maximum relative error | 0.00602399 | <= 0.027 |
| Minimum cosine | 0.99998186 | >= 0.99967 |
| Maximum loss identity error | 5.95e-8 | <= 1e-6 |
| Maximum update JS | 5.86e-9 | <= 1e-6 |
| Maximum update TV | 0.00005472 | <= 0.00023 |

All 25 resolvable state pairs, all six task winners, and all six strict task permutations agreed.

Authoritative identities:

- report: `finance_gradient_numeric_root_cause_report:8f9db5c9249904f9846cb7482ad428f0181407a3580d7a00437fa885be57306c`;
- contract: `finance_gradient_numeric_contract:e2a1c890af575f477389b0bfb1475810aeecec3e5f4bf3a6213c552a82fa86b7`.

## v18 Inherited Sealed Numeric Candidate

The first attempt failed before any state metric was computed because the checkpoint loader read
`jobs` from the outer source manifest instead of its nested descriptor. The immutable v1 result
records `execution_failed`, `KeyError('jobs')`, zero checkpoints, and no numeric summary.

A new retry plan allowed only that source-manifest lookup repair and froze every scientific input
unchanged. It computed 20/20 fresh diagnostic checkpoints on GPUs 3-5 and passed all frozen gates:

| Metric | Observed | Frozen threshold |
| --- | ---: | ---: |
| Maximum GP delta | 0.00081042 | <= 0.0023 |
| Maximum relative error | 0.00633034 | <= 0.027 |
| Minimum cosine | 0.99997997 | >= 0.99967 |
| Maximum loss identity error | 5.31e-8 | <= 1e-6 |
| Maximum update JS | 3.37e-9 | <= 1e-6 |
| Maximum update TV | 0.00005026 | <= 0.00023 |

All 24 resolvable pairs, all six task winners, and all six strict task permutations agreed. The
result hash is
`finance_gradient_numeric_sealed_result:ed13f8f07830ad47471293a8c73c22f464844959699b1b91d7c6cc99c94721d2`.


## v19 Sealed Causal Pilot

v19 used six fresh Finance tasks, 20 states, and 60 state-conditioned realizations. The strict-FP32
Gradient execution contract passed, but the independent finite target failed before GP-C was
evaluated. Estimation/Validation reconstruction error was `0.5065/0.3774` against `0.1`, and p95
radius instability was `1.5420/1.4557` against `0.25`. A smaller-radius diagnostic did not restore
local linearity. Authorization remained unopened and `Contribution=0`.

## v20 Finite Target Identifiability Study

v20 implemented the target-measurement redesign requested by the v19 audit. It used six new tasks,
20 states, 60 fresh real-Agent realizations, 16 Estimation records, 16 Validation records, and a
frozen but unopened 16-record Authorization partition. Estimation and Validation were each split
into four mutually exclusive Objective micro-splits.

The frozen direction design contained 14 quotient coordinates and 31 rows: seven direct anchors,
seven block-2 rows, eight block-4 rows, eight block-7 rows, and one null row. Three perturbation
ratios were normalized against the measured global parameter-step norm and evaluated in both
directions. The formal study completed 186 observations per role and 372 overall.

Execution integrity passed again. Maximum parameter-step ratio relative error was `4.3255e-7`,
maximum Gradient recomposition relative error was `0.0073369`, minimum recomposition cosine was
`0.9999732`, and null Objective delta was exactly zero.

Finite-target identifiability nevertheless failed:

| Metric | Estimation | Validation | Frozen requirement |
| --- | ---: | ---: | ---: |
| Direct anchor identifiable rate | `0.0000` | `0.0000` | `>= 1.0000` |
| Maximum direct slope CV | `34.5470` | `4.3135` | `<= 0.5` |
| Maximum p95 nonlinearity ratio | `16.0095` | `63.3579` | `<= 0.25` |
| Maximum block reconstruction error | `1.8606` | `1.8830` | `<= 0.15` |
| Block direction agreement | `0.6522` | `0.5652` | `>= 0.8` |

All fourteen role-wise direct-anchor confidence intervals crossed zero. Only four of seven direct
coordinate signs agreed across Estimation and Validation, so the combined `0.5714` agreement also
failed its frozen `1.0` gate. Block-size error was not monotonic, and direct anchors themselves
were unstable; the evidence therefore localizes the blocker to Objective-level slope
observability, not only to Hadamard-style direction interaction.

The combined status is `failed`; GP-C was not evaluated; Authorization observation count is zero;
and the only valid transition is `retain_contribution_zero_and_redesign_target_measurement`.

## Authorization State

The scientifically correct state is:

- strict-FP32 numeric execution status: `passed`;
- v20 finite-target identifiability status: `failed`;
- v22 Development exact-target execution status: `passed`;
- v22 primary practical-equivalence status: `30/30`;
- v22 all-state practical-equivalence status: `100/100`;
- v22 meaningful-beyond-MPE count: `0/100`;
- v23 final Explorer qualification status: `failed`;
- v23 Factorial Discovery rollout count: `0/1800`;
- `gp_c_evaluated=false`;
- `authorization_objective_access=forbidden`;
- `authorization_objective_observation_count=0`;
- `production_authorized=false`;
- `contribution_authorized=false`;
- v23 report next permitted stage: `protocol_repair_only` under a new frozen contract;
- VTDO updates, Student training, and downstream claims remain unauthorized.

The current evidence establishes reliable strict-FP32 execution and a precise exact one-step target
on Development. It also shows that every observed Development coordinate is materially below the
current MPE. This neither validates nor falsifies GP-C or theoretical Contribution: a proxy cannot
be meaningfully ranked against a Development target with no practically meaningful coordinates,
and no fresh Validation result exists.

## Next Step

Do not rerun GP-C, open Authorization, issue the 60-task Validation contract, or launch the reserved
v23 Discovery. The final v9 qualification is a negative outcome under its frozen gates. Any next
attempt must be a separately identified Agent-environment redesign with new tasks and unchanged
scientific claim boundaries; it cannot relax v9 thresholds or reinterpret its partial valid cells
as a pass. Objective Support remains a separate unresolved bottleneck and cannot be repaired by
changing Explorer models alone.

## Authoritative References

- `docs/finance_v25_26_v25_29_answer_contract_and_confirmation_report.md`
- `docs/finance_v20_target_identifiability_report.md`
- `docs/finance_v22_development_power_plan.md`
- `docs/finance_v22_development_exact_target_report.md`
- `docs/finance_v23_capability_sensitive_agent_plan.md`
- `docs/finance_v23_explorer_runtime_factorial_report.md`
- `docs/finance_v19_sealed_causal_pilot_report.md`
- `docs/finance_v18_sealed_numeric_authorization_report.md`
- `docs/finance_v17_numeric_root_cause_report.md`
- `docs/finance_v16_numeric_contract_validation_report.md`
- `docs/finance_v14_real_agent_gradient_projection_report.md`
- `docs/vtdo_experiment_protocol.md`
- `docs/valid_trajectory_distribution_optimization.md`
- `docs/server_recovery.md`
- `artifacts/vtdo_experiment/finance_v20_target_identifiability_study_p2_v1_20260806/combined_report.json`
- `artifacts/vtdo_experiment/finance_v20_target_identifiability_study_p2_v1_20260806/estimation_report.json`
- `artifacts/vtdo_experiment/finance_v20_target_identifiability_study_p2_v1_20260806/validation_report.json`
- `artifacts/vtdo_experiment/finance_v17_sealed_numeric_candidate_retry_v2_20260806/report.json`
- `artifacts/vtdo_experiment/finance_v17_numeric_root_cause_dev20_val20_temp02_v13_20260805/report.json`
- `artifacts/vtdo_experiment/finance_v17_numeric_root_cause_dev20_val20_temp02_v13_20260805/frozen_numeric_contract.json`

## v25.22-v25.23 Mechanism Repair And Information Geometry

The v25.21 Candidate Verification and State-dependent Stopping mechanisms were repaired without
rerunning the two already-replicated recovery mechanisms. The final Flash Development run
completed 96/96 rollouts and froze both repaired mechanisms. A new held-out Population persisted
the Development Selection Freeze identity and passed every static freshness, semantic, scenario,
and public/Oracle isolation gate.

Held-out Confirmation completed 100/100 rollouts. Runtime eligibility, API transport, bounded JSON,
Observation replay, and authority integrity were 100%, with zero Runtime pathology. Candidate
Verification was behavior-successful on 25/25 mechanism trajectories. Stopping was evaluable and
behavior-successful on 19/25; the six unevaluable outcomes remain model failures. Both mechanisms
passed the unchanged matched-pair criteria, so all four frozen mechanisms are independently
confirmed.

The corrected v25.23 v2 geometry audit used 20 mechanism-required tasks and 100 rollouts from the
two held-out Confirmation sources. Coverage was balanced at five groups per mechanism and boundary
mass was 45%. The v2 replay freezes every numerical/source-contract dependency and uses the same
Fisher weights for the information matrix, centering, and general-difficulty regression. The
initial unweighted-residual v1 artifact is superseded.

| Matrix | Numerical rank | Effective rank | Condition number |
| --- | ---: | ---: | ---: |
| Raw | 5 | 1.20598 | 1270.31 |
| General-difficulty residual | 3 | 2.40054 | 5.26 |

The raw distribution remains dominated by a common direction. Removing that direction restores
numerical conditioning but leaves only three independent residual directions, below the frozen
rank-4 and effective-rank-3 requirements.

The current authorization state is:

```text
all_four_mechanisms_confirmed = true
information_geometry_ready = false
pro_sparse_anchor_authorized = false
beneficiary_screening_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = capability_mechanism_support_redesign_only
```

Mechanism confirmation is retained as a positive result. The current task support is rejected as a
well-conditioned capability distribution. See
`docs/finance_v25_22_v25_23_capability_mechanism_repair_and_geometry_report.md`.

## v25.30-v25.33 Stable Capability-decision Support

The measurement contract now uses `capability_contract_success`: semantic answer validity must
co-occur with the registered Host trigger/resolution behavior and no post-completion violation.
Public tasks no longer expose oracle mechanism identity or canonical repair values.

v25.33 completed 480/480 fresh Flash rollouts. Runtime transport, bounded JSON, Observation replay,
and authority integrity were 100%, with zero reported Runtime pathology. The common Top-4 geometry
passed with effective rank 3.5929, condition number 3.4290, and 99.90% bootstrap joint-geometry
success.

The experiment nevertheless failed its preregistered parent-support contract. State-dependent
Stopping contributed only 3.16% of information, had one nonzero task, and had a zero bootstrap
lower bound. Confirmation and Pro remain blocked. Failure-artifact replay also identified a
state-dependent unreachable `uncertain_source_coverage` recovery path, which must be repaired
before a new Stopping boundary calibration.

```text
runtime_measurement_ready = true
common_top4_geometry_passed = true
capability_support_admitted = false
fresh_confirmation_authorized = false
pro_sparse_anchor_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stable_support_redesign_only
```

See `docs/finance_v25_30_v25_33_stable_capability_decision_report.md`.

## v25.34 Stopping Boundary Calibration

v25.34 used one fresh Population, five State-dependent Stopping tasks, and 12 Flash realizations
per task. The first 60-rollout run proved that source coverage was repaired but conflict resolution
remained 0/12. Trace replay identified a generic Runtime defect: typed public conflict dimensions,
candidate actions, and the action-selection rule were omitted from the next decision Prompt and
were lost entirely after an identical failed-call block.

The paired v2 run changed only the content-hashed implementation. It preserved the latest typed
prerequisite contract without selecting the correct action for the model. Runtime remained 60/60
eligible with zero pathology. Conflict resolution reached 10/12, complete Contract success reached
9/12, and the task became a boundary response at 0.75. All frozen v25.34-v2 gates passed.

```text
runtime_measurement_ready = true
stopping_instrument_repair_validated = true
boundary_signal_observed = true
fresh_stable_support_development_permitted = true
historical_result_reclassified = false
fresh_confirmation_authorized = false
pro_sparse_anchor_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = fresh_stable_support_development_population_build
```

See `docs/finance_v25_34_stopping_boundary_calibration_report.md`.

## v25.35 Cross-population Stable-support Development

v25.35 froze all 30 prior submechanism populations, built three mutually disjoint fresh
populations, and completed 480/480 DeepSeek V4-Flash rollouts. Every population passed exact
execution integrity, terminal resolution, Observation replay, authority integrity, zero L0-L2
failures, zero Runtime pathology, and complete typed failed-action context replay.

Stable support did not generalize. Only Population 2 passed all per-population support gates.
Population 1 had a zero Stopping bootstrap lower bound; Population 3 had only one nonzero Stopping
task and a 78.25% joint-geometry bootstrap pass rate. All three pairwise Top-4 bootstrap alignment
rates failed at 38.10%, 54.35%, and 23.30%.

The pooled diagnostic would have passed with 99.95% joint geometry and a 5.60% Stopping LCB, which
empirically confirms that pooled results cannot rescue population failures.

```text
all_population_runtime_ready = true
all_population_capability_support_admitted = false
cross_population_alignment_ready = false
development_admitted = false
fresh_confirmation_preparation_authorized = false
pro_sparse_anchor_authorized = false
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stable_support_redesign_only
```

See `docs/finance_v25_35_cross_population_stable_support_report.md`.


## v25.24 Submechanism Direction Design

v25.24 replaced parent-mechanism labels with 24 typed submechanism candidates: six candidates
inside each of the four independently confirmed mechanisms. A deterministic 6-choose-5 search per
parent evaluates 1,296 balanced designs before any model response is observed. Demand vectors are
mechanically derived from typed Action primitives and Evidence dependencies, then projected off the
common workflow direction.

The selected 20-task design passes every frozen structural gate:

- residual numerical rank 6;
- residual effective rank 4.698069;
- residual condition number 18.862716;
- high-cosine pair fraction 9.47%;
- every axis supported by at least two parent mechanisms;
- 20 distinct workflow backbones.

Only 5/20 selected variants currently have both a Host intervention and real-Finance Materializer
implementation. Static success therefore does not authorize an API run:

```text
structural_geometry_ready = true
runtime_population_ready = false
api_calls = 0
gpu_jobs = 0
next_permitted_stage = submechanism_runtime_implementation_only
```

Flash, Pro, Beneficiary, Exact Target, GP-C, production Contribution, and Student training remain
blocked. See `docs/finance_v25_24_submechanism_direction_design_report.md`.

## v25.36 Stopping Shape Stability Development

v25.36 first replayed v25.35 offline and rejected a Stopping-only explanation for the observed
cross-population geometry drift. It then changed the primary sampling unit from repeated rollout
to independent Finance task: six Stopping Shapes each received four fresh tasks spanning retrieval
join, calculation chain, definition reconciliation, and verification-sensitive selection, with
eight Flash realizations per task.

All 192/192 rollouts completed. Execution integrity, terminal resolution, API transport, bounded
JSON resolution, Observation replay, and authority integrity were 100%; Runtime pathology and
L0-L2 failures were zero. The measurement instrument therefore remains valid.

Shape-level stable support did not fully pass. `authority_coverage_gap` and
`contextual_resolution_choice` passed every task-level gate. `partial_required_evidence` failed
only its hierarchical bootstrap information lower bound. `single_dimension_conflict` was too hard
in three of four strata and derived all observed information from one task. The
`verified_extra_call_cost` control also failed its success and heterogeneity gates, while the
error-risk control passed.

```text
runtime_measurement_ready = true
all_shapes_admitted = false
difficulty_policy_frozen = false
fresh_cross_population_preparation_authorized = false
pro_api_call_count = 0
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stopping_shape_support_redesign_only
```

No pooled estimate, post-hoc task selection, threshold relaxation, or post-hoc Finalizer repair was
used. The only permitted transition is a fresh Shape-redesign Development. See
`docs/finance_v25_36_stopping_shape_stability_report.md`.

## v25.37 Stopping Shape Redesign Development

v25.37 materialized 48 fully fresh Finance tasks: six Shapes, four structural strata, two tasks per
Shape-stratum cell, and eight Flash realizations per task. The three v25.36 passing items were
frozen as positive controls; only partial evidence, single conflict, and extra-call cost received
typed redesigns.

All 384/384 rollouts completed. Runtime execution, terminal resolution, API transport, bounded
JSON, Observation replay, and authority integrity were 100%; Runtime pathology and L0-L2 failures
were zero. All run-manifest hashes and four 384-row denominators verify.

The Shape result remains negative:

- authority coverage gap and contextual resolution choice replicated;
- partial required evidence was saturated in six of eight tasks;
- single-dimensional conflict moved from floor to ceiling but had only four nonzero tasks;
- verified extra-call cost retained a full zero-to-one task range;
- verified extra-call error risk regressed to 0.7188 and missed its 0.75 control threshold.

~~~
runtime_measurement_ready = true
positive_control_regression_count = 1
redesigned_shape_admission_count = 0
all_shapes_admitted = false
difficulty_policy_frozen = false
fresh_three_population_preparation_authorized = false
pro_api_call_count = 0
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stopping_shape_redesign_only
~~~

Both post-completion controls had 100% ordered Host behavior but lower full valid-trajectory
success. This is a preregistered-response diagnostic, not permission to rescue the failed controls.
A future Development must prospectively freeze the Control estimand and redesign the task
dependencies before any new API call. Pro, Beneficiary, Exact Target, GP-C, Contribution, VTDO
updates, and Student training remain blocked.

See `docs/finance_v25_37_stopping_shape_redesign_report.md`.

## v25.40 Stopping Shape Policy Development

v25.40 completed 384/384 fresh Flash rollouts after repairing the Partial tool-output
manifest and replacing descriptive conflict labels with typed public Evidence states.
All Runtime integrity gates passed. Authority and Partial were admitted and both
controls passed; Contextual and Conflict did not.

A causal audit found query-based states were emitted only after their required record
had already been selected and used, making the required query redundant. The next
stage is restricted to a fresh causal-timing repair.

```text
estimand_semantics_frozen = true
shape_support_policy_frozen = false
boundary_candidate_admission_count = 2/4
runtime_control_pass_count = 2/2
pro_api_call_count = 0
exact_target_evaluated = false
gp_c_evaluated = false
production_contribution = 0
next_permitted_stage = stopping_shape_causal_timing_repair_only
```

See `docs/finance_v25_40_stopping_shape_policy_report.md`.

## v25.43-v25.44 Stopping Instrument Audit

v25.43 and the first v25.44 run historically appeared to validate the
agent_tool_observation.v2 side channel and, in the first v25.44 population,
admitted all four boundary candidates plus both controls. A hardened Snapshot v3
repair subsequently restored exact Definition-pair capacity in the real Finance
Archive:

    Archive scanned / eligible        = 564,297 / 512,845
    base / companion / final facts    = 151,022 / 92 / 151,114
    period / definition pair capacity = 75,509 / 90
    Snapshot status                   = passed

The hardened fresh run completed 384/384 Flash rollouts. Its diagnostic result
was 3/4 boundary candidates and 2/2 controls, with Authority failing only
between-task heterogeneity:

    stopping behavior success       = 268/384 = 69.79%
    full valid-trajectory success   = 183/384 = 47.66%
    answer-semantic success         = 194/384 = 50.52%
    API calls / model tokens        = 3,700 / 19,293,960
    estimated cost                  = USD 1.9192

A recursive raw audit then found the actual P0: 219 of 1,449 tool observations,
covering 32 of 48 tasks, still embedded Host-only event metadata inside nested
strict business results (host_event 219 times and host_event_sequence 63
times). The previous zero-leak audit checked only top-level keys.

The Runtime now recursively rejects reserved Host metadata, emits trigger and
resolution events only through the outer typed side channel, recursively audits
historical predecessors, and verifies aggregate response rates against atomic
Shape rows. Repository-wide validation passes: Ruff, Mypy over 318 source files,
and 733 tests.

All historical v25.43/v25.44 Shape outcomes remain immutable diagnostics but are
invalid for authorization:

    estimand semantics                 = retained
    shape support policy               = not frozen
    three-population preparation       = withdrawn
    Pro / Beneficiary / Exact / GP-C   = blocked
    production Contribution            = 0
    next permitted stage               = fresh instrument-reset protocol only

See:

- docs/finance_v25_43_v25_44_stopping_role_position_validation_report.md
- docs/finance_v25_44_snapshot_v3_capacity_hardening_report.md
- docs/finance_v25_44_hardened_replication_instrument_audit.md
