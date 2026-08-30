from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest

from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.operations.program import (
    TaskProgramExecutor,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.release import (
    DiversityReleasePolicy,
    SplitPolicy,
    assign_realization_split,
    select_diversity_aware_release,
)
from trusted_synthesis.core.task.binding import make_evidence_binding
from trusted_synthesis.core.task.program import make_program
from trusted_synthesis.core.task.realization import (
    PROTECTED_REWRITE_VERSION,
    QuestionRendererProfile,
    SurfaceRealization,
    validate_protected_rewrite,
)
from trusted_synthesis.core.task.semantic import (
    BindingSnapshot,
    canonicalize_semantic_plan,
    proposal_from_pattern,
)
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.semantic_proposals import (
    ProposalAuthorization,
    audit_raw_proposal_compatibility,
    raw_finance_semantic_proposals,
)
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.experiments.qa_realization_vnext.census import (
    _lexical_near_duplicate_cluster_sizes,
    run_task_package_census,
    write_census_artifacts,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime


def test_realization_portfolio_closes_three_identity_layers_without_legacy_drift(
    finance_evidence: EvidenceItem,
) -> None:
    plugin = FinanceTaskPlugin()
    bundle = EvidenceBundle(
        bundle_id="bundle:qa_realization_fact",
        evidence=(finance_evidence,),
        purpose="qa realization vnext fixture",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    pattern = next(item for item in plugin.pattern_manifest if item.task_type == "fact_retrieval")
    binding = make_evidence_binding(
        pattern_id=pattern.pattern_id,
        pattern_version=pattern.pattern_version,
        pattern_hash=pattern.pattern_hash,
        role_bindings={"fact": (finance_evidence.evidence_id,)},
        source_graph_id=graph.graph_id,
        domain_snapshot_id=graph.source_build_id,
    )
    instantiation = plugin.compile_binding("fact_retrieval", graph, bundle, binding)
    compilation = plugin.realize_instantiation(instantiation, graph, bundle)

    assert len(compilation.candidates) == 4
    assert len(compilation.selected) == 3
    assert compilation.portfolio.child_weight_denominator == 3
    assert len({item.realization.semantic_task_id for item in compilation.candidates}) == 1
    assert len({item.binding_snapshot_id for item in compilation.candidates}) == 1
    assert len({item.realization.realization_id for item in compilation.candidates}) == 4
    assert len({item.task.task_hash for item in compilation.candidates}) == 4
    canonical = next(
        item
        for item in compilation.candidates
        if item.realization.renderer_profile_id == pattern.instruction_renderer_id
    )
    assert canonical.task.task_hash == instantiation.task.task_hash
    assert canonical.realization.final_instruction == instantiation.task.public.instruction
    assert all(item.task.task_id == instantiation.task.task_id for item in compilation.candidates)

    binding_payload = compilation.semantic_binding.binding.model_dump(mode="json")
    binding_payload["role_bindings"] = {"fact": ("evidence:counterfactual",)}
    binding_payload["binding_snapshot_id"] = canonical_hash(
        {key: value for key, value in binding_payload.items() if key != "binding_snapshot_id"},
        prefix="binding_snapshot:",
    )
    with pytest.raises(ValueError, match="disagree with role bindings"):
        BindingSnapshot.model_validate(binding_payload)

    realization_payload = canonical.realization.model_dump(mode="json")
    validation = dict(realization_payload["validation"])
    checks = dict(validation["checks"])
    checks["protected_template_round_trip"] = False
    validation.update(
        {
            "passed": False,
            "checks": checks,
            "issues": ("protected_template_round_trip",),
        }
    )

    realization_payload["validation"] = validation
    with pytest.raises(ValueError, match="realization identity is invalid"):
        SurfaceRealization.model_validate(realization_payload)


def test_semantic_identity_excludes_renderer_but_proposal_provenance_remains_bound(
    finance_evidence: EvidenceItem,
) -> None:
    plugin = FinanceTaskPlugin()
    registry = plugin.operation_registry()
    bundle = EvidenceBundle(
        bundle_id="bundle:renderer_identity",
        evidence=(finance_evidence,),
        purpose="renderer identity fixture",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    pattern = next(item for item in plugin.pattern_manifest if item.task_type == "fact_retrieval")
    binding = make_evidence_binding(
        pattern_id=pattern.pattern_id,
        pattern_version=pattern.pattern_version,
        pattern_hash=pattern.pattern_hash,
        role_bindings={"fact": (finance_evidence.evidence_id,)},
        source_graph_id=graph.graph_id,
        domain_snapshot_id=graph.source_build_id,
    )
    instantiation = plugin.compile_binding("fact_retrieval", graph, bundle, binding)
    alternate = pattern.model_copy(
        update={"instruction_renderer_id": "finance.fact_retrieval.concise_en.v1"}
    )
    first_proposal = proposal_from_pattern(pattern, registry)
    second_proposal = proposal_from_pattern(alternate, registry)
    first_plan = canonicalize_semantic_plan(
        first_proposal,
        instantiation.program,
        instantiation.binding,
        registry,
    )
    second_plan = canonicalize_semantic_plan(
        second_proposal,
        instantiation.program,
        instantiation.binding,
        registry,
    )

    assert first_proposal.proposal_id != second_proposal.proposal_id
    assert first_plan.semantic_task_id == second_plan.semantic_task_id
    assert first_plan.parameterized_hash == second_plan.parameterized_hash

    parameterized_node = instantiation.program.nodes[0].model_copy(
        update={"parameters": {"diagnostic_parameter": "changed"}}
    )
    parameterized_program = make_program(
        (parameterized_node,),
        instantiation.program.output_node_id,
    )
    parameterized_plan = canonicalize_semantic_plan(
        first_proposal,
        parameterized_program,
        instantiation.binding,
        registry,
    )
    assert first_plan.topology_hash == parameterized_plan.topology_hash
    assert first_plan.parameterized_hash != parameterized_plan.parameterized_hash
    assert first_plan.semantic_task_id != parameterized_plan.semantic_task_id


def test_protected_rewrite_gate_rejects_slot_numeric_and_semantic_drift() -> None:
    valid = validate_protected_rewrite(
        {
            "rewrite_version": PROTECTED_REWRITE_VERSION,
            "question_template": ("For <slot_period>, what is <slot_subject>'s <slot_metric>?"),
        },
        ("period", "subject", "metric"),
    )
    missing_slot = validate_protected_rewrite(
        {
            "rewrite_version": PROTECTED_REWRITE_VERSION,
            "question_template": "What is <slot_subject>'s <slot_metric>?",
        },
        ("period", "subject", "metric"),
    )
    extra_number = validate_protected_rewrite(
        {
            "rewrite_version": PROTECTED_REWRITE_VERSION,
            "question_template": (
                "For <slot_period>, what is <slot_subject>'s <slot_metric> above 10?"
            ),
        },
        ("period", "subject", "metric"),
    )
    semantic_extension = validate_protected_rewrite(
        {
            "rewrite_version": PROTECTED_REWRITE_VERSION,
            "question_template": ("For <slot_period>, predict <slot_subject>'s <slot_metric>?"),
        },
        ("period", "subject", "metric"),
    )

    assert valid.passed
    assert "rewrite_placeholder_mismatch" in missing_slot.errors
    assert "rewrite_unprotected_number" in extra_number.errors
    assert "rewrite_forbidden_extension" in semantic_extension.errors
    with pytest.raises(ValueError, match="answer-like slots"):
        QuestionRendererProfile(
            profile_id="finance.invalid.answer_slot.v1",
            task_type="fact_retrieval",
            intent="direct_lookup",
            language="en",
            style="invalid",
            protected_template="What is <slot_expected_value>?",
            required_slots=("expected_value",),
            required_operator_cues=("what is",),
            source_requirement="optional",
        )


def test_raw_proposal_migration_authorizes_only_complete_current_surface() -> None:
    audit = audit_raw_proposal_compatibility()

    assert audit.authorized_count == 1
    assert audit.blocked_count == 2
    assert audit.imported_qa_row_count == 0
    authorized = [
        row for row in audit.rows if row.authorization == ProposalAuthorization.AUTHORIZED
    ]
    assert [row.task_type for row in authorized] == ["registered_cross_metric_comparison"]
    assert all(
        row.evidence_role_contract_match
        and row.operation_dag_contract_match
        and row.parameter_contract_match
        and row.answer_schema_contract_match
        and row.semantic_constraint_contract_match
        and row.renderer_intent_contract_match
        and row.quality_profile_contract_match
        for row in authorized
    )
    blocked = [row for row in audit.rows if row.authorization == ProposalAuthorization.BLOCKED]
    assert all(row.missing_operator_ids for row in blocked)
    proposals = {item.task_type: item for item in raw_finance_semantic_proposals()}
    temporal = proposals["temporal_peak_secondary_lookup"]
    assert temporal.answer_schema["required_fields"][-2:] == ["unit", "currency"]
    ranked = proposals["growth_filter_margin_rank"]
    assert ranked.operations[1].parameters["value"] == "10"


def test_registered_cross_metric_proposal_executes_and_independently_verifies(
    finance_evidence: EvidenceItem,
) -> None:
    definition_attributes = {
        **finance_evidence.definition.attributes,
        "statement_type": "income_statement",
        "period_type": "duration",
        "comparability_level": "xbrl_concept_level",
    }
    revenue = finance_evidence.model_copy(
        update={
            "definition": finance_evidence.definition.model_copy(
                update={"attributes": definition_attributes}
            )
        }
    )
    gross_profit = revenue.model_copy(
        update={
            "evidence_id": "evidence:finance:fact_gross_profit_2023@kg_test",
            "assertion_id": "assertion:finance:fact_gross_profit_2023",
            "evidence_version_id": "version:finance:fact_gross_profit_2023@kg_test",
            "predicate": "gross_profit",
            "payload": revenue.payload.model_copy(update={"value": Decimal("169148")}),
            "definition": revenue.definition.model_copy(
                update={"definition_id": "sdef_gross_profit"}
            ),
            "provenance": revenue.provenance.model_copy(
                update={"source_record_id": "fact_gross_profit_2023"}
            ),
        }
    )
    bundle = EvidenceBundle(
        bundle_id="bundle:registered_cross_metric",
        evidence=(revenue, gross_profit),
        purpose="registered cross metric fixture",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    plugin = FinanceTaskPlugin()
    task = plugin.registered_cross_metric_comparison(
        graph,
        bundle,
        revenue.evidence_id,
        gross_profit.evidence_id,
        registered_pair="revenue/gross_profit",
    )
    registry = finance_vnext_operation_registry()
    evidence_by_id = {item.evidence_id: item for item in bundle.evidence}
    execution = TaskProgramExecutor(registry).execute(
        task.oracle.task_program,
        evidence_by_id,
    )
    verification = TaskProgramOracleVerifier(registry).verify(
        task.oracle.task_program,
        evidence_by_id,
        execution.node_outputs,
    )

    assert execution.final_output == {
        "higher_ref": revenue.evidence_id,
        "difference": "214137",
    }
    assert verification.passed
    assert task.public.metadata["proposal_source"] == "raw_static_graph_pattern"
    assert "Which metric is higher" in task.public.instruction


def test_registered_cross_metric_rejects_unregistered_or_context_drift(
    finance_evidence: EvidenceItem,
) -> None:
    plugin = FinanceTaskPlugin()
    invalid = finance_evidence.model_copy(
        update={
            "evidence_id": "evidence:finance:fact_inventory_2023@kg_test",
            "assertion_id": "assertion:finance:fact_inventory_2023",
            "evidence_version_id": "version:finance:fact_inventory_2023@kg_test",
            "predicate": "inventory",
            "definition": finance_evidence.definition.model_copy(
                update={"definition_id": "sdef_inventory"}
            ),
            "provenance": finance_evidence.provenance.model_copy(
                update={"source_record_id": "fact_inventory_2023"}
            ),
        }
    )
    bundle = EvidenceBundle(
        bundle_id="bundle:unregistered_cross_metric",
        evidence=(finance_evidence, invalid),
        purpose="unregistered cross metric fixture",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)

    with pytest.raises(ValueError, match="unregistered_financial_comparison_pair"):
        plugin.registered_cross_metric_comparison(
            graph,
            bundle,
            finance_evidence.evidence_id,
            invalid.evidence_id,
            registered_pair="revenue/inventory",
        )


def test_semantic_parent_split_and_diversity_release_conserve_parent_weight(
    finance_evidence: EvidenceItem,
) -> None:
    compilation, bundle, graph = _fact_realization_compilation(finance_evidence)
    split_policy = SplitPolicy(policy_id="qa_realization_split_fixture.v1")
    assert (
        len({assign_realization_split(item, split_policy) for item in compilation.candidates}) == 1
    )

    corpus = EvidenceCorpus.from_bundle(bundle)
    canonical = next(
        item for item in compilation.candidates if item.realization.style == "canonical"
    )
    records = []
    generator = FinanceNumericCandidateGenerator()
    evaluator = CandidateQualityEvaluator()
    for index, realized in enumerate(compilation.candidates):
        trajectory_id = f"trajectory:realization:{index}"
        generated = generator.generate(
            realized.task.public,
            InMemoryEvidenceToolRuntime(corpus),
        )
        trajectory = generated.model_copy(update={"trajectory_id": trajectory_id})
        assessment = evaluator.evaluate(
            realized.task,
            corpus,
            graph,
            trajectory,
        )
        assert assessment.decision == ReleaseDecision.ACCEPTED
        records.append(
            (
                realized,
                trajectory,
                assessment,
            )
        )
    _, trajectory, assessment = next(
        record for record in records if record[0].realization.style == "canonical"
    )
    rejected_trajectory_id = "trajectory:realization:rejected"
    records.append(
        (
            canonical,
            trajectory.model_copy(update={"trajectory_id": rejected_trajectory_id}),
            assessment.model_copy(
                update={
                    "assessment_id": "assessment:realization:rejected",
                    "trajectory_id": rejected_trajectory_id,
                    "decision": ReleaseDecision.REJECTED,
                    "fatal_failures": ("question_contract_round_trip",),
                }
            ),
        )
    )
    with pytest.raises(ValueError, match="trajectory task identity mismatch"):
        select_diversity_aware_release(
            (
                (
                    records[0][0],
                    records[0][1].model_copy(update={"task_id": "task:foreign"}),
                    records[0][2],
                ),
            ),
            policy=DiversityReleasePolicy(policy_id="qa_realization_bad_binding.v1"),
            split_policy=split_policy,
        )
    selection = select_diversity_aware_release(
        records,
        policy=DiversityReleasePolicy(
            policy_id="qa_realization_release_fixture.v1",
            max_per_semantic_parent=2,
        ),
        split_policy=split_policy,
    )

    assert len(selection.selected_realization_ids) == 2
    assert len(selection.valid_but_not_selected_realization_ids) == 2
    assert set(selection.semantic_parent_child_counts.values()) == {2}
    assert set(selection.semantic_parent_child_weights.values()) == {"1/2"}
    assert selection.failure_distribution == {"question_contract_round_trip": 1}


def test_read_only_census_writes_exact_artifact_set(
    finance_evidence: EvidenceItem,
    tmp_path: Path,
) -> None:
    compilation, _, _ = _fact_realization_compilation(finance_evidence)
    canonical = next(
        item for item in compilation.candidates if item.realization.style == "canonical"
    )
    task_path = tmp_path / "task_packages.jsonl"
    task_path.write_text(canonical.task.model_dump_json() + "\n", encoding="utf-8")
    census = run_task_package_census((task_path,))
    output = tmp_path / "census"
    written = write_census_artifacts(census, output)

    assert len(census.rows) == 1
    assert census.semantic_metrics["unique_semantic_task_count"] == 1
    assert census.semantic_metrics["retrieval_track_distribution"] == {"resolved": 1}
    assert census.semantic_metrics["planning_track_distribution"] == {"plan_given": 1}
    assert census.surface_metrics["unique_normalized_skeleton_count"] == 1
    assert census.surface_metrics["maximum_realizations_per_binding_snapshot"] == 1
    assert census.surface_metrics["slot_variant_usage"] == {"legacy_canonical": 1}
    assert census.surface_metrics["largest_lexical_near_duplicate_cluster_size"] == 1
    assert census.coupling_metrics["normalized_mutual_information"] == 0.0
    assert census.split_audit["leaking_semantic_parent_count"] == 0
    assert census.row_manifest_hash == canonical_hash(
        tuple(row.row_id for row in census.rows),
        prefix="qa_census_row_manifest:",
    )
    assert len(written) == 9
    assert all((output / name).is_file() for name in written)


def test_near_duplicate_cluster_sizes_weight_realization_counts() -> None:
    counts = Counter({"alpha": 13, "beta": 12, "gamma": 12, "delta": 13})

    assert _lexical_near_duplicate_cluster_sizes(counts) == (13, 13, 12, 12)


def _fact_realization_compilation(finance_evidence: EvidenceItem):
    plugin = FinanceTaskPlugin()
    bundle = EvidenceBundle(
        bundle_id="bundle:qa_realization_helper",
        evidence=(finance_evidence,),
        purpose="qa realization helper fixture",
        graph_build_id="kg_test",
    )
    graph = ProofGraphBuilder().build(bundle)
    pattern = next(item for item in plugin.pattern_manifest if item.task_type == "fact_retrieval")
    binding = make_evidence_binding(
        pattern_id=pattern.pattern_id,
        pattern_version=pattern.pattern_version,
        pattern_hash=pattern.pattern_hash,
        role_bindings={"fact": (finance_evidence.evidence_id,)},
        source_graph_id=graph.graph_id,
        domain_snapshot_id=graph.source_build_id,
    )
    instantiation = plugin.compile_binding("fact_retrieval", graph, bundle, binding)
    return plugin.realize_instantiation(instantiation, graph, bundle), bundle, graph
