"""Fixed-pi CPU comparison and read-only real-material prerequisites.

No real study can be started here. A CPU control has five named synthetic
tasks and a toy tokenizer, not a relaxed version of the 180-task admission.
"""

import argparse
import copy
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import torch

from ..finance_qa_vnext_anchored_vtdo import gradients, state_catalog, state_materials
from ..finance_qa_vnext_basis_scale_preparation import design
from ..finance_qa_vnext_eval_readiness import materials
from ..finance_qa_vnext_task_build.archive import validate_record
from . import integration
from . import protocol as p
from .loss import HierarchicalTrajectoryLoss

MATERIALS = (
    "trusted_data_synthesis/artifacts/qa_vnext_readiness_revision/fixed_AB_20260912_materials"
)


def comparison_plan():
    return p.record(
        "loss_only_comparison_plan",
        parent_commit=p.PARENT_COMMIT,
        audit_sha256=p.AUDIT_SHA256,
        objectives=list(p.OBJECTIVES),
        first_phase_only=True,
        profiles={profile: p.policy(profile) for profile in p.PROFILES},
        availability_profile_is_not_a_hyperparameter_search=True,
        profile_chosen_from_public_material_before_model_outputs=True,
        first_phase_pi="same data-bound fixed distribution for both objectives and all ten epochs",
        original_material_kernel_task_order_seed_optimizer_and_initial_state_shared=True,
        parent_state_catalog_and_all_original_package_proofs_required=True,
        original_full_baseline="existing full-package token mean, never (1,1,1) layer means",
        same_seed_pair=True,
        seeds=[11, 29, 47],
        final_epoch=10,
        adaptive_state_updates_in_loss_isolation=0,
        first_phase_probe_or_feedback_requests=0,
        feedback_log_probability_is_never_hierarchical_loss=True,
        main_metric="CompletePass unchanged",
        independent_tool_final_diagnostics="not yet validated; unsupported verdicts UNKNOWN",
        synthetic_controls_are_effect_estimates=False,
        no_ablation_or_weight_sweep=True,
        parent_real_Qwen_feedback_adapter_validated=False,
        formal_GPU_resource_and_execution_manifest_registered=False,
        actual_financial_comparison_admitted=False,
    )


def _json_tensors(value):
    if isinstance(value, torch.Tensor):
        p.require(
            value.device.type == "cpu"
            and value.layout == torch.strided
            and not value.is_complex()
            and bool(torch.isfinite(value).all()),
            "pair.finite_CPU_tensor_evidence_no_device_transfer",
        )
        return {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "values": value.detach().cpu().tolist(),
        }
    if isinstance(value, dict):
        p.require(len({str(key) for key in value}) == len(value), "pair.distinct_serialized_keys")
        return {str(key): _json_tensors(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_tensors(item) for item in value]
    if isinstance(value, Fraction):
        return str(value)
    return value


def _steps(model, optimizer):
    values = {}
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        step = optimizer.state.get(parameter, {}).get("step", 0)
        value = float(step.item() if isinstance(step, torch.Tensor) else step)
        p.require(value >= 0 and value.is_integer(), "pair.actual_integer_Adam_step")
        values[name] = int(value)
    return values


def _optimizer_ownership(model, optimizer):
    p.require(isinstance(optimizer, torch.optim.AdamW), "pair.actual_AdamW_factory")
    expected = [value for value in model.parameters() if value.requires_grad]
    actual = [value for group in optimizer.param_groups for value in group["params"]]
    p.require(
        len(actual) == len(expected)
        and {id(value) for value in actual} == {id(value) for value in expected},
        "pair.optimizer_owns_exact_condition_parameters",
    )
    _json_tensors(optimizer.state_dict())


def run_fixed_pi_pair_cpu(
    model_factory,
    optimizer_factory,
    *,
    examples,
    batch,
    catalog,
    manifest,
    distribution,
    annotations,
    profile="public_rtf",
    seed=11,
):
    """Ten toy five-task updates per condition, without feedback or new pi.

    All original source objects are privately snapshotted before factories run.
    Successful records include actual parameters/Adam states and consumption,
    not a callback's self-declared success. This is not a production adapter.
    """
    p.require(
        profile in p.PROFILES and type(seed) is int and seed in (11, 29, 47),
        "pair.fixed_profile_and_seed",
    )
    source = copy.deepcopy(
        {
            "examples": examples,
            "batch": batch,
            "catalog": catalog,
            "manifest": manifest,
            "distribution": distribution,
            "annotations": annotations,
        }
    )
    frozen_digest = p.sha(p.encode(source))
    examples, batch, catalog, manifest, distribution, annotations = (
        source[key]
        for key in ("examples", "batch", "catalog", "manifest", "distribution", "annotations")
    )
    state_catalog.validate_catalog(catalog, manifest)
    p.require(
        manifest.get("tokenizer_binding", {}).get("id") == "toy-tokenizer"
        and {row["task_id"] for row in batch["tasks"]} == {*design.DUAL_GROUPS, "c0", "c1"}
        and len(examples) == 64
        and set(annotations) == {row["package_id"] for row in examples},
        "pair.five_task_toy_fixture_not_formal_population",
    )
    pool = examples[0]["pool"]
    state_materials.validate_update(
        examples, batch, pool=pool, catalog=catalog, distribution=distribution
    )
    for objective in p.OBJECTIVES:
        loss = HierarchicalTrajectoryLoss(objective=objective, profile=profile)
        for package in examples:
            annotation = annotations[package["package_id"]]
            p.require(
                annotation["CPU_only"] is True and annotation["synthetic"] is True,
                "pair.synthetic_annotations_only",
            )
            loss.token_coefficients(package, annotation)
    original_rng = torch.random.get_rng_state()
    results = {}
    try:
        generator = torch.Generator(device="cpu")
        generator.manual_seed(seed)
        torch.random.set_rng_state(generator.get_state())
        base_model = model_factory()
        p.require(
            isinstance(base_model, torch.nn.Module)
            and 0 < sum(value.numel() for value in base_model.parameters()) <= 100_000
            and all(value.device.type == "cpu" for value in base_model.parameters())
            and all(value.device.type == "cpu" for value in base_model.buffers()),
            "pair.small_CPU_model_only",
        )
        base_optimizer = optimizer_factory(base_model)
        _optimizer_ownership(base_model, base_optimizer)
        initial_model = _json_tensors(base_model.state_dict())
        initial_optimizer = _json_tensors(base_optimizer.state_dict())
        initial_model_digest = p.sha(p.encode(initial_model))
        initial_optimizer_digest = p.sha(p.encode(initial_optimizer))
        training_rng = torch.random.get_rng_state().clone()
        for objective in p.OBJECTIVES:
            model = copy.deepcopy(base_model)
            torch.random.set_rng_state(training_rng)
            optimizer = optimizer_factory(model)
            _optimizer_ownership(model, optimizer)
            optimizer.load_state_dict(copy.deepcopy(base_optimizer.state_dict()))
            p.require(
                _json_tensors(model.state_dict()) == initial_model
                and _json_tensors(optimizer.state_dict()) == initial_optimizer,
                "pair.exact_common_initial_model_and_Adam",
            )
            loss = HierarchicalTrajectoryLoss(objective=objective, profile=profile)
            torch.random.set_rng_state(training_rng)
            class_result = integration.class_gradients(
                model, examples, loss=loss, annotations=annotations
            )
            p.require(
                _json_tensors(model.state_dict()) == initial_model
                and _json_tensors(optimizer.state_dict()) == initial_optimizer,
                "pair.class_gradient_does_not_train_or_change_Adam",
            )
            torch.random.set_rng_state(training_rng)
            updates, traces = [], []
            for epoch in range(10):
                model.train()
                before = _steps(model, optimizer)
                trace = []

                def observed(event, trace=trace):
                    if event["event"] == "original_row_backward":
                        trace.append((event["package_id"], event["candidate_id"]))

                result = integration.execute_update_cpu(
                    model,
                    optimizer,
                    examples,
                    batch,
                    pool=pool,
                    catalog=catalog,
                    distribution=distribution,
                    loss=loss,
                    annotations=annotations,
                    event_sink=observed,
                )
                after = _steps(model, optimizer)
                p.require(
                    set(after) == set(before)
                    and all(after[name] == before[name] + 1 for name in after),
                    "pair.actual_Adam_step_not_callback_claim",
                )
                expected_trace = [
                    (package["package_id"], row["candidate_id"])
                    for package in examples
                    for row in package["rows"]
                ]
                p.require(trace == expected_trace, "pair.all_original_rows_in_same_order")
                p.require(
                    p.sha(p.encode(source)) == frozen_digest,
                    "pair.fixed_material_pi_annotation_snapshot",
                )
                traces.append(p.sha(p.encode(trace)))
                updates.append(
                    p.record(
                        "fixed_pi_CPU_epoch",
                        epoch=epoch + 1,
                        actual_Adam_steps=after,
                        original_row_sequence_sha256=traces[-1],
                        consumption=result,
                    )
                )
            results[objective] = p.record(
                "fixed_pi_CPU_condition",
                objective=objective,
                loss=loss.describe(),
                initial_model_sha256=initial_model_digest,
                initial_optimizer_sha256=initial_optimizer_digest,
                shared_training_RNG_sha256=gradients.tensor_digest({"rng": training_rng}),
                class_gradients_at_common_initial_point=_json_tensors(class_result["gradients"]),
                class_gradient_evidence=class_result["artifact"],
                updates=updates,
                final_model=_json_tensors(model.state_dict()),
                final_optimizer=_json_tensors(optimizer.state_dict()),
                final_model_is_epoch_10=True,
                pi_sha256=p.sha(p.encode(distribution)),
                original_row_sequence_sha256=traces,
                CPU_control_only=True,
                actual_Qwen_or_financial_utility_run=False,
            )
        first, second = (results[objective] for objective in p.OBJECTIVES)
        for name in (
            "initial_model_sha256",
            "initial_optimizer_sha256",
            "shared_training_RNG_sha256",
            "pi_sha256",
            "original_row_sequence_sha256",
        ):
            p.require(first[name] == second[name], "pair.same_comparison_binding:" + name)
    finally:
        torch.random.set_rng_state(original_rng)
    return p.record(
        "fixed_pi_CPU_pair",
        created_at=p.now(),
        plan_id=comparison_plan()["id"],
        profile=profile,
        seed=seed,
        pool=pool,
        source_snapshot_sha256=frozen_digest,
        materials_manifest_id=manifest["id"],
        state_catalog_id=catalog["id"],
        package_ids=[row["package_id"] for row in examples],
        original_annotations=annotations,
        fixed_pi=distribution,
        initial_model=initial_model,
        initial_optimizer=initial_optimizer,
        conditions=results,
        total_optimizer_steps=20,
        five_task_updates_per_condition=10,
        full_vs_hier_training_loss_values_are_comparable_effect_scores=False,
        same_Probe_material_pi_seed_initial_state_and_order=True,
        feedback_calls=0,
        adaptive_pi_updates=0,
        GPU_operations=0,
        CPU_control_only=True,
        formal_population_or_token_budget_claimed=False,
        actual_Qwen_or_financial_utility_run=False,
    )


def material_preflight(live_root):
    """Read only the sealed training-material manifest; never Student outputs.

    This verifies the exact two metadata files read, not every raw member. It
    can show an input blocker, but cannot admit a model run even if READY.
    """
    root = Path(live_root).resolve()
    folder = root / MATERIALS
    paths = [folder / "manifest.json", folder / "material_manifest.json"]
    p.require(
        all(
            path.is_file() and not any(item.is_symlink() for item in (path, *path.parents))
            for path in paths
        ),
        "preflight.sealed_regular_material_metadata",
    )
    parent_raw, material_raw = (path.read_bytes() for path in paths)
    parent, manifest = json.loads(parent_raw), json.loads(material_raw)
    validate_record(parent, "manifest")
    materials.checked_record(manifest, "fixed_AB_material_manifest")
    members = [row for row in parent["members"] if row["path"] == "material_manifest.json"]
    p.require(
        len(members) == 1
        and members[0]["sha256"] == p.sha(material_raw)
        and members[0]["bytes"] == len(material_raw),
        "preflight.actual_metadata_member_SHA_and_size",
    )
    p.require(
        all(
            path.read_bytes() == original
            for path, original in zip(paths, (parent_raw, material_raw), strict=True)
        ),
        "preflight.metadata_unchanged_during_read",
    )
    selection = manifest["population_selection"]
    ready = manifest["status"] == "FIXED_AB_MATERIALS_READY" and bool(manifest["packages"])
    p.require(
        manifest["status"] in {"FIXED_AB_MATERIALS_READY", "STOP_INSUFFICIENT_COMMON_AB_MATERIALS"},
        "preflight.registered_material_terminal",
    )
    return p.record(
        "material_admission_snapshot",
        observed_at=p.now(),
        source_root=str(root),
        material_directory=MATERIALS,
        parent_manifest_id=parent["id"],
        parent_manifest_sha256=p.sha(parent_raw),
        material_manifest_id=manifest["id"],
        material_manifest_sha256=p.sha(material_raw),
        material_status=manifest["status"],
        selection_status=selection["status"],
        ready_counts=selection.get("ready_counts"),
        selected_task_count=len(selection.get("selected", [])),
        training_package_descriptor_count=len(manifest["packages"]),
        parent_material_metadata_ready=ready,
        status="METADATA_READY_STILL_NOT_ADMITTED" if ready else "BLOCKED_COMMON_MATERIALS",
        full_material_member_sweep_performed=False,
        raw_or_unselected_packages_read_or_selected=False,
        Student_development_or_confirmation_outputs_read=False,
        new_teacher_requests=0,
        source_files_written=0,
        parent_real_Qwen_adapter_validated=False,
        actual_financial_comparison_admitted=False,
    )


def require_real_execution():
    raise ValueError(
        "HIERARCHICAL_REAL_STUDY_NOT_ADMITTED: complete materials, "
        "real Qwen adapter and prospective execution freeze required"
    )


def artifact_target(requested):
    code_root = Path(__file__).resolve().parents[5]
    p.require(Path.cwd().resolve() == code_root, "study.output_only_loaded_new_worktree")
    branch = subprocess.check_output(
        ["git", "symbolic-ref", "--short", "HEAD"], cwd=code_root, text=True
    ).strip()
    p.require(branch == p.BRANCH, "study.output_only_hierarchical_branch")
    target = Path(requested).absolute()
    p.require(
        ".." not in target.parts
        and target == target.resolve()
        and target.is_relative_to(code_root / p.OUTPUT)
        and not any(path.is_symlink() for path in (target, *target.parents)),
        "study.new_branch_artifact_output_only",
    )
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("spec", "material-preflight", "run"))
    parser.add_argument("--live-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.phase == "run":
        require_real_execution()
    if args.phase == "material-preflight":
        p.require(args.live_root is not None, "preflight.explicit_read_only_source_root")
        result = material_preflight(args.live_root)
    else:
        result = comparison_plan()
    if args.output:
        p.write_once(artifact_target(args.output), result)
    print(p.encode(result).decode(), flush=True)


if __name__ == "__main__":
    main()
