from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pytest
import torch

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_gradient_precision_calibration as base_calibration,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_gradient_precision_calibration_v5 as calibration,
)
from trusted_synthesis.hashing import canonical_hash


def _selection(plan_hash: str = "plan:1") -> dict[str, object]:
    value: dict[str, object] = {
        "calibration_version": calibration.CALIBRATION_VERSION,
        "plan_hash": plan_hash,
        "status": "frozen",
        "selected_profile_id": "bf16_checkpoint_strict_accumulation",
        "development_result_hashes": ("result:1",),
        "frozen_raw_thresholds": calibration.RAW_SAFETY_BOUNDS,
        "pairwise_uncertainty_envelope": 0.001,
        "numeric_algorithm_contract_hash": calibration.NUMERIC_ALGORITHM_CONTRACT_HASH,
        "profile_resource_contracts": calibration.PROFILE_RESOURCE_CONTRACTS,
        "selected_resource_contract": calibration.PROFILE_RESOURCE_CONTRACTS[
            "bf16_checkpoint_strict_accumulation"
        ],
        "validation_observed": False,
        "sealed_candidate_outcomes_observed": False,
    }
    value["selection_hash"] = canonical_hash(
        value,
        prefix="finance_gradient_precision_v5_selection:",
    )
    return value


def _result(plan: dict[str, object]) -> dict[str, object]:
    source = plan["sources"]["development"]  # type: ignore[index]
    value: dict[str, object] = {
        "calibration_version": calibration.CALIBRATION_VERSION,
        "plan_hash": plan["plan_hash"],
        "split": "development",
        "profile": asdict(calibration._profile("bf16_checkpoint_strict_accumulation")),
        "source_plan_hash": source["plan_hash"],
        "source_manifest_hash": source["manifest_hash"],
        "objective_split": source["objective_split"],
        "objective_record_set_id": source["objective_record_set_id"],
        "requested_cuda_device_ids": (0,),
        "resource_contract": calibration.PROFILE_RESOURCE_CONTRACTS[
            "bf16_checkpoint_strict_accumulation"
        ],
        "preflight_gpu_memory": {
            "0": {
                "free_bytes": 70 * calibration.GIB,
                "total_bytes": 80 * calibration.GIB,
                "allocated_bytes": 0,
                "reserved_bytes": 0,
            }
        },
        "numeric_algorithm_contract_hash": calibration.NUMERIC_ALGORITHM_CONTRACT_HASH,
        "status": "completed",
    }
    value["result_hash"] = canonical_hash(
        value,
        prefix="finance_gradient_precision_v5_result:",
    )
    return value


def test_selection_replay_rejects_tampering() -> None:
    plan = {"plan_hash": "plan:1"}
    selection = _selection()
    calibration._verify_selection(selection, plan)

    selection["pairwise_uncertainty_envelope"] = 0.004
    with pytest.raises(ValueError, match="immutable identity replay"):
        calibration._verify_selection(selection, plan)


def test_result_replay_checks_source_identity_and_content_hash() -> None:
    plan: dict[str, object] = {
        "plan_hash": "plan:1",
        "sources": {
            "development": {
                "plan_hash": "source-plan:1",
                "manifest_hash": "source-manifest:1",
                "objective_split": "estimation",
                "objective_record_set_id": "objective-set:1",
            }
        },
    }
    result = _result(plan)
    calibration._verify_result(
        result,
        plan,
        split="development",
        profile_id="bf16_checkpoint_strict_accumulation",
    )

    result["objective_record_set_id"] = "objective-set:other"
    with pytest.raises(ValueError, match="source differs"):
        calibration._verify_result(
            result,
            plan,
            split="development",
            profile_id="bf16_checkpoint_strict_accumulation",
        )


def test_raw_summary_retains_strict_rank_as_diagnostic_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = {
        **calibration.RAW_SAFETY_BOUNDS,
        "minimum_task_rank_agreement": 0.0,
    }

    def fake_summary(*args: object, **kwargs: object) -> dict[str, object]:
        return {"metrics": metrics, "task_rows": (), "status": "failed"}

    monkeypatch.setattr(calibration, "_summary", fake_summary)
    result = calibration._raw_summary(
        [{"unused": True}],
        task_distributions={},
        thresholds=calibration.RAW_SAFETY_BOUNDS,
    )

    assert result["status"] == "passed"
    assert result["strict_rank_agreement_diagnostic"] == 0.0
    assert "minimum_task_rank_agreement" not in result["thresholds"]


def test_failed_validation_rejects_stale_frozen_contract(tmp_path: Path) -> None:
    (tmp_path / "frozen_numeric_contract.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="stale frozen contract"):
        calibration._reject_stale_frozen_contract(
            tmp_path,
            validation_passed=False,
        )

    calibration._reject_stale_frozen_contract(
        tmp_path,
        validation_passed=True,
    )


def test_validation_profile_cannot_run_before_selection_is_frozen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "plan.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(calibration, "_verify_plan", lambda plan: None)

    with pytest.raises(ValueError, match="before profile selection"):
        calibration.run_profile(
            argparse.Namespace(
                output_dir=str(tmp_path),
                split="validation",
                profile_id="bf16_checkpoint_strict_accumulation",
                gpu_ids=(0,),
            )
        )


def test_prepare_rejects_preobserved_sealed_candidate(
    tmp_path: Path,
) -> None:
    report: dict[str, object] = {
        "population_version": calibration.POPULATION_VERSION,
        "status": "passed",
        "sealed_candidate_outcomes_observed": True,
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_gradient_calibration_population:",
    )
    report_path = tmp_path / "population.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="observed before calibration"):
        calibration.prepare(
            argparse.Namespace(
                population_report_path=str(report_path),
                development_source_run_dir=str(tmp_path / "development"),
                validation_source_run_dir=str(tmp_path / "validation"),
                output_dir=str(tmp_path / "output"),
            )
        )


def test_derived_thresholds_exclude_retired_strict_rank_gate() -> None:
    metrics = {
        "maximum_loss_identity_absolute_error": 0.0,
        "minimum_gradient_recomposition_cosine": 0.9998,
        "maximum_gradient_recomposition_relative_error": 0.02,
        "maximum_gp_score_absolute_delta": 0.002,
        "maximum_update_total_variation": 0.0002,
        "maximum_update_jensen_shannon": 0.0,
    }

    thresholds = calibration._derived_raw_thresholds(metrics)

    assert set(thresholds) == calibration.RAW_THRESHOLD_KEYS
    assert "minimum_task_rank_agreement" not in thresholds


def test_resource_preflight_is_fail_closed() -> None:
    sufficient = {
        "0": {
            "free_bytes": 70 * calibration.GIB,
            "total_bytes": 80 * calibration.GIB,
            "allocated_bytes": 0,
            "reserved_bytes": 0,
        }
    }
    assert (
        calibration._verify_gpu_resource_preflight(
            profile_id="bf16_checkpoint_strict_accumulation",
            gpu_ids=(0,),
            snapshot=sufficient,
        )
        == calibration.PROFILE_RESOURCE_CONTRACTS["bf16_checkpoint_strict_accumulation"]
    )

    with pytest.raises(ValueError, match="requires 1 GPU"):
        calibration._verify_gpu_resource_preflight(
            profile_id="bf16_checkpoint_strict_accumulation",
            gpu_ids=(0, 1),
            snapshot=sufficient,
        )
    insufficient = {"0": {**sufficient["0"], "free_bytes": 63 * calibration.GIB}}
    with pytest.raises(ValueError, match="free-memory preflight"):
        calibration._verify_gpu_resource_preflight(
            profile_id="bf16_checkpoint_strict_accumulation",
            gpu_ids=(0,),
            snapshot=insufficient,
        )


def test_shared_token_region_losses_evaluate_cross_entropy_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logits = torch.tensor(
        [[[2.0, 0.0], [0.0, 2.0], [1.0, 1.0]]],
        requires_grad=True,
    )
    targets = torch.tensor([[0, 1, 0]])
    calls = 0
    original = torch.nn.functional.cross_entropy

    def counted(*args: object, **kwargs: object) -> torch.Tensor:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(torch.nn.functional, "cross_entropy", counted)
    full, common, differential = base_calibration._shared_token_region_losses(
        logits,
        targets,
        common_ordinals=torch.tensor([0, 1]),
        differential_ordinals=torch.tensor([2]),
        accumulator_dtype="float64",
    )

    assert calls == 1
    assert torch.allclose(full, (2 * common + differential) / 3, atol=1e-12)


def test_profile_checkpoints_resume_only_exact_plan_jobs(tmp_path: Path) -> None:
    profile = calibration._profile("bf16_checkpoint_strict_accumulation")
    job = {
        "job_id": "job:1",
        "task_id": "task:1",
        "task_type": "comparison",
        "state_id": "state:1",
        "record_id": "record:1",
        "gradient_seed": 7,
    }
    source = {
        "plan_hash": "source-plan:1",
        "plan_sha256": "a" * 64,
        "manifest_hash": "source-manifest:1",
        "manifest_sha256": "b" * 64,
        "objective_split": "estimation",
        "objective_record_set_id": "objective:1",
        "target_records_sha256": "c" * 64,
        "token_region_manifest_hash": "tokens:1",
        "beneficiary_adapter_tensor_sha256": "d" * 64,
        "jobs": [job],
    }
    plan = {"plan_hash": "plan:1"}
    row = {
        **job,
        "full_gp_score": 0.2,
        "recomposed_gp_score": 0.2,
    }
    checkpoint = calibration._build_profile_checkpoint(
        plan=plan,
        source=source,
        split="development",
        profile=profile,
        job=job,
        row=row,
    )
    checkpoint_path = calibration._profile_checkpoint_path(
        tmp_path,
        split="development",
        profile_id=profile.profile_id,
        job_id=job["job_id"],
    )
    calibration._write_json(checkpoint_path, checkpoint)

    resumed = calibration._load_profile_checkpoints(
        tmp_path,
        plan=plan,
        source=source,
        split="development",
        profile=profile,
    )

    assert resumed[job["job_id"]]["row"] == row

    checkpoint["row"]["record_id"] = "record:other"
    calibration._write_json(checkpoint_path, checkpoint)
    with pytest.raises(ValueError, match="immutable identity replay"):
        calibration._load_profile_checkpoints(
            tmp_path,
            plan=plan,
            source=source,
            split="development",
            profile=profile,
        )
