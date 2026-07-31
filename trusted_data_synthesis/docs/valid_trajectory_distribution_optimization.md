# Valid Trajectory Distribution Optimization

## Method Objective

The framework does not optimize an undifferentiated notion of "data quality". For each public
task `x`, it constructs and improves a finite approximation to the distribution of independently
valid solution trajectories:

```text
p(trajectory | x, V(trajectory, Omega_x) = 1)
```

This is **Valid Trajectory Distribution Optimization (VTDO)**. Finance is a reference domain, not
the method specification. The same objects and update apply to Legal and Science trajectories.

VTDO is not reinforcement learning, online policy learning, free-form template discovery, or a
claim that the framework enumerates every mathematically valid reasoning path. It is a verified,
finite synthesis-policy update over observable trajectory configurations.

## Verification Boundary

For a task `x`, the hidden verification context is:

```text
Omega_x = (E_x, P_x, G_x, Q_x)
```

where:

- `E_x` is the immutable Gold Evidence Bundle inside its frozen public Evidence Corpus;
- `P_x` is the executable TaskProgram and independent operation oracle;
- `G_x` is the pinned Proof Graph;
- `Q_x` is the executable universal and domain Quality Contract.

`TrajectoryValidityEvaluator` defines `V(trajectory, Omega_x)` by jointly requiring the existing
independent Candidate Workflow Verifier and Quality Contract Runtime to pass. It records component
validity for identity/interface, Evidence, Proof Graph, program execution, answer/claim, citation,
and the Quality Contract. Missing verifiers and runtime exceptions fail closed.

## Oracle Execution Specification

The Reference Workflow remains useful for reproducibility, counterfactual calibration, and a
known-good execution example. It is no longer interpreted as the unique gold chain of thought.

Every newly compiled Proof-Carrying artifact freezes an `OracleExecutionSpecification` containing:

- required Evidence and actions;
- allowed tools;
- TaskProgram, Proof Graph, Evidence, and Quality Contract hashes;
- answer schema and Quality Clause identities;
- one or more auditable reference examples;
- the validity rule used for candidate trajectories.

The compatibility field `reference_trajectory` remains the first reference example. Alternative
plans, wording, and intermediate organization are valid when they satisfy the same specification.

## Trajectory Attributes

VTDO measures, but does not prescribe, a behavior vector `m(trajectory)`:

```text
tool_call_count
tool_depth
reasoning_depth
evidence_dependency_count
verification_degree
branching_factor
operation_count
capability_tags
```

Exact values are retained in feedback. A finite `TrajectoryAttributeProfile` bucketization is used
only for policy allocation and diversity reporting. It is not a rigid behavior template, and it
does not constrain natural-language realization.

Profile count, entropy, and normalized diversity are computed only over trajectories with
`V(trajectory, Omega_x) = 1`. Failed trajectories still contribute to validity and failure
statistics, but can never increase valid-solution diversity.

The v3 optimization configuration is:

```text
a = (
  task_pattern,
  evidence_binding_stratum,
  difficulty,
  distractor_context,
  trajectory_attribute_profile
)
```

The distractor dimension remains an Evidence/retrieval condition. The new trajectory profile is
the behavior dimension that turns the old task-distribution policy into a finite approximation of
`p(trajectory | x)`.

## Structured Trajectory Feedback

Each evaluated trajectory produces a versioned `TrajectoryFeedback` record with:

```text
task and trajectory identity
configuration and verification-context identity
binary and component validity
observed trajectory profile
missing target attributes
diversity contribution
failure type and failure location
```

Clause feedback remains responsible for calibrated routing between interface failure, synthesis
defect, and agent capability gap. Trajectory feedback adds execution validity and behavioral
coverage; it does not replace root-cause calibration.

## Utility and Proximal Update

For each configuration `a`, the auditable utility is:

```text
R(a) = alpha * validity_reward(a)
     + beta  * capability_and_distribution_coverage(a)
     + gamma * trajectory_diversity_gain(a)
     - lambda * synthesis_defect_risk(a)
```

The implementation freezes all four components and weights in `TrajectoryUtilityComponents`.
The update remains the closed-form KL-proximal exponentiated update:

```text
pi_next(a) proportional_to pi_t(a) * exp(eta * R(a))
```

Fixed domain or experiment-group marginals are preserved exactly by conditional exponentiation and
deterministic largest-remainder allocation. Reports include KL divergence, total-variation shift,
configuration entropy, trajectory-profile entropy, effective profile count, and capability tags.

The previous CCGR objective remains callable as a historical control. The canonical trajectory
method is `update_valid_trajectory_policy`, identified as
`valid_trajectory_distribution_optimization@vtdo.v1`.

## Multiple Valid Trajectories

`ValidTrajectoryMaterializer` asks a domain-neutral candidate provider for several executions of
one frozen context, verifies every candidate, and retains only independently valid trajectories.
It may cap repeated attribute profiles to prevent one surface strategy from dominating. The report
separately records requested, generated, verified, valid, retained, rejected, and diversity-pruned
counts. Provider exhaustion and an insufficient valid pool block the materialization.

This produces the intended chain:

```text
Proof-Carrying Task
  -> Oracle Execution Specification
  -> multiple candidate trajectories
  -> V(trajectory, Omega_x)
  -> valid trajectory pool
  -> structured trajectory feedback
  -> VTDO policy update
  -> next synthesis allocation
```

## Experimental Metrics

In addition to answer accuracy and Contract acceptance, experiments should report:

- valid trajectory rate and component validity;
- trajectory attribute profile coverage and entropy;
- capability-tag coverage;
- valid alternatives per task;
- synthesis-defect risk and missing-attribute rate;
- KL/TV policy shift;
- downstream training utility under equal-token, equal-model, equal-seed controls.

An increase in trajectory diversity is not itself a success criterion. It counts only when the
additional trajectories remain independently valid and improve held-out capability or training
utility.
