from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel

from trusted_synthesis.core.task.capability_observation import (
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.causal_capability_depth import (
    FinanceEffectKind,
    PublicPromptProjection,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import (
    OPERATOR_CATALOG,
    HostSemanticChoice,
    PresentedPublicCandidate,
    PublicDecisionState,
    PublicOperationPayload,
    PublicSemanticPrompt,
    PublicSemanticTask,
    TargetComponent,
    candidate_grounding_findings,
    canonical_bytes,
    default_semantic_runtime_binding,
    execute_semantic_runtime,
    project_public_semantic_task,
    public_only_select_action,
    public_record_from_evidence,
    resolve_public_operator,
    resolve_required_record_handles,
    resolve_rule_record,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization as v168,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as v168_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_projection_causal_runtime_hardening as v169,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_projection_causal_runtime_models as v169_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_semantic_execution_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_semantic_execution_static_audit as static_audit,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_170_public_semantic_execution_hardening_v3_20260828"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_170_public_semantic_execution_hardening_v3_20260828"
)
EXPECTED_REVIEW_SHA256: Final = "1dd7e35803ce73bfd7d9be3517399c6e416d6aa4f7504276fdad38ceb6131d85"
EXPECTED_REVIEW_BYTE_COUNT: Final = 25_632
AUTHORIZED_STAGE: Final = (
    "capability_observation_public_semantic_sufficiency_and_task_execution_hardening_only"
)
PRESENTATION_SALT: Final = "finance-v26.170-variant-replica-state-presentation-v1"
V169_DIR: Final = v169.OUTPUT_DIR
V168_DIR: Final = v168.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/public_semantic_capability_depth.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_public_semantic_execution_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_public_semantic_execution_static_audit.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_public_semantic_execution_hardening.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.170 cannot resolve the trusted_data_synthesis package root")


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


def _write(path: Path, value: Any) -> None:
    if path.exists():
        raise ValueError(f"v26.170 immutable output already exists:{path}")
    path.write_text(
        json.dumps(
            _json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.170 immutable output already exists:{path}")
    path.write_bytes(payload)


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
    return model_type(
        **{field: models.identity(provisional, field, prefix)},
        **values,
    )


def _make_core_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    identity = canonical_hash(
        provisional.model_dump(mode="json", exclude={field}),
        prefix=prefix,
    )
    return model_type(**{field: identity}, **values)


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
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT or _sha256(path) != EXPECTED_REVIEW_SHA256:
        raise ValueError("v26.170 external audit input does not match authorization")
    values = {
        "review_sha256": EXPECTED_REVIEW_SHA256,
        "review_byte_count": EXPECTED_REVIEW_BYTE_COUNT,
        "authorized_stage": AUTHORIZED_STAGE,
    }
    return cast(
        models.ExternalAuditAuthorization,
        _make_model(
            models.ExternalAuditAuthorization,
            values,
            field="authorization_id",
            prefix="finance_v26_public_semantic_external_audit_authorization:",
        ),
    )


def _module_name(relative_path: str) -> str:
    parts = Path(relative_path).with_suffix("").parts
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
        raise ValueError(f"v26.170 unresolved trusted_synthesis imports:{sorted(unresolved)}")
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
            prefix="finance_v26_public_semantic_transitive_source_root:",
        ),
    )


@dataclass(frozen=True)
class _PredecessorProducts:
    audit: models.PredecessorIntegrityAudit
    report: v169_models.CausalDepthHardeningReport
    catalog: v169_models.CausalDevelopmentCatalog
    transition: v169_models.CausalDepthTransition
    v168_catalog: v168_models.ExecutableDepthCatalog


def _predecessor_integrity(package_root: Path) -> _PredecessorProducts:
    root = package_root / V169_DIR
    report = v169_models.CausalDepthHardeningReport.model_validate(_load(root / "report.json"))
    catalog = v169_models.CausalDevelopmentCatalog.model_validate(
        _load(root / "causal_development_catalog.json")
    )
    transition = v169_models.CausalDepthTransition.model_validate(
        _load(root / "prospective_transition_contract.json")
    )
    if report.status != "passed" or report.next_stage != transition.next_stage:
        raise ValueError("v26.169 predecessor report is not a passed static result")
    paths = tuple(sorted(path for path in root.iterdir() if path.is_file()))
    if len(paths) != 17:
        raise ValueError("v26.169 authoritative Root file count changed")
    detail_by_name = {item.relative_path: item for item in report.detail_files}
    for path in paths:
        if path.name == "report.json":
            continue
        binding = detail_by_name[path.name]
        if binding.byte_count != path.stat().st_size or binding.sha256 != _sha256(path):
            raise ValueError(f"v26.169 predecessor file changed:{path.name}")
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=str(path.relative_to(package_root)),
            source_kind="v26_169_frozen_output",
        )
        for path in paths
    )
    audit_values = {
        "predecessor_report_id": report.report_id,
        "predecessor_catalog_id": catalog.catalog_id,
        "predecessor_transition_id": transition.transition_id,
        "bindings": bindings,
    }
    audit = cast(
        models.PredecessorIntegrityAudit,
        _make_model(
            models.PredecessorIntegrityAudit,
            audit_values,
            field="audit_id",
            prefix="finance_v26_public_semantic_predecessor_integrity:",
        ),
    )
    v168_catalog = v168_models.ExecutableDepthCatalog.model_validate(
        _load(package_root / V168_DIR / "development_executable_depth_catalog.json")
    )
    return _PredecessorProducts(
        audit=audit,
        report=report,
        catalog=catalog,
        transition=transition,
        v168_catalog=v168_catalog,
    )


def _rehash_v169_public_task_mutation(
    catalog: v169_models.CausalDevelopmentCatalog,
) -> bool:
    group = catalog.groups[0]
    package = group.packages[0]
    projection = package.prompt_binding.projections[0]
    payload = copy.deepcopy(projection.semantic_payload)
    payload["task"]["instruction"] = "Rehashed crossed public Task instruction."
    rendered = canonical_bytes(payload)
    projection_values = projection.model_dump(mode="python", exclude={"projection_id"})
    projection_values.update(
        {
            "semantic_payload": payload,
            "semantic_payload_hash": canonical_hash(
                payload,
                prefix="causal_depth_public_prompt_payload:",
            ),
            "rendered_prompt_hash": hashlib.sha256(rendered).hexdigest(),
            "rendered_prompt_bytes": len(rendered),
        }
    )
    mutated_projection = cast(
        PublicPromptProjection,
        _make_core_model(
            PublicPromptProjection,
            projection_values,
            field="projection_id",
            prefix="causal_depth_public_prompt_projection:",
        ),
    )
    projections = tuple(
        mutated_projection if item.projection_id == projection.projection_id else item
        for item in package.prompt_binding.projections
    )
    binding_values = package.prompt_binding.model_dump(mode="python", exclude={"binding_id"})
    binding_values["projections"] = projections
    mutated_binding = cast(
        v169_models.CausalPromptBinding,
        _make_model(
            v169_models.CausalPromptBinding,
            binding_values,
            field="binding_id",
            prefix="causal_depth_prompt_binding:",
        ),
    )
    signature_values = package.signature.model_dump(mode="python", exclude={"signature_id"})
    signature_values.update(
        {
            "prompt_binding_id": mutated_binding.binding_id,
            "public_projection_hash": canonical_hash(
                tuple(item.projection_id for item in projections),
                prefix="causal_public_projection_set:",
            ),
        }
    )
    signature = cast(
        v169_models.CausalDepthSignature,
        _make_model(
            v169_models.CausalDepthSignature,
            signature_values,
            field="signature_id",
            prefix="causal_depth_package_signature:",
        ),
    )
    package_values = package.model_dump(mode="python", exclude={"artifact_id"})
    package_values.update({"prompt_binding": mutated_binding, "signature": signature})
    mutated_package = cast(
        v169_models.CausalDepthPackage,
        _make_model(
            v169_models.CausalDepthPackage,
            package_values,
            field="artifact_id",
            prefix="finance_v26_causal_depth_package_artifact:",
        ),
    )
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    group_values["packages"] = tuple(
        mutated_package if item.package_id == package.package_id else item
        for item in group.packages
    )
    mutated_group = cast(
        v169_models.CausalDepthGroup,
        _make_model(
            v169_models.CausalDepthGroup,
            group_values,
            field="group_id",
            prefix="finance_v26_causal_depth_group:",
        ),
    )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    catalog_values["groups"] = tuple(
        mutated_group if item.group_id == group.group_id else item for item in catalog.groups
    )
    try:
        _make_model(
            v169_models.CausalDevelopmentCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_causal_development_catalog:",
        )
    except ValueError:
        return False
    return True


def _semantic_value_pairs(public: Mapping[str, Any]) -> tuple[bytes, ...]:
    operation = public["metadata"]["agent_contract_guidance"]["public_operation_execution_contract"]
    return tuple(
        sorted(
            {
                canonical_bytes(constraint["value"])
                for variable in operation["variables"]
                for rule in variable["resolution_rules"]
                for constraint in rule["equals"]
                if constraint.get("value") is not None
            }
        )
    )


def _defect_audit(
    predecessor: _PredecessorProducts,
) -> models.V169SemanticDefectAudit:
    v169_groups = {item.finance_core_id: item for item in predecessor.catalog.groups}
    instruction_exact = 0
    alias_retained = 0
    alias_count = 0
    period_retained = 0
    period_count = 0
    rule_retained = 0
    rule_count = 0
    task_hashes: set[str] = set()
    for core in predecessor.v168_catalog.finance_cores:
        package = v169_groups[core.core_id].packages[0]
        projected = package.prompt_binding.projections[0].semantic_payload["task"]
        encoded = canonical_bytes(projected)
        public = core.operational_record.task_package.task.public.model_dump(mode="json")
        instruction_exact += projected.get("instruction") == public["instruction"]
        aliases = tuple(public["retrieval_scope"]["aliases"])
        periods = tuple(public["retrieval_scope"]["partial_constraints"]["period_labels"])
        alias_count += len(aliases)
        period_count += len(periods)
        alias_retained += sum(canonical_bytes(item) in encoded for item in aliases)
        period_retained += sum(canonical_bytes(item) in encoded for item in periods)
        pairs = _semantic_value_pairs(public)
        rule_count += len(pairs)
        rule_retained += sum(item in encoded for item in pairs)
        task_hashes.add(package.prompt_binding.public_task_projection_hash)
    action_states = 0
    externally_bound = 0
    none_bound = 0
    indexed = 0
    reference_minimum = 0
    set_expected = 0
    alternatives = 0
    task_invalid = 0
    terminate_invalid = 0
    set_alternate = 0
    target_d0: dict[CapabilityFamily, int] = {}
    non_target_d0: dict[CapabilityFamily, int] = {}
    for group in predecessor.catalog.groups:
        d0 = group.packages[0]
        candidates = {item.candidate_id: item for item in d0.graph.candidates}
        target_d0[group.capability_family] = sum(
            candidates[cast(str, state.reference_candidate_id)].target_capability_action
            for state in d0.graph.states
            if state.reference_candidate_id is not None
        )
        non_target_d0[group.capability_family] = sum(
            not candidates[cast(str, state.reference_candidate_id)].target_capability_action
            for state in d0.graph.states
            if state.reference_candidate_id is not None
        )
        for package in group.packages:
            candidate_by_id = {item.candidate_id: item for item in package.graph.candidates}
            transition_by_candidate = {
                item.candidate_id: item for item in package.graph.transitions
            }
            projection_by_state = {
                item.host_state_id: item for item in package.prompt_binding.projections
            }
            for state in package.graph.states:
                if state.reference_candidate_id is None:
                    continue
                action_states += 1
                projection = projection_by_state[state.state_id]
                outside = copy.deepcopy(projection.semantic_payload)
                options = outside["state"].pop("options")
                outside_bytes = canonical_bytes(outside)
                reference = candidate_by_id[state.reference_candidate_id]
                reference_option = next(
                    item for item in options if item["action_id"] == reference.public_action_id
                )
                reference_values = tuple(
                    canonical_bytes(item["value"]) for item in reference_option["arguments"]
                )
                externally_bound += bool(reference_values) and all(
                    item in outside_bytes for item in reference_values
                )
                candidate_values = tuple(
                    canonical_bytes(argument["value"])
                    for option in options
                    for argument in option["arguments"]
                )
                none_bound += bool(candidate_values) and not any(
                    item in outside_bytes for item in candidate_values
                )
                indexed_values = [
                    int(match.group(1))
                    for option in options
                    for argument in option["arguments"]
                    if (match := re.search(r"_([0-9]+)$", str(argument["value"])))
                ]
                reference_indexes = [
                    int(match.group(1))
                    for argument in reference_option["arguments"]
                    if (match := re.search(r"_([0-9]+)$", str(argument["value"])))
                ]
                if indexed_values:
                    indexed += 1
                    reference_minimum += min(reference_indexes) == min(indexed_values)
            for candidate in package.graph.candidates:
                transition = transition_by_candidate[candidate.candidate_id]
                if candidate.reference_action:
                    set_expected += any(
                        item.kind == FinanceEffectKind.SET_EXPECTED_RESULT
                        for item in transition.effects
                    )
                    continue
                alternatives += 1
                task_invalid += transition.status.value == "task_invalid"
                terminate_invalid += candidate.action_kind.value == "terminate_invalid"
                set_alternate += any(
                    item.kind == FinanceEffectKind.SET_ALTERNATE_RESULT
                    for item in transition.effects
                )
    values = {
        "original_public_instruction_exact_count": instruction_exact,
        "registered_alias_value_retained_count": alias_retained,
        "registered_alias_value_count": alias_count,
        "registered_period_value_retained_count": period_retained,
        "registered_period_value_count": period_count,
        "resolution_rule_value_retained_count": rule_retained,
        "resolution_rule_value_count": rule_count,
        "unique_public_task_projection_hash_count": len(task_hashes),
        "action_state_count": action_states,
        "reference_parameter_externally_bound_state_count": externally_bound,
        "no_candidate_parameter_externally_bound_state_count": none_bound,
        "indexed_token_state_count": indexed,
        "reference_index_minimum_state_count": reference_minimum,
        "set_expected_result_effect_count": set_expected,
        "nonreference_alternative_count": alternatives,
        "task_invalid_alternative_count": task_invalid,
        "terminate_invalid_alternative_count": terminate_invalid,
        "set_alternate_result_effect_count": set_alternate,
        "d0_target_state_count_by_family": target_d0,
        "d0_non_target_state_count_by_family": non_target_d0,
        "rehashed_public_task_parent_mutation_accepted": _rehash_v169_public_task_mutation(
            predecessor.catalog
        ),
    }
    return cast(
        models.V169SemanticDefectAudit,
        _make_model(
            models.V169SemanticDefectAudit,
            values,
            field="audit_id",
            prefix="finance_v26_v169_public_semantic_execution_defect_audit:",
        ),
    )


def _projection_contract() -> models.PublicSemanticProjectionContract:
    return cast(
        models.PublicSemanticProjectionContract,
        _make_model(
            models.PublicSemanticProjectionContract,
            {},
            field="contract_id",
            prefix="public_semantic_projection_contract:",
        ),
    )


def _presentation_policy() -> models.ReplicaPresentationPolicy:
    values = {
        "preoutcome_fixed_salt_sha256": hashlib.sha256(PRESENTATION_SALT.encode()).hexdigest()
    }
    return cast(
        models.ReplicaPresentationPolicy,
        _make_model(
            models.ReplicaPresentationPolicy,
            values,
            field="policy_id",
            prefix="public_semantic_replica_presentation_policy:",
        ),
    )


def _choice(
    decision_kind: str,
    tool_id: str,
    arguments: dict[str, Any],
) -> HostSemanticChoice:
    operation = PublicOperationPayload(
        decision_kind=decision_kind,
        tool_id=tool_id,
        arguments=arguments,
    )
    return HostSemanticChoice(
        semantic_key=operation.semantic_key,
        operation=operation,
    )


def _operator_choices(
    task: PublicSemanticTask, operation_handle: str
) -> tuple[HostSemanticChoice, ...]:
    operation = next(item for item in task.operations if item.operation_handle == operation_handle)
    expected = resolve_public_operator(task, operation_handle)
    alternatives = tuple(item for item in OPERATOR_CATALOG if item != expected)[:2]
    return tuple(
        _choice(
            "select_operator",
            operation.tool_id,
            {"operation_handle": operation.operation_handle, "operator_id": item},
        )
        for item in (expected, *alternatives)
    )


def _context_specs(
    task: PublicSemanticTask,
) -> tuple[tuple[str, str, dict[str, Any], tuple[HostSemanticChoice, ...]], ...]:
    terminal = next(
        item for item in task.operations if item.operation_handle == task.terminal_operation_handle
    )
    left, right = resolve_required_record_handles(task)
    fields = list(task.answer_fields)
    return (
        (
            "context.operator",
            "select_operator",
            {"operation_handle": terminal.operation_handle},
            _operator_choices(task, terminal.operation_handle),
        ),
        (
            "context.records",
            "select_records",
            {"operation_handle": terminal.operation_handle},
            (
                _choice("select_records", terminal.tool_id, {"record_handles": [left, right]}),
                _choice("select_records", terminal.tool_id, {"record_handles": [left, left]}),
                _choice("select_records", terminal.tool_id, {"record_handles": [right, right]}),
            ),
        ),
        (
            "context.projection",
            "select_projection",
            {"terminal_operation_handle": terminal.operation_handle},
            (
                _choice("select_projection", "cross_check_evidence", {"answer_fields": fields}),
                _choice(
                    "select_projection", "cross_check_evidence", {"answer_fields": [fields[0]]}
                ),
                _choice(
                    "select_projection", "cross_check_evidence", {"answer_fields": [fields[-1]]}
                ),
            ),
        ),
        (
            "context.scope",
            "select_scope",
            {"aliases": list(task.aliases), "periods": list(task.periods)},
            (
                _choice("select_scope", "query_structured_fact", {"record_handles": [left, right]}),
                _choice("select_scope", "query_structured_fact", {"record_handles": [left, left]}),
                _choice(
                    "select_scope", "query_structured_fact", {"record_handles": [right, right]}
                ),
            ),
        ),
    )


def _reconciliation_specs(
    task: PublicSemanticTask,
) -> tuple[tuple[str, str, dict[str, Any], tuple[HostSemanticChoice, ...]], ...]:
    normalizations = tuple(item for item in task.operations if item.node_kind == "normalization")
    terminal = next(
        item for item in task.operations if item.operation_handle == task.terminal_operation_handle
    )
    output_by_symbol = {item.output_symbol: item.output_handle for item in task.operations}
    rows: list[tuple[str, str, dict[str, Any], tuple[HostSemanticChoice, ...]]] = []
    for index, operation in enumerate(normalizations):
        variable = operation.input_symbols[0]
        rule = next(
            item
            for item in task.resolution_rules
            if item.variable_symbol == variable and item.source_tool_id == "query_structured_fact"
        )
        correct = resolve_rule_record(task, rule)
        other = next(item for item in task.records if item.record_handle != correct.record_handle)
        other_output = next(
            item.output_handle
            for item in normalizations
            if item.output_handle != operation.output_handle
        )
        arguments = {
            "operation_handle": operation.operation_handle,
            "output_handle": operation.output_handle,
            "record_handle": correct.record_handle,
            "rule_handle": rule.rule_handle,
        }
        rows.append(
            (
                f"reconciliation.mapping.{index + 1}",
                "reconcile_record",
                {"operation_handle": operation.operation_handle, "rule_handle": rule.rule_handle},
                (
                    _choice("reconcile_record", operation.tool_id, arguments),
                    _choice(
                        "reconcile_record",
                        operation.tool_id,
                        {**arguments, "record_handle": other.record_handle},
                    ),
                    _choice(
                        "reconcile_record",
                        operation.tool_id,
                        {**arguments, "output_handle": other_output},
                    ),
                ),
            )
        )
    correct_outputs = [output_by_symbol[item] for item in terminal.input_symbols]
    rows.append(
        (
            "reconciliation.consume",
            "consume_outputs",
            {"operation_handle": terminal.operation_handle},
            (
                _choice(
                    "consume_outputs",
                    terminal.tool_id,
                    {
                        "operation_handle": terminal.operation_handle,
                        "output_handles": correct_outputs,
                    },
                ),
                _choice(
                    "consume_outputs",
                    terminal.tool_id,
                    {
                        "operation_handle": terminal.operation_handle,
                        "output_handles": [correct_outputs[0], correct_outputs[0]],
                    },
                ),
                _choice(
                    "consume_outputs",
                    terminal.tool_id,
                    {
                        "operation_handle": terminal.operation_handle,
                        "output_handles": [correct_outputs[-1], correct_outputs[-1]],
                    },
                ),
            ),
        )
    )
    rows.append(
        (
            "reconciliation.operator",
            "select_operator",
            {"operation_handle": terminal.operation_handle},
            _operator_choices(task, terminal.operation_handle),
        )
    )
    return tuple(rows)


def _recovery_specs(
    task: PublicSemanticTask,
) -> tuple[tuple[str, str, dict[str, Any], tuple[HostSemanticChoice, ...]], ...]:
    query_rules = tuple(
        item for item in task.resolution_rules if item.source_tool_id == "query_structured_fact"
    )
    if len(query_rules) != 2:
        raise ValueError("Recovery public Task does not expose two query Rules")
    rows = []
    for index in range(4):
        rule = query_rules[index % 2]
        other = query_rules[(index + 1) % 2]
        missing_index = (index + 1) % len(rule.equals)
        failed_selector = [
            item.model_dump(mode="json")
            for offset, item in enumerate(rule.equals)
            if offset != missing_index
        ]
        correct_selector = [item.model_dump(mode="json") for item in rule.equals]
        other_selector = [item.model_dump(mode="json") for item in other.equals]
        partial_selector = correct_selector[:-1]
        rows.append(
            (
                f"recovery.revision.{index + 1}",
                "revise_selector",
                {
                    "deterministic_failure_observed": True,
                    "failed_selector": failed_selector,
                    "missing_selector": list(rule.equals[missing_index].selector),
                    "rule_handle": rule.rule_handle,
                },
                (
                    _choice(
                        "revise_selector",
                        rule.source_tool_id,
                        {
                            "rule_handle": rule.rule_handle,
                            "selector": correct_selector,
                            "source_tool_id": rule.source_tool_id,
                        },
                    ),
                    _choice(
                        "revise_selector",
                        rule.source_tool_id,
                        {
                            "rule_handle": other.rule_handle,
                            "selector": other_selector,
                            "source_tool_id": other.source_tool_id,
                        },
                    ),
                    _choice(
                        "revise_selector",
                        rule.source_tool_id,
                        {
                            "rule_handle": rule.rule_handle,
                            "selector": partial_selector,
                            "source_tool_id": rule.source_tool_id,
                        },
                    ),
                ),
            )
        )
    return tuple(rows)


def _stopping_specs(
    task: PublicSemanticTask,
    depth_index: int,
) -> tuple[tuple[str, str, dict[str, Any], tuple[HostSemanticChoice, ...]], ...]:
    receipt = {
        "all_required_operations_complete": True,
        "no_unresolved_failure": True,
        "oracle_verification_passed": True,
    }
    assertions = tuple(receipt)[:depth_index]
    rows: list[tuple[str, str, dict[str, Any], tuple[HostSemanticChoice, ...]]] = []
    for assertion in assertions:
        rows.append(
            (
                f"stopping.readiness.{assertion}",
                "assess_readiness",
                {"assertion": assertion, "execution_receipt": receipt},
                tuple(
                    _choice(
                        "assess_readiness",
                        "cross_check_evidence",
                        {"assertion": assertion, "verdict": verdict},
                    )
                    for verdict in task.verdict_catalog
                ),
            )
        )
    rows.append(
        (
            "stopping.final_decision",
            "stop_or_continue",
            {"execution_receipt": receipt},
            tuple(
                _choice(
                    "stop_or_continue",
                    "cross_check_evidence",
                    {"command": command},
                )
                for command in task.control_commands
            ),
        )
    )
    return tuple(rows)


def _component_specs(
    family: CapabilityFamily,
    depth: ObservationDepth,
    task: PublicSemanticTask,
) -> tuple[tuple[str, str, dict[str, Any], tuple[HostSemanticChoice, ...]], ...]:
    depth_index = OBSERVATION_DEPTH_ORDER.index(depth)
    if family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION:
        return _context_specs(task)[: depth_index + 1]
    if family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        return _reconciliation_specs(task)[: depth_index + 1]
    if family == CapabilityFamily.FAILURE_RECOVERY:
        return _recovery_specs(task)[: depth_index + 1]
    return _stopping_specs(task, depth_index)


def _action_id(
    package_id: str,
    component_key: str,
    replica_index: int,
    semantic_key: str,
) -> str:
    value = f"{PRESENTATION_SALT}|{package_id}|{component_key}|{replica_index}|{semantic_key}"
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def _prompt(
    *,
    package_id: str,
    component_key: str,
    replica_index: int,
    task: PublicSemanticTask,
    state: PublicDecisionState,
    choices: tuple[HostSemanticChoice, ...],
) -> PublicSemanticPrompt:
    base = (
        int(
            hashlib.sha256(
                f"{PRESENTATION_SALT}|{package_id}|{component_key}".encode()
            ).hexdigest()[:8],
            16,
        )
        % 3
    )
    shift = (base + replica_index) % 3
    ordered = choices[shift:] + choices[:shift]
    raw = tuple(
        PresentedPublicCandidate(
            action_id=_action_id(
                package_id,
                component_key,
                replica_index,
                choice.semantic_key,
            ),
            presentation_index=index,
            operation=choice.operation,
        )
        for index, choice in enumerate(ordered)
    )
    target_length = max(len(canonical_bytes(item.model_dump(mode="json"))) for item in raw)
    candidates = tuple(
        PresentedPublicCandidate(
            action_id=item.action_id,
            presentation_index=item.presentation_index,
            operation=item.operation,
            padding="x" * (target_length - len(canonical_bytes(item.model_dump(mode="json")))),
        )
        for item in raw
    )
    prompt_payload = {
        "task": task.model_dump(mode="json"),
        "state": state.model_dump(mode="json"),
        "candidates": [item.model_dump(mode="json") for item in candidates],
    }
    rendered = canonical_bytes(prompt_payload)
    return PublicSemanticPrompt(
        prompt_hash=hashlib.sha256(rendered).hexdigest(),
        rendered_bytes=len(rendered),
        task=task,
        state=state,
        candidates=cast(Any, candidates),
    )


def _build_component(
    *,
    package_id: str,
    task: PublicSemanticTask,
    component_key: str,
    decision_kind: str,
    facts: dict[str, Any],
    choices: tuple[HostSemanticChoice, ...],
) -> TargetComponent:
    state_token = hashlib.sha256(
        f"{package_id}|{component_key}|public-semantic-state".encode()
    ).hexdigest()[:24]
    state = PublicDecisionState(
        state_token=state_token,
        decision_kind=decision_kind,
        facts=facts,
    )
    if len(choices) != 3:
        raise ValueError("v26.170 target Component does not have three semantic Choices")
    for choice in choices:
        findings = candidate_grounding_findings(task, state, choice.operation)
        if findings:
            raise ValueError(f"v26.170 Candidate is not publicly grounded:{findings}")
    probe = _prompt(
        package_id=package_id,
        component_key=component_key,
        replica_index=0,
        task=task,
        state=state,
        choices=choices,
    )
    selected_action_id = public_only_select_action(probe)
    reference = next(
        item.operation.semantic_key
        for item in probe.candidates
        if item.action_id == selected_action_id
    )
    values = {
        "component_key": component_key,
        "public_state": state,
        "choices": cast(Any, choices),
        "reference_semantic_key": reference,
    }
    return cast(
        TargetComponent,
        _make_core_model(
            TargetComponent,
            values,
            field="component_id",
            prefix="public_semantic_target_component:",
        ),
    )


def _presentations(
    *,
    package_id: str,
    task: PublicSemanticTask,
    component: TargetComponent,
) -> tuple[models.ReplicaPresentation, ...]:
    output = []
    for replica in range(6):
        prompt = _prompt(
            package_id=package_id,
            component_key=component.component_key,
            replica_index=replica,
            task=task,
            state=component.public_state,
            choices=component.choices,
        )
        values = {
            "package_id": package_id,
            "component_id": component.component_id,
            "replica_index": replica,
            "prompt": prompt,
        }
        output.append(
            cast(
                models.ReplicaPresentation,
                _make_model(
                    models.ReplicaPresentation,
                    values,
                    field="presentation_id",
                    prefix="public_semantic_replica_presentation:",
                ),
            )
        )
    return tuple(output)


def _evidence_by_handle(
    core: v168_models.LowNuisanceFinanceCore,
    task: PublicSemanticTask,
) -> dict[str, Any]:
    return {
        public_record_from_evidence(item).record_handle: item
        for item in core.operational_record.evidence_bundle.evidence
    }


def _build_package(
    *,
    predecessor: v169_models.CausalDepthPackage,
    predecessor_group_id: str,
    core: v168_models.LowNuisanceFinanceCore,
    source_verification: Any,
    projection_contract: models.PublicSemanticProjectionContract,
    presentation_policy: models.ReplicaPresentationPolicy,
) -> models.HardenedSemanticPackage:
    source_task = core.operational_record.task_package.task
    task = project_public_semantic_task(
        source_task.public.model_dump(mode="json"),
        core.operational_record.evidence_bundle.evidence,
    )
    specs = _component_specs(predecessor.capability_family, predecessor.depth, task)
    component_keys = tuple(item[0] for item in specs)
    package_id = canonical_hash(
        {
            "predecessor_package_id": predecessor.package_id,
            "capability_family": predecessor.capability_family.value,
            "depth": predecessor.depth.value,
            "finance_core_id": core.core_id,
            "fixed_generation_condition_id": predecessor.fixed_generation_condition_id,
            "projection_contract_id": projection_contract.contract_id,
            "presentation_policy_id": presentation_policy.policy_id,
            "public_task_hash": task.semantic_hash,
            "component_keys": list(component_keys),
            "schema_version": models.V26_PUBLIC_SEMANTIC_EXECUTION_VERSION,
        },
        prefix="finance_v26_public_semantic_package:",
    )
    components = tuple(
        _build_component(
            package_id=package_id,
            task=task,
            component_key=component_key,
            decision_kind=decision_kind,
            facts=facts,
            choices=choices,
        )
        for component_key, decision_kind, facts, choices in specs
    )
    presentations = tuple(
        presentation
        for component in components
        for presentation in _presentations(
            package_id=package_id,
            task=task,
            component=component,
        )
    )
    prompts = tuple(
        next(
            item.prompt
            for item in presentations
            if item.component_id == component.component_id and item.replica_index == 0
        )
        for component in components
    )
    prompt_values = {
        "package_id": package_id,
        "public_task_hash": task.semantic_hash,
        "projection_contract_id": projection_contract.contract_id,
        "prompts": prompts,
        "prompt_count": len(prompts),
    }
    prompt_binding = cast(
        models.HardenedPromptBinding,
        _make_model(
            models.HardenedPromptBinding,
            prompt_values,
            field="binding_id",
            prefix="public_semantic_prompt_binding:",
        ),
    )
    parent_values = {
        "finance_core_id": core.core_id,
        "source_public_task_hash": canonical_hash(
            source_task.public.model_dump(mode="json"),
            prefix="source_public_finance_task:",
        ),
        "source_public_evidence_semantic_hash": canonical_hash(
            tuple(item.semantic_fields for item in task.records),
            prefix="source_public_finance_evidence_semantics:",
        ),
        "projected_public_task_hash": task.semantic_hash,
        "projection_contract_id": projection_contract.contract_id,
    }
    parent_binding = cast(
        models.PublicTaskParentBinding,
        _make_model(
            models.PublicTaskParentBinding,
            parent_values,
            field="binding_id",
            prefix="public_semantic_task_parent_binding:",
        ),
    )
    load_values = {
        "package_id": package_id,
        "capability_family": predecessor.capability_family,
        "depth": predecessor.depth,
        "target_component_count": len(components),
        "total": len(components),
    }
    target_load = cast(
        models.IsolatedTargetLoad,
        _make_model(
            models.IsolatedTargetLoad,
            load_values,
            field="load_id",
            prefix="isolated_capability_target_load:",
        ),
    )
    baseline = execute_semantic_runtime(
        default_semantic_runtime_binding(
            task=task,
            components=components,
            original_program=source_task.oracle.task_program,
            evidence_by_handle=_evidence_by_handle(core, task),
        )
    )
    if (
        not baseline.qualified_valid
        or baseline.program_execution is None
        or baseline.program_execution.final_output
        != source_verification.independently_computed_output
    ):
        raise ValueError("v26.170 public-only baseline does not reproduce exact Program output")
    values = {
        "package_id": package_id,
        "predecessor_package_id": predecessor.package_id,
        "predecessor_group_id": predecessor_group_id,
        "capability_family": predecessor.capability_family,
        "depth": predecessor.depth,
        "finance_core_id": core.core_id,
        "fixed_generation_condition_id": predecessor.fixed_generation_condition_id,
        "projection_contract_id": projection_contract.contract_id,
        "presentation_policy_id": presentation_policy.policy_id,
        "public_task": task,
        "task_parent_binding": parent_binding,
        "components": components,
        "prompt_binding": prompt_binding,
        "replica_presentations": presentations,
        "target_load": target_load,
        "baseline_execution": baseline,
        "source_program_verification_hash": canonical_hash(
            source_verification.model_dump(mode="json"),
            prefix="source_program_verification:",
        ),
    }
    return cast(
        models.HardenedSemanticPackage,
        _make_model(
            models.HardenedSemanticPackage,
            values,
            field="artifact_id",
            prefix="finance_v26_public_semantic_package_artifact:",
        ),
    )


def _development_catalog(
    predecessor: _PredecessorProducts,
    projection_contract: models.PublicSemanticProjectionContract,
    presentation_policy: models.ReplicaPresentationPolicy,
) -> models.HardenedSemanticDevelopmentCatalog:
    cores = {item.core_id: item for item in predecessor.v168_catalog.finance_cores}
    v168_groups = {item.group_id: item for item in predecessor.v168_catalog.groups}
    groups: list[models.HardenedSemanticGroup] = []
    for predecessor_group in predecessor.catalog.groups:
        core = cores[predecessor_group.finance_core_id]
        source_group = v168_groups[predecessor_group.predecessor_group_id]
        source_by_package = {item.package_id: item for item in source_group.packages}
        packages = tuple(
            _build_package(
                predecessor=item,
                predecessor_group_id=predecessor_group.group_id,
                core=core,
                source_verification=source_by_package[
                    item.predecessor_package_id
                ].variant_program_verification,
                projection_contract=projection_contract,
                presentation_policy=presentation_policy,
            )
            for item in predecessor_group.packages
        )
        group_values = {
            "predecessor_group_id": predecessor_group.group_id,
            "capability_family": predecessor_group.capability_family,
            "finance_core_id": core.core_id,
            "packages": packages,
        }
        groups.append(
            cast(
                models.HardenedSemanticGroup,
                _make_model(
                    models.HardenedSemanticGroup,
                    group_values,
                    field="group_id",
                    prefix="finance_v26_public_semantic_group:",
                ),
            )
        )
    values = {
        "predecessor_catalog_id": predecessor.catalog.catalog_id,
        "predecessor_report_id": predecessor.report.report_id,
        "v168_finance_core_catalog_id": predecessor.v168_catalog.catalog_id,
        "sealed_confirmation_receipt_id": predecessor.catalog.sealed_confirmation_receipt_id,
        "projection_contract_id": projection_contract.contract_id,
        "presentation_policy_id": presentation_policy.policy_id,
        "fixed_generation_condition_id": predecessor.catalog.fixed_generation_condition_id,
        "finance_cores": tuple(sorted(cores.values(), key=lambda item: item.core_id)),
        "groups": tuple(sorted(groups, key=lambda item: item.predecessor_group_id)),
    }
    return cast(
        models.HardenedSemanticDevelopmentCatalog,
        _make_model(
            models.HardenedSemanticDevelopmentCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_public_semantic_development_catalog:",
        ),
    )


def _transition(
    *,
    predecessor_transition_id: str,
    catalog: models.HardenedSemanticDevelopmentCatalog,
    projection_contract: models.PublicSemanticProjectionContract,
    presentation_policy: models.ReplicaPresentationPolicy,
    static: models.PublicSemanticStaticAudit,
) -> models.PublicSemanticTransition:
    values = {
        "predecessor_transition_id": predecessor_transition_id,
        "development_catalog_id": catalog.catalog_id,
        "projection_contract_id": projection_contract.contract_id,
        "presentation_policy_id": presentation_policy.policy_id,
        "static_audit_id": static.audit_id,
        "blocked_predecessor_stage": (
            "capability_observation_executable_depth_development_runner_preflight_only"
        ),
        "next_stage": (
            "capability_observation_public_semantic_execution_development_runner_preflight_only"
        ),
    }
    return cast(
        models.PublicSemanticTransition,
        _make_model(
            models.PublicSemanticTransition,
            values,
            field="transition_id",
            prefix="finance_v26_public_semantic_transition:",
        ),
    )


def _detail_files(output_dir: Path) -> tuple[models.FileBinding, ...]:
    return tuple(
        _file_binding(
            path=path,
            relative_path=path.name,
            source_kind=(
                "external_audit_input"
                if path.name == "external_joint_audit_input.txt"
                else "formal_output"
            ),
        )
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "report.json"
    )


def build(
    *,
    package_root: Path,
    output_dir: Path,
    external_audit_path: Path,
) -> models.BuildProducts:
    authorization = _authorization(external_audit_path)
    source_root = _transitive_source_root(package_root)
    predecessor = _predecessor_integrity(package_root)
    defect = _defect_audit(predecessor)
    projection_contract = _projection_contract()
    presentation_policy = _presentation_policy()
    development = _development_catalog(
        predecessor,
        projection_contract,
        presentation_policy,
    )
    sufficiency = static_audit.build_sufficiency_audit(development)
    grounding = static_audit.build_grounding_audit(development)
    execution = static_audit.build_execution_audit(development, predecessor.v168_catalog)
    isolation = static_audit.build_isolation_audit(development)
    increments = static_audit.build_increment_necessity_catalog(development)
    parent_binding = static_audit.build_parent_binding_audit(development)
    replica = static_audit.build_replica_presentation_audit(development)
    static = static_audit.build_static_audit(
        source_root=source_root,
        sufficiency=sufficiency,
        grounding=grounding,
        execution=execution,
        isolation=isolation,
        increments=increments,
        parent_binding=parent_binding,
        replica=replica,
    )
    transition = _transition(
        predecessor_transition_id=predecessor.transition.transition_id,
        catalog=development,
        projection_contract=projection_contract,
        presentation_policy=presentation_policy,
        static=static,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(output_dir / "external_joint_audit_input.txt", external_audit_path.read_bytes())
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("predecessor_integrity_audit.json", predecessor.audit),
        ("v169_semantic_defect_audit.json", defect),
        ("public_semantic_projection_contract.json", projection_contract),
        ("replica_presentation_policy.json", presentation_policy),
        ("hardened_semantic_development_catalog.json", development),
        ("public_semantic_sufficiency_audit.json", sufficiency),
        ("candidate_grounding_audit.json", grounding),
        ("real_program_execution_audit.json", execution),
        ("target_isolation_audit.json", isolation),
        ("depth_increment_necessity_catalog.json", increments),
        ("prompt_parent_binding_audit.json", parent_binding),
        ("replica_presentation_audit.json", replica),
        ("public_semantic_static_audit.json", static),
        ("prospective_transition_contract.json", transition),
    )
    for filename, value in outputs:
        _write(output_dir / filename, value)
    details = _detail_files(output_dir)
    report_values = {
        "run_id": RUN_ID,
        "authorization_id": authorization.authorization_id,
        "transitive_source_root_id": source_root.root_id,
        "predecessor_integrity_audit_id": predecessor.audit.audit_id,
        "defect_audit_id": defect.audit_id,
        "projection_contract_id": projection_contract.contract_id,
        "presentation_policy_id": presentation_policy.policy_id,
        "development_catalog_id": development.catalog_id,
        "sufficiency_audit_id": sufficiency.audit_id,
        "grounding_audit_id": grounding.audit_id,
        "execution_audit_id": execution.audit_id,
        "isolation_audit_id": isolation.audit_id,
        "increment_catalog_id": increments.catalog_id,
        "parent_binding_audit_id": parent_binding.audit_id,
        "replica_audit_id": replica.audit_id,
        "static_audit_id": static.audit_id,
        "transition_id": transition.transition_id,
        "detail_files": details,
        "next_stage": transition.next_stage,
    }
    report = cast(
        models.PublicSemanticHardeningReport,
        _make_model(
            models.PublicSemanticHardeningReport,
            report_values,
            field="report_id",
            prefix="finance_v26_public_semantic_hardening_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor.audit,
        defect=defect,
        projection_contract=projection_contract,
        presentation_policy=presentation_policy,
        development_catalog=development,
        sufficiency=sufficiency,
        grounding=grounding,
        execution=execution,
        isolation=isolation,
        increments=increments,
        parent_binding=parent_binding,
        replica=replica,
        static=static,
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
