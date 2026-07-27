from trusted_synthesis.domains.legal.operations import legal_operation_registry
from trusted_synthesis.domains.legal.pattern_runtime import LegalTaskPatternRuntime
from trusted_synthesis.domains.legal.patterns import (
    LEGAL_CONDITION_APPLICATION_PATTERN,
    LEGAL_EXCEPTION_APPLICATION_PATTERN,
    LEGAL_RULE_APPLICATION_PATTERN,
    LEGAL_TASK_PATTERNS,
)
from trusted_synthesis.domains.legal.policy import LegalSemanticPolicy
from trusted_synthesis.domains.legal.quality_clauses import LegalQualityClauseProvider
from trusted_synthesis.domains.legal.tasks import LegalTaskPlugin

__all__ = [
    "LegalQualityClauseProvider",
    "LegalSemanticPolicy",
    "LegalTaskPatternRuntime",
    "LegalTaskPlugin",
    "LEGAL_CONDITION_APPLICATION_PATTERN",
    "LEGAL_EXCEPTION_APPLICATION_PATTERN",
    "LEGAL_RULE_APPLICATION_PATTERN",
    "LEGAL_TASK_PATTERNS",
    "legal_operation_registry",
    "legal_counterfactual_registry",
]
from trusted_synthesis.domains.legal.counterfactual import legal_counterfactual_registry
