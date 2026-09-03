# ruff: noqa: E501
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_typed_failure_exit_provenance_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_typed_failure_exit_provenance_preflight as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_typed_failure_exit_provenance_runtime as runtime,
)

REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/777e90eb-8079-4b3a-960d-b01af66a88ca/pasted-text.txt"
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
    output = tmp_path_factory.mktemp("v26_216") / "build"
    subject.build(
        repository_root=repository,
        output_dir=output,
        external_review_path=REVIEW,
        source_identity=source_identity,
    )
    return repository, output, source_identity


def test_external_authority_and_v215_freeze(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    external = _load(output / "external_revision_authorization.json")
    freeze = _load(output / "v215_freeze.json")
    assert external["review_sha256"] == subject.REVIEW_SHA256
    assert external["review_byte_count"] == 12_959
    assert external["operator_directive_byte_count"] == 36
    assert (
        external["operator_directive_sha256"]
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert external["failed_at"] == "ACTUAL_V209_TYPED_FAILURE_EXIT_SURFACE_PROVENANCE_CLOSURE"
    assert freeze["formal_file_count"] == 44
    assert freeze["four_direct_constructor_controls_retained"] is True
    assert freeze["complete_exit_surface_failed"] is True
    assert freeze["v211_authorization_consumed"] is False


def test_exact_v209_exit_surface_contract_is_ast_total(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    contract = _load(output / "typed_failure_exit_surface_contract.json")
    assert contract["exact_v209_source_sha256"] == (
        "4529523fc737f26801118cc5cf78b682f2e510c5f887ed0d14a60a5bd26d9b35"
    )
    assert (
        contract["typed_failure_exit_count"],
        contract["direct_constructor_exit_count"],
        contract["authenticated_rethrow_exit_count"],
    ) == (5, 4, 1)
    assert [item["exit_code"] for item in contract["exits"]] == [
        "E0_invalid_dispatch_chain",
        "E1_empty_queue",
        "E2_authenticated_rethrow",
        "E3_reasoning_key",
        "E4_non_object",
    ]
    assert [item["source_line"] for item in contract["exits"]] == [647, 652, 658, 819, 824]
    assert contract["constructor_string_count_is_authority"] is False
    assert contract["complete_ast_raise_enumeration_required"] is True


def test_runner_requires_source_exit_proof_before_authority_append(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    runner_source = inspect.getsource(runtime.ExitProvenanceRunner._invoke_current_state)
    terminalizer_source = inspect.getsource(
        runtime.ExitProvenanceRunner._terminalize_actual_failure
    )
    transport_source = inspect.getsource(runtime.ExitTracingScriptedTransport.send)
    dispatcher_parameters = tuple(
        inspect.signature(runtime.ExitProvenanceDispatcher.dispatch).parameters
    )
    binding = _load(output / "runner_observation_binding.json")
    assert runner_source.count("except v209.TypedTransportFailure as error:") == 2
    assert "record_transport_exit" in transport_source
    assert "require_for_runner(error)" in terminalizer_source
    assert terminalizer_source.index("require_for_runner(error)") < terminalizer_source.index(
        "record_from_runner(observation)"
    )
    assert dispatcher_parameters == ("self", "evidence")
    assert binding["exact_exit_proof_required_before_runner_authority"] is True
    assert binding["unauthenticated_rethrow_rejected_before_runner_authority"] is True


def test_five_source_exits_terminalize_and_persist(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "exit_surface_execution_audit.json")
    assert [
        (item["control_name"], item["expected_exit_code"], item["expected_terminal"])
        for item in audit["controls"]
    ] == [tuple(item) for item in models.EXIT_CONTROL_ITEMS]
    assert audit["typed_failure_exit_count"] == 5
    assert audit["direct_constructor_control_count"] == 4
    assert audit["authenticated_rethrow_control_count"] == 1
    assert audit["runner_owned_observation_count"] == 5
    assert audit["consumer_terminal_branch_count"] == 5
    assert audit["exact_exit_terminal_match_count"] == 5
    assert audit["persisted_layer_count"] == 25
    assert audit["exception_escape_count"] == 0
    proofs = [item["source_exit_proof"] for item in audit["controls"]]
    assert sum(item["source_exit_kind"] == "authenticated_rethrow" for item in proofs) == 1
    assert sum(item["upstream_failure_observation_id"] is not None for item in proofs) == 1


def test_raw_binds_exact_source_proof_observation_record_and_decision(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    for control in _load(output / "exit_surface_execution_audit.json")["controls"]:
        raw = _load(output / control["persistence"]["raw_relative_path"])
        observation = models.TypedFailureObservation.model_validate(raw["failure_observation"])
        evidence = models.AuthenticatedTypedFailureEvidence.model_validate(
            raw["authenticated_evidence"]
        )
        decision = models.DerivedTerminalDecision.model_validate(raw["derived_terminal_decision"])
        proof = observation.source_exit_proof
        record = observation.invocation_record
        assert observation.runner_owned is True
        assert observation.source_exit_admitted is True
        assert proof.source_exit_id == decision.source_exit_id
        assert proof.source_exit_kind == decision.source_exit_kind
        assert proof.terminal_kind == observation.caught_terminal_kind == decision.terminal_kind
        assert record["typed_terminal"] == decision.terminal_kind
        assert record["event_sequence"][-1] == "terminal_dispatch"
        assert evidence.failure_observation.observation_id == observation.observation_id


def test_unauthenticated_rethrow_and_retained_fully_rehashed_attacks_reject(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "negative_control_audit.json")
    assert {item["control_name"] for item in audit["controls"]} == {
        "registered_terminal_rethrow_without_upstream_authority",
        "unregistered_terminal_rethrow",
        "nonregistered_exact_class_spoof",
        "instrument_observation_reclassified_as_provider_identity",
        "privacy_observation_reclassified_as_transport",
        "exception_reason_hash_replaced",
        "cross_job_failure_observation_substituted",
    }
    assert (
        audit["rejected_count"],
        audit["accepted_count"],
        audit["unauthenticated_registered_rethrow_rejection_count"],
        audit["additional_source_admission_rejection_count"],
        audit["retained_authority_attack_count"],
        audit["runner_authority_append_count"],
        audit["raw_write_count"],
    ) == (7, 0, 1, 2, 4, 0, 0)
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
