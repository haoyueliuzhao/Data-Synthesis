from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel

from trusted_synthesis.core.task.validity_separated_capability_depth import (
    canonical_bytes,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization as v168,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as v168_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_semantic_execution_hardening as v170,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_public_semantic_execution_models as v170_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_static_audit as static_audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_runtime as causal_runtime,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_171_validity_causal_reaudit_v1_20260829"
OUTPUT_DIR: Final = "artifacts/vtdo_experiment/finance_v26_171_validity_causal_reaudit_v1_20260829"
EXPECTED_REVIEW_SHA256: Final = "0a9e048bf1d83540185af60c64bb138a503a880689e8aeecf32efb5bec40f5b8"
EXPECTED_REVIEW_BYTE_COUNT: Final = 26_048
AUTHORIZED_STAGE: Final = (
    "capability_observation_validity_separation_presentation_deleak_"
    "and_causal_component_reaudit_only"
)
V170_DIR: Final = v170.OUTPUT_DIR
V168_DIR: Final = v168.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/validity_separated_capability_depth.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_validity_causal_reaudit_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_validity_causal_runtime.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_validity_causal_reaudit_static_audit.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_validity_causal_reaudit.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.171 cannot resolve the trusted_data_synthesis package root")


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
        raise ValueError(f"v26.171 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.171 immutable output already exists:{path}")
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
        raise ValueError("v26.171 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.171 external audit byte count does not match Authorization")
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
            prefix="finance_v26_validity_causal_external_audit_authorization:",
        ),
    )


def _module_name(relative_path: str) -> str:
    path = relative_path.removeprefix("src/").removesuffix(".py")
    return path.replace("/", ".")


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
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
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
        pending.extend(
            item for item in _imported_modules(package_root, path) if item not in visited
        )
    if unresolved:
        raise ValueError(f"v26.171 unresolved trusted_synthesis imports:{sorted(unresolved)}")
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=relative,
            source_kind=(
                "implementation" if relative in ENTRY_SOURCE_PATHS else "transitive_source"
            ),
        )
        for relative, path in sorted(files.items())
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
            prefix="finance_v26_validity_causal_transitive_source_root:",
        ),
    )


@dataclass(frozen=True)
class _PredecessorProducts:
    audit: models.PredecessorIntegrityAudit
    report: v170_models.PublicSemanticHardeningReport
    catalog: v170_models.HardenedSemanticDevelopmentCatalog
    transition: v170_models.PublicSemanticTransition
    v168_catalog: v168_models.ExecutableDepthCatalog


def _predecessor_integrity(package_root: Path) -> _PredecessorProducts:
    v170_dir = package_root / V170_DIR
    files = tuple(sorted(path for path in v170_dir.iterdir() if path.is_file()))
    if len(files) != 18:
        raise ValueError("v26.170 formal Root file count changed")
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=f"{V170_DIR}/{path.name}",
            source_kind="v26_170_frozen_output",
        )
        for path in files
    )
    report = v170_models.PublicSemanticHardeningReport.model_validate(
        _load(v170_dir / "report.json")
    )
    catalog = v170_models.HardenedSemanticDevelopmentCatalog.model_validate(
        _load(v170_dir / "hardened_semantic_development_catalog.json")
    )
    transition = v170_models.PublicSemanticTransition.model_validate(
        _load(v170_dir / "prospective_transition_contract.json")
    )
    if (
        report.development_catalog_id != catalog.catalog_id
        or report.transition_id != transition.transition_id
    ):
        raise ValueError("v26.170 report parents changed")
    v168_catalog = v168_models.ExecutableDepthCatalog.model_validate(
        _load(package_root / V168_DIR / "development_executable_depth_catalog.json")
    )
    values = {
        "predecessor_report_id": report.report_id,
        "predecessor_catalog_id": catalog.catalog_id,
        "predecessor_transition_id": transition.transition_id,
        "bindings": bindings,
    }
    audit = cast(
        models.PredecessorIntegrityAudit,
        _make_model(
            models.PredecessorIntegrityAudit,
            values,
            field="audit_id",
            prefix="finance_v26_v170_predecessor_integrity:",
        ),
    )
    return _PredecessorProducts(audit, report, catalog, transition, v168_catalog)


def _validity_contract() -> models.ValiditySeparationContract:
    values = {
        "base_inputs": (
            "local_program_contract_valid",
            "operation_lineage_complete",
            "answer_projection_complete",
            "answer_schema_valid",
            "public_answer_semantically_valid",
            "reference_identity_valid",
            "citation_complete",
            "terminal_verification_complete",
            "postcompletion_control_passed",
        )
    }
    return cast(
        models.ValiditySeparationContract,
        _make_model(
            models.ValiditySeparationContract,
            values,
            field="contract_id",
            prefix="validity_separation_contract:",
        ),
    )


def _component_contract() -> models.CausalComponentContract:
    values = {
        "allowed_decisions_by_family": causal_runtime.component_contract_projection(),
    }
    return cast(
        models.CausalComponentContract,
        _make_model(
            models.CausalComponentContract,
            values,
            field="contract_id",
            prefix="causal_component_contract:",
        ),
    )


def _presentation_policy() -> models.DeleakedPresentationPolicy:
    values = {
        "preoutcome_fixed_salt_sha256": hashlib.sha256(
            causal_runtime.PRESENTATION_SALT.encode()
        ).hexdigest()
    }
    return cast(
        models.DeleakedPresentationPolicy,
        _make_model(
            models.DeleakedPresentationPolicy,
            values,
            field="policy_id",
            prefix="deleaked_public_candidate_presentation_policy:",
        ),
    )


def _parent_binding_contract() -> models.SemanticParentBindingContract:
    values = {
        "recomputed_fields": tuple(
            sorted(
                {
                    "reference_choice_handle",
                    "source_program_verification_hash",
                    "source_public_task_hash",
                    "source_public_evidence_semantic_hash",
                    "projected_public_task_id",
                    "source_finance_core_id",
                }
            )
        )
    }
    return cast(
        models.SemanticParentBindingContract,
        _make_model(
            models.SemanticParentBindingContract,
            values,
            field="contract_id",
            prefix="semantic_parent_binding_contract:",
        ),
    )


def _v168_package(
    catalog: v168_models.ExecutableDepthCatalog,
    *,
    finance_core_id: str,
    depth: Any,
) -> v168_models.ExecutableDepthPackage:
    matches = tuple(
        package
        for group in catalog.groups
        if group.finance_core_id == finance_core_id
        for package in group.packages
        if package.depth == depth
    )
    if len(matches) != 1:
        raise ValueError("v26.171 could not identify one exact v26.168 source Package")
    return matches[0]


def _source_parent_binding(
    *,
    source: v170_models.HardenedSemanticPackage,
    source_v168: v168_models.ExecutableDepthPackage,
    core: v168_models.LowNuisanceFinanceCore,
    public_task: Any,
    contract: models.SemanticParentBindingContract,
) -> models.SourceSemanticParentBinding:
    _, verification, _ = causal_runtime.source_execution_receipt(core)
    if canonical_bytes(verification) != canonical_bytes(source_v168.variant_program_verification):
        raise ValueError("fresh source Program Verification differs from v26.168")
    source_task = core.operational_record.task_package.task
    values = {
        "source_finance_core_id": core.core_id,
        "source_v170_package_artifact_id": source.artifact_id,
        "source_v168_package_id": source_v168.package_id,
        "source_program_verification": verification,
        "source_program_verification_hash": canonical_hash(
            verification.model_dump(mode="json"),
            prefix="source_program_verification:",
        ),
        "source_public_task_hash": canonical_hash(
            source_task.public.model_dump(mode="json"),
            prefix="source_public_finance_task:",
        ),
        "source_public_evidence_semantic_hash": canonical_hash(
            tuple(item.semantic_fields for item in source.public_task.records),
            prefix="source_public_finance_evidence_semantics:",
        ),
        "projected_public_task_id": public_task.task_id,
        "parent_binding_contract_id": contract.contract_id,
    }
    return cast(
        models.SourceSemanticParentBinding,
        _make_model(
            models.SourceSemanticParentBinding,
            values,
            field="binding_id",
            prefix="causal_semantic_source_parent_binding:",
        ),
    )


def _package_id(
    *,
    source: v170_models.HardenedSemanticPackage,
    public_task_id: str,
    component_keys: tuple[str, ...],
    validity: models.ValiditySeparationContract,
    component: models.CausalComponentContract,
    presentation: models.DeleakedPresentationPolicy,
    parent: models.SemanticParentBindingContract,
) -> str:
    return canonical_hash(
        {
            "source_v170_package_artifact_id": source.artifact_id,
            "capability_family": source.capability_family.value,
            "depth": source.depth.value,
            "finance_core_id": source.finance_core_id,
            "fixed_generation_condition_id": source.fixed_generation_condition_id,
            "validity_contract_id": validity.contract_id,
            "component_contract_id": component.contract_id,
            "presentation_policy_id": presentation.policy_id,
            "parent_binding_contract_id": parent.contract_id,
            "public_task_id": public_task_id,
            "component_keys": list(component_keys),
            "schema_version": models.V26_VALIDITY_CAUSAL_REAUDIT_VERSION,
        },
        prefix="finance_v26_validity_causal_package:",
    )


def _build_package(
    *,
    source: v170_models.HardenedSemanticPackage,
    source_group_id: str,
    source_v168: v168_models.ExecutableDepthPackage,
    core: v168_models.LowNuisanceFinanceCore,
    validity: models.ValiditySeparationContract,
    component_contract: models.CausalComponentContract,
    presentation: models.DeleakedPresentationPolicy,
    parent_contract: models.SemanticParentBindingContract,
) -> models.ValiditySeparatedCausalPackage:
    public_task = causal_runtime.build_public_task(core, source.public_task)
    specs = causal_runtime.component_specs(
        core=core,
        family=source.capability_family,
        depth=source.depth,
        task=source.public_task,
    )
    component_keys = tuple(item.component_key for item in specs)
    package_id = _package_id(
        source=source,
        public_task_id=public_task.task_id,
        component_keys=component_keys,
        validity=validity,
        component=component_contract,
        presentation=presentation,
        parent=parent_contract,
    )
    components = tuple(
        causal_runtime.build_component(
            package_id=package_id,
            family=source.capability_family,
            depth=source.depth,
            task=public_task,
            spec=spec,
        )
        for spec in specs
    )
    presentations: list[models.ReplicaPresentation] = []
    for target in components:
        for replica in range(6):
            prompt = causal_runtime.prompt_for_component(
                package_id=package_id,
                task=public_task,
                component=target,
                replica_index=replica,
            )
            values = {
                "package_id": package_id,
                "component_id": target.component_id,
                "replica_index": replica,
                "prompt": prompt,
            }
            presentations.append(
                cast(
                    models.ReplicaPresentation,
                    _make_model(
                        models.ReplicaPresentation,
                        values,
                        field="presentation_id",
                        prefix="causal_deleaked_replica_presentation:",
                    ),
                )
            )
    baseline_prompts = tuple(
        next(
            item.prompt
            for item in presentations
            if item.component_id == target.component_id and item.replica_index == 0
        )
        for target in components
    )
    prompt_values = {
        "package_id": package_id,
        "public_task_id": public_task.task_id,
        "component_contract_id": component_contract.contract_id,
        "presentation_policy_id": presentation.policy_id,
        "baseline_prompts": baseline_prompts,
        "prompt_count": len(baseline_prompts),
        "dynamic_predecessor_receipts_required": any(
            item.dependency_component_keys for item in components
        ),
    }
    prompt_binding = cast(
        models.CausalPromptBinding,
        _make_model(
            models.CausalPromptBinding,
            prompt_values,
            field="binding_id",
            prefix="causal_public_prompt_binding:",
        ),
    )
    source_parent = _source_parent_binding(
        source=source,
        source_v168=source_v168,
        core=core,
        public_task=public_task,
        contract=parent_contract,
    )
    target_values = {
        "package_id": package_id,
        "capability_family": source.capability_family,
        "depth": source.depth,
        "target_component_count": len(components),
        "family_validator_passed_count": len(components),
    }
    target_load = cast(
        models.CausalTargetLoad,
        _make_model(
            models.CausalTargetLoad,
            target_values,
            field="load_id",
            prefix="causal_family_validated_target_load:",
        ),
    )
    baseline = causal_runtime.execute_runtime(
        causal_runtime.RuntimeInput(
            package_id=package_id,
            capability_family=source.capability_family,
            public_task=public_task,
            components=components,
            finance_core=core,
        )
    )
    if not baseline.qualified_validity.qualified_valid:
        raise ValueError("v26.171 baseline did not close Base and Mechanism")
    values = {
        "package_id": package_id,
        "source_v170_package_artifact_id": source.artifact_id,
        "source_v170_group_id": source_group_id,
        "capability_family": source.capability_family,
        "depth": source.depth,
        "finance_core_id": source.finance_core_id,
        "fixed_generation_condition_id": source.fixed_generation_condition_id,
        "validity_contract_id": validity.contract_id,
        "component_contract_id": component_contract.contract_id,
        "presentation_policy_id": presentation.policy_id,
        "parent_binding_contract_id": parent_contract.contract_id,
        "public_task": public_task,
        "source_parent_binding": source_parent,
        "components": components,
        "prompt_binding": prompt_binding,
        "replica_presentations": tuple(presentations),
        "target_load": target_load,
        "baseline_execution": baseline,
    }
    return cast(
        models.ValiditySeparatedCausalPackage,
        _make_model(
            models.ValiditySeparatedCausalPackage,
            values,
            field="artifact_id",
            prefix="finance_v26_validity_causal_package_artifact:",
        ),
    )


def _development_catalog(
    predecessor: _PredecessorProducts,
    validity: models.ValiditySeparationContract,
    component: models.CausalComponentContract,
    presentation: models.DeleakedPresentationPolicy,
    parent: models.SemanticParentBindingContract,
) -> models.ValiditySeparatedDevelopmentCatalog:
    cores = {item.core_id: item for item in predecessor.catalog.finance_cores}
    groups: list[models.ValiditySeparatedCausalGroup] = []
    for source_group in predecessor.catalog.groups:
        core = cores[source_group.finance_core_id]
        packages = tuple(
            _build_package(
                source=source,
                source_group_id=source_group.group_id,
                source_v168=_v168_package(
                    predecessor.v168_catalog,
                    finance_core_id=source.finance_core_id,
                    depth=source.depth,
                ),
                core=core,
                validity=validity,
                component_contract=component,
                presentation=presentation,
                parent_contract=parent,
            )
            for source in source_group.packages
        )
        group_values = {
            "source_v170_group_id": source_group.group_id,
            "capability_family": source_group.capability_family,
            "finance_core_id": source_group.finance_core_id,
            "packages": packages,
        }
        groups.append(
            cast(
                models.ValiditySeparatedCausalGroup,
                _make_model(
                    models.ValiditySeparatedCausalGroup,
                    group_values,
                    field="group_id",
                    prefix="finance_v26_validity_causal_group:",
                ),
            )
        )
    values = {
        "source_v170_catalog_id": predecessor.catalog.catalog_id,
        "source_v170_report_id": predecessor.report.report_id,
        "sealed_confirmation_receipt_id": predecessor.catalog.sealed_confirmation_receipt_id,
        "validity_contract_id": validity.contract_id,
        "component_contract_id": component.contract_id,
        "presentation_policy_id": presentation.policy_id,
        "parent_binding_contract_id": parent.contract_id,
        "finance_cores": tuple(sorted(cores.values(), key=lambda item: item.core_id)),
        "groups": tuple(sorted(groups, key=lambda item: item.source_v170_group_id)),
    }
    return cast(
        models.ValiditySeparatedDevelopmentCatalog,
        _make_model(
            models.ValiditySeparatedDevelopmentCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_validity_separated_development_catalog:",
        ),
    )


def _transition(
    *,
    predecessor: _PredecessorProducts,
    catalog: models.ValiditySeparatedDevelopmentCatalog,
    validity: models.ValiditySeparationContract,
    component: models.CausalComponentContract,
    presentation: models.DeleakedPresentationPolicy,
    parent: models.SemanticParentBindingContract,
    static: models.ValidityCausalStaticAudit,
) -> models.ValidityCausalTransition:
    values = {
        "predecessor_transition_id": predecessor.transition.transition_id,
        "development_catalog_id": catalog.catalog_id,
        "validity_contract_id": validity.contract_id,
        "component_contract_id": component.contract_id,
        "presentation_policy_id": presentation.policy_id,
        "parent_binding_contract_id": parent.contract_id,
        "static_audit_id": static.audit_id,
        "blocked_predecessor_stage": predecessor.transition.next_stage,
        "next_stage": (
            "capability_observation_validity_separated_causal_deleaked_"
            "development_runner_preflight_only"
        ),
    }
    return cast(
        models.ValidityCausalTransition,
        _make_model(
            models.ValidityCausalTransition,
            values,
            field="transition_id",
            prefix="finance_v26_validity_causal_transition:",
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
    defect = static_audit.build_v170_defect_reproduction(predecessor.catalog)
    validity = _validity_contract()
    component = _component_contract()
    presentation = _presentation_policy()
    parent_contract = _parent_binding_contract()
    development = _development_catalog(
        predecessor,
        validity,
        component,
        presentation,
        parent_contract,
    )
    static_audit.validate_catalog_reconstruction(
        catalog=development,
        source_catalog=predecessor.catalog,
        v168_catalog=predecessor.v168_catalog,
        validity=validity,
        component_contract=component,
        presentation_policy=presentation,
        parent_contract=parent_contract,
    )
    answer_projection = static_audit.build_answer_projection_audit(development)
    validity_separation = static_audit.build_validity_separation_audit(development)
    causal_component = static_audit.build_causal_component_audit(development)
    component_family = static_audit.build_component_family_audit(development)
    candidate_legality = static_audit.build_candidate_legality_audit(development)
    presentation_deleak = static_audit.build_presentation_deleak_audit(development)
    increments = static_audit.build_depth_increment_catalog(development)
    parent_binding = static_audit.build_parent_binding_audit(
        catalog=development,
        source_catalog=predecessor.catalog,
        v168_catalog=predecessor.v168_catalog,
        increments=increments,
    )
    computed_evidence = static_audit.build_computed_evidence_audit(development)
    destructive = static_audit.build_destructive_audit(
        catalog=development,
        source_catalog=predecessor.catalog,
        v168_catalog=predecessor.v168_catalog,
        increments=increments,
    )
    static = static_audit.build_static_audit(
        source_root=source_root,
        answer_projection=answer_projection,
        validity_separation=validity_separation,
        causal_component=causal_component,
        component_family=component_family,
        candidate_legality=candidate_legality,
        presentation_deleak=presentation_deleak,
        increments=increments,
        parent_binding=parent_binding,
        computed_evidence=computed_evidence,
        destructive=destructive,
    )
    transition = _transition(
        predecessor=predecessor,
        catalog=development,
        validity=validity,
        component=component,
        presentation=presentation,
        parent=parent_contract,
        static=static,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(output_dir / "external_joint_audit_input.txt", external_audit_path.read_bytes())
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("predecessor_integrity_audit.json", predecessor.audit),
        ("v170_defect_reproduction_audit.json", defect),
        ("validity_separation_contract.json", validity),
        ("causal_component_contract.json", component),
        ("deleaked_presentation_policy.json", presentation),
        ("semantic_parent_binding_contract.json", parent_contract),
        ("validity_separated_development_catalog.json", development),
        ("public_answer_projection_audit.json", answer_projection),
        ("validity_separation_audit.json", validity_separation),
        ("causal_component_audit.json", causal_component),
        ("component_family_audit.json", component_family),
        ("candidate_legality_audit.json", candidate_legality),
        ("presentation_deleak_audit.json", presentation_deleak),
        ("depth_increment_causal_catalog.json", increments),
        ("semantic_parent_binding_audit.json", parent_binding),
        ("computed_evidence_audit.json", computed_evidence),
        ("production_destructive_audit.json", destructive),
        ("validity_causal_static_audit.json", static),
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
        "defect_reproduction_audit_id": defect.audit_id,
        "validity_contract_id": validity.contract_id,
        "component_contract_id": component.contract_id,
        "presentation_policy_id": presentation.policy_id,
        "parent_binding_contract_id": parent_contract.contract_id,
        "development_catalog_id": development.catalog_id,
        "answer_projection_audit_id": answer_projection.audit_id,
        "validity_separation_audit_id": validity_separation.audit_id,
        "causal_component_audit_id": causal_component.audit_id,
        "component_family_audit_id": component_family.audit_id,
        "candidate_legality_audit_id": candidate_legality.audit_id,
        "presentation_deleak_audit_id": presentation_deleak.audit_id,
        "depth_increment_catalog_id": increments.catalog_id,
        "parent_binding_audit_id": parent_binding.audit_id,
        "computed_evidence_audit_id": computed_evidence.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "static_audit_id": static.audit_id,
        "transition_id": transition.transition_id,
        "detail_files": details,
        "next_stage": transition.next_stage,
    }
    report = cast(
        models.ValidityCausalReauditReport,
        _make_model(
            models.ValidityCausalReauditReport,
            report_values,
            field="report_id",
            prefix="finance_v26_validity_causal_reaudit_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor.audit,
        defect=defect,
        validity_contract=validity,
        component_contract=component,
        presentation_policy=presentation,
        parent_binding_contract=parent_contract,
        development_catalog=development,
        answer_projection=answer_projection,
        validity_separation=validity_separation,
        causal_component=causal_component,
        component_family=component_family,
        candidate_legality=candidate_legality,
        presentation_deleak=presentation_deleak,
        increments=increments,
        parent_binding=parent_binding,
        computed_evidence=computed_evidence,
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
