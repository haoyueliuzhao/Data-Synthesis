from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.core.task.job_bound_multistep_outcome import (
    CapabilityDevelopmentJob,
    CapabilityDevelopmentJobManifest,
    ComponentAttemptOutcome,
    EmpiricalCapabilityOutcomeRow,
    FrozenGenerationProfile,
    JobBoundMultistepOutcomeContract,
    JobBoundRunnerContract,
    ScriptedPreflightOutcomeRow,
    evaluate_empirical_capability_estimands,
    make_identity_model,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback as v177,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_models as v177_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_parent_rejection_history_models as v176_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_breadth_depth_task_synthesis as v167,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_breadth_depth_task_synthesis_models as v167_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executed_counterfactual_outcome_closure as v178,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executed_counterfactual_outcome_closure_models as v178_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as runtime,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    compile_qualified_final_response_grammar,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    compile_semantic_action_response_grammar,
)

RUN_ID: Final = "finance_v26_179_job_bound_multistep_outcome_preflight_v1_20260830"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_179_job_bound_multistep_outcome_preflight_v1_20260830"
)
EXPECTED_REVIEW_SHA256: Final = "fac64d597640109f965cfd4acea6ffa25a6891909113d62053bd570debb10601"
EXPECTED_REVIEW_BYTE_COUNT: Final = 19_996
AUDITED_COMMIT: Final = "b8a728e3e3342abc1ec8d2002c738cfdbcfddc21"
V178_DIR: Final = v178.OUTPUT_DIR
V177_DIR: Final = v177.OUTPUT_DIR
V167_DIR: Final = v167.OUTPUT_DIR
V167_DEVELOPMENT_CATALOG: Final = f"{V167_DIR}/development_group_catalog.json"
ENTRY_SOURCE_PATHS: Final = (
    "src/trusted_synthesis/core/task/job_bound_multistep_outcome.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_job_bound_multistep_outcome_preflight_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_job_bound_multistep_outcome_preflight.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.179 cannot resolve the trusted_data_synthesis package root")


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
        raise ValueError(f"v26.179 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_file_bytes(value))
    temporary.replace(path)


def _write_exact(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"v26.179 immutable output already exists:{path}")
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
        raise ValueError("v26.179 external audit SHA-256 does not match Authorization")
    if path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.179 external audit byte count does not match Authorization")
    return cast(
        models.ExternalAuditAuthorization,
        models.make_identity_model(
            models.ExternalAuditAuthorization,
            {
                "review_sha256": EXPECTED_REVIEW_SHA256,
                "review_byte_count": EXPECTED_REVIEW_BYTE_COUNT,
                "audited_commit": AUDITED_COMMIT,
                "authorized_stage": models.AUTHORIZED_STAGE,
            },
            field="authorization_id",
            prefix="finance_v26_job_bound_outcome_external_authorization:",
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
            prefix="finance_v26_job_bound_outcome_transitive_source_root:",
        ),
    )


@dataclass(frozen=True)
class FrozenPredecessor:
    audit: models.V178PredecessorFreezeAudit
    report: v178_models.ClosureReport
    transition: v178_models.ProspectiveTransition
    outcome_contract: v178_models.CapabilityOutcomeContract
    exact_reachability: v178_models.ExactCatalogReachabilityAudit
    fixture_audit: v178_models.OutcomeRowFixtureAudit
    source: v177.PredecessorObjects


def _predecessor_freeze(package_root: Path) -> FrozenPredecessor:
    source_dir = package_root / V178_DIR
    paths = tuple(sorted(path for path in source_dir.iterdir() if path.is_file()))
    if len(paths) != 14:
        raise ValueError("v26.178 authoritative formal directory is not exactly 14 files")
    report = v178_models.ClosureReport.model_validate(_load(source_dir / "report.json"))
    transition = v178_models.ProspectiveTransition.model_validate(
        _load(source_dir / "prospective_transition_contract.json")
    )
    outcome_contract = v178_models.CapabilityOutcomeContract.model_validate(
        _load(source_dir / "capability_outcome_contract.json")
    )
    exact = v178_models.ExactCatalogReachabilityAudit.model_validate(
        _load(source_dir / "exact_catalog_reachability_audit.json")
    )
    fixtures = v178_models.OutcomeRowFixtureAudit.model_validate(
        _load(source_dir / "outcome_row_fixture_audit.json")
    )
    if transition.next_stage != models.BLOCKED_PREDECESSOR_STAGE:
        raise ValueError("v26.178 did not retain the audited no-further-experiment decision")
    with tempfile.TemporaryDirectory(prefix="finance-v26-179-v178-rebuild-") as temporary:
        rebuild_dir = Path(temporary)
        v178.build(
            package_root=package_root,
            output_dir=rebuild_dir,
            external_audit_path=source_dir / "external_v177_source_level_audit_input.txt",
        )
        rebuilt = tuple(sorted(path for path in rebuild_dir.iterdir() if path.is_file()))
        if len(rebuilt) != len(paths):
            raise ValueError("v26.178 independent rebuild file count differs")
        for source_path in paths:
            candidate = rebuild_dir / source_path.name
            if not candidate.is_file() or source_path.read_bytes() != candidate.read_bytes():
                raise ValueError(f"v26.178 independent rebuild differs:{source_path.name}")
    bindings = tuple(
        _file_binding(
            path=path,
            relative_path=f"{V178_DIR}/{path.name}",
            source_kind="predecessor_artifact",
        )
        for path in paths
    )
    audit = cast(
        models.V178PredecessorFreezeAudit,
        models.make_identity_model(
            models.V178PredecessorFreezeAudit,
            {
                "predecessor_report_id": report.report_id,
                "predecessor_transition_id": transition.transition_id,
                "predecessor_outcome_contract_id": outcome_contract.contract_id,
                "predecessor_files": bindings,
                "predecessor_decision": models.BLOCKED_PREDECESSOR_STAGE,
            },
            field="audit_id",
            prefix="finance_v26_v178_predecessor_freeze_audit:",
        ),
    )
    return FrozenPredecessor(
        audit=audit,
        report=report,
        transition=transition,
        outcome_contract=outcome_contract,
        exact_reachability=exact,
        fixture_audit=fixtures,
        source=v178._load_v176_objects(package_root),
    )


def _scope_narrowing(frozen: FrozenPredecessor) -> models.V178ScopeNarrowingAudit:
    return cast(
        models.V178ScopeNarrowingAudit,
        models.make_identity_model(
            models.V178ScopeNarrowingAudit,
            {
                "old_report_id": frozen.report.report_id,
                "reference_prefix_state_count": frozen.exact_reachability.state_scan_count,
                "displayed_candidate_count": frozen.exact_reachability.candidate_scan_count,
                "local_outcome_fixture_count": frozen.fixture_audit.fixture_row_count,
            },
            field="audit_id",
            prefix="finance_v26_v178_outcome_scope_narrowing_audit:",
        ),
    )


def _generation_profile(
    package_root: Path,
    predecessor: v177.PredecessorObjects,
) -> models.GenerationProfileBindingAudit:
    source_path = package_root / V167_DEVELOPMENT_CATALOG
    catalog = v167_models.CapabilityObservationGroupCatalog.model_validate(_load(source_path))
    signatures = tuple(item.skeleton.nuisance_signature for item in catalog.groups)
    fields = (
        "prompt_contract_id",
        "action_grammar_id",
        "final_grammar_id",
        "model_config_id",
        "thinking_policy_id",
        "bounded_generation_policy_id",
        "resource_contract_id",
    )
    configurations = {tuple(getattr(item, field) for field in fields) for item in signatures}
    if len(signatures) != 8 or len(configurations) != 1:
        raise ValueError("frozen Development generation configuration is not unique")
    values_tuple = next(iter(configurations))
    values = dict(zip(fields, values_tuple, strict=True))
    profile = cast(
        FrozenGenerationProfile,
        make_identity_model(
            FrozenGenerationProfile,
            {
                "source_development_catalog_id": catalog.catalog_id,
                "source_nuisance_signature_ids": tuple(
                    sorted(item.signature_id for item in signatures)
                ),
                **values,
            },
            field="profile_id",
            prefix="capability_job_bound_generation_profile:",
        ),
    )
    action = compile_semantic_action_response_grammar()
    final = compile_qualified_final_response_grammar()
    fixed_conditions = {
        item.fixed_generation_condition_id for item in v177._v171_packages(predecessor.source)
    }
    if action.grammar_id != profile.action_grammar_id:
        raise ValueError("frozen Action Grammar does not compile to its bound identity")
    if final.grammar_id != profile.final_grammar_id:
        raise ValueError("frozen Final Grammar does not compile to its bound identity")
    if len(fixed_conditions) != 1:
        raise ValueError("v26.171 Development source has multiple generation conditions")
    return cast(
        models.GenerationProfileBindingAudit,
        models.make_identity_model(
            models.GenerationProfileBindingAudit,
            {
                "profile": profile,
                "source_catalog_binding": _file_binding(
                    path=source_path,
                    relative_path=V167_DEVELOPMENT_CATALOG,
                    source_kind="frozen_generation_parent",
                ),
            },
            field="audit_id",
            prefix="finance_v26_job_bound_generation_profile_binding_audit:",
        ),
    )


def _outcome_contract() -> JobBoundMultistepOutcomeContract:
    return cast(
        JobBoundMultistepOutcomeContract,
        make_identity_model(
            JobBoundMultistepOutcomeContract,
            {},
            field="contract_id",
            prefix="capability_job_bound_multistep_outcome_contract:",
        ),
    )


def _v177_public_parent_ids(package_root: Path) -> tuple[str, str]:
    directory = package_root / V177_DIR
    feedback = v177_models.PublicFeedbackContract.model_validate(
        _load(directory / "public_typed_rejection_feedback_contract.json")
    )
    surface = v177_models.ProductionRejectionSurfaceCatalog.model_validate(
        _load(directory / "production_rejection_surface_catalog.json")
    )
    return feedback.contract_id, surface.catalog_id


def _job(
    *,
    runner: v176_models.AuthoritativeRunnerInputPackage,
    source: Any,
    replica_index: int,
    profile: FrozenGenerationProfile,
    contract: JobBoundMultistepOutcomeContract,
    public_feedback_contract_id: str,
    rejection_surface_id: str,
) -> CapabilityDevelopmentJob:
    parent = {
        "runner_package_id": runner.runner_package_id,
        "execution_package_id": runner.package_id,
        "authoritative_package_artifact_id": (runner.source_development_package_artifact_id),
        "source_package_artifact_id": runner.source_v171_package_artifact_id,
        "source_package_id": runner.source_package_id,
        "source_group_id": runner.source_group_id,
        "finance_core_id": runner.finance_core_id,
        "capability_family": runner.capability_family,
        "depth": runner.depth,
        "fixed_generation_condition_id": source.fixed_generation_condition_id,
        "replica_index": replica_index,
        "schedule_ids": runner.schedule_ids,
        "generation_profile_id": profile.profile_id,
        "outcome_contract_id": contract.contract_id,
        "public_feedback_contract_id": public_feedback_contract_id,
        "typed_rejection_surface_contract_id": rejection_surface_id,
    }
    seed_id = canonical_hash(parent, prefix="capability_job_bound_development_seed:")
    values = {
        **parent,
        "raw_namespace": canonical_hash(
            {"seed_id": seed_id, "kind": "raw_execution"},
            prefix="capability_job_bound_raw_namespace:",
        ),
        "result_namespace": canonical_hash(
            {"seed_id": seed_id, "kind": "result"},
            prefix="capability_job_bound_result_namespace:",
        ),
        "deterministic_seed_id": seed_id,
    }
    return cast(
        CapabilityDevelopmentJob,
        make_identity_model(
            CapabilityDevelopmentJob,
            values,
            field="job_id",
            prefix="capability_job_bound_development_job:",
        ),
    )


def _manifest(
    *,
    predecessor: v177.PredecessorObjects,
    profile: FrozenGenerationProfile,
    contract: JobBoundMultistepOutcomeContract,
    public_feedback_contract_id: str,
    rejection_surface_id: str,
) -> CapabilityDevelopmentJobManifest:
    source_by_artifact = {
        item.artifact_id: item for item in v177._v171_packages(predecessor.source)
    }
    jobs: list[CapabilityDevelopmentJob] = []
    for runner in sorted(predecessor.runner.packages, key=lambda item: item.runner_package_id):
        source = source_by_artifact[runner.source_v171_package_artifact_id]
        for replica_index in range(6):
            jobs.append(
                _job(
                    runner=runner,
                    source=source,
                    replica_index=replica_index,
                    profile=profile,
                    contract=contract,
                    public_feedback_contract_id=public_feedback_contract_id,
                    rejection_surface_id=rejection_surface_id,
                )
            )
    values = {
        "source_runner_catalog_id": predecessor.runner.catalog_id,
        "source_development_catalog_id": predecessor.development.catalog_id,
        "generation_profile_id": profile.profile_id,
        "outcome_contract_id": contract.contract_id,
        "jobs": tuple(jobs),
        "expected_job_ids": tuple(sorted(item.job_id for item in jobs)),
    }
    return cast(
        CapabilityDevelopmentJobManifest,
        make_identity_model(
            CapabilityDevelopmentJobManifest,
            values,
            field="manifest_id",
            prefix="capability_job_bound_development_manifest:",
        ),
    )


def _exact_job_set(
    *,
    manifest: CapabilityDevelopmentJobManifest,
    predecessor: v177.PredecessorObjects,
    profile: FrozenGenerationProfile,
    contract: JobBoundMultistepOutcomeContract,
) -> models.ExactJobSetAudit:
    runner_by_id = {item.runner_package_id: item for item in predecessor.runner.packages}
    sources = {item.artifact_id: item for item in v177._v171_packages(predecessor.source)}
    runner_matches = 0
    source_matches = 0
    profile_matches = 0
    contract_matches = 0
    for job in manifest.jobs:
        runner = runner_by_id[job.runner_package_id]
        source = sources[job.source_package_artifact_id]
        runner_matches += int(
            runner.package_id == job.execution_package_id
            and runner.source_development_package_artifact_id
            == job.authoritative_package_artifact_id
            and runner.source_v171_package_artifact_id == job.source_package_artifact_id
            and runner.schedule_ids == job.schedule_ids
        )
        source_matches += int(
            source.finance_core_id == job.finance_core_id
            and source.fixed_generation_condition_id == job.fixed_generation_condition_id
        )
        profile_matches += int(job.generation_profile_id == profile.profile_id)
        contract_matches += int(job.outcome_contract_id == contract.contract_id)
    if not all(
        item == 192 for item in (runner_matches, source_matches, profile_matches, contract_matches)
    ):
        raise ValueError("exact Job set crosses an authoritative source parent")
    values = {
        "manifest_id": manifest.manifest_id,
        "source_runner_parent_match_count": runner_matches,
        "source_package_parent_match_count": source_matches,
        "generation_profile_parent_match_count": profile_matches,
        "outcome_contract_parent_match_count": contract_matches,
    }
    return cast(
        models.ExactJobSetAudit,
        models.make_identity_model(
            models.ExactJobSetAudit,
            values,
            field="audit_id",
            prefix="finance_v26_exact_192_job_set_audit:",
        ),
    )


def _runner_contract(
    *,
    manifest: CapabilityDevelopmentJobManifest,
    predecessor: v177.PredecessorObjects,
    profile: FrozenGenerationProfile,
    contract: JobBoundMultistepOutcomeContract,
    public_feedback_contract_id: str,
) -> JobBoundRunnerContract:
    return cast(
        JobBoundRunnerContract,
        make_identity_model(
            JobBoundRunnerContract,
            {
                "manifest_id": manifest.manifest_id,
                "source_runner_catalog_id": predecessor.runner.catalog_id,
                "generation_profile_id": profile.profile_id,
                "outcome_contract_id": contract.contract_id,
                "public_feedback_contract_id": public_feedback_contract_id,
            },
            field="runner_id",
            prefix="capability_job_bound_multistep_runner_contract:",
        ),
    )


def _empirical_schema(
    branches: models.RunnerBranchControlAudit,
) -> models.EmpiricalOutcomeSchemaAudit:
    multi = next(item for item in branches.rows if item.scenario == "two_component_corrections")
    if multi.outcome.outcome.correction_count != 2:
        raise ValueError("empirical schema lacks an executed multi-Component control")
    required = (
        "job_id",
        "manifest_id",
        "execution_package_id",
        "source_package_artifact_id",
        "replica_index",
        "attempt_trace_id",
        "raw_namespace",
        "result_namespace",
        "raw_execution_id",
        "result_id",
        "outcome",
    )
    return cast(
        models.EmpiricalOutcomeSchemaAudit,
        models.make_identity_model(
            models.EmpiricalOutcomeSchemaAudit,
            {
                "required_parent_fields": required,
                "component_attempt_field_count": len(ComponentAttemptOutcome.model_fields),
            },
            field="audit_id",
            prefix="finance_v26_empirical_job_bound_outcome_schema_audit:",
        ),
    )


def _expect_rejection(
    *,
    mutation: str,
    surface: str,
    action: Callable[[], Any],
) -> models.DestructiveMutation:
    try:
        action()
    except (ValueError, ValidationError, TypeError, KeyError) as exc:
        return models.DestructiveMutation(
            mutation=mutation,
            surface=cast(Any, surface),
            error_code=type(exc).__name__,
        )
    raise ValueError(f"destructive mutation was accepted:{mutation}")


def _remake(
    value: BaseModel,
    *,
    field: str,
    prefix: str,
    updates: Mapping[str, Any],
) -> BaseModel:
    payload = value.model_dump(mode="python", exclude={field})
    payload.update(updates)
    return cast(
        BaseModel,
        make_identity_model(type(value), payload, field=field, prefix=prefix),
    )


def _validate_transition_parents(
    observed: Mapping[str, str],
    expected: Mapping[str, str],
) -> None:
    if observed != expected:
        raise ValueError("prospective Transition does not bind every exact evidence parent")


def _destructive_audit(
    *,
    manifest: CapabilityDevelopmentJobManifest,
    runner: JobBoundRunnerContract,
    predecessor: v177.PredecessorObjects,
    profile: FrozenGenerationProfile,
    contract: JobBoundMultistepOutcomeContract,
    denominator: models.ScriptedDenominatorPreflightAudit,
    branches: models.RunnerBranchControlAudit,
    parent_ids: Mapping[str, str],
) -> models.ProductionDestructiveAudit:
    direct = denominator.rows[0]
    direct_attempt = direct.outcome.component_attempts[0]
    abi_row = next(
        item.outcome for item in branches.rows if item.scenario == "abi_invalid_first_response"
    )
    one_row = next(
        item.outcome for item in branches.rows if item.scenario == "one_component_correction"
    )
    two_row = next(
        item.outcome for item in branches.rows if item.scenario == "two_component_corrections"
    )
    different = next(
        item
        for item in branches.rows
        if item.scenario == "different_current_invalid_second_response"
    )

    def changed_job(index: int, updates: Mapping[str, Any]) -> CapabilityDevelopmentJob:
        return cast(
            CapabilityDevelopmentJob,
            _remake(
                manifest.jobs[index],
                field="job_id",
                prefix="capability_job_bound_development_job:",
                updates=updates,
            ),
        )

    def changed_manifest(jobs: Sequence[CapabilityDevelopmentJob]) -> Any:
        return make_identity_model(
            CapabilityDevelopmentJobManifest,
            {
                **manifest.model_dump(
                    mode="python", exclude={"manifest_id", "jobs", "expected_job_ids"}
                ),
                "jobs": tuple(jobs),
                "expected_job_ids": tuple(sorted(item.job_id for item in jobs)),
            },
            field="manifest_id",
            prefix="capability_job_bound_development_manifest:",
        )

    actions: list[tuple[str, str, Callable[[], Any]]] = [
        (
            "duplicate_job_identity",
            "manifest",
            lambda: changed_manifest((*manifest.jobs[:-1], manifest.jobs[0])),
        ),
        (
            "missing_job_row",
            "manifest",
            lambda: changed_manifest(manifest.jobs[:-1]),
        ),
        (
            "extra_job_row",
            "manifest",
            lambda: changed_manifest((*manifest.jobs, manifest.jobs[0])),
        ),
        (
            "duplicate_package_replica_cell",
            "manifest",
            lambda: changed_manifest((*manifest.jobs[:-1], changed_job(-1, {"replica_index": 0}))),
        ),
        (
            "duplicate_raw_namespace",
            "manifest",
            lambda: changed_manifest(
                (
                    manifest.jobs[0],
                    changed_job(1, {"raw_namespace": manifest.jobs[0].raw_namespace}),
                    *manifest.jobs[2:],
                )
            ),
        ),
        (
            "duplicate_result_namespace",
            "manifest",
            lambda: changed_manifest(
                (
                    manifest.jobs[0],
                    changed_job(1, {"result_namespace": manifest.jobs[0].result_namespace}),
                    *manifest.jobs[2:],
                )
            ),
        ),
        (
            "crossed_source_package_parent",
            "manifest",
            lambda: _exact_job_set(
                manifest=cast(
                    CapabilityDevelopmentJobManifest,
                    changed_manifest(
                        (
                            changed_job(
                                0,
                                {
                                    "source_package_artifact_id": (
                                        manifest.jobs[6].source_package_artifact_id
                                    )
                                },
                            ),
                            *manifest.jobs[1:],
                        )
                    ),
                ),
                predecessor=predecessor,
                profile=profile,
                contract=contract,
            ),
        ),
        (
            "abi_invalid_action_marked_accepted",
            "component_attempt",
            lambda: _remake(
                abi_row.outcome.component_attempts[0],
                field="attempt_id",
                prefix="capability_component_attempt_outcome:",
                updates={"first_action_accepted": True},
            ),
        ),
        (
            "accepted_action_state_precondition_false",
            "component_attempt",
            lambda: _remake(
                direct_attempt,
                field="attempt_id",
                prefix="capability_component_attempt_outcome:",
                updates={"first_action_state_precondition_valid": False},
            ),
        ),
        (
            "correction_feedback_parent_deleted",
            "component_attempt",
            lambda: _remake(
                one_row.outcome.component_attempts[0],
                field="attempt_id",
                prefix="capability_component_attempt_outcome:",
                updates={"correction_feedback_id": None},
            ),
        ),
        (
            "multicomponent_attempt_order_swapped",
            "outcome_payload",
            lambda: _remake(
                two_row.outcome,
                field="attempt_trace_id",
                prefix="capability_job_attempt_trace:",
                updates={"component_attempts": tuple(reversed(two_row.outcome.component_attempts))},
            ),
        ),
        (
            "multicomponent_correction_count_truncated",
            "outcome_payload",
            lambda: _remake(
                two_row.outcome,
                field="attempt_trace_id",
                prefix="capability_job_attempt_trace:",
                updates={"correction_count": 1},
            ),
        ),
        (
            "corrected_job_promoted_to_first_policy_success",
            "outcome_payload",
            lambda: _remake(
                one_row.outcome,
                field="attempt_trace_id",
                prefix="capability_job_attempt_trace:",
                updates={"first_policy_qualified_valid": True},
            ),
        ),
        (
            "unevaluable_terminal_marked_bounded_qualified",
            "outcome_payload",
            lambda: _remake(
                abi_row.outcome,
                field="attempt_trace_id",
                prefix="capability_job_attempt_trace:",
                updates={"bounded_policy_qualified_valid": True},
            ),
        ),
        (
            "scripted_row_promoted_to_empirical",
            "scripted_row",
            lambda: ScriptedPreflightOutcomeRow.model_validate(
                {**direct.model_dump(mode="python"), "empirical": True}
            ),
        ),
        (
            "empirical_row_missing_raw_identity",
            "empirical_row",
            lambda: EmpiricalCapabilityOutcomeRow.model_validate(
                {
                    **direct.model_dump(
                        mode="python",
                        exclude={
                            "row_id",
                            "scenario",
                            "exact_manifest_denominator_member",
                            "raw_execution_id",
                            "result_id",
                            "empirical",
                            "provider_calls",
                        },
                    ),
                    "row_id": "pending",
                    "raw_execution_id": "",
                    "result_id": "result:control",
                }
            ),
        ),
        (
            "scripted_rows_enter_empirical_estimator",
            "estimand",
            lambda: evaluate_empirical_capability_estimands(
                cast(Any, denominator.rows),
                manifest=manifest,
            ),
        ),
        (
            "duplicate_job_rows_enter_empirical_estimator",
            "estimand",
            lambda: evaluate_empirical_capability_estimands(
                cast(Any, (*denominator.rows[:-1], denominator.rows[0])),
                manifest=manifest,
            ),
        ),
        (
            "runner_complete_baseline_loading_enabled",
            "runner",
            lambda: _remake(
                runner,
                field="runner_id",
                prefix="capability_job_bound_multistep_runner_contract:",
                updates={"complete_baseline_loading_allowed": True},
            ),
        ),
        (
            "different_invalid_relabelled_exact_manifest",
            "scripted_row",
            lambda: _remake(
                different,
                field="control_id",
                prefix="capability_job_bound_runner_branch_control:",
                updates={"source_scope": "exact_manifest"},
            ),
        ),
        (
            "transition_evidence_parent_deleted",
            "transition_parent",
            lambda: _validate_transition_parents(
                {
                    key: value
                    for key, value in parent_ids.items()
                    if key != "branch_control_audit_id"
                },
                parent_ids,
            ),
        ),
    ]
    mutations = tuple(
        _expect_rejection(mutation=name, surface=surface, action=action)
        for name, surface, action in actions
    )
    return cast(
        models.ProductionDestructiveAudit,
        models.make_identity_model(
            models.ProductionDestructiveAudit,
            {
                "mutations": mutations,
                "mutation_count": len(mutations),
                "rejection_count": len(mutations),
            },
            field="audit_id",
            prefix="finance_v26_job_bound_outcome_production_destructive_audit:",
        ),
    )


def _gate(name: str, observed: int, required: int) -> models.StaticGate:
    return models.StaticGate(gate=name, observed=observed, required=required)


def _static_audit(
    *,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.V178PredecessorFreezeAudit,
    scope: models.V178ScopeNarrowingAudit,
    profile: models.GenerationProfileBindingAudit,
    contract: JobBoundMultistepOutcomeContract,
    manifest: CapabilityDevelopmentJobManifest,
    exact_jobs: models.ExactJobSetAudit,
    prefix: models.AcceptedPrefixSurfaceAudit,
    denominator: models.ScriptedDenominatorPreflightAudit,
    branches: models.RunnerBranchControlAudit,
    empirical: models.EmpiricalOutcomeSchemaAudit,
    destructive: models.ProductionDestructiveAudit,
) -> models.StaticAudit:
    gates = (
        _gate("source_root_closed", source_root.unresolved_import_count, 0),
        _gate("v178_files_frozen", predecessor.predecessor_file_count, 14),
        _gate("v178_files_rebuilt", predecessor.independent_rebuild_match_count, 14),
        _gate("v178_mutations", predecessor.predecessor_mutation_count, 0),
        _gate("scope_reference_prefix_rows", scope.reference_prefix_state_count, 480),
        _gate("scope_fixture_rows", scope.local_outcome_fixture_count, 5),
        _gate("generation_profiles", profile.unique_generation_configuration_count, 1),
        _gate("action_grammar_compile", int(profile.action_grammar_compile_match), 1),
        _gate("final_grammar_compile", int(profile.final_grammar_compile_match), 1),
        _gate("outcome_contract_jobs", contract.job_count, 192),
        _gate("manifest_packages", manifest.package_count, 32),
        _gate("manifest_replicas", manifest.replica_count, 6),
        _gate("manifest_jobs", manifest.job_count, 192),
        _gate("manifest_missing_jobs", manifest.missing_job_count, 0),
        _gate("manifest_duplicate_jobs", manifest.duplicate_job_count, 0),
        _gate("manifest_extra_jobs", manifest.extra_job_count, 0),
        _gate("exact_job_set", exact_jobs.unique_job_id_count, 192),
        _gate("accepted_prefix_combinations", prefix.source_choice_combination_count, 772),
        _gate("accepted_prefix_replica_executions", prefix.replica_execution_count, 4_632),
        _gate("accepted_prefix_rows", prefix.package_component_replica_row_count, 480),
        _gate("prefix_runtime_exceptions", prefix.runtime_exception_count, 0),
        _gate("scripted_denominator_rows", denominator.row_count, 192),
        _gate("scripted_exact_job_matches", denominator.exact_job_set_match_count, 192),
        _gate("scripted_current_prompts", denominator.current_prompt_render_count, 480),
        _gate("scripted_action_abi", denominator.action_abi_parse_count, 480),
        _gate("scripted_final_abi", denominator.final_abi_parse_count, 192),
        _gate("scripted_runtime_results", denominator.finalized_runtime_result_count, 192),
        _gate("branch_scenarios", branches.scenario_count, 11),
        _gate("branch_exact_scenarios", branches.exact_manifest_scenario_count, 10),
        _gate("branch_diagnostic_scenarios", branches.canonical_diagnostic_scenario_count, 1),
        _gate("branch_invalid_terminals", branches.invalid_second_response_terminal_count, 4),
        _gate("branch_third_prompt_rejections", branches.terminal_third_prompt_rejection_count, 1),
        _gate("empirical_rows", empirical.empirical_row_count, 0),
        _gate("empirical_estimates", empirical.empirical_estimate_count, 0),
        _gate("destructive_rejections", destructive.rejection_count, destructive.mutation_count),
        _gate("provider_calls", 0, 0),
        _gate("development_model_outcomes", 0, 0),
        _gate("sealed_confirmation_access", 0, 0),
        _gate("mapper_state_frequency_rows", 0, 0),
    )
    return cast(
        models.StaticAudit,
        models.make_identity_model(
            models.StaticAudit,
            {
                "gates": gates,
                "gate_count": len(gates),
                "passed_gate_count": len(gates),
            },
            field="audit_id",
            prefix="finance_v26_job_bound_outcome_static_audit:",
        ),
    )


def _transition(
    *,
    authorization: models.ExternalAuditAuthorization,
    source_root: models.TransitiveSourceRoot,
    predecessor: models.V178PredecessorFreezeAudit,
    scope: models.V178ScopeNarrowingAudit,
    profile: models.GenerationProfileBindingAudit,
    contract: JobBoundMultistepOutcomeContract,
    manifest: CapabilityDevelopmentJobManifest,
    exact_jobs: models.ExactJobSetAudit,
    runner: JobBoundRunnerContract,
    prefix: models.AcceptedPrefixSurfaceAudit,
    denominator: models.ScriptedDenominatorPreflightAudit,
    branches: models.RunnerBranchControlAudit,
    empirical: models.EmpiricalOutcomeSchemaAudit,
    destructive: models.ProductionDestructiveAudit,
    static: models.StaticAudit,
) -> models.ProspectiveTransition:
    values = {
        "authorization_id": authorization.authorization_id,
        "source_root_id": source_root.root_id,
        "predecessor_freeze_audit_id": predecessor.audit_id,
        "scope_narrowing_audit_id": scope.audit_id,
        "generation_profile_audit_id": profile.audit_id,
        "outcome_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "exact_job_set_audit_id": exact_jobs.audit_id,
        "runner_id": runner.runner_id,
        "accepted_prefix_surface_audit_id": prefix.audit_id,
        "scripted_denominator_audit_id": denominator.audit_id,
        "branch_control_audit_id": branches.audit_id,
        "empirical_schema_audit_id": empirical.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "static_audit_id": static.audit_id,
        "consumed_stage": models.AUTHORIZED_STAGE,
        "blocked_predecessor_stage": models.BLOCKED_PREDECESSOR_STAGE,
        "next_stage": models.NEXT_STAGE,
    }
    return cast(
        models.ProspectiveTransition,
        models.make_identity_model(
            models.ProspectiveTransition,
            values,
            field="transition_id",
            prefix="finance_v26_job_bound_outcome_preflight_transition:",
        ),
    )


def _detail_files(output_dir: Path) -> tuple[models.FileBinding, ...]:
    return tuple(
        _file_binding(
            path=path,
            relative_path=path.name,
            source_kind=(
                "external_audit_input"
                if path.name == "external_v178_latest_revision_source_audit.txt"
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
    scope = _scope_narrowing(frozen)
    profile_audit = _generation_profile(package_root, frozen.source)
    profile = profile_audit.profile
    contract = _outcome_contract()
    public_feedback_id, rejection_surface_id = _v177_public_parent_ids(package_root)
    manifest = _manifest(
        predecessor=frozen.source,
        profile=profile,
        contract=contract,
        public_feedback_contract_id=public_feedback_id,
        rejection_surface_id=rejection_surface_id,
    )
    exact_jobs = _exact_job_set(
        manifest=manifest,
        predecessor=frozen.source,
        profile=profile,
        contract=contract,
    )
    runner = _runner_contract(
        manifest=manifest,
        predecessor=frozen.source,
        profile=profile,
        contract=contract,
        public_feedback_contract_id=public_feedback_id,
    )
    prefix = runtime.scan_all_accepted_prefixes(
        manifest=manifest,
        predecessor=frozen.source,
    )
    runner_products = runtime.execute_runner_preflight(
        manifest=manifest,
        runner=runner,
        predecessor=frozen.source,
        profile=profile,
    )
    empirical = _empirical_schema(runner_products.branches)
    parent_ids = {
        "authorization_id": authorization.authorization_id,
        "source_root_id": source_root.root_id,
        "predecessor_freeze_audit_id": frozen.audit.audit_id,
        "scope_narrowing_audit_id": scope.audit_id,
        "generation_profile_audit_id": profile_audit.audit_id,
        "outcome_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "exact_job_set_audit_id": exact_jobs.audit_id,
        "runner_id": runner.runner_id,
        "accepted_prefix_surface_audit_id": prefix.audit_id,
        "scripted_denominator_audit_id": runner_products.denominator.audit_id,
        "branch_control_audit_id": runner_products.branches.audit_id,
        "empirical_schema_audit_id": empirical.audit_id,
    }
    destructive = _destructive_audit(
        manifest=manifest,
        runner=runner,
        predecessor=frozen.source,
        profile=profile,
        contract=contract,
        denominator=runner_products.denominator,
        branches=runner_products.branches,
        parent_ids=parent_ids,
    )
    static = _static_audit(
        source_root=source_root,
        predecessor=frozen.audit,
        scope=scope,
        profile=profile_audit,
        contract=contract,
        manifest=manifest,
        exact_jobs=exact_jobs,
        prefix=prefix,
        denominator=runner_products.denominator,
        branches=runner_products.branches,
        empirical=empirical,
        destructive=destructive,
    )
    transition = _transition(
        authorization=authorization,
        source_root=source_root,
        predecessor=frozen.audit,
        scope=scope,
        profile=profile_audit,
        contract=contract,
        manifest=manifest,
        exact_jobs=exact_jobs,
        runner=runner,
        prefix=prefix,
        denominator=runner_products.denominator,
        branches=runner_products.branches,
        empirical=empirical,
        destructive=destructive,
        static=static,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_exact(
        output_dir / "external_v178_latest_revision_source_audit.txt",
        external_audit_path.read_bytes(),
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("transitive_source_root.json", source_root),
        ("v178_predecessor_freeze_audit.json", frozen.audit),
        ("v178_scope_narrowing_audit.json", scope),
        ("generation_profile_binding_audit.json", profile_audit),
        ("job_bound_multistep_outcome_contract.json", contract),
        ("development_job_manifest.json", manifest),
        ("exact_192_job_set_audit.json", exact_jobs),
        ("job_bound_runner_contract.json", runner),
        ("accepted_prefix_surface_audit.json", prefix),
        ("scripted_denominator_preflight_audit.json", runner_products.denominator),
        ("runner_branch_control_audit.json", runner_products.branches),
        ("empirical_outcome_schema_audit.json", empirical),
        ("production_destructive_audit.json", destructive),
        ("static_audit.json", static),
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
                "authorization_id": authorization.authorization_id,
                "source_root_id": source_root.root_id,
                "predecessor_freeze_audit_id": frozen.audit.audit_id,
                "scope_narrowing_audit_id": scope.audit_id,
                "generation_profile_audit_id": profile_audit.audit_id,
                "outcome_contract_id": contract.contract_id,
                "manifest_id": manifest.manifest_id,
                "exact_job_set_audit_id": exact_jobs.audit_id,
                "runner_id": runner.runner_id,
                "accepted_prefix_surface_audit_id": prefix.audit_id,
                "scripted_denominator_audit_id": runner_products.denominator.audit_id,
                "branch_control_audit_id": runner_products.branches.audit_id,
                "empirical_schema_audit_id": empirical.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "detail_files": details,
                "detail_file_count": len(details),
                "next_stage": transition.next_stage,
            },
            field="report_id",
            prefix="finance_v26_job_bound_multistep_outcome_preflight_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_root=source_root,
        predecessor=frozen.audit,
        scope_narrowing=scope,
        generation_profile=profile_audit,
        outcome_contract=contract,
        manifest=manifest,
        exact_job_set=exact_jobs,
        runner=runner,
        accepted_prefix_surface=prefix,
        scripted_denominator=runner_products.denominator,
        branch_controls=runner_products.branches,
        empirical_schema=empirical,
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
