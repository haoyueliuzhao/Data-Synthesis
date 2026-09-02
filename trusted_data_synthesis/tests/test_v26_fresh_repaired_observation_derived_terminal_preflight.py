# ruff: noqa: E501
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_observation_derived_terminal_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_observation_derived_terminal_preflight as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_observation_derived_terminal_runtime as runtime,
)

REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/cddd0646-f6fb-4086-be08-34edbeab56cf/pasted-text.txt"
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
    output = tmp_path_factory.mktemp("v26_213") / "build"
    subject.build(
        repository_root=repository,
        output_dir=output,
        external_review_path=REVIEW,
        source_identity=source_identity,
    )
    return repository, output, source_identity


def test_external_authority_and_v212_freeze(built: tuple[Path, Path, tuple[str, str]]) -> None:
    _, output, _ = built
    external = _load(output / "external_revision_authorization.json")
    freeze = _load(output / "v212_freeze.json")
    assert external["review_sha256"] == subject.REVIEW_SHA256
    assert (
        external["operator_directive_sha256"]
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert freeze["formal_file_count"] == 1067
    assert freeze["durable_ingress_retained"] is True
    assert freeze["terminal_label_controls_diagnostic_only"] is True
    assert freeze["v211_authorization_consumed"] is False


def test_dispatcher_api_has_observed_evidence_only(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    parameters = tuple(
        inspect.signature(runtime.ObservationDerivedTerminalDispatcher.dispatch).parameters
    )
    build_source = inspect.getsource(subject.build)
    binding = _load(output / "observation_derived_dispatcher_binding.json")
    assert parameters == ("self", "evidence")
    assert build_source.count("consumer.execute_preflight(") == 1
    assert "_execute_manifest_main_path(" not in build_source
    assert "_diagnostic_evidences(" not in build_source
    assert len(binding["evidence_kinds"]) == 13
    assert binding["terminal_kind_input_allowed"] is False
    assert binding["expected_terminal_input_allowed"] is False
    assert binding["terminal_kinds"] == list(models.TERMINAL_KINDS)


def test_single_consumer_executes_runner_terminal_persistence_chain(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "single_consumer_execution_audit.json")
    assert audit["exact_job_count"] == 192
    assert audit["actual_runner_invocation_count"] == 792
    assert audit["injected_transport_dispatch_count"] == 792
    assert audit["completed_runner_evidence_count"] == 192
    assert audit["observation_derived_completed_qualified_count"] == 192
    assert audit["raw_result_trace_outcome_checkpoint_count"] == 960
    assert audit["build_level_terminal_join_count"] == 0
    assert audit["caller_terminal_argument_count"] == 0


def test_raw_embeds_actual_final_and_derived_terminal(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    descriptor = _load(output / "single_consumer_execution_audit.json")["descriptors"][0]
    raw = _load(output / descriptor["raw_relative_path"])
    evidence = models.CompletedRunnerEvidence.model_validate(raw["observed_evidence"])
    decision = models.DerivedTerminalDecision.model_validate(raw["derived_terminal_decision"])
    assert evidence.final_result["result_id"] == evidence.final_result_id
    assert evidence.qualified_valid is True
    assert evidence.qualified_valid == (evidence.base_valid and evidence.mechanism_valid)
    assert evidence.invocation_records[-1]["phase"] == "final"
    assert decision.evidence_id == evidence.evidence_id
    assert decision.terminal_kind == "completed_qualified"


def test_sixteen_terminals_are_triggered_by_evidence(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "terminal_evidence_audit.json")
    controls = audit["controls"]
    assert [item["expected_terminal"] for item in controls] == list(models.TERMINAL_KINDS)
    assert len({item["observed_evidence"]["evidence_kind"] for item in controls}) == 13
    assert audit["exact_derived_terminal_match_count"] == 16
    assert audit["label_only_control_count"] == 0
    assert audit["caller_terminal_argument_count"] == 0
    assert all(item["expected_terminal_passed_to_dispatcher"] is False for item in controls)


def test_provenance_negative_controls_reject_before_raw(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "negative_control_audit.json")
    assert {item["control_name"] for item in audit["controls"]} == {
        "caller_terminal_argument_absent",
        "qualified_runner_evidence_relabel",
        "cross_job_terminal_decision_substitution",
        "completed_invalid_factorization_inconsistent_with_final",
    }
    assert (audit["rejected_count"], audit["accepted_count"], audit["raw_write_count"]) == (
        4,
        0,
        0,
    )
    assert audit["fully_rehashed_downstream_attack_count"] == 2
    assert sum(len(item["fully_rehashed_downstream_layer_ids"]) for item in audit["controls"]) == 10
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
