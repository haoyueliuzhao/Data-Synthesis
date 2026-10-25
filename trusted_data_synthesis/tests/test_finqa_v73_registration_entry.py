"""Focused CPU checks for the fixed probe roster and analysis boundary."""
import importlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import finqa_v73_registration as registration


def test_two_shards_are_disjoint_and_cover_each_model_once():
    inputs = {"contexts": {f"context-{i}": {} for i in range(103)},
              "targets": {f"task/{i}": {} for i in range(96)}}
    jobs = registration.jobs_for(inputs)
    assert len(jobs) == 6
    for model in "PHL":
        a, b = (jobs[f"{model}.shard{s}"] for s in range(2))
        for field, original in (("context_ids", inputs["contexts"]), ("target_keys", inputs["targets"])):
            assert set(a[field]).isdisjoint(b[field])
            assert set(a[field]) | set(b[field]) == set(original)
    assert sum(len(j["context_ids"]) for j in jobs.values()) == 309
    assert sum(len(j["target_keys"]) for j in jobs.values()) == 288


@pytest.mark.parametrize("contexts,targets", [(289,96), (288,97)])
def test_no_budget_growth(contexts, targets):
    with pytest.raises(ValueError, match="budget"):
        registration.jobs_for({"contexts": dict.fromkeys(map(str, range(contexts))),
                               "targets": dict.fromkeys(map(str, range(targets)))})


def test_generation_and_probability_retain_separate_rosters():
    jobs = registration.jobs_for({"contexts": {"shared-input": {}}, "targets": {"a": {}, "b": {}}})
    assert sum(len(j["context_ids"]) for j in jobs.values()) == 3
    assert sum(len(j["target_keys"]) for j in jobs.values()) == 6


def test_flattening_retains_unknown_slots_and_each_old_source_hash():
    entry = importlib.import_module("finqa_v73_entry")
    bundle = {"logical_rows": [dict(task_key="a", group="F",
        contexts={"P": "same", "H": None, "L": "same"},
        source_responses={"P": dict(raw_response_sha256="old-P", response_ids_sha256="ids-P"),
                          "L": dict(raw_response_sha256="old-L", response_ids_sha256="ids-L")})]}
    result = entry.analysis_inputs(bundle)
    assert result["tasks"] == [dict(task_key="a", group="F")]
    assert len(result["logical_rows"]) == 3
    by_source = {r["source"]: r for r in result["logical_rows"]}
    assert by_source["H"]["context_id"] is None
    assert by_source["P"]["old_response_sha256"] == "old-P"
    assert by_source["L"]["old_response_sha256"] == "old-L"


def test_probe_contract_forbids_training_tool_and_native_score():
    contract = registration.contract()
    assert all(contract[key] == 0 for key in ("new_optimizer_updates", "new_backward_calls",
        "new_LoRA_initializations", "new_tools_executed", "new_native_scores", "external_API_calls"))
    assert contract["teacher_forcing_separate_from_free_generation"]
    assert not registration.recovery_policy()["UNKNOWN_state_source_numeric_or_implementation_failure_automatic_retry"]


def test_all_unknown_reconstruction_cannot_freeze_science(monkeypatch, tmp_path):
    monkeypatch.setattr(registration.b, "ROOT", tmp_path)
    monkeypatch.setattr(registration.b, "checked", lambda path: {"contexts": {}, "targets": {}})
    monkeypatch.setattr(registration.subprocess, "check_output", lambda *a, **k: pytest.fail("must not freeze any source"))
    with pytest.raises(ValueError, match="all-UNKNOWN"):
        registration.freeze("HEAD")
