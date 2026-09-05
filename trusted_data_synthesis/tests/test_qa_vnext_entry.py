"""Public Finance QA entry integration: real source coverage is never filled from old reports."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.core.task.program_depth import derive_program_depth_metrics
from trusted_synthesis.domains.finance.qa_vnext import catalog as domain
from trusted_synthesis.domains.finance.qa_vnext.callbacks import (
    ExternalJSONCallback,
    PublicFixtureCallback,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runner import (
    ENTRY_VERSION,
    build_catalog,
    run_finance_qa_vnext,
)
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import SHARE_FAMILY
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import PARENT

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "trusted_data_synthesis"
PROGRAM_TYPES = {
    "fact_retrieval",
    "registered_cross_metric_comparison",
    "temporal_growth",
    "temporal_average",
    "temporal_absolute_change",
    "registered_ratio",
    "derived_growth_absolute_spread",
}
SOURCE_GAPS = {"comparison", "derived_growth_comparison", "registered_margin_target_gap"}
ALL_TYPES = PROGRAM_TYPES | SOURCE_GAPS | {SHARE_FAMILY}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


@pytest.fixture(scope="module", autouse=True)
def existing_sources_unchanged() -> Iterator[None]:
    paths = [ROOT / domain.ARCHIVE_PATH]
    for directory in (domain.FROZEN_SOURCE_DIRECTORY, PARENT):
        paths.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())
    snapshot = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    yield
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths} == snapshot


@pytest.fixture(scope="module")
def default_entry(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    output = tmp_path_factory.mktemp("qa_entry") / "default"
    return output, run_finance_qa_vnext(ROOT, output)


def test_default_entry_declares_all_eleven_families_and_qualifies_nine_real_sessions(
    default_entry: tuple[Path, dict[str, Any]],
) -> None:
    directory, report = default_entry
    assert report["entry_version"] == ENTRY_VERSION
    assert set(report["registered_task_types"]) == ALL_TYPES
    assert report["requested_task_types"] == report["registered_task_types"]
    assert len(report["registered_task_types"]) == 11
    assert report["executed_case_count"] == report["qualified_case_count"] == 9
    assert report["all_instantiated_cases_passed"] is True
    rows = report["coverage_rows"]
    assert len(rows) == 9 and len({row["case_id"] for row in rows}) == 9
    assert {row["task_type"] for row in rows} == PROGRAM_TYPES | {SHARE_FAMILY}
    assert sum(row["task_type"] == SHARE_FAMILY for row in rows) == 2
    assert all(row["registered"] and row["source_bindable"] and row["compiled"] for row in rows)
    assert all(
        row["new_protocol_executable"]
        and row["qa_valid"]
        and row["trajectory_valid"]
        and row["qualified"]
        for row in rows
    )
    assert all(row["origin"] == "fixture" and row["model_executed"] is False for row in rows)
    assert read_json(directory / "report.json") == report
    entry = read_json(directory / "entry.json")
    assert entry["requested_task_types"] == report["requested_task_types"]
    assert entry["default_requests_all_registered_families"] is True
    assert entry["retrospective_candidate_generator_used"] is False
    assert read_json(directory / "catalog.json")["id"] == report["catalog_id"]


def test_three_unavailable_families_remain_uninstantiated_instead_of_borrowing_fixture_columns(
    default_entry: tuple[Path, dict[str, Any]],
) -> None:
    directory, report = default_entry
    assert set(report["uninstantiated_task_types"]) == SOURCE_GAPS
    gaps = report["uninstantiated_rows"]
    assert len(gaps) == 3 and {row["task_type"] for row in gaps} == SOURCE_GAPS
    for row in gaps:
        assert row["registered"] is True
        assert row["source_bindable"] is False and row["compiled"] is False
        assert row["source_binding_status"] == row["compilation_status"] == "not_instantiated"
        assert row["case_id"] is None and row["task_id"] is None
        assert row["source_binding_id"] is None
        assert row["new_protocol_executable"] is None
        assert row["qa_valid"] is None and row["trajectory_valid"] is None
        assert row["model_executed"] is False
        assert row["columns_from_one_case_only"] is True
        expected = (
            "authoritative_gross_margin_target_evidence_absent"
            if row["task_type"] == "registered_margin_target_gap"
            else "no_admissible_binding_in_this_frozen_source_pool"
        )
        assert row["reason"] == expected
    assert len(tuple((directory / "sessions").iterdir())) == 9


def test_every_coverage_column_binds_the_same_new_case_session_and_independent_audit(
    default_entry: tuple[Path, dict[str, Any]],
) -> None:
    directory, report = default_entry
    catalog = build_catalog(ROOT)
    cases, _ = catalog.frozen_source_cases(ROOT)
    compiled = {case.case_id: case for case in cases}
    for row in report["coverage_rows"]:
        session_dir = directory / "sessions" / row["case_id"]
        context = read_json(session_dir / "context.json")
        session = read_json(session_dir / "session.json")
        audit = read_json(directory / "validations" / (row["case_id"] + ".json"))
        assert (
            row["catalog_id"] == context["catalog_resolution"]["catalog_id"] == report["catalog_id"]
        )
        assert row["context_id"] == context["id"] == session["context_id"] == audit["context_id"]
        assert row["session_id"] == session["id"] == audit["session_id"]
        assert row["validation_id"] == audit["id"]
        assert row["task_id"] == context["task_id"] == audit["task_id"]
        assert row["task_type"] == context["task_type"] == audit["task_type"]
        assert row["source_binding_id"] == context["source_binding"]["id"]
        assert row["registry_hash"] == session["registry_hash"] == audit["registry_hash"]
        assert row["actual_decision_graph_id"] == audit["actual_decision_graph"]["id"]
        assert row["actual_depth_metrics"] == audit["depth_metrics"]
        assert audit["qualified"] is True and audit["errors"] == []
        assert audit["runtime_executions_by_audit"] == audit["adapter_execute_calls_by_audit"] == 0
        assert audit["independent_output_checks"] == audit["action_count"]
        assert row["columns_from_one_case_only"] is True
        assert row["previous_experiment_columns_substituted"] is False
        assert (session_dir / "session.json").read_bytes() == canonical_json_bytes(session)
        if row["task_type"] in PROGRAM_TYPES:
            case = compiled[row["case_id"]]
            assert row["task_id"] == case.task.task_id
            assert row["source_binding_id"] == case.source_binding["id"]
            assert context["public_task"] == case.task.public.model_dump(mode="json")
            assert row["program_depth_metrics"] == derive_program_depth_metrics(
                case.instantiation.program, catalog.registry
            ).model_dump(mode="json")
        else:
            assert row["program_depth_metrics"] is None
            assert row["compilation_status"] == "adapter_materialized_not_TaskPattern_compiled"


def test_actual_branch_depth_is_three_without_counting_lookups_or_callback_turns(
    default_entry: tuple[Path, dict[str, Any]],
) -> None:
    directory, report = default_entry
    row = next(
        item
        for item in report["coverage_rows"]
        if item["task_type"] == "derived_growth_absolute_spread"
    )
    audit = read_json(directory / "validations" / (row["case_id"] + ".json"))
    assert row["program_depth_metrics"]["semantic_operation_depth"] == 3
    assert row["actual_depth_metrics"]["actual_action_dependency_semantic_depth"] == 3
    assert row["actual_depth_metrics"]["actual_action_dependency_structural_depth"] == 4
    assert row["actual_depth_metrics"]["observable_choice_dependency_depth"] == 0
    assert row["actual_depth_metrics"]["callback_count_used_as_depth"] is False
    assert row["actual_depth_metrics"]["model_hidden_or_critical_reasoning_depth_measured"] is False
    assert audit["action_count"] == 8 and audit["callback_count"] == 17
    nodes = audit["actual_decision_graph"]["nodes"]
    assert len(nodes) == 8
    assert sum(node["program_role"] == "transparent_projection" for node in nodes) == 4
    assert sum(node["program_role"] == "semantic" for node in nodes) == 4
    assert row["actual_depth_metrics"]["actual_action_dependency_semantic_depth"] not in {8, 17}


def test_share_routes_share_one_task_but_have_a_witnessed_finite_difference(
    default_entry: tuple[Path, dict[str, Any]],
) -> None:
    directory, report = default_entry
    rows = [row for row in report["coverage_rows"] if row["task_type"] == SHARE_FAMILY]
    assert len(rows) == 2
    assert rows[0]["context_id"] == rows[1]["context_id"]
    assert rows[0]["task_id"] == rows[1]["task_id"]
    assert rows[0]["session_id"] != rows[1]["session_id"]
    sessions = [read_json(directory / "sessions" / row["case_id"] / "session.json") for row in rows]
    assert all(
        session["final"]["answer"]["result"] == {"value": "93.508458", "unit": "percent"}
        for session in sessions
    )
    assert sorted(session["terminal_state"]["action_count"] for session in sessions) == [2, 3]
    assert len(report["same_task_comparisons"]) == 1
    comparison = report["same_task_comparisons"][0]
    assert {comparison["left_audit_id"], comparison["right_audit_id"]} == {
        row["validation_id"] for row in rows
    }
    assert comparison["relation"] == "not_equivalent" and comparison["equivalent"] is False
    assert comparison["correspondence"] is None
    assert comparison["retained_difference_witness"] is not None
    assert comparison["content_hash_is_relation_authority"] is False
    assert comparison["historical_state_ids_or_assignments_reused"] is False


def test_entry_report_preserves_non_claims_and_training_pause(
    default_entry: tuple[Path, dict[str, Any]],
) -> None:
    _, report = default_entry
    assert report["source_scope"] == "existing frozen sources only"
    assert report["fixture_regression"] is True
    assert report["provider_calls"] == report["new_verified_model_samples"] == 0
    assert report["GPU_jobs"] == report["Student_parameter_updates"] == 0
    assert report["old_training_mainline"] == "remains_paused"
    for field in (
        "new_protocol_model_coverage_claimed",
        "all_registered_families_have_source_claimed",
        "accepted_claim_revision_supported",
        "uncertainty_resolution_beyond_empty_current_cases_claimed",
        "arbitrary_QA_or_universal_mapper_claimed",
        "production_or_training_release",
        "older_share_assignments_and_empirical_probabilities_modified",
    ):
        assert report[field] is False


@pytest.mark.parametrize(
    "selected,count,gaps",
    [
        ((SHARE_FAMILY,), 2, set()),
        (("fact_retrieval", "derived_growth_absolute_spread"), 2, set()),
        (("fact_retrieval", SHARE_FAMILY), 3, set()),
        (("comparison",), 0, {"comparison"}),
    ],
)
def test_explicit_subsets_execute_only_the_requested_source_bound_families(
    tmp_path: Path, selected: tuple[str, ...], count: int, gaps: set[str]
) -> None:
    output = tmp_path / "entry"
    report = run_finance_qa_vnext(ROOT, output, task_types=selected)
    assert report["requested_task_types"] == list(selected)
    assert set(report["registered_task_types"]) == ALL_TYPES
    assert report["executed_case_count"] == report["qualified_case_count"] == count
    assert {row["task_type"] for row in report["coverage_rows"]} == set(selected) - gaps
    assert set(report["uninstantiated_task_types"]) == gaps
    assert report["all_instantiated_cases_passed"] is bool(count)
    assert read_json(output / "entry.json")["requested_task_types"] == list(selected)
    assert len(report["same_task_comparisons"]) == int(SHARE_FAMILY in selected)


def test_unknown_type_is_rejected_before_output_or_execution(tmp_path: Path) -> None:
    output = tmp_path / "unknown"
    with pytest.raises(domain.CatalogAdmissionError, match="catalog.task_lookup"):
        run_finance_qa_vnext(ROOT, output, task_types=("nonexistent_finance_type",))
    assert not output.exists()


def test_existing_entry_output_is_not_overwritten(
    default_entry: tuple[Path, dict[str, Any]],
) -> None:
    directory, _ = default_entry
    before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }
    with pytest.raises(ProtocolError, match="entry.immutable_output"):
        run_finance_qa_vnext(ROOT, directory)
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before} == before


def test_callback_factory_is_public_and_does_not_gain_verified_model_attribution(
    tmp_path: Path,
) -> None:
    contexts = []
    fixture = PublicFixtureCallback()

    def factory(context: dict[str, Any]) -> ExternalJSONCallback:
        contexts.append(context)
        return ExternalJSONCallback(fixture.generate, client_id="entry-test-local-json")

    report = run_finance_qa_vnext(
        ROOT, tmp_path / "external", task_types=(SHARE_FAMILY,), callback_factory=factory
    )
    assert len(contexts) == 1 and contexts[0]["task_type"] == SHARE_FAMILY
    assert "oracle" not in contexts[0]
    assert report["executed_case_count"] == report["qualified_case_count"] == 1
    assert report["fixture_regression"] is False
    assert report["provider_calls"] is None
    assert report["new_verified_model_samples"] == 0
    assert report["new_protocol_model_coverage_claimed"] is False
    assert report["coverage_rows"][0]["origin"] == "external_callback"
    assert report["coverage_rows"][0]["model_executed"] is False
    assert report["same_task_comparisons"] == []


def run_cli(output: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "trusted_synthesis.cli",
            "finance-qa-vnext",
            "--repo-root",
            str(ROOT),
            "--output-dir",
            str(output),
            *arguments,
        ],
        cwd=PACKAGE,
        env={**os.environ, "PYTHONPATH": str(PACKAGE / "src")},
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def test_actual_cli_share_only_materializes_the_same_entry_and_prints_report(
    tmp_path: Path,
) -> None:
    output = tmp_path / "cli"
    result = run_cli(output, "--task-type", SHARE_FAMILY)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report == read_json(output / "report.json")
    assert report["entry_version"] == ENTRY_VERSION
    assert report["requested_task_types"] == [SHARE_FAMILY]
    assert report["executed_case_count"] == report["qualified_case_count"] == 2
    assert len(tuple((output / "sessions").iterdir())) == 2


def test_actual_cli_repeated_task_flags_select_only_those_families(tmp_path: Path) -> None:
    output, destination = tmp_path / "cli", tmp_path / "emitted.json"
    result = run_cli(
        output,
        "--task-type",
        "fact_retrieval",
        "--task-type",
        SHARE_FAMILY,
        "--output",
        str(destination),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    report = read_json(destination)
    assert report == read_json(output / "report.json")
    assert report["requested_task_types"] == ["fact_retrieval", SHARE_FAMILY]
    assert report["executed_case_count"] == report["qualified_case_count"] == 3
    assert {row["task_type"] for row in report["coverage_rows"]} == {"fact_retrieval", SHARE_FAMILY}


def test_actual_cli_unknown_type_fails_without_creating_entry(tmp_path: Path) -> None:
    output = tmp_path / "unknown"
    result = run_cli(output, "--task-type", "nonexistent_finance_type")
    assert result.returncode != 0
    assert "catalog.task_lookup" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    "selected", [(), ("fact_retrieval", "fact_retrieval"), (SHARE_FAMILY, SHARE_FAMILY)]
)
def test_empty_or_duplicate_selection_is_rejected_without_implicit_expansion(
    tmp_path: Path, selected: tuple[str, ...]
) -> None:
    output = tmp_path / "invalid_selection"
    with pytest.raises(ProtocolError, match="entry.task_selection"):
        run_finance_qa_vnext(ROOT, output, task_types=selected)
    assert not output.exists()


def test_entry_manifest_covers_every_saved_report_session_manifest_and_raw_submission(
    default_entry: tuple[Path, dict[str, Any]],
) -> None:
    directory, report = default_entry
    manifest = read_json(directory / "manifest.json")
    assert manifest["entry_report_id"] == report["id"]
    assert manifest["self_excluding"] is True
    assert manifest["covers_all_session_manifests_and_raw_submissions"] is True
    paths = [member["path"] for member in manifest["members"]]
    assert len(paths) == len(set(paths)) and paths == sorted(paths)
    expected = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path != directory / "manifest.json"
    }
    assert set(paths) == expected
    assert {"report.json", "entry.json", "catalog.json", "protocol.json"} <= set(paths)
    assert sum(path.endswith("/manifest.json") for path in paths) == 9
    assert any(path.endswith("_response.txt") for path in paths)
    for member in manifest["members"]:
        raw = (directory / member["path"]).read_bytes()
        assert member["sha256"] == hashlib.sha256(raw).hexdigest()
        assert member["bytes"] == len(raw)


@pytest.mark.parametrize("relative", ["report.json", "nested/emitted.json"])
def test_cli_rejects_report_output_inside_immutable_entry_before_writing(
    tmp_path: Path, relative: str
) -> None:
    directory = tmp_path / "immutable"
    result = run_cli(directory, "--task-type", SHARE_FAMILY, "--output", str(directory / relative))
    assert result.returncode == 2
    assert "--output must be outside the immutable --output-dir" in result.stderr
    assert not directory.exists()
