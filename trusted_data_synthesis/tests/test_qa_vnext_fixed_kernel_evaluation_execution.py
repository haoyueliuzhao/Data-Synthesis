"""Synthetic process/record controls; never launch real models, GPUs or APIs."""

import copy

import pytest
from test_qa_vnext_fixed_kernel_consumer_training import admitted_inputs as admitted_inputs
from test_qa_vnext_fixed_kernel_evaluation_decoder import assets

from trusted_synthesis.experiments.finance_qa_vnext_basis_student import decoder as old_decoder
from trusted_synthesis.experiments.finance_qa_vnext_basis_student import protocol as old_protocol
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import evaluation as e
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import execution as x
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import training as t


def frozen():
    budget = {
        key + suffix: value
        for key, value in (
            ("packages", 3200),
            ("rows", 3200),
            ("target_tokens", 6400),
            ("sequence_tokens", 12800),
        )
        for suffix in ("_all_epochs",)
    }
    return dict(
        id="synthetic_execution_freeze",
        study_freeze_id="synthetic_study",
        output_directory="experiment",
        kernel_id="synthetic_kernel",
        input_files={},
        base_binding={"id": "synthetic_base"},
        tokenizer_binding={"id": "synthetic_tokenizer"},
        training_configuration=t.training_config(),
        decoder_configuration={"id": "synthetic_decoder"},
        code_binding={"id": "synthetic_code"},
        source_root="/tmp/synthetic_sources",
        physical_originals_sha256="physical_frozen",
        material_verification={"pool_budgets": {pool: budget for pool in p.POOLS}},
    )


def test_new_decoder_changes_bindings_not_physical_generation_policy():
    old, new = old_decoder.policy(), e.policy()
    assert {key: value for key, value in old.items() if key not in ("id", "schema_version")} == {
        key: value for key, value in new.items() if key not in ("id", "schema_version")
    }
    assert old["schema_version"].startswith("basis_student.")
    assert new["schema_version"].startswith("fixed_kernel_value.")
    assert "kernel_id" in e.BINDING_FIELDS and "materials_manifest_id" not in e.BINDING_FIELDS


def test_exact_selection_confirmation_cross_products_and_no_B_dev():
    a, dev, b, confirm = (
        x.jobs_for("A_train"),
        x.jobs_for("A_dev"),
        x.jobs_for("B_train", "plus"),
        x.jobs_for("confirm", "plus"),
    )
    assert (len(a), len(dev), len(b), len(confirm)) == (9, 9, 6, 12)
    assert len(dev) * 180 + len(confirm) * 720 == 10260
    assert all(job["pool"] == "A" and job["split"] == "dev" for job in dev)
    assert {job["arm"] for job in b} == {"alpha0", "plus"}
    assert {job["arm"] for job in confirm} == {"alpha0", "plus"}
    assert len({x.job_name(job) for job in a + dev + b + confirm}) == 36
    for phase in ("B_train", "confirm"):
        with pytest.raises(ValueError, match="strict_positive"):
            x.jobs_for(phase, "alpha0")
    assert x.execution_policy()["fixed_confirm_unique_tasks"] == 720
    assert not x.execution_policy()["seeds_multiply_independent_task_count"]


def test_only_idle_large_memory_gpus_in_ascending_physical_order(monkeypatch):
    monkeypatch.setattr(
        x.subprocess,
        "check_output",
        lambda *args, **kwargs: (
            "7, GPU-7, 81000, 0\n3, GPU-3, 81000, 2\n1, GPU-1, 75999, 0\n0, GPU-0, 76000, 0\n"
        ),
    )
    assert x.available_gpus() == [
        dict(index=0, uuid="GPU-0", free_memory_MiB=76000),
        dict(index=7, uuid="GPU-7", free_memory_MiB=81000),
    ]


def fake_processes(monkeypatch, *, first_failure=False, spawn_failure=False):
    observed = dict(started=[], active=0, maximum=0, commands=[])

    class Process:
        def __init__(self, command, **kwargs):
            if spawn_failure:
                raise OSError("synthetic spawn failure")
            self.index = len(observed["started"])
            self.pid = 1000 + self.index
            self.finished = False
            observed["started"].append(self)
            observed["commands"].append((command, kwargs))
            observed["active"] += 1
            observed["maximum"] = max(observed["maximum"], observed["active"])

        def poll(self):
            if not self.finished:
                observed["active"] -= 1
                self.finished = True
            return 1 if first_failure and self.index == 0 else 0

    monkeypatch.setattr(x.subprocess, "Popen", Process)
    monkeypatch.setattr(
        x,
        "available_gpus",
        lambda: [dict(index=i, uuid=f"GPU-{i}", free_memory_MiB=81000) for i in range(12)],
    )
    monkeypatch.setattr(x, "validate_freeze", lambda frozen: None)
    monkeypatch.setattr(x.time, "sleep", lambda seconds: None)
    return observed


def release():
    return {
        "allowed_runs": [
            {key: job[key] for key in ("pool", "arm", "seed")} for job in x.jobs_for("A_train")
        ]
    }


def test_gpu_worker_cap_eight_and_complete_nine_registry(tmp_path, monkeypatch):
    observed = fake_processes(monkeypatch)
    result = x.run_jobs(tmp_path, frozen(), "A_train", release=release())
    assert result["status"] == "COMPLETE_FIXED_WORKERS"
    assert result["planned"] == len(result["finished"]) == len(observed["started"]) == 9
    assert observed["maximum"] == 8
    assert observed["active"] == 0
    assert not result["failures"] and not result["not_started"]
    for command, kwargs in observed["commands"]:
        assert any(
            item.endswith("finance_qa_vnext_fixed_kernel_value.execution") for item in command
        )
        assert kwargs["env"]["CUDA_VISIBLE_DEVICES"].startswith("GPU-")
        assert kwargs["env"]["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    with pytest.raises(ValueError, match="no_phase_reexecution"):
        x.run_jobs(tmp_path, frozen(), "A_train", release=release())


@pytest.mark.parametrize("spawn", (False, True))
def test_worker_failure_stops_new_launches_without_dropping_registry(tmp_path, monkeypatch, spawn):
    observed = fake_processes(monkeypatch, first_failure=not spawn, spawn_failure=spawn)
    with pytest.raises(ValueError, match="worker_failure_no_retry"):
        x.run_jobs(tmp_path, frozen(), "A_train", release=release())
    report = p.read_json(tmp_path / "experiment/jobs/A_train/report.json")
    assert report["planned"] == 9
    assert len(report["finished"]) + len(report["failures"]) + len(report["not_started"]) == 9
    assert len(report["failures"]) == 1
    assert len(observed["started"]) == (0 if spawn else 8)
    assert len(report["not_started"]) == (8 if spawn else 1)
    assert report["retries"] == 0 and not report["partial_output_reused"]


def test_public_worker_rejects_private_payload_before_model_load(tmp_path, monkeypatch):
    monkeypatch.setattr(x, "verify_code", lambda bound: None)
    calls = []
    monkeypatch.setattr(e, "load_decoder", lambda *args: calls.append(True))
    job = x.jobs_for("A_dev")[0]
    payload = p.record(
        "worker_job",
        job=job,
        gpu={},
        code_binding={},
        execution_freeze_id="synthetic",
        launched_at="synthetic",
        public_generation_input={},
        training_input={"private": "forbidden"},
    )
    path = tmp_path / "jobs/A_dev/job.json"
    p.write_once(path, payload)
    with pytest.raises(ValueError, match="no_private_material"):
        x.worker(tmp_path, path)
    assert calls == []


def synthetic_training_report(root, freeze, job, initial="paired"):
    path = x.job_output(root, freeze, job)
    p.write_once(path / "final.safetensors", {"synthetic_only": True})
    adapter = dict(
        path="final.safetensors",
        bytes=(path / "final.safetensors").stat().st_size,
        sha256=p.sha(path / "final.safetensors"),
        parameter_digest="synthetic_adapter",
    )
    # The real consumer tests independently execute all 400 updates. Here the
    # synthetic report interface has eight whole originals in each update.
    report = p.record(
        "training_report",
        **{key: value for key, value in x.binding(freeze).items() if key != "decoder_config_id"},
        pool=job["pool"],
        arm=job["arm"],
        seed=job["seed"],
        actual_complete=True,
        status="COMPLETE_FINAL_CHECKPOINT",
        optimizer_updates=400,
        epochs_completed=10,
        checkpoint_id=adapter["parameter_digest"],
        final_adapter=adapter,
        final_adapter_restored_identity_verified=True,
        adapter_directory=str(path.relative_to(root)),
        initial_adapter_digest=initial,
        schedule_id="paired_schedule:" + str(job["seed"]),
        physical_originals_sha256=freeze["physical_originals_sha256"],
        actual_budget=freeze["material_verification"]["pool_budgets"][job["pool"]],
        updates=[dict(packages=8, rows=8, target_tokens=16, sequence_tokens=32)] * 400,
    )
    p.write_once(path / "report.json", report)
    return report


def test_new_model_identity_and_public_job_have_no_material_payload(tmp_path):
    freeze = frozen()
    job = x.jobs_for("A_dev")[0]
    synthetic_training_report(tmp_path, freeze, {**job, "kind": "train"})
    value = x.public_generation_input(tmp_path, freeze, job)
    assert set(value) == {
        "model_identity",
        "base_binding",
        "tokenizer_binding",
        "decoder_configuration",
        "surface_directory",
        "surface_manifest_id",
        "source_root",
        "split",
        "output_directory",
    }
    assert "kernel_id" in value["model_identity"]
    assert "train_packages" not in str(value)
    assert "input_files" not in str(value)
    assert value["model_identity"]["schema_version"].startswith("fixed_kernel_value.")
    with pytest.raises(ValueError, match="identity"):
        old_decoder.validate_model_identity(value["model_identity"])


def test_old_training_report_cannot_masquerade_as_new(tmp_path):
    freeze, job = frozen(), x.jobs_for("A_train")[0]
    path = x.job_output(tmp_path, freeze, job)
    p.write_once(path / "report.json", old_protocol.record("training_report", actual_complete=True))
    with pytest.raises(ValueError, match="identity"):
        x._training_report(tmp_path, freeze, job)


def test_metadata_only_claimed_PASS_does_not_bypass_prepare_inputs(tmp_path, monkeypatch):
    files = {}
    for key in ("population", "registry", "materialization_index"):
        files[key] = tmp_path / (key + ".json")
        p.write_once(files[key], {})
    calls = []
    monkeypatch.setattr(x, "code_binding", lambda: calls.append(True))
    with pytest.raises(ValueError):
        x.prepare(
            tmp_path,
            tmp_path / "out",
            source_root=tmp_path,
            study_freeze_id="synthetic",
            population_path=files["population"],
            registry_path=files["registry"],
            materialization_index_path=files["materialization_index"],
            base_binding={},
            tokenizer_binding={},
        )
    assert calls == [] and not (tmp_path / "out").exists()


def test_immutable_file_descriptor_rejects_changed_bytes(tmp_path):
    p.write_once(tmp_path / "input.json", {"frozen": True})
    descriptor = x.descriptor(tmp_path, tmp_path / "input.json")
    modified = copy.deepcopy(descriptor)
    modified["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="original_material_file_bytes"):
        x.load_descriptor(tmp_path, modified)


@pytest.mark.parametrize(
    "selected,expected_sessions", (("alpha0", 1620), ("plus", 10260), ("minus", 10260))
)
def test_top_level_selection_controls_exactly_which_phases_can_start(
    tmp_path, monkeypatch, selected, expected_sessions
):
    freeze = frozen()
    freeze["input_files"] = {
        key: {"path": key} for key in ("population", "registry", "materialization_index")
    }
    frozen_path = tmp_path / "synthetic_freeze.json"
    p.write_once(frozen_path, freeze)
    phases, scored = [], []
    monkeypatch.setattr(x, "validate_freeze", lambda value: None)
    monkeypatch.setattr(x, "verify_code", lambda value: None)
    monkeypatch.setattr(
        x,
        "load_material_inputs",
        lambda *args: {"kernel": {}, "population": {}, "registry": {}, "outcomes": []},
    )
    monkeypatch.setattr(t, "validate_materials", lambda *args: freeze["material_verification"])
    monkeypatch.setattr(
        t, "make_release", lambda kernel, **kwargs: {"allowed_runs": kwargs["allowed_runs"]}
    )
    monkeypatch.setattr(x, "training_reports", lambda *args: [])

    def simulated_phase(root, frozen, phase, **kwargs):
        phases.append((phase, kwargs.get("selected")))
        if phase.endswith("train"):
            assert len(kwargs["release"]["allowed_runs"]) == (9 if phase == "A_train" else 6)
            if phase == "B_train":
                assert {item["arm"] for item in kwargs["release"]["allowed_runs"]} == {
                    "alpha0",
                    selected,
                }

    def simulated_scores(root, frozen, jobs):
        scored.extend(jobs)
        return []

    monkeypatch.setattr(x, "run_jobs", simulated_phase)
    monkeypatch.setattr(x, "score_jobs", simulated_scores)
    freeze["evaluation_registry"] = {"dev": [], "confirm": []}
    # The source argument is immutable; supply the complete control object via
    # the read seam, leaving the exclusive fixture file unchanged.
    original_read = p.read_json
    monkeypatch.setattr(
        p, "read_json", lambda path: freeze if path == frozen_path else original_read(path)
    )
    monkeypatch.setattr(
        e,
        "select_actual_direction",
        lambda *args, **kwargs: p.record("actual_direction_decision", selected_arm=selected),
    )
    monkeypatch.setattr(
        e,
        "confirm_actual",
        lambda *args, **kwargs: p.record("confirmation_analysis", status="NOT_CONFIRMED"),
    )
    report = x.run(tmp_path, frozen_path)
    assert [phase for phase, _ in phases] == ["A_train", "A_dev"] + (
        [] if selected == "alpha0" else ["B_train", "confirm"]
    )
    assert report["actual_evaluation_sessions"] == expected_sessions
    assert len(scored) == (9 if selected == "alpha0" else 21)
    assert report["independent_positive_effect_confirmed"] is False
    if selected != "alpha0":
        assert phases[-2:] == [("B_train", selected), ("confirm", selected)]
    assert (tmp_path / "experiment/manifest.json").exists()


def test_uncommitted_new_code_cannot_become_production_freeze(monkeypatch):
    monkeypatch.setattr(
        x.subprocess,
        "check_output",
        lambda command, **kwargs: "synthetic-commit\n" if command[1] == "rev-parse" else "",
    )
    with pytest.raises(ValueError, match="all_new_python_code_committed"):
        x.code_binding()


def test_preparation_hydrates_authoritative_index_without_duplicate_token_files(
    tmp_path, monkeypatch, admitted_inputs
):
    selected, registry, outcomes, kernel = admitted_inputs
    paths = {key: tmp_path / (key + ".json") for key in ("population", "registry", "index")}
    p.write_once(paths["population"], selected)
    p.write_once(paths["registry"], registry)
    index = p.record(
        "materialization_index",
        registry_id=registry["id"],
        freeze_id=registry["freeze_id"],
        status="COMPLETE_FIXED_MATERIALIZATION",
        collection_complete=True,
        complete_registered_denominator=10240,
    )
    p.write_once(paths["index"], index)
    hydrated = []

    def hydrate(supplied, directory):
        assert supplied == index and directory == tmp_path
        hydrated.append(supplied["id"])
        return outcomes

    # Per-session reference verification is exercised separately by the material
    # tests. This seam checks the exact bridge and full real kernel reconstruction.
    monkeypatch.setattr(x.materials, "hydrate_outcomes", hydrate)
    monkeypatch.setattr(
        x,
        "code_binding",
        lambda: p.record(
            "execution_code_binding",
            code_root=str(x.code_root()),
            head_commit="synthetic",
            members=[],
        ),
    )
    monkeypatch.setattr(x, "evaluation_registry", lambda root: {"dev": [], "confirm": []})
    tokens, base = assets()
    tokens["id"] = "synthetic_tokenizer"
    output = tmp_path / "execution"
    freeze = x.prepare(
        tmp_path,
        output,
        source_root=tmp_path,
        study_freeze_id=registry["freeze_id"],
        population_path=paths["population"],
        registry_path=paths["registry"],
        materialization_index_path=paths["index"],
        base_binding=base,
        tokenizer_binding=tokens,
    )
    assert freeze["kernel_id"] == kernel["id"]
    assert hydrated == [index["id"]]
    assert set(freeze["input_files"]) == {"population", "registry", "materialization_index"}
    assert not freeze["kernel_and_outcomes_token_arrays_serialized_again"]
    assert not freeze["Student_or_GPU_loaded"]
    files = [path for path in output.rglob("*") if path.is_file()]
    assert files == [output / "preparation/execution_freeze.json"]
    assert "input_ids" not in files[0].read_text()
