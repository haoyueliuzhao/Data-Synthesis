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
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_authorization_models as models,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = (
    "finance_v26_223_fresh_exact_v209_execution_condition_authoritative_parent_"
    "bound_online_execution_authorization_v1_20260903"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_REVIEW_SHA256: Final = "b40d6ada5e463411741f49e99d957f3dc6dc65e53b7852151a43f75c9dccb98a"
EXTERNAL_REVIEW_BYTES: Final = 16_856
OPERATOR_DIRECTIVE: Final = "参照审计继续实验"
V222_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_222_fresh_exact_v209_execution_condition_authoritative_parent_"
    "binding_repair_preflight_independent_audit_v1_20260903"
)
V221_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_221_fresh_exact_v209_execution_condition_authoritative_parent_"
    "binding_repair_preflight_v1_20260903"
)
V220_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_220_fresh_repaired_upstream_terminal_domain_exact_registry_"
    "complement_bound_online_execution_authorization_v1_20260903"
)
V209_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_209_fresh_repaired_full_condition_executable_runner_final_"
    "request_contract_continuity_repair_preflight_v1_20260902"
)
MODELS_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_parent_bound_online_execution_authorization_models.py"
)
AUTHORIZATION_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_parent_bound_online_execution_authorization.py"
)
TEST_FILE: Final = (
    "trusted_data_synthesis/tests/"
    "test_v26_fresh_exact_v209_parent_bound_online_execution_authorization.py"
)
IMPLEMENTATION_FILES: Final = tuple(sorted((MODELS_FILE, AUTHORIZATION_FILE, TEST_FILE)))


class V223Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V223Error(stage, reason)


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
    manifest_prefix: str,
    root_prefix: str,
) -> dict[str, Any]:
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    manifest = cast(dict[str, Any], json.loads(files.get("artifact_manifest.json", b"{}")))
    members = cast(list[dict[str, Any]], manifest.get("members", []))
    member_names = tuple(item.get("relative_path") for item in members)
    expected_names = tuple(sorted(set(files) - {"artifact_manifest.json"}))
    projection = tuple(members)
    manifest_without_id = {key: value for key, value in manifest.items() if key != "manifest_id"}
    if (
        len(files) != expected_file_count
        or sum(len(payload) for payload in files.values()) != expected_total_bytes
        or len(members) != expected_member_count
        or sum(int(item.get("byte_count", -1)) for item in members) != expected_member_bytes
        or member_names != expected_names
        or manifest.get("file_count") != expected_member_count
        or manifest.get("total_byte_count") != expected_member_bytes
        or manifest.get("artifact_root") != canonical_hash(projection, prefix=root_prefix)
        or manifest.get("manifest_id")
        != canonical_hash(manifest_without_id, prefix=manifest_prefix)
    ):
        _fail("formal.directory", f"formal directory geometry differs:{root}")
    for item in members:
        name = cast(str, item["relative_path"])
        payload = files.get(name)
        if payload is None or len(payload) != item["byte_count"] or _sha(payload) != item["sha256"]:
            _fail("formal.member", f"formal member differs:{root}:{name}")
    return manifest


def _external_decision(
    external_review_path: Path,
) -> tuple[models.ExternalOnlineAuthorizationDecision, bytes, bytes]:
    review = external_review_path.read_bytes()
    if len(review) != EXTERNAL_REVIEW_BYTES or _sha(review) != EXTERNAL_REVIEW_SHA256:
        _fail("authorization.external_review", "v26.223 external review bytes differ")
    directive = OPERATOR_DIRECTIVE.encode("utf-8")
    decision = cast(
        models.ExternalOnlineAuthorizationDecision,
        _make(
            models.ExternalOnlineAuthorizationDecision,
            {
                "review_sha256": EXTERNAL_REVIEW_SHA256,
                "operator_directive_sha256": _sha(directive),
            },
            "decision_id",
            "finance_v26_223_external_online_authorization_decision:",
        ),
    )
    return decision, review, directive


def _v222_freeze(
    *, repository_root: Path, external_decision_id: str
) -> models.V222IndependentAuditFreeze:
    root = repository_root / V222_DIR
    manifest = _verify_formal_directory(
        root,
        expected_file_count=16,
        expected_total_bytes=74_784,
        expected_member_count=15,
        expected_member_bytes=72_169,
        manifest_prefix="finance_v26_222_artifact_manifest:",
        root_prefix="finance_v26_222_artifact_root:",
    )
    source = _load(root / "source_identity.json")
    report = _load(root / "report.json")
    gate = _load(root / "gate_evaluation.json")
    decision = _load(root / "decision.json")
    transition = _load(root / "prospective_transition.json")
    expected = (
        manifest["manifest_id"]
        == "finance_v26_222_artifact_manifest:ecfe64ef313d5950bbcab3d296c31f05a2b5838b667d1d43375f07cc78a98688"
        and manifest["artifact_root"]
        == "finance_v26_222_artifact_root:f6cf3c042a7ee130feb537d5b3eff3f0109e81a72fb429ad32b8f41d8772400d"
        and source["source_commit"] == "b95981668173eb1ed73a2581564fed6a0b280cfb"
        and source["source_tree"] == "e9cfdb35518727452a73cca6f7d9dedab15588fb"
        and report["report_id"]
        == "finance_v26_222_independent_audit_report:b72380e5f70cb9f2ce30118a371f916fed3877e5fed066c50fdd938be7479163"
        and gate["evaluation_id"]
        == "finance_v26_222_gate_evaluation:a82020070a552f8abf4f1361d6efe72f90104b4aa0bafc14529cab33a629f42f"
        and decision["decision_id"]
        == "finance_v26_222_independent_audit_decision:96846998c5507d42113cdf10372312d1228f590266fe685d431be018cb24e2e8"
        and transition["transition_id"]
        == "finance_v26_222_transition:641c3cdf58c006b6e131770c42377600e16b5e82c5dd3238db6d5505df10f329"
        and transition["next_stage"] == models.CONSUMED_STAGE
        and transition["next_stage_authorized"] is False
        and transition["v220_authorization_forbidden"] is True
        and decision["decision"]
        == "v26_221_exact_v209_execution_condition_parent_authority_repair_preflight_independent_audit_passed"
        and decision["mandatory_revision"] == "NONE"
        and gate["passed_count"] == 6
        and gate["failed_count"] == 0
        and gate["online_authorization_issued"] is False
        and report["new_online_authorizations"] == 0
        and report["v220_authorization_consumed"] is False
        and report["provider_calls"] == 0
    )
    if not expected:
        _fail("freeze.v222", "exact v26.222 authority differs")
    tree = _git(repository_root, "rev-parse", "b95981668173eb1ed73a2581564fed6a0b280cfb^{tree}")
    if tree.decode().strip() != source["source_tree"]:
        _fail("freeze.v222_source", "v26.222 commit-to-tree relation differs")
    component_ids = tuple(
        sorted(
            (
                report["detached_rebuild_audit_id"],
                report["v209_authority_audit_id"],
                report["relation_closure_audit_id"],
                report["attack_audit_id"],
                report["scope_boundary_audit_id"],
                report["freeze_id"],
            )
        )
    )
    return cast(
        models.V222IndependentAuditFreeze,
        _make(
            models.V222IndependentAuditFreeze,
            {
                "external_decision_id": external_decision_id,
                "v222_source_commit": source["source_commit"],
                "v222_source_tree": source["source_tree"],
                "v222_artifact_manifest_id": manifest["manifest_id"],
                "v222_artifact_root": manifest["artifact_root"],
                "v222_report_id": report["report_id"],
                "v222_gate_evaluation_id": gate["evaluation_id"],
                "v222_decision_id": decision["decision_id"],
                "v222_transition_id": transition["transition_id"],
                "v222_component_audit_ids": component_ids,
                "v222_decision": decision["decision"],
            },
            "freeze_id",
            "finance_v26_223_v222_independent_audit_freeze:",
        ),
    )


def _object_identity(value: dict[str, Any], field: str, prefix: str) -> str:
    return canonical_hash({key: item for key, item in value.items() if key != field}, prefix=prefix)


def _v221_parent_binding(
    *, repository_root: Path, v222_freeze_id: str
) -> models.V221RepairedParentBinding:
    root = repository_root / V221_DIR
    manifest = _verify_formal_directory(
        root,
        expected_file_count=17,
        expected_total_bytes=112_607,
        expected_member_count=16,
        expected_member_bytes=109_876,
        manifest_prefix="finance_v26_221_artifact_manifest:",
        root_prefix="finance_v26_221_artifact_root:",
    )
    names = (
        "source_identity",
        "report",
        "gate_evaluation",
        "decision",
        "prospective_transition",
        "v209_formal_authority_freeze",
        "relation_closure_audit",
        "authoritative_execution_condition_binding",
        "repaired_composition_contract",
        "upstream_tamper_audit",
        "scope_boundary_audit",
        "implementation_binding",
        "v220_freeze",
    )
    data = {name: _load(root / f"{name}.json") for name in names}
    source = data["source_identity"]
    report = data["report"]
    gate = data["gate_evaluation"]
    decision = data["decision"]
    transition = data["prospective_transition"]
    formal = data["v209_formal_authority_freeze"]
    relation = data["relation_closure_audit"]
    condition = data["authoritative_execution_condition_binding"]
    composition = data["repaired_composition_contract"]
    v220_freeze = data["v220_freeze"]
    if not (
        manifest["manifest_id"]
        == "finance_v26_221_artifact_manifest:c52e6edea3d097f7ac3797fcdc0cbc704a99174b7514b09e62265784ed6c189a"
        and manifest["artifact_root"]
        == "finance_v26_221_artifact_root:5782f2689c74fe1388f9f8b1f600e7b01ece3296a7abfc39265bb44b64cdb5f4"
        and source["source_commit"] == "dbd9d15b6d44577725ef8d8a6c1fcca730120d5d"
        and source["source_tree"] == "06f23ef0847e39b03fae9b19155cb3e7b22fbdf7"
        and report["report_id"]
        == "finance_v26_221_parent_authority_report:f541f48e181f9321b65199cde12ab64164a51b0f39b71adf8cdccb1e6672a18c"
        and gate["evaluation_id"]
        == "finance_v26_221_gate_evaluation:ed9933daa4f86ef0a00760b59ab4ef8a28d8d6b8ba415500d03672e27d6adf41"
        and decision["decision_id"]
        == "finance_v26_221_parent_authority_decision:81788bd2cc588939d669a21a2ab441ae0b2f6dfabc5edfdc33d9f2e507f03f5f"
        and transition["transition_id"]
        == "finance_v26_221_transition:0748ae1619cd2868225ff139c78d3ff18589df5d3ad5b45f5e097071684fea85"
        and formal["freeze_id"]
        == "finance_v26_221_v209_formal_authority_freeze:3b86d17fbfb9fa5eaf352f186d5564616cf9c68246348f3f68874287cb267cf7"
        and relation["audit_id"]
        == "finance_v26_221_v209_relation_closure_audit:e949ea0535d7f5c16ef4282d39c4b66a477e763cc31c865efe8b7f5623b5960a"
        and condition["binding_id"]
        == "fresh_exact_v209_execution_condition_authoritative_parent_binding:226ac1cb40bb988af48eb740a3b4bb607afe802c933a37dc8b34868977327858"
        and composition["contract_id"]
        == "fresh_exact_v209_parent_authority_repaired_composition_contract:3945fea378cc05bc2108b950b61669152924e191aa0b562d14904ed94e77e813"
        and gate["passed_count"] == 8
        and gate["failed_count"] == 0
        and report["v220_authorization_consumed"] is False
        and report["v220_authorization_reusable"] is False
        and report["new_online_authorizations"] == 0
        and report["provider_calls"] == 0
    ):
        _fail("parent.v221", "exact v26.221 repaired authority differs")

    v209_root = repository_root / V209_DIR
    v209_manifest = _verify_formal_directory(
        v209_root,
        expected_file_count=21,
        expected_total_bytes=44_916_386,
        expected_member_count=20,
        expected_member_bytes=44_912_918,
        manifest_prefix="finance_v26_209_artifact_manifest:",
        root_prefix="finance_v26_209_artifact_root:",
    )
    catalog = _load(v209_root / "executable_runner_package_catalog.json")
    development_manifest = _load(v209_root / "executable_development_manifest.json")
    census = _load(v209_root / "executable_invocation_census.json")
    execution = _load(v209_root / "executable_execution_contract.json")
    implementation = _load(v209_root / "implementation_binding.json")
    v209_source = _load(v209_root / "source_identity.json")
    package_ids = tuple(sorted(item["package_id"] for item in catalog["packages"]))
    job_ids = tuple(sorted(item["job_id"] for item in development_manifest["jobs"]))
    coordinates = tuple(
        sorted(
            (
                item["job_id"],
                item["phase"],
                item["invocation_index"],
                item["component_key"] or "",
            )
            for item in census["rows"]
        )
    )
    namespaces = {
        name: tuple(sorted(item[f"{name}_namespace"] for item in development_manifest["jobs"]))
        for name in ("raw", "result", "trace", "outcome")
    }
    if not (
        v209_manifest["manifest_id"] == models.V209_MANIFEST_ID
        and v209_manifest["artifact_root"] == models.V209_ARTIFACT_ROOT
        and formal["exact_artifact_manifest_id"] == v209_manifest["manifest_id"]
        and formal["exact_artifact_root"] == v209_manifest["artifact_root"]
        and formal["members"] == v209_manifest["members"]
        and relation["package_catalog_id"] == catalog["catalog_id"]
        and relation["manifest_id"] == development_manifest["manifest_id"]
        and relation["runner_id"] == execution["runner_id"]
        and relation["execution_contract_id"] == execution["contract_id"]
        and relation["invocation_census_id"] == census["census_id"]
        and relation["implementation_id"] == implementation["implementation_id"]
        and relation["source_identity_id"] == v209_source["source_identity_id"]
        and package_ids == tuple(relation["exact_package_ids"])
        and job_ids == tuple(relation["exact_job_ids"])
        and models.canonical_sha256(package_ids) == relation["exact_package_set_sha256"]
        and models.canonical_sha256(job_ids) == relation["exact_job_set_sha256"]
        and models.canonical_sha256(coordinates) == relation["exact_coordinate_set_sha256"]
        and models.canonical_sha256(namespaces["raw"]) == relation["raw_namespace_set_sha256"]
        and models.canonical_sha256(namespaces["result"]) == relation["result_namespace_set_sha256"]
        and models.canonical_sha256(namespaces["trace"]) == relation["trace_namespace_set_sha256"]
        and models.canonical_sha256(namespaces["outcome"])
        == relation["outcome_namespace_set_sha256"]
        and len(package_ids) == 32
        and len(job_ids) == 192
        and len(coordinates) == len(set(coordinates)) == 792
        and all(len(value) == len(set(value)) == 192 for value in namespaces.values())
    ):
        _fail("parent.v209", "exact v26.209 authority or relation differs")

    v220_root = repository_root / V220_DIR
    v220_manifest = _verify_formal_directory(
        v220_root,
        expected_file_count=18,
        expected_total_bytes=126_513,
        expected_member_count=17,
        expected_member_bytes=123_577,
        manifest_prefix="finance_v26_220_artifact_manifest:",
        root_prefix="finance_v26_220_artifact_root:",
    )
    retained_v220_composition = _load(v220_root / "online_execution_composition_contract.json")
    if not (
        v220_manifest["manifest_id"] == v220_freeze["v220_artifact_manifest_id"]
        and v220_manifest["artifact_root"] == v220_freeze["v220_artifact_root"]
        and retained_v220_composition["contract_id"] == v220_freeze["v220_composition_contract_id"]
        and retained_v220_composition["v218_parent_set_binding_id"]
        == "fresh_repaired_v218_complete_parent_set_binding:846e8dfe38552fdde9763e4cfbb17a4170b3a1dd9bca9e20693b21238dd2f20c"
    ):
        _fail("parent.v220_composition", "retained v26.220 Composition differs")

    expected_condition: dict[str, Any] = {
        "binding_id": "pending",
        "v220_freeze_id": formal["v220_freeze_id"],
        "v209_formal_freeze_id": formal["freeze_id"],
        "relation_closure_audit_id": relation["audit_id"],
        "exact_v209_artifact_manifest_id": formal["exact_artifact_manifest_id"],
        "exact_v209_artifact_root": formal["exact_artifact_root"],
        "formal_member_set_sha256": formal["formal_member_set_sha256"],
        "package_catalog_id": relation["package_catalog_id"],
        "manifest_id": relation["manifest_id"],
        "runner_id": relation["runner_id"],
        "execution_contract_id": relation["execution_contract_id"],
        "invocation_census_id": relation["invocation_census_id"],
        "implementation_id": relation["implementation_id"],
        "source_identity_id": relation["source_identity_id"],
        "exact_package_ids": relation["exact_package_ids"],
        "exact_job_ids": relation["exact_job_ids"],
        "exact_package_set_sha256": relation["exact_package_set_sha256"],
        "exact_job_set_sha256": relation["exact_job_set_sha256"],
        "exact_coordinate_set_sha256": relation["exact_coordinate_set_sha256"],
        "raw_namespace_set_sha256": relation["raw_namespace_set_sha256"],
        "result_namespace_set_sha256": relation["result_namespace_set_sha256"],
        "trace_namespace_set_sha256": relation["trace_namespace_set_sha256"],
        "outcome_namespace_set_sha256": relation["outcome_namespace_set_sha256"],
        "exact_package_count": 32,
        "exact_job_count": 192,
        "exact_coordinate_count": 792,
        "previous_v220_condition_binding_id": v220_freeze["v220_condition_binding_id"],
        "previous_v220_condition_authority_superseded": True,
        "current_v220_authorization_consumed": False,
        "current_v220_authorization_reusable": False,
        "new_online_authorization_created": False,
        "provider_calls": 0,
        "schema_version": condition["schema_version"],
    }
    expected_condition["binding_id"] = _object_identity(
        expected_condition,
        "binding_id",
        "fresh_exact_v209_execution_condition_authoritative_parent_binding:",
    )
    expected_composition: dict[str, Any] = {
        "contract_id": "pending",
        "v220_freeze_id": v220_freeze["freeze_id"],
        "authoritative_condition_binding_id": expected_condition["binding_id"],
        "v218_parent_set_binding_id": retained_v220_composition["v218_parent_set_binding_id"],
        "retained_v220_composition_contract_id": retained_v220_composition["contract_id"],
        "exact_v209_artifact_manifest_id": formal["exact_artifact_manifest_id"],
        "exact_v209_artifact_root": formal["exact_artifact_root"],
        "exact_v209_formal_member_set_sha256": formal["formal_member_set_sha256"],
        "relation_closure_required_before_authorization": True,
        "v209_formal_admission_required_before_condition_construction": True,
        "current_v220_authorization_forbidden": True,
        "fresh_authorization_required_after_independent_audit": True,
        "caller_terminal_forbidden": True,
        "unbound_terminal_source_fails_closed": True,
        "provider_calls": 0,
        "schema_version": composition["schema_version"],
    }
    expected_composition["contract_id"] = _object_identity(
        expected_composition,
        "contract_id",
        "fresh_exact_v209_parent_authority_repaired_composition_contract:",
    )
    if expected_condition != condition:
        _fail("parent.condition_reconstruction", "complete v26.221 Condition differs")
    if expected_composition != composition:
        _fail("parent.composition_reconstruction", "complete v26.221 Composition differs")

    parent_ids = tuple(
        sorted(
            {
                manifest["manifest_id"],
                manifest["artifact_root"],
                report["report_id"],
                gate["evaluation_id"],
                decision["decision_id"],
                transition["transition_id"],
                formal["freeze_id"],
                relation["audit_id"],
                condition["binding_id"],
                composition["contract_id"],
                data["upstream_tamper_audit"]["audit_id"],
                data["scope_boundary_audit"]["audit_id"],
                data["implementation_binding"]["binding_id"],
                source["source_identity_id"],
                v220_freeze["freeze_id"],
                retained_v220_composition["v218_parent_set_binding_id"],
                retained_v220_composition["contract_id"],
                formal["exact_artifact_manifest_id"],
                formal["exact_artifact_root"],
            }
        )
    )
    return cast(
        models.V221RepairedParentBinding,
        _make(
            models.V221RepairedParentBinding,
            {
                "v222_freeze_id": v222_freeze_id,
                "v221_source_commit": source["source_commit"],
                "v221_source_tree": source["source_tree"],
                "v221_artifact_manifest_id": manifest["manifest_id"],
                "v221_artifact_root": manifest["artifact_root"],
                "v221_report_id": report["report_id"],
                "v221_gate_id": gate["evaluation_id"],
                "v221_decision_id": decision["decision_id"],
                "v221_transition_id": transition["transition_id"],
                "v209_formal_freeze_id": formal["freeze_id"],
                "relation_closure_audit_id": relation["audit_id"],
                "authoritative_condition_binding_id": condition["binding_id"],
                "repaired_composition_contract_id": composition["contract_id"],
                "v218_parent_set_binding_id": composition["v218_parent_set_binding_id"],
                "retained_v220_composition_contract_id": composition[
                    "retained_v220_composition_contract_id"
                ],
                "exact_v209_artifact_manifest_id": formal["exact_artifact_manifest_id"],
                "exact_v209_artifact_root": formal["exact_artifact_root"],
                "exact_v209_formal_member_set_sha256": formal["formal_member_set_sha256"],
                "package_catalog_id": relation["package_catalog_id"],
                "manifest_id": relation["manifest_id"],
                "runner_id": relation["runner_id"],
                "execution_contract_id": relation["execution_contract_id"],
                "invocation_census_id": relation["invocation_census_id"],
                "implementation_id": relation["implementation_id"],
                "source_identity_id": relation["source_identity_id"],
                "exact_package_ids": package_ids,
                "exact_job_ids": job_ids,
                "exact_package_set_sha256": relation["exact_package_set_sha256"],
                "exact_job_set_sha256": relation["exact_job_set_sha256"],
                "exact_coordinate_set_sha256": relation["exact_coordinate_set_sha256"],
                "raw_namespace_set_sha256": relation["raw_namespace_set_sha256"],
                "result_namespace_set_sha256": relation["result_namespace_set_sha256"],
                "trace_namespace_set_sha256": relation["trace_namespace_set_sha256"],
                "outcome_namespace_set_sha256": relation["outcome_namespace_set_sha256"],
                "condition_field_count": len(condition),
                "condition_field_match_count": len(condition),
                "composition_field_count": len(composition),
                "composition_field_match_count": len(composition),
                "exact_parent_ids": parent_ids,
                "exact_parent_set_sha256": models.canonical_sha256(parent_ids),
                "exact_parent_count": len(parent_ids),
                "v220_authorization_id": models.V220_AUTHORIZATION_ID,
            },
            "binding_id",
            "fresh_v221_complete_repaired_parent_binding:",
        ),
    )


def _composition(
    *,
    freeze: models.V222IndependentAuditFreeze,
    parents: models.V221RepairedParentBinding,
) -> models.OnlineExecutionCompositionContract:
    main_terminals = tuple(
        sorted(
            (
                "completed_invalid",
                "completed_qualified",
                "correction_action_reference_invalid",
                "correction_attempt_typed_invalid",
                "correction_response_abi_invalid",
                "final_response_abi_invalid",
                "first_action_reference_invalid",
                "first_response_abi_invalid",
            )
        )
    )
    return cast(
        models.OnlineExecutionCompositionContract,
        _make(
            models.OnlineExecutionCompositionContract,
            {
                "v222_freeze_id": freeze.freeze_id,
                "v221_parent_binding_id": parents.binding_id,
                "authoritative_condition_binding_id": parents.authoritative_condition_binding_id,
                "repaired_composition_contract_id": parents.repaired_composition_contract_id,
                "v218_parent_set_binding_id": parents.v218_parent_set_binding_id,
                "retained_v220_composition_contract_id": parents.retained_v220_composition_contract_id,
                "exact_v209_artifact_manifest_id": parents.exact_v209_artifact_manifest_id,
                "exact_v209_artifact_root": parents.exact_v209_artifact_root,
                "main_observation_terminal_kinds": main_terminals,
                "source_bound_failure_terminal_kinds": (
                    "instrument_failure",
                    "privacy_rejection",
                ),
            },
            "contract_id",
            "fresh_exact_v209_parent_bound_online_execution_composition_contract:",
        ),
    )


def _authorization(
    *,
    external: models.ExternalOnlineAuthorizationDecision,
    freeze: models.V222IndependentAuditFreeze,
    parents: models.V221RepairedParentBinding,
    composition: models.OnlineExecutionCompositionContract,
) -> models.ExactOnlineExecutionAuthorization:
    return cast(
        models.ExactOnlineExecutionAuthorization,
        _make(
            models.ExactOnlineExecutionAuthorization,
            {
                "external_decision_id": external.decision_id,
                "v222_freeze_id": freeze.freeze_id,
                "v221_parent_binding_id": parents.binding_id,
                "authoritative_condition_binding_id": parents.authoritative_condition_binding_id,
                "repaired_composition_contract_id": parents.repaired_composition_contract_id,
                "composition_contract_id": composition.contract_id,
                "v218_parent_set_binding_id": parents.v218_parent_set_binding_id,
                "exact_v209_artifact_manifest_id": parents.exact_v209_artifact_manifest_id,
                "exact_v209_artifact_root": parents.exact_v209_artifact_root,
                "v209_manifest_id": parents.manifest_id,
                "v209_runner_id": parents.runner_id,
                "v209_execution_contract_id": parents.execution_contract_id,
                "exact_package_ids": parents.exact_package_ids,
                "exact_job_ids": parents.exact_job_ids,
                "exact_package_set_sha256": parents.exact_package_set_sha256,
                "exact_job_set_sha256": parents.exact_job_set_sha256,
                "exact_coordinate_set_sha256": parents.exact_coordinate_set_sha256,
                "raw_namespace_set_sha256": parents.raw_namespace_set_sha256,
                "result_namespace_set_sha256": parents.result_namespace_set_sha256,
                "trace_namespace_set_sha256": parents.trace_namespace_set_sha256,
                "outcome_namespace_set_sha256": parents.outcome_namespace_set_sha256,
            },
            "authorization_id",
            "fresh_exact_v209_parent_bound_exact_online_execution_authorization:",
        ),
    )


def _request(authorization: models.ExactOnlineExecutionAuthorization) -> dict[str, Any]:
    return {
        "authorization": authorization,
        "authorization_bytes": models.canonical_bytes(authorization),
        "requested_stage": authorization.authorized_stage,
        "requested_v222_freeze_id": authorization.v222_freeze_id,
        "requested_v221_parent_binding_id": authorization.v221_parent_binding_id,
        "requested_condition_binding_id": authorization.authoritative_condition_binding_id,
        "requested_repaired_composition_contract_id": authorization.repaired_composition_contract_id,
        "requested_composition_contract_id": authorization.composition_contract_id,
        "requested_v218_parent_set_binding_id": authorization.v218_parent_set_binding_id,
        "requested_v209_artifact_manifest_id": authorization.exact_v209_artifact_manifest_id,
        "requested_v209_artifact_root": authorization.exact_v209_artifact_root,
        "requested_manifest_id": authorization.v209_manifest_id,
        "requested_runner_id": authorization.v209_runner_id,
        "requested_execution_contract_id": authorization.v209_execution_contract_id,
        "requested_package_ids": authorization.exact_package_ids,
        "requested_job_ids": authorization.exact_job_ids,
        "requested_coordinate_set_sha256": authorization.exact_coordinate_set_sha256,
        "requested_raw_namespace_set_sha256": authorization.raw_namespace_set_sha256,
        "requested_result_namespace_set_sha256": authorization.result_namespace_set_sha256,
        "requested_trace_namespace_set_sha256": authorization.trace_namespace_set_sha256,
        "requested_outcome_namespace_set_sha256": authorization.outcome_namespace_set_sha256,
        "provider_execution_requested": True,
    }


def _admission_audit(
    authorization: models.ExactOnlineExecutionAuthorization,
) -> models.PrecredentialAdmissionAudit:
    guard = models.PrecredentialAuthorizationGuard(
        expected_authorization=authorization,
        expected_authorization_bytes=models.canonical_bytes(authorization),
    )
    exact = _request(authorization)
    admission = guard.admit(**exact)
    cases: list[tuple[str, dict[str, Any]]] = [("exact_nonconsuming_probe", {})]
    cases.extend(
        (
            ("missing_authorization", {"authorization": None}),
            ("missing_authorization_bytes", {"authorization_bytes": None}),
            (
                "modified_authorization_bytes",
                {"authorization_bytes": models.canonical_bytes(authorization) + b"\n"},
            ),
            ("v220_authorization", {"v220_authorization_presented": True}),
            ("wrong_stage", {"requested_stage": models.CONSUMED_STAGE}),
            ("wrong_v222_freeze", {"requested_v222_freeze_id": "forged:v222"}),
            ("wrong_v221_parent", {"requested_v221_parent_binding_id": "forged:v221"}),
            ("wrong_condition", {"requested_condition_binding_id": "forged:condition"}),
            (
                "wrong_repaired_composition",
                {"requested_repaired_composition_contract_id": "forged:repair"},
            ),
            ("wrong_composition", {"requested_composition_contract_id": "forged:composition"}),
            ("wrong_v218_parent", {"requested_v218_parent_set_binding_id": "forged:v218"}),
            (
                "wrong_v209_artifact_manifest",
                {"requested_v209_artifact_manifest_id": "forged:artifact-manifest"},
            ),
            ("wrong_v209_artifact_root", {"requested_v209_artifact_root": "forged:root"}),
            ("wrong_manifest", {"requested_manifest_id": "forged:manifest"}),
            ("wrong_runner", {"requested_runner_id": "forged:runner"}),
            (
                "wrong_execution_contract",
                {"requested_execution_contract_id": "forged:execution"},
            ),
            (
                "wrong_package_set",
                {"requested_package_ids": authorization.exact_package_ids[:-1]},
            ),
            ("wrong_job_set", {"requested_job_ids": authorization.exact_job_ids[:-1]}),
            ("wrong_coordinate_set", {"requested_coordinate_set_sha256": "0" * 64}),
            ("wrong_raw_namespaces", {"requested_raw_namespace_set_sha256": "0" * 64}),
            (
                "wrong_result_namespaces",
                {"requested_result_namespace_set_sha256": "0" * 64},
            ),
            ("wrong_trace_namespaces", {"requested_trace_namespace_set_sha256": "0" * 64}),
            (
                "wrong_outcome_namespaces",
                {"requested_outcome_namespace_set_sha256": "0" * 64},
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
        admitted = False
        reason: str | None = None
        try:
            guard.admit(**{**exact, **changes})
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
                    "finance_v26_223_precredential_admission_control:",
                ),
            )
        )
    invalid = sum(item.rejected for item in controls)
    return cast(
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
            "finance_v26_223_precredential_admission_audit:",
        ),
    )


def _parent_attack_audit(
    authorization: models.ExactOnlineExecutionAuthorization,
) -> models.ParentAttackAudit:
    guard = models.PrecredentialAuthorizationGuard(
        expected_authorization=authorization,
        expected_authorization_bytes=models.canonical_bytes(authorization),
    )
    replaced_packages = tuple(sorted(("forged:package", *authorization.exact_package_ids[1:])))
    replaced_jobs = tuple(sorted(("forged:job", *authorization.exact_job_ids[1:])))
    mutations: tuple[tuple[str, dict[str, Any]], ...] = (
        ("v222_freeze_replacement", {"v222_freeze_id": "forged:v222"}),
        ("v221_parent_replacement", {"v221_parent_binding_id": "forged:v221"}),
        (
            "condition_replacement",
            {"authoritative_condition_binding_id": "forged:condition"},
        ),
        (
            "repaired_composition_replacement",
            {"repaired_composition_contract_id": "forged:repair"},
        ),
        ("composition_replacement", {"composition_contract_id": "forged:composition"}),
        ("v218_parent_replacement", {"v218_parent_set_binding_id": "forged:v218"}),
        (
            "v209_artifact_manifest_replacement",
            {"exact_v209_artifact_manifest_id": "forged:artifact-manifest"},
        ),
        ("v209_artifact_root_replacement", {"exact_v209_artifact_root": "forged:root"}),
        (
            "package_set_replacement",
            {
                "exact_package_ids": replaced_packages,
                "exact_package_set_sha256": models.canonical_sha256(replaced_packages),
            },
        ),
        (
            "job_set_replacement",
            {
                "exact_job_ids": replaced_jobs,
                "exact_job_set_sha256": models.canonical_sha256(replaced_jobs),
            },
        ),
        ("coordinate_set_replacement", {"exact_coordinate_set_sha256": "0" * 64}),
        ("raw_namespace_replacement", {"raw_namespace_set_sha256": "0" * 64}),
        ("result_namespace_replacement", {"result_namespace_set_sha256": "0" * 64}),
        ("trace_namespace_replacement", {"trace_namespace_set_sha256": "0" * 64}),
        ("outcome_namespace_replacement", {"outcome_namespace_set_sha256": "0" * 64}),
    )
    attacks: list[models.ParentAttack] = []
    for name, changes in mutations:
        values = authorization.model_dump(
            mode="python", exclude={"authorization_id"}, warnings=False
        )
        values.update(changes)
        mutated = cast(
            models.ExactOnlineExecutionAuthorization,
            _make(
                models.ExactOnlineExecutionAuthorization,
                values,
                "authorization_id",
                "fresh_exact_v209_parent_bound_exact_online_execution_authorization:",
            ),
        )
        reason: str | None = None
        try:
            guard.admit(**_request(mutated))
        except ValueError as error:
            reason = _sha(str(error).encode("utf-8"))
        if reason is None:
            _fail("negative.parent_attack", f"fully rehashed parent accepted:{name}")
        attacks.append(
            cast(
                models.ParentAttack,
                _make(
                    models.ParentAttack,
                    {
                        "attack_name": name,
                        "mutated_authorization_id": mutated.authorization_id,
                        "rejection_reason_sha256": reason,
                    },
                    "attack_id",
                    "finance_v26_223_fully_rehashed_parent_attack:",
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
                "fully_rehashed_object_count": len(attacks),
                "rejected_attack_count": len(attacks),
            },
            "audit_id",
            "finance_v26_223_parent_attack_audit:",
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
            "finance_v26_223_source_identity:",
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
        tree = _git(repository_root, "rev-parse", f"{source.source_commit}^{{tree}}")
        if tree.decode().strip() != source.source_tree:
            _fail("source.tree", "v26.223 source tree differs")
    files: list[models.SourceFile] = []
    for relative_path in source.implementation_files:
        payload = (
            _git(repository_root, "show", f"{source.source_commit}:{relative_path}")
            if use_commit
            else (repository_root / relative_path).read_bytes()
        )
        if use_commit and payload != (repository_root / relative_path).read_bytes():
            _fail("source.working_tree", f"v26.223 source file differs:{relative_path}")
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
                "v222_freeze_id": freeze_id,
                "files": tuple(files),
                "guard_symbol_sha256": _sha(
                    inspect.getsource(models.PrecredentialAuthorizationGuard).encode("utf-8")
                ),
                "build_symbol_sha256": _sha(inspect.getsource(build).encode("utf-8")),
            },
            "binding_id",
            "fresh_exact_v209_parent_bound_online_authorization_implementation_binding:",
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
                "finance_v26_223_gate:",
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
            "finance_v26_223_gate_evaluation:",
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
    freeze = _v222_freeze(
        repository_root=repository_root, external_decision_id=external.decision_id
    )
    parents = _v221_parent_binding(repository_root=repository_root, v222_freeze_id=freeze.freeze_id)
    composition = _composition(freeze=freeze, parents=parents)
    authorization = _authorization(
        external=external,
        freeze=freeze,
        parents=parents,
        composition=composition,
    )
    admission = _admission_audit(authorization)
    attacks = _parent_attack_audit(authorization)
    scope = cast(
        models.ScopeBoundaryAudit,
        _make(
            models.ScopeBoundaryAudit,
            {"authorization_id": authorization.authorization_id},
            "audit_id",
            "finance_v26_223_scope_boundary_audit:",
        ),
    )
    gate = _gate(
        (
            ("G0_external_scope_and_exact_v222_freeze", freeze.freeze_id),
            ("G1_complete_v221_repaired_parent_binding", parents.binding_id),
            (
                "G2_complete_condition_and_composition_reconstruction",
                parents.repaired_composition_contract_id,
            ),
            ("G3_exact_v209_condition_sets_and_relations", parents.relation_closure_audit_id),
            ("G4_fresh_exact_online_authorization", authorization.authorization_id),
            ("G5_precredential_admission_and_v220_rejection", admission.audit_id),
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
                "v222_freeze_id": freeze.freeze_id,
                "v221_parent_binding_id": parents.binding_id,
                "composition_contract_id": composition.contract_id,
                "authorization_id": authorization.authorization_id,
                "admission_audit_id": admission.audit_id,
                "parent_attack_audit_id": attacks.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
            },
            "decision_id",
            "finance_v26_223_online_authorization_decision:",
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
            "finance_v26_223_transition:",
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
                "v222_freeze_id": freeze.freeze_id,
                "v221_parent_binding_id": parents.binding_id,
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
            "finance_v26_223_online_authorization_report:",
        ),
    )
    payloads = {
        "decision.json": _bytes(decision),
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
        "v221_repaired_parent_binding.json": _bytes(parents),
        "v222_freeze.json": _bytes(freeze),
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
