"""CPU-only adopted-worker provenance controls; no real jobs or model loads."""

import importlib.util
from pathlib import Path

import pytest


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


TESTS = Path(__file__).resolve().parent
p = module(TESTS.parent / "scripts/finqa_v29_checkpoint_resume.py", "v29_checkpoint_proof_tests")
base = module(TESTS / "test_finance_v28_checkpoint_resume.py", "v29_prior_checkpoint_fixtures")


@pytest.fixture
def failure(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "p", p)
    f = base.failure.__wrapped__(tmp_path, monkeypatch)
    protocol = base.rewrite(
        f.queue / "protocol/record.json", schema="v29_registered_four_gpu_release_continuation.v1"
    )
    for kind in ("launch", "intent", "exit"):
        base.rewrite(f.attempt / f"{kind}/record.json", protocol_id=protocol["id"])
    f.launch = p.checked(f.attempt / "launch/record.json")
    return f


def wrap(f, monkeypatch, resume=False):
    if resume:
        f.launch["command"] = [*f.launch["command"], "--resume"]
        base.rewrite(f.scientific / "intent/record.json", explicit_resume=True)
    wrapper = base.wrap_command(f)
    monkeypatch.setattr(p, "FROZEN_IMPLEMENTATION", wrapper.parent)
    monkeypatch.setattr(
        p, "FROZEN_SHA", p.FROZEN_SHA | {wrapper.name: p.reference(wrapper)["sha256"]}
    )
    f.wrapper = wrapper
    return wrapper


def adopt(f, queue_name):
    old_attempt = f.attempt
    old_launch = p.checked(old_attempt / "launch/record.json")
    f.queue = f.root / queue_name
    f.attempt = f.queue / "queue/jobs" / f.key / "attempt001"
    protocol = base.write_json(
        f.queue / "protocol/record.json",
        dict(
            schema="v29_registered_four_gpu_release_continuation.v1",
            scientific_protocol={"id": "science"},
            jobs=[f.context["job"]],
        ),
    )
    launch = old_launch | dict(
        protocol_id=protocol["id"],
        adopted_existing_process=True,
        origin_launch=base.bound_ref(old_attempt / "launch/record.json"),
        origin_attempt=str(old_attempt),
    )
    for kind in ("launch", "intent"):
        base.write_json(f.attempt / f"{kind}/record.json", launch)
    base.write_json(
        f.attempt / "exit/record.json",
        dict(
            protocol_id=protocol["id"],
            scientific_protocol_id="science",
            key=f.key,
            exit_code=None,
            completed=False,
            result=None,
        ),
    )
    (f.attempt / "worker.log").write_text("shadow log is not the scientific traceback")
    return old_attempt


def prove(f):
    return p.prove_checkpoint_oom_resume(f.root, f.queue, f.key, f.attempt)


@pytest.mark.parametrize(
    "wrapped,resume,layers",
    [
        (False, False, 0),
        (False, False, 2),
        (True, False, 0),
        (True, True, 0),
        (True, False, 1),
        (True, True, 3),
    ],
)
def test_direct_and_multilayer_adopted_workers_keep_exact_checkpoint(
    failure, monkeypatch, wrapped, resume, layers
):
    f = failure
    if wrapped:
        wrap(f, monkeypatch, resume=resume)
    original = f.attempt
    for index in range(layers):
        adopt(f, f"adopted_{index}")
    before = {str(path): path.stat().st_mtime_ns for path in f.root.rglob("*") if path.is_file()}
    result = prove(f)
    assert result["eligible"] and result == prove(f)
    assert result["resume_checkpoint"] == str(f.checkpoint)
    assert result["original_execution_attempt"] == str(original)
    assert result["references"]["worker_log"]["path"] == str(original / "worker.log")
    assert len(result["adopted_launch_chain"]) == layers
    assert result["feedback_resampling"] is False
    assert before == {
        str(path): path.stat().st_mtime_ns for path in f.root.rglob("*") if path.is_file()
    }


def test_new_v29_resume_may_use_frozen_v28_wrapper_with_current_receipt(failure, monkeypatch):
    f = failure
    wrapper = wrap(f, monkeypatch, resume=True)
    original_attempt = f.attempt
    old_launch = p.checked(original_attempt / "launch/record.json")
    old_receipt = p.checked(original_attempt / "memory_reservation/wrapper_intent.json")
    f.queue = f.root / "v29_new_execution"
    f.attempt = f.queue / "queue/jobs" / f.key / "attempt001"
    protocol = base.write_json(
        f.queue / "protocol/record.json",
        dict(
            schema="v29_registered_four_gpu_release_continuation.v1",
            scientific_protocol={"id": "science"},
            jobs=[f.context["job"]],
        ),
    )
    command = list(old_launch["command"])
    command[command.index("--receipt-dir") + 1] = str(f.attempt / "memory_reservation")
    for kind in ("launch", "intent"):
        base.write_json(
            f.attempt / f"{kind}/record.json",
            old_launch
            | dict(
                command=command, protocol_id=protocol["id"], administrative_checkpoint_resume=True
            ),
        )
    base.write_json(
        f.attempt / "exit/record.json",
        p.checked(original_attempt / "exit/record.json") | dict(protocol_id=protocol["id"]),
    )
    base.write_json(f.attempt / "memory_reservation/wrapper_intent.json", old_receipt)
    (f.attempt / "worker.log").write_text((original_attempt / "worker.log").read_text())
    result = prove(f)
    assert result["wrapper_evidence"]["source"]["path"] == str(wrapper)
    assert result["wrapper_evidence"]["intent"]["path"].startswith(str(f.attempt))


@pytest.mark.parametrize(
    "case",
    [
        "pid",
        "birth",
        "mode",
        "origin_protocol",
        "origin_intent",
        "receipt_pid",
        "receipt_seed",
        "receipt_mode",
        "wrapper",
        "shadow_exit",
        "shadow_protocol",
        "alive",
        "session",
        "missing_scientific_oom",
        "partial_feedback",
        "administrative_stop",
    ],
)
def test_multilayer_adoption_rejects_changed_or_unsettled_evidence(failure, monkeypatch, case):
    f = failure
    wrap(f, monkeypatch, resume=True)
    original = adopt(f, "adopted_first")
    adopt(f, "adopted_second")
    if case in {"pid", "birth", "mode"}:
        key, value = {
            "pid": ("pid", 888),
            "birth": ("birth", "777"),
            "mode": ("memory_mode", "high_cache"),
        }[case]
        for kind in ("launch", "intent"):
            base.rewrite(f.attempt / f"{kind}/record.json", **{key: value})
    elif case == "origin_protocol":
        base.rewrite(original.parents[3] / "protocol/record.json", jobs=[])
    elif case == "origin_intent":
        base.rewrite(original / "intent/record.json", protocol_id="foreign")
    elif case.startswith("receipt_"):
        receipt = original / "memory_reservation/wrapper_intent.json"
        key, value = {
            "receipt_pid": ("pid", 333),
            "receipt_mode": ("memory_mode", "high_cache"),
            "receipt_seed": ("original_command", ["foreign", "--seed", "389"]),
        }[case]
        base.rewrite(receipt, **{key: value})
    elif case == "wrapper":
        f.wrapper.write_text("changed wrapper bytes")
    elif case == "shadow_exit":
        base.rewrite(f.attempt / "exit/record.json", protocol_id="foreign")
    elif case == "shadow_protocol":
        base.rewrite(f.queue / "protocol/record.json", schema="not-v29")
    elif case == "alive":
        monkeypatch.setattr(p.h, "process_snapshot", lambda _: dict(birth="99999", state="R"))
    elif case == "session":
        monkeypatch.setattr(p.h, "live_session_members", lambda _: [dict(pid=222)])
    elif case in {"missing_scientific_oom", "administrative_stop"}:
        base.rewrite(f.scientific / "stopped/record.json", error_type="KeyboardInterrupt")
    else:
        (f.arm / "feedback/partial_new_outer").mkdir(parents=True)
    with pytest.raises(ValueError):
        prove(f)


def test_null_exit_without_adoption_is_rejected(failure):
    base.rewrite(failure.attempt / "exit/record.json", exit_code=None)
    with pytest.raises(ValueError, match="unsuccessful"):
        prove(failure)


def test_adopted_partial_later_feedback_remains_ineligible(failure, monkeypatch):
    wrap(failure, monkeypatch)
    point = base.add_history(failure)
    adopt(failure, "adopted")
    assert prove(failure)["historical_feedback"]["completed_outer_count"] == 1
    base.rewrite(point / "draw1/generation_seal/seal.json", complete=False)
    with pytest.raises(ValueError, match="partial historical"):
        prove(failure)


def test_adopted_first_outer_requires_original_phase_audit(failure, monkeypatch):
    wrap(failure, monkeypatch)
    adopt(failure, "adopted")
    base.rewrite(failure.scientific / "stopped/record.json", outer_failure_audit=None)
    with pytest.raises(ValueError, match="first outer"):
        prove(failure)
