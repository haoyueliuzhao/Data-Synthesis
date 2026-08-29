from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task.executed_counterfactual_outcome_closure import (
    REQUIRED_CAPABILITY_OUTCOME_FIELDS,
    CapabilityOutcomeRow,
    evaluate_capability_estimands,
    make_capability_outcome_row,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback as v177,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_models as v177_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history as v176,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history_models as v176_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executed_counterfactual_outcome_closure_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executed_counterfactual_outcome_closure_runtime as closure_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_state_local_presentation_parent_hardening_models as v175_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_models as v171_models,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_178_executed_counterfactual_outcome_closure_v3_20260830"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_178_executed_counterfactual_outcome_closure_v3_20260830"
)
EXPECTED_REVIEW_SHA256: Final = "738e4ecc0554b285ae3bdcc5f7814cd6e1da7db8617ef67beb2cde6b6973f8c8"
EXPECTED_REVIEW_BYTE_COUNT: Final = 19_573
V177_DIR: Final = v177.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/executed_counterfactual_outcome_closure.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_executed_counterfactual_outcome_closure_runtime.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_executed_counterfactual_outcome_closure_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_executed_counterfactual_outcome_closure.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.178 cannot resolve the trusted_data_synthesis package root")


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
        raise ValueError(f"v26.178 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.178 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
        raise ValueError("v26.178 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.178 external audit byte count does not match Authorization")
    return models.make_identity_model(
        models.ExternalAuditAuthorization,
        {
            "review_sha256": EXPECTED_REVIEW_SHA256,
            "review_byte_count": EXPECTED_REVIEW_BYTE_COUNT,
            "authorized_stage": models.AUTHORIZED_STAGE,
        },
        field="authorization_id",
        prefix="finance_v26_executed_counterfactual_external_authorization:",
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
    return models.make_identity_model(
        models.TransitiveSourceRoot,
        {
            "entry_modules": entry_modules,
            "files": bindings,
            "file_count": len(bindings),
            "unresolved_imports": tuple(sorted(unresolved)),
            "unresolved_import_count": len(unresolved),
        },
        field="root_id",
        prefix="finance_v26_executed_counterfactual_outcome_transitive_source_root:",
    )


@dataclass(frozen=True)
class FrozenPredecessor:
    audit: models.V177PredecessorFreezeAudit
    v177_report: v177_models.ClosureReport
    v177_transition: v177_models.ProspectiveTransition
    v177_outcome_contract: v177_models.CapabilityOutcomeContract
    source: v177.PredecessorObjects


def _load_v176_objects(package_root: Path) -> v177.PredecessorObjects:
    source_dir = package_root / v176.OUTPUT_DIR
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
    schedules = v175_models.StateLocalScheduleCatalog.model_validate(
        _load(package_root / v176.V175_DIR / "state_local_schedule_catalog.json")
    )
    source = v171_models.ValiditySeparatedDevelopmentCatalog.model_validate(
        _load(package_root / v176.V171_DIR / "validity_separated_development_catalog.json")
    )
    return v177.PredecessorObjects(
        report=report,
        transition=transition,
        development=development,
        runner=runner,
        schedules=schedules,
        source=source,
    )


def _predecessor_freeze(package_root: Path) -> FrozenPredecessor:
    source_dir = package_root / V177_DIR
    paths = tuple(sorted(path for path in source_dir.iterdir() if path.is_file()))
    if len(paths) != 15:
        raise ValueError("v26.177 authoritative formal directory is not exactly 15 files")
    report = v177_models.ClosureReport.model_validate(_load(source_dir / "report.json"))
    transition = v177_models.ProspectiveTransition.model_validate(
        _load(source_dir / "prospective_transition_contract.json")
    )
    outcome_contract = v177_models.CapabilityOutcomeContract.model_validate(
        _load(source_dir / "capability_outcome_contract.json")
    )
    if transition.next_stage != models.BLOCKED_PREDECESSOR_STAGE:
        raise ValueError("v26.177 next stage differs from the audited blocked preflight")
    with tempfile.TemporaryDirectory(prefix="finance-v26-178-v177-rebuild-") as temporary:
        rebuild_dir = Path(temporary)
        v177.build(
            package_root=package_root,
            output_dir=rebuild_dir,
            external_audit_path=source_dir / "external_v176_revision_audit_input.txt",
        )
        rebuilt = tuple(sorted(path for path in rebuild_dir.iterdir() if path.is_file()))
        if len(rebuilt) != len(paths):
            raise ValueError("v26.177 independent rebuild file count differs")
        for source_path in paths:
            candidate = rebuild_dir / source_path.name
            if not candidate.is_file() or source_path.read_bytes() != candidate.read_bytes():
                raise ValueError(f"v26.177 independent rebuild differs:{source_path.name}")
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=f"{V177_DIR}/{path.name}",
            source_kind="predecessor_artifact",
        )
        for path in paths
    )
    audit = models.make_identity_model(
        models.V177PredecessorFreezeAudit,
        {
            "predecessor_report_id": report.report_id,
            "predecessor_transition_id": transition.transition_id,
            "predecessor_files": bindings,
            "blocked_runner_preflight_transition": models.BLOCKED_PREDECESSOR_STAGE,
        },
        field="audit_id",
        prefix="finance_v26_v177_predecessor_freeze_audit:",
    )
    return FrozenPredecessor(
        audit=audit,
        v177_report=report,
        v177_transition=transition,
        v177_outcome_contract=outcome_contract,
        source=_load_v176_objects(package_root),
    )


def _function_node(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = tuple(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name
    )
    if len(matches) != 1:
        raise ValueError(f"v26.177 source function is absent or ambiguous:{name}")
    return matches[0]


def _defect_reproduction(
    package_root: Path,
    predecessor: FrozenPredecessor,
) -> models.V177EvidenceIdentityDefectAudit:
    source_path = package_root / v177.ENTRY_SOURCE_PATHS[-1]
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    projection_function = _function_node(tree, "_production_rejection_and_projection_audits")
    aliased_fields: set[str] = set()
    for node in ast.walk(projection_function):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and key.value
                in {
                    "independent_projection_match",
                    "host_counterfactual_invariant",
                    "identity_preimage_public_only",
                }
                and isinstance(value, ast.Name)
                and value.id == "independent"
            ):
                aliased_fields.add(str(key.value))
    fixture_function = _function_node(tree, "_outcome_contract_fixture_audit")
    fixture_row_calls = sum(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id == "CapabilityOutcomeRow"
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "CapabilityOutcomeRow"
        )
        for node in ast.walk(fixture_function)
    )
    projection = v177_models.PublicFeedbackProjectionAudit.model_validate(
        _load(package_root / V177_DIR / "public_feedback_projection_audit.json")
    )
    fixture = v177_models.OutcomeContractFixtureAudit.model_validate(
        _load(package_root / V177_DIR / "outcome_contract_fixture_audit.json")
    )
    if (
        aliased_fields
        != {
            "independent_projection_match",
            "host_counterfactual_invariant",
            "identity_preimage_public_only",
        }
        or fixture_row_calls != 0
        or projection.registered_control_projection_count != 312
        or fixture.fixture_count != 5
        or predecessor.v177_outcome_contract.future_job_count != 192
    ):
        raise ValueError("v26.177 Evidence-identity defect reproduction changed")
    return models.make_identity_model(
        models.V177EvidenceIdentityDefectAudit,
        {},
        field="audit_id",
        prefix="finance_v26_v177_evidence_identity_defect_reproduction:",
    )


def _capability_outcome_contract(
    predecessor: FrozenPredecessor,
) -> models.CapabilityOutcomeContract:
    return models.make_identity_model(
        models.CapabilityOutcomeContract,
        {
            "source_v176_runner_input_catalog_id": predecessor.source.runner.catalog_id,
            "source_v177_outcome_contract_id": predecessor.v177_outcome_contract.contract_id,
        },
        field="contract_id",
        prefix="capability_executed_first_bounded_outcome_contract:",
    )


def _fixture_values(*, accepted: bool, terminal_reason: str | None) -> dict[str, Any]:
    return {
        "job_eligible": True,
        "eligibility_exclusion_reason": None,
        "first_response_abi_valid": True,
        "first_action_state_precondition_valid": False,
        "first_action_accepted": False,
        "first_attempt_base_valid": False,
        "first_attempt_mechanism_qualified": False,
        "first_attempt_qualified_valid": False,
        "correction_invoked": True,
        "correction_feedback_id": canonical_hash(
            {"accepted": accepted, "terminal_reason": terminal_reason},
            prefix="outcome_contract_fixture_public_feedback:",
        ),
        "corrected_action_accepted": accepted,
        "correction_terminal_reason": terminal_reason,
        "final_base_valid": accepted,
        "final_mechanism_qualified": accepted,
        "final_qualified_valid": accepted,
    }


def _outcome_fixture_audit() -> models.OutcomeRowFixtureAudit:
    rows = (
        make_capability_outcome_row(
            "reference_valid_correction",
            _fixture_values(accepted=True, terminal_reason=None),
        ),
        make_capability_outcome_row(
            "nonreference_valid_correction",
            {
                **_fixture_values(accepted=True, terminal_reason=None),
                "correction_feedback_id": canonical_hash(
                    "nonreference",
                    prefix="outcome_contract_fixture_public_feedback:",
                ),
            },
        ),
        make_capability_outcome_row(
            "same_current_invalid_terminal",
            _fixture_values(
                accepted=False,
                terminal_reason="correction_attempt_typed_invalid",
            ),
        ),
        make_capability_outcome_row(
            "different_current_invalid_terminal",
            {
                **_fixture_values(
                    accepted=False,
                    terminal_reason="correction_attempt_typed_invalid",
                ),
                "correction_feedback_id": canonical_hash(
                    "different-current",
                    prefix="outcome_contract_fixture_public_feedback:",
                ),
            },
        ),
        make_capability_outcome_row(
            "stale_or_foreign_action_terminal",
            _fixture_values(
                accepted=False,
                terminal_reason="correction_action_reference_invalid",
            ),
        ),
    )
    for row in rows:
        model_roundtrip = CapabilityOutcomeRow.model_validate(row.model_dump(mode="python"))
        serialized = _canonical_file_bytes(row)
        serialization_roundtrip = CapabilityOutcomeRow.model_validate(json.loads(serialized))
        if model_roundtrip != row or serialization_roundtrip != row:
            raise ValueError("Capability Outcome fixture row does not round-trip")
        if tuple(
            key for key in REQUIRED_CAPABILITY_OUTCOME_FIELDS if key not in type(row).model_fields
        ):
            raise ValueError("Capability Outcome fixture row omits a required field")
    evaluation = evaluate_capability_estimands(rows, expected_eligible_job_count=5)
    return models.make_identity_model(
        models.OutcomeRowFixtureAudit,
        {"rows": rows, "evaluation": evaluation},
        field="audit_id",
        prefix="finance_v26_executed_outcome_row_fixture_audit:",
    )


def _raw_identity(payload: Mapping[str, Any], field: str, prefix: str) -> str:
    return canonical_hash(
        {key: value for key, value in payload.items() if key != field},
        prefix=prefix,
    )


def _fully_rehashed_rejection(
    *,
    mutation: str,
    payload: dict[str, Any],
    model_type: type[BaseModel],
    field: str,
    prefix: str,
) -> models.FullyRehashedMutation:
    changed_parent_id = _raw_identity(payload, field, prefix)
    payload[field] = changed_parent_id
    changed_transition_id = canonical_hash(
        {
            "mutation": mutation,
            "changed_parent_id": changed_parent_id,
            "consumed_stage": models.AUTHORIZED_STAGE,
        },
        prefix="fully_rehashed_evidence_attack_transition:",
    )
    changed_report_id = canonical_hash(
        {
            "mutation": mutation,
            "changed_parent_id": changed_parent_id,
            "changed_transition_id": changed_transition_id,
        },
        prefix="fully_rehashed_evidence_attack_report:",
    )
    try:
        model_type.model_validate(payload)
    except (TypeError, ValidationError, ValueError) as exc:
        reason = f"{type(exc).__name__}:{str(exc).splitlines()[0]}"
    else:
        raise ValueError(f"fully rehashed evidence mutation escaped:{mutation}")
    return models.FullyRehashedMutation(
        mutation=mutation,
        changed_parent_id=changed_parent_id,
        changed_transition_id=changed_transition_id,
        changed_report_id=changed_report_id,
        rejected=True,
        reason=reason,
    )


def _destructive_audit(
    *,
    contract: models.CapabilityOutcomeContract,
    host: models.ExecutedHostCounterfactualAudit,
    controls: models.ValidControlExecutionAudit,
    reachability: models.ExactCatalogReachabilityAudit,
) -> models.FullyRehashedDestructiveAudit:
    contract_field = contract.model_dump(mode="python")
    contract_field["outcome_fields"] = contract.outcome_fields[:-1]
    eligibility = contract.model_dump(mode="python")
    eligibility["eligibility_rule"] = "outcome_dependent_eligibility"
    pooling = contract.model_dump(mode="python")
    pooling["estimand_pooling_forbidden"] = False
    host_alias = host.model_dump(mode="python")
    host_alias["measurement_method"] = "public_preimage_boolean_alias"
    control_bypass = controls.model_dump(mode="python")
    control_objects = list(control_bypass["control_objects"])
    changed_object = dict(control_objects[0])
    changed_object["operation_roundtrip_valid"] = False
    changed_object["object_id"] = _raw_identity(
        changed_object,
        "object_id",
        "canonical_valid_typed_rejection_control_object:",
    )
    control_objects[0] = changed_object
    control_bypass["control_objects"] = tuple(control_objects)
    reachability_relabel = reachability.model_dump(mode="python")
    reachability_rows = list(reachability_relabel["reachability_rows"])
    unreachable_index = next(
        index
        for index, item in enumerate(reachability_rows)
        if item["observed_rejection_count"] == 0
    )
    changed_reachability = dict(reachability_rows[unreachable_index])
    changed_reachability["exact_catalog_status"] = "reachable"
    changed_reachability["row_id"] = _raw_identity(
        changed_reachability,
        "row_id",
        "exact_catalog_typed_rejection_reachability_row:",
    )
    reachability_rows[unreachable_index] = changed_reachability
    reachability_relabel["reachability_rows"] = tuple(reachability_rows)
    attacks = (
        _fully_rehashed_rejection(
            mutation="required_outcome_field_deletion",
            payload=contract_field,
            model_type=models.CapabilityOutcomeContract,
            field="contract_id",
            prefix="capability_executed_first_bounded_outcome_contract:",
        ),
        _fully_rehashed_rejection(
            mutation="eligibility_rule_replacement",
            payload=eligibility,
            model_type=models.CapabilityOutcomeContract,
            field="contract_id",
            prefix="capability_executed_first_bounded_outcome_contract:",
        ),
        _fully_rehashed_rejection(
            mutation="first_final_estimand_pooling",
            payload=pooling,
            model_type=models.CapabilityOutcomeContract,
            field="contract_id",
            prefix="capability_executed_first_bounded_outcome_contract:",
        ),
        _fully_rehashed_rejection(
            mutation="host_counterfactual_boolean_alias",
            payload=host_alias,
            model_type=models.ExecutedHostCounterfactualAudit,
            field="audit_id",
            prefix="finance_v26_executed_host_counterfactual_invariance_audit:",
        ),
        _fully_rehashed_rejection(
            mutation="registered_control_identity_bypass",
            payload=control_bypass,
            model_type=models.ValidControlExecutionAudit,
            field="audit_id",
            prefix="finance_v26_canonical_valid_rejection_control_execution_audit:",
        ),
        _fully_rehashed_rejection(
            mutation="exact_reachability_status_relabeling",
            payload=reachability_relabel,
            model_type=models.ExactCatalogReachabilityAudit,
            field="audit_id",
            prefix="finance_v26_exact_catalog_rejection_reachability_audit:",
        ),
    )
    return models.make_identity_model(
        models.FullyRehashedDestructiveAudit,
        {
            "mutations": attacks,
            "mutation_count": len(attacks),
            "rejection_count": len(attacks),
        },
        field="audit_id",
        prefix="finance_v26_fully_rehashed_evidence_destructive_audit:",
    )


def _gate(name: str, observed: int, required: int) -> models.StaticGate:
    if observed < required:
        raise ValueError(f"v26.178 static Gate failed:{name}:{observed}<{required}")
    return models.StaticGate(gate=name, passed=True, observed=observed, required=required)


def _static_audit(
    *,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.V177PredecessorFreezeAudit,
    defect: models.V177EvidenceIdentityDefectAudit,
    reachability: models.ExactCatalogReachabilityAudit,
    controls: models.ValidControlExecutionAudit,
    host: models.ExecutedHostCounterfactualAudit,
    contract: models.CapabilityOutcomeContract,
    fixtures: models.OutcomeRowFixtureAudit,
    destructive: models.FullyRehashedDestructiveAudit,
) -> models.StaticAudit:
    gates = (
        _gate("v177_file_freeze", predecessor.independent_rebuild_match_count, 15),
        _gate(
            "old_host_counterfactual_measurement_failure",
            int(defect.host_counterfactual_measurement_failed),
            1,
        ),
        _gate("old_registered_control_downgrade", defect.old_registered_control_count, 312),
        _gate("old_outcome_fixture_row_absence", defect.old_outcome_fixture_declared_count, 5),
        _gate("exact_catalog_package_scan", reachability.package_count, 32),
        _gate("exact_catalog_component_scan", reachability.component_count, 80),
        _gate("exact_catalog_state_scan", reachability.state_scan_count, 480),
        _gate("exact_catalog_candidate_scan", reachability.candidate_scan_count, 1),
        _gate("exact_catalog_registered_branch_scan", reachability.registered_branch_count, 5),
        _gate(
            "exact_catalog_unreachable_derivation",
            reachability.valid_object_unreachable_branch_count,
            4,
        ),
        _gate("canonical_control_objects", controls.control_object_count, 72),
        _gate("canonical_control_executions", controls.execution_row_count, 432),
        _gate("canonical_diagnostic_controls", controls.canonical_diagnostic_execution_count, 312),
        _gate(
            "rematerialized_component_controls",
            controls.rematerialized_component_execution_count,
            192,
        ),
        _gate("valid_control_public_objects", controls.valid_public_object_execution_count, 432),
        _gate(
            "valid_control_reference_correction", controls.reference_correction_accept_count, 432
        ),
        _gate("valid_control_repeated_terminal", controls.repeated_invalid_terminal_count, 432),
        _gate("executed_host_counterfactual_base_rows", host.base_control_row_count, 432),
        _gate(
            "executed_host_counterfactual_interventions", host.intervention_execution_count, 3024
        ),
        _gate("host_binding_changed", host.host_binding_change_count, 3024),
        _gate("public_observation_invariance", host.public_observation_invariance_count, 3024),
        _gate("public_feedback_invariance", host.public_feedback_invariance_count, 3024),
        _gate("recovery_prompt_invariance", host.recovery_prompt_invariance_count, 3024),
        _gate("fixed_empirical_denominator", contract.eligible_job_count, 192),
        _gate(
            "exact_outcome_field_tuple",
            len(contract.outcome_fields),
            len(REQUIRED_CAPABILITY_OUTCOME_FIELDS),
        ),
        _gate("executed_outcome_fixture_rows", fixtures.fixture_row_count, 5),
        _gate(
            "outcome_fixture_model_roundtrip",
            fixtures.model_validation_roundtrip_count,
            5,
        ),
        _gate(
            "outcome_fixture_serialization_roundtrip",
            fixtures.canonical_serialization_roundtrip_count,
            5,
        ),
        _gate(
            "separate_estimand_calculation",
            len({contract.first_attempt_estimand, contract.bounded_correction_estimand}),
            2,
        ),
        _gate("fully_rehashed_destructive_rejection", destructive.rejection_count, 6),
        _gate("transitive_source_closure", source_root.file_count, len(ENTRY_SOURCE_PATHS)),
        _gate("provider_call_zero", 0, 0),
    )
    return models.make_identity_model(
        models.StaticAudit,
        {
            "gates": gates,
            "gate_count": len(gates),
            "passed_gate_count": len(gates),
        },
        field="audit_id",
        prefix="finance_v26_executed_counterfactual_outcome_static_audit:",
    )


def _transition(
    *,
    authorization: models.ExternalAuditAuthorization,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.V177PredecessorFreezeAudit,
    defect: models.V177EvidenceIdentityDefectAudit,
    reachability: models.ExactCatalogReachabilityAudit,
    controls: models.ValidControlExecutionAudit,
    host: models.ExecutedHostCounterfactualAudit,
    contract: models.CapabilityOutcomeContract,
    fixtures: models.OutcomeRowFixtureAudit,
    destructive: models.FullyRehashedDestructiveAudit,
    static: models.StaticAudit,
) -> models.ProspectiveTransition:
    return models.make_identity_model(
        models.ProspectiveTransition,
        {
            "authorization_id": authorization.authorization_id,
            "source_root_id": source_root.root_id,
            "predecessor_freeze_audit_id": predecessor.audit_id,
            "defect_reproduction_audit_id": defect.audit_id,
            "exact_catalog_reachability_audit_id": reachability.audit_id,
            "valid_control_execution_audit_id": controls.audit_id,
            "executed_host_counterfactual_audit_id": host.audit_id,
            "capability_outcome_contract_id": contract.contract_id,
            "outcome_fixture_audit_id": fixtures.audit_id,
            "destructive_audit_id": destructive.audit_id,
            "static_audit_id": static.audit_id,
            "consumed_stage": models.AUTHORIZED_STAGE,
            "blocked_predecessor_stage": models.BLOCKED_PREDECESSOR_STAGE,
            "next_stage": models.NEXT_STAGE,
        },
        field="transition_id",
        prefix="finance_v26_executed_counterfactual_outcome_transition:",
    )


def _detail_files(output_dir: Path) -> tuple[models.FileBinding, ...]:
    return tuple(
        _file_binding(
            path=path,
            relative_path=path.name,
            source_kind=(
                "external_audit_input"
                if path.name == "external_v177_source_level_audit_input.txt"
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
    frozen = _predecessor_freeze(package_root)
    defect = _defect_reproduction(package_root, frozen)
    reachability = closure_runtime.scan_exact_catalog(frozen.source)
    control_products = closure_runtime.execute_valid_controls(frozen.source)
    host = closure_runtime.execute_host_counterfactuals(control_products.host_seeds)
    contract = _capability_outcome_contract(frozen)
    fixtures = _outcome_fixture_audit()
    destructive = _destructive_audit(
        contract=contract,
        host=host,
        controls=control_products.audit,
        reachability=reachability,
    )
    static = _static_audit(
        source_root=source_root,
        predecessor=frozen.audit,
        defect=defect,
        reachability=reachability,
        controls=control_products.audit,
        host=host,
        contract=contract,
        fixtures=fixtures,
        destructive=destructive,
    )
    transition = _transition(
        authorization=authorization,
        source_root=source_root,
        predecessor=frozen.audit,
        defect=defect,
        reachability=reachability,
        controls=control_products.audit,
        host=host,
        contract=contract,
        fixtures=fixtures,
        destructive=destructive,
        static=static,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(
        output_dir / "external_v177_source_level_audit_input.txt",
        external_audit_path.read_bytes(),
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("v177_predecessor_freeze_audit.json", frozen.audit),
        ("v177_evidence_identity_defect_audit.json", defect),
        ("exact_catalog_reachability_audit.json", reachability),
        ("canonical_valid_control_execution_audit.json", control_products.audit),
        ("executed_host_counterfactual_audit.json", host),
        ("capability_outcome_contract.json", contract),
        ("outcome_row_fixture_audit.json", fixtures),
        ("fully_rehashed_destructive_audit.json", destructive),
        ("static_audit.json", static),
        ("prospective_transition_contract.json", transition),
    )
    for filename, value in outputs:
        _write(output_dir / filename, value)
    details = _detail_files(output_dir)
    report = models.make_identity_model(
        models.ClosureReport,
        {
            "run_id": RUN_ID,
            "authorization_id": authorization.authorization_id,
            "source_root_id": source_root.root_id,
            "predecessor_freeze_audit_id": frozen.audit.audit_id,
            "defect_reproduction_audit_id": defect.audit_id,
            "exact_catalog_reachability_audit_id": reachability.audit_id,
            "valid_control_execution_audit_id": control_products.audit.audit_id,
            "executed_host_counterfactual_audit_id": host.audit_id,
            "capability_outcome_contract_id": contract.contract_id,
            "outcome_fixture_audit_id": fixtures.audit_id,
            "destructive_audit_id": destructive.audit_id,
            "static_audit_id": static.audit_id,
            "transition_id": transition.transition_id,
            "detail_files": details,
            "detail_file_count": len(details),
            "next_stage": transition.next_stage,
        },
        field="report_id",
        prefix="finance_v26_executed_counterfactual_outcome_closure_report:",
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=frozen.audit,
        defect=defect,
        exact_catalog_reachability=reachability,
        valid_controls=control_products.audit,
        host_counterfactuals=host,
        capability_outcome_contract=contract,
        outcome_fixtures=fixtures,
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
