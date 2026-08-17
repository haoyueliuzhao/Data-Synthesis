# ruff: noqa: F401 - TYPE_CHECKING imports define the lazy public API.

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from trusted_synthesis.core.trajectory.admission import (
        ExecutableComponentManifest,
        JointCompilationAdmissionArtifact,
        JointCompilationAuditEvidence,
        RuntimeAuthorityPolicy,
        RuntimePublicProjection,
        admit_joint_compilation,
        make_executable_component_manifest,
        make_joint_compilation_audit_evidence,
        make_runtime_authority_policy,
        make_runtime_public_projection,
    )
    from trusted_synthesis.core.trajectory.attributes import (
        TrajectoryAttributeProfile,
        TrajectoryAttributes,
        expected_trajectory_attributes,
        extract_trajectory_attributes,
    )
    from trusted_synthesis.core.trajectory.candidate_verifier import (
        CandidateWorkflowVerifier,
    )
    from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
    from trusted_synthesis.core.trajectory.pool import (
        TrajectoryCandidateProviderProtocol,
        TrajectoryPoolMaterializationReport,
        ValidTrajectoryMaterializer,
        ValidTrajectoryPool,
        ValidTrajectoryPoolBuilder,
    )
    from trusted_synthesis.core.trajectory.scaffolding import (
        CapabilityAwarePublicProjection,
        CapabilityPrerequisiteGraph,
        CapabilityPrerequisiteNode,
        CapabilityScaffoldAdmissionArtifact,
        CapabilityScaffoldGateEvidence,
        CapabilityScaffoldLadderCompilation,
        CompiledPublicStateSummary,
        CompiledTaskConditionLineage,
        MinimalPublicStateSummarySpec,
        PublicStateObservation,
        ScaffoldInvariantStateMappingContract,
        ScaffoldSeparatedTrajectoryView,
        admit_capability_scaffold_ladder,
        compile_capability_scaffold_ladder,
        compile_public_state_summary,
        make_capability_prerequisite_graph,
        make_capability_prerequisite_node,
        make_capability_scaffold_gate_evidence,
        make_compiled_task_condition_lineage,
        make_minimal_public_state_summary_spec,
        make_public_state_observation,
        make_scaffold_invariant_state_mapping_contract,
        scaffold_gate_checks,
        separate_scaffold_trace_for_state_mapping,
    )
    from trusted_synthesis.core.trajectory.schema import (
        ActionType,
        Trajectory,
        TrajectoryStep,
        WorkflowKind,
    )
    from trusted_synthesis.core.trajectory.specification import (
        JointCompilationArtifact,
        OmegaComponentManifest,
        OracleExecutionSpecification,
        ReferenceExecutionIdentity,
        TrajectoryVerificationContext,
        make_joint_compilation_artifact,
        make_omega_component_manifest,
        make_oracle_execution_specification,
        make_trajectory_verification_context,
    )
    from trusted_synthesis.core.trajectory.state import (
        CanonicalTrajectoryGraph,
        TrajectoryState,
        TrajectoryStateAssignment,
        map_trajectory_to_state,
        trajectory_decision_trace_hash,
    )
    from trusted_synthesis.core.trajectory.validity import (
        TrajectoryValidityEvaluator,
        TrajectoryValidityReport,
    )
    from trusted_synthesis.core.trajectory.verifier import ReferenceWorkflowVerifier

_EXPORTS = {
    "ActionType": ("trusted_synthesis.core.trajectory.schema", "ActionType"),
    "CapabilityAwarePublicProjection": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "CapabilityAwarePublicProjection",
    ),
    "CapabilityPrerequisiteGraph": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "CapabilityPrerequisiteGraph",
    ),
    "CapabilityPrerequisiteNode": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "CapabilityPrerequisiteNode",
    ),
    "CapabilityScaffoldAdmissionArtifact": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "CapabilityScaffoldAdmissionArtifact",
    ),
    "CapabilityScaffoldGateEvidence": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "CapabilityScaffoldGateEvidence",
    ),
    "CapabilityScaffoldLadderCompilation": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "CapabilityScaffoldLadderCompilation",
    ),
    "CompiledPublicStateSummary": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "CompiledPublicStateSummary",
    ),
    "CompiledTaskConditionLineage": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "CompiledTaskConditionLineage",
    ),
    "ExecutableComponentManifest": (
        "trusted_synthesis.core.trajectory.admission",
        "ExecutableComponentManifest",
    ),
    "JointCompilationAdmissionArtifact": (
        "trusted_synthesis.core.trajectory.admission",
        "JointCompilationAdmissionArtifact",
    ),
    "JointCompilationAuditEvidence": (
        "trusted_synthesis.core.trajectory.admission",
        "JointCompilationAuditEvidence",
    ),
    "JointCompilationArtifact": (
        "trusted_synthesis.core.trajectory.specification",
        "JointCompilationArtifact",
    ),
    "MinimalPublicStateSummarySpec": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "MinimalPublicStateSummarySpec",
    ),
    "PublicStateObservation": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "PublicStateObservation",
    ),
    "ScaffoldInvariantStateMappingContract": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "ScaffoldInvariantStateMappingContract",
    ),
    "ScaffoldSeparatedTrajectoryView": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "ScaffoldSeparatedTrajectoryView",
    ),
    "OmegaComponentManifest": (
        "trusted_synthesis.core.trajectory.specification",
        "OmegaComponentManifest",
    ),
    "RuntimePublicProjection": (
        "trusted_synthesis.core.trajectory.admission",
        "RuntimePublicProjection",
    ),
    "RuntimeAuthorityPolicy": (
        "trusted_synthesis.core.trajectory.admission",
        "RuntimeAuthorityPolicy",
    ),
    "OracleExecutionSpecification": (
        "trusted_synthesis.core.trajectory.specification",
        "OracleExecutionSpecification",
    ),
    "ReferenceExecutionIdentity": (
        "trusted_synthesis.core.trajectory.specification",
        "ReferenceExecutionIdentity",
    ),
    "TrajectoryAttributeProfile": (
        "trusted_synthesis.core.trajectory.attributes",
        "TrajectoryAttributeProfile",
    ),
    "TrajectoryAttributes": (
        "trusted_synthesis.core.trajectory.attributes",
        "TrajectoryAttributes",
    ),
    "TrajectoryValidityEvaluator": (
        "trusted_synthesis.core.trajectory.validity",
        "TrajectoryValidityEvaluator",
    ),
    "CanonicalTrajectoryGraph": (
        "trusted_synthesis.core.trajectory.state",
        "CanonicalTrajectoryGraph",
    ),
    "TrajectoryState": (
        "trusted_synthesis.core.trajectory.state",
        "TrajectoryState",
    ),
    "TrajectoryStateAssignment": (
        "trusted_synthesis.core.trajectory.state",
        "TrajectoryStateAssignment",
    ),
    "map_trajectory_to_state": (
        "trusted_synthesis.core.trajectory.state",
        "map_trajectory_to_state",
    ),
    "trajectory_decision_trace_hash": (
        "trusted_synthesis.core.trajectory.state",
        "trajectory_decision_trace_hash",
    ),
    "TrajectoryValidityReport": (
        "trusted_synthesis.core.trajectory.validity",
        "TrajectoryValidityReport",
    ),
    "TrajectoryVerificationContext": (
        "trusted_synthesis.core.trajectory.specification",
        "TrajectoryVerificationContext",
    ),
    "TrajectoryCandidateProviderProtocol": (
        "trusted_synthesis.core.trajectory.pool",
        "TrajectoryCandidateProviderProtocol",
    ),
    "TrajectoryPoolMaterializationReport": (
        "trusted_synthesis.core.trajectory.pool",
        "TrajectoryPoolMaterializationReport",
    ),
    "ValidTrajectoryMaterializer": (
        "trusted_synthesis.core.trajectory.pool",
        "ValidTrajectoryMaterializer",
    ),
    "ValidTrajectoryPool": (
        "trusted_synthesis.core.trajectory.pool",
        "ValidTrajectoryPool",
    ),
    "ValidTrajectoryPoolBuilder": (
        "trusted_synthesis.core.trajectory.pool",
        "ValidTrajectoryPoolBuilder",
    ),
    "expected_trajectory_attributes": (
        "trusted_synthesis.core.trajectory.attributes",
        "expected_trajectory_attributes",
    ),
    "extract_trajectory_attributes": (
        "trusted_synthesis.core.trajectory.attributes",
        "extract_trajectory_attributes",
    ),
    "admit_joint_compilation": (
        "trusted_synthesis.core.trajectory.admission",
        "admit_joint_compilation",
    ),
    "admit_capability_scaffold_ladder": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "admit_capability_scaffold_ladder",
    ),
    "compile_capability_scaffold_ladder": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "compile_capability_scaffold_ladder",
    ),
    "compile_public_state_summary": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "compile_public_state_summary",
    ),
    "make_compiled_task_condition_lineage": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "make_compiled_task_condition_lineage",
    ),
    "make_executable_component_manifest": (
        "trusted_synthesis.core.trajectory.admission",
        "make_executable_component_manifest",
    ),
    "make_joint_compilation_audit_evidence": (
        "trusted_synthesis.core.trajectory.admission",
        "make_joint_compilation_audit_evidence",
    ),
    "make_capability_prerequisite_graph": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "make_capability_prerequisite_graph",
    ),
    "make_capability_prerequisite_node": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "make_capability_prerequisite_node",
    ),
    "make_capability_scaffold_gate_evidence": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "make_capability_scaffold_gate_evidence",
    ),
    "make_minimal_public_state_summary_spec": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "make_minimal_public_state_summary_spec",
    ),
    "make_public_state_observation": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "make_public_state_observation",
    ),
    "make_scaffold_invariant_state_mapping_contract": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "make_scaffold_invariant_state_mapping_contract",
    ),
    "make_runtime_public_projection": (
        "trusted_synthesis.core.trajectory.admission",
        "make_runtime_public_projection",
    ),
    "make_runtime_authority_policy": (
        "trusted_synthesis.core.trajectory.admission",
        "make_runtime_authority_policy",
    ),
    "scaffold_gate_checks": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "scaffold_gate_checks",
    ),
    "separate_scaffold_trace_for_state_mapping": (
        "trusted_synthesis.core.trajectory.scaffolding",
        "separate_scaffold_trace_for_state_mapping",
    ),
    "make_joint_compilation_artifact": (
        "trusted_synthesis.core.trajectory.specification",
        "make_joint_compilation_artifact",
    ),
    "make_omega_component_manifest": (
        "trusted_synthesis.core.trajectory.specification",
        "make_omega_component_manifest",
    ),
    "make_oracle_execution_specification": (
        "trusted_synthesis.core.trajectory.specification",
        "make_oracle_execution_specification",
    ),
    "make_trajectory_verification_context": (
        "trusted_synthesis.core.trajectory.specification",
        "make_trajectory_verification_context",
    ),
    "CandidateWorkflowVerifier": (
        "trusted_synthesis.core.trajectory.candidate_verifier",
        "CandidateWorkflowVerifier",
    ),
    "ReferenceWorkflowCompiler": (
        "trusted_synthesis.core.trajectory.generator",
        "ReferenceWorkflowCompiler",
    ),
    "ReferenceWorkflowVerifier": (
        "trusted_synthesis.core.trajectory.verifier",
        "ReferenceWorkflowVerifier",
    ),
    "Trajectory": ("trusted_synthesis.core.trajectory.schema", "Trajectory"),
    "TrajectoryStep": ("trusted_synthesis.core.trajectory.schema", "TrajectoryStep"),
    "WorkflowKind": ("trusted_synthesis.core.trajectory.schema", "WorkflowKind"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
