from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.trajectory.executable_task import (
    StaticModelAuthorityPathCatalog,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_pilot import (
    EmpiricalPilotJob,
    EmpiricalSupportPilotContract,
    PublicReachabilityCondition,
    build_empirical_pilot_job_manifest,
    build_empirical_support_pilot_contract,
    evaluate_mechanism_estimand,
    load_v26_56_inputs,
    make_public_reachability_condition,
    match_empirical_program,
    replay_empirical_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_empirical_support_runner import (
    run_empirical_support_pilot,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig
from trusted_synthesis.runtime.tools import AgentToolObservation

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = (
    PACKAGE_ROOT
    / "artifacts"
    / "vtdo_experiment"
    / "finance_v26_56_executable_task_rematerialization_20260818"
)
MODEL_CONFIG = PACKAGE_ROOT / "config" / "deepseek_v4_flash_agent_v23_paired_pilot.json"


@pytest.fixture(scope="module")
def source_bundle() -> tuple:
    return load_v26_56_inputs(SOURCE_DIR)


@pytest.fixture(scope="module")
def frozen_contract(source_bundle: tuple) -> EmpiricalSupportPilotContract:
    del source_bundle
    payload = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    model = AgentModelConfig.model_validate(payload["model"])
    return build_empirical_support_pilot_contract(
        run_id="finance_v26_57_test",
        source_dir=SOURCE_DIR,
        model_config=model,
        package_root=PACKAGE_ROOT,
    )


def test_contract_separates_capability_and_reachability_roles(
    frozen_contract: EmpiricalSupportPilotContract,
    source_bundle: tuple,
) -> None:
    _, records, _, catalogs, _ = source_bundle
    manifest = build_empirical_pilot_job_manifest(frozen_contract, records, catalogs)

    assert len(frozen_contract.source_capability_task_ids) == 12
    assert len(frozen_contract.source_vtdo_candidate_task_ids) == 12
    assert not (
        set(frozen_contract.source_capability_task_ids)
        & set(frozen_contract.source_vtdo_candidate_task_ids)
    )
    assert len(frozen_contract.source_static_state_ids) == 36
    assert len(manifest.jobs) == 456
    assert Counter(item.sampling_mode for item in manifest.jobs) == Counter(
        {
            "capability_unconditional": 96,
            "reachability_unconditional": 144,
            "reachability_conditioned": 216,
        }
    )
    assert len({item.job_id for item in manifest.jobs}) == 456
    assert all(
        item.requested_quotient_state_id is None
        for item in manifest.jobs
        if item.sampling_mode != "reachability_conditioned"
    )


def test_public_conditions_expose_behavior_not_state_or_path_identity() -> None:
    conditions = tuple(
        make_public_reachability_condition(strategy)
        for strategy in (
            "structured_direct",
            "search_then_structured",
            "search_then_open",
        )
    )
    assert len({item.condition_id for item in conditions}) == 3
    for item in conditions:
        serialized = json.dumps(item.public_payload, sort_keys=True).casefold()
        assert "state_id" not in serialized
        assert "path_id" not in serialized
        assert "compiler_witness" not in serialized
        assert "gold_evidence" not in serialized
        assert "action_sequence" not in serialized
        assert "tool_sequence" not in serialized
        assert "evidence:finance:" not in serialized
        assert not item.exposes_target_state_id
        assert not item.exposes_complete_action_sequence

    corrupted = conditions[0].model_dump(mode="python")
    corrupted["public_payload"] = {
        **corrupted["public_payload"],
        "target_state_id": "state:forbidden",
    }
    with pytest.raises(ValidationError, match="frozen strategy|forbidden identity"):
        PublicReachabilityCondition.model_validate(corrupted)


def test_job_contract_rejects_role_and_condition_leakage(
    frozen_contract: EmpiricalSupportPilotContract,
    source_bundle: tuple,
) -> None:
    _, records, _, catalogs, _ = source_bundle
    manifest = build_empirical_pilot_job_manifest(frozen_contract, records, catalogs)
    capability = next(
        item for item in manifest.jobs if item.sampling_mode == "capability_unconditional"
    )
    corrupted = capability.model_dump(mode="python")
    corrupted["requested_static_path_id"] = "path:foreign"
    corrupted["requested_path_strategy"] = "structured_direct"
    corrupted["requested_quotient_state_id"] = "state:foreign"
    corrupted["public_condition_id"] = "condition:foreign"
    with pytest.raises(ValidationError, match="unexpectedly carries a target state"):
        EmpiricalPilotJob.model_validate(corrupted)


def test_compiler_witnesses_replay_but_never_enter_empirical_counts(
    source_bundle: tuple,
) -> None:
    _, records, environments, catalogs, _ = source_bundle
    records_by_task = {item.task_package.package_id: item for item in records}
    environments_by_id = {item.manifest_id: item for item in environments}
    observations = tuple(
        AgentToolObservation.model_validate(item)
        for item in json.loads(
            (SOURCE_DIR / "public_witness_observations.json").read_text(encoding="utf-8")
        )
    )
    observations_by_id = {item.observation_id: item for item in observations}
    witnesses = json.loads(
        (SOURCE_DIR / "public_executable_witnesses.json").read_text(encoding="utf-8")
    )
    strategy_counts: Counter[str] = Counter()
    for witness in witnesses:
        record = records_by_task[witness["task_package_id"]]
        environment = environments_by_id[record.environment_manifest_id]
        witness_observations = tuple(
            observations_by_id[item["observation_id"]] for item in witness["steps"]
        )
        replayed, selected, failures = replay_empirical_observations(
            record, environment, witness_observations
        )
        complete, nodes, _, lineage = match_empirical_program(record, witness_observations)
        mechanism = evaluate_mechanism_estimand(
            record,
            witness_observations,
            stopped_by_model=True,
        )
        assert replayed, failures
        assert set(record.task_package.evidence_support_lattice.necessary_evidence_ids) <= set(
            selected
        )
        assert complete
        assert len(nodes) == len(record.task_package.task.oracle.task_program.nodes)
        assert set(record.task_package.evidence_support_lattice.necessary_evidence_ids) <= set(
            lineage
        )
        assert mechanism.success
        strategy_counts[witness["path_strategy_id"]] += 1

    assert len(witnesses) == 48
    assert strategy_counts == Counter(
        {
            "structured_direct": 24,
            "search_then_structured": 12,
            "search_then_open": 12,
        }
    )
    assert all(
        not path.model_generated and path.materialization_origin == "compiler"
        for catalog in catalogs
        for path in catalog.paths
    )


def test_runtime_replay_fails_closed_on_environment_identity_mutation(
    source_bundle: tuple,
) -> None:
    _, records, environments, _, _ = source_bundle
    record = records[0]
    environment = next(
        item for item in environments if item.manifest_id == record.environment_manifest_id
    )
    rows = tuple(
        AgentToolObservation.model_validate(item)
        for item in json.loads(
            (SOURCE_DIR / "public_witness_observations.json").read_text(encoding="utf-8")
        )
        if item["environment_manifest_id"] == environment.manifest_id
    )
    mutated = (rows[0].model_copy(update={"environment_manifest_id": "foreign"}), *rows[1:])
    replayed, _, failures = replay_empirical_observations(record, environment, mutated)
    assert not replayed
    assert any("environment_identity" in item for item in failures)


def test_audit_only_preflight_is_credential_free_and_deterministic(
    tmp_path: Path,
) -> None:
    outputs = (tmp_path / "first", tmp_path / "second")
    reports = []
    for output in outputs:
        reports.append(
            run_empirical_support_pilot(
                run_id="finance_v26_57_preflight_test",
                source_dir=SOURCE_DIR,
                model_config_path=MODEL_CONFIG,
                output_dir=output,
                package_root=PACKAGE_ROOT,
                workers=1,
                audit_only=True,
            )
        )
    assert reports[0] == reports[1]
    assert reports[0].status == "preflight"
    assert reports[0].completed_rollout_count == 0
    assert reports[0].provider_call_count == 0
    assert reports[0].next_permitted_stage == "model_discovery_and_parallel_execution"
    for name in ("execution_contract.json", "job_manifest.json", "report.json"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()


def test_contract_rejects_incomplete_implementation_manifest(
    frozen_contract: EmpiricalSupportPilotContract,
) -> None:
    payload = frozen_contract.model_dump(mode="python")
    payload["implementation_source_files"] = payload["implementation_source_files"][:-1]
    with pytest.raises(ValidationError, match="implementation source manifest is incomplete"):
        EmpiricalSupportPilotContract.model_validate(payload)


def test_vtdo_catalogs_remain_static_inputs_not_empirical_outputs(
    source_bundle: tuple,
) -> None:
    _, _, _, catalogs, _ = source_bundle
    typed = tuple(StaticModelAuthorityPathCatalog.model_validate(item) for item in catalogs)
    assert len([item for item in typed if item.status == "passed"]) == 12
    assert all(not item.empirical_reachability_evaluated for item in typed)
