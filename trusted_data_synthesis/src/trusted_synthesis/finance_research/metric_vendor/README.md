# Pinned upstream scoring code

This directory contains licensed **scoring code only**, not benchmark records or
model-visible references. `PROVENANCE.json` binds upstream commits, original
source hashes, local hashes, and the two mechanical packaging changes. The
wrapper verifies those hashes before scoring.

- FinQA: `czyssrs/FinQA` at `0f16e2867befa6840783e58be38c9efb9229d742`;
  original `code/evaluate/evaluate.py`, MIT license in `FinQA.LICENSE`.
  A final newline was added, with no evaluator code changes.
  [Original evaluator](https://github.com/czyssrs/FinQA/blob/0f16e2867befa6840783e58be38c9efb9229d742/code/evaluate/evaluate.py).
- TAT-QA: `NExTplusplus/TAT-QA` at `870accc41953dcde885aabeb963d94aabdc0fbc3`;
  original `tatqa_metric.py` and `tatqa_utils.py`, MIT scorer license in
  `TATQA.LICENSE`. The metric's utility import is package-relative and its final
  newline was added. Its scoring algorithm is unchanged.
  [Original metric](https://github.com/NExTplusplus/TAT-QA/blob/870accc41953dcde885aabeb963d94aabdc0fbc3/tatqa_metric.py).
  The **dataset** has a separate CC BY 4.0 declaration in the upstream README;
  the MIT code license must not be substituted for that data attribution.

The wrapper calls FinQA's program tokenizer, program executor, and symbolic
equivalence checker, following the per-item comparisons in `evaluate_result`.
It preserves the official exact comparison against `exe_ans`; it does not add
numeric tolerances, scale repair, sign repair, or final-answer substitution.
If the official assertion that equivalent programs execute to the supplied
answer would fail, the wrapper reports `reference_inconsistency` with null
native metrics, rather than editing a gold annotation.

The wrapper instantiates TAT-QA's `TaTQAEmAndF1` with original answer type,
answer, and scale. It preserves multi-span, count, numeric rounding, and scale
behavior, including upstream edge cases, rather than reimplementing a simpler
exact-match approximation. All this is offline; no gold information becomes
a model-visible tool observation.

Using an official scorer does **not** make the full tool-augmented experiment
identical to an upstream model pipeline. Native metrics do not measure tool
reliability or `CompletePass`. Missing optional dependencies and missing FinQA
programs return explicit `unsupported`, not fabricated scores.

FinanceMath's adapter follows the public
[author data card](https://huggingface.co/datasets/yale-nlp/FinanceMath/blob/main/README.md).
No FinanceMath gated download, acceptance of access conditions, Python solution
execution, or model-mediated extraction has been performed by this adapter.
Its official metric is not bound in this revision. The separately named exact
numeric diagnostic is project-defined and is **not** an official tolerance.

Dataset imports require local snapshots. The import helpers keep original QA
text, all normalized FinQA pre/table/post context, all TAT-QA table/paragraph
context, and all FinanceMath Markdown tables. FinQA's `table_ori` and upstream
retrieval annotations remain in private audit metadata, while its official
`table` is the public table and the native program evaluator's table. They do
not select the public evidence using `gold_inds`, `qa.model_input`, TAT-QA
`rel_paragraphs`, answer types, or derivations.
