from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    MAXIMUM_FAILED_TOOL_CALLS,
    MAXIMUM_OBSERVATION_BYTES,
    MAXIMUM_REQUIRED_TOOL_CALLS,
    MAXIMUM_TOOL_CALLS,
    MODEL_TOKEN_BUDGET,
    CapabilityRuntimeArm,
    RuntimeTaskBinding,
    _make_runtime_binding,
    make_v25_native_runtime_context,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    BoundaryStage,
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (
    CAPABILITY_BOUNDARY_RUNNER_VERSION,
    CapabilityBoundaryRolloutRecord,
    _run_one,
    _to_outcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_SENSITIVE_FAMILIES,
    CAPABILITY_SENSITIVE_FRONTIER_VERSION,
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_frozen_inputs import (
    project_frozen_input_mirror_root,
    resolve_frozen_input,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_MODELS,
    ExplorerArm,
    ExplorerModelContract,
    FinanceProFlashPilotContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_satisfiability import (
    PublicContractSatisfiabilityAudit,
    RuntimeArmName,
    make_public_contract_audit,
    make_public_contract_record,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import OpenAICompatibleJsonClient
from trusted_synthesis.runtime.agent.iterative import IterativeAgentProtocolProfile

PUBLIC_CONTRACT_REGRESSION_CONTRACT_VERSION = (
    "finance_public_contract_regression_contract.v5"
)
PUBLIC_CONTRACT_REGRESSION_REPORT_VERSION = (
    "finance_public_contract_regression_report.v5"
)
PUBLIC_CONTRACT_REGRESSION_RUNNER_VERSION = (
    "finance_public_contract_regression_runner.v5"
)
FRESHNESS_SIGNATURE_VERSION = "finance_public_task_exposure_signature.v1"

REGRESSION_TASKS_PER_FAMILY = 1
REGRESSION_REPLICAS = 2
REGRESSION_MODEL_ARMS = (ExplorerArm.FLASH,)
REGRESSION_RUNTIME_ARMS = (
    CapabilityRuntimeArm.SCRIPTED_TOOL,
    CapabilityRuntimeArm.AUTONOMOUS_AGENT,
)
REGRESSION_TASK_COUNT = len(CAPABILITY_SENSITIVE_FAMILIES)
REGRESSION_BINDING_COUNT = REGRESSION_TASK_COUNT * len(REGRESSION_RUNTIME_ARMS)
REGRESSION_ROLLOUT_COUNT = (
    REGRESSION_BINDING_COUNT * len(REGRESSION_MODEL_ARMS) * REGRESSION_REPLICAS
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExposureContractReference(FrozenModel):
    reference_id: str = Field(min_length=1)
    contract_path: str = Field(min_length=1)
    contract_sha256: str = Field(min_length=64, max_length=64)
    contract_id: str = Field(min_length=1)
    contract_schema_version: str = Field(min_length=1)
    population_path: str = Field(min_length=1)
    population_sha256: str = Field(min_length=64, max_length=64)
    population_id: str = Field(min_length=1)
    binding_field_names: tuple[str, ...] = Field(min_length=1)
    exposed_task_artifact_ids: tuple[str, ...] = Field(min_length=1)
    exposed_task_signatures: tuple[str, ...] = Field(min_length=1)
    exposed_evidence_ids: tuple[str, ...] = Field(min_length=1)
    exposed_evidence_version_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_reference(self) -> ExposureContractReference:
        if tuple(sorted(set(self.binding_field_names))) != self.binding_field_names:
            raise ValueError("exposure binding fields are not canonical")
        if tuple(sorted(set(self.exposed_task_artifact_ids))) != (
            self.exposed_task_artifact_ids
        ):
            raise ValueError("exposed task artifact identities are not canonical")
        if tuple(sorted(set(self.exposed_task_signatures))) != (
            self.exposed_task_signatures
        ):
            raise ValueError("exposed task signatures are not canonical")
        if len(self.exposed_task_artifact_ids) != len(self.exposed_task_signatures):
            raise ValueError("exposure identities and signatures have different denominators")
        for field_name in ("exposed_evidence_ids", "exposed_evidence_version_ids"):
            values = getattr(self, field_name)
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{field_name} are not canonical")
        if self.reference_id != exposure_contract_reference_id(self):
            raise ValueError("exposure contract reference identity is invalid")
        return self


class FinancePublicContractRegressionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    population_path: str = Field(min_length=1)
    population_sha256: str = Field(min_length=64, max_length=64)
    population_id: str = Field(min_length=1)
    exposure_contract_references: tuple[ExposureContractReference, ...] = Field(
        min_length=1
    )
    excluded_task_signatures: tuple[str, ...] = Field(min_length=1)
    excluded_task_signature_set_hash: str = Field(min_length=1)
    excluded_evidence_ids: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_id_set_hash: str = Field(min_length=1)
    excluded_evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    excluded_evidence_version_set_hash: str = Field(min_length=1)
    selected_task_signatures: tuple[str, ...] = Field(
        min_length=REGRESSION_TASK_COUNT,
        max_length=REGRESSION_TASK_COUNT,
    )
    selected_task_signature_set_hash: str = Field(min_length=1)
    selected_evidence_ids: tuple[str, ...] = Field(min_length=1)
    selected_evidence_id_set_hash: str = Field(min_length=1)
    selected_evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    selected_evidence_version_set_hash: str = Field(min_length=1)
    model_source_contract_path: str = Field(min_length=1)
    model_source_contract_sha256: str = Field(min_length=64, max_length=64)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(
        min_length=1,
        max_length=1,
    )
    model_sampling_contract_hash: str = Field(min_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=REGRESSION_BINDING_COUNT,
        max_length=REGRESSION_BINDING_COUNT,
    )
    public_contract_audit: PublicContractSatisfiabilityAudit
    replicas: int = Field(default=REGRESSION_REPLICAS, ge=2, le=2)
    requested_rollouts: int = Field(
        default=REGRESSION_ROLLOUT_COUNT,
        ge=REGRESSION_ROLLOUT_COUNT,
        le=REGRESSION_ROLLOUT_COUNT,
    )
    maximum_tool_calls: int = Field(default=MAXIMUM_TOOL_CALLS, ge=1)
    maximum_failed_tool_calls: int = Field(default=MAXIMUM_FAILED_TOOL_CALLS, ge=0)
    maximum_total_observation_bytes: int = Field(
        default=MAXIMUM_OBSERVATION_BYTES,
        ge=1,
    )
    maximum_model_tokens_per_rollout: int = Field(
        default=MODEL_TOKEN_BUDGET,
        ge=1,
    )
    model_contract_repair_attempts: int = Field(default=2, ge=2, le=2)
    random_seed: int
    sampling_salt: str = Field(min_length=1)
    next_permitted_stage: Literal["fresh_public_contract_regression"] = (
        "fresh_public_contract_regression"
    )
    model_ranking_claim_authorized: Literal[False] = False
    capability_localization_claim_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = PUBLIC_CONTRACT_REGRESSION_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinancePublicContractRegressionContract:
        if self.schema_version != PUBLIC_CONTRACT_REGRESSION_CONTRACT_VERSION:
            raise ValueError("public-contract regression version is unsupported")
        if self.maximum_failed_tool_calls != MAXIMUM_FAILED_TOOL_CALLS:
            raise ValueError("public-contract regression changed the failed-call budget")
        if self.maximum_tool_calls != (
            MAXIMUM_REQUIRED_TOOL_CALLS + self.maximum_failed_tool_calls
        ):
            raise ValueError("public-contract regression lacks failed-call recovery capacity")
        if {item.arm for item in self.model_contracts} != set(REGRESSION_MODEL_ARMS):
            raise ValueError("public-contract regression must be Flash-only")
        if self.model_sampling_contract_hash != _model_sampling_contract_hash(
            self.model_contracts
        ):
            raise ValueError("public-contract regression model identity is invalid")
        reference_paths = tuple(item.contract_path for item in self.exposure_contract_references)
        if len(set(reference_paths)) != len(reference_paths):
            raise ValueError("exposure contracts are duplicated")
        expected_excluded = tuple(
            sorted(
                {
                    signature
                    for reference in self.exposure_contract_references
                    for signature in reference.exposed_task_signatures
                }
            )
        )
        if self.excluded_task_signatures != expected_excluded:
            raise ValueError("excluded signatures differ from frozen exposure contracts")
        expected_evidence_ids = tuple(
            sorted(
                {
                    evidence_id
                    for reference in self.exposure_contract_references
                    for evidence_id in reference.exposed_evidence_ids
                }
            )
        )
        expected_evidence_versions = tuple(
            sorted(
                {
                    version_id
                    for reference in self.exposure_contract_references
                    for version_id in reference.exposed_evidence_version_ids
                }
            )
        )
        if self.excluded_evidence_ids != expected_evidence_ids:
            raise ValueError("excluded Evidence IDs differ from exposure contracts")
        if self.excluded_evidence_version_ids != expected_evidence_versions:
            raise ValueError("excluded Evidence Versions differ from exposure contracts")
        if len(set(self.selected_task_signatures)) != REGRESSION_TASK_COUNT:
            raise ValueError("selected regression task signatures are not unique")
        if set(self.excluded_task_signatures) & set(self.selected_task_signatures):
            raise ValueError("fresh regression reuses a prior exposed task signature")
        if set(self.excluded_evidence_ids) & set(self.selected_evidence_ids):
            raise ValueError("fresh regression reuses a prior exposed Evidence ID")
        if set(self.excluded_evidence_version_ids) & set(
            self.selected_evidence_version_ids
        ):
            raise ValueError("fresh regression reuses a prior exposed Evidence Version")
        if self.excluded_task_signature_set_hash != _signature_set_hash(
            self.excluded_task_signatures,
            prefix="finance_excluded_exposure_signatures:",
        ):
            raise ValueError("excluded exposure signature identity is invalid")
        if self.selected_task_signature_set_hash != _signature_set_hash(
            self.selected_task_signatures,
            prefix="finance_regression_selected_signatures:",
        ):
            raise ValueError("selected task signature identity is invalid")
        identity_fields = (
            (
                self.excluded_evidence_ids,
                self.excluded_evidence_id_set_hash,
                "finance_excluded_exposure_evidence_ids:",
            ),
            (
                self.excluded_evidence_version_ids,
                self.excluded_evidence_version_set_hash,
                "finance_excluded_exposure_evidence_versions:",
            ),
            (
                self.selected_evidence_ids,
                self.selected_evidence_id_set_hash,
                "finance_regression_selected_evidence_ids:",
            ),
            (
                self.selected_evidence_version_ids,
                self.selected_evidence_version_set_hash,
                "finance_regression_selected_evidence_versions:",
            ),
        )
        if any(
            observed_hash != _signature_set_hash(values, prefix=prefix)
            for values, observed_hash, prefix in identity_fields
        ):
            raise ValueError("regression Evidence identity hash is invalid")
        _validate_regression_bindings(self.bindings)
        selected_task_ids = {item.task_artifact_id for item in self.bindings}
        if len(selected_task_ids) != REGRESSION_TASK_COUNT:
            raise ValueError("regression does not contain exactly seven tasks")
        if {
            item.task_artifact_id for item in self.public_contract_audit.records
        } != selected_task_ids:
            raise ValueError("static audit and regression bindings use different tasks")
        if not self.public_contract_audit.all_public_contracts_satisfiable:
            raise ValueError("API regression requires a passing static public-contract audit")
        if self.public_contract_audit.population_id != self.population_id:
            raise ValueError("static audit belongs to another population")
        expected_rollouts = (
            len(self.bindings) * len(self.model_contracts) * self.replicas
        )
        if self.requested_rollouts != expected_rollouts:
            raise ValueError("public-contract regression rollout count is inconsistent")
        if self.contract_id != public_contract_regression_contract_id(self):
            raise ValueError("public-contract regression identity is invalid")
        return self


class RegressionCellSummary(FrozenModel):
    model_arm: ExplorerArm
    runtime_arm: CapabilityRuntimeArm
    family: str = Field(min_length=1)
    attempted_count: int = Field(ge=1)
    technical_resolution_count: int = Field(ge=0)
    bounded_json_resolution_count: int = Field(ge=0)
    observation_replay_count: int = Field(ge=0)
    authority_integrity_count: int = Field(ge=0)
    semantic_answer_correct_count: int = Field(ge=0)
    valid_success_count: int = Field(ge=0)
    budget_exhaustion_count: int = Field(ge=0)
    runtime_infrastructure_failure_count: int = Field(ge=0)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)


class FinancePublicContractRegressionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    requested_rollout_count: int = Field(ge=1)
    recorded_rollout_count: int = Field(ge=0)
    cells: tuple[RegressionCellSummary, ...] = Field(
        min_length=len(REGRESSION_MODEL_ARMS)
        * len(REGRESSION_RUNTIME_ARMS)
        * len(CAPABILITY_SENSITIVE_FAMILIES),
        max_length=len(REGRESSION_MODEL_ARMS)
        * len(REGRESSION_RUNTIME_ARMS)
        * len(CAPABILITY_SENSITIVE_FAMILIES),
    )
    outcome_set_hash: str = Field(min_length=1)
    technical_resolution_count: int = Field(ge=0)
    selector_contradiction_count: int = Field(ge=0)
    scripted_selection_precondition_failure_count: int = Field(ge=0)
    autonomous_selection_model_violation_count: int = Field(ge=0)
    operation_reference_model_violation_count: int = Field(ge=0)
    ratio_pair_model_violation_count: int = Field(ge=0)
    model_protocol_violation_count: int = Field(ge=0)
    semantic_success_count_by_runtime: dict[CapabilityRuntimeArm, int]
    all_runtime_semantically_reachable: bool
    deterministic_contract_defect_count: int = Field(ge=0)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    status: Literal["passed", "failed"]
    next_permitted_stage: Literal[
        "matched_ladder_construction_only",
        "public_contract_repair_only",
    ]
    semantic_results_are_descriptive_only: Literal[True] = True
    pro_flash_ranking_authorized: Literal[False] = False
    capability_localization_authorized: Literal[False] = False
    bridge_tier_decision_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = PUBLIC_CONTRACT_REGRESSION_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinancePublicContractRegressionReport:
        if self.schema_version != PUBLIC_CONTRACT_REGRESSION_REPORT_VERSION:
            raise ValueError("public-contract regression report version is unsupported")
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("public-contract regression lacks its complete denominator")
        if sum(item.attempted_count for item in self.cells) != self.recorded_rollout_count:
            raise ValueError("regression cells do not cover every rollout")
        expected_cells = {
            (model, runtime, family)
            for model in REGRESSION_MODEL_ARMS
            for runtime in REGRESSION_RUNTIME_ARMS
            for family in CAPABILITY_SENSITIVE_FAMILIES
        }
        if {
            (item.model_arm, item.runtime_arm, item.family) for item in self.cells
        } != expected_cells:
            raise ValueError("regression report lacks a Model x Runtime x Family cell")
        expected_deterministic = (
            self.selector_contradiction_count
            + self.scripted_selection_precondition_failure_count
        )
        if self.deterministic_contract_defect_count != expected_deterministic:
            raise ValueError("deterministic public-contract defect count is inconsistent")
        expected_model_violations = (
            self.autonomous_selection_model_violation_count
            + self.operation_reference_model_violation_count
            + self.ratio_pair_model_violation_count
        )
        if self.model_protocol_violation_count != expected_model_violations:
            raise ValueError("model protocol violation count is inconsistent")
        expected_reachable = all(
            self.semantic_success_count_by_runtime.get(runtime, 0) > 0
            for runtime in REGRESSION_RUNTIME_ARMS
        )
        if self.all_runtime_semantically_reachable != expected_reachable:
            raise ValueError("runtime semantic reachability decision is inconsistent")
        passed = (
            self.technical_resolution_count == self.requested_rollout_count
            and self.deterministic_contract_defect_count == 0
            and self.all_runtime_semantically_reachable
            and all(item.budget_exhaustion_count == 0 for item in self.cells)
            and all(
                item.runtime_infrastructure_failure_count == 0 for item in self.cells
            )
            and all(
                item.bounded_json_resolution_count == item.attempted_count
                for item in self.cells
            )
            and all(
                item.observation_replay_count == item.attempted_count
                for item in self.cells
            )
            and all(
                item.authority_integrity_count == item.attempted_count
                for item in self.cells
            )
        )
        if (self.status == "passed") != passed:
            raise ValueError("public-contract regression status is inconsistent")
        expected_next = (
            "matched_ladder_construction_only"
            if passed
            else "public_contract_repair_only"
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("public-contract regression transition is not fail-closed")
        if self.report_id != public_contract_regression_report_id(self):
            raise ValueError("public-contract regression report identity is invalid")
        return self


def prepare_public_contract_regression(
    *,
    population_path: Path,
    exposure_contract_paths: tuple[Path, ...],
    model_source_contract_path: Path,
    finance_archive_config_path: Path,
    output_path: Path,
    run_id: str,
    random_seed: int,
    sampling_salt: str,
) -> FinancePublicContractRegressionContract:
    if output_path.exists():
        raise ValueError("public-contract regression contract is immutable and exists")
    population_path = population_path.resolve()
    model_source_contract_path = model_source_contract_path.resolve()
    finance_archive_config_path = finance_archive_config_path.resolve()
    exposure_contract_paths = tuple(item.resolve() for item in exposure_contract_paths)
    if not exposure_contract_paths:
        raise ValueError("public-contract regression requires prior exposure contracts")
    population = CapabilitySensitiveFrontierPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    if population.schema_version != CAPABILITY_SENSITIVE_FRONTIER_VERSION:
        raise ValueError("public-contract regression population version is unsupported")
    if not population.audit.structural_frontier_ready:
        raise ValueError("public-contract regression requires a structurally valid population")

    exposure_references = tuple(
        _make_exposure_contract_reference(path) for path in exposure_contract_paths
    )
    excluded_signatures = tuple(
        sorted(
            {
                signature
                for reference in exposure_references
                for signature in reference.exposed_task_signatures
            }
        )
    )
    exposed_ids = {
        artifact_id
        for reference in exposure_references
        for artifact_id in reference.exposed_task_artifact_ids
    }
    exposed_tasks = load_exposed_tasks_from_references(exposure_references)
    exposed_evidence_ids, exposed_evidence_version_ids = _task_evidence_identity_sets(
        exposed_tasks
    )
    selected = _select_fresh_easy_tasks(
        population,
        prior_signatures=set(excluded_signatures),
        prior_artifact_ids=exposed_ids,
        prior_evidence_ids=exposed_evidence_ids,
        prior_evidence_version_ids=exposed_evidence_version_ids,
        sampling_salt=sampling_salt,
    )
    selected_signatures = tuple(
        sorted(public_task_exposure_signature(item) for item in selected)
    )
    selected_evidence_ids, selected_evidence_version_ids = _task_evidence_identity_sets(
        selected
    )
    protocol = IterativeAgentProtocolProfile(
        initial_plan_mode="implicit_public",
        observation_view="compact",
        contract_repair_token_reserve=8_000,
        final_answer_token_reserve=12_000,
        host_repair_missing_verification=True,
    )
    bindings = tuple(
        _make_runtime_binding(task, runtime, protocol)
        for task in selected
        for runtime in REGRESSION_RUNTIME_ARMS
    )
    records = []
    for task in selected:
        for runtime in REGRESSION_RUNTIME_ARMS:
            context, manifest, _ = make_v25_native_runtime_context(task, runtime, protocol)
            records.append(
                make_public_contract_record(
                    task=task,
                    runtime_arm=cast(RuntimeArmName, runtime.value),
                    runtime_task=context.task,
                    manifest=manifest,
                    maximum_required_tool_calls=MAXIMUM_REQUIRED_TOOL_CALLS,
                )
            )
    static_audit = make_public_contract_audit(
        population_id=population.population_id,
        records=tuple(records),
        required_runtime_arms=tuple(
            cast(RuntimeArmName, runtime.value) for runtime in REGRESSION_RUNTIME_ARMS
        ),
    )
    if not static_audit.all_public_contracts_satisfiable:
        raise ValueError("public-contract static audit failed; API access is forbidden")

    model_source = FinanceProFlashPilotContract.model_validate_json(
        model_source_contract_path.read_text(encoding="utf-8")
    )
    model_contracts = tuple(
        item for item in model_source.model_contracts if item.arm in REGRESSION_MODEL_ARMS
    )
    if len(model_contracts) != len(REGRESSION_MODEL_ARMS):
        raise ValueError("model source lacks the frozen Flash contract")
    values = {
        "run_id": run_id,
        "population_path": str(population_path),
        "population_sha256": _sha256(population_path),
        "population_id": population.population_id,
        "exposure_contract_references": exposure_references,
        "excluded_task_signatures": excluded_signatures,
        "excluded_task_signature_set_hash": _signature_set_hash(
            excluded_signatures,
            prefix="finance_excluded_exposure_signatures:",
        ),
        "excluded_evidence_ids": tuple(sorted(exposed_evidence_ids)),
        "excluded_evidence_id_set_hash": _signature_set_hash(
            exposed_evidence_ids,
            prefix="finance_excluded_exposure_evidence_ids:",
        ),
        "excluded_evidence_version_ids": tuple(sorted(exposed_evidence_version_ids)),
        "excluded_evidence_version_set_hash": _signature_set_hash(
            exposed_evidence_version_ids,
            prefix="finance_excluded_exposure_evidence_versions:",
        ),
        "selected_task_signatures": selected_signatures,
        "selected_task_signature_set_hash": _signature_set_hash(
            selected_signatures,
            prefix="finance_regression_selected_signatures:",
        ),
        "selected_evidence_ids": tuple(sorted(selected_evidence_ids)),
        "selected_evidence_id_set_hash": _signature_set_hash(
            selected_evidence_ids,
            prefix="finance_regression_selected_evidence_ids:",
        ),
        "selected_evidence_version_ids": tuple(sorted(selected_evidence_version_ids)),
        "selected_evidence_version_set_hash": _signature_set_hash(
            selected_evidence_version_ids,
            prefix="finance_regression_selected_evidence_versions:",
        ),
        "model_source_contract_path": str(model_source_contract_path),
        "model_source_contract_sha256": _sha256(model_source_contract_path),
        "finance_archive_config_path": str(finance_archive_config_path),
        "finance_archive_config_sha256": _sha256(finance_archive_config_path),
        "model_contracts": model_contracts,
        "model_sampling_contract_hash": _model_sampling_contract_hash(model_contracts),
        "protocol_profile": protocol,
        "bindings": bindings,
        "public_contract_audit": static_audit,
        "replicas": REGRESSION_REPLICAS,
        "requested_rollouts": REGRESSION_ROLLOUT_COUNT,
        "maximum_tool_calls": MAXIMUM_TOOL_CALLS,
        "maximum_failed_tool_calls": MAXIMUM_FAILED_TOOL_CALLS,
        "maximum_total_observation_bytes": MAXIMUM_OBSERVATION_BYTES,
        "maximum_model_tokens_per_rollout": MODEL_TOKEN_BUDGET,
        "model_contract_repair_attempts": 2,
        "random_seed": random_seed,
        "sampling_salt": sampling_salt,
        "next_permitted_stage": "fresh_public_contract_regression",
        "model_ranking_claim_authorized": False,
        "capability_localization_claim_authorized": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = FinancePublicContractRegressionContract.model_construct(
        contract_id="pending",
        **values,
    )
    contract = FinancePublicContractRegressionContract(
        contract_id=public_contract_regression_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_public_contract_regression(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinancePublicContractRegressionReport:
    if workers < 1:
        raise ValueError("public-contract regression workers must be positive")
    contract = FinancePublicContractRegressionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_frozen_inputs(contract)
    if not contract.public_contract_audit.all_public_contracts_satisfiable:
        raise ValueError("static audit failed; API regression is forbidden")
    population_path = resolve_regression_population_path(contract)
    population = CapabilitySensitiveFrontierPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    tasks = {item.artifact_id: item for item in population.tasks}
    required_task_ids = {item.task_artifact_id for item in contract.bindings}
    if not required_task_ids <= set(tasks):
        raise ValueError("regression bindings reference missing task artifacts")

    run_identity = _run_identity(contract)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "public_contract_regression.checkpoint.jsonl"
    records_path = output_dir / "public_contract_regression_records.jsonl"
    outcomes_path = output_dir / "public_contract_regression_outcomes.jsonl"
    report_path = output_dir / "finance_public_contract_regression_report.json"
    manifest_path = output_dir / "public_contract_regression_run_manifest.json"
    historical = _load_checkpoint(
        checkpoint_path,
        run_identity=run_identity,
        contract=contract,
    )
    records = {_record_key(item): item for item in historical}
    jobs = tuple(
        (model, binding, replicate)
        for binding in sorted(contract.bindings, key=lambda item: item.binding_id)
        for replicate in range(contract.replicas)
        for model in REGRESSION_MODEL_ARMS
    )
    pending = tuple(
        item
        for item in jobs
        if (item[0], item[1].binding_id, item[2]) not in records
    )
    print(
        f"[v25.9:public_contract_regression] resuming {len(records)}/{len(jobs)}; "
        f"executing {len(pending)} with {min(workers, max(1, len(pending)))} workers",
        flush=True,
    )
    clients: dict[ExplorerArm, OpenAICompatibleJsonClient] = {}
    if pending:
        model_contracts = {item.arm: item for item in contract.model_contracts}
        clients = {
            arm: OpenAICompatibleJsonClient(
                item.config.model_copy(
                    update={
                        "contract_repair_attempts": contract.model_contract_repair_attempts
                    }
                )
            )
            for arm, item in model_contracts.items()
        }
        discovered = {arm: client.discover_models() for arm, client in clients.items()}
        discovery_source = "live_provider"
    else:
        discovered = _load_discovered_models(manifest_path, run_identity)
        discovery_source = "frozen_run_manifest"
    for arm in REGRESSION_MODEL_ARMS:
        if EXPECTED_MODELS[arm.value] not in discovered.get(arm, ()):
            raise ValueError(f"provider evidence lacks frozen {arm.value} model")

    if pending:
        with ThreadPoolExecutor(max_workers=min(workers, len(pending))) as executor:
            futures = {
                executor.submit(
                    _run_one,
                    contract,
                    BoundaryStage.RUNTIME_QUALIFICATION,
                    model,
                    binding,
                    tasks[binding.task_artifact_id],
                    replicate,
                    run_identity,
                    clients[model],
                ): (model, binding.binding_id, replicate)
                for model, binding, replicate in pending
            }
            for index, future in enumerate(as_completed(futures), start=1):
                key = futures[future]
                record = future.result()
                if key != _record_key(record):
                    raise ValueError("public-contract worker returned another job")
                _append_jsonl(checkpoint_path, record.model_dump(mode="json"))
                records[key] = record
                if index % 10 == 0 or index == len(futures):
                    print(
                        "[v25.9:public_contract_regression] "
                        f"completed {len(records)}/{len(jobs)}",
                        flush=True,
                    )

    ordered = tuple(
        records[(model, binding.binding_id, replicate)]
        for model, binding, replicate in jobs
    )
    _write_jsonl_atomic(records_path, (item.model_dump(mode="json") for item in ordered))
    outcomes = tuple(_to_outcome(item, contract.bindings) for item in ordered)
    _write_jsonl_atomic(
        outcomes_path,
        (item.model_dump(mode="json") for item in outcomes),
    )
    report = make_public_contract_regression_report(contract, ordered, outcomes)
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_json_atomic(
        manifest_path,
        {
            "run_identity": run_identity,
            "runner_version": PUBLIC_CONTRACT_REGRESSION_RUNNER_VERSION,
            "reused_boundary_runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
            "contract_id": contract.contract_id,
            "static_audit_id": contract.public_contract_audit.audit_id,
            "discovered_models": {
                arm.value: values for arm, values in discovered.items()
            },
            "model_discovery_source": discovery_source,
            "checkpoint_sha256": _sha256(checkpoint_path),
            "records_sha256": _sha256(records_path),
            "outcomes_sha256": _sha256(outcomes_path),
            "outcome_set_hash": report.outcome_set_hash,
            "report_id": report.report_id,
            "report_schema_version": report.schema_version,
            "report_sha256": _sha256(report_path),
        },
    )
    return report


def make_public_contract_regression_report(
    contract: FinancePublicContractRegressionContract,
    records: tuple[CapabilityBoundaryRolloutRecord, ...],
    outcomes: tuple[CapabilityRolloutOutcome, ...],
) -> FinancePublicContractRegressionReport:
    if len(records) != contract.requested_rollouts or len(outcomes) != len(records):
        raise ValueError("regression report requires a complete frozen denominator")
    by_binding = {item.binding_id: item for item in contract.bindings}
    cells = []
    for model in REGRESSION_MODEL_ARMS:
        for runtime in REGRESSION_RUNTIME_ARMS:
            for family in CAPABILITY_SENSITIVE_FAMILIES:
                values = tuple(
                    item
                    for item in outcomes
                    if (
                        item.model_arm == model
                        and item.runtime_arm == runtime
                        and item.family == family
                    )
                )
                if len(values) != contract.replicas:
                    raise ValueError("regression cell lacks its two frozen replicas")
                cells.append(
                    RegressionCellSummary(
                        model_arm=model,
                        runtime_arm=runtime,
                        family=family,
                        attempted_count=len(values),
                        technical_resolution_count=sum(item.completed for item in values),
                        bounded_json_resolution_count=sum(
                            item.bounded_json_resolution_success for item in values
                        ),
                        observation_replay_count=sum(
                            item.observation_replay_success for item in values
                        ),
                        authority_integrity_count=sum(
                            item.authority_integrity_success for item in values
                        ),
                        semantic_answer_correct_count=sum(
                            item.semantic_answer_correct for item in values
                        ),
                        valid_success_count=sum(item.valid_success for item in values),
                        budget_exhaustion_count=sum(
                            item.budget_exhausted for item in values
                        ),
                        runtime_infrastructure_failure_count=sum(
                            item.runtime_infrastructure_failure_count for item in values
                        ),
                        api_call_count=sum(item.api_call_count for item in values),
                        total_model_tokens=sum(item.total_model_tokens for item in values),
                        estimated_cost_usd=sum(
                            item.estimated_cost_usd for item in values
                        ),
                    )
                )
    selector_count = sum(_contains_selector_contradiction(item) for item in records)
    scripted_precondition_count = sum(
        (
            by_binding[item.binding_id].runtime_arm
            == CapabilityRuntimeArm.SCRIPTED_TOOL
        )
        and _contains_selection_precondition_failure(item)
        for item in records
    )
    autonomous_model_selection_count = sum(
        (
            by_binding[item.binding_id].runtime_arm
            == CapabilityRuntimeArm.AUTONOMOUS_AGENT
        )
        and (
            _contains_selector_contradiction(item)
            or _contains_selection_precondition_failure(item)
        )
        for item in records
    )
    operation_reference_count = sum(
        _contains_operation_reference_model_violation(item) for item in records
    )
    ratio_pair_count = sum(
        _contains_ratio_pair_model_violation(item) for item in records
    )
    semantic_by_runtime = {
        runtime: sum(
            item.semantic_answer_correct for item in outcomes if item.runtime_arm == runtime
        )
        for runtime in REGRESSION_RUNTIME_ARMS
    }
    technical_count = sum(item.completed for item in outcomes)
    deterministic_count = selector_count + scripted_precondition_count
    model_protocol_count = (
        autonomous_model_selection_count + operation_reference_count + ratio_pair_count
    )
    all_reachable = all(value > 0 for value in semantic_by_runtime.values())
    passed = (
        technical_count == contract.requested_rollouts
        and deterministic_count == 0
        and all_reachable
        and all(item.budget_exhaustion_count == 0 for item in cells)
        and all(item.runtime_infrastructure_failure_count == 0 for item in cells)
        and all(
            item.bounded_json_resolution_count == item.attempted_count for item in cells
        )
        and all(item.observation_replay_count == item.attempted_count for item in cells)
        and all(item.authority_integrity_count == item.attempted_count for item in cells)
    )
    report_values = {
        "contract_id": contract.contract_id,
        "static_audit_id": contract.public_contract_audit.audit_id,
        "requested_rollout_count": contract.requested_rollouts,
        "recorded_rollout_count": len(outcomes),
        "cells": tuple(cells),
        "outcome_set_hash": canonical_hash(
            tuple(sorted(item.outcome_id for item in outcomes)),
            prefix="finance_public_contract_regression_outcomes:",
        ),
        "technical_resolution_count": technical_count,
        "selector_contradiction_count": selector_count,
        "scripted_selection_precondition_failure_count": scripted_precondition_count,
        "autonomous_selection_model_violation_count": autonomous_model_selection_count,
        "operation_reference_model_violation_count": operation_reference_count,
        "ratio_pair_model_violation_count": ratio_pair_count,
        "model_protocol_violation_count": model_protocol_count,
        "semantic_success_count_by_runtime": semantic_by_runtime,
        "all_runtime_semantically_reachable": all_reachable,
        "deterministic_contract_defect_count": deterministic_count,
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "status": "passed" if passed else "failed",
        "next_permitted_stage": (
            "matched_ladder_construction_only"
            if passed
            else "public_contract_repair_only"
        ),
        "semantic_results_are_descriptive_only": True,
        "pro_flash_ranking_authorized": False,
        "capability_localization_authorized": False,
        "bridge_tier_decision_authorized": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    provisional = FinancePublicContractRegressionReport.model_construct(
        report_id="pending",
        **report_values,
    )
    return FinancePublicContractRegressionReport(
        report_id=public_contract_regression_report_id(provisional),
        **report_values,
    )


def public_task_exposure_signature(
    task: CapabilitySensitiveTaskArtifact | Mapping[str, Any],
) -> str:
    raw = (
        task.model_dump(mode="json")
        if isinstance(task, CapabilitySensitiveTaskArtifact)
        else dict(task)
    )
    task_value = cast(Mapping[str, Any], raw["task"])
    public = cast(Mapping[str, Any], task_value["public"])
    oracle = cast(Mapping[str, Any], task_value["oracle"])
    program = cast(Mapping[str, Any], oracle["task_program"])
    corpus = cast(Mapping[str, Any], raw["public_corpus"])
    evidence = cast(list[Mapping[str, Any]], corpus["evidence"])
    evidence_semantics = tuple(
        sorted(
            (
                str(item["subject"]["subject_id"]),
                str(item["predicate"]),
                str(item["temporal_context"].get("label") or ""),
                str(item["definition"]["definition_id"]),
                str(item["source"]["source_id"]),
            )
            for item in evidence
        )
    )
    program_semantics = tuple(
        (
            str(node["operator_id"]),
            tuple(
                (
                    str(ref["kind"]),
                    str(ref.get("role_id") or ""),
                    str(ref.get("selector") or ""),
                )
                for ref in node["input_refs"]
            ),
            tuple(sorted(cast(Mapping[str, Any], node.get("parameters", {})).items())),
        )
        for node in program["nodes"]
    )
    return canonical_hash(
        {
            "version": FRESHNESS_SIGNATURE_VERSION,
            "family": str(raw["family"]),
            "task_type": str(public["task_type"]),
            "instruction": _normalize_text(str(public["instruction"])),
            "evidence_semantics": evidence_semantics,
            "program_semantics": program_semantics,
        },
        prefix="finance_public_task_exposure_signature:",
    )


def _make_exposure_contract_reference(
    contract_path: Path,
) -> ExposureContractReference:
    raw = json.loads(contract_path.read_text(encoding="utf-8"))
    schema_version = str(raw.get("schema_version") or "")
    binding_fields: tuple[str, ...]
    source_task_map: Mapping[str, Any] | None = None
    population_path_field = "population_path"
    if schema_version.startswith("finance_capability_boundary_contract."):
        binding_fields = ("localization_bindings", "qualification_bindings")
    elif schema_version.startswith("finance_public_contract_regression_contract."):
        binding_fields = ("bindings",)
    elif schema_version.startswith("finance_matched_tier_localization_contract."):
        binding_fields = ("bindings",)
    elif schema_version.startswith("finance_structural_tier_localization_contract."):
        binding_fields = ("bindings",)
    elif schema_version.startswith("finance_multitier_runtime_repair_calibration.") or (
        schema_version.startswith("finance_runtime_resolution_contract.")
    ):
        binding_fields = ("bindings",)
        population_path_field = "source_population_path"
        raw_source_map = raw.get("source_task_artifact_ids")
        if not isinstance(raw_source_map, Mapping):
            raise ValueError("runtime exposure contract lacks source task identities")
        source_task_map = raw_source_map
    else:
        raise ValueError(
            f"unsupported exposure contract schema: {schema_version or '<missing>'}"
        )
    population_path = Path(str(raw.get(population_path_field) or "")).resolve()
    if not population_path.is_file():
        raise ValueError("exposure contract population cannot be loaded")
    population = json.loads(population_path.read_text(encoding="utf-8"))
    tasks = _population_tasks_by_id(population)
    bound_ids = tuple(
        sorted(
            {
                str(item["task_artifact_id"])
                for field in binding_fields
                for item in raw.get(field, ())
                if isinstance(item, Mapping) and item.get("task_artifact_id")
            }
        )
    )
    exposed_ids = tuple(
        sorted(
            {
                str(source_task_map[item]) if source_task_map is not None else item
                for item in bound_ids
                if source_task_map is None or item in source_task_map
            }
        )
    )
    if source_task_map is not None and len(exposed_ids) != len(bound_ids):
        raise ValueError("runtime exposure source task mapping is incomplete")
    if not exposed_ids or not set(exposed_ids) <= set(tasks):
        raise ValueError("exposure contract task identities cannot be reconstructed")
    exposed_tasks = tuple(tasks[item] for item in exposed_ids)
    signatures = tuple(
        sorted(public_task_exposure_signature(tasks[item]) for item in exposed_ids)
    )
    if len(set(signatures)) != len(exposed_ids):
        raise ValueError("exposure contract contains a semantic task collision")
    values = {
        "contract_path": str(contract_path),
        "contract_sha256": _sha256(contract_path),
        "contract_id": str(raw.get("contract_id") or ""),
        "contract_schema_version": schema_version,
        "population_path": str(population_path),
        "population_sha256": _sha256(population_path),
        "population_id": str(population.get("population_id") or raw.get("population_id") or ""),
        "binding_field_names": tuple(sorted(binding_fields)),
        "exposed_task_artifact_ids": exposed_ids,
        "exposed_task_signatures": signatures,
        "exposed_evidence_ids": tuple(
            sorted(_task_evidence_identity_sets(exposed_tasks)[0])
        ),
        "exposed_evidence_version_ids": tuple(
            sorted(_task_evidence_identity_sets(exposed_tasks)[1])
        ),
    }
    if not values["contract_id"] or not values["population_id"]:
        raise ValueError("exposure contract or population lacks immutable identity")
    provisional = ExposureContractReference.model_construct(
        reference_id="pending",
        **values,
    )
    return ExposureContractReference(
        reference_id=exposure_contract_reference_id(provisional),
        **values,
    )


def load_exposed_tasks_from_references(
    references: Iterable[ExposureContractReference],
) -> tuple[Mapping[str, Any], ...]:
    exposed: dict[str, Mapping[str, Any]] = {}
    for reference in references:
        contract_path = Path(reference.contract_path)
        population_path = Path(reference.population_path)
        if _sha256(contract_path) != reference.contract_sha256:
            raise ValueError("exposure contract changed after regression freeze")
        if _sha256(population_path) != reference.population_sha256:
            raise ValueError("exposure population changed after regression freeze")
        tasks = _population_tasks_by_id(
            json.loads(population_path.read_text(encoding="utf-8"))
        )
        for artifact_id in reference.exposed_task_artifact_ids:
            task = tasks.get(artifact_id)
            if task is None:
                raise ValueError("frozen exposure task is absent from its population")
            exposed[artifact_id] = task
        observed = tuple(
            sorted(
                public_task_exposure_signature(tasks[item])
                for item in reference.exposed_task_artifact_ids
            )
        )
        if observed != reference.exposed_task_signatures:
            raise ValueError("frozen exposure semantics changed")
    return tuple(exposed[item] for item in sorted(exposed))


def _population_tasks_by_id(
    population: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    values = [
        item
        for item in population.get("tasks", ())
        if isinstance(item, Mapping)
    ]
    values.extend(
        item
        for group in population.get("groups", ())
        if isinstance(group, Mapping)
        for item in group.get("variants", ())
        if isinstance(item, Mapping)
    )
    tasks = {str(item.get("artifact_id") or ""): item for item in values}
    tasks.pop("", None)
    if len(tasks) != len(values):
        raise ValueError("exposure population duplicates task identities")
    return tasks


def _select_fresh_easy_tasks(
    population: CapabilitySensitiveFrontierPopulation,
    *,
    prior_signatures: set[str],
    prior_artifact_ids: set[str],
    prior_evidence_ids: set[str],
    prior_evidence_version_ids: set[str],
    sampling_salt: str,
) -> tuple[CapabilitySensitiveTaskArtifact, ...]:
    selected = []
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        candidates = tuple(
            item
            for item in population.tasks
            if (
                item.family == family
                and item.tier == DifficultyTier.EASY_CONTROL
                and item.artifact_id not in prior_artifact_ids
                and public_task_exposure_signature(item) not in prior_signatures
                and not (
                    {evidence.evidence_id for evidence in item.public_corpus.evidence}
                    & prior_evidence_ids
                )
                and not (
                    {
                        evidence.evidence_version_id
                        for evidence in item.public_corpus.evidence
                    }
                    & prior_evidence_version_ids
                )
            )
        )
        ordered = sorted(
            candidates,
            key=lambda item: canonical_hash(
                {
                    "salt": sampling_salt,
                    "artifact_id": item.artifact_id,
                    "signature": public_task_exposure_signature(item),
                },
                prefix="finance_public_contract_regression_selection:",
            ),
        )
        if len(ordered) < REGRESSION_TASKS_PER_FAMILY:
            raise ValueError(f"no semantically fresh Easy task remains for {family}")
        selected.extend(ordered[:REGRESSION_TASKS_PER_FAMILY])
    return tuple(selected)


def _task_evidence_identity_sets(
    tasks: Iterable[CapabilitySensitiveTaskArtifact | Mapping[str, Any]],
) -> tuple[set[str], set[str]]:
    evidence_ids: set[str] = set()
    evidence_version_ids: set[str] = set()
    for task in tasks:
        raw = (
            task.model_dump(mode="json")
            if isinstance(task, CapabilitySensitiveTaskArtifact)
            else task
        )
        corpus = raw.get("public_corpus")
        evidence = corpus.get("evidence") if isinstance(corpus, Mapping) else None
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("exposed task lacks immutable public Evidence")
        for item in evidence:
            if not isinstance(item, Mapping):
                raise ValueError("exposed task contains malformed Evidence")
            evidence_id = item.get("evidence_id")
            evidence_version_id = item.get("evidence_version_id")
            if not isinstance(evidence_id, str) or not evidence_id:
                raise ValueError("exposed task Evidence lacks an ID")
            if not isinstance(evidence_version_id, str) or not evidence_version_id:
                raise ValueError("exposed task Evidence lacks a Version ID")
            evidence_ids.add(evidence_id)
            evidence_version_ids.add(evidence_version_id)
    if not evidence_ids or not evidence_version_ids:
        raise ValueError("task Evidence identity set is empty")
    return evidence_ids, evidence_version_ids


def _validate_regression_bindings(bindings: tuple[RuntimeTaskBinding, ...]) -> None:
    by_task: dict[str, list[RuntimeTaskBinding]] = defaultdict(list)
    for item in bindings:
        if item.tier != DifficultyTier.EASY_CONTROL:
            raise ValueError("public-contract regression may use only fresh Easy tasks")
        by_task[item.task_artifact_id].append(item)
    if len(bindings) != REGRESSION_BINDING_COUNT or len(by_task) != REGRESSION_TASK_COUNT:
        raise ValueError("public-contract regression binding count is invalid")
    for values in by_task.values():
        if {item.runtime_arm for item in values} != set(REGRESSION_RUNTIME_ARMS):
            raise ValueError("a regression task lacks a Runtime binding")
        if len(values) != len(REGRESSION_RUNTIME_ARMS):
            raise ValueError("a regression task duplicates a Runtime binding")
    counts = {
        family: len({item.task_artifact_id for item in bindings if item.family == family})
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }
    if counts != {
        family: REGRESSION_TASKS_PER_FAMILY
        for family in CAPABILITY_SENSITIVE_FAMILIES
    }:
        raise ValueError("public-contract regression is not balanced by family")


def _contains_selector_contradiction(record: CapabilityBoundaryRolloutRecord) -> bool:
    value = _record_search_text(record)
    return "public_selector_mismatch" in value or (
        "selector" in value
        and any(item in value for item in ("contradiction", "selector_mismatch"))
    )


def _contains_selection_precondition_failure(
    record: CapabilityBoundaryRolloutRecord,
) -> bool:
    value = _record_search_text(record)
    return any(
        item in value
        for item in (
            "missing selected_evidence",
            "selected evidence is required",
            "selected_evidence precondition",
            "tool preconditions are not closed",
            "calculator evidence was not selected",
            "evidence ids were not selected",
        )
    )


def _contains_operation_reference_model_violation(
    record: CapabilityBoundaryRolloutRecord,
) -> bool:
    value = _record_search_text(record)
    return any(
        item in value
        for item in (
            "operation selector is invalid",
            "calculator operation reference is unknown",
            "calculator operand object needs evidence_id, operation_ref, or value",
        )
    )


def _contains_ratio_pair_model_violation(
    record: CapabilityBoundaryRolloutRecord,
) -> bool:
    value = _record_search_text(record)
    return any(
        item in value
        for item in (
            "ratio pair is not explicitly registered",
            "ratio inputs require registered definitions",
        )
    )


def _record_search_text(record: CapabilityBoundaryRolloutRecord) -> str:
    return json.dumps(
        record.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    ).casefold()


def _verify_frozen_inputs(contract: FinancePublicContractRegressionContract) -> None:
    resolve_regression_population_path(contract)
    paths = [
        (
            Path(contract.model_source_contract_path),
            contract.model_source_contract_sha256,
        ),
        (
            Path(contract.finance_archive_config_path),
            contract.finance_archive_config_sha256,
        ),
    ]
    paths.extend(
        (Path(reference.contract_path), reference.contract_sha256)
        for reference in contract.exposure_contract_references
    )
    paths.extend(
        (Path(reference.population_path), reference.population_sha256)
        for reference in contract.exposure_contract_references
    )
    for path, expected in paths:
        if _sha256(path) != expected:
            raise ValueError(f"frozen public-contract regression input changed: {path}")


def resolve_regression_population_path(
    contract: FinancePublicContractRegressionContract,
) -> Path:
    return resolve_frozen_input(
        Path(contract.population_path),
        contract.population_sha256,
        mirror_roots=(
            project_frozen_input_mirror_root(
                Path(contract.finance_archive_config_path)
            ),
        ),
    )


def _load_checkpoint(
    path: Path,
    *,
    run_identity: str,
    contract: FinancePublicContractRegressionContract,
) -> tuple[CapabilityBoundaryRolloutRecord, ...]:
    if not path.is_file():
        return ()
    records = tuple(
        CapabilityBoundaryRolloutRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    binding_ids = {item.binding_id for item in contract.bindings}
    keys = set()
    for record in records:
        key = _record_key(record)
        if key in keys:
            raise ValueError("regression checkpoint contains duplicate jobs")
        keys.add(key)
        if (
            record.run_identity != run_identity
            or record.binding_id not in binding_ids
            or not 0 <= record.replicate < contract.replicas
        ):
            raise ValueError("regression checkpoint contains an unknown job")
    return records


def _load_discovered_models(
    manifest_path: Path,
    run_identity: str,
) -> dict[ExplorerArm, tuple[str, ...]]:
    if not manifest_path.is_file():
        raise ValueError("completed regression lacks a frozen model-discovery manifest")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if raw.get("run_identity") != run_identity:
        raise ValueError("regression run manifest belongs to another run")
    discovered = raw.get("discovered_models")
    if not isinstance(discovered, dict):
        raise ValueError("regression run manifest lacks model discovery evidence")
    return {
        arm: tuple(str(item) for item in discovered.get(arm.value, ()))
        for arm in REGRESSION_MODEL_ARMS
    }


def _model_sampling_contract_hash(
    contracts: tuple[ExplorerModelContract, ...],
) -> str:
    if {item.arm for item in contracts} != set(REGRESSION_MODEL_ARMS):
        raise ValueError("public regression model contracts are incomplete")
    return canonical_hash(
        tuple(
            item.model_dump(mode="json")
            for item in sorted(contracts, key=lambda value: value.arm.value)
        ),
        prefix="finance_public_regression_model_sampling_contract:",
    )


def _run_identity(contract: FinancePublicContractRegressionContract) -> str:
    return canonical_hash(
        {
            "contract_id": contract.contract_id,
            "runner_version": PUBLIC_CONTRACT_REGRESSION_RUNNER_VERSION,
            "reused_boundary_runner_version": CAPABILITY_BOUNDARY_RUNNER_VERSION,
            "binding_ids": tuple(sorted(item.binding_id for item in contract.bindings)),
            "replicas": contract.replicas,
        },
        prefix="finance_public_contract_regression_run:",
    )


def _record_key(
    record: CapabilityBoundaryRolloutRecord,
) -> tuple[ExplorerArm, str, int]:
    return record.model_arm, record.binding_id, record.replicate


def _signature_set_hash(signatures: Iterable[str], *, prefix: str) -> str:
    return canonical_hash(tuple(sorted(signatures)), prefix=prefix)


def _normalize_text(value: str) -> str:
    return " ".join(
        "".join(
            character.casefold() if character.isalnum() else " " for character in value
        ).split()
    )


def public_contract_regression_contract_id(
    value: FinancePublicContractRegressionContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_public_contract_regression_contract:",
    )


def exposure_contract_reference_id(value: ExposureContractReference) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"reference_id"}),
        prefix="finance_exposure_contract_reference:",
    )


def public_contract_regression_report_id(
    value: FinancePublicContractRegressionReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_public_contract_regression_report:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def _write_jsonl_atomic(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Finance v25.9 contract regression")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--population", type=Path, required=True)
    prepare.add_argument(
        "--exposure-contract",
        type=Path,
        action="append",
        required=True,
        dest="exposure_contracts",
    )
    prepare.add_argument("--model-source-contract", type=Path, required=True)
    prepare.add_argument("--finance-config", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--random-seed", type=int, default=25_900)
    prepare.add_argument("--sampling-salt", default="finance-v25.9-public-contract-regression")
    run = subparsers.add_parser("run")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--workers", type=int, default=14)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "prepare":
        contract = prepare_public_contract_regression(
            population_path=args.population,
            exposure_contract_paths=tuple(args.exposure_contracts),
            model_source_contract_path=args.model_source_contract,
            finance_archive_config_path=args.finance_config,
            output_path=args.output,
            run_id=args.run_id,
            random_seed=args.random_seed,
            sampling_salt=args.sampling_salt,
        )
        print(
            json.dumps(
                {
                    "contract_id": contract.contract_id,
                    "static_audit_id": contract.public_contract_audit.audit_id,
                    "static_audit_passed": (
                        contract.public_contract_audit.all_public_contracts_satisfiable
                    ),
                    "requested_rollouts": contract.requested_rollouts,
                },
                indent=2,
            )
        )
    else:
        report = run_public_contract_regression(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
