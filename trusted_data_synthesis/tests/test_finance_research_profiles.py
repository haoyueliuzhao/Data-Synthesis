import pytest
from test_finance_research_datasets import finqa_record, tatqa_context

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.datasets import adapt_finqa, adapt_tatqa
from trusted_synthesis.finance_research.profiles import (
    FINQA_OPERATORS,
    PUBLIC_PROFILE_ID,
    profile_definition,
    public_run_view,
)


def test_public_profile_is_a_new_bound_view_not_new_qa_or_source_snapshot():
    raw = finqa_record()
    original = adapt_finqa([raw], split="train", revision="original-fixture")[0].public
    before = original.model_dump_json()
    view = public_run_view(original)
    assert view.task_id == original.task_id
    assert view.sources == original.sources
    assert view.question == original.question
    assert view.version == original.version
    assert original.model_dump_json() == before
    assert digest(view) != digest(original)
    assert view.answer_contract["original_public_task_sha256"] == digest(original)
    assert view.answer_contract["profile_id"] == PUBLIC_PROFILE_ID
    assert view.answer_contract["profile_sha256"] == digest(profile_definition())
    assert "optional" not in view.answer_contract["program"]
    assert "PRIVATE" not in view.model_dump_json()
    assert raw["qa"]["program"] not in view.model_dump_json()


def test_profile_is_shared_generic_contract_not_answer_dependent():
    first = finqa_record()
    second = finqa_record()
    second["id"] += "different"
    second["qa"].update(program="multiply(24, 3)", exe_ans=72)
    tasks = adapt_finqa([first, second], split="train", revision="fixture")
    one, two = [public_run_view(x.public) for x in tasks]
    assert one.answer_contract["submission_profile"] == two.answer_contract["submission_profile"]
    assert one.answer_contract["profile_sha256"] == two.answer_contract["profile_sha256"]
    profile = profile_definition()
    assert profile["required_final_fields"] == ["answer", "program"]
    assert "final_answer" not in profile["final_submission"]
    assert "final_answer" not in str(profile["dsl"])
    assert "harness-defined Final submission" in profile["final_submission"]
    assert profile["contains_task_specific_reference"] is False
    assert len(FINQA_OPERATORS) == 10
    assert profile["dsl"]["allowed_operators"] == list(FINQA_OPERATORS)
    profile["dsl"]["allowed_operators"].append("invented")
    assert "invented" not in profile_definition()["dsl"]["allowed_operators"]


def test_view_rejects_private_bundle_wrong_dataset_and_double_application():
    bundle = adapt_finqa([finqa_record()], split="train", revision="fixture")[0]
    with pytest.raises(TypeError, match="PublicTask"):
        public_run_view(bundle)
    with pytest.raises(ValueError, match="original public task"):
        public_run_view(public_run_view(bundle.public))
    tatqa = adapt_tatqa([tatqa_context()], split="test", revision="fixture")[0]
    with pytest.raises(ValueError, match="dataset"):
        public_run_view(tatqa.public)
    with pytest.raises(ValueError, match="unknown submission"):
        profile_definition("finqa_unregistered")


def test_documented_operators_match_pinned_official_scorer():
    pytest.importorskip("sympy")
    from trusted_synthesis.finance_research.metric_vendor import finqa_evaluate

    assert list(FINQA_OPERATORS) == finqa_evaluate.all_ops
