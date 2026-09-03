# ruff: noqa: E501
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.task import fresh_artifact_backed_outcome_authority as outcome_authority
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_terminal_domain_exact_registry_complement_preflight as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_upstream_typed_failure_event_authority_models as v217_models,
)

REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/3ac55d98-0d2c-4150-9562-2976e8c811ef/pasted-text.txt"
)
FORMAL = Path(subject.OUTPUT_DIR)
RUNTIME_PREFIXES = (
    "consumer_ingress/",
    "exit_surface_controls/",
    "upstream_event_descriptors/",
    "upstream_events/",
    "upstream_observation_descriptors/",
    "upstream_observations/",
)


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
    output = tmp_path_factory.mktemp("v26_218") / "build"
    subject.build(
        repository_root=repository,
        output_dir=output,
        external_review_path=REVIEW,
        source_identity=source_identity,
    )
    return repository, output, source_identity


def test_external_authority_and_exact_v217_freeze(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    external = _load(output / "external_revision_authorization.json")
    freeze = _load(output / "v217_freeze.json")
    assert external["review_sha256"] == subject.REVIEW_SHA256
    assert external["review_byte_count"] == 14_305
    assert external["operator_directive_byte_count"] == 36
    assert (
        external["operator_directive_sha256"]
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert external["audit_result"] == (
        "VALID_SCOPED_CALLER_LABEL_REMOVAL_AND_ARTIFACT_BACKED_E2_CHAIN"
    )
    assert external["failed_at"] == "EXACT_V195_REACHABLE_TERMINAL_COMPLEMENT_BINDING"
    assert (freeze["formal_file_count"], freeze["formal_total_byte_count"]) == (
        59,
        1_075_394,
    )
    assert (freeze["manifest_member_count"], freeze["manifest_member_byte_count"]) == (
        58,
        1_064_349,
    )
    assert freeze["caller_label_removal_retained"] is True
    assert freeze["artifact_backed_e2_chain_retained"] is True
    assert freeze["exact_registry_complement_failed"] is True
    assert freeze["v211_authorization_consumed"] is False


def test_terminal_partition_is_derived_from_exact_v195_registry(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    repository, output, _ = built
    binding = _load(output / "exact_registry_complement_binding.json")
    registry = outcome_authority.FreshTerminalRegistry.model_validate(
        _load(repository / subject.v217_preflight.V195_DIR / "fresh_terminal_registry.json")
    )
    actual_reachable = tuple(
        sorted(
            (item.terminal_kind, item.policy_id)
            for item in registry.policies
            if item.registration_status == "reachable"
        )
    )
    admitted = tuple(binding["admitted_terminal_kinds"])
    forbidden = tuple(binding["forbidden_terminal_kinds"])
    assert binding["exact_v195_terminal_registry_id"] == registry.registry_id
    assert (
        tuple(tuple(item) for item in binding["reachable_terminal_policy_items"])
        == actual_reachable
    )
    assert admitted == ("instrument_failure",)
    assert forbidden == tuple(sorted({item[0] for item in actual_reachable} - set(admitted)))
    assert (len(actual_reachable), len(admitted), len(forbidden)) == (16, 1, 15)
    assert set(admitted) | set(forbidden) == {item[0] for item in actual_reachable}
    assert not set(admitted) & set(forbidden)
    assert binding["forbidden_derived_from_registry"] is True
    assert binding["handwritten_forbidden_set_is_authority"] is False


def test_exact_correct_names_are_included_and_old_misspellings_excluded(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    binding = _load(output / "exact_registry_complement_binding.json")
    forbidden = set(binding["forbidden_terminal_kinds"])
    assert "provider_failure_no_payload" in forbidden
    assert "resource_budget_exhausted" in forbidden
    assert "provider_no_payload_failure" not in forbidden
    assert "resource_failure" not in forbidden
    complement_source = inspect.getsource(subject._complement_binding)
    assert "reachable_terminal_policy_items" in complement_source
    assert "FORBIDDEN_UPSTREAM_TERMINALS" not in complement_source
    assert "reachable_kinds - set(admitted)" in complement_source


def test_v217_execution_and_35_runtime_files_are_retained_byte_exact(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    repository, output, _ = built
    retained = _load(output / "retained_execution_audit.json")
    v217_root = repository / subject.V217_DIR
    v217_execution = _load(v217_root / "exit_surface_execution_audit.json")
    assert retained["v217_execution"] == v217_execution
    assert retained["exact_v217_execution_object_match"] is True
    assert (
        retained["retained_runtime_file_byte_match_count"],
        retained["retained_source_exit_controls"],
        retained["retained_persisted_layers"],
        retained["retained_upstream_artifact_files"],
    ) == (35, 5, 25, 8)
    runtime_files = {
        name: payload
        for name, payload in _files(output).items()
        if name.startswith(RUNTIME_PREFIXES)
    }
    assert len(runtime_files) == 35
    for name, payload in runtime_files.items():
        assert payload == (v217_root / name).read_bytes()


def test_retained_e2_artifact_chain_and_five_layer_terminalization(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = v217_models.ExitSurfaceExecutionAudit.model_validate(
        _load(output / "retained_execution_audit.json")["v217_execution"]
    )
    assert audit.typed_failure_exit_count == 5
    assert audit.persisted_layer_count == 25
    assert audit.positive_source_derived_upstream_event_count == 1
    assert audit.positive_upstream_event_descriptor_count == 1
    assert audit.positive_derived_upstream_observation_count == 1
    assert audit.positive_upstream_observation_descriptor_count == 1
    assert audit.positive_e2_embedded_artifact_chain_count == 1
    assert audit.exception_escape_count == audit.empirical_row_count == audit.provider_calls == 0
    e2 = next(
        item for item in audit.controls if item.expected_exit_code == "E2_authenticated_rethrow"
    )
    chain = e2.source_exit_proof.upstream_artifact_chain
    assert chain is not None
    assert chain.event.source_job_id == e2.failure_observation.job_id
    assert chain.event.source_invocation_request_parent_id == (
        e2.source_exit_proof.dispatch_or_response_parent_id
    )
    assert chain.observation.terminal_kind == "instrument_failure"


def test_same_length_four_parent_full_rehash_attack_rejects_at_registry_admission(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    binding = _load(output / "exact_registry_complement_binding.json")
    composition = _load(output / "composition_contract.json")
    gates = _load(output / "gate_evaluation.json")
    report = _load(output / "report.json")
    negative = _load(output / "registry_complement_negative_control_audit.json")
    control = negative["control"]
    assert control["candidate_forbidden_count"] == 15
    assert control["expected_missing_terminal_kinds"] == [
        "provider_failure_no_payload",
        "resource_budget_exhausted",
    ]
    assert control["injected_non_registry_terminal_kinds"] == [
        "provider_no_payload_failure",
        "resource_failure",
    ]
    assert control["fully_rehashed_object_count"] == 4
    assert control["rejected"] is True
    assert control["rejection_stage"] == "registry_complement_admission"
    assert control["candidate_binding_id"] != binding["binding_id"]
    assert control["candidate_composition_id"] != composition["contract_id"]
    assert control["candidate_gate_id"] not in {item["gate_id"] for item in gates["gates"]}
    assert control["candidate_report_id"] != report["report_id"]
    assert (negative["rejected_count"], negative["accepted_count"]) == (1, 0)
    assert not (output / "negative_controls").exists()


def test_noncompensatory_gates_scope_and_transition(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    gates = _load(output / "gate_evaluation.json")
    scope = _load(output / "scope_boundary_audit.json")
    decision = _load(output / "decision.json")
    transition = _load(output / "prospective_transition.json")
    report = _load(output / "report.json")
    assert (gates["passed_count"], gates["failed_count"]) == (8, 0)
    assert len(gates["gates"]) == 8
    assert scope["current_v211_authorization_consumed"] is False
    assert scope["new_online_authorizations"] == 0
    assert scope["provider_calls"] == scope["provider_client_constructions"] == 0
    assert scope["credential_lookups"] == 0
    assert scope["empirical_rows"] == scope["empirical_estimates"] == 0
    assert decision["decision"] == models.DECISION
    assert transition["next_stage"] == models.NEXT_STAGE
    assert transition["provider_execution_authorized"] is False
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
