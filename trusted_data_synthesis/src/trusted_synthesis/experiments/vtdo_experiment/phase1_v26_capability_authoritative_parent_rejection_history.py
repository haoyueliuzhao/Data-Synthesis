from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from itertools import product
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task.capability_observation import (
    CapabilityFamily,
    ObservationDepth,
)
from trusted_synthesis.core.task.state_local_presentation_hardening import (
    StateLocalRankSchedule,
    StepRuntimeResult,
    classify_action_acceptance,
    make_identity_model,
    public_only_select_hardened_action,
    topological_components,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_joint_presentation_receipt_hardening as v174,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_joint_presentation_receipt_hardening_models as v174_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_semantic_table_trace_hardening as v173,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_semantic_table_trace_hardening_models as v173_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_state_local_presentation_parent_hardening as v175,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_state_local_presentation_parent_hardening_models as v175_models,
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

RUN_ID: Final = "finance_v26_176_authoritative_parent_rejection_history_v2_20260829"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_176_authoritative_parent_rejection_history_v2_20260829"
)
EXPECTED_REVIEW_SHA256: Final = "a27241c83208eb0312a58508539321688e2c7385aaf9e7be6a675fa2cbb2ac42"
EXPECTED_REVIEW_BYTE_COUNT: Final = 22_178
V175_DIR: Final = v175.OUTPUT_DIR
V174_DIR: Final = v174.OUTPUT_DIR
V173_DIR: Final = v173.OUTPUT_DIR
V171_DIR: Final = v171.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/authoritative_rejection_history_hardening.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_parent_rejection_history_runtime.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_parent_rejection_history_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_parent_rejection_history.py",
)
INHERITED_CONTRACT_FIELDS: Final = (
    "mechanism_semantics_contract_id",
    "failure_receipt_contract_id",
    "step_runtime_contract_id",
    "sequential_estimand_contract_id",
)
DEVELOPMENT_METADATA_FIELDS: Final = (
    "source_v175_package_artifact_id",
    "package_id",
    "source_v174_package_artifact_id",
    "source_v173_package_artifact_id",
    "source_v171_package_artifact_id",
    "source_package_id",
    "source_group_id",
    "finance_core_id",
    "capability_family",
    "depth",
    "public_task_id",
    "topological_component_keys",
    "reference_path_hash",
    "presentation_contract_id",
    "interaction_parent_receipt_contract_id",
    "schedule_catalog_id",
    "schedule_ids",
    "mechanism_semantics_contract_id",
    "failure_receipt_contract_id",
    "step_runtime_contract_id",
    "sequential_estimand_contract_id",
    "authoritative_parent_contract_id",
    "typed_rejection_history_contract_id",
)
RUNNER_METADATA_FIELDS: Final = (
    "source_development_package_artifact_id",
    *DEVELOPMENT_METADATA_FIELDS,
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.176 cannot resolve the trusted_data_synthesis package root")


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
        raise ValueError(f"v26.176 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.176 immutable output already exists:{path}")
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
    return models.make_identity_model(model_type, values, field=field, prefix=prefix)


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
        raise ValueError("v26.176 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.176 external audit byte count does not match Authorization")
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
            prefix="finance_v26_authoritative_parent_history_external_authorization:",
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
        raise ValueError(f"v26.176 source closure has unresolved imports:{sorted(unresolved)}")
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
            prefix="finance_v26_authoritative_parent_history_transitive_source_root:",
        ),
    )


def _v171_packages(
    catalog: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> tuple[v171_models.ValiditySeparatedCausalPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


def _v174_packages(
    catalog: v174_models.HardenedDevelopmentCatalog,
) -> tuple[v174_models.HardenedDevelopmentPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


def _v175_packages(
    catalog: v175_models.StateLocalDevelopmentCatalog,
) -> tuple[v175_models.StateLocalDevelopmentPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


def _development_packages(
    catalog: models.AuthoritativeDevelopmentCatalog,
) -> tuple[models.AuthoritativeDevelopmentPackage, ...]:
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


class PredecessorObjects:
    def __init__(
        self,
        *,
        report: v175_models.HardeningReport,
        catalog: v175_models.StateLocalDevelopmentCatalog,
        runner: v175_models.StateLocalRunnerInputCatalog,
        transition: v175_models.ProspectiveTransition,
        schedules: v175_models.StateLocalScheduleCatalog,
        exhaustive: v175_models.ExhaustiveTrajectoryInteractionAudit,
        v174_catalog: v174_models.HardenedDevelopmentCatalog,
        v174_mechanism: v174_models.MechanismSemanticsContract,
        v174_receipt: v174_models.ExactFailureReceiptContract,
        v174_runtime: v174_models.StepRuntimeContract,
        v174_estimand: v174_models.SequentialEstimandContract,
        v173_catalog: v173_models.HardenedDevelopmentCatalog,
        source: v171_models.ValiditySeparatedDevelopmentCatalog,
    ) -> None:
        self.report = report
        self.catalog = catalog
        self.runner = runner
        self.transition = transition
        self.schedules = schedules
        self.exhaustive = exhaustive
        self.v174_catalog = v174_catalog
        self.v174_mechanism = v174_mechanism
        self.v174_receipt = v174_receipt
        self.v174_runtime = v174_runtime
        self.v174_estimand = v174_estimand
        self.v173_catalog = v173_catalog
        self.source = source


def _predecessor_freeze(
    package_root: Path,
) -> tuple[models.PredecessorFreezeAudit, PredecessorObjects]:
    source_dir = package_root / V175_DIR
    paths = tuple(sorted(path for path in source_dir.iterdir() if path.is_file()))
    if len(paths) != 19:
        raise ValueError("v26.175 formal predecessor directory is not exactly 19 files")
    report = v175_models.HardeningReport.model_validate(_load(source_dir / "report.json"))
    catalog = v175_models.StateLocalDevelopmentCatalog.model_validate(
        _load(source_dir / "state_local_development_catalog.json")
    )
    runner = v175_models.StateLocalRunnerInputCatalog.model_validate(
        _load(source_dir / "state_local_runner_input_catalog.json")
    )
    transition = v175_models.ProspectiveTransition.model_validate(
        _load(source_dir / "prospective_transition_contract.json")
    )
    schedules = v175_models.StateLocalScheduleCatalog.model_validate(
        _load(source_dir / "state_local_schedule_catalog.json")
    )
    exhaustive = v175_models.ExhaustiveTrajectoryInteractionAudit.model_validate(
        _load(source_dir / "exhaustive_trajectory_interaction_audit.json")
    )
    with tempfile.TemporaryDirectory(prefix="finance-v26-176-v175-rebuild-") as temporary:
        rebuild_dir = Path(temporary)
        v175.build(
            package_root=package_root,
            output_dir=rebuild_dir,
            external_audit_path=source_dir / "external_joint_audit_input.txt",
        )
        rebuilt = tuple(sorted(path for path in rebuild_dir.iterdir() if path.is_file()))
        if len(rebuilt) != len(paths):
            raise ValueError("v26.175 independent rebuild file count differs")
        for source_path in paths:
            candidate = rebuild_dir / source_path.name
            if not candidate.is_file() or source_path.read_bytes() != candidate.read_bytes():
                raise ValueError(f"v26.175 independent rebuild differs:{source_path.name}")
    v174_dir = package_root / V174_DIR
    v174_catalog = v174_models.HardenedDevelopmentCatalog.model_validate(
        _load(v174_dir / "hardened_development_catalog.json")
    )
    v174_mechanism = v174_models.MechanismSemanticsContract.model_validate(
        _load(v174_dir / "mechanism_semantics_contract.json")
    )
    v174_receipt = v174_models.ExactFailureReceiptContract.model_validate(
        _load(v174_dir / "exact_failure_receipt_contract.json")
    )
    v174_runtime_contract = v174_models.StepRuntimeContract.model_validate(
        _load(v174_dir / "step_runtime_contract.json")
    )
    v174_estimand = v174_models.SequentialEstimandContract.model_validate(
        _load(v174_dir / "sequential_estimand_contract.json")
    )
    v173_catalog = v173_models.HardenedDevelopmentCatalog.model_validate(
        _load(package_root / V173_DIR / "hardened_development_catalog.json")
    )
    source = v171_models.ValiditySeparatedDevelopmentCatalog.model_validate(
        _load(package_root / V171_DIR / "validity_separated_development_catalog.json")
    )
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=f"{V175_DIR}/{path.name}",
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
                "predecessor_runner_input_catalog_id": runner.catalog_id,
                "predecessor_transition_id": transition.transition_id,
                "predecessor_files": bindings,
                "predecessor_file_count": 19,
                "independent_rebuild_match_count": 19,
                "predecessor_mutation_count": 0,
                "stale_runner_transition_blocked": True,
            },
            field="audit_id",
            prefix="finance_v26_v175_predecessor_freeze_audit:",
        ),
    )
    return audit, PredecessorObjects(
        report=report,
        catalog=catalog,
        runner=runner,
        transition=transition,
        schedules=schedules,
        exhaustive=exhaustive,
        v174_catalog=v174_catalog,
        v174_mechanism=v174_mechanism,
        v174_receipt=v174_receipt,
        v174_runtime=v174_runtime_contract,
        v174_estimand=v174_estimand,
        v173_catalog=v173_catalog,
        source=source,
    )


def _old_runner_for_changed_development(
    *,
    original: v175_models.StateLocalDevelopmentCatalog,
    changed: v175_models.StateLocalDevelopmentCatalog,
    runner: v175_models.StateLocalRunnerInputCatalog,
) -> v175_models.StateLocalRunnerInputCatalog:
    original_by_artifact = {item.artifact_id: item for item in _v175_packages(original)}
    changed_by_package_id = {item.package_id: item for item in _v175_packages(changed)}
    packages: list[v175_models.StateLocalRunnerInputPackage] = []
    for row in runner.packages:
        old_package = original_by_artifact[row.source_development_package_artifact_id]
        new_package = changed_by_package_id[old_package.package_id]
        values = row.model_dump(mode="python", exclude={"package_id"})
        values.update(
            {
                "source_development_package_artifact_id": new_package.artifact_id,
                "source_v174_package_artifact_id": (new_package.source_v174_package_artifact_id),
                "source_package_id": new_package.source_package_id,
                "public_task_id": new_package.public_task_id,
                "topological_component_keys": new_package.topological_component_keys,
                "presentation_contract_id": new_package.presentation_contract_id,
                "interaction_parent_receipt_contract_id": (
                    new_package.interaction_parent_receipt_contract_id
                ),
                "schedule_catalog_id": new_package.schedule_catalog_id,
                "schedule_ids": new_package.schedule_ids,
                "mechanism_semantics_contract_id": (new_package.mechanism_semantics_contract_id),
                "failure_receipt_contract_id": new_package.failure_receipt_contract_id,
                "step_runtime_contract_id": new_package.step_runtime_contract_id,
                "sequential_estimand_contract_id": (new_package.sequential_estimand_contract_id),
            }
        )
        packages.append(
            cast(
                v175_models.StateLocalRunnerInputPackage,
                v175._make_model(
                    v175_models.StateLocalRunnerInputPackage,
                    values,
                    field="package_id",
                    prefix="finance_v26_state_local_presentation_runner_input_package:",
                ),
            )
        )
    values = runner.model_dump(mode="python", exclude={"catalog_id"})
    changed_packages = _v175_packages(changed)
    values.update(
        {
            "source_development_catalog_id": changed.catalog_id,
            "expected_source_artifact_ids": tuple(item.artifact_id for item in changed_packages),
            "expected_source_package_ids": tuple(
                item.source_package_id for item in changed_packages
            ),
            "packages": tuple(packages),
        }
    )
    return cast(
        v175_models.StateLocalRunnerInputCatalog,
        v175._make_model(
            v175_models.StateLocalRunnerInputCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_state_local_presentation_runner_input_catalog:",
        ),
    )


def _old_replace_all_development_contract(
    catalog: v175_models.StateLocalDevelopmentCatalog,
    field_name: str,
) -> v175_models.StateLocalDevelopmentCatalog:
    changed_value = f"forged:{field_name}"
    groups: list[v175_models.StateLocalDevelopmentGroup] = []
    for group in catalog.groups:
        packages: list[v175_models.StateLocalDevelopmentPackage] = []
        for package in group.packages:
            values = package.model_dump(mode="python", exclude={"artifact_id"})
            values[field_name] = changed_value
            packages.append(
                cast(
                    v175_models.StateLocalDevelopmentPackage,
                    v175._make_model(
                        v175_models.StateLocalDevelopmentPackage,
                        values,
                        field="artifact_id",
                        prefix="finance_v26_state_local_presentation_package_artifact:",
                    ),
                )
            )
        values = group.model_dump(mode="python", exclude={"group_id"})
        values["packages"] = tuple(packages)
        groups.append(
            cast(
                v175_models.StateLocalDevelopmentGroup,
                v175._make_model(
                    v175_models.StateLocalDevelopmentGroup,
                    values,
                    field="group_id",
                    prefix="finance_v26_state_local_presentation_group:",
                ),
            )
        )
    values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    values[field_name] = changed_value
    values["groups"] = tuple(groups)
    return cast(
        v175_models.StateLocalDevelopmentCatalog,
        v175._make_model(
            v175_models.StateLocalDevelopmentCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_state_local_presentation_development_catalog:",
        ),
    )


def _old_validate(
    *,
    catalog: v175_models.StateLocalDevelopmentCatalog,
    runner: v175_models.StateLocalRunnerInputCatalog,
    predecessor: PredecessorObjects,
) -> None:
    v175._validate_catalog(
        catalog=catalog,
        schedule_catalog=predecessor.schedules,
        runner=runner,
        source=predecessor.source,
        v173_catalog=predecessor.v173_catalog,
        predecessor=predecessor.v174_catalog,
    )


def _defect_reproduction(predecessor: PredecessorObjects) -> models.V175DefectReproductionAudit:
    accepted_runner = 0
    for field_name in INHERITED_CONTRACT_FIELDS:
        changed_runner = v175._replace_runner_package_fields(
            predecessor.runner,
            {0: {field_name: f"forged:{field_name}"}},
        )
        _old_validate(
            catalog=predecessor.catalog,
            runner=changed_runner,
            predecessor=predecessor,
        )
        accepted_runner += 1

    first = _v175_packages(predecessor.catalog)[0]
    changed_public_task = v175._replace_development_package_field(
        predecessor.catalog,
        field="public_task_id",
        value="forged:public_task",
    )
    changed_public_task_runner = _old_runner_for_changed_development(
        original=predecessor.catalog,
        changed=changed_public_task,
        runner=predecessor.runner,
    )
    _old_validate(
        catalog=changed_public_task,
        runner=changed_public_task_runner,
        predecessor=predecessor,
    )

    accepted_development_contract = 0
    for field_name in INHERITED_CONTRACT_FIELDS:
        changed = _old_replace_all_development_contract(predecessor.catalog, field_name)
        changed_runner = _old_runner_for_changed_development(
            original=predecessor.catalog,
            changed=changed,
            runner=predecessor.runner,
        )
        _old_validate(catalog=changed, runner=changed_runner, predecessor=predecessor)
        accepted_development_contract += 1

    result = first.replica_results[0]
    result_values = result.model_dump(mode="python", exclude={"result_id"})
    result_values["public_citations"] = (*result.public_citations, "public_record:forged")
    changed_result = cast(
        StepRuntimeResult,
        make_identity_model(
            StepRuntimeResult,
            result_values,
            field="result_id",
            prefix="step_runtime_result:",
        ),
    )
    changed_results = (changed_result, *first.replica_results[1:])
    changed_saved = v175._replace_development_package_field(
        predecessor.catalog,
        field="replica_results",
        value=changed_results,
    )
    changed_saved_runner = _old_runner_for_changed_development(
        original=predecessor.catalog,
        changed=changed_saved,
        runner=predecessor.runner,
    )
    _old_validate(
        catalog=changed_saved,
        runner=changed_saved_runner,
        predecessor=predecessor,
    )
    if len(predecessor.exhaustive.rows) != 772:
        raise ValueError("v26.175 Replica-0 interaction denominator changed")
    return cast(
        models.V175DefectReproductionAudit,
        _make_model(
            models.V175DefectReproductionAudit,
            {
                "accepted_runner_inherited_contract_attack_count": accepted_runner,
                "accepted_development_inherited_contract_attack_count": (
                    accepted_development_contract
                ),
                "accepted_fully_rehashed_attack_count": (
                    accepted_runner + accepted_development_contract + 2
                ),
                "full_choice_combination_execution_count": len(predecessor.exhaustive.rows),
                "stale_runner_transition_blocked": True,
            },
            field="audit_id",
            prefix="finance_v26_v175_parent_history_defect_reproduction:",
        ),
    )


def _parent_contract() -> models.AuthoritativePackageRunnerParentContract:
    return cast(
        models.AuthoritativePackageRunnerParentContract,
        _make_model(
            models.AuthoritativePackageRunnerParentContract,
            {
                "development_metadata_fields": DEVELOPMENT_METADATA_FIELDS,
                "runner_metadata_fields": RUNNER_METADATA_FIELDS,
                "inherited_v174_contract_fields": INHERITED_CONTRACT_FIELDS,
            },
            field="contract_id",
            prefix="authoritative_package_runner_parent_contract:",
        ),
    )


def _rejection_history_contract() -> models.TypedRejectionHistoryContract:
    return cast(
        models.TypedRejectionHistoryContract,
        _make_model(
            models.TypedRejectionHistoryContract,
            {},
            field="contract_id",
            prefix="typed_rejection_history_contract:",
        ),
    )


def _build_development_catalog(
    *,
    predecessor: PredecessorObjects,
    parent_contract: models.AuthoritativePackageRunnerParentContract,
    rejection_contract: models.TypedRejectionHistoryContract,
) -> models.AuthoritativeDevelopmentCatalog:
    groups: list[models.AuthoritativeDevelopmentGroup] = []
    for old_group in predecessor.catalog.groups:
        packages: list[models.AuthoritativeDevelopmentPackage] = []
        for old in old_group.packages:
            values = {
                "source_v175_package_artifact_id": old.artifact_id,
                "package_id": old.package_id,
                "source_v174_package_artifact_id": old.source_v174_package_artifact_id,
                "source_v173_package_artifact_id": old.source_v173_package_artifact_id,
                "source_v171_package_artifact_id": old.source_v171_package_artifact_id,
                "source_package_id": old.source_package_id,
                "source_group_id": old.source_group_id,
                "finance_core_id": old.finance_core_id,
                "capability_family": old.capability_family,
                "depth": old.depth,
                "public_task_id": old.public_task_id,
                "topological_component_keys": old.topological_component_keys,
                "reference_path_hash": old.reference_path_hash,
                "presentation_contract_id": old.presentation_contract_id,
                "interaction_parent_receipt_contract_id": (
                    old.interaction_parent_receipt_contract_id
                ),
                "schedule_catalog_id": old.schedule_catalog_id,
                "schedule_ids": old.schedule_ids,
                "mechanism_semantics_contract_id": old.mechanism_semantics_contract_id,
                "failure_receipt_contract_id": old.failure_receipt_contract_id,
                "step_runtime_contract_id": old.step_runtime_contract_id,
                "sequential_estimand_contract_id": old.sequential_estimand_contract_id,
                "authoritative_parent_contract_id": parent_contract.contract_id,
                "typed_rejection_history_contract_id": rejection_contract.contract_id,
                "replica_results": old.replica_results,
            }
            packages.append(
                cast(
                    models.AuthoritativeDevelopmentPackage,
                    _make_model(
                        models.AuthoritativeDevelopmentPackage,
                        values,
                        field="artifact_id",
                        prefix="finance_v26_authoritative_parent_history_package_artifact:",
                    ),
                )
            )
        groups.append(
            cast(
                models.AuthoritativeDevelopmentGroup,
                _make_model(
                    models.AuthoritativeDevelopmentGroup,
                    {
                        "source_group_id": old_group.source_group_id,
                        "finance_core_id": old_group.finance_core_id,
                        "capability_family": old_group.capability_family,
                        "packages": tuple(packages),
                    },
                    field="group_id",
                    prefix="finance_v26_authoritative_parent_history_group:",
                ),
            )
        )
    old = predecessor.catalog
    return cast(
        models.AuthoritativeDevelopmentCatalog,
        _make_model(
            models.AuthoritativeDevelopmentCatalog,
            {
                "source_v175_catalog_id": old.catalog_id,
                "source_v174_catalog_id": old.source_v174_catalog_id,
                "source_v173_catalog_id": old.source_v173_catalog_id,
                "source_v171_catalog_id": old.source_v171_catalog_id,
                "presentation_contract_id": old.presentation_contract_id,
                "interaction_parent_receipt_contract_id": (
                    old.interaction_parent_receipt_contract_id
                ),
                "schedule_catalog_id": old.schedule_catalog_id,
                "mechanism_semantics_contract_id": old.mechanism_semantics_contract_id,
                "failure_receipt_contract_id": old.failure_receipt_contract_id,
                "step_runtime_contract_id": old.step_runtime_contract_id,
                "sequential_estimand_contract_id": old.sequential_estimand_contract_id,
                "authoritative_parent_contract_id": parent_contract.contract_id,
                "typed_rejection_history_contract_id": rejection_contract.contract_id,
                "groups": tuple(groups),
            },
            field="catalog_id",
            prefix="finance_v26_authoritative_parent_history_development_catalog:",
        ),
    )


def _build_runner_input_catalog(
    development: models.AuthoritativeDevelopmentCatalog,
) -> models.AuthoritativeRunnerInputCatalog:
    source_packages = _development_packages(development)
    packages = tuple(
        cast(
            models.AuthoritativeRunnerInputPackage,
            _make_model(
                models.AuthoritativeRunnerInputPackage,
                {
                    "source_development_package_artifact_id": item.artifact_id,
                    **{
                        field_name: getattr(item, field_name)
                        for field_name in DEVELOPMENT_METADATA_FIELDS
                    },
                },
                field="runner_package_id",
                prefix="finance_v26_authoritative_parent_history_runner_input_package:",
            ),
        )
        for item in source_packages
    )
    return cast(
        models.AuthoritativeRunnerInputCatalog,
        _make_model(
            models.AuthoritativeRunnerInputCatalog,
            {
                "source_development_catalog_id": development.catalog_id,
                "presentation_contract_id": development.presentation_contract_id,
                "interaction_parent_receipt_contract_id": (
                    development.interaction_parent_receipt_contract_id
                ),
                "schedule_catalog_id": development.schedule_catalog_id,
                "mechanism_semantics_contract_id": (development.mechanism_semantics_contract_id),
                "failure_receipt_contract_id": development.failure_receipt_contract_id,
                "step_runtime_contract_id": development.step_runtime_contract_id,
                "sequential_estimand_contract_id": (development.sequential_estimand_contract_id),
                "authoritative_parent_contract_id": (development.authoritative_parent_contract_id),
                "typed_rejection_history_contract_id": (
                    development.typed_rejection_history_contract_id
                ),
                "expected_source_artifact_ids": tuple(item.artifact_id for item in source_packages),
                "expected_source_package_ids": tuple(
                    item.source_package_id for item in source_packages
                ),
                "packages": packages,
            },
            field="catalog_id",
            prefix="finance_v26_authoritative_parent_history_runner_input_catalog:",
        ),
    )


def _schedule_mapping(
    *,
    package: models.AuthoritativeDevelopmentPackage,
    source: v171_models.ValiditySeparatedCausalPackage,
    schedule_catalog: v175_models.StateLocalScheduleCatalog,
) -> dict[str, StateLocalRankSchedule]:
    schedules_by_id = {item.schedule_id: item for item in schedule_catalog.schedules}
    ordered = topological_components(source.components)
    return {
        component.component_key: schedules_by_id[schedule_id]
        for component, schedule_id in zip(ordered, package.schedule_ids, strict=True)
    }


def _reference_result(
    *,
    package: models.AuthoritativeDevelopmentPackage,
    source: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
    replica_index: int,
    schedules: Mapping[str, StateLocalRankSchedule],
) -> StepRuntimeResult:
    state = step_runtime.initialize(
        _runtime_input(source, core),
        package_id=package.package_id,
        replica_index=replica_index,
        schedules_by_component=schedules,
    )
    while state.current_index < len(state.ordered_components):
        before = state.current_index
        prompt = step_runtime.render_next_prompt(state)
        observation = step_runtime.step(state, public_only_select_hardened_action(prompt))
        if not observation.action_accepted or state.current_index != before + 1:
            raise ValueError("authoritative reference replay did not commit one Action")
    return step_runtime.finalize(state)


def _expected_development_fields(
    *,
    package: models.AuthoritativeDevelopmentPackage,
    old: v175_models.StateLocalDevelopmentPackage,
    source: v171_models.ValiditySeparatedCausalPackage,
    old_v174: v174_models.HardenedDevelopmentPackage,
    source_group_id: str,
    predecessor: PredecessorObjects,
    parent_contract: models.AuthoritativePackageRunnerParentContract,
    rejection_contract: models.TypedRejectionHistoryContract,
) -> dict[str, Any]:
    ordered = topological_components(source.components)
    topology = tuple(item.component_key for item in ordered)
    reference_path = canonical_hash(
        tuple(item.reference_choice_handle for item in ordered),
        prefix="hardened_reference_path:",
    )
    if old_v174.source_v171_package_artifact_id != source.artifact_id:
        raise ValueError("authoritative v26.174 Package crosses its v26.171 source")
    if old.source_v174_package_artifact_id != old_v174.artifact_id:
        raise ValueError("v26.175 Package crosses its exact v26.174 Package")
    if old_v174.source_v173_package_artifact_id != old.source_v173_package_artifact_id:
        raise ValueError("v26.175 Package crosses its exact v26.173 Package")
    authoritative = {
        "source_v175_package_artifact_id": old.artifact_id,
        "package_id": old.package_id,
        "source_v174_package_artifact_id": old_v174.artifact_id,
        "source_v173_package_artifact_id": old_v174.source_v173_package_artifact_id,
        "source_v171_package_artifact_id": source.artifact_id,
        "source_package_id": source.package_id,
        "source_group_id": source_group_id,
        "finance_core_id": source.finance_core_id,
        "capability_family": source.capability_family,
        "depth": source.depth,
        "public_task_id": source.public_task.task_id,
        "topological_component_keys": topology,
        "reference_path_hash": reference_path,
        "presentation_contract_id": predecessor.catalog.presentation_contract_id,
        "interaction_parent_receipt_contract_id": (
            predecessor.catalog.interaction_parent_receipt_contract_id
        ),
        "schedule_catalog_id": predecessor.schedules.catalog_id,
        "schedule_ids": old.schedule_ids,
        "mechanism_semantics_contract_id": predecessor.v174_mechanism.contract_id,
        "failure_receipt_contract_id": predecessor.v174_receipt.contract_id,
        "step_runtime_contract_id": predecessor.v174_runtime.contract_id,
        "sequential_estimand_contract_id": predecessor.v174_estimand.contract_id,
        "authoritative_parent_contract_id": parent_contract.contract_id,
        "typed_rejection_history_contract_id": rejection_contract.contract_id,
    }
    for field_name, expected in authoritative.items():
        if getattr(old, field_name, expected) != expected and field_name not in {
            "source_v175_package_artifact_id",
            "authoritative_parent_contract_id",
            "typed_rejection_history_contract_id",
        }:
            raise ValueError(f"v26.175 Package metadata differs from source:{field_name}")
    if package.source_v175_package_artifact_id != old.artifact_id:
        raise ValueError("authoritative Package crosses its exact v26.175 artifact")
    return authoritative


def _validate_authoritative_catalog(
    *,
    catalog: models.AuthoritativeDevelopmentCatalog,
    runner: models.AuthoritativeRunnerInputCatalog,
    predecessor: PredecessorObjects,
    parent_contract: models.AuthoritativePackageRunnerParentContract,
    rejection_contract: models.TypedRejectionHistoryContract,
    replay_results: bool,
) -> tuple[int, int, int, int]:
    expected_top = {
        "source_v175_catalog_id": predecessor.catalog.catalog_id,
        "source_v174_catalog_id": predecessor.v174_catalog.catalog_id,
        "source_v173_catalog_id": predecessor.v173_catalog.catalog_id,
        "source_v171_catalog_id": predecessor.source.catalog_id,
        "presentation_contract_id": predecessor.catalog.presentation_contract_id,
        "interaction_parent_receipt_contract_id": (
            predecessor.catalog.interaction_parent_receipt_contract_id
        ),
        "schedule_catalog_id": predecessor.schedules.catalog_id,
        "mechanism_semantics_contract_id": predecessor.v174_mechanism.contract_id,
        "failure_receipt_contract_id": predecessor.v174_receipt.contract_id,
        "step_runtime_contract_id": predecessor.v174_runtime.contract_id,
        "sequential_estimand_contract_id": predecessor.v174_estimand.contract_id,
        "authoritative_parent_contract_id": parent_contract.contract_id,
        "typed_rejection_history_contract_id": rejection_contract.contract_id,
    }
    for field_name, expected_value in expected_top.items():
        if getattr(catalog, field_name) != expected_value:
            raise ValueError(f"authoritative Development Catalog crosses:{field_name}")
    if (
        predecessor.v174_catalog.mechanism_semantics_contract_id
        != predecessor.v174_mechanism.contract_id
        or predecessor.v174_catalog.failure_receipt_contract_id
        != predecessor.v174_receipt.contract_id
        or predecessor.v174_catalog.step_runtime_contract_id != predecessor.v174_runtime.contract_id
        or predecessor.v174_catalog.sequential_estimand_contract_id
        != predecessor.v174_estimand.contract_id
    ):
        raise ValueError("v26.174 Catalog crosses an exact authoritative Contract object")

    old_by_artifact = {item.artifact_id: item for item in _v175_packages(predecessor.catalog)}
    source_by_artifact = {item.artifact_id: item for item in _v171_packages(predecessor.source)}
    v174_by_artifact = {item.artifact_id: item for item in _v174_packages(predecessor.v174_catalog)}
    source_group_by_artifact = {
        package.artifact_id: group.group_id
        for group in predecessor.source.groups
        for package in group.packages
    }
    core_by_id = {item.core_id: item for item in predecessor.source.finance_cores}
    schedule_by_id = {item.schedule_id: item for item in predecessor.schedules.schedules}
    package_matches = 0
    metadata_matches = 0
    replay_matches = 0
    for package in _development_packages(catalog):
        old = old_by_artifact[package.source_v175_package_artifact_id]
        source = source_by_artifact[package.source_v171_package_artifact_id]
        old_v174 = v174_by_artifact[package.source_v174_package_artifact_id]
        development_expected = _expected_development_fields(
            package=package,
            old=old,
            source=source,
            old_v174=old_v174,
            source_group_id=source_group_by_artifact[source.artifact_id],
            predecessor=predecessor,
            parent_contract=parent_contract,
            rejection_contract=rejection_contract,
        )
        for field_name in parent_contract.development_metadata_fields:
            if getattr(package, field_name) != development_expected[field_name]:
                raise ValueError(f"authoritative Development Package crosses source:{field_name}")
            metadata_matches += 1
        for schedule_id, component in zip(
            package.schedule_ids,
            topological_components(source.components),
            strict=True,
        ):
            schedule = schedule_by_id[schedule_id]
            if (
                schedule.source_package_artifact_id != source.artifact_id
                or schedule.component_key != component.component_key
            ):
                raise ValueError("authoritative Development crosses a State Schedule")
        if package.replica_results != old.replica_results:
            raise ValueError("authoritative Development does not preserve v26.175 Results")
        package_matches += 1
        if replay_results:
            schedules = _schedule_mapping(
                package=package,
                source=source,
                schedule_catalog=predecessor.schedules,
            )
            for replica_index, saved in enumerate(package.replica_results):
                fresh = _reference_result(
                    package=package,
                    source=source,
                    core=core_by_id[source.finance_core_id],
                    replica_index=replica_index,
                    schedules=schedules,
                )
                if _canonical_file_bytes(fresh) != _canonical_file_bytes(saved):
                    raise ValueError("fresh six-Replica replay differs from saved Result")
                replay_matches += 1

    if runner.source_development_catalog_id != catalog.catalog_id:
        raise ValueError("authoritative Runner crosses its Development Catalog")
    development_by_artifact = {item.artifact_id: item for item in _development_packages(catalog)}
    if set(runner.expected_source_artifact_ids) != set(development_by_artifact):
        raise ValueError("authoritative Runner source-artifact denominator changed")
    runner_matches = 0
    runner_metadata_matches = 0
    for row in runner.packages:
        source = development_by_artifact[row.source_development_package_artifact_id]
        runner_expected: dict[str, Any] = {
            "source_development_package_artifact_id": source.artifact_id,
            **{
                field_name: getattr(source, field_name)
                for field_name in DEVELOPMENT_METADATA_FIELDS
            },
        }
        for field_name in parent_contract.runner_metadata_fields:
            if getattr(row, field_name) != runner_expected[field_name]:
                raise ValueError(f"authoritative Runner Package crosses source:{field_name}")
            runner_metadata_matches += 1
        runner_matches += 1
    return package_matches, metadata_matches, replay_matches, runner_metadata_matches


def _replace_development_package_field(
    catalog: models.AuthoritativeDevelopmentCatalog,
    *,
    field_name: str,
    value: Any,
) -> models.AuthoritativeDevelopmentCatalog:
    groups = list(catalog.groups)
    group = groups[0]
    packages = list(group.packages)
    values = packages[0].model_dump(mode="python", exclude={"artifact_id"})
    values[field_name] = value
    packages[0] = cast(
        models.AuthoritativeDevelopmentPackage,
        _make_model(
            models.AuthoritativeDevelopmentPackage,
            values,
            field="artifact_id",
            prefix="finance_v26_authoritative_parent_history_package_artifact:",
        ),
    )
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    group_values["packages"] = tuple(packages)
    groups[0] = cast(
        models.AuthoritativeDevelopmentGroup,
        _make_model(
            models.AuthoritativeDevelopmentGroup,
            group_values,
            field="group_id",
            prefix="finance_v26_authoritative_parent_history_group:",
        ),
    )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    catalog_values["groups"] = tuple(groups)
    return cast(
        models.AuthoritativeDevelopmentCatalog,
        _make_model(
            models.AuthoritativeDevelopmentCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_authoritative_parent_history_development_catalog:",
        ),
    )


def _replace_all_development_contract(
    catalog: models.AuthoritativeDevelopmentCatalog,
    field_name: str,
) -> models.AuthoritativeDevelopmentCatalog:
    changed_value = f"forged:{field_name}"
    groups: list[models.AuthoritativeDevelopmentGroup] = []
    for group in catalog.groups:
        packages: list[models.AuthoritativeDevelopmentPackage] = []
        for package in group.packages:
            values = package.model_dump(mode="python", exclude={"artifact_id"})
            values[field_name] = changed_value
            packages.append(
                cast(
                    models.AuthoritativeDevelopmentPackage,
                    _make_model(
                        models.AuthoritativeDevelopmentPackage,
                        values,
                        field="artifact_id",
                        prefix="finance_v26_authoritative_parent_history_package_artifact:",
                    ),
                )
            )
        group_values = group.model_dump(mode="python", exclude={"group_id"})
        group_values["packages"] = tuple(packages)
        groups.append(
            cast(
                models.AuthoritativeDevelopmentGroup,
                _make_model(
                    models.AuthoritativeDevelopmentGroup,
                    group_values,
                    field="group_id",
                    prefix="finance_v26_authoritative_parent_history_group:",
                ),
            )
        )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    catalog_values[field_name] = changed_value
    catalog_values["groups"] = tuple(groups)
    return cast(
        models.AuthoritativeDevelopmentCatalog,
        _make_model(
            models.AuthoritativeDevelopmentCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_authoritative_parent_history_development_catalog:",
        ),
    )


def _replace_development_catalog_field(
    catalog: models.AuthoritativeDevelopmentCatalog,
    field_name: str,
) -> models.AuthoritativeDevelopmentCatalog:
    values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    values[field_name] = f"forged:{field_name}"
    return cast(
        models.AuthoritativeDevelopmentCatalog,
        _make_model(
            models.AuthoritativeDevelopmentCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_authoritative_parent_history_development_catalog:",
        ),
    )


def _replace_runner_package_field(
    runner: models.AuthoritativeRunnerInputCatalog,
    *,
    field_name: str,
    value: Any,
) -> models.AuthoritativeRunnerInputCatalog:
    packages = list(runner.packages)
    values = packages[0].model_dump(mode="python", exclude={"runner_package_id"})
    old_source = packages[0].source_development_package_artifact_id
    values[field_name] = value
    packages[0] = cast(
        models.AuthoritativeRunnerInputPackage,
        _make_model(
            models.AuthoritativeRunnerInputPackage,
            values,
            field="runner_package_id",
            prefix="finance_v26_authoritative_parent_history_runner_input_package:",
        ),
    )
    catalog_values = runner.model_dump(mode="python", exclude={"catalog_id"})
    catalog_values["packages"] = tuple(packages)
    if field_name == "source_development_package_artifact_id":
        catalog_values["expected_source_artifact_ids"] = tuple(
            value if item == old_source else item for item in runner.expected_source_artifact_ids
        )
    return cast(
        models.AuthoritativeRunnerInputCatalog,
        _make_model(
            models.AuthoritativeRunnerInputCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_authoritative_parent_history_runner_input_catalog:",
        ),
    )


def _replace_all_runner_contract(
    runner: models.AuthoritativeRunnerInputCatalog,
    field_name: str,
) -> models.AuthoritativeRunnerInputCatalog:
    changed_value = f"forged:{field_name}"
    packages = []
    for package in runner.packages:
        values = package.model_dump(mode="python", exclude={"runner_package_id"})
        values[field_name] = changed_value
        packages.append(
            cast(
                models.AuthoritativeRunnerInputPackage,
                _make_model(
                    models.AuthoritativeRunnerInputPackage,
                    values,
                    field="runner_package_id",
                    prefix="finance_v26_authoritative_parent_history_runner_input_package:",
                ),
            )
        )
    values = runner.model_dump(mode="python", exclude={"catalog_id"})
    values[field_name] = changed_value
    values["packages"] = tuple(packages)
    return cast(
        models.AuthoritativeRunnerInputCatalog,
        _make_model(
            models.AuthoritativeRunnerInputCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_authoritative_parent_history_runner_input_catalog:",
        ),
    )


def _expect_rejection(
    *,
    name: str,
    surface: str,
    action: Callable[[], Any],
) -> models.MutationResult:
    try:
        action()
    except (KeyError, StopIteration, TypeError, ValidationError, ValueError) as exc:
        return models.MutationResult(
            mutation=name,
            surface=cast(Any, surface),
            fully_rehashed=True,
            rejected=True,
            error_code=type(exc).__name__,
        )
    raise ValueError(f"v26.176 fully rehashed mutation was accepted:{name}")


def _parent_reconstruction_audit(
    *,
    catalog: models.AuthoritativeDevelopmentCatalog,
    runner: models.AuthoritativeRunnerInputCatalog,
    predecessor: PredecessorObjects,
    parent_contract: models.AuthoritativePackageRunnerParentContract,
    rejection_contract: models.TypedRejectionHistoryContract,
) -> models.AuthoritativeParentReconstructionAudit:
    package_matches, metadata_matches, replay_matches, runner_metadata_matches = (
        _validate_authoritative_catalog(
            catalog=catalog,
            runner=runner,
            predecessor=predecessor,
            parent_contract=parent_contract,
            rejection_contract=rejection_contract,
            replay_results=True,
        )
    )

    def validate(
        changed_catalog: models.AuthoritativeDevelopmentCatalog = catalog,
        changed_runner: models.AuthoritativeRunnerInputCatalog | None = None,
        *,
        rebuild_runner: bool = False,
    ) -> None:
        actual_runner = (
            _build_runner_input_catalog(changed_catalog)
            if rebuild_runner
            else changed_runner or runner
        )
        _validate_authoritative_catalog(
            catalog=changed_catalog,
            runner=actual_runner,
            predecessor=predecessor,
            parent_contract=parent_contract,
            rejection_contract=rejection_contract,
            replay_results=False,
        )

    first = _development_packages(catalog)[0]
    same_length = next(
        item
        for item in _development_packages(catalog)[1:]
        if len(item.schedule_ids) == len(first.schedule_ids)
    )
    actions: list[tuple[str, str, Callable[[], Any]]] = []

    def development_field_action(field_name: str, value: Any) -> Callable[[], Any]:
        def action() -> None:
            validate(
                _replace_development_package_field(
                    catalog,
                    field_name=field_name,
                    value=value,
                ),
                rebuild_runner=True,
            )

        return action

    def development_contract_action(field_name: str) -> Callable[[], Any]:
        def action() -> None:
            validate(
                _replace_all_development_contract(catalog, field_name),
                rebuild_runner=True,
            )

        return action

    def development_catalog_action(field_name: str) -> Callable[[], Any]:
        def action() -> None:
            validate(
                _replace_development_catalog_field(catalog, field_name),
                rebuild_runner=True,
            )

        return action

    def runner_field_action(field_name: str, value: Any) -> Callable[[], Any]:
        def action() -> None:
            validate(
                changed_runner=_replace_runner_package_field(
                    runner,
                    field_name=field_name,
                    value=value,
                )
            )

        return action

    def runner_contract_action(field_name: str) -> Callable[[], Any]:
        def action() -> None:
            validate(changed_runner=_replace_all_runner_contract(runner, field_name))

        return action

    for field_name, value in (
        ("public_task_id", "forged:public_task"),
        ("source_v175_package_artifact_id", "forged:v175_package"),
        ("source_v174_package_artifact_id", "forged:v174_package"),
        ("source_v173_package_artifact_id", "forged:v173_package"),
        ("source_v171_package_artifact_id", "forged:v171_package"),
        ("source_package_id", "forged:source_package"),
        ("source_group_id", "forged:source_group"),
        ("finance_core_id", "forged:finance_core"),
        ("capability_family", CapabilityFamily.FAILURE_RECOVERY),
        ("depth", next(item for item in ObservationDepth if item != first.depth)),
        ("topological_component_keys", same_length.topological_component_keys),
        ("reference_path_hash", "forged:reference_path"),
        ("schedule_ids", same_length.schedule_ids),
    ):
        actions.append(
            (
                f"development_{field_name}_changed",
                "development_parent",
                development_field_action(field_name, value),
            )
        )
    for field_name in (
        "presentation_contract_id",
        "interaction_parent_receipt_contract_id",
        *INHERITED_CONTRACT_FIELDS,
        "authoritative_parent_contract_id",
        "typed_rejection_history_contract_id",
    ):
        actions.append(
            (
                f"development_{field_name}_changed",
                "development_parent",
                development_contract_action(field_name),
            )
        )
    for field_name in (
        "source_v175_catalog_id",
        "source_v174_catalog_id",
        "source_v173_catalog_id",
        "source_v171_catalog_id",
    ):
        actions.append(
            (
                f"development_catalog_{field_name}_changed",
                "development_parent",
                development_catalog_action(field_name),
            )
        )

    first_result = first.replica_results[0]
    changed_result_values = first_result.model_dump(mode="python", exclude={"result_id"})
    changed_result_values["public_citations"] = (
        *first_result.public_citations,
        "public_record:forged",
    )
    changed_result = cast(
        StepRuntimeResult,
        make_identity_model(
            StepRuntimeResult,
            changed_result_values,
            field="result_id",
            prefix="step_runtime_result:",
        ),
    )
    actions.append(
        (
            "saved_replica_result_changed",
            "saved_replica_result",
            lambda: validate(
                _replace_development_package_field(
                    catalog,
                    field_name="replica_results",
                    value=(changed_result, *first.replica_results[1:]),
                ),
                rebuild_runner=True,
            ),
        )
    )

    for field_name, value in (
        ("public_task_id", "forged:public_task"),
        ("source_v175_package_artifact_id", "forged:v175_package"),
        ("source_v174_package_artifact_id", "forged:v174_package"),
        ("source_v173_package_artifact_id", "forged:v173_package"),
        ("source_v171_package_artifact_id", "forged:v171_package"),
        ("finance_core_id", "forged:finance_core"),
        ("reference_path_hash", "forged:reference_path"),
        ("schedule_ids", same_length.schedule_ids),
        ("source_development_package_artifact_id", "forged:development_artifact"),
    ):
        actions.append(
            (
                f"runner_{field_name}_changed",
                "runner_parent",
                runner_field_action(field_name, value),
            )
        )
    for field_name in (
        "presentation_contract_id",
        "interaction_parent_receipt_contract_id",
        *INHERITED_CONTRACT_FIELDS,
        "authoritative_parent_contract_id",
        "typed_rejection_history_contract_id",
    ):
        actions.append(
            (
                f"runner_{field_name}_changed",
                "runner_parent",
                runner_contract_action(field_name),
            )
        )
    actions.append(
        (
            "runner_duplicate_source_row",
            "runner_denominator",
            lambda: validate(
                changed_runner=_replace_runner_package_field(
                    runner,
                    field_name="source_development_package_artifact_id",
                    value=runner.packages[1].source_development_package_artifact_id,
                )
            ),
        )
    )
    mutations = tuple(
        _expect_rejection(name=name, surface=surface, action=action)
        for name, surface, action in actions
    )
    return cast(
        models.AuthoritativeParentReconstructionAudit,
        _make_model(
            models.AuthoritativeParentReconstructionAudit,
            {
                "development_package_match_count": package_matches,
                "development_metadata_field_match_count": metadata_matches,
                "fresh_replica_replay_count": replay_matches,
                "fresh_replica_byte_match_count": replay_matches,
                "runner_package_match_count": len(runner.packages),
                "runner_metadata_field_match_count": runner_metadata_matches,
                "mutations": mutations,
                "mutation_count": len(mutations),
                "rejection_count": len(mutations),
            },
            field="audit_id",
            prefix="finance_v26_authoritative_parent_reconstruction_audit:",
        ),
    )


def _choice_action(
    state: step_runtime.StepRuntimeState,
    source_choice_handle: str,
) -> str:
    prompt = step_runtime.render_next_prompt(state)
    mapping = state.pending_source_by_display or {}
    display = next(key for key, value in mapping.items() if value == source_choice_handle)
    return next(item.action_id for item in prompt.candidates if item.choice_handle == display)


def _trajectory_outcome(
    *,
    package: models.AuthoritativeDevelopmentPackage,
    source: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
    schedules: Mapping[str, StateLocalRankSchedule],
    selected_handles: tuple[str, ...],
    replica_index: int,
) -> models.ReplicaTrajectoryOutcome:
    ordered = topological_components(source.components)
    state = step_runtime.initialize(
        _runtime_input(source, core),
        package_id=package.package_id,
        replica_index=replica_index,
        schedules_by_component=schedules,
    )
    acceptances: list[bool] = []
    dependency_consistent = True
    receipt_consistent = True
    roundtrip_passed = True
    rejected_component: str | None = None
    for component, selected_handle in zip(ordered, selected_handles, strict=True):
        prompt = step_runtime.render_next_prompt(state)
        mapping = state.pending_source_by_display or {}
        display = next(key for key, value in mapping.items() if value == selected_handle)
        roundtrip_passed = roundtrip_passed and mapping[display] == selected_handle
        expected_predecessors = tuple(
            state.observations[key].receipt_id for key in component.dependency_component_keys
        )
        dependency_consistent = dependency_consistent and (
            tuple(item.receipt_id for item in prompt.state.prior_observations)
            == expected_predecessors
        )
        before_index = state.current_index
        before_events = len(state.events)
        observation = step_runtime.step(state, _choice_action(state, selected_handle))
        acceptances.append(observation.action_accepted)
        dependency_consistent = dependency_consistent and (
            observation.predecessor_receipt_ids == expected_predecessors
        )
        receipt = prompt.state.failure_receipt
        if source.capability_family == CapabilityFamily.FAILURE_RECOVERY:
            if receipt is None:
                receipt_consistent = False
            else:
                failure_matches = tuple(
                    event for event in state.events if event.event_id == receipt.failure_event_id
                )
                receipt_consistent = receipt_consistent and len(failure_matches) == 1
                new_retries = tuple(
                    event
                    for event in state.events[before_events:]
                    if event.event_type in {"recovery_succeeded", "recovery_retry_failed"}
                )
                if observation.action_accepted:
                    receipt_consistent = receipt_consistent and (
                        len(new_retries) == 1
                        and new_retries[0].public_effects.get("failure_receipt_id")
                        == receipt.receipt_id
                    )
                else:
                    receipt_consistent = receipt_consistent and not new_retries
        elif receipt is not None:
            receipt_consistent = False
        if not observation.action_accepted:
            rejected_component = component.component_key
            if state.current_index != before_index:
                raise ValueError("all-Replica typed rejection advanced its Component")
            break
        if state.current_index != before_index + 1:
            raise ValueError("all-Replica accepted Action did not advance one Component")
    all_accepted = len(acceptances) == len(ordered) and all(acceptances)
    result = step_runtime.finalize(state) if all_accepted else None
    first_failed = rejected_component
    if result is not None and first_failed is None:
        first_failed = next(
            (
                component.component_key
                for component in ordered
                if not result.mechanism_qualification.component_semantic_checks[
                    component.component_key
                ]
            ),
            None,
        )
    references = tuple(item.reference_choice_handle for item in ordered)
    semantic = {
        "selected_source_choice_handles": selected_handles,
        "nonreference_choice_count": sum(
            selected != reference
            for selected, reference in zip(selected_handles, references, strict=True)
        ),
        "attempted_component_count": len(acceptances),
        "committed_component_count": sum(acceptances),
        "all_actions_accepted": all_accepted,
        "typed_rejection": not all_accepted,
        "first_failed_component_key": first_failed,
        "dependency_receipt_consistent": dependency_consistent,
        "exact_failure_receipt_consistent": receipt_consistent,
        "display_source_roundtrip_passed": roundtrip_passed,
        "base_valid": result.task_validity.base_valid if result is not None else None,
        "mechanism_semantically_qualified": (
            result.mechanism_qualification.mechanism_semantically_qualified
            if result is not None
            else None
        ),
        "qualified_valid": (
            result.qualified_validity.qualified_valid if result is not None else None
        ),
        "reference_path_match": (
            result.mechanism_qualification.reference_path_match if result is not None else None
        ),
    }
    values = {
        "package_artifact_id": package.artifact_id,
        "package_id": package.package_id,
        "replica_index": replica_index,
        **semantic,
        "semantic_outcome_hash": hashlib.sha256(_canonical_file_bytes(semantic)).hexdigest(),
    }
    return cast(
        models.ReplicaTrajectoryOutcome,
        _make_model(
            models.ReplicaTrajectoryOutcome,
            values,
            field="execution_id",
            prefix="all_replica_trajectory_outcome:",
        ),
    )


def _all_replica_trajectory_audit(
    *,
    catalog: models.AuthoritativeDevelopmentCatalog,
    predecessor: PredecessorObjects,
) -> models.AllReplicaTrajectoryAudit:
    source_by_artifact = {item.artifact_id: item for item in _v171_packages(predecessor.source)}
    core_by_id = {item.core_id: item for item in predecessor.source.finance_cores}
    outcomes: list[models.ReplicaTrajectoryOutcome] = []
    for package in _development_packages(catalog):
        source = source_by_artifact[package.source_v171_package_artifact_id]
        ordered = topological_components(source.components)
        schedules = _schedule_mapping(
            package=package,
            source=source,
            schedule_catalog=predecessor.schedules,
        )
        choice_vectors = product(
            *(
                tuple(item.choice_handle for item in component.public_state.choice_legend)
                for component in ordered
            )
        )
        for selected in choice_vectors:
            selected_handles = cast(tuple[str, ...], tuple(selected))
            for replica_index in range(6):
                outcomes.append(
                    _trajectory_outcome(
                        package=package,
                        source=source,
                        core=core_by_id[source.finance_core_id],
                        schedules=schedules,
                        selected_handles=selected_handles,
                        replica_index=replica_index,
                    )
                )
    if len(outcomes) != 4_632:
        raise ValueError("all-Replica trajectory denominator changed")
    by_combination: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    for item in outcomes:
        by_combination.setdefault(
            (item.package_artifact_id, item.selected_source_choice_handles),
            [],
        ).append(item.semantic_outcome_hash)
    mismatch_count = sum(
        len(values) != 6 or len(set(values)) != 1 for values in by_combination.values()
    )
    references = tuple(item for item in outcomes if item.nonreference_choice_count == 0)
    single = tuple(item for item in outcomes if item.nonreference_choice_count == 1)
    multi = tuple(item for item in outcomes if item.nonreference_choice_count >= 2)
    accepted = tuple(item for item in outcomes if item.all_actions_accepted)
    return cast(
        models.AllReplicaTrajectoryAudit,
        _make_model(
            models.AllReplicaTrajectoryAudit,
            {
                "outcomes": tuple(outcomes),
                "reference_execution_count": len(references),
                "single_nonreference_execution_count": len(single),
                "multi_nonreference_execution_count": len(multi),
                "fully_accepted_execution_count": len(accepted),
                "typed_rejected_execution_count": len(outcomes) - len(accepted),
                "base_valid_count": sum(bool(item.base_valid) for item in accepted),
                "mechanism_semantically_qualified_count": sum(
                    bool(item.mechanism_semantically_qualified) for item in accepted
                ),
                "qualified_valid_count": sum(bool(item.qualified_valid) for item in accepted),
                "semantic_outcome_replica_mismatch_count": mismatch_count,
                "dependency_receipt_failure_count": sum(
                    not item.dependency_receipt_consistent for item in outcomes
                ),
                "exact_failure_receipt_failure_count": sum(
                    not item.exact_failure_receipt_consistent for item in outcomes
                ),
                "display_source_roundtrip_failure_count": sum(
                    not item.display_source_roundtrip_passed for item in outcomes
                ),
                "qualified_conjunction_mismatch_count": sum(
                    item.qualified_valid
                    != (bool(item.base_valid) and bool(item.mechanism_semantically_qualified))
                    for item in accepted
                ),
            },
            field="audit_id",
            prefix="finance_v26_all_replica_trajectory_audit:",
        ),
    )


def _invalid_action(
    state: step_runtime.StepRuntimeState,
) -> str:
    prompt = step_runtime.render_next_prompt(state)
    component = state.ordered_components[state.current_index]
    mapping = state.pending_source_by_display or {}
    for candidate in prompt.candidates:
        source_handle = mapping[candidate.choice_handle]
        acceptance = classify_action_acceptance(
            package_id=state.package_id,
            task=state.runtime_input.public_task,
            component=component,
            source_choice_handle=source_handle,
            visible_failure_receipt=prompt.state.failure_receipt,
            expected_failure_receipt=state.failure_receipts.get(component.component_key),
        )
        if not acceptance.accepted:
            return candidate.action_id
    raise ValueError("Recovery Component does not expose a typed-rejected Action")


def _state_at_component(
    *,
    package: models.AuthoritativeDevelopmentPackage,
    source: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
    schedules: Mapping[str, StateLocalRankSchedule],
    component_key: str,
    replica_index: int,
) -> step_runtime.StepRuntimeState:
    state = step_runtime.initialize(
        _runtime_input(source, core),
        package_id=package.package_id,
        replica_index=replica_index,
        schedules_by_component=schedules,
    )
    while state.ordered_components[state.current_index].component_key != component_key:
        prompt = step_runtime.render_next_prompt(state)
        observation = step_runtime.step(state, public_only_select_hardened_action(prompt))
        if not observation.action_accepted:
            raise ValueError("Recovery-prefix reference Action did not commit")
    return state


def _retry_count(events: Sequence[Any]) -> int:
    return sum(
        item.event_type in {"recovery_succeeded", "recovery_retry_failed"} for item in events
    )


def _hidden_parent_exposure_count(
    *,
    prompt: Any,
    package: models.AuthoritativeDevelopmentPackage,
    source: v171_models.ValiditySeparatedCausalPackage,
    schedules: Mapping[str, StateLocalRankSchedule],
) -> int:
    forbidden_keys = {
        "schedule_id",
        "schedule_ids",
        "schedule_catalog_id",
        "seed_commitment",
        "derivation_nonce",
        "collision_nonce",
        "source_package_artifact_id",
        "source_v175_package_artifact_id",
        "source_v174_package_artifact_id",
        "source_v173_package_artifact_id",
        "source_v171_package_artifact_id",
        "reference_choice_handle",
        "reference_path_hash",
        "replica_index",
    }
    hidden_values = {
        package.source_v175_package_artifact_id,
        package.source_v174_package_artifact_id,
        package.source_v173_package_artifact_id,
        package.source_v171_package_artifact_id,
        package.reference_path_hash,
        *(item.schedule_id for item in schedules.values()),
        *(item.seed_commitment for item in schedules.values()),
        *(item.reference_choice_handle for item in topological_components(source.components)),
    }
    count = 0

    def walk(value: Any) -> None:
        nonlocal count
        if isinstance(value, Mapping):
            for key, item in value.items():
                if str(key).casefold() in forbidden_keys:
                    count += 1
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, str) and value in hidden_values:
            count += 1

    walk(prompt.model_dump(mode="json"))
    return count


def _finish_reference(state: step_runtime.StepRuntimeState) -> StepRuntimeResult:
    while state.current_index < len(state.ordered_components):
        prompt = step_runtime.render_next_prompt(state)
        observation = step_runtime.step(state, public_only_select_hardened_action(prompt))
        if not observation.action_accepted:
            raise ValueError("corrected reference suffix did not commit")
    return step_runtime.finalize(state)


def _typed_rejection_recovery_audit(
    *,
    catalog: models.AuthoritativeDevelopmentCatalog,
    predecessor: PredecessorObjects,
) -> models.TypedRejectionRecoveryAudit:
    source_by_artifact = {item.artifact_id: item for item in _v171_packages(predecessor.source)}
    core_by_id = {item.core_id: item for item in predecessor.source.finance_cores}
    rows: list[models.TypedRejectionRecoveryRow] = []
    recovery_component_count = 0
    for package in _development_packages(catalog):
        source = source_by_artifact[package.source_v171_package_artifact_id]
        if source.capability_family != CapabilityFamily.FAILURE_RECOVERY:
            continue
        schedules = _schedule_mapping(
            package=package,
            source=source,
            schedule_catalog=predecessor.schedules,
        )
        core = core_by_id[source.finance_core_id]
        for component in topological_components(source.components):
            recovery_component_count += 1
            for replica_index in range(6):
                corrected = _state_at_component(
                    package=package,
                    source=source,
                    core=core,
                    schedules=schedules,
                    component_key=component.component_key,
                    replica_index=replica_index,
                )
                initial_prompt = step_runtime.render_next_prompt(corrected)
                wrong_action = _invalid_action(corrected)
                before_index = corrected.current_index
                before_tools = corrected.local_tool_invocation_count
                before_retries = _retry_count(corrected.events)
                first_observation = step_runtime.step(corrected, wrong_action)
                first_acceptance = corrected.rejection_acceptances_by_component[
                    component.component_key
                ][0]
                first_feedback = corrected.rejection_feedback_by_component[component.component_key][
                    0
                ]
                if (
                    first_observation.action_accepted
                    or corrected.current_index != before_index
                    or corrected.local_tool_invocation_count != before_tools
                    or _retry_count(corrected.events) != before_retries
                ):
                    raise ValueError("initial typed rejection committed Runtime behavior")
                recovery_prompt = step_runtime.render_next_prompt(corrected)
                visible_feedback = recovery_prompt.state.facts.get("current_action_feedback")
                if visible_feedback != (first_feedback.model_dump(mode="json"),):
                    raise ValueError("recovery Prompt does not bind exact typed feedback")
                if recovery_prompt.prompt_hash == initial_prompt.prompt_hash:
                    raise ValueError("recovery Prompt hash ignored its typed feedback parent")
                hidden_count = _hidden_parent_exposure_count(
                    prompt=recovery_prompt,
                    package=package,
                    source=source,
                    schedules=schedules,
                )
                corrected_observation = step_runtime.step(
                    corrected,
                    public_only_select_hardened_action(recovery_prompt),
                )
                if (
                    not corrected_observation.action_accepted
                    or corrected.current_index != before_index + 1
                ):
                    raise ValueError("corrected second response did not commit one Component")
                corrected_result = _finish_reference(corrected)
                if not corrected_result.qualified_validity.qualified_valid:
                    raise ValueError("corrected typed-rejection trajectory is not Qualified")

                repeated = _state_at_component(
                    package=package,
                    source=source,
                    core=core,
                    schedules=schedules,
                    component_key=component.component_key,
                    replica_index=replica_index,
                )
                repeated_wrong_action = _invalid_action(repeated)
                step_runtime.step(repeated, repeated_wrong_action)
                step_runtime.render_next_prompt(repeated)
                second_before_index = repeated.current_index
                second_before_tools = repeated.local_tool_invocation_count
                second_before_retries = _retry_count(repeated.events)
                second_observation = step_runtime.step(repeated, repeated_wrong_action)
                second_feedback = repeated.rejection_feedback_by_component[component.component_key][
                    1
                ]
                later_prompt_blocked = False
                try:
                    step_runtime.render_next_prompt(repeated)
                except step_runtime.TypedRejectionRecoveryExhausted:
                    later_prompt_blocked = True
                if (
                    second_observation.action_accepted
                    or repeated.current_index != second_before_index
                    or repeated.local_tool_invocation_count != second_before_tools
                    or _retry_count(repeated.events) != second_before_retries
                    or repeated.recovery_terminal_feedback_id != second_feedback.feedback_id
                    or not later_prompt_blocked
                ):
                    raise ValueError("repeated wrong Action did not close as a typed terminal")
                rows.append(
                    cast(
                        models.TypedRejectionRecoveryRow,
                        _make_model(
                            models.TypedRejectionRecoveryRow,
                            {
                                "package_artifact_id": package.artifact_id,
                                "package_id": package.package_id,
                                "component_key": component.component_key,
                                "replica_index": replica_index,
                                "rejected_action_id": wrong_action,
                                "first_rejection_observation_id": (first_observation.receipt_id),
                                "first_rejection_acceptance_id": first_acceptance.report_id,
                                "first_feedback_id": first_feedback.feedback_id,
                                "recovery_prompt_hash": recovery_prompt.prompt_hash,
                                "recovery_prompt_parent_match": True,
                                "initial_rejection_retry_delta": 0,
                                "initial_rejection_tool_call_delta": 0,
                                "initial_rejection_component_advance": False,
                                "corrected_action_accepted": True,
                                "corrected_action_component_advance": True,
                                "corrected_final_result_id": corrected_result.result_id,
                                "corrected_final_qualified": True,
                                "repeated_wrong_second_feedback_id": (second_feedback.feedback_id),
                                "repeated_wrong_typed_rejected": True,
                                "repeated_wrong_retry_delta": 0,
                                "repeated_wrong_tool_call_delta": 0,
                                "repeated_wrong_component_advance": False,
                                "repeated_wrong_terminal_emitted": True,
                                "later_prompt_blocked": True,
                                "hidden_parent_exposure_count": hidden_count,
                            },
                            field="row_id",
                            prefix="typed_rejection_recovery_row:",
                        ),
                    )
                )
    if recovery_component_count != 20 or len(rows) != 120:
        raise ValueError("typed-rejection Recovery Component/Replica denominator changed")
    hidden_count = sum(item.hidden_parent_exposure_count for item in rows)
    return cast(
        models.TypedRejectionRecoveryAudit,
        _make_model(
            models.TypedRejectionRecoveryAudit,
            {
                "rows": tuple(rows),
                "model_visible_feedback_parent_match_count": sum(
                    item.recovery_prompt_parent_match for item in rows
                ),
                "hidden_parent_exposure_count": hidden_count,
            },
            field="audit_id",
            prefix="finance_v26_typed_rejection_recovery_audit:",
        ),
    )


def _production_destructive_audit(
    parent: models.AuthoritativeParentReconstructionAudit,
) -> models.ProductionDestructiveAudit:
    return cast(
        models.ProductionDestructiveAudit,
        _make_model(
            models.ProductionDestructiveAudit,
            {
                "mutations": parent.mutations,
                "mutation_count": len(parent.mutations),
                "rejection_count": len(parent.mutations),
            },
            field="audit_id",
            prefix="finance_v26_authoritative_parent_history_destructive_audit:",
        ),
    )


def _static_audit(
    *,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.PredecessorFreezeAudit,
    defect: models.V175DefectReproductionAudit,
    development: models.AuthoritativeDevelopmentCatalog,
    runner: models.AuthoritativeRunnerInputCatalog,
    parent: models.AuthoritativeParentReconstructionAudit,
    all_replica: models.AllReplicaTrajectoryAudit,
    recovery: models.TypedRejectionRecoveryAudit,
    destructive: models.ProductionDestructiveAudit,
) -> models.StaticAudit:
    gates = (
        models.StaticGate(
            gate="transitive_source_closure",
            observed=source_root.unresolved_import_count,
            required=0,
        ),
        models.StaticGate(
            gate="v175_byte_rebuild",
            observed=predecessor.independent_rebuild_match_count,
            required=19,
        ),
        models.StaticGate(
            gate="v175_stale_runner_blocked",
            observed=predecessor.stale_runner_transition_blocked,
            required=True,
        ),
        models.StaticGate(
            gate="v175_parent_gap_reproduced",
            observed=defect.accepted_fully_rehashed_attack_count,
            required=10,
        ),
        models.StaticGate(
            gate="authoritative_development_packages",
            observed=parent.development_package_match_count,
            required=32,
        ),
        models.StaticGate(
            gate="authoritative_development_metadata",
            observed=parent.development_metadata_field_match_count,
            required=32 * len(DEVELOPMENT_METADATA_FIELDS),
        ),
        models.StaticGate(
            gate="inherited_contract_package_bindings",
            observed=parent.inherited_contract_package_match_count,
            required=128,
        ),
        models.StaticGate(
            gate="fresh_six_replica_replay",
            observed=parent.fresh_replica_replay_count,
            required=192,
        ),
        models.StaticGate(
            gate="fresh_replica_byte_match",
            observed=parent.fresh_replica_byte_match_count,
            required=192,
        ),
        models.StaticGate(
            gate="authoritative_runner_packages",
            observed=parent.runner_package_match_count,
            required=32,
        ),
        models.StaticGate(
            gate="authoritative_runner_metadata",
            observed=parent.runner_metadata_field_match_count,
            required=32 * len(RUNNER_METADATA_FIELDS),
        ),
        models.StaticGate(
            gate="runner_inherited_contract_bindings",
            observed=parent.runner_inherited_contract_match_count,
            required=128,
        ),
        models.StaticGate(
            gate="fully_rehashed_parent_attacks",
            observed=parent.rejection_count,
            required=parent.mutation_count,
        ),
        models.StaticGate(
            gate="all_replica_choice_executions",
            observed=all_replica.execution_count,
            required=4_632,
        ),
        models.StaticGate(
            gate="all_replica_semantic_equivalence",
            observed=all_replica.semantic_outcome_replica_mismatch_count,
            required=0,
        ),
        models.StaticGate(
            gate="all_replica_dependency_receipts",
            observed=all_replica.dependency_receipt_failure_count,
            required=0,
        ),
        models.StaticGate(
            gate="all_replica_display_source_roundtrip",
            observed=all_replica.display_source_roundtrip_failure_count,
            required=0,
        ),
        models.StaticGate(
            gate="typed_rejection_visible_feedback",
            observed=recovery.model_visible_feedback_parent_match_count,
            required=120,
        ),
        models.StaticGate(
            gate="corrected_second_response",
            observed=recovery.corrected_final_qualified_count,
            required=120,
        ),
        models.StaticGate(
            gate="repeated_wrong_action_typed_terminal",
            observed=recovery.repeated_wrong_typed_terminal_count,
            required=120,
        ),
        models.StaticGate(
            gate="later_prompt_after_terminal",
            observed=recovery.later_prompt_after_terminal_count,
            required=0,
        ),
        models.StaticGate(
            gate="hidden_parent_exposure",
            observed=recovery.hidden_parent_exposure_count,
            required=0,
        ),
        models.StaticGate(
            gate="rejection_noncommit",
            observed=(
                recovery.rejection_retry_invocation_count
                + recovery.rejection_tool_call_count
                + recovery.rejection_component_advance_count
            ),
            required=0,
        ),
        models.StaticGate(
            gate="runner_source_denominator",
            observed=len(runner.packages),
            required=32,
        ),
        models.StaticGate(
            gate="future_job_denominator",
            observed=runner.future_job_count,
            required=192,
        ),
        models.StaticGate(
            gate="production_destructive_rejection",
            observed=destructive.rejection_count,
            required=destructive.mutation_count,
        ),
        models.StaticGate(
            gate="provider_calls",
            observed=development.provider_calls + runner.provider_calls,
            required=0,
        ),
        models.StaticGate(
            gate="development_jobs",
            observed=development.development_jobs + runner.development_jobs,
            required=0,
        ),
    )
    return cast(
        models.StaticAudit,
        _make_model(
            models.StaticAudit,
            {
                "gates": gates,
                "gate_count": len(gates),
                "passed_gate_count": len(gates),
            },
            field="audit_id",
            prefix="finance_v26_authoritative_parent_history_static_audit:",
        ),
    )


def _transition(
    *,
    predecessor: PredecessorObjects,
    development: models.AuthoritativeDevelopmentCatalog,
    runner: models.AuthoritativeRunnerInputCatalog,
    parent: models.AuthoritativeParentReconstructionAudit,
    recovery: models.TypedRejectionRecoveryAudit,
    all_replica: models.AllReplicaTrajectoryAudit,
    static: models.StaticAudit,
) -> models.ProspectiveTransition:
    return cast(
        models.ProspectiveTransition,
        _make_model(
            models.ProspectiveTransition,
            {
                "predecessor_transition_id": predecessor.transition.transition_id,
                "development_catalog_id": development.catalog_id,
                "runner_input_catalog_id": runner.catalog_id,
                "parent_reconstruction_audit_id": parent.audit_id,
                "typed_rejection_recovery_audit_id": recovery.audit_id,
                "all_replica_trajectory_audit_id": all_replica.audit_id,
                "static_audit_id": static.audit_id,
                "blocked_predecessor_stage": predecessor.transition.next_stage,
                "consumed_stage": models.AUTHORIZED_STAGE,
                "next_stage": models.NEXT_STAGE,
            },
            field="transition_id",
            prefix="finance_v26_authoritative_parent_history_transition:",
        ),
    )


def _detail_files(output_dir: Path) -> tuple[models.FileBinding, ...]:
    return tuple(
        _file_binding(
            path=path,
            relative_path=path.name,
            source_kind=(
                "external_audit_input"
                if path.name == "external_parent_history_audit_input.txt"
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
    predecessor_audit, predecessor = _predecessor_freeze(package_root)
    defect = _defect_reproduction(predecessor)
    parent_contract = _parent_contract()
    rejection_contract = _rejection_history_contract()
    development = _build_development_catalog(
        predecessor=predecessor,
        parent_contract=parent_contract,
        rejection_contract=rejection_contract,
    )
    runner = _build_runner_input_catalog(development)
    parent = _parent_reconstruction_audit(
        catalog=development,
        runner=runner,
        predecessor=predecessor,
        parent_contract=parent_contract,
        rejection_contract=rejection_contract,
    )
    all_replica = _all_replica_trajectory_audit(
        catalog=development,
        predecessor=predecessor,
    )
    recovery = _typed_rejection_recovery_audit(
        catalog=development,
        predecessor=predecessor,
    )
    destructive = _production_destructive_audit(parent)
    static = _static_audit(
        source_root=source_root,
        predecessor=predecessor_audit,
        defect=defect,
        development=development,
        runner=runner,
        parent=parent,
        all_replica=all_replica,
        recovery=recovery,
        destructive=destructive,
    )
    transition = _transition(
        predecessor=predecessor,
        development=development,
        runner=runner,
        parent=parent,
        recovery=recovery,
        all_replica=all_replica,
        static=static,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(
        output_dir / "external_parent_history_audit_input.txt",
        external_audit_path.read_bytes(),
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("v175_predecessor_freeze_audit.json", predecessor_audit),
        ("v175_defect_reproduction_audit.json", defect),
        ("authoritative_package_runner_parent_contract.json", parent_contract),
        ("typed_rejection_history_contract.json", rejection_contract),
        ("authoritative_development_catalog.json", development),
        ("authoritative_runner_input_catalog.json", runner),
        ("authoritative_parent_reconstruction_audit.json", parent),
        ("all_replica_trajectory_audit.json", all_replica),
        ("typed_rejection_recovery_audit.json", recovery),
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
                "predecessor_audit_id": predecessor_audit.audit_id,
                "defect_audit_id": defect.audit_id,
                "parent_contract_id": parent_contract.contract_id,
                "rejection_history_contract_id": rejection_contract.contract_id,
                "development_catalog_id": development.catalog_id,
                "runner_input_catalog_id": runner.catalog_id,
                "parent_reconstruction_audit_id": parent.audit_id,
                "all_replica_trajectory_audit_id": all_replica.audit_id,
                "typed_rejection_recovery_audit_id": recovery.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "detail_files": details,
                "detail_file_count": len(details),
                "next_stage": transition.next_stage,
            },
            field="report_id",
            prefix="finance_v26_authoritative_parent_history_hardening_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor_audit,
        defect=defect,
        parent_contract=parent_contract,
        rejection_history_contract=rejection_contract,
        development_catalog=development,
        runner_input_catalog=runner,
        parent_reconstruction_audit=parent,
        all_replica_trajectory_audit=all_replica,
        typed_rejection_recovery_audit=recovery,
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
