"""CPU-only final-analysis admission: six real-exit identities, no bare bypass."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import finqa_v73_binding as b
import finqa_v73_entry as entry


def six_accepted(tmp_path, monkeypatch, mutation=None):
    monkeypatch.setattr(b, "ROOT", tmp_path)
    jobs = {f"{model}.shard{shard}": dict(job_id=f"{model}.shard{shard}", model=model,
        context_ids=[f"{model}{shard}ctx"], target_keys=[f"{model}{shard}task"])
        for model in "PHL" for shard in range(2)}
    protocol = dict(id="protocol", jobs=jobs, gpu_uuids={"6": "GPU-fixture"})
    accepted_refs, exit_refs = {}, {}
    for index, (key, job) in enumerate(jobs.items()):
        first = index == 0
        stable = tmp_path / "jobs" / key
        attempt = stable / "attempts/attempt0001"
        pid, birth = 100 + index, str(500 + index)
        if mutation == "same_identity_twice" and index == 1:
            pid, birth = 100, "500"
        launch = dict(protocol_id="protocol", job=job, attempt=1, pid=pid, birth=birth,
                      gpu_index=6, gpu_uuid="GPU-fixture")
        if first and mutation == "wrong_launch_birth":
            launch["birth"] = "other-birth"
        b.publish(attempt / "launch/record.json", launch)
        actual = dict(protocol_id="protocol", job_id=key, attempt=1, pid=pid, birth=birth,
                      gpu_index=6, returncode=0, actual_waitpid_observed=True)
        if first and mutation == "wrong_actual_job":
            actual["job_id"] = "L.shard1"
        if first and mutation == "wrong_actual_attempt":
            actual["attempt"] = 2
        if first and mutation == "nonzero_exit":
            actual["returncode"] = 1
        if first and mutation == "no_waitpid":
            actual["actual_waitpid_observed"] = False
        b.publish(attempt / "actual_exit/record.json", actual)
        result = dict(protocol_id="protocol", job_id=key, job=job, pid=pid, gpu_index=6,
            status="COMPLETE", resources=dict(all_gates_passed=True), model_released=True,
            generation_results=1, probability_results=1, output_refs=[{}, {}],
            optimizer_updates=0, tools_executed=0, native_scores=0, external_API_calls=0)
        if first and mutation == "foreign_result_protocol":
            result["protocol_id"] = "foreign"
        if first and mutation == "failed_resources":
            result["resources"]["all_gates_passed"] = False
        if first and mutation == "new_tool_execution":
            result["tools_executed"] = 1
        sealed = b.publish(stable / "result/record.json", result)
        result_ref = b.entry(stable / "result/record.json")
        b.publish(attempt / "completed/record.json", dict(protocol_id="protocol", result=result_ref))
        accepted = dict(protocol_id="protocol", job_id=key, attempt=1, result=result_ref,
            result_id=sealed["id"], actual_exit=b.entry(attempt / "actual_exit/record.json"),
            actual_exit_zero=True, resources_passed=True)
        if first and mutation == "foreign_accepted_protocol":
            accepted["protocol_id"] = "foreign"
        b.publish(stable / "accepted/record.json", accepted)
        accepted_refs[key] = b.entry(stable / "accepted/record.json")
        exit_refs[key] = accepted["actual_exit"]
    if mutation == "barrier_cross_job_reference":
        accepted_refs["P.shard0"] = accepted_refs["P.shard1"]
    barrier = dict(protocol_id="protocol", active_workers=[], accepted_jobs=accepted_refs, actual_exits=exit_refs)
    if mutation == "active_worker":
        barrier["active_workers"] = ["P.shard0"]
    if mutation == "five_exits":
        del barrier["actual_exits"]["L.shard1"]
    b.publish(tmp_path / "all_jobs_exit_barrier/record.json", barrier)
    return protocol


def test_six_bound_real_exits_are_admitted(tmp_path, monkeypatch):
    protocol = six_accepted(tmp_path, monkeypatch)
    barrier, accepted = entry.accepted_analysis_jobs(protocol)
    assert barrier == b.entry(tmp_path / "all_jobs_exit_barrier/record.json")
    assert set(accepted) == set(protocol["jobs"])
    assert len({(r["actual_exit"]["pid"], r["actual_exit"]["birth"]) for r in accepted.values()}) == 6


@pytest.mark.parametrize("mutation", ["wrong_launch_birth", "wrong_actual_job", "wrong_actual_attempt",
    "nonzero_exit", "no_waitpid", "foreign_result_protocol", "failed_resources", "new_tool_execution",
    "foreign_accepted_protocol", "barrier_cross_job_reference", "active_worker", "five_exits",
    "same_identity_twice"])
def test_identity_source_and_six_exit_barrier_cannot_be_bypassed(tmp_path, monkeypatch, mutation):
    protocol = six_accepted(tmp_path, monkeypatch, mutation)
    with pytest.raises(ValueError):
        entry.accepted_analysis_jobs(protocol)


def test_stale_barrier_reference_is_rejected_before_summary(tmp_path, monkeypatch):
    protocol = six_accepted(tmp_path, monkeypatch)
    path = tmp_path / "jobs/P.shard0/accepted/record.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="bytes changed"):
        entry.accepted_analysis_jobs(protocol)


def test_direct_CPU_entry_without_controller_barrier_cannot_analyze(tmp_path, monkeypatch):
    protocol = six_accepted(tmp_path, monkeypatch)
    (tmp_path / "all_jobs_exit_barrier/record.json").unlink()
    monkeypatch.setitem(sys.modules, "finqa_v73_registration", SimpleNamespace(checked_protocol=lambda: protocol))
    monkeypatch.setitem(sys.modules, "finqa_v73_resources", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "finqa_v73_controller", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "finqa_v73_analysis", SimpleNamespace(
        summarize=lambda *_: pytest.fail("summary must not run without six actual accepted exits")))
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    with pytest.raises(FileNotFoundError):
        entry.analyze(tmp_path / "final_analysis/attempt0001")
    assert not (tmp_path / "final_summary").exists()
