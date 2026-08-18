from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.executable_support import (
    TypedAnswerProjectionContract,
)
from trusted_synthesis.core.trajectory.executable_task import (
    BoundEvidenceSupportLattice,
    CitationCompletenessContract,
    ExecutableTaskSemanticSource,
    MechanismCausalContract,
    PublicRuntimeContract,
    ToolClosureContract,
)
from trusted_synthesis.hashing import canonical_hash

PUBLIC_OPERATION_CONTRACT_VERSION = "public_operation_execution_contract.v2"
PUBLIC_STOP_READINESS_VERSION = "public_stop_readiness_contract.v2"
PUBLIC_STOP_READINESS_VIEW_VERSION = "public_stop_readiness_view.v1"
PUBLIC_OPERATION_RUNTIME_PROJECTION_VERSION = "public_operation_runtime_projection.v2"
OPERATIONAL_EXECUTABLE_TASK_PACKAGE_VERSION = "operational_executable_task_package.v2"
OPERATIONAL_EXECUTABLE_VERIFIER_VERSION = "operational_executable_verifier_binding.v2"
AUTHORITY_PRESERVING_PUBLIC_OPERATION_CONTRACT_VERSION = "public_operation_execution_contract.v3"
PUBLIC_ACTION_NEUTRAL_REPAIR_CONTRACT_VERSION = "public_action_neutral_repair_contract.v1"
PUBLIC_ACTION_NEUTRAL_REPAIR_VIEW_VERSION = "public_action_neutral_repair_view.v1"
PUBLIC_TERMINAL_VERIFICATION_TARGET_VERSION = "public_terminal_verification_target.v1"
PUBLIC_TERMINAL_VERIFICATION_TARGET_VIEW_VERSION = "public_terminal_verification_target_view.v1"
AUTHORITY_PRESERVING_STOP_READINESS_VERSION = "public_stop_readiness_contract.v3"
AUTHORITY_PRESERVING_STOP_READINESS_VIEW_VERSION = "public_stop_readiness_view.v2"
AUTHORITY_PRESERVING_RUNTIME_PROJECTION_VERSION = "public_operation_runtime_projection.v3"
AUTHORITY_PRESERVING_EXECUTABLE_TASK_PACKAGE_VERSION = "operational_executable_task_package.v3"
AUTHORITY_PRESERVING_EXECUTABLE_VERIFIER_VERSION = "operational_executable_verifier_binding.v3"

OperationNodeKind = Literal["normalization", "calculation"]
OperatorChoiceMode = Literal["not_applicable", "fixed_semantics", "model_context_choice"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PublicOperationPredicate(FrozenModel):
    selector: tuple[str, ...] = Field(min_length=1)
    value: Any


class PublicVariableResolutionRule(FrozenModel):
    source_tool_id: Literal["query_structured_fact", "open_document"]
    collection_selector: tuple[str, ...] = Field(min_length=1)
    evidence_id_selector: tuple[str, ...] = Field(min_length=1)
    equals: tuple[PublicOperationPredicate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rule(self) -> PublicVariableResolutionRule:
        if len({item.selector for item in self.equals}) != len(self.equals):
            raise ValueError("public variable resolution predicates are duplicated")
        return self


class PublicOperationVariable(FrozenModel):
    symbol: str = Field(min_length=1)
    semantic_role: str = Field(min_length=1)
    resolution_rules: tuple[PublicVariableResolutionRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_variable(self) -> PublicOperationVariable:
        if len({item.source_tool_id for item in self.resolution_rules}) != len(
            self.resolution_rules
        ):
            raise ValueError("public variable repeats a source tool resolution rule")
        _reject_private_disclosures(self.model_dump(mode="json"))
        return self


class PublicOperationInput(FrozenModel):
    source_symbol: str = Field(min_length=1)
    selector: str | None = None


class PublicOperationNode(FrozenModel):
    node_id: str = Field(min_length=1)
    node_kind: OperationNodeKind
    semantic_role: str = Field(min_length=1)
    tool_id: Literal["normalize_metric_unit_period", "calculator"]
    dependency_node_ids: tuple[str, ...] = ()
    inputs: tuple[PublicOperationInput, ...] = Field(min_length=1)
    output_symbol: str = Field(min_length=1)
    allowed_operator_ids: tuple[str, ...] = ()
    operator_choice_mode: OperatorChoiceMode
    operator_selection_rule: str | None = None
    operator_output_schemas: dict[str, str] = Field(default_factory=dict)
    required_output_schema: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    normalization_target: dict[str, Any] | None = None
    terminal: bool = False
    required_for_completion: Literal[True] = True
    decision_authority: Literal["model"] = "model"

    @model_validator(mode="after")
    def validate_node(self) -> PublicOperationNode:
        if self.dependency_node_ids != tuple(sorted(set(self.dependency_node_ids))):
            raise ValueError("public Operation dependencies are not canonical")
        if self.allowed_operator_ids != tuple(sorted(set(self.allowed_operator_ids))):
            raise ValueError("public Operation allowed operators are not canonical")
        if self.node_kind == "normalization":
            if self.tool_id != "normalize_metric_unit_period":
                raise ValueError("normalization node uses another public tool")
            if self.operator_choice_mode != "not_applicable" or self.allowed_operator_ids:
                raise ValueError("normalization node unexpectedly carries an operator choice")
            if not self.normalization_target or self.parameters:
                raise ValueError("normalization node target or parameters are malformed")
            if self.operator_output_schemas or self.required_output_schema is not None:
                raise ValueError(
                    "normalization node unexpectedly carries calculator output schemas"
                )
        else:
            if self.tool_id != "calculator" or self.normalization_target is not None:
                raise ValueError("calculation node has malformed tool semantics")
            if not self.allowed_operator_ids:
                raise ValueError("calculation node lacks an allowed operator")
            if (
                self.operator_choice_mode == "fixed_semantics"
                and len(self.allowed_operator_ids) != 1
            ):
                raise ValueError("fixed calculation node must expose one operator")
            if (
                self.operator_choice_mode == "model_context_choice"
                and len(self.allowed_operator_ids) < 2
            ):
                raise ValueError("model-choice node must expose symmetric alternatives")
            if self.operator_choice_mode == "not_applicable":
                raise ValueError("calculation node lacks operator-choice semantics")
        if self.operator_choice_mode == "model_context_choice":
            if not self.operator_selection_rule:
                raise ValueError("model-choice node lacks a public selection rule")
            if set(self.operator_output_schemas) != set(self.allowed_operator_ids):
                raise ValueError("calculation operator schemas are incomplete")
            if not self.required_output_schema:
                raise ValueError("calculation node lacks a required output schema")
            matching = sum(
                value == self.required_output_schema
                for value in self.operator_output_schemas.values()
            )
            if matching != 1:
                raise ValueError("public result schema does not identify one allowed operator")
        if self.operator_choice_mode != "model_context_choice" and self.operator_selection_rule:
            raise ValueError("fixed node unexpectedly carries a choice rule")
        _reject_private_disclosures(self.model_dump(mode="json"))
        return self


class PublicOperationContractView(FrozenModel):
    view_id: str = Field(min_length=1)
    variables: tuple[PublicOperationVariable, ...] = Field(min_length=1)
    nodes: tuple[PublicOperationNode, ...] = Field(min_length=1)
    terminal_node_id: str = Field(min_length=1)
    completion_rule: Literal["all_required_nodes_and_terminal_node"] = (
        "all_required_nodes_and_terminal_node"
    )
    acquisition_path_policy: Literal["model_owned_any_allowed_public_acquisition"] = (
        "model_owned_any_allowed_public_acquisition"
    )
    exact_tool_sequence_required: Literal[False] = False
    gold_evidence_ids_exposed: Literal[False] = False
    oracle_node_ids_exposed: Literal[False] = False
    correct_choice_exposed_for_model_choice: Literal[False] = False
    schema_version: str = PUBLIC_OPERATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_view(self) -> PublicOperationContractView:
        if tuple(item.symbol for item in self.variables) != tuple(
            sorted(item.symbol for item in self.variables)
        ):
            raise ValueError("public Operation variables are not canonical")
        if len({item.symbol for item in self.variables}) != len(self.variables):
            raise ValueError("public Operation variables are duplicated")
        node_ids = tuple(item.node_id for item in self.nodes)
        if node_ids != tuple(sorted(node_ids)) or len(set(node_ids)) != len(node_ids):
            raise ValueError("public Operation nodes are not canonical or unique")
        nodes = {item.node_id: item for item in self.nodes}
        if self.terminal_node_id not in nodes or not nodes[self.terminal_node_id].terminal:
            raise ValueError("public Operation terminal node is invalid")
        if sum(item.terminal for item in self.nodes) != 1:
            raise ValueError("public Operation contract must contain one terminal node")
        variable_symbols = {item.symbol for item in self.variables}
        output_to_node = {item.output_symbol: item.node_id for item in self.nodes}
        if len(output_to_node) != len(self.nodes):
            raise ValueError("public Operation output symbols are duplicated")
        for node in self.nodes:
            unknown_dependencies = set(node.dependency_node_ids) - set(nodes)
            if unknown_dependencies or node.node_id in node.dependency_node_ids:
                raise ValueError("public Operation node has an invalid dependency")
            for item in node.inputs:
                if item.source_symbol in variable_symbols:
                    continue
                producer = output_to_node.get(item.source_symbol)
                if producer is None or producer not in node.dependency_node_ids:
                    raise ValueError("public Operation input is detached from its producer")
        _validate_acyclic(nodes)
        if _terminal_ancestors(nodes, self.terminal_node_id) != set(nodes):
            raise ValueError("public Operation contains a node outside terminal closure")
        _reject_private_disclosures(
            self.model_dump(
                mode="json",
                exclude={
                    "view_id",
                    "gold_evidence_ids_exposed",
                    "oracle_node_ids_exposed",
                    "correct_choice_exposed_for_model_choice",
                },
            )
        )
        if self.view_id != public_operation_contract_view_id(self):
            raise ValueError("public Operation view identity is invalid")
        return self


class PublicOperationExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    source_program_dag_hash: str = Field(min_length=1)
    source_verifier_dag_hash: str = Field(min_length=1)
    public_view: PublicOperationContractView
    public_view_hash: str = Field(min_length=1)
    schema_version: str = PUBLIC_OPERATION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> PublicOperationExecutionContract:
        if self.public_view_hash != canonical_hash(
            self.public_view, prefix="public_operation_contract_view:"
        ):
            raise ValueError("public Operation view hash is invalid")
        if self.contract_id != public_operation_execution_contract_id(self):
            raise ValueError("public Operation contract identity is invalid")
        return self


_REPAIR_EXPOSED_FIELDS = (
    "error_category",
    "failed_tool_id",
    "identical_arguments_forbidden",
    "unresolved_public_variables",
    "unresolved_semantic_requirements",
)
_REPAIR_FORBIDDEN_BINDING_FIELDS = (
    "available_resolution_actions",
    "expected_arguments",
    "operator",
    "parameters",
    "required_argument_patch",
    "required_next_tools",
    "required_prerequisite_action",
    "suggested_argument_patch",
)


class PublicActionNeutralRepairContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    operation_contract_id: str = Field(min_length=1)
    exposed_context_fields: tuple[str, ...] = _REPAIR_EXPOSED_FIELDS
    forbidden_action_binding_fields: tuple[str, ...] = _REPAIR_FORBIDDEN_BINDING_FIELDS
    failed_attempt_tool_identity_exposed: Literal[True] = True
    correct_tool_disclosed: Literal[False] = False
    correct_operator_disclosed: Literal[False] = False
    correct_parameters_disclosed: Literal[False] = False
    expected_arguments_disclosed: Literal[False] = False
    model_retains_repair_decision: Literal[True] = True
    repair_semantics_source: Literal["typed_runtime_error_and_public_semantic_progress"] = (
        "typed_runtime_error_and_public_semantic_progress"
    )
    schema_version: str = PUBLIC_ACTION_NEUTRAL_REPAIR_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> PublicActionNeutralRepairContract:
        if self.exposed_context_fields != _REPAIR_EXPOSED_FIELDS:
            raise ValueError("action-neutral repair exposed fields changed")
        if self.forbidden_action_binding_fields != _REPAIR_FORBIDDEN_BINDING_FIELDS:
            raise ValueError("action-neutral repair forbidden fields changed")
        if self.contract_id != public_action_neutral_repair_contract_id(self):
            raise ValueError("action-neutral repair contract identity is invalid")
        return self


class PublicActionNeutralRepairView(FrozenModel):
    contract_id: str = Field(min_length=1)
    operation_contract_id: str = Field(min_length=1)
    exposed_context_fields: tuple[str, ...] = _REPAIR_EXPOSED_FIELDS
    forbidden_action_binding_fields: tuple[str, ...] = _REPAIR_FORBIDDEN_BINDING_FIELDS
    failed_attempt_tool_identity_exposed: Literal[True] = True
    correct_tool_disclosed: Literal[False] = False
    correct_operator_disclosed: Literal[False] = False
    correct_parameters_disclosed: Literal[False] = False
    expected_arguments_disclosed: Literal[False] = False
    model_retains_repair_decision: Literal[True] = True
    repair_semantics_source: Literal["typed_runtime_error_and_public_semantic_progress"] = (
        "typed_runtime_error_and_public_semantic_progress"
    )
    source_binding_identity_exposed: Literal[False] = False
    schema_version: str = PUBLIC_ACTION_NEUTRAL_REPAIR_VIEW_VERSION

    @model_validator(mode="after")
    def validate_view(self) -> PublicActionNeutralRepairView:
        if self.exposed_context_fields != _REPAIR_EXPOSED_FIELDS:
            raise ValueError("action-neutral repair view exposed fields changed")
        if self.forbidden_action_binding_fields != _REPAIR_FORBIDDEN_BINDING_FIELDS:
            raise ValueError("action-neutral repair view forbidden fields changed")
        _reject_private_disclosures(self.model_dump(mode="json"))
        return self


class PublicTerminalVerificationTargetView(FrozenModel):
    view_id: str = Field(min_length=1)
    operation_contract_id: str = Field(min_length=1)
    verification_tool_id: Literal["cross_check_evidence"] = "cross_check_evidence"
    evidence_argument_field: Literal["evidence_ids"] = "evidence_ids"
    claim_argument_field: Literal["claim_or_result"] = "claim_or_result"
    terminal_reference_field: Literal["operation_ref"] = "operation_ref"
    required_claim_fields: tuple[Literal["operation_ref"], ...] = ("operation_ref",)
    additional_claim_fields_policy: Literal["forbid"] = "forbid"
    reference_source: Literal["terminal_operation_ref_from_public_progress"] = (
        "terminal_operation_ref_from_public_progress"
    )
    verification_result_field: Literal["verified"] = "verified"
    verification_success_value: Literal[True] = True
    terminal_must_precede_verification: Literal[True] = True
    wrong_or_missing_reference_fails_closed: Literal[True] = True
    schema_version: str = PUBLIC_TERMINAL_VERIFICATION_TARGET_VIEW_VERSION

    @model_validator(mode="after")
    def validate_view(self) -> PublicTerminalVerificationTargetView:
        if self.required_claim_fields != (self.terminal_reference_field,):
            raise ValueError("terminal verification target claim schema changed")
        _reject_private_disclosures(self.model_dump(mode="json", exclude={"view_id"}))
        if self.view_id != public_terminal_verification_target_view_id(self):
            raise ValueError("terminal verification target view identity is invalid")
        return self


class PublicTerminalVerificationTarget(FrozenModel):
    target_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    operation_contract_id: str = Field(min_length=1)
    source_verifier_dag_hash: str = Field(min_length=1)
    public_view: PublicTerminalVerificationTargetView
    public_view_hash: str = Field(min_length=1)
    schema_version: str = PUBLIC_TERMINAL_VERIFICATION_TARGET_VERSION

    @model_validator(mode="after")
    def validate_target(self) -> PublicTerminalVerificationTarget:
        if self.public_view.operation_contract_id != self.operation_contract_id:
            raise ValueError("terminal verification target binds another Operation contract")
        if self.public_view_hash != canonical_hash(
            self.public_view, prefix="public_terminal_verification_target_view:"
        ):
            raise ValueError("terminal verification target view hash is invalid")
        if self.target_id != public_terminal_verification_target_id(self):
            raise ValueError("terminal verification target identity is invalid")
        return self


class PublicStopReadinessContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    operation_contract_id: str = Field(min_length=1)
    required_node_ids: tuple[str, ...] = Field(min_length=1)
    terminal_node_id: str = Field(min_length=1)
    terminal_verification_target_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    verification_after_terminal_required: Literal[True] = True
    final_answer_requires_stop_ready: Literal[True] = True
    maximum_postcompletion_tool_calls: Literal[0] = 0
    readiness_formula: Literal[
        "all_required_nodes_and_terminal_and_postterminal_verification_and_no_extra_action"
    ] = "all_required_nodes_and_terminal_and_postterminal_verification_and_no_extra_action"
    schema_version: str = PUBLIC_STOP_READINESS_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> PublicStopReadinessContract:
        if self.required_node_ids != tuple(sorted(set(self.required_node_ids))):
            raise ValueError("public stop required nodes are not canonical")
        if self.terminal_node_id not in self.required_node_ids:
            raise ValueError("public stop contract omits the terminal node")
        if (
            self.schema_version == AUTHORITY_PRESERVING_STOP_READINESS_VERSION
            and self.terminal_verification_target_id is None
        ):
            raise ValueError("authority-preserving stop contract lacks a verification target")
        if self.contract_id != public_stop_readiness_contract_id(self):
            raise ValueError("public stop-readiness identity is invalid")
        return self


class PublicStopReadinessView(FrozenModel):
    """Model-visible stop semantics with source-binding identities removed."""

    contract_id: str = Field(min_length=1)
    operation_contract_id: str = Field(min_length=1)
    required_node_ids: tuple[str, ...] = Field(min_length=1)
    terminal_node_id: str = Field(min_length=1)
    terminal_verification_target_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    verification_after_terminal_required: Literal[True] = True
    final_answer_requires_stop_ready: Literal[True] = True
    maximum_postcompletion_tool_calls: Literal[0] = 0
    readiness_formula: Literal[
        "all_required_nodes_and_terminal_and_postterminal_verification_and_no_extra_action"
    ] = "all_required_nodes_and_terminal_and_postterminal_verification_and_no_extra_action"
    source_binding_identity_exposed: Literal[False] = False
    schema_version: str = PUBLIC_STOP_READINESS_VIEW_VERSION

    @model_validator(mode="after")
    def validate_view(self) -> PublicStopReadinessView:
        if self.required_node_ids != tuple(sorted(set(self.required_node_ids))):
            raise ValueError("public stop view required nodes are not canonical")
        if self.terminal_node_id not in self.required_node_ids:
            raise ValueError("public stop view omits the terminal node")
        if (
            self.schema_version == AUTHORITY_PRESERVING_STOP_READINESS_VIEW_VERSION
            and self.terminal_verification_target_id is None
        ):
            raise ValueError("authority-preserving stop view lacks a verification target")
        _reject_private_disclosures(self.model_dump(mode="json"))
        return self


class PublicOperationRuntimeProjection(FrozenModel):
    projection_id: str = Field(min_length=1)
    operation_contract_id: str = Field(min_length=1)
    stop_readiness_contract_id: str = Field(min_length=1)
    action_neutral_repair_contract_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    terminal_verification_target_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    visible_progress_fields: tuple[str, ...] = Field(min_length=1)
    hidden_binding_fields: tuple[str, ...] = Field(min_length=1)
    correct_model_choice_hidden: Literal[True] = True
    gold_evidence_ids_hidden: Literal[True] = True
    schema_version: str = PUBLIC_OPERATION_RUNTIME_PROJECTION_VERSION

    @model_validator(mode="after")
    def validate_projection(self) -> PublicOperationRuntimeProjection:
        groups = (self.visible_progress_fields, self.hidden_binding_fields)
        if any(group != tuple(sorted(set(group))) for group in groups):
            raise ValueError("public Operation projection fields are not canonical")
        if set(self.visible_progress_fields) & set(self.hidden_binding_fields):
            raise ValueError("public Operation projection exposes a hidden field")
        if self.schema_version == AUTHORITY_PRESERVING_RUNTIME_PROJECTION_VERSION and (
            self.action_neutral_repair_contract_id is None
            or self.terminal_verification_target_id is None
        ):
            raise ValueError("authority-preserving Runtime projection lacks a public contract")
        if self.projection_id != public_operation_runtime_projection_id(self):
            raise ValueError("public Operation Runtime projection identity is invalid")
        return self


class PublicOperationNodeBinding(FrozenModel):
    public_node_id: str = Field(min_length=1)
    source_program_node_id: str | None = None
    expected_operator_id: str | None = None


class OperationalExecutableVerifierBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    answer_projection_contract_id: str = Field(min_length=1)
    evidence_support_lattice_id: str = Field(min_length=1)
    citation_contract_id: str = Field(min_length=1)
    public_runtime_contract_id: str = Field(min_length=1)
    mechanism_contract_id: str = Field(min_length=1)
    operation_contract_id: str = Field(min_length=1)
    stop_readiness_contract_id: str = Field(min_length=1)
    runtime_projection_id: str = Field(min_length=1)
    action_neutral_repair_contract_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    terminal_verification_target_id: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_program_dag_hash: str = Field(min_length=1)
    source_verifier_dag_hash: str = Field(min_length=1)
    node_bindings: tuple[PublicOperationNodeBinding, ...] = Field(min_length=1)
    verifier_implementation_id: str = Field(min_length=1)
    verifier_version: str = Field(min_length=1)
    evidence_acceptance_rule: Literal["registered_sufficient_set_membership"] = (
        "registered_sufficient_set_membership"
    )
    exact_gold_equality_required: bool
    schema_version: str = OPERATIONAL_EXECUTABLE_VERIFIER_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> OperationalExecutableVerifierBinding:
        if tuple(item.public_node_id for item in self.node_bindings) != tuple(
            sorted(item.public_node_id for item in self.node_bindings)
        ):
            raise ValueError("operational Verifier node bindings are not canonical")
        if len({item.public_node_id for item in self.node_bindings}) != len(self.node_bindings):
            raise ValueError("operational Verifier node bindings are duplicated")
        if self.schema_version == AUTHORITY_PRESERVING_EXECUTABLE_VERIFIER_VERSION and (
            self.action_neutral_repair_contract_id is None
            or self.terminal_verification_target_id is None
        ):
            raise ValueError("authority-preserving Verifier lacks a public contract binding")
        if self.binding_id != operational_executable_verifier_binding_id(self):
            raise ValueError("operational executable Verifier identity is invalid")
        return self


class OperationalExecutableTaskPackage(FrozenModel):
    package_id: str = Field(min_length=1)
    semantic_source: ExecutableTaskSemanticSource
    task: TaskPackage
    tool_closure: ToolClosureContract
    answer_projection: TypedAnswerProjectionContract
    evidence_support_lattice: BoundEvidenceSupportLattice
    citation_contract: CitationCompletenessContract
    public_runtime_contract: PublicRuntimeContract
    mechanism_contract: MechanismCausalContract
    operation_contract: PublicOperationExecutionContract
    stop_readiness_contract: PublicStopReadinessContract
    runtime_projection: PublicOperationRuntimeProjection
    verifier_binding: OperationalExecutableVerifierBinding
    action_neutral_repair_contract: PublicActionNeutralRepairContract | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    terminal_verification_target: PublicTerminalVerificationTarget | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    schema_version: str = OPERATIONAL_EXECUTABLE_TASK_PACKAGE_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> OperationalExecutableTaskPackage:
        source_id = self.semantic_source.semantic_source_id
        source_bound = (
            self.tool_closure.semantic_source_id,
            self.answer_projection.task_id,
            self.evidence_support_lattice.semantic_source_id,
            self.citation_contract.semantic_source_id,
            self.public_runtime_contract.semantic_source_id,
            self.mechanism_contract.semantic_source_id,
            self.operation_contract.semantic_source_id,
            self.stop_readiness_contract.semantic_source_id,
            self.verifier_binding.semantic_source_id,
            *(
                (self.action_neutral_repair_contract.semantic_source_id,)
                if self.action_neutral_repair_contract is not None
                else ()
            ),
            *(
                (self.terminal_verification_target.semantic_source_id,)
                if self.terminal_verification_target is not None
                else ()
            ),
        )
        if any(item != source_id for item in source_bound):
            raise ValueError("operational task contracts were compiled from different sources")
        if self.task.task_id != self.package_id:
            raise ValueError("operational package and TaskPackage identities differ")
        if tuple(sorted(self.task.public.allowed_tools)) != self.tool_closure.allowed_tool_ids:
            raise ValueError("operational Task Allowed Tools differ from tool closure")
        if self.public_runtime_contract.allowed_tool_ids != self.tool_closure.allowed_tool_ids:
            raise ValueError("operational Runtime differs from tool closure")
        if (
            self.stop_readiness_contract.operation_contract_id
            != self.operation_contract.contract_id
        ):
            raise ValueError("public stop contract is detached from Operation execution")
        if self.runtime_projection.operation_contract_id != self.operation_contract.contract_id:
            raise ValueError("Runtime projection is detached from Operation execution")
        if (
            self.runtime_projection.stop_readiness_contract_id
            != self.stop_readiness_contract.contract_id
        ):
            raise ValueError("Runtime projection is detached from stop readiness")
        authority_preserving = (
            self.schema_version == AUTHORITY_PRESERVING_EXECUTABLE_TASK_PACKAGE_VERSION
        )
        if authority_preserving and (
            self.action_neutral_repair_contract is None or self.terminal_verification_target is None
        ):
            raise ValueError("authority-preserving package lacks repair or verification")
        if self.action_neutral_repair_contract is not None:
            if (
                self.action_neutral_repair_contract.operation_contract_id
                != self.operation_contract.contract_id
            ):
                raise ValueError("repair contract is detached from Operation execution")
            if (
                self.runtime_projection.action_neutral_repair_contract_id
                != self.action_neutral_repair_contract.contract_id
            ):
                raise ValueError("Runtime projection is detached from repair authority")
        if self.terminal_verification_target is not None:
            target_id = self.terminal_verification_target.target_id
            if (
                self.terminal_verification_target.source_verifier_dag_hash
                != self.operation_contract.source_verifier_dag_hash
            ):
                raise ValueError("terminal verification target binds another Verifier DAG")
            if self.stop_readiness_contract.terminal_verification_target_id != target_id:
                raise ValueError("stop readiness is detached from terminal verification")
            if self.runtime_projection.terminal_verification_target_id != target_id:
                raise ValueError("Runtime projection is detached from terminal verification")
        binding_values: dict[str, str | None] = {
            "answer_projection_contract_id": self.answer_projection.contract_id,
            "evidence_support_lattice_id": self.evidence_support_lattice.lattice_id,
            "citation_contract_id": self.citation_contract.contract_id,
            "public_runtime_contract_id": self.public_runtime_contract.contract_id,
            "mechanism_contract_id": self.mechanism_contract.contract_id,
            "operation_contract_id": self.operation_contract.contract_id,
            "stop_readiness_contract_id": self.stop_readiness_contract.contract_id,
            "runtime_projection_id": self.runtime_projection.projection_id,
        }
        if authority_preserving:
            binding_values.update(
                {
                    "action_neutral_repair_contract_id": (
                        self.action_neutral_repair_contract.contract_id
                        if self.action_neutral_repair_contract is not None
                        else None
                    ),
                    "terminal_verification_target_id": (
                        self.terminal_verification_target.target_id
                        if self.terminal_verification_target is not None
                        else None
                    ),
                }
            )
        if any(
            getattr(self.verifier_binding, key) != value for key, value in binding_values.items()
        ):
            raise ValueError("operational Verifier does not bind the packaged contracts")
        if (
            self.verifier_binding.source_program_dag_hash
            != self.operation_contract.source_program_dag_hash
        ):
            raise ValueError("operational Verifier and public contract bind another Program")
        if (
            self.verifier_binding.source_verifier_dag_hash
            != self.operation_contract.source_verifier_dag_hash
        ):
            raise ValueError("operational Verifier and public contract bind another Verifier DAG")
        if {item.public_node_id for item in self.verifier_binding.node_bindings} != {
            item.node_id for item in self.operation_contract.public_view.nodes
        }:
            raise ValueError("operational Verifier does not map every public Operation node")
        if (
            self.verifier_binding.exact_gold_equality_required
            != self.evidence_support_lattice.exact_equality_required
        ):
            raise ValueError("operational Verifier equality differs from Evidence lattice")
        public_bindings = self.task.public.metadata.get("executable_support_bindings")
        expected_public = {
            "answer_projection_contract_id": self.answer_projection.contract_id,
            "citation_contract_id": self.citation_contract.contract_id,
            "intended_use": self.semantic_source.intended_use,
            "operation_contract_id": self.operation_contract.contract_id,
            "public_runtime_contract_id": self.public_runtime_contract.contract_id,
            "runtime_projection_id": self.runtime_projection.projection_id,
            "stop_readiness_contract_id": self.stop_readiness_contract.contract_id,
            "tool_closure_contract_id": self.tool_closure.closure_id,
        }
        if authority_preserving:
            expected_public.update(
                {
                    "action_neutral_repair_contract_id": (
                        self.action_neutral_repair_contract.contract_id
                        if self.action_neutral_repair_contract is not None
                        else "missing"
                    ),
                    "terminal_verification_target_id": (
                        self.terminal_verification_target.target_id
                        if self.terminal_verification_target is not None
                        else "missing"
                    ),
                }
            )
        if public_bindings != expected_public:
            raise ValueError("Task Public Spec does not expose operational bindings")
        guidance = self.task.public.metadata.get("agent_contract_guidance")
        if not isinstance(guidance, Mapping):
            raise ValueError("operational Task lacks public Agent guidance")
        if guidance.get(
            "public_operation_execution_contract"
        ) != self.operation_contract.public_view.model_dump(mode="json"):
            raise ValueError("Task Public Spec exposes another Operation contract")
        observed_stop = guidance.get("public_stop_readiness_contract")
        expected_stop = public_stop_readiness_view(self.stop_readiness_contract).model_dump(
            mode="json"
        )
        legacy_stop = self.stop_readiness_contract.model_dump(mode="json")
        if self.schema_version in {
            OPERATIONAL_EXECUTABLE_TASK_PACKAGE_VERSION,
            AUTHORITY_PRESERVING_EXECUTABLE_TASK_PACKAGE_VERSION,
        }:
            stop_matches = observed_stop == expected_stop
        else:
            stop_matches = observed_stop in (expected_stop, legacy_stop)
        if not stop_matches:
            raise ValueError("Task Public Spec exposes another stop contract")
        if authority_preserving:
            if (
                self.action_neutral_repair_contract is None
                or self.terminal_verification_target is None
            ):
                raise ValueError("authority-preserving public contract is incomplete")
            expected_repair = public_action_neutral_repair_view(
                self.action_neutral_repair_contract
            ).model_dump(mode="json")
            if guidance.get("public_action_neutral_repair_contract") != expected_repair:
                raise ValueError("Task Public Spec exposes another repair contract")
            expected_target = self.terminal_verification_target.public_view.model_dump(mode="json")
            if guidance.get("public_terminal_verification_target") != expected_target:
                raise ValueError("Task Public Spec exposes another terminal verification target")
        oracle_bindings = self.task.oracle.selection_contract.get("executable_support_bindings")
        expected_oracle = {
            **expected_public,
            "evidence_support_lattice_id": self.evidence_support_lattice.lattice_id,
            "mechanism_contract_id": self.mechanism_contract.contract_id,
            "semantic_source_id": source_id,
            "verifier_binding_id": self.verifier_binding.binding_id,
        }
        if oracle_bindings != expected_oracle:
            raise ValueError("Task Oracle Contract does not bind operational support")
        if self.package_id != operational_executable_task_package_id(self):
            raise ValueError("operational executable task package identity is invalid")
        return self


def public_operation_contract_view_id(value: PublicOperationContractView) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"view_id"}),
        prefix="public_operation_contract_view:",
    )


def public_operation_execution_contract_id(value: PublicOperationExecutionContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="public_operation_execution_contract:",
    )


def public_action_neutral_repair_contract_id(
    value: PublicActionNeutralRepairContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="public_action_neutral_repair_contract:",
    )


def public_action_neutral_repair_view(
    value: PublicActionNeutralRepairContract,
) -> PublicActionNeutralRepairView:
    return PublicActionNeutralRepairView(
        contract_id=value.contract_id,
        operation_contract_id=value.operation_contract_id,
        exposed_context_fields=value.exposed_context_fields,
        forbidden_action_binding_fields=value.forbidden_action_binding_fields,
        failed_attempt_tool_identity_exposed=value.failed_attempt_tool_identity_exposed,
        correct_tool_disclosed=value.correct_tool_disclosed,
        correct_operator_disclosed=value.correct_operator_disclosed,
        correct_parameters_disclosed=value.correct_parameters_disclosed,
        expected_arguments_disclosed=value.expected_arguments_disclosed,
        model_retains_repair_decision=value.model_retains_repair_decision,
        repair_semantics_source=value.repair_semantics_source,
    )


def public_terminal_verification_target_view_id(
    value: PublicTerminalVerificationTargetView,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"view_id"}),
        prefix="public_terminal_verification_target_view:",
    )


def public_terminal_verification_target_id(
    value: PublicTerminalVerificationTarget,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"target_id"}),
        prefix="public_terminal_verification_target:",
    )


def public_stop_readiness_contract_id(value: PublicStopReadinessContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="public_stop_readiness_contract:",
    )


def public_stop_readiness_view(
    value: PublicStopReadinessContract,
) -> PublicStopReadinessView:
    return PublicStopReadinessView(
        contract_id=value.contract_id,
        operation_contract_id=value.operation_contract_id,
        required_node_ids=value.required_node_ids,
        terminal_node_id=value.terminal_node_id,
        terminal_verification_target_id=value.terminal_verification_target_id,
        verification_after_terminal_required=value.verification_after_terminal_required,
        final_answer_requires_stop_ready=value.final_answer_requires_stop_ready,
        maximum_postcompletion_tool_calls=value.maximum_postcompletion_tool_calls,
        readiness_formula=value.readiness_formula,
        schema_version=(
            AUTHORITY_PRESERVING_STOP_READINESS_VIEW_VERSION
            if value.schema_version == AUTHORITY_PRESERVING_STOP_READINESS_VERSION
            else PUBLIC_STOP_READINESS_VIEW_VERSION
        ),
    )


def public_operation_runtime_projection_id(value: PublicOperationRuntimeProjection) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"projection_id"}),
        prefix="public_operation_runtime_projection:",
    )


def operational_executable_verifier_binding_id(
    value: OperationalExecutableVerifierBinding,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"binding_id"}),
        prefix="operational_executable_verifier_binding:",
    )


def operational_executable_task_package_id(value: OperationalExecutableTaskPackage) -> str:
    payload = value.model_dump(mode="json", exclude={"package_id"})
    payload["task"]["task_id"] = "self"
    payload["task"]["public"]["task_id"] = "self"
    payload["task"]["oracle"]["task_id"] = "self"
    return canonical_hash(payload, prefix="operational_executable_task_package:")


def _reject_private_disclosures(value: object) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).casefold()
    forbidden = (
        "evidence:",
        "gold_evidence",
        "hidden_program",
        "oracle_node",
        "semantic_source",
        "source_program",
        "expected_operator",
        "selected_operator",
        "compiler_witness",
    )
    if any(item in serialized for item in forbidden):
        raise ValueError("public Operation contract exposes a private identity or decision")


def _validate_acyclic(nodes: dict[str, PublicOperationNode]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ValueError("public Operation dependencies contain a cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency in nodes[node_id].dependency_node_ids:
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in nodes:
        visit(node_id)


def _terminal_ancestors(nodes: dict[str, PublicOperationNode], terminal_node_id: str) -> set[str]:
    output: set[str] = set()

    def collect(node_id: str) -> None:
        if node_id in output:
            return
        output.add(node_id)
        for dependency in nodes[node_id].dependency_node_ids:
            collect(dependency)

    collect(terminal_node_id)
    return output
