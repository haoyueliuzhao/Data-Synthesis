#!/usr/bin/env python3
"""Combine regional QA export manifests into one deterministic release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _row_key(row: dict[str, Any]) -> str:
    if row.get("id"):
        return str(row["id"])
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=_row_key)
    keys = [_row_key(row) for row in ordered]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate QA identity detected in {path}")
    with path.open("w", encoding="utf-8") as handle:
        for row in ordered:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    content = path.read_bytes()
    return {
        "path": str(path),
        "rows": len(ordered),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def combine(manifest_paths: list[Path], output_dir: Path) -> dict[str, Any]:
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in manifest_paths]
    kg_build_ids = {str(item["kg_build_id"]) for item in manifests}
    if len(kg_build_ids) != 1:
        raise ValueError(f"input exports do not share one KG build: {sorted(kg_build_ids)}")

    artifact_types = ("benchmark", "sft", "trace_seeds")
    files: dict[str, dict[str, Any]] = {}
    for artifact_type in artifact_types:
        splits = sorted(
            {
                split
                for manifest in manifests
                for split in (manifest.get("files", {}).get(artifact_type, {}) or {})
            }
        )
        files[artifact_type] = {}
        for split in splits:
            rows: list[dict[str, Any]] = []
            for manifest in manifests:
                source = (manifest.get("files", {}).get(artifact_type, {}) or {}).get(split)
                if source:
                    rows.extend(_load_jsonl(Path(source["path"])))
            files[artifact_type][split] = _write_jsonl(
                output_dir / artifact_type / f"{split}.jsonl",
                rows,
            )

    benchmark_count = sum(item["rows"] for item in files["benchmark"].values())
    result = {
        "release_type": "combined_regional_qa_export",
        "kg_build_id": next(iter(kg_build_ids)),
        "source_qa_build_ids": [str(item["qa_build_id"]) for item in manifests],
        "sample_count": benchmark_count,
        "sft_allowed_splits": sorted(
            {
                split
                for manifest in manifests
                for split in manifest.get("sft_allowed_splits", [])
            }
        ),
        "files": files,
        "source_manifests": [str(path) for path in manifest_paths],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result["manifest"] = str(manifest_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            combine(args.manifest, args.output_dir),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
