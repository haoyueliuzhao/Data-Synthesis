from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_multitrajectory import models
from trusted_synthesis.experiments.qa_reasoning_multitrajectory.preflight import (
    PreflightError,
    as_dict,
    build_preflight,
    files_at,
    freeze_directory,
)
from trusted_synthesis.experiments.qa_reasoning_multitrajectory.quotient import (
    QuotientAdmissionError,
    build_quotient_contract,
    project_quotient,
)
from trusted_synthesis.experiments.qa_reasoning_multitrajectory.runtime import run_trajectory

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/213ec87b-c479-4cd6-b027-6d36ea3e1f67/pasted-text.txt"
)


def git(*args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), *args), check=True, capture_output=True, text=True
    ).stdout.strip()


def build(path: Path) -> dict[str, Any]:
    return build_preflight(
        repo_root=ROOT,
        external_audit_path=REVIEW,
        source_commit=git("rev-parse", "HEAD"),
        source_tree=git("rev-parse", "HEAD^{tree}"),
        output_directory=path,
    )


@pytest.fixture(scope="module")
def products(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return build(tmp_path_factory.mktemp("qa_multi") / "formal")


def test_contract_registered_on_disk_before_every_actual_callback(products: dict[str, Any]) -> None:
    writer = products["writer"]
    assert writer.read_bytes("quotient_contract.json") == canonical_json_bytes(
        build_quotient_contract()
    )
    assert products["preregistration"]["outcomes_seen_at_registration"] == 0
    contract_event = next(
        event["event_ordinal"]
        for event in writer.events
        if event["relative_path"] == "quotient_contract.json" and event["kind"] == "directory_fsync"
    )
    callbacks = [e for e in writer.events if e["kind"] == "action_dispatch"]
    assert len(callbacks) == 20
    assert all(e["event_ordinal"] > contract_event for e in callbacks)


def test_same_exact_tasks_have_two_fresh_distinct_qualified_trajectories(
    products: dict[str, Any],
) -> None:
    for offset in (0, 2):
        left, right = products["results"][offset : offset + 2]
        assert canonical_json_bytes(left["package"]) == canonical_json_bytes(right["package"])
        assert canonical_json_bytes(left["bundle"]) == canonical_json_bytes(right["bundle"])
        assert canonical_json_bytes(left["graph"]) == canonical_json_bytes(right["graph"])
        assert (
            as_dict(left["trajectory"])["trajectory_id"]
            != as_dict(right["trajectory"])["trajectory_id"]
        )
        assert left["replay_audit"]["passed"] and right["replay_audit"]["passed"]
        for result in (left, right):
            assert as_dict(result["qualification"])["qualified"]
            assert len(result["states"]) == 6 and len(result["envelopes"]) == 5
            # Both sibling execute/reject pairs are publicly ready after D0.
            assert len(as_dict(result["states"][1])["available_action_ids"]) == 4


def test_independent_schedule_commutation_is_one_class_per_task(products: dict[str, Any]) -> None:
    rows = products["quotient_partition"]["rows"]
    assert len(rows) == 2
    assert all(row["distinct_trajectory_ids"] == 2 for row in rows)
    assert all(row["qualified_trajectories"] == 2 for row in rows)
    assert all(row["distinct_quotient_classes"] == 1 for row in rows)
    assert products["quotient_partition"]["tasks_with_multiple_classes"] == 0
    assert products["projections"][0] == products["projections"][1]
    assert products["projections"][2] == products["projections"][3]
    assert products["projections"][0]["content_id"] != products["projections"][2]["content_id"]
    assert products["gate_evaluation"]["failed"] == 0
    assert products["decision"]["scientific_outcome"].startswith("no_same_task")


def test_quotient_rejects_reused_replay_and_outcome_selected_rules(
    products: dict[str, Any],
) -> None:
    result = copy.deepcopy(products["results"][1])
    result["replay_audit"] = copy.deepcopy(products["results"][0]["replay_audit"])
    with pytest.raises(QuotientAdmissionError):
        project_quotient(result, products["quotient_contract"])
    contract = copy.deepcopy(products["quotient_contract"])
    contract["independent_commuting_pair"] = ()
    with pytest.raises(QuotientAdmissionError):
        project_quotient(products["results"][0], contract)


def test_dependency_invalid_schedule_rejects_before_output(products: dict[str, Any]) -> None:
    writer = products["writer"]
    before = files_at(writer.root)
    with pytest.raises(ValueError):
        run_trajectory(
            writer=writer,
            runtime_prefix="invalid_schedule",
            loaded=products["loaded"][0],
            schedule=(
                "branch_merge",
                "comparability",
                "revenue_branch",
                "operating_income_branch",
                "final_grounding",
            ),
        )
    assert files_at(writer.root) == before


def test_independent_mutations_reject_and_metrics_remain_separate(products: dict[str, Any]) -> None:
    negative = products["negative_audit"]
    assert negative["attempted"] == negative["rejected"] == 8
    assert negative["accepted"] == negative["formal_attack_writes"] == 0
    stages = {row["stage"] for row in negative["controls"]}
    assert len(stages) >= 4
    for result in products["results"]:
        d = as_dict(result["depth"])
        assert (
            d["semantic_operation_depth"],
            d["reasoning_depth"],
            d["evidence_integration_depth"],
            d["correction_depth"],
            d["critical_decision_coverage"],
        ) == (3, 4, 4, 0, 1.0)


def test_complete_second_execution_build_is_byte_identical(
    products: dict[str, Any], tmp_path: Path
) -> None:
    rebuilt = build(tmp_path / "rebuilt")
    original_files = files_at(products["writer"].root)
    assert original_files == files_at(rebuilt["writer"].root)
    manifest = products["manifest"]
    freeze_directory(
        products["writer"].root.parent,
        products["writer"].root.name,
        manifest["manifest_id"],
        manifest["artifact_root"],
        len(original_files),
        sum(map(len, original_files.values())),
    )


def test_wrong_review_and_source_reject_before_output(tmp_path: Path) -> None:
    review = tmp_path / "changed_review.txt"
    review.write_bytes(REVIEW.read_bytes() + b"\n")
    target = tmp_path / "must_not_exist"
    with pytest.raises(PreflightError, match="external review"):
        build_preflight(
            repo_root=ROOT,
            external_audit_path=review,
            source_commit="0" * 40,
            source_tree="1" * 40,
            output_directory=target,
        )
    assert not target.exists()
    with pytest.raises(PreflightError):
        build_preflight(
            repo_root=ROOT,
            external_audit_path=REVIEW,
            source_commit="0" * 40,
            source_tree="1" * 40,
            output_directory=target,
        )
    assert not target.exists()


def test_scope_and_historical_transition_remain_precise(products: dict[str, Any]) -> None:
    assert products["authorization"]["same_task_multitrajectory_authorized"] is True
    assert products["scope_audit"]["same_task_deterministic_trajectories"] == 4
    assert products["scope_audit"]["Provider_calls"] == 0
    assert products["scope_audit"]["old_mainline_resumed"] is False
    assert products["transition"]["next_stage_authorized"] is False
    assert products["transition"]["prospective_next_stage"] == models.NEXT_STAGE
    historical = json.loads((ROOT / models.PREDECESSOR_DIRECTORY / "transition.json").read_bytes())
    assert historical["next_stage_authorized"] is False
    assert products["source_binding"]["implementation"]["member_count"] == 6
