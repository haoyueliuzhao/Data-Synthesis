# ruff: noqa: E501
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_preflight as stage,
)
from trusted_synthesis.experiments.vtdo_experiment.json_explicit_authoritative_execution_kernel import (
    AuthoritativeJsonExplicitExecutionKernel,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
AUDIT_PATH = PACKAGE_ROOT / "tests/fixtures/v26_193_authoritative_execution_kernel_audit.txt"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, models.PreflightReport]:
    output = tmp_path_factory.mktemp("v26-194") / "formal"
    report = stage.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=AUDIT_PATH,
        output_dir=output,
    )
    return output, report


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_external_anchor_runtime_choice_and_fresh_parent_chain(
    built: tuple[Path, models.PreflightReport],
) -> None:
    output, report = built
    anchor = _load(output / "external_v26_193_anchor.json")
    semantic = _load(output / "runtime_semantic_contract.json")
    manifest = _load(output / "authoritative_development_manifest.json")
    runner = _load(output / "authoritative_runner_contract.json")
    execution = _load(output / "authoritative_execution_contract.json")
    assert anchor["source_commit"] == "b5b21ee90926713773d4028028ec67c7a7d40d4e"
    assert anchor["exact_file_count"] == anchor["exact_file_match_count"] == 12
    assert semantic["experiment_condition_changed"] is True
    assert semantic["semantic_equivalence_claimed"] is False
    assert semantic["full_public_event_payload_drift_count"] == 48
    assert semantic["public_effect_match_count"] == 48
    assert len(manifest["jobs"]) == 192
    assert len(set(manifest["expected_job_ids"])) == 192
    assert runner["scripted_reference_only"] is False
    assert runner["fixture_response_in_production_input"] is False
    assert execution["fresh_outcome_authority_materialized"] is False
    assert report.online_development_execution_authorized is False


def test_certified_kernel_invocation_and_all_controls_pass(
    built: tuple[Path, models.PreflightReport],
) -> None:
    output, _ = built
    invocation = _load(output / "kernel_invocation_audit.json")
    destructive = _load(output / "destructive_audit.json")
    static = _load(output / "static_audit.json")
    assert invocation["registered_invocation_count"] == 792
    assert invocation["request_binding_certificate_count"] == 792
    assert invocation["transmitted_body_hash_match_count"] == 792
    assert invocation["privacy_envelope_before_semantic_parse_count"] == 792
    assert invocation["raw_writer_completion_count"] == 192
    assert destructive["predecessor_attack_regression_pass_count"] == 14
    assert destructive["rejection_count"] == 12
    assert destructive["accepted_count"] == 0
    assert static["failed_count"] == 0
    names = {item["attack_name"] for item in destructive["attacks"]}
    assert names == {
        "same_runner_id_changed_runner_source",
        "same_job_id_old_current_runtime_swap",
        "transport_mutates_body_after_validation",
        "transport_ignores_validated_body",
        "direct_client_route_bypasses_renderer",
        "missing_or_crossed_stage_one_request_certificate",
        "wrong_dynamic_resource_certificate",
        "privacy_journal_written_after_parsing",
        "raw_result_writer_bypass",
        "fixture_response_enters_production_runner_input",
        "forty_eight_drift_result_parent_substitution",
        "artifact_root_report_source_commit_joint_rehash",
    }


def test_production_runner_api_has_no_fixture_response() -> None:
    signature = inspect.signature(AuthoritativeJsonExplicitExecutionKernel.invoke)
    assert "fixture_response" not in signature.parameters
    assert tuple(signature.parameters) == (
        "self",
        "job_id",
        "logical_request_index",
        "prompt_kind",
        "public_attempt_phase",
        "core",
    )


def test_report_binds_sealed_evidence_root_and_distribution_is_exact(
    built: tuple[Path, models.PreflightReport],
) -> None:
    output, report = built
    evidence = models.ArtifactManifest.model_validate(
        _load(output / "sealed_evidence_manifest.json")
    )
    distribution = models.ArtifactManifest.model_validate(_load(output / "artifact_manifest.json"))
    assert report.sealed_evidence_manifest_id == evidence.manifest_id
    assert report.sealed_evidence_artifact_root == evidence.artifact_root
    observed = tuple(sorted(path.name for path in output.iterdir() if path.is_file()))
    assert observed == tuple(
        sorted((*[item.relative_path for item in distribution.members], "artifact_manifest.json"))
    )
    for member in distribution.members:
        payload = (output / member.relative_path).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == member.sha256
        assert len(payload) == member.byte_count


def test_empty_directory_rebuild_is_byte_identical(
    built: tuple[Path, models.PreflightReport], tmp_path: Path
) -> None:
    output, _ = built
    rebuilt = tmp_path / "rebuilt"
    stage.build(
        repository_root=REPOSITORY_ROOT,
        audit_path=AUDIT_PATH,
        output_dir=rebuilt,
    )
    names = tuple(sorted(path.name for path in output.iterdir() if path.is_file()))
    assert names == tuple(sorted(path.name for path in rebuilt.iterdir() if path.is_file()))
    assert all((output / name).read_bytes() == (rebuilt / name).read_bytes() for name in names)
