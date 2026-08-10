# Finance v23 Capability-Sensitive Agent Experiment Plan

Status date: 2026-08-11

Current status: `paired_explorer_calibration_failed_discovery_not_permitted`

## Motivation

Finance v22 measured an exact one-step Development target on 30 tasks, 100 accepted states, 500
realizations, and eight Objective micro-splits. The target was numerically precise, but all 100
state coordinates were practically equivalent under their update-derived MPE. Objective support,
not realization sampling, accounted for `99.9443%` of nested measurement variance.

The next experiment therefore does not mechanically enlarge the same bare-model population and
does not open the proposed 60-task Validation. It first tests whether a real, replayable Agent
environment creates capability-sensitive trajectory states:

```text
Agent-runtime validity
-> capability-frontier task screening
-> new Agent state space and Reachability
-> larger Development exact target
-> fresh exact-target Validation
-> independent GP-C authorization
-> VTDO rounds and Student training
```

The hypotheses are:

1. model-selected tools, queries, verification, recovery, and stopping create more valid behavioral
   states than direct generation or a Host-scripted tool sequence;
2. Beneficiary frontier tasks expose larger state contrasts than tasks already mastered or wholly
   out of reach;
3. broader tasks and Objective support reveal exact-target coordinates beyond MPE;
4. only after an independently authorized Contribution proxy may full `(C+N)` VTDO be tested.

## Implemented Runtime Boundary

The runtime follows `model decides, Host executes, frozen environment, replayable observations`.

The model may decide:

- tool selection and public arguments;
- query reformulation;
- whether to continue after an Observation;
- recovery after a failed tool call;
- when to verify and stop;
- the final answer and citations.

The Host owns:

- tool execution, timeout, and budget enforcement;
- immutable source, content, and snapshot-time hashes;
- typed Observations and execution identity;
- independent validity and quotient-state assignment.

Gold Evidence IDs, Oracle programs, reference answers, Proof Graphs, and target quotient states are
not model-visible. The runtime records public rationale summaries and structured decisions; it does
not request hidden chain-of-thought.

The domain-neutral implementation is in:

- `runtime/tools.py`: frozen tool/environment and content-addressed Observation contracts;
- `runtime/agent/iterative.py`: one-action-per-turn scripted/autonomous loop;
- `phase1_pro_flash_agent_pilot.py`: paired Explorer identity and isolated task partitions;
- `phase1_explorer_runtime_factorial.py`: immutable three-arm design and fail-closed gates;
- `phase1_explorer_runtime_factorial_runner.py`: checkpointed parallel execution and reports.

Required public input and output fields are executable Host gates rather than prompt-only
descriptions. Missing model arguments, unknown fields, or malformed successful tool outputs stop
the run before an Observation can enter the trajectory.

Finance only registers concrete tool semantics in `domains/finance/agent_tools.py`:

```text
search_archive
open_document
query_structured_fact
calculator
normalize_metric_unit_period
cross_check_evidence
```

The contracts, deterministic fake runtime, read-only Archive executors, independent Finance
verifier, and checkpointed API runner are tested. The final v9 API qualification completed on
2026-08-11; it failed its preregistered completion and JSON-contract gates, so factorial Discovery
did not run.

## Pro--Flash Paired Explorer Factorial

The paired experiment treats `deepseek-v4-pro` and `deepseek-v4-flash` as different Explorer
identities. There is no fallback and no claim that Flash is an in-place replacement. Both models
receive the same public tasks, frozen Archive, Host runtime, temperature, `top_p`, tool budget, and
90,000-token cumulative rollout budget. The primary contrasts are:

```text
Flash vs Pro within Autonomous Agent
Autonomous Agent vs Scripted Tool within each model
```

The preferred later materialization mechanism remains Contract B: Flash may discover states, but
Pro would rematerialize any selected public state condition under the same verifier. Contract A,
where Flash also materializes training trajectories, is only an end-to-end supplementary arm.
Neither contract was opened because calibration failed.

The final frozen identities are:

| Item | Identity |
| --- | --- |
| Base contract | `finance_pro_flash_paired_pilot_contract:61618f1d...` |
| Factorial contract | `finance_explorer_runtime_factorial_contract:3c627a08...` |
| Runtime | `finance_archive_interactive_runtime.v3` |
| Toolset | `finance_archive_agent_toolset.v4` |
| Solver | `iterative_agent_solver.v9` |
| Quotient mapper | `dependency_wl_canonicalizer.v6` |

The six calibration tasks and 30 reserved Discovery tasks are balanced over the six Finance task
families. The 18 reserved exact-target tasks were frozen but never opened. v9 excludes 150 prior
task identities: 42 historical v20/v21/v22 identities and the 108 fresh tasks consumed by v6-v8.

## Three-Arm Pilot

The same 24-30 tasks are assigned to all arms, with six families and four or five tasks per family.

| Arm | Model authority | Host authority |
| --- | --- | --- |
| Direct/Bare | direct answer or complete response | validity verification |
| Scripted Tool | public query arguments and answer | frozen tool order and execution |
| Autonomous Agent | tool, query, continue, recovery, stop, answer | execution and budgets |

Scripted and Autonomous use the same tool manifest, Evidence snapshot, token budget, tool-call
budget, timeout, and verifier. Direct/Bare is a reference baseline and is not presented as a
strictly identical tool condition.

Pre-outcome support must satisfy:

- 8-12 unconditional runs per Task x Arm;
- 5-8 state-conditioned attempts per selected state;
- 12-18 exact-target tasks, with two or three per family;
- a new Explorer identity, state-catalog version, Reachability manifest, initial distribution, and
  materialization contract;
- frozen independent-validity-verifier, quotient-state-mapper, and exact-target-design manifests;
- explicit exclusion hashes for v20, cancelled v21, and v22 populations.

## Pilot Measurements

Agent execution:

- tool-call success;
- query reformulation and error recovery;
- Evidence provenance completeness;
- verification success and stop-decision quality;
- validity rate and cost.

State-space sensitivity:

- accepted states per task and natural state entropy;
- decision-trace diversity and off-target transitions;
- state-conditioned on-target rate and Reachability interval width;
- differential token and gradient fractions;
- state update-vector distance;
- `abs(exact target) / MPE`, near-MPE rate, and meaningful-coordinate rate.

Every aggregate report is content-bound to all three trajectory manifests, raw paired metrics, the
state catalog, Reachability, and the exact-target report.

## Fail-Closed Advancement

The Pilot advances only when all five preregistered gates pass:

1. Autonomous improves state coverage or entropy, including a minimum paired-task fraction;
2. it produces nontrivial planning, verification, reformulation, or recovery states;
3. validity, tool success, provenance, and stop quality remain above frozen thresholds;
4. near-MPE or meaningful-coordinate rate exceeds both baselines;
5. differences affect supervision gradients, not only trajectory length.

Threshold values are required by the typed contract and must be frozen after the capacity audit but
before the first API outcome. A failed gate permits only `agent_environment_redesign`. A passing
Pilot permits only `beneficiary_frontier_screening`; it cannot open Validation, Authorization, or
GP-C.

## Capability Frontier And New Population

After a passing Pilot, build 150-300 frozen-Archive candidates spanning the six existing families,
multi-document joins, period and definition alignment, source conflict, recovery, and long Evidence
lineage. The frozen Qwen2.5-7B Beneficiary screens direct answer, NLL, tool choice, query,
calculation, verification, and recovery errors.

Development-only rules retain tasks where the Beneficiary is partially capable but unstable.
Fully mastered and wholly unreachable tasks are excluded using predeclared rules, never by looking
at Contribution outcomes. Switching from bare to Agent generation creates a new kernel and requires
new Explorer, catalog, Reachability, `pi_0`, and materialization identities.

## Exact Target, Validation, And GP-C

After the Agent population is qualified, run a new 30-48 task Development study with 3-5 states per
task, initially five realizations per state, and 64-128 Objective records. Re-estimate variance
because the generation kernel has changed.

Only then may a fresh 60-task Validation be preregistered. Tasks, Evidence versions, semantic
signatures, trajectories, realizations, and Objective records must be disjoint from Pilot and
Development. Significance and meaningful-beyond-MPE remain separate axes. A GP-C comparison may be
opened only when the Development-frozen Validation rule finds a sufficient, distributed, stable set
of meaningful coordinates.

If the exact target remains practically equivalent, the permitted optimization is explicitly
`Novelty-anchored / No-C VTDO`. If GP-C fails, the same No-C path applies. Full `(C+N)` VTDO is
allowed only after independent GP-C authorization.

## Student Evaluation

Any later training experiment fixes task marginal, supervision tokens, base model, LoRA contract,
three training seeds, and Benchmark snapshots. It compares Bare, Scripted, Agent validity,
Novelty-only, No-C round 1/3, Full `(C+N)` when authorized, random state, and CCGR.

FinQA and TAT-QA remain external benchmarks, but the Agent study also requires frozen tool-choice,
query, grounding, calculation, verification, recovery, stopping, end-to-end answer, and cost
metrics.

## Current Claim Boundary

Real v23 calibration trajectories now exist, but the final qualification status is `failed`.
There is no v23 Discovery population, capability-frontier population, state-conditioned study,
exact target, Validation result, GP-C score, VTDO update, or Student result. Production
Contribution remains zero. The result establishes an executable and fail-closed experiment and a
negative Explorer qualification outcome; it is not evidence that the Agent hypothesis is true or
that Flash improves capability sensitivity. See
`docs/finance_v23_explorer_runtime_factorial_report.md`.
