"""Boundary arithmetic only; actual public1000 tokenization is a separate artifact."""

import copy
import json

import pytest

from trusted_synthesis.finance_research import v8_representation as representation
from trusted_synthesis.finance_research.contracts import PublicSource, PublicTask, RunConfig, digest


class Tokenizer:
    def __init__(self, count, altered=False):
        self.count, self.altered = count, altered

    def apply_chat_template(self, messages, **kwargs):
        return "original full public prompt"

    def __call__(self, text, **kwargs):
        assert kwargs.get("truncation") is False
        return {"input_ids": [1] * self.count}

    def decode(self, ids, **kwargs):
        return "changed" if self.altered else "original full public prompt"


def task_and_config():
    task = PublicTask(
        dataset="finqa",
        task_id="synthetic",
        question="Revenue?",
        sources=(
            PublicSource(source_id="source", kind="text", locator="text", content="Revenue is 10."),
        ),
        version="test",
    )
    config = RunConfig(
        role="sft",
        harness_id="bigfinance-derived-vtdo-v7",
        submission_profile="finqa-public-reasoning-v2",
        max_new_tokens=16384,
        context_limit=1048576,
    )
    return task, config


def test_teacher_capacity_is_not_student_history_admission():
    task, config = task_and_config()
    row = representation.measure_initial(task, config, Tokenizer(12000))
    assert row["initial_prefix_fits"]
    assert row["one_response_total_if_token_counts_were_equal"] > 24576
    assert row["equal_token_count_comparison_is_not_a_bound"]
    assert not row["complete_multiturn_package_fit_claimed"]
    assert row["API_output_limit"] == 16384


def test_initial_prompt_alone_cannot_consume_all_student_context():
    task, config = task_and_config()
    row = representation.measure_initial(task, config, Tokenizer(24576))
    assert not row["initial_prefix_fits"]


def test_tokenizer_changes_to_original_text_are_not_silently_repaired():
    task, config = task_and_config()
    with pytest.raises(ValueError, match="preserve public input"):
        representation.measure_initial(task, config, Tokenizer(100, altered=True))


def test_exact_legacy_histogram_identity_reconstruction_never_rewrites_or_hides_drift():
    original = dict(
        schema="finqa_v7_new_full_probe.v1",
        configs_by_task={"a": {"max_new_tokens": 2048}, "b": {"max_new_tokens": 16384}},
        capacity_histogram={2048: 1, 16384: 1},
    )
    original["id"] = digest(original)
    persisted = json.loads(json.dumps(original, sort_keys=True))
    untouched = copy.deepcopy(persisted)
    result = representation.validate_material_registration(persisted)
    assert result["legacy_integer_histogram_reconstruction"]
    assert persisted == untouched and result["original_id"] == original["id"]
    persisted["configs_by_task"]["a"]["max_new_tokens"] = 16384
    with pytest.raises(ValueError, match="histogram differs"):
        representation.validate_material_registration(persisted)
