"""Science adapter extension point; no production source is enabled yet."""

from trusted_synthesis.domains.science.operations import science_operation_registry
from trusted_synthesis.domains.science.pattern_runtime import ScienceTaskPatternRuntime
from trusted_synthesis.domains.science.patterns import (
    SCIENCE_DESCRIPTIVE_SYNTHESIS_PATTERN,
    SCIENCE_PROTOCOL_COMPARISON_PATTERN,
    SCIENCE_PROTOCOL_COMPATIBILITY_PATTERN,
    SCIENCE_TASK_PATTERNS,
)
from trusted_synthesis.domains.science.policy import ScienceSemanticPolicy
from trusted_synthesis.domains.science.quality_clauses import ScienceQualityClauseProvider
from trusted_synthesis.domains.science.tasks import ScienceTaskPlugin

__all__ = [
    "ScienceQualityClauseProvider",
    "ScienceSemanticPolicy",
    "ScienceTaskPatternRuntime",
    "ScienceTaskPlugin",
    "SCIENCE_DESCRIPTIVE_SYNTHESIS_PATTERN",
    "SCIENCE_PROTOCOL_COMPARISON_PATTERN",
    "SCIENCE_PROTOCOL_COMPATIBILITY_PATTERN",
    "SCIENCE_TASK_PATTERNS",
    "science_operation_registry",
    "science_counterfactual_registry",
]
from trusted_synthesis.domains.science.counterfactual import science_counterfactual_registry
