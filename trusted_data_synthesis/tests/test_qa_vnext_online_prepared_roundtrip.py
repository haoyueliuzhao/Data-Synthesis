"""Real zero-network preparation/readback; only Git/design inputs are isolated."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import runner
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    identity,
    read_json,
    record,
    sha,
)

ROOT = Path(__file__).resolve().parents[2]


def test_real_prepare_readback_handles_registry_tuples_and_rejects_bool_int_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No _prepared/panel/control/software/tokenizer mock hides serialization bugs."""
    calls = {"source_snapshot": 0, "source_verification": 0, "credential": 0, "network": 0}

    def no_network(*args: Any, **kwargs: Any) -> Any:
        calls["network"] += 1
        raise AssertionError("the preparation round-trip must not make a network request")

    def no_credential(*args: Any, **kwargs: Any) -> Any:
        calls["credential"] += 1
        raise AssertionError("the preparation round-trip must not read a credential")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(runner, "_credential", no_credential)
    isolated_source = record(
        "implementation",
        source_commit="a" * 40,
        source_tree="b" * 40,
        members=[],
        every_python_source_bound=True,
        isolated_test_git_input_not_an_actual_source_commit=True,
    )

    def source_snapshot(root: Path) -> dict[str, Any]:
        assert root == ROOT.resolve()
        calls["source_snapshot"] += 1
        return isolated_source

    def source_verification(root: Path, implementation: dict[str, Any]) -> None:
        assert root == ROOT.resolve()
        identity(implementation, "implementation")
        assert implementation == isolated_source
        calls["source_verification"] += 1

    monkeypatch.setattr(runner, "source_snapshot", source_snapshot)
    monkeypatch.setattr(runner, "verify_source_snapshot", source_verification)
    design = b"Isolated local preparation/readback control; no online population is launched.\n"
    design_path = tmp_path / "isolated_design.txt"
    design_path.write_bytes(design)
    monkeypatch.setattr(runner, "DESIGN_BYTES", len(design))
    monkeypatch.setattr(runner, "DESIGN_SHA256", sha(design))
    directory = tmp_path / "preparation"

    # These are the real public preparation function and its real persisted loader.
    report = runner.prepare(ROOT, directory, design_path, run_tag="isolated-readback-control")
    prepared = runner._prepared(ROOT, directory)
    assert prepared["report"] == report
    assert report["prepared"] is True and report["provider_attempts"] == 0
    assert len(prepared["registrations"]) == 12
    assert prepared["report"]["execution_directory"] == str(tmp_path / "execution")
    assert not (tmp_path / "execution").exists()
    assert prepared["software"] == runner._software()
    assert prepared["tokenizer_binding"]["member_count"] == 5
    assert prepared["tokenizer_binding"]["maximum_sequence_length"] == 24_576
    assert prepared["tokenizer_binding"]["language_model_loaded"] is False

    parsed_condition = read_json((directory / "condition.json").read_bytes())
    current_context = prepared["panel"].adapter("C").context
    parsed_context = parsed_condition["task_contexts"]["C"]
    live_invariants = current_context["catalog_resolution"]["registry_manifest"][0][
        "invariant_checks"
    ]
    saved_invariants = parsed_context["catalog_resolution"]["registry_manifest"][0][
        "invariant_checks"
    ]
    assert isinstance(live_invariants, tuple) and isinstance(saved_invariants, list)
    assert current_context != parsed_context
    assert canonical_json_bytes(current_context) == canonical_json_bytes(parsed_context)
    controls = read_json((directory / "controls/report.json").read_bytes())
    assert controls["id"] == report["controls_id"]
    assert controls["passed"] is True and controls["control_count"] == 4
    assert controls["provider_attempts"] == controls["population_sessions"] == 0
    assert controls["mock_attempts"] > 0 and controls["exported_candidates"] == 0
    assert controls["maximum_actual_http_body_bytes"] <= 98_304
    assert controls["maximum_input_admission_proxy"] <= 99_328
    assert calls == {"source_snapshot": 1, "source_verification": 1, "credential": 0, "network": 0}

    # A same-ID bool->int edit is equal under Python's loose equality, but it is
    # not the frozen JSON condition. Re-sealing only this temporary manifest
    # ensures the population guard, not an unrelated member hash, rejects it.
    altered = dict(parsed_condition)
    altered["autonomous_planning"] = 0
    assert altered == parsed_condition
    assert canonical_json_bytes(altered) != canonical_json_bytes(parsed_condition)
    (directory / "condition.json").write_bytes(canonical_json_bytes(altered))
    manifest = read_json((directory / "manifest.json").read_bytes())
    members = [
        {
            "path": path.relative_to(directory).as_posix(),
            "bytes": len(path.read_bytes()),
            "sha256": sha(path.read_bytes()),
        }
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path != directory / "manifest.json"
    ]
    resealed = record(
        "preparation_manifest",
        **{
            key: value
            for key, value in manifest.items()
            if key not in {"id", "schema_version", "members"}
        },
        members=members,
    )
    (directory / "manifest.json").write_bytes(canonical_json_bytes(resealed))
    with pytest.raises(ProtocolError, match="run.frozen_population"):
        runner._prepared(ROOT, directory)
    assert calls["source_verification"] == 2
    assert calls["credential"] == calls["network"] == 0
    assert not (tmp_path / "execution").exists()
