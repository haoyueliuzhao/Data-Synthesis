from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_capability_reachability_failure_audit import (  # noqa: E501
    CapabilityConversionSummary,
    CapabilityFailureDiagnostic,
    CapabilityReachabilityFailureAuditReport,
    ReachabilityRouteSummary,
    StateSupportDiagnostic,
    StoppingRoleContrast,
    ValidMappingDiagnostic,
    VerifierReplayDifferential,
    build_capability_reachability_failure_audit,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
CAPABILITY_RUN = ARTIFACT_ROOT / "finance_v26_71_capability_development_20260819"
CAPABILITY_TASKS = ARTIFACT_ROOT / "finance_v26_69_fresh_capability_population_20260819"
REACHABILITY_RUN = ARTIFACT_ROOT / "finance_v26_72_state_reachability_20260819"
REACHABILITY_TASKS = (
    ARTIFACT_ROOT / "finance_v26_65_authority_preserving_operation_hardening_20260819"
)
POSTRUN_AUDIT = ARTIFACT_ROOT / "finance_v26_73_authority_role_postrun_audit_v3_20260819"
FORMAL_AUDIT = ARTIFACT_ROOT / "finance_v26_74_capability_reachability_failure_audit_v2_20260819"
RUN_ID = "finance_v26_74_capability_reachability_failure_audit_v2_20260819"
DETAIL_FILES = (
    "capability_conversion_summaries.json",
    "capability_failure_diagnostics.json",
    "reachability_route_summaries.json",
    "reachability_valid_mapping_diagnostics.json",
    "state_support_diagnostics.json",
    "stopping_role_contrast.json",
    "verifier_replay_differentials.json",
    "report.json",
)


def _build(output: Path) -> CapabilityReachabilityFailureAuditReport:
    return build_capability_reachability_failure_audit(
        run_id=RUN_ID,
        capability_run_dir=CAPABILITY_RUN,
        capability_task_source_dir=CAPABILITY_TASKS,
        reachability_run_dir=REACHABILITY_RUN,
        reachability_task_source_dir=REACHABILITY_TASKS,
        postrun_audit_dir=POSTRUN_AUDIT,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def rebuilt_audit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_74_rebuild")
    _build(output)
    return output


def _load_list(path: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    return tuple(
        model.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))
    )


def test_v26_74_is_deterministic_and_matches_formal(
    rebuilt_audit: Path,
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate"
    _build(duplicate)
    for relative in DETAIL_FILES:
        assert (rebuilt_audit / relative).read_bytes() == (duplicate / relative).read_bytes()
        assert (rebuilt_audit / relative).read_bytes() == (FORMAL_AUDIT / relative).read_bytes()


def test_capability_failure_conversion_is_complete(rebuilt_audit: Path) -> None:
    failures = _load_list(
        rebuilt_audit / "capability_failure_diagnostics.json",
        CapabilityFailureDiagnostic,
    )
    summaries = _load_list(
        rebuilt_audit / "capability_conversion_summaries.json",
        CapabilityConversionSummary,
    )
    by_scope = {item.scope: item for item in summaries}

    assert len(failures) == 92
    assert Counter(item.mechanism_id for item in failures) == {
        "context_conditioned_action": 20,
        "semantic_reconciliation": 24,
        "failure_recovery": 24,
        "state_dependent_stopping": 24,
    }
    overall = by_scope["all_mechanisms"]
    assert overall.mechanism_success_count == 30
    assert overall.valid_given_mechanism_success.exact_fraction == "4/30"
    assert overall.mechanism_success_given_valid.exact_fraction == "4/4"

    recovery = by_scope["failure_recovery"]
    assert recovery.mechanism_success_count == recovery.local_success_invalid_count == 12
    assert recovery.local_success_program_closed_count == 1
    assert recovery.local_success_postterminal_verified_count == 1
    assert recovery.local_success_verifier_evaluated_count == 0
    assert recovery.local_success_failure_reason_counts == {
        "failed_tool_budget": 7,
        "model_token_budget": 2,
        "unavailable_tool": 3,
    }
    assert recovery.valid_given_mechanism_success.exact_fraction == "0/12"


def test_stopping_contrast_localizes_the_replay_gap(rebuilt_audit: Path) -> None:
    contrast = StoppingRoleContrast.model_validate_json(
        (rebuilt_audit / "stopping_role_contrast.json").read_text(encoding="utf-8")
    )

    assert contrast.capability.local_mechanism_success_count == 8
    assert contrast.capability.full_program_lineage_count == 8
    assert contrast.capability.postterminal_verification_count == 8
    assert contrast.capability.frozen_runtime_replay_failure_count == 8
    assert contrast.capability.sole_runtime_replay_blocker_count == 8
    assert contrast.capability.independently_valid_count == 0
    assert contrast.reachability.independently_valid_count == 16
    assert contrast.reachability.frozen_runtime_replay_failure_count == 0
    assert contrast.shared_task_package_count == contrast.shared_semantic_source_count == 0
    assert contrast.shared_structural_signature_count == 0
    assert contrast.capability_zero_valid_interpretation_blocked_by_verifier_gap
    assert not contrast.causal_task_structure_attribution_supported
    assert not contrast.historical_results_reclassified


def test_valid_mapping_and_route_diagnostics_retain_frozen_counts(
    rebuilt_audit: Path,
) -> None:
    mappings = _load_list(
        rebuilt_audit / "reachability_valid_mapping_diagnostics.json",
        ValidMappingDiagnostic,
    )
    routes = _load_list(
        rebuilt_audit / "reachability_route_summaries.json",
        ReachabilityRouteSummary,
    )

    assert len(mappings) == 21
    assert sum(item.sampling_mode == "reachability_unconditional" for item in mappings) == 5
    conditioned = tuple(
        item for item in mappings if item.sampling_mode == "reachability_conditioned"
    )
    assert len(conditioned) == 16
    assert sum(item.on_target is True for item in conditioned) == 2
    assert sum(item.on_target is False for item in conditioned) == 14
    assert all(item.actual_path_strategy == "structured_direct" for item in mappings)
    assert [item.adherence_count for item in routes] == [52, 6, 7]
    assert [item.independently_valid_count for item in routes] == [2, 6, 8]
    assert [item.on_target_valid_count for item in routes] == [2, 0, 0]
    assert [item.off_target_valid_count for item in routes] == [0, 6, 8]


def test_state_hits_and_releases_remain_nonadmitted(rebuilt_audit: Path) -> None:
    states = _load_list(
        rebuilt_audit / "state_support_diagnostics.json",
        StateSupportDiagnostic,
    )

    assert len(states) == 4
    assert sum(item.natural_hit_count for item in states) == 5
    assert sum(item.conditioned_on_target_count for item in states) == 2
    assert sum(item.released_count for item in states) == 2
    released = tuple(item for item in states if item.released_count)
    assert len(released) == 2
    assert all(item.released_count == 1 and item.release_shortfall == 2 for item in released)
    assert all(not item.admitted and item.historical_freeze_retained for item in states)


def test_replay_differential_is_prospective_only(rebuilt_audit: Path) -> None:
    rows = _load_list(
        rebuilt_audit / "verifier_replay_differentials.json",
        VerifierReplayDifferential,
    )
    report = CapabilityReachabilityFailureAuditReport.model_validate_json(
        (rebuilt_audit / "report.json").read_text(encoding="utf-8")
    )

    assert len(rows) == 18
    assert Counter(item.role for item in rows) == {
        "capability_development": 10,
        "state_reachability": 8,
    }
    assert sum(item.runtime_replay_is_sole_frozen_blocker for item in rows) == 15
    assert all(item.authority_aligned_replay_passed for item in rows)
    assert all(item.failed_mismatch_observations_action_neutral for item in rows)
    assert all(item.prospective_repair_signal for item in rows)
    assert all(not item.historical_validity_reclassified for item in rows)
    assert report.status == "verifier_replay_contract_gap_observed"
    assert report.next_permitted_stage == "authority_preserving_verifier_replay_repair_only"
    assert report.admitted_state_count == report.admitted_task_count == 0
    assert report.production_contribution == report.api_call_count == report.gpu_job_count == 0


def test_report_identity_and_frozen_count_mutations_fail_closed(rebuilt_audit: Path) -> None:
    payload = json.loads((rebuilt_audit / "report.json").read_text(encoding="utf-8"))
    payload["report_id"] = "finance_v26_capability_reachability_failure_audit:tampered"
    with pytest.raises(ValidationError, match="identity is invalid"):
        CapabilityReachabilityFailureAuditReport.model_validate(payload)

    payload = json.loads((rebuilt_audit / "report.json").read_text(encoding="utf-8"))
    payload["capability_invalid_count"] = 91
    with pytest.raises(ValidationError):
        CapabilityReachabilityFailureAuditReport.model_validate(payload)
