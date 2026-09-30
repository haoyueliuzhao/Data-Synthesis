"""Realize the old prospective intent through an explicitly later six-task source."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .calibration import now
from .v6_collection import bound, persist, require, sha
from .v13_material_registration import checked, entry, read_ref
from .v16_material import BINDING_SCHEMA

SCHEMA = "v16_six_task_condition_realization.v1"
SEEDS = (11, 29, 47)
ARMS = ["Static", "Manual+", "Manual-", "C-only", "Full"]


def validate_lineage(
    binding,
    definition,
    *,
    binding_schema=BINDING_SCHEMA,
    definition_schema="v16_six_task_definition.v1",
    inherited_count=738,
    successor_count=6,
):
    """The old registration remains old; the new one is never backdated."""
    intent = read_ref(definition["prospective_intent"])
    source = Path(definition["source_root"])
    require(
        binding["schema"] == binding_schema
        and definition["schema"] == definition_schema
        and binding["original_registration"]
        == definition["source_registration"]
        == intent["mapping_plan"]
        and binding["prefix_material_binding"]
        == definition["prefix_material_binding"]
        == intent["prefix_material_binding"]
        and binding["prospective_intent"] == definition["prospective_intent"]
        and binding["inherited_mapping_authorities"] == definition["inherited_mapping_authorities"]
        and binding["previous_failed_authorities"] == definition["previous_failed_authorities"]
        and binding["successor_task_ids"] == definition["fixed_unresolved_task_ids"]
        and len(binding["inherited_mapping_authorities"]) == inherited_count
        and len(binding["successor_task_ids"]) == successor_count
        and intent["schema"] == "v15_pre_student_continuation_intent.v1"
        and intent["decision"] == "proceed_exploratory_if_complete_nontrivial_material"
        and intent["no_student_started_at_registration"] is True
        and intent["scope_confirmed"] is True
        and intent["student_results_used"] is definition["student_results_used"] is False
        and intent["arms"] == binding["fixed_arms"] == ARMS
        and intent["seeds"] == binding["fixed_seeds"] == list(SEEDS)
        and intent["require_actual_prefix_step"] == 298
        and intent["feedback_denominator"] == binding["feedback_denominator"] == 700
        and intent["dev_tasks"] == 883,
        "fixed successor inheritance must preserve the prospective choice and prior authorities",
    )
    original_at, successor_at = (
        datetime.fromisoformat(intent["at"]),
        datetime.fromisoformat(definition["at"]),
    )
    for seed in SEEDS:
        launch = checked(
            source / "prefix_training" / f"seed{seed}/launch_attempts/attempt001/intent/record.json"
        )
        launched_at = datetime.fromisoformat(launch["at"])
        require(
            original_at <= launched_at < successor_at,
            "original intent must precede each prefix; successor source must honestly follow it",
        )
    return intent


def validate_condition_realization(
    record, material_binding, material_identity, *, schema=SCHEMA, lineage_validator=None
):
    binding = checked(material_binding)
    definition = read_ref(binding["definition"])
    (lineage_validator or validate_lineage)(binding, definition)
    require(
        record["schema"] == schema
        and record["prospective_intent"] == definition["prospective_intent"]
        and record["successor_registration"] == binding["registration"]
        and record["original_registration"] == definition["source_registration"]
        and record["material_identity"] == material_identity
        and record["decision_fixed_before_prefix"] is True
        and record["new_source_registered_after_prefix_start"] is True
        and record["no_new_research_scale_decision"] is True
        and record["student_results_used"] is False,
        "successor realizes the original condition; it is not a new post-result scale choice",
    )
    return True


def completed_prefixes(definition):
    """Cheap durable metadata gate before any tensor is opened for migration."""
    from .v15_prefix_training import checkpoint_ref, latest_checkpoint

    source, result = Path(definition["source_root"]), {}
    for seed in SEEDS:
        root = source / "prefix_training" / f"seed{seed}"
        finished = checked(root / "result/record.json")
        checkpoint = latest_checkpoint(root / "shared")
        require(
            checkpoint is not None
            and checkpoint_ref(checkpoint)["step"] == 298
            and finished["schema"] == "v15_prior_prefix_seed_result.v1"
            and finished["seed"] == seed
            and finished["complete_prefix"] is True
            and finished["checkpoint"] == checkpoint_ref(checkpoint)
            and finished["actual"]["committed_step"]
            == finished["actual"]["consumption"]["updates"]
            == 298,
            "all three actual committed step298 prefixes required before zero-update migration",
        )
        result[seed] = dict(result=finished, checkpoint=checkpoint)
    return result


def register_and_migrate(
    output,
    *,
    allowed_gpu_indices,
    lineage_validator=None,
    prefix_loader=None,
    pool_loader=None,
    schema=SCHEMA,
    receipt_schema="v16_prefix_migration_receipt.v1",
    handoff_schema="v16_original_five_arm_handoff.v1",
):
    from .v9_training_launcher import checked_launch, file_binding, material_identity, register
    from .v15_prefix_training import checkpoint_ref, migrate_prefix_checkpoint
    from .v16_material import load_historical_prefix, load_training_pool

    output = Path(output).resolve()
    binding_path = output / "material/binding/record.json"
    binding = checked(binding_path)
    definition = read_ref(binding["definition"])
    intent = (lineage_validator or validate_lineage)(binding, definition)
    prefixes = completed_prefixes(definition)
    prefix_pool, full_pool = (
        (prefix_loader or load_historical_prefix)(definition),
        (pool_loader or load_training_pool)(binding_path),
    )
    identity = material_identity(full_pool)
    scale_root = output / "training/condition_realization"
    scale = bound(
        dict(
            schema=schema,
            prospective_intent=definition["prospective_intent"],
            successor_registration=binding["registration"],
            original_registration=definition["source_registration"],
            material_binding=file_binding(binding_path),
            material_identity=identity,
            decision="proceed_exploratory",
            conditional_scope_confirmed=True,
            student_results_used=False,
            statistical_power_claimed=False,
            prefix_may_already_have_executed=True,
            decision_fixed_before_prefix=True,
            new_source_registered_after_prefix_start=True,
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
    # The original mechanism registrar rejects any launcher state.pt. Freeze the
    # unchanged mechanism contract before adding even a zero-update shared state.
    from .v9_mechanism_execution import register as register_mechanisms

    original_workflow_path = Path(definition["source_root"]) / "workflow/registration/record.json"
    original_workflow = checked(original_workflow_path)
    original_mechanism_sha = original_workflow["source_bindings"]["v9_mechanism_execution.py"]
    require(
        original_workflow["continuation_intent_id"] == intent["id"]
        and sha(Path(__file__).parent / "v9_mechanism_execution.py") == original_mechanism_sha,
        "original pre-prefix mechanism implementation choices must remain byte-identical",
    )
    mechanism_root = output / "mechanisms"
    if not (mechanism_root / "registration/record.json").exists():
        register_mechanisms(launcher, mechanism_root)
    persist(
        output / "training/mechanism_lineage",
        bound(
            dict(
                schema="fixed_mechanism_prefix_handoff.v1",
                prospective_intent=definition["prospective_intent"],
                original_registration=definition["source_registration"],
                launcher_id=plan["id"],
                original_pre_prefix_workflow=entry(original_workflow_path),
                original_mechanism_source_sha256=original_mechanism_sha,
                mechanism_registration=entry(mechanism_root / "registration/record.json"),
                choices_source="original_registered_five_arm_mainline",
                choices_changed_after_Student=False,
                Student_results_used=False,
                registration_precedes_any_launcher_checkpoint=True,
            )
        ),
    )
    migrations = {}
    for seed in SEEDS:
        prefix_result, checkpoint = prefixes[seed]["result"], prefixes[seed]["checkpoint"]
        receipt_path = output / "prefix_migrations" / f"seed{seed}/record.json"
        if receipt_path.exists():
            receipt = checked(receipt_path)
            require(
                receipt["source_prefix_result_id"] == prefix_result["id"]
                and receipt["full_binding"] == entry(binding_path)
                and receipt["prospective_intent_id"] == intent["id"]
                and receipt["launcher_id"] == plan["id"]
                and receipt["migration"]["source_prefix"] == checkpoint_ref(checkpoint)
                and receipt["migration"]["migrated_checkpoint"]
                == checkpoint_ref(launcher / f"seed{seed}/shared/step0298_step"),
                "existing migration cannot select another prefix or rewrite state",
            )
        else:
            proof = migrate_prefix_checkpoint(
                checkpoint, prefix_pool, full_pool, launcher / f"seed{seed}/shared"
            )
            receipt = bound(
                dict(
                    schema=receipt_schema,
                    at=now(),
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
            schema=handoff_schema,
            launcher=str(launcher),
            launcher_id=plan["id"],
            condition_realization=entry(scale_root / "record.json"),
            migrations=migrations,
            arms=ARMS,
            seeds=list(SEEDS),
            prefix_retrained=False,
            optimizer_steps_during_migration=0,
            first_formal_outer_required_before_C_or_Full_step299=True,
            dev_tasks_per_model=883,
            final_dev_models=15,
            dev_sessions=13245,
            API_calls=0,
            GPU_used=False,
        )
    )
    persist(output / "training_handoff", result)
    return result
