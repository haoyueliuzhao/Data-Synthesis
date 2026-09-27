"""Offline benchmark metrics, explicitly separate from trajectory reliability.

FinQA requires the predicted DSL program: a final numeric answer alone is not
its official execution/program score. TAT-QA invokes the pinned upstream scorer
with the unmodified reference answer type and scale. No model calls occur here.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

from .contracts import TaskBundle

VENDOR = Path(__file__).with_name("metric_vendor")


@lru_cache(maxsize=1)
def metric_provenance() -> dict:
    provenance = json.loads((VENDOR / "PROVENANCE.json").read_text())
    for filename, binding in provenance["files"].items():
        if hashlib.sha256((VENDOR / filename).read_bytes()).hexdigest() != binding["local_sha256"]:
            raise RuntimeError(f"pinned metric source changed: {filename}")
    return provenance


def _derived_answer_match(prediction: Any, reference: Any) -> float:
    """Project diagnostic only: exact numeric value, with no relative tolerance."""
    if isinstance(prediction, bool) or isinstance(reference, bool):
        return float(type(prediction) is type(reference) and prediction == reference)
    try:
        pred, gold = Decimal(str(prediction).strip()), Decimal(str(reference).strip())
        return float(pred.is_finite() and gold.is_finite() and pred == gold)
    except (ValueError, InvalidOperation):
        return float(prediction == reference)


def score_native(
    bundle: TaskBundle, prediction: Any, scale: str = "", program: str | list[str] | None = None
) -> dict[str, Any]:
    """Return per-task scores; unsupported metrics are null, never invented zeros.

    The ``native`` and ``derived`` dictionaries must not be pooled into one
    CompletePass, nor averaged across datasets with different metric semantics.
    Dataset/tool/input changes still make the overall run tool-augmented even
    when the numerical scorer is exactly upstream.
    """
    dataset = bundle.public.dataset
    output = {
        "dataset": dataset,
        "task_id": bundle.public.task_id,
        "metric_tier": "native_task_metric_not_trajectory_completepass",
        "protocol": "tool_augmented_original_public_context",
        "native": {},
        "derived": {},
        "status": "unsupported",
    }
    if dataset == "finqa":
        output["derived"] = {
            "exact_final_answer_match": _derived_answer_match(prediction, bundle.reference.answer),
            "definition": "project exact numeric/string match; no tolerance; not official FinQA",
        }
        output["native"] = {"execution_accuracy": None, "program_accuracy": None}
        if program is None:
            output["reason"] = (
                "official FinQA execution/program metrics require predicted DSL program"
            )
            return output
        provenance = metric_provenance()
        try:
            from .metric_vendor import finqa_evaluate as scorer
        except ImportError as exc:
            output["reason"] = f"optional native metric dependency missing: {exc.name}"
            return output
        output["provenance"] = {
            **provenance["FinQA"],
            "source": provenance["files"]["finqa_evaluate.py"],
        }
        predicted = scorer.program_tokenization(program) if isinstance(program, str) else program
        # The official interface requires explicit EOF in token-array submissions.
        if (
            not isinstance(predicted, list)
            or not predicted
            or predicted[-1] != "EOF"
            or any(not isinstance(token, str) for token in predicted)
        ):
            output.update(status="invalid_prediction", reason="invalid FinQA program token array")
            output["native"] = {"execution_accuracy": 0.0, "program_accuracy": 0.0}
            return output
        table = next(
            source.content for source in bundle.public.sources if source.locator == "table"
        )
        gold = scorer.program_tokenization(bundle.reference.program)
        invalid, executed = scorer.eval_program(predicted, table)
        # Upstream can print structure errors; do not mix them into structured CLI output.
        with contextlib.redirect_stdout(io.StringIO()):
            program_equal = scorer.equal_program(gold, predicted)
        execution_equal = invalid == 0 and executed == bundle.reference.answer
        if program_equal and executed != bundle.reference.answer:
            # evaluate_result asserts this exact invariant. Preserve the failure,
            # rather than silently promoting contradictory upstream annotations.
            output.update(
                status="reference_inconsistency",
                reason="upstream program-equivalence/execution assertion would fail",
            )
            return output
        output["native"] = {
            "execution_accuracy": float(execution_equal),
            "program_accuracy": float(program_equal),
        }
        output["status"] = "scored" if not invalid else "invalid_prediction"
        return output
    if dataset == "tatqa":
        output["native"] = {"exact_match": None, "f1": None, "scale_accuracy": None}
        provenance = metric_provenance()
        try:
            from .metric_vendor.tatqa_metric import TaTQAEmAndF1
        except ImportError as exc:
            output["reason"] = f"optional native metric dependency missing: {exc.name}"
            return output
        output["provenance"] = {
            **provenance["TAT-QA"],
            "sources": {
                filename: provenance["files"][filename]
                for filename in ("tatqa_metric.py", "tatqa_utils.py")
            },
        }
        ground_truth = {
            "answer": bundle.reference.answer,
            "scale": bundle.reference.scale,
            "answer_type": bundle.reference.annotations["answer_type"],
        }
        scorer = TaTQAEmAndF1()
        scorer(ground_truth, prediction, pred_scale=scale)
        em, f1, scale_accuracy, _ = scorer.get_overall_metric()
        output["native"] = {"exact_match": em, "f1": f1, "scale_accuracy": scale_accuracy}
        output["status"] = "scored"
        return output
    if dataset == "financemath":
        output["native"] = {"numeric_accuracy": None}
        output["reason"] = (
            "FinanceMath official evaluation code/license and answer-extraction protocol are not "
            "bound in this revision; local adapter availability does not imply metric readiness"
        )
        output["derived"] = {
            "exact_final_answer_match": _derived_answer_match(prediction, bundle.reference.answer),
            "definition": "project exact numeric match; not official FinanceMath tolerance",
        }
        return output
    output["reason"] = "native metric adapter not registered"
    return output
