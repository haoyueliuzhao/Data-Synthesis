"""Synthetic sealed metadata only: report gates never invoke live analysis."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import finqa_v73_analysis as analysis
import finqa_v73_report as report


def save(path, body):
    body = {key: value for key, value in body.items() if key != "id"}
    body["id"] = report.digest(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(body, sort_keys=True).encode()
    path.write_bytes(raw)
    return dict(path=str(path), id=body["id"], sha256=report.hashlib.sha256(raw).hexdigest())


def fixture(root):
    spec = importlib.util.spec_from_file_location("v73_report_synthetic_fixture", Path(__file__).with_name("test_finqa_v73_analysis.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    _, inputs, generation, probability = module.fixture()
    selection = save(root / "selection/record.json", dict(candidate_counts={"F": 125, "K": 380},
        source_distributions={group: dict(selected={"cluster": 48}) for group in ("F", "K")}))
    legacy = save(root / "legacy/record.json", dict(status="STOPPED_FAILURE_NO_RETRY"))
    audit = save(root / "legacy_audit/record.json", dict(status="PASS", new_model_calls=0))
    preparation = save(root / "preparation/record.json", dict(status="PREPARATION_REJECTED"))
    jobs = {name: dict(job_id=name, model=name[0], context_ids=[name], target_keys=[name]) for name in report.JOBS}
    protocol_ref = save(root / "protocol/record.json", dict(jobs=jobs, source_commit="test-source", implementation={"id": "test-implementation"},
        scientific_contract={}, model_bindings={}, measurement_policy={}, resource_policy={},
        selection=selection, prior_execution_failure=legacy, prior_cold_entry_audit=audit, rejected_preparation=preparation))
    protocol = json.loads(Path(protocol_ref["path"]).read_text())
    for index, name in enumerate(sorted(report.JOBS)):
        directory = root / "jobs" / name
        resource = dict(all_gates_passed=True, peak_allocated_bytes=1024**3, peak_rss_bytes=1024**3,
            minimum_boundary_free_bytes=3*1024**3, minimum_host_available_bytes=100*1024**3)
        result = save(directory / "result/record.json", dict(status="COMPLETE", protocol_id=protocol["id"], job=jobs[name], job_id=name,
            pid=100+index, gpu_index=index, model_released=True, started_epoch=100, finished_epoch=200,
            generation_results=1, probability_results=1, optimizer_updates=0, tools_executed=0,
            native_scores=0, external_API_calls=0, resources=resource, output_refs=[]))
        actual = save(directory / "attempts/attempt0001/actual_exit/record.json", dict(protocol_id=protocol["id"], job_id=name,
            pid=100+index, birth=str(1000+index), gpu_index=index, attempt=1,
            returncode=0, actual_waitpid_observed=True, observed_epoch=201))
        save(directory / "attempts/attempt0001/launch/record.json", dict(protocol_id=protocol["id"], job=jobs[name],
            pid=100+index, birth=str(1000+index), gpu_index=index, gpu_uuid=f"gpu{index}", attempt=1, started_epoch=99))
        save(directory / "accepted/record.json", dict(protocol_id=protocol["id"], job_id=name, attempt=1,
            result=result, result_id=result["id"], actual_exit=actual, actual_exit_zero=True, resources_passed=True))
    summary = analysis.summarize(protocol, inputs, generation, probability)
    summary.update(physical_generation_results=6, physical_probability_results=6, actual_costs={"actual_model_generate_calls": 6})
    final_ref = save(root / "final_summary/record.json", summary)
    cpu = root / "final_analysis/attempt0001"
    cpu_resource = save(cpu / "resources/closeout/record.json", dict(status="COMPLETE", protocol_id=protocol["id"], pid=900, birth="9000",
        all_gates_passed=True, CUDA_initialized=False, peak_rss_bytes=1024**3, started_epoch=202, finished_epoch=203))
    cpu_exit = save(cpu / "actual_exit/record.json", dict(protocol_id=protocol["id"], pid=900, birth="9000", returncode=0, actual_waitpid_observed=True))
    cpu_result = save(cpu / "result/record.json", dict(status="COMPLETE", protocol_id=protocol["id"], pid=900, analysis=final_ref))
    save(root / "final_analysis/accepted/record.json", dict(protocol_id=protocol["id"], result=cpu_result, resources=cpu_resource,
        actual_exit=cpu_exit, analysis=final_ref))
    controller = save(root / "supervisor/attempts/attempt0001/actual_exit/record.json", dict(returncode=0, actual_waitpid_observed=True))
    save(root / "supervisor/closeout/record.json", dict(status="COMPLETE", protocol_id=protocol["id"], automatic_restart_stopped=True,
        actual_controller_exit=controller))
    save(root / "closeout/record.json", dict(status="COMPLETE", active_workers=0, accepted_jobs=sorted(jobs), protocol_id=protocol["id"],
        analysis=final_ref, generation_calls=6, probability_sequences=6, finished_epoch=204, resource_wait_seconds=0))


def test_live_or_failed_run_is_rejected_before_any_summary_read(tmp_path):
    save(tmp_path / "closeout/record.json", dict(status="RUNNING", active_workers=6, accepted_jobs=[]))
    reader = report.Reader()
    with pytest.raises(ValueError, match="has not completed"):
        report.extract(tmp_path, reader=reader)
    assert len(reader.sources) == 1


def test_complete_run_reads_each_metadata_once_and_renders_NA_and_no_accuracy_claim(tmp_path):
    fixture(tmp_path)
    reader = report.Reader()
    data = report.extract(tmp_path, reader=reader)
    assert data["execution"]["peak_dispatched_worker_concurrency"] == 6
    assert data["report_read_policy"]["source_JSON_count"] == len(reader.sources)
    assert len(reader.sources) == len(reader.cache)
    assert not any("/outputs/" in path or "/episodes/" in path for path in reader.sources)
    text = report.render_report(data)
    assert "NA" in text and "二者都不是答案正确率" in text
    assert "48道残余失效题F" in text and "固定父回应" in text
    assert "旧execution_revision_01终态为`STOPPED_FAILURE_NO_RETRY`" in text
    assert "没有监督器自身父进程waitpid码" in text


@pytest.mark.parametrize("kind", ["GPU_nonzero", "CPU_unobserved", "CPU_wrong_identity"])
def test_actual_exit_gate_cannot_be_replaced_by_a_complete_boolean(tmp_path, kind):
    fixture(tmp_path)
    if kind == "GPU_nonzero":
        accepted_path = tmp_path / "jobs/P.shard0/accepted/record.json"
    else:
        accepted_path = tmp_path / "final_analysis/accepted/record.json"
    accepted = json.loads(accepted_path.read_text())
    actual_path = Path(accepted["actual_exit"]["path"])
    actual = json.loads(actual_path.read_text())
    if kind == "GPU_nonzero": actual["returncode"] = 1
    elif kind == "CPU_unobserved": actual["actual_waitpid_observed"] = False
    else: actual["pid"] = 999
    accepted["actual_exit"] = save(actual_path, actual)
    save(accepted_path, accepted)
    reader = report.Reader()
    with pytest.raises(ValueError):
        report.extract(tmp_path, reader=reader)
    assert str((tmp_path / "final_summary/record.json").resolve()) not in reader.sources


def test_reader_refuses_raw_payload_and_detects_changed_byte_binding(tmp_path):
    reader = report.Reader()
    with pytest.raises(ValueError, match="never a raw"):
        reader.read(tmp_path / "episodes/episode.json")
    ref = save(tmp_path / "summary/record.json", dict(value=1))
    changed = save(Path(ref["path"]), dict(value=2))
    assert ref["sha256"] != changed["sha256"]
    with pytest.raises(ValueError, match="source reference changed"):
        reader.read(ref)
