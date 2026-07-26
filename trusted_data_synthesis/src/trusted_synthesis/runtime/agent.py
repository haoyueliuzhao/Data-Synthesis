from __future__ import annotations

from typing import Protocol

from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.runtime.tools import EvidenceToolRuntime


class CandidateAgent(Protocol):
    """Public-only agent boundary; concrete behavior belongs to a domain or experiment."""

    def generate(self, task: TaskPublicSpec, runtime: EvidenceToolRuntime) -> Trajectory: ...
