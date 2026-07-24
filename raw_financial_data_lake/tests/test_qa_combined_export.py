from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from finraw.qa.export import combine_qa_export_manifests


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_manifest(root: Path, build_id: str, kg_build_id: str, qa_id: str) -> Path:
    files: dict[str, dict[str, dict[str, object]]] = {}
    for kind, row in {
        "benchmark": {"id": qa_id, "question": f"Question {qa_id}"},
        "sft": {
            "messages": [{"role": "user", "content": f"Question {qa_id}"}],
            "metadata": {"qa_build_id": build_id, "qa_group_id": qa_id},
        },
        "trace_seeds": {"question": f"Question {qa_id}"},
    }.items():
        path = root / build_id / kind / "train.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        files[kind] = {
            "train": {
                "path": str(path),
                "rows": 1,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        }
    manifest = {
        "qa_build_id": build_id,
        "kg_build_id": kg_build_id,
        "sample_count": 1,
        "split_counts": {"train": 1},
        "files": files,
    }
    manifest_path = root / build_id / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_combined_qa_export_is_deterministic_and_checksummed(tmp_path: Path) -> None:
    left = _source_manifest(tmp_path, "qa_left", "kg_1", "qa_2")
    right = _source_manifest(tmp_path, "qa_right", "kg_1", "qa_1")

    result = combine_qa_export_manifests(
        [str(left), str(right)], str(tmp_path / "release"), "release_1"
    )

    assert result["sample_count"] == 2
    assert result["split_counts"] == {"train": 2}
    assert result["qa_build_ids"] == ["qa_left", "qa_right"]
    benchmark = Path(result["files"]["benchmark"]["train"]["path"])
    rows = [json.loads(line) for line in benchmark.read_text().splitlines()]
    assert [row["id"] for row in rows] == ["qa_1", "qa_2"]
    assert result["files"]["benchmark"]["train"]["sha256"] == _sha256(benchmark)

    with pytest.raises(FileExistsError, match="already exists"):
        combine_qa_export_manifests(
            [str(right), str(left)], str(tmp_path / "release"), "release_1"
        )


def test_combined_qa_export_rejects_mixed_kg_builds(tmp_path: Path) -> None:
    left = _source_manifest(tmp_path, "qa_left", "kg_1", "qa_1")
    right = _source_manifest(tmp_path, "qa_right", "kg_2", "qa_2")

    with pytest.raises(ValueError, match="one pinned KG build"):
        combine_qa_export_manifests(
            [str(left), str(right)], str(tmp_path / "release"), "release_1"
        )
