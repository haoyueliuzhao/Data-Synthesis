"""Fixed PDF-native 180-task compiler; pending source-exhaustion never passes.

Only previously qualified facts and separately admitted legal identities enter
this stage. Source selection exposes every preregistered metric in the declared
report vintage/window; private witnesses never filter the public rows. This is
preparatory code until the registered 60/60/60 and scripted-control gates pass.
"""

# ruff: noqa: E501 -- fixed English templates and explicit scientific contracts

from __future__ import annotations

import argparse
import copy
import json
import subprocess
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import cross_market_financial_qualification_20260926 as financial
import cross_market_statistics_20260926 as statistics
import fixed_kernel_cross_market_runtime_20260926 as runtime

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import periods as period_tools
from trusted_synthesis.experiments.finance_qa_vnext_eval_surface.guard import METRIC_NAMES
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
    record as relation_record,
)

base, p = financial.base, runtime.p
SCRIPT = "trusted_data_synthesis/scripts/cross_market_panel_20260926.py"
RAW = base.RAW / "panel_01"
SALT = "cross_market_PDF_panel_20260926.v1:"
GROUPS = financial.GROUPS
QUOTAS = dict.fromkeys(GROUPS, 60)
QUANTITIES = {
    "three_year_mean": "three_annual_flow_mean",
    "argmax_then_lookup": "three_year_peak_then_same_period_metric",
    "difference": "difference",
    "relative_change": "relative_change",
}


def require(condition, reason):
    if not condition:
        raise ValueError("cross_market_panel." + reason)


def reference(path):
    path = Path(path).resolve()
    value = base.read(path)
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size, id=value["id"])


def read_reference(ref):
    path = Path(ref["path"])
    require(
        path.is_absolute() and ".." not in path.parts and path.resolve() == path,
        "registered_regular_absolute_input",
    )
    require(
        base.sha(path) == ref["sha256"] and path.stat().st_size == ref["bytes"],
        "frozen_input_bytes",
    )
    value = base.read(path)
    if "id" in ref:
        require(value["id"] == ref["id"], "frozen_input_identity")
    return value


def issuer_join(task, documents, mapping):
    require(task["security_id"] in mapping, "missing_issuer")
    issuer = mapping[task["security_id"]]
    require(issuer["admitted"] is True, "issuer_not_admitted")
    require(
        issuer.get("exposure", {}).get("project_source_identity_screen_passed") is True,
        "project_history_screen_pending",
    )
    bindings = {row["raw_object_id"]: row for row in issuer["document_bindings"]}
    for raw_id in task["raw_object_ids"]:
        require(raw_id in documents and raw_id in bindings, "missing_document_identity")
        document = documents[raw_id]["document"]
        binding = bindings[raw_id]
        require(
            binding["admitted"] is True
            and binding["raw_sha256"] == document["sha256"]
            and binding["original_url"] == document["original_url"]
            and document["security_id"] == task["security_id"],
            "exact_admitted_document_identity",
        )
    return issuer


def require_composition_review(task, documents, reviews, financial_protocol_id):
    """Consume an independently produced, all-source semantic review; never mint one."""
    if task["group"] != "composition_required":
        return None
    review = reviews.get(task["task_id"])
    require(review is not None, "pending_independent_source_exhaustion_review")
    base.checked(review, "cross_market_composition_source_exhaustion_review")
    expected = set(task["source_exhaustion_review_raw_objects"])
    require(
        review["task_id"] == task["task_id"]
        and review["financial_protocol_id"] == financial_protocol_id
        and review["metric_id"] == task["metric_id"]
        and review["periods"] == task["periods"]
        and review["passed"] is True
        and review["no_same_concept_three_year_aggregate"] is True
        and review["all_original_source_pages_reviewed"] is True
        and review["review_method"] == "independent_full_source_semantic_review"
        and bool(review["reviewer_id"])
        and review["sole_basis_is_regex_absence"] is False,
        "invalid_or_nonsemantic_source_exhaustion_review",
    )
    rows = review["documents"]
    require(
        len(rows) == len(expected)
        and {row["raw_object_id"] for row in rows} == expected
        and set(task["raw_object_ids"]) <= expected,
        "source_exhaustion_complete_document_scope",
    )
    for row in rows:
        doc = documents[row["raw_object_id"]]
        require(
            row["raw_sha256"] == doc["document"]["sha256"]
            and row["page_text_reference"] == doc["input_references"]["text_bundle"]
            and row["all_pages_reviewed"] is True
            and bool(row["semantic_review_notes"])
            and isinstance(row["reviewed_relevant_locations"], list),
            "source_exhaustion_source_content_binding",
        )
    return review["id"]


def public_spec(task, issuer, documents):
    """Project only the public target/declared vintages, never answer or witness roles."""
    quantity = QUANTITIES[task["quantity"]]
    metrics = [task["metric_id"]] + (
        [task["secondary_metric_id"]] if task["secondary_metric_id"] else []
    )
    unit = "percent" if quantity == "relative_change" else "million " + task["currency"]
    identity = dict(
        issuer_cluster_id=issuer["issuer_cluster_id"],
        group=task["group"],
        quantity=quantity,
        metrics=metrics,
        periods=task["periods"],
        currency=task["currency"],
    )
    task_id = "cross_market_panel_task:" + base.sha(base.encode(identity))
    contract = dict(
        schema=period_tools.SCHEMA,
        task_id=task_id,
        source_cluster=issuer["issuer_cluster_id"],
        quantity=quantity,
        metric_ids=metrics,
        periods=[period_tools._period(*pair) for pair in task["periods"]],
        operation=period_tools._target_operation({"quantity": quantity, "metric_ids": metrics}),
        period_order="chronological",
        interval_boundaries="inclusive",
        fiscal_year_naming="not_inferred_from_metadata_year",
    )
    contract["id"] = "actual_period_contract:" + base.sha(base.encode(contract))
    descriptors = []
    for raw_id in sorted(task["raw_object_ids"]):
        qualified = documents[raw_id]
        doc = qualified["document"]
        descriptors.append(
            dict(
                raw_object_id=raw_id,
                raw_sha256=doc["sha256"],
                original_url=doc["original_url"],
                source_id=doc["source_id"],
                source_publish_date=doc["publish_date"],
                financial_qualification_record_id=qualified["id"],
                complete_original_pdf=dict(
                    path=doc["path"], sha256=doc["sha256"], bytes=doc["bytes"]
                ),
                complete_original_page_text=qualified["input_references"]["text_bundle"],
            )
        )
    return dict(
        task_id=task_id,
        group=task["group"],
        legal_name=issuer["legal_name"],
        security_id=task["security_id"],
        issuer_cluster_id=issuer["issuer_cluster_id"],
        source_cluster=issuer["issuer_cluster_id"],
        raw_object_ids=sorted(task["raw_object_ids"]),
        source_documents=descriptors,
        period_contract=contract,
        quantity_contract=dict(unit=unit, decimal_places=2, rounding="half_away_from_zero"),
    )


def question(spec):
    """Original English finite templates, with legal issuer/native-currency slots."""
    contract = spec["period_contract"]
    periods = contract["periods"]
    dates = [f"{row['start']} through {row['end']}" for row in periods]
    metrics, kind = contract["metric_ids"], contract["operation"]["kind"]
    entity = spec["legal_name"]
    output = f"Report the result in {spec['quantity_contract']['unit']}, rounded to two decimal places using half away from zero."
    if kind in {"difference", "relative_change"}:
        noun = "signed change" if kind == "difference" else "percentage change"
        equation = (
            "current minus previous"
            if kind == "difference"
            else "(current minus previous) divided by the strictly positive previous amount and multiplied by one hundred"
        )
        body = f"Calculate the {noun} in {METRIC_NAMES[metrics[0]]} for {entity} from {dates[0]} to {dates[1]}, defined as {equation}. {output}"
    elif kind == "arithmetic_mean":
        body = f"Calculate the arithmetic mean of {METRIC_NAMES[metrics[0]]} for {entity} across exactly three actual annual periods: [{'; '.join(dates)}]. {output}"
    else:
        body = f"Among all three actual annual periods: [{'; '.join(dates)}], identify the actual period with the highest {METRIC_NAMES[metrics[0]]} for {entity}, then report {METRIC_NAMES[metrics[1]]} for that same actual period. In the first Final, report the selected actual period_id and the secondary amount in {spec['quantity_contract']['unit']}, rounded to two decimal places using half away from zero."
    return (
        body
        + "\nUse the original report vintage(s) explicitly listed in source_documents; do not substitute a later restatement.\n"
        + period_tools.render_public_periods(contract)
    )


def public_sources(spec, document_facts, metric_universe):
    """Public-only source compiler: this signature has no gold/witness arguments."""
    periods = spec["period_contract"]["periods"]
    lower, upper = (
        min(row["start"] or row["end"] for row in periods),
        max(row["end"] for row in periods),
    )
    visible, observations = [], defaultdict(list)
    for raw_id in spec["raw_object_ids"]:
        for fact in document_facts[raw_id]:
            record = fact["record"]
            if fact["metric_id"] not in metric_universe or not (
                lower <= (record.get("start") or record["end"]) <= record["end"] <= upper
            ):
                continue
            require(
                fact["raw_object_id"] == raw_id
                and fact["security_id"] == spec["security_id"]
                and fact["status"] == "FINANCIALLY_QUALIFIED_ISSUER_PENDING",
                "qualified_public_fact_identity",
            )
            key = (
                fact["metric_id"],
                record.get("start"),
                record["end"],
                fact["currency"],
                fact["statement_scope"],
            )
            observations[key].append(fact)
            visible.append(fact)
    for rows in observations.values():
        semantics = {
            (str(Fraction(row["record"]["val"])), row["source_definition_id"]) for row in rows
        }
        require(len(semantics) == 1, "ambiguous_native_observation_in_public_vintages")
    require(visible, "nonempty_public_window")
    sources = []
    for fact in sorted(visible, key=lambda row: (row["raw_object_id"], row["native_pointer"])):
        source_id = "pdf_source:" + base.sha(
            base.encode([fact["raw_object_id"], fact["native_pointer"]])
        )
        sources.append(
            dict(
                source_id=source_id,
                source_kind="official_report_pdf_numeric_record",
                raw_object_id=fact["raw_object_id"],
                raw_sha256=fact["raw_sha256"],
                original_url=fact["original_url"],
                native_pointer=fact["native_pointer"],
                concept="pdf-financial:" + fact["metric_id"],
                label=fact["label"],
                definition=copy.deepcopy(fact["native_definition"]),
                unit=fact["currency"],
                record=copy.deepcopy(fact["record"]),
                evidence={
                    key: copy.deepcopy(fact["evidence"][key])
                    for key in (
                        "page",
                        "table",
                        "row",
                        "period_slot",
                        "parser_word_index",
                        "raw_value_text",
                        "unit_header",
                    )
                }
                | dict(
                    financial_fact_id=fact["fact_id"],
                    full_original_evidence_sha256=base.sha(base.encode(fact["evidence"])),
                ),
            )
        )
    require(
        len({row["source_id"] for row in sources}) == len(sources), "unique_mechanical_source_ids"
    )
    public = dict(
        question=question(spec),
        sources=sources,
        source_documents=copy.deepcopy(spec["source_documents"]),
        period_contract=copy.deepcopy(spec["period_contract"]),
        quantity_contract=copy.deepcopy(spec["quantity_contract"]),
        source_policy=dict(
            scope="finite_given_sources_declared_official_PDF_vintages",
            all_prequalified_registered_metrics_in_public_window=True,
            document_selection="financial_preregistered_latest_metadata_then_raw_identity",
            window=dict(start=lower, end=upper),
            no_private_solution_role_filter=True,
            original_currency_sign_period_and_document_version_retained=True,
            full_evidence_certificates_in_immutable_audit_not_repeated_in_model_context=True,
            compact_projection_changes_no_numeric_record_label_or_definition=True,
        ),
        tool_contract=dict(
            tools=sorted(runtime.prior.TOOLS),
            numeric_read_arguments=["source_id", "unit"],
            no_cross_currency_arithmetic=True,
            complete_original_references_for_audit_not_additional_online_tools=True,
        ),
    )
    runtime.SourceViewSources(public)
    return public, visible


def _witness(basis, bindings, operators, output):
    return relation_record(
        "financial_witness",
        basis=basis,
        input_bindings=bindings,
        operator_dag=dict(operators=operators, output_step=output),
    )


def private_certificate(task, review_id):
    facts = task["fact_ids"]
    if task["group"] != "dual_sufficient":
        kind = (
            "panel_composition_certificate"
            if task["group"] == "composition_required"
            else "panel_other_financial_certificate"
        )
        return relation_record(
            kind,
            complete=True,
            leaf_fact_ids=facts,
            public_fact_ids=facts,
            source_financial_candidate_id=task["task_id"],
            source_exhaustion_review_id=review_id,
            vintage_bridge=task.get("vintage_bridge"),
            exact_source_financial_admission_not_reinferred=True,
        )
    require(
        task["metric_id"] == "gross_profit" and len(task["relation_certificates"]) == 2,
        "registered_gross_profit_dual_required",
    )
    previous, current = task["relation_certificates"]
    endpoints = dict(
        previous=previous["gross_profit_fact_id"], current=current["gross_profit_fact_id"]
    )
    endpoint = _witness(
        "endpoint",
        endpoints,
        [
            dict(
                step_id="change",
                operator="difference",
                inputs=[dict(binding="previous"), dict(binding="current")],
            )
        ],
        "change",
    )
    bindings = dict(
        previous_revenue=previous["revenue_fact_id"],
        previous_cost=previous["cost_fact_id"],
        current_revenue=current["revenue_fact_id"],
        current_cost=current["cost_fact_id"],
    )
    operators = [
        dict(
            step_id=when,
            operator="linear_combination",
            inputs=[dict(binding=when + "_revenue"), dict(binding=when + "_cost")],
            params=dict(coefficients=[1, relation["cost_coefficient"]]),
        )
        for when, relation in (("previous", previous), ("current", current))
    ]
    operators.append(
        dict(
            step_id="change",
            operator="difference",
            inputs=[dict(step="previous"), dict(step="current")],
        )
    )
    movement = _witness("movement", bindings, operators, "change")
    certificate = relation_record(
        "financial_relation_certificate",
        complete=True,
        family="annual_flow",
        leaf_fact_ids=facts,
        public_fact_ids=facts,
        witnesses=[endpoint, movement],
        previous_component_fact_ids=[previous["revenue_fact_id"], previous["cost_fact_id"]],
        previous_component_coefficients=[1, previous["cost_coefficient"]],
        source_financial_candidate_id=task["task_id"],
        original_PDF_relations=task["relation_certificates"],
    )
    if task["quantity"] != "relative_change":
        return certificate
    outer = []
    for witness in (endpoint, movement):
        dag = copy.deepcopy(witness["operator_dag"])
        denominator = (
            dict(binding="previous") if witness["basis"] == "endpoint" else dict(step="previous")
        )
        dag["operators"].append(
            dict(
                step_id="growth",
                operator="ratio_percent",
                inputs=[dict(step="change"), denominator],
            )
        )
        outer.append(
            _witness(witness["basis"], witness["input_bindings"], dag["operators"], "growth")
        )
    return relation_record(
        "relative_quantity_certificate",
        quantity="relative_change",
        family="annual_flow",
        leaf_fact_ids=facts,
        public_fact_ids=facts,
        base_relation_certificate=certificate,
        witnesses=outer,
    )


def private_bundle(task, spec, public, review_id):
    target = dict(
        quantity=QUANTITIES[task["quantity"]],
        source_cluster=spec["source_cluster"],
        unit=spec["quantity_contract"]["unit"],
    )
    if task["group"] == "dual_sufficient":
        target.update(
            metric_id=task["metric_id"],
            previous_period=task["periods"][0],
            current_period=task["periods"][1],
        )
    else:
        target.update(
            metric_ids=spec["period_contract"]["metric_ids"], actual_periods=task["periods"]
        )
    return relation_record(
        "EvaluationTaskBundle",
        task_id=spec["task_id"],
        family=task["group"],
        source_cluster=spec["source_cluster"],
        public=public,
        private=dict(
            canonical_target=target, relation_certificate=private_certificate(task, review_id)
        ),
        validation=dict(
            status="passed",
            issuer_and_project_history_join=True,
            financial_candidate_id=task["task_id"],
            composition_source_exhaustion_review_id=review_id,
        ),
    )


def _read_actions(fact_ids, facts, source_map, unit):
    return [
        dict(
            tool="read_source",
            arguments=dict(
                source_id=source_map[(facts[key]["raw_object_id"], facts[key]["native_pointer"])],
                unit=unit,
            ),
        )
        for key in fact_ids
    ]


def scripted_controls(task, spec, public, bundle, native_bindings):
    """Bounded synthetic proof executions over selected real facts, not Student Q."""
    source_map = {
        (row["raw_object_id"], row["native_pointer"]): row["source_id"] for row in public["sources"]
    }
    amount_unit = "million " + task["currency"]
    answer = Fraction(task["answer_exact"]) / (
        1 if task["quantity"] == "relative_change" else 1000000
    )
    final = dict(
        value=str(runtime.assessment._rounded(answer, 2)), unit=spec["quantity_contract"]["unit"]
    )
    controls = []
    if task["group"] == "dual_sufficient":
        previous, current = task["relation_certificates"]
        routes = [
            ([previous["gross_profit_fact_id"], current["gross_profit_fact_id"]], "b-a", "a"),
            (
                [
                    previous["revenue_fact_id"],
                    previous["cost_fact_id"],
                    current["revenue_fact_id"],
                    current["cost_fact_id"],
                ],
                f"(c+({current['cost_coefficient']})*d)-(a+({previous['cost_coefficient']})*b)",
                f"a+({previous['cost_coefficient']})*b",
            ),
        ]
        for ids, expression, denominator in routes:
            if task["quantity"] == "relative_change":
                expression = f"({expression})/({denominator})"
            actions = _read_actions(ids, native_bindings, source_map, amount_unit)
            variables = {
                name: dict(result_id=f"tool:{index + 1}")
                for index, name in enumerate("abcd"[: len(ids)])
            }
            actions.append(
                dict(
                    tool="calculate",
                    arguments=dict(expression=expression, variables=variables, unit=final["unit"]),
                )
            )
            actions.append(dict(final={**final, "result_id": f"tool:{len(ids) + 1}"}))
            controls.append((True, actions))
    elif task["group"] == "composition_required":
        actions = _read_actions(task["fact_ids"], native_bindings, source_map, amount_unit)
        actions.append(
            dict(
                tool="calculate",
                arguments=dict(
                    expression="(a+b+c)/3",
                    variables={
                        name: dict(result_id=f"tool:{index + 1}")
                        for index, name in enumerate("abc")
                    },
                    unit=amount_unit,
                ),
            )
        )
        actions.append(dict(final={**final, "result_id": "tool:4"}))
        controls.append((True, actions))
    else:
        facts = task["fact_ids"]
        require(len(facts) == 6, "registered_peak_six_facts")
        actions = _read_actions(facts[:3], native_bindings, source_map, amount_unit)
        actions.append(
            dict(
                tool="select_max",
                arguments=dict(result_ids=["tool:1", "tool:2", "tool:3"], unit=amount_unit),
            )
        )
        peak = task["periods"].index(task["unique_argmax_period"])
        actions.extend(_read_actions([facts[peak + 3]], native_bindings, source_map, amount_unit))
        actions.append(
            dict(
                tool="lookup_selected",
                arguments=dict(selection_result_id="tool:4", source_result_id="tool:5"),
            )
        )
        actions.append(
            dict(
                final={
                    **final,
                    "result_id": "tool:6",
                    "period_id": runtime.runtime.actual_period(
                        native_bindings[facts[peak]]["record"]
                    )["period_id"],
                }
            )
        )
        controls.append((True, actions))
    controls.append((False, [dict(final={**final, "result_id": "tool:999"})]))
    messages = [dict(role="user", content=p.encode(public).decode())]
    identity = dict(
        task_id=spec["task_id"],
        family=spec["group"],
        surface_version_id="scripted_preflight_only",
        public_messages_sha256=p.sha(p.encode(messages)),
        parent_manifest_id="scripted_preflight_only",
    )
    bound, results = runtime.build_runtime(), []
    for expected, actions in controls:
        sources = bound.Sources(public)
        session = bound.generate(
            messages,
            identity,
            sources,
            scripted=[json.dumps(row) for row in actions],
            requested_basis="neutral",
        )
        outcome = bound.assess_session(session, bundle, native_bindings, sources)
        results.append(
            dict(
                expected=expected,
                observed=outcome["financial_valid"],
                reason=outcome["reason"],
                session_id=session["id"],
                assessment_id=outcome["id"],
            )
        )
    return results


def choose_tasks(candidates, documents, mapping, reviews, financial_protocol_id, metric_universe):
    facts = {row["fact_id"]: row for doc in documents.values() for row in doc["qualified_facts"]}
    document_facts = {key: row["qualified_facts"] for key, row in documents.items()}
    accepted, rejected = {}, []
    for task in candidates:
        try:
            require(
                task["group"] in GROUPS and task["quantity"] in QUANTITIES,
                "registered_task_structure",
            )
            require(set(task["fact_ids"]) <= set(facts), "task_fact_join")
            issuer = issuer_join(task, documents, mapping)
            review = require_composition_review(task, documents, reviews, financial_protocol_id)
            spec = public_spec(task, issuer, documents)
            public, visible = public_sources(spec, document_facts, metric_universe)
            require(
                set(task["fact_ids"]) <= {row["fact_id"] for row in visible},
                "target_facts_not_all_public",
            )
            rank = tuple(
                sorted(
                    (facts[key]["source_publish_date"], facts[key]["raw_object_id"])
                    for key in task["fact_ids"]
                )
            )
            item = dict(
                task=task, spec=spec, public=public, visible=visible, review=review, rank=rank
            )
            previous = accepted.get(spec["task_id"])
            if previous is None or (rank, task["security_id"], task["task_id"]) > (
                previous["rank"],
                previous["task"]["security_id"],
                previous["task"]["task_id"],
            ):
                accepted[spec["task_id"]] = item
        except (ValueError, KeyError, TypeError) as error:
            rejected.append(
                dict(
                    candidate_task_id=task.get("task_id"),
                    group=task.get("group"),
                    reason=str(error),
                )
            )
    by_group = {group: defaultdict(list) for group in GROUPS}
    for item in accepted.values():
        by_group[item["spec"]["group"]][item["spec"]["issuer_cluster_id"]].append(item)
    selected = []
    for group in GROUPS:
        buckets = by_group[group]
        for rows in buckets.values():
            rows.sort(key=lambda item: (item["task"]["periods"][-1][1], item["spec"]["task_id"]))
        issuers = sorted(buckets, key=lambda cluster: base.sha(SALT + cluster))
        ordered, offset = [], 0
        while any(offset < len(buckets[key]) for key in issuers):
            ordered.extend(buckets[key][offset] for key in issuers if offset < len(buckets[key]))
            offset += 1
        selected.extend(ordered[:60])
    counts = Counter(item["spec"]["group"] for item in accepted.values())
    return selected, dict((group, counts[group]) for group in GROUPS), rejected


def compile_panel(
    candidates,
    documents,
    issuer_admission,
    reviews,
    financial_protocol_id,
    metric_universe,
    token_counter,
):
    mapping = statistics.admission_mapping(issuer_admission)
    selected, counts, rejected = choose_tasks(
        candidates, documents, mapping, reviews, financial_protocol_id, metric_universe
    )
    report = dict(
        candidate_admission_counts=counts,
        quotas=QUOTAS,
        rejections=rejected,
        passed=False,
        panel_ready=False,
        status="BLOCKED_GROUP_QUOTAS_OR_SOURCE_GATES",
        model_calls=0,
        actual_model_scoring_cases=0,
    )
    if any(counts[group] < 60 for group in GROUPS):
        return report, []
    require(
        len(selected) == len({item["spec"]["task_id"] for item in selected}) == 180
        and Counter(item["spec"]["group"] for item in selected) == QUOTAS,
        "exact_selected_180_fixed_groups",
    )
    checks, prepared = [], []
    for item in selected:
        spec, public = item["spec"], item["public"]
        natives = {
            fact["fact_id"]: {
                **copy.deepcopy(fact),
                "entity_id": spec["issuer_cluster_id"],
                "issuer_cluster_id": spec["issuer_cluster_id"],
                "source_cluster": spec["issuer_cluster_id"],
                "issuer_admission_id": issuer_admission["id"],
            }
            for fact in item["visible"]
        }
        bundle = private_bundle(item["task"], spec, public, item["review"])
        controls = scripted_controls(item["task"], spec, public, bundle, natives)
        messages = [dict(role="user", content=p.encode(public).decode())]
        tokens = token_counter(messages)
        check = dict(
            task_id=spec["task_id"],
            initial_prompt_tokens=tokens,
            available_history_growth_tokens=24576 - 2048 - tokens,
            controls=controls,
            passed=type(tokens) is int
            and 0 < tokens <= 18432
            and all(row["expected"] is row["observed"] for row in controls),
        )
        checks.append(check)
        prepared.append(
            dict(
                spec=spec,
                public_messages=messages,
                bundle=bundle,
                native_bindings=natives,
                candidate_task_id=item["task"]["task_id"],
            )
        )
    passed = all(row["passed"] for row in checks)
    report.update(
        status="PASS_180_PDF_PUBLIC_PRIVATE_CONTRACTS"
        if passed
        else "BLOCKED_SELECTED_INPUT_OR_SCRIPTED_CONTROL",
        passed=passed,
        panel_ready=passed,
        selected_task_ids=[item["spec"]["task_id"] for item in selected],
        selected_group_counts=dict(Counter(item["spec"]["group"] for item in selected)),
        selected_issuer_count=len({item["spec"]["issuer_cluster_id"] for item in selected}),
        selected_market_group_counts=dict(
            Counter(
                item["spec"]["group"] + ":" + item["spec"]["security_id"].split(":", 1)[0]
                for item in selected
            )
        ),
        checks=checks,
        scripted_control_executions=sum(len(row["controls"]) for row in checks),
        input_tokenizations=len(checks),
        no_replacement_after_selected_input_failure=True,
    )
    return report, prepared if passed else []


def register(root, financial_root, issuer_path, review_path=None, output=RAW):
    output = Path(output).resolve()
    require(output.is_relative_to(base.RAW) and output != base.RAW, "isolated_panel_output_root")
    if (output / "protocol.json").exists():
        return protocol(root, output)
    financial_root = Path(financial_root).resolve()
    summary = base.checked(
        base.read(financial_root / "summary.json"), "cross_market_financial_qualification_completed"
    )
    financial_plan = base.read(financial_root / "protocol.json")
    kind = financial_plan["schema_version"].split(".")[-1]
    require(
        kind
        in {
            "cross_market_financial_qualification_protocol",
            "cross_market_financial_header_revision_protocol",
        },
        "known_financial_preparation_protocol",
    )
    base.checked(financial_plan, kind)
    require(
        summary["protocol_id"] == financial_plan["id"]
        and summary["documents"] == 440
        and financial_plan["public_metric_universe"] == list(financial.METRICS),
        "complete_fixed_financial_inputs",
    )
    candidates = base.checked(
        base.read(financial_root / "candidate_tasks.json"), "cross_market_financial_task_candidates"
    )
    require(candidates["protocol_id"] == financial_plan["id"], "same_candidate_pass")
    document_refs = []
    for item in financial_plan["documents"]:
        key = base.sha(item["document"]["raw_object_id"])[:24]
        path = financial_root / "documents" / (key + ".json")
        value = base.checked(base.read(path), "cross_market_financial_document")
        require(
            value["protocol_id"] == financial_plan["id"] and value["document"] == item["document"],
            "financial_document_registry_join",
        )
        document_refs.append(reference(path))
    issuer = base.checked(base.read(issuer_path), "cross_market_issuer_admission")
    statistics.admission_mapping(issuer)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in (
        SCRIPT,
        financial.SCRIPT,
        "trusted_data_synthesis/scripts/fixed_kernel_cross_market_runtime_20260926.py",
        "trusted_data_synthesis/scripts/cross_market_statistics_20260926.py",
    ):
        payload = (Path(root) / name).read_bytes()
        require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "compiler_committed_before_registration",
        )
        sources[name] = base.sha(payload)
    reuse_path = base.PARENT / "reuse_admission.json"
    reuse = p.checked(base.read(reuse_path), "direction_calibration_material_admission")
    require(reuse["passed"] is True, "admitted_original_tokenizer_binding")
    plan = base.record(
        "cross_market_panel_compilation_protocol",
        at=base.now(),
        code_commit=head,
        sources=sources,
        financial_protocol_id=financial_plan["id"],
        financial_protocol=reference(financial_root / "protocol.json"),
        financial_summary=reference(financial_root / "summary.json"),
        candidates=reference(financial_root / "candidate_tasks.json"),
        documents=document_refs,
        issuer_admission=reference(issuer_path),
        source_exhaustion_reviews=reference(review_path) if review_path else None,
        source_exhaustion_pending_is_failure=True,
        tokenizer_binding=reuse["materials"]["assets"]["tokenizer_binding"],
        tokenizer_parent_admission=reference(reuse_path),
        runtime_binding=runtime.binding(),
        public_metric_universe=list(financial.METRICS),
        quotas=QUOTAS,
        selection_salt=SALT,
        selection="issuer-target dedup; original latest publication/raw-object metadata rule; issuer hash roundrobin, then endperiod/taskid; no substitution after control/input failure",
        source_scope="all qualified registered metrics within public time window from explicitly declared report vintages",
        ambiguity_rule="reject full task on conflicting value or source definition for any public metric/period/currency/scope",
        maximum_compiler_passes=1,
        maximum_scripted_control_executions=420,
        maximum_initial_prompt_tokenizations=180,
        actual_model_generation_calls=0,
        actual_model_scoring_cases=0,
        original_PDF_opens=0,
        source_exhaustion_review_created_by_compiler=False,
        GPU_processes=0,
        network_requests=0,
        new_training_updates=0,
        evaluation_launch_authorized=False,
    )
    base.write(output / "protocol.json", plan)
    return plan


def protocol(root, output):
    plan = base.checked(
        base.read(Path(output) / "protocol.json"), "cross_market_panel_compilation_protocol"
    )
    for name, digest in plan["sources"].items():
        require(base.sha(Path(root) / name) == digest, "frozen_compiler_source:" + name)
    require(
        plan["runtime_binding"] == runtime.binding()
        and plan["quotas"] == QUOTAS
        and plan["public_metric_universe"] == list(financial.METRICS),
        "frozen_runtime_quota_metric_contract",
    )
    return plan


def _asset_reference(path):
    path = Path(path).resolve()
    value = base.read(path)
    result = dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)
    if "id" in value:
        result["id"] = value["id"]
    return result


def publish_panel(output, plan, report, prepared):
    """Publish an admitted full panel only; blocked runs have no callable manifest."""
    require(report["passed"] is True and len(prepared) == 180, "no_partial_panel_publication")
    rows, private_rows, native_bindings = [], [], {}
    for item in prepared:
        spec = item["spec"]
        view = p.record(
            "given_public_source_view_v2",
            canonical_task_id=spec["task_id"],
            group=spec["group"],
            source_cluster=spec["source_cluster"],
            public_messages=item["public_messages"],
            public_messages_sha256=p.sha(p.encode(item["public_messages"])),
            compilation_protocol_id=plan["id"],
            runtime_binding_id=plan["runtime_binding"]["id"],
        )
        stem = spec["task_id"].split(":", 1)[1]
        path = Path(output) / "public/views" / (stem + ".json")
        base.write(path, view)
        rows.append(
            {
                key: spec[key]
                for key in (
                    "task_id",
                    "group",
                    "source_cluster",
                    "issuer_cluster_id",
                    "security_id",
                    "raw_object_ids",
                )
            }
            | dict(
                path=str(path.resolve()),
                surface_version_id=view["id"],
                public_messages_sha256=view["public_messages_sha256"],
                source_financial_candidate_id=item["candidate_task_id"],
            )
        )
        bundle_path = Path(output) / "private/bundles" / (stem + ".json")
        base.write(bundle_path, item["bundle"])
        private_rows.append(dict(task_id=spec["task_id"], **_asset_reference(bundle_path)))
        for key, native in item["native_bindings"].items():
            require(
                key not in native_bindings or native_bindings[key] == native,
                "consistent_native_binding_across_tasks",
            )
            native_bindings[key] = native
    manifest = p.record(
        "source_view_manifest_v2",
        split="calibration",
        tasks=rows,
        task_count=180,
        compilation_protocol_id=plan["id"],
        runtime_binding_id=plan["runtime_binding"]["id"],
        issuer_admission_id=plan["issuer_admission"]["id"],
    )
    manifest_path = Path(output) / "public/manifest.json"
    base.write(manifest_path, manifest)
    admission = p.record(
        "calibration_panel_admission",
        **report,
        source_manifest_id=manifest["id"],
        compilation_protocol_id=plan["id"],
        issuer_admission=plan["issuer_admission"],
        runtime_binding_id=plan["runtime_binding"]["id"],
    )
    admission_path = Path(output) / "public/admission.json"
    base.write(admission_path, admission)
    native_path = Path(output) / "private/native_bindings.json"
    base.write(native_path, native_bindings)
    assets = p.record(
        "calibration_private_assets",
        source_manifest_id=manifest["id"],
        bundles=private_rows,
        native_bindings=_asset_reference(native_path),
        compilation_protocol_id=plan["id"],
    )
    assets_path = Path(output) / "private/assets.json"
    base.write(assets_path, assets)
    references = dict(
        manifest=_asset_reference(manifest_path),
        admission=_asset_reference(admission_path),
        private_assets=_asset_reference(assets_path),
    )
    base.write(Path(output) / "evaluation_panel_references.json", references)
    return references


def run(root, output=RAW):
    output = Path(output).resolve()
    plan = protocol(root, output)
    with base.locked(output / "run.lock"):
        if (output / "summary.json").exists():
            result = base.checked(
                base.read(output / "summary.json"), "cross_market_panel_compilation_completed"
            )
            require(result["protocol_id"] == plan["id"], "same_completed_compilation")
            return result
        require(
            not (output / "compilation_attempt.json").exists(),
            "unsettled_compilation_no_budget_reset",
        )
        candidates = read_reference(plan["candidates"])
        document_rows = [read_reference(ref) for ref in plan["documents"]]
        documents = {row["document"]["raw_object_id"]: row for row in document_rows}
        require(
            len(documents) == 440
            and all(row["protocol_id"] == plan["financial_protocol_id"] for row in document_rows),
            "fixed_complete_financial_document_join",
        )
        issuer = read_reference(plan["issuer_admission"])
        reviews = {}
        if plan["source_exhaustion_reviews"] is not None:
            review_bundle = base.checked(
                read_reference(plan["source_exhaustion_reviews"]),
                "cross_market_composition_source_exhaustion_reviews",
            )
            reviews = {row["task_id"]: row for row in review_bundle["reviews"]}
            require(
                len(reviews) == len(review_bundle["reviews"]), "unique_external_composition_reviews"
            )
        base.write(
            output / "compilation_attempt.json",
            dict(protocol_id=plan["id"], attempt=1, at=base.now()),
        )
        from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
            load_tokenizer,
        )

        tokenizer = None

        def count_tokens(messages):
            nonlocal tokenizer
            if tokenizer is None:
                tokenizer = load_tokenizer(plan["tokenizer_binding"])
            rendered = tokenizer.apply_chat_template(
                [
                    dict(role="system", content=runtime.SYSTEM + "\nRequested guidance: neutral"),
                    *messages,
                ],
                tokenize=False,
                add_generation_prompt=True,
            )
            return len(tokenizer(rendered, add_special_tokens=False, truncation=False)["input_ids"])

        report, prepared = compile_panel(
            candidates["candidates"],
            documents,
            issuer,
            reviews,
            plan["financial_protocol_id"],
            plan["public_metric_universe"],
            count_tokens,
        )
        references = publish_panel(output, plan, report, prepared) if report["passed"] else None
        result = base.record(
            "cross_market_panel_compilation_completed",
            protocol_id=plan["id"],
            **report,
            evaluation_panel_references=references,
            evaluation_started=False,
            at=base.now(),
        )
        base.write(output / "summary.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--financial-root", type=Path, default=base.RAW / "financial_header_revision_01"
    )
    parser.add_argument(
        "--issuer-admission", type=Path, default=base.RAW / "issuer_admission_01/admission.json"
    )
    parser.add_argument("--source-exhaustion-reviews", type=Path)
    parser.add_argument("--output", type=Path, default=RAW)
    args = parser.parse_args()
    if args.action == "register":
        value = register(
            args.root.resolve(),
            args.financial_root,
            args.issuer_admission,
            args.source_exhaustion_reviews,
            args.output,
        )
    elif args.action == "run":
        value = run(args.root.resolve(), args.output)
    else:
        value = (
            base.read(args.output / "summary.json")
            if (args.output / "summary.json").exists()
            else protocol(args.root.resolve(), args.output)
        )
    base.emit(
        dict(
            event="cross_market_panel_" + args.action,
            id=value["id"],
            status=value.get("status"),
            passed=value.get("passed", False),
        )
    )


if __name__ == "__main__":
    main()
