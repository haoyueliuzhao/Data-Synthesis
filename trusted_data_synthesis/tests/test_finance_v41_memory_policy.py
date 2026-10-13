"""CPU-only checks for phase-specific admission; no controller or CUDA imports."""

import importlib
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v41_memory_policy")


@pytest.fixture
def protocol():
    return {
        "allowed_gpu_indices": [0, 4, 7],
        "gpu_uuids": {str(i): f"GPU-test-{i}" for i in (0, 4, 7)},
    }


@pytest.fixture
def row():
    return {"index": 4, "uuid": "GPU-test-4", "free_mib": 48 * 1024, "processes": []}


PHASES = [
    ("shard00", {}, "class", 28),
    ("shard01", {}, "class", 28),
    ("shard02", {}, "class", 28),
    ("shard03", {}, "class", 28),
    ("train", {}, "train", 32),
    ("replay_R3", {}, "replay_R3", 48),
    ("virtual_point", {"feedback": {"mode": "sealed_existing"}}, "virtual_existing", 24),
    ("virtual_point", {"feedback": {"mode": "first_sampling"}}, "virtual_first_sampling", 32),
    ("distribution", {}, "distribution", 24),
    ("generate", {}, "generate", 48),
]


@pytest.mark.parametrize("stage,context,phase,gib", PHASES)
def test_exact_phase_and_threshold_boundary(protocol, row, stage, context, phase, gib):
    assert subject.phase_key(stage, context) == phase
    assert subject.minimum_free_mib(stage, context) == gib * 1024
    for difference, eligible in [(-1, False), (0, True), (1, True)]:
        observed = dict(row, free_mib=gib * 1024 + difference)
        assert subject.eligible_gpu(observed, protocol, stage, context, worker_pid=999) is eligible


def test_shared_external_pids_admitted_without_changing_input(protocol, row):
    row["processes"] = [{"pid": 42, "used_memory_mib": "19000"}, {"pid": 71}]
    row["free_mib"] = 28 * 1024
    before = deepcopy((row, protocol))
    assert subject.eligible_gpu(row, protocol, "shard00", {}, worker_pid=999)
    assert (row, protocol) == before


def test_each_virtual_mode_has_own_threshold_and_cannot_use_a_phase_alias(protocol, row):
    row["free_mib"] = 24 * 1024
    assert subject.eligible_gpu(
        row, protocol, "virtual_point", {"feedback": {"mode": "sealed_existing"}}
    )
    assert not subject.eligible_gpu(
        row, protocol, "virtual_point", {"feedback": {"mode": "first_sampling"}}
    )
    with pytest.raises(subject.MemoryPolicyError, match="unregistered"):
        subject.phase_key("virtual_existing", {"feedback": {"mode": "first_sampling"}})


@pytest.mark.parametrize("stage", ["", "shard04", "replay_R2", "class", "unknown", None, []])
def test_unknown_stages_have_no_default(stage):
    with pytest.raises(subject.MemoryPolicyError, match="unregistered"):
        subject.minimum_free_mib(stage, {})


@pytest.mark.parametrize(
    "context",
    [
        None,
        {},
        {"feedback": None},
        {"feedback": {}},
        {"feedback": {"mode": "existing"}},
        {"feedback": {"mode": "unknown"}},
        {"feedback": {"mode": []}},
    ],
)
def test_unknown_or_missing_virtual_mode_is_rejected(context):
    with pytest.raises(subject.MemoryPolicyError, match="requires"):
        subject.minimum_free_mib("virtual_point", context)


@pytest.mark.parametrize(
    "processes",
    [
        None,
        {},
        "",
        [{"used_memory_mib": "1"}],
        [{"pid": "42"}],
        [{"pid": True}],
        [{"pid": 0}],
        [{"pid": -2}],
        [{"pid": 42}, {"pid": 42}],
        [{"pid": 42, "gpu_uuid": "GPU-other"}],
    ],
)
def test_incomplete_or_invalid_process_observation_fails_closed(protocol, row, processes):
    row["processes"] = processes
    assert not subject.eligible_gpu(row, protocol, "distribution", {})


def test_missing_process_list_is_not_an_idle_observation(protocol, row):
    del row["processes"]
    assert not subject.eligible_gpu(row, protocol, "distribution", {})


def test_own_worker_pid_is_rejected_even_with_ample_memory(protocol, row):
    row["processes"] = [{"pid": 999}]
    assert not subject.eligible_gpu(row, protocol, "distribution", {}, worker_pid=999)


@pytest.mark.parametrize("worker_pid", [0, -1, True, "999"])
def test_invalid_explicit_worker_pid_is_not_silently_ignored(protocol, row, worker_pid):
    with pytest.raises(subject.MemoryPolicyError, match="worker_pid"):
        subject.eligible_gpu(row, protocol, "distribution", {}, worker_pid=worker_pid)


@pytest.mark.parametrize(
    "free_mib", [None, "73728", True, -1, float("nan"), float("inf"), -float("inf")]
)
def test_unknown_nonfinite_or_negative_free_memory_is_rejected(protocol, row, free_mib):
    row["free_mib"] = free_mib
    assert not subject.eligible_gpu(row, protocol, "distribution", {})


@pytest.mark.parametrize(
    "changes",
    [{"uuid": "GPU-another"}, {"index": 3}, {"index": 8}, {"index": True}, {"index": "4"}],
)
def test_wrong_uuid_or_unregistered_physical_device_rejected(protocol, row, changes):
    row.update(changes)
    assert not subject.eligible_gpu(row, protocol, "distribution", {})


@pytest.mark.parametrize(
    "bad_protocol",
    [
        {},
        {"allowed_gpu_indices": [4], "gpu_uuids": {}},
        {"allowed_gpu_indices": [4, 4], "gpu_uuids": {"4": "GPU-test-4"}},
        {"allowed_gpu_indices": [4, 9], "gpu_uuids": {"4": "GPU-test-4", "9": "GPU-test-9"}},
    ],
)
def test_invalid_scope_rejected(row, bad_protocol):
    assert not subject.eligible_gpu(row, bad_protocol, "distribution", {})
    with pytest.raises(subject.MemoryPolicyError, match="scope"):
        subject.policy_record(scope=bad_protocol, evidence_refs=[{"path": "evidence"}])


def test_policy_record_keeps_runtime_limits_separate_and_copies_references(protocol):
    refs = [{"path": "read-only/result/record.json", "sha256": "test-resource-reference"}]
    record = subject.policy_record(scope=protocol, evidence_refs=refs)
    assert record["minimum_free_gib_by_phase"] == dict(subject.PHASE_MINIMUM_FREE_GIB)
    assert record["admission"]["external_compute_process_presence_is_not_a_veto"] is True
    assert record["admission"]["automatic_retry"] is False
    assert record["admission"]["maximum_total_workers_including_initializing_and_draining"] == 4
    assert record["admission"]["maximum_project_workers_per_gpu"] == 1
    assert record["unchanged_runtime"]["maximum_historical_allocated_bytes"] == 76 * 1024**3
    assert record["unchanged_runtime"]["minimum_boundary_free_bytes"] == 2 * 1024**3
    assert record["unchanged_runtime"]["R3_nonKV_activation_residency_bytes"] == 16 * 1024**3
    assert record["unchanged_runtime"]["mathematics_changed"] is False
    assert record["evidence_interpretation"]["historical_observations_are_not_upper_bounds"] is True
    protocol["allowed_gpu_indices"].append(6)
    refs[0]["path"] = "changed"
    assert record["scope"]["allowed_gpu_indices"] == [0, 4, 7]
    assert record["evidence_refs"][0]["path"] == "read-only/result/record.json"


@pytest.mark.parametrize("refs", [[], None, "path", ["path"]])
def test_missing_or_unstructured_evidence_rejected(protocol, refs):
    with pytest.raises(subject.MemoryPolicyError, match="evidence"):
        subject.policy_record(scope=protocol, evidence_refs=refs)
