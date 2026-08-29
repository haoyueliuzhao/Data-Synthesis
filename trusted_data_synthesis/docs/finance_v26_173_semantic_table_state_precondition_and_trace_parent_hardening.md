# Finance v26.173 Semantic Table, State Precondition, And Trace Parent Hardening

Audit date: 2026-08-29

## Decision

Finance v26.173 consumes only:

```text
capability_observation_semantic_table_deleak_state_precondition_and_trace_parent_hardening_only
```

The bound external audit is exactly 25,187 bytes with SHA-256
`b5a67c76303687e81ccaf3b6fc966b4a579ca25011df6ee5887e9e785c5949e7`.
Credential lookup, Provider-client construction, Stage 1 or Stage 2 Provider calls, Development
Jobs, sealed Confirmation payload access, GPU jobs, Mapper calls, State Assignment, frequency,
Contribution, VTDO, Student visibility, training, release, and production use are zero.

The stage preserves every v26.172 file and local result. It blocks, without execution, the
v26.172 transition
`capability_observation_dynamic_depth_development_runner_preflight_only`. The reviewed semantic
table, current-State acceptance, step-execution, and parent-validation defects are all in objects
that the stale transition was not authorized to change.

The strongest v26.173 result is a credential-free static and local-runtime hardening result over
the exact 32 Development Packages and 192 six-Replica reference executions. It is not a Runner
preflight, model behavior, a Development outcome, an empirical depth boundary, or a general
model-visible noninterference proof.

## Predecessor Freeze And Defect Reproduction

All 22 authoritative v26.172 formal files are rebound without mutation. The predecessor report,
source Root, Catalogs, audits, and transition remain historical evidence and are not rewritten or
reclassified.

The implementation independently reproduces the reviewed blockers before constructing a v26.173
replacement:

```text
target States                                                   80
six-Replica presentations                                      480
States with one stable decoded value-index rule                 40
stable-index reference recoveries                              240
States with unique decoded operation length                     32
decoded-length reference recoveries                            192
minimum-action-ID reference recoveries                         197
wrong-current-Rule Recovery Candidates                          20
old Base-true plus semantic-Mechanism-true Recovery conflicts    6
v26.172 baseline event projections                             192
accepted fully rehashed parent mutations                         4
```

The external report states that 56 States have an imbalanced reference action-ID rank. Direct
recomputation from the exact v26.172 Catalog finds 64. v26.173 preserves both values under
separate fields:

```text
external_reported_action_id_rank_imbalanced_state_count     56
direct_recomputed_action_id_rank_imbalanced_state_count     64
```

The difference is reported rather than silently reconciled. Both counts establish the reviewed
structural imbalance, and neither is reused as evidence for the replacement surface.

The four accepted old parent mutations independently alter and rehash a reference path, a
Mechanism execution parent, a display-to-operation mapping, or Runner input topology. Acceptance
means that v26.172 content hashes were internally self-consistent but were not all reconstructed
from the exact authoritative source objects.

## Replica-Local Semantic Tables

The v26.173 model-visible table removes the stable State-wide value indices reviewed in v26.172.
For each exact `Package x Component x Replica x field`, it creates a fresh opaque value-handle
assignment. A handle has meaning only inside that field table and Replica. The complete public
operation remains decodable from the current Prompt, but neither an index nor a handle vector is
stable across Replicas.

The construction additionally freezes:

1. independently phased field assignments;
2. balanced reference value-handle rank per State;
3. balanced reference action-ID, display-handle, Legend, and Candidate rank;
4. fixed-width public handles and equal canonical encoded-operation length within a State;
5. no model-visible padding field;
6. no operation-derived public identifier.

Field order is deterministic and pre-outcome. It first uses public discriminative cardinality and
then a content hash. The per-field phase schedule prevents a multi-field three-Choice State from
making the reference operation the all-minimum or all-maximum vector in every Replica.

Across 80 States, 480 presentations, and 1,356 displayed Candidate rows:

```text
stable cross-Replica value-handle vectors             0
reference action-ID rank imbalances                   0
reference value-handle rank imbalances                0
reference display-handle rank imbalances              0
reference Legend-position imbalances                  0
reference Candidate-position imbalances               0
visible padding fields                                0
```

## Stratified Shortcut Gate

The audit does not accept a global `x/480` aggregate as sufficient. It freezes 80 exact strata
keyed by capability family, depth, decision kind, Choice count, source group, and Component. Each
stratum contains six Replicas and admits no registered selector above its structural baseline:

```text
maximum successes per stratum = 6 / Choice count
```

Thus a two-Choice stratum permits at most three recoveries and a three-Choice stratum at most two.
All 80 strata pass and the excess-stratum count is zero.

The ten registered selector totals are:

```text
action-ID lexical order                 174 / 480
Candidate position                     174 / 480
display Choice-handle order             174 / 480
Legend position                        174 / 480
semantic-catalog lexical order          146 / 480
minimum value-handle vector             146 / 480
maximum value-handle vector             146 / 480
argument-field order                      0 / 480
encoded operation length                  0 / 480
fixed value-handle vector                 0 / 480
```

The 174 and 146 totals are sums of per-stratum structural baselines, not tuned global thresholds.
The formal claim is limited to these registered stratified structural shortcuts. It does not
claim universal statistical independence or resistance to every learned feature.

## State-Bound Recovery Acceptance

v26.173 makes `ActionAcceptanceReport` a hard parent of Mechanism and Qualified validity. For a
Recovery revision, the selected Rule must equal all three current public bindings:

```text
current failed Rule
failure-receipt Rule
retry Rule
```

The Runtime retry consumes the selected Rule handle and the exact matching failure receipt. A
State-invalid action emits a typed `target_rule_mismatch` rejection before retry; it cannot enter
Mechanism qualification or Qualified validity merely because a different Rule would form a
successful abstract Recovery path.

The complete wrong-current-Rule surface now produces:

```text
wrong-current-Rule Candidates                    20
State-precondition invalid                       20
typed target mismatch                            20
accepted actions                                  0
retry invocations                                 0
semantic-Mechanism-qualified                      0
Base-valid                                        0
Qualified-valid                                   0
```

The 20 exact reference Recovery component executions separately pass Rule/receipt/retry lineage
and Qualified validity. Forty row-level bindings cover the reference and rejected cases. This is
a current-State semantic repair, not a reclassification of any v26.172 row.

## Production Step Runtime

The new production API is explicitly incremental:

```text
initialize
render_next_prompt
step
finalize
```

It does not call or filter a v26.171 or v26.172 complete baseline execution. It receives no
static reference Trace, future Prompt, or precommitted Choice vector. Each call renders only the
current public State, accepts one displayed action, validates it, executes its source operation,
persists the resulting Runtime events and public Observation, and derives the next State from
bound predecessor receipts.

Reconciliation retains one live Finance Runtime from normalization emission through reference
consumption and final calculation. For D0-D2, fixed non-target support operations required for
task completion are derived from the public source graph and actually execute at finalize; they
are not copied from a future Trace.

The local reference fixture records:

```text
Packages                                           32
Replica executions                                192
initialize calls                                  192
current Prompt renders                            480
step calls                                        480
public Observations                               480
actual local Runtime events                     1,104
predecessor-conditioned Prompts                   288
bound predecessor-receipt links                   480
finalize calls                                    192
reference Qualified executions                    192
complete baseline Result loads                      0
baseline-event filtering                            0
static reference-Trace inputs                       0
Provider calls                                      0
Development Jobs                                    0
```

The separate Runner Input Catalog contains 32 Packages, zero materialized Prompt or Observation,
no reference-Trace payload, no precommitted Choice vector, and only source-bound topology needed
to initialize a future step Runtime.

## Exact-Source Parent Reconstruction

Saved child hashes are never accepted as their own semantic oracle. The parent validator rebuilds
each object from exact authoritative source inputs and compares the reconstructed bytes and
identities. It covers:

```text
Package reconstructions                            32 / 32
Prompt reconstructions                            480 / 480
display/source mapping matches                    480 / 480
reference operation matches                      480 / 480
Observation/effect matches                       480 / 480
receipt-parent matches                           480 / 480
Mechanism-report matches                         192 / 192
reference-path matches                            32 / 32
Runner-input topology matches                     32 / 32
```

Four attack controls change one semantic parent and then recompute every affected descendant
identity before validation:

1. a changed reference path;
2. a crossed Mechanism execution parent;
3. a rank-preserving semantic value swap behind one display handle;
4. reversed Runner topology.

All four are fully rehashed and all four reject against exact-source reconstruction. Together
with malformed-handle, duplicate-value, future-Prompt, precommitted-vector, baseline-load,
empirical-estimand, Confirmation-access, and Provider-authorization controls, all 19 production
mutations reject and acceptance count is zero.

## Sequential Estimand Registration

The successor protocol now has distinct future fields for:

```text
per-step conditional success
first failed target Component
target-Component hazard
complete Package success
task Base validity and Mechanism qualification
```

v26.173 registers only the schema. Empirical rows, conditional-step estimates, Component-hazard
estimates, Package-success estimates, and latent-ability-boundary claims are all zero. D0-D3
remain bounded sequential target-decision depth. No monotonic success assumption or latent
capability threshold is inferred from static execution.

## Reproducibility And Checks

The formal directory contains 21 files and 10,783,941 bytes. Its report SHA-256 is
`df22bd406dea069101f5f921b9ead6e8b9f905b110d886d5371e1bc6ae475283`.
The transitive implementation Root contains 314 local files with zero unresolved
`trusted_synthesis` imports.

Focused Pytest passes 6/6 in 61.05 seconds, including a complete empty-directory byte-identical
rebuild. The complete adjacent v26.172 regression passes 6/6 in 28.88 seconds. Focused PyCompile,
Ruff check, Ruff format check, and no-import-follow Mypy pass the four new modules. Package-wide
Ruff passes.

No package-wide Mypy pass is claimed. The unchanged Python 3.14 / Pydantic 2.13 environment is
already documented by v26.172 as reporting 5,692 historical recursive-import diagnostics across
158 files; v26.173 relies on the focused no-import-follow check for its new modules and does not
reinterpret that historical toolchain result.

All fifteen noncompensatory static Gates pass. Provider calls, Development Jobs, Confirmation
payload loads, empirical rows, and historical mutations are zero.

## Authoritative Identities

- report:
  `finance_v26_semantic_table_trace_hardening_report:a3abb3c22ffe6b1933bc519a087073d17a15aa3ce990af6b73ba9a9e4af8a3fc`;
- transitive source Root:
  `finance_v26_semantic_table_trace_transitive_source_root:c53d1f8364dd5db8625f592327530ef553c471c103682b3588ea8b3b6beccbdc`;
- external authorization:
  `finance_v26_semantic_table_trace_external_authorization:a190a824c504da6e296159439aa5a735f2742687c9ed62ff944e3c6803625307`;
- v26.172 predecessor freeze:
  `finance_v26_v172_predecessor_freeze_audit:8ff5dadf9d8673e726d80cd17cdf403af6a8079f76ca07dc05b95416c0e00971`;
- v26.172 defect reproduction:
  `finance_v26_v172_semantic_trace_defect_reproduction:dd8142d46471bb61a9e5f5572af25d9209db1bf32ecf97192bf7936a0e8649fd`;
- Semantic Table Presentation Contract:
  `semantic_table_presentation_contract:e92c6c4aa42d1b701df7313bfafe141ecdc7eabf6f606492db3057eedf396ea6`;
- State Precondition Mechanism Contract:
  `state_precondition_mechanism_contract:eed1a675f1a66de0661cabb4a1ee1493e29f7a5b518d4a080fa56086fc94ab47`;
- Production Step Runtime Contract:
  `production_step_runtime_contract:acd669ad81c61205c79c3e887790504a4967dc9f04a53b909bf796f5d7a1226d`;
- Semantic Parent Reconstruction Contract:
  `semantic_parent_reconstruction_contract:ee7194442a8bdf7864742d1aa1c9d162e57bd0ac6b03b4bed796a241992cc75e`;
- Sequential Estimand Contract:
  `sequential_depth_estimand_contract:9fee09c5b3f4e750ce7ffaf58b7656d32d1d60513346abefc59ab19039dab4ae`;
- Development Catalog:
  `finance_v26_semantic_table_trace_development_catalog:fd88c80b47d3d773f4e4eee7fe09223815503be408dd5be229e68abf5943a264`;
- zero-Prompt Runner Input Catalog:
  `finance_v26_semantic_table_trace_runner_input_catalog:8e60961a0aeb67be24c8332fadfe22f5d65db5d5a4ba1fa6880729bcbf7049a6`;
- stratified shortcut audit:
  `finance_v26_stratified_semantic_table_shortcut_audit:22e17bac831f3809cbb13caa82a50b073a8a701634e3831d516e9993d1bcca23`;
- Recovery State audit:
  `finance_v26_recovery_state_consistency_audit:1a7035c06c97b5c011eeeba57af34e12a8b91174b632a02cae3dc4779cc172be`;
- true Step Runtime audit:
  `finance_v26_true_step_runtime_audit:99a427db836f53d55a27847384858c946559b500998723ebbe7ff96ee3045dea`;
- semantic parent reconstruction audit:
  `finance_v26_semantic_parent_reconstruction_audit:e5a319198e17c8e052404f3fa78b885b567b038718d178e36c8dc3668d462960`;
- sequential estimand registration audit:
  `finance_v26_sequential_estimand_registration_audit:1b47e917108b461514ad0ec8c927cab88bcf684facd8df3f318e2fb68d29c7fd`;
- destructive audit:
  `finance_v26_semantic_table_trace_destructive_audit:3445ae0859d793435d5cfceee99de32ea413ab0b1161c4c59e584da9b2e81559`;
- static audit:
  `finance_v26_semantic_table_trace_static_audit:796c729fd60ce62029ef1804d890561f78ffb3b22441e5ac908caa485e540398`;
- transition:
  `finance_v26_semantic_table_trace_transition:64fe397080aa6b8fe06388354248d44b851ffb08d3a78c0eda67cc268f06bc3c`.

## Permitted Transition

The only permitted transition is:

```text
capability_observation_state_bound_step_runtime_development_runner_preflight_only
```

The successor may materialize only the exact future 192-Job Development Manifest and complete a
credential-free, one-current-Prompt-at-a-time Runner preflight from the exact v26.173 zero-Prompt
Runner Input Catalog. It must bind every exact source Package, Replica-local semantic table,
stratified presentation, Action Acceptance, current-State Recovery Rule and receipt, incremental
Runtime state, Observation, Base/Mechanism/Qualified report, reconstructed semantic parent,
sequential-estimand schema, fixed condition, model/Thinking, Grammar, Policy, resource, threshold,
terminal, and sealed Confirmation receipt.

Provider execution, Development outcomes, reference-Trace loading as Runner input, precommitted
Choice vectors, future-Prompt materialization, complete baseline Result loading, Confirmation
payload loading, source/task/Component/Candidate changes, presentation or validity tuning,
threshold changes, historical rewrite or reclassification, Mapper, State, frequency,
Contribution, VTDO, Student visibility, training, release, and production remain forbidden.
