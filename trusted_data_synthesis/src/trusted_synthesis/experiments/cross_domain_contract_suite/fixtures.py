from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from trusted_synthesis.core.evaluation.counterfactual import (
    CounterfactualOperatorRegistry,
)
from trusted_synthesis.core.evidence import (
    EpistemicStatus,
    EvidenceKind,
    EvidenceScope,
    ExperimentalResult,
    RuleStatement,
    SourceLocator,
    TemporalContext,
    UncertaintyInterval,
)
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import (
    EvidenceBundle,
    EvidenceItem,
    ProvenanceRef,
    SemanticDefinitionRef,
    SourceAuthority,
    SourceRef,
    SubjectRef,
)
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.plugins import (
    DomainPluginSet,
    DomainQualityClauseProviderProtocol,
    SemanticPolicyProtocol,
)
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.domains.legal import (
    LegalQualityClauseProvider,
    LegalSemanticPolicy,
    LegalTaskPlugin,
    legal_counterfactual_registry,
    legal_operation_registry,
)
from trusted_synthesis.domains.science import (
    ScienceQualityClauseProvider,
    ScienceSemanticPolicy,
    ScienceTaskPlugin,
    science_counterfactual_registry,
    science_operation_registry,
)
from trusted_synthesis.hashing import canonical_hash


@dataclass(frozen=True)
class ContractCase:
    domain: str
    bundle: EvidenceBundle
    corpus: EvidenceCorpus
    proof_graph: ProofGraph
    task: TaskPackage
    registry: OperationRegistry
    semantic_policy: SemanticPolicyProtocol
    quality_clause_provider: DomainQualityClauseProviderProtocol
    plugin_set: DomainPluginSet
    counterfactual_registry: CounterfactualOperatorRegistry


def build_contract_cases() -> tuple[ContractCase, ...]:
    return (_legal_case(), _science_case())


def build_pattern_validation_cases(*, per_domain: int = 10) -> tuple[ContractCase, ...]:
    if per_domain < 1:
        raise ValueError("pattern validation requires at least one case per domain")
    return tuple(_legal_case(index) for index in range(1, per_domain + 1)) + tuple(
        _science_case(index) for index in range(1, per_domain + 1)
    )


def fixture_manifest_hash(cases: tuple[ContractCase, ...]) -> str:
    return canonical_hash(
        {
            case.domain: {
                "bundle_hash": case.bundle.bundle_hash,
                "corpus_ids": tuple(item.evidence_version_id for item in case.corpus.evidence),
                "task_hash": case.task.task_hash,
                "operation_manifest": case.registry.manifest(),
                "plugin_set": case.plugin_set.model_dump(mode="json"),
            }
            for case in cases
        },
        prefix="cross_domain_fixture_manifest:",
    )


def _legal_case(index: int | None = None) -> ContractCase:
    suffix = "" if index is None else f"_{index:02d}"
    rules = (
        _legal_rule(f"guidance{suffix}", "Agency Guidance", "administrative filing"),
        _legal_rule(f"statute{suffix}", "Example Act", "statutory filing"),
    )
    distractors = (
        _legal_rule(
            f"wrong_definition{suffix}",
            "Other Act",
            "unrelated filing",
            definition="other",
        ),
        _legal_rule(
            f"wrong_scope{suffix}",
            "Local Rule",
            "local filing",
            scope_id="other_jdx",
        ),
        _legal_rule(f"wrong_time{suffix}", "Expired Act", "expired filing", year=2024),
    )
    bundle = _bundle("legal", rules, case_key=suffix or "base")
    corpus = _corpus("legal", (*rules, *distractors), case_key=suffix or "base")
    graph = ProofGraphBuilder().build(bundle)
    registry = legal_operation_registry()
    counterfactual_registry = legal_counterfactual_registry()
    plugin = LegalTaskPlugin()
    policy = LegalSemanticPolicy()
    task = plugin.rule_application(
        graph,
        bundle,
        rules,
        satisfied_conditions=("threshold exceeded",),
        present_exceptions=(),
        authority_priority=("Example Act", "Agency Guidance"),
    )
    return ContractCase(
        domain="legal",
        bundle=bundle,
        corpus=corpus,
        proof_graph=graph,
        task=task,
        registry=registry,
        semantic_policy=policy,
        quality_clause_provider=LegalQualityClauseProvider(),
        plugin_set=DomainPluginSet(
            domain="legal",
            evidence_adapter_id="legal_contract_fixture.v1",
            semantic_policy_id=policy.policy_id,
            task_plugin_ids=(plugin.plugin_id,),
            quality_clause_provider_id=LegalQualityClauseProvider.provider_id,
            quality_clause_provider_version=LegalQualityClauseProvider.provider_version,
            operation_registry_manifest_hash=canonical_hash(
                registry.manifest(), prefix="operation_manifest:"
            ),
            counterfactual_operator_manifest_hash=(
                counterfactual_registry.manifest_hash
            ),
            versions={"fixture": "1.3.0"},
        ),
        counterfactual_registry=counterfactual_registry,
    )


def _science_case(index: int | None = None) -> ContractCase:
    suffix = "" if index is None else f"_{index:02d}"
    results = (
        _science_result(f"method_a{suffix}", "10.2", "9.7", "10.7"),
        _science_result(f"method_b{suffix}", "11.0", "10.4", "11.6"),
    )
    distractors = (
        _science_result(
            f"wrong_definition{suffix}",
            "12.0",
            "11.5",
            "12.5",
            definition="other",
        ),
        _science_result(
            f"wrong_scope{suffix}",
            "8.0",
            "7.5",
            "8.5",
            scope_id="other_dataset",
        ),
        _science_result(f"wrong_time{suffix}", "9.0", "8.5", "9.5", year=2024),
    )
    bundle = _bundle("science", results, case_key=suffix or "base")
    corpus = _corpus("science", (*results, *distractors), case_key=suffix or "base")
    graph = ProofGraphBuilder().build(bundle)
    registry = science_operation_registry()
    counterfactual_registry = science_counterfactual_registry()
    plugin = ScienceTaskPlugin()
    policy = ScienceSemanticPolicy()
    task = plugin.compare_experiments(graph, bundle, *results)
    return ContractCase(
        domain="science",
        bundle=bundle,
        corpus=corpus,
        proof_graph=graph,
        task=task,
        registry=registry,
        semantic_policy=policy,
        quality_clause_provider=ScienceQualityClauseProvider(),
        plugin_set=DomainPluginSet(
            domain="science",
            evidence_adapter_id="science_contract_fixture.v1",
            semantic_policy_id=policy.policy_id,
            task_plugin_ids=(plugin.plugin_id,),
            quality_clause_provider_id=ScienceQualityClauseProvider.provider_id,
            quality_clause_provider_version=ScienceQualityClauseProvider.provider_version,
            operation_registry_manifest_hash=canonical_hash(
                registry.manifest(), prefix="operation_manifest:"
            ),
            counterfactual_operator_manifest_hash=(
                counterfactual_registry.manifest_hash
            ),
            versions={"fixture": "1.3.0"},
        ),
        counterfactual_registry=counterfactual_registry,
    )


def _bundle(
    domain: str,
    evidence: tuple[EvidenceItem, ...],
    *,
    case_key: str = "base",
) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=f"bundle:{domain}:complex_contract:{case_key}",
        evidence=evidence,
        purpose=f"{domain} non-lookup reasoning contract",
        graph_build_id=f"{domain}_contract_build",
    )


def _corpus(
    domain: str,
    evidence: tuple[EvidenceItem, ...],
    *,
    case_key: str = "base",
) -> EvidenceCorpus:
    return EvidenceCorpus(
        corpus_id=f"corpus:{domain}:contract_with_distractors:{case_key}",
        evidence=evidence,
        build_id=f"{domain}_contract_build",
    )


def _legal_rule(
    key: str,
    authority: str,
    effect: str,
    *,
    definition: str = "filing_requirement",
    scope_id: str = "example_jdx",
    year: int = 2025,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"evidence:legal:{key}@v1",
        assertion_id=f"assertion:legal:{key}",
        evidence_version_id=f"version:legal:{key}@v1",
        domain="legal",
        evidence_kind=EvidenceKind.RULE,
        subject=SubjectRef(
            subject_id="filing_case", name="Example filing case", subject_type="legal_matter"
        ),
        predicate="filing_requirement",
        payload=RuleStatement(
            rule_text="A filing is required when the threshold is exceeded.",
            conditions=("threshold exceeded",),
            exceptions=("registered exemption",),
            authority=authority,
            legal_effect=effect,
        ),
        temporal_context=TemporalContext(label=f"effective {year}", valid_to=date(year, 1, 1)),
        scope=EvidenceScope(scope_type="legal_system", scope_id=scope_id),
        source=SourceRef(
            source_id=f"legal_source_{key}",
            name=authority,
            authority=SourceAuthority.PRIMARY,
        ),
        source_locator=SourceLocator(uri=f"https://example.org/law/{key}", text_span="section 10"),
        definition=SemanticDefinitionRef(definition_id=f"legal_definition:{definition}"),
        provenance=ProvenanceRef(
            adapter_id="legal_contract.v1",
            archive_id="legal_contract_archive",
            source_record_id=key,
            build_ids={"evidence": "legal_contract_build"},
        ),
        epistemic_status=EpistemicStatus.OBSERVED,
        extraction_confidence=1,
    )


def _science_result(
    key: str,
    value: str,
    lower: str,
    upper: str,
    *,
    definition: str = "accuracy_gain",
    scope_id: str = "held_out_dataset",
    year: int = 2025,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"evidence:science:{key}@v1",
        assertion_id=f"assertion:science:{key}",
        evidence_version_id=f"version:science:{key}@v1",
        domain="science",
        evidence_kind=EvidenceKind.EXPERIMENTAL_RESULT,
        subject=SubjectRef(subject_id=key, name=key, subject_type="experimental_method"),
        predicate="treatment_effect",
        payload=ExperimentalResult(
            metric="accuracy_gain",
            value=Decimal(value),
            unit="percentage_point",
            dataset="held_out_dataset",
            method="randomized_controlled_protocol",
            comparator="shared_baseline",
            uncertainty=UncertaintyInterval(
                lower=Decimal(lower), upper=Decimal(upper), confidence_level=0.95
            ),
            sample_size=500,
            protocol={"seed_policy": "fixed", "evaluation_split": "held_out"},
        ),
        temporal_context=TemporalContext(
            label=f"study version {year}", observed_at=date(year, 2, 1)
        ),
        scope=EvidenceScope(scope_type="study_population", scope_id=scope_id),
        source=SourceRef(
            source_id=f"paper_{key}",
            name=f"Peer-reviewed study {key}",
            authority=SourceAuthority.PEER_REVIEWED,
        ),
        source_locator=SourceLocator(uri=f"https://example.org/papers/{key}", text_span="table 2"),
        definition=SemanticDefinitionRef(definition_id=f"science_definition:{definition}"),
        provenance=ProvenanceRef(
            adapter_id="science_contract.v1",
            archive_id="science_contract_archive",
            source_record_id=key,
            build_ids={"evidence": "science_contract_build"},
        ),
        epistemic_status=EpistemicStatus.OBSERVED,
        extraction_confidence=1,
    )
