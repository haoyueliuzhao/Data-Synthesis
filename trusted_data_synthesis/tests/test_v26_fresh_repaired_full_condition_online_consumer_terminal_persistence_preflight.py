# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_online_consumer_terminal_persistence_preflight as subject,
)

REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/98c5ae41-4bff-4078-b58d-baed13a438ff/pasted-text.txt"
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
    output = tmp_path_factory.mktemp("v26_212") / "build"
    subject.build(
        repository_root=repository,
        output_dir=output,
        external_review_path=REVIEW,
        source_identity=source_identity,
    )
    return repository, output, source_identity


def test_external_authority_and_v211_freeze(built: tuple[Path, Path, tuple[str, str]]) -> None:
    _, output, _ = built
    external = _load(output / "external_repair_authorization.json")
    freeze = _load(output / "v211_freeze.json")
    assert external["review_sha256"] == subject.REVIEW_SHA256
    assert (
        external["operator_directive_sha256"]
        == hashlib.sha256(subject.OPERATOR_DIRECTIVE.encode("utf-8")).hexdigest()
    )
    assert freeze["formal_file_count"] == 17
    assert freeze["v211_authorization_consumed"] is False
    modified = output.parent / "modified_review.txt"
    modified.write_bytes(REVIEW.read_bytes() + b"\n")
    with pytest.raises(subject.V212Error, match="external review bytes differ"):
        subject._external_authorization(modified)


def test_source_bound_repair_parent_chain(built: tuple[Path, Path, tuple[str, str]]) -> None:
    _, output, _ = built
    implementation = _load(output / "implementation_binding.json")
    consumer = _load(output / "online_execution_consumer_implementation_binding.json")
    assert len(implementation["files"]) == 4
    assert len(implementation["symbols"]) == 11
    assert implementation["provider_network_symbols"] == 0
    assert implementation["credential_environment_symbols"] == 0
    assert (
        len(
            {
                consumer["consumption_contract_id"],
                consumer["run_start_contract_id"],
                consumer["provider_transport_binding_id"],
                consumer["terminal_registry_dispatcher_binding_id"],
                consumer["raw_result_writer_binding_id"],
                consumer["trace_outcome_checkpoint_binding_id"],
            }
        )
        == 6
    )


def test_durable_ingress_order_controls(built: tuple[Path, Path, tuple[str, str]]) -> None:
    _, output, _ = built
    audit = _load(output / "ingress_order_audit.json")
    controls = {item["control_name"]: item for item in audit["controls"]}
    assert set(controls) == {
        "exact_legal_order",
        "factory_before_consumption",
        "factory_before_run_start_receipt",
        "second_consumption",
    }
    assert controls["exact_legal_order"]["admitted"] is True
    assert all(item["rejected"] for name, item in controls.items() if name != "exact_legal_order")
    assert sum(item["credential_boundary_probe_count"] for item in controls.values()) == 1
    assert (output / "control_ingress/authorization_consumption_receipt.json").is_file()
    assert (output / "control_ingress/run_start_receipt.json").is_file()


def test_exact_v209_runner_and_192_job_persistence(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    audit = _load(output / "scripted_persistence_audit.json")
    assert audit["exact_job_count"] == 192
    assert audit["v209_invocation_count"] == 792
    assert audit["transport_dispatch_count"] == 792
    assert audit["actual_byte_match_count"] == 960
    assert len(audit["records"]) == 192
    assert {tuple(item["persistence_sequence"]) for item in audit["records"]} == {
        ("raw", "result", "trace", "outcome", "checkpoint")
    }


def test_actual_persisted_bytes_are_manifested(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    manifest = models.ArtifactManifest.model_validate(_load(output / "artifact_manifest.json"))
    members = {item.relative_path: item for item in manifest.members}
    for record in _load(output / "scripted_persistence_audit.json")["records"]:
        for layer in ("raw", "result", "trace", "outcome", "checkpoint"):
            relative = record[f"{layer}_relative_path"]
            payload = (output / relative).read_bytes()
            assert hashlib.sha256(payload).hexdigest() == record[f"{layer}_sha256"]
            assert members[relative].sha256 == record[f"{layer}_sha256"]


def test_complete_reachable_terminal_persistence(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    binding = _load(output / "terminal_registry_dispatcher_binding.json")
    audit = _load(output / "terminal_persistence_audit.json")
    assert tuple(binding["terminal_kinds"]) == models.TERMINAL_KINDS
    assert tuple(item["terminal_kind"] for item in audit["controls"]) == models.TERMINAL_KINDS
    assert audit["raw_result_trace_outcome_checkpoint_count"] == 80
    assert audit["exception_escape_count"] == 0


def test_mutations_gates_and_scope_boundary(
    built: tuple[Path, Path, tuple[str, str]],
) -> None:
    _, output, _ = built
    mutation = _load(output / "source_mutation_audit.json")
    gates = _load(output / "gate_evaluation.json")
    scope = _load(output / "scope_boundary_audit.json")
    transition = _load(output / "prospective_transition.json")
    assert (mutation["attack_count"], mutation["rejected_count"], mutation["accepted_count"]) == (
        7,
        7,
        0,
    )
    assert (gates["passed_count"], gates["failed_count"]) == (7, 0)
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
