# ruff: noqa: E501, SLF001
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
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_authoritative_execution_kernel_models as v194_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_execution as v188,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_first_response_action_interface_disambiguation_calibration_preflight_models as v203_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight_models as v206_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_preflight_independent_audit_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair as v193,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair_models as v193_models,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    make_qualified_final_host_envelope,
    parse_qualified_final_response,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    SemanticActionResponseRejection,
    parse_exact_canonical_action_payload,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    make_stage_one_request_body,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = (
    "finance_v26_207_fresh_repaired_full_condition_preflight_independent_audit_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_AUDIT_SHA256: Final = "c305d4092220fd02344051690445f885ae3139c25134d61be1513cfeb826677f"
EXTERNAL_AUDIT_BYTES: Final = 12_167
V206_COMMIT: Final = "0266bfc027ee6ef74f4d8b3a8762ebf7cdeeccb2"
V206_TREE: Final = "98afacbad5b4af207dc00d851a9937d81ce0b9f5"
V206_DIR: Final = "trusted_data_synthesis/artifacts/vtdo_experiment/finance_v26_206_fresh_repaired_action_interface_full_condition_integration_preflight_v1_20260902"
V194_DIR: Final = "trusted_data_synthesis/artifacts/vtdo_experiment/finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
V193_DIR: Final = "trusted_data_synthesis/artifacts/vtdo_experiment/finance_v26_193_json_prompt_authority_repair_preflight_v2_20260901"
V203_DIR: Final = "trusted_data_synthesis/artifacts/vtdo_experiment/finance_v26_203_fresh_first_response_action_interface_disambiguation_stratified_calibration_population_preflight_v1_20260902"
V192_GENERATION_PROFILE: Final = "trusted_data_synthesis/artifacts/vtdo_experiment/finance_v26_192_json_explicit_prompt_contract_preflight_v1_20260831/json_explicit_generation_profile.json"
MODEL_PROFILE: Final = (
    "trusted_data_synthesis/config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
)
V194_RESOURCE_CONTRACT_ID: Final = "authoritative_kernel_resource_persistence_contract:ba6fb7967c3429d05184cc7a3ddc619187bf28ea438cc1b46bd66ce6a21055b4"
IMPLEMENTATION_FILES: Final = tuple(
    sorted(
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_repaired_full_condition_preflight_independent_audit.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_repaired_full_condition_preflight_independent_audit_models.py",
            "trusted_data_synthesis/tests/test_v26_fresh_repaired_full_condition_preflight_independent_audit.py",
        )
    )
)


class V207Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V207Error(stage, reason)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _bytes(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()


def _key_count(value: Any, target: str) -> int:
    if isinstance(value, dict):
        return int(target in value) + sum(_key_count(item, target) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_key_count(item, target) for item in value)
    return 0


def _make(model_type: type[Any], values: dict[str, Any], field: str, prefix: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=prefix)


def _authorization(path: Path) -> tuple[models.ExternalIndependentAuditAuthorization, bytes]:
    payload = path.read_bytes()
    if len(payload) != EXTERNAL_AUDIT_BYTES or _sha(payload) != EXTERNAL_AUDIT_SHA256:
        _fail("A0.authorization", "v26.207 external Audit bytes differ")
    return cast(
        models.ExternalIndependentAuditAuthorization,
        _make(
            models.ExternalIndependentAuditAuthorization,
            {"audit_sha256": _sha(payload), "audit_byte_count": len(payload)},
            "authorization_id",
            "finance_v26_207_external_independent_audit_authorization:",
        ),
    ), payload


def _targets(repository_root: Path) -> dict[str, Any]:
    root = repository_root / V206_DIR
    manifest = v206_models.ArtifactManifest.model_validate(_load(root / "artifact_manifest.json"))
    paths = tuple(sorted(path.name for path in root.iterdir() if path.is_file()))
    if len(paths) != 17 or sum((root / name).stat().st_size for name in paths) != 2_519_097:
        _fail("A0.geometry", "v26.206 formal directory geometry differs")
    if {item.relative_path for item in manifest.members} != set(paths) - {"artifact_manifest.json"}:
        _fail("A0.paths", "v26.206 formal path set differs")
    for item in manifest.members:
        payload = (root / item.relative_path).read_bytes()
        if len(payload) != item.byte_count or _sha(payload) != item.sha256:
            _fail("A0.bytes", f"v26.206 member differs:{item.relative_path}")
    return {name: _load(root / name) for name in paths if name.endswith(".json")}


def _freeze(authorization_id: str, targets: dict[str, Any]) -> models.V206PreflightFreeze:
    report = v206_models.PreflightReport.model_validate(targets["report.json"])
    transition = v206_models.ProspectiveTransition.model_validate(
        targets["prospective_transition.json"]
    )
    gates = v206_models.FullConditionGateAudit.model_validate(
        targets["full_condition_gate_audit.json"]
    )
    census = v206_models.RepairedCallsiteCensus.model_validate(
        targets["repaired_callsite_census.json"]
    )
    integration = v206_models.ScriptedIntegrationAudit.model_validate(
        targets["scripted_integration_audit.json"]
    )
    manifest = v206_models.RepairedDevelopmentManifest.model_validate(
        targets["repaired_development_manifest.json"]
    )
    runner = v206_models.RepairedRunnerContract.model_validate(
        targets["repaired_runner_contract.json"]
    )
    execution = v206_models.RepairedExecutionContract.model_validate(
        targets["repaired_execution_contract.json"]
    )
    estimand = v206_models.ProspectiveEstimandContract.model_validate(
        targets["prospective_estimand_contract.json"]
    )
    artifact = v206_models.ArtifactManifest.model_validate(targets["artifact_manifest.json"])
    return cast(
        models.V206PreflightFreeze,
        _make(
            models.V206PreflightFreeze,
            {
                "authorization_id": authorization_id,
                "v206_report_id": report.report_id,
                "v206_transition_id": transition.transition_id,
                "v206_gate_audit_id": gates.audit_id,
                "v206_callsite_census_id": census.census_id,
                "v206_scripted_integration_audit_id": integration.audit_id,
                "v206_manifest_id": manifest.manifest_id,
                "v206_runner_id": runner.runner_id,
                "v206_execution_contract_id": execution.contract_id,
                "v206_estimand_contract_id": estimand.contract_id,
                "v206_artifact_manifest_id": artifact.manifest_id,
                "v206_artifact_root": artifact.artifact_root,
                "v206_source_commit": V206_COMMIT,
                "v206_source_tree": V206_TREE,
            },
            "freeze_id",
            "finance_v26_207_v206_preflight_freeze:",
        ),
    )


def _detached_rebuild(
    repository_root: Path, freeze_id: str
) -> tuple[models.DetachedSourceRebuildAudit, bytes, bytes]:
    with tempfile.TemporaryDirectory(prefix="v26-207-detached-") as temporary:
        base = Path(temporary)
        archive = base / "source.tar"
        snapshot = base / "snapshot"
        snapshot.mkdir()
        subprocess.run(
            ["git", "archive", "--format=tar", f"--output={archive}", V206_COMMIT],
            cwd=repository_root,
            check=True,
            capture_output=True,
        )
        with tarfile.open(archive) as stream:
            stream.extractall(snapshot, filter="data")
        tree_id = subprocess.run(
            ["git", "rev-parse", f"{V206_COMMIT}^{{tree}}"],
            cwd=repository_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        if tree_id != V206_TREE:
            _fail("A1.tree", "v26.206 exact tree differs")
        rebuilt = base / "rebuilt"
        module = "trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight"
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(snapshot / "trusted_data_synthesis/src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "C.UTF-8",
        }
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                module,
                "--repository-root",
                str(repository_root),
                "--output-dir",
                str(rebuilt),
                "--external-audit",
                str(repository_root / V206_DIR / "external_audit.txt"),
                "--source-commit",
                V206_COMMIT,
                "--source-tree",
                V206_TREE,
            ],
            cwd=snapshot,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
        if run.returncode:
            _fail("A1.execution", run.stderr[-2000:])
        saved = repository_root / V206_DIR
        names = tuple(sorted(path.name for path in rebuilt.iterdir() if path.is_file()))
        if names != tuple(sorted(path.name for path in saved.iterdir() if path.is_file())) or any(
            (rebuilt / name).read_bytes() != (saved / name).read_bytes() for name in names
        ):
            _fail("A1.bytes", "detached v26.206 rebuild differs")
        source_rel = "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight.py"
        source_bytes = (snapshot / source_rel).read_bytes()
        model_bytes = (snapshot / source_rel.replace(".py", "_models.py")).read_bytes()
    return (
        cast(
            models.DetachedSourceRebuildAudit,
            _make(
                models.DetachedSourceRebuildAudit,
                {
                    "freeze_id": freeze_id,
                    "exact_source_commit": V206_COMMIT,
                    "exact_source_tree": V206_TREE,
                },
                "audit_id",
                "finance_v26_207_detached_source_rebuild_audit:",
            ),
        ),
        source_bytes,
        model_bytes,
    )


def _calls(tree: ast.AST, function: str, called: str) -> int:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function:
            return sum(
                isinstance(item, ast.Call)
                and (
                    (isinstance(item.func, ast.Name) and item.func.id == called)
                    or (isinstance(item.func, ast.Attribute) and item.func.attr == called)
                )
                for item in ast.walk(node)
            )
    return 0


def _route(
    freeze_id: str,
    census: v206_models.RepairedCallsiteCensus,
    source_bytes: bytes,
    model_bytes: bytes,
) -> models.SourceRouteNoBypassAudit:
    tree = ast.parse(source_bytes)
    definitions = Counter(node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
    actions = tuple(row for row in census.rows if row.phase != "final")
    direct_names = {
        "ProviderClient",
        "DeepSeekClient",
        "OpenAI",
        "create_client",
        "invoke_provider",
        "send_request",
        "transport_request",
        "invoke_action",
        "invoke_correction",
    }
    direct = sum(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in direct_names)
            or (isinstance(node.func, ast.Attribute) and node.func.attr in direct_names)
        )
        for node in ast.walk(tree)
    )
    executable = sum(
        isinstance(node, (ast.FunctionDef, ast.ClassDef))
        and any(
            token in node.name.lower()
            for token in ("online_runner", "provider_runner", "execution_runner")
        )
        for node in ast.walk(tree)
    )
    transport = sum(
        isinstance(node, (ast.FunctionDef, ast.ClassDef)) and "transport" in node.name.lower()
        for node in ast.walk(tree)
    )
    observed = (
        definitions["_repaired_messages"],
        definitions["_callsite_row"],
        definitions["_scripted_integration"],
        _calls(tree, "_callsite_row", "_repaired_messages"),
        _calls(tree, "_callsite_row", "make_stage_one_request_body"),
        _calls(tree, "_scripted_integration", "_callsite_row"),
        len(actions),
        sum(row.exact_four_field_action_contract for row in actions),
        direct,
        executable,
        transport,
    )
    if observed != (1, 1, 1, 1, 1, 3, 600, 600, 0, 0, 0):
        _fail("A3.source", f"v26.206 route source geometry differs:{observed}")
    return cast(
        models.SourceRouteNoBypassAudit,
        _make(
            models.SourceRouteNoBypassAudit,
            {
                "freeze_id": freeze_id,
                "exact_source_commit": V206_COMMIT,
                "preflight_source_sha256": _sha(source_bytes),
                "model_source_sha256": _sha(model_bytes),
            },
            "audit_id",
            "finance_v26_207_source_route_no_bypass_audit:",
        ),
    )


def _parent_chain(
    repository_root: Path, freeze_id: str, targets: dict[str, Any]
) -> tuple[
    models.IndependentParentReconstructionAudit,
    v206_models.FullConditionRepairProfile,
    v206_models.RepairedDevelopmentManifest,
    v206_models.RepairedExecutionContract,
    v194_models.AuthoritativeDevelopmentManifest,
    v193_models.ExactPromptEvidenceSet,
]:
    v194_root = repository_root / V194_DIR
    source_catalog = v194_models.AuthoritativeRunnerPackageCatalog.model_validate(
        _load(v194_root / "authoritative_runner_package_catalog.json")
    )
    source_manifest = v194_models.AuthoritativeDevelopmentManifest.model_validate(
        _load(v194_root / "authoritative_development_manifest.json")
    )
    source_runner = v194_models.AuthoritativeRunnerContract.model_validate(
        _load(v194_root / "authoritative_runner_contract.json")
    )
    source_execution = v194_models.AuthoritativeExecutionContract.model_validate(
        _load(v194_root / "authoritative_execution_contract.json")
    )
    evidence = v193_models.ExactPromptEvidenceSet.model_validate(
        _load(repository_root / V193_DIR / "exact_prompt_evidence_set.json")
    )
    action_contract = v203_models.ExactActionInterfaceContract.model_validate(
        _load(repository_root / V203_DIR / "exact_action_interface_contract.json")
    )
    old_authorization = v206_models.ExternalPreflightAuthorization.model_validate(
        targets["external_authorization.json"]
    )
    old_freeze = v206_models.PredecessorFreeze.model_validate(targets["predecessor_freeze.json"])
    profile = cast(
        v206_models.FullConditionRepairProfile,
        _make(
            v206_models.FullConditionRepairProfile,
            {
                "authorization_id": old_authorization.authorization_id,
                "predecessor_freeze_id": old_freeze.freeze_id,
                "source_v203_action_contract_id": action_contract.contract_id,
                "frozen_action_grammar_id": action_contract.frozen_action_grammar_id,
                "exact_required_fields": action_contract.required_fields,
                "exact_allowed_fields": action_contract.allowed_fields,
                "decision_kind_value": action_contract.decision_kind_value,
                "protocol_value": action_contract.protocol_value,
            },
            "profile_id",
            "fresh_repaired_action_interface_full_condition_profile:",
        ),
    )
    final_grammar_id = _load(repository_root / V192_GENERATION_PROFILE)["final_grammar_id"]
    packages = tuple(
        cast(
            v206_models.RepairedRunnerPackage,
            _make(
                v206_models.RepairedRunnerPackage,
                {
                    "source_v194_package_id": source.package_id,
                    "source_v194_package_sha256": v206_models.canonical_sha256(source),
                    "repair_profile_id": profile.profile_id,
                    "runtime_semantic_contract_id": source.runtime_semantic_contract_id,
                    "runtime_implementation_binding_id": source.runtime_implementation_binding_id,
                    "final_grammar_id": final_grammar_id,
                    "resource_contract_id": source.resource_persistence_contract_id,
                    "capability_family": source.capability_family,
                    "depth": source.depth,
                    "schedule_ids": source.schedule_ids,
                    "component_keys": source.topological_component_keys,
                },
                "package_id",
                "fresh_repaired_full_condition_runner_package:",
            ),
        )
        for source in sorted(source_catalog.packages, key=lambda item: item.package_id)
    )
    catalog = cast(
        v206_models.RepairedRunnerPackageCatalog,
        _make(
            v206_models.RepairedRunnerPackageCatalog,
            {
                "repair_profile_id": profile.profile_id,
                "packages": packages,
                "source_v194_package_ids": tuple(
                    sorted(item.source_v194_package_id for item in packages)
                ),
            },
            "catalog_id",
            "fresh_repaired_full_condition_package_catalog:",
        ),
    )
    package_by_source = {item.source_v194_package_id: item for item in packages}
    jobs: list[v206_models.RepairedDevelopmentJob] = []
    for source in sorted(source_manifest.jobs, key=lambda item: item.job_id):
        parent = {
            "source_v194_job_id": source.job_id,
            "package_id": package_by_source[source.package_id].package_id,
            "repair_profile_id": profile.profile_id,
            "replica_index": source.replica_index,
        }
        jobs.append(
            cast(
                v206_models.RepairedDevelopmentJob,
                _make(
                    v206_models.RepairedDevelopmentJob,
                    {
                        **parent,
                        "source_v194_job_sha256": v206_models.canonical_sha256(source),
                        "source_v194_package_id": source.package_id,
                        "raw_namespace": canonical_hash(
                            parent, prefix="fresh_repaired_raw_namespace:"
                        ),
                        "result_namespace": canonical_hash(
                            parent, prefix="fresh_repaired_result_namespace:"
                        ),
                        "trace_namespace": canonical_hash(
                            parent, prefix="fresh_repaired_trace_namespace:"
                        ),
                        "outcome_namespace": canonical_hash(
                            parent, prefix="fresh_repaired_outcome_namespace:"
                        ),
                        "deterministic_seed_id": canonical_hash(
                            parent, prefix="fresh_repaired_deterministic_seed:"
                        ),
                    },
                    "job_id",
                    "fresh_repaired_full_condition_development_job:",
                ),
            )
        )
    job_tuple = tuple(jobs)
    manifest = cast(
        v206_models.RepairedDevelopmentManifest,
        _make(
            v206_models.RepairedDevelopmentManifest,
            {
                "package_catalog_id": catalog.catalog_id,
                "repair_profile_id": profile.profile_id,
                "jobs": job_tuple,
                "expected_job_ids": tuple(sorted(item.job_id for item in job_tuple)),
                "source_v194_job_ids": tuple(sorted(item.source_v194_job_id for item in job_tuple)),
            },
            "manifest_id",
            "fresh_repaired_full_condition_manifest:",
        ),
    )
    runner = cast(
        v206_models.RepairedRunnerContract,
        _make(
            v206_models.RepairedRunnerContract,
            {
                "manifest_id": manifest.manifest_id,
                "package_catalog_id": catalog.catalog_id,
                "repair_profile_id": profile.profile_id,
                "source_v194_runner_id": source_runner.runner_id,
            },
            "runner_id",
            "fresh_repaired_full_condition_runner:",
        ),
    )
    execution = cast(
        v206_models.RepairedExecutionContract,
        _make(
            v206_models.RepairedExecutionContract,
            {
                "runner_id": runner.runner_id,
                "manifest_id": manifest.manifest_id,
                "package_catalog_id": catalog.catalog_id,
                "repair_profile_id": profile.profile_id,
                "source_v194_execution_contract_id": source_execution.contract_id,
                "resource_contract_id": V194_RESOURCE_CONTRACT_ID,
            },
            "contract_id",
            "fresh_repaired_full_condition_execution_contract:",
        ),
    )
    saved = (
        v206_models.FullConditionRepairProfile.model_validate(
            targets["full_condition_repair_profile.json"]
        ),
        v206_models.RepairedRunnerPackageCatalog.model_validate(
            targets["repaired_runner_package_catalog.json"]
        ),
        v206_models.RepairedDevelopmentManifest.model_validate(
            targets["repaired_development_manifest.json"]
        ),
        v206_models.RepairedRunnerContract.model_validate(targets["repaired_runner_contract.json"]),
        v206_models.RepairedExecutionContract.model_validate(
            targets["repaired_execution_contract.json"]
        ),
    )
    if any(
        left.model_dump(mode="json") != right.model_dump(mode="json")
        for left, right in zip((profile, catalog, manifest, runner, execution), saved, strict=True)
    ):
        _fail("A2.match", "independently rebuilt parent object differs")
    old_ids = {
        *[item.package_id for item in source_catalog.packages],
        *[item.job_id for item in source_manifest.jobs],
        *[item.raw_namespace for item in source_manifest.jobs],
        *[item.result_namespace for item in source_manifest.jobs],
    }
    new_ids = {
        *[item.package_id for item in catalog.packages],
        *[item.job_id for item in manifest.jobs],
        *[item.raw_namespace for item in manifest.jobs],
        *[item.result_namespace for item in manifest.jobs],
        *[item.trace_namespace for item in manifest.jobs],
        *[item.outcome_namespace for item in manifest.jobs],
    }
    audit = cast(
        models.IndependentParentReconstructionAudit,
        _make(
            models.IndependentParentReconstructionAudit,
            {
                "freeze_id": freeze_id,
                "reconstructed_repair_profile_id": profile.profile_id,
                "reconstructed_package_catalog_id": catalog.catalog_id,
                "reconstructed_manifest_id": manifest.manifest_id,
                "reconstructed_runner_id": runner.runner_id,
                "reconstructed_execution_contract_id": execution.contract_id,
                "predecessor_identity_collision_count": len(old_ids & new_ids),
            },
            "audit_id",
            "finance_v26_207_independent_parent_reconstruction_audit:",
        ),
    )
    return audit, profile, manifest, execution, source_manifest, evidence


def _messages(
    core: dict[str, Any], prompt_kind: str, profile: v206_models.FullConditionRepairProfile
) -> tuple[tuple[dict[str, str], ...], str, tuple[str, ...]]:
    public = copy.deepcopy(core["public_prompt"])
    semantic = public["task"]["semantic_task"]
    answer_fields = semantic.pop("answer_fields")
    operation_fields = semantic.pop("operator_output_fields")
    state_id = public["state"]["state_token"]
    candidates = tuple(item["action_id"] for item in public["candidates"])
    system = {
        "authoritative_response_contract": {
            "additional_properties": False,
            "allowed_fields": list(profile.exact_allowed_fields),
            "exactly_one_json_object": True,
            "field_values": {
                "action_id": {"one_of": list(candidates)},
                "decision_kind": profile.decision_kind_value,
                "protocol": profile.protocol_value,
                "state_id": state_id,
            },
            "required_fields": list(profile.exact_required_fields),
            "wrapper_allowed": False,
        },
        "instruction": "Return exactly one JSON object conforming only to the authoritative four-field Action response contract. Do not answer the task directly and do not emit any additional field or wrapper.",
    }
    user = {
        "interface_profile": "disambiguated_action_interface_full_condition",
        "prompt_kind": prompt_kind,
        "public_prompt": public,
        "response_contract_location": "system_message_only",
        "verifier_internal_task_metadata": {
            "answer_fields": answer_fields,
            "classification": "verifier_internal_task_metadata_not_model_response_schema",
            "model_response_schema": False,
            "operator_output_fields": operation_fields,
        },
    }
    if (
        _key_count(user, "response_abi")
        or _key_count(user, "grammar_id")
        or _key_count(system, "grammar_id")
    ):
        _fail("A4.interface", "old ABI or Grammar ID remains model-visible")
    return (
        (
            {"role": "system", "content": models.canonical_bytes(system).decode()},
            {"role": "user", "content": models.canonical_bytes(user).decode()},
        ),
        state_id,
        candidates,
    )


def _callsite(
    source_row: v193_models.ProviderRequestEvidenceRow,
    source_job_id: str,
    fresh_job_id: str,
    core: dict[str, Any],
    config: AgentModelConfig,
    profile: v206_models.FullConditionRepairProfile,
    final_grammar_id: str,
) -> v206_models.RepairedCallsiteRow:
    coordinate = source_row.coordinate
    candidates: tuple[str, ...]
    if v206_models.canonical_sha256(core) != source_row.prompt_core_sha256:
        _fail("A4.core", "Runtime Prompt core differs from v26.193")
    if coordinate.phase == "final":
        request = json.loads(source_row.request_body_canonical_json)
        messages = tuple(request["messages"])
        state_id, candidates = coordinate.state_token, ()
        parser_id = "prospective_qualified_final_response_grammar.parse_qualified_final_response"
        grammar_id, action_contract = final_grammar_id, False
    else:
        messages, state_id, candidates = _messages(core, coordinate.prompt_kind, profile)
        request = make_stage_one_request_body(config, messages[-1]["content"])
        request["messages"] = [dict(item) for item in messages]
        parser_id = (
            "prospective_semantic_action_response_grammar.parse_exact_canonical_action_payload"
        )
        grammar_id, action_contract = profile.frozen_action_grammar_id, True
    message_bytes, request_bytes = models.canonical_bytes(messages), models.canonical_bytes(request)
    prompt_id = canonical_hash(
        {
            "fresh_job_id": fresh_job_id,
            "source_v193_coordinate_id": coordinate.coordinate_id,
            "canonical_messages_sha256": _sha(message_bytes),
            "repair_profile_id": profile.profile_id,
        },
        prefix="fresh_repaired_full_condition_prompt:",
    )
    request_id = canonical_hash(
        {
            "fresh_job_id": fresh_job_id,
            "repaired_prompt_id": prompt_id,
            "canonical_request_body_sha256": _sha(request_bytes),
        },
        prefix="fresh_repaired_full_condition_request:",
    )
    return cast(
        v206_models.RepairedCallsiteRow,
        _make(
            v206_models.RepairedCallsiteRow,
            {
                "source_v193_evidence_row_id": source_row.row_id,
                "source_v193_coordinate_id": coordinate.coordinate_id,
                "source_v194_job_id": source_job_id,
                "fresh_job_id": fresh_job_id,
                "invocation_index": coordinate.invocation_index,
                "phase": coordinate.phase,
                "prompt_kind": coordinate.prompt_kind,
                "component_key": coordinate.component_key,
                "current_state_id": state_id,
                "candidate_action_ids": candidates,
                "rejected_action_id": coordinate.rejected_action_id,
                "rejection_receipt_id": coordinate.rejection_receipt_id,
                "repaired_prompt_id": prompt_id,
                "request_id": request_id,
                "canonical_messages_sha256": _sha(message_bytes),
                "canonical_messages_byte_count": len(message_bytes),
                "canonical_request_body_sha256": _sha(request_bytes),
                "canonical_request_body_byte_count": len(request_bytes),
                "repair_profile_id": profile.profile_id,
                "parser_id": parser_id,
                "grammar_id": grammar_id,
                "exact_four_field_action_contract": action_contract,
            },
            "row_id",
            "fresh_repaired_full_condition_callsite_row:",
        ),
    )


def _parse_action(
    state_id: str, action_id: str, profile: v206_models.FullConditionRepairProfile
) -> str:
    parsed = parse_exact_canonical_action_payload(
        {
            "state_id": state_id,
            "action_id": action_id,
            "decision_kind": profile.decision_kind_value,
            "protocol": profile.protocol_value,
        }
    )
    if parsed.state_id != state_id or parsed.action_id != action_id:
        _fail("A4.parser", "Action parser crossed State or Action")
    return parsed.action_id


def _replay(
    repository_root: Path,
    freeze_id: str,
    route_id: str,
    execution: v206_models.RepairedExecutionContract,
    manifest: v206_models.RepairedDevelopmentManifest,
    source_manifest: v194_models.AuthoritativeDevelopmentManifest,
    evidence: v193_models.ExactPromptEvidenceSet,
    profile: v206_models.FullConditionRepairProfile,
    targets: dict[str, Any],
) -> tuple[
    models.IndependentCallsiteReconstructionAudit,
    models.IndependentScriptedReplayAudit,
    dict[str, Any],
]:
    config = AgentModelConfig.model_validate(_load(repository_root / MODEL_PROFILE)["model"])
    sources = {item.job_id: item for item in source_manifest.jobs}
    fresh = {item.source_v194_job_id: item for item in manifest.jobs}
    evidence_by_job: dict[str, list[v193_models.ProviderRequestEvidenceRow]] = defaultdict(list)
    for row in evidence.rows:
        evidence_by_job[row.coordinate.fresh_job_id].append(row)
    all_calls: list[v206_models.RepairedCallsiteRow] = []
    all_rows: list[v206_models.ScriptedIntegrationRow] = []
    probes: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="v26-207-runtime-") as temporary:
        prepared = v188.prepare_execution(
            package_root=repository_root / "trusted_data_synthesis",
            output_dir=Path(temporary) / "provider_forbidden",
        )
        old_jobs = {item.job_id: item for item in prepared.frozen.manifest.jobs}
        for source_id in sorted(sources):
            source, new_job = sources[source_id], fresh[source_id]
            source_rows = tuple(
                sorted(
                    evidence_by_job[source.source_job_id],
                    key=lambda item: item.coordinate.invocation_index,
                )
            )
            old_id = source_rows[0].coordinate.source_job_id
            if any(row.coordinate.source_job_id != old_id for row in source_rows):
                _fail("A4.parents", "source Job parent crossed")
            context = frozen_runtime.prepare_job(old_jobs[old_id], prepared.runtime_catalog)
            state = frozen_runtime._initialize(context)
            by_key = {
                (
                    row.coordinate.phase,
                    row.coordinate.state_token,
                    row.coordinate.rejected_action_id,
                    row.coordinate.rejection_receipt_id,
                ): row
                for row in source_rows
            }
            calls: list[v206_models.RepairedCallsiteRow] = []
            actions = subsequent = corrections = 0
            while state.current_index < len(state.ordered_components):
                index = state.current_index
                prompt = step_runtime.render_next_prompt(state)
                dispositions = frozen_runtime._candidate_dispositions(state, prompt)
                phase = "first_action" if index == 0 else "subsequent_action"
                row = _callsite(
                    by_key[(phase, prompt.state.state_token, None, None)],
                    source_id,
                    new_job.job_id,
                    v193._action_core(prompt, prepared),
                    config,
                    profile,
                    prepared.profile.final_grammar_id,
                )
                calls.append(row)
                all_calls.append(row)
                selection = frozen_runtime._reference_selection(state, prompt, dispositions, index)
                if selection.action_id is None:
                    _fail("A4.reference", "reference Action absent")
                action_id = _parse_action(prompt.state.state_token, selection.action_id, profile)
                actions += 1
                subsequent += int(index > 0)
                for invalid in (item for item in dispositions if not item.acceptance.accepted):
                    branch = copy.deepcopy(state)
                    receipt = v193._rejection_receipt(step_runtime.step(branch, invalid.action_id))
                    correction_prompt = step_runtime.render_next_prompt(branch)
                    correction_dispositions = frozen_runtime._candidate_dispositions(
                        branch, correction_prompt
                    )
                    correction = frozen_runtime._reference_correction(
                        branch, correction_prompt, correction_dispositions, index, invalid.action_id
                    )
                    if correction.action_id is None:
                        _fail("A4.correction", "reference Correction absent")
                    correction_row = _callsite(
                        by_key[
                            (
                                "correction",
                                correction_prompt.state.state_token,
                                invalid.action_id,
                                receipt,
                            )
                        ],
                        source_id,
                        new_job.job_id,
                        v193._action_core(correction_prompt, prepared),
                        config,
                        profile,
                        prepared.profile.final_grammar_id,
                    )
                    calls.append(correction_row)
                    all_calls.append(correction_row)
                    corrected = _parse_action(
                        correction_prompt.state.state_token, correction.action_id, profile
                    )
                    if not getattr(step_runtime.step(branch, corrected), "action_accepted", False):
                        _fail("A4.correction", "Correction did not commit")
                    corrections += 1
                    probes.setdefault(
                        "correction", (correction_prompt.state.state_token, corrected)
                    )
                if not getattr(step_runtime.step(state, action_id), "action_accepted", False):
                    _fail("A4.action", "Action did not commit")
                probes.setdefault(
                    "action",
                    (
                        prompt.state.state_token,
                        action_id,
                        tuple(item.action_id for item in prompt.candidates),
                    ),
                )
            result = step_runtime.finalize(state)
            frozen_runtime._parse_final_fixture(
                result, context.source, grammar=prepared.final_grammar, profile=prepared.profile
            )
            final_core, _ = v188.render_final_prompt(
                context=context, result=result, grammar=prepared.final_grammar
            )
            final = _callsite(
                by_key[("final", result.result_id, None, None)],
                source_id,
                new_job.job_id,
                final_core,
                config,
                profile,
                prepared.profile.final_grammar_id,
            )
            calls.append(final)
            all_calls.append(final)
            if tuple(item.invocation_index for item in calls) != tuple(
                item.coordinate.invocation_index for item in source_rows
            ):
                _fail("A4.order", "callsite order differs")
            if not (
                result.task_validity.base_valid
                and result.mechanism_qualification.mechanism_semantically_qualified
                and result.qualified_validity.qualified_valid
            ):
                _fail("A4.validity", "reference trajectory not Qualified")
            call_ids = tuple(item.row_id for item in calls)
            raw_id = canonical_hash(
                {"job_id": new_job.job_id, "callsite_row_ids": call_ids},
                prefix="fresh_repaired_scripted_raw:",
            )
            result_id = canonical_hash(
                {"job_id": new_job.job_id, "raw_id": raw_id, "qualified_valid": True},
                prefix="fresh_repaired_scripted_result:",
            )
            trace_id = canonical_hash(
                {"job_id": new_job.job_id, "raw_id": raw_id, "result_id": result_id},
                prefix="fresh_repaired_scripted_trace:",
            )
            outcome_id = canonical_hash(
                {"job_id": new_job.job_id, "trace_id": trace_id, "qualified_valid": True},
                prefix="fresh_repaired_scripted_outcome:",
            )
            all_rows.append(
                cast(
                    v206_models.ScriptedIntegrationRow,
                    _make(
                        v206_models.ScriptedIntegrationRow,
                        {
                            "job_id": new_job.job_id,
                            "source_v194_job_id": source_id,
                            "callsite_row_ids": call_ids,
                            "subsequent_action_count": subsequent,
                            "typed_rejection_branch_count": corrections,
                            "correction_count": corrections,
                            "exact_action_parse_count": actions,
                            "action_reference_and_state_valid_count": actions,
                            "correction_reference_and_state_valid_count": corrections,
                            "runtime_commit_count": actions,
                            "raw_id": raw_id,
                            "result_id": result_id,
                            "trace_id": trace_id,
                            "outcome_id": outcome_id,
                        },
                        "row_id",
                        "finance_v26_206_scripted_integration_row:",
                    ),
                )
            )
            probes.setdefault("final", (result, prepared))
    call_tuple = tuple(sorted(all_calls, key=lambda item: item.row_id))
    rebuilt_census = cast(
        v206_models.RepairedCallsiteCensus,
        _make(
            v206_models.RepairedCallsiteCensus,
            {
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "repair_profile_id": profile.profile_id,
                "source_v193_evidence_set_id": evidence.evidence_set_id,
                "rows": call_tuple,
                "maximum_repaired_message_byte_count": max(
                    item.canonical_messages_byte_count for item in call_tuple
                ),
                "maximum_repaired_request_body_byte_count": max(
                    item.canonical_request_body_byte_count for item in call_tuple
                ),
            },
            "census_id",
            "finance_v26_206_repaired_callsite_census:",
        ),
    )
    integration_tuple = tuple(sorted(all_rows, key=lambda item: item.job_id))
    rebuilt_integration = cast(
        v206_models.ScriptedIntegrationAudit,
        _make(
            v206_models.ScriptedIntegrationAudit,
            {
                "execution_contract_id": execution.contract_id,
                "callsite_census_id": rebuilt_census.census_id,
                "rows": integration_tuple,
            },
            "audit_id",
            "finance_v26_206_scripted_full_condition_integration_audit:",
        ),
    )
    saved_census = v206_models.RepairedCallsiteCensus.model_validate(
        targets["repaired_callsite_census.json"]
    )
    saved_integration = v206_models.ScriptedIntegrationAudit.model_validate(
        targets["scripted_integration_audit.json"]
    )
    if rebuilt_census.model_dump(mode="json") != saved_census.model_dump(
        mode="json"
    ) or rebuilt_integration.model_dump(mode="json") != saved_integration.model_dump(mode="json"):
        _fail("A4.match", "independent replay differs from v26.206")
    independent_calls = tuple(
        cast(
            models.IndependentCallsiteRow,
            _make(
                models.IndependentCallsiteRow,
                {
                    "source_coordinate_id": row.source_v193_coordinate_id,
                    "source_v194_job_id": row.source_v194_job_id,
                    "fresh_job_id": row.fresh_job_id,
                    "phase": row.phase,
                    "rebuilt_v206_callsite_row_id": row.row_id,
                    "rebuilt_prompt_id": row.repaired_prompt_id,
                    "rebuilt_request_id": row.request_id,
                    "canonical_message_sha256": row.canonical_messages_sha256,
                    "canonical_request_sha256": row.canonical_request_body_sha256,
                },
                "row_id",
                "finance_v26_207_independent_callsite_row:",
            ),
        )
        for row in call_tuple
    )
    callsite_audit = cast(
        models.IndependentCallsiteReconstructionAudit,
        _make(
            models.IndependentCallsiteReconstructionAudit,
            {
                "freeze_id": freeze_id,
                "route_audit_id": route_id,
                "rows": independent_calls,
            },
            "audit_id",
            "finance_v26_207_independent_callsite_reconstruction_audit:",
        ),
    )
    independent_rows = tuple(
        cast(
            models.IndependentReplayRow,
            _make(
                models.IndependentReplayRow,
                {
                    "job_id": row.job_id,
                    "source_v194_job_id": row.source_v194_job_id,
                    "callsite_count": len(row.callsite_row_ids),
                    "correction_count": row.correction_count,
                    "rebuilt_raw_id": row.raw_id,
                    "rebuilt_result_id": row.result_id,
                    "rebuilt_trace_id": row.trace_id,
                    "rebuilt_outcome_id": row.outcome_id,
                    "saved_integration_row_id": row.row_id,
                },
                "row_id",
                "finance_v26_207_independent_replay_row:",
            ),
        )
        for row in integration_tuple
    )
    replay_audit = cast(
        models.IndependentScriptedReplayAudit,
        _make(
            models.IndependentScriptedReplayAudit,
            {
                "freeze_id": freeze_id,
                "callsite_reconstruction_audit_id": callsite_audit.audit_id,
                "rows": independent_rows,
            },
            "audit_id",
            "finance_v26_207_independent_scripted_replay_audit:",
        ),
    )
    return callsite_audit, replay_audit, probes


def _controls(
    freeze_id: str,
    execution_id: str,
    profile: v206_models.FullConditionRepairProfile,
    probes: dict[str, Any],
    targets: dict[str, Any],
) -> models.IndependentFailureControlAudit:
    state_id, action_id, candidates = probes["action"]
    correction_state, correction_action = probes["correction"]
    result, prepared = probes["final"]
    try:
        parse_exact_canonical_action_payload(
            {
                "state_id": state_id,
                "action_id": action_id,
                "decision_kind": profile.decision_kind_value,
            }
        )
    except SemanticActionResponseRejection:
        pass
    else:
        _fail("A4.control.first", "invalid first ABI crossed parser")
    unknown = "f" * 24
    if unknown in candidates:
        _fail("A4.control.unknown", "unknown Action collided")
    parsed = parse_exact_canonical_action_payload(
        {
            "state_id": state_id,
            "action_id": unknown,
            "decision_kind": profile.decision_kind_value,
            "protocol": profile.protocol_value,
        }
    )
    if parsed.action_id in candidates:
        _fail("A4.control.unknown", "unknown Action became current")
    try:
        parse_exact_canonical_action_payload(
            {
                "state_id": correction_state,
                "action_id": correction_action,
                "decision_kind": profile.decision_kind_value,
            }
        )
    except SemanticActionResponseRejection:
        pass
    else:
        _fail("A4.control.correction", "invalid Correction ABI crossed parser")
    terminal_state_id = canonical_hash(
        tuple(item.observation.receipt_id for item in result.steps),
        prefix="capability_job_bound_terminal_state:",
    )
    envelope = make_qualified_final_host_envelope(
        grammar=prepared.final_grammar,
        terminal_state_id=terminal_state_id,
        terminal_commit_id=result.result_id,
    )
    try:
        parse_qualified_final_response({}, grammar=prepared.final_grammar, envelope=envelope)
    except (ValidationError, ValueError):
        pass
    else:
        _fail("A4.control.final", "invalid Final ABI crossed parser")
    definitions = (
        ("invalid_first_action_abi", "first_action_parser", "first_response_abi_invalid"),
        ("unknown_action_reference", "first_action_reference", "first_action_reference_invalid"),
        ("invalid_correction_abi", "correction_parser", "correction_response_abi_invalid"),
        ("invalid_final_abi", "final_parser", "final_response_abi_invalid"),
        ("typed_outer_terminal", "outer_terminal_projection", "instrument_failure"),
    )
    old_controls = tuple(
        cast(
            v206_models.FailureControl,
            _make(
                v206_models.FailureControl,
                {
                    "control_name": name,
                    "target_stage": stage,
                    "expected_terminal": terminal,
                    "observed_terminal": terminal,
                    "verifier_invoked": False,
                },
                "control_id",
                "finance_v26_206_failure_control:",
            ),
        )
        for name, stage, terminal in definitions
    )
    old_audit = cast(
        v206_models.FailureControlAudit,
        _make(
            v206_models.FailureControlAudit,
            {"execution_contract_id": execution_id, "controls": old_controls},
            "audit_id",
            "finance_v26_206_failure_control_audit:",
        ),
    )
    saved = v206_models.FailureControlAudit.model_validate(targets["failure_control_audit.json"])
    if old_audit.model_dump(mode="json") != saved.model_dump(mode="json"):
        _fail("A4.control.match", "failure control reconstruction differs")
    controls = tuple(
        cast(
            models.IndependentFailureControl,
            _make(
                models.IndependentFailureControl,
                {
                    "control_name": item.control_name,
                    "expected_terminal": item.expected_terminal,
                    "observed_terminal": item.observed_terminal,
                },
                "control_id",
                "finance_v26_207_independent_failure_control:",
            ),
        )
        for item in old_controls
    )
    return cast(
        models.IndependentFailureControlAudit,
        _make(
            models.IndependentFailureControlAudit,
            {"freeze_id": freeze_id, "controls": controls},
            "audit_id",
            "finance_v26_207_independent_failure_control_audit:",
        ),
    )


def _boundary(
    freeze_id: str,
    execution: v206_models.RepairedExecutionContract,
    manifest: v206_models.RepairedDevelopmentManifest,
    targets: dict[str, Any],
) -> models.EstimandResourceBoundaryAudit:
    estimand = cast(
        v206_models.ProspectiveEstimandContract,
        _make(
            v206_models.ProspectiveEstimandContract,
            {"execution_contract_id": execution.contract_id, "manifest_id": manifest.manifest_id},
            "contract_id",
            "fresh_repaired_full_condition_prospective_estimand_contract:",
        ),
    )
    saved = v206_models.ProspectiveEstimandContract.model_validate(
        targets["prospective_estimand_contract.json"]
    )
    if estimand.model_dump(mode="json") != saved.model_dump(mode="json"):
        _fail("A5.estimand", "Estimand Contract differs")
    return cast(
        models.EstimandResourceBoundaryAudit,
        _make(
            models.EstimandResourceBoundaryAudit,
            {"freeze_id": freeze_id, "reconstructed_estimand_contract_id": estimand.contract_id},
            "audit_id",
            "finance_v26_207_estimand_resource_boundary_audit:",
        ),
    )


def _source(value: tuple[str, str]) -> models.SourceIdentity:
    return cast(
        models.SourceIdentity,
        _make(
            models.SourceIdentity,
            {
                "source_commit": value[0],
                "source_tree": value[1],
                "implementation_files": IMPLEMENTATION_FILES,
            },
            "source_identity_id",
            "finance_v26_207_source_identity:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_audit_path: Path,
    source_identity: tuple[str, str],
) -> models.IndependentAuditReport:
    if output_dir.exists():
        raise FileExistsError(f"v26.207 output exists:{output_dir}")
    authorization, audit_bytes = _authorization(external_audit_path)
    targets = _targets(repository_root)
    freeze = _freeze(authorization.authorization_id, targets)
    detached, source_bytes, model_bytes = _detached_rebuild(repository_root, freeze.freeze_id)
    saved_census = v206_models.RepairedCallsiteCensus.model_validate(
        targets["repaired_callsite_census.json"]
    )
    route = _route(freeze.freeze_id, saved_census, source_bytes, model_bytes)
    parent, profile, manifest, execution, source_manifest, evidence = _parent_chain(
        repository_root, freeze.freeze_id, targets
    )
    callsites, replay, probes = _replay(
        repository_root,
        freeze.freeze_id,
        route.audit_id,
        execution,
        manifest,
        source_manifest,
        evidence,
        profile,
        targets,
    )
    controls = _controls(freeze.freeze_id, execution.contract_id, profile, probes, targets)
    boundary = _boundary(freeze.freeze_id, execution, manifest, targets)
    gates = cast(
        models.IndependentAuditGateEvaluation,
        _make(
            models.IndependentAuditGateEvaluation,
            {
                "freeze_id": freeze.freeze_id,
                "detached_rebuild_audit_id": detached.audit_id,
                "parent_reconstruction_audit_id": parent.audit_id,
                "route_no_bypass_audit_id": route.audit_id,
                "callsite_reconstruction_audit_id": callsites.audit_id,
                "scripted_replay_audit_id": replay.audit_id,
                "failure_control_audit_id": controls.audit_id,
                "boundary_audit_id": boundary.audit_id,
            },
            "evaluation_id",
            "finance_v26_207_independent_audit_gate_evaluation:",
        ),
    )
    decision = cast(
        models.IndependentAuditDecision,
        _make(
            models.IndependentAuditDecision,
            {
                "authorization_id": authorization.authorization_id,
                "gate_evaluation_id": gates.evaluation_id,
                "route_no_bypass_audit_id": route.audit_id,
            },
            "decision_id",
            "finance_v26_207_independent_audit_decision:",
        ),
    )
    transition = cast(
        models.BlockedTransition,
        _make(
            models.BlockedTransition,
            {"decision_id": decision.decision_id},
            "transition_id",
            "finance_v26_207_blocked_transition:",
        ),
    )
    source = _source(source_identity)
    report = cast(
        models.IndependentAuditReport,
        _make(
            models.IndependentAuditReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "freeze_id": freeze.freeze_id,
                "detached_rebuild_audit_id": detached.audit_id,
                "parent_reconstruction_audit_id": parent.audit_id,
                "route_no_bypass_audit_id": route.audit_id,
                "callsite_reconstruction_audit_id": callsites.audit_id,
                "scripted_replay_audit_id": replay.audit_id,
                "failure_control_audit_id": controls.audit_id,
                "boundary_audit_id": boundary.audit_id,
                "gate_evaluation_id": gates.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
                "source_identity_id": source.source_identity_id,
            },
            "report_id",
            "finance_v26_207_independent_audit_report:",
        ),
    )
    payloads = {
        "external_audit.txt": audit_bytes,
        "external_authorization.json": _bytes(authorization),
        "v206_preflight_freeze.json": _bytes(freeze),
        "detached_source_rebuild_audit.json": _bytes(detached),
        "independent_parent_reconstruction_audit.json": _bytes(parent),
        "source_route_no_bypass_audit.json": _bytes(route),
        "independent_callsite_reconstruction_audit.json": _bytes(callsites),
        "independent_scripted_replay_audit.json": _bytes(replay),
        "independent_failure_control_audit.json": _bytes(controls),
        "estimand_resource_boundary_audit.json": _bytes(boundary),
        "independent_audit_gate_evaluation.json": _bytes(gates),
        "decision.json": _bytes(decision),
        "blocked_transition.json": _bytes(transition),
        "source_identity.json": _bytes(source),
        "report.json": _bytes(report),
    }
    artifact = models.artifact_manifest(RUN_ID, payloads)
    payloads["artifact_manifest.json"] = _bytes(artifact)
    for name, payload in sorted(payloads.items()):
        _write(output_dir / name, payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    report = build(
        repository_root=args.repository_root.resolve(),
        output_dir=args.output_dir.resolve(),
        external_audit_path=args.external_audit.resolve(),
        source_identity=(args.source_commit, args.source_tree),
    )
    print(models.canonical_bytes(report).decode())


if __name__ == "__main__":
    main()
