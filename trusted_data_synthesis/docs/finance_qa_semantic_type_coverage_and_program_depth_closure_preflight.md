# Finance QA Semantic-Type Coverage And Program-Depth Closure Preflight

## Post-Freeze Identity Erratum

The formal semantic-coverage JSON directory is immutable and remains the evidence authority. The
original prose recorded pre-write identities for its row Manifest, Decision, and Transition.
Direct revalidation of the frozen JSON gives:

```text
row Manifest  offline_qa_semantic_coverage_row_manifest:
              5967b1e2d803f554d53fbc2bf6ffc372172d234c95010b59cfa87114d673c687
Decision      offline_qa_semantic_coverage_decision:
              d1d01104cf54810d5407717de762233eedfd752ff64cf42997a85996b0c69060
Transition    offline_qa_semantic_coverage_transition:
              1bf08f075b2bf6ffa45b83b4175cfba80c525e57df57a69e6d53e0a515d1f924
Manifest      offline_qa_semantic_coverage_artifact_manifest:
              b5b83ba05cc59ad723620ec7ff672e069f9eb938ce3d53eb611faea2b091ca6b
Root          offline_qa_semantic_coverage_artifact_root:
              a34e87e38ccdf06e1a4eb9941eaae91d96ccc522f963626d90f1b5ad6758f8ba
```

This post-freeze documentation erratum changes no formal JSON byte, identity, Manifest, Root,
row, decision, or transition. References later in this document that show different row-Manifest,
Decision, or Transition identities are superseded by the exact values above.

## Scope And Decision

This independent QA side-path consumes only
`offline_qa_semantic_type_coverage_and_program_depth_closure_preflight_only`.
The exact 19,325-byte external review is bound at SHA-256
`c6efa19fd1c5ad9df0d7ebb2916ed66f57e4f5921fcdc8a9f1578ef5c225f16d`.
The exact 51-byte operator directive `参照审计报告给出的方案逐项修订优化` is separately
bound at SHA-256
`7f441e43f03a244a1ecab4ec08cca9e8572d874bafb8c8cc31c5ff32badc83c5`.

The resulting decision is:

```text
offline_qa_existing_finance_pattern_catalog_semantic_type_coverage_and_
program_depth_closure_preflight_passed
```

This is a credential-free constructive preflight over the eight task types already present in
the Finance Pattern Catalog. It is not evidence of real-world Finance QA distribution coverage,
Provider model behavior, empirical task difficulty, QA release quality, training usefulness, or
production readiness.

The stage performs zero Provider calls, credential lookups, GPU Jobs, Development Jobs,
empirical evaluations, or VTDO writes. It does not use, consume, mutate, or become a parent of
the v26.223 online authorization or the frozen v26.194/v26.222 VTDO condition.

## Authorized Repair Partition

The external review authorizes three ordered phases:

```text
A  read-only Census of the existing future QA pool
B  generic public-Plan candidate execution
C  materialization of all eight existing Finance Pattern types
```

The review requires phase D to occur only after phases A-C pass. Consequently, this stage does
not add `argmax`, `select_by_period`, entity-table growth/filter/intersection, or rank Operations.
The following two Raw proposals remain explicitly deferred:

```text
temporal_peak_secondary_lookup
growth_filter_margin_rank
```

The authorization identity is
`offline_qa_semantic_coverage_revision_authorization:2883176c87a40718b625cb130f24290ba52f8b4d9ed4671f61ffc53b4dbb0851`.

## Phase A: Exact Baseline Census

The stage reads and revalidates the complete prior future QA directory at
`artifacts/qa_realization_vnext/future_qa_candidate_population_v2_20260901`.
It binds all 18 files and 1,233,274 bytes, checks all seventeen self-excluding Manifest members,
and requires the saved Manifest and Root:

```text
Manifest  future_qa_preoutcome_candidate_manifest:
          18523303bb2fed9df208205bc7fb44e92cde6bff9d46dd179220b3a8af1990ad
Root      future_qa_candidate_artifact_root:
          9caf67aa43317415f0227b5ae6ea4f78dd5cf68a9fb0d1491436f13494081e04
```

The baseline Census confirms the review's diagnosis:

```text
semantic instances / surface candidates / selected surfaces     4 / 16 / 8
task types / Program topologies / Answer Schemas                 1 / 1 / 1
registered comparison pairs                                      4 / 6
semantic-instance depth distribution                            {1: 4}
surface-row depth distribution                                 {1: 16}
renderer controls per semantic instance                               4
non-null ProgramExecution rows                                        0
```

The old pool remains a valid immutable single-type surface-realization control. This stage does
not rewrite it. Its new read-only Census identity is
`baseline_qa_semantic_census:0d6fc5b4dbefe3193336c465e41e36fb46ed2591d92dda88bd8a2cf606588808`.

## Phase B: Generic Public-Plan Candidate Executor

The new `PublicPlanCandidateExecutor` takes one `RealizedTaskPackage`, its
`CanonicalSemanticPlan`, exact `BindingSnapshot`, an `EvidenceCorpus`, and an
`OperationRegistry`. The execution order is:

```text
validate exact BindingSnapshot Evidence IDs, versions, and source records
  -> resolve every public evidence role from public semantic constraints
  -> reconstruct the complete public Program skeleton
  -> require exact source Program ID and hash
  -> map every reconstructed node to exactly one CanonicalSemanticPlan node
  -> require exact node and dependency-edge sets
  -> execute every node in topological order through its Registry executor
  -> materialize one node-bound TrajectoryStep per Program node
  -> replay every output through the independent Oracle-verifier implementation
  -> apply public data-driven result projection and bind complete citations
  -> persist non-null ProgramExecution inside the candidate Trajectory
```

The candidate executor never reads `task.oracle` as a behavior source. The hidden Oracle Program
is used later only by the pre-existing independent `CandidateWorkflowVerifier`, after the
candidate trajectory already exists. The new executor contains no `task_type` result branch.
Its result projection is driven by public Answer Schema data.

Two previously implicit answer projections are now public and declarative:

- fact retrieval projects the unique bound Evidence source into `source_id`;
- derived growth comparison projects both intermediate growth nodes, the terminal comparison,
  and the public entity labels into the nine-field labeled answer.

The executor Contract identity is
`public_plan_candidate_executor_contract:640a06e87c2251ff76aa3eb6e9f77fad36aa6f182ae6e760d3924ab6e04683ea`.

## Phase C: Eight Existing Task Types

The semantic denominator contains thirteen exact BindingSnapshot-level instances. Renderer
children are kept separate: exactly two surface realizations are materialized per semantic
instance, for 26 surface controls total. Only one surface sibling per semantic instance is used
for the semantic execution row.

The task-type distribution is:

| Task type | Semantic instances | Program nodes | Edges | Maximum dependency depth |
| --- | ---: | ---: | ---: | ---: |
| `fact_retrieval` | 1 | 1 | 0 | 1 |
| `comparison` | 1 | 1 | 0 | 1 |
| `registered_cross_metric_comparison` | 6 | 1 | 0 | 1 |
| `temporal_growth` | 1 | 3 | 2 | 2 |
| `temporal_average` | 1 | 4 | 3 | 2 |
| `temporal_absolute_change` | 1 | 3 | 2 | 2 |
| `registered_ratio` | 1 | 3 | 2 | 2 |
| `derived_growth_comparison` | 1 | 7 | 6 | 3 |

All six registered comparison pairs are represented:

```text
current_assets/current_liabilities
operating_cash_flow/net_income
revenue/gross_profit
revenue/net_income
revenue/operating_income
total_assets/total_liabilities
```

The complete constructive result is:

```text
registered / materialized task types                         8 / 8
semantic instances / renderer controls                    13 / 26
Program topologies / parameterized Programs                 8 / 13
Answer Schema identities                                         7
semantic depth distribution                         {1: 8, 2: 4, 3: 1}
Program node distribution                           {1: 8, 3: 3, 4: 1, 7: 1}
non-null ProgramExecution                               13 / 13
exact Plan-to-trajectory matches                        13 / 13
independently replayed complete executions              13 / 13
existing CandidateQualityEvaluator accepted             13 / 13
```

There are seven Answer Schema identities because `comparison` and
`registered_cross_metric_comparison` intentionally share the same public comparison result
shape. This is reported as an observed result rather than inflated to eight.

Every task includes `evidence.search` in its tool set. The seven calculating types also include
`calculator`; fact retrieval contains only `evidence.search`. Retrieval is resolved and planning
is `plan_given` for all thirteen constructive controls. These facts do not imply autonomous
planning or open retrieval capability.

The semantic Coverage Census identity is
`offline_qa_semantic_coverage_census:548857ac3a09a94a6368197e1693af5ccee297ae2aa8908495a94b6bb217c539`.
Its exact thirteen-row Manifest is
`offline_qa_semantic_coverage_row_manifest:4f3ff7553a1e9eb94495102ab34d406ce235ab76ae441605188473f49af61b1b`.

## Negative Controls

Four controls reject before any formal output write or Provider boundary:

```text
missing exact bound Evidence
cross-version Evidence substitution
Registry without registered_compare
public Program parameter substitution
```

The result is:

```text
controls / rejected / accepted        4 / 4 / 0
attack output writes / Provider calls     0 / 0
```

The Audit identity is
`offline_qa_semantic_negative_control_audit:e505ab3c9209eef4a46fe81a502bc3618e8e65f3e48b1401bd497eda7b33683e`.

## Noncompensatory Gates

The exact Gate partition is:

```text
A0 exact external scope                                             PASS
A1 baseline single-type Census frozen                               PASS
A2 public Plan executor source-bound                                PASS
A3 existing Catalog types materialized 8/8                          PASS
A4 registered comparison pairs materialized 6/6                     PASS
A5 exact depth strata 1/2/3 observed                                PASS
A6 nodewise execution and independent replay exact                  PASS
A7 negative controls reject                                         PASS
A8 phase-D new Operations remain deferred                           PASS
A9 zero Provider/GPU/Development/VTDO boundary                      PASS
passed / failed                                                    10 / 0
```

The Gate identity is
`offline_qa_semantic_coverage_gate_evaluation:327a6ff24e4c821c11f483de4e85f9101474c74c9eb82ecbffa2d801289ec8ff`.

## Identities And Reproducibility

Principal identities are:

- Decision:
  `offline_qa_semantic_coverage_decision:e6f4acc8524c0407bb48901c4866b77df046249b7e3b2343a569f2949b0b09ea`;
- Transition:
  `offline_qa_semantic_coverage_transition:54ea86b216fe7caf4875b1eb955592ae0442ee2eccd8fa81a7eac752b2a4c955`;
- Report:
  `offline_qa_semantic_coverage_preflight_report:8beb3aff5720514d91d3b0c903725d164cd70d25b945b5fda322383544ebb653`;
- Artifact Manifest:
  `offline_qa_semantic_coverage_artifact_manifest:b5b83ba05cc59ad723620ec7ff672e069f9eb938ce3d53eb611faea2b091ca6b`;
- Artifact Root:
  `offline_qa_semantic_coverage_artifact_root:a34e87e38ccdf06e1a4eb9941eaae91d96ccc522f963626d90f1b5ad6758f8ba`.

The exact source commit/tree are:

```text
commit  530a700eae1aa33fddb41f4f48bd99bd17798bd7
tree    070595f1293b18fc282246d7e9542ba572a0914b
```

The formal directory contains seventeen files and 810,715 bytes. Its self-excluding Manifest
binds sixteen files and 808,285 bytes. Focused tests pass 8/8, including two independent formal
directory builds with exact path and byte equality. Focused PyCompile, Ruff check/format, and
no-import-follow Mypy pass. The adjacent candidate, Finance Pattern, QA realization, and prior
future-QA tests pass 51/51; package-wide Ruff passes.

## Transition And Remaining Boundary

The only permitted successor is:

```text
offline_qa_semantic_type_coverage_and_program_depth_closure_
preflight_independent_audit_only
```

That audit must independently rederive the baseline Census, rebuild all thirteen semantic
instances and 26 renderer controls, reconstruct every public Program and exact node/edge map,
replay every node without using candidate outputs as an oracle, rerun the four negative controls,
and verify the formal directory byte for byte. It may not add new Operations or make Provider
calls.

Only after a passing independent audit and a separate new authorization may phase D consider one
deferred Raw proposal at a time. Real-world benchmark distribution coverage, Provider execution,
QA Release Population construction, VTDO integration, training, release, and production remain
unauthorized.
