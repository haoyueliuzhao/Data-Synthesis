"""Schema dispatch and automatic pre-Student handoff; no GPU/API allocation."""

import json
from pathlib import Path

import pytest

from trusted_synthesis.finance_research import v9_conditional_training as old
from trusted_synthesis.finance_research import v9_training_launcher as launcher
from trusted_synthesis.finance_research import v10_material as material
from trusted_synthesis.finance_research import v10_training as training


def test_binding_schema_dispatch_never_impersonates_old_mask_or_validator(tmp_path, monkeypatch):
    path = tmp_path / "binding.json"
    monkeypatch.setattr(material, "load_training_pool", lambda p: ("v10", Path(p)))
    monkeypatch.setattr(old, "load_training_pool", lambda p: ("v9", Path(p)))
    path.write_text(json.dumps({"schema": material.BINDING_SCHEMA}))
    assert training.load_training_pool(path) == ("v10", path)
    assert launcher.load_training_pool(path) == ("v10", path)
    path.write_text(json.dumps({"schema": "v9_conditional_training_binding.v1"}))
    assert training.load_training_pool(path) == ("v9", path)
    path.write_text(json.dumps({"schema": "v10_candidate_self_report_ready"}))
    with pytest.raises(ValueError, match="unknown real material"):
        training.load_training_pool(path)


def test_handoff_reuses_actual_profile_scale_rule_and_original_launcher(tmp_path, monkeypatch):
    path = tmp_path / "binding.json"
    path.write_text(json.dumps({"schema": material.BINDING_SCHEMA}))
    events = []

    def scale(binding, output, **kwargs):
        assert kwargs["decision"] == "proceed_exploratory" and kwargs["scope_confirmed"] is True
        assert "no arbitrary minimum N" in kwargs["rationale"]
        events.append("scale")
        Path(output).mkdir(parents=True)
        (Path(output) / "record.json").write_text(
            json.dumps(launcher.bound({"scope": "synthetic verified profile"}))
        )

    def register(binding, scale_path, root, **kwargs):
        events.append("register")
        assert kwargs == {"allowed_gpu_indices": (5, 7), "minimum_free_mib": 20000}
        assert Path(scale_path).is_file()
        return {"id": "original-five-arm-entrypoint"}

    monkeypatch.setattr(launcher, "scale_decision", scale)
    monkeypatch.setattr(launcher, "register", register)
    monkeypatch.setattr(
        launcher, "gpu_inventory", lambda: pytest.fail("no reservation before training")
    )
    monkeypatch.setattr(
        launcher, "load_student", lambda *a, **k: pytest.fail("no model load during registration")
    )
    result = training.register_exploratory_training(
        path, tmp_path / "handoff", allowed_gpu_indices=(5, 7), minimum_free_mib=20000
    )
    assert events == ["scale", "register"]
    assert result["seeds"] == [11, 29, 47] and len(result["arms"]) == 5
    assert result["dev_sessions"] == 13245 and result["dev_tasks_per_model"] == 883
    assert result["training_entrypoint"].endswith(".run_seed")
    assert result["API_calls"] == 0 and result["GPU_allocated"] is False
    assert result["new_scale_approval_required"] is False


def test_material_failure_stops_handoff_before_launcher_or_resource_use(tmp_path, monkeypatch):
    path = tmp_path / "binding.json"
    path.write_text(json.dumps({"schema": material.BINDING_SCHEMA}))
    monkeypatch.setattr(
        launcher,
        "scale_decision",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("unresolved material")),
    )
    monkeypatch.setattr(
        launcher, "register", lambda *a, **k: pytest.fail("no launch on partial material")
    )
    with pytest.raises(ValueError, match="unresolved material"):
        training.register_exploratory_training(path, tmp_path / "out", allowed_gpu_indices=(0,))


def test_actual_step_report_names_the_real_new_supervision_without_changing_optimizer(tmp_path):
    from test_finance_v8_training_driver import driver, pool

    from trusted_synthesis.finance_research.providers import parameter_digest

    toy = pool()  # Explicit CPU-only synthetic material, never real production admission.
    toy.material_schema = material.BINDING_SCHEMA
    toy._manifest.registration.validator_binding_id = "v10_real_AB_A_mask_once_semantic_mapping.v1"
    run = driver(tmp_path / "v10-real-tiny-step", material=toy)
    before = parameter_digest(run.parameters)
    report = run.step()
    assert parameter_digest(run.parameters) != before
    assert report["schema_version"] == "v10_actual_task_batch_update.v1"
    assert report["supervision_policy"] == "v10_single_authority_original_spans.v1"
    assert report["execution_design"] == "original_unfused_response_rows_v10"
    assert report["id"].startswith("v10_task_batch_update:")
    assert report["optimizer_step_calls"] == report["clip_calls"] == 1
    assert report["additional_batch_division"] is False and report["CPU_control_only"] is True
