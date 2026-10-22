"""CPU-only registration invariants: 20 read-only adoptions plus four new jobs."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import finqa_v67_binding as binding
import finqa_v67_evaluation as evaluation
import finqa_v67_registration as registration


def rewrite(path, body):
    body = {key: value for key, value in body.items() if key != "id"}
    value = dict(**body, id=binding.digest(body))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


@pytest.fixture
def registered(tmp_path, monkeypatch):
    root, science, peer = (tmp_path / key for key in ("completion", "science", "early"))
    monkeypatch.setattr(binding, "ROOT", root)
    monkeypatch.setattr(binding, "SCIENTIFIC_ROOT", science)
    monkeypatch.setattr(registration, "ROOT", root)
    monkeypatch.setattr(registration, "_VERIFIED_PROTOCOL", None)
    monkeypatch.setattr(registration, "_VERIFIED_IMPLEMENTATION", None)
    original_checked_protocol = registration.checked_protocol
    monkeypatch.setattr(registration, "checked_protocol", lambda requested=None:
                        original_checked_protocol(root if requested is None else requested))
    base = rewrite(science / "protocol/record.json", dict(
        gpu_lease_root=str(tmp_path / "legacy-exclusive-leases"),
        gpu_uuids={str(n): f"GPU-frozen-{n}" for n in range(8)},
        cpu_affinity={str(n): "0-1" for n in range(8)}, gpu_isolation_policy={"unchanged": True},
        signal_policy={"legal_stop": "unchanged"}, signal_source_bindings={"frozen": "hash"},
        auto_recovery_policy={"UNKNOWN": "block"}, allowed_gpu_indices=list(range(8))))
    old = rewrite(peer / "protocol/record.json", dict(legacy_max_per_gpu=1))
    monkeypatch.setattr(binding, "BASE_PROTOCOL_ID", base["id"])
    monkeypatch.setattr(binding, "EARLY_PROTOCOL_ID", old["id"])
    monkeypatch.setattr(binding, "base_protocol", lambda: base)
    slots = dict(second_slot_lease_root=str(tmp_path / "global-secondary-leases"),
        legacy_gpu_lease_root=base["gpu_lease_root"], max_total_project_workers_per_gpu=2,
        max_new_workers_per_gpu=1, max_legacy_workers_per_gpu=1,
        primary_exit_never_creates_a_second_secondary_slot=True,
        both_lanes_require_exclusive_flock=True)
    monkeypatch.setattr(binding, "gpu_slot_policy", lambda: deepcopy(slots))
    runtime = SimpleNamespace(resource_policy=lambda: {"allocated_gib": 76, "boundary_free_gib": 2,
        "host_reserve_gib": 96}, resource_recovery_policy=lambda: {"UNKNOWN": "block"},
        memory_protection_policy=lambda: {"max_warm_gib": 16})
    monkeypatch.setitem(sys.modules, "finqa_v67_runtime", runtime)
    implementation = rewrite(root / "implementation/record.json", dict(committed_files=list(registration.FILES)))
    monkeypatch.setattr(registration, "checked_implementation", lambda *args, **kwargs: implementation)
    original_jobs = evaluation.original.planned_jobs()
    newjobs = evaluation.planned_jobs()
    oldjobs = {key: value for key, value in original_jobs.items() if key not in newjobs}
    old_plan = rewrite(peer / "evaluations/registration/record.json", dict(jobs=oldjobs))
    inherited = rewrite(root / "inherited_peer_journal/record.json", dict(
        protocol_id=old["id"], immutable_snapshot=True, resource_wait_seconds=17.0))
    protocol = rewrite(root / "protocol/record.json", dict(schema=registration.SCHEMA,
        control_root=str(root), scientific_root=str(science), scientific_protocol_id=base["id"],
        max_gpu_workers=3, max_workers_per_gpu=2, own_max_workers_per_gpu=1,
        global_total_limit=6, reserved_cross_control_startup_gib=208,
        reserved_peer_gpu_workers=3, reserved_peer_worker_startup_gib=48,
        cpu_seal_rss_limit_gib=64, max_cpu_sealing_workers=1, gpu_priority=list(binding.GPU_PRIORITY),
        gpu_lease_root=slots["second_slot_lease_root"], legacy_gpu_lease_root=base["gpu_lease_root"],
        gpu_slot_policy=slots, resource_policy=runtime.resource_policy(),
        resource_recovery_policy=runtime.resource_recovery_policy(),
        memory_protection_policy=runtime.memory_protection_policy(), evaluation=evaluation.evaluation_contract(),
        implementation=binding.entry(root / "implementation/record.json"), scoring_calls_authorized=0,
        new_training_or_feedback_calls_authorized=0,
        science_protocol_ref=binding.entry(science / "protocol/record.json"),
        peer_source_protocol=binding.entry(peer / "protocol/record.json"),
        peer_source_plan=binding.entry(peer / "evaluations/registration/record.json"),
        eligible_training_branches={"seed389/C05": {"unchanged_final_branch": True}},
        peer_job_roster=oldjobs, peer_residual_roster=list(binding.RESIDUAL_PEER_JOBS),
        peer_protocol_id=old["id"], inherited_journal=binding.entry(root / "inherited_peer_journal/record.json"),
        **{key: base[key] for key in ('gpu_uuids', 'cpu_affinity', 'gpu_isolation_policy', 'signal_policy',
                'signal_source_bindings', 'auto_recovery_policy', 'allowed_gpu_indices')}))
    new_plan = rewrite(root / "evaluations/registration/record.json", dict(
        protocol_id=protocol["id"], scientific_protocol_id=base["id"], jobs=newjobs,
        scoring_calls=0, private_references_read=False))
    prepared = rewrite(root / "prepared/record.json", dict(schema=registration.PREPARED_SCHEMA,
        protocol_id=protocol["id"], scientific_protocol_id=base["id"], generation_jobs=4, sessions=1243,
        adopted_jobs=20, adopted_sessions=6215, peer_protocol_id=old["id"],
        peer_residual_roster=list(binding.RESIDUAL_PEER_JOBS), private_references_read=False, scoring_calls=0,
        peer_job_roster=oldjobs, inherited_journal=protocol["inherited_journal"],
        generation_plan=binding.entry(root / "evaluations/registration/record.json")))
    return SimpleNamespace(root=root, protocol=protocol, prepared=prepared, newjobs=newjobs,
        oldjobs=oldjobs, original_jobs=original_jobs, slots=slots, new_plan=new_plan,
        old_plan=old_plan, inherited=inherited)


def test_registered_four_plus_twenty_is_exact_original_dose_without_regeneration(registered):
    e = registered
    assert registration.checked_protocol(e.root) == e.protocol
    assert registration.checked_prepared(e.root) == e.prepared
    assert set(e.newjobs).isdisjoint(e.oldjobs)
    assert {**e.oldjobs, **e.newjobs} == e.original_jobs
    assert len(e.newjobs) == 4 and len(e.oldjobs) == 20
    assert sum(row["denominator"] for row in e.newjobs.values()) == 1243
    assert sum(row["denominator"] for row in e.oldjobs.values()) == 6215
    contract = e.protocol["evaluation"]
    assert contract["complete_provider_returns_and_episodes_never_regenerated"]
    assert contract["original_scientific_budget_unchanged"]
    assert contract["original_generation_jobs"] == 24 and contract["original_total_sessions"] == 7458
    assert contract["scoring_calls"] == 0 and contract["private_scoring_authorized"] is False
    assert e.protocol["reserved_cross_control_startup_gib"] == 3 * 48 + 64
    assert e.protocol["max_gpu_workers"] + e.protocol["reserved_peer_gpu_workers"] == 6
    assert e.protocol["own_max_workers_per_gpu"] == 1
    assert e.slots["max_legacy_workers_per_gpu"] + e.slots["max_new_workers_per_gpu"] == 2


@pytest.mark.parametrize("field,value", [
    ("max_gpu_workers", 4), ("max_workers_per_gpu", 3), ("own_max_workers_per_gpu", 2),
    ("global_total_limit", 7), ("reserved_cross_control_startup_gib", 207),
    ("reserved_peer_gpu_workers", 2), ("reserved_peer_worker_startup_gib", 47),
    ("cpu_seal_rss_limit_gib", 192), ("max_cpu_sealing_workers", 2),
    ("gpu_priority", [0, 6, 7]), ("gpu_lease_root", "/other-secondary-root"),
    ("legacy_gpu_lease_root", "/different-legacy-root"),
    ("gpu_slot_policy", {"changed": True}), ("resource_policy", {"allocated_gib": 80}),
    ("resource_recovery_policy", {"UNKNOWN": "retry"}), ("memory_protection_policy", {"max_warm_gib": 32}),
    ("scoring_calls_authorized", 1), ("new_training_or_feedback_calls_authorized", 1),
    ("eligible_training_branches", {"seed137/C05": {}}),
    ("allowed_gpu_indices", [0, 6, 7]), ("signal_policy", {"legal_stop": "ignore"}),
    ("gpu_isolation_policy", {"unchanged": False}), ("auto_recovery_policy", {"UNKNOWN": "retry"}),
])
def test_protocol_rejects_policy_or_dose_partition_drift(registered, field, value):
    e = registered
    changed = deepcopy(e.protocol)
    changed[field] = value
    rewrite(e.root / "protocol/record.json", changed)
    with pytest.raises(ValueError):
        registration.checked_protocol(e.root)


@pytest.mark.parametrize("field,value", [
    ("generation_jobs", 5), ("sessions", 1244), ("adopted_jobs", 19), ("adopted_sessions", 6214),
    ("scoring_calls", 1), ("private_references_read", True),
    ("peer_residual_roster", []), ("peer_job_roster", {}),
])
def test_prepared_rejects_reduced_adoption_or_extra_generation(registered, field, value):
    e = registered
    changed = deepcopy(e.prepared)
    changed[field] = value
    rewrite(e.root / "prepared/record.json", changed)
    with pytest.raises(ValueError):
        registration.checked_prepared(e.root)


def test_evaluation_contract_cannot_enable_regeneration(registered):
    e = registered
    changed = deepcopy(e.protocol)
    changed["evaluation"]["complete_provider_returns_and_episodes_never_regenerated"] = False
    rewrite(e.root / "protocol/record.json", changed)
    with pytest.raises(ValueError):
        registration.checked_protocol(e.root)


def test_reference_bytes_are_bound_not_just_completion_booleans(registered):
    e = registered
    source = Path(e.protocol["peer_source_plan"]["path"])
    changed = deepcopy(e.old_plan)
    changed["jobs"].pop(next(iter(changed["jobs"])))
    rewrite(source, changed)
    with pytest.raises(ValueError, match="bytes changed"):
        registration.checked_prepared(e.root)


def test_foreign_registration_roots_are_rejected(registered):
    e = registered
    with pytest.raises(ValueError, match="foreign"):
        registration.checked_protocol(e.root.parent / "different")
    with pytest.raises(ValueError, match="foreign"):
        registration.checked_prepared(e.root.parent / "different")
