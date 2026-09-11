"""Write-once stages and explicit historical, implementation and resource boundaries."""

import os
import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import write

from .plan import (
    BASELINE,
    DOCUMENT,
    OUTPUT,
    PACKAGE,
    TEST,
    encode,
    read_json,
    record,
    reference,
    require,
    sha,
)


class Store:
    def __init__(self, directory):
        self.root = Path(directory)
        require(not self.root.exists(), "store.phase_once_no_overwrite_or_resume")
        self.root.mkdir(parents=True)

    def write(self, name, data):
        path = Path(name)
        require(not path.is_absolute() and ".." not in path.parts, "store.relative_name")
        require(not (self.root / "manifest.json").exists(), "store.phase_already_sealed")
        write(self.root, name, data)

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
        value = record("DR_stage_manifest", members=members, **fields)
        self.json("manifest.json", value)
        require(manifest(self.root) == value, "store.seal_verified")
        return value


def history_guard(root):
    paths = [
        "trusted_data_synthesis",
        *[":(exclude)" + p for p in (PACKAGE, OUTPUT, DOCUMENT, TEST)],
    ]
    for command in (
        ["git", "diff", "--name-only", BASELINE, "--", *paths],
        ["git", "status", "--porcelain", "--", *paths],
    ):
        require(not subprocess.check_output(command, cwd=root), "history.only_new_DR_study_changes")
    return {"baseline": BASELINE, "closed_experiments_unchanged": True}


def implementation(root):
    paths = subprocess.check_output(
        ["git", "ls-files", "--", "trusted_data_synthesis/src/**/*.py", TEST], cwd=root, text=True
    ).splitlines()
    require(paths and TEST in paths, "implementation.tracked_sources_and_test")
    require(
        not subprocess.check_output(
            ["git", "status", "--porcelain", "--", "trusted_data_synthesis/src", TEST, DOCUMENT],
            cwd=root,
        ),
        "implementation.commit_rules_before_freeze",
    )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    remote = subprocess.check_output(
        ["git", "rev-parse", "refs/remotes/origin/main"], cwd=root, text=True
    ).strip()
    require(commit == remote, "implementation.push_rules_before_freeze")
    return record(
        "DR_frozen_implementation", commit=commit, references=[reference(root, p) for p in paths]
    )


def verify_preparation(root):
    directory = Path(root) / OUTPUT / "preparation"
    sealed = manifest(directory)
    data = read_json(directory / "implementation.json")
    for ref in data["references"]:
        require(reference(root, ref["path"]) == ref, "implementation.frozen_bytes")
    for ref in read_json(directory / "historical_references.json"):
        require(reference(root, ref["path"]) == ref, "implementation.historical_input_bytes")
    return sealed


def credential(path):
    """Read one literal key, never source shell code or persist the value."""
    values = []
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == "DEEPSEEK_API_KEY":
            value = value.strip()
            if value.startswith(("'", '"')):
                require(len(value) >= 2 and value[-1] == value[0], "credential.literal_quotes")
                value = value[1:-1]
            values.append(value)
    require(len(values) == 1 and 0 < len(values[0]) <= 2048, "credential.one_available_key")
    require(all(32 < ord(c) != 127 for c in values[0]), "credential.single_literal")
    return values[0]


def pipe_credential(value):
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, value.encode())
    finally:
        os.close(write_fd)
    return read_fd
