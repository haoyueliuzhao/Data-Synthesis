# Finance QA Generator Source Commit/Tree/Member Authority And Depth-Metric Repair Preflight

## Scope And Decision

This QA side-path consumes only
`qa_generator_source_commit_tree_member_authority_repair_preflight_only`. The exact 21,798-byte
external review is bound at SHA-256
`118445beed3d77d53cd66b8d1cb4594c4111b7bfd430f6d3ed2360ba01b65033`. It retains the
eight registered fixed-fixture generator/verifier results, fails the predecessor's stronger G2
source-authority interpretation, and authorizes only a credential-free source-authority and
depth-metric repair. The exact 44-byte operator directive `参照审计继续修订优化QA合成链路`,
SHA-256 `d7312594a41e3ad1ca523fd87399cc52205bc6c63e9d81bd8552754d916c7fa7`,
is admitted only for that scope.

The resulting decision is:

```text
qa_generator_source_commit_tree_member_authority_repair_preflight_passed_
independent_audit_required
```

The repair verifies actual Git commit, tree, blob, committed-byte, and current-byte relations for
the fourteen retained generator/verifier sources and five new repair implementation sources. It
also replaces three previously conflated depth labels with four explicitly noninterchangeable
metrics. All eight fixed canonical cases still execute and verify, but their maximum semantic
operation depth is only two and no semantic-depth-three case exists.

Provider calls, credential lookups, GPU Jobs, online Job Manifests, empirical rows, QA Release
objects, VTDO rows, training rows, and production rows are zero. This stage is not Archive
grounding, realistic-difficulty calibration, Benchmark-distribution measurement, online
generation, or Release authorization.

## Immutable Predecessor And Scope Correction

The complete predecessor formal directory is revalidated before the repair is admitted:

```text
formal files / bytes             19 / 449,574
Manifest members / member bytes  18 / 446,741
formal bytes modified                       0
```

Its immutable identities remain:

- Manifest: `qa_generator_totality_artifact_manifest:d8c7ce9ad3ea97a15aaeaf170f8680359e88dffbbf045f3e1ddda294c6c17853`;
- Root: `qa_generator_totality_artifact_root:f2d08a0b4eb35b51b65a901bddb7ce794b2357bced0e6673d819ccf05bcf63db`;
- Report: `qa_generator_totality_report:595e1166ebcbdeb4e9f924a562cad65b540237332ebe3ca158e9a797677d23ee`;
- Transition: `qa_generator_totality_transition:dbfddcc94d86907c9120b71dacfd4e85a1f0d5d66020f94307e5af75a1d3e642`.

The new Freeze is
`qa_generator_source_authority_predecessor_freeze:454893143af7f57d952dff22e1aae4d4c5905519c17bbe7f0db21049b2df34d1`.
No predecessor JSON, Manifest, Root, row, Report, or Transition byte is changed. Its 8/8 fixed
Fixture behavior remains evidence, but its historical `G2_source_bound_successor_generator`
interpretation is superseded because the old builder accepted caller-supplied commit/tree labels
without proving their Git relation.

## Exact Git Source Authority

The new authority resolves `commit^{commit}` and `commit^{tree}` through Git, reads every member
with `git show <commit>:<path>`, records its blob object, and requires current execution bytes to
equal committed bytes. Requested and resolved identities must agree. The Gate is derived from
these checks; the predecessor's self-declared `finance_numeric_candidate_v7_source_bound=True`
and `registered_catalog_totalized=True` fields are not authority.

### Retained generator/verifier binding

```text
requested / resolved commit  dba5d949a743dd625e5fe0e10b0f4809ac9f87ad
requested / resolved tree    d706531377e5303265cd2dcee3e355c6642c466b
source members                                                   14
members present at commit                                    14 / 14
committed/current byte matches                               14 / 14
commit object / commit-tree relation                    commit / true
path-set SHA-256            2d24258e2d540715069bb5ba207d3b559bb45b2e44213fcb595182d2911e3146
file-set SHA-256            f5ea13aaf82a6fb216a47e8b967035bcef73c50daeb7aae61b846a281db2634e
```

The fourteen exact members are:

```text
core/evaluation/answer.py
core/evaluation/evaluator.py
core/operations/program.py
core/operations/registry.py
core/trajectory/candidate_verifier.py
core/trajectory/public_plan_executor.py
domains/finance/operations.py
domains/finance/pattern_runtime.py
domains/finance/patterns.py
domains/finance/policy.py
domains/finance/tasks.py
experiments/finance_pilot/candidate.py
experiments/qa_generator_totality/preflight.py
experiments/qa_semantic_coverage/preflight.py
```

All paths above are rooted at `trusted_data_synthesis/src/trusted_synthesis/`. The Binding is
`qa_generator_authoritative_source_binding:cd4f225e2e27fa8006828bf4deadd847ad1113d69e9c1c7a0e0d9e3cb3d3e7e9`.

### Repair implementation binding

```text
requested / resolved commit  f26e30c0c6488e5b14b2004bd776e23f23dbc77d
requested / resolved tree    7917ca2e0172394d2779d0186d1046bda872555c
source members                                                    5
members present at commit                                      5 / 5
committed/current byte matches                                 5 / 5
commit object / commit-tree relation                    commit / true
path-set SHA-256            674da32629598c78f6a49fe2a6fe88a6a798178732d5698c5453cbeab3ac9999
file-set SHA-256            3c4f739eeb9520b69efb2e6da6a78da8bceb4e922f7bd025ff5b7bf21aa82284
```

The five exact members are:

```text
trusted_data_synthesis/src/trusted_synthesis/core/task/program_depth.py
trusted_data_synthesis/src/trusted_synthesis/experiments/qa_generator_source_authority/__init__.py
trusted_data_synthesis/src/trusted_synthesis/experiments/qa_generator_source_authority/depth.py
trusted_data_synthesis/src/trusted_synthesis/experiments/qa_generator_source_authority/models.py
trusted_data_synthesis/src/trusted_synthesis/experiments/qa_generator_source_authority/preflight.py
```

The Binding is
`qa_generator_authoritative_source_binding:df21b1f4f733f199a741007fb602c36bfa6cb5683eae8c3e1dbd00232f7937ff`.
Thus the code that defines and admits the repaired authority and all four depth metrics is itself
inside the exact commit/tree/member authority.

## Reproduced Legacy Counterexample

The preflight executes the old `_source_binding` with:

```text
source_commit  0000000000000000000000000000000000000000
source_tree    1111111111111111111111111111111111111111
```

The old Binding is constructed as
`qa_generator_totality_source_binding:f9ee1a7058720579564b6e03bc590340f858984285f104410ba747bb2358fc58`.
Its self-declared source-bound and catalog-totalized fields remain true and its old G2 predicate
evaluates true. Presenting the same nonexistent commit to the repaired authority is rejected at
`git_commit_resolution` with `GitSourceAuthorityError`; the reason SHA-256 is
`10078ab8a5517a9c04c0cdbfc80492748eb3c076d5c486c4a47f6f6c2e5e9726`.

This directly demonstrates both facts without rewriting the predecessor: the old source-binding
claim had a counterexample, while the new authority rejects that exact counterexample. The Audit
identity is
`qa_generator_legacy_source_counterexample_audit:5b2ad1f7d0083aaa8516bd2d39c759e04081df6173acaefe42c76bad6d311d8f`.

## Five Source-Authority Attacks

Five actual controls reject before any output write or external execution:

| Attack | Rejection stage | Exception | Reason SHA-256 |
| --- | --- | --- | --- |
| `nonexistent_commit` | `git_commit_resolution` | `GitSourceAuthorityError` | `10078ab8a5517a9c04c0cdbfc80492748eb3c076d5c486c4a47f6f6c2e5e9726` |
| `real_commit_wrong_tree` | `commit_tree_relation` | `GitSourceAuthorityError` | `238fb4374af8c14b2452ce5250952b4de7725ffcdd3fe7c431cf1b304878d725` |
| `changed_source_member` | `committed_member_bytes` | `GitSourceAuthorityError` | `d1d5b32bd4fe2b6df124a8e1328ebcec8a62e39a08772d8732cb0cb61a498b0a` |
| `crossed_source_members` | `committed_member_bytes` | `GitSourceAuthorityError` | `d1d5b32bd4fe2b6df124a8e1328ebcec8a62e39a08772d8732cb0cb61a498b0a` |
| `uncommitted_worktree_source` | `current_worktree_member_bytes` | `GitSourceAuthorityError` | `83bc6cbe3558eef08b8a7528f9c5ce46f9db90e54b10940714b38551d843d2e7` |

```text
attacks / rejected / accepted       5 / 5 / 0
attack output writes                        0
Provider calls                              0
```

The Audit identity is
`qa_generator_source_authority_negative_audit:f7d626a9ac63f89cbfa13be1a4075461e7b0021d3c863b85046458b37cc0a082`.

## Four Noninterchangeable Depth Metrics

The new Contract defines four separate values:

```text
node_count
  all exact source Program nodes

structural_dependency_depth
  longest output-ancestor DAG path counting every Program node

semantic_operation_depth
  longest output-ancestor DAG path with semantic=1 and
  transparent_projection=0

workflow_interaction_depth
  one evidence-resolution stage + semantic_operation_depth
  + one independent-verification stage
```

The `program_role` values in the exact Registry are the role authority; their Manifest SHA-256 is
`74229358e9c21a1f08a4cc33df9a8cd648de72a4b3600309d197c1b664afaf40`.
An exact source Program and complete output-dependency closure are required. Pure retrieval has
semantic depth zero. Fixed PLAN and ANSWER template steps are not counted. A pure retrieval
trajectory has no explicit semantic calculation, but its independent Program verification is
still required and supplies the verification interaction stage.

The old evaluator field named `program_depth`, which equals node count, and the old
`semantic_only_depth`, which equals structural depth, are explicitly non-authoritative for future
depth sampling. The Contract identity is
`qa_program_depth_metric_contract:3ba7a43cf65f5a37a3dcc648f62ac78489e8b5af16aea0583005e9cd06472865`.

### Exact eight-case measurements

| Task type | Nodes | Structural | Semantic | Workflow | Operator sequence |
| --- | ---: | ---: | ---: | ---: | --- |
| `comparison` | 1 | 1 | 1 | 3 | `compare` |
| `derived_growth_comparison` | 7 | 3 | 2 | 4 | `lookup × 4, growth × 2, compare` |
| `fact_retrieval` | 1 | 1 | 0 | 2 | `lookup` |
| `registered_cross_metric_comparison` | 1 | 1 | 1 | 3 | `registered_compare` |
| `registered_ratio` | 3 | 2 | 1 | 3 | `lookup × 2, ratio` |
| `temporal_absolute_change` | 3 | 2 | 1 | 3 | `lookup × 2, difference` |
| `temporal_average` | 4 | 2 | 1 | 3 | `lookup × 3, aggregate` |
| `temporal_growth` | 3 | 2 | 1 | 3 | `lookup × 2, growth` |

The exact distributions are:

```text
node_count                    {1: 3, 3: 3, 4: 1, 7: 1}
structural_dependency_depth   {1: 3, 2: 4, 3: 1}
semantic_operation_depth      {0: 1, 1: 6, 2: 1}
workflow_interaction_depth    {2: 1, 3: 6, 4: 1}
maximum structural depth                                     3
maximum semantic depth                                       2
semantic depth >= 3 rows                                     0
output dependency closed / workflow source bound         8 / 8
```

These values confirm shallow fixed-Fixture structure; they do not establish deep-question or
realistic-difficulty coverage. The Audit identity is
`qa_program_depth_metric_audit:34eda481363cc892054f483f8f531f0d5ffe955a07f03cefde2ad4bb98d91d66`.

The eight `DepthMetricRow / ProgramDepthMetrics` identities are:

- `comparison`:
  `qa_program_depth_metric_row:9a04acb4695bcb7f80998fe214b6afba430cefe722512a92d842742303d47526` /
  `program_depth_metrics:2716788f8ec1360a2c238ea1a3d3c14452dc082adb939d88cb5f5aaf04621b9a`;
- `derived_growth_comparison`:
  `qa_program_depth_metric_row:139746801a24f854ba14e12ae6cfbcb64fdc85e9b5c201ef0dfbfb6948a7c11d` /
  `program_depth_metrics:108080940cba5723f4c35e516523c0f46b3a0d5d087322eb856d55b2919d91c7`;
- `fact_retrieval`:
  `qa_program_depth_metric_row:b6bdd478c838cb1cd8db0d8be0a5448c52df124db8401f83c6c41d2d3581489d` /
  `program_depth_metrics:f3ac1719f44a20a4556ca10747f623f6a376a3b70184db66e691b129a139da02`;
- `registered_cross_metric_comparison`:
  `qa_program_depth_metric_row:44d24ba6ce8bbb3b3e34755fcf57cc0ed5d6fe3967c8c53df2cdcacdcd9ab4e6` /
  `program_depth_metrics:37bc38f8d0bc5a047e983768c06c6fbb60b402b558fd070c1c7138e59b7c63a6`;
- `registered_ratio`:
  `qa_program_depth_metric_row:13392a681d34bc99818040047bfc03952301719557d96afd6a7d493706c25314` /
  `program_depth_metrics:6d75f53c8ec9e6f50864d9e251d2655ee0681f5282257b6de2a09de633465663`;
- `temporal_absolute_change`:
  `qa_program_depth_metric_row:2cfd9263fb01d5138ff29bbaf5121eab12d37983cd74f3376401cac5be71374a` /
  `program_depth_metrics:3dcb24218707f92956b7bdbc3646808c8793d3dc3acbc2805c2047e81f2d790e`;
- `temporal_average`:
  `qa_program_depth_metric_row:400e66e37d79ce45453efafd04f08eaecac27595f04ca6e4d9cf4ef52acbdb7c` /
  `program_depth_metrics:943f303f215058ad0caa0c8f6b2d630c5f07720daf328af2d44b8a5cfc4ec468`;
- `temporal_growth`:
  `qa_program_depth_metric_row:200283c9fd43d232e9ac98ac9c0174dced0853a7387919e017c6d207a1f6fc09` /
  `program_depth_metrics:742effcc1ccad5172a9b00b25401c618690dad9b72211da726b4c7b5d12d247a`.

## Three Depth-Specific Attacks

All three attacks retain the original final-answer bytes, whose SHA-256 is
`5c456682a3aa97824b2179d642b142b398af6d496d6781a86dc4c304503de4e8`.
They recompute candidate Program identities but cannot replace exact semantic dependency
authority:

| Attack | Rejection stage | Result |
| --- | --- | --- |
| `delete_required_semantic_dependency` | `exact_source_program_admission` | REJECTED |
| `bypass_derived_semantic_chain` | `exact_source_program_admission` | REJECTED |
| `inflate_with_irrelevant_lookup` | `output_dependency_closure` | REJECTED |

The first two reason hashes are
`6013b361bdd5f268b6fe330fd38de138dc128b1ce18b31574716f2fae058426c`; the third is
`900acbf6f97c9a16b7d787ee962a1ab51c76effe1fa1d7b88e62421dd1562381`.

```text
attacks / rejected / accepted        3 / 3 / 0
final answers retained                   3 / 3
attack output writes                         0
Provider calls / GPU Jobs                 0 / 0
```

The Audit identity is
`qa_program_depth_negative_control_audit:6fdd6c29a0435be0ab9acda436925fc948638d73469ed3c606c0a0e627e24b7b`.

## Retained Eight-Type Fixture Execution

The repaired source authority reruns one deterministic canonical Fixture for each registered
Finance task type through the existing generator, exact public Program execution, independent
node replay, answer/schema/citation checks, and `CandidateQualityEvaluator`:

```text
registered task types / generator successes             8 / 8
exact Program executions / operation-correct rows        8 / 8
answer-schema / answer-correct rows                      8 / 8
citation-correct / evaluator-accepted rows               8 / 8
insufficient-capability rows                                  0
```

The retained Audit identity is
`qa_generator_source_authority_retained_fixture_audit:1ad3c4ef3e468bf641af560a68a00554c88bfe1d4469d5cade36276c29118e0c`.
Its eight row identities are:

- `comparison`: `qa_generator_source_authority_retained_fixture_row:1837eed49dd253158a0502ab6db32bdac02222411e9910d480e47bd1890cd4c4`;
- `derived_growth_comparison`: `qa_generator_source_authority_retained_fixture_row:f0a07f1d5a05ca080e36dd24e40785c5cdc19611981df1e0374a6024f381a13e`;
- `fact_retrieval`: `qa_generator_source_authority_retained_fixture_row:00fe27191707a156625d0e39f8a1d4e3db42895ec50f6e400a74f9fdcaae91b4`;
- `registered_cross_metric_comparison`: `qa_generator_source_authority_retained_fixture_row:d704cf0693caa7ade692b875a49505c358fdf8297d82c7d4624a6252d01f5f7a`;
- `registered_ratio`: `qa_generator_source_authority_retained_fixture_row:3d393f2f26ab6d6994f7f404800cd8c172bceb364c1548d5c1e258d991162741`;
- `temporal_absolute_change`: `qa_generator_source_authority_retained_fixture_row:b42480efe4ff1c9acb0bacfc2d382091568286565739811bdbf41006b0a47d09`;
- `temporal_average`: `qa_generator_source_authority_retained_fixture_row:d06f960779f670ad73db626668ede7c29fbd59138e8bfbe6eace81d319e26013`;
- `temporal_growth`: `qa_generator_source_authority_retained_fixture_row:97ef0984dcb7c603a02f0e45dec1abeed0243331a7cc430e015c4b76516be680`.

This remains deterministic Fixture constructibility evidence. One case per type does not prove
parameter-space totality, Archive-grounded constructibility rate, model-generated QA quality, or
future corpus balance.

## Noncompensatory Gates

The exact Gate partition is:

```text
G0 exact external scope                                         PASS
G1 predecessor formal directory frozen                          PASS
G2 exact Git commit/tree/member authority                        PASS
G3 four depth metrics; legacy depth fields non-authoritative     PASS
G4 retained fixed-fixture totality 8/8                           PASS
G5 legacy counterexample and five source attacks reject          PASS
G6 three depth attacks reject                                    PASS
G7 zero Provider/GPU/online/Release boundary                     PASS
passed / failed                                                   8 / 0
```

No Gate compensates for another. A nonexistent commit, incorrect tree, changed or crossed member,
uncommitted implementation byte, aliased depth metric, incomplete output dependency, accepted
depth attack, missing Fixture type, or scope expansion prevents the passing Decision. The Gate
identity is
`qa_generator_source_authority_gate:a424203dbf5ad7f9f1f69c380286ee20162edd47f917f316adfb57d401cea1c5`.

## Authoritative Identities

The principal identities are:

- authorization / predecessor Freeze:
  `qa_generator_source_authority_authorization:0374527bdc9a26e3bc89855b92c0d054840fc6b964f12de012b3817c132d5d4c` /
  `qa_generator_source_authority_predecessor_freeze:454893143af7f57d952dff22e1aae4d4c5905519c17bbe7f0db21049b2df34d1`;
- generator / repair source Bindings:
  `qa_generator_authoritative_source_binding:cd4f225e2e27fa8006828bf4deadd847ad1113d69e9c1c7a0e0d9e3cb3d3e7e9` /
  `qa_generator_authoritative_source_binding:df21b1f4f733f199a741007fb602c36bfa6cb5683eae8c3e1dbd00232f7937ff`;
- legacy / source-negative Audits:
  `qa_generator_legacy_source_counterexample_audit:5b2ad1f7d0083aaa8516bd2d39c759e04081df6173acaefe42c76bad6d311d8f` /
  `qa_generator_source_authority_negative_audit:f7d626a9ac63f89cbfa13be1a4075461e7b0021d3c863b85046458b37cc0a082`;
- depth Contract / measurement / negative Audits:
  `qa_program_depth_metric_contract:3ba7a43cf65f5a37a3dcc648f62ac78489e8b5af16aea0583005e9cd06472865` /
  `qa_program_depth_metric_audit:34eda481363cc892054f483f8f531f0d5ffe955a07f03cefde2ad4bb98d91d66` /
  `qa_program_depth_negative_control_audit:6fdd6c29a0435be0ab9acda436925fc948638d73469ed3c606c0a0e627e24b7b`;
- retained Fixture / scope Audits:
  `qa_generator_source_authority_retained_fixture_audit:1ad3c4ef3e468bf641af560a68a00554c88bfe1d4469d5cade36276c29118e0c` /
  `qa_generator_source_authority_scope_audit:38b69b80cb16f9700eeef71f0a0cb348d3337e7c1d8aef7ca19371a28c546d14`;
- Gate / Report / Transition:
  `qa_generator_source_authority_gate:a424203dbf5ad7f9f1f69c380286ee20162edd47f917f316adfb57d401cea1c5` /
  `qa_generator_source_authority_repair_report:f42aca195e54f4f59c04e47fc4a27984bf75db88338146e87c57e65c9e38a1f8` /
  `qa_generator_source_authority_transition:4ec41dda6eb1379e33f9abbfba5d66df8c422889c683085b711e87396055fe02`;
- Artifact Manifest / Root:
  `qa_generator_source_authority_artifact_manifest:6df4b52442396600fc7112f9af7598cb3d1c8cea08532156614288da7e7bec4b` /
  `qa_generator_source_authority_artifact_root:307fd8ef9563e619f8e8f3815e5b754ccd01bfd872af72bd094e9244cbe85d4b`.

## Reproducibility And Claim Boundary

The formal directory contains 24 files and 463,886 bytes. Its self-excluding Manifest binds 23
members and 460,263 bytes. Two complete empty-directory builds produce exact path and byte
equality. The focused repair tests and retained predecessor tests pass 23/23. Focused PyCompile,
Ruff check/format, and no-import-follow Mypy pass; the complete selected adjacent QA partition
passes 64/64, and package-wide Ruff passes.

The evidence establishes:

- exact Git source authority for the retained 14-member generator/verifier surface;
- exact Git source authority for the five-member repair implementation;
- retained 8/8 deterministic registered-type fixed-Fixture execution and verification;
- distinct, reproducible structural and semantic depth measurements for those Fixtures;
- rejection of the exact legacy source counterexample, five source attacks, and three depth
  attacks.

It does not establish:

- grounding against a real financial Archive;
- realistic ambiguity, language quality, or empirical reasoning difficulty;
- `semantic_operation_depth >= 3` constructibility;
- type or depth frequencies matching FinQA or any other Benchmark;
- model-generated question or answer quality;
- a QA Release Population, training-corpus utility, balance, or safety;
- Provider/GPU readiness, VTDO integration, release, or production readiness.

## Transition And Prohibitions

The only permitted successor is:

```text
qa_generator_source_commit_tree_member_authority_repair_preflight_
independent_audit_only
```

That stage may independently rebuild the exact 24-file directory, resolve both exact Git
commit/tree relations, reread all 14+5 committed members and current bytes, reproduce the legacy
counterexample, independently rederive all four depth metrics for the eight fixed Fixtures, and
repeat all five source and three depth attacks. It must make zero Provider calls and cannot create
a QA Release Population.

Archive grounding, realistic-difficulty calibration, semantic-depth-three-plus expansion,
Benchmark-distribution comparison, online generation, Provider or GPU execution, empirical
estimation, QA Release, VTDO integration, training, release, and production remain unauthorized.
