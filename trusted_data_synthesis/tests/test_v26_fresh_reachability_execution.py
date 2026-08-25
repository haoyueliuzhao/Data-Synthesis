from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from trusted_synthesis.core.evaluation.joint_support_validity import (
    JointSupportValidityContract,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_runner_preflight as preflight,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / execution.OUTPUT_DIR


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _prepared() -> execution.PreparedExecution:
    _, replay_contract = preflight.bounded.predecessor._load_and_replay_verifier_qualification(  # noqa: SLF001
        PACKAGE_ROOT / preflight.bounded.predecessor.VERIFIER_QUALIFICATION_DIR,
        PACKAGE_ROOT,
    )
    return execution.PreparedExecution(
        source_replay=execution.ExecutionSourceReplayAudit.model_validate(
            _load(FORMAL_DIR / "execution_source_replay_audit.json")
        ),
        preflight_report=preflight.ReachabilityPreflightReport.model_validate(
            _load(FORMAL_DIR / "frozen_v26_153_report.json")
        ),
        frozen_input=preflight.FrozenReachabilityInputAudit.model_validate(
            _load(FORMAL_DIR / "frozen_reachability_input_audit.json")
        ),
        tasks=preflight.TaskPackageCatalog.model_validate(
            _load(FORMAL_DIR / "frozen_reachability_task_package_catalog.json")
        ),
        paths=preflight.PathCatalog.model_validate(
            _load(FORMAL_DIR / "frozen_reachability_path_catalog.json")
        ),
        support_closure=preflight.SupportClosureAudit.model_validate(
            _load(FORMAL_DIR / "frozen_support_closure_audit.json")
        ),
        detour_qualification=preflight.ReachabilityDetourQualificationAudit.model_validate(
            _load(FORMAL_DIR / "frozen_detour_qualification_audit.json")
        ),
        resource=preflight.ResourceContract.model_validate(
            _load(FORMAL_DIR / "frozen_reachability_resource_contract.json")
        ),
        execution_contract=preflight.ExecutionContract.model_validate(
            _load(FORMAL_DIR / "frozen_reachability_execution_contract.json")
        ),
        manifest=preflight.ReachabilityManifest.model_validate(
            _load(FORMAL_DIR / "frozen_reachability_manifest.json")
        ),
        outcome_contract=preflight.OutcomeContract.model_validate(
            _load(FORMAL_DIR / "frozen_reachability_outcome_contract.json")
        ),
        runner_contract=preflight.RunnerContract.model_validate(
            _load(FORMAL_DIR / "frozen_reachability_runner_contract.json")
        ),
        joint_contract=JointSupportValidityContract.model_validate(
            _load(FORMAL_DIR / "frozen_joint_support_validity_contract.json")
        ),
        grammar=QualifiedFinalResponseGrammar.model_validate(
            _load(FORMAL_DIR / "frozen_qualified_final_response_grammar.json")
        ),
        transition=preflight.ProspectiveTransitionContract.model_validate(
            _load(FORMAL_DIR / "frozen_preflight_transition_contract.json")
        ),
        preexecution_binding=execution.PreexecutionBindingAudit.model_validate(
            _load(FORMAL_DIR / "preexecution_binding_audit.json")
        ),
        role_inputs=preflight.old_capability._load_role_inputs(  # noqa: SLF001
            package_root=PACKAGE_ROOT,
            implementation_root=PACKAGE_ROOT,
        ),
        replay_contract=replay_contract,
    )


def test_v26_154_prepare_only_is_exact_and_has_zero_online_artifacts() -> None:
    prepared = _prepared()
    files = tuple(path for path in FORMAL_DIR.iterdir() if path.is_file())

    assert prepared.source_replay.replayed_file_count == 10_156
    assert prepared.source_replay.replay_pass_count == 10_156
    assert prepared.preexecution_binding.exact_job_count == 360
    assert prepared.preexecution_binding.unconditional_job_count == 144
    assert prepared.preexecution_binding.conditioned_job_count == 216
    assert prepared.preexecution_binding.registered_path_count == 36
    assert len(files) == 17
    assert not (FORMAL_DIR / "fresh_reachability_results.checkpoint.jsonl").exists()
    assert not tuple(FORMAL_DIR.glob("raw_execution/**/*.json"))
    assert not tuple(FORMAL_DIR.glob("raw_provider_envelopes/**/*.json"))
    assert not tuple(FORMAL_DIR.glob("public_payload_projections/**/*.json"))
    assert not tuple(FORMAL_DIR.glob("transport_invocation_certificates/**/*.json"))


def test_v26_154_unconditional_and_conditioned_scripted_jobs_are_route_bound() -> None:
    prepared = _prepared()
    static = prepared.role_inputs.static
    paths, registered, unconditional = preflight._make_paths(  # noqa: SLF001
        tasks=prepared.tasks,
        frozen_input=prepared.frozen_input,
        static=static,
        grammar=prepared.grammar,
    )
    assert paths == prepared.paths
    registered_by_id = {
        item.path.path_id: item
        for item in registered
        if isinstance(item.path, preflight.FreshReachabilityPath)
    }
    unconditional_by_task = {item.package.task_package_id: item for item in unconditional}
    jobs = (
        next(
            item
            for item in prepared.manifest.jobs
            if item.sampling_mode == "reachability_unconditional"
        ),
        next(
            item
            for item in prepared.manifest.jobs
            if item.sampling_mode == "reachability_conditioned"
        ),
    )

    def client_factory(
        _config: Any,
        job: preflight.FreshReachabilityJob,
        _binding: Any,
    ) -> Any:
        compiled = (
            unconditional_by_task[job.task_package_id]
            if job.requested_path_id is None
            else registered_by_id[job.requested_path_id]
        )
        return preflight.s1_runner.ScriptedS1QualificationClient(
            static.agent_model_config,
            final_answer=preflight._reference_final_answer(  # noqa: SLF001
                compiled,
                old_grammar=static.final_grammar,
            ),
        )

    with tempfile.TemporaryDirectory(prefix="v26_154_two_job_control_") as temporary:
        pairs = tuple(
            execution._run_one_job(  # noqa: SLF001
                job=job,
                prepared=prepared,
                client_factory=client_factory,
                output_dir=Path(temporary),
            )
            for job in jobs
        )

    results = tuple(item[0] for item in pairs)
    unconditional_result, conditioned_result = results
    assert unconditional_result.sampling_mode == "reachability_unconditional"
    assert unconditional_result.requested_path_id is None
    assert unconditional_result.public_path_condition is None
    assert conditioned_result.sampling_mode == "reachability_conditioned"
    assert conditioned_result.requested_path_id is not None
    assert conditioned_result.requested_path_strategy == conditioned_result.public_path_condition
    assert all(item.condition_binding_valid for item in results)
    for job, (_, raw) in zip(jobs, pairs, strict=True):
        package = execution._package_for_job(prepared, job)  # noqa: SLF001
        execution._online_noninterference(  # noqa: SLF001
            raw=raw,
            package=package,
            job=job,
            prepared=prepared,
        )
        replay = execution.replay_authority_preserving_observations(
            prepared.replay_contract,
            package.operational_record,
            package.environment,
            raw.observations,
        )
        assert replay.passed
    assert all(item.exact_model_passed for item in results)
    assert all(item.fallback_absent for item in results)
    assert all(item.thinking_continuity_passed for item in results)
    assert all(item.provider_usage_complete for item in results)
    assert all(item.dynamic_precall_binding_passed for item in results)
    assert all(item.exact_request_binding_passed for item in results)
    assert all(item.privacy_artifact_pairing_passed for item in results)
    assert all(item.reversible_commit_integrity_passed for item in results)
    assert all(item.rollout_budget_passed for item in results)
    assert all(item.provider_native_tool_absent is False for item in results)
    assert all(item.instrument_integrity is False for item in results)
    assert all(item.qualified_trajectory_validity is None for item in results)
    assert all(item.state_mapping_eligible is False for item in results)
    assert all(item.state_mapping_row_count == 0 for item in results)

    gate = execution._measurement_gate(results, complete_raw_count=2)  # noqa: SLF001
    assert gate.passed is False
    assert gate.failure_ids == (
        "complete_raw_360_of_360",
        "instrument_failure_zero",
        "model_endpoint_360_of_360",
    )
    payload = json.loads(execution._canonical_bytes(results))  # noqa: SLF001
    assert isinstance(payload, list)
    assert len(payload) == 2
