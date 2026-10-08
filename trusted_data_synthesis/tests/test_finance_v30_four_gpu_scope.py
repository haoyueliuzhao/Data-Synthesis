"""CPU-only tests of the supplemental whitelist; never signal or start workers."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("v30_test", SCRIPTS / "finqa_v30_four_gpu_scope.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def forbid(*args, **kwargs):
    raise AssertionError("test must not launch real processes")


@pytest.fixture
def state(tmp_path, monkeypatch):
    base = c.v29.v28.predecessor_module()
    obj = object.__new__(c.controller_type(base))
    obj.root, obj.scope_root = tmp_path / "queue", tmp_path / "scope"
    obj.scope, obj.scope_ref = {"id": "scope"}, {"path": "/fixture/scope", "id": "scope"}
    obj.jobs = [dict(key=f"job{i}", kind="test", dependencies=[]) for i in range(6)]
    obj.completed, obj.children, obj.failures = set(), {}, []
    obj.stop = False
    obj.cooldowns, obj.rejections, obj.observations = {}, {}, {}
    obj.pending_checkpoint_resumes, obj.checkpoint_recoveries = {}, {}
    obj.plan = {"id": "original-v29"}
    obj.science = {
        "id": "original-science",
        "dispatch_disk_floor_bytes": 1024,
        "budgets": {"fixed": 24},
    }
    rows = [dict(index=i, uuid=f"GPU-{i}", free_mib=81154) for i in range(8)]
    legacy = SimpleNamespace(
        inventory=lambda: rows,
        disk_available=lambda _: 10**12,
        atomic_status=lambda root, value: setattr(obj, "last_status", value),
        cpu_command=forbid,
    )
    obj.legacy = c.ScopedLegacy(legacy, obj.scope_ref)
    obj.base = SimpleNamespace(assignments=base.assignments)
    monkeypatch.setattr(c.v29.v28, "compute_processes", lambda: set())
    monkeypatch.setattr(c.v29.subprocess, "Popen", forbid)
    monkeypatch.setattr(c, "SOURCE_ROOT", tmp_path / "science")
    return SimpleNamespace(obj=obj, rows=rows, monkeypatch=monkeypatch)


@pytest.mark.parametrize("gpu", [0, 1, 2, 6])
def test_direct_launch_rejects_excluded_card_even_when_idle(state, gpu):
    with pytest.raises(ValueError, match="outside four-GPU scope"):
        state.obj.launch(state.obj.jobs[0], state.rows[gpu])
    assert not state.obj.root.exists()


@pytest.mark.parametrize("resume_kind", ["fresh", "administrative", "automatic"])
def test_all_launch_paths_share_the_same_hard_gate(state, resume_kind):
    job = state.obj.jobs[0]
    state.obj.plan["origins"] = {job["key"]: {"state": resume_kind}}
    if resume_kind == "automatic":
        state.obj.pending_checkpoint_resumes[job["key"]] = {"id": "mock-proof"}
    with pytest.raises(ValueError, match="outside four-GPU scope"):
        state.obj.launch(job, state.rows[0])


def test_four_children_count_even_before_gpu_memory_is_used(state):
    state.obj.children = {str(gpu): {"gpu": gpu} for gpu in c.ALLOWED_GPUS}
    with pytest.raises(ValueError, match="capacity reached"):
        state.obj.launch(state.obj.jobs[0], state.rows[3])
    state.obj.legacy._legacy.inventory = forbid
    state.obj.dispatch()  # Capacity checked before querying device allocations.


def test_allowed_launch_delegates_to_original_resume_logic_without_changes(state):
    calls = []

    class Original:
        def launch(self, job, row):
            calls.append((job, row))
            return "original-result"

    obj = object.__new__(type("TestScoped", (c.ScopedMixin, Original), {}))
    obj.children = {}
    job, row = state.obj.jobs[0], state.rows[7]
    assert obj.launch(job, row) == "original-result"
    assert calls == [(job, row)]


def test_dispatch_filters_idle_excluded_cards_and_preserves_stability_rule(state):
    launched = []

    def record(job, row):
        launched.append(row["index"])
        state.obj.children[job["key"]] = {"gpu": row["index"]}

    state.obj.launch = record
    state.obj.dispatch()
    assert launched == []
    state.obj.dispatch()
    assert set(launched) == set(c.ALLOWED_GPUS)
    assert len(launched) == 4
    assert {gpu for gpu, floor in state.obj.observations} == set(c.ALLOWED_GPUS)


def test_excluded_idle_capacity_is_never_used_when_allowed_cards_are_full(state):
    for gpu in c.ALLOWED_GPUS:
        state.rows[gpu]["free_mib"] = 0
    state.obj.launch = forbid
    state.obj.dispatch()
    state.obj.dispatch()
    assert not any(state.obj.observations.values())


def test_resume_candidates_remain_scoped_and_require_idle_admission(state):
    state.obj.jobs = state.obj.jobs[:1]
    state.obj.pending_checkpoint_resumes[state.obj.jobs[0]["key"]] = {"id": "mock-proof"}
    state.monkeypatch.setattr(
        c.v29.v28, "compute_processes", lambda: {state.rows[gpu]["uuid"] for gpu in c.ALLOWED_GPUS}
    )
    state.obj.launch = forbid
    state.obj.dispatch()
    state.obj.dispatch()


def test_status_distinguishes_effective_scope_from_historical_registration(state):
    state.obj.status("WAITING_FOR_RESOURCES")
    status = state.obj.last_status
    assert status["protocol_id"] == "original-v29"
    assert status["scientific_protocol_id"] == "original-science"
    assert status["allowed_gpu_indices"] == [3, 4, 5, 7]
    assert status["max_gpu_workers"] == 4
    assert status["supplemental_resource_policy"] == state.obj.scope_ref
    assert status["predecessor_registered_allowed_gpu_indices"] == list(range(8))
    assert status["predecessor_registered_max_gpu_workers"] == 6
    assert status["excluded_gpus_reusable_when_idle"] is False


def test_adoption_rejects_excluded_worker_without_side_effects(state):
    with pytest.raises(ValueError, match="adoption outside"):
        state.obj.adopt(state.obj.jobs[0], {"gpu": 0})
    assert not state.obj.root.exists()


@pytest.mark.parametrize("gpu,accepted", [(3, True), (0, False)])
def test_initialization_restores_same_queue_without_restarting_workers(state, gpu, accepted):
    children = {"retained": {"gpu": gpu, "pid": 1234, "birth": "mock-birth", "process": None}}
    restored = []

    class Original:
        _frozen_base = SimpleNamespace(verify_source=lambda: ({}, object()))

        def __init__(self, root, resume=False):
            restored.append((root, resume))
            self.children = children
            self.legacy = object()

    test_type = type("TestScoped", (c.ScopedMixin, Original), {})
    state.monkeypatch.setattr(c, "verify_policy", lambda root: {"id": "scope"})
    state.monkeypatch.setattr(c, "entry", lambda path: {"path": str(path), "id": "scope"})
    state.monkeypatch.setattr(c, "verify_handoff", lambda root, legacy: {})
    if accepted:
        obj = test_type(state.obj.scope_root)
        assert obj.children is children
        assert obj.children["retained"]["pid"] == 1234
    else:
        with pytest.raises(ValueError, match="ownership bound"):
            test_type(state.obj.scope_root)
    assert restored == [(c.QUEUE_ROOT, True)]


def test_final_result_preserves_science_and_explicitly_binds_scope(state):
    for relative in (
        "protocol/record.json",
        "c_only_test_extension/summary/record.json",
        "replication_evaluation/summary/record.json",
        "descriptive_six_seed_summary/record.json",
    ):
        c.publish(c.SOURCE_ROOT / relative, {"kind": relative})
    obj = state.obj
    obj.completed = {job["key"] for job in obj.jobs}
    scores = []
    obj.score_ready_blocks = lambda: scores.append("original scorer")
    obj.run()
    result = c.checked(obj.root / "result/record.json")
    assert result["scientific_protocol_id"] == "original-science"
    assert result["registered_budgets"] == obj.science["budgets"]
    assert result["supplemental_resource_policy"] == obj.scope_ref
    assert result["allowed_gpu_indices"] == [3, 4, 5, 7]
    assert result["max_gpu_workers"] == 4
    assert c.checked(obj.scope_root / "result/record.json")["queue_result"] == c.entry(
        obj.root / "result/record.json"
    )
    assert scores == ["original scorer"]
    assert obj.last_status["phase"] == "REPLICATION_COMPLETE"


@pytest.mark.parametrize(
    "mutation", [None, "live_controller", "outside_worker", "changed_snapshot"]
)
def test_handoff_binds_controller_identity_and_worker_snapshot(state, mutation):
    obj = state.obj
    state.monkeypatch.setattr(c, "QUEUE_ROOT", obj.root)
    old_launch = obj.root / "launch_01/record.json"
    c.publish(
        old_launch, {"pid": 5678, "birth": "controller-birth", "protocol_id": c.PREDECESSOR_ID}
    )
    job = obj.jobs[0]
    attempt = obj.root / "queue/jobs/job0/attempt001"
    child = dict(
        job=job,
        gpu=0 if mutation == "outside_worker" else 7,
        pid=1234,
        birth="worker-birth",
        attempt=str(attempt),
    )
    c.publish(attempt / "launch/record.json", {k: v for k, v in child.items() if k != "attempt"})
    snapshot = obj.scope_root / "handoff_snapshot/status.json"
    snapshot.parent.mkdir(parents=True)
    value = dict(
        protocol_id=c.PREDECESSOR_ID, failures=[], active_children=[child], phase="DRAINING_ON_STOP"
    )
    snapshot.write_text(json.dumps(value))
    handoff = dict(
        predecessor_controller_launch=c.entry(old_launch),
        controller_pid=5678,
        birth="controller-birth",
        post_handoff_controller_absent=True,
        no_worker_signals=True,
        predecessor_status_snapshot={**c.file_entry(snapshot), "value": value},
        retained_worker_launches=[c.entry(attempt / "launch/record.json")],
    )
    c.publish(obj.scope_root / "handoff/record.json", handoff)
    if mutation == "changed_snapshot":
        snapshot.write_text("{}")
    legacy = SimpleNamespace(
        process_birth=lambda pid: "controller-birth" if mutation == "live_controller" else None
    )
    if mutation:
        with pytest.raises(ValueError):
            c.verify_handoff(obj.scope_root, legacy)
    else:
        assert c.verify_handoff(obj.scope_root, legacy)["controller_pid"] == 5678
