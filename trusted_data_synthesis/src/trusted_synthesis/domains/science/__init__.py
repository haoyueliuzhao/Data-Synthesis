"""Science adapter extension point; no production source is enabled yet."""

from trusted_synthesis.domains.science.operations import science_operation_registry
from trusted_synthesis.domains.science.pattern_runtime import ScienceTaskPatternRuntime
from trusted_synthesis.domains.science.patterns import SCIENCE_PROTOCOL_COMPARISON_PATTERN
from trusted_synthesis.domains.science.policy import ScienceSemanticPolicy
from trusted_synthesis.domains.science.quality_clauses import ScienceQualityClauseProvider
from trusted_synthesis.domains.science.tasks import ScienceTaskPlugin

__all__ = [
    "ScienceQualityClauseProvider",
    "ScienceSemanticPolicy",
    "ScienceTaskPatternRuntime",
    "ScienceTaskPlugin",
    "SCIENCE_PROTOCOL_COMPARISON_PATTERN",
    "science_operation_registry",
]
