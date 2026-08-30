from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast, get_args

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJobManifest,
    EmpiricalCapabilityOutcomeRow,
    EndpointKind,
    FrozenGenerationProfile,
    JobBoundOutcomePayload,
    JobBoundRunnerContract,
    ScriptedPreflightOutcomeRow,
    evaluate_empirical_capability_estimands,
)
from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    make_identity_model as make_outcome_identity_model,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback as v177,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history as v176,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history_models as v176_models,
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
    phase1_v26_capability_job_bound_outcome_parent_terminal_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_state_local_presentation_parent_hardening_models as v175_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_causal_reaudit_models as v171_models,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_180_job_bound_parent_terminal_audit_v1_20260830"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_180_job_bound_parent_terminal_audit_v1_20260830"
)
EXPECTED_REVIEW_SHA256: Final = "f2da2aef728d78964a6c6b0060382f55a91937dc86c029c5cd7b8fdd9f7cdd78"
EXPECTED_REVIEW_BYTE_COUNT: Final = 22_294
AUDITED_COMMIT: Final = "27ac98d03d078d522cecf7a0cb290230cac63036"
V179_DIR: Final = v179.OUTPUT_DIR
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_job_bound_outcome_parent_terminal_audit_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_job_bound_outcome_parent_terminal_audit.py",
)
OUTER_ENDPOINTS: Final = (
    "provider_failure_no_payload",
    "provider_transport_failure",
    "privacy_rejection",
    "resource_budget_exhausted",
    "instrument_failure",
    "provider_identity_thinking_usage_failure",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.180 cannot resolve the trusted_data_synthesis package root")


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
        raise ValueError(f"v26.180 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.180 immutable output already exists:{path}")
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
        raise ValueError("v26.180 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.180 external audit byte count does not match Authorization")
    return cast(
        models.ExternalAuditAuthorization,
        models.make_identity_model(
            models.ExternalAuditAuthorization,
            {
                "review_sha256": EXPECTED_REVIEW_SHA256,
                "review_byte_count": EXPECTED_REVIEW_BYTE_COUNT,
                "audited_commit": AUDITED_COMMIT,
                "consumed_stage": models.CONSUMED_STAGE,
            },
            field="authorization_id",
            prefix="finance_v26_job_bound_parent_terminal_external_authorization:",
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
            prefix="finance_v26_job_bound_parent_terminal_transitive_source_root:",
        ),
    )


@dataclass(frozen=True)
class FrozenV179:
    report: v179_models.PreflightReport
    transition: v179_models.ProspectiveTransition
    manifest: CapabilityDevelopmentJobManifest
    profile_audit: v179_models.GenerationProfileBindingAudit
    runner: JobBoundRunnerContract
    prefix: v179_models.AcceptedPrefixSurfaceAudit
    scripted: v179_models.ScriptedDenominatorPreflightAudit
    branches: v179_models.RunnerBranchControlAudit
    empirical_schema: v179_models.EmpiricalOutcomeSchemaAudit


def _predecessor_freeze(
    package_root: Path,
) -> tuple[models.V179PredecessorFreezeAudit, FrozenV179]:
    source_dir = package_root / V179_DIR
    paths = tuple(sorted(path for path in source_dir.iterdir() if path.is_file()))
    if len(paths) != 18:
        raise ValueError("v26.179 authoritative formal directory is not exactly 18 files")
    report = v179_models.PreflightReport.model_validate(_load(source_dir / "report.json"))
    transition = v179_models.ProspectiveTransition.model_validate(
        _load(source_dir / "prospective_transition_contract.json")
    )
    manifest = CapabilityDevelopmentJobManifest.model_validate(
        _load(source_dir / "development_job_manifest.json")
    )
    profile_audit = v179_models.GenerationProfileBindingAudit.model_validate(
        _load(source_dir / "generation_profile_binding_audit.json")
    )
    runner = JobBoundRunnerContract.model_validate(
        _load(source_dir / "job_bound_runner_contract.json")
    )
    prefix = v179_models.AcceptedPrefixSurfaceAudit.model_validate(
        _load(source_dir / "accepted_prefix_surface_audit.json")
    )
    scripted = v179_models.ScriptedDenominatorPreflightAudit.model_validate(
        _load(source_dir / "scripted_denominator_preflight_audit.json")
    )
    branches = v179_models.RunnerBranchControlAudit.model_validate(
        _load(source_dir / "runner_branch_control_audit.json")
    )
    empirical_schema = v179_models.EmpiricalOutcomeSchemaAudit.model_validate(
        _load(source_dir / "empirical_outcome_schema_audit.json")
    )
    if report.next_stage != models.CONSUMED_STAGE or transition.next_stage != models.CONSUMED_STAGE:
        raise ValueError("v26.179 report or Transition differs from the audited next stage")
    with tempfile.TemporaryDirectory(prefix="finance-v26-180-v179-rebuild-") as temporary:
        rebuild_dir = Path(temporary)
        v179.build(
            package_root=package_root,
            output_dir=rebuild_dir,
            external_audit_path=source_dir / "external_v178_latest_revision_source_audit.txt",
        )
        rebuilt = tuple(sorted(path for path in rebuild_dir.iterdir() if path.is_file()))
        if len(rebuilt) != len(paths):
            raise ValueError("v26.179 independent rebuild file count differs")
        for source_path in paths:
            candidate = rebuild_dir / source_path.name
            if not candidate.is_file() or candidate.read_bytes() != source_path.read_bytes():
                raise ValueError(f"v26.179 independent rebuild differs:{source_path.name}")
    bindings = tuple(
        _binding(
            path=path,
            relative_path=f"{V179_DIR}/{path.name}",
            source_kind="predecessor_artifact",
        )
        for path in paths
    )
    audit = cast(
        models.V179PredecessorFreezeAudit,
        models.make_identity_model(
            models.V179PredecessorFreezeAudit,
            {
                "predecessor_report_id": report.report_id,
                "predecessor_transition_id": transition.transition_id,
                "predecessor_next_stage": transition.next_stage,
                "predecessor_files": bindings,
            },
            field="audit_id",
            prefix="finance_v26_v179_predecessor_freeze_audit:",
        ),
    )
    return audit, FrozenV179(
        report=report,
        transition=transition,
        manifest=manifest,
        profile_audit=profile_audit,
        runner=runner,
        prefix=prefix,
        scripted=scripted,
        branches=branches,
        empirical_schema=empirical_schema,
    )


def _runtime_predecessor(package_root: Path) -> v177.PredecessorObjects:
    v176_dir = package_root / v176.OUTPUT_DIR
    return v177.PredecessorObjects(
        report=v176_models.HardeningReport.model_validate(_load(v176_dir / "report.json")),
        transition=v176_models.ProspectiveTransition.model_validate(
            _load(v176_dir / "prospective_transition_contract.json")
        ),
        development=v176_models.AuthoritativeDevelopmentCatalog.model_validate(
            _load(v176_dir / "authoritative_development_catalog.json")
        ),
        runner=v176_models.AuthoritativeRunnerInputCatalog.model_validate(
            _load(v176_dir / "authoritative_runner_input_catalog.json")
        ),
        schedules=v175_models.StateLocalScheduleCatalog.model_validate(
            _load(package_root / v176.V175_DIR / "state_local_schedule_catalog.json")
        ),
        source=v171_models.ValiditySeparatedDevelopmentCatalog.model_validate(
            _load(package_root / v176.V171_DIR / "validity_separated_development_catalog.json")
        ),
    )


def _claim_scope(frozen: FrozenV179) -> models.V179ClaimScopeAudit:
    if (
        frozen.manifest.job_count != 192
        or frozen.scripted.row_count != 192
        or frozen.prefix.source_choice_combination_count != 772
        or frozen.prefix.replica_execution_count != 4_632
        or frozen.prefix.history_dependent_acceptance_row_count != 0
        or frozen.branches.scenario_count != 11
        or frozen.report.provider_calls != 0
        or frozen.report.empirical_outcome_row_count != 0
    ):
        raise ValueError("v26.179 retained local-preflight evidence changed")
    two_corrections = next(
        item for item in frozen.branches.rows if item.scenario == "two_component_corrections"
    )
    if two_corrections.outcome.outcome.correction_count != 2:
        raise ValueError("v26.179 multicomponent correction result changed")
    return cast(
        models.V179ClaimScopeAudit,
        models.make_identity_model(
            models.V179ClaimScopeAudit,
            {"predecessor_report_id": frozen.report.report_id},
            field="audit_id",
            prefix="finance_v26_v179_outcome_claim_scope_audit:",
        ),
    )


def _empirical_row(
    scripted: ScriptedPreflightOutcomeRow,
    *,
    outcome: JobBoundOutcomePayload,
    raw_execution_id: str,
    result_id: str,
) -> EmpiricalCapabilityOutcomeRow:
    values = {
        "job_id": scripted.job_id,
        "manifest_id": scripted.manifest_id,
        "execution_package_id": scripted.execution_package_id,
        "source_package_artifact_id": scripted.source_package_artifact_id,
        "replica_index": scripted.replica_index,
        "attempt_trace_id": outcome.attempt_trace_id,
        "raw_namespace": scripted.raw_namespace,
        "result_namespace": scripted.result_namespace,
        "raw_execution_id": raw_execution_id,
        "result_id": result_id,
        "outcome": outcome,
    }
    return cast(
        EmpiricalCapabilityOutcomeRow,
        make_outcome_identity_model(
            EmpiricalCapabilityOutcomeRow,
            values,
            field="row_id",
            prefix="capability_empirical_job_bound_outcome_row:",
        ),
    )


def _attack_result(
    *,
    control_index: int,
    attack_name: str,
    rows: Sequence[EmpiricalCapabilityOutcomeRow],
    manifest: CapabilityDevelopmentJobManifest,
) -> models.ParentAuthenticityAttackResult:
    evaluation = evaluate_empirical_capability_estimands(rows, manifest=manifest)
    values = {
        "control_index": control_index,
        "attack_name": attack_name,
        "row_count": len(rows),
        "fully_rehashed_row_count": len(rows),
        "unique_row_id_count": len({item.row_id for item in rows}),
        "unique_job_id_count": len({item.job_id for item in rows}),
        "unique_raw_execution_id_count": len({item.raw_execution_id for item in rows}),
        "unique_result_id_count": len({item.result_id for item in rows}),
        "unique_attempt_trace_id_count": len({item.attempt_trace_id for item in rows}),
        "exact_manifest_job_set_match": evaluation.exact_job_set_match,
        "current_estimator_accepted": True,
        "q_first_fraction": evaluation.q_first_fraction,
        "q_bounded_correction_fraction": evaluation.q_bounded_correction_fraction,
        "defect_reproduced": True,
        "empirical_evidence": False,
    }
    return cast(
        models.ParentAuthenticityAttackResult,
        models.make_identity_model(
            models.ParentAuthenticityAttackResult,
            values,
            field="attack_id",
            prefix="finance_v26_job_bound_parent_authenticity_attack:",
        ),
    )


def _parent_authenticity(frozen: FrozenV179) -> models.ParentAuthenticityAudit:
    scripted = frozen.scripted.rows
    if len(scripted) != 192 or not all(
        item.outcome.bounded_policy_qualified_valid for item in scripted
    ):
        raise ValueError("v26.179 scripted parent-attack source denominator changed")
    outcomes = tuple(item.outcome for item in scripted)
    raw_ids = tuple(f"audit_raw:{item.job_id}" for item in scripted)
    result_ids = tuple(f"audit_result:{item.job_id}" for item in scripted)

    def rows_for(
        selected_outcomes: Sequence[JobBoundOutcomePayload],
        selected_raw_ids: Sequence[str],
        selected_result_ids: Sequence[str],
    ) -> tuple[EmpiricalCapabilityOutcomeRow, ...]:
        if not (
            len(selected_outcomes)
            == len(selected_raw_ids)
            == len(selected_result_ids)
            == len(scripted)
        ):
            raise ValueError("parent-attack vector length changed")
        return tuple(
            _empirical_row(
                source,
                outcome=selected_outcomes[index],
                raw_execution_id=selected_raw_ids[index],
                result_id=selected_result_ids[index],
            )
            for index, source in enumerate(scripted)
        )

    rotated_outcomes = (*outcomes[1:], outcomes[0])
    rotated_raw = (*raw_ids[1:], raw_ids[0])
    rotated_result = (*result_ids[1:], result_ids[0])
    mismatched_results = tuple(
        canonical_hash(
            {"job_id": item.job_id, "declared_parent": "unrelated_outcome_and_final"},
            prefix="audit_mismatched_result_parent:",
        )
        for item in scripted
    )
    row_sets = (
        (
            "cross_job_outcome_payload_reassignment",
            rows_for(rotated_outcomes, raw_ids, result_ids),
        ),
        (
            "duplicate_raw_execution_id_across_jobs",
            rows_for(outcomes, ("audit_raw:shared",) * 192, result_ids),
        ),
        (
            "duplicate_result_id_across_jobs",
            rows_for(outcomes, raw_ids, ("audit_result:shared",) * 192),
        ),
        (
            "swapped_raw_and_result_parents",
            rows_for(outcomes, rotated_raw, rotated_result),
        ),
        (
            "result_parent_outcome_final_mismatch",
            rows_for(outcomes, raw_ids, mismatched_results),
        ),
        (
            "duplicate_attempt_trace_across_jobs",
            rows_for((outcomes[0],) * 192, raw_ids, result_ids),
        ),
    )
    attacks = tuple(
        _attack_result(
            control_index=index,
            attack_name=name,
            rows=rows,
            manifest=frozen.manifest,
        )
        for index, (name, rows) in enumerate(row_sets, start=1)
    )
    if (
        attacks[1].unique_raw_execution_id_count != 1
        or attacks[2].unique_result_id_count != 1
        or attacks[5].unique_attempt_trace_id_count != 1
        or any(item.unique_job_id_count != 192 for item in attacks)
    ):
        raise ValueError("v26.180 parent-authenticity attacks did not realize their targets")
    return cast(
        models.ParentAuthenticityAudit,
        models.make_identity_model(
            models.ParentAuthenticityAudit,
            {
                "manifest_id": frozen.manifest.manifest_id,
                "predecessor_empirical_schema_audit_id": frozen.empirical_schema.audit_id,
                "attacks": attacks,
            },
            field="audit_id",
            prefix="finance_v26_empirical_outcome_parent_authenticity_audit:",
        ),
    )


def _qualified_payload_with_final_abi_false(
    source: JobBoundOutcomePayload,
) -> JobBoundOutcomePayload:
    values = source.model_dump(mode="python", exclude={"attempt_trace_id"})
    values["final_response_abi_valid"] = False
    return cast(
        JobBoundOutcomePayload,
        make_outcome_identity_model(
            JobBoundOutcomePayload,
            values,
            field="attempt_trace_id",
            prefix="capability_job_attempt_trace:",
        ),
    )


def _final_abi_totality(
    *,
    package_root: Path,
    frozen: FrozenV179,
    predecessor: v177.PredecessorObjects,
) -> models.FinalAbiTotalityAudit:
    promoted = _qualified_payload_with_final_abi_false(frozen.scripted.rows[0].outcome)
    if (
        promoted.final_response_abi_valid is not False
        or promoted.final_qualified_valid is not True
        or promoted.bounded_policy_qualified_valid is not True
        or promoted.endpoint_kind != "completed_qualified"
    ):
        raise ValueError("Final-ABI false promotion control did not reproduce the defect")
    registered = "final_response_abi_invalid" in get_args(EndpointKind)
    if registered:
        raise ValueError("v26.179 unexpectedly registers a Final-ABI-invalid endpoint")

    catalog = v179_runtime.runtime_catalog(predecessor)
    context = v179_runtime.prepare_job(frozen.manifest.jobs[0], catalog)
    action_grammar = v179_runtime.compile_semantic_action_response_grammar()
    final_grammar = v179_runtime.compile_qualified_final_response_grammar()
    profile = frozen.profile_audit.profile
    invocation_count = 0
    original = v179_runtime._parse_final_fixture

    def parse_malformed_final(
        result: Any,
        source: Any,
        *,
        grammar: Any,
        profile: FrozenGenerationProfile,
    ) -> None:
        del source
        nonlocal invocation_count
        invocation_count += 1
        terminal_state_id = canonical_hash(
            tuple(item.observation.receipt_id for item in result.steps),
            prefix="capability_job_bound_terminal_state:",
        )
        envelope = v179_runtime.make_qualified_final_host_envelope(
            grammar=grammar,
            terminal_state_id=terminal_state_id,
            terminal_commit_id=result.result_id,
        )
        v179_runtime.parse_qualified_final_response({}, grammar=grammar, envelope=envelope)
        raise ValueError("malformed Final unexpectedly crossed the exact Final Grammar")

    returned_trace = False
    error: Exception | None = None
    v179_runtime._parse_final_fixture = parse_malformed_final
    try:
        v179_runtime.execute_trace(
            context=context,
            manifest_id=frozen.manifest.manifest_id,
            scenario="audit_final_response_abi_invalid",
            profile=profile,
            action_grammar=action_grammar,
            final_grammar=final_grammar,
            exact_denominator=False,
        )
        returned_trace = True
    except Exception as exc:  # The defect is precisely an escaping terminal exception.
        error = exc
    finally:
        v179_runtime._parse_final_fixture = original
    if returned_trace or error is None or invocation_count != 1:
        raise ValueError("malformed Final did not expose the frozen Runner totality defect")
    return cast(
        models.FinalAbiTotalityAudit,
        models.make_identity_model(
            models.FinalAbiTotalityAudit,
            {
                "promoted_payload_id": promoted.attempt_trace_id,
                "final_abi_false_qualified_payload_accepted": True,
                "final_response_abi_invalid_endpoint_registered": registered,
                "invalid_final_parser_rejected": True,
                "production_runner_final_parser_invocation_count": invocation_count,
                "production_runner_returned_trace": returned_trace,
                "production_runner_exception_type": type(error).__name__,
                "production_runner_exception_message": str(error),
                "typed_final_abi_invalid_outcome_count": 0,
                "exact_outcome_row_count": 0,
                "verifier_null_policy_proven": False,
                "qualified_false_policy_proven": False,
            },
            field="audit_id",
            prefix="finance_v26_final_abi_terminal_totality_audit:",
        ),
    )


def _first_action_reference_totality(
    *,
    frozen: FrozenV179,
    predecessor: v177.PredecessorObjects,
) -> models.FirstActionReferenceTotalityAudit:
    catalog = v179_runtime.runtime_catalog(predecessor)
    context = v179_runtime.prepare_job(frozen.manifest.jobs[0], catalog)
    action_grammar = v179_runtime.compile_semantic_action_response_grammar()
    final_grammar = v179_runtime.compile_qualified_final_response_grammar()
    profile = frozen.profile_audit.profile
    selected: str | None = None

    def unknown_first_action(
        state: Any,
        prompt: Any,
        rows: tuple[Any, ...],
        component_index: int,
    ) -> v179_runtime.ResponseSelection:
        del prompt
        nonlocal selected
        nonce = 0
        current_ids = {item.action_id for item in rows}
        while True:
            candidate = canonical_hash(
                {
                    "package_id": state.package_id,
                    "component_index": component_index,
                    "nonce": nonce,
                },
                prefix="audit_unknown_first_action:",
            ).split(":", 1)[1][:24]
            if candidate not in current_ids and candidate not in state.seen_public_action_ids:
                selected = candidate
                return v179_runtime.ResponseSelection(candidate)
            nonce += 1

    returned_trace = False
    error: Exception | None = None
    try:
        v179_runtime.execute_trace(
            context=context,
            manifest_id=frozen.manifest.manifest_id,
            scenario="audit_unknown_first_action",
            profile=profile,
            action_grammar=action_grammar,
            final_grammar=final_grammar,
            first_selector=unknown_first_action,
            exact_denominator=False,
        )
        returned_trace = True
    except Exception as exc:  # The old Runner raises after successful ABI parsing.
        error = exc
    if (
        returned_trace
        or error is None
        or selected is None
        or str(error) != "ABI-valid first response references an absent current Action"
    ):
        raise ValueError("unknown first-Action control did not reproduce the Runner defect")
    registered = "first_action_reference_invalid" in get_args(EndpointKind)
    if registered:
        raise ValueError("v26.179 unexpectedly registers a first-Action reference endpoint")
    return cast(
        models.FirstActionReferenceTotalityAudit,
        models.make_identity_model(
            models.FirstActionReferenceTotalityAudit,
            {
                "unknown_action_id": selected,
                "action_abi_valid": True,
                "response_state_matches_current_state": True,
                "action_absent_from_current_candidates": True,
                "first_action_reference_invalid_endpoint_registered": registered,
                "production_runner_raised": True,
                "production_runner_exception_type": type(error).__name__,
                "production_runner_exception_message": str(error),
                "typed_outcome_count": 0,
                "exact_outcome_row_count": 0,
                "correction_policy_frozen": False,
            },
            field="audit_id",
            prefix="finance_v26_first_action_reference_terminal_totality_audit:",
        ),
    )


def _failure_field_semantics(
    *,
    package_root: Path,
    frozen: FrozenV179,
) -> models.FailureFieldSemanticsAudit:
    source = frozen.scripted.rows[0].outcome
    if not all(item.committed for item in source.component_attempts):
        raise ValueError("completed failure-field control source has an uncommitted Component")
    fake_key = "audit.fake.completed.component"
    values = source.model_dump(mode="python", exclude={"attempt_trace_id"})
    values["first_failed_component_key"] = fake_key
    promoted = cast(
        JobBoundOutcomePayload,
        make_outcome_identity_model(
            JobBoundOutcomePayload,
            values,
            field="attempt_trace_id",
            prefix="capability_job_attempt_trace:",
        ),
    )
    if promoted.first_failed_component_key != fake_key:
        raise ValueError("completed fake first-failed Component was not accepted")
    runtime_source = (
        package_root / "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime.py"
    ).read_text(encoding="utf-8")
    mechanism_fallback = (
        "if result is not None and first_failed is None:" in runtime_source
        and "result.mechanism_qualification.component_semantic_checks.get" in runtime_source
    )
    if not mechanism_fallback:
        raise ValueError("v26.179 mechanism-failure fallback source branch changed")
    fields = JobBoundOutcomePayload.model_fields
    return cast(
        models.FailureFieldSemanticsAudit,
        models.make_identity_model(
            models.FailureFieldSemanticsAudit,
            {
                "promoted_payload_id": promoted.attempt_trace_id,
                "all_components_committed": True,
                "expected_first_uncommitted_component_key": None,
                "injected_first_failed_component_key": fake_key,
                "fully_rehashed_payload_accepted": True,
                "first_uncommitted_component_key_field_present": (
                    "first_uncommitted_component_key" in fields
                ),
                "first_mechanism_failed_component_key_field_present": (
                    "first_mechanism_failed_component_key" in fields
                ),
                "old_field_has_runtime_mechanism_fallback": mechanism_fallback,
                "strict_failure_field_semantics_closed": False,
            },
            field="audit_id",
            prefix="finance_v26_first_failure_field_semantics_audit:",
        ),
    )


def _outer_terminal_totality(frozen: FrozenV179) -> models.OuterTerminalTotalityAudit:
    registered = set(get_args(EndpointKind))
    source = frozen.scripted.rows[0].outcome
    rows: list[models.OuterEndpointTotalityRow] = []
    for endpoint in OUTER_ENDPOINTS:
        if endpoint in registered:
            raise ValueError(f"v26.179 unexpectedly registers outer endpoint:{endpoint}")
        values = source.model_dump(mode="python")
        values["endpoint_kind"] = endpoint
        constructible = True
        try:
            JobBoundOutcomePayload.model_validate(values)
        except ValidationError:
            constructible = False
        if constructible:
            raise ValueError(f"v26.179 unexpectedly constructs outer endpoint:{endpoint}")
        rows.append(
            cast(
                models.OuterEndpointTotalityRow,
                models.make_identity_model(
                    models.OuterEndpointTotalityRow,
                    {
                        "endpoint_kind": endpoint,
                        "endpoint_registered_in_v179": False,
                        "job_bound_payload_constructible": False,
                        "exact_outcome_row_constructible": False,
                        "task_verifier_value_available": False,
                        "qualified_value_available": False,
                        "provider_call_executed": False,
                    },
                    field="row_id",
                    prefix="finance_v26_outer_endpoint_totality_row:",
                ),
            )
        )
    return cast(
        models.OuterTerminalTotalityAudit,
        models.make_identity_model(
            models.OuterTerminalTotalityAudit,
            {
                "rows": tuple(rows),
                "endpoint_class_count": len(rows),
                "registered_endpoint_count": 0,
                "exact_outcome_row_count": 0,
                "missing_exact_outcome_row_count": len(rows),
                "terminal_totality_closed": False,
            },
            field="audit_id",
            prefix="finance_v26_outer_terminal_totality_audit:",
        ),
    )


def _online_gate(
    *,
    parent: models.ParentAuthenticityAudit,
    final: models.FinalAbiTotalityAudit,
    first_action: models.FirstActionReferenceTotalityAudit,
    failure_field: models.FailureFieldSemanticsAudit,
    outer: models.OuterTerminalTotalityAudit,
) -> models.OnlineExecutionGate:
    return cast(
        models.OnlineExecutionGate,
        models.make_identity_model(
            models.OnlineExecutionGate,
            {
                "parent_authenticity_audit_id": parent.audit_id,
                "final_abi_totality_audit_id": final.audit_id,
                "first_action_totality_audit_id": first_action.audit_id,
                "failure_field_audit_id": failure_field.audit_id,
                "outer_terminal_totality_audit_id": outer.audit_id,
                "decision": models.FAILED_DECISION,
            },
            field="gate_id",
            prefix="finance_v26_job_bound_online_execution_gate:",
        ),
    )


def _gate(name: str, condition: bool, evidence: str) -> models.StaticGate:
    if not condition:
        raise ValueError(f"v26.180 static Gate failed:{name}:{evidence}")
    return models.StaticGate(gate_name=name, evidence=evidence)


def _static_audit(
    *,
    authorization: models.ExternalAuditAuthorization,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.V179PredecessorFreezeAudit,
    claim: models.V179ClaimScopeAudit,
    parent: models.ParentAuthenticityAudit,
    final: models.FinalAbiTotalityAudit,
    first_action: models.FirstActionReferenceTotalityAudit,
    failure_field: models.FailureFieldSemanticsAudit,
    outer: models.OuterTerminalTotalityAudit,
    online_gate: models.OnlineExecutionGate,
) -> models.StaticAudit:
    attacks = {item.attack_name: item for item in parent.attacks}
    gates = (
        _gate(
            "external_audit_binding",
            authorization.review_sha256 == EXPECTED_REVIEW_SHA256
            and authorization.review_byte_count == EXPECTED_REVIEW_BYTE_COUNT,
            f"{authorization.review_byte_count}:{authorization.review_sha256}",
        ),
        _gate(
            "transitive_source_closure",
            source_root.unresolved_import_count == 0,
            f"files={source_root.file_count}",
        ),
        _gate(
            "v179_exact_file_freeze",
            predecessor.predecessor_file_count == 18,
            "18/18 files bound",
        ),
        _gate(
            "v179_byte_identical_rebuild",
            predecessor.independent_rebuild_match_count == 18,
            "18/18 files match",
        ),
        _gate(
            "v179_local_preflight_retained",
            claim.local_scripted_runner_preflight_retained,
            "credential-free local preflight retained",
        ),
        _gate(
            "exact_job_index_retained",
            claim.exact_prospective_job_index_set_retained,
            "32 packages x 6 replicas = 192 jobs",
        ),
        _gate(
            "claim_scope_narrowed",
            not claim.exact_job_outcome_evidence_set_closed,
            claim.strongest_estimator_claim,
        ),
        _gate(
            "cross_job_outcome_reassignment_reproduced",
            attacks["cross_job_outcome_payload_reassignment"].current_estimator_accepted,
            "fully rehashed 192-row denominator accepted",
        ),
        _gate(
            "duplicate_raw_parent_reproduced",
            attacks["duplicate_raw_execution_id_across_jobs"].unique_raw_execution_id_count == 1,
            "one Raw ID accepted for 192 jobs",
        ),
        _gate(
            "duplicate_result_parent_reproduced",
            attacks["duplicate_result_id_across_jobs"].unique_result_id_count == 1,
            "one Result ID accepted for 192 jobs",
        ),
        _gate(
            "swapped_raw_result_parents_reproduced",
            attacks["swapped_raw_and_result_parents"].current_estimator_accepted,
            "rotated Raw and Result parents accepted",
        ),
        _gate(
            "result_outcome_parent_mismatch_reproduced",
            attacks["result_parent_outcome_final_mismatch"].current_estimator_accepted,
            "unrelated Result parents accepted",
        ),
        _gate(
            "duplicate_trace_parent_reproduced",
            attacks["duplicate_attempt_trace_across_jobs"].unique_attempt_trace_id_count == 1,
            "one attempt trace accepted for 192 jobs",
        ),
        _gate(
            "all_parent_authenticity_attacks_accepted",
            parent.current_estimator_acceptance_count == 6,
            "6/6 current-estimator acceptances",
        ),
        _gate(
            "final_abi_false_qualified_promotion_reproduced",
            final.final_abi_false_qualified_payload_accepted,
            final.promoted_payload_id,
        ),
        _gate(
            "final_abi_runner_non_total_reproduced",
            not final.production_runner_returned_trace
            and final.typed_final_abi_invalid_outcome_count == 0,
            final.production_runner_exception_type,
        ),
        _gate(
            "unknown_first_action_non_total_reproduced",
            first_action.production_runner_raised and first_action.typed_outcome_count == 0,
            first_action.production_runner_exception_message,
        ),
        _gate(
            "completed_fake_failure_key_reproduced",
            failure_field.fully_rehashed_payload_accepted,
            failure_field.injected_first_failed_component_key,
        ),
        _gate(
            "strict_failure_fields_absent",
            not failure_field.first_uncommitted_component_key_field_present
            and not failure_field.first_mechanism_failed_component_key_field_present,
            "both prospective fields absent",
        ),
        _gate(
            "outer_terminal_rows_missing",
            outer.missing_exact_outcome_row_count == outer.endpoint_class_count == 6,
            "6/6 outer endpoint classes lack exact rows",
        ),
        _gate(
            "all_registered_defect_controls_reproduced",
            parent.defect_reproduction_count + 2 + 1 + 1 + 1 == 11,
            "controls 1-11 reproduced",
        ),
        _gate(
            "no_authoritative_descriptors_created",
            parent.raw_execution_descriptor_count
            + parent.job_result_descriptor_count
            + parent.authoritative_job_bound_trace_count
            == 0,
            "repair objects remain unmaterialized",
        ),
        _gate(
            "no_empirical_rows_or_estimates",
            parent.formal_empirical_outcome_row_count + parent.formal_empirical_estimate_count == 0,
            "0 empirical rows; 0 estimates",
        ),
        _gate(
            "online_execution_gate_failed_closed",
            online_gate.decision == models.FAILED_DECISION
            and not online_gate.online_development_execution_authorized,
            online_gate.decision,
        ),
        _gate(
            "zero_provider_and_model_execution",
            predecessor.provider_calls
            + parent.provider_calls
            + final.provider_calls
            + first_action.provider_calls
            + failure_field.provider_calls
            + outer.provider_calls
            == 0,
            "Provider=0; Development outcomes=0",
        ),
    )
    return cast(
        models.StaticAudit,
        models.make_identity_model(
            models.StaticAudit,
            {
                "gates": gates,
                "gate_count": len(gates),
                "passed_gate_count": len(gates),
                "registered_defect_control_count": 11,
                "reproduced_defect_control_count": 11,
            },
            field="audit_id",
            prefix="finance_v26_job_bound_parent_terminal_static_audit:",
        ),
    )


def _transition(
    *,
    authorization: models.ExternalAuditAuthorization,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.V179PredecessorFreezeAudit,
    claim: models.V179ClaimScopeAudit,
    parent: models.ParentAuthenticityAudit,
    final: models.FinalAbiTotalityAudit,
    first_action: models.FirstActionReferenceTotalityAudit,
    failure_field: models.FailureFieldSemanticsAudit,
    outer: models.OuterTerminalTotalityAudit,
    static: models.StaticAudit,
    online_gate: models.OnlineExecutionGate,
) -> models.ProspectiveTransition:
    return cast(
        models.ProspectiveTransition,
        models.make_identity_model(
            models.ProspectiveTransition,
            {
                "authorization_id": authorization.authorization_id,
                "source_root_id": source_root.root_id,
                "predecessor_freeze_audit_id": predecessor.audit_id,
                "claim_scope_audit_id": claim.audit_id,
                "parent_authenticity_audit_id": parent.audit_id,
                "final_abi_totality_audit_id": final.audit_id,
                "first_action_totality_audit_id": first_action.audit_id,
                "failure_field_audit_id": failure_field.audit_id,
                "outer_terminal_totality_audit_id": outer.audit_id,
                "static_audit_id": static.audit_id,
                "online_execution_gate_id": online_gate.gate_id,
                "consumed_stage": models.CONSUMED_STAGE,
                "decision": models.FAILED_DECISION,
                "next_stage": models.NEXT_STAGE,
                "permitted_change_surface": (
                    "raw_execution_descriptor",
                    "job_result_descriptor",
                    "job_bound_attempt_trace_parent",
                    "empirical_outcome_row_constructor",
                    "exact_evidence_set_estimator",
                    "first_action_reference_invalid_endpoint",
                    "final_response_abi_invalid_endpoint",
                    "strict_failure_localization_fields",
                    "outer_terminal_exact_row_totality",
                ),
            },
            field="transition_id",
            prefix="finance_v26_job_bound_parent_terminal_audit_transition:",
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
    predecessor_audit, frozen = _predecessor_freeze(package_root)
    claim = _claim_scope(frozen)
    runtime_predecessor = _runtime_predecessor(package_root)
    parent = _parent_authenticity(frozen)
    final = _final_abi_totality(
        package_root=package_root,
        frozen=frozen,
        predecessor=runtime_predecessor,
    )
    first_action = _first_action_reference_totality(
        frozen=frozen,
        predecessor=runtime_predecessor,
    )
    failure_field = _failure_field_semantics(package_root=package_root, frozen=frozen)
    outer = _outer_terminal_totality(frozen)
    online_gate = _online_gate(
        parent=parent,
        final=final,
        first_action=first_action,
        failure_field=failure_field,
        outer=outer,
    )
    static = _static_audit(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor_audit,
        claim=claim,
        parent=parent,
        final=final,
        first_action=first_action,
        failure_field=failure_field,
        outer=outer,
        online_gate=online_gate,
    )
    transition = _transition(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor_audit,
        claim=claim,
        parent=parent,
        final=final,
        first_action=first_action,
        failure_field=failure_field,
        outer=outer,
        static=static,
        online_gate=online_gate,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(
        output_dir / "external_v179_revision_result_audit.txt",
        external_audit_path.read_bytes(),
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("v179_predecessor_freeze_audit.json", predecessor_audit),
        ("v179_claim_scope_audit.json", claim),
        ("empirical_parent_authenticity_audit.json", parent),
        ("final_abi_terminal_totality_audit.json", final),
        ("first_action_reference_totality_audit.json", first_action),
        ("failure_field_semantics_audit.json", failure_field),
        ("outer_terminal_totality_audit.json", outer),
        ("online_execution_gate.json", online_gate),
        ("static_audit.json", static),
        ("prospective_transition_contract.json", transition),
    )
    for filename, value in outputs:
        _write(output_dir / filename, value)
    details = _detail_files(output_dir)
    report = cast(
        models.AuditReport,
        models.make_identity_model(
            models.AuditReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "source_root_id": source_root.root_id,
                "predecessor_freeze_audit_id": predecessor_audit.audit_id,
                "claim_scope_audit_id": claim.audit_id,
                "parent_authenticity_audit_id": parent.audit_id,
                "final_abi_totality_audit_id": final.audit_id,
                "first_action_totality_audit_id": first_action.audit_id,
                "failure_field_audit_id": failure_field.audit_id,
                "outer_terminal_totality_audit_id": outer.audit_id,
                "static_audit_id": static.audit_id,
                "online_execution_gate_id": online_gate.gate_id,
                "transition_id": transition.transition_id,
                "detail_files": details,
                "detail_file_count": len(details),
                "registered_defect_control_count": 11,
                "reproduced_defect_control_count": 11,
                "predecessor_file_count": predecessor_audit.predecessor_file_count,
                "predecessor_rebuild_match_count": (
                    predecessor_audit.independent_rebuild_match_count
                ),
                "exact_job_index_count": frozen.manifest.job_count,
                "empirical_outcome_row_count": 0,
                "empirical_estimate_count": 0,
                "provider_calls": 0,
                "stage2_provider_calls": 0,
                "development_model_outcomes": 0,
                "online_execution_authorized": False,
                "decision": models.FAILED_DECISION,
                "next_stage": models.NEXT_STAGE,
            },
            field="report_id",
            prefix="finance_v26_job_bound_parent_terminal_audit_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=predecessor_audit,
        claim_scope=claim,
        parent_authenticity=parent,
        final_abi_totality=final,
        first_action_totality=first_action,
        failure_field_semantics=failure_field,
        outer_terminal_totality=outer,
        static=static,
        online_gate=online_gate,
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
