from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.trajectory_validity import (
    QualifiedTrajectoryValidityReport,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping import (
    ValidOnlyMappingAuthorization,
    ValidOnlyMappingResult,
    ValidOnlyStateMapperContract,
    map_independently_valid_trajectory_to_state,
)
from trusted_synthesis.hashing import canonical_hash

EMPIRICAL_STATE_MAPPING_VERSION = "empirical_structural_state_mapping.v1"
EMPIRICAL_STATE_CANONICALIZER_VERSION = "public_dependency_multiset.v1"

ReferenceKind = Literal["evidence", "operation"]
EdgeRelation = Literal[
    "consumes_evidence",
    "consumes_operation",
    "produces_evidence",
    "produces_operation",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


class PublicTrajectoryAction(FrozenModel):
    action_index: int = Field(ge=0)
    decision_kind: str = Field(min_length=1)
    action_kind: str = Field(min_length=1)
    tool_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    observation_status: str | None = None
    error_code: str | None = None
    observation_result: dict[str, Any] | None = None
    evidence_ids: tuple[str, ...] = ()
    provenance_hashes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_action(self) -> PublicTrajectoryAction:
        if self.evidence_ids != tuple(sorted(set(self.evidence_ids))):
            raise ValueError("public trajectory Evidence IDs are noncanonical")
        if self.provenance_hashes != tuple(sorted(set(self.provenance_hashes))):
            raise ValueError("public trajectory provenance hashes are noncanonical")
        if self.tool_id is None and self.arguments:
            raise ValueError("non-tool trajectory action carries Tool arguments")
        return self


class PublicTrajectoryProjection(FrozenModel):
    trajectory_id: str = Field(min_length=1)
    terminal_disposition: str = Field(min_length=1)
    actions: tuple[PublicTrajectoryAction, ...] = ()
    semantic_rejections: tuple[dict[str, Any], ...] = ()
    final_result: dict[str, Any] | None = None
    final_citations: tuple[str, ...] = ()
    raw_observation_prefix_hash: str = Field(min_length=1)
    trajectory_content_hash: str = Field(min_length=1)
    schema_version: str = EMPIRICAL_STATE_MAPPING_VERSION

    @model_validator(mode="after")
    def validate_projection(self) -> PublicTrajectoryProjection:
        if tuple(item.action_index for item in self.actions) != tuple(range(len(self.actions))):
            raise ValueError("public trajectory action indexes are not contiguous")
        if self.final_citations != tuple(sorted(set(self.final_citations))):
            raise ValueError("public trajectory Final citations are noncanonical")
        if self.raw_observation_prefix_hash != public_observation_prefix_hash(self.actions):
            raise ValueError("public trajectory Raw Observation prefix hash changed")
        if self.trajectory_content_hash != public_trajectory_content_hash(self):
            raise ValueError("public trajectory content hash changed")
        return self


class EmpiricalActionClass(FrozenModel):
    signature: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    action_kind: str = Field(min_length=1)
    tool_id: str | None = None
    semantic_payload_hash: str = Field(min_length=1)
    multiplicity: int = Field(ge=1)


class EmpiricalReferenceClass(FrozenModel):
    signature: str = Field(min_length=1)
    reference_kind: ReferenceKind
    normalized_reference: str = Field(min_length=1)


class EmpiricalDependencyEdgeClass(FrozenModel):
    source_signature: str = Field(min_length=1)
    relation: EdgeRelation
    target_signature: str = Field(min_length=1)
    multiplicity: int = Field(ge=1)


class EmpiricalStructuralState(FrozenModel):
    state_id: str = Field(min_length=1)
    omega_task_context_id: str = Field(min_length=1)
    canonicalizer_version: str = EMPIRICAL_STATE_CANONICALIZER_VERSION
    action_classes: tuple[EmpiricalActionClass, ...] = ()
    reference_classes: tuple[EmpiricalReferenceClass, ...] = ()
    dependency_edge_classes: tuple[EmpiricalDependencyEdgeClass, ...] = ()
    result_semantics_hash: str = Field(min_length=1)
    evidence_lineage_hash: str = Field(min_length=1)
    failure_pattern_hash: str = Field(min_length=1)
    schema_version: str = EMPIRICAL_STATE_MAPPING_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> EmpiricalStructuralState:
        action_signatures = tuple(item.signature for item in self.action_classes)
        reference_signatures = tuple(item.signature for item in self.reference_classes)
        if action_signatures != tuple(sorted(set(action_signatures))):
            raise ValueError("empirical State action classes are noncanonical")
        if reference_signatures != tuple(sorted(set(reference_signatures))):
            raise ValueError("empirical State reference classes are noncanonical")
        known = set(action_signatures) | set(reference_signatures)
        edge_keys = tuple(
            (item.source_signature, item.relation, item.target_signature)
            for item in self.dependency_edge_classes
        )
        if edge_keys != tuple(sorted(set(edge_keys))):
            raise ValueError("empirical State dependency edges are noncanonical")
        if any(
            edge.source_signature not in known or edge.target_signature not in known
            for edge in self.dependency_edge_classes
        ):
            raise ValueError("empirical State dependency graph has a dangling edge")
        if self.state_id != _identity(self, "state_id", "empirical_structural_state:"):
            raise ValueError("empirical structural State identity is invalid")
        return self


class EmpiricalRouteProjection(FrozenModel):
    projection_id: str = Field(min_length=1)
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    public_condition_id: str = Field(min_length=1)
    requested_path_id: str | None = None
    requested_path_strategy: str | None = None
    static_path_catalog_id: str = Field(min_length=1)
    empirical_decision_kinds: tuple[str, ...] = ()
    empirical_tool_ids: tuple[str, ...] = ()
    static_path_is_target_condition_only: Literal[True] = True
    projection_is_not_structural_state: Literal[True] = True
    schema_version: str = EMPIRICAL_STATE_MAPPING_VERSION

    @model_validator(mode="after")
    def validate_projection(self) -> EmpiricalRouteProjection:
        conditioned = self.sampling_mode == "reachability_conditioned"
        if conditioned != (self.requested_path_id is not None):
            raise ValueError("empirical route projection changed its Path conditioning")
        if conditioned != (self.requested_path_strategy is not None):
            raise ValueError("empirical route projection changed its Path strategy binding")
        if self.projection_id != _identity(
            self,
            "projection_id",
            "empirical_reachability_route_projection:",
        ):
            raise ValueError("empirical route projection identity is invalid")
        return self


class ValidOnlyEmpiricalStateAssignment(FrozenModel):
    assignment_id: str = Field(min_length=1)
    mapping_result_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    trajectory_content_hash: str = Field(min_length=1)
    qualified_validity_report_id: str = Field(min_length=1)
    omega_task_context_id: str = Field(min_length=1)
    structural_state_id: str = Field(min_length=1)
    route_condition_id: str = Field(min_length=1)
    static_path_catalog_id: str = Field(min_length=1)
    raw_observation_prefix_hash: str = Field(min_length=1)
    structural_state: EmpiricalStructuralState
    route_projection: EmpiricalRouteProjection
    qualified_validity: Literal[True] = True
    valid_only_gate_crossed: Literal[True] = True
    static_path_used_as_empirical_state: Literal[False] = False
    schema_version: str = EMPIRICAL_STATE_MAPPING_VERSION

    @model_validator(mode="after")
    def validate_assignment(self) -> ValidOnlyEmpiricalStateAssignment:
        if (
            self.structural_state_id != self.structural_state.state_id
            or self.omega_task_context_id != self.structural_state.omega_task_context_id
            or self.route_condition_id != self.route_projection.projection_id
            or self.static_path_catalog_id != self.route_projection.static_path_catalog_id
        ):
            raise ValueError("valid-only State Assignment crossed a bound parent")
        if self.assignment_id != _identity(
            self,
            "assignment_id",
            "valid_only_empirical_state_assignment:",
        ):
            raise ValueError("valid-only empirical State Assignment identity is invalid")
        return self


def public_observation_prefix_hash(actions: Sequence[PublicTrajectoryAction]) -> str:
    return canonical_hash(
        tuple(
            {
                "action_index": item.action_index,
                "tool_id": item.tool_id,
                "arguments": item.arguments,
                "observation_status": item.observation_status,
                "error_code": item.error_code,
                "observation_result": item.observation_result,
                "evidence_ids": item.evidence_ids,
                "provenance_hashes": item.provenance_hashes,
            }
            for item in actions
            if item.tool_id is not None
        ),
        prefix="raw_public_observation_prefix:",
    )


def public_trajectory_content_hash(value: PublicTrajectoryProjection) -> str:
    return canonical_hash(
        {
            "trajectory_id": value.trajectory_id,
            "terminal_disposition": value.terminal_disposition,
            "actions": value.actions,
            "semantic_rejections": value.semantic_rejections,
            "final_result": value.final_result,
            "final_citations": value.final_citations,
            "raw_observation_prefix_hash": value.raw_observation_prefix_hash,
        },
        prefix="public_model_trajectory_content:",
    )


def make_public_trajectory_projection(
    *,
    trajectory_id: str,
    terminal_disposition: str,
    actions: Sequence[PublicTrajectoryAction],
    semantic_rejections: Sequence[Mapping[str, Any]] = (),
    final_result: Mapping[str, Any] | None,
    final_citations: Sequence[str] = (),
) -> PublicTrajectoryProjection:
    ordered = tuple(actions)
    rejections = tuple(dict(item) for item in semantic_rejections)
    citations = tuple(sorted(set(final_citations)))
    prefix_hash = public_observation_prefix_hash(ordered)
    values = {
        "trajectory_id": trajectory_id,
        "terminal_disposition": terminal_disposition,
        "actions": ordered,
        "semantic_rejections": rejections,
        "final_result": dict(final_result) if final_result is not None else None,
        "final_citations": citations,
        "raw_observation_prefix_hash": prefix_hash,
    }
    provisional = PublicTrajectoryProjection.model_construct(
        trajectory_content_hash="pending",
        **values,
    )
    return PublicTrajectoryProjection(
        trajectory_content_hash=public_trajectory_content_hash(provisional),
        **values,
    )


def make_empirical_route_projection(
    *,
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"],
    public_condition_id: str,
    requested_path_id: str | None,
    requested_path_strategy: str | None,
    static_path_catalog_id: str,
    trajectory: PublicTrajectoryProjection,
) -> EmpiricalRouteProjection:
    values = {
        "sampling_mode": sampling_mode,
        "public_condition_id": public_condition_id,
        "requested_path_id": requested_path_id,
        "requested_path_strategy": requested_path_strategy,
        "static_path_catalog_id": static_path_catalog_id,
        "empirical_decision_kinds": tuple(item.decision_kind for item in trajectory.actions),
        "empirical_tool_ids": tuple(
            item.tool_id for item in trajectory.actions if item.tool_id is not None
        ),
    }
    provisional = EmpiricalRouteProjection.model_construct(projection_id="pending", **values)
    return EmpiricalRouteProjection(
        projection_id=_identity(
            provisional,
            "projection_id",
            "empirical_reachability_route_projection:",
        ),
        **values,
    )


def _normalize(value: Any, aliases: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(item, aliases) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item, aliases) for item in value]
    if isinstance(value, str):
        return aliases.get(value, value)
    return value


def _references(value: Any) -> tuple[tuple[ReferenceKind, str], ...]:
    found: set[tuple[ReferenceKind, str]] = set()

    def visit(item: Any, parent_key: str | None = None) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                visit(child, str(key))
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                visit(child, parent_key)
            return
        if not isinstance(item, str) or parent_key is None:
            return
        key = parent_key.casefold()
        if "evidence_id" in key or item.startswith("evidence:"):
            found.add(("evidence", item))
        elif "operation_ref" in key or item.startswith("operation:"):
            found.add(("operation", item))

    visit(value)
    return tuple(sorted(found))


def _reference_signature(kind: ReferenceKind, reference: str) -> str:
    return canonical_hash(
        {"reference_kind": kind, "normalized_reference": reference},
        prefix="empirical_reference_class:",
    )


def _build_structural_state(
    authorization: ValidOnlyMappingAuthorization,
    trajectory: PublicTrajectoryProjection,
    *,
    runtime_operation_aliases: Mapping[str, str],
) -> EmpiricalStructuralState:
    aliases = dict(runtime_operation_aliases)
    action_rows: list[tuple[str, str, str, str | None, str]] = []
    reference_rows: dict[tuple[ReferenceKind, str], str] = {}
    edge_counter: Counter[tuple[str, EdgeRelation, str]] = Counter()
    evidence_lineage: set[str] = set(trajectory.final_citations)
    failure_rows: list[dict[str, Any]] = []

    for action in trajectory.actions:
        normalized_arguments = _normalize(action.arguments, aliases)
        normalized_result = _normalize(action.observation_result, aliases)
        semantic_payload = {
            "decision_kind": action.decision_kind,
            "action_kind": action.action_kind,
            "tool_id": action.tool_id,
            "arguments": normalized_arguments,
            "observation_status": action.observation_status,
            "error_code": action.error_code,
            "observation_result": normalized_result,
        }
        payload_hash = canonical_hash(
            semantic_payload,
            prefix="empirical_action_semantics:",
        )
        action_signature = canonical_hash(
            {
                "decision_kind": action.decision_kind,
                "action_kind": action.action_kind,
                "tool_id": action.tool_id,
                "semantic_payload_hash": payload_hash,
            },
            prefix="empirical_action_class:",
        )
        action_rows.append(
            (
                action_signature,
                action.decision_kind,
                action.action_kind,
                action.tool_id,
                payload_hash,
            )
        )
        consumed = _references(normalized_arguments)
        produced = _references(normalized_result)
        for kind, reference in (*consumed, *produced):
            reference_rows[(kind, reference)] = _reference_signature(kind, reference)
            if kind == "evidence":
                evidence_lineage.add(reference)
        evidence_lineage.update(action.evidence_ids)
        evidence_lineage.update(action.provenance_hashes)
        for kind, reference in consumed:
            relation = cast(EdgeRelation, f"consumes_{kind}")
            edge_counter[
                (
                    reference_rows[(kind, reference)],
                    relation,
                    action_signature,
                )
            ] += 1
        for kind, reference in produced:
            relation = cast(EdgeRelation, f"produces_{kind}")
            edge_counter[
                (
                    action_signature,
                    relation,
                    reference_rows[(kind, reference)],
                )
            ] += 1
        if action.observation_status not in (None, "succeeded") or action.error_code is not None:
            failure_rows.append(
                {
                    "decision_kind": action.decision_kind,
                    "tool_id": action.tool_id,
                    "status": action.observation_status,
                    "error_code": action.error_code,
                }
            )

    grouped_actions = Counter(row[0] for row in action_rows)
    action_lookup = {row[0]: row for row in action_rows}
    action_classes = tuple(
        EmpiricalActionClass(
            signature=signature,
            decision_kind=action_lookup[signature][1],
            action_kind=action_lookup[signature][2],
            tool_id=action_lookup[signature][3],
            semantic_payload_hash=action_lookup[signature][4],
            multiplicity=multiplicity,
        )
        for signature, multiplicity in sorted(grouped_actions.items())
    )
    reference_classes = tuple(
        EmpiricalReferenceClass(
            signature=signature,
            reference_kind=kind,
            normalized_reference=reference,
        )
        for (kind, reference), signature in sorted(
            reference_rows.items(),
            key=lambda item: item[1],
        )
    )
    edges = tuple(
        EmpiricalDependencyEdgeClass(
            source_signature=source,
            relation=relation,
            target_signature=target,
            multiplicity=multiplicity,
        )
        for (source, relation, target), multiplicity in sorted(edge_counter.items())
    )
    values = {
        "omega_task_context_id": authorization.omega_task_context_id,
        "action_classes": action_classes,
        "reference_classes": reference_classes,
        "dependency_edge_classes": edges,
        "result_semantics_hash": canonical_hash(
            _normalize(trajectory.final_result, aliases),
            prefix="empirical_result_semantics:",
        ),
        "evidence_lineage_hash": canonical_hash(
            tuple(sorted(evidence_lineage)),
            prefix="empirical_evidence_lineage:",
        ),
        "failure_pattern_hash": canonical_hash(
            {
                "public_failures": tuple(sorted(failure_rows, key=repr)),
                "semantic_rejections": tuple(
                    sorted(
                        (_normalize(item, aliases) for item in trajectory.semantic_rejections),
                        key=repr,
                    )
                ),
            },
            prefix="empirical_failure_pattern:",
        ),
    }
    provisional = EmpiricalStructuralState.model_construct(state_id="pending", **values)
    return EmpiricalStructuralState(
        state_id=_identity(provisional, "state_id", "empirical_structural_state:"),
        **values,
    )


def map_independently_valid_public_trajectory_to_state(
    *,
    trajectory: PublicTrajectoryProjection,
    qualified_validity_report: QualifiedTrajectoryValidityReport,
    mapper_contract: ValidOnlyStateMapperContract,
    omega_task_context_id: str,
    route_projection: EmpiricalRouteProjection,
    runtime_operation_aliases: Mapping[str, str],
) -> ValidOnlyEmpiricalStateAssignment:
    mapping: ValidOnlyMappingResult[EmpiricalStructuralState] = (
        map_independently_valid_trajectory_to_state(
            trajectory_id=trajectory.trajectory_id,
            qualified_validity_report=qualified_validity_report,
            mapper_contract=mapper_contract,
            omega_task_context_id=omega_task_context_id,
            raw_observation_prefix_hash=trajectory.raw_observation_prefix_hash,
            mapper=lambda authorization: _build_structural_state(
                authorization,
                trajectory,
                runtime_operation_aliases=runtime_operation_aliases,
            ),
        )
    )
    state = mapping.mapped_state
    values = {
        "mapping_result_id": mapping.result_id,
        "mapper_contract_id": mapper_contract.contract_id,
        "trajectory_id": trajectory.trajectory_id,
        "trajectory_content_hash": trajectory.trajectory_content_hash,
        "qualified_validity_report_id": qualified_validity_report.report_id,
        "omega_task_context_id": omega_task_context_id,
        "structural_state_id": state.state_id,
        "route_condition_id": route_projection.projection_id,
        "static_path_catalog_id": route_projection.static_path_catalog_id,
        "raw_observation_prefix_hash": trajectory.raw_observation_prefix_hash,
        "structural_state": state,
        "route_projection": route_projection,
    }
    provisional = ValidOnlyEmpiricalStateAssignment.model_construct(
        assignment_id="pending",
        **values,
    )
    return ValidOnlyEmpiricalStateAssignment(
        assignment_id=_identity(
            provisional,
            "assignment_id",
            "valid_only_empirical_state_assignment:",
        ),
        **values,
    )
