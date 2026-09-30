"""Prospective continuation conditions and zero-update migration of real prefixes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .calibration import now
from .v6_collection import bound, persist, require
from .v13_material_registration import checked, entry, read_ref


def register_intent(output):
    from .v15_mapping_registration import checked_plan

    output = Path(output).resolve()
    plan = checked_plan(output)
    prefix = checked(output / "prefix_material/binding/record.json")
    require(
        not any((output / "prefix_training" / f"seed{s}").exists() for s in (11, 29, 47)),
        "continuation policy must precede all Student training",
    )
    result = bound(
        dict(
            schema="v15_pre_student_continuation_intent.v1",
            at=now(),
            mapping_plan=entry(output / "registration/record.json"),
            prefix_material_binding=entry(output / "prefix_material/binding/record.json"),
            prefix_pool_id=prefix["id"],
            mapping_plan_id=plan["id"],
            decision="proceed_exploratory_if_complete_nontrivial_material",
            required_fixed_tasks=744,
            required_fixed_packages=2468,
            require_all_originals=True,
            require_all_mapping=True,
            require_D_pi_positive=True,
            require_within_task_chi_contrast=True,
            require_actual_prefix_step=298,
            scope_confirmed=True,
            student_results_used=False,
            statistical_power_claimed=False,
            no_loss_or_score_gate=True,
            no_new_prefix_training=True,
            no_student_started_at_registration=True,
            arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
            seeds=[11, 29, 47],
            feedback_denominator=700,
            dev_tasks=883,
            test_opened=False,
            loss_changed=False,
        )
    )
    persist(output / "continuation_intent", result)
    return result


def validate_condition_realization(record, material_binding, material_identity):
    """Explicit new source contract, not an alias of the old pre-Student schema."""
    binding = checked(material_binding)
    intent = read_ref(record["prospective_intent"])
    require(
        record["schema"] == "v15_prospective_condition_realization.v1"
        and binding["schema"] == "v15_complete_material_binding.v1"
        and intent["schema"] == "v15_pre_student_continuation_intent.v1"
        and intent["decision"] == "proceed_exploratory_if_complete_nontrivial_material"
        and intent["mapping_plan"] == binding["registration"]
        and intent["prefix_material_binding"] == binding["prefix_material_binding"]
        and intent["no_student_started_at_registration"] is True
        and intent["scope_confirmed"] is True
        and record["decision_fixed_before_prefix"] is True
        and record["no_new_research_scale_decision"] is True
        and record["material_identity"] == material_identity
        and record["student_results_used"] is intent["student_results_used"] is False,
        "V15 must realize its original prefix-blind intent on the identical complete material",
    )
    root = Path(binding["material_root"])
    for seed in (11, 29, 47):
        launch = checked(
            root / "prefix_training" / f"seed{seed}/launch_attempts/attempt001/intent/record.json"
        )
        require(
            datetime.fromisoformat(intent["at"]) <= datetime.fromisoformat(launch["at"]),
            "continuation intent was not frozen before actual Student launch",
        )
    return True


def register_and_migrate(output, *, allowed_gpu_indices):
    """Realize a pre-Student rule, not a post-prefix selection using its outcomes."""
    from .v9_training_launcher import checked_launch, file_binding, material_identity, register
    from .v15_material import load_training_pool
    from .v15_prefix_material import load_prefix_pool
    from .v15_prefix_training import checkpoint_ref, latest_checkpoint, migrate_prefix_checkpoint

    output = Path(output).resolve()
    intent = checked(output / "continuation_intent/record.json")
    binding_path = output / "material/binding/record.json"
    prefix_path = output / "prefix_material/binding/record.json"
    require(
        intent["mapping_plan"] == entry(output / "registration/record.json")
        and intent["prefix_material_binding"] == entry(prefix_path)
        and intent["decision"] == "proceed_exploratory_if_complete_nontrivial_material",
        "pre-prefix decision and materials cannot be changed after seeing Student",
    )
    prefix_pool, full_pool = load_prefix_pool(prefix_path), load_training_pool(binding_path)
    identity = material_identity(full_pool)
    scale_root = output / "training/condition_realization"
    scale = bound(
        dict(
            schema="v15_prospective_condition_realization.v1",
            prospective_intent=entry(output / "continuation_intent/record.json"),
            material_binding=file_binding(binding_path),
            material_identity=identity,
            decision="proceed_exploratory",
            conditional_scope_confirmed=True,
            student_results_used=False,
            statistical_power_claimed=False,
            prefix_may_already_have_executed=True,
            decision_fixed_before_prefix=True,
            no_new_research_scale_decision=True,
            no_prefix_loss_or_dev_selection=True,
        )
    )
    persist(scale_root, scale)
    launcher = output / "training/five_arm_training"
    if (launcher / "registration/record.json").exists():
        plan, _, _ = checked_launch(launcher)
    else:
        plan = register(
            binding_path,
            scale_root / "record.json",
            launcher,
            allowed_gpu_indices=allowed_gpu_indices,
            minimum_free_mib=24576,
        )
    migrations = {}
    for seed in (11, 29, 47):
        prefix_result = checked(output / "prefix_training" / f"seed{seed}/result/record.json")
        checkpoint = latest_checkpoint(output / "prefix_training" / f"seed{seed}/shared")
        require(
            checkpoint is not None and checkpoint_ref(checkpoint)["step"] == 298,
            "each actual prefix must reach its unique step298 before continuation",
        )
        receipt_path = output / "prefix_migrations" / f"seed{seed}/record.json"
        if receipt_path.exists():
            receipt = checked(receipt_path)
            require(
                receipt["source_prefix_result_id"] == prefix_result["id"]
                and receipt["migration"]["migrated_checkpoint"]
                == checkpoint_ref(launcher / f"seed{seed}/shared/step0298_step"),
                "saved migration cannot select another prefix or rewrite state",
            )
        else:
            proof = migrate_prefix_checkpoint(
                checkpoint, prefix_pool, full_pool, launcher / f"seed{seed}/shared"
            )
            receipt = bound(
                dict(
                    schema="v15_prefix_migration_receipt.v1",
                    seed=seed,
                    source_prefix_result_id=prefix_result["id"],
                    prospective_intent_id=intent["id"],
                    full_binding=entry(binding_path),
                    launcher_id=plan["id"],
                    migration=proof,
                )
            )
            persist(receipt_path.parent, receipt)
        migrations[str(seed)] = entry(receipt_path)
    result = bound(
        dict(
            schema="v15_original_five_arm_handoff.v1",
            launcher=str(launcher),
            launcher_id=plan["id"],
            condition_realization=entry(scale_root / "record.json"),
            migrations=migrations,
            arms=intent["arms"],
            seeds=intent["seeds"],
            prefix_retrained=False,
            API_calls=0,
            GPU_used=False,
        )
    )
    persist(output / "training_handoff", result)
    return result
