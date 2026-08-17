from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.operations.program import ProgramExecutionError, TaskProgramExecutor
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.synthesis.schema import CompiledProofCarryingArtifacts
from trusted_synthesis.core.task.answer_schema import allowed_result_fields, required_answer_fields
from trusted_synthesis.core.trajectory.executable_support import (
    EXECUTABLE_SUPPORT_CONTRACT_VERSION,
    PROJECTION_VIEWS,
    AlternativeValidPathCatalog,
    EvidenceSupportLattice,
    EvidenceSupportSet,
    ExecutableSupportTaskCompilation,
    MechanismNecessityArtifact,
    ProjectionViewBinding,
    PublicExecutableWitnessArtifact,
    PublicWitnessStep,
    TypedAnswerProjectionContract,
    alternative_valid_path_catalog_id,
    answer_projection_source_spec_hash,
    evidence_support_lattice_id,
    evidence_support_set_id,
    executable_support_task_compilation_id,
    mechanism_necessity_artifact_id,
    public_executable_witness_id,
    render_public_output_instruction,
    typed_answer_projection_contract_id,
)
from trusted_synthesis.domains.finance.agent_tools import finance_archive_agent_tool_specs
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceArchiveInteractiveToolRuntime,
    finance_runtime_snapshot_hash,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bridge_statistical_audit import (
    BridgeStatisticalAuditReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26FreshTaskPopulation,
    V26FreshTaskRoot,
    load_v26_selected_source_tasks,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolObservation,
    AgentToolResult,
    make_agent_tool_environment_manifest,
    make_agent_tool_observation,
)

V26_EXECUTABLE_SUPPORT_AUDIT_VERSION = "finance_v26_executable_support_audit.v2"
V26_EXECUTABLE_SUPPORT_COMPILER_ID = "finance.v26.executable_support_compiler"
V26_EXECUTABLE_SUPPORT_COMPILER_VERSION = "1.1.0"
V26_TYPED_ANSWER_PROJECTION_VERSION = "typed_answer_projection.v2"
V26_EVIDENCE_LATTICE_VERSION = "evidence_support_lattice.v1"

TargetMechanism = Literal[
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
]

TARGET_MECHANISMS: tuple[TargetMechanism, ...] = (
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
)

CONDITIONAL_METRIC_DEFINITIONS = {
    "valid_trajectory_rate": "P(V=1)",
    "mechanism_necessity": "P(Y_k=1 | V=1)",
    "mechanism_closure": "P(V=1 | Y_k=1)",
    "valid_state_entropy": (
        "H(Z | V=1,x,gamma); undefined when a task-condition has no valid rollout"
    ),
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ImmutableArtifactFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class TaskExecutableSupportAuditRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    source_mechanism_id: str = Field(min_length=1)
    target_mechanism_id: TargetMechanism
    answer_projection_contract_id: str = Field(min_length=1)
    answer_projection_bound: bool
    public_witness_id: str = Field(min_length=1)
    public_witness_passed: bool
    evidence_support_lattice_id: str = Field(min_length=1)
    evidence_lattice_bound: bool
    mechanism_necessity_artifact_id: str = Field(min_length=1)
    mechanism_necessity_passed: bool
    alternative_path_catalog_id: str = Field(min_length=1)
    alternative_paths_passed: bool
    capability_measurement_eligible: bool
    vtdo_multistate_eligible: bool
    blockers: tuple[str, ...]
    schema_version: str = V26_EXECUTABLE_SUPPORT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> TaskExecutableSupportAuditRecord:
        expected_capability = all(
            (
                self.answer_projection_bound,
                self.public_witness_passed,
                self.evidence_lattice_bound,
                self.mechanism_necessity_passed,
            )
        )
        expected_vtdo = expected_capability and self.alternative_paths_passed
        if self.capability_measurement_eligible != expected_capability:
            raise ValueError("task audit capability eligibility is inconsistent")
        if self.vtdo_multistate_eligible != expected_vtdo:
            raise ValueError("task audit VTDO eligibility is inconsistent")
        if bool(self.blockers) == expected_vtdo:
            raise ValueError("task audit blockers are inconsistent")
        if self.record_id != task_executable_support_audit_record_id(self):
            raise ValueError("task executable-support audit identity is invalid")
        return self


class V26ExecutableSupportAuditReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_no_api_root: str = Field(min_length=1)
    source_compiled_artifacts_sha256: str = Field(min_length=64, max_length=64)
    source_development_population_sha256: str = Field(min_length=64, max_length=64)
    source_statistical_audit_id: str = Field(min_length=1)
    source_statistical_audit_sha256: str = Field(min_length=64, max_length=64)
    compiler_id: Literal["finance.v26.executable_support_compiler"] = (
        "finance.v26.executable_support_compiler"
    )
    compiler_version: Literal["1.0.0", "1.1.0"] = "1.1.0"
    task_count: Literal[24] = 24
    typed_answer_projection_compiled_count: Literal[24] = 24
    typed_answer_projection_bound_count: int = Field(ge=0, le=24)
    public_witness_pass_count: int = Field(ge=0, le=24)
    evidence_lattice_compiled_count: Literal[24] = 24
    evidence_lattice_bound_count: int = Field(ge=0, le=24)
    mechanism_necessity_pass_count: int = Field(ge=0, le=24)
    alternative_path_catalog_pass_count: int = Field(ge=0, le=24)
    capability_measurement_eligible_count: int = Field(ge=0, le=24)
    vtdo_multistate_eligible_count: int = Field(ge=0, le=24)
    target_mechanism_task_counts: dict[TargetMechanism, int]
    legacy_combined_recovery_stopping_task_count: Literal[8] = 8
    prospectively_split_recovery_task_count: Literal[4] = 4
    prospectively_split_stopping_task_count: Literal[4] = 4
    context_wrong_action_irreparable_pass_count: int = Field(ge=0, le=8)
    reconciliation_normalized_ref_consumed_pass_count: int = Field(ge=0, le=8)
    conditional_metric_definitions: dict[str, str]
    task_records: tuple[TaskExecutableSupportAuditRecord, ...] = Field(min_length=24, max_length=24)
    immutable_artifact_files: tuple[ImmutableArtifactFile, ...] = Field(min_length=7)
    status: Literal["passed", "blocked"]
    next_permitted_stage: Literal[
        "fresh_executable_support_development",
        "capability_task_or_scaffold_redesign_only",
    ]
    fresh_confirmation_authorized: Literal[False] = False
    state_support_discovery_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = V26_EXECUTABLE_SUPPORT_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> V26ExecutableSupportAuditReport:
        expected_compiler_version = {
            "finance_v26_executable_support_audit.v1": "1.0.0",
            V26_EXECUTABLE_SUPPORT_AUDIT_VERSION: V26_EXECUTABLE_SUPPORT_COMPILER_VERSION,
        }.get(self.schema_version)
        if expected_compiler_version is None or self.compiler_version != expected_compiler_version:
            raise ValueError("v26 executable-support report compiler version is inconsistent")
        expected_counts: dict[TargetMechanism, int] = {
            "context_conditioned_action": 8,
            "semantic_reconciliation": 8,
            "failure_recovery": 4,
            "state_dependent_stopping": 4,
        }
        if self.target_mechanism_task_counts != expected_counts:
            raise ValueError("v26 executable-support mechanism split is inconsistent")
        if self.conditional_metric_definitions != CONDITIONAL_METRIC_DEFINITIONS:
            raise ValueError("v26 executable-support conditional metrics differ from protocol")
        if tuple(item.task_id for item in self.task_records) != tuple(
            sorted(item.task_id for item in self.task_records)
        ):
            raise ValueError("v26 executable-support task records are not canonical")
        counters = {
            "typed_answer_projection_bound_count": sum(
                item.answer_projection_bound for item in self.task_records
            ),
            "public_witness_pass_count": sum(
                item.public_witness_passed for item in self.task_records
            ),
            "evidence_lattice_bound_count": sum(
                item.evidence_lattice_bound for item in self.task_records
            ),
            "mechanism_necessity_pass_count": sum(
                item.mechanism_necessity_passed for item in self.task_records
            ),
            "alternative_path_catalog_pass_count": sum(
                item.alternative_paths_passed for item in self.task_records
            ),
            "capability_measurement_eligible_count": sum(
                item.capability_measurement_eligible for item in self.task_records
            ),
            "vtdo_multistate_eligible_count": sum(
                item.vtdo_multistate_eligible for item in self.task_records
            ),
        }
        if any(getattr(self, key) != value for key, value in counters.items()):
            raise ValueError("v26 executable-support report count is inconsistent")
        expected_passed = self.capability_measurement_eligible_count == self.task_count
        if self.status != ("passed" if expected_passed else "blocked"):
            raise ValueError("v26 executable-support report status is inconsistent")
        expected_stage = (
            "fresh_executable_support_development"
            if expected_passed
            else "capability_task_or_scaffold_redesign_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("v26 executable-support report transition is inconsistent")
        if self.report_id != v26_executable_support_audit_report_id(self):
            raise ValueError("v26 executable-support report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise ValueError(f"immutable v26 executable-support artifact exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_models(path: Path, values: tuple[BaseModel, ...], *, identity: str) -> None:
    rows = sorted(
        (item.model_dump(mode="json") for item in values),
        key=lambda item: str(item[identity]),
    )
    _write_json(path, rows)


def _projection_contract(task: CapabilitySensitiveTaskArtifact) -> TypedAnswerProjectionContract:
    required = tuple(required_answer_fields(task.task.public.answer_schema))
    allowed = tuple(sorted(allowed_result_fields(task.task.public.answer_schema)))
    labels = tuple(sorted(set(task.answer_projection.values())))
    base = {
        "task_id": task.task.task_id,
        "source_task_hash": task.task.task_hash,
        "required_result_fields": required,
        "allowed_result_fields": allowed,
        "internal_reference_projection": dict(sorted(task.answer_projection.items())),
        "public_reference_labels": labels,
        "public_output_instruction": render_public_output_instruction(required, labels),
        "schema_version": EXECUTABLE_SUPPORT_CONTRACT_VERSION,
    }
    unhashed = TypedAnswerProjectionContract.model_construct(
        contract_id="pending",
        source_spec_hash="pending",
        view_bindings=(),
        **base,
    )
    source_hash = answer_projection_source_spec_hash(unhashed)
    bindings = tuple(
        ProjectionViewBinding(
            view=view,
            implementation_id=f"core.answer_projection.{view}",
            implementation_version=V26_TYPED_ANSWER_PROJECTION_VERSION,
            source_spec_hash=source_hash,
        )
        for view in PROJECTION_VIEWS
    )
    provisional = TypedAnswerProjectionContract.model_construct(
        contract_id="pending",
        source_spec_hash=source_hash,
        view_bindings=bindings,
        **base,
    )
    return TypedAnswerProjectionContract(
        contract_id=typed_answer_projection_contract_id(provisional),
        source_spec_hash=source_hash,
        view_bindings=bindings,
        **base,
    )


def _projection_bound(
    task: CapabilitySensitiveTaskArtifact,
    contract: TypedAnswerProjectionContract,
) -> bool:
    public = task.task.public.metadata.get("typed_answer_projection")
    hidden = task.task.oracle.selection_contract.get("typed_answer_projection")
    return bool(
        isinstance(public, dict)
        and isinstance(hidden, dict)
        and public.get("contract_id") == contract.contract_id
        and hidden == contract.model_dump(mode="json")
    )


def _support_set(
    kind: Literal["sufficient", "invalid"], ids: tuple[str, ...]
) -> EvidenceSupportSet:
    values = {
        "kind": kind,
        "evidence_ids": tuple(sorted(ids)),
        "rationale_code": (
            "oracle_program_and_public_witness_complete"
            if kind == "sufficient"
            else "required_role_ablation_breaks_program"
        ),
    }
    provisional = EvidenceSupportSet.model_construct(support_set_id="pending", **values)
    return EvidenceSupportSet(
        support_set_id=evidence_support_set_id(provisional),
        **values,
    )


def _evidence_lattice(
    task: CapabilitySensitiveTaskArtifact,
    compiled: CompiledProofCarryingArtifacts,
) -> EvidenceSupportLattice:
    gold = tuple(sorted(task.task.oracle.gold_evidence_ids))
    by_id = task.public_corpus.by_id()
    necessary: list[str] = []
    invalid_sets: list[EvidenceSupportSet] = []
    executor = TaskProgramExecutor(default_registry())
    for removed in gold:
        remaining = tuple(item for item in gold if item != removed)
        evidence = {item: by_id[item] for item in remaining}
        rejected = False
        try:
            executor.execute(task.task.oracle.task_program, evidence)
        except ProgramExecutionError:
            rejected = True
        if rejected:
            necessary.append(removed)
            if remaining:
                invalid_sets.append(_support_set("invalid", remaining))
    if not necessary:
        necessary = list(gold)
    provisional_lattice_id = canonical_hash(
        {"task_id": task.task.task_id, "version": V26_EVIDENCE_LATTICE_VERSION},
        prefix="prospective_evidence_support_lattice:",
    )
    hidden = task.task.oracle.selection_contract.get("evidence_support_lattice")
    current_bound = bool(
        isinstance(hidden, dict) and hidden.get("lattice_id") == provisional_lattice_id
    )
    values = {
        "task_id": task.task.task_id,
        "joint_compilation_id": compiled.joint_compilation.artifact_id,
        "necessary_evidence_ids": tuple(sorted(necessary)),
        "sufficient_support_sets": (_support_set("sufficient", gold),),
        "invalid_support_sets": tuple(sorted(invalid_sets, key=lambda item: item.support_set_id)),
        "semantic_alternative_search_complete": False,
        "unique_support_proven": False,
        "exact_equality_required": False,
        "current_verifier_bound": current_bound,
        "binding_status": "bound" if current_bound else "requires_verifier_binding",
        "schema_version": EXECUTABLE_SUPPORT_CONTRACT_VERSION,
    }
    provisional = EvidenceSupportLattice.model_construct(lattice_id="pending", **values)
    return EvidenceSupportLattice(
        lattice_id=evidence_support_lattice_id(provisional),
        **values,
    )


def _publicly_identifiable_evidence(
    task: CapabilitySensitiveTaskArtifact,
) -> tuple[Any, ...]:
    instruction = _normalize_text(task.task.public.instruction)
    aliases = {
        _normalize_text(str(item)) for item in task.task.public.retrieval_scope.get("aliases", ())
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
    gold = {item.evidence_id for item in task.evidence_bundle.evidence}
    if {item.evidence_id for item in selected} != gold:
        raise ValueError("public task fields do not identify exactly the required Evidence")
    return selected


def _normalize_text(value: str) -> str:
    return " ".join(
        "".join(character.lower() if character.isalnum() else " " for character in value).split()
    )


def _replace_runtime_refs(value: Any, reverse: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return reverse.get(value, value)
    if isinstance(value, Mapping):
        return {key: _replace_runtime_refs(item, reverse) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_runtime_refs(item, reverse) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_runtime_refs(item, reverse) for item in value)
    return value


def _project_answer(value: Mapping[str, Any], projection: Mapping[str, str]) -> dict[str, Any]:
    output = dict(value)
    for field in ("higher_ref", "selected_ref"):
        reference = output.get(field)
        if reference is not None and str(reference) in projection:
            output[field] = projection[str(reference)]
    return output


def _make_tool_manifest(task: CapabilitySensitiveTaskArtifact) -> Any:
    allowed = tuple(task.task.public.allowed_tools)
    specs = tuple(item for item in finance_archive_agent_tool_specs() if item.tool_id in allowed)
    if set(item.tool_id for item in specs) != set(allowed):
        raise ValueError("public witness refers to an unknown Finance tool")
    corpus = task.public_corpus
    snapshot_id = str(corpus.build_id or f"corpus:{corpus.corpus_id}")
    return make_agent_tool_environment_manifest(
        environment_id=f"finance_v26_executable_support:{task.artifact_id}",
        corpus_id=corpus.corpus_id,
        corpus_hash=corpus.corpus_hash,
        snapshot_id=snapshot_id,
        snapshot_hash=finance_runtime_snapshot_hash(corpus.corpus_hash, None, None),
        network_policy="forbidden",
        tools=specs,
        maximum_tool_calls=64,
        maximum_failed_tool_calls=4,
        maximum_total_observation_bytes=2_000_000,
        tool_timeout_seconds=30.0,
    )


def _compile_public_witness(
    task: CapabilitySensitiveTaskArtifact,
    compiled: CompiledProofCarryingArtifacts,
) -> tuple[PublicExecutableWitnessArtifact, tuple[AgentToolObservation, ...]]:
    manifest = _make_tool_manifest(task)
    runtime = FinanceArchiveInteractiveToolRuntime(task.public_corpus, manifest)
    by_tool = manifest.tools_by_id
    observations: list[AgentToolObservation] = []
    selected_ids: list[str] = []
    operation_evidence_ids: set[str] = set()
    verification_support_ids: set[str] = set()
    operation_refs: dict[str, str] = {}
    final_result: Mapping[str, Any] | None = None
    failures: list[str] = []
    only_public_inputs = True
    gold = set(task.task.oracle.gold_evidence_ids)

    def execute(tool_id: str, arguments: dict[str, Any]) -> AgentToolResult:
        nonlocal only_public_inputs
        call = AgentToolCall(
            call_index=len(observations) + 1,
            tool_id=tool_id,
            arguments=arguments,
        )
        by_tool[tool_id].validate_arguments(arguments)
        if tool_id == "query_structured_fact" and any(
            evidence_id in json.dumps(arguments, ensure_ascii=False, sort_keys=True)
            for evidence_id in task.task.oracle.gold_evidence_ids
        ):
            only_public_inputs = False
        referenced = _argument_evidence_ids(arguments)
        if tool_id != "query_structured_fact" and not referenced <= set(selected_ids):
            only_public_inputs = False
        result = runtime.execute(call)
        observation = make_agent_tool_observation(
            environment_manifest_id=manifest.manifest_id,
            call=call,
            result=result,
            observation_time_hash=canonical_hash(
                {"task_id": task.task.task_id, "call_index": call.call_index},
                prefix="public_witness_logical_time:",
            ),
        )
        observations.append(observation)
        if result.status != "succeeded":
            raise ValueError(result.error_message or f"public witness {tool_id} failed")
        return result

    try:
        selected = _publicly_identifiable_evidence(task)
        for item in selected:
            payload = item.payload.model_dump(mode="json", exclude_none=True)
            result = execute(
                "query_structured_fact",
                {
                    "subject_alias": item.subject.subject_id,
                    "metric_alias": item.predicate,
                    "period_label": item.temporal_context.label,
                    "public_filters": {
                        "source_id": item.source.source_id,
                        "source_authority": item.source.authority.value,
                        "unit": payload.get("unit"),
                        "currency": payload.get("currency"),
                        "definition_id": item.definition.definition_id,
                        "time_basis": item.temporal_context.basis,
                        "frequency": item.temporal_context.frequency,
                        "subject_type": item.subject.subject_type,
                    },
                },
            )
            selected_ids.extend(result.evidence_ids)
        selected_ids = list(dict.fromkeys(selected_ids))

        if task.reconciliation_axes:
            if "normalize_metric_unit_period" not in by_tool:
                raise ValueError("required_normalization_tool_not_allowed")
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
                execute(
                    "normalize_metric_unit_period",
                    {"evidence_ids": selected_ids, "target_definition": target},
                )

        for node in task.task.oracle.task_program.nodes:
            operands: list[dict[str, str]] = []
            for item in node.input_refs:
                if item.kind.value == "evidence":
                    operands.append({"evidence_id": item.ref_id})
                else:
                    operand = {"operation_ref": operation_refs[item.ref_id]}
                    if item.selector is not None:
                        operand["selector"] = item.selector
                    operands.append(operand)
            result = execute(
                "calculator",
                {
                    "operator": node.operator_id,
                    "operands": operands,
                    "parameters": node.parameters,
                },
            )
            operation_evidence_ids.update(result.evidence_ids)
            operation = cast(dict[str, Any], result.result["result"])
            operation_refs[node.node_id] = str(operation["operation_ref"])
            final_result = cast(Mapping[str, Any], operation["output"])

        reverse = {runtime_ref: node_id for node_id, runtime_ref in operation_refs.items()}
        canonical_result = cast(dict[str, Any], _replace_runtime_refs(final_result, reverse))
        projected = _project_answer(canonical_result, task.answer_projection)
        output_ref = operation_refs[task.task.oracle.task_program.output_node_id]
        for _ in task.verification_checkpoints:
            result = execute(
                "cross_check_evidence",
                {
                    "evidence_ids": selected_ids,
                    "claim_or_result": {"operation_ref": output_ref},
                },
            )
            if result.result.get("verified") is not True:
                raise ValueError("public witness verification returned false")
            verification_support_ids.update(result.result.get("support") or ())
            verification_support_ids.update(result.evidence_ids)

        operation_lineage_complete = gold <= operation_evidence_ids
        evidence_support_complete = set(selected_ids) == gold
        verification_complete = gold <= verification_support_ids
        answer_projection_complete = (
            canonical_result == task.execution.final_output
            and projected == task.projected_expected_output
            and set(required_answer_fields(task.task.public.answer_schema)) <= set(projected)
        )
    except (KeyError, TypeError, ValueError) as exc:
        failures.append(str(exc) or type(exc).__name__)
        projected = {}
        operation_lineage_complete = False
        evidence_support_complete = False
        verification_complete = False
        answer_projection_complete = False

    only_allowed_tools = set(item.call.tool_id for item in observations) <= set(
        task.task.public.allowed_tools
    )
    cited_ids = tuple(sorted(set(selected_ids)))
    citation_complete = set(cited_ids) == gold
    checks = {
        "only_public_inputs": only_public_inputs,
        "only_allowed_tools": only_allowed_tools,
        "operation_lineage_complete": operation_lineage_complete,
        "evidence_support_complete": evidence_support_complete,
        "verification_complete": verification_complete,
        "answer_projection_complete": answer_projection_complete,
        "citation_complete": citation_complete,
    }
    for key, passed in checks.items():
        if not passed and key not in failures:
            failures.append(key)
    verifier_report = {
        "task_id": task.task.task_id,
        "joint_compilation_id": compiled.joint_compilation.artifact_id,
        "checks": checks,
        "selected_evidence_ids": sorted(set(selected_ids)),
        "verification_support_ids": sorted(verification_support_ids),
        "cited_evidence_ids": cited_ids,
        "normalized_answer_hash": canonical_hash(projected, prefix="public_witness_answer:"),
    }
    steps = tuple(
        PublicWitnessStep(
            step_index=index,
            tool_id=item.call.tool_id,
            call_hash=canonical_hash(item.call, prefix="public_witness_tool_call:"),
            observation_id=item.observation_id,
            observation_content_hash=item.content_hash,
            evidence_ids=tuple(sorted(item.evidence_ids)),
            operation_ref=_operation_ref(item),
            normalized_operation_ref=_normalized_operation_ref(item),
        )
        for index, item in enumerate(observations, start=1)
    )
    values = {
        "task_id": task.task.task_id,
        "joint_compilation_id": compiled.joint_compilation.artifact_id,
        "environment_manifest_id": manifest.manifest_id,
        "environment_manifest_hash": canonical_hash(manifest, prefix="public_witness_environment:"),
        "public_projection_hash": canonical_hash(
            compiled.public_artifact, prefix="public_witness_projection:"
        ),
        "allowed_tools": tuple(sorted(task.task.public.allowed_tools)),
        "steps": steps,
        "selected_evidence_ids": tuple(sorted(set(selected_ids))),
        "verification_support_ids": tuple(sorted(verification_support_ids)),
        "cited_evidence_ids": cited_ids,
        "citation_complete": citation_complete,
        "normalized_answer_hash": verifier_report["normalized_answer_hash"],
        "independent_verifier_report_hash": canonical_hash(
            verifier_report, prefix="public_witness_independent_verifier:"
        ),
        **checks,
        "full_validity_passed": all(checks.values()),
        "failure_reasons": tuple(sorted(set(failures))),
        "schema_version": EXECUTABLE_SUPPORT_CONTRACT_VERSION,
    }
    provisional = PublicExecutableWitnessArtifact.model_construct(witness_id="pending", **values)
    return (
        PublicExecutableWitnessArtifact(
            witness_id=public_executable_witness_id(provisional),
            **values,
        ),
        tuple(observations),
    )


def _argument_evidence_ids(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        found = {
            str(item)
            for key, item in value.items()
            if key == "evidence_id" and isinstance(item, str)
        }
        found.update(
            str(item)
            for key, items in value.items()
            if key == "evidence_ids" and isinstance(items, (list, tuple))
            for item in items
        )
        for item in value.values():
            found.update(_argument_evidence_ids(item))
        return found
    if isinstance(value, (list, tuple)):
        return {item for nested in value for item in _argument_evidence_ids(nested)}
    return set()


def _operation_ref(observation: AgentToolObservation) -> str | None:
    if observation.call.tool_id != "calculator":
        return None
    result = observation.result.get("result")
    return str(result.get("operation_ref")) if isinstance(result, dict) else None


def _normalized_operation_ref(observation: AgentToolObservation) -> str | None:
    if observation.call.tool_id != "normalize_metric_unit_period":
        return None
    value = observation.result.get("normalized_operation_ref")
    return str(value) if value else None


def _target_mechanism(root: V26FreshTaskRoot) -> TargetMechanism:
    if root.mechanism_id == "context_conditioned_action":
        return "context_conditioned_action"
    if root.mechanism_id == "semantic_reconciliation":
        return "semantic_reconciliation"
    if root.task_family == "finance.recovery_guided_search":
        return "failure_recovery"
    if root.task_family == "finance.stopping_decision_control":
        return "state_dependent_stopping"
    raise ValueError(f"cannot split v26 target mechanism: {root.task_family}")


def _necessity_artifact(
    task: CapabilitySensitiveTaskArtifact,
    root: V26FreshTaskRoot,
    witness: PublicExecutableWitnessArtifact,
) -> MechanismNecessityArtifact:
    target = _target_mechanism(root)
    typed_contract = task.task.oracle.selection_contract.get("mechanism_necessity_contract")
    registered = isinstance(typed_contract, dict) and typed_contract.get("mechanism_id") == target
    normalized_refs = tuple(
        item.normalized_operation_ref for item in witness.steps if item.normalized_operation_ref
    )
    closure_checks: dict[str, bool]
    if target == "context_conditioned_action":
        closure_checks = {
            "mechanism_registered_in_task_contract": registered,
            "wrong_action_irreparable": False,
        }
        required = ("replace", "bypass")
    elif target == "semantic_reconciliation":
        closure_checks = {
            "mechanism_registered_in_task_contract": registered,
            "normalized_operation_reference_emitted": bool(normalized_refs),
            "normalized_operation_reference_consumed": False,
        }
        required = ("delete", "bypass")
    elif target == "failure_recovery":
        closure_checks = {
            "mechanism_registered_in_task_contract": registered,
            "typed_failure_trigger_registered": False,
            "recovery_separate_from_stopping": root.mechanism_id != "recovery_and_stopping",
        }
        required = ("delete", "replace")
    else:
        closure_checks = {
            "mechanism_registered_in_task_contract": registered,
            "model_owned_stop_decision_registered": False,
            "stopping_separate_from_recovery": root.mechanism_id != "recovery_and_stopping",
        }
        required = ("delete", "bypass")
    failures = tuple(sorted(key for key, passed in closure_checks.items() if not passed))
    values = {
        "task_id": task.task.task_id,
        "public_witness_id": witness.witness_id,
        "target_mechanism_id": target,
        "required_mutation_kinds": required,
        "counterfactual_results": (),
        "closure_checks": closure_checks,
        "mechanism_observed_in_witness": registered,
        "status": "blocked",
        "failure_reasons": failures or ("mechanism_counterfactuals_missing",),
        "schema_version": EXECUTABLE_SUPPORT_CONTRACT_VERSION,
    }
    provisional = MechanismNecessityArtifact.model_construct(artifact_id="pending", **values)
    return MechanismNecessityArtifact(
        artifact_id=mechanism_necessity_artifact_id(provisional),
        **values,
    )


def _alternative_catalog(
    task: CapabilitySensitiveTaskArtifact,
    witness: PublicExecutableWitnessArtifact,
) -> AlternativeValidPathCatalog:
    values = {
        "task_id": task.task.task_id,
        "paths": (),
        "compiler_witness_count": int(witness.full_validity_passed),
        "scaffold_surface_only_path_count": 0,
        "status": "blocked",
        "failure_reasons": (
            "three_model_owned_valid_paths_missing",
            "three_distinct_quotient_states_missing",
            "compiler_witness_is_not_model_owned",
        ),
        "schema_version": EXECUTABLE_SUPPORT_CONTRACT_VERSION,
    }
    provisional = AlternativeValidPathCatalog.model_construct(catalog_id="pending", **values)
    return AlternativeValidPathCatalog(
        catalog_id=alternative_valid_path_catalog_id(provisional),
        **values,
    )


def _task_compilation(
    *,
    root: V26FreshTaskRoot,
    task: CapabilitySensitiveTaskArtifact,
    compiled: CompiledProofCarryingArtifacts,
    projection: TypedAnswerProjectionContract,
    projection_bound: bool,
    witness: PublicExecutableWitnessArtifact,
    lattice: EvidenceSupportLattice,
    necessity: MechanismNecessityArtifact,
    catalog: AlternativeValidPathCatalog,
) -> ExecutableSupportTaskCompilation:
    blockers: list[str] = []
    checks = {
        "typed_answer_projection_not_bound": projection_bound,
        "public_executable_witness_failed": witness.full_validity_passed,
        "evidence_support_lattice_not_bound": lattice.current_verifier_bound,
        "mechanism_necessity_not_proven": necessity.status == "passed",
        "three_alternative_valid_paths_not_proven": catalog.status == "passed",
    }
    blockers.extend(key for key, passed in checks.items() if not passed)
    capability = all(tuple(checks.values())[:4])
    vtdo = capability and checks["three_alternative_valid_paths_not_proven"]
    values = {
        "task_id": task.task.task_id,
        "joint_compilation_id": compiled.joint_compilation.artifact_id,
        "source_mechanism_id": root.mechanism_id,
        "target_mechanism_id": _target_mechanism(root),
        "answer_projection_contract_id": projection.contract_id,
        "public_witness_id": witness.witness_id,
        "mechanism_necessity_artifact_id": necessity.artifact_id,
        "alternative_path_catalog_id": catalog.catalog_id,
        "evidence_support_lattice_id": lattice.lattice_id,
        "answer_projection_bound": projection_bound,
        "evidence_lattice_bound": lattice.current_verifier_bound,
        "public_witness_passed": witness.full_validity_passed,
        "mechanism_necessity_passed": necessity.status == "passed",
        "alternative_paths_passed": catalog.status == "passed",
        "capability_measurement_eligible": capability,
        "vtdo_multistate_eligible": vtdo,
        "assigned_task_use": (
            "vtdo_multistate" if vtdo else "capability_measurement" if capability else "blocked"
        ),
        "blockers": tuple(sorted(blockers)),
        "schema_version": EXECUTABLE_SUPPORT_CONTRACT_VERSION,
    }
    provisional = ExecutableSupportTaskCompilation.model_construct(
        compilation_id="pending", **values
    )
    return ExecutableSupportTaskCompilation(
        compilation_id=executable_support_task_compilation_id(provisional),
        **values,
    )


def _task_record(
    *,
    root: V26FreshTaskRoot,
    task: CapabilitySensitiveTaskArtifact,
    projection: TypedAnswerProjectionContract,
    projection_bound: bool,
    witness: PublicExecutableWitnessArtifact,
    lattice: EvidenceSupportLattice,
    necessity: MechanismNecessityArtifact,
    catalog: AlternativeValidPathCatalog,
    compilation: ExecutableSupportTaskCompilation,
) -> TaskExecutableSupportAuditRecord:
    values = {
        "task_id": task.task.task_id,
        "source_task_artifact_id": task.artifact_id,
        "source_mechanism_id": root.mechanism_id,
        "target_mechanism_id": _target_mechanism(root),
        "answer_projection_contract_id": projection.contract_id,
        "answer_projection_bound": projection_bound,
        "public_witness_id": witness.witness_id,
        "public_witness_passed": witness.full_validity_passed,
        "evidence_support_lattice_id": lattice.lattice_id,
        "evidence_lattice_bound": lattice.current_verifier_bound,
        "mechanism_necessity_artifact_id": necessity.artifact_id,
        "mechanism_necessity_passed": necessity.status == "passed",
        "alternative_path_catalog_id": catalog.catalog_id,
        "alternative_paths_passed": catalog.status == "passed",
        "capability_measurement_eligible": compilation.capability_measurement_eligible,
        "vtdo_multistate_eligible": compilation.vtdo_multistate_eligible,
        "blockers": compilation.blockers,
        "schema_version": V26_EXECUTABLE_SUPPORT_AUDIT_VERSION,
    }
    provisional = TaskExecutableSupportAuditRecord.model_construct(record_id="pending", **values)
    return TaskExecutableSupportAuditRecord(
        record_id=task_executable_support_audit_record_id(provisional),
        **values,
    )


def _artifact_file(path: Path, output_dir: Path, record_count: int) -> ImmutableArtifactFile:
    return ImmutableArtifactFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=record_count,
    )


def build_v26_executable_support_audit(
    *,
    run_id: str,
    source_no_api_dir: Path,
    source_statistical_audit_path: Path,
    output_dir: Path,
) -> V26ExecutableSupportAuditReport:
    compiled_path = source_no_api_dir / "joint" / "compiled_proof_artifacts.json"
    population_path = source_no_api_dir / "population" / "development.json"
    compiled_rows = json.loads(compiled_path.read_text(encoding="utf-8"))
    if not isinstance(compiled_rows, list):
        raise ValueError("v26 source compiled artifacts must be a list")
    compiled = tuple(CompiledProofCarryingArtifacts.model_validate(item) for item in compiled_rows)
    population = V26FreshTaskPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    statistical = BridgeStatisticalAuditReport.model_validate_json(
        source_statistical_audit_path.read_text(encoding="utf-8")
    )
    if (
        statistical.rollout_count != 576
        or statistical.status != "observed_non_authorizing"
        or statistical.next_transition != "capability_task_or_scaffold_redesign_only"
    ):
        raise ValueError("v26 executable-support audit requires the blocked complete v26.53 audit")
    if len(compiled) != 24 or len(population.tasks) != 24:
        raise ValueError("v26 executable-support audit requires exactly 24 source tasks")

    source_tasks = load_v26_selected_source_tasks(population)
    source_by_task = {item.task.task_id: item for item in source_tasks}
    root_by_task = {item.task_id: item for item in population.tasks}
    compiled_by_task = {item.task.task_id: item for item in compiled}
    expected = set(source_by_task)
    if set(root_by_task) != expected or set(compiled_by_task) != expected:
        raise ValueError("v26 executable-support source identities are incomplete")

    projections: list[TypedAnswerProjectionContract] = []
    witnesses: list[PublicExecutableWitnessArtifact] = []
    observations: list[AgentToolObservation] = []
    lattices: list[EvidenceSupportLattice] = []
    necessities: list[MechanismNecessityArtifact] = []
    catalogs: list[AlternativeValidPathCatalog] = []
    compilations: list[ExecutableSupportTaskCompilation] = []
    records: list[TaskExecutableSupportAuditRecord] = []

    for task_id in sorted(expected):
        task = source_by_task[task_id]
        root = root_by_task[task_id]
        compiled_item = compiled_by_task[task_id]
        projection = _projection_contract(task)
        projection_bound = _projection_bound(task, projection)
        lattice = _evidence_lattice(task, compiled_item)
        witness, witness_observations = _compile_public_witness(task, compiled_item)
        necessity = _necessity_artifact(task, root, witness)
        catalog = _alternative_catalog(task, witness)
        compilation = _task_compilation(
            root=root,
            task=task,
            compiled=compiled_item,
            projection=projection,
            projection_bound=projection_bound,
            witness=witness,
            lattice=lattice,
            necessity=necessity,
            catalog=catalog,
        )
        record = _task_record(
            root=root,
            task=task,
            projection=projection,
            projection_bound=projection_bound,
            witness=witness,
            lattice=lattice,
            necessity=necessity,
            catalog=catalog,
            compilation=compilation,
        )
        projections.append(projection)
        witnesses.append(witness)
        observations.extend(witness_observations)
        lattices.append(lattice)
        necessities.append(necessity)
        catalogs.append(catalog)
        compilations.append(compilation)
        records.append(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "answer": output_dir / "typed_answer_projection_contracts.json",
        "witness": output_dir / "public_executable_witnesses.json",
        "observations": output_dir / "public_witness_observations.json",
        "lattice": output_dir / "evidence_support_lattices.json",
        "necessity": output_dir / "mechanism_necessity_artifacts.json",
        "catalog": output_dir / "alternative_valid_path_catalogs.json",
        "compilation": output_dir / "task_support_compilations.json",
    }
    _write_models(paths["answer"], tuple(projections), identity="contract_id")
    _write_models(paths["witness"], tuple(witnesses), identity="witness_id")
    _write_models(paths["observations"], tuple(observations), identity="observation_id")
    _write_models(paths["lattice"], tuple(lattices), identity="lattice_id")
    _write_models(paths["necessity"], tuple(necessities), identity="artifact_id")
    _write_models(paths["catalog"], tuple(catalogs), identity="catalog_id")
    _write_models(paths["compilation"], tuple(compilations), identity="compilation_id")
    files = tuple(
        _artifact_file(
            path,
            output_dir,
            len(observations) if key == "observations" else 24,
        )
        for key, path in sorted(paths.items())
    )

    mechanism_counts = Counter(_target_mechanism(item) for item in population.tasks)
    ordered_records = tuple(sorted(records, key=lambda item: item.task_id))
    context_irreparable = sum(
        item.closure_checks.get("wrong_action_irreparable") is True
        for item in necessities
        if item.target_mechanism_id == "context_conditioned_action"
    )
    reconciliation_consumed = sum(
        item.closure_checks.get("normalized_operation_reference_consumed") is True
        for item in necessities
        if item.target_mechanism_id == "semantic_reconciliation"
    )
    values = {
        "run_id": run_id,
        "source_no_api_root": str(source_no_api_dir),
        "source_compiled_artifacts_sha256": _sha256(compiled_path),
        "source_development_population_sha256": _sha256(population_path),
        "source_statistical_audit_id": statistical.audit_id,
        "source_statistical_audit_sha256": _sha256(source_statistical_audit_path),
        "typed_answer_projection_bound_count": sum(
            _projection_bound(source_by_task[item.task_id], item) for item in projections
        ),
        "public_witness_pass_count": sum(item.full_validity_passed for item in witnesses),
        "evidence_lattice_bound_count": sum(item.current_verifier_bound for item in lattices),
        "mechanism_necessity_pass_count": sum(item.status == "passed" for item in necessities),
        "alternative_path_catalog_pass_count": sum(item.status == "passed" for item in catalogs),
        "capability_measurement_eligible_count": sum(
            item.capability_measurement_eligible for item in compilations
        ),
        "vtdo_multistate_eligible_count": sum(
            item.vtdo_multistate_eligible for item in compilations
        ),
        "target_mechanism_task_counts": {
            mechanism: mechanism_counts[mechanism] for mechanism in TARGET_MECHANISMS
        },
        "context_wrong_action_irreparable_pass_count": context_irreparable,
        "reconciliation_normalized_ref_consumed_pass_count": reconciliation_consumed,
        "conditional_metric_definitions": CONDITIONAL_METRIC_DEFINITIONS,
        "task_records": ordered_records,
        "immutable_artifact_files": files,
        "status": (
            "passed"
            if all(item.capability_measurement_eligible for item in compilations)
            else "blocked"
        ),
        "next_permitted_stage": (
            "fresh_executable_support_development"
            if all(item.capability_measurement_eligible for item in compilations)
            else "capability_task_or_scaffold_redesign_only"
        ),
        "schema_version": V26_EXECUTABLE_SUPPORT_AUDIT_VERSION,
    }
    provisional = V26ExecutableSupportAuditReport.model_construct(report_id="pending", **values)
    report = V26ExecutableSupportAuditReport(
        report_id=v26_executable_support_audit_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def task_executable_support_audit_record_id(
    value: TaskExecutableSupportAuditRecord,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="finance_v26_task_executable_support_audit:",
    )


def v26_executable_support_audit_report_id(
    value: V26ExecutableSupportAuditReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_executable_support_audit:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Finance v26 executable-support audit")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-no-api-dir", type=Path, required=True)
    parser.add_argument("--source-statistical-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build_v26_executable_support_audit(
        run_id=args.run_id,
        source_no_api_dir=args.source_no_api_dir,
        source_statistical_audit_path=args.source_statistical_audit,
        output_dir=args.output_dir,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
