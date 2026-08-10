# Finance v22 Development Population And Power Study

Status date: 2026-08-08

Current status: `superseded_as_immediate_next_step_by_agent_runtime_pilot`. The initial Explorer
distribution, the complete DeepSeek v13 state-conditioned population, 500 state gradients, eight
Objective gradients, and 4,000 exact-target observations are complete. The original target report
remains immutable; a separate v22.1 analysis corrects inference and study sizing without rewriting
its observations.

The v22.1 recommendation is retained as a statistical reference. It is not an active Validation
contract: the 2026-08-11 design amendment first tests whether a frozen, Host-executed Agent runtime
creates capability-sensitive states. See `docs/finance_v23_capability_sensitive_agent_plan.md`.

## Scientific Question

v20 showed that strict FP32 execution was reliable while its finite target was not identifiable.
v21 began a larger direct-coordinate run, but it was stopped by operator request before completion
so that the target-observability protocol could be revised. v22 first asks a more basic question:

> What task, Objective-support, and trajectory-realization variance must a target experiment absorb,
> and how many independent tasks are required to detect an effect large enough to change a VTDO
> state probability by two percentage points?

This is a Development-only variance and power study. It cannot inspect Validation or Authorization,
evaluate GP-C, authorize Contribution, or update a VTDO distribution.

## Frozen Development Population

The target population was selected before any v22 Explorer or target outcome was observed. It is
sampled from the existing 420-task real Finance pool while excluding all six v21 target tasks,
their semantic signatures, and their 58 Evidence versions.

| Component | Frozen support |
| --- | ---: |
| Independent target tasks | 30 |
| Finance task families | 6 |
| Tasks per family | 5 |
| Accepted quotient states | 100 |
| States per task | 3-5 |
| Public Evidence versions | 312 |
| Shared Evidence across target tasks | 0 |
| Unconditioned Explorer replicas per task | 10 planned |
| State-conditioned realizations per state | 5 planned |

The six task families are comparison, derived growth comparison, registered ratio, temporal
absolute change, temporal average, and temporal growth.

## Frozen Development Objective Support

The Objective role contains 64 real training records selected from tasks disjoint from both the
v22 target population and the six historical v21 targets. The selector rejects shared task IDs,
semantic signatures, and Evidence versions. The 64 records are frozen into eight deterministic,
mutually exclusive micro-splits of eight records each. Each split covers five or six task families.

No Validation or Authorization partition exists in this artifact. The explicit access fields are
`forbidden`, GP-C execution is false, and production Contribution remains zero.

## Minimum Practical Effect

The engineering MPE is derived from the frozen anchored VTDO update rather than assigned in raw
Objective units. For each task-state coordinate, the implementation finds the minimum centered
state-to-rest Contribution contrast whose isolated change moves the selected next-round state
probability by at least:

```text
delta_pi = 0.02
```

The calculation holds the current distribution, uniform coverage anchor, novelty transform, and
task-conditional Reachability estimates fixed. It reports a state contrast, not only the selected
state's centered amplitude. This remains an engineering threshold, not a business effect or a
claim about downstream model accuracy.

## Planned Development Measurements

The data stage will collect:

- 300 unconditioned DeepSeek Explorer observations;
- exactly five independent state-conditioned realizations for each of 100 states;
- natural state frequencies and entropy by task;
- task-conditional on-target rates and Wilson intervals;
- off-target transition matrices;
- API success, contract repair, token, cost, and retry telemetry;
- the update-derived MPE distribution.

Only after these pre-target quantities were frozen did the Development target study estimate nested
variance across task, task family, Objective micro-split, realization, and numeric replay. The
result is now complete. A post-measurement audit showed that the original homogeneous-mean power
diagnostic is insufficient to freeze the number of task-specific coordinates for GP-C validation,
so the final Validation contract remains unopened.

## Materializer Diagnostics

The unconditioned DeepSeek Explorer stage completed before state-conditioned materialization:

| Measure | Observed |
| --- | ---: |
| Requested trajectories | 300 |
| Valid trajectories | 300 |
| Catalog hits | 298 |
| Valid off-catalog trajectories | 2 |
| API / JSON-contract success | 900 / 900 |

The first DeepSeek state-conditioned run released 315 of 500 requested realizations before the
provider exhausted its prepaid credit. It remains a partial model-sensitivity artifact and is not
silently combined with later local-model runs.

The first local Qwen diagnostic used Action Prompt v11 and Search Prompt v7 with one attempt per
state. The seven-replica serving pool completed every HTTP request, but only 8 of 100 requested
state realizations were independently verified and released:

| Measure | Observed |
| --- | ---: |
| API calls / HTTP successes | 258 / 258 |
| JSON-contract successes | 183 |
| Generation successes / failures | 25 / 75 |
| Independently released trajectories | 8 |
| Invalid trajectories | 16 |
| Off-target trajectories | 1 |

The failure taxonomy localized the remaining issue to Action Plan realization rather than serving
or search. Common failures were truncated or malformed JSON, direct semantic operations emitted for
transparent-projection states, and lookup projections emitted for baseline states. Action Prompt
v12 therefore makes the following generic, public-only changes:

- action catalogs contain only fields required to choose and wire operations;
- baseline and projection modes receive mutually exclusive typed examples;
- public evidence roles, terminal-operation constraints, and topology rules are repeated in a
  final recency block;
- contract repair explicitly changes topology for `state_execution_*` failures;
- the local structured-generation profile uses temperature 0.2 and 2,048 output tokens.

These changes do not let the Host select evidence or construct the operation graph. A fresh
100-state smoke run must pass a predeclared engineering threshold before the five-realization run is
allowed. The failed diagnostic remains immutable and auditable.

The predeclared smoke threshold is: at least 70 of 100 requested states released, 100% HTTP success,
no identity or public/oracle-isolation violation, at most two search-contract failures, at most ten
combined baseline/projection topology failures, at least one release from every registered task
family, and at least one release from every registered state strategy. Failing any item blocks the
500-realization run and permits only another versioned engineering diagnostic.

The Action Prompt v12 smoke also failed this frozen threshold. It released 18 of 100 requested
states after 315/315 successful local API calls and 290 JSON-contract successes. The released set
covered all five registered state strategies, but only comparison, registered ratio, and temporal
absolute change; derived growth comparison, temporal average, and temporal growth had no release.
The dominant action failures were 19 wrong-arity operation plans, including multiple raw Evidence
items batched into a one-input `lookup`, plus six semantic-compatibility failures. Another 38
generated trajectories were rejected by the independent evaluator, but the v3 materialization
report retained only their count rather than their typed validity reports. The 500-realization run
therefore remains blocked.

The next and only permitted diagnostic uses Action Prompt v13 and materialization report v4. v13
restores each registered operation's public input schema and invariant checks, derives a compact
operator input-count contract, and states explicitly that a series role contains separate Evidence
items rather than one batched lookup. It still leaves Evidence selection and operation-graph
construction to the model. Report v4 freezes every independently rejected trajectory together with
its validity report, so a failed diagnostic remains causally auditable instead of collapsing all
post-generation failures into one counter. The original smoke threshold is unchanged.

## Fail-Closed Transition

The Development target measurement is complete. Under the 2026-08-11 amendment, the next permitted
transition is a pre-outcome Agent Runtime Pilot capacity audit and contract freeze. A passing Pilot
may proceed only to Beneficiary frontier screening and a new Agent Development population. The
historical 60-task recommendation cannot be frozen until variance is re-estimated under that new
generation kernel. GP-C remains inaccessible.

## Completed Development Data Stage

DeepSeek v4 Pro with Action Prompt v13 passed the unchanged 100-state smoke gate and then completed
the full conditioned run. The complete data report is immutable at:

```text
artifacts/vtdo_experiment/
  finance_v22_development_data_analysis_deepseek_v13_v1_20260808/report.json
```

| Measure | Result |
| --- | ---: |
| Independent tasks | 30 |
| Accepted quotient states | 100 |
| Unconditioned Explorer observations | 300 |
| State-conditioned realizations | 500 / 500 |
| Conditioned attempts | 502 |
| On-target attempts | 500 |
| On-target rate | 99.6016% |
| API / JSON-contract successes | 1,506 / 1,506 |
| Duplicate-trajectory retries | 2 |
| Mean empirical natural-state entropy | 0.0059505 |
| Update-derived MPE range | 0.0078282 - 0.0209338 |

The entropy is computed from ten unconditioned observations per task. Most tasks placed all ten
observations in one catalog state; this is an observed Explorer concentration, not a claim that the
other accepted states are invalid or unreachable. The five state-conditioned realizations remain
independent draws inside each frozen quotient state. Repository-side price coefficients estimate
the conditioned run at USD 1.0902; this is not a provider invoice.

## Exact One-Step Development Target

The pre-outcome target implementation is:

```text
src/trusted_synthesis/experiments/vtdo_experiment/phase1_development_target.py
```

It does not continue the v20 finite-radius or Hadamard protocol. It freezes one shared global
one-step update over the complete conditional distribution:

```text
g(pi) = sum_x mu(x) sum_z pi(z|x) mean_r g(x,z,r)
theta' = theta - AdamW_cold_start(g(pi))
```

`mu(x)` is uniform and immutable across the 30 Development tasks. Each quotient state receives five
equally weighted trajectory realizations, preserving `P(tau|x,z)` independently of assistant-token
length. The Development Objective contains eight immutable micro-splits of eight equally weighted
records. Every Objective gradient is evaluated at the same `theta'`, rather than constructing a
different post-update model for each task.

For each task, state, Objective micro-split, and realization, the measured surrogate is the exact
chain derivative for the frozen one-step optimizer:

```text
Y(x,z,m,r) = mu(x) < d AdamW(g) / d g ^T g_objective(m),
                         g(x,z,r) - sum_j pi(j|x) mean_r g(x,j,r) >
```

The AdamW vector-Jacobian product includes the derivative of global-norm clipping when clipping is
active. It uses neither a finite radius nor GP-C as its target. One primary state coordinate per
task is selected by an outcome-blind salted hash before gradients are observed; all 100 states are
retained for variance estimation. The resulting 4,000 crossed observations estimate task-family,
task, state, Objective, realization, interaction, and numeric components. Only then may an empirical
power simulation freeze the size of a future fresh Validation population.

The target remains a one-step engineering surrogate, not the full Student-training functional. A
successful Development result cannot establish Validation identifiability, evaluate GP-C, open
Authorization, authorize Contribution, update VTDO, or support downstream Student claims.

## Completed Exact-Target Result

The measurement contract was frozen at source commit `3aa1b0c` before outcomes. Two concurrent
three-GPU workers completed 500/500 state gradients, followed by 8/8 Objective micro-splits. The
aggregate produced 4,000 crossed observations and passed numeric and simplex replay:

| Measure | Result |
| --- | ---: |
| FP32/FP64 maximum target delta | `1.0551e-11` |
| Maximum simplex-centering error | `1.1699e-11` |
| Objective share of nested measurement variance | `99.9443%` |
| Realization share | `0.0005%` |
| Primary coordinates statistically nonzero | 26 / 30 |
| Primary coordinates practically equivalent | 30 / 30 |
| All states practically equivalent | 100 / 100 |
| Coordinates meaningful beyond MPE | 0 / 100 |

The original exclusive resolution labels hid that 26 primary coordinates were both statistically
nonzero and practically equivalent. The separately hashed v22.1 analysis reports both axes. Median
primary effect magnitude is `0.001181 x MPE`; the maximum is `0.024457 x MPE`.

The original `power=1.0` result for a homogeneous one-MPE population mean is retained as a
diagnostic but cannot freeze task count for future proxy-target agreement. The recommended fresh
Validation support is 60 tasks (10 per family), five realizations per state, and 128 Objective
records (16 x 8). That recommendation is not yet a Validation contract and does not open any held
out data. It is now also conditional on a passing Agent Pilot and a new Development power study.
Full results are in `docs/finance_v22_development_exact_target_report.md`.

## Immutable References

- `artifacts/vtdo_experiment/finance_v22_development_population30_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v22_development_objective64_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v21_target_observability_population420_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v21_target_observability_population6_v1_20260807/`
- `artifacts/vtdo_experiment/finance_v22_development_exact_target_v1_20260808/`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_development_power.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_development_target.py`
- `src/trusted_synthesis/experiments/vtdo_experiment/phase1_development_design_analysis.py`
