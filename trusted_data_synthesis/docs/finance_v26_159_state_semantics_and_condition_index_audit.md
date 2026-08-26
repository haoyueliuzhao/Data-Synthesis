# Finance v26.159 State Semantics And Condition Index Audit

Audit date: 2026-08-26

## Decision

Finance v26.159 consumes the new external code-audit decision
`valid_only_state_semantics_and_condition_index_audit_only`. It performs no model generation and
does not change a historical terminal, validity label, Assignment, State ID, or Route ID. The
immutable v26.157 facts remain:

```text
Mapper-v1 Assignments             100
Mapper-v1 structural State IDs     41
Mapper-v1 Route Projection IDs     44
```

Those values are implementation artifacts under Mapper v1. They are not promoted to a claim of
41 verified semantic quotient states or a Reachability probability distribution.

The stage introduces a prospective Mapper v2 implementation, runs a diagnostic v1/v2 dual map
over the same 100 Qualified Raw trajectories, independently reconstructs every v2 State with a
second Reference Mapper, emits a contrast witness for every pair of diagnostic v2 States, and
separates pre-treatment Experimental Condition from post-treatment empirical Route. All v2
Assignments remain in memory or diagnostic rows only. Formal new State Assignment, frequency,
VTDO, Provider-call, Stage 2 Provider-call, and GPU-job counts are zero.

## Audit Remediation

| Audit finding | v26.159 remediation |
| --- | --- |
| P0: Raw Final representation used as result semantics | Mapper v2 consumes the Qualified Verifier's `observed_canonical_result`; Raw Final receives a separate audit hash and cannot enter State identity. |
| P0: Condition and empirical Route mixed | `ExperimentalConditionV2` contains only sampling mode, public condition, requested Path/strategy, and static Path catalog. `EmpiricalRouteSignatureV2` contains only observed typed events. |
| P0: task-level support pooled across conditions | State occurrence is reported per `(task_package_id, experimental_condition_id)`, with pooled, any-fixed-condition, and Unconditional summaries kept separate. |
| P1: Core authorization did not bind trajectory content | `valid_only_state_mapping_v2` takes the trajectory object as a Core argument and binds semantic content, bound artifact, Raw artifact, and Qualified Verifier input hashes before callback invocation. |
| P1: nested Pydantic hashing used `default=str` | `to_canonical_json_data()` recursively supports registered types and fails closed on unknown objects. Legacy `canonical_hash()` is unchanged for historical identity replay. |
| P1: Support, Instrument, and endpoint classifications overlapped | Prospective v2 projections separate Raw Instrument integrity, Measurement Support, resource accounting, Detour allowance, Provider response, public payload, model action, model terminal, and completed endpoint. |
| P1/P2: temporal quotient was underdefined | A content-addressed Temporal Quotient Policy commutes only independent successful acquisitions and preserves relative Failure, Verification, and Final/stopping order, and emits pairwise relations for other noncommutative actions. |
| P2: Evidence and provenance shared an untyped set | State lineage now uses typed `citation`, `evidence`, and `provenance` entries. |
| P2: references were inferred from arbitrary strings | Six exact Tool reference Schemas use typed argument/result paths with wildcard sequence positions; unknown Tools fail closed. |
| P2: State artifacts lacked difference witnesses | The stage emits 820/820 pairwise `StateContrastArtifactV2` rows over 41 diagnostic States. |
| Shared Mapper semantics weakened independent audit | A separate Reference Mapper independently normalizes payloads and rebuilds action classes, references, edges, temporal relations, Result, lineage, and failure pattern. |

The v1 modules remain byte-unchanged. Future callers must use the versioned v2 modules; the old
helpers remain available only to replay historical evidence.

## Strict Content Addressing

The new strict canonicalizer recursively handles:

```text
Pydantic BaseModel
Mapping with string keys
list and tuple
finite Decimal
Enum
date, time, and datetime
finite JSON float
JSON scalar and null
```

Unknown objects, non-string Mapping keys, NaN, infinity, and unregistered containers fail closed.
The trajectory address is split into:

```text
trajectory_semantic_content_hash  # excludes trajectory identity
trajectory_bound_artifact_hash    # binds identity to semantic content
raw_final_payload_hash             # audit only
canonical_result_semantics_hash    # enters quotient State identity
```

The v2 valid-only authorization additionally binds the Raw execution artifact hash and exact
Qualified Verifier input hash. A same-ID trajectory with a different Final payload fails before
the mapper callback; the Core passes the exact authorized trajectory object to the callback, so a
different closure-captured trajectory cannot substitute for it.

## Result Semantics Diagnostic

The zero-call minimal diagnostic replaces only Mapper v1's `result_semantics_hash` with the
already-frozen Qualified Verifier Canonical Result. It exactly reproduces the external audit:

```text
Assignments                                            100
Mapper-v1 States                                        41
Raw-vs-Canonical Result representation differences      45
Mapper-v1 States participating in result-only merges     14
Assignments participating in those merge groups         40
minimal result-only equivalence classes                  34
```

Thus `41 -> 34` is valid only for the single-field Result diagnostic. It is not the complete
Mapper v2 partition.

The full Mapper v2 simultaneously applies Canonical Result semantics, set-like field policy,
typed Tool references, typed lineage, strict JSON, and explicit temporal relations. Its diagnostic
partition is:

```text
Mapper-v1 State IDs                         41
Mapper-v2 diagnostic State IDs              41
v1 State IDs participating in v2 merges     12
v1 State IDs split across multiple v2 IDs    5
```

The equal net count is coincidental. Canonical Result and set semantics merge some v1 States,
while typed references and temporal policy split others. It does not validate the old partition.
Every diagnostic row records its v1 State ID, v2 State ID, Raw and Canonical Result hashes,
Experimental Condition, empirical Route Signature, and explicit merge/split reason. It also
records `historical_reclassified=false`, `frequency_authorized=false`, and
`vtdo_authorized=false`.

## Gold And Reference Controls

Five computed Gold State pairs pass:

```text
merge  independent successful acquisition order
merge  numeric JSON representation under one Verifier Canonical Result
split  failure/revision relative order
split  terminal-verification relative order
split  Final/stopping relative order
```

Both members of every pair also match the independent Reference Mapper. Across the historical
denominator, production and Reference Mapper v2 States match exactly for 100/100 trajectories.
The Reference Mapper does not call the production State builder and does not trust the embedded
production `typed_references`; it independently traverses the frozen Tool Schemas over Raw
arguments and Observation results.

The 41 unique diagnostic v2 States produce `41 * 40 / 2 = 820` pairwise contrasts. Every pair has
at least one typed witness among Task/Omega context, semantic policy, action payload or
multiplicity, typed lineage, dependency edge, Canonical Result, failure pattern, and temporal
relation.

## Condition And Route Decomposition

The 100 Qualified rows contain:

```text
unique pure Experimental Condition IDs                  29
Task x Experimental Condition cells                     37
Mapper-v1 mixed Route Projection IDs                    44
Mapper-v2 post-treatment empirical Route Signatures     44
fixed Task-condition cells split by v1 Route behavior    9
Unconditional Task-condition cells                       9
Unconditional cells split by v1 Route behavior           3
```

The pure Condition ID deliberately does not include task identity. The estimand cell is the pair
`(task_package_id, experimental_condition_id)`, hence 29 pure IDs and 37 Task-condition cells are
both correct. Empirical Route Signature includes observed Decision, Action, Tool, status, error,
and typed event-semantics hashes; it is an outcome descriptor and cannot be used as a conditioning
variable.

The frozen source Population has twelve tasks, but only ten tasks have at least one Qualified
trajectory in the 100-row mapping denominator. Missing tasks are not imputed as single-state.
Support descriptions are:

| Mapping | Across all conditions | Any fixed condition | Unconditional condition |
| --- | ---: | ---: | ---: |
| Mapper v1 | 10 | 8 | 4 |
| Result-only minimal diagnostic | 9 | 8 | 3 |
| Full Mapper v2 diagnostic | 9 | 8 | 4 |

These are counts of Qualified-covered tasks exhibiting more than one observed ID. They are not
frequency estimates and do not establish non-degenerate natural Explorer distributions.

## Measurement Classification

The 360 historical Raw rows are projected diagnostically under the future v2 decomposition:

```text
historical second-Detour Support Exits                         4
historical rows also projected as Instrument failures          4
those rows with Raw-native Instrument integrity                4
v2 Support/Instrument overlap                                  0
historical typed semantic rejections                           1
future v2 typed-rejection rows with evaluable model terminal    1
```

The four Detour rows remain historical Support Exits; the v2 projection shows how a future Runner
can preserve Raw Instrument integrity without counting the same boundary twice. The one typed
semantic rejection remains historically unchanged. Its v2 evaluability is a prospective
classifier result, not a retrospective validity label.

`classify_measurement_support_v2()` no longer catches arbitrary exceptions. A resolver must
return an exactly bound typed `available` or `unavailable` result. Programming exceptions
propagate as Instrument defects, and state/progress binding mismatches raise a Contract error.

## Artifacts And Identities

The final build writes fourteen detail artifacts plus one report. A second independent output
directory reproduces all fifteen files byte for byte.

- report:
  `finance_v26_state_semantics_audit_report:1af922c296dba8df78cec0082178e0e913d8ad228bb3b95dfe7371b06b73fd08`;
- historical Mapper-v1 freeze:
  `finance_v26_historical_mapper_v1_freeze:f27401fe9b6cf6dee32e41f3d0e759aadecbff377c13065575b4859ae028d163`;
- Result Semantics diagnostic:
  `finance_v26_result_semantics_diagnostic:619bedd401f7adec71044cfc5f7f9996aee1cf4798c8cd4b42010c89eb9e614f`;
- Condition/Route decomposition:
  `finance_v26_condition_route_decomposition:5395083b213c99855ad66fe1a6ff139d9f0df2e5f8871659f7684da6bc4d85ac`;
- fixed-condition support:
  `finance_v26_fixed_condition_state_support:afcfdfa1546838b68bfd7b30ca1b4205c39dad318c72f0fa6805d2989e1b9df7`;
- Mapper v2 semantic policy:
  `empirical_state_semantic_policy:588bf09238a4a16c830ad9216d40d311229b537204cdb383ebb117be2cededca`;
- valid-only Mapper v2 Contract:
  `valid_only_state_mapper_contract_v2:a2acb7b475dd7ce4558310f4ad207a09f9ffa270ad785051bf9b41d1d9b0281a`;
- Mapper v2 diagnostic Catalog:
  `finance_v26_mapper_v2_diagnostic_catalog:a69bb4bb74b2db97b22f0e772f53abc811c3e51e56cea94657cd2eb9f425eb53`;
- Mapper v2 State Catalog:
  `finance_v26_mapper_v2_state_catalog:4fdc6a73487a52c4076645a273aa3ea8039f5ee01eb4ef9ac7a0c9424aab782c`;
- State Contrast Catalog:
  `finance_v26_state_contrast_catalog:a77677a30e905e47727a313bb8c9167fe8e5124205acddd273ecc026a2c9ca95`;
- Gold State Pair audit:
  `finance_v26_mapper_v2_gold_fixture_audit:f8681ea7285d60fe4eaa4b3dc3a1bddd941f21843eae22adef585264cb876d49`;
- independent Reference Mapper audit:
  `finance_v26_independent_reference_mapper_audit:d9a4d4600ef130369dc95a98241c74e17a0260f98d169f983d0d24ea22398d46`;
- Measurement classification decomposition:
  `finance_v26_measurement_classification_decomposition:7e458d3882fd009edae9a1d33f72feaa55b8ecc202e6c005fc76793e922e74cd`;
- destructive audit:
  `finance_v26_state_semantics_destructive_audit:2dcb908c0cf9863ca8a54d52243c8ac1a835d74a9f60a70409cc2bd2c19f287b`;
- transition:
  `finance_v26_state_semantics_transition:17fe66c33e8c2d0f284b0d06bb85a881f61f7d52ff685a74e5f6c26cade44f31`.

## Verification

```text
new v2 Core and v26.159 tests                 24/24 passed
historical Mapper-v1 and valid-only tests     11/11 passed
v26.156-v26.158 artifact constraint tests       3 passed
v26.158 full transitive rebuild                 1 setup error
focused Ruff                                      passed
package-wide Ruff                                 passed
focused Mypy over nine new source files           passed
package-wide Mypy                    495 files, four historical diagnostics
formal/independent v26.159 files            15/15 byte-identical
destructive mutations                         12/12 failed closed
Provider calls                                    0
Stage 2 Provider calls                            0
GPU jobs                                          0
```

The v26.158 full-transitive setup error is not an assertion failure. The checked-out repository
lacks the historical bound file
`finance_v25_44_hardened_stopping_evidence_snapshot_v3_20260816/finance_stopping_evidence_snapshot.jsonl`,
the same missing-file limitation identified by the external audit. The three artifact constraint
tests that do not require that absent file pass. Package-wide Mypy retains the three historical
v26.70/v26.129 diagnostics and one diagnostic in byte-frozen v26.154; v26.159 contributes zero.

## Transition

The only permitted next stage is:

```text
fresh_mapper_v2_reachability_frequency_experiment_preflight_only
```

That successor may design and credential-free preflight a new experiment only. It must use a
fresh model-unexposed Population, Mapper v2, the pure Experimental Condition index, complete
Measurement Support denominator, separate Unconditional and conditioned strata, task-primary and
rollout-secondary statistics, and an independent postrun audit. It may not pool conditioned rows
into a natural Explorer frequency.

Provider execution, historical rerun or reclassification, current-denominator frequency,
State-probability, VTDO Energy/Novelty/Contribution, training, release, and production use remain
unauthorized.
