from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import pytest

from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    EmpiricalBoundaryStatus,
    ObservationPartition,
)
from trusted_synthesis.core.task.executable_capability_depth import (
    MechanismCounterfactualKind,
    classify_capability_boundary,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_168_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))
SEALED_DIR = Path(
    os.environ.get("V26_168_TEST_SEALED_DIR", PACKAGE_ROOT / build_module.SEALED_OUTPUT_DIR)
)


def _load(directory: Path, name: str) -> Any:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def _development_catalog() -> models.ExecutableDepthCatalog:
    return models.ExecutableDepthCatalog.model_validate(
        _load(FORMAL_DIR, "development_executable_depth_catalog.json")
    )


def test_formal_executable_depth_artifacts_close_real_runtime_gates() -> None:
    report = models.ExecutableDepthRematerializationReport.model_validate(
        _load(FORMAL_DIR, "report.json")
    )
    defect = models.V167ExecutableDepthDefectAudit.model_validate(
        _load(FORMAL_DIR, "v167_executable_depth_defect_audit.json")
    )
    static = models.ExecutableDepthStaticAudit.model_validate(
        _load(FORMAL_DIR, "executable_depth_static_audit.json")
    )
    necessity = models.MechanismNecessityCatalog.model_validate(
        _load(FORMAL_DIR, "mechanism_necessity_catalog.json")
    )
    destructive = models.ProductionDestructiveAudit.model_validate(
        _load(FORMAL_DIR, "production_destructive_audit.json")
    )
    catalog = _development_catalog()
    packages = tuple(package for group in catalog.groups for package in group.packages)

    assert report.status == "passed"
    assert report.provider_calls == report.stage_two_provider_calls == report.gpu_jobs == 0
    assert report.development_jobs == report.mapper_calls == report.vtdo_rows == 0
    assert report.runner_preflighted is False
    assert defect.actual_public_witness_pass_count == 48
    assert defect.actual_public_witness_failure_count == 16
    assert defect.reconciliation_failure_count == 16
    assert defect.metadata_ladder_only is True
    assert len(static.gates) == static.passed_gate_count == 22
    assert static.public_witness_pass_count == static.task_verifier_pass_count == 64
    assert static.mechanism_necessity_pass_count == 64
    assert len(necessity.replays) == necessity.failed_counterfactual_count == 128
    assert Counter(item.counterfactual_kind for item in necessity.replays) == {
        MechanismCounterfactualKind.DELETE_TARGET_ACTION: 64,
        MechanismCounterfactualKind.BYPASS_TARGET_ACTION: 64,
    }
    assert len(destructive.mutations) == destructive.detected_count == 30
    assert len(packages) == 32
    assert sum(item.operational_witness_compiler_invocation_count for item in packages) == 32
    assert sum(item.task_program_verifier_invocation_count for item in packages) == 32
    assert all(item.variant_operational_witness.full_validity_passed for item in packages)
    assert all(item.variant_program_verification.passed for item in packages)
    assert all(item.depth_witness.full_validity_passed for item in packages)
    assert all(item.depth_witness.mechanism_verifier_invoked for item in packages)

    for group in catalog.groups:
        assert tuple(item.depth for item in group.packages) == OBSERVATION_DEPTH_ORDER
        totals = tuple(item.target_load.total for item in group.packages)
        assert all(left < right for left, right in zip(totals, totals[1:], strict=False))
        assert len({item.graph.graph_id for item in group.packages}) == 4
        assert len({item.signature.candidate_set_hash for item in group.packages}) == 4
        assert len({item.signature.transition_hash for item in group.packages}) == 4
        assert len({item.nuisance.measurement_id for item in group.packages}) == 1
        assert len({item.prompt_binding.rendered_prompt_bytes for item in group.packages}) == 1


def test_capability_loads_are_computed_from_distinct_executable_graphs() -> None:
    expected_totals = {
        CapabilityFamily.CONTEXT_CONDITIONED_ACTION: (2, 4, 8, 14),
        CapabilityFamily.SEMANTIC_RECONCILIATION: (6, 10, 16, 30),
        CapabilityFamily.FAILURE_RECOVERY: (5, 6, 12, 21),
        CapabilityFamily.STATE_DEPENDENT_STOPPING: (5, 7, 11, 16),
    }
    expected_primary_dimension = {
        CapabilityFamily.CONTEXT_CONDITIONED_ACTION: (
            "model_owned_decision_states",
            (1, 1, 2, 3),
        ),
        CapabilityFamily.SEMANTIC_RECONCILIATION: (
            "normalized_reference_consumptions",
            (1, 2, 3, 6),
        ),
        CapabilityFamily.FAILURE_RECOVERY: ("typed_failures", (1, 1, 2, 3)),
        CapabilityFamily.STATE_DEPENDENT_STOPPING: (
            "near_terminal_checkpoints",
            (1, 1, 2, 3),
        ),
    }
    catalog = _development_catalog()
    for group in catalog.groups:
        totals = tuple(item.target_load.total for item in group.packages)
        assert totals == expected_totals[group.capability_family]
        key, expected = expected_primary_dimension[group.capability_family]
        assert tuple(item.target_load.dimensions[key] for item in group.packages) == expected
        assert all(item.target_load.computed_from_runtime_graph for item in group.packages)
        assert all(
            not item.target_load.declared_load_used_as_measurement for item in group.packages
        )

    reconciliation = tuple(
        package
        for group in catalog.groups
        if group.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION
        for package in group.packages
    )
    assert len(reconciliation) == 8
    for package in reconciliation:
        observed_consumptions = sum(
            len(item.consumed_reference_ids) for item in package.depth_witness.observations
        )
        assert set(package.depth_witness.emitted_reference_ids) <= set(
            package.depth_witness.consumed_reference_ids
        )
        assert (
            package.depth_witness.event_multiplicities["normalization_reference_consumed"]
            == observed_consumptions
        )


def test_boundary_algorithm_is_total_for_development_and_confirmation() -> None:
    totality = models.BoundaryAlgorithmTotalityAudit.model_validate(
        _load(FORMAL_DIR, "boundary_algorithm_totality_audit.json")
    )
    assert totality.development_pattern_count == 256
    assert totality.confirmation_pattern_count == 256
    assert totality.uniquely_classified_pattern_count == 512
    assert totality.threshold_edge_case_pass_count == 8

    boundary_pairs: tuple[
        tuple[Literal[2], Literal[6]],
        tuple[Literal[3], Literal[8]],
    ] = ((2, 6), (3, 8))
    for threshold, denominator in boundary_pairs:
        status, bracket = classify_capability_boundary(
            ((0, 0, 0, 0), (0, 0, 0, 0)),
            threshold=threshold,
            denominator=denominator,
        )
        assert status == EmpiricalBoundaryStatus.BELOW_OBSERVATION_FLOOR
        assert bracket is None
        status, bracket = classify_capability_boundary(
            ((threshold,) * 4, (threshold,) * 4),
            threshold=threshold,
            denominator=denominator,
        )
        assert status == EmpiricalBoundaryStatus.ABOVE_OBSERVATION_CEILING
        assert bracket is None
        status, bracket = classify_capability_boundary(
            (
                (threshold, threshold, 0, 0),
                (threshold, threshold, 0, 0),
            ),
            threshold=threshold,
            denominator=denominator,
        )
        assert status == EmpiricalBoundaryStatus.BOUNDARY_BRACKETED
        assert bracket == OBSERVATION_DEPTH_ORDER[1:3]
        status, bracket = classify_capability_boundary(
            ((threshold, 0, 0, 0), (threshold, threshold, 0, 0)),
            threshold=threshold,
            denominator=denominator,
        )
        assert status == EmpiricalBoundaryStatus.NONMONOTONIC_OR_CONFOUNDED
        assert bracket is None
        status, bracket = classify_capability_boundary(
            ((threshold, 0, threshold, 0), (threshold, 0, 0, 0)),
            threshold=threshold,
            denominator=denominator,
        )
        assert status == EmpiricalBoundaryStatus.NONMONOTONIC_OR_CONFOUNDED
        assert bracket is None

    with pytest.raises(ValueError, match="outside its frozen denominator"):
        classify_capability_boundary(
            ((7, 0, 0, 0), (0, 0, 0, 0)),
            threshold=2,
            denominator=6,
        )


def test_confirmation_payload_is_outside_development_products_and_source_is_closed() -> None:
    receipt = models.SealedConfirmationReceipt.model_validate(
        _load(FORMAL_DIR, "sealed_confirmation_receipt.json")
    )
    transition = models.TransitionContract.model_validate(
        _load(FORMAL_DIR, "prospective_transition_contract.json")
    )
    source_root = models.TransitiveSourceRoot.model_validate(
        _load(FORMAL_DIR, "transitive_source_root.json")
    )
    sealed_file = SEALED_DIR / "sealed_confirmation_executable_depth_catalog.json"
    payload = sealed_file.read_bytes()
    sealed_catalog = models.ExecutableDepthCatalog.model_validate(json.loads(payload))

    assert receipt.payload_path_disclosed_to_development is False
    assert receipt.payload_embedded_in_development_root is False
    assert receipt.development_payload_access_count == 0
    assert receipt.sealed_content_root_sha256 == hashlib.sha256(payload).hexdigest()
    assert receipt.sealed_byte_count == len(payload)
    assert sealed_catalog.partition == ObservationPartition.CONFIRMATION
    assert sealed_catalog.package_count == 32
    assert "confirmation_catalog" not in models.BuildProducts.model_fields
    assert not (FORMAL_DIR / sealed_file.name).exists()
    assert build_module.SEALED_OUTPUT_DIR.encode() not in b"".join(
        path.read_bytes() for path in FORMAL_DIR.iterdir() if path.suffix == ".json"
    )
    assert transition.confirmation_payload_loading_authorized is False
    assert transition.next_stage == (
        "capability_observation_executable_depth_development_runner_preflight_only"
    )

    paths = {item.relative_path for item in source_root.files}
    required = {
        "src/trusted_synthesis/core/operations/program.py",
        "src/trusted_synthesis/core/task/executable_capability_depth.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_role_kernel_compatibility_preflight.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_public_operation_witness.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_role_kernel_scalability_design.py",
    }
    assert required <= paths
    assert source_root.file_count == len(paths)
    assert source_root.file_count >= 250
    assert source_root.unresolved_trusted_synthesis_import_count == 0


def test_empty_directory_rebuild_is_byte_identical_and_replays_64_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_rebuild = tmp_path / "main"
    sealed_rebuild = tmp_path / "sealed"
    invocation_count = 0
    original = build_module._compile_variant_task_verification

    def counted_variant_verification(**kwargs: Any) -> Any:
        nonlocal invocation_count
        invocation_count += 1
        return original(**kwargs)

    monkeypatch.setattr(
        build_module,
        "_compile_variant_task_verification",
        counted_variant_verification,
    )
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=main_rebuild,
        sealed_output_dir=sealed_rebuild,
        external_audit_path=FORMAL_DIR / "external_joint_audit_input.txt",
    )
    assert products.report.status == "passed"
    assert invocation_count == 64
    assert products.confirmation_receipt.development_payload_access_count == 0

    for formal, rebuilt in ((FORMAL_DIR, main_rebuild), (SEALED_DIR, sealed_rebuild)):
        formal_names = tuple(sorted(path.name for path in formal.iterdir() if path.is_file()))
        rebuilt_names = tuple(sorted(path.name for path in rebuilt.iterdir() if path.is_file()))
        assert rebuilt_names == formal_names
        for name in formal_names:
            assert (rebuilt / name).read_bytes() == (formal / name).read_bytes()


def test_production_mutations_cover_real_role_runtime_and_verifier_objects() -> None:
    destructive = models.ProductionDestructiveAudit.model_validate(
        _load(FORMAL_DIR, "production_destructive_audit.json")
    )
    target_kinds = {item.target_object_kind for item in destructive.mutations}
    assert {
        "depth_witness",
        "executable_graph",
        "operational_task_package",
        "operational_witness",
        "runtime_observation",
        "runtime_trace",
        "task_program",
        "task_verifier_binding",
        "verifier_contract",
    } <= target_kinds
    assert destructive.abstract_summary_dictionary_mutation_count == 0
    assert all(item.production_validator_invoked for item in destructive.mutations)
    assert all(item.detected for item in destructive.mutations)
