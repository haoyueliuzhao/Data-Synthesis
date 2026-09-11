"""One source inventory with original-byte provenance; no task or model manufacture."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest

from .core import (
    OUTPUT,
    PACKAGE,
    Store,
    encode,
    history_guard,
    read_json,
    record,
    reference,
    require,
    sha,
)
from .examples import reviewed_examples
from .governance import ARCHIVE, annotated_governance, draft_company_split, known_exposure
from .protocol import preparation_protocol
from .screen import GROUPS, screen_public


def load_rows(root):
    directory = root / OUTPUT / "source_intake"
    manifest(directory)
    intake = read_json(directory / "report.json")
    require(
        intake["status"] == "SOURCE_BYTES_ACQUIRED_NOT_TASK_CERTIFIED", "census.exact_intake_state"
    )
    sources = []
    rows = []
    for split in ("train", "dev"):
        ref = reference(root, OUTPUT + f"/source_intake/finqa/{split}.json")
        original = read_json(root / ref["path"])
        sources.append({**ref, "source_split": split, "original_rows": len(original)})
        rows.extend(
            {
                **row,
                "source_split": split,
                "source_file_sha256": ref["sha256"],
                "source_record_index": index,
            }
            for index, row in enumerate(original)
        )
    require(len(rows) == len({row["id"] for row in rows}), "census.unique_original_question_ids")
    return rows, sources


def source_views(rows, draft):
    """Deduplicate page AND actual public view, never original question count."""
    assignments = {row["entry_id"]: row for row in draft["rows"]}
    grouped = defaultdict(list)
    for row in rows:
        public = {
            key: row.get(key) for key in ("filename", "table_ori", "table", "pre_text", "post_text")
        }
        grouped[(row["filename"], sha(encode(public)))].append(row)
    result = []
    for (page, view_hash), originals in sorted(grouped.items()):
        originals.sort(key=lambda row: (row["source_split"], row["source_record_index"], row["id"]))
        representative = originals[0]
        metadata = [assignments[row["id"]] for row in originals]
        require(len({row["draft_split"] for row in metadata}) == 1, "census.same_page_single_split")
        # Conservative at source-view level: one protected use excludes all its questions.
        training_excluded = any(row["training_source_excluded"] for row in metadata)
        evaluation_excluded = any(row["fresh_evaluation_source_excluded"] for row in metadata)
        split = metadata[0]["draft_split"]
        admitted_as_lead = not (training_excluded if split == "train" else evaluation_excluded)
        result.append(
            record(
                "basis_scale_source_view",
                page=page,
                public_view_sha256=view_hash,
                component_id=metadata[0]["component_id"],
                company_proxy=metadata[0]["company_proxy"],
                draft_split=split,
                original_question_ids=[row["id"] for row in originals],
                original_row_references=[
                    {
                        "original_id": row["id"],
                        "source_split": row["source_split"],
                        "source_file_sha256": row["source_file_sha256"],
                        "source_record_index": row["source_record_index"],
                    }
                    for row in originals
                ],
                training_source_excluded=training_excluded,
                fresh_evaluation_source_excluded=evaluation_excluded,
                admitted_as_draft_split_source_lead=admitted_as_lead,
                screening=screen_public(representative),
                physical_task_identity_or_sufficient_relation_certified=False,
            )
        )
    return result


def summarize_views(views):
    result = {}
    for split in ("train", "dev", "confirm"):
        all_rows = [row for row in views if row["draft_split"] == split]
        leads = [row for row in all_rows if row["admitted_as_draft_split_source_lead"]]
        grouped = {
            group: [row for row in leads if group in row["screening"]["groups"]] for group in GROUPS
        }
        result[split] = {
            "source_views": len(all_rows),
            "source_eligible_views": len(leads),
            "source_excluded_views": len(all_rows) - len(leads),
            "source_eligible_original_questions": sum(
                len(row["original_question_ids"]) for row in leads
            ),
            "source_company_proxy_count": len({row["company_proxy"] for row in leads}),
            "any_dual_group_screened_views": sum(bool(row["screening"]["groups"]) for row in leads),
            "screened_views_by_group": {group: len(items) for group, items in grouped.items()},
            "screened_company_proxies_by_group": {
                group: sorted({row["company_proxy"] for row in items})
                for group, items in grouped.items()
            },
            "screened_unique_table_hashes_by_group": {
                group: len(
                    {row["screening"]["source"]["authoritative_table_sha256"] for row in items}
                )
                for group, items in grouped.items()
            },
            "certified_distinct_tasks": 0,
            "no_lead_is_not_proof_of_absent_sufficient_relation": True,
            "one_source_view_may_support_multiple_distinct_quantities_only_after_review": True,
            "group_overlap_and_repeated_tables_prevent_adding_counts_as_task_quota": True,
        }
    return result


def run(root):
    root = Path(root)
    history_guard(root)
    rows, sources = load_rows(root)
    known = known_exposure(root)
    evaluation = read_json(root / ARCHIVE)
    governance = annotated_governance(rows, evaluation, known)
    draft = draft_company_split(rows, known, evaluation_rows=evaluation)
    views = source_views(rows, draft)
    from .entity import runtime

    entities = runtime(root, sorted({row["filename"].split("/")[0] for row in rows}))
    store = Store(root / OUTPUT / "source_census")
    protocol = preparation_protocol()
    store.json("protocol.json", protocol)
    store.json("source_references.json", sources)
    store.json("known_exposure.json", known)
    store.json("governance.json", governance)
    store.json("company_split_draft.json", draft)
    store.json("entity_evidence.json", entities)
    archived_entity_sources = []
    for ref in entities["source_references"]:
        raw = (root / ref["path"]).read_bytes()
        require(
            len(raw) == ref["bytes"] and sha(raw) == ref["sha256"],
            "census.original_entity_snapshot",
        )
        suffix = Path(ref["path"]).parts[-2:]
        destination = str(Path("entity_originals").joinpath(*suffix))
        store.write(destination, raw)
        archived_entity_sources.append({**ref, "archived_path": destination})
    store.json("entity_originals_index.json", archived_entity_sources)
    store.json("source_views.json", views)
    store.json("reviewed_source_examples.json", reviewed_examples(rows, draft))
    report = record(
        "basis_scale_source_census_report",
        status="SOURCE_TASK_READINESS_NOT_ESTABLISHED",
        reason="SOURCE_RELATION_AND_ISSUER_REVIEW_PENDING_NOT_A_GENERATION_FAILURE",
        original_question_records=len(rows),
        original_source_split_counts=dict(Counter(row["source_split"] for row in rows)),
        original_company_codes=len({row["filename"].split("/")[0] for row in rows}),
        original_reports=len({"/".join(row["filename"].split("/")[:2]) for row in rows}),
        original_pages=len({row["filename"] for row in rows}),
        distinct_page_public_views=len(views),
        original_table_hashes=len(
            {
                row["table_ori_sha256"]
                for row in governance["rows"]
                if row["table_ori_sha256"] is not None
            }
        ),
        governed_source_eligibility=governance["eligibility_counts"]["rows"],
        historical_strict_company_scenario=governance["strict_fresh_company_scenario_counts"][
            "rows"
        ],
        company_source_components=len(draft["components"]),
        split_rows=draft["split_row_counts"],
        source_screening_by_draft_split=summarize_views(views),
        source_views_with_dash_unknown=sum(bool(row["screening"]["dash_cells"]) for row in views),
        source_views_with_original_cleaned_differences=sum(
            bool(row["screening"]["table_comparison"]["differences"]) for row in views
        ),
        table_differences_include_case_and_formatting_not_all_numeric_errors=True,
        source_volume_does_not_establish_required_dual_tasks=True,
        source_screen_recall_not_measured_and_false_negatives_possible=True,
        numeric_supply_deficit_not_established_by_screen_counts_alone=True,
        source_inventory_scope=(
            "pinned official FinQA TRAIN and DEV only; not every public financial source"
        ),
        real_historical_company_identity_certified=False,
        task_supply_gate="NOT_ESTABLISHED",
        actual_new_certified_tasks=0,
        actual_common_ready_A_B_tasks=0,
        new_Teacher_sessions=0,
        new_semantic_API_requests=0,
        new_tokenizer_loads=0,
        new_Student_runs=0,
        new_optimizer_updates=0,
        new_generated_support_packages=0,
        new_effect_measurement=None,
        effect_not_measured_is_not_zero_effect=True,
        source_preparation_can_continue_without_relaxing_or_repeating_old_closed_studies=True,
        budget_protocol_id=protocol["id"],
        full_collection_protocol_frozen=False,
        support_generation_allowed=False,
        training_allowed=False,
    )
    store.json("report.json", report)
    store.json(
        "implementation_references.json",
        [
            reference(root, str(path.relative_to(root)))
            for path in sorted((root / PACKAGE).glob("*.py"))
        ],
    )
    store.json("history.json", history_guard(root))
    store.seal(report_id=report["id"])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(encode(run(args.root)).decode())


if __name__ == "__main__":
    main()
