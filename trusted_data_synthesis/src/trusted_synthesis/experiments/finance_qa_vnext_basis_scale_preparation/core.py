"""New-study identities and write-once source artifacts; historical studies stay closed."""

import hashlib
import json
import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import write

BASELINE = "8da711daf4817950fe8a5176c533e48a7fae507b"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "finance_qa_vnext_basis_scale_preparation"
)
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_basis_scale_preparation/source_inventory_20260911"
)
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_basis_scale_preparation.md"
AUDIT = "/home/zhuxinrui/.codex/attachments/d61e3c0c-e49a-46a3-a337-cf78275ed6e7/pasted-text.txt"
AUDIT_SHA = "717ecc3efc7e51802462a430a6ebc6f5a85a7460e2f5fd3205b02125ae669c9a"


def require(condition, code):
    if not condition:
        raise ValueError(code)


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def record(kind, **fields):
    body = {"schema_version": "basis_scale_preparation.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def read_json(path):
    return json.loads(Path(path).read_bytes())


def reference(root, relative):
    root = Path(root)
    relative = Path(relative)
    require(not relative.is_absolute() and ".." not in relative.parts, "reference.relative_path")
    path = root / relative
    require(path.is_file() and not path.is_symlink(), "reference.regular_file")
    require(path.resolve().is_relative_to(root.resolve()), "reference.inside_root")
    raw = path.read_bytes()
    return {"path": str(relative), "bytes": len(raw), "sha256": sha(raw)}


class Store:
    def __init__(self, directory):
        self.root = Path(directory)
        require(not self.root.exists(), "store.new_phase_only")
        self.root.mkdir(parents=True)

    def write(self, name, raw):
        path = Path(name)
        require(not path.is_absolute() and ".." not in path.parts, "store.relative_path")
        require(not (self.root / "manifest.json").exists(), "store.sealed")
        write(self.root, name, raw)

    def json(self, name, value):
        self.write(name, encode(value))

    def seal(self, **fields):
        members = []
        for path in sorted(self.root.rglob("*")):
            require(not path.is_symlink(), "store.no_symlink")
            if path.is_file():
                raw = path.read_bytes()
                members.append(
                    {
                        "path": str(path.relative_to(self.root)),
                        "bytes": len(raw),
                        "sha256": sha(raw),
                    }
                )
        result = record("basis_scale_stage_manifest", members=members, **fields)
        self.json("manifest.json", result)
        require(manifest(self.root) == result, "store.verified_seal")
        return result


def history_guard(root):
    excluded = (
        PACKAGE,
        OUTPUT,
        DOCUMENT,
        "trusted_data_synthesis/tests/test_qa_vnext_basis_scale_*.py",
    )
    paths = ["trusted_data_synthesis", *[":(exclude)" + path for path in excluded]]
    for command in (
        ["git", "diff", "--name-only", BASELINE, "--", *paths],
        ["git", "status", "--porcelain", "--", *paths],
    ):
        require(
            not subprocess.check_output(command, cwd=root), "history.only_new_scale_preparation"
        )
    return {"baseline": BASELINE, "closed_studies_and_evaluation_only_snapshots_unchanged": True}
