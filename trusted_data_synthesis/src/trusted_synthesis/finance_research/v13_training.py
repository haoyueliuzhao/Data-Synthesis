"""Original paired five-arm launcher, only after complete fixed V13 admission."""

from pathlib import Path

from .storage import read_json
from .v6_collection import require


def register_exploratory_training(material_binding, output, *, allowed_gpu_indices):
    from .v9_training_launcher import checked_launch, read_bound, register, scale_decision
    from .v13_material import BINDING_SCHEMA

    material_binding, output = Path(material_binding).resolve(), Path(output).resolve()
    require(
        read_json(material_binding).get("schema") == BINDING_SCHEMA,
        "real complete V13 field-authority binding required; no legacy masquerade",
    )
    scale = output / "exploratory_scale/record.json"
    launcher = output / "five_arm_training"
    if not scale.exists():
        scale_decision(
            material_binding,
            scale.parent,
            decision="proceed_exploratory",
            scope_confirmed=True,
            rationale=(
                "Audit-authorized fixed 2468-original/744-task material, all authority and mapping "
                "complete with genuine nonzero D_pi and within-task chi contrast; true one-package "
                "tasks retained as static with unknown chi. No Student-result selection, arbitrary "
                "minimum N, claimed power, removed difficult package or changed five-arm loss."
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
        schema="v13_fixed_material_training_handoff.v1",
        launcher=str(launcher),
        launcher_id=plan["id"],
        scale_decision_id=read_bound(scale)["id"],
        seeds=[11, 29, 47],
        arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
        final_dev_models=15,
        dev_tasks_per_model=883,
        dev_sessions=13245,
        training_entrypoint="trusted_synthesis.finance_research.v9_training_launcher.run_seed",
        evaluation_entrypoint="trusted_synthesis.finance_research.v9_final_evaluation",
        mechanism_entrypoint="trusted_synthesis.finance_research.v9_mechanism_execution",
        GPU_allocated=False,
        API_calls=0,
        new_scale_approval_required=False,
        test1147_opened=False,
        original_mainline_unchanged=True,
    )
