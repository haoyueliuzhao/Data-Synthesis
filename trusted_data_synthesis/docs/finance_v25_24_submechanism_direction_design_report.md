# Finance v25.24 Submechanism Direction Design

## 1. Purpose

v25.23 confirmed four real Agent mechanisms but rejected their task support as a balanced
seven-axis capability distribution. The corrected residual matrix had numerical rank 3, matching
the maximum contrast dimension of four nearly fixed mechanism centers. v25.24 therefore changes
within-mechanism structure before making any new model call.

This is a Development-stage, model-free experiment. It does not estimate model capability and does
not reuse v25.23 responses to select tasks.

## 2. Typed design contract

The four confirmed parent mechanisms each receive six preregistered candidates:

- Typed Tool Recovery: parameter value, parameter field, missing prerequisite Evidence, tool
  switch, operation-reference repair, and selector-scope repair;
- Candidate Verification: period scope, unit, SourceDefinition, local calculation, insufficient
  Evidence, and entity-scope repair;
- Cross-family Recovery: retrieval, argument, calculation prerequisite, verification rejection,
  Evidence conflict, and empty-result tool fallback;
- State-dependent Stopping: incomplete-continue, complete-stop, post-completion risk,
  post-completion cost, unresolved conflict, and uncertain source coverage.

Every candidate contains:

```text
typed Action Graph
+ typed Evidence dependencies
+ Host intervention contract
+ observable diagnostic outputs
+ mechanically derived capability witnesses
```

The seven-axis demand vector is recomputed from a frozen primitive/relation ontology. Candidate
names, parent labels, expected model outcomes, and prior response rates do not contribute to that
vector. Tampered vectors and non-topological graphs fail closed.

## 3. Direction selection

The selector evaluates all `6^4 = 1,296` ways of retaining five candidates per parent. It first
enforces cross-parent axis support and then deterministically optimizes residual rank, effective
rank, pairwise cosine, condition number, regularized log determinant, and minimum positive
eigenvalue. The general workflow direction is removed by orthogonal projection before computing:

```text
Sigma_struct_perp = mean_i a_i_perp a_i_perp^T
```

No model response is available at this stage.

## 4. Result

The selected 20-task structural design passed all preregistered gates:

| Metric | Result | Requirement |
| --- | ---: | ---: |
| Residual numerical rank | 6 | >= 5 |
| Residual effective rank | 4.698069 | >= 4 |
| Residual condition number | 18.862716 | <= 100 |
| High-cosine pair fraction | 0.094737 | <= 0.35 |
| Minimum parent support per axis | 2 | >= 2 |
| Distinct workflow backbones | 20 | >= 10 |
| Maximum backbone share | 0.05 | <= 0.20 |

The residual eigenvalues are approximately:

```text
0.154465, 0.133201, 0.111242, 0.056691, 0.033177, 0.008189, 0
```

This repairs the structural rank bottleneck found in v25.23. It does not yet show that Flash
responses preserve this geometry.

## 5. Runtime gap and authorization

Only 5 of the 20 selected variants match a currently implemented, real-Finance Host and
Materializer contract. The remaining 15 require new typed interventions or new Evidence
materialization. They are retained as design candidates, not mislabeled as executable tasks.

The frozen state is therefore:

```text
structural_geometry_ready = true
runtime_population_ready = false
api_calls = 0
gpu_jobs = 0
next_permitted_stage = submechanism_runtime_implementation_only
```

Flash, Pro, Beneficiary, Exact Target, GP-C, production Contribution, VTDO updates, and Student
training remain blocked. After all 20 selected variants have distinct executable Host contracts,
the required sequence is:

```text
fresh Finance Development Population
-> Flash valid_success primary matrix
-> preregistered multi-output diagnostics
-> frozen selection
-> disjoint Confirmation
-> same structural and response-weighted geometry gates
```

The tool, verification, recovery, and stopping outputs are preregistered diagnostics. They cannot
rescue a failed primary `valid_success` matrix without a new Development protocol.

## 6. Artifact identities

- Source v25.23 report:
  `finance_capability_mechanism_information_geometry_report:9030c4c16a1cfe2b479f083818ea8c907967f403119c33b4942eef3be0fd9b91`
- v25.24 report:
  `finance_capability_submechanism_direction_report:9c1e3684db51c9dbde1510ee4753d383abfe0044a3ed261cb8d31c1bb3bb58d3`
- Artifact directory:
  `artifacts/vtdo_experiment/finance_v25_24_submechanism_direction_design_v1_20260814/`

Provider telemetry is exactly zero because this stage deliberately stops before API execution.


## 7. Engineering validation

- Ruff: passed;
- Mypy: 294 source files passed;
- Pytest: 603 passed;
- Generalization Contract v1.2: 131 Core/runtime/architecture files scanned, zero domain
  imports, branches, field accesses, dynamic imports, or dispatch violations;
- focused structural-design tests: vector tamper rejection, graph-topology rejection,
  deterministic selection, immutable report, and fail-closed API transition all passed;
- `git diff --check`: passed.
