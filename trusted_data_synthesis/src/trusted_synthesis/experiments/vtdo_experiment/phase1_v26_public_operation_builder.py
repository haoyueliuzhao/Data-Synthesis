from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.program import InputRefKind, TaskProgram
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.public_operation import (
    OPERATIONAL_EXECUTABLE_TASK_PACKAGE_VERSION,
    OperationalExecutableTaskPackage,
    OperationalExecutableVerifierBinding,
    PublicOperationContractView,
    PublicOperationExecutionContract,
    PublicOperationInput,
    PublicOperationNode,
    PublicOperationNodeBinding,
    PublicOperationPredicate,
    PublicOperationRuntimeProjection,
    PublicOperationVariable,
    PublicStopReadinessContract,
    PublicVariableResolutionRule,
    operational_executable_task_package_id,
    operational_executable_verifier_binding_id,
    public_operation_contract_view_id,
    public_operation_execution_contract_id,
    public_operation_runtime_projection_id,
    public_stop_readiness_contract_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_capability_ladder import (
    core_task_semantic_signature,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    RematerializedExecutableTaskRecord,
    V26ExecutableTaskRematerializationReport,
    _materialize_task,
    _TaskDraft,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exposure_clean_population import (
    ExposureCleanPopulationReceipt,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26FreshTaskPopulation,
    load_v26_selected_source_tasks,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    FRESHNESS_CHANNELS,
    IMPLEMENTATION_SOURCE_PATHS,
    V26_OPERATIONAL_VERIFIER_ID,
    V26_OPERATIONAL_VERIFIER_VERSION,
    V26_PUBLIC_OPERATION_REMATERIALIZATION_VERSION,
    FreshnessChannelAudit,
    ImmutableArtifactFile,
    ImplementationSourceFile,
    OperationalTaskRecord,
    PublicOperationFreshnessAudit,
    TargetMechanism,
    operational_task_record_id,
    public_operation_freshness_audit_id,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import (
    AgentToolEnvironmentManifest,
)

MECHANISM_SOURCE_FAMILY = {
    "context_conditioned_action": "finance.branching_operation_plan",
    "failure_recovery": "finance.recovery_guided_search",
    "state_dependent_stopping": "finance.stopping_decision_control",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    if path.exists():
        raise ValueError(f"immutable v26.60 artifact exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_models(path: Path, values: Sequence[BaseModel], *, identity: str) -> None:
    rows = sorted(
        (item.model_dump(mode="json") for item in values),
        key=lambda item: str(item[identity]),
    )
    _write_json(path, rows)


def _artifact_file(
    path: Path,
    output_dir: Path,
    record_count: int,
) -> ImmutableArtifactFile:
    return ImmutableArtifactFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        record_count=record_count,
    )


def _implementation_source_files() -> tuple[ImplementationSourceFile, ...]:
    package_root = Path(__file__).resolve().parents[4]
    paths = tuple(package_root / value for value in sorted(IMPLEMENTATION_SOURCE_PATHS))
    if any(not path.is_file() for path in paths):
        raise ValueError("v26.60 implementation manifest refers to a missing file")
    return tuple(
        ImplementationSourceFile(
            relative_path=str(path.relative_to(package_root)),
            sha256=_sha256(path),
        )
        for path in paths
    )


def _load_population(path: Path) -> CapabilitySensitiveFrontierPopulation:
    return CapabilitySensitiveFrontierPopulation.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def _load_sources(
    *,
    development_population_path: Path,
    secondary_source_path: Path,
    tertiary_source_path: Path,
    tertiary_no_api_report_path: Path,
    prior_rematerialization_dir: Path,
    snapshot_path: Path,
    exposure_receipt_path: Path,
) -> tuple[
    V26FreshTaskPopulation,
    tuple[CapabilitySensitiveTaskArtifact, ...],
    tuple[
        CapabilitySensitiveFrontierPopulation,
        CapabilitySensitiveFrontierPopulation,
        CapabilitySensitiveFrontierPopulation,
    ],
    V26ExecutableTaskRematerializationReport,
    tuple[RematerializedExecutableTaskRecord, ...],
    ExposureCleanPopulationReceipt,
    str,
]:
    development = V26FreshTaskPopulation.model_validate_json(
        development_population_path.read_text(encoding="utf-8")
    )
    if development.phase != "development":
        raise ValueError("v26.60 source selection is not the frozen Development role")
    development_tasks = load_v26_selected_source_tasks(development)
    primary_path = Path(development.source_population_path)
    if _sha256(primary_path) != development.source_population_sha256:
        raise ValueError("v26.60 primary source Population byte replay failed")
    primary = _load_population(primary_path)
    secondary = _load_population(secondary_source_path)
    tertiary = _load_population(tertiary_source_path)
    if len({primary.population_id, secondary.population_id, tertiary.population_id}) != 3:
        raise ValueError("v26.60 requires three independently identified source Populations")
    tertiary_report = json.loads(tertiary_no_api_report_path.read_text(encoding="utf-8"))
    expected_tertiary_source = (
        tertiary_no_api_report_path.parent / "population" / "confirmation_source.json"
    )
    if (
        tertiary_report.get("model_api_calls") != 0
        or tertiary_report.get("gpu_jobs") != 0
        or tertiary_source_path.resolve() != expected_tertiary_source.resolve()
    ):
        raise ValueError("v26.60 tertiary source lacks an immutable zero-API receipt")
    tertiary_report_sha256 = _sha256(tertiary_no_api_report_path)

    prior_report = V26ExecutableTaskRematerializationReport.model_validate_json(
        (prior_rematerialization_dir / "report.json").read_text(encoding="utf-8")
    )
    prior_records = tuple(
        RematerializedExecutableTaskRecord.model_validate(item)
        for item in json.loads(
            (prior_rematerialization_dir / "rematerialized_task_records.json").read_text(
                encoding="utf-8"
            )
        )
    )
    if {item.task_package.package_id for item in prior_records} != {
        item.task_package.package_id for item in prior_report.task_records
    }:
        raise ValueError("v26.56 task-record replay differs from its immutable report")

    receipt = ExposureCleanPopulationReceipt.model_validate_json(
        exposure_receipt_path.read_text(encoding="utf-8")
    )
    if Path(
        receipt.source_artifacts_path
    ).resolve() != snapshot_path.resolve() or receipt.source_artifacts_sha256 != _sha256(
        snapshot_path
    ):
        raise ValueError("v26.60 Snapshot differs from the exposure-clean receipt")
    return (
        development,
        development_tasks,
        (primary, secondary, tertiary),
        prior_report,
        prior_records,
        receipt,
        tertiary_report_sha256,
    )


def _source_task_values(
    tasks: Sequence[CapabilitySensitiveTaskArtifact],
) -> dict[str, set[str]]:
    return {
        "source_task_artifact_id": {item.artifact_id for item in tasks},
        "source_task_semantic_signature": {core_task_semantic_signature(item) for item in tasks},
        "source_task_hash": {item.task.task_hash for item in tasks},
        "evidence_id": {
            evidence.evidence_id for task in tasks for evidence in task.public_corpus.evidence
        },
        "evidence_version_id": {
            evidence.evidence_version_id
            for task in tasks
            for evidence in task.public_corpus.evidence
        },
        "source_record_id": {
            evidence.provenance.source_record_id
            for task in tasks
            for evidence in task.public_corpus.evidence
        },
    }


def _record_evidence_values(
    records: Sequence[RematerializedExecutableTaskRecord],
) -> dict[str, set[str]]:
    return {
        "source_task_artifact_id": {
            value for record in records for value in record.source_task_artifact_ids
        },
        "source_task_semantic_signature": set(),
        "source_task_hash": set(),
        "evidence_id": {
            item.evidence_id for record in records for item in record.public_corpus.evidence
        },
        "evidence_version_id": {
            item.evidence_version_id for record in records for item in record.public_corpus.evidence
        },
        "source_record_id": {
            item.provenance.source_record_id
            for record in records
            for item in record.public_corpus.evidence
        },
    }


def _merge_values(*groups: Mapping[str, set[str]]) -> dict[str, set[str]]:
    return {
        channel: set().union(*(group[channel] for group in groups))
        for channel in FRESHNESS_CHANNELS
    }


def _select_source_tasks(
    sources: Sequence[CapabilitySensitiveFrontierPopulation],
    *,
    excluded: Mapping[str, set[str]],
    sampling_salt: str,
) -> dict[TargetMechanism, tuple[CapabilitySensitiveTaskArtifact, ...]]:
    output: dict[TargetMechanism, tuple[CapabilitySensitiveTaskArtifact, ...]] = {}
    selected_evidence_ids: set[str] = set()
    selected_evidence_versions: set[str] = set()
    selected_source_records: set[str] = set()
    for mechanism, family in MECHANISM_SOURCE_FAMILY.items():
        candidates = [task for source in sources for task in source.tasks if task.family == family]
        if mechanism == "failure_recovery":
            candidates = [item for item in candidates if item.recovery_branches]
        eligible = []
        for item in candidates:
            values = _source_task_values((item,))
            if any(values[channel] & excluded[channel] for channel in FRESHNESS_CHANNELS):
                continue
            eligible.append(item)
        eligible.sort(
            key=lambda item: canonical_hash(
                {
                    "salt": sampling_salt,
                    "mechanism": mechanism,
                    "source_task_artifact_id": item.artifact_id,
                },
                prefix="finance_v26_public_operation_source_rank:",
            )
        )
        selected = []
        for item in eligible:
            evidence_ids = {value.evidence_id for value in item.public_corpus.evidence}
            versions = {value.evidence_version_id for value in item.public_corpus.evidence}
            source_records = {
                value.provenance.source_record_id for value in item.public_corpus.evidence
            }
            if (
                evidence_ids & selected_evidence_ids
                or versions & selected_evidence_versions
                or source_records & selected_source_records
            ):
                continue
            selected.append(item)
            selected_evidence_ids.update(evidence_ids)
            selected_evidence_versions.update(versions)
            selected_source_records.update(source_records)
            if len(selected) == 6:
                break
        if len(selected) != 6:
            raise ValueError(f"fresh source capacity cannot supply six tasks for {mechanism}")
        output[cast(TargetMechanism, mechanism)] = tuple(selected)
    return output


def _freshness_audit(
    *,
    development: V26FreshTaskPopulation,
    prior_report: V26ExecutableTaskRematerializationReport,
    prior_records: Sequence[RematerializedExecutableTaskRecord],
    sources: Sequence[CapabilitySensitiveFrontierPopulation],
    tertiary_no_api_report_sha256: str,
    prior_values: Mapping[str, set[str]],
    selected_source_tasks: Sequence[CapabilitySensitiveTaskArtifact],
    drafts: Sequence[_TaskDraft],
) -> PublicOperationFreshnessAudit:
    selected_values = _source_task_values(selected_source_tasks)
    selected_containers = tuple(
        sorted(
            {
                value
                for draft in drafts
                if draft.mechanism_id == "semantic_reconciliation"
                for value in draft.source_task_artifact_ids
            }
        )
    )
    prior_containers = {
        value
        for record in prior_records
        if record.mechanism_id == "semantic_reconciliation"
        for value in record.source_task_artifact_ids
    }
    shared_containers = tuple(sorted(set(selected_containers) & prior_containers))
    if selected_containers != shared_containers:
        raise ValueError("Reconciliation uses an unregistered shared source container")
    selected_values["evidence_id"] = {
        item.evidence_id for draft in drafts for item in draft.public_corpus.evidence
    }
    selected_values["evidence_version_id"] = {
        item.evidence_version_id for draft in drafts for item in draft.public_corpus.evidence
    }
    selected_values["source_record_id"] = {
        item.provenance.source_record_id
        for draft in drafts
        for item in draft.public_corpus.evidence
    }
    channels = []
    for channel in sorted(FRESHNESS_CHANNELS):
        prior = tuple(sorted(prior_values[channel]))
        selected = tuple(sorted(selected_values[channel]))
        overlap = tuple(sorted(set(prior) & set(selected)))
        if overlap:
            raise ValueError(f"v26.60 freshness channel {channel} is not disjoint")
        channels.append(
            FreshnessChannelAudit(
                channel=channel,
                prior_count=len(prior),
                selected_count=len(selected),
                prior_set_hash=canonical_hash(
                    {"channel": channel, "values": prior},
                    prefix="finance_v26_public_operation_prior_set:",
                ),
                selected_set_hash=canonical_hash(
                    {"channel": channel, "values": selected},
                    prefix="finance_v26_public_operation_selected_set:",
                ),
                overlap_values=(),
                overlap_count=0,
            )
        )
    values = {
        "development_population_id": development.population_id,
        "prior_rematerialization_report_id": prior_report.report_id,
        "source_population_ids": tuple(sorted(item.population_id for item in sources)),
        "tertiary_no_api_report_sha256": tertiary_no_api_report_sha256,
        "tertiary_model_api_calls": 0,
        "tertiary_gpu_jobs": 0,
        "shared_read_only_source_container_ids": shared_containers,
        "source_container_reuse_policy": (
            "immutable_container_shared_rows_must_be_identity_disjoint"
        ),
        "selected_reconciliation_source_record_overlap_count": 0,
        "channels": tuple(channels),
        "selected_task_count": len(selected_source_tasks),
        "selected_reconciliation_evidence_count": sum(
            len(draft.public_corpus.evidence)
            for draft in drafts
            if draft.mechanism_id == "semantic_reconciliation"
        ),
        "status": "passed",
        "schema_version": V26_PUBLIC_OPERATION_REMATERIALIZATION_VERSION,
    }
    provisional = PublicOperationFreshnessAudit.model_construct(audit_id="pending", **values)
    return PublicOperationFreshnessAudit(
        audit_id=public_operation_freshness_audit_id(provisional),
        **values,
    )


def _public_predicates(item: EvidenceItem) -> tuple[PublicOperationPredicate, ...]:
    values: dict[tuple[str, ...], Any] = {
        ("subject", "name"): item.subject.name,
        ("subject", "subject_id"): item.subject.subject_id,
        ("subject", "type"): item.subject.subject_type,
        ("metric", "predicate"): item.predicate,
        ("metric", "definition_id"): item.definition.definition_id,
        ("period",): item.temporal_context.label,
        ("source", "source_id"): item.source.source_id,
        ("source", "authority"): item.source.authority.value,
        ("payload", "kind"): item.payload.kind,
        ("payload", "unit"): getattr(item.payload, "unit", None),
        ("payload", "currency"): getattr(item.payload, "currency", None),
        ("time_basis",): item.temporal_context.basis,
        ("frequency",): item.temporal_context.frequency,
    }
    return tuple(
        PublicOperationPredicate(selector=selector, value=values[selector])
        for selector in sorted(values)
    )


def _public_variables(
    draft: _TaskDraft,
) -> tuple[tuple[PublicOperationVariable, ...], dict[str, str]]:
    variables = []
    evidence_to_symbol = {}
    for index, item in enumerate(
        sorted(draft.public_corpus.evidence, key=lambda value: value.evidence_id),
        start=1,
    ):
        symbol = f"required_evidence_role_{index:02d}"
        predicates = _public_predicates(item)
        rules = (
            PublicVariableResolutionRule(
                source_tool_id="query_structured_fact",
                collection_selector=("facts",),
                evidence_id_selector=("evidence_id",),
                equals=predicates,
            ),
            PublicVariableResolutionRule(
                source_tool_id="open_document",
                collection_selector=("content", "facts"),
                evidence_id_selector=("evidence_id",),
                equals=predicates,
            ),
        )
        variables.append(
            PublicOperationVariable(
                symbol=symbol,
                semantic_role=f"required_public_finance_record_{index:02d}",
                resolution_rules=rules,
            )
        )
        evidence_to_symbol[item.evidence_id] = symbol
    return tuple(variables), evidence_to_symbol


def _source_verifier_dag_hash(program: TaskProgram) -> str:
    return canonical_hash(
        {
            "output_node_id": program.output_node_id,
            "nodes": tuple(
                {
                    "node_id": node.node_id,
                    "dependencies": node.dependencies,
                    "output_schema": node.output_schema,
                    "verifier_id": node.verifier_id,
                }
                for node in program.nodes
            ),
        },
        prefix="finance_v26_source_verifier_dag:",
    )


def _base_operation_nodes(
    draft: _TaskDraft,
    evidence_to_symbol: Mapping[str, str],
) -> tuple[tuple[PublicOperationNode, ...], tuple[PublicOperationNodeBinding, ...]]:
    source_nodes = tuple(draft.program.nodes)
    public_ids = {
        node.node_id: f"operation_stage_{index:02d}"
        for index, node in enumerate(source_nodes, start=1)
    }
    output_symbols = {
        node.node_id: (
            "terminal_operation_result"
            if node.node_id == draft.program.output_node_id
            else f"intermediate_result_{index:02d}"
        )
        for index, node in enumerate(source_nodes, start=1)
    }
    nodes = []
    bindings = []
    for index, node in enumerate(source_nodes, start=1):
        is_terminal = node.node_id == draft.program.output_node_id
        inputs = []
        for ref in node.input_refs:
            if ref.kind == InputRefKind.EVIDENCE:
                source_symbol = evidence_to_symbol[ref.ref_id]
            else:
                source_symbol = output_symbols[ref.ref_id]
            inputs.append(PublicOperationInput(source_symbol=source_symbol, selector=ref.selector))
        model_choice = draft.mechanism_id == "context_conditioned_action" and index == 1
        if model_choice:
            alternate = "difference" if node.operator_id != "difference" else "compare"
            operators = tuple(sorted((node.operator_id, alternate)))
            schemas = {
                operator: default_registry().require(operator).output_schema
                for operator in operators
            }
        else:
            operators = (node.operator_id,)
            schemas = {}
        dependencies = tuple(sorted(public_ids[value] for value in node.dependencies))
        nodes.append(
            PublicOperationNode(
                node_id=public_ids[node.node_id],
                node_kind="calculation",
                semantic_role=(
                    "terminal_answer_operation"
                    if is_terminal
                    else "context_owned_operation_choice"
                    if model_choice
                    else f"required_calculation_stage_{index:02d}"
                ),
                tool_id="calculator",
                dependency_node_ids=dependencies,
                inputs=tuple(inputs),
                output_symbol=output_symbols[node.node_id],
                allowed_operator_ids=operators,
                operator_choice_mode=(
                    "model_context_choice" if model_choice else "fixed_semantics"
                ),
                operator_selection_rule=(
                    "choose the registered operator whose public output schema matches "
                    "this semantic node's required output schema"
                    if model_choice
                    else None
                ),
                operator_output_schemas=schemas,
                required_output_schema=node.output_schema if model_choice else None,
                parameters=dict(node.parameters),
                terminal=is_terminal,
            )
        )
        bindings.append(
            PublicOperationNodeBinding(
                public_node_id=public_ids[node.node_id],
                source_program_node_id=node.node_id,
                expected_operator_id=node.operator_id,
            )
        )
    return (
        tuple(sorted(nodes, key=lambda item: item.node_id)),
        tuple(sorted(bindings, key=lambda item: item.public_node_id)),
    )


def _reconciliation_operation_nodes(
    draft: _TaskDraft,
    evidence_to_symbol: Mapping[str, str],
) -> tuple[tuple[PublicOperationNode, ...], tuple[PublicOperationNodeBinding, ...]]:
    by_period: defaultdict[str, list[EvidenceItem]] = defaultdict(list)
    for item in draft.public_corpus.evidence:
        by_period[str(item.temporal_context.label)].append(item)
    target_specs = {
        str(item["period"]): dict(item)
        for item in cast(list[dict[str, Any]], draft.mechanism_public_state["target_definitions"])
    }
    normalization_nodes = []
    bindings = []
    for index, period in enumerate(sorted(by_period), start=1):
        target = target_specs[period]
        normalization_target = {
            key: target[key]
            for key in (
                "predicate",
                "definition_id",
                "unit",
                "currency",
                "time_basis",
                "frequency",
            )
        }
        node_id = f"operation_stage_{index:02d}"
        normalization_nodes.append(
            PublicOperationNode(
                node_id=node_id,
                node_kind="normalization",
                semantic_role=f"required_definition_normalization_{index:02d}",
                tool_id="normalize_metric_unit_period",
                inputs=tuple(
                    PublicOperationInput(source_symbol=evidence_to_symbol[item.evidence_id])
                    for item in sorted(by_period[period], key=lambda value: value.evidence_id)
                ),
                output_symbol=f"normalized_reference_{index:02d}",
                operator_choice_mode="not_applicable",
                normalization_target=normalization_target,
            )
        )
        bindings.append(PublicOperationNodeBinding(public_node_id=node_id))
    source_node = draft.program.nodes[0]
    terminal_id = f"operation_stage_{len(normalization_nodes) + 1:02d}"
    terminal = PublicOperationNode(
        node_id=terminal_id,
        node_kind="calculation",
        semantic_role="terminal_answer_operation",
        tool_id="calculator",
        dependency_node_ids=tuple(item.node_id for item in normalization_nodes),
        inputs=tuple(
            PublicOperationInput(
                source_symbol=item.output_symbol,
                selector="normalized_inputs.target",
            )
            for item in normalization_nodes
        ),
        output_symbol="terminal_operation_result",
        allowed_operator_ids=(source_node.operator_id,),
        operator_choice_mode="fixed_semantics",
        parameters=dict(source_node.parameters),
        terminal=True,
    )
    bindings.append(
        PublicOperationNodeBinding(
            public_node_id=terminal_id,
            source_program_node_id=source_node.node_id,
            expected_operator_id=source_node.operator_id,
        )
    )
    return (
        tuple(sorted((*normalization_nodes, terminal), key=lambda item: item.node_id)),
        tuple(sorted(bindings, key=lambda item: item.public_node_id)),
    )


def _operation_contracts(
    draft: _TaskDraft,
    semantic_source_id: str,
) -> tuple[
    PublicOperationExecutionContract,
    PublicStopReadinessContract,
    PublicOperationRuntimeProjection,
    tuple[PublicOperationNodeBinding, ...],
]:
    variables, evidence_to_symbol = _public_variables(draft)
    if draft.mechanism_id == "semantic_reconciliation":
        nodes, bindings = _reconciliation_operation_nodes(draft, evidence_to_symbol)
    else:
        nodes, bindings = _base_operation_nodes(draft, evidence_to_symbol)
    terminal_id = next(item.node_id for item in nodes if item.terminal)
    view_values = {
        "variables": variables,
        "nodes": nodes,
        "terminal_node_id": terminal_id,
    }
    view_provisional = PublicOperationContractView.model_construct(view_id="pending", **view_values)
    view = PublicOperationContractView(
        view_id=public_operation_contract_view_id(view_provisional),
        **view_values,
    )
    operation_values = {
        "semantic_source_id": semantic_source_id,
        "source_program_dag_hash": draft.program.program_hash,
        "source_verifier_dag_hash": _source_verifier_dag_hash(draft.program),
        "public_view": view,
        "public_view_hash": canonical_hash(view, prefix="public_operation_contract_view:"),
    }
    operation_provisional = PublicOperationExecutionContract.model_construct(
        contract_id="pending", **operation_values
    )
    operation = PublicOperationExecutionContract(
        contract_id=public_operation_execution_contract_id(operation_provisional),
        **operation_values,
    )
    stop_values = {
        "semantic_source_id": semantic_source_id,
        "operation_contract_id": operation.contract_id,
        "required_node_ids": tuple(item.node_id for item in nodes),
        "terminal_node_id": terminal_id,
    }
    stop_provisional = PublicStopReadinessContract.model_construct(
        contract_id="pending", **stop_values
    )
    stop = PublicStopReadinessContract(
        contract_id=public_stop_readiness_contract_id(stop_provisional),
        **stop_values,
    )
    projection_values = {
        "operation_contract_id": operation.contract_id,
        "stop_readiness_contract_id": stop.contract_id,
        "visible_progress_fields": tuple(
            sorted(
                (
                    "completed_node_ids",
                    "ready_nodes",
                    "remaining_node_ids",
                    "stop_ready",
                    "terminal_node_completed",
                    "unresolved_variable_requirements",
                    "verification_after_terminal_completed",
                )
            )
        ),
        "hidden_binding_fields": tuple(
            sorted(
                (
                    "evidence_symbol_bindings",
                    "expected_operator_ids",
                    "source_program_node_ids",
                    "verifier_ids",
                )
            )
        ),
    }
    projection_provisional = PublicOperationRuntimeProjection.model_construct(
        projection_id="pending", **projection_values
    )
    projection = PublicOperationRuntimeProjection(
        projection_id=public_operation_runtime_projection_id(projection_provisional),
        **projection_values,
    )
    return operation, stop, projection, bindings


def _answer_observation_constraints(draft: _TaskDraft) -> dict[str, Any]:
    exact_field = next(
        (
            field
            for field in ("value", "difference", "percentage")
            if field in draft.projected_expected_output
        ),
        None,
    )
    if exact_field is None:
        raise ValueError("v26.60 terminal output lacks a scalar answer field")
    return {
        "source_tool_id": "calculator",
        "source_operation_role": "terminal",
        "source_result_selector": ("result", "output"),
        "field_selectors": {exact_field: (exact_field,)},
        "exact_fields": (exact_field,),
    }


def _upgrade_task(
    draft: _TaskDraft,
) -> tuple[OperationalTaskRecord, AgentToolEnvironmentManifest]:
    base_record, environment = _materialize_task(draft)
    base = base_record.task_package
    operation, stop, runtime_projection, node_bindings = _operation_contracts(
        draft,
        base.semantic_source.semantic_source_id,
    )
    verifier_values = {
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "answer_projection_contract_id": base.answer_projection.contract_id,
        "evidence_support_lattice_id": base.evidence_support_lattice.lattice_id,
        "citation_contract_id": base.citation_contract.contract_id,
        "public_runtime_contract_id": base.public_runtime_contract.contract_id,
        "mechanism_contract_id": base.mechanism_contract.contract_id,
        "operation_contract_id": operation.contract_id,
        "stop_readiness_contract_id": stop.contract_id,
        "runtime_projection_id": runtime_projection.projection_id,
        "source_program_dag_hash": operation.source_program_dag_hash,
        "source_verifier_dag_hash": operation.source_verifier_dag_hash,
        "node_bindings": node_bindings,
        "verifier_implementation_id": V26_OPERATIONAL_VERIFIER_ID,
        "verifier_version": V26_OPERATIONAL_VERIFIER_VERSION,
        "exact_gold_equality_required": base.evidence_support_lattice.exact_equality_required,
    }
    verifier_provisional = OperationalExecutableVerifierBinding.model_construct(
        binding_id="pending", **verifier_values
    )
    verifier = OperationalExecutableVerifierBinding(
        binding_id=operational_executable_verifier_binding_id(verifier_provisional),
        **verifier_values,
    )
    public_bindings = {
        "answer_projection_contract_id": base.answer_projection.contract_id,
        "citation_contract_id": base.citation_contract.contract_id,
        "intended_use": draft.intended_use,
        "operation_contract_id": operation.contract_id,
        "public_runtime_contract_id": base.public_runtime_contract.contract_id,
        "runtime_projection_id": runtime_projection.projection_id,
        "stop_readiness_contract_id": stop.contract_id,
        "tool_closure_contract_id": base.tool_closure.closure_id,
    }
    oracle_bindings = {
        **public_bindings,
        "evidence_support_lattice_id": base.evidence_support_lattice.lattice_id,
        "mechanism_contract_id": base.mechanism_contract.contract_id,
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "verifier_binding_id": verifier.binding_id,
    }
    metadata = dict(base.task.public.metadata)
    metadata.pop("agent_contract_guidance", None)
    metadata["executable_support_bindings"] = public_bindings
    metadata["agent_contract_guidance"] = {
        "public_operation_execution_contract": operation.public_view.model_dump(mode="json"),
        "public_stop_readiness_contract": stop.model_dump(mode="json"),
        "answer_observation_constraints": _answer_observation_constraints(draft),
    }
    public_template = base.task.public.model_copy(
        update={"task_id": "pending", "metadata": metadata}
    )
    selection_contract = dict(base.task.oracle.selection_contract)
    selection_contract["executable_support_bindings"] = oracle_bindings
    oracle_template = base.task.oracle.model_copy(
        update={"task_id": "pending", "selection_contract": selection_contract}
    )
    task_template = TaskPackage(
        task_id="pending",
        public=public_template,
        oracle=oracle_template,
    )
    package_values = {
        "semantic_source": base.semantic_source,
        "task": task_template,
        "tool_closure": base.tool_closure,
        "answer_projection": base.answer_projection,
        "evidence_support_lattice": base.evidence_support_lattice,
        "citation_contract": base.citation_contract,
        "public_runtime_contract": base.public_runtime_contract,
        "mechanism_contract": base.mechanism_contract,
        "operation_contract": operation,
        "stop_readiness_contract": stop,
        "runtime_projection": runtime_projection,
        "verifier_binding": verifier,
        "schema_version": OPERATIONAL_EXECUTABLE_TASK_PACKAGE_VERSION,
    }
    provisional = OperationalExecutableTaskPackage.model_construct(
        package_id="pending", **package_values
    )
    package_id = operational_executable_task_package_id(provisional)
    task = TaskPackage(
        task_id=package_id,
        public=public_template.model_copy(update={"task_id": package_id}),
        oracle=oracle_template.model_copy(update={"task_id": package_id}),
    )
    package = OperationalExecutableTaskPackage(
        package_id=package_id,
        **{**package_values, "task": task},
    )
    record_values = {
        "mechanism_id": draft.mechanism_id,
        "intended_use": draft.intended_use,
        "source_task_artifact_ids": tuple(sorted(draft.source_task_artifact_ids)),
        "task_package": package,
        "evidence_bundle": draft.evidence_bundle,
        "public_corpus": draft.public_corpus,
        "proof_graph": draft.proof_graph,
        "projected_expected_output": draft.projected_expected_output,
        "answer_projection": draft.answer_projection,
        "mechanism_public_state": draft.mechanism_public_state,
        "mechanism_private_state": draft.mechanism_private_state,
        "recovery_scenario": base_record.recovery_scenario,
        "target_program_evidence_ids": draft.target_program_evidence_ids,
        "environment_manifest_id": environment.manifest_id,
        "environment_manifest_hash": base.public_runtime_contract.environment_manifest_hash,
        "schema_version": V26_PUBLIC_OPERATION_REMATERIALIZATION_VERSION,
    }
    record_provisional = OperationalTaskRecord.model_construct(record_id="pending", **record_values)
    record = OperationalTaskRecord(
        record_id=operational_task_record_id(record_provisional),
        **record_values,
    )
    return record, environment
