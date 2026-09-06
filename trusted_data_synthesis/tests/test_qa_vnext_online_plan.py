"""Zero-call population and source-freeze controls; no experiment is launched here."""

from __future__ import annotations

import copy
import io
import json
import socket
import tarfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext import catalog as domain
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, contract
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import plan
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    PARENT_COMMIT,
    STAGE,
    TASK_GROUPS,
    identity,
    record,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import TransportConfig

ROOT = Path(__file__).resolve().parents[2]


def reseal(value: dict[str, Any], kind: str, **changes: Any) -> dict[str, Any]:
    body = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return record(kind, **{**body, **changes})


@pytest.fixture(autouse=True)
def no_online_work(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("population/source-freeze tests must not make network calls")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(scope="module", autouse=True)
def old_baseline_and_source_files_are_not_rewritten() -> Iterator[None]:
    paths = [
        ROOT / plan.BASELINE_ENTRY / "report.json",
        ROOT / plan.BASELINE_ENTRY / "manifest.json",
        ROOT / domain.ARCHIVE_PATH,
    ]
    paths.extend(
        (ROOT / domain.FROZEN_SOURCE_DIRECTORY / name) for name, _, _ in domain.SOURCE_MEMBERS
    )
    before = {path: sha(path.read_bytes()) for path in paths}
    yield
    assert {path: sha(path.read_bytes()) for path in paths} == before


@pytest.fixture(scope="module")
def panel() -> plan.TaskPanel:
    return plan.load_panel(ROOT)


@pytest.fixture
def implementation() -> dict[str, Any]:
    # Condition tests inspect ID propagation only. Actual file-byte verification
    # is separately exercised below with a complete controlled source archive.
    return record(
        "implementation",
        source_commit="a" * 40,
        source_tree="b" * 40,
        members=[],
        every_python_source_bound=True,
        constructed_condition_binding_control_only=True,
    )


def freeze(
    panel: plan.TaskPanel,
    implementation: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    *,
    run_tag: str = "test-fixed-plan",
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], plan.TaskPanel]:
    monkeypatch.setattr(plan, "load_panel", lambda root: panel)
    return plan.freeze_condition(
        ROOT, config or TransportConfig().as_record(), implementation, run_tag=run_tag
    )


def test_panel_is_three_exact_existing_contexts_with_three_five_three_coverage(
    panel: plan.TaskPanel,
) -> None:
    assert set(panel.cases) == {"C", "B"}
    assert panel.cases["B"].case_id == "branch_cdw_fy2015_fy2016"
    assert panel.cases["C"].task_type == "registered_cross_metric_comparison"
    baseline = json.loads((ROOT / plan.BASELINE_ENTRY / "report.json").read_bytes())
    for group, task_type in TASK_GROUPS.items():
        first, second = panel.adapter(group), panel.adapter(group)
        assert first is not second
        assert first.registry is second.registry is panel.catalog.registry
        assert first.context == second.context
        assert first.context["task_type"] == task_type
        old_rows = [row for row in baseline["coverage_rows"] if row["task_type"] == task_type]
        assert old_rows
        assert all(
            row["context_id"] == first.context["id"] and row["task_id"] == first.context["task_id"]
            for row in old_rows
        )
        assert first.context["source_binding"]["source_bindable"] is True
    rows = panel.coverage
    assert len(rows) == 11
    assert len({row["task_type"] for row in rows}) == 11
    assert Counter(row["population_status"] for row in rows) == {
        "selected_model_task": 3,
        "source_available_not_selected": 5,
        "source_unavailable": 3,
    }
    for row in rows:
        identity(row, "population_coverage")
        assert row["registered"] is True
        assert row["selected_for_model_population"] is (row["task_type"] in TASK_GROUPS.values())
        assert row["registered_model_sessions"] == (
            4 if row["selected_for_model_population"] else 0
        )
        assert row["old_fixture_success_is_model_coverage"] is False
        if row["population_status"] == "source_available_not_selected":
            assert row["source_available"] is True and row["task_group"] is None
        elif row["population_status"] == "source_unavailable":
            assert row["source_available"] is False and row["task_group"] is None


@pytest.mark.parametrize("group", ["", "D", "S01"])
def test_panel_does_not_invent_an_extra_task_group(panel: plan.TaskPanel, group: str) -> None:
    with pytest.raises(ProtocolError, match="panel.group"):
        panel.adapter(group)


def test_condition_preregisters_twelve_sessions_in_four_fixed_cbs_rounds(
    panel: plan.TaskPanel, implementation: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    condition, registrations, actual_panel = freeze(panel, implementation, monkeypatch)
    assert actual_panel is panel
    identity(condition, "condition")
    assert condition["stage"] == STAGE
    assert condition["predecessor_commit"] == PARENT_COMMIT
    assert (
        condition["design_sha256"]
        == "b6fdec3498d77da346dd1c4dc4891fee8665ef14ea439cfcecd7ee1800174593"
    )
    assert condition["design_byte_count"] == 27_149
    assert condition["implementation_id"] == implementation["id"]
    assert condition["model_configuration_id"] == TransportConfig().as_record()["id"]
    assert condition["catalog_id"] == panel.catalog.descriptor["id"]
    assert condition["protocol_id"] == contract()["id"]
    assert condition["session_count"] == len(registrations) == 12
    assert condition["sessions_per_task"] == condition["rounds"] == 4
    assert condition["round_launch_order"] == ["C", "B", "S"]
    assert [item["label"] for item in registrations] == [
        f"{group}{round_index:02d}" for round_index in range(1, 5) for group in ("C", "B", "S")
    ]
    assert [item["ordinal"] for item in registrations] == list(range(12))
    assert (
        len({item["id"] for item in registrations})
        == len({item["session_id"] for item in registrations})
        == 12
    )
    assert (
        len({item["context_id"] for item in registrations})
        == len({item["task_id"] for item in registrations})
        == 3
    )
    assert Counter(item["task_group"] for item in registrations) == {"C": 4, "B": 4, "S": 4}
    for item in registrations:
        identity(item, "session_registration")
        context = condition["task_contexts"][item["task_group"]]
        assert context == panel.adapter(item["task_group"]).context
        assert item["context_id"] == context["id"]
        assert item["task_id"] == context["task_id"]
        assert item["task_type"] == TASK_GROUPS[item["task_group"]]
        assert item["run_condition_id"] == condition["id"]
        assert item["model_configuration_id"] == condition["model_configuration_id"]
        assert item["registry_hash"] == strict_canonical_hash(panel.catalog.registry.manifest())
        assert item["session_id"] == strict_canonical_hash(
            {"condition_id": condition["id"], "group": item["task_group"], "round": item["round"]},
            prefix="qa_vnext_online_session:",
        )
        assert item["id"] != item["session_id"] != context["id"]


def test_condition_budgets_include_final_and_match_the_single_transport_configuration(
    panel: plan.TaskPanel, implementation: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    condition, registrations, _ = freeze(panel, implementation, monkeypatch)
    config = TransportConfig().as_record()
    assert condition["maximum_actions_per_session"] == 12
    assert (
        condition["maximum_submissions_per_session"]
        == condition["maximum_provider_attempts_per_session"]
        == 32
    )
    assert condition["maximum_submissions_per_session"] >= 8 + 8 + 1
    assert condition["maximum_provider_attempts"] == 12 * 32 == 384
    assert condition["input_admission_allowance"] == config["maximum_input_tokens"] == 99_328
    assert condition["output_token_limit"] == config["max_tokens"] == 8192
    assert (
        condition["maximum_reserved_token_allowance"]
        == config["maximum_pilot_reserved_tokens"]
        == 384 * (99_328 + 8192)
    )
    assert condition["input_allowance_is_exact_provider_token_count"] is False
    assert condition["valid_final_stops_immediately"] is True
    assert condition["maximum_same_task_comparison_pairs"] == 3 * 6 == 18
    for item in registrations:
        assert item["maximum_actions"] == 12
        assert item["maximum_submissions"] == item["maximum_provider_attempts"] == 32


def test_plan_preserves_unknown_not_started_and_neutral_share_without_claiming_model_success(
    panel: plan.TaskPanel, implementation: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    condition, registrations, _ = freeze(panel, implementation, monkeypatch)
    assert condition["missing_or_unstarted_sessions_are_not_failures"] is True
    assert condition["unknown_and_not_started_have_null_success_indicator"] is True
    assert "missing usage remains unknown" in condition["actual_usage_authority"]
    assert condition["given_plan_and_legal_candidates"] is True
    assert condition["autonomous_planning"] is False
    assert condition["share_route_preassignment"] is None
    assert condition["maximum_parallel_sessions"] == 3
    assert condition["next_round_waits_for_current_round"] is True
    assert condition["halt_future_rounds_on_integrity_or_internal_execution_failure"] is True
    assert condition["already_started_sessions_remain_in_the_registered_population"] is True
    assert condition["malformed_public_response_is_a_new_submission_not_a_network_retry"] is True
    assert (
        condition["automatic_network_retries"]
        == condition["model_fallbacks"]
        == condition["session_replacements"]
        == 0
    )
    assert (
        condition["student_parameter_loads"]
        == condition["student_forward_calls"]
        == condition["student_updates"]
        == condition["gpu_jobs"]
        == 0
    )
    assert condition["outcome_adaptive_reordering"] is False
    assert condition["new_quotient_assignments_materialized"] is False
    assert condition["old_state_ids_or_P_Q_weights_reused"] is False
    assert condition["old_mainline"] == "remains_paused"
    for item in registrations:
        assert item["reference_route"] is None and item["replacement_allowed"] is False
        assert (
            item["independent_initial_state"] is True
            and item["reads_other_session_responses"] is False
        )
        assert not {"qualified", "qa_valid", "trajectory_valid", "end_to_end_success"} & set(item)


def test_identical_freeze_inputs_are_deterministic_and_run_tag_changes_all_session_ids(
    panel: plan.TaskPanel, implementation: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    first, first_rows, _ = freeze(panel, implementation, monkeypatch)
    second, second_rows, _ = freeze(panel, implementation, monkeypatch)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert canonical_json_bytes(first_rows) == canonical_json_bytes(second_rows)
    changed, changed_rows, _ = freeze(
        panel, implementation, monkeypatch, run_tag="different-fixed-run"
    )
    assert changed["id"] != first["id"]
    assert not {item["session_id"] for item in first_rows} & {
        item["session_id"] for item in changed_rows
    }
    assert changed["task_contexts"] == first["task_contexts"]


@pytest.mark.parametrize("run_tag", ["", "a/b", "/absolute"])
def test_invalid_run_tag_does_not_create_a_condition(
    panel: plan.TaskPanel,
    implementation: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    run_tag: str,
) -> None:
    with pytest.raises(ProtocolError, match="plan.run_tag"):
        freeze(panel, implementation, monkeypatch, run_tag=run_tag)


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_tokens", 16384),
        ("maximum_input_tokens", 200000),
        ("system_prompt", "Always choose reconstructed_total."),
        ("automatic_retries", 1),
    ],
)
def test_changed_teacher_prompt_or_budget_cannot_borrow_the_fixed_condition(
    panel: plan.TaskPanel,
    implementation: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: Any,
) -> None:
    config = reseal(TransportConfig().as_record(), "transport_config", **{field: value})
    with pytest.raises(ProtocolError, match="plan.fixed_generation_configuration"):
        freeze(panel, implementation, monkeypatch, config=config)


@pytest.mark.parametrize("subject", ["config", "implementation"])
def test_freeze_rejects_modified_record_content_with_an_unrecomputed_id(
    panel: plan.TaskPanel,
    implementation: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    subject: str,
) -> None:
    config = TransportConfig().as_record()
    if subject == "config":
        config["system_prompt"] = "changed"
    else:
        implementation["source_commit"] = "changed"
    with pytest.raises(ProtocolError, match="online.identity"):
        freeze(panel, implementation, monkeypatch, config=config)


def test_baseline_report_cannot_change_content_while_retaining_the_old_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = ROOT / plan.BASELINE_ENTRY / "report.json"
    original_read = Path.read_bytes
    payload = json.loads(original_read(target))
    payload["source_scope"] = "forged expanded source scope under old report id"
    changed = canonical_json_bytes(payload)

    def read(path: Path) -> bytes:
        return changed if path == target else original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(ProtocolError):
        plan.load_panel(ROOT)


def test_branch_cannot_be_replaced_with_another_source_case(
    panel: plan.TaskPanel, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases, rows = panel.catalog.frozen_source_cases(ROOT)
    changed = [
        replace(case, case_id="branch_other_case") if case.task_type == TASK_GROUPS["B"] else case
        for case in cases
    ]
    monkeypatch.setattr(panel.catalog, "frozen_source_cases", lambda root: (changed, rows))
    monkeypatch.setattr(plan, "build_catalog", lambda root: panel.catalog)
    with pytest.raises(ProtocolError, match="panel.fixed_branch"):
        plan.load_panel(ROOT)


@pytest.fixture
def source_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, bytes], list[list[str]]]:
    root = tmp_path / "controlled_repository"
    members = {"module.py": b"VALUE = 1\n", "package/helper.py": b"def helper():\n    return 2\n"}
    for name, raw in members.items():
        target = root / "trusted_data_synthesis/src" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        for name, raw in {**members, "README.txt": b"Not a Python source member"}.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(raw)
            archive.addfile(entry, io.BytesIO(raw))
    calls = []

    def git(command: list[str], *, cwd: Path, text: bool = False) -> str | bytes:
        assert cwd == root
        calls.append(command)
        if command == ["git", "rev-parse", "HEAD"]:
            assert text is True
            return "a" * 40 + "\n"
        if command == ["git", "rev-parse", "HEAD^{tree}"]:
            assert text is True
            return "b" * 40 + "\n"
        assert command == ["git", "archive", "a" * 40 + ":trusted_data_synthesis/src"]
        assert text is False
        return data.getvalue()

    monkeypatch.setattr(plan.subprocess, "check_output", git)
    return root, members, calls


def test_source_snapshot_checks_all_python_files_against_one_archive_without_extracting(
    source_archive: tuple[Path, dict[str, bytes], list[list[str]]],
) -> None:
    root, files, calls = source_archive
    before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    snapshot = plan.source_snapshot(root)
    identity(snapshot, "implementation")
    assert snapshot["source_commit"] == "a" * 40 and snapshot["source_tree"] == "b" * 40
    assert snapshot["every_python_source_bound"] is True
    assert snapshot["members"] == [
        {"path": "trusted_data_synthesis/src/" + name, "sha256": sha(raw), "bytes": len(raw)}
        for name, raw in sorted(files.items())
    ]
    assert len(calls) == 3
    assert {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    } == before
    plan.verify_source_snapshot(root, snapshot)


@pytest.mark.parametrize("mutation", ["changed", "extra"])
def test_dirty_python_content_or_new_uncommitted_module_prevents_source_freeze(
    source_archive: tuple[Path, dict[str, bytes], list[list[str]]], mutation: str
) -> None:
    root, _, _ = source_archive
    target = (
        root
        / "trusted_data_synthesis/src"
        / ("module.py" if mutation == "changed" else "new_module.py")
    )
    target.write_bytes(b"CHANGED = True\n")
    error = (
        "plan.source_not_committed" if mutation == "changed" else "plan.uncommitted_source_members"
    )
    with pytest.raises(ProtocolError, match=error):
        plan.source_snapshot(root)


@pytest.mark.parametrize("mutation", ["changed", "extra", "missing"])
def test_postfreeze_source_changes_are_rejected(
    source_archive: tuple[Path, dict[str, bytes], list[list[str]]], mutation: str
) -> None:
    root, _, _ = source_archive
    snapshot = plan.source_snapshot(root)
    target = root / "trusted_data_synthesis/src/module.py"
    if mutation == "changed":
        target.write_bytes(b"VALUE = 9\n")
    elif mutation == "extra":
        (target.parent / "extra.py").write_bytes(b"VALUE = 9\n")
    else:
        target.unlink()
    with pytest.raises((ProtocolError, FileNotFoundError)):
        plan.verify_source_snapshot(root, snapshot)


def test_source_member_path_cannot_escape_repository(
    source_archive: tuple[Path, dict[str, bytes], list[list[str]]],
) -> None:
    root, _, _ = source_archive
    snapshot = plan.source_snapshot(root)
    members = copy.deepcopy(snapshot["members"])
    members[0]["path"] = "../outside.py"
    forged = reseal(snapshot, "implementation", members=members)
    with pytest.raises(ProtocolError, match="plan.source_path"):
        plan.verify_source_snapshot(root, forged)


def test_source_snapshot_identity_cannot_be_silently_changed(
    source_archive: tuple[Path, dict[str, bytes], list[list[str]]],
) -> None:
    root, _, _ = source_archive
    snapshot = plan.source_snapshot(root)
    snapshot["source_commit"] = "c" * 40
    with pytest.raises(ProtocolError, match="online.identity.implementation"):
        plan.verify_source_snapshot(root, snapshot)


@pytest.fixture
def sealed(tmp_path: Path) -> tuple[DurableStore, dict[str, Any]]:
    store = DurableStore(tmp_path / "sealed")
    store.json("condition.json", {"id": "test-condition"})
    store.write("nested/raw.body", b"  original raw bytes\n")
    return store, plan.seal_directory(
        store, kind="test_plan_manifest", condition_id="test-condition"
    )


def test_sealed_directory_has_exact_sorted_members_hashes_and_no_self_member(
    sealed: tuple[DurableStore, dict[str, Any]],
) -> None:
    store, manifest = sealed
    actual = plan.verify_directory(store.root, kind="test_plan_manifest")
    assert actual == manifest
    assert manifest["self_excluding"] is True
    assert manifest["condition_id"] == "test-condition"
    assert [member["path"] for member in manifest["members"]] == [
        "condition.json",
        "nested/raw.body",
    ]
    for member in manifest["members"]:
        raw = (store.root / member["path"]).read_bytes()
        assert member["sha256"] == sha(raw) and member["bytes"] == len(raw)


@pytest.mark.parametrize(
    "mutation",
    ["bytes", "extra", "missing", "duplicate", "identity", "noncanonical", "self_exclusion"],
)
def test_manifest_and_member_tampering_is_rejected(
    sealed: tuple[DurableStore, dict[str, Any]], mutation: str
) -> None:
    store, manifest = sealed
    path = store.root / "manifest.json"
    if mutation == "bytes":
        (store.root / "nested/raw.body").write_bytes(b"changed")
    elif mutation == "extra":
        (store.root / "extra.json").write_bytes(b"{}")
    elif mutation == "missing":
        (store.root / "condition.json").unlink()
    elif mutation == "duplicate":
        altered = reseal(
            manifest, "test_plan_manifest", members=manifest["members"] + [manifest["members"][0]]
        )
        path.write_bytes(canonical_json_bytes(altered))
    elif mutation == "identity":
        manifest["condition_id"] = "different"
        path.write_bytes(canonical_json_bytes(manifest))
    elif mutation == "noncanonical":
        path.write_bytes(path.read_bytes() + b"\n")
    else:
        path.write_bytes(
            canonical_json_bytes(reseal(manifest, "test_plan_manifest", self_excluding=False))
        )
    with pytest.raises(ProtocolError):
        plan.verify_directory(store.root, kind="test_plan_manifest")


@pytest.mark.parametrize("name", ["manifest.json", "condition.json"])
def test_manifest_or_member_symlinks_are_rejected(
    sealed: tuple[DurableStore, dict[str, Any]], tmp_path: Path, name: str
) -> None:
    store, _ = sealed
    path = store.root / name
    outside = tmp_path / ("outside_" + name)
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(ProtocolError):
        plan.verify_directory(store.root, kind="test_plan_manifest")


def test_directory_cannot_be_resealed_over_an_existing_manifest(
    sealed: tuple[DurableStore, dict[str, Any]],
) -> None:
    store, _ = sealed
    before = (store.root / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        plan.seal_directory(store, kind="test_plan_manifest")
    assert (store.root / "manifest.json").read_bytes() == before
