"""Synthetic metadata-only tests: no internet, environment creation or model IO."""

import ast
import copy
from pathlib import Path

import provision_cross_market_vision_pilot_20260927 as m
import pytest


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "ROOT_DATA", tmp_path)
    return dict(
        python=[3, 12, 13],
        versions={**m.EXPECTED_VERSIONS, "Pillow": None, "torchvision": None},
        torch_site=str(tmp_path / "trusted_data_synthesis/.venv/lib/python3.12/site-packages"),
    )


def test_exact_official_snapshot_and_finite_files():
    rows = m.manifest()
    assert len(rows) == 18
    weights = [r for r in rows if r["role"] == "weights"]
    assert len(weights) == 4 and sum(r["bytes"] for r in weights) == 17056744056
    assert sum(r["bytes"] for r in rows if r["role"] == "metadata") == 16011200
    assert all(f"/resolve/{m.REVISION}/" in r["url"] for r in rows)
    assert all(r["hash_kind"] == "sha256" for r in weights)
    assert next(r for r in rows if r["filename"] == "config.json")["hash_kind"] == "git_blob_sha1"


@pytest.mark.parametrize("name,value", [("MAX_WEIGHT_BYTES", 1), ("MAX_METADATA_BYTES", 1)])
def test_caps_fail_closed(monkeypatch, name, value):
    monkeypatch.setattr(m, name, value)
    with pytest.raises(ValueError, match="vision_.*cap"):
        m.manifest()


def test_duplicate_or_path_filename_rejected(monkeypatch):
    rows = list(m.MODEL_FILES)
    rows[0] = rows[1]
    monkeypatch.setattr(m, "MODEL_FILES", rows)
    with pytest.raises(ValueError, match="exact_file_scope"):
        m.manifest()
    rows[0] = ("../README.md", 43006, "git_blob_sha1", "b" * 40)
    with pytest.raises(ValueError, match="safe_pinned_file"):
        m.manifest()


def test_all_runtime_actions_disabled_and_no_plan_writes(runtime, tmp_path):
    before = list(tmp_path.rglob("*"))
    plan = m.plan_fields(runtime)
    for field in (
        "weight_download_authorized",
        "dependency_install_authorized",
        "source_build_authorized",
        "environment_creation_authorized",
        "trust_remote_code",
    ):
        assert plan[field] is False
    for field in (
        "network_requests",
        "model_loads",
        "GPU_processes",
        "PDF_opens",
        "page_renders",
        "semantic_certificates",
        "Student_environment_writes",
    ):
        assert plan[field] == 0
    assert list(tmp_path.rglob("*")) == before
    assert "NOT independent model lineage" in plan["independence"]
    assert plan["load_readiness"] == "PENDING_DEPENDENCIES_AND_RUNTIME_VALIDATION"


@pytest.mark.parametrize("field,value", [("torch", "2.8.0"), ("transformers", "4.52.1")])
def test_parent_runtime_cannot_silently_change(runtime, field, value):
    runtime["versions"][field] = value
    with pytest.raises(ValueError, match="exact_inherited_runtime"):
        m.plan_fields(runtime)


def test_parent_site_cannot_escape(runtime):
    runtime["torch_site"] = "/tmp/other-env/site-packages"
    with pytest.raises(ValueError, match="inherited_site"):
        m.plan_fields(runtime)


def test_denied_wheel_keeps_unknown_size_and_source_build_unproven(runtime):
    plan = m.plan_fields(runtime)
    wheel = plan["dependency_wheels"][1]
    assert wheel["bytes"] is None and "HEAD_403" in wheel["status"]
    alternative = plan["source_build_alternative"]
    assert alternative["commit"] == "59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca"
    assert alternative["status"].endswith("NOT_FETCHED_OR_BUILT")
    assert "pkg_resources" in alternative["pending"]


def test_registration_requires_committed_source_and_preserves_record(
    runtime, tmp_path, monkeypatch
):
    root = tmp_path / "worktree"
    raw = tmp_path / "data"
    monkeypatch.setattr(m.base, "RAW", raw)
    monkeypatch.setattr(m, "RAW", raw / "vision_plan")
    for name in (m.SCRIPT, m.base.SCRIPT):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic frozen source\n")
    committed = {name: (root / name).read_bytes() for name in (m.SCRIPT, m.base.SCRIPT)}

    def git(args, **kwargs):
        if args[1] == "rev-parse":
            return "a" * 40
        assert args[1] == "show"
        return committed[args[2].split(":", 1)[1]]

    monkeypatch.setattr(m.subprocess, "check_output", git)
    monkeypatch.setattr(m, "runtime_metadata", lambda: copy.deepcopy(runtime))
    (root / m.SCRIPT).write_text("uncommitted change")
    with pytest.raises(ValueError, match="committed_code"):
        m.register(root)
    assert not (m.RAW / "protocol.json").exists()
    (root / m.SCRIPT).write_bytes(committed[m.SCRIPT])
    plan = m.register(root)
    saved = (m.RAW / "protocol.json").read_bytes()
    assert m.register(root) == plan and m.protocol(root) == plan
    assert (m.RAW / "protocol.json").read_bytes() == saved
    (root / m.SCRIPT).write_text("post-freeze change")
    with pytest.raises(ValueError, match="frozen_code"):
        m.protocol(root)


def test_module_has_no_acquisition_or_model_execution_surface():
    tree = ast.parse(Path(m.__file__).read_text())
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert not {"download", "install", "fetch_one", "open_response", "load_model"} & functions
    imports = {node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)}
    assert not {"torch", "transformers", "urllib.request", "requests", "venv"} & imports
