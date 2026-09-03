# ruff: noqa: E501
from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_authority_repair_independent_audit_models as models,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = (
    "finance_v26_222_fresh_exact_v209_execution_condition_authoritative_parent_"
    "binding_repair_preflight_independent_audit_v1_20260903"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_REVIEW_SHA256: Final = "3c687f46977a555a3f71d6759e6cd1c1de1117b7ea9e99e3d22e52e7afa1e318"
EXTERNAL_REVIEW_BYTES: Final = 14_613
OPERATOR_DIRECTIVE: Final = "参照审计报告继续实验修订"
V221_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_221_fresh_exact_v209_execution_condition_authoritative_parent_"
    "binding_repair_preflight_v1_20260903"
)
V209_DIR: Final = (
    "trusted_data_synthesis/artifacts/vtdo_experiment/"
    "finance_v26_209_fresh_repaired_full_condition_executable_runner_final_"
    "request_contract_continuity_repair_preflight_v1_20260902"
)
MODELS_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_parent_authority_repair_independent_audit_models.py"
)
AUDIT_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_parent_authority_repair_independent_audit.py"
)
TEST_FILE: Final = (
    "trusted_data_synthesis/tests/"
    "test_v26_fresh_exact_v209_parent_authority_repair_independent_audit.py"
)
IMPLEMENTATION_FILES: Final = tuple(sorted((MODELS_FILE, AUDIT_FILE, TEST_FILE)))
V221_MODULE: Final = (
    "trusted_synthesis.experiments.vtdo_experiment."
    "phase1_v26_fresh_exact_v209_execution_condition_parent_authority_repair_preflight"
)
V209_SOURCE_COMMIT: Final = "5809e9782515e55ee797b43730584d5d860aaa5c"
V209_SOURCE_TREE: Final = "b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"
EVENT_SEQUENCE: Final = (
    "read_current_runtime_state",
    "compile_authoritative_messages",
    "build_canonical_request",
    "validate_request_and_certificate",
    "emit_pre_transport_receipt",
    "injected_transport_dispatch",
    "project_public_payload",
    "parse_exact_response",
    "validate_current_state_and_candidate_or_final_envelope",
    "runtime_step_or_finalize",
    "terminal_dispatch",
)
OBJECT_IDS: Final = {
    "catalog_id": "fresh_repaired_final_continuity_executable_full_condition_package_catalog:078c9b261f2d05cf6c9b44de7e04372886cf6c5b1f3083439c56433694141993",
    "manifest_id": "fresh_repaired_final_continuity_executable_full_condition_manifest:f73da35ef4bbc3cfb6c4782918985ef649d89b6d6d09831f35354154d23b9621",
    "runner_id": "fresh_repaired_final_continuity_executable_full_condition_runner:e58b8318667568b9becbb1fa946f1ac079937c9c744b6a2c4877661abebf0266",
    "contract_id": "fresh_repaired_final_continuity_executable_full_condition_execution_contract:fc10dce5cdb2a3f677c93ad0780b5aa2b2e22eb44d6a1bf3c1d43d11ac6540d4",
    "census_id": "finance_v26_209_executable_invocation_census:e93f0b9121399d37bf1ed32137437117d2aae989ab41682e09cdc0c489e72212",
    "implementation_id": "fresh_repaired_final_continuity_executable_route_implementation_binding:12c518f9f8f839d6c65a67c432c4177bc8ef95cb0188036796a08fd31c1b65e7",
    "source_identity_id": "finance_v26_209_source_identity:317d8cb091aab7495dc2c97ec9158fe92e46ba9f7386ab3c4acad912bf8f9f52",
}
IDENTITY_RULES: Final = {
    "artifact": ("manifest_id", "finance_v26_209_artifact_manifest:"),
    "implementation": (
        "implementation_id",
        "fresh_repaired_final_continuity_executable_route_implementation_binding:",
    ),
    "source": ("source_identity_id", "finance_v26_209_source_identity:"),
    "package": (
        "package_id",
        "fresh_repaired_final_continuity_executable_full_condition_runner_package:",
    ),
    "catalog": (
        "catalog_id",
        "fresh_repaired_final_continuity_executable_full_condition_package_catalog:",
    ),
    "job": (
        "job_id",
        "fresh_repaired_final_continuity_executable_full_condition_development_job:",
    ),
    "manifest": (
        "manifest_id",
        "fresh_repaired_final_continuity_executable_full_condition_manifest:",
    ),
    "runner": (
        "runner_id",
        "fresh_repaired_final_continuity_executable_full_condition_runner:",
    ),
    "execution": (
        "contract_id",
        "fresh_repaired_final_continuity_executable_full_condition_execution_contract:",
    ),
    "invocation": (
        "invocation_id",
        "fresh_repaired_final_continuity_executable_invocation_record:",
    ),
    "census": ("census_id", "finance_v26_209_executable_invocation_census:"),
}


class V222Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V222Error(stage, reason)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_bytes()))


def _load_bytes(payload: bytes) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(payload))


def _bytes(value: Any) -> bytes:
    return models.canonical_bytes(value) + b"\n"


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _all_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _git(repository_root: Path, *args: str) -> bytes:
    run = subprocess.run(("git", *args), cwd=repository_root, check=False, capture_output=True)
    if run.returncode:
        _fail("source.git", run.stderr.decode("utf-8", errors="replace"))
    return run.stdout


def _make(model_type: type[Any], values: dict[str, Any], field: str, prefix: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=prefix)


def _identity(document: dict[str, Any], field: str, prefix: str) -> str:
    return canonical_hash(
        {name: value for name, value in document.items() if name != field},
        prefix=prefix,
    )


def _require_identity(document: dict[str, Any], field: str, prefix: str, stage: str) -> None:
    if document.get(field) != _identity(document, field, prefix):
        _fail(stage, f"content identity differs:{field}")


@dataclass(frozen=True)
class SavedV221:
    root: Path
    files: dict[str, bytes]
    artifact: dict[str, Any]
    report: dict[str, Any]
    gate: dict[str, Any]
    decision: dict[str, Any]
    transition: dict[str, Any]
    source: dict[str, Any]
    formal: dict[str, Any]
    relations: dict[str, Any]
    condition: dict[str, Any]
    composition: dict[str, Any]
    attacks: dict[str, Any]


def _saved_v221(repository_root: Path) -> SavedV221:
    root = repository_root / V221_DIR
    files = _all_files(root)
    if len(files) != 17 or sum(map(len, files.values())) != 112_607:
        _fail("A0.v221_geometry", "v26.221 formal directory geometry differs")
    artifact = _load_bytes(files["artifact_manifest.json"])
    members = {item["relative_path"]: item for item in artifact["members"]}
    if (
        artifact["file_count"] != 16
        or artifact["total_byte_count"] != 109_876
        or set(members) != set(files) - {"artifact_manifest.json"}
    ):
        _fail("A0.v221_manifest", "v26.221 Manifest geometry differs")
    for name, member in members.items():
        payload = files[name]
        if len(payload) != member["byte_count"] or _sha(payload) != member["sha256"]:
            _fail("A0.v221_member", f"v26.221 member differs:{name}")
    expected_root = canonical_hash(
        tuple(artifact["members"]), prefix="finance_v26_221_artifact_root:"
    )
    _require_identity(
        artifact,
        "manifest_id",
        "finance_v26_221_artifact_manifest:",
        "A0.v221_manifest_identity",
    )
    if (
        expected_root != artifact["artifact_root"]
        or artifact["manifest_id"]
        != "finance_v26_221_artifact_manifest:c52e6edea3d097f7ac3797fcdc0cbc704a99174b7514b09e62265784ed6c189a"
        or artifact["artifact_root"]
        != "finance_v26_221_artifact_root:5782f2689c74fe1388f9f8b1f600e7b01ece3296a7abfc39265bb44b64cdb5f4"
    ):
        _fail("A0.v221_artifact_authority", "v26.221 Manifest or Root differs")
    saved = SavedV221(
        root=root,
        files=files,
        artifact=artifact,
        report=_load_bytes(files["report.json"]),
        gate=_load_bytes(files["gate_evaluation.json"]),
        decision=_load_bytes(files["decision.json"]),
        transition=_load_bytes(files["prospective_transition.json"]),
        source=_load_bytes(files["source_identity.json"]),
        formal=_load_bytes(files["v209_formal_authority_freeze.json"]),
        relations=_load_bytes(files["relation_closure_audit.json"]),
        condition=_load_bytes(files["authoritative_execution_condition_binding.json"]),
        composition=_load_bytes(files["repaired_composition_contract.json"]),
        attacks=_load_bytes(files["upstream_tamper_audit.json"]),
    )
    exact = {
        "report_id": "finance_v26_221_parent_authority_report:f541f48e181f9321b65199cde12ab64164a51b0f39b71adf8cdccb1e6672a18c",
        "gate_id": "finance_v26_221_gate_evaluation:ed9933daa4f86ef0a00760b59ab4ef8a28d8d6b8ba415500d03672e27d6adf41",
        "decision_id": "finance_v26_221_parent_authority_decision:81788bd2cc588939d669a21a2ab441ae0b2f6dfabc5edfdc33d9f2e507f03f5f",
        "transition_id": "finance_v26_221_transition:0748ae1619cd2868225ff139c78d3ff18589df5d3ad5b45f5e097071684fea85",
        "formal_id": "finance_v26_221_v209_formal_authority_freeze:3b86d17fbfb9fa5eaf352f186d5564616cf9c68246348f3f68874287cb267cf7",
        "relations_id": "finance_v26_221_v209_relation_closure_audit:e949ea0535d7f5c16ef4282d39c4b66a477e763cc31c865efe8b7f5623b5960a",
        "condition_id": "fresh_exact_v209_execution_condition_authoritative_parent_binding:226ac1cb40bb988af48eb740a3b4bb607afe802c933a37dc8b34868977327858",
        "composition_id": "fresh_exact_v209_parent_authority_repaired_composition_contract:3945fea378cc05bc2108b950b61669152924e191aa0b562d14904ed94e77e813",
        "attacks_id": "finance_v26_221_upstream_tamper_audit:6306cd29f2589166599e88b6d386229fbd4af7ced0f6f7105c2c8f0f6d29f2a8",
    }
    if (
        saved.source["source_commit"] != models.V221_COMMIT
        or saved.source["source_tree"] != models.V221_TREE
        or saved.report["report_id"] != exact["report_id"]
        or saved.gate["evaluation_id"] != exact["gate_id"]
        or saved.decision["decision_id"] != exact["decision_id"]
        or saved.transition["transition_id"] != exact["transition_id"]
        or saved.formal["freeze_id"] != exact["formal_id"]
        or saved.relations["audit_id"] != exact["relations_id"]
        or saved.condition["binding_id"] != exact["condition_id"]
        or saved.composition["contract_id"] != exact["composition_id"]
        or saved.attacks["audit_id"] != exact["attacks_id"]
        or saved.report["v220_authorization_consumed"] is not False
        or saved.report["v220_authorization_reusable"] is not False
        or saved.report["new_online_authorizations"] != 0
        or saved.report["provider_calls"] != 0
        or saved.transition["next_stage"] != models.CONSUMED_STAGE
        or saved.transition["next_stage_authorized"] is not False
        or saved.transition["provider_execution_authorized"] is not False
    ):
        _fail("A0.v221_authority", "v26.221 frozen authority differs")
    tree = _git(repository_root, "rev-parse", f"{models.V221_COMMIT}^{{tree}}").decode().strip()
    if tree != models.V221_TREE:
        _fail("A0.v221_source", "v26.221 source commit or tree differs")
    return saved


def _authorization(
    review_path: Path,
) -> tuple[models.ExternalIndependentAuditAuthorization, bytes, bytes]:
    review = review_path.read_bytes()
    if len(review) != EXTERNAL_REVIEW_BYTES or _sha(review) != EXTERNAL_REVIEW_SHA256:
        _fail("A0.authorization", "v26.222 external review bytes differ")
    directive = OPERATOR_DIRECTIVE.encode("utf-8")
    return (
        cast(
            models.ExternalIndependentAuditAuthorization,
            _make(
                models.ExternalIndependentAuditAuthorization,
                {
                    "review_sha256": _sha(review),
                    "review_byte_count": len(review),
                    "operator_directive_sha256": _sha(directive),
                    "operator_directive_byte_count": len(directive),
                },
                "authorization_id",
                "finance_v26_222_external_independent_audit_authorization:",
            ),
        ),
        review,
        directive,
    )


def _freeze(authorization_id: str, saved: SavedV221) -> models.V221Freeze:
    return cast(
        models.V221Freeze,
        _make(
            models.V221Freeze,
            {
                "external_authorization_id": authorization_id,
                "v221_artifact_manifest_id": saved.artifact["manifest_id"],
                "v221_artifact_root": saved.artifact["artifact_root"],
                "v221_report_id": saved.report["report_id"],
                "v221_gate_id": saved.gate["evaluation_id"],
                "v221_decision_id": saved.decision["decision_id"],
                "v221_transition_id": saved.transition["transition_id"],
                "v221_formal_freeze_id": saved.formal["freeze_id"],
                "v221_relation_audit_id": saved.relations["audit_id"],
                "v221_condition_binding_id": saved.condition["binding_id"],
                "v221_composition_contract_id": saved.composition["contract_id"],
                "v221_tamper_audit_id": saved.attacks["audit_id"],
                "v221_decision": saved.report["decision"],
            },
            "freeze_id",
            "finance_v26_222_v221_freeze:",
        ),
    )


def _detached_rebuild(
    *, repository_root: Path, saved: SavedV221, freeze_id: str
) -> models.DetachedRebuildAudit:
    with tempfile.TemporaryDirectory(prefix="finance-v26-222-detached-") as temporary:
        temporary_root = Path(temporary)
        archive = temporary_root / "source.tar"
        snapshot = temporary_root / "snapshot"
        output = temporary_root / "rebuilt"
        snapshot.mkdir()
        archive_run = subprocess.run(
            (
                "git",
                "archive",
                "--format=tar",
                f"--output={archive}",
                models.V221_COMMIT,
                "trusted_data_synthesis/src",
            ),
            cwd=repository_root,
            check=False,
            capture_output=True,
        )
        if archive_run.returncode:
            _fail(
                "A1.archive",
                archive_run.stderr.decode("utf-8", errors="replace"),
            )
        with tarfile.open(archive, "r") as stream:
            stream.extractall(snapshot, filter="data")
        archived_source_files = _all_files(snapshot / "trusted_data_synthesis" / "src")
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(snapshot / "trusted_data_synthesis" / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "C.UTF-8",
        }
        run = subprocess.run(
            (
                sys.executable,
                "-m",
                V221_MODULE,
                "--repository-root",
                str(repository_root),
                "--output-dir",
                str(output),
                "--external-review",
                str(saved.root / "external_review.txt"),
                "--source-commit",
                models.V221_COMMIT,
                "--source-tree",
                models.V221_TREE,
            ),
            cwd=snapshot,
            env=environment,
            check=False,
            capture_output=True,
        )
        if run.returncode:
            _fail("A1.detached_builder", run.stderr.decode("utf-8", errors="replace"))
        rebuilt = _all_files(output)
        paths = set(rebuilt) & set(saved.files)
        path_matches = len(saved.files) if set(rebuilt) == set(saved.files) else 0
        sha_matches = sum(_sha(rebuilt[name]) == _sha(saved.files[name]) for name in paths)
        byte_count_matches = sum(len(rebuilt[name]) == len(saved.files[name]) for name in paths)
        actual_matches = sum(rebuilt[name] == saved.files[name] for name in paths)
        rebuilt_manifest = _load_bytes(rebuilt["artifact_manifest.json"])
        manifest_revalidations = sum(
            len(rebuilt[item["relative_path"]]) == item["byte_count"]
            and _sha(rebuilt[item["relative_path"]]) == item["sha256"]
            for item in rebuilt_manifest["members"]
        )
        if (
            len(rebuilt) != 17
            or sum(map(len, rebuilt.values())) != 112_607
            or path_matches != 17
            or sha_matches != 17
            or byte_count_matches != 17
            or actual_matches != 17
            or manifest_revalidations != 16
        ):
            _fail("A1.detached_comparison", "v26.221 detached rebuild differs")
    return cast(
        models.DetachedRebuildAudit,
        _make(
            models.DetachedRebuildAudit,
            {
                "freeze_id": freeze_id,
                "archived_source_file_count": len(archived_source_files),
            },
            "audit_id",
            "finance_v26_222_detached_rebuild_audit:",
        ),
    )


@dataclass(frozen=True)
class IndependentV209:
    files: dict[str, bytes]
    artifact: dict[str, Any]
    catalog: dict[str, Any]
    manifest: dict[str, Any]
    runner: dict[str, Any]
    execution: dict[str, Any]
    census: dict[str, Any]
    implementation: dict[str, Any]
    source: dict[str, Any]
    member_set_sha256: str
    package_ids: tuple[str, ...]
    job_ids: tuple[str, ...]
    coordinates: tuple[tuple[str, str, int, str], ...]
    namespaces: dict[str, tuple[str, ...]]


def _independent_exact_member_admission(files: dict[str, bytes]) -> dict[str, Any]:
    artifact = _load_bytes(files["artifact_manifest.json"])
    expected_root = canonical_hash(
        tuple(artifact["members"]), prefix="finance_v26_209_artifact_root:"
    )
    if (
        artifact.get("manifest_id") != models.V209_MANIFEST_ID
        or artifact.get("artifact_root") != models.V209_ROOT
        or expected_root != models.V209_ROOT
        or _identity(artifact, "manifest_id", "finance_v26_209_artifact_manifest:")
        != models.V209_MANIFEST_ID
    ):
        _fail(
            "independent_exact_v209_manifest_root_admission",
            "candidate v26.209 Manifest or Root differs",
        )
    members = {item["relative_path"]: item for item in artifact["members"]}
    if set(members) != set(files) - {"artifact_manifest.json"}:
        _fail("independent_exact_v209_member_admission", "candidate path set differs")
    for name, member in members.items():
        payload = files[name]
        if len(payload) != member["byte_count"] or _sha(payload) != member["sha256"]:
            _fail(
                "independent_exact_v209_member_admission",
                f"candidate member differs:{name}",
            )
    return artifact


def _independent_v209_authority(
    *, repository_root: Path, saved: SavedV221, freeze_id: str
) -> tuple[models.IndependentV209AuthorityAudit, IndependentV209]:
    root = repository_root / V209_DIR
    files = _all_files(root)
    if len(files) != 21 or sum(map(len, files.values())) != 44_916_386:
        _fail("A2.v209_geometry", "v26.209 formal directory geometry differs")
    artifact = _independent_exact_member_admission(files)
    if artifact["file_count"] != 20 or artifact["total_byte_count"] != 44_912_918:
        _fail("A2.v209_manifest_geometry", "v26.209 Manifest geometry differs")
    catalog = _load_bytes(files["executable_runner_package_catalog.json"])
    manifest = _load_bytes(files["executable_development_manifest.json"])
    runner = _load_bytes(files["executable_runner_contract.json"])
    execution = _load_bytes(files["executable_execution_contract.json"])
    census = _load_bytes(files["executable_invocation_census.json"])
    implementation = _load_bytes(files["implementation_binding.json"])
    source = _load_bytes(files["source_identity.json"])
    identity_matches = 0
    for name, document in (
        ("artifact", artifact),
        ("implementation", implementation),
        ("source", source),
    ):
        field, prefix = IDENTITY_RULES[name]
        if document[field] != _identity(document, field, prefix):
            _fail("A2.object_identity", f"v26.209 {name} identity differs")
        identity_matches += 1
    packages = catalog["packages"]
    if (
        len(packages) != 32
        or catalog["package_count"] != 32
        or len({item["package_id"] for item in packages}) != 32
        or catalog["source_v206_package_ids"]
        != sorted(item["source_v206_package_id"] for item in packages)
        or any(len(item["schedule_ids"]) != len(item["component_keys"]) for item in packages)
    ):
        _fail("A2.package_semantics", "v26.209 Package Catalog semantics differ")
    for item in packages:
        field, prefix = IDENTITY_RULES["package"]
        if item[field] != _identity(item, field, prefix):
            _fail("A2.package_identity", f"v26.209 Package identity differs:{item[field]}")
        identity_matches += 1
    field, prefix = IDENTITY_RULES["catalog"]
    if catalog[field] != _identity(catalog, field, prefix):
        _fail("A2.catalog_identity", "v26.209 Catalog identity differs")
    identity_matches += 1
    jobs = manifest["jobs"]
    namespace_prefixes = {
        "raw": "fresh_repaired_final_continuity_executable_raw_namespace:",
        "result": "fresh_repaired_final_continuity_executable_result_namespace:",
        "trace": "fresh_repaired_final_continuity_executable_trace_namespace:",
        "outcome": "fresh_repaired_final_continuity_executable_outcome_namespace:",
    }
    if len(jobs) != 192 or manifest["job_count"] != 192:
        _fail("A2.job_geometry", "v26.209 Job geometry differs")
    for item in jobs:
        parent = {
            "source_v206_job_id": item["source_v206_job_id"],
            "package_id": item["package_id"],
            "implementation_id": item["implementation_id"],
            "repair_profile_id": item["repair_profile_id"],
            "replica_index": item["replica_index"],
        }
        for namespace, namespace_prefix in namespace_prefixes.items():
            if item[f"{namespace}_namespace"] != canonical_hash(parent, prefix=namespace_prefix):
                _fail("A2.namespace_owner", f"v26.209 namespace owner differs:{namespace}")
        if item["deterministic_seed_id"] != canonical_hash(
            parent,
            prefix="fresh_repaired_final_continuity_executable_deterministic_seed:",
        ):
            _fail("A2.deterministic_seed", "v26.209 deterministic seed differs")
        field, prefix = IDENTITY_RULES["job"]
        if item[field] != _identity(item, field, prefix):
            _fail("A2.job_identity", f"v26.209 Job identity differs:{item[field]}")
        identity_matches += 1
    job_ids = tuple(sorted(item["job_id"] for item in jobs))
    package_ids = tuple(sorted(item["package_id"] for item in packages))
    if (
        len(set(job_ids)) != 192
        or manifest["expected_job_ids"] != list(job_ids)
        or manifest["source_v206_job_ids"] != sorted(item["source_v206_job_id"] for item in jobs)
        or len({(item["package_id"], item["replica_index"]) for item in jobs}) != 192
        or any(
            len({item[f"{namespace}_namespace"] for item in jobs}) != 192
            for namespace in namespace_prefixes
        )
    ):
        _fail("A2.manifest_semantics", "v26.209 Manifest semantics differ")
    field, prefix = IDENTITY_RULES["manifest"]
    if manifest[field] != _identity(manifest, field, prefix):
        _fail("A2.manifest_identity", "v26.209 Development Manifest identity differs")
    identity_matches += 1
    for name, document in (("runner", runner), ("execution", execution)):
        field, prefix = IDENTITY_RULES[name]
        if document[field] != _identity(document, field, prefix):
            _fail("A2.object_identity", f"v26.209 {name} identity differs")
        identity_matches += 1
    phase_counts = {
        name: 0 for name in ("first_action", "subsequent_action", "correction", "final")
    }
    uniqueness_fields: dict[str, set[str]] = {
        name: set()
        for name in (
            "invocation_id",
            "prompt_id",
            "request_id",
            "certificate_id",
            "pre_transport_receipt_id",
        )
    }
    rows = census["rows"]
    if len(rows) != 792 or census["dynamic_invocation_count"] != 792:
        _fail("A2.census_geometry", "v26.209 Census geometry differs")
    for row in rows:
        message = row["canonical_messages_json"].encode("utf-8")
        request = row["canonical_request_body_json"].encode("utf-8")
        if (
            models.canonical_bytes(json.loads(message)) != message
            or models.canonical_bytes(json.loads(request)) != request
            or _sha(message) != row["canonical_messages_sha256"]
            or _sha(request) != row["canonical_request_body_sha256"]
            or len(message) != row["canonical_messages_byte_count"]
            or len(request) != row["canonical_request_body_byte_count"]
            or tuple(row["event_sequence"]) != EVENT_SEQUENCE
            or row["typed_terminal"] is not None
            or row["transport_dispatch_count"] != 1
            or row["direct_provider_calls"] != 0
            or row["empirical"] is not False
        ):
            _fail("A2.invocation_semantics", "v26.209 invocation bytes or order differ")
        if row["phase"] == "final":
            if (
                row["candidate_action_ids"]
                or row["selected_action_id"] is not None
                or row["action_accepted"] is not None
            ):
                _fail("A2.final_invocation", "v26.209 Final carries Action fields")
        elif not row["candidate_action_ids"]:
            _fail("A2.action_invocation", "v26.209 Action lacks Candidates")
        phase_counts[row["phase"]] += 1
        for name in uniqueness_fields:
            uniqueness_fields[name].add(row[name])
        field, prefix = IDENTITY_RULES["invocation"]
        if row[field] != _identity(row, field, prefix):
            _fail("A2.invocation_identity", f"v26.209 invocation identity differs:{row[field]}")
        identity_matches += 1
    if phase_counts != {
        "first_action": 192,
        "subsequent_action": 288,
        "correction": 120,
        "final": 192,
    } or any(len(values) != 792 for values in uniqueness_fields.values()):
        _fail("A2.census_semantics", "v26.209 Census phase or identity set differs")
    field, prefix = IDENTITY_RULES["census"]
    if census[field] != _identity(census, field, prefix):
        _fail("A2.census_identity", "v26.209 Census identity differs")
    identity_matches += 1
    if identity_matches != 1_024:
        _fail("A2.identity_total", "v26.209 identity-bearing total differs")
    if (
        source["source_commit"] != V209_SOURCE_COMMIT
        or source["source_tree"] != V209_SOURCE_TREE
        or implementation["source_commit"] != V209_SOURCE_COMMIT
        or implementation["source_tree"] != V209_SOURCE_TREE
        or tuple(source["implementation_files"]) != tuple(sorted(source["implementation_files"]))
        or tuple(item["relative_path"] for item in implementation["files"])
        != tuple(sorted(item["relative_path"] for item in implementation["files"]))
    ):
        _fail("A2.source_binding", "v26.209 source binding differs")
    actual_tree = (
        _git(repository_root, "rev-parse", f"{V209_SOURCE_COMMIT}^{{tree}}").decode().strip()
    )
    if actual_tree != V209_SOURCE_TREE:
        _fail("A2.source_tree", "v26.209 source tree differs")
    source_file_matches = 0
    for item in implementation["files"]:
        payload = _git(repository_root, "show", f"{V209_SOURCE_COMMIT}:{item['relative_path']}")
        if len(payload) != item["byte_count"] or _sha(payload) != item["sha256"]:
            _fail("A2.source_file", f"v26.209 source file differs:{item['relative_path']}")
        source_file_matches += 1
    if source_file_matches != 3:
        _fail("A2.source_file_count", "v26.209 source file count differs")
    for field_name, expected in OBJECT_IDS.items():
        owner = {
            "catalog_id": catalog,
            "manifest_id": manifest,
            "runner_id": runner,
            "contract_id": execution,
            "census_id": census,
            "implementation_id": implementation,
            "source_identity_id": source,
        }[field_name]
        if owner[field_name] != expected:
            _fail("A2.expected_identity", f"v26.209 expected identity differs:{field_name}")
    coordinates = tuple(
        sorted(
            (
                row["job_id"],
                row["phase"],
                row["invocation_index"],
                row["component_key"] or "",
            )
            for row in rows
        )
    )
    namespaces = {
        name: tuple(sorted(item[f"{name}_namespace"] for item in jobs))
        for name in namespace_prefixes
    }
    member_set_sha256 = models.canonical_sha256(tuple(artifact["members"]))
    projection = {
        "exact_v209_artifact_manifest_id": artifact["manifest_id"],
        "exact_v209_artifact_root": artifact["artifact_root"],
        "formal_member_set_sha256": member_set_sha256,
        "package_catalog_id": catalog["catalog_id"],
        "manifest_id": manifest["manifest_id"],
        "runner_id": runner["runner_id"],
        "execution_contract_id": execution["contract_id"],
        "invocation_census_id": census["census_id"],
        "implementation_id": implementation["implementation_id"],
        "source_identity_id": source["source_identity_id"],
        "exact_package_set_sha256": models.canonical_sha256(package_ids),
        "exact_job_set_sha256": models.canonical_sha256(job_ids),
        "exact_coordinate_set_sha256": models.canonical_sha256(coordinates),
        "raw_namespace_set_sha256": models.canonical_sha256(namespaces["raw"]),
        "result_namespace_set_sha256": models.canonical_sha256(namespaces["result"]),
        "trace_namespace_set_sha256": models.canonical_sha256(namespaces["trace"]),
        "outcome_namespace_set_sha256": models.canonical_sha256(namespaces["outcome"]),
    }
    matches = sum(saved.condition.get(name) == value for name, value in projection.items())
    if matches != 17:
        _fail("A2.candidate_projection", "independent v26.209 projection differs from v26.221")
    independent = IndependentV209(
        files=files,
        artifact=artifact,
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
        census=census,
        implementation=implementation,
        source=source,
        member_set_sha256=member_set_sha256,
        package_ids=package_ids,
        job_ids=job_ids,
        coordinates=coordinates,
        namespaces=namespaces,
    )
    audit = cast(
        models.IndependentV209AuthorityAudit,
        _make(
            models.IndependentV209AuthorityAudit,
            {
                "freeze_id": freeze_id,
                "package_catalog_id": catalog["catalog_id"],
                "manifest_id": manifest["manifest_id"],
                "runner_id": runner["runner_id"],
                "execution_contract_id": execution["contract_id"],
                "invocation_census_id": census["census_id"],
                "implementation_id": implementation["implementation_id"],
                "source_identity_id": source["source_identity_id"],
            },
            "audit_id",
            "finance_v26_222_independent_v209_authority_audit:",
        ),
    )
    return audit, independent


def _independent_relation_closure(
    *, authority_audit_id: str, value: IndependentV209, saved: SavedV221
) -> models.IndependentRelationClosureAudit:
    jobs = value.manifest["jobs"]
    rows = value.census["rows"]
    job_ids = set(value.job_ids)
    package_ids = set(value.package_ids)
    census_ids = {row["job_id"] for row in rows}
    census_memberships = sum(row["job_id"] in job_ids for row in rows)
    package_memberships = sum(item["package_id"] in package_ids for item in jobs)
    cells = {(item["package_id"], item["replica_index"]) for item in jobs}
    prefixes = {
        "raw": "fresh_repaired_final_continuity_executable_raw_namespace:",
        "result": "fresh_repaired_final_continuity_executable_result_namespace:",
        "trace": "fresh_repaired_final_continuity_executable_trace_namespace:",
        "outcome": "fresh_repaired_final_continuity_executable_outcome_namespace:",
    }
    namespace_owner_matches = 0
    for item in jobs:
        parent = {
            "source_v206_job_id": item["source_v206_job_id"],
            "package_id": item["package_id"],
            "implementation_id": item["implementation_id"],
            "repair_profile_id": item["repair_profile_id"],
            "replica_index": item["replica_index"],
        }
        namespace_owner_matches += sum(
            item[f"{name}_namespace"] == canonical_hash(parent, prefix=prefix)
            for name, prefix in prefixes.items()
        )
    parent_pairs = (
        (value.runner["manifest_id"], value.manifest["manifest_id"]),
        (value.runner["package_catalog_id"], value.catalog["catalog_id"]),
        (value.runner["implementation_id"], value.implementation["implementation_id"]),
        (value.runner["repair_profile_id"], value.manifest["repair_profile_id"]),
        (value.execution["runner_id"], value.runner["runner_id"]),
        (value.execution["manifest_id"], value.manifest["manifest_id"]),
        (value.execution["package_catalog_id"], value.catalog["catalog_id"]),
        (value.execution["implementation_id"], value.implementation["implementation_id"]),
        (value.execution["repair_profile_id"], value.manifest["repair_profile_id"]),
        (value.census["execution_contract_id"], value.execution["contract_id"]),
        (value.census["manifest_id"], value.manifest["manifest_id"]),
        (value.census["implementation_id"], value.implementation["implementation_id"]),
    )
    parent_matches = sum(actual == expected for actual, expected in parent_pairs)
    if (
        census_ids != job_ids
        or value.manifest["expected_job_ids"] != list(value.job_ids)
        or census_memberships != 792
        or package_memberships != 192
        or len(cells) != 192
        or namespace_owner_matches != 768
        or any(len(set(items)) != 192 for items in value.namespaces.values())
        or len(set(value.coordinates)) != 792
        or parent_matches != 12
    ):
        _fail("A3.relation_closure", "independent v26.209 relation closure differs")
    projection = {
        "exact_package_ids": list(value.package_ids),
        "exact_job_ids": list(value.job_ids),
        "exact_package_set_sha256": models.canonical_sha256(value.package_ids),
        "exact_job_set_sha256": models.canonical_sha256(value.job_ids),
        "exact_coordinate_set_sha256": models.canonical_sha256(value.coordinates),
        "raw_namespace_set_sha256": models.canonical_sha256(value.namespaces["raw"]),
        "result_namespace_set_sha256": models.canonical_sha256(value.namespaces["result"]),
        "trace_namespace_set_sha256": models.canonical_sha256(value.namespaces["trace"]),
        "outcome_namespace_set_sha256": models.canonical_sha256(value.namespaces["outcome"]),
        "package_catalog_id": value.catalog["catalog_id"],
        "manifest_id": value.manifest["manifest_id"],
        "runner_id": value.runner["runner_id"],
        "execution_contract_id": value.execution["contract_id"],
        "invocation_census_id": value.census["census_id"],
        "implementation_id": value.implementation["implementation_id"],
        "source_identity_id": value.source["source_identity_id"],
    }
    matches = sum(saved.relations.get(name) == item for name, item in projection.items())
    if matches != 16:
        _fail("A3.candidate_projection", "independent relations differ from v26.221")
    return cast(
        models.IndependentRelationClosureAudit,
        _make(
            models.IndependentRelationClosureAudit,
            {
                "v209_authority_audit_id": authority_audit_id,
                "exact_package_ids": value.package_ids,
                "exact_job_ids": value.job_ids,
                "exact_package_set_sha256": models.canonical_sha256(value.package_ids),
                "exact_job_set_sha256": models.canonical_sha256(value.job_ids),
                "exact_coordinate_set_sha256": models.canonical_sha256(value.coordinates),
                "raw_namespace_set_sha256": models.canonical_sha256(value.namespaces["raw"]),
                "result_namespace_set_sha256": models.canonical_sha256(value.namespaces["result"]),
                "trace_namespace_set_sha256": models.canonical_sha256(value.namespaces["trace"]),
                "outcome_namespace_set_sha256": models.canonical_sha256(
                    value.namespaces["outcome"]
                ),
            },
            "audit_id",
            "finance_v26_222_independent_relation_closure_audit:",
        ),
    )


def _rehash_candidate_artifact(files: dict[str, bytes]) -> tuple[dict[str, bytes], str, str]:
    candidate = dict(files)
    original = _load_bytes(candidate["artifact_manifest.json"])
    members = tuple(
        {
            "relative_path": name,
            "sha256": _sha(payload),
            "byte_count": len(payload),
        }
        for name, payload in sorted(candidate.items())
        if name != "artifact_manifest.json"
    )
    root = canonical_hash(members, prefix="finance_v26_209_artifact_root:")
    artifact: dict[str, Any] = {
        "artifact_root": root,
        "file_count": len(members),
        "manifest_id": "pending",
        "members": list(members),
        "run_id": original["run_id"],
        "schema_version": original["schema_version"],
        "total_byte_count": sum(item["byte_count"] for item in members),
    }
    artifact["manifest_id"] = _identity(
        artifact, "manifest_id", "finance_v26_209_artifact_manifest:"
    )
    candidate["artifact_manifest.json"] = _bytes(artifact)
    return candidate, artifact["manifest_id"], root


def _prospective_ids(
    *, name: str, candidate_manifest_id: str, candidate_root: str, mutated_sha256: str
) -> tuple[str, str, str]:
    condition = canonical_hash(
        {
            "attack": name,
            "candidate_manifest_id": candidate_manifest_id,
            "candidate_root": candidate_root,
            "mutated_sha256": mutated_sha256,
        },
        prefix="prospective_v26_221_attack_condition:",
    )
    composition = canonical_hash(
        {"attack": name, "condition_id": condition},
        prefix="prospective_v26_221_attack_composition:",
    )
    authorization = canonical_hash(
        {"attack": name, "composition_id": composition},
        prefix="prospective_v26_221_attack_authorization:",
    )
    return condition, composition, authorization


def _independent_attacks(
    *, authority_audit_id: str, value: IndependentV209, saved: SavedV221
) -> models.IndependentAttackAudit:
    candidate_by_name = {item["control_name"]: item for item in saved.attacks["controls"]}
    controls: list[models.IndependentAttackControl] = []
    for mutation_kind in ("job_id", "raw_namespace"):
        for rehash in (False, True):
            name = f"equal_cardinality_{mutation_kind}_{'formal_rehash' if rehash else 'stale_manifest'}"
            candidate = dict(value.files)
            document = _load_bytes(candidate["executable_development_manifest.json"])
            jobs = document["jobs"]
            if mutation_kind == "job_id":
                jobs[0]["job_id"] = (
                    "fresh_repaired_final_continuity_executable_full_condition_development_job:"
                    + "0" * 64
                )
            else:
                jobs[0]["raw_namespace"] = (
                    "fresh_repaired_final_continuity_executable_raw_namespace:" + "0" * 64
                )
            candidate["executable_development_manifest.json"] = _bytes(document)
            if rehash:
                candidate, candidate_manifest_id, candidate_root = _rehash_candidate_artifact(
                    candidate
                )
            else:
                original = _load_bytes(candidate["artifact_manifest.json"])
                candidate_manifest_id = original["manifest_id"]
                candidate_root = original["artifact_root"]
            job_ids = tuple(item["job_id"] for item in jobs)
            namespaces = tuple(item["raw_namespace"] for item in jobs)
            prospective = _prospective_ids(
                name=name,
                candidate_manifest_id=candidate_manifest_id,
                candidate_root=candidate_root,
                mutated_sha256=_sha(candidate["executable_development_manifest.json"]),
            )
            rejection: V222Error | None = None
            try:
                _independent_exact_member_admission(candidate)
            except V222Error as error:
                rejection = error
            if rejection is None:
                _fail("A4.attack_accepted", f"independent attack accepted:{name}")
            expected_stage = rejection.stage.removeprefix("independent_")
            projection = {
                "control_name": name,
                "mutation_kind": mutation_kind,
                "candidate_artifact_manifest_rehashed": rehash,
                "candidate_artifact_manifest_id": candidate_manifest_id,
                "candidate_artifact_root": candidate_root,
                "prospective_condition_id": prospective[0],
                "prospective_composition_id": prospective[1],
                "prospective_authorization_id": prospective[2],
                "candidate_job_count": len(job_ids),
                "candidate_unique_job_count": len(set(job_ids)),
                "candidate_namespace_count": len(namespaces),
                "candidate_unique_namespace_count": len(set(namespaces)),
                "rejection_stage": expected_stage,
                "rejected_before_condition_construction": True,
                "authoritative_condition_created": False,
                "online_authorization_created": False,
                "attack_writes": 0,
                "provider_calls": 0,
            }
            candidate_control = candidate_by_name[name]
            if any(candidate_control.get(field) != item for field, item in projection.items()):
                _fail("A4.candidate_projection", f"v26.221 attack projection differs:{name}")
            controls.append(
                cast(
                    models.IndependentAttackControl,
                    _make(
                        models.IndependentAttackControl,
                        {
                            "control_name": name,
                            "mutation_kind": mutation_kind,
                            "candidate_artifact_manifest_rehashed": rehash,
                            "candidate_artifact_manifest_id": candidate_manifest_id,
                            "candidate_artifact_root": candidate_root,
                            "prospective_condition_id": prospective[0],
                            "prospective_composition_id": prospective[1],
                            "prospective_authorization_id": prospective[2],
                            "candidate_job_count": len(job_ids),
                            "candidate_unique_job_count": len(set(job_ids)),
                            "candidate_namespace_count": len(namespaces),
                            "candidate_unique_namespace_count": len(set(namespaces)),
                            "rejection_stage": rejection.stage,
                        },
                        "control_id",
                        "finance_v26_222_independent_upstream_attack_control:",
                    ),
                )
            )
    return cast(
        models.IndependentAttackAudit,
        _make(
            models.IndependentAttackAudit,
            {"v209_authority_audit_id": authority_audit_id, "controls": tuple(controls)},
            "audit_id",
            "finance_v26_222_independent_upstream_attack_audit:",
        ),
    )


def _source_identity(value: tuple[str, str]) -> models.SourceIdentity:
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
            "finance_v26_222_source_identity:",
        ),
    )


def _implementation_binding(
    *,
    repository_root: Path,
    authorization_id: str,
    freeze_id: str,
    source: models.SourceIdentity,
) -> models.ImplementationBinding:
    if source.source_commit != "1" * 40:
        actual_tree = (
            _git(repository_root, "rev-parse", f"{source.source_commit}^{{tree}}").decode().strip()
        )
        if actual_tree != source.source_tree:
            _fail("source.tree", "v26.222 source tree differs")
    files: list[models.SourceBinding] = []
    for relative in IMPLEMENTATION_FILES:
        live = (repository_root / relative).read_bytes()
        if source.source_commit != "1" * 40:
            committed = _git(repository_root, "show", f"{source.source_commit}:{relative}")
            if committed != live:
                _fail("source.file", f"v26.222 live source differs:{relative}")
        files.append(
            models.SourceBinding(
                relative_path=relative,
                symbol="<file>",
                sha256=_sha(live),
                byte_count=len(live),
            )
        )
    symbol_values = (
        _saved_v221,
        _detached_rebuild,
        _independent_v209_authority,
        _independent_relation_closure,
        _independent_attacks,
        build,
    )
    symbols = tuple(
        models.SourceBinding(
            relative_path=AUDIT_FILE,
            symbol=value.__name__,
            sha256=_sha(inspect.getsource(value).encode("utf-8")),
            byte_count=len(inspect.getsource(value).encode("utf-8")),
        )
        for value in symbol_values
    )
    tree = ast.parse((repository_root / AUDIT_FILE).read_text(encoding="utf-8"))
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    candidate_helpers = {
        "_admit_exact_v209_files",
        "_relation_closure",
        "_upstream_tamper_audit",
    }
    imported_roots = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    if called & candidate_helpers or imported_roots & {"requests", "urllib", "httpx", "openai"}:
        _fail("source.independence", "candidate helper or network surface is present")
    return cast(
        models.ImplementationBinding,
        _make(
            models.ImplementationBinding,
            {
                "authorization_id": authorization_id,
                "freeze_id": freeze_id,
                "source_identity_id": source.source_identity_id,
                "files": tuple(files),
                "symbols": symbols,
            },
            "binding_id",
            "fresh_exact_v209_parent_authority_independent_audit_implementation_binding:",
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
                "finance_v26_222_gate:",
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
            "finance_v26_222_gate_evaluation:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.Report:
    external, review, directive = _authorization(external_review_path)
    saved = _saved_v221(repository_root)
    freeze = _freeze(external.authorization_id, saved)
    detached = _detached_rebuild(
        repository_root=repository_root, saved=saved, freeze_id=freeze.freeze_id
    )
    authority_audit, authority = _independent_v209_authority(
        repository_root=repository_root, saved=saved, freeze_id=freeze.freeze_id
    )
    relations = _independent_relation_closure(
        authority_audit_id=authority_audit.audit_id, value=authority, saved=saved
    )
    attacks = _independent_attacks(
        authority_audit_id=authority_audit.audit_id, value=authority, saved=saved
    )
    scope = cast(
        models.ScopeBoundaryAudit,
        _make(
            models.ScopeBoundaryAudit,
            {"freeze_id": freeze.freeze_id},
            "audit_id",
            "finance_v26_222_scope_boundary_audit:",
        ),
    )
    gate = _gate(
        (
            ("A0_exact_v221_source_and_formal_freeze", freeze.freeze_id),
            ("A1_detached_v221_directory_rebuild", detached.audit_id),
            ("A2_independent_exact_v209_parent_authority", authority_audit.audit_id),
            ("A3_independent_v209_relation_closure", relations.audit_id),
            ("A4_independent_four_upstream_attacks_reject", attacks.audit_id),
            ("A5_zero_provider_authorization_and_empirical_boundary", scope.audit_id),
        )
    )
    decision = cast(
        models.Decision,
        _make(
            models.Decision,
            {
                "authorization_id": external.authorization_id,
                "freeze_id": freeze.freeze_id,
                "detached_rebuild_audit_id": detached.audit_id,
                "v209_authority_audit_id": authority_audit.audit_id,
                "relation_closure_audit_id": relations.audit_id,
                "attack_audit_id": attacks.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
            },
            "decision_id",
            "finance_v26_222_independent_audit_decision:",
        ),
    )
    transition = cast(
        models.Transition,
        _make(
            models.Transition,
            {"decision_id": decision.decision_id},
            "transition_id",
            "finance_v26_222_transition:",
        ),
    )
    source = _source_identity(source_identity)
    implementation = _implementation_binding(
        repository_root=repository_root,
        authorization_id=external.authorization_id,
        freeze_id=freeze.freeze_id,
        source=source,
    )
    report = cast(
        models.Report,
        _make(
            models.Report,
            {
                "run_id": RUN_ID,
                "source_identity_id": source.source_identity_id,
                "implementation_binding_id": implementation.binding_id,
                "authorization_id": external.authorization_id,
                "freeze_id": freeze.freeze_id,
                "detached_rebuild_audit_id": detached.audit_id,
                "v209_authority_audit_id": authority_audit.audit_id,
                "relation_closure_audit_id": relations.audit_id,
                "attack_audit_id": attacks.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            "report_id",
            "finance_v26_222_independent_audit_report:",
        ),
    )
    payloads = {
        "decision.json": _bytes(decision),
        "detached_rebuild_audit.json": _bytes(detached),
        "external_independent_audit_authorization.json": _bytes(external),
        "external_review.txt": review,
        "gate_evaluation.json": _bytes(gate),
        "implementation_binding.json": _bytes(implementation),
        "independent_relation_closure_audit.json": _bytes(relations),
        "independent_upstream_attack_audit.json": _bytes(attacks),
        "independent_v209_authority_audit.json": _bytes(authority_audit),
        "operator_authorization.txt": directive,
        "prospective_transition.json": _bytes(transition),
        "report.json": _bytes(report),
        "scope_boundary_audit.json": _bytes(scope),
        "source_identity.json": _bytes(source),
        "v221_freeze.json": _bytes(freeze),
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
