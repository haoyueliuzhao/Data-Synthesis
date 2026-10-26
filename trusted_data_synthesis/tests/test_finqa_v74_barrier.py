"""CPU-only complete worker exit barrier accepts exactly the fixed192 panel."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import finqa_v74_binding as b
import finqa_v74_entry as entry


def barrier_fixture(tmp_path, monkeypatch, *, mutation=None):
    monkeypatch.setattr(b, "ROOT", tmp_path)
    job = dict(job_id="P.continuation", model="P", kind="generate", stage="generate",
        memory_phase="generate", condition_ids=[f"condition-{i:03d}" for i in range(192)])
    protocol = dict(id="protocol", jobs={job["job_id"]: job}, gpu_uuids={"6": "original-gpu-uuid"})
    stable = tmp_path / "jobs/P.continuation"
    attempt = stable / "attempts/attempt0001"
    identity = dict(pid=12345, birth="98765", gpu_index=6)
    b.publish(attempt / "launch/record.json", dict(protocol_id="protocol", job=job,
        attempt=1, gpu_uuid="original-gpu-uuid", **identity))
    b.publish(attempt / "actual_exit/record.json", dict(protocol_id="protocol", job_id=job["job_id"],
        attempt=1, returncode=0, actual_waitpid_observed=True, **identity))
    # The acceptance layer binds the complete roster. Opening each terminal
    # record belongs to the scoring layer and is deliberately not duplicated.
    outcomes = {key: dict(path=str(stable / "outputs" / key / "result.json"), sha256=key)
                for key in job["condition_ids"]}
    result = dict(status="COMPLETE", protocol_id="protocol", job=job, job_id=job["job_id"],
        pid=identity["pid"], gpu_index=6, resources=dict(all_gates_passed=True),
        model_released=True, terminal_conditions=192, outcomes=outcomes,
        output_refs=list(outcomes.values()), optimizer_updates=0, new_first_responses=0,
        native_scores=0, external_API_calls=0)
    if mutation == "premature_native_scores":
        result["native_scores"] = 1
    elif mutation == "missing_terminal":
        result["outcomes"].pop(job["condition_ids"][-1])
    elif mutation == "unreleased_model":
        result["model_released"] = False
    completed_result = b.publish(stable / "result/record.json", result)
    result_ref = b.entry(stable / "result/record.json")
    b.publish(attempt / "completed/record.json", dict(protocol_id="protocol", result=result_ref))
    exit_ref = b.entry(attempt / "actual_exit/record.json")
    b.publish(stable / "accepted/record.json", dict(protocol_id="protocol", job_id=job["job_id"],
        actual_exit_zero=True, resources_passed=True, attempt=1, actual_exit=exit_ref,
        result=result_ref, result_id=completed_result["id"]))
    b.publish(tmp_path / "all_jobs_exit_barrier/record.json", dict(protocol_id="protocol", active_workers=[],
        accepted_jobs={job["job_id"]: b.entry(stable / "accepted/record.json")},
        actual_exits={job["job_id"]: exit_ref}))
    return protocol


def test_full192_terminal_worker_and_actual_exit_are_accepted(tmp_path, monkeypatch):
    protocol = barrier_fixture(tmp_path, monkeypatch)
    barrier, accepted = entry.accepted_analysis_jobs(protocol)
    assert barrier == b.entry(tmp_path / "all_jobs_exit_barrier/record.json")
    assert set(accepted) == {"P.continuation"}
    result = accepted["P.continuation"]["result"]
    assert result["terminal_conditions"] == len(result["outcomes"]) == len(result["output_refs"]) == 192
    assert result["native_scores"] == 0


@pytest.mark.parametrize("mutation", ["premature_native_scores", "missing_terminal", "unreleased_model"])
def test_saved_exit_zero_cannot_override_invalid_scoring_gate(tmp_path, monkeypatch, mutation):
    protocol = barrier_fixture(tmp_path, monkeypatch, mutation=mutation)
    with pytest.raises(ValueError, match="complete inference-only result"):
        entry.accepted_analysis_jobs(protocol)
