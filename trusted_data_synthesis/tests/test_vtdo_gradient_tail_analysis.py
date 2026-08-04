from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_gradient_tail_analysis import (
    analyze_gradient_projection_tail,
)
from trusted_synthesis.hashing import canonical_hash


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _seal(value: dict[str, Any], *, field: str, prefix: str) -> dict[str, Any]:
    value[field] = canonical_hash(value, prefix=prefix)
    return value


def _tail_fixture(root: Path) -> None:
    gradient_path = root / "gradient.safetensors"
    gradient_path.parent.mkdir(parents=True, exist_ok=True)
    gradient_path.write_bytes(b"frozen-gradient")
    gradient_sha256 = hashlib.sha256(gradient_path.read_bytes()).hexdigest()
    plan = _seal(
        {
            "jobs": ({"job_id": "job-a"}, {"job_id": "job-b"}),
        },
        field="plan_hash",
        prefix="finance_contribution_gradient_plan:",
    )
    base_row = {
        "status": "passed",
        "plan_hash": plan["plan_hash"],
        "partition_count": 2,
        "state_gradient_file": str(gradient_path),
        "state_gradient_sha256": gradient_sha256,
        "common_token_gradient_file": str(gradient_path),
        "common_token_gradient_sha256": gradient_sha256,
        "differential_token_gradient_file": str(gradient_path),
        "differential_token_gradient_sha256": gradient_sha256,
        "task_id": "task-a",
        "task_type": "comparison",
        "source_distribution_id": "distribution-a",
        "realization_index": 0,
        "loss_identity_absolute_error": 0.0,
        "differential_supervised_token_fraction": 0.08,
        "state_supervised_tokens": 3000,
    }
    rows = [
        _seal(
            {
                **base_row,
                "job_id": "job-a",
                "result_hash_seed": "a",
                "record_id": "record-a",
                "state_id": "state-a",
                "numeric_full_gp_score": 0.51,
                "numeric_recomposed_gp_score": 0.49,
                "numeric_gp_score_absolute_delta": 0.02,
                "token_gradient_recomposition_relative_error": 0.03,
                "token_gradient_recomposition_cosine": 0.98,
            },
            field="result_hash",
            prefix="finance_contribution_gradient_result:",
        ),
        _seal(
            {
                **base_row,
                "job_id": "job-b",
                "result_hash_seed": "b",
                "record_id": "record-b",
                "state_id": "state-b",
                "numeric_full_gp_score": 0.50,
                "numeric_recomposed_gp_score": 0.52,
                "numeric_gp_score_absolute_delta": 0.001,
                "token_gradient_recomposition_relative_error": 0.01,
                "token_gradient_recomposition_cosine": 0.9999,
            },
            field="result_hash",
            prefix="finance_contribution_gradient_result:",
        ),
    ]
    workers_dir = root / "workers"
    workers_dir.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(rows):
        (workers_dir / f"partition_{index}.jsonl").write_text(
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    _write_json(
        root / "worker_summary.json",
        {"plan_hash": plan["plan_hash"], "workers": ({}, {})},
    )
    _write_json(root / "plan.json", plan)
    evaluation_manifest = _seal(
        {"record_gradients": (), "aggregate_gradients": ()},
        field="manifest_hash",
        prefix="finance_contribution_evaluation_gradient_manifest:",
    )
    _write_json(root / "evaluation_gradient_manifest.json", evaluation_manifest)
    thresholds = {
        "maximum_gp_score_absolute_delta": 0.0023,
        "maximum_loss_identity_absolute_error": 1e-6,
        "maximum_token_gradient_recomposition_relative_error": 0.022,
        "maximum_update_jensen_shannon": 1e-6,
        "maximum_update_total_variation": 0.00027,
        "minimum_task_rank_agreement": 1.0,
        "minimum_token_gradient_recomposition_cosine": 0.99975,
    }
    numeric_task_rows = (
        {
            "task_id": "task-a",
            "state_count": 2,
            "rank_agreement": 0.0,
            "update_total_variation": 0.0001,
            "update_jensen_shannon": 1e-8,
        },
    )
    report = _seal(
        {
            "experiment_version": "finance_contribution_gradient_projection.v14",
            "run_role": "production_candidate",
            "plan_hash": plan["plan_hash"],
            "numeric_contract_hash": "numeric-contract-a",
            "evaluation_gradient_manifest_hash": evaluation_manifest["manifest_hash"],
            "task_count": 1,
            "state_count": 2,
            "state_realization_count": 2,
            "state_rows": (
                {
                    "state_gradient_file": str(gradient_path),
                    "state_gradient_sha256": gradient_sha256,
                },
                {
                    "state_gradient_file": str(gradient_path),
                    "state_gradient_sha256": gradient_sha256,
                },
            ),
            "task_gradient_artifacts": (
                {"file": str(gradient_path), "sha256": gradient_sha256},
            ),
            "global_gradient_artifact": {
                "file": str(gradient_path),
                "sha256": gradient_sha256,
            },
            "gradient_numeric_precision": {
                "thresholds": thresholds,
                "task_rows": numeric_task_rows,
                "status": "failed",
            },
            "gradient_realization_sampling_stability": {
                "status": "passed",
                "thresholds": {},
                "metrics": {},
            },
            "task_rows": (
                {
                    "task_id": "task-a",
                    "task_type": "comparison",
                    "spearman": 1.0,
                    "pairwise_concordance": 1.0,
                    "winner_agreement": 1.0,
                },
            ),
            "macro_task_spearman": 1.0,
            "macro_task_spearman_ci95": (1.0, 1.0),
            "macro_spearman_p_value": 0.01,
            "macro_pairwise_concordance": 1.0,
            "macro_pairwise_concordance_ci95": (1.0, 1.0),
            "macro_pairwise_concordance_p_value": 0.01,
            "winner_agreement_rate": 1.0,
            "status": "partial",
            "production_authorized": False,
            "blockers": ("gradient_numeric_precision_failed",),
        },
        field="report_hash",
        prefix="finance_contribution_gradient_report:",
    )
    _write_json(root / "report.json", report)


def test_gradient_tail_analysis_replays_integrity_and_slices_failures(tmp_path: Path) -> None:
    _tail_fixture(tmp_path)

    report = analyze_gradient_projection_tail(tmp_path, rehash_artifacts=True)

    assert report["integrity"]["status"] == "passed"
    assert report["integrity"]["artifact_content_hash_pass_count"] == 1
    record_tail = report["record_level_numeric_tail"]
    assert record_tail["slices"]["any_violation_count"] == 1
    assert record_tail["metrics"]["token_recomposition_relative_error"][
        "violation_count"
    ] == 1
    assert record_tail["metrics"]["token_recomposition_cosine"]["violation_count"] == 1
    assert record_tail["metrics"]["gp_score_absolute_delta"]["violation_count"] == 1
    task_tail = report["task_level_numeric_tail"]
    assert task_tail["metrics"]["rank_agreement"]["violation_count"] == 1
    assert len(task_tail["rank_flip_details"]) == 1
    assert report["production_decision"]["downstream_experiments_permitted"] is False


def test_gradient_tail_analysis_rejects_worker_identity_mutation(tmp_path: Path) -> None:
    _tail_fixture(tmp_path)
    partition = tmp_path / "workers" / "partition_0.jsonl"
    row = json.loads(partition.read_text(encoding="utf-8"))
    row["numeric_full_gp_score"] = 999.0
    partition.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="immutable identity replay failed:result_hash"):
        analyze_gradient_projection_tail(tmp_path)
