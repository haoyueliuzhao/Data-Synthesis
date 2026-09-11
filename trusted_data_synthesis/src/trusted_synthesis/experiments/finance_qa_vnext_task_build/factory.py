"""Actual QA Build -> registered Pattern -> plan -> question -> validation."""

import json
from collections import Counter, defaultdict, deque
from decimal import Decimal
from pathlib import Path

from finraw.qa import pipeline
from finraw.qa.graph_patterns import get_pattern, pattern_content_hash
from finraw.qa.store import insert_rows

from . import issuer_tables
from .archive import WORK, RecordDB, record, require, write_json
from .protocol import CAPS, CASH, RESTRICTED, all_leaf_uses
from .relations import (
    BindingRejected,
    actual_period,
    annual_relation,
    basic,
    consecutive,
    definition_pair,
    endpoint_plan,
    relative_certificate,
    stock_relation,
    target_identity,
    value,
    witness,
)

CONTROL_METRICS = {
    "revenue",
    "net_income",
    "operating_income",
    "net_cash_provided_by_used_in_operating_activities",
}


def qa_config():
    defaults = pipeline._qa_policy({})
    return {
        "qa": {
            "quotas": dict.fromkeys(defaults["quotas"], 0),
            "derived_quotas": dict.fromkeys(defaults["derived_quotas"], 0),
            "graph_patterns": {"enabled": False},
            "pattern_mining": {"enabled": False, "auto_run": False},
            "question_generation": {
                "mode": "controlled_template",
                "language": "en",
                "max_workers": 8,
                "benchmark_alignment": {
                    "enabled": True,
                    "explicit_unit": True,
                    "explicit_precision": True,
                    "decimal_places": 2,
                    "output_contract": {"mode": "fixed", "instruction_styles": ["direct"]},
                },
            },
            "quality_gate": {
                "minimum_overall_pass_rate": 1.0,
                "critical_tasks": {},
                "max_critical_check_failures": 0,
            },
            "split_policy": "task_factory_all_leaf_source_cluster_v1",
        }
    }


def round_robin(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["target"]["source_cluster"]].append(row)
    queues = {
        key: deque(
            sorted(values, key=lambda row: (row["target"]["current_period"][1], row["task_id"]))
        )
        for key, values in groups.items()
    }
    result = []
    while any(queues.values()):
        for key in sorted(queues):
            if queues[key]:
                result.append(queues[key].popleft())
    return result


def enumerate_bindings(facts, bindings, usage):
    lookup = {
        (fact["entity_id"], fact["metric_id"], *actual_period(fact)): fact
        for fact in facts.values()
    }
    require(len(lookup) == len(facts), "factory.unique_fact_per_actual_period")
    series = defaultdict(list)
    for fact in facts.values():
        if fact["metric_id"] in {
            "gross_profit",
            CASH,
            RESTRICTED,
            issuer_tables.FCF,
            *CONTROL_METRICS,
        }:
            series[fact["entity_id"], fact["metric_id"]].append(fact)
    accepted, failures, identity_seen = defaultdict(list), [], set()
    for key in sorted(series):
        ordered = sorted(series[key], key=lambda fact: (fact["period_end"], fact["fact_id"]))
        for previous, current in zip(ordered, ordered[1:], strict=False):
            group = (
                "company_defined_metric"
                if key[1] == issuer_tables.FCF
                else "annual_flow"
                if key[1] == "gross_profit"
                else "stock_rollforward"
                if key[1] in {CASH, RESTRICTED}
                else "control"
            )
            try:
                basic([previous, current], bindings, usage)
                consecutive(previous, current)
                definition_pair(previous, current, bindings)
                task_id, target = target_identity(previous, current, bindings)
                if group == "company_defined_metric":
                    certificate = issuer_tables.relation(previous, current, lookup, bindings, usage)
                elif group == "annual_flow":
                    certificate = annual_relation(previous, current, lookup, bindings, usage)
                elif group == "stock_rollforward":
                    certificate = stock_relation(previous, current, lookup, bindings, usage)
                else:
                    plan, inputs = endpoint_plan(previous, current)
                    oracle = witness(plan, inputs, [previous, current], "fixed_control_reference")
                    certificate = record(
                        "control_reference",
                        family="control",
                        leaf_fact_ids=[previous["fact_id"], current["fact_id"]],
                        public_fact_ids=[previous["fact_id"], current["fact_id"]],
                        witnesses=[oracle],
                        only_one_possible_method_claimed=False,
                    )
                require(
                    task_id not in identity_seen, "factory.target_identity_not_wording_or_route"
                )
                identity_seen.add(task_id)
                accepted[group].append(
                    {
                        "task_id": task_id,
                        "target": target,
                        "family": group,
                        "previous_fact_id": previous["fact_id"],
                        "current_fact_id": current["fact_id"],
                        "certificate": certificate,
                    }
                )
                if value(previous) > 0:
                    rate_id, rate_target = target_identity(
                        previous, current, bindings, "relative_change"
                    )
                    require(rate_id not in identity_seen, "factory.no_duplicate_relative_target")
                    identity_seen.add(rate_id)
                    accepted[group].append(
                        {
                            "task_id": rate_id,
                            "target": rate_target,
                            "family": group,
                            "previous_fact_id": previous["fact_id"],
                            "current_fact_id": current["fact_id"],
                            "certificate": relative_certificate(certificate, previous, facts),
                        }
                    )
            except (BindingRejected, ValueError) as exc:
                failures.append(
                    {
                        "family": group,
                        "entity_id": key[0],
                        "metric_id": key[1],
                        "previous_fact_id": previous["fact_id"],
                        "current_fact_id": current["fact_id"],
                        "previous_period": actual_period(previous),
                        "current_period": actual_period(current),
                        "status": "BINDING_REJECTED",
                        "reason": getattr(exc, "code", str(exc)),
                        "details": getattr(exc, "details", {}),
                    }
                )
    selected, overflow = {}, {}
    for group, cap in CAPS.items():
        ordered = round_robin(accepted[group])
        selected[group], overflow[group] = (
            ordered[:cap],
            [value["task_id"] for value in ordered[cap:]],
        )
    return (
        selected,
        failures,
        {
            "qualified_counts": {key: len(value) for key, value in accepted.items()},
            "cap_excluded_target_ids": overflow,
        },
    )


def match_for(item, facts, bindings):
    previous, current = facts[item["previous_fact_id"]], facts[item["current_fact_id"]]
    return {
        "fact_ids": [previous["fact_id"], current["fact_id"]],
        "entity_ids": [current["entity_id"]],
        "metric_ids": [current["metric_id"]],
        "input_bindings": {"previous": previous["fact_id"], "current": current["fact_id"]},
        "target_time_scope": {
            "basis": "explicit_source_periods",
            "frequency": "annual",
            "previous_period_start": previous.get("period_start"),
            "previous_period_end": previous["period_end"],
            "period_start": current.get("period_start"),
            "period_end": current["period_end"],
        },
        "source_document_ids": sorted(
            {bindings[fact["fact_id"]]["document_id"] for fact in (previous, current)}
        ),
        "frequency": "annual",
        "binding_source": "pinned_native_actual_period_enumerator_v1",
    }


def compile_batch(db, kg, items, facts, bindings, output, name):
    output = Path(output) / name
    initial = pipeline.build_qa_candidates(db, qa_config(), kg_build_id=kg["kg_build_id"])
    qa_build_id = initial["qa_build_id"]
    require(initial["candidate_count"] == 0, "factory.no_default_or_benchmark_candidates")
    entity_names = {
        row["entity_id"]: row["canonical_name"]
        for row in db.fetchall("SELECT * FROM canonical_entities")
    }
    metrics = {row["metric_id"]: row for row in db.fetchall("SELECT * FROM metrics")}
    metric_names = {key: row["canonical_name"] for key, row in metrics.items()}
    candidates, plans, compilations = [], [], []
    derived_parents = defaultdict(list)
    for row in db.fetchall(
        "SELECT * FROM derived_facts WHERE build_id=? AND input_build_id=? "
        "AND derived_type IN ('difference','yoy_growth') "
        "AND verification_status IN ('single_source','cross_verified')",
        (kg["input_qa_build_id"], kg["input_fact_build_id"]),
    ):
        derived_parents[
            row["derived_type"], tuple(sorted(json.loads(row["input_fact_ids"])))
        ].append(row)
    usage = {
        key: {"split": value["split"], "allowed_uses": value["allowed_uses"]}
        for key, value in bindings.items()
    }
    for item in items:
        match = match_for(item, facts, bindings)
        growth = item["target"]["quantity"] == "relative_change"
        pattern = get_pattern(
            "pinned_annual_metric_growth" if growth else "pinned_annual_metric_change"
        )
        derived_type = "yoy_growth" if growth else "difference"
        parents = derived_parents[derived_type, tuple(sorted(match["fact_ids"]))]
        require(len(parents) == 1, "factory.actual_unique_DerivedFact_parent")
        parent = parents[0]
        match["source_derived_ids"] = [parent["derived_id"]]
        lineage = {parent["derived_id"]: json.loads(parent["input_fact_ids"])}
        all_leaf_uses([parent["derived_id"], *match["fact_ids"]], lineage, usage)
        candidate, plan = pipeline._graph_pattern_candidate(
            db,
            match,
            pattern,
            facts,
            qa_build_id,
            kg["kg_build_id"],
            entity_names,
            metric_names,
            metrics,
            {},
        )
        # The registered Pattern is the parent identity. This is NOT a mined
        # proposal and does not fabricate a publication score or compilation.
        compilation = record(
            "task_pattern_compilation",
            task_id=item["task_id"],
            qa_build_id=qa_build_id,
            candidate_id=candidate["candidate_id"],
            operation_plan_id=plan["plan_id"],
            pattern_id=pattern.pattern_id,
            pattern_version=pattern.pattern_version,
            pattern_hash=pattern_content_hash(pattern),
            pattern_spec=pattern.as_row(),
            match=match,
            reference_execution=plan,
            relation_certificate_id=item["certificate"]["id"],
            compiler_entrypoint="finraw.qa.pipeline._graph_pattern_candidate",
            binding_enumerator="finance_qa_vnext_task_build.factory.enumerate_bindings",
            candidate_eligibility=candidate["eligibility_status"],
            rejection_reasons=candidate["rejection_reasons"],
            is_mined_proposal=False,
            model_generated=False,
        )
        candidates.append(candidate)
        plans.append(plan)
        compilations.append(compilation)
    with db.transaction():
        insert_rows(
            db,
            "qa_candidates",
            candidates,
            pipeline.CANDIDATE_COLUMNS,
            pipeline._candidate_json_columns(),
        )
        insert_rows(
            db, "qa_operation_plans", plans, pipeline.PLAN_COLUMNS, pipeline._plan_json_columns()
        )
        original = pipeline._qa_build(db, qa_build_id)
        notes = {
            **original["notes"],
            "task_counts": dict(Counter(row["task_subtype"] for row in candidates)),
            "emitted_task_counts": dict(Counter(row["task_subtype"] for row in candidates)),
            "rejection_counts": dict(
                Counter(reason for row in candidates for reason in row["rejection_reasons"])
            ),
            "task_factory_adapter": {
                "batch": name,
                "task_count": len(items),
                "compiler_records": [value["id"] for value in compilations],
                "prior_empty_build_is_constructor_not_final_inventory": True,
            },
        }
        db.execute(
            "UPDATE qa_builds SET candidate_count=?, notes=? WHERE qa_build_id=?",
            (len(candidates), json.dumps(notes, ensure_ascii=False, sort_keys=True), qa_build_id),
        )
    write_json(output / "constructor_report.json", initial)
    write_json(output / "pattern_compilations.json", compilations)
    write_json(output / "relation_certificates.json", [item["certificate"] for item in items])
    write_json(
        output / "target_bindings.json",
        [{key: value for key, value in item.items() if key != "certificate"} for item in items],
    )
    generation = pipeline.generate_qa_samples(db, qa_build_id)
    validation = pipeline.validate_qa_samples(db, qa_build_id)
    write_json(output / "generation_report.json", generation)
    write_json(output / "validation_report.json", validation)
    return qa_build_id, candidates, plans, compilations, validation


def public_projection(question, native_sources, quantity_contract):
    """The only student/teacher-visible fields; no canonical_semantics copy."""
    return {
        "question": question,
        "sources": native_sources,
        "quantity_contract": {
            key: quantity_contract[key]
            for key in ("unit", "currency", "decimal_places", "rounding")
        },
        "source_policy": (
            "Use only these original records, their explicit periods, units and native definitions."
        ),
        "tool_contract": {
            "calculate": (
                "Evaluate explicit arithmetic over numeric source values; "
                "do not assume hidden references."
            ),
            "Final": "Return the requested quantity and units.",
        },
    }


def teacher_messages(bundle):
    public = bundle["public"]
    allowed = public_projection(public["question"], public["sources"], public["quantity_contract"])
    require(public == allowed, "public.only_whitelisted_fields")
    return [
        {
            "role": "user",
            "content": json.dumps(
                allowed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        }
    ]


def export_batch(
    db, kg, qa_build_id, items, candidates, plans, compilations, facts, bindings, usage, output
):
    candidate_by_id = {row["candidate_id"]: row for row in candidates}
    plan_by_id = {row["plan_id"]: row for row in plans}
    item_by_id = {row["task_id"]: row for row in items}
    compile_by_candidate = {row["candidate_id"]: row for row in compilations}
    exported, rejected = [], []
    for sample in db.fetchall(
        "SELECT * FROM qa_samples WHERE qa_build_id=? ORDER BY qa_id", (qa_build_id,)
    ):
        candidate = candidate_by_id[sample["candidate_id"]]
        compilation = compile_by_candidate[sample["candidate_id"]]
        item = item_by_id[compilation["task_id"]]
        if sample["validation_status"] != "passed":
            rejected.append(
                {
                    "task_id": item["task_id"],
                    "candidate_id": candidate["candidate_id"],
                    "qa_id": sample["qa_id"],
                    "status": "QA_VALIDATION_REJECTED",
                }
            )
            continue
        certificate = item["certificate"]
        derived_ids = candidate["source_derived_ids"]
        lineage = {}
        for identifier in derived_ids:
            parent = db.fetchone(
                "SELECT * FROM derived_facts "
                "WHERE derived_id=? AND build_id=? AND input_build_id=?",
                (identifier, kg["input_qa_build_id"], kg["input_fact_build_id"]),
            )
            require(parent is not None, "export.real_DerivedFact_parent_chain")
            lineage[identifier] = json.loads(parent["input_fact_ids"])
        leaf_ids = all_leaf_uses([*certificate["leaf_fact_ids"], *derived_ids], lineage, usage)
        basic([facts[identifier] for identifier in leaf_ids], bindings, usage)
        plan = plan_by_id[candidate["operation_plan_id"]]
        previous, current = facts[item["previous_fact_id"]], facts[item["current_fact_id"]]
        consecutive(previous, current)
        definition_pair(previous, current, bindings)
        independently_recomputed = value(current) - value(previous)
        if item["target"]["quantity"] == "relative_change":
            independently_recomputed = 100 * independently_recomputed / value(previous)
        require(
            independently_recomputed == Decimal(candidate["answer_payload"]["value"]),
            "export.independent_native_target_recompute",
        )
        require(
            target_identity(previous, current, bindings, item["target"]["quantity"])[0]
            == item["task_id"],
            "export.semantic_task_identity",
        )
        checks = db.fetchall(
            "SELECT * FROM qa_quality_checks WHERE qa_id=? ORDER BY check_name", (sample["qa_id"],)
        )
        require(
            bool(checks) and all(row["check_status"] == "passed" for row in checks),
            "export.actual_QA_quality_records",
        )
        native_sources = []
        emitted_tables = set()
        for identifier in sorted(
            certificate["public_fact_ids"],
            key=lambda key: (bindings[key]["tag"], bindings[key]["record"]["end"], key),
        ):
            source = bindings[identifier]
            raw = db.fetchone(
                "SELECT * FROM raw_objects WHERE raw_object_id=?", (source["raw_object_id"],)
            )
            if source.get("source_kind") == "issuer_report_table":
                if source["table_id"] not in emitted_tables:
                    table = source["table_record"]
                    native_sources.append(
                        {
                            "source_id": source["table_id"],
                            "source_kind": "original_issuer_reconciliation",
                            "original_url": raw["original_url"],
                            "raw_sha256": source["raw_sha256"],
                            "native_table_xpath": table["table_xpath"],
                            "unit": "million USD",
                            "definition": table["structure"]["definition_quote"],
                            "original_rows": [
                                [cell["text"] for cell in row] for row in table["structure"]["rows"]
                            ],
                            "nearby_original_source_text": table["structure"]["nearby_source_text"],
                        }
                    )
                    emitted_tables.add(source["table_id"])
                continue
            native_sources.append(
                {
                    "source_id": identifier,
                    "original_url": raw["original_url"],
                    "raw_sha256": source["raw_sha256"],
                    "native_pointer": source["pointer"],
                    "concept": "us-gaap:" + source["tag"],
                    "label": source["native_definition"]["label"],
                    "definition": source["native_definition"]["description"],
                    "unit": "USD",
                    "record": source["record"],
                }
            )
        contract = {
            "unit": item["target"]["unit"],
            "currency": item["target"]["currency"],
            "decimal_places": 2,
            "rounding": "half away from zero",
        }
        bundle = record(
            "TaskBundle",
            task_id=item["task_id"],
            split="train",
            allowed_uses=["train"],
            source_cluster=item["target"]["source_cluster"],
            family=item["family"],
            parents={
                "qa_build_id": qa_build_id,
                "candidate_id": candidate["candidate_id"],
                "qa_id": sample["qa_id"],
                "pattern_id": candidate["pattern_id"],
                "pattern_hash": candidate["pattern_hash"],
                "compilation_id": compilation["id"],
                "operation_plan_id": plan["plan_id"],
                "kg_build_id": kg["kg_build_id"],
                "fact_build_id": kg["input_fact_build_id"],
                "entity_build_id": kg["input_entity_build_id"],
                "source_definition_build_id": kg["input_source_definition_build_id"],
                "document_build_id": kg["input_document_build_id"],
                "all_leaf_fact_ids": leaf_ids,
                "source_derived_ids": derived_ids,
                "source_document_ids": sorted({bindings[key]["document_id"] for key in leaf_ids}),
                "source_definition_ids": sorted(
                    {facts[key]["source_definition_id"] for key in leaf_ids}
                ),
            },
            public=public_projection(sample["question"], native_sources, contract),
            private={
                "canonical_target": item["target"],
                "answer_exact": str(independently_recomputed),
                "answer_payload": candidate["answer_payload"],
                "reference_plan": plan,
                "relation_certificate": certificate,
                "basis_witnesses": certificate["witnesses"],
                "oracle_execution_origin": "deterministic reference only, not Teacher behavior",
            },
            validation={
                "status": "passed",
                "qa_check_ids": [row["check_id"] for row in checks],
                "persisted_question_roundtrip_checked_by_QA_pipeline": True,
                "native_value_period_definition_checked_again_at_export": True,
                "all_leaf_source_use_checked_again_at_export": True,
                "independent_target_recompute": str(independently_recomputed),
            },
            actual_model_sessions=[],
            training_materials=[],
            tokenizer_artifacts=[],
        )
        teacher_messages(bundle)
        directory = Path(output) / "tasks" / item["task_id"]
        write_json(directory / "task_bundle.json", bundle)
        write_json(directory / "teacher_visible.json", teacher_messages(bundle))
        exported.append(
            {
                "task_id": item["task_id"],
                "bundle_id": bundle["id"],
                "path": str((directory / "task_bundle.json").relative_to(output)),
                "family": item["family"],
                "source_cluster": bundle["source_cluster"],
                "qa_build_id": qa_build_id,
                "qa_id": sample["qa_id"],
            }
        )
        db.execute("UPDATE qa_samples SET split='train' WHERE qa_id=?", (sample["qa_id"],))
    return exported, rejected


def dump_parents(db, output):
    tables = [
        "pipeline_builds",
        "canonical_entities",
        "metrics",
        "source_metric_definitions",
        "source_registry",
        "raw_objects",
        "source_documents",
        "raw_extracted_tables",
        "document_text_chunks",
        "atomic_facts",
        "standardized_facts",
        "fact_quality_checks",
        "derived_facts",
        "kg_builds",
        "kg_nodes",
        "kg_edges",
        "kg_quality_checks",
        "qa_builds",
        "qa_templates",
        "qa_graph_patterns",
        "qa_candidates",
        "qa_operation_plans",
        "qa_samples",
        "qa_evidence_paths",
        "qa_quality_checks",
    ]
    inventory = []
    for table in tables:
        rows = db.fetchall("SELECT * FROM " + table + " ORDER BY 1")
        for offset in range(0, len(rows), 500):
            path = Path(output) / "parents" / table / f"{offset // 500:04d}.json"
            write_json(path, rows[offset : offset + 500])
        inventory.append({"table": table, "row_count": len(rows), "chunk_size": 500})
    write_json(Path(output) / "parent_table_inventory.json", inventory)
    return inventory


def run(root, output, native_report):
    root, output = Path(root).resolve(), Path(output)
    db = RecordDB(str(root / WORK / "native_fact_qa.sqlite3"))
    kg = native_report["kg_build"]
    bindings = json.loads((output / "native_bindings.json").read_bytes())
    facts = pipeline._load_facts_by_id(
        db, list(bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
    )
    usage = {
        key: {
            "split": row["split"],
            "allowed_uses": row["allowed_uses"],
            "source_cluster": row["source_cluster"],
        }
        for key, row in bindings.items()
    }
    write_json(output / "all_leaf_usage.json", usage)
    selected, failures, enumeration = enumerate_bindings(facts, bindings, usage)
    write_json(output / "binding_failures.json", failures)
    write_json(output / "binding_enumeration.json", enumeration)
    dual_queues = [
        deque(selected[group])
        for group in ("stock_rollforward", "annual_flow", "company_defined_metric")
    ]
    duals = []
    while any(dual_queues):
        for queue in dual_queues:
            if queue:
                duals.append(queue.popleft())
    first = duals[:12] + selected["control"][:8]
    remaining = duals[12:] + selected["control"][8:]
    require(
        len(first) == 20 and len(duals[:12]) == 12 and len(selected["control"][:8]) == 8,
        "factory.actual_first_20_supply_required",
    )
    exported, rejected, batches = [], [], []
    for name, items in (("first_20", first), ("candidate_catalog", remaining)):
        if not items:
            continue
        qa_build_id, candidates, plans, compilations, validation = compile_batch(
            db, kg, items, facts, bindings, output, name
        )
        batch_exported, batch_rejected = export_batch(
            db,
            kg,
            qa_build_id,
            items,
            candidates,
            plans,
            compilations,
            facts,
            bindings,
            usage,
            output,
        )
        exported.extend(batch_exported)
        rejected.extend(batch_rejected)
        batch = {
            "batch": name,
            "qa_build_id": qa_build_id,
            "requested_count": len(items),
            "exported_count": len(batch_exported),
            "qa_validation": validation,
        }
        batches.append(batch)
        write_json(output / name / "export_report.json", batch)
        print(json.dumps(batch, ensure_ascii=False), flush=True)
        if name == "first_20":
            require(len(batch_exported) == 20, "factory.first_20_end_to_end_gate")
    write_json(
        output / "catalog.json",
        record(
            "fixed_task_catalog",
            tasks=exported,
            both_future_pools_use_this_exact_catalog=True,
            final_training_population_selected=False,
            training_mu_fixed=False,
        ),
    )
    write_json(output / "qa_validation_rejections.json", rejected)
    parents = dump_parents(db, output)
    summary = record(
        "task_factory_report",
        status="ACTUAL_QA_BUILDS_AND_TASK_BUNDLES_EXPORTED",
        kg_build_id=kg["kg_build_id"],
        batches=batches,
        exported_task_count=len(exported),
        family_counts=dict(Counter(value["family"] for value in exported)),
        source_cluster_count=len({value["source_cluster"] for value in exported}),
        candidate_caps=CAPS,
        binding_rejection_count=len(failures),
        binding_rejection_reasons=dict(Counter(value["reason"] for value in failures)),
        qa_rejection_count=len(rejected),
        parent_tables=parents,
        target_group_shortfalls={
            group: max(0, 40 - sum(row["family"] == group for row in exported))
            for group in ("annual_flow", "stock_rollforward", "company_defined_metric")
        },
        original_FinQA_questions_used=0,
        original_FinQA_answers_used=0,
        original_FinQA_programs_used=0,
        first_20_then_catalog_in_one_stage=True,
        no_model_correctness_based_task_selection=True,
        actual_Teacher_sessions=0,
        actual_Student_runs=0,
        task_generation_LLM_calls=0,
        actual_tokenizer_loads=0,
        actual_GPU_runs=0,
        training_material_rows=0,
        final_200_task_training_population_ready=False,
        future_training_or_material_kernel_frozen=False,
    )
    write_json(output / "report.json", summary)
    db.close()
    return summary
