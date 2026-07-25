# QA 3000 Review Remediation

## Scope

This remediation addresses the review of commit `a953dbec05b6774a4271f6138cdd6691e1af1bc3`. It changes the next-build generation and L3 evaluation contracts. It does not relabel the historical 3,000 questions as a quality-approved training release.

## Release audit correction

The pinned release `qa3000_dc734a635439cc83` is now explicitly classified as an `l0_passed_diagnostic` release. Item-level L2 rows were joined back to the exact 3,000 QA IDs instead of copying aggregate statistics from the 3,217-item candidate pool.

Exact release results:

| Measure | Count |
| --- | ---: |
| Pinned QA | 3,000 |
| L0 passed | 3,000 |
| L2 accepted | 2,038 |
| Manual review | 849 |
| Rejected subjective fatal | 75 |
| Rejected subjective quality | 38 |
| Training approved after split and role eligibility | 673 |
| Diagnostic only | 2,327 |

The regenerated immutable audit is under `data/audit/qa_3000_final_v3_exact_audit/`.

## Output-contract remediation

The output contract remains deterministic and answer-type aware, but user-visible requirements are now separated from matcher metadata.

- Numeric unit requirements remain visible when financially necessary.
- Decimal precision is deterministically visible for only a configured share of questions; the next profiles use 35%.
- Ranking, screening, follow-up and provenance tasks use distinct natural instructions.
- Repetitive phrases such as “complete table” and “do not omit rows” are no longer universal suffixes.
- Internal IDs, schema fields, Scope hashes and operation parameters remain hidden in the rubric.

## Scope contract

Scope is now represented by a versioned structure containing:

- display name;
- source;
- effective date;
- membership rule;
- data-eligibility rule;
- entity count and exact member IDs;
- membership hash;
- whether membership is authoritative.

Static Scope Matchers and compiled Scope bindings emit the same contract. Public wording explicitly describes non-authoritative scopes as complete-case dataset universes, preventing available-data samples from being presented as full authoritative industries. English and Chinese renderers use the same frozen contract.

## Typed Walk answer contract

`filtered_rank_followup` now exposes only:

- `ranking_table`;
- `followup_table`;
- units and currency.

`top_k`, follow-up rank, thresholds and Scope are retained as hidden audit metadata. The matcher validates that hidden metadata against the pinned schema rather than requiring the model to repeat it.

The Answer Schema Registry was upgraded to `qa_answer_schema_registry.v2`. Every L3 sample now passes a deterministic Oracle before an API call:

```text
canonical gold
→ public model contract
→ normalization
→ matcher
```

The operation plan is also replayed over the exact facts included in the prompt. Its output is adapted through the same Answer Schema Registry and must reproduce the gold answer.

Production-data verification covered all 184 Typed Walk samples in the two current QA builds:

| Check | Passed |
| --- | ---: |
| Answer-schema Oracle | 184 / 184 |
| Prompt-evidence operation replay | 184 / 184 |
| Combined preflight | 184 / 184 |

This includes 35 / 35 `walk_scope_filter_rank_followup` samples.

## Evidence-selection metrics

Evidence Pool and Retrieval modes no longer use exact-set equality as the sole criterion. The trial details and aggregate L3 report now include:

- required evidence recall;
- context evidence recall;
- evidence precision;
- exact-set match rate;
- required/context/selected evidence counts;
- answer-field failure counts.

A trial passes evidence selection when required-fact recall is 100% and precision reaches the configured threshold, defaulting to 0.8. Exact-set match remains an audit metric.

## Next-build distribution contracts

Two new immutable profiles define the next production target:

- `config/profiles/prod_qa_deepseek_v4_global_quality_v9.json`
- `config/profiles/prod_qa_deepseek_v4_greater_china_quality_v8.json`

Both enforce:

```text
Automatic Pattern Mining >= 12%
Typed Edge Walk          >= 5%
Fact QA                  <= 25%
DerivedFact QA           <= 30%
Static Graph Pattern     <= 30%
```

The Greater China profile raises Single Fact, Difference, YoY and Ratio supply while reducing multi-year extrema quotas. This directly targets the observed 73-item Greater China T2 shortage.

## Verification

```text
Ruff: all changed files passed
Pytest: 428 passed
Typed Walk production preflight: 184 / 184 passed
Exact 3,000-item audit rebuilt successfully
```

## Remaining production work

The old 3,000 questions retain their original wording and L3 responses. To measure the effect of these changes, the next production run must:

1. build a 5,500–6,500 item L0-passed pool with the new profiles;
2. run item-level L2 evaluation;
3. select 3,000 samples under market, task, language and pipeline quotas;
4. require `accepted` or `accepted_for_coverage`, a training split, no confirmed fatal flag and valid Dataset Role eligibility;
5. rerun the fixed L3 Core Set under Answer Schema Registry v2.

Until that run is complete, `qa3000_dc734a635439cc83` remains a diagnostic benchmark artifact, not the final SFT release.
