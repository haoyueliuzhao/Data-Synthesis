"""Freeze Action-publication repair plus two fresh B sessions, never C/S reruns."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import public_action_contract
from trusted_synthesis.domains.finance.qa_vnext.measurement import _request, _state
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import public_update_contract

from ..finance_qa_vnext_model_execution.models import (
    TASK_GROUPS as ALL_TASK_GROUPS,
)
from ..finance_qa_vnext_model_execution.models import (
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

TASK_GROUPS = {"B": ALL_TASK_GROUPS["B"]}
STAGE = "finance_qa_vnext_action_public_contract_repair_and_branch_reachability_pilot"
DESIGN_BYTES = 27_163
DESIGN_SHA256 = "faed220ec5e344741d239883beb3d05020f1d65e82d045a3c98bca19aec0ebeb"
PREDECESSOR = "5df110cc6b98bd65658ad4204c3ccd5b4ec1c9a7"


def configuration() -> TransportConfig:
    return TransportConfig(
        attempts_per_session=32, maximum_pilot_attempts=64, system_prompt=SYSTEM_PROMPT
    )


def initial_request(adapter: Any) -> dict[str, Any]:
    state = _state(
        adapter.context["id"], [], None, {"submissions": 0, "actions": 0, "updates": 0}, None, False
    )
    return _request(adapter, state, contract())


def history_inventory(root: Path) -> dict[str, Any]:
    members = []
    for name in (
        "qa_vnext_model_execution",
        "qa_vnext_update_calibration",
        "qa_vnext_repaired_full_task",
    ):
        directory = root / "trusted_data_synthesis/artifacts" / name
        require(directory.is_dir(), "branch.history_missing")
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
    return record("action_branch_history_inventory", members=members, immutable=True)


def freeze_condition(
    root: Path, config: dict[str, Any], implementation: dict[str, Any], *, run_tag: str
) -> tuple[dict[str, Any], list[dict[str, Any]], TaskPanel]:
    identity(implementation, "implementation")
    require(config == configuration().as_record(), "branch.fixed_configuration")
    require(bool(run_tag) and "/" not in run_tag, "branch.run_tag")
    panel = load_panel(root)
    panel.coverage = [
        record(
            "population_coverage",
            **{
                **{k: v for k, v in row.items() if k not in {"id", "schema_version"}},
                "registered_model_sessions": 2 if row["task_type"] == TASK_GROUPS["B"] else 0,
                "selected_for_model_population": row["task_type"] == TASK_GROUPS["B"],
                "task_group": "B" if row["task_type"] == TASK_GROUPS["B"] else None,
                "population_status": "selected_model_task"
                if row["task_type"] == TASK_GROUPS["B"]
                else "source_available_not_selected"
                if row["source_available"]
                else "source_unavailable",
            },
        )
        for row in panel.coverage
    ]
    condition = record(
        "action_branch_condition",
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
        public_action_contract=public_action_contract(),
        task_contexts={group: panel.adapter(group).context for group in TASK_GROUPS},
        generation_condition=(
            "fresh B full execution under Action and retained Update public contracts"
        ),
        given_plan_and_legal_candidates=True,
        autonomous_planning=False,
        accept_only_instruction=False,
        share_route_preassignment=None,
        historical_pending_states_or_model_responses_used_as_prefix=False,
        session_count=2,
        sessions_per_task=2,
        rounds=1,
        round_launch_order=["B01", "B02"],
        maximum_parallel_sessions=2,
        next_round_waits_for_current_round=True,
        outcome_adaptive_reordering=False,
        automatic_network_retries=0,
        model_fallbacks=0,
        session_replacements=0,
        maximum_actions_per_session=12,
        maximum_submissions_per_session=32,
        maximum_provider_attempts_per_session=32,
        maximum_provider_attempts=64,
        maximum_http_body_bytes=98304,
        input_admission_allowance=99328,
        output_token_limit=8192,
        maximum_reserved_token_allowance=6_881_280,
        allowance_is_actual_usage=False,
        missing_usage_is_unknown=True,
        unknown_and_not_started_have_null_success_indicator=True,
        valid_final_stops_immediately=True,
        public_correction_is_a_new_model_submission_not_a_network_retry=True,
        halt_future_rounds_on_integrity_or_internal_execution_failure=True,
        already_started_sessions_remain_in_registered_population=True,
        registered_denominator=2,
        equal_task_weights=[1.0],
        scientific_witness_criterion=(
            "at least one Qualified complete B session under this condition"
        ),
        historical_C_S_not_in_this_population=True,
        no_cross_condition_success_pooling=True,
        scientific_success_is_not_workflow_gate=True,
        maximum_same_task_comparison_pairs=1,
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
    for replicate in (1, 2):
        for group in ("B",):
            round_number = 1
            adapter = panel.adapter(group)
            session_id = strict_canonical_hash(
                {"condition_id": condition["id"], "group": group, "replicate": replicate},
                prefix="qa_vnext_action_branch_session:",
            )
            # Existing wire identity is required by unchanged independent qualification.
            registrations.append(
                record(
                    "session_registration",
                    session_id=session_id,
                    label=f"{group}{replicate:02d}",
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
        len(registrations) == 2 and len({r["session_id"] for r in registrations}) == 2,
        "branch.population",
    )
    return condition, registrations, panel


def prepare(root: Path, directory: Path, design_path: Path, *, run_tag: str) -> dict[str, Any]:
    from .controls import run_controls, validator_preservation

    root, directory = root.resolve(), directory.resolve()
    require(directory.name == "preparation", "branch.preparation_name")
    design = design_path.read_bytes()
    require(len(design) == DESIGN_BYTES and sha(design) == DESIGN_SHA256, "branch.design_bytes")
    preservation = validator_preservation(root)
    implementation = source_snapshot(root)
    config = configuration()
    condition, registrations, panel = freeze_condition(
        root, config.as_record(), implementation, run_tag=run_tag
    )
    store = DurableStore(directory)
    store.write("experiment_design.txt", design)
    for key, value in {
        "implementation": implementation,
        "validator_preservation": preservation,
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
            "branch.initial_request_budget",
        )
        store.json(f"initial/{row['label']}_request.json", request)
        store.json(f"initial/{row['label']}_http.json", http)
    controls = run_controls(panel, directory / "controls", config)
    require(controls["passed"], "branch.entry_controls")
    report = record(
        "action_branch_preparation",
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
    from .controls import validator_preservation

    manifest = verify_directory(directory, kind="preparation_manifest")
    values = {
        key: read_json((directory / (key + ".json")).read_bytes())
        for key in (
            "report",
            "validator_preservation",
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
    identity(values["report"], "action_branch_preparation")
    verify_source_snapshot(root, values["implementation"])
    require(
        validator_preservation(root) == values["validator_preservation"], "branch.frozen_validators"
    )
    require(_software() == values["software"], "branch.frozen_software")
    config = configuration()
    require(config.as_record() == values["configuration"], "branch.frozen_configuration")
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
            canonical_json_bytes(actual) == canonical_json_bytes(frozen), "branch.frozen_population"
        )
    require(register_tokenizer(root) == values["tokenizer_binding"], "branch.frozen_tokenizer")
    require(
        values["report"]["condition_id"] == condition["id"]
        and values["report"]["execution_directory"] == str(directory.parent / "execution")
        and manifest["preparation_id"] == values["report"]["id"],
        "branch.preparation_binding",
    )
    for row in registrations:
        request = initial_request(panel.adapter(row["task_group"]))
        http = render_http_request(request, config, session_id=row["session_id"], attempt_index=0)
        require(
            canonical_json_bytes(request)
            == (directory / f"initial/{row['label']}_request.json").read_bytes()
            and canonical_json_bytes(http)
            == (directory / f"initial/{row['label']}_http.json").read_bytes(),
            "branch.frozen_initial_request",
        )
    return {**values, "manifest": manifest, "config": config, "panel": panel}
