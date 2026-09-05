"""Read/rebuild the one actual run without dispatching any new candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import (
    FixedFixtureRuntimeError,
)
from trusted_synthesis.experiments.qa_reasoning_part_whole_share import models, preflight, runtime
from trusted_synthesis.experiments.qa_reasoning_source_distinct_support import source as old_source

ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / (
    "trusted_data_synthesis/artifacts/qa_reasoning_part_whole_share/"
    "finance_qa_vnext_part_whole_share_dual_support_preflight_v1_20260905"
)
COMMIT = "b6783ac6676c6b821ab819f9215961fbd0605e84"
TREE = "475ff81d9e26d9424c1f6942de5cf7eb5cda1fb2"


def read(name: str) -> dict[str, Any]:
    return json.loads((FORMAL / (name + ".json")).read_bytes())


def test_exact_new_review_and_preserved_parent_science() -> None:
    review = (FORMAL / "external_review.txt").read_bytes()
    assert len(review) == 22925 and hashlib.sha256(review).hexdigest() == models.REVIEW_SHA256
    assert preflight.authorize(review) == read("authorization")
    with pytest.raises(models.ShareError):
        preflight.authorize(review + b"\n")
    parent = json.loads((ROOT / models.PARENT / "decision.json").read_bytes())
    assert parent["status"] == "source_not_instantiated" and parent["scientific_witness"] is None
    assert read("decision")["old_compound_task_W"] is None
    assert read("predecessor_freeze")["original_gate_partition"] == [3, 0, 1, 1]


def test_new_task_keeps_one_visible_universe_and_common_obligations() -> None:
    source, contract, family = read("source_binding"), read("contract"), read("candidate_family")
    assert contract["task"]["is_new_task"]
    assert contract["task"]["period"] == "2015"
    assert contract["task"]["currency"] == "dollar_as_disclosed"
    assert contract["task"]["evidence_universe_ids"] == sorted(
        e["id"] for e in source["evidence"].values()
    )
    assert [d["route"] for d in family["candidates"]] == ["D", "S"]
    assert [len(d["nodes"]) for d in family["candidates"]] == [2, 3]
    assert len({d["task_id"] for d in family["candidates"]}) == 1
    assert contract["shared_obligations"] == [
        "period_scope",
        "numerator_denominator",
        "percent_unit",
        "final_grounding",
    ]
    assert contract["route_specific_preconditions"]["D"] == []
    assert contract["route_specific_preconditions"]["S"]


def test_registration_is_durable_before_original_executions() -> None:
    registration = read("registration_receipt")
    assert registration["before_candidate_execution"] and registration["runtime_limit"] == 2
    events = registration["write_events"]
    paths = {e["relative_path"] for e in events}
    assert all(not p.startswith("runtime/") for p in paths)
    for name in ("source_binding.json", "contract.json", "candidate_family.json"):
        assert any(e["kind"] == "file_fsync" and e["relative_path"] == name for e in events)
        assert any(e["kind"] == "directory_fsync" and e["relative_path"] == name for e in events)
    assert (
        registration["measurement_rule_sha256"]
        == hashlib.sha256((FORMAL / "contract.json").read_bytes()).hexdigest()
    )


def test_local_contract_preserves_heterogeneous_source_metrics() -> None:
    source, contract = read("source_binding"), read("contract")
    evidence = source["evidence"]
    assert len({evidence[k]["metric"] for k in ("freight", "other", "total")}) == 3
    op = contract["operations"]["relation_sum"]
    assert op["parameters"] == {"method": "sum"}
    assert op["raw_evidence_metadata_rewriting_permitted"] is False
    assert op["disclosed_total_value_read_by_executor"] is False
    assert contract["old_registry_modified"] is False
    assert contract["numeric"] == {
        "precision": 50,
        "rounding": "ROUND_HALF_EVEN",
        "final_quantum": "0.000001",
        "source_reconciliation_tolerance": "0",
        "answer_tolerance": "0",
    }


def test_authoritative_formal_geometry_and_all_manifest_bytes() -> None:
    actual = files_at(FORMAL)
    manifest = read("artifact_manifest")
    assert len(actual) == 65 and sum(map(len, actual.values())) == 254479
    validate_manifest(actual, manifest["manifest_id"], manifest["artifact_root"])
    assert manifest["member_count"] == 64


def test_scope_has_only_two_original_routes_and_no_external_execution() -> None:
    scope, gate, decision, transition = (
        read(n) for n in ("scope", "gate_evaluation", "decision", "transition")
    )
    assert scope["new_task_instances"] == 1
    assert scope["bound_positive_candidate_attempts"] == scope["complete_runtime_routes"] == 2
    assert scope["actual_operation_records"] == 5
    assert scope["whole_archive_rescan_calls"] == scope["old_source_builder_calls"] == 0
    assert scope["Provider_calls"] == scope["credential_lookups"] == scope["GPU_jobs"] == 0
    assert {row["status"] for row in gate["rows"]} == {"PASS"}
    assert gate["second_class_required_for_pass"] is False
    assert decision["W_share"] == 1 and decision["formal_class_count"] == 2
    assert not transition["next_stage_authorized"]


def test_rebuild_uses_original_runtime_bytes_without_any_new_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("rebuild attempted another candidate execution or old source scan")

    monkeypatch.setattr(runtime, "run_candidate", forbidden)
    for cls in (
        runtime.RelationSumExecutor,
        runtime.ShareRatioExecutor,
        runtime.ScalePercentExecutor,
    ):
        monkeypatch.setattr(cls, "execute", forbidden)
    monkeypatch.setattr(old_source, "scan_archive", forbidden)
    parent_before = files_at(ROOT / models.PARENT)
    before = files_at(FORMAL)
    target = tmp_path / "rebuild"
    result = preflight.build_preflight(
        repo_root=ROOT,
        external_audit_path=FORMAL / "external_review.txt",
        source_commit=COMMIT,
        source_tree=TREE,
        output_directory=target,
        replay_from=FORMAL,
    )
    assert result["new_runtime_calls"] == 0
    assert files_at(target) == before == files_at(FORMAL)
    assert files_at(ROOT / models.PARENT) == parent_before
    with pytest.raises(FixedFixtureRuntimeError):
        preflight.build_preflight(
            repo_root=ROOT,
            external_audit_path=FORMAL / "external_review.txt",
            source_commit=COMMIT,
            source_tree=TREE,
            output_directory=target,
            replay_from=FORMAL,
        )
