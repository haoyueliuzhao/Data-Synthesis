from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SupportEstimate:
    evaluated_binding_count: int
    completed_binding_count: int
    semantic_pass_count: int
    operation_pass_count: int
    unique_answer_count: int

    @property
    def completion_rate(self) -> float:
        return (
            self.completed_binding_count / self.evaluated_binding_count
            if self.evaluated_binding_count
            else 0.0
        )

    @property
    def unique_answer_rate(self) -> float:
        return (
            self.unique_answer_count / self.operation_pass_count
            if self.operation_pass_count
            else 0.0
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "evaluated_binding_count": self.evaluated_binding_count,
            "completed_binding_count": self.completed_binding_count,
            "semantic_pass_count": self.semantic_pass_count,
            "operation_pass_count": self.operation_pass_count,
            "unique_answer_count": self.unique_answer_count,
            "completion_rate": self.completion_rate,
            "unique_answer_rate": self.unique_answer_rate,
        }
