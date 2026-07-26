from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evaluation.counterfactual.schema import MinimalityReport
from trusted_synthesis.core.trajectory.schema import Trajectory

MINIMALITY_VALIDATOR_VERSION = "counterfactual_minimality.v1"


def validate_minimality(
    source: Trajectory,
    mutated: Trajectory,
    allowed_json_path_prefixes: tuple[str, ...],
    *,
    threshold: float = 0.9,
) -> MinimalityReport:
    source_value = source.model_dump(
        mode="json",
        exclude={"trajectory_id", "generator_version"},
    )
    mutated_value = mutated.model_dump(
        mode="json",
        exclude={"trajectory_id", "generator_version"},
    )
    changed = tuple(_changed_paths(source_value, mutated_value))
    if not changed:
        raise ValueError("counterfactual operator did not change the source trajectory")
    unexpected = tuple(
        path
        for path in changed
        if not any(_path_allowed(path, prefix) for prefix in allowed_json_path_prefixes)
    )
    leaf_count = max(_leaf_count(source_value), 1)
    edit_count = len(changed)
    normalized_distance = min(edit_count / leaf_count, 1.0)
    score = 1.0 - normalized_distance
    return MinimalityReport(
        changed_json_paths=changed,
        allowed_json_path_prefixes=allowed_json_path_prefixes,
        unexpected_json_paths=unexpected,
        source_leaf_count=leaf_count,
        edit_count=edit_count,
        semantic_factor_count=1,
        normalized_edit_distance=normalized_distance,
        minimality_score=score,
        threshold=threshold,
        passed=not unexpected and score >= threshold,
        validator_version=MINIMALITY_VALIDATOR_VERSION,
    )


def _changed_paths(left: Any, right: Any, path: str = "") -> list[str]:
    if type(left) is not type(right):
        return [path or "$"]
    if isinstance(left, dict):
        changed: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                changed.append(child)
            else:
                changed.extend(_changed_paths(left[key], right[key], child))
        return changed
    if isinstance(left, list):
        if len(left) != len(right):
            return [path or "$"]
        changed = []
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            child = f"{path}[{index}]" if path else f"[{index}]"
            changed.extend(_changed_paths(left_item, right_item, child))
        return changed
    return [] if left == right else [path or "$"]


def _leaf_count(value: Any) -> int:
    if isinstance(value, dict):
        return sum(_leaf_count(item) for item in value.values()) or 1
    if isinstance(value, list):
        return sum(_leaf_count(item) for item in value) or 1
    return 1


def _path_allowed(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}.") or path.startswith(f"{prefix}[")
