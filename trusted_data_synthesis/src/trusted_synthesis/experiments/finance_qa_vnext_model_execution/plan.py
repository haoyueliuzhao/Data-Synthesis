"""Freeze the three-task, twelve-session population before any Provider attempt."""

from __future__ import annotations

import io
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.catalog import CatalogCase, FinanceQACatalog
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.runner import build_catalog
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore, TaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import SHARE_FAMILY, ShareTaskAdapter

from .models import PARENT_COMMIT, STAGE, TASK_GROUPS, identity, read_json, record, require, sha

DESIGN_BYTES = 27_149
DESIGN_SHA256 = "b6fdec3498d77da346dd1c4dc4891fee8665ef14ea439cfcecd7ee1800174593"
BASELINE_ENTRY = (
    "trusted_data_synthesis/artifacts/qa_vnext_integration/"
    "finance_qa_vnext_unified_entry_v2_20260906/entry"
)


@dataclass
class TaskPanel:
    root: Path
    catalog: FinanceQACatalog
    cases: dict[str, CatalogCase]
    coverage: list[dict[str, Any]]

    def adapter(self, group: str) -> TaskAdapter:
        require(group in TASK_GROUPS, "panel.group")
        if group == "S":
            return ShareTaskAdapter(
                self.root, self.catalog.registry, self.catalog.resolve(SHARE_FAMILY).receipt
            )
        case = self.cases[group]
        self.catalog.admit_case(case)
        return ProgramTaskAdapter(case, self.catalog.registry)


def load_panel(root: Path) -> TaskPanel:
    root = root.resolve()
    catalog = build_catalog(root)
    cases, source_rows = catalog.frozen_source_cases(root)
    by_type = {case.task_type: case for case in cases}
    require(
        by_type[TASK_GROUPS["B"]].case_id == "branch_cdw_fy2015_fy2016",
        "panel.fixed_branch",
    )
    selected = {group: by_type[TASK_GROUPS[group]] for group in ("C", "B")}
    # Check the exact three previously source-bound contexts, not old model outcomes.
    baseline = read_json((root / BASELINE_ENTRY / "report.json").read_bytes())
    require(
        strict_canonical_hash(
            {key: value for key, value in baseline.items() if key != "id"},
            prefix="finance_qa_vnext_entry_report:",
        )
        == baseline["id"],
        "panel.baseline_report_identity",
    )
    require(
        baseline["id"] == "finance_qa_vnext_entry_report:"
        "e0c20b27fbc35fb981f90141c0f0a93e07ec675e9715d13c6a04ad6d805ad7c6",
        "panel.baseline_report",
    )
    panel = TaskPanel(root, catalog, selected, [])
    for group in TASK_GROUPS:
        adapter = panel.adapter(group)
        original = [
            row for row in baseline["coverage_rows"] if row["task_type"] == TASK_GROUPS[group]
        ]
        require(
            bool(original)
            and all(
                row["context_id"] == adapter.context["id"]
                and row["task_id"] == adapter.context["task_id"]
                for row in original
            ),
            "panel.fixed_source_context",
        )
    status_by_type = {row["task_type"]: row for row in source_rows}
    for task_type in catalog.task_types:
        source_available = (
            True if task_type == SHARE_FAMILY else status_by_type[task_type]["source_bindable"]
        )
        selected_group = next((g for g, task in TASK_GROUPS.items() if task == task_type), None)
        panel.coverage.append(
            record(
                "population_coverage",
                task_type=task_type,
                registered=True,
                source_available=source_available,
                selected_for_model_population=selected_group is not None,
                task_group=selected_group,
                population_status=(
                    "selected_model_task"
                    if selected_group
                    else "source_available_not_selected"
                    if source_available
                    else "source_unavailable"
                ),
                registered_model_sessions=4 if selected_group else 0,
                old_fixture_success_is_model_coverage=False,
            )
        )
    return panel


def source_snapshot(root: Path) -> dict[str, Any]:
    """Check all Python sources against one Git commit, without extracting an archive."""
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    archive = subprocess.check_output(
        ["git", "archive", commit + ":trusted_data_synthesis/src"], cwd=root
    )
    members = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as stream:
        for item in stream.getmembers():
            if not item.isfile() or not item.name.endswith(".py"):
                continue
            handle = stream.extractfile(item)
            assert handle is not None
            frozen = handle.read()
            relative = "trusted_data_synthesis/src/" + item.name
            require((root / relative).read_bytes() == frozen, "plan.source_not_committed")
            members.append({"path": relative, "sha256": sha(frozen), "bytes": len(frozen)})
    require(
        {item["path"] for item in members}
        == {
            path.relative_to(root).as_posix()
            for path in (root / "trusted_data_synthesis/src").rglob("*.py")
        },
        "plan.uncommitted_source_members",
    )
    return record(
        "implementation",
        source_commit=commit,
        source_tree=tree,
        members=sorted(members, key=lambda item: item["path"]),
        every_python_source_bound=True,
    )


def verify_source_snapshot(root: Path, implementation: dict[str, Any]) -> None:
    identity(implementation, "implementation")
    for member in implementation["members"]:
        path = root / member["path"]
        require(path.resolve().is_relative_to(root.resolve()), "plan.source_path")
        data = path.read_bytes()
        require(
            len(data) == member["bytes"] and sha(data) == member["sha256"],
            "plan.source_changed_after_freeze",
        )
    require(
        {item["path"] for item in implementation["members"]}
        == {
            path.relative_to(root).as_posix()
            for path in (root / "trusted_data_synthesis/src").rglob("*.py")
        },
        "plan.source_member_set_changed",
    )


def freeze_condition(
    root: Path, config: dict[str, Any], implementation: dict[str, Any], *, run_tag: str
) -> tuple[dict[str, Any], list[dict[str, Any]], TaskPanel]:
    from .transport import TransportConfig

    identity(implementation, "implementation")
    identity(config, "transport_config")
    require(config == TransportConfig().as_record(), "plan.fixed_generation_configuration")
    panel = load_panel(root)
    require(bool(run_tag) and "/" not in run_tag, "plan.run_tag")
    condition = record(
        "condition",
        stage=STAGE,
        run_tag=run_tag,
        predecessor_commit=PARENT_COMMIT,
        design_sha256=DESIGN_SHA256,
        design_byte_count=DESIGN_BYTES,
        current_user_directive="参照实验设计方案进行后续实验",
        current_directive_authorizes_the_proposed_online_stage=True,
        implementation_id=implementation["id"],
        model_configuration_id=config["id"],
        catalog_id=panel.catalog.descriptor["id"],
        protocol_id=contract()["id"],
        task_contexts={group: panel.adapter(group).context for group in TASK_GROUPS},
        given_plan_and_legal_candidates=True,
        autonomous_planning=False,
        private_reasoning_requested=False,
        share_route_preassignment=None,
        session_count=12,
        sessions_per_task=4,
        rounds=4,
        round_launch_order=["C", "B", "S"],
        maximum_parallel_sessions=3,
        next_round_waits_for_current_round=True,
        outcome_adaptive_reordering=False,
        automatic_network_retries=0,
        model_fallbacks=0,
        session_replacements=0,
        maximum_actions_per_session=12,
        maximum_submissions_per_session=32,
        maximum_provider_attempts_per_session=32,
        maximum_provider_attempts=384,
        input_admission_allowance=99_328,
        output_token_limit=8192,
        maximum_reserved_token_allowance=41_287_680,
        input_allowance_is_exact_provider_token_count=False,
        actual_usage_authority="observed Provider usage; missing usage remains unknown",
        missing_or_unstarted_sessions_are_not_failures=True,
        unknown_and_not_started_have_null_success_indicator=True,
        valid_final_stops_immediately=True,
        malformed_public_response_is_a_new_submission_not_a_network_retry=True,
        halt_future_rounds_on_integrity_or_internal_execution_failure=True,
        already_started_sessions_remain_in_the_registered_population=True,
        maximum_same_task_comparison_pairs=18,
        new_quotient_assignments_materialized=False,
        old_state_ids_or_P_Q_weights_reused=False,
        student_parameter_loads=0,
        student_forward_calls=0,
        student_updates=0,
        gpu_jobs=0,
        old_mainline="remains_paused",
    )
    registrations: list[dict[str, Any]] = []
    for round_index in range(4):
        for group in ("C", "B", "S"):
            adapter = panel.adapter(group)
            session_id = strict_canonical_hash(
                {"condition_id": condition["id"], "group": group, "round": round_index + 1},
                prefix="qa_vnext_online_session:",
            )
            registrations.append(
                record(
                    "session_registration",
                    session_id=session_id,
                    label=f"{group}{round_index + 1:02d}",
                    ordinal=len(registrations),
                    round=round_index + 1,
                    task_group=group,
                    task_type=TASK_GROUPS[group],
                    task_id=adapter.context["task_id"],
                    context_id=adapter.context["id"],
                    protocol_id=contract()["id"],
                    registry_hash=strict_canonical_hash(panel.catalog.registry.manifest()),
                    model_configuration_id=config["id"],
                    run_condition_id=condition["id"],
                    maximum_actions=12,
                    maximum_submissions=32,
                    maximum_provider_attempts=32,
                    replacement_allowed=False,
                    reference_route=None,
                    independent_initial_state=True,
                    reads_other_session_responses=False,
                )
            )
    require(len(registrations) == 12, "plan.complete_population")
    return condition, registrations, panel


def seal_directory(store: DurableStore, *, kind: str, **binding: Any) -> dict[str, Any]:
    members = []
    for path in sorted(store.root.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            members.append(
                {
                    "path": path.relative_to(store.root).as_posix(),
                    "sha256": sha(data),
                    "bytes": len(data),
                }
            )
    manifest = record(kind, **binding, members=members, self_excluding=True)
    store.json("manifest.json", manifest)
    return manifest


def verify_directory(directory: Path, *, kind: str) -> dict[str, Any]:
    require(not directory.is_symlink(), "manifest.root_symlink")
    require(not (directory / "manifest.json").is_symlink(), "manifest.manifest_symlink")
    manifest = read_json((directory / "manifest.json").read_bytes())
    identity(manifest, kind)
    require(manifest.get("self_excluding") is True, "manifest.self_excluding")
    expected = {item["path"]: item for item in manifest["members"]}
    require(len(expected) == len(manifest["members"]), "manifest.duplicate_path")
    actual = {
        path.relative_to(directory).as_posix(): path
        for path in directory.rglob("*")
        if path.is_file() and path != directory / "manifest.json"
    }
    require(set(actual) == set(expected), "manifest.complete_members")
    for name, path in actual.items():
        require(
            not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()),
            "manifest.symlink",
        )
        raw = path.read_bytes()
        require(
            len(raw) == expected[name]["bytes"] and sha(raw) == expected[name]["sha256"],
            "manifest.member_bytes",
        )
    require(
        (directory / "manifest.json").read_bytes() == canonical_json_bytes(manifest),
        "manifest.canonical",
    )
    return manifest
