"""Science adapter extension point; no production source is enabled yet."""

from trusted_synthesis.domains.science.operations import science_operation_registry
from trusted_synthesis.domains.science.policy import ScienceSemanticPolicy
from trusted_synthesis.domains.science.quality_clauses import ScienceQualityClauseProvider
from trusted_synthesis.domains.science.tasks import ScienceTaskPlugin

__all__ = [
    "ScienceQualityClauseProvider",
    "ScienceSemanticPolicy",
    "ScienceTaskPlugin",
    "science_operation_registry",
]
