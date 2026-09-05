"""End-to-end preflight I/O and replay, with explicitly test-only source authority."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import pytest
import torch

from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import files_at
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import preflight
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.models import (
    TrainingPreflightError,
    record,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.safety import (
    offline_cpu_guard,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/6969daee-b45b-4fe7-9ad3-d421de7ca065/pasted-text.txt"
)


def _test_authority(root: Path, commit: str, tree: str) -> dict[str, Any]:
    return record(
        "source_authority",
        implementation={"commit": commit, "tree": tree},
        test_only_isolated_source_authority=True,
        formal_source_freeze_claimed=False,
    )


@pytest.fixture(scope="module")
def package(tmp_path_factory: Any) -> Any:
    output = tmp_path_factory.mktemp("share-training-preflight") / "package"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(preflight, "_authority", _test_authority)
        formal_review = ROOT / preflight.DEFAULT_DIRECTORY / "external_review.txt"
        review = formal_review if formal_review.exists() else REVIEW
        result = preflight.build_preflight(
            repo_root=ROOT,
            external_audit=review,
            source_commit="isolated-test-only-not-a-formal-commit",
            source_tree="isolated-test-only-not-a-formal-tree",
            output_directory=output,
        )
        yield output, result


def test_complete_preflight_materializes_real_rows_and_applied_weights(package: Any) -> None:
    directory, result = package
    report = result["report"]
    assert result["validation"]["passed"] is True
    assert report["counts"]["positive_units"] == 27
    assert report["target_tokens"] == 15_939
    assert report["actual_batch_shape"] == [27, 15_110]
    assert report["controls_passed"] == 13
    assert report["loss_check_count"] == 18
    assert report["gate_passed"] == 4 and report["gate_failed"] == 0
    assert report["Student_parameter_updates"] == report["GPU_jobs"] == 0
    assert report["original_qualification_or_quotient_reexecuted"] is False
    files = files_at(directory)
    assert result["artifact_file_count"] == len(files) == 40
    assert result["artifact_total_bytes"] == sum(map(len, files.values()))
    assert len(files["training_rows.jsonl"].splitlines()) == 27
    scope = json.loads(files["runtime_scope.json"])
    assert not any(scope["forbidden_attempt_counts"].values())
    assert scope["CUDA_initialized"] is False
    assert report["Contribution"] is report["Student_utility"] is None


def test_all_files_rebuilt_byte_identically(package: Any, tmp_path: Path) -> None:
    directory, _ = package
    result = preflight.replay_preflight(
        repo_root=ROOT, replay_from=directory, output_directory=tmp_path / "replayed"
    )
    assert result["all_files_byte_identical"] is True
    assert result["new_statistical_samples"] == 0


def test_existing_output_is_never_overwritten(package: Any) -> None:
    directory, _ = package
    original = files_at(directory)
    with pytest.raises(TrainingPreflightError, match="output_no_replace"):
        preflight.build_preflight(
            repo_root=ROOT,
            external_audit=REVIEW,
            source_commit="unused",
            source_tree="unused",
            output_directory=directory,
        )
    assert files_at(directory) == original


def test_bad_review_rejected_before_root_creation(tmp_path: Path) -> None:
    bad = tmp_path / "wrong-review.txt"
    bad.write_bytes(b"not the accepted audit")
    output = tmp_path / "absent"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(preflight, "_authority", _test_authority)
        with pytest.raises(TrainingPreflightError, match="review_authority"):
            preflight.build_preflight(
                repo_root=ROOT,
                external_audit=bad,
                source_commit="test",
                source_tree="test",
                output_directory=output,
            )
    assert not output.exists()


def test_manifest_detects_changed_weight_tensor(package: Any, tmp_path: Path) -> None:
    directory, _ = package
    files = files_at(directory)
    destination = tmp_path / "corrupted"
    for path, data in files.items():
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data + b"x" if path == "weights/Q.npz" else data)
    with pytest.raises(ValueError):
        preflight.validate_artifacts(repo_root=ROOT, artifact_directory=destination)


def test_guard_records_zero_attempts_and_restores_threads() -> None:
    before = torch.get_num_threads()
    with offline_cpu_guard() as scope:
        assert torch.get_num_threads() == 8
        assert not torch.cuda.is_initialized()
    assert torch.get_num_threads() == before
    assert not any(scope["forbidden_attempt_counts"].values())


@pytest.mark.parametrize("name", [".env", "model.safetensors", "pytorch_model.bin"])
def test_guard_rejects_credential_and_weight_reads_without_opening(
    tmp_path: Path, name: str
) -> None:
    with pytest.raises(TrainingPreflightError, match="scope.forbidden_"):
        with offline_cpu_guard():
            (tmp_path / name).read_bytes()


def test_guard_rejects_network_before_lookup() -> None:
    with pytest.raises(TrainingPreflightError, match="forbidden_network"):
        with offline_cpu_guard():
            socket.getaddrinfo("invalid.test", 443)


def test_guard_rejects_cuda_before_initialization() -> None:
    with pytest.raises(TrainingPreflightError, match="forbidden_cuda"):
        with offline_cpu_guard():
            torch.cuda._lazy_init()
    assert not torch.cuda.is_initialized()


def test_cli_validate_is_read_only(package: Any, monkeypatch: Any, capsys: Any) -> None:
    directory, _ = package
    before = files_at(directory)
    monkeypatch.setattr(
        "sys.argv",
        [
            "preflight",
            "--mode",
            "validate",
            "--repo-root",
            str(ROOT),
            "--replay-from",
            str(directory),
        ],
    )
    preflight.main()
    result = json.loads(capsys.readouterr().out)
    assert result["passed"] is True
    assert result["same_27_rows_retokenized"] is True
    assert files_at(directory) == before
