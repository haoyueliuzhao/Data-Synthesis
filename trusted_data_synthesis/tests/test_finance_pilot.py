from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from trusted_synthesis.core.evaluation.evaluator import (
    CandidateQualityEvaluator,
    ReferenceQualityEvaluator,
)
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence import ScalarObservation, TemporalContext
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.refinement import build_synthesis_cell
from trusted_synthesis.core.release import SplitPolicy, select_candidate_release
from trusted_synthesis.core.task.difficulty import assess_task_difficulty
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.experiments.finance_pilot.mutations import generate_mutations
from trusted_synthesis.experiments.finance_pilot.sampler import (
    TaskBinding,
    discover_bindings,
    select_real_distractors,
)
from trusted_synthesis.experiments.finance_pilot.schema import FinancePilotConfig
from trusted_synthesis.experiments.finance_pilot.task_factory import (
    PilotTaskCase,
    build_task_cases,
)
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime


def _case(finance_evidence: EvidenceItem) -> PilotTaskCase:
    observations = [finance_evidence]
    for year, value in ((2024, "400000"), (2025, "500000")):
        observations.append(
            finance_evidence.model_copy(
                update={
                    "evidence_id": f"evidence:finance:revenue_{year}@kg_test",
                    "assertion_id": f"assertion:finance:revenue_{year}",
                    "evidence_version_id": f"version:finance:revenue_{year}@kg_test",
                    "payload": ScalarObservation(
                        value=Decimal(value),
                        unit="million USD",
                        currency="USD",
                    ),
                    "temporal_context": TemporalContext(
                        label=f"FY{year}",
                        valid_from=date(year - 1, 10, 1),
                        valid_to=date(year, 9, 30),
                        basis="fiscal_period",
                        frequency="annual",
                    ),
                    "provenance": finance_evidence.provenance.model_copy(
                        update={"source_record_id": f"revenue_{year}"}
                    ),
                    "domain_context": {
                        **finance_evidence.domain_context,
                        "fiscal_year": year,
                    },
                }
            )
        )
    bundle = EvidenceBundle(
        bundle_id="bundle_finance_pilot_average",
        evidence=tuple(observations),
        purpose="finance pilot average test",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    task = FinanceTaskPlugin(allow_structured_claims=True).temporal_average(
        graph,
        bundle,
        tuple(item.evidence_id for item in observations),
    )
    corpus = EvidenceCorpus.from_bundle(bundle)
    binding = TaskBinding(
        task_type="temporal_average",
        evidence_ids=task.oracle.gold_evidence_ids,
        stratum=("global", "financial_statement", "annual", "sec", "single_source"),
    )
    return PilotTaskCase(
        binding=binding,
        bundle=bundle,
        corpus=corpus,
        proof_graph=graph,
        task=task,
        distractor_ids=(),
    )


def test_real_archive_distractors_are_unmodified_and_have_hidden_labels(
    finance_evidence: EvidenceItem,
) -> None:
    wrong_period = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:revenue_2022@kg_test",
            "assertion_id": "assertion:finance:revenue_2022",
            "evidence_version_id": "version:finance:revenue_2022@kg_test",
            "temporal_context": TemporalContext(
                label="FY2022",
                valid_from=date(2021, 9, 26),
                valid_to=date(2022, 9, 24),
                basis="fiscal_period",
                frequency="annual",
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "fact_revenue_2022"}
            ),
        }
    )
    wrong_entity = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:other_revenue_2023@kg_test",
            "assertion_id": "assertion:finance:other_revenue_2023",
            "evidence_version_id": "version:finance:other_revenue_2023@kg_test",
            "subject": finance_evidence.subject.model_copy(
                update={"subject_id": "OTHER_US", "name": "Other Company"}
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "fact_other_revenue_2023"}
            ),
        }
    )

    selection = select_real_distractors(
        (finance_evidence, wrong_period, wrong_entity),
        (finance_evidence,),
        hard_count=2,
        broad_count=0,
        preferred_hard_kinds=("wrong_period", "wrong_entity"),
    )

    assert {item.evidence_id for item in selection.evidence} == {
        wrong_period.evidence_id,
        wrong_entity.evidence_id,
    }
    assert selection.kinds[wrong_period.evidence_id] == "wrong_period"
    assert selection.kinds[wrong_entity.evidence_id] == "wrong_entity"
    assert selection.mismatches[wrong_period.evidence_id] == ("wrong_period",)
    assert selection.mismatches[wrong_entity.evidence_id] == ("wrong_entity",)
    assert all("distractor" not in item.evidence_id for item in selection.evidence)
    assert all(
        "synthetic_distractor_kind" not in item.domain_context for item in selection.evidence
    )


def test_real_archive_hard_distractors_require_one_semantic_mismatch(
    finance_evidence: EvidenceItem,
) -> None:
    distant = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:distant_fact@kg_test",
            "assertion_id": "assertion:finance:distant_fact",
            "evidence_version_id": "version:finance:distant_fact@kg_test",
            "subject": finance_evidence.subject.model_copy(
                update={"subject_id": "OTHER_US", "name": "Other Company"}
            ),
            "predicate": "total_assets",
            "temporal_context": TemporalContext(
                label="FY2022",
                valid_from=date(2021, 9, 26),
                valid_to=date(2022, 9, 24),
                basis="fiscal_period",
                frequency="annual",
            ),
        }
    )

    selection = select_real_distractors(
        (finance_evidence, distant),
        (finance_evidence,),
        hard_count=1,
        broad_count=1,
    )

    assert selection.hard == ()
    assert selection.broad == (distant,)
    assert len(selection.mismatches[distant.evidence_id]) > 1


def test_synthesis_cell_signature_v3_tracks_bounded_semantic_contracts(
    finance_evidence: EvidenceItem,
) -> None:
    case = _case(finance_evidence)
    baseline = build_synthesis_cell(
        case.task.public,
        case.corpus,
        case.task.oracle.gold_evidence_ids,
    )
    first = case.corpus.evidence[0]
    variants = (
        first.model_copy(
            update={"payload": first.payload.model_copy(update={"unit": "USD", "currency": "USD"})}
        ),
        first.model_copy(
            update={
                "payload": first.payload.model_copy(
                    update={"unit": first.payload.unit, "currency": "EUR"}
                )
            }
        ),
        first.model_copy(
            update={
                "temporal_context": first.temporal_context.model_copy(
                    update={"basis": "calendar_period"}
                )
            }
        ),
        first.model_copy(
            update={
                "temporal_context": first.temporal_context.model_copy(
                    update={"frequency": "quarterly"}
                )
            }
        ),
        first.model_copy(
            update={
                "definition": first.definition.model_copy(
                    update={
                        "attributes": {
                            **first.definition.attributes,
                            "metric_category": "cash_flow",
                        }
                    }
                )
            }
        ),
        first.model_copy(
            update={
                "definition": first.definition.model_copy(
                    update={
                        "attributes": {
                            **first.definition.attributes,
                            "period_type": "duration",
                        }
                    }
                )
            }
        ),
        first.model_copy(update={"domain_context": {**first.domain_context, "is_forecast": True}}),
    )
    stratum_ids = {baseline.binding_stratum_id}
    for index, variant in enumerate(variants):
        corpus = EvidenceCorpus(
            corpus_id=f"signature_v3_variant_{index}",
            evidence=(
                variant,
                *tuple(
                    item for item in case.corpus.evidence if item.evidence_id != first.evidence_id
                ),
            ),
            build_id=case.corpus.build_id,
        )
        cell = build_synthesis_cell(
            case.task.public,
            corpus,
            case.task.oracle.gold_evidence_ids,
        )
        stratum_ids.add(cell.binding_stratum_id)

    assert len(stratum_ids) == 8
    assert all(value.startswith("binding_stratum_v3:") for value in stratum_ids)


def test_difficulty_changes_with_retrieval_ambiguity_within_one_pattern(
    finance_evidence: EvidenceItem,
) -> None:
    case = _case(finance_evidence)
    baseline = build_synthesis_cell(
        case.task.public,
        case.corpus,
        case.task.oracle.gold_evidence_ids,
    )
    anchor = case.corpus.evidence[0]
    distractors = tuple(
        anchor.model_copy(
            update={
                "evidence_id": f"evidence:finance:near_miss_{index}@kg_test",
                "assertion_id": f"assertion:finance:near_miss_{index}",
                "evidence_version_id": f"version:finance:near_miss_{index}@kg_test",
                "subject": anchor.subject.model_copy(
                    update={
                        "subject_id": f"NEAR_MISS_{index}",
                        "name": f"Near Miss Company {index}",
                    }
                ),
                "source": anchor.source.model_copy(
                    update={"source_id": f"official_peer_source_{index}"}
                ),
                "provenance": anchor.provenance.model_copy(
                    update={"source_record_id": f"near_miss_{index}"}
                ),
            }
        )
        for index in range(10)
    )
    ambiguous_corpus = EvidenceCorpus(
        corpus_id="finance_temporal_average_with_real_near_misses",
        evidence=(*case.corpus.evidence, *distractors),
        build_id=case.corpus.build_id,
    )

    ambiguous = build_synthesis_cell(
        case.task.public,
        ambiguous_corpus,
        case.task.oracle.gold_evidence_ids,
    )

    levels = ("easy", "medium", "hard", "expert", "research")
    assert ambiguous.pattern_id == baseline.pattern_id
    assert ambiguous.binding_stratum_id == baseline.binding_stratum_id
    assert levels.index(ambiguous.difficulty_bucket) > levels.index(baseline.difficulty_bucket)
    assert ambiguous.distractor_profile_id != baseline.distractor_profile_id


def test_temporal_average_reference_and_candidate_are_accepted(
    finance_evidence: EvidenceItem,
) -> None:
    case = _case(finance_evidence)
    reference = ReferenceWorkflowCompiler().compile(case.task, case.bundle)
    candidate = FinanceNumericCandidateGenerator().generate(
        case.task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )

    reference_quality = ReferenceQualityEvaluator(semantic_policy=FinanceSemanticPolicy()).evaluate(
        case.task, case.bundle, case.proof_graph, reference
    )
    candidate_quality = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(),
        claim_verifier=FinanceClaimVerifier(),
    ).evaluate(case.task, case.corpus, case.proof_graph, candidate)

    assert len(case.task.oracle.task_program.nodes) == 4
    assert len(case.binding.stratum) == 5
    assert reference_quality.decision == ReleaseDecision.ACCEPTED
    assert candidate_quality.decision == ReleaseDecision.ACCEPTED
    assert candidate.final_answer["result"]["method"] == "mean"


def test_pilot_mutations_are_rejected_and_not_released(
    finance_evidence: EvidenceItem,
) -> None:
    case = _case(finance_evidence)
    candidate = FinanceNumericCandidateGenerator().generate(
        case.task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(),
        claim_verifier=FinanceClaimVerifier(),
    )
    clean = evaluator.evaluate(case.task, case.corpus, case.proof_graph, candidate)
    mutations = generate_mutations(
        case,
        candidate,
        (
            "missing_evidence",
            "arithmetic_error",
            "wrong_answer",
            "citation_mismatch",
            "unsupported_claim",
            "oracle_leakage",
            "disallowed_tool",
            "failed_step",
            "extra_result_field",
            "program_node_mismatch",
            "conflicting_calculation",
            "verification_result_mismatch",
            "claim_value_mismatch",
            "multi_error",
        ),
    )
    mutated = [
        (
            mutation,
            evaluator.evaluate(
                case.task,
                case.corpus,
                case.proof_graph,
                mutation.trajectory,
            ),
        )
        for mutation in mutations
    ]
    selection = select_candidate_release(
        [
            (case.task, candidate, clean),
            *[(case.task, mutation.trajectory, assessment) for mutation, assessment in mutated],
        ],
        SplitPolicy(policy_id="pilot_test_split"),
    )

    assert clean.decision == ReleaseDecision.ACCEPTED
    assert all(assessment.decision == ReleaseDecision.REJECTED for _, assessment in mutated)
    assert all(
        set(mutation.expected_failure_gates).issubset(assessment.fatal_failures)
        for mutation, assessment in mutated
    )
    assert all(
        set(mutation.expected_failure_checks).issubset(assessment.failed_check_ids)
        for mutation, assessment in mutated
    )
    assert all(
        set(mutation.expected_detail_tokens).issubset(
            {detail for details in assessment.check_failure_details.values() for detail in details}
        )
        for mutation, assessment in mutated
        if mutation.expected_detail_tokens
    )
    assert selection.accepted_trajectory_ids == (candidate.trajectory_id,)


def test_registered_ratio_requires_exact_period_identity(
    finance_evidence: EvidenceItem,
) -> None:
    gross_profit = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:gross_profit_2023@kg_test",
            "assertion_id": "assertion:finance:gross_profit_2023",
            "evidence_version_id": "version:finance:gross_profit_2023@kg_test",
            "predicate": "gross_profit",
            "definition": finance_evidence.definition.model_copy(
                update={
                    "definition_id": "sdef_gross_profit",
                    "text": "Registered gross profit definition.",
                }
            ),
            "temporal_context": finance_evidence.temporal_context.model_copy(
                update={"valid_from": date(2022, 10, 2)}
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "gross_profit_2023"}
            ),
        }
    )
    config = FinancePilotConfig(
        task_quotas={"registered_ratio": 1},
        require_full_quota=False,
    )

    mismatched = discover_bindings((gross_profit, finance_evidence), config)
    aligned = discover_bindings(
        (
            gross_profit.model_copy(update={"temporal_context": finance_evidence.temporal_context}),
            finance_evidence,
        ),
        config,
    )

    assert mismatched == ()
    assert len(aligned) == 1
    assert aligned[0].task_type == "registered_ratio"


def test_registered_ratio_runtime_rejects_cross_source_binding(
    finance_evidence: EvidenceItem,
) -> None:
    numerator = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:gross_profit_cross_source@kg_test",
            "assertion_id": "assertion:finance:gross_profit_cross_source",
            "evidence_version_id": "version:finance:gross_profit_cross_source@kg_test",
            "predicate": "gross_profit",
            "definition": finance_evidence.definition.model_copy(
                update={
                    "definition_id": "sdef_gross_profit",
                    "text": "Registered gross profit definition.",
                }
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "gross_profit_cross_source"}
            ),
        }
    )
    denominator = finance_evidence.model_copy(
        update={
            "source": finance_evidence.source.model_copy(
                update={"source_id": "incompatible_finance_source"}
            )
        }
    )
    bundle = EvidenceBundle(
        bundle_id="bundle_ratio_cross_source",
        evidence=(numerator, denominator),
        purpose="ratio runtime cross-source regression",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)

    with pytest.raises(ValueError, match="same_source"):
        FinanceTaskPlugin(allow_structured_claims=True).registered_ratio(
            graph,
            bundle,
            numerator.evidence_id,
            denominator.evidence_id,
            registered_pair="gross_profit/revenue",
        )


def test_temporal_average_runtime_rejects_noncontiguous_periods(
    finance_evidence: EvidenceItem,
) -> None:
    series = tuple(
        finance_evidence.model_copy(
            update={
                "evidence_id": f"evidence:finance:revenue_sparse_{year}@kg_test",
                "assertion_id": f"assertion:finance:revenue_sparse_{year}",
                "evidence_version_id": f"version:finance:revenue_sparse_{year}@kg_test",
                "temporal_context": TemporalContext(
                    label=f"FY{year}",
                    valid_from=date(year - 1, 10, 1),
                    valid_to=date(year, 9, 30),
                    basis="fiscal_period",
                    frequency="annual",
                ),
                "provenance": finance_evidence.provenance.model_copy(
                    update={"source_record_id": f"revenue_sparse_{year}"}
                ),
            }
        )
        for year in (2021, 2023, 2025)
    )
    bundle = EvidenceBundle(
        bundle_id="bundle_temporal_average_sparse",
        evidence=series,
        purpose="temporal runtime continuity regression",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)

    with pytest.raises(ValueError, match="contiguous_periods"):
        FinanceTaskPlugin(allow_structured_claims=True).temporal_average(
            graph,
            bundle,
            tuple(item.evidence_id for item in series),
        )


def test_finance_catalog_v2_discovers_and_compiles_multi_step_programs(
    finance_evidence: EvidenceItem,
) -> None:
    evidence = []
    values = {
        "AAPL_US": {
            "revenue": {2022: 100, 2023: 120, 2024: 150},
            "net_income": {2022: 10, 2023: 15, 2024: 20},
        },
        "MSFT_US": {
            "revenue": {2022: 100, 2023: 110, 2024: 140},
            "net_income": {2022: 8, 2023: 11, 2024: 18},
        },
    }
    for subject_id, metrics in values.items():
        subject = finance_evidence.subject.model_copy(
            update={
                "subject_id": subject_id,
                "name": "Apple Inc." if subject_id == "AAPL_US" else "Microsoft Corp.",
            }
        )
        scope = finance_evidence.scope.model_copy(
            update={
                "scope_id": subject_id,
                "label": f"{subject.name} consolidated",
            }
        )
        for predicate, by_year in metrics.items():
            definition = finance_evidence.definition.model_copy(
                update={
                    "definition_id": f"sdef_{predicate}",
                    "text": f"Registered {predicate} definition.",
                }
            )
            for year, value in by_year.items():
                evidence.append(
                    finance_evidence.model_copy(
                        update={
                            "evidence_id": (
                                f"evidence:finance:{subject_id}:{predicate}:{year}@kg_test"
                            ),
                            "assertion_id": (f"assertion:finance:{subject_id}:{predicate}:{year}"),
                            "evidence_version_id": (
                                f"version:finance:{subject_id}:{predicate}:{year}@kg_test"
                            ),
                            "subject": subject,
                            "predicate": predicate,
                            "payload": ScalarObservation(
                                value=Decimal(value),
                                unit="million USD",
                                currency="USD",
                            ),
                            "temporal_context": TemporalContext(
                                label=f"FY{year}",
                                valid_from=date(year - 1, 10, 1),
                                valid_to=date(year, 9, 30),
                                basis="fiscal_period",
                                frequency="annual",
                            ),
                            "scope": scope,
                            "definition": definition,
                            "provenance": finance_evidence.provenance.model_copy(
                                update={"source_record_id": (f"{subject_id}:{predicate}:{year}")}
                            ),
                            "domain_context": {
                                **finance_evidence.domain_context,
                                "fiscal_year": year,
                            },
                        }
                    )
                )

    config = FinancePilotConfig(
        task_quotas={
            "temporal_absolute_change": 1,
            "registered_ratio": 1,
            "derived_growth_comparison": 1,
        },
        require_full_quota=True,
    )
    bindings = discover_bindings(tuple(evidence), config)
    cases = build_task_cases(
        bindings,
        tuple(evidence),
        distractors_per_task=0,
        hard_distractors_per_task=0,
        hard_distractor_types=(),
        task_synthesizer=FinanceTaskPlugin(allow_structured_claims=True),
    )
    by_type = {case.binding.task_type: case for case in cases}

    assert set(by_type) == {
        "temporal_absolute_change",
        "registered_ratio",
        "derived_growth_comparison",
    }
    assert tuple(
        node.operator_id
        for node in by_type["temporal_absolute_change"].task.oracle.task_program.nodes
    ) == ("lookup", "lookup", "difference")
    assert tuple(
        node.operator_id for node in by_type["registered_ratio"].task.oracle.task_program.nodes
    ) == ("lookup", "lookup", "ratio")
    assert tuple(
        node.operator_id
        for node in by_type["derived_growth_comparison"].task.oracle.task_program.nodes
    ) == (
        "lookup",
        "lookup",
        "lookup",
        "lookup",
        "growth",
        "growth",
        "compare",
    )

    evaluator = ReferenceQualityEvaluator(semantic_policy=FinanceSemanticPolicy())
    for case in cases:
        reference = ReferenceWorkflowCompiler().compile(case.task, case.bundle)
        assessment = evaluator.evaluate(
            case.task,
            case.bundle,
            case.proof_graph,
            reference,
        )
        assert assessment.decision == ReleaseDecision.ACCEPTED

    derived_case = by_type["derived_growth_comparison"]
    derived_reference = ReferenceWorkflowCompiler().compile(
        derived_case.task,
        derived_case.bundle,
    )
    result = derived_reference.final_answer["result"]
    assert set(result) == {
        "selected_entity_id",
        "selected_entity_name",
        "left_entity_id",
        "left_entity_name",
        "left_growth_pct",
        "right_entity_id",
        "right_entity_name",
        "right_growth_pct",
        "difference_percentage_points",
    }
    assert result["selected_entity_id"] in {"AAPL_US", "MSFT_US"}
    assert not any(str(value).startswith(("op:", "operation:")) for value in result.values())

    declared_pattern = next(
        pattern
        for pattern in FinanceTaskPlugin().pattern_manifest
        if pattern.task_type == "derived_growth_comparison"
    ).model_copy(update={"difficulty_base": "research", "difficulty_base_cost": 25.0})
    profile = assess_task_difficulty(
        pattern=declared_pattern,
        program=derived_case.task.oracle.task_program,
        proof_graph=derived_case.proof_graph,
        evidence_ids=derived_case.task.oracle.gold_evidence_ids,
        semantic_alignment_cost=0,
    )
    assert profile.pattern_prior_level.value == "research"
    assert profile.level.value != "research"
