"""Actual-period panel reconstruction after one explicit rule/source/code freeze."""

import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from finraw.qa import pipeline

from ..finance_qa_vnext_catalog_bridge import panel_native
from ..finance_qa_vnext_catalog_bridge import panels as old_panels
from ..finance_qa_vnext_task_build.archive import record, require, sha, write_json
from ..finance_qa_vnext_task_build.factory import dump_parents
from ..finance_qa_vnext_task_build.protocol import source_split
from ..finance_qa_vnext_task_build.relations import actual_period, value
from . import panel_rules, periods
from .panel_diagnosis import OLD, diagnose

policy = panel_rules.policy
inspect_source_metadata = old_panels.inspect_source_metadata


def public_bytes(public):
    """Canonical public-object SHA; old bundles had no independent public file."""
    return json.dumps(public, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def load_prior(root, split):
    directory = Path(root) / OLD / split
    targets = json.loads((directory / "QA/target_bindings.json").read_bytes())
    catalog = json.loads((directory / "catalog.json").read_bytes())
    bundles = {
        row["task_id"]: json.loads((directory / row["path"]).read_bytes())
        for row in catalog["tasks"]
    }
    return directory, targets, bundles


def expected_answer(item, facts, contract):
    inputs = item["match"]["input_bindings"]
    if item["family"] == "dual_sufficient":
        result = value(facts[inputs["current"]]) - value(facts[inputs["previous"]])
        if item["target"]["quantity"] == "relative_change":
            result = result * 100 / value(facts[inputs["previous"]])
        return {"value": str(result)}
    if item["family"] == "composition_required":
        return {"value": str(sum(value(facts[key]) for key in inputs["series"]) / 3)}
    chosen = max((facts[key] for key in inputs["primary_series"]), key=value)
    matching = [
        facts[key]
        for key in inputs["secondary_series"]
        if actual_period(facts[key]) == actual_period(chosen)
    ]
    require(len(matching) == 1, "readiness.unique_same_actual_period_followup")
    selected = next(
        row for row in contract["periods"] if (row["start"], row["end"]) == actual_period(chosen)
    )
    return {
        "value": str(value(matching[0])),
        "period_id": selected["period_id"],
        "actual_period": {"start": selected["start"], "end": selected["end"]},
    }


def export_batch(
    db, kg, compiled, items, facts, bindings, sources, output, split, freeze_id, prior
):
    qa_build_id, candidates, plans, compilations, _ = compiled
    item_map = {row["task_id"]: row for row in items}
    candidate_map = {row["candidate_id"]: row for row in candidates}
    plan_map = {row["plan_id"]: row for row in plans}
    compilation_map = {row["candidate_id"]: row for row in compilations if "candidate_id" in row}
    rejected = [row for row in compilations if "candidate_id" not in row]
    exported = []
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
                    "reason": "readiness.QA_validation_rejected",
                }
            )
            continue
        contract = periods.build_contract(item, facts, bindings)
        expected = expected_answer(item, facts, contract)
        require(
            Decimal(expected["value"]) == Decimal(candidate["answer_payload"]["value"]),
            "readiness.independent_reference_amount",
        )
        if "actual_period" in expected:
            actual = candidate["answer_payload"].get("actual_period")
            require(
                actual is not None
                and actual.get("start", actual.get("period_start"))
                == expected["actual_period"]["start"]
                and actual.get("end", actual.get("period_end")) == expected["actual_period"]["end"],
                "readiness.reference_exact_selected_period",
            )
        checks = db.fetchall(
            "SELECT * FROM qa_quality_checks WHERE qa_id=? ORDER BY check_name", (sample["qa_id"],)
        )
        require(
            checks and all(row["check_status"] == "passed" for row in checks),
            "readiness.actual_QA_checks",
        )
        previous = prior.get(item["task_id"])
        question = sample["question"]
        question_reused = bool(previous and previous["public"]["question"] == question)
        if question_reused:
            question = previous["public"]["question"]
        public = {
            "question": question + "\n\n" + periods.render_public_periods(contract),
            "period_contract": contract,
            "source_document": sources[item["target"]["source_cluster"]],
            "quantity_contract": {
                "unit": item["target"]["unit"],
                "currency": item["target"]["currency"],
                "decimal_places": 2,
                "rounding": "half away from zero",
                "period_required": "actual_period" in expected,
            },
            "source_policy": (
                "Complete original pinned companyfacts snapshot remains available through bounded "
                "source-driven queries and exact reads; no private answer-leaf projection."
            ),
            "tool_contract": {
                "query_source": (
                    "Query original concepts, dates, and units with bounded pagination; "
                    "preserve source definitions and actual dates."
                ),
                "read_source": "Read exact original records, not a private reference-only subset.",
                "calculate": (
                    "Execute explicit arithmetic/comparisons using actually read source operands."
                ),
                "select_max": (
                    "Select from all listed candidate-period source values in one array; "
                    "retain the complete candidate support."
                ),
                "compare": (
                    "Compare candidates step by step; the final selection proof must cover "
                    "every listed candidate period."
                ),
                "lookup_selected": (
                    "Read the secondary metric for the exact actual period established "
                    "by select_max or the complete comparison chain."
                ),
                "Final": (
                    "First Final stops execution; report value, requested unit, "
                    "and selected actual period_id for a peak-followup target."
                ),
            },
        }
        messages = [
            {"role": "user", "content": json.dumps(public, ensure_ascii=False, sort_keys=True)}
        ]
        task_dir = Path(output) / "tasks" / item["task_id"]
        write_json(task_dir / "public_messages.json", messages)
        stored = json.loads((task_dir / "public_messages.json").read_bytes())
        period_check = periods.validate_public_periods(
            stored, contract, bindings, canonical_target=item["target"]
        )
        require(
            period_check["passed"],
            "readiness.persisted_public_period_admission:" + ",".join(period_check["errors"]),
        )
        surface = record(
            "evaluation_surface_version",
            task_id=item["task_id"],
            public_messages_sha256=sha(task_dir / "public_messages.json"),
            qa_build_id=qa_build_id,
            qa_id=sample["qa_id"],
            period_contract_id=contract["id"],
            parent_freeze_id=freeze_id,
            prior_bundle_id=previous["id"] if previous else None,
            prior_qa_question_bytes_reused=question_reused,
            base_qa_question_sha256=hashlib.sha256(question.encode()).hexdigest(),
        )
        bundle = record(
            "EvaluationTaskBundle",
            version=2,
            task_id=item["task_id"],
            split=split,
            allowed_uses=[split],
            source_cluster=item["target"]["source_cluster"],
            family=item["family"],
            parents={
                "qa_build_id": qa_build_id,
                "qa_id": sample["qa_id"],
                "candidate_id": sample["candidate_id"],
                "pattern_id": candidate["pattern_id"],
                "pattern_hash": candidate["pattern_hash"],
                "operation_plan_id": candidate["operation_plan_id"],
                "compilation_id": compilation["id"],
                "kg_build_id": kg["kg_build_id"],
                "fact_build_id": kg["input_fact_build_id"],
                "all_leaf_fact_ids": compilation["source_leaf_ids"],
                "source_derived_ids": compilation["match"].get("source_derived_ids", []),
                "prior_bundle_id": previous["id"] if previous else None,
            },
            surface=surface,
            public=public,
            private={
                "canonical_target": item["target"],
                "answer": expected,
                "answer_payload": candidate["answer_payload"],
                "reference_plan": plan_map[candidate["operation_plan_id"]],
                "relation_certificate": item["certificate"],
                "reference_plan_is_not_unique_allowed_execution": True,
            },
            validation={
                "status": "passed",
                "qa_check_ids": [row["check_id"] for row in checks],
                "actual_period_check": period_check,
            },
            Teacher_sessions=0,
            Student_sessions=0,
        )
        write_json(task_dir / "task_bundle.json", bundle)
        exported.append(
            {
                "task_id": item["task_id"],
                "bundle_id": bundle["id"],
                "path": str((task_dir / "task_bundle.json").relative_to(output)),
                "public_path": str((task_dir / "public_messages.json").relative_to(output)),
                "surface_version_id": surface["id"],
                "prior_base_qa_question_bytes_reused": question_reused,
                "public_messages_sha256": surface["public_messages_sha256"],
                "family": item["family"],
                "source_cluster": bundle["source_cluster"],
                "raw_snapshot_sha256": public["source_document"]["complete_original_snapshot"][
                    "sha256"
                ],
                "periods": sorted(
                    {facts[key]["period_end"] for key in compilation["source_leaf_ids"]}
                ),
                "qa_build_id": qa_build_id,
                "qa_id": sample["qa_id"],
            }
        )
        db.execute("UPDATE qa_samples SET split=? WHERE qa_id=?", (split, sample["qa_id"]))
    accounted = {row["task_id"] for row in [*exported, *rejected]}
    for item in items:
        if item["task_id"] not in accounted:
            compiler = next(row for row in compilations if row["task_id"] == item["task_id"])
            rejected.append(
                {
                    "task_id": item["task_id"],
                    "reason": "readiness.candidate_not_emitted_as_QA_sample",
                    "candidate_id": compiler.get("candidate_id"),
                    "candidate_rejection_reasons": compiler.get("rejection_reasons"),
                }
            )
    return exported, rejected


def impact_rows(root, split, prior_targets, prior, exported, items, bindings, selected_ids):
    lookup = {row["task_id"]: row for row in exported}
    targets = {row["task_id"]: row for row in items}
    original_bindings = json.loads((Path(root) / OLD / split / "native_bindings.json").read_bytes())
    result = []
    for old_item in prior_targets:
        identifier = old_item["task_id"]
        old_bundle = prior.get(identifier)
        new_entry = lookup.get(identifier)
        new_item = targets.get(identifier)
        prior_periods = old_item["target"].get("actual_periods") or [
            old_item["target"]["previous_period"],
            old_item["target"]["current_period"],
        ]
        prior_calendar_conflict = bool(
            old_bundle
            and "calendar year" in old_bundle["public"]["question"].lower()
            and any(
                start != end[:4] + "-01-01" or end != end[:4] + "-12-31"
                for start, end in prior_periods
            )
        )
        require(
            new_item is None
            or public_bytes(new_item["target"]) == public_bytes(old_item["target"]),
            "readiness.no_changed_target_under_old_identity",
        )
        result.append(
            record(
                "panel_target_impact",
                task_id=identifier,
                split=split,
                prior_exported=old_bundle is not None,
                prior_bundle_id=old_bundle["id"] if old_bundle else None,
                prior_public_sha256=hashlib.sha256(public_bytes(old_bundle["public"])).hexdigest()
                if old_bundle
                else None,
                prior_public_sha_rule=(
                    "UTF-8 canonical JSON of exact parsed old public object; "
                    "old archive has no separate public_messages file"
                ),
                prior_public=old_bundle["public"] if old_bundle else None,
                prior_public_calendar_label_conflict=prior_calendar_conflict,
                revisions=(
                    ["new actual-period Derived/QA parent for prior unexported registered target"]
                    if old_bundle is None
                    else [
                        "actual interval contract and source-date independent admission",
                        "unsupported calendar-year label corrected"
                        if prior_calendar_conflict
                        else "no unsupported calendar-year literal detected in prior question",
                        "prior base QA question bytes reused"
                        if new_entry and new_entry["prior_base_qa_question_bytes_reused"]
                        else (
                            "base QA question version updated to explicit actual comparison periods"
                        ),
                    ]
                ),
                canonical_target=old_item["target"],
                original_actual_period_evidence=[
                    {
                        "fact_id": key,
                        "raw_sha256": original_bindings[key]["raw_sha256"],
                        "pointer": original_bindings[key]["pointer"],
                        "record": original_bindings[key]["record"],
                    }
                    for key in old_item["match"]["fact_ids"]
                ],
                actual_period_evidence=None
                if new_item is None
                else [
                    {
                        "fact_id": key,
                        "raw_sha256": bindings[key]["raw_sha256"],
                        "pointer": bindings[key]["pointer"],
                        "record": bindings[key]["record"],
                    }
                    for key in new_item["match"]["fact_ids"]
                ],
                new_public_identity=new_entry,
                selected_in_new_panel=identifier in selected_ids,
                canonical_target_changed=False,
                outcome="NEW_ACTUAL_PERIOD_VERSION"
                if new_entry
                else "RETAINED_UNRESOLVED_REJECTION",
                original_record_preserved=True,
            )
        )
    return result


def run(root, output, work, *, expected_policy_id, expected_source_metadata_id, freeze_id):
    root, output, work = Path(root).resolve(), Path(output).resolve(), Path(work).resolve()
    require(expected_policy_id == policy()["id"], "readiness.frozen_panel_policy")
    require(
        freeze_id and output.is_relative_to(root) and work.is_relative_to(root),
        "readiness.frozen_contained_run",
    )
    require(not output.exists(), "readiness.new_panel_version_only")
    metadata = inspect_source_metadata(root)
    require(metadata["id"] == expected_source_metadata_id, "readiness.frozen_source_metadata")
    output.mkdir(parents=True)
    write_json(output / "policy.json", policy())
    write_json(output / "source_metadata.json", metadata)
    write_json(output / "archived_twelve_gap_diagnosis.json", diagnose(root))
    reports, all_selected, all_impacts = {}, [], []
    for split in ("dev", "confirm"):
        split_output = output / split
        _, prior_targets, prior = load_prior(root, split)
        db, inputs, bindings, native = panel_native.build(
            root, split_output, work / split / "native_fact_qa.sqlite3", metadata, split
        )
        try:
            kg = native["kg_build"]
            facts = pipeline._load_facts_by_id(
                db, list(bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
            )
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
                key: {name: row[name] for name in ("split", "allowed_uses", "source_cluster")}
                for key, row in bindings.items()
            }
            write_json(split_output / "all_leaf_usage.json", usage)
            payloads = {
                item["raw_object"]["raw_object_id"]: json.loads(
                    (root / item["local_path"]).read_bytes()
                )
                for item in inputs
            }
            candidates, failures = panel_rules.enumerate_all(
                facts, bindings, usage, split, payloads, [row["task_id"] for row in prior_targets]
            )
            write_json(split_output / "all_source_qualified_candidates.json", candidates)
            write_json(split_output / "source_rejections.json", failures)
            sources = old_panels.public_source_index(inputs, facts, bindings, split_output)
            selected, exported, rejected, attempted = [], [], [], []
            remaining = {group: list(candidates[group]) for group in panel_rules.GROUPS}
            batch = 0
            while True:
                counts = Counter(row["family"] for row in selected)
                take = []
                for group in panel_rules.GROUPS:
                    missing = panel_rules.TARGETS[split][group] - counts[group]
                    if missing > 0:
                        size = (
                            missing + policy()["compile_reserve_per_group"]
                            if batch == 0
                            else policy()["compile_reserve_per_group"]
                        )
                        take.extend(remaining[group][:size])
                        del remaining[group][:size]
                if not take:
                    break
                batch_output = split_output / "QA" / f"batch_{batch:03d}"
                compiled = old_panels.compile_batch(
                    db, kg, take, facts, bindings, usage, batch_output, split
                )
                emitted, failed = export_batch(
                    db,
                    kg,
                    compiled,
                    take,
                    facts,
                    bindings,
                    sources,
                    split_output,
                    split,
                    freeze_id,
                    prior,
                )
                rank = {item["task_id"]: index for index, item in enumerate(take)}
                emitted.sort(key=lambda row: rank[row["task_id"]])
                for row in emitted:
                    if counts[row["family"]] < panel_rules.TARGETS[split][row["family"]]:
                        selected.append(row)
                        counts[row["family"]] += 1
                exported.extend(emitted)
                rejected.extend(failed)
                attempted.extend(take)
                batch += 1
                if all(
                    counts[group] == panel_rules.TARGETS[split][group]
                    for group in panel_rules.GROUPS
                ):
                    break
            chosen = {row["task_id"] for row in selected}
            write_json(split_output / "compiler_rejections.json", rejected)
            write_json(
                split_output / "compiled_overflow.json",
                [row for row in exported if row["task_id"] not in chosen],
            )
            write_json(split_output / "uncompiled_overflow.json", remaining)
            impacts = impact_rows(
                root,
                split,
                prior_targets,
                prior,
                exported,
                [row for group in candidates.values() for row in group],
                bindings,
                chosen,
            )
            write_json(split_output / "version_impact.json", impacts)
            counts = Counter(row["family"] for row in selected)
            shortages = {
                group: panel_rules.TARGETS[split][group] - counts[group]
                for group in panel_rules.GROUPS
            }
            catalog = record(
                "actual_period_evaluation_catalog",
                split=split,
                tasks=selected,
                requested_counts=panel_rules.TARGETS[split],
                realized_counts=dict(counts),
                shortages=shortages,
                parent_freeze_id=freeze_id,
                source_metadata_id=metadata["id"],
                rule_id=policy()["id"],
                Teacher_outcome_selection=False,
            )
            write_json(split_output / "catalog.json", catalog)
            correlation = old_panels.correlation_report(selected)
            write_json(split_output / "source_correlation_report.json", correlation)
            dump_parents(db, split_output)
            reports[split] = {
                "catalog_id": catalog["id"],
                "realized_counts": dict(counts),
                "shortages": shortages,
                "all_source_qualified_counts": {
                    group: len(rows) for group, rows in candidates.items()
                },
                "source_rejection_counts": dict(Counter(row["reason"] for row in failures)),
                "compiled_candidate_count": len(attempted),
                "compiler_rejection_count": len(rejected),
                "compiled_overflow_count": len(exported) - len(selected),
                "source_correlation": correlation,
                "qa_build_ids": sorted({row["qa_build_id"] for row in exported}),
                "native_fact_build_id": native["id"],
            }
            all_selected.extend({**row, "split": split} for row in selected)
            all_impacts.extend(impacts)
        finally:
            db.close()
    require(
        len(all_impacts) == 886 and sum(row["prior_exported"] for row in all_impacts) == 874,
        "readiness.complete_prior_impact_ledger",
    )
    require(
        all(source_split(row["source_cluster"]) == row["split"] for row in all_selected),
        "readiness.original_split_every_task",
    )
    require(
        len({row["task_id"] for row in all_selected}) == len(all_selected),
        "readiness.unique_selected_task_ids",
    )
    complete = all(not any(row["shortages"].values()) for row in reports.values())
    result = record(
        "actual_period_panel_report",
        status="ACTUAL_PERIOD_PANELS_PREPARED" if complete else "BLOCKED_PANEL_SUPPLY_SHORTFALL",
        panels=reports,
        unique_task_count=len(all_selected),
        quota_complete=complete,
        prior_export_impact_count=874,
        prior_registered_impact_count=886,
        all_original_records_preserved=True,
        all_selected_public_period_checks_passed=True,
        Teacher_sessions=0,
        Student_sessions=0,
        model_requests=0,
        GPU_operations=0,
        parent_freeze_id=freeze_id,
        rule_id=policy()["id"],
    )
    write_json(output / "report.json", result)
    return result
