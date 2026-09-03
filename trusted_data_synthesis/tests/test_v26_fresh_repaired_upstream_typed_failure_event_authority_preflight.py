# ruff: noqa: E501
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_typed_failure_exit_provenance_runtime as v216_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_preflight as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_runtime as runtime,
)

REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/9e9d0547-f85a-458d-b0ba-078d1b0135bb/pasted-text.txt"
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
    output = tmp_path_factory.mktemp("v26_217") / "build"
    subject.build(
        repository_root=repository,
        output_dir=output,
        external_review_path=REVIEW,
        source_identity=source_identity,
    )
    return repository, output, source_identity


def test_external_authority_and_v216_freeze(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    external = _load(output / "external_revision_authorization.json")
    freeze = _load(output / "v216_freeze.json")
    assert external["review_sha256"] == subject.REVIEW_SHA256
    assert external["review_byte_count"] == 14_940
    assert external["operator_directive_byte_count"] == 36
    assert (
        external["operator_directive_sha256"]
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert external["failed_at"] == (
        "UPSTREAM_FAILURE_OBSERVATION_SOURCE_AUTHORITY_AND_ARTIFACT_BACKING"
    )
    assert (freeze["formal_file_count"], freeze["formal_total_byte_count"]) == (
        50,
        1_038_367,
    )
    assert freeze["five_exit_ast_controls_retained"] is True
    assert freeze["unauthenticated_rethrow_attack_retained"] is True
    assert freeze["upstream_event_authority_failed"] is True
    assert freeze["v211_authorization_consumed"] is False


def test_exact_v209_exit_surface_contract_remains_ast_total(
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


def test_upstream_terminal_is_event_derived_and_domain_restricted(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    source_binding = _load(output / "upstream_event_source_binding.json")
    observation_binding = _load(output / "upstream_observation_binding.json")
    assert tuple(
        inspect.signature(runtime.ArtifactBackedUpstreamFailureObserver.observe_failure).parameters
    ) == ("self", "event")
    assert tuple(
        inspect.signature(
            runtime.BoundUpstreamInstrumentEventSource.emit_instrument_failure
        ).parameters
    ) == ("self", "source_job_id", "source_invocation_request_parent_id")
    assert source_binding["admitted_event_terminal_policy_items"][0][:2] == [
        "transport_instrument_failure",
        "instrument_failure",
    ]
    assert set(source_binding["forbidden_terminal_kinds"]) == set(
        models.FORBIDDEN_UPSTREAM_TERMINALS
    )
    assert "completed_qualified" in source_binding["forbidden_terminal_kinds"]
    assert source_binding["terminal_argument_allowed"] is False
    assert source_binding["reason_argument_allowed"] is False
    assert source_binding["source_event_id_argument_allowed"] is False
    assert observation_binding["observation_terminal_derived_from_event_kind"] is True
    assert observation_binding["event_and_observation_artifacts_required"] is True


def test_e2_event_observation_and_descriptors_are_durable_and_dispatch_bound(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    controls = _load(output / "exit_surface_execution_audit.json")["controls"]
    e2 = next(item for item in controls if item["expected_exit_code"] == "E2_authenticated_rethrow")
    proof = models.SourceExitProof.model_validate(e2["source_exit_proof"])
    assert proof.upstream_artifact_chain is not None
    chain = proof.upstream_artifact_chain
    assert chain.event.source_job_id == e2["failure_observation"]["job_id"]
    assert chain.event.source_invocation_request_parent_id == proof.dispatch_or_response_parent_id
    assert chain.observation.terminal_kind == "instrument_failure"
    assert (
        chain.observation.exception_reason_sha256
        == hashlib.sha256(models.UPSTREAM_FAILURE_REASON.encode("utf-8")).hexdigest()
    )
    event_path = output / chain.event_descriptor.relative_path
    event_descriptor_path = output / runtime._descriptor_file_relative(chain.event_descriptor)
    observation_path = output / chain.observation_descriptor.relative_path
    observation_descriptor_path = output / runtime._descriptor_file_relative(
        chain.observation_descriptor
    )
    assert event_path.read_bytes() == models.canonical_bytes(chain.event) + b"\n"
    assert (
        event_descriptor_path.read_bytes() == models.canonical_bytes(chain.event_descriptor) + b"\n"
    )
    assert observation_path.read_bytes() == models.canonical_bytes(chain.observation) + b"\n"
    assert observation_descriptor_path.read_bytes() == (
        models.canonical_bytes(chain.observation_descriptor) + b"\n"
    )
    assert chain.persistence_sequence == (
        "event",
        "event_descriptor",
        "observation",
        "observation_descriptor",
    )


def test_five_source_exits_terminalize_and_raw_embeds_artifact_chain(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "exit_surface_execution_audit.json")
    assert [
        (item["control_name"], item["expected_exit_code"], item["expected_terminal"])
        for item in audit["controls"]
    ] == [tuple(item) for item in models.EXIT_CONTROL_ITEMS]
    assert (
        audit["typed_failure_exit_count"],
        audit["positive_source_derived_upstream_event_count"],
        audit["positive_upstream_event_descriptor_count"],
        audit["positive_derived_upstream_observation_count"],
        audit["positive_upstream_observation_descriptor_count"],
        audit["positive_e2_embedded_artifact_chain_count"],
    ) == (5, 1, 1, 1, 1, 1)
    assert audit["persisted_layer_count"] == 25
    assert audit["exception_escape_count"] == audit["empirical_row_count"] == 0
    for control in audit["controls"]:
        raw = _load(output / control["persistence"]["raw_relative_path"])
        observation = models.TypedFailureObservation.model_validate(raw["failure_observation"])
        evidence = models.AuthenticatedTypedFailureEvidence.model_validate(
            raw["authenticated_evidence"]
        )
        decision = models.DerivedTerminalDecision.model_validate(raw["derived_terminal_decision"])
        assert observation.source_exit_proof.source_exit_id == decision.source_exit_id
        assert observation.invocation_record["typed_terminal"] == decision.terminal_kind
        assert observation.invocation_record["event_sequence"][-1] == "terminal_dispatch"
        assert evidence.failure_observation.observation_id == observation.observation_id
        if control["expected_exit_code"] == "E2_authenticated_rethrow":
            assert (
                raw["failure_observation"]["source_exit_proof"]["upstream_artifact_chain"]
                is not None
            )


def test_five_upstream_authority_attacks_reject_before_raw(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "negative_control_audit.json")
    assert {item["control_name"] for item in audit["controls"]} == {
        "completed_qualified_producer_mint_attempt",
        "registered_event_incompatible_outer_terminal",
        "caller_forged_source_event_id_full_rehash",
        "missing_upstream_event_artifact",
        "cross_event_cross_job_observation_substitution",
    }
    assert (
        audit["rejected_count"],
        audit["accepted_count"],
        audit["fully_rehashed_attack_count"],
        audit["fully_rehashed_downstream_layer_identity_count"],
        audit["runner_authority_append_count"],
        audit["raw_write_count"],
    ) == (5, 0, 2, 10, 0, 0)
    assert sum(len(item["fully_rehashed_downstream_layer_ids"]) for item in audit["controls"]) == 10
    assert not (output / "negative_controls").exists()
    assert not tuple(output.rglob("*.temporarily_absent"))


def test_runner_source_scope_gates_and_transition(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    runner_source = inspect.getsource(v216_runtime.ExitProvenanceRunner._invoke_current_state)
    terminalizer_source = inspect.getsource(
        runtime.ArtifactBackedExitProvenanceRunner._terminalize_actual_failure
    )
    transport_source = inspect.getsource(runtime.ExitTracingScriptedTransport.send)
    assert runner_source.count("except v209.TypedTransportFailure as error:") == 2
    assert transport_source.index("emit_instrument_failure") < transport_source.index(
        "super().send(effective)"
    )
    assert "_dispatch_parent(effective)" in transport_source
    assert terminalizer_source.index("require_for_runner(error)") < terminalizer_source.index(
        "record_from_runner(observation)"
    )
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
