"""Persistence/rebuild tests with isolated source authority, never new executions."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import files_at
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import adapter, engine
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import independent as old_audit
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import preflight as old_preflight
from trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement import models, preflight

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/9b1d4cfa-9270-49a6-9a8d-72493b31d79b/pasted-text.txt"
)
if (ROOT / preflight.DEFAULT_DIRECTORY / "external_review.txt").is_file():
    AUDIT = ROOT / preflight.DEFAULT_DIRECTORY / "external_review.txt"
REAL_AUTHORITY = preflight._authority


def _forbidden(*args: Any, **kwargs: Any) -> None:
    raise AssertionError("new Provider, credential, model/mock, old audit or candidate execution")


def _isolated_authority(root: Path, commit: str, tree: str) -> dict[str, Any]:
    return models.record(
        "source_authority",
        implementation={"commit": "isolated_test_source", "tree": "isolated_test_tree"},
        references={},
        test_only_not_a_formal_source_authority=True,
        source_freeze_precedes_formal_artifact_materialization=False,
    )


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    directory = tmp_path_factory.mktemp("share-quotient-test") / "original"
    before = files_at(ROOT / models.PARENT)
    with pytest.MonkeyPatch.context() as guard:
        guard.setattr(preflight, "_authority", _isolated_authority)
        for target, names in (
            (adapter.DeepSeekAdapter, ("perform",)),
            (adapter.CurlTransport, ("send",)),
            (adapter.MockTransport, ("send",)),
            (engine.ModelProtocolEngine, ("__init__", "exchange")),
            (old_audit, ("audit_records", "audit_session")),
            (old_preflight, ("_credential", "prepare_pilot", "run_online", "replay_pilot")),
        ):
            for name in names:
                guard.setattr(target, name, _forbidden)
        for executor in (
            engine.RelationSumExecutor,
            engine.ShareRatioExecutor,
            engine.ScalePercentExecutor,
        ):
            guard.setattr(executor, "execute", _forbidden)
        result = preflight.build_measurement(
            repo_root=ROOT,
            external_audit=AUDIT,
            source_commit="isolated_test_source",
            source_tree="isolated_test_tree",
            output_directory=directory,
        )
        yield {"root": directory, "result": result, "files": files_at(directory)}
        assert files_at(ROOT / models.PARENT) == before


def _copy(built: dict[str, Any], tmp_path: Path) -> Path:
    destination = tmp_path / "tampered"
    shutil.copytree(built["root"], destination)
    return destination


def _rewrite(path: Path, value: dict[str, Any]) -> None:
    kind = value["schema_version"].removeprefix("share_quotient_").removesuffix(".v1")
    updated = models.record(
        kind, **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )
    path.write_bytes(canonical_json_bytes(updated))


def _rehash_manifest(root: Path) -> None:
    files = files_at(root)
    previous = json.loads(files["artifact_manifest.json"])
    members = [
        {"relative_path": name, "sha256": models.sha(data), "byte_count": len(data)}
        for name, data in sorted(files.items())
        if name != "artifact_manifest.json"
    ]
    body = {
        "schema_version": "share_quotient_manifest.v1",
        "members": members,
        "member_count": len(members),
        "member_bytes": sum(member["byte_count"] for member in members),
        "report_id": previous["report_id"],
        "self_excluding": True,
        "artifact_root": strict_canonical_hash(members, prefix="share_quotient_root:"),
    }
    (root / "artifact_manifest.json").write_bytes(
        canonical_json_bytes(
            {**body, "manifest_id": strict_canonical_hash(body, prefix="share_quotient_manifest:")}
        )
    )


def test_complete_finite_artifact_set_and_control_partition(built: dict[str, Any]) -> None:
    result = built["result"]
    assert result["report"]["status"] == "finite_quotient_measurement_completed_as_scoped"
    assert result["report"]["pair_results"] == {
        "equivalent": 6,
        "different_retained_semantics": 4,
        "undetermined": 0,
    }
    assert (
        result["report"]["new_provider_calls"]
        == result["report"]["new_candidate_runtime_executions"]
        == 0
    )
    assert result["validation"]["passed"]
    assert len(built["files"]) == 51
    assert len([name for name in built["files"] if name.startswith("pairs/")]) == 10
    assert "assignments/M01.json" not in built["files"]
    control = json.loads(built["files"]["controls.json"])
    assert control["passed"] == 12 and control["failed"] == 0
    assert all(row["qualified_scientific_sample"] is False for row in control["controls"])
    assert json.loads(built["files"]["source_authority.json"])[
        "test_only_not_a_formal_source_authority"
    ]


def test_full_rebuild_recomputes_same_evidence_byte_identically(
    built: dict[str, Any], tmp_path: Path
) -> None:
    result = preflight.replay_measurement(
        repo_root=ROOT, replay_from=built["root"], output_directory=tmp_path / "rebuilt"
    )
    assert result["all_files_byte_identical"] is True
    assert result["new_statistical_samples"] == 0
    assert files_at(tmp_path / "rebuilt") == built["files"]
    assert files_at(built["root"]) == built["files"]


def test_no_replace_before_any_new_input_read(
    built: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(preflight, "load_inputs", _forbidden)
    with pytest.raises(models.MeasurementError, match="preflight.output_no_replace"):
        preflight.build_measurement(
            repo_root=ROOT,
            external_audit=AUDIT,
            source_commit="irrelevant",
            source_tree="irrelevant",
            output_directory=built["root"],
        )
    assert files_at(built["root"]) == built["files"]


def test_wrong_review_rejected_before_output_creation(
    built: dict[str, Any], tmp_path: Path
) -> None:
    wrong = tmp_path / "wrong-review.txt"
    wrong.write_bytes(b"wrong review")
    with pytest.raises(models.MeasurementError, match="preflight.review_authority"):
        preflight.build_measurement(
            repo_root=ROOT,
            external_audit=wrong,
            source_commit="isolated_test_source",
            source_tree="isolated_test_tree",
            output_directory=tmp_path / "not_created",
        )
    assert not (tmp_path / "not_created").exists()


def test_source_must_be_an_actual_exact_commit(
    built: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(preflight, "_authority", REAL_AUTHORITY)
    with pytest.raises(ValueError):
        preflight.build_measurement(
            repo_root=ROOT,
            external_audit=AUDIT,
            source_commit="0" * 40,
            source_tree="0" * 40,
            output_directory=tmp_path / "not_created",
        )
    assert not (tmp_path / "not_created").exists()


def test_rehashed_persistence_order_change_is_rejected(
    built: dict[str, Any], tmp_path: Path
) -> None:
    root = _copy(built, tmp_path)
    path = root / "persistence.json"
    value = json.loads(path.read_bytes())
    value["write_events"][0]["kind"] = "directory_fsync"
    _rewrite(path, value)
    _rehash_manifest(root)
    with pytest.raises(models.MeasurementError, match="validation.file_directory_order"):
        preflight.validate_artifacts(repo_root=ROOT, artifact_directory=root)


def test_rehashed_empirical_denominator_change_is_rejected(
    built: dict[str, Any], tmp_path: Path
) -> None:
    root = _copy(built, tmp_path)
    path = root / "empirical_measurement.json"
    value = json.loads(path.read_bytes())
    value["q"] = {"numerator": 5, "denominator": 5, "exact": "5/5", "value": 1.0}
    _rewrite(path, value)
    _rehash_manifest(root)
    with pytest.raises(models.MeasurementError, match="validation.independent_measurement"):
        preflight.validate_artifacts(repo_root=ROOT, artifact_directory=root)


def test_rehashed_bad_bijection_is_rejected(built: dict[str, Any], tmp_path: Path) -> None:
    root = _copy(built, tmp_path)
    path = root / "pairs/02_M02_M04.json"
    value = json.loads(path.read_bytes())
    value["bijection"].pop()
    _rewrite(path, value)
    _rehash_manifest(root)
    with pytest.raises(models.MeasurementError, match="validation.independent_measurement"):
        preflight.validate_artifacts(repo_root=ROOT, artifact_directory=root)


def test_rehashed_control_claim_is_recomputed_not_trusted(
    built: dict[str, Any], tmp_path: Path
) -> None:
    root = _copy(built, tmp_path)
    control_path = root / "controls.json"
    controls = json.loads(control_path.read_bytes())
    controls["controls"][0]["result"]["reason"] = "invented certificate"
    item_path = root / "controls/01_consistent_graph_key_and_display_rename.json"
    _rewrite(item_path, controls["controls"][0])
    controls["controls"][0] = json.loads(item_path.read_bytes())
    _rewrite(control_path, controls)
    _rehash_manifest(root)
    with pytest.raises(models.MeasurementError, match="validation.control_recomputation"):
        preflight.validate_artifacts(repo_root=ROOT, artifact_directory=root)


def test_missing_projection_cannot_be_replaced_by_a_new_manifest(
    built: dict[str, Any], tmp_path: Path
) -> None:
    root = _copy(built, tmp_path)
    (root / "projections/M03.json").unlink()
    _rehash_manifest(root)
    with pytest.raises((models.MeasurementError, KeyError)):
        preflight.validate_artifacts(repo_root=ROOT, artifact_directory=root)
