"""Two CPU-only guards for the thin worker; no native science is executed."""

import hashlib
from types import SimpleNamespace

import pytest

import finqa_v58_worker as worker


def test_science_and_evaluation_delegate_the_original_argv(monkeypatch):
    calls = []

    def original_main():
        calls.append(list(worker.sys.argv))
        return "ORIGINAL_ENTRY"

    monkeypatch.setattr(worker, "_load_private_worker", lambda: SimpleNamespace(main=original_main))
    for mode, tail in (("science", ["--seed", "137", "--stage", "shard01", "--gpu-index", "4"]),
                       ("evaluation", ["worker", "--job", "CPU_PANEL_JOB", "--gpu", "4"])):
        argv = ["finqa_v58_worker.py", "--mode", mode, "--root", str(worker.SCIENCE_ROOT), *tail]
        monkeypatch.setattr(worker.sys, "argv", argv)
        assert worker.main() == "ORIGINAL_ENTRY"
        assert calls[-1] == argv


def test_monitor_filter_requires_exact_name_directory_and_frozen_bytes(tmp_path):
    directory = tmp_path / "registered"
    directory.mkdir()
    path = directory / "finqa_v58_worker.py"
    path.write_text("# CPU-only fixture\n")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = dict(files={path.name: expected})
    assert worker._monitoring_file(path, directory, manifest)["source_binding"] == "new_immutable_manifest"
    assert worker._monitoring_file(path, directory, None)["source_binding"] == "prospective_workspace_bytes"
    assert worker._monitoring_file(directory / "finqa_v58_unregistered_science.py", directory, manifest) is None
    with pytest.raises(RuntimeError, match="another source directory"):
        worker._monitoring_file(tmp_path / path.name, directory, manifest)
    with pytest.raises(RuntimeError, match="differs from the new frozen manifest"):
        worker._monitoring_file(path, directory, dict(files={path.name: "0" * 64}))
