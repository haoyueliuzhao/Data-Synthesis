"""Four tiny lineage/worker/budget stubs; no models, full corpus or GPU checks."""

from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import execution as x
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import trajectory_study as s


def budgets(rows, sequence):
    result = dict(
        packages_per_epoch=40,
        rows_per_epoch=rows,
        target_tokens_per_epoch=80,
        sequence_tokens_per_epoch=sequence,
    )
    return {
        **result,
        **{key.replace("per_epoch", "all_epochs"): value * 10 for key, value in result.items()},
    }


@pytest.fixture
def parent(tmp_path, monkeypatch):
    root, source = tmp_path / "new", tmp_path / "parent"
    root.mkdir()
    source.mkdir()
    source_budgets = {pool: budgets(80, 800) for pool in p.POOLS}
    actual_budgets = {pool: budgets(40, 480) for pool in p.POOLS}
    verification = p.record(
        "material_input_verification",
        kernel_id="original_kernel",
        pool_budgets=source_budgets,
        tokenizer_binding_id="tokenizer",
    )
    gate = p.record(
        "material_gate",
        kernel_id="original_kernel",
        training_gate="PASS",
        material_gate="PASS",
        dose_gate="PASS",
        generation_report_id="generation",
    )
    p.write_once(source / "material/material_gate.json", gate)
    frozen = p.record(
        "execution_freeze",
        study_freeze_id="original_study",
        output_directory="old",
        source_root="/readonly/evaluation",
        kernel_id="original_kernel",
        input_files={},
        material_input_receipt={
            "path": "old/preparation/receipt.json",
            "bytes": 25,
            "sha256": "receipt",
        },
        original_material_gate=x.descriptor(source, source / "material/material_gate.json"),
        original_material_gate_id=gate["id"],
        base_binding={"id": "base"},
        tokenizer_binding={"id": "tokenizer"},
        training_configuration={"id": "old_training"},
        decoder_configuration={"id": "unchanged_decoder"},
        analysis_policy={"id": "unchanged_analysis"},
        evaluation_registry={"dev": ["original_dev"], "confirm": ["original_confirm"]},
        material_verification=verification,
        physical_originals_sha256="physical",
        code_binding={"code_root": str(source)},
        material_gate="PASS",
        dose_gate="PASS",
        training_gate="PASS",
    )
    authority = p.record(
        "fast_execution_authority",
        execution_freeze_id=frozen["id"],
        original_kernel_id="original_kernel",
        original_material_gate_id=gate["id"],
        original_registry_freeze_id="original_study",
        original_generation_report_id="generation",
        actual_full_original_kernel_ID_equal=True,
        completion_freeze_id="budget_completion",
    )
    frozen_path = source / "old/preparation/execution_freeze.json"
    authority_path = source / "old/preparation/fast_execution_authority.json"
    p.write_once(frozen_path, frozen)
    p.write_once(authority_path, authority)
    calls = []

    def cache(source_root, output, parent_path, *, workers):
        assert source_root == source and parent_path == frozen_path and workers == 24
        calls.append("cache")
        manifest = p.record(
            "trajectory_material_cache",
            kernel_id="original_kernel",
            material_verification_id=verification["id"],
            parent_execution_freeze_id=frozen["id"],
            source_material_receipt=frozen["material_input_receipt"],
            source_material_budgets=source_budgets,
            pool_budgets=actual_budgets,
        )
        p.write_once(output / "manifest.json", manifest)
        return manifest

    def code():
        calls.append("code")
        return {"id": "committed_code", "code_root": str(root)}

    monkeypatch.setattr(x, "code_binding", code)
    monkeypatch.setattr(x.trajectory_materials, "prepare_cache", cache)
    monkeypatch.setattr(
        x.fast_materials,
        "load_material_inputs",
        lambda *_a, **_k: pytest.fail("forbidden full material hydration"),
    )
    monkeypatch.setattr(
        x.fast_materials,
        "load_authority",
        lambda *_a, **_k: pytest.fail("prepare must let cache builder own one receipt load"),
    )
    monkeypatch.setattr(s, "guard", lambda value: root)
    monkeypatch.setattr(s, "PARENT_ROOT", source)
    monkeypatch.setattr(s, "PARENT_OUTPUT", "old")
    monkeypatch.setattr(s, "OUTPUT", "trajectory")
    monkeypatch.setattr(s, "EXPECTED_GATE", gate["id"])
    monkeypatch.setattr(s, "EXPECTED_KERNEL", "original_kernel")
    return SimpleNamespace(
        root=root,
        source=source,
        freeze=frozen,
        authority=authority,
        freeze_path=frozen_path,
        authority_path=authority_path,
        calls=calls,
    )


def test_prepare_reuses_parent_ids_and_rejects_fake_new_authority(parent, monkeypatch):
    before = p.sha(parent.freeze_path)
    result = s.prepare(parent.root)
    frozen, authority = result["execution_freeze"], result["authority"]
    assert parent.calls == ["code", "cache"] and p.sha(parent.freeze_path) == before
    for key in (
        "material_verification",
        "input_files",
        "material_input_receipt",
        "decoder_configuration",
        "evaluation_registry",
        "base_binding",
        "tokenizer_binding",
        "physical_originals_sha256",
    ):
        assert frozen[key] == parent.freeze[key]
    assert frozen["input_root"] == str(parent.source)
    assert (
        frozen["full_kernel_rebuilds"] == 0
        and frozen["new_full_kernel_identity_measurement_claimed"] is False
    )
    assert authority["source_material_validation_reused"] is True
    assert (
        authority["dropout_correlation_changed"] is True
        and authority["bitwise_equivalence_claimed"] is False
    )
    assert frozen["training_configuration"]["id"] != parent.freeze["training_configuration"]["id"]
    fields = {key: value for key, value in authority.items() if key not in {"id", "schema_version"}}
    fields["trajectory_cache_id"] = "forged_cache"
    path = parent.root / "trajectory/preparation/trajectory_execution_authority.json"
    path.write_bytes(p.encode(p.record("trajectory_execution_authority", **fields)))
    monkeypatch.setattr(x, "run", lambda *_a: pytest.fail("bad lineage reached execution"))
    with pytest.raises(ValueError, match="prospective_fresh_run_authority"):
        s.run(parent.root)
    assert parent.calls == ["code", "cache"]


def test_bad_parent_lineage_fails_before_cache_work(parent):
    fields = {
        key: value for key, value in parent.authority.items() if key not in {"id", "schema_version"}
    }
    fields["original_kernel_id"] = "other_kernel"
    parent.authority_path.write_bytes(p.encode(p.record("fast_execution_authority", **fields)))
    with pytest.raises(ValueError, match="actual_parent_freeze_authority_gate_join"):
        s.prepare(parent.root)
    assert parent.calls == []


def test_worker_reads_parent_authority_and_new_compact_pool_only(tmp_path, monkeypatch):
    source = tmp_path / "parent"
    source.mkdir()
    calls, trajectories = [], object()

    class Authority(dict):
        verification = {"id": "source_verification"}

    authority = Authority(kernel={"id": "original_kernel"}, population={}, registry={}, outcomes=[])
    manifest = p.record("trajectory_material_cache", synthetic=True)
    p.write_once(tmp_path / "cache/manifest.json", manifest)
    cached = dict(
        cache_root="cache",
        manifest=x.descriptor(tmp_path, tmp_path / "cache/manifest.json"),
        manifest_id=manifest["id"],
    )

    def load(root, *_a, **kwargs):
        assert root == source and kwargs["expected_kernel_id"] == "original_kernel"
        calls.append("parent_authority")
        return authority

    def pool(root, observed, selected):
        assert root == tmp_path / "cache" and observed == manifest and selected == "A"
        calls.append("compact_pool")
        return trajectories

    def run(*_a, **kwargs):
        assert kwargs["verified_inputs"] is authority and kwargs["trajectory_cache"] is trajectories
        calls.append("fresh_training")
        return {"actual_complete": True}

    monkeypatch.setattr(x, "verify_code", lambda *_a: None)
    monkeypatch.setattr(x.fast_materials, "load_authority", load)
    monkeypatch.setattr(
        x.fast_materials,
        "load_training_pool",
        lambda *_a, **_k: pytest.fail("original pool reloaded"),
    )
    monkeypatch.setattr(x.trajectory_materials, "load_pool", pool)
    monkeypatch.setattr(x.training, "run", run)
    job = p.record(
        "worker_job",
        job=dict(kind="train", pool="A", arm="plus", seed=11),
        gpu={},
        code_binding={},
        execution_freeze_id="new_execution",
        launched_at="synthetic",
        training_input=dict(
            input_root=str(source),
            trajectory_cache=cached,
            input_files={},
            material_input_receipt={},
            expected_kernel_id="original_kernel",
            expected_material_verification_id="source_verification",
            base_binding={},
            release={"kernel_id": "original_kernel"},
            output_directory="training",
        ),
    )
    path = tmp_path / "jobs/A_train/job.json"
    p.write_once(path, job)
    assert x.worker(tmp_path, path)["actual_complete"] is True
    assert calls == ["parent_authority", "compact_pool", "fresh_training"]


def test_training_report_separates_fused_compute_from_original_material_budget(tmp_path):
    old, actual = budgets(80, 800), budgets(40, 480)
    frozen = dict(
        study_freeze_id="study",
        kernel_id="kernel",
        output_directory="run",
        training_configuration={"id": "trajectory_config"},
        decoder_configuration={"id": "decoder"},
        trajectory_pool_budgets={"A": actual},
        material_verification={"pool_budgets": {"A": old}},
        trajectory_cache={"manifest_id": "cache"},
        physical_originals_sha256="physical",
    )
    job = dict(kind="train", pool="A", arm="plus", seed=11)
    directory = x.job_output(tmp_path, frozen, job)
    directory.mkdir(parents=True)
    adapter_path = directory / "final_adapter.safetensors"
    adapter_path.write_bytes(b"synthetic adapter bytes, not loaded")
    adapter = dict(
        path=adapter_path.name,
        bytes=adapter_path.stat().st_size,
        sha256=p.sha(adapter_path),
        parameter_digest="checkpoint",
    )
    fields = dict(
        **{k: v for k, v in x.binding(frozen).items() if k != "decoder_config_id"},
        pool="A",
        arm="plus",
        seed=11,
        actual_complete=True,
        status="COMPLETE_FINAL_CHECKPOINT",
        optimizer_updates=400,
        epochs_completed=10,
        actual_budget=actual,
        source_material_budget=old,
        trajectory_cache_id="cache",
        physical_originals_sha256="physical",
        updates=[dict(packages=1, rows=1, target_tokens=2, sequence_tokens=12)] * 400,
        final_adapter=adapter,
        final_adapter_restored_identity_verified=True,
        checkpoint_id="checkpoint",
    )
    report = p.record("training_report", **fields)
    path = directory / "report.json"
    p.write_once(path, report)
    assert x._training_report(tmp_path, frozen, job) == report
    fields["source_material_budget"] = actual
    path.write_bytes(p.encode(p.record("training_report", **fields)))
    with pytest.raises(ValueError, match="physical_original_budget"):
        x._training_report(tmp_path, frozen, job)
