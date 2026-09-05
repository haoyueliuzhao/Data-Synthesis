"""Exact frozen text export; no old inference, quotient computation or tokenization."""

from __future__ import annotations

import copy
import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import adapter, engine
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import independent as pilot_audit
from trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement import (
    comparison,
    measurement,
    projection,
)
from trusted_synthesis.experiments.qa_reasoning_share_quotient_measurement import (
    independent as quotient_audit,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import inputs as exporter
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.models import (
    TrainingPreflightError,
    record,
    representation_contract,
)

ROOT = Path(__file__).resolve().parents[2]


def _forbidden(*args: Any, **kwargs: Any) -> None:
    raise AssertionError("only exact old artifact readers are permitted")


@pytest.fixture(scope="module")
def frozen() -> Iterator[dict[str, Any]]:
    with pytest.MonkeyPatch.context() as guard:
        guard.setattr(engine.ModelProtocolEngine, "__init__", _forbidden)
        guard.setattr(engine.ModelProtocolEngine, "exchange", _forbidden)
        guard.setattr(adapter.DeepSeekAdapter, "perform", _forbidden)
        guard.setattr(adapter.CurlTransport, "send", _forbidden)
        guard.setattr(adapter.MockTransport, "send", _forbidden)
        for executor in (
            engine.RelationSumExecutor,
            engine.ShareRatioExecutor,
            engine.ScalePercentExecutor,
        ):
            guard.setattr(executor, "execute", _forbidden)
        for name in ("audit_session", "audit_records", "aggregate_pilot"):
            guard.setattr(pilot_audit, name, _forbidden)
        guard.setattr(quotient_audit, "audit_measurement", _forbidden)
        for module in (projection, comparison, measurement):
            for name, value in tuple(vars(module).items()):
                if callable(value) and getattr(value, "__module__", None) == module.__name__:
                    guard.setattr(module, name, _forbidden)
        inputs = exporter.load_inputs(ROOT)
        contract = representation_contract(
            record("tokenizer_binding", status="text_only_test_no_tokenization")
        )
        dataset = exporter.export_rows(inputs, contract)
        yield {"inputs": inputs, "contract": contract, "dataset": dataset}
        exporter.assert_unchanged(ROOT, inputs)


def _renew(obj: dict[str, Any], **changes: Any) -> dict[str, Any]:
    body = {key: value for key, value in obj.items() if key != "id"} | changes
    return {**body, "id": strict_canonical_hash(body, prefix=obj["id"].split(":")[0] + ":")}


def _replace_row(dataset: dict[str, Any], index: int, row: dict[str, Any]) -> dict[str, Any]:
    dataset["rows"][index] = _renew(row)
    return _renew(dataset)


def test_exact_two_parent_directories_and_closed_assignments(frozen: dict[str, Any]) -> None:
    inputs = frozen["inputs"]
    assert len(inputs["quotient_files"]) == 51
    assert sum(map(len, inputs["quotient_files"].values())) == 1_086_642
    assert len(inputs["pilot_files"]) == 785
    assert sum(map(len, inputs["pilot_files"].values())) == 8_312_321
    assert len(inputs["assignments"]) == 5
    assert len(inputs["states"]) == 2
    assert len({row["state_id"] for row in inputs["assignments"]}) == 2
    assert inputs["parent_freeze"]["qualification_or_quotient_recomputed"] is False
    assert inputs["parent_freeze"]["provider_calls"] == inputs["parent_freeze"]["GPU_jobs"] == 0
    exporter.assert_unchanged(ROOT, inputs)


def test_exact_original_27_targets_and_all_24_exclusions(frozen: dict[str, Any]) -> None:
    inputs, contract, dataset = (frozen[key] for key in ("inputs", "contract", "dataset"))
    validation = exporter.validate_text_dataset(inputs, contract, dataset)
    assert validation["passed"] is True
    assert validation["tokenization_or_mask_claimed"] is False
    assert dataset["counts"]["positive_kind_counts"] == {"action": 11, "update": 11, "final": 5}
    assert dataset["counts"]["positive_units_by_session"] == {
        "M01": 0,
        "M02": 5,
        "M03": 7,
        "M04": 5,
        "M05": 5,
        "M06": 5,
    }
    assert dataset["counts"]["positive_target_utf8_bytes"] == 30_938
    assert Counter(row["reason"] for row in dataset["exclusions"]) == {
        "nonqualified_trajectory": 12,
        "rejected_submission": 12,
    }
    feedback_rows = []
    for row in dataset["rows"]:
        original_request = json.loads(
            inputs["pilot_files"][row["source_paths"]["pilot"]["request"]]
        )
        original_submission = json.loads(
            inputs["pilot_files"][row["source_paths"]["pilot"]["submission"]]
        )
        assert row["messages"][1]["content"] == canonical_json_bytes(original_request).decode()
        assert row["target_text"] == original_submission["raw_public_json"]
        feedback = original_request["state"]["last_feedback"]
        if feedback and feedback["code"].startswith("admission."):
            feedback_rows.append((row["session_label"], row["turn_index"] + 1))
    assert feedback_rows == [
        ("M02", 7),
        ("M03", 10),
        ("M03", 12),
        ("M04", 4),
        ("M05", 4),
        ("M05", 8),
    ]
    assert canonical_json_bytes(exporter.export_rows(inputs, contract)) == canonical_json_bytes(
        dataset
    )


@pytest.mark.parametrize("change", ["reserialize_same_json", "round_observed_value"])
def test_raw_target_is_never_repaired_or_reserialized(frozen: dict[str, Any], change: str) -> None:
    dataset = copy.deepcopy(frozen["dataset"])
    index = next(
        i
        for i, row in enumerate(dataset["rows"])
        if row["session_label"] == "M03" and row["turn_index"] == 9
    )
    row = dataset["rows"][index]
    parsed = json.loads(row["target_text"])
    if change == "round_observed_value":
        parsed["proposed_claim"]["value"] = "93.508458"
    row["target_text"] = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    dataset = _replace_row(dataset, index, row)
    with pytest.raises(TrainingPreflightError, match="text.exact_original_input_and_target"):
        exporter.validate_text_dataset(frozen["inputs"], frozen["contract"], dataset)


@pytest.mark.parametrize("change", ["erase_feedback", "future_request"])
def test_real_request_state_cannot_be_cleaned_or_replaced(
    frozen: dict[str, Any], change: str
) -> None:
    dataset = copy.deepcopy(frozen["dataset"])
    index = next(
        i
        for i, row in enumerate(dataset["rows"])
        if row["session_label"] == "M05" and row["turn_index"] == 3
    )
    row = dataset["rows"][index]
    request = json.loads(row["messages"][1]["content"])
    if change == "erase_feedback":
        request["state"]["last_feedback"] = None
    else:
        session = next(s for s in frozen["inputs"]["sessions"] if s["label"] == "M05")
        request = session["records"]["events"][8]["request"]
    row["messages"][1]["content"] = canonical_json_bytes(request).decode()
    dataset = _replace_row(dataset, index, row)
    with pytest.raises(TrainingPreflightError, match="text.exact_original_input_and_target"):
        exporter.validate_text_dataset(frozen["inputs"], frozen["contract"], dataset)


@pytest.mark.parametrize("choice", ["M01_admitted", "qualified_rejection"])
def test_nonqualified_and_rejected_submissions_cannot_enter_positive_pool(
    frozen: dict[str, Any],
    choice: str,
) -> None:
    dataset = copy.deepcopy(frozen["dataset"])
    label, index = ("M01", 0) if choice == "M01_admitted" else ("M02", 4)
    session = next(s for s in frozen["inputs"]["sessions"] if s["label"] == label)
    row = dataset["rows"][0]
    row["session_id"], row["session_label"], row["turn_index"] = (
        session["declaration"]["id"],
        label,
        index,
    )
    dataset = _replace_row(dataset, 0, row)
    with pytest.raises(TrainingPreflightError, match="text.positive_membership_order"):
        exporter.validate_text_dataset(frozen["inputs"], frozen["contract"], dataset)


def test_training_export_cannot_change_a_saved_assignment(frozen: dict[str, Any]) -> None:
    inputs = copy.deepcopy(frozen["inputs"])
    assignment = inputs["assignments"][0]
    other_state = next(
        state["id"] for state in inputs["states"] if state["id"] != assignment["state_id"]
    )
    inputs["assignments"][0] = _renew(assignment, state_id=other_state)
    with pytest.raises(
        TrainingPreflightError, match="training_inputs.assignment_collection_changed"
    ):
        exporter.validate_text_dataset(inputs, frozen["contract"], frozen["dataset"])


@pytest.mark.parametrize("parent", ["quotient", "pilot"])
def test_parent_bytes_are_frozen_even_for_a_self_consistent_text_view(
    frozen: dict[str, Any],
    parent: str,
) -> None:
    inputs = copy.deepcopy(frozen["inputs"])
    path = "assignments/M02.json" if parent == "quotient" else "online/M02/turns/00_submission.json"
    raw = inputs[parent + "_files"][path]
    inputs[parent + "_files"][path] = bytes((raw[0] ^ 1,)) + raw[1:]
    with pytest.raises(TrainingPreflightError):
        exporter.validate_text_dataset(inputs, frozen["contract"], frozen["dataset"])
    exporter.assert_unchanged(ROOT, frozen["inputs"])


def test_exclusion_ledger_cannot_drop_an_original_failure(frozen: dict[str, Any]) -> None:
    dataset = copy.deepcopy(frozen["dataset"])
    dataset = _renew(dataset, exclusions=dataset["exclusions"][1:])
    with pytest.raises(TrainingPreflightError, match="text.complete_exclusion_coverage"):
        exporter.validate_text_dataset(frozen["inputs"], frozen["contract"], dataset)
