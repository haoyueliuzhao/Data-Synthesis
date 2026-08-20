from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_feasible_role_task_rematerialization import (  # noqa: E501
    FRESHNESS_CHANNELS,
    PATH_STRATEGIES,
    BudgetFeasibleRoleRematerializationReport,
    BudgetFeasibleRoleTaskPackage,
    BudgetQualifiedPathAudit,
    CompactPromptContract,
    RoleDestructivePreflightAudit,
    RoleFreshnessAudit,
    RoleSourceCapacityAudit,
    build_budget_feasible_role_task_rematerialization,
)
from trusted_synthesis.runtime.agent.compact_budget_prompt import (
    require_action_neutral_public_projection,
)
from trusted_synthesis.runtime.agent.prospective_thinking import (
    PROSPECTIVE_THINKING_MODE_POLICY,
    ProspectiveThinkingModelBinding,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821"
SELECTION_SALT = "finance_v26_90_budget_feasible_role_task_rematerialization.v1"


def _rows(path: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(model.model_validate(item) for item in payload)


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(item) for item in value.values()), set())
    if isinstance(value, (list, tuple)):
        return set().union(*(_keys(item) for item in value), set())
    return set()


@pytest.fixture(scope="session")
def formal_build(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any]:
    output = tmp_path_factory.mktemp("v26_90_formal")
    report = build_budget_feasible_role_task_rematerialization(
        run_id=RUN_ID,
        selection_salt=SELECTION_SALT,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )
    return output, report


def test_dual_build_is_byte_identical(
    formal_build: tuple[Path, Any],
    tmp_path: Path,
) -> None:
    formal_dir, formal_report = formal_build
    independent_dir = tmp_path / "independent"
    independent_report = build_budget_feasible_role_task_rematerialization(
        run_id=RUN_ID,
        selection_salt=SELECTION_SALT,
        output_dir=independent_dir,
        package_root=PACKAGE_ROOT,
    )
    formal_files = tuple(sorted(path.name for path in formal_dir.iterdir()))
    independent_files = tuple(sorted(path.name for path in independent_dir.iterdir()))
    assert formal_files == independent_files
    assert all(
        (formal_dir / name).read_bytes() == (independent_dir / name).read_bytes()
        for name in formal_files
    )
    assert formal_report.report_id == independent_report.report_id


def test_report_freezes_static_only_transition(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    report = BudgetFeasibleRoleRematerializationReport.model_validate_json(
        (output / "report.json").read_text(encoding="utf-8")
    )
    assert report.task_count == 24
    assert report.budget_qualified_path_count == 48
    assert report.maximum_path_upper_bound == 115612
    assert report.minimum_path_headroom == 4388
    assert report.maximum_prompt_utf8_bytes == 8438
    assert report.model_api_calls == report.gpu_jobs == 0
    assert not report.empirical_contract_materialized
    assert not report.job_manifest_materialized
    assert not report.independent_budget_calibration_executed
    assert report.next_permitted_stage == "thinking_budget_calibration_preflight_only"
    assert not (output / "execution_contract.json").exists()
    assert not (output / "job_manifest.json").exists()


def test_role_source_capacity_is_balanced_and_preoutcome(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    audit = RoleSourceCapacityAudit.model_validate_json(
        (output / "source_capacity_audit.json").read_text(encoding="utf-8")
    )
    assert len(audit.selected_rows) == 24
    assert audit.reachability_single_node_two_evidence_count == 12
    assert not audit.source_task_outcomes_loaded
    assert not audit.source_task_outcomes_used
    assert set(audit.eligible_task_counts) == {
        "context_conditioned_action",
        "semantic_reconciliation",
        "failure_recovery",
        "state_dependent_stopping",
    }
    assert all(value >= 11 for value in audit.eligible_task_counts.values())


def test_nine_channel_freshness_and_role_isolation(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    audit = RoleFreshnessAudit.model_validate_json(
        (output / "source_freshness_audit.json").read_text(encoding="utf-8")
    )
    assert tuple(item.channel for item in audit.channels) == FRESHNESS_CHANNELS
    assert audit.historical_task_record_count == 156
    assert audit.historical_job_identity_count == 1200
    assert all(item.prior_overlap_count == 0 for item in audit.channels)
    assert all(item.cross_role_overlap_count == 0 for item in audit.channels)
    jobs = next(item for item in audit.channels if item.channel == "job_id")
    assert jobs.prior_count == 1200
    assert jobs.selected_count == 0


def test_every_role_package_binds_required_static_paths(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    packages = _rows(
        output / "budget_feasible_role_task_packages.json",
        BudgetFeasibleRoleTaskPackage,
    )
    counts = Counter(item.role for item in packages)
    assert counts == {"capability": 12, "reachability": 12}
    for package in packages:
        assert package.budget_proved_before_identity_freeze
        assert package.thinking_required_before_client_construction
        assert package.empirical_job_count == 0
        if package.role == "capability":
            assert package.path_strategy_ids == ("structured_direct",)
        else:
            assert package.path_strategy_ids == PATH_STRATEGIES

    mutated = packages[0].model_dump(mode="python")
    mutated["task_package_id"] = "finance_v26_budget_feasible_role_task_package:stale"
    with pytest.raises(ValidationError, match="identity"):
        BudgetFeasibleRoleTaskPackage.model_validate(mutated)


def test_all_request_and_path_bounds_use_frozen_arithmetic(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    rows = _rows(output / "budget_qualified_path_audits.json", BudgetQualifiedPathAudit)
    assert len(rows) == 48
    assert sum(item.role == "capability" for item in rows) == 12
    assert sum(item.role == "reachability" for item in rows) == 36
    assert min(item.maximum_cumulative_path_upper_bound for item in rows) == 57634
    assert max(item.maximum_cumulative_path_upper_bound for item in rows) == 115612
    assert all(item.full_path_budget_qualified for item in rows)
    assert all(item.maximum_prompt_utf8_bytes <= 60000 for item in rows)
    assert all(
        request.prompt_token_upper_bound == request.prompt_utf8_bytes + 256
        and request.request_token_upper_bound == request.prompt_token_upper_bound + 4096
        for row in rows
        for request in row.request_bounds
    )


def test_compact_prompt_contracts_are_action_neutral(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    contracts = _rows(output / "compact_prompt_contracts.json", CompactPromptContract)
    forbidden = {
        "expected_arguments",
        "expected_operator_id",
        "gold_evidence_ids",
        "mechanism_private_state",
        "oracle",
        "source_program_node_id",
        "target_evidence_ids",
    }
    assert len(contracts) == 24
    assert all(not (_keys(item.public_context) & forbidden) for item in contracts)
    assert all(not item.action_binding_fields_exposed for item in contracts)
    with pytest.raises(ValueError, match="private/action-bearing"):
        require_action_neutral_public_projection({"expected_arguments": {}})


def test_thinking_binding_is_exact_and_future_only(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    payload = json.loads((output / "thinking_mode_binding.json").read_text(encoding="utf-8"))
    binding = ProspectiveThinkingModelBinding.model_validate(payload["binding"])
    assert payload["policy"]["policy_id"] == PROSPECTIVE_THINKING_MODE_POLICY.policy_id
    assert binding.model_config_id == payload["model_config_id"]
    assert binding.thinking_type == "enabled"
    assert not payload["client_construction_permitted_in_this_stage"]


def test_destructive_preflight_and_calibration_math(
    formal_build: tuple[Path, Any],
) -> None:
    output, _ = formal_build
    audit = RoleDestructivePreflightAudit.model_validate_json(
        (output / "destructive_preflight_audit.json").read_text(encoding="utf-8")
    )
    assert audit.rejected_mutation_count == 11
    assert audit.thinking_mutation_count == 4
    assert audit.prompt_projection_mutation_count == 4
    assert audit.role_package_mutation_count == 3
    assert all(item.rejected for item in audit.mutation_results)
    zero_no_call_upper = 1 - math.pow(0.05, 1 / 32)
    lower = 0.0
    upper = 1.0
    for _ in range(100):
        candidate = (lower + upper) / 2
        probability_at_most_one = math.pow(1 - candidate, 32) + (
            32 * candidate * math.pow(1 - candidate, 31)
        )
        if probability_at_most_one > 0.05:
            lower = candidate
        else:
            upper = candidate
    one_no_call_upper = (lower + upper) / 2
    assert zero_no_call_upper <= 0.10
    assert one_no_call_upper > 0.10
