from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceMultiStateConfig,
    build_finance_task_state_artifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    compile_finance_agent_case,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    EXPECTED_FAMILIES,
    ExplorerArm,
    ExplorerModelContract,
    _ArtifactIndexRow,
    _paired_runtime_context,
    _paired_sampling_contract_hash,
    _select_populations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_runner import (
    PRO_FLASH_ROLLOUT_RECORD_VERSION,
    FinanceProFlashRolloutRecord,
    PilotStage,
    _load_checkpoint,
    finance_pro_flash_rollout_record_id,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig


def _model(arm: ExplorerArm) -> ExplorerModelContract:
    model = f"deepseek-v4-{arm.value}"
    config = AgentModelConfig(
        provider="deepseek",
        endpoint="https://api.deepseek.com/v1/chat/completions",
        models_endpoint="https://api.deepseek.com/models",
        model=model,
        api_key_env="DEEPSEEK_API_KEY",
        timeout_seconds=180,
        max_output_tokens=2048,
        temperature=0.6,
        maximum_model_attempts=1,
        contract_repair_attempts=1,
        auto_discover_models=True,
        require_requested_model=True,
        request_body_overrides={"thinking": {"type": "disabled"}, "top_p": 0.9},
        interaction_protocol="host_instrumented",
    )
    return ExplorerModelContract(
        arm=arm,
        requested_model=model,
        config_sha256="a" * 64,
        public_manifest_hash=config.public_manifest_hash,
        config=config,
    )


def test_task_selection_is_balanced_disjoint_and_evidence_fresh() -> None:
    rows = tuple(
        _ArtifactIndexRow(
            task_id=f"{family}:{index}",
            family=family,
            artifact_id=f"artifact:{family}:{index}",
            source_context_id=f"context:{family}:{index}",
            evidence_version_ids=frozenset({f"evidence:{family}:{index}"}),
        )
        for family in EXPECTED_FAMILIES
        for index in range(8)
    )
    excluded_task = f"{EXPECTED_FAMILIES[0]}:0"
    excluded_evidence = f"evidence:{EXPECTED_FAMILIES[1]}:0"
    discovery, calibration = _select_populations(
        rows,
        excluded_task_ids={excluded_task},
        excluded_evidence_versions={excluded_evidence},
        sampling_salt="paired-selection-test",
    )

    assert len(discovery) == 30
    assert len(calibration) == 6
    assert {item.task_id for item in discovery}.isdisjoint(item.task_id for item in calibration)
    assert excluded_task not in {item.task_id for item in (*discovery, *calibration)}
    assert all(
        excluded_evidence not in item.evidence_version_ids for item in (*discovery, *calibration)
    )


def test_model_pair_rejects_sampling_contract_drift() -> None:
    pro = _model(ExplorerArm.PRO)
    flash = _model(ExplorerArm.FLASH)
    assert _paired_sampling_contract_hash((pro, flash))

    drifted_config = flash.config.model_copy(update={"temperature": 0.7})
    drifted_flash = flash.model_copy(
        update={
            "config": drifted_config,
            "public_manifest_hash": drifted_config.public_manifest_hash,
        }
    )
    with pytest.raises(ValueError, match="differ outside"):
        _paired_sampling_contract_hash((pro, drifted_flash))


def test_rebound_context_hides_plan_and_freezes_real_finance_tools(tmp_path: Path) -> None:
    case = compile_finance_agent_case(build_finance_counterfactual_case(1))
    artifact = build_finance_task_state_artifact(
        case,
        FinanceMultiStateConfig(
            finance_archive_config_path=tmp_path / "unused.json",
            task_count=1,
        ),
    )

    context, manifest = _paired_runtime_context(artifact)

    assert context.task.public.program_skeleton is None
    assert set(context.task.public.allowed_tools) == set(manifest.tools_by_id)
    assert manifest.corpus_id == context.public_corpus.corpus_id
    assert manifest.corpus_hash == context.public_corpus.corpus_hash
    assert manifest.network_policy == "forbidden"
    assert context.context_id != artifact.omega.context_id
    assert context.task.oracle == artifact.omega.task.oracle


def test_checkpoint_rejects_another_run_identity(tmp_path: Path) -> None:
    values = {
        "run_identity": "run:one",
        "contract_id": "contract:test",
        "stage": PilotStage.CALIBRATION,
        "arm": ExplorerArm.PRO,
        "task_id": "task:test",
        "task_family": EXPECTED_FAMILIES[0],
        "replicate": 0,
        "attempt_id": "attempt:test",
        "requested_model": "deepseek-v4-pro",
        "model_config_hash": "model-config:test",
        "status": "failed",
        "solve_result": None,
        "verification_report": None,
        "state_assignment": None,
        "failure_telemetry": (),
        "error_type": "SyntheticFailure",
        "error_message": "expected test failure",
        "schema_version": PRO_FLASH_ROLLOUT_RECORD_VERSION,
    }
    provisional = FinanceProFlashRolloutRecord.model_construct(record_id="pending", **values)
    record = FinanceProFlashRolloutRecord(
        record_id=finance_pro_flash_rollout_record_id(provisional),
        **values,
    )
    path = tmp_path / "checkpoint.jsonl"
    path.write_text(json.dumps(record.model_dump(mode="json")) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="another run"):
        _load_checkpoint(
            path,
            run_identity="run:two",
            task_ids={"task:test"},
            replicas=1,
        )
