from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_runtime_pilot import (
    AgentPilotArm,
    AgentPilotArmContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_FAMILIES,
    FinanceProFlashPilotContract,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import ITERATIVE_AGENT_SOLVER_VERSION

EXPLORER_RUNTIME_FACTORIAL_CONTRACT_VERSION = "finance_explorer_runtime_factorial_contract.v1"
SCRIPTED_TOOL_POLICY_VERSION = "finance_scripted_tool_policy.v1"

_SCRIPTED_TOOL_SEQUENCES: dict[str, tuple[str, ...]] = {
    "finance.comparison": (
        "search_archive",
        "query_structured_fact",
        "query_structured_fact",
        "normalize_metric_unit_period",
        "calculator",
        "cross_check_evidence",
    ),
    "finance.derived_growth_comparison": (
        "search_archive",
        "query_structured_fact",
        "query_structured_fact",
        "query_structured_fact",
        "query_structured_fact",
        "normalize_metric_unit_period",
        "calculator",
        "calculator",
        "calculator",
        "cross_check_evidence",
    ),
    "finance.registered_ratio": (
        "search_archive",
        "query_structured_fact",
        "query_structured_fact",
        "normalize_metric_unit_period",
        "calculator",
        "cross_check_evidence",
    ),
    "finance.temporal_absolute_change": (
        "search_archive",
        "query_structured_fact",
        "query_structured_fact",
        "normalize_metric_unit_period",
        "calculator",
        "cross_check_evidence",
    ),
    "finance.temporal_average": (
        "search_archive",
        "query_structured_fact",
        "query_structured_fact",
        "query_structured_fact",
        "normalize_metric_unit_period",
        "calculator",
        "cross_check_evidence",
    ),
    "finance.temporal_growth": (
        "search_archive",
        "query_structured_fact",
        "query_structured_fact",
        "normalize_metric_unit_period",
        "calculator",
        "cross_check_evidence",
    ),
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FactorialThresholds(FrozenModel):
    minimum_calibration_completion_rate: float = Field(default=1.0, ge=0, le=1)
    minimum_calibration_json_contract_rate: float = Field(default=0.95, ge=0, le=1)
    minimum_valid_trajectories_per_model_runtime: int = Field(default=1, ge=1)
    minimum_interactive_tool_success_rate: float = Field(default=0.80, ge=0, le=1)
    minimum_autonomous_validity_rate: float = Field(default=0.65, ge=0, le=1)
    maximum_autonomous_validity_drop_vs_scripted: float = Field(default=0.15, ge=0, le=1)
    minimum_autonomous_diversity_task_fraction: float = Field(default=0.50, ge=0, le=1)
    minimum_autonomous_state_entropy_gain: float = Field(default=0.05, ge=0)
    minimum_autonomous_accepted_state_gain: float = Field(default=0.20, ge=0)
    minimum_nontrivial_autonomous_state_rate: float = Field(default=0.20, ge=0, le=1)


class FinanceExplorerRuntimeFactorialContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    run_role: Literal["development_explorer_runtime_factorial_only"] = (
        "development_explorer_runtime_factorial_only"
    )
    base_contract_path: str = Field(min_length=1)
    base_contract_sha256: str = Field(min_length=64, max_length=64)
    base_contract_id: str = Field(min_length=1)
    source_population_report_path: str = Field(min_length=1)
    source_population_report_sha256: str = Field(min_length=64, max_length=64)
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    calibration_task_manifest_hash: str = Field(min_length=1)
    discovery_task_manifest_hash: str = Field(min_length=1)
    model_manifest_hash: str = Field(min_length=1)
    runtime_arms: tuple[AgentPilotArmContract, ...] = Field(min_length=3, max_length=3)
    scripted_tool_policy_version: str = SCRIPTED_TOOL_POLICY_VERSION
    scripted_tool_policy_hash: str = Field(min_length=1)
    calibration_runs_per_task_model_runtime: int = Field(default=1, ge=1, le=1)
    discovery_runs_per_task_model_runtime: int = Field(default=10, ge=10, le=10)
    primary_model_contrast: Literal["flash_vs_pro_within_autonomous"] = (
        "flash_vs_pro_within_autonomous"
    )
    primary_runtime_contrast: Literal["autonomous_vs_scripted_within_model"] = (
        "autonomous_vs_scripted_within_model"
    )
    direct_arm_interpretation: Literal["reference_not_strict_tool_condition"] = (
        "reference_not_strict_tool_condition"
    )
    thresholds: FactorialThresholds
    calibration_outcomes_may_change_thresholds: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    contribution_approximation_authorized: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = EXPLORER_RUNTIME_FACTORIAL_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceExplorerRuntimeFactorialContract:
        arm_by_id = {item.arm: item for item in self.runtime_arms}
        if set(arm_by_id) != set(AgentPilotArm) or len(arm_by_id) != len(self.runtime_arms):
            raise ValueError("factorial Pilot requires Direct, Scripted, and Autonomous arms")
        scripted = arm_by_id[AgentPilotArm.SCRIPTED_TOOL]
        autonomous = arm_by_id[AgentPilotArm.AUTONOMOUS_AGENT]
        if (
            scripted.token_budget != autonomous.token_budget
            or scripted.tool_call_budget != autonomous.tool_call_budget
        ):
            raise ValueError("Scripted and Autonomous factorial arms require identical budgets")
        if scripted.script_policy_hash != self.scripted_tool_policy_hash:
            raise ValueError("factorial Scripted arm uses another script policy")
        if self.scripted_tool_policy_hash != scripted_tool_policy_hash():
            raise ValueError("factorial script policy hash is invalid")
        if self.contract_id != explorer_runtime_factorial_contract_id(self):
            raise ValueError("factorial Pilot contract identity is invalid")
        return self


def prepare_explorer_runtime_factorial_contract(
    *,
    base_contract_path: Path,
    finance_archive_config_path: Path,
    output_path: Path,
    run_id: str,
    thresholds: FactorialThresholds | None = None,
) -> FinanceExplorerRuntimeFactorialContract:
    if output_path.exists():
        raise ValueError("factorial Pilot contract is immutable and already exists")
    base_contract_path = base_contract_path.resolve()
    finance_archive_config_path = finance_archive_config_path.resolve()
    base = FinanceProFlashPilotContract.model_validate_json(
        base_contract_path.read_text(encoding="utf-8")
    )
    if base.solver_version != ITERATIVE_AGENT_SOLVER_VERSION:
        raise ValueError("base paired contract does not freeze the current iterative solver")
    source_report_path = (
        Path(base.source_artifacts_path).resolve().with_name("finance_agent_population_report.json")
    )
    source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
    archive_hash = _sha256(finance_archive_config_path)
    if source_report.get("archive_config_sha256") != archive_hash:
        raise ValueError("factorial Archive config differs from the source population")
    arms = _runtime_arm_contracts(base)
    values = {
        "run_id": run_id,
        "run_role": "development_explorer_runtime_factorial_only",
        "base_contract_path": str(base_contract_path),
        "base_contract_sha256": _sha256(base_contract_path),
        "base_contract_id": base.contract_id,
        "source_population_report_path": str(source_report_path),
        "source_population_report_sha256": _sha256(source_report_path),
        "finance_archive_config_path": str(finance_archive_config_path),
        "finance_archive_config_sha256": archive_hash,
        "calibration_task_manifest_hash": canonical_hash(
            base.calibration_tasks,
            prefix="factorial_calibration_tasks:",
        ),
        "discovery_task_manifest_hash": canonical_hash(
            base.discovery_tasks,
            prefix="factorial_discovery_tasks:",
        ),
        "model_manifest_hash": canonical_hash(
            base.model_contracts,
            prefix="factorial_explorer_models:",
        ),
        "runtime_arms": arms,
        "scripted_tool_policy_version": SCRIPTED_TOOL_POLICY_VERSION,
        "scripted_tool_policy_hash": scripted_tool_policy_hash(),
        "calibration_runs_per_task_model_runtime": 1,
        "discovery_runs_per_task_model_runtime": 10,
        "primary_model_contrast": "flash_vs_pro_within_autonomous",
        "primary_runtime_contrast": "autonomous_vs_scripted_within_model",
        "direct_arm_interpretation": "reference_not_strict_tool_condition",
        "thresholds": thresholds or FactorialThresholds(),
        "calibration_outcomes_may_change_thresholds": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_contribution": 0.0,
        "schema_version": EXPLORER_RUNTIME_FACTORIAL_CONTRACT_VERSION,
    }
    provisional = FinanceExplorerRuntimeFactorialContract.model_construct(
        contract_id="pending",
        **values,
    )
    contract = FinanceExplorerRuntimeFactorialContract(
        contract_id=explorer_runtime_factorial_contract_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def scripted_tool_sequence(family: str) -> tuple[str, ...]:
    try:
        return _SCRIPTED_TOOL_SEQUENCES[family]
    except KeyError as exc:
        raise ValueError(f"unknown Finance scripted-tool family: {family}") from exc


def scripted_tool_policy_hash() -> str:
    if set(_SCRIPTED_TOOL_SEQUENCES) != set(EXPECTED_FAMILIES):
        raise ValueError("scripted tool policy does not cover every frozen family")
    return canonical_hash(
        {
            "version": SCRIPTED_TOOL_POLICY_VERSION,
            "sequences": _SCRIPTED_TOOL_SEQUENCES,
            "oracle_inputs_visible": False,
        },
        prefix="finance_scripted_tool_policy:",
    )


def explorer_runtime_factorial_contract_id(
    value: FinanceExplorerRuntimeFactorialContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_explorer_runtime_factorial_contract:",
    )


def _runtime_arm_contracts(
    base: FinanceProFlashPilotContract,
) -> tuple[AgentPilotArmContract, ...]:
    token_budget = base.maximum_model_tokens_per_rollout
    tool_budget = base.maximum_tool_calls
    return (
        AgentPilotArmContract(
            arm=AgentPilotArm.DIRECT_BARE,
            model_decision_authorities=("complete_response", "answer_generation"),
            host_decision_authorities=("validity_verification",),
            uses_tool_environment=False,
            token_budget=token_budget,
            tool_call_budget=0,
        ),
        AgentPilotArmContract(
            arm=AgentPilotArm.SCRIPTED_TOOL,
            model_decision_authorities=(
                "query_construction",
                "tool_arguments",
                "answer_generation",
            ),
            host_decision_authorities=("tool_selection", "tool_execution", "validity_verification"),
            uses_tool_environment=True,
            script_policy_hash=scripted_tool_policy_hash(),
            token_budget=token_budget,
            tool_call_budget=tool_budget,
        ),
        AgentPilotArmContract(
            arm=AgentPilotArm.AUTONOMOUS_AGENT,
            model_decision_authorities=(
                "tool_selection",
                "query_construction",
                "continue_or_stop",
                "failure_recovery",
                "answer_generation",
            ),
            host_decision_authorities=("tool_execution", "validity_verification"),
            uses_tool_environment=True,
            token_budget=token_budget,
            tool_call_budget=tool_budget,
        ),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
