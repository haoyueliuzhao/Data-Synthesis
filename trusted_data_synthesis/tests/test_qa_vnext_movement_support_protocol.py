"""Offline diagnosis output gates; no model or training process is opened."""

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_movement_support import protocol, run


def test_policy_no_topup_or_training_and_generation_is_not_final_material():
    value = protocol.policy()
    assert protocol.checked_record(value, "phase_zero_policy") == value
    assert value["registered_sessions"] == 24640
    for name in ["new_Teacher_source_or_rewrite_requests", "Student_or_GPU_calls"]:
        assert value[name] == 0
    for name in [
        "no_automatic_topup_or_training",
        "final_zero_does_not_prove_generation_probability_zero",
        "requested_basis_is_not_actual_method",
        "structural_signal_is_not_financial_qualification",
        "original_32_per_guidance_and_8_plus_2_rules_unchanged",
    ]:
        assert value[name] is True
    assert value["Student_development_or_confirmation_outputs_read"] is False


def test_content_record_detects_mutation():
    value = protocol.record("test", a=[1])
    value["a"].append(2)
    with pytest.raises(ValueError, match="content_identity"):
        protocol.checked_record(value, "test")


def test_write_once_does_not_overwrite(tmp_path):
    path = tmp_path / "separate" / "evidence.json"
    protocol.write_once(path, {"first": True})
    with pytest.raises(FileExistsError):
        protocol.write_once(path, {"replacement": True})
    assert json.loads(path.read_bytes()) == {"first": True}


@pytest.mark.parametrize("leaf", [False, True])
def test_output_symlink_rejected(tmp_path, leaf):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="safe_exclusive_output"):
        protocol.write_once(link if leaf else link / "evidence.json", {})
    assert not list(target.iterdir())


def test_parent_traversal_rejected(tmp_path):
    with pytest.raises(ValueError, match="safe_exclusive_output"):
        protocol.write_once(tmp_path / "a" / ".." / "evidence.json", {})


@pytest.mark.parametrize("mutation", ["same_root", "wrong_branch", "main_moved", "wrong_code_root"])
def test_isolation_gates_before_any_write(tmp_path, monkeypatch, mutation):
    code = tmp_path / "code"
    data = tmp_path / "data"
    code.mkdir()
    data.mkdir()
    module_file = code / "module.py"
    monkeypatch.setattr(run, "__file__", str(module_file))

    def fake_git(root, *args):
        if args == ("branch", "--show-current"):
            return ("main" if mutation == "wrong_branch" else protocol.BRANCH).encode()
        return ("different" if mutation == "main_moved" else protocol.BASE_COMMIT).encode()

    monkeypatch.setattr(run, "git", fake_git)
    if mutation == "same_root":
        data = code
    if mutation == "wrong_code_root":
        monkeypatch.setattr(run, "__file__", str(data / "module.py"))
    with pytest.raises(ValueError):
        run.guarded_roots(code, data)
    assert not (code / protocol.OUTPUT).exists()


def test_valid_roots_only_return_new_branch_output(tmp_path, monkeypatch):
    code, data = tmp_path / "code", tmp_path / "data"
    code.mkdir()
    data.mkdir()
    monkeypatch.setattr(run, "__file__", str(code / "module.py"))
    monkeypatch.setattr(
        run,
        "git",
        lambda root, *args: (
            protocol.BRANCH if args == ("branch", "--show-current") else protocol.BASE_COMMIT
        ).encode(),
    )
    c, d, o = run.guarded_roots(code, data)
    assert (c, d, o) == (code, data, code / protocol.OUTPUT)
    assert not o.exists()


def test_source_snapshot_allows_only_skip_worktree_absence(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run, "git", lambda root, *args: b"S missing.py\0" if args[0] == "ls-files" else b"commit"
    )
    result = run.source_snapshot(tmp_path)
    assert result["members"] == [
        {"path": "missing.py", "materialized": False, "skip_worktree": True}
    ]
    monkeypatch.setattr(
        run, "git", lambda root, *args: b"H missing.py\0" if args[0] == "ls-files" else b"commit"
    )
    with pytest.raises(ValueError, match="only_sparse_absence_allowed"):
        run.source_snapshot(tmp_path)


def test_sha_file_matches_canonical_bytes(tmp_path):
    path = tmp_path / "record.json"
    protocol.write_once(path, {"x": "中文"})
    assert protocol.sha(path) == protocol.sha(protocol.encode({"x": "中文"}))
    assert isinstance(path, Path)


@pytest.mark.parametrize(
    "mutation", ["duplicate_full", "duplicate_public", "different_set", "partial"]
)
def test_full_catalog_exact_unique_task_set(mutation):
    full = {"tasks": [{"task_id": str(i)} for i in range(255)]}
    public = {"tasks": [{"task_id": str(i)} for i in range(255)]}
    run.require_task_sets(full, public)
    if mutation == "duplicate_full":
        full["tasks"][-1] = full["tasks"][0]
    elif mutation == "duplicate_public":
        public["tasks"][-1] = public["tasks"][0]
    elif mutation == "different_set":
        full["tasks"][-1] = {"task_id": "not_public"}
    else:
        full["tasks"].pop()
    with pytest.raises(ValueError, match="unique_exact_full_and_public_task_sets"):
        run.require_task_sets(full, public)


@pytest.mark.parametrize("field", ["id", "bundle_id", "task_id"])
def test_qualification_binds_private_bundle_not_just_public_surface(field):
    entry = {"qualification_id": "q"}
    qualification = {"id": "q", "bundle_id": "b", "task_id": "t"}
    fixture = {"bundle": {"id": "b", "task_id": "t"}}
    run.require_qualification_bundle(entry, qualification, fixture)
    qualification[field] = "different"
    with pytest.raises(ValueError, match="private_bundle_join"):
        run.require_qualification_bundle(entry, qualification, fixture)


def test_code_snapshot_binds_even_uncommitted_bytes(monkeypatch):
    monkeypatch.setattr(run, "git", lambda root, *args: b"same_commit")
    root = Path(run.__file__).resolve().parents[5]
    value = run.diagnostic_code_snapshot(root)
    assert len(value["members"]) >= 8
    assert any(row["path"].endswith("run.py") for row in value["members"])
    monkeypatch.setattr(run, "sha", lambda value: "changed_same_commit")
    assert run.diagnostic_code_snapshot(root)["id"] != value["id"]


def test_child_rejects_code_change_before_control(monkeypatch):
    monkeypatch.setattr(run, "diagnostic_code_snapshot", lambda root: {"id": "changed"})
    with pytest.raises(ValueError, match="child_code_before"):
        run._control_job((None, "movement", "/tmp/unused", {"id": "frozen"}))


def test_child_rejects_code_change_after_control(monkeypatch):
    from trusted_synthesis.experiments.finance_qa_vnext_movement_support import controls

    calls = iter([{"id": "frozen"}, {"id": "changed"}])
    monkeypatch.setattr(run, "diagnostic_code_snapshot", lambda root: next(calls))
    monkeypatch.setattr(controls, "run_fixture_control", lambda *args: {"test": True})
    with pytest.raises(ValueError, match="child_code_after"):
        run._control_job((None, "movement", "/tmp/unused", {"id": "frozen"}))
