"""Thin three-task successor entrypoint; original prefixes and main matrix are unchanged."""

from pathlib import Path

from . import v16_workflow as shared
from .v6_collection import sha
from .v17_continuation import register_and_migrate
from .v17_material import produce
from .v17_registration import OUTPUT, checked_plan

SOURCES = shared.SOURCES + ("v17_workflow.py", "v17_material.py", "v17_continuation.py")


def source_bindings():
    return {name: sha(Path(__file__).parent / name) for name in SOURCES}


def register_workflow(output=OUTPUT, *, allowed_gpu_indices, max_gpu_workers=8):
    return shared.register_workflow(
        output,
        allowed_gpu_indices=allowed_gpu_indices,
        max_gpu_workers=max_gpu_workers,
        plan_loader=checked_plan,
        source_loader=source_bindings,
        schema="v17_three_task_continuation_workflow.v1",
    )


class Supervisor(shared.Supervisor):
    plan_loader = staticmethod(checked_plan)
    source_loader = staticmethod(source_bindings)
    scope_label = "THREE_TASK"
    mainline_schema = "v17_three_task_complete_mainline_result.v1"

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
