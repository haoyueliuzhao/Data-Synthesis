# Finance v25.44 Evidence Snapshot v3 Capacity Hardening

## Purpose

The first v25.44 development run admitted all four Stopping boundary Shapes and
both Runtime controls. A subsequent fresh-population rehearsal exposed a
selection-layer capacity defect before any API call: the Snapshot reported high
aggregate normalization capacity, but the `required_3` conflict role had no
fresh exact `definition` companion.

This was not a shortage in the frozen Finance Archive. It was a Snapshot
selection error.

## Root-cause audit

The failed rehearsal used the full historical identity exclusion set and a
151,022-item Snapshot. A field-specific bucket audit found:

```text
selected Snapshot
period exact-pair buckets            327
definition exact-pair buckets          0
payload-context exact-pair buckets     0
subject exact-pair buckets            491
```

The underlying 564,297-record Archive was then scanned independently. After
historical exclusion and semantic validation, 512,845 records remained and
contained 1,272 fresh exact `definition` pair keys. The v2 selector had retained
complete contiguous time-series chunks but dropped isolated alternate
SourceDefinition records.

The old aggregate metric:

```text
period + definition + payload_context pair capacity
```

was therefore unsound as a readiness gate: abundant period alternatives could
hide zero definition capacity.

## Snapshot v3 contract

Snapshot v3 makes two prospective changes:

1. Select complete contiguous series exactly as before, then add exact
   one-difference companions for `definition` and `payload_context` when the
   base target is present.
2. Replace aggregate normalization readiness with field-specific, fail-closed
   gates for period and definition capacity.

The closure is deterministic and bounded by the frozen maximum Snapshot size.
It adds only records whose non-target semantic identity fields match a selected
base record and whose target field differs. Same-definition duplicate records
are not admitted as companions.

The report now records:

```text
base_selected_evidence_count
companion_evidence_count
period_pair_capacity
definition_pair_capacity
payload_context_pair_capacity
```

The Schema identities are intentionally advanced to:

```text
finance_stopping_evidence_snapshot.v3
finance_stopping_evidence_snapshot_selection.v2
```

No compatibility path silently treats v2 as v3.

## Real Archive result

The v3 rebuild used the same frozen Archive and the same 42 historical
Population references as the hardened rehearsal.

| Metric | Result |
| --- | ---: |
| Archive records scanned | 564,297 |
| Fresh semantically valid records | 512,845 |
| Base selected records | 151,022 |
| Exact companion records added | 92 |
| Final selected records | 151,114 |
| Period pair capacity | 75,509 |
| Definition pair capacity | 90 |
| Payload-context pair capacity | 0 |
| Contextual pair capacity | 2,436 |
| Rejection reasons | 0 |
| Status | passed |

The zero payload-context capacity remains explicit. It is not required by the
current preregistered v25.44 conflict allocation and cannot be claimed as
supported.

## Scientific boundary

This hardening result authorizes only a new static Population build. It does not
itself reproduce the v25.44 model result and does not authorize Pro,
Beneficiary, Exact Target, GP-C, Contribution, a VTDO update, or Student
training. Production Contribution remains zero.

## Immutable artifact

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/
vtdo_experiment/finance_v25_44_hardened_stopping_evidence_snapshot_v3_20260816/
```

Snapshot ID:

```text
finance_stopping_evidence_snapshot:b6a064ef5106c045bb2c06bd3affca775cd8f3b6c95b4b4e7e92d222c426dad0
```

## Hardened replication outcome

A fresh 48-task, 384-rollout Flash run was completed after the Snapshot v3
repair. Snapshot capacity and file integrity passed, but the run did not
reproduce full Shape admission: three of four boundary candidates passed,
Authority failed the frozen between-task heterogeneity gate, and both controls
passed.

A deeper independent audit then found 219 tool observations with nested
Host-only metadata. This invalidates the run as authorization evidence even
though all aggregate integrity gates originally reported success. Snapshot v3
remains a valid capacity artifact; it no longer authorizes an API run under the
old instrument contract.

The current next stage is a fresh instrument-reset protocol. See
docs/finance_v25_44_hardened_replication_instrument_audit.md.
