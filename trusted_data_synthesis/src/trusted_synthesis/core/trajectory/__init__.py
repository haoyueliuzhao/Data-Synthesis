# ruff: noqa: F401 - TYPE_CHECKING imports define the lazy public API.

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from trusted_synthesis.core.trajectory.candidate_verifier import (
        CandidateWorkflowVerifier,
    )
    from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
    from trusted_synthesis.core.trajectory.schema import (
        ActionType,
        Trajectory,
        TrajectoryStep,
        WorkflowKind,
    )
    from trusted_synthesis.core.trajectory.verifier import ReferenceWorkflowVerifier

_EXPORTS = {
    "ActionType": ("trusted_synthesis.core.trajectory.schema", "ActionType"),
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
