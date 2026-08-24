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
    phase1_v26_final_grammar_privacy_rematerialization as engineering_static,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_execution as privacy_runner,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_privacy_compatibility_root_cause_audit as predecessor,
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
from trusted_synthesis.runtime.agent import (
    prospective_semantic_action_response_grammar as action_grammar,
)
from trusted_synthesis.runtime.agent.compact_budget_prompt import render_compact_final_prompt
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    FinalResponseHostEnvelope,
    make_final_response_host_envelope,
    render_exact_final_primary_prompt,
    render_exact_final_rescue_prompt,
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

RUN_ID: Final = "finance_v26_137_s1_privacy_safe_prompt_runner_preflight_v1_20260824"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_137_s1_privacy_safe_prompt_runner_preflight_v1_20260824"
)
IMPLEMENTATION_PATH: Final = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_s1_privacy_safe_prompt_runner_preflight.py"
)
PREDECESSOR_DIR: Final = predecessor.OUTPUT_DIR
QUALIFICATION_PREFLIGHT_DIR: Final = runner_base.OUTPUT_DIR
EXECUTION_DIR: Final = predecessor.EXECUTION_DIR
POSTRUN_DIR: Final = predecessor.POSTRUN_DIR
NEXT_STAGE: Final = "privacy_safe_s1_representation_qualification_execution_only"
PROSPECTIVE_RUNNER_RUN_ID: Final = (
    "finance_v26_137_privacy_safe_s1_qualification_runner_v1_20260824"
)
PROSPECTIVE_EXECUTION_RUN_ID: Final = (
    "finance_v26_138_privacy_safe_s1_qualification_execution_v1_20260824"
)
PROSPECTIVE_REPORT_RUN_ID: Final = (
    "finance_v26_138_privacy_safe_s1_qualification_execution_report_v1_20260824"
)

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_s1_privacy_root_cause_audit_report:"
    "5ac66c4c25b021406c49628c67aa06b6aa776c59550810d8cc7c9e06e1451b65"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "282de86de46d76073e115af7fa5e1e772f59532bb4c3d08f0d68b95922907bfb"
)
EXPECTED_PREDECESSOR_SOURCE_ID: Final = (
    "finance_v26_s1_root_cause_source_replay:"
    "73b74723dbe69790539112ad00f66db5574f3774ed0ca90c7146663a79386352"
)
EXPECTED_PREDECESSOR_CLASSIFIER_ID: Final = (
    "finance_v26_privacy_classifier_type_system_audit:"
    "32f846dc58a1675fd1aeaf309ff6c152c9ad974674d6f5d513e35b573043039b"
)
EXPECTED_PREDECESSOR_GRAMMAR_ID: Final = (
    "finance_v26_action_grammar_privacy_compatibility:"
    "3fb0a2947cd134fc1ae212a4136bbbfe6b83bf4143f5079f764aa80aefdcbe4a"
)
EXPECTED_PREDECESSOR_PROMPT_ID: Final = (
    "finance_v26_s1_prompt_privacy_compatibility:"
    "75867629bcee4ff4f86ed6072b1faac379759559e015a510bf467aa14d25f1af"
)
EXPECTED_PREDECESSOR_GATE_ID: Final = (
    "finance_v26_s1_qualification_gate_decomposition:"
    "bd47399403171f962acd6fcbb09af4bdb8d3480aacf6f2cf7bb4564fee995ac3"
)
EXPECTED_PREDECESSOR_DECISION_ID: Final = (
    "finance_v26_s1_privacy_root_cause_decision:"
    "60054e8f265c13fb3f056403e3f053299a7dfc75f77720b178301f70634a4792"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_s1_privacy_root_cause_transition:"
    "a8ebfd89e76d2717c58577d6e08286b737ccd18b961832abad09ced217077b74"
)
EXPECTED_QUALIFICATION_REPORT_ID: Final = (
    "finance_v26_s1_qualification_preflight_report:"
    "9d79af8e43b93f768d615be5aa1ca22ac2f733b5171fb191b87b4f0bf1785c4a"
)
EXPECTED_QUALIFICATION_PATH_CATALOG_ID: Final = (
    "finance_v26_s1_qualification_path_catalog:"
    "48e21b62dc6be94a204980ccbfa186fad0f3087a8f92f37ee8b3c26856039026"
)
EXPECTED_QUALIFICATION_RESOURCE_ID: Final = (
    "finance_v26_s1_qualification_resource_contract:"
    "9ba3c63a1c7cfebe6a954eda18e0cd6e3414fcc2fc17a2ac0c95e6e7a199fba6"
)
EXPECTED_QUALIFICATION_MANIFEST_ID: Final = (
    "finance_v26_s1_qualification_manifest:"
    "75dd0c9a5e705225bf02063a8ab18cfaaefcc19df62a1c26b2b8c783a83e99eb"
)
EXPECTED_QUALIFICATION_RUNNER_ID: Final = (
    "finance_v26_s1_qualification_runner_contract:"
    "1aca524bc565c1157f876ad55d2f469c516dd1ff85308cf9719029f914cd750c"
)

PREDECESSOR_OUTPUT_NAMES: Final = (
    "accepted_entry_boundary_audit.json",
    "action_grammar_privacy_compatibility_audit.json",
    "destructive_audit.json",
    "privacy_classifier_type_system_audit.json",
    "prompt_privacy_compatibility_audit.json",
    "prospective_transition_contract.json",
    "qualification_gate_decomposition_audit.json",
    "root_cause_decision.json",
    "source_replay_audit.json",
    "report.json",
)
OLD_SENSITIVE_KEY_PATHS: Final = predecessor.SENSITIVE_PROMPT_KEY_PATHS
SAFE_REPLACEMENT_KEY_PATHS: Final = (
    "hidden_model_content_reused",
    "response_grammar.hidden_model_content",
)
PRIVACY_SAFE_PROMPT_PROTOCOL: Final = "prospective_role_scalable_semantic_action_prompt.v2"
PRIVACY_INSTRUCTION: Final = (
    "Do not include or reuse private chain-of-thought or hidden reasoning in the public JSON "
    "response."
)
PROMPT_PHASES: Final = ("primary", "abi_rescue", "semantic_recovery")
PROMPT_PREFIXES: Final = {
    "primary": "Select one visible action and return exactly one four-field JSON object.",
    "abi_rescue": "Correct only the response ABI and return exactly one four-field JSON object.",
    "semantic_recovery": (
        "Use the public rejection and select one visible action as a four-field JSON object."
    ),
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    raise ValueError(f"v26.137 cannot replay bound file: {relative_path}")


def _sensitive_key_paths(value: Any, path: tuple[str, ...] = ()) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            next_path = path + (str(key),)
            normalized = str(key).casefold()
            if "reasoning" in normalized and normalized not in predecessor.CLASSIFIER_WHITELIST:
                found.append(".".join(next_path))
            found.extend(_sensitive_key_paths(item, next_path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_sensitive_key_paths(item, path + (f"[{index}]",)))
    return tuple(found)


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_136_transitive_source",
        "v26_136_output",
        "v26_137_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_source_replay_id: str = EXPECTED_PREDECESSOR_SOURCE_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_file_count: Literal[3873] = 3873
    predecessor_output_file_count: Literal[10] = 10
    implementation_file_count: Literal[1] = 1
    replayed_file_count: Literal[3884] = 3884
    replay_pass_count: Literal[3884] = 3884
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=3884, max_length=3884)
    replay_before_prompt_or_runner_construction: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_privacy_safe_s1_source_replay.v1"] = (
        "finance_v26_privacy_safe_s1_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
            or len(paths) != self.replayed_file_count
        ):
            raise ValueError("v26.137 source replay changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_safe_s1_source_replay:"
        ):
            raise ValueError("v26.137 source replay identity changed")
        return self


class PredecessorIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_rebuild_file_count: Literal[10] = 10
    predecessor_rebuild_byte_match_count: Literal[10] = 10
    formal_qualification_remains_failed: Literal[True] = True
    historical_privacy_rejected_job_count: Literal[1] = 1
    historical_accepted_entry_count: Literal[31] = 31
    historical_instrument_integrity_call_count: Literal[197] = 197
    historical_rejected_payload_or_key_recovered_or_inferred: Literal[False] = False
    historical_row_or_gate_reclassified: Literal[False] = False
    role_source_model_exposure_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_predecessor_integrity.v1"] = (
        "finance_v26_privacy_safe_s1_predecessor_integrity.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_safe_s1_predecessor_integrity:"
        ):
            raise ValueError("v26.137 predecessor-integrity identity changed")
        return self


class MetadataRename(FrozenModel):
    old_key_path: str = Field(min_length=1)
    new_key_path: str = Field(min_length=1)
    host_internal_field_retained: Literal[True] = True
    model_visible_old_key_removed: Literal[True] = True
    privacy_prohibition_semantics_preserved: Literal[True] = True

    @model_validator(mode="after")
    def validate_rename(self) -> MetadataRename:
        if "reasoning" in self.new_key_path.casefold():
            raise ValueError("v26.137 replacement Key remains classifier-sensitive")
        return self


class PrivacySafePromptMetadataContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_root_cause_decision_id: str = EXPECTED_PREDECESSOR_DECISION_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_prompt_audit_id: str = EXPECTED_PREDECESSOR_PROMPT_ID
    predecessor_classifier_audit_id: str = EXPECTED_PREDECESSOR_CLASSIFIER_ID
    predecessor_grammar_compatibility_audit_id: str = EXPECTED_PREDECESSOR_GRAMMAR_ID
    prompt_protocol: str = PRIVACY_SAFE_PROMPT_PROTOCOL
    action_grammar_id: str = runner_base.EXPECTED_ACTION_GRAMMAR_ID
    compact_projection_protocol_id: str = runner_base.EXPECTED_COMPACT_PROTOCOL_ID
    s1_candidate_id: str = runner_base.EXPECTED_S1_CANDIDATE_ID
    classifier_matching_rule: Literal["casefolded_mapping_key_substring_reasoning"] = (
        "casefolded_mapping_key_substring_reasoning"
    )
    classifier_scans_mapping_keys: Literal[True] = True
    classifier_scans_scalar_values: Literal[False] = False
    metadata_renames: tuple[MetadataRename, MetadataRename]
    privacy_instruction_scalar_value: str = PRIVACY_INSTRUCTION
    model_visible_prompt_strong_schema: Literal[True] = True
    host_internal_private_reasoning_fields_retained: Literal[True] = True
    classifier_changed: Literal[False] = False
    action_grammar_changed: Literal[False] = False
    candidate_or_s1_changed: Literal[False] = False
    only_authorized_model_visible_differences: tuple[str, ...] = (
        "prompt_protocol_value",
        "private_reasoning_reused_to_hidden_model_content_reused",
        "response_grammar.private_reasoning_content_to_hidden_model_content",
    )
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_prompt_metadata_contract.v1"] = (
        "finance_v26_privacy_safe_prompt_metadata_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> PrivacySafePromptMetadataContract:
        observed = tuple((item.old_key_path, item.new_key_path) for item in self.metadata_renames)
        if observed != tuple(zip(OLD_SENSITIVE_KEY_PATHS, SAFE_REPLACEMENT_KEY_PATHS, strict=True)):
            raise ValueError("v26.137 metadata rename set changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_prompt_metadata_contract:"
        ):
            raise ValueError("v26.137 Prompt metadata Contract identity changed")
        return self


class PrivacySafeVisibleGrammar(FrozenModel):
    id: str = Field(min_length=1)
    fields: tuple[str, str, str, str]
    types: tuple[str, str, str, str]
    shape_rules: tuple[str, ...]
    state_id_rule: str = Field(min_length=1)
    action_id_rule: str = Field(min_length=1)
    decision_kind_rule: str = Field(min_length=1)
    protocol_constant: str = Field(min_length=1)
    fixed_stage: Literal["host_bound_not_model_generated"] = "host_bound_not_model_generated"
    host_rules: tuple[str, ...]
    hidden_model_content: str = PRIVACY_INSTRUCTION


class PrivacySafePromptEnvelope(FrozenModel):
    prompt_protocol: str = Field(min_length=1)
    semantic_action_protocol: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    public_path_condition: str | None
    compact_public_state: dict[str, Any]
    visible_action_candidates: dict[str, Any]
    candidate_presentation: dict[str, Any]
    typed_failure: dict[str, Any] | None
    response_grammar: PrivacySafeVisibleGrammar
    lossless_projection_contract: dict[str, Any]
    previous_response_content_reused: Literal[False] = False
    hidden_model_content_reused: Literal[False] = False

    @model_validator(mode="after")
    def validate_envelope(self) -> PrivacySafePromptEnvelope:
        dumped = self.model_dump(mode="json")
        if _sensitive_key_paths(dumped):
            raise ValueError("v26.137 Prompt strong Schema contains a classifier-sensitive Key")
        if self.response_grammar.id != runner_base.EXPECTED_ACTION_GRAMMAR_ID:
            raise ValueError("v26.137 Prompt strong Schema changed Action Grammar")
        if self.response_grammar.hidden_model_content != PRIVACY_INSTRUCTION:
            raise ValueError("v26.137 Prompt strong Schema weakened the privacy instruction")
        return self


class PromptBindingRow(FrozenModel):
    row_id: str = Field(min_length=1)
    predecessor_state_binding_id: str = Field(min_length=1)
    logical_state_index: int = Field(ge=0)
    state_id: str = Field(min_length=1)
    candidate_count: int = Field(gt=0)
    presented_action_ids: tuple[str, ...] = Field(min_length=1)
    predecessor_prompt_sha256s: dict[str, str]
    privacy_safe_prompt_sha256s: dict[str, str]
    predecessor_prompt_utf8_bytes: dict[str, int]
    privacy_safe_prompt_utf8_bytes: dict[str, int]
    reference_action_id: str = Field(min_length=1)
    reference_decision_kind: str = Field(min_length=1)
    reversible_commit_id: str = Field(min_length=1)
    privacy_safe_prompt_hash_changed_count: Literal[3] = 3
    classifier_sensitive_key_count: Literal[0] = 0
    full_prompt_payload_echo_privacy_accepted_count: Literal[3] = 3
    intended_action_payload_privacy_accepted_count: Literal[3] = 3
    exact_state_reconstruction_count: Literal[3] = 3
    exact_candidate_set_and_order_count: Literal[3] = 3
    exact_reference_proposal_count: Literal[3] = 3
    exact_stage_two_commit_count: Literal[3] = 3
    authorized_difference_only_count: Literal[3] = 3

    @model_validator(mode="after")
    def validate_row(self) -> PromptBindingRow:
        if (
            tuple(sorted(self.predecessor_prompt_sha256s)) != tuple(sorted(PROMPT_PHASES))
            or tuple(sorted(self.privacy_safe_prompt_sha256s)) != tuple(sorted(PROMPT_PHASES))
            or any(
                self.predecessor_prompt_sha256s[phase] == self.privacy_safe_prompt_sha256s[phase]
                for phase in PROMPT_PHASES
            )
            or len(self.presented_action_ids) != self.candidate_count
        ):
            raise ValueError("v26.137 Prompt binding row changed")
        if self.row_id != _identity(self, "row_id", "finance_v26_privacy_safe_s1_prompt_binding:"):
            raise ValueError("v26.137 Prompt binding identity changed")
        return self


class PrivacySafeTaskPackage(FrozenModel):
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    source_role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    operational_record_id: str = Field(min_length=1)
    operational_task_package_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = Field(min_length=1)
    prompt_protocol: str = PRIVACY_SAFE_PROMPT_PROTOCOL
    stage_one_profile_id: str = runner_base.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = runner_base.EXPECTED_STAGE_TWO_PROFILE_ID
    thinking_type: Literal["enabled"] = "enabled"
    semantic_action_protocol_id: str = runner_base.EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = runner_base.EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = runner_base.EXPECTED_FINAL_GRAMMAR_ID
    compact_projection_protocol_id: str = runner_base.EXPECTED_COMPACT_PROTOCOL_ID
    s1_candidate_id: str = runner_base.EXPECTED_S1_CANDIDATE_ID
    source_model_exposed_before_freeze: Literal[True] = True
    engineering_qualification_only: Literal[True] = True
    role_or_state_eligible: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_safe_s1_task_package.v1"] = (
        "finance_v26_privacy_safe_s1_task_package.v1"
    )

    @model_validator(mode="after")
    def validate_package(self) -> PrivacySafeTaskPackage:
        if self.task_package_id == self.predecessor_task_package_id:
            raise ValueError("v26.137 TaskPackage reused a predecessor identity")
        if self.task_package_id != _identity(
            self, "task_package_id", "finance_v26_privacy_safe_s1_task_package:"
        ):
            raise ValueError("v26.137 TaskPackage identity changed")
        return self


class PrivacySafeTaskPackageCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = Field(min_length=1)
    packages: tuple[PrivacySafeTaskPackage, ...] = Field(min_length=24, max_length=24)
    task_package_count: Literal[24] = 24
    distinct_source_task_count: Literal[24] = 24
    predecessor_identity_overlap_count: Literal[0] = 0
    role_source_task_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_task_package_catalog.v1"] = (
        "finance_v26_privacy_safe_s1_task_package_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> PrivacySafeTaskPackageCatalog:
        if (
            len(self.packages) != self.task_package_count
            or len({item.task_package_id for item in self.packages}) != self.task_package_count
            or len({item.source_task_artifact_id for item in self.packages})
            != self.distinct_source_task_count
        ):
            raise ValueError("v26.137 TaskPackage denominator changed")
        if self.catalog_id != _identity(
            self, "catalog_id", "finance_v26_privacy_safe_s1_task_package_catalog:"
        ):
            raise ValueError("v26.137 TaskPackage Catalog identity changed")
        return self


class PrivacySafePath(FrozenModel):
    path_id: str = Field(min_length=1)
    predecessor_path_id: str = Field(min_length=1)
    source_engineering_path_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    source_role: Literal["capability", "reachability"]
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: Literal["structured_direct", "search_then_structured", "search_then_open"]
    prompt_metadata_contract_id: str = Field(min_length=1)
    prompt_rows: tuple[PromptBindingRow, ...] = Field(min_length=1)
    final_primary_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_rescue_prompt_sha256: str = Field(min_length=64, max_length=64)
    final_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    final_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    primary_request_count: int = Field(gt=0, le=21)
    provider_call_count_with_recoveries: int = Field(gt=0, le=23)
    transport_inclusive_invocation_count: int = Field(gt=0, le=24)
    static_complete_path_upper_bound_tokens: int = Field(gt=0, le=1120000)
    program_closed: Literal[True] = True
    terminal_verification_completed: Literal[True] = True
    final_commit_reached: Literal[True] = True
    role_evidence_eligible: Literal[False] = False

    @model_validator(mode="after")
    def validate_path(self) -> PrivacySafePath:
        if (
            self.path_id == self.predecessor_path_id
            or self.primary_request_count != len(self.prompt_rows) + 1
            or self.provider_call_count_with_recoveries != self.primary_request_count + 2
            or self.transport_inclusive_invocation_count
            != self.provider_call_count_with_recoveries + 1
        ):
            raise ValueError("v26.137 Path identity or accounting changed")
        if self.path_id != _identity(self, "path_id", "finance_v26_privacy_safe_s1_path:"):
            raise ValueError("v26.137 Path identity changed")
        return self


class PrivacySafePathCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    predecessor_path_catalog_id: str = EXPECTED_QUALIFICATION_PATH_CATALOG_ID
    paths: tuple[PrivacySafePath, ...] = Field(min_length=48, max_length=48)
    path_count: Literal[48] = 48
    state_count: Literal[324] = 324
    regenerated_prompt_count: Literal[972] = 972
    prompt_hash_changed_count: Literal[972] = 972
    classifier_sensitive_key_count: Literal[0] = 0
    prompt_echo_privacy_accept_count: Literal[972] = 972
    state_candidate_reference_commit_preservation_count: Literal[972] = 972
    maximum_action_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_action_abi_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_semantic_recovery_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_final_primary_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_final_rescue_prompt_utf8_bytes: int = Field(gt=0, le=60000)
    maximum_registered_path_static_tokens: int = Field(gt=0, le=1120000)
    full_object_fallback_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_path_catalog.v1"] = (
        "finance_v26_privacy_safe_s1_path_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> PrivacySafePathCatalog:
        rows = tuple(row for path in self.paths for row in path.prompt_rows)
        if (
            len(self.paths) != self.path_count
            or len({item.path_id for item in self.paths}) != self.path_count
            or len(rows) != self.state_count
            or sum(item.privacy_safe_prompt_hash_changed_count for item in rows)
            != self.prompt_hash_changed_count
        ):
            raise ValueError("v26.137 Path Catalog denominator changed")
        if self.catalog_id != _identity(
            self, "catalog_id", "finance_v26_privacy_safe_s1_path_catalog:"
        ):
            raise ValueError("v26.137 Path Catalog identity changed")
        return self


class PromptPrivacyNoninterferenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    predecessor_prompt_audit_id: str = EXPECTED_PREDECESSOR_PROMPT_ID
    predecessor_classifier_audit_id: str = EXPECTED_PREDECESSOR_CLASSIFIER_ID
    exact_action_grammar_id: str = runner_base.EXPECTED_ACTION_GRAMMAR_ID
    registered_state_count: Literal[324] = 324
    phase_prompt_counts: dict[str, int] = {
        "abi_rescue": 324,
        "primary": 324,
        "semantic_recovery": 324,
    }
    regenerated_prompt_count: Literal[972] = 972
    predecessor_sensitive_key_occurrence_count: Literal[1944] = 1944
    privacy_safe_sensitive_key_occurrence_count: Literal[0] = 0
    privacy_safe_prompts_with_sensitive_key_count: Literal[0] = 0
    predecessor_prompt_echo_privacy_rejection_count: Literal[972] = 972
    privacy_safe_prompt_echo_privacy_rejection_count: Literal[0] = 0
    privacy_safe_prompt_echo_privacy_accept_count: Literal[972] = 972
    intended_action_payload_grammar_pass_count: Literal[972] = 972
    intended_action_payload_privacy_pass_count: Literal[972] = 972
    synthetic_forbidden_reasoning_key_privacy_rejection_count: Literal[24] = 24
    predecessor_classifier_case_count: Literal[24] = 24
    predecessor_classifier_case_pass_count: Literal[24] = 24
    exact_state_reconstruction_count: Literal[972] = 972
    exact_candidate_set_and_order_count: Literal[972] = 972
    exact_reference_proposal_count: Literal[972] = 972
    exact_stage_two_commit_count: Literal[972] = 972
    authorized_difference_only_count: Literal[972] = 972
    prompt_hash_changed_count: Literal[972] = 972
    privacy_prohibition_instruction_count: Literal[972] = 972
    host_internal_private_reasoning_fields_retained: Literal[True] = True
    classifier_unchanged: Literal[True] = True
    action_grammar_unchanged: Literal[True] = True
    candidate_s1_stage_two_unchanged: Literal[True] = True
    historical_rejection_cause_identified: Literal[False] = False
    historical_rejected_payload_or_key_inferred: Literal[False] = False
    provider_calls: Literal[0] = 0
    status: Literal["prompt_output_key_namespace_noninterference_passed"] = (
        "prompt_output_key_namespace_noninterference_passed"
    )
    schema_version: Literal["finance_v26_prompt_privacy_noninterference_audit.v1"] = (
        "finance_v26_prompt_privacy_noninterference_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PromptPrivacyNoninterferenceAudit:
        if (
            sum(self.phase_prompt_counts.values()) != self.regenerated_prompt_count
            or self.privacy_safe_sensitive_key_occurrence_count
            or self.privacy_safe_prompt_echo_privacy_rejection_count
            or self.privacy_safe_prompt_echo_privacy_accept_count != self.regenerated_prompt_count
        ):
            raise ValueError("v26.137 Prompt/privacy noninterference changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_prompt_privacy_noninterference_audit:"
        ):
            raise ValueError("v26.137 noninterference identity changed")
        return self


class PrivacySafeResourceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_resource_contract_id: str = EXPECTED_QUALIFICATION_RESOURCE_ID
    prompt_metadata_contract_id: str = Field(min_length=1)
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
    resource_bound_values_changed: Literal[False] = False
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_safe_s1_resource_contract.v1"] = (
        "finance_v26_privacy_safe_s1_resource_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> PrivacySafeResourceContract:
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
            raise ValueError("v26.137 resource arithmetic changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_s1_resource_contract:"
        ):
            raise ValueError("v26.137 Resource Contract identity changed")
        return self


class PrivacySafeQualificationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_root_cause_decision_id: str = EXPECTED_PREDECESSOR_DECISION_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    prompt_metadata_contract_id: str = Field(min_length=1)
    noninterference_audit_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    task_package_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    path_ids: tuple[str, ...] = Field(min_length=48, max_length=48)
    qualification_object: Literal["privacy_safe_flash_model_visible_s1_usability"] = (
        "privacy_safe_flash_model_visible_s1_usability"
    )
    exact_job_denominator: Literal[32] = 32
    engineering_task_count: Literal[24] = 24
    engineering_path_count: Literal[48] = 48
    static_state_count: Literal[324] = 324
    first_action_interface_minimum_jobs: Literal[24] = 24
    required_mechanism_path_cell_coverage: Literal[12] = 12
    instrument_privacy_model_thinking_or_usage_failure_tolerance: Literal[0] = 0
    privacy_gate_is_noncompensatory: Literal[True] = True
    prior_31_of_32_entry_result_not_pooled: Literal[True] = True
    prior_formal_qualification_failure_retained: Literal[True] = True
    historical_rejected_row_remains_privacy_rejected: Literal[True] = True
    full_object_fallback_authorized: Literal[False] = False
    role_source_provider_exposure_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_safe_s1_qualification_contract.v1"] = (
        "finance_v26_privacy_safe_s1_qualification_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> PrivacySafeQualificationContract:
        if (
            len(set(self.task_package_ids)) != self.engineering_task_count
            or len(set(self.path_ids)) != self.engineering_path_count
            or self.first_action_interface_minimum_jobs != 24
            or self.required_mechanism_path_cell_coverage != 12
        ):
            raise ValueError("v26.137 Qualification Contract denominator changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_s1_qualification_contract:"
        ):
            raise ValueError("v26.137 Qualification Contract identity changed")
        return self


class PrivacySafeQualificationJob(FrozenModel):
    job_id: str = Field(min_length=1)
    predecessor_qualification_job_id: str = Field(min_length=1)
    source_engineering_job_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    predecessor_task_package_id: str = Field(min_length=1)
    path_id: str = Field(min_length=1)
    predecessor_path_id: str = Field(min_length=1)
    source_engineering_path_id: str = Field(min_length=1)
    source_task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    path_strategy_id: Literal["structured_direct", "search_then_structured", "search_then_open"]
    source_role: Literal["capability", "reachability"]
    job_seed: int = Field(ge=0)
    candidate_presentation_salt_parent_job_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = Field(min_length=1)
    stage_one_profile_id: str = runner_base.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = runner_base.EXPECTED_STAGE_TWO_PROFILE_ID
    thinking_type: Literal["enabled"] = "enabled"
    semantic_action_protocol_id: str = runner_base.EXPECTED_ACTION_PROTOCOL_ID
    semantic_action_response_grammar_id: str = runner_base.EXPECTED_ACTION_GRAMMAR_ID
    exact_final_response_grammar_id: str = runner_base.EXPECTED_FINAL_GRAMMAR_ID
    compact_projection_protocol_id: str = runner_base.EXPECTED_COMPACT_PROTOCOL_ID
    s1_candidate_id: str = runner_base.EXPECTED_S1_CANDIDATE_ID
    resource_contract_id: str = Field(min_length=1)
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    source_model_exposed_before_freeze: Literal[True] = True
    engineering_qualification_only: Literal[True] = True
    role_or_state_eligible: Literal[False] = False
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_safe_s1_qualification_job.v1"] = (
        "finance_v26_privacy_safe_s1_qualification_job.v1"
    )

    @model_validator(mode="after")
    def validate_job(self) -> PrivacySafeQualificationJob:
        if (
            self.job_id == self.predecessor_qualification_job_id
            or self.candidate_presentation_salt_parent_job_id
            != self.predecessor_qualification_job_id
        ):
            raise ValueError("v26.137 Job identity or presentation lineage changed")
        if self.job_id != _identity(
            self, "job_id", "finance_v26_privacy_safe_s1_qualification_job:"
        ):
            raise ValueError("v26.137 Job identity changed")
        return self


class PrivacySafeQualificationManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    predecessor_manifest_id: str = EXPECTED_QUALIFICATION_MANIFEST_ID
    contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = Field(min_length=1)
    prospective_runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    prospective_report_run_id: str = PROSPECTIVE_REPORT_RUN_ID
    jobs: tuple[PrivacySafeQualificationJob, ...] = Field(min_length=32, max_length=32)
    mechanism_job_counts: dict[str, int]
    path_strategy_job_counts: dict[str, int]
    cell_job_counts: dict[str, int]
    distinct_task_package_count: Literal[24] = 24
    exact_denominator: Literal[32] = 32
    predecessor_job_identity_overlap_count: Literal[0] = 0
    role_source_job_count: Literal[0] = 0
    exact_job_assignment_and_seed_preservation_count: Literal[32] = 32
    each_job_execute_at_most_once: Literal[True] = True
    execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_safe_s1_qualification_manifest.v1"] = (
        "finance_v26_privacy_safe_s1_qualification_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> PrivacySafeQualificationManifest:
        if (
            len(self.jobs) != self.exact_denominator
            or len({item.job_id for item in self.jobs}) != self.exact_denominator
            or len({item.task_package_id for item in self.jobs}) != self.distinct_task_package_count
            or len(self.cell_job_counts) != 12
        ):
            raise ValueError("v26.137 Manifest denominator changed")
        if self.manifest_id != _identity(
            self, "manifest_id", "finance_v26_privacy_safe_s1_qualification_manifest:"
        ):
            raise ValueError("v26.137 Manifest identity changed")
        return self


class PrivacySafeOutcomeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    qualification_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    exact_denominator: Literal[32] = 32
    gate_selected_before_future_outcomes: Literal[True] = True
    first_action_interface_minimum_jobs: Literal[24] = 24
    required_cell_coverage: Literal[12] = 12
    instrument_privacy_model_thinking_or_usage_failure_tolerance: Literal[0] = 0
    entry_privacy_instrument_and_overall_reported_separately: Literal[True] = True
    overall_gate_is_noncompensatory_conjunction: Literal[True] = True
    clean_prompt_future_privacy_rejection_is_model_privacy_noncompliance: Literal[True] = True
    clean_prompt_future_privacy_rejection_fails_closed: Literal[True] = True
    classifier_relaxation_alias_stripping_or_output_repair_authorized: Literal[False] = False
    repeat_prompt_tuning_until_pass_authorized: Literal[False] = False
    entry_decline_is_new_prompt_condition_not_historical_pooling: Literal[True] = True
    passing_execution_requires_independent_postrun_audit: Literal[True] = True
    pass_directly_authorizes_role_execution: Literal[False] = False
    zero_role_capability_reachability_state_mapping_rows: Literal[True] = True
    schema_version: Literal["finance_v26_privacy_safe_s1_outcome_contract.v1"] = (
        "finance_v26_privacy_safe_s1_outcome_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> PrivacySafeOutcomeContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_s1_outcome_contract:"
        ):
            raise ValueError("v26.137 Outcome Contract identity changed")
        return self


class PrivacySafeRunnerContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_runner_contract_id: str = EXPECTED_QUALIFICATION_RUNNER_ID
    qualification_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = Field(min_length=1)
    noninterference_audit_id: str = Field(min_length=1)
    runner_run_id: str = PROSPECTIVE_RUNNER_RUN_ID
    execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    exact_job_denominator: Literal[32] = 32
    stage_one_profile_id: str = runner_base.EXPECTED_STAGE_ONE_PROFILE_ID
    stage_two_profile_id: str = runner_base.EXPECTED_STAGE_TWO_PROFILE_ID
    thinking_type: Literal["enabled"] = "enabled"
    exact_final_response_grammar_id: str = runner_base.EXPECTED_FINAL_GRAMMAR_ID
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
    privacy_safe_s1_only_model_visible_action_prompts: Literal[True] = True
    candidate_presentation_preserved_from_predecessor_job: Literal[True] = True
    full_object_fallback_allowed: Literal[False] = False
    privacy_classifier_unchanged: Literal[True] = True
    privacy_redacted_envelope_before_public_projection: Literal[True] = True
    invalid_payload_or_private_reasoning_persisted: Literal[False] = False
    raw_only_recovery: Literal[True] = True
    orphan_artifact_fails_closed: Literal[True] = True
    second_detour_terminal_after_observation_before_later_provider: Literal[True] = True
    stage_two_provider_call_upper_bound: Literal[0] = 0
    runner_implemented: Literal[True] = True
    empirical_execution_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_privacy_safe_s1_runner_contract.v1"] = (
        "finance_v26_privacy_safe_s1_runner_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> PrivacySafeRunnerContract:
        if (
            self.maximum_stage_one_provider_calls
            != self.maximum_primary_stage_one_requests
            + self.maximum_abi_rescue_calls
            + self.maximum_semantic_recovery_calls
            or self.maximum_transport_inclusive_invocations
            != self.maximum_stage_one_provider_calls + self.maximum_transport_replacement_calls
        ):
            raise ValueError("v26.137 Runner counters changed")
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_s1_runner_contract:"
        ):
            raise ValueError("v26.137 Runner Contract identity changed")
        return self


class PrivacySafeRawExecution(FrozenModel):
    artifact_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    job: PrivacySafeQualificationJob
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
    terminal_disposition: runner_base.QualificationTerminal
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
    role_class_external_action_opportunity_count: Literal[0] = 0
    role_class_external_action_selected_count: Literal[0] = 0
    stage_two_provider_call_count: Literal[0] = 0
    capability_reachability_state_mapping_eligible: Literal[False] = False
    later_provider_calls_after_detour_terminal: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_raw_execution.v1"] = (
        "finance_v26_privacy_safe_s1_raw_execution.v1"
    )

    @model_validator(mode="after")
    def validate_raw(self) -> PrivacySafeRawExecution:
        if (
            len(self.provider_envelope_artifacts) != self.stage_one_provider_call_count
            or len(self.public_payload_projection_artifacts) != self.stage_one_provider_call_count
            or len(self.provider_telemetry) != self.stage_one_provider_call_count
            or len(self.transport_invocation_artifacts) != self.transport_inclusive_invocation_count
            or self.transport_replacement_attempt_count
            != self.transport_inclusive_invocation_count - self.stage_one_provider_call_count
        ):
            raise ValueError("v26.137 Raw Provider denominator changed")
        if self.terminal_disposition == "ordinary_detour_allowance_exhausted" and (
            self.ordinary_detour_count != 2 or self.completed_result is not None
        ):
            raise ValueError("v26.137 second-Detour terminal changed")
        if self.artifact_id != _identity(
            self, "artifact_id", "finance_v26_privacy_safe_s1_raw_execution:"
        ):
            raise ValueError("v26.137 Raw identity changed")
        return self


class RunnerFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    scripted_job_count: Literal[32] = 32
    completed_job_count: Literal[32] = 32
    first_action_interface_qualified_count: Literal[32] = 32
    covered_mechanism_path_cell_count: Literal[12] = 12
    semantic_action_primary_count: Literal[224] = 224
    exact_four_field_action_payload_count: Literal[224] = 224
    reversible_commit_count: Literal[224] = 224
    public_observation_count: Literal[192] = 192
    final_primary_count: Literal[32] = 32
    exact_two_field_final_payload_count: Literal[32] = 32
    privacy_envelope_count: Literal[256] = 256
    public_projection_count: Literal[256] = 256
    envelope_before_projection_pass_count: Literal[256] = 256
    privacy_safe_s1_action_prompt_count: Literal[224] = 224
    predecessor_sensitive_prompt_key_count: Literal[0] = 0
    full_object_action_prompt_count: Literal[0] = 0
    raw_recovery_pass_count: Literal[32] = 32
    role_source_job_count: Literal[0] = 0
    fixture_hash: str = Field(min_length=64, max_length=64)
    scripted_local_calls: Literal[256] = 256
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_runner_fixture.v1"] = (
        "finance_v26_privacy_safe_s1_runner_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerFixtureAudit:
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_safe_s1_runner_fixture:"
        ):
            raise ValueError("v26.137 Runner fixture identity changed")
        return self


class RunnerControlRow(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: str = Field(min_length=1)
    passed: Literal[True] = True
    metrics: dict[str, Any]

    @model_validator(mode="after")
    def validate_row(self) -> RunnerControlRow:
        if self.control_id != _identity(
            self, "control_id", "finance_v26_privacy_safe_s1_runner_control:"
        ):
            raise ValueError("v26.137 Runner control identity changed")
        return self


class RunnerControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    rows: tuple[RunnerControlRow, ...] = Field(min_length=17, max_length=17)
    control_count: Literal[17] = 17
    passed_control_count: Literal[17] = 17
    one_detour_completed: Literal[True] = True
    second_detour_terminal: Literal["ordinary_detour_allowance_exhausted"] = (
        "ordinary_detour_allowance_exhausted"
    )
    later_provider_calls_after_second_detour: Literal[0] = 0
    real_provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_runner_control_audit.v1"] = (
        "finance_v26_privacy_safe_s1_runner_control_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerControlAudit:
        if (
            len(self.rows) != self.control_count
            or sum(item.passed for item in self.rows) != self.passed_control_count
        ):
            raise ValueError("v26.137 Runner controls changed")
        if self.audit_id != _identity(
            self, "audit_id", "finance_v26_privacy_safe_s1_runner_control_audit:"
        ):
            raise ValueError("v26.137 Runner control audit identity changed")
        return self


class MutationResult(FrozenModel):
    mutation: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutations: tuple[MutationResult, ...] = Field(min_length=28, max_length=28)
    mutation_count: Literal[28] = 28
    rejection_count: Literal[28] = 28
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    schema_version: Literal["finance_v26_privacy_safe_s1_destructive.v1"] = (
        "finance_v26_privacy_safe_s1_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if len(self.mutations) != self.mutation_count:
            raise ValueError("v26.137 destructive denominator changed")
        if self.audit_id != _identity(self, "audit_id", "finance_v26_privacy_safe_s1_destructive:"):
            raise ValueError("v26.137 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    next_permitted_stage: Literal["privacy_safe_s1_representation_qualification_execution_only"] = (
        NEXT_STAGE
    )
    exact_manifest_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    prospective_execution_run_id: str = PROSPECTIVE_EXECUTION_RUN_ID
    prospective_report_run_id: str = PROSPECTIVE_REPORT_RUN_ID
    only_exact_fresh_32_job_engineering_manifest_authorized: Literal[True] = True
    provider_calls_authorized: Literal[True] = True
    role_provider_calls_authorized: Literal[False] = False
    capability_reachability_execution_authorized: Literal[False] = False
    state_mapping_training_release_or_production_authorized: Literal[False] = False
    classifier_grammar_candidate_s1_model_thinking_or_bounds_change_authorized: Literal[False] = (
        False
    )
    alias_stripping_or_output_repair_authorized: Literal[False] = False
    historical_rerun_recovery_or_reclassification_authorized: Literal[False] = False
    historical_rejected_payload_or_key_inference_authorized: Literal[False] = False
    privacy_gate_remains_zero_tolerance_and_noncompensatory: Literal[True] = True
    clean_interface_privacy_rejection_fails_closed: Literal[True] = True
    pass_requires_independent_postrun_audit_before_role_transition: Literal[True] = True
    qualification_rows_role_or_state_eligible: Literal[False] = False
    status: Literal["passed_privacy_safe_s1_runner_preflight"] = (
        "passed_privacy_safe_s1_runner_preflight"
    )
    schema_version: Literal["finance_v26_privacy_safe_s1_transition.v1"] = (
        "finance_v26_privacy_safe_s1_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self, "contract_id", "finance_v26_privacy_safe_s1_transition:"
        ):
            raise ValueError("v26.137 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class PrivacySafePromptPreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    prompt_metadata_contract_id: str = Field(min_length=1)
    task_package_catalog_id: str = Field(min_length=1)
    path_catalog_id: str = Field(min_length=1)
    noninterference_audit_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    qualification_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    outcome_contract_id: str = Field(min_length=1)
    runner_contract_id: str = Field(min_length=1)
    runner_fixture_audit_id: str = Field(min_length=1)
    runner_control_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    prospective_execution_id: str = Field(min_length=1)
    prospective_report_id: str = Field(min_length=1)
    detail_files: tuple[DetailFile, ...] = Field(min_length=15, max_length=15)
    fresh_prompt_protocol_count: Literal[1] = 1
    fresh_task_package_count: Literal[24] = 24
    fresh_path_count: Literal[48] = 48
    static_state_count: Literal[324] = 324
    regenerated_action_prompt_count: Literal[972] = 972
    fresh_job_count: Literal[32] = 32
    scripted_fixture_job_count: Literal[32] = 32
    scripted_fixture_call_count: Literal[256] = 256
    classifier_sensitive_prompt_key_count: Literal[0] = 0
    prompt_echo_privacy_accept_count: Literal[972] = 972
    action_interface_static_preservation_count: Literal[972] = 972
    first_action_interface_fixture_pass_count: Literal[32] = 32
    formal_v26_134_qualification_remains_failed: Literal[True] = True
    unique_historical_rejection_cause_identified: Literal[False] = False
    qualification_execution_performed: Literal[False] = False
    role_execution_authorized: Literal[False] = False
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    empirical_rows_created: Literal[0] = 0
    historical_rows_reclassified: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: str = NEXT_STAGE
    status: Literal["privacy_safe_s1_prompt_runner_preflight_passed"] = (
        "privacy_safe_s1_prompt_runner_preflight_passed"
    )
    schema_version: Literal["finance_v26_privacy_safe_s1_prompt_preflight_report.v1"] = (
        "finance_v26_privacy_safe_s1_prompt_preflight_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> PrivacySafePromptPreflightReport:
        if self.report_id != _identity(
            self, "report_id", "finance_v26_privacy_safe_s1_prompt_preflight_report:"
        ):
            raise ValueError("v26.137 report identity changed")
        return self


@dataclass(frozen=True)
class _LoadedInputs:
    qualification_report: runner_base.S1QualificationPreflightReport
    qualification_path_catalog: runner_base.S1QualificationPathCatalog
    qualification_resource: runner_base.S1QualificationResourceContract
    qualification_manifest: runner_base.S1QualificationManifest
    qualification_runner: runner_base.S1QualificationRunnerContract
    engineering: engineering_static.FinalGrammarStaticInputs
    engineering_materials: tuple[Any, ...]
    final_materials: tuple[Any, ...]


def _make_source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
) -> SourceReplayAudit:
    root = package_root / PREDECESSOR_DIR
    report_path = root / "report.json"
    report = predecessor.RootCauseAuditReport.model_validate(_load(report_path))
    source = predecessor.RootCauseSourceReplayAudit.model_validate(
        _load(root / "source_replay_audit.json")
    )
    transition = predecessor.ProspectiveTransitionContract.model_validate(
        _load(root / "prospective_transition_contract.json")
    )
    if (
        report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or source.audit_id != EXPECTED_PREDECESSOR_SOURCE_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.next_permitted_stage != predecessor.NEXT_STAGE
        or transition.provider_calls_authorized
    ):
        raise ValueError("v26.137 predecessor authorization changed")
    expected_details = {item.relative_path: item.sha256 for item in report.detail_files}
    entries: dict[str, SourceReplayEntry] = {}
    for item in source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries[item.relative_path] = SourceReplayEntry(
            relative_path=item.relative_path,
            source_kind="v26_136_transitive_source",
            expected_sha256=item.expected_sha256,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    for name in PREDECESSOR_OUTPUT_NAMES:
        path = root / name
        expected = (
            EXPECTED_PREDECESSOR_REPORT_SHA256 if name == "report.json" else expected_details[name]
        )
        relative = str(path.relative_to(package_root))
        entries[relative] = SourceReplayEntry(
            relative_path=relative,
            source_kind="v26_136_output",
            expected_sha256=expected,
            observed_sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
    implementation = implementation_root / IMPLEMENTATION_PATH
    relative = str(implementation.relative_to(implementation_root))
    entries[relative] = SourceReplayEntry(
        relative_path=relative,
        source_kind="v26_137_implementation",
        expected_sha256=_sha256(implementation),
        observed_sha256=_sha256(implementation),
        byte_count=implementation.stat().st_size,
    )
    ordered = tuple(entries[key] for key in sorted(entries))
    provisional = SourceReplayAudit.model_construct(audit_id="pending", entries=ordered)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_s1_source_replay:",
        ),
        entries=ordered,
    )


def _make_predecessor_integrity(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    postrun_dir: Path,
) -> PredecessorIntegrityAudit:
    root = package_root / PREDECESSOR_DIR
    report = predecessor.RootCauseAuditReport.model_validate(_load(root / "report.json"))
    gate = predecessor.QualificationGateDecompositionAudit.model_validate(
        _load(root / "qualification_gate_decomposition_audit.json")
    )
    decision = predecessor.RootCauseDecision.model_validate(
        _load(root / "root_cause_decision.json")
    )
    if (
        report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or gate.audit_id != EXPECTED_PREDECESSOR_GATE_ID
        or decision.decision_id != EXPECTED_PREDECESSOR_DECISION_ID
        or report.formal_s1_representation_qualification_passed
        or gate.privacy_rejected_job_count != 1
        or gate.observed_entry_qualified_count != 31
        or gate.http_success_exact_model_thinking_usage_call_count != 197
        or decision.unique_historical_privacy_rejection_cause_identified
    ):
        raise ValueError("v26.137 predecessor scientific result changed")
    with tempfile.TemporaryDirectory(prefix="v26_137_predecessor_rebuild_") as temporary:
        rebuilt_dir = Path(temporary)
        rebuilt = predecessor.build_root_cause_audit(
            package_root=package_root,
            implementation_root=implementation_root,
            execution_dir=execution_dir,
            postrun_dir=postrun_dir,
            output_dir=rebuilt_dir,
        )
        if rebuilt != report:
            raise ValueError("v26.137 predecessor report rebuild changed")
        matches = sum(
            (root / name).read_bytes() == (rebuilt_dir / name).read_bytes()
            for name in PREDECESSOR_OUTPUT_NAMES
        )
    values = {"predecessor_rebuild_byte_match_count": cast(Literal[10], matches)}
    provisional = PredecessorIntegrityAudit.model_construct(audit_id="pending", **values)
    return PredecessorIntegrityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_s1_predecessor_integrity:",
        ),
        **values,
    )


def _make_prompt_metadata_contract() -> PrivacySafePromptMetadataContract:
    renames = tuple(
        MetadataRename(old_key_path=old, new_key_path=new)
        for old, new in zip(OLD_SENSITIVE_KEY_PATHS, SAFE_REPLACEMENT_KEY_PATHS, strict=True)
    )
    values = {"metadata_renames": cast(tuple[MetadataRename, MetadataRename], renames)}
    provisional = PrivacySafePromptMetadataContract.model_construct(contract_id="pending", **values)
    return PrivacySafePromptMetadataContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_prompt_metadata_contract:",
        ),
        **values,
    )


def _privacy_safe_visible_grammar(
    grammar: action_grammar.SemanticActionResponseGrammar,
) -> PrivacySafeVisibleGrammar:
    old = action_grammar._model_visible_grammar(grammar)  # noqa: SLF001
    expected_keys = {
        "id",
        "fields",
        "types",
        "shape_rules",
        "state_id_rule",
        "action_id_rule",
        "decision_kind_rule",
        "protocol_constant",
        "fixed_stage",
        "host_rules",
        "private_reasoning_content",
    }
    if set(old) != expected_keys or old.pop("private_reasoning_content") != "not_allowed":
        raise ValueError("v26.137 predecessor model-visible Grammar changed")
    return PrivacySafeVisibleGrammar.model_validate(
        {**old, "hidden_model_content": PRIVACY_INSTRUCTION}
    )


def render_privacy_safe_s1_action_prompt(
    *,
    phase: Literal["primary", "abi_rescue", "semantic_recovery"],
    instruction: str,
    state: SemanticActionState,
    public_path_condition: str | None,
    presentation_salt: str,
    typed_failure: Mapping[str, Any] | None,
    grammar: action_grammar.SemanticActionResponseGrammar,
) -> str:
    action_grammar.validate_candidate_space_completeness(state)
    compact = runner_base.predecessor.predecessor
    payload = PrivacySafePromptEnvelope(
        prompt_protocol=f"{PRIVACY_SAFE_PROMPT_PROTOCOL}.{phase}",
        semantic_action_protocol=action_grammar.SEMANTIC_ACTION_PROTOCOL_VERSION,
        instruction=instruction,
        public_path_condition=public_path_condition,
        compact_public_state=compact._compact_state_projection(state),  # noqa: SLF001
        visible_action_candidates=compact._compact_candidates(  # noqa: SLF001
            state, presentation_salt
        ),
        candidate_presentation={
            "order_is_semantically_neutral": True,
            "presentation_salt_sha256": hashlib.sha256(
                presentation_salt.encode("utf-8")
            ).hexdigest(),
        },
        typed_failure=dict(typed_failure) if typed_failure is not None else None,
        response_grammar=_privacy_safe_visible_grammar(grammar),
        lossless_projection_contract={
            "exact_state_reconstruction_required": True,
            "exact_candidate_set_reconstruction_required": True,
            "exact_action_ids_unchanged": True,
            "stage_two_semantic_choice_or_repair": False,
        },
    )
    prompt = PROMPT_PREFIXES[phase] + "\n" + _canonical_bytes(payload).decode("utf-8").rstrip("\n")
    if len(prompt.encode("utf-8")) > runner_base.PROMPT_CEILING_BYTES:
        raise ValueError("v26.137 privacy-safe S1 Prompt exceeds frozen byte ceiling")
    return prompt


def _privacy_safe_prompt_payload(prompt: str) -> PrivacySafePromptEnvelope:
    prefix, separator, serialized = prompt.partition("\n")
    if separator != "\n" or prefix not in PROMPT_PREFIXES.values():
        raise ValueError("v26.137 privacy-safe Prompt envelope is malformed")
    return PrivacySafePromptEnvelope.model_validate(json.loads(serialized))


def _typed_failure(phase: str) -> dict[str, str] | None:
    if phase == "primary":
        return None
    if phase == "abi_rescue":
        return {
            "family": "response_serialization_failure",
            "subtype": "canonical_action_not_exact_four_field_grammar",
        }
    return {
        "family": "semantic_action_rejection",
        "subtype": "fixture_typed_semantic_rejection",
    }


def _authorized_prompt_difference(old_prompt: str, new_prompt: str) -> bool:
    old = runner_base.predecessor.predecessor._compact_prompt_payload(old_prompt)  # noqa: SLF001
    new = _privacy_safe_prompt_payload(new_prompt).model_dump(mode="json")
    old_protocol = old.pop("prompt_protocol", None)
    new_protocol = new.pop("prompt_protocol", None)
    old_reuse = old.pop("private_reasoning_reused", None)
    new_reuse = new.pop("hidden_model_content_reused", None)
    old_grammar = dict(cast(Mapping[str, Any], old.pop("response_grammar", {})))
    new_grammar = dict(cast(Mapping[str, Any], new.pop("response_grammar", {})))
    old_private = old_grammar.pop("private_reasoning_content", None)
    new_private = new_grammar.pop("hidden_model_content", None)
    return bool(
        isinstance(old_protocol, str)
        and old_protocol.endswith(tuple(f".{phase}" for phase in PROMPT_PHASES))
        and new_protocol in {f"{PRIVACY_SAFE_PROMPT_PROTOCOL}.{phase}" for phase in PROMPT_PHASES}
        and old_reuse is False
        and new_reuse is False
        and old_private == "not_allowed"
        and new_private == PRIVACY_INSTRUCTION
        and old_grammar == new_grammar
        and old == new
    )


def _load_inputs(package_root: Path, implementation_root: Path) -> _LoadedInputs:
    root = package_root / QUALIFICATION_PREFLIGHT_DIR
    report = runner_base.S1QualificationPreflightReport.model_validate(_load(root / "report.json"))
    path_catalog = runner_base.S1QualificationPathCatalog.model_validate(
        _load(root / "s1_qualification_path_catalog.json")
    )
    resource = runner_base.S1QualificationResourceContract.model_validate(
        _load(root / "s1_qualification_resource_contract.json")
    )
    manifest = runner_base.S1QualificationManifest.model_validate(
        _load(root / "s1_qualification_manifest.json")
    )
    runner = runner_base.S1QualificationRunnerContract.model_validate(
        _load(root / "s1_qualification_runner_contract.json")
    )
    if (
        report.report_id != EXPECTED_QUALIFICATION_REPORT_ID
        or path_catalog.catalog_id != EXPECTED_QUALIFICATION_PATH_CATALOG_ID
        or resource.contract_id != EXPECTED_QUALIFICATION_RESOURCE_ID
        or manifest.manifest_id != EXPECTED_QUALIFICATION_MANIFEST_ID
        or runner.contract_id != EXPECTED_QUALIFICATION_RUNNER_ID
    ):
        raise ValueError("v26.137 frozen qualification inputs changed")
    loaded = runner_base._load_inputs(package_root, implementation_root)  # noqa: SLF001
    rebuilt_catalog = runner_base._make_path_catalog(loaded)  # noqa: SLF001
    if rebuilt_catalog != path_catalog:
        raise ValueError("v26.137 predecessor S1 Path Catalog no longer rebuilds")
    return _LoadedInputs(
        qualification_report=report,
        qualification_path_catalog=path_catalog,
        qualification_resource=resource,
        qualification_manifest=manifest,
        qualification_runner=runner,
        engineering=loaded.engineering,
        engineering_materials=loaded.engineering_materials,
        final_materials=loaded.final_materials,
    )


def _make_task_packages(
    loaded: _LoadedInputs,
    prompt_contract: PrivacySafePromptMetadataContract,
) -> PrivacySafeTaskPackageCatalog:
    packages: list[PrivacySafeTaskPackage] = []
    for old in loaded.engineering.tasks:
        values = {
            "predecessor_task_package_id": old.task_package_id,
            "source_task_artifact_id": old.source_task_artifact_id,
            "source_role": old.source_role,
            "mechanism_id": old.mechanism_id,
            "operational_record_id": old.operational_record_id,
            "operational_task_package_id": old.operational_task_package_id,
            "environment_manifest_id": old.environment_manifest_id,
            "semantic_source_id": old.semantic_source_id,
            "prompt_metadata_contract_id": prompt_contract.contract_id,
        }
        provisional = PrivacySafeTaskPackage.model_construct(task_package_id="pending", **values)
        packages.append(
            PrivacySafeTaskPackage(
                task_package_id=_identity(
                    provisional,
                    "task_package_id",
                    "finance_v26_privacy_safe_s1_task_package:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(packages, key=lambda item: item.task_package_id))
    catalog_values: dict[str, Any] = {
        "prompt_metadata_contract_id": prompt_contract.contract_id,
        "packages": ordered,
    }
    provisional_catalog = PrivacySafeTaskPackageCatalog.model_construct(
        catalog_id="pending", **catalog_values
    )
    return PrivacySafeTaskPackageCatalog(
        catalog_id=_identity(
            provisional_catalog,
            "catalog_id",
            "finance_v26_privacy_safe_s1_task_package_catalog:",
        ),
        **catalog_values,
    )


def _request_bound(prompt: str) -> int:
    return len(prompt.encode("utf-8")) + 256 + 16_385


def _make_path_catalog(
    *,
    loaded: _LoadedInputs,
    prompt_contract: PrivacySafePromptMetadataContract,
    tasks: PrivacySafeTaskPackageCatalog,
) -> PrivacySafePathCatalog:
    static = loaded.engineering
    path_map = runner_base._material_to_final_path_ids(static)  # noqa: SLF001
    old_paths = {
        item.predecessor_path_audit_id: item for item in loaded.qualification_path_catalog.paths
    }
    task_map = {item.predecessor_task_package_id: item for item in tasks.packages}
    final_material_by_v118 = {
        item.predecessor_path.path_audit_id: item for item in loaded.final_materials
    }
    v118_by_v112 = {item.predecessor_path_audit_id: item for item in static.predecessor.paths}
    v112_by_old = {
        item.predecessor_path_audit_id: item for item in static.predecessor.historical.paths
    }
    paths: list[PrivacySafePath] = []
    for material in loaded.engineering_materials:
        final_path_id = path_map[material.predecessor_path.audit_id]
        old_path = old_paths[final_path_id]
        old_v112 = v112_by_old[material.predecessor_path.audit_id]
        old_v118 = v118_by_v112[old_v112.path_audit_id]
        final_material = final_material_by_v118[old_v118.path_audit_id]
        binding = material.binding
        condition = (
            None
            if binding.source_path.role == "capability"
            else binding.source_path.path_strategy_id
        )
        rows: list[PromptBindingRow] = []
        primary_prompts: list[str] = []
        abi_prompts: list[str] = []
        semantic_prompts: list[str] = []
        for index, (state, expected, expected_call) in enumerate(
            zip(material.states, material.proposals, material.expected_calls, strict=True)
        ):
            old_row = old_path.state_rows[index]
            salt = canonical_hash(
                {
                    "predecessor_report_id": runner_base.EXPECTED_PREDECESSOR_REPORT_ID,
                    "engineering_path_id": final_path_id,
                    "state_id": state.state_id,
                    "logical_index": index,
                },
                prefix="finance_v26_s1_qualification_candidate_presentation:",
            )
            old_prompts: dict[str, str] = {}
            new_prompts: dict[str, str] = {}
            presented: tuple[str, ...] | None = None
            selected_commit: CanonicalActionCommit | None = None
            for phase in PROMPT_PHASES:
                old_prompt = runner_base.predecessor.predecessor._compact_action_prompt(  # noqa: SLF001
                    phase=cast(Any, phase),
                    instruction=binding.record.task_package.task.public.instruction,
                    state=state,
                    public_path_condition=condition,
                    presentation_salt=salt,
                    typed_failure=_typed_failure(phase),
                    grammar=static.action_grammar,
                )
                new_prompt = render_privacy_safe_s1_action_prompt(
                    phase=cast(Any, phase),
                    instruction=binding.record.task_package.task.public.instruction,
                    state=state,
                    public_path_condition=condition,
                    presentation_salt=salt,
                    typed_failure=_typed_failure(phase),
                    grammar=static.action_grammar,
                )
                old_prompts[phase] = old_prompt
                new_prompts[phase] = new_prompt
                decoded_old, candidates_old = (
                    runner_base.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
                        old_prompt, presentation_salt=salt
                    )
                )
                decoded_new, candidates_new = (
                    runner_base.predecessor.predecessor._decode_compact_prompt_with_expected_salt(  # noqa: SLF001
                        new_prompt, presentation_salt=salt
                    )
                )
                proposal_old = runner_base.predecessor.predecessor._compact_reference_proposal(  # noqa: SLF001
                    old_prompt, presentation_salt=salt
                )
                proposal_new = runner_base.predecessor.predecessor._compact_reference_proposal(  # noqa: SLF001
                    new_prompt, presentation_salt=salt
                )
                selected = evaluate_canonical_action_proposal(
                    decoded_new, proposal_new, call_index=index + 1
                )
                intended = action_grammar.exact_canonical_action_payload(proposal_new)
                parsed_intended = action_grammar.parse_exact_canonical_action_payload(intended)
                new_payload = _privacy_safe_prompt_payload(new_prompt).model_dump(mode="json")
                if (
                    decoded_old != state
                    or decoded_new != state
                    or candidates_old != candidates_new
                    or proposal_old != expected
                    or proposal_new != expected
                    or parsed_intended != expected
                    or selected.commit is None
                    or selected.rejection is not None
                    or selected.commit.call != expected_call
                    or _sensitive_key_paths(new_payload)
                    or legacy.contains_private_reasoning(new_payload)
                    or legacy.contains_private_reasoning(intended)
                    or not legacy.contains_private_reasoning(
                        runner_base.predecessor.predecessor._compact_prompt_payload(old_prompt)  # noqa: SLF001
                    )
                    or not _authorized_prompt_difference(old_prompt, new_prompt)
                ):
                    raise ValueError("v26.137 Prompt joint compilation changed semantics")
                current_presented = tuple(item.action_id for item in candidates_new)
                if presented is None:
                    presented = current_presented
                    selected_commit = selected.commit
                elif presented != current_presented or selected_commit != selected.commit:
                    raise ValueError("v26.137 phase changed Candidate order or Commit")
            if presented is None or selected_commit is None:
                raise ValueError("v26.137 Prompt row is empty")
            predecessor_hashes = {
                phase: legacy.sha256_text(old_prompts[phase]) for phase in PROMPT_PHASES
            }
            safe_hashes = {phase: legacy.sha256_text(new_prompts[phase]) for phase in PROMPT_PHASES}
            if predecessor_hashes != {
                "primary": old_row.primary_prompt_sha256,
                "abi_rescue": old_row.abi_rescue_prompt_sha256,
                "semantic_recovery": old_row.semantic_recovery_prompt_sha256,
            }:
                raise ValueError("v26.137 predecessor Prompt hash changed")
            values = {
                "predecessor_state_binding_id": old_row.row_id,
                "logical_state_index": index,
                "state_id": state.state_id,
                "candidate_count": len(presented),
                "presented_action_ids": presented,
                "predecessor_prompt_sha256s": predecessor_hashes,
                "privacy_safe_prompt_sha256s": safe_hashes,
                "predecessor_prompt_utf8_bytes": {
                    phase: len(old_prompts[phase].encode("utf-8")) for phase in PROMPT_PHASES
                },
                "privacy_safe_prompt_utf8_bytes": {
                    phase: len(new_prompts[phase].encode("utf-8")) for phase in PROMPT_PHASES
                },
                "reference_action_id": expected.action_id,
                "reference_decision_kind": expected.decision_kind,
                "reversible_commit_id": selected_commit.commit_id,
            }
            provisional_row = PromptBindingRow.model_construct(row_id="pending", **values)
            rows.append(
                PromptBindingRow(
                    row_id=_identity(
                        provisional_row,
                        "row_id",
                        "finance_v26_privacy_safe_s1_prompt_binding:",
                    ),
                    **values,
                )
            )
            primary_prompts.append(new_prompts["primary"])
            abi_prompts.append(new_prompts["abi_rescue"])
            semantic_prompts.append(new_prompts["semantic_recovery"])
        final_primary = final_material.primary_prompt
        final_rescue = final_material.rescue_prompt
        static_upper = sum(_request_bound(item) for item in primary_prompts)
        static_upper += _request_bound(final_primary)
        static_upper += max(
            max(_request_bound(item) for item in abi_prompts),
            _request_bound(final_rescue),
        )
        static_upper += max(_request_bound(item) for item in semantic_prompts)
        task = task_map[old_path.engineering_task_package_id]
        values = {
            "predecessor_path_id": old_path.path_id,
            "source_engineering_path_id": old_path.predecessor_path_audit_id,
            "task_package_id": task.task_package_id,
            "predecessor_task_package_id": old_path.engineering_task_package_id,
            "source_task_artifact_id": old_path.source_task_artifact_id,
            "source_role": old_path.source_role,
            "mechanism_id": old_path.mechanism_id,
            "path_strategy_id": old_path.path_strategy_id,
            "prompt_metadata_contract_id": prompt_contract.contract_id,
            "prompt_rows": tuple(rows),
            "final_primary_prompt_sha256": old_path.final_primary_prompt_sha256,
            "final_rescue_prompt_sha256": old_path.final_rescue_prompt_sha256,
            "final_primary_prompt_utf8_bytes": old_path.final_primary_prompt_utf8_bytes,
            "final_rescue_prompt_utf8_bytes": old_path.final_rescue_prompt_utf8_bytes,
            "primary_request_count": old_path.primary_request_count,
            "provider_call_count_with_recoveries": old_path.provider_call_count_with_recoveries,
            "transport_inclusive_invocation_count": (old_path.transport_inclusive_invocation_count),
            "static_complete_path_upper_bound_tokens": static_upper,
        }
        provisional_path = PrivacySafePath.model_construct(path_id="pending", **values)
        paths.append(
            PrivacySafePath(
                path_id=_identity(
                    provisional_path,
                    "path_id",
                    "finance_v26_privacy_safe_s1_path:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(paths, key=lambda item: item.path_id))
    all_rows = tuple(row for path in ordered for row in path.prompt_rows)
    values = {
        "prompt_metadata_contract_id": prompt_contract.contract_id,
        "task_package_catalog_id": tasks.catalog_id,
        "paths": ordered,
        "maximum_action_primary_prompt_utf8_bytes": max(
            row.privacy_safe_prompt_utf8_bytes["primary"] for row in all_rows
        ),
        "maximum_action_abi_rescue_prompt_utf8_bytes": max(
            row.privacy_safe_prompt_utf8_bytes["abi_rescue"] for row in all_rows
        ),
        "maximum_semantic_recovery_prompt_utf8_bytes": max(
            row.privacy_safe_prompt_utf8_bytes["semantic_recovery"] for row in all_rows
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
    provisional = PrivacySafePathCatalog.model_construct(catalog_id="pending", **values)
    return PrivacySafePathCatalog(
        catalog_id=_identity(
            provisional,
            "catalog_id",
            "finance_v26_privacy_safe_s1_path_catalog:",
        ),
        **values,
    )


def _make_noninterference_audit(
    *,
    package_root: Path,
    prompt_contract: PrivacySafePromptMetadataContract,
    catalog: PrivacySafePathCatalog,
) -> PromptPrivacyNoninterferenceAudit:
    classifier = predecessor.PrivacyClassifierTypeSystemAudit.model_validate(
        _load(package_root / PREDECESSOR_DIR / "privacy_classifier_type_system_audit.json")
    )
    if (
        classifier.audit_id != EXPECTED_PREDECESSOR_CLASSIFIER_ID
        or classifier.synthetic_case_count != classifier.synthetic_pass_count
        or classifier.synthetic_case_count != 24
    ):
        raise ValueError("v26.137 classifier type-system control changed")
    forbidden = tuple(
        legacy.contains_private_reasoning({f"reasoning_control_{index}": "synthetic"})
        for index in range(24)
    )
    if not all(forbidden):
        raise ValueError("v26.137 unchanged Classifier accepted a forbidden synthetic Key")
    values = {
        "prompt_metadata_contract_id": prompt_contract.contract_id,
        "path_catalog_id": catalog.catalog_id,
        "synthetic_forbidden_reasoning_key_privacy_rejection_count": cast(
            Literal[24], sum(forbidden)
        ),
        "predecessor_classifier_case_pass_count": cast(
            Literal[24], classifier.synthetic_pass_count
        ),
    }
    provisional = PromptPrivacyNoninterferenceAudit.model_construct(audit_id="pending", **values)
    return PromptPrivacyNoninterferenceAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_prompt_privacy_noninterference_audit:",
        ),
        **values,
    )


def _make_resource_contract(
    prompt_contract: PrivacySafePromptMetadataContract,
    catalog: PrivacySafePathCatalog,
) -> PrivacySafeResourceContract:
    values = {
        "prompt_metadata_contract_id": prompt_contract.contract_id,
        "qualified_maximum_action_primary_prompt_utf8_bytes": (
            catalog.maximum_action_primary_prompt_utf8_bytes
        ),
        "qualified_maximum_action_abi_rescue_prompt_utf8_bytes": (
            catalog.maximum_action_abi_rescue_prompt_utf8_bytes
        ),
        "qualified_maximum_semantic_recovery_prompt_utf8_bytes": (
            catalog.maximum_semantic_recovery_prompt_utf8_bytes
        ),
        "qualified_maximum_final_primary_prompt_utf8_bytes": (
            catalog.maximum_final_primary_prompt_utf8_bytes
        ),
        "qualified_maximum_final_rescue_prompt_utf8_bytes": (
            catalog.maximum_final_rescue_prompt_utf8_bytes
        ),
        "maximum_registered_path_static_tokens": catalog.maximum_registered_path_static_tokens,
    }
    provisional = PrivacySafeResourceContract.model_construct(contract_id="pending", **values)
    return PrivacySafeResourceContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_s1_resource_contract:",
        ),
        **values,
    )


def _make_qualification_contract(
    *,
    prompt_contract: PrivacySafePromptMetadataContract,
    noninterference: PromptPrivacyNoninterferenceAudit,
    tasks: PrivacySafeTaskPackageCatalog,
    catalog: PrivacySafePathCatalog,
    resource: PrivacySafeResourceContract,
) -> PrivacySafeQualificationContract:
    values = {
        "prompt_metadata_contract_id": prompt_contract.contract_id,
        "noninterference_audit_id": noninterference.audit_id,
        "task_package_catalog_id": tasks.catalog_id,
        "path_catalog_id": catalog.catalog_id,
        "resource_contract_id": resource.contract_id,
        "task_package_ids": tuple(sorted(item.task_package_id for item in tasks.packages)),
        "path_ids": tuple(sorted(item.path_id for item in catalog.paths)),
    }
    provisional = PrivacySafeQualificationContract.model_construct(contract_id="pending", **values)
    return PrivacySafeQualificationContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_s1_qualification_contract:",
        ),
        **values,
    )


def _make_manifest(
    *,
    loaded: _LoadedInputs,
    prompt_contract: PrivacySafePromptMetadataContract,
    tasks: PrivacySafeTaskPackageCatalog,
    catalog: PrivacySafePathCatalog,
    resource: PrivacySafeResourceContract,
    contract: PrivacySafeQualificationContract,
) -> PrivacySafeQualificationManifest:
    path_map = {item.predecessor_path_id: item for item in catalog.paths}
    task_map = {item.predecessor_task_package_id: item for item in tasks.packages}
    jobs: list[PrivacySafeQualificationJob] = []
    for old in loaded.qualification_manifest.jobs:
        path = path_map[old.path_audit_id]
        task = task_map[old.task_package_id]
        values = {
            "predecessor_qualification_job_id": old.job_id,
            "source_engineering_job_id": old.predecessor_job_id,
            "contract_id": contract.contract_id,
            "task_package_id": task.task_package_id,
            "predecessor_task_package_id": old.task_package_id,
            "path_id": path.path_id,
            "predecessor_path_id": old.path_audit_id,
            "source_engineering_path_id": old.predecessor_path_audit_id,
            "source_task_artifact_id": old.source_task_artifact_id,
            "mechanism_id": old.mechanism_id,
            "path_strategy_id": old.path_strategy_id,
            "source_role": old.source_role,
            "job_seed": old.job_seed,
            "candidate_presentation_salt_parent_job_id": old.job_id,
            "prompt_metadata_contract_id": prompt_contract.contract_id,
            "resource_contract_id": resource.contract_id,
        }
        provisional = PrivacySafeQualificationJob.model_construct(job_id="pending", **values)
        jobs.append(
            PrivacySafeQualificationJob(
                job_id=_identity(
                    provisional,
                    "job_id",
                    "finance_v26_privacy_safe_s1_qualification_job:",
                ),
                **values,
            )
        )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    mechanism = Counter(item.mechanism_id for item in ordered)
    strategies = Counter(item.path_strategy_id for item in ordered)
    cells = Counter(f"{item.mechanism_id}|{item.path_strategy_id}" for item in ordered)
    values = {
        "contract_id": contract.contract_id,
        "resource_contract_id": resource.contract_id,
        "path_catalog_id": catalog.catalog_id,
        "prompt_metadata_contract_id": prompt_contract.contract_id,
        "jobs": ordered,
        "mechanism_job_counts": dict(sorted(mechanism.items())),
        "path_strategy_job_counts": dict(sorted(strategies.items())),
        "cell_job_counts": dict(sorted(cells.items())),
    }
    provisional_manifest = PrivacySafeQualificationManifest.model_construct(
        manifest_id="pending", **values
    )
    return PrivacySafeQualificationManifest(
        manifest_id=_identity(
            provisional_manifest,
            "manifest_id",
            "finance_v26_privacy_safe_s1_qualification_manifest:",
        ),
        **values,
    )


def _make_outcome_contract(
    contract: PrivacySafeQualificationContract,
    manifest: PrivacySafeQualificationManifest,
) -> PrivacySafeOutcomeContract:
    values = {
        "qualification_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
    }
    provisional = PrivacySafeOutcomeContract.model_construct(contract_id="pending", **values)
    return PrivacySafeOutcomeContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_s1_outcome_contract:",
        ),
        **values,
    )


def _make_runner_contract(
    *,
    prompt_contract: PrivacySafePromptMetadataContract,
    noninterference: PromptPrivacyNoninterferenceAudit,
    contract: PrivacySafeQualificationContract,
    manifest: PrivacySafeQualificationManifest,
    outcome: PrivacySafeOutcomeContract,
    resource: PrivacySafeResourceContract,
) -> PrivacySafeRunnerContract:
    values = {
        "qualification_contract_id": contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "resource_contract_id": resource.contract_id,
        "prompt_metadata_contract_id": prompt_contract.contract_id,
        "noninterference_audit_id": noninterference.audit_id,
    }
    provisional = PrivacySafeRunnerContract.model_construct(contract_id="pending", **values)
    return PrivacySafeRunnerContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_s1_runner_contract:",
        ),
        **values,
    )


def _raw_path(output_dir: Path, job: PrivacySafeQualificationJob) -> Path:
    return output_dir / "raw_execution" / f"{job.job_id.rsplit(':', 1)[-1]}.json"


def _privacy_safe_active_call(
    ledger: runner_base._S1Journal,  # noqa: SLF001
    *,
    attempts: list[privacy_runner.PrivacyFirstAttempt],
    logical_request_index: int,
    request_kind: legacy.StageOneRequestKind,
    public_attempt_phase: Literal["primary", "semantic_recovery"],
    primary_prompt: str,
    state: SemanticActionState | None,
    presentation_salt: str | None,
    instruction: str | None,
    condition: str | None,
    final_response_host_envelope: FinalResponseHostEnvelope | None,
    static: engineering_static.FinalGrammarStaticInputs,
    abi_rescue_count: int,
    semantic_recovery_count: int,
) -> tuple[runner_base._CallOutcome, int]:  # noqa: SLF001
    primary = runner_base._invoke_once(  # noqa: SLF001
        ledger,
        logical_request_index=logical_request_index,
        request_kind=request_kind,
        public_attempt_phase=public_attempt_phase,
        primary_prompt=primary_prompt,
        prompt=primary_prompt,
        state=state,
        final_response_host_envelope=final_response_host_envelope,
        static=static,
        abi_rescue_count=abi_rescue_count,
        semantic_recovery_count=semantic_recovery_count,
    )
    attempts.append(primary.attempt)
    if abi_rescue_count == 0 and runner_base._abi_rescue_allowed(primary.attempt):  # noqa: SLF001
        abi_rescue_count = 1
        family = primary.attempt.failure_family or "channel_parse_failure"
        subtype = (
            primary.attempt.failure_subtype
            or primary.attempt.completion_failure_type
            or "completion_failure"
        )
        if request_kind == "semantic_proposal":
            if state is None or presentation_salt is None or instruction is None:
                raise ValueError("v26.137 Action ABI Rescue lacks privacy-safe S1 state")
            rescue_prompt = render_privacy_safe_s1_action_prompt(
                phase="abi_rescue",
                instruction=instruction,
                state=state,
                public_path_condition=condition,
                presentation_salt=presentation_salt,
                typed_failure={"family": family, "subtype": subtype},
                grammar=static.action_grammar,
            )
        else:
            rescue_prompt = render_exact_final_rescue_prompt(
                primary_prompt,
                failure_family=family,
                failure_subtype=subtype,
            )
        rescue = runner_base._invoke_once(  # noqa: SLF001
            ledger,
            logical_request_index=logical_request_index,
            request_kind=request_kind,
            public_attempt_phase="abi_rescue",
            primary_prompt=primary_prompt,
            prompt=rescue_prompt,
            state=state,
            final_response_host_envelope=final_response_host_envelope,
            static=static,
            abi_rescue_count=abi_rescue_count,
            semantic_recovery_count=semantic_recovery_count,
        )
        attempts.append(rescue.attempt)
        return rescue, abi_rescue_count
    return primary, abi_rescue_count


def execute_privacy_safe_s1_job_raw(
    *,
    job: PrivacySafeQualificationJob,
    old_job: engineering_static.FinalGrammarJob,
    runner_contract: PrivacySafeRunnerContract,
    resource_contract: PrivacySafeResourceContract,
    static: engineering_static.FinalGrammarStaticInputs,
    binding: legacy.RuntimeBinding,
    client: Any | None,
    output_dir: Path,
) -> PrivacySafeRawExecution:
    raw_path = _raw_path(output_dir, job)
    if raw_path.exists():
        raw = PrivacySafeRawExecution.model_validate(_load(raw_path))
        if raw.runner_contract_id != runner_contract.contract_id or raw.job != job:
            raise ValueError("v26.137 Raw recovery crosses fresh identities")
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
                raise ValueError("v26.137 Raw recovery bytes changed")
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
            raise ValueError("v26.137 Raw recovery telemetry changed")
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
        raise ValueError("v26.137 orphan Provider or invocation artifact forbids retry")
    if client is None:
        raise ValueError("pending v26.137 Job has no Stage 1 client")
    if (
        old_job.job_id != job.source_engineering_job_id
        or old_job.task_package_id != job.predecessor_task_package_id
    ):
        raise ValueError("v26.137 Job changed its engineering assignment")
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
    condition = (
        None
        if binding.source_registered_path.role == "capability"
        else binding.source_registered_path.path_strategy_id
    )
    terminal: runner_base.QualificationTerminal = "model_result_failure"
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
        presentation_salt = canonical_hash(
            {
                "qualification_job_id": job.candidate_presentation_salt_parent_job_id,
                "logical_request_index": logical_index,
                "state_id": state.state_id,
                "semantic_recovery_count": semantic_recovery_count,
                "ordinary_detour_count": ordinary_detour_count,
            },
            prefix="finance_v26_s1_qualification_candidate_presentation:",
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
        prompt = render_privacy_safe_s1_action_prompt(
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
        if decoded_state != state or _sensitive_key_paths(
            _privacy_safe_prompt_payload(prompt).model_dump(mode="json")
        ):
            raise ValueError("v26.137 online Prompt changed state or privacy-safe Key surface")
        diagnostic_reference = runner_base._reference_proposal_from_s1_prompt(prompt)  # noqa: SLF001
        ledger.ordinary_detour_count = ordinary_detour_count
        outcome, abi_rescue_count = _privacy_safe_active_call(
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
            raise ValueError("accepted v26.137 action lacks a Commit")
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
        outcome, abi_rescue_count = _privacy_safe_active_call(
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
    provisional_raw = PrivacySafeRawExecution.model_construct(artifact_id="pending", **raw_values)
    raw = PrivacySafeRawExecution(
        artifact_id=_identity(
            provisional_raw,
            "artifact_id",
            "finance_v26_privacy_safe_s1_raw_execution:",
        ),
        **raw_values,
    )
    _write_json_atomic(raw_path, raw)
    return raw


def _job_context(
    loaded: _LoadedInputs,
    job: PrivacySafeQualificationJob,
) -> tuple[engineering_static.FinalGrammarJob, legacy.RuntimeBinding]:
    qualification_job = next(
        item
        for item in loaded.qualification_manifest.jobs
        if item.job_id == job.predecessor_qualification_job_id
    )
    old = next(
        item
        for item in loaded.engineering.manifest.jobs
        if item.job_id == job.source_engineering_job_id
    )
    if (
        qualification_job.predecessor_job_id != old.job_id
        or qualification_job.task_package_id != job.predecessor_task_package_id
        or qualification_job.path_audit_id != job.predecessor_path_id
        or qualification_job.predecessor_path_audit_id != job.source_engineering_path_id
        or qualification_job.job_seed != job.job_seed
    ):
        raise ValueError("v26.137 Job context changed assignment, Path, or seed")
    return old, privacy_runner.privacy_first_runtime_binding(loaded.engineering, old)


def _fixture_hash(raws: Sequence[PrivacySafeRawExecution]) -> str:
    return hashlib.sha256(
        _canonical_bytes([item.model_dump(mode="json") for item in raws])
    ).hexdigest()


def _make_runner_fixture(
    *,
    loaded: _LoadedInputs,
    manifest: PrivacySafeQualificationManifest,
    resource: PrivacySafeResourceContract,
    runner_contract: PrivacySafeRunnerContract,
) -> RunnerFixtureAudit:
    raws: list[PrivacySafeRawExecution] = []
    all_prompts: list[tuple[str, str, str]] = []
    with tempfile.TemporaryDirectory(prefix="v26_137_fixture_") as temporary:
        root = Path(temporary)
        for job in manifest.jobs:
            old, binding = _job_context(loaded, job)
            client = runner_base.ScriptedS1QualificationClient(
                loaded.engineering.agent_model_config,
                final_answer=binding.compiler_trajectory.final_answer,
            )
            raw = execute_privacy_safe_s1_job_raw(
                job=job,
                old_job=old,
                runner_contract=runner_contract,
                resource_contract=resource,
                static=loaded.engineering,
                binding=binding,
                client=client,
                output_dir=root,
            )
            if raw.terminal_disposition != "completed_model_result":
                raise ValueError(
                    "v26.137 scripted reference Job did not complete: "
                    f"{job.job_id} {raw.terminal_disposition} "
                    f"{raw.terminal_failure_type} {raw.execution_error}"
                )
            recovered = execute_privacy_safe_s1_job_raw(
                job=job,
                old_job=old,
                runner_contract=runner_contract,
                resource_contract=resource,
                static=loaded.engineering,
                binding=binding,
                client=None,
                output_dir=root,
            )
            if recovered.model_dump(mode="json") != raw.model_dump(mode="json"):
                raise ValueError("v26.137 scripted Raw recovery changed")
            raws.append(raw)
            all_prompts.extend(client.prompts)
    action_attempts = sum(item.exact_four_field_action_payload_count for item in raws)
    commits = sum(len(item.commits) for item in raws)
    observations = sum(len(item.observations) for item in raws)
    final_payloads = sum(item.exact_two_field_final_payload_count for item in raws)
    calls = sum(item.stage_one_provider_call_count for item in raws)
    action_prompts = tuple(
        prompt for request_kind, _, prompt in all_prompts if request_kind == "semantic_proposal"
    )
    safe_prompts = sum(
        PRIVACY_SAFE_PROMPT_PROTOCOL in prompt
        and not _sensitive_key_paths(_privacy_safe_prompt_payload(prompt).model_dump(mode="json"))
        for prompt in action_prompts
    )
    values = {
        "runner_contract_id": runner_contract.contract_id,
        "manifest_id": manifest.manifest_id,
        "semantic_action_primary_count": action_attempts,
        "exact_four_field_action_payload_count": action_attempts,
        "reversible_commit_count": commits,
        "public_observation_count": observations,
        "exact_two_field_final_payload_count": final_payloads,
        "privacy_envelope_count": calls,
        "public_projection_count": calls,
        "envelope_before_projection_pass_count": calls,
        "privacy_safe_s1_action_prompt_count": safe_prompts,
        "fixture_hash": _fixture_hash(raws),
        "scripted_local_calls": calls,
    }
    provisional = RunnerFixtureAudit.model_construct(audit_id="pending", **values)
    return RunnerFixtureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_s1_runner_fixture:",
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
            "finance_v26_privacy_safe_s1_runner_control:",
        ),
        **values,
    )


def _run_control_job(
    *,
    loaded: _LoadedInputs,
    job: PrivacySafeQualificationJob,
    resource: PrivacySafeResourceContract,
    runner_contract: PrivacySafeRunnerContract,
    root: Path,
    **client_kwargs: Any,
) -> tuple[PrivacySafeRawExecution, runner_base.ScriptedS1QualificationClient]:
    old, binding = _job_context(loaded, job)
    client = runner_base.ScriptedS1QualificationClient(
        loaded.engineering.agent_model_config,
        final_answer=binding.compiler_trajectory.final_answer,
        **client_kwargs,
    )
    raw = execute_privacy_safe_s1_job_raw(
        job=job,
        old_job=old,
        runner_contract=runner_contract,
        resource_contract=resource,
        static=loaded.engineering,
        binding=binding,
        client=client,
        output_dir=root,
    )
    return raw, client


def _make_runner_controls(
    *,
    package_root: Path,
    loaded: _LoadedInputs,
    manifest: PrivacySafeQualificationManifest,
    resource: PrivacySafeResourceContract,
    runner_contract: PrivacySafeRunnerContract,
    noninterference: PromptPrivacyNoninterferenceAudit,
) -> RunnerControlAudit:
    ordinary_job = manifest.jobs[0]
    detour_job = next(
        item
        for item in manifest.jobs
        if item.source_engineering_path_id == runner_base.EXPECTED_DETOUR_PATH_ID
    )
    rows: list[RunnerControlRow] = []
    with tempfile.TemporaryDirectory(prefix="v26_137_controls_") as temporary:
        base = Path(temporary)
        abi, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "abi",
            malformed_action_once=True,
        )
        if (
            abi.terminal_disposition != "completed_model_result"
            or abi.abi_rescue_attempt_count != 1
        ):
            raise ValueError("v26.137 ABI Rescue control failed")
        rows.append(_control_row("privacy_safe_exact_abi_rescue", {"abi_rescues": 1}))

        semantic, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "semantic",
            semantic_rejection_once=True,
        )
        if (
            semantic.terminal_disposition != "completed_model_result"
            or semantic.semantic_recovery_attempt_count != 1
            or semantic.abi_rescue_attempt_count != 0
        ):
            raise ValueError("v26.137 Semantic Recovery control failed")
        rows.append(
            _control_row(
                "semantic_recovery_counter_separate",
                {"semantic_recoveries": 1, "abi_rescues": 0},
            )
        )

        transport, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "transport",
            transport_failure_once=True,
        )
        if (
            transport.terminal_disposition != "completed_model_result"
            or transport.transport_replacement_attempt_count != 1
            or transport.transport_inclusive_invocation_count
            != transport.stage_one_provider_call_count + 1
        ):
            raise ValueError("v26.137 Transport Replacement control failed")
        rows.append(
            _control_row(
                "transport_replacement_counter_separate",
                {
                    "transport_replacements": 1,
                    "provider_calls": transport.stage_one_provider_call_count,
                    "transport_invocations": transport.transport_inclusive_invocation_count,
                },
            )
        )

        privacy, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "privacy",
            privacy_failure_once=True,
        )
        privacy_bytes = b"".join(
            (base / "privacy" / item.relative_path).read_bytes()
            for item in privacy.provider_envelope_artifacts
        )
        projection_bytes = b"".join(
            (base / "privacy" / item.relative_path).read_bytes()
            for item in privacy.public_payload_projection_artifacts
        )
        if (
            privacy.privacy_rejected_payload_count != 1
            or b"fixture private content" in privacy_bytes + projection_bytes
            or b"reasoning_trace" in privacy_bytes + projection_bytes
        ):
            raise ValueError("v26.137 privacy-first rejection control failed")
        rows.append(_control_row("privacy_first_envelope_projection", {"rejections": 1}))

        for tokens in (16_384, 16_385):
            usage, _ = _run_control_job(
                loaded=loaded,
                job=ordinary_job,
                resource=resource,
                runner_contract=runner_contract,
                root=base / f"usage_{tokens}",
                completion_tokens=tokens,
            )
            if usage.terminal_disposition != "completed_model_result":
                raise ValueError("v26.137 admitted Usage boundary failed")
        rejected_usage, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "usage_16386",
            completion_tokens=16_386,
        )
        if rejected_usage.terminal_disposition != "instrument_failure":
            raise ValueError("v26.137 rejected Usage boundary failed")
        rows.append(
            _control_row(
                "completion_usage_boundaries",
                {"admitted": [16384, 16385], "instrument_failure": 16386},
            )
        )

        one_detour, _ = _run_control_job(
            loaded=loaded,
            job=detour_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "one_detour",
            force_action_id=runner_base.EXPECTED_DETOUR_ACTION_ID,
            force_action_uses=1,
        )
        if (
            one_detour.terminal_disposition != "completed_model_result"
            or one_detour.ordinary_detour_count != 1
            or one_detour.abi_rescue_attempt_count
            or one_detour.semantic_recovery_attempt_count
            or one_detour.transport_replacement_attempt_count
        ):
            raise ValueError("v26.137 one-Detour control failed")
        rows.append(
            _control_row(
                "one_ordinary_detour_then_replan",
                {"ordinary_detours": 1, "other_recovery_counters": [0, 0, 0]},
            )
        )

        two_detour, _ = _run_control_job(
            loaded=loaded,
            job=detour_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "two_detour",
            force_action_id=runner_base.EXPECTED_DETOUR_ACTION_ID,
            force_action_uses=2,
        )
        if (
            two_detour.terminal_disposition != "ordinary_detour_allowance_exhausted"
            or two_detour.ordinary_detour_count != 2
            or len(two_detour.progress_events) < 2
            or not two_detour.progress_events[-1].ordinary_detour_observed
            or two_detour.later_provider_calls_after_detour_terminal != 0
        ):
            raise ValueError("v26.137 second-Detour terminal control failed")
        rows.append(
            _control_row(
                "second_detour_typed_measurement_terminal",
                {
                    "ordinary_detours_observed": 2,
                    "later_provider_calls": 0,
                    "proposal_and_tool_observation_retained": True,
                },
            )
        )

        wrong, _ = _run_control_job(
            loaded=loaded,
            job=ordinary_job,
            resource=resource,
            runner_contract=runner_contract,
            root=base / "wrong_final",
            wrong_final_answer=True,
        )
        if (
            wrong.terminal_disposition != "completed_model_result"
            or not wrong.first_action_interface_qualified
            or wrong.exact_two_field_final_payload_count != 1
        ):
            raise ValueError("v26.137 wrong-answer separation control failed")
        rows.append(
            _control_row(
                "representation_abi_separate_from_answer_validity",
                {"exact_final_abi": 1, "answer_validity_used_for_gate": False},
            )
        )

        old, binding = _job_context(loaded, ordinary_job)
        recovered = execute_privacy_safe_s1_job_raw(
            job=ordinary_job,
            old_job=old,
            runner_contract=runner_contract,
            resource_contract=resource,
            static=loaded.engineering,
            binding=binding,
            client=None,
            output_dir=base / "abi",
        )
        if recovered.model_dump(mode="json") != abi.model_dump(mode="json"):
            raise ValueError("v26.137 complete Raw recovery changed")
        rows.append(_control_row("complete_raw_zero_call_recovery", {"recovered": 1}))

        orphan_root = base / "orphan"
        orphan_path = privacy_runner.provider_envelope_path(orphan_root, cast(Any, ordinary_job), 0)
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_text("{}\n", encoding="utf-8")
        try:
            execute_privacy_safe_s1_job_raw(
                job=ordinary_job,
                old_job=old,
                runner_contract=runner_contract,
                resource_contract=resource,
                static=loaded.engineering,
                binding=binding,
                client=None,
                output_dir=orphan_root,
            )
        except ValueError:
            pass
        else:
            raise ValueError("v26.137 orphan artifact did not fail closed")
        rows.append(_control_row("orphan_artifact_blocks_retry", {"rejected": 1}))

        rows.append(
            _control_row(
                "privacy_safe_s1_only_no_full_object_fallback",
                {
                    "prompt_protocol": PRIVACY_SAFE_PROMPT_PROTOCOL,
                    "s1_candidate_id": runner_base.EXPECTED_S1_CANDIDATE_ID,
                    "fallback_count": 0,
                },
            )
        )
        rows.append(
            _control_row(
                "role_class_external_frequency_opportunity_separation",
                {
                    "retained_role_external_actions": runner_base.ROLE_CLASS_EXTERNAL_ACTION_COUNT,
                    "engineering_online_opportunities": 0,
                    "zero_opportunity_is_not_zero_frequency": True,
                },
            )
        )
        rows.append(
            _control_row(
                "resource_and_counter_vector_exact",
                {"resource": [60000, 21, 23, 24, 1120000], "counters": [1, 1, 1, 1]},
            )
        )

        if (
            noninterference.privacy_safe_sensitive_key_occurrence_count
            or noninterference.privacy_safe_prompt_echo_privacy_rejection_count
        ):
            raise ValueError("v26.137 Prompt noninterference control failed")
        rows.append(
            _control_row(
                "prompt_privacy_key_namespace_noninterference",
                {"prompts": 972, "sensitive_keys": 0, "echo_privacy_rejections": 0},
            )
        )

        classifier = predecessor.PrivacyClassifierTypeSystemAudit.model_validate(
            _load(package_root / PREDECESSOR_DIR / "privacy_classifier_type_system_audit.json")
        )
        if (
            classifier.synthetic_pass_count != 24
            or not legacy.contains_private_reasoning({"reasoning": "synthetic"})
            or legacy.contains_private_reasoning(
                {"policy": PRIVACY_INSTRUCTION, "hidden_model_content_reused": False}
            )
        ):
            raise ValueError("v26.137 privacy prohibition preservation control failed")
        rows.append(
            _control_row(
                "privacy_prohibition_and_classifier_preserved",
                {"classifier_cases": 24, "forbidden_key_rejected": True},
            )
        )

        predecessor_gate = predecessor.QualificationGateDecompositionAudit.model_validate(
            _load(package_root / PREDECESSOR_DIR / "qualification_gate_decomposition_audit.json")
        )
        if predecessor_gate.overall_authorization_gate_passed or (
            predecessor_gate.privacy_rejected_job_count != 1
        ):
            raise ValueError("v26.137 historical failed Gate changed")
        rows.append(
            _control_row(
                "historical_failed_gate_and_rejected_row_immutable",
                {"overall_gate_passed": False, "privacy_rejected_rows": 1},
            )
        )

        sample_state = build_semantic_action_state(
            binding.record.task_package.task.public,
            binding.environment,
            (),
        )
        sample_salt = canonical_hash(
            {"control": "clean_prompt_echo", "state_id": sample_state.state_id},
            prefix="finance_v26_privacy_safe_prompt_control_salt:",
        )
        sample_prompt = render_privacy_safe_s1_action_prompt(
            phase="primary",
            instruction=binding.record.task_package.task.public.instruction,
            state=sample_state,
            public_path_condition=None,
            presentation_salt=sample_salt,
            typed_failure=None,
            grammar=loaded.engineering.action_grammar,
        )
        echo_payload = _privacy_safe_prompt_payload(sample_prompt).model_dump(mode="json")
        grammar_rejected = False
        try:
            action_grammar.parse_exact_canonical_action_payload(echo_payload)
        except action_grammar.SemanticActionResponseRejection:
            grammar_rejected = True
        if legacy.contains_private_reasoning(echo_payload) or not grammar_rejected:
            raise ValueError("v26.137 clean Prompt echo separation control failed")
        rows.append(
            _control_row(
                "clean_prompt_echo_privacy_accepts_grammar_rejects",
                {"privacy_accepted": True, "action_grammar_rejected": True},
            )
        )
    ordered = tuple(sorted(rows, key=lambda item: item.control_id))
    values = {"runner_contract_id": runner_contract.contract_id, "rows": ordered}
    provisional = RunnerControlAudit.model_construct(audit_id="pending", **values)
    return RunnerControlAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_s1_runner_control_audit:",
        ),
        **values,
    )


def _revalidate(model: BaseModel, **changes: Any) -> Any:
    values = model.model_dump(mode="json")
    values.update(changes)
    return type(model).model_validate(values)


def _expect_rejected(name: str, callback: Callable[[], Any]) -> MutationResult:
    try:
        callback()
    except (ValueError, TypeError):
        return MutationResult(mutation=name)
    raise ValueError(f"v26.137 destructive mutation was accepted: {name}")


def _make_transition(
    manifest: PrivacySafeQualificationManifest,
    runner_contract: PrivacySafeRunnerContract,
    outcome: PrivacySafeOutcomeContract,
) -> ProspectiveTransitionContract:
    values = {
        "exact_manifest_id": manifest.manifest_id,
        "runner_contract_id": runner_contract.contract_id,
        "outcome_contract_id": outcome.contract_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_privacy_safe_s1_transition:",
        ),
        **values,
    )


def _make_destructive(
    *,
    loaded: _LoadedInputs,
    prompt_contract: PrivacySafePromptMetadataContract,
    tasks: PrivacySafeTaskPackageCatalog,
    catalog: PrivacySafePathCatalog,
    noninterference: PromptPrivacyNoninterferenceAudit,
    resource: PrivacySafeResourceContract,
    qualification: PrivacySafeQualificationContract,
    manifest: PrivacySafeQualificationManifest,
    outcome: PrivacySafeOutcomeContract,
    runner_contract: PrivacySafeRunnerContract,
    transition: ProspectiveTransitionContract,
    predecessor_integrity: PredecessorIntegrityAudit,
) -> DestructiveAudit:
    material = loaded.engineering_materials[0]
    state = material.states[0]
    binding = material.binding
    salt = canonical_hash(
        {"mutation": "prompt_schema", "state_id": state.state_id},
        prefix="finance_v26_privacy_safe_prompt_mutation_salt:",
    )
    prompt = render_privacy_safe_s1_action_prompt(
        phase="primary",
        instruction=binding.record.task_package.task.public.instruction,
        state=state,
        public_path_condition=None,
        presentation_salt=salt,
        typed_failure=None,
        grammar=loaded.engineering.action_grammar,
    )
    payload = _privacy_safe_prompt_payload(prompt).model_dump(mode="json")
    grammar_payload = dict(cast(Mapping[str, Any], payload["response_grammar"]))
    first_task = tasks.packages[0]
    first_path = catalog.paths[0]
    first_job = manifest.jobs[0]
    mutations = (
        _expect_rejected(
            "restore_top_level_private_reasoning_reused",
            lambda: PrivacySafePromptEnvelope.model_validate(
                {**payload, "private_reasoning_reused": False}
            ),
        ),
        _expect_rejected(
            "restore_nested_private_reasoning_content",
            lambda: PrivacySafePromptEnvelope.model_validate(
                {
                    **payload,
                    "response_grammar": {
                        **grammar_payload,
                        "private_reasoning_content": "not_allowed",
                    },
                }
            ),
        ),
        _expect_rejected(
            "introduce_new_reasoning_substring_key",
            lambda: PrivacySafePromptEnvelope.model_validate(
                {**payload, "public_reasoning_policy": "forbidden"}
            ),
        ),
        _expect_rejected(
            "permit_hidden_model_content_reuse",
            lambda: PrivacySafePromptEnvelope.model_validate(
                {**payload, "hidden_model_content_reused": True}
            ),
        ),
        _expect_rejected(
            "weaken_scalar_privacy_instruction",
            lambda: PrivacySafePromptEnvelope.model_validate(
                {
                    **payload,
                    "response_grammar": {
                        **grammar_payload,
                        "hidden_model_content": "allowed",
                    },
                }
            ),
        ),
        _expect_rejected(
            "classifier_change",
            lambda: _revalidate(prompt_contract, classifier_changed=True),
        ),
        _expect_rejected(
            "classifier_binding_change",
            lambda: _revalidate(prompt_contract, predecessor_classifier_audit_id="changed"),
        ),
        _expect_rejected(
            "action_grammar_change",
            lambda: _revalidate(first_task, semantic_action_response_grammar_id="changed"),
        ),
        _expect_rejected(
            "candidate_authority_change",
            lambda: _revalidate(first_task, s1_candidate_id="changed"),
        ),
        _expect_rejected(
            "compact_s1_projection_change",
            lambda: _revalidate(first_task, compact_projection_protocol_id="changed"),
        ),
        _expect_rejected(
            "stage_one_model_profile_change",
            lambda: _revalidate(first_job, stage_one_profile_id="changed"),
        ),
        _expect_rejected(
            "thinking_disable",
            lambda: _revalidate(first_job, thinking_type="disabled"),
        ),
        _expect_rejected(
            "completion_bound_change",
            lambda: _revalidate(resource, exact_request_completion_bound_tokens=16385),
        ),
        _expect_rejected(
            "rollout_bound_change",
            lambda: _revalidate(resource, rollout_upper_bound_tokens=1120001),
        ),
        _expect_rejected(
            "abi_rescue_count_change",
            lambda: _revalidate(resource, maximum_abi_rescue_calls=2),
        ),
        _expect_rejected(
            "semantic_recovery_count_change",
            lambda: _revalidate(resource, maximum_semantic_recovery_calls=2),
        ),
        _expect_rejected(
            "transport_replacement_count_change",
            lambda: _revalidate(resource, maximum_transport_replacement_calls=2),
        ),
        _expect_rejected(
            "ordinary_detour_count_change",
            lambda: _revalidate(resource, maximum_ordinary_detours=2),
        ),
        _expect_rejected(
            "stage_two_provider_route",
            lambda: _revalidate(runner_contract, stage_two_provider_call_upper_bound=1),
        ),
        _expect_rejected(
            "full_object_fallback",
            lambda: _revalidate(runner_contract, full_object_fallback_allowed=True),
        ),
        _expect_rejected(
            "reuse_predecessor_task_package_identity",
            lambda: _revalidate(first_task, task_package_id=first_task.predecessor_task_package_id),
        ),
        _expect_rejected(
            "reuse_predecessor_path_identity",
            lambda: _revalidate(first_path, path_id=first_path.predecessor_path_id),
        ),
        _expect_rejected(
            "reuse_predecessor_job_identity",
            lambda: _revalidate(first_job, job_id=first_job.predecessor_qualification_job_id),
        ),
        _expect_rejected(
            "job_seed_change",
            lambda: _revalidate(first_job, job_seed=first_job.job_seed + 1),
        ),
        _expect_rejected(
            "role_source_job_insertion",
            lambda: _revalidate(manifest, role_source_job_count=1),
        ),
        _expect_rejected(
            "historical_gate_reclassification",
            lambda: _revalidate(predecessor_integrity, formal_qualification_remains_failed=False),
        ),
        _expect_rejected(
            "compensatory_privacy_gate",
            lambda: _revalidate(outcome, overall_gate_is_noncompensatory_conjunction=False),
        ),
        _expect_rejected(
            "authorize_role_provider_calls",
            lambda: _revalidate(transition, role_provider_calls_authorized=True),
        ),
    )
    if (
        noninterference.privacy_safe_sensitive_key_occurrence_count
        or qualification.provider_calls_authorized
    ):
        raise ValueError("v26.137 destructive baseline changed")
    values = {"mutations": mutations}
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_privacy_safe_s1_destructive:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_privacy_safe_prompt_preflight(
    *,
    package_root: Path,
    implementation_root: Path,
    execution_dir: Path,
    postrun_dir: Path,
    output_dir: Path,
) -> PrivacySafePromptPreflightReport:
    source = _make_source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
    )
    predecessor_integrity = _make_predecessor_integrity(
        package_root=package_root,
        implementation_root=implementation_root,
        execution_dir=execution_dir,
        postrun_dir=postrun_dir,
    )
    prompt_contract = _make_prompt_metadata_contract()
    loaded = _load_inputs(package_root, implementation_root)
    tasks = _make_task_packages(loaded, prompt_contract)
    catalog = _make_path_catalog(
        loaded=loaded,
        prompt_contract=prompt_contract,
        tasks=tasks,
    )
    noninterference = _make_noninterference_audit(
        package_root=package_root,
        prompt_contract=prompt_contract,
        catalog=catalog,
    )
    resource = _make_resource_contract(prompt_contract, catalog)
    qualification = _make_qualification_contract(
        prompt_contract=prompt_contract,
        noninterference=noninterference,
        tasks=tasks,
        catalog=catalog,
        resource=resource,
    )
    manifest = _make_manifest(
        loaded=loaded,
        prompt_contract=prompt_contract,
        tasks=tasks,
        catalog=catalog,
        resource=resource,
        contract=qualification,
    )
    outcome = _make_outcome_contract(qualification, manifest)
    runner_contract = _make_runner_contract(
        prompt_contract=prompt_contract,
        noninterference=noninterference,
        contract=qualification,
        manifest=manifest,
        outcome=outcome,
        resource=resource,
    )
    fixture = _make_runner_fixture(
        loaded=loaded,
        manifest=manifest,
        resource=resource,
        runner_contract=runner_contract,
    )
    controls = _make_runner_controls(
        package_root=package_root,
        loaded=loaded,
        manifest=manifest,
        resource=resource,
        runner_contract=runner_contract,
        noninterference=noninterference,
    )
    transition = _make_transition(manifest, runner_contract, outcome)
    destructive = _make_destructive(
        loaded=loaded,
        prompt_contract=prompt_contract,
        tasks=tasks,
        catalog=catalog,
        noninterference=noninterference,
        resource=resource,
        qualification=qualification,
        manifest=manifest,
        outcome=outcome,
        runner_contract=runner_contract,
        transition=transition,
        predecessor_integrity=predecessor_integrity,
    )
    prospective_execution_id = canonical_hash(
        {
            "run_id": PROSPECTIVE_EXECUTION_RUN_ID,
            "manifest_id": manifest.manifest_id,
            "runner_contract_id": runner_contract.contract_id,
            "outcome_contract_id": outcome.contract_id,
        },
        prefix="finance_v26_privacy_safe_s1_qualification_execution:",
    )
    prospective_report_id = canonical_hash(
        {
            "run_id": PROSPECTIVE_REPORT_RUN_ID,
            "prospective_execution_id": prospective_execution_id,
            "outcome_contract_id": outcome.contract_id,
        },
        prefix="finance_v26_privacy_safe_s1_qualification_execution_report:",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_values: tuple[tuple[str, BaseModel], ...] = (
        ("destructive_audit.json", destructive),
        ("predecessor_integrity_audit.json", predecessor_integrity),
        ("privacy_safe_outcome_contract.json", outcome),
        ("privacy_safe_path_catalog.json", catalog),
        ("privacy_safe_prompt_metadata_contract.json", prompt_contract),
        ("privacy_safe_qualification_contract.json", qualification),
        ("privacy_safe_qualification_manifest.json", manifest),
        ("privacy_safe_resource_contract.json", resource),
        ("privacy_safe_runner_contract.json", runner_contract),
        ("privacy_safe_runner_control_audit.json", controls),
        ("privacy_safe_runner_fixture_audit.json", fixture),
        ("privacy_safe_task_package_catalog.json", tasks),
        ("prompt_privacy_noninterference_audit.json", noninterference),
        ("prospective_transition_contract.json", transition),
        ("source_replay_audit.json", source),
    )
    for name, value in detail_values:
        _write_json_atomic(output_dir / name, value)
    details = tuple(_detail(output_dir / name, output_dir) for name, _ in detail_values)
    values = {
        "source_replay_audit_id": source.audit_id,
        "predecessor_integrity_audit_id": predecessor_integrity.audit_id,
        "prompt_metadata_contract_id": prompt_contract.contract_id,
        "task_package_catalog_id": tasks.catalog_id,
        "path_catalog_id": catalog.catalog_id,
        "noninterference_audit_id": noninterference.audit_id,
        "resource_contract_id": resource.contract_id,
        "qualification_contract_id": qualification.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "runner_contract_id": runner_contract.contract_id,
        "runner_fixture_audit_id": fixture.audit_id,
        "runner_control_audit_id": controls.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "prospective_execution_id": prospective_execution_id,
        "prospective_report_id": prospective_report_id,
        "detail_files": details,
    }
    provisional_report = PrivacySafePromptPreflightReport.model_construct(
        report_id="pending", **values
    )
    report = PrivacySafePromptPreflightReport(
        report_id=_identity(
            provisional_report,
            "report_id",
            "finance_v26_privacy_safe_s1_prompt_preflight_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.137 privacy-safe S1 Prompt Runner preflight"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--execution-dir", type=Path, default=package_default / EXECUTION_DIR)
    parser.add_argument("--postrun-dir", type=Path, default=package_default / POSTRUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_privacy_safe_prompt_preflight(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        execution_dir=args.execution_dir,
        postrun_dir=args.postrun_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
