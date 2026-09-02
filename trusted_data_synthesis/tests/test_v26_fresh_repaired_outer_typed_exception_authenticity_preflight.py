# ruff: noqa: E501
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_outer_typed_exception_authenticity_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_outer_typed_exception_authenticity_preflight as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_outer_typed_exception_authenticity_runtime as runtime,
)

REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/e60e678f-e3c8-4804-9710-c11570892cf9/pasted-text.txt"
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
    output = tmp_path_factory.mktemp("v26_214") / "build"
    subject.build(
        repository_root=repository,
        output_dir=output,
        external_review_path=REVIEW,
        source_identity=source_identity,
    )
    return repository, output, source_identity


def test_external_authority_and_v213_freeze(built: tuple[Path, Path, tuple[str, str]]) -> None:
    _, output, _ = built
    external = _load(output / "external_revision_authorization.json")
    freeze = _load(output / "v213_freeze.json")
    assert external["review_sha256"] == subject.REVIEW_SHA256
    assert external["review_byte_count"] == 14653
    assert external["operator_directive_byte_count"] == 30
    assert (
        external["operator_directive_sha256"]
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert freeze["formal_file_count"] == 1058
    assert freeze["completed_main_path_retained"] is True
    assert freeze["parser_reference_bound_paths_retained"] is True
    assert freeze["outer_typed_exception_authenticity_failed"] is True
    assert freeze["v211_authorization_consumed"] is False


def test_runner_catch_and_dispatcher_expose_no_subtype_terminal_input(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    parameters = tuple(
        inspect.signature(runtime.AuthenticTypedFailureDispatcher.dispatch).parameters
    )
    runner_source = inspect.getsource(
        runtime.ObservationAuthenticFullConditionRunner._invoke_current_state
    )
    build_source = inspect.getsource(subject.build)
    binding = _load(output / "authentic_dispatcher_binding.json")
    assert parameters == ("self", "evidence")
    assert "except v209.TypedTransportFailure as error:" in runner_source
    assert "record_from_runner(observation)" in runner_source
    assert build_source.count("consumer.execute_preflight(") == 1
    assert binding["dispatcher_input"] == "AuthenticatedTypedFailureEvidence"
    assert binding["terminal_from_observation_not_subtype"] is True
    assert binding["terminal_kind_input_allowed"] is False
    assert not hasattr(models, "ProviderIdentityFailureEvidence")
    assert not hasattr(models, "TransportFailureEvidence")


def test_single_consumer_terminalizes_eight_actual_runner_failures(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "failure_execution_audit.json")
    assert audit["actual_runner_invocation_count"] == 8
    assert audit["runner_catch_observation_count"] == 8
    assert audit["terminal_branch_count"] == 8
    assert audit["exact_terminal_match_count"] == 8
    assert audit["persisted_layer_count"] == 40
    assert audit["distinct_exception_class_count"] == 8
    assert audit["distinct_terminal_count"] == 8
    assert audit["caller_selected_evidence_subtype_count"] == 0
    assert audit["build_level_failure_join_count"] == 0
    assert audit["exception_escape_count"] == 0


def test_raw_embeds_runner_observation_and_exact_invocation_record(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    control = _load(output / "failure_execution_audit.json")["controls"][0]
    descriptor = control["persistence"]
    raw = _load(output / descriptor["raw_relative_path"])
    observation = models.TypedFailureObservation.model_validate(raw["failure_observation"])
    evidence = models.AuthenticatedTypedFailureEvidence.model_validate(
        raw["authenticated_evidence"]
    )
    decision = models.DerivedTerminalDecision.model_validate(raw["derived_terminal_decision"])
    record = observation.invocation_record
    assert observation.runner_owned is True
    assert observation.constructed_inside_runner_catch is True
    assert record["invocation_id"] == observation.invocation_id
    assert record["job_id"] == observation.job_id
    assert record["typed_terminal"] == observation.caught_terminal_kind
    assert record["event_sequence"][-1] == "terminal_dispatch"
    assert evidence.failure_observation.observation_id == observation.observation_id
    assert decision.observation_id == observation.observation_id
    assert decision.terminal_kind == observation.caught_terminal_kind


def test_all_outer_terminals_derive_from_one_authenticated_evidence_type(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    controls = _load(output / "failure_execution_audit.json")["controls"]
    assert [item["expected_terminal"] for item in controls] == list(models.OUTER_TERMINAL_KINDS)
    assert {item["evidence"]["evidence_kind"] for item in controls} == {
        "runner_owned_typed_failure"
    }
    assert {item["failure_observation"]["caught_exception_class"] for item in controls} == {
        name for name, _terminal in models.EXCEPTION_TERMINAL_ITEMS
    }
    assert all(
        item["decision"]["terminal_kind"]
        == item["failure_observation"]["invocation_record"]["typed_terminal"]
        for item in controls
    )


def test_four_fully_rehashed_attacks_reject_before_raw(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "negative_control_audit.json")
    assert {item["control_name"] for item in audit["controls"]} == {
        "instrument_record_as_provider_identity",
        "provider_identity_record_as_transport",
        "exception_reason_hash_replaced",
        "cross_job_failure_observation_substituted",
    }
    assert (audit["rejected_count"], audit["accepted_count"], audit["raw_write_count"]) == (
        4,
        0,
        0,
    )
    assert audit["fully_rehashed_attack_count"] == 4
    assert audit["fully_rehashed_downstream_layer_identity_count"] == 20
    assert sum(len(item["fully_rehashed_downstream_layer_ids"]) for item in audit["controls"]) == 20
    assert not (output / "negative_controls").exists()


def test_gates_scope_and_transition(built: tuple[Path, Path, tuple[str, str]]) -> None:
    _, output, _ = built
    gates = _load(output / "gate_evaluation.json")
    scope = _load(output / "scope_boundary_audit.json")
    transition = _load(output / "prospective_transition.json")
    assert (gates["passed_count"], gates["failed_count"]) == (8, 0)
    assert scope["current_v211_authorization_consumed"] is False
    assert scope["provider_calls"] == scope["credential_lookups"] == scope["empirical_rows"] == 0
    assert transition["next_stage"] == models.NEXT_STAGE
    assert transition["new_online_authorization_required_after_independent_audit"] is True


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
