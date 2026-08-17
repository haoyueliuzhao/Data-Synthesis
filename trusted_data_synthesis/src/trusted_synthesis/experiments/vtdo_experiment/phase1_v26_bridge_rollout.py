from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.scaffolding import (
    CapabilityAwarePublicProjection,
    CompiledPublicStateSummary,
    PublicSummaryField,
    compile_public_state_summary,
    make_public_state_observation,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    MECHANISM_ESTIMANDS,
    BridgeEstimandOutcome,
    BridgeMechanism,
    EstimandId,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    FRESHNESS_CHANNELS,
    FreshnessChannel,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import (
    AgentStopRejection,
    PublicAgentScaffoldCompiler,
)
from trusted_synthesis.runtime.tools import AgentToolObservation

V26_BRIDGE_ROLLOUT_CONTRACT_VERSION = "finance_v26_bridge_rollout_contract.v1"
V26_BRIDGE_SCAFFOLD_COMPILER_VERSION = "finance_v26_live_scaffold_compiler.v1"
V26_BRIDGE_SCAFFOLD_SNAPSHOT_VERSION = "finance_v26_scaffold_snapshot.v1"
V26_BRIDGE_HISTORICAL_RECORD_MANIFEST_VERSION = "finance_v26_historical_api_record_manifest.v1"
V26_BRIDGE_HISTORICAL_EXPOSURE_AUDIT_VERSION = "finance_v26_historical_api_exposure_audit.v2"
V26_BRIDGE_HISTORICAL_POOL_EXPOSURE_AUDIT_VERSION = (
    "finance_v26_historical_evidence_pool_exposure_audit.v1"
)
V26_BRIDGE_RAW_INTEGRITY_AUDIT_VERSION = "finance_v26_bridge_raw_integrity_audit.v1"
V26_BRIDGE_ESTIMAND_EVALUATOR_VERSION = "finance_v26_bridge_estimand_evaluator.v1"
V26_BRIDGE_FIXED_POLICY_VERSION = "finance_v26_bridge_fixed_policy.v1"

HISTORICAL_EXPOSURE_CHANNELS = (*FRESHNESS_CHANNELS, "instruction_hash")
HISTORICAL_PROVIDER_MARKERS = (
    "deepseek",
    "provider_telemetry",
    "model_request_prompts",
    "api_call_count",
)
HISTORICAL_PROVIDER_DISCOVERY_VERSION = "finance_v26_rg_provider_discovery.v1"
_FORBIDDEN_SCAFFOLD_MARKERS = (
    "correct_action",
    "correct_argument",
    "gold_answer",
    "gold_evidence",
    "hidden_program",
    "host_event",
    "mechanism_activation",
    "internal_completion",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BridgeScaffoldSnapshot(FrozenModel):
    snapshot_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    request_index: int = Field(ge=0)
    summary: CompiledPublicStateSummary
    model_visible_payload: dict[str, Any]
    model_visible_payload_hash: str = Field(min_length=1)
    schema_version: str = V26_BRIDGE_SCAFFOLD_SNAPSHOT_VERSION

    @model_validator(mode="after")
    def validate_snapshot(self) -> BridgeScaffoldSnapshot:
        if self.summary.task_id != self.task_id:
            raise ValueError("Bridge scaffold snapshot crosses task identities")
        expected_hash = canonical_hash(
            self.model_visible_payload,
            prefix="finance_v26_scaffold_model_visible_payload:",
        )
        if self.model_visible_payload_hash != expected_hash:
            raise ValueError("Bridge scaffold model-visible payload hash is invalid")
        _assert_scaffold_payload_public(self.model_visible_payload)
        if self.snapshot_id != bridge_scaffold_snapshot_id(self):
            raise ValueError("Bridge scaffold snapshot identity is invalid")
        return self


class HistoricalExposureChannel(FrozenModel):
    channel: str = Field(min_length=1)
    current_value_count: int = Field(ge=0)
    matching_file_count: int = Field(ge=0)
    overlap_count: int = Field(ge=0)
    overlap_hash: str = Field(min_length=1)
    matching_files_hash: str = Field(min_length=1)


class HistoricalApiRecordManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    artifact_root: str = Field(min_length=1)
    discovery_version: str = HISTORICAL_PROVIDER_DISCOVERY_VERSION
    discovery_markers: tuple[str, ...] = HISTORICAL_PROVIDER_MARKERS
    rg_version: str = Field(min_length=1)
    record_files: tuple[str, ...] = Field(min_length=1)
    record_file_sha256: dict[str, str]
    total_record_bytes: int = Field(ge=1)
    schema_version: str = V26_BRIDGE_HISTORICAL_RECORD_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> HistoricalApiRecordManifest:
        if self.discovery_markers != HISTORICAL_PROVIDER_MARKERS:
            raise ValueError("historical Provider discovery markers changed")
        if tuple(sorted(set(self.record_files))) != self.record_files:
            raise ValueError("historical Provider record files are not canonical")
        if set(self.record_files) != set(self.record_file_sha256):
            raise ValueError("historical Provider file hash manifest is incomplete")
        if self.manifest_id != historical_api_record_manifest_id(self):
            raise ValueError("historical Provider record manifest identity is invalid")
        return self


class HistoricalApiExposureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    current_population_id: str = Field(min_length=1)
    record_manifest: HistoricalApiRecordManifest
    current_identity_set_hash: str = Field(min_length=1)
    channels: tuple[HistoricalExposureChannel, ...] = Field(min_length=1)
    exposed_task_ids: tuple[str, ...]
    exposed_evidence_ids: tuple[str, ...]
    exposed_source_record_ids: tuple[str, ...]
    exposed_instruction_hashes: tuple[str, ...]
    status: Literal["passed", "blocked"]
    blockers: tuple[str, ...]
    schema_version: str = V26_BRIDGE_HISTORICAL_EXPOSURE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> HistoricalApiExposureAudit:
        if self.status != ("blocked" if self.blockers else "passed"):
            raise ValueError("historical API exposure status differs from its blockers")
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("historical API exposure blockers are duplicated")
        if tuple(item.channel for item in self.channels) != HISTORICAL_EXPOSURE_CHANNELS:
            raise ValueError("historical API exposure channels are incomplete or reordered")
        if self.audit_id != historical_api_exposure_audit_id(self):
            raise ValueError("historical API exposure audit identity is invalid")
        return self


class HistoricalEvidencePoolExposureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    source_evidence_ids: tuple[str, ...] = Field(min_length=1)
    source_evidence_set_hash: str = Field(min_length=1)
    source_evidence_count: int = Field(ge=1)
    record_manifest: HistoricalApiRecordManifest
    exposed_evidence_ids: tuple[str, ...]
    exposed_evidence_set_hash: str = Field(min_length=1)
    exposed_evidence_count: int = Field(ge=0)
    unexposed_evidence_count: int = Field(ge=0)
    status: Literal["observed"] = "observed"
    schema_version: Literal["finance_v26_historical_evidence_pool_exposure_audit.v1"] = (
        "finance_v26_historical_evidence_pool_exposure_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> HistoricalEvidencePoolExposureAudit:
        if self.source_evidence_ids != tuple(sorted(set(self.source_evidence_ids))):
            raise ValueError("source Evidence identities are not canonical")
        if self.exposed_evidence_ids != tuple(sorted(set(self.exposed_evidence_ids))):
            raise ValueError("exposed Evidence identities are not canonical")
        if not set(self.exposed_evidence_ids) <= set(self.source_evidence_ids):
            raise ValueError("historical exposure contains Evidence outside the source pool")
        if self.source_evidence_count != len(self.source_evidence_ids):
            raise ValueError("source Evidence count is inconsistent")
        if self.exposed_evidence_count != len(self.exposed_evidence_ids):
            raise ValueError("exposed Evidence count is inconsistent")
        if self.unexposed_evidence_count != (
            self.source_evidence_count - self.exposed_evidence_count
        ):
            raise ValueError("unexposed Evidence count is inconsistent")
        if self.source_evidence_set_hash != canonical_hash(
            self.source_evidence_ids,
            prefix="finance_v26_historical_source_evidence_set:",
        ):
            raise ValueError("source Evidence set hash is invalid")
        if self.exposed_evidence_set_hash != canonical_hash(
            self.exposed_evidence_ids,
            prefix="finance_v26_historical_exposed_evidence_set:",
        ):
            raise ValueError("exposed Evidence set hash is invalid")
        if self.audit_id != historical_evidence_pool_exposure_audit_id(self):
            raise ValueError("historical Evidence-pool exposure audit identity is invalid")
        return self


class BridgeRawIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    raw_artifact_count: int = Field(ge=0)
    expected_raw_artifact_count: int = Field(ge=0)
    byte_hash_pass_count: int = Field(ge=0)
    identity_pass_count: int = Field(ge=0)
    prompt_hash_pass_count: int = Field(ge=0)
    scaffold_hash_pass_count: int = Field(ge=0)
    side_channel_hash_pass_count: int = Field(ge=0)
    noninterference_pass_count: int = Field(ge=0)
    provider_call_id_unique: bool
    duplicate_provider_call_ids: tuple[str, ...]
    failed_artifacts: tuple[str, ...]
    status: Literal["passed", "partial", "failed"]
    schema_version: str = V26_BRIDGE_RAW_INTEGRITY_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> BridgeRawIntegrityAudit:
        complete = self.raw_artifact_count == self.expected_raw_artifact_count
        all_pass = (
            self.byte_hash_pass_count
            == self.identity_pass_count
            == self.prompt_hash_pass_count
            == self.scaffold_hash_pass_count
            == self.side_channel_hash_pass_count
            == self.noninterference_pass_count
            == self.raw_artifact_count
        )
        expected_status = (
            "passed"
            if complete and all_pass and self.provider_call_id_unique and not self.failed_artifacts
            else "partial"
            if all_pass and self.provider_call_id_unique and not self.failed_artifacts
            else "failed"
        )
        if self.status != expected_status:
            raise ValueError("Bridge raw integrity status is inconsistent")
        if self.audit_id != bridge_raw_integrity_audit_id(self):
            raise ValueError("Bridge raw integrity audit identity is invalid")
        return self


class LivePublicScaffoldCompiler(PublicAgentScaffoldCompiler):
    """Compile one admitted scaffold from public runtime state only.

    The object is intentionally rollout-local. Its snapshots are an audit side channel and
    never participate in quotient-state identity.
    """

    def __init__(self, projection: CapabilityAwarePublicProjection) -> None:
        if projection.scaffold_level == "gamma_0" or projection.public_summary_spec is None:
            raise ValueError("gamma_0 must run without a public scaffold compiler")
        self._projection = projection
        self._snapshots: list[BridgeScaffoldSnapshot] = []
        self._manifest_hash = canonical_hash(
            {
                "compiler_version": V26_BRIDGE_SCAFFOLD_COMPILER_VERSION,
                "projection_id": projection.projection_id,
                "compiled_task_condition_id": projection.compiled_task_condition_id,
                "scaffold_payload_hash": projection.scaffold_payload_hash,
                "summary_spec_id": projection.public_summary_spec.summary_spec_id,
            },
            prefix="finance_v26_live_scaffold_compiler_manifest:",
        )

    @property
    def manifest_hash(self) -> str:
        return self._manifest_hash

    @property
    def snapshots(self) -> tuple[BridgeScaffoldSnapshot, ...]:
        return tuple(self._snapshots)

    @property
    def final_summary(self) -> CompiledPublicStateSummary:
        if not self._snapshots:
            raise ValueError("live scaffold compiler produced no summary")
        return self._snapshots[-1].summary

    def compile_public_context(
        self,
        *,
        task: TaskPublicSpec,
        tool_environment: Mapping[str, Any],
        observations: tuple[AgentToolObservation, ...],
        stop_rejections: tuple[AgentStopRejection, ...],
    ) -> Mapping[str, Any]:
        projection = self._projection
        summary_spec = projection.public_summary_spec
        if summary_spec is None or task.task_id != projection.base_runtime_projection.task_id:
            raise ValueError("live scaffold compiler received another task or projection")
        public_observations = _public_state_observations(
            task=task,
            tool_environment=tool_environment,
            observations=observations,
            stop_rejections=stop_rejections,
            included_fields=set(summary_spec.included_fields),
        )
        summary = compile_public_state_summary(summary_spec, public_observations)
        payload: dict[str, Any] = {
            "public_state_summary": summary.values,
        }
        if projection.scaffold_rank >= 2:
            payload["public_capability_contract"] = [
                item.model_dump(mode="json") for item in projection.public_capability_nodes
            ]
        if projection.scaffold_rank >= 3:
            payload["public_subgoal_dependencies"] = [
                {"prerequisite": left, "dependent": right}
                for left, right in projection.public_dependency_edges
            ]
        _assert_scaffold_payload_public(payload)
        values = {
            "task_id": task.task_id,
            "request_index": len(self._snapshots),
            "summary": summary,
            "model_visible_payload": payload,
            "model_visible_payload_hash": canonical_hash(
                payload,
                prefix="finance_v26_scaffold_model_visible_payload:",
            ),
            "schema_version": V26_BRIDGE_SCAFFOLD_SNAPSHOT_VERSION,
        }
        provisional = BridgeScaffoldSnapshot.model_construct(snapshot_id="pending", **values)
        snapshot = BridgeScaffoldSnapshot(
            snapshot_id=bridge_scaffold_snapshot_id(provisional),
            **values,
        )
        self._snapshots.append(snapshot)
        return payload


def bridge_scaffold_snapshot_id(value: BridgeScaffoldSnapshot) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"snapshot_id"}),
        prefix="finance_v26_scaffold_snapshot:",
    )


def historical_api_exposure_audit_id(value: HistoricalApiExposureAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_historical_api_exposure_audit:",
    )


def historical_api_record_manifest_id(value: HistoricalApiRecordManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_v26_historical_api_record_manifest:",
    )


def historical_evidence_pool_exposure_audit_id(
    value: HistoricalEvidencePoolExposureAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_historical_evidence_pool_exposure_audit:",
    )


def bridge_raw_integrity_audit_id(value: BridgeRawIntegrityAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_bridge_raw_integrity_audit:",
    )


def build_historical_api_record_manifest(
    *,
    artifact_root: Path,
    output_path: Path | None = None,
) -> HistoricalApiRecordManifest:
    root = artifact_root.resolve()
    marker_expression = "|".join(re.escape(item) for item in HISTORICAL_PROVIDER_MARKERS)
    command = (
        "rg",
        "-l",
        "--no-messages",
        "-i",
        marker_expression,
        str(root),
        "-g",
        "*.jsonl",
        "-g",
        "!**/*checkpoint*",
    )
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode not in {0, 1}:
        raise ValueError(f"historical Provider discovery failed: {completed.stderr[:500]}")
    files = tuple(
        sorted(
            str(path.resolve())
            for raw in completed.stdout.splitlines()
            if raw.strip()
            for path in (Path(raw.strip()),)
            if path.is_file()
        )
    )
    if not files:
        raise ValueError("historical Provider discovery found no API-bearing records")
    rg_version_result = subprocess.run(
        ("rg", "--version"), check=True, capture_output=True, text=True
    )
    rg_version = rg_version_result.stdout.splitlines()[0].strip()
    hashes = {path: _sha256_file(Path(path)) for path in files}
    values: dict[str, Any] = {
        "artifact_root": str(root),
        "rg_version": rg_version,
        "record_files": files,
        "record_file_sha256": hashes,
        "total_record_bytes": sum(Path(path).stat().st_size for path in files),
        "schema_version": V26_BRIDGE_HISTORICAL_RECORD_MANIFEST_VERSION,
    }
    provisional = HistoricalApiRecordManifest.model_construct(manifest_id="pending", **values)
    manifest = HistoricalApiRecordManifest(
        manifest_id=historical_api_record_manifest_id(provisional), **values
    )
    if output_path is not None:
        _write_json_atomic(output_path, manifest.model_dump(mode="json"))
    return manifest


def replay_historical_api_record_manifest(
    manifest: HistoricalApiRecordManifest,
) -> None:
    for raw_path in manifest.record_files:
        path = Path(raw_path)
        if not path.is_file() or _sha256_file(path) != manifest.record_file_sha256[raw_path]:
            raise ValueError("historical Provider record manifest replay failed")


def audit_historical_api_exposure(
    *,
    current_population_id: str,
    current_identity_channels: Mapping[FreshnessChannel, Iterable[str]],
    current_instructions: Sequence[str],
    record_manifest: HistoricalApiRecordManifest,
    output_path: Path | None = None,
) -> HistoricalApiExposureAudit:
    if set(current_identity_channels) != set(FRESHNESS_CHANNELS):
        raise ValueError("historical exposure input lacks frozen freshness channels")
    replay_historical_api_record_manifest(record_manifest)
    current: dict[str, set[str]] = {
        key: {str(item) for item in current_identity_channels[key] if str(item)}
        for key in FRESHNESS_CHANNELS
    }
    instruction_by_token = {
        _json_string_body(instruction): hashlib.sha256(
            _normalize_text(instruction).encode("utf-8")
        ).hexdigest()
        for instruction in current_instructions
        if instruction.strip()
    }
    current["instruction_hash"] = set(instruction_by_token.values())
    token_channels: dict[str, tuple[str, str]] = {
        value: (channel, value)
        for channel, values in current.items()
        if channel != "instruction_hash"
        for value in values
    }
    token_channels.update(
        {token: ("instruction_hash", digest) for token, digest in instruction_by_token.items()}
    )
    overlaps: dict[str, set[str]] = {channel: set() for channel in HISTORICAL_EXPOSURE_CHANNELS}
    matching_files: dict[str, set[str]] = {
        channel: set() for channel in HISTORICAL_EXPOSURE_CHANNELS
    }
    token_matches = _scan_manifest_exact_tokens(record_manifest, token_channels)
    for token, raw_paths in token_matches.items():
        channel, value = token_channels[token]
        overlaps[channel].add(value)
        matching_files[channel].update(raw_paths)
    channels = tuple(
        HistoricalExposureChannel(
            channel=key,
            current_value_count=len(current[key]),
            matching_file_count=len(matching_files[key]),
            overlap_count=len(overlaps[key]),
            overlap_hash=canonical_hash(
                sorted(overlaps[key]),
                prefix=f"finance_v26_historical_overlap_{key}:",
            ),
            matching_files_hash=canonical_hash(
                sorted(matching_files[key]),
                prefix=f"finance_v26_historical_matching_files_{key}:",
            ),
        )
        for key in HISTORICAL_EXPOSURE_CHANNELS
    )
    blockers = tuple(
        f"historical_api_overlap:{item.channel}:{item.overlap_count}"
        for item in channels
        if item.overlap_count
    )
    audit_values: dict[str, Any] = {
        "current_population_id": current_population_id,
        "record_manifest": record_manifest,
        "current_identity_set_hash": canonical_hash(
            {key: sorted(values) for key, values in current.items()},
            prefix="finance_v26_historical_current_identity_set:",
        ),
        "channels": channels,
        "exposed_task_ids": tuple(sorted(overlaps["task_id"])),
        "exposed_evidence_ids": tuple(sorted(overlaps["evidence_id"])),
        "exposed_source_record_ids": tuple(sorted(overlaps["source_record_id"])),
        "exposed_instruction_hashes": tuple(sorted(overlaps["instruction_hash"])),
        "status": "blocked" if blockers else "passed",
        "blockers": blockers,
        "schema_version": V26_BRIDGE_HISTORICAL_EXPOSURE_AUDIT_VERSION,
    }
    provisional = HistoricalApiExposureAudit.model_construct(audit_id="pending", **audit_values)
    audit = HistoricalApiExposureAudit(
        audit_id=historical_api_exposure_audit_id(provisional),
        **audit_values,
    )
    if output_path is not None:
        _write_json_atomic(output_path, audit.model_dump(mode="json"))
    return audit


def audit_historical_evidence_pool_exposure(
    *,
    source_artifacts_path: Path,
    source_evidence_ids: Sequence[str],
    record_manifest: HistoricalApiRecordManifest,
    output_path: Path | None = None,
) -> HistoricalEvidencePoolExposureAudit:
    replay_historical_api_record_manifest(record_manifest)
    source_path = source_artifacts_path.resolve()
    canonical_ids = tuple(sorted(set(source_evidence_ids)))
    if not canonical_ids:
        raise ValueError("historical exposure audit received an empty source Evidence pool")
    matches = _scan_manifest_exact_tokens(
        record_manifest,
        {value: ("evidence_id", value) for value in canonical_ids},
    )
    exposed = tuple(sorted(matches))
    values: dict[str, Any] = {
        "source_artifacts_path": str(source_path),
        "source_artifacts_sha256": _sha256_file(source_path),
        "source_evidence_ids": canonical_ids,
        "source_evidence_set_hash": canonical_hash(
            canonical_ids,
            prefix="finance_v26_historical_source_evidence_set:",
        ),
        "source_evidence_count": len(canonical_ids),
        "record_manifest": record_manifest,
        "exposed_evidence_ids": exposed,
        "exposed_evidence_set_hash": canonical_hash(
            exposed,
            prefix="finance_v26_historical_exposed_evidence_set:",
        ),
        "exposed_evidence_count": len(exposed),
        "unexposed_evidence_count": len(canonical_ids) - len(exposed),
        "status": "observed",
        "schema_version": V26_BRIDGE_HISTORICAL_POOL_EXPOSURE_AUDIT_VERSION,
    }
    provisional = HistoricalEvidencePoolExposureAudit.model_construct(audit_id="pending", **values)
    audit = HistoricalEvidencePoolExposureAudit(
        audit_id=historical_evidence_pool_exposure_audit_id(provisional),
        **values,
    )
    if output_path is not None:
        _write_json_atomic(output_path, audit.model_dump(mode="json"))
    return audit


def evaluate_bridge_estimands(
    *,
    mechanism_id: BridgeMechanism,
    source_task: CapabilitySensitiveTaskArtifact,
    observations: Sequence[AgentToolObservation],
    trajectory_steps: Sequence[Mapping[str, Any]],
    independent_validity_passed: bool,
    stopped_by_model: bool,
    stop_rejection_count: int,
) -> tuple[BridgeEstimandOutcome, ...]:
    successful_tools = tuple(
        item.call.tool_id for item in observations if item.status == "succeeded"
    )
    failed_indices = tuple(
        index for index, item in enumerate(observations) if item.status == "failed"
    )
    successful_indices = tuple(
        index for index, item in enumerate(observations) if item.status == "succeeded"
    )
    operators = tuple(
        str(item.get("operator_id"))
        for item in trajectory_steps
        if item.get("operator_id") is not None
    )
    expected_first_tool = _expected_first_tool(source_task)
    context_alignment = bool(successful_tools and successful_tools[0] == expected_first_tool)
    required_branch_count = max(1, source_task.structure.operation_branch_count)
    branch_flip = independent_validity_passed and len(set(operators)) >= required_branch_count
    semantic_reconciliation = (
        independent_validity_passed
        and "normalize_metric_unit_period" in successful_tools
        and bool(source_task.reconciliation_axes)
    )
    failure_recovery = any(
        success_index > failure_index
        for failure_index in failed_indices
        for success_index in successful_indices
    )
    stopping_calibration = (
        independent_validity_passed
        and stopped_by_model
        and bool(successful_tools)
        and (
            stop_rejection_count > 0
            or len(successful_tools) >= source_task.structure.minimal_tool_calls
        )
    )
    outcomes: dict[EstimandId, bool] = {
        "context_action_alignment": context_alignment,
        "counterfactual_branch_flip": branch_flip,
        "semantic_reconciliation": semantic_reconciliation,
        "failure_recovery": failure_recovery,
        "stopping_calibration": stopping_calibration,
    }
    fixed_policy: dict[EstimandId, bool] = {
        "context_action_alignment": _fixed_policy_first_tool(source_task) == expected_first_tool,
        "counterfactual_branch_flip": False,
        "semantic_reconciliation": False,
        "failure_recovery": False,
        "stopping_calibration": False,
    }
    return tuple(
        BridgeEstimandOutcome(
            estimand_id=estimand_id,
            evaluated=True,
            success=outcomes[estimand_id],
            fixed_policy_success=fixed_policy[estimand_id],
        )
        for estimand_id in MECHANISM_ESTIMANDS[mechanism_id]
    )


def unevaluated_bridge_estimands(
    mechanism_id: BridgeMechanism,
) -> tuple[BridgeEstimandOutcome, ...]:
    return tuple(
        BridgeEstimandOutcome(
            estimand_id=estimand_id,
            evaluated=False,
        )
        for estimand_id in MECHANISM_ESTIMANDS[mechanism_id]
    )


def make_provider_call_ids(
    *,
    rollout_identity: Mapping[str, Any],
    telemetry: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    return tuple(
        canonical_hash(
            {
                "rollout_identity": dict(rollout_identity),
                "call_index": index,
                "request_hash": row.get("request_hash"),
                "response_hash": row.get("response_hash"),
                "model_selected": row.get("model_selected"),
                "http_status": row.get("http_status"),
            },
            prefix="finance_v26_bridge_provider_call:",
        )
        for index, row in enumerate(telemetry)
    )


def write_raw_payload_first(path: Path, payload: Mapping[str, Any]) -> str:
    """Write exactly the canonical bytes hashed by BridgeRolloutObservation."""

    serialized = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(serialized).hexdigest()
    if path.exists():
        existing = path.read_bytes()
        if existing != serialized:
            raise ValueError("Bridge raw Artifact identity already exists with different bytes")
        return digest

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(serialized)
    temporary.replace(path)
    return hashlib.sha256(serialized).hexdigest()


def replay_raw_payload(path: Path, expected_sha256: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Bridge raw Artifact byte hash replay failed")
    payload = json.loads(raw)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if raw != canonical:
        raise ValueError("Bridge raw Artifact is not canonically serialized")
    return payload


def _public_state_observations(
    *,
    task: TaskPublicSpec,
    tool_environment: Mapping[str, Any],
    observations: Sequence[AgentToolObservation],
    stop_rejections: Sequence[AgentStopRejection],
    included_fields: set[PublicSummaryField],
) -> tuple[Any, ...]:
    metadata = dict(task.metadata.get("capability_sensitive_frontier") or {})
    stopping_conditions = tuple(str(item) for item in metadata.get("stopping_conditions", ()))
    reconciliation_axes = tuple(str(item) for item in metadata.get("reconciliation_axes", ()))
    requirements = tuple(
        str(item.value if hasattr(item, "value") else item) for item in task.requirements
    )
    tool_rows = tuple(tool_environment.get("tools") or ())
    tool_ids = tuple(str(item.get("tool_id")) for item in tool_rows if isinstance(item, Mapping))
    selected_evidence = tuple(
        sorted({evidence_id for item in observations for evidence_id in item.evidence_ids})
    )
    completed_tools = tuple(
        item.call.tool_id for item in observations if item.status == "succeeded"
    )
    failure_history = tuple(
        str(item.error_code or "public_tool_failure")
        for item in observations
        if item.status == "failed"
    )
    failure_history += tuple(item.reason_code for item in stop_rejections)
    resolved_relations = (
        reconciliation_axes if "normalize_metric_unit_period" in completed_tools else ()
    )
    unmet = set(requirements)
    if selected_evidence:
        unmet.discard("retrieve_evidence")
        unmet.discard("select_evidence")
        unmet.discard("cite_source")
    if "calculator" in completed_tools:
        unmet.discard("calculate")
    if "cross_check_evidence" in completed_tools:
        unmet.discard("verify_result")
    base_values: dict[PublicSummaryField, Any] = {
        "selected_evidence_roles": selected_evidence,
        "completed_operation_types": completed_tools,
        "unmet_public_preconditions": tuple(sorted(unmet)),
        "resolved_relation_types": tuple(sorted(resolved_relations)),
        "unresolved_relation_types": tuple(
            sorted(set(reconciliation_axes) - set(resolved_relations))
        ),
        "available_operation_references": tuple(sorted(tool_ids)),
        "remaining_tool_budget": int(tool_environment.get("remaining_tool_calls", 0)),
        "public_completion_conditions": stopping_conditions,
        "typed_failure_category": failure_history[-1] if failure_history else "none_observed",
        "typed_failure_category_history": failure_history,
        "public_completion_condition_history": (
            {
                "observation_count": len(observations),
                "unmet_precondition_count": len(unmet),
                "stop_rejection_count": len(stop_rejections),
            },
        ),
    }
    values = {key: value for key, value in base_values.items() if key in included_fields}
    return (
        make_public_state_observation(
            task_id=task.task_id,
            sequence_index=0,
            source_kind="task_public",
            values=values,
        ),
    )


def _expected_first_tool(task: CapabilitySensitiveTaskArtifact) -> str:
    first_action = task.query_stages[0].action if task.query_stages else "broad_search"
    return {
        "broad_search": "search_archive",
        "typed_refinement": "query_structured_fact",
        "document_inspection": "open_document",
    }.get(first_action, "search_archive")


def _fixed_policy_first_tool(task: CapabilitySensitiveTaskArtifact) -> str:
    return sorted(task.required_tool_ids)[0]


def _scan_manifest_exact_tokens(
    manifest: HistoricalApiRecordManifest,
    token_channels: Mapping[str, tuple[str, str]],
) -> dict[str, set[str]]:
    tokens = tuple(sorted(token_channels))
    if not tokens or any("\n" in item or "\r" in item for item in tokens):
        raise ValueError("historical API exposure tokens are empty or multiline")
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as handle:
            temporary_name = handle.name
            handle.write("\n".join(tokens) + "\n")
        command = (
            "rg",
            "-F",
            "-o",
            "--with-filename",
            "--line-number",
            "--no-heading",
            "--no-messages",
            "-f",
            temporary_name,
            *manifest.record_files,
        )
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode not in {0, 1}:
            raise ValueError(f"historical exact-token scan failed: {completed.stderr[:500]}")
        matches: dict[str, set[str]] = {}
        for row in completed.stdout.splitlines():
            raw_path, _, token = row.split(":", 2)
            if token not in token_channels:
                raise ValueError("historical exact-token scanner returned an unknown token")
            matches.setdefault(token, set()).add(str(Path(raw_path).resolve()))
        return matches
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def _json_string_body(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _assert_scaffold_payload_public(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    if any(marker in serialized for marker in _FORBIDDEN_SCAFFOLD_MARKERS):
        raise ValueError("live scaffold payload contains a forbidden marker")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)
