# ruff: noqa: E501
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_actual_typed_failure_source_totality_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_actual_typed_failure_source_totality_preflight as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_actual_typed_failure_source_totality_runtime as runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_contract_continuity_repair_preflight as v209,
)

REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/72808d0b-d1f5-4937-b3b5-69f231ff414d/pasted-text.txt"
)
FORMAL = Path(subject.OUTPUT_DIR)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, tuple[str, str]]:
    repository = Path(__file__).resolve().parents[2]
    formal = repository / FORMAL
    if formal.is_dir():
        source = _load(formal / "source_identity.json")
        source_identity = (str(source["source_commit"]), str(source["source_tree"]))
    else:
        source_identity = ("1" * 40, "2" * 40)
    output = tmp_path_factory.mktemp("v26_215") / "build"
    subject.build(
        repository_root=repository,
        output_dir=output,
        external_review_path=REVIEW,
        source_identity=source_identity,
    )
    return repository, output, source_identity


def test_external_authority_and_v214_freeze(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    external = _load(output / "external_revision_authorization.json")
    freeze = _load(output / "v214_freeze.json")
    assert external["review_sha256"] == subject.REVIEW_SHA256
    assert external["review_byte_count"] == 13_092
    assert external["operator_directive_byte_count"] == 42
    assert (
        external["operator_directive_sha256"]
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert external["failed_at"] == "ACTUAL_V209_TYPED_FAILURE_SOURCE_SURFACE_TOTALITY"
    assert freeze["formal_file_count"] == 63
    assert freeze["dedicated_exception_controls_retained"] is True
    assert freeze["actual_v209_source_totality_failed"] is True
    assert freeze["v211_authorization_consumed"] is False


def test_exact_v209_source_contract_uses_type_id_instance_terminal_and_origin(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    contract = _load(output / "typed_failure_source_contract.json")
    assert contract["exact_v209_source_sha256"] == (
        "4529523fc737f26801118cc5cf78b682f2e510c5f887ed0d14a60a5bd26d9b35"
    )
    assert contract["admitted_exception_type_ids"] == [models.EXACT_V209_EXCEPTION_TYPE_ID]
    assert contract["failure_origin_terminals"] == [
        ["transport_send", ["instrument_failure"]],
        ["public_projection", ["instrument_failure", "privacy_rejection"]],
    ]
    assert contract["total_raise_callsite_count"] == 4
    assert contract["bare_class_name_authority"] is False
    assert contract["class_to_unique_terminal_required"] is False
    assert contract["instance_terminal_required"] is True


def test_runner_has_two_origin_specific_catches_and_no_terminal_input(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    runner_source = inspect.getsource(runtime.ActualSourceAuthenticRunner._invoke_current_state)
    terminalizer_source = inspect.getsource(
        runtime.ActualSourceAuthenticRunner._terminalize_actual_failure
    )
    dispatcher_parameters = tuple(
        inspect.signature(runtime.ActualSourceDispatcher.dispatch).parameters
    )
    binding = _load(output / "runner_observation_binding.json")
    assert runner_source.count("except v209.TypedTransportFailure as error:") == 2
    assert 'failure_origin="transport_send"' in runner_source
    assert 'failure_origin="public_projection"' in runner_source
    assert "_exception_type_id(error)" in terminalizer_source
    assert "error.terminal" in terminalizer_source
    assert dispatcher_parameters == ("self", "evidence")
    assert binding["observation_constructed_from_actual_caught_instance"] is True
    assert binding["separate_transport_and_projection_catches"] is True


def test_four_actual_v209_base_exception_sources_terminalize_and_persist(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "source_surface_execution_audit.json")
    assert [
        (item["control_name"], item["expected_origin"], item["expected_terminal"])
        for item in audit["controls"]
    ] == [tuple(item) for item in models.SOURCE_CONTROL_ITEMS]
    assert audit["exercised_source_callsite_count"] == 4
    assert audit["actual_base_exception_count"] == 4
    assert audit["runner_owned_observation_count"] == 4
    assert audit["consumer_terminal_branch_count"] == 4
    assert audit["exact_origin_terminal_match_count"] == 4
    assert audit["persisted_layer_count"] == 20
    assert audit["exception_escape_count"] == 0
    assert {item["failure_observation"]["exception_type_id"] for item in audit["controls"]} == {
        models.EXACT_V209_EXCEPTION_TYPE_ID
    }
    assert {item["failure_observation"]["exception_qualname"] for item in audit["controls"]} == {
        v209.TypedTransportFailure.__qualname__
    }


def test_raw_binds_exact_source_observation_record_and_decision(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    for control in _load(output / "source_surface_execution_audit.json")["controls"]:
        raw = _load(output / control["persistence"]["raw_relative_path"])
        observation = models.TypedFailureObservation.model_validate(raw["failure_observation"])
        evidence = models.AuthenticatedTypedFailureEvidence.model_validate(
            raw["authenticated_evidence"]
        )
        decision = models.DerivedTerminalDecision.model_validate(raw["derived_terminal_decision"])
        record = observation.invocation_record
        assert observation.runner_owned is True
        assert observation.actual_source_admitted is True
        assert observation.failure_origin == decision.failure_origin
        assert observation.caught_terminal_kind == decision.terminal_kind
        assert record["typed_terminal"] == decision.terminal_kind
        assert record["event_sequence"][-1] == "terminal_dispatch"
        assert evidence.failure_observation.observation_id == observation.observation_id


def test_source_admission_and_retained_fully_rehashed_attacks_reject(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "negative_control_audit.json")
    assert {item["control_name"] for item in audit["controls"]} == {
        "base_exception_unregistered_terminal",
        "nonregistered_exact_class_spoof",
        "instrument_observation_reclassified_as_provider_identity",
        "privacy_observation_reclassified_as_transport",
        "exception_reason_hash_replaced",
        "cross_job_failure_observation_substituted",
    }
    assert (
        audit["rejected_count"],
        audit["accepted_count"],
        audit["source_admission_rejection_count"],
        audit["retained_authority_attack_count"],
        audit["raw_write_count"],
    ) == (6, 0, 2, 4, 0)
    assert audit["fully_rehashed_attack_count"] == 4
    assert audit["fully_rehashed_downstream_layer_identity_count"] == 20
    assert sum(len(item["fully_rehashed_downstream_layer_ids"]) for item in audit["controls"]) == 20
    assert not (output / "negative_controls").exists()


def test_gates_scope_and_transition(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    gates = _load(output / "gate_evaluation.json")
    scope = _load(output / "scope_boundary_audit.json")
    transition = _load(output / "prospective_transition.json")
    report = _load(output / "report.json")
    assert (gates["passed_count"], gates["failed_count"]) == (8, 0)
    assert scope["current_v211_authorization_consumed"] is False
    assert scope["new_online_authorizations"] == 0
    assert scope["provider_calls"] == scope["credential_lookups"] == 0
    assert scope["empirical_rows"] == scope["empirical_estimates"] == 0
    assert transition["next_stage"] == models.NEXT_STAGE
    assert transition["new_online_authorization_required_after_independent_audit"] is True
    assert report["decision"] == models.DECISION


def test_complete_byte_rebuild(built: tuple[Path, Path, tuple[str, str]], tmp_path: Path) -> None:
    repository, output, source_identity = built
    rebuilt = tmp_path / "rebuilt"
    subject.build(
        repository_root=repository,
        output_dir=rebuilt,
        external_review_path=REVIEW,
        source_identity=source_identity,
    )
    assert _files(rebuilt) == _files(output)
