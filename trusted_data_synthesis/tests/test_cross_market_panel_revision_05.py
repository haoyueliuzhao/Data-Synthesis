"""Synthetic-only proof of isolated evidence05 panel and closed selection order."""

import copy
from types import SimpleNamespace

import cross_market_panel_revision_05_20260927 as m
import pytest
from test_cross_market_panel import fixture, panel_fixture

SCOPE = "synthetic_saved_text_table_domain_not_whole_PDF_visual"
REVIEW_KIND = "cross_market_composition_text_table_review"
BUNDLE_KIND = "cross_market_composition_text_table_reviews"


def review(task, passed=True):
    return m.base.record(
        REVIEW_KIND,
        task_id=task["task_id"],
        financial_protocol_id="financial:synthetic",
        passed=passed,
        scope=SCOPE,
    )


@pytest.fixture
def module(monkeypatch):
    def validate(bundle, financial_protocol_id):
        m.base.checked(bundle, BUNDLE_KIND)
        m.require(bundle["financial_protocol_id"] == financial_protocol_id, "synthetic_parent")
        m.require(bundle["scope"] == SCOPE, "synthetic_scope")

    def require_review(task, documents, reviews, financial_protocol_id):
        if task["group"] != "composition_required":
            return None
        value = reviews.get(task["task_id"])
        m.require(value is not None, "synthetic_pending")
        m.base.checked(value, REVIEW_KIND)
        m.require(
            value["passed"] is True
            and value["financial_protocol_id"] == financial_protocol_id
            and value["scope"] == SCOPE,
            "synthetic_invalid_review",
        )
        return value["id"]

    value = SimpleNamespace(
        BUNDLE_KIND=BUNDLE_KIND,
        REVIEW_SCOPE=SCOPE,
        require_composition_review=require_review,
        validate_bundle=validate,
    )
    monkeypatch.setattr(m, "review_module", lambda: value)
    return value


def synthetic_panel():
    tasks, documents, issuer, _ = panel_fixture()
    reviews = {
        task["task_id"]: review(task) for task in tasks if task["group"] == "composition_required"
    }
    return tasks, documents, issuer, reviews


def closed_bundle(tasks, documents, issuer, reviews, rejected=()):
    frontier = m.frontier_module()
    items, _ = frontier.eligible_items(
        tasks, documents, m.core.statistics.admission_mapping(issuer), m.core.financial.METRICS
    )
    items = [item for item in items if item["task"]["group"] == "composition_required"]
    selected = frontier.next_selected(items, set(rejected))
    return m.base.record(
        BUNDLE_KIND,
        financial_protocol_id="financial:synthetic",
        scope=SCOPE,
        reviews=list(reviews.values()),
        selection_closure=dict(
            complete=True,
            eligible_candidate_task_ids=[item["task"]["task_id"] for item in items],
            selected_candidate_task_ids=[item["task"]["task_id"] for item in selected],
            semantically_rejected_candidate_task_ids=list(rejected),
            reviewed_candidate_task_ids=list(set(reviews) | set(rejected)),
        ),
    )


def remake(value, kind, **updates):
    return m.base.record(
        kind, **{k: v for k, v in value.items() if k not in {"id", "schema_version"}} | updates
    )


def test_namespace_isolation_retains_original_question_selection_and_control(module):
    original = m.core.require_composition_review
    namespace = m.compiler_namespace()
    assert m.core.require_composition_review is original
    assert namespace["require_composition_review"] is module.require_composition_review
    assert namespace["question"].__code__ is m.core.question.__code__
    assert namespace["choose_tasks"].__code__ is m.core.choose_tasks.__code__
    assert namespace["scripted_controls"].__code__ is m.core.scripted_controls.__code__


def test_question_renders_period_contract_exactly_once(module, monkeypatch):
    task, documents, issuer = fixture(group="composition_required")
    spec = m.core.public_spec(task, issuer, documents)
    monkeypatch.setattr(
        m.core.period_tools, "render_public_periods", lambda contract: "PERIOD_MARKER"
    )
    assert m.compiler_namespace()["question"](spec).count("PERIOD_MARKER") == 1


def test_new_text_certificate_has_no_old_visual_or_exhaustion_claim(module):
    task, documents, issuer = fixture(group="composition_required")
    namespace = m.compiler_namespace()
    spec = namespace["public_spec"](task, issuer, documents)
    public, visible = namespace["public_sources"](
        spec,
        {key: row["qualified_facts"] for key, row in documents.items()},
        m.core.financial.METRICS,
    )
    bundle = namespace["private_bundle"](task, spec, public, "synthetic-text-review")
    certificate = bundle["private"]["relation_certificate"]
    assert "source_exhaustion_review_id" not in certificate
    assert certificate["source_text_table_review_id"] == "synthetic-text-review"
    assert certificate["full_original_PDF_visual_exhaustion_claimed"] is False
    assert "composition_source_exhaustion_review_id" not in bundle["validation"]
    natives = {
        fact["fact_id"]: {
            **fact,
            "entity_id": spec["issuer_cluster_id"],
            "issuer_cluster_id": spec["issuer_cluster_id"],
            "source_cluster": spec["source_cluster"],
            "issuer_admission_id": "synthetic",
        }
        for fact in visible
    }
    controls = namespace["scripted_controls"](task, spec, public, bundle, natives)
    assert all(row["expected"] is row["observed"] for row in controls)


def test_closed_frontier_recomputes_original_full_candidate_selection(module):
    tasks, docs, issuer, reviews = synthetic_panel()
    bundle = closed_bundle(tasks, docs, issuer, reviews)
    expected = m.validate_selection_closure(tasks, docs, issuer, bundle, "financial:synthetic")
    assert len(expected) == 60
    assert expected == bundle["selection_closure"]["selected_candidate_task_ids"]


@pytest.mark.parametrize(
    "field",
    ["eligible_candidate_task_ids", "selected_candidate_task_ids", "reviewed_candidate_task_ids"],
)
def test_missing_or_changed_closure_members_never_pass(module, field):
    tasks, docs, issuer, reviews = synthetic_panel()
    original = closed_bundle(tasks, docs, issuer, reviews)
    closure = copy.deepcopy(original["selection_closure"])
    closure[field] = closure[field][1:]
    changed = remake(original, BUNDLE_KIND, selection_closure=closure)
    with pytest.raises(ValueError):
        m.validate_selection_closure(tasks, docs, issuer, changed, "financial:synthetic")


def test_selected_pending_or_rejected_is_not_silent_negative(module):
    tasks, docs, issuer, reviews = synthetic_panel()
    original = closed_bundle(tasks, docs, issuer, reviews)
    selected = original["selection_closure"]["selected_candidate_task_ids"][0]
    wrong = copy.deepcopy(reviews)
    wrong[selected] = remake(wrong[selected], REVIEW_KIND, passed=False)
    changed = remake(original, BUNDLE_KIND, reviews=list(wrong.values()))
    with pytest.raises(ValueError, match="all_really_passed"):
        m.validate_selection_closure(tasks, docs, issuer, changed, "financial:synthetic")


def test_unknown_or_shadowed_review_cannot_promote_nonfrontier_candidate(module):
    tasks, docs, issuer, reviews = synthetic_panel()
    original = closed_bundle(tasks, docs, issuer, reviews)
    task, _, _ = fixture(index=999, group="composition_required")
    changed = remake(original, BUNDLE_KIND, reviews=[*original["reviews"], review(task)])
    with pytest.raises(ValueError, match="all_really_passed"):
        m.validate_selection_closure(tasks, docs, issuer, changed, "financial:synthetic")


def test_failed_selected_controls_cannot_select_replacements(module):
    tasks, docs, issuer, reviews = synthetic_panel()
    namespace = m.compiler_namespace()
    namespace["scripted_controls"] = lambda *args: [dict(expected=True, observed=False)]
    report, prepared = namespace["compile_panel"](
        tasks,
        docs,
        issuer,
        reviews,
        "financial:synthetic",
        m.core.financial.METRICS,
        lambda messages: 100,
    )
    assert report["status"] == "BLOCKED_SELECTED_INPUT_OR_SCRIPTED_CONTROL"
    assert report["no_replacement_after_selected_input_failure"] is True
    assert prepared == []


def test_new_panel_serialization_is_accepted_by_existing_cross_market_bridge(
    module, monkeypatch, tmp_path
):
    import fixed_kernel_cross_market_evaluation_20260926 as evaluation

    tasks, docs, issuer, reviews = synthetic_panel()
    namespace = m.compiler_namespace()
    namespace["scripted_controls"] = lambda *args: [dict(expected=True, observed=True)]
    report, prepared = namespace["compile_panel"](
        tasks,
        docs,
        issuer,
        reviews,
        "financial:synthetic",
        m.core.financial.METRICS,
        lambda messages: 100,
    )
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    plan = dict(
        id="synthetic-new-panel",
        runtime_binding=m.core.runtime.binding(),
        issuer_admission={"id": issuer["id"]},
    )
    references = namespace["publish_panel"](tmp_path, plan, report, prepared)
    manifest = evaluation.prior.public_manifest({"panel": references})
    assert len(manifest["tasks"]) == 180
    private = evaluation.prior._private_assets(
        {"panel": references}, manifest, {"id": "synthetic-seal"}
    )
    assert len(private["bundles"]) == 180


def test_missing_review_does_not_run_tokenizer(module):
    tasks, docs, issuer, _ = synthetic_panel()
    namespace = m.compiler_namespace()

    def forbidden(messages):
        raise AssertionError("no tokenizer before quota passes")

    report, prepared = namespace["compile_panel"](
        tasks, docs, issuer, {}, "financial:synthetic", m.core.financial.METRICS, forbidden
    )
    assert report["passed"] is False
    assert prepared == []


def financial_inputs(**overrides):
    body = dict(
        evidence_revision_number=5,
        document_count=440,
        documents=[{}] * 440,
        fixed_original_candidates=9513,
        fixed_supplementary_anchors=20,
        fixed_total_candidate_anchors=9533,
        maximum_anchor_scan_documents=0,
        maximum_new_review_plans=0,
        public_metric_universe=list(m.core.financial.METRICS),
        quotas=m.core.QUOTAS,
    )
    plan = m.base.record(m.financial05.prior.PROTOCOL, **body | overrides)
    candidates = m.base.record(
        "cross_market_financial_task_candidates",
        protocol_id=plan["id"],
        candidates=[dict(group=group) for group in m.core.GROUPS for _ in range(60)],
    )
    summary = m.base.record(
        m.financial05.prior.COMPLETION,
        protocol_id=plan["id"],
        status="FINANCIAL_ENUMERATION_COMPLETE_NOT_EVALUATION_READY",
        documents=440,
        input_candidates=9533,
        original_input_candidates=9513,
        supplementary_input_candidates=20,
        candidate_counts=m.core.QUOTAS,
    )
    return plan, summary, candidates


def test_only_exact_evidence05_inputs_are_accepted():
    assert m.validate_financial_inputs(*financial_inputs()) == m.core.QUOTAS


@pytest.mark.parametrize(
    "changed",
    [
        dict(evidence_revision_number=4),
        dict(fixed_supplementary_anchors=21),
        dict(maximum_anchor_scan_documents=440),
        dict(maximum_new_review_plans=1),
        dict(quotas={group: 59 for group in m.core.GROUPS}),
    ],
)
def test_prior_or_expanded_financial_scope_is_rejected(changed):
    with pytest.raises(ValueError, match="exact_financial05_inputs"):
        m.validate_financial_inputs(*financial_inputs(**changed))


def test_read_review_bundle_requires_unique_task_identity(module, tmp_path, monkeypatch):
    task, _, _ = fixture(group="composition_required")
    one = review(task)
    bundle = m.base.record(
        BUNDLE_KIND,
        financial_protocol_id="financial:synthetic",
        scope=SCOPE,
        reviews=[one, one],
    )
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    path = tmp_path / "reviews.json"
    m.base.write(path, bundle)
    with pytest.raises(ValueError, match="unique_settled_task_reviews"):
        m.review_bundle(path, "financial:synthetic")


def test_actual_new_review_validator_is_wired_without_old_visual_requirement():
    from test_cross_market_text_table_review_revision import (
        assess,
        financial_documents,
    )
    from test_cross_market_text_table_review_revision import fixture as text_fixture

    values = text_fixture()
    result = assess(values)
    assert result["original_visual_content_reviewed"] is False
    namespace = m.compiler_namespace()
    assert (
        namespace["require_composition_review"](
            values[0], financial_documents(values), {"task-1": result}, "financial-plan"
        )
        == result["id"]
    )
