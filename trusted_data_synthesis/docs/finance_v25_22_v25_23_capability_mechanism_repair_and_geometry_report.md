# Finance v25.22-v25.23 Capability Mechanism Repair And Geometry

## 1. Scope

This report records the task-only repair requested by the v25.21 audit, its fresh held-out
Confirmation, and the first mechanism-specific Information Geometry audit. The experiment remains
Finance-only and Flash-only.

The following remained forbidden throughout:

- DeepSeek Pro calls;
- GPU jobs;
- Beneficiary screening;
- Exact Target;
- GP-C;
- Authorization Objective access;
- production Contribution and VTDO updates.

Provider cost fields are telemetry estimates. They are not billing records.

## 2. Mechanism Repair

Two v25.21 mechanisms were already replicated and were not rerun:

- `finance.typed_tool_plan_and_argument_recovery`;
- `finance.cross_family_failure_recovery`.

The repaired mechanisms were:

- `finance.candidate_verification_and_repair`;
- `finance.state_dependent_control_and_stopping`.

### Candidate verification

The mechanism-required task now exposes an untrusted candidate while keeping the canonical
candidate, repair target, and preserved fields in the Oracle contract. The Agent must:

1. independently replay the calculation;
2. compare the candidate with selected Evidence;
3. identify exactly one local semantic error;
4. repair only that field;
5. preserve every unaffected field;
6. emit the answer after verified repair.

The current real-Finance pool could support a fresh semantic `period_scope` near miss for every
selected group. It did not support equally fresh source-definition, unit, or currency near misses.
The result therefore validates the localized semantic-repair mechanism for period scope; it must
not be generalized to every financial error family.

### State-dependent stopping

The task now has externally observable incomplete and complete states. A strict nonempty subset of
required roles must be verified before remaining-role actions are allowed. After verified
completion, every additional tool call is rejected as a redundant action. Behavior success
requires:

- an observed incomplete state;
- an observed complete state;
- no action after verified completion;
- a terminal answer that depends on the stop decision.

### Isolation and identity

The exact mechanism scenario, canonical candidate, repair target, preserved fields, and required
completion roles live only in the Oracle selection contract. Public task metadata contains only
generic mechanism requirements.

Confirmation Population v4 additionally freezes the Development Selection Freeze path, SHA-256,
and object ID. Contract preparation and runtime replay independently compare:

```text
Population
<-> Selection Freeze
<-> Runtime Contract
```

A mismatch fails before model-client construction.

## 3. Development History

Early immutable attempts are retained as diagnostics, not reclassified evidence.

- The first run exposed a stage-schema mismatch and missing typed Finance tool-result fields. It is
  invalid as a Runtime result.
- The corrected numeric candidate run passed candidate verification but failed stopping because
  the Agent could skip the incomplete-state observation.
- The state-transition run passed stopping but exposed candidate saturation and a public target
  disclosure.
- The final design moved exact scenario data to Oracle and replaced numeric corruption with a
  semantic period-scope error.

Final Development artifacts:

- Population:
  `finance_capability_mechanism_repair_population:a3d73e5ca58578dd41b561d0ff6f2370b97920f6d7dcb43d44b2508d80f0e48c`
- Contract:
  `finance_capability_mechanism_repair_contract:fb5a6fbaa31b8c5bcc25d5681bfcd25be33a00d4838b6ebaea520a6d63ce377c`
- Report:
  `finance_capability_mechanism_repair_report:62bf3924ac16631e777649afe8e6999ad3b868ea14c51f521acde7c5f5468c7a`

Development completed 96/96 rollouts:

| Metric | Result |
| --- | ---: |
| Runtime eligibility | 96/96 |
| API / JSON / replay / authority | 100% |
| Runtime pathology | 0% |
| Semantic accuracy | 89.58% |
| End-to-end valid success | 75.00% |
| API calls | 777 |
| Model tokens | 4,225,352 |
| Estimated telemetry cost | USD 0.4903 |

Both repaired mechanisms met the frozen Development selection rules. The resulting Selection
Freeze is:

`finance_capability_mechanism_repair_freeze:d8b89d2c6a565f116ee62273bb993813bf3e36a7e27861eb370b124307a28dba`

## 4. Fresh Held-out Confirmation

The v4 Confirmation Population excludes v25.21 Development and Confirmation plus every v25.22
Development population. It is disjoint on task, group, Evidence ID, Evidence Version ID, and core
semantic signature.

Artifacts:

- Population:
  `finance_capability_mechanism_repair_population:2975d010c2c49cf573f44864ea6767854a7b90ab9e7183c8485fb12dbe43ded5`
- Contract:
  `finance_capability_mechanism_repair_contract:5c96e45f8796cff676ecb10184f00d41f4b7bc17fffe0df8483eb717f82cad4d`
- Report:
  `finance_capability_mechanism_repair_report:2ac4f2a1ccf8e99245db3c057dd2fc632217f343b8869477dd10fbf5a5841343`

The frozen denominator is 10 matched groups, 20 tasks, five replicas per task, and 100 rollouts.

| Metric | Result |
| --- | ---: |
| Recorded rollouts | 100/100 |
| Runtime eligible | 100/100 |
| API / JSON / replay / authority | 100% |
| Runtime pathology | 0% |
| Semantic accuracy | 79.00% |
| End-to-end valid success | 66.00% |
| API calls | 886 |
| Model tokens | 5,034,657 |
| Estimated telemetry cost | USD 0.5232 |
| Contract repairs | 8 |
| Budget exhaustion | 0 |
| Runtime infrastructure failures | 0 |

Independent mechanism decisions:

| Mechanism | Boundary groups | Matched differences | Behavior success | Decision |
| --- | ---: | ---: | ---: | --- |
| Candidate verification and repair | 1 | 3 | 25/25 | confirmed |
| State-dependent control and stopping | 3 | 4 | 19/25 | confirmed |

All 25 candidate-mechanism trajectories were behavior-evaluable and successful. Nineteen stopping
trajectories were behavior-evaluable and all nineteen passed every stopping check. Six stopping
trajectories produced no evaluable mechanism trace and remain model failures in the denominator.

The four-mechanism combined state is therefore:

```text
all_information_geometry_mechanisms_confirmed = true
information_geometry_authorized = true
```

This authorizes only the Information Geometry computation. It does not imply that the resulting
geometry is well conditioned.

## 5. v25.23 Mechanism Information Geometry

The legacy Flash Information Matrix was not reused because it represents seven task families and
two Workflow Runtimes. v25.23 defines a new immutable source contract over the four confirmed
mechanisms.

Primary geometry policy:

- source data: the two independent held-out Confirmation runs;
- response: `valid_success`;
- population: `mechanism_required` variants only;
- matched controls: confirmation evidence only, excluded from the matrix;
- demand: frozen seven-axis task demand, L2 normalized;
- matrix:
  `mean_x p_hat(x)(1-p_hat(x))a(x)a(x)^T`;
- general-difficulty residual: Fisher-weighted centering and weighted least squares under the
  same `p_hat(x)(1-p_hat(x))` measure;
- Bootstrap: 400 mechanism-stratified task-and-realization replicates;
- implementation identity: complete numerical and typed-source manifest;
- source identity: recursive path/hash replay through Population, Selection Freeze, Runtime
  Contract, Archive config, and exclusion populations;
- thresholds: unchanged Autonomous thresholds.

Artifacts:

The initial v1 replay used unweighted centering and regression for the residual matrix while the
information matrix itself used Fisher weights. That mismatch could let zero-information tasks alter
the robustness diagnostic. v1 is retained as a diagnostic artifact but is superseded by the
fully frozen, Fisher-weighted v2 replay below.

- Contract:
  `finance_capability_mechanism_information_geometry_contract:9fedbbaf5a13a6c6242ac3c87279db11818ddce71615e205ca042a7b87172a1e`
- Report:
  `finance_capability_mechanism_information_geometry_report:9030c4c16a1cfe2b479f083818ea8c907967f403119c33b4942eef3be0fd9b91`

The two sources contain 300 total rollouts. The geometry uses 20 mechanism-required tasks and 100
rollouts, exactly five groups and five replicas per mechanism.

### Passed gates

- complete task and rollout denominators;
- balanced mechanism group coverage;
- eight distinct normalized demand vectors;
- 45% boundary-task fraction;
- raw numerical rank 5;
- all seven marginal axes have positive Bootstrap lower bounds above the frozen threshold;
- maximum mechanism information share 33.33%;
- general-difficulty factor fraction 53.81%;
- residual condition number 5.26.

### Failed gates

| Gate | Observed | Frozen requirement |
| --- | ---: | ---: |
| Raw effective rank | 1.20598 | >= 3.0 |
| Raw condition number | 1270.31 | <= 100 |
| Residual numerical rank | 3 | >= 4 |
| Residual effective rank | 2.40054 | >= 3.0 |

The raw eigenvalues are approximately:

```text
0.08089167
0.00228528
0.00058063
0.00017874
0.00006368
0
0
```

The result is not a lack of mechanism observations. The raw geometry is dominated by one common
direction. After a measure-consistent general-difficulty adjustment, conditioning improves, but
only three independent residual directions remain and their effective rank stays below three.
Thus the corrected diagnosis is missing independent mechanism support, not merely residual
numerical ill-conditioning. This is exactly the distinction between label/mechanism balance and
capability-space balance.

The fail-closed transition is:

```text
information_geometry_ready = false
pro_sparse_anchor_authorized = false
next_permitted_stage = capability_mechanism_support_redesign_only
```

## 6. Scientific Interpretation

v25.22 confirms that the repaired tasks can induce verifiable Agent behaviors. v25.23 shows that
four confirmed behaviors are still insufficient to form a well-conditioned seven-axis capability
distribution.

The result does not invalidate the four mechanisms. It rejects the stronger claim that the current
task support is ready for Pro anchoring or Beneficiary screening.

The next population must change capability directions, not merely add more entities, periods, or
replicas. In particular:

1. preserve the four confirmed mechanism contracts;
2. create more orthogonal action-graph and Evidence-dependency combinations within them;
3. move saturated verification cells away from `p=1`;
4. increase independent Planning, Verification, Recovery, and Stopping contrasts without making
   all tasks share the same retrieval/calculation backbone;
5. freeze a new Development selection and use a fully disjoint Confirmation;
6. rerun geometry with the same thresholds.

Subsetting the current responses, changing thresholds, calling Pro, or opening Beneficiary,
Exact Target, GP-C, or Contribution is forbidden.

## 7. Artifact Paths

- `artifacts/vtdo_experiment/finance_v25_22_mechanism_repair_confirmation_population_v2_20260814/`
- `artifacts/vtdo_experiment/finance_v25_22_mechanism_repair_confirmation_contract_v1_20260814/`
- `artifacts/vtdo_experiment/finance_v25_22_mechanism_repair_confirmation_run_v1_20260814/`
- `artifacts/vtdo_experiment/finance_v25_23_mechanism_information_geometry_contract_v2_20260814/`
- `artifacts/vtdo_experiment/finance_v25_23_mechanism_information_geometry_run_v2_20260814/`

## 8. Engineering Validation

- Ruff: all checks passed;
- Mypy: 291 source files passed;
- Pytest: 599 tests passed;
- Generalization Contract v1.2: 131 files scanned, with zero Core domain imports, branches,
  field accesses, dynamic imports, or dispatch violations;
- immutable v2 contract/report reload: passed;
- `git diff --check`: passed.

No API or GPU was used for the v25.23 v2 correction and replay.
