from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.domains.finance.public_tool_results import (
    SUCCESS_MODELS,
    FailedResultPublic,
    PublicCompletionState,
    PublicRetryContract,
    finance_public_result_contract_manifest,
    validate_finance_public_tool_result,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    _make_terminals,
    make_submechanism_behavior_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    _execute_stage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    _load_records,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_policy import (
    FinanceStoppingShapePolicyContract,
    make_stopping_shape_policy_observations,
    make_stopping_shape_policy_report,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_policy_protocol import (
    FinanceStoppingInstrumentResetGrammarProtocol,
    FinanceStoppingShapePolicyPopulation,
    load_stopping_shape_grammar_protocol,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability_protocol import (
    FrozenArtifactReference,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import (
    ITERATIVE_AGENT_AUDIT_VERSION,
    ITERATIVE_AGENT_FAILURE_ARTIFACT_VERSION,
    IterativeAgentFailureArtifact,
    _assert_no_model_forbidden_prompt,
    _noninterference_scanner_manifest_hash,
    _prompt_noninterference_attestation_hash,
    _sha256_text,
    model_input_projection_manifest,
)
from trusted_synthesis.runtime.tools import (
    RESERVED_HOST_RESULT_KEYS,
    RESERVED_HOST_RESULT_MARKERS,
    AgentToolResult,
    reserved_host_marker_paths,
    reserved_host_result_paths,
)

STOPPING_INSTRUMENT_RESET_PROTOCOL_VERSION = "finance_stopping_instrument_reset_protocol.v3"
STOPPING_INSTRUMENT_RESET_POPULATION_VERSION = "finance_stopping_instrument_reset_population.v3"
STOPPING_INSTRUMENT_RESET_CONTRACT_VERSION = "finance_stopping_instrument_reset_contract.v3"
STOPPING_INSTRUMENT_RESET_STATIC_AUDIT_VERSION = "finance_stopping_instrument_reset_static_audit.v3"
STOPPING_INSTRUMENT_RESET_RAW_AUDIT_VERSION = "finance_stopping_instrument_reset_raw_audit.v3"
STOPPING_INSTRUMENT_RESET_REPORT_VERSION = "finance_stopping_instrument_reset_report.v3"
STOPPING_INSTRUMENT_RESET_LABEL = "finance_v25_45_stopping_instrument_reset"
EXPECTED_TASK_COUNT = 48
EXPECTED_ROLLOUT_COUNT = 384


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InstrumentResetStaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    public_schema_count: int = Field(ge=1)
    tool_schema_coverage_count: int = Field(ge=1)
    nested_model_count: int = Field(ge=1)
    nested_extra_forbid_count: int = Field(ge=1)
    host_field_mutation_count: int = Field(ge=1)
    host_field_mutation_rejection_count: int = Field(ge=0)
    host_marker_mutation_count: int = Field(ge=1)
    host_marker_mutation_rejection_count: int = Field(ge=0)
    whitelist_alias_mutation_count: int = Field(ge=1)
    whitelist_alias_mutation_rejection_count: int = Field(ge=0)
    serialized_prompt_mutation_count: int = Field(ge=1)
    serialized_prompt_mutation_rejection_count: int = Field(ge=0)
    public_result_contract_manifest_hash: str = Field(min_length=1)
    noninterference_scanner_manifest_hash: str = Field(min_length=1)
    model_input_projection_manifest_hash: str = Field(min_length=1)
    recursive_mapping_coverage: bool
    recursive_sequence_coverage: bool
    optional_object_coverage: bool
    union_object_coverage: bool
    rejection_reasons: tuple[str, ...]
    ready: bool
    schema_version: str = STOPPING_INSTRUMENT_RESET_STATIC_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> InstrumentResetStaticAudit:
        expected = not self.rejection_reasons
        if self.ready != expected:
            raise ValueError("Instrument-reset static decision is inconsistent")
        if self.host_field_mutation_rejection_count != self.host_field_mutation_count:
            raise ValueError("Instrument-reset Host-field mutations were not all rejected")
        if self.host_marker_mutation_rejection_count != self.host_marker_mutation_count:
            raise ValueError("Instrument-reset Host-marker mutations were not all rejected")
        if self.whitelist_alias_mutation_rejection_count != self.whitelist_alias_mutation_count:
            raise ValueError("Instrument-reset whitelist mutations were not all rejected")
        if self.serialized_prompt_mutation_rejection_count != self.serialized_prompt_mutation_count:
            raise ValueError("Instrument-reset serialized Prompt mutations were not all rejected")
        if self.nested_extra_forbid_count != self.nested_model_count:
            raise ValueError("Instrument-reset nested public models are not all strict")
        if self.audit_id != _artifact_id(
            self, "audit_id", "finance_stopping_instrument_reset_static_audit:"
        ):
            raise ValueError("Instrument-reset static audit identity is invalid")
        return self


class FinanceStoppingInstrumentResetProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_45_stopping_instrument_reset"] = (
        "finance_v25_45_stopping_instrument_reset"
    )
    source_snapshot_v3: FrozenArtifactReference
    source_grammar_protocol: FrozenArtifactReference
    source_outcome_artifacts_used: Literal[False] = False
    historical_shape_support_transferred: Literal[False] = False
    public_result_contract_version: Literal["finance_public_result_contract.v1"] = (
        "finance_public_result_contract.v1"
    )
    public_result_contract_manifest: dict[str, Any]
    public_result_contract_manifest_hash: str = Field(min_length=1)
    noninterference_version: Literal["recursive_host_agent_noninterference.v2"] = (
        "recursive_host_agent_noninterference.v2"
    )
    noninterference_scanner_manifest_hash: str = Field(min_length=1)
    model_input_projection_manifest: dict[str, Any]
    model_input_projection_manifest_hash: str = Field(min_length=1)
    reserved_host_fields: tuple[str, ...]
    reserved_host_markers: tuple[str, ...]
    aggregation_before_raw_audit_forbidden: Literal[True] = True
    contaminated_record_filtering_authorized: Literal[False] = False
    posthoc_task_deletion_authorized: Literal[False] = False
    task_count: Literal[48] = 48
    rollout_count: Literal[384] = 384
    next_permitted_stage: Literal["instrument_reset_population_build"] = (
        "instrument_reset_population_build"
    )
    schema_version: str = STOPPING_INSTRUMENT_RESET_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> FinanceStoppingInstrumentResetProtocol:
        manifest = finance_public_result_contract_manifest()
        if self.public_result_contract_manifest != manifest:
            raise ValueError("Instrument-reset public result manifest changed")
        if self.public_result_contract_manifest_hash != manifest["manifest_hash"]:
            raise ValueError("Instrument-reset public result manifest identity is invalid")
        if self.noninterference_scanner_manifest_hash != (_noninterference_scanner_manifest_hash()):
            raise ValueError("Instrument-reset scanner identity changed")
        projection = model_input_projection_manifest()
        if self.model_input_projection_manifest != projection:
            raise ValueError("Instrument-reset model-input projection changed")
        if self.model_input_projection_manifest_hash != projection["manifest_hash"]:
            raise ValueError("Instrument-reset model-input projection identity is invalid")
        if self.reserved_host_fields != tuple(sorted(RESERVED_HOST_RESULT_KEYS)):
            raise ValueError("Instrument-reset Host field registry changed")
        if self.reserved_host_markers != tuple(sorted(RESERVED_HOST_RESULT_MARKERS)):
            raise ValueError("Instrument-reset Host marker registry changed")
        if self.protocol_id != _artifact_id(
            self, "protocol_id", "finance_stopping_instrument_reset_protocol:"
        ):
            raise ValueError("Instrument-reset protocol identity is invalid")
        return self


class FinanceStoppingInstrumentResetPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_protocol: FrozenArtifactReference
    source_grammar_population: FrozenArtifactReference
    task_artifact_ids: tuple[str, ...] = Field(min_length=48, max_length=48)
    grammar_population_static_ready: Literal[True] = True
    historical_task_disjoint: Literal[True] = True
    historical_evidence_disjoint: Literal[True] = True
    historical_evidence_version_disjoint: Literal[True] = True
    historical_semantic_signature_disjoint: Literal[True] = True
    historical_materializer_disjoint: Literal[True] = True
    static_noninterference_audit: InstrumentResetStaticAudit
    model_api_calls: Literal[0] = 0
    historical_shape_support_transferred: Literal[False] = False
    next_permitted_stage: Literal["flash_instrument_reset", "instrument_reset_repair_only"]
    schema_version: str = STOPPING_INSTRUMENT_RESET_POPULATION_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> FinanceStoppingInstrumentResetPopulation:
        if len(set(self.task_artifact_ids)) != EXPECTED_TASK_COUNT:
            raise ValueError("Instrument-reset population task identities are incomplete")
        expected = (
            "flash_instrument_reset"
            if self.static_noninterference_audit.ready
            else "instrument_reset_repair_only"
        )
        if self.next_permitted_stage != expected:
            raise ValueError("Instrument-reset population transition is inconsistent")
        if self.population_id != _artifact_id(
            self, "population_id", "finance_stopping_instrument_reset_population:"
        ):
            raise ValueError("Instrument-reset population identity is invalid")
        return self


class FinanceStoppingInstrumentResetContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_protocol: FrozenArtifactReference
    source_population: FrozenArtifactReference
    source_execution_contract: FrozenArtifactReference
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    public_result_contract_manifest_hash: str = Field(min_length=1)
    noninterference_scanner_manifest_hash: str = Field(min_length=1)
    model_input_projection_manifest_hash: str = Field(min_length=1)
    task_count: Literal[48] = 48
    rollout_count: Literal[384] = 384
    requested_model: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
    raw_audit_before_aggregation: Literal[True] = True
    source_outcomes_used: Literal[False] = False
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_instrument_reset"] = "flash_instrument_reset"
    schema_version: str = STOPPING_INSTRUMENT_RESET_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceStoppingInstrumentResetContract:
        if self.implementation_manifest != _implementation_manifest():
            raise ValueError("Instrument-reset implementation changed after freeze")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest, prefix="finance_stopping_instrument_reset_implementation:"
        ):
            raise ValueError("Instrument-reset implementation identity is invalid")
        if (
            self.public_result_contract_manifest_hash
            != (finance_public_result_contract_manifest()["manifest_hash"])
        ):
            raise ValueError("Instrument-reset public result identity changed")
        if self.noninterference_scanner_manifest_hash != (_noninterference_scanner_manifest_hash()):
            raise ValueError("Instrument-reset scanner identity changed")
        if (
            self.model_input_projection_manifest_hash
            != model_input_projection_manifest()["manifest_hash"]
        ):
            raise ValueError("Instrument-reset model-input projection identity changed")
        if self.contract_id != _artifact_id(
            self, "contract_id", "finance_stopping_instrument_reset_contract:"
        ):
            raise ValueError("Instrument-reset contract identity is invalid")
        return self


class InstrumentResetRawAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    expected_record_count: Literal[384] = 384
    record_count: int = Field(ge=0)
    auditable_record_count: int = Field(ge=0)
    successful_record_count: int = Field(ge=0)
    behavior_failure_record_count: int = Field(ge=0)
    tool_observation_count: int = Field(ge=0)
    strict_public_schema_pass_count: int = Field(ge=0)
    recursive_host_field_violation_count: int = Field(ge=0)
    recursive_host_marker_violation_count: int = Field(ge=0)
    public_result_hash_match_count: int = Field(ge=0)
    host_side_channel_hash_match_count: int = Field(ge=0)
    internal_result_hash_match_count: int = Field(ge=0)
    prompt_attestation_record_count: int = Field(ge=0)
    model_request_prompt_count: int = Field(ge=0)
    model_request_prompt_scan_pass_count: int = Field(ge=0)
    model_request_prompt_hash_match_count: int = Field(ge=0)
    last_prompt_hash_match_count: int = Field(ge=0)
    side_channel_unknown_event_count: int = Field(ge=0)
    contamination_task_count: int = Field(ge=0)
    unattested_task_count: int = Field(ge=0)
    public_contract_violation_task_count: int = Field(ge=0)
    rejection_reasons: tuple[str, ...]
    instrument_status: Literal["passed", "failed"]
    shape_analysis_authorized: bool
    schema_version: str = STOPPING_INSTRUMENT_RESET_RAW_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> InstrumentResetRawAudit:
        expected = not self.rejection_reasons
        if (self.instrument_status == "passed") != expected:
            raise ValueError("Instrument-reset raw audit decision is inconsistent")
        if self.shape_analysis_authorized != expected:
            raise ValueError("Instrument-reset Shape authorization is inconsistent")
        if expected and not (
            self.record_count
            == self.auditable_record_count
            == self.prompt_attestation_record_count
            == self.last_prompt_hash_match_count
            == EXPECTED_ROLLOUT_COUNT
        ):
            raise ValueError("Instrument-reset passed with an incomplete rollout denominator")
        if expected and (
            self.successful_record_count + self.behavior_failure_record_count
            != self.record_count
        ):
            raise ValueError("Instrument-reset behavior outcome accounting is incomplete")
        if expected and not (
            self.tool_observation_count
            == self.strict_public_schema_pass_count
            == self.public_result_hash_match_count
            == self.host_side_channel_hash_match_count
            == self.internal_result_hash_match_count
        ):
            raise ValueError("Instrument-reset passed with incomplete observation accounting")
        if expected and not (
            self.model_request_prompt_count
            == self.model_request_prompt_scan_pass_count
            == self.model_request_prompt_hash_match_count
        ):
            raise ValueError("Instrument-reset passed with incomplete API Prompt accounting")
        if expected and any(
            (
                self.recursive_host_field_violation_count,
                self.recursive_host_marker_violation_count,
                self.side_channel_unknown_event_count,
                self.contamination_task_count,
                self.unattested_task_count,
                self.public_contract_violation_task_count,
            )
        ):
            raise ValueError("Instrument-reset passed despite a noninterference violation")
        if self.audit_id != _artifact_id(
            self, "audit_id", "finance_stopping_instrument_reset_raw_audit:"
        ):
            raise ValueError("Instrument-reset raw audit identity is invalid")
        return self


class FinanceStoppingInstrumentResetReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    instrument_audit_id: str = Field(min_length=1)
    instrument_status: Literal["passed", "failed"]
    shape_analysis_authorized: bool
    shape_report_id: str | None = None
    boundary_candidate_admitted_count: int = Field(ge=0, le=4)
    runtime_control_pass_count: int = Field(ge=0, le=2)
    all_shapes_admitted: bool
    historical_shape_support_transferred: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "instrument_reset_repair_only",
        "stopping_shape_redesign_only",
        "fresh_three_population_shape_policy_preparation",
    ]
    schema_version: str = STOPPING_INSTRUMENT_RESET_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceStoppingInstrumentResetReport:
        if not self.shape_analysis_authorized:
            expected = "instrument_reset_repair_only"
            if self.shape_report_id is not None or self.all_shapes_admitted:
                raise ValueError("Failed instrument-reset report contains Shape evidence")
        elif self.all_shapes_admitted:
            expected = "fresh_three_population_shape_policy_preparation"
        else:
            expected = "stopping_shape_redesign_only"
        if self.next_permitted_stage != expected:
            raise ValueError("Instrument-reset report transition is inconsistent")
        if self.report_id != _artifact_id(
            self, "report_id", "finance_stopping_instrument_reset_report:"
        ):
            raise ValueError("Instrument-reset report identity is invalid")
        return self


def prepare_instrument_reset(
    *,
    source_snapshot_path: Path,
    source_grammar_protocol_path: Path,
    source_grammar_population_path: Path,
    source_execution_contract_path: Path,
    output_dir: Path,
    run_id: str,
) -> tuple[
    FinanceStoppingInstrumentResetProtocol,
    FinanceStoppingInstrumentResetPopulation,
    FinanceStoppingInstrumentResetContract,
]:
    output_dir.mkdir(parents=True, exist_ok=False)
    grammar_protocol = load_stopping_shape_grammar_protocol(source_grammar_protocol_path)
    if not isinstance(grammar_protocol, FinanceStoppingInstrumentResetGrammarProtocol):
        raise ValueError("Instrument reset requires a fresh v9 Grammar protocol")
    grammar_population = FinanceStoppingShapePolicyPopulation.model_validate_json(
        source_grammar_population_path.read_text(encoding="utf-8")
    )
    execution = FinanceStoppingShapePolicyContract.model_validate_json(
        source_execution_contract_path.read_text(encoding="utf-8")
    )
    _verify_reference(grammar_population.protocol_path, grammar_population.protocol_sha256)
    if execution.source_protocol.artifact_id != grammar_protocol.protocol_id:
        raise ValueError("Instrument-reset execution contract crosses protocol identities")
    if execution.source_population.artifact_id != grammar_population.population_id:
        raise ValueError("Instrument-reset execution contract crosses population identities")
    if not grammar_population.static_audit.ready:
        raise ValueError("Instrument-reset grammar population is not statically ready")
    if grammar_protocol.source_finance_artifacts.path != str(source_snapshot_path.resolve()):
        raise ValueError("Instrument-reset grammar protocol does not bind Snapshot v3")
    if _sha256(source_snapshot_path) != grammar_protocol.source_finance_artifacts.sha256:
        raise ValueError("Instrument-reset Snapshot v3 content changed")

    public_manifest = finance_public_result_contract_manifest()
    projection_manifest = model_input_projection_manifest()
    protocol_values = {
        "run_id": run_id,
        "source_snapshot_v3": _reference(
            source_snapshot_path, grammar_protocol.source_finance_artifacts.artifact_id
        ),
        "source_grammar_protocol": _reference(
            source_grammar_protocol_path, grammar_protocol.protocol_id
        ),
        "public_result_contract_manifest": public_manifest,
        "public_result_contract_manifest_hash": public_manifest["manifest_hash"],
        "noninterference_scanner_manifest_hash": _noninterference_scanner_manifest_hash(),
        "model_input_projection_manifest": projection_manifest,
        "model_input_projection_manifest_hash": projection_manifest["manifest_hash"],
        "reserved_host_fields": tuple(sorted(RESERVED_HOST_RESULT_KEYS)),
        "reserved_host_markers": tuple(sorted(RESERVED_HOST_RESULT_MARKERS)),
    }
    provisional_protocol = FinanceStoppingInstrumentResetProtocol.model_construct(
        protocol_id="pending", **protocol_values
    )
    protocol = FinanceStoppingInstrumentResetProtocol(
        protocol_id=_artifact_id(
            provisional_protocol,
            "protocol_id",
            "finance_stopping_instrument_reset_protocol:",
        ),
        **protocol_values,
    )
    protocol_path = output_dir / "finance_stopping_instrument_reset_protocol.json"
    _write_json(protocol_path, protocol.model_dump(mode="json"))

    static_audit = make_static_noninterference_audit()
    population_values = {
        "run_id": run_id,
        "source_protocol": _reference(protocol_path, protocol.protocol_id),
        "source_grammar_population": _reference(
            source_grammar_population_path, grammar_population.population_id
        ),
        "task_artifact_ids": tuple(
            sorted(item.artifact.artifact_id for item in grammar_population.tasks)
        ),
        "historical_task_disjoint": grammar_population.static_audit.historical_task_disjoint,
        "historical_evidence_disjoint": (
            grammar_population.static_audit.historical_evidence_disjoint
        ),
        "historical_evidence_version_disjoint": (
            grammar_population.static_audit.historical_evidence_version_disjoint
        ),
        "historical_semantic_signature_disjoint": (
            grammar_population.static_audit.historical_semantic_signature_disjoint
        ),
        "historical_materializer_disjoint": (
            grammar_population.static_audit.historical_materializer_disjoint
        ),
        "static_noninterference_audit": static_audit,
        "next_permitted_stage": (
            "flash_instrument_reset" if static_audit.ready else "instrument_reset_repair_only"
        ),
    }
    provisional_population = FinanceStoppingInstrumentResetPopulation.model_construct(
        population_id="pending", **population_values
    )
    population = FinanceStoppingInstrumentResetPopulation(
        population_id=_artifact_id(
            provisional_population,
            "population_id",
            "finance_stopping_instrument_reset_population:",
        ),
        **population_values,
    )
    population_path = output_dir / "finance_stopping_instrument_reset_population.json"
    _write_json(population_path, population.model_dump(mode="json"))
    _write_json(
        output_dir / "finance_stopping_instrument_reset_static_audit.json",
        static_audit.model_dump(mode="json"),
    )
    if not static_audit.ready:
        raise ValueError("Instrument-reset static noninterference audit failed")

    implementation = _implementation_manifest()
    contract_values = {
        "run_id": run_id,
        "source_protocol": _reference(protocol_path, protocol.protocol_id),
        "source_population": _reference(population_path, population.population_id),
        "source_execution_contract": _reference(
            source_execution_contract_path, execution.contract_id
        ),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation, prefix="finance_stopping_instrument_reset_implementation:"
        ),
        "public_result_contract_manifest_hash": public_manifest["manifest_hash"],
        "noninterference_scanner_manifest_hash": _noninterference_scanner_manifest_hash(),
        "model_input_projection_manifest_hash": projection_manifest["manifest_hash"],
    }
    provisional_contract = FinanceStoppingInstrumentResetContract.model_construct(
        contract_id="pending", **contract_values
    )
    contract = FinanceStoppingInstrumentResetContract(
        contract_id=_artifact_id(
            provisional_contract,
            "contract_id",
            "finance_stopping_instrument_reset_contract:",
        ),
        **contract_values,
    )
    _write_json(
        output_dir / "finance_stopping_instrument_reset_contract.json",
        contract.model_dump(mode="json"),
    )
    return protocol, population, contract


def make_static_noninterference_audit() -> InstrumentResetStaticAudit:
    public_manifest = finance_public_result_contract_manifest()
    nested_schemas: list[dict[str, Any]] = []
    public_models: tuple[type[BaseModel], ...] = (
        *SUCCESS_MODELS.values(),
        FailedResultPublic,
    )
    for model in public_models:
        schema = model.model_json_schema()
        nested_schemas.extend(schema.get("$defs", {}).values())
        nested_schemas.append(schema)
    object_models = [item for item in nested_schemas if item.get("type") == "object"]
    strict_models = [item for item in object_models if item.get("additionalProperties") is False]

    host_field_cases: list[dict[str, Any]] = []
    for key in sorted(RESERVED_HOST_RESULT_KEYS):
        host_field_cases.extend(
            (
                {key: "forbidden"},
                {"safe": {key: "forbidden"}},
                {"safe": [{key: "forbidden"}]},
                {"safe": {"nested": [{"deeper": {key: "forbidden"}}]}},
            )
        )
    host_field_rejections = sum(_generic_result_rejected(item) for item in host_field_cases)
    host_marker_cases = [{"safe": marker} for marker in sorted(RESERVED_HOST_RESULT_MARKERS)] + [
        {"safe": [{"value": marker}]} for marker in sorted(RESERVED_HOST_RESULT_MARKERS)
    ]
    host_marker_rejections = sum(_generic_result_rejected(item) for item in host_marker_cases)

    aliases = ("completion_reason", "trigger_label", "resolution_status", "oracle_stage")
    alias_cases: list[tuple[type[BaseModel], dict[str, Any]]] = []
    for alias in aliases:
        alias_cases.extend(
            (
                (FailedResultPublic, {alias: "forbidden"}),
                (PublicCompletionState, {"complete": False, alias: "forbidden"}),
                (
                    PublicRetryContract,
                    {
                        "policy": "prerequisite_action_required",
                        "suggested_argument_patch": {"rule": "continue", alias: "forbidden"},
                    },
                ),
            )
        )
    alias_rejections = sum(_pydantic_extra_rejected(*item) for item in alias_cases)
    prompt_cases = tuple(
        _serialized_prompt({"safe": {key: "forbidden"}})
        for key in sorted(RESERVED_HOST_RESULT_KEYS)
    ) + tuple(
        _serialized_prompt({"safe": [{"value": marker}]})
        for marker in sorted(RESERVED_HOST_RESULT_MARKERS)
    )
    prompt_rejections = sum(_serialized_prompt_rejected(item) for item in prompt_cases)
    reasons = []
    if len(SUCCESS_MODELS) != 6:
        reasons.append("public_tool_schema_coverage_incomplete")
    if len(strict_models) != len(object_models):
        reasons.append("nested_public_model_not_extra_forbid")
    if host_field_rejections != len(host_field_cases):
        reasons.append("recursive_host_field_mutation_not_rejected")
    if host_marker_rejections != len(host_marker_cases):
        reasons.append("recursive_host_marker_mutation_not_rejected")
    if alias_rejections != len(alias_cases):
        reasons.append("public_whitelist_alias_mutation_not_rejected")
    if prompt_rejections != len(prompt_cases):
        reasons.append("serialized_prompt_mutation_not_rejected")
    values = {
        "public_schema_count": len(SUCCESS_MODELS) + 1,
        "tool_schema_coverage_count": len(SUCCESS_MODELS),
        "nested_model_count": len(object_models),
        "nested_extra_forbid_count": len(strict_models),
        "host_field_mutation_count": len(host_field_cases),
        "host_field_mutation_rejection_count": host_field_rejections,
        "host_marker_mutation_count": len(host_marker_cases),
        "host_marker_mutation_rejection_count": host_marker_rejections,
        "whitelist_alias_mutation_count": len(alias_cases),
        "whitelist_alias_mutation_rejection_count": alias_rejections,
        "serialized_prompt_mutation_count": len(prompt_cases),
        "serialized_prompt_mutation_rejection_count": prompt_rejections,
        "public_result_contract_manifest_hash": public_manifest["manifest_hash"],
        "noninterference_scanner_manifest_hash": _noninterference_scanner_manifest_hash(),
        "model_input_projection_manifest_hash": (
            model_input_projection_manifest()["manifest_hash"]
        ),
        "recursive_mapping_coverage": True,
        "recursive_sequence_coverage": True,
        "optional_object_coverage": True,
        "union_object_coverage": True,
        "rejection_reasons": tuple(reasons),
        "ready": not reasons,
    }
    provisional = InstrumentResetStaticAudit.model_construct(audit_id="pending", **values)
    return InstrumentResetStaticAudit(
        audit_id=_artifact_id(
            provisional, "audit_id", "finance_stopping_instrument_reset_static_audit:"
        ),
        **values,
    )


def run_instrument_reset(
    *, contract_path: Path, output_dir: Path, workers: int
) -> FinanceStoppingInstrumentResetReport:
    reset = FinanceStoppingInstrumentResetContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_frozen_reset_inputs(reset)
    base_path = Path(reset.source_execution_contract.path)
    base = FinanceStoppingShapePolicyContract.model_validate_json(
        base_path.read_text(encoding="utf-8")
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    prefix = "stopping_instrument_reset"
    outcomes, discovered = _execute_stage(
        contract=cast(Any, base),
        tasks={item.artifact_id: item for item in base.tasks},
        bindings=base.bindings,
        model_arm=ExplorerArm.FLASH,
        replicas=base.replicas,
        output_dir=output_dir,
        prefix=prefix,
        workers=workers,
    )
    records_path = output_dir / f"{prefix}_records.jsonl"
    records = _load_records(records_path)
    raw_audit = make_raw_instrument_audit(reset, base, records)
    raw_path = output_dir / "finance_stopping_instrument_reset_raw_audit.json"
    _write_json(raw_path, raw_audit.model_dump(mode="json"))

    shape_report = None
    if raw_audit.shape_analysis_authorized:
        terminals = _make_terminals(cast(Any, base), records, outcomes)
        behaviors = make_submechanism_behavior_observations(
            cast(Any, base), records, outcomes, terminals
        )
        observations = make_stopping_shape_policy_observations(base, behaviors, outcomes, terminals)
        _write_jsonl(
            output_dir / f"{prefix}_terminal_outcomes.jsonl",
            (item.model_dump(mode="json") for item in terminals),
        )
        _write_jsonl(
            output_dir / f"{prefix}_behavior_diagnostics.jsonl",
            (item.model_dump(mode="json") for item in behaviors),
        )
        _write_jsonl(
            output_dir / f"{prefix}_shape_observations.jsonl",
            (item.model_dump(mode="json") for item in observations),
        )
        shape_report = make_stopping_shape_policy_report(
            base,
            records,
            outcomes,
            terminals,
            observations,
            discovered_models=discovered,
        )
        _write_json(
            output_dir / "finance_stopping_instrument_reset_shape_report.json",
            shape_report.model_dump(mode="json"),
        )

    all_shapes = bool(shape_report and shape_report.all_shapes_contract_passing)
    values = {
        "contract_id": reset.contract_id,
        "instrument_audit_id": raw_audit.audit_id,
        "instrument_status": raw_audit.instrument_status,
        "shape_analysis_authorized": raw_audit.shape_analysis_authorized,
        "shape_report_id": shape_report.report_id if shape_report else None,
        "boundary_candidate_admitted_count": (
            shape_report.boundary_candidate_admitted_count if shape_report else 0
        ),
        "runtime_control_pass_count": (
            shape_report.runtime_control_pass_count if shape_report else 0
        ),
        "all_shapes_admitted": all_shapes,
        "next_permitted_stage": (
            "instrument_reset_repair_only"
            if not raw_audit.shape_analysis_authorized
            else (
                "fresh_three_population_shape_policy_preparation"
                if all_shapes
                else "stopping_shape_redesign_only"
            )
        ),
    }
    provisional = FinanceStoppingInstrumentResetReport.model_construct(
        report_id="pending", **values
    )
    report = FinanceStoppingInstrumentResetReport(
        report_id=_artifact_id(
            provisional, "report_id", "finance_stopping_instrument_reset_report:"
        ),
        **values,
    )
    report_path = output_dir / "finance_stopping_instrument_reset_report.json"
    _write_json(report_path, report.model_dump(mode="json"))
    (output_dir / "finance_stopping_instrument_reset_report.md").write_text(
        _render_report(report, raw_audit, shape_report), encoding="utf-8"
    )
    manifest = {
        "schema_version": "finance_stopping_instrument_reset_manifest.v1",
        "contract_id": reset.contract_id,
        "report_id": report.report_id,
        "raw_audit_id": raw_audit.audit_id,
        "records_sha256": _sha256(records_path),
        "raw_audit_sha256": _sha256(raw_path),
        "report_sha256": _sha256(report_path),
        "aggregation_performed": raw_audit.shape_analysis_authorized,
        "shape_analysis_authorized": raw_audit.shape_analysis_authorized,
        "historical_shape_support_transferred": False,
        "pro_api_call_count": 0,
        "beneficiary_authorized": False,
        "exact_target_authorized": False,
        "gp_c_authorized": False,
        "production_contribution": 0.0,
    }
    _write_json(output_dir / "finance_stopping_instrument_reset_manifest.json", manifest)
    return report


def make_raw_instrument_audit(
    reset: FinanceStoppingInstrumentResetContract,
    base: FinanceStoppingShapePolicyContract,
    records: Sequence[Any],
) -> InstrumentResetRawAudit:
    expected_scanner = _noninterference_scanner_manifest_hash()
    public_pass = 0
    field_violations = 0
    marker_violations = 0
    public_hash_matches = 0
    host_hash_matches = 0
    internal_hash_matches = 0
    prompt_attested = 0
    request_prompt_count = 0
    request_prompt_scan_passes = 0
    request_prompt_hash_matches = 0
    last_prompt_matches = 0
    unknown_events = 0
    observation_count = 0
    contaminated_tasks: set[str] = set()
    unattested_tasks: set[str] = set()
    public_contract_tasks: set[str] = set()
    reasons: set[str] = set()
    auditable = 0
    successful = 0
    behavior_failures = 0

    for record in records:
        last_prompt_field = "final_model_prompt_hash"
        expected_audit_version = ITERATIVE_AGENT_AUDIT_VERSION
        if record.status == "completed" and record.agent_audit is not None:
            audit = record.agent_audit
            observations = tuple(record.observations)
            successful += 1
        elif record.status == "failed" and record.failure_artifact is not None:
            try:
                failure = IterativeAgentFailureArtifact.model_validate(
                    record.failure_artifact
                )
            except ValidationError:
                reasons.add("failure_rollout_noninterference_artifact_invalid")
                unattested_tasks.add(record.task_artifact_id)
                continue
            audit = failure.model_dump(mode="json")
            observations = failure.observations
            behavior_failures += 1
            last_prompt_field = "last_model_prompt_hash"
            expected_audit_version = ITERATIVE_AGENT_FAILURE_ARTIFACT_VERSION
        else:
            reasons.add("rollout_noninterference_artifact_missing")
            unattested_tasks.add(record.task_artifact_id)
            continue
        auditable += 1
        expected_events = set(base.task_expected_host_events[record.task_artifact_id])
        if audit.get("schema_version") != expected_audit_version:
            reasons.add("rollout_audit_schema_not_reset_version")
            unattested_tasks.add(record.task_artifact_id)
        prompt_hashes = tuple(str(item) for item in audit.get("decision_prompt_hashes", ()))
        prompt_attestations = tuple(
            str(item)
            for item in audit.get("decision_prompt_noninterference_attestation_hashes", ())
        )
        scanner = str(audit.get("noninterference_scanner_manifest_hash", ""))
        plan_hash = str(audit.get("plan_prompt_hash", ""))
        plan_attestation = str(audit.get("plan_prompt_noninterference_attestation_hash", ""))
        expected_prompt_attestations = tuple(
            _prompt_noninterference_attestation_hash(item, expected_scanner)
            for item in prompt_hashes
        )
        request_prompts = tuple(str(item) for item in audit.get("model_request_prompts", ()))
        request_hashes = tuple(
            str(item) for item in audit.get("model_request_prompt_hashes", ())
        )
        request_attestations = tuple(
            str(item)
            for item in audit.get(
                "model_request_prompt_noninterference_attestation_hashes", ()
            )
        )
        telemetry_hashes = tuple(
            str(item.get("request_hash", "")) for item in audit.get("telemetry", ())
        )
        request_prompt_count += len(request_prompts)
        request_hashes_valid = len(request_prompts) == len(request_hashes) == len(
            request_attestations
        ) == len(telemetry_hashes)
        for index, prompt in enumerate(request_prompts):
            try:
                _assert_no_model_forbidden_prompt(prompt)
            except ValueError:
                reasons.add("actual_model_request_prompt_contaminated")
                contaminated_tasks.add(record.task_artifact_id)
            else:
                request_prompt_scan_passes += 1
            expected_hash = _sha256_text(prompt)
            if (
                index < len(request_hashes)
                and index < len(request_attestations)
                and index < len(telemetry_hashes)
                and request_hashes[index] == expected_hash == telemetry_hashes[index]
                and request_attestations[index]
                == _prompt_noninterference_attestation_hash(expected_hash, expected_scanner)
            ):
                request_prompt_hash_matches += 1
            else:
                reasons.add("actual_model_request_prompt_hash_mismatch")
                unattested_tasks.add(record.task_artifact_id)
        if (
            scanner == expected_scanner
            and prompt_hashes
            and prompt_attestations == expected_prompt_attestations
            and plan_attestation
            == _prompt_noninterference_attestation_hash(plan_hash, expected_scanner)
            and request_hashes_valid
            and request_prompts
        ):
            prompt_attested += 1
        else:
            reasons.add("model_prompt_noninterference_attestation_failed")
            unattested_tasks.add(record.task_artifact_id)
        if request_hashes and audit.get(last_prompt_field) == request_hashes[-1]:
            last_prompt_matches += 1
        else:
            reasons.add("last_model_prompt_hash_mismatch")
            unattested_tasks.add(record.task_artifact_id)

        public_hashes = tuple(audit.get("public_model_visible_result_hashes", ()))
        host_hashes = tuple(audit.get("host_event_side_channel_hashes", ()))
        internal_hashes = tuple(audit.get("internal_tool_result_hashes", ()))
        if not (
            len(observations) == len(public_hashes) == len(host_hashes) == len(internal_hashes)
        ):
            reasons.add("observation_hash_denominator_mismatch")
            unattested_tasks.add(record.task_artifact_id)

        for index, observation in enumerate(observations):
            observation_count += 1
            paths = reserved_host_result_paths(observation.result)
            markers = reserved_host_marker_paths(
                observation.result,
                markers=frozenset(
                    (*RESERVED_HOST_RESULT_MARKERS, *observation.host_events)
                ),
            )
            field_violations += len(paths)
            marker_violations += len(markers)
            if paths or markers:
                contaminated_tasks.add(record.task_artifact_id)
            try:
                reconstructed = AgentToolResult(
                    status=observation.status,
                    result=observation.result,
                    evidence_ids=observation.evidence_ids,
                    provenance_hashes=observation.provenance_hashes,
                    host_events=observation.host_events,
                    error_code=observation.error_code,
                    error_message=observation.error_message,
                )
                validate_finance_public_tool_result(observation.call.tool_id, reconstructed)
            except (ValidationError, ValueError):
                reasons.add("strict_public_result_schema_failed")
                public_contract_tasks.add(record.task_artifact_id)
            else:
                public_pass += 1
            if index < len(public_hashes) and public_hashes[index] == canonical_hash(
                observation.result, prefix="agent_public_model_visible_result:"
            ):
                public_hash_matches += 1
            else:
                reasons.add("public_model_visible_result_hash_mismatch")
                unattested_tasks.add(record.task_artifact_id)
            if index < len(host_hashes) and host_hashes[index] == canonical_hash(
                observation.host_events, prefix="agent_host_event_side_channel:"
            ):
                host_hash_matches += 1
            else:
                reasons.add("host_event_side_channel_hash_mismatch")
                unattested_tasks.add(record.task_artifact_id)
            if index < len(internal_hashes) and internal_hashes[index] == observation.content_hash:
                internal_hash_matches += 1
            else:
                reasons.add("internal_tool_result_hash_mismatch")
                unattested_tasks.add(record.task_artifact_id)
            unknown = set(observation.host_events) - expected_events
            unknown_events += len(unknown)
            if unknown:
                reasons.add("unknown_host_side_channel_event")
                contaminated_tasks.add(record.task_artifact_id)

    if len(records) != EXPECTED_ROLLOUT_COUNT:
        reasons.add("record_denominator_incomplete")
    if auditable != EXPECTED_ROLLOUT_COUNT:
        reasons.add("auditable_record_denominator_incomplete")
    if successful + behavior_failures != len(records):
        reasons.add("behavior_outcome_denominator_incomplete")
    if field_violations:
        reasons.add("recursive_host_field_contamination")
    if marker_violations:
        reasons.add("recursive_host_marker_contamination")
    if public_pass != observation_count:
        reasons.add("strict_public_schema_coverage_incomplete")
    if any(
        value != observation_count
        for value in (public_hash_matches, host_hash_matches, internal_hash_matches)
    ):
        reasons.add("observation_hash_coverage_incomplete")
    if request_prompt_scan_passes != request_prompt_count:
        reasons.add("actual_model_request_prompt_scan_incomplete")
    if request_prompt_hash_matches != request_prompt_count:
        reasons.add("actual_model_request_prompt_hash_coverage_incomplete")
    values = {
        "contract_id": reset.contract_id,
        "record_count": len(records),
        "auditable_record_count": auditable,
        "successful_record_count": successful,
        "behavior_failure_record_count": behavior_failures,
        "tool_observation_count": observation_count,
        "strict_public_schema_pass_count": public_pass,
        "recursive_host_field_violation_count": field_violations,
        "recursive_host_marker_violation_count": marker_violations,
        "public_result_hash_match_count": public_hash_matches,
        "host_side_channel_hash_match_count": host_hash_matches,
        "internal_result_hash_match_count": internal_hash_matches,
        "prompt_attestation_record_count": prompt_attested,
        "model_request_prompt_count": request_prompt_count,
        "model_request_prompt_scan_pass_count": request_prompt_scan_passes,
        "model_request_prompt_hash_match_count": request_prompt_hash_matches,
        "last_prompt_hash_match_count": last_prompt_matches,
        "side_channel_unknown_event_count": unknown_events,
        "contamination_task_count": len(contaminated_tasks),
        "unattested_task_count": len(unattested_tasks),
        "public_contract_violation_task_count": len(public_contract_tasks),
        "rejection_reasons": tuple(sorted(reasons)),
        "instrument_status": "passed" if not reasons else "failed",
        "shape_analysis_authorized": not reasons,
    }
    provisional = InstrumentResetRawAudit.model_construct(audit_id="pending", **values)
    return InstrumentResetRawAudit(
        audit_id=_artifact_id(
            provisional, "audit_id", "finance_stopping_instrument_reset_raw_audit:"
        ),
        **values,
    )


def _generic_result_rejected(payload: dict[str, Any]) -> bool:
    try:
        AgentToolResult(status="succeeded", result=payload)
    except ValidationError:
        return True
    return False


def _pydantic_extra_rejected(model: type[BaseModel], payload: dict[str, Any]) -> bool:
    try:
        model.model_validate(payload)
    except ValidationError as exc:
        return any(item.get("type") == "extra_forbidden" for item in exc.errors())
    return False


def _serialized_prompt(value: dict[str, Any]) -> str:
    return (
        "Return one public JSON object.\nPUBLIC_CONTEXT_JSON:\n"
        + json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _serialized_prompt_rejected(prompt: str) -> bool:
    try:
        _assert_no_model_forbidden_prompt(prompt)
    except ValueError:
        return True
    return False


def _artifact_id(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        "src/trusted_synthesis/runtime/tools.py",
        "src/trusted_synthesis/runtime/agent/client.py",
        "src/trusted_synthesis/runtime/agent/iterative.py",
        "src/trusted_synthesis/domains/finance/agent_tools.py",
        "src/trusted_synthesis/domains/finance/interactive_agent_runtime.py",
        "src/trusted_synthesis/domains/finance/iterative_agent_verifier.py",
        "src/trusted_synthesis/domains/finance/public_tool_results.py",
        "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary_runner.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_multitier_confirmation.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_policy.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_instrument_reset.py",
    )
    return {item: _sha256(root / item) for item in paths}


def _verify_frozen_reset_inputs(contract: FinanceStoppingInstrumentResetContract) -> None:
    for reference in (
        contract.source_protocol,
        contract.source_population,
        contract.source_execution_contract,
    ):
        _verify_reference(reference.path, reference.sha256)
    if contract.implementation_manifest != _implementation_manifest():
        raise ValueError("Instrument-reset implementation changed after contract freeze")


def _verify_reference(path: str | Path, expected_sha256: str) -> None:
    if _sha256(Path(path)) != expected_sha256:
        raise ValueError(f"frozen Instrument-reset input changed: {path}")


def _reference(path: Path, artifact_id: str) -> FrozenArtifactReference:
    resolved = path.resolve()
    return FrozenArtifactReference(
        path=str(resolved), sha256=_sha256(resolved), artifact_id=artifact_id
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise ValueError(f"immutable Instrument-reset output exists: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Sequence[Any] | Any) -> None:
    if path.exists():
        raise ValueError(f"immutable Instrument-reset output exists: {path}")
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in values),
        encoding="utf-8",
    )


def _render_report(
    report: FinanceStoppingInstrumentResetReport,
    raw: InstrumentResetRawAudit,
    shape: Any | None,
) -> str:
    lines = [
        "# Finance v25.45 Stopping Instrument Reset",
        "",
        f"- Instrument status: `{report.instrument_status}`",
        f"- Auditable records: **{raw.auditable_record_count}/{raw.expected_record_count}**",
        f"- Successful Agent outcomes: **{raw.successful_record_count}**",
        f"- Fail-closed behavior outcomes: **{raw.behavior_failure_record_count}**",
        f"- Tool observations: **{raw.tool_observation_count}**",
        f"- Recursive Host field violations: **{raw.recursive_host_field_violation_count}**",
        f"- Recursive Host marker violations: **{raw.recursive_host_marker_violation_count}**",
        "- Strict public-schema pass: "
        f"**{raw.strict_public_schema_pass_count}/{raw.tool_observation_count}**",
        f"- Prompt attestation pass: **{raw.prompt_attestation_record_count}/{raw.record_count}**",
        "- Actual API Prompt recursive scan: "
        f"**{raw.model_request_prompt_scan_pass_count}/{raw.model_request_prompt_count}**",
        "- Actual API Prompt hash match: "
        f"**{raw.model_request_prompt_hash_match_count}/{raw.model_request_prompt_count}**",
        f"- Shape analysis authorized: **{report.shape_analysis_authorized}**",
        f"- Unattested tasks: **{raw.unattested_task_count}**",
        "- Public-contract violation tasks: "
        f"**{raw.public_contract_violation_task_count}**",
        f"- Next permitted stage: `{report.next_permitted_stage}`",
        "- Historical Shape support transferred: **false**",
        "- Pro / Beneficiary / Exact Target / GP-C: **blocked**",
        "- Production Contribution: **0**",
        "",
    ]
    if raw.rejection_reasons:
        lines.extend(
            ["## Instrument failures", "", *(f"- `{x}`" for x in raw.rejection_reasons), ""]
        )
    if shape is not None:
        lines.extend(
            [
                "## Shape diagnostics",
                "",
                f"- Boundary candidates admitted: **{shape.boundary_candidate_admitted_count}/4**",
                f"- Runtime controls passed: **{shape.runtime_control_pass_count}/2**",
                f"- All Shapes admitted: **{shape.all_shapes_contract_passing}**",
                "",
            ]
        )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare or run v25.45 instrument reset")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--snapshot", required=True, type=Path)
    prepare.add_argument("--grammar-protocol", required=True, type=Path)
    prepare.add_argument("--grammar-population", required=True, type=Path)
    prepare.add_argument("--execution-contract", required=True, type=Path)
    prepare.add_argument("--output-dir", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    run = sub.add_parser("run")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--workers", type=int, default=32)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        protocol, population, contract = prepare_instrument_reset(
            source_snapshot_path=args.snapshot,
            source_grammar_protocol_path=args.grammar_protocol,
            source_grammar_population_path=args.grammar_population,
            source_execution_contract_path=args.execution_contract,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
        print(
            json.dumps(
                {
                    "protocol_id": protocol.protocol_id,
                    "population_id": population.population_id,
                    "contract_id": contract.contract_id,
                    "ready": population.static_noninterference_audit.ready,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        report = run_instrument_reset(
            contract_path=args.contract, output_dir=args.output_dir, workers=args.workers
        )
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
