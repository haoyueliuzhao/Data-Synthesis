from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceArchiveInteractiveToolRuntime,
    recovery_scenario_from_metadata,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_SENSITIVE_FAMILIES,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.llm_agent import _state_execution_shape_contract
from trusted_synthesis.runtime.tools import AgentToolCall, AgentToolEnvironmentManifest

PUBLIC_CONTRACT_SATISFIABILITY_VERSION = "public_contract_satisfiability.v1"
SCRIPTED_SEQUENCE_COMPILATION_VERSION = "finance_scripted_sequence_compilation.v1"
PUBLIC_CONTRACT_AUDIT_VERSION = "finance_public_contract_satisfiability_audit.v3"

RuntimeArmName = Literal[
    "direct_fixed_retrieval",
    "scripted_tool",
    "autonomous_agent",
]

ToolState = Literal[
    "public_task_constraints",
    "discovered_evidence",
    "exposed_locator",
    "selected_evidence",
    "normalized_evidence",
    "computed_result",
    "verified_result",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolTransitionSpec(FrozenModel):
    tool_id: str = Field(min_length=1)
    preconditions: tuple[ToolState, ...]
    effects: tuple[ToolState, ...] = Field(min_length=1)


class ToolStateTraceStep(FrozenModel):
    step_index: int = Field(ge=1)
    tool_id: str = Field(min_length=1)
    preconditions: tuple[ToolState, ...]
    effects: tuple[ToolState, ...]
    state_before: tuple[ToolState, ...]
    state_after: tuple[ToolState, ...]
    passed: Literal[True] = True


FINANCE_TOOL_TRANSITIONS: dict[str, ToolTransitionSpec] = {
    "search_archive": ToolTransitionSpec(
        tool_id="search_archive",
        preconditions=("public_task_constraints",),
        effects=("discovered_evidence", "exposed_locator"),
    ),
    "open_document": ToolTransitionSpec(
        tool_id="open_document",
        preconditions=("exposed_locator",),
        effects=("selected_evidence",),
    ),
    "query_structured_fact": ToolTransitionSpec(
        tool_id="query_structured_fact",
        preconditions=("public_task_constraints",),
        effects=("discovered_evidence", "selected_evidence"),
    ),
    "normalize_metric_unit_period": ToolTransitionSpec(
        tool_id="normalize_metric_unit_period",
        preconditions=("selected_evidence",),
        effects=("normalized_evidence",),
    ),
    "calculator": ToolTransitionSpec(
        tool_id="calculator",
        preconditions=("selected_evidence",),
        effects=("computed_result",),
    ),
    "cross_check_evidence": ToolTransitionSpec(
        tool_id="cross_check_evidence",
        preconditions=("selected_evidence", "computed_result"),
        effects=("verified_result",),
    ),
}


class ScriptedSequenceCompilation(FrozenModel):
    task_artifact_id: str = Field(min_length=1)
    tool_sequence: tuple[str, ...] = Field(min_length=1)
    minimum_tool_calls: int = Field(ge=1)
    minimum_model_stop_decisions: int = Field(ge=0, le=1)
    minimum_evidence_selection_calls: int = Field(ge=0)
    compiler_inserted_selection_calls: int = Field(ge=0)
    state_trace: tuple[ToolStateTraceStep, ...] = Field(min_length=1)
    terminal_state: tuple[ToolState, ...] = Field(min_length=1)
    compilation_hash: str = Field(min_length=1)
    schema_version: str = SCRIPTED_SEQUENCE_COMPILATION_VERSION

    @model_validator(mode="after")
    def validate_compilation(self) -> ScriptedSequenceCompilation:
        if self.schema_version != SCRIPTED_SEQUENCE_COMPILATION_VERSION:
            raise ValueError("Scripted sequence compilation version is unsupported")
        if self.minimum_tool_calls != len(self.tool_sequence):
            raise ValueError("Scripted minimum tool-call count differs from its sequence")
        if len(self.state_trace) != len(self.tool_sequence):
            raise ValueError("Scripted state trace does not cover every tool call")
        if tuple(item.tool_id for item in self.state_trace) != self.tool_sequence:
            raise ValueError("Scripted state trace and tool sequence differ")
        if "verified_result" not in self.terminal_state:
            raise ValueError("Scripted sequence lacks a verified terminal result")
        if self.compilation_hash != scripted_sequence_compilation_hash(self):
            raise ValueError("Scripted sequence compilation identity is invalid")
        return self


class PublicContractCheck(FrozenModel):
    check_id: Literal[
        "compiler_prompt_verifier_consistency",
        "tool_precondition_closure",
        "public_valid_witness",
        "minimum_call_accounting",
    ]
    passed: bool
    details: dict[str, Any]


class PublicContractSatisfiabilityRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    runtime_arm: RuntimeArmName
    checks: tuple[PublicContractCheck, ...] = Field(min_length=4, max_length=4)
    passed: bool
    schema_version: str = PUBLIC_CONTRACT_SATISFIABILITY_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> PublicContractSatisfiabilityRecord:
        expected_checks = {
            "compiler_prompt_verifier_consistency",
            "tool_precondition_closure",
            "public_valid_witness",
            "minimum_call_accounting",
        }
        if {item.check_id for item in self.checks} != expected_checks:
            raise ValueError("public contract audit record lacks a required check")
        if self.passed != all(item.passed for item in self.checks):
            raise ValueError("public contract audit decision is inconsistent")
        if self.record_id != public_contract_record_id(self):
            raise ValueError("public contract audit record identity is invalid")
        return self


class PublicContractSatisfiabilityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    required_runtime_arms: tuple[RuntimeArmName, ...] = Field(min_length=1)
    records: tuple[PublicContractSatisfiabilityRecord, ...] = Field(min_length=7)
    passed_record_count: int = Field(ge=0)
    all_public_contracts_satisfiable: bool
    next_permitted_stage: Literal[
        "fresh_runtime_regression",
        "task_or_runtime_contract_repair_only",
    ]
    schema_version: str = PUBLIC_CONTRACT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PublicContractSatisfiabilityAudit:
        if self.schema_version != PUBLIC_CONTRACT_AUDIT_VERSION:
            raise ValueError("public contract audit version is unsupported")
        if len(set(self.required_runtime_arms)) != len(self.required_runtime_arms):
            raise ValueError("public contract audit Runtime arms are not unique")
        runtime_count = len(self.required_runtime_arms)
        family_count = len(CAPABILITY_SENSITIVE_FAMILIES)
        if len(self.records) % (family_count * runtime_count) != 0:
            raise ValueError(
                "public contract audit must contain balanced families across declared Runtimes"
            )
        task_ids = {item.task_artifact_id for item in self.records}
        if len(task_ids) * runtime_count != len(self.records):
            raise ValueError("public contract audit contains duplicate or incomplete task cells")
        for task_id in task_ids:
            if {
                item.runtime_arm for item in self.records if item.task_artifact_id == task_id
            } != set(self.required_runtime_arms):
                raise ValueError("public contract audit task lacks a declared Runtime")
        if {item.family for item in self.records} != set(CAPABILITY_SENSITIVE_FAMILIES):
            raise ValueError("public contract audit does not cover every capability family")
        family_task_counts = {
            family: len(
                {
                    item.task_artifact_id
                    for item in self.records
                    if item.family == family
                }
            )
            for family in CAPABILITY_SENSITIVE_FAMILIES
        }
        if len(set(family_task_counts.values())) != 1:
            raise ValueError("public contract audit is not balanced by capability family")
        expected_count = sum(item.passed for item in self.records)
        if self.passed_record_count != expected_count:
            raise ValueError("public contract audit pass count is inconsistent")
        expected_ready = expected_count == len(self.records)
        if self.all_public_contracts_satisfiable != expected_ready:
            raise ValueError("public contract audit readiness is inconsistent")
        expected_stage = (
            "fresh_runtime_regression"
            if expected_ready
            else "task_or_runtime_contract_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("public contract audit stage is inconsistent")
        if self.audit_id != public_contract_audit_id(self):
            raise ValueError("public contract audit identity is invalid")
        return self


def compile_scripted_tool_sequence(
    task: CapabilitySensitiveTaskArtifact,
    *,
    maximum_required_tool_calls: int,
) -> ScriptedSequenceCompilation:
    query_tools = {
        "broad_search": "search_archive",
        "typed_refinement": "query_structured_fact",
        "document_inspection": "open_document",
        "cross_source_join": "query_structured_fact",
    }
    sequence = [query_tools[item.action] for item in task.query_stages]
    sequence.extend("query_structured_fact" for _ in task.recovery_branches)
    selection_actions = sum(
        item.action in {"typed_refinement", "document_inspection", "cross_source_join"}
        for item in task.query_stages
    ) + len(task.recovery_branches)
    inserted_selection_calls = max(
        0,
        task.structure.minimum_evidence_selection_calls - selection_actions,
    )
    sequence.extend(
        "query_structured_fact"
        for _ in range(inserted_selection_calls)
    )
    sequence.extend("normalize_metric_unit_period" for _ in task.reconciliation_axes)
    sequence.extend("calculator" for _ in task.task.oracle.task_program.nodes)
    sequence.extend("cross_check_evidence" for _ in task.verification_checkpoints)
    stop_decisions = int(task.tier == DifficultyTier.HARD_CONTROL)
    if len(sequence) != task.structure.minimal_tool_calls:
        raise ValueError("Scripted sequence differs from the frozen tool-call contract")
    if stop_decisions != task.structure.minimal_model_stop_decisions:
        raise ValueError("Scripted stop decision differs from the frozen model-decision contract")
    if len(sequence) > maximum_required_tool_calls:
        raise ValueError("Scripted sequence exceeds the required-call budget")
    trace, terminal_state = replay_tool_preconditions(tuple(sequence))
    values = {
        "task_artifact_id": task.artifact_id,
        "tool_sequence": tuple(sequence),
        "minimum_tool_calls": len(sequence),
        "minimum_model_stop_decisions": stop_decisions,
        "minimum_evidence_selection_calls": task.structure.minimum_evidence_selection_calls,
        "compiler_inserted_selection_calls": inserted_selection_calls,
        "state_trace": trace,
        "terminal_state": terminal_state,
    }
    provisional = ScriptedSequenceCompilation.model_construct(
        compilation_hash="pending",
        **values,
    )
    return ScriptedSequenceCompilation(
        compilation_hash=scripted_sequence_compilation_hash(provisional),
        **values,
    )


def replay_tool_preconditions(
    sequence: tuple[str, ...],
) -> tuple[tuple[ToolStateTraceStep, ...], tuple[ToolState, ...]]:
    state: set[ToolState] = {"public_task_constraints"}
    trace = []
    for index, tool_id in enumerate(sequence, start=1):
        transition = FINANCE_TOOL_TRANSITIONS.get(tool_id)
        if transition is None:
            raise ValueError(f"Scripted sequence uses an unregistered tool transition:{tool_id}")
        missing = set(transition.preconditions) - state
        if missing:
            raise ValueError(
                f"Scripted tool preconditions are not closed:{tool_id}:{sorted(missing)}"
            )
        before = tuple(sorted(state))
        state.update(transition.effects)
        trace.append(
            ToolStateTraceStep(
                step_index=index,
                tool_id=tool_id,
                preconditions=transition.preconditions,
                effects=transition.effects,
                state_before=before,
                state_after=tuple(sorted(state)),
            )
        )
    return tuple(trace), tuple(sorted(state))


def make_public_contract_record(
    *,
    task: CapabilitySensitiveTaskArtifact,
    runtime_arm: RuntimeArmName,
    runtime_task: Any,
    manifest: AgentToolEnvironmentManifest,
    maximum_required_tool_calls: int,
) -> PublicContractSatisfiabilityRecord:
    compilation = compile_scripted_tool_sequence(
        task,
        maximum_required_tool_calls=maximum_required_tool_calls,
    )
    selector_check = _selector_consistency_check(
        task,
        runtime_arm,
        runtime_task.public,
    )
    closure_check = PublicContractCheck(
        check_id="tool_precondition_closure",
        passed=all(item.passed for item in compilation.state_trace),
        details={
            "compilation_hash": compilation.compilation_hash,
            "state_trace_length": len(compilation.state_trace),
            "terminal_state": compilation.terminal_state,
            "audit_role": (
                "frozen_script"
                if runtime_arm == "scripted_tool"
                else "existential_public_tool_witness"
            ),
        },
    )
    witness_check = _public_witness_check(task, manifest)
    call_check = PublicContractCheck(
        check_id="minimum_call_accounting",
        passed=(
            compilation.minimum_tool_calls == task.structure.minimal_tool_calls
            and compilation.minimum_model_stop_decisions
            == task.structure.minimal_model_stop_decisions
            and compilation.minimum_tool_calls <= maximum_required_tool_calls
        ),
        details={
            "minimum_tool_calls": compilation.minimum_tool_calls,
            "minimum_model_stop_decisions": compilation.minimum_model_stop_decisions,
            "minimum_evidence_selection_calls": (
                compilation.minimum_evidence_selection_calls
            ),
            "compiler_inserted_selection_calls": (
                compilation.compiler_inserted_selection_calls
            ),
            "maximum_required_tool_calls": maximum_required_tool_calls,
        },
    )
    checks = (selector_check, closure_check, witness_check, call_check)
    values = {
        "task_artifact_id": task.artifact_id,
        "task_id": task.task.task_id,
        "family": task.family,
        "runtime_arm": runtime_arm,
        "checks": checks,
        "passed": all(item.passed for item in checks),
    }
    provisional = PublicContractSatisfiabilityRecord.model_construct(
        record_id="pending",
        **values,
    )
    return PublicContractSatisfiabilityRecord(
        record_id=public_contract_record_id(provisional),
        **values,
    )


def make_public_contract_audit(
    *,
    population_id: str,
    records: tuple[PublicContractSatisfiabilityRecord, ...],
    required_runtime_arms: tuple[RuntimeArmName, ...],
) -> PublicContractSatisfiabilityAudit:
    passed_count = sum(item.passed for item in records)
    ready = passed_count == len(records)
    values = {
        "population_id": population_id,
        "required_runtime_arms": required_runtime_arms,
        "records": records,
        "passed_record_count": passed_count,
        "all_public_contracts_satisfiable": ready,
        "next_permitted_stage": (
            "fresh_runtime_regression"
            if ready
            else "task_or_runtime_contract_repair_only"
        ),
    }
    provisional = PublicContractSatisfiabilityAudit.model_construct(
        audit_id="pending",
        **values,
    )
    return PublicContractSatisfiabilityAudit(
        audit_id=public_contract_audit_id(provisional),
        **values,
    )


def _selector_consistency_check(
    task: CapabilitySensitiveTaskArtifact,
    runtime_arm: RuntimeArmName,
    public_task: Any,
) -> PublicContractCheck:
    guidance = public_task.metadata.get("agent_contract_guidance")
    expected_selectors = tuple(
        sorted(
            {
                item.selector
                for node in task.task.oracle.task_program.nodes
                for item in node.input_refs
                if item.kind.value == "operation" and item.selector is not None
            }
        )
    )
    expected_ratio_pairs = tuple(
        sorted(
            {
                str(node.parameters["registered_pair"])
                for node in task.task.oracle.task_program.nodes
                if node.operator_id == "ratio"
                and isinstance(node.parameters.get("registered_pair"), str)
            }
        )
    )
    operation_contract = (
        guidance.get("calculator_operation_reference_contract")
        if isinstance(guidance, dict)
        else None
    )
    guidance_passed = bool(
        isinstance(operation_contract, dict)
        and tuple(operation_contract.get("allowed_selectors", ()))
        == expected_selectors
        and operation_contract.get("scalar_selector") == "value"
        and operation_contract.get("selector_base")
        == "prior calculator observation result.result.output"
        and operation_contract.get("literal_operation_names_are_forbidden") is True
        and tuple(guidance.get("registered_ratio_pairs", ()))
        == expected_ratio_pairs
    )
    guidance_details = {
        "operation_guidance_present": isinstance(operation_contract, dict),
        "operation_guidance_matches_program": guidance_passed,
        "expected_operation_selectors": expected_selectors,
        "expected_registered_ratio_pairs": expected_ratio_pairs,
    }
    if runtime_arm != "direct_fixed_retrieval":
        return PublicContractCheck(
            check_id="compiler_prompt_verifier_consistency",
            passed=guidance_passed,
            details={
                "selector_contract": "plan_hidden_operation_guidance",
                **guidance_details,
            },
        )
    shape = _state_execution_shape_contract(public_task, {})
    expected = tuple(
        {
            "public_node_id": node.public_node_id,
            "operator_id": node.operator_id,
            "inputs": tuple(
                {
                    "kind": item.kind.value,
                    "role_id": item.role_id,
                    "selector": item.selector,
                }
                for item in node.inputs
            ),
        }
        for node in public_task.program_skeleton.nodes
    )
    observed = tuple(shape.get("public_program_input_contract", ()))
    passed = (
        shape.get("mode") == "public_program"
        and observed == expected
        and guidance_passed
    )
    return PublicContractCheck(
        check_id="compiler_prompt_verifier_consistency",
        passed=passed,
        details={
            "shape_mode": shape.get("mode"),
            "public_node_count": len(expected),
            "null_selector_count": sum(
                item["selector"] is None
                for node in expected
                for item in node["inputs"]
            ),
            "prompt_contract_equals_public_skeleton": observed == expected,
            **guidance_details,
        },
    )


def _public_witness_check(
    task: CapabilitySensitiveTaskArtifact,
    manifest: AgentToolEnvironmentManifest,
) -> PublicContractCheck:
    details: dict[str, Any]
    try:
        selected = _publicly_identifiable_evidence(task)
        dead_nodes = _dead_program_nodes(task)
        unsupported = _unsupported_public_operations(task)
        if dead_nodes:
            raise ValueError(f"program contains public-unrecoverable dead nodes:{dead_nodes}")
        if unsupported:
            raise ValueError(f"program contains publicly unsupported operations:{unsupported}")
        recovery_scenario = recovery_scenario_from_metadata(
            task.task.public.metadata
        )
        runtime = FinanceArchiveInteractiveToolRuntime(
            task.public_corpus,
            manifest,
            recovery_scenario=recovery_scenario,
        )
        by_tool = {item.tool_id: item for item in manifest.tools}
        call_index = 0
        selected_ids: list[str] = []
        for item in selected:
            call_index += 1
            payload: dict[str, Any] = getattr(
                item.payload,
                "model_dump",
                lambda **_: {},
            )(
                mode="json",
                exclude_none=True,
            )
            filters = {
                "source_id": item.source.source_id,
                "source_authority": item.source.authority.value,
                "unit": payload.get("unit"),
                "currency": payload.get("currency"),
                "definition_id": item.definition.definition_id,
                "time_basis": item.temporal_context.basis,
                "frequency": item.temporal_context.frequency,
                "subject_type": item.subject.subject_type,
            }
            arguments = {
                "subject_alias": item.subject.subject_id,
                "metric_alias": item.predicate,
                "period_label": item.temporal_context.label,
                "public_filters": filters,
            }
            if recovery_scenario is not None and call_index == 1:
                probe_arguments = _recovery_probe_arguments(item, arguments)
                by_tool["query_structured_fact"].validate_arguments(probe_arguments)
                probe_result = runtime.execute(
                    AgentToolCall(
                        call_index=call_index,
                        tool_id="query_structured_fact",
                        arguments=probe_arguments,
                    )
                )
                if (
                    probe_result.status != "failed"
                    or probe_result.error_code != recovery_scenario.error_code
                ):
                    raise ValueError("typed recovery probe did not reach its frozen failure")
                call_index += 1
            by_tool["query_structured_fact"].validate_arguments(arguments)
            result = runtime.execute(
                AgentToolCall(
                    call_index=call_index,
                    tool_id="query_structured_fact",
                    arguments=arguments,
                )
            )
            if result.status != "succeeded":
                raise ValueError(result.error_message or "public structured query failed")
            selected_ids.extend(result.evidence_ids)
        selected_ids = list(dict.fromkeys(selected_ids))
        if set(selected_ids) != {item.evidence_id for item in selected}:
            raise ValueError("public selectors did not uniquely recover the witness Evidence")
        if task.reconciliation_axes:
            first = selected[0]
            scalar = first.payload.model_dump(mode="json", exclude_none=True)
            target = {
                "predicate": first.predicate,
                "definition_id": first.definition.definition_id,
                "unit": scalar.get("unit"),
                "currency": scalar.get("currency"),
                "time_basis": first.temporal_context.basis,
                "frequency": first.temporal_context.frequency,
            }
            for _ in task.reconciliation_axes:
                call_index += 1
                arguments = {"evidence_ids": selected_ids, "target_definition": target}
                result = runtime.execute(
                    AgentToolCall(
                        call_index=call_index,
                        tool_id="normalize_metric_unit_period",
                        arguments=arguments,
                    )
                )
                if result.status != "succeeded":
                    raise ValueError(result.error_message or "public normalization failed")
        operation_refs: dict[str, str] = {}
        final_result: Mapping[str, Any] | None = None
        for node in task.task.oracle.task_program.nodes:
            operands = []
            for item in node.input_refs:
                if item.kind.value == "evidence":
                    operands.append({"evidence_id": item.ref_id})
                else:
                    operand: dict[str, Any] = {
                        "operation_ref": operation_refs[item.ref_id],
                    }
                    if item.selector is not None:
                        operand["selector"] = item.selector
                    operands.append(operand)
            call_index += 1
            result = runtime.execute(
                AgentToolCall(
                    call_index=call_index,
                    tool_id="calculator",
                    arguments={
                        "operator": node.operator_id,
                        "operands": operands,
                        "parameters": node.parameters,
                    },
                )
            )
            if result.status != "succeeded":
                raise ValueError(result.error_message or "public calculator witness failed")
            operation = result.result["result"]
            operation_refs[node.node_id] = str(operation["operation_ref"])
            final_result = operation["output"]
        reverse_operation_refs = {
            runtime_ref: node_id for node_id, runtime_ref in operation_refs.items()
        }
        canonical_final_result = _replace_runtime_operation_refs(
            final_result,
            reverse_operation_refs,
        )
        if canonical_final_result != task.execution.final_output:
            raise ValueError("public witness output differs from the frozen program execution")
        output_ref = operation_refs[task.task.oracle.task_program.output_node_id]
        for _ in task.verification_checkpoints:
            call_index += 1
            result = runtime.execute(
                AgentToolCall(
                    call_index=call_index,
                    tool_id="cross_check_evidence",
                    arguments={
                        "evidence_ids": selected_ids,
                        "claim_or_result": {"operation_ref": output_ref},
                    },
                )
            )
            if result.status != "succeeded" or not result.result.get("verified"):
                raise ValueError(result.error_message or "public verification witness failed")
        details = {
            "public_selector_count": len(selected),
            "hidden_gold_selector_count": 0,
            "program_node_count": len(task.task.oracle.task_program.nodes),
            "dead_program_node_count": 0,
            "unsupported_operation_count": 0,
            "tool_execution_count": call_index,
            "output_replay_match": True,
            "opaque_operation_refs_canonicalized": len(reverse_operation_refs),
            "typed_recovery_observed": recovery_scenario is not None,
        }
        passed = True
    except (KeyError, TypeError, ValueError) as exc:
        details = {"error": str(exc)}
        passed = False
    return PublicContractCheck(
        check_id="public_valid_witness",
        passed=passed,
        details=details,
    )


def _recovery_probe_arguments(
    item: Any,
    corrected_arguments: dict[str, Any],
) -> dict[str, Any]:
    probe = {
        **corrected_arguments,
        "public_filters": dict(corrected_arguments["public_filters"]),
    }
    if item.subject.name and item.subject.name != item.subject.subject_id:
        probe["subject_alias"] = item.subject.name
        return probe
    metric_name = str(item.definition.attributes.get("metric_name") or "")
    if metric_name and metric_name != item.predicate:
        probe["metric_alias"] = metric_name
        return probe
    definition_id = item.definition.definition_id
    if definition_id and definition_id != item.predicate:
        probe["metric_alias"] = definition_id
        return probe
    filters = probe["public_filters"]
    if filters:
        filters.pop(next(iter(sorted(filters))))
        return probe
    raise ValueError("typed recovery witness lacks two equivalent public selectors")


def _replace_runtime_operation_refs(
    value: Any,
    reverse_operation_refs: Mapping[str, str],
) -> Any:
    if isinstance(value, str):
        return reverse_operation_refs.get(value, value)
    if isinstance(value, Mapping):
        return {
            key: _replace_runtime_operation_refs(item, reverse_operation_refs)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _replace_runtime_operation_refs(item, reverse_operation_refs)
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _replace_runtime_operation_refs(item, reverse_operation_refs)
            for item in value
        )
    return value


def _publicly_identifiable_evidence(
    task: CapabilitySensitiveTaskArtifact,
) -> tuple[Any, ...]:
    instruction = _normalize_text(task.task.public.instruction)
    aliases = {
        _normalize_text(str(item))
        for item in task.task.public.retrieval_scope.get("aliases", ())
    }
    selected = tuple(
        item
        for item in task.public_corpus.evidence
        if (
            _normalize_text(item.subject.subject_id) in aliases
            or _normalize_text(item.subject.name) in aliases
        )
        and (
            _normalize_text(item.predicate) in aliases
            or _normalize_text(str(item.definition.attributes.get("metric_name") or "")) in aliases
        )
        and _normalize_text(str(item.temporal_context.label or "")) in instruction
    )
    if not selected:
        raise ValueError("public task fields identify no Evidence")
    gold_ids = {item.evidence_id for item in task.evidence_bundle.evidence}
    if {item.evidence_id for item in selected} != gold_ids:
        raise ValueError("public task fields do not identify exactly the required Evidence")
    return selected


def _dead_program_nodes(task: CapabilitySensitiveTaskArtifact) -> tuple[str, ...]:
    program = task.task.oracle.task_program
    by_id = {item.node_id: item for item in program.nodes}
    reachable = set()
    pending = [program.output_node_id]
    while pending:
        node_id = pending.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        pending.extend(
            item.ref_id
            for item in by_id[node_id].input_refs
            if item.kind.value == "operation"
        )
    return tuple(sorted(set(by_id) - reachable))


def _unsupported_public_operations(
    task: CapabilitySensitiveTaskArtifact,
) -> tuple[str, ...]:
    instruction = _normalize_text(task.task.public.instruction)
    markers = {
        "lookup": ("find", "reported", "observation"),
        "compare": ("higher", "compare", "exceeded"),
        "difference": ("change", "differ", "deviation"),
        "ratio": ("ratio", "divide"),
        "growth": ("growth", "relative change"),
        "aggregate": ("average", "mean", "sum", "total"),
    }
    unsupported = []
    for node in task.task.oracle.task_program.nodes:
        expected = markers.get(node.operator_id)
        if expected is None or not any(item in instruction for item in expected):
            unsupported.append(node.node_id)
        method = node.parameters.get("method")
        if method == "mean" and not any(item in instruction for item in ("mean", "average")):
            unsupported.append(node.node_id)
        if method == "sum" and not any(item in instruction for item in ("sum", "total")):
            unsupported.append(node.node_id)
    return tuple(sorted(set(unsupported)))


def _normalize_text(value: str) -> str:
    return " ".join(
        "".join(character.lower() if character.isalnum() else " " for character in value).split()
    )


def scripted_sequence_compilation_hash(value: ScriptedSequenceCompilation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"compilation_hash"}),
        prefix="finance_scripted_sequence_compilation:",
    )


def public_contract_record_id(value: PublicContractSatisfiabilityRecord) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="finance_public_contract_satisfiability_record:",
    )


def public_contract_audit_id(value: PublicContractSatisfiabilityAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_public_contract_satisfiability_audit:",
    )
