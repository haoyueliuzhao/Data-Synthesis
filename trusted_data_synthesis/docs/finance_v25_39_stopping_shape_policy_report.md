# Finance v25.39 Stopping Shape Policy Development

## Status

v25.39 executed the preregistered 48-task, 384-rollout Flash-only Development
experiment on a fresh immutable Finance Evidence snapshot. The runtime instrument
completed every requested rollout, but the Shape policy remains unfrozen.

This run is a diagnostic Development result. It does not authorize Pro,
Beneficiary screening, Exact Target, GP-C, Contribution estimation, or a
three-population experiment.

## Immutable inputs

- Finance archive build: `kg_20260711_062123_bc4b4394`
- Full adapter scan: 564,297 Evidence items
- Eligible after historical exclusion and Finance semantic policy: 513,997
- Frozen snapshot: 30,000 Evidence items from 3 sources, 76 subjects, and 68 predicates
- Disjoint three-period Gold capacity: 7,683
- Contextual-pair capacity: 2,853
- Normalization-pair capacity: 14,963
- Population: 48 tasks, with 2 tasks for each Shape x structural-stratum cell
- Development: 8 independent Flash realizations per task, 384 total

All historical Evidence identity exclusions, within-population disjointness,
program replay, Host replay, public/oracle isolation, and static task contracts
passed before API execution.

## Execution integrity

| Check | Result |
| --- | ---: |
| Requested / recorded rollouts | 384 / 384 |
| API transport resolution | 100% |
| Bounded JSON resolution | 100% |
| Terminal resolution | 100% |
| Observation replay | 100% |
| Authority integrity | 100% |
| Runtime pathology | 0% |
| L0-L2 failures | 0 |
| Pro API calls | 0 |

The run used 3,823 model calls and 20,182,641 model tokens. The configured cost
estimate was USD 1.960657.

## Estimand decision

The three responses remained separate:

- `Y_stop`: capability/Shape information.
- `Y_valid`: positive training support.
- `Y_sem`: answer-semantic diagnosis only.

`estimand_semantics_frozen=true` and cross-estimand rescue remained forbidden.
The aggregate rates were `Y_stop=0.6380`, `Y_valid=0.4245`, and
`Y_sem=0.4453`.

## Shape results

| Shape | Role | Y_stop | Y_valid | Decision |
| --- | --- | ---: | ---: | --- |
| `authority_coverage_gap` | boundary | 0.8281 | 0.5156 | near-pass; 5/6 required nonzero tasks |
| `contextual_resolution_choice` | boundary | 0.0000 | 0.0000 | floor |
| `partial_required_evidence` | boundary | 0.0000 | 0.0000 | invalid instrument result |
| `single_dimension_conflict` | boundary | 1.0000 | 0.7344 | ceiling |
| `verified_extra_call_cost` | control | 1.0000 | 0.6562 | passed |
| `verified_extra_call_error_risk` | control | 1.0000 | 0.6406 | passed |

Boundary candidates admitted: 0/4. Boundary near-pass: 1/4. Runtime controls
passed: 2/2. Total contract-passing Shapes: 2/6.

## Post-run forensic findings

### Partial Evidence instrument defect

All 64 Partial trajectories are invalid for capability inference. Flash reached
the required Archive probe, but the Host added a top-level
`dependency_branch_observation` field that was absent from the frozen tool output
contract. Strict observation validation rejected the successful Host result with:

```text
Agent tool result contains unknown fields: ['dependency_branch_observation']
```

This is an instrument defect, not evidence that the model has zero stopping
capability. The next run must register this optional Host-owned output and include
an end-to-end manifest-validation regression.

### Contextual floor

All 64 trajectories observed the conflict trigger, but none emitted the required
resolution event. Every run exhausted the four-failed-call budget. The public
signal only stated that a relation was unwarranted, while the Oracle required an
exact structured-fact query. Agents instead tried normalization and document
inspection, both of which were plausible under the published state. The task did
not expose enough public Evidence-state information to identify the correct
action.

The next design must expose the compared public record identities and requested
role, while continuing to hide the Oracle conflict-field label and Shape identity.

### Conflict ceiling

All eight Conflict tasks used `temporal_alignment`, but the Runtime required
`normalize_metric_unit_period` for every conflict dimension. The correct action
was therefore constant across tasks and directly aligned with the generic public
signal. This created a ceiling rather than an Evidence-dependent decision.

The next design must preregister multiple one-dimensional mismatch families and
map each public Evidence state to a genuinely different resolution action.

### Authority near-pass

Authority passed every gate except the minimum of six nonzero-information tasks;
five tasks were nonzero. It remains unchanged in the next run. No threshold is
relaxed and no task is deleted post hoc.

## Next permitted experiment

v25.40 may only:

1. repair the Partial observation contract;
2. make Contextual action selection identifiable from public Evidence state;
3. balance Conflict mismatch dimensions and vary the required action;
4. retain Authority and both controls unchanged;
5. rerun a fresh Flash-only Development population.

Until all four boundary candidates and both controls pass their preregistered
gates, `shape_support_policy_frozen=false`, three-population preparation remains
blocked, and production Contribution remains exactly zero.
