from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.experiments.qa_realization_vnext.release_authority import (
    QAReleaseAuthorityError,
    build_qa_release_authority_bundle,
)
from trusted_synthesis.experiments.qa_realization_vnext.release_authority_envelope import (
    FROZEN_ATTACK_IDS,
    PERMITTED_CHANGE_SURFACE,
    build_authorization,
    build_population_manifest,
    capture_runtime_environment,
)
from trusted_synthesis.experiments.qa_realization_vnext.release_authority_envelope_preflight import (  # noqa: E501
    EXECUTED_MODULE_PATH,
    _build_attack_audit,
    _build_payloads,
    _capture_attack,
    _mutated_report_payloads,
    _placeholder_controls,
    _require_exact_attack_ids,
    _run_attack_controls,
    _unrelated_exception_control,
    extract_git_archive,
    load_qa_release_authority_envelope_directory,
    validate_qa_release_authority_payloads,
    verify_source_archive_projection,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture()
def source_archive(tmp_path: Path) -> tuple[Path, Path, str, str]:
    repo = tmp_path / "repo"
    module = repo / EXECUTED_MODULE_PATH
    module.parent.mkdir(parents=True)
    module.write_text("SOURCE_MARKER = 'archive projection'\n", encoding="utf-8")
    executable = repo / "tool.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    (repo / "linked-tool").symlink_to("tool.sh")
    _git(repo.parent, "init", str(repo))
    _git(repo, "config", "user.email", "qa-authority@example.invalid")
    _git(repo, "config", "user.name", "QA Authority Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    commit_id = _git(repo, "rev-parse", "HEAD")
    tree_id = _git(repo, "rev-parse", "HEAD^{tree}")
    archive = tmp_path / "source.tar"
    _git(repo, "archive", "--format=tar", f"--output={archive}", commit_id)
    extracted = tmp_path / "extracted"
    extract_git_archive(archive, extracted)
    return archive, extracted, commit_id, tree_id


@pytest.fixture()
def envelope_context(source_archive: tuple[Path, Path, str, str]):
    archive, extracted, commit_id, tree_id = source_archive
    projection, manifest = verify_source_archive_projection(
        source_archive_path=archive,
        source_commit_id=commit_id,
        source_tree_id=tree_id,
        executed_source_root=extracted,
    )
    audit_bytes = b"external audit authorization fixture\n"
    authorization = build_authorization(
        external_audit_bytes=audit_bytes,
        source_commit_id=commit_id,
        observed_change_surface=PERMITTED_CHANGE_SURFACE,
    )
    bundle = build_qa_release_authority_bundle(
        source_tree_id=tree_id,
        source_archive_sha256=projection.source_archive_sha256,
        source_snapshot_manifest_sha256=projection.source_manifest_sha256,
    )
    population = build_population_manifest(
        authorization=authorization,
        source_projection=projection,
        bundle=bundle,
    )
    runtime = capture_runtime_environment(extracted)
    controls = _placeholder_controls()
    unrelated = _unrelated_exception_control()
    attack_audit = _build_attack_audit(controls, unrelated)
    payloads, envelope = _build_payloads(
        external_audit_bytes=audit_bytes,
        authorization=authorization,
        source_projection=projection,
        source_manifest=manifest,
        population=population,
        runtime=runtime,
        bundle=bundle,
        attack_audit=attack_audit,
    )
    return {
        "archive": archive,
        "extracted": extracted,
        "audit_bytes": audit_bytes,
        "authorization": authorization,
        "projection": projection,
        "manifest": manifest,
        "bundle": bundle,
        "population": population,
        "runtime": runtime,
        "payloads": payloads,
        "envelope": envelope,
    }


def test_git_archive_is_the_only_source_projection(
    source_archive: tuple[Path, Path, str, str],
) -> None:
    archive, extracted, commit_id, tree_id = source_archive
    projection, manifest = verify_source_archive_projection(
        source_archive_path=archive,
        source_commit_id=commit_id,
        source_tree_id=tree_id,
        executed_source_root=extracted,
    )
    assert projection.source_tree_id == tree_id
    assert projection.archive_embedded_commit_id == commit_id
    assert manifest.file_count == 3
    assert any(row.kind == "symlink" for row in manifest.files)
    assert any(row.executable for row in manifest.files)

    (extracted / EXECUTED_MODULE_PATH).write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="executed source file differs"):
        verify_source_archive_projection(
            source_archive_path=archive,
            source_commit_id=commit_id,
            source_tree_id=tree_id,
            executed_source_root=extracted,
        )


def test_population_freezes_exact_fixture_surface_and_instance_sets(envelope_context) -> None:
    population = envelope_context["population"]
    assert population.fixture_indexes == (1, 2)
    assert len(population.fixture_input_ids) == 2
    assert len(population.semantic_instance_ids) == 2
    assert len(population.members) == 6
    assert len({row.realized_package_id for row in population.members}) == 6

    single_fixture_bundle = build_qa_release_authority_bundle(
        source_tree_id=envelope_context["projection"].source_tree_id,
        source_archive_sha256=envelope_context["projection"].source_archive_sha256,
        source_snapshot_manifest_sha256=envelope_context["projection"].source_manifest_sha256,
        fixture_indexes=(1,),
    )
    changed = build_population_manifest(
        authorization=envelope_context["authorization"],
        source_projection=envelope_context["projection"],
        bundle=single_fixture_bundle,
    )
    assert changed.population_id != population.population_id


def test_envelope_loader_cross_validates_every_catalog_and_external_anchor(
    envelope_context,
    tmp_path: Path,
) -> None:
    context = envelope_context
    report = validate_qa_release_authority_payloads(
        context["payloads"],
        expected_envelope_id=context["envelope"].envelope_id,
        expected_authorization_id=context["authorization"].authorization_id,
        expected_population_id=context["population"].population_id,
        external_audit_bytes=context["audit_bytes"],
        source_archive_path=context["archive"],
    )
    assert report.status == "passed"
    assert report.exact_attack_count == len(FROZEN_ATTACK_IDS)

    attacked = _mutated_report_payloads(context["payloads"])
    with pytest.raises(QAReleaseAuthorityError) as captured:
        validate_qa_release_authority_payloads(
            attacked,
            expected_envelope_id=context["envelope"].envelope_id,
            expected_authorization_id=context["authorization"].authorization_id,
            expected_population_id=context["population"].population_id,
            external_audit_bytes=context["audit_bytes"],
            source_archive_path=context["archive"],
        )
    assert captured.value.reason_code == "report_cross_envelope_mismatch"
    assert captured.value.stage == "report"

    output = tmp_path / "published"
    write_immutable_artifact_directory(output, context["payloads"])
    audit_path = tmp_path / "external-audit.txt"
    audit_path.write_bytes(context["audit_bytes"])
    loaded = load_qa_release_authority_envelope_directory(
        output,
        expected_envelope_id=context["envelope"].envelope_id,
        expected_authorization_id=context["authorization"].authorization_id,
        expected_population_id=context["population"].population_id,
        external_audit_path=audit_path,
        source_archive_path=context["archive"],
    )
    assert loaded == report.model_dump(mode="json")
    with pytest.raises(FileExistsError):
        write_immutable_artifact_directory(output, context["payloads"])


def test_exact_attack_registry_and_actual_typed_stages(envelope_context) -> None:
    context = envelope_context
    controls = _run_attack_controls(
        bundle=context["bundle"],
        authorization=context["authorization"],
        source_projection=context["projection"],
        source_manifest=context["manifest"],
        population=context["population"],
        base_payloads=context["payloads"],
        envelope=context["envelope"],
        external_audit_bytes=context["audit_bytes"],
        source_archive_path=context["archive"],
    )
    assert tuple(row.attack_id for row in controls) == FROZEN_ATTACK_IDS
    assert len(controls) == 23
    assert all(row.actual_exception_type == "QAReleaseAuthorityError" for row in controls)
    assert all(row.target_validator_reached for row in controls)
    assert all(row.counted_as_rejection_evidence for row in controls)
    with pytest.raises(ValueError, match="registry membership or order"):
        _require_exact_attack_ids(FROZEN_ATTACK_IDS[:-1])


def test_same_exception_phrase_from_wrong_validator_is_not_counted() -> None:
    control = _capture_attack(
        "wrong_validator_probe",
        "runtime_semantic_contract_mismatch",
        "runtime_contracts",
        lambda: (_ for _ in ()).throw(ValueError("runtime_semantic_contract_mismatch")),
    )
    assert control.actual_exception_type == "ValueError"
    assert control.actual_stage == ""
    assert control.counted_as_rejection_evidence is False


def test_report_and_markdown_are_content_addressed(envelope_context) -> None:
    payloads = envelope_context["payloads"]
    envelope = envelope_context["envelope"]
    report = json.loads(payloads["report.json"])
    assert report["report_id"] == envelope.report.report_id
    assert len(payloads["report.md"]) == envelope.report_markdown_byte_count
    assert report["provider_calls"] == 0
    assert report["archive_backed_pilot_authorized"] is False
    assert report["production_authorized"] is False
