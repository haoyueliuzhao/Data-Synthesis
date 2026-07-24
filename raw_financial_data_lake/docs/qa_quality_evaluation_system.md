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

The implemented first phase covers L0-L2. L3 empirical model trials and L4
training-utility experiments remain explicit later phases.

```text
Pinned QA Build
  -> L0 deterministic validity (hard veto)
  -> L1 structure, coverage, rarity, and dataset role
  -> L2 Surface + Grounded financial judges
  -> disagreement / fatal routing
  -> advisory decision and human review queue
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

`dataset_role_value_score` is programmatic and distinct from item-level financial
value. It combines rarity or coverage contribution across:

- T2/T3 x market x language cell;
- operation x answer type;
- source class x metric family;
- advanced automatic pipeline use;
- holdout role;
- graph-pattern coverage;
- question-skeleton coverage.

This score can preserve a rare but sound item. It cannot rescue an invalid
financial question or a confirmed fatal defect.

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

Both T2 and T3 use eight 1-5 dimensions:

- task authenticity;
- standalone financial value;
- financial semantic validity;
- clarity and unambiguity;
- reasoning necessity;
- evidence/scope fit;
- answer/rubric fit;
- language quality.

T2 weights precision, historical scope, and verifiability more heavily. T3 gives
more weight to financial value, necessary multi-step reasoning, and scope fit.
Scores are aggregated by dimension median and normalized to 0-100. Judge
disagreement, confidence, and fatal-flag disagreement remain separate fields.

Initial advisory decisions are:

```text
L0 failure                     -> rejected_deterministic
confirmed fatal defect         -> rejected_subjective_fatal
score >= 80, low disagreement  -> accepted
score >= 70 + rare coverage    -> accepted_for_coverage
score 60-80 or disagreement    -> manual_review
score < 60                     -> rejected_subjective_quality
```

These thresholds are not a release gate until calibration records
`thresholds_are_calibrated=true`.

## 7. Persistence

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
- `manual_review_queue.jsonl`.

Slice metrics are reported by benchmark task, market, language, difficulty,
generation pipeline, operation family, answer type, and topic. Each slice includes
sample count, L0 pass rate, subjective mean/P10/P50/P90, fatal rate, review rate,
judge disagreement rate, and dataset-role value.

## 10. Calibration and later phases

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
`rejected_llm_review_unresolved` rather than silently accepted.

## L3 empirical model trials

`qa-quality-empirical` sends a stratified numeric sample to both pinned
respondent models under the same evidence-given contract. DeepSeek-V4-Pro and
DeepSeek-V4-Flash answer independently. Neither model judges the other; Gold
and Rubric perform deterministic numeric, unit, currency, and tolerance checks.

```bash
python -m finraw.cli --config config/profiles/prod_qa_quality_advisory.json \
  qa-quality-empirical \
  --qa-build-id QA_BUILD_GLOBAL \
  --qa-build-id QA_BUILD_GREATER_CHINA \
  --limit 12 \
  --output-dir data/audit/qa_quality/deepseek_l3_smoke
```

The API credential is read only from `DEEPSEEK_API_KEY`; it is never persisted
in run manifests, trial telemetry, or reports.
