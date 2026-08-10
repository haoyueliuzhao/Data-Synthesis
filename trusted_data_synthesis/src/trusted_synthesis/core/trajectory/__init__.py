# ruff: noqa: F401 - TYPE_CHECKING imports define the lazy public API.

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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
    "JointCompilationArtifact": (
        "trusted_synthesis.core.trajectory.specification",
        "JointCompilationArtifact",
    ),
    "OmegaComponentManifest": (
        "trusted_synthesis.core.trajectory.specification",
        "OmegaComponentManifest",
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
