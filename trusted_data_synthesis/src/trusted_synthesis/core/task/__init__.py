from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
)
from trusted_synthesis.core.task.schema import (
    TaskLevel,
    TaskOracleContract,
    TaskPackage,
    TaskPublicSpec,
    TaskRequirement,
)

__all__ = [
    "InputRefKind",
    "OperationNode",
    "ProgramInputRef",
    "ProofGraphTaskSynthesizer",
    "TaskLevel",
    "TaskPackageBuilder",
    "TaskOracleContract",
    "TaskPackage",
    "TaskProgram",
    "TaskPublicSpec",
    "TaskRequirement",
    "TaskSynthesisError",
]


def __getattr__(name: str):
    if name == "TaskPackageBuilder":
        from trusted_synthesis.core.task.builder import TaskPackageBuilder

        return TaskPackageBuilder
    if name in {"ProofGraphTaskSynthesizer", "TaskSynthesisError"}:
        from trusted_synthesis.core.task.generator import (
            ProofGraphTaskSynthesizer,
            TaskSynthesisError,
        )

        return {
            "ProofGraphTaskSynthesizer": ProofGraphTaskSynthesizer,
            "TaskSynthesisError": TaskSynthesisError,
        }[name]
    raise AttributeError(name)
