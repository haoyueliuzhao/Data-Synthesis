# Trusted Data Synthesis

Trusted Data Synthesis is a domain-agnostic framework for constructing and evaluating
proof-carrying agent trajectories. Finance is the first full reference implementation, not the
specification of the core framework.

```text
Domain Evidence Adapter
-> Evidence IR and Proof Graph
-> Task Pattern and content-addressed Binding
-> Public Task and hidden Oracle Contract
-> Candidate Trajectory and independent replay
-> Quality Contract and typed counterfactuals
-> Canonical trajectory state z
-> VTDO distribution refinement pi_t(z | x)
-> Fixed-task-marginal causal training and frozen evaluation
```

## Active Method Boundary

The sole paper experiment is `vtdo_experiment.v6`. Its evidence chain is deliberately ordered:

```text
Trajectory State Validation
-> Distribution Refinement
-> Equal-budget Downstream Training
```

The active protocol does not reinterpret legacy synthesis cells as VTDO states and does not use
surface paraphrases to inflate state support. A real state must differ in retrieval scope,
verification frontier, evidence lineage, or another independently replayable decision path.

The six experiment components are:

1. controlled VTDO validation on a 200-state synthetic space;
2. real financial trajectory-state construction with 3-5 accepted states per task;
3. multi-seed empirical contribution validation against observed downstream utility changes;
4. update-operator verification plus exogenous, VTDO-induced, and method-specific moving-potential
   tracks;
5. replayable real-feedback Round production and a paired `M0 -> M1` beneficiary-state probe;
6. equal-supervised-token Qwen2.5-7B training over fixed-task-marginal validity,
   contribution-only, novelty-only, random-state, and VTDO arms, with controlled corruption and
   CCGR reported separately, followed by frozen native FinQA/TAT-QA evaluation.

Missing recorded Explorer outputs, local Probe observations, paired finite-Intervention validation, VTDO rounds, or arm capacity are
represented as blocked components. They are never replaced with synthetic evidence or inferred
gains. FinQA and TAT-QA snapshots are frozen under `benchmarks/`; FinanceBench remains an optional
extension rather than a hidden preflight requirement.

## Repository Layout

```text
src/trusted_synthesis/core/                 domain-independent contracts and runtime
src/trusted_synthesis/domains/              domain policies and adapters
src/trusted_synthesis/experiments/          reusable experiment support
src/trusted_synthesis/experiments/vtdo_experiment/
                                             canonical paper experiment
config/vtdo_experiment_finance.json         canonical experiment configuration
config/vtdo_qwen2_5_7b_500k.json            frozen student configuration
docs/vtdo_experiment_protocol.md            experiment and claim protocol
```

The financial adapter reads immutable artifacts from `../raw_financial_data_lake`. It does not
write to that archive.

## Environment

```bash
cd /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis
source scripts/activate_project.sh
python -m pip install -e ".[dev,finance,training]"
```

The migrated server and model-cache contract are documented in
[Server Recovery](docs/server_recovery.md).

## Core Validation

```bash
trusted-synthesis inspect-finance --config config/finance_archive.json
trusted-synthesis audit-finance-synthesis-capacity \
  --config config/finance_archive.json \
  --output artifacts/audits/finance_capacity.json
trusted-synthesis audit-generalization --source-root src
trusted-synthesis validate-task-patterns --tasks-per-domain 10
trusted-synthesis validate-counterfactuals \
  --tasks-per-domain 10 \
  --output artifacts/audits/counterfactual_contract.json
pytest -q
```

## Canonical Experiment

```bash
trusted-synthesis run-vtdo-experiment \
  --vtdo-config config/vtdo_experiment_finance.json
```

The configured output directory must be absent or empty. The run freezes configuration hashes,
input hashes, source-tree identity, Git state, reports, state artifacts, distributions, and
training-arm manifests.

GPU training is a separate fail-closed step. It is allowed only when the serialized preflight
reports `primary_causal_training_ready=true` for a primary arm, or has no shared blockers and an
individually ready capacity for a secondary arm:

```bash
trusted-synthesis train-vtdo-arm \
  --training-config config/vtdo_qwen2_5_7b_500k.json \
  --preflight <run>/training_preflight.json \
  --arm-manifest <run>/training_arms/arm_dataset_hashes.json \
  --arm B5_vtdo \
  --dataset <run>/training_arms/B5_vtdo.jsonl \
  --seed 20260731 \
  --output-dir <run>/models/B5_vtdo/seed_20260731
```

## Reproducibility And Safety

- Core code cannot import a concrete domain plugin or branch on a domain name.
- Universal and domain-specific quality gates remain separate and fail closed.
- Oracle content, gold evidence, and reference answers are excluded from public task inputs.
- External benchmark snapshots are evaluation-only and must match frozen SHA-256 values.
- FinQA predictions carry both answer and executable program contracts; TAT-QA predictions carry
  answer and scale. Prediction manifests bind the arm, training result, model/adapter contents,
  generation config, and evaluation snapshot.
- Exact/near prompt, evidence, source-record, document, and binding collisions block evaluation;
  unavailable required leakage channels also fail closed, while subject overlap is a soft
  diagnostic.
- API credentials are read from configured environment variables and are never serialized.
- Fixed-potential contraction is an update-operator verification, not a closed-loop convergence
  claim. Moving-potential behavior is evaluated through objective gain, tracking error, dynamic
  regret, state turnover, and finite-step practical stabilization.

See [VTDO Experiment Protocol](docs/vtdo_experiment_protocol.md),
[Valid Trajectory Distribution Optimization](docs/valid_trajectory_distribution_optimization.md),
[Current Project Status](docs/current_project_status.md),
[Finance v16 Numeric Contract Validation](docs/finance_v16_numeric_contract_validation_report.md),
[Generalization Contract](docs/generalization_contract.md), and
[Experiment Migration Audit](docs/vtdo_experiment_migration_audit.md).

## Removed Legacy Surface

The v0.8/v0.9 training-utility and validation implementations, configurations, tests, reports,
checkpoints, and generated artifacts have been permanently removed from the working tree. Tracked
source history remains available through Git; ignored generated outputs were intentionally deleted.
No compatibility alias maps a legacy schema or command into `vtdo_experiment.v6`.
