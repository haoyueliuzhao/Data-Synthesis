"""Freeze only the newly authorized six-session population and entry checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.measurement import _request, _state
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import public_update_contract

from ..finance_qa_vnext_model_execution.models import (
    TASK_GROUPS,
    identity,
    read_json,
    record,
    require,
    sha,
)
from ..finance_qa_vnext_model_execution.plan import (
    TaskPanel,
    load_panel,
    seal_directory,
    source_snapshot,
    verify_directory,
    verify_source_snapshot,
)
from ..finance_qa_vnext_model_execution.representation import register_tokenizer
from ..finance_qa_vnext_model_execution.runner import _software
from ..finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    TransportConfig,
    render_http_request,
)

STAGE = "finance_qa_vnext_repaired_update_six_session_full_task_pilot"
DESIGN_BYTES = 24_739
DESIGN_SHA256 = "08cb42f52e679c5ebb4b6646a03003bb69174b57a0e5f006cb4b6a6f75778042"
PREDECESSOR = "140c012a55f04c0f4ffc6f22d6128cc2790eb3cd"


def configuration() -> TransportConfig:
    return TransportConfig(
        attempts_per_session=32, maximum_pilot_attempts=192, system_prompt=SYSTEM_PROMPT
    )


def initial_request(adapter: Any) -> dict[str, Any]:
    state = _state(
        adapter.context["id"], [], None, {"submissions": 0, "actions": 0, "updates": 0}, None, False
    )
    return _request(adapter, state, contract())


def history_inventory(root: Path) -> dict[str, Any]:
    members = []
    for name in ("qa_vnext_model_execution", "qa_vnext_update_calibration"):
        directory = root / "trusted_data_synthesis/artifacts" / name
        require(directory.is_dir(), "six.history_missing")
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                data = path.read_bytes()
                members.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "bytes": len(data),
                        "sha256": sha(data),
                    }
                )
    return record("repaired_history_inventory", members=members, immutable=True)


def freeze_condition(
    root: Path, config: dict[str, Any], implementation: dict[str, Any], *, run_tag: str
) -> tuple[dict[str, Any], list[dict[str, Any]], TaskPanel]:
    identity(implementation, "implementation")
    require(config == configuration().as_record(), "six.fixed_configuration")
    require(bool(run_tag) and "/" not in run_tag, "six.run_tag")
    panel = load_panel(root)
    panel.coverage = [
        record(
            "population_coverage",
            **{
                **{k: v for k, v in row.items() if k not in {"id", "schema_version"}},
                "registered_model_sessions": 2 if row["selected_for_model_population"] else 0,
            },
        )
        for row in panel.coverage
    ]
    condition = record(
        "repaired_full_condition",
        stage=STAGE,
        run_tag=run_tag,
        predecessor_commit=PREDECESSOR,
        implementation_id=implementation["id"],
        design_sha256=DESIGN_SHA256,
        design_byte_count=DESIGN_BYTES,
        current_user_directive="参照审计继续实验",
        current_directive_authorizes_the_proposed_online_stage=True,
        model_configuration_id=config["id"],
        catalog_id=panel.catalog.descriptor["id"],
        protocol_id=contract()["id"],
        public_update_contract=public_update_contract(),
        task_contexts={group: panel.adapter(group).context for group in TASK_GROUPS},
        generation_condition="fresh full execution under repaired public presentation and feedback",
        given_plan_and_legal_candidates=True,
        autonomous_planning=False,
        accept_only_instruction=False,
        share_route_preassignment=None,
        historical_pending_states_or_model_responses_used_as_prefix=False,
        session_count=6,
        sessions_per_task=2,
        rounds=2,
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
        maximum_provider_attempts=192,
        maximum_http_body_bytes=98304,
        input_admission_allowance=99328,
        output_token_limit=8192,
        maximum_reserved_token_allowance=20_643_840,
        allowance_is_actual_usage=False,
        missing_usage_is_unknown=True,
        unknown_and_not_started_have_null_success_indicator=True,
        valid_final_stops_immediately=True,
        public_correction_is_a_new_model_submission_not_a_network_retry=True,
        halt_future_rounds_on_integrity_or_internal_execution_failure=True,
        already_started_sessions_remain_in_registered_population=True,
        registered_denominator=6,
        equal_task_weights=[1 / 3, 1 / 3, 1 / 3],
        scientific_witness_criterion="at least one Qualified complete success per selected task",
        scientific_success_is_not_workflow_gate=True,
        maximum_same_task_comparison_pairs=3,
        optional_export="actual Qualified sessions; admitted original responses only",
        optional_token_limit=24576,
        overlength_candidates_preserved_without_truncation=True,
        old_results_combined=False,
        old_quotient_assignments_or_weights_reused=False,
        student_parameter_loads=0,
        student_updates=0,
        gpu_jobs=0,
        old_mainline="remains_paused",
    )
    registrations = []
    for round_number in (1, 2):
        for group in ("C", "B", "S"):
            adapter = panel.adapter(group)
            session_id = strict_canonical_hash(
                {"condition_id": condition["id"], "group": group, "round": round_number},
                prefix="qa_vnext_repaired_full_session:",
            )
            # Existing wire identity is required by unchanged independent qualification.
            registrations.append(
                record(
                    "session_registration",
                    session_id=session_id,
                    label=f"{group}{round_number:02d}",
                    ordinal=len(registrations),
                    round=round_number,
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
    require(
        len(registrations) == 6 and len({r["session_id"] for r in registrations}) == 6,
        "six.population",
    )
    return condition, registrations, panel


def prepare(root: Path, directory: Path, design_path: Path, *, run_tag: str) -> dict[str, Any]:
    from .controls import run_controls

    root, directory = root.resolve(), directory.resolve()
    require(directory.name == "preparation", "six.preparation_name")
    design = design_path.read_bytes()
    require(len(design) == DESIGN_BYTES and sha(design) == DESIGN_SHA256, "six.design_bytes")
    implementation = source_snapshot(root)
    config = configuration()
    condition, registrations, panel = freeze_condition(
        root, config.as_record(), implementation, run_tag=run_tag
    )
    store = DurableStore(directory)
    store.write("experiment_design.txt", design)
    for key, value in {
        "implementation": implementation,
        "configuration": config.as_record(),
        "software": _software(),
        "condition": condition,
        "registrations": registrations,
        "catalog": panel.catalog.descriptor,
        "protocol": contract(),
        "coverage": panel.coverage,
        "history_inventory": history_inventory(root),
        "tokenizer_binding": register_tokenizer(root),
    }.items():
        store.json(key + ".json", value)
    for row in registrations:
        request = initial_request(panel.adapter(row["task_group"]))
        http = render_http_request(request, config, session_id=row["session_id"], attempt_index=0)
        require(
            http["body_byte_count"] <= config.maximum_serialized_request_bytes,
            "six.initial_request_budget",
        )
        store.json(f"initial/{row['label']}_request.json", request)
        store.json(f"initial/{row['label']}_http.json", http)
    controls = run_controls(panel, directory / "controls", config)
    require(controls["passed"], "six.entry_controls")
    report = record(
        "repaired_preparation",
        stage=STAGE,
        condition_id=condition["id"],
        implementation_id=implementation["id"],
        controls_id=controls["id"],
        session_registration_ids=[r["id"] for r in registrations],
        execution_directory=str(directory.parent / "execution"),
        provider_attempts=0,
        prepared=True,
    )
    store.json("report.json", report)
    seal_directory(store, kind="preparation_manifest", preparation_id=report["id"])
    return report


def _prepared(root: Path, directory: Path) -> dict[str, Any]:
    manifest = verify_directory(directory, kind="preparation_manifest")
    values = {
        key: read_json((directory / (key + ".json")).read_bytes())
        for key in (
            "report",
            "condition",
            "implementation",
            "configuration",
            "registrations",
            "tokenizer_binding",
            "coverage",
            "software",
            "history_inventory",
        )
    }
    identity(values["report"], "repaired_preparation")
    verify_source_snapshot(root, values["implementation"])
    require(_software() == values["software"], "six.frozen_software")
    config = configuration()
    require(config.as_record() == values["configuration"], "six.frozen_configuration")
    condition, registrations, panel = freeze_condition(
        root, config.as_record(), values["implementation"], run_tag=values["condition"]["run_tag"]
    )
    for actual, frozen in (
        (condition, values["condition"]),
        (registrations, values["registrations"]),
        (panel.coverage, values["coverage"]),
        (history_inventory(root), values["history_inventory"]),
    ):
        require(
            canonical_json_bytes(actual) == canonical_json_bytes(frozen), "six.frozen_population"
        )
    require(register_tokenizer(root) == values["tokenizer_binding"], "six.frozen_tokenizer")
    require(
        values["report"]["condition_id"] == condition["id"]
        and values["report"]["execution_directory"] == str(directory.parent / "execution")
        and manifest["preparation_id"] == values["report"]["id"],
        "six.preparation_binding",
    )
    for row in registrations:
        request = initial_request(panel.adapter(row["task_group"]))
        http = render_http_request(request, config, session_id=row["session_id"], attempt_index=0)
        require(
            canonical_json_bytes(request)
            == (directory / f"initial/{row['label']}_request.json").read_bytes()
            and canonical_json_bytes(http)
            == (directory / f"initial/{row['label']}_http.json").read_bytes(),
            "six.frozen_initial_request",
        )
    return {**values, "manifest": manifest, "config": config, "panel": panel}
