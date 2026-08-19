from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_preflight import (  # noqa: E501
    CompilerReplayAudit,
    PreflightMutationAudit,
    PublicPrivateIsolationAudit,
    VerifierBoundInstrumentContract,
    VerifierBoundInstrumentJobManifest,
    VerifierBoundInstrumentPreflightReport,
    VerifierBoundSourceReplayAudit,
    build_verifier_bound_instrument_preflight,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
TASK_SOURCE = ARTIFACT_ROOT / "finance_v26_76_verifier_bound_instrument_population_20260819"
VERIFIER_QUALIFICATION = (
    ARTIFACT_ROOT / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
)
HISTORICAL_JOB_MANIFESTS = (
    ARTIFACT_ROOT
    / "finance_v26_63_operation_closure_requalification_20260818"
    / "job_manifest.json",
    ARTIFACT_ROOT
    / (
        "finance_v26_66_authority_preserving_instrument_requalification_"
        "finalization_recovery_20260819"
    )
    / "job_manifest.json",
    ARTIFACT_ROOT / "finance_v26_71_capability_development_20260819" / "job_manifest.json",
    ARTIFACT_ROOT / "finance_v26_72_state_reachability_20260819" / "job_manifest.json",
)
FORMAL = ARTIFACT_ROOT / "finance_v26_77_verifier_bound_instrument_preflight_20260819"
RUN_ID = "finance_v26_77_verifier_bound_instrument_preflight_20260819"
DETAIL_FILES = (
    "compiler_replay_audits.json",
    "destructive_mutation_audits.json",
    "execution_contract.json",
    "job_manifest.json",
    "public_private_isolation_audits.json",
    "report.json",
    "source_replay_audit.json",
)


def _build(output: Path) -> VerifierBoundInstrumentPreflightReport:
    return build_verifier_bound_instrument_preflight(
        run_id=RUN_ID,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER_QUALIFICATION,
        historical_job_manifest_paths=HISTORICAL_JOB_MANIFESTS,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_77_rebuild")
    _build(output)
    return output


def _load_list(path: Path, model: type[ModelT]) -> tuple[ModelT, ...]:
    return tuple(
        model.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))
    )


def test_v26_77_is_deterministic_and_matches_formal(
    rebuilt: Path,
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate"
    _build(duplicate)
    for relative in DETAIL_FILES:
        assert (rebuilt / relative).read_bytes() == (duplicate / relative).read_bytes()
        assert (rebuilt / relative).read_bytes() == (FORMAL / relative).read_bytes()


def test_source_replay_and_contract_are_complete(rebuilt: Path) -> None:
    replay = VerifierBoundSourceReplayAudit.model_validate_json(
        (rebuilt / "source_replay_audit.json").read_text(encoding="utf-8")
    )
    contract = VerifierBoundInstrumentContract.model_validate_json(
        (rebuilt / "execution_contract.json").read_text(encoding="utf-8")
    )

    assert replay.replayed_file_count == replay.replay_pass_count
    assert replay.replay_pass_count >= 50
    assert all(item.passed for item in replay.entries)
    assert contract.expected_job_count == 32
    assert contract.replicas_per_task == 4
    assert contract.model_id == "deepseek-v4-flash"
    assert not contract.fallback_models
    assert contract.require_requested_model
    assert contract.measurement_instrument_only
    assert contract.runtime_verifier_semantic_commutativity_required
    assert contract.maximum_total_estimated_cost_usd == 2.0


def test_job_manifest_is_fresh_and_balanced(rebuilt: Path) -> None:
    manifest = VerifierBoundInstrumentJobManifest.model_validate_json(
        (rebuilt / "job_manifest.json").read_text(encoding="utf-8")
    )

    assert len(manifest.jobs) == 32
    assert len({item.job_id for item in manifest.jobs}) == 32
    assert Counter(item.mechanism_id for item in manifest.jobs) == {
        "context_conditioned_action": 8,
        "semantic_reconciliation": 8,
        "failure_recovery": 8,
        "state_dependent_stopping": 8,
    }
    assert set(Counter(item.task_package_id for item in manifest.jobs).values()) == {4}
    historical_ids: set[str] = set()
    for path in HISTORICAL_JOB_MANIFESTS:
        historical_ids.update(
            item["job_id"] for item in json.loads(path.read_text(encoding="utf-8"))["jobs"]
        )
    assert not ({item.job_id for item in manifest.jobs} & historical_ids)


def test_compiler_replay_and_public_isolation_pass(rebuilt: Path) -> None:
    compiler = _load_list(rebuilt / "compiler_replay_audits.json", CompilerReplayAudit)
    isolation = _load_list(
        rebuilt / "public_private_isolation_audits.json", PublicPrivateIsolationAudit
    )

    assert len(compiler) == len(isolation) == 8
    assert sum(item.observation_count for item in compiler) == 81
    assert all(item.passed and item.runtime_verifier_semantically_equal for item in compiler)
    assert all(not item.replay_failure_ids for item in compiler)
    assert all(item.passed for item in isolation)
    assert all(not item.forbidden_key_paths for item in isolation)
    assert all(not item.private_identity_paths for item in isolation)


def test_destructive_replay_mutations_fail_closed(rebuilt: Path) -> None:
    audits = _load_list(rebuilt / "destructive_mutation_audits.json", PreflightMutationAudit)

    assert len(audits) == 24
    assert Counter(item.mutation_kind for item in audits) == {
        "wrong_environment": 8,
        "changed_result": 8,
        "action_bearing_repair": 8,
    }
    assert all(item.mutated_observation_content_address_valid for item in audits)
    assert all(item.baseline_replay_passed and item.mutation_rejected for item in audits)
    environment = tuple(item for item in audits if item.mutation_kind == "wrong_environment")
    assert all("environment_identity" in item.replay_failure_ids[0] for item in environment)
    payload = tuple(item for item in audits if item.mutation_kind != "wrong_environment")
    assert all(
        any("replay_mismatch" in failure for failure in item.replay_failure_ids) for item in payload
    )


def test_v26_77_authorizes_only_small_instrument_requalification(rebuilt: Path) -> None:
    report = VerifierBoundInstrumentPreflightReport.model_validate_json(
        (rebuilt / "report.json").read_text(encoding="utf-8")
    )

    assert report.expected_job_count == report.fresh_job_count == 32
    assert report.compiler_runtime_witness_pass_count == 8
    assert report.compiler_witness_observation_count == 81
    assert report.destructive_replay_mutation_reject_count == 24
    assert report.authority_terminal_mutation_reject_count == 40
    assert report.legacy_operation_mutation_reject_count == 64
    assert report.historical_job_identity_overlap_count == 0
    assert not report.model_client_constructed
    assert report.next_permitted_stage == (
        "fresh_verifier_v2_bound_instrument_requalification_only"
    )
    assert report.instrument_requalification_authorized
    assert not report.capability_development_execution_authorized
    assert not report.state_reachability_execution_authorized
    assert report.model_api_calls == report.gpu_jobs == report.production_contribution == 0


def test_v26_77_identity_and_mutation_semantics_fail_closed(rebuilt: Path) -> None:
    contract = json.loads((rebuilt / "execution_contract.json").read_text(encoding="utf-8"))
    contract["maximum_total_estimated_cost_usd"] = 2.5
    with pytest.raises(ValidationError):
        VerifierBoundInstrumentContract.model_validate(contract)

    mutation = json.loads(
        (rebuilt / "destructive_mutation_audits.json").read_text(encoding="utf-8")
    )[0]
    mutation["replay_failure_ids"] = ["observation:0:unrelated_failure"]
    with pytest.raises(ValidationError, match="another reason"):
        PreflightMutationAudit.model_validate(mutation)

    report = json.loads((rebuilt / "report.json").read_text(encoding="utf-8"))
    report["report_id"] = "finance_v26_verifier_bound_instrument_preflight:tampered"
    with pytest.raises(ValidationError, match="identity is invalid"):
        VerifierBoundInstrumentPreflightReport.model_validate(report)
