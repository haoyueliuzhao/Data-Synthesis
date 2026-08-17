from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.audit_artifacts import (
    atomic_audit_case_id,
    make_atomic_audit_case_result,
)
from trusted_synthesis.core.evaluation.contracts import QualityContractCompiler
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.trajectory.admission import (
    DESTRUCTIVE_MUTATION_CHECKS,
    EXECUTABLE_CLOSURE_CHECKS,
    PUBLIC_SUFFICIENCY_CHECKS,
    admit_joint_compilation,
    make_executable_component_manifest,
    make_joint_compilation_audit_evidence,
    make_runtime_public_projection,
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
    variation_provider_id: str = "joint_admission_contract_provider"
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
                verification_requirement="output",
                lineage_requirement="citation_minimum",
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


def _compile(case: ContractCase):
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
    return artifacts, state_space


def _audit(kind: str, joint_id: str, *, failed_check: str | None = None):
    expected = {
        "public_sufficiency": PUBLIC_SUFFICIENCY_CHECKS,
        "executable_closure": EXECUTABLE_CLOSURE_CHECKS,
        "destructive_mutation": DESTRUCTIVE_MUTATION_CHECKS,
    }[kind]
    return make_joint_compilation_audit_evidence(
        audit_kind=kind,  # type: ignore[arg-type]
        joint_compilation_id=joint_id,
        case_results=tuple(
            make_atomic_audit_case_result(
                check_id=item,
                subject_id=joint_id,
                input_artifact_ids=(joint_id,),
                output_artifact_ids=(f"audit:{kind}:{item}",),
                implementation_manifest={
                    "auditor_id": f"contract_suite.{kind}",
                    "auditor_version": "1.0.0",
                    "check_id": item,
                },
                replay_implementation_manifest={
                    "auditor_id": f"contract_suite.{kind}.independent",
                    "auditor_version": "1.0.0",
                    "check_id": item,
                },
                check_passed=item != failed_check,
            )
            for item in expected
        ),
        auditor_id=f"contract_suite.{kind}",
        auditor_version="1.0.0",
    )


def _component(kind: str, joint_id: str):
    component_id = f"contract_suite.{kind}"
    replay = make_atomic_audit_case_result(
        check_id=f"{kind}_contract_replay",
        subject_id=component_id,
        input_artifact_ids=(joint_id,),
        output_artifact_ids=(component_id,),
        implementation_manifest={
            "component_id": component_id,
            "component_version": "1.0.0",
            "check_id": f"{kind}_contract_replay",
        },
        replay_implementation_manifest={
            "component_id": f"{component_id}.independent",
            "component_version": "1.0.0",
            "check_id": f"{kind}_contract_replay",
        },
        check_passed=True,
    )
    return make_executable_component_manifest(
        component_kind=kind,  # type: ignore[arg-type]
        component_id=component_id,
        component_version="1.0.0",
        joint_compilation_id=joint_id,
        input_schema={"joint_compilation_id": "string"},
        output_schema={"passed": "boolean"},
        replay_case=replay,
    )


@pytest.mark.parametrize("case", build_contract_cases(), ids=lambda item: item.domain)
def test_joint_compilation_admission_is_reused_across_domains(case: ContractCase) -> None:
    artifacts, state_space = _compile(case)
    joint_id = artifacts.joint_compilation.artifact_id
    projections = tuple(
        make_runtime_public_projection(artifacts, state_space, runtime_id=runtime_id)
        for runtime_id in ("scripted", "autonomous")
    )
    admission = admit_joint_compilation(
        artifacts,
        state_space,
        runtime_projections=projections,
        public_sufficiency_evidence=_audit("public_sufficiency", joint_id),
        executable_closure_evidence=_audit("executable_closure", joint_id),
        destructive_mutation_evidence=_audit("destructive_mutation", joint_id),
        verifier_manifest=_component("independent_verifier", joint_id),
        materialization_manifest=_component("trajectory_materializer", joint_id),
    )

    assert admission.status == "admitted"
    assert admission.next_transition == "agent_state_discovery"
    assert all(admission.gates.values())
    assert admission.model_api_calls == 0
    assert admission.gpu_jobs == 0
    assert {item.runtime_id for item in admission.runtime_projections} == {
        "scripted",
        "autonomous",
    }


def test_failed_destructive_mutation_audit_routes_only_to_compiler_repair() -> None:
    case = build_contract_cases()[0]
    artifacts, state_space = _compile(case)
    joint_id = artifacts.joint_compilation.artifact_id
    projection = make_runtime_public_projection(
        artifacts,
        state_space,
        runtime_id="autonomous",
    )
    admission = admit_joint_compilation(
        artifacts,
        state_space,
        runtime_projections=(projection,),
        public_sufficiency_evidence=_audit("public_sufficiency", joint_id),
        executable_closure_evidence=_audit("executable_closure", joint_id),
        destructive_mutation_evidence=_audit(
            "destructive_mutation",
            joint_id,
            failed_check="mutate_state_mapper_rejected",
        ),
        verifier_manifest=_component("independent_verifier", joint_id),
        materialization_manifest=_component("trajectory_materializer", joint_id),
    )

    assert admission.status == "blocked"
    assert admission.blockers == ("destructive_mutation_rejection",)
    assert admission.next_transition == "joint_compilation_repair_only"


def test_runtime_projection_rejects_a_detached_state_space() -> None:
    legal, science = build_contract_cases()
    legal_artifacts, _ = _compile(legal)
    _, science_state_space = _compile(science)

    with pytest.raises(ValueError, match="detached from Joint Compilation"):
        make_runtime_public_projection(
            legal_artifacts,
            science_state_space,
            runtime_id="autonomous",
        )


def test_admission_rejects_caller_forged_gate_and_swapped_audit_kind() -> None:
    case = build_contract_cases()[0]
    artifacts, state_space = _compile(case)
    joint_id = artifacts.joint_compilation.artifact_id
    projection = make_runtime_public_projection(
        artifacts,
        state_space,
        runtime_id="autonomous",
    )
    admission = admit_joint_compilation(
        artifacts,
        state_space,
        runtime_projections=(projection,),
        public_sufficiency_evidence=_audit("public_sufficiency", joint_id),
        executable_closure_evidence=_audit("executable_closure", joint_id),
        destructive_mutation_evidence=_audit("destructive_mutation", joint_id),
        verifier_manifest=_component("independent_verifier", joint_id),
        materialization_manifest=_component("trajectory_materializer", joint_id),
    )
    forged = admission.model_dump(mode="json")
    forged["gates"]["semantic_closure"] = False
    with pytest.raises(ValidationError, match="not derived from Evidence"):
        type(admission).model_validate(forged)

    swapped = admission.model_dump(mode="json")
    swapped["public_sufficiency_evidence"] = admission.executable_closure_evidence.model_dump(
        mode="json"
    )
    with pytest.raises(ValidationError, match="Evidence kind is invalid"):
        type(admission).model_validate(swapped)


def test_atomic_audit_case_rejects_manifest_tampering_after_outer_rehash() -> None:
    case = make_atomic_audit_case_result(
        check_id="implementation_identity_required",
        subject_id="joint:test",
        input_artifact_ids=("joint:test",),
        output_artifact_ids=("audit:test",),
        implementation_manifest={"implementation": "primary.v1"},
        replay_implementation_manifest={"implementation": "independent.v1"},
        check_passed=True,
    )
    provisional = case.model_copy(
        update={
            "implementation_manifest": {"implementation": "substituted.v1"},
            "case_id": "pending",
        }
    )
    payload = provisional.model_dump(mode="json")
    payload["case_id"] = atomic_audit_case_id(provisional)

    with pytest.raises(ValidationError, match="implementation manifest hash is invalid"):
        type(case).model_validate(payload)


def test_atomic_audit_case_rejects_payload_tampering_after_outer_rehash() -> None:
    case = make_atomic_audit_case_result(
        check_id="independent_replay_required",
        subject_id="joint:test",
        input_artifact_ids=("joint:test",),
        output_artifact_ids=("audit:test",),
        implementation_manifest={"implementation": "primary.v1"},
        replay_implementation_manifest={"implementation": "independent.v1"},
        check_passed=True,
        result_details={"evaluated_cases": 8},
    )
    payload = case.model_dump(mode="json")
    payload["result_payload"]["details"]["evaluated_cases"] = 0
    payload["case_id"] = "atomic_audit_case:outer_rehashed"

    with pytest.raises(ValidationError, match="result payload hash is invalid"):
        type(case).model_validate(payload)
