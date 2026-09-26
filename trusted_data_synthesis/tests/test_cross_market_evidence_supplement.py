"""Pure source-boundary controls, no PDF/API/model execution."""

import copy

import pytest
import register_cross_market_evidence_supplement_20260926 as m


def fixture():
    docs = [dict(raw_object_id=f"r{i}") for i in range(440)]
    roster = [dict(security_id=f"s{i}", documents=docs[i::64]) for i in range(64)]
    return dict(
        source=dict(metadata_inventory=dict(roster=roster)),
        candidate_extraction=dict(candidate_count=9513),
        text_audit=dict(candidates_reviewed=9513, pages=104439, empty_text_pages=420),
        blocked_panel=dict(
            passed=False,
            panel_ready=False,
            evaluation_started=False,
            evaluation_panel_references=None,
            candidate_admission_counts=dict(
                dual_sufficient=14, composition_required=0, other_financial=25
            ),
        ),
    )


def test_original_frozen_universe_and_failure_accepted_without_mutation():
    inputs = fixture()
    saved = copy.deepcopy(inputs)
    securities, docs = m.verify_invariants(inputs)
    assert len(securities) == 64 and len(docs) == 440
    assert inputs == saved


@pytest.mark.parametrize(
    "field", ["documents", "candidates", "pages", "renders", "passed", "quota"]
)
def test_cannot_expand_sources_or_rewrite_failure(field):
    values = fixture()
    if field == "documents":
        values["source"]["metadata_inventory"]["roster"][0]["documents"].pop()
    elif field == "candidates":
        values["candidate_extraction"]["candidate_count"] += 1
    elif field == "pages":
        values["text_audit"]["pages"] += 1
    elif field == "renders":
        values["text_audit"]["empty_text_pages"] += 1
    elif field == "passed":
        values["blocked_panel"]["passed"] = True
    else:
        values["blocked_panel"]["candidate_admission_counts"]["dual_sufficient"] = 60
    with pytest.raises(ValueError):
        m.verify_invariants(values)
