# v0.9 Clause-Guided Local Synthesis Refinement

## Scope

v0.9 implements **Calibrated Clause-Guided Refinement (CCGR)**: root failures observed under a
sample-specific Quality Contract update a finite synthesis policy without changing the framework,
task language, operator set, or model strategy. Finance remains the reference implementation;
Legal and Science remain mandatory contract domains.

The initial build is a control-plane and offline-contract milestone. It does not report a trained
model improvement, a real-Agent Round-0 distribution, or an external benchmark result.

## Host-Instrumented Student Protocol

Teacher generation, student SFT, and student evaluation now share one interaction contract:

```text
System
User: public task + evidence + public operation contract
Assistant: AgentActionPlanContract
Tool: HostExecutionFeedbackContract
Assistant: AgentAnswerDecisionContract
```

Only the two Assistant turns contribute to SFT loss. Execution IDs, observations, immutable source
locators, operation results, and lineage are Host-owned Tool content. The Tool contract retains a
raw result for audit and a model-visible result whose internal execution references are replaced by
stable public step IDs; neither field is an Assistant target. Evaluation generates the Action Plan
first, executes it through the domain registry, then generates the Answer Decision.
The model is scored on Evidence selection, operator/input/parameter decisions, answer correctness,
and citations. `host_replay_available` and `execution_replay_valid` are execution metrics, not
self-verification claims.

For the current controlled tasks, selected, used, and cited Evidence must match exactly. That
assumption is intentionally retained in v0.9 and must not be generalized to open research tasks.

## Failed Action Lifecycle

Host action failures are serialized as `FailedActionPlan` with the failed step, operator, selected
Evidence, parameters, error code, category, and attempted Action Plan. Contract repair may still
recover a later attempt, but both recovered and exhausted semantic failures remain observable.

The Feedback Router assigns one owner:

| Route | Examples | Action |
| --- | --- | --- |
| Interface failure | invalid JSON, unknown Evidence ID, unregistered tool, provider failure | repair adapter, prompt, or runtime |
| Upstream data defect | source/version/definition/binding defects | suppress the cell and optionally tighten a declared binding constraint |
| Agent capability gap | wrong allowed Evidence, operator, parameter, dependency, answer, or citation | increase clean training demand |

Interface failures have zero synthesis utility. The other two routes update the policy in opposite
directions; this distinction prevents invalid data from being amplified as training demand.

## CCGR Optimization Space

The optimized variable is a distribution over auditable Synthesis Cells:

```text
a = (pattern, evidence_binding_stratum, difficulty_bucket, distractor_profile)
pi_t(a) = probability of sampling cell a in round t
```

Binding strata and distractor profiles are structural hashes. Core may inspect Evidence kind,
authority, definition coverage, temporal/scope cardinality, and equality relations to required
Evidence, but it does not interpret domain-specific values. Domain plugins may expose safe
tightening candidates through a refinement contract.

## Counterfactual Clause Calibration

Typed counterfactual results produce one reliability value per root Clause kind:

```text
kappa_c = geometric_mean(
    mutation_validity_rate,
    detection_rate,
    root_cause_f1,
    failure_closure_f1,
)
omega_c = severity_weight_c * kappa_c
```

Calibration is keyed by the expected root Clause kind, not merely the mutated source Clause. A
Clause absent from the calibration manifest receives the configured fail-closed reliability floor,
which is zero in the frozen v0.9 contract. Raw Failure Reweighting sets `kappa=1` only as an
ablation.

## Calibrated Cell Statistics

Every evaluated task contributes one exposure to its Synthesis Cell. Only independently localized
root failures contribute directional mass:

```text
D_t(a) = calibrated synthesis-defect weight / exposed samples in a
G_t(a) = calibrated capability-gap weight / exposed samples in a
U_t(a) = max(0, target_share(a) - observed_share(a))
```

The legacy Pattern x Clause lambda allocator remains serialized as an engineering baseline, but it
is not the v0.9 optimization algorithm.

## Policy Update

Full CCGR solves a KL-regularized objective and uses its closed-form exponentiated update:

```text
pi_next(a) = pi_t(a) * exp(eta * (G_t(a) - beta * D_t(a) + gamma * U_t(a)))
             ------------------------------------------------------------------
             sum_a' pi_t(a') * exp(eta * (G_t(a') - beta * D_t(a') + gamma * U_t(a')))
```

The update manifest freezes the prior and next policy, calibrated Clause feedback, `D/G/U`, utility
per cell, KL divergence, total-variation shift, entropy, effective cell count, and deterministic
largest-remainder budget allocation. A binding constraint can only be activated when the relevant
Clause or failure family maps to a predeclared option and the calibrated defect risk exceeds the
threshold. CCGR cannot invent a new rule.

## Algorithm Ablations

The same update engine materializes six frozen comparisons:

| Ablation | Change |
| --- | --- |
| Static Verified | `eta=0` |
| Raw Failure Reweighting | `kappa=1` |
| No Defect Suppression | `beta=0` |
| No Coverage Regularization | `gamma=0` |
| Random Same Shift | deterministic random utilities matched to Full CCGR TV distance |
| Full CCGR | calibrated `G - beta D + gamma U` |

All variants preserve the same sample budget. Random Same Shift isolates whether gains come from the
feedback direction rather than merely perturbing the distribution.

## Causal Cohorts

| Cohort | Evidence | Proof Graph | Executable Program | Quality Contract | Feedback allocation |
| --- | --- | --- | --- | --- | --- |
| C1 Conventional Synthetic | no grounding requirement | no | no | no | no |
| C2 Evidence-Grounded | yes | no | no | no | no |
| C3 Verified Static | yes | yes | yes | yes | no |
| C4 Feedback-Refined Verified | yes | yes | yes | yes | yes |

C1-C4 freeze the same Qwen2.5-7B base model, Host-Instrumented training format, supervised Assistant
token budget, training seed, Pattern Catalog hash, and Finance/Legal/Science distribution. The
Qwen revision is content-addressed in the cohort contract. C4 may differ from C3 only in the
allocation derived from calibrated, direction-aware feedback. D1-D5 remain engineering regression
cohorts rather than the main causal labels.

## Online Gate

The real DeepSeek Round-0 run remains mandatory before GPU training:

```text
attempted tasks                         = 100%
Action Plan contract success            >= 90%
Host execution evaluable                >= 90%
Answer Decision contract success        >= 90%
complete Contract acceptance            >= 60%
accepted Finance, Legal, and Science     all present
accepted major Patterns                  all present
resume calls for completed tasks         = 0
```

First-call and repair-assisted successes are reported separately. A failed online gate blocks the
training experiment rather than being replaced by offline counterfactual evidence.
Incomplete runs persist stage-level progress, so Action-contract success, Host evaluability, and
Answer-contract success are aggregated from explicit fields rather than inferred from error text.

## Initial Offline Build

Run the contract-only MVP with:

```bash
trusted-synthesis build-v09-initial \
  --v09-config config/training_utility_v09_initial.json \
  --tasks-per-domain 3 \
  --output-dir artifacts/training_utility_v09/v09_initial
```

The command compiles Proof-Carrying Samples and Quality Contracts in all three domains, generates
typed one-factor counterfactuals, independently evaluates root failure closure, calibrates and
routes the resulting feedback, and materializes both legacy lambda baselines and six CCGR
ablations. It writes:

```text
v09_initial_build_report.json
v09_initial_build_report.md
v09_refinement_manifest.json
feedback_exposures.jsonl
feedback_signals.jsonl
synthesis_cells.jsonl
clause_feedback.jsonl
ccgr_policy_updates.json
```

The report must retain `round0_real_agent_feedback=false`, `online_gate.status=not_run`, and
`external_benchmark_status=not_executed`. Passing this build proves that the feedback machinery is
executable and cross-domain; it does not prove that C4 improves Qwen, that real Agent failures have
the same distribution, or that native external tasks improve.

## Next Experimental Step

After a clean release validation, run the 30-task Host-Instrumented online gate together with pinned
counterfactual calibration reports. If it passes, use real routed roots to materialize C4, build
equal-budget C1-C4 datasets, train one pilot seed, and evaluate internal contracts before scaling to
three seeds and native external benchmarks. A passed offline build validates Algorithm 1 execution;
it still does not establish training utility.

## Real-Training Pilot Commands

An operator may train the offline-calibrated data only as an explicitly labeled engineering pilot.
It must retain `causal_status=offline_pilot_only`; its C4-C3 delta cannot be reported as the causal
effect of real-agent feedback. Materialize and audit the frozen datasets before allocating GPUs:

```bash
trusted-synthesis prepare-v09-training \
  --v09-config config/training_utility_v09_initial.json \
  --training-config config/training_utility_v09_qwen2_5_7b.json \
  --refinement-manifest artifacts/training_utility_v09/v09_ccgr_full_catalog_20260729/v09_refinement_manifest.json \
  --agent-artifacts artifacts/agent_validation/v08_production_v6_20260727 \
  --output-dir artifacts/training_utility_v09/v09_training_pilot_20260729 \
  --allow-offline-refinement-pilot

trusted-synthesis audit-training-token-budget \
  --training-config config/training_utility_v09_qwen2_5_7b.json \
  --cohort C1_conventional_synthetic \
  --dataset artifacts/training_utility_v09/v09_training_pilot_20260729/C1_conventional_synthetic.jsonl
```

Run the token audit for C1 through C4. Every audit must be `ready`, have zero truncation, remain
under `max_steps`, and stay within the frozen supervised-token deviation. Train each cohort from the
same base snapshot on an isolated GPU:

```bash
CUDA_VISIBLE_DEVICES=0 trusted-synthesis train-training-utility \
  --training-config config/training_utility_v09_qwen2_5_7b.json \
  --cohort C1_conventional_synthetic \
  --dataset artifacts/training_utility_v09/v09_training_pilot_20260729/C1_conventional_synthetic.jsonl \
  --output-dir artifacts/training_utility_v09/v09_real_training/C1
```

After training, evaluate the base model and every adapter against the same `evaluation.jsonl`, then
use `summarize-v09-training` to enforce dataset hashes and produce the C1-C4 comparison. The report
records the C4-C3 delta but marks it `not_identified` until a successful Host-Instrumented online
Round-0 rebuild supplies real feedback.
