from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast, get_args

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    AuthoritativeCapabilityOutcomeRow,
    AuthoritativeJobBoundOutcomeContract,
    AuthoritativeTerminalPolicy,
    AuthoritativeTerminalRegistry,
    ComponentAttemptEvidence,
    FailureLocus,
    JobBoundAttemptTrace,
    JobComponentSequence,
    JobResultDescriptor,
    JobResultEvidencePayload,
    RawExecutionDescriptor,
    RawExecutionEvidencePayload,
    TerminalExclusionWitness,
    TerminalKind,
    evaluate_exact_evidence_set,
    validate_authoritative_bundle,
)
from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    identity as outcome_identity,
)
from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    make_identity_model as make_outcome_identity_model,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJob,
    CapabilityDevelopmentJobManifest,
    EndpointKind,
    JobBoundRunnerContract,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    make_identity_model as make_job_identity_model,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_capability_censoring_vtdo_admission_audit_models as v166_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_preflight_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_preflight_runtime as runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight as v179,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_models as v179_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as v179_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_outcome_parent_terminal_audit as v180,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_outcome_parent_terminal_audit_models as v180_models,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_181_authoritative_outcome_terminal_preflight_v1_20260830"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_181_authoritative_outcome_terminal_preflight_v1_20260830"
)
EXPECTED_REVIEW_SHA256: Final = "3c6038e4c303f393339daf346452d6f9824704cd498629b7eb89aaf6217f679d"
EXPECTED_REVIEW_BYTE_COUNT: Final = 25_586
AUDITED_V179_COMMIT: Final = "27ac98d03d078d522cecf7a0cb290230cac63036"
AUDITED_V180_IMPLEMENTATION_COMMIT: Final = "a9f8435f375a1e2a4da21b29e1f9d1917f3e964c"
V180_DIR: Final = v180.OUTPUT_DIR
V179_DIR: Final = v179.OUTPUT_DIR
V166_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_166_bounded_policy_capability_censoring_vtdo_admission_audit_v1_20260828"
)
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/authoritative_job_bound_outcome.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_outcome_terminal_preflight_runtime.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_outcome_terminal_preflight_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_authoritative_outcome_terminal_preflight.py",
)


@dataclass(frozen=True)
class FrozenInputs:
    v180_report: v180_models.AuditReport
    v180_transition: v180_models.ProspectiveTransition
    v180_parent: v180_models.ParentAuthenticityAudit
    v180_final: v180_models.FinalAbiTotalityAudit
    v180_first_action: v180_models.FirstActionReferenceTotalityAudit
    v180_outer: v180_models.OuterTerminalTotalityAudit
    manifest: CapabilityDevelopmentJobManifest
    runner: JobBoundRunnerContract
    profile_audit: v179_models.GenerationProfileBindingAudit
    scripted: v179_models.ScriptedDenominatorPreflightAudit
    branches: v179_models.RunnerBranchControlAudit
    terminal_matrix: v166_models.TerminalEndpointSchemaAudit


@dataclass(frozen=True)
class EvidenceCatalogs:
    raws: tuple[RawExecutionDescriptor, ...]
    results: tuple[JobResultDescriptor, ...]
    traces: tuple[JobBoundAttemptTrace, ...]
    rows: tuple[AuthoritativeCapabilityOutcomeRow, ...]


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.181 cannot resolve the trusted_data_synthesis package root")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", warnings=False)
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
        raise ValueError(f"v26.181 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.181 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _binding(*, path: Path, relative_path: str, source_kind: str) -> models.FileBinding:
    return models.FileBinding(
        relative_path=relative_path,
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
        source_kind=cast(Any, source_kind),
    )


def _authorization(path: Path) -> models.ExternalAuditAuthorization:
    if _sha256(path) != EXPECTED_REVIEW_SHA256:
        raise ValueError("v26.181 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.181 external audit byte count does not match Authorization")
    return cast(
        models.ExternalAuditAuthorization,
        models.make_identity_model(
            models.ExternalAuditAuthorization,
            {
                "review_sha256": EXPECTED_REVIEW_SHA256,
                "review_byte_count": EXPECTED_REVIEW_BYTE_COUNT,
                "audited_v179_commit": AUDITED_V179_COMMIT,
                "audited_v180_implementation_commit": AUDITED_V180_IMPLEMENTATION_COMMIT,
                "consumed_stage": models.AUTHORIZED_STAGE,
            },
            field="authorization_id",
            prefix="finance_v26_authoritative_outcome_external_authorization:",
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
        _binding(path=path, relative_path=relative, source_kind="implementation_source")
        for relative, path in sorted(files.items())
    )
    return cast(
        models.TransitiveSourceRoot,
        models.make_identity_model(
            models.TransitiveSourceRoot,
            {
                "entry_modules": entry_modules,
                "files": bindings,
                "file_count": len(bindings),
                "unresolved_imports": tuple(sorted(unresolved)),
                "unresolved_import_count": len(unresolved),
            },
            field="root_id",
            prefix="finance_v26_authoritative_outcome_transitive_source_root:",
        ),
    )


def _load_frozen_inputs(package_root: Path) -> FrozenInputs:
    v180_dir = package_root / V180_DIR
    v179_dir = package_root / V179_DIR
    return FrozenInputs(
        v180_report=v180_models.AuditReport.model_validate(_load(v180_dir / "report.json")),
        v180_transition=v180_models.ProspectiveTransition.model_validate(
            _load(v180_dir / "prospective_transition_contract.json")
        ),
        v180_parent=v180_models.ParentAuthenticityAudit.model_validate(
            _load(v180_dir / "empirical_parent_authenticity_audit.json")
        ),
        v180_final=v180_models.FinalAbiTotalityAudit.model_validate(
            _load(v180_dir / "final_abi_terminal_totality_audit.json")
        ),
        v180_first_action=v180_models.FirstActionReferenceTotalityAudit.model_validate(
            _load(v180_dir / "first_action_reference_totality_audit.json")
        ),
        v180_outer=v180_models.OuterTerminalTotalityAudit.model_validate(
            _load(v180_dir / "outer_terminal_totality_audit.json")
        ),
        manifest=CapabilityDevelopmentJobManifest.model_validate(
            _load(v179_dir / "development_job_manifest.json")
        ),
        runner=JobBoundRunnerContract.model_validate(
            _load(v179_dir / "job_bound_runner_contract.json")
        ),
        profile_audit=v179_models.GenerationProfileBindingAudit.model_validate(
            _load(v179_dir / "generation_profile_binding_audit.json")
        ),
        scripted=v179_models.ScriptedDenominatorPreflightAudit.model_validate(
            _load(v179_dir / "scripted_denominator_preflight_audit.json")
        ),
        branches=v179_models.RunnerBranchControlAudit.model_validate(
            _load(v179_dir / "runner_branch_control_audit.json")
        ),
        terminal_matrix=v166_models.TerminalEndpointSchemaAudit.model_validate(
            _load(package_root / V166_DIR / "terminal_endpoint_schema_audit.json")
        ),
    )


def _predecessor_freeze(
    package_root: Path,
) -> tuple[models.V180PredecessorFreezeAudit, FrozenInputs]:
    source_dir = package_root / V180_DIR
    paths = tuple(sorted(path for path in source_dir.iterdir() if path.is_file()))
    if len(paths) != 14:
        raise ValueError("v26.180 authoritative formal directory is not exactly 14 files")
    frozen = _load_frozen_inputs(package_root)
    if (
        frozen.v180_report.next_stage != models.AUTHORIZED_STAGE
        or frozen.v180_transition.next_stage != models.AUTHORIZED_STAGE
    ):
        raise ValueError("v26.180 report or Transition differs from the audited stage")
    with tempfile.TemporaryDirectory(prefix="finance-v26-181-v180-rebuild-") as temporary:
        rebuild_dir = Path(temporary)
        v180.build(
            package_root=package_root,
            output_dir=rebuild_dir,
            external_audit_path=source_dir / "external_v179_revision_result_audit.txt",
        )
        rebuilt = tuple(sorted(path for path in rebuild_dir.iterdir() if path.is_file()))
        if len(rebuilt) != len(paths):
            raise ValueError("v26.180 independent rebuild file count differs")
        for source_path in paths:
            candidate = rebuild_dir / source_path.name
            if not candidate.is_file() or candidate.read_bytes() != source_path.read_bytes():
                raise ValueError(f"v26.180 independent rebuild differs:{source_path.name}")
    bindings = tuple(
        _binding(
            path=path,
            relative_path=f"{V180_DIR}/{path.name}",
            source_kind="predecessor_artifact",
        )
        for path in paths
    )
    audit = cast(
        models.V180PredecessorFreezeAudit,
        models.make_identity_model(
            models.V180PredecessorFreezeAudit,
            {
                "predecessor_report_id": frozen.v180_report.report_id,
                "predecessor_transition_id": frozen.v180_transition.transition_id,
                "predecessor_next_stage": frozen.v180_transition.next_stage,
                "predecessor_files": bindings,
            },
            field="audit_id",
            prefix="finance_v26_v180_predecessor_freeze_audit:",
        ),
    )
    return audit, frozen


def _measurement_scope(frozen: FrozenInputs) -> models.V180MeasurementScopeAudit:
    if (
        frozen.v180_parent.attack_count != 6
        or frozen.v180_parent.current_estimator_acceptance_count != 6
        or frozen.v180_final.production_runner_exception_type != "ValidationError"
        or frozen.v180_outer.endpoint_class_count != 6
        or frozen.v180_report.online_execution_authorized
    ):
        raise ValueError("v26.180 retained negative evidence changed")
    return cast(
        models.V180MeasurementScopeAudit,
        models.make_identity_model(
            models.V180MeasurementScopeAudit,
            {"predecessor_report_id": frozen.v180_report.report_id},
            field="audit_id",
            prefix="finance_v26_v180_measurement_scope_audit:",
        ),
    )


def _terminal_registry(
    *,
    package_root: Path,
    frozen: FrozenInputs,
) -> models.TerminalRegistryDerivationAudit:
    profile = frozen.profile_audit.profile
    v166_labels = {
        f"v166.case:{item.case_name}": item.case_id for item in frozen.terminal_matrix.cases
    }
    v179_labels = {
        f"v179.endpoint:{item}": frozen.runner.runner_id for item in get_args(EndpointKind)
    }
    v180_labels = {
        f"v180.outer:{item.endpoint_kind}": item.row_id for item in frozen.v180_outer.rows
    }
    profile_values = {
        "model_config_id": profile.model_config_id,
        "thinking_policy_id": profile.thinking_policy_id,
        "action_grammar_id": profile.action_grammar_id,
        "final_grammar_id": profile.final_grammar_id,
        "bounded_generation_policy_id": profile.bounded_generation_policy_id,
        "resource_contract_id": profile.resource_contract_id,
    }
    profile_labels = {f"profile.parent:{name}": value for name, value in profile_values.items()}
    source_parents = {
        **v166_labels,
        **v179_labels,
        **v180_labels,
        **profile_labels,
    }
    source_labels = tuple(sorted(source_parents))
    if (
        len(v166_labels) != 8
        or len(v179_labels) != 6
        or len(v180_labels) != 6
        or len(profile_labels) != 6
        or len(source_labels) != 26
    ):
        raise ValueError("authoritative terminal source registries changed")

    labels_by_terminal: dict[TerminalKind, tuple[str, ...]] = {
        "completed_qualified": (
            "v166.case:completed_endpoint",
            "v179.endpoint:completed_qualified",
        ),
        "completed_invalid": (
            "v166.case:model_result_failure",
            "v179.endpoint:completed_invalid",
        ),
        "first_response_abi_invalid": (
            "v166.case:typed_semantic_rejection",
            "v179.endpoint:first_response_abi_invalid",
            "profile.parent:action_grammar_id",
        ),
        "correction_response_abi_invalid": (
            "v166.case:typed_semantic_rejection",
            "v179.endpoint:correction_response_abi_invalid",
            "profile.parent:action_grammar_id",
        ),
        "first_action_reference_invalid": (
            "v166.case:typed_semantic_rejection",
            "profile.parent:action_grammar_id",
        ),
        "correction_action_reference_invalid": (
            "v166.case:typed_semantic_rejection",
            "v179.endpoint:correction_action_reference_invalid",
            "profile.parent:action_grammar_id",
        ),
        "correction_attempt_typed_invalid": (
            "v166.case:typed_semantic_rejection",
            "v179.endpoint:correction_attempt_typed_invalid",
        ),
        "final_response_abi_invalid": (
            "v166.case:typed_semantic_rejection",
            "profile.parent:final_grammar_id",
        ),
        "provider_failure_no_payload": ("v180.outer:provider_failure_no_payload",),
        "provider_transport_failure": (
            "v166.case:transport_endpoint",
            "v180.outer:provider_transport_failure",
        ),
        "privacy_rejection": (
            "v166.case:privacy_endpoint",
            "v180.outer:privacy_rejection",
        ),
        "resource_budget_exhausted": (
            "v180.outer:resource_budget_exhausted",
            "profile.parent:resource_contract_id",
        ),
        "instrument_failure": (
            "v166.case:instrument_endpoint",
            "v180.outer:instrument_failure",
        ),
        "provider_identity_failure": (
            "v180.outer:provider_identity_thinking_usage_failure",
            "profile.parent:model_config_id",
        ),
        "thinking_integrity_failure": (
            "v180.outer:provider_identity_thinking_usage_failure",
            "profile.parent:thinking_policy_id",
        ),
        "usage_integrity_failure": (
            "v180.outer:provider_identity_thinking_usage_failure",
            "profile.parent:thinking_policy_id",
        ),
        "policy_horizon_exhausted": (
            "v166.case:policy_horizon",
            "profile.parent:bounded_generation_policy_id",
        ),
        "measurement_support_exit": ("v166.case:measurement_support_exit",),
    }
    consumed = tuple(sorted({label for labels in labels_by_terminal.values() for label in labels}))
    if consumed != source_labels:
        raise ValueError("authoritative terminal normalization leaves a source label unmapped")

    runner_source = (
        package_root / "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime.py"
    )
    runner_text = runner_source.read_text(encoding="utf-8")
    exclusion_specs: dict[TerminalKind, tuple[str, tuple[str, ...]]] = {
        "policy_horizon_exhausted": (
            "frozen_step_runtime_has_no_ordinary_detour_or_policy_horizon_branch",
            ("policy_horizon", "ordinary_detour"),
        ),
        "measurement_support_exit": (
            "frozen_development_step_runtime_has_no_measurement_support_callback_or_exit",
            ("measurement_support", "support_exit"),
        ),
    }
    witnesses: dict[TerminalKind, TerminalExclusionWitness] = {}
    for terminal_kind, (reason, tokens) in exclusion_specs.items():
        token_counts = {token: runner_text.count(token) for token in tokens}
        witnesses[terminal_kind] = cast(
            TerminalExclusionWitness,
            make_outcome_identity_model(
                TerminalExclusionWitness,
                {
                    "terminal_kind": terminal_kind,
                    "frozen_runner_id": frozen.runner.runner_id,
                    "frozen_runner_source_sha256": _sha256(runner_source),
                    "exact_parent_ids": tuple(
                        sorted(source_parents[label] for label in labels_by_terminal[terminal_kind])
                    ),
                    "exclusion_reason_code": reason,
                    "excluded_branch_token_counts": token_counts,
                },
                field="witness_id",
                prefix="capability_authoritative_terminal_exclusion_witness:",
            ),
        )

    false_model_terminals = {
        "first_response_abi_invalid",
        "correction_response_abi_invalid",
        "first_action_reference_invalid",
        "correction_action_reference_invalid",
        "correction_attempt_typed_invalid",
        "final_response_abi_invalid",
    }
    null_outer_terminals = {
        "provider_failure_no_payload",
        "provider_transport_failure",
        "privacy_rejection",
        "resource_budget_exhausted",
        "instrument_failure",
        "provider_identity_failure",
        "thinking_integrity_failure",
        "usage_integrity_failure",
        "measurement_support_exit",
    }
    policies: list[AuthoritativeTerminalPolicy] = []
    for terminal_kind_value in get_args(TerminalKind):
        terminal_kind = cast(TerminalKind, terminal_kind_value)
        values: tuple[
            bool | None,
            bool | None,
            bool | None,
            bool | None,
            bool,
            bool,
        ]
        if terminal_kind == "completed_qualified":
            values = (True, True, True, True, True, True)
        elif terminal_kind == "completed_invalid":
            values = (False, False, False, False, True, False)
        elif terminal_kind in false_model_terminals:
            values = (False, False, False, False, False, False)
        elif terminal_kind == "policy_horizon_exhausted":
            values = (False, False, False, False, False, False)
        elif terminal_kind in null_outer_terminals:
            values = (None, None, None, None, False, False)
        else:
            raise ValueError(f"terminal policy is missing:{terminal_kind}")
        task, base, mechanism, qualified, verifier, mapping = values
        witness = witnesses.get(terminal_kind)
        status = (
            "not_applicable_with_independent_exclusion_witness"
            if witness is not None
            else "reachable"
        )
        labels = tuple(sorted(labels_by_terminal[terminal_kind]))
        policies.append(
            cast(
                AuthoritativeTerminalPolicy,
                make_outcome_identity_model(
                    AuthoritativeTerminalPolicy,
                    {
                        "terminal_kind": terminal_kind,
                        "registration_status": status,
                        "source_labels": labels,
                        "source_parent_ids": tuple(
                            sorted({source_parents[label] for label in labels})
                        ),
                        "exclusion_witness_id": (
                            witness.witness_id if witness is not None else None
                        ),
                        "expected_task_completion": task,
                        "expected_base_validity": base,
                        "expected_mechanism_qualification": mechanism,
                        "expected_qualified_validity": qualified,
                        "expected_task_verifier_invoked": verifier,
                        "expected_mapping_eligible": mapping,
                    },
                    field="policy_id",
                    prefix="capability_authoritative_terminal_policy:",
                ),
            )
        )
    registry = cast(
        AuthoritativeTerminalRegistry,
        make_outcome_identity_model(
            AuthoritativeTerminalRegistry,
            {
                "v166_terminal_matrix_id": frozen.terminal_matrix.audit_id,
                "v179_runner_id": frozen.runner.runner_id,
                "v179_generation_profile_id": profile.profile_id,
                "v180_outer_terminal_audit_id": frozen.v180_outer.audit_id,
                "derivation_source_labels": source_labels,
                "consumed_derivation_source_labels": consumed,
                "policies": tuple(policies),
                "exclusion_witnesses": tuple(witnesses[item] for item in sorted(witnesses)),
            },
            field="registry_id",
            prefix="capability_authoritative_terminal_registry:",
        ),
    )
    counts = {
        status: sum(item.registration_status == status for item in registry.policies)
        for status in (
            "reachable",
            "registered_but_unreachable_under_frozen_runner",
            "not_applicable_with_independent_exclusion_witness",
        )
    }
    return cast(
        models.TerminalRegistryDerivationAudit,
        models.make_identity_model(
            models.TerminalRegistryDerivationAudit,
            {
                "v166_terminal_matrix_id": frozen.terminal_matrix.audit_id,
                "v179_runner_id": frozen.runner.runner_id,
                "v179_generation_profile_id": profile.profile_id,
                "v180_outer_terminal_audit_id": frozen.v180_outer.audit_id,
                "derivation_source_label_count": len(source_labels),
                "consumed_derivation_source_label_count": len(consumed),
                "registry": registry,
                "reachable_count": counts["reachable"],
                "registered_but_unreachable_count": counts[
                    "registered_but_unreachable_under_frozen_runner"
                ],
                "not_applicable_with_witness_count": counts[
                    "not_applicable_with_independent_exclusion_witness"
                ],
            },
            field="audit_id",
            prefix="finance_v26_authoritative_terminal_registry_derivation_audit:",
        ),
    )


def _outcome_contract(
    *,
    frozen: FrozenInputs,
    registry: AuthoritativeTerminalRegistry,
) -> AuthoritativeJobBoundOutcomeContract:
    scripted_by_job = {item.job_id: item for item in frozen.scripted.rows}
    if set(scripted_by_job) != set(frozen.manifest.expected_job_ids):
        raise ValueError("scripted reference rows do not equal the exact Manifest Job set")
    sequences: list[JobComponentSequence] = []
    for job_id in frozen.manifest.expected_job_ids:
        job = next(item for item in frozen.manifest.jobs if item.job_id == job_id)
        component_keys = tuple(
            item.component_key for item in scripted_by_job[job_id].outcome.component_attempts
        )
        if len(component_keys) != len(job.schedule_ids):
            raise ValueError("reference Component sequence differs from frozen Schedules")
        sequences.append(JobComponentSequence(job_id=job_id, ordered_component_keys=component_keys))
    return cast(
        AuthoritativeJobBoundOutcomeContract,
        make_outcome_identity_model(
            AuthoritativeJobBoundOutcomeContract,
            {
                "predecessor_manifest_id": frozen.manifest.manifest_id,
                "predecessor_runner_id": frozen.runner.runner_id,
                "terminal_registry_id": registry.registry_id,
                "job_component_sequences": tuple(sequences),
            },
            field="contract_id",
            prefix="capability_authoritative_job_bound_outcome_contract:",
        ),
    )


class _ChangedParserValidationPayload(BaseModel):
    required_value: str


def _semantic_parser_attack_count(
    grammar: Any,
) -> int:
    def sentinel_value_error(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise ValueError("sentinel after malformed Final was accepted")

    def accepted_then_later_failure(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        return {"accepted": True}

    def changed_validation_error(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        _ChangedParserValidationPayload.model_validate({})

    controls: tuple[Callable[[], Any], ...] = (
        lambda: runtime.evaluate_malformed_final_parser(
            grammar=grammar,
            parser=sentinel_value_error,
        ),
        lambda: runtime.evaluate_malformed_final_parser(
            grammar=grammar,
            escaped_exception_phase="runtime_finalize",
        ),
        lambda: runtime.evaluate_malformed_final_parser(
            grammar=grammar,
            parser=accepted_then_later_failure,
        ),
        lambda: runtime.evaluate_malformed_final_parser(
            grammar=grammar,
            parser=changed_validation_error,
        ),
    )
    rejected = 0
    for control in controls:
        try:
            control()
        except (AssertionError, ValueError):
            rejected += 1
        else:
            raise ValueError("Final parser semantic attack crossed the exact Gate")
    return rejected


def _final_parser_gate(
    *,
    frozen: FrozenInputs,
    registry: AuthoritativeTerminalRegistry,
    contract: AuthoritativeJobBoundOutcomeContract,
) -> tuple[models.FinalParserSemanticGateAudit, runtime.FinalParserSemanticResult]:
    grammar = v179_runtime.compile_qualified_final_response_grammar()
    if grammar.grammar_id != frozen.profile_audit.profile.final_grammar_id:
        raise ValueError("compiled Final Grammar differs from the frozen generation profile")
    semantic_result = runtime.evaluate_malformed_final_parser(grammar=grammar)
    job = frozen.manifest.jobs[0]
    scripted = next(item for item in frozen.scripted.rows if item.job_id == job.job_id)
    bundle = runtime.build_authoritative_bundle(
        job=job,
        manifest=frozen.manifest,
        runner=frozen.runner,
        registry=registry,
        terminal_kind="final_response_abi_invalid",
        evidence_kind="scripted_preflight_control",
        source_outcome=scripted.outcome,
        final_parser_result=semantic_result,
    )
    validate_authoritative_bundle(
        job=job,
        manifest=frozen.manifest,
        runner_id=frozen.runner.runner_id,
        registry=registry,
        contract=contract,
        raw=bundle.raw,
        result=bundle.result,
        trace=bundle.trace,
        row=bundle.row,
        expected_evidence_kind="scripted_preflight_control",
    )
    attack_rejections = _semantic_parser_attack_count(grammar)
    return (
        cast(
            models.FinalParserSemanticGateAudit,
            models.make_identity_model(
                models.FinalParserSemanticGateAudit,
                {
                    "grammar_id": grammar.grammar_id,
                    "parser_input_hash": semantic_result.parser_input_hash,
                    "parser_invocation_count": semantic_result.parser_invocation_count,
                    "parser_rejected": semantic_result.parser_rejected,
                    "parser_exception_type": semantic_result.exception_type,
                    "parser_exception_message": semantic_result.exception_message,
                    "escaped_exception_phase": semantic_result.escaped_exception_phase,
                    "semantic_attack_rejection_count": attack_rejections,
                },
                field="audit_id",
                prefix="finance_v26_final_parser_semantic_gate_audit:",
            ),
        ),
        semantic_result,
    )


def _scripted_catalogs(
    *,
    frozen: FrozenInputs,
    registry: AuthoritativeTerminalRegistry,
) -> EvidenceCatalogs:
    scripted_by_job = {item.job_id: item for item in frozen.scripted.rows}
    bundles = tuple(
        runtime.build_authoritative_bundle(
            job=job,
            manifest=frozen.manifest,
            runner=frozen.runner,
            registry=registry,
            terminal_kind="completed_qualified",
            evidence_kind="scripted_preflight_control",
            source_outcome=scripted_by_job[job.job_id].outcome,
        )
        for job in frozen.manifest.jobs
    )
    return EvidenceCatalogs(
        raws=tuple(item.raw for item in bundles),
        results=tuple(item.result for item in bundles),
        traces=tuple(item.trace for item in bundles),
        rows=tuple(item.row for item in bundles),
    )


def _evidence_dag(
    *,
    frozen: FrozenInputs,
    registry: AuthoritativeTerminalRegistry,
    contract: AuthoritativeJobBoundOutcomeContract,
) -> tuple[models.AuthoritativeEvidenceDagAudit, EvidenceCatalogs]:
    catalogs = _scripted_catalogs(frozen=frozen, registry=registry)
    evaluation = evaluate_exact_evidence_set(
        raws=catalogs.raws,
        results=catalogs.results,
        traces=catalogs.traces,
        rows=catalogs.rows,
        manifest=frozen.manifest,
        registry=registry,
        contract=contract,
        runner_id=frozen.runner.runner_id,
        expected_evidence_kind="scripted_preflight_control",
    )
    audit = cast(
        models.AuthoritativeEvidenceDagAudit,
        models.make_identity_model(
            models.AuthoritativeEvidenceDagAudit,
            {
                "contract": contract,
                "scripted_evaluation": evaluation,
            },
            field="audit_id",
            prefix="finance_v26_authoritative_evidence_dag_audit:",
        ),
    )
    return audit, catalogs


def _unknown_first_action_policy(
    *,
    package_root: Path,
    frozen: FrozenInputs,
    registry: AuthoritativeTerminalRegistry,
    contract: AuthoritativeJobBoundOutcomeContract,
) -> models.UnknownFirstActionPolicyAudit:
    predecessor = v180._runtime_predecessor(package_root)
    catalog = v179_runtime.runtime_catalog(predecessor)
    job = frozen.manifest.jobs[0]
    context = v179_runtime.prepare_job(job, catalog)
    unknown, state_token, component_key = runtime.prepare_unknown_first_action_control(
        context=context
    )
    bundle = runtime.build_authoritative_bundle(
        job=job,
        manifest=frozen.manifest,
        runner=frozen.runner,
        registry=registry,
        terminal_kind="first_action_reference_invalid",
        evidence_kind="scripted_preflight_control",
        state_token=state_token,
        component_key=component_key,
    )
    validate_authoritative_bundle(
        job=job,
        manifest=frozen.manifest,
        runner_id=frozen.runner.runner_id,
        registry=registry,
        contract=contract,
        raw=bundle.raw,
        result=bundle.result,
        trace=bundle.trace,
        row=bundle.row,
        expected_evidence_kind="scripted_preflight_control",
    )
    return cast(
        models.UnknownFirstActionPolicyAudit,
        models.make_identity_model(
            models.UnknownFirstActionPolicyAudit,
            {
                "contract_id": contract.contract_id,
                "job_id": job.job_id,
                "state_token": state_token,
                "unknown_action_id": unknown,
            },
            field="audit_id",
            prefix="finance_v26_unknown_first_action_policy_audit:",
        ),
    )


def _terminal_totality(
    *,
    frozen: FrozenInputs,
    registry: AuthoritativeTerminalRegistry,
    contract: AuthoritativeJobBoundOutcomeContract,
    semantic_result: runtime.FinalParserSemanticResult,
) -> models.TerminalTotalityAudit:
    policies = {item.terminal_kind: item for item in registry.policies}
    scripted_by_job = {item.job_id: item for item in frozen.scripted.rows}
    invalid_branch = next(
        item
        for item in frozen.branches.rows
        if item.scenario == "accepted_first_action_downstream_task_invalid"
    )
    invalid_job = next(
        item for item in frozen.manifest.jobs if item.job_id == invalid_branch.outcome.job_id
    )
    rows: list[models.TerminalTotalityControlRow] = []
    for index, terminal_kind_value in enumerate(get_args(TerminalKind)):
        terminal_kind = cast(TerminalKind, terminal_kind_value)
        job = frozen.manifest.jobs[index % len(frozen.manifest.jobs)]
        source_outcome = None
        parser_result = None
        if terminal_kind == "completed_qualified":
            source_outcome = scripted_by_job[job.job_id].outcome
        elif terminal_kind == "completed_invalid":
            job = invalid_job
            source_outcome = invalid_branch.outcome.outcome
        elif terminal_kind == "final_response_abi_invalid":
            source_outcome = scripted_by_job[job.job_id].outcome
            parser_result = semantic_result
        sequence = next(
            item.ordered_component_keys
            for item in contract.job_component_sequences
            if item.job_id == job.job_id
        )
        bundle = runtime.build_authoritative_bundle(
            job=job,
            manifest=frozen.manifest,
            runner=frozen.runner,
            registry=registry,
            terminal_kind=terminal_kind,
            evidence_kind="scripted_preflight_control",
            source_outcome=source_outcome,
            final_parser_result=parser_result,
            component_key=sequence[0],
        )
        validate_authoritative_bundle(
            job=job,
            manifest=frozen.manifest,
            runner_id=frozen.runner.runner_id,
            registry=registry,
            contract=contract,
            raw=bundle.raw,
            result=bundle.result,
            trace=bundle.trace,
            row=bundle.row,
            expected_evidence_kind="scripted_preflight_control",
        )
        policy = policies[terminal_kind]
        root_hash = canonical_hash(
            {
                "raw": bundle.raw.model_dump(mode="json"),
                "result": bundle.result.model_dump(mode="json"),
                "trace": bundle.trace.model_dump(mode="json"),
                "row": bundle.row.model_dump(mode="json"),
            },
            prefix="finance_v26_terminal_totality_control_bundle_root:",
        )
        rows.append(
            cast(
                models.TerminalTotalityControlRow,
                models.make_identity_model(
                    models.TerminalTotalityControlRow,
                    {
                        "terminal_kind": terminal_kind,
                        "policy_id": policy.policy_id,
                        "registration_status": policy.registration_status,
                        "control_bundle_root_hash": root_hash,
                        "task_completion": bundle.row.task_completion,
                        "task_verifier_invoked": bundle.row.task_verifier_invoked,
                        "base_validity": bundle.row.final_base_valid,
                        "mechanism_qualification": bundle.row.final_mechanism_qualified,
                        "qualified_validity": bundle.row.final_qualified_valid,
                        "terminal_locus_count": int(bundle.row.terminal_locus_id is not None),
                        "diagnostic_only": policy.registration_status != "reachable",
                    },
                    field="row_id",
                    prefix="finance_v26_terminal_totality_control_row:",
                ),
            )
        )
    return cast(
        models.TerminalTotalityAudit,
        models.make_identity_model(
            models.TerminalTotalityAudit,
            {"registry_id": registry.registry_id, "rows": tuple(rows)},
            field="audit_id",
            prefix="finance_v26_terminal_totality_preflight_audit:",
        ),
    )


def _constructed_rehash(
    model_type: type[BaseModel],
    source: BaseModel,
    *,
    field: str,
    prefix: str,
    updates: Mapping[str, Any],
) -> Any:
    values = {name: getattr(source, name) for name in type(source).model_fields if name != field}
    values.update(updates)
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    values[field] = outcome_identity(provisional, field, prefix)
    return model_type.model_construct(**values)


def _failure_locus_row_values(loci: Sequence[FailureLocus]) -> dict[str, str | None]:
    return {
        "first_runtime_uncommitted_locus_id": next(
            (
                item.locus_id
                for item in loci
                if item.stage
                in {"action_abi", "action_reference", "state_precondition", "operation_support"}
            ),
            None,
        ),
        "first_base_invalid_locus_id": next(
            (item.locus_id for item in loci if item.stage in {"base_answer", "base_citation"}),
            None,
        ),
        "first_mechanism_failed_locus_id": next(
            (item.locus_id for item in loci if item.stage == "mechanism"),
            None,
        ),
        "terminal_locus_id": loci[-1].locus_id if loci else None,
    }


def _cascade_bundle(
    source: runtime.AuthoritativeEvidenceBundle,
    *,
    raw_payload_updates: Mapping[str, Any] | None = None,
    raw_updates: Mapping[str, Any] | None = None,
    result_payload_updates: Mapping[str, Any] | None = None,
    result_updates: Mapping[str, Any] | None = None,
    trace_updates: Mapping[str, Any] | None = None,
    row_updates: Mapping[str, Any] | None = None,
) -> runtime.AuthoritativeEvidenceBundle:
    raw_payload = cast(
        RawExecutionEvidencePayload,
        _constructed_rehash(
            RawExecutionEvidencePayload,
            source.raw.payload,
            field="payload_id",
            prefix="capability_authoritative_raw_execution_payload:",
            updates=raw_payload_updates or {},
        ),
    )
    raw_values: dict[str, Any] = {"payload": raw_payload}
    raw_values.update(raw_updates or {})
    raw = cast(
        RawExecutionDescriptor,
        _constructed_rehash(
            RawExecutionDescriptor,
            source.raw,
            field="raw_execution_id",
            prefix="capability_authoritative_raw_execution_descriptor:",
            updates=raw_values,
        ),
    )
    loci = tuple(
        cast(
            FailureLocus,
            _constructed_rehash(
                FailureLocus,
                item,
                field="locus_id",
                prefix="capability_authoritative_failure_locus:",
                updates={"source_descriptor_id": raw.raw_execution_id},
            ),
        )
        for item in source.trace.failure_loci
    )
    result_payload_values: dict[str, Any] = {
        "raw_execution_id": raw.raw_execution_id,
        "failure_locus_ids": tuple(item.locus_id for item in loci),
    }
    result_payload_values.update(result_payload_updates or {})
    result_payload = cast(
        JobResultEvidencePayload,
        _constructed_rehash(
            JobResultEvidencePayload,
            source.result.payload,
            field="payload_id",
            prefix="capability_authoritative_job_result_payload:",
            updates=result_payload_values,
        ),
    )
    result_values: dict[str, Any] = {
        "raw_execution_id": raw.raw_execution_id,
        "payload": result_payload,
    }
    result_values.update(result_updates or {})
    result = cast(
        JobResultDescriptor,
        _constructed_rehash(
            JobResultDescriptor,
            source.result,
            field="result_id",
            prefix="capability_authoritative_job_result_descriptor:",
            updates=result_values,
        ),
    )
    trace_values: dict[str, Any] = {
        "raw_execution_id": raw.raw_execution_id,
        "result_id": result.result_id,
        "component_attempts": raw_payload.component_attempts,
        "failure_loci": loci,
        "correction_count": sum(item.correction_invoked for item in raw_payload.component_attempts),
    }
    trace_values.update(trace_updates or {})
    trace = cast(
        JobBoundAttemptTrace,
        _constructed_rehash(
            JobBoundAttemptTrace,
            source.trace,
            field="trace_id",
            prefix="capability_authoritative_job_bound_attempt_trace:",
            updates=trace_values,
        ),
    )
    row_values: dict[str, Any] = {
        "raw_execution_id": raw.raw_execution_id,
        "result_id": result.result_id,
        "trace_id": trace.trace_id,
        "correction_count": trace.correction_count,
        "task_completion": result_payload.task_completion,
        "task_verifier_invoked": result_payload.task_verifier_invoked,
        "final_result_id": result_payload.final_result_id,
        "final_base_valid": result_payload.final_base_valid,
        "final_mechanism_qualified": result_payload.final_mechanism_qualified,
        "final_qualified_valid": result_payload.final_qualified_valid,
        "first_policy_qualified_valid": bool(
            result_payload.final_qualified_valid is True and trace.correction_count == 0
        ),
        "bounded_policy_qualified_valid": result_payload.final_qualified_valid is True,
        **_failure_locus_row_values(loci),
    }
    row_values.update(row_updates or {})
    row = cast(
        AuthoritativeCapabilityOutcomeRow,
        _constructed_rehash(
            AuthoritativeCapabilityOutcomeRow,
            source.row,
            field="row_id",
            prefix="capability_authoritative_outcome_row:",
            updates=row_values,
        ),
    )
    return runtime.AuthoritativeEvidenceBundle(raw=raw, result=result, trace=trace, row=row)


def _replace_at(items: Sequence[Any], index: int, value: Any) -> tuple[Any, ...]:
    output = list(items)
    output[index] = value
    return tuple(output)


def _catalog_root(catalogs: EvidenceCatalogs, manifest_id: str) -> str:
    return canonical_hash(
        {
            "manifest_id": manifest_id,
            "raws": [item.model_dump(mode="json", warnings=False) for item in catalogs.raws],
            "results": [item.model_dump(mode="json", warnings=False) for item in catalogs.results],
            "traces": [item.model_dump(mode="json", warnings=False) for item in catalogs.traces],
            "rows": [item.model_dump(mode="json", warnings=False) for item in catalogs.rows],
        },
        prefix="finance_v26_authoritative_destructive_catalog_root:",
    )


def _evaluate_catalogs(
    *,
    catalogs: EvidenceCatalogs,
    manifest: CapabilityDevelopmentJobManifest,
    frozen: FrozenInputs,
    registry: AuthoritativeTerminalRegistry,
    contract: AuthoritativeJobBoundOutcomeContract,
) -> None:
    evaluate_exact_evidence_set(
        raws=catalogs.raws,
        results=catalogs.results,
        traces=catalogs.traces,
        rows=catalogs.rows,
        manifest=manifest,
        registry=registry,
        contract=contract,
        runner_id=frozen.runner.runner_id,
        expected_evidence_kind="scripted_preflight_control",
    )


def _mutation_result(
    *,
    name: str,
    family: str,
    mutation_root: str,
    rejection_phase: str,
    fully_rehashed_object_count: int,
    downstream_parent_rehash_count: int,
) -> models.DestructiveMutation:
    mutation_transition_id = canonical_hash(
        {"mutation_name": name, "mutation_root": mutation_root},
        prefix="finance_v26_authoritative_outcome_mutation_transition:",
    )
    mutation_report_id = canonical_hash(
        {
            "mutation_name": name,
            "mutation_transition_id": mutation_transition_id,
            "rejection_phase": rejection_phase,
        },
        prefix="finance_v26_authoritative_outcome_mutation_report:",
    )
    return cast(
        models.DestructiveMutation,
        models.make_identity_model(
            models.DestructiveMutation,
            {
                "mutation_transition_id": mutation_transition_id,
                "mutation_report_id": mutation_report_id,
                "mutation_name": name,
                "mutation_family": family,
                "fully_rehashed_object_count": fully_rehashed_object_count,
                "downstream_parent_rehash_count": downstream_parent_rehash_count,
                "rejection_phase": rejection_phase,
            },
            field="mutation_id",
            prefix="finance_v26_authoritative_outcome_destructive_mutation:",
        ),
    )


def _destructive_audit(
    *,
    frozen: FrozenInputs,
    registry: AuthoritativeTerminalRegistry,
    contract: AuthoritativeJobBoundOutcomeContract,
    baseline: EvidenceCatalogs,
) -> models.ProductionDestructiveAudit:
    bundles = tuple(
        runtime.AuthoritativeEvidenceBundle(
            raw=baseline.raws[index],
            result=baseline.results[index],
            trace=baseline.traces[index],
            row=baseline.rows[index],
        )
        for index in range(len(baseline.rows))
    )
    deep_index = next(
        index for index, item in enumerate(bundles) if len(item.trace.component_attempts) >= 2
    )
    other_index = next(
        index
        for index, item in enumerate(bundles)
        if item.trace.component_attempts[0].component_key
        != bundles[deep_index].trace.component_attempts[0].component_key
    )
    cases: list[
        tuple[
            str,
            str,
            EvidenceCatalogs,
            CapabilityDevelopmentJobManifest,
            int,
            int,
        ]
    ] = []

    row_cross = cast(
        AuthoritativeCapabilityOutcomeRow,
        _constructed_rehash(
            AuthoritativeCapabilityOutcomeRow,
            baseline.rows[1],
            field="row_id",
            prefix="capability_authoritative_outcome_row:",
            updates={
                "raw_execution_id": baseline.raws[0].raw_execution_id,
                "result_id": baseline.results[0].result_id,
                "trace_id": baseline.traces[0].trace_id,
            },
        ),
    )
    cases.append(
        (
            "cross_job_outcome_payload_reassignment",
            "predecessor_parent_attack",
            EvidenceCatalogs(
                baseline.raws,
                baseline.results,
                baseline.traces,
                _replace_at(baseline.rows, 1, row_cross),
            ),
            frozen.manifest,
            1,
            3,
        )
    )

    duplicate_raw_downstream = _cascade_bundle(
        bundles[1],
        result_payload_updates={"raw_execution_id": baseline.raws[0].raw_execution_id},
        result_updates={"raw_execution_id": baseline.raws[0].raw_execution_id},
        trace_updates={"raw_execution_id": baseline.raws[0].raw_execution_id},
        row_updates={"raw_execution_id": baseline.raws[0].raw_execution_id},
    )
    cases.append(
        (
            "duplicate_raw_execution_id_across_jobs",
            "predecessor_parent_attack",
            EvidenceCatalogs(
                _replace_at(baseline.raws, 1, baseline.raws[0]),
                _replace_at(baseline.results, 1, duplicate_raw_downstream.result),
                _replace_at(baseline.traces, 1, duplicate_raw_downstream.trace),
                _replace_at(baseline.rows, 1, duplicate_raw_downstream.row),
            ),
            frozen.manifest,
            4,
            3,
        )
    )

    duplicate_result_trace = cast(
        JobBoundAttemptTrace,
        _constructed_rehash(
            JobBoundAttemptTrace,
            baseline.traces[1],
            field="trace_id",
            prefix="capability_authoritative_job_bound_attempt_trace:",
            updates={"result_id": baseline.results[0].result_id},
        ),
    )
    duplicate_result_row = cast(
        AuthoritativeCapabilityOutcomeRow,
        _constructed_rehash(
            AuthoritativeCapabilityOutcomeRow,
            baseline.rows[1],
            field="row_id",
            prefix="capability_authoritative_outcome_row:",
            updates={
                "result_id": baseline.results[0].result_id,
                "trace_id": duplicate_result_trace.trace_id,
            },
        ),
    )
    cases.append(
        (
            "duplicate_result_id_across_jobs",
            "predecessor_parent_attack",
            EvidenceCatalogs(
                baseline.raws,
                _replace_at(baseline.results, 1, baseline.results[0]),
                _replace_at(baseline.traces, 1, duplicate_result_trace),
                _replace_at(baseline.rows, 1, duplicate_result_row),
            ),
            frozen.manifest,
            3,
            2,
        )
    )

    swapped = _cascade_bundle(
        bundles[0],
        result_payload_updates={"raw_execution_id": baseline.raws[1].raw_execution_id},
        result_updates={"raw_execution_id": baseline.raws[1].raw_execution_id},
        trace_updates={"raw_execution_id": baseline.raws[1].raw_execution_id},
        row_updates={"raw_execution_id": baseline.raws[1].raw_execution_id},
    )
    cases.append(
        (
            "swapped_raw_and_result_parents",
            "predecessor_parent_attack",
            EvidenceCatalogs(
                baseline.raws,
                _replace_at(baseline.results, 0, swapped.result),
                _replace_at(baseline.traces, 0, swapped.trace),
                _replace_at(baseline.rows, 0, swapped.row),
            ),
            frozen.manifest,
            3,
            3,
        )
    )

    unrelated_final_id = canonical_hash(
        {"attack": "result_parent_outcome_final_mismatch"},
        prefix="finance_v26_unrelated_final_result:",
    )
    result_mismatch = _cascade_bundle(
        bundles[0],
        result_payload_updates={"final_result_id": unrelated_final_id},
        row_updates={"final_result_id": bundles[0].row.final_result_id},
    )
    cases.append(
        (
            "result_parent_outcome_final_mismatch",
            "predecessor_parent_attack",
            EvidenceCatalogs(
                _replace_at(baseline.raws, 0, result_mismatch.raw),
                _replace_at(baseline.results, 0, result_mismatch.result),
                _replace_at(baseline.traces, 0, result_mismatch.trace),
                _replace_at(baseline.rows, 0, result_mismatch.row),
            ),
            frozen.manifest,
            4,
            3,
        )
    )

    duplicate_trace_row = cast(
        AuthoritativeCapabilityOutcomeRow,
        _constructed_rehash(
            AuthoritativeCapabilityOutcomeRow,
            baseline.rows[1],
            field="row_id",
            prefix="capability_authoritative_outcome_row:",
            updates={"trace_id": baseline.traces[0].trace_id},
        ),
    )
    cases.append(
        (
            "duplicate_attempt_trace_across_jobs",
            "predecessor_parent_attack",
            EvidenceCatalogs(
                baseline.raws,
                baseline.results,
                _replace_at(baseline.traces, 1, baseline.traces[0]),
                _replace_at(baseline.rows, 1, duplicate_trace_row),
            ),
            frozen.manifest,
            2,
            1,
        )
    )

    forged_raw_id = canonical_hash(
        {"attack": "same_raw_content_different_forged_ids"},
        prefix="finance_v26_forged_raw_identity:",
    )
    forged_raw = baseline.raws[1].model_copy(update={"raw_execution_id": forged_raw_id})
    forged_raw_downstream = _cascade_bundle(
        bundles[1],
        result_payload_updates={"raw_execution_id": forged_raw_id},
        result_updates={"raw_execution_id": forged_raw_id},
        trace_updates={"raw_execution_id": forged_raw_id},
        row_updates={"raw_execution_id": forged_raw_id},
    )
    cases.append(
        (
            "same_raw_content_different_forged_ids",
            "content_identity_attack",
            EvidenceCatalogs(
                _replace_at(baseline.raws, 1, forged_raw),
                _replace_at(baseline.results, 1, forged_raw_downstream.result),
                _replace_at(baseline.traces, 1, forged_raw_downstream.trace),
                _replace_at(baseline.rows, 1, forged_raw_downstream.row),
            ),
            frozen.manifest,
            4,
            3,
        )
    )

    forged_result_id = canonical_hash(
        {"attack": "same_result_content_different_forged_ids"},
        prefix="finance_v26_forged_result_identity:",
    )
    forged_result = baseline.results[1].model_copy(update={"result_id": forged_result_id})
    forged_result_trace = cast(
        JobBoundAttemptTrace,
        _constructed_rehash(
            JobBoundAttemptTrace,
            baseline.traces[1],
            field="trace_id",
            prefix="capability_authoritative_job_bound_attempt_trace:",
            updates={"result_id": forged_result_id},
        ),
    )
    forged_result_row = cast(
        AuthoritativeCapabilityOutcomeRow,
        _constructed_rehash(
            AuthoritativeCapabilityOutcomeRow,
            baseline.rows[1],
            field="row_id",
            prefix="capability_authoritative_outcome_row:",
            updates={"result_id": forged_result_id, "trace_id": forged_result_trace.trace_id},
        ),
    )
    cases.append(
        (
            "same_result_content_different_forged_ids",
            "content_identity_attack",
            EvidenceCatalogs(
                baseline.raws,
                _replace_at(baseline.results, 1, forged_result),
                _replace_at(baseline.traces, 1, forged_result_trace),
                _replace_at(baseline.rows, 1, forged_result_row),
            ),
            frozen.manifest,
            3,
            2,
        )
    )

    duplicate_bytes_trace_id = canonical_hash(
        {"attack": "unique_trace_ids_duplicate_canonical_bytes"},
        prefix="finance_v26_forged_trace_identity:",
    )
    duplicate_bytes_trace = baseline.traces[0].model_copy(
        update={"trace_id": duplicate_bytes_trace_id}
    )
    duplicate_bytes_row = cast(
        AuthoritativeCapabilityOutcomeRow,
        _constructed_rehash(
            AuthoritativeCapabilityOutcomeRow,
            baseline.rows[1],
            field="row_id",
            prefix="capability_authoritative_outcome_row:",
            updates={"trace_id": duplicate_bytes_trace_id},
        ),
    )
    cases.append(
        (
            "unique_trace_ids_duplicate_canonical_bytes",
            "content_identity_attack",
            EvidenceCatalogs(
                baseline.raws,
                baseline.results,
                _replace_at(baseline.traces, 1, duplicate_bytes_trace),
                _replace_at(baseline.rows, 1, duplicate_bytes_row),
            ),
            frozen.manifest,
            2,
            1,
        )
    )

    deep = bundles[deep_index]
    truncated = _cascade_bundle(
        deep,
        raw_payload_updates={"component_attempts": deep.raw.payload.component_attempts[:-1]},
    )
    cases.append(
        (
            "component_attempt_truncation",
            "attempt_trace_attack",
            EvidenceCatalogs(
                _replace_at(baseline.raws, deep_index, truncated.raw),
                _replace_at(baseline.results, deep_index, truncated.result),
                _replace_at(baseline.traces, deep_index, truncated.trace),
                _replace_at(baseline.rows, deep_index, truncated.row),
            ),
            frozen.manifest,
            6,
            4,
        )
    )

    spliced_attempts = (
        bundles[other_index].raw.payload.component_attempts[0],
        *deep.raw.payload.component_attempts[1:],
    )
    spliced = _cascade_bundle(
        deep,
        raw_payload_updates={"component_attempts": spliced_attempts},
    )
    cases.append(
        (
            "component_attempt_splicing",
            "attempt_trace_attack",
            EvidenceCatalogs(
                _replace_at(baseline.raws, deep_index, spliced.raw),
                _replace_at(baseline.results, deep_index, spliced.result),
                _replace_at(baseline.traces, deep_index, spliced.trace),
                _replace_at(baseline.rows, deep_index, spliced.row),
            ),
            frozen.manifest,
            6,
            4,
        )
    )

    reordered_attempts = tuple(
        cast(
            ComponentAttemptEvidence,
            _constructed_rehash(
                ComponentAttemptEvidence,
                item,
                field="attempt_id",
                prefix="capability_authoritative_component_attempt:",
                updates={"component_index": index},
            ),
        )
        for index, item in enumerate(reversed(deep.raw.payload.component_attempts))
    )
    reordered = _cascade_bundle(
        deep,
        raw_payload_updates={"component_attempts": reordered_attempts},
    )
    cases.append(
        (
            "component_attempt_reordering",
            "attempt_trace_attack",
            EvidenceCatalogs(
                _replace_at(baseline.raws, deep_index, reordered.raw),
                _replace_at(baseline.results, deep_index, reordered.result),
                _replace_at(baseline.traces, deep_index, reordered.trace),
                _replace_at(baseline.rows, deep_index, reordered.row),
            ),
            frozen.manifest,
            len(reordered_attempts) + 5,
            4,
        )
    )

    inner_job_mismatch = _cascade_bundle(
        bundles[0],
        raw_payload_updates={"job_id": frozen.manifest.jobs[1].job_id},
    )
    cases.append(
        (
            "inner_outcome_job_parent_mismatch",
            "job_parent_attack",
            EvidenceCatalogs(
                _replace_at(baseline.raws, 0, inner_job_mismatch.raw),
                _replace_at(baseline.results, 0, inner_job_mismatch.result),
                _replace_at(baseline.traces, 0, inner_job_mismatch.trace),
                _replace_at(baseline.rows, 0, inner_job_mismatch.row),
            ),
            frozen.manifest,
            5,
            4,
        )
    )

    final_row_mismatch = cast(
        AuthoritativeCapabilityOutcomeRow,
        _constructed_rehash(
            AuthoritativeCapabilityOutcomeRow,
            baseline.rows[0],
            field="row_id",
            prefix="capability_authoritative_outcome_row:",
            updates={"final_result_id": unrelated_final_id},
        ),
    )
    cases.append(
        (
            "final_result_descriptor_mismatch",
            "job_parent_attack",
            EvidenceCatalogs(
                baseline.raws,
                baseline.results,
                baseline.traces,
                _replace_at(baseline.rows, 0, final_row_mismatch),
            ),
            frozen.manifest,
            1,
            1,
        )
    )

    crossed_path = _cascade_bundle(
        bundles[0],
        raw_updates={"raw_artifact_path": baseline.raws[1].raw_artifact_path},
    )
    cases.append(
        (
            "correct_namespace_cross_job_artifact_path",
            "artifact_parent_attack",
            EvidenceCatalogs(
                _replace_at(baseline.raws, 0, crossed_path.raw),
                _replace_at(baseline.results, 0, crossed_path.result),
                _replace_at(baseline.traces, 0, crossed_path.trace),
                _replace_at(baseline.rows, 0, crossed_path.row),
            ),
            frozen.manifest,
            5,
            4,
        )
    )

    source_job = frozen.manifest.jobs[0]
    fake_job_values = source_job.model_dump(mode="python", exclude={"job_id"})
    fake_job_values["deterministic_seed_id"] = canonical_hash(
        {"attack": "package_replica_same_manifest_job_replaced"},
        prefix="finance_v26_replaced_job_seed:",
    )
    fake_job = cast(
        CapabilityDevelopmentJob,
        make_job_identity_model(
            CapabilityDevelopmentJob,
            fake_job_values,
            field="job_id",
            prefix="capability_job_bound_development_job:",
        ),
    )
    attacked_jobs = (fake_job, *frozen.manifest.jobs[1:])
    attacked_manifest_values = frozen.manifest.model_dump(mode="python", exclude={"manifest_id"})
    attacked_manifest_values.update(
        jobs=attacked_jobs,
        expected_job_ids=tuple(sorted(item.job_id for item in attacked_jobs)),
    )
    attacked_manifest = cast(
        CapabilityDevelopmentJobManifest,
        make_job_identity_model(
            CapabilityDevelopmentJobManifest,
            attacked_manifest_values,
            field="manifest_id",
            prefix="capability_job_bound_development_manifest:",
        ),
    )
    cases.append(
        (
            "package_replica_same_manifest_job_replaced",
            "job_parent_attack",
            baseline,
            attacked_manifest,
            2,
            2,
        )
    )

    fake_job_row = cast(
        AuthoritativeCapabilityOutcomeRow,
        _constructed_rehash(
            AuthoritativeCapabilityOutcomeRow,
            baseline.rows[0],
            field="row_id",
            prefix="capability_authoritative_outcome_row:",
            updates={"job_id": fake_job.job_id},
        ),
    )
    cases.append(
        (
            "missing_real_job_plus_extra_fake_job",
            "job_parent_attack",
            EvidenceCatalogs(
                baseline.raws,
                baseline.results,
                baseline.traces,
                _replace_at(baseline.rows, 0, fake_job_row),
            ),
            frozen.manifest,
            1,
            1,
        )
    )

    cases.append(
        (
            "outer_terminal_row_missing",
            "terminal_totality_attack",
            EvidenceCatalogs(
                baseline.raws,
                baseline.results,
                baseline.traces,
                baseline.rows[:-1],
            ),
            frozen.manifest,
            1,
            2,
        )
    )
    cases.append(
        (
            "outer_terminal_row_duplicate",
            "terminal_totality_attack",
            EvidenceCatalogs(
                baseline.raws,
                baseline.results,
                baseline.traces,
                (*baseline.rows, baseline.rows[0]),
            ),
            frozen.manifest,
            1,
            2,
        )
    )

    terminal_mismatch = _cascade_bundle(
        bundles[0],
        raw_payload_updates={"terminal_kind": "provider_failure_no_payload"},
    )
    cases.append(
        (
            "raw_terminal_result_terminal_mismatch",
            "terminal_totality_attack",
            EvidenceCatalogs(
                _replace_at(baseline.raws, 0, terminal_mismatch.raw),
                _replace_at(baseline.results, 0, terminal_mismatch.result),
                _replace_at(baseline.traces, 0, terminal_mismatch.trace),
                _replace_at(baseline.rows, 0, terminal_mismatch.row),
            ),
            frozen.manifest,
            5,
            4,
        )
    )

    provider_bundle = runtime.build_authoritative_bundle(
        job=frozen.manifest.jobs[0],
        manifest=frozen.manifest,
        runner=frozen.runner,
        registry=registry,
        terminal_kind="provider_failure_no_payload",
        evidence_kind="scripted_preflight_control",
    )
    foreign_provider_bundle = runtime.build_authoritative_bundle(
        job=frozen.manifest.jobs[1],
        manifest=frozen.manifest,
        runner=frozen.runner,
        registry=registry,
        terminal_kind="provider_failure_no_payload",
        evidence_kind="scripted_preflight_control",
    )
    provider_baseline = EvidenceCatalogs(
        _replace_at(baseline.raws, 0, provider_bundle.raw),
        _replace_at(baseline.results, 0, provider_bundle.result),
        _replace_at(baseline.traces, 0, provider_bundle.trace),
        _replace_at(baseline.rows, 0, provider_bundle.row),
    )
    _evaluate_catalogs(
        catalogs=provider_baseline,
        manifest=frozen.manifest,
        frozen=frozen,
        registry=registry,
        contract=contract,
    )
    replaced_provider = _cascade_bundle(
        provider_bundle,
        raw_payload_updates={
            "provider_artifact_ids": foreign_provider_bundle.raw.payload.provider_artifact_ids
        },
    )
    cases.append(
        (
            "provider_transport_artifact_parent_replacement",
            "artifact_parent_attack",
            EvidenceCatalogs(
                _replace_at(provider_baseline.raws, 0, replaced_provider.raw),
                _replace_at(provider_baseline.results, 0, replaced_provider.result),
                _replace_at(provider_baseline.traces, 0, replaced_provider.trace),
                _replace_at(provider_baseline.rows, 0, replaced_provider.row),
            ),
            frozen.manifest,
            6,
            5,
        )
    )

    mutations: list[models.DestructiveMutation] = []
    for name, family, catalogs, manifest, object_count, parent_count in cases:
        root = _catalog_root(catalogs, manifest.manifest_id)
        try:
            _evaluate_catalogs(
                catalogs=catalogs,
                manifest=manifest,
                frozen=frozen,
                registry=registry,
                contract=contract,
            )
        except (AssertionError, ValidationError, ValueError) as exc:
            phase = f"{type(exc).__name__}:{exc}"
        else:
            raise ValueError(f"authoritative destructive attack was accepted:{name}")
        mutations.append(
            _mutation_result(
                name=name,
                family=family,
                mutation_root=root,
                rejection_phase=phase,
                fully_rehashed_object_count=object_count,
                downstream_parent_rehash_count=parent_count,
            )
        )

    grammar = v179_runtime.compile_qualified_final_response_grammar()

    def sentinel_value_error(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise ValueError("sentinel ValueError substitution")

    def accepted_then_later_failure(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        return {"accepted": True}

    def changed_validation_error(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        _ChangedParserValidationPayload.model_validate({})

    parser_cases: tuple[tuple[str, Callable[[], Any]], ...] = (
        (
            "parser_validationerror_to_sentinel_valueerror",
            lambda: runtime.evaluate_malformed_final_parser(
                grammar=grammar, parser=sentinel_value_error
            ),
        ),
        (
            "parser_rejected_wrong_exception_phase",
            lambda: runtime.evaluate_malformed_final_parser(
                grammar=grammar, escaped_exception_phase="runtime_finalize"
            ),
        ),
        (
            "parser_accepted_then_later_runtime_failure",
            lambda: runtime.evaluate_malformed_final_parser(
                grammar=grammar, parser=accepted_then_later_failure
            ),
        ),
        (
            "parser_exception_reason_changed",
            lambda: runtime.evaluate_malformed_final_parser(
                grammar=grammar, parser=changed_validation_error
            ),
        ),
    )
    for name, control in parser_cases:
        root = canonical_hash(
            {
                "mutation_name": name,
                "grammar_id": grammar.grammar_id,
                "profile_id": frozen.profile_audit.profile.profile_id,
            },
            prefix="finance_v26_final_parser_destructive_control_root:",
        )
        try:
            control()
        except (AssertionError, ValidationError, ValueError) as exc:
            phase = f"{type(exc).__name__}:{exc}"
        else:
            raise ValueError(f"Final parser destructive attack was accepted:{name}")
        mutations.append(
            _mutation_result(
                name=name,
                family="final_parser_semantic_attack",
                mutation_root=root,
                rejection_phase=phase,
                fully_rehashed_object_count=3,
                downstream_parent_rehash_count=2,
            )
        )
    if len(mutations) != 25:
        raise ValueError("authoritative destructive denominator is not exactly 25")
    return cast(
        models.ProductionDestructiveAudit,
        models.make_identity_model(
            models.ProductionDestructiveAudit,
            {
                "contract_id": contract.contract_id,
                "registry_id": registry.registry_id,
                "mutations": tuple(mutations),
            },
            field="audit_id",
            prefix="finance_v26_authoritative_outcome_production_destructive_audit:",
        ),
    )


def _gate(
    name: str,
    condition: bool,
    *,
    layer: str,
    evidence: str,
) -> models.MetaGate:
    if not condition:
        raise ValueError(f"v26.181 meta-Gate failed:{name}:{evidence}")
    return models.MetaGate(
        gate_name=name,
        layer=cast(Any, layer),
        evidence=evidence,
    )


def _meta_gates(
    *,
    authorization: models.ExternalAuditAuthorization,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.V180PredecessorFreezeAudit,
    scope: models.V180MeasurementScopeAudit,
    registry: models.TerminalRegistryDerivationAudit,
    contract: AuthoritativeJobBoundOutcomeContract,
    final: models.FinalParserSemanticGateAudit,
    dag: models.AuthoritativeEvidenceDagAudit,
    totality: models.TerminalTotalityAudit,
    unknown: models.UnknownFirstActionPolicyAudit,
    destructive: models.ProductionDestructiveAudit,
) -> models.AuditIntegrityMetaGateAudit:
    gates = (
        _gate(
            "external_audit_binding",
            authorization.review_sha256 == EXPECTED_REVIEW_SHA256,
            layer="audit_construction_integrity",
            evidence=f"{authorization.review_byte_count}:{authorization.review_sha256}",
        ),
        _gate(
            "audit_implementation_commit_distinguished",
            authorization.audited_v180_implementation_commit == AUDITED_V180_IMPLEMENTATION_COMMIT,
            layer="audit_construction_integrity",
            evidence=authorization.audited_v180_implementation_commit,
        ),
        _gate(
            "transitive_source_closure",
            source_root.unresolved_import_count == 0,
            layer="audit_construction_integrity",
            evidence=f"files={source_root.file_count}",
        ),
        _gate(
            "v180_exact_file_freeze",
            predecessor.predecessor_file_count == 14,
            layer="audit_construction_integrity",
            evidence="14/14 files bound",
        ),
        _gate(
            "v180_byte_identical_rebuild",
            predecessor.independent_rebuild_match_count == 14,
            layer="audit_construction_integrity",
            evidence="14/14 files match",
        ),
        _gate(
            "v180_negative_parent_facts_retained",
            scope.negative_parent_authenticity_facts_retained,
            layer="audit_construction_integrity",
            evidence="6/6 old parent attacks remain accepted by the old estimator",
        ),
        _gate(
            "v180_runtime_non_totality_retained",
            scope.runtime_non_totality_facts_retained,
            layer="audit_construction_integrity",
            evidence="Final and unknown first-Action negative facts retained",
        ),
        _gate(
            "historical_final_validationerror_retained",
            scope.historical_malformed_final_exception_type == "ValidationError",
            layer="audit_construction_integrity",
            evidence=scope.historical_malformed_final_exception_type,
        ),
        _gate(
            "old_formal_parser_gate_not_promoted",
            not scope.old_formal_parser_rejection_gate_closed,
            layer="scientific_admission_boundary",
            evidence="old sentinel ambiguity remains explicitly false",
        ),
        _gate(
            "old_terminal_registry_marked_unknown",
            scope.old_complete_terminal_registry_claim == "unknown",
            layer="scientific_admission_boundary",
            evidence="six old outer classes are not treated as exhaustive",
        ),
        _gate(
            "old_static_gates_narrowed_to_meta_gates",
            scope.old_static_gate_interpretation
            == "audit_integrity_and_defect_reproduction_meta_gates",
            layer="scientific_admission_boundary",
            evidence=scope.old_static_gate_interpretation,
        ),
        _gate(
            "terminal_source_registry_exact_set",
            registry.derivation_source_label_count == 26,
            layer="preflight_contract_integrity",
            evidence="8 v26.166 + 6 v26.179 + 6 v26.180 + 6 profile labels",
        ),
        _gate(
            "terminal_source_registry_no_omission",
            registry.unmapped_source_label_count == 0,
            layer="preflight_contract_integrity",
            evidence="26/26 source labels consumed",
        ),
        _gate(
            "terminal_kind_exact_set",
            registry.terminal_kind_count == 18,
            layer="preflight_contract_integrity",
            evidence="18 orthogonal terminal kinds",
        ),
        _gate(
            "terminal_status_partition",
            registry.reachable_count
            + registry.registered_but_unreachable_count
            + registry.not_applicable_with_witness_count
            == 18,
            layer="preflight_contract_integrity",
            evidence=(
                f"{registry.reachable_count}/"
                f"{registry.registered_but_unreachable_count}/"
                f"{registry.not_applicable_with_witness_count}"
            ),
        ),
        _gate(
            "terminal_exclusion_witnesses",
            registry.not_applicable_with_witness_count == 2,
            layer="preflight_contract_integrity",
            evidence="policy Horizon and Measurement Support each have source-bound witnesses",
        ),
        _gate(
            "policy_horizon_source_exclusion",
            next(
                item
                for item in registry.registry.exclusion_witnesses
                if item.terminal_kind == "policy_horizon_exhausted"
            ).applicable_branch_count
            == 0,
            layer="preflight_contract_integrity",
            evidence="frozen Runner has no ordinary-Detour/Horizon branch",
        ),
        _gate(
            "measurement_support_source_exclusion",
            next(
                item
                for item in registry.registry.exclusion_witnesses
                if item.terminal_kind == "measurement_support_exit"
            ).applicable_branch_count
            == 0,
            layer="preflight_contract_integrity",
            evidence="frozen Runner has no Measurement Support callback/exit",
        ),
        _gate(
            "exact_job_component_sequences",
            len(contract.job_component_sequences) == 192,
            layer="preflight_contract_integrity",
            evidence="192 content-bound Component sequences",
        ),
        _gate(
            "contract_manifest_parent",
            contract.predecessor_manifest_id == dag.scripted_evaluation.manifest_id,
            layer="preflight_contract_integrity",
            evidence=contract.predecessor_manifest_id,
        ),
        _gate(
            "final_parser_exact_grammar",
            final.grammar_id != "",
            layer="preflight_contract_integrity",
            evidence=final.grammar_id,
        ),
        _gate(
            "final_parser_validationerror_semantics",
            final.parser_rejected and final.parser_exception_type == "ValidationError",
            layer="preflight_contract_integrity",
            evidence=final.parser_exception_type,
        ),
        _gate(
            "final_parser_boundary_phase",
            final.escaped_exception_phase == "final_parser",
            layer="preflight_contract_integrity",
            evidence=final.escaped_exception_phase,
        ),
        _gate(
            "final_parser_typed_projection",
            final.typed_final_abi_invalid_bundle_count == 1 and final.exact_outcome_row_count == 1,
            layer="preflight_contract_integrity",
            evidence="one typed final_response_abi_invalid control",
        ),
        _gate(
            "final_parser_semantic_attacks",
            final.semantic_attack_rejection_count == 4,
            layer="preflight_contract_integrity",
            evidence="4/4 semantic parser attacks rejected",
        ),
        _gate(
            "exact_raw_descriptor_set",
            dag.raw_descriptor_count == 192 and dag.unique_raw_descriptor_count == 192,
            layer="preflight_contract_integrity",
            evidence="192/192 Raw descriptors",
        ),
        _gate(
            "exact_result_descriptor_set",
            dag.result_descriptor_count == 192 and dag.unique_result_descriptor_count == 192,
            layer="preflight_contract_integrity",
            evidence="192/192 Result descriptors",
        ),
        _gate(
            "exact_attempt_trace_set",
            dag.job_bound_trace_count == 192 and dag.unique_trace_count == 192,
            layer="preflight_contract_integrity",
            evidence="192/192 Job-bound AttemptTraces",
        ),
        _gate(
            "exact_outcome_row_set",
            dag.scripted_outcome_row_count == 192 and dag.unique_row_count == 192,
            layer="preflight_contract_integrity",
            evidence="192/192 scripted Outcome rows",
        ),
        _gate(
            "exact_job_set_bijection",
            dag.scripted_evaluation.exact_job_set_match,
            layer="preflight_contract_integrity",
            evidence="Job -> Raw -> Result -> Trace -> Outcome exact set",
        ),
        _gate(
            "artifact_path_parent_reconstruction",
            dag.raw_path_parent_match_count == 192 and dag.result_path_parent_match_count == 192,
            layer="preflight_contract_integrity",
            evidence="384/384 Job-owned paths",
        ),
        _gate(
            "scripted_rows_not_empirical",
            not dag.scripted_evaluation.empirical and dag.formal_empirical_row_count == 0,
            layer="scientific_admission_boundary",
            evidence="reference controls only; empirical rows=0",
        ),
        _gate(
            "typed_failure_locus_projection",
            sum(item.terminal_locus_count for item in totality.rows) == 17,
            layer="preflight_contract_integrity",
            evidence="17 failure terminals bind a strict terminal locus",
        ),
        _gate(
            "unknown_first_action_policy_frozen",
            unknown.frozen_policy == "immediate_typed_terminal_without_correction",
            layer="preflight_contract_integrity",
            evidence=unknown.frozen_policy,
        ),
        _gate(
            "terminal_totality_exact_controls",
            totality.exact_outcome_row_count == 18 and totality.exactly_one_projection_count == 18,
            layer="preflight_contract_integrity",
            evidence="18/18 terminal controls project exactly once",
        ),
        _gate(
            "terminal_totality_no_exception_escape",
            totality.exception_escape_count == 0 and dag.python_exception_escape_count == 0,
            layer="preflight_contract_integrity",
            evidence="Python/Pydantic/ValueError escape count=0",
        ),
        _gate(
            "expanded_destructive_denominator",
            destructive.mutation_count == 25 and destructive.rejection_count == 25,
            layer="preflight_contract_integrity",
            evidence="25/25 production mutations rejected",
        ),
        _gate(
            "mutation_transition_report_rehash",
            destructive.transition_report_rehash_count == 25,
            layer="preflight_contract_integrity",
            evidence="25/25 mutation Transitions and Reports rehashed",
        ),
        _gate(
            "zero_provider_and_development_outcomes",
            authorization.provider_execution_authorized is False,
            layer="scientific_admission_boundary",
            evidence="Provider=0; Development outcomes=0",
        ),
        _gate(
            "zero_formal_empirical_rows_and_estimates",
            dag.formal_empirical_row_count + dag.formal_empirical_estimate_count == 0,
            layer="scientific_admission_boundary",
            evidence="formal empirical rows=0; estimates=0",
        ),
        _gate(
            "online_execution_remains_blocked",
            True,
            layer="scientific_admission_boundary",
            evidence="independent credential-free post-preflight audit required",
        ),
    )
    return cast(
        models.AuditIntegrityMetaGateAudit,
        models.make_identity_model(
            models.AuditIntegrityMetaGateAudit,
            {
                "gates": gates,
                "gate_count": len(gates),
                "passed_gate_count": len(gates),
            },
            field="audit_id",
            prefix="finance_v26_authoritative_outcome_meta_gate_audit:",
        ),
    )


def _transition(
    *,
    authorization: models.ExternalAuditAuthorization,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.V180PredecessorFreezeAudit,
    scope: models.V180MeasurementScopeAudit,
    registry: models.TerminalRegistryDerivationAudit,
    contract: AuthoritativeJobBoundOutcomeContract,
    final: models.FinalParserSemanticGateAudit,
    dag: models.AuthoritativeEvidenceDagAudit,
    totality: models.TerminalTotalityAudit,
    unknown: models.UnknownFirstActionPolicyAudit,
    destructive: models.ProductionDestructiveAudit,
    meta: models.AuditIntegrityMetaGateAudit,
) -> models.ProspectiveTransition:
    return cast(
        models.ProspectiveTransition,
        models.make_identity_model(
            models.ProspectiveTransition,
            {
                "authorization_id": authorization.authorization_id,
                "source_root_id": source_root.root_id,
                "predecessor_freeze_audit_id": predecessor.audit_id,
                "measurement_scope_audit_id": scope.audit_id,
                "terminal_registry_audit_id": registry.audit_id,
                "outcome_contract_id": contract.contract_id,
                "final_parser_gate_audit_id": final.audit_id,
                "evidence_dag_audit_id": dag.audit_id,
                "terminal_totality_audit_id": totality.audit_id,
                "unknown_action_policy_audit_id": unknown.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "meta_gate_audit_id": meta.audit_id,
                "consumed_stage": models.AUTHORIZED_STAGE,
                "next_stage": models.NEXT_STAGE,
            },
            field="transition_id",
            prefix="finance_v26_authoritative_outcome_preflight_transition:",
        ),
    )


def _detail_files(output_dir: Path) -> tuple[models.FileBinding, ...]:
    return tuple(
        _binding(
            path=path,
            relative_path=f"{OUTPUT_DIR}/{path.name}",
            source_kind="formal_detail",
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
    predecessor, frozen = _predecessor_freeze(package_root)
    scope = _measurement_scope(frozen)
    registry = _terminal_registry(package_root=package_root, frozen=frozen)
    contract = _outcome_contract(frozen=frozen, registry=registry.registry)
    final, semantic_result = _final_parser_gate(
        frozen=frozen,
        registry=registry.registry,
        contract=contract,
    )
    dag, catalogs = _evidence_dag(
        frozen=frozen,
        registry=registry.registry,
        contract=contract,
    )
    unknown = _unknown_first_action_policy(
        package_root=package_root,
        frozen=frozen,
        registry=registry.registry,
        contract=contract,
    )
    totality = _terminal_totality(
        frozen=frozen,
        registry=registry.registry,
        contract=contract,
        semantic_result=semantic_result,
    )
    destructive = _destructive_audit(
        frozen=frozen,
        registry=registry.registry,
        contract=contract,
        baseline=catalogs,
    )
    meta = _meta_gates(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor,
        scope=scope,
        registry=registry,
        contract=contract,
        final=final,
        dag=dag,
        totality=totality,
        unknown=unknown,
        destructive=destructive,
    )
    transition = _transition(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor,
        scope=scope,
        registry=registry,
        contract=contract,
        final=final,
        dag=dag,
        totality=totality,
        unknown=unknown,
        destructive=destructive,
        meta=meta,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(
        output_dir / "external_v180_revision_report_audit.txt",
        external_audit_path.read_bytes(),
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("v180_predecessor_freeze_audit.json", predecessor),
        ("v180_measurement_scope_audit.json", scope),
        ("authoritative_terminal_registry_audit.json", registry),
        ("authoritative_job_bound_outcome_contract.json", contract),
        ("final_parser_semantic_gate_audit.json", final),
        ("authoritative_evidence_dag_audit.json", dag),
        ("terminal_totality_preflight_audit.json", totality),
        ("unknown_first_action_policy_audit.json", unknown),
        ("production_destructive_audit.json", destructive),
        ("audit_integrity_meta_gate_audit.json", meta),
        ("prospective_transition_contract.json", transition),
    )
    for filename, value in outputs:
        _write(output_dir / filename, value)
    details = _detail_files(output_dir)
    report = cast(
        models.PreflightReport,
        models.make_identity_model(
            models.PreflightReport,
            {
                "run_id": RUN_ID,
                "audited_v179_commit": AUDITED_V179_COMMIT,
                "audited_v180_implementation_commit": (AUDITED_V180_IMPLEMENTATION_COMMIT),
                "audit_implementation_source_root_id": source_root.root_id,
                "authorization_id": authorization.authorization_id,
                "predecessor_freeze_audit_id": predecessor.audit_id,
                "measurement_scope_audit_id": scope.audit_id,
                "terminal_registry_audit_id": registry.audit_id,
                "outcome_contract_id": contract.contract_id,
                "final_parser_gate_audit_id": final.audit_id,
                "evidence_dag_audit_id": dag.audit_id,
                "terminal_totality_audit_id": totality.audit_id,
                "unknown_action_policy_audit_id": unknown.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "meta_gate_audit_id": meta.audit_id,
                "transition_id": transition.transition_id,
                "detail_files": details,
                "detail_file_count": len(details),
                "next_stage": transition.next_stage,
            },
            field="report_id",
            prefix="finance_v26_authoritative_outcome_preflight_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor,
        measurement_scope=scope,
        terminal_registry=registry,
        outcome_contract=contract,
        final_parser_gate=final,
        evidence_dag=dag,
        terminal_totality=totality,
        unknown_action_policy=unknown,
        destructive=destructive,
        meta_gates=meta,
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
