from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal

from trusted_synthesis.core.evaluation.evaluator import ReferenceQualityEvaluator
from trusted_synthesis.core.evaluation.schema import GateScope, ReleaseDecision
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
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.core.trajectory.verifier import ReferenceWorkflowVerifier
from trusted_synthesis.domains.legal import (
    LegalSemanticPolicy,
    LegalTaskPlugin,
    legal_operation_registry,
)
from trusted_synthesis.domains.science import (
    ScienceSemanticPolicy,
    ScienceTaskPlugin,
    science_operation_registry,
)


def test_legal_rule_exception_and_authority_program_replays() -> None:
    rules = (
        _legal_rule("guidance", "Agency Guidance", "administrative filing"),
        _legal_rule("statute", "Example Act", "statutory filing"),
    )
    bundle = _bundle("legal", rules)
    graph = ProofGraphBuilder().build(bundle)
    task = LegalTaskPlugin().rule_application(
        graph,
        bundle,
        rules,
        satisfied_conditions=("threshold exceeded",),
        present_exceptions=(),
        authority_priority=("Example Act", "Agency Guidance"),
    )
    registry = legal_operation_registry()
    workflow = ReferenceWorkflowCompiler(registry).compile(task, bundle)
    assessment = ReferenceQualityEvaluator(
        semantic_policy=LegalSemanticPolicy(),
        workflow_verifier=ReferenceWorkflowVerifier(registry),
    ).evaluate(task, bundle, graph, workflow)

    assert [node.operator_id for node in task.oracle.task_program.nodes] == [
        "legal_apply_rule",
        "legal_apply_rule",
        "legal_resolve_authority",
    ]
    assert workflow.final_answer["result"] == {
        "applicable": True,
        "selected_ref": "apply_2",
        "authority": "Example Act",
        "legal_effect": "statutory filing",
    }
    _assert_cross_domain_assessment(assessment)


def test_science_protocol_alignment_effect_and_uncertainty_program_replays() -> None:
    left = _science_result("method_a", "10.2", "9.7", "10.7")
    right = _science_result("method_b", "11.0", "10.4", "11.6")
    bundle = _bundle("science", (left, right))
    graph = ProofGraphBuilder().build(bundle)
    task = ScienceTaskPlugin().compare_experiments(graph, bundle, left, right)
    registry = science_operation_registry()
    workflow = ReferenceWorkflowCompiler(registry).compile(task, bundle)
    assessment = ReferenceQualityEvaluator(
        semantic_policy=ScienceSemanticPolicy(),
        workflow_verifier=ReferenceWorkflowVerifier(registry),
    ).evaluate(task, bundle, graph, workflow)

    assert task.public.retrieval_track.value == "semi_open"
    assert [node.operator_id for node in task.oracle.task_program.nodes] == [
        "science_align_protocol",
        "science_compare_effect",
    ]
    assert workflow.final_answer["result"] == {
        "higher_ref": right.evidence_id,
        "difference": "0.8",
        "uncertainty_intervals_overlap": True,
        "qualified_conclusion": "observed_difference_with_overlapping_uncertainty",
    }
    _assert_cross_domain_assessment(assessment)


def test_non_finance_operation_mutation_is_rejected_by_universal_replay() -> None:
    rules = (
        _legal_rule("guidance", "Agency Guidance", "administrative filing"),
        _legal_rule("statute", "Example Act", "statutory filing"),
    )
    bundle = _bundle("legal", rules)
    graph = ProofGraphBuilder().build(bundle)
    task = LegalTaskPlugin().rule_application(
        graph,
        bundle,
        rules,
        satisfied_conditions=("threshold exceeded",),
        present_exceptions=(),
        authority_priority=("Example Act", "Agency Guidance"),
    )
    registry = legal_operation_registry()
    workflow = ReferenceWorkflowCompiler(registry).compile(task, bundle)
    execution = deepcopy(workflow.program_execution)
    execution["node_outputs"]["result"]["legal_effect"] = "mutated effect"
    mutated = workflow.model_copy(update={"program_execution": execution})

    assessment = ReferenceQualityEvaluator(
        semantic_policy=LegalSemanticPolicy(),
        workflow_verifier=ReferenceWorkflowVerifier(registry),
    ).evaluate(task, bundle, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "independent_recompute" in assessment.fatal_failures
    assert all(gate.passed for gate in assessment.domain_gates)


def _assert_cross_domain_assessment(assessment) -> None:
    assert assessment.decision == ReleaseDecision.ACCEPTED
    assert assessment.universal_gates
    assert assessment.domain_gates
    assert all(gate.passed for gate in assessment.universal_gates)
    assert all(gate.passed for gate in assessment.domain_gates)
    assert all(gate.scope == GateScope.UNIVERSAL for gate in assessment.universal_gates)
    assert all(gate.scope == GateScope.DOMAIN for gate in assessment.domain_gates)


def _bundle(domain: str, evidence: tuple[EvidenceItem, ...]) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=f"bundle:{domain}:complex_contract",
        evidence=evidence,
        purpose=f"{domain} non-lookup reasoning contract",
        graph_build_id=f"{domain}_contract_build",
    )


def _legal_rule(key: str, authority: str, effect: str) -> EvidenceItem:
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
        temporal_context=TemporalContext(label="effective 2025", valid_to=date(2025, 1, 1)),
        scope=EvidenceScope(scope_type="legal_system", scope_id="example_jdx"),
        source=SourceRef(
            source_id=f"legal_source_{key}",
            name=authority,
            authority=SourceAuthority.PRIMARY,
        ),
        source_locator=SourceLocator(uri=f"https://example.org/law/{key}", text_span="section 10"),
        definition=SemanticDefinitionRef(definition_id="legal_definition:filing_requirement"),
        provenance=ProvenanceRef(
            adapter_id="legal_contract.v1",
            archive_id="legal_contract_archive",
            source_record_id=key,
            build_ids={"evidence": "legal_contract_build"},
        ),
        epistemic_status=EpistemicStatus.OBSERVED,
        extraction_confidence=1,
    )


def _science_result(key: str, value: str, lower: str, upper: str) -> EvidenceItem:
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
        temporal_context=TemporalContext(label="study version 2025", observed_at=date(2025, 2, 1)),
        scope=EvidenceScope(scope_type="study_population", scope_id="held_out_dataset"),
        source=SourceRef(
            source_id=f"paper_{key}",
            name=f"Peer-reviewed study {key}",
            authority=SourceAuthority.PEER_REVIEWED,
        ),
        source_locator=SourceLocator(uri=f"https://example.org/papers/{key}", text_span="table 2"),
        definition=SemanticDefinitionRef(definition_id="science_definition:accuracy_gain"),
        provenance=ProvenanceRef(
            adapter_id="science_contract.v1",
            archive_id="science_contract_archive",
            source_record_id=key,
            build_ids={"evidence": "science_contract_build"},
        ),
        epistemic_status=EpistemicStatus.OBSERVED,
        extraction_confidence=1,
    )
