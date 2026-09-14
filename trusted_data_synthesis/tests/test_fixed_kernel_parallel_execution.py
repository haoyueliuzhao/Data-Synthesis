"""Three small synthetic handoff controls; never launch or signal real processes."""

from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import execution as x
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    parallel_lineage as lineage,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import parallel_study as s
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def budget(rows, sequence):
    values = dict(
        packages_per_epoch=40,
        rows_per_epoch=rows,
        target_tokens_per_epoch=80,
        sequence_tokens_per_epoch=sequence,
    )
    return {
        **values,
        **{key.replace("per_epoch", "all_epochs"): 10 * value for key, value in values.items()},
    }


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root, parent = tmp_path / "new", tmp_path / "parent"
    root.mkdir()
    parent.mkdir()
    monkeypatch.setattr(s, "guard", lambda value: root)
    monkeypatch.setattr(s, "PARENT_ROOT", parent)
    monkeypatch.setattr(s, "PARENT_OUTPUT", "old")
    monkeypatch.setattr(s, "PARENT_RUNTIME", "runtime")
    monkeypatch.setattr(s, "OUTPUT", "newout")
    monkeypatch.setattr(s, "check_scheduler", lambda frozen: {"state": "T"})
    monkeypatch.setattr(
        x, "code_binding", lambda: {"id": "new_committed_code", "code_root": str(root)}
    )
    monkeypatch.setattr(
        x.trajectory_materials, "prepare_cache", lambda *_a, **_k: pytest.fail("cache rebuilt")
    )
    monkeypatch.setattr(
        x.fast_materials, "load_material_inputs", lambda *_a, **_k: pytest.fail("raw corpus loaded")
    )
    cache = parent / "old/preparation/trajectory_cache"
    pools = {}
    for pool in p.POOLS:
        pools[pool] = {}
        for key, name in (
            ("input_ids", "input_ids.npy"),
            ("target_positions", "target_positions.npy"),
            ("package_index", "packages.json"),
        ):
            path = cache / pool / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((pool + ":synthetic:" + key).encode())
            pools[pool][key] = x.descriptor(cache, path)
    actual = {pool: budget(40, 480) for pool in p.POOLS}
    source = {pool: budget(80, 800) for pool in p.POOLS}
    manifest = p.record(
        "trajectory_material_cache",
        pools=pools,
        kernel_id=s.EXPECTED_KERNEL,
        pool_budgets=actual,
        source_material_budgets=source,
    )
    p.write_once(cache / "manifest.json", manifest)
    p.write_once(cache / "started.json", p.record("trajectory_cache_started", synthetic=True))
    verification = p.record(
        "material_input_verification", kernel_id=s.EXPECTED_KERNEL, pool_budgets=source
    )
    old = p.record(
        "execution_freeze",
        output_directory="old",
        study_freeze_id="original_study",
        source_root="/original/evaluation",
        input_root="/original/receipt_root",
        input_files={},
        material_input_receipt={"path": "original_receipt", "bytes": 25, "sha256": "unchanged"},
        kernel_id=s.EXPECTED_KERNEL,
        original_material_gate_id=s.EXPECTED_GATE,
        training_configuration=x.training.training_config(),
        decoder_configuration={"id": "decoder"},
        base_binding={"id": "base"},
        tokenizer_binding={"id": "tokenizer"},
        physical_originals_sha256="physical",
        material_verification=verification,
        trajectory_pool_budgets=actual,
        source_material_budgets=source,
        trajectory_cache=dict(
            cache_root=str(cache.relative_to(parent)),
            manifest=x.descriptor(parent, cache / "manifest.json"),
            manifest_id=manifest["id"],
        ),
    )
    authority = p.record(
        "trajectory_execution_authority",
        execution_freeze_id=old["id"],
        original_kernel_id=s.EXPECTED_KERNEL,
        original_material_gate_id=s.EXPECTED_GATE,
        original_generation_report_id="closed_generation",
        completion_freeze_id="completion_budget",
    )
    pause = p.record("parallel_tail_handoff_pause", synthetic=True)
    p.write_once(parent / "old/preparation/execution_freeze.json", old)
    p.write_once(parent / "old/preparation/trajectory_execution_authority.json", authority)
    p.write_once(parent / "runtime/parallel_tail_handoff_pause.json", pause)
    workers = [
        dict(
            job=job,
            request_id="original_job:" + x.job_name(job),
            release_id="original_release",
            process={"pid": 1000 + index, "start_ticks": index + 1},
            gpu={"uuid": f"GPU-{index}"},
        )
        for index, job in enumerate(job for job in x.jobs_for("A_train") if job != s.TAIL)
    ]
    monkeypatch.setattr(
        s, "source_workers", lambda *_a: ({"pid": 42, "start_ticks": 1, "state": "T"}, workers)
    )
    result = s.prepare(root)
    return SimpleNamespace(
        root=root,
        parent=parent,
        old=old,
        cache=cache,
        manifest=manifest,
        frozen=result["execution_freeze"],
        authority=result["authority"],
        workers=workers,
    )


def test_prepare_copies_only_eight_cache_files_and_preserves_parent_authorities(prepared):
    value = prepared
    frozen = value.frozen
    copied = value.root / frozen["trajectory_cache"]["cache_root"]
    originals = sorted(
        path.relative_to(value.cache) for path in value.cache.rglob("*") if path.is_file()
    )
    assert len(originals) == 8
    assert all(
        (copied / name).read_bytes() == (value.cache / name).read_bytes() for name in originals
    )
    assert p.read_json(copied / "manifest.json") == value.manifest
    assert frozen["trajectory_cache"]["manifest_id"] == value.manifest["id"]
    assert frozen["input_root"] == value.old["input_root"]
    assert frozen["material_input_receipt"] == value.old["material_input_receipt"]
    assert frozen["material_verification"] == value.old["material_verification"]
    assert frozen["heterogeneous_execution"] is True
    assert frozen["per_run_training_configuration_ids"] == lineage.configuration_ids()
    assert len(frozen["parent_workers"]) == 8 and all(
        row["job"] != s.TAIL for row in frozen["parent_workers"]
    )
    assert value.authority["parent_workers_signaled"] is False


def create_parent_report(value, job):
    directory = x.job_output(value.parent, {**value.frozen, "output_directory": "old"}, job)
    directory.mkdir(parents=True)
    adapter = directory / "final_adapter.safetensors"
    adapter.write_bytes(b"synthetic final adapter bytes; never loaded")
    fields = dict(
        **{
            key: item for key, item in x.binding(value.frozen).items() if key != "decoder_config_id"
        },
        pool=job["pool"],
        arm=job["arm"],
        seed=job["seed"],
        release_id="original_release",
        actual_complete=True,
        status="COMPLETE_FINAL_CHECKPOINT",
        optimizer_updates=400,
        epochs_completed=10,
        base_binding_id="base",
        tokenizer_binding_id="tokenizer",
        physical_originals_sha256="physical",
        trajectory_cache_id=value.manifest["id"],
        actual_budget=value.frozen["trajectory_pool_budgets"]["A"],
        source_material_budget=value.frozen["source_material_budgets"]["A"],
        initial_adapter_digest="0" * 64,
        schedule_id="original_schedule_47",
        adapter_directory=str(directory.relative_to(value.parent)),
        checkpoint_id="1" * 64,
        final_adapter=dict(
            path=adapter.name,
            bytes=adapter.stat().st_size,
            sha256=p.sha(adapter),
            parameter_digest="1" * 64,
        ),
        final_adapter_restored_identity_verified=True,
        updates=[
            dict(
                packages=1,
                rows=1,
                target_tokens=2,
                sequence_tokens=12,
                path="old/training/historical_update.json",
            )
        ]
        * 400,
    )
    report = p.record("training_report", **fields)
    p.write_once(directory / "report.json", report)
    p.write_once(directory / "identity.json", p.record("training_run_identity", original=True))
    return report, directory


def test_completed_import_keeps_report_ID_and_bytes_but_decoder_uses_new_adapter_location(prepared):
    job = dict(kind="train", pool="A", arm="alpha0", seed=47)
    report, source = create_parent_report(prepared, job)
    bound = next(row for row in prepared.workers if row["job"] == job)
    observation = dict(
        state="Z", return_code=0, exit_status_provable=True, pid=bound["process"]["pid"]
    )
    receipt = s.import_completed_run(prepared.root, prepared.frozen, bound, observation)
    copied = x.job_output(prepared.root, prepared.frozen, job)
    assert (copied / "report.json").read_bytes() == (source / "report.json").read_bytes()
    assert receipt["training_report_id"] == report["id"]
    assert receipt["report_ID_or_historical_paths_rewritten"] is False
    assert p.read_json(copied / "report.json")["adapter_directory"] == report["adapter_directory"]
    public = x.public_generation_input(
        prepared.root, prepared.frozen, {**job, "kind": "generate", "split": "dev"}
    )
    identity = public["model_identity"]
    assert identity["training_report_id"] == report["id"]
    assert identity["adapter_directory"] == str(copied.relative_to(prepared.root))
    assert identity["adapter_directory"] != report["adapter_directory"]
    assert identity["training_configuration_id"] == report["training_configuration_id"]


def test_handoff_launches_only_one_tail_and_checks_existing_seed47_pair(prepared, monkeypatch):
    records = [
        dict(
            job=row["job"],
            training_report_id="original:" + x.job_name(row["job"]),
            initial_adapter_digest="0" * 64,
            schedule_id="schedule:" + str(row["job"]["seed"]),
        )
        for row in prepared.workers
    ]
    reports = [
        dict(
            id="new_tail" if job == s.TAIL else "original:" + x.job_name(job),
            pool=job["pool"],
            arm=job["arm"],
            seed=job["seed"],
            training_configuration_id=lineage.expected_training_config(
                job["pool"], job["arm"], job["seed"]
            )["id"],
        )
        for job in x.jobs_for("A_train")
    ]
    calls = []
    monkeypatch.setattr(x, "validate_freeze", lambda *_a: None)
    monkeypatch.setattr(s, "await_parent_imports", lambda *_a: records)
    monkeypatch.setattr(s, "await_devices", lambda *_a: [f"GPU-{index}" for index in range(8)])
    monkeypatch.setattr(
        s.fast_materials, "load_authority", lambda *_a, **_k: {"kernel": {"id": s.EXPECTED_KERNEL}}
    )

    def release(*_a, **kwargs):
        assert kwargs["allowed_runs"] == [dict(pool="A", arm="minus", seed=47)]
        return {"id": "new_tail_release"}

    def launch(*_a, **kwargs):
        assert len(kwargs["devices"]) == 8
        assert kwargs["expected_initial_adapter_digest"] == "0" * 64
        assert kwargs["expected_schedule_id"] == "schedule:47"
        calls.append("tail")
        return reports[-1]

    def continuation(_root, _freeze, *, handoff):
        assert handoff["imported_parent_runs"] == 8 and handoff["new_parallel_runs"] == 1
        assert handoff["training_report_ids"] == [row["id"] for row in reports]
        calls.append("Adev_B_confirm")
        return {"actual_complete": True}

    monkeypatch.setattr(s.parallel_training, "make_release", release)
    monkeypatch.setattr(s.parallel_training, "launch", launch)
    monkeypatch.setattr(x, "validate_training_report", lambda report, *_a: report)
    monkeypatch.setattr(x, "training_reports", lambda *_a: reports)
    monkeypatch.setattr(x, "run", continuation)
    assert s.run(prepared.root)["actual_complete"] is True
    assert calls == ["tail", "Adev_B_confirm"]
