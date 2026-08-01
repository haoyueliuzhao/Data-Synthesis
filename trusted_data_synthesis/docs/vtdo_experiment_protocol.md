# VTDO Experiment Protocol v3

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
experiment schema:       vtdo_experiment.v3
experiment config:       config/vtdo_experiment_finance.json
student config:          config/vtdo_qwen2_5_7b_500k.json
runner:                  trusted-synthesis run-vtdo-experiment
trainer:                 trusted-synthesis train-vtdo-arm
default output:          artifacts/vtdo_experiment/finance_v3
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

The initial fixed-potential target is retained only as a diagnostic:

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

Ablations are reported separately under explicit semantics:

```text
No Global Coverage Anchor
No Coverage Prior
No Iteration
No Quotient with Exact Contribution
No Quotient with Noisy Contribution
```

The production moving-potential methods are not ranked by distance to the initial target. Their
main diagnostics are expected log potential, coverage alignment, entropy, active support, and the
contribution-novelty phase trajectory. Fixed-point KL and projective contraction belong only to
the stationary-potential operator-control track. No contribution-oracle KL metric is used.

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
observation file containing at least 90 observations from at least 30 tasks, with at least three
states per eligible task. Each observation binds:

```text
task_condition_id
state_id
estimated contribution C_hat
observed downstream delta J
beneficiary checkpoint and evaluation distribution
probe protocol and baseline-distribution identity
intervention budget and seed
evaluation snapshot identity
```

The primary diagnostics are within-task rank correlation, pairwise concordance, task-macro
Spearman, centered global Spearman, sign agreement, and task-cluster bootstrap intervals. A
negative rank relationship fails even when its absolute magnitude is large. Missing, undersized,
single-state, or identity-inconsistent observations block this component. Synthetic observations
are never created as a replacement.

## 6. Experiment 4: Refinement Dynamics

### Fixed-potential control

For fixed `Phi`, the update has a unique fixed point and a projective contraction governed by
`rho`. The experiment runs the controlled update for ten rounds and verifies the numerical
contraction within the configured tolerance. Its experimental role is **update operator
verification**: it verifies the analytic implementation under a stationary potential, but it is
not evidence that the model-coupled VTDO loop converges to a static optimum.

### Controlled moving-potential tracking

For each round, the implementation independently evaluates the proximal objective

```text
F_t(pi) = E_pi[log Phi_t]
          - lambda KL(pi || pi_t)
          - kappa KL(pi || r)
```

and verifies both `F_t(pi_(t+1)) >= F_t(pi_t)` and equality with the exact proximal optimizer:

```text
pi_prox_t*(z) proportional to
    pi_t(z)^(lambda/(lambda+kappa))
    r(z)^(kappa/(lambda+kappa))
    Phi_t(z)^(1/(lambda+kappa))
```

Tracking is measured against the instantaneous anchored optimum with the historical proximal term
removed:

```text
G_t(pi) = E_pi[log Phi_t] - kappa KL(pi || r)
pi_anchor_t*(z) proportional to r(z) Phi_t(z)^(1/kappa)
TrackingError_t = KL(pi_(t+1) || pi_anchor_t*)
```

The five-round benchmark compares no feedback, one-shot static optimization, and full VTDO on the
same moving-potential sequence. It reports tracking error and cumulative dynamic regret. This
tests whether the update direction follows an evolving target, rather than merely whether the
formula remains numerically stable.

### Real feedback-loop stabilization

Production VTDO recomputes contribution and novelty after model feedback, so the optimum moves.
The primary analysis horizon is five rounds, with checkpoints at rounds 1, 3, and 5. The practical
stabilization score uses the current round potential on both sides:

```text
S_t = KL(pi_(t+1) || pi_t)
      + alpha * |E_pi_(t+1)[log Phi_t] - E_pi_t[log Phi_t]|
      + zeta * D_Phi(t)
```

`D_Phi(t)` is a projective potential-drift diagnostic over pairwise log-potential ratios. The
first transition cannot satisfy a consecutive-round stop criterion because no preceding potential
exists for drift comparison.

Practical stabilization requires `S_t < epsilon` for two consecutive transitions. The report also
tracks utility, entropy, active coverage, state entries/exits, tracking error, dynamic regret, and
per-round distribution identity. It may state that updates stabilize, track a moving optimum, or
exhibit diminishing returns; it must not claim mathematical convergence of the moving-potential
process.

Real financial refinement is accepted only from immutable, lineage-linked `VTDORoundArtifact`
files. Every round independently replays the variational objective and exact proximal optimizer.
Missing rounds are reported as blocked and are not replaced by the controlled run.

## 7. Experiment 5: Equal-Supervised-Token Downstream Training

The frozen training matrix is:

| Arm | Definition |
|---|---|
| `B1_raw` | Unfiltered generated trajectories, including a controlled invalid attempt per task |
| `B2_validity` | Independently valid trajectories |
| `B2_contribution_only` | Same accepted support and selected Round, weighted only by normalized contribution |
| `B2_novelty_only` | Same accepted support and selected Round, weighted only by normalized novelty |
| `B3_ccgr` | States sampled from a current, frozen CCGR task distribution |
| `B4_random_state` | One deterministic random accepted state per task |
| `B5_vtdo` | States sampled from the selected real VTDO round distribution |

The primary causal arms are B2 Validity, Contribution Only, Novelty Only, B4 Random State, and B5
VTDO. Their per-task sampling weights each sum to one, freezing the task marginal `mu(x)` and
changing only `pi(z|x)`. B1 is a controlled-quality lower bound rather than a natural raw Explorer
distribution. B3 is a historical task-distribution baseline with a deliberately nonuniform task
marginal and is therefore not part of the strict causal comparison.

All training runs use the same Qwen2.5-7B revision, LoRA configuration, and supervised-token
budget. The protocol does **not** claim equal optimizer steps or equal compute. Every run records
assistant-supervised tokens, prompt tokens, total processed tokens, optimizer steps, scheduled
examples, unique records, and repetition rate. The three frozen primary seeds are supplied
explicitly to the trainer. The primary capacity contract requires at least 100 unique tasks and at
least 50 unique accepted states per arm. Dataset size alone is not readiness.

The feedback-loop ablation freezes trainable B5 datasets only at one-based refinement checkpoints
1 and 3. Every trainable checkpoint must contain all task conditions, replay a complete lineage-linked
round sequence from Round 1, preserve exact trajectory-state support, and satisfy the same task,
state, token, model, and benchmark contracts. Each checkpoint has an independent dataset hash and
manifest. Missing real rounds block the comparison; controlled synthetic distributions are never
substituted for these training datasets. Round 1 is the one-shot condition, Round 3 is the primary
iterative condition, and Round 5 is analysis-only and is never materialized as a training arm.

FinQA, TAT-QA, and FinanceBench are evaluation-only. Their exact snapshot IDs and SHA-256 hashes
must be frozen before training. The trainer validates the serialized preflight, arm manifest,
dataset identity, task/state capacity, token schedule, model revision, and benchmark contract
before allocating a GPU.

The one-shot versus iterative comparison uses rounds 1 and 3 with identical task marginals,
supervised-token budgets, model settings, and seeds. Round 5 remains an analysis checkpoint.

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
6. every primary causal arm satisfies the fixed-task-marginal, state, supervised-token, model,
   and multi-seed contracts;
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

The run emits JSON reports, CSV tables, SVG figures, multi-state artifacts, causal and secondary
training-arm datasets,
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
fixed_potential_operator_verification.csv
moving_potential_tracking_rounds.csv
real_refinement_rounds.csv
table2_moving_potential_tracking.csv
table3_refinement_dynamics.csv
table4_refinement_checkpoints.csv
figure3_moving_potential_tracking.svg
figure4_refinement_dynamics.svg
training_preflight.json
training_arms/*.jsonl
vtdo_experiment_report.md
manifest.json
```

GPU training is invoked per ready arm with `train-vtdo-arm`. A blocked preflight exits before model
loading or CUDA allocation. Each invocation must include a seed from the frozen preflight.

External predictions are evaluated without training-data access:

```bash
trusted-synthesis evaluate-vtdo-benchmarks \
  --vtdo-config config/vtdo_experiment_finance.json \
  --predictions <run>/benchmark_predictions.jsonl
```

The evaluator reports contract success, semantic accuracy conditional on a valid contract,
end-to-end accuracy, and Wilson intervals for FinQA, TAT-QA, and FinanceBench. Training preflight
also performs text, operation, subject, evidence, source-record, document, and binding leakage
checks against the frozen evaluation snapshots.

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
