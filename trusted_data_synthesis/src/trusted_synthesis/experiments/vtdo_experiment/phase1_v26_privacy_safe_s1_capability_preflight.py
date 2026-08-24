from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_dynamic_role_preflight as role_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as privacy_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_privacy_safe_prompt_qualification_postrun_audit as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_privacy_safe_prompt_runner_preflight as prompt_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_preflight as runner_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_execution as action_execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_two_stage_semantic_proposal_execution as legacy,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    make_final_response_host_envelope,
    parse_prompt_only_reference_final_payload,
    render_exact_final_primary_prompt,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_protocol import (
    CanonicalActionCommit,
    PublicSemanticRejectionObservation,
    SemanticActionState,
    build_semantic_action_state,
    evaluate_canonical_action_proposal,
)
from trusted_synthesis.runtime.agent.prospective_thinking_completion import CompletionProjection
from trusted_synthesis.runtime.tools import AgentToolObservation

RUN_ID: Final = "finance_v26_140_privacy_safe_s1_capability_preflight_v1_20260824"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_140_privacy_safe_s1_capability_preflight_v1_20260824"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_privacy_safe_s1_capability_preflight.py"
)
PREDECESSOR_DIR: Final = predecessor.OUTPUT_DIR
EXECUTION_DIR: Final = predecessor.EXECUTION_DIR
ROLE_DIR: Final = role_base.OUTPUT_DIR
PROMPT_DIR: Final = prompt_base.OUTPUT_DIR
NEXT_STAGE: Final = "privacy_safe_s1_capability_execution_only"
PROSPECTIVE_RUNNER_RUN_ID: Final = "finance_v26_140_privacy_safe_s1_capability_runner_v1_20260824"
PROSPECTIVE_EXECUTION_RUN_ID: Final = (
    "finance_v26_141_privacy_safe_s1_capability_execution_v1_20260824"
)
PROSPECTIVE_REPORT_RUN_ID: Final = (
    "finance_v26_141_privacy_safe_s1_capability_execution_report_v1_20260824"
)

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_privacy_safe_s1_postrun_audit_report:"
    "4dca82657f009642423a416cd1da3553f2327fd1ecdf468bdc1b1b169eba497a"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "720194f4d93fe10a4b4891fb3213b2bc452c03578c5b280bec025cd73f8cb47b"
)
EXPECTED_PREDECESSOR_GATE_ID: Final = (
    "finance_v26_privacy_safe_s1_qualification_gate_audit:"
    "10206b746caef04c550b1b9ba389f0f3a14203f1f5594a9a26ca584ae82488cc"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_privacy_safe_s1_postrun_transition:"
    "97def7ae5bbfdb49edf6f8854cb41a86dbd997731be84dbe00462a14192d0cbf"
)
EXPECTED_PREDECESSOR_TRANSITION_SHA256: Final = (
    "0d7165d8961a3062b4f170a5f62318b39847028cb242d6b34caba80bebc3c065"
)
EXPECTED_ROLE_REPORT_ID: Final = (
    "finance_v26_bounded_dynamic_role_preflight_report:"
    "cb509fe5dfed2ef5c399dc9781852c873b08f028960abf0e086124db6b67cb06"
)
EXPECTED_ROLE_REPORT_SHA256: Final = (
    "e60444665db0da325ced6427fd07a11139d2db8ba99cbca0b02b00db461ed2f9"
)
EXPECTED_ROLE_KERNEL_ID: Final = (
    "finance_v26_bounded_dynamic_role_kernel:"
    "6b40395f55211b036f570a53f7c89f157844c819cc7c0533c721f78465e3186c"
)
EXPECTED_ROLE_RESOURCE_ID: Final = (
    "finance_v26_bounded_dynamic_resource_contract:"
    "addc8f6b01bc1111dc23ee176b440518cc1016087c0e20669d1ae9ee5be97820"
)
EXPECTED_ROLE_TASK_CATALOG_ID: Final = (
    "finance_v26_role_task_package_catalog:"
    "7b49db254ac45809e85ea0bb0252fd3f38254e7df3c951ed7c54ba63cab544f7"
)
EXPECTED_ROLE_PATH_CATALOG_ID: Final = (
    "finance_v26_role_path_catalog:b38b5b04af181f291a12313b5f5007cf630ebd1c2f915c82eaae22c2963ef5f8"
)
EXPECTED_ROLE_IDENTITY_CHAIN_ID: Final = (
    "finance_v26_role_identity_chain:"
    "16f63a56f33cc0ede19c8df5c4d8eda763847d86321399a6f28e0992f43ff6ab"
)
EXPECTED_ROLE_RUNNER_ID: Final = (
    "finance_v26_bounded_dynamic_runner_contract:"
    "06a317c786050d812fc6ffafac9e0d7560c335f3b6742697d08ed413b798fd76"
)
EXPECTED_CAPABILITY_POPULATION_ID: Final = role_base.EXPECTED_CAPABILITY_POPULATION_ID
EXPECTED_PROMPT_CONTRACT_ID: Final = (
    "finance_v26_privacy_safe_prompt_metadata_contract:"
    "13b048dc569ea491edbf4f6dbf636240634537e55f3f30a50e6cfb8410c4da72"
)
EXPECTED_PROMPT_CONTRACT_SHA256: Final = (
    "b600223d09bc22b115fb47d77977617d57fae59d511a36b2f385afd0152c0ec3"
)

CAPABILITY_TASK_COUNT: Final = 12
CAPABILITY_PATH_COUNT: Final = 12
CAPABILITY_JOB_COUNT: Final = 96
CAPABILITY_ROLLOUTS_PER_TASK: Final = 8
REGISTERED_ACTION_STATE_COUNT: Final = 111
REGISTERED_ACTION_PROMPT_COUNT: Final = 333
PROMPT_PHASES: Final = prompt_base.PROMPT_PHASES
MECHANISMS: Final = (
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
)
TIERS: Final = ("easy_control", "frontier", "hard_control")


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        path = root / relative_path
        if path.is_file() and _sha256(path) == expected_sha256:
            return path
    raise ValueError(f"v26.140 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_source_replay_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=4535, max_length=4535)
    replayed_file_count: Literal[4535] = 4535
    replay_pass_count: Literal[4535] = 4535
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_source_replay.v1"] = (
        "finance_v26_privacy_safe_capability_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            self.entries != tuple(sorted(self.entries, key=lambda item: item.relative_path))
            or len(set(paths)) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.140 source replay changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_safe_capability_source_replay:"
        ):
            raise ValueError("v26.140 source replay identity changed")
        return self


class PredecessorIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_gate_id: str = EXPECTED_PREDECESSOR_GATE_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_rebuild_file_count: Literal[9] = 9
    predecessor_rebuild_byte_match_count: Literal[9] = 9
    exact_v2_engineering_s1_qualification_passed: Literal[True] = True
    historical_v1_gate_remains_failed: Literal[True] = True
    historical_rows_pooled_or_reclassified: Literal[False] = False
    engineering_result_used_for_role_task_selection: Literal[False] = False
    role_source_model_exposure_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_predecessor_integrity.v1"] = (
        "finance_v26_privacy_safe_capability_predecessor_integrity.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_privacy_safe_capability_predecessor_integrity:",
        ):
            raise ValueError("v26.140 predecessor integrity identity changed")
        return self


class FrozenCapabilityInputAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    role_report_id: str = EXPECTED_ROLE_REPORT_ID
    role_kernel_id: str = EXPECTED_ROLE_KERNEL_ID
    role_resource_contract_id: str = EXPECTED_ROLE_RESOURCE_ID
    predecessor_task_catalog_id: str = EXPECTED_ROLE_TASK_CATALOG_ID
    predecessor_path_catalog_id: str = EXPECTED_ROLE_PATH_CATALOG_ID
    predecessor_identity_chain_id: str = EXPECTED_ROLE_IDENTITY_CHAIN_ID
    predecessor_runner_contract_id: str = EXPECTED_ROLE_RUNNER_ID
    capability_population_id: str = EXPECTED_CAPABILITY_POPULATION_ID
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    capability_task_count: Literal[12] = 12
    capability_path_count: Literal[12] = 12
    capability_job_count: Literal[96] = 96
    easy_frontier_hard_task_counts: dict[str, int]
    mechanism_task_counts: dict[str, int]
    source_task_projection_pass_count: Literal[12] = 12
    task_tier_projection_pass_count: Literal[12] = 12
    path_semantic_reconstruction_pass_count: Literal[12] = 12
    job_assignment_seed_projection_pass_count: Literal[96] = 96
    reachability_source_count_retained_unexposed: Literal[12] = 12
    fresh_reachability_task_package_count: Literal[0] = 0
    fresh_reachability_path_count: Literal[0] = 0
    fresh_reachability_contract_count: Literal[0] = 0
    fresh_reachability_manifest_count: Literal[0] = 0
    fresh_reachability_job_count: Literal[0] = 0
    role_population_task_or_tier_changed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_frozen_capability_input_audit.v1"] = (
        "finance_v26_frozen_capability_input_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> FrozenCapabilityInputAudit:
        if self.easy_frontier_hard_task_counts != {tier: 4 for tier in TIERS}:
            raise ValueError("v26.140 Capability Tier balance changed")
        if self.mechanism_task_counts != {mechanism: 3 for mechanism in MECHANISMS}:
            raise ValueError("v26.140 Capability mechanism balance changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_frozen_capability_input_audit:"
        ):
            raise ValueError("v26.140 frozen Capability input identity changed")
        return self


class CapabilityTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    predecessor_package: role_base.RoleScalableTaskPackage
    role_kernel_id: str = EXPECTED_ROLE_KERNEL_ID
    capability_population_id: str = EXPECTED_CAPABILITY_POPULATION_ID
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    prompt_protocol: str = prompt_base.PRIVACY_SAFE_PROMPT_PROTOCOL
    role: Literal["capability"] = "capability"
    mechanism_id: str = Field(min_length=1)
    tier: Literal["easy_control", "frontier", "hard_control"]
    source_task_artifact_id: str = Field(min_length=1)
    source_binding_id: str = Field(min_length=1)
    stage_one_profile_id: str = role_base.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = role_base.EXPECTED_STAGE_TWO_PROFILE_ID
    model_config_id: str = role_base.EXPECTED_MODEL_CONFIG_ID
    thinking_binding_id: str = role_base.EXPECTED_THINKING_BINDING_ID
    thinking_type: Literal["enabled"] = "enabled"
    semantic_action_protocol_id: str = role_base.EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = role_base.EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = role_base.EXPECTED_FINAL_GRAMMAR_ID
    compact_projection_protocol_id: str = role_base.EXPECTED_COMPACT_PROTOCOL_ID
    s1_candidate_id: str = role_base.EXPECTED_S1_CANDIDATE_ID
    candidate_authority_and_presentation_preserved: Literal[True] = True
    source_task_semantics_preserved: Literal[True] = True
    task_or_tier_changed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_task_package.v1"] = (
        "finance_v26_privacy_safe_capability_task_package.v1"
    )

    @model_validator(mode="after")
    def validate_package(self) -> CapabilityTaskPackage:
        old = self.predecessor_package
        if (
            old.task_package_id != self.predecessor_task_package_id
            or old.role != self.role
            or old.role_population_id != self.capability_population_id
            or old.kernel_id != self.role_kernel_id
            or old.mechanism_id != self.mechanism_id
            or old.tier != self.tier
            or old.source_task_artifact_id != self.source_task_artifact_id
            or old.source_binding_id != self.source_binding_id
            or self.task_package_id == self.predecessor_task_package_id
        ):
            raise ValueError("v26.140 Capability TaskPackage projection changed")
        if self.task_package_id != _identity(
            self, "task_package_id", "finance_v26_privacy_safe_capability_task_package:"
        ):
            raise ValueError("v26.140 Capability TaskPackage identity changed")
        return self


class CapabilityTaskPackageCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    role_kernel_id: str = EXPECTED_ROLE_KERNEL_ID
    capability_population_id: str = EXPECTED_CAPABILITY_POPULATION_ID
    predecessor_catalog_id: str = EXPECTED_ROLE_TASK_CATALOG_ID
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    packages: tuple[CapabilityTaskPackage, ...] = Field(min_length=12, max_length=12)
    task_package_count: Literal[12] = 12
    distinct_source_task_count: Literal[12] = 12
    predecessor_identity_overlap_count: Literal[0] = 0
    mechanism_tier_cell_count: Literal[12] = 12
    reachability_task_package_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_task_catalog.v1"] = (
        "finance_v26_privacy_safe_capability_task_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> CapabilityTaskPackageCatalog:
        cells = {(item.mechanism_id, item.tier) for item in self.packages}
        if (
            self.packages != tuple(sorted(self.packages, key=lambda item: item.task_package_id))
            or len({item.task_package_id for item in self.packages}) != self.task_package_count
            or len({item.source_task_artifact_id for item in self.packages})
            != self.distinct_source_task_count
            or len(cells) != self.mechanism_tier_cell_count
            or cells != {(mechanism, tier) for mechanism in MECHANISMS for tier in TIERS}
        ):
            raise ValueError("v26.140 Capability TaskPackage catalog changed")
        if self.catalog_id != _identity(
            self, "catalog_id", "finance_v26_privacy_safe_capability_task_catalog:"
        ):
            raise ValueError("v26.140 Capability TaskPackage catalog identity changed")
        return self


class CapabilityPromptBindingRow(FrozenModel):
    row_id: str = Field(min_length=1)
    predecessor_path_id: str = Field(min_length=1)
    logical_state_index: int = Field(ge=0)
    state_id: str = Field(min_length=1)
    presentation_salt: str = Field(min_length=1)
    candidate_count: int = Field(gt=0)
    presented_action_ids: tuple[str, ...] = Field(min_length=1)
    predecessor_prompt_sha256s: dict[str, str]
    privacy_safe_prompt_sha256s: dict[str, str]
    predecessor_prompt_utf8_bytes: dict[str, int]
    privacy_safe_prompt_utf8_bytes: dict[str, int]
    reference_proposal_id: str = Field(min_length=1)
    reference_action_id: str = Field(min_length=1)
    reference_decision_kind: str = Field(min_length=1)
    reversible_commit_id: str = Field(min_length=1)
    observation_id: str | None
    classifier_sensitive_key_count: Literal[0] = 0
    prompt_echo_privacy_accept_count: Literal[3] = 3
    prompt_echo_action_grammar_rejection_count: Literal[3] = 3
    intended_action_grammar_pass_count: Literal[3] = 3
    intended_action_privacy_pass_count: Literal[3] = 3
    state_candidate_reference_commit_preservation_count: Literal[3] = 3
    only_authorized_prompt_difference_count: Literal[3] = 3
    prompt_hash_changed_count: Literal[3] = 3

    @model_validator(mode="after")
    def validate_row(self) -> CapabilityPromptBindingRow:
        if (
            set(self.predecessor_prompt_sha256s) != set(PROMPT_PHASES)
            or set(self.privacy_safe_prompt_sha256s) != set(PROMPT_PHASES)
            or len(self.presented_action_ids) != self.candidate_count
            or any(
                self.predecessor_prompt_sha256s[phase] == self.privacy_safe_prompt_sha256s[phase]
                for phase in PROMPT_PHASES
            )
        ):
            raise ValueError("v26.140 Capability Prompt row changed")
        if self.row_id != _identity(
            self, "row_id", "finance_v26_privacy_safe_capability_prompt_binding:"
        ):
            raise ValueError("v26.140 Capability Prompt row identity changed")
        return self


class CapabilityPath(FrozenModel):
    path_id: str = Field(min_length=1)
    predecessor_path_id: str = Field(min_length=1)
    predecessor_census_path_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    role_kernel_id: str = EXPECTED_ROLE_KERNEL_ID
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    role: Literal["capability"] = "capability"
    mechanism_id: str = Field(min_length=1)
    tier: Literal["easy_control", "frontier", "hard_control"]
    path_strategy_id: Literal["structured_direct"] = "structured_direct"
    public_path_condition: None = None
    prompt_rows: tuple[CapabilityPromptBindingRow, ...] = Field(min_length=1)
    reference_state_ids: tuple[str, ...] = Field(min_length=1)
    reference_proposal_ids: tuple[str, ...] = Field(min_length=1)
    stage_two_commit_ids: tuple[str, ...] = Field(min_length=1)
    observation_ids: tuple[str, ...]
    final_primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_rescue_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    final_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    primary_request_count: int = Field(gt=0, le=21)
    provider_call_count_with_recoveries: int = Field(gt=0, le=23)
    transport_inclusive_invocation_count: int = Field(gt=0, le=24)
    static_complete_path_upper_bound_tokens: int = Field(gt=0, le=1120000)
    program_closed: Literal[True] = True
    terminal_node_completed: Literal[True] = True
    terminal_verification_completed: Literal[True] = True
    final_commit_reached: Literal[True] = True
    exact_final_abi_passed: Literal[True] = True
    full_object_fallback_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_path.v1"] = (
        "finance_v26_privacy_safe_capability_path.v1"
    )

    @model_validator(mode="after")
    def validate_path(self) -> CapabilityPath:
        count = len(self.prompt_rows)
        if (
            self.path_id == self.predecessor_path_id
            or count != len(self.reference_state_ids)
            or count != len(self.reference_proposal_ids)
            or count != len(self.stage_two_commit_ids)
            or self.primary_request_count != count + 1
            or self.provider_call_count_with_recoveries != self.primary_request_count + 2
            or self.transport_inclusive_invocation_count
            != self.provider_call_count_with_recoveries + 1
        ):
            raise ValueError("v26.140 Capability Path accounting changed")
        if self.path_id != _identity(self, "path_id", "finance_v26_privacy_safe_capability_path:"):
            raise ValueError("v26.140 Capability Path identity changed")
        return self


class CapabilityPathCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    predecessor_catalog_id: str = EXPECTED_ROLE_PATH_CATALOG_ID
    task_package_catalog_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    paths: tuple[CapabilityPath, ...] = Field(min_length=12, max_length=12)
    path_count: Literal[12] = 12
    registered_state_count: Literal[111] = 111
    regenerated_action_prompt_count: Literal[333] = 333
    maximum_candidate_count: int = Field(gt=0, le=128)
    maximum_action_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_action_abi_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_action_semantic_recovery_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_final_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_final_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_registered_path_static_tokens: int = Field(gt=0, le=1120000)
    classifier_sensitive_key_count: Literal[0] = 0
    prompt_echo_privacy_rejection_count: Literal[0] = 0
    state_candidate_reference_commit_preservation_count: Literal[333] = 333
    predecessor_path_identity_overlap_count: Literal[0] = 0
    reachability_path_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_path_catalog.v1"] = (
        "finance_v26_privacy_safe_capability_path_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> CapabilityPathCatalog:
        rows = tuple(row for path in self.paths for row in path.prompt_rows)
        if (
            self.paths != tuple(sorted(self.paths, key=lambda item: item.path_id))
            or len({item.path_id for item in self.paths}) != self.path_count
            or len(rows) != self.registered_state_count
            or self.regenerated_action_prompt_count != len(rows) * len(PROMPT_PHASES)
            or len({item.task_package_id for item in self.paths}) != self.path_count
        ):
            raise ValueError("v26.140 Capability Path catalog changed")
        if self.catalog_id != _identity(
            self, "catalog_id", "finance_v26_privacy_safe_capability_path_catalog:"
        ):
            raise ValueError("v26.140 Capability Path catalog identity changed")
        return self


class CapabilityPromptNoninterferenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    path_catalog_id: str = Field(min_length=1)
    registered_state_count: Literal[111] = 111
    phase_prompt_counts: dict[str, int]
    registered_action_prompt_count: Literal[333] = 333
    classifier_sensitive_key_count: Literal[0] = 0
    predecessor_sensitive_key_occurrence_count: Literal[666] = 666
    predecessor_prompt_echo_privacy_rejection_count: Literal[333] = 333
    privacy_safe_prompt_echo_privacy_rejection_count: Literal[0] = 0
    privacy_safe_prompt_echo_privacy_accept_count: Literal[333] = 333
    prompt_echo_action_grammar_rejection_count: Literal[333] = 333
    intended_action_grammar_pass_count: Literal[333] = 333
    intended_action_privacy_pass_count: Literal[333] = 333
    exact_state_candidate_reference_commit_count: Literal[333] = 333
    only_authorized_difference_count: Literal[333] = 333
    full_object_fallback_count: Literal[0] = 0
    classifier_grammar_candidate_s1_changed: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["capability_role_prompt_noninterference_passed"] = (
        "capability_role_prompt_noninterference_passed"
    )
    schema_version: Literal["finance_v26_capability_prompt_noninterference.v1"] = (
        "finance_v26_capability_prompt_noninterference.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CapabilityPromptNoninterferenceAudit:
        if (
            self.phase_prompt_counts != {phase: 111 for phase in PROMPT_PHASES}
            or sum(self.phase_prompt_counts.values()) != self.registered_action_prompt_count
        ):
            raise ValueError("v26.140 Capability Prompt noninterference denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_capability_prompt_noninterference:"
        ):
            raise ValueError("v26.140 Capability Prompt audit identity changed")
        return self


class CapabilityResourceBinding(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_resource_contract_id: str = EXPECTED_ROLE_RESOURCE_ID
    path_catalog_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    prompt_upper_bound_bytes: Literal[60000] = 60000
    chat_envelope_tokens: Literal[256] = 256
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    provider_accounting_margin_tokens: Literal[1] = 1
    accounted_completion_bound_tokens: Literal[16385] = 16385
    rollout_upper_bound_tokens: Literal[1120000] = 1120000
    maximum_primary_stage_one_requests: Literal[21] = 21
    maximum_stage_one_provider_calls: Literal[23] = 23
    maximum_transport_inclusive_invocations: Literal[24] = 24
    maximum_abi_rescue_calls: Literal[1] = 1
    maximum_semantic_recovery_calls: Literal[1] = 1
    maximum_transport_replacement_calls: Literal[1] = 1
    maximum_ordinary_detours: Literal[1] = 1
    qualified_maximum_action_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_action_abi_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_semantic_recovery_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_final_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    qualified_maximum_final_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_registered_path_static_tokens: int = Field(gt=0, le=1120000)
    old_resource_values_changed: Literal[False] = False
    new_resource_candidate_selected: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_resource_binding.v1"] = (
        "finance_v26_privacy_safe_capability_resource_binding.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> CapabilityResourceBinding:
        if (
            self.accounted_completion_bound_tokens
            != self.exact_request_completion_bound_tokens + self.provider_accounting_margin_tokens
            or self.maximum_stage_one_provider_calls
            != self.maximum_primary_stage_one_requests
            + self.maximum_abi_rescue_calls
            + self.maximum_semantic_recovery_calls
            or self.maximum_transport_inclusive_invocations
            != self.maximum_stage_one_provider_calls + self.maximum_transport_replacement_calls
        ):
            raise ValueError("v26.140 Capability resource arithmetic changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_capability_resource_binding:"
        ):
            raise ValueError("v26.140 Capability resource identity changed")
        return self


class CapabilityExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_contract_id: str = Field(min_length=1)
    predecessor_qualification_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_qualification_gate_id: str = EXPECTED_PREDECESSOR_GATE_ID
    role_kernel_id: str = EXPECTED_ROLE_KERNEL_ID
    capability_population_id: str = EXPECTED_CAPABILITY_POPULATION_ID
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    resource_binding_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    task_package_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    path_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    role: Literal["capability"] = "capability"
    exact_job_denominator: Literal[96] = 96
    tasks_per_mechanism: Literal[3] = 3
    tasks_per_tier: Literal[4] = 4
    rollouts_per_task: Literal[8] = 8
    task_is_primary_sampling_unit: Literal[True] = True
    model_id: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    stage_one_profile_id: str = role_base.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = role_base.EXPECTED_STAGE_TWO_PROFILE_ID
    model_config_id: str = role_base.EXPECTED_MODEL_CONFIG_ID
    thinking_binding_id: str = role_base.EXPECTED_THINKING_BINDING_ID
    thinking_type: Literal["enabled"] = "enabled"
    compact_projection_is_model_visible_condition: Literal[True] = True
    privacy_safe_v2_prompt_is_model_visible_condition: Literal[True] = True
    invalid_model_outcomes_retained: Literal[True] = True
    compiler_witnesses_excluded: Literal[True] = True
    reachability_identity_or_execution_included: Literal[False] = False
    empirical_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_execution_contract.v1"] = (
        "finance_v26_privacy_safe_capability_execution_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> CapabilityExecutionContract:
        if (
            len(set(self.task_package_ids)) != CAPABILITY_TASK_COUNT
            or len(set(self.path_ids)) != CAPABILITY_PATH_COUNT
        ):
            raise ValueError("v26.140 Capability execution denominator changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_capability_execution_contract:"
        ):
            raise ValueError("v26.140 Capability execution Contract identity changed")
        return self


class CapabilityJob(FrozenModel):
    job_id: str = Field(min_length=1)
    predecessor_job_id: str = Field(min_length=1)
    predecessor_job: role_base.RoleJob
    contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: Literal["easy_control", "frontier", "hard_control"]
    role: Literal["capability"] = "capability"
    sampling_mode: Literal["capability_unconditional"] = "capability_unconditional"
    replicate_index: int = Field(ge=0, lt=8)
    seed: int = Field(ge=0)
    requested_path_id: None = None
    requested_path_strategy: None = None
    public_condition_id: None = None
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    stage_one_profile_id: str = role_base.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = role_base.EXPECTED_STAGE_TWO_PROFILE_ID
    exact_final_response_grammar_id: str = role_base.EXPECTED_FINAL_GRAMMAR_ID
    thinking_type: Literal["enabled"] = "enabled"
    candidate_presentation_parent_job_id: str = Field(min_length=1)
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    execution_authorized: Literal[False] = False
    state_mapping_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_safe_capability_job.v1"] = (
        "finance_v26_privacy_safe_capability_job.v1"
    )

    @model_validator(mode="after")
    def validate_job(self) -> CapabilityJob:
        old = self.predecessor_job
        if (
            old.job_id != self.predecessor_job_id
            or old.task_package_id != self.predecessor_task_package_id
            or old.mechanism_id != self.mechanism_id
            or old.tier != self.tier
            or old.role != self.role
            or old.sampling_mode != self.sampling_mode
            or old.replicate_index != self.replicate_index
            or old.seed != self.seed
            or old.requested_path_id is not None
            or old.requested_path_strategy is not None
            or old.public_condition_id is not None
            or self.job_id == self.predecessor_job_id
            or self.candidate_presentation_parent_job_id != self.predecessor_job_id
        ):
            raise ValueError("v26.140 Capability Job lineage changed")
        if self.job_id != _identity(self, "job_id", "finance_v26_privacy_safe_capability_job:"):
            raise ValueError("v26.140 Capability Job identity changed")
        return self


class CapabilityManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    predecessor_manifest_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    resource_binding_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    prospective_report_run_id: str = PROSPECTIVE_REPORT_RUN_ID
    jobs: tuple[CapabilityJob, ...] = Field(min_length=96, max_length=96)
    exact_denominator: Literal[96] = 96
    distinct_task_package_count: Literal[12] = 12
    rollouts_per_task: Literal[8] = 8
    distinct_seed_count: Literal[96] = 96
    predecessor_job_identity_overlap_count: Literal[0] = 0
    exact_assignment_seed_preservation_count: Literal[96] = 96
    reachability_job_count: Literal[0] = 0
    each_job_execute_at_most_once: Literal[True] = True
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_safe_capability_manifest.v1"] = (
        "finance_v26_privacy_safe_capability_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> CapabilityManifest:
        counts = Counter(item.task_package_id for item in self.jobs)
        if (
            self.jobs != tuple(sorted(self.jobs, key=lambda item: item.job_id))
            or len({item.job_id for item in self.jobs}) != self.exact_denominator
            or len({item.seed for item in self.jobs}) != self.distinct_seed_count
            or len(counts) != self.distinct_task_package_count
            or set(counts.values()) != {self.rollouts_per_task}
        ):
            raise ValueError("v26.140 Capability Manifest denominator changed")
        if self.manifest_id != _identity(
            self, "manifest_id", "finance_v26_privacy_safe_capability_manifest:"
        ):
            raise ValueError("v26.140 Capability Manifest identity changed")
        return self


class CapabilityOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    exact_denominator: Literal[96] = 96
    primary_estimand: Literal["independently_valid_complete_trajectory"] = (
        "independently_valid_complete_trajectory"
    )
    causal_funnel: tuple[str, ...] = (
        "instrument_eligible",
        "privacy_compliant",
        "action_entry",
        "reversible_commit",
        "public_progress",
        "program_closure",
        "terminal_verification",
        "exact_final_abi",
        "independent_validity",
    )
    terminal_categories: tuple[str, ...] = (
        "model_valid_trajectory",
        "model_invalid_trajectory",
        "ordinary_detour_allowance_exhausted",
        "typed_budget_no_call",
        "provider_transport_failure",
        "instrument_failure",
        "privacy_rejection",
    )
    minimum_mechanisms_with_independently_valid_trajectory_for_successor_preflight: Literal[4] = 4
    complete_raw_denominator_required: Literal[True] = True
    zero_privacy_instrument_identity_thinking_usage_failure_required: Literal[True] = True
    zero_budget_transport_detour_support_exit_required: Literal[True] = True
    model_invalid_trajectories_retained_not_instrument_failures: Literal[True] = True
    detour_support_exit_not_model_invalid: Literal[True] = True
    task_primary_and_rollout_secondary_sampling_units: Literal[True] = True
    report_task_mechanism_tier_and_overall_summaries: Literal[True] = True
    no_posthoc_task_deletion_threshold_change_or_host_repair: Literal[True] = True
    independent_postrun_audit_required: Literal[True] = True
    passing_capability_does_not_directly_authorize_reachability_execution: Literal[True] = True
    state_mapping_rows: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_outcome_contract.v1"] = (
        "finance_v26_privacy_safe_capability_outcome_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> CapabilityOutcomeContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_capability_outcome_contract:"
        ):
            raise ValueError("v26.140 Capability Outcome Contract identity changed")
        return self


class CapabilityRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_runner_contract_id: str = EXPECTED_ROLE_RUNNER_ID
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = EXPECTED_PROMPT_CONTRACT_ID
    runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    exact_job_denominator: Literal[96] = 96
    stage_one_profile_id: str = role_base.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = role_base.EXPECTED_STAGE_TWO_PROFILE_ID
    exact_final_response_grammar_id: str = role_base.EXPECTED_FINAL_GRAMMAR_ID
    thinking_type: Literal["enabled"] = "enabled"
    exact_request_completion_bound_tokens: Literal[16384] = 16384
    rollout_upper_bound_tokens: Literal[1120000] = 1120000
    maximum_primary_stage_one_requests: Literal[21] = 21
    maximum_stage_one_provider_calls: Literal[23] = 23
    maximum_transport_inclusive_invocations: Literal[24] = 24
    maximum_abi_rescue_calls: Literal[1] = 1
    maximum_semantic_recovery_calls: Literal[1] = 1
    maximum_transport_replacement_calls: Literal[1] = 1
    maximum_ordinary_detours: Literal[1] = 1
    all_four_counters_independent: Literal[True] = True
    v2_privacy_safe_s1_only_action_prompts: Literal[True] = True
    frozen_role_candidate_presentation_algorithm: Literal[True] = True
    full_object_fallback_allowed: Literal[False] = False
    privacy_classifier_unchanged: Literal[True] = True
    privacy_redacted_envelope_before_public_projection: Literal[True] = True
    invalid_payload_or_private_reasoning_persisted: Literal[False] = False
    raw_only_recovery: Literal[True] = True
    orphan_artifact_fails_closed: Literal[True] = True
    second_detour_terminal_after_observation_before_later_provider: Literal[True] = True
    stage_two_provider_call_upper_bound: Literal[0] = 0
    capability_only: Literal[True] = True
    reachability_identity_or_route_present: Literal[False] = False
    runner_implemented: Literal[True] = True
    empirical_execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_safe_capability_runner_contract.v1"] = (
        "finance_v26_privacy_safe_capability_runner_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> CapabilityRunnerContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_capability_runner_contract:"
        ):
            raise ValueError("v26.140 Capability Runner Contract identity changed")
        return self


CapabilityTerminal = Literal[
    "completed_model_result",
    "model_result_failure",
    "typed_semantic_rejection",
    "ordinary_detour_allowance_exhausted",
    "typed_budget_no_call",
    "provider_transport_failure",
    "instrument_failure",
]


class CapabilityRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job: CapabilityJob
    task_package_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    provider_envelope_artifacts: tuple[legacy.RawFileDescriptor, ...]
    public_payload_projection_artifacts: tuple[legacy.RawFileDescriptor, ...]
    transport_invocation_artifacts: tuple[legacy.RawFileDescriptor, ...]
    provider_telemetry: tuple[legacy.ModelCallTelemetry, ...]
    attempts: tuple[privacy_runner.PrivacyFirstAttempt, ...]
    semantic_choices: tuple[action_execution.SemanticChoiceRecord, ...]
    commits: tuple[action_execution.SemanticActionCommitRecord, ...]
    semantic_rejections: tuple[PublicSemanticRejectionObservation, ...]
    observations: tuple[AgentToolObservation, ...]
    progress_events: tuple[runner_base.PublicProgressEvent, ...]
    completed_result: privacy_runner.PrivacyFirstCompletedResult | None = None
    terminal_disposition: CapabilityTerminal
    terminal_failure_type: str | None = None
    execution_error: str | None = None
    cumulative_provider_tokens: int = Field(ge=0, le=1120000)
    stage_one_provider_call_count: int = Field(ge=0, le=23)
    transport_inclusive_invocation_count: int = Field(ge=0, le=24)
    abi_rescue_attempt_count: int = Field(ge=0, le=1)
    semantic_recovery_attempt_count: int = Field(ge=0, le=1)
    transport_replacement_attempt_count: int = Field(ge=0, le=1)
    ordinary_detour_count: int = Field(ge=0, le=2)
    privacy_rejected_payload_count: int = Field(ge=0)
    exact_four_field_action_payload_count: int = Field(ge=0)
    exact_two_field_final_payload_count: int = Field(ge=0, le=1)
    first_action_interface_qualified: bool
    stage_two_provider_call_count: Literal[0] = 0
    reachability_or_state_mapping_eligible: Literal[False] = False
    later_provider_calls_after_detour_terminal: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_raw_execution.v1"] = (
        "finance_v26_privacy_safe_capability_raw_execution.v1"
    )

    @model_validator(mode="after")
    def validate_raw(self) -> CapabilityRawExecution:
        if (
            self.task_package_id != self.job.task_package_id
            or len(self.provider_envelope_artifacts) != self.stage_one_provider_call_count
            or len(self.public_payload_projection_artifacts) != self.stage_one_provider_call_count
            or len(self.provider_telemetry) != self.stage_one_provider_call_count
            or len(self.transport_invocation_artifacts) != self.transport_inclusive_invocation_count
            or self.transport_replacement_attempt_count
            != self.transport_inclusive_invocation_count - self.stage_one_provider_call_count
        ):
            raise ValueError("v26.140 Capability Raw denominator changed")
        if self.terminal_disposition == "ordinary_detour_allowance_exhausted" and (
            self.ordinary_detour_count != 2 or self.completed_result is not None
        ):
            raise ValueError("v26.140 Capability Detour terminal changed")
        if self.artifact_id != _identity(
            self, "artifact_id", "finance_v26_privacy_safe_capability_raw_execution:"
        ):
            raise ValueError("v26.140 Capability Raw identity changed")
        return self


class CapabilityDetourPreflightRow(FrozenModel):
    row_id: str = Field(min_length=1)
    predecessor_dynamic_row_id: str = Field(min_length=1)
    predecessor_path_id: str = Field(min_length=1)
    capability_path_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    tier: Literal["easy_control", "frontier", "hard_control"]
    state_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    decision_kind: str = Field(min_length=1)
    reference_state_index: int = Field(ge=0)
    completed_after_one_detour: Literal[True] = True
    ordinary_detour_count: Literal[1] = 1
    maximum_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    static_complete_path_upper_bound_tokens: int = Field(gt=0, le=1120000)
    primary_request_count: int = Field(gt=0, le=21)
    provider_call_count_with_recoveries: int = Field(gt=0, le=23)
    transport_inclusive_invocation_count: int = Field(gt=0, le=24)
    sensitive_prompt_key_count: Literal[0] = 0
    provider_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_row(self) -> CapabilityDetourPreflightRow:
        if self.row_id != _identity(
            self, "row_id", "finance_v26_privacy_safe_capability_detour_row:"
        ):
            raise ValueError("v26.140 Capability Detour row identity changed")
        return self


class CapabilityDynamicEnvelopeAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_dynamic_envelope_audit_id: str = Field(min_length=1)
    resource_binding_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    rows: tuple[CapabilityDetourPreflightRow, ...] = Field(min_length=9, max_length=9)
    eligible_capability_detour_count: Literal[9] = 9
    eligible_capability_detour_pass_count: Literal[9] = 9
    maximum_one_detour_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_one_detour_static_tokens: int = Field(gt=0, le=1120000)
    maximum_one_detour_primary_requests: int = Field(gt=0, le=21)
    maximum_one_detour_provider_calls: int = Field(gt=0, le=23)
    maximum_one_detour_transport_invocations: int = Field(gt=0, le=24)
    second_detour_typed_terminal_passed: Literal[True] = True
    second_detour_proposal_and_observation_retained: Literal[True] = True
    later_provider_calls_after_second_detour: Literal[0] = 0
    reachability_detour_row_materialized_or_executed_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_dynamic_envelope.v1"] = (
        "finance_v26_privacy_safe_capability_dynamic_envelope.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> CapabilityDynamicEnvelopeAudit:
        if (
            self.rows != tuple(sorted(self.rows, key=lambda item: item.row_id))
            or len({item.predecessor_dynamic_row_id for item in self.rows})
            != self.eligible_capability_detour_count
        ):
            raise ValueError("v26.140 Capability Detour denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_safe_capability_dynamic_envelope:"
        ):
            raise ValueError("v26.140 Capability dynamic envelope identity changed")
        return self


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    scripted_job_count: Literal[96] = 96
    completed_job_count: Literal[96] = 96
    first_action_interface_qualified_count: Literal[96] = 96
    covered_mechanism_tier_cell_count: Literal[12] = 12
    semantic_action_primary_count: Literal[888] = 888
    exact_four_field_action_payload_count: Literal[888] = 888
    reversible_commit_count: Literal[888] = 888
    public_observation_count: Literal[792] = 792
    final_primary_count: Literal[96] = 96
    exact_two_field_final_payload_count: Literal[96] = 96
    privacy_envelope_count: Literal[984] = 984
    public_projection_count: Literal[984] = 984
    envelope_before_projection_pass_count: Literal[984] = 984
    privacy_safe_s1_action_prompt_count: Literal[888] = 888
    classifier_sensitive_prompt_key_count: Literal[0] = 0
    full_object_action_prompt_count: Literal[0] = 0
    raw_recovery_pass_count: Literal[96] = 96
    scripted_local_calls: Literal[984] = 984
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    reachability_job_count: Literal[0] = 0
    fixture_hash: str = Field(min_length=64, max_length=64)
    schema_version: Literal["finance_v26_privacy_safe_capability_runner_fixture.v1"] = (
        "finance_v26_privacy_safe_capability_runner_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_safe_capability_runner_fixture:"
        ):
            raise ValueError("v26.140 Capability Runner fixture identity changed")
        return self


class RunnerControlRow(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    passed: Literal[True] = True
    metrics: dict[str, Any]

    @model_validator(mode="after")
    def validate_row(self) -> RunnerControlRow:
        if self.control_id != _identity(
            self, "control_id", "finance_v26_privacy_safe_capability_runner_control:"
        ):
            raise ValueError("v26.140 Capability Runner control identity changed")
        return self


class RunnerControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    rows: tuple[RunnerControlRow, ...] = Field(min_length=20)
    control_count: int = Field(ge=20)
    passed_control_count: int = Field(ge=20)
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_runner_controls.v1"] = (
        "finance_v26_privacy_safe_capability_runner_controls.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerControlAudit:
        if (
            self.rows != tuple(sorted(self.rows, key=lambda item: item.control_id))
            or self.control_count != len(self.rows)
            or self.passed_control_count != self.control_count
        ):
            raise ValueError("v26.140 Capability Runner control denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_safe_capability_runner_controls:"
        ):
            raise ValueError("v26.140 Capability Runner control identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=30)
    mutation_count: int = Field(ge=30)
    rejection_count: int = Field(ge=30)
    provider_calls: Literal[0] = 0
    reachability_provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_destructive.v1"] = (
        "finance_v26_privacy_safe_capability_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if (
            self.mutation_count != len(self.mutations)
            or self.rejection_count != self.mutation_count
        ):
            raise ValueError("v26.140 destructive denominator changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_safe_capability_destructive:"
        ):
            raise ValueError("v26.140 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    exact_manifest_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    next_permitted_stage: str = NEXT_STAGE
    exact_fresh_96_job_capability_execution_authorized: Literal[True] = True
    provider_calls_authorized_only_for_exact_capability_denominator: Literal[True] = True
    capability_execution_authorized: Literal[True] = True
    reachability_identity_materialization_authorized: Literal[False] = False
    reachability_execution_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    role_population_task_tier_s1_candidate_prompt_grammar_model_resource_change_authorized: Literal[
        False
    ] = False
    historical_rerun_pooling_or_reclassification_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    preflight_provider_calls: Literal[0] = 0
    production_contribution: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_capability_transition.v1"] = (
        "finance_v26_privacy_safe_capability_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_capability_transition:"
        ):
            raise ValueError("v26.140 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class CapabilityPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    status: Literal["privacy_safe_s1_capability_runner_preflight_passed"] = (
        "privacy_safe_s1_capability_runner_preflight_passed"
    )
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    frozen_capability_input_audit_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    prompt_noninterference_audit_id: str = Field(min_length=1)
    resource_binding_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    dynamic_envelope_audit_id: str = Field(min_length=1)
    runner_control_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    prospective_execution_id: str = Field(min_length=1)
    prospective_report_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=15)
    fresh_capability_task_package_count: Literal[12] = 12
    fresh_capability_path_count: Literal[12] = 12
    fresh_capability_job_count: Literal[96] = 96
    registered_role_state_count: Literal[111] = 111
    registered_v2_action_prompt_count: Literal[333] = 333
    scripted_fixture_call_count: Literal[984] = 984
    eligible_capability_detour_pass_count: Literal[9] = 9
    fresh_reachability_identity_count: Literal[0] = 0
    role_source_model_exposure_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    capability_execution_occurred: Literal[False] = False
    next_permitted_stage: str = NEXT_STAGE
    schema_version: Literal["finance_v26_privacy_safe_capability_preflight_report.v1"] = (
        "finance_v26_privacy_safe_capability_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> CapabilityPreflightReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_privacy_safe_capability_preflight_report:"
        ):
            raise ValueError("v26.140 report identity changed")
        return self


@dataclass(frozen=True)
class _RoleInputs:
    prompt_contract: prompt_base.PrivacySafePromptMetadataContract
    role_report: role_base.BoundedDynamicRolePreflightReport
    policy: role_base.OrdinaryDetourPolicy
    dynamic: role_base.DynamicTrajectoryEnvelopeAudit
    resource: role_base.RoleScalableResourceContract
    kernel: role_base.RoleScalableKernel
    task_catalog: role_base.RoleTaskPackageCatalog
    path_catalog: role_base.RolePathCatalog
    identity_chain: role_base.RoleIdentityChain
    runner: role_base.RoleRunnerContract
    immediate: Any
    static: Any


@dataclass(frozen=True)
class _CapabilityBinding:
    package: CapabilityTaskPackage
    record: Any
    environment: Any
    prompt_contract: Any
    selection_id: str
    execution: Any


@dataclass(frozen=True)
class _FixtureResult:
    raw: CapabilityRawExecution
    client: Any


def _make_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
) -> SourceReplayAudit:
    predecessor_dir = package_root / PREDECESSOR_DIR
    formal = predecessor.PostrunSourceReplayAudit.model_validate(
        _load(predecessor_dir / "source_replay_audit.json")
    )
    expected: dict[str, str] = {item.relative_path: item.expected_sha256 for item in formal.entries}
    for path in sorted(predecessor_dir.iterdir()):
        if path.is_file():
            expected[str(path.relative_to(package_root))] = _sha256(path)
    implementation_path = implementation_root / IMPLEMENTATION_PATH
    if not implementation_path.is_file():
        raise ValueError("v26.140 implementation source is missing")
    expected[IMPLEMENTATION_PATH] = _sha256(implementation_path)
    if len(expected) != 4535:
        raise ValueError(f"v26.140 source replay denominator changed: {len(expected)}")
    entries: list[SourceReplayEntry] = []
    for relative_path, expected_sha in sorted(expected.items()):
        path = _find_bound_path(
            relative_path,
            expected_sha,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries.append(
            SourceReplayEntry(
                relative_path=relative_path,
                expected_sha256=expected_sha,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    values = {
        "predecessor_source_replay_id": formal.audit_id,
        "entries": tuple(entries),
    }
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_capability_source_replay:",
        ),
        **values,
    )


def _make_predecessor_integrity(
    *,
    package_root: Path,
    implementation_root: Path,
    source_replay: SourceReplayAudit,
) -> PredecessorIntegrityAudit:
    predecessor_dir = package_root / PREDECESSOR_DIR
    report_path = predecessor_dir / "report.json"
    transition_path = predecessor_dir / "prospective_transition_contract.json"
    report = predecessor.PostrunAuditReport.model_validate(_load(report_path))
    gate = predecessor.QualificationGateAudit.model_validate(
        _load(predecessor_dir / "qualification_gate_audit.json")
    )
    transition = predecessor.ProspectiveTransitionContract.model_validate(_load(transition_path))
    if (
        _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or gate.audit_id != EXPECTED_PREDECESSOR_GATE_ID
        or not gate.representation_qualification_gate_passed
        or gate.privacy_gate_failure_job_count != 0
        or _sha256(transition_path) != EXPECTED_PREDECESSOR_TRANSITION_SHA256
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.next_permitted_stage != predecessor.NEXT_STAGE
        or transition.provider_calls_authorized
        or not transition.fresh_capability_taskpackage_contract_manifest_runner_preflight_authorized
    ):
        raise ValueError("v26.140 direct predecessor decision changed")
    with tempfile.TemporaryDirectory(prefix="v26_140_predecessor_") as directory:
        rebuilt_dir = Path(directory)
        predecessor.build_postrun_audit(
            package_root=package_root,
            implementation_root=implementation_root,
            execution_dir=package_root / EXECUTION_DIR,
            output_dir=rebuilt_dir,
        )
        formal_files = tuple(sorted(path for path in predecessor_dir.iterdir() if path.is_file()))
        rebuilt_files = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
        if tuple(path.name for path in formal_files) != tuple(path.name for path in rebuilt_files):
            raise ValueError("v26.140 predecessor rebuild file set changed")
        matches = sum(
            formal_path.read_bytes() == (rebuilt_dir / formal_path.name).read_bytes()
            for formal_path in formal_files
        )
    if len(formal_files) != 9 or matches != 9:
        raise ValueError("v26.140 predecessor rebuild bytes changed")
    values = {"source_replay_audit_id": source_replay.audit_id}
    provisional = PredecessorIntegrityAudit.model_construct(audit_id="pending", **values)
    return PredecessorIntegrityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_capability_predecessor_integrity:",
        ),
        **values,
    )


def _load_role_inputs(
    *,
    package_root: Path,
    implementation_root: Path,
) -> _RoleInputs:
    role_dir = package_root / ROLE_DIR
    prompt_dir = package_root / PROMPT_DIR
    role_report_path = role_dir / "report.json"
    prompt_contract_path = prompt_dir / "privacy_safe_prompt_metadata_contract.json"
    role_report = role_base.BoundedDynamicRolePreflightReport.model_validate(
        _load(role_report_path)
    )
    prompt_contract = prompt_base.PrivacySafePromptMetadataContract.model_validate(
        _load(prompt_contract_path)
    )
    policy = role_base.OrdinaryDetourPolicy.model_validate(
        _load(role_dir / "ordinary_detour_policy.json")
    )
    dynamic = role_base.DynamicTrajectoryEnvelopeAudit.model_validate(
        _load(role_dir / "dynamic_trajectory_envelope_audit.json")
    )
    resource = role_base.RoleScalableResourceContract.model_validate(
        _load(role_dir / "bounded_dynamic_resource_contract.json")
    )
    kernel = role_base.RoleScalableKernel.model_validate(
        _load(role_dir / "bounded_dynamic_role_kernel.json")
    )
    task_catalog = role_base.RoleTaskPackageCatalog.model_validate(
        _load(role_dir / "role_task_package_catalog.json")
    )
    path_catalog = role_base.RolePathCatalog.model_validate(
        _load(role_dir / "role_path_catalog.json")
    )
    identity_chain = role_base.RoleIdentityChain.model_validate(
        _load(role_dir / "role_identity_chain.json")
    )
    runner = role_base.RoleRunnerContract.model_validate(
        _load(role_dir / "bounded_dynamic_runner_contract.json")
    )
    if (
        _sha256(role_report_path) != EXPECTED_ROLE_REPORT_SHA256
        or role_report.report_id != EXPECTED_ROLE_REPORT_ID
        or kernel.kernel_id != EXPECTED_ROLE_KERNEL_ID
        or resource.contract_id != EXPECTED_ROLE_RESOURCE_ID
        or task_catalog.catalog_id != EXPECTED_ROLE_TASK_CATALOG_ID
        or path_catalog.catalog_id != EXPECTED_ROLE_PATH_CATALOG_ID
        or identity_chain.chain_id != EXPECTED_ROLE_IDENTITY_CHAIN_ID
        or runner.contract_id != EXPECTED_ROLE_RUNNER_ID
        or _sha256(prompt_contract_path) != EXPECTED_PROMPT_CONTRACT_SHA256
        or prompt_contract.contract_id != EXPECTED_PROMPT_CONTRACT_ID
    ):
        raise ValueError("v26.140 frozen role or v2 Prompt identity changed")
    immediate = role_base._rebuild_immediate_predecessor(  # noqa: SLF001
        package_root=package_root,
        predecessor_dir=package_root / role_base.PREDECESSOR_DIR,
    )
    rebuilt_tasks, task_mapping = role_base._rematerialize_tasks(  # noqa: SLF001
        predecessor_catalog=immediate.task_catalog,
        kernel=kernel,
    )
    rebuilt_paths, path_mapping = role_base._rematerialize_paths(  # noqa: SLF001
        predecessor_catalog=immediate.path_catalog,
        kernel=kernel,
        task_catalog=rebuilt_tasks,
        task_mapping=task_mapping,
    )
    rebuilt_chain = role_base._make_identity_chain(  # noqa: SLF001
        kernel=kernel,
        resource=resource,
        task_catalog=rebuilt_tasks,
        path_catalog=rebuilt_paths,
        predecessor_chain=immediate.identity_chain,
        task_mapping=task_mapping,
        path_mapping=path_mapping,
    )
    rebuilt_runner = role_base._make_runner_contract(  # noqa: SLF001
        kernel=kernel,
        resource=resource,
        identity_chain=rebuilt_chain,
        policy=policy,
        envelope=dynamic,
    )
    if (
        rebuilt_tasks != task_catalog
        or rebuilt_paths != path_catalog
        or rebuilt_chain != identity_chain
        or rebuilt_runner != runner
    ):
        raise ValueError("v26.140 v26.132 Capability parents do not reproduce")
    static = prompt_base._load_inputs(package_root, implementation_root).engineering  # noqa: SLF001
    return _RoleInputs(
        prompt_contract=prompt_contract,
        role_report=role_report,
        policy=policy,
        dynamic=dynamic,
        resource=resource,
        kernel=kernel,
        task_catalog=task_catalog,
        path_catalog=path_catalog,
        identity_chain=identity_chain,
        runner=runner,
        immediate=immediate,
        static=static,
    )


def _make_frozen_capability_input(inputs: _RoleInputs) -> FrozenCapabilityInputAudit:
    packages = tuple(item for item in inputs.task_catalog.packages if item.role == "capability")
    paths = tuple(item for item in inputs.path_catalog.paths if item.role == "capability")
    jobs = inputs.identity_chain.capability_manifest.jobs
    if (
        len(packages) != 12
        or len(paths) != 12
        or len(jobs) != 96
        or any(item.role != "capability" for item in jobs)
        or any(item.requested_path_id is not None for item in jobs)
    ):
        raise ValueError("v26.140 frozen Capability denominator changed")
    values = {
        "easy_frontier_hard_task_counts": dict(
            sorted(Counter(item.tier for item in packages).items())
        ),
        "mechanism_task_counts": dict(
            sorted(Counter(item.mechanism_id for item in packages).items())
        ),
    }
    provisional = FrozenCapabilityInputAudit.model_construct(audit_id="pending", **values)
    return FrozenCapabilityInputAudit(
        audit_id=_identity(provisional, "audit_id", "finance_v26_frozen_capability_input_audit:"),
        **values,
    )


def _make_task_catalog(
    inputs: _RoleInputs,
) -> tuple[CapabilityTaskPackageCatalog, dict[str, CapabilityTaskPackage]]:
    packages: list[CapabilityTaskPackage] = []
    for old in inputs.task_catalog.packages:
        if old.role != "capability":
            continue
        values = {
            "predecessor_task_package_id": old.task_package_id,
            "predecessor_package": old,
            "mechanism_id": old.mechanism_id,
            "tier": old.tier,
            "source_task_artifact_id": old.source_task_artifact_id,
            "source_binding_id": old.source_binding_id,
        }
        provisional = CapabilityTaskPackage.model_construct(task_package_id="pending", **values)
        packages.append(
            CapabilityTaskPackage(
                task_package_id=_identity(
                    provisional,
                    "task_package_id",
                    "finance_v26_privacy_safe_capability_task_package:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(packages, key=lambda item: item.task_package_id))
    values = {"packages": ordered}
    provisional_catalog = CapabilityTaskPackageCatalog.model_construct(
        catalog_id="pending", **values
    )
    catalog = CapabilityTaskPackageCatalog(
        catalog_id=_identity(
            provisional_catalog,
            "catalog_id",
            "finance_v26_privacy_safe_capability_task_catalog:",
        ),
        **values,
    )
    return catalog, {item.predecessor_task_package_id: item for item in catalog.packages}


def _request_bound(prompt: str) -> int:
    return len(prompt.encode("utf-8")) + 256 + 16_385


def _path_execution_index(inputs: _RoleInputs) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for execution in inputs.immediate.executions:
        if execution.path.role != "capability":
            continue
        key = execution.path.predecessor_census_path_id
        if key in output:
            raise ValueError("v26.140 duplicate Capability census path")
        output[key] = execution
    if len(output) != CAPABILITY_PATH_COUNT:
        raise ValueError("v26.140 Capability execution reconstruction changed")
    return output


def _make_prompt_row(
    *,
    old_path: role_base.RoleScalablePath,
    execution: Any,
    logical_index: int,
    grammar: Any,
) -> CapabilityPromptBindingRow:
    state = execution.states[logical_index]
    expected = execution.proposals[logical_index]
    expected_commit = execution.commits[logical_index]
    salt = old_path.candidate_presentation_salts[logical_index]
    old_prompts: dict[str, str] = {}
    new_prompts: dict[str, str] = {}
    presented_ids: tuple[str, ...] | None = None
    for phase in PROMPT_PHASES:
        old_prompt = role_base.predecessor._compact_action_prompt(  # noqa: SLF001
            phase=cast(Any, phase),
            instruction=execution.task.package.operational_record.task_package.task.public.instruction,
            state=state,
            public_path_condition=None,
            presentation_salt=salt,
            typed_failure=prompt_base._typed_failure(phase),  # noqa: SLF001
            grammar=grammar,
        )
        new_prompt = prompt_base.render_privacy_safe_s1_action_prompt(
            phase=cast(Any, phase),
            instruction=execution.task.package.operational_record.task_package.task.public.instruction,
            state=state,
            public_path_condition=None,
            presentation_salt=salt,
            typed_failure=prompt_base._typed_failure(phase),  # noqa: SLF001
            grammar=grammar,
        )
        decoded_old, candidates_old = (
            role_base.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
                old_prompt, presentation_salt=salt
            )
        )
        decoded_new, candidates_new = (
            role_base.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
                new_prompt, presentation_salt=salt
            )
        )
        proposal_old = role_base.predecessor._compact_reference_proposal(  # noqa: SLF001
            old_prompt, presentation_salt=salt
        )
        proposal_new = role_base.predecessor._compact_reference_proposal(  # noqa: SLF001
            new_prompt, presentation_salt=salt
        )
        parsed = prompt_base.action_grammar.parse_exact_canonical_action_payload(
            prompt_base.action_grammar.exact_canonical_action_payload(proposal_new)
        )
        selected = evaluate_canonical_action_proposal(
            decoded_new, parsed, call_index=logical_index + 1
        )
        old_payload = role_base.predecessor._compact_prompt_payload(old_prompt)  # noqa: SLF001
        new_payload = prompt_base._privacy_safe_prompt_payload(new_prompt).model_dump(  # noqa: SLF001
            mode="json"
        )
        grammar_rejected_echo = False
        try:
            prompt_base.action_grammar.parse_exact_canonical_action_payload(new_payload)
        except prompt_base.action_grammar.SemanticActionResponseRejection:
            grammar_rejected_echo = True
        if (
            decoded_old != state
            or decoded_new != state
            or candidates_old != candidates_new
            or proposal_old != expected
            or proposal_new != expected
            or parsed != expected
            or selected.commit != expected_commit
            or selected.rejection is not None
            or len(prompt_base._sensitive_key_paths(old_payload)) != 2  # noqa: SLF001
            or prompt_base._sensitive_key_paths(new_payload)  # noqa: SLF001
            or not legacy.contains_private_reasoning(old_payload)
            or legacy.contains_private_reasoning(new_payload)
            or legacy.contains_private_reasoning(
                prompt_base.action_grammar.exact_canonical_action_payload(proposal_new)
            )
            or not grammar_rejected_echo
            or not prompt_base._authorized_prompt_difference(old_prompt, new_prompt)  # noqa: SLF001
        ):
            raise ValueError("v26.140 Capability Prompt joint compilation changed")
        current_ids = tuple(item.action_id for item in candidates_new)
        if presented_ids is None:
            presented_ids = current_ids
        elif presented_ids != current_ids:
            raise ValueError("v26.140 Prompt phase changed Candidate presentation")
        old_prompts[phase] = old_prompt
        new_prompts[phase] = new_prompt
    if presented_ids is None:
        raise ValueError("v26.140 Capability Prompt row is empty")
    predecessor_hashes = {phase: legacy.sha256_text(old_prompts[phase]) for phase in PROMPT_PHASES}
    if predecessor_hashes["primary"] != old_path.primary_prompt_sha256s[logical_index]:
        raise ValueError("v26.140 predecessor Capability primary Prompt changed")
    values = {
        "predecessor_path_id": old_path.path_id,
        "logical_state_index": logical_index,
        "state_id": state.state_id,
        "presentation_salt": salt,
        "candidate_count": len(presented_ids),
        "presented_action_ids": presented_ids,
        "predecessor_prompt_sha256s": predecessor_hashes,
        "privacy_safe_prompt_sha256s": {
            phase: legacy.sha256_text(new_prompts[phase]) for phase in PROMPT_PHASES
        },
        "predecessor_prompt_utf8_bytes": {
            phase: len(old_prompts[phase].encode("utf-8")) for phase in PROMPT_PHASES
        },
        "privacy_safe_prompt_utf8_bytes": {
            phase: len(new_prompts[phase].encode("utf-8")) for phase in PROMPT_PHASES
        },
        "reference_proposal_id": expected.proposal_id,
        "reference_action_id": expected.action_id,
        "reference_decision_kind": expected.decision_kind,
        "reversible_commit_id": expected_commit.commit_id,
        "observation_id": (
            execution.observations[logical_index].observation_id
            if logical_index < len(execution.observations)
            else None
        ),
    }
    provisional = CapabilityPromptBindingRow.model_construct(row_id="pending", **values)
    return CapabilityPromptBindingRow(
        row_id=_identity(
            provisional,
            "row_id",
            "finance_v26_privacy_safe_capability_prompt_binding:",
        ),
        **values,
    )


def _make_path_catalog(
    *,
    inputs: _RoleInputs,
    tasks: CapabilityTaskPackageCatalog,
    task_map: Mapping[str, CapabilityTaskPackage],
) -> tuple[CapabilityPathCatalog, dict[str, CapabilityPath]]:
    execution_index = _path_execution_index(inputs)
    paths: list[CapabilityPath] = []
    for old_path in inputs.path_catalog.paths:
        if old_path.role != "capability":
            continue
        execution = execution_index[old_path.predecessor_census_path_id]
        if (
            tuple(item.state_id for item in execution.states) != old_path.reference_state_ids
            or tuple(item.proposal_id for item in execution.proposals)
            != old_path.reference_proposal_ids
            or tuple(item.commit_id for item in execution.commits) != old_path.stage_two_commit_ids
            or tuple(item.observation_id for item in execution.observations)
            != old_path.observation_ids
            or tuple(legacy.sha256_text(item) for item in execution.action_prompts)
            != old_path.primary_prompt_sha256s
        ):
            raise ValueError("v26.140 Capability path semantic reconstruction changed")
        rows = tuple(
            _make_prompt_row(
                old_path=old_path,
                execution=execution,
                logical_index=index,
                grammar=inputs.static.action_grammar,
            )
            for index in range(len(execution.states))
        )
        primary_prompts = [
            prompt_base.render_privacy_safe_s1_action_prompt(
                phase="primary",
                instruction=(
                    execution.task.package.operational_record.task_package.task.public.instruction
                ),
                state=state,
                public_path_condition=None,
                presentation_salt=old_path.candidate_presentation_salts[index],
                typed_failure=None,
                grammar=inputs.static.action_grammar,
            )
            for index, state in enumerate(execution.states)
        ]
        abi_prompts = [
            prompt_base.render_privacy_safe_s1_action_prompt(
                phase="abi_rescue",
                instruction=(
                    execution.task.package.operational_record.task_package.task.public.instruction
                ),
                state=state,
                public_path_condition=None,
                presentation_salt=old_path.candidate_presentation_salts[index],
                typed_failure=prompt_base._typed_failure("abi_rescue"),  # noqa: SLF001
                grammar=inputs.static.action_grammar,
            )
            for index, state in enumerate(execution.states)
        ]
        semantic_prompts = [
            prompt_base.render_privacy_safe_s1_action_prompt(
                phase="semantic_recovery",
                instruction=(
                    execution.task.package.operational_record.task_package.task.public.instruction
                ),
                state=state,
                public_path_condition=None,
                presentation_salt=old_path.candidate_presentation_salts[index],
                typed_failure=prompt_base._typed_failure("semantic_recovery"),  # noqa: SLF001
                grammar=inputs.static.action_grammar,
            )
            for index, state in enumerate(execution.states)
        ]
        static_upper = sum(_request_bound(item) for item in primary_prompts)
        static_upper += _request_bound(execution.final_primary_prompt)
        static_upper += max(
            max(_request_bound(item) for item in abi_prompts),
            _request_bound(execution.final_rescue_prompt),
        )
        static_upper += max(_request_bound(item) for item in semantic_prompts)
        task = task_map[old_path.task_package_id]
        values = {
            "predecessor_path_id": old_path.path_id,
            "predecessor_census_path_id": old_path.predecessor_census_path_id,
            "task_package_id": task.task_package_id,
            "predecessor_task_package_id": old_path.task_package_id,
            "mechanism_id": old_path.mechanism_id,
            "tier": old_path.tier,
            "prompt_rows": rows,
            "reference_state_ids": old_path.reference_state_ids,
            "reference_proposal_ids": old_path.reference_proposal_ids,
            "stage_two_commit_ids": old_path.stage_two_commit_ids,
            "observation_ids": old_path.observation_ids,
            "final_primary_prompt_sha256": old_path.final_primary_prompt_sha256,
            "final_rescue_prompt_sha256": old_path.final_rescue_prompt_sha256,
            "final_primary_prompt_utf8_bytes": len(execution.final_primary_prompt.encode("utf-8")),
            "final_rescue_prompt_utf8_bytes": len(execution.final_rescue_prompt.encode("utf-8")),
            "primary_request_count": old_path.primary_request_count,
            "provider_call_count_with_recoveries": old_path.maximum_provider_calls_with_recovery,
            "transport_inclusive_invocation_count": (
                old_path.maximum_transport_inclusive_invocations
            ),
            "static_complete_path_upper_bound_tokens": static_upper,
        }
        if (
            legacy.sha256_text(execution.final_primary_prompt)
            != old_path.final_primary_prompt_sha256
            or legacy.sha256_text(execution.final_rescue_prompt)
            != old_path.final_rescue_prompt_sha256
        ):
            raise ValueError("v26.140 Capability Final Prompt changed")
        provisional = CapabilityPath.model_construct(path_id="pending", **values)
        paths.append(
            CapabilityPath(
                path_id=_identity(
                    provisional,
                    "path_id",
                    "finance_v26_privacy_safe_capability_path:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(paths, key=lambda item: item.path_id))
    rows = tuple(row for path in ordered for row in path.prompt_rows)
    values = {
        "task_package_catalog_id": tasks.catalog_id,
        "paths": ordered,
        "maximum_candidate_count": max(item.candidate_count for item in rows),
        "maximum_action_primary_prompt_utf8_bytes": max(
            item.privacy_safe_prompt_utf8_bytes["primary"] for item in rows
        ),
        "maximum_action_abi_rescue_prompt_utf8_bytes": max(
            item.privacy_safe_prompt_utf8_bytes["abi_rescue"] for item in rows
        ),
        "maximum_action_semantic_recovery_prompt_utf8_bytes": max(
            item.privacy_safe_prompt_utf8_bytes["semantic_recovery"] for item in rows
        ),
        "maximum_final_primary_prompt_utf8_bytes": max(
            item.final_primary_prompt_utf8_bytes for item in ordered
        ),
        "maximum_final_rescue_prompt_utf8_bytes": max(
            item.final_rescue_prompt_utf8_bytes for item in ordered
        ),
        "maximum_registered_path_static_tokens": max(
            item.static_complete_path_upper_bound_tokens for item in ordered
        ),
    }
    provisional_catalog = CapabilityPathCatalog.model_construct(catalog_id="pending", **values)
    catalog = CapabilityPathCatalog(
        catalog_id=_identity(
            provisional_catalog,
            "catalog_id",
            "finance_v26_privacy_safe_capability_path_catalog:",
        ),
        **values,
    )
    return catalog, {item.predecessor_path_id: item for item in catalog.paths}


def _make_prompt_noninterference(
    catalog: CapabilityPathCatalog,
) -> CapabilityPromptNoninterferenceAudit:
    values = {
        "path_catalog_id": catalog.catalog_id,
        "phase_prompt_counts": {phase: REGISTERED_ACTION_STATE_COUNT for phase in PROMPT_PHASES},
    }
    provisional = CapabilityPromptNoninterferenceAudit.model_construct(audit_id="pending", **values)
    return CapabilityPromptNoninterferenceAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_capability_prompt_noninterference:",
        ),
        **values,
    )


def _make_resource_binding(catalog: CapabilityPathCatalog) -> CapabilityResourceBinding:
    values = {
        "path_catalog_id": catalog.catalog_id,
        "qualified_maximum_action_primary_prompt_utf8_bytes": (
            catalog.maximum_action_primary_prompt_utf8_bytes
        ),
        "qualified_maximum_action_abi_rescue_prompt_utf8_bytes": (
            catalog.maximum_action_abi_rescue_prompt_utf8_bytes
        ),
        "qualified_maximum_semantic_recovery_prompt_utf8_bytes": (
            catalog.maximum_action_semantic_recovery_prompt_utf8_bytes
        ),
        "qualified_maximum_final_primary_prompt_utf8_bytes": (
            catalog.maximum_final_primary_prompt_utf8_bytes
        ),
        "qualified_maximum_final_rescue_prompt_utf8_bytes": (
            catalog.maximum_final_rescue_prompt_utf8_bytes
        ),
        "maximum_registered_path_static_tokens": catalog.maximum_registered_path_static_tokens,
    }
    provisional = CapabilityResourceBinding.model_construct(contract_id="pending", **values)
    return CapabilityResourceBinding(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_capability_resource_binding:",
        ),
        **values,
    )


def _make_execution_contract(
    *,
    inputs: _RoleInputs,
    tasks: CapabilityTaskPackageCatalog,
    paths: CapabilityPathCatalog,
    resource: CapabilityResourceBinding,
) -> CapabilityExecutionContract:
    values = {
        "predecessor_contract_id": inputs.identity_chain.capability_contract.contract_id,
        "task_package_catalog_id": tasks.catalog_id,
        "path_catalog_id": paths.catalog_id,
        "resource_binding_id": resource.contract_id,
        "task_package_ids": tuple(item.task_package_id for item in tasks.packages),
        "path_ids": tuple(item.path_id for item in paths.paths),
    }
    provisional = CapabilityExecutionContract.model_construct(contract_id="pending", **values)
    return CapabilityExecutionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_capability_execution_contract:",
        ),
        **values,
    )


def _make_manifest(
    *,
    inputs: _RoleInputs,
    tasks: CapabilityTaskPackageCatalog,
    paths: CapabilityPathCatalog,
    contract: CapabilityExecutionContract,
    resource: CapabilityResourceBinding,
) -> CapabilityManifest:
    task_map = {item.predecessor_task_package_id: item for item in tasks.packages}
    old_manifest = inputs.identity_chain.capability_manifest
    jobs: list[CapabilityJob] = []
    for old in old_manifest.jobs:
        task = task_map[old.task_package_id]
        values = {
            "predecessor_job_id": old.job_id,
            "predecessor_job": old,
            "contract_id": contract.contract_id,
            "resource_contract_id": resource.contract_id,
            "task_package_id": task.task_package_id,
            "predecessor_task_package_id": old.task_package_id,
            "source_task_artifact_id": task.source_task_artifact_id,
            "mechanism_id": old.mechanism_id,
            "tier": old.tier,
            "replicate_index": old.replicate_index,
            "seed": old.seed,
            "candidate_presentation_parent_job_id": old.job_id,
        }
        provisional = CapabilityJob.model_construct(job_id="pending", **values)
        jobs.append(
            CapabilityJob(
                job_id=_identity(
                    provisional,
                    "job_id",
                    "finance_v26_privacy_safe_capability_job:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    old_projection = sorted(
        (
            item.task_package_id,
            item.mechanism_id,
            item.tier,
            item.replicate_index,
            item.seed,
        )
        for item in old_manifest.jobs
    )
    new_projection = sorted(
        (
            item.predecessor_task_package_id,
            item.mechanism_id,
            item.tier,
            item.replicate_index,
            item.seed,
        )
        for item in ordered
    )
    if old_projection != new_projection:
        raise ValueError("v26.140 Capability Job assignment or Seed changed")
    values = {
        "predecessor_manifest_id": old_manifest.manifest_id,
        "contract_id": contract.contract_id,
        "resource_binding_id": resource.contract_id,
        "task_package_catalog_id": tasks.catalog_id,
        "path_catalog_id": paths.catalog_id,
        "jobs": ordered,
    }
    provisional_manifest = CapabilityManifest.model_construct(manifest_id="pending", **values)
    return CapabilityManifest(
        manifest_id=_identity(
            provisional_manifest,
            "manifest_id",
            "finance_v26_privacy_safe_capability_manifest:",
        ),
        **values,
    )


def _make_outcome_contract(
    contract: CapabilityExecutionContract,
    manifest: CapabilityManifest,
) -> CapabilityOutcomeContract:
    values = {"execution_contract_id": contract.contract_id, "manifest_id": manifest.manifest_id}
    provisional = CapabilityOutcomeContract.model_construct(contract_id="pending", **values)
    return CapabilityOutcomeContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_capability_outcome_contract:",
        ),
        **values,
    )


def _make_runner_contract(
    *,
    contract: CapabilityExecutionContract,
    manifest: CapabilityManifest,
    outcome: CapabilityOutcomeContract,
    resource: CapabilityResourceBinding,
    paths: CapabilityPathCatalog,
) -> CapabilityRunnerContract:
    values = {
        "execution_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "resource_contract_id": resource.contract_id,
        "path_catalog_id": paths.catalog_id,
    }
    provisional = CapabilityRunnerContract.model_construct(contract_id="pending", **values)
    return CapabilityRunnerContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_capability_runner_contract:",
        ),
        **values,
    )


def _capability_raw_path(output_dir: Path, job: CapabilityJob) -> Path:
    return output_dir / "raw_execution" / f"{job.job_id.rsplit(':', 1)[-1]}.json"


def execute_capability_job_raw(
    *,
    job: CapabilityJob,
    runner_contract: CapabilityRunnerContract,
    resource_contract: CapabilityResourceBinding,
    static: Any,
    binding: _CapabilityBinding,
    client: Any | None,
    output_dir: Path,
) -> CapabilityRawExecution:
    raw_path = _capability_raw_path(output_dir, job)
    if raw_path.exists():
        raw = CapabilityRawExecution.model_validate(_load(raw_path))
        if raw.runner_contract_id != runner_contract.contract_id or raw.job != job:
            raise ValueError("v26.140 Raw recovery crosses fresh identities")
        for descriptor in (
            *raw.provider_envelope_artifacts,
            *raw.public_payload_projection_artifacts,
            *raw.transport_invocation_artifacts,
        ):
            path = output_dir / descriptor.relative_path
            if (
                not path.is_file()
                or _sha256(path) != descriptor.sha256
                or path.stat().st_size != descriptor.byte_count
            ):
                raise ValueError("v26.140 Raw recovery bytes changed")
        envelopes = tuple(
            privacy_runner.PrivacyFirstProviderEnvelope.model_validate(
                _load(output_dir / item.relative_path)
            )
            for item in raw.provider_envelope_artifacts
        )
        projections = tuple(
            privacy_runner.PublicPayloadProjection.model_validate(
                _load(output_dir / item.relative_path)
            )
            for item in raw.public_payload_projection_artifacts
        )
        for envelope, projection in zip(envelopes, projections, strict=True):
            privacy_runner.validate_provider_artifact_pair(envelope, projection)
        if tuple(item.provider_telemetry for item in envelopes) != raw.provider_telemetry:
            raise ValueError("v26.140 Raw recovery telemetry changed")
        return raw
    envelope_dir = privacy_runner.provider_envelope_path(output_dir, cast(Any, job), 0).parent
    projection_dir = privacy_runner.payload_projection_path(output_dir, cast(Any, job), 0).parent
    invocation_dir = runner_base._invocation_path(  # noqa: SLF001
        output_dir, cast(Any, job), 0
    ).parent
    if any(
        directory.exists() and any(directory.iterdir())
        for directory in (envelope_dir, projection_dir, invocation_dir)
    ):
        raise ValueError("v26.140 orphan Provider or invocation artifact forbids retry")
    if client is None:
        raise ValueError("pending v26.140 Job has no Stage 1 client")
    ledger = runner_base._S1Journal(  # noqa: SLF001
        client,
        runner_contract=cast(Any, runner_contract),
        resource_contract=cast(Any, resource_contract),
        job=cast(Any, job),
        output_dir=output_dir,
    )
    runtime = legacy._runtime(binding.record, binding.environment)  # noqa: SLF001
    observations: list[AgentToolObservation] = []
    attempts: list[privacy_runner.PrivacyFirstAttempt] = []
    choices: list[action_execution.SemanticChoiceRecord] = []
    commits: list[action_execution.SemanticActionCommitRecord] = []
    semantic_rejections: list[PublicSemanticRejectionObservation] = []
    progress_events: list[runner_base.PublicProgressEvent] = []
    abi_rescue_count = 0
    semantic_recovery_count = 0
    ordinary_detour_count = 0
    pending_semantic_recovery = False
    prior_rejected_action_id: str | None = None
    condition = None
    terminal: CapabilityTerminal = "model_result_failure"
    failure_type: str | None = None
    error: str | None = None
    completed: privacy_runner.PrivacyFirstCompletedResult | None = None
    final_state: SemanticActionState | None = None
    final_commit: CanonicalActionCommit | None = None
    logical_index = 0
    for _ in range(resource_contract.maximum_primary_stage_one_requests - 1):
        state = build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            tuple(observations),
            semantic_rejections=tuple(semantic_rejections),
        )
        presentation_salt = role_base._presentation_salt(  # noqa: SLF001
            selection_id=binding.selection_id,
            package=binding.package.predecessor_package,
            strategy="structured_direct",
            state=state,
            logical_index=logical_index,
        )
        phase: Literal["primary", "semantic_recovery"] = (
            "semantic_recovery" if pending_semantic_recovery else "primary"
        )
        typed_failure = None
        if pending_semantic_recovery:
            rejection = semantic_rejections[-1]
            typed_failure = {
                "family": "semantic_action_rejection",
                "subtype": rejection.error_category,
                "rejection_id": rejection.rejection_id,
            }
        prompt = prompt_base.render_privacy_safe_s1_action_prompt(
            phase=phase,
            instruction=binding.record.task_package.task.public.instruction,
            state=state,
            public_path_condition=condition,
            presentation_salt=presentation_salt,
            typed_failure=typed_failure,
            grammar=static.action_grammar,
        )
        decoded_state, _ = (
            runner_base.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
                prompt, presentation_salt=presentation_salt
            )
        )
        if decoded_state != state or prompt_base._sensitive_key_paths(
            prompt_base._privacy_safe_prompt_payload(prompt).model_dump(mode="json")
        ):
            raise ValueError("v26.140 online Prompt changed state or privacy-safe Key surface")
        diagnostic_reference = runner_base._reference_proposal_from_s1_prompt(prompt)  # noqa: SLF001
        ledger.ordinary_detour_count = ordinary_detour_count
        outcome, abi_rescue_count = prompt_base._privacy_safe_active_call(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="semantic_proposal",
            public_attempt_phase=phase,
            primary_prompt=prompt,
            state=state,
            presentation_salt=presentation_salt,
            instruction=binding.record.task_package.task.public.instruction,
            condition=condition,
            final_response_host_envelope=None,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        current_index = logical_index
        logical_index += 1
        if outcome.attempt.disposition != "usable" or outcome.proposal is None:
            terminal = runner_base._terminal_from_attempt(outcome.attempt)  # noqa: SLF001
            failure_type = (
                outcome.attempt.failure_subtype
                or outcome.attempt.completion_failure_type
                or outcome.attempt.disposition
            )
            error = outcome.attempt.error
            break
        proposal = outcome.proposal
        selected = evaluate_canonical_action_proposal(
            state,
            proposal,
            call_index=len(observations) + 1,
        )
        if selected.rejection is not None:
            choices.append(
                action_execution._choice_record(  # noqa: SLF001
                    logical_request_index=current_index,
                    phase=phase,
                    state=state,
                    proposal=proposal,
                    commit=None,
                    rejection=selected.rejection,
                    prior_rejected_action_id=prior_rejected_action_id,
                    observation=None,
                    progress=None,
                )
            )
            if semantic_recovery_count == 0 and selected.rejection.semantic_recovery_available:
                semantic_recovery_count = 1
                semantic_rejections.append(selected.rejection)
                prior_rejected_action_id = proposal.action_id
                pending_semantic_recovery = True
                continue
            terminal = "typed_semantic_rejection"
            failure_type = "semantic_recovery_exhausted"
            error = selected.rejection.error_category
            break
        commit = selected.commit
        if commit is None:
            raise ValueError("accepted v26.140 action lacks a Commit")
        commits.append(
            runner_base._semantic_commit_record(  # noqa: SLF001
                logical_request_index=current_index,
                state=state,
                proposal=proposal,
                commit=commit,
                stage_two_profile_id=static.stage_two.profile_id,
                provider_calls_before_commit=ledger.provider_call_count,
            )
        )
        pending_semantic_recovery = False
        observation: AgentToolObservation | None = None
        progress: bool | None = None
        detour_terminal = False
        if commit.call is not None:
            observation = legacy._execute_observation(  # noqa: SLF001
                record=binding.record,
                environment=binding.environment,
                runtime=runtime,
                observations=tuple(observations),
                projection=CompletionProjection(
                    request_kind="decision",
                    action="call_tool",
                    tool_id=commit.call.tool_id,
                    arguments=commit.call.arguments,
                ),
            )
            observations.append(observation)
            after = build_semantic_action_state(
                binding.record.task_package.task.public,
                binding.environment,
                tuple(observations),
                semantic_rejections=tuple(semantic_rejections),
            )
            event = runner_base._progress_event(  # noqa: SLF001
                logical_request_index=current_index,
                before=state,
                after=after,
                observation=observation,
                selected_action_id=proposal.action_id,
                reference_action_id=diagnostic_reference.action_id,
                ordinary_detour_count_before=ordinary_detour_count,
            )
            progress_events.append(event)
            progress = event.progress_vector_changed
            ordinary_detour_count = event.ordinary_detour_count_after
            ledger.ordinary_detour_count = ordinary_detour_count
            detour_terminal = ordinary_detour_count > runner_base.MAXIMUM_ORDINARY_DETOURS
        choices.append(
            action_execution._choice_record(  # noqa: SLF001
                logical_request_index=current_index,
                phase=phase,
                state=state,
                proposal=proposal,
                commit=commit,
                rejection=None,
                prior_rejected_action_id=prior_rejected_action_id,
                observation=observation,
                progress=progress,
            )
        )
        if detour_terminal:
            terminal = "ordinary_detour_allowance_exhausted"
            failure_type = "ordinary_detour_allowance_exhausted"
            error = "trajectory left the pre-registered T_dyn^(1) measurement support"
            break
        if commit.action == "emit_final":
            final_state = state
            final_commit = commit
            break
    else:
        terminal = "model_result_failure"
        failure_type = "semantic_action_primary_request_limit_exhausted"
        error = "model did not reach Final within the frozen request limit"
    if (
        final_state is not None
        and final_commit is not None
        and terminal == "model_result_failure"
        and failure_type is None
    ):
        compact_source = render_compact_final_prompt(
            binding.prompt_contract.public_context,
            binding.record.task_package.task.public,
            tuple(observations),
            public_path_condition=condition,
        )
        final_prompt = render_exact_final_primary_prompt(
            compact_source,
            grammar=static.final_grammar,
        )
        host_envelope = make_final_response_host_envelope(
            terminal_state_id=final_state.state_id,
            terminal_commit_id=final_commit.commit_id,
            grammar=static.final_grammar,
        )
        ledger.ordinary_detour_count = ordinary_detour_count
        outcome, abi_rescue_count = prompt_base._privacy_safe_active_call(
            ledger,
            attempts=attempts,
            logical_request_index=logical_index,
            request_kind="final_answer",
            public_attempt_phase="primary",
            primary_prompt=final_prompt,
            state=None,
            presentation_salt=None,
            instruction=None,
            condition=condition,
            final_response_host_envelope=host_envelope,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        if outcome.attempt.disposition == "usable" and outcome.final_payload is not None:
            citations = legacy._selected_evidence_ids(observations)  # noqa: SLF001
            values = {
                "job_id": job.job_id,
                "answer": outcome.final_payload.answer,
                "rationale_summary": outcome.final_payload.rationale_summary,
                "cited_evidence_ids": citations,
                "final_attempt_id": outcome.attempt.attempt_id,
                "final_response_host_envelope": host_envelope,
            }
            provisional_completed = privacy_runner.PrivacyFirstCompletedResult.model_construct(
                result_id="pending", **values
            )
            completed = privacy_runner.PrivacyFirstCompletedResult(
                result_id=_identity(
                    provisional_completed,
                    "result_id",
                    "finance_v26_privacy_first_completed_result:",
                ),
                **values,
            )
            terminal = "completed_model_result"
        else:
            terminal = runner_base._terminal_from_attempt(outcome.attempt)  # noqa: SLF001
            failure_type = (
                outcome.attempt.failure_subtype
                or outcome.attempt.completion_failure_type
                or outcome.attempt.disposition
            )
            error = outcome.attempt.error
    if ledger.instrument_failures:
        terminal = "instrument_failure"
        failure_type = "provider_usage_or_binding_contract_failure"
        error = ";".join(ledger.instrument_failures)
        completed = None
    first_choice = choices[0] if choices else None
    first_interface = bool(
        first_choice is not None
        and first_choice.visible_action_id_match
        and first_choice.decision_kind_match
        and first_choice.semantic_accepted
        and first_choice.commit_id is not None
    )
    raw_values: dict[str, Any] = {
        "runner_contract_id": runner_contract.contract_id,
        "job": job,
        "task_package_id": job.task_package_id,
        "operational_record_id": binding.record.record_id,
        "environment_manifest_id": binding.environment.manifest_id,
        "provider_envelope_artifacts": ledger.envelope_descriptors,
        "public_payload_projection_artifacts": ledger.projection_descriptors,
        "transport_invocation_artifacts": ledger.transport_invocation_descriptors,
        "provider_telemetry": ledger.telemetry,
        "attempts": tuple(attempts),
        "semantic_choices": tuple(choices),
        "commits": tuple(commits),
        "semantic_rejections": tuple(semantic_rejections),
        "observations": tuple(observations),
        "progress_events": tuple(progress_events),
        "completed_result": completed,
        "terminal_disposition": terminal,
        "terminal_failure_type": failure_type,
        "execution_error": error,
        "cumulative_provider_tokens": ledger.cumulative_tokens,
        "stage_one_provider_call_count": ledger.provider_call_count,
        "transport_inclusive_invocation_count": ledger.transport_invocation_count,
        "abi_rescue_attempt_count": sum(
            item.public_attempt_phase == "abi_rescue" for item in attempts
        ),
        "semantic_recovery_attempt_count": sum(
            item.public_attempt_phase == "semantic_recovery" for item in choices
        ),
        "transport_replacement_attempt_count": ledger.transport_replacement_count,
        "ordinary_detour_count": ordinary_detour_count,
        "privacy_rejected_payload_count": sum(
            item == "privacy_rejected" for item in ledger.projection_statuses
        ),
        "exact_four_field_action_payload_count": sum(
            item.exact_four_field_action_payload for item in attempts
        ),
        "exact_two_field_final_payload_count": sum(
            item.exact_two_field_final_payload for item in attempts
        ),
        "first_action_interface_qualified": first_interface,
    }
    provisional_raw = CapabilityRawExecution.model_construct(artifact_id="pending", **raw_values)
    raw = CapabilityRawExecution(
        artifact_id=_identity(
            provisional_raw,
            "artifact_id",
            "finance_v26_privacy_safe_capability_raw_execution:",
        ),
        **raw_values,
    )
    _write_json_atomic(raw_path, raw)
    return raw


def _capability_binding(
    *,
    inputs: _RoleInputs,
    tasks: CapabilityTaskPackageCatalog,
    job: CapabilityJob,
) -> _CapabilityBinding:
    package = next(item for item in tasks.packages if item.task_package_id == job.task_package_id)
    old_job = next(
        item
        for item in inputs.identity_chain.capability_manifest.jobs
        if item.job_id == job.predecessor_job_id
    )
    old_path = next(
        item
        for item in inputs.path_catalog.paths
        if item.role == "capability" and item.task_package_id == package.predecessor_task_package_id
    )
    execution = _path_execution_index(inputs)[old_path.predecessor_census_path_id]
    if (
        old_job.task_package_id != package.predecessor_task_package_id
        or old_job.mechanism_id != job.mechanism_id
        or old_job.tier != job.tier
        or old_job.replicate_index != job.replicate_index
        or old_job.seed != job.seed
        or old_job.sampling_mode != "capability_unconditional"
        or execution.task.package.source_task_artifact_id != package.source_task_artifact_id
    ):
        raise ValueError("v26.140 Capability runtime assignment changed")
    old = package.predecessor_package
    return _CapabilityBinding(
        package=package,
        record=old.operational_record,
        environment=old.environment,
        prompt_contract=old.prompt_contract,
        selection_id=inputs.immediate.loaded.selection.audit_id,
        execution=execution,
    )


def _reference_final_answer(
    binding: _CapabilityBinding,
    *,
    grammar: Any,
) -> Mapping[str, Any]:
    state = binding.execution.states[-1]
    commit = binding.execution.commits[-1]
    envelope = make_final_response_host_envelope(
        terminal_state_id=state.state_id,
        terminal_commit_id=commit.commit_id,
        grammar=grammar,
    )
    payload = parse_prompt_only_reference_final_payload(
        binding.execution.final_primary_prompt,
        envelope=envelope,
    )
    return cast(Mapping[str, Any], payload.answer)


def _fixture_hash(raws: Sequence[CapabilityRawExecution]) -> str:
    return hashlib.sha256(
        _canonical_bytes([item.model_dump(mode="json") for item in raws])
    ).hexdigest()


def _run_fixture_job(
    *,
    inputs: _RoleInputs,
    tasks: CapabilityTaskPackageCatalog,
    job: CapabilityJob,
    resource: CapabilityResourceBinding,
    runner: CapabilityRunnerContract,
    output_dir: Path,
    **client_kwargs: Any,
) -> _FixtureResult:
    binding = _capability_binding(inputs=inputs, tasks=tasks, job=job)
    client = runner_base.ScriptedS1QualificationClient(
        inputs.static.agent_model_config,
        final_answer=_reference_final_answer(binding, grammar=inputs.static.final_grammar),
        **client_kwargs,
    )
    raw = execute_capability_job_raw(
        job=job,
        runner_contract=runner,
        resource_contract=resource,
        static=inputs.static,
        binding=binding,
        client=client,
        output_dir=output_dir,
    )
    return _FixtureResult(raw=raw, client=client)


def _make_runner_fixture(
    *,
    inputs: _RoleInputs,
    tasks: CapabilityTaskPackageCatalog,
    manifest: CapabilityManifest,
    resource: CapabilityResourceBinding,
    runner: CapabilityRunnerContract,
) -> RunnerFixtureAudit:
    raws: list[CapabilityRawExecution] = []
    prompts: list[tuple[str, str, str]] = []
    with tempfile.TemporaryDirectory(prefix="v26_140_capability_fixture_") as temporary:
        root = Path(temporary)
        for job in manifest.jobs:
            result = _run_fixture_job(
                inputs=inputs,
                tasks=tasks,
                job=job,
                resource=resource,
                runner=runner,
                output_dir=root,
            )
            raw = result.raw
            if raw.terminal_disposition != "completed_model_result":
                raise ValueError(
                    "v26.140 scripted Capability Job did not complete: "
                    f"{job.job_id} {raw.terminal_disposition} "
                    f"{raw.terminal_failure_type} {raw.execution_error}"
                )
            recovered = execute_capability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=inputs.static,
                binding=_capability_binding(inputs=inputs, tasks=tasks, job=job),
                client=None,
                output_dir=root,
            )
            if recovered.model_dump(mode="json") != raw.model_dump(mode="json"):
                raise ValueError("v26.140 Capability Raw recovery changed")
            raws.append(raw)
            prompts.extend(result.client.prompts)
    action_prompts = tuple(prompt for kind, _, prompt in prompts if kind == "semantic_proposal")
    safe_prompt_count = sum(
        prompt_base.PRIVACY_SAFE_PROMPT_PROTOCOL in prompt
        and not prompt_base._sensitive_key_paths(  # noqa: SLF001
            prompt_base._privacy_safe_prompt_payload(prompt).model_dump(mode="json")  # noqa: SLF001
        )
        for prompt in action_prompts
    )
    cells = {
        (item.job.mechanism_id, item.job.tier)
        for item in raws
        if item.first_action_interface_qualified
    }
    values = {
        "runner_contract_id": runner.contract_id,
        "manifest_id": manifest.manifest_id,
        "completed_job_count": sum(
            item.terminal_disposition == "completed_model_result" for item in raws
        ),
        "first_action_interface_qualified_count": sum(
            item.first_action_interface_qualified for item in raws
        ),
        "covered_mechanism_tier_cell_count": len(cells),
        "semantic_action_primary_count": sum(
            item.exact_four_field_action_payload_count for item in raws
        ),
        "exact_four_field_action_payload_count": sum(
            item.exact_four_field_action_payload_count for item in raws
        ),
        "reversible_commit_count": sum(len(item.commits) for item in raws),
        "public_observation_count": sum(len(item.observations) for item in raws),
        "final_primary_count": sum(item.exact_two_field_final_payload_count for item in raws),
        "exact_two_field_final_payload_count": sum(
            item.exact_two_field_final_payload_count for item in raws
        ),
        "privacy_envelope_count": sum(item.stage_one_provider_call_count for item in raws),
        "public_projection_count": sum(item.stage_one_provider_call_count for item in raws),
        "envelope_before_projection_pass_count": sum(
            item.stage_one_provider_call_count for item in raws
        ),
        "privacy_safe_s1_action_prompt_count": safe_prompt_count,
        "scripted_local_calls": sum(item.stage_one_provider_call_count for item in raws),
        "fixture_hash": _fixture_hash(raws),
    }
    provisional = RunnerFixtureAudit.model_construct(audit_id="pending", **values)
    return RunnerFixtureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_capability_runner_fixture:",
        ),
        **values,
    )


def _control_row(name: str, metrics: Mapping[str, Any]) -> RunnerControlRow:
    values = {"control_name": name, "metrics": dict(metrics)}
    provisional = RunnerControlRow.model_construct(control_id="pending", **values)
    return RunnerControlRow(
        control_id=_identity(
            provisional,
            "control_id",
            "finance_v26_privacy_safe_capability_runner_control:",
        ),
        **values,
    )


def _make_dynamic_envelope(
    *,
    inputs: _RoleInputs,
    tasks: CapabilityTaskPackageCatalog,
    paths: CapabilityPathCatalog,
    manifest: CapabilityManifest,
    resource: CapabilityResourceBinding,
    runner: CapabilityRunnerContract,
) -> tuple[CapabilityDynamicEnvelopeAudit, CapabilityRawExecution, CapabilityRawExecution]:
    deltas = {
        row.privacy_safe_prompt_utf8_bytes[phase] - row.predecessor_prompt_utf8_bytes[phase]
        for path in paths.paths
        for row in path.prompt_rows
        for phase in PROMPT_PHASES
    }
    if deltas != {84}:
        raise ValueError(f"v26.140 privacy-safe Action Prompt delta changed: {sorted(deltas)}")
    delta = 84
    bounded_by_census = {
        item.predecessor_census_path_id: item
        for item in inputs.path_catalog.paths
        if item.role == "capability"
    }
    predecessor_paths = {
        item.path_id: bounded_by_census[item.predecessor_census_path_id]
        for item in inputs.immediate.path_catalog.paths
        if item.role == "capability"
    }
    new_paths = {item.predecessor_path_id: item for item in paths.paths}
    jobs_by_old_task: dict[str, CapabilityJob] = {}
    for job in manifest.jobs:
        if job.replicate_index == 0:
            jobs_by_old_task[job.predecessor_task_package_id] = job
    rows: list[CapabilityDetourPreflightRow] = []
    old_rows = tuple(
        item
        for item in inputs.dynamic.rows
        if item.role == "capability" and item.outcome == "eligible_closed_no_progress"
    )
    if len(old_rows) != 9:
        raise ValueError("v26.140 eligible Capability Detour denominator changed")
    for old in old_rows:
        old_path = predecessor_paths[old.predecessor_path_id]
        path = new_paths[old_path.path_id]
        job = jobs_by_old_task[old_path.task_package_id]
        primary = cast(int, old.primary_request_count)
        provider = cast(int, old.provider_call_count_with_recoveries)
        transport = cast(int, old.transport_inclusive_invocation_count)
        old_prompt = cast(int, old.maximum_prompt_utf8_bytes)
        old_tokens = cast(int, old.static_complete_path_upper_bound_tokens)
        values = {
            "predecessor_dynamic_row_id": old.row_id,
            "predecessor_path_id": old_path.path_id,
            "capability_path_id": path.path_id,
            "task_package_id": path.task_package_id,
            "job_id": job.job_id,
            "mechanism_id": old.mechanism_id,
            "tier": old.tier,
            "state_id": old.state_id,
            "action_id": old.action_id,
            "decision_kind": old.decision_kind,
            "reference_state_index": old.reference_state_index,
            "maximum_prompt_utf8_bytes": old_prompt + delta,
            "static_complete_path_upper_bound_tokens": (old_tokens + delta * (primary + 1)),
            "primary_request_count": primary,
            "provider_call_count_with_recoveries": provider,
            "transport_inclusive_invocation_count": transport,
        }
        provisional = CapabilityDetourPreflightRow.model_construct(row_id="pending", **values)
        rows.append(
            CapabilityDetourPreflightRow(
                row_id=_identity(
                    provisional,
                    "row_id",
                    "finance_v26_privacy_safe_capability_detour_row:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(rows, key=lambda item: item.row_id))
    control_row = min(ordered, key=lambda item: (item.reference_state_index, item.row_id))
    control_job = next(item for item in manifest.jobs if item.job_id == control_row.job_id)
    with tempfile.TemporaryDirectory(prefix="v26_140_detour_") as temporary:
        root = Path(temporary)
        one = _run_fixture_job(
            inputs=inputs,
            tasks=tasks,
            job=control_job,
            resource=resource,
            runner=runner,
            output_dir=root / "one",
            force_action_id=control_row.action_id,
            force_action_uses=1,
        ).raw
        two = _run_fixture_job(
            inputs=inputs,
            tasks=tasks,
            job=control_job,
            resource=resource,
            runner=runner,
            output_dir=root / "two",
            force_action_id=control_row.action_id,
            force_action_uses=2,
        ).raw
    if (
        one.terminal_disposition != "completed_model_result"
        or one.ordinary_detour_count != 1
        or two.terminal_disposition != "ordinary_detour_allowance_exhausted"
        or two.ordinary_detour_count != 2
        or not two.progress_events[-1].ordinary_detour_observed
        or two.later_provider_calls_after_detour_terminal != 0
    ):
        raise ValueError("v26.140 Capability Detour Runner control failed")
    values = {
        "predecessor_dynamic_envelope_audit_id": inputs.dynamic.audit_id,
        "resource_binding_id": resource.contract_id,
        "runner_contract_id": runner.contract_id,
        "rows": ordered,
        "maximum_one_detour_prompt_utf8_bytes": max(
            item.maximum_prompt_utf8_bytes for item in ordered
        ),
        "maximum_one_detour_static_tokens": max(
            item.static_complete_path_upper_bound_tokens for item in ordered
        ),
        "maximum_one_detour_primary_requests": max(item.primary_request_count for item in ordered),
        "maximum_one_detour_provider_calls": max(
            item.provider_call_count_with_recoveries for item in ordered
        ),
        "maximum_one_detour_transport_invocations": max(
            item.transport_inclusive_invocation_count for item in ordered
        ),
    }
    provisional = CapabilityDynamicEnvelopeAudit.model_construct(audit_id="pending", **values)
    return (
        CapabilityDynamicEnvelopeAudit(
            audit_id=_identity(
                provisional,
                "audit_id",
                "finance_v26_privacy_safe_capability_dynamic_envelope:",
            ),
            **values,
        ),
        one,
        two,
    )


def _make_runner_controls(
    *,
    inputs: _RoleInputs,
    tasks: CapabilityTaskPackageCatalog,
    paths: CapabilityPathCatalog,
    manifest: CapabilityManifest,
    resource: CapabilityResourceBinding,
    runner: CapabilityRunnerContract,
    fixture: RunnerFixtureAudit,
    noninterference: CapabilityPromptNoninterferenceAudit,
    dynamic: CapabilityDynamicEnvelopeAudit,
    one_detour: CapabilityRawExecution,
    two_detour: CapabilityRawExecution,
) -> RunnerControlAudit:
    ordinary = manifest.jobs[0]
    rows: list[RunnerControlRow] = []
    with tempfile.TemporaryDirectory(prefix="v26_140_capability_controls_") as temporary:
        root = Path(temporary)
        abi = _run_fixture_job(
            inputs=inputs,
            tasks=tasks,
            job=ordinary,
            resource=resource,
            runner=runner,
            output_dir=root / "abi",
            malformed_action_once=True,
        ).raw
        if (
            abi.terminal_disposition != "completed_model_result"
            or abi.abi_rescue_attempt_count != 1
            or abi.semantic_recovery_attempt_count != 0
        ):
            raise ValueError("v26.140 Capability ABI Rescue control failed")
        rows.append(_control_row("exact_action_abi_rescue", {"abi_rescues": 1}))

        semantic = _run_fixture_job(
            inputs=inputs,
            tasks=tasks,
            job=ordinary,
            resource=resource,
            runner=runner,
            output_dir=root / "semantic",
            semantic_rejection_once=True,
        ).raw
        if (
            semantic.terminal_disposition != "completed_model_result"
            or semantic.semantic_recovery_attempt_count != 1
            or semantic.abi_rescue_attempt_count != 0
        ):
            raise ValueError("v26.140 Capability Semantic Recovery control failed")
        rows.append(
            _control_row(
                "semantic_recovery_is_separate",
                {"semantic_recoveries": 1, "abi_rescues": 0},
            )
        )

        transport = _run_fixture_job(
            inputs=inputs,
            tasks=tasks,
            job=ordinary,
            resource=resource,
            runner=runner,
            output_dir=root / "transport",
            transport_failure_once=True,
        ).raw
        if (
            transport.terminal_disposition != "completed_model_result"
            or transport.transport_replacement_attempt_count != 1
            or transport.transport_inclusive_invocation_count
            != transport.stage_one_provider_call_count + 1
        ):
            raise ValueError("v26.140 Capability Transport Replacement control failed")
        rows.append(
            _control_row(
                "single_transport_replacement",
                {
                    "transport_replacements": 1,
                    "provider_calls": transport.stage_one_provider_call_count,
                    "transport_invocations": transport.transport_inclusive_invocation_count,
                },
            )
        )

        privacy_root = root / "privacy"
        privacy = _run_fixture_job(
            inputs=inputs,
            tasks=tasks,
            job=ordinary,
            resource=resource,
            runner=runner,
            output_dir=privacy_root,
            privacy_failure_once=True,
        ).raw
        artifact_bytes = b"".join(
            (privacy_root / item.relative_path).read_bytes()
            for item in (
                *privacy.provider_envelope_artifacts,
                *privacy.public_payload_projection_artifacts,
            )
        )
        if (
            privacy.privacy_rejected_payload_count != 1
            or b"fixture private content" in artifact_bytes
            or b"reasoning_trace" in artifact_bytes
        ):
            raise ValueError("v26.140 Capability privacy-first rejection control failed")
        rows.append(
            _control_row(
                "privacy_first_generic_rejection",
                {"privacy_rejections": 1, "rejected_payload_persisted": False},
            )
        )

        admitted: list[int] = []
        for tokens in (16_384, 16_385):
            usage = _run_fixture_job(
                inputs=inputs,
                tasks=tasks,
                job=ordinary,
                resource=resource,
                runner=runner,
                output_dir=root / f"usage_{tokens}",
                completion_tokens=tokens,
            ).raw
            if usage.terminal_disposition != "completed_model_result":
                raise ValueError("v26.140 admitted Completion Usage control failed")
            admitted.append(tokens)
        rejected_usage = _run_fixture_job(
            inputs=inputs,
            tasks=tasks,
            job=ordinary,
            resource=resource,
            runner=runner,
            output_dir=root / "usage_16386",
            completion_tokens=16_386,
        ).raw
        if rejected_usage.terminal_disposition != "instrument_failure":
            raise ValueError("v26.140 rejected Completion Usage control failed")
        rows.append(
            _control_row(
                "completion_usage_semantics",
                {"admitted": admitted, "instrument_failure": 16386},
            )
        )

        wrong = _run_fixture_job(
            inputs=inputs,
            tasks=tasks,
            job=ordinary,
            resource=resource,
            runner=runner,
            output_dir=root / "wrong_final",
            wrong_final_answer=True,
        ).raw
        if (
            wrong.terminal_disposition != "completed_model_result"
            or wrong.exact_two_field_final_payload_count != 1
            or not wrong.first_action_interface_qualified
        ):
            raise ValueError("v26.140 Final ABI/validity separation control failed")
        rows.append(
            _control_row(
                "exact_final_abi_separate_from_validity",
                {"exact_final_abi": 1, "host_answer_repair": False},
            )
        )

        binding = _capability_binding(inputs=inputs, tasks=tasks, job=ordinary)
        recovered = execute_capability_job_raw(
            job=ordinary,
            runner_contract=runner,
            resource_contract=resource,
            static=inputs.static,
            binding=binding,
            client=None,
            output_dir=root / "abi",
        )
        if recovered.model_dump(mode="json") != abi.model_dump(mode="json"):
            raise ValueError("v26.140 Capability complete Raw recovery changed")
        rows.append(_control_row("complete_raw_zero_call_recovery", {"recovered": 1}))

        orphan_root = root / "orphan"
        orphan = privacy_runner.provider_envelope_path(orphan_root, cast(Any, ordinary), 0)
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_text("{}\n", encoding="utf-8")
        try:
            execute_capability_job_raw(
                job=ordinary,
                runner_contract=runner,
                resource_contract=resource,
                static=inputs.static,
                binding=binding,
                client=None,
                output_dir=orphan_root,
            )
        except ValueError:
            pass
        else:
            raise ValueError("v26.140 orphan Provider artifact did not block retry")
        rows.append(_control_row("orphan_artifact_blocks_retry", {"blocked": 1}))

    if (
        one_detour.ordinary_detour_count != 1
        or one_detour.terminal_disposition != "completed_model_result"
    ):
        raise ValueError("v26.140 one-Detour control changed")
    rows.append(
        _control_row(
            "one_ordinary_detour_then_replan",
            {
                "ordinary_detours": 1,
                "abi_semantic_transport_counts": [
                    one_detour.abi_rescue_attempt_count,
                    one_detour.semantic_recovery_attempt_count,
                    one_detour.transport_replacement_attempt_count,
                ],
            },
        )
    )
    if (
        two_detour.terminal_disposition != "ordinary_detour_allowance_exhausted"
        or two_detour.ordinary_detour_count != 2
        or two_detour.later_provider_calls_after_detour_terminal != 0
    ):
        raise ValueError("v26.140 second-Detour control changed")
    rows.append(
        _control_row(
            "second_detour_is_typed_support_exit",
            {
                "ordinary_detours": 2,
                "later_provider_calls": 0,
                "retained_proposal_and_observation": True,
                "classified_as_model_invalid": False,
            },
        )
    )

    max_candidate = max(row.candidate_count for path in paths.paths for row in path.prompt_rows)
    max_prompt = max(
        row.privacy_safe_prompt_utf8_bytes["primary"]
        for path in paths.paths
        for row in path.prompt_rows
    )
    if (
        max_candidate != paths.maximum_candidate_count
        or max_prompt != paths.maximum_action_primary_prompt_utf8_bytes
        or max_prompt > resource.prompt_upper_bound_bytes
    ):
        raise ValueError("v26.140 maximum Candidate or Prompt control failed")
    rows.append(_control_row("maximum_candidate_state", {"candidate_count": max_candidate}))
    rows.append(
        _control_row(
            "maximum_registered_prompt",
            {"utf8_bytes": max_prompt, "ceiling": resource.prompt_upper_bound_bytes},
        )
    )

    deep = tuple(
        item
        for item in tasks.packages
        if item.mechanism_id == "semantic_reconciliation"
        and item.predecessor_package.deep_reconciliation_formal_compiler_used
    )
    if len(deep) != 2:
        raise ValueError("v26.140 deep Reconciliation coverage changed")
    rows.append(_control_row("deep_reconciliation_paths", {"task_count": len(deep)}))

    mechanism_counts = Counter(item.mechanism_id for item in tasks.packages)
    tier_counts = Counter(item.tier for item in tasks.packages)
    if mechanism_counts != Counter({item: 3 for item in MECHANISMS}) or tier_counts != Counter(
        {item: 4 for item in TIERS}
    ):
        raise ValueError("v26.140 Capability mechanism/Tier coverage changed")
    rows.append(
        _control_row(
            "all_mechanism_tier_cells",
            {"cell_count": len(MECHANISMS) * len(TIERS)},
        )
    )
    rows.append(
        _control_row(
            "failure_recovery_role_tasks",
            {"task_count": mechanism_counts["failure_recovery"]},
        )
    )
    rows.append(
        _control_row(
            "state_dependent_stopping_role_tasks",
            {"task_count": mechanism_counts["state_dependent_stopping"]},
        )
    )

    if (
        noninterference.registered_action_prompt_count != 333
        or noninterference.classifier_sensitive_key_count != 0
        or noninterference.privacy_safe_prompt_echo_privacy_rejection_count != 0
    ):
        raise ValueError("v26.140 role Prompt noninterference control failed")
    rows.append(
        _control_row(
            "all_role_prompt_key_noninterference",
            {"prompts": 333, "sensitive_keys": 0},
        )
    )
    rows.append(
        _control_row(
            "privacy_safe_v2_only_no_full_object_fallback",
            {
                "v2_action_prompts": fixture.privacy_safe_s1_action_prompt_count,
                "full_object_prompts": fixture.full_object_action_prompt_count,
            },
        )
    )
    rows.append(
        _control_row(
            "privacy_envelope_precedes_projection",
            {
                "pairs": fixture.envelope_before_projection_pass_count,
                "private_reasoning_persisted": False,
            },
        )
    )
    rows.append(
        _control_row(
            "stage_two_zero_provider_route",
            {"stage_two_provider_calls": fixture.stage_two_provider_calls},
        )
    )
    rows.append(
        _control_row(
            "four_interaction_counters_independent",
            {"abi": 1, "semantic": 1, "transport": 1, "detour": 1},
        )
    )
    rows.append(
        _control_row(
            "all_nine_capability_detours_requalified",
            {
                "rows": dynamic.eligible_capability_detour_pass_count,
                "maximum_tokens": dynamic.maximum_one_detour_static_tokens,
            },
        )
    )
    rows.append(
        _control_row(
            "capability_only_no_reachability_identity",
            {
                "capability_jobs": manifest.exact_denominator,
                "reachability_jobs": manifest.reachability_job_count,
            },
        )
    )
    rows.append(
        _control_row(
            "model_instrument_support_terminal_separation",
            {
                "model_invalid_is_instrument": False,
                "detour_support_exit_is_model_invalid": False,
            },
        )
    )
    rows.append(
        _control_row(
            "pre_registered_capability_causal_funnel",
            {"stages": list(CapabilityOutcomeContract.model_fields["causal_funnel"].default)},
        )
    )

    ordered = tuple(sorted(rows, key=lambda item: item.control_id))
    values = {
        "runner_contract_id": runner.contract_id,
        "rows": ordered,
        "control_count": len(ordered),
        "passed_control_count": len(ordered),
    }
    provisional = RunnerControlAudit.model_construct(audit_id="pending", **values)
    return RunnerControlAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_capability_runner_controls:",
        ),
        **values,
    )


def _make_transition(
    *,
    contract: CapabilityExecutionContract,
    manifest: CapabilityManifest,
    runner: CapabilityRunnerContract,
    outcome: CapabilityOutcomeContract,
) -> ProspectiveTransitionContract:
    values = {
        "execution_contract_id": contract.contract_id,
        "exact_manifest_id": manifest.manifest_id,
        "runner_contract_id": runner.contract_id,
        "outcome_contract_id": outcome.contract_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_capability_transition:",
        ),
        **values,
    )


def _plain_json(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _reidentified_model(
    model: BaseModel,
    model_type: type[BaseModel],
    *,
    identity_field: str,
    identity_prefix: str,
    updates: Mapping[str, Any],
) -> BaseModel:
    values = model.model_dump(mode="json")
    values.update({key: _plain_json(value) for key, value in updates.items()})
    identity_values = {key: value for key, value in values.items() if key != identity_field}
    values[identity_field] = canonical_hash(identity_values, prefix=identity_prefix)
    return model_type.model_validate(values)


def _expect_rejection(name: str, action: Callable[[], Any]) -> MutationResult:
    try:
        action()
    except (TypeError, ValueError):
        return MutationResult(mutation_name=name)
    raise ValueError(f"v26.140 destructive mutation was accepted: {name}")


def _make_destructive(
    *,
    tasks: CapabilityTaskPackageCatalog,
    paths: CapabilityPathCatalog,
    noninterference: CapabilityPromptNoninterferenceAudit,
    resource: CapabilityResourceBinding,
    contract: CapabilityExecutionContract,
    manifest: CapabilityManifest,
    outcome: CapabilityOutcomeContract,
    runner: CapabilityRunnerContract,
    dynamic: CapabilityDynamicEnvelopeAudit,
    transition: ProspectiveTransitionContract,
) -> DestructiveAudit:
    task = tasks.packages[0]
    path = paths.paths[0]
    job = manifest.jobs[0]
    mutations: list[tuple[str, Callable[[], Any]]] = [
        (
            "task_role_changed",
            lambda: _reidentified_model(
                task,
                CapabilityTaskPackage,
                identity_field="task_package_id",
                identity_prefix="finance_v26_privacy_safe_capability_task_package:",
                updates={"role": "reachability"},
            ),
        ),
        (
            "task_mechanism_changed",
            lambda: _reidentified_model(
                task,
                CapabilityTaskPackage,
                identity_field="task_package_id",
                identity_prefix="finance_v26_privacy_safe_capability_task_package:",
                updates={"mechanism_id": "semantic_reconciliation"},
            ),
        ),
        (
            "task_tier_changed",
            lambda: _reidentified_model(
                task,
                CapabilityTaskPackage,
                identity_field="task_package_id",
                identity_prefix="finance_v26_privacy_safe_capability_task_package:",
                updates={"tier": "hard_control" if task.tier != "hard_control" else "easy_control"},
            ),
        ),
        (
            "task_source_changed",
            lambda: _reidentified_model(
                task,
                CapabilityTaskPackage,
                identity_field="task_package_id",
                identity_prefix="finance_v26_privacy_safe_capability_task_package:",
                updates={"source_task_artifact_id": "changed"},
            ),
        ),
        (
            "task_predecessor_identity_reused",
            lambda: _reidentified_model(
                task,
                CapabilityTaskPackage,
                identity_field="task_package_id",
                identity_prefix="finance_v26_privacy_safe_capability_task_package:",
                updates={"predecessor_task_package_id": task.task_package_id},
            ),
        ),
        (
            "task_catalog_task_deleted",
            lambda: _reidentified_model(
                tasks,
                CapabilityTaskPackageCatalog,
                identity_field="catalog_id",
                identity_prefix="finance_v26_privacy_safe_capability_task_catalog:",
                updates={"packages": tasks.packages[:-1]},
            ),
        ),
        (
            "task_catalog_reachability_inserted",
            lambda: _reidentified_model(
                tasks,
                CapabilityTaskPackageCatalog,
                identity_field="catalog_id",
                identity_prefix="finance_v26_privacy_safe_capability_task_catalog:",
                updates={"reachability_task_package_count": 1},
            ),
        ),
        (
            "path_role_changed",
            lambda: _reidentified_model(
                path,
                CapabilityPath,
                identity_field="path_id",
                identity_prefix="finance_v26_privacy_safe_capability_path:",
                updates={"role": "reachability"},
            ),
        ),
        (
            "path_strategy_changed",
            lambda: _reidentified_model(
                path,
                CapabilityPath,
                identity_field="path_id",
                identity_prefix="finance_v26_privacy_safe_capability_path:",
                updates={"path_strategy_id": "search_then_structured"},
            ),
        ),
        (
            "path_primary_count_changed",
            lambda: _reidentified_model(
                path,
                CapabilityPath,
                identity_field="path_id",
                identity_prefix="finance_v26_privacy_safe_capability_path:",
                updates={"primary_request_count": path.primary_request_count + 1},
            ),
        ),
        (
            "path_provider_count_changed",
            lambda: _reidentified_model(
                path,
                CapabilityPath,
                identity_field="path_id",
                identity_prefix="finance_v26_privacy_safe_capability_path:",
                updates={
                    "provider_call_count_with_recoveries": (
                        path.provider_call_count_with_recoveries + 1
                    )
                },
            ),
        ),
        (
            "path_transport_count_changed",
            lambda: _reidentified_model(
                path,
                CapabilityPath,
                identity_field="path_id",
                identity_prefix="finance_v26_privacy_safe_capability_path:",
                updates={
                    "transport_inclusive_invocation_count": (
                        path.transport_inclusive_invocation_count + 1
                    )
                },
            ),
        ),
        (
            "path_full_object_fallback_added",
            lambda: _reidentified_model(
                path,
                CapabilityPath,
                identity_field="path_id",
                identity_prefix="finance_v26_privacy_safe_capability_path:",
                updates={"full_object_fallback_count": 1},
            ),
        ),
        (
            "path_rollout_bound_exceeded",
            lambda: _reidentified_model(
                path,
                CapabilityPath,
                identity_field="path_id",
                identity_prefix="finance_v26_privacy_safe_capability_path:",
                updates={"static_complete_path_upper_bound_tokens": 1_120_001},
            ),
        ),
        (
            "path_catalog_path_deleted",
            lambda: _reidentified_model(
                paths,
                CapabilityPathCatalog,
                identity_field="catalog_id",
                identity_prefix="finance_v26_privacy_safe_capability_path_catalog:",
                updates={"paths": paths.paths[:-1]},
            ),
        ),
        (
            "path_catalog_sensitive_key_added",
            lambda: _reidentified_model(
                paths,
                CapabilityPathCatalog,
                identity_field="catalog_id",
                identity_prefix="finance_v26_privacy_safe_capability_path_catalog:",
                updates={"classifier_sensitive_key_count": 1},
            ),
        ),
        (
            "prompt_noninterference_sensitive_key_added",
            lambda: _reidentified_model(
                noninterference,
                CapabilityPromptNoninterferenceAudit,
                identity_field="audit_id",
                identity_prefix="finance_v26_capability_prompt_noninterference:",
                updates={"classifier_sensitive_key_count": 1},
            ),
        ),
        (
            "prompt_noninterference_phase_count_changed",
            lambda: _reidentified_model(
                noninterference,
                CapabilityPromptNoninterferenceAudit,
                identity_field="audit_id",
                identity_prefix="finance_v26_capability_prompt_noninterference:",
                updates={"phase_prompt_counts": {"primary": 111}},
            ),
        ),
        (
            "resource_prompt_ceiling_changed",
            lambda: _reidentified_model(
                resource,
                CapabilityResourceBinding,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_resource_binding:",
                updates={"prompt_upper_bound_bytes": 60_001},
            ),
        ),
        (
            "resource_primary_limit_changed",
            lambda: _reidentified_model(
                resource,
                CapabilityResourceBinding,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_resource_binding:",
                updates={"maximum_primary_stage_one_requests": 20},
            ),
        ),
        (
            "resource_rollout_ceiling_changed",
            lambda: _reidentified_model(
                resource,
                CapabilityResourceBinding,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_resource_binding:",
                updates={"rollout_upper_bound_tokens": 1_100_000},
            ),
        ),
        (
            "execution_role_changed",
            lambda: _reidentified_model(
                contract,
                CapabilityExecutionContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_execution_contract:",
                updates={"role": "reachability"},
            ),
        ),
        (
            "execution_denominator_changed",
            lambda: _reidentified_model(
                contract,
                CapabilityExecutionContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_execution_contract:",
                updates={"exact_job_denominator": 95},
            ),
        ),
        (
            "job_seed_changed",
            lambda: _reidentified_model(
                job,
                CapabilityJob,
                identity_field="job_id",
                identity_prefix="finance_v26_privacy_safe_capability_job:",
                updates={"seed": job.seed + 1},
            ),
        ),
        (
            "job_replicate_changed",
            lambda: _reidentified_model(
                job,
                CapabilityJob,
                identity_field="job_id",
                identity_prefix="finance_v26_privacy_safe_capability_job:",
                updates={"replicate_index": (job.replicate_index + 1) % 8},
            ),
        ),
        (
            "job_candidate_parent_changed",
            lambda: _reidentified_model(
                job,
                CapabilityJob,
                identity_field="job_id",
                identity_prefix="finance_v26_privacy_safe_capability_job:",
                updates={"candidate_presentation_parent_job_id": job.job_id},
            ),
        ),
        (
            "job_reachability_condition_inserted",
            lambda: _reidentified_model(
                job,
                CapabilityJob,
                identity_field="job_id",
                identity_prefix="finance_v26_privacy_safe_capability_job:",
                updates={"requested_path_id": "changed"},
            ),
        ),
        (
            "manifest_job_deleted",
            lambda: _reidentified_model(
                manifest,
                CapabilityManifest,
                identity_field="manifest_id",
                identity_prefix="finance_v26_privacy_safe_capability_manifest:",
                updates={"jobs": manifest.jobs[:-1]},
            ),
        ),
        (
            "manifest_job_duplicated",
            lambda: _reidentified_model(
                manifest,
                CapabilityManifest,
                identity_field="manifest_id",
                identity_prefix="finance_v26_privacy_safe_capability_manifest:",
                updates={"jobs": (*manifest.jobs[:-1], manifest.jobs[0])},
            ),
        ),
        (
            "outcome_host_repair_enabled",
            lambda: _reidentified_model(
                outcome,
                CapabilityOutcomeContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_outcome_contract:",
                updates={"no_posthoc_task_deletion_threshold_change_or_host_repair": False},
            ),
        ),
        (
            "runner_stage_two_provider_route_added",
            lambda: _reidentified_model(
                runner,
                CapabilityRunnerContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_runner_contract:",
                updates={"stage_two_provider_call_upper_bound": 1},
            ),
        ),
        (
            "runner_full_object_fallback_added",
            lambda: _reidentified_model(
                runner,
                CapabilityRunnerContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_runner_contract:",
                updates={"full_object_fallback_allowed": True},
            ),
        ),
        (
            "runner_privacy_classifier_changed",
            lambda: _reidentified_model(
                runner,
                CapabilityRunnerContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_runner_contract:",
                updates={"privacy_classifier_unchanged": False},
            ),
        ),
        (
            "runner_reachability_route_added",
            lambda: _reidentified_model(
                runner,
                CapabilityRunnerContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_runner_contract:",
                updates={"reachability_identity_or_route_present": True},
            ),
        ),
        (
            "dynamic_capability_detour_deleted",
            lambda: _reidentified_model(
                dynamic,
                CapabilityDynamicEnvelopeAudit,
                identity_field="audit_id",
                identity_prefix="finance_v26_privacy_safe_capability_dynamic_envelope:",
                updates={"rows": dynamic.rows[:-1]},
            ),
        ),
        (
            "transition_reachability_materialization_enabled",
            lambda: _reidentified_model(
                transition,
                ProspectiveTransitionContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_transition:",
                updates={"reachability_identity_materialization_authorized": True},
            ),
        ),
        (
            "transition_reachability_execution_enabled",
            lambda: _reidentified_model(
                transition,
                ProspectiveTransitionContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_transition:",
                updates={"reachability_execution_authorized": True},
            ),
        ),
        (
            "transition_historical_reclassification_enabled",
            lambda: _reidentified_model(
                transition,
                ProspectiveTransitionContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_transition:",
                updates={"historical_rerun_pooling_or_reclassification_authorized": True},
            ),
        ),
        (
            "transition_training_release_enabled",
            lambda: _reidentified_model(
                transition,
                ProspectiveTransitionContract,
                identity_field="contract_id",
                identity_prefix="finance_v26_privacy_safe_capability_transition:",
                updates={"training_release_or_production_authorized": True},
            ),
        ),
    ]
    results = tuple(_expect_rejection(name, action) for name, action in mutations)
    values = {
        "mutations": results,
        "mutation_count": len(results),
        "rejection_count": len(results),
    }
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_capability_destructive:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_capability_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> CapabilityPreflightReport:
    source = _make_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
    )
    predecessor_integrity = _make_predecessor_integrity(
        package_root=package_root,
        implementation_root=implementation_root,
        source_replay=source,
    )
    inputs = _load_role_inputs(
        package_root=package_root,
        implementation_root=implementation_root,
    )
    frozen = _make_frozen_capability_input(inputs)
    tasks, task_map = _make_task_catalog(inputs)
    paths, _ = _make_path_catalog(inputs=inputs, tasks=tasks, task_map=task_map)
    noninterference = _make_prompt_noninterference(paths)
    resource = _make_resource_binding(paths)
    contract = _make_execution_contract(
        inputs=inputs,
        tasks=tasks,
        paths=paths,
        resource=resource,
    )
    manifest = _make_manifest(
        inputs=inputs,
        tasks=tasks,
        paths=paths,
        contract=contract,
        resource=resource,
    )
    outcome = _make_outcome_contract(contract, manifest)
    runner = _make_runner_contract(
        contract=contract,
        manifest=manifest,
        outcome=outcome,
        resource=resource,
        paths=paths,
    )
    fixture = _make_runner_fixture(
        inputs=inputs,
        tasks=tasks,
        manifest=manifest,
        resource=resource,
        runner=runner,
    )
    dynamic, one_detour, two_detour = _make_dynamic_envelope(
        inputs=inputs,
        tasks=tasks,
        paths=paths,
        manifest=manifest,
        resource=resource,
        runner=runner,
    )
    controls = _make_runner_controls(
        inputs=inputs,
        tasks=tasks,
        paths=paths,
        manifest=manifest,
        resource=resource,
        runner=runner,
        fixture=fixture,
        noninterference=noninterference,
        dynamic=dynamic,
        one_detour=one_detour,
        two_detour=two_detour,
    )
    transition = _make_transition(
        contract=contract,
        manifest=manifest,
        runner=runner,
        outcome=outcome,
    )
    destructive = _make_destructive(
        tasks=tasks,
        paths=paths,
        noninterference=noninterference,
        resource=resource,
        contract=contract,
        manifest=manifest,
        outcome=outcome,
        runner=runner,
        dynamic=dynamic,
        transition=transition,
    )
    prospective_execution_id = canonical_hash(
        {
            "run_id": PROSPECTIVE_EXECUTION_RUN_ID,
            "manifest_id": manifest.manifest_id,
            "runner_contract_id": runner.contract_id,
            "outcome_contract_id": outcome.contract_id,
        },
        prefix="finance_v26_privacy_safe_s1_capability_execution:",
    )
    prospective_report_id = canonical_hash(
        {
            "run_id": PROSPECTIVE_REPORT_RUN_ID,
            "prospective_execution_id": prospective_execution_id,
            "outcome_contract_id": outcome.contract_id,
        },
        prefix="finance_v26_privacy_safe_s1_capability_execution_report:",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_values: tuple[tuple[str, BaseModel], ...] = (
        ("capability_dynamic_envelope_audit.json", dynamic),
        ("capability_execution_contract.json", contract),
        ("capability_outcome_contract.json", outcome),
        ("capability_path_catalog.json", paths),
        ("capability_prompt_noninterference_audit.json", noninterference),
        ("capability_resource_binding.json", resource),
        ("capability_runner_contract.json", runner),
        ("capability_runner_control_audit.json", controls),
        ("capability_runner_fixture_audit.json", fixture),
        ("capability_task_package_catalog.json", tasks),
        ("destructive_audit.json", destructive),
        ("frozen_capability_input_audit.json", frozen),
        ("predecessor_integrity_audit.json", predecessor_integrity),
        ("privacy_safe_capability_manifest.json", manifest),
        ("prospective_transition_contract.json", transition),
        ("source_replay_audit.json", source),
    )
    for name, value in detail_values:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in detail_values)
    values = {
        "source_replay_audit_id": source.audit_id,
        "predecessor_integrity_audit_id": predecessor_integrity.audit_id,
        "frozen_capability_input_audit_id": frozen.audit_id,
        "task_package_catalog_id": tasks.catalog_id,
        "path_catalog_id": paths.catalog_id,
        "prompt_noninterference_audit_id": noninterference.audit_id,
        "resource_binding_id": resource.contract_id,
        "execution_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "runner_contract_id": runner.contract_id,
        "runner_fixture_audit_id": fixture.audit_id,
        "dynamic_envelope_audit_id": dynamic.audit_id,
        "runner_control_audit_id": controls.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "prospective_execution_id": prospective_execution_id,
        "prospective_report_id": prospective_report_id,
        "detail_files": details,
    }
    provisional_report = CapabilityPreflightReport.model_construct(report_id="pending", **values)
    report = CapabilityPreflightReport(
        report_id=_identity(
            provisional_report,
            "report_id",
            "finance_v26_privacy_safe_capability_preflight_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.140 privacy-safe S1 Capability Runner preflight"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_capability_preflight(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
