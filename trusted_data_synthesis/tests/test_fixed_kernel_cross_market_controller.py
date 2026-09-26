"""Controller controls use generated metadata/tiny CPU tensors, not real models."""

import os
from pathlib import Path

import fixed_kernel_cross_market_evaluation_20260926 as evaluation
import pytest
import run_fixed_kernel_cross_market_evaluation_20260926 as m


@pytest.fixture
def context(tmp_path):
    c = evaluation.Context(tmp_path)
    tasks = [
        dict(
            task_id=f"task-{index}",
            group=m.prior.GROUPS[index % 3],
            path=str(tmp_path / f"task{index}.json"),
        )
        for index in range(180)
    ]
    manifest = m.p.record("source_view_manifest_v2", split="calibration", tasks=tasks)
    admission = m.p.record(
        "calibration_panel_admission", passed=True, source_manifest_id=manifest["id"]
    )
    c.write(tmp_path / "manifest.json", manifest)
    c.write(tmp_path / "admission.json", admission)
    panel = {name: m.reference(tmp_path / (name + ".json")) for name in ("manifest", "admission")}
    models = [
        dict(key=f"{arm}_{seed}", condition=arm, seed=seed)
        for arm in m.prior.ARMS
        for seed in m.prior.SEEDS
    ]
    plan = m.p.record(
        evaluation.PROTOCOL_KIND,
        frozen=True,
        panel=panel,
        source_manifest_id=manifest["id"],
        materials=dict(
            runtime_binding=evaluation.views.binding(), assets={"base_binding": {"id": "base"}}
        ),
        scientific_sources={},
        models=models,
        scheduling=dict(generation_shards_stochastic=3, generation_shards_greedy=2),
    )
    c.write(tmp_path / "protocol.json", plan)
    return c, plan


def test_exact45shards18cohorts4860paired_sessions(context, monkeypatch):
    c, plan = context

    def point(c, plan, model):
        return c.RAW / "points" / model["key"] / "point.json", {"id": "point:" + model["key"]}

    monkeypatch.setattr(m, "prepare_point", point)
    cohorts = m.prepare_cohorts(c, plan)
    assert len(cohorts) == 18
    assert sum(len(row["shards"]) for row in cohorts) == 45
    assert sum(len(row["registration"]["jobs"]) for row in cohorts) == 4860
    for seed in m.prior.SEEDS:
        for mode in m.prior.MODES:
            selected = [
                row
                for row in cohorts
                if row["common"]["seed"] == seed and row["common"]["phase"] == mode
            ]
            assert (
                len({tuple(job["seed"] for job in row["registration"]["jobs"]) for row in selected})
                == 1
            )
    for row in cohorts:
        indices = [unit["index"] for shard in row["shards"] for unit in shard["jobs"]]
        assert sorted(indices) == list(range(len(row["registration"]["jobs"])))
    assert len({row["point"]["id"] for row in cohorts}) == 9


def test_incomplete_cohort_never_sealed(context):
    c, plan = context
    cohort = {"common": {"directory": str(c.RAW / "notcomplete")}, "shards": [{"key": "missing"}]}
    assert m.seal_cohort(c, plan, cohort) is None
    assert not (c.RAW / "notcomplete/generation_manifest.json").exists()


def test_existing_step240_cpu_serialization_no_training(context):
    c, plan = context
    path = c.RAW / "tiny_cpu_checkpoint.pt"
    saved = {
        "completed_updates": 240,
        "snapshot": {"id": "snapshot:synthetic"},
        "state": {
            "theta/test.lora_A": m.legacy.torch.ones((2, 2), dtype=m.legacy.torch.float32),
            "theta/test.lora_B": m.legacy.torch.zeros((2, 2), dtype=m.legacy.torch.float32),
        },
        "update_report": {"id": "update:synthetic"},
    }
    m.legacy.torch.save(saved, path)
    model = dict(
        key="negative_11",
        condition="negative",
        seed=11,
        path=str(path),
        sha256=m.p.sha(path),
        snapshot_id="snapshot:synthetic",
    )
    point_path, point = m.prepare_point(c, plan, model)
    assert point["step"] == 240
    assert point["run"] == {"condition": "negative", "seed": 11}
    assert point["origin_checkpoint"] == model
    assert Path(point_path).is_file()
    assert m.prepare_point(c, plan, model) == (point_path, point)
    assert m.p.sha(path) == model["sha256"]


def test_worker_cannot_bypass_launch_charge(context):
    c, plan = context
    job = m.p.record(
        "cross_market_evaluation_work_unit", protocol_id=plan["id"], key="g", work_kind="generate"
    )
    path = c.RAW / "jobspecs/g.json"
    c.write(path, job)
    with pytest.raises(ValueError, match="registered_precharged_worker"):
        m.worker(c.RAW, c.RAW, path, 1)


def test_process_identity_detects_actual_process():
    assert m.process_identity(os.getpid()) is not None
    assert m.process_identity(999999999) is None


def test_gpu_capacity_query_read_only_and_threshold(monkeypatch):
    monkeypatch.setattr(
        m.subprocess,
        "check_output",
        lambda *a, **kw: "GPU-one, 81000\nGPU-two, 49000\nGPU-three, 49152\n",
    )
    assert m.available_gpus(49152) == ["GPU-one", "GPU-three"]


@pytest.mark.parametrize("changed", [False, True])
def test_parent_training_credit_content_identity(context, monkeypatch, changed):
    c, _plan = context
    monkeypatch.setattr(m, "PARENT", c.RAW)
    admission = m.p.record("direction_calibration_material_admission", passed=True)
    complete = m.p.record(
        "B_direction_calibration_training_completed", complete=True, committed_optimizer_updates=120
    )
    if changed:
        admission["undocumented_mutation"] = True
    c.write(c.RAW / "reuse_admission.json", admission)
    c.write(c.RAW / "training_stage_20260926/complete.json", complete)
    if changed:
        with pytest.raises(ValueError):
            m.training_credits()
    else:
        assert m.training_credits() == (admission, complete)


def test_completed_controller_is_idempotent_without_loading_points(context, monkeypatch):
    c, plan = context
    reports = []
    for index in range(18):
        path = c.RAW / "scores" / f"{index}.json"
        c.write(path, m.p.record("synthetic_score", cohort=index))
        reports.append(m.reference(path))
    seal_path = c.RAW / "generation_seal.json"
    c.write(seal_path, m.p.record("synthetic_seal", complete=True))
    completed = m.p.record(
        "cross_market_evaluation_completed",
        complete=True,
        protocol_id=plan["id"],
        source_manifest_id=plan["source_manifest_id"],
        scored_sessions=4860,
        scoring_reports=reports,
        generation_seal=m.reference(seal_path),
    )
    c.write(c.RAW / "complete.json", completed)

    def forbidden(*args):
        raise AssertionError("completed experiment must not prepare/load model points")

    monkeypatch.setattr(m, "prepare_cohorts", forbidden)
    assert m.coordinate(c.RAW, c.RAW) == completed
