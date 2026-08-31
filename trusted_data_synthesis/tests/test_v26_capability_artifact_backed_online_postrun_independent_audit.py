from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_postrun_independent_audit as audit,
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
    override = os.environ.get("V26_189_EXTERNAL_AUDIT")
    if override:
        return Path(override)
    return _package_root() / audit.OUTPUT_DIR / "external_v26_188_result_audit.txt"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[audit.BuildProducts, Path]:
    commit, tree = _source_identity()
    output = tmp_path_factory.mktemp("v26-189-postrun") / "formal"
    products = audit.build(
        package_root=_package_root(),
        output_dir=output,
        external_audit_path=_external_audit(),
        source_commit=commit,
        source_tree=tree,
    )
    return products, output


def test_complete_independent_replay(built: tuple[audit.BuildProducts, Path]) -> None:
    products, output = built
    assert products.report.online_execution_and_evidence_chain == "PASS"
    assert products.report.model_semantic_capability_observation == "UNINSTANTIATED"
    assert products.report.formal_end_to_end_q_first == "0/192"
    assert products.report.model_endpoint_conditional_semantic_q == "null"
    assert products.raw_events.http_400_count == 192
    assert products.raw_events.http_success_count == 0
    assert products.raw_events.response_envelope_count == 0
    assert products.raw_events.model_identity_evaluable_count == 0
    assert products.raw_events.observed_wrong_model_response_count == 0
    assert products.evidence_replay.raw_result_byte_match_count == 384
    assert products.evidence_replay.descriptor_byte_match_count == 576
    assert products.evidence_replay.exact_parent_chain_match_count == 192
    assert products.static.provider_calls == 0
    assert len(tuple(output.iterdir())) == 14


def test_layered_gate_and_estimand_separation(
    built: tuple[audit.BuildProducts, Path],
) -> None:
    products, _ = built
    assert products.gates.job_exact_set == "PASS"
    assert products.gates.frozen_terminal_admission == "PASS"
    assert products.gates.provider_request_acceptance == "FAIL"
    assert products.gates.model_endpoint_observability == "UNINSTANTIATED"
    assert products.gates.semantic_capability_measurement == "UNAVAILABLE"
    assert products.gates.capability_measurement_gate_passed is False
    assert products.estimands.q_job_bounded_fraction == "0/192"
    assert products.estimands.model_endpoint_denominator == 0
    assert products.estimands.semantic_capability_fraction == "null"
    assert products.estimands.semantic_null_is_not_zero


def test_http_400_shape_rejects_false_model_observation() -> None:
    root = _package_root() / audit.V188_DIR
    path = next((root / "raw_provider_envelopes").glob("*/call_000.json"))
    telemetry = json.loads(path.read_text(encoding="utf-8"))["provider_telemetry"]
    audit.validate_http_400_telemetry(telemetry)
    changed = dict(telemetry)
    changed["response_model"] = "deepseek-v4-flash"
    with pytest.raises(ValueError, match="pre-envelope HTTP-400"):
        audit.validate_http_400_telemetry(changed)


def test_external_audit_binding_and_credential_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("not the authorized audit", encoding="utf-8")
    with pytest.raises(ValueError, match="external audit bytes differ"):
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


def test_existing_output_fails_without_byte_drift(built: tuple[audit.BuildProducts, Path]) -> None:
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
