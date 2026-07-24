# Financial QA Quality Evaluation System

## 1. Purpose

The quality system evaluates an immutable QA build without weakening any existing
deterministic gate. It separates five questions that must not be collapsed into a
single score:

1. Is the item deterministically correct and traceable?
2. Is its structure useful to the dataset?
3. Is the question authentic, clear, and financially meaningful?
4. How difficult and discriminative is it empirically?
5. Does training on it improve downstream financial search and reasoning?

The implemented system covers L0-L3. L4 training-utility experiments remain an
explicit later phase.

```text
Pinned QA Build
  -> L0 deterministic validity (hard veto)
  -> L1 release-contract gap and dataset role
  -> L2 Surface + Grounded financial judges
  -> disagreement / fatal routing
  -> Risk Router and calibrated decision
  -> quality-aware release
  -> L3 four-mode empirical evaluation
  -> reproducible slice report
```

Subjective scores are advisory until a human calibration set freezes thresholds.
They do not alter `qa_samples.validation_status` or activate a QA build.

## 2. Evaluation identity

Each `qa_evaluation_runs` row pins:

- `qa_build_id`;
- rubric version and hash;
- redacted evaluation configuration hash;
- judge manifest and hash;
- exact sample manifest and hash;
- calibration version;
- Git commit and evaluation mode.

The sample manifest stores both `qa_id` and `stable_qa_id`, making a report
replayable even when a later QA build becomes active.

## 3. L0 deterministic veto

The evaluator reads existing deterministic results instead of asking an LLM to
recheck arithmetic. An item fails L0 when any of these conditions applies:

- `qa_samples.validation_status != passed`;
- its candidate is not eligible;
- any persisted `qa_quality_checks` row is not passed.

An L0 failure produces `rejected_deterministic`. No judge is called and no LLM
score can override the result.

## 4. L1 dataset role value

`dataset_role_value_score` is programmatic and distinct from item-level
financial value. Version `qa_dataset_role.v2` no longer rewards rarity inside
the evaluated batch. It measures the remaining deficit against a pinned Release
Contract and, when configured, a FinSearchComp Gap Manifest.

The default contract freezes:

- the official T2/T3 x Global/Greater China target distribution;
- a market-language distribution that prevents language from determining market;
- target shares for Fact, DerivedFact, Static Pattern, Automatic Mining, and
  Typed Edge Walk pipelines;
- optional absolute gap targets;
- surface-signature and operation-program capacity limits.

Only `train` and `train_complex` participate in training-distribution
counts. `dev`, `test`, and every holdout split receive a Dataset Role
score of zero and cannot become `accepted_for_coverage`. Quality evaluation
can still accept those items as evaluation samples, but release selection and
SFT export must preserve their holdout role.

Question identity uses the existing protected question or template identity,
the Contamination Guard slot-normalized signature, and the normalized Operation
Program signature. Entity substitution, year substitution, or light paraphrase
therefore does not manufacture a new rare skeleton. Signature capacity only
penalizes saturation; it does not treat a singleton as inherently valuable.

The resolved contract and its hash are pinned in every evaluation run. This score
cannot rescue an invalid financial question or a confirmed fatal defect.

## 4.1 Regional contracts and language identity

An evaluation run still pins one `qa_build_id`, so Dataset Role V2.1 resolves the
contract from the build's actual market pool:

- Global: T2 119/203, T3 84/203; English 80%, Chinese 15%, mixed 5%;
- Greater China: T2 100/188, T3 88/188; Chinese 65%, English 20%, mixed 15%;
- Combined: the four official market-task cells and both market-language grids.

The resolved contract and hash are immutable run metadata. `bilingual`,
`mixed-language`, `zh_en`, and `en_zh` are canonicalized to `mixed` before both
scoring and release selection. A future multi-build evaluation run can use the
Combined contract without changing these cell semantics.

## 5. L2 judge views

### Surface Financial Analyst

Receives only the user-facing question, task, language, answer type, and a
sanitized output contract. It does not receive answers, candidate scores,
generation pipeline, internal IDs, or current quality status.

### Grounded QA Auditor

Receives a sanitized semantic summary, operation names, answer schema, source
authority classes, evidence counts, and scope-completeness summary. Gold answer
values and raw Fact/KG IDs remain hidden.

### Adversarial Reviewer

Runs only for disagreement, low confidence, disputed fatal flags, or boundary
items. It searches for ambiguity, gratuitous complexity, weak follow-up logic,
and evidence/scope mismatch.

## 6. Rubric and decisions

T2 and T3 use eight 1-5 dimensions, but roles do not vote on dimensions they
cannot observe. Surface owns task authenticity, standalone financial value,
clarity, and language quality. Grounded owns financial semantics, reasoning
necessity, evidence/scope fit, and answer/rubric fit. Their owned dimensions form
the provisional score.

The Adversarial Reviewer is not a third ordinary voter. It receives only routed
dimensions and returns uphold, downgrade, fatal, or escalate resolutions. The
final item records base dimensions and score, the threshold-only base decision,
all adversarial resolutions, final dimensions and score, final decision, and
score delta.

T2 weights precision, historical scope, and verifiability more heavily. T3 gives
more weight to financial value, necessary multi-step reasoning, and scope fit.
Confidence, fatal flags, routing reasons, and adjudication state remain separate
from the numeric score.

Initial advisory decisions are:

```text
L0 failure                     -> rejected_deterministic
confirmed fatal defect         -> rejected_subjective_fatal
score >= 80, low disagreement  -> accepted
score >= 70 + contract gap
  + training-eligible split      -> accepted_for_coverage
score 60-80                    -> manual_review
pending adversarial challenge  -> manual_review
unresolved human-routed dispute -> manual_review
unresolved LLM-only dispute     -> quarantined_judge_disagreement
score < 60                     -> rejected_subjective_quality
```

These thresholds are not a release gate until calibration records
`thresholds_are_calibrated=true`.

The Risk Router records `no_dispute`, `adversarial_challenge_pending`,
`adversarial_challenge_resolved`, `human_review_required`, or
`quarantined_judge_disagreement`. Judge non-consensus is never relabeled as a
quality defect.

## 7. L2 diagnostic reporting

Each report separates issue evidence into:

- per-role Surface, Grounded, and Adversarial counts;
- samples flagged by any judge;
- samples flagged by at least two roles;
- issues confirmed by a structured Adversarial resolution.

Legacy Adversarial calls without a resolution contract are not reported as
confirmed adjudication. Unresolved items are classified by total-score
disagreement, same-dimension disagreement for legacy runs, low confidence, fatal
disagreement, missing dimensions, pending adjudicator, resolution-contract
errors, escalation, and multiple reasons.

Reports also compare base and final scores and decisions, summarize resolution
actions and transitions, and expose task-subtype slices. Every rate includes a
95% Wilson interval. Slices below the configured minimum, 30 by default, are
marked insufficient_slice_size and are descriptive only.

## 8. Persistence

The QA layer now includes:

- `qa_evaluation_runs`;
- `qa_judge_calls`;
- `qa_evaluation_items`;
- `qa_human_reviews`;
- `qa_perturbation_cases`;
- `qa_quality_releases`;
- `qa_quality_release_members`.

Judge calls persist requested and actual model, prompt/input/response hashes,
structured scores, defects, confidence, latency/token/cost telemetry, fallback
state, and failures. API keys are never stored.

## 8. Commands

```bash
python -m finraw.cli --config config/profiles/prod_qa_quality_advisory.json \
  qa-quality-init --qa-build-id qa_build_xxx --limit 1000

python -m finraw.cli --config config/profiles/prod_qa_quality_advisory.json \
  qa-quality-evaluate --evaluation-run-id qaeval_xxx

python -m finraw.cli --config config/profiles/prod_qa_quality_advisory.json \
  qa-quality-adjudicate --evaluation-run-id qaeval_xxx

python -m finraw.cli --config config/profiles/prod_qa_quality_advisory.json \
  qa-quality-review-export --evaluation-run-id qaeval_xxx

python -m finraw.cli --config config/profiles/prod_qa_quality_advisory.json \
  qa-quality-report --evaluation-run-id qaeval_xxx
```

Set `DEEPSEEK_API_KEY` in the process environment. The profile can discover and
record a replacement model when the requested model is unavailable or exhausted.

## 9. Report artifacts

An evaluation report writes:

- `qa_quality_evaluation_report.json`;
- `qa_quality_evaluation_report.md`;
- `qa_evaluation_items.jsonl`;
- `judge_disagreement.jsonl`;
- `judge_disagreement_quarantine.jsonl`;
- `manual_review_queue.jsonl`;
- `qa_generation_issue_feedback.json`;
- `qa_generation_issue_hotspots.csv`.

Slice metrics are reported by benchmark task, market, language, difficulty,
generation pipeline, operation family, answer type, and topic. Each slice includes
sample count, L0 pass rate, subjective mean/P10/P50/P90, fatal rate, review rate,
judge disagreement rate, and dataset-role value.

## 9.1 Generation feedback loop

Successful judge calls are attributed to the generation components that produced
each sample. The feedback cube is keyed by:

```text
Issue Code x Template ID x Pattern ID x Operation Macro
           x Metric Pair x Generation Pipeline x Language
```

Every row reports the component population, samples flagged by any judge,
samples flagged by at least two roles, adversarially confirmed samples, and the
affected rate within that exact component slice. One-dimensional hotspots also
identify a bad template, metric pair, macro, pipeline, or language when the full
cube is sparse.

Issues are routed to an owning module. Formulaic instructions go to the output
contract and verbalizer, awkward periods to the period verbalizer, unclear scopes
to the scope description builder, weak metric pairs to the ontology and Pattern
Gate, and weak follow-ups to static patterns or Walk Macros. `overly_trivial`
changes sampling quota, while `low_standalone_value` changes Pattern Value and
dataset selection. These are quality optimization signals, not deterministic
correctness failures.

## 10. Quality-aware release

`qa-quality-release` selects only `accepted` or `accepted_for_coverage` samples
from `train` and `train_complex`. It independently rechecks the immutable sample
manifest, deterministic status, Dataset Role eligibility, subjective threshold,
and confirmed fatal flags.

Selection V2 is quota constrained rather than a global Top-N. It converts every
hard target distribution to deterministic integer counts using largest
remainders, then fills scarce task-language-pipeline intersections before using
quality score as the tie-breaker. The release report records target, eligible,
selected, and unmet counts for every cell. It also requires at least 1.3 eligible
Typed Walk candidates per selected Typed Walk slot by default. A quota or supply
shortfall produces `draft_partial` in advisory mode or `partial` in a calibrated
release gate; imbalance is never silently published.

The current pilot pipeline contract is Fact 30%, Derived 25%, Static Pattern 25%,
Automatic Mining 15%, and Typed Walk 5%. The 5% Walk target should only be raised
when its candidate supply repeatedly clears the configured buffer.

```bash
python -m finraw.cli --config CONFIG qa-quality-release \
  --evaluation-run-id qaeval_xxx \
  --target-size 1000 \
  --output-dir data/audit/qa_quality/release
```

## 11. Calibration and later phases

Before `release_gate` mode is allowed to block publication:

1. Blind-review at least 200-300 stratified items with two human reviewers.
2. Add at least 100 controlled defect and invariance pairs.
3. Measure Spearman correlation, weighted kappa, fatal recall/precision, and
   pairwise preference accuracy by language, market, T2/T3, pipeline, and
   difficulty.
4. Freeze calibrated thresholds and judge manifests.
5. Run equal-size training ablations to verify that Quality + Coverage selection
   outperforms L0-only and random selection.

Correctness determines whether an item may be evaluated. Financial quality
determines whether it is worth training on. Dataset role determines whether it
should be selected. Downstream utility determines whether the quality policy is
actually credible.


## Temporary LLM-only review policy

Human calibration can be temporarily disabled with
`calibration.replacement_mode=llm_secondary_review`. In that mode every L0/L1
passing item is scored by the two pinned L2 DeepSeek-V4-Pro roles and then
reviewed by a separately prompted adversarial DeepSeek-V4-Pro role. Pro has no
Flash fallback: an unavailable Pro call is recorded as a failed call.

This is a provisional operational replacement, not evidence of human-judge
agreement. Items that remain disputed after the adversarial pass are marked
`quarantined_judge_disagreement`. Quarantine is a routing outcome, not a
subjective-quality rejection, and such items cannot enter a quality release.

## L3 empirical model trials

L3 uses four separate, pinned run modes. One empirical run evaluates exactly one
mode so the same model and QA item cannot leak information between modes:

| Mode | Input | Primary capability |
| --- | --- | --- |
| gold_plan_given | Evidence + Gold Operation Plan | Plan execution and output compliance |
| evidence_only | Evidence only | Independent reasoning-program formation |
| evidence_pool | Relevant evidence + distractors | Evidence selection and calculation |
| retrieval_tool | Question + registered tools | Retrieval, tool use, evidence selection, and calculation |

retrieval_tool exposes only registered entity, metric, pinned-fact, and
calculator tools. It must execute at least one tool call; a direct unsupported
answer fails the end-to-end gate. Mode C and D also require an exact
selected_evidence_ids set. Mode A and B store evidence selection as not
applicable rather than awarding an artificial pass.

Each Trial persists:

    api_call_success
    json_contract_success
    semantic_answer_correct
    unit_currency_correct
    row_completeness
    order_correct
    evidence_selection_correct
    end_to_end_correct

Every overall, model, and slice report fixes the following denominators:

    contract_success_rate
    = valid JSON answer contracts / all trials

    semantic_accuracy_given_valid_contract
    = semantically correct answers / valid JSON contracts

    end_to_end_accuracy
    = fully correct trials / all trials

DeepSeek-V4-Pro and DeepSeek-V4-Flash answer independently. Neither model judges
the other; the shared Answer Schema Registry, Gold answer, and Rubric perform
deterministic scoring.

    python -m finraw.cli --config config/profiles/prod_qa_quality_advisory.json \
      qa-quality-empirical \
      --qa-build-id QA_BUILD_GLOBAL \
      --qa-build-id QA_BUILD_GREATER_CHINA \
      --mode evidence_pool \
      --limit 100 \
      --output-dir data/audit/qa_quality/l3_evidence_pool

Run the command once per mode to compare the capability gaps. The API credential
is read only from DEEPSEEK_API_KEY; it is never persisted in run manifests,
trial telemetry, or reports.
