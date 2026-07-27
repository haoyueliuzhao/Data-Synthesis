from __future__ import annotations

from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.plugins import DomainPluginSet
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.counterfactual import (
    finance_counterfactual_registry,
)
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.quality_clauses import FinanceQualityClauseProvider
from trusted_synthesis.domains.finance.source_grounding import (
    FinanceSourceGroundingVerifier,
)
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.hashing import canonical_hash


def finance_plugin_set(
    adapter: FinanceArchiveAdapter,
    registry: OperationRegistry,
    source_grounding_verifier: FinanceSourceGroundingVerifier,
) -> DomainPluginSet:
    return DomainPluginSet(
        domain="finance",
        evidence_adapter_id=adapter.adapter_id,
        semantic_policy_id=FinanceSemanticPolicy.policy_id,
        task_plugin_ids=(FinanceTaskPlugin.plugin_id,),
        verification_plugin_ids=(
            FinanceClaimVerifier.plugin_id,
            source_grounding_verifier.verifier_id,
        ),
        quality_clause_provider_id=FinanceQualityClauseProvider.provider_id,
        quality_clause_provider_version=FinanceQualityClauseProvider.provider_version,
        operation_registry_manifest_hash=canonical_hash(
            registry.manifest(), prefix="operation_manifest:"
        ),
        counterfactual_operator_manifest_hash=(finance_counterfactual_registry().manifest_hash),
        versions={
            "source_grounding": source_grounding_verifier.verifier_version,
            "plugin_set": "1.3.0",
        },
    )
