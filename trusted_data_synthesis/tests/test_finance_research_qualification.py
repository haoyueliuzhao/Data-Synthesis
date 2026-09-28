"""Finite semantic fixtures with mocked transport; no dataset outcomes/API/GPU."""

import asyncio
import json

import pytest

from trusted_synthesis.finance_research.contracts import (
    ModelIdentity,
    ModelTurn,
    RunConfig,
    ToolCall,
    digest,
)
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.harness import run_episode
from trusted_synthesis.finance_research.providers import _api_messages
from trusted_synthesis.finance_research.qualification import qualify_episode, task_support_check


def source_fixture(*, question=None, program=None, answer=None):
    raw = {
        "id": "SYNTHETIC/2021/page_1.pdf-1",
        "filename": "SYNTHETIC/2021/page_1.pdf",
        "pre_text": ["All amounts are in million USD."],
        "post_text": [],
        "table": [["Metric", "2021", "2020"], ["Revenue", "120", "90"]],
        "qa": {
            "question": question or "What was the percentage change in Revenue from 2020 to 2021?",
            "program": program or "subtract(120, 90), divide(#0, 90)",
            "exe_ans": 0.33333 if answer is None else answer,
            "gold_inds": {"table_1": "Revenue was 120 in 2021 and 90 in 2020."},
        },
    }
    return adapt_finqa([raw], split="train", revision="synthetic-not-material")[0]


def episode_fixture(bundle, actions, *, prose=""):
    class FixtureProvider:
        identity = ModelIdentity(backend="deepseek_api", model_id="deepseek-flash")
        actual_model_calls = 0

        def __init__(self):
            self.index = 0

        async def chat(self, messages, tools, config):
            index = self.index
            self.index += 1
            self.actual_model_calls += 1  # Mock counter only; no transport exists.
            name, arguments = actions[index]
            body = {
                "model": "deepseek-flash",
                "messages": _api_messages(messages),
                "tools": tools,
                "max_tokens": config.max_new_tokens,
                "temperature": config.temperature,
                "top_p": config.top_p,
                "stream": False,
                "thinking": {"type": "disabled"},
            }
            payload = {
                "id": f"mock-response-{index}",
                "model": "deepseek-flash",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": prose,
                            "tool_calls": [
                                {
                                    "id": f"mock-call-{index}",
                                    "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(arguments)},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            }
            return ModelTurn(
                raw_text=prose,
                tool_calls=(
                    ToolCall(
                        call_id=f"mock-call-{index}",
                        name=name,
                        arguments=arguments,
                        raw_arguments=json.dumps(arguments),
                    ),
                ),
                provider_metadata={
                    "public_request": body,
                    "request_sha256": digest(body),
                    "api_response": payload,
                    "fixture_no_real_API": True,
                },
            )

    provider = FixtureProvider()
    return asyncio.run(
        run_episode(
            bundle.public,
            provider,
            RunConfig(
                harness_id="bigfinance-derived-vtdo-v3",
                submission_profile="finqa_program_v2",
                role="sft",
                max_steps=32,
                max_new_tokens=256,
            ),
            invocation_context={
                "run_id": "synthetic-run",
                "episode_id": "synthetic-episode",
                "attempt": 1,
            },
        )
    )


def final(bundle, answer="0.33333", program=None):
    return (
        "final_answer",
        {"answer": answer, "program": bundle.reference.program if program is None else program},
    )


def actions(bundle):
    return [
        ("read_source", {"source_id": "table:0"}),
        (
            "calculate",
            {
                "expression": "(a-b)/b",
                "variables": {"a": "prev:r1.output.content.1.1", "b": "prev:r1.output.content.1.2"},
            },
        ),
        final(bundle),
    ]


def test_static_author_support_is_not_limited_to_two_year_question_template():
    bundle = source_fixture(
        question="What was Revenue in 2021?", program="add(120, const_0)", answer=120
    )
    public = task_support_check(bundle.public)
    assert public["status"] == "private_evidence_required"
    checked = task_support_check(bundle)
    assert checked["status"] == "author_anchored_supported"
    assert checked["public_structure"]["status"] == "private_evidence_required"
    assert not checked["material_admission"] and checked["no_probe_outcome_examined"]


def test_declarative_program_can_qualify_without_fabricated_online_calculation():
    bundle = source_fixture()
    episode = episode_fixture(bundle, [final(bundle)])
    result = qualify_episode(bundle, episode)
    assert result["decision"]["verdict"] == "CompletePass", result["decision"]
    assert result["evidence"]["proved_state"]["basis"]["delivery_mode"] == "declarative_program"
    assert result["evidence"]["checks"]["actual_calculations"] == []
    assert result["decision"]["episode_sha256"] == digest(episode)
    assert result["decision"]["evidence_sha256"] == digest(result["evidence"])
    assert result["evidence"]["candidate_only_not_material_pool_admission"]


def test_actual_calc_is_source_bound_and_all_original_failures_replay():
    bundle = source_fixture()
    live = actions(bundle)
    broken = (
        "calculate",
        {
            "expression": "(a-b)/b",
            "variables": {"a": "prev:r1.output.content.99.1", "b": "prev:r1.output.content.1.2"},
        },
    )
    episode = episode_fixture(bundle, [live[0], broken, live[1], live[2]])
    result = qualify_episode(bundle, episode)
    assert result["decision"]["verdict"] == "CompletePass", result["decision"]
    proof = result["evidence"]["proved_state"]["basis"]
    assert proof["delivery_mode"] == "actually_executed_calculation"
    assert proof["necessary_recovery"]
    replay = result["evidence"]["checks"]["replay"]
    assert len(replay["tool_events"]) == 4 and replay["tool_events"][1]["is_error"]
    assert replay["full_failed_prefix_retained"] and replay["online_calls_added"] == 0


def test_redundant_reads_and_duplicate_calculations_do_not_mint_state():
    bundle = source_fixture()
    live = actions(bundle)
    one = qualify_episode(bundle, episode_fixture(bundle, live))
    two = qualify_episode(bundle, episode_fixture(bundle, [*live[:2], live[0], live[1], live[2]]))
    assert one["decision"]["verdict"] == two["decision"]["verdict"] == "CompletePass"
    assert one["decision"]["state_id"] == two["decision"]["state_id"]
    assert one["decision"]["episode_sha256"] != two["decision"]["episode_sha256"]


def test_same_correct_result_without_source_dependency_does_not_qualify():
    bundle = source_fixture()
    result = qualify_episode(
        bundle, episode_fixture(bundle, [final(bundle, program="divide(const_1, const_3)")])
    )
    assert result["decision"]["verdict"] == "unknown"
    assert result["decision"]["state_id"] is None


@pytest.mark.parametrize(
    "change,expected",
    [("wrong_final", "invalid"), ("wrong_tool_output", "invalid"), ("extra_prose", "unknown")],
)
def test_contradictions_and_unproved_claims_cannot_become_material(change, expected):
    bundle = source_fixture()
    if change == "wrong_final":
        episode = episode_fixture(bundle, [final(bundle, answer="99")])
    elif change == "extra_prose":
        episode = episode_fixture(bundle, [final(bundle)], prose="Revenue was audited perfectly.")
    else:
        episode = episode_fixture(bundle, actions(bundle))
        events = list(episode.tool_events)
        events[1] = events[1].model_copy(
            update={"raw_output": {**events[1].raw_output, "result": "999"}}
        )
        episode = episode.model_copy(update={"tool_events": tuple(events)})
    result = qualify_episode(bundle, episode)
    assert result["decision"]["verdict"] == expected, result["decision"]
    assert result["decision"]["state_id"] is None


def test_ambiguous_source_number_and_unknown_unit_remain_unknown():
    bundle = source_fixture(program="subtract(120, 90)", answer=30)
    changed = bundle.public.sources[-1].model_copy(
        update={"content": [["Metric", "2021", "2020"], ["Revenue", "120", "120"]]}
    )
    duplicate = bundle.model_copy(
        update={
            "public": bundle.public.model_copy(
                update={"sources": (*bundle.public.sources[:-1], changed)}
            )
        }
    )
    assert task_support_check(duplicate)["status"] == "unknown"
    no_unit = bundle.model_copy(
        update={
            "public": bundle.public.model_copy(update={"sources": (bundle.public.sources[-1],)})
        }
    )
    assert task_support_check(no_unit)["reason"] == "final_quantity_unit_or_scale_not_proved"


def test_commutative_program_order_uses_same_proved_state():
    bundle = source_fixture(
        question="What was total Revenue in 2020 and 2021?", program="add(120, 90)", answer=210
    )
    one = qualify_episode(bundle, episode_fixture(bundle, [final(bundle, answer="210")]))
    two = qualify_episode(
        bundle, episode_fixture(bundle, [final(bundle, answer="210", program="add(90, 120)")])
    )
    assert one["decision"]["verdict"] == two["decision"]["verdict"] == "CompletePass"
    assert one["decision"]["state_id"] == two["decision"]["state_id"]


def test_same_row_ratio_can_cancel_unknown_common_unit_but_not_mixed_scales():
    bundle = source_fixture()
    table = bundle.public.sources[-1]
    same_unit = bundle.model_copy(
        update={"public": bundle.public.model_copy(update={"sources": (table,)})}
    )
    assert task_support_check(same_unit)["status"] == "author_anchored_supported"
    altered = table.model_copy(
        update={
            "content": [
                ["Metric", "2021 (millions)", "2020 (thousands)"],
                ["Revenue", "120", "90"],
            ]
        }
    )
    mixed = bundle.model_copy(
        update={"public": bundle.public.model_copy(update={"sources": (altered,)})}
    )
    assert task_support_check(mixed)["status"] == "unknown"


def test_mixed_scale_text_overrides_naive_same_row_unit_cancellation():
    bundle = source_fixture()
    statement = bundle.public.sources[0].model_copy(
        update={
            "content": "Revenue is in millions for 2021 and thousands for 2020.",
        }
    )
    mixed = bundle.model_copy(
        update={
            "public": bundle.public.model_copy(
                update={
                    "sources": (statement, bundle.public.sources[-1]),
                }
            )
        }
    )
    assert task_support_check(mixed)["reason"] == "mixed_public_source_scales_not_proved"


def test_exact_single_period_author_text_may_bind_but_mixed_text_units_remain_unknown():
    bundle = source_fixture(
        question="What was Revenue in 2021?", program="add(120, const_0)", answer=120
    )
    sentence = "In 2021 Revenue was 120 million USD."
    source = bundle.public.sources[0].model_copy(update={"content": sentence})
    anchored = bundle.model_copy(
        update={
            "public": bundle.public.model_copy(
                update={"sources": (source, bundle.public.sources[-1])}
            ),
            "reference": bundle.reference.model_copy(
                update={"annotations": {"gold_inds": {"text_0": sentence}}}
            ),
        }
    )
    assert task_support_check(anchored)["status"] == "author_anchored_supported"
    mixed_sentence = "In 2021 Revenue was 120 million USD and the tax rate was 30%."
    mixed = anchored.model_copy(
        update={
            "public": anchored.public.model_copy(
                update={
                    "sources": (
                        source.model_copy(update={"content": mixed_sentence}),
                        bundle.public.sources[-1],
                    )
                }
            ),
            "reference": anchored.reference.model_copy(
                update={"annotations": {"gold_inds": {"text_0": mixed_sentence}}}
            ),
        }
    )
    assert task_support_check(mixed)["reason"] == "mixed_text_units_require_finer_author_evidence"


def test_declared_percent_conversion_is_fixed_qualification_not_native_score_repair():
    bundle = source_fixture()
    episode = episode_fixture(
        bundle,
        [
            (
                "final_answer",
                {
                    "answer": "33.333%",
                    "scale": "percent",
                    "program": bundle.reference.program,
                },
            )
        ],
    )
    result = qualify_episode(bundle, episode)
    assert result["decision"]["verdict"] == "CompletePass", result["decision"]
    assert result["evidence"]["checks"]["Final"]["raw_native_diagnostic_not_modified"]


def test_rule_binding_mismatch_cannot_issue_candidate_under_another_registration():
    bundle = source_fixture()
    with pytest.raises(ValueError, match="frozen registration"):
        qualify_episode(
            bundle, episode_fixture(bundle, [final(bundle)]), qualification_rule_id="foreign-rule"
        )


def test_correct_numeric_ratio_with_currency_claim_is_not_qualified():
    bundle = source_fixture()
    result = qualify_episode(bundle, episode_fixture(bundle, [final(bundle, answer="$0.33333")]))
    assert result["decision"]["verdict"] == "invalid"
    assert (
        result["decision"]["reason"]
        == "Final_currency_symbol_conflicts_with_proved_quantity_dimension"
    )
