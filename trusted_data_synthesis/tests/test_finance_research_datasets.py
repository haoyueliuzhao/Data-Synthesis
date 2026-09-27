import json

import pytest

from trusted_synthesis.finance_research.catalog import validate_dataset_role
from trusted_synthesis.finance_research.datasets import (
    adapt_financemath,
    adapt_finqa,
    adapt_tatqa,
    load_snapshot,
)


def finqa_record():
    return {
        "id": "SYNTHETIC/2020/page_1.pdf-1",
        "filename": "SYNTHETIC/2020/page_1.pdf",
        "pre_text": ["Revenue is shown below.", "Keep this irrelevant sentence."],
        "post_text": ["Keep this complete footer."],
        "table": [["Year", "Revenue"], ["2020", "8"], ["2019", "2"]],
        "table_ori": [["Year", "Revenue"], ["2020", "$8"], ["2019", "$2"]],
        "qa": {
            "question": "What is the increase?",
            "program": "subtract(8, 2)",
            "exe_ans": 6,
            "answer": "6",
            "program_re": "subtract(8, 2)",
            "gold_inds": {"table_1": "PRIVATE GOLD ANCHOR"},
            "model_input": [["table_1", "PRIVATE SELECTED CONTEXT"]],
        },
    }


def tatqa_context(answer_type="multi-span", answer=None, scale=""):
    return {
        "table": {"uid": "synthetic-context", "table": [["Country"], ["China"], ["USA"]]},
        "paragraphs": [
            {"uid": "p1", "order": 1, "text": "Keep all paragraphs."},
            {"uid": "p2", "order": 2, "text": "Also keep this irrelevant text."},
        ],
        "questions": [
            {
                "uid": "synthetic-q",
                "question": "What are the countries?",
                "answer": ["China", "USA"] if answer is None else answer,
                "answer_type": answer_type,
                "answer_from": "table",
                "derivation": "PRIVATE DERIVATION",
                "rel_paragraphs": [2],
                "scale": scale,
                "req_comparison": False,
            }
        ],
    }


def test_finqa_context_is_complete_and_gold_is_private():
    raw = finqa_record()
    bundle = adapt_finqa([raw], split="train", revision="fixture-v1")[0]
    assert [source.content for source in bundle.public.sources] == [
        *raw["pre_text"],
        raw["table"],
        *raw["post_text"],
    ]
    public = bundle.public.model_dump_json()
    assert "PRIVATE" not in public
    assert "gold_inds" not in public
    assert "model_input" not in public
    assert bundle.reference.annotations["source_metadata"]["table_ori"] == raw["table_ori"]
    assert bundle.reference.annotations["gold_inds"] == raw["qa"]["gold_inds"]
    assert bundle.lineage.original_id == raw["id"]
    assert bundle.lineage.source_group == "finqa:report:SYNTHETIC/2020"
    assert bundle.lineage.strata["reference_program_steps"] == 1


def test_finqa_report_group_crosses_page_boundaries():
    raw = finqa_record()
    other = {**raw, "id": "SYNTHETIC/2020/page_2.pdf-7", "filename": "SYNTHETIC/2020/page_2.pdf"}
    a, b = adapt_finqa([raw, other], split="train", revision="fixture-v1")
    assert a.lineage.source_group == b.lineage.source_group
    assert a.lineage.context_fingerprint == b.lineage.context_fingerprint


def test_tatqa_retains_all_questions_and_natural_answer_types_privately():
    raw = tatqa_context()
    raw["questions"].append(
        {**raw["questions"][0], "uid": "second-q", "answer_type": "count", "answer": 2, "scale": ""}
    )
    bundles = adapt_tatqa([raw], split="test", revision="fixture-v1")
    assert len(bundles) == 2
    for bundle in bundles:
        assert len(bundle.public.sources) == 3
        assert bundle.lineage.source_group_level == "context"
        public = bundle.public.model_dump_json()
        assert all(
            label not in public
            for label in ("answer_type", "answer_from", "derivation", "rel_paragraphs", "PRIVATE")
        )
    assert bundles[0].reference.answer == ["China", "USA"]
    assert bundles[1].reference.answer == 2
    assert bundles[0].lineage.context_fingerprint == bundles[1].lineage.context_fingerprint


def test_financemath_reads_only_official_local_schema_verbatim():
    markdown = "| rate | term |\n|---|---|\n| 0.05 | 2 |"
    raw = {
        "question_id": "validation-synthetic",
        "question": "Compute the interest.",
        "tables": [markdown],
        "python_solution": "PRIVATE PYTHON",
        "ground_truth": 2.345,
        "topic": "PRIVATE TOPIC",
        "parent_ids": ["source-1"],
    }
    bundle = adapt_financemath([raw], split="validation", revision="user-local-v1")[0]
    assert bundle.public.sources[0].content == markdown
    assert bundle.reference.program == "PRIVATE PYTHON"
    assert "PRIVATE" not in bundle.public.model_dump_json()
    assert bundle.lineage.parent_ids == ("source-1",)


def test_missing_reference_duplicate_id_or_revision_fail_closed():
    raw = finqa_record()
    with pytest.raises(ValueError, match="duplicate"):
        adapt_finqa([raw, raw], split="train", revision="fixture-v1")
    with pytest.raises(ValueError, match="revision"):
        adapt_finqa([raw], split="train", revision="")
    raw["qa"].pop("exe_ans")
    with pytest.raises(ValueError, match="private_test"):
        adapt_finqa([raw], split="private_test", revision="fixture-v1")


def test_snapshot_json_load_and_unknown_dataset(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps([finqa_record()]))
    assert len(load_snapshot("FinQA", path, "train", "fixture-v1")) == 1
    with pytest.raises(ValueError, match="not admitted"):
        load_snapshot("multihiertt", path, "train", "fixture-v1")


@pytest.mark.parametrize(
    "dataset,split,role",
    [
        ("finqa", "test", "sft"),
        ("finqa", "dev", "feedback"),
        ("tatqa", "train", "sft"),
        ("financemath", "test", "feedback"),
        ("financemath", "train", "sft"),
        ("openenv290", "test", "sft"),
        ("openenv290", "test", "feedback"),
        ("multihiertt", "test", "test"),
    ],
)
def test_forbidden_roles(dataset, split, role):
    with pytest.raises(ValueError):
        validate_dataset_role(dataset, split, role)


def test_allowed_roles_and_explicit_tatqa_training_revision():
    validate_dataset_role("finqa", "train", "sft")
    validate_dataset_role("finqa", "train", "feedback")
    validate_dataset_role("finqa", "dev", "development")
    validate_dataset_role("finqa", "public_test", "test")
    validate_dataset_role("tatqa", "test", "test")
    validate_dataset_role("tatqa", "train", "sft", separate_training=True)
    validate_dataset_role("financemath", "validation", "development")
    validate_dataset_role("openenv290", "test", "test")
