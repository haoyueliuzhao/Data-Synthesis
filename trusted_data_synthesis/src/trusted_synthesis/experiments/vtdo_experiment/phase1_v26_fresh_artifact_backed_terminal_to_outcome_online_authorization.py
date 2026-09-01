from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from pydantic import BaseModel

from trusted_synthesis.core.task import (
    fresh_artifact_backed_terminal_to_outcome_integration as integration,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as v194_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_independent_audit_models as v198_models,  # noqa: E501
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_integration_repair_models as v197_models,  # noqa: E501
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_artifact_backed_terminal_to_outcome_online_authorization_models as models,  # noqa: E501
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = (
    "finance_v26_199_fresh_artifact_backed_terminal_to_outcome_online_authorization_v1_20260901"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
V198_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_198_fresh_artifact_backed_terminal_to_outcome_integration_repair_"
    "independent_audit_v3_20260901"
)
V197_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_197_fresh_artifact_backed_terminal_to_outcome_integration_repair_"
    "preflight_v1_20260901"
)
V194_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
)
V192_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_192_json_explicit_prompt_contract_preflight_v1_20260831"
)
EXPECTED_EXTERNAL_AUDIT_SHA256: Final = (
    "ba183459a9e487b755d42ce6ee0403ac0c2b5dcb9801161987889b85361ddaac"
)
EXPECTED_EXTERNAL_AUDIT_BYTES: Final = 11_446
V198_REPORT_ID: Final = (
    "finance_v26_198_terminal_outcome_repair_independent_audit_report:"
    "e52160edb2883910ff2b91f81a3480e0af5e52867e76f4757a97fab6e4504131"
)
V198_DECISION_ID: Final = (
    "finance_v26_198_independent_audit_decision:"
    "e6af14a10062efb00ae6c3105458b0cd153d653e5469d9a1a46a8cf08a7ee5a6"
)
V198_TRANSITION_ID: Final = (
    "finance_v26_198_transition:afbd151b363ff8b77cd7bd510bb8fdc14188d63d12b78952578ffc8f20430b5e"
)
V198_SOURCE_COMMIT: Final = "16ea0c26fc8376f38101ed4784243e3ab2c5c059"
V198_SOURCE_TREE: Final = "db6e6697fd2832716ba0be6e1292cbb4527f5110"
V198_SEALED_ROOT: Final = (
    "finance_v26_198_sealed_evidence_artifact_root:"
    "eaca708da42a5e6ab4c477d6b8af65ae680dc52942c96e55ebb9e84acf55398b"
)
V198_DISTRIBUTION_ROOT: Final = (
    "finance_v26_198_distribution_artifact_root:"
    "8327c96e0c2ab0b79aa7d0a519a1e271c185827b8a8e86fe0a6c0eb716210faf"
)
V197_REPORT_ID: Final = (
    "finance_v26_197_terminal_outcome_repair_preflight_report:"
    "57692819ab14fc6f7f6a9fa90f7f6c9ddb887da77ce997286d0392aed5d07954"
)
V197_INTEGRATION_CONTRACT_ID: Final = (
    "fresh_terminal_to_outcome_integration_contract:"
    "d8de732958e439dabedd63baec87e3f504f29dfd8bd2050881652da4aef29c58"
)
V197_IMPLEMENTATION_BINDING_ID: Final = (
    "fresh_terminal_to_outcome_implementation_binding:"
    "b5f2ca3cff51b6563b58c7840f244f4bb21cf9b07f0ceb4fe9b526046fa1ce57"
)
V197_SOURCE_COMMIT: Final = "2551fc331f5e1327a5b78054423223d158f08d6a"
V197_SOURCE_TREE: Final = "a5b1699e8e1de3622f2ddb567d6df2148a47f47e"
V194_REPORT_ID: Final = (
    "finance_v26_194_execution_kernel_preflight_report:"
    "f95f59b95819f081153774abba04a26f255d41b6ce7ce819db031625faec9747"
)
PACKAGE_CATALOG_ID: Final = (
    "authoritative_kernel_package_catalog:"
    "cd7bee78c7ed7bc618d7b4d6441546264d1a6392336dceedee9abb89ea7e7211"
)
MANIFEST_ID: Final = (
    "authoritative_kernel_manifest:15da508affe0a4727f85fbc727ac1a4b6772b014fdb6a40d4e5c93ae374cd803"
)
RUNNER_ID: Final = (
    "authoritative_execution_kernel_runner:"
    "7a3b8ae6bfb178c351f10a00c08c18373ee61f0bf64b500f245644cc99e1e034"
)
EXECUTION_CONTRACT_ID: Final = (
    "authoritative_execution_kernel_contract:"
    "53dccfcd1a4516ae8c79c9b64cd41193b99e8594598a25049335db565070786d"
)
RUNTIME_CONTRACT_ID: Final = (
    "current_runtime_semantic_contract:"
    "68cbbcf9d0e562b046bd67832aeab533d474f458f4b8d342ee3fe3d4549960a6"
)
KERNEL_RESOURCE_CONTRACT_ID: Final = (
    "authoritative_kernel_resource_persistence_contract:"
    "ba6fb7967c3429d05184cc7a3ddc619187bf28ea438cc1b46bd66ce6a21055b4"
)
GENERATION_PROFILE_ID: Final = (
    "json_explicit_generation_profile:"
    "058158afa8c23bb977cbc3b2b7c51326b271b5e32c19d1f4e39c7048ca7fa068"
)
PROMPT_CONTRACT_ID: Final = (
    "json_explicit_prompt_contract:d0094129a9f434aaa5f023d049fb9f10f300e04cc7140bf484012b41d4413afe"
)
PROMPT_SCHEMA_ID: Final = (
    "json_explicit_prompt_schema:17d41e7a1f7358bdb254fc34ce49e9638c4bdcab737af5d633474c82f0234c1b"
)
MODEL_CONFIG_ID: Final = (
    "agent_model_config:05eb110b4269f3a569d24918f356cb905d871aace45b9024c4575295b05a1015"
)
THINKING_POLICY_ID: Final = (
    "prospective_thinking_model_binding:"
    "5afdd81c4318c89d5c31f9398e77b28822eb338578c2bc3533ed77d6291d33c8"
)
ACTION_GRAMMAR_ID: Final = (
    "prospective_semantic_action_response_grammar:"
    "bbda30254855071bc024f6217cea4eec57512eaa50c8e5e0f7755c6e92d07e82"
)
FINAL_GRAMMAR_ID: Final = (
    "prospective_qualified_final_response_grammar:"
    "2370b603f1243c500e19ef0b45e6bdfa32434a7b4242b0c884ee977dd169d3fc"
)
BOUNDED_POLICY_ID: Final = (
    "bounded_policy_endpoint_generation_policy:"
    "481664d9ed21cb7f610754ff290021b7fb6ce5451ff57600b572224bff60bbe2"
)
GENERATION_RESOURCE_ID: Final = (
    "finance_v26_fresh_reachability_resource_contract:"
    "64507d067b2842c93da2d622b18d7b27973bf23396968994dda6e50fe06ef0e5"
)


class OnlineAuthorizationError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}:{reason}")


def _fail(stage: str, reason: str) -> NoReturn:
    raise OnlineAuthorizationError(stage, reason)


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", warnings=False)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _canonical_bytes(value: Any, *, newline: bool = True) -> bytes:
    payload = json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return payload + (b"\n" if newline else b"")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _set_sha256(values: tuple[str, ...]) -> str:
    return _sha256_bytes(_canonical_bytes(tuple(sorted(values)), newline=False))


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _git(repository_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repository_root), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_identity(repository_root: Path) -> tuple[str, str]:
    commit = _git(repository_root, "rev-parse", "HEAD")
    tree = _git(repository_root, "show", "-s", "--format=%T", "HEAD")
    if len(commit) != 40 or len(tree) != 40:
        _fail("git", "source Git identity is not exact")
    return commit, tree


def _git_blob(repository_root: Path, commit: str, relative_path: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(repository_root), "show", f"{commit}:{relative_path}"),
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _file_binding(root: Path, relative_path: str) -> models.FileBinding:
    path = root / relative_path
    payload = path.read_bytes()
    return models.FileBinding(
        relative_path=relative_path,
        sha256=_sha256_bytes(payload),
        byte_count=len(payload),
    )


def _recursive_bindings(root: Path) -> tuple[models.FileBinding, ...]:
    return tuple(
        models.FileBinding(
            relative_path=path.relative_to(root).as_posix(),
            sha256=_sha256_bytes(path.read_bytes()),
            byte_count=path.stat().st_size,
        )
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )


def _external_decision(
    audit_path: Path,
) -> tuple[models.ExternalOnlineAuthorizationDecision, bytes]:
    if not audit_path.is_file():
        _fail("authorization", "external v26.198 online decision is missing")
    payload = audit_path.read_bytes()
    if (
        len(payload) != EXPECTED_EXTERNAL_AUDIT_BYTES
        or _sha256_bytes(payload) != EXPECTED_EXTERNAL_AUDIT_SHA256
    ):
        _fail("authorization", "external v26.198 online decision bytes differ")
    decision = cast(
        models.ExternalOnlineAuthorizationDecision,
        models.make_identity(
            models.ExternalOnlineAuthorizationDecision,
            {
                "audit_sha256": EXPECTED_EXTERNAL_AUDIT_SHA256,
                "audit_byte_count": EXPECTED_EXTERNAL_AUDIT_BYTES,
                "audit_decision": "v26_198_accepted_online_authorization_only",
                "v198_report_id": V198_REPORT_ID,
                "v198_decision_id": V198_DECISION_ID,
                "v198_transition_id": V198_TRANSITION_ID,
            },
            field="decision_id",
            prefix="finance_v26_199_external_online_authorization_decision:",
        ),
    )
    return decision, payload


def _verify_manifest_members(
    root: Path,
    manifest: v198_models.ArtifactManifest,
) -> None:
    for item in manifest.members:
        path = root / item.relative_path
        if not path.is_file():
            _fail("v198.freeze", f"missing v26.198 member {item.relative_path}")
        payload = path.read_bytes()
        if len(payload) != item.byte_count or _sha256_bytes(payload) != item.sha256:
            _fail("v198.freeze", f"changed v26.198 member {item.relative_path}")


def _v198_freeze(
    *,
    repository_root: Path,
    external_decision: models.ExternalOnlineAuthorizationDecision,
) -> models.V198AuthorityFreeze:
    root = repository_root / V198_DIR
    bindings = _recursive_bindings(root)
    if len(bindings) != 48 or sum(item.byte_count for item in bindings) != 275_894:
        _fail("v198.freeze", "v26.198 formal directory geometry differs")
    report = v198_models.IndependentAuditReport.model_validate(_load(root / "report.json"))
    decision = v198_models.IndependentAuditDecision.model_validate(
        _load(root / "independent_audit_decision.json")
    )
    transition = v198_models.ProspectiveTransition.model_validate(
        _load(root / "prospective_transition.json")
    )
    static = v198_models.StaticAudit.model_validate(_load(root / "static_audit.json"))
    sealed = v198_models.ArtifactManifest.model_validate(
        _load(root / "sealed_evidence_manifest.json")
    )
    distribution = v198_models.ArtifactManifest.model_validate(
        _load(root / "artifact_manifest.json")
    )
    _verify_manifest_members(root, sealed)
    _verify_manifest_members(root, distribution)
    if (
        report.report_id != V198_REPORT_ID
        or decision.decision_id != V198_DECISION_ID
        or transition.transition_id != V198_TRANSITION_ID
        or report.source_commit != V198_SOURCE_COMMIT
        or report.source_tree != V198_SOURCE_TREE
        or report.sealed_artifact_root != V198_SEALED_ROOT
        or sealed.artifact_root != V198_SEALED_ROOT
        or distribution.artifact_root != V198_DISTRIBUTION_ROOT
        or static.passed_count != static.gate_count
        or static.failed_count
        or transition.next_stage != models.CONSUMED_STAGE
        or transition.online_execution_authorized
        or transition.provider_calls_authorized
        or transition.job_192_execution_authorized
    ):
        _fail("v198.freeze", "v26.198 authority parent differs")
    return cast(
        models.V198AuthorityFreeze,
        models.make_identity(
            models.V198AuthorityFreeze,
            {
                "external_decision_id": external_decision.decision_id,
                "v198_report_id": report.report_id,
                "v198_decision_id": decision.decision_id,
                "v198_transition_id": transition.transition_id,
                "v198_source_commit": report.source_commit,
                "v198_source_tree": report.source_tree,
                "v198_sealed_artifact_root": sealed.artifact_root,
                "v198_distribution_artifact_root": distribution.artifact_root,
            },
            field="audit_id",
            prefix="finance_v26_199_v198_authority_freeze_audit:",
        ),
    )


def _frozen_condition(
    *,
    repository_root: Path,
    external_decision: models.ExternalOnlineAuthorizationDecision,
    freeze: models.V198AuthorityFreeze,
) -> models.FrozenExecutionConditionBinding:
    root194 = repository_root / V194_DIR
    root192 = repository_root / V192_DIR
    report = v194_models.PreflightReport.model_validate(_load(root194 / "report.json"))
    catalog = v194_models.AuthoritativeRunnerPackageCatalog.model_validate(
        _load(root194 / "authoritative_runner_package_catalog.json")
    )
    manifest = v194_models.AuthoritativeDevelopmentManifest.model_validate(
        _load(root194 / "authoritative_development_manifest.json")
    )
    runner = v194_models.AuthoritativeRunnerContract.model_validate(
        _load(root194 / "authoritative_runner_contract.json")
    )
    execution = v194_models.AuthoritativeExecutionContract.model_validate(
        _load(root194 / "authoritative_execution_contract.json")
    )
    runtime = v194_models.RuntimeSemanticContract.model_validate(
        _load(root194 / "runtime_semantic_contract.json")
    )
    resource = v194_models.KernelResourcePersistenceContract.model_validate(
        _load(root194 / "kernel_resource_persistence_contract.json")
    )
    profile = _load(root192 / "json_explicit_generation_profile.json")
    prompt = _load(root192 / "json_explicit_prompt_contract.json")
    expected_profile = {
        "profile_id": GENERATION_PROFILE_ID,
        "prompt_contract_id": PROMPT_CONTRACT_ID,
        "prompt_schema_id": PROMPT_SCHEMA_ID,
        "model_config_id": MODEL_CONFIG_ID,
        "thinking_policy_id": THINKING_POLICY_ID,
        "action_grammar_id": ACTION_GRAMMAR_ID,
        "final_grammar_id": FINAL_GRAMMAR_ID,
        "bounded_generation_policy_id": BOUNDED_POLICY_ID,
        "resource_contract_id": GENERATION_RESOURCE_ID,
    }
    if any(profile.get(key) != value for key, value in expected_profile.items()):
        _fail("condition.profile", "frozen generation profile differs")
    if prompt.get("contract_id") != PROMPT_CONTRACT_ID:
        _fail("condition.prompt", "frozen Prompt Contract differs")
    if (
        report.report_id != V194_REPORT_ID
        or catalog.catalog_id != PACKAGE_CATALOG_ID
        or manifest.manifest_id != MANIFEST_ID
        or runner.runner_id != RUNNER_ID
        or execution.contract_id != EXECUTION_CONTRACT_ID
        or runtime.contract_id != RUNTIME_CONTRACT_ID
        or resource.contract_id != KERNEL_RESOURCE_CONTRACT_ID
        or report.exact_package_count != 32
        or report.exact_job_count != 192
        or report.exact_registered_invocation_count != 792
        or manifest.package_catalog_id != catalog.catalog_id
        or runner.manifest_id != manifest.manifest_id
        or runner.package_catalog_id != catalog.catalog_id
        or execution.runner_id != runner.runner_id
        or execution.manifest_id != manifest.manifest_id
        or execution.package_catalog_id != catalog.catalog_id
        or execution.resource_persistence_contract_id != resource.contract_id
    ):
        _fail("condition.parents", "frozen 192-Job parent chain differs")
    package_ids = {item.package_id for item in catalog.packages}
    if any(
        item.package_id not in package_ids
        or item.runtime_semantic_contract_id != RUNTIME_CONTRACT_ID
        or item.resource_persistence_contract_id != KERNEL_RESOURCE_CONTRACT_ID
        for item in manifest.jobs
    ):
        _fail("condition.jobs", "frozen Job parent binding differs")
    job_ids = tuple(sorted(item.job_id for item in manifest.jobs))
    raw_namespaces = tuple(sorted(item.raw_namespace for item in manifest.jobs))
    result_namespaces = tuple(sorted(item.result_namespace for item in manifest.jobs))
    relative_paths = (
        f"{V194_DIR}/report.json",
        f"{V194_DIR}/authoritative_runner_package_catalog.json",
        f"{V194_DIR}/authoritative_development_manifest.json",
        f"{V194_DIR}/authoritative_runner_contract.json",
        f"{V194_DIR}/authoritative_execution_contract.json",
        f"{V194_DIR}/runtime_semantic_contract.json",
        f"{V194_DIR}/kernel_resource_persistence_contract.json",
        f"{V192_DIR}/json_explicit_generation_profile.json",
        f"{V192_DIR}/json_explicit_prompt_contract.json",
    )
    files = tuple(_file_binding(repository_root, path) for path in relative_paths)
    return cast(
        models.FrozenExecutionConditionBinding,
        models.make_identity(
            models.FrozenExecutionConditionBinding,
            {
                "external_decision_id": external_decision.decision_id,
                "v198_freeze_audit_id": freeze.audit_id,
                "v194_report_id": report.report_id,
                "package_catalog_id": catalog.catalog_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_contract_id": execution.contract_id,
                "runtime_semantic_contract_id": runtime.contract_id,
                "kernel_resource_persistence_contract_id": resource.contract_id,
                "generation_profile_id": profile["profile_id"],
                "prompt_contract_id": profile["prompt_contract_id"],
                "prompt_schema_id": profile["prompt_schema_id"],
                "model_config_id": profile["model_config_id"],
                "thinking_policy_id": profile["thinking_policy_id"],
                "action_grammar_id": profile["action_grammar_id"],
                "final_grammar_id": profile["final_grammar_id"],
                "bounded_generation_policy_id": profile["bounded_generation_policy_id"],
                "generation_resource_contract_id": profile["resource_contract_id"],
                "exact_job_ids": job_ids,
                "exact_job_set_sha256": _set_sha256(job_ids),
                "raw_namespace_set_sha256": _set_sha256(raw_namespaces),
                "result_namespace_set_sha256": _set_sha256(result_namespaces),
                "parent_files": files,
            },
            field="binding_id",
            prefix="finance_v26_199_frozen_execution_condition_binding:",
        ),
    )


def _successor_binding(
    *,
    repository_root: Path,
    freeze: models.V198AuthorityFreeze,
    condition: models.FrozenExecutionConditionBinding,
) -> models.SuccessorIntegrationAuthorityBinding:
    root = repository_root / V197_DIR
    report = v197_models.RepairPreflightReport.model_validate(_load(root / "report.json"))
    contract = integration.TerminalOutcomeIntegrationContract.model_validate(
        _load(root / "terminal_to_outcome_integration_contract.json")
    )
    implementation = v197_models.IntegrationImplementationBinding.model_validate(
        _load(root / "integration_implementation_binding.json")
    )
    if (
        report.report_id != V197_REPORT_ID
        or contract.contract_id != V197_INTEGRATION_CONTRACT_ID
        or implementation.binding_id != V197_IMPLEMENTATION_BINDING_ID
        or implementation.source_commit != V197_SOURCE_COMMIT
        or implementation.source_tree != V197_SOURCE_TREE
        or contract.manifest_id != condition.manifest_id
        or contract.package_catalog_id != condition.package_catalog_id
        or contract.predecessor_runner_id != condition.runner_id
        or contract.predecessor_execution_contract_id != condition.execution_contract_id
    ):
        _fail("successor.parents", "successor integration parent differs")
    successor_files: list[models.FileBinding] = []
    for item in implementation.files:
        payload = _git_blob(repository_root, V197_SOURCE_COMMIT, item.relative_path)
        if len(payload) != item.byte_count or _sha256_bytes(payload) != item.sha256:
            _fail("successor.source", f"changed successor source {item.relative_path}")
        successor_files.append(
            models.FileBinding(
                relative_path=item.relative_path,
                sha256=item.sha256,
                byte_count=item.byte_count,
            )
        )
    return cast(
        models.SuccessorIntegrationAuthorityBinding,
        models.make_identity(
            models.SuccessorIntegrationAuthorityBinding,
            {
                "v198_freeze_audit_id": freeze.audit_id,
                "frozen_condition_binding_id": condition.binding_id,
                "v197_report_id": report.report_id,
                "v198_report_id": freeze.v198_report_id,
                "integration_contract_id": contract.contract_id,
                "integration_implementation_binding_id": implementation.binding_id,
                "terminal_registry_id": contract.terminal_registry_id,
                "raw_descriptor_contract_id": contract.raw_descriptor_contract_id,
                "result_descriptor_contract_id": contract.result_descriptor_contract_id,
                "attempt_trace_contract_id": contract.attempt_trace_contract_id,
                "outcome_row_contract_id": contract.outcome_row_contract_id,
                "evaluator_contract_id": contract.evaluator_contract_id,
                "successor_source_commit": implementation.source_commit,
                "successor_source_tree": implementation.source_tree,
                "successor_files": tuple(successor_files),
            },
            field="binding_id",
            prefix="finance_v26_199_successor_integration_authority_binding:",
        ),
    )


def _online_authorization(
    *,
    external_decision: models.ExternalOnlineAuthorizationDecision,
    freeze: models.V198AuthorityFreeze,
    condition: models.FrozenExecutionConditionBinding,
    successor: models.SuccessorIntegrationAuthorityBinding,
) -> models.ExactOnlineExecutionAuthorization:
    return cast(
        models.ExactOnlineExecutionAuthorization,
        models.make_identity(
            models.ExactOnlineExecutionAuthorization,
            {
                "external_decision_id": external_decision.decision_id,
                "v198_freeze_audit_id": freeze.audit_id,
                "frozen_condition_binding_id": condition.binding_id,
                "successor_integration_binding_id": successor.binding_id,
                "v198_report_id": freeze.v198_report_id,
                "v198_decision_id": freeze.v198_decision_id,
                "v198_transition_id": freeze.v198_transition_id,
                "package_catalog_id": condition.package_catalog_id,
                "manifest_id": condition.manifest_id,
                "runner_id": condition.runner_id,
                "execution_contract_id": condition.execution_contract_id,
                "integration_contract_id": successor.integration_contract_id,
                "integration_implementation_binding_id": (
                    successor.integration_implementation_binding_id
                ),
                "generation_profile_id": condition.generation_profile_id,
                "model_config_id": condition.model_config_id,
                "thinking_policy_id": condition.thinking_policy_id,
                "action_grammar_id": condition.action_grammar_id,
                "final_grammar_id": condition.final_grammar_id,
                "bounded_generation_policy_id": condition.bounded_generation_policy_id,
                "generation_resource_contract_id": (condition.generation_resource_contract_id),
                "kernel_resource_persistence_contract_id": (
                    condition.kernel_resource_persistence_contract_id
                ),
                "terminal_registry_id": successor.terminal_registry_id,
                "raw_descriptor_contract_id": successor.raw_descriptor_contract_id,
                "result_descriptor_contract_id": successor.result_descriptor_contract_id,
                "attempt_trace_contract_id": successor.attempt_trace_contract_id,
                "outcome_row_contract_id": successor.outcome_row_contract_id,
                "evaluator_contract_id": successor.evaluator_contract_id,
                "exact_job_ids": condition.exact_job_ids,
                "exact_job_set_sha256": condition.exact_job_set_sha256,
                "raw_namespace_set_sha256": condition.raw_namespace_set_sha256,
                "result_namespace_set_sha256": condition.result_namespace_set_sha256,
            },
            field="authorization_id",
            prefix="fresh_terminal_to_outcome_exact_online_execution_authorization:",
        ),
    )


def _request_arguments(
    authorization: models.ExactOnlineExecutionAuthorization,
) -> dict[str, Any]:
    return {
        "authorization": authorization,
        "authorization_bytes": models.canonical_bytes(authorization),
        "requested_stage": authorization.authorized_stage,
        "requested_manifest_id": authorization.manifest_id,
        "requested_job_ids": authorization.exact_job_ids,
        "requested_runner_id": authorization.runner_id,
        "requested_execution_contract_id": authorization.execution_contract_id,
        "requested_integration_contract_id": authorization.integration_contract_id,
        "requested_generation_profile_id": authorization.generation_profile_id,
        "requested_model_config_id": authorization.model_config_id,
        "requested_thinking_policy_id": authorization.thinking_policy_id,
        "requested_action_grammar_id": authorization.action_grammar_id,
        "requested_final_grammar_id": authorization.final_grammar_id,
        "requested_policy_id": authorization.bounded_generation_policy_id,
        "requested_generation_resource_contract_id": (
            authorization.generation_resource_contract_id
        ),
        "requested_kernel_resource_contract_id": (
            authorization.kernel_resource_persistence_contract_id
        ),
        "provider_execution_requested": True,
        "qa_integration_requested": False,
    }


def _prepare_online_entry(
    *,
    guard: models.PrecredentialOnlineAuthorizationGuard,
    request: dict[str, Any],
    client_factory: Any,
    kernel_writer_factory: Any,
    outcome_writer_factory: Any,
) -> models.OnlineAuthorizationAdmission:
    admission = guard.admit(**request)
    client_factory()
    kernel_writer_factory()
    outcome_writer_factory()
    return admission


def _admission_control(
    *,
    name: str,
    guard: models.PrecredentialOnlineAuthorizationGuard,
    request: dict[str, Any],
) -> tuple[models.AdmissionControl, models.OnlineAuthorizationAdmission | None]:
    counts = {"client": 0, "kernel": 0, "outcome": 0}

    def client_factory() -> object:
        counts["client"] += 1
        return object()

    def kernel_writer_factory() -> object:
        counts["kernel"] += 1
        return object()

    def outcome_writer_factory() -> object:
        counts["outcome"] += 1
        return object()

    admission: models.OnlineAuthorizationAdmission | None = None
    reason_sha: str | None = None
    try:
        admission = _prepare_online_entry(
            guard=guard,
            request=request,
            client_factory=client_factory,
            kernel_writer_factory=kernel_writer_factory,
            outcome_writer_factory=outcome_writer_factory,
        )
    except (TypeError, ValueError) as exc:
        reason_sha = _sha256_bytes(str(exc).encode("utf-8"))
    admitted = admission is not None
    control = cast(
        models.AdmissionControl,
        models.make_identity(
            models.AdmissionControl,
            {
                "control_name": name,
                "admitted": admitted,
                "rejected": not admitted,
                "rejection_reason_sha256": reason_sha,
                "client_factory_count": counts["client"],
                "kernel_writer_factory_count": counts["kernel"],
                "outcome_writer_factory_count": counts["outcome"],
            },
            field="control_id",
            prefix="finance_v26_199_precredential_admission_control:",
        ),
    )
    return control, admission


def _admission_audit(
    authorization: models.ExactOnlineExecutionAuthorization,
) -> tuple[models.OnlineAuthorizationAdmission, models.PrecredentialAdmissionAudit]:
    authorization_bytes = models.canonical_bytes(authorization)
    guard = models.PrecredentialOnlineAuthorizationGuard(
        expected_authorization=authorization,
        expected_authorization_bytes=authorization_bytes,
    )
    source = inspect.getsource(_prepare_online_entry)
    positions = (
        source.find("guard.admit"),
        source.find("client_factory()"),
        source.find("kernel_writer_factory()"),
        source.find("outcome_writer_factory()"),
    )
    if positions[0] < 0 or positions != tuple(sorted(positions)):
        _fail("admission.order", "authorization guard is not before all factories")
    exact = _request_arguments(authorization)
    self_declared = authorization.model_construct(authorization_id="self_declared")
    changed_jobs = list(authorization.exact_job_ids)
    changed_jobs[0] = "authoritative_kernel_development_job:" + "f" * 64
    invalid_requests = (
        ("missing_authorization", {**exact, "authorization": None}),
        (
            "modified_authorization_bytes",
            {**exact, "authorization_bytes": authorization_bytes + b" "},
        ),
        ("self_declared_authorization", {**exact, "authorization": self_declared}),
        ("cross_manifest", {**exact, "requested_manifest_id": "cross.manifest"}),
        ("changed_job_set", {**exact, "requested_job_ids": tuple(sorted(changed_jobs))}),
        ("changed_model", {**exact, "requested_model_config_id": "cross.model"}),
        ("changed_thinking", {**exact, "requested_thinking_policy_id": "cross.thinking"}),
        ("qa_integration_request", {**exact, "qa_integration_requested": True}),
        ("provider_execution_absent", {**exact, "provider_execution_requested": False}),
    )
    legal_control, admission = _admission_control(
        name="exact_online_authorization",
        guard=guard,
        request=exact,
    )
    if admission is None:
        _fail("admission.legal", "exact online Authorization did not admit")
    controls = [legal_control]
    for name, request in invalid_requests:
        control, invalid_admission = _admission_control(
            name=name,
            guard=guard,
            request=request,
        )
        if invalid_admission is not None:
            _fail("admission.invalid", f"invalid control admitted: {name}")
        controls.append(control)
    audit = cast(
        models.PrecredentialAdmissionAudit,
        models.make_identity(
            models.PrecredentialAdmissionAudit,
            {
                "authorization_id": authorization.authorization_id,
                "admission_id": admission.admission_id,
                "controls": tuple(controls),
            },
            field="audit_id",
            prefix="finance_v26_199_precredential_admission_audit:",
        ),
    )
    return admission, audit


def _rehash_authorization(
    authorization: models.ExactOnlineExecutionAuthorization,
    updates: dict[str, Any],
) -> models.ExactOnlineExecutionAuthorization:
    values = authorization.model_dump(mode="python", warnings=False)
    values.pop("authorization_id")
    values.update(updates)
    return cast(
        models.ExactOnlineExecutionAuthorization,
        models.make_identity(
            models.ExactOnlineExecutionAuthorization,
            values,
            field="authorization_id",
            prefix="fresh_terminal_to_outcome_exact_online_execution_authorization:",
        ),
    )


def _destructive_audit(
    authorization: models.ExactOnlineExecutionAuthorization,
) -> models.DestructiveAudit:
    changed_jobs = list(authorization.exact_job_ids)
    changed_jobs[0] = "authoritative_kernel_development_job:" + "e" * 64
    changed_job_tuple = tuple(sorted(changed_jobs))
    attacks: tuple[tuple[str, dict[str, Any]], ...] = (
        ("v198_report_replacement", {"v198_report_id": "attack.v198.report"}),
        ("v198_decision_replacement", {"v198_decision_id": "attack.v198.decision"}),
        ("v198_transition_replacement", {"v198_transition_id": "attack.v198.transition"}),
        ("package_catalog_replacement", {"package_catalog_id": "attack.catalog"}),
        ("manifest_replacement", {"manifest_id": "attack.manifest"}),
        ("runner_replacement", {"runner_id": "attack.runner"}),
        ("execution_contract_replacement", {"execution_contract_id": "attack.execution"}),
        ("integration_contract_replacement", {"integration_contract_id": "attack.integration"}),
        (
            "integration_implementation_replacement",
            {"integration_implementation_binding_id": "attack.implementation"},
        ),
        ("generation_profile_replacement", {"generation_profile_id": "attack.profile"}),
        ("model_replacement", {"model_config_id": "attack.model"}),
        ("thinking_replacement", {"thinking_policy_id": "attack.thinking"}),
        ("action_grammar_replacement", {"action_grammar_id": "attack.action.grammar"}),
        ("final_grammar_replacement", {"final_grammar_id": "attack.final.grammar"}),
        ("bounded_policy_replacement", {"bounded_generation_policy_id": "attack.policy"}),
        (
            "generation_resource_replacement",
            {"generation_resource_contract_id": "attack.generation.resource"},
        ),
        (
            "kernel_resource_replacement",
            {"kernel_resource_persistence_contract_id": "attack.kernel.resource"},
        ),
        ("terminal_registry_replacement", {"terminal_registry_id": "attack.registry"}),
        (
            "job_set_substitution",
            {
                "exact_job_ids": changed_job_tuple,
                "exact_job_set_sha256": _set_sha256(changed_job_tuple),
            },
        ),
        ("raw_namespace_set_replacement", {"raw_namespace_set_sha256": "f" * 64}),
    )
    guard = models.PrecredentialOnlineAuthorizationGuard(
        expected_authorization=authorization,
        expected_authorization_bytes=models.canonical_bytes(authorization),
    )
    request = _request_arguments(authorization)
    controls: list[models.DestructiveControl] = []
    for name, updates in attacks:
        changed = _rehash_authorization(authorization, updates)
        control, admission = _admission_control(
            name=f"destructive_{name}",
            guard=guard,
            request={
                **request,
                "authorization": changed,
                "authorization_bytes": models.canonical_bytes(changed),
            },
        )
        if admission is not None or not control.rejected:
            _fail("destructive", f"fully rehashed attack admitted: {name}")
        controls.append(
            cast(
                models.DestructiveControl,
                models.make_identity(
                    models.DestructiveControl,
                    {
                        "attack_name": name,
                        "changed_authorization_id": changed.authorization_id,
                    },
                    field="control_id",
                    prefix="finance_v26_199_online_authorization_destructive_control:",
                ),
            )
        )
    return cast(
        models.DestructiveAudit,
        models.make_identity(
            models.DestructiveAudit,
            {
                "authorization_id": authorization.authorization_id,
                "controls": tuple(controls),
            },
            field="audit_id",
            prefix="finance_v26_199_online_authorization_destructive_audit:",
        ),
    )


def _gate(name: str, *evidence_ids: str) -> models.StaticGate:
    return models.StaticGate(name=name, evidence_ids=tuple(evidence_ids))


def _artifact_manifest(root: Path, *, scope: str) -> models.ArtifactManifest:
    members = tuple(
        models.ArtifactMember(
            relative_path=path.relative_to(root).as_posix(),
            sha256=_sha256_bytes(path.read_bytes()),
            byte_count=path.stat().st_size,
        )
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )
    artifact_root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix=f"finance_v26_199_{scope}_artifact_root:",
    )
    return cast(
        models.ArtifactManifest,
        models.make_identity(
            models.ArtifactManifest,
            {
                "run_id": RUN_ID,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": artifact_root,
                "scope": scope,
            },
            field="manifest_id",
            prefix=f"finance_v26_199_{scope}_artifact_manifest:",
        ),
    )


def build(
    *,
    repository_root: Path,
    audit_path: Path,
    output_dir: Path,
) -> models.OnlineAuthorizationReport:
    if output_dir.exists():
        _fail("output", "v26.199 output directory already exists")
    external_decision, audit_bytes = _external_decision(audit_path)
    freeze = _v198_freeze(
        repository_root=repository_root,
        external_decision=external_decision,
    )
    condition = _frozen_condition(
        repository_root=repository_root,
        external_decision=external_decision,
        freeze=freeze,
    )
    successor = _successor_binding(
        repository_root=repository_root,
        freeze=freeze,
        condition=condition,
    )
    authorization = _online_authorization(
        external_decision=external_decision,
        freeze=freeze,
        condition=condition,
        successor=successor,
    )
    admission, admission_audit = _admission_audit(authorization)
    scope = cast(
        models.ScopeExclusionAudit,
        models.make_identity(
            models.ScopeExclusionAudit,
            {"authorization_id": authorization.authorization_id},
            field="audit_id",
            prefix="finance_v26_199_scope_exclusion_audit:",
        ),
    )
    destructive = _destructive_audit(authorization)
    gates = (
        _gate("exact_external_v26_198_online_decision", external_decision.decision_id),
        _gate("v26_198_exact_report_parent", freeze.audit_id),
        _gate("v26_198_exact_decision_parent", freeze.audit_id),
        _gate("v26_198_exact_transition_parent", freeze.audit_id),
        _gate("v26_198_exact_48_file_authority", freeze.audit_id),
        _gate("v26_198_sealed_and_distribution_roots", freeze.audit_id),
        _gate("v26_194_exact_32_package_condition", condition.binding_id),
        _gate("v26_194_exact_192_job_manifest", condition.binding_id),
        _gate("v26_194_exact_792_registered_invocations", condition.binding_id),
        _gate("v26_194_unique_raw_result_namespaces", condition.binding_id),
        _gate("exact_generation_profile", condition.binding_id),
        _gate("exact_model_config", condition.binding_id),
        _gate("exact_thinking_policy", condition.binding_id),
        _gate("exact_action_and_final_grammars", condition.binding_id),
        _gate("exact_bounded_policy", condition.binding_id),
        _gate("exact_generation_and_kernel_resource_contracts", condition.binding_id),
        _gate("exact_successor_kernel_identity", successor.binding_id),
        _gate("exact_fresh_integration_contract", successor.binding_id),
        _gate("six_outcome_authority_semantics_unchanged", successor.binding_id),
        _gate("old_complete_job_fallback_forbidden", successor.binding_id),
        _gate("exact_one_manifest_execution_scope", authorization.authorization_id),
        _gate("precredential_online_authorization_admits_exact_request", admission.admission_id),
        _gate("invalid_requests_reject_before_factories", admission_audit.audit_id),
        _gate("fully_rehashed_authorization_attacks_reject", destructive.audit_id),
        _gate("provider_calls_during_authorization_zero", scope.audit_id),
        _gate("online_authorization_not_consumed", scope.audit_id),
        _gate("qa_integration_forbidden", scope.audit_id),
        _gate("downstream_empirical_and_vtdo_rows_zero", scope.audit_id),
    )
    static = cast(
        models.StaticAudit,
        models.make_identity(
            models.StaticAudit,
            {"gates": gates},
            field="audit_id",
            prefix="finance_v26_199_static_audit:",
        ),
    )
    decision = cast(
        models.OnlineAuthorizationDecision,
        models.make_identity(
            models.OnlineAuthorizationDecision,
            {
                "external_decision_id": external_decision.decision_id,
                "v198_freeze_audit_id": freeze.audit_id,
                "frozen_condition_binding_id": condition.binding_id,
                "successor_integration_binding_id": successor.binding_id,
                "authorization_id": authorization.authorization_id,
                "precredential_admission_audit_id": admission_audit.audit_id,
                "scope_exclusion_audit_id": scope.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "decision": (
                    "exact_frozen_192_job_online_execution_authorization_issued_not_consumed"
                ),
            },
            field="decision_id",
            prefix="finance_v26_199_online_authorization_decision:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {
                "decision_id": decision.decision_id,
                "authorization_id": authorization.authorization_id,
            },
            field="transition_id",
            prefix="finance_v26_199_transition:",
        ),
    )
    payloads: dict[str, bytes] = {
        "external_v26_198_online_authorization_audit.txt": audit_bytes,
        "external_online_authorization_decision.json": _canonical_bytes(external_decision),
        "v26_198_authority_freeze_audit.json": _canonical_bytes(freeze),
        "frozen_execution_condition_binding.json": _canonical_bytes(condition),
        "successor_integration_authority_binding.json": _canonical_bytes(successor),
        "exact_online_execution_authorization.json": _canonical_bytes(authorization),
        "online_authorization_admission.json": _canonical_bytes(admission),
        "precredential_admission_audit.json": _canonical_bytes(admission_audit),
        "scope_exclusion_audit.json": _canonical_bytes(scope),
        "destructive_audit.json": _canonical_bytes(destructive),
        "static_audit.json": _canonical_bytes(static),
        "online_authorization_decision.json": _canonical_bytes(decision),
        "prospective_transition.json": _canonical_bytes(transition),
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, payload in sorted(payloads.items()):
        _write_no_replace(output_dir / name, payload)
    sealed = _artifact_manifest(output_dir, scope="sealed_evidence")
    if sealed.file_count != 13:
        _fail("artifact.sealed", "v26.199 sealed evidence file count differs")
    _write_no_replace(output_dir / "sealed_evidence_manifest.json", _canonical_bytes(sealed))
    source_commit, source_tree = _git_identity(repository_root)
    report = cast(
        models.OnlineAuthorizationReport,
        models.make_identity(
            models.OnlineAuthorizationReport,
            {
                "run_id": RUN_ID,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "external_decision_id": external_decision.decision_id,
                "v198_freeze_audit_id": freeze.audit_id,
                "frozen_condition_binding_id": condition.binding_id,
                "successor_integration_binding_id": successor.binding_id,
                "authorization_id": authorization.authorization_id,
                "admission_id": admission.admission_id,
                "precredential_admission_audit_id": admission_audit.audit_id,
                "scope_exclusion_audit_id": scope.audit_id,
                "destructive_audit_id": destructive.audit_id,
                "static_audit_id": static.audit_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
                "sealed_manifest_id": sealed.manifest_id,
                "sealed_artifact_root": sealed.artifact_root,
                "decision": decision.decision,
            },
            field="report_id",
            prefix="finance_v26_199_terminal_outcome_online_authorization_report:",
        ),
    )
    _write_no_replace(output_dir / "report.json", _canonical_bytes(report))
    distribution = _artifact_manifest(output_dir, scope="distribution")
    if distribution.file_count != 15:
        _fail("artifact.distribution", "v26.199 distribution file count differs")
    _write_no_replace(output_dir / "artifact_manifest.json", _canonical_bytes(distribution))
    if len(_recursive_bindings(output_dir)) != 16:
        _fail("artifact.final", "v26.199 formal file count differs")
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
