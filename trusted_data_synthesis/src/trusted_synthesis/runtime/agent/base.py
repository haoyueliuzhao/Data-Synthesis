from __future__ import annotations

from typing import Protocol

from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.runtime.tools import EvidenceToolRuntime


class AgentSolver(Protocol):
    """Stable public-only solver boundary for real and deterministic candidates."""

    def solve(self, task: TaskPublicSpec, environment: EvidenceToolRuntime) -> Trajectory: ...


class CandidateAgent(Protocol):
    """Backward-compatible candidate boundary used by existing experiments."""

    def generate(self, task: TaskPublicSpec, runtime: EvidenceToolRuntime) -> Trajectory: ...
