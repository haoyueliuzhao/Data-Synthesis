# Finance v25.44 Hardened Replication and Recursive Instrument Audit

## Executive conclusion

The Snapshot v3 capacity repair passed, and the hardened Flash run completed all
384 preregistered rollouts. The run is nevertheless **not valid Shape-policy
authorization evidence**.

A recursive raw-artifact audit found Host-only event metadata inside nested
business-result objects:

    contaminated tool observations             219 / 1,449
    contaminated independent tasks              32 / 48
    embedded host_event occurrences                 219
    embedded host_event_sequence occurrences         63

The previous audit checked only top-level result keys. The model-visible
business payload still contained values such as completion_state.host_event,
while agent_tool_observation.v2 requires those events to be carried exclusively
by AgentToolResult.host_events.

Consequently, v25.43 and both v25.44 runs remain immutable diagnostics but
cannot authorize a Stopping Shape policy. Preparation of three populations is
withdrawn. Pro, Beneficiary, Exact Target, GP-C, VTDO updates, and Student
training remain blocked; production Contribution remains zero.

## Snapshot v3 capacity result

The prospective Snapshot repair itself remains valid:

| Metric | Result |
| --- | ---: |
| Archive records scanned | 564,297 |
| Fresh semantically valid records | 512,845 |
| Base selected records | 151,022 |
| Exact companion records | 92 |
| Final selected records | 151,114 |
| Period exact-pair capacity | 75,509 |
| Definition exact-pair capacity | 90 |
| Contextual exact-pair capacity | 2,436 |
| Snapshot status | passed |

This establishes materialization capacity only. It does not validate the Agent
measurement instrument.

## Hardened Flash run

The committed-source run used 48 fresh tasks, eight realizations per task, and
DeepSeek V4 Flash only.

| Metric | Result |
| --- | ---: |
| Requested / recorded rollouts | 384 / 384 |
| Execution, terminal, replay, authority integrity | 100% |
| Runtime pathology / L0-L2 failures | 0 / 0 |
| Stopping behavior success | 268 / 384 = 69.79% |
| Full valid-trajectory success | 183 / 384 = 47.66% |
| Answer-semantic success | 194 / 384 = 50.52% |
| API calls / model tokens | 3,700 / 19,293,960 |
| Estimated API cost | USD 1.9192 |
| Boundary candidates admitted | 3 / 4 |
| Runtime controls passed | 2 / 2 |

The Shape-level diagnostic result was:

| Shape | Stop | Full valid | Task range | Effective tasks | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Authority coverage gap | 51.56% | 37.50% | 0.875 | 6.490 | failed heterogeneity |
| Contextual resolution | 29.69% | 20.31% | 0.625 | 5.681 | diagnostic pass |
| Partial required evidence | 73.44% | 34.38% | 0.750 | 5.724 | diagnostic pass |
| Single-dimension conflict | 64.06% | 48.44% | 0.750 | 6.673 | diagnostic pass |
| Extra-call cost control | 100% | 78.12% | 0 | 0 | control pass |
| Extra-call risk control | 100% | 67.19% | 0 | 0 | control pass |

These decisions are reported only to preserve the frozen run. Because the
instrument contract failed, none can be transferred into support authorization.

Authority heterogeneity was structurally concentrated:

    verification_selection_frontier   1.000, 0.875
    retrieval_join_frontier            0.750, 0.375
    definition_reconciliation_frontier 0.500, 0.250
    calculation_chain_frontier         0.250, 0.125

This is useful for prospective matching, but it is not a valid post-hoc rescue.

## Independent integrity audit

The raw files were inspected independently of the aggregate report:

    records / terminal / behavior / Shape observations 384 each
    unique tasks                                         48
    replicates per task                                   8
    requested model                    deepseek-v4-flash only
    selected model                     deepseek-v4-flash only
    tool observations                                  1,449
    agent_tool_observation.v2                          1,449
    Manifest content-hash mismatches                       0
    unknown-field contract failures                        0
    post-completion violations                             0
    trigger observations                                 383
    ordered resolutions                                  268

There was one call-level HTTP failure and four call-level JSON-contract
failures, all resolved within the frozen rollout protocol. They did not create
L0-L2 terminal failures.

The aggregate report rates equal the atomic Shape observations. A new model
invariant now enforces that equality prospectively.

## Engineering repair

The prospective Runtime now enforces:

1. AgentToolResult.result and AgentToolObservation.result recursively reject
   host_event, host_events, host_event_sequence, and submechanism_activation.
2. Trigger and resolution events are captured at the Runtime call boundary and
   emitted only through the typed outer host_events side channel.
3. Historical predecessor audits scan nested mappings and lists, not only
   top-level result keys.
4. Aggregate Stopping, full-valid, and semantic rates must equal the weighted
   atomic Shape responses.

The old artifacts are not rewritten or reclassified.

Repository-wide repair validation:

    Ruff                              passed
    Mypy                              318 source files passed
    Pytest                            733 passed
    git diff --check                 passed

## Next permitted experiment

The next stage is strictly:

    fresh instrument-reset protocol
    -> fresh identity-disjoint 48-task population
    -> static recursive Host-isolation audit
    -> 384 Flash rollouts
    -> independent raw-artifact audit

The protocol must not treat v25.43 or v25.44 Shape outcomes as prior support.
It may reuse the prospective task grammar and Snapshot v3 capacity contract,
but must use a new protocol, population, contract, implementation manifest, and
rollout identity set.

Only after the repaired instrument passes recursively and all four boundary
candidates plus both controls pass may three-population stability preparation
be reconsidered.

## Immutable artifacts

Snapshot v3:

    /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/
    vtdo_experiment/finance_v25_44_hardened_stopping_evidence_snapshot_v3_20260816/

Hardened Population:

    /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/
    vtdo_experiment/finance_v25_44_stopping_shape_policy_population_v8_hardened_final_20260816/

Hardened Flash run:

    /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/
    vtdo_experiment/finance_v25_44_stopping_shape_policy_development_v8_hardened_final_20260816/
