# Finance VTDO Phase 1 Initial Experiment Report

> This document preserves the single-task mechanism baseline. The population-level
> follow-up, reachability correction, and Contribution horizon falsification are
> reported in `finance_phase11_population_experiment_report.md`.

## 1. Executive conclusion

This experiment establishes a **partial but real** finance VTDO minimum loop:

~~~text
legacy public financial data
-> Omega compilation
-> multi-state quotient catalog
-> real DeepSeek exploration
-> real Qwen2.5-7B Contribution Probe
-> anchored distribution update
-> independently verified D1 materialization
~~~

The artifact and identity contracts pass, but the experiment itself remains
partial. The compiled state space satisfies the planned 100-task requirement,
while real unconditioned model exploration covers only one task and discovers
fewer than three accepted states. The result therefore validates the machinery
and one real feedback instance; it does not establish population-level VTDO
effectiveness.

## 2. Frozen experiment identity

| Item | Value |
| --- | --- |
| Experiment | finance_phase1_mvp.v1 |
| KG build | kg_20260711_062123_bc4b4394 |
| Data source | archived raw_financial_data_lake |
| Explorer | DeepSeek V4 Pro |
| Beneficiary | local Qwen2.5-7B-Instruct |
| GPU | A100-SXM4-80GB |
| Base-model manifest | base_model_content_manifest:4f4c5ef... |
| Input manifest | finance_phase1_input_manifest:b7fe345... |
| Artifact manifest | finance_phase1_artifact_manifest:372472... |

The input manifest freezes the archive configuration, multi-state artifacts,
Explorer outputs, beneficiary report, and all six Probe worker reports. The
artifact audit also re-hashed all 11 local base-model files and the LoRA Adapter.

## 3. Real financial substrate

The pinned archive contains:

- 913,475 KG nodes and 5,734,348 KG edges;
- 658,535 Fact nodes and 135,990 DerivedFact nodes;
- 6,272 execution-validated bindings across seven finance patterns;
- 98.12% source-grounding pass rate on 189,749 checked facts.

The capacity scan is intentionally marked partial. Its source pool contains SEC,
FRED, and World Bank records and is global-only. This is adequate for this
mechanism test but not a balanced production finance release. The old
corpus-disjoint capacity contract also reports shortfalls for derived growth and
registered-ratio cells; these do not invalidate the 100-task multi-state test.

## 4. Omega and compiled state space

The official v6 compilation chain accepted 100 of 105 attempted tasks:

| Metric | Result |
| --- | ---: |
| Accepted tasks | 100 |
| Tasks with at least three accepted states | 100 |
| Accepted states | 468 |
| States per task | min 3, mean 4.68, max 5 |
| Strategy attempts / verifier passes | 525 / 525 |
| Duplicate quotient states | 47 |
| Raw to quotient states | 1,356 -> 468 |
| Wrong-answer mutation rejection | 100 / 100 |
| Semantic false merges | 0 |

This answers Q1 at the **compiled and deterministically witnessed** level. It does
not by itself prove that a real Explorer naturally discovers the same support.

## 5. Real Explorer observations

### 5.1 Unconditioned Discovery

For one frozen task, DeepSeek V4 Pro generated ten independent replicas:

| Metric | Result |
| --- | ---: |
| Replicas | 10 |
| API calls / successful calls | 20 / 20 |
| JSON-contract success | 20 / 20 |
| Valid trajectories | 9 |
| Accepted states among valid trajectories | 1 |
| Tokens | 227,181 |

All nine valid replicas collapsed to compact_direct. This is strong evidence
that surface diversity is not trajectory-state diversity.

### 5.2 State-conditioned exploration

Two candidates were requested for each of three target states:

| Metric | Result |
| --- | ---: |
| Generated / valid / mapped | 6 / 6 / 6 |
| On-target | 4 |
| On-target rate | 66.67% |
| API calls / successful calls | 12 / 12 |
| Tokens | 173,792 |

The model reached compact_direct and broad_direct, but both attempts targeting
broad_full_lineage collapsed to broad_direct. Real accepted support therefore
contains two states, below the planned minimum of three.

The main Explorer experiment used 32 successful calls and 400,973 tokens. With
the two-call smoke test, total API use was 34 calls and 423,359 tokens.

## 6. Real Contribution Probe

The Probe uses disjoint data identities:

- four baseline-training tasks;
- two internal-validation tasks;
- two untouched final-test tasks;
- one target task with three state-conditioned update records.

The final-test records were not used for training, validation, contribution
estimation, selection, or D1 materialization. The artifact audit reports zero
final-test leakage.

The beneficiary LoRA run used four optimization steps:

| Metric | Result |
| --- | ---: |
| Runtime | 37.0 s |
| Peak allocated GPU memory | 54,553,558,528 bytes |
| Internal-validation NLL | 0.0654765 |
| Beneficiary checkpoint | qwen_beneficiary_checkpoint:4cb8b... |

Six cold-start Probe workers executed three AdamW steps each:

| State strategy | Seed gains | Mean gain | Standard error |
| --- | --- | ---: | ---: |
| compact_direct | 0.036528, 0.037493 | 0.037010 | 0.000482 |
| broad_direct | 0.038816, 0.038605 | 0.038710 | 0.000105 |
| broad_full_lineage | 0.037180, 0.038043 | 0.037612 | 0.000431 |

Aggregate worker runtime was 269.14 seconds; maximum allocated memory was
71,431,279,104 bytes. Every worker reproduced the frozen beneficiary metric and
Adapter tensor hash before adaptation.

These values demonstrate an executable C_hat -> Phi -> pi_next chain. They are
not a statistically stable contribution ranking: only one task and two seeds
were used.

## 7. Distribution update

The empirical prior uses nine valid unconditioned observations plus a uniform
coverage pseudo-count of strength one:

| State | pi0 | pi1 | Delta |
| --- | ---: | ---: | ---: |
| compact_direct | 0.93333 | 0.07809 | -0.85524 |
| broad_direct | 0.03333 | 0.46395 | +0.43061 |
| broad_full_lineage | 0.03333 | 0.45796 | +0.42462 |

Distribution diagnostics:

| Metric | Value |
| --- | ---: |
| Total variation | 0.85524 |
| KL(pi1 || pi0) | 2.22789 |
| JS(pi1, pi0) | 0.43357 |
| Entropy pi0 | 0.29114 |
| Entropy pi1 | 0.91309 |
| Accepted support | 3 -> 3 |

The update is a reallocation over fixed accepted support, not filtering.
broad_direct has the largest measured contribution and gains probability.
broad_full_lineage also gains heavily because it is novel despite having no
real on-target Explorer hit. This exposes the main uncertainty in the default
energy profile.

### 7.1 Energy sensitivity

| Profile | TV | KL | Next entropy |
| --- | ---: | ---: | ---: |
| Default | 0.8552 | 2.2279 | 0.9131 |
| Contribution-heavy | 0.6151 | 1.2426 | 1.0981 |
| History-heavy | 0.2886 | 0.3559 | 0.8969 |
| Conservative | 0.1511 | 0.1196 | 0.6750 |
| Higher novelty temperature | 0.8501 | 2.2021 | 0.9219 |

The default profile is explicitly marked production_ready=false. Production
hyperparameters must be selected with multi-task evidence and downstream
validation; this experiment must not be used to justify the default weights.

## 8. D1 materialization

Thirty independently regenerated deterministic trajectories were allocated from
pi1. Each was mapped back to its target quotient state and rerun through the
independent verifier.

| Metric | Result |
| --- | ---: |
| Released records | 30 / 30 |
| Allocation | 14 / 2 / 14 |
| Quota fill | 100% |
| State hit rate | 100% |
| Validity rate | 100% |
| End-to-end acceptance | 100% |
| Unique decision traces | 30 |
| TV to integer allocation | 0 |
| TV to source pi1 | 0.02462 |
| JS to source pi1 | 0.000847 |

During artifact auditing, D1 records were found to keep the pre-materialization
task artifact in their formal source_artifact_id, while the materialized identity
existed only in metadata. The record builder was fixed so every D1 record now
formally binds its own StateConditionedTrainingArtifact; a regression test covers
this contract.

This D1 validates controlled materialization and lineage. It does **not** validate
LLM state-conditioned materialization reliability.

## 9. Acceptance matrix

| Question / gate | Status | Scope |
| --- | --- | --- |
| Q1: more than one accepted state exists | Passed | 100 compiled tasks |
| Q1: at least three states observed from real model | Not passed | 1 real task, 2 states |
| Q2: pi0 changes to pi1 without support filtering | Passed | 1 Probe task |
| Q3: C_hat -> Phi -> pi1 executes | Passed | 1 Probe task |
| High-C/high-N states gain mass | Provisional | Default profile, 1 task |
| D1 distribution fidelity | Passed | Controlled 30-record materializer |
| Real LLM materialization | Not tested | Deferred |
| Student training / benchmark gain | Not tested | Excluded by Phase 1 plan |
| Artifact identity and isolation | Passed | Full local re-hash |

The correct overall status is therefore partial, not passed.

## 10. Reproducible artifacts

Primary directory:

~~~text
artifacts/vtdo_experiment/finance_phase1_mvp_v1/
~~~

Important files:

~~~text
finance_phase1_mvp_summary.json
artifact_integrity_audit.json
artifact_manifest.json
distribution_update/phase1_input_manifest.json
distribution_update/three_state_catalog.json
distribution_update/pi0_empirical_estimate.json
distribution_update/contribution_protocol.json
distribution_update/probe_observations.jsonl
distribution_update/contribution_manifest.json
distribution_update/anchored_distribution_update.json
distribution_update/energy_sensitivity.json
distribution_update/contribution_novelty_states.csv
distribution_update/contribution_novelty_states.svg
distribution_update/materialization_report.json
distribution_update/materialized_artifacts.jsonl
distribution_update/D1_materialized_training_records.jsonl
~~~

The full integrity audit passed with report hash:

~~~text
finance_phase1_artifact_integrity_audit:
f04a9cde43d6924e146e20a6ced70f8635ca06a8ca4cd56ee4ebcd35b4408c4b
~~~

## 11. Required next gate

Before claiming that VTDO optimizes real Explorer behavior:

1. run unconditioned Discovery on a stratified 10-20 task pilot before the
   planned 100 x 10 grid;
2. require at least three real accepted states on enough tasks to estimate a
   non-degenerate push-forward distribution;
3. improve broad_full_lineage state conditioning and report off-target
   transitions rather than treating fixture support as observed support;
4. estimate Contribution on multiple tasks and at least three seeds, with
   confidence-aware energy;
5. select a conservative energy configuration before materialization;
6. run a small real LLM materializer test;
7. only then proceed to Student training and external benchmarks.

This sequence preserves the Phase 1 claim: the current result proves a working,
auditable minimum mechanism, while the empirical generality claim remains open.
