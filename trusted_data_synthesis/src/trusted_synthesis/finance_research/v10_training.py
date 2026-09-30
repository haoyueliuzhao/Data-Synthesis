"""V10 loader dispatch and the authorized fixed exploratory launcher handoff.

Optimizer, five arms, three seeds, task scheduling and real700 feedback are the
existing implementations. Registration allocates no GPU and launches no API.
"""

from pathlib import Path

from .storage import read_json
from .v10_material import BINDING_SCHEMA


def load_training_pool(binding_path):
    schema = read_json(binding_path).get("schema")
    if schema == "v13_material_binding.v1":
        from .v13_material import load_training_pool as load_v13

        return load_v13(binding_path)
    if schema == BINDING_SCHEMA:
        from .v10_material import load_training_pool as load_v10

        return load_v10(binding_path)
    if schema == "v9_conditional_training_binding.v1":
        from .v9_conditional_training import load_training_pool as load_v9

        return load_v9(binding_path)
    raise ValueError("unknown real material binding; no fake V8 compatibility adapter")


def register_exploratory_training(
    material_binding, output, *, allowed_gpu_indices, minimum_free_mib=24576
):
    """Prospective audit-approved rule, not a fresh user scale approval gate.

    Only an already fully verified, nondegenerate V10 kernel can reach the common
    launcher. That launcher retains the actual-profile scale record, original
    Qwen fresh adapters, unchanged Adam and GPU headroom lock. No resource is held
    here. The supervisor calls its normal train/resume/evaluation entrypoints.
    """
    from .v9_training_launcher import read_bound, register, scale_decision

    material_binding, output = Path(material_binding).resolve(), Path(output).resolve()
    if read_json(material_binding).get("schema") != BINDING_SCHEMA:
        raise ValueError("automatic audit rule is specific to new V10 material")
    scale_path = output / "exploratory_scale/record.json"
    launch_root = output / "five_arm_training"
    if not scale_path.exists():
        scale_decision(
            material_binding,
            scale_path.parent,
            decision="proceed_exploratory",
            rationale=(
                "Prospectively authorized new-batch rule: complete genuine shared material, "
                "D_pi>0 and within-task chi0/1 support; no arbitrary minimum N, "
                "no statistical-power claim or Student-result selection."
            ),
            scope_confirmed=True,
        )
    if (launch_root / "registration/record.json").exists():
        from .v9_training_launcher import checked_launch

        plan, _, _ = checked_launch(launch_root)
    else:
        plan = register(
            material_binding,
            scale_path,
            launch_root,
            allowed_gpu_indices=allowed_gpu_indices,
            minimum_free_mib=minimum_free_mib,
        )
    return dict(
        schema="v10_exploratory_training_handoff.v1",
        launcher=str(launch_root),
        launcher_id=plan["id"],
        scale_decision_id=read_bound(scale_path)["id"],
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
    )
