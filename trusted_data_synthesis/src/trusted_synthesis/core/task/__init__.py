from trusted_synthesis.core.task.binding import EvidenceBinding, make_evidence_binding
from trusted_synthesis.core.task.difficulty import TaskDifficultyLevel, TaskDifficultyProfile
from trusted_synthesis.core.task.pattern import (
    EvidenceRoleSpec,
    PatternBindingValidationReport,
    PatternInputKind,
    PatternInputRef,
    ProgramNodeTemplate,
    TaskPatternMaterialization,
    TaskPatternSpec,
)
from trusted_synthesis.core.task.pattern_compiler import (
    TASK_PATTERN_COMPILER_VERSION,
    TaskPatternCompiler,
    TaskPatternInstantiation,
)
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
    "EvidenceBinding",
    "EvidenceRoleSpec",
    "InputRefKind",
    "OperationNode",
    "PatternBindingValidationReport",
    "PatternInputKind",
    "PatternInputRef",
    "ProgramInputRef",
    "ProgramNodeTemplate",
    "ProofGraphTaskSynthesizer",
    "TaskDifficultyLevel",
    "TaskDifficultyProfile",
    "TaskLevel",
    "TaskOracleContract",
    "TaskPackage",
    "TaskPackageBuilder",
    "TaskPatternCompiler",
    "TaskPatternInstantiation",
    "TaskPatternMaterialization",
    "TaskPatternSpec",
    "TASK_PATTERN_COMPILER_VERSION",
    "TaskProgram",
    "TaskPublicSpec",
    "TaskRequirement",
    "TaskSynthesisError",
    "make_evidence_binding",
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
