# ruff: noqa: E501
from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path
from typing import Any, NoReturn, cast

from pydantic import BaseModel

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization as v231_stage,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_manifest_byte_repair_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_models as v231_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_population_independent_audit_models as v230_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_source_authority_recovery_population_preflight_models as v229_models,
)

RUN_ID = models.RUN_ID
V229_RUN_ID = v231_stage.V229_RUN_ID
V230_RUN_ID = v231_stage.V230_RUN_ID
V231_RUN_ID = v231_stage.RUN_ID
DIRECTIVE = models.DIRECTIVE.encode("utf-8")
IMPLEMENTATION_PATH = "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_manifest_byte_repair.py"
SOURCE_PATHS = tuple(
    sorted(
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_manifest_byte_repair.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_manifest_byte_repair_models.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization.py",
            "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_authorization_models.py",
        )
    )
)
REQUIRED_SYMBOLS = tuple(
    sorted(
        (
            "_admission_audit",
            "_authorization",
            "_composition",
            "_external_decision",
            "_gate",
            "_manifest_attack_audit",
            "_manifest_authority",
            "_parent_attack_audit",
            "_recovery_execution_contract",
            "_recovery_parent_binding",
            "_source_identity",
            "_v230_freeze",
            "_v231_candidate_freeze",
        )
    )
)


class V232Error(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(f"{stage}:{reason}")
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise V232Error(stage, reason)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        _fail("load", f"object required:{path}")
    return value


def _bytes(value: Any) -> bytes:
    return models.canonical_bytes(value)


def _make(model_type: type[BaseModel], values: dict[str, Any], field: str, prefix: str) -> Any:
    return models.make_identity(model_type, values, field=field, prefix=prefix)


def _git(repository_root: Path, *args: str) -> bytes:
    return subprocess.run(
        ("git", *args), cwd=repository_root, check=True, capture_output=True
    ).stdout


def _formal_dir(repository_root: Path, run_id: str) -> Path:
    return repository_root / "trusted_data_synthesis" / "artifacts" / "vtdo_experiment" / run_id


def _external_decision(review_path: Path) -> tuple[models.ExternalRepairDecision, bytes]:
    review = review_path.read_bytes()
    if (
        len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT
        or models.sha(review) != models.EXTERNAL_REVIEW_SHA256
    ):
        _fail("external.review", "external review bytes differ")
    compact = "".join(review.decode("utf-8").split())
    required = (
        "AUDIT_DECISION=FAIL_NARROWLY_AT_G0",
        "BLOCKING_DEFECT=PREDECESSOR_SELF_EXCLUDING_MANIFEST_ACTUAL_BYTE_AUTHORITY_NOT_CLOSED",
        "FIRST_FAILED_GATE=G0_EXACT_V26_230_FREEZE",
        "MANDATORY_REVISION=NARROW",
        "RECOVERY_POPULATION_AUTHORITY=RETAINED",
        models.CONSUMED_STAGE,
    )
    if any(marker not in compact for marker in required):
        _fail("external.scope", "external repair decision markers differ")
    if (
        len(DIRECTIVE) != models.DIRECTIVE_BYTE_COUNT
        or models.sha(DIRECTIVE) != models.DIRECTIVE_SHA256
    ):
        _fail("external.directive", "operator directive bytes differ")
    decision = cast(
        models.ExternalRepairDecision,
        _make(
            models.ExternalRepairDecision,
            {},
            "decision_id",
            models.ExternalRepairDecision.prefix(),
        ),
    )
    return decision, review


def _manifest_spec(version: str) -> tuple[str, type[BaseModel], int, str, int, int, int, int]:
    if version == "v26.229":
        return (
            V229_RUN_ID,
            v229_models.ArtifactManifest,
            models.V229_MANIFEST_BYTES,
            models.V229_MANIFEST_SHA256,
            117,
            1_105_367,
            116,
            1_088_415,
        )
    if version == "v26.230":
        return (
            V230_RUN_ID,
            v230_models.ArtifactManifest,
            models.V230_MANIFEST_BYTES,
            models.V230_MANIFEST_SHA256,
            20,
            308_132,
            19,
            304_982,
        )
    if version == "v26.231":
        return (
            V231_RUN_ID,
            v231_models.ArtifactManifest,
            models.V231_MANIFEST_BYTES,
            models.V231_MANIFEST_SHA256,
            18,
            103_759,
            17,
            100_870,
        )
    _fail("freeze.version", f"unknown predecessor version:{version}")


def _validate_manifest_raw(
    *, raw: bytes, manifest_type: type[BaseModel], expected_bytes: int, expected_sha256: str
) -> BaseModel:
    if len(raw) != expected_bytes or models.sha(raw) != expected_sha256:
        _fail("freeze.manifest_bytes", "Manifest actual bytes differ")
    try:
        return manifest_type.model_validate_json(raw)
    except ValueError as error:
        _fail("freeze.manifest_schema", str(error))


def _manifest_authority(
    repository_root: Path, version: str
) -> tuple[models.ManifestByteAuthority, BaseModel, bytes]:
    (
        run_id,
        manifest_type,
        expected_bytes,
        expected_sha256,
        expected_file_count,
        expected_total_bytes,
        expected_member_count,
        expected_member_bytes,
    ) = _manifest_spec(version)
    directory = _formal_dir(repository_root, run_id)
    raw = (directory / "artifact_manifest.json").read_bytes()
    manifest = _validate_manifest_raw(
        raw=raw,
        manifest_type=manifest_type,
        expected_bytes=expected_bytes,
        expected_sha256=expected_sha256,
    )
    manifest_value = cast(Any, manifest)
    members = tuple(manifest_value.members)
    expected_paths = {"artifact_manifest.json", *(row.relative_path for row in members)}
    actual_paths = {
        path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()
    }
    if actual_paths != expected_paths:
        _fail("freeze.paths", f"formal path set differs:{version}")
    for row in members:
        payload = (directory / row.relative_path).read_bytes()
        if len(payload) != row.byte_count or models.sha(payload) != row.sha256:
            _fail("freeze.member", f"formal member differs:{version}:{row.relative_path}")
    total_bytes = sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
    member_bytes = sum(row.byte_count for row in members)
    if (
        len(actual_paths) != expected_file_count
        or total_bytes != expected_total_bytes
        or len(members) != expected_member_count
        or member_bytes != expected_member_bytes
    ):
        _fail("freeze.geometry", f"formal directory geometry differs:{version}")
    values = {
        "predecessor_version": version,
        "run_id": run_id,
        "expected_byte_count": expected_bytes,
        "actual_byte_count": len(raw),
        "expected_sha256": expected_sha256,
        "actual_sha256": models.sha(raw),
        "manifest_id": manifest_value.manifest_id,
        "artifact_root": manifest_value.artifact_root,
        "manifest_member_count": len(members),
        "manifest_member_bytes": member_bytes,
        "formal_file_count": len(actual_paths),
        "formal_total_bytes": total_bytes,
    }
    authority = cast(
        models.ManifestByteAuthority,
        _make(
            models.ManifestByteAuthority,
            values,
            "authority_id",
            models.ManifestByteAuthority.prefix(),
        ),
    )
    return authority, manifest, raw


def _v231_candidate_freeze(
    repository_root: Path,
    external: models.ExternalRepairDecision,
    authority: models.ManifestByteAuthority,
) -> models.V231CandidateFreeze:
    directory = _formal_dir(repository_root, V231_RUN_ID)
    report = v231_models.Report.model_validate(_load(directory / "report.json"))
    gate = v231_models.GateEvaluation.model_validate(_load(directory / "gate_evaluation.json"))
    decision = v231_models.Decision.model_validate(_load(directory / "decision.json"))
    transition = v231_models.Transition.model_validate(_load(directory / "transition.json"))
    authorization = v231_models.ExactOnlineAuthorization.model_validate(
        _load(directory / "exact_online_execution_authorization.json")
    )
    source = v231_models.SourceIdentity.model_validate(_load(directory / "source_identity.json"))
    if (
        authority.manifest_id != models.V231_MANIFEST_ID
        or authority.artifact_root != models.V231_ARTIFACT_ROOT
        or report.report_id != models.V231_REPORT_ID
        or gate.evaluation_id != models.V231_GATE_ID
        or decision.decision_id != models.V231_DECISION_ID
        or transition.transition_id != models.V231_TRANSITION_ID
        or authorization.authorization_id != models.V231_AUTHORIZATION_ID
        or source.source_commit != "d74406041cabb1ea61df22b99f8a96affdae2ea0"
        or source.source_tree != "3cdbb7cbdbc79ec01726ba262b8833d4e013d058"
    ):
        _fail("freeze.v231", "v26.231 candidate authority differs")
    return cast(
        models.V231CandidateFreeze,
        _make(
            models.V231CandidateFreeze,
            {
                "external_decision_id": external.decision_id,
                "manifest_byte_authority_id": authority.authority_id,
                "source_commit": source.source_commit,
                "source_tree": source.source_tree,
            },
            "freeze_id",
            models.V231CandidateFreeze.prefix(),
        ),
    )


def _v230_freeze(
    repository_root: Path,
    external: models.ExternalRepairDecision,
    v231_freeze: models.V231CandidateFreeze,
    authority: models.ManifestByteAuthority,
) -> models.V230Freeze:
    rebuilt = v231_stage._v230_freeze(repository_root, external.decision_id)
    old = v231_models.V230Freeze.model_validate(
        _load(_formal_dir(repository_root, V231_RUN_ID) / "v230_freeze.json")
    )
    rebuilt_projection = rebuilt.model_dump(
        mode="python", exclude={"freeze_id", "external_decision_id"}
    )
    old_projection = old.model_dump(mode="python", exclude={"freeze_id", "external_decision_id"})
    if rebuilt_projection != old_projection:
        _fail("freeze.v230_projection", "v26.230 retained Freeze projection differs")
    values = rebuilt.model_dump(mode="python", exclude={"freeze_id"})
    values.update(
        {
            "v231_candidate_freeze_id": v231_freeze.freeze_id,
            "v230_manifest_byte_authority_id": authority.authority_id,
            "old_v231_freeze_id": old.freeze_id,
        }
    )
    return cast(
        models.V230Freeze,
        _make(models.V230Freeze, values, "freeze_id", models.V230Freeze.prefix()),
    )


def _recovery_parent_binding(
    repository_root: Path,
    freeze: models.V230Freeze,
    v229_authority: models.ManifestByteAuthority,
    v230_authority: models.ManifestByteAuthority,
) -> models.RecoveryParentBinding:
    directory = _formal_dir(repository_root, V231_RUN_ID)
    old_freeze = v231_models.V230Freeze.model_validate(_load(directory / "v230_freeze.json"))
    rebuilt = v231_stage._recovery_parent_binding(repository_root, old_freeze)
    saved = v231_models.RecoveryParentBinding.model_validate(
        _load(directory / "recovery_parent_binding.json")
    )
    if _bytes(rebuilt) != _bytes(saved):
        _fail("parent.retained_projection", "retained v26.231 Recovery parent differs")
    values = rebuilt.model_dump(mode="python", exclude={"binding_id", "v230_freeze_id"})
    values.update(
        {
            "v230_freeze_id": freeze.freeze_id,
            "v229_manifest_byte_authority_id": v229_authority.authority_id,
            "v230_manifest_byte_authority_id": v230_authority.authority_id,
        }
    )
    return cast(
        models.RecoveryParentBinding,
        _make(
            models.RecoveryParentBinding,
            values,
            "binding_id",
            models.RecoveryParentBinding.prefix(),
        ),
    )


def _recovery_execution_contract(
    repository_root: Path,
    parent: models.RecoveryParentBinding,
) -> models.RecoveryExecutionContract:
    retained = v231_models.RecoveryExecutionContract.model_validate(
        _load(_formal_dir(repository_root, V231_RUN_ID) / "recovery_execution_contract.json")
    )
    if retained.contract_id != models.V231_EXECUTION_CONTRACT_ID:
        _fail("contract.retained_projection", "retained v26.231 Contract differs")
    old_values = retained.model_dump(mode="python", exclude={"contract_id", "parent_binding_id"})
    old_values["parent_binding_id"] = parent.binding_id
    return cast(
        models.RecoveryExecutionContract,
        _make(
            models.RecoveryExecutionContract,
            old_values,
            "contract_id",
            models.RecoveryExecutionContract.prefix(),
        ),
    )


def _composition(
    freeze: models.V230Freeze,
    parent: models.RecoveryParentBinding,
    contract: models.RecoveryExecutionContract,
) -> models.RecoveryComposition:
    values = {
        "v230_freeze_id": freeze.freeze_id,
        "parent_binding_id": parent.binding_id,
        "execution_contract_id": contract.contract_id,
        "event_sequence": v231_models.EVENT_SEQUENCE,
    }
    return cast(
        models.RecoveryComposition,
        _make(
            models.RecoveryComposition,
            values,
            "composition_id",
            models.RecoveryComposition.prefix(),
        ),
    )


def _authorization(
    external: models.ExternalRepairDecision,
    v231_freeze: models.V231CandidateFreeze,
    v229_authority: models.ManifestByteAuthority,
    v230_authority: models.ManifestByteAuthority,
    freeze: models.V230Freeze,
    parent: models.RecoveryParentBinding,
    contract: models.RecoveryExecutionContract,
    composition: models.RecoveryComposition,
) -> models.ExactOnlineAuthorization:
    values = {
        "external_decision_id": external.decision_id,
        "v230_freeze_id": freeze.freeze_id,
        "parent_binding_id": parent.binding_id,
        "execution_contract_id": contract.contract_id,
        "composition_id": composition.composition_id,
        "recovery_job_ids": parent.recovery_job_ids,
        "recovery_job_set_sha256": parent.job_set_sha256,
        "v231_candidate_freeze_id": v231_freeze.freeze_id,
        "v229_manifest_byte_authority_id": v229_authority.authority_id,
        "v230_manifest_byte_authority_id": v230_authority.authority_id,
    }
    return cast(
        models.ExactOnlineAuthorization,
        _make(
            models.ExactOnlineAuthorization,
            values,
            "authorization_id",
            models.ExactOnlineAuthorization.prefix(),
        ),
    )


class PrecredentialGuard:
    def __init__(self, expected: models.ExactOnlineAuthorization) -> None:
        self._expected = models.ExactOnlineAuthorization.model_validate(
            expected.model_dump(mode="python")
        )
        self._bytes = _bytes(self._expected)

    def admit(
        self,
        *,
        authorization: object | None,
        authorization_bytes: bytes | None,
        requested_stage: str,
        requested_v230_freeze_id: str,
        requested_parent_binding_id: str,
        requested_execution_contract_id: str,
        requested_composition_id: str,
        requested_recovery_job_ids: tuple[str, ...],
        provider_execution_requested: bool,
        continuation_to_terminal_requested: bool,
        successful_prefix_provider_reissue_requested: bool = False,
        historical_mutation_requested: bool = False,
        historical_terminal_backfill_requested: bool = False,
        replacement_run_requested: bool = False,
        extra_recovery_job_requested: bool = False,
        max_tokens_change_requested: bool = False,
        empirical_estimation_requested: bool = False,
        qa_integration_requested: bool = False,
    ) -> models.Admission:
        if type(authorization) is not models.ExactOnlineAuthorization:
            raise ValueError("authorization parent type differs")
        assert isinstance(authorization, models.ExactOnlineAuthorization)
        strict = models.ExactOnlineAuthorization.model_validate(
            authorization.model_dump(mode="python")
        )
        if (
            authorization_bytes != self._bytes
            or strict.authorization_id != self._expected.authorization_id
        ):
            raise ValueError("authorization bytes or identity differ")
        actual = (
            requested_stage,
            requested_v230_freeze_id,
            requested_parent_binding_id,
            requested_execution_contract_id,
            requested_composition_id,
            requested_recovery_job_ids,
        )
        expected = (
            strict.authorized_stage,
            strict.v230_freeze_id,
            strict.parent_binding_id,
            strict.execution_contract_id,
            strict.composition_id,
            strict.recovery_job_ids,
        )
        if actual != expected:
            raise ValueError("requested Recovery execution parent differs")
        if not provider_execution_requested or not continuation_to_terminal_requested:
            raise ValueError("exact Recovery execution intent is required")
        if any(
            (
                successful_prefix_provider_reissue_requested,
                historical_mutation_requested,
                historical_terminal_backfill_requested,
                replacement_run_requested,
                extra_recovery_job_requested,
                max_tokens_change_requested,
                empirical_estimation_requested,
                qa_integration_requested,
            )
        ):
            raise ValueError("requested Recovery execution contains a forbidden expansion")
        return cast(
            models.Admission,
            _make(
                models.Admission,
                {
                    "authorization_id": strict.authorization_id,
                    "authorized_stage": strict.authorized_stage,
                    "v230_freeze_id": strict.v230_freeze_id,
                    "parent_binding_id": strict.parent_binding_id,
                    "execution_contract_id": strict.execution_contract_id,
                    "composition_id": strict.composition_id,
                    "recovery_job_set_sha256": strict.recovery_job_set_sha256,
                },
                "admission_id",
                models.Admission.prefix(),
            ),
        )


def _request(authorization: models.ExactOnlineAuthorization) -> dict[str, Any]:
    return {
        "authorization": authorization,
        "authorization_bytes": _bytes(authorization),
        "requested_stage": authorization.authorized_stage,
        "requested_v230_freeze_id": authorization.v230_freeze_id,
        "requested_parent_binding_id": authorization.parent_binding_id,
        "requested_execution_contract_id": authorization.execution_contract_id,
        "requested_composition_id": authorization.composition_id,
        "requested_recovery_job_ids": authorization.recovery_job_ids,
        "provider_execution_requested": True,
        "continuation_to_terminal_requested": True,
    }


def _control(name: str, *, admitted: bool, reason: str | None = None) -> models.AdmissionControl:
    return cast(
        models.AdmissionControl,
        _make(
            models.AdmissionControl,
            {
                "control_name": name,
                "admitted": admitted,
                "rejected": not admitted,
                "rejection_reason_sha256": None if reason is None else models.sha(reason.encode()),
            },
            "control_id",
            models.AdmissionControl.prefix(),
        ),
    )


def _admission_audit(
    authorization: models.ExactOnlineAuthorization,
    old_authorization: v231_models.ExactOnlineAuthorization,
) -> models.AdmissionAudit:
    guard = PrecredentialGuard(authorization)
    base = _request(authorization)
    admission = guard.admit(**base)
    controls = [_control("exact_nonconsuming_diagnostic", admitted=True)]
    attacks: tuple[tuple[str, str, Any], ...] = (
        ("missing_authorization", "authorization", None),
        ("modified_authorization_bytes", "authorization_bytes", _bytes(authorization) + b"x"),
        ("superseded_v231_authorization", "authorization", old_authorization),
        ("changed_stage", "requested_stage", authorization.authorized_stage + "_changed"),
        (
            "changed_v230_freeze",
            "requested_v230_freeze_id",
            authorization.v230_freeze_id + "_changed",
        ),
        (
            "changed_parent_binding",
            "requested_parent_binding_id",
            authorization.parent_binding_id + "_changed",
        ),
        (
            "changed_execution_contract",
            "requested_execution_contract_id",
            authorization.execution_contract_id + "_changed",
        ),
        (
            "changed_composition",
            "requested_composition_id",
            authorization.composition_id + "_changed",
        ),
        ("changed_job_set", "requested_recovery_job_ids", authorization.recovery_job_ids[:-1]),
        ("missing_provider_intent", "provider_execution_requested", False),
        ("missing_continuation_intent", "continuation_to_terminal_requested", False),
        ("historical_prefix_reissue", "successful_prefix_provider_reissue_requested", True),
        ("historical_mutation", "historical_mutation_requested", True),
        ("historical_terminal_backfill", "historical_terminal_backfill_requested", True),
        ("replacement_192_job_run", "replacement_run_requested", True),
        ("extra_recovery_job", "extra_recovery_job_requested", True),
        ("max_tokens_change", "max_tokens_change_requested", True),
        ("empirical_estimation", "empirical_estimation_requested", True),
        ("qa_integration", "qa_integration_requested", True),
    )
    for name, field, value in attacks:
        candidate = dict(base)
        candidate[field] = value
        try:
            guard.admit(**candidate)
        except ValueError as error:
            controls.append(_control(name, admitted=False, reason=str(error)))
        else:
            _fail("admission.control", f"invalid control admitted:{name}")
    return cast(
        models.AdmissionAudit,
        _make(
            models.AdmissionAudit,
            {
                "authorization_id": authorization.authorization_id,
                "admission_id": admission.admission_id,
                "controls": tuple(controls),
            },
            "audit_id",
            models.AdmissionAudit.prefix(),
        ),
    )


def _parent_attack_audit(
    authorization: models.ExactOnlineAuthorization,
) -> models.ParentAttackAudit:
    guard = PrecredentialGuard(authorization)
    base = _request(authorization)
    mutations: list[tuple[str, str, Any]] = [
        (
            "external_decision_parent",
            "external_decision_id",
            authorization.external_decision_id + "_changed",
        ),
        (
            "v231_candidate_freeze_parent",
            "v231_candidate_freeze_id",
            authorization.v231_candidate_freeze_id + "_changed",
        ),
        ("v230_freeze_parent", "v230_freeze_id", authorization.v230_freeze_id + "_changed"),
        (
            "recovery_parent_binding",
            "parent_binding_id",
            authorization.parent_binding_id + "_changed",
        ),
        (
            "recovery_execution_contract",
            "execution_contract_id",
            authorization.execution_contract_id + "_changed",
        ),
    ]
    for index in range(5):
        changed = list(authorization.recovery_job_ids)
        changed[index] = f"finance_v26_229_recovery_job:{index:064x}"
        mutations.append(
            (f"recovery_job_member_{index}", "recovery_job_ids", tuple(sorted(changed)))
        )
    rows: list[models.ParentAttack] = []
    for name, field, value in mutations:
        values = authorization.model_dump(mode="python", exclude={"authorization_id"})
        values[field] = value
        if field == "recovery_job_ids":
            values["recovery_job_set_sha256"] = models.canonical_sha256(value)
        candidate = cast(
            models.ExactOnlineAuthorization,
            _make(
                models.ExactOnlineAuthorization,
                values,
                "authorization_id",
                models.ExactOnlineAuthorization.prefix(),
            ),
        )
        request = dict(base)
        request["authorization"] = candidate
        request["authorization_bytes"] = _bytes(candidate)
        try:
            guard.admit(**request)
        except ValueError as error:
            rows.append(
                cast(
                    models.ParentAttack,
                    _make(
                        models.ParentAttack,
                        {
                            "attack_name": name,
                            "mutated_authorization_id": candidate.authorization_id,
                            "rejection_reason_sha256": models.sha(str(error).encode()),
                        },
                        "attack_id",
                        models.ParentAttack.prefix(),
                    ),
                )
            )
        else:
            _fail("parent.attack", f"fully rehashed parent attack admitted:{name}")
    return cast(
        models.ParentAttackAudit,
        _make(
            models.ParentAttackAudit,
            {"authorization_id": authorization.authorization_id, "attacks": tuple(rows)},
            "audit_id",
            models.ParentAttackAudit.prefix(),
        ),
    )


def _same_length_reordering(raw: bytes) -> bytes:
    value = json.loads(raw)
    if not isinstance(value, dict) or len(value) < 2:
        _fail("attack.input", "Manifest object cannot be reordered")
    keys = list(value)
    reordered = {key: value[key] for key in (*keys[1:], keys[0])}
    candidate = json.dumps(
        reordered, ensure_ascii=False, sort_keys=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    if raw.endswith(b"\n"):
        candidate += b"\n"
    if len(candidate) != len(raw) or candidate == raw or json.loads(candidate) != json.loads(raw):
        _fail("attack.construction", "same-length semantic-equivalent Manifest attack differs")
    return candidate


def _manifest_attack(*, name: str, version: str, raw: bytes) -> models.ManifestAttack:
    run_id, manifest_type, expected_bytes, expected_sha256, *_ = _manifest_spec(version)
    del run_id
    candidate = _same_length_reordering(raw)
    caught: Exception | None = None
    try:
        _validate_manifest_raw(
            raw=candidate,
            manifest_type=manifest_type,
            expected_bytes=expected_bytes,
            expected_sha256=expected_sha256,
        )
    except Exception as error:
        caught = error
    if not isinstance(caught, V232Error) or caught.stage != "freeze.manifest_bytes":
        _fail("attack.rejection", f"Manifest attack did not reject at byte guard:{version}")
    return cast(
        models.ManifestAttack,
        _make(
            models.ManifestAttack,
            {
                "attack_name": name,
                "predecessor_version": version,
                "original_byte_count": len(raw),
                "candidate_byte_count": len(candidate),
                "original_sha256": models.sha(raw),
                "candidate_sha256": models.sha(candidate),
                "reason_sha256": models.sha(str(caught).encode()),
            },
            "attack_id",
            models.ManifestAttack.prefix(),
        ),
    )


def _manifest_attack_audit(v229_raw: bytes, v230_raw: bytes) -> models.ManifestAttackAudit:
    attacks = (
        _manifest_attack(
            name="v26_230_manifest_same_length_key_reordering",
            version="v26.230",
            raw=v230_raw,
        ),
        _manifest_attack(
            name="v26_229_manifest_same_length_key_reordering",
            version="v26.229",
            raw=v229_raw,
        ),
    )
    return cast(
        models.ManifestAttackAudit,
        _make(
            models.ManifestAttackAudit,
            {"attacks": attacks},
            "audit_id",
            models.ManifestAttackAudit.prefix(),
        ),
    )


def _scope(authorization: models.ExactOnlineAuthorization) -> models.ScopeAudit:
    return cast(
        models.ScopeAudit,
        _make(
            models.ScopeAudit,
            {"authorization_id": authorization.authorization_id},
            "audit_id",
            models.ScopeAudit.prefix(),
        ),
    )


def _source_identity(
    repository_root: Path, source_commit: str, source_tree: str
) -> models.SourceIdentity:
    development = source_commit == source_tree == "1" * 40
    if development:
        resolved_commit = _git(repository_root, "rev-parse", "HEAD").decode().strip()
        resolved_tree = _git(repository_root, "rev-parse", "HEAD^{tree}").decode().strip()
    else:
        resolved_commit = (
            _git(repository_root, "rev-parse", f"{source_commit}^{{commit}}").decode().strip()
        )
        resolved_tree = (
            _git(repository_root, "rev-parse", f"{source_commit}^{{tree}}").decode().strip()
        )
        if resolved_commit != source_commit or resolved_tree != source_tree:
            _fail("source.commit_tree", "source commit/tree relation differs")
    members: list[models.SourceMember] = []
    for relative_path in SOURCE_PATHS:
        current = (repository_root / relative_path).read_bytes()
        if development:
            committed = current
            blob = hashlib_sha1_blob(current)
        else:
            committed = _git(repository_root, "show", f"{source_commit}:{relative_path}")
            blob = (
                _git(repository_root, "rev-parse", f"{source_commit}:{relative_path}")
                .decode()
                .strip()
            )
            if committed != current:
                _fail("source.current", f"current source differs:{relative_path}")
        members.append(
            models.SourceMember(
                relative_path=relative_path,
                git_blob_oid=blob,
                sha256=models.sha(committed),
                byte_count=len(committed),
                committed_current_bytes_match=True,
            )
        )
    ordered = tuple(sorted(members, key=lambda row: row.relative_path))
    return cast(
        models.SourceIdentity,
        _make(
            models.SourceIdentity,
            {
                "source_commit": source_commit if not development else resolved_commit,
                "source_tree": resolved_tree,
                "members": ordered,
                "member_set_sha256": models.canonical_sha256(
                    tuple(row.model_dump(mode="json") for row in ordered)
                ),
            },
            "source_identity_id",
            models.SourceIdentity.prefix(),
        ),
    )


def hashlib_sha1_blob(payload: bytes) -> str:
    import hashlib

    return hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload, usedforsecurity=False
    ).hexdigest()


def _implementation_binding(
    repository_root: Path,
    source: models.SourceIdentity,
    external: models.ExternalRepairDecision,
    freeze: models.V231CandidateFreeze,
) -> models.ImplementationBinding:
    tree = ast.parse((repository_root / IMPLEMENTATION_PATH).read_text(encoding="utf-8"))
    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if not set(REQUIRED_SYMBOLS).issubset(functions):
        _fail("implementation.symbols", "required implementation symbol missing")
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    if names & {"requests", "httpx", "urllib", "socket", "environ"} or attrs & {
        "urlopen",
        "request",
        "getenv",
    }:
        _fail("implementation.scope", "network or credential symbol present")
    return cast(
        models.ImplementationBinding,
        _make(
            models.ImplementationBinding,
            {
                "source_identity_id": source.source_identity_id,
                "external_decision_id": external.decision_id,
                "v231_candidate_freeze_id": freeze.freeze_id,
                "required_symbols": REQUIRED_SYMBOLS,
            },
            "binding_id",
            models.ImplementationBinding.prefix(),
        ),
    )


def _gate(evidence: tuple[tuple[str, tuple[str, ...]], ...]) -> models.GateEvaluation:
    gates = tuple(models.Gate(name=name, evidence_ids=ids) for name, ids in evidence)
    return cast(
        models.GateEvaluation,
        _make(
            models.GateEvaluation,
            {"gates": gates},
            "evaluation_id",
            models.GateEvaluation.prefix(),
        ),
    )


def build(
    *,
    repository_root: Path,
    output_dir: Path,
    external_review_path: Path,
    source_identity: tuple[str, str],
) -> models.Report:
    external, review = _external_decision(external_review_path)
    v231_manifest, _, _ = _manifest_authority(repository_root, "v26.231")
    v230_manifest, _, v230_raw = _manifest_authority(repository_root, "v26.230")
    v229_manifest, _, v229_raw = _manifest_authority(repository_root, "v26.229")
    v231_freeze = _v231_candidate_freeze(repository_root, external, v231_manifest)
    freeze = _v230_freeze(repository_root, external, v231_freeze, v230_manifest)
    parent = _recovery_parent_binding(repository_root, freeze, v229_manifest, v230_manifest)
    contract = _recovery_execution_contract(repository_root, parent)
    composition = _composition(freeze, parent, contract)
    authorization = _authorization(
        external,
        v231_freeze,
        v229_manifest,
        v230_manifest,
        freeze,
        parent,
        contract,
        composition,
    )
    old_authorization = v231_models.ExactOnlineAuthorization.model_validate(
        _load(
            _formal_dir(repository_root, V231_RUN_ID) / "exact_online_execution_authorization.json"
        )
    )
    admission = _admission_audit(authorization, old_authorization)
    parent_attacks = _parent_attack_audit(authorization)
    manifest_attacks = _manifest_attack_audit(v229_raw, v230_raw)
    scope = _scope(authorization)
    source = _source_identity(repository_root, *source_identity)
    implementation = _implementation_binding(repository_root, source, external, v231_freeze)
    gate = _gate(
        (
            (
                "G0_external_scope_v231_candidate_and_exact_v230_manifest_byte_freeze",
                (
                    external.decision_id,
                    v231_freeze.freeze_id,
                    v230_manifest.authority_id,
                    freeze.freeze_id,
                ),
            ),
            (
                "G1_exact_v229_manifest_byte_contract_population_and_33_jobs",
                (v229_manifest.authority_id, parent.binding_id),
            ),
            ("G2_exact_55_prefix_and_33_failed_request_authority", (parent.binding_id,)),
            (
                "G3_continue_from_failure_to_terminal_semantics",
                (contract.contract_id, composition.composition_id),
            ),
            ("G4_explicit_residual_resource_and_call_budget", (contract.contract_id,)),
            (
                "G5_fresh_manifest_byte_bound_one_time_authorization",
                (authorization.authorization_id,),
            ),
            (
                "G6_precredential_parent_and_manifest_byte_attacks",
                (admission.audit_id, parent_attacks.audit_id, manifest_attacks.audit_id),
            ),
            (
                "G7_zero_provider_recovery_empirical_boundary",
                (scope.audit_id, implementation.binding_id),
            ),
        )
    )
    decision = cast(
        models.Decision,
        _make(
            models.Decision,
            {
                "external_decision_id": external.decision_id,
                "gate_evaluation_id": gate.evaluation_id,
                "authorization_id": authorization.authorization_id,
            },
            "decision_id",
            models.Decision.prefix(),
        ),
    )
    transition = cast(
        models.Transition,
        _make(
            models.Transition,
            {
                "decision_id": decision.decision_id,
                "authorization_id": authorization.authorization_id,
            },
            "transition_id",
            models.Transition.prefix(),
        ),
    )
    report = cast(
        models.Report,
        _make(
            models.Report,
            {
                "source_identity_id": source.source_identity_id,
                "implementation_binding_id": implementation.binding_id,
                "external_decision_id": external.decision_id,
                "v231_candidate_freeze_id": v231_freeze.freeze_id,
                "v229_manifest_byte_authority_id": v229_manifest.authority_id,
                "v230_manifest_byte_authority_id": v230_manifest.authority_id,
                "v230_freeze_id": freeze.freeze_id,
                "parent_binding_id": parent.binding_id,
                "execution_contract_id": contract.contract_id,
                "composition_id": composition.composition_id,
                "authorization_id": authorization.authorization_id,
                "admission_audit_id": admission.audit_id,
                "parent_attack_audit_id": parent_attacks.audit_id,
                "manifest_attack_audit_id": manifest_attacks.audit_id,
                "scope_audit_id": scope.audit_id,
                "gate_evaluation_id": gate.evaluation_id,
                "decision_id": decision.decision_id,
                "transition_id": transition.transition_id,
            },
            "report_id",
            models.Report.prefix(),
        ),
    )
    payloads = {
        "decision.json": _bytes(decision),
        "exact_online_execution_authorization.json": _bytes(authorization),
        "external_manifest_byte_repair_decision.json": _bytes(external),
        "external_review.txt": review,
        "gate_evaluation.json": _bytes(gate),
        "implementation_binding.json": _bytes(implementation),
        "manifest_byte_negative_control_audit.json": _bytes(manifest_attacks),
        "online_execution_composition.json": _bytes(composition),
        "operator_directive.txt": DIRECTIVE,
        "parent_attack_audit.json": _bytes(parent_attacks),
        "precredential_admission_audit.json": _bytes(admission),
        "recovery_execution_contract.json": _bytes(contract),
        "recovery_parent_binding.json": _bytes(parent),
        "report.json": _bytes(report),
        "scope_boundary_audit.json": _bytes(scope),
        "source_identity.json": _bytes(source),
        "transition.json": _bytes(transition),
        "v229_manifest_byte_authority.json": _bytes(v229_manifest),
        "v230_freeze.json": _bytes(freeze),
        "v230_manifest_byte_authority.json": _bytes(v230_manifest),
        "v231_candidate_freeze.json": _bytes(v231_freeze),
        "v231_manifest_byte_authority.json": _bytes(v231_manifest),
    }
    manifest = models.artifact_manifest(payloads)
    output_dir.mkdir(parents=True, exist_ok=False)
    for relative_path, payload in sorted(payloads.items()):
        (output_dir / relative_path).write_bytes(payload)
    (output_dir / "artifact_manifest.json").write_bytes(_bytes(manifest))
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
