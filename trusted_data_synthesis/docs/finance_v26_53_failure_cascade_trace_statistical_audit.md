# Finance v26.53 Failure Cascade and Trace Statistical Audit

Audit date: 2026-08-18

## Decision

This is a read-only, non-authorizing statistical audit of the immutable Finance v26.43 Bridge
Development run.

The result is:

> The 576 model trajectories exhibit substantial downstream trace variation, but the variation is
> overwhelmingly carried by invalid trajectories. The dominant blocker is end-to-end semantic,
> operational, verification, and answer closure. The 23 valid trajectories are too sparse,
> task-concentrated, and mechanism-concentrated to support a positive claim about reachable valid
> state diversity.

The authoritative transition remains:

```text
capability_task_or_scaffold_redesign_only
```

This audit did not rescore v26.43, relax a threshold, call a model API, use a GPU, select a Scaffold
level, open Confirmation, discover states, evaluate Exact Target or GP-C, or authorize
Contribution.

## Identity And Inputs

The final artifact is:

```text
artifacts/vtdo_experiment/
  finance_v26_53_failure_cascade_trace_audit_20260818/
```

Its identity is:

```text
finance_v26_bridge_statistical_audit:
c7851d1487fbab1c5d4814451ea3f46aa52f54e68f01bc841cd66acfcd43c64b
```

The audit binds the exact bytes of seven immutable inputs:

| Input | SHA-256 prefix |
| --- | --- |
| v26.43 Bridge report | `7a4e563b6e00` |
| v26.43 Bridge rollouts | `83e781a94ecd` |
| v26.43 Bridge Cells | `8795bc3ac9da` |
| v26.43 Support Freeze | `bdda6de18d68` |
| v26.42 compiled proof artifacts | `43f634ec9c01` |
| v26.42 Development Population | `effac9dd8401` |
| grounded source Population | `db6773b5afa8` |

The output contains:

| Artifact | Rows | SHA-256 prefix |
| --- | ---: | --- |
| `rollout_diagnostics.json` | 576 | `a8449e7d32f6` |
| `trace_cell_summaries.json` | 96 | `770b3e22f8c` |
| `scaffold_task_influences.json` | 24 | `8baf2e6f0fc2` |
| `report.json` | 1 | content-addressed by the audit ID |

The earlier v26.50 through v26.52 outputs were implementation-development diagnostics and are not
authoritative scientific artifacts. Review found two audit-layer defects before commit: the first
Answer Projection classifier inferred equivalence from string shape, and the first JSD
implementation accumulated over an unordered set. v26.53 uses the compiled Answer Projection map,
deterministic sorted `math.fsum` accumulation, and an explicit Quotient State denominator. An
independent v26.53 rebuild reproduced all three detail artifacts byte for byte.

The immutable v26.43 Support Freeze uses the historical v4 Freeze and v1 inference identities.
Current production code has moved to v5/v2. The audit therefore uses a sealed, audit-only v4
projection that independently checks the historical content hash, exact 12 Cell identities,
three blocked mechanism selections, and the unchanged transition. It does not weaken the current
production Schema or add a legacy execution path.

## Audit Method

### Ordered failure cascade

For each rollout, the audit maps independent verifier failures to the earliest registered contract
stage:

```text
model contract
-> public-state interpretation
-> tool selection
-> argument construction
-> recovery
-> evidence selection
-> operation execution
-> verification
-> citation
-> answer projection
```

This is an ordered diagnostic contract, not a causal root-cause estimator. A rollout assigned to
`operation_execution` may also fail verification, citation, and answer checks.

### Model-owned trace canonicalization

The canonicalizer removes Host-controlled execution, Scaffold text, entity names, metric names,
periods, values, raw rationale, automatic verification, and terminal wrappers. It retains only
model-owned behavior:

- action and tool type;
- status and semantic operator;
- argument-key shape;
- Gold, extra, and total Evidence counts;
- input-reference counts;
- Evidence selection, operation, recovery, verification, and stopping order.

This prevents entity, year, or numeric substitutions from being counted as decision diversity.

### Statistical unit

The complete design has 96 Cells:

```text
3 mechanisms x 4 Scaffold levels x 8 tasks
```

Every Cell contains six rollouts. Each Cell reports separate `all`, `valid`, and `invalid`
slices. Scaffold comparisons pair each task's `gamma_0` Cell against `gamma_1` through
`gamma_3`. Mechanism summaries use the task as the primary sampling unit and 5,000 frozen
percentile-bootstrap replicates. Rollouts are not treated as independent task replicas.

## Denominator Closure

All registered denominators close exactly:

| Quantity | Count |
| --- | ---: |
| Requested and audited rollouts | 576 |
| Independently valid | 23 |
| Model-invalid | 553 |
| Independent verifier reports | 568 |
| Model-contract failures before verifier report | 8 |
| Mechanism/Scaffold/task Cells | 96 |
| Task-level Scaffold influence records | 24 |

The valid rate is 3.9931%; the invalid rate is 96.0069%. The source and output hashes replay
without credentials.

## Failure Cascade

The 553 invalid trajectories are completely assigned:

| Earliest failed stage | Count | Share of 553 |
| --- | ---: | ---: |
| Operation execution | 288 | 52.08% |
| Answer projection | 198 | 35.80% |
| Evidence selection | 32 | 5.79% |
| Verification | 24 | 4.34% |
| Model contract | 8 | 1.45% |
| Argument construction | 2 | 0.36% |
| Citation | 1 | 0.18% |
| Public-state interpretation | 0 | 0.00% |
| Tool selection | 0 | 0.00% |
| Recovery as earliest gate | 0 | 0.00% |

The mechanism breakdown sharpens the diagnosis:

| Mechanism | Invalid | Operation | Answer | Evidence | Verification | Other |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Context-conditioned action | 192 | 66 | 82 | 26 | 12 | 6 |
| Semantic reconciliation | 171 | 117 | 43 | 2 | 4 | 5 |
| Recovery and stopping | 190 | 105 | 73 | 4 | 8 | 0 |

Semantic reconciliation and recovery/stopping predominantly fail before final answer projection,
at operation execution. Context-conditioned action has a larger evidence-selection and
answer-projection burden, but it still produces no valid trajectory.

### Overlapping verifier checks

Eight model-contract failures have no independent semantic report. Among the remaining 545
independently verified failures:

| Failed check | Count | Share of 545 |
| --- | ---: | ---: |
| Answer correct | 521 | 95.60% |
| Operation lineage covers Gold | 321 | 58.90% |
| Verification support covers Gold | 297 | 54.50% |
| Citation exactly Gold | 183 | 33.58% |
| Selected Evidence covers Gold | 32 | 5.87% |
| Citations were selected | 11 | 2.02% |
| Deterministic tool replay | 2 | 0.37% |
| Stop after successful verification | 1 | 0.18% |

There are 15 distinct failure patterns. Their entropy is 2.5825 bits and the largest pattern
occupies 36.33%. The leading patterns are:

| Failed-check set | Count |
| --- | ---: |
| Answer only | 198 |
| Citation + operation + verification + answer | 133 |
| Operation + verification + answer | 85 |
| Operation + answer | 45 |
| Evidence + citation + operation + verification + answer | 21 |
| Citation + operation + verification, answer correct | 19 |

This confirms that the answer failure count is not a simple final-format denominator. Most
failures contain an upstream operation or verification defect, while a separate 198-rollout slice
passes every earlier registered gate and fails only answer equality.

## Answer Projection Audit

The 198 answer-only failures split as follows:

| Mismatch class | Count | Share |
| --- | ---: | ---: |
| Mixed numeric/value and reference mismatch | 137 | 69.19% |
| Reference representation only | 25 | 12.63% |
| Numeric or scalar only | 26 | 13.13% |
| Reference identity or projected-label error | 10 | 5.05% |
| Structural or other | 0 | 0.00% |

The affected mechanisms are Context 82, Recovery/Stopping 73, and Reconciliation 43.

This slice contains two different engineering problems:

1. The 137 mixed and 26 numeric/scalar failures are not explainable as output formatting alone.
2. The 25 representation-only cases exactly match the human-facing value frozen in the
   compiled `selection_contract.answer_projection` map while the Oracle normalized answer carries
   an Evidence reference. They are confirmed Answer Projection contract mismatches, not inferred
   from string shape alone.

The ten reference-identity or projected-label failures are not representation-only: four select a
different Evidence reference and six emit a human-facing entity or date that differs from the
compiled projection.

No v26.43 answer was rescored. Future work should compile one typed Answer Projection family into
the public output contract, Oracle matcher, and verifier rather than accepting variants post hoc.

## Citation And Evidence Support

The observed Evidence-set relations are:

| Relation to Gold | Selected Evidence | Cited Evidence |
| --- | ---: | ---: |
| Exact Gold | 536 | 385 |
| Strict subset | 32 | 183 |
| Strict superset | 0 | 0 |
| Partial overlap | 0 | 0 |
| Disjoint | 0 | 0 |
| Unavailable due to model contract | 8 | 8 |

Of the 183 citation-equality failures:

- 162 had already selected all Gold Evidence;
- 19 had a correct answer;
- zero cited a strict superset;
- zero failed only `citation_exact_gold`;
- zero failed only the citation-check family.

Therefore, this run does not support the claim that exact Gold equality rejected extra or
alternative sufficient Evidence. Every observed citation-equality failure was a missing-Gold
citation case, not a strict-superset case. At the same time, semantic equivalence of non-Gold
Evidence was not evaluated, so the run also cannot establish that one Gold set is the only legal
support. An Evidence Support Lattice remains a prospective design requirement, not a basis for
retrospective rescoring.

## Trace Diversity

### All and invalid trajectories

Across all 96 six-rollout Cells:

| Statistic | Result |
| --- | ---: |
| Unique traces per Cell, minimum / mean / maximum | 3 / 5.323 / 6 |
| Effective trace count, minimum / mean / maximum | 2.381 / 5.188 / 6 |
| Mean maximum trace share | 0.2656 |
| Mean pairwise normalized edit distance | 0.3595 |
| Mean unique action sequences | 3.188 |

The 553 invalid trajectories occupy 95 nonempty invalid Cells:

| Statistic | Result |
| --- | ---: |
| Mean unique traces per nonempty Cell | 5.232 |
| Mean effective trace count | 5.120 |
| Mean maximum trace share | 0.2600 |
| Mean pairwise normalized edit distance | 0.3634 |
| Mean unique action sequences | 3.168 |

At mechanism level, the 192-rollout populations contain 126, 119, and 127 normalized trace
templates for Context, Reconciliation, and Recovery/Stopping respectively. They contain 59, 29,
and 33 normalized action sequences.

These results reject a global same-template-collapse explanation. The model does produce many
different downstream invalid paths.

### Valid trajectories

The positive slice is qualitatively different:

| Statistic | Result |
| --- | ---: |
| Valid trajectories | 23 |
| Tasks with any valid trajectory | 3 / 24 |
| Cells with any valid trajectory | 9 / 96 |
| Global normalized trace templates | 13 |
| Global action sequences | 5 |
| Valid Quotient State observations | 23 / 23 |
| Invalid Quotient State observations | 0 / 553 |
| Unique Quotient states | 21 |
| Quotient State entropy | 4.3496 bits |
| Effective Quotient State count | 20.3880 |
| Maximum Quotient State share | 8.70% |
| Trace entropy | 3.3275 bits |
| Effective trace count | 10.0386 |
| Maximum mechanism share | 91.30% |

The State Mapper runs only after full validity: all 23 valid rollouts have a Quotient State and no
invalid rollout does. Therefore `H(Z | invalid)` is undefined rather than zero. Within the valid
slice, state entropy is 4.3496 bits and effective state count is 20.3880, but those values remain
conditioned on only three tasks and one mechanism contributing 91.30% of observations.

Within the nine nonempty valid Cells, the mean unique trace count is 2.111, mean effective trace
count is 2.072, mean maximum trace share is 0.648, mean pairwise edit distance is 0.168, and mean
unique action count is 1.222.

The valid observations are concentrated in three tasks:

| Mechanism | Task ID prefix | Valid | Scaffold distribution |
| --- | --- | ---: | --- |
| Semantic reconciliation | `task:d5b98105...` | 14 | 3 / 6 / 3 / 2 |
| Semantic reconciliation | `task:84c37aca...` | 7 | 2 / 2 / 1 / 2 |
| Recovery and stopping | `task:2e340e1c...` | 2 | 2 / 0 / 0 / 0 |

A global entropy value over 23 observations cannot overcome this task and mechanism
concentration. The valid slice is insufficient for estimating a useful
`pi(z | x, gamma)` or for claiming heterogeneous positive state support.

## Scaffold Behavior Impact

The task-first paired JSD and change estimates compare `gamma_1` through `gamma_3` with each task's
`gamma_0` baseline. Brackets are task-bootstrap 95% intervals. The Valid-rate column is
the descriptive four-level mean rather than a causal Scaffold-effect estimate:

| Mechanism | Trace JSD | Action JSD | Trace change | Action change | First-tool change | Valid rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Context | 0.8069 [0.6506, 0.9306] | 0.4677 [0.2636, 0.6677] | 0.9306 [0.8889, 0.9655] | 0.6875 [0.4306, 0.8958] | 0.0347 [0, 0.1042] | 0 [0, 0] |
| Reconciliation | 0.8572 [0.7497, 0.9435] | 0.2705 [0.1709, 0.3812] | 0.9653 [0.9097, 1] | 0.5139 [0.3750, 0.6458] | 0.0139 [0, 0.0347] | 0.1094 [0, 0.2552] |
| Recovery/stopping | 0.8220 [0.7089, 0.9313] | 0.3580 [0.2701, 0.4530] | 0.9375 [0.8889, 0.9861] | 0.6111 [0.5417, 0.6806] | 0.0278 [0, 0.0694] | 0.0104 [0, 0.0313] |

All eight tasks in every mechanism change their modal normalized trace at some Scaffold level.
Modal action changes occur in 6/8 Context tasks, 2/8 Reconciliation tasks, and 4/8
Recovery/Stopping tasks. By contrast, the first model tool is almost invariant: `search_archive`
is first in 567/576 trajectories, and the paired first-tool-change estimates remain near zero.

The Scaffold therefore changes downstream invalid execution details and sometimes the action
sequence, but it does not change the initial acquisition policy and does not create stable valid
support. High trace JSD is not evidence of useful capability bridging when validity remains zero
or near zero.

## Local Mechanism Behavior Versus Closure

The immutable v26.43 estimands and the new closure audit agree on the central disconnect:

| Mechanism | Local behavior by gamma_0..gamma_3 | Full valid by level |
| --- | --- | --- |
| Context alignment | 46, 48, 48, 47 of 48 | 0, 0, 0, 0 |
| Context branch flip | 0, 0, 0, 0 of 48 | 0, 0, 0, 0 |
| Semantic reconciliation estimand | 0, 0, 0, 0 of 48 | 5, 8, 4, 4 |
| Failure recovery | 2, 9, 9, 8 of 48 | 2, 0, 0, 0 |
| Stopping calibration | 0, 0, 0, 0 of 48 | 2, 0, 0, 0 combined-mechanism valid |

The 21 valid Reconciliation trajectories do not demonstrate the registered Reconciliation
mechanism, because its estimand is zero in all 192 attempts. Recovery responds locally to higher
Scaffolds, yet full validity disappears and Stopping remains absent. Context alignment is
saturated while the mechanism-defining branch flip remains absent.

## Static Multi-path Support

All 24 tasks have exactly one registered Reference Workflow example. Their source Programs have:

| Operation branches | Tasks |
| ---: | ---: |
| 1 | 6 |
| 2 | 14 |
| 3 | 4 |

The current artifacts contain zero dedicated:

- `PublicExecutableWitnessArtifact`;
- `MechanismNecessityArtifact`;
- `AlternativeValidPathCatalog`.

One registered reference example does not prove that only one semantically valid path exists.
Conversely, operation-branch count does not prove that multiple model-owned end-to-end paths are
publicly executable. The current data therefore cannot identify whether the task support has
latent alternative valid paths.

## Supported Conclusions

The audit supports all of the following:

1. Runtime, transport, recursive noninterference, and raw artifact integrity are not the v26.43
   blocker.
2. The dominant complete-trajectory break occurs at operation execution and answer projection,
   followed by evidence selection and verification.
3. The 198 answer-only failures include a real Answer Projection contract issue, but 173/198 have
   a numeric/scalar mismatch, a wrong Evidence reference, or a wrong projected label and are not
   representation-only.
4. Exact Gold citation equality is not an isolated observed blocker and did not reject any strict
   Evidence superset in this run.
5. Invalid model trajectories are behaviorally diverse; global trace collapse is not the main
   explanation.
6. The valid support is too sparse and concentrated for a positive diversity or state-support
   conclusion.
7. Scaffold levels alter downstream traces much more than first-tool choice or complete validity.
8. Local mechanism metrics remain decoupled from end-to-end valid closure.

The audit does not establish:

- that Flash lacks the underlying financial capability;
- that only one semantically valid solution path exists;
- that Evidence-set equality is generally the correct or incorrect validity rule;
- that the 23 valid trajectories form a useful training distribution;
- that Joint Compilation, GP-C, Contribution, or VTDO is invalid.

## Required Redesign Before Another API Run

The next experiment should be compiled only after these pre-API conditions exist:

1. **Public executable witness**: every task has a hidden static proof that one complete trajectory
   is executable using only the Public Projection and allowed tools.
2. **Typed Answer Projection**: public answer instructions, Oracle Schema, human rendering, and
   verifier reference semantics are compiled from one registered contract.
3. **Mechanism necessity**: removing, replacing, or bypassing the target mechanism action must fail
   end-to-end validity.
4. **Mechanism separation**: Recovery and Stopping are developed independently before a new joint
   mechanism test.
5. **Causal reconciliation**: downstream operations consume only the normalized reconciliation
   reference, so the mechanism cannot be bypassed.
6. **Counterfactual Context action**: Context A and Context B require different actions and wrong
   actions cannot be repaired into a valid answer.
7. **Alternative valid path catalog**: tasks intended for VTDO multi-state optimization statically
   register and verify more than one model-owned public path.
8. **Evidence support semantics**: necessary coverage, sufficiency, invalid Evidence exclusion, and
   task-specific exact equality are represented separately.

No additional same-design rollouts should be launched before these conditions are audited.

## Validation

The final audit completed with:

- zero API calls;
- zero GPU jobs;
- 576/576 diagnostic rows;
- 96/96 trace Cells;
- 24/24 task-level Scaffold comparisons;
- task-first 5,000-replicate intervals;
- exact source and output hash replay;
- status `observed_non_authorizing`;
- transition `capability_task_or_scaffold_redesign_only`;
- focused statistical-audit tests: 9 passed;
- repository Ruff: passed;
- repository Mypy: 344 source files passed;
- complete Pytest: 855 passed in 353.97 seconds.

The implementation is in
`src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_bridge_statistical_audit.py`.
