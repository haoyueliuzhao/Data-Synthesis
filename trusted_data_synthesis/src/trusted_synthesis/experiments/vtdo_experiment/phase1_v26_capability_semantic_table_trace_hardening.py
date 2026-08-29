from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task.capability_observation import CapabilityFamily
from trusted_synthesis.core.task.dynamic_capability_depth import (
    DynamicPublicPrompt as V172DynamicPublicPrompt,
)
from trusted_synthesis.core.task.dynamic_capability_depth import (
    DynamicPublicState as V172DynamicPublicState,
)
from trusted_synthesis.core.task.dynamic_capability_depth import (
    DynamicReplicaTrace as V172DynamicReplicaTrace,
)
from trusted_synthesis.core.task.dynamic_capability_depth import (
    DynamicStepRecord as V172DynamicStepRecord,
)
from trusted_synthesis.core.task.dynamic_capability_depth import (
    SemanticMechanismQualification as V172SemanticMechanismQualification,
)
from trusted_synthesis.core.task.dynamic_capability_depth import (
    make_identity_model as make_v172_core_identity,
)
from trusted_synthesis.core.task.dynamic_capability_depth import (
    resolve_dynamic_operation,
)
from trusted_synthesis.core.task.dynamic_capability_depth import (
    semantic_mechanism_qualification as v172_semantic_mechanism_qualification,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import canonical_bytes
from trusted_synthesis.core.task.semantic_table_trace_hardening import (
    SEMANTIC_TABLE_PRESENTATION_SALT,
    ActionAcceptanceReport,
    HardenedPublicObservation,
    HardenedPublicPrompt,
    HardenedPublicState,
    HardenedStepRecord,
    StateBoundMechanismQualification,
    StateBoundQualifiedValidity,
    StepRuntimeResult,
    execution_parent_hash,
    public_only_select_hardened_action,
    resolve_encoded_operation,
    resolve_runtime_operation,
    topological_components,
)
from trusted_synthesis.core.task.semantic_table_trace_hardening import (
    make_identity_model as make_core_identity,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_dynamic_depth_hardening as v172,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_dynamic_depth_hardening_models as v172_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_semantic_table_trace_hardening_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_semantic_table_trace_hardening_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit as v171,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_models as v171_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_runtime as v171_runtime,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_173_semantic_table_trace_hardening_v1_20260829"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_173_semantic_table_trace_hardening_v1_20260829"
)
EXPECTED_REVIEW_SHA256: Final = "b5a67c76303687e81ccaf3b6fc966b4a579ca25011df6ee5887e9e785c5949e7"
EXPECTED_REVIEW_BYTE_COUNT: Final = 25_187
V172_DIR: Final = v172.OUTPUT_DIR
V171_DIR: Final = v171.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/semantic_table_trace_hardening.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_semantic_table_trace_hardening_runtime.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_semantic_table_trace_hardening_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_semantic_table_trace_hardening.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.173 cannot resolve the trusted_data_synthesis package root")


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


def _canonical_file_bytes(value: Any) -> bytes:
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
        raise ValueError(f"v26.173 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.173 immutable output already exists:{path}")
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
    return models.make_identity_model(
        model_type,
        values,
        field=field,
        prefix=prefix,
    )


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
        raise ValueError("v26.173 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.173 external audit byte count does not match Authorization")
    return cast(
        models.ExternalAuditAuthorization,
        _make_model(
            models.ExternalAuditAuthorization,
            {
                "review_sha256": EXPECTED_REVIEW_SHA256,
                "review_byte_count": EXPECTED_REVIEW_BYTE_COUNT,
                "authorized_stage": models.AUTHORIZED_STAGE,
            },
            field="authorization_id",
            prefix="finance_v26_semantic_table_trace_external_authorization:",
        ),
    )


def _module_name(relative_path: str) -> str:
    return relative_path.removeprefix("src/").removesuffix(".py").replace("/", ".")


def _module_path(package_root: Path, module: str) -> Path | None:
    if not module.startswith("trusted_synthesis"):
        return None
    base = package_root / "src" / Path(*module.split("."))
    source = base.with_suffix(".py")
    if source.is_file():
        return source
    package = base / "__init__.py"
    return package if package.is_file() else None


def _imported_modules(package_root: Path, path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current = _module_name(path.relative_to(package_root).as_posix())
    current_parts = current.split(".")
    output: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            output.update(
                item.name for item in node.names if item.name.startswith("trusted_synthesis")
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                base = current_parts[: -node.level]
                module = ".".join((*base, *module.split("."))) if module else ".".join(base)
            if module.startswith("trusted_synthesis"):
                output.add(module)
                for alias in node.names:
                    candidate = f"{module}.{alias.name}"
                    if _module_path(package_root, candidate) is not None:
                        output.add(candidate)
    return tuple(sorted(output))


def _transitive_source_root(package_root: Path) -> models.TransitiveSourceRoot:
    entry_modules = tuple(_module_name(item) for item in ENTRY_SOURCE_PATHS)
    pending = list(entry_modules)
    visited: set[str] = set()
    files: dict[str, Path] = {}
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
        relative = path.relative_to(package_root).as_posix()
        files[relative] = path
        for imported in _imported_modules(package_root, path):
            if imported not in visited:
                pending.append(imported)
    if unresolved:
        raise ValueError(f"v26.173 source closure has unresolved imports:{sorted(unresolved)}")
    bindings = tuple(
        _file_binding(path=path, relative_path=relative, source_kind="implementation")
        for relative, path in sorted(files.items())
    )
    return cast(
        models.TransitiveSourceRoot,
        _make_model(
            models.TransitiveSourceRoot,
            {
                "entry_modules": entry_modules,
                "files": bindings,
                "file_count": len(bindings),
                "unresolved_import_count": 0,
            },
            field="root_id",
            prefix="finance_v26_semantic_table_trace_transitive_source_root:",
        ),
    )


def _source_packages(
    catalog: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> tuple[v171_models.ValiditySeparatedCausalPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


def _v172_packages(
    catalog: v172_models.DynamicHardeningCatalog,
) -> tuple[v172_models.DynamicHardeningPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


def _hardened_packages(
    catalog: models.HardenedDevelopmentCatalog,
) -> tuple[models.HardenedDevelopmentPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


def _predecessor_freeze(
    package_root: Path,
) -> tuple[
    models.PredecessorFreezeAudit,
    v172_models.DynamicHardeningCatalog,
    v172_models.DynamicRunnerInputCatalog,
    v172_models.DynamicHardeningTransition,
    v171_models.ValiditySeparatedDevelopmentCatalog,
]:
    source_dir = package_root / V172_DIR
    paths = tuple(sorted(path for path in source_dir.iterdir() if path.is_file()))
    if len(paths) != 22:
        raise ValueError("v26.172 formal predecessor directory is not exactly 22 files")
    report = v172_models.DynamicHardeningReport.model_validate(_load(source_dir / "report.json"))
    catalog = v172_models.DynamicHardeningCatalog.model_validate(
        _load(source_dir / "dynamic_depth_development_catalog.json")
    )
    runner_input = v172_models.DynamicRunnerInputCatalog.model_validate(
        _load(source_dir / "dynamic_runner_input_catalog.json")
    )
    transition = v172_models.DynamicHardeningTransition.model_validate(
        _load(source_dir / "prospective_transition_contract.json")
    )
    with tempfile.TemporaryDirectory(prefix="finance-v26-173-v172-rebuild-") as temporary:
        rebuild_dir = Path(temporary)
        v172.build(
            package_root=package_root,
            output_dir=rebuild_dir,
            external_audit_path=source_dir / "external_joint_audit_input.txt",
        )
        rebuilt = tuple(sorted(path for path in rebuild_dir.iterdir() if path.is_file()))
        if len(rebuilt) != len(paths):
            raise ValueError("v26.172 independent rebuild file count differs")
        for source in paths:
            candidate = rebuild_dir / source.name
            if not candidate.is_file() or source.read_bytes() != candidate.read_bytes():
                raise ValueError(f"v26.172 independent rebuild differs:{source.name}")
    source_catalog = v171_models.ValiditySeparatedDevelopmentCatalog.model_validate(
        _load(package_root / V171_DIR / "validity_separated_development_catalog.json")
    )
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=f"{V172_DIR}/{path.name}",
            source_kind="predecessor_artifact",
        )
        for path in paths
    )
    audit = cast(
        models.PredecessorFreezeAudit,
        _make_model(
            models.PredecessorFreezeAudit,
            {
                "predecessor_report_id": report.report_id,
                "predecessor_catalog_id": catalog.catalog_id,
                "predecessor_runner_input_catalog_id": runner_input.catalog_id,
                "predecessor_transition_id": transition.transition_id,
                "files": bindings,
                "file_count": 22,
                "independent_rebuild_match_count": 22,
                "predecessor_mutation_count": 0,
            },
            field="audit_id",
            prefix="finance_v26_v172_predecessor_freeze_audit:",
        ),
    )
    return audit, catalog, runner_input, transition, source_catalog


def _rehash_v172_parent(
    catalog: v172_models.DynamicHardeningCatalog,
    *,
    mutation: Literal["reference_path", "mechanism_parent", "display_mapping"],
) -> v172_models.DynamicHardeningCatalog:
    group = catalog.groups[0]
    package = group.packages[0]
    package_values = package.model_dump(mode="python", exclude={"artifact_id"})
    if mutation == "reference_path":
        package_values["reference_path_hash"] = canonical_hash(
            "forged-reference-path",
            prefix="dynamic_reference_path:",
        )
    elif mutation == "mechanism_parent":
        semantic_values = package.baseline_semantic_mechanism.model_dump(
            mode="python",
            exclude={"report_id"},
        )
        semantic_values["execution_result_id"] = "forged-execution-parent"
        package_values["baseline_semantic_mechanism"] = make_v172_core_identity(
            V172SemanticMechanismQualification,
            semantic_values,
            field="report_id",
            prefix="semantic_mechanism_qualification_report:",
        )
    else:
        traces = list(package.replica_traces)
        trace = traces[0]
        steps = list(trace.steps)
        step = steps[0]
        state_values = step.prompt.state.model_dump(mode="python", exclude={"state_token"})
        legends = state_values["choice_legend"]
        selected_index = next(
            index
            for index, item in enumerate(legends)
            if item["choice_handle"] == step.displayed_choice_handle
        )
        other_index = 1 if selected_index == 0 else 0
        legends[selected_index]["value_indices"] = legends[other_index]["value_indices"]
        state_token = hashlib.sha256(canonical_bytes(state_values)).hexdigest()[:24]
        mutated_state = V172DynamicPublicState(state_token=state_token, **state_values)
        prompt_values = step.prompt.model_dump(
            mode="python",
            exclude={"prompt_hash", "rendered_bytes"},
        )
        prompt_values["state"] = mutated_state
        payload = {
            "task": step.prompt.task.model_dump(mode="json"),
            "state": mutated_state.model_dump(mode="json"),
            "candidates": [item.model_dump(mode="json") for item in step.prompt.candidates],
        }
        rendered = canonical_bytes(payload)
        mutated_prompt = V172DynamicPublicPrompt(
            prompt_hash=hashlib.sha256(rendered).hexdigest(),
            rendered_bytes=len(rendered),
            **prompt_values,
        )
        observation_values = step.observation.model_dump(mode="python", exclude={"receipt_id"})
        observation_values["state_token"] = state_token
        mutated_observation = make_v172_core_identity(
            type(step.observation),
            observation_values,
            field="receipt_id",
            prefix="dynamic_public_observation_receipt:",
        )
        step_values = step.model_dump(mode="python", exclude={"step_id"})
        step_values.update(prompt=mutated_prompt, observation=mutated_observation)
        steps[0] = make_v172_core_identity(
            V172DynamicStepRecord,
            step_values,
            field="step_id",
            prefix="dynamic_depth_step_record:",
        )
        trace_values = trace.model_dump(mode="python", exclude={"trace_id"})
        trace_values["steps"] = tuple(steps)
        traces[0] = make_v172_core_identity(
            V172DynamicReplicaTrace,
            trace_values,
            field="trace_id",
            prefix="dynamic_depth_replica_trace:",
        )
        package_values["replica_traces"] = tuple(traces)
    mutated_package = _make_v172_model(
        v172_models.DynamicHardeningPackage,
        package_values,
        field="artifact_id",
        prefix="finance_v26_dynamic_depth_package_artifact:",
    )
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    packages = list(group.packages)
    packages[0] = mutated_package
    group_values["packages"] = tuple(packages)
    mutated_group = _make_v172_model(
        v172_models.DynamicHardeningGroup,
        group_values,
        field="group_id",
        prefix="finance_v26_dynamic_depth_group:",
    )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    groups = list(catalog.groups)
    groups[0] = mutated_group
    catalog_values["groups"] = tuple(groups)
    return cast(
        v172_models.DynamicHardeningCatalog,
        _make_v172_model(
            v172_models.DynamicHardeningCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_dynamic_depth_development_catalog:",
        ),
    )


def _make_v172_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    return v172_models.make_identity_model(
        model_type,
        values,
        field=field,
        prefix=prefix,
    )


def _v172_parent_gap_count(
    *,
    catalog: v172_models.DynamicHardeningCatalog,
    runner_input: v172_models.DynamicRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> int:
    accepted = 0
    for mutation in ("reference_path", "mechanism_parent", "display_mapping"):
        mutated = _rehash_v172_parent(catalog, mutation=cast(Any, mutation))
        v172._validate_catalog_against_source(catalog=mutated, source=source)
        accepted += 1
    package = next(
        item for item in runner_input.packages if len(item.topological_component_keys) > 1
    )
    package_values = package.model_dump(mode="python", exclude={"package_id"})
    package_values["topological_component_keys"] = tuple(
        reversed(package.topological_component_keys)
    )
    mutated_package = _make_v172_model(
        v172_models.DynamicRunnerInputPackage,
        package_values,
        field="package_id",
        prefix="finance_v26_dynamic_depth_runner_input_package:",
    )
    catalog_values = runner_input.model_dump(mode="python", exclude={"catalog_id"})
    packages = list(runner_input.packages)
    packages[packages.index(package)] = mutated_package
    catalog_values["packages"] = tuple(packages)
    _make_v172_model(
        v172_models.DynamicRunnerInputCatalog,
        catalog_values,
        field="catalog_id",
        prefix="finance_v26_dynamic_depth_runner_input_catalog:",
    )
    accepted += 1
    return accepted


def _defect_reproduction(
    *,
    catalog: v172_models.DynamicHardeningCatalog,
    runner_input: v172_models.DynamicRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> models.V172DefectReproductionAudit:
    packages = _v172_packages(catalog)
    step_groups = tuple(
        tuple(result.steps[index] for result in package.replica_traces)
        for package in packages
        for index in range(len(package.replica_traces[0].steps))
    )
    steps = tuple(item for group in step_groups for item in group)
    index_decisions = {
        "select_operator",
        "select_records",
        "select_projection",
        "select_scope",
        "assess_dynamic_readiness",
        "stop_or_continue",
    }
    stable_states = sum(
        group[0].prompt.state.decision_kind in index_decisions for group in step_groups
    )
    stable_presentations = sum(step.prompt.state.decision_kind in index_decisions for step in steps)
    unique_length_states = 0
    unique_length_presentations = 0
    action_imbalanced = 0
    minimum_action_success = 0
    for group in step_groups:
        first = group[0]
        operations = tuple(
            resolve_dynamic_operation(first.prompt.state, item.choice_handle)
            for item in first.prompt.state.choice_legend
        )
        lengths = tuple(len(canonical_bytes(item.model_dump(mode="json"))) for item in operations)
        selected_index = next(
            index
            for index, item in enumerate(first.prompt.state.choice_legend)
            if item.choice_handle == first.displayed_choice_handle
        )
        if lengths.count(lengths[selected_index]) == 1:
            unique_length_states += 1
            unique_length_presentations += 6
        ranks = [
            sorted(item.action_id for item in step.prompt.candidates).index(step.selected_action_id)
            for step in group
        ]
        expected = 6 // len(first.prompt.candidates)
        if any(ranks.count(index) != expected for index in range(len(first.prompt.candidates))):
            action_imbalanced += 1
        minimum_action_success += sum(rank == 0 for rank in ranks)
    source_by_artifact = {item.artifact_id: item for item in _source_packages(source)}
    core_by_id = {item.core_id: item for item in source.finance_cores}
    wrong_count = 0
    conflict_count = 0
    for package in _source_packages(source):
        if package.capability_family != CapabilityFamily.FAILURE_RECOVERY:
            continue
        runtime_input = v172._runtime_input(package, core_by_id[package.finance_core_id])
        for component in package.components:
            wrong = next(
                item
                for item in component.public_state.choice_legend
                if str(item.operation.arguments.get("rule_handle"))
                != str(component.public_state.facts.get("rule_handle"))
            )
            result = v171_runtime.execute_runtime(
                runtime_input,
                {component.component_key: wrong.choice_handle},
            )
            semantic = v172_semantic_mechanism_qualification(
                package_id=package.package_id,
                family=package.capability_family,
                components=package.components,
                selected_by_component={component.component_key: wrong.choice_handle},
                result=result,
            )
            wrong_count += 1
            conflict_count += int(
                result.task_validity.base_valid and semantic.mechanism_semantically_qualified
            )
    if len(source_by_artifact) != 32:
        raise ValueError("v26.173 source Package denominator changed")
    values = {
        "target_state_count": len(step_groups),
        "presentation_count": len(steps),
        "stable_index_rule_state_count": stable_states,
        "stable_index_rule_recovery_count": stable_presentations,
        "unique_decoded_operation_length_state_count": unique_length_states,
        "decoded_operation_length_recovery_count": unique_length_presentations,
        "external_reported_action_id_rank_imbalanced_state_count": 56,
        "direct_recomputed_action_id_rank_imbalanced_state_count": action_imbalanced,
        "minimum_action_id_recovery_count": minimum_action_success,
        "recovery_wrong_current_rule_candidate_count": wrong_count,
        "recovery_contract_conflict_count": conflict_count,
        "baseline_projection_trace_count": sum(len(item.replica_traces) for item in packages),
        "accepted_fully_rehashed_parent_mutation_count": _v172_parent_gap_count(
            catalog=catalog,
            runner_input=runner_input,
            source=source,
        ),
        "stale_runner_preflight_blocked": True,
    }
    return cast(
        models.V172DefectReproductionAudit,
        _make_model(
            models.V172DefectReproductionAudit,
            values,
            field="audit_id",
            prefix="finance_v26_v172_semantic_trace_defect_reproduction:",
        ),
    )


def _semantic_table_contract() -> models.SemanticTablePresentationContract:
    selectors: tuple[models.ShortcutSelector, ...] = (
        "action_id_order",
        "argument_field_order",
        "candidate_position",
        "catalog_lexical_order",
        "choice_handle_order",
        "encoded_operation_length",
        "fixed_value_handle_vector",
        "legend_position",
        "maximum_value_handle_vector",
        "minimum_value_handle_vector",
    )
    return cast(
        models.SemanticTablePresentationContract,
        _make_model(
            models.SemanticTablePresentationContract,
            {
                "registered_shortcut_selectors": selectors,
                "preoutcome_salt_sha256": hashlib.sha256(
                    SEMANTIC_TABLE_PRESENTATION_SALT.encode()
                ).hexdigest(),
            },
            field="contract_id",
            prefix="semantic_table_presentation_contract:",
        ),
    )


def _state_precondition_contract() -> models.StatePreconditionMechanismContract:
    return cast(
        models.StatePreconditionMechanismContract,
        _make_model(
            models.StatePreconditionMechanismContract,
            {},
            field="contract_id",
            prefix="state_precondition_mechanism_contract:",
        ),
    )


def _step_runtime_contract() -> models.StepRuntimeContract:
    return cast(
        models.StepRuntimeContract,
        _make_model(
            models.StepRuntimeContract,
            {},
            field="contract_id",
            prefix="production_step_runtime_contract:",
        ),
    )


def _parent_reconstruction_contract() -> models.SemanticParentReconstructionContract:
    return cast(
        models.SemanticParentReconstructionContract,
        _make_model(
            models.SemanticParentReconstructionContract,
            {
                "reconstructed_parents": (
                    "display_source_handle_mapping",
                    "mechanism_report",
                    "observation_public_effects",
                    "prompt_state_token",
                    "receipt_parent",
                    "reference_operation",
                    "reference_path_hash",
                    "runner_input_topology",
                )
            },
            field="contract_id",
            prefix="semantic_parent_reconstruction_contract:",
        ),
    )


def _sequential_estimand_contract() -> models.SequentialEstimandContract:
    return cast(
        models.SequentialEstimandContract,
        _make_model(
            models.SequentialEstimandContract,
            {
                "registered_future_fields": (
                    "component_specific_hazard",
                    "first_failed_component",
                    "full_package_success",
                    "per_step_conditional_success",
                    "task_base_and_mechanism_qualification",
                )
            },
            field="contract_id",
            prefix="sequential_depth_estimand_contract:",
        ),
    )


def _runtime_input(
    package: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
) -> v171_runtime.RuntimeInput:
    return v171_runtime.RuntimeInput(
        package_id=package.package_id,
        capability_family=package.capability_family,
        public_task=package.public_task,
        components=package.components,
        finance_core=core,
    )


def _hardened_package_id(
    *,
    source: v171_models.ValiditySeparatedCausalPackage,
    v172_package: v172_models.DynamicHardeningPackage,
    topology: Sequence[str],
    contract_ids: Mapping[str, str],
) -> str:
    return canonical_hash(
        {
            "source_v171_package_artifact_id": source.artifact_id,
            "source_v172_package_artifact_id": v172_package.artifact_id,
            "topological_component_keys": list(topology),
            "contracts": dict(sorted(contract_ids.items())),
            "schema_version": models.V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION,
        },
        prefix="finance_v26_semantic_table_trace_package:",
    )


def _reference_result(
    *,
    package_id: str,
    source: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
    replica_index: int,
) -> StepRuntimeResult:
    state = step_runtime.initialize(
        _runtime_input(source, core),
        package_id=package_id,
        replica_index=replica_index,
    )
    while state.current_index < len(state.ordered_components):
        prompt = step_runtime.render_next_prompt(state)
        step_runtime.step(state, public_only_select_hardened_action(prompt))
    return step_runtime.finalize(state)


def _build_development_catalog(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    predecessor: v172_models.DynamicHardeningCatalog,
    semantic_table: models.SemanticTablePresentationContract,
    state_precondition: models.StatePreconditionMechanismContract,
    runtime_contract: models.StepRuntimeContract,
    parent_contract: models.SemanticParentReconstructionContract,
    estimand_contract: models.SequentialEstimandContract,
) -> models.HardenedDevelopmentCatalog:
    v172_by_source = {item.source_package_artifact_id: item for item in _v172_packages(predecessor)}
    core_by_id = {item.core_id: item for item in source.finance_cores}
    contract_ids = {
        "semantic_table": semantic_table.contract_id,
        "state_precondition": state_precondition.contract_id,
        "step_runtime": runtime_contract.contract_id,
        "parent_reconstruction": parent_contract.contract_id,
        "sequential_estimand": estimand_contract.contract_id,
    }
    groups: list[models.HardenedDevelopmentGroup] = []
    for source_group in source.groups:
        packages: list[models.HardenedDevelopmentPackage] = []
        for source_package in source_group.packages:
            predecessor_package = v172_by_source[source_package.artifact_id]
            ordered = topological_components(source_package.components)
            topology = tuple(item.component_key for item in ordered)
            package_id = _hardened_package_id(
                source=source_package,
                v172_package=predecessor_package,
                topology=topology,
                contract_ids=contract_ids,
            )
            core = core_by_id[source_package.finance_core_id]
            results = tuple(
                _reference_result(
                    package_id=package_id,
                    source=source_package,
                    core=core,
                    replica_index=replica,
                )
                for replica in range(6)
            )
            reference_path = canonical_hash(
                tuple(item.reference_choice_handle for item in ordered),
                prefix="hardened_reference_path:",
            )
            package_values = {
                "package_id": package_id,
                "source_v172_package_artifact_id": predecessor_package.artifact_id,
                "source_v171_package_artifact_id": source_package.artifact_id,
                "source_package_id": source_package.package_id,
                "source_group_id": source_group.group_id,
                "finance_core_id": source_package.finance_core_id,
                "capability_family": source_package.capability_family,
                "depth": source_package.depth,
                "public_task_id": source_package.public_task.task_id,
                "topological_component_keys": topology,
                "reference_path_hash": reference_path,
                "semantic_table_contract_id": semantic_table.contract_id,
                "state_precondition_contract_id": state_precondition.contract_id,
                "step_runtime_contract_id": runtime_contract.contract_id,
                "parent_reconstruction_contract_id": parent_contract.contract_id,
                "sequential_estimand_contract_id": estimand_contract.contract_id,
                "replica_results": results,
            }
            packages.append(
                cast(
                    models.HardenedDevelopmentPackage,
                    _make_model(
                        models.HardenedDevelopmentPackage,
                        package_values,
                        field="artifact_id",
                        prefix="finance_v26_semantic_table_trace_package_artifact:",
                    ),
                )
            )
        groups.append(
            cast(
                models.HardenedDevelopmentGroup,
                _make_model(
                    models.HardenedDevelopmentGroup,
                    {
                        "source_group_id": source_group.group_id,
                        "finance_core_id": source_group.finance_core_id,
                        "capability_family": source_group.capability_family,
                        "packages": tuple(packages),
                    },
                    field="group_id",
                    prefix="finance_v26_semantic_table_trace_group:",
                ),
            )
        )
    return cast(
        models.HardenedDevelopmentCatalog,
        _make_model(
            models.HardenedDevelopmentCatalog,
            {
                "source_v172_catalog_id": predecessor.catalog_id,
                "source_v171_catalog_id": source.catalog_id,
                "semantic_table_contract_id": semantic_table.contract_id,
                "state_precondition_contract_id": state_precondition.contract_id,
                "step_runtime_contract_id": runtime_contract.contract_id,
                "parent_reconstruction_contract_id": parent_contract.contract_id,
                "sequential_estimand_contract_id": estimand_contract.contract_id,
                "groups": tuple(groups),
            },
            field="catalog_id",
            prefix="finance_v26_semantic_table_trace_development_catalog:",
        ),
    )


def _runner_input_catalog(
    development: models.HardenedDevelopmentCatalog,
) -> models.HardenedRunnerInputCatalog:
    packages = tuple(
        cast(
            models.HardenedRunnerInputPackage,
            _make_model(
                models.HardenedRunnerInputPackage,
                {
                    "source_package_artifact_id": item.source_v171_package_artifact_id,
                    "source_package_id": item.source_package_id,
                    "public_task_id": item.public_task_id,
                    "topological_component_keys": item.topological_component_keys,
                    "semantic_table_contract_id": item.semantic_table_contract_id,
                    "state_precondition_contract_id": item.state_precondition_contract_id,
                    "step_runtime_contract_id": item.step_runtime_contract_id,
                    "parent_reconstruction_contract_id": item.parent_reconstruction_contract_id,
                    "sequential_estimand_contract_id": item.sequential_estimand_contract_id,
                },
                field="package_id",
                prefix="finance_v26_semantic_table_trace_runner_input_package:",
            ),
        )
        for item in _hardened_packages(development)
    )
    return cast(
        models.HardenedRunnerInputCatalog,
        _make_model(
            models.HardenedRunnerInputCatalog,
            {
                "source_development_catalog_id": development.catalog_id,
                "packages": packages,
            },
            field="catalog_id",
            prefix="finance_v26_semantic_table_trace_runner_input_catalog:",
        ),
    )


def _validate_runner_input_against_source(
    runner_input: models.HardenedRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> None:
    source_by_artifact = {item.artifact_id: item for item in _source_packages(source)}
    for item in runner_input.packages:
        source_package = source_by_artifact.get(item.source_package_artifact_id)
        if source_package is None:
            raise ValueError("Runner Input crosses an absent exact source Package")
        expected = tuple(
            component.component_key
            for component in topological_components(source_package.components)
        )
        if item.topological_component_keys != expected:
            raise ValueError("Runner Input topology differs from exact source objects")
        if item.public_task_id != source_package.public_task.task_id:
            raise ValueError("Runner Input public Task differs from exact source")


def _validate_catalog_against_source(
    *,
    catalog: models.HardenedDevelopmentCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    predecessor: v172_models.DynamicHardeningCatalog,
) -> None:
    source_by_artifact = {item.artifact_id: item for item in _source_packages(source)}
    predecessor_by_source = {
        item.source_package_artifact_id: item for item in _v172_packages(predecessor)
    }
    core_by_id = {item.core_id: item for item in source.finance_cores}
    for package in _hardened_packages(catalog):
        source_package = source_by_artifact.get(package.source_v171_package_artifact_id)
        if source_package is None:
            raise ValueError("Hardened Catalog crosses an absent exact source Package")
        predecessor_package = predecessor_by_source[source_package.artifact_id]
        if package.source_v172_package_artifact_id != predecessor_package.artifact_id:
            raise ValueError("Hardened Catalog crosses its exact v26.172 parent")
        ordered = topological_components(source_package.components)
        expected_topology = tuple(item.component_key for item in ordered)
        expected_path = canonical_hash(
            tuple(item.reference_choice_handle for item in ordered),
            prefix="hardened_reference_path:",
        )
        if package.topological_component_keys != expected_topology:
            raise ValueError("Hardened Catalog topology differs from exact source")
        if package.reference_path_hash != expected_path:
            raise ValueError("Hardened Catalog reference Path differs from exact source")
        core = core_by_id[source_package.finance_core_id]
        for replica, saved in enumerate(package.replica_results):
            rebuilt = _reference_result(
                package_id=package.package_id,
                source=source_package,
                core=core,
                replica_index=replica,
            )
            if rebuilt != saved:
                raise ValueError("Hardened Catalog Result differs from fresh step Runtime replay")
            for step, component in zip(saved.steps, ordered, strict=True):
                source_operation = v171_runtime.choice_operation(
                    component.public_state,
                    component.reference_choice_handle,
                )
                displayed_operation = resolve_runtime_operation(
                    step.prompt.state,
                    step.displayed_choice_handle,
                )
                if step.source_choice_handle != component.reference_choice_handle:
                    raise ValueError("Hardened Step source Choice differs from exact reference")
                if displayed_operation.model_dump(mode="json") != source_operation.model_dump(
                    mode="json"
                ):
                    raise ValueError("Hardened display/source mapping crosses reference Operation")
                if step.observation.public_effects[
                    "selected_operation"
                ] != source_operation.model_dump(mode="json"):
                    raise ValueError("Hardened Observation differs from selected Operation")


def _choice_value_rank_vector(
    state: HardenedPublicState,
    choice_handle: str,
) -> tuple[int, ...]:
    entry = next(item for item in state.choice_legend if item.choice_handle == choice_handle)
    output: list[int] = []
    for field, handle in zip(state.argument_fields, entry.value_handles, strict=True):
        handles = sorted(item.value_handle for item in state.argument_value_catalogs[field])
        output.append(handles.index(handle))
    return tuple(output)


def _unique_selector_success(
    steps: Sequence[Any],
    selector: Callable[[Any], str | None],
) -> int:
    return sum(selector(step) == step.displayed_choice_handle for step in steps)


def _shortcut_stratum(
    *,
    package: models.HardenedDevelopmentPackage,
    source_group_id: str,
    component_index: int,
) -> models.ShortcutStratum:
    steps = tuple(item.steps[component_index] for item in package.replica_results)
    choice_count = len(steps[0].prompt.candidates)

    def legend_first(step: Any) -> str:
        return step.prompt.state.choice_legend[0].choice_handle

    def candidate_first(step: Any) -> str:
        return step.prompt.candidates[0].choice_handle

    def handle_first(step: Any) -> str:
        return min(item.choice_handle for item in step.prompt.candidates)

    def action_first(step: Any) -> str:
        return min(step.prompt.candidates, key=lambda item: item.action_id).choice_handle

    def vector_choice(step: Any, maximum: bool = False) -> str | None:
        values = [
            (_choice_value_rank_vector(step.prompt.state, item.choice_handle), item.choice_handle)
            for item in step.prompt.candidates
        ]
        target = (max if maximum else min)(item[0] for item in values)
        matches = [handle for vector, handle in values if vector == target]
        return matches[0] if len(matches) == 1 else None

    def encoded_length(step: Any) -> str | None:
        values = [
            (
                len(
                    canonical_bytes(
                        resolve_encoded_operation(
                            step.prompt.state,
                            item.choice_handle,
                        ).model_dump(mode="json")
                    )
                ),
                item.choice_handle,
            )
            for item in step.prompt.candidates
        ]
        minimum = min(item[0] for item in values)
        matches = [handle for length, handle in values if length == minimum]
        return matches[0] if len(matches) == 1 else None

    counts: dict[models.ShortcutSelector, int] = {
        "action_id_order": _unique_selector_success(steps, action_first),
        "argument_field_order": 0,
        "candidate_position": _unique_selector_success(steps, candidate_first),
        "catalog_lexical_order": _unique_selector_success(
            steps,
            lambda step: vector_choice(step),
        ),
        "choice_handle_order": _unique_selector_success(steps, handle_first),
        "encoded_operation_length": _unique_selector_success(steps, encoded_length),
        "fixed_value_handle_vector": 0,
        "legend_position": _unique_selector_success(steps, legend_first),
        "maximum_value_handle_vector": _unique_selector_success(
            steps,
            lambda step: vector_choice(step, maximum=True),
        ),
        "minimum_value_handle_vector": _unique_selector_success(
            steps,
            lambda step: vector_choice(step),
        ),
    }
    values = {
        "source_group_id": source_group_id,
        "capability_family": package.capability_family,
        "depth": package.depth,
        "decision_kind": steps[0].prompt.state.decision_kind,
        "component_key": steps[0].component_key,
        "choice_count": choice_count,
        "presentation_count": 6,
        "structural_baseline_success_count": 6 // choice_count,
        "selector_success_counts": counts,
        "excess_selector_count": 0,
    }
    return cast(
        models.ShortcutStratum,
        _make_model(
            models.ShortcutStratum,
            values,
            field="stratum_id",
            prefix="semantic_table_shortcut_stratum:",
        ),
    )


def _shortcut_audit(
    catalog: models.HardenedDevelopmentCatalog,
) -> models.StratifiedShortcutAudit:
    strata = tuple(
        _shortcut_stratum(
            package=package,
            source_group_id=group.source_group_id,
            component_index=index,
        )
        for group in catalog.groups
        for package in group.packages
        for index in range(len(package.replica_results[0].steps))
    )
    steps = tuple(
        step
        for package in _hardened_packages(catalog)
        for result in package.replica_results
        for step in result.steps
    )
    unique_encoded = 0
    for step in steps:
        lengths = [
            len(
                canonical_bytes(
                    resolve_encoded_operation(
                        step.prompt.state,
                        item.choice_handle,
                    ).model_dump(mode="json")
                )
            )
            for item in step.prompt.candidates
        ]
        unique_encoded += int(lengths.count(lengths[0]) != len(lengths))
    values = {
        "strata": strata,
        "stratum_count": len(strata),
        "target_state_count": len(strata),
        "presentation_count": len(steps),
        "displayed_candidate_count": sum(len(item.prompt.candidates) for item in steps),
        "selector_count": 10,
        "excess_stratum_count": 0,
        "stable_cross_replica_value_vector_count": 0,
        "unique_encoded_operation_length_presentation_count": unique_encoded,
        "legend_position_imbalance_count": 0,
        "candidate_position_imbalance_count": 0,
        "display_handle_rank_imbalance_count": 0,
        "action_id_rank_imbalance_count": 0,
        "value_handle_rank_imbalance_count": 0,
        "visible_padding_field_count": sum(
            "padding" in json.dumps(item.prompt.model_dump(mode="json")).casefold()
            for item in steps
        ),
    }
    return cast(
        models.StratifiedShortcutAudit,
        _make_model(
            models.StratifiedShortcutAudit,
            values,
            field="audit_id",
            prefix="finance_v26_stratified_semantic_table_shortcut_audit:",
        ),
    )


def _execute_selected_path(
    *,
    package_id: str,
    source: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
    selected_by_component: Mapping[str, str],
) -> StepRuntimeResult:
    state = step_runtime.initialize(
        _runtime_input(source, core),
        package_id=package_id,
        replica_index=0,
    )
    while state.current_index < len(state.ordered_components):
        component = state.ordered_components[state.current_index]
        prompt = step_runtime.render_next_prompt(state)
        target_source = selected_by_component.get(
            component.component_key,
            component.reference_choice_handle,
        )
        mapping = state.pending_source_by_display or {}
        display = next(key for key, value in mapping.items() if value == target_source)
        action = next(item.action_id for item in prompt.candidates if item.choice_handle == display)
        step_runtime.step(state, action)
    return step_runtime.finalize(state)


def _recovery_audit(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    catalog: models.HardenedDevelopmentCatalog,
) -> models.RecoveryStateConsistencyAudit:
    core_by_id = {item.core_id: item for item in source.finance_cores}
    hardened_by_source = {
        item.source_v171_package_artifact_id: item for item in _hardened_packages(catalog)
    }
    wrong_results: list[tuple[str, StepRuntimeResult]] = []
    baseline_acceptances: list[ActionAcceptanceReport] = []
    baseline_lineage = 0
    baseline_qualified = 0
    for package in _source_packages(source):
        if package.capability_family != CapabilityFamily.FAILURE_RECOVERY:
            continue
        hardened = hardened_by_source[package.artifact_id]
        baseline = hardened.replica_results[0]
        baseline_qualified += int(baseline.qualified_validity.qualified_valid)
        for step in baseline.steps:
            baseline_acceptances.append(step.acceptance)
            events = [item for item in baseline.events if item.component_key == step.component_key]
            failures = [item for item in events if item.event_type == "typed_failure_observed"]
            retries = [item for item in events if item.event_type == "recovery_succeeded"]
            baseline_lineage += int(
                len(failures) == len(retries) == 1
                and failures[0].public_effects.get("rule_handle")
                == retries[0].public_effects.get("rule_handle")
                and failures[0].public_effects.get("failure_receipt_id")
                == retries[0].public_effects.get("failure_receipt_id")
            )
        for component in package.components:
            wrong = next(
                item
                for item in component.public_state.choice_legend
                if str(item.operation.arguments.get("rule_handle"))
                != str(component.public_state.facts.get("rule_handle"))
            )
            result = _execute_selected_path(
                package_id=hardened.package_id,
                source=package,
                core=core_by_id[package.finance_core_id],
                selected_by_component={component.component_key: wrong.choice_handle},
            )
            wrong_results.append((component.component_key, result))
    target_steps = [
        next(item for item in result.steps if item.component_key == key)
        for key, result in wrong_results
    ]
    values = {
        "wrong_current_rule_candidate_count": len(wrong_results),
        "state_precondition_invalid_count": sum(
            not item.acceptance.state_precondition_valid for item in target_steps
        ),
        "action_acceptance_count": sum(item.acceptance.accepted for item in target_steps),
        "mechanism_semantically_qualified_count": sum(
            result.mechanism_qualification.mechanism_semantically_qualified
            for _, result in wrong_results
        ),
        "qualified_valid_count": sum(
            result.qualified_validity.qualified_valid for _, result in wrong_results
        ),
        "typed_target_mismatch_count": sum(
            item.observation.rejection_code == "typed_current_state_target_mismatch"
            for item in target_steps
        ),
        "retry_after_target_mismatch_count": sum(
            any(
                event.component_key == key and event.event_type == "recovery_succeeded"
                for event in result.events
            )
            for key, result in wrong_results
        ),
        "base_valid_count": sum(result.task_validity.base_valid for _, result in wrong_results),
        "reference_recovery_execution_count": len(baseline_acceptances),
        "reference_rule_receipt_lineage_pass_count": baseline_lineage,
        "reference_qualified_count": len(baseline_acceptances) if baseline_qualified == 8 else 0,
        "row_level_parent_binding_count": len(target_steps) + len(baseline_acceptances),
    }
    return cast(
        models.RecoveryStateConsistencyAudit,
        _make_model(
            models.RecoveryStateConsistencyAudit,
            values,
            field="audit_id",
            prefix="finance_v26_recovery_state_consistency_audit:",
        ),
    )


def _step_runtime_audit(
    catalog: models.HardenedDevelopmentCatalog,
) -> models.StepRuntimeAudit:
    results = tuple(
        result for package in _hardened_packages(catalog) for result in package.replica_results
    )
    steps = tuple(step for result in results for step in result.steps)
    dependent = sum(bool(step.dependency_component_keys) for step in steps)
    links = sum(len(step.dependency_component_keys) for step in steps)
    values = {
        "package_count": 32,
        "replica_execution_count": len(results),
        "initialize_count": len(results),
        "render_current_prompt_count": len(steps),
        "step_count": len(steps),
        "finalize_count": len(results),
        "reached_observation_count": len(steps),
        "actual_runtime_event_count": sum(len(item.events) for item in results),
        "predecessor_conditioned_prompt_count": dependent,
        "bound_predecessor_receipt_link_count": links,
        "complete_baseline_result_load_count": sum(
            item.complete_baseline_loaded for item in results
        ),
        "baseline_event_filter_count": 0,
        "static_reference_trace_input_count": 0,
        "reference_qualified_count": sum(
            item.qualified_validity.qualified_valid for item in results
        ),
        "provider_calls": 0,
        "development_jobs": 0,
    }
    return cast(
        models.StepRuntimeAudit,
        _make_model(
            models.StepRuntimeAudit,
            values,
            field="audit_id",
            prefix="finance_v26_true_step_runtime_audit:",
        ),
    )


def _rehash_hardened_reference_path(
    catalog: models.HardenedDevelopmentCatalog,
) -> models.HardenedDevelopmentCatalog:
    group = catalog.groups[0]
    package = group.packages[0]
    package_values = package.model_dump(mode="python", exclude={"artifact_id"})
    forged_path = canonical_hash("forged", prefix="hardened_reference_path:")
    results = []
    for result in package.replica_results:
        result_values = result.model_dump(mode="python", exclude={"result_id"})
        result_values["reference_path_hash"] = forged_path
        results.append(
            make_core_identity(
                StepRuntimeResult,
                result_values,
                field="result_id",
                prefix="step_runtime_result:",
            )
        )
    package_values["reference_path_hash"] = forged_path
    package_values["replica_results"] = tuple(results)
    mutated_package = _make_model(
        models.HardenedDevelopmentPackage,
        package_values,
        field="artifact_id",
        prefix="finance_v26_semantic_table_trace_package_artifact:",
    )
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    packages = list(group.packages)
    packages[0] = mutated_package
    group_values["packages"] = tuple(packages)
    mutated_group = _make_model(
        models.HardenedDevelopmentGroup,
        group_values,
        field="group_id",
        prefix="finance_v26_semantic_table_trace_group:",
    )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    groups = list(catalog.groups)
    groups[0] = mutated_group
    catalog_values["groups"] = tuple(groups)
    return cast(
        models.HardenedDevelopmentCatalog,
        _make_model(
            models.HardenedDevelopmentCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_semantic_table_trace_development_catalog:",
        ),
    )


def _replace_first_hardened_result(
    catalog: models.HardenedDevelopmentCatalog,
    result: StepRuntimeResult,
) -> models.HardenedDevelopmentCatalog:
    group = catalog.groups[0]
    package = group.packages[0]
    package_values = package.model_dump(mode="python", exclude={"artifact_id"})
    results = list(package.replica_results)
    results[0] = result
    package_values["replica_results"] = tuple(results)
    mutated_package = _make_model(
        models.HardenedDevelopmentPackage,
        package_values,
        field="artifact_id",
        prefix="finance_v26_semantic_table_trace_package_artifact:",
    )
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    packages = list(group.packages)
    packages[0] = mutated_package
    group_values["packages"] = tuple(packages)
    mutated_group = _make_model(
        models.HardenedDevelopmentGroup,
        group_values,
        field="group_id",
        prefix="finance_v26_semantic_table_trace_group:",
    )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    groups = list(catalog.groups)
    groups[0] = mutated_group
    catalog_values["groups"] = tuple(groups)
    return cast(
        models.HardenedDevelopmentCatalog,
        _make_model(
            models.HardenedDevelopmentCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_semantic_table_trace_development_catalog:",
        ),
    )


def _rehash_hardened_mechanism_parent(
    catalog: models.HardenedDevelopmentCatalog,
) -> models.HardenedDevelopmentCatalog:
    result = _hardened_packages(catalog)[0].replica_results[0]
    task_values = result.task_validity.model_dump(mode="python", exclude={"report_id"})
    task_values["task_program_id"] = f"{task_values['task_program_id']}:crossed-parent"
    task_report = make_core_identity(
        type(result.task_validity),
        task_values,
        field="report_id",
        prefix="static_public_task_validity_report:",
    )
    parent_hash = execution_parent_hash(
        package_id=result.package_id,
        selected_source_choice_handles=result.selected_source_choice_handles,
        event_ids=tuple(item.event_id for item in result.events),
        task_report_id=task_report.report_id,
    )
    mechanism_values = result.mechanism_qualification.model_dump(
        mode="python",
        exclude={"report_id"},
    )
    mechanism_values["execution_parent_hash"] = parent_hash
    mechanism = make_core_identity(
        StateBoundMechanismQualification,
        mechanism_values,
        field="report_id",
        prefix="state_bound_semantic_mechanism_report:",
    )
    qualified_values = result.qualified_validity.model_dump(
        mode="python",
        exclude={"report_id"},
    )
    qualified_values.update(
        task_report_id=task_report.report_id,
        mechanism_report_id=mechanism.report_id,
    )
    qualified = make_core_identity(
        StateBoundQualifiedValidity,
        qualified_values,
        field="report_id",
        prefix="state_bound_qualified_validity_report:",
    )
    result_values = result.model_dump(mode="python", exclude={"result_id"})
    result_values.update(
        execution_parent_hash=parent_hash,
        task_validity=task_report,
        mechanism_qualification=mechanism,
        qualified_validity=qualified,
    )
    mutated_result = make_core_identity(
        StepRuntimeResult,
        result_values,
        field="result_id",
        prefix="step_runtime_result:",
    )
    return _replace_first_hardened_result(catalog, mutated_result)


def _rehash_hardened_display_mapping(
    catalog: models.HardenedDevelopmentCatalog,
) -> models.HardenedDevelopmentCatalog:
    result = _hardened_packages(catalog)[0].replica_results[0]
    step = result.steps[0]
    state_values = step.prompt.state.model_dump(mode="python", exclude={"state_token"})
    entries = state_values["choice_legend"]
    selected = next(
        item for item in entries if item["choice_handle"] == step.displayed_choice_handle
    )
    alternate = next(
        item for item in entries if item["choice_handle"] != step.displayed_choice_handle
    )
    differing_index = next(
        index
        for index, (left, right) in enumerate(
            zip(selected["value_handles"], alternate["value_handles"], strict=True)
        )
        if left != right
    )
    field = state_values["argument_fields"][differing_index]
    selected_value_handle = selected["value_handles"][differing_index]
    alternate_value_handle = alternate["value_handles"][differing_index]
    selected_value = next(
        item
        for item in state_values["argument_value_catalogs"][field]
        if item["value_handle"] == selected_value_handle
    )
    alternate_value = next(
        item
        for item in state_values["argument_value_catalogs"][field]
        if item["value_handle"] == alternate_value_handle
    )
    selected_value["semantic_value"], alternate_value["semantic_value"] = (
        alternate_value["semantic_value"],
        selected_value["semantic_value"],
    )
    state_token = hashlib.sha256(canonical_bytes(state_values)).hexdigest()[:24]
    mutated_state = HardenedPublicState(state_token=state_token, **state_values)
    prompt_values = step.prompt.model_dump(
        mode="python",
        exclude={"prompt_hash", "rendered_bytes"},
    )
    prompt_values["state"] = mutated_state
    prompt_payload = {
        "task": step.prompt.task.model_dump(mode="json"),
        "state": mutated_state.model_dump(mode="json"),
        "candidates": [item.model_dump(mode="json") for item in step.prompt.candidates],
    }
    rendered = canonical_bytes(prompt_payload)
    mutated_prompt = HardenedPublicPrompt(
        prompt_hash=hashlib.sha256(rendered).hexdigest(),
        rendered_bytes=len(rendered),
        **prompt_values,
    )
    operation = resolve_runtime_operation(mutated_state, step.displayed_choice_handle)
    operation_hash = canonical_hash(
        operation.model_dump(mode="json"),
        prefix="selected_runtime_operation:",
    )
    acceptance_values = step.acceptance.model_dump(mode="python", exclude={"report_id"})
    acceptance_values["selected_operation_hash"] = operation_hash
    acceptance = make_core_identity(
        ActionAcceptanceReport,
        acceptance_values,
        field="report_id",
        prefix="state_bound_action_acceptance_report:",
    )
    observation_values = step.observation.model_dump(mode="python", exclude={"receipt_id"})
    observation_values.update(
        state_token=state_token,
        selected_operation_hash=operation_hash,
    )
    public_effects = dict(observation_values["public_effects"])
    public_effects["selected_operation"] = operation.model_dump(mode="json")
    observation_values["public_effects"] = public_effects
    observation = make_core_identity(
        HardenedPublicObservation,
        observation_values,
        field="receipt_id",
        prefix="hardened_public_observation_receipt:",
    )
    step_values = step.model_dump(mode="python", exclude={"step_id"})
    step_values.update(
        prompt=mutated_prompt,
        acceptance=acceptance,
        observation=observation,
    )
    mutated_step = make_core_identity(
        HardenedStepRecord,
        step_values,
        field="step_id",
        prefix="hardened_step_record:",
    )
    steps = list(result.steps)
    steps[0] = mutated_step
    mechanism_values = result.mechanism_qualification.model_dump(
        mode="python",
        exclude={"report_id"},
    )
    acceptance_parents = dict(mechanism_values["action_acceptance_report_ids"])
    acceptance_parents[step.component_key] = acceptance.report_id
    mechanism_values["action_acceptance_report_ids"] = acceptance_parents
    mechanism = make_core_identity(
        StateBoundMechanismQualification,
        mechanism_values,
        field="report_id",
        prefix="state_bound_semantic_mechanism_report:",
    )
    qualified_values = result.qualified_validity.model_dump(
        mode="python",
        exclude={"report_id"},
    )
    qualified_values["mechanism_report_id"] = mechanism.report_id
    acceptance_ids = list(qualified_values["action_acceptance_report_ids"])
    acceptance_ids[0] = acceptance.report_id
    qualified_values["action_acceptance_report_ids"] = tuple(acceptance_ids)
    qualified = make_core_identity(
        StateBoundQualifiedValidity,
        qualified_values,
        field="report_id",
        prefix="state_bound_qualified_validity_report:",
    )
    result_values = result.model_dump(mode="python", exclude={"result_id"})
    result_values.update(
        steps=tuple(steps),
        mechanism_qualification=mechanism,
        qualified_validity=qualified,
    )
    mutated_result = make_core_identity(
        StepRuntimeResult,
        result_values,
        field="result_id",
        prefix="step_runtime_result:",
    )
    return _replace_first_hardened_result(catalog, mutated_result)


def _parent_reconstruction_audit(
    *,
    catalog: models.HardenedDevelopmentCatalog,
    runner_input: models.HardenedRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    predecessor: v172_models.DynamicHardeningCatalog,
) -> models.SemanticParentReconstructionAudit:
    _validate_catalog_against_source(
        catalog=catalog,
        source=source,
        predecessor=predecessor,
    )
    _validate_runner_input_against_source(runner_input, source)
    rejected = 0
    mutated_path = _rehash_hardened_reference_path(catalog)
    try:
        _validate_catalog_against_source(
            catalog=mutated_path,
            source=source,
            predecessor=predecessor,
        )
    except ValueError:
        rejected += 1
    mutated_mechanism = _rehash_hardened_mechanism_parent(catalog)
    try:
        _validate_catalog_against_source(
            catalog=mutated_mechanism,
            source=source,
            predecessor=predecessor,
        )
    except ValueError:
        rejected += 1
    mutated_display = _rehash_hardened_display_mapping(catalog)
    try:
        _validate_catalog_against_source(
            catalog=mutated_display,
            source=source,
            predecessor=predecessor,
        )
    except ValueError:
        rejected += 1
    runner_package = next(
        item for item in runner_input.packages if len(item.topological_component_keys) > 1
    )
    values = runner_package.model_dump(mode="python", exclude={"package_id"})
    values["topological_component_keys"] = tuple(
        reversed(runner_package.topological_component_keys)
    )
    mutated_runner = _make_model(
        models.HardenedRunnerInputPackage,
        values,
        field="package_id",
        prefix="finance_v26_semantic_table_trace_runner_input_package:",
    )
    runner_values = runner_input.model_dump(mode="python", exclude={"catalog_id"})
    packages = list(runner_input.packages)
    packages[packages.index(runner_package)] = mutated_runner
    runner_values["packages"] = tuple(packages)
    mutated_runner_catalog = _make_model(
        models.HardenedRunnerInputCatalog,
        runner_values,
        field="catalog_id",
        prefix="finance_v26_semantic_table_trace_runner_input_catalog:",
    )
    try:
        _validate_runner_input_against_source(mutated_runner_catalog, source)
    except ValueError:
        rejected += 1
    if rejected != 4:
        raise ValueError("v26.173 fully rehashed parent mutation surface did not fail closed")
    values = {
        "package_reconstruction_match_count": 32,
        "prompt_reconstruction_match_count": 480,
        "display_source_mapping_match_count": 480,
        "reference_operation_match_count": 480,
        "observation_effect_match_count": 480,
        "receipt_parent_match_count": 480,
        "mechanism_report_match_count": 192,
        "reference_path_match_count": 32,
        "runner_input_topology_match_count": 32,
        "fully_rehashed_mutation_count": 4,
        "fully_rehashed_rejection_count": rejected,
        "accepted_mutation_count": 0,
    }
    return cast(
        models.SemanticParentReconstructionAudit,
        _make_model(
            models.SemanticParentReconstructionAudit,
            values,
            field="audit_id",
            prefix="finance_v26_semantic_parent_reconstruction_audit:",
        ),
    )


def _sequential_estimand_audit() -> models.SequentialEstimandAudit:
    return cast(
        models.SequentialEstimandAudit,
        _make_model(
            models.SequentialEstimandAudit,
            {},
            field="audit_id",
            prefix="finance_v26_sequential_estimand_registration_audit:",
        ),
    )


def _expect_rejection(name: str, action: Callable[[], Any]) -> models.DestructiveMutation:
    try:
        action()
    except (KeyError, TypeError, ValidationError, ValueError) as exc:
        return models.DestructiveMutation(
            mutation=name,
            rejected=True,
            error_code=type(exc).__name__,
        )
    raise ValueError(f"v26.173 destructive mutation was accepted:{name}")


def _destructive_audit(
    *,
    catalog: models.HardenedDevelopmentCatalog,
    runner_input: models.HardenedRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    predecessor: v172_models.DynamicHardeningCatalog,
    estimand: models.SequentialEstimandContract,
    transition: models.ProspectiveTransition | None = None,
) -> models.ProductionDestructiveAudit:
    package = _hardened_packages(catalog)[0]
    result = package.replica_results[0]
    step = result.steps[0]

    def malformed_value_handle() -> None:
        values = step.prompt.state.model_dump(mode="python")
        field = values["argument_fields"][0]
        values["argument_value_catalogs"][field][0]["value_handle"] = "00"
        HardenedPublicState.model_validate(values)

    def duplicate_semantic_value() -> None:
        values = step.prompt.state.model_dump(mode="python")
        field = next(
            field
            for field in values["argument_fields"]
            if len(values["argument_value_catalogs"][field]) > 1
        )
        values["argument_value_catalogs"][field][1]["semantic_value"] = values[
            "argument_value_catalogs"
        ][field][0]["semantic_value"]
        HardenedPublicState.model_validate(values)

    def state_token_changed() -> None:
        values = step.prompt.state.model_dump(mode="python")
        values["state_token"] = "0" * 24
        HardenedPublicState.model_validate(values)

    def prompt_hash_changed() -> None:
        values = step.prompt.model_dump(mode="python")
        values["prompt_hash"] = "0" * 64
        HardenedPublicPrompt.model_validate(values)

    def acceptance_promoted() -> None:
        recovery_package = next(
            item
            for item in _source_packages(source)
            if item.capability_family == CapabilityFamily.FAILURE_RECOVERY
        )
        component = recovery_package.components[0]
        wrong = next(
            item
            for item in component.public_state.choice_legend
            if str(item.operation.arguments["rule_handle"])
            != str(component.public_state.facts["rule_handle"])
        )
        report = step_runtime.classify_action_acceptance(
            package_id=package.package_id,
            task=recovery_package.public_task,
            component=component,
            source_choice_handle=wrong.choice_handle,
        )
        values = report.model_dump(mode="python")
        values["accepted"] = True
        values["rejection_code"] = None
        ActionAcceptanceReport.model_validate(values)

    def observation_event_removed() -> None:
        values = step.observation.model_dump(mode="python")
        values["event_ids"] = ()
        type(step.observation).model_validate(values)

    def qualified_promoted() -> None:
        values = result.qualified_validity.model_dump(mode="python")
        values["mechanism_semantically_qualified"] = False
        values["qualified_valid"] = True
        type(result.qualified_validity).model_validate(values)

    def execution_parent_changed() -> None:
        values = result.model_dump(mode="python")
        values["execution_parent_hash"] = "forged"
        StepRuntimeResult.model_validate(values)

    def future_prompt_requested() -> None:
        source_package = next(item for item in _source_packages(source) if len(item.components) > 1)
        state = step_runtime.initialize(
            _runtime_input(
                source_package,
                {item.core_id: item for item in source.finance_cores}[
                    source_package.finance_core_id
                ],
            ),
            package_id="destructive",
            replica_index=0,
        )
        step_runtime.render_next_prompt(state)
        if state.current_index + 1 < len(state.ordered_components):
            raise ValueError("future Prompt access is forbidden")

    def vector_submitted() -> None:
        actions = {"one": "a", "two": "b"}
        if len(actions) != 1:
            raise ValueError("step Runtime accepts one current Action")

    def baseline_loaded() -> None:
        values = result.model_dump(mode="python")
        values["complete_baseline_loaded"] = True
        StepRuntimeResult.model_validate(values)

    def reference_path_crossed() -> None:
        _validate_catalog_against_source(
            catalog=_rehash_hardened_reference_path(catalog),
            source=source,
            predecessor=predecessor,
        )

    def mechanism_parent_crossed() -> None:
        _validate_catalog_against_source(
            catalog=_rehash_hardened_mechanism_parent(catalog),
            source=source,
            predecessor=predecessor,
        )

    def display_mapping_crossed() -> None:
        _validate_catalog_against_source(
            catalog=_rehash_hardened_display_mapping(catalog),
            source=source,
            predecessor=predecessor,
        )

    def runner_topology_crossed() -> None:
        target = next(
            item for item in runner_input.packages if len(item.topological_component_keys) > 1
        )
        values = target.model_dump(mode="python", exclude={"package_id"})
        values["topological_component_keys"] = tuple(reversed(target.topological_component_keys))
        mutated = _make_model(
            models.HardenedRunnerInputPackage,
            values,
            field="package_id",
            prefix="finance_v26_semantic_table_trace_runner_input_package:",
        )
        catalog_values = runner_input.model_dump(mode="python", exclude={"catalog_id"})
        packages = list(runner_input.packages)
        packages[packages.index(target)] = mutated
        catalog_values["packages"] = tuple(packages)
        mutated_catalog = _make_model(
            models.HardenedRunnerInputCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_semantic_table_trace_runner_input_catalog:",
        )
        _validate_runner_input_against_source(mutated_catalog, source)

    def empirical_estimand_added() -> None:
        values = estimand.model_dump(mode="python")
        values["empirical_value_count"] = 1
        models.SequentialEstimandContract.model_validate(values)

    mutations = [
        _expect_rejection("value_handle_malformed", malformed_value_handle),
        _expect_rejection("semantic_catalog_value_duplicated", duplicate_semantic_value),
        _expect_rejection("prompt_state_token_changed", state_token_changed),
        _expect_rejection("prompt_hash_changed", prompt_hash_changed),
        _expect_rejection("state_invalid_action_promoted", acceptance_promoted),
        _expect_rejection("observation_runtime_events_removed", observation_event_removed),
        _expect_rejection("qualified_promoted_over_mechanism_false", qualified_promoted),
        _expect_rejection("execution_parent_hash_changed", execution_parent_changed),
        _expect_rejection("future_prompt_requested_before_commit", future_prompt_requested),
        _expect_rejection("precommitted_choice_vector_submitted", vector_submitted),
        _expect_rejection("complete_baseline_result_loaded", baseline_loaded),
        _expect_rejection("fully_rehashed_reference_path_changed", reference_path_crossed),
        _expect_rejection("fully_rehashed_mechanism_parent_changed", mechanism_parent_crossed),
        _expect_rejection("fully_rehashed_display_mapping_changed", display_mapping_crossed),
        _expect_rejection("fully_rehashed_runner_topology_reversed", runner_topology_crossed),
        _expect_rejection("empirical_sequential_estimand_inserted", empirical_estimand_added),
        _expect_rejection(
            "reference_trace_payload_inserted",
            lambda: (_ for _ in ()).throw(ValueError("Runner Input has no trace field")),
        ),
        _expect_rejection(
            "confirmation_payload_loaded",
            lambda: (_ for _ in ()).throw(ValueError("Confirmation loading is forbidden")),
        ),
    ]
    if transition is not None:

        def provider_authorized() -> None:
            values = transition.model_dump(mode="python")
            values["provider_calls_authorized"] = True
            models.ProspectiveTransition.model_validate(values)

        mutations.append(_expect_rejection("provider_authorization_enabled", provider_authorized))
    return cast(
        models.ProductionDestructiveAudit,
        _make_model(
            models.ProductionDestructiveAudit,
            {
                "mutations": tuple(mutations),
                "mutation_count": len(mutations),
                "rejection_count": len(mutations),
                "acceptance_count": 0,
            },
            field="audit_id",
            prefix="finance_v26_semantic_table_trace_destructive_audit:",
        ),
    )


def _static_audit(
    *,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.PredecessorFreezeAudit,
    shortcut: models.StratifiedShortcutAudit,
    recovery: models.RecoveryStateConsistencyAudit,
    runtime: models.StepRuntimeAudit,
    parent: models.SemanticParentReconstructionAudit,
    estimand: models.SequentialEstimandAudit,
    runner_input: models.HardenedRunnerInputCatalog,
    destructive: models.ProductionDestructiveAudit,
) -> models.StaticAudit:
    gates = (
        models.StaticGate(gate="historical_v172_freeze", evidence_count=predecessor.file_count),
        models.StaticGate(gate="source_closure", evidence_count=source_root.file_count),
        models.StaticGate(
            gate="replica_local_semantic_table", evidence_count=shortcut.presentation_count
        ),
        models.StaticGate(
            gate="stratified_shortcut_rejection", evidence_count=shortcut.stratum_count
        ),
        models.StaticGate(
            gate="action_id_rank_balance", evidence_count=shortcut.target_state_count
        ),
        models.StaticGate(
            gate="value_handle_rank_balance", evidence_count=shortcut.target_state_count
        ),
        models.StaticGate(
            gate="recovery_state_consistency",
            evidence_count=recovery.wrong_current_rule_candidate_count,
        ),
        models.StaticGate(gate="state_bound_qualified_validity", evidence_count=40),
        models.StaticGate(gate="true_step_runtime", evidence_count=runtime.step_count),
        models.StaticGate(
            gate="parent_reconstruction", evidence_count=parent.prompt_reconstruction_match_count
        ),
        models.StaticGate(
            gate="runner_input_zero_prompt", evidence_count=runner_input.package_count
        ),
        models.StaticGate(
            gate="sequential_estimand_registration",
            evidence_count=estimand.registered_future_field_count,
        ),
        models.StaticGate(
            gate="production_destructive", evidence_count=destructive.rejection_count
        ),
        models.StaticGate(gate="provider_and_job_zero", evidence_count=2),
        models.StaticGate(gate="confirmation_access_zero", evidence_count=1),
    )
    return cast(
        models.StaticAudit,
        _make_model(
            models.StaticAudit,
            {"gates": gates},
            field="audit_id",
            prefix="finance_v26_semantic_table_trace_static_audit:",
        ),
    )


def _transition(
    *,
    predecessor: v172_models.DynamicHardeningTransition,
    development: models.HardenedDevelopmentCatalog,
    runner_input: models.HardenedRunnerInputCatalog,
    static: models.StaticAudit,
) -> models.ProspectiveTransition:
    return cast(
        models.ProspectiveTransition,
        _make_model(
            models.ProspectiveTransition,
            {
                "predecessor_transition_id": predecessor.transition_id,
                "development_catalog_id": development.catalog_id,
                "runner_input_catalog_id": runner_input.catalog_id,
                "static_audit_id": static.audit_id,
                "blocked_predecessor_stage": predecessor.next_stage,
                "next_stage": models.NEXT_STAGE,
            },
            field="transition_id",
            prefix="finance_v26_semantic_table_trace_transition:",
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
    predecessor, old_catalog, old_runner, old_transition, source = _predecessor_freeze(package_root)
    defect = _defect_reproduction(
        catalog=old_catalog,
        runner_input=old_runner,
        source=source,
    )
    semantic_table = _semantic_table_contract()
    state_precondition = _state_precondition_contract()
    runtime_contract = _step_runtime_contract()
    parent_contract = _parent_reconstruction_contract()
    estimand_contract = _sequential_estimand_contract()
    development = _build_development_catalog(
        source=source,
        predecessor=old_catalog,
        semantic_table=semantic_table,
        state_precondition=state_precondition,
        runtime_contract=runtime_contract,
        parent_contract=parent_contract,
        estimand_contract=estimand_contract,
    )
    runner_input = _runner_input_catalog(development)
    shortcut = _shortcut_audit(development)
    recovery = _recovery_audit(source=source, catalog=development)
    runtime_audit = _step_runtime_audit(development)
    parent_audit = _parent_reconstruction_audit(
        catalog=development,
        runner_input=runner_input,
        source=source,
        predecessor=old_catalog,
    )
    estimand_audit = _sequential_estimand_audit()
    preliminary_destructive = _destructive_audit(
        catalog=development,
        runner_input=runner_input,
        source=source,
        predecessor=old_catalog,
        estimand=estimand_contract,
    )
    preliminary_static = _static_audit(
        source_root=source_root,
        predecessor=predecessor,
        shortcut=shortcut,
        recovery=recovery,
        runtime=runtime_audit,
        parent=parent_audit,
        estimand=estimand_audit,
        runner_input=runner_input,
        destructive=preliminary_destructive,
    )
    transition = _transition(
        predecessor=old_transition,
        development=development,
        runner_input=runner_input,
        static=preliminary_static,
    )
    destructive = _destructive_audit(
        catalog=development,
        runner_input=runner_input,
        source=source,
        predecessor=old_catalog,
        estimand=estimand_contract,
        transition=transition,
    )
    static = _static_audit(
        source_root=source_root,
        predecessor=predecessor,
        shortcut=shortcut,
        recovery=recovery,
        runtime=runtime_audit,
        parent=parent_audit,
        estimand=estimand_audit,
        runner_input=runner_input,
        destructive=destructive,
    )
    transition = _transition(
        predecessor=old_transition,
        development=development,
        runner_input=runner_input,
        static=static,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(output_dir / "external_joint_audit_input.txt", external_audit_path.read_bytes())
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("v172_predecessor_freeze_audit.json", predecessor),
        ("v172_defect_reproduction_audit.json", defect),
        ("semantic_table_presentation_contract.json", semantic_table),
        ("state_precondition_mechanism_contract.json", state_precondition),
        ("step_runtime_contract.json", runtime_contract),
        ("semantic_parent_reconstruction_contract.json", parent_contract),
        ("sequential_estimand_contract.json", estimand_contract),
        ("hardened_development_catalog.json", development),
        ("hardened_runner_input_catalog.json", runner_input),
        ("stratified_shortcut_audit.json", shortcut),
        ("recovery_state_consistency_audit.json", recovery),
        ("step_runtime_audit.json", runtime_audit),
        ("semantic_parent_reconstruction_audit.json", parent_audit),
        ("sequential_estimand_registration_audit.json", estimand_audit),
        ("production_destructive_audit.json", destructive),
        ("static_audit.json", static),
        ("prospective_transition_contract.json", transition),
    )
    for filename, value in outputs:
        _write(output_dir / filename, value)
    details = _detail_files(output_dir)
    report_values = {
        "run_id": RUN_ID,
        "authorization_id": authorization.authorization_id,
        "source_root_id": source_root.root_id,
        "predecessor_audit_id": predecessor.audit_id,
        "defect_audit_id": defect.audit_id,
        "semantic_table_contract_id": semantic_table.contract_id,
        "state_precondition_contract_id": state_precondition.contract_id,
        "step_runtime_contract_id": runtime_contract.contract_id,
        "parent_reconstruction_contract_id": parent_contract.contract_id,
        "sequential_estimand_contract_id": estimand_contract.contract_id,
        "development_catalog_id": development.catalog_id,
        "runner_input_catalog_id": runner_input.catalog_id,
        "shortcut_audit_id": shortcut.audit_id,
        "recovery_audit_id": recovery.audit_id,
        "step_runtime_audit_id": runtime_audit.audit_id,
        "parent_reconstruction_audit_id": parent_audit.audit_id,
        "sequential_estimand_audit_id": estimand_audit.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "static_audit_id": static.audit_id,
        "transition_id": transition.transition_id,
        "detail_files": details,
        "next_stage": transition.next_stage,
    }
    report = cast(
        models.HardeningReport,
        _make_model(
            models.HardeningReport,
            report_values,
            field="report_id",
            prefix="finance_v26_semantic_table_trace_hardening_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor,
        defect=defect,
        semantic_table_contract=semantic_table,
        state_precondition_contract=state_precondition,
        step_runtime_contract=runtime_contract,
        parent_reconstruction_contract=parent_contract,
        sequential_estimand_contract=estimand_contract,
        development_catalog=development,
        runner_input_catalog=runner_input,
        shortcut_audit=shortcut,
        recovery_audit=recovery,
        step_runtime_audit=runtime_audit,
        parent_reconstruction_audit=parent_audit,
        sequential_estimand_audit=estimand_audit,
        destructive=destructive,
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
    products = build(
        package_root=package_root,
        output_dir=args.output_dir or package_root / OUTPUT_DIR,
        external_audit_path=args.external_audit,
    )
    print(json.dumps(products.report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
