# ruff: noqa: E501, SLF001
from __future__ import annotations

import argparse
import copy
import hashlib
import json
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
    phase1_v26_fresh_first_response_action_interface_disambiguation_paired_postrun_independent_audit_models as v205_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight_models as models,
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
    "finance_v26_206_fresh_repaired_action_interface_full_condition_"
    "integration_preflight_v1_20260902"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_AUDIT_SHA256: Final = "b0ab58a19818e7a5086bbc0b7ffa03768d1148d9c441093407c43184c9c6fd59"
EXTERNAL_AUDIT_BYTES: Final = 14_288
V205_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_205_fresh_first_response_action_interface_disambiguation_"
    "paired_online_calibration_postrun_independent_audit_v1_20260902"
)
V203_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_203_fresh_first_response_action_interface_disambiguation_"
    "stratified_calibration_population_preflight_v1_20260902"
)
V194_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_194_authoritative_execution_kernel_parent_preflight_v1_20260901"
)
V193_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_193_json_prompt_authority_repair_preflight_v2_20260901"
)
V192_GENERATION_PROFILE: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_192_json_explicit_prompt_contract_preflight_v1_20260831/"
    "json_explicit_generation_profile.json"
)
MODEL_PROFILE: Final = (
    "trusted_data_synthesis/config/deepseek_v4_flash_agent_two_stage_stage1_thinking_16k_v1.json"
)
V194_PACKAGE_CATALOG_ID: Final = (
    "authoritative_kernel_package_catalog:"
    "cd7bee78c7ed7bc618d7b4d6441546264d1a6392336dceedee9abb89ea7e7211"
)
V194_MANIFEST_ID: Final = (
    "authoritative_kernel_manifest:15da508affe0a4727f85fbc727ac1a4b6772b014fdb6a40d4e5c93ae374cd803"
)
V194_RUNNER_ID: Final = (
    "authoritative_execution_kernel_runner:"
    "7a3b8ae6bfb178c351f10a00c08c18373ee61f0bf64b500f245644cc99e1e034"
)
V194_EXECUTION_CONTRACT_ID: Final = (
    "authoritative_execution_kernel_contract:"
    "53dccfcd1a4516ae8c79c9b64cd41193b99e8594598a25049335db565070786d"
)
V194_RESOURCE_CONTRACT_ID: Final = (
    "authoritative_kernel_resource_persistence_contract:"
    "ba6fb7967c3429d05184cc7a3ddc619187bf28ea438cc1b46bd66ce6a21055b4"
)
V193_EVIDENCE_SET_ID: Final = (
    "json_explicit_exact_prompt_evidence_set:"
    "4982ca86b6a5862c0bed33cee02bfb5a2085d4d60a6c0495b09d548584f9a371"
)
V203_ACTION_CONTRACT_ID: Final = (
    "fresh_first_response_exact_action_interface_contract:"
    "a95252bf3ce3d3c510636034f151eb5c8f219ee42c6e09f0fd8848f58bd0ffc1"
)
IMPLEMENTATION_FILES: Final = tuple(
    sorted(
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_v26_fresh_repaired_action_interface_full_condition_integration_preflight_models.py",
            "trusted_data_synthesis/tests/"
            "test_v26_fresh_repaired_action_interface_full_condition_integration_preflight.py",
        )
    )
)


class V206Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V206Error(stage, reason)


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def _file_bytes(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()


def _recursive_key_count(value: Any, target: str) -> int:
    if isinstance(value, dict):
        return int(target in value) + sum(
            _recursive_key_count(item, target) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return sum(_recursive_key_count(item, target) for item in value)
    return 0


def _authorization(
    external_audit_path: Path,
) -> tuple[models.ExternalPreflightAuthorization, bytes]:
    payload = external_audit_path.read_bytes()
    if len(payload) != EXTERNAL_AUDIT_BYTES or _sha256_bytes(payload) != EXTERNAL_AUDIT_SHA256:
        _fail("authorization", "v26.206 external Audit bytes differ")
    authorization = cast(
        models.ExternalPreflightAuthorization,
        models.make_identity(
            models.ExternalPreflightAuthorization,
            {
                "audit_sha256": _sha256_bytes(payload),
                "audit_byte_count": len(payload),
            },
            field="authorization_id",
            prefix="finance_v26_206_external_preflight_authorization:",
        ),
    )
    return authorization, payload


def _verify_self_excluding_manifest(
    root: Path,
    manifest: Any,
    *,
    manifest_name: str = "artifact_manifest.json",
) -> tuple[int, int]:
    actual_files = tuple(sorted(path for path in root.iterdir() if path.is_file()))
    members = tuple(manifest.members)
    if {item.relative_path for item in members} != {
        path.name for path in actual_files if path.name != manifest_name
    }:
        _fail("freeze.path_set", f"formal directory path set differs:{root.name}")
    for member in members:
        payload = (root / member.relative_path).read_bytes()
        if len(payload) != member.byte_count or _sha256_bytes(payload) != member.sha256:
            _fail("freeze.member_bytes", f"formal member bytes differ:{member.relative_path}")
    return len(actual_files), sum(path.stat().st_size for path in actual_files)


def _predecessor_freeze(
    *,
    repository_root: Path,
    authorization_id: str,
) -> tuple[
    models.PredecessorFreeze,
    v194_models.AuthoritativeRunnerPackageCatalog,
    v194_models.AuthoritativeDevelopmentManifest,
    v194_models.AuthoritativeRunnerContract,
    v194_models.AuthoritativeExecutionContract,
    v194_models.KernelResourcePersistenceContract,
    v193_models.ExactPromptEvidenceSet,
    v203_models.ExactActionInterfaceContract,
]:
    v205_root = repository_root / V205_DIR
    v205_manifest = v205_models.ArtifactManifest.model_validate(
        _load(v205_root / "artifact_manifest.json")
    )
    file_count, total_bytes = _verify_self_excluding_manifest(v205_root, v205_manifest)
    if (file_count, total_bytes) != (14, 91_230):
        _fail("freeze.v205_geometry", "v26.205 formal directory geometry differs")
    v205_report = _load(v205_root / "report.json")
    v205_decision = v205_models.PostrunIndependentAuditDecision.model_validate(
        _load(v205_root / "decision.json")
    )
    v205_transition = v205_models.ProspectiveTransition.model_validate(
        _load(v205_root / "prospective_transition.json")
    )
    if v205_transition.next_stage != models.CONSUMED_STAGE:
        _fail("freeze.v205_transition", "v26.205 does not authorize the consumed stage")

    v194_root = repository_root / V194_DIR
    package_catalog = v194_models.AuthoritativeRunnerPackageCatalog.model_validate(
        _load(v194_root / "authoritative_runner_package_catalog.json")
    )
    manifest = v194_models.AuthoritativeDevelopmentManifest.model_validate(
        _load(v194_root / "authoritative_development_manifest.json")
    )
    runner = v194_models.AuthoritativeRunnerContract.model_validate(
        _load(v194_root / "authoritative_runner_contract.json")
    )
    execution = v194_models.AuthoritativeExecutionContract.model_validate(
        _load(v194_root / "authoritative_execution_contract.json")
    )
    resource = v194_models.KernelResourcePersistenceContract.model_validate(
        _load(v194_root / "kernel_resource_persistence_contract.json")
    )
    if (
        package_catalog.catalog_id != V194_PACKAGE_CATALOG_ID
        or manifest.manifest_id != V194_MANIFEST_ID
        or runner.runner_id != V194_RUNNER_ID
        or execution.contract_id != V194_EXECUTION_CONTRACT_ID
        or resource.contract_id != V194_RESOURCE_CONTRACT_ID
    ):
        _fail("freeze.v194_identity", "v26.194 full-condition identity chain differs")
    evidence = v193_models.ExactPromptEvidenceSet.model_validate(
        _load(repository_root / V193_DIR / "exact_prompt_evidence_set.json")
    )
    action_contract = v203_models.ExactActionInterfaceContract.model_validate(
        _load(repository_root / V203_DIR / "exact_action_interface_contract.json")
    )
    if evidence.evidence_set_id != V193_EVIDENCE_SET_ID:
        _fail("freeze.v193_evidence", "v26.193 exact Prompt evidence identity differs")
    if action_contract.contract_id != V203_ACTION_CONTRACT_ID:
        _fail("freeze.v203_contract", "v26.203 Action Contract identity differs")
    freeze = cast(
        models.PredecessorFreeze,
        models.make_identity(
            models.PredecessorFreeze,
            {
                "authorization_id": authorization_id,
                "v205_report_content_sha256": models.canonical_sha256(v205_report),
                "v205_decision_id": v205_decision.decision_id,
                "v205_transition_id": v205_transition.transition_id,
                "v205_artifact_manifest_id": v205_manifest.manifest_id,
                "v205_artifact_root": v205_manifest.artifact_root,
                "v205_source_commit": "76a2d00bc9b1517da659eda901b9dff8f3389aa0",
                "v205_source_tree": "c78ad15bf191a98f085cc76deaf0f35f68c2e9a9",
                "v205_manifest_member_match_count": len(v205_manifest.members),
                "v194_package_catalog_id": package_catalog.catalog_id,
                "v194_manifest_id": manifest.manifest_id,
                "v194_runner_id": runner.runner_id,
                "v194_execution_contract_id": execution.contract_id,
                "v194_resource_contract_id": resource.contract_id,
                "v193_prompt_evidence_set_id": evidence.evidence_set_id,
                "v203_action_contract_id": action_contract.contract_id,
            },
            field="freeze_id",
            prefix="finance_v26_206_predecessor_freeze:",
        ),
    )
    return freeze, package_catalog, manifest, runner, execution, resource, evidence, action_contract


def _repair_profile(
    authorization_id: str,
    freeze_id: str,
    contract: v203_models.ExactActionInterfaceContract,
) -> models.FullConditionRepairProfile:
    return cast(
        models.FullConditionRepairProfile,
        models.make_identity(
            models.FullConditionRepairProfile,
            {
                "authorization_id": authorization_id,
                "predecessor_freeze_id": freeze_id,
                "source_v203_action_contract_id": contract.contract_id,
                "frozen_action_grammar_id": contract.frozen_action_grammar_id,
                "exact_required_fields": contract.required_fields,
                "exact_allowed_fields": contract.allowed_fields,
                "decision_kind_value": contract.decision_kind_value,
                "protocol_value": contract.protocol_value,
            },
            field="profile_id",
            prefix="fresh_repaired_action_interface_full_condition_profile:",
        ),
    )


def _fresh_identity_chain(
    *,
    profile: models.FullConditionRepairProfile,
    source_catalog: v194_models.AuthoritativeRunnerPackageCatalog,
    source_manifest: v194_models.AuthoritativeDevelopmentManifest,
    source_runner: v194_models.AuthoritativeRunnerContract,
    source_execution: v194_models.AuthoritativeExecutionContract,
    final_grammar_id: str,
) -> tuple[
    models.RepairedRunnerPackageCatalog,
    models.RepairedDevelopmentManifest,
    models.RepairedRunnerContract,
    models.RepairedExecutionContract,
]:
    packages = tuple(
        cast(
            models.RepairedRunnerPackage,
            models.make_identity(
                models.RepairedRunnerPackage,
                {
                    "source_v194_package_id": source.package_id,
                    "source_v194_package_sha256": models.canonical_sha256(source),
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
                field="package_id",
                prefix="fresh_repaired_full_condition_runner_package:",
            ),
        )
        for source in sorted(source_catalog.packages, key=lambda item: item.package_id)
    )
    catalog = cast(
        models.RepairedRunnerPackageCatalog,
        models.make_identity(
            models.RepairedRunnerPackageCatalog,
            {
                "repair_profile_id": profile.profile_id,
                "packages": packages,
                "source_v194_package_ids": tuple(
                    sorted(item.source_v194_package_id for item in packages)
                ),
            },
            field="catalog_id",
            prefix="fresh_repaired_full_condition_package_catalog:",
        ),
    )
    fresh_package_by_source = {item.source_v194_package_id: item for item in catalog.packages}
    jobs: list[models.RepairedDevelopmentJob] = []
    for source in sorted(source_manifest.jobs, key=lambda item: item.job_id):
        package = fresh_package_by_source[source.package_id]
        parent = {
            "source_v194_job_id": source.job_id,
            "package_id": package.package_id,
            "repair_profile_id": profile.profile_id,
            "replica_index": source.replica_index,
        }
        jobs.append(
            cast(
                models.RepairedDevelopmentJob,
                models.make_identity(
                    models.RepairedDevelopmentJob,
                    {
                        **parent,
                        "source_v194_job_sha256": models.canonical_sha256(source),
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
                    field="job_id",
                    prefix="fresh_repaired_full_condition_development_job:",
                ),
            )
        )
    job_tuple = tuple(jobs)
    manifest = cast(
        models.RepairedDevelopmentManifest,
        models.make_identity(
            models.RepairedDevelopmentManifest,
            {
                "package_catalog_id": catalog.catalog_id,
                "repair_profile_id": profile.profile_id,
                "jobs": job_tuple,
                "expected_job_ids": tuple(sorted(item.job_id for item in job_tuple)),
                "source_v194_job_ids": tuple(sorted(item.source_v194_job_id for item in job_tuple)),
            },
            field="manifest_id",
            prefix="fresh_repaired_full_condition_manifest:",
        ),
    )
    runner = cast(
        models.RepairedRunnerContract,
        models.make_identity(
            models.RepairedRunnerContract,
            {
                "manifest_id": manifest.manifest_id,
                "package_catalog_id": catalog.catalog_id,
                "repair_profile_id": profile.profile_id,
                "source_v194_runner_id": source_runner.runner_id,
            },
            field="runner_id",
            prefix="fresh_repaired_full_condition_runner:",
        ),
    )
    execution = cast(
        models.RepairedExecutionContract,
        models.make_identity(
            models.RepairedExecutionContract,
            {
                "runner_id": runner.runner_id,
                "manifest_id": manifest.manifest_id,
                "package_catalog_id": catalog.catalog_id,
                "repair_profile_id": profile.profile_id,
                "source_v194_execution_contract_id": source_execution.contract_id,
                "resource_contract_id": V194_RESOURCE_CONTRACT_ID,
            },
            field="contract_id",
            prefix="fresh_repaired_full_condition_execution_contract:",
        ),
    )
    return catalog, manifest, runner, execution


def _repaired_messages(
    *,
    core: dict[str, Any],
    prompt_kind: str,
    profile: models.FullConditionRepairProfile,
) -> tuple[tuple[dict[str, str], ...], str, tuple[str, ...]]:
    public = copy.deepcopy(core["public_prompt"])
    semantic = public["task"]["semantic_task"]
    answer_fields = semantic.pop("answer_fields")
    operator_output_fields = semantic.pop("operator_output_fields")
    candidates = tuple(item["action_id"] for item in public["candidates"])
    state_id = public["state"]["state_token"]
    verifier_metadata = {
        "answer_fields": answer_fields,
        "classification": "verifier_internal_task_metadata_not_model_response_schema",
        "model_response_schema": False,
        "operator_output_fields": operator_output_fields,
    }
    system_payload = {
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
        "instruction": (
            "Return exactly one JSON object conforming only to the authoritative four-field "
            "Action response contract. Do not answer the task directly and do not emit any "
            "additional field or wrapper."
        ),
    }
    user_payload = {
        "interface_profile": "disambiguated_action_interface_full_condition",
        "prompt_kind": prompt_kind,
        "public_prompt": public,
        "response_contract_location": "system_message_only",
        "verifier_internal_task_metadata": verifier_metadata,
    }
    repair_counts = {
        "response_abi": _recursive_key_count(user_payload, "response_abi"),
        "user_grammar_id": _recursive_key_count(user_payload, "grammar_id"),
        "system_grammar_id": _recursive_key_count(system_payload, "grammar_id"),
    }
    if (
        repair_counts
        != {
            "response_abi": 0,
            "user_grammar_id": 0,
            "system_grammar_id": 0,
        }
        or any(
            key in user_payload["public_prompt"]["task"]["semantic_task"]
            for key in ("answer_fields", "operator_output_fields")
        )
        or set(verifier_metadata)
        != {
            "answer_fields",
            "classification",
            "model_response_schema",
            "operator_output_fields",
        }
    ):
        _fail(
            "interface.repair",
            f"v26.206 repaired model-visible projection differs:{repair_counts}",
        )
    messages = (
        {"role": "system", "content": models.canonical_bytes(system_payload).decode()},
        {"role": "user", "content": models.canonical_bytes(user_payload).decode()},
    )
    return messages, state_id, candidates


def _callsite_row(
    *,
    source_row: v193_models.ProviderRequestEvidenceRow,
    source_v194_job_id: str,
    fresh_job_id: str,
    core: dict[str, Any],
    config: AgentModelConfig,
    profile: models.FullConditionRepairProfile,
    final_grammar_id: str,
) -> models.RepairedCallsiteRow:
    coordinate = source_row.coordinate
    if models.canonical_sha256(core) != source_row.prompt_core_sha256:
        _fail("callsite.source_core", "Runtime Prompt core differs from v26.193 evidence")
    if coordinate.phase == "final":
        source_body = json.loads(source_row.request_body_canonical_json)
        messages = tuple(source_body["messages"])
        request_body = source_body
        state_id = coordinate.state_token
        candidates: tuple[str, ...] = ()
        parser_id = "prospective_qualified_final_response_grammar.parse_qualified_final_response"
        grammar_id = final_grammar_id
        exact_action = False
    else:
        messages, state_id, candidates = _repaired_messages(
            core=core,
            prompt_kind=coordinate.prompt_kind,
            profile=profile,
        )
        request_body = make_stage_one_request_body(config, messages[-1]["content"])
        request_body["messages"] = [dict(item) for item in messages]
        parser_id = (
            "prospective_semantic_action_response_grammar.parse_exact_canonical_action_payload"
        )
        grammar_id = profile.frozen_action_grammar_id
        exact_action = True
    message_bytes = models.canonical_bytes(messages)
    body_bytes = models.canonical_bytes(request_body)
    prompt_id = canonical_hash(
        {
            "fresh_job_id": fresh_job_id,
            "source_v193_coordinate_id": coordinate.coordinate_id,
            "canonical_messages_sha256": _sha256_bytes(message_bytes),
            "repair_profile_id": profile.profile_id,
        },
        prefix="fresh_repaired_full_condition_prompt:",
    )
    request_id = canonical_hash(
        {
            "fresh_job_id": fresh_job_id,
            "repaired_prompt_id": prompt_id,
            "canonical_request_body_sha256": _sha256_bytes(body_bytes),
        },
        prefix="fresh_repaired_full_condition_request:",
    )
    return cast(
        models.RepairedCallsiteRow,
        models.make_identity(
            models.RepairedCallsiteRow,
            {
                "source_v193_evidence_row_id": source_row.row_id,
                "source_v193_coordinate_id": coordinate.coordinate_id,
                "source_v194_job_id": source_v194_job_id,
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
                "canonical_messages_sha256": _sha256_bytes(message_bytes),
                "canonical_messages_byte_count": len(message_bytes),
                "canonical_request_body_sha256": _sha256_bytes(body_bytes),
                "canonical_request_body_byte_count": len(body_bytes),
                "repair_profile_id": profile.profile_id,
                "parser_id": parser_id,
                "grammar_id": grammar_id,
                "exact_four_field_action_contract": exact_action,
            },
            field="row_id",
            prefix="fresh_repaired_full_condition_callsite_row:",
        ),
    )


def _reference_action_payload(
    *,
    state_id: str,
    action_id: str,
    profile: models.FullConditionRepairProfile,
) -> str:
    proposal = parse_exact_canonical_action_payload(
        {
            "state_id": state_id,
            "action_id": action_id,
            "decision_kind": profile.decision_kind_value,
            "protocol": profile.protocol_value,
        }
    )
    if proposal.state_id != state_id or proposal.action_id != action_id:
        _fail("integration.action_parser", "exact Action parser crossed current State")
    return proposal.action_id


def _scripted_integration(
    *,
    repository_root: Path,
    execution: models.RepairedExecutionContract,
    manifest: models.RepairedDevelopmentManifest,
    source_manifest: v194_models.AuthoritativeDevelopmentManifest,
    evidence: v193_models.ExactPromptEvidenceSet,
    profile: models.FullConditionRepairProfile,
) -> tuple[
    models.RepairedCallsiteCensus,
    models.ScriptedIntegrationAudit,
    dict[str, Any],
]:
    package_root = repository_root / "trusted_data_synthesis"
    config = AgentModelConfig.model_validate(_load(repository_root / MODEL_PROFILE)["model"])
    source_v194_by_id = {item.job_id: item for item in source_manifest.jobs}
    source_rows_by_v193_job: dict[str, list[v193_models.ProviderRequestEvidenceRow]] = defaultdict(
        list
    )
    for row in evidence.rows:
        source_rows_by_v193_job[row.coordinate.fresh_job_id].append(row)
    new_job_by_source = {item.source_v194_job_id: item for item in manifest.jobs}
    if set(new_job_by_source) != set(source_v194_by_id):
        _fail("integration.job_set", "v26.206 fresh Job source set differs")
    all_callsites: list[models.RepairedCallsiteRow] = []
    integration_rows: list[models.ScriptedIntegrationRow] = []
    probes: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="v26-206-provider-forbidden-") as temporary:
        prepared = v188.prepare_execution(
            package_root=package_root,
            output_dir=Path(temporary) / "provider_invocation_forbidden",
        )
        if prepared.profile.action_grammar_id != profile.frozen_action_grammar_id:
            _fail(
                "integration.action_grammar", "frozen Action Grammar differs from Repair Contract"
            )
        old_source_jobs = {item.job_id: item for item in prepared.frozen.manifest.jobs}
        for source_v194_id in sorted(source_v194_by_id):
            source_v194 = source_v194_by_id[source_v194_id]
            fresh = new_job_by_source[source_v194_id]
            source_rows = tuple(
                sorted(
                    source_rows_by_v193_job[source_v194.source_job_id],
                    key=lambda item: item.coordinate.invocation_index,
                )
            )
            if not source_rows:
                _fail("integration.prompt_parent", "v26.194 Job lacks v26.193 Prompt rows")
            old_job_id = source_rows[0].coordinate.source_job_id
            if any(item.coordinate.source_job_id != old_job_id for item in source_rows):
                _fail("integration.prompt_parent", "one v26.194 Job crosses old source Jobs")
            old_source = old_source_jobs[old_job_id]
            context = frozen_runtime.prepare_job(old_source, prepared.runtime_catalog)
            state = frozen_runtime._initialize(context)
            source_by_key = {
                (
                    item.coordinate.phase,
                    item.coordinate.state_token,
                    item.coordinate.rejected_action_id,
                    item.coordinate.rejection_receipt_id,
                ): item
                for item in source_rows
            }
            job_callsites: list[models.RepairedCallsiteRow] = []
            action_count = 0
            subsequent_count = 0
            correction_count = 0
            while state.current_index < len(state.ordered_components):
                component_index = state.current_index
                prompt = step_runtime.render_next_prompt(state)
                dispositions = frozen_runtime._candidate_dispositions(state, prompt)
                phase = "first_action" if component_index == 0 else "subsequent_action"
                key = (phase, prompt.state.state_token, None, None)
                source_row = source_by_key.get(key)
                if source_row is None:
                    _fail("integration.callsite", "registered Action callsite is absent")
                core = v193._action_core(prompt, prepared)
                callsite = _callsite_row(
                    source_row=source_row,
                    source_v194_job_id=source_v194_id,
                    fresh_job_id=fresh.job_id,
                    core=core,
                    config=config,
                    profile=profile,
                    final_grammar_id=prepared.profile.final_grammar_id,
                )
                job_callsites.append(callsite)
                all_callsites.append(callsite)
                selection = frozen_runtime._reference_selection(
                    state, prompt, dispositions, component_index
                )
                if selection.action_id is None:
                    _fail("integration.reference", "reference Action lacks an Action ID")
                action_id = _reference_action_payload(
                    state_id=prompt.state.state_token,
                    action_id=selection.action_id,
                    profile=profile,
                )
                if action_id not in {item.action_id for item in prompt.candidates}:
                    _fail(
                        "integration.reference",
                        "reference Action is absent from current Candidates",
                    )
                action_count += 1
                subsequent_count += int(component_index > 0)
                for invalid in (item for item in dispositions if not item.acceptance.accepted):
                    branch = copy.deepcopy(state)
                    rejected = step_runtime.step(branch, invalid.action_id)
                    receipt = v193._rejection_receipt(rejected)
                    correction_prompt = step_runtime.render_next_prompt(branch)
                    correction_rows = frozen_runtime._candidate_dispositions(
                        branch, correction_prompt
                    )
                    correction_selection = frozen_runtime._reference_correction(
                        branch,
                        correction_prompt,
                        correction_rows,
                        component_index,
                        invalid.action_id,
                    )
                    if correction_selection.action_id is None:
                        _fail("integration.correction", "reference Correction lacks an Action ID")
                    correction_key = (
                        "correction",
                        correction_prompt.state.state_token,
                        invalid.action_id,
                        receipt,
                    )
                    correction_source = source_by_key.get(correction_key)
                    if correction_source is None:
                        _fail("integration.correction", "registered Correction callsite is absent")
                    correction_core = v193._action_core(correction_prompt, prepared)
                    correction_callsite = _callsite_row(
                        source_row=correction_source,
                        source_v194_job_id=source_v194_id,
                        fresh_job_id=fresh.job_id,
                        core=correction_core,
                        config=config,
                        profile=profile,
                        final_grammar_id=prepared.profile.final_grammar_id,
                    )
                    job_callsites.append(correction_callsite)
                    all_callsites.append(correction_callsite)
                    corrected_action = _reference_action_payload(
                        state_id=correction_prompt.state.state_token,
                        action_id=correction_selection.action_id,
                        profile=profile,
                    )
                    if corrected_action not in {
                        item.action_id for item in correction_prompt.candidates
                    }:
                        _fail("integration.correction", "Correction references an absent Action")
                    corrected = step_runtime.step(branch, corrected_action)
                    if not getattr(corrected, "action_accepted", False):
                        _fail("integration.correction", "reference Correction did not commit")
                    correction_count += 1
                    probes.setdefault(
                        "correction",
                        (correction_prompt.state.state_token, correction_selection.action_id),
                    )
                committed = step_runtime.step(state, action_id)
                if not getattr(committed, "action_accepted", False):
                    _fail("integration.action", "reference Action did not commit")
                probes.setdefault(
                    "action",
                    (
                        prompt.state.state_token,
                        selection.action_id,
                        tuple(item.action_id for item in prompt.candidates),
                    ),
                )
            result = step_runtime.finalize(state)
            frozen_runtime._parse_final_fixture(
                result,
                context.source,
                grammar=prepared.final_grammar,
                profile=prepared.profile,
            )
            final_prompt, _ = v188.render_final_prompt(
                context=context,
                result=result,
                grammar=prepared.final_grammar,
            )
            final_source = source_by_key.get(("final", result.result_id, None, None))
            if final_source is None:
                _fail("integration.final", "registered Final callsite is absent")
            final_callsite = _callsite_row(
                source_row=final_source,
                source_v194_job_id=source_v194_id,
                fresh_job_id=fresh.job_id,
                core=final_prompt,
                config=config,
                profile=profile,
                final_grammar_id=prepared.profile.final_grammar_id,
            )
            job_callsites.append(final_callsite)
            all_callsites.append(final_callsite)
            if tuple(item.coordinate.invocation_index for item in source_rows) != tuple(
                item.invocation_index for item in job_callsites
            ):
                _fail("integration.order", "v26.206 callsite invocation order differs")
            if (
                not result.task_validity.base_valid
                or not result.mechanism_qualification.mechanism_semantically_qualified
                or not result.qualified_validity.qualified_valid
            ):
                _fail("integration.validity", "scripted reference trajectory is not Qualified")
            callsite_ids = tuple(item.row_id for item in job_callsites)
            raw_id = canonical_hash(
                {"job_id": fresh.job_id, "callsite_row_ids": callsite_ids},
                prefix="fresh_repaired_scripted_raw:",
            )
            result_id = canonical_hash(
                {"job_id": fresh.job_id, "raw_id": raw_id, "qualified_valid": True},
                prefix="fresh_repaired_scripted_result:",
            )
            trace_id = canonical_hash(
                {"job_id": fresh.job_id, "raw_id": raw_id, "result_id": result_id},
                prefix="fresh_repaired_scripted_trace:",
            )
            outcome_id = canonical_hash(
                {"job_id": fresh.job_id, "trace_id": trace_id, "qualified_valid": True},
                prefix="fresh_repaired_scripted_outcome:",
            )
            integration_rows.append(
                cast(
                    models.ScriptedIntegrationRow,
                    models.make_identity(
                        models.ScriptedIntegrationRow,
                        {
                            "job_id": fresh.job_id,
                            "source_v194_job_id": source_v194_id,
                            "callsite_row_ids": callsite_ids,
                            "subsequent_action_count": subsequent_count,
                            "typed_rejection_branch_count": correction_count,
                            "correction_count": correction_count,
                            "exact_action_parse_count": action_count,
                            "action_reference_and_state_valid_count": action_count,
                            "correction_reference_and_state_valid_count": correction_count,
                            "runtime_commit_count": action_count,
                            "raw_id": raw_id,
                            "result_id": result_id,
                            "trace_id": trace_id,
                            "outcome_id": outcome_id,
                        },
                        field="row_id",
                        prefix="finance_v26_206_scripted_integration_row:",
                    ),
                )
            )
            probes.setdefault("final", (result, context, prepared))
    callsite_tuple = tuple(sorted(all_callsites, key=lambda item: item.row_id))
    phase_counts = Counter(item.phase for item in callsite_tuple)
    census = cast(
        models.RepairedCallsiteCensus,
        models.make_identity(
            models.RepairedCallsiteCensus,
            {
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
                "repair_profile_id": profile.profile_id,
                "source_v193_evidence_set_id": evidence.evidence_set_id,
                "rows": callsite_tuple,
                "maximum_repaired_message_byte_count": max(
                    item.canonical_messages_byte_count for item in callsite_tuple
                ),
                "maximum_repaired_request_body_byte_count": max(
                    item.canonical_request_body_byte_count for item in callsite_tuple
                ),
            },
            field="census_id",
            prefix="finance_v26_206_repaired_callsite_census:",
        ),
    )
    if phase_counts != Counter(
        {"first_action": 192, "subsequent_action": 288, "correction": 120, "final": 192}
    ):
        _fail("integration.callsite_counts", "v26.206 callsite count differs")
    integration_tuple = tuple(sorted(integration_rows, key=lambda item: item.job_id))
    integration = cast(
        models.ScriptedIntegrationAudit,
        models.make_identity(
            models.ScriptedIntegrationAudit,
            {
                "execution_contract_id": execution.contract_id,
                "callsite_census_id": census.census_id,
                "rows": integration_tuple,
            },
            field="audit_id",
            prefix="finance_v26_206_scripted_full_condition_integration_audit:",
        ),
    )
    return census, integration, probes


def _failure_controls(
    *,
    execution_contract_id: str,
    profile: models.FullConditionRepairProfile,
    probes: dict[str, Any],
) -> models.FailureControlAudit:
    state_id, action_id, candidates = probes["action"]
    correction_state, correction_action = probes["correction"]
    result, _context, prepared = probes["final"]

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
        _fail("control.first_abi", "invalid first Action ABI crossed the exact parser")

    unknown_action = "f" * 24
    if unknown_action in candidates:
        _fail("control.unknown_reference", "unknown Action control collided with a Candidate")
    proposal = parse_exact_canonical_action_payload(
        {
            "state_id": state_id,
            "action_id": unknown_action,
            "decision_kind": profile.decision_kind_value,
            "protocol": profile.protocol_value,
        }
    )
    if proposal.action_id in candidates:
        _fail("control.unknown_reference", "unknown Action control became current")

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
        _fail("control.correction_abi", "invalid Correction ABI crossed the exact parser")

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
        _fail("control.final_abi", "invalid Final ABI crossed the exact parser")

    definitions = (
        (
            "invalid_first_action_abi",
            "first_action_parser",
            "first_response_abi_invalid",
            False,
        ),
        (
            "unknown_action_reference",
            "first_action_reference",
            "first_action_reference_invalid",
            False,
        ),
        (
            "invalid_correction_abi",
            "correction_parser",
            "correction_response_abi_invalid",
            False,
        ),
        (
            "invalid_final_abi",
            "final_parser",
            "final_response_abi_invalid",
            False,
        ),
        (
            "typed_outer_terminal",
            "outer_terminal_projection",
            "instrument_failure",
            False,
        ),
    )
    controls = tuple(
        cast(
            models.FailureControl,
            models.make_identity(
                models.FailureControl,
                {
                    "control_name": name,
                    "target_stage": stage,
                    "expected_terminal": terminal,
                    "observed_terminal": terminal,
                    "verifier_invoked": verifier,
                },
                field="control_id",
                prefix="finance_v26_206_failure_control:",
            ),
        )
        for name, stage, terminal, verifier in definitions
    )
    return cast(
        models.FailureControlAudit,
        models.make_identity(
            models.FailureControlAudit,
            {
                "execution_contract_id": execution_contract_id,
                "controls": controls,
            },
            field="audit_id",
            prefix="finance_v26_206_failure_control_audit:",
        ),
    )


def _source_identity(
    source_identity: tuple[str, str],
) -> models.SourceIdentity:
    commit, tree = source_identity
    return cast(
        models.SourceIdentity,
        models.make_identity(
            models.SourceIdentity,
            {
                "source_commit": commit,
                "source_tree": tree,
                "implementation_files": IMPLEMENTATION_FILES,
            },
            field="source_identity_id",
            prefix="finance_v26_206_source_identity:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_audit_path: Path,
    source_identity: tuple[str, str],
) -> models.PreflightReport:
    if output_dir.exists():
        raise FileExistsError(f"v26.206 output already exists:{output_dir}")
    authorization, audit_bytes = _authorization(external_audit_path)
    (
        freeze,
        source_catalog,
        source_manifest,
        source_runner,
        source_execution,
        _source_resource,
        evidence,
        action_contract,
    ) = _predecessor_freeze(
        repository_root=repository_root,
        authorization_id=authorization.authorization_id,
    )
    profile = _repair_profile(authorization.authorization_id, freeze.freeze_id, action_contract)
    final_grammar_id = _load(repository_root / V192_GENERATION_PROFILE)["final_grammar_id"]
    catalog, manifest, runner, execution = _fresh_identity_chain(
        profile=profile,
        source_catalog=source_catalog,
        source_manifest=source_manifest,
        source_runner=source_runner,
        source_execution=source_execution,
        final_grammar_id=final_grammar_id,
    )
    census, integration, probes = _scripted_integration(
        repository_root=repository_root,
        execution=execution,
        manifest=manifest,
        source_manifest=source_manifest,
        evidence=evidence,
        profile=profile,
    )
    controls = _failure_controls(
        execution_contract_id=execution.contract_id,
        profile=profile,
        probes=probes,
    )
    estimand = cast(
        models.ProspectiveEstimandContract,
        models.make_identity(
            models.ProspectiveEstimandContract,
            {
                "execution_contract_id": execution.contract_id,
                "manifest_id": manifest.manifest_id,
            },
            field="contract_id",
            prefix="fresh_repaired_full_condition_prospective_estimand_contract:",
        ),
    )
    old_ids = {
        *(item.package_id for item in source_catalog.packages),
        *(item.job_id for item in source_manifest.jobs),
        *(item.raw_namespace for item in source_manifest.jobs),
        *(item.result_namespace for item in source_manifest.jobs),
    }
    fresh_ids = {
        *(item.package_id for item in catalog.packages),
        *(item.job_id for item in manifest.jobs),
        *(item.raw_namespace for item in manifest.jobs),
        *(item.result_namespace for item in manifest.jobs),
        *(item.trace_namespace for item in manifest.jobs),
        *(item.outcome_namespace for item in manifest.jobs),
    }
    if old_ids & fresh_ids:
        _fail("gate.f1", "v26.206 fresh identity collides with a predecessor identity")
    gates = cast(
        models.FullConditionGateAudit,
        models.make_identity(
            models.FullConditionGateAudit,
            {
                "predecessor_freeze_id": freeze.freeze_id,
                "manifest_id": manifest.manifest_id,
                "callsite_census_id": census.census_id,
                "scripted_integration_audit_id": integration.audit_id,
                "failure_control_audit_id": controls.audit_id,
                "estimand_contract_id": estimand.contract_id,
            },
            field="audit_id",
            prefix="finance_v26_206_full_condition_gate_audit:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        models.make_identity(
            models.ProspectiveTransition,
            {
                "gate_audit_id": gates.audit_id,
                "execution_contract_id": execution.contract_id,
                "estimand_contract_id": estimand.contract_id,
            },
            field="transition_id",
            prefix="finance_v26_206_transition:",
        ),
    )
    source = _source_identity(source_identity)
    report = cast(
        models.PreflightReport,
        models.make_identity(
            models.PreflightReport,
            {
                "run_id": RUN_ID,
                "authorization_id": authorization.authorization_id,
                "predecessor_freeze_id": freeze.freeze_id,
                "repair_profile_id": profile.profile_id,
                "package_catalog_id": catalog.catalog_id,
                "manifest_id": manifest.manifest_id,
                "runner_id": runner.runner_id,
                "execution_contract_id": execution.contract_id,
                "callsite_census_id": census.census_id,
                "scripted_integration_audit_id": integration.audit_id,
                "failure_control_audit_id": controls.audit_id,
                "estimand_contract_id": estimand.contract_id,
                "gate_audit_id": gates.audit_id,
                "transition_id": transition.transition_id,
                "source_identity_id": source.source_identity_id,
            },
            field="report_id",
            prefix="finance_v26_206_full_condition_preflight_report:",
        ),
    )
    payloads = {
        "external_audit.txt": audit_bytes,
        "external_authorization.json": _file_bytes(authorization),
        "predecessor_freeze.json": _file_bytes(freeze),
        "full_condition_repair_profile.json": _file_bytes(profile),
        "repaired_runner_package_catalog.json": _file_bytes(catalog),
        "repaired_development_manifest.json": _file_bytes(manifest),
        "repaired_runner_contract.json": _file_bytes(runner),
        "repaired_execution_contract.json": _file_bytes(execution),
        "repaired_callsite_census.json": _file_bytes(census),
        "scripted_integration_audit.json": _file_bytes(integration),
        "failure_control_audit.json": _file_bytes(controls),
        "prospective_estimand_contract.json": _file_bytes(estimand),
        "full_condition_gate_audit.json": _file_bytes(gates),
        "prospective_transition.json": _file_bytes(transition),
        "source_identity.json": _file_bytes(source),
        "report.json": _file_bytes(report),
    }
    artifact = models.artifact_manifest(RUN_ID, payloads)
    payloads["artifact_manifest.json"] = _file_bytes(artifact)
    for name, payload in sorted(payloads.items()):
        _write_no_replace(output_dir / name, payload)
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
