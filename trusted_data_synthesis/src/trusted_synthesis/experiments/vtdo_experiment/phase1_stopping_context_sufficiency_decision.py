from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_context_sufficiency import (  # noqa: E501
    FinanceStoppingContextSufficiencyMechanismReport,
    FinanceStoppingContextSufficiencyPopulation,
    FinanceStoppingContextSufficiencyReport,
    _artifact_id,
    _sha256,
)

DECISION_VERSION = "finance_stopping_context_sufficiency_scientific_decision.v1"


class ContextSufficiencyScientificDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    report_id: str = Field(min_length=1)
    mechanism_report_id: str = Field(min_length=1)
    source_sha256: dict[str, str]
    static_construct_validity_passed: Literal[True] = True
    runtime_measurement_passed: Literal[True] = True
    contextual_mechanism_fidelity_passed: Literal[False] = False
    interpretation: Literal[
        "flash_contextual_tool_selection_limitation_under_sufficient_public_context"
    ] = "flash_contextual_tool_selection_limitation_under_sufficient_public_context"
    automated_report_transition: Literal["contextual_shape_redesign_only"] = (
        "contextual_shape_redesign_only"
    )
    governance_transition: Literal["contextual_tool_selection_limitation_recorded"] = (
        "contextual_tool_selection_limitation_recorded"
    )
    transition_tightening_reason: Literal[
        "preoutcome_stop_rule_after_static_context_sufficiency"
    ] = "preoutcome_stop_rule_after_static_context_sufficiency"
    same_grammar_prompt_help_authorized: Literal[False] = False
    threshold_relaxation_authorized: Literal[False] = False
    posthoc_task_deletion_authorized: Literal[False] = False
    additional_flash_rollouts_authorized: Literal[False] = False
    pro_api_calls_authorized: Literal[False] = False
    beneficiary_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    schema_version: str = DECISION_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> ContextSufficiencyScientificDecision:
        if self.decision_id != _artifact_id(
            self,
            "decision_id",
            "finance_stopping_context_sufficiency_scientific_decision:",
        ):
            raise ValueError("Context-sufficiency scientific decision identity is invalid")
        return self


def build_scientific_decision(
    *,
    population_path: Path,
    report_path: Path,
    mechanism_report_path: Path,
    output_path: Path,
) -> ContextSufficiencyScientificDecision:
    if output_path.exists():
        raise ValueError("Context-sufficiency scientific decision is immutable")
    population = FinanceStoppingContextSufficiencyPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    report = FinanceStoppingContextSufficiencyReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    mechanism = FinanceStoppingContextSufficiencyMechanismReport.model_validate_json(
        mechanism_report_path.read_text(encoding="utf-8")
    )
    if not (
        population.static_audit.ready
        and population.static_audit.pair_public_context_sufficiency_rate == 1.0
        and population.static_audit.pair_unique_applicable_action_rate == 1.0
        and population.static_audit.action_order_permutation_invariance_rate == 1.0
        and population.static_audit.action_label_rewrite_invariance_rate == 1.0
        and population.static_audit.context_removal_indeterminate_rate == 1.0
        and population.static_audit.context_swap_action_flip_rate == 1.0
        and report.shape_analysis_authorized
        and report.raw_instrument_status == "passed"
        and report.contextual_mechanism_fidelity_passing is False
        and report.next_permitted_stage == "contextual_shape_redesign_only"
        and mechanism.report_id == report.mechanism_report_id
        and mechanism.passed is False
        and report.production_contribution == 0.0
    ):
        raise ValueError("v25.47 does not satisfy the conservative capability-limit decision")
    values = {
        "population_id": population.population_id,
        "report_id": report.report_id,
        "mechanism_report_id": mechanism.report_id,
        "source_sha256": {
            "population": _sha256(population_path),
            "report": _sha256(report_path),
            "mechanism_report": _sha256(mechanism_report_path),
        },
    }
    provisional = ContextSufficiencyScientificDecision.model_construct(
        decision_id="pending", **values
    )
    decision = ContextSufficiencyScientificDecision(
        decision_id=_artifact_id(
            provisional,
            "decision_id",
            "finance_stopping_context_sufficiency_scientific_decision:",
        ),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(decision.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return decision


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze the conservative Finance v25.47 scientific decision"
    )
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mechanism-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    build_scientific_decision(
        population_path=args.population,
        report_path=args.report,
        mechanism_report_path=args.mechanism_report,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
