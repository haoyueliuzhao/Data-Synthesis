"""Fresh source-isolated panel preparation, never a Teacher/Student experiment.

The parent stage must freeze both ``policy()`` and the source metadata identity
before calling ``run``. This module has no auto-run or unbounded refill path.
"""

import json
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from finraw.qa import pipeline
from finraw.qa.graph_patterns import get_pattern, pattern_content_hash
from finraw.qa.store import insert_rows

from ..finance_qa_vnext_task_build.archive import WORK, RecordDB, record, require, sha, write_json
from ..finance_qa_vnext_task_build.factory import dump_parents, qa_config
from ..finance_qa_vnext_task_build.protocol import all_leaf_uses, source_split
from . import panel_native, panel_rules


def policy():
    return panel_rules.policy()


def inspect_source_metadata(root):
    """Permitted pre-freeze read-only metadata census; no numeric source scan."""
    db = RecordDB(str(Path(root) / WORK / "qa_build.sqlite3"))
    try:
        return panel_native.source_metadata(root, db)
    finally:
        db.close()


def compile_batch(db, kg, items, facts, bindings, usage, output, split):
    output = Path(output)
    initial = pipeline.build_qa_candidates(db, qa_config(), kg_build_id=kg["kg_build_id"])
    qa_build_id = initial["qa_build_id"]
    require(initial["candidate_count"] == 0, "panel.no_default_candidates")
    entities = {
        row["entity_id"]: row["canonical_name"]
        for row in db.fetchall("SELECT * FROM canonical_entities")
    }
    metrics = {row["metric_id"]: row for row in db.fetchall("SELECT * FROM metrics")}
    candidates, plans, compilations = [], [], []
    derived = defaultdict(list)
    for row in db.fetchall(
        "SELECT * FROM derived_facts WHERE build_id=? AND input_build_id=? "
        "AND derived_type IN ('difference','yoy_growth') "
        "AND verification_status IN ('single_source','cross_verified')",
        (kg["input_qa_build_id"], kg["input_fact_build_id"]),
    ):
        derived[row["derived_type"], tuple(sorted(json.loads(row["input_fact_ids"])))].append(row)
    for item in items:
        match = dict(item["match"])
        lineage = {}
        if item["family"] == "dual_sufficient":
            derived_type = (
                "difference" if item["target"]["quantity"] == "difference" else "yoy_growth"
            )
            parents = derived[derived_type, tuple(sorted(match["fact_ids"]))]
            # Not a guessed DerivedFact: if this stage's real derived builder
            # cannot supply the temporal parent, retain the task as rejected.
            if len(parents) != 1:
                compilations.append(
                    record(
                        "panel_compilation_rejection",
                        task_id=item["task_id"],
                        reason="panel.no_unique_real_DerivedFact_parent",
                        parent_count=len(parents),
                    )
                )
                continue
            parent = parents[0]
            match["source_derived_ids"] = [parent["derived_id"]]
            lineage[parent["derived_id"]] = json.loads(parent["input_fact_ids"])
        leaf_ids = all_leaf_uses(
            [*item["certificate"]["leaf_fact_ids"], *lineage], lineage, usage, expected=split
        )
        panel_rules.basic([facts[key] for key in leaf_ids], bindings, usage, split)
        pattern = get_pattern(item["pattern_id"])
        candidate, plan = pipeline._graph_pattern_candidate(
            db,
            match,
            pattern,
            facts,
            qa_build_id,
            kg["kg_build_id"],
            entities,
            {key: row["canonical_name"] for key, row in metrics.items()},
            metrics,
            panel_rules.semantic_policy(),
        )
        compilation = record(
            "panel_pattern_compilation",
            task_id=item["task_id"],
            qa_build_id=qa_build_id,
            candidate_id=candidate["candidate_id"],
            operation_plan_id=plan["plan_id"],
            pattern_id=pattern.pattern_id,
            pattern_hash=pattern_content_hash(pattern),
            pattern_spec=pattern.as_row(),
            match=match,
            source_leaf_ids=leaf_ids,
            certificate_id=item["certificate"]["id"],
            candidate_eligibility=candidate["eligibility_status"],
            rejection_reasons=candidate["rejection_reasons"],
            compiler="finraw.qa.pipeline._graph_pattern_candidate",
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
            "panel_adapter": {
                "split": split,
                "pre_QA_fixed_targets": len(items),
                "no_refill_after_QA_rejection": True,
            },
        }
        db.execute(
            "UPDATE qa_builds SET candidate_count=?, notes=? WHERE qa_build_id=?",
            (len(candidates), json.dumps(notes, sort_keys=True), qa_build_id),
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


def public_source_index(inputs, facts, bindings, output):
    """Keep every selected annual record AND access to every original snapshot byte.

    Complete snapshots are referenced once, never duplicated 900 times. A future
    online evaluator must implement the declared read_source tool; it must not
    reduce the publicly available document to a private reference plan's leaves.
    """
    result = {}
    for item in inputs:
        raw = item["raw_object"]
        rows = []
        for identifier, bound in sorted(bindings.items()):
            if bound["entity_id"] != item["entity"]["entity_id"]:
                continue
            rows.append(
                {
                    "source_id": identifier,
                    "source_kind": "original_companyfacts_observation",
                    "original_url": raw["original_url"],
                    "raw_sha256": raw["content_sha256"],
                    "native_pointer": bound["pointer"],
                    "concept": "us-gaap:" + bound["tag"],
                    "label": bound["native_definition"]["label"],
                    "definition": bound["native_definition"]["description"],
                    "unit": "USD",
                    "record": bound["record"],
                    "graph_ready_for_registered_tasks": identifier in facts,
                }
            )
        source = record(
            "panel_public_source_document",
            source_cluster=item["source_cluster"],
            source_id=raw["raw_object_id"],
            complete_original_snapshot={
                "path": item["local_path"],
                "sha256": raw["content_sha256"],
                "bytes": raw["content_size_bytes"],
                "original_url": raw["original_url"],
                "media_type": "application/json",
                "all_concepts_units_years_and_occurrences_available": True,
            },
            native_annual_records=rows,
            selection_rule=(
                "all observations selected before task enumeration, "
                "never answer-witness-only projection"
            ),
            omitted_source_numeric_records=False,
        )
        path = Path(output) / "public_sources" / (raw["raw_object_id"] + ".json")
        write_json(path, source)
        result[item["source_cluster"]] = {
            "source_id": source["source_id"],
            "document_id": source["id"],
            "path": str(path.relative_to(output)),
            "sha256": sha(path),
            "bytes": path.stat().st_size,
            "complete_original_snapshot": source["complete_original_snapshot"],
            "native_annual_record_count": len(rows),
        }
    write_json(Path(output) / "public_source_index.json", result)
    return result


def score_final(final, expected, quantity):
    """Secondary target correctness only; never stand in for full trace validity."""
    try:
        amount = Decimal(str(final["value"]))
        reference = Decimal(str(expected["value"]))
        unit = "percent" if quantity == "relative_change" else "million USD"
        amount_ok = (
            amount.is_finite()
            and reference.is_finite()
            and final.get("unit") == unit
            and amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            == reference.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
        period_ok = "period" not in expected or str(final.get("period")) == str(expected["period"])
        return {
            "target_correct": bool(amount_ok and period_ok),
            "amount_correct": bool(amount_ok),
            "period_correct": period_ok,
            "complete_trajectory_qualified": None,
            "is_primary_utility_score": False,
        }
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return {
            "target_correct": False,
            "amount_correct": False,
            "period_correct": False,
            "complete_trajectory_qualified": None,
            "is_primary_utility_score": False,
        }


def export_batch(
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
    sources,
    output,
    split,
):
    item_map = {item["task_id"]: item for item in items}
    candidate_map = {row["candidate_id"]: row for row in candidates}
    plan_map = {row["plan_id"]: row for row in plans}
    compilation_map = {row["candidate_id"]: row for row in compilations if "candidate_id" in row}
    exported, rejected = [], []
    for compilation in compilations:
        if "candidate_id" not in compilation:
            rejected.append(compilation)
    for sample in db.fetchall(
        "SELECT * FROM qa_samples WHERE qa_build_id=? ORDER BY qa_id", (qa_build_id,)
    ):
        compilation = compilation_map[sample["candidate_id"]]
        item = item_map[compilation["task_id"]]
        candidate = candidate_map[sample["candidate_id"]]
        if sample["validation_status"] != "passed":
            rejected.append(
                {
                    "task_id": item["task_id"],
                    "qa_id": sample["qa_id"],
                    "reason": "panel.QA_validation_rejected",
                }
            )
            continue
        leaves = compilation["source_leaf_ids"]
        panel_rules.basic([facts[key] for key in leaves], bindings, usage, split)
        require(
            all_leaf_uses(leaves, {}, usage, expected=split) == sorted(leaves),
            "panel.export_leaf_permission",
        )
        expected = panel_rules.independent_answer(item, facts)
        require(
            Decimal(expected["value"]) == Decimal(candidate["answer_payload"]["value"]),
            "panel.independent_value_recompute",
        )
        if "period" in expected:
            require(
                str(candidate["answer_payload"].get("period")) == expected["period"],
                "panel.independent_peak_period_recompute",
            )
        checks = db.fetchall(
            "SELECT * FROM qa_quality_checks WHERE qa_id=? ORDER BY check_name", (sample["qa_id"],)
        )
        require(
            checks and all(row["check_status"] == "passed" for row in checks),
            "panel.actual_QA_checks_passed",
        )
        source = sources[item["target"]["source_cluster"]]
        public = {
            "question": sample["question"],
            "source_document": source,
            "quantity_contract": {
                "unit": item["target"]["unit"],
                "currency": item["target"]["currency"],
                "decimal_places": 2,
                "rounding": "half away from zero",
                "period_required": "period" in expected,
            },
            "source_policy": (
                "Use the complete fixed original source, its source definitions and actual "
                "observation periods; every original snapshot record remains available."
            ),
            "tool_contract": {
                "read_source": (
                    "Read the complete public source by source_id, optionally using an exact "
                    "native JSON pointer; empty pointer returns the complete original "
                    "snapshot, never a private Oracle projection."
                ),
                "calculate": (
                    "Execute arithmetic over explicitly read and cited original numeric "
                    "source values."
                ),
                "Final": (
                    "Return the requested quantity and units; a peak-followup question "
                    "also requires the requested year."
                ),
            },
        }
        bundle = record(
            "EvaluationTaskBundle",
            task_id=item["task_id"],
            split=split,
            allowed_uses=[split],
            source_cluster=item["target"]["source_cluster"],
            family=item["family"],
            parents={
                "qa_build_id": qa_build_id,
                "qa_id": sample["qa_id"],
                "candidate_id": candidate["candidate_id"],
                "pattern_id": candidate["pattern_id"],
                "pattern_hash": candidate["pattern_hash"],
                "operation_plan_id": candidate["operation_plan_id"],
                "compilation_id": compilation["id"],
                "kg_build_id": kg["kg_build_id"],
                "fact_build_id": kg["input_fact_build_id"],
                "all_leaf_fact_ids": leaves,
                "source_derived_ids": compilation["match"].get("source_derived_ids", []),
            },
            public=public,
            private={
                "canonical_target": item["target"],
                "answer": expected,
                "answer_payload": candidate["answer_payload"],
                "reference_plan": plan_map[candidate["operation_plan_id"]],
                "relation_certificate": item["certificate"],
                "score_contract": policy()["score"],
                "reference_plan_is_not_unique_allowed_execution": True,
            },
            validation={
                "status": "passed",
                "qa_check_ids": [row["check_id"] for row in checks],
                "public_target_and_score_fixed_before_Student": True,
            },
            Teacher_sessions=0,
            Student_sessions=0,
        )
        path = Path(output) / "tasks" / item["task_id"] / "task_bundle.json"
        write_json(path, bundle)
        exported.append(
            {
                "task_id": item["task_id"],
                "bundle_id": bundle["id"],
                "path": str(path.relative_to(output)),
                "family": item["family"],
                "source_cluster": bundle["source_cluster"],
                "raw_snapshot_sha256": source["complete_original_snapshot"]["sha256"],
                "periods": sorted({facts[key]["period_end"] for key in leaves}),
                "qa_build_id": qa_build_id,
                "qa_id": sample["qa_id"],
            }
        )
        db.execute("UPDATE qa_samples SET split=? WHERE qa_id=?", (split, sample["qa_id"]))
    sampled = {row["task_id"] for row in exported} | {row["task_id"] for row in rejected}
    rejected.extend(
        {"task_id": item["task_id"], "reason": "panel.candidate_not_emitted_as_QA_sample"}
        for item in items
        if item["task_id"] not in sampled
    )
    return exported, rejected


def correlation_report(tasks):
    issuer = Counter(row["source_cluster"] for row in tasks)
    snapshots = Counter(row["raw_snapshot_sha256"] for row in tasks)
    periods = Counter((row["source_cluster"], period) for row in tasks for period in row["periods"])
    return {
        "task_count": len(tasks),
        "source_CIK_cluster_count": len(issuer),
        "original_snapshot_count": len(snapshots),
        "tasks_per_CIK_cluster": dict(sorted(issuer.items())),
        "tasks_per_original_snapshot": dict(sorted(snapshots.items())),
        "issuer_period_membership_counts": [
            {"source_cluster": key[0], "period_end": key[1], "task_count": count}
            for key, count in sorted(periods.items())
        ],
        "overlapping_issuer_period_pairs": sum(
            count * (count - 1) // 2 for count in periods.values()
        ),
        "overlap_pair_sum_can_count_one_pair_in_multiple_periods": True,
        "effective_sample_size_or_power_inferred": False,
    }


def run(root, output, work, *, expected_policy_id, expected_source_metadata_id, freeze_id):
    """Call once only after the parent stage has frozen source/rule/code identities."""
    root, output, work = Path(root).resolve(), Path(output), Path(work)
    require(expected_policy_id == policy()["id"], "panel.frozen_rule_identity")
    require(isinstance(freeze_id, str) and bool(freeze_id), "panel.parent_freeze_required")
    metadata = inspect_source_metadata(root)
    require(metadata["id"] == expected_source_metadata_id, "panel.frozen_source_metadata_identity")
    require(not output.exists(), "panel.new_output_only")
    require(
        output.resolve().is_relative_to(root) and work.resolve().is_relative_to(root),
        "panel.contained_output_and_work",
    )
    output.mkdir(parents=True)
    write_json(output / "policy.json", policy())
    write_json(output / "source_metadata.json", metadata)
    panels, all_tasks = {}, []
    for split in ("dev", "confirm"):
        split_output = output / split
        db, inputs, bindings, native = panel_native.build(
            root, split_output, work / split / "native_fact_qa.sqlite3", metadata, split
        )
        try:
            kg = native["kg_build"]
            facts = pipeline._load_facts_by_id(
                db, list(bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
            )
            # A normalized row is usable only if its actual KG node exists.
            present = {
                row["source_pk"]
                for row in db.fetchall(
                    "SELECT source_pk FROM kg_nodes WHERE kg_build_id=? "
                    "AND node_type='Fact' AND is_active=1",
                    (kg["kg_build_id"],),
                )
            }
            facts = {key: row for key, row in facts.items() if key in present}
            usage = {
                key: {
                    "split": row["split"],
                    "allowed_uses": row["allowed_uses"],
                    "source_cluster": row["source_cluster"],
                }
                for key, row in bindings.items()
            }
            write_json(split_output / "all_leaf_usage.json", usage)
            payloads = {
                item["raw_object"]["raw_object_id"]: json.loads(
                    (root / item["local_path"]).read_bytes()
                )
                for item in inputs
            }
            selected, failures, enumeration = panel_rules.enumerate_targets(
                facts, bindings, usage, split, payloads
            )
            write_json(split_output / "binding_failures.json", failures)
            write_json(split_output / "binding_enumeration.json", enumeration)
            items = [row for group in panel_rules.GROUPS for row in selected[group]]
            sources = public_source_index(inputs, facts, bindings, split_output)
            qa_build_id, candidates, plans, compilations, validation = compile_batch(
                db, kg, items, facts, bindings, usage, split_output / "QA", split
            )
            exported, rejected = export_batch(
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
                sources,
                split_output,
                split,
            )
            write_json(split_output / "QA_export_rejections.json", rejected)
            counts = Counter(row["family"] for row in exported)
            shortages = {
                group: max(0, cap - counts[group])
                for group, cap in panel_rules.TARGETS[split].items()
            }
            catalog = record(
                "evaluation_task_catalog",
                split=split,
                tasks=exported,
                requested_counts=panel_rules.TARGETS[split],
                realized_counts=dict(counts),
                shortages=shortages,
                selection_complete_without_refill=True,
                Teacher_outcomes_used=False,
                source_metadata_id=metadata["id"],
                rule_id=policy()["id"],
                parent_freeze_id=freeze_id,
            )
            write_json(split_output / "catalog.json", catalog)
            correlation = correlation_report(exported)
            write_json(split_output / "source_correlation_report.json", correlation)
            dump_parents(db, split_output)
            panels[split] = {
                "catalog_id": catalog["id"],
                "realized_counts": dict(counts),
                "shortages": shortages,
                "selected_before_QA": len(items),
                "QA_export_rejections": len(rejected),
                "binding_rejection_counts": dict(Counter(row["reason"] for row in failures)),
                "source_correlation": correlation,
                "native_fact_build_id": native["id"],
                "qa_build_id": qa_build_id,
                "QA_validation": validation,
            }
            all_tasks.extend({**row, "split": split} for row in exported)
        finally:
            db.close()
    dev_sources = {row["source_cluster"] for row in all_tasks if row["split"] == "dev"}
    confirm_sources = {row["source_cluster"] for row in all_tasks if row["split"] == "confirm"}
    require(dev_sources.isdisjoint(confirm_sources), "panel.dev_confirm_CIK_disjoint")
    require(
        all(source_split(row["source_cluster"]) == row["split"] for row in all_tasks),
        "panel.all_exported_original_splits",
    )
    require(
        len({row["task_id"] for row in all_tasks}) == len(all_tasks),
        "panel.no_task_or_seed_multiplication",
    )
    complete = all(not any(value["shortages"].values()) for value in panels.values())
    report = record(
        "evaluation_panel_preparation",
        status="FIXED_REAL_PANELS_PREPARED" if complete else "PARTIAL_REAL_PANELS_SUPPLY_SHORTFALL",
        panels=panels,
        unique_task_count=len(all_tasks),
        expected_task_count=900,
        quota_complete=complete,
        source_CIK_split_disjoint=True,
        historical_confirmation_issuers_reused=False,
        primary_scoring_contract_fixed=policy()["score"],
        complete_source_read_tool_required_for_future_sessions=True,
        online_evaluation_sessions_authorized=False,
        source_surface_rewrite_requests=0,
        Teacher_sessions=0,
        Student_sessions=0,
        tokenizer_loads=0,
        GPU_operations=0,
        rule_id=policy()["id"],
        parent_freeze_id=freeze_id,
    )
    write_json(output / "report.json", report)
    return report


def read_complete_source(root, source_reference, *, pointer=""):
    """Public-only evaluator helper; no TaskBundle private field is read."""
    root = Path(root).resolve()
    reference = source_reference["complete_original_snapshot"]
    path = root / reference["path"]
    require(
        path.resolve().is_relative_to(root) and not path.is_symlink(),
        "panel.public_source_containment",
    )
    require(
        path.stat().st_size == reference["bytes"] and sha(path) == reference["sha256"],
        "panel.public_original_snapshot_identity",
    )
    value = json.loads(path.read_bytes())
    require(pointer == "" or pointer.startswith("/"), "panel.exact_JSON_pointer")
    if pointer:
        for token in pointer[1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            value = value[int(token)] if isinstance(value, list) else value[token]
    return value
