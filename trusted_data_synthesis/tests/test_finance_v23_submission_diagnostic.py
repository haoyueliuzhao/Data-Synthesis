"""CPU-only tests of fixed selection, exact algebra and immutable publication."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/report_finqa_v23_submission_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("v23_submission_diagnostic", SCRIPT)
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)


def row(state):
    return {
        "native": {
            "status": "invalid_prediction" if state == "invalid" else "scored",
            "program_executable": state != "invalid",
            "native": {"execution_accuracy": int(state == "executable_correct")},
        }
    }


def test_fixed_selection_covers_all_nine_cells_and_sorts_before_limit():
    full, c_only = {}, {}
    for f in diagnostic.STATES:
        for c in diagnostic.STATES:
            for suffix in ("z", "b", "a"):
                key = f"{f}/{c}/{suffix}"
                full[key], c_only[key] = row(f), row(c)
    result = diagnostic.summarize_pair(full, c_only)
    assert result["denominator"] == 27
    assert all(
        value == 3
        for cells in result["full_rows_c_only_columns"].values()
        for value in cells.values()
    )
    assert (
        sum(
            sum(cells.values())
            for cells in result["full_binary_rows_c_only_state_columns"].values()
        )
        == 27
    )
    assert len({key for values in result["selected"].values() for key in values}) == 6
    for values in result["selected"].values():
        assert len(values) == 2
        assert values[0].endswith("/a") and values[1].endswith("/b")


def test_fewer_samples_and_input_order_do_not_change_selection():
    full = {"z": row("invalid"), "a": row("executable_correct")}
    c_only = {"z": row("executable_correct"), "a": row("executable_wrong")}
    result = diagnostic.summarize_pair(full, c_only)
    assert result["selected"][diagnostic.CATEGORIES[0]] == ["z"]
    assert result["selected"][diagnostic.CATEGORIES[1]] == []
    assert result["selected"][diagnostic.CATEGORIES[2]] == ["a"]
    assert result == diagnostic.summarize_pair(dict(reversed(list(full.items()))), c_only)


def test_algebra_reproduces_audit_pooled_identity_without_causal_claim():
    value = diagnostic.algebra(
        {"invalid": 925, "executable_wrong": 553, "executable_correct": 1171},
        {"invalid": 744, "executable_wrong": 620, "executable_correct": 1285},
    )
    assert value["delta_J"] * 100 == pytest.approx(-4.303510758776895)
    assert value["validity_term"] * 100 == pytest.approx(-4.608979370217452)
    assert value["conditional_accuracy_term"] * 100 == pytest.approx(0.305468611440558)
    assert value["causal"] is False
    assert value["valid_subsets_identical"] is False


def test_reject_unknown_or_unexecutable_scored_row():
    item = row("executable_wrong")
    item["native"]["native"]["execution_accuracy"] = None
    with pytest.raises(ValueError, match="unknown"):
        diagnostic.state(item)
    item = row("executable_wrong")
    item["native"]["program_executable"] = False
    with pytest.raises(ValueError, match="status"):
        diagnostic.state(item)


def test_persist_never_overwrites(tmp_path):
    path = tmp_path / "selection.json"
    diagnostic.persist(path, {"x": 1})
    diagnostic.persist(path, {"x": 1})
    with pytest.raises(ValueError, match="immutable"):
        diagnostic.persist(path, {"x": 2})
    assert json.loads(path.read_bytes()) == {"x": 1}


def test_evidence_requires_selection_before_any_episode_read(tmp_path):
    with pytest.raises(FileNotFoundError):
        diagnostic.collect_evidence(tmp_path / "selection.json")


def test_pair_roster_mismatch_rejected():
    with pytest.raises(ValueError, match="unpaired"):
        diagnostic.summarize_pair(
            {"a": row("executable_correct")}, {"b": row("executable_correct")}
        )


def test_selection_phase_reads_only_six_scores_and_paired_metadata(tmp_path, monkeypatch):
    paired_path = tmp_path / "final_evaluation/paired_summary/record.json"
    payloads = {}
    refs = {}
    for seed in diagnostic.SEEDS:
        for arm in diagnostic.ARMS:
            path = tmp_path / f"final_evaluation/models/seed{seed}/{arm}/scores/record.json"
            rows = []
            for index in range(883):
                item = row("executable_correct")
                item.update(task_key=f"finqa/dev-{index:04}", stop_reason="final_answer")
                rows.append(item)
            payloads[path] = dict(
                seed=seed,
                arm={"full": "Full", "c_only": "C-only"}[arm],
                denominator=883,
                metrics={"execution_accuracy": {"unknown": 0}},
                results=rows,
            )
            refs[f"seed{seed}/{arm}"] = {"path": str(path), "sha256": "fixture"}
    payloads[paired_path] = {"distinct_question_count": 883, "report_bindings": refs}
    calls = []

    def score_metadata_only(path, expected_sha=None):
        assert Path(path) in payloads, "selection must not open original output"
        calls.append(Path(path))
        return payloads[Path(path)], {"path": str(path), "sha256": "fixture", "bytes": 0}

    monkeypatch.setattr(diagnostic, "read_json", score_metadata_only)
    selection = diagnostic.prepare_selection(tmp_path)
    assert len(calls) == 7
    assert selection["sample_pair_count"] == 0
    assert selection["selection_rule"]["uses_response_text_for_selection"] is False


def test_tampered_selection_rejected_before_episode_access(tmp_path):
    path = tmp_path / "selection.json"
    diagnostic.persist(path, {"id": "wrong", "samples": [], "source_run": "/unreadable"})
    with pytest.raises(ValueError, match="selection content ID"):
        diagnostic.collect_evidence(path)


def test_compact_summary_keeps_provenance_but_never_copies_raw_logs():
    selection = {"id": "selection", "selection_rule": {}, "by_seed": {}, "pooled_algebra": {}}
    source = {"path": "/existing/episode.json", "sha256": "original-sha", "bytes": 100}
    episode = {
        "source": source,
        "episode_key": "key",
        "stop_reason": "no_tool_call",
        "full_episode_bytes_read": True,
        "turns": [{"raw_text": "large raw model transcript"}],
        "tool_events": [{"raw_output": "large tool transcript"}],
    }
    evidence = {
        "id": "evidence",
        "selection_id": "selection",
        "scope_limits": {},
        "sample_stop_reason_counts": {"no_tool_call": 2},
        "samples": [
            {
                "seed": 11,
                "task_key": "dev-only",
                "category": "fixed",
                "scores": {},
                "episodes": {"full": episode, "c_only": episode},
            }
        ],
    }
    summary = diagnostic.compact_evidence(selection, evidence)
    serialized = json.dumps(summary)
    assert '"raw_text"' not in serialized and '"tool_events"' not in serialized
    assert "large raw model transcript" not in serialized
    assert summary["samples"][0]["episodes"]["full"]["source"] == source
    assert summary["sample_pair_count"] == 1 and summary["sample_episode_count"] == 2
    assert summary["distinct_sample_task_count"] == 1
    assert summary["evidence_id"] == "evidence" and summary["selection_id"] == "selection"
