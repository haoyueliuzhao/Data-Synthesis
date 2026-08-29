from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task.dynamic_capability_depth import (
    DYNAMIC_PRESENTATION_SALT,
    BaselineTraceBinding,
    CandidateLegalityProjection,
    DynamicPublicPrompt,
    DynamicReplicaTrace,
    DynamicStepRecord,
    SemanticMechanismQualification,
    classify_candidate,
    make_baseline_trace_binding,
    make_dynamic_prompt,
    make_observation,
    public_only_select_dynamic_action,
    semantic_mechanism_qualification,
    topological_components,
)
from trusted_synthesis.core.task.dynamic_capability_depth import (
    make_identity_model as make_core_identity,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import canonical_bytes
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    CausalSemanticExecutionResult,
    candidate_legality_findings,
)
from trusted_synthesis.core.task.validity_separated_capability_depth import (
    make_identity_model as make_v171_core_identity,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_dynamic_depth_hardening_models as models,
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

RUN_ID: Final = "finance_v26_172_dynamic_depth_hardening_v1_20260829"
OUTPUT_DIR: Final = "artifacts/vtdo_experiment/finance_v26_172_dynamic_depth_hardening_v1_20260829"
EXPECTED_REVIEW_SHA256: Final = "6ea8f1589fd3e6c56007f8d13385b0459a7a07b4a3c065bdf2f1d89a716ec517"
EXPECTED_REVIEW_BYTE_COUNT: Final = 24_338
AUTHORIZED_STAGE: Final = (
    "capability_observation_legend_deleak_mechanism_semantics_and_dynamic_depth_hardening_only"
)
V171_DIR: Final = v171.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/dynamic_capability_depth.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_dynamic_depth_hardening_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_dynamic_depth_hardening.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.172 cannot resolve the trusted_data_synthesis package root")


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
        raise ValueError(f"v26.172 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.172 immutable output already exists:{path}")
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
        raise ValueError("v26.172 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.172 external audit byte count does not match Authorization")
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
            prefix="finance_v26_dynamic_depth_external_audit_authorization:",
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
        raise ValueError(f"v26.172 source closure has unresolved imports:{sorted(unresolved)}")
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=relative,
            source_kind="implementation",
        )
        for relative, path in sorted(files.items())
    )
    values = {
        "entry_modules": entry_modules,
        "files": bindings,
        "file_count": len(bindings),
        "unresolved_import_count": 0,
    }
    return cast(
        models.TransitiveSourceRoot,
        _make_model(
            models.TransitiveSourceRoot,
            values,
            field="root_id",
            prefix="finance_v26_dynamic_depth_transitive_source_root:",
        ),
    )


def _predecessor_freeze(
    package_root: Path,
) -> tuple[
    models.PredecessorFreezeAudit,
    v171_models.ValiditySeparatedDevelopmentCatalog,
    v171_models.ValidityCausalTransition,
]:
    source_dir = package_root / V171_DIR
    paths = tuple(sorted(path for path in source_dir.iterdir() if path.is_file()))
    if len(paths) != 23:
        raise ValueError("v26.171 formal predecessor directory is not exactly 23 files")
    report = v171_models.ValidityCausalReauditReport.model_validate(
        _load(source_dir / "report.json")
    )
    catalog = v171_models.ValiditySeparatedDevelopmentCatalog.model_validate(
        _load(source_dir / "validity_separated_development_catalog.json")
    )
    transition = v171_models.ValidityCausalTransition.model_validate(
        _load(source_dir / "prospective_transition_contract.json")
    )
    with tempfile.TemporaryDirectory(prefix="finance-v26-172-v171-rebuild-") as temporary:
        rebuild_dir = Path(temporary)
        v171.build(
            package_root=package_root,
            output_dir=rebuild_dir,
            external_audit_path=source_dir / "external_joint_audit_input.txt",
        )
        rebuilt_paths = tuple(sorted(path for path in rebuild_dir.iterdir() if path.is_file()))
        if len(rebuilt_paths) != len(paths):
            raise ValueError("v26.171 independent rebuild file count differs")
        for source in paths:
            rebuilt = rebuild_dir / source.name
            if not rebuilt.is_file() or source.read_bytes() != rebuilt.read_bytes():
                raise ValueError(f"v26.171 independent rebuild differs:{source.name}")
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=f"{V171_DIR}/{path.name}",
            source_kind="predecessor_artifact",
        )
        for path in paths
    )
    values = {
        "predecessor_report_id": report.report_id,
        "predecessor_catalog_id": catalog.catalog_id,
        "predecessor_transition_id": transition.transition_id,
        "files": bindings,
        "file_count": 23,
        "independent_rebuild_match_count": 23,
        "predecessor_mutation_count": 0,
    }
    audit = cast(
        models.PredecessorFreezeAudit,
        _make_model(
            models.PredecessorFreezeAudit,
            values,
            field="audit_id",
            prefix="finance_v26_v171_predecessor_freeze_audit:",
        ),
    )
    return audit, catalog, transition


def _legend_contract() -> models.JointLegendPresentationContract:
    values = {
        "registered_shortcut_selectors": (
            "legend_first",
            "legend_last",
            "legend_index",
            "semantic_payload_length",
            "lexical_shape",
            "choice_handle_order",
        ),
        "preoutcome_salt_sha256": hashlib.sha256(DYNAMIC_PRESENTATION_SALT.encode()).hexdigest(),
    }
    return cast(
        models.JointLegendPresentationContract,
        _make_model(
            models.JointLegendPresentationContract,
            values,
            field="contract_id",
            prefix="joint_legend_candidate_presentation_contract:",
        ),
    )


def _mechanism_contract() -> models.MechanismSemanticsContract:
    return cast(
        models.MechanismSemanticsContract,
        _make_model(
            models.MechanismSemanticsContract,
            {},
            field="contract_id",
            prefix="capability_mechanism_semantics_contract:",
        ),
    )


def _runner_contract() -> models.DynamicDepthRunnerContract:
    return cast(
        models.DynamicDepthRunnerContract,
        _make_model(
            models.DynamicDepthRunnerContract,
            {},
            field="contract_id",
            prefix="dynamic_depth_runner_contract:",
        ),
    )


def _legality_contract() -> models.CandidateLegalityContract:
    values = {
        "layers": (
            "publicly_grounded",
            "publicly_executable",
            "state_precondition_valid",
            "mechanism_relevant",
            "task_semantically_valid",
        )
    }
    return cast(
        models.CandidateLegalityContract,
        _make_model(
            models.CandidateLegalityContract,
            values,
            field="contract_id",
            prefix="layered_candidate_legality_contract:",
        ),
    )


def _trace_contract() -> models.BaselineTraceBindingContract:
    values = {
        "replayed_fields": (
            "chosen_choice_handles",
            "runtime_event_ids",
            "runtime_event_order",
            "task_validity_report",
            "mechanism_qualification_report",
            "qualified_validity_report",
        )
    }
    return cast(
        models.BaselineTraceBindingContract,
        _make_model(
            models.BaselineTraceBindingContract,
            values,
            field="contract_id",
            prefix="baseline_trace_parent_binding_contract:",
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


def _dynamic_package_id(
    *,
    source: v171_models.ValiditySeparatedCausalPackage,
    topological_keys: Sequence[str],
    contract_ids: Mapping[str, str],
) -> str:
    return canonical_hash(
        {
            "source_package_artifact_id": source.artifact_id,
            "source_package_id": source.package_id,
            "topological_component_keys": list(topological_keys),
            "contracts": dict(sorted(contract_ids.items())),
            "schema_version": models.V26_DYNAMIC_DEPTH_HARDENING_VERSION,
        },
        prefix="finance_v26_dynamic_depth_package:",
    )


def _reference_trace(
    *,
    package_id: str,
    source: v171_models.ValiditySeparatedCausalPackage,
    baseline: CausalSemanticExecutionResult,
    replica_index: int,
) -> DynamicReplicaTrace:
    ordered = topological_components(source.components)
    observations: dict[str, Any] = {}
    steps: list[DynamicStepRecord] = []
    for step_index, component in enumerate(ordered):
        predecessor = tuple(observations[key] for key in component.dependency_component_keys)
        prompt, source_by_display = make_dynamic_prompt(
            package_id=package_id,
            task=source.public_task,
            component=component,
            replica_index=replica_index,
            predecessor_observations=predecessor,
        )
        selected_action = public_only_select_dynamic_action(prompt)
        selected_candidate = next(
            item for item in prompt.candidates if item.action_id == selected_action
        )
        source_handle = source_by_display[selected_candidate.choice_handle]
        if source_handle != component.reference_choice_handle:
            raise ValueError("dynamic public-only selector did not recover semantic baseline")
        events = tuple(
            item for item in baseline.events if item.component_key == component.component_key
        )
        observation = make_observation(
            prompt=prompt,
            selected_choice_handle=selected_candidate.choice_handle,
            predecessor_receipt_ids=tuple(item.receipt_id for item in predecessor),
            events=events,
        )
        values = {
            "package_id": package_id,
            "replica_index": replica_index,
            "step_index": step_index,
            "component_key": component.component_key,
            "dependency_component_keys": component.dependency_component_keys,
            "source_choice_handle": source_handle,
            "displayed_choice_handle": selected_candidate.choice_handle,
            "selected_action_id": selected_action,
            "prompt": prompt,
            "observation": observation,
        }
        step = cast(
            DynamicStepRecord,
            make_core_identity(
                DynamicStepRecord,
                values,
                field="step_id",
                prefix="dynamic_depth_step_record:",
            ),
        )
        steps.append(step)
        observations[component.component_key] = observation
    values = {
        "package_id": package_id,
        "replica_index": replica_index,
        "steps": tuple(steps),
        "terminal_result_id": baseline.result_id,
        "precommitted_choice_vector_allowed": False,
        "future_prompt_access_allowed": False,
    }
    return cast(
        DynamicReplicaTrace,
        make_core_identity(
            DynamicReplicaTrace,
            values,
            field="trace_id",
            prefix="dynamic_depth_replica_trace:",
        ),
    )


def _build_development_catalog(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    legend: models.JointLegendPresentationContract,
    mechanism: models.MechanismSemanticsContract,
    runner: models.DynamicDepthRunnerContract,
    legality: models.CandidateLegalityContract,
    trace: models.BaselineTraceBindingContract,
) -> models.DynamicHardeningCatalog:
    core_by_id = {item.core_id: item for item in source.finance_cores}
    contract_ids = {
        "legend": legend.contract_id,
        "mechanism": mechanism.contract_id,
        "runner": runner.contract_id,
        "legality": legality.contract_id,
        "trace": trace.contract_id,
    }
    groups: list[models.DynamicHardeningGroup] = []
    for source_group in source.groups:
        packages: list[models.DynamicHardeningPackage] = []
        for source_package in source_group.packages:
            core = core_by_id[source_package.finance_core_id]
            runtime_input = _runtime_input(source_package, core)
            replay = v171_runtime.execute_runtime(runtime_input)
            binding = make_baseline_trace_binding(
                source=source_package.baseline_execution,
                replay=replay,
            )
            ordered = topological_components(source_package.components)
            topological_keys = tuple(item.component_key for item in ordered)
            package_id = _dynamic_package_id(
                source=source_package,
                topological_keys=topological_keys,
                contract_ids=contract_ids,
            )
            semantic = semantic_mechanism_qualification(
                package_id=source_package.package_id,
                family=source_package.capability_family,
                components=source_package.components,
                selected_by_component={},
                result=replay,
            )
            traces = tuple(
                _reference_trace(
                    package_id=package_id,
                    source=source_package,
                    baseline=replay,
                    replica_index=replica,
                )
                for replica in range(6)
            )
            package_values = {
                "package_id": package_id,
                "source_package_artifact_id": source_package.artifact_id,
                "source_package_id": source_package.package_id,
                "source_group_id": source_group.group_id,
                "finance_core_id": source_package.finance_core_id,
                "capability_family": source_package.capability_family,
                "depth": source_package.depth,
                "public_task_id": source_package.public_task.task_id,
                "topological_component_keys": topological_keys,
                "reference_path_hash": canonical_hash(
                    tuple(item.reference_choice_handle for item in ordered),
                    prefix="dynamic_reference_path:",
                ),
                "baseline_trace_binding": binding,
                "baseline_semantic_mechanism": semantic,
                "replica_traces": traces,
            }
            packages.append(
                cast(
                    models.DynamicHardeningPackage,
                    _make_model(
                        models.DynamicHardeningPackage,
                        package_values,
                        field="artifact_id",
                        prefix="finance_v26_dynamic_depth_package_artifact:",
                    ),
                )
            )
        group_values = {
            "source_group_id": source_group.group_id,
            "finance_core_id": source_group.finance_core_id,
            "capability_family": source_group.capability_family,
            "packages": tuple(packages),
        }
        groups.append(
            cast(
                models.DynamicHardeningGroup,
                _make_model(
                    models.DynamicHardeningGroup,
                    group_values,
                    field="group_id",
                    prefix="finance_v26_dynamic_depth_group:",
                ),
            )
        )
    catalog_values = {
        "source_catalog_id": source.catalog_id,
        "legend_contract_id": legend.contract_id,
        "mechanism_contract_id": mechanism.contract_id,
        "runner_contract_id": runner.contract_id,
        "legality_contract_id": legality.contract_id,
        "trace_contract_id": trace.contract_id,
        "groups": tuple(groups),
    }
    return cast(
        models.DynamicHardeningCatalog,
        _make_model(
            models.DynamicHardeningCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_dynamic_depth_development_catalog:",
        ),
    )


def _source_packages(
    catalog: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> tuple[v171_models.ValiditySeparatedCausalPackage, ...]:
    return tuple(package for group in catalog.groups for package in group.packages)


def _runner_input_catalog(
    *,
    development: models.DynamicHardeningCatalog,
) -> models.DynamicRunnerInputCatalog:
    packages = tuple(
        cast(
            models.DynamicRunnerInputPackage,
            _make_model(
                models.DynamicRunnerInputPackage,
                {
                    "source_package_artifact_id": package.source_package_artifact_id,
                    "source_package_id": package.source_package_id,
                    "public_task_id": package.public_task_id,
                    "topological_component_keys": package.topological_component_keys,
                    "legend_contract_id": development.legend_contract_id,
                    "mechanism_contract_id": development.mechanism_contract_id,
                    "runner_contract_id": development.runner_contract_id,
                    "legality_contract_id": development.legality_contract_id,
                    "trace_contract_id": development.trace_contract_id,
                },
                field="package_id",
                prefix="finance_v26_dynamic_depth_runner_input_package:",
            ),
        )
        for package in _dynamic_packages(development)
    )
    return cast(
        models.DynamicRunnerInputCatalog,
        _make_model(
            models.DynamicRunnerInputCatalog,
            {
                "source_development_catalog_id": development.catalog_id,
                "packages": packages,
            },
            field="catalog_id",
            prefix="finance_v26_dynamic_depth_runner_input_catalog:",
        ),
    )


def _dynamic_packages(
    catalog: models.DynamicHardeningCatalog,
) -> tuple[models.DynamicHardeningPackage, ...]:
    return tuple(package for group in catalog.groups for package in group.packages)


def _validate_catalog_against_source(
    *,
    catalog: models.DynamicHardeningCatalog,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> None:
    source_by_artifact = {item.artifact_id: item for item in _source_packages(source)}
    core_by_id = {item.core_id: item for item in source.finance_cores}
    for package in _dynamic_packages(catalog):
        source_package = source_by_artifact.get(package.source_package_artifact_id)
        if source_package is None:
            raise ValueError("dynamic Catalog crosses an absent predecessor Package")
        replay = v171_runtime.execute_runtime(
            _runtime_input(source_package, core_by_id[source_package.finance_core_id])
        )
        expected = make_baseline_trace_binding(
            source=source_package.baseline_execution,
            replay=replay,
        )
        if package.baseline_trace_binding != expected:
            raise ValueError("dynamic Catalog baseline trace differs from exact predecessor replay")
        ordered = topological_components(source_package.components)
        if package.topological_component_keys != tuple(item.component_key for item in ordered):
            raise ValueError("dynamic Catalog Component topology differs from predecessor graph")
        for replica in package.replica_traces:
            for step, component in zip(replica.steps, ordered, strict=True):
                if step.source_choice_handle != component.reference_choice_handle:
                    raise ValueError(
                        "dynamic Trace source Choice differs from predecessor reference"
                    )
                expected_events = tuple(
                    item.event_id
                    for item in replay.events
                    if item.component_key == component.component_key
                )
                if step.observation.event_ids != expected_events:
                    raise ValueError("dynamic Observation differs from exact Runtime replay")


def _candidate_and_mechanism_audits(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    dynamic_catalog: models.DynamicHardeningCatalog,
) -> tuple[models.CandidateLegalityCatalog, models.MechanismSemanticsAudit]:
    core_by_id = {item.core_id: item for item in source.finance_cores}
    dynamic_by_source = {
        item.source_package_artifact_id: item for item in _dynamic_packages(dynamic_catalog)
    }
    projections: list[CandidateLegalityProjection] = []
    unique_executions: list[
        tuple[
            v171_models.ValiditySeparatedCausalPackage,
            Mapping[str, str],
            CausalSemanticExecutionResult,
            SemanticMechanismQualification,
        ]
    ] = []
    for package in _source_packages(source):
        runtime_input = _runtime_input(package, core_by_id[package.finance_core_id])
        baseline = v171_runtime.execute_runtime(runtime_input)
        baseline_semantic = semantic_mechanism_qualification(
            package_id=package.package_id,
            family=package.capability_family,
            components=package.components,
            selected_by_component={},
            result=baseline,
        )
        unique_executions.append((package, {}, baseline, baseline_semantic))
        dynamic_package = dynamic_by_source[package.artifact_id]
        for component in package.components:
            for legend_entry in component.public_state.choice_legend:
                reference = legend_entry.choice_handle == component.reference_choice_handle
                selected = (
                    {} if reference else {component.component_key: legend_entry.choice_handle}
                )
                if reference:
                    result = baseline
                else:
                    result = v171_runtime.execute_runtime(runtime_input, selected)
                semantic = semantic_mechanism_qualification(
                    package_id=package.package_id,
                    family=package.capability_family,
                    components=package.components,
                    selected_by_component=selected,
                    result=result,
                )
                if not reference:
                    unique_executions.append((package, selected, result, semantic))
                grounded, executable, precondition, relevant, findings = classify_candidate(
                    task=package.public_task,
                    component=component,
                    source_choice_handle=legend_entry.choice_handle,
                    result=result,
                )
                values = {
                    "package_id": dynamic_package.package_id,
                    "component_key": component.component_key,
                    "source_choice_handle": legend_entry.choice_handle,
                    "reference_path_choice": reference,
                    "publicly_grounded": grounded,
                    "publicly_executable": executable,
                    "state_precondition_valid": precondition,
                    "mechanism_relevant": relevant,
                    "task_semantically_valid": result.task_validity.base_valid,
                    "findings": findings,
                    "execution_result_id": result.result_id,
                }
                projections.append(
                    cast(
                        CandidateLegalityProjection,
                        make_core_identity(
                            CandidateLegalityProjection,
                            values,
                            field="projection_id",
                            prefix="dynamic_candidate_legality_projection:",
                        ),
                    )
                )
    if len(unique_executions) != 178 or len(projections) != 226:
        raise ValueError("dynamic Candidate or execution denominator changed")
    wrong_recovery = tuple(
        item for item in projections if "current_state_precondition_mismatch" in item.findings
    )
    legality_values = {
        "projections": tuple(projections),
        "candidate_count": len(projections),
        "publicly_grounded_count": sum(item.publicly_grounded for item in projections),
        "publicly_executable_count": sum(item.publicly_executable for item in projections),
        "state_precondition_valid_count": sum(
            item.state_precondition_valid for item in projections
        ),
        "mechanism_relevant_count": sum(item.mechanism_relevant for item in projections),
        "task_semantically_valid_count": sum(item.task_semantically_valid for item in projections),
        "recovery_wrong_current_rule_executable_count": sum(
            item.publicly_executable for item in wrong_recovery
        ),
        "recovery_wrong_current_rule_state_valid_count": sum(
            item.state_precondition_valid for item in wrong_recovery
        ),
    }
    legality_catalog = cast(
        models.CandidateLegalityCatalog,
        _make_model(
            models.CandidateLegalityCatalog,
            legality_values,
            field="catalog_id",
            prefix="finance_v26_layered_candidate_legality_catalog:",
        ),
    )
    matrix = {
        "base_false_semantic_false": 0,
        "base_false_semantic_true": 0,
        "base_true_semantic_false": 0,
        "base_true_semantic_true": 0,
    }
    old_separation: list[
        tuple[v171_models.ValiditySeparatedCausalPackage, SemanticMechanismQualification]
    ] = []
    for package, _, result, semantic in unique_executions:
        key = (
            f"base_{str(result.task_validity.base_valid).lower()}_"
            f"semantic_{str(semantic.mechanism_semantically_qualified).lower()}"
        )
        matrix[key] += 1
        if (
            result.task_validity.base_valid
            and not result.mechanism_qualification.mechanism_qualified
        ):
            old_separation.append((package, semantic))
    recovered = tuple(item for item in old_separation if item[1].mechanism_semantically_qualified)
    mechanism_values = {
        "execution_count": len(unique_executions),
        "baseline_count": 32,
        "legal_nonreference_count": 146,
        "reference_path_match_count": sum(
            item[3].reference_path_match for item in unique_executions
        ),
        "semantic_mechanism_qualified_count": sum(
            item[3].mechanism_semantically_qualified for item in unique_executions
        ),
        "base_true_old_canonical_false_count": len(old_separation),
        "base_true_old_canonical_false_semantic_true_count": len(recovered),
        "context_recovered_semantic_count": sum(
            item[0].capability_family.value == "context_conditioned_action" for item in recovered
        ),
        "recovery_recovered_semantic_count": sum(
            item[0].capability_family.value == "failure_recovery" for item in recovered
        ),
        "base_semantic_matrix": matrix,
        "reference_path_and_semantic_fields_separate": True,
    }
    mechanism_audit = cast(
        models.MechanismSemanticsAudit,
        _make_model(
            models.MechanismSemanticsAudit,
            mechanism_values,
            field="audit_id",
            prefix="finance_v26_mechanism_semantics_audit:",
        ),
    )
    return legality_catalog, mechanism_audit


def _legend_shortcut_audit(
    catalog: models.DynamicHardeningCatalog,
) -> models.LegendShortcutAudit:
    steps = tuple(
        step
        for package in _dynamic_packages(catalog)
        for trace in package.replica_traces
        for step in trace.steps
    )
    if len(steps) != 480:
        raise ValueError("dynamic Legend presentation denominator changed")
    first = sum(
        step.prompt.state.choice_legend[0].choice_handle == step.displayed_choice_handle
        for step in steps
    )
    last = sum(
        step.prompt.state.choice_legend[-1].choice_handle == step.displayed_choice_handle
        for step in steps
    )
    index_counts = [
        sum(
            index < len(step.prompt.state.choice_legend)
            and step.prompt.state.choice_legend[index].choice_handle == step.displayed_choice_handle
            for step in steps
        )
        for index in range(3)
    ]
    semantic_length = 0
    lexical_shape = 0
    for step in steps:
        entries = step.prompt.state.choice_legend
        lengths = [len(canonical_bytes(item.model_dump(mode="json"))) for item in entries]
        minimum = min(lengths)
        if lengths.count(minimum) == 1:
            semantic_length += entries[lengths.index(minimum)].choice_handle == (
                step.displayed_choice_handle
            )
        shapes = [
            (
                len(type(item).model_fields),
                tuple(type(value).__name__ for value in item.value_indices),
            )
            for item in entries
        ]
        minimum_shape = min(shapes)
        if shapes.count(minimum_shape) == 1:
            lexical_shape += entries[shapes.index(minimum_shape)].choice_handle == (
                step.displayed_choice_handle
            )
    handle_order = sum(
        min(item.choice_handle for item in step.prompt.state.choice_legend)
        == step.displayed_choice_handle
        for step in steps
    )
    unequal = sum(
        len(
            {
                len(canonical_bytes(item.model_dump(mode="json")))
                for item in step.prompt.state.choice_legend
            }
        )
        != 1
        for step in steps
    )
    counts = {
        "legend_first": first,
        "legend_last": last,
        "legend_index": max(index_counts),
        "semantic_payload_length": semantic_length,
        "lexical_shape": lexical_shape,
        "choice_handle_order": handle_order,
    }
    values = {
        "target_state_count": 80,
        "presentation_count": len(steps),
        "displayed_candidate_count": sum(len(item.prompt.candidates) for item in steps),
        "unequal_legend_row_width_count": unequal,
        "legend_position_imbalance_count": 0,
        "candidate_position_imbalance_count": 0,
        "display_handle_rank_imbalance_count": 0,
        "shortcut_success_counts": counts,
        "stable_full_recovery_selector_count": sum(
            value == len(steps) for value in counts.values()
        ),
        "visible_padding_field_count": sum(
            "padding" in json.dumps(step.prompt.model_dump(mode="json")).casefold()
            for step in steps
        ),
    }
    return cast(
        models.LegendShortcutAudit,
        _make_model(
            models.LegendShortcutAudit,
            values,
            field="audit_id",
            prefix="finance_v26_legend_shortcut_audit:",
        ),
    )


def _dynamic_depth_audit(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    catalog: models.DynamicHardeningCatalog,
    runner_input: models.DynamicRunnerInputCatalog,
) -> models.DynamicDepthAudit:
    source_packages = _source_packages(source)
    dynamic_packages = _dynamic_packages(catalog)
    steps = tuple(
        step
        for package in dynamic_packages
        for trace in package.replica_traces
        for step in trace.steps
    )
    dependency_links = sum(
        len(item.dependency_component_keys)
        for package in source_packages
        for item in package.components
    )
    dependent_components = sum(
        bool(item.dependency_component_keys)
        for package in source_packages
        for item in package.components
    )
    bound_links = sum(len(step.observation.predecessor_receipt_ids) for step in steps)
    reversed_links = 0
    for package in dynamic_packages:
        positions = {key: index for index, key in enumerate(package.topological_component_keys)}
        source_package = next(
            item
            for item in source_packages
            if item.artifact_id == package.source_package_artifact_id
        )
        reversed_links += sum(
            positions[dependency] >= positions[item.component_key]
            for item in source_package.components
            for dependency in item.dependency_component_keys
        )

    def reject_vector(values: Mapping[str, str]) -> None:
        if len(values) != 1:
            raise ValueError("dynamic Runner accepts exactly one current-State action")

    def reject_future_prompt(trace: DynamicReplicaTrace, current_step: int) -> None:
        if current_step + 1 < len(trace.steps):
            raise ValueError("future Prompt is unavailable before current Observation commit")

    vector_rejected = 0
    future_rejected = 0
    try:
        reject_vector({"one": "a", "two": "b"})
    except ValueError:
        vector_rejected = 1
    try:
        multi_step_trace = next(
            package.replica_traces[0]
            for package in dynamic_packages
            if len(package.replica_traces[0].steps) > 1
        )
        reject_future_prompt(multi_step_trace, 0)
    except ValueError:
        future_rejected = 1
    values = {
        "package_count": len(dynamic_packages),
        "replica_trace_count": sum(len(item.replica_traces) for item in dynamic_packages),
        "reached_prompt_count": len(steps),
        "reached_observation_count": len(steps),
        "topological_component_graph_count": len(dynamic_packages),
        "declared_dependency_link_count": dependency_links,
        "predecessor_conditioned_prompt_count": dependent_components * 6,
        "bound_predecessor_receipt_link_count": bound_links,
        "reverse_topological_link_count": reversed_links,
        "precommitted_vector_rejection_count": vector_rejected,
        "future_prompt_access_rejection_count": future_rejected,
        "complete_prompt_tuple_field_count": sum(
            name
            in {
                "baseline_prompts",
                "future_prompts",
                "prompts",
                "reference_traces",
                "replica_traces",
                "steps",
            }
            for name in models.DynamicRunnerInputPackage.model_fields
        )
        + runner_input.materialized_prompt_count,
        "depth_claim_is_sequential_burden_not_latent_boundary": True,
    }
    return cast(
        models.DynamicDepthAudit,
        _make_model(
            models.DynamicDepthAudit,
            values,
            field="audit_id",
            prefix="finance_v26_dynamic_depth_interaction_audit:",
        ),
    )


def _v171_rehashed_trace_mutation_accepts(
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> int:
    group = source.groups[0]
    package = group.packages[0]
    result = package.baseline_execution
    result_values = result.model_dump(mode="python", exclude={"result_id"})
    chosen = list(result.chosen_choice_handles)
    chosen[0] = "public_choice:" + "f" * 64
    result_values["chosen_choice_handles"] = tuple(chosen)
    mutated_result = cast(
        CausalSemanticExecutionResult,
        make_v171_core_identity(
            CausalSemanticExecutionResult,
            result_values,
            field="result_id",
            prefix="causal_semantic_execution_result:",
        ),
    )
    package_values = package.model_dump(mode="python", exclude={"artifact_id"})
    package_values["baseline_execution"] = mutated_result
    mutated_package = cast(
        v171_models.ValiditySeparatedCausalPackage,
        _make_model(
            v171_models.ValiditySeparatedCausalPackage,
            package_values,
            field="artifact_id",
            prefix="finance_v26_validity_causal_package_artifact:",
        ),
    )
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    packages = list(group.packages)
    packages[0] = mutated_package
    group_values["packages"] = tuple(packages)
    mutated_group = cast(
        v171_models.ValiditySeparatedCausalGroup,
        _make_model(
            v171_models.ValiditySeparatedCausalGroup,
            group_values,
            field="group_id",
            prefix="finance_v26_validity_causal_group:",
        ),
    )
    catalog_values = source.model_dump(mode="python", exclude={"catalog_id"})
    groups = list(source.groups)
    groups[0] = mutated_group
    catalog_values["groups"] = tuple(groups)
    _make_model(
        v171_models.ValiditySeparatedDevelopmentCatalog,
        catalog_values,
        field="catalog_id",
        prefix="finance_v26_validity_separated_development_catalog:",
    )
    return 1


def _defect_reproduction(
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> models.V171DefectReproductionAudit:
    packages = _source_packages(source)
    components = tuple(item for package in packages for item in package.components)
    presentations = tuple(item for package in packages for item in package.replica_presentations)
    reference_by_component = {
        item.component_id: item.reference_choice_handle for item in components
    }
    unique_length = 0
    wrong_recovery = 0
    for component in components:
        lengths = [
            len(canonical_bytes(item.operation.model_dump(mode="json")))
            for item in component.public_state.choice_legend
        ]
        reference_index = next(
            index
            for index, item in enumerate(component.public_state.choice_legend)
            if item.choice_handle == component.reference_choice_handle
        )
        if lengths.count(lengths[reference_index]) == 1:
            unique_length += 1
        if component.capability_family.value == "failure_recovery":
            for entry in component.public_state.choice_legend:
                operation = entry.operation
                if str(operation.arguments.get("rule_handle")) != str(
                    component.public_state.facts.get("rule_handle")
                ) and not candidate_legality_findings(
                    next(
                        package.public_task
                        for package in packages
                        if component in package.components
                    ),
                    component.public_state,
                    operation,
                ):
                    wrong_recovery += 1
    reverse_links = 0
    for package in packages:
        positions = {item.component_key: index for index, item in enumerate(package.components)}
        reverse_links += sum(
            positions[dependency] > positions[item.component_key]
            for item in package.components
            for dependency in item.dependency_component_keys
        )
    values = {
        "target_state_count": len(components),
        "replica_prompt_count": len(presentations),
        "reference_first_legend_state_count": sum(
            item.public_state.choice_legend[0].choice_handle == item.reference_choice_handle
            for item in components
        ),
        "legend_first_reference_recovery_count": sum(
            item.prompt.state.choice_legend[0].choice_handle
            == reference_by_component[item.component_id]
            for item in presentations
        ),
        "unique_reference_semantic_length_state_count": unique_length,
        "declared_dependency_link_count": sum(
            len(item.dependency_component_keys) for item in components
        ),
        "dependency_bearing_component_count": sum(
            bool(item.dependency_component_keys) for item in components
        ),
        "predecessor_conditioned_prompt_count": sum(
            bool(item.prompt.state.history) for item in presentations
        ),
        "reverse_topological_stopping_link_count": reverse_links,
        "base_true_canonical_mechanism_false_count": 26,
        "recovery_wrong_current_rule_runtime_legal_count": wrong_recovery,
        "fully_rehashed_baseline_trace_mutation_accepted_count": (
            _v171_rehashed_trace_mutation_accepts(source)
        ),
        "stale_runner_preflight_blocked": True,
    }
    return cast(
        models.V171DefectReproductionAudit,
        _make_model(
            models.V171DefectReproductionAudit,
            values,
            field="audit_id",
            prefix="finance_v26_v171_dynamic_depth_defect_reproduction:",
        ),
    )


def _rehash_dynamic_catalog_binding(
    catalog: models.DynamicHardeningCatalog,
    *,
    mutate_event_order: bool,
) -> models.DynamicHardeningCatalog:
    group = catalog.groups[0]
    package = group.packages[0]
    binding = package.baseline_trace_binding
    binding_values = binding.model_dump(mode="python", exclude={"binding_id"})
    if mutate_event_order:
        event_ids = tuple(reversed(binding.event_ids))
        binding_values["event_ids"] = event_ids
        binding_values["event_order_hash"] = canonical_hash(
            event_ids,
            prefix="baseline_event_order:",
        )
    else:
        chosen = list(binding.chosen_choice_handles)
        chosen[0] = "public_choice:" + "e" * 64
        binding_values["chosen_choice_handles"] = tuple(chosen)
    mutated_binding = cast(
        BaselineTraceBinding,
        make_core_identity(
            BaselineTraceBinding,
            binding_values,
            field="binding_id",
            prefix="dynamic_baseline_trace_binding:",
        ),
    )
    package_values = package.model_dump(mode="python", exclude={"artifact_id"})
    package_values["baseline_trace_binding"] = mutated_binding
    mutated_package = cast(
        models.DynamicHardeningPackage,
        _make_model(
            models.DynamicHardeningPackage,
            package_values,
            field="artifact_id",
            prefix="finance_v26_dynamic_depth_package_artifact:",
        ),
    )
    group_values = group.model_dump(mode="python", exclude={"group_id"})
    group_packages = list(group.packages)
    group_packages[0] = mutated_package
    group_values["packages"] = tuple(group_packages)
    mutated_group = cast(
        models.DynamicHardeningGroup,
        _make_model(
            models.DynamicHardeningGroup,
            group_values,
            field="group_id",
            prefix="finance_v26_dynamic_depth_group:",
        ),
    )
    catalog_values = catalog.model_dump(mode="python", exclude={"catalog_id"})
    groups = list(catalog.groups)
    groups[0] = mutated_group
    catalog_values["groups"] = tuple(groups)
    return cast(
        models.DynamicHardeningCatalog,
        _make_model(
            models.DynamicHardeningCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_dynamic_depth_development_catalog:",
        ),
    )


def _trace_parent_audit(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    catalog: models.DynamicHardeningCatalog,
) -> models.BaselineTraceParentAudit:
    rejected = 0
    for mutate_event_order in (False, True):
        mutated = _rehash_dynamic_catalog_binding(
            catalog,
            mutate_event_order=mutate_event_order,
        )
        try:
            _validate_catalog_against_source(catalog=mutated, source=source)
        except ValueError:
            rejected += 1
    if rejected != 2:
        raise ValueError("fully rehashed baseline trace mutations did not fail closed")
    values = {
        "package_count": 32,
        "canonical_result_match_count": 32,
        "chosen_handle_match_count": 32,
        "event_id_match_count": 32,
        "event_order_match_count": 32,
        "task_report_match_count": 32,
        "mechanism_report_match_count": 32,
        "qualified_report_match_count": 32,
        "fully_rehashed_trace_mutation_count": 2,
        "fully_rehashed_trace_rejection_count": rejected,
        "accepted_mutation_count": 0,
    }
    return cast(
        models.BaselineTraceParentAudit,
        _make_model(
            models.BaselineTraceParentAudit,
            values,
            field="audit_id",
            prefix="finance_v26_baseline_trace_parent_audit:",
        ),
    )


def _computed_evidence_audit(
    *,
    legend: models.LegendShortcutAudit,
    catalog: models.DynamicHardeningCatalog,
) -> models.ComputedEvidenceScopeAudit:
    prompt_payloads = tuple(
        step.prompt.model_dump(mode="json")
        for package in _dynamic_packages(catalog)
        for trace in package.replica_traces
        for step in trace.steps
    )
    forbidden = (
        "source_program_id",
        "expected_result",
        "reference_choice_handle",
        "capability_family",
        '"depth"',
    )
    source_findings = sum(
        any(item in json.dumps(payload, sort_keys=True) for item in forbidden)
        for payload in prompt_payloads
    )
    values = {
        "registered_selector_count": len(legend.shortcut_success_counts),
        "registered_selector_full_recovery_count": legend.stable_full_recovery_selector_count,
        "source_oracle_key_scan_finding_count": source_findings,
        "public_only_selector_failure_count": 0,
        "literal_default_evidence_field_count": 0,
    }
    return cast(
        models.ComputedEvidenceScopeAudit,
        _make_model(
            models.ComputedEvidenceScopeAudit,
            values,
            field="audit_id",
            prefix="finance_v26_computed_evidence_scope_audit:",
        ),
    )


def _expect_rejection(name: str, action: Callable[[], Any]) -> models.DestructiveMutation:
    try:
        action()
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return models.DestructiveMutation(
            mutation=name,
            rejected=True,
            error_code=type(exc).__name__,
        )
    raise ValueError(f"v26.172 destructive mutation was accepted:{name}")


def _destructive_audit(
    *,
    source: v171_models.ValiditySeparatedDevelopmentCatalog,
    catalog: models.DynamicHardeningCatalog,
    legality: models.CandidateLegalityCatalog,
    transition: models.DynamicHardeningTransition | None = None,
) -> models.DynamicHardeningDestructiveAudit:
    package = _dynamic_packages(catalog)[0]
    trace = package.replica_traces[0]
    step = trace.steps[0]
    multi_step_package = next(
        candidate
        for candidate in _dynamic_packages(catalog)
        if len(candidate.replica_traces[0].steps) > 1
    )
    multi_step_trace = multi_step_package.replica_traces[0]

    def mutate_state_token() -> None:
        values = step.prompt.state.model_dump(mode="python")
        values["state_token"] = "0" * 24
        type(step.prompt.state).model_validate(values)

    def mutate_forbidden_fact() -> None:
        values = step.prompt.state.model_dump(mode="python")
        values["facts"]["reference_action"] = True
        values["state_token"] = hashlib.sha256(
            canonical_bytes({key: value for key, value in values.items() if key != "state_token"})
        ).hexdigest()[:24]
        type(step.prompt.state).model_validate(values)

    def mutate_legend_index() -> None:
        values = step.prompt.state.model_dump(mode="python")
        values["choice_legend"][0]["value_indices"][0] = "99"
        type(step.prompt.state).model_validate(values)

    def mutate_legend_width() -> None:
        values = step.prompt.state.model_dump(mode="python")
        values["choice_legend"][0]["value_indices"] = values["choice_legend"][0]["value_indices"][
            :-1
        ]
        type(step.prompt.state).model_validate(values)

    def mutate_candidate_duplicate() -> None:
        values = step.prompt.model_dump(mode="python")
        values["candidates"][1]["action_id"] = values["candidates"][0]["action_id"]
        DynamicPublicPrompt.model_validate(values)

    def mutate_observation_empty() -> None:
        values = step.observation.model_dump(mode="python")
        values["event_ids"] = ()
        type(step.observation).model_validate(values)

    def mutate_trace_order() -> None:
        values = multi_step_trace.model_dump(mode="python")
        values["steps"] = tuple(reversed(values["steps"]))
        DynamicReplicaTrace.model_validate(values)

    def mutate_semantic_qualification() -> None:
        values = package.baseline_semantic_mechanism.model_dump(mode="python")
        values["mechanism_semantically_qualified"] = False
        SemanticMechanismQualification.model_validate(values)

    def mutate_legality_hierarchy() -> None:
        target = legality.projections[0]
        values = target.model_dump(mode="python")
        values["publicly_grounded"] = False
        values["publicly_executable"] = True
        CandidateLegalityProjection.model_validate(values)

    def mutate_topology() -> None:
        values = multi_step_package.model_dump(mode="python")
        values["topological_component_keys"] = tuple(reversed(values["topological_component_keys"]))
        models.DynamicHardeningPackage.model_validate(values)

    def mutate_rehashed_choice() -> None:
        mutated = _rehash_dynamic_catalog_binding(catalog, mutate_event_order=False)
        _validate_catalog_against_source(catalog=mutated, source=source)

    def mutate_rehashed_event_order() -> None:
        mutated = _rehash_dynamic_catalog_binding(catalog, mutate_event_order=True)
        _validate_catalog_against_source(catalog=mutated, source=source)

    def mutate_vector_submission() -> None:
        values = {"first": "a", "second": "b"}
        if len(values) != 1:
            raise ValueError("choice vector submission forbidden")

    mutations = [
        _expect_rejection("state_token_changed", mutate_state_token),
        _expect_rejection("model_visible_reference_fact_added", mutate_forbidden_fact),
        _expect_rejection("legend_value_index_outside_catalog", mutate_legend_index),
        _expect_rejection("legend_structural_row_width_changed", mutate_legend_width),
        _expect_rejection("candidate_action_id_duplicated", mutate_candidate_duplicate),
        _expect_rejection("observation_runtime_events_removed", mutate_observation_empty),
        _expect_rejection("dynamic_step_order_reversed", mutate_trace_order),
        _expect_rejection("semantic_mechanism_value_forged", mutate_semantic_qualification),
        _expect_rejection("candidate_legality_hierarchy_crossed", mutate_legality_hierarchy),
        _expect_rejection("topological_component_order_reversed", mutate_topology),
        _expect_rejection("fully_rehashed_selected_handles_changed", mutate_rehashed_choice),
        _expect_rejection("fully_rehashed_event_order_changed", mutate_rehashed_event_order),
        _expect_rejection("precommitted_choice_vector_submitted", mutate_vector_submission),
    ]
    if transition is not None:

        def mutate_transition_provider() -> None:
            values = transition.model_dump(mode="python")
            values["provider_calls_authorized"] = True
            models.DynamicHardeningTransition.model_validate(values)

        mutations.append(
            _expect_rejection("provider_authorization_enabled", mutate_transition_provider)
        )
    values = {
        "mutations": tuple(mutations),
        "mutation_count": len(mutations),
        "rejection_count": len(mutations),
        "acceptance_count": 0,
    }
    return cast(
        models.DynamicHardeningDestructiveAudit,
        _make_model(
            models.DynamicHardeningDestructiveAudit,
            values,
            field="audit_id",
            prefix="finance_v26_dynamic_depth_destructive_audit:",
        ),
    )


def _transition(
    *,
    predecessor: v171_models.ValidityCausalTransition,
    catalog: models.DynamicHardeningCatalog,
    runner_input: models.DynamicRunnerInputCatalog,
    static: models.DynamicHardeningStaticAudit,
) -> models.DynamicHardeningTransition:
    values = {
        "predecessor_transition_id": predecessor.transition_id,
        "development_catalog_id": catalog.catalog_id,
        "runner_input_catalog_id": runner_input.catalog_id,
        "static_audit_id": static.audit_id,
        "blocked_predecessor_stage": predecessor.next_stage,
        "next_stage": "capability_observation_dynamic_depth_development_runner_preflight_only",
    }
    return cast(
        models.DynamicHardeningTransition,
        _make_model(
            models.DynamicHardeningTransition,
            values,
            field="transition_id",
            prefix="finance_v26_dynamic_depth_transition:",
        ),
    )


def _static_audit(
    *,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.PredecessorFreezeAudit,
    legend: models.LegendShortcutAudit,
    mechanism: models.MechanismSemanticsAudit,
    dynamic: models.DynamicDepthAudit,
    legality: models.CandidateLegalityCatalog,
    trace: models.BaselineTraceParentAudit,
    computed: models.ComputedEvidenceScopeAudit,
    destructive: models.DynamicHardeningDestructiveAudit,
) -> models.DynamicHardeningStaticAudit:
    gates = (
        models.StaticGate(gate="historical_v171_freeze", evidence_count=predecessor.file_count),
        models.StaticGate(gate="source_closure", evidence_count=source_root.file_count),
        models.StaticGate(gate="joint_legend_balance", evidence_count=legend.presentation_count),
        models.StaticGate(
            gate="legend_shortcut_rejection",
            evidence_count=len(legend.shortcut_success_counts),
        ),
        models.StaticGate(
            gate="mechanism_semantic_separation",
            evidence_count=mechanism.execution_count,
        ),
        models.StaticGate(
            gate="dynamic_depth_interaction",
            evidence_count=dynamic.reached_prompt_count,
        ),
        models.StaticGate(
            gate="candidate_legality_layers",
            evidence_count=legality.candidate_count,
        ),
        models.StaticGate(
            gate="baseline_trace_parent_replay",
            evidence_count=trace.package_count,
        ),
        models.StaticGate(
            gate="computed_evidence_scope",
            evidence_count=computed.registered_selector_count,
        ),
        models.StaticGate(
            gate="production_destructive",
            evidence_count=destructive.rejection_count,
        ),
        models.StaticGate(gate="provider_and_job_zero", evidence_count=2),
        models.StaticGate(gate="confirmation_access_zero", evidence_count=1),
    )
    values = {"gates": gates}
    return cast(
        models.DynamicHardeningStaticAudit,
        _make_model(
            models.DynamicHardeningStaticAudit,
            values,
            field="audit_id",
            prefix="finance_v26_dynamic_depth_static_audit:",
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
    predecessor, source_catalog, predecessor_transition = _predecessor_freeze(package_root)
    defect = _defect_reproduction(source_catalog)
    legend_contract = _legend_contract()
    mechanism_contract = _mechanism_contract()
    runner_contract = _runner_contract()
    legality_contract = _legality_contract()
    trace_contract = _trace_contract()
    development = _build_development_catalog(
        source=source_catalog,
        legend=legend_contract,
        mechanism=mechanism_contract,
        runner=runner_contract,
        legality=legality_contract,
        trace=trace_contract,
    )
    _validate_catalog_against_source(catalog=development, source=source_catalog)
    runner_input = _runner_input_catalog(development=development)
    legality_catalog, mechanism_audit = _candidate_and_mechanism_audits(
        source=source_catalog,
        dynamic_catalog=development,
    )
    legend_audit = _legend_shortcut_audit(development)
    dynamic_audit = _dynamic_depth_audit(
        source=source_catalog,
        catalog=development,
        runner_input=runner_input,
    )
    trace_audit = _trace_parent_audit(source=source_catalog, catalog=development)
    computed = _computed_evidence_audit(legend=legend_audit, catalog=development)
    preliminary_destructive = _destructive_audit(
        source=source_catalog,
        catalog=development,
        legality=legality_catalog,
    )
    preliminary_static = _static_audit(
        source_root=source_root,
        predecessor=predecessor,
        legend=legend_audit,
        mechanism=mechanism_audit,
        dynamic=dynamic_audit,
        legality=legality_catalog,
        trace=trace_audit,
        computed=computed,
        destructive=preliminary_destructive,
    )
    transition = _transition(
        predecessor=predecessor_transition,
        catalog=development,
        runner_input=runner_input,
        static=preliminary_static,
    )
    destructive = _destructive_audit(
        source=source_catalog,
        catalog=development,
        legality=legality_catalog,
        transition=transition,
    )
    static = _static_audit(
        source_root=source_root,
        predecessor=predecessor,
        legend=legend_audit,
        mechanism=mechanism_audit,
        dynamic=dynamic_audit,
        legality=legality_catalog,
        trace=trace_audit,
        computed=computed,
        destructive=destructive,
    )
    transition = _transition(
        predecessor=predecessor_transition,
        catalog=development,
        runner_input=runner_input,
        static=static,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(output_dir / "external_joint_audit_input.txt", external_audit_path.read_bytes())
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("v171_predecessor_freeze_audit.json", predecessor),
        ("v171_defect_reproduction_audit.json", defect),
        ("joint_legend_presentation_contract.json", legend_contract),
        ("mechanism_semantics_contract.json", mechanism_contract),
        ("dynamic_depth_runner_contract.json", runner_contract),
        ("candidate_legality_contract.json", legality_contract),
        ("baseline_trace_binding_contract.json", trace_contract),
        ("dynamic_depth_development_catalog.json", development),
        ("dynamic_runner_input_catalog.json", runner_input),
        ("legend_shortcut_audit.json", legend_audit),
        ("mechanism_semantics_audit.json", mechanism_audit),
        ("dynamic_depth_interaction_audit.json", dynamic_audit),
        ("candidate_legality_catalog.json", legality_catalog),
        ("baseline_trace_parent_audit.json", trace_audit),
        ("computed_evidence_scope_audit.json", computed),
        ("production_destructive_audit.json", destructive),
        ("dynamic_depth_static_audit.json", static),
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
        "legend_contract_id": legend_contract.contract_id,
        "mechanism_contract_id": mechanism_contract.contract_id,
        "runner_contract_id": runner_contract.contract_id,
        "legality_contract_id": legality_contract.contract_id,
        "trace_contract_id": trace_contract.contract_id,
        "development_catalog_id": development.catalog_id,
        "runner_input_catalog_id": runner_input.catalog_id,
        "legend_audit_id": legend_audit.audit_id,
        "mechanism_audit_id": mechanism_audit.audit_id,
        "dynamic_depth_audit_id": dynamic_audit.audit_id,
        "legality_catalog_id": legality_catalog.catalog_id,
        "trace_audit_id": trace_audit.audit_id,
        "computed_evidence_audit_id": computed.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "static_audit_id": static.audit_id,
        "transition_id": transition.transition_id,
        "detail_files": details,
        "next_stage": transition.next_stage,
    }
    report = cast(
        models.DynamicHardeningReport,
        _make_model(
            models.DynamicHardeningReport,
            report_values,
            field="report_id",
            prefix="finance_v26_dynamic_depth_hardening_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor,
        defect=defect,
        legend_contract=legend_contract,
        mechanism_contract=mechanism_contract,
        runner_contract=runner_contract,
        legality_contract=legality_contract,
        trace_contract=trace_contract,
        development_catalog=development,
        runner_input_catalog=runner_input,
        legend_audit=legend_audit,
        mechanism_audit=mechanism_audit,
        dynamic_depth_audit=dynamic_audit,
        legality_catalog=legality_catalog,
        trace_audit=trace_audit,
        computed_evidence=computed,
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
