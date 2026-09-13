"""A complete fixed-pi toy comparison, never a relaxed real-material study."""

import copy
import json
import os
from pathlib import Path

import pytest
import torch
from test_qa_vnext_anchored_state_catalog import toy_materials as toy_materials
from test_qa_vnext_hierarchical_integration import CountingAdam, Tiny, inputs, unequal_packages

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import training_runtime
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss import study
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss.loss import (
    HierarchicalTrajectoryLoss,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
    record as archive_record,
)


@pytest.fixture(autouse=True)
def CPU_threads():
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


@pytest.fixture(scope="module")
def paired_controls(toy_materials):
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        results = {}
        for profile in p.PROFILES:
            examples, batch, catalog, pi, annotations = inputs(toy_materials, profile)
            before = torch.random.get_rng_state().clone()
            original = copy.deepcopy((examples, batch, catalog, pi, annotations))
            result = study.run_fixed_pi_pair_cpu(
                Tiny,
                CountingAdam,
                examples=examples,
                batch=batch,
                catalog=catalog,
                manifest=toy_materials[1],
                distribution=pi,
                annotations=annotations,
                profile=profile,
                seed=11,
            )
            assert torch.equal(torch.random.get_rng_state(), before)
            assert (examples, batch, catalog, pi, annotations) == original
            results[profile] = result
            destination = os.environ.get("HIERARCHICAL_CPU_EVIDENCE_DIRECTORY")
            if destination:
                target = study.artifact_target(Path(destination) / (profile + ".json"))
                p.write_once(target, result)
        return results
    finally:
        torch.set_num_threads(old)


def test_prospective_design_is_two_losses_with_fixed_pi_and_full_baseline():
    plan = study.comparison_plan()
    assert plan["objectives"] == ["full_token_mean", "hierarchical"]
    assert plan["adaptive_state_updates_in_loss_isolation"] == 0
    assert plan["first_phase_probe_or_feedback_requests"] == 0
    assert plan["actual_financial_comparison_admitted"] is False
    assert plan["profiles"]["public_tf"]["weights"] == {
        "reasoning": "0",
        "tools": "1/2",
        "final": "1/5",
    }


@pytest.mark.parametrize("profile", p.PROFILES)
def test_complete_paired_controls_have_actual_same_inputs_and_Adam_steps(profile, paired_controls):
    result = paired_controls[profile]
    p.checked_record(result, "fixed_pi_CPU_pair")
    assert result["total_optimizer_steps"] == 20
    assert len(result["package_ids"]) == 64
    assert result["CPU_control_only"] and not result["actual_Qwen_or_financial_utility_run"]
    assert (
        result["adaptive_pi_updates"] == result["feedback_calls"] == result["GPU_operations"] == 0
    )
    first, second = (result["conditions"][key] for key in p.OBJECTIVES)
    for name in (
        "initial_model_sha256",
        "initial_optimizer_sha256",
        "shared_training_RNG_sha256",
        "pi_sha256",
        "original_row_sequence_sha256",
    ):
        assert first[name] == second[name]
    for objective, condition in result["conditions"].items():
        assert len(condition["updates"]) == 10
        for epoch, update in enumerate(condition["updates"], 1):
            assert set(update["actual_Adam_steps"].values()) == {epoch}
            consumed = update["consumption"]
            assert consumed["packages_completed"] == 64
            assert consumed["backward_calls"] == 256
            assert (
                consumed["zero_grad_calls"]
                == consumed["clip_calls"]
                == consumed["optimizer_step_calls"]
                == 1
            )
            assert consumed["delegated_unchanged_parent_full_consumer"] is (
                objective == "full_token_mean"
            )
    first_parameters = torch.tensor(first["final_model"]["table"]["values"])
    second_parameters = torch.tensor(second["final_model"]["table"]["values"])
    if profile == "public_rtf":
        # In this inherited toy, all rows within a package have identical
        # logits/labels. The RTF weighted means therefore equal Full in real
        # arithmetic. Roundoff is not a positive algorithm-effect control.
        torch.testing.assert_close(first_parameters, second_parameters, atol=1e-6, rtol=0)
    else:
        # This particular toy isolates the declared 0.7 overall scale, not
        # independent tool/final capability. Adam epsilon makes it observable.
        assert (first_parameters - second_parameters).abs().max().item() > 1e-4


@pytest.mark.parametrize(
    "mutation", ["manifest", "rows", "pi", "annotation", "not_toy", "drop_package"]
)
def test_invalid_source_or_shared_state_stops_before_model_factory(toy_materials, mutation):
    examples, batch, catalog, pi, annotations = inputs(toy_materials)
    manifest = copy.deepcopy(toy_materials[1])
    if mutation == "manifest":
        manifest["status"] = "forged"
    elif mutation == "rows":
        examples[0]["rows"][0]["representation"]["input_ids"][0] = 99
    elif mutation == "pi":
        key = next(iter(pi))
        pi[key][next(iter(pi[key]))] = "3/2"
    elif mutation == "annotation":
        annotations[examples[0]["package_id"]]["profile"] = "public_tf"
    elif mutation == "not_toy":
        fields = {
            key: value for key, value in manifest.items() if key not in {"id", "schema_version"}
        }
        fields["tokenizer_binding"] = {"id": "real_binding"}
        manifest = training_runtime.record("fixed_AB_material_manifest", **fields)
    else:
        examples.pop()

    def forbidden():
        pytest.fail("invalid inputs must not construct a model")

    with pytest.raises(ValueError):
        study.run_fixed_pi_pair_cpu(
            forbidden,
            CountingAdam,
            examples=examples,
            batch=batch,
            catalog=catalog,
            manifest=manifest,
            distribution=pi,
            annotations=annotations,
        )


def material_fixture(tmp_path, *, ready=False):
    folder = tmp_path / study.MATERIALS
    folder.mkdir(parents=True)
    material = training_runtime.record(
        "fixed_AB_material_manifest",
        status="FIXED_AB_MATERIALS_READY" if ready else "STOP_INSUFFICIENT_COMMON_AB_MATERIALS",
        packages=[{"synthetic_metadata_only": True}] if ready else [],
        population_selection={
            "status": "PROSPECTIVE_POPULATION_SELECTED" if ready else "INPUT_INADEQUATE",
            "selected": [],
            "ready_counts": {"control": 43, "annual_flow_components": 0},
        },
    )
    raw = p.encode(material)
    (folder / "material_manifest.json").write_bytes(raw)
    parent = archive_record(
        "manifest",
        members=[{"path": "material_manifest.json", "sha256": p.sha(raw), "bytes": len(raw)}],
    )
    (folder / "manifest.json").write_bytes(p.encode(parent))
    return folder


@pytest.mark.parametrize("ready", [False, True])
def test_metadata_snapshot_never_authorizes_real_model_or_selects_unselected_packages(
    tmp_path, ready
):
    folder = material_fixture(tmp_path, ready=ready)
    original = {path.name: path.read_bytes() for path in folder.iterdir()}
    value = study.material_preflight(tmp_path)
    assert value["parent_material_metadata_ready"] is ready
    assert not value["actual_financial_comparison_admitted"]
    assert not value["Student_development_or_confirmation_outputs_read"]
    assert not value["raw_or_unselected_packages_read_or_selected"]
    assert {path.name: path.read_bytes() for path in folder.iterdir()} == original


@pytest.mark.parametrize("mutation", ["member_bytes", "record_body", "symlink"])
def test_metadata_missing_identity_or_regular_file_blocks(tmp_path, mutation):
    folder = material_fixture(tmp_path)
    path = folder / "material_manifest.json"
    if mutation == "member_bytes":
        path.write_bytes(path.read_bytes() + b"\n")
    elif mutation == "record_body":
        value = json.loads(path.read_bytes())
        value["packages"] = [{"forged": True}]
        raw = p.encode(value)
        path.write_bytes(raw)
        (folder / "manifest.json").write_bytes(
            p.encode(
                archive_record(
                    "manifest",
                    members=[{"path": path.name, "bytes": len(raw), "sha256": p.sha(raw)}],
                )
            )
        )
    else:
        original = tmp_path / "original.json"
        path.rename(original)
        path.symlink_to(original)
    with pytest.raises(ValueError):
        study.material_preflight(tmp_path)


def test_real_execution_hard_gate_cannot_be_opened_by_CPU_results():
    with pytest.raises(ValueError, match="HIERARCHICAL_REAL_STUDY_NOT_ADMITTED"):
        study.require_real_execution()


def test_artifact_path_cannot_escape_with_parent_traversal_or_other_branch(monkeypatch):
    root = Path(study.__file__).resolve().parents[5]
    monkeypatch.chdir(root)
    monkeypatch.setattr(study.subprocess, "check_output", lambda *args, **kwargs: p.BRANCH + "\n")
    assert study.artifact_target(root / p.OUTPUT / "synthetic.json").is_relative_to(root / p.OUTPUT)
    with pytest.raises(ValueError, match="artifact_output_only"):
        study.artifact_target(root / p.OUTPUT / ".." / ".." / "outside.json")
    monkeypatch.setattr(study.subprocess, "check_output", lambda *args, **kwargs: "main\n")
    with pytest.raises(ValueError, match="hierarchical_branch"):
        study.artifact_target(root / p.OUTPUT / "synthetic.json")


def test_artifact_writer_cannot_use_other_worktree_as_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="loaded_new_worktree"):
        study.artifact_target(tmp_path / p.OUTPUT / "synthetic.json")


def test_CPU_pair_never_uses_global_all_device_seed(toy_materials, monkeypatch):
    data = inputs(toy_materials, "public_tf")

    def forbidden(*args, **kwargs):
        pytest.fail("CPU control must not reseed CUDA or other devices")

    monkeypatch.setattr(torch, "manual_seed", forbidden)
    seen = []

    def stop_after_class(model, packages, **kwargs):
        seen.append(torch.random.get_rng_state().clone())
        raise ValueError("synthetic_stop_before_training")

    monkeypatch.setattr(study.integration, "class_gradients", stop_after_class)
    before = torch.random.get_rng_state().clone()
    with pytest.raises(ValueError, match="synthetic_stop_before_training"):
        study.run_fixed_pi_pair_cpu(
            Tiny,
            CountingAdam,
            examples=data[0],
            batch=data[1],
            catalog=data[2],
            manifest=toy_materials[1],
            distribution=data[3],
            annotations=data[4],
            profile="public_tf",
        )
    assert len(seen) == 1 and torch.equal(torch.random.get_rng_state(), before)


def test_non_CPU_optimizer_tensor_rejected_before_serialization_or_training(toy_materials):
    data = inputs(toy_materials, "public_tf")

    def incompatible(model):
        optimizer = CountingAdam(model)
        optimizer.param_groups[0]["unvalidated_tensor"] = torch.empty(1, device="meta")
        return optimizer

    with pytest.raises(ValueError, match="finite_CPU_tensor_evidence"):
        study.run_fixed_pi_pair_cpu(
            Tiny,
            incompatible,
            examples=data[0],
            batch=data[1],
            catalog=data[2],
            manifest=toy_materials[1],
            distribution=data[3],
            annotations=data[4],
            profile="public_tf",
        )


@pytest.mark.parametrize("profile", p.PROFILES)
def test_different_layer_losses_change_gradient_direction_beyond_scalar_rescaling(profile):
    packages, annotations = unequal_packages(profile)
    model = Tiny()
    before = copy.deepcopy(model.state_dict())
    results = {
        objective: study.integration.class_gradients(
            model,
            packages,
            annotations=annotations,
            loss=HierarchicalTrajectoryLoss(objective=objective, profile=profile),
        )
        for objective in p.OBJECTIVES
    }
    full, hierarchical = (
        results[objective]["gradients"]["x"]["z"]["table"].double().flatten()
        for objective in p.OBJECTIVES
    )
    scalar = torch.dot(hierarchical, full) / torch.dot(full, full)
    residual = torch.linalg.vector_norm(hierarchical - scalar * full).item()
    assert residual > 1e-5
    assert all(torch.equal(value, before[name]) for name, value in model.state_dict().items())
    result = p.record(
        "nondegenerate_layer_gradient_CPU_control",
        profile=profile,
        original_packages=packages,
        original_annotations=annotations,
        gradients={key: study._json_tensors(value["gradients"]) for key, value in results.items()},
        gradient_evidence={key: value["artifact"] for key, value in results.items()},
        least_squares_global_scale=scalar.item(),
        residual_beyond_scalar_rescaling=residual,
        CPU_control_only=True,
        actual_Qwen_or_financial_utility_run=False,
        actual_parameter_updates=0,
        GPU_operations=0,
    )
    destination = os.environ.get("HIERARCHICAL_CPU_EVIDENCE_DIRECTORY")
    if destination:
        target = study.artifact_target(
            Path(destination).parent / ("layer_gradient_" + profile + ".json")
        )
        p.write_once(target, result)
