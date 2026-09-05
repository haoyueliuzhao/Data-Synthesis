"""The versioned Finance QA entry: one Catalog, Registry, callback protocol and Runtime."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from trusted_synthesis.core.task.program_depth import derive_program_depth_metrics

from .callbacks import PublicFixtureCallback
from .catalog import FinanceQACatalog, catalog_operation_registry
from .measurement import audit_session, compare_sessions
from .program_adapter import ProgramTaskAdapter
from .protocol import contract, record, require
from .runtime import Callback, DurableStore, PublicQARuntime, TaskAdapter
from .share_adapter import (
    SHARE_FAMILY,
    SHARE_OPERATIONS,
    ShareTaskAdapter,
    add_share_operations,
    load_share_source,
)

ENTRY_VERSION = "finance_qa_vnext_entry.v2"


def build_catalog(repo_root: Path) -> FinanceQACatalog:
    registry = catalog_operation_registry()
    add_share_operations(registry)
    catalog = FinanceQACatalog(registry)
    _, legacy, _ = load_share_source(repo_root)
    catalog.register_adapter_family(
        SHARE_FAMILY,
        adapter_id="source_explicit_share_obligations.v2",
        required_operations=SHARE_OPERATIONS,
        contract_id=legacy["id"],
    )
    return catalog


def run_finance_qa_vnext(
    repo_root: Path,
    output_directory: Path,
    *,
    task_types: tuple[str, ...] | None = None,
    callback_factory: Callable[[dict[str, Any]], Callback] | None = None,
) -> dict[str, Any]:
    """Materialize bound tasks through v2, or explicitly retain uninstantiated rows.

    The default is a deterministic integration regression over existing sources,
    not a Provider/model study. Supplying an external callback does not authorize
    or assert any verified model-origin classification.
    """
    require(not output_directory.exists(), "entry.immutable_output")
    root = repo_root.resolve()
    catalog = build_catalog(root)
    requested = catalog.task_types if task_types is None else task_types
    require(bool(requested) and len(requested) == len(set(requested)), "entry.task_selection")
    for task_type in requested:
        catalog.resolve(task_type)
    pattern_types = tuple(name for name in requested if name != SHARE_FAMILY)
    cases, coverage = (
        catalog.frozen_source_cases(root, task_types=pattern_types) if pattern_types else ((), ())
    )
    include_share = task_types is None or SHARE_FAMILY in task_types
    store = DurableStore(output_directory)
    store.json("catalog.json", catalog.descriptor)
    store.json("protocol.json", contract())
    store.json(
        "entry.json",
        record(
            "entry",
            version=ENTRY_VERSION,
            requested_task_types=list(requested),
            default_requests_all_registered_families=True,
            fixture_default=True,
            retrospective_candidate_generator_used=False,
            accepted_claim_revision_supported=False,
            production_or_training_release=False,
        ),
    )
    audits: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    by_case = {row["case_id"]: row for row in coverage if row["compiled"]}

    def run_case(
        case_id: str,
        adapter: TaskAdapter,
        callback: Callback,
        source_row: dict[str, Any],
        program_metrics: dict[str, Any] | None,
    ) -> None:
        session = PublicQARuntime(adapter, callback, output_directory / "sessions" / case_id).run()
        audited = audit_session(adapter, session, output_directory / "sessions" / case_id)
        store.json("validations/" + case_id + ".json", audited)
        audits.append(audited)
        result_rows.append(
            record(
                "coverage",
                case_id=case_id,
                task_type=adapter.context["task_type"],
                registered=source_row["registered"],
                source_bindable=source_row["source_bindable"],
                source_binding_id=source_row["source_binding_id"],
                compilation_status=source_row["compilation_status"],
                compiled=source_row["compiled"],
                context_id=adapter.context["id"],
                task_id=adapter.context["task_id"],
                catalog_id=catalog.descriptor["id"],
                registry_hash=session["registry_hash"],
                session_id=session["id"],
                validation_id=audited["id"],
                new_protocol_executable=any("execution" in event for event in session["events"]),
                qa_valid=audited["qa_valid"],
                trajectory_valid=audited["trajectory_valid"],
                qualified=audited["qualified"],
                origin=callback.binding["origin"],
                model_executed=False,
                program_depth_metrics=program_metrics,
                actual_decision_graph_id=(audited["actual_decision_graph"] or {}).get("id"),
                actual_depth_metrics=audited["depth_metrics"],
                columns_from_one_case_only=True,
                previous_experiment_columns_substituted=False,
            )
        )

    for case in cases:
        catalog.admit_case(case)
        adapter = ProgramTaskAdapter(case, catalog.registry)
        callback = (
            callback_factory(adapter.context) if callback_factory else PublicFixtureCallback()
        )
        metrics = derive_program_depth_metrics(
            case.instantiation.program, catalog.registry
        ).model_dump(mode="json")
        run_case(case.case_id, adapter, callback, by_case[case.case_id], metrics)
    if include_share:
        resolution = catalog.resolve(SHARE_FAMILY).receipt
        for preference in (
            ("external",) if callback_factory else ("disclosed_total", "reconstructed_total")
        ):
            share = ShareTaskAdapter(root, catalog.registry, resolution)
            callback = (
                callback_factory(share.context)
                if callback_factory
                else PublicFixtureCallback(support_preference=preference)
            )
            run_case(
                "share_" + preference,
                share,
                callback,
                {
                    "registered": True,
                    "source_bindable": True,
                    "source_binding_id": share.binding["id"],
                    "compiled": True,
                    "compilation_status": "adapter_materialized_not_TaskPattern_compiled",
                },
                None,
            )
    uninstantiated = [row for row in coverage if not row["compiled"]]
    comparisons = []
    for index, left in enumerate(audits):
        for right in audits[index + 1 :]:
            if left["context_id"] == right["context_id"]:
                comparisons.append(compare_sessions(left, right))
    report = record(
        "entry_report",
        entry_version=ENTRY_VERSION,
        catalog_id=catalog.descriptor["id"],
        registered_task_types=list(catalog.task_types),
        requested_task_types=list(requested),
        coverage_rows=result_rows,
        uninstantiated_rows=uninstantiated,
        executed_case_count=len(result_rows),
        qualified_case_count=sum(row["qualified"] for row in result_rows),
        all_instantiated_cases_passed=bool(result_rows)
        and all(row["qualified"] for row in result_rows),
        uninstantiated_task_types=[row["task_type"] for row in uninstantiated],
        same_task_comparisons=comparisons,
        source_scope="existing frozen sources only",
        fixture_regression=callback_factory is None,
        provider_calls=0 if callback_factory is None else None,
        new_verified_model_samples=0,
        GPU_jobs=0,
        Student_parameter_updates=0,
        new_protocol_model_coverage_claimed=False,
        all_registered_families_have_source_claimed=False,
        accepted_claim_revision_supported=False,
        uncertainty_resolution_beyond_empty_current_cases_claimed=False,
        arbitrary_QA_or_universal_mapper_claimed=False,
        production_or_training_release=False,
        older_share_assignments_and_empirical_probabilities_modified=False,
        old_training_mainline="remains_paused",
    )
    store.json("report.json", report)
    members = []
    for path in sorted(output_directory.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            members.append(
                {
                    "path": path.relative_to(output_directory).as_posix(),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            )
    store.json(
        "manifest.json",
        record(
            "entry_manifest",
            entry_report_id=report["id"],
            members=members,
            self_excluding=True,
            covers_all_session_manifests_and_raw_submissions=True,
        ),
    )
    return report
