"""Pure synthetic frontier tests: no reviews, provider calls or real admissions."""

import copy

import cross_market_text_frontier_20260927 as m
import pytest
from test_cross_market_panel import fixture


def item(issuer, index, *, year=2022, public_id=None):
    return dict(
        task=dict(
            task_id=f"candidate:{issuer}:{index}",
            group=m.GROUP,
            periods=[
                [f"{year - 2}-01-01", f"{year - 2}-12-31"],
                [f"{year - 1}-01-01", f"{year - 1}-12-31"],
                [f"{year}-01-01", f"{year}-12-31"],
            ],
        ),
        spec=dict(
            task_id=public_id or f"public:{issuer}:{index:04}",
            group=m.GROUP,
            issuer_cluster_id="issuer:" + m.base.sha(issuer),
        ),
    )


def verdicts(passed=(), rejected=()):
    return dict(passed_task_ids=list(passed), rejected_task_ids=list(rejected))


def test_eligible_items_reuses_real_helpers_for_all_three_groups_without_review(monkeypatch):
    tasks, documents, mapping = [], {}, {}
    for index, group in enumerate(m.panel.GROUPS):
        task, docs, issuer = fixture(index=index, group=group)
        tasks.append(task)
        documents.update(docs)
        mapping[issuer["security_id"]] = issuer
    before = copy.deepcopy((tasks, documents, mapping))
    monkeypatch.setattr(
        m.panel,
        "require_composition_review",
        lambda *_: pytest.fail("preflight cannot mint or require an existing review"),
    )
    rows, rejected = m.eligible_items(tasks, documents, mapping, m.panel.financial.METRICS)
    assert not rejected and {row["task"]["group"] for row in rows} == set(m.panel.GROUPS)
    assert (tasks, documents, mapping) == before
    assert all("review" not in row for row in rows)
    assert all(set(row) == {"task", "spec", "public", "visible", "rank"} for row in rows)


@pytest.mark.parametrize("failure", ["issuer", "document", "fact_join", "public_ambiguity"])
def test_real_nonsemantic_failures_are_retained_not_passed(failure):
    task, documents, issuer = fixture(group=m.GROUP)
    doc = next(iter(documents.values()))
    if failure == "issuer":
        issuer["exposure"]["project_source_identity_screen_passed"] = False
    elif failure == "document":
        issuer["document_bindings"][0]["raw_sha256"] = "changed"
    elif failure == "fact_join":
        task["fact_ids"].append("absent")
    else:
        changed = copy.deepcopy(doc["qualified_facts"][0])
        changed["fact_id"] = "conflicting-public-fact"
        changed["native_pointer"] += "&conflict=1"
        changed["record"]["val"] = "999999999"
        doc["qualified_facts"].append(changed)
    rows, rejected = m.eligible_items(
        [task], documents, {issuer["security_id"]: issuer}, m.panel.financial.METRICS
    )
    assert not rows and len(rejected) == 1
    assert rejected[0]["candidate_task_id"] == task["task_id"] and rejected[0]["reason"]


def test_duplicate_target_tiebreak_matches_old_latest_rank_rule():
    task, documents, issuer = fixture(group=m.GROUP)
    other = copy.deepcopy(task)
    task["task_id"], other["task_id"] = "candidate:a", "candidate:z"
    rows, rejected = m.eligible_items(
        [other, task], documents, {issuer["security_id"]: issuer}, m.panel.financial.METRICS
    )
    assert not rejected and len(rows) == 1 and rows[0]["task"]["task_id"] == "candidate:z"


def test_original_hash_roundrobin_then_endperiod_then_public_id():
    rows = [item(issuer, i) for issuer in ("A", "B", "C") for i in range(3)]
    rows.append(item("A", 99, year=2021))
    before = copy.deepcopy(rows)
    issuers = sorted(
        {r["spec"]["issuer_cluster_id"] for r in rows},
        key=lambda key: m.base.sha(m.panel.SALT + key),
    )
    ordered = m.ordered(list(reversed(rows)))
    assert [r["spec"]["issuer_cluster_id"] for r in ordered[:3]] == issuers
    same_issuer = [
        r for r in ordered if r["spec"]["issuer_cluster_id"] == rows[0]["spec"]["issuer_cluster_id"]
    ]
    assert [r["task"]["periods"][-1][1] for r in same_issuer] == [
        "2021-12-31",
        "2022-12-31",
        "2022-12-31",
        "2022-12-31",
    ]
    assert [r["spec"]["task_id"] for r in same_issuer[1:]] == sorted(
        r["spec"]["task_id"] for r in same_issuer[1:]
    )
    assert rows == before


def test_rejection_rebuilds_each_issuer_bucket_not_old_global_list(monkeypatch):
    monkeypatch.setattr(m, "QUOTA", 3)
    rows = [item(issuer, i) for issuer in ("A", "B") for i in range(3)]
    old = m.ordered(rows)
    rejected = {old[0]["task"]["task_id"]}
    revised = m.next_selected(rows, rejected)
    assert revised[0]["task"]["task_id"] == old[2]["task"]["task_id"]
    assert revised[1]["task"]["task_id"] == old[1]["task"]["task_id"]
    assert revised != [r for r in old if r["task"]["task_id"] not in rejected][:3]


def test_missing_or_technical_pending_never_replaced_by_sixty_later_passes():
    rows = [item("one issuer", i) for i in range(61)]
    sorted_rows = m.ordered(rows)
    passed = [r["task"]["task_id"] for r in sorted_rows[1:]]
    report = m.closure(rows, verdicts(passed))
    assert report["explicit_pass_count"] == 60 and report["closed"] is False
    assert report["pending_task_ids"] == [sorted_rows[0]["task"]["task_id"]]
    assert not report["selected_task_ids"]
    assert report["passed_outside_optimistic_frontier"] == [sorted_rows[-1]["task"]["task_id"]]
    assert report["missing_review_is_not_rejection"] is True


def test_actual_explicit_reject_may_advance_but_is_not_created_by_closure():
    rows = [item("one issuer", i) for i in range(61)]
    ordered = m.ordered(rows)
    passed = [r["task"]["task_id"] for r in ordered[1:]]
    rejected = [ordered[0]["task"]["task_id"]]
    report = m.closure(rows, verdicts(passed, rejected))
    assert report["closed"] is True and report["selected_task_ids"] == passed
    assert report["explicit_rejected_task_ids"] == rejected
    assert report["semantic_certificate_created"] is False
    assert report["caller_must_validate_original_review_evidence"] is True


def test_later_missing_reviews_do_not_prevent_a_closed_prefix():
    rows = [item("one issuer", i) for i in range(80)]
    first60 = [r["task"]["task_id"] for r in m.ordered(rows)[:60]]
    report = m.closure(rows, verdicts(first60))
    assert report["closed"] and report["selected_task_ids"] == first60
    assert report["pending_task_ids"] == [] and report["explicit_reject_count"] == 0


def test_59_admissible_tasks_is_shortage_even_if_all_passed():
    rows = [item("one issuer", i) for i in range(59)]
    report = m.closure(rows, verdicts([r["task"]["task_id"] for r in rows]))
    assert report["status"] == "PREDECLARED_POOL_EXHAUSTED_BELOW_QUOTA"
    assert not report["closed"] and not report["selected_task_ids"]


@pytest.mark.parametrize(
    "reviews",
    [
        {"passed_task_ids": ["unknown"], "rejected_task_ids": []},
        {"passed_task_ids": ["candidate:A:0"], "rejected_task_ids": ["candidate:A:0"]},
        {"passed_task_ids": ["candidate:A:0", "candidate:A:0"], "rejected_task_ids": []},
        {"passed_task_ids": [], "rejected_task_ids": [], "technical_pending_is_reject": True},
    ],
)
def test_unknown_duplicate_contradictory_or_implicit_verdicts_fail(reviews):
    with pytest.raises(ValueError):
        m.closure([item("A", 0)], reviews)


def test_ordered_requires_unique_composition_items():
    row = item("A", 0)
    with pytest.raises(ValueError, match="unique_candidate"):
        m.ordered([row, copy.deepcopy(row)])
    changed = copy.deepcopy(row)
    changed["task"]["group"] = "dual_sufficient"
    with pytest.raises(ValueError, match="composition_items_only"):
        m.ordered([changed])
