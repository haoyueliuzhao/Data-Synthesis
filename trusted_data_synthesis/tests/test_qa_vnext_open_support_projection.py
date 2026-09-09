"""Synthetic open-history projection controls; no provider or empirical sessions."""

import copy

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_autonomous_formula.online.calculator import (
    calculate,
)
from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.plan import (
    condition,
    encode,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.projection import (
    project_session,
)

GOAL = {"quantity": "synthetic amount", "period": "2020", "unit": "USD_million"}


def make_session(specifications, answer_id=None):
    facts = [
        {"id": "source:" + name, "segment": name, "value": value, "token": value}
        for name, value in (("a", "10"), ("b", "4"), ("c", "6"), ("d", "-2"), ("e", "6"))
    ]
    public = {
        "id": "constructed-document",
        "task_id": "constructed-task",
        "numeric_catalog": facts,
        "segments": {fact["segment"]: {"text": fact["token"], "period": "2020"} for fact in facts},
    }
    previous, turns = {}, []

    def turn(choice, call=None, final=False, protocol_error=None, raw_override=None):
        index = len(turns)
        raw = raw_override if raw_override is not None else encode(choice)
        event = {
            "response_index": index,
            "raw_sha256": sha(raw),
            "tool_call": call,
            "final": final,
            "protocol_error": protocol_error,
        }
        turns.append(
            {
                "binding": {"response_index": index, "raw_response_sha256": sha(raw)},
                "raw": raw,
                "parsed": None if protocol_error else choice,
                "event": event,
            }
        )

    for specification in specifications:
        name = specification.get("tool", "calculate")
        if name == "format_error":
            turn(
                None,
                protocol_error="invalid_json",
                raw_override=(
                    b'{"tool":"calculate","arguments":{"expression":"x-y",'
                    b'"variables":{"x":20/2,"y":4}}}'
                ),
            )
            continue
        call_id = "tool:" + str(len(previous) + 1)
        arguments = specification["arguments"]
        if name == "calculate":
            result = calculate(arguments, previous)
        elif name == "read_source":
            source_id = arguments["locators"][0]
            fact = next(item for item in facts if item["id"] == source_id)
            result = {
                "records": [
                    {"numeric_record": fact, "segment": public["segments"][fact["segment"]]}
                ],
                "exact_value": fact["value"],
                "numeric_source_id": source_id,
            }
        else:
            raise AssertionError("unsupported synthetic tool")
        output = {"call_id": call_id, "tool": name, "status": "ok", "result": result}
        call = {"id": call_id, "name": name, "arguments": arguments, "output": output}
        choice = {
            "tool": name,
            "arguments": arguments,
            "message": specification.get(
                "message",
                "Public formula, source role, period 2020 and million-dollar unit explanation.",
            ),
        }
        turn(choice, call=call)
        previous[call_id] = output
    answer_id = answer_id or next(
        cid for cid in reversed(previous) if previous[cid]["tool"] == "calculate"
    )
    final = {
        "value": previous[answer_id]["result"]["exact_value"],
        "unit": "USD_million",
        "citations": [answer_id],
    }
    turn({"final": final}, final=True)
    return {
        "row": {
            "label": "T_G2_01",
            "task_key": "G2",
            "arm": "T",
            "id": "constructed-closeout",
            "formula_driven_trace_verified": True,
            "answer_calculation_id": answer_id,
        },
        "public": public,
        "result": {"final": final},
        "turns": turns,
    }


def evidence(session, index):
    return [{"response_index": index, "quote": session["turns"][index]["raw"].decode()}]


def source(session, index, source_id, **extra):
    return {
        "kind": "source",
        "source_id": source_id,
        "attribution": "reviewer_interpretation",
        "declaration_pointer": None,
        "evidence": evidence(session, index),
        "role": "explicit synthetic source role",
        "period": "2020",
        "unit": "USD_million",
        **extra,
    }


def result_reference(session, index, result_id):
    return {"kind": "result", "result_id": result_id, "evidence": evidence(session, index)}


def mapping(session, occurrences):
    return {
        "occurrences": occurrences,
        "event_annotations": [
            {
                "response_index": index,
                "role": "Final" if turn["event"]["final"] else "calculation",
                "interpretation": "Reviewed synthetic public event semantics.",
                "evidence": evidence(session, index),
            }
            for index, turn in enumerate(session["turns"])
        ],
        "revisions": [],
        "cross_checks": [],
    }


def direct():
    session = make_session([{"arguments": {"expression": "10-4"}}])
    ledger = mapping(
        session,
        {
            "tool:1": {
                "body.left": source(session, 0, "source:a"),
                "body.right": source(session, 0, "source:b"),
            }
        },
    )
    return session, ledger


def projected(session, ledger):
    output = project_session(session, ledger, GOAL)
    assert output["status"] == "MAPPED", output["reason"]
    return output


def test_literal_sources_are_evidenced_without_rewriting_model_or_execution():
    session, ledger = direct()
    original = copy.deepcopy(session)
    output = projected(session, ledger)
    assert session == original
    assert output["behavior_signature"]["fixed_condition"] == condition()["id"]
    assert output["behavior_signature"]["active_support"] == ["source:a", "source:b"]
    assert output["raw_public_sequence"][0]["raw_response"] == session["turns"][0]["raw"].decode()
    assert output["offline_normalization_adaptations"][0]["original_expression"] == "10-4"
    assert output["offline_normalization_adaptations"][0][
        "derived_expression_is_not_model_formula_or_execution"
    ]


@pytest.mark.parametrize(
    "mutation",
    (
        "foreign_source",
        "wrong_value",
        "future_evidence",
        "missing_event",
        "unconsumed_address",
        "missing_scale_reason",
    ),
)
def test_unresolved_source_or_history_mapping_preserves_validity(mutation):
    session, ledger = direct()
    occurrence = ledger["occurrences"]["tool:1"]["body.left"]
    if mutation == "foreign_source":
        occurrence["source_id"] = "another-document:a"
    elif mutation == "wrong_value":
        occurrence["source_id"] = "source:b"
    elif mutation == "future_evidence":
        occurrence["evidence"] = evidence(session, 1)
    elif mutation == "missing_event":
        ledger["event_annotations"].pop()
    elif mutation == "unconsumed_address":
        ledger["occurrences"]["tool:1"]["body.unused"] = source(session, 0, "source:c")
    else:
        occurrence.update(source_id="source:d", scale="-5")
    output = project_session(session, ledger, GOAL)
    assert output["status"] == "UNDETERMINED"
    assert output["behavior_key"] is None
    assert output["original_validity_preserved"] is True
    assert session["row"]["formula_driven_trace_verified"] is True


def test_explicit_model_declaration_pointer_must_match_original_arguments():
    session = make_session(
        [
            {
                "arguments": {
                    "expression": "x-y",
                    "variables": {"x": {"value": 10, "source_id": "source:a"}, "y": 4},
                }
            }
        ]
    )
    ledger = mapping(
        session,
        {
            "tool:1": {
                "body.left": source(
                    session,
                    0,
                    "source:a",
                    attribution="model_declaration",
                    declaration_pointer=["variables", "x", "source_id"],
                ),
                "body.right": source(session, 0, "source:b"),
            }
        },
    )
    output = projected(session, ledger)
    assert (
        output["source_mapping_ledger"][0]["source_association_attribution"] == "model_declaration"
    )
    ledger["occurrences"]["tool:1"]["body.left"]["declaration_pointer"] = ["variables", "y"]
    assert project_session(session, ledger, GOAL)["status"] == "UNDETERMINED"


def test_actual_result_references_unfold_and_equal_valued_literals_do_not():
    session = make_session(
        [
            {"arguments": {"expression": "10-4"}},
            {
                "arguments": {
                    "expression": "prior+6",
                    "variables": {"prior": {"result_id": "tool:1"}},
                }
            },
        ]
    )
    ledger = mapping(
        session,
        {
            "tool:1": {
                "body.left": source(session, 0, "source:a"),
                "body.right": source(session, 0, "source:b"),
            },
            "tool:2": {
                "body.left": result_reference(session, 1, "tool:1"),
                "body.right": source(session, 1, "source:c"),
            },
        },
    )
    split = projected(session, ledger)
    whole = make_session([{"arguments": {"expression": "10-4+6"}}])
    whole_ledger = mapping(
        whole,
        {
            "tool:1": {
                "body.left.left": source(whole, 0, "source:a"),
                "body.left.right": source(whole, 0, "source:b"),
                "body.right": source(whole, 0, "source:c"),
            }
        },
    )
    assert split["behavior_key"] == projected(whole, whole_ledger)["behavior_key"]
    fake = make_session(
        [{"arguments": {"expression": "10-4"}}, {"arguments": {"expression": "6+6"}}]
    )
    fake_ledger = mapping(
        fake,
        {
            "tool:1": {
                "body.left": source(fake, 0, "source:a"),
                "body.right": source(fake, 0, "source:b"),
            },
            "tool:2": {
                "body.left": result_reference(fake, 1, "tool:1"),
                "body.right": source(fake, 1, "source:c"),
            },
        },
    )
    assert project_session(fake, fake_ledger, GOAL)["status"] == "UNDETERMINED"


def test_unused_variable_numbers_do_not_become_sources_or_classes():
    session = make_session(
        [{"arguments": {"expression": "x-y", "variables": {"x": 10, "y": 4, "unused": 6}}}]
    )
    ledger = mapping(
        session,
        {
            "tool:1": {
                "body.left": source(session, 0, "source:a"),
                "body.right": source(session, 0, "source:b"),
            }
        },
    )
    first = projected(session, ledger)
    literal, literal_ledger = direct()
    assert first["behavior_key"] == projected(literal, literal_ledger)["behavior_key"]
    assert len(first["source_mapping_ledger"]) == 2


def test_reviewed_negative_source_magnitude_adapts_only_offline_ast():
    magnitude = make_session([{"arguments": {"expression": "10-2"}}])
    magnitude_ledger = mapping(
        magnitude,
        {
            "tool:1": {
                "body.left": source(magnitude, 0, "source:a"),
                "body.right": source(
                    magnitude,
                    0,
                    "source:d",
                    scale="-1",
                    scale_reason="Subtraction uses the positive magnitude of the signed decrease.",
                ),
            }
        },
    )
    output = projected(magnitude, magnitude_ledger)
    signed = make_session([{"arguments": {"expression": "a+d", "variables": {"a": 10, "d": -2}}}])
    signed_ledger = mapping(
        signed,
        {
            "tool:1": {
                "body.left": source(signed, 0, "source:a"),
                "body.right": source(signed, 0, "source:d"),
            }
        },
    )
    assert output["behavior_key"] == projected(signed, signed_ledger)["behavior_key"]
    occurrence = output["source_mapping_ledger"][1]
    assert occurrence["actual_consumed_exact"] == "2"
    assert occurrence["source_exact"] == "-2"
    assert occurrence["normalization_scale"] == "-1"
    assert (
        output["actual_execution_and_support"]["calls"][0]["call"]["arguments"]["expression"]
        == "10-2"
    )


def test_real_scalar_source_read_unfolds_when_consumed_not_merely_read():
    session = make_session(
        [
            {"tool": "read_source", "arguments": {"locators": ["source:a"]}},
            {"arguments": {"expression": "read-4", "variables": {"read": {"result_id": "tool:1"}}}},
        ]
    )
    ledger = mapping(
        session,
        {
            "tool:2": {
                "body.left": result_reference(session, 1, "tool:1"),
                "body.right": source(session, 1, "source:b"),
            }
        },
    )
    output = projected(session, ledger)
    literal, literal_ledger = direct()
    assert output["behavior_key"] == projected(literal, literal_ledger)["behavior_key"]
    assert len(output["source_read_events"]) == 1
    assert output["actual_execution_and_support"]["dependency_edges"] == [
        {"producer_call_id": "tool:1", "consumer_call_id": "tool:2", "kind": "actual_result_id"}
    ]
    unused = make_session(
        [
            {"tool": "read_source", "arguments": {"locators": ["source:c"]}},
            {"arguments": {"expression": "10-4"}},
        ]
    )
    unused_ledger = mapping(
        unused,
        {
            "tool:2": {
                "body.left": source(unused, 1, "source:a"),
                "body.right": source(unused, 1, "source:b"),
            }
        },
    )
    assert (
        projected(unused, unused_ledger)["behavior_key"]
        == projected(literal, literal_ledger)["behavior_key"]
    )


def test_substantive_revision_is_retained_even_when_final_formula_matches():
    session = make_session(
        [{"arguments": {"expression": "6"}}, {"arguments": {"expression": "10-4"}}]
    )
    ledger = mapping(
        session,
        {
            "tool:1": {"body": source(session, 0, "source:c")},
            "tool:2": {
                "body.left": source(session, 1, "source:a"),
                "body.right": source(session, 1, "source:b"),
            },
        },
    )
    ledger["event_annotations"][0]["role"] = "superseded_calculation"
    ledger["revisions"] = [
        {
            "change_kind": "substantive",
            "before_index": 0,
            "after_index": 1,
            "interpretation": "The model changed the documented support route.",
            "semantic_key": {"from_support": ["source:c"], "to_support": ["source:a", "source:b"]},
            "evidence": evidence(session, 0) + evidence(session, 1),
        }
    ]
    revised = projected(session, ledger)
    plain, plain_ledger = direct()
    unrevised = projected(plain, plain_ledger)
    assert (
        revised["behavior_signature"]["answer_source_normal_form"]
        == unrevised["behavior_signature"]["answer_source_normal_form"]
    )
    assert revised["behavior_key"] != unrevised["behavior_key"]


def test_format_only_recovery_retains_error_but_does_not_create_semantic_class():
    session = make_session(
        [
            {"tool": "format_error"},
            {"arguments": {"expression": "x-y", "variables": {"x": 10, "y": 4}}},
        ]
    )
    ledger = mapping(
        session,
        {
            "tool:1": {
                "body.left": source(session, 1, "source:a"),
                "body.right": source(session, 1, "source:b"),
            }
        },
    )
    assert project_session(session, ledger, GOAL)["status"] == "UNDETERMINED"
    ledger["revisions"] = [
        {
            "change_kind": "format_only",
            "before_index": 0,
            "after_index": 1,
            "interpretation": "Synthetic syntax repair; no substantive semantic change asserted.",
            "semantic_key": None,
            "evidence": evidence(session, 0) + evidence(session, 1),
        }
    ]
    repaired = projected(session, ledger)
    plain, plain_ledger = direct()
    assert repaired["behavior_key"] == projected(plain, plain_ledger)["behavior_key"]
    assert repaired["raw_public_sequence"][0]["event"]["tool_call"] is None


def test_independent_executed_cross_check_is_retained_and_unknown_check_unresolved():
    session = make_session(
        [
            {"arguments": {"expression": "10-4"}},
            {
                "arguments": {"expression": "6"},
                "message": "Verify the task amount using an independent disclosed source.",
            },
        ],
        answer_id="tool:1",
    )
    ledger = mapping(
        session,
        {
            "tool:1": {
                "body.left": source(session, 0, "source:a"),
                "body.right": source(session, 0, "source:b"),
            },
            "tool:2": {"body": source(session, 1, "source:c")},
        },
    )
    assert project_session(session, ledger, GOAL)["status"] == "UNDETERMINED"
    ledger["cross_checks"] = [
        {
            "call_id": "tool:2",
            "interpretation": "The executed alternate-source estimate checks the task answer.",
            "evidence": evidence(session, 1),
        }
    ]
    checked = projected(session, ledger)
    plain, plain_ledger = direct()
    assert checked["behavior_key"] != projected(plain, plain_ledger)["behavior_key"]
    assert len(checked["behavior_signature"]["evidenced_independent_cross_checks"]) == 1
    ledger["cross_checks"][0]["call_id"] = "tool:99"
    assert project_session(session, ledger, GOAL)["status"] == "UNDETERMINED"


def test_answer_derived_equal_value_is_not_an_independent_cross_check():
    session = make_session(
        [
            {"arguments": {"expression": "10-4"}},
            {
                "arguments": {
                    "expression": "answer+6-6",
                    "variables": {"answer": {"result_id": "tool:1"}},
                }
            },
        ],
        answer_id="tool:1",
    )
    ledger = mapping(
        session,
        {
            "tool:1": {
                "body.left": source(session, 0, "source:a"),
                "body.right": source(session, 0, "source:b"),
            },
            "tool:2": {
                "body.left.left": result_reference(session, 1, "tool:1"),
                "body.left.right": source(session, 1, "source:c"),
                "body.right": source(session, 1, "source:e"),
            },
        },
    )
    ledger["cross_checks"] = [
        {
            "call_id": "tool:2",
            "interpretation": "Claimed check should be rejected as answer-derived.",
            "evidence": evidence(session, 1),
        }
    ]
    output = project_session(session, ledger, GOAL)
    assert output["status"] == "UNDETERMINED"
    assert output["reason"] == "projection.cross_check_not_derived_from_answer"
