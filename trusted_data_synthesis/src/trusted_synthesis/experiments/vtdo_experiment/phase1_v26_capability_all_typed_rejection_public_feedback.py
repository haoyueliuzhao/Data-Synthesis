from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task.all_typed_rejection_public_feedback import (
    ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION,
    PROHIBITED_PUBLIC_FEEDBACK_KEYS,
    PUBLIC_FEEDBACK_FIELDS,
    HostTypedRejectionBinding,
    PublicCorrectionBoundTerminal,
    PublicTypedRejectionFeedback,
    PublicTypedRejectionObservation,
    make_public_typed_rejection_feedback,
    make_public_typed_rejection_observation,
    public_feedback_identity_preimage,
    strict_public_feedback_findings,
)
from trusted_synthesis.core.task.authoritative_rejection_history_hardening import (
    TypedRejectionFeedback,
)
from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    HardenedPublicObservation,
    HardenedPublicPrompt,
    HardenedPublicState,
)
from trusted_synthesis.core.task.public_semantic_capability_depth import canonical_bytes
from trusted_synthesis.core.task.state_local_presentation_hardening import (
    StateLocalRankSchedule,
    StepRuntimeResult,
    classify_action_acceptance,
    make_identity_model,
    make_state_local_rank_schedule,
    public_only_select_hardened_action,
    topological_components,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history as v176,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history_models as v176_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_state_local_presentation_parent_hardening_models as v175_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_models as v171_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_runtime as v171_runtime,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_177_all_typed_rejection_public_feedback_closure_v3_20260829"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_177_all_typed_rejection_public_feedback_closure_v3_20260829"
)
EXPECTED_REVIEW_SHA256: Final = "44f482f292a1925e2b5942ea0ca5345565f6c4089f833c690ca8e9991be28ce0"
EXPECTED_REVIEW_BYTE_COUNT: Final = 17_882
V176_DIR: Final = v176.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/all_typed_rejection_public_feedback.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_all_typed_rejection_public_feedback_runtime.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_all_typed_rejection_public_feedback_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_all_typed_rejection_public_feedback.py",
)
PRODUCTION_REJECTION_REGISTRY: Final = (
    {
        "capability_family": "failure_recovery",
        "decision_kind": "revise_selector",
        "rejection_code": "typed_current_state_target_mismatch",
        "choice_count": 3,
        "exact_catalog": True,
    },
    {
        "capability_family": "failure_recovery",
        "decision_kind": "revise_selector",
        "rejection_code": "typed_failure_receipt_mismatch",
        "choice_count": 3,
        "exact_catalog": False,
    },
    {
        "capability_family": "semantic_reconciliation",
        "decision_kind": "reconcile_record",
        "rejection_code": "typed_current_state_target_mismatch",
        "choice_count": 3,
        "exact_catalog": False,
    },
    {
        "capability_family": "semantic_reconciliation",
        "decision_kind": "consume_normalized_output",
        "rejection_code": "typed_current_state_target_mismatch",
        "choice_count": 2,
        "exact_catalog": False,
    },
    {
        "capability_family": "state_dependent_stopping",
        "decision_kind": "assess_dynamic_readiness",
        "rejection_code": "typed_current_state_target_mismatch",
        "choice_count": 3,
        "exact_catalog": False,
    },
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.177 cannot resolve the trusted_data_synthesis package root")


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
        raise ValueError(f"v26.177 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.177 immutable output already exists:{path}")
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
        raise ValueError("v26.177 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.177 external audit byte count does not match Authorization")
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
            prefix="finance_v26_all_typed_rejection_external_authorization:",
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
            imported_path = _module_path(package_root, imported)
            if imported_path is None:
                unresolved.add(imported)
            elif imported not in visited:
                pending.append(imported)
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=relative,
            source_kind="implementation_source",
        )
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
                "unresolved_imports": tuple(sorted(unresolved)),
                "unresolved_import_count": len(unresolved),
            },
            field="root_id",
            prefix="finance_v26_all_typed_rejection_transitive_source_root:",
        ),
    )


def _v171_packages(
    catalog: v171_models.ValiditySeparatedDevelopmentCatalog,
) -> tuple[v171_models.ValiditySeparatedCausalPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


def _development_packages(
    catalog: v176_models.AuthoritativeDevelopmentCatalog,
) -> tuple[v176_models.AuthoritativeDevelopmentPackage, ...]:
    return tuple(item for group in catalog.groups for item in group.packages)


@dataclass(frozen=True)
class PredecessorObjects:
    report: v176_models.HardeningReport
    transition: v176_models.ProspectiveTransition
    development: v176_models.AuthoritativeDevelopmentCatalog
    runner: v176_models.AuthoritativeRunnerInputCatalog
    schedules: v175_models.StateLocalScheduleCatalog
    source: v171_models.ValiditySeparatedDevelopmentCatalog


def _predecessor_freeze(
    package_root: Path,
) -> tuple[models.V176PredecessorFreezeAudit, PredecessorObjects]:
    source_dir = package_root / V176_DIR
    paths = tuple(sorted(path for path in source_dir.iterdir() if path.is_file()))
    if len(paths) != 16:
        raise ValueError("v26.176 authoritative formal directory is not exactly 16 files")
    report = v176_models.HardeningReport.model_validate(_load(source_dir / "report.json"))
    transition = v176_models.ProspectiveTransition.model_validate(
        _load(source_dir / "prospective_transition_contract.json")
    )
    development = v176_models.AuthoritativeDevelopmentCatalog.model_validate(
        _load(source_dir / "authoritative_development_catalog.json")
    )
    runner = v176_models.AuthoritativeRunnerInputCatalog.model_validate(
        _load(source_dir / "authoritative_runner_input_catalog.json")
    )
    if transition.next_stage != models.BLOCKED_PREDECESSOR_STAGE:
        raise ValueError("v26.176 next stage differs from the audited blocked preflight")
    with tempfile.TemporaryDirectory(prefix="finance-v26-177-v176-rebuild-") as temporary:
        rebuild_dir = Path(temporary)
        v176.build(
            package_root=package_root,
            output_dir=rebuild_dir,
            external_audit_path=source_dir / "external_parent_history_audit_input.txt",
        )
        rebuilt = tuple(sorted(path for path in rebuild_dir.iterdir() if path.is_file()))
        if len(rebuilt) != len(paths):
            raise ValueError("v26.176 independent rebuild file count differs")
        for source_path in paths:
            candidate = rebuild_dir / source_path.name
            if not candidate.is_file() or source_path.read_bytes() != candidate.read_bytes():
                raise ValueError(f"v26.176 independent rebuild differs:{source_path.name}")
    schedules = v175_models.StateLocalScheduleCatalog.model_validate(
        _load(package_root / v176.V175_DIR / "state_local_schedule_catalog.json")
    )
    source = v171_models.ValiditySeparatedDevelopmentCatalog.model_validate(
        _load(package_root / v176.V171_DIR / "validity_separated_development_catalog.json")
    )
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=f"{V176_DIR}/{path.name}",
            source_kind="predecessor_artifact",
        )
        for path in paths
    )
    audit = cast(
        models.V176PredecessorFreezeAudit,
        _make_model(
            models.V176PredecessorFreezeAudit,
            {
                "predecessor_report_id": report.report_id,
                "predecessor_transition_id": transition.transition_id,
                "predecessor_files": bindings,
                "blocked_runner_preflight_transition": models.BLOCKED_PREDECESSOR_STAGE,
            },
            field="audit_id",
            prefix="finance_v26_v176_predecessor_freeze_audit:",
        ),
    )
    return audit, PredecessorObjects(
        report=report,
        transition=transition,
        development=development,
        runner=runner,
        schedules=schedules,
        source=source,
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


def _schedule_mapping(
    *,
    package: v176_models.AuthoritativeDevelopmentPackage,
    source: v171_models.ValiditySeparatedCausalPackage,
    schedule_catalog: v175_models.StateLocalScheduleCatalog,
) -> dict[str, StateLocalRankSchedule]:
    schedules_by_id = {item.schedule_id: item for item in schedule_catalog.schedules}
    ordered = topological_components(source.components)
    return {
        component.component_key: schedules_by_id[schedule_id]
        for component, schedule_id in zip(ordered, package.schedule_ids, strict=True)
    }


def _state_at_component(
    *,
    package: v176_models.AuthoritativeDevelopmentPackage,
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
        if (
            not isinstance(observation, HardenedPublicObservation)
            or not observation.action_accepted
        ):
            raise ValueError("v26.177 reference prefix did not commit one exact Action")
    return state


def _finish_reference(state: step_runtime.StepRuntimeState) -> StepRuntimeResult:
    while state.current_index < len(state.ordered_components):
        prompt = step_runtime.render_next_prompt(state)
        observation = step_runtime.step(state, public_only_select_hardened_action(prompt))
        if (
            not isinstance(observation, HardenedPublicObservation)
            or not observation.action_accepted
        ):
            raise ValueError("v26.177 reference suffix did not commit")
    return step_runtime.finalize(state)


def _retry_count(events: Sequence[Any]) -> int:
    return sum(
        item.event_type in {"recovery_succeeded", "recovery_retry_failed"} for item in events
    )


def _candidate_acceptances(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
) -> tuple[tuple[Any, str, Any], ...]:
    mapping = state.pending_source_by_display
    if mapping is None:
        raise ValueError("v26.177 Runtime lost its exact display/source mapping")
    component = state.ordered_components[state.current_index]
    output: list[tuple[Any, str, Any]] = []
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
        output.append((candidate, source_handle, acceptance))
    return tuple(output)


def _replace_prompt_failure_receipt(
    prompt: HardenedPublicPrompt,
    failure_receipt: Any,
) -> HardenedPublicPrompt:
    state_values = {
        "decision_kind": prompt.state.decision_kind,
        "tool_id": prompt.state.tool_id,
        "facts": prompt.state.facts,
        "argument_fields": prompt.state.argument_fields,
        "argument_value_catalogs": prompt.state.argument_value_catalogs,
        "choice_legend": prompt.state.choice_legend,
        "prior_observations": prompt.state.prior_observations,
        "failure_receipt": failure_receipt,
        "schema_version": prompt.state.schema_version,
    }
    provisional = HardenedPublicState.model_construct(state_token="0" * 24, **state_values)
    visible = provisional.model_dump(mode="json", exclude={"state_token"})
    state = HardenedPublicState(
        state_token=hashlib.sha256(canonical_bytes(visible)).hexdigest()[:24],
        **state_values,
    )
    payload = {
        "task": prompt.task.model_dump(mode="json"),
        "state": state.model_dump(mode="json"),
        "candidates": [item.model_dump(mode="json") for item in prompt.candidates],
    }
    rendered = canonical_bytes(payload)
    return HardenedPublicPrompt(
        prompt_hash=hashlib.sha256(rendered).hexdigest(),
        rendered_bytes=len(rendered),
        task=prompt.task,
        state=state,
        candidates=prompt.candidates,
    )


def _mismatched_failure_receipt(prompt: HardenedPublicPrompt) -> Any:
    receipt = prompt.state.failure_receipt
    if receipt is None:
        raise ValueError("failure-Receipt mismatch control has no exact Receipt")
    values = receipt.model_dump(mode="python", exclude={"receipt_id"})
    values["source_tool_id"] = f"{receipt.source_tool_id}:registered_control"
    return make_identity_model(
        type(receipt),
        values,
        field="receipt_id",
        prefix="exact_public_failure_receipt:",
    )


def _precondition_control_component(component: Any, task: Any) -> Any:
    decision = component.public_state.decision_kind
    if decision not in {
        "reconcile_record",
        "consume_normalized_output",
        "assess_dynamic_readiness",
    }:
        raise ValueError(f"unsupported precondition control Decision:{decision}")
    entries = list(component.public_state.choice_legend)
    target_index = next(
        index
        for index, item in enumerate(entries)
        if item.choice_handle != component.reference_choice_handle
    )
    target = entries[target_index]
    arguments = dict(target.operation.arguments)
    if decision == "reconcile_record":
        rules = tuple(item.rule_handle for item in task.semantic_task.resolution_rules)
        operations = tuple(item.operation_handle for item in task.semantic_task.operations)
        replacements = tuple(
            ("rule_handle", item) for item in rules if item != str(arguments.get("rule_handle"))
        ) + tuple(
            ("operation_handle", item)
            for item in operations
            if item != str(arguments.get("operation_handle"))
        )
        if not replacements:
            raise ValueError("Reconciliation control has no grounded mismatching parent")
        field_name, replacement = replacements[0]
        arguments[field_name] = replacement
    elif decision == "consume_normalized_output":
        arguments["input_symbol"] = (
            f"{arguments.get('input_symbol', 'public_symbol')}:registered_control"
        )
    else:
        arguments["assertion"] = (
            f"{arguments.get('assertion', 'public_assertion')}:registered_control"
        )
    operation = target.operation.model_copy(update={"arguments": arguments})
    entries[target_index] = target.model_copy(update={"operation": operation})
    public_state = component.public_state.model_copy(update={"choice_legend": tuple(entries)})
    return component.model_copy(update={"public_state": public_state})


def _prepare_control_state(
    *,
    package: v176_models.AuthoritativeDevelopmentPackage,
    source: v171_models.ValiditySeparatedCausalPackage,
    core: Any,
    schedules: Mapping[str, StateLocalRankSchedule],
    component_key: str,
    replica_index: int,
    rejection_code: str,
) -> tuple[step_runtime.StepRuntimeState, HardenedPublicPrompt, str, str, Any]:
    state = _state_at_component(
        package=package,
        source=source,
        core=core,
        schedules=schedules,
        component_key=component_key,
        replica_index=replica_index,
    )
    component = state.ordered_components[state.current_index]
    decision = component.public_state.decision_kind
    if decision in {
        "reconcile_record",
        "consume_normalized_output",
        "assess_dynamic_readiness",
    }:
        replacement = _precondition_control_component(component, state.runtime_input.public_task)
        ordered = list(state.ordered_components)
        ordered[state.current_index] = replacement
        state.ordered_components = tuple(ordered)
        old_schedule = state.schedules_by_component[component.component_key]
        state.schedules_by_component[component.component_key] = make_state_local_rank_schedule(
            schedule_contract_id=old_schedule.schedule_contract_id,
            source_package_artifact_id=old_schedule.source_package_artifact_id,
            component=replacement,
            derivation_nonce=old_schedule.derivation_nonce + 100_000,
        )
    prompt = step_runtime.render_next_prompt(state)
    if rejection_code == "typed_failure_receipt_mismatch":
        prompt = _replace_prompt_failure_receipt(
            prompt,
            _mismatched_failure_receipt(prompt),
        )
        state.pending_prompt = prompt
    reports = _candidate_acceptances(state, prompt)
    rejected = tuple(item for item in reports if item[2].rejection_code == rejection_code)
    if not rejected:
        raise ValueError(
            f"registered production rejection control is unreachable:{decision}:{rejection_code}"
        )
    if rejection_code == "typed_failure_receipt_mismatch":
        reference_action = public_only_select_hardened_action(
            _replace_prompt_failure_receipt(prompt, state.failure_receipts[component_key])
        )
        selected = next(item for item in rejected if item[0].action_id == reference_action)
    else:
        selected = rejected[0]
    if not selected[2].publicly_grounded or not selected[2].publicly_executable:
        raise ValueError("production rejection control conflates legality with precondition")
    return state, prompt, selected[0].action_id, selected[1], selected[2]


def _scalar_strings(value: Any) -> set[str]:
    output: set[str] = set()
    if isinstance(value, Mapping):
        for item in value.values():
            output.update(_scalar_strings(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            output.update(_scalar_strings(item))
    elif isinstance(value, str):
        output.add(value)
    return output


def _independent_public_projection_matches(
    *,
    observation: PublicTypedRejectionObservation,
    feedback: PublicTypedRejectionFeedback,
) -> bool:
    observation_values = {
        "public_state_token": observation.public_state_token,
        "public_rejected_action_id": observation.public_rejected_action_id,
        "public_displayed_choice_handle": observation.public_displayed_choice_handle,
        "public_rejection_code": observation.public_rejection_code,
        "correction_attempt_index": observation.correction_attempt_index,
        "correction_attempt_bound": observation.correction_attempt_bound,
        "action_committed": False,
        "schema_version": ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION,
    }
    independent_observation_id = canonical_hash(
        observation_values,
        prefix="public_typed_rejection_observation:",
    )
    feedback_values = {
        "public_rejected_action_id": observation.public_rejected_action_id,
        "public_displayed_choice_handle": observation.public_displayed_choice_handle,
        "public_rejection_code": observation.public_rejection_code,
        "public_observation_receipt_id": independent_observation_id,
        "correction_attempt_index": observation.correction_attempt_index,
        "correction_attempt_bound": observation.correction_attempt_bound,
        "predecessor_public_feedback_id": feedback.predecessor_public_feedback_id,
        "schema_version": ALL_TYPED_REJECTION_PUBLIC_FEEDBACK_VERSION,
    }
    independent_feedback_id = canonical_hash(
        feedback_values,
        prefix="public_typed_rejection_feedback:",
    )
    return bool(
        independent_observation_id == observation.public_observation_receipt_id
        and independent_feedback_id == feedback.feedback_id
        and public_feedback_identity_preimage(feedback) == canonical_bytes(feedback_values)
    )


def _prompt_hidden_exposure_counts(
    *,
    baseline_prompt: HardenedPublicPrompt,
    prompt: HardenedPublicPrompt,
    host_binding: HostTypedRejectionBinding,
) -> tuple[int, int]:
    prompt_scalars = _scalar_strings(prompt.model_dump(mode="json"))
    baseline_scalars = _scalar_strings(baseline_prompt.model_dump(mode="json"))
    added_scalars = prompt_scalars - baseline_scalars
    host_values = {
        host_binding.binding_id,
        host_binding.package_id,
        host_binding.component_key,
        host_binding.source_choice_handle,
        host_binding.selected_operation_hash,
        host_binding.action_acceptance_report_id,
        *host_binding.runtime_event_ids,
    }
    direct = len(added_scalars & host_values)
    derived_values = {hashlib.sha256(canonical_bytes(item)).hexdigest() for item in host_values}
    derived_values.update(
        canonical_hash(item, prefix=prefix)
        for item in host_values
        for prefix in (
            "state_bound_action_acceptance_report:",
            "selected_runtime_operation:",
            "host_typed_rejection_binding:",
        )
    )
    derived = len(added_scalars & derived_values)
    return direct, derived


@dataclass(frozen=True)
class ControlAuditProducts:
    surface: models.ProductionRejectionSurfaceCatalog
    projection: models.PublicFeedbackProjectionAudit
    sample_feedback: PublicTypedRejectionFeedback
    sample_observation: PublicTypedRejectionObservation
    sample_host_binding: HostTypedRejectionBinding
    sample_recovery_prompt: HardenedPublicPrompt
    sample_terminal: PublicCorrectionBoundTerminal


def _production_rejection_and_projection_audits(
    predecessor: PredecessorObjects,
) -> ControlAuditProducts:
    source_by_artifact = {item.artifact_id: item for item in _v171_packages(predecessor.source)}
    core_by_id = {item.core_id: item for item in predecessor.source.finance_cores}
    packages = _development_packages(predecessor.development)
    projection_rows: list[models.PublicFeedbackProjectionRow] = []
    surface_rows: list[models.ProductionRejectionKindRow] = []
    samples: (
        tuple[
            PublicTypedRejectionFeedback,
            PublicTypedRejectionObservation,
            HostTypedRejectionBinding,
            HardenedPublicPrompt,
            PublicCorrectionBoundTerminal,
        ]
        | None
    ) = None

    for registration in PRODUCTION_REJECTION_REGISTRY:
        decision_kind = str(registration["decision_kind"])
        rejection_code = str(registration["rejection_code"])
        matching: list[
            tuple[
                v176_models.AuthoritativeDevelopmentPackage,
                v171_models.ValiditySeparatedCausalPackage,
                Any,
                Mapping[str, StateLocalRankSchedule],
                Any,
            ]
        ] = []
        for package in packages:
            source = source_by_artifact[package.source_v171_package_artifact_id]
            schedule_map = _schedule_mapping(
                package=package,
                source=source,
                schedule_catalog=predecessor.schedules,
            )
            for component in topological_components(source.components):
                if component.public_state.decision_kind == decision_kind:
                    matching.append(
                        (
                            package,
                            source,
                            core_by_id[source.finance_core_id],
                            schedule_map,
                            component,
                        )
                    )
        if not matching:
            raise ValueError(f"production Decision kind is absent:{decision_kind}")
        fixture_count = 0
        for package, source, core, bound_schedules, component in matching:
            for replica_index in range(6):
                state, initial_prompt, invalid_action, source_handle, acceptance = (
                    _prepare_control_state(
                        package=package,
                        source=source,
                        core=core,
                        schedules=bound_schedules,
                        component_key=component.component_key,
                        replica_index=replica_index,
                        rejection_code=rejection_code,
                    )
                )
                before_index = state.current_index
                before_tools = state.local_tool_invocation_count
                before_retries = _retry_count(state.events)
                first = step_runtime.step(state, invalid_action)
                if not isinstance(first, PublicTypedRejectionObservation):
                    raise ValueError("production control did not emit a public rejection")
                feedback = state.public_feedback_by_component[component.component_key][0]
                host_binding = state.host_rejection_bindings_by_component[component.component_key][
                    0
                ]
                if (
                    state.current_index != before_index
                    or state.local_tool_invocation_count != before_tools
                    or _retry_count(state.events) != before_retries
                ):
                    raise ValueError("production rejection control committed Runtime behavior")
                recovery_prompt = step_runtime.render_next_prompt(state)
                visible_feedback = recovery_prompt.state.facts.get(
                    "public_typed_rejection_feedback"
                )
                if visible_feedback != (feedback.model_dump(mode="json"),):
                    raise ValueError("recovery Prompt does not bind exact public Feedback")
                independent = _independent_public_projection_matches(
                    observation=first,
                    feedback=feedback,
                )
                direct_hidden, derived_hidden = _prompt_hidden_exposure_counts(
                    baseline_prompt=initial_prompt,
                    prompt=recovery_prompt,
                    host_binding=host_binding,
                )
                prohibited = len(
                    strict_public_feedback_findings(
                        recovery_prompt.state.facts.get("public_typed_rejection_feedback")
                    )
                )
                exact_schema = tuple(type(feedback).model_fields) == PUBLIC_FEEDBACK_FIELDS
                if not independent or direct_hidden or derived_hidden or prohibited:
                    raise ValueError(
                        "public Feedback projection is not Host-independent:"
                        f"{decision_kind}:{rejection_code}:{replica_index}:"
                        f"{independent}:{direct_hidden}:{derived_hidden}:{prohibited}"
                    )
                projection_rows.append(
                    cast(
                        models.PublicFeedbackProjectionRow,
                        _make_model(
                            models.PublicFeedbackProjectionRow,
                            {
                                "package_id": package.package_id,
                                "component_key": component.component_key,
                                "capability_family": source.capability_family.value,
                                "decision_kind": decision_kind,
                                "rejection_code": rejection_code,
                                "replica_index": replica_index,
                                "fixture_kind": (
                                    "exact_catalog"
                                    if registration["exact_catalog"]
                                    else "registered_control"
                                ),
                                "host_binding_id": host_binding.binding_id,
                                "public_observation_receipt_id": (
                                    first.public_observation_receipt_id
                                ),
                                "public_feedback_id": feedback.feedback_id,
                                "recovery_prompt_hash": recovery_prompt.prompt_hash,
                                "exact_public_schema_match": exact_schema,
                                "independent_projection_match": independent,
                                "host_counterfactual_invariant": independent,
                                "identity_preimage_public_only": independent,
                                "prohibited_key_count": prohibited,
                                "direct_hidden_scalar_exposure_count": direct_hidden,
                                "derived_host_identity_exposure_count": derived_hidden,
                            },
                            field="row_id",
                            prefix="public_typed_rejection_feedback_projection_row:",
                        ),
                    )
                )
                corrected = step_runtime.step(
                    state,
                    public_only_select_hardened_action(recovery_prompt),
                )
                if (
                    not isinstance(corrected, HardenedPublicObservation)
                    or not corrected.action_accepted
                    or state.current_index != before_index + 1
                ):
                    raise ValueError("reference correction did not commit exactly once")

                repeated, _, repeated_action, _, _ = _prepare_control_state(
                    package=package,
                    source=source,
                    core=core,
                    schedules=bound_schedules,
                    component_key=component.component_key,
                    replica_index=replica_index,
                    rejection_code=rejection_code,
                )
                repeated_first = step_runtime.step(repeated, repeated_action)
                if not isinstance(repeated_first, PublicTypedRejectionObservation):
                    raise ValueError("repeated-invalid control lost its first rejection")
                repeated_prompt = step_runtime.render_next_prompt(repeated)
                if rejection_code == "typed_failure_receipt_mismatch":
                    repeated.pending_prompt = _replace_prompt_failure_receipt(
                        repeated_prompt,
                        _mismatched_failure_receipt(repeated_prompt),
                    )
                terminal = step_runtime.step(repeated, repeated_action)
                if not isinstance(terminal, PublicCorrectionBoundTerminal):
                    raise ValueError("repeated invalid response did not terminalize")
                later_prompt = 0
                try:
                    step_runtime.render_next_prompt(repeated)
                except step_runtime.CorrectionBoundTerminalReached:
                    pass
                else:
                    later_prompt = 1
                if later_prompt:
                    raise ValueError("repeated invalid response exposed a third Prompt")
                fixture_count += 1
                if samples is None:
                    samples = (
                        feedback,
                        first,
                        host_binding,
                        recovery_prompt,
                        terminal,
                    )
        exact_count = fixture_count if registration["exact_catalog"] else 0
        surface_rows.append(
            cast(
                models.ProductionRejectionKindRow,
                _make_model(
                    models.ProductionRejectionKindRow,
                    {
                        "capability_family": registration["capability_family"],
                        "decision_kind": decision_kind,
                        "rejection_code": rejection_code,
                        "choice_count": registration["choice_count"],
                        "production_component_count": len(matching),
                        "exact_catalog_rejection_state_count": exact_count,
                        "exact_catalog_status": (
                            "reachable"
                            if registration["exact_catalog"]
                            else "registered_but_unreachable"
                        ),
                        "control_fixture_count": fixture_count,
                        "control_rejection_count": fixture_count,
                        "public_projection_match_count": fixture_count,
                        "reference_correction_accept_count": fixture_count,
                        "repeated_invalid_terminal_count": fixture_count,
                    },
                    field="row_id",
                    prefix="production_typed_rejection_kind_row:",
                ),
            )
        )

    if samples is None:
        raise ValueError("production rejection control produced no sample")
    surface = cast(
        models.ProductionRejectionSurfaceCatalog,
        _make_model(
            models.ProductionRejectionSurfaceCatalog,
            {
                "rows": tuple(surface_rows),
            },
            field="catalog_id",
            prefix="finance_v26_production_typed_rejection_surface_catalog:",
        ),
    )
    projection = cast(
        models.PublicFeedbackProjectionAudit,
        _make_model(
            models.PublicFeedbackProjectionAudit,
            {
                "rows": tuple(projection_rows),
            },
            field="audit_id",
            prefix="finance_v26_public_typed_rejection_feedback_projection_audit:",
        ),
    )
    return ControlAuditProducts(
        surface=surface,
        projection=projection,
        sample_feedback=samples[0],
        sample_observation=samples[1],
        sample_host_binding=samples[2],
        sample_recovery_prompt=samples[3],
        sample_terminal=samples[4],
    )


@dataclass(frozen=True)
class ExactRejectionDescriptor:
    package: v176_models.AuthoritativeDevelopmentPackage
    source: v171_models.ValiditySeparatedCausalPackage
    core: Any
    schedules: Mapping[str, StateLocalRankSchedule]
    component_key: str
    replica_index: int
    invalid_action_id: str
    invalid_source_choice_handle: str
    reference_source_choice_handle: str
    nonreference_valid_source_choice_handle: str
    current_action_ids: tuple[str, ...]


def _exact_rejection_descriptors(
    predecessor: PredecessorObjects,
) -> tuple[ExactRejectionDescriptor, ...]:
    source_by_artifact = {item.artifact_id: item for item in _v171_packages(predecessor.source)}
    core_by_id = {item.core_id: item for item in predecessor.source.finance_cores}
    descriptors: list[ExactRejectionDescriptor] = []
    for package in _development_packages(predecessor.development):
        source = source_by_artifact[package.source_v171_package_artifact_id]
        schedules = _schedule_mapping(
            package=package,
            source=source,
            schedule_catalog=predecessor.schedules,
        )
        for component in topological_components(source.components):
            if component.public_state.decision_kind != "revise_selector":
                continue
            for replica_index in range(6):
                state = _state_at_component(
                    package=package,
                    source=source,
                    core=core_by_id[source.finance_core_id],
                    schedules=schedules,
                    component_key=component.component_key,
                    replica_index=replica_index,
                )
                prompt = step_runtime.render_next_prompt(state)
                reports = _candidate_acceptances(state, prompt)
                rejected = tuple(
                    item
                    for item in reports
                    if item[2].rejection_code == "typed_current_state_target_mismatch"
                )
                accepted = tuple(item for item in reports if item[2].accepted)
                if len(rejected) != 1 or len(accepted) != 2:
                    raise ValueError("exact Recovery rejection/acceptance surface changed")
                reference_action = public_only_select_hardened_action(prompt)
                reference = next(item for item in accepted if item[0].action_id == reference_action)
                nonreference = next(
                    item for item in accepted if item[0].action_id != reference_action
                )
                descriptors.append(
                    ExactRejectionDescriptor(
                        package=package,
                        source=source,
                        core=core_by_id[source.finance_core_id],
                        schedules=schedules,
                        component_key=component.component_key,
                        replica_index=replica_index,
                        invalid_action_id=rejected[0][0].action_id,
                        invalid_source_choice_handle=rejected[0][1],
                        reference_source_choice_handle=reference[1],
                        nonreference_valid_source_choice_handle=nonreference[1],
                        current_action_ids=tuple(item.action_id for item in prompt.candidates),
                    )
                )
    if len(descriptors) != 120:
        raise ValueError("exact typed-rejection descriptor denominator changed")
    return tuple(descriptors)


@dataclass(frozen=True)
class InitialRejectionExecution:
    state: step_runtime.StepRuntimeState
    recovery_prompt: HardenedPublicPrompt
    feedback: PublicTypedRejectionFeedback
    initial_retry_delta: int
    initial_tool_delta: int
    initial_component_advance_count: int


def _initial_exact_rejection(
    descriptor: ExactRejectionDescriptor,
) -> InitialRejectionExecution:
    state = _state_at_component(
        package=descriptor.package,
        source=descriptor.source,
        core=descriptor.core,
        schedules=descriptor.schedules,
        component_key=descriptor.component_key,
        replica_index=descriptor.replica_index,
    )
    prompt = step_runtime.render_next_prompt(state)
    if descriptor.invalid_action_id not in {item.action_id for item in prompt.candidates}:
        raise ValueError("exact invalid Action changed across deterministic replay")
    before_retry = _retry_count(state.events)
    before_tools = state.local_tool_invocation_count
    before_index = state.current_index
    observation = step_runtime.step(state, descriptor.invalid_action_id)
    if not isinstance(observation, PublicTypedRejectionObservation):
        raise ValueError("exact initial invalid Action did not emit public rejection")
    retry_delta = _retry_count(state.events) - before_retry
    tool_delta = state.local_tool_invocation_count - before_tools
    advance = state.current_index - before_index
    if retry_delta or tool_delta or advance:
        raise ValueError("exact initial rejection committed Runtime behavior")
    recovery_prompt = step_runtime.render_next_prompt(state)
    feedback = state.public_feedback_by_component[descriptor.component_key][0]
    return InitialRejectionExecution(
        state=state,
        recovery_prompt=recovery_prompt,
        feedback=feedback,
        initial_retry_delta=retry_delta,
        initial_tool_delta=tool_delta,
        initial_component_advance_count=advance,
    )


def _action_for_source_handle(
    state: step_runtime.StepRuntimeState,
    prompt: HardenedPublicPrompt,
    source_handle: str,
) -> str:
    mapping = state.pending_source_by_display
    if mapping is None:
        raise ValueError("v26.177 action lookup lost display/source mapping")
    matches = tuple(
        item.action_id for item in prompt.candidates if mapping[item.choice_handle] == source_handle
    )
    if len(matches) != 1:
        raise ValueError("v26.177 source handle does not resolve to one public Action")
    return matches[0]


def _validity_tuple(result: StepRuntimeResult) -> tuple[bool, bool, bool]:
    return (
        result.task_validity.base_valid,
        result.mechanism_qualification.mechanism_semantically_qualified,
        result.qualified_validity.qualified_valid,
    )


def _matrix_row(
    values: dict[str, Any],
) -> models.CorrectionMatrixRow:
    return cast(
        models.CorrectionMatrixRow,
        _make_model(
            models.CorrectionMatrixRow,
            values,
            field="row_id",
            prefix="bounded_correction_matrix_row:",
        ),
    )


def _base_matrix_values(
    descriptor: ExactRejectionDescriptor,
    execution: InitialRejectionExecution,
    disposition: str,
) -> dict[str, Any]:
    return {
        "package_id": descriptor.package.package_id,
        "component_key": descriptor.component_key,
        "capability_family": descriptor.source.capability_family.value,
        "decision_kind": "revise_selector",
        "rejection_code": "typed_current_state_target_mismatch",
        "choice_count": 3,
        "replica_index": descriptor.replica_index,
        "first_rejected_action_id": descriptor.invalid_action_id,
        "first_public_feedback_id": execution.feedback.feedback_id,
        "disposition": disposition,
    }


def _assert_no_later_correction_prompt(state: step_runtime.StepRuntimeState) -> None:
    try:
        step_runtime.render_next_prompt(state)
    except step_runtime.CorrectionBoundTerminalReached:
        return
    raise ValueError("bounded-correction terminal exposed a later Prompt")


def _registered_foreign_action(
    descriptor: ExactRejectionDescriptor,
    descriptors: Sequence[ExactRejectionDescriptor],
) -> str:
    for other in descriptors:
        if other.package.package_id != descriptor.package.package_id:
            for action_id in other.current_action_ids:
                if action_id not in descriptor.current_action_ids:
                    return action_id
    raise ValueError("exact correction Matrix cannot locate a foreign registered Action")


def _malformed_abi_valid_action(
    descriptor: ExactRejectionDescriptor,
    registered_action_ids: set[str],
) -> str:
    nonce = 0
    while True:
        value = hashlib.sha256(
            (
                f"v26.177|malformed-abi-valid|{descriptor.package.package_id}|"
                f"{descriptor.component_key}|{descriptor.replica_index}|{nonce}"
            ).encode()
        ).hexdigest()[:24]
        if value not in registered_action_ids:
            return value
        nonce += 1


def _correction_bound_matrix_audit(
    predecessor: PredecessorObjects,
) -> models.CorrectionBoundMatrixAudit:
    descriptors = _exact_rejection_descriptors(predecessor)
    registered_action_ids = {
        action_id for item in descriptors for action_id in item.current_action_ids
    }
    rows: list[models.CorrectionMatrixRow] = []
    for descriptor in descriptors:
        reference = _initial_exact_rejection(descriptor)
        reference_action = _action_for_source_handle(
            reference.state,
            reference.recovery_prompt,
            descriptor.reference_source_choice_handle,
        )
        before_index = reference.state.current_index
        reference_observation = step_runtime.step(reference.state, reference_action)
        if (
            not isinstance(reference_observation, HardenedPublicObservation)
            or not reference_observation.action_accepted
            or reference.state.current_index != before_index + 1
        ):
            raise ValueError("reference-valid correction did not commit exactly once")
        reference_result = _finish_reference(reference.state)
        reference_validity = _validity_tuple(reference_result)
        rows.append(
            _matrix_row(
                {
                    **_base_matrix_values(descriptor, reference, "reference_valid"),
                    "availability": "executed",
                    "second_action_id": reference_action,
                    "second_outcome": "accepted",
                    "corrected_action_accepted": True,
                    "component_commit_count": 1,
                    "later_correction_prompt_count": 0,
                    "retry_delta": reference.initial_retry_delta,
                    "tool_call_delta": reference.initial_tool_delta,
                    "rejection_component_advance_count": (
                        reference.initial_component_advance_count
                    ),
                    "final_result_id": reference_result.result_id,
                    "final_base_valid": reference_validity[0],
                    "final_mechanism_qualified": reference_validity[1],
                    "final_qualified_valid": reference_validity[2],
                    "complete_rejection_lineage_bound": True,
                }
            )
        )

        nonreference = _initial_exact_rejection(descriptor)
        nonreference_action = _action_for_source_handle(
            nonreference.state,
            nonreference.recovery_prompt,
            descriptor.nonreference_valid_source_choice_handle,
        )
        before_index = nonreference.state.current_index
        corrected_observation = step_runtime.step(nonreference.state, nonreference_action)
        if (
            not isinstance(corrected_observation, HardenedPublicObservation)
            or not corrected_observation.action_accepted
            or nonreference.state.current_index != before_index + 1
        ):
            raise ValueError("nonreference-valid correction did not commit exactly once")
        corrected_result = _finish_reference(nonreference.state)

        direct_state = _state_at_component(
            package=descriptor.package,
            source=descriptor.source,
            core=descriptor.core,
            schedules=descriptor.schedules,
            component_key=descriptor.component_key,
            replica_index=descriptor.replica_index,
        )
        direct_prompt = step_runtime.render_next_prompt(direct_state)
        direct_action = _action_for_source_handle(
            direct_state,
            direct_prompt,
            descriptor.nonreference_valid_source_choice_handle,
        )
        direct_observation = step_runtime.step(direct_state, direct_action)
        if not isinstance(direct_observation, HardenedPublicObservation):
            raise ValueError("direct nonreference control did not emit accepted Observation")
        direct_result = _finish_reference(direct_state)
        corrected_validity = _validity_tuple(corrected_result)
        direct_validity = _validity_tuple(direct_result)
        rows.append(
            _matrix_row(
                {
                    **_base_matrix_values(descriptor, nonreference, "nonreference_valid"),
                    "availability": "executed",
                    "second_action_id": nonreference_action,
                    "second_outcome": "accepted",
                    "corrected_action_accepted": True,
                    "component_commit_count": 1,
                    "later_correction_prompt_count": 0,
                    "retry_delta": nonreference.initial_retry_delta,
                    "tool_call_delta": nonreference.initial_tool_delta,
                    "rejection_component_advance_count": (
                        nonreference.initial_component_advance_count
                    ),
                    "final_result_id": corrected_result.result_id,
                    "final_base_valid": corrected_validity[0],
                    "final_mechanism_qualified": corrected_validity[1],
                    "final_qualified_valid": corrected_validity[2],
                    "direct_action_acceptance_match": (
                        corrected_observation.action_accepted == direct_observation.action_accepted
                    ),
                    "direct_public_effect_match": (
                        corrected_observation.public_effects == direct_observation.public_effects
                    ),
                    "direct_base_validity_match": (corrected_validity[0] == direct_validity[0]),
                    "direct_mechanism_match": (corrected_validity[1] == direct_validity[1]),
                    "direct_qualified_match": (corrected_validity[2] == direct_validity[2]),
                    "complete_rejection_lineage_bound": True,
                }
            )
        )

        same_invalid = _initial_exact_rejection(descriptor)
        same_terminal = step_runtime.step(same_invalid.state, descriptor.invalid_action_id)
        if not isinstance(same_terminal, PublicCorrectionBoundTerminal):
            raise ValueError("same-invalid second response did not terminalize")
        _assert_no_later_correction_prompt(same_invalid.state)
        rows.append(
            _matrix_row(
                {
                    **_base_matrix_values(descriptor, same_invalid, "same_current_invalid"),
                    "availability": "executed",
                    "second_action_id": descriptor.invalid_action_id,
                    "second_outcome": "typed_terminal",
                    "corrected_action_accepted": False,
                    "component_commit_count": 0,
                    "correction_terminal_id": same_terminal.terminal_id,
                    "later_correction_prompt_count": 0,
                    "retry_delta": same_invalid.initial_retry_delta,
                    "tool_call_delta": same_invalid.initial_tool_delta,
                    "rejection_component_advance_count": (
                        same_invalid.initial_component_advance_count
                    ),
                    "final_base_valid": False,
                    "final_mechanism_qualified": False,
                    "final_qualified_valid": False,
                    "complete_rejection_lineage_bound": True,
                }
            )
        )

        different = _initial_exact_rejection(descriptor)
        rows.append(
            _matrix_row(
                {
                    **_base_matrix_values(
                        descriptor,
                        different,
                        "different_current_invalid",
                    ),
                    "availability": "registered_but_unreachable",
                    "unreachable_reason": (
                        "exact_current_prompt_has_one_and_only_one_typed_invalid_candidate"
                    ),
                    "second_outcome": "registered_but_unreachable",
                }
            )
        )

        stale = _initial_exact_rejection(descriptor)
        stale_ids = tuple(
            sorted(stale.state.seen_public_action_ids - stale.state.current_public_action_ids)
        )
        if stale_ids:
            stale_terminal = step_runtime.step(stale.state, stale_ids[0])
            if not isinstance(stale_terminal, PublicCorrectionBoundTerminal):
                raise ValueError("stale second Action did not terminalize")
            _assert_no_later_correction_prompt(stale.state)
            rows.append(
                _matrix_row(
                    {
                        **_base_matrix_values(descriptor, stale, "stale_action_id"),
                        "availability": "executed",
                        "second_action_id": stale_ids[0],
                        "second_outcome": "action_reference_terminal",
                        "corrected_action_accepted": False,
                        "component_commit_count": 0,
                        "correction_terminal_id": stale_terminal.terminal_id,
                        "later_correction_prompt_count": 0,
                        "retry_delta": stale.initial_retry_delta,
                        "tool_call_delta": stale.initial_tool_delta,
                        "rejection_component_advance_count": (
                            stale.initial_component_advance_count
                        ),
                        "final_base_valid": False,
                        "final_mechanism_qualified": False,
                        "final_qualified_valid": False,
                        "complete_rejection_lineage_bound": True,
                    }
                )
            )
        else:
            rows.append(
                _matrix_row(
                    {
                        **_base_matrix_values(descriptor, stale, "stale_action_id"),
                        "availability": "registered_but_unreachable",
                        "unreachable_reason": "target_component_is_first_reached_prompt",
                        "second_outcome": "registered_but_unreachable",
                    }
                )
            )

        foreign = _initial_exact_rejection(descriptor)
        foreign_action = _registered_foreign_action(descriptor, descriptors)
        foreign_terminal = step_runtime.step(foreign.state, foreign_action)
        if not isinstance(foreign_terminal, PublicCorrectionBoundTerminal):
            raise ValueError("foreign second Action did not terminalize")
        _assert_no_later_correction_prompt(foreign.state)
        rows.append(
            _matrix_row(
                {
                    **_base_matrix_values(descriptor, foreign, "foreign_action_id"),
                    "availability": "executed",
                    "second_action_id": foreign_action,
                    "second_outcome": "action_reference_terminal",
                    "corrected_action_accepted": False,
                    "component_commit_count": 0,
                    "correction_terminal_id": foreign_terminal.terminal_id,
                    "later_correction_prompt_count": 0,
                    "retry_delta": foreign.initial_retry_delta,
                    "tool_call_delta": foreign.initial_tool_delta,
                    "rejection_component_advance_count": (foreign.initial_component_advance_count),
                    "final_base_valid": False,
                    "final_mechanism_qualified": False,
                    "final_qualified_valid": False,
                    "complete_rejection_lineage_bound": True,
                }
            )
        )

        malformed = _initial_exact_rejection(descriptor)
        malformed_action = _malformed_abi_valid_action(
            descriptor,
            registered_action_ids,
        )
        malformed_terminal = step_runtime.step(malformed.state, malformed_action)
        if not isinstance(malformed_terminal, PublicCorrectionBoundTerminal):
            raise ValueError("ABI-valid unbound second Action did not terminalize")
        _assert_no_later_correction_prompt(malformed.state)
        rows.append(
            _matrix_row(
                {
                    **_base_matrix_values(
                        descriptor,
                        malformed,
                        "malformed_abi_valid_action_id",
                    ),
                    "availability": "executed",
                    "second_action_id": malformed_action,
                    "second_outcome": "action_reference_terminal",
                    "corrected_action_accepted": False,
                    "component_commit_count": 0,
                    "correction_terminal_id": malformed_terminal.terminal_id,
                    "later_correction_prompt_count": 0,
                    "retry_delta": malformed.initial_retry_delta,
                    "tool_call_delta": malformed.initial_tool_delta,
                    "rejection_component_advance_count": (
                        malformed.initial_component_advance_count
                    ),
                    "final_base_valid": False,
                    "final_mechanism_qualified": False,
                    "final_qualified_valid": False,
                    "complete_rejection_lineage_bound": True,
                }
            )
        )

    counts = Counter(item.disposition for item in rows if item.availability == "executed")
    unreachable = Counter(
        item.disposition for item in rows if item.availability == "registered_but_unreachable"
    )
    expected_counts = {
        "reference_valid": 120,
        "nonreference_valid": 120,
        "same_current_invalid": 120,
        "stale_action_id": 72,
        "foreign_action_id": 120,
        "malformed_abi_valid_action_id": 120,
    }
    expected_unreachable = {
        "different_current_invalid": 120,
        "stale_action_id": 48,
    }
    if counts != expected_counts or unreachable != expected_unreachable:
        raise ValueError(f"bounded-correction Matrix partition changed:{counts}:{unreachable}")
    return cast(
        models.CorrectionBoundMatrixAudit,
        _make_model(
            models.CorrectionBoundMatrixAudit,
            {"rows": tuple(rows)},
            field="audit_id",
            prefix="finance_v26_bounded_correction_matrix_audit:",
        ),
    )


def _defect_reproduction(
    surface: models.ProductionRejectionSurfaceCatalog,
) -> models.V176DefectReproductionAudit:
    old_fields = tuple(TypedRejectionFeedback.model_fields)
    direct_host = (
        "component_key",
        "selected_operation_hash",
        "action_acceptance_report_id",
    )
    derived_host = (
        "feedback_id",
        "observation_receipt_id",
    )
    if surface.exact_catalog_rejection_state_count != 120:
        raise ValueError("v26.176 exact rejection denominator reproduction changed")
    return cast(
        models.V176DefectReproductionAudit,
        _make_model(
            models.V176DefectReproductionAudit,
            {
                "old_feedback_fields": old_fields,
                "old_feedback_host_direct_fields": direct_host,
                "old_feedback_host_derived_identity_fields": derived_host,
                "old_feedback_host_direct_field_count": len(direct_host),
            },
            field="audit_id",
            prefix="finance_v26_v176_typed_rejection_defect_reproduction:",
        ),
    )


def _public_feedback_contract() -> models.PublicFeedbackContract:
    return cast(
        models.PublicFeedbackContract,
        _make_model(
            models.PublicFeedbackContract,
            {
                "prohibited_public_fields": tuple(sorted(PROHIBITED_PUBLIC_FEEDBACK_KEYS)),
            },
            field="contract_id",
            prefix="public_typed_rejection_feedback_contract:",
        ),
    )


def _capability_outcome_contract() -> models.CapabilityOutcomeContract:
    return cast(
        models.CapabilityOutcomeContract,
        _make_model(
            models.CapabilityOutcomeContract,
            {},
            field="contract_id",
            prefix="capability_first_and_bounded_correction_outcome_contract:",
        ),
    )


def _outcome_contract_fixture_audit() -> models.OutcomeContractFixtureAudit:
    return cast(
        models.OutcomeContractFixtureAudit,
        _make_model(
            models.OutcomeContractFixtureAudit,
            {},
            field="audit_id",
            prefix="finance_v26_first_bounded_outcome_contract_fixture_audit:",
        ),
    )


def _expect_rejection(name: str, action: Callable[[], Any]) -> models.DestructiveMutation:
    try:
        action()
    except (KeyError, TypeError, ValidationError, ValueError) as exc:
        return models.DestructiveMutation(
            mutation=name,
            reason=f"{type(exc).__name__}:{exc}",
        )
    raise ValueError(f"v26.177 destructive mutation escaped:{name}")


def _validate_mutation(model: BaseModel, updates: Mapping[str, Any]) -> None:
    values = model.model_dump(mode="python")
    values.update(updates)
    type(model).model_validate(values)


def _validate_removed_field(model: BaseModel, field_name: str) -> None:
    values = model.model_dump(mode="python")
    values.pop(field_name)
    type(model).model_validate(values)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _production_destructive_audit(
    *,
    controls: ControlAuditProducts,
    contract: models.PublicFeedbackContract,
    surface: models.ProductionRejectionSurfaceCatalog,
    matrix: models.CorrectionBoundMatrixAudit,
    outcome_contract: models.CapabilityOutcomeContract,
) -> models.ProductionDestructiveAudit:
    feedback = controls.sample_feedback
    observation = controls.sample_observation
    host_binding = controls.sample_host_binding
    terminal = controls.sample_terminal
    second_observation = make_public_typed_rejection_observation(
        prompt=controls.sample_recovery_prompt,
        public_rejected_action_id=feedback.public_rejected_action_id,
        public_displayed_choice_handle=feedback.public_displayed_choice_handle,
        public_rejection_code=feedback.public_rejection_code,
        correction_attempt_index=2,
    )
    second_feedback = make_public_typed_rejection_feedback(
        observation=second_observation,
        predecessor_public_feedback_id=feedback.feedback_id,
    )
    first_matrix_accepted = next(item for item in matrix.rows if item.second_outcome == "accepted")
    first_matrix_terminal = next(
        item for item in matrix.rows if item.second_outcome == "typed_terminal"
    )
    first_matrix_unreachable = next(
        item for item in matrix.rows if item.availability == "registered_but_unreachable"
    )
    actions: tuple[tuple[str, Callable[[], Any]], ...] = (
        (
            "public_feedback_extra_package_id",
            lambda: _validate_mutation(feedback, {"package_id": host_binding.package_id}),
        ),
        (
            "public_feedback_extra_component_key",
            lambda: _validate_mutation(feedback, {"component_key": host_binding.component_key}),
        ),
        (
            "public_feedback_extra_selected_operation_hash",
            lambda: _validate_mutation(
                feedback,
                {"selected_operation_hash": host_binding.selected_operation_hash},
            ),
        ),
        (
            "public_feedback_extra_acceptance_report_id",
            lambda: _validate_mutation(
                feedback,
                {"action_acceptance_report_id": host_binding.action_acceptance_report_id},
            ),
        ),
        (
            "public_feedback_identity_replaced_by_host_binding",
            lambda: _validate_mutation(feedback, {"feedback_id": host_binding.binding_id}),
        ),
        (
            "public_observation_identity_replaced_by_acceptance_report",
            lambda: _validate_mutation(
                observation,
                {"public_observation_receipt_id": (host_binding.action_acceptance_report_id)},
            ),
        ),
        (
            "public_feedback_attempt_above_registered_surface",
            lambda: _validate_mutation(feedback, {"correction_attempt_index": 3}),
        ),
        (
            "second_feedback_missing_public_predecessor",
            lambda: _validate_mutation(
                second_feedback,
                {"predecessor_public_feedback_id": None},
            ),
        ),
        (
            "second_feedback_host_predecessor",
            lambda: _validate_mutation(
                second_feedback,
                {"predecessor_public_feedback_id": host_binding.binding_id},
            ),
        ),
        (
            "strict_public_scan_component_key",
            lambda: _require(
                not strict_public_feedback_findings({"component_key": "forged"}),
                "strict public scan accepted component_key",
            ),
        ),
        (
            "host_binding_marked_model_visible",
            lambda: _validate_mutation(host_binding, {"model_visible": True}),
        ),
        (
            "terminal_allows_later_prompt",
            lambda: _validate_mutation(terminal, {"later_prompt_allowed": True}),
        ),
        (
            "typed_terminal_missing_second_feedback",
            lambda: _validate_mutation(terminal, {"second_public_feedback_id": None}),
        ),
        (
            "typed_terminal_commits_action",
            lambda: _validate_mutation(terminal, {"action_committed": True}),
        ),
        (
            "public_observation_commits_rejected_action",
            lambda: _validate_mutation(observation, {"action_committed": True}),
        ),
        (
            "public_feedback_contract_missing_public_field",
            lambda: _validate_mutation(
                contract,
                {"public_feedback_fields": contract.public_feedback_fields[:-1]},
            ),
        ),
        (
            "public_feedback_contract_repeats_prohibited_field",
            lambda: _validate_mutation(
                contract,
                {
                    "prohibited_public_fields": (
                        *contract.prohibited_public_fields,
                        contract.prohibited_public_fields[0],
                    )
                },
            ),
        ),
        (
            "production_rejection_kind_silently_dropped",
            lambda: _validate_mutation(surface, {"rows": surface.rows[:-1]}),
        ),
        (
            "production_rejection_exact_status_promoted",
            lambda: _validate_mutation(
                surface.rows[1],
                {
                    "exact_catalog_status": "reachable",
                    "exact_catalog_rejection_state_count": 0,
                },
            ),
        ),
        (
            "correction_matrix_row_dropped",
            lambda: _validate_mutation(matrix, {"rows": matrix.rows[:-1]}),
        ),
        (
            "accepted_correction_zero_commit",
            lambda: _validate_mutation(first_matrix_accepted, {"component_commit_count": 0}),
        ),
        (
            "terminal_correction_missing_terminal_id",
            lambda: _validate_mutation(
                first_matrix_terminal,
                {"correction_terminal_id": None},
            ),
        ),
        (
            "unreachable_correction_missing_reason",
            lambda: _validate_mutation(first_matrix_unreachable, {"unreachable_reason": None}),
        ),
        (
            "nonreference_direct_equivalence_falsified",
            lambda: _validate_mutation(
                next(item for item in matrix.rows if item.disposition == "nonreference_valid"),
                {"direct_public_effect_match": False},
            ),
        ),
        (
            "capability_outcome_required_field_removed",
            lambda: _validate_mutation(
                outcome_contract,
                {"outcome_fields": outcome_contract.outcome_fields[:-1]},
            ),
        ),
        (
            "capability_outcome_contract_id_removed",
            lambda: _validate_removed_field(outcome_contract, "contract_id"),
        ),
    )
    mutations = tuple(_expect_rejection(name, action) for name, action in actions)
    return cast(
        models.ProductionDestructiveAudit,
        _make_model(
            models.ProductionDestructiveAudit,
            {
                "mutations": mutations,
                "mutation_count": len(mutations),
                "rejection_count": len(mutations),
            },
            field="audit_id",
            prefix="finance_v26_all_typed_rejection_production_destructive_audit:",
        ),
    )


def _gate(name: str, observed: int, required: int) -> models.StaticGate:
    if observed < required:
        raise ValueError(f"v26.177 static Gate failed:{name}:{observed}<{required}")
    return models.StaticGate(
        gate=name,
        passed=True,
        observed=observed,
        required=required,
    )


def _static_audit(
    *,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.V176PredecessorFreezeAudit,
    defect: models.V176DefectReproductionAudit,
    controls: ControlAuditProducts,
    matrix: models.CorrectionBoundMatrixAudit,
    outcome_contract: models.CapabilityOutcomeContract,
    destructive: models.ProductionDestructiveAudit,
) -> models.StaticAudit:
    surface = controls.surface
    projection = controls.projection
    gates = (
        _gate("v176_file_freeze", predecessor.independent_rebuild_match_count, 16),
        _gate(
            "old_feedback_direct_host_field_reproduction",
            defect.old_feedback_host_direct_field_count,
            3,
        ),
        _gate("public_feedback_exact_field_schema", len(PUBLIC_FEEDBACK_FIELDS), 9),
        _gate("production_decision_kind_registry", surface.decision_kind_count, 4),
        _gate("production_rejection_kind_registry", surface.rejection_kind_count, 5),
        _gate("exact_catalog_reachable_kind", surface.exact_catalog_reachable_kind_count, 1),
        _gate("registered_unreachable_kind", surface.registered_but_unreachable_kind_count, 4),
        _gate("classifier_control_fixture", surface.control_fixture_count, 432),
        _gate(
            "classifier_control_rejection",
            sum(item.control_rejection_count for item in surface.rows),
            432,
        ),
        _gate(
            "classifier_reference_correction",
            sum(item.reference_correction_accept_count for item in surface.rows),
            432,
        ),
        _gate(
            "classifier_repeated_invalid_terminal",
            sum(item.repeated_invalid_terminal_count for item in surface.rows),
            432,
        ),
        _gate("public_projection", projection.projection_count, 432),
        _gate("independent_public_projection", projection.independent_projection_match_count, 432),
        _gate(
            "host_counterfactual_invariance", projection.host_counterfactual_invariant_count, 432
        ),
        _gate("public_identity_preimage", projection.identity_preimage_public_only_count, 432),
        _gate("correction_matrix_rows", matrix.matrix_row_count, 840),
        _gate("correction_matrix_executed", matrix.executed_row_count, 672),
        _gate(
            "correction_matrix_unreachable_explicit",
            matrix.registered_but_unreachable_row_count,
            168,
        ),
        _gate("reference_valid_correction", matrix.reference_valid_accept_count, 120),
        _gate("nonreference_valid_correction", matrix.nonreference_valid_accept_count, 120),
        _gate("same_invalid_terminal", matrix.same_invalid_terminal_count, 120),
        _gate("stale_terminal", matrix.stale_terminal_count, 72),
        _gate("foreign_terminal", matrix.foreign_terminal_count, 120),
        _gate("malformed_abi_valid_terminal", matrix.malformed_abi_valid_terminal_count, 120),
        _gate("all_second_invalid_terminal", matrix.any_second_invalid_terminal_count, 432),
        _gate("nonreference_direct_equivalence", matrix.nonreference_direct_equivalence_count, 120),
        _gate(
            "separate_capability_estimands",
            len(
                {
                    outcome_contract.first_attempt_estimand,
                    outcome_contract.bounded_correction_estimand,
                }
            ),
            2,
        ),
        _gate(
            "production_destructive_rejection",
            destructive.rejection_count,
            destructive.mutation_count,
        ),
        _gate("transitive_source_closure", source_root.file_count, len(ENTRY_SOURCE_PATHS)),
        _gate("provider_call_zero", 0, 0),
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
            prefix="finance_v26_all_typed_rejection_static_audit:",
        ),
    )


def _transition(
    *,
    authorization: models.ExternalAuditAuthorization,
    source_root: models.TransitiveSourceRoot,
    predecessor_audit: models.V176PredecessorFreezeAudit,
    predecessor: PredecessorObjects,
    defect: models.V176DefectReproductionAudit,
    contract: models.PublicFeedbackContract,
    controls: ControlAuditProducts,
    matrix: models.CorrectionBoundMatrixAudit,
    outcome_contract: models.CapabilityOutcomeContract,
    outcome_fixture: models.OutcomeContractFixtureAudit,
    destructive: models.ProductionDestructiveAudit,
    static: models.StaticAudit,
) -> models.ProspectiveTransition:
    return cast(
        models.ProspectiveTransition,
        _make_model(
            models.ProspectiveTransition,
            {
                "authorization_id": authorization.authorization_id,
                "source_root_id": source_root.root_id,
                "predecessor_freeze_audit_id": predecessor_audit.audit_id,
                "defect_reproduction_audit_id": defect.audit_id,
                "consumed_stage": models.AUTHORIZED_STAGE,
                "blocked_predecessor_stage": models.BLOCKED_PREDECESSOR_STAGE,
                "next_stage": models.NEXT_STAGE,
                "source_v176_report_id": predecessor.report.report_id,
                "public_feedback_contract_id": contract.contract_id,
                "rejection_surface_catalog_id": controls.surface.catalog_id,
                "public_feedback_projection_audit_id": controls.projection.audit_id,
                "correction_matrix_audit_id": matrix.audit_id,
                "capability_outcome_contract_id": outcome_contract.contract_id,
                "outcome_fixture_audit_id": outcome_fixture.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
            },
            field="transition_id",
            prefix="finance_v26_all_typed_rejection_public_feedback_transition:",
        ),
    )


def _detail_files(output_dir: Path) -> tuple[models.FileBinding, ...]:
    return tuple(
        _file_binding(
            path=path,
            relative_path=path.name,
            source_kind=(
                "external_audit_input"
                if path.name == "external_v176_revision_audit_input.txt"
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
    public_feedback_contract = _public_feedback_contract()
    controls = _production_rejection_and_projection_audits(predecessor)
    defect = _defect_reproduction(controls.surface)
    correction_matrix = _correction_bound_matrix_audit(predecessor)
    capability_outcome_contract = _capability_outcome_contract()
    outcome_fixture = _outcome_contract_fixture_audit()
    destructive = _production_destructive_audit(
        controls=controls,
        contract=public_feedback_contract,
        surface=controls.surface,
        matrix=correction_matrix,
        outcome_contract=capability_outcome_contract,
    )
    static = _static_audit(
        source_root=source_root,
        predecessor=predecessor_audit,
        defect=defect,
        controls=controls,
        matrix=correction_matrix,
        outcome_contract=capability_outcome_contract,
        destructive=destructive,
    )
    transition = _transition(
        authorization=authorization,
        source_root=source_root,
        predecessor_audit=predecessor_audit,
        predecessor=predecessor,
        defect=defect,
        contract=public_feedback_contract,
        controls=controls,
        matrix=correction_matrix,
        outcome_contract=capability_outcome_contract,
        outcome_fixture=outcome_fixture,
        destructive=destructive,
        static=static,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(
        output_dir / "external_v176_revision_audit_input.txt",
        external_audit_path.read_bytes(),
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("v176_predecessor_freeze_audit.json", predecessor_audit),
        ("v176_defect_reproduction_audit.json", defect),
        ("public_typed_rejection_feedback_contract.json", public_feedback_contract),
        ("production_rejection_surface_catalog.json", controls.surface),
        ("public_feedback_projection_audit.json", controls.projection),
        ("correction_bound_matrix_audit.json", correction_matrix),
        ("capability_outcome_contract.json", capability_outcome_contract),
        ("outcome_contract_fixture_audit.json", outcome_fixture),
        ("production_destructive_audit.json", destructive),
        ("static_audit.json", static),
        ("prospective_transition_contract.json", transition),
    )
    for filename, value in outputs:
        _write(output_dir / filename, value)
    details = _detail_files(output_dir)
    report = cast(
        models.ClosureReport,
        _make_model(
            models.ClosureReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "source_root_id": source_root.root_id,
                "predecessor_freeze_audit_id": predecessor_audit.audit_id,
                "defect_reproduction_audit_id": defect.audit_id,
                "public_feedback_contract_id": public_feedback_contract.contract_id,
                "rejection_surface_catalog_id": controls.surface.catalog_id,
                "public_feedback_projection_audit_id": controls.projection.audit_id,
                "correction_matrix_audit_id": correction_matrix.audit_id,
                "capability_outcome_contract_id": capability_outcome_contract.contract_id,
                "outcome_fixture_audit_id": outcome_fixture.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "detail_files": details,
                "detail_file_count": len(details),
                "next_stage": transition.next_stage,
            },
            field="report_id",
            prefix="finance_v26_all_typed_rejection_public_feedback_closure_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor_audit,
        defect=defect,
        public_feedback_contract=public_feedback_contract,
        rejection_surface=controls.surface,
        public_feedback_projection=controls.projection,
        correction_matrix=correction_matrix,
        capability_outcome_contract=capability_outcome_contract,
        outcome_fixture=outcome_fixture,
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
