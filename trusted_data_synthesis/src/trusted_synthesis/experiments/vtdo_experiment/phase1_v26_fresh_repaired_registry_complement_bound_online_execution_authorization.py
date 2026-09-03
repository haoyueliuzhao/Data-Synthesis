# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_registry_complement_bound_online_execution_authorization_models as models,
)

RUN_ID: Final = (
    "finance_v26_220_fresh_repaired_upstream_terminal_domain_exact_registry_"
    "complement_bound_online_execution_authorization_v1_20260903"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_REVIEW_SHA256: Final = "8a8ac1155fee931a4da4ae6c5ecbeab57fafdd4132d3a0626e42b471ba8fe459"
EXTERNAL_REVIEW_BYTES: Final = 13_007
OPERATOR_DIRECTIVE: Final = "参照审计继续实验"
V219_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_219_fresh_repaired_upstream_terminal_domain_exact_registry_"
    "complement_binding_preflight_independent_audit_v1_20260903"
)
V218_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_218_fresh_repaired_upstream_terminal_domain_exact_registry_"
    "complement_binding_preflight_v1_20260903"
)
V213_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_213_fresh_repaired_full_condition_observation_derived_terminal_"
    "single_consumer_path_repair_preflight_v1_20260902"
)
V209_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_209_fresh_repaired_full_condition_executable_runner_final_"
    "request_contract_continuity_repair_preflight_v1_20260902"
)
MODELS_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_registry_complement_bound_online_execution_"
    "authorization_models.py"
)
AUTHORIZATION_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_repaired_registry_complement_bound_online_execution_"
    "authorization.py"
)
TEST_FILE: Final = (
    "trusted_data_synthesis/tests/"
    "test_v26_fresh_repaired_registry_complement_bound_online_execution_"
    "authorization.py"
)
IMPLEMENTATION_FILES: Final = tuple(sorted((MODELS_FILE, AUTHORIZATION_FILE, TEST_FILE)))


class V220Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V220Error(stage, reason)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_bytes()))


def _bytes(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _make(model_type: type[Any], values: dict[str, Any], field: str, prefix: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=prefix)


def _git(repository_root: Path, *args: str) -> bytes:
    run = subprocess.run(("git", *args), cwd=repository_root, check=False, capture_output=True)
    if run.returncode:
        _fail("source.git", run.stderr.decode("utf-8", errors="replace"))
    return run.stdout


def _verify_formal_directory(
    root: Path,
    *,
    expected_file_count: int,
    expected_total_bytes: int,
    expected_member_count: int,
    expected_member_bytes: int,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    if len(files) != expected_file_count or sum(map(len, files.values())) != expected_total_bytes:
        _fail("freeze.geometry", f"formal directory geometry differs:{root.name}")
    manifest = _load(root / "artifact_manifest.json")
    members = {item["relative_path"]: item for item in manifest["members"]}
    if (
        manifest["file_count"] != expected_member_count
        or manifest["total_byte_count"] != expected_member_bytes
        or set(members) != set(files) - {"artifact_manifest.json"}
    ):
        _fail("freeze.manifest", f"formal Manifest geometry differs:{root.name}")
    for name, member in members.items():
        payload = files[name]
        if len(payload) != member["byte_count"] or _sha(payload) != member["sha256"]:
            _fail("freeze.member", f"formal member differs:{root.name}/{name}")
    return files, manifest


def _external_decision(
    review_path: Path,
) -> tuple[models.ExternalOnlineAuthorizationDecision, bytes, bytes]:
    review = review_path.read_bytes()
    if len(review) != EXTERNAL_REVIEW_BYTES or _sha(review) != EXTERNAL_REVIEW_SHA256:
        _fail("authorization.external_review", "v26.220 external review bytes differ")
    directive = OPERATOR_DIRECTIVE.encode("utf-8")
    decision = cast(
        models.ExternalOnlineAuthorizationDecision,
        _make(
            models.ExternalOnlineAuthorizationDecision,
            {
                "review_sha256": _sha(review),
                "review_byte_count": len(review),
                "operator_directive_sha256": _sha(directive),
                "operator_directive_byte_count": len(directive),
            },
            "decision_id",
            "finance_v26_220_external_online_authorization_decision:",
        ),
    )
    return decision, review, directive


def _v219_freeze(
    *, repository_root: Path, external_decision_id: str
) -> models.V219IndependentAuditFreeze:
    root = repository_root / V219_DIR
    _, manifest = _verify_formal_directory(
        root,
        expected_file_count=17,
        expected_total_bytes=46_670,
        expected_member_count=16,
        expected_member_bytes=43_862,
    )
    source = _load(root / "source_identity.json")
    report = _load(root / "report.json")
    gate = _load(root / "gate_evaluation.json")
    decision = _load(root / "decision.json")
    transition = _load(root / "prospective_transition.json")
    expected = (
        manifest["manifest_id"]
        == "finance_v26_219_artifact_manifest:14f2db99329b76781a46060868328ec6adc4f34a4016495632070067409990ed"
        and manifest["artifact_root"]
        == "finance_v26_219_artifact_root:c55ae394df7fc02b7db9c80c0a129531e200bf0ec44a1562e87d026ebb67e658"
        and report["report_id"]
        == "finance_v26_219_independent_audit_report:baa4a1897d4abc8939160332da260d94925bc3bbc234452b76e57f99d0c6070f"
        and gate["evaluation_id"]
        == "finance_v26_219_gate_evaluation:d59db6154ee07b74b763b455c3d643ef56aaae47a7cabe2ac6a52baff682946d"
        and decision["decision_id"]
        == "finance_v26_219_independent_audit_decision:396ba40f0ab00eff72872f3e6d2fc176114e1a2ad52b3d2b73efc8d0fbf359f3"
        and transition["transition_id"]
        == "finance_v26_219_transition:b54346c061e3b7ed06ff88632784cedb4298f0b0eacc8d9453ff860e8039b341"
        and transition["next_stage"] == models.CONSUMED_STAGE
        and transition["next_stage_authorized"] is False
        and source["source_commit"] == "40a7f6aa6fe5dac3a0b2f0865418bc384d4e6252"
        and source["source_tree"] == "3cc72c2d7721d4212dc68787ccf19c29e8f36c19"
        and gate["passed_count"] == 7
        and gate["failed_count"] == 0
        and report["current_v211_authorization_consumed"] is False
        and report["provider_calls"] == 0
    )
    if not expected:
        _fail("freeze.v219_authority", "v26.219 authority differs")
    component_ids = tuple(
        sorted(
            (
                report["detached_rebuild_audit_id"],
                report["registry_complement_audit_id"],
                report["retained_runtime_audit_id"],
                report["source_exit_persistence_audit_id"],
                report["full_rehash_attack_audit_id"],
                report["scope_boundary_audit_id"],
            )
        )
    )
    return cast(
        models.V219IndependentAuditFreeze,
        _make(
            models.V219IndependentAuditFreeze,
            {
                "external_decision_id": external_decision_id,
                "v219_source_commit": source["source_commit"],
                "v219_source_tree": source["source_tree"],
                "v219_artifact_manifest_id": manifest["manifest_id"],
                "v219_artifact_root": manifest["artifact_root"],
                "v219_report_id": report["report_id"],
                "v219_gate_evaluation_id": gate["evaluation_id"],
                "v219_decision_id": decision["decision_id"],
                "v219_transition_id": transition["transition_id"],
                "v219_component_audit_ids": component_ids,
                "v219_decision": decision["decision"],
            },
            "freeze_id",
            "finance_v26_220_v219_independent_audit_freeze:",
        ),
    )


def _v218_parent_set(
    *, repository_root: Path, v219_freeze_id: str
) -> models.V218RepairedParentSetBinding:
    root = repository_root / V218_DIR
    _, manifest = _verify_formal_directory(
        root,
        expected_file_count=51,
        expected_total_bytes=1_054_511,
        expected_member_count=50,
        expected_member_bytes=1_044_590,
    )
    names = {
        "source": "source_identity.json",
        "report": "report.json",
        "gate": "gate_evaluation.json",
        "decision": "decision.json",
        "transition": "prospective_transition.json",
        "implementation": "implementation_binding.json",
        "complement": "exact_registry_complement_binding.json",
        "composition": "composition_contract.json",
        "retained": "retained_execution_audit.json",
        "negative": "registry_complement_negative_control_audit.json",
        "scope": "scope_boundary_audit.json",
        "freeze": "v217_freeze.json",
    }
    data = {key: _load(root / name) for key, name in names.items()}
    complement = data["complement"]
    composition = data["composition"]
    expected = (
        manifest["manifest_id"]
        == "finance_v26_218_artifact_manifest:81b777673ed46c08fb6010ac3241f2fd87e087af4dc6f0c8266e4886dcb2276e"
        and manifest["artifact_root"]
        == "finance_v26_218_artifact_root:b9b4524a734249133d34007af751537cd25e8a705a31657c66bde5bd9b7b34e1"
        and data["source"]["source_commit"] == "6171fcc27a4a88693cb9daa1485b0d658b11a5a1"
        and data["source"]["source_tree"] == "1de85c4ee2f69a360bc7b7c13704186042648064"
        and complement["exact_v195_terminal_registry_id"] == models.REGISTRY_ID
        and (
            complement["registry_reachable_count"],
            complement["admitted_terminal_count"],
            complement["forbidden_terminal_count"],
        )
        == (16, 1, 15)
        and complement["union_equals_reachable"] is True
        and complement["intersection_is_empty"] is True
        and "provider_failure_no_payload" in complement["forbidden_terminal_kinds"]
        and "resource_budget_exhausted" in complement["forbidden_terminal_kinds"]
        and "provider_no_payload_failure" not in complement["forbidden_terminal_kinds"]
        and "resource_failure" not in complement["forbidden_terminal_kinds"]
        and data["report"]["current_v211_authorization_consumed"] is False
        and data["report"]["provider_calls"] == 0
    )
    if not expected:
        _fail("parent.v218", "v26.218 repaired parent set differs")
    parent_ids = tuple(
        sorted(
            {
                manifest["manifest_id"],
                manifest["artifact_root"],
                data["report"]["report_id"],
                data["gate"]["evaluation_id"],
                data["decision"]["decision_id"],
                data["transition"]["transition_id"],
                data["implementation"]["binding_id"],
                complement["binding_id"],
                composition["contract_id"],
                data["retained"]["audit_id"],
                data["negative"]["audit_id"],
                data["scope"]["audit_id"],
                data["freeze"]["freeze_id"],
                complement["exact_v195_terminal_registry_id"],
                composition["v217_composition_contract_id"],
                composition["v217_consumer_binding_id"],
                composition["v217_dispatcher_binding_id"],
                composition["v217_event_source_binding_id"],
                composition["v217_observation_binding_id"],
                composition["v217_persistence_binding_id"],
                composition["v217_runner_binding_id"],
                composition["v217_source_contract_id"],
            }
        )
    )
    return cast(
        models.V218RepairedParentSetBinding,
        _make(
            models.V218RepairedParentSetBinding,
            {
                "v219_freeze_id": v219_freeze_id,
                "v218_source_commit": data["source"]["source_commit"],
                "v218_source_tree": data["source"]["source_tree"],
                "v218_artifact_manifest_id": manifest["manifest_id"],
                "v218_artifact_root": manifest["artifact_root"],
                "v218_report_id": data["report"]["report_id"],
                "v218_gate_id": data["gate"]["evaluation_id"],
                "v218_decision_id": data["decision"]["decision_id"],
                "v218_transition_id": data["transition"]["transition_id"],
                "exact_v195_registry_id": complement["exact_v195_terminal_registry_id"],
                "complement_binding_id": complement["binding_id"],
                "v218_composition_contract_id": composition["contract_id"],
                "exact_parent_ids": parent_ids,
                "exact_parent_set_sha256": models.canonical_sha256(parent_ids),
                "exact_parent_count": len(parent_ids),
                "admitted_event_terminal_policy_items": tuple(
                    tuple(item) for item in complement["admitted_event_terminal_policy_items"]
                ),
                "forbidden_terminal_kinds": tuple(complement["forbidden_terminal_kinds"]),
            },
            "binding_id",
            "fresh_repaired_v218_complete_parent_set_binding:",
        ),
    )


def _execution_condition(
    *, repository_root: Path, v219_freeze_id: str
) -> models.ExactExecutionConditionBinding:
    root = repository_root / V209_DIR
    manifest = _load(root / "executable_development_manifest.json")
    catalog = _load(root / "executable_runner_package_catalog.json")
    census = _load(root / "executable_invocation_census.json")
    contract = _load(root / "executable_execution_contract.json")
    implementation = _load(root / "implementation_binding.json")
    source = _load(root / "source_identity.json")
    jobs = manifest["jobs"]
    rows = census["rows"]
    packages = catalog["packages"]
    job_ids = tuple(sorted(item["job_id"] for item in jobs))
    package_ids = tuple(sorted(item["package_id"] for item in packages))
    coordinates = tuple(
        sorted(
            (
                item["job_id"],
                item["phase"],
                item["invocation_index"],
                item["component_key"] or "",
            )
            for item in rows
        )
    )
    namespaces = {
        name: tuple(sorted(item[f"{name}_namespace"] for item in jobs))
        for name in ("raw", "result", "trace", "outcome")
    }
    phase_counts = {
        "first_action": sum(item["phase"] == "first_action" for item in rows),
        "subsequent_action": sum(item["phase"] == "subsequent_action" for item in rows),
        "correction": sum(item["phase"] == "correction" for item in rows),
        "final": sum(item["phase"] == "final" for item in rows),
    }
    if (
        source["source_commit"] != "5809e9782515e55ee797b43730584d5d860aaa5c"
        or source["source_tree"] != "b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"
        or implementation["implementation_id"] != contract["implementation_id"]
        or contract["manifest_id"] != manifest["manifest_id"]
        or contract["package_catalog_id"] != catalog["catalog_id"]
        or census["manifest_id"] != manifest["manifest_id"]
        or (len(package_ids), manifest["replica_count"], len(job_ids), len(rows))
        != (32, 6, 192, 792)
        or phase_counts
        != {
            "first_action": 192,
            "subsequent_action": 288,
            "correction": 120,
            "final": 192,
        }
        or len(set(coordinates)) != 792
        or any(len(set(value)) != 192 for value in namespaces.values())
        or any(item["provider_calls"] != 0 for item in jobs)
    ):
        _fail("condition.v209", "exact v26.209 execution condition differs")
    return cast(
        models.ExactExecutionConditionBinding,
        _make(
            models.ExactExecutionConditionBinding,
            {
                "v219_freeze_id": v219_freeze_id,
                "v209_source_commit": source["source_commit"],
                "v209_source_tree": source["source_tree"],
                "v209_implementation_id": implementation["implementation_id"],
                "v209_package_catalog_id": catalog["catalog_id"],
                "v209_manifest_id": manifest["manifest_id"],
                "v209_runner_id": contract["runner_id"],
                "v209_execution_contract_id": contract["contract_id"],
                "v209_invocation_census_id": census["census_id"],
                "repair_profile_id": contract["repair_profile_id"],
                "kernel_resource_contract_id": contract["resource_contract_id"],
                "exact_package_ids": package_ids,
                "exact_job_ids": job_ids,
                "exact_package_set_sha256": models.canonical_sha256(package_ids),
                "exact_job_set_sha256": models.canonical_sha256(job_ids),
                "exact_coordinate_set_sha256": models.canonical_sha256(coordinates),
                "raw_namespace_set_sha256": models.canonical_sha256(namespaces["raw"]),
                "result_namespace_set_sha256": models.canonical_sha256(namespaces["result"]),
                "trace_namespace_set_sha256": models.canonical_sha256(namespaces["trace"]),
                "outcome_namespace_set_sha256": models.canonical_sha256(namespaces["outcome"]),
            },
            "binding_id",
            "fresh_repaired_registry_complement_bound_execution_condition:",
        ),
    )


def _composition(
    *,
    repository_root: Path,
    freeze: models.V219IndependentAuditFreeze,
    parents: models.V218RepairedParentSetBinding,
    condition: models.ExactExecutionConditionBinding,
) -> models.OnlineExecutionCompositionContract:
    v213_root = repository_root / V213_DIR
    consumer = _load(v213_root / "single_consumer_implementation_binding.json")
    dispatcher = _load(v213_root / "observation_derived_dispatcher_binding.json")
    persistence = _load(v213_root / "observation_bound_persistence_binding.json")
    main_composition = _load(v213_root / "single_consumer_composition_contract.json")
    v218_composition = _load(repository_root / V218_DIR / "composition_contract.json")
    main_terminal_kinds = tuple(sorted(dispatcher["terminal_kinds"][:8]))
    if (
        consumer["binding_id"]
        != "fresh_repaired_single_online_consumer_implementation_binding:1c5923d5c9856c3c4d084ef2f05aaf88ab02cbcb3bc1b899988ee464eda7bcc2"
        or dispatcher["binding_id"]
        != "fresh_repaired_observation_derived_terminal_dispatcher_binding:10a51ef2cc7f7ce20ad63918507c201f12112e34729e1088ab272da3820b209f"
        or persistence["binding_id"]
        != "fresh_repaired_observation_bound_persistence_binding:21f1608bceeb683c59c4421eb836404709e7136f01a2c34b634de1c95532eff9"
        or main_composition["contract_id"]
        != "fresh_repaired_observation_derived_single_consumer_composition_contract:f27da41c720b6041e918b5018291403b15281b990975dd411acd9eff4a1a4644"
        or main_composition["caller_terminal_forbidden"] is not True
        or v218_composition["contract_id"] != parents.v218_composition_contract_id
        or v218_composition["complement_binding_id"] != parents.complement_binding_id
        or condition.v209_runner_id != consumer["exact_v209_runner_id"]
    ):
        _fail("composition.parents", "online execution composition parent differs")
    return cast(
        models.OnlineExecutionCompositionContract,
        _make(
            models.OnlineExecutionCompositionContract,
            {
                "v219_freeze_id": freeze.freeze_id,
                "v218_parent_set_binding_id": parents.binding_id,
                "condition_binding_id": condition.binding_id,
                "exact_v213_main_consumer_binding_id": consumer["binding_id"],
                "exact_v213_main_dispatcher_binding_id": dispatcher["binding_id"],
                "exact_v213_main_persistence_binding_id": persistence["binding_id"],
                "exact_v213_main_composition_contract_id": main_composition["contract_id"],
                "exact_v218_failure_complement_binding_id": parents.complement_binding_id,
                "exact_v218_failure_composition_contract_id": parents.v218_composition_contract_id,
                "exact_v218_failure_source_contract_id": v218_composition[
                    "v217_source_contract_id"
                ],
                "main_observation_terminal_kinds": main_terminal_kinds,
                "source_bound_failure_terminal_kinds": (
                    "instrument_failure",
                    "privacy_rejection",
                ),
            },
            "contract_id",
            "fresh_repaired_registry_complement_bound_online_execution_composition_contract:",
        ),
    )


def _authorization(
    *,
    external: models.ExternalOnlineAuthorizationDecision,
    freeze: models.V219IndependentAuditFreeze,
    parents: models.V218RepairedParentSetBinding,
    condition: models.ExactExecutionConditionBinding,
    composition: models.OnlineExecutionCompositionContract,
) -> models.ExactOnlineExecutionAuthorization:
    return cast(
        models.ExactOnlineExecutionAuthorization,
        _make(
            models.ExactOnlineExecutionAuthorization,
            {
                "external_decision_id": external.decision_id,
                "v219_freeze_id": freeze.freeze_id,
                "v218_parent_set_binding_id": parents.binding_id,
                "condition_binding_id": condition.binding_id,
                "composition_contract_id": composition.contract_id,
                "exact_v218_parent_set_sha256": parents.exact_parent_set_sha256,
                "v209_manifest_id": condition.v209_manifest_id,
                "v209_runner_id": condition.v209_runner_id,
                "v209_execution_contract_id": condition.v209_execution_contract_id,
                "exact_job_ids": condition.exact_job_ids,
                "exact_job_set_sha256": condition.exact_job_set_sha256,
                "exact_coordinate_set_sha256": condition.exact_coordinate_set_sha256,
                "raw_namespace_set_sha256": condition.raw_namespace_set_sha256,
                "result_namespace_set_sha256": condition.result_namespace_set_sha256,
                "trace_namespace_set_sha256": condition.trace_namespace_set_sha256,
                "outcome_namespace_set_sha256": condition.outcome_namespace_set_sha256,
            },
            "authorization_id",
            "fresh_repaired_registry_complement_bound_exact_online_execution_authorization:",
        ),
    )


def _request(authorization: models.ExactOnlineExecutionAuthorization) -> dict[str, Any]:
    return {
        "authorization": authorization,
        "authorization_bytes": models.canonical_bytes(authorization),
        "requested_stage": authorization.authorized_stage,
        "requested_v218_parent_set_binding_id": authorization.v218_parent_set_binding_id,
        "requested_condition_binding_id": authorization.condition_binding_id,
        "requested_composition_contract_id": authorization.composition_contract_id,
        "requested_manifest_id": authorization.v209_manifest_id,
        "requested_runner_id": authorization.v209_runner_id,
        "requested_execution_contract_id": authorization.v209_execution_contract_id,
        "requested_job_ids": authorization.exact_job_ids,
        "requested_coordinate_set_sha256": authorization.exact_coordinate_set_sha256,
        "provider_execution_requested": True,
    }


def _admission_audit(
    authorization: models.ExactOnlineExecutionAuthorization,
) -> models.PrecredentialAdmissionAudit:
    guard = models.PrecredentialAuthorizationGuard(
        expected_authorization=authorization,
        expected_authorization_bytes=models.canonical_bytes(authorization),
    )
    exact_request = _request(authorization)
    admission = guard.admit(**exact_request)
    cases: list[tuple[str, dict[str, Any]]] = [("exact_nonconsuming_probe", {})]
    cases.extend(
        (
            ("missing_authorization", {"authorization": None}),
            ("missing_authorization_bytes", {"authorization_bytes": None}),
            (
                "modified_authorization_bytes",
                {"authorization_bytes": models.canonical_bytes(authorization) + b"\n"},
            ),
            ("old_v211_authorization", {"old_v211_authorization_presented": True}),
            ("wrong_stage", {"requested_stage": models.CONSUMED_STAGE}),
            (
                "wrong_v218_parent_set",
                {"requested_v218_parent_set_binding_id": "forged:v218"},
            ),
            ("wrong_condition", {"requested_condition_binding_id": "forged:condition"}),
            (
                "wrong_composition",
                {"requested_composition_contract_id": "forged:composition"},
            ),
            ("wrong_manifest", {"requested_manifest_id": "forged:manifest"}),
            ("wrong_runner", {"requested_runner_id": "forged:runner"}),
            (
                "wrong_execution_contract",
                {"requested_execution_contract_id": "forged:execution"},
            ),
            (
                "wrong_job_set",
                {"requested_job_ids": authorization.exact_job_ids[:-1]},
            ),
            (
                "wrong_coordinate_set",
                {"requested_coordinate_set_sha256": "0" * 64},
            ),
            ("no_provider_execution_request", {"provider_execution_requested": False}),
            ("replacement_run", {"replacement_run_requested": True}),
            ("failed_job_rerun", {"failed_job_rerun_requested": True}),
            ("recovery_run", {"recovery_run_requested": True}),
            ("condition_change", {"condition_change_requested": True}),
            ("qa_integration", {"qa_integration_requested": True}),
            ("caller_terminal", {"caller_terminal_provided": True}),
            ("historical_response", {"historical_response_provided": True}),
            ("reference_choice_vector", {"reference_choice_vector_provided": True}),
            ("prebuilt_final", {"prebuilt_final_provided": True}),
        )
    )
    controls: list[models.AdmissionControl] = []
    for name, changes in cases:
        request = {**exact_request, **changes}
        admitted = False
        reason: str | None = None
        try:
            guard.admit(**request)
            admitted = True
        except ValueError as error:
            reason = _sha(str(error).encode("utf-8"))
        controls.append(
            cast(
                models.AdmissionControl,
                _make(
                    models.AdmissionControl,
                    {
                        "control_name": name,
                        "admitted": admitted,
                        "rejected": not admitted,
                        "rejection_reason_sha256": reason,
                    },
                    "control_id",
                    "finance_v26_220_precredential_admission_control:",
                ),
            )
        )
    invalid = sum(item.rejected for item in controls)
    audit = cast(
        models.PrecredentialAdmissionAudit,
        _make(
            models.PrecredentialAdmissionAudit,
            {
                "authorization_id": authorization.authorization_id,
                "admission_id": admission.admission_id,
                "controls": tuple(controls),
                "invalid_control_count": invalid,
            },
            "audit_id",
            "finance_v26_220_precredential_admission_audit:",
        ),
    )
    return audit


def _parent_attack_audit(
    *,
    authorization: models.ExactOnlineExecutionAuthorization,
    composition: models.OnlineExecutionCompositionContract,
) -> models.ParentAttackAudit:
    guard = models.PrecredentialAuthorizationGuard(
        expected_authorization=authorization,
        expected_authorization_bytes=models.canonical_bytes(authorization),
    )
    mutations: tuple[tuple[str, str, Any], ...] = (
        ("v219_freeze_replacement", "v219_freeze_id", "forged:v219"),
        ("v218_parent_set_replacement", "v218_parent_set_binding_id", "forged:v218"),
        ("condition_replacement", "condition_binding_id", "forged:condition"),
        (
            "v213_consumer_replacement",
            "exact_v213_main_consumer_binding_id",
            "forged:consumer",
        ),
        (
            "v213_dispatcher_replacement",
            "exact_v213_main_dispatcher_binding_id",
            "forged:dispatcher",
        ),
        (
            "v213_persistence_replacement",
            "exact_v213_main_persistence_binding_id",
            "forged:persistence",
        ),
        (
            "v213_composition_replacement",
            "exact_v213_main_composition_contract_id",
            "forged:main-composition",
        ),
        (
            "v218_complement_replacement",
            "exact_v218_failure_complement_binding_id",
            "forged:complement",
        ),
        (
            "v218_composition_replacement",
            "exact_v218_failure_composition_contract_id",
            "forged:failure-composition",
        ),
        (
            "v218_source_contract_replacement",
            "exact_v218_failure_source_contract_id",
            "forged:source-contract",
        ),
        (
            "main_terminal_partition_replacement",
            "main_observation_terminal_kinds",
            tuple(f"forged_terminal_{index}" for index in range(8)),
        ),
        (
            "crossed_main_consumer_parent",
            "exact_v213_main_consumer_binding_id",
            composition.exact_v213_main_dispatcher_binding_id,
        ),
    )
    attacks: list[models.ParentAttack] = []
    for name, field, value in mutations:
        values = composition.model_dump(mode="python", exclude={"contract_id"}, warnings=False)
        values[field] = value
        mutated_composition = cast(
            models.OnlineExecutionCompositionContract,
            _make(
                models.OnlineExecutionCompositionContract,
                values,
                "contract_id",
                "fresh_repaired_registry_complement_bound_online_execution_composition_contract:",
            ),
        )
        auth_values = authorization.model_dump(
            mode="python", exclude={"authorization_id"}, warnings=False
        )
        auth_values["composition_contract_id"] = mutated_composition.contract_id
        if field == "v219_freeze_id":
            auth_values["v219_freeze_id"] = value
        elif field == "v218_parent_set_binding_id":
            auth_values["v218_parent_set_binding_id"] = value
        elif field == "condition_binding_id":
            auth_values["condition_binding_id"] = value
        mutated_authorization = cast(
            models.ExactOnlineExecutionAuthorization,
            _make(
                models.ExactOnlineExecutionAuthorization,
                auth_values,
                "authorization_id",
                "fresh_repaired_registry_complement_bound_exact_online_execution_authorization:",
            ),
        )
        reason: str | None = None
        try:
            request = _request(mutated_authorization)
            guard.admit(**request)
        except ValueError as error:
            reason = _sha(str(error).encode("utf-8"))
        if reason is None:
            _fail("negative.parent_attack", f"fully rehashed parent attack accepted:{name}")
        attacks.append(
            cast(
                models.ParentAttack,
                _make(
                    models.ParentAttack,
                    {
                        "attack_name": name,
                        "mutated_authorization_id": mutated_authorization.authorization_id,
                        "mutated_composition_id": mutated_composition.contract_id,
                        "rejection_reason_sha256": reason,
                    },
                    "attack_id",
                    "finance_v26_220_fully_rehashed_parent_attack:",
                ),
            )
        )
    return cast(
        models.ParentAttackAudit,
        _make(
            models.ParentAttackAudit,
            {
                "authorization_id": authorization.authorization_id,
                "attacks": tuple(attacks),
                "attack_count": len(attacks),
                "fully_rehashed_object_count": 2 * len(attacks),
                "rejected_attack_count": len(attacks),
            },
            "audit_id",
            "finance_v26_220_parent_attack_audit:",
        ),
    )


def _source_identity(source_identity: tuple[str, str]) -> models.SourceIdentity:
    return cast(
        models.SourceIdentity,
        _make(
            models.SourceIdentity,
            {
                "source_commit": source_identity[0],
                "source_tree": source_identity[1],
                "implementation_files": IMPLEMENTATION_FILES,
            },
            "source_identity_id",
            "finance_v26_220_source_identity:",
        ),
    )


def _implementation_binding(
    *,
    repository_root: Path,
    source: models.SourceIdentity,
    external_decision_id: str,
    freeze_id: str,
) -> models.ImplementationBinding:
    use_commit = source.source_commit != "1" * 40
    if use_commit:
        tree = (
            _git(repository_root, "rev-parse", f"{source.source_commit}^{{tree}}").decode().strip()
        )
        if tree != source.source_tree:
            _fail("source.tree", "v26.220 source tree differs")
    files: list[models.SourceFile] = []
    for relative_path in source.implementation_files:
        payload = (
            _git(repository_root, "show", f"{source.source_commit}:{relative_path}")
            if use_commit
            else (repository_root / relative_path).read_bytes()
        )
        if use_commit and payload != (repository_root / relative_path).read_bytes():
            _fail("source.working_tree", f"v26.220 source file differs:{relative_path}")
        files.append(
            models.SourceFile(
                relative_path=relative_path,
                sha256=_sha(payload),
                byte_count=len(payload),
            )
        )
    return cast(
        models.ImplementationBinding,
        _make(
            models.ImplementationBinding,
            {
                "source_identity_id": source.source_identity_id,
                "external_decision_id": external_decision_id,
                "v219_freeze_id": freeze_id,
                "files": tuple(files),
                "guard_symbol_sha256": _sha(
                    inspect.getsource(models.PrecredentialAuthorizationGuard).encode("utf-8")
                ),
                "build_symbol_sha256": _sha(inspect.getsource(build).encode("utf-8")),
            },
            "binding_id",
            "fresh_repaired_registry_complement_bound_online_authorization_implementation_binding:",
        ),
    )


def _gate(evidence: tuple[tuple[str, str], ...]) -> models.GateEvaluation:
    gates = tuple(
        cast(
            models.GateResult,
            _make(
                models.GateResult,
                {"gate_name": name, "evidence_id": evidence_id},
                "gate_id",
                "finance_v26_220_gate:",
            ),
        )
        for name, evidence_id in evidence
    )
    return cast(
        models.GateEvaluation,
        _make(
            models.GateEvaluation,
            {"gates": gates},
            "evaluation_id",
            "finance_v26_220_gate_evaluation:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.Report:
    external, review, directive = _external_decision(external_review_path)
    freeze = _v219_freeze(
        repository_root=repository_root, external_decision_id=external.decision_id
    )
    parents = _v218_parent_set(repository_root=repository_root, v219_freeze_id=freeze.freeze_id)
    condition = _execution_condition(
        repository_root=repository_root, v219_freeze_id=freeze.freeze_id
    )
    composition = _composition(
        repository_root=repository_root,
        freeze=freeze,
        parents=parents,
        condition=condition,
    )
    authorization = _authorization(
        external=external,
        freeze=freeze,
        parents=parents,
        condition=condition,
        composition=composition,
    )
    admission = _admission_audit(authorization)
    attacks = _parent_attack_audit(authorization=authorization, composition=composition)
    scope = cast(
        models.ScopeBoundaryAudit,
        _make(
            models.ScopeBoundaryAudit,
            {"authorization_id": authorization.authorization_id},
            "audit_id",
            "finance_v26_220_scope_boundary_audit:",
        ),
    )
    gate = _gate(
        (
            ("G0_external_scope_and_v219_independent_audit_freeze", freeze.freeze_id),
            ("G1_complete_v218_repaired_parent_set", parents.binding_id),
            ("G2_exact_v209_192_job_condition", condition.binding_id),
            ("G3_source_bound_single_consumer_composition", composition.contract_id),
            ("G4_fresh_exact_online_authorization", authorization.authorization_id),
            ("G5_precredential_admission_and_old_v211_rejection", admission.audit_id),
            ("G6_fully_rehashed_parent_attacks_reject", attacks.audit_id),
            ("G7_zero_provider_credential_empirical_boundary", scope.audit_id),
        )
    )
    decision = cast(
        models.OnlineAuthorizationDecision,
        _make(
            models.OnlineAuthorizationDecision,
            {
                "external_decision_id": external.decision_id,
                "v219_freeze_id": freeze.freeze_id,
                "v218_parent_set_binding_id": parents.binding_id,
                "condition_binding_id": condition.binding_id,
                "composition_contract_id": composition.contract_id,
                "authorization_id": authorization.authorization_id,
                "admission_audit_id": admission.audit_id,
                "parent_attack_audit_id": attacks.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
            },
            "decision_id",
            "finance_v26_220_online_authorization_decision:",
        ),
    )
    transition = cast(
        models.ProspectiveTransition,
        _make(
            models.ProspectiveTransition,
            {
                "decision_id": decision.decision_id,
                "authorization_id": authorization.authorization_id,
            },
            "transition_id",
            "finance_v26_220_transition:",
        ),
    )
    source = _source_identity(source_identity)
    implementation = _implementation_binding(
        repository_root=repository_root,
        source=source,
        external_decision_id=external.decision_id,
        freeze_id=freeze.freeze_id,
    )
    report = cast(
        models.Report,
        _make(
            models.Report,
            {
                "run_id": RUN_ID,
                "source_identity_id": source.source_identity_id,
                "implementation_binding_id": implementation.binding_id,
                "external_decision_id": external.decision_id,
                "v219_freeze_id": freeze.freeze_id,
                "v218_parent_set_binding_id": parents.binding_id,
                "condition_binding_id": condition.binding_id,
                "composition_contract_id": composition.contract_id,
                "authorization_id": authorization.authorization_id,
                "admission_audit_id": admission.audit_id,
                "parent_attack_audit_id": attacks.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            "report_id",
            "finance_v26_220_online_authorization_report:",
        ),
    )
    payloads = {
        "decision.json": _bytes(decision),
        "exact_192_job_condition_binding.json": _bytes(condition),
        "exact_online_execution_authorization.json": _bytes(authorization),
        "external_online_authorization_decision.json": _bytes(external),
        "external_review.txt": review,
        "gate_evaluation.json": _bytes(gate),
        "implementation_binding.json": _bytes(implementation),
        "online_execution_composition_contract.json": _bytes(composition),
        "operator_authorization.txt": directive,
        "parent_attack_audit.json": _bytes(attacks),
        "precredential_admission_audit.json": _bytes(admission),
        "prospective_transition.json": _bytes(transition),
        "report.json": _bytes(report),
        "scope_boundary_audit.json": _bytes(scope),
        "source_identity.json": _bytes(source),
        "v218_repaired_parent_set_binding.json": _bytes(parents),
        "v219_freeze.json": _bytes(freeze),
    }
    artifact = models.artifact_manifest(RUN_ID, payloads)
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, payload in sorted(payloads.items()):
        (output_dir / name).write_bytes(payload)
    (output_dir / "artifact_manifest.json").write_bytes(_bytes(artifact))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-review", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    build(
        repository_root=args.repository_root.resolve(),
        output_dir=args.output_dir.resolve(),
        external_review_path=args.external_review.resolve(),
        source_identity=(args.source_commit, args.source_tree),
    )


if __name__ == "__main__":
    main()
