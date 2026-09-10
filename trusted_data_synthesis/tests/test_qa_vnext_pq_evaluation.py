"""CPU-only scripted transcript controls, never bound Student/model/tokenizer runs."""

import copy
import json
import socket

import pytest

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_pq_student import evaluate, runtime
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
    OUTPUT,
    encode,
    evaluation_config,
    record,
)

PUBLIC = {
    "id": "synthetic-public",
    "task_id": "synthetic-task",
    "question": "What is the net change in millions of dollars?",
    "numeric_catalog": [
        {"id": "source:a", "value": "300", "segment": "s0"},
        {"id": "source:b", "value": "109", "segment": "s1"},
    ],
    "segments": {
        "s0": "Prior balance 300 million dollars",
        "s1": "Current balance 109 million dollars",
    },
}
PRIVATE = {
    "unit": "USD_million",
    "facts": {"source:a": {"value": "300"}, "source:b": {"value": "109"}},
    "target": {"op": "subtract", "args": ["source:b", "source:a"]},
    "relations": {},
}
IDENTITY = {"id": "synthetic-only-no-student"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("CPU-only evaluator test attempted network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def session(tmp_path, turns, *, terminal="stop", invoked=True):
    responses = iter(turns)

    def decoder(messages):
        content = next(responses)
        raw = content if isinstance(content, str) else encode(content).decode()
        generated = ([20, 151645] if terminal == "stop" else [20]) if invoked else []
        return {
            "content": raw,
            "finish_reason": terminal,
            "generation_invoked": invoked,
            "generated_token_ids": generated,
            "public_content_token_ids": generated[:-1] if terminal == "stop" else generated,
            "generated_token_count": len(generated),
            "prompt_token_count": 100,
            "prompt_truncated": False,
        }

    runtime.run_session(PUBLIC, tmp_path, decoder, IDENTITY)
    return evaluate.audit_session(tmp_path, PUBLIC, IDENTITY)


def reviewed(audit):
    review = evaluate.review_template(audit, PUBLIC, PRIVATE)
    review["author"] = "CPU synthetic fixture, not model outcome review"
    review["publication"]["direction_multiplier"] = 1
    final_index = audit["first_final_index"]
    if final_index is not None:
        final_quote = {
            "response_index": final_index,
            "quote": audit["raw_messages"][str(final_index)],
        }
        review["publication"]["evidence"] = [final_quote]
        for field in evaluate.FIELDS:
            review[field] = {
                "status": "PASS",
                "evidence": [final_quote],
                "explanation": "synthetic known relationship",
            }
    if audit["calculations"]:
        calculation = audit["calculations"][-1]
        quote = {
            "response_index": calculation["response_index"],
            "quote": audit["raw_messages"][str(calculation["response_index"])],
        }
        review["calculation"].update(
            call_id=calculation["call_id"],
            unit="USD_million",
            direction_multiplier=1,
            evidence=[quote],
        )
        for field in evaluate.FIELDS[:3]:
            review[field]["evidence"] = [quote]
    return review


def calc(expression="new - old", **extra):
    return {
        "tool": "calculate",
        "arguments": {
            "expression": expression,
            "variables": {"old": "300", "new": "109"},
            "sources": {"old": "source:a", "new": "source:b"},
        },
        "message": "Signed change in USD_million: current balance minus prior balance.",
        **extra,
    }


def test_independent_source_resultrefs_notebook_and_complete_trace(tmp_path):
    audit = session(
        tmp_path,
        [
            {"tool": "read_source", "arguments": {"locators": ["source:a"]}},
            {
                "tool": "notebook",
                "arguments": {
                    "operation": "write",
                    "key": "formula",
                    "text": "Signed change = current - prior, in USD_million",
                },
            },
            {"tool": "notebook", "arguments": {"operation": "read", "key": "formula"}},
            {
                "tool": "calculate",
                "arguments": {
                    "expression": "new - old",
                    "variables": {"new": "109", "old": {"result_id": "tool:1"}},
                },
                "message": "Signed USD_million change=current-prior",
            },
            {"final": {"value": "-191", "unit": "USD_million", "result_id": "tool:4"}},
        ],
    )
    grade = evaluate.qualify(audit, reviewed(audit), PUBLIC, PRIVATE)
    assert audit["calculations"][0]["used_result_ids"] == ["tool:1"]
    assert grade["task_answer_status"] == "PASS"
    assert grade["complete_verifiable_trajectory"]


def test_primary_lexical_priority_cannot_swap_finer_secondary_or_unit(tmp_path):
    audit = session(
        tmp_path,
        [
            '{"final":{"value":-190.0,"unit":"USD_million",'
            '"answer":"The exact change is -191 million dollars."}}'
        ],
    )
    review = reviewed(audit)
    assert review["publication"]["value"] == "-190.0"
    assert evaluate.qualify(audit, review, PUBLIC, PRIVATE)["task_answer_status"] == "FAIL"
    review["publication"]["value"] = "-191"
    with pytest.raises(ValueError, match="absolute_priority"):
        evaluate.qualify(audit, review, PUBLIC, PRIVATE)
    review = reviewed(audit)
    review["publication"]["unit"] = "USD_thousand"
    with pytest.raises(ValueError, match="unit_absolute_priority"):
        evaluate.qualify(audit, review, PUBLIC, PRIVATE)


def test_money_conversion_scales_number_and_quantum_but_retains_reference_cap():
    score = evaluate.score_quantity("-191000", "USD_thousand", 1, PRIVATE)
    assert score["task_answer_status"] == "PASS"
    assert score["converted_lexical_quantum"] == "1/1000"
    assert score["rounding_tolerance"] == "1/2000"
    assert (
        evaluate.score_quantity("-0.191", "USD_billion", 1, PRIVATE)["rounding_tolerance"]
        == "1/200"
    )
    assert (
        evaluate.score_quantity("-190.99", "USD_million", 1, PRIVATE)["task_answer_status"]
        == "FAIL"
    )
    percent = {**PRIVATE, "unit": "percent"}
    assert (
        evaluate.score_quantity("-1.91", "fraction", 1, percent)["task_answer_status"]
        == "UNDETERMINED"
    )
    assert (
        evaluate.score_quantity("-191", "USD_million", 1, percent)["task_answer_status"] == "FAIL"
    )


def test_positive_decrease_magnitude_requires_original_Final_and_precalc_evidence(tmp_path):
    audit = session(
        tmp_path,
        [
            calc(
                "old - new",
                message="Calculate decrease magnitude in USD_million: prior minus current.",
            ),
            {
                "final": {
                    "value": "191",
                    "unit": "USD_million",
                    "answer": "A decrease of 191 million dollars.",
                }
            },
        ],
    )
    review = reviewed(audit)
    review["publication"]["direction_multiplier"] = -1
    review["calculation"]["direction_multiplier"] = -1
    assert evaluate.qualify(audit, review, PUBLIC, PRIVATE)["complete_verifiable_trajectory"]
    late = copy.deepcopy(review)
    late["calculation"]["evidence"] = late["publication"]["evidence"]
    assert not evaluate.qualify(audit, late, PUBLIC, PRIVATE)["complete_verifiable_trajectory"]
    unsigned = copy.deepcopy(review)
    unsigned["publication"]["direction_multiplier"] = 1
    assert evaluate.qualify(audit, unsigned, PUBLIC, PRIVATE)["task_answer_status"] == "FAIL"
    assert (
        evaluate.score_quantity("-191", "USD_million", -1, PRIVATE)["task_answer_status"]
        == "UNDETERMINED"
    )


def test_later_decrease_word_cannot_retroactively_orient_old_minus_new(tmp_path):
    audit = session(
        tmp_path,
        [
            calc("old - new", message="Compute old minus new in USD_million."),
            {
                "final": {
                    "value": "191",
                    "unit": "USD_million",
                    "answer": "A decrease of 191 million dollars.",
                }
            },
        ],
    )
    review = reviewed(audit)
    review["publication"]["direction_multiplier"] = -1
    review["calculation"]["direction_multiplier"] = -1
    grade = evaluate.qualify(audit, review, PUBLIC, PRIVATE)
    assert grade["task_answer_status"] == "PASS"
    assert not grade["complete_verifiable_trajectory"]


def test_secondary_uses_own_display_tolerance_not_primary_cap(tmp_path):
    audit = session(
        tmp_path,
        [{"final": {"value": "-191", "unit": "USD_million", "answer": "-0.19 billion dollars"}}],
    )
    review = reviewed(audit)
    review["secondary"] = [
        {
            "value": "-0.19",
            "unit": "USD_billion",
            "direction_multiplier": 1,
            "evidence": review["publication"]["evidence"],
            "explanation": "coarse billion display",
        }
    ]
    grade = evaluate.qualify(audit, review, PUBLIC, PRIVATE)
    assert grade["task_answer_status"] == "PASS"
    assert grade["secondary"][0]["rounding_tolerance"] == "5"
    assert not grade["complete_verifiable_trajectory"]


@pytest.mark.parametrize(
    "terminal,invoked,content",
    [
        ("context_token_limit", False, ""),
        ("stop", True, ""),
        ("generation_truncated_length", True, '{"final":'),
    ],
)
def test_nonfinal_delivery_unresolved_and_noninvoked_context_not_model_request(
    tmp_path, terminal, invoked, content
):
    audit = session(tmp_path, [content], terminal=terminal, invoked=invoked)
    grade = evaluate.qualify(audit, reviewed(audit), PUBLIC, PRIVATE)
    assert audit["model_requests"] == int(invoked)
    assert audit["decoder_requests"] == 1
    assert grade["task_answer_status"] == "UNDETERMINED"
    assert not grade["complete_verifiable_trajectory"]
    assert grade["delivery_status"] == "NO_FINAL"
    assert (tmp_path / "turns/000_assistant.raw").exists() == invoked


def test_exact_history_and_local_origin_reject_http_projection(tmp_path):
    session(tmp_path, [{"final": {"value": "-191", "unit": "USD_million"}}])
    path = tmp_path / "result.json"
    result = json.loads(path.read_bytes())
    result["origin"] = "live_http"
    path.write_bytes(encode(result))
    with pytest.raises(ValueError, match="actual_local_origin"):
        evaluate.audit_session(tmp_path, PUBLIC, IDENTITY)


def test_unicode_protocol_error_replay_matches_runtime(tmp_path):
    audit = session(
        tmp_path,
        [
            '{"final":{"value":"-191","unit":"USD_million","answer":"\\ud800"}}',
            {"final": {"value": "-191", "unit": "USD_million"}},
        ],
    )
    assert audit["first_final_index"] == 1
    assert audit["model_requests"] == 2


@pytest.mark.parametrize(
    "text,value",
    [
        ("The year is 2014.", "14"),
        ("The amount is 1400.", "14"),
        ("The change is -191 million dollars.", "191"),
    ],
)
def test_fallback_numeric_extraction_never_uses_substring_or_drops_sign(tmp_path, text, value):
    audit = session(tmp_path, [{"final": {"answer": text, "unit": "USD_million"}}])
    review = reviewed(audit)
    review["publication"]["value"] = value
    assert evaluate.qualify(audit, review, PUBLIC, PRIVATE)["task_answer_status"] == "UNDETERMINED"


def test_Final_consistency_evidence_cannot_be_only_earlier_calculation(tmp_path):
    audit = session(tmp_path, [calc(), {"final": {"value": "-191", "unit": "USD_million"}}])
    review = reviewed(audit)
    review["final_answer_consistency"]["evidence"] = review["calculation"]["evidence"]
    with pytest.raises(ValueError, match="actual_first_Final_evidence"):
        evaluate.qualify(audit, review, PUBLIC, PRIVATE)


def test_assess_finalize_all_84_synthetic_sessions_and_paired_counts(tmp_path, monkeypatch):
    output = tmp_path / OUTPUT
    registrations = [
        {
            "task_key": f"{prefix}{i}",
            "group": "transfer" if prefix == "T" else "regression",
            "public_document_id": PUBLIC["id"],
        }
        for prefix in ("T", "R")
        for i in range(1, 7)
    ]
    prep = DurableStore(output / "preparation")
    prep.json("evaluation_policy.json", evaluate.policy())
    prep.json("evaluation_configuration.json", evaluation_config())
    prep.json("evaluation_registrations.json", registrations)
    prep.json("implementation.json", {"synthetic_fixture": True})
    prep.json("private/evaluation_targets.json", {r["task_key"]: PRIVATE for r in registrations})
    for registration in registrations:
        prep.json(f"public/{registration['task_key']}.json", PUBLIC)
    seal_directory(prep, kind="synthetic_pq_preparation")
    monkeypatch.setattr(evaluate, "verify_source_snapshot", lambda root, snapshot: None)
    for variant in evaluation_config()["variants"]:
        store = DurableStore(output / "evaluation" / variant)
        store.json("identity.json", IDENTITY)
        store.json("configuration.json", evaluation_config())
        rows = []
        for registration in registrations:
            key = registration["task_key"]
            audit = session(
                store.root / "sessions" / key,
                [calc(), {"final": {"value": "-191", "unit": "USD_million"}}],
            )
            rows.append({"task_key": key, "result_id": audit["result_id"]})
        store.json(
            "report.json",
            record(
                "synthetic_generation_report",
                variant=variant,
                model_identity=IDENTITY,
                teacher_calls=0,
                rows=rows,
            ),
        )
        seal_directory(store, kind="pq_student_generation_manifest")
    assert evaluate.assess(tmp_path)["sessions"] == 84
    reviews = {
        f"{variant}/{r['task_key']}": reviewed(
            json.loads((output / f"assessment/audits/{variant}/{r['task_key']}.json").read_bytes())
        )
        for variant in evaluation_config()["variants"]
        for r in registrations
    }
    path = tmp_path / "synthetic_reviews.json"
    path.write_bytes(encode({"reviews": reviews}))
    report = evaluate.finalize(tmp_path, path)
    assert report["sessions"] == 84
    assert report["by_variant"]["B0"]["all12"]["complete_trace_PASS"] == 12
    assert len(report["paired_seed_differences"]) == 9
    assert all(
        row["Q_minus_P_answer_PASS"] == row["Q_minus_P_complete_trace_PASS"] == 0
        for row in report["paired_seed_differences"]
    )
    with pytest.raises(ValueError, match="no_overwrite"):
        evaluate.assess(tmp_path)
