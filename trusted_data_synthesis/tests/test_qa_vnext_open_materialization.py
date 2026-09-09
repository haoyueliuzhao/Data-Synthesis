"""New open-interaction joins and attributed views, without empirical relation measurement.

All projection calls below use constructed fixtures and a monkeypatched fixture ledger.
The one real-population check reads immutable source bindings only: it never projects,
compares, normalizes, or tokenizes any real response.
"""

from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_open_materialization import projection, source
from trusted_synthesis.experiments.finance_qa_vnext_open_materialization.plan import (
    encode,
    record,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    request_body,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_LABEL = "synthetic-T-control"
FIXTURE_TASK = "synthetic-task-not-panel"


def constructed_session(*, literal=False, with_error=False, with_message=False):
    public = {
        "id": "synthetic-document",
        "task_id": "synthetic-task-version",
        "question": "A constructed balance change control, not a panel question.",
        "numeric_catalog": [
            {"id": "source:a", "segment": "p0", "value": "17", "token": "17"},
            {"id": "source:b", "segment": "p1", "value": "5", "token": "5"},
        ],
        "segments": {
            "p0": {"text": "Closing balance: 17 units.", "locator": ["pre_text", 0]},
            "p1": {"text": "Opening balance: 5 units.", "locator": ["pre_text", 1]},
        },
    }
    row = {
        "label": FIXTURE_LABEL,
        "arm": "T",
        "task_key": FIXTURE_TASK,
        "id": "synthetic-parent-review",
        "formula_driven_trace_verified": True,
        "answer_calculation_id": "tool:1",
        "semantic_review": {
            field: {"status": "PASS"}
            for field in ("formula_applicability", "variable_correspondence", "unit_handling")
        },
    }
    arguments = {
        "expression": "17 - 5" if literal else "x - y",
        "sources": {"closing": "source:a", "opening": "source:b"},
        "variables": {}
        if literal
        else {
            "x": {"value": "17", "source": "source:a"},
            "y": {"value": "5", "source": "source:b"},
        },
    }
    call = {
        "id": "tool:1",
        "name": "calculate",
        "arguments": arguments,
        "output": {
            "call_id": "tool:1",
            "tool": "calculate",
            "status": "ok",
            "result": {
                "expression": arguments["expression"],
                "exact_value": "12",
                "resolved_variables": {}
                if literal
                else {
                    "x": {"exact_value": "17", "result_id": None},
                    "y": {"exact_value": "5", "result_id": None},
                },
                "financial_meaning_certified": False,
                "source_declarations_validated": False,
            },
        },
    }
    calculation = {
        "message": "Change is closing balance minus opening balance, both in units.",
        "tool": "calculate",
        "arguments": arguments,
    }
    final = {"final": {"value": "12", "unit": "units", "result_id": "tool:1"}}
    specifications = []
    if with_error:
        specifications.append(
            (
                b'{"tool":"calculate","arguments":{"value":17/1}}',
                None,
                "synthetic_json_error",
                None,
                False,
            )
        )
    if with_message:
        specifications.append(
            (
                b'{"message":"An unreviewed change in scope is contemplated."}',
                {"message": "An unreviewed change in scope is contemplated."},
                None,
                None,
                False,
            )
        )
    specifications.extend(
        [
            (b" \n" + encode(calculation) + b"  ", calculation, None, call, False),
            (
                b' { "final" : { "value" : "12", "unit" : "units", "result_id" : "tool:1" } } ',
                final,
                None,
                None,
                True,
            ),
        ]
    )
    result = {"id": "synthetic-session-result", "final": final["final"]}
    messages = [
        {"role": "system", "content": "Synthetic T instruction; never a real SYSTEM."},
        {"role": "user", "content": encode({"task": public}).decode()},
    ]
    turns = []
    for index, (raw, parsed, error, tool, is_final) in enumerate(specifications):
        request = encode(request_body(messages))
        projected = encode(
            {
                "is_original_http_response": False,
                "choices": [{"message": {"role": "assistant", "content": raw.decode()}}],
            }
        )
        binding = record(
            "open_interaction_binding",
            session_label=row["label"],
            population=row["arm"],
            task_key=row["task_key"],
            source_closeout_id=row["id"],
            session_result_id=result["id"],
            source_document_id=public["id"],
            response_index=index,
            actual_tool_call_id=tool["id"] if tool else None,
            request_sha256=sha(request),
            response_projection_sha256=sha(projected),
            raw_response_sha256=sha(raw),
        )
        event = {
            "response_index": index,
            "raw_sha256": sha(raw),
            "protocol_error": error,
            "tool_call": tool,
            "final": is_final,
        }
        turns.append(
            {
                "binding": binding,
                "request_bytes": request,
                "projection_bytes": projected,
                "raw": raw,
                "input_messages": deepcopy(messages),
                "event": event,
                "parsed": parsed,
            }
        )
        messages.append({"role": "assistant", "content": raw.decode()})
        if error:
            messages.append(
                {"role": "user", "content": encode({"interface_error": error}).decode()}
            )
        elif tool:
            messages.append(
                {"role": "user", "content": encode({"tool_result": tool["output"]}).decode()}
            )
        elif not is_final:
            messages.append(
                {"role": "user", "content": encode({"receipt": "model_message_recorded"}).decode()}
            )
    result["events"] = deepcopy([turn["event"] for turn in turns])
    return {"public": public, "row": row, "result": result, "turns": turns}


@pytest.fixture
def fixture_ledger(monkeypatch):
    monkeypatch.setattr(
        projection,
        "GOALS",
        {
            FIXTURE_TASK: {
                "period": "synthetic period",
                "relation": "closing minus opening",
                "unit": "units",
            }
        },
    )
    monkeypatch.setattr(projection, "CONTEXT", {FIXTURE_TASK: ["p0", "p1"]})
    monkeypatch.setattr(
        projection,
        "SOURCES",
        {
            FIXTURE_TASK: {
                "body.left": ("source:a", "closing balance", "units"),
                "body.right": ("source:b", "opening balance", "units"),
            }
        },
    )
    monkeypatch.setattr(projection, "CONSTANTS", {FIXTURE_TASK: {}})
    monkeypatch.setattr(
        projection,
        "DECLARATIONS",
        {
            FIXTURE_LABEL: {
                "body.left": ["variables", "x", "source"],
                "body.right": ["variables", "y", "source"],
            }
        },
    )
    monkeypatch.setattr(projection, "FORMAT_RECOVERIES", {})


def test_real_population_source_joins_only_without_real_projection(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Real relation measurement is forbidden in pre-freeze controls")

    monkeypatch.setattr(projection, "project_session", forbidden)
    monkeypatch.setattr(projection, "normalize_expression", forbidden)
    report, manifests, sessions, valid = source.load_population(ROOT)
    assert report["registered"] == len(sessions) == 24
    assert set(manifests) == {"preparation", "online", "assessment", "closeout"}
    assert Counter(session["row"]["arm"] for session in valid.values()) == {"T": 10, "A": 2}
    assert sum(len(session["turns"]) for session in sessions.values()) == 44
    for label, session in sessions.items():
        assert session["row"]["label"] == label
        for turn in session["turns"]:
            binding = turn["binding"]
            assert binding["session_label"] == label
            assert binding["population"] == session["row"]["arm"]
            assert binding["response_index"] == turn["event"]["response_index"]
            assert binding["raw_response_sha256"] == sha(turn["raw"])


def test_positive_candidates_preserve_actual_input_target_bytes_and_system():
    session = constructed_session()
    for turn, kind in zip(session["turns"], ("calculate", "Final"), strict=True):
        before = deepcopy(turn)
        candidate = source.positive_candidate(session, turn)
        assert candidate["input_messages"] == turn["input_messages"]
        assert candidate["target_response"].encode() == turn["raw"]
        assert candidate["response_kind"] == kind
        assert candidate["population"] == "T" and candidate["session_label"] == FIXTURE_LABEL
        assert candidate["original_system_preserved"]
        assert candidate["target_only_original_public_model_content"]
        assert not candidate["offline_annotation_inserted_in_target"]
        assert candidate["no_training_weight_assigned"] and turn == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("session_label", "other-session"),
        ("population", "A"),
        ("task_key", "other-task"),
        ("source_closeout_id", "other-review"),
        ("session_result_id", "other-result"),
    ],
)
def test_cross_session_condition_and_parent_binding_swaps_are_rejected(field, value):
    session = constructed_session()
    exchanged = deepcopy(session["turns"][0])
    exchanged["binding"][field] = value
    with pytest.raises(ValueError, match="same_session_and_condition"):
        source.positive_candidate(session, exchanged)


@pytest.mark.parametrize("field", ("request_bytes", "projection_bytes", "raw", "input_messages"))
def test_input_target_or_projection_from_another_turn_is_rejected(field):
    session = constructed_session()
    exchanged = deepcopy(session["turns"][0])
    exchanged[field] = deepcopy(session["turns"][1][field])
    with pytest.raises(ValueError, match="materialize"):
        source.positive_candidate(session, exchanged)


def test_response_index_swap_and_self_rehashed_target_cannot_forge_an_interaction():
    session = constructed_session()
    exchanged = deepcopy(session["turns"][0])
    exchanged["binding"]["response_index"] = 1
    with pytest.raises(ValueError, match="materialize"):
        source.positive_candidate(session, exchanged)
    forged = deepcopy(session["turns"][0])
    forged["raw"] = b'{"final":"a replacement, not the original target"}'
    forged["binding"]["raw_response_sha256"] = sha(forged["raw"])
    forged["event"]["raw_sha256"] = sha(forged["raw"])
    with pytest.raises(ValueError, match="materialize"):
        source.positive_candidate(session, forged)


def test_invalid_parent_is_not_promoted_and_json_error_is_not_a_positive_target():
    session = constructed_session(with_error=True)
    assert source.positive_candidate(session, session["turns"][0]) is None
    candidate = source.positive_candidate(session, session["turns"][1])
    assert session["turns"][0]["raw"].decode() in [
        message["content"] for message in candidate["input_messages"]
    ]
    session["row"]["formula_driven_trace_verified"] = False
    with pytest.raises(ValueError, match="source_joint_valid_only"):
        source.positive_candidate(session, session["turns"][1])


def test_false_final_qualification_cannot_promote_an_original_json_error():
    session = constructed_session(with_error=True)
    exchanged = deepcopy(session["turns"][0])
    exchanged["event"]["protocol_error"] = None
    exchanged["event"]["final"] = True
    with pytest.raises(ValueError, match="materialize"):
        source.positive_candidate(session, exchanged)
    # Even internally aligned event claims cannot make invalid original JSON a Final.
    session["turns"][0]["event"] = deepcopy(exchanged["event"])
    session["result"]["events"][0] = deepcopy(exchanged["event"])
    with pytest.raises(ValueError):
        source.positive_candidate(session, session["turns"][0])


@pytest.mark.parametrize("literal", (False, True))
def test_model_source_declaration_and_executed_variable_are_distinct(fixture_ledger, literal):
    session = constructed_session(literal=literal)
    turn = session["turns"][0]
    path = ["sources", "closing"] if literal else ["variables", "x", "source"]
    item, binding = projection.attribute_source(
        session, turn, "body.left", ("source:a", "closing balance", "units"), path
    )
    assert item["source_association_attribution"] == binding["attribution"] == "model_declaration"
    assert item["execution_kind"] == ("consumed_literal" if literal else "consumed_named_variable")
    assert item["named_variable_value_was_consumed"] is not literal
    assert item["model_source_annotation_present"]
    assert not item["source_annotation_validated_by_tool"]
    assert item["executed_exact"] == "17" and binding["evidence_verified"]
    assert item["model_evidence"]["quote"].encode() == turn["raw"]
    assert item["finite_semantic_review_not_automatic_certification"]


def test_reviewer_attribution_is_explicit_not_fabricated_model_source_declaration(fixture_ledger):
    session = constructed_session(literal=True)
    turn = session["turns"][0]
    item, binding = projection.attribute_source(
        session, turn, "body.left", ("source:a", "closing balance", "units"), None
    )
    assert (
        item["source_association_attribution"]
        == binding["attribution"]
        == "reviewer_interpretation"
    )
    assert item["model_source_declaration_pointer"] is None
    assert not item["named_variable_value_was_consumed"]
    assert not item["model_source_annotation_present"]
    assert not item["source_annotation_validated_by_tool"]
    assert item["no_match_by_numeric_value_search"]
    assert item["parent_semantic_review_id"] == session["row"]["id"]


def test_same_number_without_a_ledger_or_public_role_evidence_is_not_a_binding(
    fixture_ledger, monkeypatch
):
    session = constructed_session(literal=True)
    turn = session["turns"][0]
    monkeypatch.setattr(projection, "DECLARATIONS", {})
    with pytest.raises(ValueError, match="no_automatic_literal_binding"):
        projection.attribute_source(
            session, turn, "body.left", ("source:a", "closing balance", "units"), None
        )
    monkeypatch.setattr(projection, "DECLARATIONS", {FIXTURE_LABEL: {}})
    turn["parsed"].pop("message")
    with pytest.raises(ValueError, match="public_role_evidence_required"):
        projection.attribute_source(
            session, turn, "body.left", ("source:a", "closing balance", "units"), None
        )


def test_unknown_source_wrong_value_and_conflicting_model_id_are_rejected(fixture_ledger):
    session = constructed_session()
    turn = session["turns"][0]
    path = ["variables", "x", "source"]
    with pytest.raises(ValueError, match="source_belongs_to_same_document"):
        projection.attribute_source(
            session, turn, "body.left", ("source:other-document", "closing", "units"), path
        )
    with pytest.raises(ValueError, match="source_vs_actual_value_conflict"):
        projection.attribute_source(
            session, turn, "body.left", ("source:b", "opening", "units"), path
        )
    turn["event"]["tool_call"]["arguments"]["variables"]["x"]["source"] = "source:b"
    with pytest.raises(ValueError, match="actual_model_source_declaration"):
        projection.attribute_source(
            session, turn, "body.left", ("source:a", "closing", "units"), path
        )


def test_synthetic_three_views_keep_raw_relation_and_execution_separate(fixture_ledger):
    session = constructed_session()
    before = deepcopy(session)
    projected = projection.project_session(session)
    assert projected["status"] == "MAPPED"
    assert projected["model_proposed_relation"]["original_expression"] == "x - y"
    assert (
        projected["model_proposed_relation"]["original_public_message"]
        == session["turns"][0]["parsed"]["message"]
    )
    assert projected["model_proposed_relation"]["interpretation_is_not_added_model_text"]
    assert (
        projected["actual_execution_and_support"]["calls"][0]["arguments"]["expression"] == "x - y"
    )
    assert (
        projected["raw_public_sequence"][0]["model_evidence"]["quote"].encode()
        == session["turns"][0]["raw"]
    )
    assert projected["raw_DAG_not_replaced_by_normal_form"] and session == before


def test_known_synthetic_format_recovery_has_no_first_execution_or_positive_error_target(
    fixture_ledger, monkeypatch
):
    session = constructed_session(with_error=True)
    monkeypatch.setattr(
        projection,
        "FORMAT_RECOVERIES",
        {
            FIXTURE_LABEL: {
                "before": 0,
                "after": 1,
                "before_anchor": '"value":17/1',
                "after_anchor": '"value":"17"',
                "before_sha256": sha(session["turns"][0]["raw"]),
                "after_sha256": sha(session["turns"][1]["raw"]),
                "interpretation": "Synthetic JSON scalar representation repair only.",
            }
        },
    )
    projected = projection.project_session(session)
    assert projected["status"] == "MAPPED"
    revision = projected["revisions"][0]
    assert revision["change_kind"] == "format_recovery"
    assert revision["before_execution"] is None and revision["after_execution"] == "tool:1"
    assert len(projected["raw_public_sequence"]) == 3
    assert len(projected["actual_execution_and_support"]["calls"]) == 1
    assert source.positive_candidate(session, session["turns"][0]) is None
    assert [entry["response_index"] for entry in revision["model_evidence"]] == [0, 1]


def test_unresolved_format_repair_is_undetermined_not_an_assumed_new_method(fixture_ledger):
    projected = projection.project_session(constructed_session(with_error=True))
    assert projected["status"] == "UNDETERMINED"
    assert projected["reason"] == "repair_semantics_unresolved"
    assert projected["behavior_key"] is None and projected["behavior_signature"] is None
    assert projected["revisions"][0]["kind"] == "repair_semantics_unresolved"


def test_same_format_anchor_without_frozen_full_response_bytes_is_undetermined(
    fixture_ledger, monkeypatch
):
    session = constructed_session(with_error=True)
    monkeypatch.setattr(
        projection,
        "FORMAT_RECOVERIES",
        {
            FIXTURE_LABEL: {
                "before": 0,
                "after": 1,
                "before_anchor": '"value":17/1',
                "after_anchor": '"value":"17"',
                "before_sha256": sha(session["turns"][0]["raw"]),
                "after_sha256": sha(session["turns"][1]["raw"]),
                "interpretation": "Applies only to the fully specified synthetic responses.",
            },
        },
    )
    session["turns"][0]["raw"] += b" "
    session["turns"][0]["binding"]["raw_response_sha256"] = sha(session["turns"][0]["raw"])
    revisions, known = projection.validate_format_recovery(session)
    assert not known and revisions[0]["kind"] == "repair_semantics_unresolved"
    projected = projection.project_session(session)
    assert projected["status"] == "UNDETERMINED" and projected["behavior_key"] is None


def test_missing_ledger_or_unreviewed_public_revision_stays_undetermined(
    fixture_ledger, monkeypatch
):
    session = constructed_session(with_message=True)
    projected = projection.project_session(session)
    assert projected["status"] == "UNDETERMINED"
    assert (
        projected["reason"] == "unreviewed_public_semantic_history"
        and projected["behavior_key"] is None
    )
    monkeypatch.setattr(projection, "DECLARATIONS", {})
    projected = projection.project_session(constructed_session())
    assert (
        projected["status"] == "UNDETERMINED"
        and projected["reason"] == "no_frozen_occurrence_ledger"
    )
    assert projected["behavior_key"] is None


def test_format_recovery_cannot_relabel_an_actual_execution_as_unexecuted(
    fixture_ledger, monkeypatch
):
    session = constructed_session(with_error=True)
    monkeypatch.setattr(
        projection,
        "FORMAT_RECOVERIES",
        {
            FIXTURE_LABEL: {
                "before": 0,
                "after": 1,
                "before_anchor": '"value":17/1',
                "after_anchor": '"value":"17"',
                "before_sha256": sha(session["turns"][0]["raw"]),
                "after_sha256": sha(session["turns"][1]["raw"]),
                "interpretation": "Synthetic format-only recovery.",
            }
        },
    )
    session["turns"][0]["event"]["tool_call"] = deepcopy(session["turns"][1]["event"]["tool_call"])
    with pytest.raises(ValueError, match="format_before_unexecuted"):
        projection.validate_format_recovery(session)
