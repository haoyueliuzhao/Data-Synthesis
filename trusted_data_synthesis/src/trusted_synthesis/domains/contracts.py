"""Backward-compatible exports for plugin contracts now owned by Core."""

from trusted_synthesis.core.plugins import (
    ClaimVerification,
    ClaimVerifierProtocol,
    ComparabilityDecision,
    DomainPluginSet,
    EvidenceAdapterProtocol,
    OperationRegistryProvider,
    SemanticPolicyProtocol,
    SemanticSignature,
    SemanticValidationReport,
    SourceGroundingVerifierProtocol,
)

DomainValidationReport = SemanticValidationReport
DomainEvidenceAdapter = EvidenceAdapterProtocol
DomainSemanticPolicy = SemanticPolicyProtocol
DomainTaskPlugin = OperationRegistryProvider
DomainVerificationPlugin = ClaimVerifierProtocol

__all__ = [
    "ClaimVerification",
    "ComparabilityDecision",
    "DomainEvidenceAdapter",
    "DomainPluginSet",
    "DomainSemanticPolicy",
    "DomainTaskPlugin",
    "DomainValidationReport",
    "DomainVerificationPlugin",
    "SemanticSignature",
    "SourceGroundingVerifierProtocol",
]
