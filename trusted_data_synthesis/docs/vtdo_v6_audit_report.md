# VTDO v6 Repair And Audit Report

## Scope

This audit was completed on 2026-08-01 against Git baseline
`d189e4836abcaff9ddedcb31a555354b4a94a5f7` plus the active, uncommitted VTDO v6
working tree. Existing user changes were preserved. The audit covers Contribution validation,
real-feedback Round assembly, refinement dynamics, beneficiary shift, training identity,
FinQA/TAT-QA evaluation, contamination controls, Finance semantics, and Core/domain boundaries.

The active schema is `vtdo_experiment.v6`. No legacy compatibility alias is accepted.

## Prior Audit Findings

| Prior finding | Repair | Independent evidence |
|---|---|---|
| Contribution validation reused the estimation source | Probe and finite Intervention are separate typed artifacts; adapted/intervention model-state and checkpoint identities must differ and are globally unique across atomic observations | Reused artifacts are rejected both within a pair and across rounds |
| Contribution identity could not represent multiple tasks and rounds | Atomic identity is `(task, round, state, seed)`; baseline and beneficiary contracts are task-round scoped | Two-round regression preserves six task-round cells but only three statistical task clusters |
| Probe set identity conflicted after Round 1 | Exact `probe_set_hash` is round-specific; `probe_protocol_family_hash` is stable across the sequence | Three linked real rounds replay with three set hashes and one family hash |
| Benchmark evaluation accepted a partial manifest | Evaluation requires the complete typed prediction manifest and replays training result, model, Adapter, generation, prediction, and snapshot identities | Legacy three-field manifests and post-generation Adapter mutation are rejected |
| Leakage audit reported zero collisions with unavailable identity channels | Every channel reports coverage; required unavailable channels fail closed; benchmark IDs and rendered context hashes are no longer mislabeled as source/document hashes | Missing shared document identity blocks training preflight instead of reporting a false clean result |
| Real-feedback and training inputs lacked complete content identity | Real-feedback reports hash all four source files; training results hash config, preflight, arm manifest, dataset, base model, and Adapter | Exact-key manifests and content mutation checks are replayed by consumers |
| Beneficiary shift used a global baseline and an any-seed threshold | Support is paired exactly by task/state/seed across declared baseline and updated rounds; model/checkpoint must change; the decision uses a task-clustered Student-t lower bound | Extra/missing support and checkpoint reuse fail closed |
| Dynamics accepted undeclared tasks/rounds and turnover was always zero | Expected task IDs and exact round sets are required; turnover uses an explicit active-support threshold | Three-round replay rejects task-set mismatch and reports thresholded entries/exits |
| FinQA/TAT-QA metrics diverged from released contracts | FinQA Answer Accuracy and Program Execution use separate display and `exe_ans` golds; TAT-QA normalizes equivalent scales | All 1,147 FinQA gold programs and 1,663 TAT-QA gold answer/scale pairs replay |
| Finance rendering assumed every subject was a company and confused filing FY with economic time | Entity-type-aware comparison nouns, natural point/duration windows, `source_report_fiscal_year`, and `economic_period_year` are separate | Country comparison, point-time wording, archive adaptation, and World Bank grounding regressions pass |
| Training readiness could overstate usable arms | Preflight emits exact `permitted_arm_ids`; the trainer refuses any other arm | Shared blockers produce an empty permission set even when local capacity exists |

## Additional Defects Found During Re-Audit

1. The frozen benchmark manifest and README still declared metric/adapter v3 while code and the
   canonical experiment used v4. Both are now aligned to v4.
2. Blank FinQA display answers did not fall back to `exe_ans`. Empty strings now use the released
   executable answer while nonempty display answers remain a separate answer contract.
3. Contribution bootstrap treated multiple rounds of one task as independent clusters. Round
   metrics are now macro-averaged within task before task-cluster bootstrap.
4. A Probe artifact could be replayed under a new Round identity. Contribution validation and the
   independent Round assembler now reject reused observation, model-state, and checkpoint IDs.
5. Registered-ratio replay accepted all-missing unit/currency and comparability context. Runtime
   validation now requires explicit payload context and a nonempty comparability level.
6. World Bank source replay could prefer filing fiscal-year metadata over the evidence economic
   period. Economic period and period end now take precedence.
7. Local base-model paths in training results could depend on the evaluator working directory.
   Local model paths are now serialized as resolved paths and remain content-hashed.

## Verification

```text
Ruff lint:                  passed
Mypy:                       200 source files passed
Pytest:                     210 passed in 60.35s
Python compileall:          passed
git diff --check:           passed
Cross-domain contracts:     17 passed
Generalization audit:       127 files, 0 imports, 0 branches, 0 field leaks
Frozen benchmark self-test: 1,147 FinQA + 1,663 TAT-QA passed
```

`ruff format --check src tests` reports 29 older files that would be mechanically reformatted.
They are outside this repair's behavioral scope and were not bulk-edited; `ruff check` is clean.

## Current Claim Boundary

The v6 implementation is ready to collect new immutable experiment inputs, but the canonical
configuration intentionally remains empirically incomplete:

```text
Contribution Probe/Intervention observation path: not configured
real Explorer/Probe Round inputs:                  not configured
paired beneficiary M0/M1 observations:             not configured
current CCGR task distribution:                    not configured
trained adapters and immutable predictions:        not produced
shared benchmark document-identity map:             not configured
```

Consequently, this audit supports implementation correctness, fail-closed identity enforcement,
controlled moving-potential analysis, and benchmark evaluator consistency. It does not support a
claim of empirical Contribution validity, real feedback stabilization, or downstream training
improvement. Those claims require the recorded real-model assets and GPU experiment matrix.
