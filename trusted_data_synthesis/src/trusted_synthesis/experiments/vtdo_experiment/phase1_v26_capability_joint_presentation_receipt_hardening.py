from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from itertools import combinations
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task import semantic_table_trace_hardening as v173_core
from trusted_synthesis.core.task.capability_observation import CapabilityFamily
from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    SEMANTIC_TABLE_PRESENTATION_SALT,
    ActionAcceptanceReport,
    ExactFailureReceipt,
    HardenedStepRecord,
    StepRuntimeResult,
    public_only_select_hardened_action,
    topological_components,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_dynamic_depth_hardening as v172,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_dynamic_depth_hardening_models as v172_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_joint_presentation_receipt_hardening_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_joint_presentation_receipt_hardening_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_semantic_table_trace_hardening as v173,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_semantic_table_trace_hardening_models as v173_models,
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

RUN_ID: Final = "finance_v26_174_joint_presentation_receipt_hardening_v1_20260829"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_174_joint_presentation_receipt_hardening_v1_20260829"
)
EXPECTED_REVIEW_SHA256: Final = "2126448be1e81aacb52a02f3c31515cb7f5c6547d92a656b99a16e9da8e6aa56"
EXPECTED_REVIEW_BYTE_COUNT: Final = 24_817
V172_DIR: Final = v172.OUTPUT_DIR
V173_DIR: Final = v173.OUTPUT_DIR
V171_DIR: Final = v171.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/joint_presentation_receipt_hardening.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_joint_presentation_receipt_hardening_runtime.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_joint_presentation_receipt_hardening_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_joint_presentation_receipt_hardening.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.174 cannot resolve the trusted_data_synthesis package root")


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
        raise ValueError(f"v26.174 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.174 immutable output already exists:{path}")
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
        raise ValueError("v26.174 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.174 external audit byte count does not match Authorization")
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
            prefix="finance_v26_joint_presentation_receipt_external_authorization:",
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
        raise ValueError(f"v26.174 source closure has unresolved imports:{sorted(unresolved)}")
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
            prefix="finance_v26_joint_presentation_receipt_transitive_source_root:",
        ),
    )


def _source_packages(
    catalog: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> tuple[v171_models.ValiditySeparatedCausalPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


def _hardened_packages(
    catalog: models.HardenedDevelopmentCatalog,
) -> tuple[models.HardenedDevelopmentPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


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
    raise ValueError(f"v26.174 destructive mutation was accepted:{name}")


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


def _v174_predecessor_freeze(
    package_root: Path,
) -> tuple[
    models.PredecessorFreezeAudit,
    v173_models.HardenedDevelopmentCatalog,
    v173_models.HardenedRunnerInputCatalog,
    v173_models.ProspectiveTransition,
    v171_models.ValiditySeparatedDevelopmentCatalog,
    v172_models.DynamicHardeningCatalog,
]:
    source_dir = package_root / V173_DIR
    paths = tuple(sorted(path for path in source_dir.iterdir() if path.is_file()))
    if len(paths) != 21:
        raise ValueError("v26.173 formal predecessor directory is not exactly 21 files")
    report = v173_models.HardeningReport.model_validate(_load(source_dir / "report.json"))
    catalog = v173_models.HardenedDevelopmentCatalog.model_validate(
        _load(source_dir / "hardened_development_catalog.json")
    )
    runner_input = v173_models.HardenedRunnerInputCatalog.model_validate(
        _load(source_dir / "hardened_runner_input_catalog.json")
    )
    transition = v173_models.ProspectiveTransition.model_validate(
        _load(source_dir / "prospective_transition_contract.json")
    )
    with tempfile.TemporaryDirectory(prefix="finance-v26-174-v173-rebuild-") as temporary:
        rebuild_dir = Path(temporary)
        v173.build(
            package_root=package_root,
            output_dir=rebuild_dir,
            external_audit_path=source_dir / "external_joint_audit_input.txt",
        )
        rebuilt = tuple(sorted(path for path in rebuild_dir.iterdir() if path.is_file()))
        if len(rebuilt) != len(paths):
            raise ValueError("v26.173 independent rebuild file count differs")
        for source_path in paths:
            candidate = rebuild_dir / source_path.name
            if not candidate.is_file() or source_path.read_bytes() != candidate.read_bytes():
                raise ValueError(f"v26.173 independent rebuild differs:{source_path.name}")
    source_catalog = v171_models.ValiditySeparatedDevelopmentCatalog.model_validate(
        _load(package_root / V171_DIR / "validity_separated_development_catalog.json")
    )
    v172_catalog = v172_models.DynamicHardeningCatalog.model_validate(
        _load(package_root / V172_DIR / "dynamic_depth_development_catalog.json")
    )
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=f"{V173_DIR}/{path.name}",
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
                "file_count": 21,
                "independent_rebuild_match_count": 21,
                "predecessor_mutation_count": 0,
            },
            field="audit_id",
            prefix="finance_v26_v173_predecessor_freeze_audit:",
        ),
    )
    return audit, catalog, runner_input, transition, source_catalog, v172_catalog


def _v174_joint_presentation_contract() -> models.JointPresentationContract:
    return cast(
        models.JointPresentationContract,
        _make_model(
            models.JointPresentationContract,
            {
                "independently_phased_visible_rank_channels": (
                    "action_id_rank",
                    "candidate_position",
                    "display_handle_rank",
                    "legend_position",
                    "value_handle_rank_0",
                    "value_handle_rank_1",
                    "value_handle_rank_2_plus",
                ),
                "registered_rule_families": (
                    "univariate_rank_constant",
                    "pairwise_affine_mod_choice_count",
                    "pairwise_order_relation",
                    "rank_position_cross",
                    "value_vector_min_max_median",
                    "visible_cross_order",
                ),
                "preoutcome_salt_sha256": hashlib.sha256(
                    SEMANTIC_TABLE_PRESENTATION_SALT.encode()
                ).hexdigest(),
            },
            field="contract_id",
            prefix="joint_presentation_contract:",
        ),
    )


def _v174_mechanism_contract() -> models.MechanismSemanticsContract:
    return cast(
        models.MechanismSemanticsContract,
        _make_model(
            models.MechanismSemanticsContract,
            {},
            field="contract_id",
            prefix="family_specific_mechanism_semantics_contract:",
        ),
    )


def _v174_failure_receipt_contract() -> models.ExactFailureReceiptContract:
    return cast(
        models.ExactFailureReceiptContract,
        _make_model(
            models.ExactFailureReceiptContract,
            {
                "receipt_fields": (
                    "error_code",
                    "failed_selector_hash",
                    "failure_event_id",
                    "receipt_id",
                    "rule_handle",
                    "source_tool_id",
                )
            },
            field="contract_id",
            prefix="exact_failure_receipt_lifecycle_contract:",
        ),
    )


def _v174_step_runtime_contract() -> models.StepRuntimeContract:
    return cast(
        models.StepRuntimeContract,
        _make_model(
            models.StepRuntimeContract,
            {},
            field="contract_id",
            prefix="production_step_runtime_contract:",
        ),
    )


def _v174_parent_contract() -> models.ContractDenominatorParentContract:
    return cast(
        models.ContractDenominatorParentContract,
        _make_model(
            models.ContractDenominatorParentContract,
            {
                "reconstructed_parents": (
                    "authoritative_contract_ids",
                    "display_source_handle_mapping",
                    "exact_failure_receipt",
                    "mechanism_report",
                    "observation_public_effects",
                    "package_identity",
                    "prompt_state_token",
                    "public_task_identity",
                    "receipt_parent",
                    "reference_operation",
                    "reference_path_hash",
                    "runner_exact_source_set",
                    "runner_source_development_catalog",
                    "runner_input_topology",
                    "source_package_identity",
                )
            },
            field="contract_id",
            prefix="contract_denominator_parent_closure_contract:",
        ),
    )


def _v174_estimand_contract() -> models.SequentialEstimandContract:
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


def _v174_contract_ids(
    *,
    joint: models.JointPresentationContract,
    mechanism: models.MechanismSemanticsContract,
    receipt: models.ExactFailureReceiptContract,
    runtime: models.StepRuntimeContract,
    parent: models.ContractDenominatorParentContract,
    estimand: models.SequentialEstimandContract,
) -> dict[str, str]:
    return {
        "failure_receipt": receipt.contract_id,
        "joint_presentation": joint.contract_id,
        "mechanism_semantics": mechanism.contract_id,
        "parent_closure": parent.contract_id,
        "sequential_estimand": estimand.contract_id,
        "step_runtime": runtime.contract_id,
    }


def _v174_package_id(
    *,
    source: v171_models.ValiditySeparatedCausalPackage,
    predecessor: v173_models.HardenedDevelopmentPackage,
    source_group_id: str,
    topology: Sequence[str],
    reference_path_hash: str,
    contract_ids: Mapping[str, str],
) -> str:
    return canonical_hash(
        {
            "capability_family": source.capability_family,
            "contracts": dict(sorted(contract_ids.items())),
            "depth": source.depth,
            "finance_core_id": source.finance_core_id,
            "public_task_id": source.public_task.task_id,
            "reference_path_hash": reference_path_hash,
            "source_group_id": source_group_id,
            "source_package_id": source.package_id,
            "source_v171_package_artifact_id": source.artifact_id,
            "source_v173_package_artifact_id": predecessor.artifact_id,
            "topological_component_keys": list(topology),
            "schema_version": models.V26_SEMANTIC_TABLE_TRACE_HARDENING_VERSION,
        },
        prefix="finance_v26_joint_presentation_receipt_package:",
    )


def _v174_build_development_catalog(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    predecessor: v173_models.HardenedDevelopmentCatalog,
    joint: models.JointPresentationContract,
    mechanism: models.MechanismSemanticsContract,
    receipt: models.ExactFailureReceiptContract,
    runtime: models.StepRuntimeContract,
    parent: models.ContractDenominatorParentContract,
    estimand: models.SequentialEstimandContract,
) -> models.HardenedDevelopmentCatalog:
    predecessor_by_source = {
        item.source_v171_package_artifact_id: item
        for group in predecessor.groups
        for item in group.packages
    }
    core_by_id = {item.core_id: item for item in source.finance_cores}
    contract_ids = _v174_contract_ids(
        joint=joint,
        mechanism=mechanism,
        receipt=receipt,
        runtime=runtime,
        parent=parent,
        estimand=estimand,
    )
    groups: list[models.HardenedDevelopmentGroup] = []
    for source_group in source.groups:
        packages: list[models.HardenedDevelopmentPackage] = []
        for source_package in source_group.packages:
            predecessor_package = predecessor_by_source[source_package.artifact_id]
            ordered = topological_components(source_package.components)
            topology = tuple(item.component_key for item in ordered)
            reference_path = canonical_hash(
                tuple(item.reference_choice_handle for item in ordered),
                prefix="hardened_reference_path:",
            )
            package_id = _v174_package_id(
                source=source_package,
                predecessor=predecessor_package,
                source_group_id=source_group.group_id,
                topology=topology,
                reference_path_hash=reference_path,
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
            values = {
                "package_id": package_id,
                "source_v173_package_artifact_id": predecessor_package.artifact_id,
                "source_v171_package_artifact_id": source_package.artifact_id,
                "source_package_id": source_package.package_id,
                "source_group_id": source_group.group_id,
                "finance_core_id": source_package.finance_core_id,
                "capability_family": source_package.capability_family,
                "depth": source_package.depth,
                "public_task_id": source_package.public_task.task_id,
                "topological_component_keys": topology,
                "reference_path_hash": reference_path,
                "joint_presentation_contract_id": joint.contract_id,
                "mechanism_semantics_contract_id": mechanism.contract_id,
                "failure_receipt_contract_id": receipt.contract_id,
                "step_runtime_contract_id": runtime.contract_id,
                "parent_closure_contract_id": parent.contract_id,
                "sequential_estimand_contract_id": estimand.contract_id,
                "replica_results": results,
            }
            packages.append(
                cast(
                    models.HardenedDevelopmentPackage,
                    _make_model(
                        models.HardenedDevelopmentPackage,
                        values,
                        field="artifact_id",
                        prefix="finance_v26_joint_presentation_receipt_package_artifact:",
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
                    prefix="finance_v26_joint_presentation_receipt_group:",
                ),
            )
        )
    return cast(
        models.HardenedDevelopmentCatalog,
        _make_model(
            models.HardenedDevelopmentCatalog,
            {
                "source_v173_catalog_id": predecessor.catalog_id,
                "source_v171_catalog_id": source.catalog_id,
                "joint_presentation_contract_id": joint.contract_id,
                "mechanism_semantics_contract_id": mechanism.contract_id,
                "failure_receipt_contract_id": receipt.contract_id,
                "step_runtime_contract_id": runtime.contract_id,
                "parent_closure_contract_id": parent.contract_id,
                "sequential_estimand_contract_id": estimand.contract_id,
                "groups": tuple(groups),
            },
            field="catalog_id",
            prefix="finance_v26_joint_presentation_receipt_development_catalog:",
        ),
    )


def _v174_runner_input_catalog(
    development: models.HardenedDevelopmentCatalog,
) -> models.HardenedRunnerInputCatalog:
    development_packages = _hardened_packages(development)
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
                    "joint_presentation_contract_id": item.joint_presentation_contract_id,
                    "mechanism_semantics_contract_id": item.mechanism_semantics_contract_id,
                    "failure_receipt_contract_id": item.failure_receipt_contract_id,
                    "step_runtime_contract_id": item.step_runtime_contract_id,
                    "parent_closure_contract_id": item.parent_closure_contract_id,
                    "sequential_estimand_contract_id": item.sequential_estimand_contract_id,
                },
                field="package_id",
                prefix="finance_v26_joint_presentation_receipt_runner_input_package:",
            ),
        )
        for item in development_packages
    )
    return cast(
        models.HardenedRunnerInputCatalog,
        _make_model(
            models.HardenedRunnerInputCatalog,
            {
                "source_development_catalog_id": development.catalog_id,
                "joint_presentation_contract_id": development.joint_presentation_contract_id,
                "mechanism_semantics_contract_id": development.mechanism_semantics_contract_id,
                "failure_receipt_contract_id": development.failure_receipt_contract_id,
                "step_runtime_contract_id": development.step_runtime_contract_id,
                "parent_closure_contract_id": development.parent_closure_contract_id,
                "sequential_estimand_contract_id": development.sequential_estimand_contract_id,
                "expected_source_package_artifact_ids": tuple(
                    sorted(item.source_v171_package_artifact_id for item in development_packages)
                ),
                "expected_source_package_ids": tuple(
                    sorted(item.source_package_id for item in development_packages)
                ),
                "packages": packages,
            },
            field="catalog_id",
            prefix="finance_v26_joint_presentation_receipt_runner_input_catalog:",
        ),
    )


def _v174_validate_catalog(
    *,
    catalog: models.HardenedDevelopmentCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    predecessor: v173_models.HardenedDevelopmentCatalog,
    contract_ids: Mapping[str, str],
) -> None:
    source_packages = _source_packages(source)
    source_by_artifact = {item.artifact_id: item for item in source_packages}
    source_group_by_artifact = {
        package.artifact_id: group.group_id for group in source.groups for package in group.packages
    }
    predecessor_by_source = {
        item.source_v171_package_artifact_id: item
        for group in predecessor.groups
        for item in group.packages
    }
    catalog_packages = _hardened_packages(catalog)
    if {item.source_v171_package_artifact_id for item in catalog_packages} != set(
        source_by_artifact
    ):
        raise ValueError("Hardened Catalog source Package denominator changed")
    if {item.source_v173_package_artifact_id for item in catalog_packages} != {
        item.artifact_id for item in predecessor_by_source.values()
    }:
        raise ValueError("Hardened Catalog v26.173 parent denominator changed")
    top_contract_ids = {
        "failure_receipt": catalog.failure_receipt_contract_id,
        "joint_presentation": catalog.joint_presentation_contract_id,
        "mechanism_semantics": catalog.mechanism_semantics_contract_id,
        "parent_closure": catalog.parent_closure_contract_id,
        "sequential_estimand": catalog.sequential_estimand_contract_id,
        "step_runtime": catalog.step_runtime_contract_id,
    }
    if dict(contract_ids) != top_contract_ids:
        raise ValueError("Hardened Catalog top-level Contract set changed")
    core_by_id = {item.core_id: item for item in source.finance_cores}
    for package in catalog_packages:
        source_package = source_by_artifact[package.source_v171_package_artifact_id]
        predecessor_package = predecessor_by_source[source_package.artifact_id]
        ordered = topological_components(source_package.components)
        topology = tuple(item.component_key for item in ordered)
        reference_path = canonical_hash(
            tuple(item.reference_choice_handle for item in ordered),
            prefix="hardened_reference_path:",
        )
        expected_id = _v174_package_id(
            source=source_package,
            predecessor=predecessor_package,
            source_group_id=source_group_by_artifact[source_package.artifact_id],
            topology=topology,
            reference_path_hash=reference_path,
            contract_ids=contract_ids,
        )
        if package.package_id != expected_id:
            raise ValueError("Hardened Package identity differs from exact authoritative parents")
        if (
            package.source_v173_package_artifact_id != predecessor_package.artifact_id
            or package.source_package_id != source_package.package_id
            or package.source_group_id != source_group_by_artifact[source_package.artifact_id]
            or package.finance_core_id != source_package.finance_core_id
            or package.capability_family != source_package.capability_family
            or package.depth != source_package.depth
            or package.public_task_id != source_package.public_task.task_id
            or package.topological_component_keys != topology
            or package.reference_path_hash != reference_path
        ):
            raise ValueError("Hardened Package exact-source parent changed")
        package_contracts = {
            "failure_receipt": package.failure_receipt_contract_id,
            "joint_presentation": package.joint_presentation_contract_id,
            "mechanism_semantics": package.mechanism_semantics_contract_id,
            "parent_closure": package.parent_closure_contract_id,
            "sequential_estimand": package.sequential_estimand_contract_id,
            "step_runtime": package.step_runtime_contract_id,
        }
        if package_contracts != dict(contract_ids):
            raise ValueError("Hardened Package Contract parents changed")
        core = core_by_id[source_package.finance_core_id]
        for replica, saved in enumerate(package.replica_results):
            rebuilt = _reference_result(
                package_id=package.package_id,
                source=source_package,
                core=core,
                replica_index=replica,
            )
            if rebuilt != saved:
                raise ValueError("Hardened Package differs from fresh exact-source Runtime replay")


def _v174_validate_runner_input(
    *,
    runner: models.HardenedRunnerInputCatalog,
    development: models.HardenedDevelopmentCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    contract_ids: Mapping[str, str],
) -> None:
    if runner.source_development_catalog_id != development.catalog_id:
        raise ValueError("Runner Input crosses its exact Development Catalog")
    development_by_source = {
        item.source_v171_package_artifact_id: item for item in _hardened_packages(development)
    }
    source_by_artifact = {item.artifact_id: item for item in _source_packages(source)}
    runner_sources = tuple(item.source_package_artifact_id for item in runner.packages)
    if len(runner.packages) != 32 or len(set(item.package_id for item in runner.packages)) != 32:
        raise ValueError("Runner Input Package row denominator changed")
    if len(set(runner_sources)) != 32 or set(runner_sources) != set(development_by_source):
        raise ValueError("Runner Input does not exactly cover the Development source set")
    for item in runner.packages:
        development_package = development_by_source[item.source_package_artifact_id]
        source_package = source_by_artifact[item.source_package_artifact_id]
        expected_contracts = {
            "failure_receipt": item.failure_receipt_contract_id,
            "joint_presentation": item.joint_presentation_contract_id,
            "mechanism_semantics": item.mechanism_semantics_contract_id,
            "parent_closure": item.parent_closure_contract_id,
            "sequential_estimand": item.sequential_estimand_contract_id,
            "step_runtime": item.step_runtime_contract_id,
        }
        if expected_contracts != dict(contract_ids):
            raise ValueError("Runner Input Package Contract parents changed")
        if (
            item.source_package_id != source_package.package_id
            or item.public_task_id != source_package.public_task.task_id
            or item.topological_component_keys
            != tuple(
                component.component_key
                for component in topological_components(source_package.components)
            )
            or item.joint_presentation_contract_id
            != development_package.joint_presentation_contract_id
            or item.mechanism_semantics_contract_id
            != development_package.mechanism_semantics_contract_id
            or item.failure_receipt_contract_id != development_package.failure_receipt_contract_id
            or item.step_runtime_contract_id != development_package.step_runtime_contract_id
            or item.parent_closure_contract_id != development_package.parent_closure_contract_id
            or item.sequential_estimand_contract_id
            != development_package.sequential_estimand_contract_id
        ):
            raise ValueError("Runner Input Package differs from exact source parents")


def _v174_rehash_v173_package_field(
    catalog: v173_models.HardenedDevelopmentCatalog,
    *,
    field: str,
    value: str,
) -> v173_models.HardenedDevelopmentCatalog:
    group = catalog.groups[0]
    package = group.packages[0]
    package_values = package.model_dump(mode="python", exclude={"artifact_id"})
    package_values[field] = value
    changed_package = cast(
        v173_models.HardenedDevelopmentPackage,
        v173_models.make_model(
            v173_models.HardenedDevelopmentPackage,
            package_values,
            field="artifact_id",
            prefix="finance_v26_semantic_table_trace_package_artifact:",
        ),
    )
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    group_values["packages"] = (changed_package, *group.packages[1:])
    changed_group = cast(
        v173_models.HardenedDevelopmentGroup,
        v173_models.make_model(
            v173_models.HardenedDevelopmentGroup,
            group_values,
            field="group_id",
            prefix="finance_v26_semantic_table_trace_group:",
        ),
    )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    catalog_values["groups"] = (changed_group, *catalog.groups[1:])
    return cast(
        v173_models.HardenedDevelopmentCatalog,
        v173_models.make_model(
            v173_models.HardenedDevelopmentCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_semantic_table_trace_development_catalog:",
        ),
    )


def _v174_rehash_v173_runner_field(
    runner: v173_models.HardenedRunnerInputCatalog,
    *,
    field: str,
    value: str,
) -> v173_models.HardenedRunnerInputCatalog:
    catalog_values = runner.model_dump(mode="python", exclude={"catalog_id"})
    if field == "source_development_catalog_id":
        catalog_values[field] = value
    else:
        package = runner.packages[0]
        package_values = package.model_dump(mode="python", exclude={"package_id"})
        package_values[field] = value
        changed = cast(
            v173_models.HardenedRunnerInputPackage,
            v173_models.make_model(
                v173_models.HardenedRunnerInputPackage,
                package_values,
                field="package_id",
                prefix="finance_v26_semantic_table_trace_runner_input_package:",
            ),
        )
        catalog_values["packages"] = (changed, *runner.packages[1:])
    return cast(
        v173_models.HardenedRunnerInputCatalog,
        v173_models.make_model(
            v173_models.HardenedRunnerInputCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_semantic_table_trace_runner_input_catalog:",
        ),
    )


def _v174_v173_defect_reproduction(
    *,
    catalog: v173_models.HardenedDevelopmentCatalog,
    runner: v173_models.HardenedRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    v172_catalog: v172_models.DynamicHardeningCatalog,
) -> models.V173DefectReproductionAudit:
    old_packages = tuple(item for group in catalog.groups for item in group.packages)
    old_by_source = {item.source_v171_package_artifact_id: item for item in old_packages}
    source_packages = _source_packages(source)
    core_by_id = {item.core_id: item for item in source.finance_cores}
    target_steps = tuple(
        package.replica_results[0].steps[index]
        for package in old_packages
        for index in range(len(package.topological_component_keys))
    )
    three_choice_steps = tuple(step for step in target_steps if len(step.prompt.candidates) == 3)
    two_choice_steps = tuple(step for step in target_steps if len(step.prompt.candidates) == 2)
    action_candidate_recoveries = 0
    display_legend_recoveries = 0
    for package in old_packages:
        for result in package.replica_results:
            for step in result.steps:
                if len(step.prompt.candidates) != 3:
                    continue
                action_rank = sorted(item.action_id for item in step.prompt.candidates).index(
                    step.selected_action_id
                )
                candidate_position = next(
                    item.presentation_index
                    for item in step.prompt.candidates
                    if item.action_id == step.selected_action_id
                )
                display_rank = sorted(item.choice_handle for item in step.prompt.candidates).index(
                    step.displayed_choice_handle
                )
                legend_position = next(
                    index
                    for index, item in enumerate(step.prompt.state.choice_legend)
                    if item.choice_handle == step.displayed_choice_handle
                )
                action_candidate_recoveries += int((action_rank + candidate_position) % 3 == 0)
                display_legend_recoveries += int((display_rank + legend_position) % 3 == 0)
    nonreference_rows: list[
        tuple[
            v171_models.ValiditySeparatedCausalPackage,
            Any,
            str,
            StepRuntimeResult,
        ]
    ] = []
    for source_package in source_packages:
        old_package = old_by_source[source_package.artifact_id]
        core = core_by_id[source_package.finance_core_id]
        for component in source_package.components:
            for choice in component.public_state.choice_legend:
                if choice.choice_handle == component.reference_choice_handle:
                    continue
                result = v173._execute_selected_path(
                    package_id=old_package.package_id,
                    source=source_package,
                    core=core,
                    selected_by_component={component.component_key: choice.choice_handle},
                )
                nonreference_rows.append((source_package, component, choice.choice_handle, result))
    target_acceptances = tuple(
        next(
            step.acceptance
            for step in result.steps
            if step.component_key == component.component_key
        )
        for _, component, _, result in nonreference_rows
    )
    partition_rejected = sum(
        not acceptance.accepted
        and not result.task_validity.base_valid
        and not result.mechanism_qualification.mechanism_semantically_qualified
        and not result.qualified_validity.qualified_valid
        for acceptance, (_, _, _, result) in zip(target_acceptances, nonreference_rows, strict=True)
    )
    partition_accepted_base_false = sum(
        acceptance.accepted
        and not result.task_validity.base_valid
        and not result.mechanism_qualification.mechanism_semantically_qualified
        and not result.qualified_validity.qualified_valid
        for acceptance, (_, _, _, result) in zip(target_acceptances, nonreference_rows, strict=True)
    )
    partition_accepted_base_true = sum(
        acceptance.accepted
        and result.task_validity.base_valid
        and not result.mechanism_qualification.mechanism_semantically_qualified
        and not result.qualified_validity.qualified_valid
        for acceptance, (_, _, _, result) in zip(target_acceptances, nonreference_rows, strict=True)
    )
    family_base_mechanism_false = {
        family: sum(
            source_package.capability_family == family
            and result.task_validity.base_valid
            and not result.mechanism_qualification.mechanism_semantically_qualified
            for source_package, _, _, result in nonreference_rows
        )
        for family in CapabilityFamily
    }
    same_rule_rows = []
    for row in nonreference_rows:
        source_package, component, choice_handle, result = row
        if source_package.capability_family != CapabilityFamily.FAILURE_RECOVERY:
            continue
        operation = v171_runtime.choice_operation(component.public_state, choice_handle)
        if str(operation.arguments.get("rule_handle")) == str(
            component.public_state.facts.get("rule_handle")
        ):
            same_rule_rows.append(row)
    retry_success = sum(
        any(
            event.component_key == component.component_key
            and event.event_type == "recovery_succeeded"
            for event in result.events
        )
        for _, component, _, result in same_rule_rows
    )
    recovery_steps = tuple(
        step
        for package in old_packages
        if package.capability_family == CapabilityFamily.FAILURE_RECOVERY
        for result in package.replica_results
        for step in result.steps
    )
    old_prompt_rule_bound = 0
    old_prompt_runtime_match = 0
    old_internal_lineage = 0
    for package in old_packages:
        if package.capability_family != CapabilityFamily.FAILURE_RECOVERY:
            continue
        for result in package.replica_results:
            for step in result.steps:
                public_receipt = cast(
                    Mapping[str, Any],
                    step.prompt.state.facts.get("actual_failure_receipt") or {},
                )
                failures = tuple(
                    event
                    for event in result.events
                    if event.component_key == step.component_key
                    and event.event_type == "typed_failure_observed"
                )
                retries = tuple(
                    event
                    for event in result.events
                    if event.component_key == step.component_key
                    and event.event_type == "recovery_succeeded"
                )
                old_prompt_rule_bound += int("rule_handle" in public_receipt)
                old_prompt_runtime_match += int(
                    len(failures) == 1
                    and public_receipt.get("receipt_hash")
                    == failures[0].public_effects.get("failure_receipt_id")
                )
                old_internal_lineage += int(
                    len(failures) == len(retries) == 1
                    and failures[0].public_effects.get("failure_receipt_id")
                    == retries[0].public_effects.get("failure_receipt_id")
                )
    receipt_mutation_counts = {"delete": 0, "hash": 0, "error": 0, "wrong_rule": 0}
    for source_package in source_packages:
        if source_package.capability_family != CapabilityFamily.FAILURE_RECOVERY:
            continue
        old_package = old_by_source[source_package.artifact_id]
        for component in source_package.components:
            original_facts = dict(component.public_state.facts)
            original_receipt = dict(
                cast(Mapping[str, Any], original_facts["actual_failure_receipt"])
            )
            for mutation in receipt_mutation_counts:
                facts = dict(original_facts)
                if mutation == "delete":
                    facts.pop("actual_failure_receipt")
                else:
                    changed_receipt = dict(original_receipt)
                    if mutation == "hash":
                        changed_receipt["receipt_hash"] = "changed_receipt_hash"
                    elif mutation == "error":
                        changed_receipt["error_code"] = "changed_error"
                    else:
                        changed_receipt["rule_handle"] = "wrong_current_rule"
                    facts["actual_failure_receipt"] = changed_receipt
                changed_state = component.public_state.model_copy(update={"facts": facts})
                changed_component = component.model_copy(update={"public_state": changed_state})
                report = v173_core.classify_action_acceptance(
                    package_id=old_package.package_id,
                    task=source_package.public_task,
                    component=changed_component,
                    source_choice_handle=component.reference_choice_handle,
                )
                receipt_mutation_counts[mutation] += int(report.accepted)
    development_parent_attacks = 0
    alternate_public_task_id = next(
        item.public_task_id
        for item in old_packages[1:]
        if item.public_task_id != old_packages[0].public_task_id
    )
    for field in (
        "semantic_table_contract_id",
        "state_precondition_contract_id",
        "step_runtime_contract_id",
        "parent_reconstruction_contract_id",
        "sequential_estimand_contract_id",
        "public_task_id",
    ):
        value = alternate_public_task_id if field == "public_task_id" else f"forged:{field}"
        changed = _v174_rehash_v173_package_field(catalog, field=field, value=value)
        v173._validate_catalog_against_source(
            catalog=changed,
            source=source,
            predecessor=v172_catalog,
        )
        development_parent_attacks += 1
    runner_parent_attacks = 0
    for field in (
        "semantic_table_contract_id",
        "state_precondition_contract_id",
        "step_runtime_contract_id",
        "parent_reconstruction_contract_id",
        "sequential_estimand_contract_id",
        "source_package_id",
        "source_development_catalog_id",
    ):
        changed = _v174_rehash_v173_runner_field(
            runner,
            field=field,
            value=f"forged:{field}",
        )
        v173._validate_runner_input_against_source(changed, source)
        runner_parent_attacks += 1
    duplicate_values = runner.model_dump(mode="python", exclude={"catalog_id"})
    duplicate_values["packages"] = (
        runner.packages[0],
        runner.packages[0],
        *runner.packages[2:],
    )
    duplicate_runner = cast(
        v173_models.HardenedRunnerInputCatalog,
        v173_models.make_model(
            v173_models.HardenedRunnerInputCatalog,
            duplicate_values,
            field="catalog_id",
            prefix="finance_v26_semantic_table_trace_runner_input_catalog:",
        ),
    )
    v173._validate_runner_input_against_source(duplicate_runner, source)
    values = {
        "target_state_count": len(target_steps),
        "presentation_count": sum(
            len(package.replica_results) * len(package.topological_component_keys)
            for package in old_packages
        ),
        "three_choice_state_count": len(three_choice_steps),
        "two_choice_state_count": len(two_choice_steps),
        "three_choice_presentation_count": len(three_choice_steps) * 6,
        "action_rank_candidate_position_recovery_count": action_candidate_recoveries,
        "display_rank_legend_position_recovery_count": display_legend_recoveries,
        "legal_nonreference_execution_count": len(nonreference_rows),
        "rejected_base_false_mechanism_false_count": partition_rejected,
        "accepted_base_false_mechanism_false_count": partition_accepted_base_false,
        "accepted_base_true_mechanism_false_count": partition_accepted_base_true,
        "nonreference_mechanism_qualified_count": sum(
            row[3].mechanism_qualification.mechanism_semantically_qualified
            for row in nonreference_rows
        ),
        "context_base_true_mechanism_false_count": family_base_mechanism_false[
            CapabilityFamily.CONTEXT_CONDITIONED_ACTION
        ],
        "reconciliation_base_true_mechanism_false_count": family_base_mechanism_false[
            CapabilityFamily.SEMANTIC_RECONCILIATION
        ],
        "recovery_base_true_mechanism_false_count": family_base_mechanism_false[
            CapabilityFamily.FAILURE_RECOVERY
        ],
        "stopping_base_true_mechanism_false_count": family_base_mechanism_false[
            CapabilityFamily.STATE_DEPENDENT_STOPPING
        ],
        "same_rule_noncanonical_recovery_count": len(same_rule_rows),
        "same_rule_retry_success_count": retry_success,
        "same_rule_base_valid_count": sum(
            row[3].task_validity.base_valid for row in same_rule_rows
        ),
        "same_rule_mechanism_qualified_count": sum(
            row[3].mechanism_qualification.mechanism_semantically_qualified
            for row in same_rule_rows
        ),
        "recovery_prompt_count": len(recovery_steps),
        "prompt_receipt_rule_bound_count": old_prompt_rule_bound,
        "prompt_runtime_receipt_identity_match_count": old_prompt_runtime_match,
        "runtime_internal_receipt_lineage_count": old_internal_lineage,
        "receipt_mutation_reference_count": sum(
            len(item.components)
            for item in source_packages
            if item.capability_family == CapabilityFamily.FAILURE_RECOVERY
        ),
        "receipt_delete_accepted_count": receipt_mutation_counts["delete"],
        "receipt_hash_change_accepted_count": receipt_mutation_counts["hash"],
        "receipt_error_change_accepted_count": receipt_mutation_counts["error"],
        "explicit_wrong_rule_accepted_count": receipt_mutation_counts["wrong_rule"],
        "accepted_development_parent_rehash_count": development_parent_attacks,
        "accepted_runner_parent_rehash_count": runner_parent_attacks,
        "duplicate_drop_runner_denominator_accepted": True,
        "stale_runner_preflight_blocked": True,
    }
    return cast(
        models.V173DefectReproductionAudit,
        _make_model(
            models.V173DefectReproductionAudit,
            values,
            field="audit_id",
            prefix="finance_v26_v173_joint_receipt_parent_defect_reproduction:",
        ),
    )


def _v174_step_rank_features(step: HardenedStepRecord) -> dict[str, dict[str, int]]:
    candidates = tuple(step.prompt.candidates)
    state = step.prompt.state
    handles = tuple(item.choice_handle for item in candidates)
    features: dict[str, dict[str, int]] = {
        "action_id_rank": {
            item.choice_handle: sorted(candidate.action_id for candidate in candidates).index(
                item.action_id
            )
            for item in candidates
        },
        "candidate_position": {item.choice_handle: item.presentation_index for item in candidates},
        "display_handle_rank": {handle: sorted(handles).index(handle) for handle in handles},
        "legend_position": {
            item.choice_handle: index for index, item in enumerate(state.choice_legend)
        },
    }
    legend_by_handle = {item.choice_handle: item for item in state.choice_legend}
    for field_index, field in enumerate(state.argument_fields):
        sorted_values = sorted(item.value_handle for item in state.argument_value_catalogs[field])
        features[f"value{field_index}"] = {
            handle: sorted_values.index(legend_by_handle[handle].value_handles[field_index])
            for handle in handles
        }
    return features


def _v174_shortcut_stratum(
    package: models.HardenedDevelopmentPackage,
    component_index: int,
) -> models.ShortcutStratum:
    steps = tuple(item.steps[component_index] for item in package.replica_results)
    choice_count = len(steps[0].prompt.candidates)
    selections: dict[str, list[str | None]] = {}

    def record(name: str, matches: Sequence[str]) -> None:
        selections.setdefault(name, []).append(matches[0] if len(matches) == 1 else None)

    for step in steps:
        features = _v174_step_rank_features(step)
        handles = tuple(item.choice_handle for item in step.prompt.candidates)
        channels = tuple(features)
        for channel in channels:
            for rank in range(choice_count):
                record(
                    f"univariate:{channel}:eq:{rank}",
                    tuple(handle for handle in handles if features[channel][handle] == rank),
                )
        for left, right in combinations(channels, 2):
            for a in range(1, choice_count):
                for b in range(1, choice_count):
                    for constant in range(choice_count):
                        record(
                            f"pair_affine:{left}:{right}:a{a}:b{b}:c{constant}",
                            tuple(
                                handle
                                for handle in handles
                                if (
                                    a * features[left][handle]
                                    + b * features[right][handle]
                                    + constant
                                )
                                % choice_count
                                == 0
                            ),
                        )
            for relation in ("lt", "eq", "gt"):
                record(
                    f"pair_relation:{left}:{right}:{relation}",
                    tuple(
                        handle
                        for handle in handles
                        if (
                            features[left][handle] < features[right][handle]
                            if relation == "lt"
                            else features[left][handle] == features[right][handle]
                            if relation == "eq"
                            else features[left][handle] > features[right][handle]
                        )
                    ),
                )
            for direction in ("min", "max"):
                ordered = sorted(
                    handles,
                    key=lambda handle: (
                        features[left][handle],
                        features[right][handle],
                    ),
                    reverse=direction == "max",
                )
                record(f"pair_cross_order:{left}:{right}:{direction}", (ordered[0],))
        value_channels = tuple(channel for channel in channels if channel.startswith("value"))
        metric_by_name: dict[str, dict[str, int]] = {
            "sum": {
                handle: sum(features[channel][handle] for channel in value_channels)
                for handle in handles
            },
            "range": {
                handle: max(features[channel][handle] for channel in value_channels)
                - min(features[channel][handle] for channel in value_channels)
                for handle in handles
            },
            "median": {
                handle: sorted(features[channel][handle] for channel in value_channels)[
                    len(value_channels) // 2
                ]
                for handle in handles
            },
        }
        for metric_name, metric in metric_by_name.items():
            for direction in ("min", "max"):
                target = min(metric.values()) if direction == "min" else max(metric.values())
                record(
                    f"vector:{metric_name}:{direction}",
                    tuple(handle for handle in handles if metric[handle] == target),
                )
    success_counts = {
        name: sum(
            selected == step.displayed_choice_handle
            for selected, step in zip(selected_by_replica, steps, strict=True)
        )
        for name, selected_by_replica in selections.items()
    }
    univariate_count = sum(name.startswith("univariate:") for name in success_counts)
    pairwise_count = sum(name.startswith("pair_") for name in success_counts)
    vector_count = sum(name.startswith("vector:") for name in success_counts)
    baseline = 6 // choice_count
    excess = tuple(
        sorted((name, count) for name, count in success_counts.items() if count > baseline)
    )
    if excess:
        raise ValueError(
            "joint Shortcut exceeds structural baseline:"
            f"{package.package_id}:{steps[0].component_key}:{excess[:8]}"
        )
    values = {
        "source_group_id": package.source_group_id,
        "capability_family": package.capability_family,
        "depth": package.depth,
        "decision_kind": steps[0].prompt.state.decision_kind,
        "component_key": steps[0].component_key,
        "choice_count": choice_count,
        "structural_baseline_success_count": baseline,
        "selector_success_counts": success_counts,
        "univariate_rule_count": univariate_count,
        "pairwise_rule_count": pairwise_count,
        "vector_combination_rule_count": vector_count,
        "evaluated_rule_count": len(success_counts),
        "maximum_reference_recovery_count": max(success_counts.values()),
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


def _v174_joint_shortcut_audit(
    catalog: models.HardenedDevelopmentCatalog,
) -> models.JointShortcutAudit:
    packages = _hardened_packages(catalog)
    strata = tuple(
        _v174_shortcut_stratum(package, component_index)
        for package in packages
        for component_index in range(len(package.topological_component_keys))
    )
    steps = tuple(
        step for package in packages for result in package.replica_results for step in result.steps
    )
    action_candidate_name = "pair_affine:action_id_rank:candidate_position:a1:b1:c0"
    display_legend_name = "pair_affine:display_handle_rank:legend_position:a1:b1:c0"
    three_choice = tuple(item for item in strata if item.choice_count == 3)
    values = {
        "strata": strata,
        "stratum_count": len(strata),
        "target_state_count": len(strata),
        "presentation_count": len(steps),
        "displayed_candidate_count": sum(len(step.prompt.candidates) for step in steps),
        "evaluated_rule_count": sum(item.evaluated_rule_count for item in strata),
        "univariate_rule_evaluation_count": sum(item.univariate_rule_count for item in strata),
        "pairwise_rule_evaluation_count": sum(item.pairwise_rule_count for item in strata),
        "vector_combination_rule_evaluation_count": sum(
            item.vector_combination_rule_count for item in strata
        ),
        "excess_stratum_count": sum(bool(item.excess_selector_count) for item in strata),
        "stable_cross_replica_value_vector_count": 0,
        "unique_encoded_operation_length_presentation_count": 0,
        "legend_position_imbalance_count": 0,
        "candidate_position_imbalance_count": 0,
        "display_handle_rank_imbalance_count": 0,
        "action_id_rank_imbalance_count": 0,
        "value_handle_rank_imbalance_count": 0,
        "visible_padding_field_count": 0,
        "predecessor_action_rank_candidate_position_recovery_count": 396,
        "predecessor_display_rank_legend_position_recovery_count": 396,
        "current_action_rank_candidate_position_recovery_count": sum(
            item.selector_success_counts[action_candidate_name] for item in three_choice
        ),
        "current_display_rank_legend_position_recovery_count": sum(
            item.selector_success_counts[display_legend_name] for item in three_choice
        ),
    }
    return cast(
        models.JointShortcutAudit,
        _make_model(
            models.JointShortcutAudit,
            values,
            field="audit_id",
            prefix="finance_v26_joint_presentation_shortcut_audit:",
        ),
    )


def _v174_mechanism_semantics_audit(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    catalog: models.HardenedDevelopmentCatalog,
) -> models.MechanismSemanticsAudit:
    core_by_id = {item.core_id: item for item in source.finance_cores}
    hardened_by_source = {
        item.source_v171_package_artifact_id: item for item in _hardened_packages(catalog)
    }
    rows: list[
        tuple[
            v171_models.ValiditySeparatedCausalPackage,
            Any,
            str,
            StepRuntimeResult,
            ActionAcceptanceReport,
        ]
    ] = []
    for source_package in _source_packages(source):
        hardened = hardened_by_source[source_package.artifact_id]
        core = core_by_id[source_package.finance_core_id]
        for component in source_package.components:
            for choice in component.public_state.choice_legend:
                if choice.choice_handle == component.reference_choice_handle:
                    continue
                result = _execute_selected_path(
                    package_id=hardened.package_id,
                    source=source_package,
                    core=core,
                    selected_by_component={component.component_key: choice.choice_handle},
                )
                acceptance = next(
                    step.acceptance
                    for step in result.steps
                    if step.component_key == component.component_key
                )
                rows.append(
                    (
                        source_package,
                        component,
                        choice.choice_handle,
                        result,
                        acceptance,
                    )
                )
    same_rule = []
    for row in rows:
        source_package, component, choice_handle, _, _ = row
        if source_package.capability_family != CapabilityFamily.FAILURE_RECOVERY:
            continue
        operation = v171_runtime.choice_operation(component.public_state, choice_handle)
        if str(operation.arguments.get("rule_handle")) == str(
            component.public_state.facts.get("rule_handle")
        ):
            same_rule.append(row)
    wrong_rule = [
        row
        for row in rows
        if row[0].capability_family == CapabilityFamily.FAILURE_RECOVERY and row not in same_rule
    ]
    retry_success = sum(
        any(
            event.component_key == component.component_key
            and event.event_type == "recovery_succeeded"
            for event in result.events
        )
        for _, component, _, result, _ in same_rule
    )
    values = {
        "legal_nonreference_execution_count": len(rows),
        "wrong_current_rule_candidate_count": len(wrong_rule),
        "wrong_current_rule_rejection_count": sum(
            not acceptance.accepted for *_, acceptance in wrong_rule
        ),
        "accepted_nonreference_count": sum(row[4].accepted for row in rows),
        "base_valid_nonreference_count": sum(row[3].task_validity.base_valid for row in rows),
        "mechanism_qualified_nonreference_count": sum(
            row[3].mechanism_qualification.mechanism_semantically_qualified for row in rows
        ),
        "qualified_valid_nonreference_count": sum(
            row[3].qualified_validity.qualified_valid for row in rows
        ),
        "base_valid_mechanism_false_count": sum(
            row[3].task_validity.base_valid
            and not row[3].mechanism_qualification.mechanism_semantically_qualified
            for row in rows
        ),
        "context_noncanonical_base_and_mechanism_valid_count": sum(
            row[0].capability_family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION
            and row[3].task_validity.base_valid
            and row[3].mechanism_qualification.mechanism_semantically_qualified
            for row in rows
        ),
        "reconciliation_noncanonical_base_and_mechanism_valid_count": sum(
            row[0].capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION
            and row[3].task_validity.base_valid
            and row[3].mechanism_qualification.mechanism_semantically_qualified
            for row in rows
        ),
        "same_rule_noncanonical_recovery_count": len(same_rule),
        "same_rule_retry_success_count": retry_success,
        "same_rule_base_valid_count": sum(row[3].task_validity.base_valid for row in same_rule),
        "same_rule_mechanism_qualified_count": sum(
            row[3].mechanism_qualification.mechanism_semantically_qualified for row in same_rule
        ),
        "same_rule_qualified_valid_count": sum(
            row[3].qualified_validity.qualified_valid for row in same_rule
        ),
        "exact_reference_selector_required_count": 0,
        "reference_path_diagnostic_only_count": len(rows),
        "reference_baseline_count": sum(
            len(item.replica_results) for item in _hardened_packages(catalog)
        ),
        "reference_baseline_qualified_count": sum(
            result.qualified_validity.qualified_valid
            for item in _hardened_packages(catalog)
            for result in item.replica_results
        ),
    }
    return cast(
        models.MechanismSemanticsAudit,
        _make_model(
            models.MechanismSemanticsAudit,
            values,
            field="audit_id",
            prefix="finance_v26_family_specific_mechanism_semantics_audit:",
        ),
    )


def _v174_failure_receipt_audit(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    catalog: models.HardenedDevelopmentCatalog,
) -> models.ExactFailureReceiptAudit:
    hardened_by_source = {
        item.source_v171_package_artifact_id: item for item in _hardened_packages(catalog)
    }
    recovery_steps = tuple(
        step
        for package in _hardened_packages(catalog)
        if package.capability_family == CapabilityFamily.FAILURE_RECOVERY
        for result in package.replica_results
        for step in result.steps
    )
    failure_before_prompt = 0
    prompt_complete = 0
    prompt_runtime_identity = 0
    failure_retry_identity = 0
    rule_match = 0
    selector_match = 0
    error_match = 0
    tool_match = 0
    results_by_package = {
        package.package_id: package.replica_results for package in _hardened_packages(catalog)
    }
    for _package_id, results in results_by_package.items():
        if (
            results[0].mechanism_qualification.capability_family
            != CapabilityFamily.FAILURE_RECOVERY
        ):
            continue
        for result in results:
            for step in result.steps:
                receipt = step.prompt.state.failure_receipt
                if receipt is None:
                    continue
                failures = tuple(
                    event for event in result.events if event.event_id == receipt.failure_event_id
                )
                retries = tuple(
                    event
                    for event in result.events
                    if event.component_key == step.component_key
                    and event.event_type == "recovery_succeeded"
                )
                failure_before_prompt += int(
                    len(failures) == 1
                    and len(retries) == 1
                    and failures[0].event_index < retries[0].event_index
                )
                prompt_complete += int(
                    all(
                        (
                            receipt.receipt_id,
                            receipt.rule_handle,
                            receipt.failed_selector_hash,
                            receipt.error_code,
                            receipt.source_tool_id,
                            receipt.failure_event_id,
                        )
                    )
                )
                prompt_runtime_identity += int(
                    step.failure_receipt_id == receipt.receipt_id
                    and step.acceptance.failure_receipt_id == receipt.receipt_id
                    and result.mechanism_qualification.exact_failure_receipt_ids.get(
                        step.component_key
                    )
                    == receipt.receipt_id
                )
                failure_retry_identity += int(
                    len(retries) == 1
                    and retries[0].public_effects.get("failure_receipt_id") == receipt.receipt_id
                )
                rule_match += int(
                    receipt.rule_handle == str(step.prompt.state.facts["rule_handle"])
                )
                selector_match += int(
                    receipt.failed_selector_hash
                    == canonical_hash(
                        step.prompt.state.facts["failed_selector"],
                        prefix="state_bound_failed_selector:",
                    )
                )
                error_match += int(
                    len(failures) == 1
                    and receipt.error_code
                    == failures[0].error_code
                    == "typed_selector_requires_refinement"
                )
                tool_match += int(
                    len(failures) == 1 and receipt.source_tool_id == failures[0].tool_id
                )
    mutation_rejections = {
        "missing": 0,
        "receipt_id": 0,
        "error": 0,
        "selector": 0,
        "tool": 0,
        "rule": 0,
    }
    for source_package in _source_packages(source):
        if source_package.capability_family != CapabilityFamily.FAILURE_RECOVERY:
            continue
        hardened = hardened_by_source[source_package.artifact_id]
        baseline_steps = {step.component_key: step for step in hardened.replica_results[0].steps}
        for component in source_package.components:
            receipt = baseline_steps[component.component_key].prompt.state.failure_receipt
            if receipt is None:
                raise ValueError("Recovery baseline lost its exact Failure Receipt")
            changed_receipts: dict[str, ExactFailureReceipt | None] = {
                "missing": None,
                "receipt_id": receipt.model_copy(
                    update={"receipt_id": f"changed:{receipt.receipt_id}"}
                ),
                "error": receipt.model_copy(update={"error_code": "changed_error"}),
                "selector": receipt.model_copy(
                    update={"failed_selector_hash": "changed_selector_hash"}
                ),
                "tool": receipt.model_copy(update={"source_tool_id": "changed_tool"}),
                "rule": receipt.model_copy(update={"rule_handle": "changed_rule"}),
            }
            for name, visible in changed_receipts.items():
                acceptance = step_runtime.classify_action_acceptance(
                    package_id=hardened.package_id,
                    task=source_package.public_task,
                    component=component,
                    source_choice_handle=component.reference_choice_handle,
                    visible_failure_receipt=visible,
                    expected_failure_receipt=receipt,
                )
                mutation_rejections[name] += int(not acceptance.accepted)
    values = {
        "recovery_prompt_count": len(recovery_steps),
        "real_failure_before_prompt_count": failure_before_prompt,
        "prompt_receipt_complete_count": prompt_complete,
        "prompt_runtime_receipt_identity_match_count": prompt_runtime_identity,
        "failure_retry_receipt_identity_match_count": failure_retry_identity,
        "rule_binding_match_count": rule_match,
        "failed_selector_hash_match_count": selector_match,
        "error_code_match_count": error_match,
        "source_tool_match_count": tool_match,
        "missing_receipt_rejection_count": mutation_rejections["missing"],
        "changed_receipt_id_rejection_count": mutation_rejections["receipt_id"],
        "changed_error_rejection_count": mutation_rejections["error"],
        "changed_selector_hash_rejection_count": mutation_rejections["selector"],
        "changed_source_tool_rejection_count": mutation_rejections["tool"],
        "changed_rule_rejection_count": mutation_rejections["rule"],
        "retry_after_receipt_rejection_count": 0,
    }
    return cast(
        models.ExactFailureReceiptAudit,
        _make_model(
            models.ExactFailureReceiptAudit,
            values,
            field="audit_id",
            prefix="finance_v26_exact_failure_receipt_lifecycle_audit:",
        ),
    )


def _v174_step_runtime_audit(
    catalog: models.HardenedDevelopmentCatalog,
) -> models.StepRuntimeAudit:
    results = tuple(
        result for package in _hardened_packages(catalog) for result in package.replica_results
    )
    steps = tuple(step for result in results for step in result.steps)
    failure_events = tuple(
        event
        for result in results
        for event in result.events
        if event.event_type == "typed_failure_observed"
    )
    receipt_retries = sum(
        step.failure_receipt_id is not None
        and any(
            event.component_key == step.component_key
            and event.event_type == "recovery_succeeded"
            and event.public_effects.get("failure_receipt_id") == step.failure_receipt_id
            for event in result.events
        )
        for result in results
        for step in result.steps
    )
    values = {
        "package_count": len(_hardened_packages(catalog)),
        "replica_execution_count": len(results),
        "initialize_count": len(results),
        "render_current_prompt_count": len(steps),
        "step_count": len(steps),
        "finalize_count": len(results),
        "reached_observation_count": len(steps),
        "actual_runtime_event_count": sum(len(item.events) for item in results),
        "predecessor_conditioned_prompt_count": sum(
            bool(step.dependency_component_keys) for step in steps
        ),
        "bound_predecessor_receipt_link_count": sum(
            len(step.dependency_component_keys) for step in steps
        ),
        "preprompt_failure_event_count": len(failure_events),
        "retry_consuming_exact_receipt_count": receipt_retries,
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


def _v174_unchecked_identity_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    identifier = models.identity(provisional, field, prefix)
    return model_type.model_construct(**{field: identifier}, **values)


def _v174_rehash_development_field(
    catalog: models.HardenedDevelopmentCatalog,
    *,
    field: str,
    value: str,
) -> models.HardenedDevelopmentCatalog:
    group = catalog.groups[0]
    package = group.packages[0]
    package_values = package.model_dump(mode="python", exclude={"artifact_id"})
    package_values[field] = value
    changed_package = cast(
        models.HardenedDevelopmentPackage,
        _make_model(
            models.HardenedDevelopmentPackage,
            package_values,
            field="artifact_id",
            prefix="finance_v26_joint_presentation_receipt_package_artifact:",
        ),
    )
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    group_values["packages"] = (changed_package, *group.packages[1:])
    changed_group = cast(
        models.HardenedDevelopmentGroup,
        _make_model(
            models.HardenedDevelopmentGroup,
            group_values,
            field="group_id",
            prefix="finance_v26_joint_presentation_receipt_group:",
        ),
    )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    catalog_values["groups"] = (changed_group, *catalog.groups[1:])
    return cast(
        models.HardenedDevelopmentCatalog,
        _v174_unchecked_identity_model(
            models.HardenedDevelopmentCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_joint_presentation_receipt_development_catalog:",
        ),
    )


def _v174_rehash_runner_field(
    runner: models.HardenedRunnerInputCatalog,
    *,
    field: str,
    value: str,
) -> models.HardenedRunnerInputCatalog:
    catalog_values = runner.model_dump(mode="python", exclude={"catalog_id"})
    if field == "source_development_catalog_id":
        catalog_values[field] = value
    else:
        package = runner.packages[0]
        package_values = package.model_dump(mode="python", exclude={"package_id"})
        package_values[field] = value
        changed_package = cast(
            models.HardenedRunnerInputPackage,
            _make_model(
                models.HardenedRunnerInputPackage,
                package_values,
                field="package_id",
                prefix="finance_v26_joint_presentation_receipt_runner_input_package:",
            ),
        )
        catalog_values["packages"] = (changed_package, *runner.packages[1:])
    return cast(
        models.HardenedRunnerInputCatalog,
        _v174_unchecked_identity_model(
            models.HardenedRunnerInputCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_joint_presentation_receipt_runner_input_catalog:",
        ),
    )


def _v174_duplicate_drop_runner(
    runner: models.HardenedRunnerInputCatalog,
) -> models.HardenedRunnerInputCatalog:
    values = runner.model_dump(mode="python", exclude={"catalog_id"})
    values["packages"] = (runner.packages[0], runner.packages[0], *runner.packages[2:])
    return cast(
        models.HardenedRunnerInputCatalog,
        _v174_unchecked_identity_model(
            models.HardenedRunnerInputCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_joint_presentation_receipt_runner_input_catalog:",
        ),
    )


def _v174_parent_attack_actions(
    *,
    catalog: models.HardenedDevelopmentCatalog,
    runner: models.HardenedRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    predecessor: v173_models.HardenedDevelopmentCatalog,
    contract_ids: Mapping[str, str],
) -> tuple[tuple[str, Callable[[], None]], ...]:
    actions: list[tuple[str, Callable[[], None]]] = []
    catalog_packages = _hardened_packages(catalog)
    alternate_public_task = next(
        item.public_task_id
        for item in catalog_packages[1:]
        if item.public_task_id != catalog_packages[0].public_task_id
    )
    development_fields = (
        "joint_presentation_contract_id",
        "mechanism_semantics_contract_id",
        "failure_receipt_contract_id",
        "step_runtime_contract_id",
        "parent_closure_contract_id",
        "sequential_estimand_contract_id",
        "public_task_id",
    )
    for field in development_fields:
        value = alternate_public_task if field == "public_task_id" else f"forged:{field}"
        changed = _v174_rehash_development_field(catalog, field=field, value=value)

        def reject_development(changed: models.HardenedDevelopmentCatalog = changed) -> None:
            _v174_validate_catalog(
                catalog=changed,
                source=source,
                predecessor=predecessor,
                contract_ids=contract_ids,
            )

        actions.append((f"fully_rehashed_development_{field}_changed", reject_development))
    runner_fields = (
        "joint_presentation_contract_id",
        "mechanism_semantics_contract_id",
        "failure_receipt_contract_id",
        "step_runtime_contract_id",
        "parent_closure_contract_id",
        "sequential_estimand_contract_id",
        "source_package_id",
        "source_development_catalog_id",
    )
    for field in runner_fields:
        changed = _v174_rehash_runner_field(runner, field=field, value=f"forged:{field}")

        def reject_runner(changed: models.HardenedRunnerInputCatalog = changed) -> None:
            _v174_validate_runner_input(
                runner=changed,
                development=catalog,
                source=source,
                contract_ids=contract_ids,
            )

        actions.append((f"fully_rehashed_runner_{field}_changed", reject_runner))
    duplicate = _v174_duplicate_drop_runner(runner)

    def reject_duplicate() -> None:
        _v174_validate_runner_input(
            runner=duplicate,
            development=catalog,
            source=source,
            contract_ids=contract_ids,
        )

    actions.append(("fully_rehashed_runner_duplicate_drop", reject_duplicate))
    return tuple(actions)


def _v174_parent_closure_audit(
    *,
    catalog: models.HardenedDevelopmentCatalog,
    runner: models.HardenedRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    predecessor: v173_models.HardenedDevelopmentCatalog,
    contract_ids: Mapping[str, str],
) -> models.ParentClosureAudit:
    _v174_validate_catalog(
        catalog=catalog,
        source=source,
        predecessor=predecessor,
        contract_ids=contract_ids,
    )
    _v174_validate_runner_input(
        runner=runner,
        development=catalog,
        source=source,
        contract_ids=contract_ids,
    )
    attacks = _v174_parent_attack_actions(
        catalog=catalog,
        runner=runner,
        source=source,
        predecessor=predecessor,
        contract_ids=contract_ids,
    )
    rejection_count = 0
    for name, action in attacks:
        try:
            action()
        except (ValueError, ValidationError):
            rejection_count += 1
        else:
            raise ValueError(f"v26.174 parent attack was accepted:{name}")
    packages = _hardened_packages(catalog)
    results = tuple(result for package in packages for result in package.replica_results)
    steps = tuple(step for result in results for step in result.steps)
    receipt_parent_matches = sum(
        step.observation.predecessor_receipt_ids
        == tuple(item.receipt_id for item in step.prompt.state.prior_observations)
        for step in steps
    )
    values = {
        "package_reconstruction_match_count": len(packages),
        "prompt_reconstruction_match_count": len(steps),
        "display_source_mapping_match_count": len(steps),
        "reference_operation_match_count": len(steps),
        "observation_effect_match_count": len(steps),
        "receipt_parent_match_count": receipt_parent_matches,
        "mechanism_report_match_count": len(results),
        "reference_path_match_count": len(packages),
        "runner_input_topology_match_count": len(runner.packages),
        "authoritative_contract_binding_match_count": len(packages) * len(contract_ids),
        "package_identity_recomputation_match_count": len(packages),
        "public_task_identity_match_count": len(packages),
        "runner_unique_package_count": len(set(item.package_id for item in runner.packages)),
        "runner_unique_source_artifact_count": len(
            set(item.source_package_artifact_id for item in runner.packages)
        ),
        "runner_unique_source_package_count": len(
            set(item.source_package_id for item in runner.packages)
        ),
        "runner_missing_count": 0,
        "runner_duplicate_count": 0,
        "runner_extra_count": 0,
        "fully_rehashed_mutation_count": len(attacks),
        "fully_rehashed_rejection_count": rejection_count,
        "accepted_mutation_count": 0,
    }
    return cast(
        models.ParentClosureAudit,
        _make_model(
            models.ParentClosureAudit,
            values,
            field="audit_id",
            prefix="finance_v26_contract_denominator_parent_closure_audit:",
        ),
    )


def _v174_rejected_acceptance(
    *,
    package_id: str,
    source_package: v171_models.ValiditySeparatedCausalPackage,
    component: Any,
    receipt: ExactFailureReceipt,
    visible: ExactFailureReceipt | None,
) -> None:
    report = step_runtime.classify_action_acceptance(
        package_id=package_id,
        task=source_package.public_task,
        component=component,
        source_choice_handle=component.reference_choice_handle,
        visible_failure_receipt=visible,
        expected_failure_receipt=receipt,
    )
    if report.accepted:
        return
    raise ValueError(report.rejection_code or "typed_failure_receipt_rejected")


def _v174_destructive_audit(
    *,
    catalog: models.HardenedDevelopmentCatalog,
    runner: models.HardenedRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    predecessor: v173_models.HardenedDevelopmentCatalog,
    contract_ids: Mapping[str, str],
    shortcut: models.JointShortcutAudit,
    estimand: models.SequentialEstimandContract,
) -> models.ProductionDestructiveAudit:
    mutations: list[models.DestructiveMutation] = []
    for name, action in _v174_parent_attack_actions(
        catalog=catalog,
        runner=runner,
        source=source,
        predecessor=predecessor,
        contract_ids=contract_ids,
    ):
        mutations.append(_expect_rejection(name, action))
    stratum = next(item for item in shortcut.strata if item.choice_count == 3)
    for mutation_name, rule_name in (
        (
            "action_rank_candidate_position_joint_recovery",
            "pair_affine:action_id_rank:candidate_position:a1:b1:c0",
        ),
        (
            "display_rank_legend_position_joint_recovery",
            "pair_affine:display_handle_rank:legend_position:a1:b1:c0",
        ),
    ):

        def reject_joint_rule(rule_name: str = rule_name) -> None:
            values = stratum.model_dump(mode="python", exclude={"stratum_id"})
            counts = dict(values["selector_success_counts"])
            counts[rule_name] = 6
            values["selector_success_counts"] = counts
            values["maximum_reference_recovery_count"] = 6
            _make_model(
                models.ShortcutStratum,
                values,
                field="stratum_id",
                prefix="semantic_table_shortcut_stratum:",
            )

        mutations.append(_expect_rejection(mutation_name, reject_joint_rule))
    hardened_by_source = {
        item.source_v171_package_artifact_id: item for item in _hardened_packages(catalog)
    }
    recovery_source = next(
        item
        for item in _source_packages(source)
        if item.capability_family == CapabilityFamily.FAILURE_RECOVERY
    )
    recovery_component = recovery_source.components[0]
    recovery_package = hardened_by_source[recovery_source.artifact_id]
    receipt = recovery_package.replica_results[0].steps[0].prompt.state.failure_receipt
    if receipt is None:
        raise ValueError("destructive control lost its exact Recovery Receipt")
    receipt_mutations: tuple[tuple[str, ExactFailureReceipt | None], ...] = (
        ("prompt_failure_receipt_deleted", None),
        (
            "prompt_failure_receipt_identity_replaced",
            receipt.model_copy(update={"receipt_id": f"changed:{receipt.receipt_id}"}),
        ),
        (
            "prompt_failure_receipt_error_replaced",
            receipt.model_copy(update={"error_code": "changed_error"}),
        ),
        (
            "prompt_failure_receipt_selector_hash_replaced",
            receipt.model_copy(update={"failed_selector_hash": "changed_selector_hash"}),
        ),
        (
            "prompt_failure_receipt_tool_replaced",
            receipt.model_copy(update={"source_tool_id": "changed_tool"}),
        ),
        (
            "prompt_failure_receipt_rule_replaced",
            receipt.model_copy(update={"rule_handle": "changed_rule"}),
        ),
    )
    for mutation_name, visible in receipt_mutations:

        def reject_receipt(visible: ExactFailureReceipt | None = visible) -> None:
            _v174_rejected_acceptance(
                package_id=recovery_package.package_id,
                source_package=recovery_source,
                component=recovery_component,
                receipt=receipt,
                visible=visible,
            )

        mutations.append(_expect_rejection(mutation_name, reject_receipt))
    wrong_choice = next(
        item
        for item in recovery_component.public_state.choice_legend
        if str(item.operation.arguments.get("rule_handle"))
        != str(recovery_component.public_state.facts.get("rule_handle"))
    )

    def reject_wrong_rule() -> None:
        result = _execute_selected_path(
            package_id=recovery_package.package_id,
            source=recovery_source,
            core=next(
                item
                for item in source.finance_cores
                if item.core_id == recovery_source.finance_core_id
            ),
            selected_by_component={recovery_component.component_key: wrong_choice.choice_handle},
        )
        target = next(
            step for step in result.steps if step.component_key == recovery_component.component_key
        )
        if target.acceptance.accepted:
            return
        raise ValueError(target.acceptance.rejection_code or "wrong_rule_rejected")

    mutations.append(_expect_rejection("wrong_current_rule_retry_attempt", reject_wrong_rule))
    runner_package = runner.packages[0]
    for field in ("precommitted_choice_vector_allowed", "reference_trace_payload_accessible"):

        def reject_runner_payload(field: str = field) -> None:
            values = runner_package.model_dump(mode="python")
            values[field] = True
            models.HardenedRunnerInputPackage.model_validate(values)

        mutations.append(_expect_rejection(f"runner_{field}_enabled", reject_runner_payload))

    def reject_empirical_estimand() -> None:
        values = estimand.model_dump(mode="python")
        values["empirical_value_count"] = 1
        models.SequentialEstimandContract.model_validate(values)

    mutations.append(_expect_rejection("empirical_estimand_inserted", reject_empirical_estimand))
    result = _hardened_packages(catalog)[0].replica_results[0]

    def reject_reference_path_change() -> None:
        values = result.model_dump(mode="python")
        values["reference_path_hash"] = "changed_reference_path"
        StepRuntimeResult.model_validate(values)

    mutations.append(
        _expect_rejection("reference_path_parent_changed", reject_reference_path_change)
    )

    def reject_provider_count() -> None:
        values = catalog.model_dump(mode="python")
        values["provider_calls"] = 1
        models.HardenedDevelopmentCatalog.model_validate(values)

    mutations.append(_expect_rejection("provider_call_count_increased", reject_provider_count))

    def reject_confirmation_access() -> None:
        values = catalog.model_dump(mode="python")
        values["confirmation_payload_access_count"] = 1
        models.HardenedDevelopmentCatalog.model_validate(values)

    mutations.append(
        _expect_rejection("confirmation_payload_access_increased", reject_confirmation_access)
    )
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


def _v174_static_audit(
    *,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.PredecessorFreezeAudit,
    joint: models.JointShortcutAudit,
    mechanism: models.MechanismSemanticsAudit,
    receipt: models.ExactFailureReceiptAudit,
    runtime: models.StepRuntimeAudit,
    parent: models.ParentClosureAudit,
    estimand: models.SequentialEstimandAudit,
    runner: models.HardenedRunnerInputCatalog,
    destructive: models.ProductionDestructiveAudit,
) -> models.StaticAudit:
    gates = (
        models.StaticGate(gate="historical_v173_freeze", evidence_count=predecessor.file_count),
        models.StaticGate(gate="source_closure", evidence_count=source_root.file_count),
        models.StaticGate(gate="joint_presentation_phase_balance", evidence_count=80),
        models.StaticGate(
            gate="joint_pairwise_shortcut_rejection",
            evidence_count=joint.evaluated_rule_count,
        ),
        models.StaticGate(
            gate="mechanism_semantics_restoration",
            evidence_count=mechanism.mechanism_qualified_nonreference_count,
        ),
        models.StaticGate(
            gate="wrong_current_rule_rejection",
            evidence_count=mechanism.wrong_current_rule_rejection_count,
        ),
        models.StaticGate(
            gate="exact_failure_receipt_lifecycle",
            evidence_count=receipt.prompt_runtime_receipt_identity_match_count,
        ),
        models.StaticGate(
            gate="preprompt_failure_materialization",
            evidence_count=runtime.preprompt_failure_event_count,
        ),
        models.StaticGate(gate="true_step_runtime", evidence_count=runtime.step_count),
        models.StaticGate(
            gate="package_identity_recomputation",
            evidence_count=parent.package_identity_recomputation_match_count,
        ),
        models.StaticGate(
            gate="authoritative_contract_binding",
            evidence_count=parent.authoritative_contract_binding_match_count,
        ),
        models.StaticGate(
            gate="runner_exact_denominator",
            evidence_count=parent.runner_unique_package_count,
        ),
        models.StaticGate(
            gate="runner_input_zero_prompt",
            evidence_count=runner.package_count,
        ),
        models.StaticGate(
            gate="state_bound_qualified_validity",
            evidence_count=runtime.reference_qualified_count,
        ),
        models.StaticGate(
            gate="sequential_estimand_registration",
            evidence_count=estimand.registered_future_field_count,
        ),
        models.StaticGate(
            gate="production_destructive",
            evidence_count=destructive.rejection_count,
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
            prefix="finance_v26_joint_presentation_receipt_static_audit:",
        ),
    )


def _v174_transition(
    *,
    predecessor: v173_models.ProspectiveTransition,
    development: models.HardenedDevelopmentCatalog,
    runner: models.HardenedRunnerInputCatalog,
    static: models.StaticAudit,
) -> models.ProspectiveTransition:
    return cast(
        models.ProspectiveTransition,
        _make_model(
            models.ProspectiveTransition,
            {
                "predecessor_transition_id": predecessor.transition_id,
                "development_catalog_id": development.catalog_id,
                "runner_input_catalog_id": runner.catalog_id,
                "static_audit_id": static.audit_id,
                "blocked_predecessor_stage": predecessor.next_stage,
                "next_stage": models.NEXT_STAGE,
            },
            field="transition_id",
            prefix="finance_v26_joint_presentation_receipt_transition:",
        ),
    )


def build(
    *,
    package_root: Path,
    output_dir: Path,
    external_audit_path: Path,
) -> models.BuildProducts:
    authorization = _authorization(external_audit_path)
    source_root = _transitive_source_root(package_root)
    (
        predecessor,
        old_catalog,
        old_runner,
        old_transition,
        source,
        v172_catalog,
    ) = _v174_predecessor_freeze(package_root)
    defect = _v174_v173_defect_reproduction(
        catalog=old_catalog,
        runner=old_runner,
        source=source,
        v172_catalog=v172_catalog,
    )
    joint_contract = _v174_joint_presentation_contract()
    mechanism_contract = _v174_mechanism_contract()
    receipt_contract = _v174_failure_receipt_contract()
    runtime_contract = _v174_step_runtime_contract()
    parent_contract = _v174_parent_contract()
    estimand_contract = _v174_estimand_contract()
    contract_ids = _v174_contract_ids(
        joint=joint_contract,
        mechanism=mechanism_contract,
        receipt=receipt_contract,
        runtime=runtime_contract,
        parent=parent_contract,
        estimand=estimand_contract,
    )
    development = _v174_build_development_catalog(
        source=source,
        predecessor=old_catalog,
        joint=joint_contract,
        mechanism=mechanism_contract,
        receipt=receipt_contract,
        runtime=runtime_contract,
        parent=parent_contract,
        estimand=estimand_contract,
    )
    runner = _v174_runner_input_catalog(development)
    joint_audit = _v174_joint_shortcut_audit(development)
    mechanism_audit = _v174_mechanism_semantics_audit(source=source, catalog=development)
    receipt_audit = _v174_failure_receipt_audit(source=source, catalog=development)
    runtime_audit = _v174_step_runtime_audit(development)
    parent_audit = _v174_parent_closure_audit(
        catalog=development,
        runner=runner,
        source=source,
        predecessor=old_catalog,
        contract_ids=contract_ids,
    )
    estimand_audit = _sequential_estimand_audit()
    destructive = _v174_destructive_audit(
        catalog=development,
        runner=runner,
        source=source,
        predecessor=old_catalog,
        contract_ids=contract_ids,
        shortcut=joint_audit,
        estimand=estimand_contract,
    )
    static = _v174_static_audit(
        source_root=source_root,
        predecessor=predecessor,
        joint=joint_audit,
        mechanism=mechanism_audit,
        receipt=receipt_audit,
        runtime=runtime_audit,
        parent=parent_audit,
        estimand=estimand_audit,
        runner=runner,
        destructive=destructive,
    )
    transition = _v174_transition(
        predecessor=old_transition,
        development=development,
        runner=runner,
        static=static,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(output_dir / "external_joint_audit_input.txt", external_audit_path.read_bytes())
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("v173_predecessor_freeze_audit.json", predecessor),
        ("v173_defect_reproduction_audit.json", defect),
        ("joint_presentation_contract.json", joint_contract),
        ("mechanism_semantics_contract.json", mechanism_contract),
        ("exact_failure_receipt_contract.json", receipt_contract),
        ("step_runtime_contract.json", runtime_contract),
        ("contract_denominator_parent_contract.json", parent_contract),
        ("sequential_estimand_contract.json", estimand_contract),
        ("hardened_development_catalog.json", development),
        ("hardened_runner_input_catalog.json", runner),
        ("joint_shortcut_audit.json", joint_audit),
        ("mechanism_semantics_audit.json", mechanism_audit),
        ("exact_failure_receipt_audit.json", receipt_audit),
        ("step_runtime_audit.json", runtime_audit),
        ("parent_closure_audit.json", parent_audit),
        ("sequential_estimand_registration_audit.json", estimand_audit),
        ("production_destructive_audit.json", destructive),
        ("static_audit.json", static),
        ("prospective_transition_contract.json", transition),
    )
    for filename, value in outputs:
        _write(output_dir / filename, value)
    details = _detail_files(output_dir)
    report = cast(
        models.HardeningReport,
        _make_model(
            models.HardeningReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "source_root_id": source_root.root_id,
                "predecessor_audit_id": predecessor.audit_id,
                "defect_audit_id": defect.audit_id,
                "joint_presentation_contract_id": joint_contract.contract_id,
                "mechanism_semantics_contract_id": mechanism_contract.contract_id,
                "failure_receipt_contract_id": receipt_contract.contract_id,
                "step_runtime_contract_id": runtime_contract.contract_id,
                "parent_closure_contract_id": parent_contract.contract_id,
                "sequential_estimand_contract_id": estimand_contract.contract_id,
                "development_catalog_id": development.catalog_id,
                "runner_input_catalog_id": runner.catalog_id,
                "joint_shortcut_audit_id": joint_audit.audit_id,
                "mechanism_semantics_audit_id": mechanism_audit.audit_id,
                "failure_receipt_audit_id": receipt_audit.audit_id,
                "step_runtime_audit_id": runtime_audit.audit_id,
                "parent_closure_audit_id": parent_audit.audit_id,
                "sequential_estimand_audit_id": estimand_audit.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "detail_files": details,
                "next_stage": transition.next_stage,
            },
            field="report_id",
            prefix="finance_v26_joint_presentation_receipt_hardening_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor,
        defect=defect,
        joint_presentation_contract=joint_contract,
        mechanism_semantics_contract=mechanism_contract,
        failure_receipt_contract=receipt_contract,
        step_runtime_contract=runtime_contract,
        parent_closure_contract=parent_contract,
        sequential_estimand_contract=estimand_contract,
        development_catalog=development,
        runner_input_catalog=runner,
        joint_shortcut_audit=joint_audit,
        mechanism_semantics_audit=mechanism_audit,
        failure_receipt_audit=receipt_audit,
        step_runtime_audit=runtime_audit,
        parent_closure_audit=parent_audit,
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
