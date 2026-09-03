# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn, cast

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_execution_condition_parent_authority_repair_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight_models as v209_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_registry_complement_bound_online_execution_authorization_models as v220_models,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = (
    "finance_v26_221_fresh_exact_v209_execution_condition_authoritative_parent_"
    "binding_repair_preflight_v1_20260903"
)
OUTPUT_DIR: Final = f"artifacts/vtdo_experiment/{RUN_ID}"
EXTERNAL_REVIEW_SHA256: Final = "fbf49cf53f7612b260c1e1b2ec6f66747c5335c168ac133bcef510ea628ac605"
EXTERNAL_REVIEW_BYTES: Final = 13_510
OPERATOR_DIRECTIVE: Final = "参照审计报告继续实验修订"
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
    "phase1_v26_fresh_exact_v209_execution_condition_parent_authority_repair_models.py"
)
PREFLIGHT_FILE: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_fresh_exact_v209_execution_condition_parent_authority_repair_preflight.py"
)
TEST_FILE: Final = (
    "trusted_data_synthesis/tests/"
    "test_v26_fresh_exact_v209_execution_condition_parent_authority_repair_preflight.py"
)
IMPLEMENTATION_FILES: Final = tuple(sorted((MODELS_FILE, PREFLIGHT_FILE, TEST_FILE)))
V209_KEY_FILES: Final = (
    "executable_runner_package_catalog.json",
    "executable_development_manifest.json",
    "executable_runner_contract.json",
    "executable_execution_contract.json",
    "executable_invocation_census.json",
    "implementation_binding.json",
    "source_identity.json",
)


class V221Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _fail(stage: str, reason: str) -> NoReturn:
    raise V221Error(stage, reason)


def _load_bytes(payload: bytes) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(payload))


def _load(path: Path) -> dict[str, Any]:
    return _load_bytes(path.read_bytes())


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


def _all_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _verify_directory(
    root: Path,
    *,
    expected_file_count: int,
    expected_total_bytes: int,
    expected_member_count: int,
    expected_member_bytes: int,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    files = _all_files(root)
    if len(files) != expected_file_count or sum(map(len, files.values())) != expected_total_bytes:
        _fail("formal.geometry", f"formal directory geometry differs:{root.name}")
    artifact = _load_bytes(files["artifact_manifest.json"])
    members = {item["relative_path"]: item for item in artifact["members"]}
    if (
        artifact["file_count"] != expected_member_count
        or artifact["total_byte_count"] != expected_member_bytes
        or set(members) != set(files) - {"artifact_manifest.json"}
    ):
        _fail("formal.paths", f"formal Manifest path set differs:{root.name}")
    for name, member in members.items():
        payload = files[name]
        if len(payload) != member["byte_count"] or _sha(payload) != member["sha256"]:
            _fail("formal.member", f"formal member differs:{root.name}/{name}")
    return files, artifact


def _external_authorization(
    review_path: Path,
) -> tuple[models.ExternalRepairAuthorization, bytes, bytes]:
    review = review_path.read_bytes()
    if len(review) != EXTERNAL_REVIEW_BYTES or _sha(review) != EXTERNAL_REVIEW_SHA256:
        _fail("authorization.external_review", "v26.221 external review bytes differ")
    directive = OPERATOR_DIRECTIVE.encode("utf-8")
    authorization = cast(
        models.ExternalRepairAuthorization,
        _make(
            models.ExternalRepairAuthorization,
            {
                "review_sha256": _sha(review),
                "review_byte_count": len(review),
                "operator_directive_sha256": _sha(directive),
                "operator_directive_byte_count": len(directive),
            },
            "authorization_id",
            "finance_v26_221_external_repair_authorization:",
        ),
    )
    return authorization, review, directive


def _v220_freeze(*, repository_root: Path, external_authorization_id: str) -> models.V220Freeze:
    root = repository_root / V220_DIR
    _, artifact_raw = _verify_directory(
        root,
        expected_file_count=18,
        expected_total_bytes=126_513,
        expected_member_count=17,
        expected_member_bytes=123_577,
    )
    artifact = v220_models.ArtifactManifest.model_validate(artifact_raw)
    source = v220_models.SourceIdentity.model_validate(_load(root / "source_identity.json"))
    report = v220_models.Report.model_validate(_load(root / "report.json"))
    gate = v220_models.GateEvaluation.model_validate(_load(root / "gate_evaluation.json"))
    decision = v220_models.OnlineAuthorizationDecision.model_validate(_load(root / "decision.json"))
    transition = v220_models.ProspectiveTransition.model_validate(
        _load(root / "prospective_transition.json")
    )
    condition = v220_models.ExactExecutionConditionBinding.model_validate(
        _load(root / "exact_192_job_condition_binding.json")
    )
    composition = v220_models.OnlineExecutionCompositionContract.model_validate(
        _load(root / "online_execution_composition_contract.json")
    )
    online_authorization = v220_models.ExactOnlineExecutionAuthorization.model_validate(
        _load(root / "exact_online_execution_authorization.json")
    )
    if (
        source.source_commit != "4276d29f39a77f933f470fafd590020698fe9931"
        or source.source_tree != "9f9cfab48ad7de93b7eec8b58382fc780d5b15fd"
        or artifact.manifest_id
        != "finance_v26_220_artifact_manifest:b2fc48d72a545fd2964fcad2437ced2bcd026d631dfbeef484e2221636bb269d"
        or artifact.artifact_root
        != "finance_v26_220_artifact_root:959b8f0afeec330e744e6fe33d20904037c3466bf782d1644ba885b5b630f213"
        or report.report_id
        != "finance_v26_220_online_authorization_report:4560dd33351074bfa183c839e3908a224e5d3e34542a00f918c63235817c8d15"
        or gate.evaluation_id
        != "finance_v26_220_gate_evaluation:0ee3a7ad611975c9a42126975b1ebb7567cba072c2a1b77cfeeab635e74915a3"
        or decision.decision_id
        != "finance_v26_220_online_authorization_decision:fa540ccc6f281ede4e163f30a062e41b11dbba40878ea82353b9e0aac0f3437c"
        or transition.transition_id
        != "finance_v26_220_transition:d8a9e318ef38508907390a9a71abf1509f1841836db7fe0df354edf75bb33935"
        or online_authorization.authorization_id != models.V220_AUTHORIZATION_ID
        or online_authorization.authorization_consumed
        or report.authorization_consumed
        or report.provider_calls != 0
    ):
        _fail("freeze.v220", "v26.220 frozen authority differs")
    return cast(
        models.V220Freeze,
        _make(
            models.V220Freeze,
            {
                "external_authorization_id": external_authorization_id,
                "v220_source_commit": source.source_commit,
                "v220_source_tree": source.source_tree,
                "v220_artifact_manifest_id": artifact.manifest_id,
                "v220_artifact_root": artifact.artifact_root,
                "v220_report_id": report.report_id,
                "v220_gate_id": gate.evaluation_id,
                "v220_decision_id": decision.decision_id,
                "v220_transition_id": transition.transition_id,
                "v220_condition_binding_id": condition.binding_id,
                "v220_composition_contract_id": composition.contract_id,
                "v220_authorization_id": online_authorization.authorization_id,
                "historical_v220_decision": report.decision,
                "current_scoped_classification": (
                    "v26_220_materializes_an_unconsumed_fresh_authorization_object_but_"
                    "does_not_authoritatively_bind_the_exact_v26_209_execution_condition"
                ),
            },
            "freeze_id",
            "finance_v26_221_v220_freeze:",
        ),
    )


@dataclass(frozen=True)
class V209Authority:
    files: dict[str, bytes]
    artifact: v209_models.ArtifactManifest
    catalog: v209_models.ExecutableRunnerPackageCatalog
    manifest: v209_models.ExecutableDevelopmentManifest
    runner: v209_models.ExecutableRunnerContract
    execution: v209_models.ExecutableExecutionContract
    census: v209_models.ExecutableInvocationCensus
    implementation: v209_models.ImplementationBinding
    source: v209_models.SourceIdentity


def _admit_exact_v209_files(files: dict[str, bytes]) -> v209_models.ArtifactManifest:
    try:
        artifact = v209_models.ArtifactManifest.model_validate(
            _load_bytes(files["artifact_manifest.json"])
        )
    except (KeyError, ValueError) as error:
        _fail("exact_v209_manifest_root_admission", str(error))
    if (
        artifact.manifest_id != models.V209_MANIFEST_ID
        or artifact.artifact_root != models.V209_ARTIFACT_ROOT
    ):
        _fail(
            "exact_v209_manifest_root_admission",
            "candidate v26.209 Manifest identity or Root differs",
        )
    members = {item.relative_path: item for item in artifact.members}
    if set(members) != set(files) - {"artifact_manifest.json"}:
        _fail("exact_v209_member_admission", "candidate v26.209 path set differs")
    for name, member in members.items():
        payload = files[name]
        if len(payload) != member.byte_count or _sha(payload) != member.sha256:
            _fail("exact_v209_member_admission", f"candidate v26.209 member differs:{name}")
    return artifact


def _v209_authority(repository_root: Path) -> V209Authority:
    root = repository_root / V209_DIR
    files = _all_files(root)
    if len(files) != 21 or sum(map(len, files.values())) != 44_916_386:
        _fail("exact_v209_formal_geometry", "v26.209 formal directory geometry differs")
    artifact = _admit_exact_v209_files(files)
    if artifact.file_count != 20 or artifact.total_byte_count != 44_912_918:
        _fail("exact_v209_formal_geometry", "v26.209 Manifest geometry differs")
    try:
        catalog = v209_models.ExecutableRunnerPackageCatalog.model_validate(
            _load_bytes(files["executable_runner_package_catalog.json"])
        )
        manifest = v209_models.ExecutableDevelopmentManifest.model_validate(
            _load_bytes(files["executable_development_manifest.json"])
        )
        runner = v209_models.ExecutableRunnerContract.model_validate(
            _load_bytes(files["executable_runner_contract.json"])
        )
        execution = v209_models.ExecutableExecutionContract.model_validate(
            _load_bytes(files["executable_execution_contract.json"])
        )
        census = v209_models.ExecutableInvocationCensus.model_validate(
            _load_bytes(files["executable_invocation_census.json"])
        )
        implementation = v209_models.ImplementationBinding.model_validate(
            _load_bytes(files["implementation_binding.json"])
        )
        source = v209_models.SourceIdentity.model_validate(
            _load_bytes(files["source_identity.json"])
        )
    except ValueError as error:
        _fail("exact_v209_object_identity_admission", str(error))
    if (
        source.source_commit != "5809e9782515e55ee797b43730584d5d860aaa5c"
        or source.source_tree != "b2272bc1766a2d9b8c6562cb0b9f2f47151ad7cf"
        or implementation.source_commit != source.source_commit
        or implementation.source_tree != source.source_tree
    ):
        _fail("exact_v209_source_identity_admission", "v26.209 source identity differs")
    tree = _git(repository_root, "rev-parse", f"{source.source_commit}^{{tree}}").decode().strip()
    if tree != source.source_tree:
        _fail("exact_v209_source_tree_admission", "v26.209 commit tree differs")
    for item in implementation.files:
        payload = _git(repository_root, "show", f"{source.source_commit}:{item.relative_path}")
        if len(payload) != item.byte_count or _sha(payload) != item.sha256:
            _fail(
                "exact_v209_source_file_admission",
                f"v26.209 source file differs:{item.relative_path}",
            )
    return V209Authority(
        files=files,
        artifact=artifact,
        catalog=catalog,
        manifest=manifest,
        runner=runner,
        execution=execution,
        census=census,
        implementation=implementation,
        source=source,
    )


def _formal_freeze(
    *, v220_freeze_id: str, authority: V209Authority
) -> models.V209FormalAuthorityFreeze:
    members = tuple(
        models.FormalMember(
            relative_path=item.relative_path,
            sha256=item.sha256,
            byte_count=item.byte_count,
        )
        for item in authority.artifact.members
    )
    projection = tuple(item.model_dump(mode="json", warnings=False) for item in members)
    return cast(
        models.V209FormalAuthorityFreeze,
        _make(
            models.V209FormalAuthorityFreeze,
            {
                "v220_freeze_id": v220_freeze_id,
                "v209_source_commit": authority.source.source_commit,
                "v209_source_tree": authority.source.source_tree,
                "exact_artifact_manifest_id": authority.artifact.manifest_id,
                "exact_artifact_root": authority.artifact.artifact_root,
                "members": members,
                "formal_member_set_sha256": models.canonical_sha256(projection),
            },
            "freeze_id",
            "finance_v26_221_v209_formal_authority_freeze:",
        ),
    )


def _namespace_parent(job: v209_models.ExecutableDevelopmentJob) -> dict[str, Any]:
    return {
        "source_v206_job_id": job.source_v206_job_id,
        "package_id": job.package_id,
        "implementation_id": job.implementation_id,
        "repair_profile_id": job.repair_profile_id,
        "replica_index": job.replica_index,
    }


def _relation_closure(
    *, formal_freeze_id: str, authority: V209Authority
) -> models.RelationClosureAudit:
    package_ids = tuple(sorted(item.package_id for item in authority.catalog.packages))
    job_ids = tuple(sorted(item.job_id for item in authority.manifest.jobs))
    census_job_ids = {item.job_id for item in authority.census.rows}
    manifest_job_ids = set(job_ids)
    coordinates = tuple(
        sorted(
            (
                item.job_id,
                item.phase,
                item.invocation_index,
                item.component_key or "",
            )
            for item in authority.census.rows
        )
    )
    namespaces = {
        field: tuple(
            sorted(getattr(item, f"{field}_namespace") for item in authority.manifest.jobs)
        )
        for field in ("raw", "result", "trace", "outcome")
    }
    namespace_prefixes = {
        "raw": "fresh_repaired_final_continuity_executable_raw_namespace:",
        "result": "fresh_repaired_final_continuity_executable_result_namespace:",
        "trace": "fresh_repaired_final_continuity_executable_trace_namespace:",
        "outcome": "fresh_repaired_final_continuity_executable_outcome_namespace:",
    }
    namespace_owner_matches = sum(
        getattr(job, f"{field}_namespace") == canonical_hash(_namespace_parent(job), prefix=prefix)
        for job in authority.manifest.jobs
        for field, prefix in namespace_prefixes.items()
    )
    parent_pairs = (
        (authority.runner.manifest_id, authority.manifest.manifest_id),
        (authority.runner.package_catalog_id, authority.catalog.catalog_id),
        (authority.runner.implementation_id, authority.implementation.implementation_id),
        (authority.runner.repair_profile_id, authority.manifest.repair_profile_id),
        (authority.execution.runner_id, authority.runner.runner_id),
        (authority.execution.manifest_id, authority.manifest.manifest_id),
        (authority.execution.package_catalog_id, authority.catalog.catalog_id),
        (authority.execution.implementation_id, authority.implementation.implementation_id),
        (authority.execution.repair_profile_id, authority.manifest.repair_profile_id),
        (authority.census.execution_contract_id, authority.execution.contract_id),
        (authority.census.manifest_id, authority.manifest.manifest_id),
        (authority.census.implementation_id, authority.implementation.implementation_id),
    )
    package_memberships = sum(
        item.package_id in set(package_ids) for item in authority.manifest.jobs
    )
    census_memberships = sum(item.job_id in manifest_job_ids for item in authority.census.rows)
    cells = {(item.package_id, item.replica_index) for item in authority.manifest.jobs}
    if (
        census_job_ids != manifest_job_ids
        or authority.manifest.expected_job_ids != job_ids
        or package_memberships != 192
        or census_memberships != 792
        or len(cells) != 192
        or namespace_owner_matches != 768
        or any(len(set(values)) != 192 for values in namespaces.values())
        or len(set(coordinates)) != 792
        or sum(actual == expected for actual, expected in parent_pairs) != 12
    ):
        _fail("exact_v209_relation_closure", "v26.209 relation closure differs")
    return cast(
        models.RelationClosureAudit,
        _make(
            models.RelationClosureAudit,
            {
                "formal_freeze_id": formal_freeze_id,
                "package_catalog_id": authority.catalog.catalog_id,
                "manifest_id": authority.manifest.manifest_id,
                "runner_id": authority.runner.runner_id,
                "execution_contract_id": authority.execution.contract_id,
                "invocation_census_id": authority.census.census_id,
                "implementation_id": authority.implementation.implementation_id,
                "source_identity_id": authority.source.source_identity_id,
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
            "audit_id",
            "finance_v26_221_v209_relation_closure_audit:",
        ),
    )


def _condition_binding(
    *,
    v220: models.V220Freeze,
    formal: models.V209FormalAuthorityFreeze,
    relations: models.RelationClosureAudit,
) -> models.AuthoritativeExecutionConditionBinding:
    return cast(
        models.AuthoritativeExecutionConditionBinding,
        _make(
            models.AuthoritativeExecutionConditionBinding,
            {
                "v220_freeze_id": v220.freeze_id,
                "v209_formal_freeze_id": formal.freeze_id,
                "relation_closure_audit_id": relations.audit_id,
                "exact_v209_artifact_manifest_id": formal.exact_artifact_manifest_id,
                "exact_v209_artifact_root": formal.exact_artifact_root,
                "formal_member_set_sha256": formal.formal_member_set_sha256,
                "package_catalog_id": relations.package_catalog_id,
                "manifest_id": relations.manifest_id,
                "runner_id": relations.runner_id,
                "execution_contract_id": relations.execution_contract_id,
                "invocation_census_id": relations.invocation_census_id,
                "implementation_id": relations.implementation_id,
                "source_identity_id": relations.source_identity_id,
                "exact_package_ids": relations.exact_package_ids,
                "exact_job_ids": relations.exact_job_ids,
                "exact_package_set_sha256": relations.exact_package_set_sha256,
                "exact_job_set_sha256": relations.exact_job_set_sha256,
                "exact_coordinate_set_sha256": relations.exact_coordinate_set_sha256,
                "raw_namespace_set_sha256": relations.raw_namespace_set_sha256,
                "result_namespace_set_sha256": relations.result_namespace_set_sha256,
                "trace_namespace_set_sha256": relations.trace_namespace_set_sha256,
                "outcome_namespace_set_sha256": relations.outcome_namespace_set_sha256,
                "previous_v220_condition_binding_id": v220.v220_condition_binding_id,
            },
            "binding_id",
            "fresh_exact_v209_execution_condition_authoritative_parent_binding:",
        ),
    )


def _composition(
    *,
    v220: models.V220Freeze,
    condition: models.AuthoritativeExecutionConditionBinding,
    repository_root: Path,
) -> models.RepairedCompositionContract:
    old = v220_models.OnlineExecutionCompositionContract.model_validate(
        _load(repository_root / V220_DIR / "online_execution_composition_contract.json")
    )
    return cast(
        models.RepairedCompositionContract,
        _make(
            models.RepairedCompositionContract,
            {
                "v220_freeze_id": v220.freeze_id,
                "authoritative_condition_binding_id": condition.binding_id,
                "v218_parent_set_binding_id": old.v218_parent_set_binding_id,
                "retained_v220_composition_contract_id": old.contract_id,
                "exact_v209_artifact_manifest_id": condition.exact_v209_artifact_manifest_id,
                "exact_v209_artifact_root": condition.exact_v209_artifact_root,
                "exact_v209_formal_member_set_sha256": condition.formal_member_set_sha256,
            },
            "contract_id",
            "fresh_exact_v209_parent_authority_repaired_composition_contract:",
        ),
    )


def _candidate_artifact(
    files: dict[str, bytes], *, rehash: bool
) -> tuple[dict[str, bytes], str, str]:
    candidate = dict(files)
    original = v209_models.ArtifactManifest.model_validate(
        _load_bytes(files["artifact_manifest.json"])
    )
    if rehash:
        artifact = v209_models.artifact_manifest(
            original.run_id,
            {
                name: payload
                for name, payload in candidate.items()
                if name != "artifact_manifest.json"
            },
        )
        candidate["artifact_manifest.json"] = v209_models.canonical_bytes(artifact) + b"\n"
        return candidate, artifact.manifest_id, artifact.artifact_root
    return candidate, original.manifest_id, original.artifact_root


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


def _upstream_tamper_audit(
    *, formal_freeze_id: str, authority: V209Authority
) -> models.UpstreamTamperAudit:
    controls: list[models.UpstreamTamperControl] = []
    for mutation_kind in ("job_id", "raw_namespace"):
        for rehash in (False, True):
            name = f"equal_cardinality_{mutation_kind}_{'formal_rehash' if rehash else 'stale_manifest'}"
            candidate = dict(authority.files)
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
            candidate["executable_development_manifest.json"] = (
                v209_models.canonical_bytes(document) + b"\n"
            )
            candidate, candidate_manifest_id, candidate_root = _candidate_artifact(
                candidate, rehash=rehash
            )
            candidate_job_ids = tuple(item["job_id"] for item in jobs)
            candidate_namespaces = tuple(item["raw_namespace"] for item in jobs)
            prospective = _prospective_ids(
                name=name,
                candidate_manifest_id=candidate_manifest_id,
                candidate_root=candidate_root,
                mutated_sha256=_sha(candidate["executable_development_manifest.json"]),
            )
            rejection: V221Error | None = None
            try:
                _admit_exact_v209_files(candidate)
            except V221Error as error:
                rejection = error
            if rejection is None:
                _fail("negative.upstream_tamper", f"upstream tamper accepted:{name}")
            controls.append(
                cast(
                    models.UpstreamTamperControl,
                    _make(
                        models.UpstreamTamperControl,
                        {
                            "control_name": name,
                            "mutation_kind": mutation_kind,
                            "candidate_artifact_manifest_rehashed": rehash,
                            "candidate_artifact_manifest_id": candidate_manifest_id,
                            "candidate_artifact_root": candidate_root,
                            "prospective_condition_id": prospective[0],
                            "prospective_composition_id": prospective[1],
                            "prospective_authorization_id": prospective[2],
                            "candidate_job_count": len(candidate_job_ids),
                            "candidate_unique_job_count": len(set(candidate_job_ids)),
                            "candidate_namespace_count": len(candidate_namespaces),
                            "candidate_unique_namespace_count": len(set(candidate_namespaces)),
                            "rejection_stage": rejection.stage,
                            "rejection_reason_sha256": _sha(rejection.reason.encode("utf-8")),
                        },
                        "control_id",
                        "finance_v26_221_upstream_tamper_control:",
                    ),
                )
            )
    return cast(
        models.UpstreamTamperAudit,
        _make(
            models.UpstreamTamperAudit,
            {"formal_freeze_id": formal_freeze_id, "controls": tuple(controls)},
            "audit_id",
            "finance_v26_221_upstream_tamper_audit:",
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
            "finance_v26_221_source_identity:",
        ),
    )


def _implementation_binding(
    *,
    repository_root: Path,
    source: models.SourceIdentity,
    external_authorization_id: str,
    v220_freeze_id: str,
) -> models.ImplementationBinding:
    use_commit = source.source_commit != "1" * 40
    if use_commit:
        tree = (
            _git(repository_root, "rev-parse", f"{source.source_commit}^{{tree}}").decode().strip()
        )
        if tree != source.source_tree:
            _fail("source.tree", "v26.221 source tree differs")
    files: list[models.SourceFile] = []
    for relative_path in source.implementation_files:
        payload = (
            _git(repository_root, "show", f"{source.source_commit}:{relative_path}")
            if use_commit
            else (repository_root / relative_path).read_bytes()
        )
        if use_commit and payload != (repository_root / relative_path).read_bytes():
            _fail("source.working_tree", f"v26.221 source differs:{relative_path}")
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
                "external_authorization_id": external_authorization_id,
                "v220_freeze_id": v220_freeze_id,
                "files": tuple(files),
                "formal_admission_symbol_sha256": _sha(
                    inspect.getsource(_admit_exact_v209_files).encode("utf-8")
                ),
                "relation_closure_symbol_sha256": _sha(
                    inspect.getsource(_relation_closure).encode("utf-8")
                ),
                "attack_symbol_sha256": _sha(
                    inspect.getsource(_upstream_tamper_audit).encode("utf-8")
                ),
            },
            "binding_id",
            "fresh_exact_v209_parent_authority_repair_implementation_binding:",
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
                "finance_v26_221_gate:",
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
            "finance_v26_221_gate_evaluation:",
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.Report:
    external, review, directive = _external_authorization(external_review_path)
    v220 = _v220_freeze(
        repository_root=repository_root,
        external_authorization_id=external.authorization_id,
    )
    authority = _v209_authority(repository_root)
    formal = _formal_freeze(v220_freeze_id=v220.freeze_id, authority=authority)
    relations = _relation_closure(formal_freeze_id=formal.freeze_id, authority=authority)
    condition = _condition_binding(v220=v220, formal=formal, relations=relations)
    composition = _composition(
        v220=v220,
        condition=condition,
        repository_root=repository_root,
    )
    attacks = _upstream_tamper_audit(formal_freeze_id=formal.freeze_id, authority=authority)
    scope = cast(
        models.ScopeBoundaryAudit,
        _make(
            models.ScopeBoundaryAudit,
            {"v220_authorization_id": v220.v220_authorization_id},
            "audit_id",
            "finance_v26_221_scope_boundary_audit:",
        ),
    )
    gate = _gate(
        (
            ("R0_external_scope_and_exact_v220_freeze", v220.freeze_id),
            ("R1_exact_v209_formal_manifest_root_and_member_bytes", formal.freeze_id),
            ("R2_strict_v209_object_identity_revalidation", formal.freeze_id),
            ("R3_v209_job_package_namespace_and_census_relation_closure", relations.audit_id),
            ("R4_authoritative_condition_and_repaired_composition", condition.binding_id),
            ("R5_equal_cardinality_upstream_tamper_attacks_reject", attacks.audit_id),
            ("R6_v220_authorization_unconsumed_and_no_new_authorization", scope.audit_id),
            ("R7_zero_provider_credential_empirical_boundary", scope.audit_id),
        )
    )
    decision = cast(
        models.Decision,
        _make(
            models.Decision,
            {
                "external_authorization_id": external.authorization_id,
                "v220_freeze_id": v220.freeze_id,
                "v209_formal_freeze_id": formal.freeze_id,
                "relation_closure_audit_id": relations.audit_id,
                "authoritative_condition_binding_id": condition.binding_id,
                "repaired_composition_contract_id": composition.contract_id,
                "upstream_tamper_audit_id": attacks.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
            },
            "decision_id",
            "finance_v26_221_parent_authority_decision:",
        ),
    )
    transition = cast(
        models.Transition,
        _make(
            models.Transition,
            {"decision_id": decision.decision_id},
            "transition_id",
            "finance_v26_221_transition:",
        ),
    )
    source = _source_identity(source_identity)
    implementation = _implementation_binding(
        repository_root=repository_root,
        source=source,
        external_authorization_id=external.authorization_id,
        v220_freeze_id=v220.freeze_id,
    )
    report = cast(
        models.Report,
        _make(
            models.Report,
            {
                "run_id": RUN_ID,
                "source_identity_id": source.source_identity_id,
                "implementation_binding_id": implementation.binding_id,
                "external_authorization_id": external.authorization_id,
                "v220_freeze_id": v220.freeze_id,
                "v209_formal_freeze_id": formal.freeze_id,
                "relation_closure_audit_id": relations.audit_id,
                "authoritative_condition_binding_id": condition.binding_id,
                "repaired_composition_contract_id": composition.contract_id,
                "upstream_tamper_audit_id": attacks.audit_id,
                "scope_boundary_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            "report_id",
            "finance_v26_221_parent_authority_report:",
        ),
    )
    payloads = {
        "authoritative_execution_condition_binding.json": _bytes(condition),
        "decision.json": _bytes(decision),
        "external_repair_authorization.json": _bytes(external),
        "external_review.txt": review,
        "gate_evaluation.json": _bytes(gate),
        "implementation_binding.json": _bytes(implementation),
        "operator_authorization.txt": directive,
        "prospective_transition.json": _bytes(transition),
        "relation_closure_audit.json": _bytes(relations),
        "repaired_composition_contract.json": _bytes(composition),
        "report.json": _bytes(report),
        "scope_boundary_audit.json": _bytes(scope),
        "source_identity.json": _bytes(source),
        "upstream_tamper_audit.json": _bytes(attacks),
        "v209_formal_authority_freeze.json": _bytes(formal),
        "v220_freeze.json": _bytes(v220),
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
