from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    EdgeRelation,
    EmpiricalActionClassV2,
    EmpiricalDependencyEdgeClassV2,
    EmpiricalReferenceClassV2,
    EmpiricalStateSemanticPolicyV2,
    EmpiricalStructuralStateV2,
    EmpiricalTemporalRelationClassV2,
    LineageKind,
    PublicTrajectoryActionV2,
    PublicTrajectoryProjectionV2,
    ReferenceDirection,
    ReferenceKind,
    TemporalRelation,
    TypedLineageEntryV2,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class IndependentReferenceMappingV2(FrozenModel):
    mapping_id: str = Field(min_length=1)
    trajectory_bound_artifact_hash: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    structural_state: EmpiricalStructuralStateV2
    production_mapper_called: Literal[False] = False
    independent_normalizer: Literal[True] = True
    independent_graph_builder: Literal[True] = True
    independent_temporal_builder: Literal[True] = True
    schema_version: str = "independent_reference_empirical_mapping.v2"

    @model_validator(mode="after")
    def validate_mapping(self) -> IndependentReferenceMappingV2:
        if self.mapping_id != _identity(
            self,
            "mapping_id",
            "independent_reference_empirical_mapping_v2:",
        ):
            raise ValueError("independent Reference Mapper identity changed")
        return self


def _normalize(
    value: Any,
    *,
    aliases: Mapping[str, str],
    set_like_fields: frozenset[str],
    field_name: str | None = None,
) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize(
                child,
                aliases=aliases,
                set_like_fields=set_like_fields,
                field_name=str(key),
            )
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        rows = [
            _normalize(
                child,
                aliases=aliases,
                set_like_fields=set_like_fields,
            )
            for child in value
        ]
        if field_name in set_like_fields:
            keyed = {canonical_json_bytes(row): row for row in rows}
            return [keyed[key] for key in sorted(keyed)]
        return rows
    return aliases.get(value, value) if isinstance(value, str) else value


def _path_values(value: Any, path: tuple[str, ...]) -> tuple[Any, ...]:
    if not path:
        return (value,)
    head, *tail = path
    if head == "*":
        if not isinstance(value, (list, tuple)):
            return ()
        return tuple(child for item in value for child in _path_values(item, tuple(tail)))
    if not isinstance(value, Mapping) or head not in value:
        return ()
    return _path_values(value[head], tuple(tail))


def _typed_reference_rows(
    action: PublicTrajectoryActionV2,
    aliases: Mapping[str, str],
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> dict[tuple[ReferenceDirection, ReferenceKind], tuple[str, ...]]:
    found: dict[tuple[ReferenceDirection, ReferenceKind], set[str]] = {
        ("consumed", "evidence"): set(),
        ("consumed", "operation"): set(),
        ("produced", "evidence"): set(),
        ("produced", "operation"): set(),
    }
    if action.tool_id is None:
        return {key: () for key in found}
    schema = next(
        (
            item
            for item in semantic_policy.typed_reference_policy.tool_schemas
            if item.tool_id == action.tool_id
        ),
        None,
    )
    if schema is None:
        raise ValueError(f"Reference Mapper has no Tool schema for {action.tool_id}")
    roots: dict[str, Mapping[str, Any]] = {
        "arguments": action.arguments,
        "observation_result": action.observation_result or {},
    }
    for field in schema.fields:
        for value in _path_values(roots[field.source], field.path):
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                raise TypeError("Reference Mapper found an invalid typed reference")
            found[(field.direction, field.reference_kind)].add(aliases.get(value, value))
    return {key: tuple(sorted(values)) for key, values in found.items()}


def _reference_signature(kind: ReferenceKind, value: str) -> str:
    return strict_canonical_hash(
        {"reference_kind": kind, "normalized_reference": value},
        prefix="empirical_reference_class_v2:",
    )


def _barrier(action: PublicTrajectoryActionV2) -> str | None:
    if action.error_code is not None or action.observation_status not in (None, "succeeded"):
        return "failure"
    if (
        action.tool_id == "cross_check_evidence"
        or action.decision_kind == "verify_terminal_operation"
    ):
        return "verification"
    if action.action_kind == "emit_final" or action.decision_kind == "emit_final_answer":
        return "final"
    return None


def _temporal(
    left: PublicTrajectoryActionV2,
    right: PublicTrajectoryActionV2,
    *,
    left_references: Mapping[tuple[ReferenceDirection, ReferenceKind], tuple[str, ...]],
    right_references: Mapping[tuple[ReferenceDirection, ReferenceKind], tuple[str, ...]],
) -> TemporalRelation | None:
    left_kind = _barrier(left)
    right_kind = _barrier(right)
    relations: dict[tuple[str | None, str], TemporalRelation] = {
        ("failure", "left"): "failure_precedes",
        ("failure", "right"): "precedes_failure",
        ("verification", "left"): "verification_precedes",
        ("verification", "right"): "precedes_verification",
        ("final", "left"): "final_precedes",
        ("final", "right"): "precedes_final",
    }
    if left_kind is not None:
        return relations[(left_kind, "left")]
    if right_kind is not None:
        return relations[(right_kind, "right")]
    left_commutative = bool(
        left.decision_kind == "acquire_public_input"
        and left.observation_status == "succeeded"
        and not left_references[("consumed", "evidence")]
        and not left_references[("consumed", "operation")]
    )
    right_commutative = bool(
        right.decision_kind == "acquire_public_input"
        and right.observation_status == "succeeded"
        and not right_references[("consumed", "evidence")]
        and not right_references[("consumed", "operation")]
    )
    return None if left_commutative and right_commutative else "ordered_noncommutative"


_REJECTION_KEYS = frozenset(
    {
        "blocked_public_call_signature",
        "correct_evidence_exposed",
        "correct_node_exposed",
        "correct_operand_exposed",
        "correct_operator_exposed",
        "correct_tool_exposed",
        "error_category",
        "exact_argument_values_retained",
        "failed_decision_kind",
        "job_terminal",
        "selected_tool_id",
        "semantic_recovery_available",
        "unresolved_public_symbols",
        "violated_public_constraint",
    }
)


def reference_map_public_trajectory_v2(
    *,
    trajectory: PublicTrajectoryProjectionV2,
    omega_task_context_id: str,
    runtime_operation_aliases: Mapping[str, str],
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> IndependentReferenceMappingV2:
    if trajectory.reference_projection_policy_id != semantic_policy.reference_projection_policy_id:
        raise ValueError("Reference Mapper crossed Reference Projection policies")
    aliases = dict(runtime_operation_aliases)
    set_like_fields = frozenset(semantic_policy.sequence_policy.set_like_field_names)
    actions: list[dict[str, Any]] = []
    refs: dict[tuple[ReferenceKind, str], str] = {}
    dependencies: Counter[tuple[str, EdgeRelation, str]] = Counter()
    lineage: set[tuple[LineageKind, str]] = {
        ("citation", value) for value in trajectory.final_citations
    }
    failures: list[dict[str, Any]] = []

    for action in trajectory.actions:
        typed = _typed_reference_rows(action, aliases, semantic_policy)
        payload = {
            "decision_kind": action.decision_kind,
            "action_kind": action.action_kind,
            "tool_id": action.tool_id,
            "arguments": _normalize(
                action.arguments,
                aliases=aliases,
                set_like_fields=set_like_fields,
            ),
            "observation_status": action.observation_status,
            "error_code": action.error_code,
            "observation_result": _normalize(
                action.observation_result,
                aliases=aliases,
                set_like_fields=set_like_fields,
            ),
            "typed_references": {
                f"{direction}_{kind}": values for (direction, kind), values in sorted(typed.items())
            },
        }
        payload_hash = strict_canonical_hash(
            payload,
            prefix="empirical_action_semantics_v2:",
        )
        signature = strict_canonical_hash(
            {
                "decision_kind": action.decision_kind,
                "action_kind": action.action_kind,
                "tool_id": action.tool_id,
                "semantic_payload_hash": payload_hash,
            },
            prefix="empirical_action_class_v2:",
        )
        actions.append(
            {
                "signature": signature,
                "decision_kind": action.decision_kind,
                "action_kind": action.action_kind,
                "tool_id": action.tool_id,
                "payload": payload,
                "payload_hash": payload_hash,
                "action": action,
                "typed_references": typed,
            }
        )
        for (direction, kind), values in typed.items():
            relation = cast(
                EdgeRelation,
                f"{'consumes' if direction == 'consumed' else 'produces'}_{kind}",
            )
            for value in values:
                ref_signature = _reference_signature(kind, value)
                refs[(kind, value)] = ref_signature
                edge = (
                    (ref_signature, relation, signature)
                    if direction == "consumed"
                    else (signature, relation, ref_signature)
                )
                dependencies[edge] += 1
                if kind == "evidence":
                    lineage.add(("evidence", value))
        lineage.update(("evidence", value) for value in action.evidence_ids)
        lineage.update(("provenance", value) for value in action.provenance_hashes)
        if _barrier(action) == "failure":
            failures.append(
                {
                    "failure_ordinal": len(failures),
                    "decision_kind": action.decision_kind,
                    "tool_id": action.tool_id,
                    "status": action.observation_status,
                    "error_code": action.error_code,
                }
            )

    multiplicities = Counter(str(row["signature"]) for row in actions)
    by_signature = {str(row["signature"]): row for row in actions}
    action_classes = tuple(
        EmpiricalActionClassV2(
            signature=signature,
            decision_kind=str(by_signature[signature]["decision_kind"]),
            action_kind=str(by_signature[signature]["action_kind"]),
            tool_id=cast(str | None, by_signature[signature]["tool_id"]),
            semantic_payload=cast(dict[str, Any], by_signature[signature]["payload"]),
            semantic_payload_hash=str(by_signature[signature]["payload_hash"]),
            multiplicity=count,
        )
        for signature, count in sorted(multiplicities.items())
    )
    reference_classes = tuple(
        EmpiricalReferenceClassV2(
            signature=signature,
            reference_kind=kind,
            normalized_reference=value,
        )
        for (kind, value), signature in sorted(refs.items(), key=lambda row: row[1])
    )
    dependency_classes = tuple(
        EmpiricalDependencyEdgeClassV2(
            source_signature=source,
            relation=relation,
            target_signature=target,
            multiplicity=count,
        )
        for (source, relation, target), count in sorted(dependencies.items())
    )
    temporal: Counter[tuple[str, TemporalRelation, str]] = Counter()
    for index, left in enumerate(actions):
        for right in actions[index + 1 :]:
            temporal_relation = _temporal(
                cast(PublicTrajectoryActionV2, left["action"]),
                cast(PublicTrajectoryActionV2, right["action"]),
                left_references=cast(
                    dict[tuple[ReferenceDirection, ReferenceKind], tuple[str, ...]],
                    left["typed_references"],
                ),
                right_references=cast(
                    dict[tuple[ReferenceDirection, ReferenceKind], tuple[str, ...]],
                    right["typed_references"],
                ),
            )
            if temporal_relation is not None:
                temporal[(str(left["signature"]), temporal_relation, str(right["signature"]))] += 1
    temporal_classes = tuple(
        EmpiricalTemporalRelationClassV2(
            source_signature=source,
            relation=relation,
            target_signature=target,
            multiplicity=count,
        )
        for (source, relation, target), count in sorted(temporal.items())
    )
    typed_lineage = tuple(
        TypedLineageEntryV2(lineage_kind=kind, value=value) for kind, value in sorted(lineage)
    )
    result = _normalize(
        trajectory.canonical_result,
        aliases=aliases,
        set_like_fields=set_like_fields,
    )
    if not isinstance(result, dict):
        raise TypeError("Reference Mapper canonical Result is not a Mapping")
    rejection_rows = tuple(
        {
            "rejection_ordinal": index,
            "semantics": _normalize(
                {key: value for key, value in row.items() if key in _REJECTION_KEYS},
                aliases=aliases,
                set_like_fields=set_like_fields,
            ),
        }
        for index, row in enumerate(trajectory.semantic_rejections)
    )
    failure_pattern = {
        "public_failures": tuple(failures),
        "semantic_rejections": rejection_rows,
    }
    state_values = {
        "omega_task_context_id": omega_task_context_id,
        "semantic_policy_id": semantic_policy.policy_id,
        "answer_semantic_schema_id": trajectory.answer_semantic_schema_id,
        "reference_projection_policy_id": trajectory.reference_projection_policy_id,
        "action_classes": action_classes,
        "reference_classes": reference_classes,
        "dependency_edge_classes": dependency_classes,
        "temporal_relation_classes": temporal_classes,
        "canonical_result": result,
        "canonical_result_semantics_hash": strict_canonical_hash(
            result,
            prefix="empirical_canonical_result_semantics_v2:",
        ),
        "typed_lineage": typed_lineage,
        "typed_lineage_hash": strict_canonical_hash(
            typed_lineage,
            prefix="empirical_typed_lineage_v2:",
        ),
        "failure_pattern": failure_pattern,
        "failure_pattern_hash": strict_canonical_hash(
            failure_pattern,
            prefix="empirical_failure_pattern_v2:",
        ),
    }
    provisional_state = EmpiricalStructuralStateV2.model_construct(
        state_id="pending",
        **state_values,
    )
    state = EmpiricalStructuralStateV2(
        state_id=_identity(
            provisional_state,
            "state_id",
            "empirical_structural_state_v2:",
        ),
        **state_values,
    )
    mapping_values = {
        "trajectory_bound_artifact_hash": trajectory.trajectory_bound_artifact_hash,
        "semantic_policy_id": semantic_policy.policy_id,
        "structural_state": state,
    }
    provisional = IndependentReferenceMappingV2.model_construct(
        mapping_id="pending", **mapping_values
    )
    return IndependentReferenceMappingV2(
        mapping_id=_identity(
            provisional,
            "mapping_id",
            "independent_reference_empirical_mapping_v2:",
        ),
        **mapping_values,
    )
