# VTDO Experiment Protocol v6

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
experiment schema:       vtdo_experiment.v6
experiment config:       config/vtdo_experiment_finance.json
student config:          config/vtdo_qwen2_5_7b_500k.json
runner:                  trusted-synthesis run-vtdo-experiment
feedback compiler:       trusted-synthesis generate-vtdo-real-feedback
trainer:                 trusted-synthesis train-vtdo-arm
benchmark predictor:     trusted-synthesis predict-vtdo-benchmarks
default output:          artifacts/vtdo_experiment/finance_v6
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
full JointCompilationArtifact and Omega_x persisted for every accepted task
Omega component manifest replayed before state discovery
```

Accepted states must differ through replayable decisions such as retrieval breadth, verification
frontier, selected evidence lineage, or output lineage. Surface paraphrases and deterministic
format variants are quotient probes only; they cannot increase positive training support.

Before provider invocation, each domain compiles its state semantics into the same Core variation
axes: Evidence Acquisition, Evidence Support, Execution Realization, Verification Policy, and
Lineage Policy. The resulting `TrajectoryStateSpaceCompilation` must embed the original immutable
`JointCompilationArtifact` and freeze the variation-provider manifest. Legal and Science
same-`Omega_x` contract tests must each realize at least two valid states. Domain strategy names
remain in plugins or experiment fixtures and cannot become Core enums.

For every attempted strategy, the artifact records:

```text
strategy attempt count
independent verifier pass count
rejected attempt count and reason
duplicate quotient-state count
raw-sequence and canonical-state identity
retrieval, operation, and evidence-lineage hashes
Omega component manifest and canonicalizer version
verified State discovery witnesses
```

The report must expose the complete funnel rather than computing a pass rate only over retained
states. Every accepted state is replayed by both `CandidateWorkflowVerifier` and the compiled
`QualityContractRuntime`; injected wrong-answer mutations must be rejected.

The configured task count is an **accepted-task quota**, not merely a candidate-attempt limit.
The provider deterministically overprovisions candidate tasks, the materializer continues until
the quota is filled or the candidate pool is exhausted, and the report records both successful
and rejected tasks. Exhaustion before the accepted quota is reached fails closed. This prevents a
nominal 100-task experiment from silently becoming a smaller experiment after state deduplication.

The current Finance implementation is explicitly a
`FinanceDeterministicStateFixtureProvider`. It validates state-space compilation and verifier
behavior; it is not an Explorer and must never be reported as observed model behavior. A real
Explorer or Materializer receives only `PublicStateGenerationRequest`, never full `Omega_x`, an
exact state object, gold Evidence IDs, hidden programs, Proof Graph, or reference answer. Every
request must pass the leakage audit before a provider call.

Final data materialization is a separate, fresh state-conditioned generation phase. It rejects
discovery reuse by trajectory ID, content hash, and normalized decision-trace hash; replays
`V(tau, Omega_x)`; and reproduces the requested quotient state. Reports must include requested,
attempted, off-target, and released counts per state; quota fill and per-state acceptance; source,
allocated-target, and released distributions; total variation and Jensen-Shannon divergence; public
request audits; and decision-trace uniqueness. A budget large enough for the positive support uses a
one-item support floor. A smaller budget declares support truncation. Failed quotas are never
reassigned to easier states.

## 5. Experiment 3: Empirical Contribution Validation

The only active production-candidate approximation family is Scheme 3, Gradient Projection. Local
beneficiary Probes and single-state finite interventions are historical diagnostics; they cannot
authorize a real VTDO Contribution update. The theoretical estimand is unchanged.

For each task, the active experiment freezes one conditional state distribution, three independently
verified quotient states, state-specific training records, four estimation objective records, four
disjoint validation objective records, and an untouched final-test set. For state training-loss
gradient `g_z`, objective-loss gradient `g_v`, and optimizer descent map `U`, the preregistered
variants are:

```text
GP-A = cosine(g_z,g_v) - E_pi[cosine(g_z,g_v)]
GP-B = <g_v, g_z - E_pi[g_z]>
GP-C = <g_v, U(g_z) - E_pi[U(g_z)]>
```

GP-A is the direction-only baseline. GP-B retains gradient magnitude and centers in gradient
space. GP-C is optimizer-aware and must bind the exact optimizer state and hyperparameters. With
plain SGD and a positive scalar learning rate, GP-C and GP-B have identical rankings and are not
independent estimators.

The active runner requires at least 30 tasks and 90 state gradients. Every gradient artifact binds
the task, state, beneficiary checkpoint, tokenizer, supervised-token mask, source record,
distribution, objective split, dtype, and content hash. Estimation and validation objectives are
mutually disjoint. The untouched final test cannot be loaded until every candidate score, scale,
threshold, perturbation, and design identity is frozen.

Proxy stability is necessary but not sufficient. Estimation and validation Gradient Projection
rankings are compared first. Independent validation then constructs two zero-sum contrast
coordinates for each three-state task and evaluates a frozen symmetric batch design:

```text
30 tasks x 2 coordinates = 60 coordinates
64 x 60 Sylvester-Hadamard design
D_h = (J(theta - eta*(g_base + epsilon*H_h G))
       - J(theta - eta*(g_base - epsilon*H_h G))) / (2*epsilon)
```

The intervention binds the complete conditional distribution, so task marginal `mu(x)`, state
support, and total update mass remain fixed. The learning-rate ladder is preregistered and may be
selected only by parameter-step fidelity. The final-test outcome cannot select the scale. A target
is interpretable only when probabilities remain positive, numeric replays are deterministic,
Hadamard reconstruction passes, and the actual float32 parameter update matches the intended update.
Production additionally requires the selected optimizer and learning rate to match the source
training contract.

For both estimation and validation proxies, the lower 95% macro-Spearman bound must exceed zero,
the lower 95% pairwise-concordance bound must exceed 0.5, winner agreement must pass its frozen
minimum, and permutation p-values must be below 0.05. Missing support, leakage, parameter-step
non-identifiability, source-scale mismatch, or either failed rank gate blocks authorization.

The first completed 30-task run found estimation-versus-validation Spearman `0.717`, but its
independent cached-SGD target failed both rank gates. The selected numerically identifiable
learning rate was `5e-4`, not the source `5e-5`.

The subsequent GP-A/B/C comparison retained the 30-task support and froze a one-step cold-start
AdamW target before final evaluation. Estimation/validation Spearman against that matching target
was `0.417/0.450` for GP-A, `0.483/0.467` for GP-B, and `0.517/0.517` for GP-C. All passed the
frozen rank gate. Paired intervals did not establish GP-C as better than GP-B, and none of the
three transferred to the old SGD target. Because the historical continuation optimizer state is
unavailable, this is mechanism evidence under a diagnostic optimizer contract, not production
authorization. Real Finance VTDO rounds still use `Contribution=0`. Immutable evidence is in
`docs/finance_gradient_projection_abc_validation_report.md`.

The independent authorization run then froze GP-C as Primary, GP-B as Secondary, a strictly fresh
30-task population, disjoint Estimation/Validation/Authorization objectives, the one-step cold-start
AdamW contract, and state-homogeneous `E_pi[U(g_z)]` batch semantics. Calibration was fit on
Estimation only. In addition to rank evidence, the gate compared proxy- and finite-target-induced
next distributions using TV, Jensen-Shannon divergence, probability-update direction, and target
variational regret. GP-C failed the internal rank and distribution gates: Estimation/Validation
Spearman was `0.150/0.300`, direction agreement was `0.544/0.589`, and mean normalized regret was
`3.867/3.010`. The untouched Authorization objective was not opened and no production credential
was issued. A post-global-update objective-gradient diagnostic did not recover GP-C. This negative
result supersedes any interpretation that the earlier diagnostic population was sufficient for
production authorization; it does not erase that run's bounded mechanism evidence. Full evidence
is in `docs/finance_gradient_projection_independent_authorization_report.md`.

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

The five-round benchmark compares no feedback, one-shot static optimization, and full VTDO under
three explicitly separated tracks:

```text
Track A  exogenous_shared              primary, method-neutral potential sequence
Track B  vtdo_induced_shared           supplementary, shared sequence induced by VTDO exposure
Track C  method_specific_closed_loop   supplementary, each method induces its own potential
```

Track A is the headline comparison because every method sees the same exogenous drift and no
method exposure enters `Phi_t`. Tracks B and C analyze endogenous feedback and cannot replace the
method-neutral result. Every track reports tracking error, cumulative dynamic regret, exact
proximal-objective replay, and confidence intervals. When regret advantage is required, the lower
confidence bound, not merely the sample mean, must be nonnegative.

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

### Recorded real-feedback production

`generate-vtdo-real-feedback` consumes a frozen Finance state pool, recorded Explorer trajectories,
and atomic beneficiary intervention records. It independently replays every trajectory through the
Finance verifier, reconstructs exploration distributions and multi-seed Contribution probes,
builds `RealRoundAssemblyInput`, assembles the Round artifacts, and replays the serialized inputs a
second time. Checkpoint, generation, evaluation, budget, seed-set, and source-file hashes are part
of the report identity. Missing model outputs are never synthesized by this compiler.

### Beneficiary model-state shift

The primary causal refinement experiment freezes the beneficiary checkpoint so that only
`pi(z|x)` changes. A separate paired `M0 -> M1` experiment compares Contribution observations on
exactly the same task-state-seed support and frozen evaluation/probe contract. It reports task-clustered absolute
Contribution shift with a paired confidence bound, task-wise rank correlation, and direction-change
rate. This supports the
limited claim that `C_t(x,z)` can depend on model state; it does not substitute for the fixed-
beneficiary primary comparison.

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

FinQA and TAT-QA are mandatory evaluation-only snapshots for the primary experiment; FinanceBench
is an optional extension. Exact repository revisions, split identities, adapter/metric versions,
and SHA-256 hashes must be frozen before training. The trainer validates the serialized preflight,
arm manifest,
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
7. the mandatory FinQA and TAT-QA snapshots match their frozen identities and hashes;
8. no public training input contains Oracle evidence IDs, reference answers, or hidden programs;
9. no hard benchmark leakage collision or unavailable required hard channel is present;
   subject overlap is report-only.

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
beneficiary_state_shift_report.json
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
benchmark_leakage_audit.json
vtdo_experiment_report.md
manifest.json
```

GPU training is invoked per ready arm with `train-vtdo-arm`. A blocked preflight exits before model
loading or CUDA allocation. Each invocation must include a seed from the frozen preflight.

External predictions are first generated from an immutable training result and generation config,
then evaluated without training-data access:

```bash
trusted-synthesis predict-vtdo-benchmarks \
  --vtdo-config config/vtdo_experiment_finance.json \
  --training-result <model-run>/training_result.json \
  --generation-config config/vtdo_benchmark_generation.json \
  --output-dir <model-run>/benchmark_predictions

trusted-synthesis evaluate-vtdo-benchmarks \
  --vtdo-config config/vtdo_experiment_finance.json \
  --predictions <model-run>/benchmark_predictions/benchmark_predictions.jsonl \
  --prediction-manifest \
    <model-run>/benchmark_predictions/benchmark_prediction_manifest.json
```

The evaluator reports contract success, semantic accuracy conditional on a valid contract,
end-to-end accuracy, native F1, Wilson intervals, and FinQA program execution accuracy. FinQA
prompts contain pre-text, tables, post-text, and an answer/scale/program contract; TAT-QA prompts
contain tables, paragraphs, and an answer/scale contract. The immutable prediction manifest binds
the training arm/result/seed, adapter and base-model content, generator, generation config, and
evaluation snapshot. Exact/near prompt, evidence, source-record, document, and binding collisions
are hard blockers; an unavailable required hard channel also blocks the run, and subject overlap is
a soft diagnostic.

## 11. Claim Discipline

| Evidence available | Permitted claim |
|---|---|
| Controlled synthetic run | update implementation and controlled distribution behavior |
| Fixed-potential control | numerical verification of the contraction result |
| Exogenous moving-potential track | method-neutral finite-step tracking and dynamic regret |
| Endogenous moving-potential tracks | supplementary feedback-path diagnostics only |
| Real multi-state artifacts | state-construction feasibility and verified state diversity |
| Stable Gradient Projection splits | proxy reproducibility only, not causal Contribution validity |
| Independently authorized Contribution proxy | association with a frozen, numerically identifiable distribution target |
| Paired M0/M1 observations | model-state dependence under the frozen probe contract |
| Equal-budget trained arms | downstream utility comparison |
| Frozen external benchmarks | benchmark generalization under the declared snapshots |

No report may promote a blocked component, simulated observation, or distribution-only checkpoint
into a downstream empirical conclusion.

## 12. Legacy Removal

Historical v0.8/v0.9 source, tests, configurations, reports, checkpoints, and generated outputs
have been permanently removed from the working tree. Restoring tracked source requires an explicit
historical Git revision; ignored generated outputs are not recoverable. The active CLI and config
loader intentionally provide no compatibility alias.
