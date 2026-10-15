"""CPU/mock coverage; the separately registered 2GiB GPU probe is not repeated."""

import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_finance_v43_consumers as old_tests

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
a = importlib.import_module("finqa_v47_admission")
r = importlib.import_module("finqa_v47_reservation")
GIB = 1024**3


@pytest.fixture
def resource(tmp_path):
    f = old_tests.resource.__wrapped__(tmp_path)
    f.kwargs["plan"].update(
        gpu_admission_policy=a.gpu_policy_record(),
        gpu_reservation_policy=a.reservation_policy_record(),
        host_admission_policy=a.host_policy_record(),
        host_ram_runtime_hard_gates_unchanged=True,
        max_gpu_workers=None,
        independent_total_worker_limit=None,
        total_worker_limit_removed=True,
        max_workers_per_gpu=1,
    )
    return f


def test_shared_train_below_old_32GiB_gate_is_actually_admitted(resource):
    resource.kwargs["stage"] = "train"
    resource.ready["free_mib"] = 28 * 1024
    assert a.wait_for_pre_cuda_admission(**resource.kwargs) is resource.ready
    assert resource.status()["minimum_free_mib"] == 26 * 1024
    assert resource.status()["cuda_initialized"] is False
    assert resource.status()["gpu"]["processes"]


@pytest.mark.parametrize(
    "stage,expected",
    [
        ("shard00", 24),
        ("shard03", 24),
        ("train", 26),
        ("generate", 24),
        ("distribution", 22),
        ("replay_R3", 56),
    ],
)
def test_registered_shared_thresholds(stage, expected):
    assert a.minimum_free_mib(stage, None) == expected * 1024


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_gpu_workers", 5),
        ("independent_total_worker_limit", 8),
        ("max_workers_per_gpu", 2),
        ("total_worker_limit_removed", False),
    ],
)
def test_no_independent_cap_and_one_worker_per_device(resource, field, value):
    resource.kwargs["plan"][field] = value
    with pytest.raises(ValueError, match="independent worker cap"):
        a.validate_plan(resource.kwargs["plan"])


def test_reservation_target_fits_admission_after_context_initialization():
    assert r.target_bytes(36 * GIB, 26 * GIB, "train") == 32 * GIB
    assert r.target_bytes(53 * GIB, 56 * GIB, "replay_R3") == 45 * GIB
    assert r.target_bytes(79 * GIB, 24 * GIB, "shard00") == 72 * GIB
    with pytest.raises(r.ReservationAdmissionError):
        r.target_bytes(52 * GIB, 56 * GIB, "replay_R3")


def test_R3_capacity_keeps_physical_and_reusable_predicates_distinct():
    value = r.assess_r3_capacity(28 * GIB, 30 * GIB, 10 * GIB, 80 * GIB, GIB)
    assert value["physical_free_pass"] and value["raw_free_pass"]
    assert value["available_bytes"] == 12 * GIB
    assert value["required_available_bytes"] == 21 * GIB
    assert not value["available_pass"] and value["recoverable_when_capacity_changes"]


def test_same_capacity_with_own_context_reclaimed_does_not_restart(resource):
    value = r.assess_r3_capacity(28 * GIB, 52 * GIB, 3 * GIB, 80 * GIB, GIB)
    assert value["available_pass"] and not value["raw_free_pass"]
    condition = value["retry_capacity_condition"]
    assert condition["failed_available_capacity_bytes"] == 55 * GIB
    row = dict(resource.ready, free_mib=int(58 * 1024))
    assert not a.check_retry_capacity(condition, [row])
    row["free_mib"] = 59 * 1024
    assert a.check_retry_capacity(condition, [row])
    assert not a.check_retry_capacity(condition, [dict(row, uuid="foreign")])


@pytest.mark.parametrize(
    "values",
    [
        (60, 62, 10, 80, 1),  # Declared allocated budget would exceed lifetime cap.
        (28, 29, 10, 40, 1),  # Device cannot accommodate the required dispatch capacity.
        (28, 30, 3, 80, 5),  # Fixed eight-GiB physical headroom cannot satisfy raw guard.
    ],
)
def test_impossible_fixed_budget_cannot_cold_retry(values):
    value = r.assess_r3_capacity(*(item * GIB for item in values))
    assert not value["recoverable_when_capacity_changes"]
    assert not r.check_retry_capacity(value["retry_capacity_condition"], [dict(free_mib=80 * 1024)])


class FakeTensor:
    def __init__(self, cuda, size):
        self.cuda, self.size = cuda, size
        self.address = cuda.address + sum(cuda.live.values())
        if not cuda.reserved:
            cuda.reserved = size
            self.address = cuda.address
        assert sum(cuda.live.values()) + size <= cuda.reserved
        cuda.live[self.address] = size
        cuda.peak = max(cuda.peak, sum(cuda.live.values()))

    def data_ptr(self):
        return self.address

    def zero_(self):
        return self

    def __del__(self):
        self.cuda.live.pop(self.address, None)


class FakeCuda:
    def __init__(self):
        self.initialized = False
        self.initial_free = 36 * GIB
        self.reserved = self.peak = self.resets = 0
        self.address = 1024
        self.live = {}
        self.memory = SimpleNamespace(get_allocator_backend=lambda: "native")

    def is_initialized(self):
        return self.initialized

    def reset_peak_memory_stats(self):
        self.initialized = True
        self.resets += 1
        self.peak = sum(self.live.values())

    def synchronize(self):
        pass

    def mem_get_info(self):
        return self.initial_free - self.reserved, 80 * GIB

    def memory_allocated(self):
        return sum(self.live.values())

    def memory_reserved(self):
        return self.reserved

    def max_memory_allocated(self):
        return self.peak

    def max_memory_reserved(self):
        return self.reserved

    def empty_cache(self):
        if not self.live:
            self.reserved = 0

    def get_rng_state(self):
        return b"unchanged CUDA RNG"

    def memory_snapshot(self):
        return [
            dict(
                address=self.address,
                total_size=self.reserved,
                allocated_size=self.memory_allocated(),
                active_size=self.memory_allocated(),
                stream=0,
                segment_type="large",
                is_expandable=False,
            )
        ]


@pytest.fixture
def allocation(tmp_path, monkeypatch):
    for name in ("PYTORCH_CUDA_ALLOC_CONF", "PYTORCH_ALLOC_CONF", "PYTORCH_NO_CUDA_MEMORY_CACHING"):
        monkeypatch.delenv(name, raising=False)
    cuda = FakeCuda()
    torch = SimpleNamespace(
        __version__="2.7.1+cu128",
        uint8="uint8",
        cuda=cuda,
        empty=lambda size, **_kw: FakeTensor(cuda, size),
        get_rng_state=lambda: b"unchanged CPU RNG",
        equal=lambda x, y: x == y,
    )
    records = {}

    def publish(path, value):
        records[str(path)] = value
        return dict(value, id="CPU-record")

    control = SimpleNamespace(
        birth=lambda _pid: "CPU-birth",
        now=lambda: "CPU-time",
        publish=publish,
        entry=lambda path: dict(path=str(path), sha256="CPU-sha", id="CPU-record"),
        checked=lambda path: records[str(path)],
        digest=lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest(),
    )
    plan = dict(id="CPU-protocol", gpu_uuids=a.GPU_UUIDS, gpu_reservation_policy=r.policy_record())
    manager = r.Reservation(torch, tmp_path, plan, "CPU-context", "train", 2, control=control)
    yield SimpleNamespace(manager=manager, cuda=cuda, torch=torch, records=records)
    manager.close()


def test_anchor_pool_survives_real_cleanup_api_and_keeps_warm_peak(allocation):
    f = allocation
    f.manager.start(26 * GIB)
    assert f.manager.target == 32 * GIB
    assert f.cuda.memory_allocated() == r.ANCHOR_BYTES
    assert f.cuda.memory_reserved() == f.cuda.max_memory_allocated() == 32 * GIB
    f.cuda.empty_cache()
    f.manager.verify_before_model_load()
    with pytest.raises(r.ReservationAdmissionError, match="later lifetime"):
        f.cuda.reset_peak_memory_stats()
    assert f.cuda.resets == 1
    result = f.manager.report()
    assert result["reservation_held_through_final_scientific_boundary"]
    f.manager.close()
    assert f.cuda.memory_reserved() == 0


def test_extra_CUDA_tensor_during_CPU_load_is_not_mislabelled(allocation):
    f = allocation
    f.manager.start(26 * GIB)
    unexpected = f.torch.empty(1024)
    with pytest.raises(r.ReservationAdmissionError, match="CPU state loading"):
        f.manager.verify_before_model_load()
    del unexpected


def test_external_free_drop_is_typed_before_any_R3_forward(allocation):
    f = allocation
    f.manager.start(26 * GIB)
    f.manager.stage = "replay_R3"
    f.cuda.initial_free = 33 * GIB  # One GiB of actual physical free remains.
    session = SimpleNamespace(
        bank=SimpleNamespace(resident_limit=2 * GIB, activation_resident_limit=16 * GIB),
        full_kv_budget_bytes=8 * GIB,
    )
    backend = SimpleNamespace(
        v32=SimpleNamespace(estimate_complete_kv_bytes=lambda *_a: GIB),
        source_binding=lambda: dict(original="unchanged CPU mathematical binding"),
    )
    with pytest.raises(r.R3CapacityError):
        f.manager.before_r3(session, object(), [1], [2], backend)
    proof = next(v for k, v in f.records.items() if k.endswith("r3_capacity_failure/record.json"))
    assert proof["failed_response_forward_calls"] == 0
    assert proof["assessment"]["physical_free_bytes"] == GIB
    assert proof["assessment"]["physical_free_pass"] is False
    assert proof["before_scientific_response"] is True
