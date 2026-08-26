from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.trajectory_validity import (
    QualifiedTrajectoryValidityReport,
)
from trusted_synthesis.core.evaluation.valid_only_state_mapping_v2 import (
    QualifiedVerifierInputBindingV2,
    ValidOnlyMappingAuthorizationV2,
    ValidOnlyMappingResultV2,
    ValidOnlyStateMapperContractV2,
    map_independently_valid_trajectory_to_state_v2,
)

EMPIRICAL_STATE_MAPPING_V2_VERSION = "empirical_structural_state_mapping.v2"
EMPIRICAL_STATE_CANONICALIZER_V2_VERSION = "schema_typed_temporal_quotient.v2"
STRICT_CANONICAL_JSON_POLICY_ID: Final = "strict_recursive_canonical_json.v1"

ReferenceKind = Literal["evidence", "operation"]
ReferenceDirection = Literal["consumed", "produced"]
ReferenceSource = Literal["arguments", "observation_result"]
LineageKind = Literal["citation", "evidence", "provenance"]
EdgeRelation = Literal[
    "consumes_evidence",
    "consumes_operation",
    "produces_evidence",
    "produces_operation",
]
TemporalRelation = Literal[
    "failure_precedes",
    "precedes_failure",
    "verification_precedes",
    "precedes_verification",
    "final_precedes",
    "precedes_final",
    "ordered_noncommutative",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return strict_canonical_hash(value.model_dump(mode="python", exclude={field}), prefix=prefix)


class SemanticSequencePolicyV2(FrozenModel):
    policy_id: str = Field(min_length=1)
    set_like_field_names: tuple[str, ...] = (
        "citations",
        "conflicts",
        "evidence_ids",
        "final_citations",
        "provenance_hashes",
        "support",
        "unresolved_public_symbols",
    )
    default_sequence_semantics: Literal["ordered"] = "ordered"
    set_like_values_sorted_by_canonical_json: Literal[True] = True
    set_like_duplicates_removed: Literal[True] = True
    schema_version: str = "empirical_semantic_sequence_policy.v2"

    @model_validator(mode="after")
    def validate_policy(self) -> SemanticSequencePolicyV2:
        if self.set_like_field_names != tuple(sorted(set(self.set_like_field_names))):
            raise ValueError("set-like field policy is noncanonical")
        if self.policy_id != _identity(
            self,
            "policy_id",
            "empirical_semantic_sequence_policy:",
        ):
            raise ValueError("semantic sequence policy identity changed")
        return self


class TypedReferenceFieldSpecV2(FrozenModel):
    source: ReferenceSource
    path: tuple[str, ...] = Field(min_length=1)
    reference_kind: ReferenceKind
    direction: ReferenceDirection


class ToolReferenceSchemaV2(FrozenModel):
    tool_id: str = Field(min_length=1)
    fields: tuple[TypedReferenceFieldSpecV2, ...]

    @model_validator(mode="after")
    def validate_schema(self) -> ToolReferenceSchemaV2:
        keys = tuple(
            (item.source, item.path, item.reference_kind, item.direction) for item in self.fields
        )
        if keys != tuple(sorted(set(keys))):
            raise ValueError("Tool reference fields are noncanonical")
        return self


class TypedReferenceExtractionPolicyV2(FrozenModel):
    policy_id: str = Field(min_length=1)
    tool_schemas: tuple[ToolReferenceSchemaV2, ...]
    unknown_tool_fails_closed: Literal[True] = True
    string_prefix_inference_forbidden: Literal[True] = True
    parent_key_substring_inference_forbidden: Literal[True] = True
    schema_version: str = "empirical_typed_reference_extraction_policy.v2"

    @model_validator(mode="after")
    def validate_policy(self) -> TypedReferenceExtractionPolicyV2:
        tool_ids = tuple(item.tool_id for item in self.tool_schemas)
        if tool_ids != tuple(sorted(set(tool_ids))):
            raise ValueError("Tool reference schemas are noncanonical")
        if self.policy_id != _identity(
            self,
            "policy_id",
            "empirical_typed_reference_extraction_policy:",
        ):
            raise ValueError("typed reference extraction policy identity changed")
        return self


class TemporalQuotientPolicyV2(FrozenModel):
    policy_id: str = Field(min_length=1)
    independent_successful_acquisition_reordering_quotiented: Literal[True] = True
    dependency_edges_preserve_order: Literal[True] = True
    failure_relative_order_preserved: Literal[True] = True
    verification_relative_order_preserved: Literal[True] = True
    final_stopping_relative_order_preserved: Literal[True] = True
    missing_dependency_does_not_imply_general_commutativity: Literal[True] = True
    schema_version: str = "empirical_temporal_quotient_policy.v2"

    @model_validator(mode="after")
    def validate_policy(self) -> TemporalQuotientPolicyV2:
        if self.policy_id != _identity(
            self,
            "policy_id",
            "empirical_temporal_quotient_policy:",
        ):
            raise ValueError("Temporal Quotient Policy identity changed")
        return self


class EmpiricalStateSemanticPolicyV2(FrozenModel):
    policy_id: str = Field(min_length=1)
    answer_semantics_contract_id: str = Field(min_length=1)
    answer_semantic_schema_authority: Literal["qualified_verifier_comparison.schema_id"] = (
        "qualified_verifier_comparison.schema_id"
    )
    reference_projection_policy_id: str = Field(min_length=1)
    decimal_canonicalization_policy_id: str = Field(min_length=1)
    sequence_policy: SemanticSequencePolicyV2
    typed_reference_policy: TypedReferenceExtractionPolicyV2
    temporal_quotient_policy: TemporalQuotientPolicyV2
    canonical_json_policy_id: Literal["strict_recursive_canonical_json.v1"] = (
        STRICT_CANONICAL_JSON_POLICY_ID
    )
    canonical_result_enters_state_identity: Literal[True] = True
    raw_final_payload_enters_state_identity: Literal[False] = False
    typed_lineage_namespaces: tuple[str, str, str] = (
        "citation",
        "evidence",
        "provenance",
    )
    schema_version: str = "empirical_state_semantic_policy.v2"

    @model_validator(mode="after")
    def validate_policy(self) -> EmpiricalStateSemanticPolicyV2:
        if self.policy_id != _identity(
            self,
            "policy_id",
            "empirical_state_semantic_policy:",
        ):
            raise ValueError("empirical State semantic policy identity changed")
        return self


class TypedActionReferencesV2(FrozenModel):
    consumed_evidence_refs: tuple[str, ...] = ()
    consumed_operation_refs: tuple[str, ...] = ()
    produced_evidence_refs: tuple[str, ...] = ()
    produced_operation_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> TypedActionReferencesV2:
        for values in self.model_dump(mode="python").values():
            if values != tuple(sorted(set(values))):
                raise ValueError("typed Action references are noncanonical")
        return self


class PublicTrajectoryActionV2(FrozenModel):
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
    typed_references: TypedActionReferencesV2

    @model_validator(mode="after")
    def validate_action(self) -> PublicTrajectoryActionV2:
        if self.evidence_ids != tuple(sorted(set(self.evidence_ids))):
            raise ValueError("v2 public trajectory Evidence IDs are noncanonical")
        if self.provenance_hashes != tuple(sorted(set(self.provenance_hashes))):
            raise ValueError("v2 public trajectory provenance hashes are noncanonical")
        if self.tool_id is None and (
            self.arguments or any(self.typed_references.model_dump().values())
        ):
            raise ValueError("non-tool v2 trajectory action carries Tool semantics")
        return self


class PublicTrajectoryProjectionV2(FrozenModel):
    trajectory_id: str = Field(min_length=1)
    terminal_disposition: str = Field(min_length=1)
    actions: tuple[PublicTrajectoryActionV2, ...] = ()
    semantic_rejections: tuple[dict[str, Any], ...] = ()
    raw_final_result: dict[str, Any] | None = None
    canonical_result: dict[str, Any]
    answer_semantic_schema_id: str = Field(min_length=1)
    reference_projection_policy_id: str = Field(min_length=1)
    final_citations: tuple[str, ...] = ()
    raw_observation_prefix_hash: str = Field(min_length=1)
    trajectory_semantic_content_hash: str = Field(min_length=1)
    trajectory_bound_artifact_hash: str = Field(min_length=1)
    raw_final_payload_hash: str = Field(min_length=1)
    canonical_result_semantics_hash: str = Field(min_length=1)
    schema_version: str = EMPIRICAL_STATE_MAPPING_V2_VERSION

    @model_validator(mode="after")
    def validate_projection(self) -> PublicTrajectoryProjectionV2:
        if tuple(item.action_index for item in self.actions) != tuple(range(len(self.actions))):
            raise ValueError("v2 public trajectory action indexes are not contiguous")
        if self.final_citations != tuple(sorted(set(self.final_citations))):
            raise ValueError("v2 public trajectory Final citations are noncanonical")
        checks = (
            self.raw_observation_prefix_hash == public_observation_prefix_hash_v2(self.actions),
            self.trajectory_semantic_content_hash == trajectory_semantic_content_hash_v2(self),
            self.trajectory_bound_artifact_hash == trajectory_bound_artifact_hash_v2(self),
            self.raw_final_payload_hash
            == strict_canonical_hash(
                self.raw_final_result,
                prefix="public_raw_final_payload_v2:",
            ),
            self.canonical_result_semantics_hash
            == strict_canonical_hash(
                self.canonical_result,
                prefix="empirical_canonical_result_semantics_v2:",
            ),
        )
        if not all(checks):
            raise ValueError("v2 public trajectory content binding changed")
        return self


class ExperimentalConditionV2(FrozenModel):
    condition_id: str = Field(min_length=1)
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"]
    public_condition_id: str | None = None
    requested_path_id: str | None = None
    requested_path_strategy: str | None = None
    static_path_catalog_id: str = Field(min_length=1)
    contains_post_treatment_model_behavior: Literal[False] = False
    schema_version: str = "empirical_experimental_condition.v2"

    @model_validator(mode="after")
    def validate_condition(self) -> ExperimentalConditionV2:
        conditioned = self.sampling_mode == "reachability_conditioned"
        if any(
            conditioned != (value is not None)
            for value in (
                self.public_condition_id,
                self.requested_path_id,
                self.requested_path_strategy,
            )
        ):
            raise ValueError("v2 Experimental Condition changed its Path binding")
        if self.condition_id != _identity(
            self,
            "condition_id",
            "empirical_experimental_condition:",
        ):
            raise ValueError("v2 Experimental Condition identity changed")
        return self


class EmpiricalRouteEventV2(FrozenModel):
    event_index: int = Field(ge=0)
    decision_kind: str = Field(min_length=1)
    action_kind: str = Field(min_length=1)
    tool_id: str | None = None
    observation_status: str | None = None
    error_code: str | None = None
    action_semantics_hash: str = Field(min_length=1)


class EmpiricalRouteSignatureV2(FrozenModel):
    route_signature_id: str = Field(min_length=1)
    events: tuple[EmpiricalRouteEventV2, ...]
    contains_pre_treatment_condition: Literal[False] = False
    schema_version: str = "empirical_route_signature.v2"

    @model_validator(mode="after")
    def validate_signature(self) -> EmpiricalRouteSignatureV2:
        if tuple(item.event_index for item in self.events) != tuple(range(len(self.events))):
            raise ValueError("v2 empirical Route events are not contiguous")
        if self.route_signature_id != _identity(
            self,
            "route_signature_id",
            "empirical_route_signature:",
        ):
            raise ValueError("v2 empirical Route Signature identity changed")
        return self


class EmpiricalActionClassV2(FrozenModel):
    signature: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    action_kind: str = Field(min_length=1)
    tool_id: str | None = None
    semantic_payload: dict[str, Any]
    semantic_payload_hash: str = Field(min_length=1)
    multiplicity: int = Field(ge=1)


class EmpiricalReferenceClassV2(FrozenModel):
    signature: str = Field(min_length=1)
    reference_kind: ReferenceKind
    normalized_reference: str = Field(min_length=1)


class EmpiricalDependencyEdgeClassV2(FrozenModel):
    source_signature: str = Field(min_length=1)
    relation: EdgeRelation
    target_signature: str = Field(min_length=1)
    multiplicity: int = Field(ge=1)


class EmpiricalTemporalRelationClassV2(FrozenModel):
    source_signature: str = Field(min_length=1)
    relation: TemporalRelation
    target_signature: str = Field(min_length=1)
    multiplicity: int = Field(ge=1)


class TypedLineageEntryV2(FrozenModel):
    lineage_kind: LineageKind
    value: str = Field(min_length=1)


class EmpiricalStructuralStateV2(FrozenModel):
    state_id: str = Field(min_length=1)
    omega_task_context_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    answer_semantic_schema_id: str = Field(min_length=1)
    reference_projection_policy_id: str = Field(min_length=1)
    canonicalizer_version: str = EMPIRICAL_STATE_CANONICALIZER_V2_VERSION
    action_classes: tuple[EmpiricalActionClassV2, ...] = ()
    reference_classes: tuple[EmpiricalReferenceClassV2, ...] = ()
    dependency_edge_classes: tuple[EmpiricalDependencyEdgeClassV2, ...] = ()
    temporal_relation_classes: tuple[EmpiricalTemporalRelationClassV2, ...] = ()
    canonical_result: dict[str, Any]
    canonical_result_semantics_hash: str = Field(min_length=1)
    typed_lineage: tuple[TypedLineageEntryV2, ...] = ()
    typed_lineage_hash: str = Field(min_length=1)
    failure_pattern: dict[str, Any]
    failure_pattern_hash: str = Field(min_length=1)
    raw_final_payload_in_state_identity: Literal[False] = False
    schema_version: str = EMPIRICAL_STATE_MAPPING_V2_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> EmpiricalStructuralStateV2:
        action_signatures = tuple(item.signature for item in self.action_classes)
        reference_signatures = tuple(item.signature for item in self.reference_classes)
        if action_signatures != tuple(sorted(set(action_signatures))):
            raise ValueError("v2 State action classes are noncanonical")
        if reference_signatures != tuple(sorted(set(reference_signatures))):
            raise ValueError("v2 State reference classes are noncanonical")
        known = set(action_signatures) | set(reference_signatures)
        edge_keys = tuple(
            (item.source_signature, item.relation, item.target_signature)
            for item in self.dependency_edge_classes
        )
        temporal_keys = tuple(
            (item.source_signature, item.relation, item.target_signature)
            for item in self.temporal_relation_classes
        )
        if edge_keys != tuple(sorted(set(edge_keys))):
            raise ValueError("v2 State dependency edges are noncanonical")
        if temporal_keys != tuple(sorted(set(temporal_keys))):
            raise ValueError("v2 State temporal relations are noncanonical")
        if any(
            item.source_signature not in known or item.target_signature not in known
            for item in (*self.dependency_edge_classes, *self.temporal_relation_classes)
        ):
            raise ValueError("v2 State graph has a dangling relation")
        lineage_keys = tuple((item.lineage_kind, item.value) for item in self.typed_lineage)
        if lineage_keys != tuple(sorted(set(lineage_keys))):
            raise ValueError("v2 State typed lineage is noncanonical")
        if self.canonical_result_semantics_hash != strict_canonical_hash(
            self.canonical_result,
            prefix="empirical_canonical_result_semantics_v2:",
        ):
            raise ValueError("v2 State canonical Result hash changed")
        if self.typed_lineage_hash != strict_canonical_hash(
            self.typed_lineage,
            prefix="empirical_typed_lineage_v2:",
        ):
            raise ValueError("v2 State typed lineage hash changed")
        if self.failure_pattern_hash != strict_canonical_hash(
            self.failure_pattern,
            prefix="empirical_failure_pattern_v2:",
        ):
            raise ValueError("v2 State failure pattern hash changed")
        if self.state_id != _identity(
            self,
            "state_id",
            "empirical_structural_state_v2:",
        ):
            raise ValueError("v2 empirical Structural State identity changed")
        return self


class ValidOnlyEmpiricalStateAssignmentV2(FrozenModel):
    assignment_id: str = Field(min_length=1)
    mapping_result_id: str = Field(min_length=1)
    mapper_contract_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    trajectory_semantic_content_hash: str = Field(min_length=1)
    trajectory_bound_artifact_hash: str = Field(min_length=1)
    raw_execution_artifact_hash: str = Field(min_length=1)
    qualified_verifier_input_hash: str = Field(min_length=1)
    qualified_validity_report_id: str = Field(min_length=1)
    omega_task_context_id: str = Field(min_length=1)
    structural_state_id: str = Field(min_length=1)
    experimental_condition_id: str = Field(min_length=1)
    empirical_route_signature_id: str = Field(min_length=1)
    static_path_catalog_id: str = Field(min_length=1)
    raw_observation_prefix_hash: str = Field(min_length=1)
    raw_final_payload_hash: str = Field(min_length=1)
    canonical_result_semantics_hash: str = Field(min_length=1)
    structural_state: EmpiricalStructuralStateV2
    experimental_condition: ExperimentalConditionV2
    empirical_route_signature: EmpiricalRouteSignatureV2
    qualified_validity: Literal[True] = True
    valid_only_gate_crossed: Literal[True] = True
    historical_reclassified: Literal[False] = False
    frequency_authorized: Literal[False] = False
    vtdo_authorized: Literal[False] = False
    schema_version: str = EMPIRICAL_STATE_MAPPING_V2_VERSION

    @model_validator(mode="after")
    def validate_assignment(self) -> ValidOnlyEmpiricalStateAssignmentV2:
        if (
            self.structural_state_id != self.structural_state.state_id
            or self.omega_task_context_id != self.structural_state.omega_task_context_id
            or self.experimental_condition_id != self.experimental_condition.condition_id
            or self.empirical_route_signature_id
            != self.empirical_route_signature.route_signature_id
            or self.static_path_catalog_id != self.experimental_condition.static_path_catalog_id
            or self.canonical_result_semantics_hash
            != self.structural_state.canonical_result_semantics_hash
        ):
            raise ValueError("v2 valid-only State Assignment crossed a bound parent")
        if self.assignment_id != _identity(
            self,
            "assignment_id",
            "valid_only_empirical_state_assignment_v2:",
        ):
            raise ValueError("v2 valid-only State Assignment identity changed")
        return self


class StateContrastArtifactV2(FrozenModel):
    contrast_id: str = Field(min_length=1)
    left_state_id: str = Field(min_length=1)
    right_state_id: str = Field(min_length=1)
    differing_dimensions: tuple[str, ...] = Field(min_length=1)
    minimal_difference_witness: dict[str, Any]
    schema_version: str = "empirical_state_contrast.v2"

    @model_validator(mode="after")
    def validate_contrast(self) -> StateContrastArtifactV2:
        if self.left_state_id >= self.right_state_id:
            raise ValueError("v2 State Contrast parent order is noncanonical")
        if self.differing_dimensions != tuple(sorted(set(self.differing_dimensions))):
            raise ValueError("v2 State Contrast dimensions are noncanonical")
        if set(self.minimal_difference_witness) != set(self.differing_dimensions):
            raise ValueError("v2 State Contrast witness is incomplete")
        if self.contrast_id != _identity(
            self,
            "contrast_id",
            "empirical_state_contrast:",
        ):
            raise ValueError("v2 State Contrast identity changed")
        return self


def _make_sequence_policy() -> SemanticSequencePolicyV2:
    provisional = SemanticSequencePolicyV2.model_construct(policy_id="pending")
    return SemanticSequencePolicyV2(
        policy_id=_identity(
            provisional,
            "policy_id",
            "empirical_semantic_sequence_policy:",
        )
    )


def _field(
    source: ReferenceSource,
    path: tuple[str, ...],
    kind: ReferenceKind,
    direction: ReferenceDirection,
) -> TypedReferenceFieldSpecV2:
    return TypedReferenceFieldSpecV2(
        source=source,
        path=path,
        reference_kind=kind,
        direction=direction,
    )


def _tool_schema(
    tool_id: str,
    fields: Sequence[TypedReferenceFieldSpecV2],
) -> ToolReferenceSchemaV2:
    return ToolReferenceSchemaV2(
        tool_id=tool_id,
        fields=tuple(
            sorted(
                fields,
                key=lambda item: (item.source, item.path, item.reference_kind, item.direction),
            )
        ),
    )


def make_default_typed_reference_policy_v2() -> TypedReferenceExtractionPolicyV2:
    schemas = (
        _tool_schema(
            "calculator",
            (
                _field("arguments", ("operands", "*", "evidence_id"), "evidence", "consumed"),
                _field("arguments", ("operands", "*", "operation_ref"), "operation", "consumed"),
                _field("observation_result", ("result", "operation_ref"), "operation", "produced"),
            ),
        ),
        _tool_schema(
            "cross_check_evidence",
            (
                _field("arguments", ("claim_or_result", "operation_ref"), "operation", "consumed"),
                _field("arguments", ("evidence_ids", "*"), "evidence", "consumed"),
            ),
        ),
        _tool_schema(
            "normalize_metric_unit_period",
            (
                _field("arguments", ("evidence_ids", "*"), "evidence", "consumed"),
                _field(
                    "observation_result", ("normalized_operation_ref",), "operation", "produced"
                ),
            ),
        ),
        _tool_schema(
            "open_document",
            (
                _field(
                    "observation_result",
                    ("content", "facts", "*", "evidence_id"),
                    "evidence",
                    "produced",
                ),
                _field("observation_result", ("evidence_ids", "*"), "evidence", "produced"),
            ),
        ),
        _tool_schema(
            "query_structured_fact",
            (
                _field("observation_result", ("evidence_ids", "*"), "evidence", "produced"),
                _field("observation_result", ("facts", "*", "evidence_id"), "evidence", "produced"),
            ),
        ),
        _tool_schema(
            "search_archive",
            (
                _field(
                    "observation_result", ("matches", "*", "evidence_id"), "evidence", "produced"
                ),
            ),
        ),
    )
    provisional = TypedReferenceExtractionPolicyV2.model_construct(
        policy_id="pending",
        tool_schemas=schemas,
    )
    return TypedReferenceExtractionPolicyV2(
        policy_id=_identity(
            provisional,
            "policy_id",
            "empirical_typed_reference_extraction_policy:",
        ),
        tool_schemas=schemas,
    )


def _make_temporal_policy() -> TemporalQuotientPolicyV2:
    provisional = TemporalQuotientPolicyV2.model_construct(policy_id="pending")
    return TemporalQuotientPolicyV2(
        policy_id=_identity(
            provisional,
            "policy_id",
            "empirical_temporal_quotient_policy:",
        )
    )


def make_empirical_state_semantic_policy_v2(
    *,
    answer_semantics_contract_id: str,
    reference_projection_policy_id: str,
    decimal_canonicalization_policy_id: str,
) -> EmpiricalStateSemanticPolicyV2:
    values = {
        "answer_semantics_contract_id": answer_semantics_contract_id,
        "reference_projection_policy_id": reference_projection_policy_id,
        "decimal_canonicalization_policy_id": decimal_canonicalization_policy_id,
        "sequence_policy": _make_sequence_policy(),
        "typed_reference_policy": make_default_typed_reference_policy_v2(),
        "temporal_quotient_policy": _make_temporal_policy(),
    }
    provisional = EmpiricalStateSemanticPolicyV2.model_construct(policy_id="pending", **values)
    return EmpiricalStateSemanticPolicyV2(
        policy_id=_identity(
            provisional,
            "policy_id",
            "empirical_state_semantic_policy:",
        ),
        **values,
    )


def _values_at_path(value: Any, path: Sequence[str]) -> tuple[Any, ...]:
    if not path:
        return (value,)
    head, *tail = path
    if head == "*":
        if not isinstance(value, (list, tuple)):
            return ()
        return tuple(child for item in value for child in _values_at_path(item, tail))
    if not isinstance(value, Mapping) or head not in value:
        return ()
    return _values_at_path(value[head], tail)


def extract_typed_action_references_v2(
    *,
    tool_id: str | None,
    arguments: Mapping[str, Any],
    observation_result: Mapping[str, Any] | None,
    policy: TypedReferenceExtractionPolicyV2,
) -> TypedActionReferencesV2:
    if tool_id is None:
        return TypedActionReferencesV2()
    schema = next((item for item in policy.tool_schemas if item.tool_id == tool_id), None)
    if schema is None:
        raise ValueError(f"typed reference policy has no schema for Tool {tool_id}")
    roots: dict[ReferenceSource, Mapping[str, Any]] = {
        "arguments": arguments,
        "observation_result": observation_result or {},
    }
    found: dict[tuple[ReferenceDirection, ReferenceKind], set[str]] = {
        ("consumed", "evidence"): set(),
        ("consumed", "operation"): set(),
        ("produced", "evidence"): set(),
        ("produced", "operation"): set(),
    }
    for field in schema.fields:
        for value in _values_at_path(roots[field.source], field.path):
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                raise TypeError("typed reference field is not a nonempty string")
            found[(field.direction, field.reference_kind)].add(value)
    return TypedActionReferencesV2(
        consumed_evidence_refs=tuple(sorted(found[("consumed", "evidence")])),
        consumed_operation_refs=tuple(sorted(found[("consumed", "operation")])),
        produced_evidence_refs=tuple(sorted(found[("produced", "evidence")])),
        produced_operation_refs=tuple(sorted(found[("produced", "operation")])),
    )


def make_public_trajectory_action_v2(
    *,
    action_index: int,
    decision_kind: str,
    action_kind: str,
    tool_id: str | None,
    arguments: Mapping[str, Any] | None = None,
    observation_status: str | None = None,
    error_code: str | None = None,
    observation_result: Mapping[str, Any] | None = None,
    evidence_ids: Sequence[str] = (),
    provenance_hashes: Sequence[str] = (),
    reference_policy: TypedReferenceExtractionPolicyV2,
) -> PublicTrajectoryActionV2:
    argument_dict = dict(arguments or {})
    result_dict = dict(observation_result) if observation_result is not None else None
    return PublicTrajectoryActionV2(
        action_index=action_index,
        decision_kind=decision_kind,
        action_kind=action_kind,
        tool_id=tool_id,
        arguments=argument_dict,
        observation_status=observation_status,
        error_code=error_code,
        observation_result=result_dict,
        evidence_ids=tuple(sorted(set(evidence_ids))),
        provenance_hashes=tuple(sorted(set(provenance_hashes))),
        typed_references=extract_typed_action_references_v2(
            tool_id=tool_id,
            arguments=argument_dict,
            observation_result=result_dict,
            policy=reference_policy,
        ),
    )


def public_observation_prefix_hash_v2(actions: Sequence[PublicTrajectoryActionV2]) -> str:
    return strict_canonical_hash(
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
                "typed_references": item.typed_references,
            }
            for item in actions
            if item.tool_id is not None
        ),
        prefix="raw_public_observation_prefix_v2:",
    )


def _trajectory_semantic_payload(value: PublicTrajectoryProjectionV2) -> dict[str, Any]:
    return {
        "terminal_disposition": value.terminal_disposition,
        "actions": value.actions,
        "semantic_rejections": value.semantic_rejections,
        "raw_final_result": value.raw_final_result,
        "canonical_result": value.canonical_result,
        "answer_semantic_schema_id": value.answer_semantic_schema_id,
        "reference_projection_policy_id": value.reference_projection_policy_id,
        "final_citations": value.final_citations,
        "raw_observation_prefix_hash": value.raw_observation_prefix_hash,
    }


def trajectory_semantic_content_hash_v2(value: PublicTrajectoryProjectionV2) -> str:
    return strict_canonical_hash(
        _trajectory_semantic_payload(value),
        prefix="public_trajectory_semantic_content_v2:",
    )


def trajectory_bound_artifact_hash_v2(value: PublicTrajectoryProjectionV2) -> str:
    return strict_canonical_hash(
        {
            "trajectory_id": value.trajectory_id,
            "trajectory_semantic_content_hash": value.trajectory_semantic_content_hash,
        },
        prefix="public_trajectory_bound_artifact_v2:",
    )


def make_public_trajectory_projection_v2(
    *,
    trajectory_id: str,
    terminal_disposition: str,
    actions: Sequence[PublicTrajectoryActionV2],
    semantic_rejections: Sequence[Mapping[str, Any]] = (),
    raw_final_result: Mapping[str, Any] | None,
    canonical_result: Mapping[str, Any],
    answer_semantic_schema_id: str,
    reference_projection_policy_id: str,
    final_citations: Sequence[str] = (),
) -> PublicTrajectoryProjectionV2:
    ordered = tuple(actions)
    rejections = tuple(dict(item) for item in semantic_rejections)
    citations = tuple(sorted(set(final_citations)))
    prefix_hash = public_observation_prefix_hash_v2(ordered)
    values = {
        "trajectory_id": trajectory_id,
        "terminal_disposition": terminal_disposition,
        "actions": ordered,
        "semantic_rejections": rejections,
        "raw_final_result": dict(raw_final_result) if raw_final_result is not None else None,
        "canonical_result": dict(canonical_result),
        "answer_semantic_schema_id": answer_semantic_schema_id,
        "reference_projection_policy_id": reference_projection_policy_id,
        "final_citations": citations,
        "raw_observation_prefix_hash": prefix_hash,
        "raw_final_payload_hash": strict_canonical_hash(
            dict(raw_final_result) if raw_final_result is not None else None,
            prefix="public_raw_final_payload_v2:",
        ),
        "canonical_result_semantics_hash": strict_canonical_hash(
            dict(canonical_result),
            prefix="empirical_canonical_result_semantics_v2:",
        ),
    }
    provisional = PublicTrajectoryProjectionV2.model_construct(
        trajectory_semantic_content_hash="pending",
        trajectory_bound_artifact_hash="pending",
        **values,
    )
    semantic_hash = trajectory_semantic_content_hash_v2(provisional)
    bound_provisional = provisional.model_copy(
        update={"trajectory_semantic_content_hash": semantic_hash}
    )
    return PublicTrajectoryProjectionV2(
        trajectory_semantic_content_hash=semantic_hash,
        trajectory_bound_artifact_hash=trajectory_bound_artifact_hash_v2(bound_provisional),
        **values,
    )


def make_experimental_condition_v2(
    *,
    sampling_mode: Literal["reachability_unconditional", "reachability_conditioned"],
    public_condition_id: str | None,
    requested_path_id: str | None,
    requested_path_strategy: str | None,
    static_path_catalog_id: str,
) -> ExperimentalConditionV2:
    values = {
        "sampling_mode": sampling_mode,
        "public_condition_id": public_condition_id,
        "requested_path_id": requested_path_id,
        "requested_path_strategy": requested_path_strategy,
        "static_path_catalog_id": static_path_catalog_id,
    }
    provisional = ExperimentalConditionV2.model_construct(condition_id="pending", **values)
    return ExperimentalConditionV2(
        condition_id=_identity(
            provisional,
            "condition_id",
            "empirical_experimental_condition:",
        ),
        **values,
    )


def make_empirical_route_signature_v2(
    trajectory: PublicTrajectoryProjectionV2,
) -> EmpiricalRouteSignatureV2:
    events = tuple(
        EmpiricalRouteEventV2(
            event_index=index,
            decision_kind=item.decision_kind,
            action_kind=item.action_kind,
            tool_id=item.tool_id,
            observation_status=item.observation_status,
            error_code=item.error_code,
            action_semantics_hash=strict_canonical_hash(
                {
                    "decision_kind": item.decision_kind,
                    "action_kind": item.action_kind,
                    "tool_id": item.tool_id,
                    "arguments": item.arguments,
                    "observation_status": item.observation_status,
                    "error_code": item.error_code,
                    "observation_result": item.observation_result,
                    "typed_references": item.typed_references,
                },
                prefix="empirical_route_event_semantics:",
            ),
        )
        for index, item in enumerate(trajectory.actions)
    )
    provisional = EmpiricalRouteSignatureV2.model_construct(
        route_signature_id="pending",
        events=events,
    )
    return EmpiricalRouteSignatureV2(
        route_signature_id=_identity(
            provisional,
            "route_signature_id",
            "empirical_route_signature:",
        ),
        events=events,
    )


def _normalize_semantic_value(
    value: Any,
    *,
    aliases: Mapping[str, str],
    sequence_policy: SemanticSequencePolicyV2,
    parent_field: str | None = None,
) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_semantic_value(
                item,
                aliases=aliases,
                sequence_policy=sequence_policy,
                parent_field=str(key),
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        normalized = [
            _normalize_semantic_value(
                item,
                aliases=aliases,
                sequence_policy=sequence_policy,
                parent_field=None,
            )
            for item in value
        ]
        if parent_field in set(sequence_policy.set_like_field_names):
            by_bytes = {canonical_json_bytes(item): item for item in normalized}
            return [by_bytes[key] for key in sorted(by_bytes)]
        return normalized
    if isinstance(value, str):
        return aliases.get(value, value)
    return value


def _reference_signature(kind: ReferenceKind, reference: str) -> str:
    return strict_canonical_hash(
        {"reference_kind": kind, "normalized_reference": reference},
        prefix="empirical_reference_class_v2:",
    )


def _normalized_references(
    references: TypedActionReferencesV2,
    aliases: Mapping[str, str],
) -> dict[tuple[ReferenceDirection, ReferenceKind], tuple[str, ...]]:
    return {
        ("consumed", "evidence"): tuple(
            sorted({aliases.get(item, item) for item in references.consumed_evidence_refs})
        ),
        ("consumed", "operation"): tuple(
            sorted({aliases.get(item, item) for item in references.consumed_operation_refs})
        ),
        ("produced", "evidence"): tuple(
            sorted({aliases.get(item, item) for item in references.produced_evidence_refs})
        ),
        ("produced", "operation"): tuple(
            sorted({aliases.get(item, item) for item in references.produced_operation_refs})
        ),
    }


def _barrier_kind(
    action: PublicTrajectoryActionV2,
) -> Literal["failure", "verification", "final"] | None:
    if action.observation_status not in (None, "succeeded") or action.error_code is not None:
        return "failure"
    if (
        action.decision_kind == "verify_terminal_operation"
        or action.tool_id == "cross_check_evidence"
    ):
        return "verification"
    if action.decision_kind == "emit_final_answer" or action.action_kind == "emit_final":
        return "final"
    return None


def _temporal_relation(
    left: PublicTrajectoryActionV2,
    right: PublicTrajectoryActionV2,
) -> TemporalRelation | None:
    left_barrier = _barrier_kind(left)
    right_barrier = _barrier_kind(right)
    if left_barrier == "failure":
        return "failure_precedes"
    if right_barrier == "failure":
        return "precedes_failure"
    if left_barrier == "verification":
        return "verification_precedes"
    if right_barrier == "verification":
        return "precedes_verification"
    if left_barrier == "final":
        return "final_precedes"
    if right_barrier == "final":
        return "precedes_final"
    left_independent = bool(
        left.decision_kind == "acquire_public_input"
        and left.observation_status == "succeeded"
        and not left.typed_references.consumed_evidence_refs
        and not left.typed_references.consumed_operation_refs
    )
    right_independent = bool(
        right.decision_kind == "acquire_public_input"
        and right.observation_status == "succeeded"
        and not right.typed_references.consumed_evidence_refs
        and not right.typed_references.consumed_operation_refs
    )
    return None if left_independent and right_independent else "ordered_noncommutative"


_REJECTION_SEMANTIC_KEYS = (
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
)


def _semantic_rejection_projection(
    value: Mapping[str, Any],
    *,
    aliases: Mapping[str, str],
    sequence_policy: SemanticSequencePolicyV2,
) -> dict[str, Any]:
    projected = {key: value[key] for key in _REJECTION_SEMANTIC_KEYS if key in value}
    normalized = _normalize_semantic_value(
        projected,
        aliases=aliases,
        sequence_policy=sequence_policy,
    )
    if not isinstance(normalized, dict):
        raise TypeError("v2 semantic rejection projection is not a Mapping")
    return normalized


def _build_structural_state_v2(
    authorization: ValidOnlyMappingAuthorizationV2,
    trajectory: PublicTrajectoryProjectionV2,
    *,
    runtime_operation_aliases: Mapping[str, str],
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> EmpiricalStructuralStateV2:
    if trajectory.answer_semantic_schema_id == "":
        raise ValueError("v2 trajectory omitted its Answer Semantic Schema")
    if trajectory.reference_projection_policy_id != semantic_policy.reference_projection_policy_id:
        raise ValueError("v2 trajectory crossed Reference Projection policies")
    aliases = dict(runtime_operation_aliases)
    sequence_policy = semantic_policy.sequence_policy
    action_rows: list[
        tuple[str, str, str, str | None, dict[str, Any], str, PublicTrajectoryActionV2]
    ] = []
    reference_rows: dict[tuple[ReferenceKind, str], str] = {}
    edge_counter: Counter[tuple[str, EdgeRelation, str]] = Counter()
    lineage: set[tuple[LineageKind, str]] = {
        ("citation", item) for item in trajectory.final_citations
    }
    failure_rows: list[dict[str, Any]] = []

    for action in trajectory.actions:
        normalized_arguments = _normalize_semantic_value(
            action.arguments,
            aliases=aliases,
            sequence_policy=sequence_policy,
        )
        normalized_result = _normalize_semantic_value(
            action.observation_result,
            aliases=aliases,
            sequence_policy=sequence_policy,
        )
        normalized_refs = _normalized_references(action.typed_references, aliases)
        semantic_payload = {
            "decision_kind": action.decision_kind,
            "action_kind": action.action_kind,
            "tool_id": action.tool_id,
            "arguments": normalized_arguments,
            "observation_status": action.observation_status,
            "error_code": action.error_code,
            "observation_result": normalized_result,
            "typed_references": {
                f"{direction}_{kind}": values
                for (direction, kind), values in sorted(normalized_refs.items())
            },
        }
        payload_hash = strict_canonical_hash(
            semantic_payload,
            prefix="empirical_action_semantics_v2:",
        )
        action_signature = strict_canonical_hash(
            {
                "decision_kind": action.decision_kind,
                "action_kind": action.action_kind,
                "tool_id": action.tool_id,
                "semantic_payload_hash": payload_hash,
            },
            prefix="empirical_action_class_v2:",
        )
        action_rows.append(
            (
                action_signature,
                action.decision_kind,
                action.action_kind,
                action.tool_id,
                cast(dict[str, Any], semantic_payload),
                payload_hash,
                action,
            )
        )
        for (direction, kind), references in normalized_refs.items():
            for reference in references:
                signature = _reference_signature(kind, reference)
                reference_rows[(kind, reference)] = signature
                relation = cast(
                    EdgeRelation,
                    f"{'consumes' if direction == 'consumed' else 'produces'}_{kind}",
                )
                if direction == "consumed":
                    edge_counter[(signature, relation, action_signature)] += 1
                else:
                    edge_counter[(action_signature, relation, signature)] += 1
                if kind == "evidence":
                    lineage.add(("evidence", reference))
        lineage.update(("evidence", item) for item in action.evidence_ids)
        lineage.update(("provenance", item) for item in action.provenance_hashes)
        if action.observation_status not in (None, "succeeded") or action.error_code is not None:
            failure_rows.append(
                {
                    "failure_ordinal": len(failure_rows),
                    "decision_kind": action.decision_kind,
                    "tool_id": action.tool_id,
                    "status": action.observation_status,
                    "error_code": action.error_code,
                }
            )

    grouped_actions = Counter(row[0] for row in action_rows)
    action_lookup = {row[0]: row for row in action_rows}
    action_classes = tuple(
        EmpiricalActionClassV2(
            signature=signature,
            decision_kind=action_lookup[signature][1],
            action_kind=action_lookup[signature][2],
            tool_id=action_lookup[signature][3],
            semantic_payload=action_lookup[signature][4],
            semantic_payload_hash=action_lookup[signature][5],
            multiplicity=multiplicity,
        )
        for signature, multiplicity in sorted(grouped_actions.items())
    )
    reference_classes = tuple(
        EmpiricalReferenceClassV2(
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
        EmpiricalDependencyEdgeClassV2(
            source_signature=source,
            relation=relation,
            target_signature=target,
            multiplicity=multiplicity,
        )
        for (source, relation, target), multiplicity in sorted(edge_counter.items())
    )
    temporal_counter: Counter[tuple[str, TemporalRelation, str]] = Counter()
    for left_index, left in enumerate(action_rows):
        for right in action_rows[left_index + 1 :]:
            temporal_relation = _temporal_relation(left[6], right[6])
            if temporal_relation is not None:
                temporal_counter[(left[0], temporal_relation, right[0])] += 1
    temporal_relations = tuple(
        EmpiricalTemporalRelationClassV2(
            source_signature=source,
            relation=relation,
            target_signature=target,
            multiplicity=multiplicity,
        )
        for (source, relation, target), multiplicity in sorted(temporal_counter.items())
    )
    typed_lineage = tuple(
        TypedLineageEntryV2(lineage_kind=kind, value=value) for kind, value in sorted(lineage)
    )
    canonical_result = _normalize_semantic_value(
        trajectory.canonical_result,
        aliases=aliases,
        sequence_policy=sequence_policy,
    )
    if not isinstance(canonical_result, dict):
        raise TypeError("v2 canonical Result is not a Mapping")
    failure_pattern = {
        "public_failures": tuple(failure_rows),
        "semantic_rejections": tuple(
            {
                "rejection_ordinal": index,
                "semantics": _semantic_rejection_projection(
                    item,
                    aliases=aliases,
                    sequence_policy=sequence_policy,
                ),
            }
            for index, item in enumerate(trajectory.semantic_rejections)
        ),
    }
    values = {
        "omega_task_context_id": authorization.omega_task_context_id,
        "semantic_policy_id": semantic_policy.policy_id,
        "answer_semantic_schema_id": trajectory.answer_semantic_schema_id,
        "reference_projection_policy_id": trajectory.reference_projection_policy_id,
        "action_classes": action_classes,
        "reference_classes": reference_classes,
        "dependency_edge_classes": edges,
        "temporal_relation_classes": temporal_relations,
        "canonical_result": canonical_result,
        "canonical_result_semantics_hash": strict_canonical_hash(
            canonical_result,
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
    provisional = EmpiricalStructuralStateV2.model_construct(state_id="pending", **values)
    return EmpiricalStructuralStateV2(
        state_id=_identity(
            provisional,
            "state_id",
            "empirical_structural_state_v2:",
        ),
        **values,
    )


def map_independently_valid_public_trajectory_to_state_v2(
    *,
    trajectory: PublicTrajectoryProjectionV2,
    qualified_validity_report: QualifiedTrajectoryValidityReport,
    verifier_input_binding: QualifiedVerifierInputBindingV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
    omega_task_context_id: str,
    experimental_condition: ExperimentalConditionV2,
    empirical_route_signature: EmpiricalRouteSignatureV2,
    runtime_operation_aliases: Mapping[str, str],
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    raw_execution_artifact_hash: str,
) -> ValidOnlyEmpiricalStateAssignmentV2:
    if mapper_contract.semantic_policy_id != semantic_policy.policy_id:
        raise ValueError("v2 Mapper Contract crossed semantic policies")
    expected_route = make_empirical_route_signature_v2(trajectory)
    if expected_route != empirical_route_signature:
        raise ValueError("v2 empirical Route Signature does not match the trajectory")
    mapping: ValidOnlyMappingResultV2[EmpiricalStructuralStateV2] = (
        map_independently_valid_trajectory_to_state_v2(
            trajectory=trajectory,
            qualified_validity_report=qualified_validity_report,
            verifier_input_binding=verifier_input_binding,
            mapper_contract=mapper_contract,
            omega_task_context_id=omega_task_context_id,
            raw_execution_artifact_hash=raw_execution_artifact_hash,
            mapper=lambda authorization, bound_trajectory: _build_structural_state_v2(
                authorization,
                bound_trajectory,
                runtime_operation_aliases=runtime_operation_aliases,
                semantic_policy=semantic_policy,
            ),
        )
    )
    state = mapping.mapped_state
    values = {
        "mapping_result_id": mapping.result_id,
        "mapper_contract_id": mapper_contract.contract_id,
        "trajectory_id": trajectory.trajectory_id,
        "trajectory_semantic_content_hash": trajectory.trajectory_semantic_content_hash,
        "trajectory_bound_artifact_hash": trajectory.trajectory_bound_artifact_hash,
        "raw_execution_artifact_hash": raw_execution_artifact_hash,
        "qualified_verifier_input_hash": verifier_input_binding.qualified_verifier_input_hash,
        "qualified_validity_report_id": qualified_validity_report.report_id,
        "omega_task_context_id": omega_task_context_id,
        "structural_state_id": state.state_id,
        "experimental_condition_id": experimental_condition.condition_id,
        "empirical_route_signature_id": empirical_route_signature.route_signature_id,
        "static_path_catalog_id": experimental_condition.static_path_catalog_id,
        "raw_observation_prefix_hash": trajectory.raw_observation_prefix_hash,
        "raw_final_payload_hash": trajectory.raw_final_payload_hash,
        "canonical_result_semantics_hash": state.canonical_result_semantics_hash,
        "structural_state": state,
        "experimental_condition": experimental_condition,
        "empirical_route_signature": empirical_route_signature,
    }
    provisional = ValidOnlyEmpiricalStateAssignmentV2.model_construct(
        assignment_id="pending",
        **values,
    )
    return ValidOnlyEmpiricalStateAssignmentV2(
        assignment_id=_identity(
            provisional,
            "assignment_id",
            "valid_only_empirical_state_assignment_v2:",
        ),
        **values,
    )


def _contrast_rows(values: Sequence[BaseModel]) -> tuple[str, ...]:
    return tuple(
        sorted(strict_canonical_hash(item, prefix="state_contrast_component:") for item in values)
    )


def make_state_contrast_v2(
    left: EmpiricalStructuralStateV2,
    right: EmpiricalStructuralStateV2,
) -> StateContrastArtifactV2:
    if left.state_id == right.state_id:
        raise ValueError("State Contrast requires two distinct States")
    if left.state_id > right.state_id:
        left, right = right, left
    comparisons: dict[str, tuple[Any, Any]] = {
        "omega_task_context": (left.omega_task_context_id, right.omega_task_context_id),
        "semantic_context_policy": (
            (
                left.semantic_policy_id,
                left.answer_semantic_schema_id,
                left.reference_projection_policy_id,
            ),
            (
                right.semantic_policy_id,
                right.answer_semantic_schema_id,
                right.reference_projection_policy_id,
            ),
        ),
        "action_multiplicity_or_payload": (
            _contrast_rows(left.action_classes),
            _contrast_rows(right.action_classes),
        ),
        "typed_evidence_lineage": (left.typed_lineage, right.typed_lineage),
        "dependency_edge": (
            _contrast_rows(left.dependency_edge_classes),
            _contrast_rows(right.dependency_edge_classes),
        ),
        "canonical_result": (left.canonical_result, right.canonical_result),
        "failure_pattern": (left.failure_pattern, right.failure_pattern),
        "temporal_relation": (
            _contrast_rows(left.temporal_relation_classes),
            _contrast_rows(right.temporal_relation_classes),
        ),
    }
    witness = {
        key: {"left": left_value, "right": right_value}
        for key, (left_value, right_value) in comparisons.items()
        if left_value != right_value
    }
    if not witness:
        raise ValueError("distinct v2 States have no semantic contrast witness")
    values = {
        "left_state_id": left.state_id,
        "right_state_id": right.state_id,
        "differing_dimensions": tuple(sorted(witness)),
        "minimal_difference_witness": witness,
    }
    provisional = StateContrastArtifactV2.model_construct(contrast_id="pending", **values)
    return StateContrastArtifactV2(
        contrast_id=_identity(
            provisional,
            "contrast_id",
            "empirical_state_contrast:",
        ),
        **values,
    )
