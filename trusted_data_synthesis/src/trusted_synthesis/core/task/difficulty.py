from __future__ import annotations

from collections import defaultdict, deque
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.program import TaskProgram


class TaskDifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"
    RESEARCH = "research"


class TaskDifficultyProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_count: float = Field(ge=1)
    graph_depth: float = Field(ge=0)
    program_depth: float = Field(ge=1)
    branch_factor: float = Field(ge=0)
    operation_count: float = Field(ge=1)
    semantic_constraint_count: float = Field(ge=0)
    semantic_alignment_cost: float = Field(ge=0)
    pattern_base_cost: float = Field(ge=0)
    total_score: float = Field(ge=0)
    level: TaskDifficultyLevel
    policy_version: str = "task_difficulty.v1"

    def numeric_features(self) -> dict[str, float]:
        return {
            key: float(value)
            for key, value in self.model_dump(mode="python").items()
            if isinstance(value, (int, float))
        }


def assess_task_difficulty(
    *,
    pattern: TaskPatternSpec,
    program: TaskProgram,
    proof_graph: ProofGraph,
    evidence_ids: tuple[str, ...],
    semantic_alignment_cost: float,
) -> TaskDifficultyProfile:
    structural = task_structure_features(program, proof_graph, evidence_ids)
    evidence_count = structural["evidence_count"]
    graph_depth = structural["graph_depth"]
    program_depth = structural["program_depth"]
    branch_factor = structural["branch_factor"]
    operation_count = structural["operation_count"]
    constraint_count = float(pattern.semantic_constraint_count)
    score = difficulty_score(
        evidence_count=evidence_count,
        graph_depth=graph_depth,
        program_depth=program_depth,
        branch_factor=branch_factor,
        operation_count=operation_count,
        semantic_constraint_count=constraint_count,
        semantic_alignment_cost=semantic_alignment_cost,
        pattern_base_cost=pattern.difficulty_base_cost,
    )
    return TaskDifficultyProfile(
        evidence_count=evidence_count,
        graph_depth=graph_depth,
        program_depth=program_depth,
        branch_factor=branch_factor,
        operation_count=operation_count,
        semantic_constraint_count=constraint_count,
        semantic_alignment_cost=semantic_alignment_cost,
        pattern_base_cost=pattern.difficulty_base_cost,
        total_score=score,
        level=difficulty_level(score, pattern.difficulty_base),
    )


def task_structure_features(
    program: TaskProgram,
    proof_graph: ProofGraph,
    evidence_ids: tuple[str, ...],
) -> dict[str, float]:
    return {
        "evidence_count": float(len(evidence_ids)),
        "graph_depth": float(_graph_depth(proof_graph, evidence_ids)),
        "program_depth": float(_program_depth(program)),
        "branch_factor": float(_program_branch_factor(program)),
        "operation_count": float(len(program.nodes)),
    }


def difficulty_score(
    *,
    evidence_count: float,
    graph_depth: float,
    program_depth: float,
    branch_factor: float,
    operation_count: float,
    semantic_constraint_count: float,
    semantic_alignment_cost: float,
    pattern_base_cost: float,
) -> float:
    score = (
        pattern_base_cost
        + evidence_count * 0.75
        + max(graph_depth - 1.0, 0.0) * 0.5
        + max(program_depth - 1.0, 0.0) * 1.5
        + branch_factor * 0.5
        + max(operation_count - 1.0, 0.0) * 0.5
        + semantic_constraint_count * 0.25
        + semantic_alignment_cost
    )
    return round(score, 6)


def _program_depth(program: TaskProgram) -> int:
    depths: dict[str, int] = {}
    for node in program.nodes:
        depths[node.node_id] = 1 + max(
            (depths[dependency] for dependency in node.dependencies),
            default=0,
        )
    return max(depths.values())


def _program_branch_factor(program: TaskProgram) -> int:
    dependents: dict[str, int] = defaultdict(int)
    for node in program.nodes:
        for dependency in node.dependencies:
            dependents[dependency] += 1
    return max(dependents.values(), default=0)


def _graph_depth(proof_graph: ProofGraph, evidence_ids: tuple[str, ...]) -> int:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in proof_graph.edges:
        adjacency[edge.source_id].add(edge.target_id)
        adjacency[edge.target_id].add(edge.source_id)
    relevant = [evidence_id for evidence_id in evidence_ids if evidence_id in adjacency]
    if not relevant:
        return 0
    longest = 0
    for root in relevant:
        distances = {root: 0}
        queue: deque[str] = deque((root,))
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor in distances:
                    continue
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
        longest = max(longest, max(distances.values(), default=0))
    return longest


def difficulty_level(score: float, pattern_base: str) -> TaskDifficultyLevel:
    score_level = (
        TaskDifficultyLevel.EASY
        if score < 5
        else TaskDifficultyLevel.MEDIUM
        if score < 9
        else TaskDifficultyLevel.HARD
        if score < 14
        else TaskDifficultyLevel.EXPERT
        if score < 21
        else TaskDifficultyLevel.RESEARCH
    )
    base_level = TaskDifficultyLevel(pattern_base)
    ordering = tuple(TaskDifficultyLevel)
    return ordering[max(ordering.index(score_level), ordering.index(base_level))]
