# Finance v25.43-v25.44 Stopping Role-position Validation

## Executive conclusion

v25.43 established a valid host-instrumented Stopping measurement after the
v25.41-v25.42 instrumentation path was frozen as invalid. It admitted two of
four capability-boundary Shapes and both Runtime controls. A preregistered
forensic analysis then identified required-Evidence role position as a nuisance
factor for the two remaining Shapes.

v25.44 changed only that nuisance factor on a fresh, identity-disjoint Finance
population:

```text
contextual_resolution_choice -> required_2
single_dimension_conflict    -> required_3
```

All four boundary candidates and both Runtime controls passed their frozen
task-level contracts. This authorizes preparation of three new independent
populations. It does **not** authorize Pro calls, Beneficiary screening, Exact
Target, GP-C, Contribution estimation, VTDO updates, or Student training.

## Why v25.41-v25.42 are not scientific evidence

The earlier causal-timing revision exposed host-only intervention metadata in
the strict business result returned to the model. Strict tool schemas therefore
failed before the intended capability response could be measured. The old
classifier also assigned those failures to the model-decision layer.

The repair introduced `agent_tool_observation.v2`:

```text
AgentToolResult.result -> strict business payload only
AgentToolResult.host_events -> typed host side channel
Observation.host_events -> replayable host side channel
```

Unknown strict-schema fields are now classified as a Runtime measurement
pathology. Historical v25.41-v25.42 results remain immutable and cannot be
reclassified or transferred into the current support decision.

## v25.43 instrument validation

v25.43 used 48 fresh tasks, six Shapes, four structural strata, two tasks per
Shape-stratum cell, and eight Flash realizations per task.

| Metric | Result |
| --- | ---: |
| Requested / recorded rollouts | 384 / 384 |
| Execution, terminal, replay, authority integrity | 100% |
| Runtime pathology / L0-L2 failures | 0 / 0 |
| Stopping behavior success | 78.65% |
| Full valid-trajectory success | 47.92% |
| Answer-semantic success | 50.26% |
| Valid training trajectories | 184 |
| Boundary candidates admitted | 2 / 4 |
| Runtime controls passed | 2 / 2 |
| API calls / model tokens | 3,899 / 20,550,190 |
| Estimated API cost | USD 1.9756 |

The two failed Shapes had the following task-level failures:

| Shape | Stop rate | Task range | Effective tasks | Result |
| --- | ---: | ---: | ---: | --- |
| Contextual | 59.38% | 1.000 | 3.765 | failed heterogeneity, nonzero-task and effective-task gates |
| Conflict | 68.75% | 0.875 | 5.708 | failed heterogeneity gate |

The frozen predecessor audit found a role-position split:

```text
Contextual required_1: 0.875, 1.000, 1.000, 1.000
Contextual required_2: 0.000, 0.250, 0.250, 0.375

Conflict required_1:   0.625, 0.750, 1.000, 1.000
Conflict required_3:   0.125, 0.625, 0.625, 0.750
```

Role position was therefore preregistered as a nuisance control. No historical
result was selected, deleted, relabeled, or copied into v25.44.

## v25.44 protocol

The v25.44 protocol froze:

- 48 new tasks and 384 Flash rollouts;
- the same four structural strata and eight realizations per task;
- unchanged Authority and Partial boundary regressions;
- unchanged post-completion Runtime controls;
- `required_2` for every Contextual task;
- `required_3` for every Conflict task;
- exact task, Evidence, Evidence-version, semantic-signature, and materializer
  disjointness from prior populations;
- no pooled rescue, post-hoc task selection, or post-hoc deletion;
- separate mechanism-observable, valid-training, and semantic estimands.

The static audit passed all gates. Every Shape-stratum cell contained two tasks,
the target-role control rate was 100%, and all 48 task identities were fresh.

## v25.44 result

### Global execution

| Metric | Result |
| --- | ---: |
| Requested / recorded rollouts | 384 / 384 |
| Execution integrity | 100% |
| Terminal resolution | 100% |
| API transport resolution | 100% |
| Bounded JSON resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Runtime pathology / L0-L2 failures | 0 / 0 |
| Stopping behavior success | 70.57% |
| Full valid-trajectory success | 46.88% |
| Answer-semantic success | 48.70% |
| Valid training trajectories | 180 |
| API calls / model tokens | 3,724 / 19,477,666 |
| Estimated API cost | USD 1.9226 |

### Preregistered Shape decisions

| Shape | Stop | Full valid | Range | Boundary / nonzero | Effective N | Max share | Bootstrap LCB | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Authority | 67.19% | 34.38% | 0.750 | 6 / 6 | 5.724 | 0.205 | 0.453 | admitted |
| Contextual | 26.56% | 12.50% | 0.500 | 7 / 7 | 6.453 | 0.184 | 0.641 | admitted |
| Partial | 76.56% | 40.62% | 0.500 | 8 / 8 | 7.317 | 0.190 | 0.594 | admitted |
| Conflict | 53.12% | 45.31% | 0.750 | 8 / 8 | 7.399 | 0.163 | 0.859 | admitted |
| Extra-call cost control | 100% | 76.56% | 0.000 | control | - | - | - | passed |
| Extra-call risk control | 100% | 71.88% | 0.000 | control | - | - | - | passed |

The role-controlled task probability vectors were:

```text
Contextual required_2: 0.125, 0.125, 0.500, 0.250,
                       0.375, 0.000, 0.375, 0.375
Conflict required_3:   0.875, 0.500, 0.500, 0.125,
                       0.750, 0.250, 0.500, 0.750
```

The Contextual range fell from 1.000 to 0.500. Conflict fell from 0.875 to the
frozen upper bound of 0.750. Both now have broad task-level information support
without single-task dominance.

## Independent raw-artifact audit

The post-run audit did not rely on the aggregate report:

```text
rollout records                         384
unique independent tasks                48
replicates per task                       8
tool observations                     3,268
agent_tool_observation.v2             3,268
strict business-result host keys           0
unknown-fields tool-schema errors           0
manifest hash mismatches                    0
trigger observed                         384
ordered resolution                        271
post-completion violations                  0
requested model              deepseek-v4-flash only
selected model               deepseek-v4-flash only
```

The 197 failed records are measured capability outcomes, not Runtime pathology.
The primary Stopping response is the frozen conjunction of Runtime eligibility,
ordered host-event resolution, and absence of a post-completion violation. It is
not the legacy terminal `stopping` capability flag.

## Scientific interpretation

v25.44 supports the following claims:

1. The host-event side channel is a valid, replayable measurement instrument.
2. Required-Evidence role position was a real nuisance factor in v25.43.
3. All four preregistered Stopping boundary Shapes can provide task-distributed
   mechanism information under the role-controlled construction.
4. The two post-completion controls remain stable.
5. Mechanism-observable support and positive training support remain different
   statistical objects.

It does not support:

- transferring historical failed trajectories into training support;
- claiming all mechanism-observable trajectories are valid training data;
- claiming stable support across independent populations;
- calling Pro or screening a Beneficiary;
- evaluating Exact Target or GP-C;
- assigning nonzero production Contribution;
- updating the VTDO distribution or training a Student.

## Next authorized experiment

The only newly authorized stage is preparation of three fresh, mutually
independent Shape-policy populations:

```text
3 populations
x 60 independent tasks per population
x 8 realizations per task
= 1,440 Flash rollouts
```

Each population must independently pass all four boundary-candidate gates and
both Runtime controls. Pooled rescue remains forbidden. The new populations must
freeze task, Evidence, Evidence-version, semantic-signature, and materializer
disjointness before any API call. Exact Target and Contribution remain blocked
until that stability experiment succeeds.

## Immutable artifact locations

```text
v25.43 report:
artifacts/vtdo_experiment/finance_v25_43_stopping_shape_policy_development_v7_20260816/

v25.44 protocol:
artifacts/vtdo_experiment/finance_v25_44_stopping_shape_policy_protocol_v8_20260816/

v25.44 population:
artifacts/vtdo_experiment/finance_v25_44_stopping_shape_policy_population_v8_20260816/

v25.44 contract:
artifacts/vtdo_experiment/finance_v25_44_stopping_shape_policy_contract_v8_20260816/

v25.44 run:
artifacts/vtdo_experiment/finance_v25_44_stopping_shape_policy_development_v8_20260816/
```
