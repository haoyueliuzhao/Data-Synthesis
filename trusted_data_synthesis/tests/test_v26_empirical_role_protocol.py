from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_role_protocol import (
    build_empirical_role_protocol,
    empirical_role_protocol_report_id,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
AUDIT_SOURCE = ARTIFACT_ROOT / "finance_v26_67_authority_preserving_postrun_audit_20260819"
TASK_SOURCE = ARTIFACT_ROOT / "finance_v26_65_authority_preserving_operation_hardening_20260819"
INSTRUMENT_SOURCE = ARTIFACT_ROOT / (
    "finance_v26_66_authority_preserving_instrument_requalification_finalization_recovery_20260819"
)
MODEL_CONFIG = PACKAGE_ROOT / "config" / "deepseek_v4_flash_agent_v23_paired_pilot.json"
RUN_ID = "finance_v26_68_empirical_role_protocol_20260819"


def _build(output_dir: Path):
    return build_empirical_role_protocol(
        run_id=RUN_ID,
        audit_dir=AUDIT_SOURCE,
        task_source_dir=TASK_SOURCE,
        instrument_dir=INSTRUMENT_SOURCE,
        model_config_path=MODEL_CONFIG,
        output_dir=output_dir,
        package_root=PACKAGE_ROOT,
    )


def test_protocol_is_byte_deterministic_and_source_bound(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = _build(first_dir)
    second = _build(second_dir)

    assert first == second
    assert first.report_id == empirical_role_protocol_report_id(first)
    assert (
        first.protocol.implementation_source.sha256
        == hashlib.sha256(
            (PACKAGE_ROOT / first.protocol.implementation_source.relative_path).read_bytes()
        ).hexdigest()
    )
    for name in (
        "task_exposure_audits.json",
        "reachability_job_design.json",
        "protocol.json",
        "report.json",
    ):
        assert (first_dir / name).read_bytes() == (second_dir / name).read_bytes()


def test_task_freshness_is_separated_by_registered_role(tmp_path: Path) -> None:
    protocol = _build(tmp_path / "protocol").protocol
    rows = protocol.task_exposure_audits

    assert Counter(item.intended_use for item in rows) == Counter(
        {"capability_measurement": 12, "vtdo_multistate_candidate": 12}
    )
    assert sum(item.api_exposed_in_v26_66 for item in rows) == 8
    assert (
        sum(
            item.api_exposed_in_v26_66
            for item in rows
            if item.intended_use == "capability_measurement"
        )
        == 8
    )
    assert all(
        not item.api_exposed_in_v26_66
        for item in rows
        if item.intended_use == "vtdo_multistate_candidate"
    )
    assert sum(item.eligible_for_state_reachability for item in rows) == 12
    assert all(not item.eligible_for_capability_development for item in rows)


def test_capability_protocol_requires_a_fresh_balanced_population(tmp_path: Path) -> None:
    protocol = _build(tmp_path / "protocol").protocol

    assert protocol.capability_source_task_count == 12
    assert protocol.capability_api_exposed_task_count == 8
    assert protocol.capability_unexposed_task_count == 4
    assert protocol.capability_minimum_balanced_task_count == 12
    assert protocol.capability_fresh_task_shortage == 8
    assert protocol.capability_planned_job_count == 96
    assert protocol.capability_fresh_population_required
    assert protocol.capability_existing_task_reuse_forbidden
    assert protocol.capability_protocol_frozen
    assert not protocol.capability_execution_ready


def test_reachability_denominators_are_complete_and_unexposed(tmp_path: Path) -> None:
    protocol = _build(tmp_path / "protocol").protocol
    jobs = protocol.reachability_jobs

    assert len(jobs) == protocol.reachability_planned_job_count == 360
    assert Counter(item.sampling_mode for item in jobs) == Counter(
        {
            "reachability_unconditional": 144,
            "reachability_conditioned": 216,
        }
    )
    assert len({item.task_package_id for item in jobs}) == 12
    assert len(protocol.source_static_state_ids) == 36
    assert set(
        Counter(
            item.requested_quotient_state_id
            for item in jobs
            if item.sampling_mode == "reachability_conditioned"
        ).values()
    ) == {6}
    assert len({item.job_id for item in jobs}) == 360
    assert all(not item.model_generated_execution for item in jobs)
    assert all(not item.compiler_witness_counted for item in jobs)


def test_public_conditions_do_not_expose_state_or_path_identity(tmp_path: Path) -> None:
    protocol = _build(tmp_path / "protocol").protocol

    assert len(protocol.public_conditions) == 3
    for condition in protocol.public_conditions:
        serialized = json.dumps(condition.public_payload, sort_keys=True).casefold()
        assert "state_id" not in serialized
        assert "path_id" not in serialized
        assert "compiler_witness" not in serialized
        assert "gold_evidence" not in serialized
        assert "action_sequence" not in serialized
        assert "tool_sequence" not in serialized
        assert "evidence:finance:" not in serialized


def test_protocol_freeze_keeps_execution_and_downstream_stages_closed(tmp_path: Path) -> None:
    report = _build(tmp_path / "protocol")
    protocol = report.protocol

    assert protocol.reachability_protocol_frozen
    assert not protocol.authority_preserving_runner_ready
    assert not protocol.reachability_execution_ready
    assert len(protocol.runner_incompatibility_reasons) == 3
    assert report.status == "protocols_frozen_execution_inputs_incomplete"
    assert report.next_permitted_stage == (
        "fresh_capability_population_and_authority_preserving_reachability_runner_only"
    )
    assert not report.capability_execution_authorized
    assert not report.state_reachability_execution_authorized
    assert not report.fresh_confirmation_authorized
    assert not report.no_c_vtdo_authorized
    assert not report.student_training_authorized
    assert not report.exact_target_authorized
    assert not report.gp_c_authorized
    assert report.production_contribution == 0
    assert report.api_call_count == report.gpu_job_count == 0
