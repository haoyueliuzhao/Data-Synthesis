"""CPU-only four-worker admission, clean activation and unchanged resource shell."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v49_controller")


@pytest.fixture
def plan(tmp_path):
    return dict(
        id="v49",
        output_root=str(tmp_path),
        schema=subject.PROTOCOL_SCHEMA,
        allowed_gpu_indices=list(subject.ALLOWED_GPUS),
        gpu_uuids=subject.admission.GPU_UUIDS,
        max_gpu_workers=4,
        independent_total_worker_limit=4,
        total_worker_limit_removed=False,
        max_workers_per_gpu=1,
        host_admission_policy=subject.host_policy_record(),
        gpu_admission_policy=subject.policy_record(),
        gpu_reservation_policy=subject.reservation_policy_record(),
    )


def test_runtime_isolated_from_old_verifiers_and_all_sources_are_new_owned():
    assert subject.parent is not subject.verifier.parent
    assert subject.parent is not subject.base.verifier.parent
    assert subject.runtime.LeasePool is subject.LeasePool
    assert subject.parent.LeasePool is subject.LeasePool
    assert subject.runtime.memory_policy is subject.admission
    assert subject.verifier.ROOT == subject.PARENT_ROOT
    assert subject.verifier.parent.checked_protocol is not subject.checked_protocol
    assert len(subject.FILES) == 9 and "finqa_v49_handoff.py" in subject.FILES
    assert subject.MAX_GPU_WORKERS == 4 and subject.device_capacity() == 8
    assert subject.DISPATCH_ORDER == (5, 2, 0, 4, 3, 7, 1, 6)
    assert (
        subject.policy_record()["admission"][
            "maximum_total_workers_including_initializing_and_draining"
        ]
        == 4
    )
    assert (
        subject.verifier.policy_record()["admission"][
            "maximum_total_workers_including_initializing_and_draining"
        ]
        == 5
    )


@pytest.mark.parametrize("state", ["INITIALIZING", "WAITING", "RUNNING", "DRAINING"])
def test_fifth_slot_rejected_before_host_inventory_disk_or_runner_access(plan, monkeypatch, state):
    pool = subject.LeasePool(SimpleNamespace(protocol=plan))
    pool.leases = {gpu: SimpleNamespace(lifecycle_state=state) for gpu in range(4)}
    monkeypatch.setattr(pool, "_host_admission", lambda _: pytest.fail("slot cap before RAM"))
    monkeypatch.setattr(
        subject.parent, "inventory", lambda: pytest.fail("slot cap before GPU query")
    )
    assert pool.try_acquire(object(), "train") is None
    assert len(pool.leases) == 4


def test_existing_overcap_is_a_hard_state_failure(plan):
    pool = subject.LeasePool(SimpleNamespace(protocol=plan))
    pool.leases = {gpu: object() for gpu in range(5)}
    with pytest.raises(ValueError, match="slot cap exceeded"):
        pool.try_acquire(object(), "train")


def test_fourth_slot_can_run_and_closed_lease_releases_only_its_slot(plan, tmp_path, monkeypatch):
    pool = subject.LeasePool(SimpleNamespace(protocol=plan, disk_gate=lambda _: None))
    pool.leases = {gpu: object() for gpu in range(3)}
    monkeypatch.setattr(pool, "_host_admission", lambda _: True)
    row = dict(index=5, uuid=plan["gpu_uuids"]["5"], free_mib=64 * 1024, processes=[])
    monkeypatch.setattr(subject.parent, "inventory", lambda: [row])
    monkeypatch.setattr(subject.parent, "TRAINING_ROOT", tmp_path / "training")
    runner = SimpleNamespace(context={}, disk_projection=lambda _: 0)
    observed, lease = pool.try_acquire(runner, "train")
    assert observed is row and len(pool.leases) == 4
    lease.close()
    assert set(pool.leases) == {0, 1, 2}


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_gpu_workers", None),
        ("max_gpu_workers", 5),
        ("max_gpu_workers", 4.0),
        ("independent_total_worker_limit", None),
        ("total_worker_limit_removed", True),
    ],
)
def test_policy_rejects_missing_loose_or_nontyped_cap(plan, key, value, monkeypatch):
    plan[key] = value
    monkeypatch.setattr(subject.admission.time_policy, "validate", lambda _: None)
    with pytest.raises(subject.admission.AdmissionError, match="four total workers"):
        subject.admission.validate_plan(plan)


def test_policies_keep_resource_math_and_stop_contract(plan, monkeypatch):
    plan["host_ram_runtime_hard_gates_unchanged"] = True
    monkeypatch.setattr(subject.admission.time_policy, "validate", lambda _: None)
    assert subject.admission.validate_plan(plan) is plan
    policy = subject.reservation_policy_record()
    assert policy["total_worker_limit_removed"] is False
    assert policy["independent_total_worker_limit"] == 4
    assert (
        policy["pre_scientific_resource_wait"][
            "same_process_reservation_lease_and_worker_slot_retained"
        ]
        is True
    )
    assert policy["lifetime_allocated_limit_bytes"] == 76 * 1024**3
    assert policy["actual_boundary_free_reserve_bytes"] == 2 * 1024**3
    assert subject.parent.HOST_RAM["reserve_bytes"] == 96 * 1024**3


@pytest.mark.parametrize("module", ["cold_worker", "worker", "evaluation"])
def test_scientific_consumers_match_v48_except_new_producer_ownership(module):
    directory = Path(subject.__file__).parent
    previous = (directory / f"finqa_v48_{module}.py").read_text()
    current = (directory / f"finqa_v49_{module}.py").read_text()
    assert current == previous.replace("v48", "v49").replace("V48", "V49")


def test_resource_wait_state_machine_matches_v48_except_identity_and_cap_policy():
    directory = Path(subject.__file__).parent
    previous = (directory / "finqa_v48_reservation.py").read_text()
    expected = previous.replace("v48", "v49").replace("V48", "V49").replace(
        "        total_worker_limit_removed=True,",
        "        total_worker_limit_removed=False,\n        independent_total_worker_limit=4,",
    )
    assert (directory / "finqa_v49_reservation.py").read_text() == expected


def test_automatic_authority_retains_four_slots_and_no_new_dose(tmp_path, monkeypatch):
    monkeypatch.setattr(subject, "entry", lambda p: dict(path=str(p), id="sealed"))
    monkeypatch.setattr(subject, "_capacity_wait_reference", lambda _: None)
    value = subject.authorization_body(parentroot=tmp_path, automatic=True)
    assert value["max_gpu_workers"] == value["independent_total_worker_limit"] == 4
    assert value["total_worker_limit_removed"] is False
    assert value["effective_device_capacity"] == 8
    assert value["automatic_recovery_authorized"] is True
    assert value["new_sampling_or_optimizer_dose_authorized"] is False
    assert value["manual_stop_terminates_supervision"] is True
    assert value["unknown_feedback_retry_allowed"] is False


def test_initialize_requires_the_same_registered_supervision_before_inheriting(
    tmp_path, monkeypatch
):
    root = tmp_path / "v49"
    parentroot = tmp_path / "v48"
    monkeypatch.setattr(subject, "ROOT", root)
    monkeypatch.setattr(subject, "checked_implementation", lambda _: {})
    monkeypatch.setattr(
        subject,
        "checked_preparation",
        lambda: dict(parent_root=str(parentroot), parent_protocol=dict(path="original")),
    )
    monkeypatch.setattr(subject, "live_parent_protocol", lambda _: dict(supervision_root="wrong"))
    monkeypatch.setattr(subject, "entry", lambda p: dict(path=str(p)))
    monkeypatch.setattr(
        subject,
        "read_ref",
        lambda _: dict(
            parent_attempt_root=str(tmp_path / "unexpected"), parent_protocol=dict(path="original")
        ),
    )
    monkeypatch.setattr(
        subject.inheritance,
        "initialize_clean_handoff",
        lambda *a, **k: pytest.fail("wrong attempt"),
    )
    with pytest.raises(ValueError, match="registered parent supervision"):
        subject.initialize_with_handoff(dict(path="receipt"), root=root)


def test_activation_binds_actual_safe_successor_without_rewriting_preparation(
    tmp_path, monkeypatch
):
    root, original, successor = (
        tmp_path / "v49",
        tmp_path / "v48",
        tmp_path / "v48/attempts/attempt0002",
    )
    monkeypatch.setattr(subject, "ROOT", root)
    monkeypatch.setattr(subject, "LIVE_PARENT_ROOT", original)
    monkeypatch.setattr(subject, "checked_implementation", lambda _: {})
    monkeypatch.setattr(subject, "checked_preparation", lambda: dict(parent_root=str(original)))
    monkeypatch.setattr(subject, "entry", lambda p: dict(path=str(p)))
    receipt = dict(
        parent_attempt_root=str(successor),
        parent_protocol=dict(path=str(successor / "protocol/record.json")),
    )
    monkeypatch.setattr(subject, "read_ref", lambda _: receipt)
    monkeypatch.setattr(
        subject, "live_parent_protocol", lambda _: dict(supervision_root=str(original))
    )
    monkeypatch.setattr(
        subject, "authorization_body", lambda **k: dict(parent_protocol=receipt["parent_protocol"])
    )
    records, inherited = {}, []
    monkeypatch.setattr(subject, "publish", lambda p, body: records.setdefault(str(p), body))
    monkeypatch.setattr(
        subject.inheritance,
        "initialize_clean_handoff",
        lambda *a, **k: inherited.append((a, k)) or {},
    )
    monkeypatch.setattr(subject, "_finish_initialization", lambda *a: dict(id="activated"))
    assert subject.initialize_with_handoff(dict(path="receipt"), root=root)["id"] == "activated"
    assert inherited[0][0][1] == successor
    assert inherited[0][1]["authorization_record"]["path"] == str(
        root / "activation_authorization/record.json"
    )
    assert (
        records[str(root / "activation_authorization/record.json")]["parent_protocol"]
        == receipt["parent_protocol"]
    )
    assert str(root / "authorization/record.json") not in records


def test_live_prepare_freezes_authority_only_and_defers_actual_frontier(tmp_path, monkeypatch):
    root, parentroot = tmp_path / "v49", tmp_path / "v48"
    monkeypatch.setattr(subject, "ROOT", root)
    monkeypatch.setattr(subject, "live_parent_protocol", lambda _: {})
    monkeypatch.setattr(subject, "entry", lambda p: dict(path=str(p)))
    monkeypatch.setattr(subject, "freeze", lambda *a: dict(source_commit="commit"))
    monkeypatch.setattr(subject, "authorization_body", lambda **k: dict(max_gpu_workers=4))
    records = {}
    monkeypatch.setattr(subject, "publish", lambda p, body: records.setdefault(str(p), body))
    value = subject.prepare(root, source_commit="commit", parentroot=parentroot)
    assert value["handoff_required"] is True
    assert value["actual_frontier_deferred_until_clean_handoff"] is True
    assert value["scientific_controller_started"] is False
    assert value["max_gpu_workers"] == 4
    assert not any(
        "initial_state" in p or "protocol/record" in p or "inheritance" in p for p in records
    )
