# Finance v12 Real-Agent Experiment Preflight Report

Date: 2026-08-03  
Active protocol: `vtdo.v12` / `aevtdr.v7`  
Scope: real Finance Archive tasks, model-controllable Agent trajectory states, and fresh GP-C preparation

## 1. Decision

The v12 real-Agent entry path is code-complete and its development and sealed-authorization task
populations now pass strict public-corpus disjointness. The result is an experiment preflight, not a
GP-C authorization. No fresh DeepSeek trajectory, state gradient, finite target, or authorization
credential was created in this run.

Current status:

```text
real Finance task population:             passed
public-state controllability:              passed
A/B full-corpus disjointness:              passed
initial-distribution fail-closed contract: passed in tests
state-realization resume contract:         passed in tests
fresh external Explorer trajectories:      blocked by missing server credential
fresh GPU gradient experiment:             deferred while all eight GPUs are occupied
production GP-C authorization:             not run
```

## 2. Population Artifacts

| Role | Partition | Tasks | States | Requestable | Artifact SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| Development | A | 30 | 120 | 120 | `7e5d2e2d02431505a63b75f424882644e7411a8fbd77173133b383b21e7bd2ab` |
| Authorization | B | 30 | 120 | 120 | `db79801412c07880aecdeb00ee2723bcd05c68320cd4cc6c7659d4f96f1553ea` |

The two populations have the same frozen task-family target mix:

```text
derived_growth_comparison  12
registered_ratio             6
temporal_growth              5
temporal_absolute_change     4
temporal_average             3
```

Each population attempted 38 candidates. Thirty were accepted and eight were rejected because
quotient-state deduplication left only two states, below the frozen minimum of three. Every accepted
task exposes four host-requestable public conditions under `semi_open + plan_hidden`; the Oracle
program and Gold Evidence remain hidden.

## 3. Independence Audit

The authorization build consumed the complete development artifact as a frozen exclusion manifest.
Its report binds the exact development SHA and excludes all 327 development public Evidence
versions before selection.

Strict overlap counts:

| Identity | Overlap |
| --- | ---: |
| Agent task ID | 0 |
| Source task ID | 0 |
| Gold Evidence version | 0 |
| Gold Source Record | 0 |
| Distractor Evidence version | 0 |
| Distractor Source Record | 0 |
| Complete Public Corpus Evidence version | 0 |
| Complete Public Corpus Source Record | 0 |

Machine-readable evidence:

`artifacts/vtdo_experiment/finance_v12_agent_population_auth30_v2_20260803/finance_agent_population_disjointness_report.json`

Report hash:

`finance_agent_population_disjointness_report:e3508ba515033bb666e26cb2fe41100f07ccfd6f46f6aa851fff2966094cb45e`

Entity, predicate, definition, and source-document categories may overlap by design; these are
semantic strata rather than sample identities. The strict identities above are fully disjoint.

## 4. Contract Repairs Completed

### Population v2

`FinanceAgentPopulationReport` now binds an optional excluded-population artifact SHA and excluded
Evidence-version count. `FinanceArchiveBindingProvider.contract_cases()` accepts a frozen exclusion
set and fills the requested quota only from cases whose complete Public Corpus is disjoint. Failure
to fill the quota is fail-closed.

### Initial distribution v4

The unconditioned Explorer now requires at least four replicas per task. A report is `passed` only
when every frozen replica is independently valid and maps to the registered state catalog for every
selected task. Positive prior smoothing can preserve support, but can no longer hide failed,
invalid, or off-catalog observations.

Checkpoint reuse is equally strict: only a completed, valid, catalog-hit observation is resumed.
Failed, invalid, and off-catalog jobs are retried on the next invocation while historical attempt
telemetry remains preserved.

### Cost telemetry

DeepSeek V4 Pro pricing is frozen in the model config with cache-hit and cache-miss input rates,
output rate, source URL, and check date. Provider cache counters are used when available; otherwise
all input is conservatively priced as cache misses. Zero placeholder rates no longer produce a
misleading zero-cost report.

## 5. Costed Execution Ladder

Historical real DeepSeek telemetry contains 107 unique HTTP calls:

```text
prompt tokens:     median 5,631; P95 9,529; max 18,699
completion tokens: median 1,302; P95 3,128; max 3,767
```

A `semi_open + full_response` trajectory uses one search call and one answer call. One contract
repair is allowed per stage.

| Stage | Trajectories | Calls, no repair | Absolute configured call ceiling |
| --- | ---: | ---: | ---: |
| 2-task smoke: pi0 | 8 | 16 | 32 |
| 2-task smoke: 3 realizations x 4 states | 24 released | 48 | 288 |
| 30-task development: pi0 | 120 | 240 | 480 |
| 30-task development: state realizations | 360 released | 720 | 4,320 |

For the 30-task successful path, 960 calls correspond to roughly USD 3.44 at historical median
token usage or USD 6.59 at historical P95 token usage under the frozen pricing. The configured
absolute retry ceiling is deliberately much larger and must not be used as a normal operating
budget. Checkpointing makes staged escalation and interruption inexpensive.

No external API call was made during this preflight, so new API spend is zero.

## 6. Resource Observation

At the final resource check all eight A100-SXM4-80GB devices were occupied by another user's
Ray/vLLM distributed job at 69-95 percent utilization. This run did not share, interrupt, or kill
that workload. The API trajectory stages do not require GPU; GPU work begins only after valid state
realizations exist.

`DEEPSEEK_API_KEY` was absent from the process environment. Credentials are intentionally accepted
only through the configured environment variable and are never placed in CLI arguments, JSON
config, checkpoints, telemetry, or this report.

## 7. Next Executable Stage

Run the two-task development smoke first:

```bash
.venv/bin/python -m trusted_synthesis.experiments.vtdo_experiment.phase1_initial_distribution \
  --artifacts-path artifacts/vtdo_experiment/finance_v12_agent_population_dev30_v2_20260803/finance_agent_task_states.jsonl \
  --model-config-path config/deepseek_v4_pro_agent_smoke.json \
  --archive-config-path config/finance_archive.json \
  --output-dir artifacts/vtdo_experiment/finance_v12_initial_distribution_dev2_20260803 \
  --task-count 2 \
  --replicas-per-task 4 \
  --workers 2
```

Only after all eight observations are valid and catalog-hit should state materialization run with
the emitted `finance_initial_distribution_report.json`. A two-task state-realization smoke precedes
5-task and 30-task scaling. Gradient support scaling, multi-radius finite targets, GP-C proxy, and
sealed authorization remain downstream and cannot consume historical v11/v18 artifacts.

## 8. Verification

Final local verification completed with:

```text
git diff --check: passed
Ruff:             passed
Mypy:             229 source files passed
Pytest:           289 passed in 115.56s
```

## 9. Post-preflight Real-Agent Projection Validation

Date: 2026-08-04
Scope: one real comparison task, four independent DeepSeek V4 Pro trajectories, and the
projection-aware quotient-state contract.

This section supersedes the earlier credential-blocked status only for the narrow initial-
distribution smoke. Gradient Projection authorization and downstream training remain separate.

### 9.1 Defect and repair

The earlier v10 run completed four trajectories and all four passed answer semantics, but none
entered the frozen state catalog. The model naturally executed lookup -> lookup -> compare while
the Oracle program expressed the equivalent direct compare. Treating this as an invalid answer was
too strict; ignoring the lookup nodes would have erased a real trajectory-cost distinction.

The repair therefore keeps both requirements:

- lookup is registered as a transparent_projection program role;
- each projection is independently replayed from immutable Evidence and remains fail-closed;
- the Host preserves the source Evidence identity through lookup output;
- the verifier maps verified candidate projection IDs to stable roles of the form
  projection:{oracle_node}:{input_index};
- compact and semantic retrieval each have direct and projection-aware quotient states;
- quotient-state, canonicalizer, decision-trace, Population, and initial-distribution versions
  were advanced rather than retaining a compatibility branch.

Tampering a projected selected_ref is rejected. The same contract is covered by Finance and Legal
tests, so the Core behavior is not Finance-specific.

### 9.2 Rebuilt population

Artifact:
artifacts/vtdo_experiment/finance_v12_agent_population_dev30_v10_stable_projection_aliases_20260804

Report ID:
finance_agent_population_report:22997d63de4e22a4b10122ae7d0b327e674eeb1be277ab0fc315dcac7cf59b22

Artifact SHA-256:
82313bf751254e4b765e132468a307b4e4e45f538b74ff4fa0d36ec3e35cb7b4

| Measure | Result |
| --- | ---: |
| Requested tasks | 30 |
| Attempted tasks | 31 |
| Accepted tasks | 30 |
| Accepted states | 100 |
| Requestable states | 100 |
| Comparison tasks with five states | 5 |
| Other tasks with three states | 25 |
| Host-blocked candidate rejections | 1 |

All 30 accepted tasks pass Gradient task selection. Comparison catalogs contain exactly:
compact_direct, compact_projection, semantic_direct, semantic_projection, and broad_direct.

### 9.3 Real API result

Artifact:
artifacts/vtdo_experiment/finance_v12_initial_distribution_dev1_v12_stable_projection_aliases_20260804

Report ID:
finance_initial_distribution_report:51ffbcfd3edb52567c5c6b53b64c34ef9f73972daf250a87557f022ca7572bcc

| Measure | Result |
| --- | ---: |
| Requested trajectories | 4 |
| Completed trajectories | 4 |
| Independently valid | 4 |
| Catalog hits | 4 |
| Off-catalog valid | 0 |
| Complete observation tasks | 1 |
| API calls | 12 |
| HTTP successes | 12 |
| JSON contract successes | 12 |
| Prompt tokens | 50,124 |
| Completion tokens | 3,283 |
| Total tokens | 53,407 |
| Config-estimated cost | USD 0.022230646 |
| Fallback calls | 0 |

The provider model inventory exposed deepseek-v4-pro and deepseek-v4-flash. Every request used the
required deepseek-v4-pro model. The cost is the repository configuration estimate based on provider
cache counters, not a claim about the final provider invoice.

All four trajectories selected two Evidence items, executed two transparent lookups followed by
compare, returned the winning raw Evidence ID, and mapped to compact_projection. The answer was
stable across replicas: the diluted EPS difference was 10.80 USD per share.

The empirical observations cover one of five catalog states. Full support in the emitted posterior
comes from the explicitly frozen positive prior; it must not be interpreted as empirical model
coverage of all five states.

### 9.4 Verification and decision

Final repository verification:

- Ruff: passed;
- Mypy: 229 source files passed;
- Pytest: 301 passed in 115.30 seconds;
- git diff --check: passed;
- credential-pattern scan over config/src/tests/docs: no match;
- no Population, API, or Pytest process remained running.

Decision: the projection-equivalence path is validated for this narrow real-Agent smoke, including
Host execution, independent replay, stable state canonicalization, and empirical distribution
materialization. It is not yet evidence for cross-task state frequencies, Gradient Projection
quality, contribution authorization, or downstream training utility. The next costed stage should
sample multiple task families before state realizations and GP-C estimation.
