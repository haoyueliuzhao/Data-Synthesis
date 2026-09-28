"""CPU-only diagnostic controls; never qualify, train, or call a model."""

import importlib.util
import json
from pathlib import Path

import pytest
from test_finance_research_datasets import finqa_record

from trusted_synthesis.finance_research.datasets import adapt_finqa

SCRIPT = Path(__file__).parents[1] / "scripts/diagnose_finqa_probe_output_20260928.py"
SPEC = importlib.util.spec_from_file_location("probe_output_diagnostic", SCRIPT)
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)


def projection(program):
    return dict(
        final_answer="6",
        final_program=program,
        final_scale="",
        stop_reason="final_answer",
        all_provider_calls_settled=True,
    )


def test_native_execution_never_uses_correct_raw_final_as_a_program_substitute():
    bundle = adapt_finqa([finqa_record()], split="train", revision="fixture")[0]
    missing = diagnostic.score_projection(bundle, projection(None))
    assert missing["program_structure"] == "missing"
    assert missing["execution_accuracy"] == 0
    assert missing["native_score"]["derived"]["exact_final_answer_match"] == 1
    wrong = diagnostic.score_projection(bundle, projection("add(8, 2)"))
    assert wrong["program_structure"] == "valid" and wrong["program_executable"] is True
    assert wrong["execution_accuracy"] == 0
    good = diagnostic.score_projection(bundle, projection("subtract(8, 2)"))
    assert good["execution_accuracy"] == good["program_accuracy"] == 1


def test_public_projection_and_bounded_prefixes_never_use_private_reasoning():
    episode = dict(
        task_id="synthetic",
        dataset="finqa",
        config={},
        turns=[
            {"raw_text": " ", "provider_metadata": {"reasoning_content": object()}},
            {"raw_text": "A" * 500},
            {"raw_text": "公开正文" * 100},
            {"raw_text": "third"},
        ],
        final_answer="6",
        final_program="subtract(8, 2)",
        final_scale="",
        stop_reason="final_answer",
        all_provider_calls_settled=True,
    )
    visible = diagnostic.public_projection(episode)
    json.dumps(visible)  # Opaque private sentinel would make this fail if traversed/copied.
    samples = diagnostic.bounded_sample(visible["public_contents"])
    assert len(samples) == 2 and [row["turn_index"] for row in samples] == [1, 2]
    assert all(len(row["content_prefix"]) == 200 for row in samples)
    assert "reasoning" not in json.dumps(samples)


def test_cross_table_retains_unknown_and_old_labels_in_each_fixed_purpose():
    common = dict(
        public_body_status="nonempty",
        program_structure="valid",
        program_executable=True,
        old_qualification_verdict="unknown",
        old_qualification_reason="free_text",
        native_status="scored",
        program_accuracy=0,
    )
    rows = [
        {**common, "purpose": "train", "execution_accuracy": 1},
        {**common, "purpose": "train", "execution_accuracy": 0},
        {
            **common,
            "purpose": "sealed_diagnostic",
            "execution_accuracy": None,
            "native_status": "diagnostic_unknown",
            "program_executable": None,
        },
    ]
    result = diagnostic.summarize(rows)
    assert result["all"]["denominator"] == 3
    assert result["all"]["native_execution_correct"] == 1
    assert result["all"]["native_execution_unknown"] == 1
    assert result["all"]["complete_denominator_execution_mean"] is None
    assert result["train"]["denominator"] == 2 and result["sealed"]["denominator"] == 1
    assert result["all"]["old_verdict_counts"] == {"unknown": 3}
    assert sum(row["slots"] for row in result["all"]["cross_table"]) == 3


def test_immutable_result_and_content_id_reject_changed_record(tmp_path):
    record = diagnostic.identified("fixture:", {"status": "unchanged"})
    diagnostic.publish(tmp_path / "once", {"record.json": diagnostic.encoded(record)})
    changed = {**record, "status": "changed"}
    with pytest.raises(ValueError, match="identity"):
        diagnostic.checked(changed, prefix="fixture:")
    with pytest.raises(FileExistsError):
        diagnostic.publish(tmp_path / "once", {"record.json": diagnostic.encoded(changed)})
    assert diagnostic.read(tmp_path / "once/record.json") == record
