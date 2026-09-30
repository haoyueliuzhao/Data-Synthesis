"""New workflow gates only; no model, device, wallet or production records."""

from types import SimpleNamespace

from trusted_synthesis.finance_research import v10_training, v13_material, v13_workflow


def supervisor(tmp_path, monkeypatch):
    ctl = v13_workflow.Supervisor.__new__(v13_workflow.Supervisor)
    ctl.output = tmp_path
    ctl.root = tmp_path / "workflow"
    ctl.plan = {"id": "synthetic-plan", "protocol_identity": "synthetic-population"}
    ctl.workflow = {"allowed_gpu_indices": [0]}
    ctl.stop, ctl.children, ctl.max_gpu_workers = False, {}, 3
    phases = []
    ctl.update = lambda phase, **values: phases.append((phase, values))
    monkeypatch.setattr(v13_workflow, "checked", lambda path: {"id": "synthetic-result"})
    return ctl, phases


def test_unfinished_measurements_do_not_create_material_or_retry(tmp_path, monkeypatch):
    ctl, phases = supervisor(tmp_path, monkeypatch)
    jobs = []
    ctl.plain_job = lambda job, phase: jobs.append(job) or False
    assert ctl.run() is None
    assert [job["module"] for job in jobs] == ["v13_material_controller"]
    assert not phases
    assert not (tmp_path / "material").exists()


def test_missing_whole_binding_stops_before_any_training_loader(tmp_path, monkeypatch):
    ctl, phases = supervisor(tmp_path, monkeypatch)
    jobs = []
    ctl.plain_job = lambda job, phase: jobs.append(job) or True
    monkeypatch.setattr(v13_material, "load_training_pool", lambda path: 1 / 0)
    assert ctl.run() is None
    assert len(jobs) == 2 and jobs[1]["module"] == "v13_workflow"
    assert phases[-1][0] == "BLOCKED_WHOLE_MATERIAL_SAVED"
    assert phases[-1][1]["no_failed_candidate_dropped"]
    assert not (tmp_path / "training").exists()


def test_equivalent_conditions_are_reported_before_GPU_allocation(tmp_path, monkeypatch):
    from trusted_synthesis.finance_research import v9_training_launcher

    ctl, phases = supervisor(tmp_path, monkeypatch)
    path = tmp_path / "material/binding/record.json"
    path.parent.mkdir(parents=True)
    path.write_text("synthetic marker, never a production binding")
    ctl.plain_job = lambda job, phase: True
    monkeypatch.setattr(v13_material, "load_training_pool", lambda path: SimpleNamespace())
    monkeypatch.setattr(
        v9_training_launcher,
        "material_identity",
        lambda *args, **kwargs: {"capability_profile": {"D_pi": 2, "chi_flexible_tasks": 0}},
    )
    monkeypatch.setattr(v13_workflow, "gpu_inventory", lambda: 1 / 0)
    assert ctl.run() is None
    assert phases[-1][0] == "BLOCKED_ALGEBRAIC_EQUIVALENCE_SAVED"
    assert not (tmp_path / "training").exists()


def test_new_material_dispatch_does_not_masquerade_as_old_schema(monkeypatch):
    monkeypatch.setattr(
        v10_training, "read_json", lambda path: {"schema": "v13_material_binding.v1"}
    )
    marker = object()
    monkeypatch.setattr(v13_material, "load_training_pool", lambda path: marker)
    assert v10_training.load_training_pool("synthetic") is marker


def test_registered_runtime_wallet_entry_is_an_explicit_delegate(monkeypatch):
    from trusted_synthesis.finance_research import (
        v12_review_registration,
        v13_material_registration,
    )

    marker = object()
    monkeypatch.setattr(v12_review_registration, "ledger_for", lambda plan: marker)
    assert v13_material_registration.ledger_for({"synthetic": True}) is marker
