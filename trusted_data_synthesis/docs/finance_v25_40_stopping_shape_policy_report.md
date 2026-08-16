# Finance v25.40 Stopping Shape Policy Development

## Status

v25.40 completed a preregistered 48-task, 384-rollout Flash-only Development
experiment on a fresh immutable Finance Evidence snapshot. It repaired the v25.39
manifest defect and made the Contextual and Conflict public states explicit, but the
complete Shape policy remains unfrozen.

This diagnostic result does not authorize Pro, Beneficiary screening, Exact Target,
GP-C, Contribution estimation, VTDO updates, or Student training.

## Immutable inputs

- Finance archive build: `kg_20260711_062123_bc4b4394`
- Full adapter scan: 564,297 Evidence items
- Eligible after historical exclusion and Finance semantic policy: 513,997
- Frozen snapshot: 100,000 Evidence items from 3 sources, 76 subjects, and 69 predicates
- Snapshot ID: `finance_stopping_evidence_snapshot:363da4af6bd1976f48d092ff4af6bad6d38fd9b5e740aa1ad5c377d388049069`
- Snapshot artifact SHA-256: `b5acdcb24fd64b9fafac19bf4ab09bac62a8ecaedb9954d97fc236c8582a0413`
- Population: 48 tasks; eight independent Flash realizations per task; 384 total

The snapshot was expanded from 30,000 to 100,000 before API access because the
smaller snapshot lacked exact one-difference Definition support. Actual materialized
capacity froze six temporal-query and two definition-normalization Conflict tasks.
Payload and source cells had zero support and were recorded as unsupported.

## Execution integrity

| Check | Result |
| --- | ---: |
| Requested / recorded rollouts | 384 / 384 |
| API transport / bounded JSON / terminal resolution | 100% |
| Observation replay / authority integrity | 100% |
| Runtime pathology | 0% |
| L0-L2 failures | 0 |
| Pro API calls | 0 |

The run used 4,016 API calls and 21,142,539 model tokens. The configured estimate
was USD 1.898276.

## Estimands and Shape results

`Y_stop`, `Y_valid`, and `Y_sem` remained separate; cross-estimand rescue was
forbidden. Aggregate rates were 0.5495, 0.3177, and 0.3281 respectively.

| Shape | Y_stop | Y_valid | Decision |
| --- | ---: | ---: | --- |
| `authority_coverage_gap` | 0.5469 | 0.2969 | admitted |
| `contextual_resolution_choice` | 0.0000 | 0.0000 | floor |
| `partial_required_evidence` | 0.7031 | 0.2656 | admitted |
| `single_dimension_conflict` | 0.2031 | 0.0469 | insufficient support |
| `verified_extra_call_cost` | 0.9375 | 0.6250 | control passed |
| `verified_extra_call_error_risk` | 0.9062 | 0.6719 | control passed |

Two of four boundary candidates were admitted, no candidate was a near-pass, and
both controls passed. The full Shape policy remains unfrozen.

## Causal-timing finding

The Partial Host-owned `dependency_branch_observation` now validates against the
typed tool output contract and Partial is admitted. Contextual and Conflict also
expose record pairs that differ in exactly one semantic field without exposing the
Oracle mismatch label.

The two residual failures are not clean capability results. Their state is emitted
after the base program already retrieved all Gold records, calculated the answer,
and attempted verification. Query-based cells then require another query for an
already selected record. All six temporal-query Conflict tasks had `Y_stop=0`, while
the two definition-normalization cells reached 0.75 and 0.875. This is a causal
placement confound, not a valid query-versus-normalization capability comparison.

## Next permitted experiment

Only the intervention placement may change:

1. Entity and temporal query decisions occur before required Evidence selection.
2. Definition normalization occurs after Evidence selection but before calculation.
3. Public state, action set, exact one-field difference, isolation, and thresholds
   remain unchanged.
4. A focused fresh-task Flash Development precedes any full confirmation.

No retry increase, threshold relaxation, post-hoc deletion, Pro call, Beneficiary
access, Exact Target, GP-C, Contribution, VTDO update, or Student training is
authorized. Production Contribution remains zero.
