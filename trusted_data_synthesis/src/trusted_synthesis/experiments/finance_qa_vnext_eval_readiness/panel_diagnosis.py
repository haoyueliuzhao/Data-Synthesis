"""Read-only, per-target reconstruction of the twelve archived compiler gaps."""

import json
from pathlib import Path

from ..finance_qa_vnext_task_build.archive import record, require, sha

OLD = "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/catalog_bridge_20260912/panels"


def table(directory, name):
    return [
        row
        for path in sorted((Path(directory) / "parents" / name).glob("*.json"))
        for row in json.loads(path.read_bytes())
    ]


def diagnose(root):
    directory = Path(root) / OLD / "confirm"
    targets = {
        row["task_id"]: row
        for row in json.loads((directory / "QA/target_bindings.json").read_bytes())
    }
    comp = {
        row["task_id"]: row
        for row in json.loads((directory / "QA/pattern_compilations.json").read_bytes())
    }
    facts = {row["fact_id"]: row for row in table(directory, "atomic_facts")}
    standardized = {row["fact_id"]: row for row in table(directory, "standardized_facts")}
    bindings = json.loads((directory / "native_bindings.json").read_bytes())
    candidates = {row["candidate_id"]: row for row in table(directory, "qa_candidates")}
    derived = [
        row
        for row in table(directory, "derived_facts")
        if row["derived_type"] in {"difference", "yoy_growth"}
    ]
    kg = json.loads((directory / "native_fact_build_report.json").read_bytes())["kg_build"]
    rejected = json.loads((directory / "QA_export_rejections.json").read_bytes())
    require(len(rejected) == 12, "readiness.expected_twelve_archived_gaps")
    cases = []
    for rejection in rejected:
        item = targets[rejection["task_id"]]
        identifiers = set(item["match"]["fact_ids"])
        compiler = comp[item["task_id"]]
        candidate = candidates.get(compiler.get("candidate_id"))
        adjacent_parents = [
            row for row in derived if identifiers.intersection(json.loads(row["input_fact_ids"]))
        ]
        related_ids = identifiers | {
            key for row in adjacent_parents for key in json.loads(row["input_fact_ids"])
        }
        exact = [
            row for row in adjacent_parents if set(json.loads(row["input_fact_ids"])) == identifiers
        ]
        cases.append(
            record(
                "archived_panel_gap_case",
                task_id=item["task_id"],
                original_rejection=rejection,
                canonical_target=item["target"],
                original_match=item["match"],
                original_compilation=compiler,
                original_kg_build=kg,
                exact_input_set_parents=exact,
                related_real_DerivedFact_rows=adjacent_parents,
                atomic_fact_rows=[facts[key] for key in sorted(related_ids)],
                standardized_fact_rows=[standardized[key] for key in sorted(related_ids)],
                original_native_bindings={key: bindings[key] for key in sorted(related_ids)},
                candidate_constraint_inputs=None
                if candidate is None
                else {
                    key: candidate[key]
                    for key in (
                        "candidate_id",
                        "qa_build_id",
                        "source_fact_ids",
                        "source_derived_ids",
                        "time_scope",
                        "eligibility_status",
                        "rejection_reasons",
                        "answer_payload",
                        "operation_plan_id",
                        "pattern_id",
                        "pattern_hash",
                    )
                },
                finding=(
                    "end_year_index_collapses_or_skips_actual_annual_periods_in_derived_builder"
                    if candidate is None
                    else "year_index_contiguity_or_coverage_disagrees_with_actual_intervals"
                ),
                missing_original_source_evidence=False,
                implementation_repair_requires_new_actual_parent_build=True,
                equal_value_parent_substitution_allowed=False,
            )
        )
    return record(
        "archived_panel_gap_diagnosis",
        cases=cases,
        case_count=len(cases),
        original_rejections_path=str((directory / "QA_export_rejections.json").relative_to(root)),
        original_rejections_sha256=sha(directory / "QA_export_rejections.json"),
        source_cluster_count=len({row["canonical_target"]["source_cluster"] for row in cases}),
        original_artifacts_modified=False,
        task_outputs_rebuilt=False,
    )
