from __future__ import annotations

import hashlib
import importlib.metadata
import locale
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.release.diversity_selector import (
    DiversityAwareReleaseSelection,
    PersistedReleaseRecord,
)
from trusted_synthesis.experiments.qa_realization_vnext.release_authority import (
    QAReleaseAuthorityBundle,
)
from trusted_synthesis.hashing import canonical_hash

AUTHORIZED_PREDECESSOR = "2485d44b506814a507b4c45fa3245758bcd16d11"
AUTHORIZED_TRANSITION = (
    "qa_release_authority_external_authorization_exact_population_"
    "source_projection_cross_catalog_envelope_independent_audit_only"
)
PERMITTED_CHANGE_SURFACE = (
    "trusted_data_synthesis/docs/current_project_status.md",
    "trusted_data_synthesis/docs/finance_v26_183_qa_release_authority.md",
    "trusted_data_synthesis/docs/finance_v26_184_qa_release_authority_envelope.md",
    (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_realization_vnext/"
        "release_authority_envelope.py"
    ),
    (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_realization_vnext/"
        "release_authority_envelope_preflight.py"
    ),
    (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_realization_vnext/"
        "source_projected_release_authority_runner.py"
    ),
    "trusted_data_synthesis/tests/test_qa_release_authority_envelope.py",
)
FORBIDDEN_OPERATIONS = (
    "archive_backed_finance_pilot",
    "contribution",
    "production_release",
    "provider_generation",
    "training",
    "v26_181_reinterpretation",
    "vtdo",
)
FROZEN_ATTACK_IDS = (
    "operation_semantic_contract_rehashed",
    "full_source_tree_binding_rehashed",
    "raw_evidence_parent_rehashed",
    "plan_dependency_rehashed",
    "task_tools_rehashed",
    "surface_validation_rehashed",
    "assessment_decision_rehashed",
    "sibling_trajectory_rebound_rehashed",
    "weight_pairing_swapped_rehashed",
    "release_plan_changed_rehashed",
    "quota_policy_changed_hard_gates_true_rehashed",
    "catalog_replaced_manifest_rehashed",
    "report_only_fields_rehashed",
    "report_markdown_mutated",
    "all_catalogs_manifest_report_jointly_rehashed",
    "one_fixture_removed_bundle_rehashed",
    "one_extra_valid_fixture_added",
    "external_audit_omitted_or_replaced",
    "unrelated_archive_paired_with_valid_root",
    "arbitrary_tree_id_paired_with_valid_manifest",
    "registered_attack_silently_omitted",
    "wrong_validator_same_exception_phrase",
    "pilot_evaluator_profile_substituted",
)


def _content_identity(model: BaseModel, *, field: str, prefix: str) -> str:
    return canonical_hash(
        model.model_dump(mode="json", exclude={field}),
        prefix=prefix,
    )


class QAReleaseAuthorityAuthorization(BaseModel):
    """External bytes and exact source change surface authorizing one transition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    authorization_id: str = Field(min_length=1)
    external_audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    external_audit_byte_count: int = Field(ge=1)
    audit_bytes_hash: str = Field(min_length=1)
    authorized_predecessor: str = Field(pattern=r"^[0-9a-f]{40}$")
    authorized_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    permitted_transition: str = Field(min_length=1)
    permitted_change_surface: tuple[str, ...] = Field(min_length=1)
    observed_change_surface: tuple[str, ...] = Field(min_length=1)
    forbidden_operations: tuple[str, ...] = Field(min_length=1)
    schema_version: str = "qa_release_authority_authorization.v1"

    @model_validator(mode="after")
    def validate_authorization(self) -> QAReleaseAuthorityAuthorization:
        if self.authorized_predecessor != AUTHORIZED_PREDECESSOR:
            raise ValueError("authorization predecessor is not the audited frozen release")
        if self.permitted_transition != AUTHORIZED_TRANSITION:
            raise ValueError("authorization transition is not the audited successor")
        if self.permitted_change_surface != PERMITTED_CHANGE_SURFACE:
            raise ValueError("authorization permitted change surface is not exact")
        if self.observed_change_surface != self.permitted_change_surface:
            raise ValueError("implementation change surface differs from authorization")
        if self.forbidden_operations != FORBIDDEN_OPERATIONS:
            raise ValueError("authorization forbidden operations are not exact")
        expected_audit_hash = canonical_hash(
            {
                "byte_count": self.external_audit_byte_count,
                "sha256": self.external_audit_sha256,
                "schema_version": "external_audit_bytes.v1",
            },
            prefix="external_audit_bytes:",
        )
        if self.audit_bytes_hash != expected_audit_hash:
            raise ValueError("authorization audit byte identity is invalid")
        expected = _content_identity(
            self,
            field="authorization_id",
            prefix="qa_release_authority_authorization:",
        )
        if self.authorization_id != expected:
            raise ValueError("QA release authority authorization identity is invalid")
        return self


class SourceSnapshotEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    kind: str = Field(pattern=r"^(file|symlink)$")
    executable: bool
    byte_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_blob_id: str = Field(pattern=r"^[0-9a-f]{40}$")
    schema_version: str = "source_snapshot_entry.v1"


class SourceSnapshotManifest(BaseModel):
    """Every member derived from one Git archive and its extracted tree."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_id: str = Field(min_length=1)
    source_commit_id: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree_id: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_archive_byte_count: int = Field(ge=1)
    files: tuple[SourceSnapshotEntry, ...] = Field(min_length=1)
    file_count: int = Field(ge=1)
    schema_version: str = "qa_release_source_snapshot_manifest.v2"

    @model_validator(mode="after")
    def validate_manifest(self) -> SourceSnapshotManifest:
        paths = tuple(row.path for row in self.files)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("source snapshot paths are not unique and sorted")
        if self.file_count != len(self.files):
            raise ValueError("source snapshot file count is not derived")
        expected = _content_identity(
            self,
            field="manifest_id",
            prefix="qa_release_source_snapshot_manifest:",
        )
        if self.manifest_id != expected:
            raise ValueError("source snapshot manifest identity is invalid")
        return self


class QAReleaseSourceProjection(BaseModel):
    """Commit/archive/extracted-tree projection used by the executing interpreter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_projection_id: str = Field(min_length=1)
    source_commit_id: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree_id: str = Field(pattern=r"^[0-9a-f]{40}$")
    archive_embedded_commit_id: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_archive_byte_count: int = Field(ge=1)
    source_manifest_id: str = Field(min_length=1)
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_manifest_byte_count: int = Field(ge=1)
    source_manifest_file_count: int = Field(ge=1)
    executed_module_path: str = Field(min_length=1)
    executed_module_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    projection_contract: str = "git_archive_to_extracted_tree_to_git_tree.v1"
    schema_version: str = "qa_release_source_projection.v1"

    @model_validator(mode="after")
    def validate_projection(self) -> QAReleaseSourceProjection:
        if self.archive_embedded_commit_id != self.source_commit_id:
            raise ValueError("archive embedded commit differs from source commit")
        expected = _content_identity(
            self,
            field="source_projection_id",
            prefix="qa_release_source_projection:",
        )
        if self.source_projection_id != expected:
            raise ValueError("QA release source projection identity is invalid")
        return self


class ReleasePopulationMember(BaseModel):
    """One pre-outcome realized surface in the exact authorized population."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    member_id: str = Field(min_length=1)
    fixture_input_id: str = Field(min_length=1)
    fixture_index: int = Field(ge=1)
    task_type: str = Field(min_length=1)
    semantic_schema_id: str = Field(min_length=1)
    semantic_instance_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    realized_package_id: str = Field(min_length=1)
    realization_id: str = Field(min_length=1)
    schema_version: str = "qa_release_population_member.v1"

    @model_validator(mode="after")
    def validate_member(self) -> ReleasePopulationMember:
        expected = _content_identity(
            self,
            field="member_id",
            prefix="qa_release_population_member:",
        )
        if self.member_id != expected:
            raise ValueError("release population member identity is invalid")
        return self


class QAReleasePopulationManifest(BaseModel):
    """Exact, externally anchored population admitted before trajectory outcomes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    population_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_projection_id: str = Field(min_length=1)
    source_selection_contract_id: str = Field(min_length=1)
    fixture_indexes: tuple[int, ...] = Field(min_length=1)
    fixture_input_ids: tuple[str, ...] = Field(min_length=1)
    semantic_instance_ids: tuple[str, ...] = Field(min_length=1)
    members: tuple[ReleasePopulationMember, ...] = Field(min_length=1)
    missing_duplicate_extra_policy: str = "fail_closed_exact_set_equality"
    pre_outcome_authorization_parent: bool = True
    schema_version: str = "qa_release_population_manifest.v1"

    @model_validator(mode="after")
    def validate_population(self) -> QAReleasePopulationManifest:
        if not self.pre_outcome_authorization_parent:
            raise ValueError("release population lacks a pre-outcome authorization parent")
        if self.missing_duplicate_extra_policy != "fail_closed_exact_set_equality":
            raise ValueError("release population admission policy is not fail-closed")
        for values, label in (
            (self.fixture_indexes, "fixture indexes"),
            (self.fixture_input_ids, "fixture input IDs"),
            (self.semantic_instance_ids, "semantic instance IDs"),
            (tuple(row.member_id for row in self.members), "population member IDs"),
        ):
            if tuple(values) != tuple(sorted(values)) or len(values) != len(set(values)):
                raise ValueError(f"release population {label} are not unique and sorted")
        for values, label in (
            (tuple(row.realized_package_id for row in self.members), "realized package IDs"),
            (tuple(row.realization_id for row in self.members), "realization IDs"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"release population {label} are not unique")
        observed_instances = tuple(sorted({row.semantic_instance_id for row in self.members}))
        if self.semantic_instance_ids != observed_instances:
            raise ValueError("release population semantic instance set is not derived")
        observed_fixtures = tuple(sorted({row.fixture_input_id for row in self.members}))
        if self.fixture_input_ids != observed_fixtures:
            raise ValueError("release population fixture input set is not derived")
        expected = _content_identity(
            self,
            field="population_id",
            prefix="qa_release_population_manifest:",
        )
        if self.population_id != expected:
            raise ValueError("QA release population identity is invalid")
        return self


class RuntimeEnvironmentIdentity(BaseModel):
    """Exact interpreter, package, OS, locale, timezone, and environment identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runtime_environment_id: str = Field(min_length=1)
    python_version: str = Field(min_length=1)
    python_implementation: str = Field(min_length=1)
    python_executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pydantic_version: str = Field(min_length=1)
    dependency_lock_hash: str = Field(min_length=1)
    installed_distribution_count: int = Field(ge=1)
    dependency_definition_hash: str = Field(min_length=1)
    os_system: str = Field(min_length=1)
    kernel_release: str = Field(min_length=1)
    libc_identity: str = Field(min_length=1)
    locale_identity: str = Field(min_length=1)
    timezone_identity: str = Field(min_length=1)
    environment_root: str = Field(min_length=1)
    schema_version: str = "qa_release_runtime_environment.v1"

    @model_validator(mode="after")
    def validate_runtime(self) -> RuntimeEnvironmentIdentity:
        expected = _content_identity(
            self,
            field="runtime_environment_id",
            prefix="qa_release_runtime_environment:",
        )
        if self.runtime_environment_id != expected:
            raise ValueError("runtime environment identity is invalid")
        return self


class AuthorityAttackControl(BaseModel):
    """One typed, independently observed authority rejection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attack_id: str = Field(min_length=1)
    mutation_kind: str = "fully_rehashed"
    expected_exception_type: str = "QAReleaseAuthorityError"
    expected_reason_code: str = Field(min_length=1)
    expected_stage: str = Field(min_length=1)
    actual_exception_type: str
    actual_reason_code: str
    actual_stage: str
    target_validator_reached: bool
    rejected: bool
    counted_as_rejection_evidence: bool
    schema_version: str = "qa_release_authority_attack_control.v2"

    @model_validator(mode="after")
    def validate_measurement(self) -> AuthorityAttackControl:
        exact = (
            self.actual_exception_type == self.expected_exception_type
            and self.actual_reason_code == self.expected_reason_code
            and self.actual_stage == self.expected_stage
        )
        if (
            self.target_validator_reached is not exact
            or self.rejected is not exact
            or self.counted_as_rejection_evidence is not exact
        ):
            raise ValueError("attack rejection measurement is not independently derived")
        return self


class AuthorityAttackAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attack_audit_id: str = Field(min_length=1)
    frozen_attack_ids: tuple[str, ...]
    controls: tuple[AuthorityAttackControl, ...]
    unrelated_exception_control: AuthorityAttackControl
    missing_attack_ids: tuple[str, ...]
    duplicate_attack_ids: tuple[str, ...]
    extra_attack_ids: tuple[str, ...]
    schema_version: str = "qa_release_authority_attack_audit.v1"

    @model_validator(mode="after")
    def validate_audit(self) -> AuthorityAttackAudit:
        if self.frozen_attack_ids != FROZEN_ATTACK_IDS:
            raise ValueError("frozen authority attack registry is not exact")
        observed = tuple(row.attack_id for row in self.controls)
        missing = tuple(item for item in FROZEN_ATTACK_IDS if item not in observed)
        duplicate = tuple(sorted({item for item in observed if observed.count(item) > 1}))
        extra = tuple(item for item in observed if item not in FROZEN_ATTACK_IDS)
        if (
            self.missing_attack_ids != missing
            or self.duplicate_attack_ids != duplicate
            or self.extra_attack_ids != extra
        ):
            raise ValueError("attack registry difference sets are not derived")
        if missing or duplicate or extra or observed != FROZEN_ATTACK_IDS:
            raise ValueError("authority attack registry membership or order is not exact")
        if any(not row.counted_as_rejection_evidence for row in self.controls):
            raise ValueError("authority attack suite contains an unproven rejection")
        unrelated = self.unrelated_exception_control
        if (
            unrelated.attack_id != "unrelated_pre_gate_exception"
            or unrelated.counted_as_rejection_evidence
        ):
            raise ValueError("unrelated exception was counted as authority evidence")
        expected = _content_identity(
            self,
            field="attack_audit_id",
            prefix="qa_release_authority_attack_audit:",
        )
        if self.attack_audit_id != expected:
            raise ValueError("authority attack audit identity is invalid")
        return self


class AuthorityArtifactRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)


class QAReleaseAuthorityArtifactManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_manifest_id: str = Field(min_length=1)
    artifact_root: str = Field(min_length=1)
    artifacts: tuple[AuthorityArtifactRow, ...] = Field(min_length=1)
    schema_version: str = "qa_release_authority_artifact_manifest.v2"

    @model_validator(mode="after")
    def validate_artifact_manifest(self) -> QAReleaseAuthorityArtifactManifest:
        names = tuple(row.name for row in self.artifacts)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("authority artifact names are not unique and sorted")
        expected_root = canonical_hash(self.artifacts, prefix="qa_release_authority_artifact_root:")
        if self.artifact_root != expected_root:
            raise ValueError("authority artifact root is not derived")
        expected = _content_identity(
            self,
            field="artifact_manifest_id",
            prefix="qa_release_authority_artifact_manifest:",
        )
        if self.artifact_manifest_id != expected:
            raise ValueError("authority artifact manifest identity is invalid")
        return self


class QAReleaseAuthorityReport(BaseModel):
    """Content-addressed report fully derived from authority parents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str = Field(min_length=1)
    status: str = "passed"
    authorization_id: str = Field(min_length=1)
    source_projection_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    runtime_environment_id: str = Field(min_length=1)
    authority_bundle_id: str = Field(min_length=1)
    release_selection_id: str = Field(min_length=1)
    attack_audit_id: str = Field(min_length=1)
    artifact_root: str = Field(min_length=1)
    artifact_manifest_id: str = Field(min_length=1)
    fixture_count: int = Field(ge=1)
    release_record_count: int = Field(ge=1)
    selected_record_count: int = Field(ge=1)
    frozen_task_type_count: int = Field(ge=1)
    frozen_renderer_profile_count: int = Field(ge=1)
    exact_attack_count: int = Field(ge=1)
    exact_attack_rejection_count: int = Field(ge=1)
    provider_calls: int = Field(ge=0)
    unrelated_exception_counted: bool
    archive_backed_pilot_authorized: bool
    production_authorized: bool
    schema_version: str = "qa_release_authority_report.v2"

    @model_validator(mode="after")
    def validate_report(self) -> QAReleaseAuthorityReport:
        if self.status != "passed":
            raise ValueError("authority report status is not source-derived passed")
        if self.provider_calls != 0 or self.unrelated_exception_counted:
            raise ValueError("authority report violates the zero-provider attack boundary")
        if self.archive_backed_pilot_authorized or self.production_authorized:
            raise ValueError("authority report overstates the permitted execution boundary")
        if self.exact_attack_count != len(
            FROZEN_ATTACK_IDS
        ) or self.exact_attack_rejection_count != len(FROZEN_ATTACK_IDS):
            raise ValueError("authority report attack denominator is not exact")
        expected = _content_identity(
            self,
            field="report_id",
            prefix="qa_release_authority_report:",
        )
        if self.report_id != expected:
            raise ValueError("QA release authority report identity is invalid")
        return self


class QAReleaseAuthorityEnvelope(BaseModel):
    """Externally anchored top object authenticating every semantic sidecar and report."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    envelope_id: str = Field(min_length=1)
    authorization: QAReleaseAuthorityAuthorization
    source_projection: QAReleaseSourceProjection
    population_manifest: QAReleasePopulationManifest
    runtime_environment: RuntimeEnvironmentIdentity
    authority_bundle: QAReleaseAuthorityBundle
    release_selection: DiversityAwareReleaseSelection
    release_records: tuple[PersistedReleaseRecord, ...]
    attack_audit: AuthorityAttackAudit
    artifact_manifest: QAReleaseAuthorityArtifactManifest
    report: QAReleaseAuthorityReport
    report_markdown_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_markdown_byte_count: int = Field(ge=1)
    schema_version: str = "qa_release_authority_envelope.v1"

    @model_validator(mode="after")
    def validate_envelope(self) -> QAReleaseAuthorityEnvelope:
        bundle = self.authority_bundle
        if self.authorization.authorized_source_commit != self.source_projection.source_commit_id:
            raise ValueError("envelope authorization crosses its source projection")
        if self.population_manifest.authorization_id != self.authorization.authorization_id:
            raise ValueError("envelope population crosses its authorization")
        if (
            self.population_manifest.source_projection_id
            != self.source_projection.source_projection_id
        ):
            raise ValueError("envelope population crosses its source projection")
        if self.release_selection != bundle.release_selection:
            raise ValueError("envelope release selection crosses its authority bundle")
        if self.release_records != self.release_selection.release_records:
            raise ValueError("envelope release records cross its release selection")
        report = self.report
        expected_report_parents = (
            self.authorization.authorization_id,
            self.source_projection.source_projection_id,
            self.population_manifest.population_id,
            self.runtime_environment.runtime_environment_id,
            bundle.authority_bundle_id,
            self.release_selection.selection_id,
            self.attack_audit.attack_audit_id,
            self.artifact_manifest.artifact_root,
            self.artifact_manifest.artifact_manifest_id,
        )
        observed_report_parents = (
            report.authorization_id,
            report.source_projection_id,
            report.population_id,
            report.runtime_environment_id,
            report.authority_bundle_id,
            report.release_selection_id,
            report.attack_audit_id,
            report.artifact_root,
            report.artifact_manifest_id,
        )
        if observed_report_parents != expected_report_parents:
            raise ValueError("envelope report crosses its authoritative parents")
        expected = _content_identity(
            self,
            field="envelope_id",
            prefix="qa_release_authority_envelope:",
        )
        if self.envelope_id != expected:
            raise ValueError("QA release authority envelope identity is invalid")
        return self


def build_authorization(
    *,
    external_audit_bytes: bytes,
    source_commit_id: str,
    observed_change_surface: tuple[str, ...],
) -> QAReleaseAuthorityAuthorization:
    audit_sha = hashlib.sha256(external_audit_bytes).hexdigest()
    payload: dict[str, Any] = {
        "external_audit_sha256": audit_sha,
        "external_audit_byte_count": len(external_audit_bytes),
        "audit_bytes_hash": canonical_hash(
            {
                "byte_count": len(external_audit_bytes),
                "sha256": audit_sha,
                "schema_version": "external_audit_bytes.v1",
            },
            prefix="external_audit_bytes:",
        ),
        "authorized_predecessor": AUTHORIZED_PREDECESSOR,
        "authorized_source_commit": source_commit_id,
        "permitted_transition": AUTHORIZED_TRANSITION,
        "permitted_change_surface": PERMITTED_CHANGE_SURFACE,
        "observed_change_surface": observed_change_surface,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "schema_version": "qa_release_authority_authorization.v1",
    }
    provisional = QAReleaseAuthorityAuthorization.model_construct(
        authorization_id="pending",
        **payload,
    )
    return QAReleaseAuthorityAuthorization(
        authorization_id=_content_identity(
            provisional,
            field="authorization_id",
            prefix="qa_release_authority_authorization:",
        ),
        **payload,
    )


def build_population_manifest(
    *,
    authorization: QAReleaseAuthorityAuthorization,
    source_projection: QAReleaseSourceProjection,
    bundle: QAReleaseAuthorityBundle,
) -> QAReleasePopulationManifest:
    fixture_by_binding = {row.evidence_binding.binding_id: row for row in bundle.fixture_inputs}
    members = []
    for record in bundle.release_selection.release_records:
        realized = record.realized
        fixture = fixture_by_binding.get(realized.binding_snapshot.evidence_binding.binding_id)
        if fixture is None:
            raise ValueError("release record lacks an exact fixture population parent")
        payload = {
            "fixture_input_id": fixture.fixture_input_id,
            "fixture_index": fixture.fixture_index,
            "task_type": realized.task.public.task_type,
            "semantic_schema_id": realized.semantic_plan.semantic_task_id,
            "semantic_instance_id": realized.semantic_instance_id,
            "binding_snapshot_id": realized.binding_snapshot_id,
            "realized_package_id": realized.realized_package_id,
            "realization_id": realized.realization.realization_id,
            "schema_version": "qa_release_population_member.v1",
        }
        provisional_member = ReleasePopulationMember.model_construct(
            member_id="pending",
            **payload,
        )
        members.append(
            ReleasePopulationMember(
                member_id=_content_identity(
                    provisional_member,
                    field="member_id",
                    prefix="qa_release_population_member:",
                ),
                **payload,
            )
        )
    sorted_members = tuple(sorted(members, key=lambda row: row.member_id))
    fixture_indexes = tuple(sorted(row.fixture_index for row in bundle.fixture_inputs))
    fixture_ids = tuple(sorted(row.fixture_input_id for row in bundle.fixture_inputs))
    semantic_instance_ids = tuple(sorted({row.semantic_instance_id for row in sorted_members}))
    payload = {
        "authorization_id": authorization.authorization_id,
        "source_projection_id": source_projection.source_projection_id,
        "source_selection_contract_id": canonical_hash(
            {
                "fixture_indexes": fixture_indexes,
                "release_policy_hash": bundle.release_policy_hash,
                "split_policy_hash": bundle.split_policy_hash,
                "schema_version": "qa_release_population_source_selection.v1",
            },
            prefix="qa_release_population_source_selection:",
        ),
        "fixture_indexes": fixture_indexes,
        "fixture_input_ids": fixture_ids,
        "semantic_instance_ids": semantic_instance_ids,
        "members": sorted_members,
        "missing_duplicate_extra_policy": "fail_closed_exact_set_equality",
        "pre_outcome_authorization_parent": True,
        "schema_version": "qa_release_population_manifest.v1",
    }
    provisional = QAReleasePopulationManifest.model_construct(population_id="pending", **payload)
    return QAReleasePopulationManifest(
        population_id=_content_identity(
            provisional,
            field="population_id",
            prefix="qa_release_population_manifest:",
        ),
        **payload,
    )


def capture_runtime_environment(source_root: Path) -> RuntimeEnvironmentIdentity:
    distributions = tuple(
        sorted(
            (
                distribution.metadata["Name"].lower(),
                distribution.version,
            )
            for distribution in importlib.metadata.distributions()
        )
    )
    dependency_definitions = []
    for relative in (
        "trusted_data_synthesis/pyproject.toml",
        "raw_financial_data_lake/pyproject.toml",
    ):
        path = source_root / relative
        if path.is_file():
            content = path.read_bytes()
            dependency_definitions.append(
                {"path": relative, "sha256": hashlib.sha256(content).hexdigest()}
            )
    executable = Path(sys.executable).resolve()
    libc_name, libc_version = platform.libc_ver()
    payload = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "pydantic_version": importlib.metadata.version("pydantic"),
        "dependency_lock_hash": canonical_hash(
            distributions,
            prefix="installed_python_distribution_lock:",
        ),
        "installed_distribution_count": len(distributions),
        "dependency_definition_hash": canonical_hash(
            dependency_definitions,
            prefix="source_dependency_definitions:",
        ),
        "os_system": platform.system(),
        "kernel_release": platform.release(),
        "libc_identity": f"{libc_name}:{libc_version}",
        "locale_identity": locale.setlocale(locale.LC_ALL, None),
        "timezone_identity": canonical_hash(
            {"TZ": os.environ.get("TZ", ""), "tzname": time.tzname},
            prefix="runtime_timezone:",
        ),
        "environment_root": str(Path(sys.prefix).resolve()),
        "schema_version": "qa_release_runtime_environment.v1",
    }
    provisional = RuntimeEnvironmentIdentity.model_construct(
        runtime_environment_id="pending",
        **payload,
    )
    return RuntimeEnvironmentIdentity(
        runtime_environment_id=_content_identity(
            provisional,
            field="runtime_environment_id",
            prefix="qa_release_runtime_environment:",
        ),
        **payload,
    )
