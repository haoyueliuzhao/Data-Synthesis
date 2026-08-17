from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.synthesis.schema import CompiledProofCarryingArtifacts
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_heterogeneous_mainline import (
    FINANCE_V26_MAINLINE_VERSION,
    CapabilityHeterogeneousMainlineProtocol,
    ContributionRecoveryContract,
    ImmutableArtifactReference,
    JointCompilationAdmissionContract,
    MainlinePreflightReport,
    MainlineStateMaterializationContract,
    MainlineSupportContract,
    StudentEvaluationContract,
    _no_c_contract,
    _population_contract,
    capability_heterogeneous_mainline_protocol_id,
    mainline_implementation_paths,
    mainline_preflight_report_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_bridge import (
    default_compiler_assisted_bridge_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_compiler_assisted_state_support import (
    make_state_support_discovery_plan,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    FAMILY_TARGET_CAPABILITY,
    MECHANISM_FAMILY_QUOTAS,
    make_v26_fresh_task_population,
    make_v26_fresh_task_root,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_stage_router import (
    V26_STAGE_ROUTER_VERSION,
    V26StageLedger,
    _bridge_support_freeze_embeds_cells,
    _model_schema_version,
    advance_v26_stage,
    initialize_v26_stage_ledger,
    make_v26_stage_artifact_reference,
    v26_stage_ledger_id,
)


def _write_population(
    path: Path,
    *,
    phase: Literal["development", "fresh_confirmation"] = "development",
    source_population_id: str = "source:development",
    task_prefix: str = "task",
) -> None:
    roots = []
    ordinal = 0
    for mechanism, families in MECHANISM_FAMILY_QUOTAS.items():
        for family, count in families.items():
            for _ in range(count):
                task_id = f"{task_prefix}:{ordinal:02d}"
                roots.append(
                    make_v26_fresh_task_root(
                        task_id=task_id,
                        mechanism_id=mechanism,
                        target_capability_id=FAMILY_TARGET_CAPABILITY[family],
                        task_family=family,
                        difficulty_tier=DifficultyTier.FRONTIER,
                        task_package_hash=f"task-hash:{ordinal}",
                        public_spec_hash=f"public-hash:{ordinal}",
                        oracle_contract_hash=f"oracle-hash:{ordinal}",
                        evidence_bundle_hash=f"bundle-hash:{ordinal}",
                        public_corpus_hash=f"corpus-hash:{ordinal}",
                        proof_graph_hash=f"graph-hash:{ordinal}",
                        allowed_tools=("evidence_lookup",),
                        source_task_artifact_id=f"source-task:{ordinal}",
                        source_task_schema_version="capability-task.test.v1",
                        source_task_content_hash=f"{ordinal:064x}",
                    )
                )
                ordinal += 1
    population = make_v26_fresh_task_population(
        protocol_id=_protocol().protocol_id,
        phase=phase,
        source_population_id=source_population_id,
        source_population_run_id=f"finance_v26_{source_population_id}",
        source_population_schema_version="capability-population.test.v1",
        source_population_path=f"/frozen/{source_population_id}.json",
        source_population_sha256="a" * 64,
        source_population_content_hash="b" * 64,
        selection_salt=f"salt:{phase}",
        tasks=roots,
    )
    path.write_text(population.model_dump_json(), encoding="utf-8")


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _protocol() -> CapabilityHeterogeneousMainlineProtocol:
    bridge = default_compiler_assisted_bridge_contract()
    values = {
        "run_id": "finance_v26_stage_router_test",
        "prior_evidence": (
            ImmutableArtifactReference(
                role="historical_measurement_hypothesis_only",
                artifact_id="decision:v25.47",
                schema_version="decision.v1",
                path="/frozen/v25.47.json",
                sha256="a" * 64,
            ),
        ),
        "population": _population_contract(),
        "joint_compilation": JointCompilationAdmissionContract(),
        "capability_bridge": bridge,
        "state_support_discovery": make_state_support_discovery_plan(bridge),
        "materialization": MainlineStateMaterializationContract(),
        "support": MainlineSupportContract(),
        "no_c": _no_c_contract(),
        "contribution": ContributionRecoveryContract(),
        "student_evaluation": StudentEvaluationContract(),
        "explorer_config_sha256": "b" * 64,
        "student_config_sha256": "c" * 64,
        "archive_config_sha256": "d" * 64,
        "schema_version": FINANCE_V26_MAINLINE_VERSION,
    }
    provisional = CapabilityHeterogeneousMainlineProtocol.model_construct(
        protocol_id="pending",
        **values,
    )
    return CapabilityHeterogeneousMainlineProtocol(
        protocol_id=capability_heterogeneous_mainline_protocol_id(provisional),
        **values,
    )


def _preflight(protocol: CapabilityHeterogeneousMainlineProtocol) -> MainlinePreflightReport:
    values = {
        "protocol_id": protocol.protocol_id,
        "checks": {"typed_stage_router_ready": True},
        "source_sha256": {
            "prior_decision": protocol.prior_evidence[0].sha256,
            "archive_config": protocol.archive_config_sha256,
            "explorer_config": protocol.explorer_config_sha256,
            "student_config": protocol.student_config_sha256,
        },
        "code_sha256": {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in sorted(mainline_implementation_paths().items())
        },
        "planned_task_count_by_split": {"synthesis_training": 100},
        "planned_explorer_rollout_count": 800,
        "status": "passed",
        "blockers": (),
        "next_permitted_stage": "v26_1_joint_compilation_admission",
    }
    provisional = MainlinePreflightReport.model_construct(report_id="pending", **values)
    return MainlinePreflightReport(
        report_id=mainline_preflight_report_id(provisional),
        **values,
    )


def _empty_ledger(tmp_path: Path) -> V26StageLedger:
    protocol = _protocol()
    preflight = _preflight(protocol)
    protocol_path = tmp_path / "protocol.json"
    preflight_path = tmp_path / "preflight.json"
    protocol_path.write_text(protocol.model_dump_json(), encoding="utf-8")
    preflight_path.write_text(preflight.model_dump_json(), encoding="utf-8")
    return initialize_v26_stage_ledger(
        run_id="v26_stage_router_test",
        protocol_path=protocol_path,
        preflight_path=preflight_path,
    )


def test_v26_router_uses_joint_schema_for_compiled_artifacts() -> None:
    compiled = CompiledProofCarryingArtifacts.model_construct(
        joint_compilation=SimpleNamespace(schema_version="joint-compilation.test.v1")
    )

    assert _model_schema_version(compiled) == "joint-compilation.test.v1"


def test_bridge_support_freeze_cell_binding_is_identity_based_not_order_based() -> None:
    first = SimpleNamespace(observation_id="bridge-cell:1")
    second = SimpleNamespace(observation_id="bridge-cell:2")
    freeze = SimpleNamespace(observations=(second, first))

    assert _bridge_support_freeze_embeds_cells(  # type: ignore[arg-type]
        freeze,
        (first, second),
    )
    assert not _bridge_support_freeze_embeds_cells(  # type: ignore[arg-type]
        freeze,
        (first, SimpleNamespace(observation_id="bridge-cell:3")),
    )


def test_v26_router_rejects_legacy_untyped_population(tmp_path: Path) -> None:
    population_path = tmp_path / "legacy_population.json"
    population_path.write_text(
        json.dumps(
            {
                "schema_version": "fresh_task_population.v1",
                "task_count": 24,
                "tasks": [{"task_id": f"legacy:{index}"} for index in range(24)],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        make_v26_stage_artifact_reference("fresh_task_population", population_path)


def test_v26_population_rejects_historical_task_promotion(tmp_path: Path) -> None:
    population_path = tmp_path / "population.json"
    _write_population(population_path)
    payload = json.loads(population_path.read_text(encoding="utf-8"))
    payload["source_population_run_id"] = "finance_v25_historical_population"

    with pytest.raises(ValidationError, match="cannot be promoted"):
        make_v26_stage_artifact_reference(
            "fresh_task_population",
            _write_json(population_path, payload),
        )


def test_v26_router_advances_only_the_next_stage(tmp_path: Path) -> None:
    population_path = tmp_path / "population.json"
    _write_population(population_path)
    ledger = _empty_ledger(tmp_path)
    assert ledger.schema_version == V26_STAGE_ROUTER_VERSION
    reference = make_v26_stage_artifact_reference(
        "fresh_task_population",
        population_path,
    )

    advanced = advance_v26_stage(
        ledger,
        stage="fresh_task_population",
        artifacts=(reference,),
    )

    assert advanced.completed_stages == ("fresh_task_population",)
    assert advanced.next_stage == "joint_compilation"
    with pytest.raises(ValueError, match="expected joint_compilation"):
        advance_v26_stage(
            advanced,
            stage="joint_audit",
            artifacts=(reference,),
        )


def test_v26_router_replays_file_content_before_transition(tmp_path: Path) -> None:
    population_path = tmp_path / "population.json"
    _write_population(population_path)
    ledger = _empty_ledger(tmp_path)
    reference = make_v26_stage_artifact_reference(
        "fresh_task_population",
        population_path,
    )
    population_path.write_text(
        population_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="content hash replay failed"):
        advance_v26_stage(
            ledger,
            stage="fresh_task_population",
            artifacts=(reference,),
        )


def test_v26_router_model_validation_replays_completed_stage_files(tmp_path: Path) -> None:
    population_path = tmp_path / "population.json"
    _write_population(population_path)
    ledger = _empty_ledger(tmp_path)
    reference = make_v26_stage_artifact_reference(
        "fresh_task_population",
        population_path,
    )
    advanced = advance_v26_stage(
        ledger,
        stage="fresh_task_population",
        artifacts=(reference,),
    )
    population_path.write_text(
        population_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    provisional = advanced.model_copy(update={"ledger_id": "pending"})
    payload = advanced.model_dump(mode="json")
    payload["ledger_id"] = v26_stage_ledger_id(provisional)

    with pytest.raises(ValidationError, match="content hash replay failed"):
        V26StageLedger.model_validate(payload)


def test_v26_router_rejects_api_calls_before_scaffold_admission(tmp_path: Path) -> None:
    population_path = tmp_path / "population.json"
    _write_population(population_path)
    ledger = _empty_ledger(tmp_path)
    payload = ledger.model_dump(mode="json")
    payload["model_api_call_count"] = 1

    with pytest.raises(ValidationError, match="before Scaffold Admission"):
        V26StageLedger.model_validate(payload)


def test_v26_router_rejects_nonprefix_stage_history(tmp_path: Path) -> None:
    population_path = tmp_path / "population.json"
    _write_population(population_path)
    ledger = _empty_ledger(tmp_path)
    payload = ledger.model_dump(mode="json")
    payload["completed_stages"] = ["fresh_task_population", "joint_audit"]
    payload["artifacts_by_stage"] = {
        "fresh_task_population": [ledger.protocol_reference.model_dump(mode="json")],
        "joint_audit": [ledger.protocol_reference.model_dump(mode="json")],
    }
    payload["current_stage"] = "joint_audit"
    payload["next_stage"] = "joint_admission"

    with pytest.raises(ValidationError, match="skipped, or reordered"):
        V26StageLedger.model_validate(payload)


def test_v26_router_rejects_a_rehashed_but_stale_preflight_manifest(
    tmp_path: Path,
) -> None:
    protocol = _protocol()
    preflight = _preflight(protocol)
    values = preflight.model_dump(mode="python", exclude={"report_id"})
    values["code_sha256"]["v26_stage_router"] = "0" * 64
    provisional = MainlinePreflightReport.model_construct(report_id="pending", **values)
    stale = MainlinePreflightReport(
        report_id=mainline_preflight_report_id(provisional),
        **values,
    )
    protocol_path = tmp_path / "protocol.json"
    preflight_path = tmp_path / "stale_preflight.json"
    protocol_path.write_text(protocol.model_dump_json(), encoding="utf-8")
    preflight_path.write_text(stale.model_dump_json(), encoding="utf-8")

    with pytest.raises(ValueError, match="implementation manifest is stale"):
        initialize_v26_stage_ledger(
            run_id="stale_preflight_test",
            protocol_path=protocol_path,
            preflight_path=preflight_path,
        )
