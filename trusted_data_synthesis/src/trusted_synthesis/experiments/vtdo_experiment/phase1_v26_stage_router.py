from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.synthesis.schema import CompiledProofCarryingArtifacts
from trusted_synthesis.core.trajectory.admission import (
    JointCompilationAdmissionArtifact,
    JointCompilationAuditEvidence,
)
from trusted_synthesis.core.trajectory.scaffolding import (
    CapabilityScaffoldAdmissionArtifact,
    CapabilityScaffoldGateEvidence,
    CapabilityScaffoldLadderCompilation,
)
from trusted_synthesis.core.vtdo.state_space import TrajectoryStateSpaceCompilation
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_heterogeneous_mainline import (
    CapabilityHeterogeneousMainlineProtocol,
    MainlinePreflightReport,
    mainline_implementation_paths,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    BridgeCellObservation,
    BridgeConfirmationAuthorization,
    BridgeDevelopmentAuthorization,
    BridgeRolloutObservation,
    CompilerAssistedBridgeConfirmation,
    CompilerAssistedBridgeContract,
    CompilerAssistedBridgeSupportFreeze,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_state_support import (
    StateSupportDiscoveryContract,
    StateSupportFreeze,
    TaskStateSupportObservation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    V26FreshTaskPopulation,
    validate_population_compilation,
)
from trusted_synthesis.hashing import canonical_hash

V26_STAGE_ROUTER_VERSION = "finance_v26_stage_router.v4"
V26_STAGE_ARTIFACT_REFERENCE_VERSION = "finance_v26_stage_artifact_reference.v3"

V26Stage = Literal[
    "fresh_task_population",
    "joint_compilation",
    "joint_audit",
    "joint_admission",
    "scaffold_compilation",
    "scaffold_audit",
    "scaffold_admission",
    "bridge_development_authorization",
    "bridge_rollout",
    "bridge_aggregation",
    "bridge_support_freeze",
    "fresh_confirmation_population",
    "fresh_confirmation_compilation",
    "bridge_confirmation_authorization",
    "bridge_confirmation_rollout",
    "bridge_confirmation_aggregation",
    "bridge_confirmation",
    "state_support_contract",
    "state_support_observation",
    "state_support_freeze",
]
StageArtifactRole = Literal[
    "mainline_protocol",
    "mainline_preflight",
    "fresh_task_population",
    "compiled_proof_artifacts",
    "trajectory_state_space",
    "joint_audit_evidence",
    "joint_admission",
    "scaffold_ladder",
    "scaffold_gate_evidence",
    "scaffold_admission",
    "bridge_development_authorization",
    "bridge_rollout",
    "bridge_cell",
    "bridge_support_freeze",
    "bridge_confirmation_authorization",
    "bridge_confirmation",
    "state_support_contract",
    "task_state_support_observation",
    "state_support_freeze",
]

V26_STAGES: tuple[V26Stage, ...] = (
    "fresh_task_population",
    "joint_compilation",
    "joint_audit",
    "joint_admission",
    "scaffold_compilation",
    "scaffold_audit",
    "scaffold_admission",
    "bridge_development_authorization",
    "bridge_rollout",
    "bridge_aggregation",
    "bridge_support_freeze",
    "fresh_confirmation_population",
    "fresh_confirmation_compilation",
    "bridge_confirmation_authorization",
    "bridge_confirmation_rollout",
    "bridge_confirmation_aggregation",
    "bridge_confirmation",
    "state_support_contract",
    "state_support_observation",
    "state_support_freeze",
)
_STAGE_ROLES: dict[V26Stage, tuple[StageArtifactRole, ...]] = {
    "fresh_task_population": ("fresh_task_population",),
    "joint_compilation": ("compiled_proof_artifacts", "trajectory_state_space"),
    "joint_audit": ("joint_audit_evidence",),
    "joint_admission": ("joint_admission",),
    "scaffold_compilation": ("scaffold_ladder",),
    "scaffold_audit": ("scaffold_gate_evidence",),
    "scaffold_admission": ("scaffold_admission",),
    "bridge_development_authorization": ("bridge_development_authorization",),
    "bridge_rollout": ("bridge_rollout",),
    "bridge_aggregation": ("bridge_cell",),
    "bridge_support_freeze": ("bridge_support_freeze",),
    "fresh_confirmation_population": ("fresh_task_population",),
    "fresh_confirmation_compilation": (
        "compiled_proof_artifacts",
        "trajectory_state_space",
        "joint_audit_evidence",
        "joint_admission",
        "scaffold_ladder",
        "scaffold_gate_evidence",
        "scaffold_admission",
    ),
    "bridge_confirmation_authorization": ("bridge_confirmation_authorization",),
    "bridge_confirmation_rollout": ("bridge_rollout",),
    "bridge_confirmation_aggregation": ("bridge_cell",),
    "bridge_confirmation": ("bridge_confirmation",),
    "state_support_contract": ("state_support_contract",),
    "state_support_observation": ("task_state_support_observation",),
    "state_support_freeze": ("state_support_freeze",),
}
_CLI_STAGE_ARTIFACT_ROLES = {
    role for roles in _STAGE_ROLES.values() for role in roles
}
_API_STAGES: frozenset[V26Stage] = frozenset(
    {
        "bridge_rollout",
        "bridge_confirmation_rollout",
        "state_support_observation",
    }
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class V26StageArtifactReference(FrozenModel):
    reference_id: str = Field(min_length=1)
    role: StageArtifactRole
    artifact_id: str = Field(min_length=1)
    artifact_schema_version: str = Field(min_length=1)
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    payload_hash: str = Field(min_length=1)
    record_count: int = Field(ge=1)
    schema_contract_replayed: Literal[True] = True
    schema_version: Literal["finance_v26_stage_artifact_reference.v3"] = (
        "finance_v26_stage_artifact_reference.v3"
    )

    @model_validator(mode="after")
    def validate_reference(self) -> V26StageArtifactReference:
        if self.reference_id != v26_stage_artifact_reference_id(self):
            raise ValueError("v26 stage artifact reference identity is invalid")
        return self


class V26StageLedger(FrozenModel):
    ledger_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    preflight_report_id: str = Field(min_length=1)
    protocol_reference: V26StageArtifactReference
    preflight_reference: V26StageArtifactReference
    completed_stages: tuple[V26Stage, ...]
    artifacts_by_stage: dict[str, tuple[V26StageArtifactReference, ...]]
    model_api_call_count: int = Field(ge=0)
    model_api_calls_by_stage: dict[str, int]
    gpu_job_count: int = Field(ge=0)
    current_stage: V26Stage | Literal["initialized"]
    next_stage: V26Stage | Literal["complete"]
    schema_version: Literal["finance_v26_stage_router.v4"] = "finance_v26_stage_router.v4"

    @model_validator(mode="after")
    def validate_ledger(self) -> V26StageLedger:
        if (
            self.protocol_reference.role != "mainline_protocol"
            or self.protocol_reference.artifact_id != self.protocol_id
        ):
            raise ValueError("v26 protocol reference is not identity-bound")
        if (
            self.preflight_reference.role != "mainline_preflight"
            or self.preflight_reference.artifact_id != self.preflight_report_id
        ):
            raise ValueError("v26 preflight reference is not identity-bound")
        expected_prefix = V26_STAGES[: len(self.completed_stages)]
        if self.completed_stages != expected_prefix:
            raise ValueError("v26 stages are incomplete, skipped, or reordered")
        if set(self.artifacts_by_stage) != set(self.completed_stages):
            raise ValueError("v26 stage artifact ledger is incomplete")
        expected_current: V26Stage | Literal["initialized"] = (
            self.completed_stages[-1] if self.completed_stages else "initialized"
        )
        if self.current_stage != expected_current:
            raise ValueError("v26 current stage is inconsistent")
        expected_next: V26Stage | Literal["complete"] = (
            V26_STAGES[len(self.completed_stages)]
            if len(self.completed_stages) < len(V26_STAGES)
            else "complete"
        )
        if self.next_stage != expected_next:
            raise ValueError("v26 next stage is inconsistent")
        scaffold_admitted = "scaffold_admission" in self.completed_stages
        if self.model_api_call_count and not scaffold_admitted:
            raise ValueError("v26 model API calls occurred before Scaffold Admission")
        expected_api_stages = {
            stage for stage in self.completed_stages if stage in _API_STAGES
        }
        if set(self.model_api_calls_by_stage) != expected_api_stages:
            raise ValueError("v26 per-stage API telemetry is incomplete or unexpected")
        if any(count < 0 for count in self.model_api_calls_by_stage.values()):
            raise ValueError("v26 per-stage API telemetry cannot be negative")
        if sum(self.model_api_calls_by_stage.values()) != self.model_api_call_count:
            raise ValueError("v26 aggregate API telemetry is not derived from stages")
        if self.gpu_job_count:
            raise ValueError("v26 pre-training stage router cannot record GPU jobs")
        _validate_v26_stage_ledger_contents(self)
        if self.ledger_id != v26_stage_ledger_id(self):
            raise ValueError("v26 stage ledger identity is invalid")
        return self


def make_v26_stage_artifact_reference(
    role: StageArtifactRole,
    path: Path,
) -> V26StageArtifactReference:
    payload = _load_json(path)
    parsed = _validate_role_payload(role, payload)
    artifact_id, schema_version, record_count = _artifact_identity(parsed, payload)
    values = {
        "role": role,
        "artifact_id": artifact_id,
        "artifact_schema_version": schema_version,
        "path": str(path.resolve()),
        "sha256": _sha256(path),
        "payload_hash": canonical_hash(payload, prefix="v26_stage_payload:"),
        "record_count": record_count,
        "schema_version": V26_STAGE_ARTIFACT_REFERENCE_VERSION,
    }
    provisional = V26StageArtifactReference.model_construct(reference_id="pending", **values)
    return V26StageArtifactReference(
        reference_id=v26_stage_artifact_reference_id(provisional),
        **values,
    )


def initialize_v26_stage_ledger(
    *,
    run_id: str,
    protocol_path: Path,
    preflight_path: Path,
) -> V26StageLedger:
    protocol_payload = _load_json(protocol_path)
    protocol = CapabilityHeterogeneousMainlineProtocol.model_validate(protocol_payload)
    preflight_payload = _load_json(preflight_path)
    preflight = MainlinePreflightReport.model_validate(preflight_payload)
    if preflight.status != "passed" or preflight.protocol_id != protocol.protocol_id:
        raise ValueError("v26 stage router requires a passing, protocol-bound preflight")
    _validate_preflight_manifest(protocol, preflight)
    protocol_ref = make_v26_stage_artifact_reference("mainline_protocol", protocol_path)
    preflight_ref = make_v26_stage_artifact_reference("mainline_preflight", preflight_path)
    return _make_ledger(
        run_id=run_id,
        protocol_id=protocol.protocol_id,
        preflight_report_id=preflight.report_id,
        protocol_reference=protocol_ref,
        preflight_reference=preflight_ref,
        completed_stages=(),
        artifacts_by_stage={},
        model_api_call_count=0,
        model_api_calls_by_stage={},
        gpu_job_count=0,
    )


def advance_v26_stage(
    ledger: V26StageLedger,
    *,
    stage: V26Stage,
    artifacts: Sequence[V26StageArtifactReference],
    model_api_calls: int = 0,
    gpu_jobs: int = 0,
) -> V26StageLedger:
    replay_v26_stage_ledger(ledger)
    if ledger.next_stage != stage:
        raise ValueError(f"v26 stage transition expected {ledger.next_stage}, got {stage}")
    rows = tuple(sorted(artifacts, key=lambda item: (item.role, item.artifact_id)))
    expected_roles = set(_STAGE_ROLES[stage])
    observed_roles = {item.role for item in rows}
    if observed_roles != expected_roles or len(rows) != len(expected_roles):
        raise ValueError("v26 stage artifact roles are incomplete or unexpected")
    for item in rows:
        _replay_reference(item)
    _validate_stage_cardinality(stage, rows)
    _validate_cross_stage_bindings(ledger, stage, rows)
    if model_api_calls and stage not in _API_STAGES:
        raise ValueError("v26 model API calls occurred outside an admitted rollout stage")
    if stage in {"bridge_rollout", "bridge_confirmation_rollout"}:
        expected_calls = _bridge_provider_call_count(rows)
        if model_api_calls != expected_calls:
            raise ValueError("v26 Bridge API telemetry differs from provider-call lineage")
    if stage == "state_support_observation" and model_api_calls <= 0:
        raise ValueError("v26 State-support observations require explicit API telemetry")
    if gpu_jobs:
        raise ValueError("v26 GPU jobs belong to the post-freeze training router")
    completed = (*ledger.completed_stages, stage)
    by_stage = dict(ledger.artifacts_by_stage)
    by_stage[stage] = rows
    api_calls_by_stage = dict(ledger.model_api_calls_by_stage)
    if stage in _API_STAGES:
        api_calls_by_stage[stage] = model_api_calls
    return _make_ledger(
        run_id=ledger.run_id,
        protocol_id=ledger.protocol_id,
        preflight_report_id=ledger.preflight_report_id,
        protocol_reference=ledger.protocol_reference,
        preflight_reference=ledger.preflight_reference,
        completed_stages=completed,
        artifacts_by_stage=by_stage,
        model_api_call_count=ledger.model_api_call_count + model_api_calls,
        model_api_calls_by_stage=api_calls_by_stage,
        gpu_job_count=ledger.gpu_job_count + gpu_jobs,
    )


def replay_v26_stage_ledger(ledger: V26StageLedger) -> None:
    _validate_v26_stage_ledger_contents(ledger)


def _validate_v26_stage_ledger_contents(ledger: V26StageLedger) -> None:
    protocol = _replay_reference(ledger.protocol_reference)
    preflight = _replay_reference(ledger.preflight_reference)
    if not isinstance(protocol, CapabilityHeterogeneousMainlineProtocol):
        raise ValueError("v26 protocol reference did not replay as a protocol")
    if not isinstance(preflight, MainlinePreflightReport):
        raise ValueError("v26 preflight reference did not replay as a preflight")
    if (
        protocol.protocol_id != ledger.protocol_id
        or preflight.report_id != ledger.preflight_report_id
        or preflight.protocol_id != protocol.protocol_id
        or preflight.status != "passed"
    ):
        raise ValueError("v26 protocol and preflight replay are not mutually bound")
    _validate_preflight_manifest(protocol, preflight)
    for stage in ledger.completed_stages:
        rows = ledger.artifacts_by_stage[stage]
        expected_roles = set(_STAGE_ROLES[stage])
        observed_roles = {item.role for item in rows}
        if observed_roles != expected_roles or len(rows) != len(expected_roles):
            raise ValueError("v26 stage artifact roles are incomplete or unexpected")
        for item in rows:
            _replay_reference(item)
        _validate_stage_cardinality(stage, rows)
        _validate_cross_stage_bindings(ledger, stage, rows)
        if stage in {"bridge_rollout", "bridge_confirmation_rollout"}:
            expected_calls = _bridge_provider_call_count(rows)
            if ledger.model_api_calls_by_stage.get(stage) != expected_calls:
                raise ValueError(
                    "v26 Bridge API telemetry differs from provider-call lineage"
                )
        if (
            stage == "state_support_observation"
            and ledger.model_api_calls_by_stage.get(stage, 0) <= 0
        ):
            raise ValueError(
                "v26 State-support observations require explicit API telemetry"
            )


def load_v26_stage_ledger(path: Path) -> V26StageLedger:
    ledger = V26StageLedger.model_validate(_load_json(path))
    replay_v26_stage_ledger(ledger)
    return ledger


def write_v26_stage_ledger(ledger: V26StageLedger, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(ledger.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def v26_stage_artifact_reference_id(value: V26StageArtifactReference) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"reference_id"}),
        prefix="finance_v26_stage_artifact_reference:",
    )


def v26_stage_ledger_id(value: V26StageLedger) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"ledger_id"}),
        prefix="finance_v26_stage_ledger:",
    )


def _make_ledger(
    *,
    run_id: str,
    protocol_id: str,
    preflight_report_id: str,
    protocol_reference: V26StageArtifactReference,
    preflight_reference: V26StageArtifactReference,
    completed_stages: tuple[V26Stage, ...],
    artifacts_by_stage: Mapping[str, tuple[V26StageArtifactReference, ...]],
    model_api_call_count: int,
    model_api_calls_by_stage: Mapping[str, int],
    gpu_job_count: int,
) -> V26StageLedger:
    current: V26Stage | Literal["initialized"] = (
        completed_stages[-1] if completed_stages else "initialized"
    )
    next_stage: V26Stage | Literal["complete"] = (
        V26_STAGES[len(completed_stages)]
        if len(completed_stages) < len(V26_STAGES)
        else "complete"
    )
    values = {
        "run_id": run_id,
        "protocol_id": protocol_id,
        "preflight_report_id": preflight_report_id,
        "protocol_reference": protocol_reference,
        "preflight_reference": preflight_reference,
        "completed_stages": completed_stages,
        "artifacts_by_stage": dict(artifacts_by_stage),
        "model_api_call_count": model_api_call_count,
        "model_api_calls_by_stage": dict(sorted(model_api_calls_by_stage.items())),
        "gpu_job_count": gpu_job_count,
        "current_stage": current,
        "next_stage": next_stage,
        "schema_version": V26_STAGE_ROUTER_VERSION,
    }
    provisional = V26StageLedger.model_construct(ledger_id="pending", **values)
    return V26StageLedger(ledger_id=v26_stage_ledger_id(provisional), **values)


def _replay_reference(reference: V26StageArtifactReference) -> Any:
    path = Path(reference.path)
    if not path.is_file() or _sha256(path) != reference.sha256:
        raise ValueError("v26 stage artifact content hash replay failed")
    payload = _load_json(path)
    if canonical_hash(payload, prefix="v26_stage_payload:") != reference.payload_hash:
        raise ValueError("v26 stage artifact canonical payload replay failed")
    parsed = _validate_role_payload(reference.role, payload)
    artifact_id, schema_version, record_count = _artifact_identity(parsed, payload)
    if (
        artifact_id != reference.artifact_id
        or schema_version != reference.artifact_schema_version
        or record_count != reference.record_count
    ):
        raise ValueError("v26 stage artifact typed identity replay failed")
    return parsed


def _validate_role_payload(role: StageArtifactRole, payload: Any) -> Any:
    model_by_role: dict[str, type[BaseModel]] = {
        "mainline_protocol": CapabilityHeterogeneousMainlineProtocol,
        "mainline_preflight": MainlinePreflightReport,
        "compiled_proof_artifacts": CompiledProofCarryingArtifacts,
        "trajectory_state_space": TrajectoryStateSpaceCompilation,
        "joint_audit_evidence": JointCompilationAuditEvidence,
        "joint_admission": JointCompilationAdmissionArtifact,
        "scaffold_ladder": CapabilityScaffoldLadderCompilation,
        "scaffold_gate_evidence": CapabilityScaffoldGateEvidence,
        "scaffold_admission": CapabilityScaffoldAdmissionArtifact,
        "bridge_development_authorization": BridgeDevelopmentAuthorization,
        "bridge_rollout": BridgeRolloutObservation,
        "bridge_cell": BridgeCellObservation,
        "bridge_support_freeze": CompilerAssistedBridgeSupportFreeze,
        "bridge_confirmation_authorization": BridgeConfirmationAuthorization,
        "bridge_confirmation": CompilerAssistedBridgeConfirmation,
        "state_support_contract": StateSupportDiscoveryContract,
        "task_state_support_observation": TaskStateSupportObservation,
        "state_support_freeze": StateSupportFreeze,
        "fresh_task_population": V26FreshTaskPopulation,
    }
    model = model_by_role[role]
    if isinstance(payload, list):
        if not payload:
            raise ValueError("v26 stage artifact list cannot be empty")
        return tuple(model.model_validate(item) for item in payload)
    return model.model_validate(payload)


def _artifact_identity(parsed: Any, payload: Any) -> tuple[str, str, int]:
    if isinstance(parsed, V26FreshTaskPopulation):
        return parsed.population_id, parsed.schema_version, parsed.task_count
    if isinstance(parsed, tuple):
        ids = tuple(_model_artifact_id(item) for item in parsed)
        if len(ids) != len(set(ids)) or ids != tuple(sorted(ids)):
            raise ValueError("v26 stage artifact list identities must be unique and sorted")
        versions = {cast(str, item.schema_version) for item in parsed}
        if len(versions) != 1:
            raise ValueError("v26 stage artifact list mixes schema versions")
        return (
            canonical_hash(ids, prefix="v26_stage_artifact_collection:"),
            next(iter(versions)),
            len(parsed),
        )
    if isinstance(parsed, BaseModel):
        return _model_artifact_id(parsed), cast(str, parsed.schema_version), 1
    raise TypeError("v26 stage payload did not resolve to a typed artifact")


def _model_artifact_id(value: BaseModel) -> str:
    for field in (
        "artifact_id",
        "population_id",
        "report_id",
        "protocol_id",
        "authorization_id",
        "confirmation_id",
        "compilation_id",
        "evidence_id",
        "admission_id",
        "ladder_id",
        "rollout_id",
        "observation_id",
        "freeze_id",
        "contract_id",
    ):
        candidate = getattr(value, field, None)
        if candidate:
            return cast(str, candidate)
    return canonical_hash(value.model_dump(mode="json"), prefix="v26_typed_stage_artifact:")


def _validate_stage_cardinality(
    stage: V26Stage,
    rows: Sequence[V26StageArtifactReference],
) -> None:
    by_role = {item.role: item for item in rows}
    if (
        stage in {"bridge_rollout", "bridge_confirmation_rollout"}
        and by_role["bridge_rollout"].record_count % 48 != 0
    ):
        raise ValueError("Bridge Rollout stage must contain complete 48-rollout cells")


def _validate_cross_stage_bindings(
    ledger: V26StageLedger,
    stage: V26Stage,
    rows: Sequence[V26StageArtifactReference],
) -> None:
    current = _models_by_role(rows)
    if stage == "fresh_task_population":
        population = current["fresh_task_population"][0]
        if population.phase != "development" or population.protocol_id != ledger.protocol_id:
            raise ValueError("v26 Development Population crosses protocol or phase identities")
        return
    if stage == "joint_compilation":
        _validate_compilation_bundle(
            population=_stage_population(ledger, "fresh_task_population"),
            models=current,
        )
        return
    if stage == "joint_audit":
        compiled = _stage_models(ledger, "joint_compilation", "compiled_proof_artifacts")
        audits = current["joint_audit_evidence"]
        _validate_joint_audits(compiled, audits)
        return
    if stage == "joint_admission":
        compiled = _stage_models(ledger, "joint_compilation", "compiled_proof_artifacts")
        audits = _stage_models(ledger, "joint_audit", "joint_audit_evidence")
        _validate_joint_admissions(compiled, audits, current["joint_admission"])
        return
    if stage == "scaffold_compilation":
        admissions = _stage_models(ledger, "joint_admission", "joint_admission")
        _validate_scaffold_ladders(
            admissions,
            current["scaffold_ladder"],
            _stage_population(ledger, "fresh_task_population"),
        )
        return
    if stage == "scaffold_audit":
        ladders = _stage_models(ledger, "scaffold_compilation", "scaffold_ladder")
        _validate_scaffold_audits(ladders, current["scaffold_gate_evidence"])
        return
    if stage == "scaffold_admission":
        ladders = _stage_models(ledger, "scaffold_compilation", "scaffold_ladder")
        audits = _stage_models(ledger, "scaffold_audit", "scaffold_gate_evidence")
        _validate_scaffold_admissions(ladders, audits, current["scaffold_admission"])
        return
    if stage == "bridge_development_authorization":
        authorizations = current["bridge_development_authorization"]
        admissions = _stage_models(ledger, "scaffold_admission", "scaffold_admission")
        _validate_bridge_authorization(
            authorizations,
            admissions,
            population=_stage_population(ledger, "fresh_task_population"),
            bridge_contract=_protocol_bridge_contract(ledger),
            confirmation=False,
        )
        return
    if stage == "bridge_rollout":
        admissions = _stage_models(ledger, "scaffold_admission", "scaffold_admission")
        authorization = _stage_models(
            ledger,
            "bridge_development_authorization",
            "bridge_development_authorization",
        )[0]
        _validate_bridge_rollouts(
            admissions,
            current["bridge_rollout"],
            population=_stage_population(ledger, "fresh_task_population"),
            phase="development",
            expected_levels_per_task=4,
            phase_authorization_id=authorization.authorization_id,
            bridge_contract=_protocol_bridge_contract(ledger),
        )
        return
    if stage == "bridge_aggregation":
        rollouts = _stage_models(ledger, "bridge_rollout", "bridge_rollout")
        _validate_bridge_cells(rollouts, current["bridge_cell"], phase="development")
        return
    if stage == "bridge_support_freeze":
        cells = _stage_models(ledger, "bridge_aggregation", "bridge_cell")
        freezes = current["bridge_support_freeze"]
        if len(freezes) != 1 or tuple(freezes[0].observations) != cells:
            raise ValueError("Bridge support freeze does not embed the Development cells")
        return
    if stage == "fresh_confirmation_population":
        development = _stage_population(ledger, "fresh_task_population")
        confirmation = current["fresh_task_population"][0]
        if (
            confirmation.phase != "fresh_confirmation"
            or confirmation.protocol_id != ledger.protocol_id
            or confirmation.source_population_id == development.source_population_id
        ):
            raise ValueError("fresh Bridge confirmation crosses protocol, phase, or source roots")
        development_ids = set(development.task_ids)
        confirmation_ids = set(confirmation.task_ids)
        if development_ids & confirmation_ids:
            raise ValueError("fresh Bridge confirmation reuses Development tasks")
        return
    if stage == "fresh_confirmation_compilation":
        _validate_complete_compilation_bundle(
            _stage_population(ledger, "fresh_confirmation_population"),
            current,
        )
        return
    if stage == "bridge_confirmation_authorization":
        authorizations = current["bridge_confirmation_authorization"]
        freezes = _stage_models(ledger, "bridge_support_freeze", "bridge_support_freeze")
        admissions = _stage_models(
            ledger,
            "fresh_confirmation_compilation",
            "scaffold_admission",
        )
        if len(authorizations) != 1 or len(freezes) != 1:
            raise ValueError("Bridge confirmation authorization cardinality is invalid")
        authorization = authorizations[0]
        if authorization.support_freeze_id != freezes[0].freeze_id:
            raise ValueError("Bridge confirmation authorization crosses support freezes")
        _validate_bridge_authorization(
            authorizations,
            admissions,
            population=_stage_population(ledger, "fresh_confirmation_population"),
            bridge_contract=_protocol_bridge_contract(ledger),
            confirmation=True,
        )
        return
    if stage == "bridge_confirmation_rollout":
        admissions = _stage_models(
            ledger,
            "fresh_confirmation_compilation",
            "scaffold_admission",
        )
        _validate_bridge_rollouts(
            admissions,
            current["bridge_rollout"],
            population=_stage_population(ledger, "fresh_confirmation_population"),
            phase="fresh_confirmation",
            expected_levels_per_task=1,
            phase_authorization_id=_stage_models(
                ledger,
                "bridge_confirmation_authorization",
                "bridge_confirmation_authorization",
            )[0].authorization_id,
            bridge_contract=_protocol_bridge_contract(ledger),
        )
        return
    if stage == "bridge_confirmation_aggregation":
        rollouts = _stage_models(
            ledger,
            "bridge_confirmation_rollout",
            "bridge_rollout",
        )
        _validate_bridge_cells(
            rollouts,
            current["bridge_cell"],
            phase="fresh_confirmation",
        )
        return
    if stage == "bridge_confirmation":
        confirmations = current["bridge_confirmation"]
        cells = _stage_models(
            ledger,
            "bridge_confirmation_aggregation",
            "bridge_cell",
        )
        freezes = _stage_models(ledger, "bridge_support_freeze", "bridge_support_freeze")
        if (
            len(confirmations) != 1
            or tuple(confirmations[0].observations) != cells
            or confirmations[0].support_freeze_id != freezes[0].freeze_id
        ):
            raise ValueError("Bridge confirmation does not replay its frozen inputs")
        return
    if stage == "state_support_contract":
        contracts = current["state_support_contract"]
        confirmations = _stage_models(ledger, "bridge_confirmation", "bridge_confirmation")
        if (
            len(contracts) != 1
            or len(confirmations) != 1
            or contracts[0].bridge_confirmation_id != confirmations[0].confirmation_id
            or contracts[0].confirmed_task_conditions
            != confirmations[0].confirmed_task_conditions
        ):
            raise ValueError("State-support contract crosses Bridge confirmations")
        return
    if stage == "state_support_observation":
        observations = current["task_state_support_observation"]
        contracts = _stage_models(ledger, "state_support_contract", "state_support_contract")
        if len(contracts) != 1 or len(observations) != contracts[0].task_count:
            raise ValueError("State-support observations have incomplete task coverage")
        conditions = {item.task_id: item for item in contracts[0].confirmed_task_conditions}
        if set(conditions) != {item.task_id for item in observations}:
            raise ValueError("State-support observations cross confirmed tasks")
        return
    if stage == "state_support_freeze":
        freezes = current["state_support_freeze"]
        contracts = _stage_models(ledger, "state_support_contract", "state_support_contract")
        observations = _stage_models(
            ledger,
            "state_support_observation",
            "task_state_support_observation",
        )
        if (
            len(freezes) != 1
            or len(contracts) != 1
            or freezes[0].contract != contracts[0]
            or tuple(freezes[0].observations) != observations
        ):
            raise ValueError("State-support freeze does not replay its contract and observations")


def _validate_compilation_bundle(
    *,
    population: V26FreshTaskPopulation,
    models: Mapping[str, tuple[Any, ...]],
) -> None:
    compiled = models["compiled_proof_artifacts"]
    spaces = models["trajectory_state_space"]
    if len(compiled) != population.task_count or len(spaces) != population.task_count:
        raise ValueError("Joint Compilation does not cover the complete task population")
    validate_population_compilation(population, compiled)
    joint_ids = {item.joint_compilation.artifact_id for item in compiled}
    if joint_ids != {item.joint_compilation_id for item in spaces}:
        raise ValueError("Joint Compilation and state-space roots differ")


def _validate_complete_compilation_bundle(
    population: V26FreshTaskPopulation,
    models: Mapping[str, tuple[Any, ...]],
) -> None:
    _validate_compilation_bundle(population=population, models=models)
    compiled = models["compiled_proof_artifacts"]
    _validate_joint_audits(compiled, models["joint_audit_evidence"])
    _validate_joint_admissions(
        compiled,
        models["joint_audit_evidence"],
        models["joint_admission"],
    )
    _validate_scaffold_ladders(
        models["joint_admission"],
        models["scaffold_ladder"],
        population,
    )
    _validate_scaffold_audits(models["scaffold_ladder"], models["scaffold_gate_evidence"])
    _validate_scaffold_admissions(
        models["scaffold_ladder"],
        models["scaffold_gate_evidence"],
        models["scaffold_admission"],
    )


def _validate_joint_audits(compiled: tuple[Any, ...], audits: tuple[Any, ...]) -> None:
    joint_ids = {item.joint_compilation.artifact_id for item in compiled}
    observed = {(item.joint_compilation_id, item.audit_kind) for item in audits}
    expected = {
        (joint_id, audit_kind)
        for joint_id in joint_ids
        for audit_kind in ("public_sufficiency", "executable_closure", "destructive_mutation")
    }
    if observed != expected or len(audits) != len(expected):
        raise ValueError("Joint Audit coverage is incomplete or duplicated")


def _validate_joint_admissions(
    compiled: tuple[Any, ...],
    audits: tuple[Any, ...],
    admissions: tuple[Any, ...],
) -> None:
    compiled_by_id = {
        item.joint_compilation.artifact_id: item for item in compiled
    }
    audit_ids = {item.evidence_id for item in audits}
    if set(compiled_by_id) != {item.joint_compilation_id for item in admissions}:
        raise ValueError("Joint Admission coverage differs from Joint Compilation")
    for admission in admissions:
        if admission.compiled_artifacts != compiled_by_id[admission.joint_compilation_id]:
            raise ValueError("Joint Admission embeds detached compiled artifacts")
        embedded = {
            admission.public_sufficiency_evidence.evidence_id,
            admission.executable_closure_evidence.evidence_id,
            admission.destructive_mutation_evidence.evidence_id,
        }
        if not embedded <= audit_ids:
            raise ValueError("Joint Admission embeds unaudited Evidence")


def _validate_scaffold_ladders(
    admissions: tuple[Any, ...],
    ladders: tuple[Any, ...],
    population: V26FreshTaskPopulation,
) -> None:
    admission_ids = {item.admission_id for item in admissions}
    if admission_ids != {item.joint_admission.admission_id for item in ladders}:
        raise ValueError("Scaffold Ladder coverage differs from Joint Admission")
    roots = {item.task_id: item for item in population.tasks}
    for ladder in ladders:
        task_id = ladder.projections[0].base_runtime_projection.task_id
        root = roots.get(task_id)
        if (
            root is None
            or ladder.dependency_graph.target_capability_id != root.target_capability_id
        ):
            raise ValueError("Scaffold Ladder target capability differs from the Population")


def _validate_scaffold_audits(ladders: tuple[Any, ...], audits: tuple[Any, ...]) -> None:
    ladder_ids = {item.ladder_id for item in ladders}
    expected_count = len(ladder_ids) * 28
    observed = {(item.ladder_id, item.scaffold_level, item.gate) for item in audits}
    if (
        len(audits) != expected_count
        or len(observed) != expected_count
        or {item.ladder_id for item in audits} != ladder_ids
    ):
        raise ValueError("Scaffold Audit coverage is incomplete or duplicated")


def _validate_scaffold_admissions(
    ladders: tuple[Any, ...],
    audits: tuple[Any, ...],
    admissions: tuple[Any, ...],
) -> None:
    ladders_by_id = {item.ladder_id: item for item in ladders}
    audit_ids = {item.evidence_id for item in audits}
    if set(ladders_by_id) != {item.ladder_id for item in admissions}:
        raise ValueError("Scaffold Admission coverage differs from compiled ladders")
    for admission in admissions:
        if admission.ladder != ladders_by_id[admission.ladder_id]:
            raise ValueError("Scaffold Admission embeds a detached ladder")
        if not {item.evidence_id for item in admission.gate_evidence} <= audit_ids:
            raise ValueError("Scaffold Admission embeds unaudited gate Evidence")


def _validate_bridge_rollouts(
    admissions: tuple[Any, ...],
    rollouts: tuple[Any, ...],
    *,
    population: V26FreshTaskPopulation,
    phase: str,
    expected_levels_per_task: int,
    phase_authorization_id: str,
    bridge_contract: CompilerAssistedBridgeContract,
) -> None:
    admissions_by_id = {item.admission_id: item for item in admissions}
    roots_by_task = {item.task_id: item for item in population.tasks}
    task_ids = {
        item.ladder.projections[0].base_runtime_projection.task_id for item in admissions
    }
    if {item.task_id for item in rollouts} != task_ids:
        raise ValueError("Bridge rollouts do not cover the admitted task population")
    if len(rollouts) != len(task_ids) * expected_levels_per_task * 6:
        raise ValueError("Bridge rollout budget differs from the frozen cell design")
    provider_call_ids = [
        call_id for rollout in rollouts for call_id in rollout.provider_call_ids
    ]
    if len(provider_call_ids) != len(set(provider_call_ids)):
        raise ValueError("Bridge provider-call identities are duplicated across rollouts")
    cells: dict[tuple[str, str], set[int]] = {}
    for rollout in rollouts:
        if (
            rollout.phase != phase
            or rollout.mechanism_id != roots_by_task[rollout.task_id].mechanism_id
            or rollout.phase_authorization_id != phase_authorization_id
            or rollout.contract_id != bridge_contract.contract_id
            or rollout.execution_manifest.model_id != bridge_contract.explorer_model
            or rollout.execution_manifest.runtime_id != bridge_contract.runtime_id
        ):
            raise ValueError("Bridge rollout phase is inconsistent with its router stage")
        admission = admissions_by_id.get(rollout.condition_lineage.scaffold_admission_id)
        if admission is None:
            raise ValueError("Bridge rollout uses an unadmitted task condition")
        projection = next(
            item
            for item in admission.ladder.projections
            if item.scaffold_level == rollout.scaffold_level
        )
        lineage = rollout.condition_lineage
        if (
            lineage.compiled_task_condition_id != projection.compiled_task_condition_id
            or lineage.projection_id != projection.projection_id
            or lineage.ladder_id != admission.ladder_id
            or lineage.joint_admission_id != admission.joint_admission_id
            or tuple(rollout.execution_manifest.tool_manifest["allowed_tools"])
            != projection.base_runtime_projection.allowed_tools
        ):
            raise ValueError("Bridge rollout condition lineage is detached")
        cells.setdefault((rollout.task_id, rollout.scaffold_level), set()).add(
            rollout.replicate_index
        )
    if len(cells) != len(task_ids) * expected_levels_per_task or any(
        indices != set(range(6)) for indices in cells.values()
    ):
        raise ValueError("Bridge rollout replicate coverage is incomplete")


def _validate_bridge_authorization(
    authorizations: tuple[Any, ...],
    admissions: tuple[Any, ...],
    *,
    population: V26FreshTaskPopulation,
    bridge_contract: CompilerAssistedBridgeContract,
    confirmation: bool,
) -> None:
    if len(authorizations) != 1 or authorizations[0].status != "authorized":
        raise ValueError("Bridge rollout requires one passing static authorization")
    authorization = authorizations[0]
    if authorization.contract_id != bridge_contract.contract_id:
        raise ValueError("Bridge authorization differs from the frozen protocol contract")
    expected_tasks = {
        item.ladder.projections[0].base_runtime_projection.task_id for item in admissions
    }
    observed_tasks = set(
        authorization.confirmation_task_ids
        if confirmation
        else authorization.development_task_ids
    )
    expected_by_mechanism = {
        mechanism: {item.task_id for item in tasks}
        for mechanism, tasks in population.tasks_by_mechanism.items()
    }
    if any(
        set(audit.task_admission_ids) != expected_by_mechanism[audit.mechanism_id]
        for audit in authorization.static_audits
    ):
        raise ValueError("Bridge static authorization crosses Population mechanisms")
    audited_admission_ids = {
        admission_id
        for audit in authorization.static_audits
        for admission_id in audit.task_admission_ids.values()
    }
    if observed_tasks != expected_tasks or audited_admission_ids != {
        item.admission_id for item in admissions
    }:
        raise ValueError("Bridge static authorization crosses task admissions")


def _validate_bridge_cells(
    rollouts: tuple[Any, ...],
    cells: tuple[Any, ...],
    *,
    phase: str,
) -> None:
    expected_ids = {item.rollout_id for item in rollouts}
    observed = [item.rollout_id for cell in cells for item in cell.rollout_observations]
    if (
        any(item.phase != phase for item in cells)
        or len(observed) != len(set(observed))
        or set(observed) != expected_ids
    ):
        raise ValueError("Bridge aggregation does not exactly partition atomic rollouts")


def _protocol_bridge_contract(
    ledger: V26StageLedger,
) -> CompilerAssistedBridgeContract:
    protocol = _replay_reference(ledger.protocol_reference)
    if not isinstance(protocol, CapabilityHeterogeneousMainlineProtocol):
        raise ValueError("v26 ledger protocol did not replay")
    return protocol.capability_bridge


def _bridge_provider_call_count(
    references: Sequence[V26StageArtifactReference],
) -> int:
    models = _models_by_role(references).get("bridge_rollout", ())
    return sum(len(item.provider_call_ids) for item in models)


def _models_by_role(
    references: Sequence[V26StageArtifactReference],
) -> dict[str, tuple[Any, ...]]:
    result: dict[str, tuple[Any, ...]] = {}
    for reference in references:
        parsed = _replay_reference(reference)
        result[reference.role] = parsed if isinstance(parsed, tuple) else (parsed,)
    return result


def _stage_models(
    ledger: V26StageLedger,
    stage: V26Stage,
    role: StageArtifactRole,
) -> tuple[Any, ...]:
    references = tuple(
        item for item in ledger.artifacts_by_stage[stage] if item.role == role
    )
    if len(references) != 1:
        raise ValueError("v26 stage ledger has an invalid role cardinality")
    parsed = _replay_reference(references[0])
    return parsed if isinstance(parsed, tuple) else (parsed,)


def _stage_population(
    ledger: V26StageLedger,
    stage: V26Stage,
) -> V26FreshTaskPopulation:
    models = _stage_models(ledger, stage, "fresh_task_population")
    if len(models) != 1 or not isinstance(models[0], V26FreshTaskPopulation):
        raise ValueError("v26 stage lacks exactly one typed fresh Population")
    return models[0]


def _validate_preflight_manifest(
    protocol: CapabilityHeterogeneousMainlineProtocol,
    preflight: MainlinePreflightReport,
) -> None:
    expected_sources = {
        "prior_decision": protocol.prior_evidence[0].sha256,
        "archive_config": protocol.archive_config_sha256,
        "explorer_config": protocol.explorer_config_sha256,
        "student_config": protocol.student_config_sha256,
    }
    expected_code = {
        name: _sha256(path)
        for name, path in sorted(mainline_implementation_paths().items())
    }
    if preflight.source_sha256 != expected_sources:
        raise ValueError("v26 preflight source manifest differs from the protocol")
    if preflight.code_sha256 != expected_code:
        raise ValueError("v26 preflight implementation manifest is stale or incomplete")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_artifact_argument(value: str) -> tuple[StageArtifactRole, Path]:
    role, separator, path = value.partition("=")
    if not separator:
        raise argparse.ArgumentTypeError("artifact must use ROLE=PATH")
    if role not in _CLI_STAGE_ARTIFACT_ROLES:
        raise argparse.ArgumentTypeError(f"unsupported stage artifact role: {role}")
    return cast(StageArtifactRole, role), Path(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Advance the fail-closed Finance v26 stages")
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init")
    initialize.add_argument("--run-id", required=True)
    initialize.add_argument("--protocol", type=Path, required=True)
    initialize.add_argument("--preflight", type=Path, required=True)
    initialize.add_argument("--output", type=Path, required=True)
    advance = commands.add_parser("advance")
    advance.add_argument("--ledger", type=Path, required=True)
    advance.add_argument("--stage", choices=V26_STAGES, required=True)
    advance.add_argument("--artifact", action="append", required=True)
    advance.add_argument("--model-api-calls", type=int, default=0)
    advance.add_argument("--gpu-jobs", type=int, default=0)
    advance.add_argument("--output", type=Path, required=True)
    status = commands.add_parser("status")
    status.add_argument("--ledger", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "init":
        ledger = initialize_v26_stage_ledger(
            run_id=args.run_id,
            protocol_path=args.protocol,
            preflight_path=args.preflight,
        )
        write_v26_stage_ledger(ledger, args.output)
    elif args.command == "advance":
        ledger = load_v26_stage_ledger(args.ledger)
        references = tuple(
            make_v26_stage_artifact_reference(*_parse_artifact_argument(item))
            for item in args.artifact
        )
        ledger = advance_v26_stage(
            ledger,
            stage=args.stage,
            artifacts=references,
            model_api_calls=args.model_api_calls,
            gpu_jobs=args.gpu_jobs,
        )
        write_v26_stage_ledger(ledger, args.output)
    else:
        ledger = load_v26_stage_ledger(args.ledger)
    print(json.dumps(ledger.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
