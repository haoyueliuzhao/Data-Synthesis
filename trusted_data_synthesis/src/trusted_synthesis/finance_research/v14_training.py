"""Same five-arm experiment after the complete V14 field/state/cache join."""

from pathlib import Path

from .storage import read_json
from .v6_collection import require


def register_exploratory_training(material_binding, output, *, allowed_gpu_indices):
    from .v9_training_launcher import checked_launch, read_bound, register, scale_decision
    from .v14_material import BINDING_SCHEMA

    material_binding, output = Path(material_binding).resolve(), Path(output).resolve()
    require(
        read_json(material_binding).get("schema") == BINDING_SCHEMA,
        "complete genuine V14 material binding required",
    )
    scale, launcher = output / "exploratory_scale/record.json", output / "five_arm_training"
    if not scale.exists():
        scale_decision(
            material_binding,
            scale.parent,
            decision="proceed_exploratory",
            scope_confirmed=True,
            rationale=(
                "Audit-authorized completion of the unchanged 2468-original/744-task kernel. "
                "Append-only representation interpretation, fixed remaining authorities and "
                "state-independent encoding preserve originals and loss. All material complete, "
                "actual D_pi and within-task chi contrast verified; no minimum N, no claimed "
                "power, no partial training, no Student-result selection or loss change."
            ),
        )
    if (launcher / "registration/record.json").exists():
        plan, _, _ = checked_launch(launcher)
    else:
        plan = register(
            material_binding,
            scale,
            launcher,
            allowed_gpu_indices=allowed_gpu_indices,
            minimum_free_mib=24576,
        )
    return dict(
        schema="v14_fixed_material_training_handoff.v1",
        launcher=str(launcher),
        launcher_id=plan["id"],
        scale_decision_id=read_bound(scale)["id"],
        seeds=[11, 29, 47],
        arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
        final_dev_models=15,
        dev_tasks_per_model=883,
        dev_sessions=13245,
        GPU_allocated=False,
        API_calls=0,
        new_scale_approval_required=False,
        test1147_opened=False,
        original_mainline_unchanged=True,
    )
