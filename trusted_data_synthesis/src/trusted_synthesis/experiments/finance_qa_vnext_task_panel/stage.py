"""Freeze actual source contexts, full population, policies and request budget checks."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import (
    public_action_contract,
    publish_action_contract,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import (
    public_update_contract,
    publish_update_contract,
)

from ..finance_qa_vnext_action_branch.plan import initial_request
from ..finance_qa_vnext_model_execution.models import identity, read_json, record, require, sha
from ..finance_qa_vnext_model_execution.plan import (
    BASELINE_ENTRY,
    seal_directory,
    source_snapshot,
    verify_directory,
    verify_source_snapshot,
)
from ..finance_qa_vnext_model_execution.representation import register_tokenizer
from ..finance_qa_vnext_model_execution.runner import _software
from ..finance_qa_vnext_model_execution.transport import SYSTEM_PROMPT, render_http_request
from .guards import execution_guard, guard_report
from .plan import STAGE, TASK_GROUPS, configuration, freeze_condition
from .representation import representation_policy

PREDECESSOR = "171035326e1f88b9e8691e02742cadacdcb94dce"
DESIGN_BYTES = 25_917
DESIGN_SHA256 = "67199bf4810f0e6d01da5069429326459ccc29c90fd410f73e23cd4d70ad65d1"
HISTORY_PREFIXES = (
    "qa_vnext_integration",
    "qa_vnext_model_execution",
    "qa_vnext_update_calibration",
    "qa_vnext_repaired_full_task",
    "qa_vnext_action_branch",
    "qa_vnext_length_adaptation",
)


def history_inventory(root: Path) -> dict[str, Any]:
    members = []
    for name in HISTORY_PREFIXES:
        directory = root / "trusted_data_synthesis/artifacts" / name
        require(directory.is_dir(), "task_panel.history_missing")
        for path in sorted(directory.rglob("*")):
            require(not path.is_symlink(), "task_panel.history_symlink")
            if path.is_file():
                raw = path.read_bytes()
                members.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "bytes": len(raw),
                        "sha256": sha(raw),
                    }
                )
    return record(
        "task_panel_history_inventory",
        members=members,
        file_count=len(members),
        byte_count=sum(item["bytes"] for item in members),
        immutable=True,
    )


def preserved_execution_sources(root: Path) -> dict[str, Any]:
    """All predecessor Python implementation bytes stay fixed; only a new wrapper is added."""
    result = subprocess.check_output(
        [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            PREDECESSOR,
            "--",
            "trusted_data_synthesis/src",
        ],
        cwd=root,
        text=True,
    )
    paths = [name for name in result.splitlines() if name.endswith(".py")]
    # One archive read is much cheaper than hundreds of git-show subprocesses.
    from io import BytesIO
    from tarfile import open as open_tar

    archive = subprocess.check_output(
        [
            "git",
            "archive",
            PREDECESSOR + ":trusted_data_synthesis/src",
        ],
        cwd=root,
    )
    members = []
    with open_tar(fileobj=BytesIO(archive), mode="r:") as stream:
        for member in stream.getmembers():
            if not member.isfile() or not member.name.endswith(".py"):
                continue
            handle = stream.extractfile(member)
            assert handle is not None
            original = handle.read()
            name = "trusted_data_synthesis/src/" + member.name
            require((root / name).read_bytes() == original, "task_panel.predecessor_source_changed")
            members.append({"path": name, "bytes": len(original), "sha256": sha(original)})
    require({item["path"] for item in members} == set(paths), "task_panel.preserved_source_set")
    return record(
        "task_panel_source_preservation",
        predecessor_commit=PREDECESSOR,
        members=members,
        file_count=len(members),
        all_predecessor_sources_byte_identical=True,
        admission_or_mapper_relaxed=False,
        existing_transport_schema_modified=False,
    )


def wiring_controls(
    root: Path, panel: Any, config: Any, registrations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Only added wiring checks: eight initial requests and existing late-state shapes."""
    require(
        len(registrations) == len({r["id"] for r in registrations}) == 16,
        "task_panel.controls_population",
    )
    rows = []

    def check(request, *, label, source_path, session_id):
        require(
            request["public_action_contract"] == public_action_contract()
            and request["public_update_contract"] == public_update_contract(),
            "task_panel.controls_publication",
        )
        http = render_http_request(request, config, session_id=session_id, attempt_index=0)
        body = read_json(http["body_json"].encode())
        require(
            body["messages"]
            == [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": canonical_json_bytes(request).decode()},
            ]
            and http["body_byte_count"] <= 98_304
            and http["input_admission_upper_bound"] <= 99_328,
            "task_panel.controls_request_budget_or_prompt",
        )
        rows.append(
            {
                "label": label,
                "source_path": source_path,
                "request_id": request["id"],
                "body_byte_count": http["body_byte_count"],
                "input_admission_upper_bound": http["input_admission_upper_bound"],
                "body_sha256": http["body_sha256"],
                "within_request_budget": True,
                "both_publications_present": True,
                "neutral_prompt_without_examples": True,
            }
        )

    by_group = {r["task_group"]: r for r in registrations if r["round"] == 1}
    for group in TASK_GROUPS:
        check(
            initial_request(panel.adapter(group)),
            label="initial_" + group,
            source_path=None,
            session_id=by_group[group]["session_id"],
        )
    baseline = read_json((root / BASELINE_ENTRY / "report.json").read_bytes())
    for coverage in baseline["coverage_rows"]:
        path = Path(BASELINE_ENTRY) / "sessions" / coverage["case_id"] / "session.json"
        session = read_json((root / path).read_bytes())
        group = next(g for g, name in TASK_GROUPS.items() if name == coverage["task_type"])
        for event in session["events"][-2:]:
            request = publish_action_contract(publish_update_contract(event["request"]))
            check(
                request,
                label=coverage["case_id"] + ":" + str(event["sequence"]),
                source_path=path.as_posix(),
                session_id=by_group[group]["session_id"],
            )
    # The latest two full B trajectories provide the already observed longest late Updates.
    for label in ("B01", "B02"):
        path = Path("trusted_data_synthesis/artifacts/qa_vnext_action_branch/") / (
            "action_contract_branch_v1_20260906/execution/sessions/"
            + label
            + "/runtime/session.json"
        )
        old = read_json((root / path).read_bytes())
        check(
            old["events"][15]["request"],
            label=label + "_historical_T16_shape",
            source_path=path.as_posix(),
            session_id=by_group["B"]["session_id"],
        )
    return record(
        "task_panel_wiring_controls",
        rows=rows,
        request_shape_count=len(rows),
        unique_initial_tasks=8,
        registered_sessions=16,
        all_expected_outcomes=True,
        maximum_observed_body_bytes=max(row["body_byte_count"] for row in rows),
        future_model_states_are_not_proven_to_fit=True,
        historical_requests_used_as_online_prefix=False,
        provider_calls=0,
        runtime_executions=0,
        finance_operation_executions=0,
        scope="new panel and publication/budget wiring only; not repeated admission calibration",
    )


def prepare(root: Path, directory: Path, design_path: Path, *, run_tag: str) -> dict[str, Any]:
    root, directory = root.resolve(), directory.resolve()
    require(
        directory.name == "preparation" and not directory.exists(), "task_panel.preparation_output"
    )
    with execution_guard(online=False) as counts:
        design = design_path.read_bytes()
        require(
            len(design) == DESIGN_BYTES and sha(design) == DESIGN_SHA256, "task_panel.design_bytes"
        )
        implementation = source_snapshot(root)
        preservation = preserved_execution_sources(root)
        config = configuration()
        binding = register_tokenizer(root)
        policy = representation_policy(binding)
        condition, registrations, panel = freeze_condition(
            root,
            config.as_record(),
            implementation,
            policy,
            run_tag=run_tag,
        )
        history = history_inventory(root)
        controls = wiring_controls(root, panel, config, registrations)
        store = DurableStore(directory)
        store.write("experiment_design.txt", design)
        for key, value in {
            "implementation": implementation,
            "source_preservation": preservation,
            "configuration": config.as_record(),
            "software": _software(),
            "condition": condition,
            "registrations": registrations,
            "catalog": panel.catalog.descriptor,
            "protocol": contract(),
            "coverage": panel.coverage,
            "history_inventory": history,
            "tokenizer_binding": binding,
            "representation_policy": policy,
            "controls": controls,
        }.items():
            store.json(key + ".json", value)
        for row in registrations:
            request = initial_request(panel.adapter(row["task_group"]))
            http = render_http_request(
                request, config, session_id=row["session_id"], attempt_index=0
            )
            store.json(f"initial/{row['label']}_request.json", request)
            store.json(f"initial/{row['label']}_http.json", http)
        require(history_inventory(root) == history, "task_panel.preparation_history_changed")
        report = record(
            "task_panel_preparation",
            stage=STAGE,
            condition_id=condition["id"],
            implementation_id=implementation["id"],
            controls_id=controls["id"],
            tokenizer_binding_id=binding["id"],
            representation_policy_id=policy["id"],
            session_registration_ids=[r["id"] for r in registrations],
            execution_directory=str(directory.parent / "execution"),
            provider_attempts=0,
            prepared=True,
        )
        store.json("report.json", report)
    store.json("execution_guards.json", guard_report(counts, phase="preparation"))
    seal_directory(store, kind="preparation_manifest", preparation_id=report["id"])
    return report


def prepared(root: Path, directory: Path) -> dict[str, Any]:
    manifest = verify_directory(directory, kind="preparation_manifest")
    names = (
        "report",
        "source_preservation",
        "condition",
        "implementation",
        "configuration",
        "registrations",
        "tokenizer_binding",
        "representation_policy",
        "coverage",
        "software",
        "history_inventory",
        "controls",
    )
    values = {key: read_json((directory / (key + ".json")).read_bytes()) for key in names}
    identity(values["report"], "task_panel_preparation")
    verify_source_snapshot(root, values["implementation"])
    require(
        preserved_execution_sources(root) == values["source_preservation"],
        "task_panel.frozen_sources",
    )
    require(_software() == values["software"], "task_panel.frozen_software")
    config = configuration()
    require(config.as_record() == values["configuration"], "task_panel.frozen_configuration")
    binding = register_tokenizer(root)
    require(binding == values["tokenizer_binding"], "task_panel.frozen_tokenizer")
    policy = representation_policy(binding)
    require(policy == values["representation_policy"], "task_panel.frozen_representation_policy")
    condition, registrations, panel = freeze_condition(
        root,
        config.as_record(),
        values["implementation"],
        policy,
        run_tag=values["condition"]["run_tag"],
    )
    for actual, frozen in (
        (condition, values["condition"]),
        (registrations, values["registrations"]),
        (panel.coverage, values["coverage"]),
        (history_inventory(root), values["history_inventory"]),
    ):
        require(
            canonical_json_bytes(actual) == canonical_json_bytes(frozen),
            "task_panel.frozen_population",
        )
    require(
        values["report"]["condition_id"] == condition["id"]
        and values["report"]["execution_directory"] == str(directory.parent / "execution")
        and manifest["preparation_id"] == values["report"]["id"],
        "task_panel.preparation_binding",
    )
    for row in registrations:
        request = initial_request(panel.adapter(row["task_group"]))
        http = render_http_request(request, config, session_id=row["session_id"], attempt_index=0)
        require(
            canonical_json_bytes(request)
            == (directory / f"initial/{row['label']}_request.json").read_bytes()
            and canonical_json_bytes(http)
            == (directory / f"initial/{row['label']}_http.json").read_bytes(),
            "task_panel.frozen_initial_request",
        )
    return {**values, "manifest": manifest, "config": config, "panel": panel}
