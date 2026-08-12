# Finance v25 Capability Boundary Revision

Audit and revision date: 2026-08-12

## Status

Finance v25 has passed the structural identifiability prerequisite, but it has not yet passed the
model-response identifiability prerequisite. The current scientific state is:

```text
70-task structural population:                 passed
Capability Necessity Audit:                    35/35 passed
Runtime-specific model-visible demand:         frozen
v25.0 Runtime Qualification:                   failed, preserved
v25.1 Runtime Qualification:                   failed, preserved
v25.6 Runtime Qualification contract:          ready, not executed
Pro-Flash paired calibration:                  forbidden until Qualification passes
Beneficiary frontier screening:                forbidden until empirical audit passes
Exact Target / GP-C / VTDO update:             forbidden
Production Contribution:                       0
```

The distinction is deliberate:

```text
structural covariance != empirical capability information
```

The structural population establishes that the task support can, in principle, probe multiple
capability directions. Only repeated model responses can establish whether those directions lie
near a model boundary.

## Structural Contract

The frozen population contains 70 executable Finance tasks across Retrieval, Planning,
Calculation, Reconciliation, Verification, Recovery, and Stopping. Each family contains three
Easy, five Frontier, and two Hard-Control tasks. The population has:

- strictly monotonic Easy--Frontier--Hard structural demands;
- 7/7 family-primary-axis matches;
- leading-six contrast effective rank `5.141`;
- leading-six contrast condition number `4.726`;
- 70/70 executable and independently replayable Programs;
- cross-sample public Evidence disjointness.

The seventh direction remains weaker. Full-space rank is seven, but the smallest eigenvalue is
`0.000164` and the full condition number is `106.603`. Reports must therefore expose uncertainty
for all seven axes and may not claim seven independently precise capability estimates merely from
the structural spectrum.

## Capability Necessity

`CapabilityNecessityAudit` performs destructive contract probes rather than checking for the
presence of decorative nodes. It removes or blocks the operation, Observation, recovery branch,
verification condition, or stopping condition associated with the preregistered primary demand.
All 35 probes fail the answer, Proof Graph, execution, or Quality Contract as required.

The audit scope is intentionally named:

```text
frontier_contract_necessity_not_model_causal_effect
```

It proves that the capability-bearing structure is necessary under the task contract. It does not
claim a causal effect on a particular model.

## Runtime-Specific Demand

Each task is compiled into three independent Runtime bindings. Host-controlled capabilities are
removed before constructing the empirical information matrix:

| Runtime | Model-visible capability axes |
| --- | --- |
| Direct Fixed Retrieval | Calculation, Reconciliation, Verification |
| Scripted Tool | Retrieval, Calculation, Reconciliation, Verification, Recovery |
| Autonomous Agent | all seven axes |

Direct Runtime freezes resolved retrieval and the public operation plan. Scripted Runtime freezes
the tool order but not tool arguments or recovery from rejected arguments. Autonomous Runtime
leaves planning, retrieval, calculation, verification, recovery, and stopping model-visible.

## Qualification Semantics

The seven-task Qualification contains one Frontier task per family and runs:

```text
7 tasks x 2 models x 3 runtimes x 3 replicas = 126 rollouts
```

It is a protocol qualification, not an answer-accuracy gate. A model error can be a completed
trial only if it produces a bounded, strongly typed, independently replayable failure artifact.
Semantic correctness, valid success, and answer accuracy remain descriptive.

The technical gates are:

- exact requested model and no fallback;
- bounded JSON resolution after at most two repair attempts;
- raw JSON response rate at least 85%;
- 100% bounded tool resolution, excluding no model mistakes;
- 100% terminal result emission;
- 100% Observation or typed-failure replay;
- 100% Host authority integrity;
- no resource-budget exhaustion;
- Host-forced verification repair at most 15% in Autonomous Runtime.

`tool_bounded_resolution` means the frozen Runtime returned a schema-valid Observation or typed
rejection. A no-match, invalid model argument, or failed semantic query is a model outcome, not an
infrastructure failure. Only `runtime_exception:*`, invalid Observation Schema, or failed replay
violates this technical gate.

## Preserved Diagnostic Runs

### v25.0

- Contract: `finance_capability_boundary_contract:62f2d8bc...`
- Qualification report: `capability_qualification_report:e4209def...`
- Records: 51 completed, 75 failed
- Decision: `protocol_repair_only`

Failures included 33 Host action-contract failures, 29 identical failed-tool repetitions, seven
failed-tool budget exhaustions, five iterative-contract failures, and one missing provider token
usage record.

### v25.1

- Contract: `finance_capability_boundary_contract:35adf7f4...`
- Qualification report: `capability_qualification_report:92394ff7...`
- Records: 65 completed, 61 failed
- Decision: `protocol_repair_only`

Failures included 28 Host action-contract failures, 26 identical failed-tool repetitions, six
iterative-contract failures, and one failed-tool budget exhaustion. v25.1 must not be reclassified
after the fact. It remains evidence that the earlier Runner discarded typed Direct semantic
failures and used an incorrect Scripted authority comparison when failed argument attempts caused
same-tool retries.

## v25.3 Superseded Preflight

v25.3 froze an unexecuted contract after the first protocol repair. It made no API call and remains
a superseded preflight Artifact. A second code audit found that Scripted argument recovery was
still marked Host-controlled and that the reported raw empirical information matrix used centered
demands rather than the preregistered `E[p(1-p)aa^T]` formula. It must not be executed.

## v25.4 Superseded Behavioral Preflight

v25.4 corrected Runtime responsibility and the empirical-information formula, then completed only
offline contract preflight. It made no API call. A final audit found that its diagnostic
`recovery_success` was equivalent to final validity rather than conditional recovery from a
recorded failure, and that Query Reformulation and Tool-sequence Diversity were absent from the
typed outcome. v25.4 is therefore preserved but must not be executed.

## v25.5 Superseded Authorization Preflight

v25.5 completed no API call and no GPU work. A final pre-execution audit found that Calibration
trusted a self-consistent passing Qualification report without independently replaying its
checkpoint, canonical records, derived outcomes, and run manifest. That authorization path was
therefore retired before execution; v25.5 remains an immutable, unexecuted preflight.

## v25.6 Protocol, Analysis, And Lineage Repairs

The production candidate uses a new incompatible identity rather than parsing old artifacts:

- Contract Schema: `finance_capability_boundary_contract.v6`;
- Runner: `finance_capability_boundary_runner.v6`;
- Rollout outcome: `finance_capability_rollout_outcome.v5`;
- Rollout record: `finance_capability_boundary_record.v6`;
- Qualification report: `finance_capability_qualification_report.v6`;
- empirical audit: `empirical_capability_information_audit.v6`;
- Beneficiary contract, outcome, and screening artifact: `v4`;
- formal contract ID:
  `finance_capability_boundary_contract:45896e3eafdc2712657a83c8b0e5482d7849639485205e5f88e396313f248ef2`.

The repairs are:

1. Direct semantic action rejection retains `FailedActionPlan` and `HostInteractionProgress`.
2. Only a semantic, task-matched, stage-ordered Direct failure is a bounded terminal result.
3. Scripted authority is checked as a state machine: a failed argument attempt does not advance
   the frozen tool cursor, while any tool-order change still fails.
4. Iterative failure artifacts must match task, Runtime mode, environment, and protocol hash.
5. Runtime exceptions are separated from model-visible typed tool failures.
6. Iterative rationale summaries use a compact 512-character Schema and a 240-character Prompt
   target to reduce repeated JSON truncation without changing answer semantics.
7. Scripted argument correction is now model-visible Recovery; only tool choice, global plan,
   stopping, and tool execution remain Host-controlled in that Runtime.
8. The raw empirical information matrix now exactly uses uncentered model-visible demand. Only the
   axis-specific diagnostic removes the intercept and preregistered general-difficulty factor.
9. Completed checkpoints can be rebuilt without credentials or provider discovery. The manifest
   records whether model discovery came from the live provider, a frozen run manifest, or the
   checkpoint contract.
10. Checkpoints are incremental, content addressed, and resumable; completed runs are canonicalized
   into immutable records, outcomes, report, and run manifest.
11. Recovery diagnostics require a recorded recovery opportunity and a successful corrected
    action. Query Reformulation and Tool-sequence Diversity are separately content-addressed;
    final answer correctness can no longer masquerade as Recovery skill.
12. Qualification authorization is independently replayed from checkpoint through canonical
    records, derived outcomes, report, and run manifest. Full rollout denominators, outcome-set
    hashes, report hashes, exact-model telemetry, and Schema versions are mandatory.
13. An adversarial regression rewrites a self-consistent Qualification report and its manifest
    hash while leaving canonical records unchanged; Calibration rejects it after independent replay.

The Capability Necessity Audit now performs executable or schema-revalidated ablations. It removes
required Evidence, Program branches, output operations, reconciliation constraints, verification
checkpoints, recovery transitions, and final sufficiency conditions, then requires the relevant
Program or typed task contract to reject the mutation. It remains a task-contract necessity test,
not a model causal-effect claim.

The contract freezes the unchanged 70-task Population and task split, 35/35 passing destructive
necessity probes, 126 Qualification rollouts, and 1,680 Calibration rollouts. Credential-free
preflights confirm both missing-run rejection before client construction and rejection of a
self-consistent but canonical-record-inconsistent Qualification report. It has not yet made an API
call.

## Paired Calibration

Calibration can start only from a passing Qualification report:

```text
28 tasks x 2 models x 3 runtimes x 10 replicas = 1,680 rollouts
```

The 28 tasks are balanced at four Frontier tasks per family and are disjoint from Qualification.
Every Pro/Flash comparison is paired by `task_id`; simple unpaired aggregate percentages are
forbidden.

The primary estimator is a task-cluster paired nested Bootstrap. It resamples tasks within the
frozen group and resamples the ten realizations within each selected task. It reports signed 95%
intervals for:

- each Runtime model gap;
- every Family x Runtime model gap;
- Autonomous Family gaps used by the Explorer decision.

A family separates Pro and Flash only when the lower confidence bound, not the point estimate,
exceeds the preregistered minimum gap. The mixed-effect formula remains a diagnostic specification;
it is not misreported as an executed GLMM.

## Empirical Capability Information

For each Model x Runtime cell, the audit estimates task success probabilities from ten independent
rollouts and constructs the uncentered preregistered matrix:

```text
I_hat(M,R) = mean_x p_hat(x) (1 - p_hat(x)) a(x,R) a(x,R)^T
```

The implementation separately centers demand and removes a preregistered general-difficulty factor
before evaluating the residual axis-specific spectrum. It reports:

- raw and residual eigenvalues;
- numerical and effective rank;
- residual condition number;
- general-factor fraction;
- per-axis marginal information with nested-Bootstrap confidence intervals;
- per-family information contribution;
- boundary-task fraction;
- state entropy, decision-trace diversity, tool semantics, verification, recovery, stopping, token
  use, cost, and latency.

An axis is informative only when its confidence-interval lower bound exceeds the frozen minimum.
All six Model x Runtime cells must pass their Runtime-specific rank, condition, boundary, general
factor, and informative-axis gates. At least two Autonomous families must also show a positive
confidence-qualified Pro--Flash gap.

## Beneficiary Screening

The Qwen2.5-7B Beneficiary is a separate local-GPU identity. The identity verifier independently
recomputes:

- training report hash;
- every base-model file size and SHA-256;
- base-model manifest hash;
- every Adapter file size and SHA-256;
- checkpoint hash;
- model-state identity.

The frozen identity is:

```text
beneficiary_model_identity:ee7a1fb3db0a4905093fc6a8c7cdbf7e4f30a8a82f0126a82a139543a55fd91d
```

Only a passing empirical information audit may create the 420-rollout Beneficiary Screening
contract (`28 x 3 x 5`). Screening measures success probability, NLL, tool selection,
verification, recovery, stopping, and accepted state support. Family ordering uses nested
Bootstrap uncertainty: the upper Beneficiary interval must not exceed Flash beyond the frozen
tolerance, while the Pro-minus-Flash lower bound must preserve the same ordering. The screening
Artifact explicitly selects only ordered, boundary-mass task IDs for state discovery and requires
at least seven such tasks. Its only positive transition is
`capability_sensitive_state_discovery`; it cannot authorize Exact Target or GP-C directly.

## Known Limits

1. The seventh structural capability direction remains weak and must be reported with uncertainty.
2. The current frozen Finance source pool has no subject-metric pair with multiple Gold source
   definitions. Reconciliation is limited to definition, period, payload-context, and source/scope
   disambiguation against distractors; it does not establish cross-source Gold reconciliation.
3. v22 Objective micro-split variance remains unresolved. A successful v25 boundary study does not
   waive the need for expanded, stratified Objective Support.
4. v25.0 and v25.1 are protocol diagnostics, not Pro--Flash capability results.
5. v25.6 Qualification and all later model-response stages remain pending.

## Fail-Closed Sequence

```text
v25.6 Runtime Qualification (126)
  -> Pro-Flash paired calibration (1,680), only if passed
  -> empirical capability information audit
  -> Qwen Beneficiary frontier screening (420), only if passed
  -> capability-sensitive state discovery
  -> fresh, disjoint Exact Target
  -> GP-C authorization, only if meaningful coordinates exist
```

At every stage, Validation Objective access, Authorization Objective access, GP-C evaluation,
VTDO updates, and nonzero production Contribution remain forbidden until the preceding typed
artifact explicitly authorizes the transition.
