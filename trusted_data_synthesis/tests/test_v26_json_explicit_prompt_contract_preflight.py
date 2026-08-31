from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_explicit_prompt_contract_preflight as preflight,
)

EXTERNAL_AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/488ab1e6-bdc3-4367-a24a-9717ace4fcbb/pasted-text.txt"
)
V179_MANIFEST = Path(
    "artifacts/vtdo_experiment/"
    "finance_v26_179_job_bound_multistep_outcome_preflight_v1_20260830/"
    "development_job_manifest.json"
)


def _package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _source_identity() -> tuple[str, str]:
    repository = _package_root().parent
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ("git", "show", "-s", "--format=%T", commit),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return commit, tree


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[preflight.BuildProducts, Path]:
    commit, tree = _source_identity()
    output = tmp_path_factory.mktemp("v26-192") / "formal"
    products = preflight.build(
        package_root=_package_root(),
        output_dir=output,
        external_audit_path=EXTERNAL_AUDIT,
        source_commit=commit,
        source_tree=tree,
    )
    return products, output


def test_fresh_identity_chain_and_exact_denominator(
    built: tuple[preflight.BuildProducts, Path],
) -> None:
    products, _ = built
    old = json.loads((_package_root() / V179_MANIFEST).read_text())
    old_job_ids = {item["job_id"] for item in old["jobs"]}
    old_raw = {item["raw_namespace"] for item in old["jobs"]}
    old_result = {item["result_namespace"] for item in old["jobs"]}
    assert len(products.package_catalog.packages) == 32
    assert len(products.manifest.jobs) == 192
    assert {item.source_job_id for item in products.manifest.jobs} == old_job_ids
    assert not ({item.job_id for item in products.manifest.jobs} & old_job_ids)
    assert not ({item.raw_namespace for item in products.manifest.jobs} & old_raw)
    assert not ({item.result_namespace for item in products.manifest.jobs} & old_result)
    assert products.profile.profile_id != products.profile.source_profile_id
    assert all(
        item.runner_package_id != item.source_runner_package_id
        for item in products.package_catalog.packages
    )


def test_formal_prompt_census_closes_all_reachable_phases(
    built: tuple[preflight.BuildProducts, Path],
) -> None:
    products, output = built
    census = products.census
    assert len(census.rows) == 792
    assert census.first_action_prompt_count == 192
    assert census.subsequent_action_prompt_count == 288
    assert census.correction_prompt_count == 120
    assert census.final_prompt_count == 192
    assert census.old_first_prompt_json_token_present_count == 0
    assert census.old_first_prompt_json_token_absent_count == 192
    assert census.new_json_token_present_count == 792
    assert census.response_format_pair_count == 792
    assert census.prompt_core_preservation_count == 792
    assert all(
        item.request_body_fields == tuple(sorted(item.request_body_fields)) for item in census.rows
    )
    assert (output / "prompt_json_contract_census.json").is_file()
    artifact_paths = {item["relative_path"] for item in products.artifact_manifest["members"]}
    assert "prompt_json_contract_census.json" in artifact_paths


def test_scripted_runner_completes_action_correction_and_final(
    built: tuple[preflight.BuildProducts, Path],
) -> None:
    products, _ = built
    audit = products.preflight
    assert audit.exact_fresh_job_count == 192
    assert audit.primary_action_prompt_count == 480
    assert audit.primary_action_abi_parse_count == 480
    assert audit.primary_runtime_step_count == 480
    assert audit.correction_prompt_count == 120
    assert audit.correction_first_rejection_step_count == 120
    assert audit.correction_reference_abi_parse_count == 120
    assert audit.correction_reference_commit_count == 120
    assert audit.final_prompt_count == 192
    assert audit.final_abi_parse_count == 192
    assert audit.qualified_valid_count == 192
    assert audit.provider_calls == 0
    assert audit.development_model_outcomes == 0


def test_preexisting_result_identity_drift_is_narrow_and_not_hidden(
    built: tuple[preflight.BuildProducts, Path],
) -> None:
    products, _ = built
    audit = products.preflight
    assert audit.source_result_identity_match_count == 144
    assert audit.source_result_identity_drift_count == 48
    assert audit.source_result_identity_drift_capability_families == ("semantic_reconciliation",)
    assert audit.source_result_identity_match_is_prompt_gate is False
    assert products.semantic.historical_source_result_identity_drift_is_preexisting
    assert products.semantic.task_semantic_change_count == 0
    assert products.semantic.candidate_change_count == 0
    assert products.semantic.schedule_change_count == 0


def test_destructive_controls_and_downstream_boundary(
    built: tuple[preflight.BuildProducts, Path],
) -> None:
    products, _ = built
    assert products.destructive.attempted_count == 12
    assert products.destructive.rejected_count == 12
    assert products.destructive.accepted_count == 0
    assert products.report["all_gates_passed"] is True
    assert products.report["provider_calls"] == 0
    assert products.report["development_model_outcomes"] == 0
    assert products.report["online_development_execution_authorized"] is False
    assert products.report["next_stage"] == preflight.NEXT_STAGE


def test_authorization_credential_and_no_replace_fail_closed(
    built: tuple[preflight.BuildProducts, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, output = built
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("wrong")
    commit, tree = _source_identity()
    with pytest.raises(ValueError, match="audit bytes differ"):
        preflight.build(
            package_root=_package_root(),
            output_dir=tmp_path / "wrong-output",
            external_audit_path=wrong,
            source_commit=commit,
            source_tree=tree,
        )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-be-read")
    with pytest.raises(ValueError, match="credential removal"):
        preflight.build(
            package_root=_package_root(),
            output_dir=tmp_path / "credential-output",
            external_audit_path=EXTERNAL_AUDIT,
            source_commit=commit,
            source_tree=tree,
        )
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    with pytest.raises(FileExistsError):
        preflight.build(
            package_root=_package_root(),
            output_dir=output,
            external_audit_path=EXTERNAL_AUDIT,
            source_commit=commit,
            source_tree=tree,
        )
    assert before == {path.name: path.read_bytes() for path in output.iterdir()}


def test_byte_identical_rebuild(
    built: tuple[preflight.BuildProducts, Path], tmp_path: Path
) -> None:
    _, first = built
    commit, tree = _source_identity()
    second = tmp_path / "rebuilt"
    preflight.build(
        package_root=_package_root(),
        output_dir=second,
        external_audit_path=EXTERNAL_AUDIT,
        source_commit=commit,
        source_tree=tree,
    )
    first_files = {path.name: path.read_bytes() for path in first.iterdir()}
    second_files = {path.name: path.read_bytes() for path in second.iterdir()}
    assert first_files == second_files
