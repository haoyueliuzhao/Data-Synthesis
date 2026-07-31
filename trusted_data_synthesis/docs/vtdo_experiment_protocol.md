# VTDO Experiment Protocol v1

## 1. Purpose

This document defines the only active paper experiment for Valid Trajectory Distribution
Optimization (VTDO). It replaces the legacy v0.8 training-utility and v0.9 validation protocols.
Historical implementations and outputs have been removed from the working tree. Tracked source
changes remain auditable through Git history, but no legacy artifact is an accepted protocol input.

The experimental claim chain is:

```text
State validity and quotient identity
-> trajectory-state distribution optimization
-> downstream training utility
```

Each stage must be established with its own observable artifact. A result at an earlier stage
cannot be reported as evidence for a later stage.

## 2. Frozen Identity

The active identities are:

```text
experiment schema:       vtdo_experiment.v1
experiment config:       config/vtdo_experiment_finance.json
student config:          config/vtdo_qwen2_5_7b_500k.json
runner:                  trusted-synthesis run-vtdo-experiment
trainer:                 trusted-synthesis train-vtdo-arm
default output:          artifacts/vtdo_experiment/finance_v1
```

Every run freezes the normalized experiment configuration, all external input hashes, execution
source-tree hash, Git commit, dirty-worktree status, state artifacts, round artifacts, arm data,
and final manifest. The output directory must be absent or empty.

## 3. Experiment 1: Controlled VTDO Validation

The controlled state space contains `K=200` states and uses five frozen seeds. Accepted-state
contribution is centered so that:

```text
E_{z ~ pi_0}[C(z)] = 0
```

Novelty follows the frozen density-ratio definition:

```text
N_t(z) = [log(r(z) / pi_t(z))]+
```

The fixed optimum used for evaluation is:

```text
p*(z) proportional to r(z) Phi(z)^(1 / kappa)
```

Main methods:

```text
Random
Contribution Only
Novelty Only
CCGR
VTDO
```

Ablations are reported separately:

```text
No Anchor
No Iteration
No Quotient
```

Required metrics are `KL(pi_t || p*)`, joint utility `E[C x N]`, coverage alignment, entropy,
active support, and the contribution-novelty phase trajectory. No contribution-oracle KL metric is
used.

This experiment validates the update implementation and controlled estimator behavior. It does
not establish empirical causal contribution or downstream training gain.

## 4. Experiment 2: Real Financial Trajectory States

The primary real-data contract requires:

```text
100 unique financial tasks
3-5 independently accepted states per task
300-500 accepted trajectories in total
one frozen Oracle program per task
full Omega_x persisted for every accepted task
```

Accepted states must differ through replayable decisions such as retrieval breadth, verification
frontier, selected evidence lineage, or output lineage. Surface paraphrases and deterministic
format variants are quotient probes only; they cannot increase positive training support.

For every attempted strategy, the artifact records:

```text
strategy attempt count
independent verifier pass count
rejected attempt count and reason
duplicate quotient-state count
raw-sequence and canonical-state identity
retrieval, operation, and evidence-lineage hashes
```

The report must expose the complete funnel rather than computing a pass rate only over retained
states. Every accepted state is replayed by both `CandidateWorkflowVerifier` and the compiled
`QualityContractRuntime`; injected wrong-answer mutations must be rejected.

The configured task count is an **accepted-task quota**, not merely a candidate-attempt limit.
The provider deterministically overprovisions candidate tasks, the materializer continues until
the quota is filled or the candidate pool is exhausted, and the report records both successful
and rejected tasks. Exhaustion before the accepted quota is reached fails closed. This prevents a
nominal 100-task experiment from silently becoming a smaller experiment after state deduplication.

The current deterministic Finance materializer is suitable for validating state construction. It
must not be described as observed model behavior unless the states originated from recorded model
calls.

## 5. Experiment 3: Empirical Contribution Validation

Contribution quality is an empirical question. The active runner accepts only an immutable JSONL
observation file containing at least 100 unique trajectory-state observations across at least 100
tasks. Each observation binds:

```text
task_id
state_id
estimated contribution C_hat
observed downstream delta J
training/evaluation identity
```

The primary diagnostics are Spearman correlation and sign agreement. Missing, undersized, or
identity-inconsistent observations block this component. Synthetic observations are never created
as a replacement.

## 6. Experiment 4: Refinement Dynamics

### Fixed-potential control

For fixed `Phi`, the update has a unique fixed point and a projective contraction governed by
`rho`. The experiment runs the controlled update for ten rounds and verifies the numerical
contraction within the configured tolerance. This is the only component that supports a strict
convergence statement.

### Moving-potential process

Production VTDO recomputes contribution and novelty, so it tracks a moving optimum. The primary
analysis horizon is five rounds, with checkpoints at rounds 1, 3, and 5. The practical
stabilization score is:

```text
S_t = KL(pi_(t+1) || pi_t) + lambda * |U_(t+1) - U_t|
```

Practical stabilization requires `S_t < epsilon` for two consecutive transitions. The report also
tracks utility, entropy, active coverage, and per-round distribution identity. It may state that
updates stabilize or exhibit diminishing returns; it must not claim mathematical convergence of
the moving-potential process.

Real financial refinement is accepted only from immutable, lineage-linked `VTDORoundArtifact`
files. Missing rounds are reported as blocked and are not replaced by the controlled run.

## 7. Experiment 5: Equal-Budget Downstream Training

The frozen B1-B5 comparison is:

| Arm | Definition |
|---|---|
| `B1_raw` | Unfiltered generated trajectories, including a controlled invalid attempt per task |
| `B2_validity` | Independently valid trajectories |
| `B3_ccgr` | States sampled from a current, frozen CCGR task distribution |
| `B4_random_state` | One deterministic random accepted state per task |
| `B5_vtdo` | States sampled from the selected real VTDO round distribution |

All arms use the same Qwen2.5-7B model revision, LoRA configuration, supervised-token budget,
optimizer schedule, number of steps, and seed. The primary contract requires at least 100 unique
tasks and at least 50 unique accepted states per arm. Dataset size alone is not readiness.

FinQA, TAT-QA, and FinanceBench are evaluation-only. Their exact snapshot IDs and SHA-256 hashes
must be frozen before training. The trainer validates the serialized preflight, arm manifest,
dataset identity, task/state capacity, token schedule, model revision, and benchmark contract
before allocating a GPU.

The one-shot versus iterative comparison uses round 1 and round 3 with identical task marginals,
token budgets, model settings, and seeds. Round 5 is an analysis checkpoint unless separately
declared and frozen as a training arm.

## 8. Sensitivity And Quotient Analysis

The controlled run evaluates `eta` in `[0.1, 0.25, 0.5, 1.0]`. Quotient analysis compares raw
trajectory hashes with canonical state identities and reports merge rate, validity purity or
variance, and contribution consistency.

If a run does not preserve complete `Omega_x`, it may be reported only as a canonicalization probe.
It cannot be used to estimate the empirical conditional state distribution.

## 9. Fail-Closed Readiness

The full training experiment is ready only when all of the following hold:

1. every requested Finance task has 3-5 independently verified canonical states;
2. empirical contribution observations satisfy the frozen sample and task thresholds;
3. real round artifacts cover the configured refinement checkpoints with exact lineage;
4. B3 uses a current CCGR distribution rather than a legacy synthesis-cell proxy;
5. B5 is derived from the selected real VTDO round;
6. every B1-B5 arm satisfies task, state, token, model, and seed parity;
7. all three external benchmark snapshots match their frozen hashes;
8. no public training input contains Oracle evidence IDs, reference answers, or hidden programs.

The run status is `passed`, `partial`, or `blocked`. A partial run may be useful for component
validation but cannot support the full downstream-training claim.

## 10. Execution

```bash
source scripts/activate_project.sh

trusted-synthesis run-vtdo-experiment \
  --vtdo-config config/vtdo_experiment_finance.json
```

The run emits JSON reports, CSV tables, SVG figures, multi-state artifacts, B1-B5 datasets,
preflight results, an input manifest, and a final manifest. A representative artifact set is:

```text
experiment_config.json
input_manifest.json
synthetic_experiment_report.json
synthetic_states.jsonl
synthetic_metric_points.csv
synthetic_phase_observations.csv
table1_synthetic_methods.csv
figure1_distribution_evolution.svg
figure2_contribution_novelty_phase.svg
finance_multi_state/finance_multi_state_report.json
finance_multi_state/finance_multi_state_tasks.jsonl
contribution_validation_report.json
refinement_dynamics_report.json
controlled_refinement_rounds.csv
fixed_potential_contraction_rounds.csv
real_refinement_rounds.csv
table2_refinement_dynamics.csv
table3_one_shot_vs_iterative.csv
figure3_refinement_dynamics.svg
training_preflight.json
training_arms/*.jsonl
vtdo_experiment_report.md
manifest.json
```

GPU training is invoked per ready arm with `train-vtdo-arm`. A blocked preflight exits before model
loading or CUDA allocation.

## 11. Claim Discipline

| Evidence available | Permitted claim |
|---|---|
| Controlled synthetic run | update implementation and controlled distribution behavior |
| Fixed-potential control | numerical verification of the contraction result |
| Moving-potential rounds | finite-step dynamics and practical stabilization only |
| Real multi-state artifacts | state-construction feasibility and verified state diversity |
| Contribution observations | association between estimated contribution and observed delta J |
| Equal-budget trained arms | downstream utility comparison |
| Frozen external benchmarks | benchmark generalization under the declared snapshots |

No report may promote a blocked component, simulated observation, or distribution-only checkpoint
into a downstream empirical conclusion.

## 12. Legacy Removal

Historical v0.8/v0.9 source, tests, configurations, reports, checkpoints, and generated outputs
have been permanently removed from the working tree. Restoring tracked source requires an explicit
historical Git revision; ignored generated outputs are not recoverable. The active CLI and config
loader intentionally provide no compatibility alias.
