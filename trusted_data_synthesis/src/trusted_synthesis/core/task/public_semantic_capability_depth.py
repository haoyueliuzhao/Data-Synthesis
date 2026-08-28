from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import (
    ProgramExecution,
    ProgramExecutionError,
    ProgramVerification,
    TaskProgramExecutor,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
    make_program,
)
from trusted_synthesis.hashing import canonical_hash

PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION = "public_semantic_capability_depth.v1"
PUBLIC_ACTION_ID_LENGTH: Final = 24
PUBLIC_CANDIDATE_DESCRIPTION: Final = "Apply the displayed public operation."

OPERATOR_CATALOG: Final = {
    "compare": "Compare two numeric public records and return the higher reference and gap.",
    "difference": "Subtract the first numeric public record from the second.",
    "growth": "Compute relative percentage change from the first record to the second.",
}
OPERATOR_OUTPUT_FIELDS: Final = {
    "compare": ("difference", "higher_ref"),
    "difference": ("value",),
    "growth": ("value",),
}
CONTROL_COMMANDS: Final = ("stop", "repeat_program", "recompute_result")
VERDICT_CATALOG: Final = ("true", "false", "unknown")
FORBIDDEN_MODEL_VISIBLE_KEYS: Final = {
    "capability_family",
    "depth",
    "evidence_id",
    "evidence_version_id",
    "expected_result",
    "future_state_graph",
    "gold_evidence_id",
    "program_operator_id",
    "program_input_record_handles",
    "reference_action",
    "reference_candidate_id",
    "required_event_multiplicities",
    "source_record_id",
    "target_capability_action",
}
FORBIDDEN_MODEL_VISIBLE_VALUE_PREFIXES: Final = (
    "evidence:",
    "evidence_version:",
    "program:",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _make_identity_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: _identity(provisional, field, prefix)}, **values)


class PublicSemanticConstraint(FrozenModel):
    selector: tuple[str, ...] = Field(min_length=1)
    value: Any


class PublicSemanticRecord(FrozenModel):
    record_handle: str = Field(pattern=r"^public_finance_record:[0-9a-f]{64}$")
    semantic_fields: dict[str, Any] = Field(min_length=7)
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> PublicSemanticRecord:
        if self.record_handle != canonical_hash(
            self.semantic_fields,
            prefix="public_finance_record:",
        ):
            raise ValueError("public Finance record handle is not content-derived")
        if scan_model_visible_leakage(self.semantic_fields):
            raise ValueError("public Finance record exposes a Host-only identity")
        return self


class PublicResolutionRule(FrozenModel):
    rule_handle: str = Field(pattern=r"^public_resolution_rule:[0-9a-f]{64}$")
    variable_symbol: str = Field(min_length=1)
    semantic_role: str = Field(min_length=1)
    collection_selector: tuple[str, ...] = Field(min_length=1)
    equals: tuple[PublicSemanticConstraint, ...] = Field(min_length=1)
    source_tool_id: str = Field(min_length=1)
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_rule(self) -> PublicResolutionRule:
        if self.rule_handle != _identity(
            self,
            "rule_handle",
            "public_resolution_rule:",
        ):
            raise ValueError("public resolution Rule identity is invalid")
        return self


class PublicOperationSemantic(FrozenModel):
    operation_handle: str = Field(pattern=r"^public_operation:[0-9a-f]{64}$")
    semantic_role: str = Field(min_length=1)
    node_kind: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    input_symbols: tuple[str, ...]
    dependency_handles: tuple[str, ...]
    allowed_operator_ids: tuple[str, ...]
    normalization_target: dict[str, Any] | None = None
    output_symbol: str = Field(min_length=1)
    output_handle: str = Field(pattern=r"^public_operation_output:[0-9a-f]{64}$")
    required_for_completion: bool
    terminal: bool
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_operation(self) -> PublicOperationSemantic:
        expected_output = canonical_hash(
            {
                "semantic_role": self.semantic_role,
                "node_kind": self.node_kind,
                "tool_id": self.tool_id,
                "output_symbol": self.output_symbol,
            },
            prefix="public_operation_output:",
        )
        if self.output_handle != expected_output:
            raise ValueError("public operation output handle is invalid")
        if self.operation_handle != _identity(
            self,
            "operation_handle",
            "public_operation:",
        ):
            raise ValueError("public operation identity is invalid")
        return self


class PublicSemanticTask(FrozenModel):
    instruction: str = Field(min_length=1)
    domain: Literal["finance"] = "finance"
    allowed_tools: tuple[str, ...] = Field(min_length=1)
    answer_type: str = Field(min_length=1)
    answer_fields: tuple[str, ...] = Field(min_length=1)
    aliases: tuple[str, ...] = Field(min_length=1)
    periods: tuple[str, ...] = Field(min_length=1)
    source_count: int = Field(ge=1)
    records: tuple[PublicSemanticRecord, PublicSemanticRecord]
    resolution_rules: tuple[PublicResolutionRule, ...] = Field(min_length=4)
    operations: tuple[PublicOperationSemantic, ...] = Field(min_length=1)
    terminal_operation_handle: str = Field(min_length=1)
    operator_catalog: dict[str, str] = OPERATOR_CATALOG
    operator_output_fields: dict[str, tuple[str, ...]] = OPERATOR_OUTPUT_FIELDS
    completion_rule: str = Field(min_length=1)
    stop_readiness: dict[str, Any] = Field(min_length=4)
    control_commands: tuple[str, ...] = CONTROL_COMMANDS
    verdict_catalog: tuple[str, ...] = VERDICT_CATALOG
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_task(self) -> PublicSemanticTask:
        record_handles = {item.record_handle for item in self.records}
        operation_handles = {item.operation_handle for item in self.operations}
        if len(record_handles) != 2 or len(operation_handles) != len(self.operations):
            raise ValueError("public semantic Task repeats a record or operation")
        if self.terminal_operation_handle not in operation_handles:
            raise ValueError("public semantic Task terminal operation is absent")
        if set(self.operator_catalog) != set(self.operator_output_fields):
            raise ValueError("public semantic Task operator catalogs are inconsistent")
        allowed_operators = {
            operator_id
            for operation in self.operations
            for operator_id in operation.allowed_operator_ids
        }
        if not allowed_operators <= set(self.operator_catalog):
            raise ValueError("public semantic Task exposes an unregistered operator")
        if self.control_commands != CONTROL_COMMANDS or self.verdict_catalog != VERDICT_CATALOG:
            raise ValueError("public semantic Task control language changed")
        if scan_model_visible_leakage(self.model_dump(mode="json")):
            raise ValueError("public semantic Task contains a Host-only field")
        return self

    @property
    def semantic_hash(self) -> str:
        return canonical_hash(
            self.model_dump(mode="json"),
            prefix="public_semantic_finance_task:",
        )


class PublicOperationPayload(FrozenModel):
    decision_kind: str = Field(min_length=1)
    tool_id: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(min_length=1)
    description: Literal["Apply the displayed public operation."] = PUBLIC_CANDIDATE_DESCRIPTION
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION

    @property
    def semantic_key(self) -> str:
        return canonical_hash(
            self.model_dump(mode="json"),
            prefix="public_semantic_choice:",
        )


class HostSemanticChoice(FrozenModel):
    semantic_key: str = Field(min_length=1)
    operation: PublicOperationPayload
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_choice(self) -> HostSemanticChoice:
        if self.semantic_key != self.operation.semantic_key:
            raise ValueError("Host semantic Choice identity is invalid")
        return self


class PublicDecisionState(FrozenModel):
    state_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    decision_kind: str = Field(min_length=1)
    facts: dict[str, Any] = Field(min_length=1)
    history: tuple[dict[str, Any], ...] = ()
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_state(self) -> PublicDecisionState:
        if scan_model_visible_leakage(self.model_dump(mode="json")):
            raise ValueError("public Decision State contains Host-only semantics")
        return self


class TargetComponent(FrozenModel):
    component_id: str = Field(min_length=1)
    component_key: str = Field(min_length=1)
    public_state: PublicDecisionState
    choices: tuple[HostSemanticChoice, HostSemanticChoice, HostSemanticChoice]
    reference_semantic_key: str = Field(min_length=1)
    target_capability_component: Literal[True] = True
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_component(self) -> TargetComponent:
        keys = {item.semantic_key for item in self.choices}
        if len(keys) != 3 or self.reference_semantic_key not in keys:
            raise ValueError("target Component does not contain three unique grounded choices")
        if any(
            item.operation.decision_kind != self.public_state.decision_kind for item in self.choices
        ):
            raise ValueError("target Component crosses a Decision kind")
        if self.component_id != _identity(
            self,
            "component_id",
            "public_semantic_target_component:",
        ):
            raise ValueError("target Component identity is invalid")
        return self


class PresentedPublicCandidate(FrozenModel):
    action_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    presentation_index: int = Field(ge=0, le=2)
    operation: PublicOperationPayload
    padding: str = ""
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION


class PublicSemanticPrompt(FrozenModel):
    prompt_hash: str = Field(min_length=64, max_length=64)
    rendered_bytes: int = Field(ge=1)
    task: PublicSemanticTask
    state: PublicDecisionState
    candidates: tuple[
        PresentedPublicCandidate,
        PresentedPublicCandidate,
        PresentedPublicCandidate,
    ]
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_prompt(self) -> PublicSemanticPrompt:
        if tuple(item.presentation_index for item in self.candidates) != (0, 1, 2):
            raise ValueError("public semantic Prompt positions are not contiguous")
        if len({item.action_id for item in self.candidates}) != 3:
            raise ValueError("public semantic Prompt repeats an action ID")
        if any(
            item.operation.decision_kind != self.state.decision_kind for item in self.candidates
        ):
            raise ValueError("public semantic Prompt crosses a Decision kind")
        lengths = {len(canonical_bytes(item.model_dump(mode="json"))) for item in self.candidates}
        if len(lengths) != 1:
            raise ValueError("public semantic Candidate encodings are not equal length")
        payload = self.model_dump(
            mode="json",
            exclude={"prompt_hash", "rendered_bytes", "schema_version"},
        )
        rendered = canonical_bytes(payload)
        if self.prompt_hash != hashlib.sha256(rendered).hexdigest():
            raise ValueError("public semantic Prompt hash is invalid")
        if self.rendered_bytes != len(rendered):
            raise ValueError("public semantic Prompt byte count is invalid")
        return self


class SemanticExecutionResult(FrozenModel):
    result_id: str = Field(min_length=1)
    selected_program: TaskProgram | None
    program_execution: ProgramExecution | None
    oracle_verification: ProgramVerification | None
    executor_invocation_count: int = Field(ge=0)
    oracle_verifier_invocation_count: int = Field(ge=0, le=1)
    deterministic_failure_observation_count: int = Field(ge=0)
    postcompletion_call_count: int = Field(ge=0)
    execution_error_code: str | None = None
    public_contract_checks: dict[str, bool] = Field(min_length=1)
    program_valid: bool
    base_valid: bool
    mechanism_qualified: bool
    qualified_valid: bool
    chosen_semantic_keys: tuple[str, ...] = Field(min_length=1)
    result_assigned_by_host: Literal[False] = False
    schema_version: str = PUBLIC_SEMANTIC_CAPABILITY_DEPTH_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> SemanticExecutionResult:
        if self.qualified_valid != (self.base_valid and self.mechanism_qualified):
            raise ValueError("public semantic Qualified validity is inconsistent")
        if self.program_valid != bool(
            self.oracle_verification is not None and self.oracle_verification.passed
        ):
            raise ValueError("public semantic Program validity is inconsistent")
        if (self.program_execution is None) != (self.executor_invocation_count == 0):
            if not (self.program_execution is not None and self.executor_invocation_count == 2):
                raise ValueError("public semantic Executor accounting is inconsistent")
        if self.result_id != _identity(
            self,
            "result_id",
            "public_semantic_execution_result:",
        ):
            raise ValueError("public semantic execution Result identity is invalid")
        return self


@dataclass(frozen=True)
class SemanticRuntimeBinding:
    task: PublicSemanticTask
    components: tuple[TargetComponent, ...]
    original_program: TaskProgram
    evidence_by_handle: Mapping[str, EvidenceItem]
    registry: OperationRegistry


def scan_model_visible_leakage(value: Any, path: str = "$") -> tuple[str, ...]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).casefold()
            if key_text in FORBIDDEN_MODEL_VISIBLE_KEYS:
                findings.append(f"{path}.{key}:host_only_key")
            findings.extend(scan_model_visible_leakage(item, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            findings.extend(scan_model_visible_leakage(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        folded = value.casefold()
        if folded.startswith(FORBIDDEN_MODEL_VISIBLE_VALUE_PREFIXES):
            findings.append(f"{path}:host_identity_value")
    return tuple(sorted(set(findings)))


def public_record_from_evidence(item: EvidenceItem) -> PublicSemanticRecord:
    raw = item.model_dump(mode="json")
    fields = {
        "frequency": raw["temporal_context"]["frequency"],
        "metric": {
            "definition_id": raw["definition"]["definition_id"],
            "metric_name": raw["definition"]["attributes"].get("metric_name"),
            "predicate": raw["predicate"],
        },
        "payload": raw["payload"],
        "period": raw["temporal_context"]["label"],
        "source": {
            "authority": raw["source"]["authority"],
            "name": raw["source"]["name"],
            "source_id": raw["source"]["source_id"],
        },
        "subject": {
            "name": raw["subject"]["name"],
            "subject_id": raw["subject"]["subject_id"],
            "type": raw["subject"]["subject_type"],
        },
        "time_basis": raw["temporal_context"]["basis"],
    }
    return PublicSemanticRecord(
        record_handle=canonical_hash(fields, prefix="public_finance_record:"),
        semantic_fields=fields,
    )


def project_public_semantic_task(
    task_public: Mapping[str, Any],
    evidence: Sequence[EvidenceItem],
) -> PublicSemanticTask:
    public = dict(task_public)
    guidance = cast(
        Mapping[str, Any],
        cast(Mapping[str, Any], public["metadata"])["agent_contract_guidance"],
    )
    operation_contract = cast(Mapping[str, Any], guidance["public_operation_execution_contract"])
    records = [public_record_from_evidence(item) for item in evidence]
    records.sort(key=lambda item: item.record_handle)

    rules: list[PublicResolutionRule] = []
    for variable in cast(Sequence[Mapping[str, Any]], operation_contract["variables"]):
        for rule in cast(Sequence[Mapping[str, Any]], variable["resolution_rules"]):
            rule_values = {
                "variable_symbol": str(variable["symbol"]),
                "semantic_role": str(variable["semantic_role"]),
                "collection_selector": tuple(str(item) for item in rule["collection_selector"]),
                "equals": tuple(
                    PublicSemanticConstraint(
                        selector=tuple(str(part) for part in constraint["selector"]),
                        value=constraint.get("value"),
                    )
                    for constraint in cast(Sequence[Mapping[str, Any]], rule["equals"])
                ),
                "source_tool_id": str(rule["source_tool_id"]),
            }
            rules.append(
                cast(
                    PublicResolutionRule,
                    _make_identity_model(
                        PublicResolutionRule,
                        rule_values,
                        field="rule_handle",
                        prefix="public_resolution_rule:",
                    ),
                )
            )
    rules.sort(key=lambda item: item.rule_handle)

    operations: list[PublicOperationSemantic] = []
    operation_handle_by_source_id: dict[str, str] = {}
    for node in cast(Sequence[Mapping[str, Any]], operation_contract["nodes"]):
        dependencies = tuple(
            operation_handle_by_source_id[str(item)]
            for item in cast(Sequence[Any], node["dependency_node_ids"])
        )
        output_values = {
            "semantic_role": str(node["semantic_role"]),
            "node_kind": str(node["node_kind"]),
            "tool_id": str(node["tool_id"]),
            "output_symbol": str(node["output_symbol"]),
        }
        operation_values: dict[str, Any] = {
            "semantic_role": str(node["semantic_role"]),
            "node_kind": str(node["node_kind"]),
            "tool_id": str(node["tool_id"]),
            "input_symbols": tuple(
                str(item["source_symbol"])
                for item in cast(Sequence[Mapping[str, Any]], node["inputs"])
            ),
            "dependency_handles": dependencies,
            "allowed_operator_ids": tuple(
                str(item) for item in cast(Sequence[Any], node["allowed_operator_ids"])
            ),
            "normalization_target": node.get("normalization_target"),
            "output_symbol": str(node["output_symbol"]),
            "output_handle": canonical_hash(
                output_values,
                prefix="public_operation_output:",
            ),
            "required_for_completion": bool(node["required_for_completion"]),
            "terminal": bool(node["terminal"]),
        }
        operation = cast(
            PublicOperationSemantic,
            _make_identity_model(
                PublicOperationSemantic,
                operation_values,
                field="operation_handle",
                prefix="public_operation:",
            ),
        )
        operations.append(operation)
        operation_handle_by_source_id[str(node["node_id"])] = operation.operation_handle

    answer_schema = cast(Mapping[str, Any], public["answer_schema"])
    retrieval_scope = cast(Mapping[str, Any], public["retrieval_scope"])
    partial = cast(Mapping[str, Any], retrieval_scope["partial_constraints"])
    corpus = cast(Mapping[str, Any], retrieval_scope["corpus_boundary"])
    stop = cast(Mapping[str, Any], guidance["public_stop_readiness_contract"])
    semantic_stop = {
        "final_answer_requires_stop_ready": bool(stop["final_answer_requires_stop_ready"]),
        "maximum_postcompletion_tool_calls": int(stop["maximum_postcompletion_tool_calls"]),
        "readiness_formula": str(stop["readiness_formula"]),
        "required_operation_handles": tuple(
            operation_handle_by_source_id[str(item)]
            for item in cast(Sequence[Any], stop["required_node_ids"])
        ),
        "verification_after_terminal_required": bool(stop["verification_after_terminal_required"]),
    }
    return PublicSemanticTask(
        instruction=str(public["instruction"]),
        allowed_tools=tuple(sorted(str(item) for item in public["allowed_tools"])),
        answer_type=str(answer_schema["type"]),
        answer_fields=tuple(str(item) for item in answer_schema["required_fields"]),
        aliases=tuple(str(item) for item in retrieval_scope["aliases"]),
        periods=tuple(str(item) for item in partial["period_labels"]),
        source_count=int(corpus["source_count"]),
        records=cast(tuple[PublicSemanticRecord, PublicSemanticRecord], tuple(records)),
        resolution_rules=tuple(rules),
        operations=tuple(operations),
        terminal_operation_handle=operation_handle_by_source_id[
            str(operation_contract["terminal_node_id"])
        ],
        completion_rule=str(operation_contract["completion_rule"]),
        stop_readiness=semantic_stop,
    )


def resolve_public_operator(
    task: PublicSemanticTask,
    operation_handle: str,
) -> str:
    operation = next(item for item in task.operations if item.operation_handle == operation_handle)
    answer_fields = set(task.answer_fields)
    matches = tuple(
        operator_id
        for operator_id in operation.allowed_operator_ids
        if set(task.operator_output_fields[operator_id]) == answer_fields
    )
    if len(matches) != 1:
        raise ValueError("public operator semantics do not identify exactly one operator")
    return matches[0]


def _get_path(value: Mapping[str, Any], selector: tuple[str, ...]) -> Any:
    current: Any = value
    for part in selector:
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


_MISSING = object()


def record_matches_rule(
    record: PublicSemanticRecord,
    rule: PublicResolutionRule,
) -> bool:
    return all(
        _get_path(record.semantic_fields, item.selector) == item.value for item in rule.equals
    )


def resolve_rule_record(
    task: PublicSemanticTask,
    rule: PublicResolutionRule,
) -> PublicSemanticRecord:
    matches = tuple(item for item in task.records if record_matches_rule(item, rule))
    if len(matches) != 1:
        raise ValueError("public resolution Rule does not identify exactly one public record")
    return matches[0]


def resolve_required_record_handles(task: PublicSemanticTask) -> tuple[str, str]:
    record_by_variable: dict[str, str] = {}
    for rule in task.resolution_rules:
        if rule.source_tool_id != "query_structured_fact":
            continue
        handle = resolve_rule_record(task, rule).record_handle
        previous = record_by_variable.setdefault(rule.variable_symbol, handle)
        if previous != handle:
            raise ValueError("public variable resolves to multiple Finance records")
    operation_by_output = {item.output_symbol: item for item in task.operations}

    def resolve_symbol(symbol: str, seen: frozenset[str] = frozenset()) -> str:
        if symbol in record_by_variable:
            return record_by_variable[symbol]
        if symbol in seen or symbol not in operation_by_output:
            raise ValueError("public Operation input cannot be resolved to a Finance record")
        operation = operation_by_output[symbol]
        if len(operation.input_symbols) != 1:
            raise ValueError("public intermediate Operation does not have one record lineage")
        return resolve_symbol(operation.input_symbols[0], seen | {symbol})

    terminal = next(
        item for item in task.operations if item.operation_handle == task.terminal_operation_handle
    )
    handles = tuple(resolve_symbol(symbol) for symbol in terminal.input_symbols)
    if len(handles) != 2 or len(set(handles)) != 2:
        raise ValueError("public Task does not derive two distinct required Finance records")
    return cast(tuple[str, str], handles)


def candidate_grounding_findings(
    task: PublicSemanticTask,
    state: PublicDecisionState,
    operation: PublicOperationPayload,
) -> tuple[str, ...]:
    surface: set[bytes] = set()

    def collect(value: Any) -> None:
        if isinstance(value, Mapping):
            for item in value.values():
                collect(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item)
        elif value is not None:
            surface.add(canonical_bytes(value))

    collect(task.model_dump(mode="json"))
    collect(state.model_dump(mode="json"))
    surface.update(canonical_bytes(item) for item in task.operator_catalog)
    findings: list[str] = []
    if operation.tool_id not in task.allowed_tools:
        findings.append("tool_not_publicly_allowed")
    if operation.decision_kind != state.decision_kind:
        findings.append("decision_kind_mismatch")

    def check(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                check(item, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                check(item, f"{path}[{index}]")
        elif value is not None and canonical_bytes(value) not in surface:
            findings.append(f"{path}:not_publicly_derivable")

    check(operation.arguments, "$.arguments")
    return tuple(sorted(set(findings)))


def public_only_select_action(prompt: PublicSemanticPrompt) -> str:
    task = prompt.task
    state = prompt.state
    facts = state.facts
    operations = {item.operation_handle: item for item in task.operations}
    rules = {item.rule_handle: item for item in task.resolution_rules}
    outputs = {item.output_symbol: item.output_handle for item in task.operations}
    decision = state.decision_kind
    desired: dict[str, Any]
    if decision == "select_operator":
        operation = operations[str(facts["operation_handle"])]
        desired = {
            "operation_handle": operation.operation_handle,
            "operator_id": resolve_public_operator(task, operation.operation_handle),
        }
    elif decision in {"select_records", "select_scope"}:
        desired = {"record_handles": list(resolve_required_record_handles(task))}
    elif decision == "select_projection":
        desired = {"answer_fields": list(task.answer_fields)}
    elif decision == "reconcile_record":
        rule = rules[str(facts["rule_handle"])]
        operation = operations[str(facts["operation_handle"])]
        desired = {
            "operation_handle": operation.operation_handle,
            "output_handle": operation.output_handle,
            "record_handle": resolve_rule_record(task, rule).record_handle,
            "rule_handle": rule.rule_handle,
        }
    elif decision == "consume_outputs":
        operation = operations[str(facts["operation_handle"])]
        desired = {
            "operation_handle": operation.operation_handle,
            "output_handles": [outputs[item] for item in operation.input_symbols],
        }
    elif decision == "revise_selector":
        rule = rules[str(facts["rule_handle"])]
        desired = {
            "rule_handle": rule.rule_handle,
            "selector": [item.model_dump(mode="json") for item in rule.equals],
            "source_tool_id": rule.source_tool_id,
        }
    elif decision == "assess_readiness":
        assertion = str(facts["assertion"])
        receipt = cast(Mapping[str, Any], facts["execution_receipt"])
        value = receipt[assertion]
        desired = {
            "assertion": assertion,
            "verdict": "true" if value is True else "false" if value is False else "unknown",
        }
    elif decision == "stop_or_continue":
        receipt = cast(Mapping[str, Any], facts["execution_receipt"])
        desired = {
            "command": "stop"
            if all(value is True for value in receipt.values())
            else "repeat_program"
        }
    else:
        raise ValueError(f"unknown public Decision kind:{decision}")
    matches = tuple(
        item.action_id for item in prompt.candidates if item.operation.arguments == desired
    )
    if len(matches) != 1:
        raise ValueError("public-only Selector did not identify exactly one semantic choice")
    return matches[0]


def build_selected_program(
    original_program: TaskProgram,
    *,
    operator_id: str,
    evidence_ids: tuple[str, str],
    registry: OperationRegistry,
) -> TaskProgram:
    if len(original_program.nodes) != 1:
        raise ValueError("public semantic Runtime requires a one-node source Program")
    original_node = original_program.nodes[0]
    definition = registry.require(operator_id)
    node = OperationNode(
        node_id=original_node.node_id,
        operator_id=operator_id,
        input_refs=tuple(
            ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id=item) for item in evidence_ids
        ),
        parameters=original_node.parameters if operator_id == original_node.operator_id else {},
        output_schema=definition.output_schema,
        verifier_id=definition.verifier_id,
        dependencies=(),
    )
    return make_program((node,), node.node_id)


def execute_semantic_runtime(
    binding: SemanticRuntimeBinding,
    selected_by_component: Mapping[str, str] | None = None,
) -> SemanticExecutionResult:
    selected_by_component = selected_by_component or {}
    task = binding.task
    selected_operator = resolve_public_operator(task, task.terminal_operation_handle)
    required_records = resolve_required_record_handles(task)
    selected_records = list(required_records)
    selected_projection = tuple(task.answer_fields)
    checks: dict[str, bool] = {}
    chosen: list[str] = []
    deterministic_failures = 0
    postcompletion_calls = 0
    rules = {item.rule_handle: item for item in task.resolution_rules}
    for component in binding.components:
        semantic_key = selected_by_component.get(
            component.component_key,
            component.reference_semantic_key,
        )
        choice_by_key = {item.semantic_key: item for item in component.choices}
        if semantic_key not in choice_by_key:
            raise ValueError("public semantic Runtime selected a non-visible Choice")
        choice = choice_by_key[semantic_key]
        chosen.append(semantic_key)
        checks[component.component_key] = semantic_key == component.reference_semantic_key
        arguments = choice.operation.arguments
        decision = component.public_state.decision_kind
        if decision == "select_operator":
            selected_operator = str(arguments["operator_id"])
        elif decision in {"select_records", "select_scope"}:
            selected_records = [str(item) for item in arguments["record_handles"]]
        elif decision == "select_projection":
            selected_projection = tuple(str(item) for item in arguments["answer_fields"])
        elif decision == "reconcile_record":
            rule = rules[str(component.public_state.facts["rule_handle"])]
            expected = resolve_rule_record(task, rule).record_handle
            position = required_records.index(expected)
            selected_records[position] = str(arguments["record_handle"])
        elif decision == "revise_selector":
            deterministic_failures += 1
            selector = tuple(
                PublicSemanticConstraint.model_validate(item)
                for item in cast(Sequence[Mapping[str, Any]], arguments["selector"])
            )
            matches = tuple(
                record
                for record in task.records
                if all(
                    _get_path(record.semantic_fields, item.selector) == item.value
                    for item in selector
                )
            )
            target_rule = rules[str(component.public_state.facts["rule_handle"])]
            expected = resolve_rule_record(task, target_rule).record_handle
            position = required_records.index(expected)
            if len(matches) == 1:
                selected_records[position] = matches[0].record_handle
            else:
                checks[component.component_key] = False
        elif decision == "stop_or_continue":
            if str(arguments["command"]) != "stop":
                postcompletion_calls += 1

    evidence_by_handle = dict(binding.evidence_by_handle)
    evidence_by_id = {item.evidence_id: item for item in evidence_by_handle.values()}
    selected_program: TaskProgram | None = None
    execution: ProgramExecution | None = None
    verification: ProgramVerification | None = None
    executor_calls = 0
    verifier_calls = 0
    error_code: str | None = None
    try:
        selected_program = build_selected_program(
            binding.original_program,
            operator_id=selected_operator,
            evidence_ids=cast(
                tuple[str, str],
                tuple(evidence_by_handle[item].evidence_id for item in selected_records),
            ),
            registry=binding.registry,
        )
        execution = TaskProgramExecutor(binding.registry).execute(
            selected_program,
            evidence_by_id,
        )
        executor_calls = 1
        verification = TaskProgramOracleVerifier(binding.registry).verify(
            binding.original_program,
            evidence_by_id,
            execution.node_outputs,
        )
        verifier_calls = 1
        if postcompletion_calls:
            TaskProgramExecutor(binding.registry).execute(selected_program, evidence_by_id)
            executor_calls += 1
    except ProgramExecutionError as exc:
        error_code = exc.error_code
    checks["answer_projection"] = selected_projection == tuple(task.answer_fields)
    checks["postcompletion_control"] = postcompletion_calls == 0
    program_valid = bool(verification is not None and verification.passed)
    base_valid = program_valid and all(checks.values())
    mechanism_qualified = all(
        selected_by_component.get(item.component_key, item.reference_semantic_key)
        == item.reference_semantic_key
        for item in binding.components
    )
    values = {
        "selected_program": selected_program,
        "program_execution": execution,
        "oracle_verification": verification,
        "executor_invocation_count": executor_calls,
        "oracle_verifier_invocation_count": verifier_calls,
        "deterministic_failure_observation_count": deterministic_failures,
        "postcompletion_call_count": postcompletion_calls,
        "execution_error_code": error_code,
        "public_contract_checks": dict(sorted(checks.items())),
        "program_valid": program_valid,
        "base_valid": base_valid,
        "mechanism_qualified": mechanism_qualified,
        "qualified_valid": base_valid and mechanism_qualified,
        "chosen_semantic_keys": tuple(chosen),
    }
    return cast(
        SemanticExecutionResult,
        _make_identity_model(
            SemanticExecutionResult,
            values,
            field="result_id",
            prefix="public_semantic_execution_result:",
        ),
    )


def default_semantic_runtime_binding(
    *,
    task: PublicSemanticTask,
    components: tuple[TargetComponent, ...],
    original_program: TaskProgram,
    evidence_by_handle: Mapping[str, EvidenceItem],
) -> SemanticRuntimeBinding:
    return SemanticRuntimeBinding(
        task=task,
        components=components,
        original_program=original_program,
        evidence_by_handle=evidence_by_handle,
        registry=default_registry(),
    )
