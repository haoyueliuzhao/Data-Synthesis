from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_outcome_authority_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
AUDIT_PATH = PACKAGE_ROOT / "tests/fixtures/v26_194_fresh_outcome_authority_audit.txt"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any]:
    output = tmp_path_factory.mktemp("v26-195") / "formal"
    report = preflight.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=AUDIT_PATH,
        output_dir=output,
    )
    return output, report


def test_exact_external_authorization_and_v194_anchor(built: tuple[Path, Any]) -> None:
    output, report = built
    anchor = _load(output / "external_v26_194_anchor.json")
    assert report.authorization_id.startswith("finance_v26_195_external_authorization:")
    assert anchor["exact_file_count"] == 22
    assert anchor["exact_file_match_count"] == 22
    assert anchor["candidate_report_values_used_as_expectations"] is False
    assert anchor["source_commit"] == "2a5b8322a94e7be84065375dd6720e532bfe05cb"
    assert anchor["source_tree"] == "3f75f98f8ad11a3a7125523ee83233b23036a82d"


def test_six_fresh_authority_layers_bind_exact_v194_jobs(
    built: tuple[Path, Any],
) -> None:
    output, report = built
    audit = _load(output / "fresh_authority_audit.json")
    assert report.fresh_layer_count == 6
    assert len(audit["materialized_layers"]) == 6
    assert audit["exact_job_parent_match_count"] == 192
    assert audit["old_v26_186_authority_identity_reuse_count"] == 0
    assert report.execution_contract_id == (
        "authoritative_execution_kernel_contract:"
        "53dccfcd1a4516ae8c79c9b64cd41193b99e8594598a25049335db565070786d"
    )


def test_exact_scripted_evidence_dag_is_nonempirical(built: tuple[Path, Any]) -> None:
    output, report = built
    evaluation = _load(output / "exact_evidence_set_evaluation.json")
    dag = _load(output / "evidence_dag_audit.json")
    assert len(tuple((output / "raw").glob("*.json"))) == 192
    assert len(tuple((output / "result").glob("*.json"))) == 192
    assert evaluation["raw_descriptor_count"] == 192
    assert evaluation["result_descriptor_count"] == 192
    assert evaluation["trace_count"] == 192
    assert evaluation["outcome_row_count"] == 192
    assert evaluation["artifact_byte_match_count"] == 384
    assert evaluation["empirical"] is False
    assert evaluation["empirical_numerator_materialized"] is False
    assert evaluation["empirical_estimate_materialized"] is False
    assert dag["old_fixture_complete_payload_rejection_count"] == 1
    assert report.provider_calls == 0
    assert report.development_model_outcomes == 0
    assert report.empirical_rows == 0
    assert report.empirical_estimates == 0


def test_outcome_writer_implementation_is_bound(built: tuple[Path, Any]) -> None:
    output, _ = built
    binding = _load(output / "outcome_writer_implementation_binding.json")
    assert [item["symbol"] for item in binding["symbols"]] == [
        "FreshOutcomeArtifactWriter",
        "FreshOutcomeArtifactWriter.write_raw",
        "FreshOutcomeArtifactWriter.write_result",
    ]
    assert binding["raw_before_result_required"] is True
    assert binding["old_fixture_complete_payload_admissible"] is False


def test_broader_outcome_attacks_and_v194_regression_reject(
    built: tuple[Path, Any],
) -> None:
    output, _ = built
    audit = _load(output / "destructive_audit.json")
    names = {item["attack_name"] for item in audit["attacks"]}
    assert audit["predecessor_execution_kernel_attack_count"] == 12
    assert audit["predecessor_execution_kernel_rejection_count"] == 12
    assert audit["attack_count"] == 23
    assert audit["rejection_count"] == 23
    assert audit["accepted_count"] == 0
    assert {
        "nested_job_model_construct_injection",
        "raw_file_byte_drift",
        "result_file_byte_drift",
        "fully_rehashed_invented_failure_locus",
        "fully_rehashed_outcome_trace_crossing",
        "duplicate_job_with_192_rows",
        "scripted_chain_promoted_to_empirical",
        "old_fixture_complete_payload",
        "noncanonical_raw_json_with_rehashed_descriptor",
    } <= names


def test_transition_requires_independent_audit_and_blocks_online(
    built: tuple[Path, Any],
) -> None:
    output, report = built
    transition = _load(output / "prospective_transition.json")
    assert report.decision == (
        "fresh_artifact_backed_outcome_authority_preflight_passed_"
        "independent_audit_required_online_execution_blocked"
    )
    assert transition["next_stage"] == (
        "fresh_artifact_backed_outcome_authority_preflight_independent_audit_only"
    )
    assert transition["online_execution_authorized"] is False
    assert transition["empirical_evaluation_authorized"] is False


def test_empty_directory_rebuild_is_byte_identical(
    built: tuple[Path, Any],
    tmp_path: Path,
) -> None:
    output, _ = built
    rebuilt = tmp_path / "rebuilt"
    preflight.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=AUDIT_PATH,
        output_dir=rebuilt,
    )
    expected = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    }
    observed = {
        path.relative_to(rebuilt).as_posix(): path.read_bytes()
        for path in rebuilt.rglob("*")
        if path.is_file()
    }
    assert observed == expected
