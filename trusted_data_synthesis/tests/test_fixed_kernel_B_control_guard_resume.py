"""CPU-only recovery transactions; all writes are confined to pytest temporary files."""

import copy
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
w = importlib.import_module("resume_fixed_kernel_B_control_guard_20260924")
p = w.p
REAL_REQUIRE_REVISION = w.require_revision


@pytest.fixture
def case(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    monkeypatch.setattr(w.b, "RAW", raw)
    monkeypatch.setattr(w, "require_quiescent", lambda: None)
    monkeypatch.setattr(w.b, "emit", lambda value: None)
    failure = dict(key=w.TARGET, attempt=1, returncode=1, error=w.ERROR)
    state = dict(
        active={},
        jobs={
            w.TARGET: dict(attempt=1, failures=0, not_before=0, stopped=failure),
            "B_static_11": dict(attempt=1, failures=0, not_before=0, stopped=None),
            "outer_replay_B_delayed_c_29": dict(
                attempt=0, failures=0, not_before=0, stopped=None
            ),
        },
    )
    original = {
        "control/state.json": state,
        "needs_attention.json": dict(jobs=copy.deepcopy(state["jobs"]), at="prior"),
        "budget/state.json": dict(counts=dict(optimizer=1200, worker_start=32)),
        f"results/{w.TARGET}/0001.json": failure,
        "heartbeat.json": dict(active={}, at="prior"),
        "watchdog_status.json": dict(returncode=1, finished_at="prior"),
    }
    for relative, value in original.items():
        w.b.write(raw / relative, value)
    payloads = {name: (raw / name).read_bytes() for name in original}
    revision = dict(
        id="synthetic_execution_revision",
        code_commit="synthetic_committed_revision",
        state_before=dict(sha256=p.sha(payloads["control/state.json"])),
        needs_attention_before=dict(sha256=p.sha(payloads["needs_attention.json"])),
        budget_before=dict(sha256=p.sha(payloads["budget/state.json"])),
    )
    calls = []

    def require_revision(root):
        calls.append(root)
        return revision, {"id": "synthetic_plan"}

    monkeypatch.setattr(w, "require_revision", require_revision)
    return SimpleNamespace(
        root=tmp_path,
        raw=raw,
        original=original,
        payloads=payloads,
        revision=revision,
        validation_calls=calls,
    )


def assert_preserved(case):
    for relative in ("budget/state.json", f"results/{w.TARGET}/0001.json"):
        assert (case.raw / relative).read_bytes() == case.payloads[relative]
    assert (w.directory() / "archive/control_state_before.json").read_bytes() == (
        case.payloads["control/state.json"]
    )
    assert (w.directory() / "archive/needs_attention_resolved.json").read_bytes() == (
        case.payloads["needs_attention.json"]
    )
    for relative in ("heartbeat.json", "watchdog_status.json"):
        assert (w.directory() / "archive" / relative).read_bytes() == case.payloads[relative]
        assert (case.raw / relative).read_bytes() == case.payloads[relative]


def test_resume_clears_only_authorized_stop_preserving_attempt_and_ledger(case):
    receipt = w.resume_control(case.root)
    after = p.read_json(case.raw / "control/state.json")
    expected = copy.deepcopy(case.original["control/state.json"])
    expected["jobs"][w.TARGET].update(
        stopped=None, not_before=0, resumed_by_revision=case.revision["id"]
    )
    assert after == expected
    assert after["jobs"][w.TARGET]["attempt"] == 1
    assert not (case.raw / "needs_attention.json").exists()
    assert_preserved(case)
    assert p.checked(receipt, "B_control_guard_resume_applied")["budget_unchanged"]
    assert receipt["old_failure_retained"] and receipt["previous_attempt_preserved"] == 1
    assert w.resume_control(case.root) == receipt


@pytest.mark.parametrize("change", ["target_attempt", "other_job", "active"])
def test_resume_rejects_any_unregistered_control_state_change(case, change):
    value = copy.deepcopy(case.original["control/state.json"])
    if change == "target_attempt":
        value["jobs"][w.TARGET]["attempt"] = 2
    elif change == "other_job":
        value["jobs"]["B_static_11"]["failures"] = 1
    else:
        value["active"]["unregistered"] = {"pid": 1234}
    w.b.write(case.raw / "control/state.json", value, immutable=False)
    with pytest.raises(ValueError, match="unchanged_failed_control_state"):
        w.resume_control(case.root)
    assert p.read_json(case.raw / "control/state.json") == value
    assert not (w.directory() / "resume_applied.json").exists()
    assert (case.raw / "needs_attention.json").read_bytes() == case.payloads[
        "needs_attention.json"
    ]


@pytest.mark.parametrize(
    "relative,guard",
    [
        ("budget/state.json", "budget_and_attempt_ledger_unchanged"),
        ("needs_attention.json", "only_registered_attention_marker"),
    ],
)
def test_resume_rejects_unregistered_budget_or_attention_change(case, relative, guard):
    w.b.write(case.raw / relative, {"foreign": True}, immutable=False)
    with pytest.raises(ValueError, match=guard):
        w.resume_control(case.root)
    assert (case.raw / "control/state.json").read_bytes() == case.payloads["control/state.json"]
    assert not (w.directory() / "resume_applied.json").exists()
    assert p.read_json(case.raw / relative) == {"foreign": True}


def test_interruption_after_state_write_recovers_once_with_same_intent(case, monkeypatch):
    original_write = w.b.write
    receipt_path = w.directory() / "resume_applied.json"
    interrupted = False

    def fail_receipt_once(path, value, immutable=True):
        nonlocal interrupted
        if Path(path) == receipt_path and not interrupted:
            interrupted = True
            raise RuntimeError("injected_receipt_failure_after_state_save")
        return original_write(path, value, immutable=immutable)

    monkeypatch.setattr(w.b, "write", fail_receipt_once)
    with pytest.raises(RuntimeError, match="injected_receipt_failure"):
        w.resume_control(case.root)
    assert not receipt_path.exists()
    assert not (case.raw / "needs_attention.json").exists()
    after = (case.raw / "control/state.json").read_bytes()
    intent = (w.directory() / "resume_intent.json").read_bytes()
    assert p.read_json(case.raw / "control/state.json")["jobs"][w.TARGET]["attempt"] == 1
    assert_preserved(case)
    receipt = w.resume_control(case.root)
    assert (case.raw / "control/state.json").read_bytes() == after
    assert (w.directory() / "resume_intent.json").read_bytes() == intent
    assert receipt["intent_id"] == p.read_json(w.directory() / "resume_intent.json")["id"]
    assert w.resume_control(case.root) == receipt
    assert_preserved(case)


def test_install_redirects_guard_and_all_child_entrypoints_with_revision_receipt(case, monkeypatch):
    w.resume_control(case.root)
    # install assigns module globals directly; pre-register their original values for teardown.
    monkeypatch.setattr(w.training, "_distribution", w.training._distribution)
    monkeypatch.setattr(w.runner, "SCRIPT", w.runner.SCRIPT)
    monkeypatch.setattr(w.runner, "implementation", w.runner.implementation)
    monkeypatch.setattr(w.runner, "publish_completed", w.runner.publish_completed)
    identity = dict(pid=4321, start_ticks=9876, command=["synthetic"], uid=1000, state="R")
    monkeypatch.setattr(w.runner.identity, "identity", lambda pid: identity)
    implementation_calls = []

    def original_implementation(root, plan):
        implementation_calls.append((root, plan))
        return {"id": "unchanged_original_implementation"}

    monkeypatch.setattr(w, "BASE_IMPLEMENTATION", original_implementation)
    publication_calls = []

    def original_publication(root, report):
        publication_calls.append((root, report))
        return True

    monkeypatch.setattr(w, "BASE_PUBLISH", original_publication)
    w.install(case.root, "worker", w.TARGET, 2)
    assert w.training._distribution is w.guard.revised_distribution
    assert w.runner.SCRIPT == w.SCRIPT
    validated_before = len(case.validation_calls)
    assert w.runner.implementation(case.root, {"id": "original_plan"}) == {
        "id": "unchanged_original_implementation"
    }
    assert len(case.validation_calls) == validated_before + 1
    assert implementation_calls == [(case.root, {"id": "original_plan"})]
    receipt = p.checked(
        p.read_json(w.directory() / "workers" / w.TARGET / "0002.json"),
        "B_control_guard_execution_process",
    )
    assert receipt["revision_id"] == case.revision["id"]
    assert receipt["mode"] == "worker" and receipt["attempt"] == 2
    assert receipt["guard_installed"] and receipt["identity"] == identity
    assert p.read_json(w.directory() / "processes/4321_9876.json") == receipt
    report = p.record("B_confirm_completed_study", protocol_id="original_plan")
    original_report = copy.deepcopy(report)
    assert w.runner.publish_completed(case.root, report) is True
    link = p.checked(
        p.read_json(w.directory() / "completion_link.json"),
        "B_control_guard_completed_report_link",
    )
    assert link["revision_id"] == case.revision["id"]
    assert link["scientific_report_id"] == report["id"]
    assert link["original_report_and_scientific_conclusions_not_modified"]
    assert report == original_report
    assert publication_calls == [(case.root, report)]


def test_install_requires_original_implementation_before_any_runtime_patch(case, monkeypatch):
    plan = dict(id=w.PLAN_ID)
    w.b.write(case.raw / "protocol.json", plan)
    revision = p.record(
        "B_control_guard_execution_revision",
        protocol_id=w.PLAN_ID,
        protocol_sha256=p.sha(case.raw / "protocol.json"),
    )
    w.b.write(w.directory() / "registration.json", revision)
    monkeypatch.setattr(w, "require_revision", REAL_REQUIRE_REVISION)
    monkeypatch.setattr(w.b, "read_protocol", lambda root: plan)

    def no_implementation_creation(*args):
        pytest.fail("The missing original implementation must never be regenerated.")

    monkeypatch.setattr(w, "BASE_IMPLEMENTATION", no_implementation_creation)
    original_guard, original_script = w.training._distribution, w.runner.SCRIPT
    with pytest.raises(ValueError, match="original_implementation_required"):
        w.install(case.root, "start")
    assert w.training._distribution is original_guard
    assert w.runner.SCRIPT == original_script
    assert not (case.raw / "implementation.json").exists()
    assert not (w.directory() / "processes").exists()
