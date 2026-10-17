"""Focused CPU/mock checks for removing only the R3 warm segment and anchor."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_finance_v50_reservation as prior

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
r = importlib.import_module("finqa_v53_reservation")
GIB = 1024**3


@pytest.fixture
def allocation(tmp_path, monkeypatch):
    source = prior.allocation.__wrapped__(tmp_path, monkeypatch)
    f = next(source)
    old = f.manager
    f.manager = r.Reservation(
        f.torch, tmp_path, dict(old.plan, gpu_reservation_policy=r.policy_record()),
        "CPU-context", "replay_R3", 0, control=old.control,
    )
    f.cuda.initial_free = 60 * GIB
    yield f
    f.manager.close()
    try:
        next(source)
    except StopIteration:
        pass


def test_R3_no_warm_no_anchor_no_snapshot_one_reset_and_rng_unchanged(allocation, monkeypatch):
    f = allocation
    monkeypatch.setattr(f.torch, "empty", lambda *_a, **_k: pytest.fail("R3 warm or anchor allocation"))
    monkeypatch.setattr(f.cuda, "memory_snapshot", lambda: pytest.fail("nonexistent R3 segment proof"))
    cpu_rng, cuda_rng = f.torch.get_rng_state(), f.cuda.get_rng_state()
    admission = f.manager.start(56 * GIB)
    assert f.manager.target == 0 and f.manager.anchor is None
    assert f.cuda.memory_reserved() == f.cuda.memory_allocated() == 0
    assert f.cuda.resets == 1
    assert admission["allocation_mode"] == "native_demand"
    assert admission["anchor_bytes"] == admission["warm_allocation_bytes"] == 0
    assert admission["segment"] is None
    assert admission["cpu_and_cuda_rng_unchanged"] is True
    assert (cpu_rng, cuda_rng) == (f.torch.get_rng_state(), f.cuda.get_rng_state())
    f.manager.mark_model_load_started()
    result = f.manager.report()
    assert result["native_demand_allocator_used"] is True
    assert result["reservation_held_through_final_scientific_boundary"] is False
    assert result["physical_free_observation_unmodified"] is True
    assert result["segment"] is None
    with pytest.raises(r.ReservationAdmissionError, match="later lifetime"):
        f.cuda.reset_peak_memory_stats()


def test_R3_original_empty_cache_runs_before_unchanged_backend(allocation, monkeypatch):
    f = allocation
    f.manager.start(56 * GIB)
    calls = []
    original_empty = f.cuda.empty_cache

    def empty_cache():
        calls.append("empty_cache")
        original_empty()

    monkeypatch.setattr(f.cuda, "empty_cache", empty_cache)

    class OriginalSession:
        bank = SimpleNamespace(resident_limit=2 * GIB, activation_resident_limit=16 * GIB)
        full_kv_budget_bytes = 8 * GIB

        def __call__(self, *_a, **_k):
            assert calls == ["empty_cache"]
            calls.append("original_backend")
            return "original-result"

    backend = SimpleNamespace(
        R3Session=OriginalSession,
        v32=SimpleNamespace(estimate_complete_kv_bytes=lambda *_a: GIB),
    )
    session = r.r3_session_class(backend, f.manager)()
    assert session(object(), None, [1], [2]) == "original-result"
    assert calls == ["empty_cache", "original_backend"]
    assert f.manager.response_calls == 1


def test_R3_reusable_cache_never_fakes_physical_free_and_failed_forward_is_zero(allocation):
    f = allocation
    f.manager.start(56 * GIB)
    # Simulate genuinely live tensors in a partly used native segment. empty_cache
    # cannot reclaim that segment; cached bytes still cannot satisfy the raw guard.
    f.cuda.live[1234] = 28 * GIB
    f.cuda.reserved, f.cuda.peak, f.cuda.initial_free = 60 * GIB, 28 * GIB, 63 * GIB
    session = SimpleNamespace(
        bank=SimpleNamespace(resident_limit=2 * GIB, activation_resident_limit=16 * GIB),
        full_kv_budget_bytes=8 * GIB,
    )
    backend = SimpleNamespace(
        v32=SimpleNamespace(estimate_complete_kv_bytes=lambda *_a: GIB),
        source_binding=lambda: dict(original="unchanged"),
    )
    with pytest.raises(r.R3CapacityError):
        f.manager.before_r3(session, object(), [1], [2], backend)
    proof = next(v for k, v in f.records.items() if k.endswith("r3_capacity_failure/record.json"))
    assessment = proof["assessment"]
    assert assessment["physical_free_bytes"] == 3 * GIB
    assert assessment["reusable_bytes"] == 32 * GIB
    assert assessment["available_pass"] and not assessment["raw_free_pass"]
    assert assessment["raw_required_free_bytes"] == 5 * GIB
    assert proof["failed_response_forward_calls"] == 0
    assert proof["schema"] == r.FAILURE_SCHEMA
    assert proof["allocation_mode"] == "native_demand"
    assert proof["physical_free_observation_unmodified"] is True
    assert proof["retry_capacity_condition"]["schema"] == r.RETRY_SCHEMA


@pytest.mark.parametrize("stage,minimum", [("train", 26), ("shard00", 24), ("distribution", 22), ("virtual_point", 22), ("generate", 24)])
def test_other_stages_keep_the_original_anchor_and_warm_peak(allocation, stage, minimum):
    f = allocation
    manager = r.Reservation(
        f.torch, f.manager.directory, f.manager.plan, "CPU-context", stage, 0,
        control=f.manager.control,
    )
    f.manager = manager
    f.cuda.initial_free = 36 * GIB
    admission = manager.start(minimum * GIB)
    assert manager.target == 32 * GIB
    assert admission["anchor_bytes"] == r.ANCHOR_BYTES
    assert admission["allocation_mode"] == "anchored_native_segment"
    assert f.cuda.memory_allocated() == r.ANCHOR_BYTES
    assert f.cuda.max_memory_allocated() == 32 * GIB
    f.cuda.empty_cache()
    manager.verify_before_model_load()
    result = manager.report()
    assert result["reservation_held_through_final_scientific_boundary"] is True
    assert result["native_demand_allocator_used"] is False
    assert result["segment"]["total_size"] == 32 * GIB


def test_R3_CPU_load_cannot_silently_allocate_scientific_CUDA_tensor(allocation):
    f = allocation
    f.manager.start(56 * GIB)
    unexpected = f.torch.empty(1024)
    with pytest.raises(r.ReservationAdmissionError, match="CPU state loading"):
        f.manager.verify_before_model_load()
    del unexpected


def test_fixed_admission_and_resource_limits_are_not_relaxed():
    assert r.target_bytes(53 * GIB, 56 * GIB, "replay_R3") == 0
    with pytest.raises(r.ReservationAdmissionError, match="admission allowance"):
        r.target_bytes(52 * GIB, 56 * GIB, "replay_R3")
    policy = r.policy_record()
    assert policy["minimum_free_gib_by_phase"]["replay_R3"] == 56
    assert policy["lifetime_allocated_limit_bytes"] == 76 * GIB
    assert policy["actual_boundary_free_reserve_bytes"] == 2 * GIB
    assert policy["R3_original_admission_predicates_unchanged"] is True
    assert policy["R3_cached_bytes_never_count_as_physical_free"] is True
