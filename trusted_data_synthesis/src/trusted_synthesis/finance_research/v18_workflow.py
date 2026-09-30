"""Research-source successor reuses the original fifteen-arm mainline with no API stage."""

from pathlib import Path

from . import v16_workflow as shared
from .v6_collection import sha
from .v18_continuation import register_and_migrate
from .v18_material import produce
from .v18_registration import OUTPUT, checked_plan

SOURCES = shared.SOURCES + (
    "v17_material.py",
    "v18_material.py",
    "v18_continuation.py",
    "v18_workflow.py",
    "v18_researcher_authority.py",
)


def source_bindings():
    return {name: sha(Path(__file__).parent / name) for name in SOURCES}


def register_workflow(output=OUTPUT, *, allowed_gpu_indices, max_gpu_workers=8):
    return shared.register_workflow(
        output,
        allowed_gpu_indices=allowed_gpu_indices,
        max_gpu_workers=max_gpu_workers,
        plan_loader=checked_plan,
        source_loader=source_bindings,
        schema="v18_researcher_continuation_workflow.v1",
    )


class Supervisor(shared.Supervisor):
    plan_loader = staticmethod(checked_plan)
    source_loader = staticmethod(source_bindings)
    scope_label = "RESEARCHER_AUTHORITY"
    mainline_schema = "v18_researcher_complete_mainline_result.v1"

    def admission_blocked(self):
        if not (self.output / "admission_hold/record.json").exists():
            return False
        self.update(
            "SEMANTIC_HOLD_PREFIX_UNTOUCHED",
            original_prefix_control_untouched=True,
            no_branch_or_feedback_started=True,
            no_retry=True,
        )
        return True

    def produce_material(self):
        return produce(self.output)

    def migrate(self):
        return register_and_migrate(
            self.output, allowed_gpu_indices=self.workflow["allowed_gpu_indices"]
        )


def main():
    return shared.main(
        default_output=OUTPUT,
        workflow_register=register_workflow,
        supervisor_class=Supervisor,
        material_producer=produce,
        migrator=register_and_migrate,
    )


if __name__ == "__main__":
    main()
