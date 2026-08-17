from __future__ import annotations

import json
from types import SimpleNamespace
from typing import cast

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bridge_rollout import (
    audit_historical_api_exposure,
    audit_historical_evidence_pool_exposure,
    build_historical_api_record_manifest,
    evaluate_bridge_estimands,
    make_provider_call_ids,
    replay_raw_payload,
    write_raw_payload_first,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bridge_rollout_runner import (
    _audit_raw_artifacts,
    _build_jobs,
    _captured_llm_failure_is_model_outcome,
    _failure_attribution,
    _make_run_report,
    _one_pending_job_per_cell,
)


def test_raw_payload_is_written_before_and_replays_canonical_bytes(tmp_path) -> None:
    path = tmp_path / "raw" / "rollout.json"
    payload = {
        "task_id": "task:new",
        "provider_call_ids": ["call:1"],
        "terminal_category": "model_valid_trajectory",
    }
    digest = write_raw_payload_first(path, payload)

    assert replay_raw_payload(path, digest) == payload
    assert path.read_bytes() == (
        b'{"provider_call_ids":["call:1"],'
        b'"task_id":"task:new","terminal_category":"model_valid_trajectory"}'
    )
    assert write_raw_payload_first(path, payload) == digest

    mutated = {**payload, "terminal_category": "model_invalid_trajectory"}
    with pytest.raises(ValueError, match="identity already exists with different bytes"):
        write_raw_payload_first(path, mutated)


def test_bridge_failure_attribution_is_deterministic() -> None:
    verification = SimpleNamespace(
        checks=(
            SimpleNamespace(check_id="answer_schema", passed=True),
            SimpleNamespace(check_id="operation_replay", passed=False),
        )
    )
    failure_artifact = SimpleNamespace(artifact_id="failure:captured")

    assert _captured_llm_failure_is_model_outcome(
        (SimpleNamespace(http_success=True),),
        failure_artifact,
    )
    assert not _captured_llm_failure_is_model_outcome(
        (SimpleNamespace(http_success=False),),
        failure_artifact,
    )

    assert (
        _failure_attribution(
            terminal="model_valid_trajectory",
            verification=verification,
            failure_reason=None,
        )
        is None
    )
    assert _failure_attribution(
        terminal="model_invalid_trajectory",
        verification=verification,
        failure_reason=None,
    ) == {
        "category": "independent_verification_failed",
        "failed_check_ids": ["operation_replay"],
    }
    assert _failure_attribution(
        terminal="model_invalid_trajectory",
        verification=None,
        failure_reason="contract exhausted",
    ) == {"category": "model_contract_failure", "reason": "contract exhausted"}
    assert _failure_attribution(
        terminal="runtime_failure",
        verification=None,
        failure_reason="contract exhausted",
    ) == {"category": "runtime_failure", "reason": "contract exhausted"}


def test_historical_api_exposure_is_fail_closed_on_evidence_overlap(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    historical = artifact_root / "historical_rollouts.jsonl"
    historical.write_text(
        json.dumps(
            {
                "task_id": "task:old",
                "evidence_ids": ["evidence:shared"],
                "instruction": "an old public question",
                "model_selected": "deepseek-v4-flash",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    channels = {
        "task_id": {"task:new"},
        "source_task_id": {"source-task:new"},
        "evidence_id": {"evidence:shared"},
        "evidence_version_id": {"evidence-version:new"},
        "core_semantic_signature": {"core:new"},
        "task_signature": {"task-signature:new"},
        "mechanism_instance_signature": {"mechanism:new"},
        "source_record_id": {"source-record:new"},
    }
    manifest = build_historical_api_record_manifest(
        artifact_root=artifact_root,
    )

    audit = audit_historical_api_exposure(
        current_population_id="population:new",
        current_identity_channels=channels,
        current_instructions=("a new public question",),
        record_manifest=manifest,
    )

    assert audit.status == "blocked"
    assert audit.exposed_evidence_ids == ("evidence:shared",)
    assert audit.exposed_task_ids == ()
    assert manifest.record_file_sha256[str(historical.resolve())]


def test_full_source_pool_exposure_is_frozen_before_resampling(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    historical = artifact_root / "historical_rollouts.jsonl"
    historical.write_text(
        json.dumps(
            {
                "evidence_ids": ["evidence:shared"],
                "model_selected": "deepseek-v4-flash",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    source = tmp_path / "source.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    manifest = build_historical_api_record_manifest(artifact_root=artifact_root)

    audit = audit_historical_evidence_pool_exposure(
        source_artifacts_path=source,
        source_evidence_ids=("evidence:fresh", "evidence:shared"),
        record_manifest=manifest,
    )

    assert audit.status == "observed"
    assert audit.source_evidence_count == 2
    assert audit.exposed_evidence_ids == ("evidence:shared",)
    assert audit.exposed_evidence_count == 1
    assert audit.unexposed_evidence_count == 1


def test_estimands_measure_actions_not_answer_accuracy_only() -> None:
    source_task = cast(
        CapabilitySensitiveTaskArtifact,
        SimpleNamespace(
            query_stages=(SimpleNamespace(action="broad_search"),),
            required_tool_ids=("calculator", "search_archive"),
            reconciliation_axes=("metric_definition",),
            structure=SimpleNamespace(operation_branch_count=2, minimal_tool_calls=3),
        ),
    )
    observations = (
        SimpleNamespace(
            status="succeeded",
            call=SimpleNamespace(tool_id="search_archive"),
            error_code=None,
            evidence_ids=(),
        ),
        SimpleNamespace(
            status="failed",
            call=SimpleNamespace(tool_id="query_structured_fact"),
            error_code="ambiguous_period",
            evidence_ids=(),
        ),
        SimpleNamespace(
            status="succeeded",
            call=SimpleNamespace(tool_id="normalize_metric_unit_period"),
            error_code=None,
            evidence_ids=("evidence:1",),
        ),
    )
    outcomes = evaluate_bridge_estimands(
        mechanism_id="recovery_and_stopping",
        source_task=source_task,
        observations=observations,  # type: ignore[arg-type]
        trajectory_steps=(
            {"operator_id": "growth:left"},
            {"operator_id": "growth:right"},
        ),
        independent_validity_passed=True,
        stopped_by_model=True,
        stop_rejection_count=1,
    )

    assert [item.estimand_id for item in outcomes] == [
        "failure_recovery",
        "stopping_calibration",
    ]
    assert all(item.success for item in outcomes)
    assert not any(item.fixed_policy_success for item in outcomes)


def test_provider_call_identity_includes_rollout_and_call_index() -> None:
    telemetry = (
        {
            "request_hash": "request",
            "response_hash": "response",
            "model_selected": "deepseek-v4-flash",
            "http_status": 200,
        },
        {
            "request_hash": "request",
            "response_hash": "response",
            "model_selected": "deepseek-v4-flash",
            "http_status": 200,
        },
    )
    first = make_provider_call_ids(
        rollout_identity={"task_id": "task:1", "replicate": 0},
        telemetry=telemetry,
    )
    second = make_provider_call_ids(
        rollout_identity={"task_id": "task:1", "replicate": 1},
        telemetry=telemetry,
    )

    assert len(set(first)) == 2
    assert set(first).isdisjoint(second)


def test_smoke_selection_imports_runner_and_covers_each_mechanism_level_cell() -> None:
    mechanisms = (
        "context_conditioned_action",
        "semantic_reconciliation",
        "recovery_and_stopping",
    )
    levels = ("gamma_0", "gamma_1", "gamma_2", "gamma_3")
    jobs = [
        (
            {
                "mechanism_id": mechanism,
                "scaffold_level": level,
                "replica_id": replica,
            },
            None,
            None,
            None,
            None,
            None,
        )
        for mechanism in mechanisms
        for level in levels
        for replica in range(2)
    ]

    selected = _one_pending_job_per_cell(jobs)

    assert len(selected) == 12
    assert {(item[0]["mechanism_id"], item[0]["scaffold_level"]) for item in selected} == {
        (mechanism, level) for mechanism in mechanisms for level in levels
    }


def test_build_jobs_joins_frozen_artifacts_by_identity_not_sequence() -> None:
    levels = ("gamma_0", "gamma_1", "gamma_2", "gamma_3")

    def make_bundle(index: int):
        task_id = f"task:{index}"
        source_id = f"source:{index}"
        ladder_id = f"ladder:{index}"
        root = SimpleNamespace(
            source_task_artifact_id=source_id,
            mechanism_id="context_conditioned_action",
        )
        source = SimpleNamespace(
            artifact_id=source_id,
            task=SimpleNamespace(task_id=task_id),
        )
        compiled = SimpleNamespace(task=SimpleNamespace(task_id=task_id))
        projections = tuple(
            SimpleNamespace(
                scaffold_level=level,
                compiled_task_condition_id=f"condition:{index}:{level}",
                base_runtime_projection=SimpleNamespace(task_id=task_id),
            )
            for level in levels
        )
        ladder = SimpleNamespace(ladder_id=ladder_id, projections=projections)
        admission = SimpleNamespace(ladder_id=ladder_id)
        return root, source, compiled, ladder, admission

    first = make_bundle(1)
    second = make_bundle(2)
    population = SimpleNamespace(tasks=(first[0], second[0]))

    jobs = _build_jobs(
        cast(object, population),  # type: ignore[arg-type]
        (second[1], first[1]),
        (second[2], first[2]),
        (second[3], first[3]),
        (second[4], first[4]),
    )

    assert len(jobs) == 48
    assert jobs[0][0]["task_id"] == "task:1"
    assert jobs[0][0]["source_task_artifact_id"] == "source:1"
    assert jobs[24][0]["task_id"] == "task:2"


def test_bridge_run_report_uses_the_support_freeze_transition() -> None:
    observations = tuple(
        SimpleNamespace(
            terminal_category="model_invalid_trajectory",
            provider_call_ids=(),
        )
        for _ in range(576)
    )
    raw_audit = _audit_raw_artifacts((), expected_count=576)
    support_freeze = SimpleNamespace(
        freeze_id="bridge-freeze:test",
        next_transition="capability_task_or_scaffold_redesign_only",
    )

    report = _make_run_report(
        run_id="run:test",
        contract=SimpleNamespace(contract_id="contract:test"),
        exposure=SimpleNamespace(audit_id="exposure:test"),
        discovered_models=("deepseek-v4-flash",),
        observations=observations,  # type: ignore[arg-type]
        raw_audit=raw_audit,
        support_freeze=support_freeze,  # type: ignore[arg-type]
        status="completed",
        next_stage=support_freeze.next_transition,
    )

    assert report.next_permitted_stage == "capability_task_or_scaffold_redesign_only"
