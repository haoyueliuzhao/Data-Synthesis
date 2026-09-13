"""Synthetic launch guards only: no live process signals, ledger, GPU or results."""

import copy
import hashlib
import os
from contextlib import contextmanager

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_linear_postprocess import runner
from trusted_synthesis.experiments.finance_qa_vnext_linear_postprocess.protocol import record


def revised(value, **changes):
    body = copy.deepcopy(value)
    kind = body.pop("schema_version").split(".", 2)[-1]
    body.pop("id")
    return record(kind, **{**body, **changes})


def plans():
    process = {
        "pid": 726630,
        "start_ticks": 123456,
        "uid": 1234,
        "command_sha256": "a" * 64,
        "alive": True,
        "state": "R",
    }
    before = record(
        "linear_handoff_plan",
        read_only=True,
        data_root="/synthetic/root",
        adapter_policy_id="synthetic:policy",
        original_follow_started_id="synthetic:started",
        original_follow_started_sha256="b" * 64,
        original_follow_pid=process["pid"],
        original_follow_identity=process,
        active_old_followers=[copy.deepcopy(process)],
        collection_parent={"manifest_id": "synthetic:manifest", "manifest_sha256": "c" * 64},
        collection_report_id="synthetic:report",
        material_output_absent=True,
        Student_output_absent=True,
        active_collectors=[],
        active_student_workers=[],
        active_other_postprocessors=[],
        managed_collection_writers=[],
        managed_writable_collection_mappings=[],
        old_follow_failure_exists=False,
        old_follow_completion_exists=False,
    )
    current = revised(
        before,
        active_old_followers=[],
        original_follow_identity={"pid": process["pid"], "alive": False},
    )
    authorization = record(
        "linear_handoff_authorization",
        reviewed_plan_id=before["id"],
        operator_approved=True,
        scope="replace_only_read_only_postprocessing_supervisor",
        no_other_source_writers_confirmed=True,
        verified_stopped_process_identity=runner.process_identity(process),
        source_registration_id="synthetic:sources",
    )
    return before, current, authorization


@pytest.mark.parametrize(
    "module,action,kind",
    [
        (runner.STUDENT_MODULE, "follow", "follow"),
        (runner.STUDENT_MODULE, "advance", "postprocessor"),
        (runner.STUDENT_MODULE, "freeze", "postprocessor"),
        (runner.STUDENT_MODULE, "run", "postprocessor"),
        (runner.COLLECT_MODULE, "collect", "collector"),
        (runner.COLLECT_MODULE, "materialize", "postprocessor"),
        (runner.RUNNER_MODULE, "execute", "postprocessor"),
        (runner.WORKER_MODULE, "--job", "worker"),
        (runner.STUDENT_MODULE, "status", None),
        (runner.RUNNER_MODULE, "inspect", None),
        (runner.RUNNER_MODULE, "source-registration", None),
    ],
)
def test_all_supported_writer_entries_are_classified(module, action, kind):
    assert runner.process_kind(["python", "-m", module, action], pid=os.getpid() + 1000) == kind


def test_inspecting_current_execute_does_not_conflict_with_itself():
    assert (
        runner.process_kind(["python", "-m", runner.RUNNER_MODULE, "execute"], pid=os.getpid())
        is None
    )


def test_exact_read_only_handoff_is_admitted_without_any_real_stop():
    before, current, authorization = plans()
    assert runner.guard_handoff(before, current, authorization) is True
    assert runner.guard_reviewed(before) == authorization["verified_stopped_process_identity"]


@pytest.mark.parametrize(
    "key,bad",
    [
        ("active_old_followers", []),
        ("active_old_followers", [{"alive": True}, {"alive": True}]),
        ("active_collectors", [{"pid": 99}]),
        ("active_student_workers", [{"pid": 99}]),
        ("active_other_postprocessors", [{"pid": 99}]),
        ("managed_collection_writers", [{"pid": 99}]),
        ("managed_writable_collection_mappings", [{"pid": 99}]),
        ("material_output_absent", False),
        ("Student_output_absent", False),
        ("old_follow_failure_exists", True),
        ("old_follow_completion_exists", True),
        ("read_only", False),
        ("original_follow_pid", 999),
    ],
)
def test_reviewed_plan_must_be_exclusively_one_original_reader(key, bad):
    before, _, _ = plans()
    with pytest.raises(ValueError):
        runner.guard_reviewed(revised(before, **{key: bad}))


@pytest.mark.parametrize(
    "key,bad",
    [
        ("pid", 99),
        ("start_ticks", 654321),
        ("uid", 999),
        ("command_sha256", "d" * 64),
        ("alive", False),
    ],
)
def test_reviewed_follow_pid_reuse_or_identity_mismatch_rejected(key, bad):
    before, _, _ = plans()
    followers = copy.deepcopy(before["active_old_followers"])
    followers[0][key] = bad
    with pytest.raises(ValueError):
        runner.guard_reviewed(revised(before, active_old_followers=followers))


@pytest.mark.parametrize(
    "key,bad",
    [
        ("active_old_followers", [{"pid": 99}]),
        ("active_collectors", [{"pid": 99}]),
        ("active_student_workers", [{"pid": 99}]),
        ("active_other_postprocessors", [{"pid": 99}]),
        ("managed_collection_writers", [{"pid": 99}]),
        ("managed_writable_collection_mappings", [{"pid": 99}]),
        ("material_output_absent", False),
        ("Student_output_absent", False),
        ("old_follow_failure_exists", True),
        ("old_follow_completion_exists", True),
        ("original_follow_identity", {"pid": 726630, "alive": True}),
        ("original_follow_identity", {"pid": 999, "alive": False}),
        ("collection_report_id", "synthetic:different"),
        ("data_root", "/different"),
    ],
)
def test_post_stop_drift_or_new_conflicting_writer_rejected(key, bad):
    before, current, authorization = plans()
    with pytest.raises(ValueError):
        runner.guard_handoff(before, revised(current, **{key: bad}), authorization)


@pytest.mark.parametrize(
    "key,bad",
    [
        ("operator_approved", False),
        ("no_other_source_writers_confirmed", False),
        ("scope", "restart_collect"),
        ("reviewed_plan_id", "synthetic:wrong"),
        ("verified_stopped_process_identity", {"pid": 726630}),
    ],
)
def test_authorization_must_bind_scope_review_and_exact_stopped_identity(key, bad):
    before, current, authorization = plans()
    with pytest.raises(ValueError):
        runner.guard_handoff(before, current, revised(authorization, **{key: bad}))


def test_self_asserted_approval_without_content_identity_is_rejected():
    before, current, authorization = plans()
    authorization["added_after_signature"] = True
    with pytest.raises(ValueError):
        runner.guard_handoff(before, current, authorization)


def test_execution_root_must_be_own_main_worktree(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "code_root", lambda: tmp_path)
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *args, **kwargs: "main\n")
    assert runner.execution_root(tmp_path) == tmp_path
    with pytest.raises(ValueError, match="own_non_symlink_code_root"):
        runner.execution_root(tmp_path / "different")
    monkeypatch.setattr(
        runner.subprocess, "check_output", lambda *args, **kwargs: "codex/revision\n"
    )
    with pytest.raises(ValueError, match="only_main_branch"):
        runner.execution_root(tmp_path)


def test_execution_via_symlink_root_is_rejected(tmp_path, monkeypatch):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(runner, "code_root", lambda: real)
    with pytest.raises(ValueError, match="own_non_symlink_code_root"):
        runner.execution_root(alias)


def test_execute_rejects_wrong_root_before_registration_or_output(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "code_root", lambda: tmp_path / "own")

    def forbidden(*args, **kwargs):
        pytest.fail("no source registration or scientific execution after root rejection")

    monkeypatch.setattr(runner, "source_registration", forbidden)
    with pytest.raises(ValueError, match="own_non_symlink_code_root"):
        runner.execute(tmp_path, {}, {})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", [False, True])
def test_execute_reuses_original_advance_and_retains_terminal_or_failure(
    tmp_path, monkeypatch, failure
):
    from trusted_synthesis.experiments.finance_qa_vnext_basis_student import stage

    before, current, authorization = plans()
    calls = []
    monkeypatch.setattr(runner, "execution_root", lambda root: tmp_path)
    monkeypatch.setattr(runner, "source_registration", lambda root: {"id": "synthetic:sources"})
    monkeypatch.setattr(runner, "inspect", lambda root: current)
    monkeypatch.setattr(runner.adapter, "binding", lambda *args: {"id": "synthetic:binding"})

    @contextmanager
    def installed(binding):
        yield {"verifications": [{"synthetic_only": True}]}

    monkeypatch.setattr(runner.adapter, "installed", installed)

    def advance(root):
        calls.append("original.advance")
        if failure:
            raise RuntimeError("synthetic injected failure")
        return {"id": "synthetic:terminal", "score_must_not_be_copied": 123}

    monkeypatch.setattr(stage, "advance", advance)
    monkeypatch.setattr(stage, "try_publish", lambda *args: {"id": "synthetic:publication"})
    if failure:
        with pytest.raises(RuntimeError, match="synthetic injected failure"):
            runner.execute(tmp_path, before, authorization)
        assert (tmp_path / runner.OPERATION / "handoff_failed.json").is_file()
    else:
        report = runner.execute(tmp_path, before, authorization)
        assert report["original_terminal_record_id"] == "synthetic:terminal"
        assert "score_must_not_be_copied" not in report
        assert (tmp_path / runner.OPERATION / "manifest.json").is_file()
    assert calls == ["original.advance"]
    with pytest.raises(ValueError, match="one_supervisor_handoff_no_retry"):
        runner.execute(tmp_path, before, authorization)
    assert calls == ["original.advance"]


def registration_fixture(tmp_path, monkeypatch):
    raw = {
        "trusted_data_synthesis/src/original.py": b"original\n",
        runner.PACKAGE + "/__init__.py": b"new\n",
        "trusted_data_synthesis/tests/test_qa_vnext_linear_synthetic.py": b"test\n",
        runner.PACKAGE + "/README.md": b"documentation\n",
        runner.PACKAGE + "/preflight_evidence.json": b'{"synthetic":true}',
    }
    blobs = {}
    for name, value in raw.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        blobs[name] = hashlib.sha1(b"blob " + str(len(value)).encode() + b"\0" + value).hexdigest()
    old = {name: digest for name, digest in blobs.items() if name.endswith("/original.py")}
    monkeypatch.setattr(
        runner, "_tree", lambda root, revision: old if revision == runner.BASE_COMMIT else blobs
    )
    monkeypatch.setattr(
        runner.subprocess, "check_output", lambda *args, **kwargs: "synthetic-commit\n"
    )
    return raw


def test_source_registration_binds_new_sources_tests_docs_and_evidence(tmp_path, monkeypatch):
    registration_fixture(tmp_path, monkeypatch)
    value = runner.source_registration(tmp_path)
    assert value["historical_source_file_count"] == 1
    assert value["existing_files_changed"] == 0
    assert {row["role"] for row in value["adapter_code"]} == {
        "adapter_source",
        "adapter_CPU_test",
        "adapter_documentation",
        "read_only_preflight_evidence",
    }


@pytest.mark.parametrize(
    "relative",
    [
        "trusted_data_synthesis/src/original.py",
        runner.PACKAGE + "/__init__.py",
        "trusted_data_synthesis/tests/test_qa_vnext_linear_synthetic.py",
        runner.PACKAGE + "/README.md",
        runner.PACKAGE + "/preflight_evidence.json",
    ],
)
def test_registration_rejects_old_or_new_uncommitted_bytes(tmp_path, monkeypatch, relative):
    registration_fixture(tmp_path, monkeypatch)
    (tmp_path / relative).write_bytes(b"drift")
    with pytest.raises(ValueError):
        runner.source_registration(tmp_path)


@pytest.mark.parametrize(
    "module,action,kind",
    [
        (runner.STUDENT_MODULE, "follow", "follow"),
        (runner.STUDENT_MODULE, "advance", "postprocessor"),
        (runner.STUDENT_MODULE, "freeze", "postprocessor"),
        (runner.STUDENT_MODULE, "run", "postprocessor"),
        (runner.COLLECT_MODULE, "collect", "collector"),
        (runner.COLLECT_MODULE, "materialize", "postprocessor"),
        (runner.RUNNER_MODULE, "execute", "postprocessor"),
    ],
)
@pytest.mark.parametrize("prefix", [["--root", "run"], ["--root=/synthetic", "--"]])
def test_options_before_positional_action_cannot_hide_a_writer(module, action, kind, prefix):
    assert (
        runner.process_kind(["python", "-m", module, *prefix, action], pid=os.getpid() + 1000)
        == kind
    )


def test_an_option_value_named_execute_is_not_an_action():
    assert (
        runner.process_kind(
            ["python", "-m", runner.RUNNER_MODULE, "--root", "execute", "inspect"],
            pid=os.getpid() + 1000,
        )
        is None
    )
