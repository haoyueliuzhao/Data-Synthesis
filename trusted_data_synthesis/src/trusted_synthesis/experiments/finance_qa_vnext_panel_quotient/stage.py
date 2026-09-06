"""One additive, frozen measurement run on the published panel, with exact resumption."""

from __future__ import annotations

from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore

from ..finance_qa_vnext_model_execution.models import identity, read_json, record, require
from ..finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
    verify_directory,
    verify_source_snapshot,
)
from .comparison import compare_projections, reuse_clean_comparison
from .distribution import build_distribution
from .guards import guard_report, measurement_guard
from .projection import project_entry
from .rules import STAGE, quotient_rule
from .source import GROUPS, PARENT_COMMIT, history_inventory, load_inputs, preserved_sources

ARTIFACT_PREFIX = "trusted_data_synthesis/artifacts/qa_vnext_panel_quotient"
RUN_TAG = "correction_aware_v1_20260907"
AUDIT_SHA256 = "b3e216d6f125c72b5dc820da7aeb49fde03ef41030af4304c3831ee4322b7da1"


def _target(root, output):
    root, output = root.resolve(), output.resolve()
    require(
        output.is_relative_to(root / ARTIFACT_PREFIX) and output != root / ARTIFACT_PREFIX,
        "panel_quotient.additive_output_only",
    )
    return root, output


def freeze_condition(inputs, rule, implementation):
    entries = inputs["entries"]
    return record(
        "panel_quotient_condition",
        stage=STAGE,
        run_tag=RUN_TAG,
        generation_condition_id=inputs["condition"]["id"],
        rule_id=rule["id"],
        implementation_id=implementation["id"],
        predecessor_commit=PARENT_COMMIT,
        source_anchor_id=inputs["source_anchor"]["id"],
        source_binding_checks_id=inputs["source_binding_checks"]["id"],
        original_panel_report_id=inputs["report"]["id"],
        audit_directive_sha256=AUDIT_SHA256,
        audit_directive_bytes=25350,
        registration_ids=[e["registration"]["id"] for e in entries],
        qualification_ids=[e["qualification"]["id"] for e in entries],
        qualified_qualification_ids=[
            e["qualification"]["id"] for e in entries if e["qualification"]["qualified"]
        ],
        session_ids=[e["session"]["id"] for e in entries],
        frozen_outcomes=[
            {
                "label": e["label"],
                "registration_id": e["registration"]["id"],
                "qualification_id": e["qualification"]["id"],
                "session_id": e["session"]["id"],
                "qualified": e["qualification"]["qualified"],
                "end_to_end_success": e["qualification"]["end_to_end_success"],
                "status": e["qualification"]["status"],
            }
            for e in entries
        ],
        original_registration_count=16,
        original_qualified_count=15,
        task_marginal={group: {"numerator": 1, "denominator": 8} for group in GROUPS},
        new_provider_calls=0,
        new_model_sessions=0,
        new_runtime_executions=0,
        requalification=0,
        retokenization=0,
        student_forward_or_update=0,
        gpu_jobs=0,
        original_candidates_and_token_arrays="byte-preserved references only",
        epistemic_scope="post-observation finite rule instantiation on known development data",
        old_mainline="remains_paused",
    )


def prepare(root: Path, output: Path):
    root, output = _target(root, output)
    preparation = output / "preparation"
    with measurement_guard() as counts:
        if preparation.exists():
            verify_directory(preparation, kind="panel_quotient_preparation_manifest")
            implementation = read_json((preparation / "implementation.json").read_bytes())
            verify_source_snapshot(root, implementation)
            return read_json((preparation / "condition.json").read_bytes())
        inputs = load_inputs(root)
        implementation = source_snapshot(root)
        rule = quotient_rule()
        condition = freeze_condition(inputs, rule, implementation)
        history = history_inventory(root)
        preserved = preserved_sources(root)
        store = DurableStore(preparation)
        for name, value in (
            ("implementation", implementation),
            ("rule", rule),
            ("condition", condition),
            ("source_anchor", inputs["source_anchor"]),
            ("source_binding_checks", inputs["source_binding_checks"]),
            ("representation_references", inputs["representation_references"]),
            ("history_inventory", history),
            ("preserved_sources", preserved),
            ("execution_guards", guard_report(counts, "preparation")),
        ):
            store.json(name + ".json", value)
        seal_directory(
            store,
            kind="panel_quotient_preparation_manifest",
            condition_id=condition["id"],
            rule_id=rule["id"],
        )
        return condition


def _comparisons(inputs, projections):
    by_label = {p["label"]: p for p in projections}
    old_by_group = {pair["task_group"]: pair for pair in inputs["old_pairs"]}
    pairs = []
    for group in GROUPS:
        valid = [
            e
            for e in inputs["entries"]
            if e["qualification"]["task_group"] == group and e["qualification"]["qualified"]
        ]
        if len(valid) != 2:
            continue
        left, right = (by_label[e["label"]] for e in valid)
        pairs.append(
            reuse_clean_comparison(left, right, old_by_group[group])
            if group in old_by_group
            else compare_projections(left, right)
        )
    return pairs


def run(root: Path, output: Path):
    root, output = _target(root, output)
    preparation, measurement = output / "preparation", output / "measurement"
    with measurement_guard() as counts:
        manifest = verify_directory(preparation, kind="panel_quotient_preparation_manifest")
        frozen = {
            name: read_json((preparation / (name + ".json")).read_bytes())
            for name in (
                "condition",
                "rule",
                "implementation",
                "history_inventory",
                "source_anchor",
                "preserved_sources",
            )
        }
        condition, rule = frozen["condition"], frozen["rule"]
        identity(condition, "panel_quotient_condition")
        identity(rule, "panel_quotient_rule")
        require(rule == quotient_rule(), "panel_quotient.rule_changed")
        verify_source_snapshot(root, frozen["implementation"])
        if measurement.exists():
            sealed = verify_directory(measurement, kind="panel_quotient_measurement_manifest")
            require(
                sealed["condition_id"] == condition["id"], "panel_quotient.resumption_condition"
            )
            return read_json((measurement / "report.json").read_bytes())
        inputs = load_inputs(root)
        require(inputs["source_anchor"] == frozen["source_anchor"], "panel_quotient.source_changed")
        require(
            freeze_condition(inputs, rule, frozen["implementation"]) == condition,
            "panel_quotient.population_changed",
        )
        projections = [
            project_entry(e, rule, condition["generation_condition_id"]) for e in inputs["entries"]
        ]
        comparisons = _comparisons(inputs, projections)
        distribution = build_distribution(
            inputs["entries"], projections, comparisons, condition, rule
        )
        from .controls import run_controls

        inputs["measurement_condition"] = condition
        controls = run_controls(inputs, rule, projections, comparisons)
        require(
            controls["all_expected_outcomes"]
            and controls["original_inputs_and_sidecars_unmodified"],
            "panel_quotient.direct_controls_failed",
        )
        after = history_inventory(root)
        require(after == frozen["history_inventory"], "panel_quotient.historical_bytes_changed")
        require(
            preserved_sources(root) == frozen["preserved_sources"],
            "panel_quotient.historical_source_changed",
        )
        guards = guard_report(counts, "measurement_and_four_direct_controls")
        report = record(
            "panel_quotient_report",
            stage=STAGE,
            condition_id=condition["id"],
            generation_condition_id=condition["generation_condition_id"],
            rule_id=rule["id"],
            implementation_id=frozen["implementation"]["id"],
            source_commit=frozen["implementation"]["source_commit"],
            preparation_manifest_id=manifest["id"],
            source_anchor_id=inputs["source_anchor"]["id"],
            original_panel_report_id=inputs["report"]["id"],
            original_registered_sessions=16,
            original_raw_submissions=152,
            original_qualified_sessions=15,
            original_qualified_submissions=120,
            original_qualified_admitted_submissions=113,
            original_qualified_unadmitted_submissions=7,
            original_supported_projections=12,
            mapped_qualified_sessions=sum(p["supported"] for p in projections),
            ineligible_labels=[p["label"] for p in projections if p["status"] == "ineligible"],
            unresolved_valid_labels=[
                p["label"] for p in projections if p["status"] == "undetermined"
            ],
            projection_ids=[p["id"] for p in projections],
            comparison_ids=[p["id"] for p in comparisons],
            pair_count=len(comparisons),
            new_pair_search_count=sum(p["new_isomorphism_search"] for p in comparisons),
            reused_old_pair_count=sum(
                p["derived_from_old_pair_id"] is not None for p in comparisons
            ),
            equivalent_pair_count=sum(p["equivalent"] is True for p in comparisons),
            event_interpretations=[
                {
                    "label": p["label"],
                    "old_supported": p["old_projection_supported"],
                    "new_status": p["status"],
                    "source_ledger_count": len(p["source_non_accept_ledger"]),
                    "rows": [
                        {
                            k: row[k]
                            for k in (
                                "sequence",
                                "disposition",
                                "nearest_admitted_successor_sequence",
                            )
                        }
                        for row in p["interpretation_ledger"]
                    ],
                    "retained_episode_count": len(p["behavior_projection"]["retained_interactions"])
                    if p["supported"]
                    else None,
                }
                for p in projections
            ],
            distribution=distribution,
            controls_id=controls["id"],
            direct_control_count=controls["control_count"],
            direct_control_family_count=controls["family_count"],
            all_direct_control_expected_outcomes=controls["all_expected_outcomes"],
            execution_guards=guards,
            complete_panel_quotient_measurement_closed=distribution[
                "complete_panel_quotient_measurement_closed"
            ],
            historical_bytes_preserved=True,
            history_inventory_id=after["id"],
            representation_references_id=inputs["representation_references"]["id"],
            original_113_candidate_and_token_records_byte_unchanged=True,
            original_15_complete_training_packages_byte_unchanged=True,
            new_token_arrays_or_training_weights_materialized=False,
            final_training_weights=None,
            no_independent_repeated_audit_stage=True,
            limitations=[
                "known development panel, not blinded",
                "one task instance per type and two registered sessions",
                "finite observed classes only",
                "S01 remains failed and unassigned",
                "S02 sum is executed but not consumed; final ratio uses disclosed Evidence",
                "no causal account of why feedback preceded choice",
                "no Contribution, Student utility or VTDO update",
            ],
        )
        store = DurableStore(measurement)
        for projection in projections:
            store.json("projections/" + projection["label"] + ".json", projection)
        for name, value in (
            ("comparisons", comparisons),
            ("assignments", distribution["assignments"]),
            ("classes", distribution["classes"]),
            ("distribution", distribution),
            ("controls", controls),
            ("execution_guards", guards),
            (
                "source_preservation",
                record(
                    "panel_quotient_preservation",
                    historical_inventory_before_id=after["id"],
                    historical_inventory_after_id=after["id"],
                    all_historical_bytes_unchanged=True,
                    source_anchor_id=inputs["source_anchor"]["id"],
                    predecessor_source_preservation_id=frozen["preserved_sources"]["id"],
                ),
            ),
            ("report", report),
        ):
            store.json(name + ".json", value)
        seal_directory(
            store,
            kind="panel_quotient_measurement_manifest",
            condition_id=condition["id"],
            report_id=report["id"],
        )
        return report
