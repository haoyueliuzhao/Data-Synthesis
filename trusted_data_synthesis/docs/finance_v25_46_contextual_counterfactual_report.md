# Finance v25.46 Contextual Counterfactual Development

Experiment date: 2026-08-17

## Decision

v25.46 completed the preregistered contextual-counterfactual test requested by the v25.45
instrument audit. The recursive measurement instrument remained clean and all four boundary
Shape contracts plus both Runtime controls passed. The additional prospective Contextual Flip
gate did not pass.

This is a localized negative result:

```text
recursive measurement instrument = passed
Shape analysis                   = authorized
boundary Shape contracts         = 4 / 4 passed
Runtime controls                 = 2 / 2 passed
Contextual Flip Consistency      = failed
all v25.46 gates                 = false
production Contribution          = 0
```

The result does not authorize Pro, Beneficiary screening, Exact Target, GP-C, a VTDO update, or
Student training. The only permitted next stage is another scoped Contextual Shape redesign.

## Frozen Design

The formal population contains 48 fresh tasks and 384 Flash rollouts:

| Component | Count |
| --- | ---: |
| Contextual counterfactual tasks | 8 |
| Matched counterfactual pairs | 4 |
| Frozen regression tasks | 40 |
| Tasks per Shape | 8 |
| Replicates per task | 8 |
| Total rollouts | 384 |

For each contextual pair, the two branches have the same core task, public corpus, gold Evidence,
program skeleton, answer schema, action set, tool budget, prompt byte length, and final answer
burden. Only the active observed Evidence context changes. The correct first resolution action
flips from `query_structured_fact` for the period branch to
`normalize_metric_unit_period` for the definition branch.

The pre-API static audit passed every frozen invariant:

```text
task / pair capacity             = 48 / 4
same core task rate              = 1.000
same public corpus rate          = 1.000
same program and answer rate     = 1.000
same action set and budget rate  = 1.000
same prompt-byte rate            = 1.000
single Context change rate       = 1.000
correct action flip rate         = 1.000
deterministic branch replay      = 1.000
lexical action-answer leakage    = 0
historical identity overlap      = 0
```

The other five Shape mechanisms, all Shape thresholds, Public Result schemas, recursive
noninterference checks, Host side channel, dual estimands, Flash model identity, and failure
attribution were unchanged from v25.45.

## Runtime Result

All 384 rollout records were retained in the capability denominator:

| Metric | Result |
| --- | ---: |
| Auditable records | 384 / 384 |
| Successful Agent outcomes | 225 |
| Fail-closed behavior outcomes | 159 |
| Full-valid trajectories | 209 |
| Observation replay success | 384 / 384 |
| Runtime infrastructure failures | 0 |
| Recursive Host field violations | 0 |
| Recursive Host marker violations | 0 |

`Successful Agent outcomes` records a semantic terminal outcome. `Full-valid trajectories` is the
stricter training-eligibility result. Neither count removes the 159 fail-closed behavior outcomes
from the Shape denominator.

The frozen DeepSeek V4-Flash route completed 4,009 model interactions, used 21,810,496 model
tokens, and recorded an estimated cost of USD 2.2382 under the contract's frozen pricing table.
The requested model was `deepseek-v4-flash`, no fallback model was allowed, and no Runtime
infrastructure failure occurred.

## Shape Result

The recursive raw audit passed before Shape aggregation. All six Shape contracts then passed:

| Shape | Role | Stopping success | Task range | Admitted |
| --- | --- | ---: | ---: | --- |
| `authority_coverage_gap` | boundary | 0.6562 | 0.7500 | yes |
| `contextual_resolution_choice` | boundary | 0.4531 | 0.5000 | yes |
| `partial_required_evidence` | boundary | 0.7812 | 0.1250 | yes |
| `single_dimension_conflict` | boundary | 0.5938 | 0.7500 | yes |
| `verified_extra_call_cost` | control | 1.0000 | 0.0000 | yes |
| `verified_extra_call_error_risk` | control | 1.0000 | 0.0000 | yes |

The contextual matched construction therefore removed the v25.45
`between_task_heterogeneity` failure. This is valid Shape-support evidence, but it is not enough to
show that the Agent uses Context to select different actions.

## Contextual Flip Result

The prospective metric evaluates the first registered resolution action after all required
Evidence has been selected. A later repair cannot turn an incorrect first action into a successful
flip.

```text
Contextual Flip Consistency         = 2 / 32 = 0.0625
preregistered minimum               = 0.1250
informative matched pairs           = 2 / 4
required informative pairs          = 4 / 4
maximum branch action-rate gap      = 0.6250
maximum permitted gap               = 0.7500
```

Per-pair results were:

| Structural stratum | Period correct | Definition correct | Dual correct |
| --- | ---: | ---: | ---: |
| Retrieval join | 5 / 8 | 1 / 8 | 0 / 8 |
| Calculation chain | 5 / 8 | 2 / 8 | 1 / 8 |
| Definition reconciliation | 1 / 8 | 2 / 8 | 1 / 8 |
| Verification selection | 5 / 8 | 0 / 8 | 0 / 8 |

The first-action diagnostic shows a strong archive-query preference. In the definition branches,
the first post-prerequisite action was usually `query_structured_fact`, often rejected by the
Host, while the required normalization action occurred only five times across 32 rollouts. The
current public state exposes opaque definition identifiers but gives only the generic statement
that one registered identity component differs. This supports a narrow interpretation:

> The paired task structure is now controlled, but the public Context is not sufficiently
> interpretable for stable counterfactual action selection.

It would be incorrect to lower the flip threshold, delete fail-closed outcomes, add replicas to the
same tasks, or claim that the Contextual Shape is capability-sensitive from its aggregate stopping
rate alone.

## Reproducibility

Formal artifacts are under the immutable experiment root:

```text
finance_v25_46_contextual_counterfactual_protocol_20260817
finance_v25_46_contextual_counterfactual_population_20260817
finance_v25_46_contextual_counterfactual_execution_contract_20260817
finance_v25_46_contextual_counterfactual_development_20260817
```

The direct Runner consumed the current `all_shapes_contract_passing` schema. A no-API finalizer
was run after completion and reproduced every existing report and manifest exactly. Repository
validation at freeze time was:

```text
Ruff       passed
Mypy       325 source files passed
Pytest     754 passed
```

## Next Permitted Experiment

The next experiment may change only the contextual task grammar and its matching/materialization
identity. A defensible revision should expose one shared, action-neutral interpretation policy that
lets the Agent distinguish a different observation event from the same event under an alternate
registered convention. Both branches must continue to share the same policy text, action set,
corpus, program, budget, prompt length, and answer burden.

The next run must use fresh tasks and rollout identities and repeat the full recursive instrument,
Shape, and flip gates. Until that run passes, the frozen state remains:

```text
Pro / Beneficiary / Exact Target / GP-C = blocked
VTDO update / Student training          = blocked
production Contribution                 = 0
```
