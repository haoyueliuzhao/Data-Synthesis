from __future__ import annotations

import hashlib
import json
from typing import Any

from finraw.qa.evaluation.contracts import DIMENSIONS, FATAL_FLAGS, RUBRIC_VERSION


T2_WEIGHTS = {
    "financial_semantic_validity": 0.20,
    "task_authenticity": 0.18,
    "clarity_unambiguity": 0.17,
    "standalone_financial_value": 0.15,
    "evidence_scope_fit": 0.10,
    "answer_rubric_fit": 0.10,
    "language_quality": 0.05,
    "reasoning_necessity": 0.05,
}

T3_WEIGHTS = {
    "standalone_financial_value": 0.18,
    "financial_semantic_validity": 0.17,
    "reasoning_necessity": 0.15,
    "task_authenticity": 0.15,
    "evidence_scope_fit": 0.12,
    "clarity_unambiguity": 0.10,
    "answer_rubric_fit": 0.07,
    "language_quality": 0.06,
}

SCORE_ANCHORS = {
    "1": "Clearly defective and unsuitable for release.",
    "2": "Major weaknesses; requires substantial rewriting or redesign.",
    "3": "Acceptable but ordinary; minor weaknesses remain.",
    "4": "Strong, natural, financially useful, and professionally framed.",
    "5": "Exceptional realism, financial value, clarity, and semantic discipline.",
}


def rubric_for_task(benchmark_task: str) -> dict[str, Any]:
    task = str(benchmark_task or "T2").upper()
    if task not in {"T2", "T3"}:
        task = "T2"
    weights = T3_WEIGHTS if task == "T3" else T2_WEIGHTS
    return {
        "rubric_version": RUBRIC_VERSION,
        "benchmark_task": task,
        "dimensions": list(DIMENSIONS),
        "weights": weights,
        "score_anchors": SCORE_ANCHORS,
        "fatal_flags": sorted(FATAL_FLAGS),
        "task_guidance": (
            "Judge whether the multi-step investigation is financially useful and "
            "whether each operation, scope restriction, and follow-up is necessary."
            if task == "T3"
            else "Do not penalize simplicity. Reward precise historical lookup, "
            "clear period/accounting scope, and a stable verifiable answer."
        ),
    }


def rubric_manifest() -> dict[str, Any]:
    manifest = {
        "version": RUBRIC_VERSION,
        "T2": rubric_for_task("T2"),
        "T3": rubric_for_task("T3"),
    }
    manifest["rubric_hash"] = _hash(manifest)
    return manifest


def rubric_hash() -> str:
    return str(rubric_manifest()["rubric_hash"])


def _hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
