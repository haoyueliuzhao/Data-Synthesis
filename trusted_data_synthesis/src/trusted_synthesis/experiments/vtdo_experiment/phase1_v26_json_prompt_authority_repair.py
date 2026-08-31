from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from functools import partial
from pathlib import Path
from typing import Any, Literal, NoReturn, cast

from pydantic import BaseModel

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_execution as v188,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_outcome_preflight as v186,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_explicit_prompt_contract_preflight as v192,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment.json_explicit_exact_future_runner import (
    CredentialFreeExactFutureRunner,
    CredentialFreeFixtureTransport,
    ZeroCallInvocation,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    compile_semantic_action_response_grammar,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    make_stage_one_request_body,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID = "finance_v26_193_json_prompt_authority_repair_preflight_v2_20260901"
V192_DIR = (
    "artifacts/vtdo_experiment/finance_v26_192_json_explicit_prompt_contract_preflight_v1_20260831"
)
V176_DIR = (
    "artifacts/vtdo_experiment/finance_v26_176_authoritative_parent_rejection_history_v2_20260829"
)
V179_DIR = (
    "artifacts/vtdo_experiment/finance_v26_179_job_bound_multistep_outcome_preflight_v1_20260830"
)
AUDITED_V192_SOURCE_COMMIT = "281abb8a2eb12434a6ade981c2a6b35b5951d98a"
AUDITED_V192_SOURCE_TREE = "d1bf6b2f165875348e6e9bcdc54492ffa07cfc84"
EXPECTED_V192_REPORT_ID = (
    "finance_v26_192_json_explicit_preflight_report:"
    "63baffe7efb1c2cab3ebd217c1ee55a67e3277cb71fb1ad8f04677bafebf4d20"
)
EXPECTED_V192_ARTIFACT_ROOT = (
    "finance_v26_192_json_explicit_artifact_root:"
    "5e2970f0ec16feb9139a676e4c8277677f0fd77f259302d85a8c28629601746a"
)
EXPECTED_ACCEPTED_PREFIX_AUDIT_ID = (
    "finance_v26_accepted_prefix_action_surface_audit:"
    "a6ea7829f12c70bc49c4722d66d9117a53e776d5e10717bb141409efc6adb0a8"
)
V179_SOURCE_COMMIT = "27ac98d03d078d522cecf7a0cb290230cac63036"
V179_SOURCE_TREE = "e2c46cd3735aa0ea090c852f1290a8e978b2b3c8"
V176_CATALOG_SHA256 = "51ed5b6344aa19cd3d51ab01d85e30a1b40d8b7fef04dc2ae04c7383b950bd95"
RUNNER_SOURCE_RELATIVE_PATH = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "json_explicit_exact_future_runner.py"
)
CURRENT_SOURCE_FILES = (
    RUNNER_SOURCE_RELATIVE_PATH,
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_json_prompt_authority_repair.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_json_prompt_authority_repair_models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "source_projected_json_prompt_authority_repair_runner.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "v179_source_snapshot_result_replay.py",
    "trusted_data_synthesis/tests/test_v26_json_prompt_authority_repair.py",
)


class RepairValidationError(ValueError):
    def __init__(self, *, stage: str, reason: str, target_validator_reached: bool = True) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason
        self.target_validator_reached = target_validator_reached


class BuildProducts:
    def __init__(
        self,
        *,
        authorization: models.ExternalAuditAuthorization,
        source_projection: models.SourceProjectionAudit,
        parent_authority: models.ParentAuthorityAudit,
        evidence_set: models.ExactPromptEvidenceSet,
        callsite: models.RunnerCallsiteTotalityAudit,
        destructive: models.TypedDestructiveAudit,
        drift: models.ResultDriftDecompositionAudit,
        outcome_gap: models.OutcomeAuthorityGapRegister,
        static: models.StaticAudit,
        transition: models.ProspectiveTransition,
        report: models.RepairReport,
        artifact_manifest: models.ArtifactManifest,
    ) -> None:
        self.authorization = authorization
        self.source_projection = source_projection
        self.parent_authority = parent_authority
        self.evidence_set = evidence_set
        self.callsite = callsite
        self.destructive = destructive
        self.drift = drift
        self.outcome_gap = outcome_gap
        self.static = static
        self.transition = transition
        self.report = report
        self.artifact_manifest = artifact_manifest


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _file_bytes(value: Any) -> bytes:
    return _canonical_bytes(value) + b"\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> tuple[str, int]:
    payload = path.read_bytes()
    return _sha256_bytes(payload), len(payload)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_bytes_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _fail(stage: str, reason: str) -> NoReturn:
    raise RepairValidationError(stage=stage, reason=reason)


def _authorization(path: Path) -> tuple[models.ExternalAuditAuthorization, bytes]:
    payload = path.read_bytes()
    if len(payload) != 22_168 or _sha256_bytes(payload) != (
        "35ff5c6f064dafbe604eb3cf24eb99942ee6f714424c77e3582c73d3c9ad3546"
    ):
        _fail("authorization.external_audit", "v26.192 external audit bytes differ")
    authorization = cast(
        models.ExternalAuditAuthorization,
        models.make_identity(
            models.ExternalAuditAuthorization,
            {"audit_sha256": ("35ff5c6f064dafbe604eb3cf24eb99942ee6f714424c77e3582c73d3c9ad3546")},
            field="authorization_id",
            prefix="finance_v26_193_external_authorization:",
        ),
    )
    return authorization, payload


def _validate_archive(path: Path, *, expected_commit: str, expected_tree: str, label: str) -> None:
    if v186._archive_commit(path) != expected_commit:  # noqa: SLF001
        _fail(f"source_projection.{label}_commit", f"{label} source Archive commit differs")
    rows = v186._archive_rows(path)  # noqa: SLF001
    if v186._git_tree_id(rows) != expected_tree:  # noqa: SLF001
        _fail(f"source_projection.{label}_tree", f"{label} source Archive tree differs")


def _module_candidates(module: str, source_root: Path) -> tuple[Path, ...]:
    if not module.startswith("trusted_synthesis"):
        return ()
    stem = source_root / Path(*module.split("."))
    candidates = (stem.with_suffix(".py"), stem / "__init__.py")
    return tuple(path for path in candidates if path.is_file())


def _module_name(path: Path, source_root: Path) -> tuple[str, bool]:
    relative = path.relative_to(source_root)
    parts = list(relative.with_suffix("").parts)
    is_package = bool(parts and parts[-1] == "__init__")
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def _imported_modules(path: Path, source_root: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current, is_package = _module_name(path, source_root)
    package_parts = current.split(".") if is_package else current.split(".")[:-1]
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(package_parts) - node.level + 1
                prefix = package_parts[: max(keep, 0)]
                base = ".".join((*prefix, *(node.module or "").split("."))).strip(".")
            else:
                base = node.module or ""
            if base:
                modules.add(base)
                modules.update(
                    candidate
                    for alias in node.names
                    if alias.name != "*"
                    for candidate in (f"{base}.{alias.name}",)
                    if _module_candidates(candidate, source_root)
                )
    return tuple(
        sorted(
            module
            for module in modules
            if module == "trusted_synthesis" or module.startswith("trusted_synthesis.")
        )
    )


def _transitive_source_bindings(extracted_repository: Path) -> tuple[models.FileBinding, ...]:
    source_root = extracted_repository / "trusted_data_synthesis" / "src"
    starts = (
        source_root / "trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_json_explicit_prompt_contract_preflight.py",
    )
    pending = list(starts)
    visited: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        if not path.is_file():
            _fail("source_projection.transitive_source", f"missing transitive source:{path}")
        visited.add(path)
        for module in _imported_modules(path, source_root):
            candidates = _module_candidates(module, source_root)
            if not candidates:
                _fail(
                    "source_projection.transitive_source",
                    f"unresolved internal source import:{module}",
                )
            pending.extend(candidates)
    explicit = (
        extracted_repository
        / "trusted_data_synthesis/tests/test_v26_json_explicit_prompt_contract_preflight.py",
        extracted_repository / "trusted_data_synthesis/pyproject.toml",
    )
    visited.update(path for path in explicit if path.is_file())
    return tuple(
        models.FileBinding(
            relative_path=path.relative_to(extracted_repository).as_posix(),
            sha256=_sha256_path(path)[0],
            byte_count=path.stat().st_size,
            source_kind="v26_192_transitive_source",
        )
        for path in sorted(visited)
    )


def _source_projection(
    *,
    package_root: Path,
    authorization: models.ExternalAuditAuthorization,
    v192_source_archive: Path,
    current_source_archive: Path,
    current_source_commit: str,
    current_source_tree: str,
) -> models.SourceProjectionAudit:
    _validate_archive(
        v192_source_archive,
        expected_commit=AUDITED_V192_SOURCE_COMMIT,
        expected_tree=AUDITED_V192_SOURCE_TREE,
        label="v26_192",
    )
    _validate_archive(
        current_source_archive,
        expected_commit=current_source_commit,
        expected_tree=current_source_tree,
        label="v26_193",
    )
    with tempfile.TemporaryDirectory(prefix="v26-193-current-source-") as temporary:
        extracted_current = Path(temporary) / "source"
        extracted_current.mkdir()
        with tarfile.open(current_source_archive, mode="r:") as archive:
            archive.extractall(extracted_current, filter="data")
        repository = package_root.parent
        for relative_path in CURRENT_SOURCE_FILES:
            live = repository / relative_path
            archived = extracted_current / relative_path
            if (
                not live.is_file()
                or not archived.is_file()
                or live.read_bytes() != archived.read_bytes()
            ):
                _fail(
                    "source_projection.current_source_bytes",
                    f"current source Archive differs from executed source:{relative_path}",
                )
    current_dir = package_root / V192_DIR
    report = _load(current_dir / "report.json")
    artifact_manifest = _load(current_dir / "artifact_manifest.json")
    if (
        report.get("report_id") != EXPECTED_V192_REPORT_ID
        or artifact_manifest.get("artifact_root") != EXPECTED_V192_ARTIFACT_ROOT
    ):
        _fail("source_projection.v26_192_identity", "v26.192 Report or Artifact Root differs")
    with tempfile.TemporaryDirectory(prefix="v26-193-v192-source-") as temporary:
        extracted = Path(temporary) / "source"
        rebuilt = Path(temporary) / "rebuild"
        extracted.mkdir()
        with tarfile.open(v192_source_archive, mode="r:") as archive:
            archive.extractall(extracted, filter="data")
        source_bindings = _transitive_source_bindings(extracted)
        old_package = extracted / "trusted_data_synthesis"
        v191_audit = current_dir / "external_v26_191_online_audit.txt"
        rebuild_code = (
            "import pathlib,sys;"
            "from trusted_synthesis.experiments.vtdo_experiment import "
            "phase1_v26_json_explicit_prompt_contract_preflight as m;"
            "m.build(package_root=pathlib.Path(sys.argv[1]),"
            "output_dir=pathlib.Path(sys.argv[2]),"
            "external_audit_path=pathlib.Path(sys.argv[3]),"
            "source_commit=sys.argv[4],source_tree=sys.argv[5])"
        )
        environment = os.environ.copy()
        environment.pop("DEEPSEEK_API_KEY", None)
        environment["PYTHONPATH"] = str(old_package / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        replay = subprocess.run(
            (
                sys.executable,
                "-c",
                rebuild_code,
                str(old_package),
                str(rebuilt),
                str(v191_audit),
                AUDITED_V192_SOURCE_COMMIT,
                AUDITED_V192_SOURCE_TREE,
            ),
            cwd=old_package,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if replay.returncode != 0:
            _fail(
                "source_projection.v26_192_archive_execution",
                "v26.192 Git-Archive replay failed",
            )
        current_files = tuple(sorted(path for path in current_dir.iterdir() if path.is_file()))
        rebuilt_files = tuple(sorted(path for path in rebuilt.iterdir() if path.is_file()))
        if len(current_files) != 17 or len(rebuilt_files) != 17:
            _fail(
                "source_projection.v26_192_formal_set",
                "v26.192 formal file denominator differs",
            )
        if tuple(path.name for path in current_files) != tuple(path.name for path in rebuilt_files):
            _fail("source_projection.v26_192_formal_set", "v26.192 formal file names differ")
        formal_bindings: list[models.FileBinding] = []
        for current, replayed in zip(current_files, rebuilt_files, strict=True):
            current_bytes = current.read_bytes()
            if current_bytes != replayed.read_bytes():
                _fail(
                    "source_projection.v26_192_byte_replay",
                    f"v26.192 formal replay differs:{current.name}",
                )
            formal_bindings.append(
                models.FileBinding(
                    relative_path=current.name,
                    sha256=_sha256_bytes(current_bytes),
                    byte_count=len(current_bytes),
                    source_kind="v26_192_formal_artifact",
                )
            )
    old_sha, old_bytes = _sha256_path(v192_source_archive)
    current_sha, current_archive_bytes = _sha256_path(current_source_archive)
    return cast(
        models.SourceProjectionAudit,
        models.make_identity(
            models.SourceProjectionAudit,
            {
                "authorization_id": authorization.authorization_id,
                "audited_v26_192_source_commit": AUDITED_V192_SOURCE_COMMIT,
                "audited_v26_192_source_tree": AUDITED_V192_SOURCE_TREE,
                "audited_source_archive_sha256": old_sha,
                "audited_source_archive_byte_count": old_bytes,
                "current_source_commit": current_source_commit,
                "current_source_tree": current_source_tree,
                "current_source_archive_sha256": current_sha,
                "current_source_archive_byte_count": current_archive_bytes,
                "transitive_source_files": source_bindings,
                "transitive_source_file_count": len(source_bindings),
                "v26_192_formal_files": tuple(formal_bindings),
            },
            field="audit_id",
            prefix="finance_v26_193_source_projection_audit:",
        ),
    )


def _load_v192_objects(
    package_root: Path,
) -> tuple[
    v192.JsonExplicitPromptContract,
    v192.JsonExplicitPromptSchema,
    v192.JsonExplicitGenerationProfile,
    v192.JsonExplicitRunnerPackageCatalog,
    v192.JsonExplicitDevelopmentManifest,
    v192.JsonExplicitRunnerContract,
]:
    root = package_root / V192_DIR
    return (
        v192.JsonExplicitPromptContract.model_validate(
            _load(root / "json_explicit_prompt_contract.json")
        ),
        v192.JsonExplicitPromptSchema.model_validate(
            _load(root / "json_explicit_prompt_schema.json")
        ),
        v192.JsonExplicitGenerationProfile.model_validate(
            _load(root / "json_explicit_generation_profile.json")
        ),
        v192.JsonExplicitRunnerPackageCatalog.model_validate(
            _load(root / "json_explicit_runner_package_catalog.json")
        ),
        v192.JsonExplicitDevelopmentManifest.model_validate(
            _load(root / "json_explicit_development_manifest.json")
        ),
        v192.JsonExplicitRunnerContract.model_validate(
            _load(root / "json_explicit_runner_contract.json")
        ),
    )


def _validate_parent_chain(
    *,
    prepared: v188.PreparedExecution,
    contract: v192.JsonExplicitPromptContract,
    schema: v192.JsonExplicitPromptSchema,
    profile: v192.JsonExplicitGenerationProfile,
    packages: v192.JsonExplicitRunnerPackageCatalog,
    manifest: v192.JsonExplicitDevelopmentManifest,
    runner: v192.JsonExplicitRunnerContract,
    source_projection_id: str,
) -> models.ParentAuthorityAudit:
    if (
        profile.source_profile_id != prepared.profile.profile_id
        or profile.prompt_contract_id != contract.contract_id
        or profile.prompt_schema_id != schema.schema_id
        or profile.action_grammar_id != prepared.profile.action_grammar_id
        or profile.final_grammar_id != prepared.profile.final_grammar_id
        or profile.model_config_id != prepared.profile.model_config_id
        or profile.thinking_policy_id != prepared.profile.thinking_policy_id
        or profile.bounded_generation_policy_id != prepared.profile.bounded_generation_policy_id
        or profile.resource_contract_id != prepared.profile.resource_contract_id
    ):
        _fail("parent.profile", "fresh generation Profile differs from frozen source semantics")
    source_jobs = {item.job_id: item for item in prepared.frozen.manifest.jobs}
    if set(manifest.source_job_ids) != set(source_jobs):
        _fail("parent.source_job_set", "fresh Manifest source Job set differs")
    package_by_id = {item.runner_package_id: item for item in packages.packages}
    package_by_source = {item.source_runner_package_id: item for item in packages.packages}
    if len(package_by_id) != 32 or len(package_by_source) != 32:
        _fail("parent.package_set", "fresh Runner Package set is not exact")
    representative: dict[str, Any] = {}
    for source in source_jobs.values():
        representative.setdefault(source.runner_package_id, source)
    if set(package_by_source) != set(representative):
        _fail("parent.package_source_set", "fresh Package source Runner set differs")
    for source_runner_id, source in sorted(representative.items()):
        package = package_by_source[source_runner_id]
        source_package = prepared.runtime_catalog.runner_by_id[source_runner_id]
        expected = {
            "source_execution_package_id": source.execution_package_id,
            "source_package_artifact_id": source.source_package_artifact_id,
            "source_package_id": source.source_package_id,
            "source_group_id": source.source_group_id,
            "finance_core_id": source.finance_core_id,
            "capability_family": source.capability_family,
            "depth": source.depth,
            "public_task_id": source_package.public_task_id,
            "schedule_ids": source.schedule_ids,
            "topological_component_keys": source_package.topological_component_keys,
            "prompt_contract_id": contract.contract_id,
            "prompt_schema_id": schema.schema_id,
            "generation_profile_id": profile.profile_id,
        }
        for field, value in expected.items():
            if getattr(package, field) != value:
                _fail("parent.package_source", f"fresh Package field differs:{field}")
    seen_source: set[str] = set()
    cells: set[tuple[str, int]] = set()
    for job in manifest.jobs:
        source_job = source_jobs.get(job.source_job_id)
        if source_job is None:
            _fail("parent.job_source", "fresh Job references an absent source Job")
        if job.source_runner_package_id != source_job.runner_package_id:
            _fail("parent.job_source", "fresh Job source Runner differs from source Job")
        fresh_package = package_by_id.get(job.runner_package_id)
        if (
            fresh_package is None
            or fresh_package.source_runner_package_id != source_job.runner_package_id
        ):
            _fail("parent.job_package", "fresh Job Runner Package is not source-owned")
        expected_fields = {
            "execution_package_id": source_job.execution_package_id,
            "source_package_artifact_id": source_job.source_package_artifact_id,
            "source_package_id": source_job.source_package_id,
            "finance_core_id": source_job.finance_core_id,
            "capability_family": source_job.capability_family,
            "depth": source_job.depth,
            "replica_index": source_job.replica_index,
            "schedule_ids": source_job.schedule_ids,
            "generation_profile_id": profile.profile_id,
            "prompt_schema_id": schema.schema_id,
            "source_outcome_contract_id": source_job.outcome_contract_id,
        }
        for field, value in expected_fields.items():
            if getattr(job, field) != value:
                _fail("parent.job_source", f"fresh Job field differs:{field}")
        namespace_parent = {
            "source_job_id": source_job.job_id,
            "runner_package_id": fresh_package.runner_package_id,
            "generation_profile_id": profile.profile_id,
            "prompt_schema_id": schema.schema_id,
        }
        expected_namespaces = (
            canonical_hash(namespace_parent, prefix="json_explicit_raw_namespace:"),
            canonical_hash(namespace_parent, prefix="json_explicit_result_namespace:"),
            canonical_hash(namespace_parent, prefix="json_explicit_deterministic_seed:"),
        )
        if (
            job.raw_namespace,
            job.result_namespace,
            job.deterministic_seed_id,
        ) != expected_namespaces:
            _fail("parent.job_namespace", "fresh Job namespace parent differs")
        seen_source.add(source_job.job_id)
        cells.add((job.runner_package_id, job.replica_index))
    if seen_source != set(source_jobs) or len(cells) != 192:
        _fail("parent.manifest_denominator", "fresh Manifest exact denominator differs")
    if (
        manifest.runner_package_catalog_id != packages.catalog_id
        or manifest.generation_profile_id != profile.profile_id
        or manifest.prompt_contract_id != contract.contract_id
        or manifest.prompt_schema_id != schema.schema_id
    ):
        _fail("parent.manifest", "fresh Manifest parent differs")
    if (
        runner.manifest_id != manifest.manifest_id
        or runner.runner_package_catalog_id != packages.catalog_id
        or runner.generation_profile_id != profile.profile_id
        or runner.prompt_contract_id != contract.contract_id
        or runner.prompt_schema_id != schema.schema_id
        or runner.source_runner_id != prepared.frozen.runner.runner_id
    ):
        _fail("parent.runner", "fresh Runner parent differs")
    return cast(
        models.ParentAuthorityAudit,
        models.make_identity(
            models.ParentAuthorityAudit,
            {
                "source_projection_id": source_projection_id,
                "runner_package_catalog_id": packages.catalog_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
            },
            field="audit_id",
            prefix="finance_v26_193_parent_authority_audit:",
        ),
    )


def _coordinate(**values: Any) -> models.PromptCoordinate:
    return cast(
        models.PromptCoordinate,
        models.make_identity(
            models.PromptCoordinate,
            values,
            field="coordinate_id",
            prefix="json_explicit_prompt_coordinate:",
        ),
    )


def _action_core(public_prompt: Any, prepared: v188.PreparedExecution) -> dict[str, Any]:
    return v192._action_core(public_prompt, prepared)  # noqa: SLF001


def _rejection_receipt(output: Any) -> str:
    receipt = getattr(output, "public_observation_receipt_id", None)
    if not isinstance(receipt, str) or not receipt:
        _fail("coordinate.correction_parent", "typed rejection lacks an exact public Receipt")
    return receipt


def _derive_expected_coordinates(
    *,
    prepared: v188.PreparedExecution,
    manifest: v192.JsonExplicitDevelopmentManifest,
) -> tuple[models.PromptCoordinate, ...]:
    source_jobs = {item.job_id: item for item in prepared.frozen.manifest.jobs}
    coordinates: list[models.PromptCoordinate] = []
    for fresh in manifest.jobs:
        source = source_jobs[fresh.source_job_id]
        context = frozen_runtime.prepare_job(source, prepared.runtime_catalog)
        state = frozen_runtime._initialize(context)  # noqa: SLF001
        invocation_index = 0
        while state.current_index < len(state.ordered_components):
            component_index = state.current_index
            component = state.ordered_components[component_index]
            prompt = step_runtime.render_next_prompt(state)
            dispositions = frozen_runtime._candidate_dispositions(state, prompt)  # noqa: SLF001
            action_core = _action_core(prompt, prepared)
            coordinates.append(
                _coordinate(
                    fresh_job_id=fresh.job_id,
                    source_job_id=fresh.source_job_id,
                    runner_package_id=fresh.runner_package_id,
                    source_runner_package_id=fresh.source_runner_package_id,
                    replica_index=fresh.replica_index,
                    invocation_index=invocation_index,
                    phase="first_action" if component_index == 0 else "subsequent_action",
                    prompt_kind="action",
                    component_index=component_index,
                    component_key=component.component_key,
                    schedule_id=fresh.schedule_ids[component_index],
                    state_token=prompt.state.state_token,
                    expected_prompt_core_sha256=_sha256_bytes(
                        _canonical_json(action_core).encode("utf-8")
                    ),
                )
            )
            invocation_index += 1
            for invalid in (item for item in dispositions if not item.acceptance.accepted):
                branch = copy.deepcopy(state)
                rejected = step_runtime.step(branch, invalid.action_id)
                receipt = _rejection_receipt(rejected)
                correction_prompt = step_runtime.render_next_prompt(branch)
                correction_core = _action_core(correction_prompt, prepared)
                coordinates.append(
                    _coordinate(
                        fresh_job_id=fresh.job_id,
                        source_job_id=fresh.source_job_id,
                        runner_package_id=fresh.runner_package_id,
                        source_runner_package_id=fresh.source_runner_package_id,
                        replica_index=fresh.replica_index,
                        invocation_index=invocation_index,
                        phase="correction",
                        prompt_kind="correction",
                        component_index=component_index,
                        component_key=component.component_key,
                        schedule_id=fresh.schedule_ids[component_index],
                        state_token=correction_prompt.state.state_token,
                        expected_prompt_core_sha256=_sha256_bytes(
                            _canonical_json(correction_core).encode("utf-8")
                        ),
                        rejected_action_id=invalid.action_id,
                        rejection_receipt_id=receipt,
                    )
                )
                invocation_index += 1
            selection = frozen_runtime._reference_selection(  # noqa: SLF001
                state, prompt, dispositions, component_index
            )
            action = frozen_runtime._parse_action_response(  # noqa: SLF001
                prompt,
                selection,
                grammar=prepared.action_grammar,
                profile=prepared.profile,
            )
            if action is None or not getattr(
                step_runtime.step(state, action), "action_accepted", False
            ):
                _fail("coordinate.reference_replay", "reference Action did not commit")
        result = step_runtime.finalize(state)
        final_prompt, _ = v188.render_final_prompt(
            context=context,
            result=result,
            grammar=prepared.final_grammar,
        )
        coordinates.append(
            _coordinate(
                fresh_job_id=fresh.job_id,
                source_job_id=fresh.source_job_id,
                runner_package_id=fresh.runner_package_id,
                source_runner_package_id=fresh.source_runner_package_id,
                replica_index=fresh.replica_index,
                invocation_index=invocation_index,
                phase="final",
                prompt_kind="final",
                state_token=result.result_id,
                expected_prompt_core_sha256=_sha256_bytes(
                    _canonical_json(final_prompt).encode("utf-8")
                ),
            )
        )
    if len(coordinates) != 792 or len({item.coordinate_id for item in coordinates}) != 792:
        _fail("coordinate.expected_set", "independent expected Prompt coordinate set differs")
    return tuple(coordinates)


def _request_row(
    *,
    coordinate: models.PromptCoordinate,
    invocation: ZeroCallInvocation,
    contract: v192.JsonExplicitPromptContract,
    schema: v192.JsonExplicitPromptSchema,
    profile: v192.JsonExplicitGenerationProfile,
) -> models.ProviderRequestEvidenceRow:
    core_bytes = invocation.prompt_core_canonical_json.encode("utf-8")
    prompt_bytes = invocation.rendered_prompt.encode("utf-8")
    request_bytes = invocation.request_body_canonical_json.encode("utf-8")
    return cast(
        models.ProviderRequestEvidenceRow,
        models.make_identity(
            models.ProviderRequestEvidenceRow,
            {
                "coordinate": coordinate,
                "prompt_contract_id": contract.contract_id,
                "prompt_schema_id": schema.schema_id,
                "generation_profile_id": profile.profile_id,
                "rendered_prompt": invocation.rendered_prompt,
                "prompt_core_canonical_json": invocation.prompt_core_canonical_json,
                "request_body_canonical_json": invocation.request_body_canonical_json,
                "rendered_prompt_sha256": _sha256_bytes(prompt_bytes),
                "prompt_core_sha256": _sha256_bytes(core_bytes),
                "request_body_sha256": _sha256_bytes(request_bytes),
                "request_body_byte_count": len(request_bytes),
                "invocation_event_sequence": invocation.event_sequence,
            },
            field="row_id",
            prefix="json_explicit_provider_request_evidence_row:",
        ),
    )


def _validate_request_row(
    *,
    row: models.ProviderRequestEvidenceRow,
    config: AgentModelConfig,
    contract: v192.JsonExplicitPromptContract,
    schema: v192.JsonExplicitPromptSchema,
    profile: v192.JsonExplicitGenerationProfile,
) -> None:
    prompt_bytes = row.rendered_prompt.encode("utf-8")
    core_bytes = row.prompt_core_canonical_json.encode("utf-8")
    request_bytes = row.request_body_canonical_json.encode("utf-8")
    if (
        row.rendered_prompt_sha256 != _sha256_bytes(prompt_bytes)
        or row.prompt_core_sha256 != _sha256_bytes(core_bytes)
        or row.request_body_sha256 != _sha256_bytes(request_bytes)
        or row.request_body_byte_count != len(request_bytes)
    ):
        _fail("request_evidence.content_hash", "Provider request evidence bytes differ")
    if row.prompt_core_sha256 != row.coordinate.expected_prompt_core_sha256:
        _fail(
            "request_evidence.expected_prompt_core",
            "Prompt core differs from independent Runtime expectation",
        )
    if row.invocation_event_sequence != ("render", "body", "validate", "sink"):
        _fail("request_evidence.invocation_order", "Runner invocation order differs")
    try:
        core = json.loads(row.prompt_core_canonical_json)
        envelope = json.loads(row.rendered_prompt)
        body = json.loads(row.request_body_canonical_json)
    except json.JSONDecodeError as error:
        raise RepairValidationError(
            stage="request_evidence.json_reparse",
            reason="Provider request evidence JSON reparse failed",
        ) from error
    if _canonical_json(core) != row.prompt_core_canonical_json:
        _fail("request_evidence.prompt_core", "Prompt core is not canonical JSON")
    if (
        not isinstance(envelope, dict)
        or _canonical_json(envelope) != row.rendered_prompt
        or tuple(sorted(envelope)) != schema.top_level_fields
        or envelope.get("prompt_kind") != row.coordinate.prompt_kind
        or _canonical_json(envelope.get("prompt_core")) != row.prompt_core_canonical_json
    ):
        _fail("request_evidence.rendered_prompt_core", "rendered Prompt core differs")
    protocol = envelope.get("provider_output_protocol")
    if (
        not isinstance(protocol, dict)
        or tuple(sorted(protocol)) != schema.protocol_fields
        or protocol.get("contract_id") != contract.contract_id
        or protocol.get("instruction") != contract.instruction
        or protocol.get("response_format") != {"type": "json_object"}
    ):
        _fail("request_evidence.rendered_protocol", "rendered Prompt protocol differs")
    expected_body = make_stage_one_request_body(config, row.rendered_prompt)
    if _canonical_json(expected_body) != row.request_body_canonical_json:
        _fail("request_evidence.request_body", "request body differs from exact renderer output")
    if (
        body.get("model") != config.model
        or body.get("thinking") != expected_body.get("thinking")
        or body.get("thinking") != {"type": "enabled"}
        or body.get("response_format") != {"type": "json_object"}
        or body.get("messages") != [{"role": "user", "content": row.rendered_prompt}]
    ):
        _fail(
            "request_evidence.request_body_binding",
            "request body model/Thinking/response_format/messages binding differs",
        )
    if (
        row.prompt_contract_id != contract.contract_id
        or row.prompt_schema_id != schema.schema_id
        or row.generation_profile_id != profile.profile_id
    ):
        _fail("request_evidence.profile_parent", "Provider request Profile parent differs")


def _validate_exact_evidence_set(
    *,
    evidence_set: models.ExactPromptEvidenceSet,
    expected_coordinates: tuple[models.PromptCoordinate, ...],
    manifest: v192.JsonExplicitDevelopmentManifest,
    packages: v192.JsonExplicitRunnerPackageCatalog,
    runner: v192.JsonExplicitRunnerContract,
    config: AgentModelConfig,
    contract: v192.JsonExplicitPromptContract,
    schema: v192.JsonExplicitPromptSchema,
    profile: v192.JsonExplicitGenerationProfile,
) -> None:
    rows = evidence_set.rows
    if len(rows) != 792 or len({row.row_id for row in rows}) != 792:
        _fail("evidence_set.row_uniqueness", "exact Prompt evidence set repeats a row")
    coordinates = tuple(row.coordinate for row in rows)
    if len({item.coordinate_id for item in coordinates}) != 792:
        _fail(
            "evidence_set.coordinate_uniqueness", "exact Prompt evidence set repeats a coordinate"
        )
    expected_by_id = {item.coordinate_id: item for item in expected_coordinates}
    actual_by_id = {item.coordinate_id: item for item in coordinates}
    if set(actual_by_id) != set(expected_by_id):
        _fail("evidence_set.exact_coordinate_set", "exact Prompt coordinate set differs")
    for coordinate_id, expected in expected_by_id.items():
        if _canonical_bytes(actual_by_id[coordinate_id]) != _canonical_bytes(expected):
            _fail("evidence_set.coordinate_payload", "Prompt coordinate payload differs")
    if evidence_set.expected_coordinate_ids != tuple(sorted(expected_by_id)):
        _fail("evidence_set.expected_coordinate_parent", "expected coordinate-set parent differs")
    manifest_jobs = {item.job_id: item for item in manifest.jobs}
    package_ids = {item.runner_package_id for item in packages.packages}
    per_job: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        coordinate = row.coordinate
        job = manifest_jobs.get(coordinate.fresh_job_id)
        if job is None:
            _fail("evidence_set.job_set", "Prompt row references a non-Manifest Job")
        if (
            coordinate.source_job_id != job.source_job_id
            or coordinate.runner_package_id != job.runner_package_id
            or coordinate.source_runner_package_id != job.source_runner_package_id
            or coordinate.replica_index != job.replica_index
            or coordinate.runner_package_id not in package_ids
        ):
            _fail("evidence_set.job_parent", "Prompt row crosses a Job/Package parent")
        if coordinate.phase != "final":
            assert coordinate.component_index is not None
            if (
                coordinate.component_index >= len(job.schedule_ids)
                or coordinate.schedule_id != job.schedule_ids[coordinate.component_index]
            ):
                _fail("evidence_set.schedule_parent", "Prompt row crosses a Schedule parent")
        per_job[job.job_id][coordinate.phase] += 1
        _validate_request_row(
            row=row,
            config=config,
            contract=contract,
            schema=schema,
            profile=profile,
        )
    if set(per_job) != set(manifest_jobs):
        _fail("evidence_set.job_set", "Prompt evidence does not cover the exact fresh Job set")
    if any(counts["first_action"] != 1 or counts["final"] != 1 for counts in per_job.values()):
        _fail(
            "evidence_set.job_phase_cardinality", "a Job lacks exactly one first Action and Final"
        )
    if (
        evidence_set.manifest_id != manifest.manifest_id
        or evidence_set.runner_id != runner.runner_id
        or evidence_set.runner_package_catalog_id != packages.catalog_id
    ):
        _fail("evidence_set.aggregate_parent", "Prompt evidence aggregate parent differs")


def _execute_zero_call_runner(
    *,
    package_root: Path,
    prepared: v188.PreparedExecution,
    contract: v192.JsonExplicitPromptContract,
    schema: v192.JsonExplicitPromptSchema,
    profile: v192.JsonExplicitGenerationProfile,
    packages: v192.JsonExplicitRunnerPackageCatalog,
    manifest: v192.JsonExplicitDevelopmentManifest,
    runner_contract: v192.JsonExplicitRunnerContract,
    expected_coordinates: tuple[models.PromptCoordinate, ...],
) -> tuple[models.ExactPromptEvidenceSet, dict[str, Any]]:
    profile_payload = _load(package_root / v188.MODEL_PROFILE_PATH)
    config = AgentModelConfig.model_validate(profile_payload["model"])
    transport = CredentialFreeFixtureTransport()
    runtime_runner = CredentialFreeExactFutureRunner(
        contract=contract,
        schema=schema,
        config=config,
        transport=transport,
    )
    source_jobs = {item.job_id: item for item in prepared.frozen.manifest.jobs}
    expected_by_tuple = {
        (
            item.fresh_job_id,
            item.invocation_index,
            item.phase,
            item.state_token,
            item.rejected_action_id,
            item.rejection_receipt_id,
        ): item
        for item in expected_coordinates
    }
    rows: list[models.ProviderRequestEvidenceRow] = []
    current_results: dict[str, Any] = {}
    action_grammar = compile_semantic_action_response_grammar()

    def capture(
        *,
        fresh: v192.JsonExplicitDevelopmentJob,
        invocation_index: int,
        phase: models.PromptPhase,
        state_token: str,
        rejected_action_id: str | None,
        rejection_receipt_id: str | None,
    ) -> None:
        key = (
            fresh.job_id,
            invocation_index,
            phase,
            state_token,
            rejected_action_id,
            rejection_receipt_id,
        )
        coordinate = expected_by_tuple.get(key)
        if coordinate is None:
            _fail("runner.coordinate", "Runner emitted an unregistered Prompt coordinate")
        rows.append(
            _request_row(
                coordinate=coordinate,
                invocation=runtime_runner.invocations[-1],
                contract=contract,
                schema=schema,
                profile=profile,
            )
        )

    for fresh in manifest.jobs:
        source = source_jobs[fresh.source_job_id]
        context = frozen_runtime.prepare_job(source, prepared.runtime_catalog)
        state = frozen_runtime._initialize(context)  # noqa: SLF001
        invocation_index = 0
        while state.current_index < len(state.ordered_components):
            component_index = state.current_index
            prompt = step_runtime.render_next_prompt(state)
            dispositions = frozen_runtime._candidate_dispositions(state, prompt)  # noqa: SLF001
            core = _action_core(prompt, prepared)
            selection = frozen_runtime._reference_selection(  # noqa: SLF001
                state, prompt, dispositions, component_index
            )
            routed = runtime_runner.invoke_action(core=core, fixture_response=selection)
            phase: models.PromptPhase = (
                "first_action" if component_index == 0 else "subsequent_action"
            )
            capture(
                fresh=fresh,
                invocation_index=invocation_index,
                phase=phase,
                state_token=prompt.state.state_token,
                rejected_action_id=None,
                rejection_receipt_id=None,
            )
            invocation_index += 1
            for invalid in (item for item in dispositions if not item.acceptance.accepted):
                branch = copy.deepcopy(state)
                rejected = step_runtime.step(branch, invalid.action_id)
                receipt = _rejection_receipt(rejected)
                correction_prompt = step_runtime.render_next_prompt(branch)
                correction_rows = frozen_runtime._candidate_dispositions(  # noqa: SLF001
                    branch, correction_prompt
                )
                correction_selection = frozen_runtime._reference_correction(  # noqa: SLF001
                    branch,
                    correction_prompt,
                    correction_rows,
                    component_index,
                    invalid.action_id,
                )
                routed_correction = runtime_runner.invoke_correction(
                    core=_action_core(correction_prompt, prepared),
                    fixture_response=correction_selection,
                )
                capture(
                    fresh=fresh,
                    invocation_index=invocation_index,
                    phase="correction",
                    state_token=correction_prompt.state.state_token,
                    rejected_action_id=invalid.action_id,
                    rejection_receipt_id=receipt,
                )
                invocation_index += 1
                corrected_action = frozen_runtime._parse_action_response(  # noqa: SLF001
                    correction_prompt,
                    routed_correction,
                    grammar=action_grammar,
                    profile=prepared.profile,
                )
                if corrected_action is None or not getattr(
                    step_runtime.step(branch, corrected_action), "action_accepted", False
                ):
                    _fail("runner.correction", "reference Correction did not commit")
            action = frozen_runtime._parse_action_response(  # noqa: SLF001
                prompt,
                routed,
                grammar=action_grammar,
                profile=prepared.profile,
            )
            if action is None or not getattr(
                step_runtime.step(state, action), "action_accepted", False
            ):
                _fail("runner.action", "reference Action did not commit")
        result = step_runtime.finalize(state)
        old_final_prompt, _ = v188.render_final_prompt(
            context=context,
            result=result,
            grammar=prepared.final_grammar,
        )
        runtime_runner.invoke_final(core=old_final_prompt, fixture_response={"fixture": "final"})
        capture(
            fresh=fresh,
            invocation_index=invocation_index,
            phase="final",
            state_token=result.result_id,
            rejected_action_id=None,
            rejection_receipt_id=None,
        )
        frozen_runtime._parse_final_fixture(  # noqa: SLF001
            result,
            context.source,
            grammar=prepared.final_grammar,
            profile=prepared.profile,
        )
        current_results[fresh.source_job_id] = result
    expected_ids = tuple(sorted(item.coordinate_id for item in expected_coordinates))
    evidence_set = cast(
        models.ExactPromptEvidenceSet,
        models.make_identity(
            models.ExactPromptEvidenceSet,
            {
                "manifest_id": manifest.manifest_id,
                "runner_id": runner_contract.runner_id,
                "runner_package_catalog_id": packages.catalog_id,
                "expected_coordinate_set_id": canonical_hash(
                    expected_ids,
                    prefix="json_explicit_expected_prompt_coordinate_set:",
                ),
                "expected_coordinate_ids": expected_ids,
                "rows": tuple(rows),
            },
            field="evidence_set_id",
            prefix="json_explicit_exact_prompt_evidence_set:",
        ),
    )
    _validate_exact_evidence_set(
        evidence_set=evidence_set,
        expected_coordinates=expected_coordinates,
        manifest=manifest,
        packages=packages,
        runner=runner_contract,
        config=config,
        contract=contract,
        schema=schema,
        profile=profile,
    )
    if len(runtime_runner.invocations) != 792:
        _fail("runner.invocation_count", "exact future Runner invocation denominator differs")
    if transport.sink_invocation_count != 792 or transport.provider_calls != 0:
        _fail("runner.transport_sink", "credential-free transport sink denominator differs")
    return evidence_set, current_results


def _callsite_totality(
    *,
    package_root: Path,
    runner_id: str,
    local_invocation_count: int,
) -> models.RunnerCallsiteTotalityAudit:
    repository = package_root.parent
    path = repository / RUNNER_SOURCE_RELATIVE_PATH
    payload = path.read_bytes()
    tree = ast.parse(payload, filename=str(path))
    runner_classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "CredentialFreeExactFutureRunner"
    ]
    if len(runner_classes) != 1:
        _fail("callsite.runner_class", "exact future Runner class denominator differs")
    runner_class = runner_classes[0]
    methods = {
        node.name: node
        for node in runner_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    invoke = methods.get("_invoke")
    if invoke is None:
        _fail("callsite.invoke", "exact future Runner lacks its single _invoke seam")

    def call_names(node: ast.AST) -> tuple[str, ...]:
        names: list[str] = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if isinstance(child.func, ast.Name):
                names.append(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                names.append(child.func.attr)
        return tuple(names)

    invoke_calls = call_names(invoke)
    renderer_count = invoke_calls.count("_render_prompt")
    body_count = invoke_calls.count("make_stage_one_request_body")
    sink_count = invoke_calls.count("invoke")
    ordered_call_lines: dict[str, list[int]] = defaultdict(list)
    for node in ast.walk(invoke):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            ordered_call_lines[node.func.id].append(node.lineno)
        elif isinstance(node.func, ast.Attribute):
            ordered_call_lines[node.func.attr].append(node.lineno)
    callsite_order_exact = (
        len(ordered_call_lines["_render_prompt"]) == 1
        and len(ordered_call_lines["make_stage_one_request_body"]) == 1
        and len(ordered_call_lines["invoke"]) == 1
        and ordered_call_lines["_render_prompt"][0]
        < ordered_call_lines["make_stage_one_request_body"][0]
        < ordered_call_lines["invoke"][0]
    )
    route_counts = {
        name: call_names(methods[name]).count("_invoke")
        for name in ("invoke_action", "invoke_correction", "invoke_final")
    }
    imported_roots = {
        name.split(".")[0]
        for node in tree.body
        for name in (
            tuple(alias.name for alias in node.names)
            if isinstance(node, ast.Import)
            else ((node.module or ""),)
            if isinstance(node, ast.ImportFrom)
            else ()
        )
    }
    network_count = len(imported_roots & {"requests", "urllib", "httpx", "aiohttp"})
    all_calls = call_names(tree)
    provider_constructor_count = sum(
        name in {"StageOneProviderClient", "DeepSeekClient", "ProviderClient"} for name in all_calls
    )
    if (
        renderer_count != 1
        or body_count != 1
        or sink_count != 1
        or any(value != 1 for value in route_counts.values())
        or network_count
        or provider_constructor_count
        or not callsite_order_exact
    ):
        _fail("callsite.totality", "future Runner source contains a renderer bypass")
    accepted = _load(package_root / V179_DIR / "accepted_prefix_surface_audit.json")
    if (
        accepted.get("audit_id") != EXPECTED_ACCEPTED_PREFIX_AUDIT_ID
        or accepted.get("replica_execution_count") != 4_632
        or accepted.get("reached_prefix_state_count") != 14_388
        or accepted.get("candidate_evaluation_count") != 41_124
    ):
        _fail("callsite.reachability_parent", "v26.179 accepted-prefix parent differs")
    return cast(
        models.RunnerCallsiteTotalityAudit,
        models.make_identity(
            models.RunnerCallsiteTotalityAudit,
            {
                "runner_id": runner_id,
                "runner_source_relative_path": RUNNER_SOURCE_RELATIVE_PATH,
                "runner_source_sha256": _sha256_bytes(payload),
                "renderer_precedes_request_body_callsite": callsite_order_exact,
                "request_body_precedes_transport_sink_callsite": callsite_order_exact,
                "local_invocation_count": local_invocation_count,
            },
            field="audit_id",
            prefix="finance_v26_193_runner_callsite_totality_audit:",
        ),
    )


_MISSING = object()


def _leaf_differences(old: Any, new: Any, path: str = "$") -> Iterable[tuple[str, Any, Any]]:
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new)):
            yield from _leaf_differences(
                old.get(key, _MISSING),
                new.get(key, _MISSING),
                f"{path}.{key}",
            )
        return
    if isinstance(old, list) and isinstance(new, list):
        for index in range(max(len(old), len(new))):
            left = old[index] if index < len(old) else _MISSING
            right = new[index] if index < len(new) else _MISSING
            yield from _leaf_differences(left, right, f"{path}[{index}]")
        return
    if old != new:
        yield path, old, new


def _diff_json(value: Any) -> str:
    return '"<missing>"' if value is _MISSING else _canonical_json(value)


def _difference_class(
    path: str,
) -> Literal[
    "content_identity",
    "parent_identity",
    "semantic_event_or_receipt",
    "semantic_validity_or_answer",
    "other",
]:
    if path.startswith(("$.events", "$.steps", "$.selected_source_choice_handles")):
        return "semantic_event_or_receipt"
    if path == "$.result_id" or path.endswith(".report_id"):
        return "content_identity"
    if path.endswith(("_parent_hash", "_report_id", ".trace_hash")) or path.startswith(
        (
            "$.package_id",
            "$.source_package_id",
            "$.reference_path_hash",
        )
    ):
        return "parent_identity"
    if path.startswith(
        (
            "$.task_validity",
            "$.mechanism_qualification",
            "$.qualified_validity",
            "$.projected_public_answer",
            "$.public_citations",
        )
    ):
        return "semantic_validity_or_answer"
    return "other"


def _drift_decomposition(
    *,
    package_root: Path,
    manifest: v192.JsonExplicitDevelopmentManifest,
    current_results: dict[str, Any],
    v179_source_archive: Path,
) -> models.ResultDriftDecompositionAudit:
    catalog_path = package_root / V176_DIR / "authoritative_development_catalog.json"
    if _sha256_path(catalog_path)[0] != V176_CATALOG_SHA256:
        _fail("drift.old_catalog", "v26.176 historical Result Catalog bytes differ")
    catalog = _load(catalog_path)
    _validate_archive(
        v179_source_archive,
        expected_commit=V179_SOURCE_COMMIT,
        expected_tree=V179_SOURCE_TREE,
        label="v26_179",
    )
    with tempfile.TemporaryDirectory(prefix="v26-193-v179-replay-") as temporary:
        temporary_root = Path(temporary)
        extracted = temporary_root / "source"
        replay_path = temporary_root / "results.json"
        extracted.mkdir()
        with tarfile.open(v179_source_archive, mode="r:") as archive:
            archive.extractall(extracted, filter="data")
        snapshot_package = extracted / "trusted_data_synthesis"
        source_helper = package_root.parent / (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "v179_source_snapshot_result_replay.py"
        )
        # Execute from the temporary root so the snapshot's sibling ``statistics.py``
        # cannot shadow Python's standard-library module during interpreter startup.
        helper = temporary_root / "v179_source_snapshot_result_replay.py"
        _write_bytes_no_replace(helper, source_helper.read_bytes())
        environment = os.environ.copy()
        environment.pop("DEEPSEEK_API_KEY", None)
        environment["PYTHONPATH"] = str(snapshot_package / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        replay = subprocess.run(
            (
                sys.executable,
                str(helper),
                "--package-root",
                str(snapshot_package),
                "--output-path",
                str(replay_path),
            ),
            cwd=snapshot_package,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if replay.returncode != 0:
            _fail("drift.v179_snapshot_replay", "v26.179 exact source snapshot replay failed")
        snapshot_payload = _load(replay_path)
    if snapshot_payload.get("row_count") != 192 or snapshot_payload.get("provider_calls") != 0:
        _fail("drift.v179_snapshot_denominator", "v26.179 snapshot Result set differs")
    snapshot_results = {item["job_id"]: item["result"] for item in snapshot_payload["rows"]}
    old_packages = {
        package["source_v171_package_artifact_id"]: package
        for group in catalog["groups"]
        for package in group["packages"]
    }
    witnesses: list[models.ResultDriftWitness] = []
    matches = 0
    snapshot_old_matches = 0
    snapshot_current_matches = 0
    for fresh in manifest.jobs:
        current = current_results[fresh.source_job_id]
        historical_package = old_packages.get(fresh.source_package_artifact_id)
        if (
            historical_package is None
            or historical_package["package_id"] != fresh.execution_package_id
        ):
            _fail("drift.old_result_parent", "historical Result Package parent differs")
        old = historical_package["replica_results"][fresh.replica_index]
        snapshot = snapshot_results.get(fresh.source_job_id)
        if snapshot is None:
            _fail("drift.v179_snapshot_job_set", "v26.179 snapshot lacks a source Job")
        new = current.model_dump(mode="json", warnings=False)
        snapshot_old_match = _canonical_bytes(snapshot) == _canonical_bytes(old)
        snapshot_current_match = _canonical_bytes(snapshot) == _canonical_bytes(new)
        snapshot_old_matches += int(snapshot_old_match)
        snapshot_current_matches += int(snapshot_current_match)
        if old["result_id"] == new["result_id"]:
            if _canonical_bytes(old) != _canonical_bytes(new):
                _fail("drift.content_identity", "equal Result IDs carry unequal canonical bytes")
            matches += 1
            continue
        raw_differences = tuple(_leaf_differences(old, new))
        differences = tuple(
            models.FieldDifferenceWitness(
                json_path=path,
                old_present=old_value is not _MISSING,
                new_present=new_value is not _MISSING,
                old_canonical_json=_diff_json(old_value),
                new_canonical_json=_diff_json(new_value),
                old_sha256=_sha256_bytes(_diff_json(old_value).encode("utf-8")),
                new_sha256=_sha256_bytes(_diff_json(new_value).encode("utf-8")),
                classification=_difference_class(path),
            )
            for path, old_value, new_value in raw_differences
        )
        old_bytes = _canonical_bytes(old)
        new_bytes = _canonical_bytes(new)
        values = {
            "fresh_job_id": fresh.job_id,
            "source_job_id": fresh.source_job_id,
            "capability_family": fresh.capability_family,
            "replica_index": fresh.replica_index,
            "old_result_id": old["result_id"],
            "snapshot_result_id": snapshot["result_id"],
            "new_result_id": new["result_id"],
            "snapshot_matches_old_canonical_bytes": snapshot_old_match,
            "snapshot_matches_current_canonical_bytes": snapshot_current_match,
            "old_result_sha256": _sha256_bytes(old_bytes),
            "new_result_sha256": _sha256_bytes(new_bytes),
            "old_result_byte_count": len(old_bytes),
            "new_result_byte_count": len(new_bytes),
            "differences": differences,
            "changed_field_count": len(differences),
            "first_changed_path": differences[0].json_path,
            "semantic_event_or_receipt_difference": any(
                item.classification == "semantic_event_or_receipt" for item in differences
            ),
            "semantic_validity_or_answer_difference": any(
                item.classification == "semantic_validity_or_answer" for item in differences
            ),
        }
        witnesses.append(
            cast(
                models.ResultDriftWitness,
                models.make_identity(
                    models.ResultDriftWitness,
                    values,
                    field="witness_id",
                    prefix="json_prompt_result_drift_witness:",
                ),
            )
        )
    if matches != 144 or len(witnesses) != 48:
        _fail("drift.denominator", "historical/current Result drift denominator differs")
    if snapshot_old_matches != 192 or snapshot_current_matches != 144:
        _fail("drift.v179_snapshot_comparison", "v26.179 snapshot Result comparison differs")
    witnesses.sort(key=lambda item: item.source_job_id)
    semantic = sum(item.semantic_event_or_receipt_difference for item in witnesses)
    validity = sum(item.semantic_validity_or_answer_difference for item in witnesses)
    return cast(
        models.ResultDriftDecompositionAudit,
        models.make_identity(
            models.ResultDriftDecompositionAudit,
            {
                "manifest_id": manifest.manifest_id,
                "historical_catalog_sha256": V176_CATALOG_SHA256,
                "v179_source_commit": V179_SOURCE_COMMIT,
                "v179_source_tree": V179_SOURCE_TREE,
                "v179_source_archive_sha256": _sha256_path(v179_source_archive)[0],
                "v179_source_archive_byte_count": _sha256_path(v179_source_archive)[1],
                "witnesses": tuple(witnesses),
                "semantic_event_or_receipt_drift_count": semantic,
                "semantic_validity_or_answer_drift_count": validity,
                "online_execution_blocked_by_drift_if_semantic": bool(semantic or validity),
                "semantic_equivalence_claimed": False,
            },
            field="audit_id",
            prefix="finance_v26_193_result_drift_decomposition_audit:",
        ),
    )


def _unsafe_rehash(
    model_type: type[BaseModel], values: dict[str, Any], *, field: str, prefix: str
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    identifier = canonical_hash(
        provisional.model_dump(mode="json", exclude={field}, warnings=False), prefix=prefix
    )
    return model_type.model_construct(**{field: identifier}, **values)


def _rehash_job(
    job: v192.JsonExplicitDevelopmentJob, **changes: Any
) -> v192.JsonExplicitDevelopmentJob:
    values = job.model_dump(mode="python", exclude={"job_id"}, warnings=False)
    values.update(changes)
    parent = {
        "source_job_id": values["source_job_id"],
        "runner_package_id": values["runner_package_id"],
        "generation_profile_id": values["generation_profile_id"],
        "prompt_schema_id": values["prompt_schema_id"],
    }
    values.update(
        raw_namespace=canonical_hash(parent, prefix="json_explicit_raw_namespace:"),
        result_namespace=canonical_hash(parent, prefix="json_explicit_result_namespace:"),
        deterministic_seed_id=canonical_hash(parent, prefix="json_explicit_deterministic_seed:"),
    )
    return cast(
        v192.JsonExplicitDevelopmentJob,
        models.make_identity(
            v192.JsonExplicitDevelopmentJob,
            values,
            field="job_id",
            prefix="json_explicit_development_job:",
        ),
    )


def _rehash_manifest(
    manifest: v192.JsonExplicitDevelopmentManifest,
    *,
    jobs: tuple[v192.JsonExplicitDevelopmentJob, ...] | None = None,
    **changes: Any,
) -> v192.JsonExplicitDevelopmentManifest:
    values = manifest.model_dump(mode="python", exclude={"manifest_id"}, warnings=False)
    selected = jobs or manifest.jobs
    values.update(
        jobs=selected,
        expected_job_ids=tuple(sorted(item.job_id for item in selected)),
        source_job_ids=tuple(sorted(item.source_job_id for item in selected)),
    )
    values.update(changes)
    return cast(
        v192.JsonExplicitDevelopmentManifest,
        models.make_identity(
            v192.JsonExplicitDevelopmentManifest,
            values,
            field="manifest_id",
            prefix="json_explicit_development_manifest:",
        ),
    )


def _rehash_runner(
    runner: v192.JsonExplicitRunnerContract, **changes: Any
) -> v192.JsonExplicitRunnerContract:
    values = runner.model_dump(mode="python", exclude={"runner_id"}, warnings=False)
    values.update(changes)
    return cast(
        v192.JsonExplicitRunnerContract,
        models.make_identity(
            v192.JsonExplicitRunnerContract,
            values,
            field="runner_id",
            prefix="json_explicit_runner_contract:",
        ),
    )


def _unsafe_evidence_set(
    evidence_set: models.ExactPromptEvidenceSet,
    *,
    rows: tuple[models.ProviderRequestEvidenceRow, ...],
) -> models.ExactPromptEvidenceSet:
    values = evidence_set.model_dump(mode="python", exclude={"evidence_set_id"}, warnings=False)
    coordinates = tuple(row.coordinate.coordinate_id for row in rows)
    expected = tuple(sorted(coordinates))
    values.update(
        rows=rows,
        expected_coordinate_ids=expected,
        expected_coordinate_set_id=canonical_hash(
            expected, prefix="json_explicit_expected_prompt_coordinate_set:"
        ),
    )
    return cast(
        models.ExactPromptEvidenceSet,
        _unsafe_rehash(
            models.ExactPromptEvidenceSet,
            values,
            field="evidence_set_id",
            prefix="json_explicit_exact_prompt_evidence_set:",
        ),
    )


def _rehash_row(
    row: models.ProviderRequestEvidenceRow, **changes: Any
) -> models.ProviderRequestEvidenceRow:
    values = row.model_dump(mode="python", exclude={"row_id"}, warnings=False)
    values.update(changes)
    prompt = str(values["rendered_prompt"])
    core = str(values["prompt_core_canonical_json"])
    request = str(values["request_body_canonical_json"])
    values.update(
        rendered_prompt_sha256=_sha256_bytes(prompt.encode()),
        prompt_core_sha256=_sha256_bytes(core.encode()),
        request_body_sha256=_sha256_bytes(request.encode()),
        request_body_byte_count=len(request.encode()),
    )
    return cast(
        models.ProviderRequestEvidenceRow,
        models.make_identity(
            models.ProviderRequestEvidenceRow,
            values,
            field="row_id",
            prefix="json_explicit_provider_request_evidence_row:",
        ),
    )


def _validate_source_projection_object(candidate: models.SourceProjectionAudit) -> None:
    if candidate.audited_v26_192_source_commit != AUDITED_V192_SOURCE_COMMIT:
        _fail("source_projection.v26_192_commit", "v26_192 source Archive commit differs")
    if candidate.audited_v26_192_source_tree != AUDITED_V192_SOURCE_TREE:
        _fail("source_projection.v26_192_tree", "v26_192 source Archive tree differs")


def _typed_attack(
    *, name: str, expected_stage: str, expected_reason: str, operation: Callable[[], None]
) -> models.TypedAttackResult:
    try:
        operation()
    except RepairValidationError as error:
        if not error.target_validator_reached:
            raise ValueError(f"attack failed before target validator:{name}") from error
        values = {
            "attack_name": name,
            "expected_exception_type": "RepairValidationError",
            "actual_exception_type": type(error).__name__,
            "expected_stage": expected_stage,
            "actual_stage": error.stage,
            "expected_reason": expected_reason,
            "actual_reason": error.reason,
        }
        return cast(
            models.TypedAttackResult,
            models.make_identity(
                models.TypedAttackResult,
                values,
                field="attack_id",
                prefix="json_prompt_typed_attack_result:",
            ),
        )
    raise ValueError(f"fully-rehashed attack was accepted:{name}")


def _destructive_audit(
    *,
    package_root: Path,
    source_projection: models.SourceProjectionAudit,
    prepared: v188.PreparedExecution,
    contract: v192.JsonExplicitPromptContract,
    schema: v192.JsonExplicitPromptSchema,
    profile: v192.JsonExplicitGenerationProfile,
    packages: v192.JsonExplicitRunnerPackageCatalog,
    manifest: v192.JsonExplicitDevelopmentManifest,
    runner: v192.JsonExplicitRunnerContract,
    evidence_set: models.ExactPromptEvidenceSet,
    expected_coordinates: tuple[models.PromptCoordinate, ...],
) -> models.TypedDestructiveAudit:
    config = AgentModelConfig.model_validate(_load(package_root / v188.MODEL_PROFILE_PATH)["model"])

    def validate_evidence(candidate: models.ExactPromptEvidenceSet) -> None:
        _validate_exact_evidence_set(
            evidence_set=candidate,
            expected_coordinates=expected_coordinates,
            manifest=manifest,
            packages=packages,
            runner=runner,
            config=config,
            contract=contract,
            schema=schema,
            profile=profile,
        )

    rows_by_phase = {
        phase: tuple(row for row in evidence_set.rows if row.coordinate.phase == phase)
        for phase in ("first_action", "subsequent_action", "correction", "final")
    }
    duplicated_rows = tuple(
        row
        for phase, count in (
            ("first_action", 192),
            ("subsequent_action", 288),
            ("correction", 120),
            ("final", 192),
        )
        for row in (rows_by_phase[phase][0],) * count
    )
    per_job_rows = {
        job_id: tuple(row for row in evidence_set.rows if row.coordinate.fresh_job_id == job_id)
        for job_id in {row.coordinate.fresh_job_id for row in evidence_set.rows}
    }
    groups: dict[tuple[int, int], list[str]] = defaultdict(list)
    for job_id, rows in per_job_rows.items():
        groups[(len(rows), sum(row.coordinate.phase == "correction" for row in rows))].append(
            job_id
        )
    dropped, replacement = next(
        (items[0], items[1]) for items in groups.values() if len(items) >= 2
    )
    dropped_job = next(item for item in manifest.jobs if item.job_id == dropped)
    cloned_replacement_rows: list[models.ProviderRequestEvidenceRow] = []
    for row in per_job_rows[replacement]:
        coordinate_values = row.coordinate.model_dump(
            mode="python", exclude={"coordinate_id"}, warnings=False
        )
        coordinate_values.update(
            fresh_job_id=dropped_job.job_id,
            source_job_id=dropped_job.source_job_id,
            runner_package_id=dropped_job.runner_package_id,
            source_runner_package_id=dropped_job.source_runner_package_id,
            replica_index=dropped_job.replica_index,
        )
        cloned_coordinate = cast(
            models.PromptCoordinate,
            models.make_identity(
                models.PromptCoordinate,
                coordinate_values,
                field="coordinate_id",
                prefix="json_explicit_prompt_coordinate:",
            ),
        )
        cloned_replacement_rows.append(_rehash_row(row, coordinate=cloned_coordinate))
    dropped_rows = tuple(
        row for row in evidence_set.rows if row.coordinate.fresh_job_id != dropped
    ) + tuple(cloned_replacement_rows)

    source_row = evidence_set.rows[0]
    target_job = next(
        item
        for item in manifest.jobs
        if item.job_id != source_row.coordinate.fresh_job_id
        and item.replica_index == source_row.coordinate.replica_index
    )
    coordinate_values = source_row.coordinate.model_dump(
        mode="python", exclude={"coordinate_id"}, warnings=False
    )
    coordinate_values.update(
        fresh_job_id=target_job.job_id,
        source_job_id=target_job.source_job_id,
        runner_package_id=target_job.runner_package_id,
        source_runner_package_id=target_job.source_runner_package_id,
    )
    crossed_coordinate = cast(
        models.PromptCoordinate,
        models.make_identity(
            models.PromptCoordinate,
            coordinate_values,
            field="coordinate_id",
            prefix="json_explicit_prompt_coordinate:",
        ),
    )
    crossed_rows = (_rehash_row(source_row, coordinate=crossed_coordinate), *evidence_set.rows[1:])
    body_row = evidence_set.rows[0]
    changed_body = json.loads(body_row.request_body_canonical_json)
    changed_body["response_format"] = {"type": "text"}
    body_rows = (
        _rehash_row(body_row, request_body_canonical_json=_canonical_json(changed_body)),
        *evidence_set.rows[1:],
    )
    other_core_row = next(
        row
        for row in evidence_set.rows
        if row.coordinate.prompt_kind == source_row.coordinate.prompt_kind
        and row.coordinate.fresh_job_id != source_row.coordinate.fresh_job_id
    )
    core_swap_rows = (
        _rehash_row(
            source_row,
            rendered_prompt=other_core_row.rendered_prompt,
            prompt_core_canonical_json=other_core_row.prompt_core_canonical_json,
            request_body_canonical_json=other_core_row.request_body_canonical_json,
        ),
        *evidence_set.rows[1:],
    )
    extra_protocol = json.loads(source_row.rendered_prompt)
    extra_protocol["provider_output_protocol"]["unauthorized_extra"] = True
    extra_rendered = _canonical_json(extra_protocol)
    extra_protocol_rows = (
        _rehash_row(
            source_row,
            rendered_prompt=extra_rendered,
            request_body_canonical_json=_canonical_json(
                make_stage_one_request_body(config, extra_rendered)
            ),
        ),
        *evidence_set.rows[1:],
    )

    left, right = next(
        (left, right)
        for left in manifest.jobs
        for right in manifest.jobs
        if left.replica_index == right.replica_index
        and left.runner_package_id != right.runner_package_id
    )
    swapped_left = _rehash_job(left, runner_package_id=right.runner_package_id)
    swapped_right = _rehash_job(right, runner_package_id=left.runner_package_id)
    swapped_jobs = tuple(
        swapped_left
        if item.job_id == left.job_id
        else swapped_right
        if item.job_id == right.job_id
        else item
        for item in manifest.jobs
    )
    swap_manifest = _rehash_manifest(
        manifest,
        jobs=swapped_jobs,
    )
    swap_runner = _rehash_runner(runner, manifest_id=swap_manifest.manifest_id)
    source_swapped_left = _rehash_job(left, source_job_id=right.source_job_id)
    source_swapped_right = _rehash_job(right, source_job_id=left.source_job_id)
    source_swapped_jobs = tuple(
        source_swapped_left
        if item.job_id == left.job_id
        else source_swapped_right
        if item.job_id == right.job_id
        else item
        for item in manifest.jobs
    )
    source_manifest = _rehash_manifest(
        manifest,
        jobs=source_swapped_jobs,
    )
    source_runner = _rehash_runner(runner, manifest_id=source_manifest.manifest_id)
    fake_catalog = canonical_hash(
        {"real": packages.catalog_id, "attack": "replacement"},
        prefix="json_explicit_runner_package_catalog:",
    )
    replaced_manifest = _rehash_manifest(manifest, runner_package_catalog_id=fake_catalog)
    replaced_runner = _rehash_runner(
        runner,
        manifest_id=replaced_manifest.manifest_id,
        runner_package_catalog_id=fake_catalog,
    )

    def validate_parent(candidate_manifest: Any, candidate_runner: Any) -> None:
        _validate_parent_chain(
            prepared=prepared,
            contract=contract,
            schema=schema,
            profile=profile,
            packages=packages,
            manifest=candidate_manifest,
            runner=candidate_runner,
            source_projection_id=source_projection.audit_id,
        )

    attacks = [
        _typed_attack(
            name="duplicated_census_rows_with_preserved_phase_counts",
            expected_stage="evidence_set.row_uniqueness",
            expected_reason="exact Prompt evidence set repeats a row",
            operation=lambda: validate_evidence(
                _unsafe_evidence_set(evidence_set, rows=duplicated_rows)
            ),
        ),
        _typed_attack(
            name="dropped_job_plus_duplicated_replacement",
            expected_stage="evidence_set.exact_coordinate_set",
            expected_reason="exact Prompt coordinate set differs",
            operation=lambda: validate_evidence(
                _unsafe_evidence_set(evidence_set, rows=dropped_rows)
            ),
        ),
        _typed_attack(
            name="cross_job_prompt_row",
            expected_stage="evidence_set.exact_coordinate_set",
            expected_reason="exact Prompt coordinate set differs",
            operation=lambda: validate_evidence(
                _unsafe_evidence_set(evidence_set, rows=crossed_rows)
            ),
        ),
        _typed_attack(
            name="package_job_parent_swap",
            expected_stage="parent.job_package",
            expected_reason="fresh Job Runner Package is not source-owned",
            operation=lambda: validate_parent(swap_manifest, swap_runner),
        ),
        _typed_attack(
            name="source_job_fresh_package_mismatch",
            expected_stage="parent.job_source",
            expected_reason="fresh Job source Runner differs from source Job",
            operation=lambda: validate_parent(source_manifest, source_runner),
        ),
        _typed_attack(
            name="manifest_runner_parent_replacement",
            expected_stage="parent.manifest",
            expected_reason="fresh Manifest parent differs",
            operation=lambda: validate_parent(replaced_manifest, replaced_runner),
        ),
        _typed_attack(
            name="response_format_body_envelope_mismatch",
            expected_stage="request_evidence.request_body",
            expected_reason="request body differs from exact renderer output",
            operation=lambda: validate_evidence(_unsafe_evidence_set(evidence_set, rows=body_rows)),
        ),
        _typed_attack(
            name="cross_job_prompt_core_envelope_body_swap",
            expected_stage="request_evidence.expected_prompt_core",
            expected_reason="Prompt core differs from independent Runtime expectation",
            operation=lambda: validate_evidence(
                _unsafe_evidence_set(evidence_set, rows=core_swap_rows)
            ),
        ),
        _typed_attack(
            name="provider_protocol_extra_field",
            expected_stage="request_evidence.rendered_protocol",
            expected_reason="rendered Prompt protocol differs",
            operation=lambda: validate_evidence(
                _unsafe_evidence_set(evidence_set, rows=extra_protocol_rows)
            ),
        ),
    ]
    source_values = source_projection.model_dump(
        mode="python", exclude={"audit_id"}, warnings=False
    )
    commit_candidate = cast(
        models.SourceProjectionAudit,
        _unsafe_rehash(
            models.SourceProjectionAudit,
            {**source_values, "audited_v26_192_source_commit": "0" * 40},
            field="audit_id",
            prefix="finance_v26_193_source_projection_audit:",
        ),
    )
    tree_candidate = cast(
        models.SourceProjectionAudit,
        _unsafe_rehash(
            models.SourceProjectionAudit,
            {**source_values, "audited_v26_192_source_tree": "f" * 40},
            field="audit_id",
            prefix="finance_v26_193_source_projection_audit:",
        ),
    )
    attacks.extend(
        (
            _typed_attack(
                name="arbitrary_source_commit_injection",
                expected_stage="source_projection.v26_192_commit",
                expected_reason="v26_192 source Archive commit differs",
                operation=lambda: _validate_source_projection_object(commit_candidate),
            ),
            _typed_attack(
                name="arbitrary_source_tree_injection",
                expected_stage="source_projection.v26_192_tree",
                expected_reason="v26_192 source Archive tree differs",
                operation=lambda: _validate_source_projection_object(tree_candidate),
            ),
        )
    )
    for phase, prompt_kind in (
        ("first_action", "action"),
        ("correction", "correction"),
        ("final", "final"),
    ):
        row = rows_by_phase[phase][0]
        envelope = json.loads(row.rendered_prompt)
        envelope["prompt_core"] = {"phase_specific_mutation": prompt_kind}
        rendered = _canonical_json(envelope)
        candidate = _rehash_row(
            row,
            rendered_prompt=rendered,
            request_body_canonical_json=_canonical_json(
                make_stage_one_request_body(config, rendered)
            ),
        )
        attacks.append(
            _typed_attack(
                name=f"{prompt_kind}_phase_specific_core_mutation",
                expected_stage="request_evidence.rendered_prompt_core",
                expected_reason="rendered Prompt core differs",
                operation=partial(
                    _validate_request_row,
                    row=candidate,
                    config=config,
                    contract=contract,
                    schema=schema,
                    profile=profile,
                ),
            )
        )
    return cast(
        models.TypedDestructiveAudit,
        models.make_identity(
            models.TypedDestructiveAudit,
            {"attacks": tuple(attacks)},
            field="audit_id",
            prefix="finance_v26_193_typed_destructive_audit:",
        ),
    )


def _outcome_gap(*, manifest_id: str, runner_id: str) -> models.OutcomeAuthorityGapRegister:
    return cast(
        models.OutcomeAuthorityGapRegister,
        models.make_identity(
            models.OutcomeAuthorityGapRegister,
            {"manifest_id": manifest_id, "runner_id": runner_id},
            field="register_id",
            prefix="finance_v26_193_outcome_authority_gap_register:",
        ),
    )


def _gate(name: str, passed: bool, *evidence_ids: str) -> models.StaticGate:
    return cast(
        models.StaticGate,
        models.make_identity(
            models.StaticGate,
            {
                "gate_name": name,
                "passed": passed,
                "evidence_ids": tuple(evidence_ids),
                "evidence_count": len(evidence_ids),
            },
            field="gate_id",
            prefix="json_prompt_authority_static_gate:",
        ),
    )


def _static_audit(
    *,
    authorization: models.ExternalAuditAuthorization,
    source: models.SourceProjectionAudit,
    parent: models.ParentAuthorityAudit,
    evidence: models.ExactPromptEvidenceSet,
    callsite: models.RunnerCallsiteTotalityAudit,
    destructive: models.TypedDestructiveAudit,
    drift: models.ResultDriftDecompositionAudit,
    outcome_gap: models.OutcomeAuthorityGapRegister,
) -> models.StaticAudit:
    gates = (
        _gate(
            "external_audit_exact",
            authorization.audit_byte_count == 22_168,
            authorization.authorization_id,
        ),
        _gate(
            "v26_192_git_archive_commit_tree_exact",
            source.audited_v26_192_source_commit == AUDITED_V192_SOURCE_COMMIT
            and source.audited_v26_192_source_tree == AUDITED_V192_SOURCE_TREE,
            source.audit_id,
        ),
        _gate(
            "v26_192_formal_17_file_byte_rebuild",
            source.v26_192_byte_match_count == 17,
            source.audit_id,
        ),
        _gate(
            "v26_192_transitive_source_manifest",
            source.transitive_source_file_count > 0,
            source.audit_id,
        ),
        _gate(
            "fresh_package_source_parent_authority",
            parent.package_source_parent_match_count == 32,
            parent.audit_id,
        ),
        _gate(
            "fresh_job_source_parent_authority",
            parent.job_source_parent_match_count == 192,
            parent.audit_id,
        ),
        _gate(
            "fresh_manifest_runner_parent_authority",
            parent.manifest_parent_match and parent.runner_parent_match,
            parent.audit_id,
        ),
        _gate("prompt_row_uniqueness", evidence.unique_row_count == 792, evidence.evidence_set_id),
        _gate(
            "prompt_exact_coordinate_set",
            evidence.unique_coordinate_count == 792,
            evidence.expected_coordinate_set_id,
        ),
        _gate(
            "prompt_exact_job_first_final_cardinality",
            evidence.exact_job_count == 192,
            evidence.evidence_set_id,
        ),
        _gate(
            "prompt_schedule_package_parents",
            evidence.exact_parent_coordinate_match_count == 792,
            evidence.evidence_set_id,
        ),
        _gate(
            "request_body_exact_reparse",
            evidence.request_body_reparse_count == 792,
            evidence.evidence_set_id,
        ),
        _gate(
            "request_model_thinking_response_message_binding",
            evidence.exact_request_body_match_count == 792,
            evidence.evidence_set_id,
        ),
        _gate("runner_single_invoke_seam", callsite.invoke_method_count == 1, callsite.audit_id),
        _gate(
            "runner_renderer_request_order_totality",
            callsite.rendered_before_request_body_count == 792,
            callsite.audit_id,
        ),
        _gate(
            "runner_provider_bypass_absent", callsite.bypass_callsite_count == 0, callsite.audit_id
        ),
        _gate(
            "accepted_prefix_reachability_parent_bound",
            callsite.accepted_prefix_state_parent_count == 14_388,
            callsite.audit_id,
        ),
        _gate(
            "phase_specific_typed_controls",
            all(
                name in {item.attack_name for item in destructive.attacks}
                for name in (
                    "action_phase_specific_core_mutation",
                    "correction_phase_specific_core_mutation",
                    "final_phase_specific_core_mutation",
                )
            ),
            destructive.audit_id,
        ),
        _gate(
            "fully_rehashed_authority_attacks",
            destructive.fully_rehashed_count == 14,
            destructive.audit_id,
        ),
        _gate("result_drift_field_witness_complete", drift.witness_count == 48, drift.audit_id),
        _gate(
            "provider_and_historical_rewrite_zero",
            drift.provider_calls == 0 and drift.historical_result_rewrite_count == 0,
            drift.audit_id,
        ),
        _gate(
            "fresh_outcome_authority_gap_fail_closed",
            not outcome_gap.online_execution_authority and outcome_gap.missing_layer_count == 6,
            outcome_gap.register_id,
        ),
    )
    passed = sum(item.passed for item in gates)
    return cast(
        models.StaticAudit,
        models.make_identity(
            models.StaticAudit,
            {
                "gates": gates,
                "gate_count": len(gates),
                "passed_gate_count": passed,
                "failed_gate_count": len(gates) - passed,
                "repair_preflight_gates_passed": passed == len(gates),
            },
            field="audit_id",
            prefix="finance_v26_193_static_audit:",
        ),
    )


def _artifact_manifest(payloads: dict[str, bytes]) -> models.ArtifactManifest:
    members = tuple(
        models.FileBinding(
            relative_path=name,
            sha256=_sha256_bytes(payload),
            byte_count=len(payload),
            source_kind="v26_193_formal_artifact",
        )
        for name, payload in sorted(payloads.items())
    )
    values = {
        "run_id": RUN_ID,
        "members": members,
        "file_count": len(members),
        "total_byte_count": sum(item.byte_count for item in members),
        "artifact_root": canonical_hash(members, prefix="finance_v26_193_artifact_root:"),
    }
    return cast(
        models.ArtifactManifest,
        models.make_identity(
            models.ArtifactManifest,
            values,
            field="manifest_id",
            prefix="finance_v26_193_artifact_manifest:",
        ),
    )


def build(
    *,
    package_root: Path,
    output_dir: Path,
    external_audit_path: Path,
    v192_source_archive: Path,
    v179_source_archive: Path,
    current_source_archive: Path,
    current_source_commit: str,
    current_source_tree: str,
) -> BuildProducts:
    if os.environ.get("DEEPSEEK_API_KEY"):
        _fail("credential.provider", "credential-free v26.193 build requires credential removal")
    if output_dir.exists():
        raise FileExistsError(f"v26.193 output already exists:{output_dir}")
    authorization, external_audit = _authorization(external_audit_path)
    source = _source_projection(
        package_root=package_root,
        authorization=authorization,
        v192_source_archive=v192_source_archive,
        current_source_archive=current_source_archive,
        current_source_commit=current_source_commit,
        current_source_tree=current_source_tree,
    )
    _validate_source_projection_object(source)
    contract, schema, profile, packages, manifest, runner = _load_v192_objects(package_root)
    prepared = v188.prepare_execution(
        package_root=package_root,
        output_dir=output_dir / "provider_invocation_forbidden",
    )
    parent = _validate_parent_chain(
        prepared=prepared,
        contract=contract,
        schema=schema,
        profile=profile,
        packages=packages,
        manifest=manifest,
        runner=runner,
        source_projection_id=source.audit_id,
    )
    expected_coordinates = _derive_expected_coordinates(prepared=prepared, manifest=manifest)
    evidence, current_results = _execute_zero_call_runner(
        package_root=package_root,
        prepared=prepared,
        contract=contract,
        schema=schema,
        profile=profile,
        packages=packages,
        manifest=manifest,
        runner_contract=runner,
        expected_coordinates=expected_coordinates,
    )
    callsite = _callsite_totality(
        package_root=package_root,
        runner_id=runner.runner_id,
        local_invocation_count=len(evidence.rows),
    )
    destructive = _destructive_audit(
        package_root=package_root,
        source_projection=source,
        prepared=prepared,
        contract=contract,
        schema=schema,
        profile=profile,
        packages=packages,
        manifest=manifest,
        runner=runner,
        evidence_set=evidence,
        expected_coordinates=expected_coordinates,
    )
    drift = _drift_decomposition(
        package_root=package_root,
        manifest=manifest,
        current_results=current_results,
        v179_source_archive=v179_source_archive,
    )
    outcome_gap = _outcome_gap(manifest_id=manifest.manifest_id, runner_id=runner.runner_id)
    static = _static_audit(
        authorization=authorization,
        source=source,
        parent=parent,
        evidence=evidence,
        callsite=callsite,
        destructive=destructive,
        drift=drift,
        outcome_gap=outcome_gap,
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {"repair_preflight_gates_passed": static.repair_preflight_gates_passed},
            field="transition_id",
            prefix="finance_v26_193_prompt_authority_transition:",
        ),
    )
    report = cast(
        models.RepairReport,
        models.make_identity(
            models.RepairReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "source_projection_id": source.audit_id,
                "parent_authority_id": parent.audit_id,
                "prompt_evidence_set_id": evidence.evidence_set_id,
                "runner_callsite_totality_id": callsite.audit_id,
                "typed_destructive_audit_id": destructive.audit_id,
                "result_drift_audit_id": drift.audit_id,
                "outcome_authority_gap_register_id": outcome_gap.register_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "result_semantic_equivalence_claimed": drift.semantic_equivalence_claimed,
                "repair_preflight_gates_passed": static.repair_preflight_gates_passed,
            },
            field="report_id",
            prefix="finance_v26_193_prompt_authority_repair_report:",
        ),
    )
    payloads = {
        "external_v26_192_revision_audit.txt": external_audit,
        "source_projection_audit.json": _file_bytes(source),
        "parent_authority_audit.json": _file_bytes(parent),
        "exact_prompt_evidence_set.json": _file_bytes(evidence),
        "runner_callsite_totality_audit.json": _file_bytes(callsite),
        "typed_destructive_audit.json": _file_bytes(destructive),
        "result_drift_decomposition_audit.json": _file_bytes(drift),
        "outcome_authority_gap_register.json": _file_bytes(outcome_gap),
        "static_audit.json": _file_bytes(static),
        "prospective_transition.json": _file_bytes(transition),
        "report.json": _file_bytes(report),
    }
    artifact_manifest = _artifact_manifest(payloads)
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, payload in payloads.items():
        _write_bytes_no_replace(output_dir / name, payload)
    _write_bytes_no_replace(output_dir / "artifact_manifest.json", _file_bytes(artifact_manifest))
    return BuildProducts(
        authorization=authorization,
        source_projection=source,
        parent_authority=parent,
        evidence_set=evidence,
        callsite=callsite,
        destructive=destructive,
        drift=drift,
        outcome_gap=outcome_gap,
        static=static,
        transition=transition,
        report=report,
        artifact_manifest=artifact_manifest,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--v192-source-archive", type=Path, required=True)
    parser.add_argument("--v179-source-archive", type=Path, required=True)
    parser.add_argument("--current-source-archive", type=Path, required=True)
    parser.add_argument("--current-source-commit", required=True)
    parser.add_argument("--current-source-tree", required=True)
    args = parser.parse_args()
    products = build(
        package_root=args.package_root.resolve(),
        output_dir=args.output_dir.resolve(),
        external_audit_path=args.external_audit.resolve(),
        v192_source_archive=args.v192_source_archive.resolve(),
        v179_source_archive=args.v179_source_archive.resolve(),
        current_source_archive=args.current_source_archive.resolve(),
        current_source_commit=args.current_source_commit,
        current_source_tree=args.current_source_tree,
    )
    print(_canonical_json(products.report))


if __name__ == "__main__":
    main()
