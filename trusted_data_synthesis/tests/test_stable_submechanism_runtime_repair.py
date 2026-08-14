from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (
    CapabilityBoundaryRolloutRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    FailureLayer,
    RuntimeTerminalOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_runtime_repair import (  # noqa: E501
    _merge_selected_records,
    _selected_transport_failures,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_support import (  # noqa: E501
    FinanceStableSupportContract,
    FinanceStableSupportReport,
    _validate_development_manifest,
)


def _terminal(
    binding_id: str,
    replicate: int,
    *,
    layer: FailureLayer,
    transport: bool,
    runtime_eligible: bool = False,
    semantic: bool = False,
) -> RuntimeTerminalOutcome:
    return RuntimeTerminalOutcome.model_construct(
        binding_id=binding_id,
        replicate=replicate,
        primary_failure_layer=layer,
        api_transport_resolved=transport,
        runtime_eligible_for_capability_denominator=runtime_eligible,
        semantic_answer_correct=semantic,
        valid_success=semantic,
    )


def _record(
    binding_id: str,
    replicate: int,
    record_id: str,
) -> CapabilityBoundaryRolloutRecord:
    return CapabilityBoundaryRolloutRecord.model_construct(
        binding_id=binding_id,
        replicate=replicate,
        record_id=record_id,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_selective_repair_uses_only_frozen_l0_transport_failures() -> None:
    terminals = (
        _terminal(
            "binding-b",
            2,
            layer=FailureLayer.L0_EXTERNAL_INFRASTRUCTURE,
            transport=False,
        ),
        _terminal(
            "binding-a",
            1,
            layer=FailureLayer.L0_EXTERNAL_INFRASTRUCTURE,
            transport=False,
        ),
        _terminal(
            "binding-c",
            0,
            layer=FailureLayer.L3_MODEL_PROTOCOL,
            transport=True,
            runtime_eligible=True,
        ),
        _terminal(
            "binding-d",
            0,
            layer=FailureLayer.L0_EXTERNAL_INFRASTRUCTURE,
            transport=True,
        ),
    )

    selected = _selected_transport_failures(terminals)

    assert tuple((item.binding_id, item.replicate) for item in selected) == (
        ("binding-a", 1),
        ("binding-b", 2),
    )


def test_selective_repair_rejects_capability_outcome_in_l0_set() -> None:
    terminal = _terminal(
        "binding-a",
        0,
        layer=FailureLayer.L0_EXTERNAL_INFRASTRUCTURE,
        transport=False,
        semantic=True,
    )

    with pytest.raises(ValueError, match="selected a capability outcome"):
        _selected_transport_failures((terminal,))


def test_merge_replaces_every_selected_job_without_semantic_cherry_pick() -> None:
    source = (
        _record("binding-a", 0, "source-a"),
        _record("binding-b", 0, "source-b"),
        _record("binding-c", 0, "source-c"),
    )
    repair = (
        _record("binding-a", 0, "repair-a-failed"),
        _record("binding-c", 0, "repair-c-passed"),
    )

    merged = _merge_selected_records(
        source,
        repair,
        selected_keys={("binding-a", 0), ("binding-c", 0)},
    )

    assert tuple(item.record_id for item in merged) == (
        "repair-a-failed",
        "source-b",
        "repair-c-passed",
    )


def test_merge_fails_closed_when_repair_omits_selected_job() -> None:
    source = (
        _record("binding-a", 0, "source-a"),
        _record("binding-b", 0, "source-b"),
    )

    with pytest.raises(ValueError, match="differ from frozen selection"):
        _merge_selected_records(
            source,
            (_record("binding-a", 0, "repair-a"),),
            selected_keys={("binding-a", 0), ("binding-b", 0)},
        )


def test_confirmation_manifest_requires_repair_authorization(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    behavior_path = tmp_path / "behavior.jsonl"
    report_path.write_text("{}\n", encoding="utf-8")
    behavior_path.write_text("{}\n", encoding="utf-8")
    development = FinanceStableSupportContract.model_construct(
        contract_id="development-contract"
    )
    report = FinanceStableSupportReport.model_construct(report_id="repaired-report")
    raw = {
        "schema_version": "finance_stable_runtime_repair_manifest.v1",
        "manifest_id": "repair-manifest",
        "source_contract_id": "development-contract",
        "repaired_report_id": "repaired-report",
        "runtime_measurement_ready": True,
        "capability_support_admitted": True,
        "next_permitted_stage": "fresh_stable_support_confirmation_preparation",
        "artifacts": {
            "repaired_report": {"sha256": _sha256(report_path)},
            "merged_behavior_observations": {"sha256": _sha256(behavior_path)},
        },
    }

    manifest_id, schema_version = _validate_development_manifest(
        raw,
        development=development,
        report=report,
        report_path=report_path,
        behavior_path=behavior_path,
    )

    assert manifest_id == "repair-manifest"
    assert schema_version == "finance_stable_runtime_repair_manifest.v1"


def test_confirmation_manifest_rejects_unready_repair(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    behavior_path = tmp_path / "behavior.jsonl"
    report_path.write_text("{}\n", encoding="utf-8")
    behavior_path.write_text("{}\n", encoding="utf-8")
    development = FinanceStableSupportContract.model_construct(
        contract_id="development-contract"
    )
    report = FinanceStableSupportReport.model_construct(report_id="repaired-report")
    raw = {
        "schema_version": "finance_stable_runtime_repair_manifest.v1",
        "manifest_id": "repair-manifest",
        "source_contract_id": "development-contract",
        "repaired_report_id": "repaired-report",
        "runtime_measurement_ready": False,
        "capability_support_admitted": True,
        "next_permitted_stage": "fresh_stable_support_confirmation_preparation",
        "artifacts": {
            "repaired_report": {"sha256": _sha256(report_path)},
            "merged_behavior_observations": {"sha256": _sha256(behavior_path)},
        },
    }

    with pytest.raises(ValueError, match="authorization is invalid"):
        _validate_development_manifest(
            raw,
            development=development,
            report=report,
            report_path=report_path,
            behavior_path=behavior_path,
        )
