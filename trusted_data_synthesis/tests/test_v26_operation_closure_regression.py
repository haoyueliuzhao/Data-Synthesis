from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_operation_closure_regression as regression,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_operation_closure_regression import (
    EXPECTED_ROLLOUT_COUNT,
    EXPECTED_TASK_COUNT,
    IMPLEMENTATION_SOURCE_PATHS,
    OperationClosureRegressionContract,
    OperationClosureRegressionJobManifest,
    build_operation_closure_regression_contract,
    build_operation_closure_regression_manifest,
    run_operation_closure_regression,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
SOURCE = ARTIFACT_ROOT / "finance_v26_60_public_operation_rematerialization_v2_20260818"
MODEL_CONFIG = PACKAGE_ROOT / "config" / "deepseek_v4_flash_agent_v23_paired_pilot.json"
RUN_ID = "finance_v26_61_operation_closure_regression_v2_20260818"
SELECTION_SALT = "finance-v26.61-operation-closure-regression-20260818"


@pytest.fixture(scope="module")
def frozen_design() -> tuple[
    OperationClosureRegressionContract,
    OperationClosureRegressionJobManifest,
]:
    payload = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    model_config = AgentModelConfig.model_validate(payload["model"])
    contract, records = build_operation_closure_regression_contract(
        run_id=RUN_ID,
        source_dir=SOURCE,
        model_config=model_config,
        package_root=PACKAGE_ROOT,
        selection_salt=SELECTION_SALT,
    )
    return contract, build_operation_closure_regression_manifest(contract, records)


def test_regression_freezes_eight_capability_tasks_and_four_replicas(
    frozen_design: tuple[
        OperationClosureRegressionContract,
        OperationClosureRegressionJobManifest,
    ],
) -> None:
    contract, manifest = frozen_design

    assert contract.task_count == EXPECTED_TASK_COUNT == 8
    assert contract.rollouts_per_task == 4
    assert contract.expected_rollout_count == EXPECTED_ROLLOUT_COUNT == 32
    assert contract.mechanism_task_counts == {
        "context_conditioned_action": 2,
        "semantic_reconciliation": 2,
        "failure_recovery": 2,
        "state_dependent_stopping": 2,
    }
    assert len(manifest.jobs) == 32
    assert Counter(item.task_package_id for item in manifest.jobs) == Counter(
        {item: 4 for item in contract.selected_task_package_ids}
    )
    assert all(item.intended_use == "capability_measurement" for item in manifest.jobs)
    assert all(item.sampling_mode == "capability_unconditional" for item in manifest.jobs)
    assert all(item.requested_static_path_id is None for item in manifest.jobs)
    assert all(item.requested_path_strategy is None for item in manifest.jobs)
    assert all(item.requested_quotient_state_id is None for item in manifest.jobs)
    assert all(item.public_condition_id is None for item in manifest.jobs)


def test_regression_contract_keeps_scientific_claims_closed(
    frozen_design: tuple[
        OperationClosureRegressionContract,
        OperationClosureRegressionJobManifest,
    ],
) -> None:
    contract, _ = frozen_design

    assert contract.measurement_instrument_only
    assert contract.unconditional_sampling_only
    assert contract.validity_not_an_instrument_gate
    assert contract.invalid_model_outcomes_retained
    assert contract.task_selection_from_model_outcomes_forbidden
    assert contract.model_comparison_forbidden
    assert contract.state_mapping_forbidden
    assert contract.compiler_witnesses_excluded
    assert not contract.fresh_confirmation_authorized
    assert not contract.no_c_vtdo_authorized
    assert not contract.student_training_authorized
    assert not contract.exact_target_authorized
    assert not contract.gp_c_authorized
    assert contract.production_contribution == 0
    assert contract.fallback_models == ()
    assert contract.require_requested_model
    assert contract.maximum_total_estimated_cost_usd == 2.0


def test_regression_replays_every_source_and_implementation_byte(
    frozen_design: tuple[
        OperationClosureRegressionContract,
        OperationClosureRegressionJobManifest,
    ],
) -> None:
    contract, _ = frozen_design

    assert len(contract.source_artifact_files) == 12
    for item in contract.source_artifact_files:
        assert hashlib.sha256((SOURCE / item.relative_path).read_bytes()).hexdigest() == item.sha256
    assert tuple(item.relative_path for item in contract.implementation_source_files) == tuple(
        sorted(IMPLEMENTATION_SOURCE_PATHS)
    )
    for item in contract.implementation_source_files:
        assert (
            hashlib.sha256((PACKAGE_ROOT / item.relative_path).read_bytes()).hexdigest()
            == item.sha256
        )


def test_regression_selection_and_job_manifest_are_deterministic(
    frozen_design: tuple[
        OperationClosureRegressionContract,
        OperationClosureRegressionJobManifest,
    ],
) -> None:
    contract, manifest = frozen_design
    payload = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    second_contract, second_records = build_operation_closure_regression_contract(
        run_id=RUN_ID,
        source_dir=SOURCE,
        model_config=AgentModelConfig.model_validate(payload["model"]),
        package_root=PACKAGE_ROOT,
        selection_salt=SELECTION_SALT,
    )
    second_manifest = build_operation_closure_regression_manifest(second_contract, second_records)

    assert second_contract.model_dump(mode="json") == contract.model_dump(mode="json")
    assert second_manifest.model_dump(mode="json") == manifest.model_dump(mode="json")


def test_audit_only_preflight_constructs_no_model_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_client(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("audit-only preflight constructed a model client")

    monkeypatch.setattr(regression, "OpenAICompatibleJsonClient", forbidden_client)
    output = tmp_path / "preflight"
    report = run_operation_closure_regression(
        run_id=RUN_ID,
        source_dir=SOURCE,
        model_config_path=MODEL_CONFIG,
        output_dir=output,
        package_root=PACKAGE_ROOT,
        selection_salt=SELECTION_SALT,
        workers=4,
        audit_only=True,
    )

    assert report.status == "preflight"
    assert report.completed_rollout_count == 0
    assert report.provider_call_count == report.provider_total_tokens == 0
    assert report.estimated_cost_usd == "0"
    assert report.raw_integrity_audit.status == "partial"
    assert not report.instrument_ready
    assert report.resource_budget_passed
    assert report.next_permitted_stage == "model_execution_only"
    assert not report.capability_development_authorized
    assert not report.state_reachability_pilot_authorized
    assert set(item.name for item in output.iterdir()) == {
        "execution_contract.json",
        "job_manifest.json",
        "report.json",
    }


def test_contract_and_manifest_mutations_fail_closed(
    frozen_design: tuple[
        OperationClosureRegressionContract,
        OperationClosureRegressionJobManifest,
    ],
) -> None:
    contract, manifest = frozen_design

    contract_payload = contract.model_dump(mode="python")
    contract_payload["validity_not_an_instrument_gate"] = False
    with pytest.raises(ValidationError):
        OperationClosureRegressionContract.model_validate(contract_payload)

    budget_payload = contract.model_dump(mode="python")
    budget_payload["maximum_total_estimated_cost_usd"] = 2.01
    with pytest.raises(ValidationError):
        OperationClosureRegressionContract.model_validate(budget_payload)

    manifest_payload = manifest.model_dump(mode="python")
    jobs = list(manifest_payload["jobs"])
    jobs[1] = jobs[0]
    manifest_payload["jobs"] = tuple(jobs)
    with pytest.raises(ValidationError, match="identities are not canonical"):
        OperationClosureRegressionJobManifest.model_validate(manifest_payload)
