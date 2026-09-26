"""Synthetic issuer/PDF candidate fixtures, never actual model or source calls."""

import copy

import cross_market_panel_20260926 as m
import pytest


def fixture(index=0, group="dual_sufficient", relative=False):
    security = f"hkex_disclosures:{index:05d}"
    cluster = "issuer:" + m.base.sha(security)
    periods = [
        [f"{year}-01-01", f"{year}-12-31"]
        for year in range(2020, 2022 if group == "dual_sufficient" else 2023)
    ]
    raw_id = "raw_pdf:" + str(index)
    digest = m.base.sha(raw_id)
    doc = dict(
        raw_object_id=raw_id,
        security_id=security,
        sha256=digest,
        original_url=f"https://www1.hkexnews.hk/{index}.pdf",
        source_id="hkex_disclosures",
        publish_date="2023-04-01",
        path=f"/synthetic/{index}.pdf",
        bytes=999,
    )
    facts = []

    def fact(metric, period, amount):
        fid = f"fact:{index}:{len(facts)}"
        row = len(facts)
        f = dict(
            fact_id=fid,
            candidate_id=fid,
            security_id=security,
            entity_id="unresolved_security:" + security,
            issuer_cluster_id=None,
            source_id="hkex_disclosures",
            source_definition_id="definition:" + metric,
            raw_object_id=raw_id,
            raw_sha256=digest,
            original_url=doc["original_url"],
            native_pointer=f"pdf://{digest}#page=5&row={row}",
            metric_id=metric,
            label=metric,
            native_definition=dict(metric_id=metric, basis="HKFRS"),
            currency="HKD",
            unit="HKD",
            original_unit="HK$ million",
            value_scale="million",
            original_value=str(amount),
            record=dict(start=period[0], end=period[1], val=str(amount)),
            statement_scope="consolidated_entity",
            source_publish_date=doc["publish_date"],
            status="FINANCIALLY_QUALIFIED_ISSUER_PENDING",
            evidence=dict(
                page=5,
                table="T",
                row=row,
                period_slot=1,
                parser_word_index=row,
                raw_value_text=str(amount),
                unit_header="HKD",
            ),
        )
        facts.append(f)
        return f

    relations = []
    if group == "dual_sufficient":
        previous, current = (
            fact("gross_profit", periods[0], 20000000),
            fact("gross_profit", periods[1], 30000000),
        )
        for period, gross, revenue, cost in (
            (periods[0], previous, 100000000, -80000000),
            (periods[1], current, 120000000, -90000000),
        ):
            rev, expense = fact("revenue", period, revenue), fact("cost_of_revenue", period, cost)
            relations.append(
                dict(
                    complete=True,
                    gross_profit_fact_id=gross["fact_id"],
                    revenue_fact_id=rev["fact_id"],
                    cost_fact_id=expense["fact_id"],
                    cost_coefficient=1,
                )
            )
        quantity, metric, secondary, answer = (
            ("relative_change" if relative else "difference"),
            "gross_profit",
            None,
            ("50" if relative else "10000000"),
        )
    elif group == "composition_required":
        for period, amount in zip(periods, (1000000, 2000000, 3000000), strict=True):
            fact("revenue", period, amount)
        quantity, metric, secondary, answer = "three_year_mean", "revenue", None, "2000000"
    else:
        for period, amount in zip(periods, (1000000, 3000000, 2000000), strict=True):
            fact("revenue", period, amount)
        for period, amount in zip(periods, (400000, 700000, 600000), strict=True):
            fact("net_income", period, amount)
        quantity, metric, secondary, answer = (
            "argmax_then_lookup",
            "revenue",
            "net_income",
            "700000",
        )
    task = dict(
        task_id=f"candidate:{index}:{group}:{quantity}",
        group=group,
        security_id=security,
        periods=periods,
        quantity=quantity,
        metric_id=metric,
        secondary_metric_id=secondary,
        currency="HKD",
        raw_object_ids=[raw_id],
        fact_ids=[row["fact_id"] for row in facts],
        relation_certificates=relations,
        answer_exact=answer,
        vintage_bridge={"exact_native_agreement": True},
    )
    if group == "other_financial":
        task["unique_argmax_period"] = periods[1]
    if group == "composition_required":
        task["source_exhaustion_review_raw_objects"] = [raw_id]
    page_text = dict(path=f"/synthetic/{index}.pages.json", sha256="a" * 64, bytes=100)
    qualified = dict(
        id="qualified-document:" + str(index),
        document=doc,
        qualified_facts=facts,
        input_references={"text_bundle": page_text},
    )
    issuer = dict(
        security_id=security,
        issuer_cluster_id=cluster,
        legal_name=f"Synthetic Issuer {index}",
        admitted=True,
        exposure={"project_source_identity_screen_passed": True},
        document_bindings=[
            dict(
                raw_object_id=raw_id,
                raw_sha256=digest,
                original_url=doc["original_url"],
                admitted=True,
            )
        ],
    )
    return task, {raw_id: qualified}, issuer


def review(task, documents):
    return m.base.record(
        "cross_market_composition_source_exhaustion_review",
        task_id=task["task_id"],
        financial_protocol_id="financial:synthetic",
        metric_id=task["metric_id"],
        periods=task["periods"],
        passed=True,
        no_same_concept_three_year_aggregate=True,
        all_original_source_pages_reviewed=True,
        review_method="independent_full_source_semantic_review",
        reviewer_id="synthetic_fixture_only",
        sole_basis_is_regex_absence=False,
        documents=[
            dict(
                raw_object_id=key,
                raw_sha256=doc["document"]["sha256"],
                page_text_reference=copy.deepcopy(doc["input_references"]["text_bundle"]),
                all_pages_reviewed=True,
                semantic_review_notes=(
                    "Synthetic fixture explicitly contains only the three annual records."
                ),
                reviewed_relevant_locations=[dict(page=5)],
            )
            for key, doc in documents.items()
        ],
    )


@pytest.mark.parametrize(
    "group,relative",
    [
        ("dual_sufficient", False),
        ("dual_sufficient", True),
        ("composition_required", False),
        ("other_financial", False),
    ],
)
def test_private_certificates_execute_under_real_pdf_runtime(group, relative):
    task, docs, issuer = fixture(group=group, relative=relative)
    spec = m.public_spec(task, issuer, docs)
    public, visible = m.public_sources(
        spec, {key: d["qualified_facts"] for key, d in docs.items()}, m.financial.METRICS
    )
    natives = {
        f["fact_id"]: {
            **f,
            "entity_id": issuer["issuer_cluster_id"],
            "source_cluster": issuer["issuer_cluster_id"],
        }
        for f in visible
    }
    bundle = m.private_bundle(
        task, spec, public, "synthetic-review" if group == "composition_required" else None
    )
    controls = m.scripted_controls(task, spec, public, bundle, natives)
    assert all(row["expected"] is row["observed"] for row in controls), controls


def test_composition_pending_never_admitted():
    task, docs, issuer = fixture(group="composition_required")
    with pytest.raises(ValueError, match="pending_independent"):
        m.require_composition_review(task, docs, {}, "financial:synthetic")


def test_composition_review_content_bound_and_regex_not_enough():
    task, docs, issuer = fixture(group="composition_required")
    evidence = review(task, docs)
    assert (
        m.require_composition_review(task, docs, {task["task_id"]: evidence}, "financial:synthetic")
        == evidence["id"]
    )
    changed = {key: value for key, value in evidence.items() if key not in {"schema_version", "id"}}
    changed["sole_basis_is_regex_absence"] = True
    with pytest.raises(ValueError, match="nonsemantic"):
        m.require_composition_review(
            task,
            docs,
            {
                task["task_id"]: m.base.record(
                    "cross_market_composition_source_exhaustion_review", **changed
                )
            },
            "financial:synthetic",
        )
    docs[next(iter(docs))]["input_references"]["text_bundle"]["sha256"] = "b" * 64
    with pytest.raises(ValueError, match="source_content_binding"):
        m.require_composition_review(task, docs, {task["task_id"]: evidence}, "financial:synthetic")


def test_public_rows_do_not_filter_by_private_solution():
    task, docs, issuer = fixture()
    extras = copy.deepcopy(next(iter(docs.values()))["qualified_facts"][0])
    extras.update(
        fact_id="distractor",
        metric_id="net_income",
        label="net_income",
        source_definition_id="definition:net_income",
        native_pointer=extras["native_pointer"] + "&distractor=1",
    )
    next(iter(docs.values()))["qualified_facts"].append(extras)
    spec = m.public_spec(task, issuer, docs)
    public, visible = m.public_sources(
        spec, {key: d["qualified_facts"] for key, d in docs.items()}, m.financial.METRICS
    )
    assert "distractor" in {row["fact_id"] for row in visible}
    assert any(row["concept"] == "pdf-financial:net_income" for row in public["sources"])
    task["answer_exact"] = "99999999"
    task["relation_certificates"] = []
    assert m.public_spec(task, issuer, docs) == spec


def test_public_conflicting_vintage_rejects_instead_of_selecting_answer_value():
    task, docs, issuer = fixture()
    extra = copy.deepcopy(next(iter(docs.values()))["qualified_facts"][0])
    extra.update(fact_id="conflicting", native_pointer=extra["native_pointer"] + "&conflict=1")
    extra["record"]["val"] = "999"
    next(iter(docs.values()))["qualified_facts"].append(extra)
    with pytest.raises(ValueError, match="ambiguous_native_observation"):
        m.public_sources(
            m.public_spec(task, issuer, docs),
            {key: d["qualified_facts"] for key, d in docs.items()},
            m.financial.METRICS,
        )


def test_history_screen_and_per_document_identity_are_both_required():
    task, docs, issuer = fixture()
    mapping = {issuer["security_id"]: issuer}
    issuer["exposure"]["project_source_identity_screen_passed"] = False
    with pytest.raises(ValueError, match="project_history"):
        m.issuer_join(task, docs, mapping)
    issuer["exposure"]["project_source_identity_screen_passed"] = True
    issuer["document_bindings"][0]["admitted"] = False
    with pytest.raises(ValueError, match="document_identity"):
        m.issuer_join(task, docs, mapping)


def test_quota_shortfall_does_not_tokenize_or_publish_partial_panel():
    task, docs, issuer = fixture()
    admission = m.base.record("cross_market_issuer_admission", rows=[issuer])

    def forbidden(messages):
        raise AssertionError("shortage is not a model input qualification pass")

    result, prepared = m.compile_panel(
        [task], docs, admission, {}, "financial:synthetic", m.financial.METRICS, forbidden
    )
    assert result["passed"] is False
    assert prepared == []
    assert result["candidate_admission_counts"] == {
        "dual_sufficient": 1,
        "composition_required": 0,
        "other_financial": 0,
    }


def test_dedup_by_issuer_target_and_deterministic_order():
    task, docs, issuer = fixture()
    duplicate = {**copy.deepcopy(task), "task_id": "another_vintage_same_target"}
    mapping = {issuer["security_id"]: issuer}
    first = m.choose_tasks(
        [task, duplicate], docs, mapping, {}, "financial:synthetic", m.financial.METRICS
    )
    second = m.choose_tasks(
        [duplicate, task], docs, mapping, {}, "financial:synthetic", m.financial.METRICS
    )
    assert first == second
    assert first[1]["dual_sufficient"] == 1


def panel_fixture():
    tasks, documents, issuers, reviews = [], {}, [], {}
    for group_index, group in enumerate(m.GROUPS):
        for index in range(60):
            task, docs, issuer = fixture(index=group_index * 60 + index, group=group)
            tasks.append(task)
            documents.update(docs)
            issuers.append(issuer)
            if group == "composition_required":
                reviews[task["task_id"]] = review(task, docs)
    return tasks, documents, m.base.record("cross_market_issuer_admission", rows=issuers), reviews


def test_selected_control_failure_cannot_trigger_replacement(monkeypatch):
    tasks, docs, admission, reviews = panel_fixture()
    monkeypatch.setattr(m, "scripted_controls", lambda *args: [dict(expected=True, observed=False)])
    report, prepared = m.compile_panel(
        tasks,
        docs,
        admission,
        reviews,
        "financial:synthetic",
        m.financial.METRICS,
        lambda messages: 100,
    )
    assert report["status"] == "BLOCKED_SELECTED_INPUT_OR_SCRIPTED_CONTROL"
    assert report["no_replacement_after_selected_input_failure"] is True
    assert prepared == []


def test_publish_complete_panel_matches_evaluation_bridge(tmp_path, monkeypatch):
    import fixed_kernel_direction_calibration_evaluation_20260926 as bridge

    monkeypatch.setattr(m.base, "RAW", tmp_path)
    tasks, docs, admission, reviews = panel_fixture()
    # Real symbolic controls are separately tested for all four target forms;
    # this test isolates complete public/private serialization and bridge joins.
    monkeypatch.setattr(m, "scripted_controls", lambda *args: [dict(expected=True, observed=True)])
    report, prepared = m.compile_panel(
        tasks,
        docs,
        admission,
        reviews,
        "financial:synthetic",
        m.financial.METRICS,
        lambda messages: 100,
    )
    assert report["passed"] is True
    plan = dict(
        id="synthetic-panel-protocol",
        runtime_binding=m.runtime.binding(),
        issuer_admission={"id": admission["id"]},
    )
    references = m.publish_panel(tmp_path, plan, report, prepared)
    manifest = bridge.public_manifest({"panel": references})
    assert len(manifest["tasks"]) == 180
    assets = bridge._private_assets(
        {"panel": references}, manifest, {"id": "synthetic-valid-seal-for-unit-test"}
    )
    assert len(assets["bundles"]) == 180
    assert all(row["raw_object_ids"] and "cik" not in row for row in manifest["tasks"])


def test_context_overflow_fails_selected_panel_without_substitution(monkeypatch):
    tasks, docs, admission, reviews = panel_fixture()
    monkeypatch.setattr(m, "scripted_controls", lambda *args: [dict(expected=True, observed=True)])
    report, prepared = m.compile_panel(
        tasks,
        docs,
        admission,
        reviews,
        "financial:synthetic",
        m.financial.METRICS,
        lambda messages: 18433,
    )
    assert report["passed"] is False and prepared == []
    assert len(report["selected_task_ids"]) == 180
