from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel

from trusted_synthesis.core.operations.program import ProgramVerification
from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.causal_capability_depth import (
    PUBLIC_ACTION_ID_LENGTH,
    CausalActionKind,
    CausalCounterfactualKind,
    CausalDepthVerifierContract,
    CausalDepthWitnessContract,
    CausalFinanceBinding,
    CausalFinanceSnapshot,
    CausalTerminalKind,
    CausalTransitionStatus,
    DepthPromptProjectionContract,
    FinanceEffect,
    FinanceEffectKind,
    HostExecutableDepthCandidate,
    HostExecutableDepthGraph,
    HostExecutableDepthState,
    HostExecutableDepthTransition,
    PublicArgument,
    PublicExecutableDepthCandidate,
    PublicExecutableDepthState,
    PublicFact,
    PublicPromptProjection,
    apply_effects,
    canonical_bytes,
    initial_snapshot,
    scan_public_leakage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization as v168,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as v168_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_projection_causal_runtime_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_projection_causal_runtime_static_audit as static_audit,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_169_public_projection_causal_depth_runtime_hardening_v1_20260828"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_169_public_projection_causal_depth_runtime_hardening_v1_20260828"
)
EXPECTED_REVIEW_SHA256: Final = "6105461d1c58f507ee5227f3b8f6867e020dedec828b7687befe1eddb108bb4e"
EXPECTED_REVIEW_BYTE_COUNT: Final = 27_021
AUTHORIZED_STAGE: Final = (
    "capability_observation_public_projection_and_causal_depth_runtime_hardening_only"
)
CANDIDATE_PRESENTATION_SALT: Final = "finance-v26.169-public-candidate-preoutcome-permutation-v1"
V168_DIR: Final = v168.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/causal_capability_depth.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_public_projection_causal_runtime_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_public_projection_causal_runtime_static_audit.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_public_projection_causal_runtime_hardening.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.169 cannot resolve the trusted_data_synthesis package root")


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
        raise ValueError(f"v26.169 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.169 immutable output already exists:{path}")
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


def _make_core_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    identifier = canonical_hash(
        provisional.model_dump(mode="json", exclude={field}),
        prefix=prefix,
    )
    return model_type(**{field: identifier}, **values)


def _file_binding(
    *,
    path: Path,
    relative_path: str,
    source_kind: str,
) -> models.FileBinding:
    return models.FileBinding(
        relative_path=relative_path,
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
        source_kind=cast(Any, source_kind),
    )


def _authorization(path: Path) -> models.ExternalAuditAuthorization:
    if _sha256(path) != EXPECTED_REVIEW_SHA256:
        raise ValueError("v26.169 external review SHA-256 changed")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.169 external review byte count changed")
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
            prefix="finance_v26_causal_depth_external_audit_authorization:",
        ),
    )


def _module_name(relative_path: str) -> str:
    parts = Path(relative_path).with_suffix("").parts
    if "src" not in parts:
        raise ValueError(f"source path is outside src:{relative_path}")
    module_parts = list(parts[parts.index("src") + 1 :])
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
    entry_modules = tuple(_module_name(path) for path in ENTRY_SOURCE_PATHS)
    pending = list(entry_modules)
    visited: set[str] = set()
    unresolved: set[str] = set()
    paths: set[Path] = set()
    while pending:
        module = pending.pop()
        if module in visited:
            continue
        visited.add(module)
        path = _module_path(package_root, module)
        if path is None:
            unresolved.add(module)
            continue
        paths.add(path)
        for imported in _imported_modules(package_root, path):
            if imported not in visited:
                pending.append(imported)
    if unresolved:
        raise ValueError(f"v26.169 unresolved trusted_synthesis imports:{sorted(unresolved)}")
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=str(path.relative_to(package_root)),
            source_kind="transitive_source",
        )
        for path in sorted(paths)
    )
    values = {
        "entry_modules": entry_modules,
        "files": bindings,
        "file_count": len(bindings),
    }
    return cast(
        models.TransitiveSourceRoot,
        _make_model(
            models.TransitiveSourceRoot,
            values,
            field="root_id",
            prefix="finance_v26_causal_depth_transitive_source_root:",
        ),
    )


@dataclass(frozen=True)
class _PredecessorProducts:
    audit: models.PredecessorIntegrityAudit
    report: v168_models.ExecutableDepthRematerializationReport
    catalog: v168_models.ExecutableDepthCatalog
    receipt: v168_models.SealedConfirmationReceipt
    transition: v168_models.TransitionContract


def _predecessor_integrity(package_root: Path) -> _PredecessorProducts:
    root = package_root / V168_DIR
    files = tuple(sorted(path for path in root.iterdir() if path.is_file()))
    if len(files) != 19:
        raise ValueError(f"v26.168 main Root no longer contains 19 files:{len(files)}")
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=str(path.relative_to(package_root)),
            source_kind="v26_168_frozen_output",
        )
        for path in files
    )
    report = v168_models.ExecutableDepthRematerializationReport.model_validate(
        _load(root / "report.json")
    )
    catalog = v168_models.ExecutableDepthCatalog.model_validate(
        _load(root / "development_executable_depth_catalog.json")
    )
    receipt = v168_models.SealedConfirmationReceipt.model_validate(
        _load(root / "sealed_confirmation_receipt.json")
    )
    transition = v168_models.TransitionContract.model_validate(
        _load(root / "prospective_transition_contract.json")
    )
    if (
        report.development_catalog_id != catalog.catalog_id
        or report.sealed_confirmation_receipt_id != receipt.receipt_id
        or report.transition_id != transition.transition_id
    ):
        raise ValueError("v26.168 report parents are inconsistent")
    values = {
        "v26_168_report_id": report.report_id,
        "v26_168_development_catalog_id": catalog.catalog_id,
        "v26_168_sealed_receipt_id": receipt.receipt_id,
        "v26_168_transition_id": transition.transition_id,
        "bindings": bindings,
    }
    audit = cast(
        models.PredecessorIntegrityAudit,
        _make_model(
            models.PredecessorIntegrityAudit,
            values,
            field="audit_id",
            prefix="finance_v26_causal_depth_predecessor_integrity:",
        ),
    )
    return _PredecessorProducts(
        audit=audit,
        report=report,
        catalog=catalog,
        receipt=receipt,
        transition=transition,
    )


def _source_replay(
    *,
    package_root: Path,
    external_audit_path: Path,
    authorization: models.ExternalAuditAuthorization,
    predecessor: models.PredecessorIntegrityAudit,
    source_root: models.TransitiveSourceRoot,
) -> models.SourceReplayAudit:
    review = _file_binding(
        path=external_audit_path,
        relative_path="external_reviews/v26_169_joint_audit_input.txt",
        source_kind="external_audit_input",
    )
    by_path = {
        item.relative_path: item for item in (review, *predecessor.bindings, *source_root.files)
    }
    values = {
        "authorization_id": authorization.authorization_id,
        "predecessor_integrity_audit_id": predecessor.audit_id,
        "transitive_source_root_id": source_root.root_id,
        "bindings": tuple(by_path[key] for key in sorted(by_path)),
    }
    return cast(
        models.SourceReplayAudit,
        _make_model(
            models.SourceReplayAudit,
            values,
            field="audit_id",
            prefix="finance_v26_causal_depth_source_replay:",
        ),
    )


def _defect_reproduction(
    catalog: v168_models.ExecutableDepthCatalog,
) -> models.V168DefectReproductionAudit:
    packages = tuple(package for group in catalog.groups for package in group.packages)
    nonterminal = tuple(
        state for package in packages for state in package.graph.states if not state.terminal
    )
    same_successor = 0
    for package in packages:
        transitions = {item.candidate_id: item for item in package.graph.transitions}
        for state in package.graph.states:
            if (
                not state.terminal
                and len({transitions[item].to_state_id for item in state.candidate_ids}) == 1
            ):
                same_successor += 1
    reference_fields = sum(item.reference_candidate_id is not None for item in nonterminal)
    reference_actions = sum(
        item.reference_action for package in packages for item in package.graph.candidates
    )
    target_actions = sum(
        item.target_capability_action for package in packages for item in package.graph.candidates
    )
    bypass = sum(
        item.action_kind.value == "target_bypass"
        for package in packages
        for item in package.graph.candidates
    )
    tempting = sum(
        "tempting_continuation" in item.semantic_role
        for package in packages
        for item in package.graph.candidates
    )
    public_family = sum(
        "capability_family" in state.public_state
        for package in packages
        for state in package.graph.states
    )
    public_depth = sum(
        "depth" in state.public_state for package in packages for state in package.graph.states
    )
    required_keys = sum(len(package.graph.required_event_multiplicities) for package in packages)
    values = {
        "predecessor_development_catalog_id": catalog.catalog_id,
        "nonterminal_state_count": len(nonterminal),
        "all_candidates_same_successor_count": same_successor,
        "reference_candidate_field_count": reference_fields,
        "reference_action_true_count": reference_actions,
        "target_capability_action_true_count": target_actions,
        "target_bypass_candidate_count": bypass,
        "tempting_continuation_candidate_count": tempting,
        "public_capability_family_field_count": public_family,
        "public_depth_field_count": public_depth,
        "required_event_key_count": required_keys,
    }
    return cast(
        models.V168DefectReproductionAudit,
        _make_model(
            models.V168DefectReproductionAudit,
            values,
            field="audit_id",
            prefix="finance_v26_v168_public_projection_runtime_defect_audit:",
        ),
    )


def _projection_contract() -> DepthPromptProjectionContract:
    return cast(
        DepthPromptProjectionContract,
        _make_core_model(
            DepthPromptProjectionContract,
            {},
            field="contract_id",
            prefix="depth_prompt_projection_contract:",
        ),
    )


def _presentation_policy() -> models.CandidatePresentationPolicy:
    values = {
        "permutation_salt_sha256": hashlib.sha256(
            CANDIDATE_PRESENTATION_SALT.encode("utf-8")
        ).hexdigest()
    }
    return cast(
        models.CandidatePresentationPolicy,
        _make_model(
            models.CandidatePresentationPolicy,
            values,
            field="policy_id",
            prefix="causal_depth_candidate_presentation_policy:",
        ),
    )


def _public_task_projection(core: v168_models.LowNuisanceFinanceCore) -> dict[str, Any]:
    public = core.operational_record.task_package.task.public.model_dump(mode="json")
    guidance = public["metadata"]["agent_contract_guidance"]
    operation = guidance["public_operation_execution_contract"]
    nodes = tuple(
        {
            "sequence": index,
            "tool": item["tool_id"],
            "dependency_count": len(item["dependency_node_ids"]),
            "operator_options": tuple(item["allowed_operator_ids"]),
            "requires_output": bool(item["required_for_completion"]),
            "terminal": bool(item["terminal"]),
        }
        for index, item in enumerate(operation["nodes"], start=1)
    )
    projection = {
        "domain": "finance",
        "instruction": (
            "Complete the currently visible finance operations and return the exact public "
            "result only after verification."
        ),
        "allowed_tools": tuple(sorted(public["allowed_tools"])),
        "answer_fields": tuple(sorted(public["answer_schema"]["required_fields"])),
        "evidence_count": len(core.operational_record.evidence_bundle.evidence),
        "operation_plan": nodes,
        "retrieval_summary": {
            "alias_count": len(public["retrieval_scope"]["aliases"]),
            "period_count": len(public["retrieval_scope"]["partial_constraints"]["period_labels"]),
            "source_count": public["retrieval_scope"]["corpus_boundary"]["source_count"],
        },
    }
    findings = scan_public_leakage(projection)
    if findings:
        raise ValueError(f"sanitized Finance task projection leaks Host semantics:{findings}")
    return projection


def _operation_contract(core: v168_models.LowNuisanceFinanceCore) -> dict[str, Any]:
    public = core.operational_record.task_package.task.public.model_dump(mode="json")
    return cast(
        dict[str, Any],
        public["metadata"]["agent_contract_guidance"]["public_operation_execution_contract"],
    )


def _finance_binding(
    core: v168_models.LowNuisanceFinanceCore,
    program_verification: ProgramVerification,
) -> CausalFinanceBinding:
    record = core.operational_record
    task = record.task_package.task
    program = task.oracle.task_program
    task_public = task.public.model_dump(mode="json")
    operation = _operation_contract(core)
    operation_nodes = tuple(item["node_id"] for item in operation["nodes"])
    terminal = cast(str, operation["terminal_node_id"])
    normalization_refs = tuple(
        sorted(
            item["output_symbol"]
            for item in operation["nodes"]
            if item["node_kind"] == "normalization"
        )
    )
    rule_payloads = tuple(
        rule for variable in operation["variables"] for rule in variable["resolution_rules"]
    )
    if len(rule_payloads) < 4:
        raise ValueError("Finance Core lacks four exact selector rule bindings")
    selector_ids = tuple(
        sorted(
            canonical_hash(
                {"core_id": core.core_id, "rule": rule},
                prefix="causal_finance_selector:",
            )
            for rule in rule_payloads[:4]
        )
    )
    selector_failure_codes = {
        selector: f"selector_fault_{index:02d}"
        for index, selector in enumerate(selector_ids, start=1)
    }
    input_refs = tuple(
        item.model_dump(mode="json") for node in program.nodes for item in node.input_refs
    )
    if not input_refs:
        raise ValueError("Finance Program has no bound inputs")
    input_binding_ids = tuple(
        sorted(
            canonical_hash(
                {"core_id": core.core_id, "input_ref": item},
                prefix="causal_finance_input_binding:",
            )
            for item in input_refs
        )
    )
    answer_fields = tuple(task_public["answer_schema"]["required_fields"])
    projection_ids = tuple(
        sorted(
            canonical_hash(
                {"core_id": core.core_id, "answer_field": item},
                prefix="causal_finance_output_projection:",
            )
            for item in answer_fields
        )
    )
    stop_contract = task_public["metadata"]["agent_contract_guidance"][
        "public_stop_readiness_contract"
    ]
    readiness_ids = tuple(
        sorted(
            canonical_hash(
                {"stop_contract": stop_contract, "check_index": index},
                prefix="causal_finance_readiness_check:",
            )
            for index in range(1, 5)
        )
    )
    public_hash = canonical_hash(
        task.public.model_dump(mode="json"),
        prefix="causal_finance_task_public:",
    )
    program_hash = canonical_hash(
        program.model_dump(mode="json"),
        prefix="causal_finance_task_program:",
    )
    verifier_hash = canonical_hash(
        program_verification.model_dump(mode="json"),
        prefix="causal_finance_independent_program_verification:",
    )
    verifier_binding_id = canonical_hash(
        {
            "task_id": task.oracle.task_id,
            "program_id": program.program_id,
            "quality_rubric": task.oracle.quality_rubric,
            "selection_contract": task.oracle.selection_contract,
            "verification_hash": verifier_hash,
        },
        prefix="causal_finance_task_verifier_binding:",
    )
    expected_result_hash = canonical_hash(
        program_verification.independently_computed_output,
        prefix="causal_finance_expected_program_result:",
    )
    evidence_ids = tuple(sorted(item.evidence_id for item in record.evidence_bundle.evidence))
    if len(evidence_ids) != 2:
        raise ValueError("causal Finance binding requires exactly two Evidence IDs")
    values = {
        "finance_core_id": core.core_id,
        "base_operational_task_package_id": record.task_package.package_id,
        "operational_record_id": record.record_id,
        "task_program_id": program.program_id,
        "task_verifier_binding_id": verifier_binding_id,
        "task_public_hash": public_hash,
        "program_hash": program_hash,
        "verifier_hash": verifier_hash,
        "evidence_ids": evidence_ids,
        "operation_node_ids": operation_nodes,
        "terminal_operation_node_id": terminal,
        "normalization_reference_ids": normalization_refs,
        "selector_ids": selector_ids,
        "selector_failure_codes": selector_failure_codes,
        "input_binding_ids": input_binding_ids,
        "projection_ids": projection_ids,
        "readiness_check_ids": readiness_ids,
        "expected_operator_id": program.nodes[0].operator_id,
        "expected_result_hash": expected_result_hash,
    }
    return cast(
        CausalFinanceBinding,
        _make_core_model(
            CausalFinanceBinding,
            values,
            field="binding_id",
            prefix="causal_finance_program_binding:",
        ),
    )


@dataclass(frozen=True)
class _ChoicePlan:
    action_kind: CausalActionKind
    tool: str
    arguments: tuple[str, ...]
    effects: tuple[FinanceEffect, ...]
    status: CausalTransitionStatus
    public_observation: str
    failure_code: str | None = None
    events: tuple[str, ...] = ()
    emitted_references: tuple[str, ...] = ()
    consumed_references: tuple[str, ...] = ()
    target_capability_action: bool = False


@dataclass(frozen=True)
class _StepPlan:
    phase: str
    facts: tuple[str, ...]
    reference: _ChoicePlan
    alternatives: tuple[_ChoicePlan, _ChoicePlan]


def _effect(kind: FinanceEffectKind, value: str | None = None) -> FinanceEffect:
    return FinanceEffect(kind=kind, value=value)


def _invalid_alternatives(
    *,
    phase: str,
    tool: str,
    arguments: tuple[tuple[str, ...], tuple[str, ...]],
    target: bool,
) -> tuple[_ChoicePlan, _ChoicePlan]:
    rows = []
    for index, values in enumerate(arguments, start=1):
        rows.append(
            _ChoicePlan(
                action_kind=CausalActionKind.TERMINATE_INVALID,
                tool=tool,
                arguments=values,
                effects=(
                    _effect(
                        FinanceEffectKind.SET_ALTERNATE_RESULT,
                        f"{phase}_alternative_{index:02d}",
                    ),
                    _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
                ),
                status=CausalTransitionStatus.TASK_INVALID,
                public_observation=(
                    "The selected finance operation violated a visible task constraint."
                ),
                events=("task_constraint_mismatch",),
                target_capability_action=target,
            )
        )
    return cast(tuple[_ChoicePlan, _ChoicePlan], tuple(rows))


def _step(
    *,
    phase: str,
    facts: tuple[str, ...],
    action_kind: CausalActionKind,
    tool: str,
    arguments: tuple[str, ...],
    effects: tuple[FinanceEffect, ...],
    events: tuple[str, ...],
    alternatives: tuple[tuple[str, ...], tuple[str, ...]],
    target: bool,
    status: CausalTransitionStatus = CausalTransitionStatus.SUCCEEDED,
    public_observation: str = "The finance operation completed and the public state changed.",
    failure_code: str | None = None,
    emitted_references: tuple[str, ...] = (),
    consumed_references: tuple[str, ...] = (),
) -> _StepPlan:
    return _StepPlan(
        phase=phase,
        facts=facts,
        reference=_ChoicePlan(
            action_kind=action_kind,
            tool=tool,
            arguments=arguments,
            effects=effects,
            status=status,
            public_observation=public_observation,
            failure_code=failure_code,
            events=events,
            emitted_references=emitted_references,
            consumed_references=consumed_references,
            target_capability_action=target,
        ),
        alternatives=_invalid_alternatives(
            phase=phase,
            tool=tool,
            arguments=alternatives,
            target=target,
        ),
    )


def _execute_and_close_steps(binding: CausalFinanceBinding) -> tuple[_StepPlan, _StepPlan]:
    execute_effects = tuple(
        _effect(FinanceEffectKind.COMPLETE_NODE, item) for item in binding.operation_node_ids
    ) + (
        _effect(FinanceEffectKind.SET_EXPECTED_RESULT, binding.expected_result_hash),
        _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
    )
    execute = _step(
        phase="finance_program_execution",
        facts=("All visible operands are available.", "The finance Program can be executed."),
        action_kind=CausalActionKind.EXECUTE_PROGRAM,
        tool="calculator",
        arguments=(binding.terminal_operation_node_id,),
        effects=execute_effects,
        events=("finance_program_executed",),
        alternatives=(("alternate_operation_01",), ("alternate_operation_02",)),
        target=False,
    )
    close = _step(
        phase="finance_program_closure",
        facts=("All required finance operation nodes have completed.",),
        action_kind=CausalActionKind.EXECUTE_PROGRAM,
        tool="cross_check_evidence",
        arguments=("close_visible_program",),
        effects=(
            _effect(FinanceEffectKind.CLOSE_PROGRAM, "closed"),
            _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
        ),
        events=("finance_program_closed",),
        alternatives=(("recheck_partial_01",), ("recheck_partial_02",)),
        target=False,
    )
    return execute, close


def _verify_step(*, target: bool = False) -> _StepPlan:
    return _step(
        phase="terminal_verification",
        facts=("The finance Program is closed and an exact result is present.",),
        action_kind=CausalActionKind.VERIFY_TERMINAL,
        tool="cross_check_evidence",
        arguments=("verify_visible_result",),
        effects=(
            _effect(FinanceEffectKind.VERIFY_TERMINAL, "verified"),
            _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
        ),
        events=("terminal_verified",),
        alternatives=(("verify_partial_result",), ("verify_unbound_result",)),
        target=target,
    )


def _context_steps(
    depth: ObservationDepth,
    binding: CausalFinanceBinding,
) -> tuple[_StepPlan, ...]:
    index = OBSERVATION_DEPTH_ORDER.index(depth)
    expected = cast(str, binding.expected_operator_id)
    rows = [
        _step(
            phase="operator_selection",
            facts=(f"The visible finance task requires operator {expected}.",),
            action_kind=CausalActionKind.SELECT_OPERATOR,
            tool="calculator",
            arguments=(expected,),
            effects=(
                _effect(FinanceEffectKind.SELECT_OPERATOR, expected),
                _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
            ),
            events=("context_action_selected",),
            alternatives=(("lookup",), ("aggregate",)),
            target=True,
        )
    ]
    if index >= 1:
        rows.append(
            _step(
                phase="primary_input_binding",
                facts=("The first public operand must be bound before execution.",),
                action_kind=CausalActionKind.SELECT_INPUT_BINDING,
                tool="calculator",
                arguments=(binding.input_binding_ids[0],),
                effects=(
                    _effect(
                        FinanceEffectKind.SELECT_INPUT_BINDING,
                        binding.input_binding_ids[0],
                    ),
                    _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
                ),
                events=("context_input_bound",),
                alternatives=(("public_operand_03",), ("public_operand_04",)),
                target=True,
            )
        )
    if index >= 2:
        rows.append(
            _step(
                phase="output_projection_selection",
                facts=("The requested public answer field must be selected.",),
                action_kind=CausalActionKind.SELECT_OUTPUT_PROJECTION,
                tool="calculator",
                arguments=(binding.projection_ids[0],),
                effects=(
                    _effect(FinanceEffectKind.SELECT_PROJECTION, binding.projection_ids[0]),
                    _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
                ),
                events=("context_projection_selected",),
                alternatives=(("public_projection_03",), ("public_projection_04",)),
                target=True,
            )
        )
    if index >= 3:
        rows.append(
            _step(
                phase="secondary_input_binding",
                facts=("A second public operand remains unbound.",),
                action_kind=CausalActionKind.SELECT_INPUT_BINDING,
                tool="calculator",
                arguments=(binding.input_binding_ids[1],),
                effects=(
                    _effect(
                        FinanceEffectKind.SELECT_INPUT_BINDING,
                        binding.input_binding_ids[1],
                    ),
                    _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
                ),
                events=("context_secondary_input_bound",),
                alternatives=(("public_operand_05",), ("public_operand_06",)),
                target=True,
            )
        )
    rows.extend(_execute_and_close_steps(binding))
    rows.append(_verify_step())
    return tuple(rows)


def _reconciliation_steps(
    depth: ObservationDepth,
    binding: CausalFinanceBinding,
    operation: Mapping[str, Any],
) -> tuple[_StepPlan, ...]:
    refs = binding.normalization_reference_ids
    if len(refs) != 2:
        raise ValueError("Reconciliation Finance Core does not expose exactly two references")
    node_by_ref = {
        item["output_symbol"]: item["node_id"]
        for item in operation["nodes"]
        if item["node_kind"] == "normalization"
    }
    rows: list[_StepPlan] = []
    for index, reference in enumerate(refs, start=1):
        rows.append(
            _step(
                phase=f"normalization_emission_{index:02d}",
                facts=("One visible operand requires typed normalization.",),
                action_kind=CausalActionKind.NORMALIZE_OPERAND,
                tool="normalize_metric_unit_period",
                arguments=(reference,),
                effects=(
                    _effect(FinanceEffectKind.PRODUCE_REFERENCE, reference),
                    _effect(FinanceEffectKind.COMPLETE_NODE, node_by_ref[reference]),
                    _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
                ),
                events=("normalization_reference_emitted",),
                emitted_references=(reference,),
                alternatives=(
                    (f"normalization_route_{index + 2:02d}",),
                    (f"normalization_route_{index + 4:02d}",),
                ),
                target=True,
            )
        )
    consumption_count = OBSERVATION_DEPTH_ORDER.index(depth) + 1
    for index in range(consumption_count):
        selected = refs[index % len(refs)]
        consume = refs if consumption_count == 1 else (selected,)
        rows.append(
            _step(
                phase=f"normalized_operand_consumption_{index + 1:02d}",
                facts=("A produced normalized operand is ready for a dependent operation.",),
                action_kind=CausalActionKind.CONSUME_OPERAND,
                tool="calculator",
                arguments=consume,
                effects=tuple(
                    _effect(FinanceEffectKind.CONSUME_REFERENCE, item) for item in consume
                )
                + (_effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),),
                events=("normalization_reference_consumed",),
                consumed_references=consume,
                alternatives=(("operand_route_03",), ("operand_route_04",)),
                target=True,
            )
        )
    rows.extend(_execute_and_close_steps(binding))
    rows.append(_verify_step())
    return tuple(rows)


def _recovery_steps(
    depth: ObservationDepth,
    binding: CausalFinanceBinding,
) -> tuple[_StepPlan, ...]:
    depth_index = OBSERVATION_DEPTH_ORDER.index(depth)
    cycle_count = (1, 1, 2, 3)[depth_index]
    selectors = binding.selector_ids[:cycle_count]
    rows: list[_StepPlan] = []
    if depth_index == 1:
        rows.append(
            _step(
                phase="recovery_input_binding",
                facts=("The public query input must be bound before issuing a selector.",),
                action_kind=CausalActionKind.SELECT_INPUT_BINDING,
                tool="query_structured_fact",
                arguments=(binding.input_binding_ids[0],),
                effects=(
                    _effect(
                        FinanceEffectKind.SELECT_INPUT_BINDING,
                        binding.input_binding_ids[0],
                    ),
                    _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
                ),
                events=("recovery_input_bound",),
                alternatives=(("query_input_03",), ("query_input_04",)),
                target=True,
            )
        )
    for index, selector in enumerate(selectors, start=1):
        code = binding.selector_failure_codes[selector]
        rows.append(
            _step(
                phase=f"selector_attempt_{index:02d}",
                facts=("A visible selector can now be issued to the public finance tool.",),
                action_kind=CausalActionKind.ISSUE_SELECTOR,
                tool="query_structured_fact",
                arguments=(selector,),
                effects=(
                    _effect(FinanceEffectKind.RECORD_FAILURE, code),
                    _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
                ),
                status=CausalTransitionStatus.TYPED_FAILURE,
                public_observation="The public tool returned a typed selector fault.",
                failure_code=code,
                events=("typed_failure_observed",),
                alternatives=(("selector_route_05",), ("selector_route_06",)),
                target=True,
            )
        )
    for index, selector in enumerate(selectors, start=1):
        rows.append(
            _step(
                phase=f"selector_revision_{index:02d}",
                facts=("A matching typed selector fault is visible and can be revised.",),
                action_kind=CausalActionKind.REVISE_SELECTOR,
                tool="query_structured_fact",
                arguments=(selector,),
                effects=(
                    _effect(FinanceEffectKind.REVISE_SELECTOR, selector),
                    _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
                ),
                events=("recovery_succeeded",),
                alternatives=(("selector_route_07",), ("selector_route_08",)),
                target=True,
            )
        )
    rows.extend(_execute_and_close_steps(binding))
    rows.append(_verify_step())
    return tuple(rows)


def _stopping_steps(
    depth: ObservationDepth,
    binding: CausalFinanceBinding,
) -> tuple[_StepPlan, ...]:
    rows = list(_execute_and_close_steps(binding))
    count = OBSERVATION_DEPTH_ORDER.index(depth) + 1
    for index, check_id in enumerate(binding.readiness_check_ids[:count], start=1):
        rows.append(
            _step(
                phase=f"readiness_check_{index:02d}",
                facts=("A public completion condition remains to be checked.",),
                action_kind=CausalActionKind.CHECK_READINESS,
                tool="cross_check_evidence",
                arguments=(check_id,),
                effects=(
                    _effect(FinanceEffectKind.RECORD_READINESS_CHECK, check_id),
                    _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
                ),
                events=("readiness_condition_checked",),
                alternatives=(("readiness_probe_05",), ("readiness_probe_06",)),
                target=False,
            )
        )
    rows.append(_verify_step())
    stop_reference = _ChoicePlan(
        action_kind=CausalActionKind.STOP,
        tool="cross_check_evidence",
        arguments=("stop_after_visible_verification",),
        effects=(
            _effect(FinanceEffectKind.STOP),
            _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
        ),
        status=CausalTransitionStatus.SUCCEEDED,
        public_observation="The verified finance task stopped without a later operation.",
        events=("stopped_after_completion",),
        target_capability_action=True,
    )
    continuations = tuple(
        _ChoicePlan(
            action_kind=CausalActionKind.CONTINUE,
            tool="calculator",
            arguments=(f"postverification_operation_{index:02d}",),
            effects=(
                _effect(FinanceEffectKind.RECORD_POSTCOMPLETION_CALL),
                _effect(FinanceEffectKind.INCREMENT_INVOCATION, "1"),
            ),
            status=CausalTransitionStatus.TASK_INVALID,
            public_observation="A later finance operation violated the completed task boundary.",
            events=("postcompletion_operation_observed",),
            target_capability_action=True,
        )
        for index in (1, 2)
    )
    rows.append(
        _StepPlan(
            phase="verified_stop_decision",
            facts=("Terminal verification has completed and no further operation is required.",),
            reference=stop_reference,
            alternatives=cast(tuple[_ChoicePlan, _ChoicePlan], continuations),
        )
    )
    return tuple(rows)


def _plans(
    family: CapabilityFamily,
    depth: ObservationDepth,
    binding: CausalFinanceBinding,
    operation: Mapping[str, Any],
) -> tuple[_StepPlan, ...]:
    if family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION:
        return _context_steps(depth, binding)
    if family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        return _reconciliation_steps(depth, binding, operation)
    if family == CapabilityFamily.FAILURE_RECOVERY:
        return _recovery_steps(depth, binding)
    return _stopping_steps(depth, binding)


def _action_id(package_id: str, step_index: int, choice_index: int) -> str:
    payload = f"{CANDIDATE_PRESENTATION_SALT}|{package_id}|{step_index}|{choice_index}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:PUBLIC_ACTION_ID_LENGTH]


def _state_token(package_id: str, state_index: int, snapshot_id: str) -> str:
    payload = f"{package_id}|{state_index}|{snapshot_id}|public-state"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:PUBLIC_ACTION_ID_LENGTH]


def _public_candidate(
    *,
    action_id: str,
    presentation_index: int,
    choice: _ChoicePlan,
    padding: str = "",
) -> PublicExecutableDepthCandidate:
    arguments = tuple(
        PublicArgument(name=f"arg_{index:02d}", value=value)
        for index, value in enumerate(choice.arguments, start=1)
    )
    return PublicExecutableDepthCandidate(
        action_id=action_id,
        presentation_index=presentation_index,
        tool=choice.tool,
        arguments=arguments,
        padding=padding,
    )


def _padded_options(
    *,
    package_id: str,
    step_index: int,
    group_index: int,
    depth: ObservationDepth,
    plans: tuple[_ChoicePlan, _ChoicePlan, _ChoicePlan],
) -> tuple[tuple[PublicExecutableDepthCandidate, ...], dict[int, str]]:
    reference_position = (group_index - 1 + OBSERVATION_DEPTH_ORDER.index(depth) + step_index) % 3
    semantic_order = [1, 2]
    semantic_order.insert(reference_position, 0)
    options = tuple(
        _public_candidate(
            action_id=_action_id(package_id, step_index, semantic_index),
            presentation_index=presentation_index,
            choice=plans[semantic_index],
        )
        for presentation_index, semantic_index in enumerate(semantic_order)
    )
    target_length = max(len(canonical_bytes(item.model_dump(mode="json"))) for item in options)
    padded = tuple(
        _public_candidate(
            action_id=item.action_id,
            presentation_index=item.presentation_index,
            choice=plans[semantic_order[item.presentation_index]],
            padding="x" * (target_length - len(canonical_bytes(item.model_dump(mode="json")))),
        )
        for item in options
    )
    lengths = {len(canonical_bytes(item.model_dump(mode="json"))) for item in padded}
    if len(lengths) != 1:
        raise ValueError("public Candidate padding did not equalize canonical encodings")
    return padded, {
        semantic_index: _action_id(package_id, step_index, semantic_index)
        for semantic_index in range(3)
    }


def _host_state_identity(values: dict[str, Any]) -> str:
    provisional = HostExecutableDepthState.model_construct(
        state_id="pending",
        candidate_ids=(),
        reference_candidate_id=None,
        **values,
    )
    return canonical_hash(
        provisional.model_dump(
            mode="json",
            exclude={"state_id", "candidate_ids", "reference_candidate_id"},
        ),
        prefix="host_causal_depth_state:",
    )


@dataclass(frozen=True)
class _StateDraft:
    state_id: str
    values: dict[str, Any]
    plans: tuple[_ChoicePlan, _ChoicePlan, _ChoicePlan]
    action_ids: dict[int, str]
    reference_snapshot: CausalFinanceSnapshot
    alternative_snapshots: tuple[CausalFinanceSnapshot, CausalFinanceSnapshot]


def _terminal_state(
    *,
    package_id: str,
    state_index: int,
    phase: str,
    snapshot: CausalFinanceSnapshot,
    terminal_kind: CausalTerminalKind,
) -> HostExecutableDepthState:
    public = PublicExecutableDepthState(
        state_token=_state_token(package_id, state_index, snapshot.snapshot_id),
        step_index=state_index,
        facts=(PublicFact(name="fact_01", value="The current finance trajectory is terminal."),),
        history=(),
        options=(),
        terminal=True,
    )
    values = {
        "state_index": state_index,
        "host_phase": phase,
        "public_state": public,
        "finance_snapshot": snapshot,
        "terminal_kind": terminal_kind,
    }
    return HostExecutableDepthState(
        state_id=_host_state_identity(values),
        candidate_ids=(),
        reference_candidate_id=None,
        **values,
    )


def _graph(
    *,
    package_id: str,
    predecessor_package_id: str,
    group_index: int,
    family: CapabilityFamily,
    depth: ObservationDepth,
    core: v168_models.LowNuisanceFinanceCore,
    binding: CausalFinanceBinding,
) -> HostExecutableDepthGraph:
    plans = _plans(family, depth, binding, _operation_contract(core))
    reference_snapshots = [initial_snapshot()]
    for plan in plans:
        reference_snapshots.append(
            apply_effects(reference_snapshots[-1], plan.reference.effects, binding)
        )
    drafts: list[_StateDraft] = []
    history: list[str] = []
    for step_index, plan in enumerate(plans):
        choices = (plan.reference, *plan.alternatives)
        options, action_ids = _padded_options(
            package_id=package_id,
            step_index=step_index,
            group_index=group_index,
            depth=depth,
            plans=choices,
        )
        public = PublicExecutableDepthState(
            state_token=_state_token(
                package_id,
                step_index,
                reference_snapshots[step_index].snapshot_id,
            ),
            step_index=step_index,
            facts=tuple(
                PublicFact(name=f"fact_{index:02d}", value=value)
                for index, value in enumerate(plan.facts, start=1)
            ),
            history=tuple(history),
            options=options,
            terminal=False,
        )
        values = {
            "state_index": step_index,
            "host_phase": plan.phase,
            "public_state": public,
            "finance_snapshot": reference_snapshots[step_index],
            "terminal_kind": CausalTerminalKind.NONE,
        }
        alternative_snapshots = cast(
            tuple[CausalFinanceSnapshot, CausalFinanceSnapshot],
            tuple(
                apply_effects(reference_snapshots[step_index], item.effects, binding)
                for item in plan.alternatives
            ),
        )
        drafts.append(
            _StateDraft(
                state_id=_host_state_identity(values),
                values=values,
                plans=choices,
                action_ids=action_ids,
                reference_snapshot=reference_snapshots[step_index + 1],
                alternative_snapshots=alternative_snapshots,
            )
        )
        history.append(plan.reference.public_observation)
    next_index = len(drafts)
    success = _terminal_state(
        package_id=package_id,
        state_index=next_index,
        phase="qualified_success_terminal",
        snapshot=reference_snapshots[-1],
        terminal_kind=CausalTerminalKind.SUCCESS,
    )
    next_index += 1
    alternate_terminals: dict[tuple[int, int], HostExecutableDepthState] = {}
    for step_index, draft in enumerate(drafts):
        for alternative_index, snapshot in enumerate(draft.alternative_snapshots, start=1):
            is_postcompletion = snapshot.postcompletion_violation
            alternate_terminals[(step_index, alternative_index)] = _terminal_state(
                package_id=package_id,
                state_index=next_index,
                phase=f"typed_task_terminal_{step_index:02d}_{alternative_index:02d}",
                snapshot=snapshot,
                terminal_kind=(
                    CausalTerminalKind.POSTCOMPLETION_VIOLATION
                    if is_postcompletion
                    else CausalTerminalKind.TASK_FAILURE
                ),
            )
            next_index += 1
    host_candidates: list[HostExecutableDepthCandidate] = []
    states: list[HostExecutableDepthState] = []
    candidate_ids_by_step: list[tuple[str, str, str]] = []
    for draft in drafts:
        candidates: list[HostExecutableDepthCandidate] = []
        for semantic_index, choice in enumerate(draft.plans):
            semantic_hash = canonical_hash(
                {
                    "action_kind": choice.action_kind.value,
                    "tool": choice.tool,
                    "arguments": choice.arguments,
                    "effects": tuple(item.model_dump(mode="json") for item in choice.effects),
                    "status": choice.status.value,
                    "events": choice.events,
                },
                prefix="causal_semantic_choice:",
            )
            values = {
                "host_state_id": draft.state_id,
                "public_action_id": draft.action_ids[semantic_index],
                "action_kind": choice.action_kind,
                "reference_action": semantic_index == 0,
                "target_capability_action": choice.target_capability_action,
                "semantic_choice_hash": semantic_hash,
            }
            candidates.append(
                cast(
                    HostExecutableDepthCandidate,
                    _make_core_model(
                        HostExecutableDepthCandidate,
                        values,
                        field="candidate_id",
                        prefix="host_causal_depth_candidate:",
                    ),
                )
            )
        candidate_ids = cast(tuple[str, str, str], tuple(item.candidate_id for item in candidates))
        states.append(
            HostExecutableDepthState(
                state_id=draft.state_id,
                candidate_ids=candidate_ids,
                reference_candidate_id=candidate_ids[0],
                **draft.values,
            )
        )
        host_candidates.extend(candidates)
        candidate_ids_by_step.append(candidate_ids)
    transitions: list[HostExecutableDepthTransition] = []
    for step_index, (draft, candidate_ids) in enumerate(
        zip(drafts, candidate_ids_by_step, strict=True)
    ):
        next_reference_state = (
            states[step_index + 1].state_id if step_index + 1 < len(states) else success.state_id
        )
        for semantic_index, (choice, candidate_id) in enumerate(
            zip(draft.plans, candidate_ids, strict=True)
        ):
            to_state_id = (
                next_reference_state
                if semantic_index == 0
                else alternate_terminals[(step_index, semantic_index)].state_id
            )
            values = {
                "from_state_id": draft.state_id,
                "candidate_id": candidate_id,
                "to_state_id": to_state_id,
                "status": choice.status,
                "public_observation": choice.public_observation,
                "failure_code": choice.failure_code,
                "effects": choice.effects,
                "emitted_event_types": tuple(sorted(choice.events)),
                "emitted_reference_ids": tuple(sorted(choice.emitted_references)),
                "consumed_reference_ids": tuple(sorted(choice.consumed_references)),
            }
            transitions.append(
                cast(
                    HostExecutableDepthTransition,
                    _make_core_model(
                        HostExecutableDepthTransition,
                        values,
                        field="transition_id",
                        prefix="host_causal_depth_transition:",
                    ),
                )
            )
    required_events = dict(
        sorted(Counter(event for plan in plans for event in plan.reference.events).items())
    )
    values = {
        "package_id": package_id,
        "predecessor_package_id": predecessor_package_id,
        "finance_core_id": core.core_id,
        "base_operational_task_package_id": core.operational_record.task_package.package_id,
        "finance_binding_id": binding.binding_id,
        "capability_family": family,
        "depth": depth,
        "initial_state_id": states[0].state_id,
        "success_terminal_state_id": success.state_id,
        "states": tuple(
            sorted(
                (*states, success, *alternate_terminals.values()),
                key=lambda item: item.state_index,
            )
        ),
        "candidates": tuple(host_candidates),
        "transitions": tuple(transitions),
        "required_event_multiplicities": required_events,
        "reference_path_candidate_ids": tuple(item[0] for item in candidate_ids_by_step),
    }
    return cast(
        HostExecutableDepthGraph,
        _make_core_model(
            HostExecutableDepthGraph,
            values,
            field="graph_id",
            prefix="host_causal_depth_graph:",
        ),
    )


def _witness_contract(
    graph: HostExecutableDepthGraph,
) -> CausalDepthWitnessContract:
    values = {
        "graph_id": graph.graph_id,
        "finance_binding_id": graph.finance_binding_id,
        "capability_family": graph.capability_family,
        "depth": graph.depth,
        "required_event_multiplicities": graph.required_event_multiplicities,
    }
    return cast(
        CausalDepthWitnessContract,
        _make_core_model(
            CausalDepthWitnessContract,
            values,
            field="contract_id",
            prefix="causal_depth_witness_contract:",
        ),
    )


def _verifier_contract(
    witness: CausalDepthWitnessContract,
    binding: CausalFinanceBinding,
) -> CausalDepthVerifierContract:
    values = {
        "witness_contract_id": witness.contract_id,
        "finance_binding_id": binding.binding_id,
        "task_program_id": binding.task_program_id,
        "task_verifier_binding_id": binding.task_verifier_binding_id,
        "counterfactual_kinds": tuple(CausalCounterfactualKind),
    }
    return cast(
        CausalDepthVerifierContract,
        _make_core_model(
            CausalDepthVerifierContract,
            values,
            field="contract_id",
            prefix="causal_depth_verifier_contract:",
        ),
    )


def _prompt_projection(
    *,
    package_id: str,
    graph: HostExecutableDepthGraph,
    state: HostExecutableDepthState,
    contract: DepthPromptProjectionContract,
    condition_id: str,
    public_task: dict[str, Any],
) -> PublicPromptProjection:
    semantic_payload = {
        "state": state.public_state.model_dump(mode="json"),
        "task": public_task,
    }
    rendered = canonical_bytes(semantic_payload)
    values = {
        "package_id": package_id,
        "graph_id": graph.graph_id,
        "host_state_id": state.state_id,
        "contract_id": contract.contract_id,
        "fixed_generation_condition_id": condition_id,
        "semantic_payload": semantic_payload,
        "semantic_payload_hash": canonical_hash(
            semantic_payload,
            prefix="causal_depth_public_prompt_payload:",
        ),
        "rendered_prompt_hash": hashlib.sha256(rendered).hexdigest(),
        "rendered_prompt_bytes": len(rendered),
        "recursive_leakage_findings": scan_public_leakage(semantic_payload),
    }
    return cast(
        PublicPromptProjection,
        _make_core_model(
            PublicPromptProjection,
            values,
            field="projection_id",
            prefix="causal_depth_public_prompt_projection:",
        ),
    )


def _prompt_binding(
    *,
    package_id: str,
    graph: HostExecutableDepthGraph,
    contract: DepthPromptProjectionContract,
    policy: models.CandidatePresentationPolicy,
    condition_id: str,
    public_task: dict[str, Any],
) -> models.CausalPromptBinding:
    projections = tuple(
        _prompt_projection(
            package_id=package_id,
            graph=graph,
            state=state,
            contract=contract,
            condition_id=condition_id,
            public_task=public_task,
        )
        for state in graph.states
        if state.terminal_kind == CausalTerminalKind.NONE
    )
    values = {
        "package_id": package_id,
        "graph_id": graph.graph_id,
        "projection_contract_id": contract.contract_id,
        "presentation_policy_id": policy.policy_id,
        "fixed_generation_condition_id": condition_id,
        "public_task_projection_hash": canonical_hash(
            public_task,
            prefix="causal_public_task_projection:",
        ),
        "projections": projections,
        "prompt_projection_count": len(projections),
    }
    return cast(
        models.CausalPromptBinding,
        _make_model(
            models.CausalPromptBinding,
            values,
            field="binding_id",
            prefix="causal_depth_prompt_binding:",
        ),
    )


def _package_semantic_id(
    *,
    predecessor_package_id: str,
    group_key: str,
    family: CapabilityFamily,
    depth: ObservationDepth,
    finance_core_id: str,
    condition_id: str,
) -> str:
    return canonical_hash(
        {
            "predecessor_package_id": predecessor_package_id,
            "group_key": group_key,
            "capability_family": family.value,
            "depth": depth.value,
            "finance_core_id": finance_core_id,
            "fixed_generation_condition_id": condition_id,
            "schema_version": models.V26_CAUSAL_DEPTH_HARDENING_VERSION,
        },
        prefix="finance_v26_causal_depth_package:",
    )


def _group_key(group: v168_models.ExecutableDepthGroup) -> str:
    return canonical_hash(
        {
            "predecessor_group_id": group.group_id,
            "capability_family": group.capability_family.value,
            "finance_core_id": group.finance_core_id,
            "schema_version": models.V26_CAUSAL_DEPTH_HARDENING_VERSION,
        },
        prefix="finance_v26_causal_depth_group_key:",
    )


def _build_package(
    *,
    predecessor: v168_models.ExecutableDepthPackage,
    predecessor_group: v168_models.ExecutableDepthGroup,
    core: v168_models.LowNuisanceFinanceCore,
    binding: CausalFinanceBinding,
    program_verification: ProgramVerification,
    projection_contract: DepthPromptProjectionContract,
    presentation_policy: models.CandidatePresentationPolicy,
    condition_id: str,
) -> models.CausalDepthPackage:
    group_key = _group_key(predecessor_group)
    package_id = _package_semantic_id(
        predecessor_package_id=predecessor.package_id,
        group_key=group_key,
        family=predecessor.capability_family,
        depth=predecessor.depth,
        finance_core_id=core.core_id,
        condition_id=condition_id,
    )
    graph = _graph(
        package_id=package_id,
        predecessor_package_id=predecessor.package_id,
        group_index=predecessor_group.group_index,
        family=predecessor.capability_family,
        depth=predecessor.depth,
        core=core,
        binding=binding,
    )
    witness_contract = _witness_contract(graph)
    verifier_contract = _verifier_contract(witness_contract, binding)
    baseline = static_audit.compile_baseline_witness(
        package_id=package_id,
        graph=graph,
        binding=binding,
        witness_contract=witness_contract,
        verifier_contract=verifier_contract,
        program_verification=program_verification,
    )
    target_load = static_audit.compute_target_load(package_id, graph, baseline)
    nuisance_values = {
        "predecessor_measurement_id": predecessor.nuisance.measurement_id,
        "finance_core_id": core.core_id,
        "base_operational_task_package_id": core.operational_record.task_package.package_id,
    }
    nuisance = cast(
        models.CausalNuisanceBinding,
        _make_model(
            models.CausalNuisanceBinding,
            nuisance_values,
            field="binding_id",
            prefix="causal_depth_nuisance_binding:",
        ),
    )
    prompt = _prompt_binding(
        package_id=package_id,
        graph=graph,
        contract=projection_contract,
        policy=presentation_policy,
        condition_id=condition_id,
        public_task=_public_task_projection(core),
    )
    signature_values = {
        "package_id": package_id,
        "predecessor_package_id": predecessor.package_id,
        "group_key": group_key,
        "finance_core_id": core.core_id,
        "finance_binding_id": binding.binding_id,
        "graph_id": graph.graph_id,
        "witness_contract_id": witness_contract.contract_id,
        "verifier_contract_id": verifier_contract.contract_id,
        "baseline_witness_id": baseline.witness_id,
        "target_load_id": target_load.load_id,
        "nuisance_binding_id": nuisance.binding_id,
        "prompt_binding_id": prompt.binding_id,
        "projection_contract_id": projection_contract.contract_id,
        "presentation_policy_id": presentation_policy.policy_id,
        "host_graph_hash": canonical_hash(
            graph.model_dump(mode="json"),
            prefix="causal_host_graph_bytes:",
        ),
        "public_projection_hash": canonical_hash(
            tuple(item.projection_id for item in prompt.projections),
            prefix="causal_public_projection_set:",
        ),
        "task_validity_report_id": baseline.task_validity.report_id,
        "mechanism_validity_report_id": baseline.mechanism_validity.report_id,
        "qualified_validity_report_id": baseline.qualified_validity.report_id,
    }
    signature = cast(
        models.CausalDepthSignature,
        _make_model(
            models.CausalDepthSignature,
            signature_values,
            field="signature_id",
            prefix="causal_depth_package_signature:",
        ),
    )
    package_values = {
        "package_id": package_id,
        "predecessor_package_id": predecessor.package_id,
        "predecessor_group_id": predecessor_group.group_id,
        "group_key": group_key,
        "capability_family": predecessor.capability_family,
        "depth": predecessor.depth,
        "finance_core_id": core.core_id,
        "fixed_generation_condition_id": condition_id,
        "finance_binding": binding,
        "graph": graph,
        "witness_contract": witness_contract,
        "verifier_contract": verifier_contract,
        "baseline_witness": baseline,
        "target_load": target_load,
        "nuisance_binding": nuisance,
        "prompt_binding": prompt,
        "signature": signature,
    }
    return cast(
        models.CausalDepthPackage,
        _make_model(
            models.CausalDepthPackage,
            package_values,
            field="artifact_id",
            prefix="finance_v26_causal_depth_package_artifact:",
        ),
    )


def _development_catalog(
    *,
    predecessor_report: v168_models.ExecutableDepthRematerializationReport,
    predecessor_catalog: v168_models.ExecutableDepthCatalog,
    receipt: v168_models.SealedConfirmationReceipt,
    projection_contract: DepthPromptProjectionContract,
    presentation_policy: models.CandidatePresentationPolicy,
) -> tuple[models.CausalDevelopmentCatalog, dict[str, ProgramVerification]]:
    condition_ids = {
        package.prompt_binding.fixed_generation_condition_id
        for group in predecessor_catalog.groups
        for package in group.packages
    }
    if len(condition_ids) != 1:
        raise ValueError("v26.168 Development packages cross generation conditions")
    condition_id = next(iter(condition_ids))
    cores = {item.core_id: item for item in predecessor_catalog.finance_cores}
    groups: list[models.CausalDepthGroup] = []
    program_verifications: dict[str, ProgramVerification] = {}
    for predecessor_group in predecessor_catalog.groups:
        core = cores[predecessor_group.finance_core_id]
        verification = predecessor_group.packages[0].variant_program_verification
        if any(
            item.variant_program_verification != verification for item in predecessor_group.packages
        ):
            raise ValueError("v26.168 Group changes independent Program verification")
        binding = _finance_binding(core, verification)
        program_verifications[core.core_id] = verification
        packages = tuple(
            _build_package(
                predecessor=item,
                predecessor_group=predecessor_group,
                core=core,
                binding=binding,
                program_verification=verification,
                projection_contract=projection_contract,
                presentation_policy=presentation_policy,
                condition_id=condition_id,
            )
            for item in predecessor_group.packages
        )
        group_values = {
            "group_key": _group_key(predecessor_group),
            "predecessor_group_id": predecessor_group.group_id,
            "capability_family": predecessor_group.capability_family,
            "finance_core_id": core.core_id,
            "packages": packages,
        }
        groups.append(
            cast(
                models.CausalDepthGroup,
                _make_model(
                    models.CausalDepthGroup,
                    group_values,
                    field="group_id",
                    prefix="finance_v26_causal_depth_group:",
                ),
            )
        )
    catalog_values = {
        "predecessor_catalog_id": predecessor_catalog.catalog_id,
        "predecessor_report_id": predecessor_report.report_id,
        "sealed_confirmation_receipt_id": receipt.receipt_id,
        "projection_contract_id": projection_contract.contract_id,
        "presentation_policy_id": presentation_policy.policy_id,
        "fixed_generation_condition_id": condition_id,
        "groups": tuple(groups),
    }
    catalog = cast(
        models.CausalDevelopmentCatalog,
        _make_model(
            models.CausalDevelopmentCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_causal_development_catalog:",
        ),
    )
    return catalog, program_verifications


def _interpretation(
    catalog: models.CausalDevelopmentCatalog,
) -> models.OperationalWitnessInterpretation:
    packages = tuple(package for group in catalog.groups for package in group.packages)
    if len({item.baseline_witness.witness_id for item in packages}) != 32:
        raise ValueError("causal depth Witness set is not package-distinct")
    return cast(
        models.OperationalWitnessInterpretation,
        _make_model(
            models.OperationalWitnessInterpretation,
            {},
            field="audit_id",
            prefix="finance_v26_operational_witness_interpretation:",
        ),
    )


def _transition(
    *,
    predecessor_transition_id: str,
    catalog: models.CausalDevelopmentCatalog,
    projection_contract: DepthPromptProjectionContract,
    presentation_policy: models.CandidatePresentationPolicy,
    static: models.CausalDepthStaticAudit,
) -> models.CausalDepthTransition:
    values = {
        "predecessor_transition_id": predecessor_transition_id,
        "development_catalog_id": catalog.catalog_id,
        "projection_contract_id": projection_contract.contract_id,
        "presentation_policy_id": presentation_policy.policy_id,
        "static_audit_id": static.audit_id,
        "next_stage": ("capability_observation_executable_depth_development_runner_preflight_only"),
    }
    return cast(
        models.CausalDepthTransition,
        _make_model(
            models.CausalDepthTransition,
            values,
            field="transition_id",
            prefix="finance_v26_causal_depth_transition:",
        ),
    )


def _detail_files(output_dir: Path) -> tuple[models.FileBinding, ...]:
    rows = []
    for path in sorted(output_dir.iterdir()):
        if not path.is_file() or path.name == "report.json":
            continue
        source_kind = (
            "external_audit_input"
            if path.name == "external_joint_audit_input.txt"
            else "formal_output"
        )
        rows.append(
            _file_binding(
                path=path,
                relative_path=path.name,
                source_kind=source_kind,
            )
        )
    return tuple(rows)


def build(
    *,
    package_root: Path,
    output_dir: Path,
    external_audit_path: Path,
) -> models.BuildProducts:
    package_root = _resolve_package_root(package_root)
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("v26.169 formal output directory is not empty")
    authorization = _authorization(external_audit_path)
    source_root = _transitive_source_root(package_root)
    predecessor = _predecessor_integrity(package_root)
    source_replay = _source_replay(
        package_root=package_root,
        external_audit_path=external_audit_path,
        authorization=authorization,
        predecessor=predecessor.audit,
        source_root=source_root,
    )
    defect = _defect_reproduction(predecessor.catalog)
    projection_contract = _projection_contract()
    presentation_policy = _presentation_policy()
    development, program_verifications = _development_catalog(
        predecessor_report=predecessor.report,
        predecessor_catalog=predecessor.catalog,
        receipt=predecessor.receipt,
        projection_contract=projection_contract,
        presentation_policy=presentation_policy,
    )
    packages = tuple(package for group in development.groups for package in group.packages)
    leakage = static_audit.build_leakage_audit(
        development,
        projection_contract,
        presentation_policy,
    )
    runtime = static_audit.build_runtime_audit(development)
    counterfactuals = static_audit.build_counterfactual_catalog(
        packages,
        program_verifications,
    )
    parent_binding = static_audit.build_parent_binding_audit(development)
    interpretation = _interpretation(development)
    static = static_audit.build_static_audit(
        catalog=development,
        leakage=leakage,
        runtime=runtime,
        counterfactuals=counterfactuals,
        parent_binding=parent_binding,
        source_root=source_root,
        interpretation=interpretation,
    )
    transition = _transition(
        predecessor_transition_id=predecessor.transition.transition_id,
        catalog=development,
        projection_contract=projection_contract,
        presentation_policy=presentation_policy,
        static=static,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(
        output_dir / "external_joint_audit_input.txt",
        external_audit_path.read_bytes(),
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("predecessor_integrity_audit.json", predecessor.audit),
        ("source_replay_audit.json", source_replay),
        ("v168_defect_reproduction_audit.json", defect),
        ("depth_prompt_projection_contract.json", projection_contract),
        ("candidate_presentation_policy.json", presentation_policy),
        ("causal_development_catalog.json", development),
        ("public_projection_leakage_audit.json", leakage),
        ("causal_runtime_audit.json", runtime),
        ("causal_counterfactual_catalog.json", counterfactuals),
        ("parent_binding_audit.json", parent_binding),
        ("operational_witness_interpretation.json", interpretation),
        ("causal_depth_static_audit.json", static),
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
        "predecessor_integrity_audit_id": predecessor.audit.audit_id,
        "defect_reproduction_audit_id": defect.audit_id,
        "projection_contract_id": projection_contract.contract_id,
        "presentation_policy_id": presentation_policy.policy_id,
        "development_catalog_id": development.catalog_id,
        "leakage_audit_id": leakage.audit_id,
        "runtime_audit_id": runtime.audit_id,
        "counterfactual_catalog_id": counterfactuals.catalog_id,
        "parent_binding_audit_id": parent_binding.audit_id,
        "operational_witness_interpretation_id": interpretation.audit_id,
        "static_audit_id": static.audit_id,
        "transition_id": transition.transition_id,
        "detail_files": details,
        "next_stage": transition.next_stage,
    }
    report = cast(
        models.CausalDepthHardeningReport,
        _make_model(
            models.CausalDepthHardeningReport,
            report_values,
            field="report_id",
            prefix="finance_v26_causal_depth_hardening_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        transitive_source_root=source_root,
        source_replay=source_replay,
        predecessor_integrity=predecessor.audit,
        defect_reproduction=defect,
        projection_contract=projection_contract,
        presentation_policy=presentation_policy,
        development_catalog=development,
        leakage_audit=leakage,
        runtime_audit=runtime,
        counterfactual_catalog=counterfactuals,
        parent_binding_audit=parent_binding,
        operational_witness_interpretation=interpretation,
        static_audit=static,
        transition=transition,
        report=report,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--external-audit", type=Path, required=True)
    args = parser.parse_args()
    package_root = _resolve_package_root(args.package_root)
    output_dir = args.output_dir or package_root / OUTPUT_DIR
    products = build(
        package_root=package_root,
        output_dir=output_dir,
        external_audit_path=args.external_audit,
    )
    print(json.dumps(products.report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
