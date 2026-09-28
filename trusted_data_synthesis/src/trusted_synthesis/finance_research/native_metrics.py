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
import math
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

from .contracts import TaskBundle, digest
from .profiles import (
    FINQA_OPERATORS,
    MODEL_TERMINAL_REASONS,
    PUBLIC_PROFILE_ID,
    profile_definition,
)

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


def _load_finqa_scorer():
    from .metric_vendor import finqa_evaluate

    return finqa_evaluate


def _program_tokens(program: Any, scorer) -> list[str] | None:
    """Validate the declared submission container, not replace upstream scoring."""
    if isinstance(program, str):
        program = scorer.program_tokenization(program)
    if (
        not isinstance(program, list)
        or len(program) < 5
        or program[-1] != "EOF"
        or (len(program) - 1) % 4
        or any(not isinstance(token, str) for token in program)
    ):
        return None
    for offset in range(0, len(program) - 1, 4):
        op, left, right, close = program[offset : offset + 4]
        if op not in {f"{name}(" for name in FINQA_OPERATORS} or close != ")":
            return None
        if not left.strip() or not right.strip():
            return None
    return program


def _finite_execution(value: Any) -> bool:
    return (
        value in ("yes", "no")
        if isinstance(value, str)
        else (type(value) in (int, float) and math.isfinite(value))
    )


def _score_finqa_profile(
    output: dict[str, Any],
    bundle: TaskBundle,
    prediction: Any,
    program: Any,
    *,
    submission_profile: str,
    stop_reason: str | None,
    all_provider_calls_settled: bool | None,
) -> dict[str, Any]:
    """Apply the declared no-prediction policy around unchanged official functions."""
    profile = profile_definition(submission_profile)
    output["submission_profile"] = profile["id"]
    output["submission_profile_sha256"] = digest(profile)
    output["missing_prediction_policy"] = profile["missing_prediction_policy"]
    output["final_program_consistency"] = {
        "status": "not_comparable",
        "match": None,
        "program_execution_result": None,
        "definition": (
            "project exact numeric/string Final-versus-predicted-program comparison; "
            "separate from native accuracy and not actual tool-trajectory CompletePass"
        ),
    }
    if all_provider_calls_settled is not True or stop_reason not in MODEL_TERMINAL_REASONS:
        output.update(
            status="unknown",
            reason="native model scoring requires known-settled normal model termination",
        )
        return output
    try:
        provenance = metric_provenance()
        scorer = _load_finqa_scorer()
    except ImportError as exc:
        output["reason"] = f"optional native metric dependency missing: {exc.name}"
        return output
    except (RuntimeError, OSError, ValueError) as exc:
        output.update(
            status="unknown", reason=f"metric provenance unavailable: {type(exc).__name__}"
        )
        return output
    output["provenance"] = {
        **provenance["FinQA"],
        "source": provenance["files"]["finqa_evaluate.py"],
    }
    # Check the reference even for a missing prediction. A broken reference must
    # not become a model zero merely because this particular model omitted Final.
    tables = [source.content for source in bundle.public.sources if source.locator == "table"]
    if len(tables) != 1 or not isinstance(tables[0], list):
        output.update(status="reference_inconsistency", reason="missing or ambiguous public table")
        return output
    table = tables[0]
    gold = _program_tokens(bundle.reference.program, scorer)
    if gold is None:
        output.update(
            status="reference_inconsistency", reason="invalid reference program container"
        )
        return output
    try:
        gold_invalid, gold_result = scorer.eval_program(gold, table)
        if (
            gold_invalid
            or not _finite_execution(gold_result)
            or gold_result != bundle.reference.answer
        ):
            output.update(
                status="reference_inconsistency",
                reason="reference program does not execute to the original exe_ans",
            )
            return output
        with contextlib.redirect_stdout(io.StringIO()):
            if not scorer.equal_program(gold, gold):
                output.update(
                    status="reference_inconsistency",
                    reason="reference program is not self-equivalent",
                )
                return output
    except Exception as exc:
        output.update(
            status="unknown",
            reason=f"reference scoring failed: {type(exc).__name__}",
        )
        return output

    def no_prediction(reason: str) -> dict[str, Any]:
        output.update(status="invalid_prediction", reason=reason)
        output["native"] = {"execution_accuracy": 0.0, "program_accuracy": 0.0}
        return output

    if stop_reason != "final_answer" or prediction is None:
        return no_prediction("no valid explicit Final at the settled model terminal")
    if program is None:
        return no_prediction("required predicted FinQA program missing")
    predicted = _program_tokens(program, scorer)
    if predicted is None:
        return no_prediction("invalid predicted FinQA program container or structure")
    # eval_program itself classifies arithmetic/operand/table errors as invalid.
    # An exception escaping the pinned scorer is not silently treated as model error.
    try:
        invalid, executed = scorer.eval_program(predicted, table)
        if invalid or not _finite_execution(executed):
            return no_prediction("predicted FinQA program is not executable")
        with contextlib.redirect_stdout(io.StringIO()):
            program_equal = scorer.equal_program(gold, predicted)
    except Exception as exc:
        output.update(status="unknown", reason=f"native scoring failed: {type(exc).__name__}")
        return output
    if program_equal and executed != bundle.reference.answer:
        output.update(
            status="reference_inconsistency",
            reason="upstream program-equivalence/execution assertion would fail",
        )
        return output
    consistency = _derived_answer_match(prediction, executed)
    output["final_program_consistency"].update(
        status="consistent" if consistency else "inconsistent",
        match=consistency,
        program_execution_result=executed,
    )
    output["native"] = {
        "execution_accuracy": float(executed == bundle.reference.answer),
        "program_accuracy": float(program_equal),
    }
    output["status"] = "scored"
    return output


def score_native(
    bundle: TaskBundle,
    prediction: Any,
    scale: str = "",
    program: str | list[str] | None = None,
    *,
    submission_profile: str | None = None,
    stop_reason: str | None = None,
    all_provider_calls_settled: bool | None = None,
) -> dict[str, Any]:
    """Return separate native metrics and project diagnostics.

    New FinQA runs explicitly declare ``submission_profile='finqa_program_v1'``
    and supply actual terminal/settlement evidence. That profile counts missing
    or invalid model predictions as zero, but never converts unknown calls,
    dependency errors or reference contradictions into zeros. Omitting a profile
    retains the historical interface for old artifacts, not a new-run default.

    The ``native`` and ``derived`` dictionaries must not be pooled into one
    CompletePass, nor averaged across datasets with different metric semantics.
    Dataset/tool/input changes still make the overall run tool-augmented even
    when the numerical scorer is exactly upstream.
    """
    dataset = bundle.public.dataset
    if submission_profile is not None:
        profile_definition(submission_profile)
        if dataset != "finqa" or submission_profile != PUBLIC_PROFILE_ID:
            raise ValueError("native scoring profile does not match dataset")
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
        if submission_profile is not None:
            return _score_finqa_profile(
                output,
                bundle,
                prediction,
                program,
                submission_profile=submission_profile,
                stop_reason=stop_reason,
                all_provider_calls_settled=all_provider_calls_settled,
            )
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
