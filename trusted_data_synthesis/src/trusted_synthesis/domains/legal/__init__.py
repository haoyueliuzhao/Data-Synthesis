from trusted_synthesis.domains.legal.operations import legal_operation_registry
from trusted_synthesis.domains.legal.policy import LegalSemanticPolicy
from trusted_synthesis.domains.legal.quality_clauses import LegalQualityClauseProvider
from trusted_synthesis.domains.legal.tasks import LegalTaskPlugin

__all__ = [
    "LegalQualityClauseProvider",
    "LegalSemanticPolicy",
    "LegalTaskPlugin",
    "legal_operation_registry",
]
