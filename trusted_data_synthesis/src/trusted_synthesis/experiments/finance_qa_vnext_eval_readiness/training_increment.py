"""Bounded UNP source increment through actual Fact, quality, KG, QA and rewrite."""

import copy
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from finraw.qa import pipeline

from ..finance_qa_vnext_catalog_bridge.catalog import read, safe_path
from ..finance_qa_vnext_catalog_bridge.protocol import qa_config
from ..finance_qa_vnext_catalog_bridge.stage import seal
from ..finance_qa_vnext_surface_build.stage import make_surface, realization_stats
from ..finance_qa_vnext_surface_build.transport import Provider
from ..finance_qa_vnext_task_build import factory, issuer_tables, native_facts
from ..finance_qa_vnext_task_build.archive import RecordDB, record, require, write_json
from ..finance_qa_vnext_task_build.protocol import policy as original_source_policy
from . import source_policy


def append_qualified_sources(cached, results):
    """Copy frozen admissions verbatim; choose new vintages once by source metadata."""
    issuer = copy.deepcopy(cached)
    require(
        not any(row["entity_id"] == source_policy.ENTITY for row in issuer["observations"]),
        "increment.no_prior_UNP_period_to_replace",
    )
    grouped = defaultdict(list)
    for result in results:
        for observation in result["observations"]:
            require(
                observation["entity_id"] == source_policy.ENTITY
                and observation["source_cluster"] == source_policy.CIK,
                "increment.only_UNP_new_observations",
            )
            grouped[observation["period_start"], observation["period_end"]].append(observation)
    chosen, omitted = [], []
    for key in sorted(grouped):
        versions = sorted(
            grouped[key], key=lambda row: (row["filing_date"], row["document_id"], row["table_id"])
        )
        chosen.append(versions[-1])
        omitted.extend(
            {
                "table_id": row["table_id"],
                "period_end": row["period_end"],
                "status": "OLDER_REPORTED_VINTAGE_NOT_A_NEW_TARGET",
            }
            for row in versions[:-1]
        )
    issuer["tables"].extend(table for result in results for table in result["tables"])
    issuer["observations"].extend(chosen)
    issuer["failures"].extend(failure for result in results for failure in result["failures"])
    issuer["older_vintage_exclusions"].extend(omitted)
    issuer["counts"] = {
        "documents": len(issuer["sources"]),
        "tables": len(issuer["tables"]),
        "selected_periods": len(issuer["observations"]),
        "source_clusters": len({row["source_cluster"] for row in issuer["observations"]}),
    }
    issuer["incremental_source_admission"] = {
        "old_cache_reused_without_reparsing": True,
        "new_source_results": results,
        "new_selected_periods": len(chosen),
        "fixed_source_count": len(results),
        "latest_qualified_vintage_selected_once": True,
    }
    return issuer


def prepared_context(root, archived, frozen_metadata):
    del archived  # Only the shared builder itself reads archived ontology/registry.
    source_policy.validate_metadata(root, frozen_metadata)
    parent = source_policy.cache_parent(root)
    inputs = source_policy.cached_inputs(root, parent)
    cached = parent.read("issuer_source_tables.json")
    unp = next(item for item in inputs if item["entity"]["entity_id"] == source_policy.ENTITY)

    def parse(source):
        try:
            return issuer_tables.parse_document(root, source, unp["observations"])
        except (OSError, ValueError) as error:
            return {
                "source": source,
                "tables": [],
                "observations": [],
                "failures": [
                    {
                        "document_id": source["document"]["document_id"],
                        "entity_id": source_policy.ENTITY,
                        "status": "ISSUER_SOURCE_UNAVAILABLE_OR_UNVERIFIABLE",
                        "reason": str(error),
                    }
                ],
            }

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(parse, frozen_metadata["selected_sources"]))
    return inputs, append_qualified_sources(cached, results)


def select_new_tasks(selected, old_ids):
    candidates = selected.get("company_defined_metric", [])
    require(
        all(
            row["family"] == "company_defined_metric"
            and row["target"]["source_cluster"] == source_policy.CIK
            for row in candidates
        ),
        "increment.only_UNP_company_tasks",
    )
    require(
        not any(selected.get(group) for group in ("stock_rollforward", "annual_flow", "control")),
        "increment.no_other_family_reenumeration",
    )
    new = [row for row in candidates if row["task_id"] not in old_ids]
    require(len({row["task_id"] for row in new}) == len(new), "increment.unique_new_tasks")
    return new[: source_policy.MAX_NEW_TASKS], new[source_policy.MAX_NEW_TASKS :]


def check_ledger(ledger, frozen):
    snapshot = ledger.snapshot()
    policy = snapshot["policy"]
    require(
        policy["stage_id"] == frozen["id"]
        and policy["request_cap"] == source_policy.REQUEST_CAP
        and policy["token_cap"] == source_policy.TOKEN_CAP
        and policy["per_task_cap"] == 2,
        "increment.preallocated_34_request_330752_token_ledger",
    )
    require(
        snapshot["previous_registered_debit"] >= 221538,
        "increment.shared_prior_debit_must_not_reset",
    )
    require(snapshot["request_reservations"] == 0, "increment.no_requests_before_new_registry")


def run(root, output, work, frozen, ledger, key):
    root, output = Path(root).resolve(), Path(output)
    if not output.is_absolute():
        output = root / output
    require(output.is_relative_to(root), "increment.output_containment")
    output = safe_path(root, output.relative_to(root))
    work = safe_path(root, work).relative_to(root)
    require(output != root and not output.exists(), "increment.one_new_output_directory")
    require(bool(key), "increment.rewrite_credential_preflight")
    metadata = frozen["training_source_metadata"]
    source_policy.validate_metadata(root, metadata)
    check_ledger(ledger, frozen)
    old_ids = set(metadata["old_task_ids"])
    require(len(old_ids) == 243, "increment.preserve_exact_243_old_tasks")
    write_json(
        output / "stage_freeze.json",
        record(
            "incremental_task_freeze",
            git_commit=frozen["git_commit"],
            stage_freeze_id=frozen["id"],
            rule={
                "source_split": original_source_policy()["source_split"],
                "source_extension": source_policy.policy(),
            },
            input_freeze=metadata,
            cache_parent=metadata["cache_parent"],
            previous_catalog_parent=metadata["catalog_parent"],
        ),
    )
    native = native_facts.run(
        root,
        output,
        work=str(work),
        prepared_context=lambda root, archive: prepared_context(root, archive, metadata),
    )
    db = RecordDB(str(root / work / "native_fact_qa.sqlite3"))
    try:
        kg = native["kg_build"]
        bindings = read(output / "native_bindings.json")
        facts = pipeline._load_facts_by_id(
            db, list(bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
        )
        usage = {
            key: {field: row[field] for field in ("split", "allowed_uses", "source_cluster")}
            for key, row in bindings.items()
        }
        write_json(output / "all_leaf_usage.json", usage)
        # Old tables are never reparsed or run through validate_binding here.
        unp = {
            key: row
            for key, row in facts.items()
            if row["entity_id"] == source_policy.ENTITY
            and bindings[key].get("source_kind") == "issuer_report_table"
        }
        selected, failures, enumeration = factory.enumerate_bindings(unp, bindings, usage)
        new, overflow = select_new_tasks(selected, old_ids)
        write_json(output / "binding_failures.json", failures)
        write_json(
            output / "binding_enumeration.json",
            {**enumeration, "scope": "new_UNP_issuer_only", "new_cap_overflow": overflow},
        )
        registry = record(
            "incremental_target_registry",
            stage_freeze_id=frozen["id"],
            tasks=[
                {key: value for key, value in row.items() if key != "certificate"} for row in new
            ],
            omitted_beyond_remaining_cap=[row["task_id"] for row in overflow],
            old_ids_rewritten=[],
            registered_before_rewrite=True,
        )
        write_json(output / "canonical_task_registry.json", registry)
        ledger.register([row["task_id"] for row in new], old_ids)
        write_json(output / "budget_initial.json", ledger.snapshot())
        exported, rejected, validation = [], [], None
        if new:
            build, candidates, plans, compilations, validation = factory.compile_batch(
                db,
                kg,
                new,
                facts,
                bindings,
                output,
                "new_tasks",
                config=qa_config(),
                provider_factory=lambda task: Provider(task, ledger, output, key),
            )
            lookup = {row["candidate_id"]: row for row in candidates}
            exported, rejected = factory.export_batch(
                db,
                kg,
                build,
                new,
                candidates,
                plans,
                compilations,
                facts,
                bindings,
                usage,
                output,
                surface_context=lambda item, sample, public: make_surface(
                    item, sample, public, lookup[sample["candidate_id"]], frozen["id"]
                ),
            )
        else:
            pipeline.ensure_qa_schema(db)
            write_json(output / "new_tasks/pattern_compilations.json", [])
        # No replacement candidates or source retries after observing QA/rewrite.
        write_json(output / "qa_validation_rejections.json", rejected)
        write_json(
            output / "catalog.json",
            record(
                "fixed_task_catalog",
                tasks=exported,
                parent_manifest_id=metadata["cache_parent"]["manifest_id"],
                final_training_population_selected=False,
            ),
        )
        tables = factory.dump_parents(db, output)
        stats = realization_stats(exported, output, ledger)
        report = record(
            "incremental_task_report",
            tasks=len(exported),
            registered_targets=len(new),
            rewrite=stats,
            actual_parents=tables,
            QA_validation=validation,
            all_registered_tasks_retained=not rejected and len(exported) == len(new),
            old_task_count_preserved=243,
            old_task_rewrite_requests=0,
            new_task_ids=[row["task_id"] for row in exported],
            binding_rejection_count=len(failures),
            source_metadata_id=metadata["id"],
            source_extension_rule_id=source_policy.policy()["id"],
            actual_Teacher_sessions=0,
            actual_Student_runs=0,
            source_or_task_refill_after_outcomes=False,
        )
        write_json(output / "rewrite_budget_ledger.json", ledger.snapshot())
        write_json(output / "report.json", report)
        seal(output, scope="new UNP tasks; cached original inputs; real Fact/quality/KG/QA parents")
        return report
    finally:
        db.close()
