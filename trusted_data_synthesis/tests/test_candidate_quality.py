from __future__ import annotations

from datetime import date
from decimal import Decimal

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evaluation.evaluator import (
    CandidateQualityEvaluator,
    ReferenceQualityEvaluator,
)
from trusted_synthesis.core.evaluation.leakage import OracleLeakageChecker
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence import ScalarObservation, TemporalContext
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.core.task.schema import PlanningTrack, VerifierRequirement
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.core.trajectory.verifier import ReferenceWorkflowVerifier
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.experiments.finance_pilot.sampler import TaskBinding
from trusted_synthesis.experiments.finance_pilot.task_factory import build_task_cases
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime


def _setup(finance_evidence: EvidenceItem):
    bundle = EvidenceBundle(
        bundle_id="bundle_candidate",
        evidence=(finance_evidence,),
        purpose="candidate quality mutations",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().fact_retrieval(graph, bundle, finance_evidence.evidence_id)
    corpus = EvidenceCorpus.from_bundle(bundle)
    candidate = FinanceNumericCandidateGenerator().generate(
        task.public, InMemoryEvidenceToolRuntime(corpus)
    )
    return task, corpus, graph, candidate


def test_correct_candidate_is_accepted(finance_evidence: EvidenceItem) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, candidate)

    assert assessment.decision == ReleaseDecision.ACCEPTED
    assert assessment.total_score == 100
    assert all(gate.passed for gate in assessment.hard_gates)


def test_wrong_or_missing_evidence_is_rejected(finance_evidence: EvidenceItem) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    mutated = _mutate_step_evidence(candidate, ActionType.SELECT_EVIDENCE, ())

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "evidence_retrieval_and_selection" in assessment.fatal_failures


def test_unknown_selected_evidence_and_wrong_answer_are_rejected(
    finance_evidence: EvidenceItem,
) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    unknown_id = "evidence:finance:unknown@kg_test"
    steps = tuple(
        step.model_copy(update={"evidence_ids": (unknown_id,)})
        if step.action in {ActionType.SEARCH, ActionType.SELECT_EVIDENCE}
        else step
        for step in candidate.steps
    )
    answer = dict(candidate.final_answer)
    answer["result"] = {**answer["result"], "value": "1"}
    mutated = candidate.model_copy(update={"steps": steps, "final_answer": answer})

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "evidence_retrieval_and_selection" in assessment.fatal_failures
    assert "answer_and_citation" in assessment.fatal_failures


def test_resolved_track_searches_a_corpus_with_distractors(
    finance_evidence: EvidenceItem,
) -> None:
    task, _, graph, _ = _setup(finance_evidence)
    distractor = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:distractor@kg_test",
            "assertion_id": "assertion:finance:distractor",
            "evidence_version_id": "version:finance:distractor@kg_test",
            "predicate": "total_assets",
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "distractor"}
            ),
        }
    )
    corpus = EvidenceCorpus(
        corpus_id="corpus_with_distractor",
        evidence=(finance_evidence, distractor),
        build_id="kg_test",
    )
    candidate = FinanceNumericCandidateGenerator().generate(
        task.public, InMemoryEvidenceToolRuntime(corpus)
    )

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, candidate)

    assert task.public.retrieval_track.value == "resolved"
    assert assessment.decision == ReleaseDecision.ACCEPTED
    assert candidate.steps[1].evidence_ids == (finance_evidence.evidence_id,)


def test_hard_in_scope_distractors_are_retrieved_but_not_selected(
    finance_evidence: EvidenceItem,
) -> None:
    binding = TaskBinding(
        task_type="fact_retrieval",
        evidence_ids=(finance_evidence.evidence_id,),
        stratum=("global", "financial_statement", "annual", "sec", "single_source"),
    )
    case = build_task_cases(
        (binding,),
        (finance_evidence,),
        distractors_per_task=7,
        hard_distractor_types=(
            "wrong_definition",
            "stale_version",
            "forecast",
            "lower_authority",
            "unit_mismatch",
            "currency_mismatch",
            "wrong_scope",
        ),
        task_synthesizer=FinanceTaskPlugin(),
    )[0]

    candidate = FinanceNumericCandidateGenerator().generate(
        case.task.public, InMemoryEvidenceToolRuntime(case.corpus)
    )
    assessment = CandidateQualityEvaluator().evaluate(
        case.task, case.corpus, case.proof_graph, candidate
    )

    assert len(case.hard_distractor_ids) == 7
    assert set(candidate.steps[1].evidence_ids) == {
        finance_evidence.evidence_id,
        *case.hard_distractor_ids,
    }
    selected = next(step for step in candidate.steps if step.action == ActionType.SELECT_EVIDENCE)
    assert selected.evidence_ids == (finance_evidence.evidence_id,)
    assert assessment.decision == ReleaseDecision.ACCEPTED


def test_post_retrieval_evidence_mentions_are_not_oracle_leakage(
    finance_evidence: EvidenceItem,
) -> None:
    task, _, _, candidate = _setup(finance_evidence)
    selected = next(step for step in candidate.steps if step.action == ActionType.SELECT_EVIDENCE)
    steps = tuple(
        step.model_copy(
            update={
                "rationale_summary": (f"Select retrieved evidence {finance_evidence.evidence_id}.")
            }
        )
        if step.step_index == selected.step_index
        else step
        for step in candidate.steps
    )

    report = OracleLeakageChecker().verify(
        task.oracle, candidate.model_copy(update={"steps": steps})
    )

    assert report.passed


def test_extra_result_properties_are_rejected(finance_evidence: EvidenceItem) -> None:
    task, _, _, candidate = _setup(finance_evidence)
    answer = dict(candidate.final_answer)
    answer["result"] = {
        **answer["result"],
        "recommendation": "Buy this security immediately.",
    }

    passed, failures = CandidateAnswerNormalizer().validate_schema(task.public, answer)

    assert not passed
    assert "unexpected_result_fields:recommendation" in failures


def test_projected_answer_contract_is_public_complete_and_fail_closed() -> None:
    normalizer = CandidateAnswerNormalizer()
    cases = (
        (
            build_finance_counterfactual_case(2),
            {"higher_ref", "difference", "result_context"},
            "result_context",
        ),
        (
            build_finance_counterfactual_case(3),
            {"value", "unit"},
            "unit",
        ),
    )

    for case, required_fields, constant_field in cases:
        schema = case.task.public.answer_schema
        assert set(schema["required_fields"]) == required_fields
        assert schema["answer_schema_contract_version"] == "answer_schema_contract.v1"

        reference = ReferenceWorkflowCompiler(case.registry).compile(case.task, case.bundle)
        assessment = ReferenceQualityEvaluator(
            workflow_verifier=ReferenceWorkflowVerifier(case.registry)
        ).evaluate(case.task, case.bundle, case.proof_graph, reference)
        assert assessment.decision == ReleaseDecision.ACCEPTED
        assert set(reference.final_answer["result"]) == required_fields

        missing = {
            **reference.final_answer,
            "result": {
                key: value
                for key, value in reference.final_answer["result"].items()
                if key != constant_field
            },
        }
        passed, failures = normalizer.validate_schema(case.task.public, missing)
        assert not passed
        assert any(item.startswith("required_fields_missing:") for item in failures)

        wrong = {
            **reference.final_answer,
            "result": {
                **reference.final_answer["result"],
                constant_field: "wrong-contract-value",
            },
        }
        passed, failures = normalizer.validate_schema(case.task.public, wrong)
        assert not passed
        assert f"answer_schema_constant_mismatch:{constant_field}" in failures


def test_wrong_calculation_is_rejected(finance_evidence: EvidenceItem) -> None:
    later = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:fact_revenue_2024@kg_test",
            "assertion_id": "assertion:finance:fact_revenue_2024",
            "evidence_version_id": "version:finance:fact_revenue_2024@kg_test",
            "payload": ScalarObservation(
                value=Decimal("421613.5"), unit="million USD", currency="USD"
            ),
            "temporal_context": TemporalContext(
                label="FY2024",
                valid_from=date(2023, 10, 1),
                valid_to=date(2024, 9, 30),
                basis="fiscal_period",
                frequency="annual",
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "fact_revenue_2024"}
            ),
        }
    )
    bundle = EvidenceBundle(
        bundle_id="bundle_candidate_growth",
        evidence=(finance_evidence, later),
        purpose="candidate calculation mutation",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = ProofGraphTaskSynthesizer().temporal_growth(
        graph, bundle, finance_evidence.evidence_id, later.evidence_id
    )
    corpus = EvidenceCorpus.from_bundle(bundle)
    candidate = FinanceNumericCandidateGenerator().generate(
        task.public, InMemoryEvidenceToolRuntime(corpus)
    )
    mutated_steps = tuple(
        step.model_copy(update={"observation": {"result": {"value": "99"}}})
        if step.action == ActionType.CALCULATE
        else step
        for step in candidate.steps
    )
    mutated = candidate.model_copy(update={"steps": mutated_steps})

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "proof_and_operation" in assessment.fatal_failures


def test_wrong_citation_locator_and_unsupported_claim_are_rejected(
    finance_evidence: EvidenceItem,
) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    answer = dict(candidate.final_answer)
    answer["citations"] = [
        {
            **answer["citations"][0],
            "source_locator": {"uri": "https://wrong.example/"},
        }
    ]
    answer["claims"] = [{"claim": "An unsupported causal conclusion."}]
    mutated = candidate.model_copy(update={"final_answer": answer})

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "answer_and_citation" in assessment.fatal_failures
    assert "domain_claims" in assessment.fatal_failures


def test_oracle_leakage_and_disallowed_tool_are_rejected(
    finance_evidence: EvidenceItem,
) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    steps = []
    for step in candidate.steps:
        if step.action == ActionType.PLAN:
            step = step.model_copy(
                update={"tool_input": {"gold_evidence_ids": task.oracle.gold_evidence_ids}}
            )
        if step.action == ActionType.SEARCH:
            step = step.model_copy(update={"tool_name": "oracle_evidence.read"})
        steps.append(step)
    mutated = candidate.model_copy(update={"steps": tuple(steps)})

    assessment = CandidateQualityEvaluator().evaluate(task, corpus, graph, mutated)

    assert assessment.decision == ReleaseDecision.REJECTED
    assert "public_boundary_and_tools" in assessment.fatal_failures


def test_missing_required_check_rejects_without_exception(
    finance_evidence: EvidenceItem,
) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    report = CandidateWorkflowVerifier().verify(task, corpus, graph, candidate)
    incomplete = report.model_copy(
        update={
            "checks": tuple(
                check for check in report.checks if check.check_id != "citation_binding"
            )
        }
    )

    class IncompleteVerifier:
        def verify(self, *args, **kwargs):
            return incomplete

    assessment = CandidateQualityEvaluator(workflow_verifier=IncompleteVerifier()).evaluate(
        task, corpus, graph, candidate
    )

    assert assessment.decision == ReleaseDecision.REJECTED
    manifest_gate = next(
        gate for gate in assessment.hard_gates if gate.gate_id == "required_check_manifest"
    )
    assert manifest_gate.details == ("citation_binding",)


def test_claim_field_is_only_allowed_by_answer_contract(
    finance_evidence: EvidenceItem,
) -> None:
    task, _, _, candidate = _setup(finance_evidence)
    answer = {
        **candidate.final_answer,
        "claims": [
            {
                "claim_id": "claim:observed_revenue",
                "claim_type": "observed_metric",
                "predicate": "revenue",
                "evidence_ids": [finance_evidence.evidence_id],
            }
        ],
    }
    normalizer = CandidateAnswerNormalizer()

    disallowed, failures = normalizer.validate_schema(task.public, answer)
    claim_task = task.public.model_copy(
        update={"answer_schema": {**task.public.answer_schema, "allow_claims": True}}
    )
    allowed, allowed_failures = normalizer.validate_schema(claim_task, answer)

    assert not disallowed
    assert "unexpected_top_level:claims" in failures
    assert allowed
    assert allowed_failures == ()


def test_plan_hidden_candidate_uses_local_node_ids_and_semantic_alignment(
    finance_evidence: EvidenceItem,
) -> None:
    task, corpus, graph, candidate = _setup(finance_evidence)
    hidden_public = task.public.model_copy(
        update={
            "planning_track": PlanningTrack.PLAN_HIDDEN,
            "program_skeleton": None,
        }
    )
    hidden_task = task.model_copy(update={"public": hidden_public})
    local_candidate = _rename_program_nodes(candidate, {"result": "candidate_lookup_1"})

    accepted = CandidateQualityEvaluator().evaluate(hidden_task, corpus, graph, local_candidate)
    wrong_steps = tuple(
        step.model_copy(update={"operator_id": "compare"})
        if step.program_node_id == "candidate_lookup_1"
        else step
        for step in local_candidate.steps
    )
    rejected = CandidateQualityEvaluator().evaluate(
        hidden_task,
        corpus,
        graph,
        local_candidate.model_copy(update={"steps": wrong_steps}),
    )

    assert hidden_task.public.program_skeleton is None
    assert accepted.decision == ReleaseDecision.ACCEPTED
    assert rejected.decision == ReleaseDecision.REJECTED
    assert "proof_and_operation" in rejected.fatal_failures


def test_source_grounding_requirement_is_explicit_and_fails_closed(
    finance_evidence: EvidenceItem,
) -> None:
    default_task, corpus, graph, candidate = _setup(finance_evidence)
    default_assessment = CandidateQualityEvaluator().evaluate(
        default_task, corpus, graph, candidate
    )
    not_applicable = next(
        check
        for check in CandidateWorkflowVerifier()
        .verify(default_task, corpus, graph, candidate)
        .checks
        if check.check_id == "source_grounding"
    )

    bundle = EvidenceBundle(
        bundle_id="bundle_required_grounding",
        evidence=(finance_evidence,),
        purpose="required source grounding",
        graph_build_id="kg_test",
    )
    required_graph = ProofGraphBuilder().build(bundle)
    required_task = FinanceTaskPlugin(
        source_grounding_requirement=VerifierRequirement.REQUIRED
    ).fact_retrieval(required_graph, bundle, finance_evidence.evidence_id)
    reference = ReferenceWorkflowCompiler().compile(required_task, bundle)
    required_assessment = ReferenceQualityEvaluator().evaluate(
        required_task, bundle, required_graph, reference
    )

    assert default_assessment.decision == ReleaseDecision.ACCEPTED
    assert not_applicable.passed
    assert not_applicable.details == ("status=not_applicable",)
    assert required_assessment.decision == ReleaseDecision.REJECTED
    grounding_gate = next(
        gate
        for gate in required_assessment.domain_gates
        if gate.gate_id == "domain_source_grounding"
    )
    assert grounding_gate.details[0] == "status=missing_required_verifier"


def _mutate_step_evidence(
    candidate: Trajectory, action: ActionType, evidence_ids: tuple[str, ...]
) -> Trajectory:
    return candidate.model_copy(
        update={
            "steps": tuple(
                step.model_copy(update={"evidence_ids": evidence_ids})
                if step.action == action
                else step
                for step in candidate.steps
            )
        }
    )


def _rename_program_nodes(candidate: Trajectory, mapping: dict[str, str]) -> Trajectory:
    def replace_ref(value: str) -> str:
        for original, replacement in mapping.items():
            value = value.replace(f"operation:{original}", f"operation:{replacement}")
        return value

    steps = []
    for step in candidate.steps:
        observation = dict(step.observation)
        verified_ref = observation.get("verified_output_ref")
        if isinstance(verified_ref, str):
            observation["verified_output_ref"] = replace_ref(verified_ref)
        steps.append(
            step.model_copy(
                update={
                    "program_node_id": mapping.get(step.program_node_id, step.program_node_id),
                    "input_refs": tuple(replace_ref(item) for item in step.input_refs),
                    "output_ref": (
                        replace_ref(step.output_ref) if step.output_ref is not None else None
                    ),
                    "observation": observation,
                }
            )
        )
    return candidate.model_copy(update={"steps": tuple(steps)})
