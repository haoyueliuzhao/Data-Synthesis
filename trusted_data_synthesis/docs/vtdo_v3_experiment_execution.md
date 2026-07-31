# VTDO v3 / AEVTDR v2 Experiment Execution

## Scope

This experiment uses the canonical trajectory-state implementation directly. CCGR is retained
only as a historical baseline. The VTDO student configuration is independent of the old D1-D5
MVP schema; no compatibility alias maps synthesis cells to quotient trajectory states.

The executable entry point is:

```bash
.venv/bin/trusted-synthesis run-vtdo-validation \
  --vtdo-config config/vtdo_validation_finance.json
```

The immutable result is written to:

```text
artifacts/vtdo_validation/vtdo_paper_validation_20260731_final/
```

The refinement-dynamics extension is frozen separately at:

```text
artifacts/vtdo_validation/vtdo_paper_validation_20260731_round_dynamics/
```

It freezes the normalized experiment and student configs, every external input SHA-256, the
execution source-tree hash, arm dataset hashes, Git commit, and dirty-worktree status.

## Completed Evidence

### Controlled synthetic validation

The run evaluates 200 states, 20 update rounds, and five fixed seeds. It includes Random,
Novelty-only, Contribution-only, No-anchor, frozen CCGR, full VTDO, No-iteration, and No-quotient.
Full VTDO has the highest mean final joint utility `E[C x N]` (`0.0556`), compared with `-0.0209`
for CCGR. Five-seed confidence intervals overlap, so this is evidence of the intended update
behavior, not a significance or convergence claim.

Generated paper artifacts include:

```text
table1_synthetic_method_comparison.csv
figure2_distribution_evolution.svg
figure3_contribution_novelty_phase.svg
synthetic_metric_points.csv
synthetic_phase_observations.csv
```

### Refinement dynamics and practical convergence

The v3 run separates two claims that must not be conflated.

First, a fixed-potential control freezes `Phi` at the first production VTDO update. The analytic
fixed point is

```text
pi*(z|x) proportional to r(z|x) Phi(z)^(eta/(1-rho)).
```

Across five seeds and ten controlled updates, the observed projective contraction factor is
`0.500000`, equal to `rho=0.5`; the maximum absolute numerical error is `1.199e-14`. This is the
finite numerical verification of the fixed-potential contraction result.

Second, the production update recomputes contribution and novelty potentials each round. It is
therefore evaluated under the following practical-stability rule:

```text
KL(pi_t || pi_(t-1)) < 0.01
and
abs(U_t - U_(t-1)) < 0.01
for two consecutive transitions.
```

No seed satisfies that rule within five rounds. Mean KL shift remains between `1.1384` and
`1.9564`; joint utility alternates in sign; entropy remains between `2.8871` and `3.1578`; active
coverage remains `42.2` states on average. The result is non-collapsing but oscillatory, not
practically converged. The paper must not state that VTDO converges after three rounds.

The distribution-only checkpoint comparison is:

| Checkpoint | Role | Mean E[C x N] | Gain from one-shot | Training evaluated |
|---:|---|---:|---:|---|
| 1 | One-shot | -0.0654 | 0.0000 | No |
| 3 | Primary iterative | -0.0468 | +0.0186 | No |
| 5 | Analysis only | -0.0357 | +0.0298 | No |

These are not downstream model gains. A one-round versus three-round training claim remains
blocked until the corresponding real state-conditioned materializations exist under the same
fixed token budget.

Generated dynamics artifacts are:

```text
refinement_dynamics_report.json
controlled_refinement_rounds.csv
fixed_potential_contraction_rounds.csv
table2_refinement_round_dynamics.csv
table3_one_shot_vs_iterative.csv
figure4_refinement_dynamics.svg
```

### Quotient-state controlled probe

Twenty archived Finance trajectories were reconstructed. Controlled surface variants produced
76 raw sequence identities but 20 canonical states, for a 73.68% equivalent merge rate. Semantic
mutations separated at 100% in this probe.

This is not an empirical estimate of a real conditional state distribution. The archived run did
not persist source-complete `Omega_x`; all 20 reconstructed contexts exhibit Quality Contract
metadata drift under current code, and only one real observed state exists per task condition.

## Training Gate

The frozen student contract is Qwen2.5-7B-Instruct, revision
`a09a35458c702b33eeacc393d103063234e8bc28`, LoRA rank 8, 500,000 supervised tokens per arm,
and seed `20260731`.

Current arm capacity is:

| Arm | Records | Tasks | States | Multi-state tasks | Status |
|---|---:|---:|---:|---:|---|
| B1 Raw | 20 | 20 | 20 | 0 | pilot only |
| B2 Validity | 18 | 18 | 18 | 0 | pilot only |
| B3 CCGR | 18 | 18 | 18 | 0 | pilot only |
| B4 Random state | 18 | 18 | 18 | 0 | pilot only |
| B5 VTDO | 0 | 0 | 0 | 0 | blocked |

`train-vtdo-arm` validates the serialized preflight identity, student config hash, formal readiness,
arm status, record and task counts, unique record identities, and arm dataset hash before loading
the model. The current B5 invocation returns a structured `blocked` decision before GPU allocation.

## Conditions For The Real Training Experiment

The B1-B5 comparison must not run until all conditions hold:

1. At least 100 unique Finance task conditions and 50 canonical accepted states are available per
   arm.
2. A nonzero set of task conditions has at least two independently generated, accepted real states.
3. DeepSeek exploration persists source-complete `Omega_x`, state assignments, validity reports,
   exploration probabilities, and on-target materialization artifacts for three rounds.
4. B5 is produced by `ValidTrajectoryStateMaterializer`; surface paraphrases and duplicated
   trajectories do not count as new states.
5. FinQA, TAT-QA, and FinanceBench snapshots and evaluation adapters are frozen before training.
6. Every arm passes the same 500,000-token audit and uses the same Qwen revision and seed.
7. At least one Finance task condition has five consecutive, independently replayable
   `VTDORoundArtifact` transitions with exact distribution lineage.
8. Round-1 and round-3 materializations are both frozen so downstream one-shot versus iterative
   gains can be compared without changing task marginal, token budget, model, or seed.

Until these conditions are met, GPU training would measure repeated singleton trajectories rather
than valid trajectory-distribution optimization and is intentionally blocked.

## Verification

The exact source tree represented by the final artifact passed:

```text
pytest: 215 passed
ruff: passed
mypy: 204 source files passed
git diff --check: passed
```

The refinement experiment status is `partial`: fixed-potential contraction and moving-potential
finite-step diagnostics are complete. Real financial round dynamics, empirical multi-round VTDO
training, and external benchmark evaluation remain unexecuted by design and are recorded as
blocked components rather than inferred from synthetic results.
