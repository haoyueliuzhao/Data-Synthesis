from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityObservationGroup,
    ObservationPartition,
    require_catalog_partition,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_breadth_depth_task_synthesis as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_breadth_depth_task_synthesis_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_observation_static_audit as static_audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / build_module.OUTPUT_DIR


def _load(name: str) -> object:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def test_formal_static_population_closes_all_noncompensatory_gates() -> None:
    report = models.CapabilityBreadthDepthStaticAuditReport.model_validate(_load("report.json"))
    capacity = models.EvidenceCapacityAudit.model_validate(_load("evidence_capacity_audit.json"))
    development = models.CapabilityObservationGroupCatalog.model_validate(
        _load("development_group_catalog.json")
    )
    confirmation = models.CapabilityObservationGroupCatalog.model_validate(
        _load("sealed_confirmation_group_catalog.json")
    )
    audit = models.TaskLadderStaticAudit.model_validate(_load("task_ladder_static_audit.json"))
    role = models.RoleDepthPreservationAudit.model_validate(
        _load("role_depth_preservation_audit.json")
    )
    assert report.status == "passed"
    assert capacity.selected_design == "full_64_task_design"
    assert capacity.fallback_48_task_design_activated is False
    assert len(development.groups) == len(confirmation.groups) == 8
    assert sum(len(item.variants) for item in (*development.groups, *confirmation.groups)) == 64
    assert len(audit.gates) == audit.passed_gate_count == 17
    assert len(role.signatures) == role.source_role_signature_match_count == 64
    assert len({item.role_task_package_id for item in role.signatures}) == 64
    for group in (*development.groups, *confirmation.groups):
        assert isinstance(group, CapabilityObservationGroup)
        assert tuple(item.depth for item in group.variants) == OBSERVATION_DEPTH_ORDER
        assert group.skeleton.historical_tier_to_observation_depth_mapping_authorized is False
        totals = tuple(item.overlay.primary_load_total for item in group.variants)
        assert all(left < right for left, right in zip(totals, totals[1:], strict=False))


def test_empty_directory_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt = tmp_path / "rebuilt"
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=rebuilt,
        external_audit_path=FORMAL_DIR / "external_joint_audit_input.txt",
    )
    assert products.report.status == "passed"
    assert products.report.provider_calls == 0
    assert products.report.development_runner_preflighted is False
    assert products.report.confirmation_runner_preflighted is False
    assert products.report.observation_depth_model_behavior_measured is False
    formal_names = tuple(sorted(path.name for path in FORMAL_DIR.iterdir() if path.is_file()))
    rebuilt_names = tuple(sorted(path.name for path in rebuilt.iterdir() if path.is_file()))
    assert rebuilt_names == formal_names
    for name in formal_names:
        assert (rebuilt / name).read_bytes() == (FORMAL_DIR / name).read_bytes()


def test_confirmation_catalog_is_rejected_by_development_reader() -> None:
    require_catalog_partition(
        catalog_partition=ObservationPartition.DEVELOPMENT,
        requested_partition=ObservationPartition.DEVELOPMENT,
    )
    with pytest.raises(ValueError, match="crosses the frozen exposure partition"):
        require_catalog_partition(
            catalog_partition=ObservationPartition.CONFIRMATION,
            requested_partition=ObservationPartition.DEVELOPMENT,
        )
    exposure = json.loads((FORMAL_DIR / "exposure_block_contract.json").read_text())
    assert exposure["development_reader_may_access_confirmation_payload"] is False
    assert exposure["confirmation_sealed_until_development_audit"] is True
    assert set(exposure["development_group_ids"]).isdisjoint(exposure["confirmation_group_ids"])


def test_all_destructive_controls_fail_closed_and_transition_is_narrow() -> None:
    formal = models.DestructiveAudit.model_validate(_load("destructive_audit.json"))
    rebuilt = static_audit.build_destructive_audit()
    assert formal == rebuilt
    assert len(formal.mutations) == formal.detected_count == 22
    assert tuple(item.mutation_name for item in formal.mutations) == (
        static_audit.DESTRUCTIVE_MUTATIONS
    )
    transition = models.TransitionContract.model_validate(
        _load("prospective_transition_contract.json")
    )
    assert transition.next_stage == "capability_observation_development_runner_preflight_only"
    assert "provider_execution" in transition.forbidden_operations
    assert "confirmation_payload_loading" in transition.forbidden_operations
    assert "vtdo_or_contribution_estimation" in transition.forbidden_operations
