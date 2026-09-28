import json

import pytest
from test_finance_research_datasets import finqa_record

from trusted_synthesis.finance_research.contracts import PublicSource, PublicTask, ToolCall, digest
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.native_metrics import score_native
from trusted_synthesis.finance_research.profiles import (
    PUBLIC_PROFILE_V2,
    profile_definition,
    public_run_view,
)


def test_profile_v1_historical_digest_unchanged_and_v2_policy_not_rescored():
    first = profile_definition("finqa_program_v1")
    second = profile_definition(PUBLIC_PROFILE_V2)
    assert digest(first) == "618ffb0137c6f739dbee9774d645f0ac1f710eb14bf8fb932b4bc9249d1bda9f"
    assert second["id"] == "finqa_program_v2" and second["version"] == 2
    assert digest(first) != digest(second)
    assert second["missing_prediction_policy"] == first["missing_prediction_policy"]
    assert second["dsl"] == first["dsl"]
    assert second["model_terminal_reasons"] == first["model_terminal_reasons"]


def test_v2_common_example_is_public_synthetic_not_selected_from_task_references():
    raw = finqa_record()
    first = adapt_finqa([raw], split="train", revision="fixture")[0]
    raw["qa"].update(program="PRIVATE_PROGRAM_SENTINEL", exe_ans="PRIVATE_ANSWER_SENTINEL")
    second = adapt_finqa([raw], split="train", revision="fixture")[0]
    one = public_run_view(first.public, PUBLIC_PROFILE_V2)
    two = public_run_view(second.public, PUBLIC_PROFILE_V2)
    assert one.answer_contract["submission_profile"] == two.answer_contract["submission_profile"]
    assert one.sources == first.public.sources and one.question == first.public.question
    assert one.task_id == first.public.task_id
    assert one.answer_contract["original_public_task_sha256"] == digest(first.public)
    assert "PRIVATE" not in one.model_dump_json()
    example = one.answer_contract["submission_profile"]["synthetic_example"]
    assert example["source"]["content"][1] == ["Revenue", "120", "90"]
    assert example["final_semantic_fields"]["program"] == "subtract(120, 90), divide(#0, 90)"
    assert "not an executed tool history" in example["scope"]
    assert set(one.answer_contract["submission_profile"]["three_languages"]) == {
        "tool_result_references",
        "calculate_expression",
        "final_finqa_program",
    }


def test_synthetic_documentation_matches_actual_shared_tool_semantics():
    from trusted_synthesis.finance_research.tools import (
        VISIBLE_REFERENCE_PROTOCOL,
        PublicToolSession,
    )

    example = profile_definition(PUBLIC_PROFILE_V2)["synthetic_example"]
    task = PublicTask(
        dataset="finqa",
        task_id="synthetic-only",
        version="fixture",
        question="Synthetic ratio",
        sources=(PublicSource.model_validate(example["source"]),),
    )
    session = PublicToolSession(task, reference_protocol=VISIBLE_REFERENCE_PROTOCOL)
    for index, (name, arguments, expected) in enumerate(
        [
            (
                "read_source",
                example["read_source_arguments"],
                example["illustrative_read_observation"],
            ),
            (
                "calculate",
                example["calculate_arguments"],
                example["illustrative_calculation_observation"],
            ),
        ]
    ):
        event = session.execute(
            ToolCall(
                call_id=f"fixture:{index}",
                name=name,
                arguments=arguments,
                raw_arguments=json.dumps(arguments),
            )
        )
        assert not event.is_error
        assert json.loads(event.visible_output) == expected


@pytest.mark.parametrize(
    "program",
    ["subtract(8, 2)", None, "subtract(8,2)", "subtract('8', 2)", "divide(subtract(8, 2), 1)"],
)
def test_v2_changes_profile_identity_only_not_native_scoring_or_program_repair(program):
    bundle = adapt_finqa([finqa_record()], split="test", revision="fixture")[0]
    common = dict(program=program, stop_reason="final_answer", all_provider_calls_settled=True)
    original = score_native(bundle, "6", submission_profile="finqa_program_v1", **common)
    revised = score_native(bundle, "6", submission_profile=PUBLIC_PROFILE_V2, **common)
    assert revised["submission_profile"] == PUBLIC_PROFILE_V2
    assert revised["submission_profile_sha256"] == digest(profile_definition(PUBLIC_PROFILE_V2))
    assert revised["native"] == original["native"]
    assert revised["status"] == original["status"]
    assert revised["final_program_consistency"] == original["final_program_consistency"]
