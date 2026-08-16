from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    _load_records,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_context_sufficiency import (  # noqa: E501
    EXPECTED_ACTION_BY_CONDITION,
    EXPECTED_ROLLOUT_COUNT,
    FinanceStoppingContextSufficiencyContract,
    FinanceStoppingContextSufficiencyMechanismReport,
    FinanceStoppingContextSufficiencyPopulation,
    _artifact_id,
    _sha256,
    _verify_reference,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_context_sufficiency_runner import (  # noqa: E501
    _record_observations,
)

DIAGNOSTIC_VERSION = "finance_stopping_context_sufficiency_diagnostic.v1"
ACTION_TOOLS = frozenset({*EXPECTED_ACTION_BY_CONDITION.values(), "open_document"})


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ContextActionDiagnostic(FrozenModel):
    condition: str = Field(min_length=1)
    expected_action: str = Field(min_length=1)
    rollout_count: int = Field(ge=1)
    first_action_attempt_counts: dict[str, int]
    first_action_success_counts: dict[str, int]
    no_post_prerequisite_action_count: int = Field(ge=0)
    correct_first_action_count: int = Field(ge=0)
    correct_first_action_rate: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_counts(self) -> ContextActionDiagnostic:
        if self.correct_first_action_rate != self.correct_first_action_count / self.rollout_count:
            raise ValueError("Context-action diagnostic rate is inconsistent")
        if (
            sum(self.first_action_attempt_counts.values())
            + (self.no_post_prerequisite_action_count)
            != self.rollout_count
        ):
            raise ValueError("Context-action diagnostic denominator changed")
        return self


class ContextSufficiencyDiagnostic(FrozenModel):
    diagnostic_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    mechanism_report_id: str = Field(min_length=1)
    source_sha256: dict[str, str]
    contextual_rollout_count: int = Field(ge=64, le=64)
    condition_diagnostics: tuple[ContextActionDiagnostic, ...] = Field(min_length=2, max_length=2)
    api_call_count: int = Field(ge=1)
    http_success_count: int = Field(ge=0)
    json_contract_success_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    prompt_cache_hit_tokens: int = Field(ge=0)
    prompt_cache_miss_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    selected_model_counts: dict[str, int]
    mechanism_gate_changed: bool = False
    contribution_authorized: bool = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = DIAGNOSTIC_VERSION

    @model_validator(mode="after")
    def validate_diagnostic(self) -> ContextSufficiencyDiagnostic:
        if self.http_success_count > self.api_call_count:
            raise ValueError("HTTP-success count exceeds the API denominator")
        if self.json_contract_success_count > self.api_call_count:
            raise ValueError("JSON-success count exceeds the API denominator")
        if sum(self.selected_model_counts.values()) != self.api_call_count:
            raise ValueError("Selected-model counts do not cover all API calls")
        if self.diagnostic_id != _artifact_id(
            self,
            "diagnostic_id",
            "finance_stopping_context_sufficiency_diagnostic:",
        ):
            raise ValueError("Context-sufficiency diagnostic identity is invalid")
        return self


def build_context_sufficiency_diagnostic(
    *,
    contract_path: Path,
    population_path: Path,
    records_path: Path,
    mechanism_report_path: Path,
    overall_report_path: Path,
    output_path: Path,
) -> ContextSufficiencyDiagnostic:
    if output_path.exists():
        raise ValueError("Context-sufficiency diagnostic is immutable")
    contract = FinanceStoppingContextSufficiencyContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    population = FinanceStoppingContextSufficiencyPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    mechanism = FinanceStoppingContextSufficiencyMechanismReport.model_validate_json(
        mechanism_report_path.read_text(encoding="utf-8")
    )
    overall = json.loads(overall_report_path.read_text(encoding="utf-8"))
    for reference in (
        contract.source_population,
        population.source_protocol,
    ):
        _verify_reference(reference.path, reference.sha256)
    if not (
        contract.source_population.artifact_id == population.population_id
        and mechanism.contract_id == contract.contract_id
        and overall.get("contract_id") == contract.contract_id
        and overall.get("mechanism_report_id") == mechanism.report_id
        and overall.get("all_v25_47_gates_passing") is False
        and overall.get("production_contribution") == 0.0
    ):
        raise ValueError("Context-sufficiency diagnostic source lineage changed")

    records = _load_records(records_path)
    if len(records) != EXPECTED_ROLLOUT_COUNT:
        raise ValueError("Context-sufficiency diagnostic lacks the full record denominator")
    task_by_id = {item.artifact.artifact_id: item for item in population.tasks}
    records_by_condition: dict[str, list[Any]] = {"period": [], "definition": []}
    for record in records:
        condition = population.task_context_conditions[record.task_artifact_id]
        if condition is not None:
            records_by_condition[condition].append(record)

    condition_rows = tuple(
        _condition_diagnostic(
            condition,
            records_by_condition[condition],
            task_by_id,
        )
        for condition in ("period", "definition")
    )
    observed_correct = {item.condition: item.correct_first_action_count for item in condition_rows}
    if observed_correct != {
        "period": mechanism.period_action_correct_count,
        "definition": mechanism.definition_action_correct_count,
    }:
        raise ValueError("Read-only action diagnostic differs from the frozen mechanism report")

    telemetry = tuple(item for record in records for item in record.telemetry)
    selected_models = Counter(str(item.model_selected) for item in telemetry)
    values = {
        "contract_id": contract.contract_id,
        "population_id": population.population_id,
        "mechanism_report_id": mechanism.report_id,
        "source_sha256": {
            "contract": _sha256(contract_path),
            "population": _sha256(population_path),
            "records": _sha256(records_path),
            "mechanism_report": _sha256(mechanism_report_path),
            "overall_report": _sha256(overall_report_path),
        },
        "contextual_rollout_count": sum(len(items) for items in records_by_condition.values()),
        "condition_diagnostics": condition_rows,
        "api_call_count": len(telemetry),
        "http_success_count": sum(bool(item.http_success) for item in telemetry),
        "json_contract_success_count": sum(bool(item.json_contract_success) for item in telemetry),
        "fallback_count": sum(bool(item.fallback_used) for item in telemetry),
        "prompt_tokens": sum(int(item.prompt_tokens or 0) for item in telemetry),
        "prompt_cache_hit_tokens": sum(
            int(item.prompt_cache_hit_tokens or 0) for item in telemetry
        ),
        "prompt_cache_miss_tokens": sum(
            int(item.prompt_cache_miss_tokens or 0) for item in telemetry
        ),
        "completion_tokens": sum(int(item.completion_tokens or 0) for item in telemetry),
        "total_tokens": sum(int(item.total_tokens or 0) for item in telemetry),
        "estimated_cost": sum(float(item.estimated_cost or 0) for item in telemetry),
        "selected_model_counts": dict(sorted(selected_models.items())),
    }
    provisional = ContextSufficiencyDiagnostic.model_construct(diagnostic_id="pending", **values)
    diagnostic = ContextSufficiencyDiagnostic(
        diagnostic_id=_artifact_id(
            provisional,
            "diagnostic_id",
            "finance_stopping_context_sufficiency_diagnostic:",
        ),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(diagnostic.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return diagnostic


def _condition_diagnostic(
    condition: str,
    records: list[Any],
    task_by_id: dict[str, Any],
) -> ContextActionDiagnostic:
    if len(records) != 32:
        raise ValueError(f"Context condition {condition!r} lacks 32 preregistered rollouts")
    expected = EXPECTED_ACTION_BY_CONDITION[condition]
    attempts: Counter[str] = Counter()
    successes: Counter[str] = Counter()
    missing = 0
    correct = 0
    for record in records:
        action = _first_post_prerequisite_action(record, task_by_id[record.task_artifact_id])
        if action is None:
            missing += 1
            continue
        tool_id, status = action
        attempts[tool_id] += 1
        if status == "succeeded":
            successes[tool_id] += 1
        if tool_id == expected and status == "succeeded":
            correct += 1
    return ContextActionDiagnostic(
        condition=condition,
        expected_action=expected,
        rollout_count=len(records),
        first_action_attempt_counts=dict(sorted(attempts.items())),
        first_action_success_counts=dict(sorted(successes.items())),
        no_post_prerequisite_action_count=missing,
        correct_first_action_count=correct,
        correct_first_action_rate=correct / len(records),
    )


def _first_post_prerequisite_action(record: Any, task: Any) -> tuple[str, str] | None:
    required_ids = {item.evidence_id for item in task.scenario.evidence_roles}
    selected: set[str] = set()
    for observation in _record_observations(record):
        if required_ids <= selected and observation.call.tool_id in ACTION_TOOLS:
            return observation.call.tool_id, observation.status
        if observation.status == "succeeded":
            selected.update(observation.evidence_ids)
    return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build read-only Finance v25.47 diagnostics")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--mechanism-report", type=Path, required=True)
    parser.add_argument("--overall-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    build_context_sufficiency_diagnostic(
        contract_path=args.contract,
        population_path=args.population,
        records_path=args.records,
        mechanism_report_path=args.mechanism_report,
        overall_report_path=args.overall_report,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
