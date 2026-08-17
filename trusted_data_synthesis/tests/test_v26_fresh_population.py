from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    FRESHNESS_CHANNELS,
    _make_freshness_channel_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_no_api_compilation_runner import (
    _artifact_accounting,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_no_api_contracts import (
    V26CredentialFreeReplayObservation,
    V26ImmutableFileRecord,
    V26NoApiExperimentReport,
    v26_no_api_experiment_report_id,
)


def test_v26_freshness_contract_freezes_exactly_eight_channels() -> None:
    assert FRESHNESS_CHANNELS == (
        "task_id",
        "source_task_id",
        "evidence_id",
        "evidence_version_id",
        "core_semantic_signature",
        "task_signature",
        "mechanism_instance_signature",
        "source_record_id",
    )

    audits = tuple(
        _make_freshness_channel_audit(
            channel,
            {f"development:{channel}"},
            {f"confirmation:{channel}"},
        )
        for channel in FRESHNESS_CHANNELS
    )

    assert tuple(item.channel for item in audits) == FRESHNESS_CHANNELS
    assert all(item.overlap_count == 0 for item in audits)


@pytest.mark.parametrize("channel", FRESHNESS_CHANNELS)
def test_v26_freshness_contract_rejects_any_channel_overlap(channel: str) -> None:
    with pytest.raises(ValueError, match=f"freshness channel {channel} is not disjoint"):
        _make_freshness_channel_audit(  # type: ignore[arg-type]
            channel,
            {"shared-identity"},
            {"shared-identity"},
        )


def test_v26_no_api_report_replays_after_canonical_key_sorting() -> None:
    values = {
        "run_id": "finance_v26_contract_test",
        "protocol_id": "protocol:test",
        "development_population_id": "population:development",
        "confirmation_population_id": "population:confirmation",
        "freshness_audit_id": "freshness:test",
        "freshness_overlap_count_by_channel": {channel: 0 for channel in FRESHNESS_CHANNELS},
        "joint_compilation_count": 24,
        "trajectory_state_space_count": 24,
        "joint_audit_evidence_count": 72,
        "joint_atomic_case_count": 384,
        "joint_admission_count": 24,
        "scaffold_ladder_count": 24,
        "scaffold_gate_evidence_count": 672,
        "scaffold_atomic_case_count": 3024,
        "scaffold_admission_count": 24,
        "history_collision_case_count": 96,
        "cross_level_mapping_case_count": 96,
        "bridge_static_audit_count": 3,
        "bridge_static_atomic_case_count": 144,
        "bridge_development_authorization_id": "bridge:test",
        "final_ledger_id": "ledger:test",
        "completed_stages": (
            "fresh_task_population",
            "joint_compilation",
            "joint_audit",
            "joint_admission",
            "scaffold_compilation",
            "scaffold_audit",
            "scaffold_admission",
            "bridge_development_authorization",
        ),
        "next_stage": "bridge_rollout",
        "credential_free_replay": V26CredentialFreeReplayObservation(
            command=("python", "replay"),
            replayed_ledger_id="ledger:test",
        ),
        "immutable_files": (
            V26ImmutableFileRecord(
                relative_path="ledger.json",
                sha256="a" * 64,
                byte_count=1,
            ),
        ),
        "model_api_calls": 0,
        "gpu_jobs": 0,
        "status": "passed",
        "schema_version": "finance_v26_no_api_joint_scaffold.v1",
    }
    provisional = V26NoApiExperimentReport.model_construct(report_id="pending", **values)
    report = V26NoApiExperimentReport(
        report_id=v26_no_api_experiment_report_id(provisional),
        **values,
    )
    canonical_json = json.dumps(report.model_dump(mode="json"), sort_keys=True)

    assert V26NoApiExperimentReport.model_validate_json(canonical_json) == report


def test_v26_report_accounting_is_derived_from_artifact_rows(tmp_path: Path) -> None:
    payloads = {
        "joint/compiled_proof_artifacts.json": [{}, {}],
        "joint/trajectory_state_spaces.json": [{}, {}],
        "joint/joint_audit_evidence.json": [
            {"case_results": [{}, {}]},
            {"case_results": [{}]},
        ],
        "joint/joint_admissions.json": [{}, {}],
        "scaffold/ladders.json": [{}, {}],
        "scaffold/gate_evidence.json": [
            {
                "case_results": [
                    {"check_id": "history_collision_sufficiency"},
                    {"check_id": "cross_level_behavior_equivalence_registered"},
                ]
            },
            {"case_results": [{"check_id": "another_check"}]},
        ],
        "scaffold/admissions.json": [{}, {}],
        "bridge/static_construct_audits.json": [
            {"case_results": [{}, {}]},
        ],
    }
    for relative_path, payload in payloads.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    assert _artifact_accounting(tmp_path) == {
        "joint_compilation_count": 2,
        "trajectory_state_space_count": 2,
        "joint_audit_evidence_count": 2,
        "joint_admission_count": 2,
        "scaffold_ladder_count": 2,
        "scaffold_gate_evidence_count": 2,
        "scaffold_admission_count": 2,
        "bridge_static_audit_count": 1,
        "joint_atomic_case_count": 3,
        "scaffold_atomic_case_count": 3,
        "history_collision_case_count": 1,
        "cross_level_mapping_case_count": 1,
        "bridge_static_atomic_case_count": 2,
    }
