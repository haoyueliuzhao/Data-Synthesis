from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from itertools import combinations, product
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task.capability_observation import CapabilityFamily
from trusted_synthesis.core.task.state_local_presentation_hardening import (
    ExactFailureReceipt,
    HardenedStepRecord,
    StateLocalRankSchedule,
    StepRuntimeResult,
    make_state_local_rank_schedule,
    public_only_select_hardened_action,
    schedule_codebook_signature,
    state_local_factorization_holds,
    topological_components,
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
    phase1_v26_capability_state_local_presentation_parent_hardening_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_state_local_presentation_runtime as step_runtime,
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

RUN_ID: Final = "finance_v26_175_state_local_presentation_parent_hardening_v1_20260829"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_175_state_local_presentation_parent_hardening_v1_20260829"
)
EXPECTED_REVIEW_SHA256: Final = "b59abae33438607bfe7aef62ccfb0ee4c6daa70d11bfdc4583c4192c5ea205b6"
EXPECTED_REVIEW_BYTE_COUNT: Final = 22_189
V174_DIR: Final = v174.OUTPUT_DIR
V173_DIR: Final = v173.OUTPUT_DIR
V171_DIR: Final = v171.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/state_local_presentation_hardening.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_state_local_presentation_runtime.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_state_local_presentation_parent_hardening_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_state_local_presentation_parent_hardening.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.175 cannot resolve the trusted_data_synthesis package root")


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
        raise ValueError(f"v26.175 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.175 immutable output already exists:{path}")
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
        raise ValueError("v26.175 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.175 external audit byte count does not match Authorization")
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
            prefix="finance_v26_state_local_presentation_external_authorization:",
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
        raise ValueError(f"v26.175 source closure has unresolved imports:{sorted(unresolved)}")
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
            prefix="finance_v26_state_local_presentation_transitive_source_root:",
        ),
    )


def _source_packages(
    catalog: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> tuple[v171_models.ValiditySeparatedCausalPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


def _v174_packages(
    catalog: v174_models.HardenedDevelopmentCatalog,
) -> tuple[v174_models.HardenedDevelopmentPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


def _development_packages(
    catalog: models.StateLocalDevelopmentCatalog,
) -> tuple[models.StateLocalDevelopmentPackage, ...]:
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


def _predecessor_freeze(
    package_root: Path,
) -> tuple[
    models.PredecessorFreezeAudit,
    v174_models.HardeningReport,
    v174_models.HardenedDevelopmentCatalog,
    v174_models.HardenedRunnerInputCatalog,
    v174_models.ProspectiveTransition,
    v174_models.JointShortcutAudit,
    v174_models.ExactFailureReceiptAudit,
    v173_models.HardenedDevelopmentCatalog,
    v171_models.ValiditySeparatedDevelopmentCatalog,
]:
    source_dir = package_root / V174_DIR
    paths = tuple(sorted(path for path in source_dir.iterdir() if path.is_file()))
    if len(paths) != 23:
        raise ValueError("v26.174 formal predecessor directory is not exactly 23 files")
    report = v174_models.HardeningReport.model_validate(_load(source_dir / "report.json"))
    catalog = v174_models.HardenedDevelopmentCatalog.model_validate(
        _load(source_dir / "hardened_development_catalog.json")
    )
    runner = v174_models.HardenedRunnerInputCatalog.model_validate(
        _load(source_dir / "hardened_runner_input_catalog.json")
    )
    transition = v174_models.ProspectiveTransition.model_validate(
        _load(source_dir / "prospective_transition_contract.json")
    )
    shortcut = v174_models.JointShortcutAudit.model_validate(
        _load(source_dir / "joint_shortcut_audit.json")
    )
    receipt = v174_models.ExactFailureReceiptAudit.model_validate(
        _load(source_dir / "exact_failure_receipt_audit.json")
    )
    with tempfile.TemporaryDirectory(prefix="finance-v26-175-v174-rebuild-") as temporary:
        rebuild_dir = Path(temporary)
        v174.build(
            package_root=package_root,
            output_dir=rebuild_dir,
            external_audit_path=source_dir / "external_joint_audit_input.txt",
        )
        rebuilt = tuple(sorted(path for path in rebuild_dir.iterdir() if path.is_file()))
        if len(rebuilt) != len(paths):
            raise ValueError("v26.174 independent rebuild file count differs")
        for source_path in paths:
            candidate = rebuild_dir / source_path.name
            if not candidate.is_file() or source_path.read_bytes() != candidate.read_bytes():
                raise ValueError(f"v26.174 independent rebuild differs:{source_path.name}")
    v173_catalog = v173_models.HardenedDevelopmentCatalog.model_validate(
        _load(package_root / V173_DIR / "hardened_development_catalog.json")
    )
    source_catalog = v171_models.ValiditySeparatedDevelopmentCatalog.model_validate(
        _load(package_root / V171_DIR / "validity_separated_development_catalog.json")
    )
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=f"{V174_DIR}/{path.name}",
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
                "predecessor_file_count": 23,
                "independent_rebuild_match_count": 23,
                "predecessor_mutation_count": 0,
                "stale_runner_transition_blocked": True,
            },
            field="audit_id",
            prefix="finance_v26_v174_predecessor_freeze_audit:",
        ),
    )
    return (
        audit,
        report,
        catalog,
        runner,
        transition,
        shortcut,
        receipt,
        v173_catalog,
        source_catalog,
    )


def _rank_features(step: HardenedStepRecord) -> dict[str, dict[str, int]]:
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


def _explicit_triple_attack_success(steps: Sequence[HardenedStepRecord]) -> int:
    success = 0
    for step in steps:
        features = _rank_features(step)
        scores = {
            handle: (
                -2 * features["candidate_position"][handle]
                + 2 * features["action_id_rank"][handle]
                - 3 * features["legend_position"][handle]
            )
            % 6
            for handle in features["candidate_position"]
        }
        maximum = max(scores.values())
        selected = tuple(handle for handle, score in scores.items() if score == maximum)
        success += int(len(selected) == 1 and selected[0] == step.displayed_choice_handle)
    return success


def _rehash_v174_catalog_field(
    catalog: v174_models.HardenedDevelopmentCatalog,
    field: str,
) -> v174_models.HardenedDevelopmentCatalog:
    values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    values[field] = f"changed:{values[field]}"
    return cast(
        v174_models.HardenedDevelopmentCatalog,
        v174_models.make_identity_model(
            v174_models.HardenedDevelopmentCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_joint_presentation_receipt_development_catalog:",
        ),
    )


def _defect_reproduction(
    *,
    catalog: v174_models.HardenedDevelopmentCatalog,
    shortcut: v174_models.JointShortcutAudit,
    receipt: v174_models.ExactFailureReceiptAudit,
) -> models.V174DefectReproductionAudit:
    three_choice_steps = tuple(
        tuple(item.steps[component_index] for item in package.replica_results)
        for package in _v174_packages(catalog)
        for component_index in range(len(package.topological_component_keys))
        if len(package.replica_results[0].steps[component_index].prompt.candidates) == 3
    )
    triple_recovery = sum(_explicit_triple_attack_success(steps) for steps in three_choice_steps)
    if len(three_choice_steps) != 66 or triple_recovery != 396:
        raise ValueError("v26.174 three-rank attack reproduction changed")
    if shortcut.evaluated_rule_count != 23_918 or shortcut.excess_stratum_count != 0:
        raise ValueError("v26.174 registered Shortcut result changed")
    _rehash_v174_catalog_field(catalog, "source_v173_catalog_id")
    _rehash_v174_catalog_field(catalog, "source_v171_catalog_id")
    classifier_only = sum(
        (
            receipt.missing_receipt_rejection_count,
            receipt.changed_receipt_id_rejection_count,
            receipt.changed_error_rejection_count,
            receipt.changed_selector_hash_rejection_count,
            receipt.changed_source_tool_rejection_count,
            receipt.changed_rule_rejection_count,
        )
    )
    return cast(
        models.V174DefectReproductionAudit,
        _make_model(
            models.V174DefectReproductionAudit,
            {
                "triple_rank_attack_recovery_count": triple_recovery,
                "classifier_only_receipt_mutation_count": classifier_only,
            },
            field="audit_id",
            prefix="finance_v26_v174_higher_order_parent_defect_reproduction:",
        ),
    )


def _presentation_contract() -> models.StateLocalPresentationContract:
    return cast(
        models.StateLocalPresentationContract,
        _make_model(
            models.StateLocalPresentationContract,
            {},
            field="contract_id",
            prefix="state_local_higher_order_presentation_contract:",
        ),
    )


def _interaction_contract() -> models.InteractionParentReceiptContract:
    return cast(
        models.InteractionParentReceiptContract,
        _make_model(
            models.InteractionParentReceiptContract,
            {},
            field="contract_id",
            prefix="interaction_parent_receipt_hardening_contract:",
        ),
    )


def _build_schedule_catalog(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    presentation: models.StateLocalPresentationContract,
) -> models.StateLocalScheduleCatalog:
    schedules: list[StateLocalRankSchedule] = []
    used_codebooks: set[str] = set()
    for package in _source_packages(source):
        for component in topological_components(package.components):
            nonce = 0
            while True:
                schedule = make_state_local_rank_schedule(
                    schedule_contract_id=presentation.contract_id,
                    source_package_artifact_id=package.artifact_id,
                    component=component,
                    derivation_nonce=nonce,
                )
                signature = schedule_codebook_signature(schedule)
                if signature not in used_codebooks:
                    used_codebooks.add(signature)
                    schedules.append(schedule)
                    break
                nonce += 1
                if nonce > 10_000:
                    raise ValueError("State-local Schedule uniqueness search did not close")
    if len(schedules) != 80 or len(used_codebooks) != 80:
        raise ValueError("State-local Schedule denominator or codebook uniqueness changed")
    return cast(
        models.StateLocalScheduleCatalog,
        _make_model(
            models.StateLocalScheduleCatalog,
            {
                "presentation_contract_id": presentation.contract_id,
                "schedules": tuple(schedules),
                "unique_codebook_count": len(used_codebooks),
            },
            field="catalog_id",
            prefix="finance_v26_state_local_schedule_catalog:",
        ),
    )


def _schedule_map(
    catalog: models.StateLocalScheduleCatalog,
) -> dict[tuple[str, str], StateLocalRankSchedule]:
    output = {
        (item.source_package_artifact_id, item.component_key): item for item in catalog.schedules
    }
    if len(output) != len(catalog.schedules):
        raise ValueError("State-local Schedule Catalog repeats a source State")
    return output


def _package_id(
    *,
    source: v171_models.ValiditySeparatedCausalPackage,
    predecessor: v174_models.HardenedDevelopmentPackage,
    source_group_id: str,
    topology: Sequence[str],
    reference_path_hash: str,
    presentation_contract_id: str,
    interaction_contract_id: str,
    schedule_catalog_id: str,
    schedule_ids: Sequence[str],
    v174_catalog: v174_models.HardenedDevelopmentCatalog,
) -> str:
    return canonical_hash(
        {
            "capability_family": source.capability_family,
            "depth": source.depth,
            "failure_receipt_contract_id": v174_catalog.failure_receipt_contract_id,
            "finance_core_id": source.finance_core_id,
            "interaction_parent_receipt_contract_id": interaction_contract_id,
            "mechanism_semantics_contract_id": v174_catalog.mechanism_semantics_contract_id,
            "presentation_contract_id": presentation_contract_id,
            "public_task_id": source.public_task.task_id,
            "reference_path_hash": reference_path_hash,
            "schedule_catalog_id": schedule_catalog_id,
            "schedule_ids": tuple(schedule_ids),
            "sequential_estimand_contract_id": v174_catalog.sequential_estimand_contract_id,
            "source_group_id": source_group_id,
            "source_package_id": source.package_id,
            "source_v171_package_artifact_id": source.artifact_id,
            "source_v173_package_artifact_id": predecessor.source_v173_package_artifact_id,
            "source_v174_package_artifact_id": predecessor.artifact_id,
            "step_runtime_contract_id": v174_catalog.step_runtime_contract_id,
            "topological_component_keys": tuple(topology),
            "schema_version": models.V26_STATE_LOCAL_PRESENTATION_VERSION,
        },
        prefix="finance_v26_state_local_presentation_package:",
    )


def _reference_result(
    *,
    package_id: str,
    source: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
    replica_index: int,
    schedules: Mapping[str, StateLocalRankSchedule],
) -> StepRuntimeResult:
    state = step_runtime.initialize(
        _runtime_input(source, core),
        package_id=package_id,
        replica_index=replica_index,
        schedules_by_component=schedules,
    )
    while state.current_index < len(state.ordered_components):
        before = state.current_index
        prompt = step_runtime.render_next_prompt(state)
        observation = step_runtime.step(state, public_only_select_hardened_action(prompt))
        if not observation.action_accepted or state.current_index != before + 1:
            raise ValueError("State-local reference path did not commit its current Action")
    return step_runtime.finalize(state)


def _build_development_catalog(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    predecessor: v174_models.HardenedDevelopmentCatalog,
    presentation: models.StateLocalPresentationContract,
    interaction: models.InteractionParentReceiptContract,
    schedules: models.StateLocalScheduleCatalog,
) -> models.StateLocalDevelopmentCatalog:
    predecessor_by_source = {
        item.source_v171_package_artifact_id: item for item in _v174_packages(predecessor)
    }
    core_by_id = {item.core_id: item for item in source.finance_cores}
    schedule_by_state = _schedule_map(schedules)
    groups: list[models.StateLocalDevelopmentGroup] = []
    for source_group in source.groups:
        packages: list[models.StateLocalDevelopmentPackage] = []
        for source_package in source_group.packages:
            old_package = predecessor_by_source[source_package.artifact_id]
            ordered = topological_components(source_package.components)
            topology = tuple(item.component_key for item in ordered)
            package_schedules = tuple(
                schedule_by_state[(source_package.artifact_id, item.component_key)]
                for item in ordered
            )
            schedule_ids = tuple(item.schedule_id for item in package_schedules)
            reference_path = canonical_hash(
                tuple(item.reference_choice_handle for item in ordered),
                prefix="hardened_reference_path:",
            )
            package_id = _package_id(
                source=source_package,
                predecessor=old_package,
                source_group_id=source_group.group_id,
                topology=topology,
                reference_path_hash=reference_path,
                presentation_contract_id=presentation.contract_id,
                interaction_contract_id=interaction.contract_id,
                schedule_catalog_id=schedules.catalog_id,
                schedule_ids=schedule_ids,
                v174_catalog=predecessor,
            )
            core = core_by_id[source_package.finance_core_id]
            schedule_mapping = {item.component_key: item for item in package_schedules}
            results = tuple(
                _reference_result(
                    package_id=package_id,
                    source=source_package,
                    core=core,
                    replica_index=replica,
                    schedules=schedule_mapping,
                )
                for replica in range(6)
            )
            values = {
                "package_id": package_id,
                "source_v174_package_artifact_id": old_package.artifact_id,
                "source_v173_package_artifact_id": old_package.source_v173_package_artifact_id,
                "source_v171_package_artifact_id": source_package.artifact_id,
                "source_package_id": source_package.package_id,
                "source_group_id": source_group.group_id,
                "finance_core_id": source_package.finance_core_id,
                "capability_family": source_package.capability_family,
                "depth": source_package.depth,
                "public_task_id": source_package.public_task.task_id,
                "topological_component_keys": topology,
                "reference_path_hash": reference_path,
                "presentation_contract_id": presentation.contract_id,
                "interaction_parent_receipt_contract_id": interaction.contract_id,
                "schedule_catalog_id": schedules.catalog_id,
                "schedule_ids": schedule_ids,
                "mechanism_semantics_contract_id": predecessor.mechanism_semantics_contract_id,
                "failure_receipt_contract_id": predecessor.failure_receipt_contract_id,
                "step_runtime_contract_id": predecessor.step_runtime_contract_id,
                "sequential_estimand_contract_id": predecessor.sequential_estimand_contract_id,
                "replica_results": results,
            }
            packages.append(
                cast(
                    models.StateLocalDevelopmentPackage,
                    _make_model(
                        models.StateLocalDevelopmentPackage,
                        values,
                        field="artifact_id",
                        prefix="finance_v26_state_local_presentation_package_artifact:",
                    ),
                )
            )
        groups.append(
            cast(
                models.StateLocalDevelopmentGroup,
                _make_model(
                    models.StateLocalDevelopmentGroup,
                    {
                        "source_group_id": source_group.group_id,
                        "finance_core_id": source_group.finance_core_id,
                        "capability_family": source_group.capability_family,
                        "packages": tuple(packages),
                    },
                    field="group_id",
                    prefix="finance_v26_state_local_presentation_group:",
                ),
            )
        )
    return cast(
        models.StateLocalDevelopmentCatalog,
        _make_model(
            models.StateLocalDevelopmentCatalog,
            {
                "source_v174_catalog_id": predecessor.catalog_id,
                "source_v173_catalog_id": predecessor.source_v173_catalog_id,
                "source_v171_catalog_id": source.catalog_id,
                "presentation_contract_id": presentation.contract_id,
                "interaction_parent_receipt_contract_id": interaction.contract_id,
                "schedule_catalog_id": schedules.catalog_id,
                "mechanism_semantics_contract_id": predecessor.mechanism_semantics_contract_id,
                "failure_receipt_contract_id": predecessor.failure_receipt_contract_id,
                "step_runtime_contract_id": predecessor.step_runtime_contract_id,
                "sequential_estimand_contract_id": predecessor.sequential_estimand_contract_id,
                "groups": tuple(groups),
            },
            field="catalog_id",
            prefix="finance_v26_state_local_presentation_development_catalog:",
        ),
    )


def _build_runner_input_catalog(
    development: models.StateLocalDevelopmentCatalog,
) -> models.StateLocalRunnerInputCatalog:
    source_packages = _development_packages(development)
    packages = tuple(
        cast(
            models.StateLocalRunnerInputPackage,
            _make_model(
                models.StateLocalRunnerInputPackage,
                {
                    "source_development_package_artifact_id": item.artifact_id,
                    "source_v174_package_artifact_id": item.source_v174_package_artifact_id,
                    "source_package_id": item.source_package_id,
                    "public_task_id": item.public_task_id,
                    "topological_component_keys": item.topological_component_keys,
                    "presentation_contract_id": item.presentation_contract_id,
                    "interaction_parent_receipt_contract_id": (
                        item.interaction_parent_receipt_contract_id
                    ),
                    "schedule_catalog_id": item.schedule_catalog_id,
                    "schedule_ids": item.schedule_ids,
                    "mechanism_semantics_contract_id": item.mechanism_semantics_contract_id,
                    "failure_receipt_contract_id": item.failure_receipt_contract_id,
                    "step_runtime_contract_id": item.step_runtime_contract_id,
                    "sequential_estimand_contract_id": item.sequential_estimand_contract_id,
                },
                field="package_id",
                prefix="finance_v26_state_local_presentation_runner_input_package:",
            ),
        )
        for item in source_packages
    )
    return cast(
        models.StateLocalRunnerInputCatalog,
        _make_model(
            models.StateLocalRunnerInputCatalog,
            {
                "source_development_catalog_id": development.catalog_id,
                "presentation_contract_id": development.presentation_contract_id,
                "interaction_parent_receipt_contract_id": (
                    development.interaction_parent_receipt_contract_id
                ),
                "schedule_catalog_id": development.schedule_catalog_id,
                "expected_source_artifact_ids": tuple(item.artifact_id for item in source_packages),
                "expected_source_package_ids": tuple(
                    item.source_package_id for item in source_packages
                ),
                "packages": packages,
            },
            field="catalog_id",
            prefix="finance_v26_state_local_presentation_runner_input_catalog:",
        ),
    )


def _validate_catalog(
    *,
    catalog: models.StateLocalDevelopmentCatalog,
    schedule_catalog: models.StateLocalScheduleCatalog,
    runner: models.StateLocalRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    v173_catalog: v173_models.HardenedDevelopmentCatalog,
    predecessor: v174_models.HardenedDevelopmentCatalog,
) -> tuple[int, int, int]:
    if catalog.source_v174_catalog_id != predecessor.catalog_id:
        raise ValueError("State-local Catalog crosses its exact v26.174 Catalog parent")
    if catalog.source_v173_catalog_id != v173_catalog.catalog_id:
        raise ValueError("State-local Catalog crosses its exact v26.173 Catalog parent")
    if catalog.source_v171_catalog_id != source.catalog_id:
        raise ValueError("State-local Catalog crosses its exact v26.171 Catalog parent")
    if catalog.schedule_catalog_id != schedule_catalog.catalog_id:
        raise ValueError("State-local Catalog crosses its exact Schedule Catalog")
    source_by_artifact = {item.artifact_id: item for item in _source_packages(source)}
    old_by_artifact = {item.artifact_id: item for item in _v174_packages(predecessor)}
    schedules_by_id = {item.schedule_id: item for item in schedule_catalog.schedules}
    package_matches = 0
    schedule_matches = 0
    for package in _development_packages(catalog):
        source_package = source_by_artifact[package.source_v171_package_artifact_id]
        old_package = old_by_artifact[package.source_v174_package_artifact_id]
        if old_package.source_v171_package_artifact_id != source_package.artifact_id:
            raise ValueError("State-local Package crosses its v26.174/v26.171 source parent")
        if old_package.source_v173_package_artifact_id != package.source_v173_package_artifact_id:
            raise ValueError("State-local Package crosses its v26.173 Package parent")
        ordered = topological_components(source_package.components)
        reconstructed_schedules: list[StateLocalRankSchedule] = []
        for component, schedule_id in zip(ordered, package.schedule_ids, strict=True):
            schedule = schedules_by_id[schedule_id]
            reconstructed = make_state_local_rank_schedule(
                schedule_contract_id=catalog.presentation_contract_id,
                source_package_artifact_id=source_package.artifact_id,
                component=component,
                derivation_nonce=schedule.derivation_nonce,
            )
            if reconstructed != schedule:
                raise ValueError("State-local Component Schedule does not reconstruct")
            reconstructed_schedules.append(reconstructed)
            schedule_matches += 1
        expected_package_id = _package_id(
            source=source_package,
            predecessor=old_package,
            source_group_id=package.source_group_id,
            topology=package.topological_component_keys,
            reference_path_hash=package.reference_path_hash,
            presentation_contract_id=catalog.presentation_contract_id,
            interaction_contract_id=catalog.interaction_parent_receipt_contract_id,
            schedule_catalog_id=schedule_catalog.catalog_id,
            schedule_ids=package.schedule_ids,
            v174_catalog=predecessor,
        )
        if expected_package_id != package.package_id:
            raise ValueError("State-local Package identity does not reconstruct")
        package_matches += 1
    development_ids = {item.artifact_id for item in _development_packages(catalog)}
    runner_ids = {item.source_development_package_artifact_id for item in runner.packages}
    if runner.source_development_catalog_id != catalog.catalog_id or runner_ids != development_ids:
        raise ValueError("State-local Runner Input source denominator changed")
    development_by_id = {item.artifact_id: item for item in _development_packages(catalog)}
    for runner_package in runner.packages:
        source_package = development_by_id[runner_package.source_development_package_artifact_id]
        if (
            runner_package.source_v174_package_artifact_id
            != source_package.source_v174_package_artifact_id
            or runner_package.source_package_id != source_package.source_package_id
            or runner_package.public_task_id != source_package.public_task_id
            or runner_package.topological_component_keys
            != source_package.topological_component_keys
            or runner_package.schedule_ids != source_package.schedule_ids
        ):
            raise ValueError("State-local Runner Input crosses an exact Development Package")
    return package_matches, schedule_matches, len(runner_ids)


def _rehash_development_catalog_field(
    catalog: models.StateLocalDevelopmentCatalog,
    field: str,
) -> models.StateLocalDevelopmentCatalog:
    values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    values[field] = f"changed:{values[field]}"
    return cast(
        models.StateLocalDevelopmentCatalog,
        _make_model(
            models.StateLocalDevelopmentCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_state_local_presentation_development_catalog:",
        ),
    )


def _triple_affine_metrics(
    *,
    steps: Sequence[HardenedStepRecord],
    contract: models.StateLocalPresentationContract,
) -> tuple[int, int, int]:
    if len(steps) != 6:
        raise ValueError("Higher-order Shortcut stratum does not contain six Replicas")
    feature_rows = tuple(_rank_features(step) for step in steps)
    channels = tuple(feature_rows[0])
    if any(tuple(item) != channels for item in feature_rows):
        raise ValueError("Higher-order Shortcut visible channel surface changes by Replica")
    choice_count = len(steps[0].prompt.candidates)
    baseline = 6 // choice_count
    evaluated = 0
    maximum = 0
    excess = 0
    for channel_triple in combinations(channels, 3):
        for coefficients in product(contract.triple_affine_coefficients, repeat=3):
            for modulus in contract.triple_affine_moduli:
                minimum_success = 0
                maximum_success = 0
                equality_success = [0] * modulus
                for step, features in zip(steps, feature_rows, strict=True):
                    handles = tuple(item.choice_handle for item in step.prompt.candidates)
                    scores = {
                        handle: sum(
                            coefficient * features[channel][handle]
                            for coefficient, channel in zip(
                                coefficients,
                                channel_triple,
                                strict=True,
                            )
                        )
                        % modulus
                        for handle in handles
                    }
                    low = min(scores.values())
                    high = max(scores.values())
                    low_matches = tuple(handle for handle, score in scores.items() if score == low)
                    high_matches = tuple(
                        handle for handle, score in scores.items() if score == high
                    )
                    minimum_success += int(
                        len(low_matches) == 1 and low_matches[0] == step.displayed_choice_handle
                    )
                    maximum_success += int(
                        len(high_matches) == 1 and high_matches[0] == step.displayed_choice_handle
                    )
                    for residue in range(modulus):
                        matches = tuple(
                            handle for handle, score in scores.items() if score == residue
                        )
                        equality_success[residue] += int(
                            len(matches) == 1 and matches[0] == step.displayed_choice_handle
                        )
                successes = (minimum_success, maximum_success, *equality_success)
                evaluated += len(successes)
                maximum = max(maximum, *successes)
                excess += sum(item > baseline for item in successes)
    return evaluated, maximum, excess


def _verify_reference_rank_materialization(
    *,
    schedule: StateLocalRankSchedule,
    steps: Sequence[HardenedStepRecord],
) -> None:
    channel_names = {
        "candidate": "candidate_position",
        "action": "action_id_rank",
        "legend": "legend_position",
        "display": "display_handle_rank",
    }
    for index in range(len(schedule.argument_fields)):
        channel_names[f"value{index}"] = f"value{index}"
    source_index = schedule.source_choice_handles.index(schedule.reference_choice_handle)
    for replica_index, step in enumerate(steps):
        features = _rank_features(step)
        for schedule_channel, feature_channel in channel_names.items():
            master_rank = schedule.master_rank_by_replica[replica_index][source_index]
            expected = schedule.channel_rank_relabelings[schedule_channel][master_rank]
            observed = features[feature_channel][step.displayed_choice_handle]
            if observed != expected:
                raise ValueError(
                    "State-local Prompt rank differs from its exact Schedule:"
                    f"{schedule.schedule_id}:{schedule_channel}:{replica_index}"
                )


def _higher_order_presentation_audit(
    *,
    catalog: models.StateLocalDevelopmentCatalog,
    schedule_catalog: models.StateLocalScheduleCatalog,
    contract: models.StateLocalPresentationContract,
) -> models.HigherOrderPresentationAudit:
    schedule_by_id = {item.schedule_id: item for item in schedule_catalog.schedules}
    strata: list[models.HigherOrderShortcutStratum] = []
    current_attack_total = 0
    pairwise_rule_total = 0
    triple_rule_total = 0
    for package in _development_packages(catalog):
        for component_index, schedule_id in enumerate(package.schedule_ids):
            schedule = schedule_by_id[schedule_id]
            steps = tuple(item.steps[component_index] for item in package.replica_results)
            _verify_reference_rank_materialization(schedule=schedule, steps=steps)
            pairwise = v174._v174_shortcut_stratum(package, component_index)
            triple_count, triple_maximum, triple_excess = _triple_affine_metrics(
                steps=steps,
                contract=contract,
            )
            explicit_success = _explicit_triple_attack_success(steps)
            if triple_excess:
                raise ValueError(
                    "State-local higher-order Shortcut exceeds baseline:"
                    f"{package.package_id}:{schedule.component_key}:{triple_excess}"
                )
            if not state_local_factorization_holds(schedule):
                raise ValueError("State-local latent-rank factorization failed")
            pairwise_rule_total += pairwise.evaluated_rule_count
            triple_rule_total += triple_count
            if len(steps[0].prompt.candidates) == 3:
                current_attack_total += explicit_success
            strata.append(
                cast(
                    models.HigherOrderShortcutStratum,
                    _make_model(
                        models.HigherOrderShortcutStratum,
                        {
                            "package_id": package.package_id,
                            "capability_family": package.capability_family,
                            "depth": package.depth,
                            "component_key": schedule.component_key,
                            "choice_count": len(steps[0].prompt.candidates),
                            "visible_rank_channel_count": len(_rank_features(steps[0])),
                            "structural_baseline_success_count": (
                                6 // len(steps[0].prompt.candidates)
                            ),
                            "registered_univariate_pairwise_rule_count": (
                                pairwise.evaluated_rule_count
                            ),
                            "registered_triple_affine_rule_count": triple_count,
                            "explicit_counterexample_success_count": explicit_success,
                            "maximum_triple_rule_success_count": triple_maximum,
                            "triple_rule_excess_count": 0,
                            "latent_rank_factorization_passed": True,
                        },
                        field="stratum_id",
                        prefix="higher_order_shortcut_stratum:",
                    ),
                )
            )
    if len(strata) != 80 or current_attack_total > 132:
        raise ValueError("State-local higher-order Presentation denominator changed")
    signatures = {schedule_codebook_signature(item) for item in schedule_catalog.schedules}
    return cast(
        models.HigherOrderPresentationAudit,
        _make_model(
            models.HigherOrderPresentationAudit,
            {
                "strata": tuple(strata),
                "current_explicit_attack_recovery_count": current_attack_total,
                "registered_univariate_pairwise_rule_evaluation_count": pairwise_rule_total,
                "registered_triple_affine_rule_evaluation_count": triple_rule_total,
                "maximum_exact_stratum_recovery_count": max(
                    item.maximum_triple_rule_success_count for item in strata
                ),
                "unique_state_local_codebook_count": len(signatures),
            },
            field="audit_id",
            prefix="finance_v26_higher_order_presentation_audit:",
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


def _trajectory_row(
    *,
    package: models.StateLocalDevelopmentPackage,
    source: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
    schedules: Mapping[str, StateLocalRankSchedule],
    selected_handles: tuple[str, ...],
) -> models.TrajectoryCombinationRow:
    ordered = topological_components(source.components)
    state = step_runtime.initialize(
        _runtime_input(source, core),
        package_id=package.package_id,
        replica_index=0,
        schedules_by_component=schedules,
    )
    acceptances: list[bool] = []
    dependency_consistent = True
    receipt_consistent = True
    rejected_component: str | None = None
    for component, selected_handle in zip(ordered, selected_handles, strict=True):
        prompt = step_runtime.render_next_prompt(state)
        expected_predecessors = tuple(
            state.observations[key].receipt_id for key in component.dependency_component_keys
        )
        dependency_consistent = dependency_consistent and (
            tuple(item.receipt_id for item in prompt.state.prior_observations)
            == expected_predecessors
        )
        before_index = state.current_index
        before_events = len(state.events)
        action = _choice_action(state, selected_handle)
        observation = step_runtime.step(state, action)
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
                raise ValueError("Typed trajectory rejection advanced its target Component")
            break
        if state.current_index != before_index + 1:
            raise ValueError("Accepted trajectory Action did not advance one Component")
    all_accepted = len(acceptances) == len(ordered) and all(acceptances)
    result: StepRuntimeResult | None = step_runtime.finalize(state) if all_accepted else None
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
    values = {
        "package_id": package.package_id,
        "selected_source_choice_handles": selected_handles,
        "nonreference_choice_count": sum(
            selected != reference
            for selected, reference in zip(selected_handles, references, strict=True)
        ),
        "target_component_count": len(ordered),
        "attempted_component_count": len(acceptances),
        "committed_component_count": sum(acceptances),
        "action_acceptance": tuple(acceptances),
        "all_actions_accepted": all_accepted,
        "typed_rejection": not all_accepted,
        "first_failed_component_key": first_failed,
        "dependency_receipt_consistent": dependency_consistent,
        "exact_failure_receipt_consistent": receipt_consistent,
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
        "task_report_id": result.task_validity.report_id if result is not None else None,
        "mechanism_report_id": (
            result.mechanism_qualification.report_id if result is not None else None
        ),
    }
    return cast(
        models.TrajectoryCombinationRow,
        _make_model(
            models.TrajectoryCombinationRow,
            values,
            field="row_id",
            prefix="full_trajectory_combination_row:",
        ),
    )


def _exhaustive_trajectory_audit(
    *,
    catalog: models.StateLocalDevelopmentCatalog,
    schedule_catalog: models.StateLocalScheduleCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> models.ExhaustiveTrajectoryInteractionAudit:
    source_by_artifact = {item.artifact_id: item for item in _source_packages(source)}
    core_by_id = {item.core_id: item for item in source.finance_cores}
    schedule_by_id = {item.schedule_id: item for item in schedule_catalog.schedules}
    rows: list[models.TrajectoryCombinationRow] = []
    package_combination_counts: list[int] = []
    for package in _development_packages(catalog):
        source_package = source_by_artifact[package.source_v171_package_artifact_id]
        ordered = topological_components(source_package.components)
        choice_vectors = tuple(
            product(
                *(
                    tuple(item.choice_handle for item in component.public_state.choice_legend)
                    for component in ordered
                )
            )
        )
        package_combination_counts.append(len(choice_vectors))
        schedules = {
            component.component_key: schedule_by_id[schedule_id]
            for component, schedule_id in zip(ordered, package.schedule_ids, strict=True)
        }
        for selected in choice_vectors:
            rows.append(
                _trajectory_row(
                    package=package,
                    source=source_package,
                    core=core_by_id[source_package.finance_core_id],
                    schedules=schedules,
                    selected_handles=cast(tuple[str, ...], tuple(selected)),
                )
            )
    references = tuple(item for item in rows if item.nonreference_choice_count == 0)
    single = tuple(item for item in rows if item.nonreference_choice_count == 1)
    multi = tuple(item for item in rows if item.nonreference_choice_count >= 2)
    accepted = tuple(item for item in rows if item.all_actions_accepted)
    if len(references) != 32 or sum(bool(item.qualified_valid) for item in references) != 32:
        raise ValueError("Exhaustive trajectory reference denominator changed")
    if len(single) != 146:
        raise ValueError("Exhaustive trajectory single-Choice denominator changed")
    return cast(
        models.ExhaustiveTrajectoryInteractionAudit,
        _make_model(
            models.ExhaustiveTrajectoryInteractionAudit,
            {
                "rows": tuple(rows),
                "declared_combination_count": len(rows),
                "maximum_package_combination_count": max(package_combination_counts),
                "fully_accepted_combination_count": len(accepted),
                "typed_rejected_combination_count": len(rows) - len(accepted),
                "multi_nonreference_combination_count": len(multi),
                "multi_nonreference_fully_accepted_count": sum(
                    item.all_actions_accepted for item in multi
                ),
                "base_valid_count": sum(bool(item.base_valid) for item in accepted),
                "mechanism_semantically_qualified_count": sum(
                    bool(item.mechanism_semantically_qualified) for item in accepted
                ),
                "qualified_valid_count": sum(bool(item.qualified_valid) for item in accepted),
                "qualified_conjunction_mismatch_count": sum(
                    item.qualified_valid
                    != (item.base_valid and item.mechanism_semantically_qualified)
                    for item in accepted
                ),
                "dependency_receipt_failure_count": sum(
                    not item.dependency_receipt_consistent for item in rows
                ),
                "exact_failure_receipt_failure_count": sum(
                    not item.exact_failure_receipt_consistent for item in rows
                ),
                "runtime_exception_count": 0,
            },
            field="audit_id",
            prefix="finance_v26_exhaustive_trajectory_interaction_audit:",
        ),
    )


def _expect_rejection(name: str, action: Callable[[], Any]) -> models.DestructiveMutation:
    try:
        action()
    except (KeyError, StopIteration, TypeError, ValidationError, ValueError) as exc:
        return models.DestructiveMutation(
            mutation=name,
            rejected=True,
            error_code=type(exc).__name__,
        )
    raise ValueError(f"v26.175 destructive mutation was accepted:{name}")


def _replace_development_package_field(
    catalog: models.StateLocalDevelopmentCatalog,
    *,
    field: str,
    value: Any,
) -> models.StateLocalDevelopmentCatalog:
    groups = list(catalog.groups)
    group = groups[0]
    packages = list(group.packages)
    package_values = packages[0].model_dump(mode="python", exclude={"artifact_id"})
    package_values[field] = value
    packages[0] = cast(
        models.StateLocalDevelopmentPackage,
        _make_model(
            models.StateLocalDevelopmentPackage,
            package_values,
            field="artifact_id",
            prefix="finance_v26_state_local_presentation_package_artifact:",
        ),
    )
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    group_values["packages"] = tuple(packages)
    groups[0] = cast(
        models.StateLocalDevelopmentGroup,
        _make_model(
            models.StateLocalDevelopmentGroup,
            group_values,
            field="group_id",
            prefix="finance_v26_state_local_presentation_group:",
        ),
    )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    catalog_values["groups"] = tuple(groups)
    return cast(
        models.StateLocalDevelopmentCatalog,
        _make_model(
            models.StateLocalDevelopmentCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_state_local_presentation_development_catalog:",
        ),
    )


def _rehash_runner_catalog_field(
    runner: models.StateLocalRunnerInputCatalog,
    field: str,
    value: Any,
) -> models.StateLocalRunnerInputCatalog:
    values = runner.model_dump(mode="python", exclude={"catalog_id"})
    values[field] = value
    return cast(
        models.StateLocalRunnerInputCatalog,
        _make_model(
            models.StateLocalRunnerInputCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_state_local_presentation_runner_input_catalog:",
        ),
    )


def _replace_runner_package_fields(
    runner: models.StateLocalRunnerInputCatalog,
    updates_by_index: Mapping[int, Mapping[str, Any]],
) -> models.StateLocalRunnerInputCatalog:
    packages = list(runner.packages)
    for index, updates in updates_by_index.items():
        values = packages[index].model_dump(mode="python", exclude={"package_id"})
        values.update(updates)
        packages[index] = cast(
            models.StateLocalRunnerInputPackage,
            _make_model(
                models.StateLocalRunnerInputPackage,
                values,
                field="package_id",
                prefix="finance_v26_state_local_presentation_runner_input_package:",
            ),
        )
    values = runner.model_dump(mode="python", exclude={"catalog_id"})
    values["packages"] = tuple(packages)
    return cast(
        models.StateLocalRunnerInputCatalog,
        _make_model(
            models.StateLocalRunnerInputCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_state_local_presentation_runner_input_catalog:",
        ),
    )


def _parent_attack_actions(
    *,
    catalog: models.StateLocalDevelopmentCatalog,
    schedule_catalog: models.StateLocalScheduleCatalog,
    runner: models.StateLocalRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    v173_catalog: v173_models.HardenedDevelopmentCatalog,
    predecessor: v174_models.HardenedDevelopmentCatalog,
) -> tuple[tuple[str, Callable[[], Any]], ...]:
    def validate_changed(
        changed_catalog: models.StateLocalDevelopmentCatalog = catalog,
        changed_runner: models.StateLocalRunnerInputCatalog = runner,
    ) -> None:
        _validate_catalog(
            catalog=changed_catalog,
            schedule_catalog=schedule_catalog,
            runner=changed_runner,
            source=source,
            v173_catalog=v173_catalog,
            predecessor=predecessor,
        )

    packages = _development_packages(catalog)
    same_length_package = next(
        item for item in packages[1:] if len(item.schedule_ids) == len(packages[0].schedule_ids)
    )
    runner_same_length_index = next(
        index
        for index, item in enumerate(runner.packages[1:], start=1)
        if len(item.schedule_ids) == len(runner.packages[0].schedule_ids)
    )
    first_runner = runner.packages[0]
    second_runner = runner.packages[runner_same_length_index]
    return (
        (
            "fully_rehashed_source_v174_catalog_id_changed",
            lambda: validate_changed(
                _rehash_development_catalog_field(catalog, "source_v174_catalog_id")
            ),
        ),
        (
            "fully_rehashed_source_v173_catalog_id_changed",
            lambda: validate_changed(
                _rehash_development_catalog_field(catalog, "source_v173_catalog_id")
            ),
        ),
        (
            "fully_rehashed_source_v171_catalog_id_changed",
            lambda: validate_changed(
                _rehash_development_catalog_field(catalog, "source_v171_catalog_id")
            ),
        ),
        (
            "fully_rehashed_runner_source_development_catalog_id_changed",
            lambda: validate_changed(
                changed_runner=_rehash_runner_catalog_field(
                    runner,
                    "source_development_catalog_id",
                    f"changed:{runner.source_development_catalog_id}",
                )
            ),
        ),
        (
            "fully_rehashed_package_source_v174_parent_changed",
            lambda: validate_changed(
                _replace_development_package_field(
                    catalog,
                    field="source_v174_package_artifact_id",
                    value=f"changed:{packages[0].source_v174_package_artifact_id}",
                )
            ),
        ),
        (
            "fully_rehashed_package_schedule_parent_crossed",
            lambda: validate_changed(
                _replace_development_package_field(
                    catalog,
                    field="schedule_ids",
                    value=same_length_package.schedule_ids,
                )
            ),
        ),
        (
            "fully_rehashed_runner_source_pair_crossed",
            lambda: validate_changed(
                changed_runner=_replace_runner_package_fields(
                    runner,
                    {
                        0: {
                            "source_development_package_artifact_id": (
                                second_runner.source_development_package_artifact_id
                            )
                        },
                        runner_same_length_index: {
                            "source_development_package_artifact_id": (
                                first_runner.source_development_package_artifact_id
                            )
                        },
                    },
                )
            ),
        ),
        (
            "fully_rehashed_runner_schedule_parent_crossed",
            lambda: validate_changed(
                changed_runner=_replace_runner_package_fields(
                    runner,
                    {0: {"schedule_ids": second_runner.schedule_ids}},
                )
            ),
        ),
    )


def _source_catalog_parent_audit(
    *,
    catalog: models.StateLocalDevelopmentCatalog,
    schedule_catalog: models.StateLocalScheduleCatalog,
    runner: models.StateLocalRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    v173_catalog: v173_models.HardenedDevelopmentCatalog,
    predecessor: v174_models.HardenedDevelopmentCatalog,
) -> models.SourceCatalogParentAudit:
    package_matches, _, _ = _validate_catalog(
        catalog=catalog,
        schedule_catalog=schedule_catalog,
        runner=runner,
        source=source,
        v173_catalog=v173_catalog,
        predecessor=predecessor,
    )
    attacks = _parent_attack_actions(
        catalog=catalog,
        schedule_catalog=schedule_catalog,
        runner=runner,
        source=source,
        v173_catalog=v173_catalog,
        predecessor=predecessor,
    )[:3]
    rejections = tuple(_expect_rejection(name, action) for name, action in attacks)
    return cast(
        models.SourceCatalogParentAudit,
        _make_model(
            models.SourceCatalogParentAudit,
            {
                "package_source_parent_match_count": package_matches,
                "fully_rehashed_top_level_attack_count": len(attacks),
                "fully_rehashed_top_level_rejection_count": sum(
                    item.rejected for item in rejections
                ),
            },
            field="audit_id",
            prefix="finance_v26_source_catalog_parent_audit:",
        ),
    )


def _mutated_receipt(
    receipt: ExactFailureReceipt,
    mutation: str,
) -> ExactFailureReceipt | None:
    if mutation == "missing":
        return None
    updates: dict[str, Any] = {
        "receipt_id": {"receipt_id": f"changed:{receipt.receipt_id}"},
        "error": {"error_code": "changed_error"},
        "selector": {"failed_selector_hash": "changed_selector_hash"},
        "tool": {"source_tool_id": "changed_tool"},
        "rule": {"rule_handle": "changed_rule"},
    }[mutation]
    return receipt.model_copy(update=updates)


def _runtime_receipt_mutation_audit(
    *,
    catalog: models.StateLocalDevelopmentCatalog,
    schedule_catalog: models.StateLocalScheduleCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> models.RuntimeReceiptMutationAudit:
    source_by_artifact = {item.artifact_id: item for item in _source_packages(source)}
    core_by_id = {item.core_id: item for item in source.finance_cores}
    schedule_by_id = {item.schedule_id: item for item in schedule_catalog.schedules}
    mutation_names = ("missing", "receipt_id", "error", "selector", "tool", "rule")
    executions: list[models.ReceiptMutationExecution] = []
    recovery_component_count = 0
    for package in _development_packages(catalog):
        if package.capability_family != CapabilityFamily.FAILURE_RECOVERY:
            continue
        source_package = source_by_artifact[package.source_v171_package_artifact_id]
        core = core_by_id[source_package.finance_core_id]
        ordered = topological_components(source_package.components)
        schedules = {
            component.component_key: schedule_by_id[schedule_id]
            for component, schedule_id in zip(ordered, package.schedule_ids, strict=True)
        }
        for target_index, component in enumerate(ordered):
            recovery_component_count += 1
            for mutation in mutation_names:
                state = step_runtime.initialize(
                    _runtime_input(source_package, core),
                    package_id=package.package_id,
                    replica_index=0,
                    schedules_by_component=schedules,
                )
                for _predecessor in ordered[:target_index]:
                    prompt = step_runtime.render_next_prompt(state)
                    before = state.current_index
                    observation = step_runtime.step(
                        state,
                        public_only_select_hardened_action(prompt),
                    )
                    if not observation.action_accepted or state.current_index != before + 1:
                        raise ValueError("Receipt mutation setup did not reach its target State")
                prompt = step_runtime.render_next_prompt(state)
                receipt = prompt.state.failure_receipt
                if receipt is None:
                    raise ValueError("Receipt mutation target Prompt has no exact Receipt")
                changed_receipt = _mutated_receipt(receipt, mutation)
                changed_state = prompt.state.model_copy(update={"failure_receipt": changed_receipt})
                state.pending_prompt = prompt.model_copy(update={"state": changed_state})
                action = _choice_action(state, component.reference_choice_handle)
                before_index = state.current_index
                before_tool_calls = state.local_tool_invocation_count
                before_retry_events = sum(
                    item.event_type in {"recovery_succeeded", "recovery_retry_failed"}
                    for item in state.events
                )
                observation = step_runtime.step(state, action)
                after_retry_events = sum(
                    item.event_type in {"recovery_succeeded", "recovery_retry_failed"}
                    for item in state.events
                )
                values = {
                    "package_id": package.package_id,
                    "component_key": component.component_key,
                    "mutation": mutation,
                    "typed_rejected": not observation.action_accepted,
                    "action_committed": False,
                    "retry_invocation_delta": after_retry_events - before_retry_events,
                    "recovery_success_event_delta": sum(
                        item.event_type == "recovery_succeeded" for item in state.events
                    )
                    - sum(item.event_type == "recovery_succeeded" for item in state.events[:-1]),
                    "local_tool_invocation_delta": (
                        state.local_tool_invocation_count - before_tool_calls
                    ),
                    "target_component_advanced": state.current_index != before_index,
                    "next_target_component_advanced": state.current_index > before_index,
                    "exact_failure_event_retained": any(
                        item.event_id == receipt.failure_event_id for item in state.events
                    ),
                }
                executions.append(
                    cast(
                        models.ReceiptMutationExecution,
                        _make_model(
                            models.ReceiptMutationExecution,
                            values,
                            field="execution_id",
                            prefix="receipt_mutation_step_execution:",
                        ),
                    )
                )
    if recovery_component_count != 20 or len(executions) != 120:
        raise ValueError("Runtime Receipt mutation denominator changed")
    return cast(
        models.RuntimeReceiptMutationAudit,
        _make_model(
            models.RuntimeReceiptMutationAudit,
            {
                "executions": tuple(executions),
                "recovery_component_count": recovery_component_count,
                "production_step_execution_count": len(executions),
                "typed_rejection_count": sum(item.typed_rejected for item in executions),
                "retry_invocation_count": sum(item.retry_invocation_delta for item in executions),
                "recovery_success_event_count": sum(
                    item.recovery_success_event_delta for item in executions
                ),
                "local_tool_invocation_count": sum(
                    item.local_tool_invocation_delta for item in executions
                ),
                "target_component_advance_count": sum(
                    item.target_component_advanced for item in executions
                ),
                "next_target_component_advance_count": sum(
                    item.next_target_component_advanced for item in executions
                ),
            },
            field="audit_id",
            prefix="finance_v26_runtime_receipt_mutation_audit:",
        ),
    )


def _parent_closure_audit(
    *,
    catalog: models.StateLocalDevelopmentCatalog,
    schedule_catalog: models.StateLocalScheduleCatalog,
    runner: models.StateLocalRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    v173_catalog: v173_models.HardenedDevelopmentCatalog,
    predecessor: v174_models.HardenedDevelopmentCatalog,
) -> models.ParentClosureAudit:
    package_matches, schedule_matches, runner_matches = _validate_catalog(
        catalog=catalog,
        schedule_catalog=schedule_catalog,
        runner=runner,
        source=source,
        v173_catalog=v173_catalog,
        predecessor=predecessor,
    )
    attacks = _parent_attack_actions(
        catalog=catalog,
        schedule_catalog=schedule_catalog,
        runner=runner,
        source=source,
        v173_catalog=v173_catalog,
        predecessor=predecessor,
    )
    rejections = tuple(_expect_rejection(name, action) for name, action in attacks)
    return cast(
        models.ParentClosureAudit,
        _make_model(
            models.ParentClosureAudit,
            {
                "development_package_reconstruction_match_count": package_matches,
                "schedule_reconstruction_match_count": schedule_matches,
                "runner_package_reconstruction_match_count": runner_matches,
                "runner_unique_source_count": runner_matches,
                "fully_rehashed_mutation_count": len(attacks),
                "fully_rehashed_rejection_count": sum(item.rejected for item in rejections),
            },
            field="audit_id",
            prefix="finance_v26_state_local_parent_closure_audit:",
        ),
    )


def _require_rejection(condition: bool, message: str) -> None:
    if condition:
        raise ValueError(message)


def _production_destructive_audit(
    *,
    catalog: models.StateLocalDevelopmentCatalog,
    schedule_catalog: models.StateLocalScheduleCatalog,
    runner: models.StateLocalRunnerInputCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    v173_catalog: v173_models.HardenedDevelopmentCatalog,
    predecessor: v174_models.HardenedDevelopmentCatalog,
    higher_order: models.HigherOrderPresentationAudit,
    interaction: models.ExhaustiveTrajectoryInteractionAudit,
    receipt: models.RuntimeReceiptMutationAudit,
) -> models.ProductionDestructiveAudit:
    actions = list(
        _parent_attack_actions(
            catalog=catalog,
            schedule_catalog=schedule_catalog,
            runner=runner,
            source=source,
            v173_catalog=v173_catalog,
            predecessor=predecessor,
        )
    )
    schedule = schedule_catalog.schedules[0]
    schedule_payload = schedule.model_dump(mode="python")
    malformed_master = dict(schedule_payload)
    rows = list(malformed_master["master_rank_by_replica"])
    rows[0] = tuple(0 for _ in rows[0])
    malformed_master["master_rank_by_replica"] = tuple(rows)
    missing_channel = dict(schedule_payload)
    channels = dict(missing_channel["channel_rank_relabelings"])
    channels.pop(next(iter(channels)))
    missing_channel["channel_rank_relabelings"] = channels
    changed_seed = dict(schedule_payload)
    changed_seed["seed_commitment"] = "0" * 64
    reference_first = dict(schedule_payload)
    reference_first["reference_first_source_normalization"] = True
    stratum = higher_order.strata[0]
    bad_stratum = stratum.model_dump(mode="python")
    bad_stratum["maximum_triple_rule_success_count"] = stratum.structural_baseline_success_count + 1
    accepted_row = next(item for item in interaction.rows if item.all_actions_accepted)
    bad_qualified = accepted_row.model_dump(mode="python")
    bad_qualified["qualified_valid"] = not bool(accepted_row.qualified_valid)
    missing_result = accepted_row.model_dump(mode="python")
    missing_result["task_report_id"] = None
    receipt_execution = receipt.executions[0]
    bad_retry = receipt_execution.model_dump(mode="python")
    bad_retry["retry_invocation_delta"] = 1
    bad_advance = receipt_execution.model_dump(mode="python")
    bad_advance["target_component_advanced"] = True
    duplicate_runner = runner.model_dump(mode="python")
    duplicate_packages = list(duplicate_runner["packages"])
    duplicate_packages[1] = duplicate_packages[0]
    duplicate_runner["packages"] = tuple(duplicate_packages)
    duplicate_codebooks = [schedule_codebook_signature(item) for item in schedule_catalog.schedules]
    duplicate_codebooks[-1] = duplicate_codebooks[0]
    actions.extend(
        (
            (
                "state_local_master_row_not_permutation",
                lambda: StateLocalRankSchedule.model_validate(malformed_master),
            ),
            (
                "state_local_visible_channel_deleted",
                lambda: StateLocalRankSchedule.model_validate(missing_channel),
            ),
            (
                "state_local_seed_commitment_changed",
                lambda: StateLocalRankSchedule.model_validate(changed_seed),
            ),
            (
                "reference_first_source_normalization_reintroduced",
                lambda: StateLocalRankSchedule.model_validate(reference_first),
            ),
            (
                "state_local_codebook_reused",
                lambda: _require_rejection(
                    len(set(duplicate_codebooks)) != len(duplicate_codebooks),
                    "State-local codebook reuse is forbidden",
                ),
            ),
            (
                "known_three_rank_396_of_396_attack_reintroduced",
                lambda: _require_rejection(
                    396 > higher_order.current_structural_baseline_total,
                    "Known three-rank attack exceeds the exact structural baseline",
                ),
            ),
            (
                "higher_order_exact_stratum_baseline_exceeded",
                lambda: models.HigherOrderShortcutStratum.model_validate(bad_stratum),
            ),
            (
                "trajectory_qualified_conjunction_changed",
                lambda: models.TrajectoryCombinationRow.model_validate(bad_qualified),
            ),
            (
                "accepted_trajectory_result_parent_deleted",
                lambda: models.TrajectoryCombinationRow.model_validate(missing_result),
            ),
            (
                "receipt_rejection_retry_invoked",
                lambda: models.ReceiptMutationExecution.model_validate(bad_retry),
            ),
            (
                "receipt_rejection_target_component_advanced",
                lambda: models.ReceiptMutationExecution.model_validate(bad_advance),
            ),
            (
                "runner_source_row_duplicated",
                lambda: models.StateLocalRunnerInputCatalog.model_validate(duplicate_runner),
            ),
        )
    )
    mutations = tuple(_expect_rejection(name, action) for name, action in actions)
    return cast(
        models.ProductionDestructiveAudit,
        _make_model(
            models.ProductionDestructiveAudit,
            {
                "mutations": mutations,
                "mutation_count": len(mutations),
                "rejection_count": sum(item.rejected for item in mutations),
            },
            field="audit_id",
            prefix="finance_v26_state_local_production_destructive_audit:",
        ),
    )


def _static_audit(
    *,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.PredecessorFreezeAudit,
    defect: models.V174DefectReproductionAudit,
    schedules: models.StateLocalScheduleCatalog,
    higher_order: models.HigherOrderPresentationAudit,
    interaction: models.ExhaustiveTrajectoryInteractionAudit,
    source_parent: models.SourceCatalogParentAudit,
    receipt: models.RuntimeReceiptMutationAudit,
    parent: models.ParentClosureAudit,
    runner: models.StateLocalRunnerInputCatalog,
    destructive: models.ProductionDestructiveAudit,
) -> models.StaticAudit:
    gates = (
        models.StaticGate(
            gate="transitive_source_closure",
            passed=source_root.unresolved_import_count == 0,
            observed=source_root.unresolved_import_count,
            required=0,
        ),
        models.StaticGate(
            gate="v174_byte_rebuild",
            passed=predecessor.independent_rebuild_match_count == 23,
            observed=predecessor.independent_rebuild_match_count,
            required=23,
        ),
        models.StaticGate(
            gate="v174_three_rank_attack_reproduced",
            passed=defect.triple_rank_attack_recovery_count == 396,
            observed=defect.triple_rank_attack_recovery_count,
            required=396,
        ),
        models.StaticGate(
            gate="state_local_schedule_denominator",
            passed=schedules.schedule_count == 80,
            observed=schedules.schedule_count,
            required=80,
        ),
        models.StaticGate(
            gate="state_local_codebook_uniqueness",
            passed=schedules.unique_codebook_count == 80,
            observed=schedules.unique_codebook_count,
            required=80,
        ),
        models.StaticGate(
            gate="reference_first_normalization_absent",
            passed=schedules.reference_first_normalization_count == 0,
            observed=schedules.reference_first_normalization_count,
            required=0,
        ),
        models.StaticGate(
            gate="known_three_rank_attack_below_baseline",
            passed=(
                higher_order.current_explicit_attack_recovery_count
                <= higher_order.current_structural_baseline_total
            ),
            observed=higher_order.current_explicit_attack_recovery_count,
            required=f"<= {higher_order.current_structural_baseline_total}",
        ),
        models.StaticGate(
            gate="triple_affine_exact_stratum_excess_zero",
            passed=higher_order.excess_stratum_count == 0,
            observed=higher_order.excess_stratum_count,
            required=0,
        ),
        models.StaticGate(
            gate="complete_choice_cartesian_surface",
            passed=interaction.declared_combination_count > 146,
            observed=interaction.declared_combination_count,
            required="> 146",
        ),
        models.StaticGate(
            gate="single_choice_surface_retained",
            passed=interaction.legal_single_choice_nonreference_combination_count == 146,
            observed=interaction.legal_single_choice_nonreference_combination_count,
            required=146,
        ),
        models.StaticGate(
            gate="multicomponent_surface_audited",
            passed=interaction.multi_nonreference_combination_count > 0,
            observed=interaction.multi_nonreference_combination_count,
            required="> 0",
        ),
        models.StaticGate(
            gate="qualified_conjunction",
            passed=interaction.qualified_conjunction_mismatch_count == 0,
            observed=interaction.qualified_conjunction_mismatch_count,
            required=0,
        ),
        models.StaticGate(
            gate="trajectory_dependency_receipts",
            passed=interaction.dependency_receipt_failure_count == 0,
            observed=interaction.dependency_receipt_failure_count,
            required=0,
        ),
        models.StaticGate(
            gate="trajectory_exact_failure_receipts",
            passed=interaction.exact_failure_receipt_failure_count == 0,
            observed=interaction.exact_failure_receipt_failure_count,
            required=0,
        ),
        models.StaticGate(
            gate="production_step_receipt_mutations",
            passed=receipt.production_step_execution_count == 120,
            observed=receipt.production_step_execution_count,
            required=120,
        ),
        models.StaticGate(
            gate="receipt_rejection_retry_zero",
            passed=receipt.retry_invocation_count == 0,
            observed=receipt.retry_invocation_count,
            required=0,
        ),
        models.StaticGate(
            gate="receipt_rejection_component_advance_zero",
            passed=receipt.target_component_advance_count == 0,
            observed=receipt.target_component_advance_count,
            required=0,
        ),
        models.StaticGate(
            gate="source_catalog_top_parent_rejection",
            passed=source_parent.fully_rehashed_top_level_rejection_count == 3,
            observed=source_parent.fully_rehashed_top_level_rejection_count,
            required=3,
        ),
        models.StaticGate(
            gate="parent_closure",
            passed=parent.accepted_mutation_count == 0,
            observed=parent.accepted_mutation_count,
            required=0,
        ),
        models.StaticGate(
            gate="runner_denominator",
            passed=runner.package_count == 32,
            observed=runner.package_count,
            required=32,
        ),
        models.StaticGate(
            gate="zero_prompt_runner_input",
            passed=(
                runner.materialized_prompt_count == 0 and runner.materialized_observation_count == 0
            ),
            observed=runner.materialized_prompt_count + runner.materialized_observation_count,
            required=0,
        ),
        models.StaticGate(
            gate="production_destructive_rejection",
            passed=destructive.acceptance_count == 0,
            observed=destructive.acceptance_count,
            required=0,
        ),
        models.StaticGate(
            gate="provider_and_development_jobs_zero",
            passed=True,
            observed=0,
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
                "passed_gate_count": sum(item.passed for item in gates),
            },
            field="audit_id",
            prefix="finance_v26_state_local_presentation_static_audit:",
        ),
    )


def _transition(
    *,
    predecessor: v174_models.ProspectiveTransition,
    development: models.StateLocalDevelopmentCatalog,
    runner: models.StateLocalRunnerInputCatalog,
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
                "consumed_stage": models.AUTHORIZED_STAGE,
                "next_stage": models.NEXT_STAGE,
            },
            field="transition_id",
            prefix="finance_v26_state_local_presentation_transition:",
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
    (
        predecessor_audit,
        _predecessor_report,
        predecessor_catalog,
        _predecessor_runner,
        predecessor_transition,
        predecessor_shortcut,
        predecessor_receipt,
        v173_catalog,
        source,
    ) = _predecessor_freeze(package_root)
    defect = _defect_reproduction(
        catalog=predecessor_catalog,
        shortcut=predecessor_shortcut,
        receipt=predecessor_receipt,
    )
    presentation_contract = _presentation_contract()
    interaction_contract = _interaction_contract()
    schedule_catalog = _build_schedule_catalog(
        source=source,
        presentation=presentation_contract,
    )
    development = _build_development_catalog(
        source=source,
        predecessor=predecessor_catalog,
        presentation=presentation_contract,
        interaction=interaction_contract,
        schedules=schedule_catalog,
    )
    runner = _build_runner_input_catalog(development)
    higher_order = _higher_order_presentation_audit(
        catalog=development,
        schedule_catalog=schedule_catalog,
        contract=presentation_contract,
    )
    exhaustive = _exhaustive_trajectory_audit(
        catalog=development,
        schedule_catalog=schedule_catalog,
        source=source,
    )
    source_parent = _source_catalog_parent_audit(
        catalog=development,
        schedule_catalog=schedule_catalog,
        runner=runner,
        source=source,
        v173_catalog=v173_catalog,
        predecessor=predecessor_catalog,
    )
    receipt = _runtime_receipt_mutation_audit(
        catalog=development,
        schedule_catalog=schedule_catalog,
        source=source,
    )
    parent = _parent_closure_audit(
        catalog=development,
        schedule_catalog=schedule_catalog,
        runner=runner,
        source=source,
        v173_catalog=v173_catalog,
        predecessor=predecessor_catalog,
    )
    destructive = _production_destructive_audit(
        catalog=development,
        schedule_catalog=schedule_catalog,
        runner=runner,
        source=source,
        v173_catalog=v173_catalog,
        predecessor=predecessor_catalog,
        higher_order=higher_order,
        interaction=exhaustive,
        receipt=receipt,
    )
    static = _static_audit(
        source_root=source_root,
        predecessor=predecessor_audit,
        defect=defect,
        schedules=schedule_catalog,
        higher_order=higher_order,
        interaction=exhaustive,
        source_parent=source_parent,
        receipt=receipt,
        parent=parent,
        runner=runner,
        destructive=destructive,
    )
    transition = _transition(
        predecessor=predecessor_transition,
        development=development,
        runner=runner,
        static=static,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(output_dir / "external_joint_audit_input.txt", external_audit_path.read_bytes())
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("v174_predecessor_freeze_audit.json", predecessor_audit),
        ("v174_defect_reproduction_audit.json", defect),
        ("state_local_presentation_contract.json", presentation_contract),
        ("interaction_parent_receipt_contract.json", interaction_contract),
        ("state_local_schedule_catalog.json", schedule_catalog),
        ("state_local_development_catalog.json", development),
        ("state_local_runner_input_catalog.json", runner),
        ("higher_order_presentation_audit.json", higher_order),
        ("exhaustive_trajectory_interaction_audit.json", exhaustive),
        ("source_catalog_parent_audit.json", source_parent),
        ("runtime_receipt_mutation_audit.json", receipt),
        ("parent_closure_audit.json", parent),
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
                "presentation_contract_id": presentation_contract.contract_id,
                "interaction_parent_receipt_contract_id": interaction_contract.contract_id,
                "schedule_catalog_id": schedule_catalog.catalog_id,
                "development_catalog_id": development.catalog_id,
                "runner_input_catalog_id": runner.catalog_id,
                "higher_order_presentation_audit_id": higher_order.audit_id,
                "exhaustive_trajectory_audit_id": exhaustive.audit_id,
                "source_catalog_parent_audit_id": source_parent.audit_id,
                "runtime_receipt_mutation_audit_id": receipt.audit_id,
                "parent_closure_audit_id": parent.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "detail_files": details,
                "detail_file_count": len(details),
                "next_stage": transition.next_stage,
            },
            field="report_id",
            prefix="finance_v26_state_local_presentation_parent_hardening_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor_audit,
        defect=defect,
        presentation_contract=presentation_contract,
        interaction_parent_receipt_contract=interaction_contract,
        schedule_catalog=schedule_catalog,
        development_catalog=development,
        runner_input_catalog=runner,
        higher_order_presentation_audit=higher_order,
        exhaustive_trajectory_audit=exhaustive,
        source_catalog_parent_audit=source_parent,
        runtime_receipt_mutation_audit=receipt,
        parent_closure_audit=parent,
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
