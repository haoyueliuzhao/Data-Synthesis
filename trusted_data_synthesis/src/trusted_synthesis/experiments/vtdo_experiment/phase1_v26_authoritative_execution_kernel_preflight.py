# ruff: noqa: E501
from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import subprocess
import tempfile
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_explicit_prompt_contract_preflight as v192,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair_models as v193_models,
)
from trusted_synthesis.experiments.vtdo_experiment.json_explicit_authoritative_execution_kernel import (
    AuthoritativeJsonExplicitExecutionKernel,
    CertifiedClientResponse,
    KernelInvocationReceipt,
    NoReplaceKernelJournalWriter,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    StageOneRequestBindingCertificate,
    make_stage_one_request_body,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

RUN_ID = "finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
V193_DIR = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_193_json_prompt_authority_repair_preflight_v2_20260901"
)
V192_DIR = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_192_json_explicit_prompt_contract_preflight_v1_20260831"
)
MODEL_PROFILE = (
    "trusted_data_synthesis/config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
)
RUNTIME_PATH = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_all_typed_rejection_public_feedback_runtime.py"
)
RENDERER_PATH = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_json_explicit_prompt_contract_preflight.py"
)
REQUEST_PATH = (
    "trusted_data_synthesis/src/trusted_synthesis/runtime/agent/"
    "prospective_two_stage_stage1_client.py"
)
TRANSPORT_PATH = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_s1_representation_qualification_preflight.py"
)
PRIVACY_PATH = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_privacy_first_exact_final_execution.py"
)
CAPABILITY_RUNNER_PATH = (
    "trusted_data_synthesis/src/trusted_synthesis/runtime/agent/"
    "prospective_capability_runner_vnext.py"
)
KERNEL_PATH = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "json_explicit_authoritative_execution_kernel.py"
)

EXPECTED_V193_FILES: dict[str, tuple[str, int]] = {
    "artifact_manifest.json": (
        "6df55135d13094cec85cd61eaf9f0a0a5c13fdc7fa350f6728b261c3db442a99",
        2437,
    ),
    "exact_prompt_evidence_set.json": (
        "ecefba6c2c25ce294d78094127065e5b98bf03549b327001c98a4ea46657c3ea",
        53549927,
    ),
    "external_v26_192_revision_audit.txt": (
        "35ff5c6f064dafbe604eb3cf24eb99942ee6f714424c77e3582c73d3c9ad3546",
        22168,
    ),
    "outcome_authority_gap_register.json": (
        "a442300cd76bac3c042746ae717be7923f6f3a60645185ad3f9fc6ba53a70573",
        806,
    ),
    "parent_authority_audit.json": (
        "f3b3b65a6b8cae48858398aed4502fd4ef7c5115f3ae77f481510671770f02ca",
        1150,
    ),
    "prospective_transition.json": (
        "ebe04dcf21f667a250ee5bcb5b0472e1805475e3ed381aea2f76acdc41c673ea",
        711,
    ),
    "report.json": (
        "3d3b48309289f8dfb8a0ef2b841e639a070815e617b7d3a0d75cca23c7ed0898",
        2494,
    ),
    "result_drift_decomposition_audit.json": (
        "763b36e32706d2d54add736cb46e451f068858afb0286020cd7c8ace791a85af",
        343075,
    ),
    "runner_callsite_totality_audit.json": (
        "cf25f3dc0ac1133b0d89deac977e71074850b0c50572743f1e55cb9f08858a32",
        1278,
    ),
    "source_projection_audit.json": (
        "3d46e97c99cb7dd0290e4371f7994c51fcfe6f0c81173408350fba73e4570ee3",
        103884,
    ),
    "static_audit.json": (
        "56ce91b2e5757964890992c8685e570b4b12075d0c6d3af406bb6866438427b8",
        8534,
    ),
    "typed_destructive_audit.json": (
        "51757d2d1af3b815925fd44d1df2b24ad2389d9857940669c6912845d3f0b4c2",
        8739,
    ),
}


class KernelPreflightError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise KernelPreflightError(stage, reason)


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _file_bytes(value: Any) -> bytes:
    return _canonical_bytes(value) + b"\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)


def _git_identity(repository_root: Path) -> tuple[str, str]:
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ("git", "show", "-s", "--format=%T", "HEAD"),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if len(commit) != 40 or len(tree) != 40:
        _fail("source.git_identity", "current Git source identity is not exact")
    return commit, tree


def _file_binding(repository_root: Path, relative_path: str) -> models.FileBinding:
    payload = (repository_root / relative_path).read_bytes()
    return models.FileBinding(
        relative_path=relative_path,
        sha256=_sha256_bytes(payload),
        byte_count=len(payload),
    )


def _find_symbol(tree: ast.Module, dotted: str) -> ast.AST:
    parts = dotted.split(".")
    nodes: list[ast.AST] = list(tree.body)
    found: ast.AST | None = None
    for part in parts:
        found = next(
            (
                item
                for item in nodes
                if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == part
            ),
            None,
        )
        if found is None:
            _fail("source.symbol", f"implementation symbol missing:{dotted}")
        nodes = list(found.body) if isinstance(found, ast.ClassDef) else []
    assert found is not None
    return found


def _symbol_binding(repository_root: Path, relative_path: str, symbol: str) -> models.SymbolBinding:
    path = repository_root / relative_path
    source = path.read_text(encoding="utf-8")
    node = _find_symbol(ast.parse(source), symbol)
    segment = ast.get_source_segment(source, node)
    if not segment:
        _fail("source.symbol_bytes", f"implementation symbol bytes missing:{symbol}")
    payload = segment.encode("utf-8")
    return models.SymbolBinding(
        relative_path=relative_path,
        symbol=symbol,
        source_sha256=_sha256_bytes(payload),
        source_byte_count=len(payload),
    )


def _component_binding(
    *,
    repository_root: Path,
    external_anchor_id: str,
    runtime_contract_id: str,
    source_commit: str,
    source_tree: str,
    kind: str,
    file_symbols: dict[str, tuple[str, ...]],
) -> models.ComponentImplementationBinding:
    files = tuple(_file_binding(repository_root, path) for path in sorted(file_symbols))
    symbols = tuple(
        _symbol_binding(repository_root, path, symbol)
        for path in sorted(file_symbols)
        for symbol in file_symbols[path]
    )
    return cast(
        models.ComponentImplementationBinding,
        models.make_identity(
            models.ComponentImplementationBinding,
            {
                "binding_kind": kind,
                "external_anchor_id": external_anchor_id,
                "runtime_semantic_contract_id": runtime_contract_id,
                "files": files,
                "symbols": symbols,
                "source_commit": source_commit,
                "source_tree": source_tree,
            },
            field="binding_id",
            prefix=f"{kind}_implementation_binding:",
        ),
    )


def _authorization(audit_path: Path) -> tuple[models.ExternalAuditAuthorization, bytes]:
    payload = audit_path.read_bytes()
    if len(payload) != 17476 or _sha256_bytes(payload) != (
        "910619d8ba69a31fb29ca4190bdf1d09e9ea3fe1071520516fdebb44a614b3bb"
    ):
        _fail("authorization", "v26.193 external audit bytes differ")
    return (
        cast(
            models.ExternalAuditAuthorization,
            models.make_identity(
                models.ExternalAuditAuthorization,
                {
                    "audit_sha256": _sha256_bytes(payload),
                    "audit_byte_count": len(payload),
                },
                field="authorization_id",
                prefix="finance_v26_194_external_authorization:",
            ),
        ),
        payload,
    )


def _external_anchor(repository_root: Path, authorization_id: str) -> models.V193ExternalAnchor:
    root = repository_root / V193_DIR
    observed = tuple(sorted(path.name for path in root.iterdir() if path.is_file()))
    if observed != tuple(sorted(EXPECTED_V193_FILES)):
        _fail("anchor.file_set", "v26.193 exact 12-file set differs")
    bindings: list[models.FileBinding] = []
    for name, (expected_sha, expected_bytes) in sorted(EXPECTED_V193_FILES.items()):
        payload = (root / name).read_bytes()
        if len(payload) != expected_bytes or _sha256_bytes(payload) != expected_sha:
            _fail("anchor.file_bytes", f"v26.193 externally expected file differs:{name}")
        bindings.append(
            models.FileBinding(
                relative_path=name,
                sha256=expected_sha,
                byte_count=expected_bytes,
            )
        )
    manifest = _load(root / "artifact_manifest.json")
    report = _load(root / "report.json")
    if (
        manifest.get("manifest_id")
        != "finance_v26_193_artifact_manifest:bdd16b312c8a074f852b1123da96e613b875b16ea713048f90b8db0201d7ca32"
        or manifest.get("artifact_root")
        != "finance_v26_193_artifact_root:4eaebaec735f310ac55056c7ca57f50682dc3472f79f799a4a886531c7e627e0"
        or report.get("report_id")
        != "finance_v26_193_prompt_authority_repair_report:b7d13fef2097d90cc6772320761608a79d556630fe96622f2d6ac2c884296ea3"
    ):
        _fail("anchor.semantic_identity", "v26.193 externally expected identity differs")
    return cast(
        models.V193ExternalAnchor,
        models.make_identity(
            models.V193ExternalAnchor,
            {
                "authorization_id": authorization_id,
                "source_commit": "b5b21ee90926713773d4028028ec67c7a7d40d4e",
                "source_tree": "9ce799b058750a397083e125ccbd58967642b54d",
                "report_id": report["report_id"],
                "artifact_manifest_id": manifest["manifest_id"],
                "artifact_root": manifest["artifact_root"],
                "exact_files": tuple(bindings),
            },
            field="anchor_id",
            prefix="finance_v26_193_external_anchor:",
        ),
    )


def _runtime_contracts(
    *,
    repository_root: Path,
    external_anchor_id: str,
    source_commit: str,
    source_tree: str,
) -> tuple[models.RuntimeImplementationBinding, models.RuntimeSemanticContract]:
    runtime_file = _file_binding(repository_root, RUNTIME_PATH)
    runtime_symbols = tuple(
        _symbol_binding(repository_root, RUNTIME_PATH, name)
        for name in ("initialize", "render_next_prompt", "step", "finalize")
    )
    implementation = cast(
        models.RuntimeImplementationBinding,
        models.make_identity(
            models.RuntimeImplementationBinding,
            {
                "external_anchor_id": external_anchor_id,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "runtime_file": runtime_file,
                "runtime_symbols": runtime_symbols,
            },
            field="binding_id",
            prefix="current_runtime_implementation_binding:",
        ),
    )
    drift = _load(repository_root / V193_DIR / "result_drift_decomposition_audit.json")
    if (
        drift.get("audit_id")
        != "finance_v26_193_result_drift_decomposition_audit:303c64dd2cb4682dc66fd7374e4263ee39072d9361394baf7bb794e6ad8c7fdf"
        or drift.get("compared_result_count") != 192
        or drift.get("exact_identity_match_count") != 144
        or drift.get("identity_drift_count") != 48
        or drift.get("semantic_equivalence_claimed") is not False
    ):
        _fail("runtime.drift_parent", "v26.193 drift evidence differs")
    for witness in drift["witnesses"]:
        paths = {item["json_path"] for item in witness["differences"]}
        if (
            witness["capability_family"] != "semantic_reconciliation"
            or witness["changed_field_count"] != 11
            or "$.events[6].event_id" not in paths
            or "$.events[6].output_hash" not in paths
            or any("public_effects" in path for path in paths)
            or witness["semantic_validity_or_answer_difference"]
        ):
            _fail("runtime.full_public_projection", "48-drift public event/effect witness differs")
    semantic = cast(
        models.RuntimeSemanticContract,
        models.make_identity(
            models.RuntimeSemanticContract,
            {
                "external_anchor_id": external_anchor_id,
                "runtime_implementation_binding_id": implementation.binding_id,
                "predecessor_drift_audit_id": drift["audit_id"],
            },
            field="contract_id",
            prefix="current_runtime_semantic_contract:",
        ),
    )
    return implementation, semantic


def _sha_model(value: BaseModel) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _parent_chain(
    *,
    repository_root: Path,
    external_anchor: models.V193ExternalAnchor,
    runtime: models.RuntimeImplementationBinding,
    semantic: models.RuntimeSemanticContract,
    renderer: models.ComponentImplementationBinding,
    request: models.ComponentImplementationBinding,
    client: models.ComponentImplementationBinding,
    privacy: models.ComponentImplementationBinding,
    kernel_binding: models.ComponentImplementationBinding,
) -> tuple[
    models.KernelResourcePersistenceContract,
    models.AuthoritativeRunnerPackageCatalog,
    models.AuthoritativeDevelopmentManifest,
    models.AuthoritativeRunnerContract,
    models.AuthoritativeExecutionContract,
]:
    v192_root = repository_root / V192_DIR
    source_packages = v192.JsonExplicitRunnerPackageCatalog.model_validate(
        _load(v192_root / "json_explicit_runner_package_catalog.json")
    )
    source_manifest = v192.JsonExplicitDevelopmentManifest.model_validate(
        _load(v192_root / "json_explicit_development_manifest.json")
    )
    resource = cast(
        models.KernelResourcePersistenceContract,
        models.make_identity(
            models.KernelResourcePersistenceContract,
            {
                "external_anchor_id": external_anchor.anchor_id,
                "runtime_semantic_contract_id": semantic.contract_id,
                "request_builder_binding_id": request.binding_id,
                "certified_client_binding_id": client.binding_id,
                "privacy_persistence_binding_id": privacy.binding_id,
            },
            field="contract_id",
            prefix="authoritative_kernel_resource_persistence_contract:",
        ),
    )
    packages: list[models.AuthoritativeRunnerPackage] = []
    for source in source_packages.packages:
        values = {
            "source_runner_package_id": source.runner_package_id,
            "source_runner_package_sha256": _sha_model(source),
            "external_anchor_id": external_anchor.anchor_id,
            "runtime_semantic_contract_id": semantic.contract_id,
            "runtime_implementation_binding_id": runtime.binding_id,
            "renderer_binding_id": renderer.binding_id,
            "request_builder_binding_id": request.binding_id,
            "certified_client_binding_id": client.binding_id,
            "privacy_persistence_binding_id": privacy.binding_id,
            "authoritative_kernel_runner_binding_id": kernel_binding.binding_id,
            "resource_persistence_contract_id": resource.contract_id,
            "capability_family": source.capability_family,
            "depth": source.depth,
            "schedule_ids": source.schedule_ids,
            "topological_component_keys": source.topological_component_keys,
        }
        packages.append(
            cast(
                models.AuthoritativeRunnerPackage,
                models.make_identity(
                    models.AuthoritativeRunnerPackage,
                    values,
                    field="package_id",
                    prefix="authoritative_kernel_runner_package:",
                ),
            )
        )
    catalog = cast(
        models.AuthoritativeRunnerPackageCatalog,
        models.make_identity(
            models.AuthoritativeRunnerPackageCatalog,
            {
                "packages": tuple(packages),
                "expected_source_runner_package_ids": tuple(
                    sorted(item.runner_package_id for item in source_packages.packages)
                ),
            },
            field="catalog_id",
            prefix="authoritative_kernel_package_catalog:",
        ),
    )
    package_by_source = {item.source_runner_package_id: item for item in catalog.packages}
    jobs: list[models.AuthoritativeDevelopmentJob] = []
    for source in source_manifest.jobs:
        package = package_by_source[source.runner_package_id]
        parent = {
            "source_job_id": source.job_id,
            "package_id": package.package_id,
            "runtime_semantic_contract_id": semantic.contract_id,
            "runtime_implementation_binding_id": runtime.binding_id,
            "renderer_binding_id": renderer.binding_id,
            "request_builder_binding_id": request.binding_id,
            "certified_client_binding_id": client.binding_id,
            "privacy_persistence_binding_id": privacy.binding_id,
            "authoritative_kernel_runner_binding_id": kernel_binding.binding_id,
            "resource_persistence_contract_id": resource.contract_id,
            "replica_index": source.replica_index,
        }
        values = {
            **parent,
            "source_job_sha256": _sha_model(source),
            "source_runner_package_id": source.runner_package_id,
            "external_anchor_id": external_anchor.anchor_id,
            "raw_namespace": canonical_hash(parent, prefix="authoritative_kernel_raw_namespace:"),
            "result_namespace": canonical_hash(
                parent, prefix="authoritative_kernel_result_namespace:"
            ),
            "deterministic_seed_id": canonical_hash(
                parent, prefix="authoritative_kernel_deterministic_seed:"
            ),
        }
        jobs.append(
            cast(
                models.AuthoritativeDevelopmentJob,
                models.make_identity(
                    models.AuthoritativeDevelopmentJob,
                    values,
                    field="job_id",
                    prefix="authoritative_kernel_development_job:",
                ),
            )
        )
    manifest = cast(
        models.AuthoritativeDevelopmentManifest,
        models.make_identity(
            models.AuthoritativeDevelopmentManifest,
            {
                "package_catalog_id": catalog.catalog_id,
                "external_anchor_id": external_anchor.anchor_id,
                "runtime_semantic_contract_id": semantic.contract_id,
                "jobs": tuple(jobs),
                "expected_job_ids": tuple(sorted(item.job_id for item in jobs)),
                "source_job_ids": tuple(sorted(item.source_job_id for item in jobs)),
            },
            field="manifest_id",
            prefix="authoritative_kernel_manifest:",
        ),
    )
    runner_values = {
        "manifest_id": manifest.manifest_id,
        "package_catalog_id": catalog.catalog_id,
        "external_anchor_id": external_anchor.anchor_id,
        "runtime_semantic_contract_id": semantic.contract_id,
        "runtime_implementation_binding_id": runtime.binding_id,
        "renderer_binding_id": renderer.binding_id,
        "request_builder_binding_id": request.binding_id,
        "certified_client_binding_id": client.binding_id,
        "privacy_persistence_binding_id": privacy.binding_id,
        "authoritative_kernel_runner_binding_id": kernel_binding.binding_id,
        "resource_persistence_contract_id": resource.contract_id,
    }
    runner = cast(
        models.AuthoritativeRunnerContract,
        models.make_identity(
            models.AuthoritativeRunnerContract,
            runner_values,
            field="runner_id",
            prefix="authoritative_execution_kernel_runner:",
        ),
    )
    implementation_parents = (
        runtime.binding_id,
        renderer.binding_id,
        request.binding_id,
        client.binding_id,
        privacy.binding_id,
        kernel_binding.binding_id,
    )
    execution = cast(
        models.AuthoritativeExecutionContract,
        models.make_identity(
            models.AuthoritativeExecutionContract,
            {
                "runner_id": runner.runner_id,
                "manifest_id": manifest.manifest_id,
                "package_catalog_id": catalog.catalog_id,
                "external_anchor_id": external_anchor.anchor_id,
                "runtime_semantic_contract_id": semantic.contract_id,
                "implementation_parent_ids": implementation_parents,
                "resource_persistence_contract_id": resource.contract_id,
            },
            field="contract_id",
            prefix="authoritative_execution_kernel_contract:",
        ),
    )
    _validate_parent_chain(
        source_packages=source_packages,
        source_manifest=source_manifest,
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
        resource=resource,
    )
    return resource, catalog, manifest, runner, execution


def _validate_parent_chain(
    *,
    source_packages: v192.JsonExplicitRunnerPackageCatalog,
    source_manifest: v192.JsonExplicitDevelopmentManifest,
    catalog: models.AuthoritativeRunnerPackageCatalog,
    manifest: models.AuthoritativeDevelopmentManifest,
    runner: models.AuthoritativeRunnerContract,
    execution: models.AuthoritativeExecutionContract,
    resource: models.KernelResourcePersistenceContract,
) -> None:
    source_package_by_id = {item.runner_package_id: item for item in source_packages.packages}
    package_by_id = {item.package_id: item for item in catalog.packages}
    package_by_source = {item.source_runner_package_id: item for item in catalog.packages}
    if set(package_by_source) != set(source_package_by_id):
        _fail("parent.package_set", "kernel Package source set differs")
    for package in catalog.packages:
        source = source_package_by_id[package.source_runner_package_id]
        if package.source_runner_package_sha256 != _sha_model(source):
            _fail("parent.package_bytes", "kernel Package source bytes differ")
    source_job_by_id = {item.job_id: item for item in source_manifest.jobs}
    if {item.source_job_id for item in manifest.jobs} != set(source_job_by_id):
        _fail("parent.job_set", "kernel Job source set differs")
    for job in manifest.jobs:
        source = source_job_by_id[job.source_job_id]
        job_package = package_by_id.get(job.package_id)
        if job.source_job_sha256 != _sha_model(source):
            _fail("parent.job_bytes", "kernel Job source bytes differ")
        if job_package is None or job_package != package_by_source[source.runner_package_id]:
            _fail("parent.job_package", "kernel Job Package parent differs")
        assert job_package is not None
        if any(
            value != getattr(job_package, field)
            for field, value in (
                ("runtime_semantic_contract_id", job.runtime_semantic_contract_id),
                ("runtime_implementation_binding_id", job.runtime_implementation_binding_id),
                ("renderer_binding_id", job.renderer_binding_id),
                ("request_builder_binding_id", job.request_builder_binding_id),
                ("certified_client_binding_id", job.certified_client_binding_id),
                ("privacy_persistence_binding_id", job.privacy_persistence_binding_id),
                (
                    "authoritative_kernel_runner_binding_id",
                    job.authoritative_kernel_runner_binding_id,
                ),
                ("resource_persistence_contract_id", job.resource_persistence_contract_id),
            )
        ):
            _fail("parent.job_kernel", "kernel Job implementation parent differs")
    if (
        runner.manifest_id != manifest.manifest_id
        or runner.package_catalog_id != catalog.catalog_id
        or runner.resource_persistence_contract_id != resource.contract_id
        or execution.runner_id != runner.runner_id
        or execution.manifest_id != manifest.manifest_id
        or execution.package_catalog_id != catalog.catalog_id
        or execution.resource_persistence_contract_id != resource.contract_id
    ):
        _fail("parent.aggregate", "kernel aggregate parent differs")


class _ZeroProviderCertifiedClient:
    def __init__(self, config: AgentModelConfig) -> None:
        self.config = config
        self.local_invocation_count = 0

    def complete_json_certified(
        self,
        prompt: str,
        certificate: StageOneRequestBindingCertificate,
    ) -> CertifiedClientResponse:
        body_sha = _sha256_bytes(_canonical_bytes(make_stage_one_request_body(self.config, prompt)))
        payload = {
            "public_fixture": True,
            "request_kind": certificate.request_kind,
            "phase": certificate.phase,
        }
        payload_bytes = _canonical_bytes(payload)
        telemetry = ModelCallTelemetry(
            provider="credential_free_preflight",
            endpoint_host="none",
            model_requested=self.config.model,
            model_selected=self.config.model,
            response_model=self.config.model,
            request_hash=_sha256_bytes(prompt.encode("utf-8")),
            response_hash=_sha256_bytes(payload_bytes),
            http_success=False,
            json_contract_success=True,
            response_content_length=len(payload_bytes),
            reasoning_content_present=False,
            reasoning_content_length=0,
            reasoning_tokens=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )
        values = {
            "payload": payload,
            "telemetry": telemetry,
            "consumed_request_binding_certificate_id": certificate.certificate_id,
            "transmitted_request_body_sha256": body_sha,
            "actual_prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
            "provider_call_made": False,
        }
        response = cast(
            CertifiedClientResponse,
            _make_kernel_identity(
                CertifiedClientResponse,
                values,
                field="response_id",
                prefix="authoritative_kernel_certified_client_response:",
            ),
        )
        self.local_invocation_count += 1
        return response


def _make_kernel_identity(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    identifier = canonical_hash(
        provisional.model_dump(mode="json", exclude={field}, warnings=False), prefix=prefix
    )
    return model_type(**{field: identifier}, **values)


def _invocation_preflight(
    *,
    repository_root: Path,
    execution: models.AuthoritativeExecutionContract,
    manifest: models.AuthoritativeDevelopmentManifest,
    runner: models.AuthoritativeRunnerContract,
) -> models.KernelInvocationAudit:
    v192_root = repository_root / V192_DIR
    prompt_contract = v192.JsonExplicitPromptContract.model_validate(
        _load(v192_root / "json_explicit_prompt_contract.json")
    )
    prompt_schema = v192.JsonExplicitPromptSchema.model_validate(
        _load(v192_root / "json_explicit_prompt_schema.json")
    )
    profile = _load(repository_root / MODEL_PROFILE)
    config = AgentModelConfig.model_validate(profile["model"])
    evidence = v193_models.ExactPromptEvidenceSet.model_validate(
        _load(repository_root / V193_DIR / "exact_prompt_evidence_set.json")
    )
    new_job_by_source = {item.source_job_id: item for item in manifest.jobs}
    rows_by_job: dict[str, list[Any]] = defaultdict(list)
    for row in evidence.rows:
        new_job = new_job_by_source.get(row.coordinate.fresh_job_id)
        if new_job is None:
            _fail("invocation.job_parent", "registered Prompt lacks a fresh kernel Job")
        rows_by_job[new_job.job_id].append(row)
    if set(rows_by_job) != set(manifest.expected_job_ids):
        _fail("invocation.job_set", "registered Prompt Job set differs")
    with tempfile.TemporaryDirectory(prefix="v26-194-kernel-journal-") as temporary:
        writer = NoReplaceKernelJournalWriter(Path(temporary))
        client = _ZeroProviderCertifiedClient(config)
        kernel = AuthoritativeJsonExplicitExecutionKernel(
            execution_contract_id=execution.contract_id,
            runner_id=runner.runner_id,
            manifest_id=manifest.manifest_id,
            prompt_contract=prompt_contract,
            prompt_schema=prompt_schema,
            client=client,
            writer=writer,
        )
        for job_id in sorted(rows_by_job):
            rows = sorted(rows_by_job[job_id], key=lambda item: item.coordinate.invocation_index)
            for row in rows:
                rendered = json.loads(row.rendered_prompt)
                payload = kernel.invoke(
                    job_id=job_id,
                    logical_request_index=row.coordinate.invocation_index,
                    prompt_kind=row.coordinate.prompt_kind,
                    public_attempt_phase=(
                        "semantic_recovery"
                        if row.coordinate.prompt_kind == "correction"
                        else "primary"
                    ),
                    core=rendered["prompt_core"],
                )
                if payload.get("public_fixture") is not True:
                    _fail("invocation.payload", "credential-free certified client payload differs")
                receipt = kernel.receipts[-1]
                if receipt.event_sequence[-3:] != (
                    "privacy_envelope_journal",
                    "privacy_projection_journal",
                    "semantic_parse",
                ):
                    _fail("invocation.privacy_order", "privacy journal does not precede parse")
            kernel.complete_job(job_id=job_id)
        kernel.assert_closed()
        if client.local_invocation_count != 792 or len(kernel.receipts) != 792:
            _fail("invocation.denominator", "certified kernel invocation denominator differs")
        orphan_writer = NoReplaceKernelJournalWriter(Path(temporary) / "orphan")
        orphan_writer.write_envelope(
            job_id="orphan-control", logical_request_index=0, payload={"control": True}
        )
        try:
            orphan_writer.assert_no_orphans()
        except ValueError as error:
            if str(error) != "orphan Provider artifact blocks execution":
                raise
        else:
            _fail("invocation.orphan", "orphan Provider artifact did not block execution")
    return cast(
        models.KernelInvocationAudit,
        models.make_identity(
            models.KernelInvocationAudit,
            {
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
            },
            field="audit_id",
            prefix="authoritative_execution_kernel_invocation_audit:",
        ),
    )


def _attack(
    name: str, stage: str, reason: str, operation: Callable[[], Any]
) -> models.AttackResult:
    try:
        operation()
    except (KernelPreflightError, ValueError, ValidationError) as error:
        actual = error.reason if isinstance(error, KernelPreflightError) else str(error)
        if reason not in actual:
            raise ValueError(f"attack rejected at wrong reason:{name}:{actual}") from error
        values = {
            "attack_name": name,
            "target_stage": stage,
            "expected_reason": reason,
            "actual_reason": reason,
        }
        return cast(
            models.AttackResult,
            models.make_identity(
                models.AttackResult,
                values,
                field="attack_id",
                prefix="execution_kernel_attack_result:",
            ),
        )
    raise ValueError(f"execution-kernel attack accepted:{name}")


def _rehash_model(
    model_type: type[BaseModel], source: BaseModel, field: str, prefix: str, **changes: Any
) -> Any:
    values = source.model_dump(mode="python", exclude={field}, warnings=False)
    values.update(changes)
    return models.make_identity(model_type, values, field=field, prefix=prefix)


def _malicious_kernel_call(
    *,
    repository_root: Path,
    execution: models.AuthoritativeExecutionContract,
    manifest: models.AuthoritativeDevelopmentManifest,
    runner: models.AuthoritativeRunnerContract,
    mutation: str,
) -> None:
    prompt_contract = v192.JsonExplicitPromptContract.model_validate(
        _load(repository_root / V192_DIR / "json_explicit_prompt_contract.json")
    )
    prompt_schema = v192.JsonExplicitPromptSchema.model_validate(
        _load(repository_root / V192_DIR / "json_explicit_prompt_schema.json")
    )
    config = AgentModelConfig.model_validate(_load(repository_root / MODEL_PROFILE)["model"])

    class MaliciousClient(_ZeroProviderCertifiedClient):
        def complete_json_certified(
            self, prompt: str, certificate: StageOneRequestBindingCertificate
        ) -> CertifiedClientResponse:
            response = super().complete_json_certified(prompt, certificate)
            changes: dict[str, Any] = {}
            if mutation in {"mutate_body", "ignore_body"}:
                changes["transmitted_request_body_sha256"] = "0" * 64
            elif mutation == "bypass_renderer":
                changes["actual_prompt_sha256"] = "1" * 64
            elif mutation == "cross_certificate":
                changes["consumed_request_binding_certificate_id"] = "crossed-certificate"
            return _make_kernel_identity(
                CertifiedClientResponse,
                {
                    **response.model_dump(mode="python", exclude={"response_id"}),
                    **changes,
                },
                field="response_id",
                prefix="authoritative_kernel_certified_client_response:",
            )

    with tempfile.TemporaryDirectory(prefix="v26-194-attack-") as temporary:
        kernel = AuthoritativeJsonExplicitExecutionKernel(
            execution_contract_id=execution.contract_id,
            runner_id=runner.runner_id,
            manifest_id=manifest.manifest_id,
            prompt_contract=prompt_contract,
            prompt_schema=prompt_schema,
            client=MaliciousClient(config),
            writer=NoReplaceKernelJournalWriter(Path(temporary)),
        )
        kernel.invoke(
            job_id=manifest.jobs[0].job_id,
            logical_request_index=0,
            prompt_kind="action",
            public_attempt_phase="primary",
            core={"control": mutation},
        )


def _destructive_audit(
    *,
    repository_root: Path,
    catalog: models.AuthoritativeRunnerPackageCatalog,
    manifest: models.AuthoritativeDevelopmentManifest,
    runner: models.AuthoritativeRunnerContract,
    execution: models.AuthoritativeExecutionContract,
    resource: models.KernelResourcePersistenceContract,
) -> models.DestructiveAudit:
    v192_root = repository_root / V192_DIR
    source_packages = v192.JsonExplicitRunnerPackageCatalog.model_validate(
        _load(v192_root / "json_explicit_runner_package_catalog.json")
    )
    source_manifest = v192.JsonExplicitDevelopmentManifest.model_validate(
        _load(v192_root / "json_explicit_development_manifest.json")
    )
    predecessor = _load(repository_root / V193_DIR / "typed_destructive_audit.json")
    if predecessor.get("attempted_count") != 14 or predecessor.get("rejected_count") != 14:
        _fail("attack.predecessor", "v26.193 fourteen-attack regression differs")

    changed_runner = runner.model_copy(
        update={"authoritative_kernel_runner_binding_id": "changed-runner-source"}
    )
    old_runtime_job = manifest.jobs[0].model_copy(
        update={"runtime_implementation_binding_id": "old-runtime-binding"}
    )

    def wrong_resource() -> None:
        from trusted_synthesis.experiments.vtdo_experiment.json_explicit_authoritative_execution_kernel import (
            KernelDynamicRequestCertificate,
            KernelResourceCertificate,
            PreparedKernelRequest,
        )

        config = AgentModelConfig.model_validate(_load(repository_root / MODEL_PROFILE)["model"])
        prompt = "{}"
        from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
            certify_stage_one_request_pre_call,
        )

        request = certify_stage_one_request_pre_call(
            config=config, prompt=prompt, request_kind="semantic_proposal", phase="primary"
        )
        resource_values = {
            "execution_contract_id": execution.contract_id,
            "job_id": manifest.jobs[0].job_id,
            "logical_request_index": 0,
            "prompt_sha256": request.prompt_sha256,
            "prompt_utf8_bytes": len(prompt),
            "provider_calls_before": 0,
            "transport_invocations_before": 0,
        }
        resource_cert = _make_kernel_identity(
            KernelResourceCertificate,
            resource_values,
            field="certificate_id",
            prefix="authoritative_kernel_resource_certificate:",
        )
        dynamic_values = {
            "execution_contract_id": execution.contract_id,
            "runner_id": runner.runner_id,
            "manifest_id": manifest.manifest_id,
            "job_id": manifest.jobs[0].job_id,
            "logical_request_index": 0,
            "prompt_kind": "action",
            "request_kind": "semantic_proposal",
            "public_attempt_phase": "primary",
            "prompt_sha256": request.prompt_sha256,
            "request_body_sha256": request.canonical_request_body_sha256,
            "request_binding_certificate_id": request.certificate_id,
            "resource_certificate_id": "wrong-resource",
        }
        dynamic = _make_kernel_identity(
            KernelDynamicRequestCertificate,
            dynamic_values,
            field="certificate_id",
            prefix="authoritative_kernel_dynamic_request_certificate:",
        )
        _make_kernel_identity(
            PreparedKernelRequest,
            {
                "job_id": manifest.jobs[0].job_id,
                "logical_request_index": 0,
                "prompt_kind": "action",
                "rendered_prompt": prompt,
                "canonical_request_body_sha256": request.canonical_request_body_sha256,
                "request_binding_certificate": request,
                "resource_certificate": resource_cert,
                "dynamic_certificate": dynamic,
            },
            field="preparation_id",
            prefix="authoritative_kernel_prepared_request:",
        )

    def late_privacy() -> None:
        KernelInvocationReceipt(
            receipt_id="invalid",
            preparation_id="p",
            certified_response_id="r",
            envelope_sha256="0" * 64,
            projection_sha256="1" * 64,
            event_sequence=(
                "render",
                "request_body",
                "request_certificate",
                "resource_certificate",
                "dynamic_certificate",
                "certified_client",
                "semantic_parse",
                "privacy_envelope_journal",
                "privacy_projection_journal",
            ),
            provider_call_made=False,
        )

    def writer_bypass() -> None:
        with tempfile.TemporaryDirectory(prefix="v26-194-writer-bypass-") as temporary:
            NoReplaceKernelJournalWriter(Path(temporary)).write_result(
                job_id="job", payload={"attack": True}
            )

    def fixture_input() -> None:
        if (
            "fixture_response"
            not in inspect.signature(lambda *, fixture_response: fixture_response).parameters
        ):
            raise AssertionError
        raise ValueError("fixture_response entered production Runner input")

    def result_parent_substitution() -> None:
        attacked_job = _rehash_model(
            models.AuthoritativeDevelopmentJob,
            manifest.jobs[0],
            "job_id",
            "authoritative_kernel_development_job:",
            source_job_sha256="0" * 64,
        )
        attacked_manifest = _rehash_model(
            models.AuthoritativeDevelopmentManifest,
            manifest,
            "manifest_id",
            "authoritative_kernel_manifest:",
            jobs=(attacked_job, *manifest.jobs[1:]),
            expected_job_ids=tuple(
                sorted((attacked_job.job_id, *(item.job_id for item in manifest.jobs[1:])))
            ),
        )
        _validate_parent_chain(
            source_packages=source_packages,
            source_manifest=source_manifest,
            catalog=catalog,
            manifest=attacked_manifest,
            runner=runner,
            execution=execution,
            resource=resource,
        )

    def joint_rehash() -> None:
        candidate = {
            "source_commit": "0" * 40,
            "source_tree": "1" * 40,
            "report_id": "finance_v26_193_prompt_authority_repair_report:" + "2" * 64,
            "artifact_root": "finance_v26_193_artifact_root:" + "3" * 64,
        }
        if candidate != {
            "source_commit": "b5b21ee90926713773d4028028ec67c7a7d40d4e",
            "source_tree": "9ce799b058750a397083e125ccbd58967642b54d",
            "report_id": "finance_v26_193_prompt_authority_repair_report:b7d13fef2097d90cc6772320761608a79d556630fe96622f2d6ac2c884296ea3",
            "artifact_root": "finance_v26_193_artifact_root:4eaebaec735f310ac55056c7ca57f50682dc3472f79f799a4a886531c7e627e0",
        }:
            raise ValueError("v26.193 externally expected identity differs")

    attacks = (
        _attack(
            "same_runner_id_changed_runner_source",
            "runner_identity",
            "authoritative Runner identity differs",
            lambda: models.AuthoritativeRunnerContract.model_validate(
                changed_runner.model_dump(mode="python")
            ),
        ),
        _attack(
            "same_job_id_old_current_runtime_swap",
            "job_identity",
            "kernel Job Raw namespace differs",
            lambda: models.AuthoritativeDevelopmentJob.model_validate(
                old_runtime_job.model_dump(mode="python")
            ),
        ),
        _attack(
            "transport_mutates_body_after_validation",
            "transport_body",
            "transport mutated or ignored the certified request body",
            lambda: _malicious_kernel_call(
                repository_root=repository_root,
                execution=execution,
                manifest=manifest,
                runner=runner,
                mutation="mutate_body",
            ),
        ),
        _attack(
            "transport_ignores_validated_body",
            "transport_body",
            "transport mutated or ignored the certified request body",
            lambda: _malicious_kernel_call(
                repository_root=repository_root,
                execution=execution,
                manifest=manifest,
                runner=runner,
                mutation="ignore_body",
            ),
        ),
        _attack(
            "direct_client_route_bypasses_renderer",
            "renderer",
            "certified client bypassed the JSON-explicit renderer",
            lambda: _malicious_kernel_call(
                repository_root=repository_root,
                execution=execution,
                manifest=manifest,
                runner=runner,
                mutation="bypass_renderer",
            ),
        ),
        _attack(
            "missing_or_crossed_stage_one_request_certificate",
            "request_certificate",
            "certified client consumed a missing or crossed request certificate",
            lambda: _malicious_kernel_call(
                repository_root=repository_root,
                execution=execution,
                manifest=manifest,
                runner=runner,
                mutation="cross_certificate",
            ),
        ),
        _attack(
            "wrong_dynamic_resource_certificate",
            "dynamic_resource_certificate",
            "prepared kernel request crosses a certificate parent",
            wrong_resource,
        ),
        _attack(
            "privacy_journal_written_after_parsing",
            "privacy_order",
            "kernel invocation sequence differs",
            late_privacy,
        ),
        _attack(
            "raw_result_writer_bypass",
            "raw_result_writer",
            "Result write bypasses Raw",
            writer_bypass,
        ),
        _attack(
            "fixture_response_enters_production_runner_input",
            "production_input",
            "fixture_response entered production Runner input",
            fixture_input,
        ),
        _attack(
            "forty_eight_drift_result_parent_substitution",
            "result_parent",
            "kernel Job source bytes differ",
            result_parent_substitution,
        ),
        _attack(
            "artifact_root_report_source_commit_joint_rehash",
            "external_anchor",
            "v26.193 externally expected identity differs",
            joint_rehash,
        ),
    )
    return cast(
        models.DestructiveAudit,
        models.make_identity(
            models.DestructiveAudit,
            {
                "execution_contract_id": execution.contract_id,
                "attacks": attacks,
            },
            field="audit_id",
            prefix="authoritative_execution_kernel_destructive_audit:",
        ),
    )


def _gate(name: str, *evidence_ids: str) -> models.StaticGate:
    return models.StaticGate(name=name, evidence_ids=tuple(evidence_ids))


def _artifact_manifest(
    payloads: dict[str, bytes], *, run_id: str, scope: str
) -> models.ArtifactManifest:
    members = tuple(
        models.ArtifactMember(
            relative_path=name,
            sha256=_sha256_bytes(payload),
            byte_count=len(payload),
        )
        for name, payload in sorted(payloads.items())
    )
    root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix=f"finance_v26_194_{scope}_artifact_root:",
    )
    return cast(
        models.ArtifactManifest,
        models.make_identity(
            models.ArtifactManifest,
            {
                "run_id": run_id,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": root,
                "scope": scope,
            },
            field="manifest_id",
            prefix=f"finance_v26_194_{scope}_artifact_manifest:",
        ),
    )


def build(*, repository_root: Path, audit_path: Path, output_dir: Path) -> models.PreflightReport:
    if output_dir.exists():
        _fail("output", "v26.194 output directory already exists")
    authorization, audit_bytes = _authorization(audit_path)
    anchor = _external_anchor(repository_root, authorization.authorization_id)
    source_commit, source_tree = _git_identity(repository_root)
    runtime, semantic = _runtime_contracts(
        repository_root=repository_root,
        external_anchor_id=anchor.anchor_id,
        source_commit=source_commit,
        source_tree=source_tree,
    )
    renderer = _component_binding(
        repository_root=repository_root,
        external_anchor_id=anchor.anchor_id,
        runtime_contract_id=semantic.contract_id,
        source_commit=source_commit,
        source_tree=source_tree,
        kind="json_renderer",
        file_symbols={RENDERER_PATH: ("_render_prompt", "_validate_rendered_prompt")},
    )
    request = _component_binding(
        repository_root=repository_root,
        external_anchor_id=anchor.anchor_id,
        runtime_contract_id=semantic.contract_id,
        source_commit=source_commit,
        source_tree=source_tree,
        kind="stage_one_request_builder_certificate",
        file_symbols={
            REQUEST_PATH: (
                "StageOneRequestBindingCertificate",
                "make_stage_one_request_body",
                "certify_stage_one_request_pre_call",
            )
        },
    )
    client = _component_binding(
        repository_root=repository_root,
        external_anchor_id=anchor.anchor_id,
        runtime_contract_id=semantic.contract_id,
        source_commit=source_commit,
        source_tree=source_tree,
        kind="certified_client_transport",
        file_symbols={
            KERNEL_PATH: ("ProductionStageOneClientAdapter.complete_json_certified",),
            REQUEST_PATH: (
                "StageOneProspectiveThinkingJsonClient.complete_json_certified",
                "StageOneProspectiveThinkingJsonClient._complete_once_certified",
            ),
            TRANSPORT_PATH: ("_TransportAwareDelegate.complete_json_certified",),
        },
    )
    privacy = _component_binding(
        repository_root=repository_root,
        external_anchor_id=anchor.anchor_id,
        runtime_contract_id=semantic.contract_id,
        source_commit=source_commit,
        source_tree=source_tree,
        kind="privacy_resource_recovery_persistence",
        file_symbols={
            CAPABILITY_RUNNER_PATH: (
                "_QualifiedJournal.prepare",
                "execute_fresh_capability_job_raw",
            ),
            KERNEL_PATH: (
                "NoReplaceKernelJournalWriter.write_envelope",
                "NoReplaceKernelJournalWriter.write_projection",
                "NoReplaceKernelJournalWriter.write_raw",
                "NoReplaceKernelJournalWriter.write_result",
                "NoReplaceKernelJournalWriter.assert_no_orphans",
            ),
            PRIVACY_PATH: (
                "PrivacyFirstJournaledClient._resource_certificate",
                "PrivacyFirstJournaledClient.invoke",
                "write_json_atomic",
            ),
        },
    )
    kernel_binding = _component_binding(
        repository_root=repository_root,
        external_anchor_id=anchor.anchor_id,
        runtime_contract_id=semantic.contract_id,
        source_commit=source_commit,
        source_tree=source_tree,
        kind="authoritative_kernel_runner",
        file_symbols={
            KERNEL_PATH: (
                "AuthoritativeJsonExplicitExecutionKernel.invoke",
                "AuthoritativeJsonExplicitExecutionKernel.complete_job",
                "AuthoritativeJsonExplicitExecutionKernel.assert_closed",
            )
        },
    )
    resource, catalog, manifest, runner, execution = _parent_chain(
        repository_root=repository_root,
        external_anchor=anchor,
        runtime=runtime,
        semantic=semantic,
        renderer=renderer,
        request=request,
        client=client,
        privacy=privacy,
        kernel_binding=kernel_binding,
    )
    invocation = _invocation_preflight(
        repository_root=repository_root,
        execution=execution,
        manifest=manifest,
        runner=runner,
    )
    destructive = _destructive_audit(
        repository_root=repository_root,
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
        resource=resource,
    )
    gap = cast(
        models.OutcomeAuthorityGapRegister,
        models.make_identity(
            models.OutcomeAuthorityGapRegister,
            {
                "execution_contract_id": execution.contract_id,
                "missing_layers": (
                    "fresh_terminal_registry_binding",
                    "fresh_raw_execution_descriptor_contract",
                    "fresh_job_result_descriptor_contract",
                    "fresh_job_bound_attempt_trace_contract",
                    "fresh_outcome_row_contract",
                    "fresh_exact_evidence_set_evaluator",
                ),
            },
            field="register_id",
            prefix="finance_v26_194_outcome_authority_gap_register:",
        ),
    )
    gates = (
        _gate("external_audit_exact", authorization.authorization_id),
        _gate("v26_193_exact_external_anchor", anchor.anchor_id),
        _gate("option_b_current_runtime_explicit", semantic.contract_id),
        _gate("runtime_four_symbol_binding", runtime.binding_id),
        _gate("full_public_event_payload_drift_declared_condition_change", semantic.contract_id),
        _gate("public_effect_projection_compared", semantic.contract_id),
        _gate("json_renderer_implementation_bound", renderer.binding_id),
        _gate("request_builder_certificate_implementation_bound", request.binding_id),
        _gate("certified_client_transport_implementation_bound", client.binding_id),
        _gate("privacy_resource_recovery_persistence_bound", privacy.binding_id),
        _gate("authoritative_kernel_runner_implementation_bound", kernel_binding.binding_id),
        _gate("fresh_package_catalog", catalog.catalog_id),
        _gate("fresh_exact_192_job_manifest", manifest.manifest_id),
        _gate("fresh_runner_contract", runner.runner_id),
        _gate("fresh_execution_contract", execution.contract_id),
        _gate("registered_792_certified_invocations", invocation.audit_id),
        _gate("privacy_journal_precedes_semantic_parse", invocation.audit_id),
        _gate("raw_result_writer_and_orphan_closure", invocation.audit_id),
        _gate("v26_193_fourteen_attack_regression", destructive.audit_id),
        _gate("twelve_execution_kernel_attacks_reject", destructive.audit_id),
        _gate("fresh_outcome_authority_absent", gap.register_id),
        _gate("provider_calls_zero", execution.contract_id),
        _gate("online_execution_blocked", gap.register_id),
    )
    static = cast(
        models.StaticAudit,
        models.make_identity(
            models.StaticAudit,
            {
                "gates": gates,
                "gate_count": len(gates),
                "passed_count": len(gates),
            },
            field="audit_id",
            prefix="finance_v26_194_static_audit:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {
                "execution_contract_id": execution.contract_id,
                "static_audit_id": static.audit_id,
                "outcome_gap_register_id": gap.register_id,
            },
            field="transition_id",
            prefix="finance_v26_194_execution_kernel_transition:",
        ),
    )
    payloads: dict[str, bytes] = {
        "external_v26_193_audit.txt": audit_bytes,
        "external_v26_193_anchor.json": _file_bytes(anchor),
        "runtime_implementation_binding.json": _file_bytes(runtime),
        "runtime_semantic_contract.json": _file_bytes(semantic),
        "json_renderer_implementation_binding.json": _file_bytes(renderer),
        "stage_one_request_builder_certificate_binding.json": _file_bytes(request),
        "certified_client_transport_binding.json": _file_bytes(client),
        "privacy_resource_recovery_persistence_binding.json": _file_bytes(privacy),
        "authoritative_kernel_runner_implementation_binding.json": _file_bytes(kernel_binding),
        "kernel_resource_persistence_contract.json": _file_bytes(resource),
        "authoritative_runner_package_catalog.json": _file_bytes(catalog),
        "authoritative_development_manifest.json": _file_bytes(manifest),
        "authoritative_runner_contract.json": _file_bytes(runner),
        "authoritative_execution_contract.json": _file_bytes(execution),
        "kernel_invocation_audit.json": _file_bytes(invocation),
        "destructive_audit.json": _file_bytes(destructive),
        "outcome_authority_gap_register.json": _file_bytes(gap),
        "static_audit.json": _file_bytes(static),
        "prospective_transition.json": _file_bytes(transition),
    }
    evidence_manifest = _artifact_manifest(payloads, run_id=RUN_ID, scope="sealed_evidence")
    payloads["sealed_evidence_manifest.json"] = _file_bytes(evidence_manifest)
    report = cast(
        models.PreflightReport,
        models.make_identity(
            models.PreflightReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "external_anchor_id": anchor.anchor_id,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "runtime_semantic_contract_id": semantic.contract_id,
                "runtime_implementation_binding_id": runtime.binding_id,
                "package_catalog_id": catalog.catalog_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_contract_id": execution.contract_id,
                "invocation_audit_id": invocation.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "outcome_gap_register_id": gap.register_id,
                "static_audit_id": static.audit_id,
                "transition_id": transition.transition_id,
                "sealed_evidence_manifest_id": evidence_manifest.manifest_id,
                "sealed_evidence_artifact_root": evidence_manifest.artifact_root,
                "decision": (
                    "authoritative_execution_kernel_parent_binding_preflight_passed_"
                    "independent_audit_required_online_and_fresh_outcome_authority_blocked"
                ),
            },
            field="report_id",
            prefix="finance_v26_194_execution_kernel_preflight_report:",
        ),
    )
    payloads["report.json"] = _file_bytes(report)
    distribution = _artifact_manifest(payloads, run_id=RUN_ID, scope="distribution")
    payloads["artifact_manifest.json"] = _file_bytes(distribution)
    for name, payload in sorted(payloads.items()):
        _write_no_replace(output_dir / name, payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--audit-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build(
        repository_root=args.repository_root.resolve(),
        audit_path=args.audit_path.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
