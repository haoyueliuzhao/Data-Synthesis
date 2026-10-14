"""CPU-only empirical RAM admission and V45 consumer namespace checks."""

import copy
import importlib
import sys
from pathlib import Path

import pytest
import test_finance_v43_consumers as v43_tests
import test_finance_v44_consumers as v44_tests

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
admission = importlib.import_module("finqa_v45_admission")
worker = importlib.import_module("finqa_v45_worker")
evaluation = importlib.import_module("finqa_v45_evaluation")
GIB = 1024**3


@pytest.fixture
def resource(tmp_path, monkeypatch):
    f = v43_tests.resource.__wrapped__(tmp_path)
    plan = f.kwargs["plan"]
    plan.update(
        max_gpu_workers=5,
        max_workers_per_gpu=1,
        host_admission_policy=admission.host_policy_record(),
        host_ram_admission_changed=True,
        host_ram_runtime_hard_gates_unchanged=True,
        dispatch_priority=[5, 2, 0, 4, 3, 7, 1, 6],
    )
    plan["gpu_admission_policy"]["admission"][
        "maximum_total_workers_including_initializing_and_draining"
    ] = 5
    # Reuse only existing behavioral assertions, against the new real modules.
    monkeypatch.setattr(v44_tests, "admission", admission)
    monkeypatch.setattr(v44_tests, "worker", worker)
    monkeypatch.setattr(v44_tests, "evaluation", evaluation)
    return f


@pytest.mark.parametrize(
    ("stage", "phase", "expected"),
    [
        ("shard00", "class", 160),
        ("shard03", "class", 160),
        ("train", "train", 48),
        ("replay_R3", "replay_R3", 48),
        ("generate", "generate", 48),
        ("virtual_point", "virtual_point", 64),
        ("distribution", "distribution", 64),
    ],
)
def test_historical_peaks_derive_the_registered_budgets(stage, phase, expected):
    peak = admission.HISTORICAL_PEAK_BYTES[phase]
    assert admission.padded_peak_bytes(peak) == expected * GIB
    assert admission.startup_budget_bytes(stage) == expected * GIB
    assert admission.host_memory_requirement(stage, []) == (96 + expected) * GIB


def test_old_full_cap_reservation_example_is_reduced_without_changing_runtime_caps():
    active = [
        dict(stage="replay_R3", rss_bytes=368 * GIB // 100, peak_rss_bytes=17 * GIB),
        dict(stage="virtual_point", rss_bytes=1633 * GIB // 100, peak_rss_bytes=30 * GIB),
        dict(stage="train", rss_bytes=291 * GIB // 100, peak_rss_bytes=17 * GIB),
    ]
    old_requirement = 96 * GIB + 160 * GIB + sum(
        192 * GIB - row["rss_bytes"] for row in active
    )
    new_requirement = admission.host_memory_requirement("shard01", active)
    assert old_requirement - new_requirement == 416 * GIB
    assert new_requirement / GIB == pytest.approx(393.08)
    assert admission.host_policy_record()["runtime_rss_limit_bytes"] == {
        "class": 160 * GIB,
        "other": 192 * GIB,
    }


def test_lifetime_peak_increases_reservation_even_when_current_rss_is_small():
    row = dict(stage="train", rss_bytes=10 * GIB, peak_rss_bytes=80 * GIB)
    assert admission.padded_peak_bytes(80 * GIB) == 112 * GIB
    assert admission.host_memory_requirement("distribution", [row]) == 262 * GIB
    row["peak_rss_bytes"] = 96 * GIB
    assert admission.host_memory_requirement("distribution", [row]) == 278 * GIB


@pytest.mark.parametrize(
    "change",
    [
        {"rss_bytes": None},
        {"peak_rss_bytes": None},
        {"rss_bytes": float("nan")},
        {"rss_bytes": True},
        {"rss_bytes": -1},
        {"rss_bytes": 21 * GIB},
        {"peak_rss_bytes": 193 * GIB},
        {"observed": False},
        {"observed": None},
    ],
)
def test_invalid_live_measurements_defer_dispatch_without_zero_fallback(change):
    row = dict(stage="train", rss_bytes=10 * GIB, peak_rss_bytes=20 * GIB)
    row.update(change)
    assert admission.host_memory_requirement("generate", [row]) is None


def test_missing_process_record_and_class_hard_limit_defer_dispatch():
    assert admission.host_memory_requirement("generate", [None]) is None
    assert admission.host_memory_requirement("generate", None) is None
    assert admission.host_memory_requirement(
        "generate", [dict(stage="shard00", rss_bytes=10 * GIB, peak_rss_bytes=161 * GIB)]
    ) is None


def test_unknown_stage_is_configuration_error_not_resource_scarcity():
    with pytest.raises(ValueError, match="unknown registered"):
        admission.host_memory_requirement("unknown", [])
    with pytest.raises(ValueError, match="unknown registered"):
        admission.host_memory_requirement(
            "train", [dict(stage="shard04", rss_bytes=0, peak_rss_bytes=0)]
        )


def test_policy_rejects_unregistered_evidence_and_exposes_empirical_limit():
    policy = admission.host_policy_record()
    assert policy["historical_successful_process_count"] == 91
    assert policy["historical_peaks_are_not_future_upper_bounds"] is True
    assert policy["current_RSS_alone_is_not_future_peak_estimate"] is True
    assert policy["evidence_refs"] == [admission.EVIDENCE_REF]
    altered = copy.deepcopy(policy["evidence_refs"])
    altered[0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="unregistered"):
        admission.host_policy_record(evidence_refs=altered)


@pytest.mark.parametrize("field", ["host_admission_policy", "dispatch_priority"])
def test_registered_policy_or_priority_cannot_drift(resource, field):
    resource.kwargs["plan"][field] = {}
    with pytest.raises(ValueError, match="host policy|GPU5 and GPU2"):
        admission.validate_plan(resource.kwargs["plan"])


def test_shared_gpu_thresholds_and_hard_runtime_gates_remain(resource):
    v44_tests.test_five_slots_keep_actual_shared_gpu_and_null_deadline(resource)


@pytest.mark.parametrize("capacity", [4, 6])
def test_only_five_slots_are_authorized(resource, capacity):
    v44_tests.test_capacity_mismatch_fails_before_admission(resource, capacity)


def test_worker_routes_new_host_policy_and_same_point_inheritance(resource, monkeypatch, tmp_path):
    v44_tests.test_worker_routes_new_inheritance_without_modifying_original_context(
        resource, monkeypatch, tmp_path
    )
    v44_tests.test_class_window_uses_v44_inheritance_and_keeps_four_math_shards(
        resource, monkeypatch
    )


def test_evaluation_routes_all_nine_barrier_and_actual_generate_cli(
    resource, monkeypatch, tmp_path
):
    v44_tests.test_score_api_routes_original_barrier_without_scoring(
        resource, monkeypatch, tmp_path
    )
    v44_tests.test_evaluation_accepts_exact_controller_generate_argv(monkeypatch, tmp_path)
