"""One injected Catalog compiler, with real-source coverage separate from fixtures."""

from __future__ import annotations

import ast
import copy
import json
from collections import Counter
from collections.abc import Iterator
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.program_depth import derive_program_depth_metrics
from trusted_synthesis.domains.finance.qa_vnext import catalog as domain

ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_FIXTURES = (
    "trusted_data_synthesis/artifacts/qa_generator_totality/"
    "qa_registered_task_catalog_generator_verifier_execution_totality_preflight_v1_20260904"
)
DEPTH_FIXTURES = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_plus/"
    "qa_semantic_operation_depth_three_plus_constructibility_and_coverage_preflight_v2_20260904"
)
OLD_DESCRIPTOR = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_catalog_integration/"
    "qa_semantic_operation_depth_three_plus_registered_catalog_integration_preflight_v1_20260904/"
    "catalog_descriptor.json"
)
TASK_DEPTHS = {
    "fact_retrieval": 0,
    "comparison": 1,
    "registered_cross_metric_comparison": 1,
    "temporal_growth": 1,
    "temporal_average": 1,
    "temporal_absolute_change": 1,
    "registered_ratio": 1,
    "derived_growth_comparison": 2,
    "derived_growth_absolute_spread": 3,
    "registered_margin_target_gap": 3,
}


@pytest.fixture(scope="module")
def original_bytes() -> Iterator[dict[Path, str]]:
    paths = [ROOT / domain.ARCHIVE_PATH, ROOT / OLD_DESCRIPTOR]
    for directory in (domain.FROZEN_SOURCE_DIRECTORY, HISTORICAL_FIXTURES, DEPTH_FIXTURES):
        paths.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())
    snapshots = {path: domain._sha(path.read_bytes()) for path in paths}
    yield snapshots
    assert {path: domain._sha(path.read_bytes()) for path in paths} == snapshots


@pytest.fixture(scope="module")
def controlled_inputs(
    original_bytes: dict[Path, str],
) -> dict[str, tuple[EvidenceBundle, dict[str, tuple[str, ...]]]]:
    """Saved artificial fixtures test compiler coverage, never real-source availability."""
    result = {}
    catalog = domain.FinanceQACatalog()
    for directory, row_name, bundle_hash, row_hash in (
        (
            HISTORICAL_FIXTURES,
            "totality_rows.jsonl",
            "1060217ae90927996d71759a191b4f9c429411fde543ea9fccf629c20e0d48a6",
            "e3f705d1358f3b0fd929b96b0a4c7b58741a4c868620fa8271f49702635364e6",
        ),
        (
            DEPTH_FIXTURES,
            "coverage_rows.jsonl",
            "45d6a22da00ba058f5f6e5add99ff831b16083bd92dc70b465ddadbe80481d45",
            "126a27c208a29a513d3168b59511753d86396859dd9c2061a5c3c6b1b770a0e1",
        ),
    ):
        raw_bundles = (ROOT / directory / "evidence_bundles.jsonl").read_bytes()
        raw_rows = (ROOT / directory / row_name).read_bytes()
        assert domain._sha(raw_bundles) == bundle_hash
        assert domain._sha(raw_rows) == row_hash
        bundles = {
            bundle.bundle_id: bundle
            for bundle in (
                EvidenceBundle.model_validate_json(line) for line in raw_bundles.splitlines()
            )
        }
        for line in raw_rows.splitlines():
            row = json.loads(line)
            task_type = row["task_type"]
            bundle = bundles[row["evidence_bundle_id"]]
            pattern = catalog.resolve(task_type).pattern
            assert pattern is not None
            evidence_ids = tuple(item.evidence_id for item in bundle.evidence)
            roles = (
                {pattern.evidence_roles[0].role_id: evidence_ids}
                if len(pattern.evidence_roles) == 1
                else {
                    role.role_id: (evidence_id,)
                    for role, evidence_id in zip(pattern.evidence_roles, evidence_ids, strict=True)
                }
            )
            result[task_type] = (bundle, roles)
    assert set(result) == set(TASK_DEPTHS)
    return result


@pytest.fixture(scope="module")
def source_cases(original_bytes: dict[Path, str]) -> tuple[Any, Any, Any]:
    catalog = domain.FinanceQACatalog()
    cases, rows = catalog.frozen_source_cases(ROOT)
    return catalog, cases, rows


def test_domain_catalog_resolves_all_historical_and_depth_types_with_one_registry() -> None:
    registry = domain.catalog_operation_registry()
    catalog = domain.FinanceQACatalog(registry=registry)
    assert catalog.registry is registry
    assert set(catalog.task_types) == set(TASK_DEPTHS)
    assert catalog.task_types == catalog.task_family_ids
    assert catalog.descriptor["historical_task_count"] == 8
    assert catalog.descriptor["total_task_count"] == 10
    assert catalog.descriptor["catalog_version"] == domain.CATALOG_VERSION
    for task_type in TASK_DEPTHS:
        resolved = catalog.resolve(task_type)
        assert resolved.pattern is not None and resolved.runtime is not None
        assert resolved.pattern.task_type == task_type
        assert resolved.receipt["registry_manifest"] == list(registry.manifest())
        for node in resolved.pattern.program_template:
            assert registry.require(node.operator_id).operator_id == node.operator_id
    assert registry.require("registered_compare").operator_id == "registered_compare"
    for operator in domain.DEPTH_OPERATIONS:
        assert registry.require(operator).program_role == "semantic"


@pytest.mark.parametrize("task_type", tuple(TASK_DEPTHS))
def test_each_registered_type_actually_compiles_through_the_same_injected_registry(
    task_type: str,
    controlled_inputs: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = domain.catalog_operation_registry()
    catalog = domain.FinanceQACatalog(registry)
    original_compiler = domain.TaskPatternCompiler
    seen = []

    def compiler(actual_registry: Any, runtime: Any) -> Any:
        seen.append(actual_registry)
        return original_compiler(actual_registry, runtime)

    monkeypatch.setattr(domain, "TaskPatternCompiler", compiler)
    bundle, roles = controlled_inputs[task_type]
    case = catalog.compile(task_type, bundle, roles, case_id=task_type + ".compiler-control")
    assert seen == [registry]
    assert case.task.public.task_type == task_type
    assert case.task.oracle.task_program == case.instantiation.program
    assert case.corpus.evidence == bundle.evidence
    assert case.instantiation.binding.role_bindings == roles
    depth = derive_program_depth_metrics(case.instantiation.program, registry)
    assert depth.semantic_operation_depth == TASK_DEPTHS[task_type]
    row = case.coverage_row()
    assert row["registered"] is row["compiled"] is True
    assert row["source_bindable"] is False
    assert row["source_binding_status"] == "supplied_evidence_not_source_revalidated"
    assert row["new_protocol_executable"] is row["qa_valid"] is row["trajectory_valid"] is None
    catalog.admit_case(case)


def test_default_source_selection_reports_all_ten_types_without_fabricating_missing_sources(
    source_cases: tuple[Any, Any, Any],
) -> None:
    catalog, cases, rows = source_cases
    assert {row["task_type"] for row in rows} == set(catalog.task_types)
    assert len(rows) == 10 and len(cases) == 7
    by_type = {row["task_type"]: row for row in rows}
    absent = {"comparison", "derived_growth_comparison", "registered_margin_target_gap"}
    assert {row["task_type"] for row in rows if not row["source_bindable"]} == absent
    for name in absent:
        assert by_type[name]["registered"] is True
        assert by_type[name]["compiled"] is False
        assert by_type[name]["case_id"] is by_type[name]["task_id"] is None
        assert by_type[name]["compilation_status"] == "not_instantiated"
    assert by_type["registered_margin_target_gap"]["reason"] == (
        "authoritative_gross_margin_target_evidence_absent"
    )
    for row in rows:
        assert row["new_protocol_executable"] is row["qa_valid"] is row["trajectory_valid"] is None
        assert row["model_executed"] is False
        assert row["columns_from_one_case_only"] is True


def test_real_cross_metric_and_branch_cases_bind_original_cells_not_old_execution_columns(
    source_cases: tuple[Any, Any, Any],
) -> None:
    catalog, cases, rows = source_cases
    by_type = {case.task_type: case for case in cases}
    cross = by_type["registered_cross_metric_comparison"]
    branch = by_type["derived_growth_absolute_spread"]
    assert [node.operator_id for node in cross.instantiation.program.nodes] == [
        "registered_compare"
    ]
    assert cross.instantiation.program.nodes[0].parameters == {
        "registered_pair": "revenue/operating_income"
    }
    assert branch.case_id == "branch_cdw_fy2015_fy2016"
    assert len(branch.instantiation.program.nodes) == 8
    assert (
        derive_program_depth_metrics(
            branch.instantiation.program, catalog.registry
        ).semantic_operation_depth
        == 3
    )
    assert {item.provenance.source_record_id for item in branch.bundle.evidence} == {
        "CDW/2017/page_38.pdf-1"
    }
    source_rows = {row["case_id"]: row for row in rows if row["compiled"]}
    for case in cases:
        binding = case.source_binding
        assert binding["source_bindable"] is True
        assert binding["source_scope"]["unique_cell_count"] == 14
        assert binding["source_scope"]["original_branch_binding_count"] == 9
        assert binding["source_scope"]["original_uninstantiated_serial_count"] == 3
        assert binding["old_execution_results_are_new_protocol_coverage"] is False
        assert binding["evidence_bundle_hash"] == case.bundle.bundle_hash
        assert all(item.source.source_id == domain.ARCHIVE_ID for item in case.bundle.evidence)
        row = source_rows[case.case_id]
        assert row["task_id"] == case.task.task_id
        assert row["source_binding_id"] == binding["id"]
        assert row["evidence_bundle_id"] == case.bundle.bundle_id
        assert row["program_id"] == case.instantiation.program.program_id


def test_multiple_source_instances_keep_each_coverage_row_attached_to_its_own_case() -> None:
    catalog = domain.FinanceQACatalog()
    requested = ("registered_cross_metric_comparison", "derived_growth_absolute_spread")
    cases, rows = catalog.frozen_source_cases(ROOT, requested, limit_per_type=2)
    assert len(cases) == len(rows) == 4
    assert Counter(row["task_type"] for row in rows) == dict.fromkeys(requested, 2)
    assert len({case.case_id for case in cases}) == 4
    by_id = {case.case_id: case for case in cases}
    for row in rows:
        case = by_id[row["case_id"]]
        assert row == case.coverage_row()
        assert row["task_id"] == case.task.task_id
        assert row["evidence_bundle_hash"] == case.bundle.bundle_hash


def test_source_discovery_and_compilation_are_deterministic(
    source_cases: tuple[Any, Any, Any],
) -> None:
    _, cases, rows = source_cases
    second_cases, second_rows = domain.FinanceQACatalog().frozen_source_cases(ROOT)
    assert second_rows == rows
    assert [
        (case.task.task_hash, case.resolution, case.source_binding) for case in second_cases
    ] == [(case.task.task_hash, case.resolution, case.source_binding) for case in cases]


@pytest.mark.parametrize(
    "member", ["artifact_manifest.json", *[item[0] for item in domain.SOURCE_MEMBERS], "archive"]
)
def test_frozen_source_or_manifest_byte_drift_is_rejected(
    member: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual_read = domain._read
    target = (
        ROOT / domain.ARCHIVE_PATH
        if member == "archive"
        else ROOT / domain.FROZEN_SOURCE_DIRECTORY / member
    )

    def changed(path: Path) -> bytes:
        raw = actual_read(path)
        return b"!" + raw[1:] if path == target.resolve() else raw

    monkeypatch.setattr(domain, "_read", changed)
    with pytest.raises(domain.CatalogAdmissionError):
        domain.FinanceQACatalog().frozen_source_cases(ROOT)


def test_source_evidence_rewrite_cannot_keep_real_source_status(
    source_cases: tuple[Any, Any, Any],
) -> None:
    catalog, cases, _ = source_cases
    case = next(case for case in cases if case.task_type == "registered_cross_metric_comparison")
    old = case.bundle.evidence[0]
    altered = old.model_copy(
        update={"payload": old.payload.model_copy(update={"value": Decimal("0")})}
    )
    bundle = case.bundle.model_copy(update={"evidence": (altered, *case.bundle.evidence[1:])})
    with pytest.raises(domain.CatalogAdmissionError, match="catalog.source_evidence_substitution"):
        catalog.compile(
            case.task_type,
            bundle,
            case.instantiation.binding.role_bindings,
            case_id=case.case_id,
            source_binding=case.source_binding,
        )


def test_artificial_gross_margin_target_fixture_cannot_fill_real_source_gap(
    controlled_inputs: dict[str, Any],
) -> None:
    catalog = domain.FinanceQACatalog()
    bundle, _ = controlled_inputs["registered_margin_target_gap"]
    with pytest.raises(domain.CatalogAdmissionError, match="catalog.source_evidence_substitution"):
        catalog.bind_frozen_source(ROOT, bundle, case_id="no-invented-source-target")
    cases, rows = catalog.frozen_source_cases(ROOT, ("registered_margin_target_gap",))
    assert cases == [] and rows[0]["source_bindable"] is rows[0]["compiled"] is False


def test_swapping_registered_pair_direction_is_not_downgraded_to_plain_compare(
    source_cases: tuple[Any, Any, Any],
) -> None:
    catalog, cases, _ = source_cases
    case = next(case for case in cases if case.task_type == "registered_cross_metric_comparison")
    roles = case.instantiation.binding.role_bindings
    swapped = {"left_metric": roles["right_metric"], "right_metric": roles["left_metric"]}
    with pytest.raises(domain.CatalogAdmissionError, match="catalog.compilation_rejected"):
        catalog.compile(
            case.task_type,
            case.bundle,
            swapped,
            case_id=case.case_id,
            source_binding=case.source_binding,
        )


def test_registry_missing_registered_compare_or_depth_operations_is_rejected() -> None:
    with pytest.raises(domain.CatalogAdmissionError, match="catalog.registry_closure"):
        domain.FinanceQACatalog(default_registry())


def test_catalog_supports_additional_adapter_family_and_keeps_injected_extra_operations(
    controlled_inputs: dict[str, Any],
) -> None:
    registry = domain.catalog_operation_registry()
    extra = replace(
        registry.require("lookup"),
        operator_id="test_share_lookup",
        verifier_id="test_share_lookup.oracle.v1",
    )
    registry.register(extra)
    catalog = domain.FinanceQACatalog(registry)
    catalog.register_adapter_family(
        "test_share", "test.share.adapter.v1", ("test_share_lookup",), "test.share.contract.v1"
    )
    assert catalog.registry is registry
    assert catalog.descriptor["total_task_count"] == 11
    resolved = catalog.resolve("test_share")
    assert resolved.pattern is resolved.runtime is None
    assert resolved.registration["compilation_kind"] == "external_adapter"
    assert registry.require("test_share_lookup") is extra
    bundle, roles = controlled_inputs["fact_retrieval"]
    with pytest.raises(domain.CatalogAdmissionError, match="external_adapter_compilation_required"):
        catalog.compile("test_share", bundle, roles)
    case = catalog.compile("fact_retrieval", bundle, roles)
    assert any(
        row["operator_id"] == "test_share_lookup" for row in case.resolution["registry_manifest"]
    )
    with pytest.raises(domain.CatalogAdmissionError, match="catalog.duplicate_task"):
        catalog.register_adapter_family("test_share", "other", ("lookup",), "other")


def test_source_binding_and_catalog_resolution_cannot_be_spliced_across_cases(
    source_cases: tuple[Any, Any, Any],
) -> None:
    catalog, cases, _ = source_cases
    first, second = cases[:2]
    with pytest.raises(domain.CatalogAdmissionError, match="catalog.compiled_case_binding"):
        catalog.admit_case(replace(first, resolution=second.resolution))
    with pytest.raises(domain.CatalogAdmissionError, match="catalog.source_binding_identity"):
        catalog.admit_case(replace(first, case_id=first.case_id + ".different-instance"))
    changed = copy.deepcopy(first.source_binding)
    changed["source_bindable"] = False
    with pytest.raises(domain.CatalogAdmissionError, match="catalog.source_binding_identity"):
        catalog.admit_case(replace(first, source_binding=changed))


def test_legacy_catalog_bytes_and_identity_remain_unmodified(
    original_bytes: dict[Path, str],
) -> None:
    raw = (ROOT / OLD_DESCRIPTOR).read_bytes()
    assert len(raw) == 20_728
    assert domain._sha(raw) == "b598c8f4f6f2374d515894083d9ae7aa1f3d452ec544cddfbb53ed471659eb56"
    old = json.loads(raw)
    new = domain.FinanceQACatalog().descriptor
    assert old["catalog_id"] != new["id"]
    assert old["preflight_only"] is True and old["catalog_promoted"] is False
    assert new["old_experimental_catalog_or_artifacts_modified"] is False
    assert {path: domain._sha(path.read_bytes()) for path in original_bytes} == original_bytes


def test_domain_catalog_does_not_import_an_old_preflight_or_candidate_generator() -> None:
    tree = ast.parse(Path(domain.__file__).read_text())
    modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(name.endswith((".preflight", ".candidate", ".engine")) for name in modules)
    assert not any("catalog_integration.catalog" in name for name in modules)


@pytest.mark.parametrize(
    "requested,limit",
    [
        ((), 1),
        (("unknown",), 1),
        (("fact_retrieval",), 0),
        (("fact_retrieval", "fact_retrieval"), 1),
    ],
)
def test_invalid_source_requests_are_rejected(requested: tuple[str, ...], limit: int) -> None:
    with pytest.raises(domain.CatalogAdmissionError):
        domain.FinanceQACatalog().frozen_source_cases(ROOT, requested, limit)
