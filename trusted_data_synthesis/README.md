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
python -m pip install -e ".[dev,finance,online,training]"
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

## Finance QA vNext Public-Decision Entry

The versioned domain entry connects one Catalog and Registry to source-bound tasks,
callback-owned typed Action/Update/Final submissions, the common Runtime, independent QA
and trajectory validation, and actual dependency-graph depth/finite comparison:

```bash
trusted-synthesis finance-qa-vnext \
  --repo-root .. \
  --output-dir /tmp/finance-qa-vnext-example
```

The output directory must not exist. The default requests all eleven registered families
over existing frozen sources: seven Pattern cases and two Share fixture sessions execute;
three unsupported-source families remain explicit uninstantiated rows. This is an offline
integration regression, not new model coverage or a training release. The older `finance-pilot`
remains a deterministic execution-trace workflow. See the detailed
[source-audit revisions and protocol boundaries](docs/finance_qa_vnext_unified_entry_source_audit_revisions.md).

The explicitly online companion is `finance-qa-vnext-model {prepare,run,analyze}`
(Python 3.11+; executed here with 3.12.13). `prepare` makes zero network calls; `run`
reads the existing `trusted_data_synthesis/.env` from the repository root and executes a
single, non-replaceable three-task/twelve-session population; `analyze` is read-only and
makes no Provider calls. The completed 2026-09-06 population has C/B/Share success counts
1/4, 0/4, 0/4, 374 requests, and three original supervision candidates with validated token
masks. It does not establish broad task completion, quotient weights or Student benefit.
Do not rerun its existing execution directory. See the [frozen conditions, real results and
Update presentation gap](docs/finance_qa_vnext_representative_model_execution_and_export.md).

The subsequent Update repair uses
`python -m trusted_synthesis.experiments.finance_qa_vnext_update_calibration.runner {prepare,run,analyze}`.
Its fixed 24-call paired calibration completed with original presentation O 0/12 and repaired
presentation R 12/12, without Action execution, Update commits or new full sessions. The old
1/12 outcome is unchanged. See the [public-contract repair, frozen design and bounded results](docs/finance_qa_vnext_update_public_contract_calibration.md).

The separately authorized six-full-session follow-up uses
`python -m trusted_synthesis.experiments.finance_qa_vnext_repaired_full_task {prepare,run,analyze}`.
It completed two fresh C/B/S rounds with neutral full-task instructions: C 2/2, B 0/2,
S 2/2, 116 actual Provider calls, 13/13 first-Update accepts and 20 eligible original-response
Token candidates. B remains blocked on Action candidate-set enumeration, not Update acceptance.
The previous twelve-session and 24-call results remain separate; no post-pilot calls or training.
See the [six-session design and execution record](docs/finance_qa_vnext_repaired_update_six_session_full_task.md).

The next bounded entry is
`python -m trusted_synthesis.experiments.finance_qa_vnext_action_branch {prepare,run,analyze}`.
It completed two fresh B sessions under published Action full-set/selected-offer rules:
2/2 Qualified, 34 actual Provider calls, 16/16 first-Update commits, semantic depth 3,
and no rejection. Original admission, Update and Final standards are unchanged. Of 34 raw
supervision candidates, 32 fit the Token limit; two overlength Updates remain untruncated.
No C/S repeat, cross-condition success pooling or Student training occurred.
See the [Action contract repair and original B reachability report](docs/finance_qa_vnext_action_public_contract_branch_reachability.md).

The original-content representation follow-up uses
`python -m trusted_synthesis.experiments.finance_qa_vnext_length_adaptation {prepare,run,verify}`.
Completed under source `7ad17013`: all 34 existing B candidates are consumable under one
separately frozen 32,768 policy, yielding two complete 17-unit packages including both T16
Updates. Eighteen small CPU batches, 27 tests and 21 local controls pass. The old 24,576
binding and 32-fit/2-not-fit result remain immutable, with zero new Provider, Runtime,
Student or GPU execution. GPU training feasibility is not claimed.
See the [full-trajectory representation adaptation results](docs/finance_qa_vnext_full_trajectory_length_adaptation.md).

The fixed-panel collection entry is
`python -m trusted_synthesis.experiments.finance_qa_vnext_task_panel {prepare,run,analyze}`.
Completed under source `555a7610`: 15/16 Qualified across eight existing tasks, 152 actual
calls, 113/113 fit positive candidates and 15 complete CPU packages. S01 is a retained
known failure; D01/B01/S02 are valid but projection-undetermined, so D/B/S conditional
frequencies remain null. Five supported pairs are equivalent. No replacement, training
or cross-condition pooling occurred; three uninstantiated types remain visible. See the
[eight-task panel design and actual results](docs/finance_qa_vnext_fixed_task_panel_collection.md).

The additive, correction-aware measurement entry is
`python -m trusted_synthesis.experiments.finance_qa_vnext_panel_quotient {prepare,run}`.
It uses only those frozen sixteen sessions, preserving qualification and all original
candidate/Token bytes. The new rule interprets D01/B01/S02 without clearing their ledgers,
retains S02's rejected ratio proposal → actual sum/Claim → disclosed-total ratio relation,
and separates fixed-denominator success from conditional class frequencies. Completed
under source `dd2df2a4`: 15 Assignments, seven equivalent pairs (five reused, two new),
and one observed class per task. S remains 1/2 successful despite conditional π=1/1;
overall success stays 15/16. All 102 tests and 24 direct controls pass; new execution
and tokenization remain zero. No class-reallocation freedom or Student benefit is claimed.
See the [finite correction-history rules and measurement record](docs/finance_qa_vnext_panel_correction_aware_quotient.md).

The next bounded support-exploration entry is
`python -m trusted_synthesis.experiments.finance_qa_vnext_support_exploration {prepare,run}`.
It preregisters four neutral and four soft-guided fresh sessions on the same Share Task,
in four fixed N/E waves with at most two parallel sessions and 256 Provider attempts.
Prompt preference does not change legal actions or qualification; actual denominator
production and Claim consumption, not profile names, establish the target support witness.
Completed under source `a6a2c2c7`: 202 calls, N 1/4 and E 2/4 successful; actual qualified
support is reconstructed Claim twice and disclosed Evidence once. The two reconstructed
correction histories remain outside the frozen quotient rule, so only one Assignment is
available, complete π stays null and the strict paired `W_support` is not established.
All 21 original positive records fit into three complete packages with E prompts retained;
63 new tests pass, with no replacement, historical rewrites or Student/GPU execution.
See the [stratified same-task support exploration design and record](docs/finance_qa_vnext_same_task_support_exploration.md).

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
