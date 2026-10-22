"""Focused CPU tests for the exact one-time GPU0-to-GPU6 migration scope."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v69_binding as b
import finqa_v69_registration as registration


def rewrite(path, body):
    body = {key: value for key, value in body.items() if key != "id"}
    value = dict(**body, id=b.digest(body))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


@pytest.fixture
def registered(tmp_path, monkeypatch):
    root, source = tmp_path / "migration", tmp_path / "completion"
    monkeypatch.setattr(b, "ROOT", root)
    monkeypatch.setattr(b, "COMPLETION_ROOT", source)
    monkeypatch.setattr(registration, "ROOT", root)
    monkeypatch.setattr(registration, "_VERIFIED_PROTOCOL", None)
    monkeypatch.setattr(registration, "_VERIFIED_IMPLEMENTATION", None)
    operational = dict(gpu_lease_root=str(tmp_path / "global-secondary"),
        gpu_slot_policy=dict(own_max_workers_per_gpu=1, max_total_project_workers_per_gpu=2),
        gpu_uuids={"0":"GPU-fixed-source", "6":"GPU-fixed-destination"}, cpu_affinity={"6":"38-75,114-151"},
        resource_policy=dict(minimum_free_gib_by_kind=dict(generate=24), host_startup_gib_by_kind=dict(generate=48),
            allocated_lifetime_limit_bytes=76*1024**3, boundary_physical_free_reserve_bytes=2*1024**3,
            effective_host_available_reserve_bytes=96*1024**3),
        resource_recovery_policy=dict(stop_signal_blocks_automatic_restart=True),
        memory_protection_policy=dict(original_gates_unchanged=True),
        signal_policy=dict(owner_uid=1004, source_SIGTERM_cooperative=True),
        signal_source_bindings=dict(frozen="same-hash"), gpu_isolation_policy=dict(foreign_processes_untouched=True))
    original = rewrite(source / "protocol/record.json", dict(scientific_protocol_id=b.BASE_PROTOCOL_ID, **operational))
    monkeypatch.setattr(b,"COMPLETION_PROTOCOL_ID",original["id"])
    job = dict(job_id=b.TARGET_JOB_ID, seed=389, arm="C05", feedback_batch=1, step=894,
        stage="generate", config=dict(temperature=0.0, seed=20260928), denominator=883,
        checkpoint=dict(path="/fixed/model/state", state_sha256="a"*64), model_identity=dict(point_id="unchanged"))
    jobs = {b.TARGET_JOB_ID:job, b.DESTINATION_JOB_ID:dict(job_id=b.DESTINATION_JOB_ID),
            "fixed_calibration_greedy":dict(job_id="fixed_calibration_greedy"),
            "fixed_calibration_draw11":dict(job_id="fixed_calibration_draw11")}
    plan = rewrite(source / "evaluations/registration/record.json", dict(protocol_id=original["id"],
        scientific_protocol_id=b.BASE_PROTOCOL_ID, jobs=jobs))
    launch_path=b.source_attempt_directory() / "launch/record.json"
    launch=rewrite(launch_path,dict(protocol_id=original["id"],job=job,pid=b.TARGET_PID,
        birth=b.TARGET_BIRTH,gpu_index=0,attempt=1))
    controller_path=source / "controllers/attempt0001/launch/record.json"
    rewrite(controller_path,dict(protocol_id=original["id"],pid=b.CONTROLLER_PID,
        birth=b.CONTROLLER_BIRTH,controller_attempt=1))
    destination_path=source / "evaluations/jobs" / b.DESTINATION_JOB_ID / "attempts/attempt0001/launch/record.json"
    rewrite(destination_path,dict(protocol_id=original["id"],job=jobs[b.DESTINATION_JOB_ID],pid=b.DESTINATION_PID,
        birth=b.DESTINATION_BIRTH,gpu_index=6,attempt=1))
    implementation = rewrite(root / "implementation/record.json",dict(committed_files=list(registration.FILES)))
    monkeypatch.setattr(registration,"checked_implementation",lambda *args,**kwargs:implementation)
    refs=dict(source_protocol=b.entry(source / "protocol/record.json"),
        source_plan=b.entry(source / "evaluations/registration/record.json"),
        source_launch=b.entry(launch_path), source_controller_launch=b.entry(controller_path),
        destination_launch=b.entry(destination_path))
    protocol = rewrite(root / "protocol/record.json",dict(schema=registration.SCHEMA, control_root=str(root),
        source_root=str(source),scientific_protocol_id=b.BASE_PROTOCOL_ID,source_protocol_id=original["id"],
        target_job=job,target=dict(job_id=b.TARGET_JOB_ID,pid=b.TARGET_PID,birth=b.TARGET_BIRTH,gpu_index=0,attempt=1),
        source_controller=dict(pid=b.CONTROLLER_PID,birth=b.CONTROLLER_BIRTH,controller_attempt=1),
        destination=dict(gpu_index=6,uuid=original["gpu_uuids"]["6"],await_job_id=b.DESTINATION_JOB_ID,
            await_pid=b.DESTINATION_PID,await_birth=b.DESTINATION_BIRTH,await_attempt=1),
        migration=registration.migration_contract(),max_new_GPU_workers=1,startup_available_gib=512,
        stop_settle_seconds=600,implementation=b.entry(root / "implementation/record.json"),**refs,**operational))
    return SimpleNamespace(root=root,source=source,protocol=protocol,original=original,plan=plan,
        launch=launch,launch_path=launch_path,controller_path=controller_path,refs=refs)


def test_exact_registration_preserves_scope_and_operational_limits(registered):
    e=registered
    assert registration.checked_protocol(e.root)==e.protocol
    source,plan,refs=registration.original_evidence()
    assert source==e.original and plan==e.plan and refs==e.refs
    assert registration.FILES == tuple(f"finqa_v69_{name}.py" for name in ("binding","registration","worker_bridge","entry"))
    contract=e.protocol["migration"]
    assert (contract["source_GPU"],contract["destination_GPU"],contract["source_attempt"],contract["continuation_attempt"])==(0,6,1,2)
    assert contract["one_identity_bound_owner_SIGTERM_only"] and not contract["source_SIGKILL_allowed"]
    assert contract["UNKNOWN_calls_authorized"]==contract["settled_response_model_calls_repeated"]==0
    assert contract["source_HARD_state_preserved"] and not contract["old_failures_and_control_journals_rewritten"]
    assert not contract["new_sampling_or_scoring_authorized"] and not contract["automatic_retry"]
    assert contract["wait_for_all_twenty_CPU_repairs_not_required"]
    assert e.protocol["resource_policy"]["minimum_free_gib_by_kind"]["generate"]==24
    assert e.protocol["startup_available_gib"]==512


@pytest.mark.parametrize("field,value",[
    ("max_new_GPU_workers",2),("startup_available_gib",511),("stop_settle_seconds",601),
    ("target",dict(job_id=b.TARGET_JOB_ID,pid=b.TARGET_PID+1,birth=b.TARGET_BIRTH,gpu_index=0,attempt=1)),
    ("destination",dict(gpu_index=7)),
    ("resource_policy",dict(minimum_free_gib_by_kind=dict(generate=23))),
    ("gpu_lease_root","/replacement-secondary"),
])
def test_registration_rejects_target_destination_or_limit_drift(registered,field,value):
    e=registered
    changed=deepcopy(e.protocol);changed[field]=value
    rewrite(e.root / "protocol/record.json",changed)
    with pytest.raises(ValueError):registration.checked_protocol(e.root)


@pytest.mark.parametrize("field,value",[
    ("source_SIGKILL_allowed",True),("UNKNOWN_calls_authorized",1),
    ("new_sampling_or_scoring_authorized",True),("old_failures_and_control_journals_rewritten",True),
])
def test_migration_contract_cannot_turn_into_retry_or_scientific_expansion(registered,field,value):
    e=registered
    changed=deepcopy(e.protocol);changed["migration"][field]=value
    rewrite(e.root / "protocol/record.json",changed)
    with pytest.raises(ValueError):registration.checked_protocol(e.root)


@pytest.mark.parametrize("field",["source_launch","source_controller_launch"])
def test_same_bytes_under_another_path_do_not_replace_original_evidence(registered,field):
    e=registered
    changed=deepcopy(e.protocol)
    alternative=e.root / "wrong_identity" / field / "record.json"
    rewrite(alternative,b.read_ref(changed[field]))
    changed[field]=b.entry(alternative)
    rewrite(e.root / "protocol/record.json",changed)
    with pytest.raises(ValueError,match="escaped original identity"):
        registration.checked_protocol(e.root)


def test_original_evidence_rejects_changed_controller_identity(registered):
    e=registered
    value=b.checked(e.controller_path);value["birth"]="different"
    rewrite(e.controller_path,value)
    with pytest.raises(ValueError,match="controller or destination"):
        registration.original_evidence()


def test_original_evidence_rejects_existing_second_attempt(registered):
    b.destination_attempt_directory().mkdir(parents=True)
    with pytest.raises(ValueError,match="continuation attempt already exists"):
        registration.original_evidence()


@pytest.mark.parametrize("which",["old_failure","old_launch","old_journal","another_job","attempt3","source_result"])
def test_append_target_record_rejects_historical_or_unregistered_writes(registered,monkeypatch,which):
    e=registered
    targets=dict(old_failure=b.source_attempt_directory() / "failure/record.json",
        old_launch=b.source_attempt_directory() / "launch/record.json",
        old_journal=e.source / "journal/state.json",
        another_job=e.source / "evaluations/jobs/other-job/accepted/record.json",
        attempt3=b.target_directory() / "attempts/attempt0003/launch/record.json",
        source_result=b.target_directory() / "result/record.json")
    monkeypatch.setattr(b._original,"publish",lambda *_:pytest.fail("forbidden original write reached publisher"))
    with pytest.raises(ValueError,match="authorized new attempt2"):
        b.append_target_record(targets[which],dict(unrelated=True))


def test_append_allows_exact_new_record_once_but_never_reopens(registered,monkeypatch):
    monkeypatch.setattr(b._original,"publish",rewrite)
    path=b.destination_attempt_directory() / "launch/record.json"
    value=b.append_target_record(path,dict(job_id=b.TARGET_JOB_ID,attempt=2))
    assert b.checked(path)==value
    with pytest.raises(ValueError,match="authorized new attempt2"):
        b.append_target_record(path,dict(job_id=b.TARGET_JOB_ID,attempt=2))
