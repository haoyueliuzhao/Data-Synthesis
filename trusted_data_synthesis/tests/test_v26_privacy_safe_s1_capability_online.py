from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_online as online,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_safe_s1_capability_preflight as preflight,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_DIR = PACKAGE_ROOT / preflight.OUTPUT_DIR


class _OnlineScriptedClient:
    def __init__(self, delegate: preflight.runner_base.ScriptedS1QualificationClient) -> None:
        self.config = delegate.config
        self._delegate = delegate

    def complete_json_certified(self, prompt: str, certificate: Any) -> Any:
        payload, telemetry = self._delegate.complete_json_certified(prompt, certificate)
        telemetry = telemetry.model_copy(
            update={
                "response_shape": {
                    "provider_native_tool_call_observed": False,
                }
            }
        )
        return payload, telemetry


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> online.PreparedExecution:
    output_dir = tmp_path_factory.mktemp("v26_141_prepare")
    return online.prepare_execution(
        preflight_dir=PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
    )


def test_v26_141_replacement_provenance_and_exact_binding(
    prepared: online.PreparedExecution,
) -> None:
    assert prepared.source_replay.replayed_file_count == 4_553
    assert prepared.preexecution_binding.byte_identical_preflight_output_count == 17
    assert prepared.preexecution_binding.scripted_fixture_call_count == 984
    assert prepared.preexecution_binding.operator_authorized_replacement_rerun
    assert not prepared.preexecution_binding.prior_attempt_artifacts_available
    assert prepared.preexecution_binding.prior_attempt_auditable_job_count == 0
    assert prepared.preexecution_binding.prior_attempt_pooled_job_count == 0
    assert not prepared.preexecution_binding.pristine_first_exposure_claimed
    assert prepared.preexecution_binding.exact_v26_140_manifest_reused
    assert prepared.preexecution_binding.durable_canonical_output_root_required
    assert prepared.manifest.manifest_id == online.EXPECTED_MANIFEST_ID
    assert len(prepared.manifest.jobs) == 96
    assert prepared.manifest.reachability_job_count == 0


def test_v26_141_full_scripted_denominator_and_zero_call_resume(
    prepared: online.PreparedExecution,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def scripted_factory(config: Any, _job: Any, binding: Any) -> _OnlineScriptedClient:
        final_answer = preflight._reference_final_answer(  # noqa: SLF001
            binding,
            grammar=prepared.inputs.static.final_grammar,
        )
        return _OnlineScriptedClient(
            preflight.runner_base.ScriptedS1QualificationClient(
                config,
                final_answer=final_answer,
            )
        )

    monkeypatch.setattr(online, "prepare_execution", lambda **_kwargs: prepared)
    output_dir = tmp_path / "execution"
    report = online.run_privacy_safe_s1_capability(
        preflight_dir=PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=8,
        client_factory=scripted_factory,
    )
    assert report.completed_job_result_count == 96
    assert report.complete_raw_execution_count == 96
    assert report.terminal_counts == {"model_valid_trajectory": 96}
    assert report.provider_call_count == 984
    assert report.action_entry_job_count == 96
    assert report.program_closed_job_count == 96
    assert report.independently_valid_trajectory_count == 96
    assert report.mechanisms_with_independently_valid_trajectory == 4
    assert report.tasks_with_independently_valid_trajectory == 12
    assert report.combined_integrity_gate_failure_job_count == 0
    assert report.combined_support_boundary_failure_job_count == 0
    assert report.capability_successor_preflight_gate_passed
    assert report.operator_authorized_replacement_rerun
    assert not report.pristine_first_exposure_claimed
    assert report.prior_lost_attempt_artifact_count == 0
    assert report.prior_lost_attempt_auditable_job_count == 0
    assert report.prior_lost_attempt_pooled_job_count == 0
    assert report.stage_two_provider_call_count == 0
    assert report.reachability_job_count == 0
    assert report.state_mapping_rows == 0
    assert report.next_permitted_stage == online.POSTRUN_STAGE

    diagnostics = tuple(
        online.CapabilityChoiceDiagnostic.model_validate(item)
        for item in online._load(  # noqa: SLF001
            output_dir / "privacy_safe_s1_capability_choice_diagnostics.json"
        )
    )
    assert len(diagnostics) == 888
    assert max(item.candidate_count for item in diagnostics) == 63

    def forbidden_client(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("completed v26.141 replay constructed a client")

    recovered = online.run_privacy_safe_s1_capability(
        preflight_dir=PREFLIGHT_DIR,
        output_dir=output_dir,
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        workers=8,
        client_factory=forbidden_client,
    )
    assert recovered == report
