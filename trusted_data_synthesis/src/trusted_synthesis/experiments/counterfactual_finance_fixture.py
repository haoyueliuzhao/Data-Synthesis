from __future__ import annotations

from datetime import date
from decimal import Decimal

from trusted_synthesis.core.evidence import (
    EpistemicStatus,
    EvidenceKind,
    EvidenceScope,
    ScalarObservation,
    SourceLocator,
    TemporalContext,
)
from trusted_synthesis.core.evidence.schema import (
    EvidenceItem,
    ProvenanceRef,
    SemanticDefinitionRef,
    SourceAuthority,
    SourceRef,
    SubjectRef,
)
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.plugins import DomainPluginSet
from trusted_synthesis.domains.finance.counterfactual import (
    finance_counterfactual_registry,
)
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.quality_clauses import FinanceQualityClauseProvider
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    ContractCase,
)
from trusted_synthesis.experiments.finance_pilot.sampler import TaskBinding
from trusted_synthesis.experiments.finance_pilot.task_factory import build_task_cases
from trusted_synthesis.hashing import canonical_hash


def build_finance_counterfactual_cases(*, count: int) -> tuple[ContractCase, ...]:
    if count < 1:
        raise ValueError("finance counterfactual validation requires at least one case")
    return tuple(_finance_case(index) for index in range(1, count + 1))


def _finance_case(index: int) -> ContractCase:
    variant = (index - 1) % 4
    entity_id = f"FINANCE_FIXTURE_{index:04d}"
    gold: tuple[EvidenceItem, ...]
    if variant == 0:
        gold = (_finance_evidence(index, role="lookup", entity_id=entity_id),)
        task_type = "fact_retrieval"
    elif variant == 1:
        gold = (
            _finance_evidence(
                index,
                role="left",
                entity_id=f"{entity_id}_A",
                value=Decimal(100_000 + index),
            ),
            _finance_evidence(
                index,
                role="right",
                entity_id=f"{entity_id}_B",
                value=Decimal(105_000 + index),
            ),
        )
        task_type = "comparison"
    elif variant == 2:
        gold = (
            _finance_evidence(
                index,
                role="earlier",
                entity_id=entity_id,
                year=2024,
                value=Decimal(90_000 + index),
            ),
            _finance_evidence(
                index,
                role="later",
                entity_id=entity_id,
                year=2025,
                value=Decimal(100_000 + index),
            ),
        )
        task_type = "temporal_growth"
    else:
        gold = tuple(
            _finance_evidence(
                index,
                role=f"series_{year}",
                entity_id=entity_id,
                year=year,
                value=Decimal(80_000 + (year - 2023) * 5_000 + index),
            )
            for year in (2023, 2024, 2025)
        )
        task_type = "temporal_average"
    registry = default_registry()
    counterfactual_registry = finance_counterfactual_registry()
    task_plugin = FinanceTaskPlugin(allow_structured_claims=True)
    binding = TaskBinding(
        task_type=task_type,
        evidence_ids=tuple(item.evidence_id for item in gold),
        stratum=(
            "global",
            "financial_statement",
            "annual",
            "sec",
            "single_source",
        ),
    )
    pilot_case = build_task_cases(
        (binding,),
        gold,
        distractors_per_task=0,
        hard_distractors_per_task=6,
        hard_distractor_types=(
            "wrong_definition",
            "stale_version",
            "forecast",
            "unit_mismatch",
            "currency_mismatch",
            "wrong_scope",
        ),
        task_synthesizer=task_plugin,
    )[0]
    policy = FinanceSemanticPolicy()
    provider = FinanceQualityClauseProvider()
    return ContractCase(
        domain="finance",
        bundle=pilot_case.bundle,
        corpus=pilot_case.corpus,
        proof_graph=pilot_case.proof_graph,
        task=pilot_case.task,
        registry=registry,
        semantic_policy=policy,
        quality_clause_provider=provider,
        plugin_set=DomainPluginSet(
            domain="finance",
            evidence_adapter_id="finance_counterfactual_fixture.v2",
            semantic_policy_id=policy.policy_id,
            task_plugin_ids=(task_plugin.plugin_id,),
            quality_clause_provider_id=provider.provider_id,
            quality_clause_provider_version=provider.provider_version,
            operation_registry_manifest_hash=canonical_hash(
                registry.manifest(), prefix="operation_manifest:"
            ),
            counterfactual_operator_manifest_hash=(counterfactual_registry.manifest_hash),
            versions={"fixture": "2.0.0"},
        ),
        counterfactual_registry=counterfactual_registry,
    )


def _finance_evidence(
    index: int,
    *,
    role: str,
    entity_id: str,
    year: int = 2025,
    value: Decimal | None = None,
) -> EvidenceItem:
    suffix = f"{index:04d}_{role}_{year}"
    return EvidenceItem(
        evidence_id=f"evidence:finance:revenue_{suffix}@kg_counterfactual",
        assertion_id=f"assertion:finance:revenue_{suffix}",
        evidence_version_id=f"version:finance:revenue_{suffix}@kg_counterfactual",
        domain="finance",
        evidence_kind=EvidenceKind.SCALAR,
        subject=SubjectRef(
            subject_id=entity_id,
            name=f"Finance Fixture Company {entity_id}",
            subject_type="company",
            attributes={"market": "US", "country": "US"},
        ),
        predicate="revenue",
        payload=ScalarObservation(
            value=value if value is not None else Decimal(100_000 + index),
            unit="million USD",
            currency="USD",
        ),
        temporal_context=TemporalContext(
            label=f"FY{year}",
            valid_from=date(year - 1, 10, 1),
            valid_to=date(year, 9, 30),
            basis="fiscal_period",
            frequency="annual",
        ),
        scope=EvidenceScope(
            scope_type="consolidated_company",
            scope_id=entity_id,
            label=f"{entity_id} consolidated",
        ),
        source=SourceRef(
            source_id="sec_companyfacts",
            name="SEC Company Facts",
            authority=SourceAuthority.OFFICIAL,
            provider="SEC",
        ),
        source_locator=SourceLocator(
            uri=f"https://data.sec.gov/submissions/{entity_id}.json",
            raw_object_id=f"raw_finance_fixture_{suffix}",
        ),
        definition=SemanticDefinitionRef(
            definition_id="sdef_revenue_gaap",
            text="GAAP revenue reported for the consolidated entity.",
            attributes={"comparability_level": "xbrl_concept_level"},
        ),
        provenance=ProvenanceRef(
            adapter_id="finance_counterfactual_fixture.v2",
            archive_id="finance_kg:kg_counterfactual",
            source_record_id=f"finance_fixture_{suffix}",
            build_ids={
                "kg": "kg_counterfactual",
                "standardized_fact": "fact_build_counterfactual",
            },
        ),
        epistemic_status=EpistemicStatus.OBSERVED,
        extraction_confidence=0.99,
        domain_context={
            "fiscal_year": year,
            "statement_type": "income_statement",
            "is_forecast": False,
        },
    )
