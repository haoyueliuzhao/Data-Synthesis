from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_gradient_numeric_root_cause as root,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_gradient_sealed_candidate as sealed,
)
from trusted_synthesis.hashing import canonical_hash


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _hashed(value: dict[str, object], *, field: str, prefix: str) -> dict[str, object]:
    result = dict(value)
    result[field] = canonical_hash(result, prefix=prefix)
    return result


def test_replay_hash_rejects_mutated_payload() -> None:
    value = _hashed(
        {"status": "passed"},
        field="report_hash",
        prefix="sealed_test:",
    )
    assert (
        sealed._replay_hash(value, field="report_hash", prefix="sealed_test:")
        == value["report_hash"]
    )
    value["status"] = "failed"
    with pytest.raises(ValueError, match="identity replay"):
        sealed._replay_hash(value, field="report_hash", prefix="sealed_test:")


def test_initial_report_lineage_distinguishes_exact_and_superseded_snapshots() -> None:
    assert (
        sealed._initial_report_lineage_mode(
            current_report_id="report:current",
            current_report_sha256="a" * 64,
            referenced_report_id="report:current",
            referenced_report_sha256="a" * 64,
        )
        == "exact_report_snapshot"
    )
    assert (
        sealed._initial_report_lineage_mode(
            current_report_id="report:resumed",
            current_report_sha256="b" * 64,
            referenced_report_id="report:original",
            referenced_report_sha256="a" * 64,
        )
        == "distribution_equivalent_superseded_report_snapshot"
    )
    with pytest.raises(ValueError, match="ID and content hash disagree"):
        sealed._initial_report_lineage_mode(
            current_report_id="report:same",
            current_report_sha256="b" * 64,
            referenced_report_id="report:same",
            referenced_report_sha256="a" * 64,
        )


def test_support_contract_requires_three_disjoint_objective_partitions(
    tmp_path: Path,
) -> None:
    artifacts = [tmp_path / f"partition_{index}.jsonl" for index in range(3)]
    for index, path in enumerate(artifacts):
        path.write_text(f"{index}\n", encoding="utf-8")
    plan = _hashed(
        {
            "experiment_version": sealed.gradient.REQUIRED_OBJECTIVE_SUPPORT_VERSION,
            "disjoint_artifact_paths": [str(path) for path in artifacts],
            "disjoint_artifact_sha256": [sealed._sha256(path) for path in artifacts],
            "objective_partitions": {
                "estimation": {"record_ids": ["estimate"]},
                "validation": {"record_ids": ["validate"]},
                "authorization": {"record_ids": ["authorize"]},
            },
            "numeric_contract_hash": sealed.EXPECTED_OLD_NUMERIC_CONTRACT_HASH,
        },
        field="plan_hash",
        prefix="finance_contribution_evaluation_support_plan:",
    )
    report = _hashed(
        {
            "status": "passed",
            "plan_hash": plan["plan_hash"],
        },
        field="report_hash",
        prefix="finance_contribution_evaluation_support_report:",
    )
    support_dir = tmp_path / "support"
    _write(support_dir / "plan.json", plan)
    _write(support_dir / "beneficiary_evaluation_report.json", report)

    observed_plan, observed_report = sealed._load_support(
        support_dir,
        artifacts_path=artifacts[2],
    )
    assert observed_plan["plan_hash"] == plan["plan_hash"]
    assert observed_report["report_hash"] == report["report_hash"]

    plan["objective_partitions"]["authorization"]["record_ids"] = ["estimate"]  # type: ignore[index]
    plan.pop("plan_hash")
    plan["plan_hash"] = canonical_hash(
        plan,
        prefix="finance_contribution_evaluation_support_plan:",
    )
    report["plan_hash"] = plan["plan_hash"]
    report.pop("report_hash")
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_contribution_evaluation_support_report:",
    )
    _write(support_dir / "plan.json", plan)
    _write(support_dir / "beneficiary_evaluation_report.json", report)
    with pytest.raises(ValueError, match="partitions overlap"):
        sealed._load_support(support_dir, artifacts_path=artifacts[2])


def test_sealed_checkpoint_is_bound_to_source_and_job(tmp_path: Path) -> None:
    profile = root._profile(sealed.EXPECTED_PROFILE_ID)
    plan = {"plan_hash": "sealed_plan"}
    source_manifest: dict[str, Any] = {
        "source_hash": "sealed_source",
        "source": {"jobs": [{"job_id": "job_1"}]},
    }
    row = {"job_id": "job_1"}
    checkpoint = sealed._build_checkpoint(
        plan=plan,
        source=source_manifest,
        profile=profile,
        job=source_manifest["source"]["jobs"][0],
        row=row,
    )
    _write(sealed._checkpoint_path(tmp_path, "job_1"), checkpoint)
    loaded = sealed._load_checkpoints(
        tmp_path,
        plan=plan,
        source_manifest=source_manifest,
        profile=profile,
    )
    assert loaded["job_1"]["row"] == row

    checkpoint["source_hash"] = "different_source"
    checkpoint.pop("checkpoint_hash")
    checkpoint["checkpoint_hash"] = canonical_hash(
        checkpoint,
        prefix="finance_gradient_numeric_sealed_checkpoint:",
    )
    _write(sealed._checkpoint_path(tmp_path, "job_1"), checkpoint)
    with pytest.raises(ValueError, match="identity differs"):
        sealed._load_checkpoints(
            tmp_path,
            plan=plan,
            source_manifest=source_manifest,
            profile=profile,
        )


@pytest.mark.parametrize(
    ("summary_status", "expected_status", "expected_next"),
    [
        ("passed", "passed", "preregister_contribution_authorization_experiment"),
        ("failed", "failed", None),
    ],
)
def test_aggregate_never_authorizes_contribution_or_production(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    summary_status: str,
    expected_status: str,
    expected_next: str | None,
) -> None:
    plan = {
        "plan_hash": "sealed_plan",
        "numeric_contract_hash": sealed.EXPECTED_CONTRACT_HASH,
        "task_set_id": sealed.EXPECTED_TASK_SET_ID,
    }
    source = {
        "source_hash": "sealed_source",
        "task_count": 6,
        "state_count": 20,
        "full_job_count": 60,
        "diagnostic_job_count": 20,
        "api_failure_counts": {"initial": {}, "state": {}},
    }
    result = _hashed(
        {
            "sealed_plan_hash": plan["plan_hash"],
            "source_hash": source["source_hash"],
            "numeric_contract_hash": plan["numeric_contract_hash"],
            "profile": {"profile_id": sealed.EXPECTED_PROFILE_ID},
            "status": "completed",
            "summary": {"status": summary_status},
        },
        field="result_hash",
        prefix="finance_gradient_numeric_sealed_result:",
    )
    _write(tmp_path / "plan.json", plan)
    _write(tmp_path / "result.json", result)
    monkeypatch.setattr(sealed, "_verify_plan", lambda _: None)
    monkeypatch.setattr(sealed, "_load_source", lambda *_: source)

    sealed.aggregate(argparse.Namespace(output_dir=str(tmp_path)))

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == expected_status
    assert report["allowed_next_stage"] == expected_next
    assert report["contribution_authorized"] is False
    assert report["production_authorized"] is False
