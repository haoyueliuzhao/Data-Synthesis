"""Five bounded workflow controls: fake processes/inventory, no API/CUDA/real wallets."""

import json
from pathlib import Path

import pytest

from trusted_synthesis.finance_research import v10_workflow as workflow
from trusted_synthesis.finance_research.storage import read_json


@pytest.fixture
def supervisor(tmp_path, monkeypatch):
    plan = dict(id="synthetic-plan", batch_id="synthetic-batch")
    monkeypatch.setattr(workflow, "checked_plan", lambda output: plan)
    return workflow.Supervisor(tmp_path / "batch", max_gpu_workers=2)


def artifact(path, **values):
    workflow.publish(Path(path).parent, workflow.bound(values), Path(path).name)


def test_generation_requires_both_complete_identical_seals_before_successor(
    supervisor, monkeypatch
):
    plan = {**supervisor.plan, "slots": [dict(slot_id=f"synthetic:{i}") for i in range(8000)]}
    assert not workflow.generation_ready(supervisor.output, plan)
    seal = workflow.bound(
        dict(protocol_id=plan["id"], denominator=8000, slots=[dict(slot=s) for s in plan["slots"]])
    )
    workflow.publish(supervisor.output / "generation_seal", seal)
    assert not workflow.generation_ready(supervisor.output, plan)
    native = dict(
        protocol_id=plan["id"],
        generation_seal_id=seal["id"],
        slot_denominator=8000,
        rows=[dict(slot=s) for s in plan["slots"]],
    )
    workflow.publish(supervisor.output / "native_support", workflow.bound(native))
    assert workflow.generation_ready(supervisor.output, plan)
    for name, rows in (
        ("prefix", native["rows"][:-1]),
        ("reordered", list(reversed(native["rows"]))),
    ):
        root = supervisor.output / name
        workflow.publish(root / "generation_seal", seal)
        workflow.publish(root / "native_support", workflow.bound({**native, "rows": rows}))
        with pytest.raises(ValueError, match="complete native"):
            workflow.generation_ready(root, plan)
    monkeypatch.setattr(supervisor, "await_generation", lambda: False)
    monkeypatch.setattr(
        supervisor, "plain_job", lambda *a: pytest.fail("incomplete generation launched successor")
    )
    assert supervisor.run() is None


def test_headroom_24GiB_occupied_exclusion_and_no_placeholder(supervisor, monkeypatch):
    inventory = [
        dict(index=0, free=24575),
        dict(index=1, free=24576),
        dict(index=2, free=40000),
        dict(index=3, free=60000),
    ]
    assert workflow.available_gpus(inventory, allowed=[0, 1, 2], occupied=[2]) == [1]
    monkeypatch.setattr(workflow, "gpu_inventory", lambda: [dict(index=0, free=24575)])
    monkeypatch.setattr(
        supervisor, "launch", lambda *a, **kw: pytest.fail("GPU placeholder allocated")
    )
    monkeypatch.setattr(workflow.time, "sleep", lambda seconds: setattr(supervisor, "stop", True))
    jobs = [
        dict(
            key="real-work-only",
            module="unused",
            args=[],
            result=supervisor.output / "missing.json",
        )
    ]
    assert supervisor.gpu_queue(jobs, [0]) is False
    assert not supervisor.children and not (supervisor.root / "jobs").exists()
    assert read_json(supervisor.root / "status.json")["no_GPU_placeholder"] is True


def test_child_command_and_active_status_are_json_serializable(supervisor, monkeypatch):
    class Process:
        pid = 234567890

        def poll(self):
            return None

    commands = []
    monkeypatch.setattr(
        workflow.subprocess, "Popen", lambda command, **kw: commands.append(command) or Process()
    )
    monkeypatch.setattr(workflow, "identity", lambda pid: "synthetic-birth")
    result = supervisor.output / "training/seed11/result/record.json"
    supervisor.launch(
        dict(
            key="train-seed11",
            module="v9_training_launcher",
            args=["run-seed", "--output", supervisor.output / "training", "--seed", 11],
            result=result,
        ),
        gpu=7,
    )
    supervisor.update("SYNTHETIC_CHILD_STATE")
    state = read_json(supervisor.root / "status.json")
    json.dumps(state, allow_nan=False)
    assert state["active_children"][0]["result"] == str(result)
    assert state["active_children"][0]["gpu"] == 7
    assert all(isinstance(v, str) for v in commands[0])
    assert commands[0][-2:] == ["--gpu", "7"]
    assert state["no_resampling"] and state["no_GPU_placeholder"]


def test_failed_gpu_job_retained_others_drain_no_new_job_or_gpu_reuse(supervisor, monkeypatch):
    jobs = [
        dict(
            key=f"job-{i}",
            module="mock-local-module",
            args=[f"job-{i}"],
            result=supervisor.output / f"result-{i}/record.json",
        )
        for i in range(3)
    ]
    by_key = {j["key"]: j for j in jobs}
    launched = []

    class Process:
        def __init__(self, key):
            self.key, self.pid, self.polls = key, 234567890 + len(launched), 0

        def poll(self):
            self.polls += 1
            if self.key == "job-0":
                return 17
            if self.polls == 1:
                return None
            artifact(by_key[self.key]["result"], synthetic_success=True)
            return 0

    def popen(command, **kwargs):
        launched.append(command)
        return Process(command[4])

    monkeypatch.setattr(workflow.subprocess, "Popen", popen)
    monkeypatch.setattr(workflow, "identity", lambda pid: "synthetic-birth")
    monkeypatch.setattr(
        workflow, "gpu_inventory", lambda: [dict(index=0, free=30000), dict(index=7, free=40000)]
    )
    monkeypatch.setattr(workflow.time, "sleep", lambda seconds: None)
    assert supervisor.gpu_queue(jobs, [0, 7]) is False
    assert len(launched) == 2 and {cmd[-1] for cmd in launched} == {"0", "7"}
    assert not (supervisor.root / "jobs/job-2").exists()
    failed = read_json(supervisor.root / "jobs/job-0/attempt001/exit/record.json")
    assert failed["exit_code"] == 17 and not failed["completed"]
    assert failed["failed_attempt_retained"] and not failed["retry_performed"]
    assert not supervisor.children and workflow.marker_complete(jobs[1]["result"])
    assert read_json(supervisor.root / "status.json")["phase"] == "BLOCKED_GPU_JOB_SAVED"


def test_workflow_15_dev883_paths_and_whole_mechanism_seals_before_scores(supervisor, monkeypatch):
    from trusted_synthesis.finance_research import v9_final_evaluation as final
    from trusted_synthesis.finance_research import v9_mechanism_execution as mechanisms
    from trusted_synthesis.finance_research import v10_training as training

    launcher = supervisor.output / "training/launcher"
    events, queues, scored = [], [], []
    final_jobs = {
        final.coordinate(seed, arm): dict(seed=seed, arm=arm)
        for seed in (11, 29, 47)
        for arm in final.ARMS
    }
    final_plan = dict(
        total_models=15, total_episodes=13245, tasks=[str(i) for i in range(883)], jobs=final_jobs
    )
    monkeypatch.setattr(supervisor, "await_generation", lambda: True)
    monkeypatch.setattr(workflow, "gpu_inventory", lambda: [dict(index=0, free=40000)])

    def plain(job, phase):
        assert job["module"] == "v10_production"
        assert job["result"] == supervisor.output / "material/result/record.json"
        artifact(job["result"], material_fixture=True)
        artifact(supervisor.output / "material/binding/record.json", material_fixture=True)
        return True

    def register_mechanisms(parent, output):
        assert parent == launcher
        events.append("mechanism_registered_before_Student")
        artifact(output / "registration/record.json", synthetic_registration=True)

    def register_final(parent, output):
        assert parent == launcher and events[-1] == "training_complete"
        artifact(output / "registration/record.json", synthetic_registration=True)

    def queue(jobs, allowed):
        queues.append(jobs)
        index = len(queues)
        if index == 1:
            assert len(jobs) == 3 and events == ["mechanism_registered_before_Student"]
            assert all(
                j["result"] == launcher / f"seed{seed}/result/record.json"
                for j, seed in zip(jobs, (11, 29, 47), strict=True)
            )
            events.append("training_complete")
        elif index == 2:
            assert len(jobs) == 15 and len(final_plan["tasks"]) == 883
            expected = {
                final.model_root(supervisor.output / "final_evaluation", item)
                / "scores/record.json"
                for item in final_jobs.values()
            }
            assert {j["result"] for j in jobs} == expected
            assert all(j["module"] == "v9_final_evaluation" for j in jobs)
        elif index == 3:
            assert len(jobs) == 3 and events[-1] == "all_15_final_scored"
            for seed in (11, 29, 47):
                root = supervisor.output / "mechanisms" / f"seed{seed}"
                artifact(
                    root / "C_direction/result/record.json",
                    directions={"Static": {}, "positive": {}, "reverse": {}},
                )
                artifact(
                    root / "N_same_point/result/record.json", conditions={"C-only": {}, "Full": {}}
                )
        else:
            assert index == 4 and len(jobs) == 15
            assert not scored
            for j in jobs:
                assert j["gpu_flag"] == "--gpu-index"
                assert (
                    j["result"]
                    == supervisor.output
                    / "mechanisms"
                    / f"seed{j['seed']}/evaluation"
                    / j["mechanism"]
                    / j["condition"]
                    / "whole_seal/record.json"
                )
        for j in jobs:
            artifact(
                j["result"],
                synthetic_only=True,
                denominator=883 if index == 2 else 360 if index == 4 else None,
            )
        return True

    def aggregate_final(output):
        assert len(queues) == 2
        assert all(workflow.marker_complete(j["result"]) for j in queues[1])
        events.append("all_15_final_scored")
        return dict(id="synthetic-final-summary")

    def score_point(output, seed, mechanism, condition):
        assert len(queues) == 4 and all(workflow.marker_complete(j["result"]) for j in queues[3])
        scored.append((seed, mechanism, condition))
        artifact(
            output / f"seed{seed}/evaluation" / mechanism / condition / "scores/record.json",
            synthetic_score_only=True,
        )

    def aggregate_mechanisms(output):
        assert len(scored) == 15 and 15 * 360 == 5400
        return dict(id="synthetic-mechanism-summary")

    monkeypatch.setattr(supervisor, "plain_job", plain)
    monkeypatch.setattr(supervisor, "gpu_queue", queue)
    monkeypatch.setattr(
        training,
        "register_exploratory_training",
        lambda *a, **kw: dict(launcher=str(launcher), arms=list(final.ARMS)),
    )
    monkeypatch.setattr(mechanisms, "register", register_mechanisms)
    monkeypatch.setattr(final, "register", register_final)
    monkeypatch.setattr(final, "checked_plan", lambda output: final_plan)
    monkeypatch.setattr(final, "aggregate", aggregate_final)
    monkeypatch.setattr(mechanisms, "score_point", score_point)
    monkeypatch.setattr(mechanisms, "aggregate", aggregate_mechanisms)
    result = supervisor.run()
    assert len(queues) == 4 and result["final_evaluation_id"] == "synthetic-final-summary"
    assert result["mechanism_report_id"] == "synthetic-mechanism-summary"
    assert "not automatically dispatched" in result["Experiment5"]
