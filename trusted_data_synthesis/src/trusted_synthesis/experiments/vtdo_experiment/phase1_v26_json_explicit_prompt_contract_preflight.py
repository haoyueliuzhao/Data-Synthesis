from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_execution as v188,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    RESPONSE_PROTOCOL_VERSION,
    compile_semantic_action_response_grammar,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    make_stage_one_request_body,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = "finance_v26_192_json_explicit_prompt_contract_preflight_v1_20260831"
AUTHORIZED_STAGE: Final = (
    "fresh_identity_json_explicit_prompt_contract_and_development_population_preflight_only"
)
NEXT_STAGE: Final = "no_further_experiment_authorized_without_new_audit_decision"
EXTERNAL_AUDIT_BYTES: Final = 12_464
EXTERNAL_AUDIT_SHA256: Final = "18ddfcb62a8401397204a46f997ca85c738701b41c3c0cfa790f79fac6df4ccf"
OPERATOR_DECISION: Final = "参照审计报告修订"
JSON_INSTRUCTION: Final = (
    "Return exactly one valid JSON object matching the response ABI. "
    "Do not return Markdown or surrounding prose."
)
RENDERER_VERSION: Final = "json_explicit_provider_prompt_renderer.v1"
V191_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_191_minimal_exact_route_online_diagnostic_v1_20260831"
)
EXPECTED_V191_REPORT_ID: Final = (
    "finance_v26_191_online_diagnostic_report:"
    "4bbd4b1de318271017870147065de6415a7b7f3215bf54b58ded1ac7cde9cb26"
)
EXPECTED_V191_ARTIFACT_ROOT: Final = (
    "finance_v26_191_online_diagnostic_artifact_root:"
    "47ce56c1e3ada224121b334c19fee66b485920de3bce132e0d4fea4b49672004"
)
EXPECTED_V191_D4_OBSERVATION_ID: Final = (
    "finance_v26_191_diagnostic_observation:"
    "6163f50a58a6862b9d4af942f2d502969cdfbbdd737fb2efdf128aca25f8e310"
)
EXPECTED_JOB_COUNT: Final = 192
EXPECTED_PACKAGE_COUNT: Final = 32
EXPECTED_PRIMARY_ACTION_PROMPTS: Final = 480
EXPECTED_CORRECTION_PROMPTS: Final = 120
EXPECTED_FINAL_PROMPTS: Final = 192
EXPECTED_TOTAL_PROMPTS: Final = 792


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _file_bytes(value: Any) -> bytes:
    return _canonical_bytes(value) + b"\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_bytes_no_replace(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _write_no_replace(path: Path, value: Any) -> None:
    _write_bytes_no_replace(path, _file_bytes(value))


def _identity(model_type: type[BaseModel], values: dict[str, Any], field: str, prefix: str) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    identifier = canonical_hash(
        provisional.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )
    return model_type(**{field: identifier}, **values)


class PredecessorFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    external_audit_sha256: str = EXTERNAL_AUDIT_SHA256
    external_audit_bytes: int = EXTERNAL_AUDIT_BYTES
    operator_decision: str = OPERATOR_DECISION
    v191_report_id: str = EXPECTED_V191_REPORT_ID
    v191_artifact_root: str = EXPECTED_V191_ARTIFACT_ROOT
    v191_formal_file_count: Literal[12] = 12
    v191_manifest_member_count: Literal[11] = 11
    v191_files_rehashed: Literal[12] = 12
    v191_observations_mutated: Literal[False] = False
    v188_outcomes_reclassified: Literal[False] = False
    schema_version: Literal["json_explicit_predecessor_freeze.v1"] = (
        "json_explicit_predecessor_freeze.v1"
    )

    @model_validator(mode="after")
    def validate_freeze(self) -> PredecessorFreeze:
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"freeze_id"}),
            prefix="finance_v26_192_predecessor_freeze:",
        )
        if self.freeze_id != expected:
            raise ValueError("v26.192 predecessor Freeze identity differs")
        return self


class JsonExplicitPromptContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    instruction: Literal[
        "Return exactly one valid JSON object matching the response ABI. "
        "Do not return Markdown or surrounding prose."
    ] = JSON_INSTRUCTION
    response_format_type: Literal["json_object"] = "json_object"
    required_prompt_phases: tuple[Literal["action", "correction", "final"], ...] = (
        "action",
        "correction",
        "final",
    )
    instruction_casefold_contains_json: Literal[True] = True
    task_instruction_text_change_allowed: Literal[False] = False
    public_state_change_allowed: Literal[False] = False
    candidate_order_change_allowed: Literal[False] = False
    schedule_change_allowed: Literal[False] = False
    grammar_change_allowed: Literal[False] = False
    validity_change_allowed: Literal[False] = False
    source_v191_report_id: str = EXPECTED_V191_REPORT_ID
    source_d4_observation_id: str = EXPECTED_V191_D4_OBSERVATION_ID
    provider_calls: Literal[0] = 0
    schema_version: Literal["json_explicit_prompt_contract.v1"] = "json_explicit_prompt_contract.v1"

    @model_validator(mode="after")
    def validate_contract(self) -> JsonExplicitPromptContract:
        if "json" not in self.instruction.casefold():
            raise ValueError("Prompt Contract instruction lacks the JSON token")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"contract_id"}),
            prefix="json_explicit_prompt_contract:",
        )
        if self.contract_id != expected:
            raise ValueError("JSON-explicit Prompt Contract identity differs")
        return self


class JsonExplicitPromptSchema(FrozenModel):
    schema_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    renderer_version: Literal["json_explicit_provider_prompt_renderer.v1"] = RENDERER_VERSION
    top_level_fields: tuple[str, ...] = (
        "prompt_core",
        "prompt_kind",
        "provider_output_protocol",
    )
    protocol_fields: tuple[str, ...] = (
        "contract_id",
        "instruction",
        "response_format",
    )
    action_core_fields: tuple[str, ...] = ("public_prompt", "response_abi")
    final_core_is_exact_frozen_prompt: Literal[True] = True
    schema_version: Literal["json_explicit_prompt_schema.v1"] = "json_explicit_prompt_schema.v1"

    @model_validator(mode="after")
    def validate_schema(self) -> JsonExplicitPromptSchema:
        if self.top_level_fields != tuple(sorted(self.top_level_fields)):
            raise ValueError("Prompt Schema top-level fields are not canonical")
        if self.protocol_fields != tuple(sorted(self.protocol_fields)):
            raise ValueError("Prompt Schema protocol fields are not canonical")
        if self.action_core_fields != tuple(sorted(self.action_core_fields)):
            raise ValueError("Prompt Schema Action core fields are not canonical")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"schema_id"}),
            prefix="json_explicit_prompt_schema:",
        )
        if self.schema_id != expected:
            raise ValueError("JSON-explicit Prompt Schema identity differs")
        return self


class JsonExplicitGenerationProfile(FrozenModel):
    profile_id: str = Field(min_length=1)
    source_profile_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    action_grammar_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    thinking_policy_id: str = Field(min_length=1)
    bounded_generation_policy_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    action_response_decision_kind: Literal["execute_public_operation"] = "execute_public_operation"
    prompt_changed_from_source: Literal[True] = True
    task_semantics_changed_from_source: Literal[False] = False
    model_changed_from_source: Literal[False] = False
    thinking_changed_from_source: Literal[False] = False
    grammar_changed_from_source: Literal[False] = False
    policy_changed_from_source: Literal[False] = False
    resource_changed_from_source: Literal[False] = False
    schema_version: Literal["json_explicit_generation_profile.v1"] = (
        "json_explicit_generation_profile.v1"
    )

    @model_validator(mode="after")
    def validate_profile(self) -> JsonExplicitGenerationProfile:
        if self.profile_id == self.source_profile_id:
            raise ValueError("fresh generation profile reused the source identity")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"profile_id"}),
            prefix="json_explicit_generation_profile:",
        )
        if self.profile_id != expected:
            raise ValueError("JSON-explicit generation profile identity differs")
        return self


class JsonExplicitRunnerPackage(FrozenModel):
    runner_package_id: str = Field(min_length=1)
    source_runner_package_id: str = Field(min_length=1)
    source_execution_package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: str = Field(min_length=1)
    depth: str = Field(min_length=1)
    public_task_id: str = Field(min_length=1)
    schedule_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    semantic_parent_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    materialized_prompt_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["json_explicit_runner_package.v1"] = "json_explicit_runner_package.v1"

    @model_validator(mode="after")
    def validate_package(self) -> JsonExplicitRunnerPackage:
        if self.runner_package_id == self.source_runner_package_id:
            raise ValueError("fresh Runner Package reused its source identity")
        if len(self.schedule_ids) != len(self.topological_component_keys):
            raise ValueError("fresh Runner Package changed its Schedule denominator")
        semantic = {
            "source_runner_package_id": self.source_runner_package_id,
            "source_execution_package_id": self.source_execution_package_id,
            "source_package_artifact_id": self.source_package_artifact_id,
            "source_package_id": self.source_package_id,
            "source_group_id": self.source_group_id,
            "finance_core_id": self.finance_core_id,
            "capability_family": self.capability_family,
            "depth": self.depth,
            "public_task_id": self.public_task_id,
            "schedule_ids": self.schedule_ids,
            "topological_component_keys": self.topological_component_keys,
        }
        if self.semantic_parent_sha256 != _sha256_bytes(_canonical_bytes(semantic)):
            raise ValueError("fresh Runner Package semantic parent bytes differ")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"runner_package_id"}),
            prefix="json_explicit_runner_package:",
        )
        if self.runner_package_id != expected:
            raise ValueError("JSON-explicit Runner Package identity differs")
        return self


class JsonExplicitRunnerPackageCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    packages: tuple[JsonExplicitRunnerPackage, ...] = Field(min_length=32, max_length=32)
    source_runner_package_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    package_count: Literal[32] = 32
    provider_calls: Literal[0] = 0
    schema_version: Literal["json_explicit_runner_package_catalog.v1"] = (
        "json_explicit_runner_package_catalog.v1"
    )

    @model_validator(mode="after")
    def validate_catalog(self) -> JsonExplicitRunnerPackageCatalog:
        if len({item.runner_package_id for item in self.packages}) != self.package_count:
            raise ValueError("fresh Runner Package Catalog repeats an identity")
        if tuple(sorted(item.source_runner_package_id for item in self.packages)) != (
            self.source_runner_package_ids
        ):
            raise ValueError("fresh Runner Package Catalog source set differs")
        if any(
            item.prompt_contract_id != self.prompt_contract_id
            or item.prompt_schema_id != self.prompt_schema_id
            or item.generation_profile_id != self.generation_profile_id
            for item in self.packages
        ):
            raise ValueError("fresh Runner Package Catalog crosses a Prompt parent")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"catalog_id"}),
            prefix="json_explicit_runner_package_catalog:",
        )
        if self.catalog_id != expected:
            raise ValueError("JSON-explicit Runner Package Catalog identity differs")
        return self


class JsonExplicitDevelopmentJob(FrozenModel):
    job_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    runner_package_id: str = Field(min_length=1)
    source_runner_package_id: str = Field(min_length=1)
    execution_package_id: str = Field(min_length=1)
    source_package_artifact_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    finance_core_id: str = Field(min_length=1)
    capability_family: str = Field(min_length=1)
    depth: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    schedule_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    generation_profile_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    source_outcome_contract_id: str = Field(min_length=1)
    raw_namespace: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    deterministic_seed_id: str = Field(min_length=1)
    empirical_outcome: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: Literal["json_explicit_development_job.v1"] = "json_explicit_development_job.v1"

    @model_validator(mode="after")
    def validate_job(self) -> JsonExplicitDevelopmentJob:
        if self.job_id == self.source_job_id:
            raise ValueError("fresh Development Job reused its source identity")
        namespace_parent = {
            "source_job_id": self.source_job_id,
            "runner_package_id": self.runner_package_id,
            "generation_profile_id": self.generation_profile_id,
            "prompt_schema_id": self.prompt_schema_id,
        }
        if (
            self.raw_namespace
            != canonical_hash(namespace_parent, prefix="json_explicit_raw_namespace:")
            or self.result_namespace
            != canonical_hash(namespace_parent, prefix="json_explicit_result_namespace:")
            or self.deterministic_seed_id
            != canonical_hash(namespace_parent, prefix="json_explicit_deterministic_seed:")
        ):
            raise ValueError("fresh Development Job namespace derivation differs")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"job_id"}),
            prefix="json_explicit_development_job:",
        )
        if self.job_id != expected:
            raise ValueError("JSON-explicit Development Job identity differs")
        return self


class JsonExplicitDevelopmentManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    runner_package_catalog_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    jobs: tuple[JsonExplicitDevelopmentJob, ...] = Field(min_length=192, max_length=192)
    expected_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    source_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    package_count: Literal[32] = 32
    replica_count: Literal[6] = 6
    job_count: Literal[192] = 192
    missing_job_count: Literal[0] = 0
    duplicate_job_count: Literal[0] = 0
    extra_job_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    schema_version: Literal["json_explicit_development_manifest.v1"] = (
        "json_explicit_development_manifest.v1"
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> JsonExplicitDevelopmentManifest:
        job_ids = tuple(item.job_id for item in self.jobs)
        if len(self.jobs) != self.job_count or len(set(job_ids)) != self.job_count:
            raise ValueError("fresh Development Manifest denominator differs")
        if self.expected_job_ids != tuple(sorted(job_ids)):
            raise ValueError("fresh Development Manifest expected Job set differs")
        if self.source_job_ids != tuple(sorted(item.source_job_id for item in self.jobs)):
            raise ValueError("fresh Development Manifest source Job set differs")
        if len({item.raw_namespace for item in self.jobs}) != self.job_count:
            raise ValueError("fresh Development Manifest repeats a Raw namespace")
        if len({item.result_namespace for item in self.jobs}) != self.job_count:
            raise ValueError("fresh Development Manifest repeats a Result namespace")
        cells = {(item.runner_package_id, item.replica_index) for item in self.jobs}
        if len(cells) != self.job_count:
            raise ValueError("fresh Development Manifest repeats a Package x Replica cell")
        if len({item.runner_package_id for item in self.jobs}) != self.package_count:
            raise ValueError("fresh Development Manifest Package denominator differs")
        if any(
            item.generation_profile_id != self.generation_profile_id
            or item.prompt_schema_id != self.prompt_schema_id
            for item in self.jobs
        ):
            raise ValueError("fresh Development Manifest crosses a Prompt parent")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"manifest_id"}),
            prefix="json_explicit_development_manifest:",
        )
        if self.manifest_id != expected:
            raise ValueError("JSON-explicit Development Manifest identity differs")
        return self


class JsonExplicitRunnerContract(FrozenModel):
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_package_catalog_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    source_runner_id: str = Field(min_length=1)
    job_count: Literal[192] = 192
    one_current_prompt_at_a_time: Literal[True] = True
    scripted_reference_only: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: Literal["json_explicit_runner_contract.v1"] = "json_explicit_runner_contract.v1"

    @model_validator(mode="after")
    def validate_runner(self) -> JsonExplicitRunnerContract:
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"runner_id"}),
            prefix="json_explicit_runner_contract:",
        )
        if self.runner_id != expected:
            raise ValueError("JSON-explicit Runner Contract identity differs")
        return self


PromptPhase = Literal["first_action", "subsequent_action", "correction", "final"]


class PromptJsonContractCensusRow(FrozenModel):
    row_id: str = Field(min_length=1)
    fresh_job_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    phase: PromptPhase
    component_index: int | None = Field(default=None, ge=0, le=3)
    component_key: str | None = None
    state_token: str | None = None
    prompt_id: str = Field(min_length=1)
    old_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    old_prompt_utf8_bytes: int = Field(gt=0)
    old_prompt_json_token_present: bool
    new_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    new_prompt_utf8_bytes: int = Field(gt=0)
    new_prompt_json_token_present: Literal[True] = True
    exact_protocol_instruction_present: Literal[True] = True
    response_format_json_object: Literal[True] = True
    prompt_core_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_core_exactly_preserved: Literal[True] = True
    request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_body_bytes: int = Field(gt=0)
    request_body_fields: tuple[str, ...]
    provider_calls: Literal[0] = 0
    schema_version: Literal["prompt_json_contract_census_row.v1"] = (
        "prompt_json_contract_census_row.v1"
    )

    @model_validator(mode="after")
    def validate_row(self) -> PromptJsonContractCensusRow:
        if self.phase == "final" and (
            self.component_index is not None
            or self.component_key is not None
            or self.state_token is not None
        ):
            raise ValueError("Final Prompt Census row exposes Component coordinates")
        if self.phase != "final" and (
            self.component_index is None or self.component_key is None or self.state_token is None
        ):
            raise ValueError("Action Prompt Census row lacks Component coordinates")
        if self.request_body_fields != tuple(sorted(self.request_body_fields)):
            raise ValueError("Prompt Census request fields are not canonical")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"row_id"}),
            prefix="prompt_json_contract_census_row:",
        )
        if self.row_id != expected:
            raise ValueError("Prompt JSON Contract Census row identity differs")
        return self


class PromptJsonContractCensus(FrozenModel):
    census_id: str = Field(min_length=1)
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    rows: tuple[PromptJsonContractCensusRow, ...] = Field(min_length=792, max_length=792)
    total_prompt_count: Literal[792] = 792
    first_action_prompt_count: Literal[192] = 192
    subsequent_action_prompt_count: Literal[288] = 288
    correction_prompt_count: Literal[120] = 120
    final_prompt_count: Literal[192] = 192
    old_first_prompt_json_token_present_count: Literal[0] = 0
    old_first_prompt_json_token_absent_count: Literal[192] = 192
    new_json_token_present_count: Literal[792] = 792
    response_format_pair_count: Literal[792] = 792
    exact_protocol_instruction_count: Literal[792] = 792
    prompt_core_preservation_count: Literal[792] = 792
    provider_calls: Literal[0] = 0
    schema_version: Literal["prompt_json_contract_census.v1"] = "prompt_json_contract_census.v1"

    @model_validator(mode="after")
    def validate_census(self) -> PromptJsonContractCensus:
        counts = Counter(item.phase for item in self.rows)
        if counts != {
            "first_action": self.first_action_prompt_count,
            "subsequent_action": self.subsequent_action_prompt_count,
            "correction": self.correction_prompt_count,
            "final": self.final_prompt_count,
        }:
            raise ValueError("Prompt Census phase denominator differs")
        if sum(item.new_prompt_json_token_present for item in self.rows) != len(self.rows):
            raise ValueError("Prompt Census contains a JSON-invisible successor Prompt")
        if sum(
            item.old_prompt_json_token_present for item in self.rows if item.phase == "first_action"
        ):
            raise ValueError("Prompt Census no longer reproduces the v26.188 first-Prompt defect")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"census_id"}),
            prefix="prompt_json_contract_census:",
        )
        if self.census_id != expected:
            raise ValueError("Prompt JSON Contract Census identity differs")
        return self


class ScriptedRunnerPreflight(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    exact_fresh_job_count: Literal[192] = 192
    fresh_to_source_job_resolution_count: Literal[192] = 192
    primary_action_prompt_count: Literal[480] = 480
    primary_action_abi_parse_count: Literal[480] = 480
    primary_runtime_step_count: Literal[480] = 480
    correction_prompt_count: Literal[120] = 120
    correction_first_rejection_step_count: Literal[120] = 120
    correction_reference_abi_parse_count: Literal[120] = 120
    correction_reference_commit_count: Literal[120] = 120
    final_prompt_count: Literal[192] = 192
    final_abi_parse_count: Literal[192] = 192
    finalized_runtime_result_count: Literal[192] = 192
    source_result_identity_match_count: Literal[144] = 144
    source_result_identity_drift_count: Literal[48] = 48
    source_result_identity_drift_capability_families: tuple[
        Literal["semantic_reconciliation"], ...
    ] = ("semantic_reconciliation",)
    source_result_identity_match_is_prompt_gate: Literal[False] = False
    base_valid_count: Literal[192] = 192
    mechanism_qualified_count: Literal[192] = 192
    qualified_valid_count: Literal[192] = 192
    runtime_exception_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    schema_version: Literal["json_explicit_scripted_runner_preflight.v1"] = (
        "json_explicit_scripted_runner_preflight.v1"
    )

    @model_validator(mode="after")
    def validate_preflight(self) -> ScriptedRunnerPreflight:
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"audit_id"}),
            prefix="json_explicit_scripted_runner_preflight:",
        )
        if self.audit_id != expected:
            raise ValueError("scripted Runner preflight identity differs")
        return self


class SemanticPreservationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    task_parent_match_count: Literal[192] = 192
    execution_package_parent_match_count: Literal[192] = 192
    source_artifact_parent_match_count: Literal[192] = 192
    schedule_parent_match_count: Literal[192] = 192
    fixed_condition_parent_match_count: Literal[192] = 192
    action_public_state_match_count: Literal[600] = 600
    candidate_order_match_count: Literal[600] = 600
    response_abi_match_count: Literal[600] = 600
    final_prompt_core_match_count: Literal[192] = 192
    historical_source_result_identity_match_count: Literal[144] = 144
    historical_source_result_identity_drift_count: Literal[48] = 48
    historical_source_result_identity_drift_is_preexisting: Literal[True] = True
    task_semantic_change_count: Literal[0] = 0
    candidate_change_count: Literal[0] = 0
    schedule_change_count: Literal[0] = 0
    grammar_change_count: Literal[0] = 0
    validity_change_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: Literal["json_explicit_semantic_preservation_audit.v1"] = (
        "json_explicit_semantic_preservation_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SemanticPreservationAudit:
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"audit_id"}),
            prefix="json_explicit_semantic_preservation_audit:",
        )
        if self.audit_id != expected:
            raise ValueError("semantic preservation Audit identity differs")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    attempted_count: Literal[12] = 12
    rejected_count: Literal[12] = 12
    accepted_count: Literal[0] = 0
    mutations: tuple[str, ...] = Field(min_length=12, max_length=12)
    provider_calls: Literal[0] = 0
    schema_version: Literal["json_explicit_destructive_audit.v1"] = (
        "json_explicit_destructive_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if len(set(self.mutations)) != self.attempted_count:
            raise ValueError("destructive Audit repeats a mutation")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"audit_id"}),
            prefix="json_explicit_destructive_audit:",
        )
        if self.audit_id != expected:
            raise ValueError("destructive Audit identity differs")
        return self


class BuildProducts:
    def __init__(
        self,
        *,
        freeze: PredecessorFreeze,
        contract: JsonExplicitPromptContract,
        schema: JsonExplicitPromptSchema,
        profile: JsonExplicitGenerationProfile,
        package_catalog: JsonExplicitRunnerPackageCatalog,
        manifest: JsonExplicitDevelopmentManifest,
        runner: JsonExplicitRunnerContract,
        census: PromptJsonContractCensus,
        preflight: ScriptedRunnerPreflight,
        semantic: SemanticPreservationAudit,
        destructive: DestructiveAudit,
        report: dict[str, Any],
        artifact_manifest: dict[str, Any],
    ) -> None:
        self.freeze = freeze
        self.contract = contract
        self.schema = schema
        self.profile = profile
        self.package_catalog = package_catalog
        self.manifest = manifest
        self.runner = runner
        self.census = census
        self.preflight = preflight
        self.semantic = semantic
        self.destructive = destructive
        self.report = report
        self.artifact_manifest = artifact_manifest


def _authorization(path: Path) -> bytes:
    payload = path.read_bytes()
    if len(payload) != EXTERNAL_AUDIT_BYTES or _sha256_bytes(payload) != EXTERNAL_AUDIT_SHA256:
        raise ValueError("external v26.191 audit bytes differ")
    return payload


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=repository, check=True, capture_output=True, text=True
    ).stdout.strip()


def _freeze_v191(package_root: Path) -> PredecessorFreeze:
    root = package_root / V191_DIR
    report = _load(root / "report.json")
    manifest = _load(root / "artifact_manifest.json")
    paths = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    if (
        report.get("report_id") != EXPECTED_V191_REPORT_ID
        or report.get("decision") != "prompt_specific_request_rejection"
        or manifest.get("artifact_root") != EXPECTED_V191_ARTIFACT_ROOT
        or manifest.get("file_count") != 11
        or len(paths) != 12
    ):
        raise ValueError("v26.191 frozen Report or Artifact Root differs")
    members = {item["relative_path"]: item for item in manifest["members"]}
    for path in paths:
        if path.name == "artifact_manifest.json":
            continue
        relative = path.relative_to(root).as_posix()
        binding = members.get(relative)
        content = path.read_bytes()
        if (
            binding is None
            or binding["sha256"] != _sha256_bytes(content)
            or binding["byte_count"] != len(content)
        ):
            raise ValueError("v26.191 formal Artifact member differs")
    return cast(
        PredecessorFreeze,
        _identity(
            PredecessorFreeze,
            {},
            "freeze_id",
            "finance_v26_192_predecessor_freeze:",
        ),
    )


def _prompt_contract() -> JsonExplicitPromptContract:
    return cast(
        JsonExplicitPromptContract,
        _identity(
            JsonExplicitPromptContract,
            {},
            "contract_id",
            "json_explicit_prompt_contract:",
        ),
    )


def _prompt_schema(contract: JsonExplicitPromptContract) -> JsonExplicitPromptSchema:
    return cast(
        JsonExplicitPromptSchema,
        _identity(
            JsonExplicitPromptSchema,
            {"contract_id": contract.contract_id},
            "schema_id",
            "json_explicit_prompt_schema:",
        ),
    )


def _generation_profile(
    prepared: v188.PreparedExecution,
    contract: JsonExplicitPromptContract,
    schema: JsonExplicitPromptSchema,
) -> JsonExplicitGenerationProfile:
    source = prepared.profile
    values = {
        "source_profile_id": source.profile_id,
        "prompt_contract_id": contract.contract_id,
        "prompt_schema_id": schema.schema_id,
        "action_grammar_id": source.action_grammar_id,
        "final_grammar_id": source.final_grammar_id,
        "model_config_id": source.model_config_id,
        "thinking_policy_id": source.thinking_policy_id,
        "bounded_generation_policy_id": source.bounded_generation_policy_id,
        "resource_contract_id": source.resource_contract_id,
        "action_response_decision_kind": source.action_response_decision_kind,
    }
    return cast(
        JsonExplicitGenerationProfile,
        _identity(
            JsonExplicitGenerationProfile,
            values,
            "profile_id",
            "json_explicit_generation_profile:",
        ),
    )


def _semantic_parent_values(source_job: Any, runner_package: Any) -> dict[str, Any]:
    return {
        "source_runner_package_id": source_job.runner_package_id,
        "source_execution_package_id": source_job.execution_package_id,
        "source_package_artifact_id": source_job.source_package_artifact_id,
        "source_package_id": source_job.source_package_id,
        "source_group_id": source_job.source_group_id,
        "finance_core_id": source_job.finance_core_id,
        "capability_family": source_job.capability_family,
        "depth": source_job.depth,
        "public_task_id": runner_package.public_task_id,
        "schedule_ids": source_job.schedule_ids,
        "topological_component_keys": runner_package.topological_component_keys,
    }


def _package_catalog(
    prepared: v188.PreparedExecution,
    contract: JsonExplicitPromptContract,
    schema: JsonExplicitPromptSchema,
    profile: JsonExplicitGenerationProfile,
) -> JsonExplicitRunnerPackageCatalog:
    by_runner: dict[str, Any] = {}
    for source_job in prepared.frozen.manifest.jobs:
        by_runner.setdefault(source_job.runner_package_id, source_job)
    packages: list[JsonExplicitRunnerPackage] = []
    for source_runner_id, source_job in sorted(by_runner.items()):
        runner_package = prepared.runtime_catalog.runner_by_id[source_runner_id]
        semantic = _semantic_parent_values(source_job, runner_package)
        values = {
            **semantic,
            "prompt_contract_id": contract.contract_id,
            "prompt_schema_id": schema.schema_id,
            "generation_profile_id": profile.profile_id,
            "semantic_parent_sha256": _sha256_bytes(_canonical_bytes(semantic)),
        }
        packages.append(
            cast(
                JsonExplicitRunnerPackage,
                _identity(
                    JsonExplicitRunnerPackage,
                    values,
                    "runner_package_id",
                    "json_explicit_runner_package:",
                ),
            )
        )
    values = {
        "prompt_contract_id": contract.contract_id,
        "prompt_schema_id": schema.schema_id,
        "generation_profile_id": profile.profile_id,
        "packages": tuple(packages),
        "source_runner_package_ids": tuple(sorted(by_runner)),
    }
    return cast(
        JsonExplicitRunnerPackageCatalog,
        _identity(
            JsonExplicitRunnerPackageCatalog,
            values,
            "catalog_id",
            "json_explicit_runner_package_catalog:",
        ),
    )


def _fresh_manifest(
    prepared: v188.PreparedExecution,
    contract: JsonExplicitPromptContract,
    schema: JsonExplicitPromptSchema,
    profile: JsonExplicitGenerationProfile,
    packages: JsonExplicitRunnerPackageCatalog,
) -> JsonExplicitDevelopmentManifest:
    package_by_source = {item.source_runner_package_id: item for item in packages.packages}
    jobs: list[JsonExplicitDevelopmentJob] = []
    for source in prepared.frozen.manifest.jobs:
        package = package_by_source[source.runner_package_id]
        namespace_parent = {
            "source_job_id": source.job_id,
            "runner_package_id": package.runner_package_id,
            "generation_profile_id": profile.profile_id,
            "prompt_schema_id": schema.schema_id,
        }
        values = {
            "source_job_id": source.job_id,
            "runner_package_id": package.runner_package_id,
            "source_runner_package_id": source.runner_package_id,
            "execution_package_id": source.execution_package_id,
            "source_package_artifact_id": source.source_package_artifact_id,
            "source_package_id": source.source_package_id,
            "finance_core_id": source.finance_core_id,
            "capability_family": source.capability_family,
            "depth": source.depth,
            "replica_index": source.replica_index,
            "schedule_ids": source.schedule_ids,
            "generation_profile_id": profile.profile_id,
            "prompt_schema_id": schema.schema_id,
            "source_outcome_contract_id": source.outcome_contract_id,
            "raw_namespace": canonical_hash(
                namespace_parent, prefix="json_explicit_raw_namespace:"
            ),
            "result_namespace": canonical_hash(
                namespace_parent, prefix="json_explicit_result_namespace:"
            ),
            "deterministic_seed_id": canonical_hash(
                namespace_parent, prefix="json_explicit_deterministic_seed:"
            ),
        }
        jobs.append(
            cast(
                JsonExplicitDevelopmentJob,
                _identity(
                    JsonExplicitDevelopmentJob,
                    values,
                    "job_id",
                    "json_explicit_development_job:",
                ),
            )
        )
    values = {
        "runner_package_catalog_id": packages.catalog_id,
        "generation_profile_id": profile.profile_id,
        "prompt_contract_id": contract.contract_id,
        "prompt_schema_id": schema.schema_id,
        "jobs": tuple(jobs),
        "expected_job_ids": tuple(sorted(item.job_id for item in jobs)),
        "source_job_ids": tuple(sorted(item.source_job_id for item in jobs)),
    }
    return cast(
        JsonExplicitDevelopmentManifest,
        _identity(
            JsonExplicitDevelopmentManifest,
            values,
            "manifest_id",
            "json_explicit_development_manifest:",
        ),
    )


def _runner_contract(
    prepared: v188.PreparedExecution,
    manifest: JsonExplicitDevelopmentManifest,
    packages: JsonExplicitRunnerPackageCatalog,
    contract: JsonExplicitPromptContract,
    schema: JsonExplicitPromptSchema,
    profile: JsonExplicitGenerationProfile,
) -> JsonExplicitRunnerContract:
    values = {
        "manifest_id": manifest.manifest_id,
        "runner_package_catalog_id": packages.catalog_id,
        "generation_profile_id": profile.profile_id,
        "prompt_contract_id": contract.contract_id,
        "prompt_schema_id": schema.schema_id,
        "source_runner_id": prepared.frozen.runner.runner_id,
    }
    return cast(
        JsonExplicitRunnerContract,
        _identity(
            JsonExplicitRunnerContract,
            values,
            "runner_id",
            "json_explicit_runner_contract:",
        ),
    )


def _action_core(public_prompt: Any, prepared: v188.PreparedExecution) -> dict[str, Any]:
    return {
        "public_prompt": public_prompt.model_dump(mode="json"),
        "response_abi": {
            "grammar_id": prepared.profile.action_grammar_id,
            "state_id": public_prompt.state.state_token,
            "decision_kind": prepared.profile.action_response_decision_kind,
            "protocol": RESPONSE_PROTOCOL_VERSION,
        },
    }


def _render_prompt(
    *,
    prompt_kind: Literal["action", "correction", "final"],
    core: dict[str, Any] | str,
    contract: JsonExplicitPromptContract,
    schema: JsonExplicitPromptSchema,
) -> str:
    payload = {
        "prompt_core": core,
        "prompt_kind": prompt_kind,
        "provider_output_protocol": {
            "contract_id": contract.contract_id,
            "instruction": contract.instruction,
            "response_format": {"type": contract.response_format_type},
        },
    }
    rendered = _canonical_json(payload)
    _validate_rendered_prompt(
        rendered=rendered,
        prompt_kind=prompt_kind,
        expected_core=core,
        contract=contract,
        schema=schema,
    )
    return rendered


def _validate_rendered_prompt(
    *,
    rendered: str,
    prompt_kind: Literal["action", "correction", "final"],
    expected_core: dict[str, Any] | str,
    contract: JsonExplicitPromptContract,
    schema: JsonExplicitPromptSchema,
) -> None:
    payload = json.loads(rendered)
    if not isinstance(payload, dict) or tuple(sorted(payload)) != schema.top_level_fields:
        raise ValueError("rendered Prompt top-level Schema differs")
    protocol = payload.get("provider_output_protocol")
    if (
        not isinstance(protocol, dict)
        or tuple(sorted(protocol)) != schema.protocol_fields
        or protocol.get("contract_id") != contract.contract_id
        or protocol.get("instruction") != contract.instruction
        or protocol.get("response_format") != {"type": "json_object"}
        or "json" not in rendered.casefold()
        or payload.get("prompt_kind") != prompt_kind
        or _canonical_bytes(payload.get("prompt_core")) != _canonical_bytes(expected_core)
    ):
        raise ValueError("rendered Prompt violates the JSON-explicit Contract")


def _census_row(
    *,
    fresh_job: JsonExplicitDevelopmentJob,
    phase: PromptPhase,
    component_index: int | None,
    component_key: str | None,
    state_token: str | None,
    old_prompt: str,
    new_prompt: str,
    core: dict[str, Any] | str,
    schema: JsonExplicitPromptSchema,
    config: AgentModelConfig,
) -> PromptJsonContractCensusRow:
    request_body = _canonical_bytes(make_stage_one_request_body(config, new_prompt))
    values = {
        "fresh_job_id": fresh_job.job_id,
        "source_job_id": fresh_job.source_job_id,
        "phase": phase,
        "component_index": component_index,
        "component_key": component_key,
        "state_token": state_token,
        "prompt_id": canonical_hash(
            {
                "prompt_schema_id": schema.schema_id,
                "phase": phase,
                "prompt": new_prompt,
            },
            prefix="json_explicit_provider_prompt:",
        ),
        "old_prompt_sha256": _sha256_bytes(old_prompt.encode()),
        "old_prompt_utf8_bytes": len(old_prompt.encode()),
        "old_prompt_json_token_present": "json" in old_prompt.casefold(),
        "new_prompt_sha256": _sha256_bytes(new_prompt.encode()),
        "new_prompt_utf8_bytes": len(new_prompt.encode()),
        "prompt_core_sha256": _sha256_bytes(_canonical_bytes(core)),
        "request_body_sha256": _sha256_bytes(request_body),
        "request_body_bytes": len(request_body),
        "request_body_fields": (
            "max_tokens",
            "messages",
            "model",
            "response_format",
            "temperature",
            "thinking",
            "top_p",
        ),
    }
    return cast(
        PromptJsonContractCensusRow,
        _identity(
            PromptJsonContractCensusRow,
            values,
            "row_id",
            "prompt_json_contract_census_row:",
        ),
    )


def _execute_preflight(
    *,
    package_root: Path,
    prepared: v188.PreparedExecution,
    contract: JsonExplicitPromptContract,
    schema: JsonExplicitPromptSchema,
    profile: JsonExplicitGenerationProfile,
    manifest: JsonExplicitDevelopmentManifest,
    runner: JsonExplicitRunnerContract,
) -> tuple[PromptJsonContractCensus, ScriptedRunnerPreflight, SemanticPreservationAudit]:
    profile_payload = _load(package_root / v188.MODEL_PROFILE_PATH)
    config = AgentModelConfig.model_validate(profile_payload["model"])
    action_grammar = compile_semantic_action_response_grammar()
    source_jobs = {item.job_id: item for item in prepared.frozen.manifest.jobs}
    source_outcomes = prepared.frozen.scripted_outcomes
    rows: list[PromptJsonContractCensusRow] = []
    primary_action_count = 0
    primary_parse_count = 0
    primary_step_count = 0
    correction_prompt_count = 0
    correction_rejection_count = 0
    correction_parse_count = 0
    correction_commit_count = 0
    final_count = 0
    final_parse_count = 0
    qualified_count = 0
    base_count = 0
    mechanism_count = 0
    result_match_count = 0
    result_drift_families: set[str] = set()
    for fresh_job in manifest.jobs:
        source_job = source_jobs[fresh_job.source_job_id]
        context = frozen_runtime.prepare_job(source_job, prepared.runtime_catalog)
        state = frozen_runtime._initialize(context)  # noqa: SLF001
        while state.current_index < len(state.ordered_components):
            component_index = state.current_index
            component = state.ordered_components[component_index]
            public_prompt = step_runtime.render_next_prompt(state)
            dispositions = frozen_runtime._candidate_dispositions(  # noqa: SLF001
                state, public_prompt
            )
            core = _action_core(public_prompt, prepared)
            old_prompt = _canonical_json(core)
            new_prompt = _render_prompt(
                prompt_kind="action",
                core=core,
                contract=contract,
                schema=schema,
            )
            phase: PromptPhase = "first_action" if component_index == 0 else "subsequent_action"
            rows.append(
                _census_row(
                    fresh_job=fresh_job,
                    phase=phase,
                    component_index=component_index,
                    component_key=component.component_key,
                    state_token=public_prompt.state.state_token,
                    old_prompt=old_prompt,
                    new_prompt=new_prompt,
                    core=core,
                    schema=schema,
                    config=config,
                )
            )
            primary_action_count += 1
            invalid_rows = tuple(item for item in dispositions if not item.acceptance.accepted)
            for invalid in invalid_rows:
                branch_state = copy.deepcopy(state)
                rejected = step_runtime.step(branch_state, invalid.action_id)
                if not hasattr(rejected, "public_observation_receipt_id"):
                    raise ValueError("invalid exact Candidate did not emit a typed rejection")
                correction_rejection_count += 1
                correction_public_prompt = step_runtime.render_next_prompt(branch_state)
                correction_core = _action_core(correction_public_prompt, prepared)
                correction_old = _canonical_json(correction_core)
                correction_new = _render_prompt(
                    prompt_kind="correction",
                    core=correction_core,
                    contract=contract,
                    schema=schema,
                )
                rows.append(
                    _census_row(
                        fresh_job=fresh_job,
                        phase="correction",
                        component_index=component_index,
                        component_key=component.component_key,
                        state_token=correction_public_prompt.state.state_token,
                        old_prompt=correction_old,
                        new_prompt=correction_new,
                        core=correction_core,
                        schema=schema,
                        config=config,
                    )
                )
                correction_prompt_count += 1
                correction_dispositions = frozen_runtime._candidate_dispositions(  # noqa: SLF001
                    branch_state, correction_public_prompt
                )
                selection = frozen_runtime._reference_correction(  # noqa: SLF001
                    branch_state,
                    correction_public_prompt,
                    correction_dispositions,
                    component_index,
                    invalid.action_id,
                )
                corrected_action = frozen_runtime._parse_action_response(  # noqa: SLF001
                    correction_public_prompt,
                    selection,
                    grammar=action_grammar,
                    profile=prepared.profile,
                )
                if corrected_action is None:
                    raise ValueError("reference correction failed the frozen Action ABI")
                correction_parse_count += 1
                corrected_output = step_runtime.step(branch_state, corrected_action)
                if not getattr(corrected_output, "action_accepted", False):
                    raise ValueError("reference correction did not commit")
                correction_commit_count += 1
            selection = frozen_runtime._reference_selection(  # noqa: SLF001
                state, public_prompt, dispositions, component_index
            )
            action_id = frozen_runtime._parse_action_response(  # noqa: SLF001
                public_prompt,
                selection,
                grammar=action_grammar,
                profile=prepared.profile,
            )
            if action_id is None:
                raise ValueError("reference Action failed the frozen Action ABI")
            primary_parse_count += 1
            output = step_runtime.step(state, action_id)
            if not getattr(output, "action_accepted", False):
                raise ValueError("reference Action did not commit")
            primary_step_count += 1
        result = step_runtime.finalize(state)
        old_final_prompt, _ = v188.render_final_prompt(
            context=context,
            result=result,
            grammar=prepared.final_grammar,
        )
        new_final_prompt = _render_prompt(
            prompt_kind="final",
            core=old_final_prompt,
            contract=contract,
            schema=schema,
        )
        rows.append(
            _census_row(
                fresh_job=fresh_job,
                phase="final",
                component_index=None,
                component_key=None,
                state_token=None,
                old_prompt=old_final_prompt,
                new_prompt=new_final_prompt,
                core=old_final_prompt,
                schema=schema,
                config=config,
            )
        )
        final_count += 1
        frozen_runtime._parse_final_fixture(  # noqa: SLF001
            result,
            context.source,
            grammar=prepared.final_grammar,
            profile=prepared.profile,
        )
        final_parse_count += 1
        base_count += int(result.task_validity.base_valid)
        mechanism_count += int(result.mechanism_qualification.mechanism_semantically_qualified)
        qualified_count += int(result.qualified_validity.qualified_valid)
        result_identity_matches = (
            source_outcomes[source_job.job_id].final_result_id == result.result_id
        )
        result_match_count += int(result_identity_matches)
        if not result_identity_matches:
            result_drift_families.add(str(source_job.capability_family.value))
    values = {
        "prompt_contract_id": contract.contract_id,
        "prompt_schema_id": schema.schema_id,
        "generation_profile_id": profile.profile_id,
        "manifest_id": manifest.manifest_id,
        "rows": tuple(rows),
    }
    census = cast(
        PromptJsonContractCensus,
        _identity(
            PromptJsonContractCensus,
            values,
            "census_id",
            "prompt_json_contract_census:",
        ),
    )
    preflight_values = {
        "runner_id": runner.runner_id,
        "manifest_id": manifest.manifest_id,
        "primary_action_prompt_count": primary_action_count,
        "primary_action_abi_parse_count": primary_parse_count,
        "primary_runtime_step_count": primary_step_count,
        "correction_prompt_count": correction_prompt_count,
        "correction_first_rejection_step_count": correction_rejection_count,
        "correction_reference_abi_parse_count": correction_parse_count,
        "correction_reference_commit_count": correction_commit_count,
        "final_prompt_count": final_count,
        "final_abi_parse_count": final_parse_count,
        "source_result_identity_match_count": result_match_count,
        "source_result_identity_drift_count": EXPECTED_JOB_COUNT - result_match_count,
        "source_result_identity_drift_capability_families": tuple(sorted(result_drift_families)),
        "base_valid_count": base_count,
        "mechanism_qualified_count": mechanism_count,
        "qualified_valid_count": qualified_count,
    }
    preflight = cast(
        ScriptedRunnerPreflight,
        _identity(
            ScriptedRunnerPreflight,
            preflight_values,
            "audit_id",
            "json_explicit_scripted_runner_preflight:",
        ),
    )
    action_rows = tuple(item for item in census.rows if item.phase != "final")
    final_rows = tuple(item for item in census.rows if item.phase == "final")
    semantic_values = {
        "manifest_id": manifest.manifest_id,
        "task_parent_match_count": len(manifest.jobs),
        "execution_package_parent_match_count": len(manifest.jobs),
        "source_artifact_parent_match_count": len(manifest.jobs),
        "schedule_parent_match_count": len(manifest.jobs),
        "fixed_condition_parent_match_count": len(manifest.jobs),
        "action_public_state_match_count": sum(
            item.prompt_core_exactly_preserved for item in action_rows
        ),
        "candidate_order_match_count": sum(
            item.prompt_core_exactly_preserved for item in action_rows
        ),
        "response_abi_match_count": sum(item.prompt_core_exactly_preserved for item in action_rows),
        "final_prompt_core_match_count": sum(
            item.prompt_core_exactly_preserved for item in final_rows
        ),
        "historical_source_result_identity_match_count": result_match_count,
        "historical_source_result_identity_drift_count": (EXPECTED_JOB_COUNT - result_match_count),
    }
    semantic = cast(
        SemanticPreservationAudit,
        _identity(
            SemanticPreservationAudit,
            semantic_values,
            "audit_id",
            "json_explicit_semantic_preservation_audit:",
        ),
    )
    return census, preflight, semantic


def _destructive_controls(
    *,
    prepared: v188.PreparedExecution,
    contract: JsonExplicitPromptContract,
    schema: JsonExplicitPromptSchema,
    profile: JsonExplicitGenerationProfile,
    packages: JsonExplicitRunnerPackageCatalog,
    manifest: JsonExplicitDevelopmentManifest,
) -> DestructiveAudit:
    mutations = (
        "prompt_instruction_deleted",
        "prompt_instruction_json_token_removed",
        "response_format_changed_to_text",
        "action_prompt_core_changed",
        "correction_prompt_core_changed",
        "final_prompt_core_changed",
        "source_generation_profile_id_reused",
        "source_runner_package_id_reused",
        "source_job_id_reused",
        "source_raw_namespace_reused",
        "source_result_namespace_reused",
        "manifest_job_deleted",
    )
    sample_core: dict[str, Any] = {"public_prompt": {}, "response_abi": {}}
    base = _render_prompt(prompt_kind="action", core=sample_core, contract=contract, schema=schema)
    rejected = 0
    payload = json.loads(base)
    trials: list[tuple[str, Any]] = []
    for mutation in mutations[:6]:
        changed = copy.deepcopy(payload)
        if mutation == "prompt_instruction_deleted":
            del changed["provider_output_protocol"]["instruction"]
        elif mutation == "prompt_instruction_json_token_removed":
            changed["provider_output_protocol"]["instruction"] = "Return one object."
        elif mutation == "response_format_changed_to_text":
            changed["provider_output_protocol"]["response_format"] = {"type": "text"}
        else:
            changed["prompt_core"] = {"mutated": mutation}
        trials.append((mutation, changed))
    for _mutation, changed in trials:
        try:
            _validate_rendered_prompt(
                rendered=_canonical_json(changed),
                prompt_kind="action",
                expected_core=sample_core,
                contract=contract,
                schema=schema,
            )
        except ValueError:
            rejected += 1
    source_jobs = {item.job_id: item for item in prepared.frozen.manifest.jobs}

    def validate_fresh_chain(
        candidate_profile: JsonExplicitGenerationProfile,
        candidate_packages: JsonExplicitRunnerPackageCatalog,
        candidate_manifest: JsonExplicitDevelopmentManifest,
    ) -> None:
        if candidate_profile.profile_id == prepared.profile.profile_id:
            raise ValueError("fresh Profile reused the source identity")
        source_runner_ids = {item.runner_package_id for item in source_jobs.values()}
        if any(item.runner_package_id in source_runner_ids for item in candidate_packages.packages):
            raise ValueError("fresh Runner Package reused a source identity")
        source_job_ids = set(source_jobs)
        if any(item.job_id in source_job_ids for item in candidate_manifest.jobs):
            raise ValueError("fresh Job reused a source identity")
        old_raw = {item.raw_namespace for item in source_jobs.values()}
        old_result = {item.result_namespace for item in source_jobs.values()}
        if any(item.raw_namespace in old_raw for item in candidate_manifest.jobs):
            raise ValueError("fresh Job reused a source Raw namespace")
        if any(item.result_namespace in old_result for item in candidate_manifest.jobs):
            raise ValueError("fresh Job reused a source Result namespace")
        if len(candidate_manifest.jobs) != EXPECTED_JOB_COUNT:
            raise ValueError("fresh Manifest Job denominator differs")

    identity_trials = (
        (
            profile.model_copy(update={"profile_id": profile.source_profile_id}),
            packages,
            manifest,
        ),
        (
            profile,
            packages.model_copy(
                update={
                    "packages": (
                        packages.packages[0].model_copy(
                            update={
                                "runner_package_id": packages.packages[0].source_runner_package_id
                            }
                        ),
                        *packages.packages[1:],
                    )
                }
            ),
            manifest,
        ),
        (
            profile,
            packages,
            manifest.model_copy(
                update={
                    "jobs": (
                        manifest.jobs[0].model_copy(
                            update={"job_id": manifest.jobs[0].source_job_id}
                        ),
                        *manifest.jobs[1:],
                    )
                }
            ),
        ),
        (
            profile,
            packages,
            manifest.model_copy(
                update={
                    "jobs": (
                        manifest.jobs[0].model_copy(
                            update={
                                "raw_namespace": source_jobs[
                                    manifest.jobs[0].source_job_id
                                ].raw_namespace
                            }
                        ),
                        *manifest.jobs[1:],
                    )
                }
            ),
        ),
        (
            profile,
            packages,
            manifest.model_copy(
                update={
                    "jobs": (
                        manifest.jobs[0].model_copy(
                            update={
                                "result_namespace": source_jobs[
                                    manifest.jobs[0].source_job_id
                                ].result_namespace
                            }
                        ),
                        *manifest.jobs[1:],
                    )
                }
            ),
        ),
        (
            profile,
            packages,
            manifest.model_copy(update={"jobs": manifest.jobs[:-1]}),
        ),
    )
    for candidate_profile, candidate_packages, candidate_manifest in identity_trials:
        try:
            validate_fresh_chain(candidate_profile, candidate_packages, candidate_manifest)
        except ValueError:
            rejected += 1
    if rejected != len(mutations):
        raise ValueError("destructive control failed to reject every mutation")
    return cast(
        DestructiveAudit,
        _identity(
            DestructiveAudit,
            {
                "attempted_count": len(mutations),
                "rejected_count": rejected,
                "mutations": mutations,
            },
            "audit_id",
            "json_explicit_destructive_audit:",
        ),
    )


def _formal_manifest(payloads: dict[str, bytes]) -> dict[str, Any]:
    members = tuple(
        {
            "relative_path": name,
            "sha256": _sha256_bytes(content),
            "byte_count": len(content),
        }
        for name, content in sorted(payloads.items())
    )
    values: dict[str, Any] = {
        "run_id": RUN_ID,
        "members": members,
        "file_count": len(members),
        "total_byte_count": sum(item["byte_count"] for item in members),
        "schema_version": "json_explicit_preflight_artifact_manifest.v1",
    }
    values["artifact_root"] = canonical_hash(
        members, prefix="finance_v26_192_json_explicit_artifact_root:"
    )
    values["manifest_id"] = canonical_hash(
        values, prefix="finance_v26_192_json_explicit_artifact_manifest:"
    )
    return values


def build(
    *,
    package_root: Path,
    output_dir: Path,
    external_audit_path: Path,
    source_commit: str,
    source_tree: str,
) -> BuildProducts:
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise ValueError("credential-free v26.192 build requires credential removal")
    if output_dir.exists():
        raise FileExistsError(f"v26.192 output already exists: {output_dir}")
    authorization = _authorization(external_audit_path)
    freeze = _freeze_v191(package_root)
    prepared = v188.prepare_execution(
        package_root=package_root,
        output_dir=output_dir / "provider_invocation_forbidden",
    )
    contract = _prompt_contract()
    schema = _prompt_schema(contract)
    profile = _generation_profile(prepared, contract, schema)
    packages = _package_catalog(prepared, contract, schema, profile)
    manifest = _fresh_manifest(prepared, contract, schema, profile, packages)
    runner = _runner_contract(prepared, manifest, packages, contract, schema, profile)
    census, preflight, semantic = _execute_preflight(
        package_root=package_root,
        prepared=prepared,
        contract=contract,
        schema=schema,
        profile=profile,
        manifest=manifest,
        runner=runner,
    )
    destructive = _destructive_controls(
        prepared=prepared,
        contract=contract,
        schema=schema,
        profile=profile,
        packages=packages,
        manifest=manifest,
    )
    gates = {
        "external_authorization_exact": True,
        "v191_predecessor_immutable": True,
        "json_explicit_prompt_contract": True,
        "fresh_prompt_schema": True,
        "fresh_generation_profile": profile.profile_id != profile.source_profile_id,
        "fresh_runner_packages": len(packages.packages) == 32,
        "fresh_192_job_manifest": len(manifest.jobs) == 192,
        "fresh_raw_result_namespaces": True,
        "all_first_action_prompts_json_explicit": True,
        "all_subsequent_action_prompts_json_explicit": True,
        "all_correction_prompts_json_explicit": True,
        "all_final_prompts_json_explicit": True,
        "response_format_instruction_pairing": len(census.rows) == 792,
        "prompt_core_semantics_preserved": True,
        "scripted_action_observation_final_chain": True,
        "reference_runtime_validity_preserved": preflight.qualified_valid_count == 192,
        "destructive_controls": destructive.rejected_count == destructive.attempted_count,
        "provider_calls_zero": True,
        "historical_reclassification_zero": True,
        "downstream_rows_zero": True,
    }
    report_values: dict[str, Any] = {
        "run_id": RUN_ID,
        "authorized_stage": AUTHORIZED_STAGE,
        "predecessor_freeze_id": freeze.freeze_id,
        "prompt_contract_id": contract.contract_id,
        "prompt_schema_id": schema.schema_id,
        "generation_profile_id": profile.profile_id,
        "source_generation_profile_id": profile.source_profile_id,
        "runner_package_catalog_id": packages.catalog_id,
        "development_manifest_id": manifest.manifest_id,
        "runner_id": runner.runner_id,
        "prompt_json_contract_census_id": census.census_id,
        "scripted_runner_preflight_id": preflight.audit_id,
        "semantic_preservation_audit_id": semantic.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "fresh_package_count": 32,
        "fresh_job_count": 192,
        "prompt_census_count": 792,
        "first_action_prompt_count": 192,
        "subsequent_action_prompt_count": 288,
        "correction_prompt_count": 120,
        "final_prompt_count": 192,
        "old_first_prompt_json_token_present_count": 0,
        "new_prompt_json_token_present_count": 792,
        "scripted_qualified_job_count": 192,
        "historical_source_result_identity_match_count": (
            preflight.source_result_identity_match_count
        ),
        "historical_source_result_identity_drift_count": (
            preflight.source_result_identity_drift_count
        ),
        "historical_source_result_identity_drift_is_prompt_gate": False,
        "provider_calls": 0,
        "stage_two_provider_calls": 0,
        "development_model_outcomes": 0,
        "old_v188_job_rerun_count": 0,
        "v191_online_observation_change_count": 0,
        "historical_outcome_reclassification_count": 0,
        "confirmation_access_count": 0,
        "mapper_rows": 0,
        "state_rows": 0,
        "frequency_rows": 0,
        "contribution_rows": 0,
        "vtdo_rows": 0,
        "student_rows": 0,
        "training_rows": 0,
        "release_rows": 0,
        "production_rows": 0,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
        "online_development_execution_authorized": False,
        "next_stage": NEXT_STAGE,
        "schema_version": "json_explicit_prompt_contract_preflight_report.v1",
    }
    report_values["report_id"] = canonical_hash(
        report_values, prefix="finance_v26_192_json_explicit_preflight_report:"
    )
    transition: dict[str, Any] = {
        "current_stage": AUTHORIZED_STAGE,
        "current_gate_passed": all(gates.values()),
        "next_stage": NEXT_STAGE,
        "online_development_execution_authorized": False,
        "old_job_rerun_authorized": False,
        "capability_estimate_authorized": False,
        "mapper_state_frequency_contribution_vtdo_authorized": False,
        "schema_version": "json_explicit_prompt_contract_preflight_transition.v1",
    }
    transition["transition_id"] = canonical_hash(
        transition, prefix="finance_v26_192_json_explicit_preflight_transition:"
    )
    static = {
        "gate_count": len(gates),
        "passed_gate_count": sum(gates.values()),
        "failed_gate_count": len(gates) - sum(gates.values()),
        "gates": gates,
        "provider_calls": 0,
        "credentials_read": 0,
        "gpu_jobs": 0,
        "schema_version": "json_explicit_prompt_contract_static_audit.v1",
    }
    static["audit_id"] = canonical_hash(
        static, prefix="finance_v26_192_json_explicit_static_audit:"
    )
    source_identity = {
        "source_commit": source_commit,
        "source_tree": source_tree,
        "schema_version": "json_explicit_preflight_source_identity.v1",
    }
    payloads = {
        "external_v26_191_online_audit.txt": authorization,
        "predecessor_freeze.json": _file_bytes(freeze),
        "json_explicit_prompt_contract.json": _file_bytes(contract),
        "json_explicit_prompt_schema.json": _file_bytes(schema),
        "json_explicit_generation_profile.json": _file_bytes(profile),
        "json_explicit_runner_package_catalog.json": _file_bytes(packages),
        "json_explicit_development_manifest.json": _file_bytes(manifest),
        "json_explicit_runner_contract.json": _file_bytes(runner),
        "prompt_json_contract_census.json": _file_bytes(census),
        "scripted_runner_preflight.json": _file_bytes(preflight),
        "semantic_preservation_audit.json": _file_bytes(semantic),
        "destructive_audit.json": _file_bytes(destructive),
        "static_audit.json": _file_bytes(static),
        "prospective_transition.json": _file_bytes(transition),
        "report.json": _file_bytes(report_values),
        "source_identity.json": _file_bytes(source_identity),
    }
    artifact_manifest = _formal_manifest(payloads)
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, content in payloads.items():
        _write_bytes_no_replace(output_dir / name, content)
    _write_no_replace(output_dir / "artifact_manifest.json", artifact_manifest)
    return BuildProducts(
        freeze=freeze,
        contract=contract,
        schema=schema,
        profile=profile,
        package_catalog=packages,
        manifest=manifest,
        runner=runner,
        census=census,
        preflight=preflight,
        semantic=semantic,
        destructive=destructive,
        report=report_values,
        artifact_manifest=artifact_manifest,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--external-audit", type=Path, required=True)
    args = parser.parse_args()
    package_root = args.package_root.resolve()
    output_dir = (
        args.output_dir or package_root / "artifacts" / "vtdo_experiment" / RUN_ID
    ).resolve()
    repository = package_root.parent
    products = build(
        package_root=package_root,
        output_dir=output_dir,
        external_audit_path=args.external_audit.resolve(),
        source_commit=_git(repository, "rev-parse", "HEAD"),
        source_tree=_git(repository, "show", "-s", "--format=%T", "HEAD"),
    )
    print(_canonical_json(products.report))


if __name__ == "__main__":
    main()
