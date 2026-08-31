from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_route_http400_request_contract_root_cause_audit as audit,
)

ATTACHMENT = Path(
    "/home/zhuxinrui/.codex/attachments/9df1d9dd-70f5-4468-b20e-30b374cb89c2/pasted-text.txt"
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


def _external_audit() -> Path:
    override = os.environ.get("V26_190_EXTERNAL_AUDIT")
    if override:
        return Path(override)
    formal = _package_root() / audit.OUTPUT_DIR / "external_v26_189_latest_audit.txt"
    return formal if formal.exists() else ATTACHMENT


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[audit.BuildProducts, Path]:
    commit, tree = _source_identity()
    output = tmp_path_factory.mktemp("v26-190-root-cause") / "formal"
    products = audit.build(
        package_root=_package_root(),
        output_dir=output,
        external_audit_path=_external_audit(),
        source_commit=commit,
        source_tree=tree,
    )
    return products, output


def test_exact_v188_request_reconstruction(built: tuple[audit.BuildProducts, Path]) -> None:
    products, output = built
    assert products.report.v188_request_reconstruction == "PASS"
    assert len(products.reconstruction.rows) == 192
    assert products.reconstruction.exact_certificate_match_count == 192
    assert products.reconstruction.prompt_utf8_bytes_minimum == 12_053
    assert products.reconstruction.prompt_utf8_bytes_maximum == 17_069
    assert products.reconstruction.canonical_request_body_bytes_minimum == 13_418
    assert products.reconstruction.canonical_request_body_bytes_maximum == 18_770
    assert products.reconstruction.forbidden_control_character_count == 0
    assert products.reconstruction.surrogate_codepoint_count == 0
    assert len(tuple(output.iterdir())) == 15


def test_historical_exact_route_http_success_corpus(
    built: tuple[audit.BuildProducts, Path],
) -> None:
    products, _ = built
    assert products.historical.exact_http_success_count == 7_229
    assert products.historical.success_within_v188_body_range == 1_811
    assert products.historical.global_request_body_bytes_minimum == 3_759
    assert products.historical.global_request_body_bytes_maximum == 55_126
    assert [item.http_200_count for item in products.historical.run_summaries] == [
        197,
        191,
        879,
        3_043,
        2_919,
    ]
    assert len(products.historical.envelope_files) == 7_229


def test_comparison_keeps_root_cause_unlocalized(
    built: tuple[audit.BuildProducts, Path],
) -> None:
    products, _ = built
    assert products.comparison.deterministic_fixed_contract_difference_count == 0
    assert products.comparison.prompt_or_body_encoding_defect_count == 0
    assert products.comparison.serializer_source_match
    assert products.comparison.v188_body_range_contained_by_historical_success_range
    assert products.comparison.secret_authorization_value_comparison_evaluable is False
    assert products.localization.unique_root_cause_identified is False
    assert products.localization.localization_result == "not_localizable_from_persisted_artifacts"
    assert products.report.unique_http_400_root_cause == (
        "NOT_LOCALIZABLE_FROM_PERSISTED_ARTIFACTS"
    )
    assert products.report.provider_calls == 0


def test_destructive_controls_and_transition(
    built: tuple[audit.BuildProducts, Path],
) -> None:
    products, _ = built
    assert products.destructive.attempted_count == 13
    assert products.destructive.rejected_count == 13
    assert products.destructive.accepted_count == 0
    assert products.static.provider_calls == 0
    assert products.static.provider_clients_constructed == 0
    assert products.static.credential_reads == 0
    assert products.transition.decision == audit.CURRENT_DECISION
    assert products.transition.recommended_future_stage_authorized_now is False
    assert products.transition.provider_execution_authorized is False


def test_external_binding_and_credential_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("not the bound v26.189 audit", encoding="utf-8")
    with pytest.raises(ValueError, match="external v26.189 audit bytes differ"):
        audit._authorization(wrong)  # noqa: SLF001
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-be-read")
    commit, tree = _source_identity()
    with pytest.raises(ValueError, match="credential removal"):
        audit.build(
            package_root=_package_root(),
            output_dir=tmp_path / "credential-rejected",
            external_audit_path=_external_audit(),
            source_commit=commit,
            source_tree=tree,
        )


def test_byte_identical_rebuild(built: tuple[audit.BuildProducts, Path], tmp_path: Path) -> None:
    _, first = built
    commit, tree = _source_identity()
    second = tmp_path / "rebuilt"
    audit.build(
        package_root=_package_root(),
        output_dir=second,
        external_audit_path=_external_audit(),
        source_commit=commit,
        source_tree=tree,
    )
    first_files = {path.name: path.read_bytes() for path in first.iterdir()}
    second_files = {path.name: path.read_bytes() for path in second.iterdir()}
    assert first_files == second_files


def test_existing_output_fails_without_byte_drift(
    built: tuple[audit.BuildProducts, Path],
) -> None:
    _, output = built
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    commit, tree = _source_identity()
    with pytest.raises(FileExistsError):
        audit.build(
            package_root=_package_root(),
            output_dir=output,
            external_audit_path=_external_audit(),
            source_commit=commit,
            source_tree=tree,
        )
    after = {path.name: path.read_bytes() for path in output.iterdir()}
    assert before == after
