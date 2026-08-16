from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.evaluation.contracts import QualityContractCompiler
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.trajectory.admission import (
    DESTRUCTIVE_MUTATION_CHECKS,
    EXECUTABLE_CLOSURE_CHECKS,
    PUBLIC_SUFFICIENCY_CHECKS,
    admit_joint_compilation,
    make_joint_compilation_audit_evidence,
    make_runtime_public_projection,
)
from trusted_synthesis.core.trajectory.scaffolding import (
    SCAFFOLD_AIDS_BY_LEVEL,
    SCAFFOLD_GATES,
    SCAFFOLD_LEVELS,
    CapabilityScaffoldLadderCompilation,
    admit_capability_scaffold_ladder,
    compile_capability_scaffold_ladder,
    make_capability_prerequisite_graph,
    make_capability_prerequisite_node,
    make_capability_scaffold_gate_evidence,
    make_minimal_public_state_summary_spec,
    make_scaffold_invariant_state_mapping_contract,
    scaffold_gate_checks,
    separate_scaffold_trace_for_state_mapping,
)
from trusted_synthesis.core.trajectory.specification import TrajectoryVerificationContext
from trusted_synthesis.core.vtdo.state_space import (
    AdmissibleTrajectoryVariation,
    compile_trajectory_state_space,
    make_admissible_trajectory_variation,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    ContractCase,
    build_contract_cases,
)


@dataclass(frozen=True)
class _VariationProvider:
    variation_provider_id: str = "capability_scaffold_contract_provider"
    variation_provider_version: str = "1.0.0"

    def compile_variations(
        self,
        context: TrajectoryVerificationContext,
    ) -> tuple[AdmissibleTrajectoryVariation, ...]:
        del context
        return (
            make_admissible_trajectory_variation(
                acquisition_requirement="bounded",
                evidence_support_requirement="required_roles",
                minimum_tool_calls=1,
                minimum_evidence_count=1,
            ),
            make_admissible_trajectory_variation(
                acquisition_requirement="multi_stage",
                evidence_support_requirement="expanded_context",
                execution_requirement="composed_execution",
                verification_requirement="full",
                lineage_requirement="full",
                minimum_tool_calls=3,
                minimum_evidence_count=2,
                minimum_reasoning_depth=2,
                minimum_verification_degree=1.0,
            ),
        )


def _joint_audit(kind: str, joint_id: str):
    expected = {
        "public_sufficiency": PUBLIC_SUFFICIENCY_CHECKS,
        "executable_closure": EXECUTABLE_CLOSURE_CHECKS,
        "destructive_mutation": DESTRUCTIVE_MUTATION_CHECKS,
    }[kind]
    return make_joint_compilation_audit_evidence(
        audit_kind=kind,  # type: ignore[arg-type]
        joint_compilation_id=joint_id,
        checks={item: True for item in expected},
        auditor_id=f"contract.{kind}",
        auditor_version="1.0.0",
    )


def _compile_admitted(case: ContractCase):
    quality = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    artifacts = ProofCarryingSampleCompiler(
        case.registry,
        quality,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
    ).compile(
        case.task,
        case.bundle,
        case.proof_graph,
        public_corpus=case.corpus,
    )
    state_space = compile_trajectory_state_space(
        artifacts.joint_compilation,
        _VariationProvider(),
    )
    joint_id = artifacts.joint_compilation.artifact_id
    projections = tuple(
        make_runtime_public_projection(artifacts, state_space, runtime_id=runtime_id)
        for runtime_id in ("scripted", "autonomous")
    )
    admission = admit_joint_compilation(
        artifacts,
        state_space,
        runtime_projections=projections,
        public_sufficiency_evidence=_joint_audit("public_sufficiency", joint_id),
        executable_closure_evidence=_joint_audit("executable_closure", joint_id),
        destructive_mutation_evidence=_joint_audit("destructive_mutation", joint_id),
        verifier_id=f"{case.domain}.independent_verifier",
        verifier_version="1.0.0",
        materialization_contract_id=f"{case.domain}.materialization",
        materialization_contract_version="1.0.0",
    )
    return artifacts, admission


def _graph(target_capability: str, *, requirement_override: str | None = None):
    identify = make_capability_prerequisite_node(
        node_key="identify_public_state",
        capability_id="state_interpretation",
        public_requirement_id="identify_the_public_relation_state",
        observable_input_kinds=("public_relation_state",),
        model_decision_kind="relation_classification",
        allowed_public_effects=("update_public_completion_state",),
        completion_evaluator_id="host.state_interpretation",
        completion_evaluator_version="1.0.0",
    )
    decide = make_capability_prerequisite_node(
        node_key="make_target_decision",
        capability_id=target_capability,
        public_requirement_id=requirement_override or "make_the_target_decision",
        prerequisite_node_keys=("identify_public_state",),
        observable_input_kinds=("public_relation_state", "public_completion_condition"),
        model_decision_kind="tool_category_selection",
        allowed_public_effects=("acquire_public_evidence",),
        completion_evaluator_id="host.target_decision",
        completion_evaluator_version="1.0.0",
    )
    return make_capability_prerequisite_graph(
        target_capability_id=target_capability,
        nodes=(identify, decide),
        target_node_keys=("make_target_decision",),
    )


def _summary():
    return make_minimal_public_state_summary_spec(
        compiler_id="contract.public_state_summary",
        compiler_version="1.0.0",
        source_kinds=("task_public", "public_tool_observation", "public_runtime_counter"),
        included_fields=(
            "completed_operation_types",
            "unmet_public_preconditions",
            "remaining_tool_budget",
        ),
    )


def _ladder(case: ContractCase) -> CapabilityScaffoldLadderCompilation:
    artifacts, admission = _compile_admitted(case)
    mapping = make_scaffold_invariant_state_mapping_contract(admission)
    return compile_capability_scaffold_ladder(
        artifacts,
        admission,
        runtime_id="autonomous",
        target_capability_id=f"{case.domain}_target_capability",
        scaffold_policy_version="bridge_policy.v1",
        dependency_graph=_graph(f"{case.domain}_target_capability"),
        summary_spec=_summary(),
        state_mapping_contract=mapping,
    )


def _gate_evidence(
    ladder: CapabilityScaffoldLadderCompilation,
    *,
    failed: tuple[str, str] | None = None,
):
    rows = []
    for projection in ladder.projections:
        for gate in SCAFFOLD_GATES:
            checks = {
                check: (projection.scaffold_level, gate) != failed
                for check in scaffold_gate_checks(projection.scaffold_level, gate)
            }
            rows.append(
                make_capability_scaffold_gate_evidence(
                    ladder_id=ladder.ladder_id,
                    projection_id=projection.projection_id,
                    joint_compilation_id=ladder.joint_compilation_id,
                    scaffold_level=projection.scaffold_level,
                    gate=gate,
                    checks=checks,
                    audit_case_ids=(f"case:{projection.scaffold_level}:{gate}",),
                    evaluator_id=f"contract.{gate}",
                    evaluator_version="1.0.0",
                )
            )
    return tuple(rows)


@pytest.mark.parametrize("case", build_contract_cases(), ids=lambda item: item.domain)
def test_capability_scaffold_compiles_the_same_core_contract_across_domains(
    case: ContractCase,
) -> None:
    ladder = _ladder(case)

    assert tuple(item.scaffold_level for item in ladder.projections) == SCAFFOLD_LEVELS
    assert tuple(item.aid_kinds for item in ladder.projections) == tuple(
        SCAFFOLD_AIDS_BY_LEVEL[level] for level in SCAFFOLD_LEVELS
    )
    assert len({item.compiled_task_condition_id for item in ladder.projections}) == 4
    assert all(
        item.joint_compilation_id == ladder.joint_compilation_id for item in ladder.projections
    )
    assert ladder.projections[1].public_summary_spec is not None
    assert ladder.projections[2].public_capability_nodes
    assert not ladder.projections[2].public_dependency_edges
    assert ladder.projections[3].public_dependency_edges
    assert ladder.valid_state_space_invariant_across_levels
    assert ladder.scaffold_changes_reachability_only
    assert len({item.state_mapping_contract_id for item in ladder.projections}) == 1
    public_payload = json.dumps(
        ladder.projections[3].model_dump(mode="json"),
        sort_keys=True,
    )
    assert "host.target_decision" not in public_payload

    admission = admit_capability_scaffold_ladder(ladder, _gate_evidence(ladder))
    assert admission.status == "admitted"
    assert admission.next_transition == "bridge_rollout_development"
    assert admission.model_api_calls == 0
    assert admission.gpu_jobs == 0


def test_failed_incremental_necessity_routes_only_to_scaffold_repair() -> None:
    ladder = _ladder(build_contract_cases()[0])
    admission = admit_capability_scaffold_ladder(
        ladder,
        _gate_evidence(ladder, failed=("gamma_2", "incremental_necessity")),
    )

    assert admission.status == "blocked"
    assert admission.blockers == ("gamma_2:incremental_necessity",)
    assert admission.next_transition == "capability_scaffold_repair_only"


def test_capability_scaffold_rejects_oracle_identity_in_public_requirement() -> None:
    case = build_contract_cases()[0]
    artifacts, admission = _compile_admitted(case)
    mapping = make_scaffold_invariant_state_mapping_contract(admission)
    leaked_requirement = artifacts.joint_compilation.omega.task.oracle.gold_evidence_ids[0]

    with pytest.raises(ValueError, match="leaks Oracle-only content"):
        compile_capability_scaffold_ladder(
            artifacts,
            admission,
            runtime_id="autonomous",
            target_capability_id="legal_target_capability",
            scaffold_policy_version="bridge_policy.v1",
            dependency_graph=_graph(
                "legal_target_capability",
                requirement_override=leaked_requirement,
            ),
            summary_spec=_summary(),
            state_mapping_contract=mapping,
        )


def test_capability_graph_rejects_cycles() -> None:
    first = make_capability_prerequisite_node(
        node_key="first",
        capability_id="planning",
        public_requirement_id="first_requirement",
        prerequisite_node_keys=("second",),
        observable_input_kinds=("public_relation_state",),
        model_decision_kind="relation_classification",
        allowed_public_effects=("update_public_completion_state",),
        completion_evaluator_id="host.first",
        completion_evaluator_version="1.0.0",
    )
    second = make_capability_prerequisite_node(
        node_key="second",
        capability_id="planning",
        public_requirement_id="second_requirement",
        prerequisite_node_keys=("first",),
        observable_input_kinds=("public_completion_condition",),
        model_decision_kind="tool_category_selection",
        allowed_public_effects=("acquire_public_evidence",),
        completion_evaluator_id="host.second",
        completion_evaluator_version="1.0.0",
    )

    with pytest.raises(ValueError, match="contains a cycle"):
        make_capability_prerequisite_graph(
            target_capability_id="planning",
            nodes=(first, second),
            target_node_keys=("second",),
        )


def test_gamma_three_accepts_a_single_node_capability_dag() -> None:
    case = build_contract_cases()[1]
    artifacts, admission = _compile_admitted(case)
    mapping = make_scaffold_invariant_state_mapping_contract(admission)
    target = make_capability_prerequisite_node(
        node_key="make_target_decision",
        capability_id="science_target_capability",
        public_requirement_id="make_the_target_decision",
        observable_input_kinds=("public_completion_condition",),
        model_decision_kind="candidate_verification",
        allowed_public_effects=("validate_public_candidate",),
        completion_evaluator_id="host.target_decision",
        completion_evaluator_version="1.0.0",
    )
    graph = make_capability_prerequisite_graph(
        target_capability_id="science_target_capability",
        nodes=(target,),
        target_node_keys=("make_target_decision",),
    )

    ladder = compile_capability_scaffold_ladder(
        artifacts,
        admission,
        runtime_id="autonomous",
        target_capability_id="science_target_capability",
        scaffold_policy_version="bridge_policy.v1",
        dependency_graph=graph,
        summary_spec=_summary(),
        state_mapping_contract=mapping,
    )

    assert ladder.projections[3].public_capability_nodes
    assert ladder.projections[3].public_dependency_edges == ()


def test_scaffold_trace_changes_do_not_change_behavior_state_identity() -> None:
    _, admission = _compile_admitted(build_contract_cases()[0])
    mapping = make_scaffold_invariant_state_mapping_contract(admission)
    behavior = {
        "tool_choice": "retrieve",
        "tool_arguments": {"query": "public rule"},
        "evidence_selection": ["public:evidence:1"],
        "stop_decision": "continue",
    }

    gamma_one = separate_scaffold_trace_for_state_mapping(
        mapping,
        behavior_payload=behavior,
        scaffold_trace={
            "scaffold_level": "gamma_1",
            "public_state_summary": {"remaining_tool_budget": 2},
        },
    )
    gamma_three = separate_scaffold_trace_for_state_mapping(
        mapping,
        behavior_payload=behavior,
        scaffold_trace={
            "scaffold_level": "gamma_3",
            "public_state_summary": {"remaining_tool_budget": 2},
            "public_subgoal_dag": [["identify", "decide"]],
        },
    )

    assert gamma_one.behavior_state_identity == gamma_three.behavior_state_identity
    assert gamma_one.scaffold_trace_hash != gamma_three.scaffold_trace_hash
    assert gamma_one.view_id != gamma_three.view_id


def test_public_summary_rejects_unregistered_fields() -> None:
    with pytest.raises(ValidationError):
        make_minimal_public_state_summary_spec(
            compiler_id="contract.public_state_summary",
            compiler_version="1.0.0",
            source_kinds=("task_public",),
            included_fields=("correct_action",),  # type: ignore[arg-type]
        )
