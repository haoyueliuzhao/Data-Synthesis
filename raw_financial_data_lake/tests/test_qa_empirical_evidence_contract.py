from finraw.qa.answer_schema_registry import match_answer, resolve_answer_schema
from finraw.qa.evaluation.empirical import _component_scores


def test_evidence_selection_uses_required_recall_and_precision_not_exact_set() -> None:
    rubric = {"target_value": "10"}
    schema = resolve_answer_schema("numeric", {"type": "numeric"}, rubric)
    expected = {"value": "10"}
    observed = {"value": "10"}
    _, details = match_answer(schema, expected, observed, rubric)
    scores = _component_scores(
        schema,
        expected,
        observed,
        rubric,
        details,
        "evidence_pool",
        {"required": {"required_fact"}, "context": {"context_fact"}},
        {"required_fact", "distractor"},
        0.5,
        api_call_success=True,
        json_contract_success=True,
    )
    assert scores["evidence_selection_correct"] is True
    assert scores["evidence_metrics"]["required_evidence_recall"] == 1.0
    assert scores["evidence_metrics"]["context_evidence_recall"] == 0.0
    assert scores["evidence_metrics"]["evidence_precision"] == 0.5
    assert scores["evidence_metrics"]["exact_set_match"] is False


def test_evidence_selection_fails_when_required_fact_is_missing() -> None:
    rubric = {"target_value": "10"}
    schema = resolve_answer_schema("numeric", {"type": "numeric"}, rubric)
    expected = {"value": "10"}
    observed = {"value": "10"}
    _, details = match_answer(schema, expected, observed, rubric)
    scores = _component_scores(
        schema,
        expected,
        observed,
        rubric,
        details,
        "evidence_pool",
        {"required": {"required_fact"}, "context": {"context_fact"}},
        {"context_fact"},
        0.8,
        api_call_success=True,
        json_contract_success=True,
    )
    assert scores["evidence_selection_correct"] is False
    assert scores["evidence_metrics"]["required_evidence_recall"] == 0.0
