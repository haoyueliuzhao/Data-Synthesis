"""Pre-call freeze from immutable historical first-Observation challenges."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import (
    publish_update_contract,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification as proof
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import sha
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    render_http_request,
)

from .controls import check_public_rules, unchanged_validator
from .models import (
    BASELINE,
    OLD_EXECUTION_SHA,
    OLD_RELATIVE,
    STAGE,
    configuration,
    inventory,
    read,
    record,
)


def historical_challenges(root: Path) -> list[dict[str, Any]]:
    old = root / OLD_RELATIVE
    old_config = read(old / "preparation/configuration.json")
    new_config = configuration().as_record()
    for field in (
        "endpoint",
        "model",
        "temperature",
        "top_p",
        "max_tokens",
        "thinking",
        "response_format",
        "stream",
        "allowed_response_models",
        "maximum_serialized_request_bytes",
        "maximum_input_tokens",
        "input_overhead_allowance",
        "maximum_http_response_bytes",
        "maximum_public_response_bytes",
        "maximum_request_reserved_tokens",
        "timeout_seconds",
        "connect_timeout_seconds",
        "automatic_retries",
        "model_fallbacks",
        "native_tool_calls",
    ):
        require(
            old_config[field] == new_config[field], "calibration.generation_condition_unchanged"
        )
    require(old_config["system_prompt"] == SYSTEM_PROMPT, "calibration.original_system_prompt")
    require(
        sha((old / "execution/manifest.json").read_bytes()) == OLD_EXECUTION_SHA,
        "calibration.historical_execution_anchor",
    )
    files = proof._Artifacts(old / "execution")
    registrations = read(old / "preparation/registrations.json")
    require(
        registrations == read(old / "execution/registrations.json"),
        "calibration.historical_registration_binding",
    )
    require(
        [r["label"] for r in registrations]
        == [f"{group}{round_:02d}" for round_ in range(1, 5) for group in "CBS"],
        "calibration.historical_population",
    )
    challenges = []
    for registration in registrations:
        label = registration["label"]
        prefix = f"sessions/{label}/runtime/"
        session = files.json(prefix + "session.json")
        first = next(
            event for event in session["events"] if event.get("execution", {}).get("success")
        )
        observation = first["observation"]
        require(
            first["parsed"]["kind"] == "action"
            and first["receipt"]["admitted"]
            and observation["independent_output_valid"] is True
            and observation["execution_id"] == first["execution"]["id"]
            and observation["proposition"] == first["execution"]["proposition"],
            "calibration.historical_execution_observation",
        )
        event = next(
            event
            for event in session["events"]
            if event["sequence"] > first["sequence"]
            and event["request"]["state"]["pending_observation"] is not None
        )
        request = event["request"]
        turn = event["sequence"]
        source_path = prefix + f"turns/{turn:03d}_request.json"
        raw = files.raw(source_path)
        require(
            raw == canonical_json_bytes(request)
            and request["state"]["pending_observation"] == observation,
            "calibration.first_pending_request",
        )
        transport_prefix = f"sessions/{label}/transport/"
        ledger = files.json(transport_prefix + "ledger.json")
        row = next(row for row in ledger["attempts"] if row["turn_index"] == turn)
        http_path = transport_prefix + row["paths"]["http_request_body"]
        body = read(old / "execution" / http_path)
        require(
            body["messages"][1]["content"].encode() == raw,
            "calibration.historical_http_public_binding",
        )
        challenges.append(
            record(
                "challenge",
                label=label,
                task_group=registration["task_group"],
                round=registration["round"],
                historical_registration=registration,
                historical_session_id=session["id"],
                historical_action_turn=first["sequence"],
                historical_update_turn=turn,
                historical_execution_id=first["execution"]["id"],
                historical_observation_id=observation["id"],
                shape=observation["proposition"]["operation"],
                source_request_path=source_path,
                source_request_sha256=sha(raw),
                source_http_body_path=http_path,
                source_http_body_sha256=sha(files.raw(http_path)),
                original_request=request,
            )
        )
    require(
        Counter(c["shape"] for c in challenges)
        == {
            "registered_compare": 4,
            "lookup": 4,
            "relation_sum": 3,
            "share_ratio": 1,
        },
        "calibration.historical_shape_coverage",
    )
    return challenges


def _condition(run_tag, implementation, design, old_inventory, challenges) -> dict[str, Any]:
    return record(
        "condition",
        stage=STAGE,
        run_tag=run_tag,
        historical_result_commit=BASELINE,
        historical_execution_manifest_sha256=OLD_EXECUTION_SHA,
        implementation_id=implementation["id"],
        model_configuration_id=configuration().as_record()["id"],
        design_sha256=sha(design),
        old_inventory_sha256=sha(canonical_json_bytes(old_inventory)),
        challenge_ids=[item["id"] for item in challenges],
        fixed_pairs=12,
        fixed_calls=24,
        selection="first actual successful Action, then first public pending-Observation request",
        shared_new_instruction="encode complete accept only; O is NOT verbatim historical replay",
        arms={"O": "unchanged historical public Request", "R": "add versioned Update rules only"},
        round_pair_orders=[["O", "R"], ["R", "O"], ["O", "R"], ["R", "O"]],
        pairs_per_round_concurrent=3,
        arms_within_pair_sequential=True,
        second_arm_frozen_before_first_call=True,
        cross_arm_response_conditioning=False,
        model_alias_is_not_immutable_weights=True,
        provider_calls_per_arm=1,
        automatic_retries=0,
        replacements=0,
        action_executions=0,
        update_commits=0,
        feedback_followup_calls=0,
        student_jobs=0,
        maximum_reserved_tokens=2580480,
        unknown_and_not_started="retain null in fixed denominator; never resample",
        known_failures="retain false, including fully evidenced no response or schema failure",
        integrity_failure=(
            "halt affected remaining arm and all future rounds; retain started prefixes"
        ),
        engineering_gate={
            "all_24_evidence_complete": True,
            "R_success_minimum": 10,
            "R_success_per_C_B_S_minimum": 3,
            "statistical_lower_bound": False,
        },
        stop_after_24=True,
        followup_six_sessions="separate future freeze, not automatically run",
        historical_q_and_token_exports_unchanged=True,
        qualified_sessions_not_measured=True,
    )


def _registration(challenge, condition, arm, position) -> dict[str, Any]:
    request = challenge["original_request"]
    if arm == "R":
        request = publish_update_contract(request)
    identity = record(
        "call_identity", condition_id=condition["id"], challenge_id=challenge["id"], arm=arm
    )
    return record(
        "registration",
        label=challenge["label"] + "_" + arm,
        pair_label=challenge["label"],
        arm=arm,
        round=challenge["round"],
        task_group=challenge["task_group"],
        shape=challenge["shape"],
        position_in_pair=position,
        session_id=identity["id"],
        condition_id=condition["id"],
        challenge_id=challenge["id"],
        model_configuration_id=configuration().as_record()["id"],
        protocol_id=request["protocol_id"],
        context_id=request["context"]["id"],
        task_id=request["context"]["task_id"],
        maximum_provider_attempts=1,
        historical_update_turn=challenge["historical_update_turn"],
        public_request_id=request["id"],
        public_request_sha256=sha(canonical_json_bytes(request)),
    )


def prepare(root: Path, directory: Path, design_path: Path, *, run_tag: str) -> dict[str, Any]:
    require(bool(run_tag) and not directory.exists(), "calibration.new_freeze_directory")
    require(
        not directory.resolve().is_relative_to((root / OLD_RELATIVE).resolve()),
        "calibration.no_historical_writes",
    )
    implementation = source_snapshot(root)
    validators = unchanged_validator(root)
    challenges = historical_challenges(root)
    old_inventory = inventory(root / "trusted_data_synthesis/artifacts/qa_vnext_model_execution")
    config = configuration()
    condition = _condition(
        run_tag, implementation, design_path.read_bytes(), old_inventory, challenges
    )
    store = DurableStore(directory)
    for name, value in (
        ("condition", condition),
        ("implementation", implementation),
        ("configuration", config.as_record()),
        ("validator_invariance", validators),
        ("historical_inventory", old_inventory),
    ):
        store.json(name + ".json", value)
    store.write("design.txt", design_path.read_bytes())
    registrations = []
    repaired = {}
    for challenge in challenges:
        label = challenge["label"]
        store.json(f"challenges/{label}.json", challenge)
        original = challenge["original_request"]
        repaired[label] = publish_update_contract(original)
        order = condition["round_pair_orders"][challenge["round"] - 1]
        for position, arm in enumerate(order):
            request = original if arm == "O" else repaired[label]
            registration = _registration(challenge, condition, arm, position)
            http = render_http_request(
                request, config, session_id=registration["session_id"], attempt_index=0
            )
            require(
                http["body_byte_count"] <= config.maximum_serialized_request_bytes
                and http["input_admission_upper_bound"] <= config.maximum_input_tokens,
                "calibration.precall_request_byte_limit",
            )
            call_label = registration["label"]
            store.json(f"requests/{call_label}.json", request)
            store.json(f"http/{call_label}.json", http)
            store.write(f"http/{call_label}.body.json", http["body_json"].encode())
            registrations.append(registration)
    controls = check_public_rules(repaired)
    store.json("controls.json", controls)
    store.json("registrations.json", registrations)
    report = record(
        "preparation",
        condition_id=condition["id"],
        prepared=True,
        calls=len(registrations),
        provider_calls=0,
        controls_id=controls["id"],
        all_actual_serialized_requests_fit=True,
    )
    store.json("report.json", report)
    seal_directory(
        store, kind="update_calibration_preparation_manifest", preparation_id=report["id"]
    )
    prepared(root, directory)
    return report


def prepared(root: Path, directory: Path) -> dict[str, Any]:
    files = proof._Artifacts(directory)
    implementation = files.json("implementation.json")
    verify_source_snapshot(root, implementation)
    require(
        files.json("validator_invariance.json") == unchanged_validator(root),
        "calibration.validator_readback",
    )
    condition = files.json("condition.json")
    require(
        files.json("configuration.json") == configuration().as_record(),
        "calibration.configuration_frozen",
    )
    require(
        inventory(root / "trusted_data_synthesis/artifacts/qa_vnext_model_execution")
        == read(directory / "historical_inventory.json"),
        "calibration.historical_immutability",
    )
    registrations = read(directory / "registrations.json")
    challenges = historical_challenges(root)
    require(
        condition
        == _condition(
            condition["run_tag"],
            implementation,
            files.raw("design.txt"),
            read(directory / "historical_inventory.json"),
            challenges,
        ),
        "calibration.condition_readback",
    )
    expected_registrations: list[dict[str, Any]] = []
    for challenge in challenges:
        require(
            files.json(f"challenges/{challenge['label']}.json") == challenge,
            "calibration.historical_challenge_readback",
        )
        order = condition["round_pair_orders"][challenge["round"] - 1]
        expected_registrations.extend(
            _registration(challenge, condition, arm, position) for position, arm in enumerate(order)
        )
    require(registrations == expected_registrations, "calibration.registration_readback")
    require(
        len(registrations) == 24 and len({r["session_id"] for r in registrations}) == 24,
        "calibration.fixed_call_population",
    )
    originals = {}
    for reg in registrations:
        challenge = files.json(f"challenges/{reg['pair_label']}.json")
        original = challenge["original_request"]
        originals[reg["pair_label"]] = original
        expected = original if reg["arm"] == "O" else publish_update_contract(original)
        require(
            files.json(f"requests/{reg['label']}.json") == expected,
            "calibration.presentation_only_change",
        )
        http = render_http_request(
            expected, configuration(), session_id=reg["session_id"], attempt_index=0
        )
        require(
            http["body_byte_count"] <= configuration().maximum_serialized_request_bytes
            and http["input_admission_upper_bound"] <= configuration().maximum_input_tokens,
            "calibration.precall_request_byte_limit",
        )
        require(
            files.json(f"http/{reg['label']}.json") == http
            and files.raw(f"http/{reg['label']}.body.json") == http["body_json"].encode(),
            "calibration.actual_http_freeze",
        )
    controls = check_public_rules(
        {label: publish_update_contract(req) for label, req in originals.items()}
    )
    require(files.json("controls.json") == controls, "calibration.control_readback")
    return {
        "condition": condition,
        "registrations": registrations,
        "implementation": implementation,
        "manifest": files.manifest,
    }
