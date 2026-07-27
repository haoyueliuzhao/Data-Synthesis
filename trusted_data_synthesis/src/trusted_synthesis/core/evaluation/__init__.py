# ruff: noqa: F401 - TYPE_CHECKING imports define the lazy public API.

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from trusted_synthesis.core.evaluation.contracts import (
        ContractQualityAssessment,
        QualityContract,
        QualityContractCompiler,
        QualityContractRuntime,
    )
    from trusted_synthesis.core.evaluation.evaluator import (
        CandidateQualityEvaluator,
        QualityEvaluator,
        ReferenceQualityEvaluator,
    )
    from trusted_synthesis.core.evaluation.quality_vector import (
        QualityDimension,
        QualityDimensionScore,
        QualityVector,
        QualityVectorCompiler,
        QualityVectorPolicy,
    )
    from trusted_synthesis.core.evaluation.schema import (
        DiagnosticQualityVector,
        DimensionScore,
        GateScope,
        HardGateResult,
        QualityAssessment,
        ReleaseDecision,
    )
    from trusted_synthesis.core.evaluation.utility import (
        TrainingCohortManifest,
        TrainingUtilityProtocol,
        TrainingUtilityResult,
        UtilityCohort,
    )

_EXPORTS = {
    "CandidateQualityEvaluator": (
        "trusted_synthesis.core.evaluation.evaluator",
        "CandidateQualityEvaluator",
    ),
    "ContractQualityAssessment": (
        "trusted_synthesis.core.evaluation.contracts",
        "ContractQualityAssessment",
    ),
    "DiagnosticQualityVector": (
        "trusted_synthesis.core.evaluation.schema",
        "DiagnosticQualityVector",
    ),
    "DimensionScore": ("trusted_synthesis.core.evaluation.schema", "DimensionScore"),
    "GateScope": ("trusted_synthesis.core.evaluation.schema", "GateScope"),
    "HardGateResult": ("trusted_synthesis.core.evaluation.schema", "HardGateResult"),
    "QUALITY_VECTOR_VERSION": (
        "trusted_synthesis.core.evaluation.quality_vector",
        "QUALITY_VECTOR_VERSION",
    ),
    "QualityAssessment": (
        "trusted_synthesis.core.evaluation.schema",
        "QualityAssessment",
    ),
    "QualityContract": (
        "trusted_synthesis.core.evaluation.contracts",
        "QualityContract",
    ),
    "QualityContractCompiler": (
        "trusted_synthesis.core.evaluation.contracts",
        "QualityContractCompiler",
    ),
    "QualityContractRuntime": (
        "trusted_synthesis.core.evaluation.contracts",
        "QualityContractRuntime",
    ),
    "QualityDimension": (
        "trusted_synthesis.core.evaluation.quality_vector",
        "QualityDimension",
    ),
    "QualityDimensionScore": (
        "trusted_synthesis.core.evaluation.quality_vector",
        "QualityDimensionScore",
    ),
    "QualityEvaluator": (
        "trusted_synthesis.core.evaluation.evaluator",
        "QualityEvaluator",
    ),
    "QualityVector": (
        "trusted_synthesis.core.evaluation.quality_vector",
        "QualityVector",
    ),
    "QualityVectorCompiler": (
        "trusted_synthesis.core.evaluation.quality_vector",
        "QualityVectorCompiler",
    ),
    "QualityVectorPolicy": (
        "trusted_synthesis.core.evaluation.quality_vector",
        "QualityVectorPolicy",
    ),
    "ReferenceQualityEvaluator": (
        "trusted_synthesis.core.evaluation.evaluator",
        "ReferenceQualityEvaluator",
    ),
    "ReleaseDecision": (
        "trusted_synthesis.core.evaluation.schema",
        "ReleaseDecision",
    ),
    "TRAINING_UTILITY_PROTOCOL_VERSION": (
        "trusted_synthesis.core.evaluation.utility",
        "TRAINING_UTILITY_PROTOCOL_VERSION",
    ),
    "TrainingCohortManifest": (
        "trusted_synthesis.core.evaluation.utility",
        "TrainingCohortManifest",
    ),
    "TrainingUtilityProtocol": (
        "trusted_synthesis.core.evaluation.utility",
        "TrainingUtilityProtocol",
    ),
    "TrainingUtilityResult": (
        "trusted_synthesis.core.evaluation.utility",
        "TrainingUtilityResult",
    ),
    "UtilityCohort": (
        "trusted_synthesis.core.evaluation.utility",
        "UtilityCohort",
    ),
    "make_training_utility_protocol": (
        "trusted_synthesis.core.evaluation.utility",
        "make_training_utility_protocol",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
