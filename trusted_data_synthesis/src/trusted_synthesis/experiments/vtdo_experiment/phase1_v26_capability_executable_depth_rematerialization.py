from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.operations.program import (
    ProgramVerification,
    TaskProgramExecutor,
    TaskProgramOracleVerifier,
)
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.answer_schema import complete_answer_schema
from trusted_synthesis.core.task.capability_observation import (
    CAPABILITY_FAMILY_ORDER,
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
    ObservationPartition,
)
from trusted_synthesis.core.task.executable_capability_depth import (
    EXECUTABLE_DEPTH_SLOT_IDS,
    BoundarySelectionAlgorithmContract,
    CapabilityDepthVerifierContract,
    CapabilityDepthWitnessContract,
    CompiledNuisanceMeasurement,
    DepthActionKind,
    DepthPromptBinding,
    DepthTransitionStatus,
    ExecutableCapabilityDepthGraph,
    ExecutableDepthCandidate,
    ExecutableDepthSignature,
    ExecutableDepthState,
    ExecutableDepthTransition,
    ObservabilityFloorNuisanceEnvelope,
    classify_capability_boundary,
)
from trusted_synthesis.core.task.program import InputRefKind, make_program
from trusted_synthesis.core.task.schema import TaskRequirement
from trusted_synthesis.core.trajectory.executable_task import BoundPublicExecutableWitness
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_breadth_depth_task_synthesis as v167,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_breadth_depth_task_synthesis_models as v167_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_static_audit as static_audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_role_kernel_compatibility_preflight as source_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_role_kernel_scalability_design as role_compiler,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    _project_answer,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FreshFrequencySourcePopulation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_witness import (
    compile_operational_witness,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_168_executable_depth_rematerialization_v2_20260828"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_168_executable_depth_rematerialization_v2_20260828"
)
SEALED_OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_168_sealed_confirmation_executable_depth_v2_20260828"
)
EXPECTED_REVIEW_SHA256: Final = "89ed58d566df56edc1dc54087cb722dc5a485ee48068a543aa15d79850a10dbb"
EXPECTED_REVIEW_BYTE_COUNT: Final = 25_940
AUTHORIZED_STAGE: Final = (
    "capability_observation_executable_depth_rematerialization_and_static_reaudit_only"
)
SOURCE_SELECTION_SALT: Final = "finance-v26.168-low-nuisance-source-selection-v1"
RESOURCE_TOKEN_CEILING: Final = 1_120_000
V167_DIR: Final = v167.OUTPUT_DIR
V163_DIR: Final = v167.V163_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/executable_capability_depth.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_executable_depth_rematerialization_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_executable_depth_static_audit.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_executable_depth_rematerialization.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.168 cannot resolve the trusted_data_synthesis package root")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _write(path: Path, value: Any) -> None:
    if path.exists():
        raise ValueError(f"v26.168 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.168 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: models.identity(provisional, field, prefix)}, **values)


def _authorization(path: Path) -> models.ExternalAuditAuthorization:
    if _sha256(path) != EXPECTED_REVIEW_SHA256 or path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.168 external audit input binding changed")
    values = {
        "review_sha256": EXPECTED_REVIEW_SHA256,
        "authorized_stage": AUTHORIZED_STAGE,
    }
    return cast(
        models.ExternalAuditAuthorization,
        _make_model(
            models.ExternalAuditAuthorization,
            values,
            field="authorization_id",
            prefix="finance_v26_executable_depth_external_audit_authorization:",
        ),
    )


def _module_name(relative_path: str) -> str:
    path = Path(relative_path)
    parts = path.with_suffix("").parts
    if "src" not in parts:
        raise ValueError(f"source path is outside src:{relative_path}")
    index = parts.index("src") + 1
    module_parts = list(parts[index:])
    if module_parts[-1] == "__init__":
        module_parts.pop()
    return ".".join(module_parts)


def _module_path(package_root: Path, module: str) -> Path | None:
    base = package_root / "src" / Path(*module.split("."))
    direct = base.with_suffix(".py")
    package = base / "__init__.py"
    if direct.is_file():
        return direct
    if package.is_file():
        return package
    return None


def _imported_modules(package_root: Path, path: Path) -> tuple[str, ...]:
    relative = str(path.relative_to(package_root))
    current = _module_name(relative)
    current_package = current.rsplit(".", 1)[0] if path.name != "__init__.py" else current
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    output: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            output.update(
                item.name for item in node.names if item.name.startswith("trusted_synthesis")
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = current_package.split(".") if current_package else []
                if node.level > len(parts):
                    continue
                prefix = parts[: len(parts) - node.level + 1]
                if node.module:
                    prefix.extend(node.module.split("."))
                base = ".".join(prefix)
            else:
                base = node.module or ""
            if not base.startswith("trusted_synthesis"):
                continue
            output.add(base)
            for alias in node.names:
                candidate = f"{base}.{alias.name}"
                if _module_path(package_root, candidate) is not None:
                    output.add(candidate)
    return tuple(sorted(output))


def _transitive_source_root(package_root: Path) -> models.TransitiveSourceRoot:
    pending = [_module_name(path) for path in ENTRY_SOURCE_PATHS]
    visited: set[str] = set()
    paths: dict[str, Path] = {}
    unresolved: set[str] = set()
    while pending:
        module = pending.pop()
        if module in visited:
            continue
        visited.add(module)
        path = _module_path(package_root, module)
        if path is None:
            unresolved.add(module)
            continue
        relative = str(path.relative_to(package_root))
        paths[relative] = path
        pending.extend(
            item for item in _imported_modules(package_root, path) if item not in visited
        )
    if unresolved:
        raise ValueError(f"v26.168 unresolved trusted_synthesis imports:{sorted(unresolved)}")
    files = tuple(
        models.FileBinding(
            relative_path=relative,
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
            source_kind="transitive_source",
        )
        for relative, path in sorted(paths.items())
    )
    values = {
        "entry_modules": tuple(sorted(_module_name(path) for path in ENTRY_SOURCE_PATHS)),
        "files": files,
        "file_count": len(files),
    }
    return cast(
        models.TransitiveSourceRoot,
        _make_model(
            models.TransitiveSourceRoot,
            values,
            field="root_id",
            prefix="finance_v26_executable_depth_transitive_source_root:",
        ),
    )


def _file_binding(
    package_root: Path,
    relative_path: str,
    source_kind: str,
) -> models.FileBinding:
    path = package_root / relative_path
    if not path.is_file():
        raise ValueError(f"v26.168 bound file is missing:{relative_path}")
    return models.FileBinding(
        relative_path=relative_path,
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
        source_kind=cast(Any, source_kind),
    )


def _source_replay(
    *,
    package_root: Path,
    authorization: models.ExternalAuditAuthorization,
    source_root: models.TransitiveSourceRoot,
    v167_report: v167_models.CapabilityBreadthDepthStaticAuditReport,
) -> models.SourceReplayAudit:
    bindings = [
        models.FileBinding(
            relative_path="external_joint_audit_input.txt",
            sha256=authorization.review_sha256,
            byte_count=authorization.review_byte_count,
            source_kind="external_audit_input",
        )
    ]
    bindings.extend(
        _file_binding(package_root, path, "implementation") for path in ENTRY_SOURCE_PATHS
    )
    bindings.extend(
        _file_binding(package_root, f"{V167_DIR}/{path.name}", "v26_167_frozen_output")
        for path in sorted((package_root / V167_DIR).iterdir())
        if path.is_file()
    )
    for path in (
        v167.SOURCE_FRAME_PATH,
        v167.PRIOR_SOURCE_POPULATION_PATH,
        v167.V163_SOURCE_SELECTION_AUDIT_PATH,
    ):
        bindings.append(_file_binding(package_root, path, "v26_163_frozen_source"))
    values = {
        "authorization_id": authorization.authorization_id,
        "v26_167_report_id": v167_report.report_id,
        "transitive_source_root_id": source_root.root_id,
        "bindings": tuple(sorted(bindings, key=lambda item: item.relative_path)),
    }
    return cast(
        models.SourceReplayAudit,
        _make_model(
            models.SourceReplayAudit,
            values,
            field="audit_id",
            prefix="finance_v26_executable_depth_source_replay:",
        ),
    )


def _source_channels(task: CapabilitySensitiveTaskArtifact) -> dict[str, tuple[str, ...]]:
    values = source_base._source_task_channels((task,))  # noqa: SLF001
    return {key: tuple(sorted(item)) for key, item in values.items()}


def _source_rank(family: CapabilityFamily, task: CapabilitySensitiveTaskArtifact) -> str:
    return hashlib.sha256(
        f"{SOURCE_SELECTION_SALT}|{family.value}|{task.artifact_id}".encode()
    ).hexdigest()


def _select_sources(
    package_root: Path,
) -> tuple[
    models.ExecutableDepthSourceCapacityAudit,
    dict[str, CapabilitySensitiveTaskArtifact],
]:
    frame = CapabilitySensitiveFrontierPopulation.model_validate(
        _load(package_root / v167.SOURCE_FRAME_PATH)
    )
    prior = FreshFrequencySourcePopulation.model_validate(
        _load(package_root / v167.PRIOR_SOURCE_POPULATION_PATH)
    )
    prior_ids = {item.source_task_artifact_id for item in prior.tasks}
    prior_channels = source_base._source_task_channels(  # noqa: SLF001
        tuple(item.source_task for item in prior.tasks)
    )
    selected: list[models.ExecutableDepthSourceBinding] = []
    selected_tasks: dict[str, CapabilitySensitiveTaskArtifact] = {}
    selected_channels: dict[str, set[str]] = {key: set() for key in source_base.FRESHNESS_CHANNELS}
    eligible_counts: dict[CapabilityFamily, int] = {}
    for family in CAPABILITY_FAMILY_ORDER:
        eligible = []
        for task in frame.tasks:
            if task.family != v167.FAMILY_SOURCE_MAP[family] or task.artifact_id in prior_ids:
                continue
            candidate_channels = source_base._source_task_channels((task,))  # noqa: SLF001
            if any(
                candidate_channels[channel] & prior_channels[channel]
                for channel in source_base.FRESHNESS_CHANNELS
            ):
                continue
            eligible.append(task)
        eligible_counts[family] = len(eligible)
        easy = sorted(
            (item for item in eligible if item.tier.value == "easy_control"),
            key=lambda item: _source_rank(family, item),
        )
        frontier = sorted(
            (item for item in eligible if item.tier.value == "frontier"),
            key=lambda item: _source_rank(family, item),
        )
        if len(easy) < 2 or len(frontier) < 2:
            raise ValueError(f"v26.168 low-nuisance capacity failed:{family.value}")
        chosen = (*easy[:2], *frontier[:2])
        for index, task in enumerate(chosen, start=1):
            source_node = task.task.oracle.task_program.nodes[0]
            if any(item.kind != InputRefKind.EVIDENCE for item in source_node.input_refs):
                raise ValueError("v26.168 selected core first node is not Evidence-only")
            evidence_ids = tuple(sorted(item.ref_id for item in source_node.input_refs))
            if len(evidence_ids) != 2:
                raise ValueError("v26.168 selected core does not use exactly two Evidence rows")
            evidence_by_id = {item.evidence_id: item for item in task.evidence_bundle.evidence}
            evidence = tuple(evidence_by_id[item] for item in evidence_ids)
            task_channels = _source_channels(task)
            for channel in source_base.FRESHNESS_CHANNELS:
                overlap = set(task_channels[channel]) & selected_channels[channel]
                if overlap:
                    raise ValueError(
                        f"v26.168 selected groups overlap on {channel}:{sorted(overlap)}"
                    )
                selected_channels[channel].update(task_channels[channel])
            partition = (
                ObservationPartition.DEVELOPMENT
                if index <= 2
                else ObservationPartition.CONFIRMATION
            )
            values = {
                "capability_family": family,
                "group_index": index,
                "partition": partition,
                "source_task_artifact_id": task.artifact_id,
                "source_task_id": task.task.task_id,
                "historical_tier": task.tier.value,
                "source_evidence_count": len(task.public_corpus.evidence),
                "source_program_node_count": len(task.task.oracle.task_program.nodes),
                "selected_core_evidence_ids": evidence_ids,
                "selected_core_evidence_version_ids": tuple(
                    sorted(item.evidence_version_id for item in evidence)
                ),
                "selected_core_source_record_ids": tuple(
                    sorted({item.provenance.source_record_id for item in evidence})
                ),
                "source_core_semantic_signature": next(iter(task_channels["core_semantic_signature"])),
                "source_mechanism_instance_signature": next(
                    iter(task_channels["mechanism_instance_signature"])
                ),
                "selection_rank": _source_rank(family, task),
            }
            binding = cast(
                models.ExecutableDepthSourceBinding,
                _make_model(
                    models.ExecutableDepthSourceBinding,
                    values,
                    field="binding_id",
                    prefix="finance_v26_executable_depth_source_binding:",
                ),
            )
            selected.append(binding)
            selected_tasks[binding.binding_id] = task
    values = {
        "source_frame_population_id": frame.population_id,
        "prior_exposed_population_id": prior.population_id,
        "eligible_count_by_capability": eligible_counts,
        "selected": tuple(selected),
    }
    audit = cast(
        models.ExecutableDepthSourceCapacityAudit,
        _make_model(
            models.ExecutableDepthSourceCapacityAudit,
            values,
            field="audit_id",
            prefix="finance_v26_executable_depth_source_capacity_audit:",
        ),
    )
    return audit, selected_tasks


def _v167_defect_audit(
    package_root: Path,
    report: v167_models.CapabilityBreadthDepthStaticAuditReport,
) -> models.V167ExecutableDepthDefectAudit:
    _, _, selected, selected_tasks, _, _ = v167._select_fresh_sources(  # noqa: SLF001
        package_root=package_root
    )
    rows = []
    for binding in selected:
        task = selected_tasks[binding.binding_id]
        draft = role_compiler._role_draft(  # noqa: SLF001
            task,
            role="capability",
            mechanism=cast(Any, binding.capability_family.value),
        )
        record, environment = role_compiler._upgrade_role_task(draft)  # noqa: SLF001
        witness, _ = compile_operational_witness(
            record,
            environment,
            strategy="structured_direct",
        )
        rows.append(
            models.V167ExecutableDefectRow(
                source_task_artifact_id=task.artifact_id,
                capability_family=binding.capability_family,
                group_index=binding.group_index,
                historical_tier=task.tier.value,
                source_evidence_count=len(task.public_corpus.evidence),
                source_program_node_count=len(task.task.oracle.task_program.nodes),
                actual_operational_witness_passed=witness.full_validity_passed,
                actual_failure_reasons=witness.failure_reasons,
            )
        )
    values = {
        "v26_167_report_id": report.report_id,
        "rows": tuple(rows),
    }
    return cast(
        models.V167ExecutableDepthDefectAudit,
        _make_model(
            models.V167ExecutableDepthDefectAudit,
            values,
            field="audit_id",
            prefix="finance_v26_v167_executable_depth_defect_audit:",
        ),
    )


def _low_nuisance_draft(
    task: CapabilitySensitiveTaskArtifact,
    family: CapabilityFamily,
) -> tuple[Any, str]:
    source_node = task.task.oracle.task_program.nodes[0]
    if any(item.kind != InputRefKind.EVIDENCE for item in source_node.input_refs):
        raise ValueError("low-nuisance core first node is not Evidence-only")
    evidence_ids = tuple(sorted(item.ref_id for item in source_node.input_refs))
    evidence_by_id = {item.evidence_id: item for item in task.evidence_bundle.evidence}
    evidence = tuple(evidence_by_id[item] for item in evidence_ids)
    bundle = EvidenceBundle(
        bundle_id=canonical_hash(
            {
                "source_task_artifact_id": task.artifact_id,
                "evidence_version_ids": tuple(item.evidence_version_id for item in evidence),
            },
            prefix="finance_v26_168_low_nuisance_bundle:",
        ),
        evidence=evidence,
        purpose="v26.168 executable capability depth low-nuisance core",
        graph_build_id=task.evidence_bundle.graph_build_id,
        metadata={"source_task_artifact_id": task.artifact_id},
    )
    corpus = EvidenceCorpus.from_bundle(bundle)
    graph = ProofGraphBuilder().build(bundle)
    program = make_program((source_node,), source_node.node_id)
    execution = TaskProgramExecutor(default_registry()).execute(program, evidence_by_id)
    verification = TaskProgramOracleVerifier(default_registry()).verify(
        program,
        evidence_by_id,
        execution.node_outputs,
    )
    if not verification.passed:
        raise ValueError("low-nuisance Finance core failed independent TaskProgram replay")
    projected = _project_answer(execution.final_output, task.answer_projection)
    base = role_compiler._role_draft(  # noqa: SLF001
        task,
        role="capability",
        mechanism=cast(Any, family.value),
    )
    public_state = dict(base.mechanism_public_state)
    if family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        periods = {str(item.temporal_context.label) for item in evidence}
        public_state["target_definitions"] = [
            item
            for item in cast(list[dict[str, Any]], public_state["target_definitions"])
            if str(item["period"]) in periods
        ]
    scope = dict(base.retrieval_scope)
    scope["aliases"] = sorted(
        {
            value
            for item in evidence
            for value in (item.subject.name, item.subject.subject_id, item.predicate)
        }
    )
    scope["corpus_boundary"] = {
        **dict(scope["corpus_boundary"]),
        "evidence_count": 2,
        "source_count": len({item.source.source_id for item in evidence}),
    }
    scope["partial_constraints"] = {
        **dict(scope["partial_constraints"]),
        "period_labels": sorted({str(item.temporal_context.label) for item in evidence}),
        "required_source_count": len({item.source.source_id for item in evidence}),
    }
    draft = replace(
        base,
        instruction=(
            "Execute the fixed two-Evidence, one-Operation Finance core and return its exact "
            "public result after verification."
        ),
        evidence_bundle=bundle,
        public_corpus=corpus,
        proof_graph=graph,
        program=program,
        projected_expected_output=projected,
        answer_projection=dict(task.answer_projection),
        answer_schema=complete_answer_schema(
            {
                "type": "capability_sensitive_numeric",
                "required_fields": sorted(projected),
                "allow_claims": False,
                "additional_result_properties": False,
            }
        ),
        retrieval_scope=scope,
        requirements=(
            TaskRequirement.RETRIEVE_EVIDENCE,
            TaskRequirement.SELECT_EVIDENCE,
            TaskRequirement.CALCULATE,
            TaskRequirement.CITE_SOURCE,
            TaskRequirement.VERIFY_RESULT,
        ),
        mechanism_public_state=public_state,
        target_program_evidence_ids=evidence_ids,
    )
    return draft, source_node.node_id


def _finance_core(
    binding: models.ExecutableDepthSourceBinding,
    task: CapabilitySensitiveTaskArtifact,
) -> models.LowNuisanceFinanceCore:
    draft, source_node_id = _low_nuisance_draft(task, binding.capability_family)
    record, environment = role_compiler._upgrade_role_task(draft)  # noqa: SLF001
    witness, _ = compile_operational_witness(
        record,
        environment,
        strategy="structured_direct",
    )
    evidence_by_id = {item.evidence_id: item for item in record.evidence_bundle.evidence}
    independent = TaskProgramOracleVerifier(default_registry()).verify(
        record.task_package.task.oracle.task_program,
        evidence_by_id,
        TaskProgramExecutor(default_registry())
        .execute(record.task_package.task.oracle.task_program, evidence_by_id)
        .node_outputs,
    )
    if not witness.full_validity_passed or not independent.passed:
        raise ValueError("v26.168 low-nuisance core lacks full public or task validity")
    values = {
        "source_binding_id": binding.binding_id,
        "capability_family": binding.capability_family,
        "partition": binding.partition,
        "source_task_artifact_id": task.artifact_id,
        "source_program_node_id": source_node_id,
        "operational_record": record,
        "environment": environment,
        "operational_witness": witness,
    }
    return cast(
        models.LowNuisanceFinanceCore,
        _make_model(
            models.LowNuisanceFinanceCore,
            values,
            field="core_id",
            prefix="finance_v26_low_nuisance_finance_core:",
        ),
    )


@dataclass(frozen=True)
class _CandidatePlan:
    action_kind: DepthActionKind
    semantic_role: str
    reference: bool
    target: bool
    status: DepthTransitionStatus = DepthTransitionStatus.SUCCEEDED
    failure_code: str | None = None
    events: tuple[str, ...] = ()
    emitted_refs: tuple[str, ...] = ()
    consumed_refs: tuple[str, ...] = ()
    axes: tuple[str, ...] = ()
    failure_type: str | None = None
    delayed: bool = False


@dataclass(frozen=True)
class _StatePlan:
    slot_id: str
    phase: str
    public_state: dict[str, Any]
    candidates: tuple[_CandidatePlan, ...]


def _reference_plan(
    action_kind: DepthActionKind,
    semantic_role: str,
    *,
    events: tuple[str, ...] = (),
    emitted_refs: tuple[str, ...] = (),
    consumed_refs: tuple[str, ...] = (),
    axes: tuple[str, ...] = (),
    failure_type: str | None = None,
    status: DepthTransitionStatus = DepthTransitionStatus.SUCCEEDED,
    failure_code: str | None = None,
    delayed: bool = False,
) -> _CandidatePlan:
    return _CandidatePlan(
        action_kind=action_kind,
        semantic_role=semantic_role,
        reference=True,
        target=True,
        status=status,
        failure_code=failure_code,
        events=events,
        emitted_refs=emitted_refs,
        consumed_refs=consumed_refs,
        axes=axes,
        failure_type=failure_type,
        delayed=delayed,
    )


def _bypass_plan(kind: DepthActionKind, semantic_role: str) -> _CandidatePlan:
    return _CandidatePlan(
        action_kind=kind,
        semantic_role=semantic_role,
        reference=False,
        target=True,
        status=DepthTransitionStatus.REJECTED,
    )


def _inert_plan(slot_id: str) -> _StatePlan:
    return _StatePlan(
        slot_id=slot_id,
        phase="inert",
        public_state={
            "active": False,
            "slot_id": slot_id,
            "unique_legal_action": True,
        },
        candidates=(
            _CandidatePlan(
                action_kind=DepthActionKind.INERT_ADVANCE,
                semantic_role=f"advance_inert_{slot_id}",
                reference=True,
                target=False,
            ),
        ),
    )


def _context_plans(depth: ObservationDepth) -> tuple[_StatePlan, ...]:
    active_count = {
        depth_value: count
        for depth_value, count in zip(OBSERVATION_DEPTH_ORDER, (1, 1, 2, 3), strict=True)
    }[depth]
    candidate_counts = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (2, 1, 1),
        ObservationDepth.D1_BASIC: (3, 1, 1),
        ObservationDepth.D2_COMPOSITIONAL: (3, 2, 1),
        ObservationDepth.D3_STRESS: (4, 3, 2),
    }[depth]
    output = []
    for index, slot_id in enumerate(EXECUTABLE_DEPTH_SLOT_IDS, start=1):
        if index > active_count:
            output.append(_inert_plan(slot_id))
            continue
        events = ["context_action_selected"]
        if depth != ObservationDepth.D0_OBSERVABILITY_ANCHOR and index == active_count:
            events.append("context_irreversible_choice")
        candidates = [
            _reference_plan(
                DepthActionKind.CONTEXT_SELECT,
                f"select_context_action_{index:02d}",
                events=tuple(sorted(events)),
                delayed=index > 1,
            )
        ]
        candidates.extend(
            _bypass_plan(
                DepthActionKind.TARGET_BYPASS,
                f"select_context_bypass_{index:02d}_{alternate:02d}",
            )
            for alternate in range(1, candidate_counts[index - 1])
        )
        output.append(
            _StatePlan(
                slot_id=slot_id,
                phase="context_decision",
                public_state={
                    "active": True,
                    "context_sensitive": True,
                    "candidate_count": len(candidates),
                    "depends_on_slot": (
                        EXECUTABLE_DEPTH_SLOT_IDS[index - 2] if index > 1 else None
                    ),
                },
                candidates=tuple(candidates),
            )
        )
    return tuple(output)


def _reconciliation_plans(depth: ObservationDepth) -> tuple[_StatePlan, ...]:
    active_count = dict(zip(OBSERVATION_DEPTH_ORDER, (1, 1, 2, 3), strict=True))[depth]
    axes_by_depth = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (("definition",), (), ()),
        ObservationDepth.D1_BASIC: (("definition", "period"), (), ()),
        ObservationDepth.D2_COMPOSITIONAL: (("definition", "period"), ("unit",), ()),
        ObservationDepth.D3_STRESS: (
            ("definition", "period"),
            ("currency", "unit"),
            ("frequency", "time_basis"),
        ),
    }[depth]
    fanout_by_depth = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (1, 0, 0),
        ObservationDepth.D1_BASIC: (2, 0, 0),
        ObservationDepth.D2_COMPOSITIONAL: (2, 1, 0),
        ObservationDepth.D3_STRESS: (2, 2, 2),
    }[depth]
    output = []
    for index, slot_id in enumerate(EXECUTABLE_DEPTH_SLOT_IDS, start=1):
        if index > active_count:
            output.append(_inert_plan(slot_id))
            continue
        reference_id = f"normalized_ref_{slot_id}"
        axes = tuple(sorted(axes_by_depth[index - 1]))
        output.append(
            _StatePlan(
                slot_id=slot_id,
                phase="normalize",
                public_state={
                    "active": True,
                    "nonidentity_axes": axes,
                    "raw_bypass_visible": True,
                },
                candidates=(
                    _reference_plan(
                        DepthActionKind.NORMALIZE_REFERENCE,
                        f"normalize_{slot_id}",
                        events=("normalization_reference_emitted",),
                        emitted_refs=(reference_id,),
                        axes=axes,
                    ),
                    _bypass_plan(DepthActionKind.TARGET_BYPASS, f"raw_bypass_{slot_id}"),
                ),
            )
        )
        for consumer in range(1, fanout_by_depth[index - 1] + 1):
            output.append(
                _StatePlan(
                    slot_id=slot_id,
                    phase="consume_normalized_reference",
                    public_state={
                        "active": True,
                        "consumer_index": consumer,
                        "required_reference_id": reference_id,
                    },
                    candidates=(
                        _reference_plan(
                            DepthActionKind.CONSUME_NORMALIZED_REFERENCE,
                            f"consume_{slot_id}_{consumer:02d}",
                            events=("normalization_reference_consumed",),
                            consumed_refs=(reference_id,),
                        ),
                        _bypass_plan(
                            DepthActionKind.TARGET_BYPASS,
                            f"skip_normalized_consumer_{slot_id}_{consumer:02d}",
                        ),
                    ),
                )
            )
    return tuple(output)


def _recovery_plans(depth: ObservationDepth) -> tuple[_StatePlan, ...]:
    active_count = dict(zip(OBSERVATION_DEPTH_ORDER, (1, 1, 2, 3), strict=True))[depth]
    recovery_alternates = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: 1,
        ObservationDepth.D1_BASIC: 2,
        ObservationDepth.D2_COMPOSITIONAL: 2,
        ObservationDepth.D3_STRESS: 3,
    }[depth]
    failure_types = (
        "typed_selector_requires_refinement",
        "typed_definition_mismatch",
        "typed_dependency_not_ready",
    )
    output = []
    for index, slot_id in enumerate(EXECUTABLE_DEPTH_SLOT_IDS, start=1):
        if index > active_count:
            output.append(_inert_plan(slot_id))
            continue
        failure_type = failure_types[index - 1]
        output.append(
            _StatePlan(
                slot_id=slot_id,
                phase="trigger_failure",
                public_state={"active": True, "registered_failure_type": failure_type},
                candidates=(
                    _reference_plan(
                        DepthActionKind.TRIGGER_TYPED_FAILURE,
                        f"trigger_{slot_id}",
                        events=("typed_failure_observed",),
                        failure_type=failure_type,
                        status=DepthTransitionStatus.TYPED_FAILURE,
                        failure_code=failure_type,
                    ),
                    _bypass_plan(DepthActionKind.TARGET_BYPASS, f"avoid_failure_{slot_id}"),
                ),
            )
        )
        candidates = [
            _reference_plan(
                DepthActionKind.REVISE_AFTER_FAILURE,
                f"revise_{slot_id}",
                events=("recovery_succeeded", "selector_revised"),
            )
        ]
        candidates.extend(
            _bypass_plan(
                DepthActionKind.TARGET_BYPASS,
                f"invalid_retry_{slot_id}_{alternate:02d}",
            )
            for alternate in range(1, recovery_alternates + 1)
        )
        output.append(
            _StatePlan(
                slot_id=slot_id,
                phase="recover",
                public_state={
                    "active": True,
                    "failure_type": failure_type,
                    "revision_candidate_count": len(candidates),
                },
                candidates=tuple(candidates),
            )
        )
    return tuple(output)


def _stopping_plans(depth: ObservationDepth) -> tuple[_StatePlan, ...]:
    active_count = dict(zip(OBSERVATION_DEPTH_ORDER, (1, 1, 2, 3), strict=True))[depth]
    active_slots = set(EXECUTABLE_DEPTH_SLOT_IDS[-active_count:])
    output = []
    for slot_id in EXECUTABLE_DEPTH_SLOT_IDS:
        if slot_id not in active_slots:
            output.append(_inert_plan(slot_id))
            continue
        is_final = slot_id == EXECUTABLE_DEPTH_SLOT_IDS[-1]
        events = ["completion_predicate_evaluated", "near_terminal_checkpoint_reached"]
        delayed = depth != ObservationDepth.D0_OBSERVABILITY_ANCHOR and not (
            active_count > 1 and is_final
        )
        if delayed:
            events.append("readiness_delayed")
        if is_final:
            events.append("completion_verified")
        candidate_count = 3 if depth != ObservationDepth.D0_OBSERVABILITY_ANCHOR else 2
        candidates = [
            _reference_plan(
                (
                    DepthActionKind.VERIFY_COMPLETION
                    if is_final
                    else DepthActionKind.ADVANCE_CHECKPOINT
                ),
                f"checkpoint_reference_{slot_id}",
                events=tuple(sorted(events)),
                delayed=delayed,
            )
        ]
        candidates.extend(
            _bypass_plan(
                DepthActionKind.TEMPTING_CONTINUATION,
                f"tempting_continuation_{slot_id}_{alternate:02d}",
            )
            for alternate in range(1, candidate_count)
        )
        output.append(
            _StatePlan(
                slot_id=slot_id,
                phase="checkpoint",
                public_state={
                    "active": True,
                    "completion_predicate_visible": True,
                    "tempting_continuation_count": candidate_count - 1,
                    "terminal_checkpoint": is_final,
                },
                candidates=tuple(candidates),
            )
        )
    output.append(
        _StatePlan(
            slot_id=EXECUTABLE_DEPTH_SLOT_IDS[-1],
            phase="verified_stop",
            public_state={
                "active": True,
                "completion_verified": True,
                "postcompletion_action_forbidden": True,
            },
            candidates=(
                _reference_plan(
                    DepthActionKind.STOP_AFTER_COMPLETION,
                    "stop_after_verified_completion",
                    events=("stopped_after_completion",),
                ),
                _bypass_plan(
                    DepthActionKind.TEMPTING_CONTINUATION,
                    "postcompletion_tempting_continuation",
                ),
            ),
        )
    )
    return tuple(output)


def _plans(family: CapabilityFamily, depth: ObservationDepth) -> tuple[_StatePlan, ...]:
    return {
        CapabilityFamily.CONTEXT_CONDITIONED_ACTION: _context_plans,
        CapabilityFamily.SEMANTIC_RECONCILIATION: _reconciliation_plans,
        CapabilityFamily.FAILURE_RECOVERY: _recovery_plans,
        CapabilityFamily.STATE_DEPENDENT_STOPPING: _stopping_plans,
    }[family](depth)


def _state_id(values: dict[str, Any]) -> str:
    provisional = ExecutableDepthState.model_construct(
        state_id="pending",
        candidate_ids=(),
        reference_candidate_id=None,
        **values,
    )
    payload = provisional.model_dump(
        mode="json",
        exclude={"state_id", "candidate_ids", "reference_candidate_id"},
    )
    return canonical_hash(payload, prefix="executable_capability_depth_state:")


def _graph(
    *,
    package_id: str,
    core: models.LowNuisanceFinanceCore,
    family: CapabilityFamily,
    depth: ObservationDepth,
) -> ExecutableCapabilityDepthGraph:
    plans = _plans(family, depth)
    active_slots = tuple(
        sorted({plan.slot_id for plan in plans if bool(plan.public_state.get("active"))})
    )
    state_base: list[dict[str, Any]] = []
    for index, plan in enumerate(plans):
        values = {
            "slot_id": plan.slot_id,
            "state_index": index,
            "phase": plan.phase,
            "public_state": {
                **plan.public_state,
                "capability_family": family.value,
                "depth": depth.value,
            },
            "terminal": False,
            "answer_ready": False,
        }
        state_base.append({"state_id": _state_id(values), **values})
    terminal_values = {
        "slot_id": "terminal",
        "state_index": len(plans),
        "phase": "answer_ready_terminal",
        "public_state": {
            "answer_ready": True,
            "capability_family": family.value,
            "depth": depth.value,
        },
        "terminal": True,
        "answer_ready": True,
    }
    state_base.append({"state_id": _state_id(terminal_values), **terminal_values})
    candidates: list[ExecutableDepthCandidate] = []
    transitions: list[ExecutableDepthTransition] = []
    state_candidates: dict[str, list[str]] = {}
    reference_candidates: dict[str, str] = {}
    reference_events: Counter[str] = Counter()
    for index, plan in enumerate(plans):
        state_id = cast(str, state_base[index]["state_id"])
        next_state_id = cast(str, state_base[index + 1]["state_id"])
        for presentation_index, candidate_plan in enumerate(plan.candidates):
            candidate_values = {
                "state_id": state_id,
                "slot_id": plan.slot_id,
                "presentation_index": presentation_index,
                "action_kind": candidate_plan.action_kind,
                "semantic_role": candidate_plan.semantic_role,
                "target_capability_action": candidate_plan.target,
                "reference_action": candidate_plan.reference,
                "nonidentity_axes": candidate_plan.axes,
                "failure_type": candidate_plan.failure_type,
            }
            candidate = cast(
                ExecutableDepthCandidate,
                _make_model(
                    ExecutableDepthCandidate,
                    candidate_values,
                    field="candidate_id",
                    prefix="executable_capability_depth_candidate:",
                ),
            )
            candidates.append(candidate)
            state_candidates.setdefault(state_id, []).append(candidate.candidate_id)
            if candidate.reference_action:
                if state_id in reference_candidates:
                    raise ValueError("depth State has multiple reference Candidates")
                reference_candidates[state_id] = candidate.candidate_id
                reference_events.update(candidate_plan.events)
            transition_values = {
                "from_state_id": state_id,
                "candidate_id": candidate.candidate_id,
                "to_state_id": next_state_id,
                "status": candidate_plan.status,
                "failure_code": candidate_plan.failure_code,
                "emitted_event_types": tuple(sorted(candidate_plan.events)),
                "emitted_reference_ids": tuple(sorted(candidate_plan.emitted_refs)),
                "consumed_reference_ids": tuple(sorted(candidate_plan.consumed_refs)),
                "public_update_delayed": candidate_plan.delayed,
            }
            transitions.append(
                _make_model(
                    ExecutableDepthTransition,
                    transition_values,
                    field="transition_id",
                    prefix="executable_capability_depth_transition:",
                )
            )
    states = []
    for index, values in enumerate(state_base):
        state_id = cast(str, values["state_id"])
        if index == len(plans):
            states.append(
                ExecutableDepthState(
                    **values,
                    candidate_ids=(),
                    reference_candidate_id=None,
                )
            )
        else:
            states.append(
                ExecutableDepthState(
                    **values,
                    candidate_ids=tuple(sorted(state_candidates[state_id])),
                    reference_candidate_id=reference_candidates[state_id],
                )
            )
    graph_values = {
        "package_id": package_id,
        "finance_core_id": core.core_id,
        "base_operational_task_package_id": core.operational_record.task_package.package_id,
        "capability_family": family,
        "depth": depth,
        "initial_state_id": states[0].state_id,
        "success_terminal_state_id": states[-1].state_id,
        "active_slot_ids": active_slots,
        "states": tuple(states),
        "candidates": tuple(sorted(candidates, key=lambda item: item.candidate_id)),
        "transitions": tuple(sorted(transitions, key=lambda item: item.transition_id)),
        "required_event_multiplicities": dict(sorted(reference_events.items())),
    }
    return cast(
        ExecutableCapabilityDepthGraph,
        _make_model(
            ExecutableCapabilityDepthGraph,
            graph_values,
            field="graph_id",
            prefix="executable_capability_depth_graph:",
        ),
    )


def _condition() -> models.FixedDevelopmentGenerationCondition:
    return cast(
        models.FixedDevelopmentGenerationCondition,
        _make_model(
            models.FixedDevelopmentGenerationCondition,
            {},
            field="condition_id",
            prefix="fixed_development_generation_condition:",
        ),
    )


def _boundary_contract() -> BoundarySelectionAlgorithmContract:
    return cast(
        BoundarySelectionAlgorithmContract,
        _make_model(
            BoundarySelectionAlgorithmContract,
            {},
            field="contract_id",
            prefix="capability_boundary_selection_algorithm_contract:",
        ),
    )


def _boundary_totality(
    contract: BoundarySelectionAlgorithmContract,
) -> models.BoundaryAlgorithmTotalityAudit:
    statuses = set()
    classified_count = 0
    patterns = tuple(itertools.product((False, True), repeat=8))
    for threshold, denominator in ((2, 6), (3, 8)):
        for pattern in patterns:
            counts = (
                tuple(threshold if value else 0 for value in pattern[:4]),
                tuple(threshold if value else 0 for value in pattern[4:]),
            )
            status, bracket = classify_capability_boundary(
                cast(Any, counts),
                threshold=cast(Any, threshold),
                denominator=cast(Any, denominator),
            )
            classified_count += 1
            statuses.add((status.value, tuple(item.value for item in bracket) if bracket else None))
    if not statuses or len(patterns) != 256 or classified_count != 512:
        raise ValueError("Boundary totality denominator changed")
    edge_cases = (
        (1, 2, False),
        (2, 2, True),
        (3, 2, True),
        (6, 2, True),
        (2, 3, False),
        (3, 3, True),
        (4, 3, True),
        (8, 3, True),
    )
    edge_pass = sum((value >= threshold) == expected for value, threshold, expected in edge_cases)
    values = {
        "contract_id": contract.contract_id,
        "uniquely_classified_pattern_count": classified_count,
        "threshold_edge_case_pass_count": edge_pass,
    }
    return cast(
        models.BoundaryAlgorithmTotalityAudit,
        _make_model(
            models.BoundaryAlgorithmTotalityAudit,
            values,
            field="audit_id",
            prefix="finance_v26_boundary_algorithm_totality_audit:",
        ),
    )


def _nuisance_envelope() -> ObservabilityFloorNuisanceEnvelope:
    values = {
        "maximum_tool_count": 6,
        "maximum_non_target_candidate_count": 2,
        "maximum_verification_obligation_count": 4,
        "maximum_prompt_bytes": 60_000,
        "maximum_base_reference_call_count": 6,
        "resource_token_ceiling": RESOURCE_TOKEN_CEILING,
    }
    return cast(
        ObservabilityFloorNuisanceEnvelope,
        _make_model(
            ObservabilityFloorNuisanceEnvelope,
            values,
            field="contract_id",
            prefix="observability_floor_nuisance_envelope:",
        ),
    )


def _render_prompt_binding(
    *,
    graph: ExecutableCapabilityDepthGraph,
    condition: models.FixedDevelopmentGenerationCondition,
    target_bytes: int,
) -> DepthPromptBinding:
    semantic = {
        "fixed_generation_condition": condition.model_dump(mode="json"),
        "runtime_graph": graph.model_dump(mode="json"),
    }
    payload = {"semantic": semantic, "padding": ""}
    base = _canonical_bytes(payload)
    padding = target_bytes - len(base)
    if padding < 0:
        raise ValueError("depth Prompt target is smaller than semantic payload")
    rendered = _canonical_bytes({"semantic": semantic, "padding": " " * padding})
    if len(rendered) != target_bytes:
        raise ValueError("depth Prompt padding did not close exact byte equality")
    values = {
        "graph_id": graph.graph_id,
        "semantic_payload_hash": canonical_hash(
            semantic,
            prefix="capability_depth_prompt_semantic_payload:",
        ),
        "rendered_prompt_hash": hashlib.sha256(rendered).hexdigest(),
        "rendered_prompt_bytes": len(rendered),
        "padding_bytes": padding,
        "fixed_generation_condition_id": condition.condition_id,
        "target_capability_candidate_hash": canonical_hash(
            tuple(item.candidate_id for item in graph.candidates),
            prefix="capability_depth_prompt_candidate_set:",
        ),
    }
    return cast(
        DepthPromptBinding,
        _make_model(
            DepthPromptBinding,
            values,
            field="binding_id",
            prefix="capability_depth_prompt_binding:",
        ),
    )


def _compile_variant_task_verification(
    *,
    core: models.LowNuisanceFinanceCore,
    condition: models.FixedDevelopmentGenerationCondition,
) -> tuple[BoundPublicExecutableWitness, ProgramVerification]:
    record = core.operational_record
    operational_witness, _ = compile_operational_witness(
        record,
        core.environment,
        strategy=cast(Any, condition.path_strategy),
    )
    program = record.task_package.task.oracle.task_program
    evidence_by_id = {item.evidence_id: item for item in record.evidence_bundle.evidence}
    execution = TaskProgramExecutor(default_registry()).execute(program, evidence_by_id)
    program_verification = TaskProgramOracleVerifier(default_registry()).verify(
        program,
        evidence_by_id,
        execution.node_outputs,
    )
    if not operational_witness.full_validity_passed or not program_verification.passed:
        raise ValueError("v26.168 Variant-local task verification failed")
    return operational_witness, program_verification


def _group(
    *,
    binding: models.ExecutableDepthSourceBinding,
    core: models.LowNuisanceFinanceCore,
    condition: models.FixedDevelopmentGenerationCondition,
) -> models.ExecutableDepthGroup:
    group_id = canonical_hash(
        {
            "group_index": binding.group_index,
            "partition": binding.partition.value,
            "capability_family": binding.capability_family.value,
            "source_binding_id": binding.binding_id,
            "finance_core_id": core.core_id,
            "schema_version": models.V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION,
        },
        prefix="finance_v26_executable_depth_group:",
    )
    record = core.operational_record
    preliminary = []
    for depth in OBSERVATION_DEPTH_ORDER:
        package_id = canonical_hash(
            {
                "group_id": group_id,
                "partition": binding.partition.value,
                "capability_family": binding.capability_family.value,
                "depth": depth.value,
                "source_binding_id": binding.binding_id,
                "finance_core_id": core.core_id,
                "schema_version": models.V26_EXECUTABLE_DEPTH_REMATERIALIZATION_VERSION,
            },
            prefix="finance_v26_executable_depth_package:",
        )
        graph = _graph(
            package_id=package_id,
            core=core,
            family=binding.capability_family,
            depth=depth,
        )
        witness_contract = cast(
            CapabilityDepthWitnessContract,
            _make_model(
                CapabilityDepthWitnessContract,
                {
                    "graph_id": graph.graph_id,
                    "capability_family": binding.capability_family,
                    "depth": depth,
                    "required_event_multiplicities": graph.required_event_multiplicities,
                },
                field="contract_id",
                prefix="capability_depth_witness_contract:",
            ),
        )
        verifier_contract = cast(
            CapabilityDepthVerifierContract,
            _make_model(
                CapabilityDepthVerifierContract,
                {"witness_contract_id": witness_contract.contract_id},
                field="contract_id",
                prefix="capability_depth_verifier_contract:",
            ),
        )
        variant_operational_witness, variant_program_verification = (
            _compile_variant_task_verification(core=core, condition=condition)
        )
        witness = static_audit.compile_depth_witness(
            graph,
            witness_contract,
            verifier_contract,
        )
        target_load = static_audit.compute_target_load(graph, witness)
        semantic = {
            "fixed_generation_condition": condition.model_dump(mode="json"),
            "runtime_graph": graph.model_dump(mode="json"),
        }
        preliminary.append(
            (
                package_id,
                graph,
                witness_contract,
                verifier_contract,
                variant_operational_witness,
                variant_program_verification,
                witness,
                target_load,
                len(_canonical_bytes({"semantic": semantic, "padding": ""})),
            )
        )
    prompt_target = max(item[-1] for item in preliminary) + 512
    base_public_bytes = len(_canonical_bytes(record.task_package.task.public))
    program = record.task_package.task.oracle.task_program
    program_edges = sum(
        item.kind == InputRefKind.OPERATION for node in program.nodes for item in node.input_refs
    )
    operation_candidates = sum(
        max(0, len(node.allowed_operator_ids) - 1)
        for node in record.task_package.operation_contract.public_view.nodes
    )
    nuisance_values = {
        "finance_core_id": core.core_id,
        "base_operational_task_package_id": record.task_package.package_id,
        "evidence_count": len(record.evidence_bundle.evidence),
        "program_node_count": len(program.nodes),
        "program_edge_count": program_edges,
        "tool_count": len(core.environment.tools),
        "non_target_candidate_count": operation_candidates,
        "verification_obligation_count": len(record.task_package.verifier_binding.node_bindings)
        + 1,
        "prompt_bytes": base_public_bytes + prompt_target,
        "base_reference_call_count": len(core.operational_witness.steps),
        "resource_token_ceiling": RESOURCE_TOKEN_CEILING,
    }
    nuisance = cast(
        CompiledNuisanceMeasurement,
        _make_model(
            CompiledNuisanceMeasurement,
            nuisance_values,
            field="measurement_id",
            prefix="compiled_capability_nuisance_measurement:",
        ),
    )
    packages = []
    for (
        package_id,
        graph,
        witness_contract,
        verifier_contract,
        variant_operational_witness,
        variant_program_verification,
        witness,
        target_load,
        _,
    ) in preliminary:
        prompt = _render_prompt_binding(
            graph=graph,
            condition=condition,
            target_bytes=prompt_target,
        )
        public_state_hash = canonical_hash(
            tuple(item.model_dump(mode="json") for item in graph.states),
            prefix="executable_depth_public_state_graph:",
        )
        candidate_hash = canonical_hash(
            tuple(item.model_dump(mode="json") for item in graph.candidates),
            prefix="executable_depth_candidate_set:",
        )
        transition_hash = canonical_hash(
            tuple(item.model_dump(mode="json") for item in graph.transitions),
            prefix="executable_depth_transition_set:",
        )
        signature_values = {
            "package_id": package_id,
            "graph_id": graph.graph_id,
            "finance_core_id": core.core_id,
            "base_operational_record_id": record.record_id,
            "variant_operational_witness_id": variant_operational_witness.witness_id,
            "variant_program_verification_hash": canonical_hash(
                variant_program_verification.model_dump(mode="json"),
                prefix="variant_task_program_verification:",
            ),
            "depth_witness_id": witness.witness_id,
            "witness_contract_id": witness_contract.contract_id,
            "verifier_contract_id": verifier_contract.contract_id,
            "target_load_id": target_load.load_id,
            "nuisance_measurement_id": nuisance.measurement_id,
            "prompt_binding_id": prompt.binding_id,
            "public_state_graph_hash": public_state_hash,
            "candidate_set_hash": candidate_hash,
            "transition_hash": transition_hash,
        }
        signature = cast(
            ExecutableDepthSignature,
            _make_model(
                ExecutableDepthSignature,
                signature_values,
                field="signature_id",
                prefix="executable_capability_depth_signature:",
            ),
        )
        packages.append(
            models.ExecutableDepthPackage(
                package_id=package_id,
                group_id=group_id,
                partition=binding.partition,
                capability_family=binding.capability_family,
                depth=graph.depth,
                source_binding_id=binding.binding_id,
                finance_core_id=core.core_id,
                graph=graph,
                witness_contract=witness_contract,
                verifier_contract=verifier_contract,
                variant_operational_witness=variant_operational_witness,
                variant_program_verification=variant_program_verification,
                depth_witness=witness,
                target_load=target_load,
                nuisance=nuisance,
                prompt_binding=prompt,
                signature=signature,
            )
        )
    return models.ExecutableDepthGroup(
        group_id=group_id,
        group_index=binding.group_index,
        partition=binding.partition,
        capability_family=binding.capability_family,
        source_binding_id=binding.binding_id,
        finance_core_id=core.core_id,
        packages=tuple(packages),
    )


def _catalog(
    partition: ObservationPartition,
    groups: Sequence[models.ExecutableDepthGroup],
    cores: Mapping[str, models.LowNuisanceFinanceCore],
) -> models.ExecutableDepthCatalog:
    selected_groups = tuple(item for item in groups if item.partition == partition)
    selected_core_ids = {item.finance_core_id for item in selected_groups}
    values = {
        "partition": partition,
        "finance_cores": tuple(
            sorted((cores[item] for item in selected_core_ids), key=lambda item: item.core_id)
        ),
        "groups": tuple(
            sorted(
                selected_groups, key=lambda item: (item.capability_family.value, item.group_index)
            )
        ),
    }
    return cast(
        models.ExecutableDepthCatalog,
        _make_model(
            models.ExecutableDepthCatalog,
            values,
            field="catalog_id",
            prefix=f"finance_v26_{partition.value}_executable_depth_catalog:",
        ),
    )


def _confirmation_receipt(path: Path, catalog_id: str) -> models.SealedConfirmationReceipt:
    values = {
        "sealed_catalog_id": catalog_id,
        "sealed_content_root_sha256": _sha256(path),
        "sealed_byte_count": path.stat().st_size,
    }
    return cast(
        models.SealedConfirmationReceipt,
        _make_model(
            models.SealedConfirmationReceipt,
            values,
            field="receipt_id",
            prefix="finance_v26_sealed_confirmation_executable_depth_receipt:",
        ),
    )


def _noninterference(
    condition: models.FixedDevelopmentGenerationCondition,
    catalog: models.ExecutableDepthCatalog,
) -> models.TargetCapabilityNoninterferenceAudit:
    packages = tuple(item for group in catalog.groups for item in group.packages)
    candidate_matches = sum(
        item.signature.candidate_set_hash
        == canonical_hash(
            tuple(candidate.model_dump(mode="json") for candidate in item.graph.candidates),
            prefix="executable_depth_candidate_set:",
        )
        for item in packages
    )
    transition_matches = sum(
        item.signature.transition_hash
        == canonical_hash(
            tuple(transition.model_dump(mode="json") for transition in item.graph.transitions),
            prefix="executable_depth_transition_set:",
        )
        for item in packages
    )
    values = {
        "condition_id": condition.condition_id,
        "candidate_set_match_count": candidate_matches,
        "transition_graph_match_count": transition_matches,
    }
    return cast(
        models.TargetCapabilityNoninterferenceAudit,
        _make_model(
            models.TargetCapabilityNoninterferenceAudit,
            values,
            field="audit_id",
            prefix="finance_v26_target_capability_noninterference_audit:",
        ),
    )


def _nuisance_audit(
    envelope: ObservabilityFloorNuisanceEnvelope,
    groups: Sequence[models.ExecutableDepthGroup],
) -> models.NuisanceRecomputationAudit:
    packages = tuple(item for group in groups for item in group.packages)
    within = (
        sum(len({item.nuisance.measurement_id for item in group.packages}) == 1 for group in groups)
        * 4
    )
    development = tuple(
        item for item in packages if item.partition == ObservationPartition.DEVELOPMENT
    )
    floor_pass = sum(
        item.nuisance.evidence_count <= envelope.maximum_evidence_count
        and item.nuisance.program_node_count <= envelope.maximum_program_node_count
        and item.nuisance.program_edge_count <= envelope.maximum_program_edge_count
        and item.nuisance.tool_count <= envelope.maximum_tool_count
        and item.nuisance.non_target_candidate_count <= envelope.maximum_non_target_candidate_count
        and item.nuisance.verification_obligation_count
        <= envelope.maximum_verification_obligation_count
        and item.nuisance.prompt_bytes <= envelope.maximum_prompt_bytes
        and item.nuisance.base_reference_call_count <= envelope.maximum_base_reference_call_count
        and item.nuisance.resource_token_ceiling == envelope.resource_token_ceiling
        for item in development
    )
    values = {
        "envelope_contract_id": envelope.contract_id,
        "within_group_exact_match_count": within,
        "development_floor_envelope_pass_count": floor_pass,
    }
    return cast(
        models.NuisanceRecomputationAudit,
        _make_model(
            models.NuisanceRecomputationAudit,
            values,
            field="audit_id",
            prefix="finance_v26_executable_depth_nuisance_recomputation_audit:",
        ),
    )


def _transition(
    *,
    development_catalog: models.ExecutableDepthCatalog,
    receipt: models.SealedConfirmationReceipt,
    boundary: BoundarySelectionAlgorithmContract,
) -> models.TransitionContract:
    values = {
        "prospective_report_id": canonical_hash(
            {
                "run_id": RUN_ID,
                "development_catalog_id": development_catalog.catalog_id,
                "sealed_confirmation_receipt_id": receipt.receipt_id,
            },
            prefix="finance_v26_executable_depth_prospective_report:",
        ),
        "development_catalog_id": development_catalog.catalog_id,
        "sealed_confirmation_receipt_id": receipt.receipt_id,
        "boundary_algorithm_contract_id": boundary.contract_id,
        "next_stage": "capability_observation_executable_depth_development_runner_preflight_only",
        "forbidden_operations": tuple(
            sorted(
                (
                    "confirmation_execution",
                    "confirmation_payload_loading",
                    "current_27_cell_selection",
                    "depth_graph_change",
                    "historical_reclassification",
                    "mapper_state_assignment",
                    "provider_execution",
                    "source_reselection",
                    "student_training",
                    "threshold_tuning",
                    "v26_167_historical_rewrite",
                    "vtdo_or_contribution_estimation",
                )
            )
        ),
    }
    return cast(
        models.TransitionContract,
        _make_model(
            models.TransitionContract,
            values,
            field="transition_id",
            prefix="finance_v26_executable_depth_transition:",
        ),
    )


def _detail_files(output_dir: Path) -> tuple[models.DetailFile, ...]:
    return tuple(
        models.DetailFile(
            filename=path.name,
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "report.json"
    )


def build(
    *,
    package_root: Path,
    output_dir: Path,
    sealed_output_dir: Path,
    external_audit_path: Path,
) -> models.BuildProducts:
    package_root = _resolve_package_root(package_root)
    output_dir = output_dir.resolve()
    sealed_output_dir = sealed_output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("v26.168 formal output directory is not empty")
    if sealed_output_dir.exists() and any(sealed_output_dir.iterdir()):
        raise ValueError("v26.168 sealed Confirmation directory is not empty")
    authorization = _authorization(external_audit_path)
    source_root = _transitive_source_root(package_root)

    # Selection is complete before loading any v26.167 audit result.
    source_capacity, selected_tasks = _select_sources(package_root)
    v167_report = v167_models.CapabilityBreadthDepthStaticAuditReport.model_validate(
        _load(package_root / V167_DIR / "report.json")
    )
    defect = _v167_defect_audit(package_root, v167_report)
    source_replay = _source_replay(
        package_root=package_root,
        authorization=authorization,
        source_root=source_root,
        v167_report=v167_report,
    )
    condition = _condition()
    boundary = _boundary_contract()
    boundary_totality = _boundary_totality(boundary)
    envelope = _nuisance_envelope()

    cores: dict[str, models.LowNuisanceFinanceCore] = {}
    groups = []
    for binding in source_capacity.selected:
        core = _finance_core(binding, selected_tasks[binding.binding_id])
        cores[core.core_id] = core
        groups.append(_group(binding=binding, core=core, condition=condition))
    development = _catalog(ObservationPartition.DEVELOPMENT, groups, cores)
    confirmation = _catalog(ObservationPartition.CONFIRMATION, groups, cores)

    sealed_output_dir.mkdir(parents=True, exist_ok=True)
    sealed_catalog_path = sealed_output_dir / "sealed_confirmation_executable_depth_catalog.json"
    _write(sealed_catalog_path, confirmation)
    receipt = _confirmation_receipt(sealed_catalog_path, confirmation.catalog_id)

    noninterference = _noninterference(condition, development)
    packages = tuple(item for group in groups for item in group.packages)
    necessity = static_audit.build_counterfactual_replays(packages)
    nuisance_audit = _nuisance_audit(envelope, groups)
    destructive = static_audit.build_production_destructive_audit(
        sample_package=development.groups[0].packages[0],
        development_catalog=development,
        receipt=receipt,
        source_root=source_root,
        boundary_contract=boundary,
        sample_core=development.finance_cores[0],
    )
    static = static_audit.build_static_audit(
        packages=packages,
        development_groups=development.groups,
        confirmation_groups=confirmation.groups,
        source_capacity=source_capacity,
        v167_defect=defect,
        source_root=source_root,
        receipt=receipt,
        noninterference=noninterference,
        boundary_totality=boundary_totality,
        necessity=necessity,
        nuisance_audit=nuisance_audit,
    )
    transition = _transition(
        development_catalog=development,
        receipt=receipt,
        boundary=boundary,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(output_dir / "external_joint_audit_input.txt", external_audit_path.read_bytes())
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("source_replay_audit.json", source_replay),
        ("v167_executable_depth_defect_audit.json", defect),
        ("executable_depth_source_capacity_audit.json", source_capacity),
        ("observability_floor_nuisance_envelope.json", envelope),
        ("fixed_development_generation_condition.json", condition),
        ("target_capability_noninterference_audit.json", noninterference),
        ("boundary_selection_algorithm_contract.json", boundary),
        ("boundary_algorithm_totality_audit.json", boundary_totality),
        ("development_executable_depth_catalog.json", development),
        ("sealed_confirmation_receipt.json", receipt),
        ("mechanism_necessity_catalog.json", necessity),
        ("nuisance_recomputation_audit.json", nuisance_audit),
        ("executable_depth_static_audit.json", static),
        ("production_destructive_audit.json", destructive),
        ("prospective_transition_contract.json", transition),
    )
    for filename, value in outputs:
        _write(output_dir / filename, value)
    details = _detail_files(output_dir)
    report_values = {
        "run_id": RUN_ID,
        "authorization_id": authorization.authorization_id,
        "source_replay_audit_id": source_replay.audit_id,
        "transitive_source_root_id": source_root.root_id,
        "v26_167_defect_audit_id": defect.audit_id,
        "source_capacity_audit_id": source_capacity.audit_id,
        "nuisance_envelope_contract_id": envelope.contract_id,
        "development_catalog_id": development.catalog_id,
        "sealed_confirmation_receipt_id": receipt.receipt_id,
        "fixed_generation_condition_id": condition.condition_id,
        "noninterference_audit_id": noninterference.audit_id,
        "boundary_algorithm_contract_id": boundary.contract_id,
        "boundary_totality_audit_id": boundary_totality.audit_id,
        "necessity_catalog_id": necessity.catalog_id,
        "nuisance_recomputation_audit_id": nuisance_audit.audit_id,
        "static_audit_id": static.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_id": transition.transition_id,
        "detail_files": details,
        "next_stage": transition.next_stage,
    }
    report = cast(
        models.ExecutableDepthRematerializationReport,
        _make_model(
            models.ExecutableDepthRematerializationReport,
            report_values,
            field="report_id",
            prefix="finance_v26_executable_depth_rematerialization_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        transitive_source_root=source_root,
        source_replay=source_replay,
        v167_defect=defect,
        source_capacity=source_capacity,
        nuisance_envelope=envelope,
        fixed_condition=condition,
        noninterference=noninterference,
        boundary_contract=boundary,
        boundary_totality=boundary_totality,
        development_catalog=development,
        confirmation_receipt=receipt,
        necessity=necessity,
        nuisance_audit=nuisance_audit,
        static_audit=static,
        destructive_audit=destructive,
        transition=transition,
        report=report,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--sealed-output-dir", type=Path)
    parser.add_argument("--external-audit", type=Path, required=True)
    args = parser.parse_args()
    package_root = _resolve_package_root(args.package_root)
    output_dir = args.output_dir or package_root / OUTPUT_DIR
    sealed_output_dir = args.sealed_output_dir or package_root / SEALED_OUTPUT_DIR
    products = build(
        package_root=package_root,
        output_dir=output_dir,
        sealed_output_dir=sealed_output_dir,
        external_audit_path=args.external_audit,
    )
    print(json.dumps(products.report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
