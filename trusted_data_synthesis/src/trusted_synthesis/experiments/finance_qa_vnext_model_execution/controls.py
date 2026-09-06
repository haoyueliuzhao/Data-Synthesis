"""Explicit offline controls for the online pilot: no network or model samples.

A dedicated adapter_mock Sender returns fixture-derived HTTP envelopes. The
unmodified online transport and public Runtime consume those bytes. These
controls do not patch HttpxSender, inspect credentials, invoke a Provider,
register population sessions, or authorize supervision export.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.runtime import (
    DurableStore,
    PublicQARuntime,
    TaskAdapter,
)

from .models import read_json, record, require, sha
from .plan import TaskPanel, seal_directory
from .qualification import qualify_session
from .representation import export_candidates
from .transport import HTTPResponse, OnlineModelCallback, TransportConfig

Behavior = Literal["complete_branch", "feedback_correction", "empty_content", "wrong_model"]
CONTROL_SPECS: tuple[tuple[str, str, Behavior, int, int], ...] = (
    ("B_complete_17", "B", "complete_branch", 17, 17),
    ("C_feedback_correction", "C", "feedback_correction", 4, 4),
    ("C_empty_content", "C", "empty_content", 1, 0),
    ("C_wrong_model", "C", "wrong_model", 1, 0),
)


class OfflineControlSender:
    """No socket implementation; response bodies are explicitly synthetic."""

    def __init__(self, behavior: Behavior):
        self.behavior = behavior
        self.fixture = PublicFixtureCallback()
        self.calls = 0

    def send(self, request: dict[str, Any], *, api_key: str | None) -> HTTPResponse:
        require(api_key is None, "controls.credentials_forbidden")
        self.calls += 1
        body = read_json(request["body_json"].encode("utf-8"))
        public = read_json(body["messages"][1]["content"].encode("utf-8"))
        content = self.fixture.generate(public).decode("utf-8")
        if self.behavior == "feedback_correction" and self.calls == 1:
            action = read_json(content.encode("utf-8"))
            require(action["kind"] == "action", "controls.first_action")
            action["state_id"] = "offline-control.invalid-current-state"
            content = canonical_json_bytes(action).decode("utf-8")
        if self.behavior == "empty_content":
            content = ""
        envelope = {
            "id": f"offline-control-{self.behavior}-{self.calls}",
            "object": "chat.completion",
            "model": "offline-control-wrong-model"
            if self.behavior == "wrong_model"
            else "deepseek-v4-pro",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
        }
        return HTTPResponse(
            200,
            canonical_json_bytes(envelope),
            headers=(("content-type", "application/json"), ("x-offline-control", "true")),
        )


def _run_control(
    adapter: TaskAdapter,
    directory: Path,
    config: TransportConfig,
    condition: dict[str, Any],
    ordinal: int,
    spec: tuple[str, str, Behavior, int, int],
) -> dict[str, Any]:
    name, group, behavior, expected_attempts, expected_submissions = spec
    store = DurableStore(directory)
    registration = record(
        "session_registration",
        session_id="qa_vnext_offline_control:" + name,
        label=name,
        ordinal=ordinal,
        round=0,
        task_group=group,
        task_type=adapter.context["task_type"],
        task_id=adapter.context["task_id"],
        context_id=adapter.context["id"],
        protocol_id=contract()["id"],
        registry_hash=strict_canonical_hash(adapter.registry.manifest()),
        model_configuration_id=config.as_record()["id"],
        run_condition_id=condition["id"],
        maximum_actions=12,
        maximum_submissions=32,
        maximum_provider_attempts=32,
        replacement_allowed=False,
        reference_route=None,
        independent_initial_state=True,
        offline_control=True,
        registered_model_population_member=False,
    )
    start = record(
        "session_start",
        status="started",
        reason="explicit adapter_mock offline control; no real Provider request",
        session_id=registration["session_id"],
        registered_id=registration["id"],
    )
    store.json("registration.json", registration)
    store.json("start.json", start)
    sender = OfflineControlSender(behavior)
    callback = OnlineModelCallback(
        config,
        session_id=registration["session_id"],
        evidence_directory=directory / "transport",
        sender=sender,
    )
    session = PublicQARuntime(
        adapter, callback, directory / "runtime", max_actions=12, max_submissions=32
    ).run()
    ledger = callback.finalize()
    qualification = qualify_session(
        adapter,
        registration,
        session,
        directory / "runtime",
        directory / "transport",
        start_record=start,
    )
    export = export_candidates(session, qualification, directory / "transport")
    store.json("qualification.json", qualification)
    store.json("export.json", export)
    measurements = []
    for row in [*ledger["attempts"], *ledger["stops"]]:
        paths = row["paths"]
        request = read_json((directory / "transport" / paths["http_request"]).read_bytes())
        raw = (directory / "transport" / paths["http_request_body"]).read_bytes()
        public = read_json((directory / "transport" / paths["public_request"]).read_bytes())
        measurements.append(
            {
                "http_request_id": request["id"],
                "public_runtime_state_id": public["state"]["id"],
                "body_byte_count": len(raw),
                "body_sha256": sha(raw),
                "input_admission_upper_bound": len(raw) + config.input_overhead_allowance,
                "untruncated_current_public_request": (
                    raw == canonical_json_bytes(request["body"])
                    and request["body"]["messages"][1]["content"].encode("utf-8")
                    == canonical_json_bytes(public)
                    and len(raw) == request["body_byte_count"]
                    and sha(raw) == request["body_sha256"]
                ),
                "within_serialized_body_cap": len(raw) < config.maximum_serialized_request_bytes,
                "within_input_admission_allowance": (
                    len(raw) + config.input_overhead_allowance < config.maximum_input_tokens
                ),
            }
        )
    audit = qualification.get("domain_audit") or {}
    checks = {
        "explicit_mock_sender": (
            callback.binding["origin"] == "adapter_mock"
            and callback.binding["transport_kind"] == "adapter_mock"
            and callback.binding["sender_implementation"]["class"] == "OfflineControlSender"
        ),
        "independent_evidence_complete": qualification["evidence_complete"] is True,
        "independent_trajectory_valid": qualification["trajectory_valid"] is True,
        "independent_domain_validation": audit.get("validation_passed") is True,
        "control_origin_recognized": qualification["control_evidence"] is True,
        "not_model_qualified": (
            qualification["model_origin_verified"] is False
            and qualification["qualified"] is False
            and qualification["export_eligible"] is False
        ),
        "zero_supervision_export": export["candidate_count"] == 0 and export["rows"] == [],
        "expected_mock_attempt_count": (
            ledger["provider_attempt_count"] == sender.calls == expected_attempts
        ),
        "expected_runtime_submission_count": len(session["events"]) == expected_submissions,
        "full_unchanged_http_requests_fit_control_allowance": bool(measurements)
        and all(
            row["untruncated_current_public_request"]
            and row["within_serialized_body_cap"]
            and row["within_input_admission_allowance"]
            for row in measurements
        ),
        "runtime_did_not_repair_public_responses": all(
            event["submission"]["host_repairs"] == []
            and event["receipt"]["no_host_semantic_repair"] is True
            for event in session["events"]
        ),
    }
    if behavior in {"complete_branch", "feedback_correction"}:
        checks["complete_domain_success"] = (
            audit.get("qualified") is True
            and qualification["qa_valid"] is True
            and session["final"] is not None
            and qualification["depth_scope"] == "complete_session"
            and "callback_stop" not in session
        )
    if behavior == "feedback_correction" and len(session["events"]) >= 2:
        first, second = session["events"][:2]
        intended = read_json(PublicFixtureCallback().generate(first["request"]))
        intended["state_id"] = "offline-control.invalid-current-state"
        first_bytes = (
            directory / "transport" / ledger["attempts"][0]["paths"]["public_content"]
        ).read_bytes()
        second_bytes = (
            directory / "transport" / ledger["attempts"][1]["paths"]["public_content"]
        ).read_bytes()
        checks["only_initial_state_id_was_invalid"] = (
            first_bytes == canonical_json_bytes(intended)
            and first["parsed"] == intended
            and first["receipt"]["admitted"] is False
            and first["receipt"]["error_code"] == "admission.current_state"
        )
        checks["new_callback_uses_feedback_and_new_state"] = (
            second["request"]["state"]["id"] != first["request"]["state"]["id"]
            and second["request"]["state"]["last_feedback"]["admitted"] is False
            and second["receipt"]["admitted"] is True
            and second_bytes == PublicFixtureCallback().generate(second["request"])
            and second["submission"]["id"] != first["submission"]["id"]
        )
    if behavior in {"empty_content", "wrong_model"}:
        expected_code = (
            "provider.no_public_content"
            if behavior == "empty_content"
            else "provider.model_identity_mismatch"
        )
        stop = session.get("callback_stop") or {}
        outcome = callback.last_outcome or {}
        checks["typed_stop_without_fabricated_submission"] = (
            stop.get("reason") == expected_code
            and stop.get("external_evidence_id") == outcome.get("id")
            and stop.get("exception_type") == "OnlineTransportError"
            and outcome.get("public_content_returned_to_runtime") is False
            and not session["events"]
            and not any((directory / "runtime" / "turns").glob("*_submission.json"))
            and not any((directory / "runtime" / "turns").glob("*_receipt.json"))
        )
        checks["prefix_domain_audit_retained"] = (
            session["final"] is None
            and qualification["status"] == "known_failure"
            and qualification["qa_valid"] is None
            and qualification["depth_scope"] == "reached_prefix"
            and qualification["terminal_outcome_id"] == outcome.get("id")
            and audit.get("evidence_complete") is True
        )
    result = record(
        "offline_control",
        name=name,
        task_group=group,
        behavior=behavior,
        passed=all(checks.values()),
        checks=checks,
        registration_id=registration["id"],
        registered_session_id=registration["session_id"],
        session_id=session["id"],
        qualification_id=qualification["id"],
        domain_audit_id=qualification["domain_audit_id"],
        export_id=export["id"],
        transport_ledger_id=ledger["id"],
        transport_kind="adapter_mock",
        provider_attempts=0,
        population_sessions=0,
        mock_attempts=ledger["provider_attempt_count"],
        runtime_submissions=len(session["events"]),
        exported_candidates=export["candidate_count"],
        request_measurements=measurements,
        maximum_actual_http_body_bytes=max(
            (row["body_byte_count"] for row in measurements), default=0
        ),
        maximum_input_admission_proxy=max(
            (row["input_admission_upper_bound"] for row in measurements), default=0
        ),
        future_requests_still_require_per_attempt_guard=True,
    )
    store.json("report.json", result)
    seal_directory(store, kind="offline_control_manifest", control_id=result["id"])
    return result


def run_controls(panel: TaskPanel, directory: Path, config: TransportConfig) -> dict[str, Any]:
    """Run the four fixed local G0 controls, never the twelve-model population."""
    store = DurableStore(directory)
    condition = record(
        "offline_control_condition",
        model_configuration_id=config.as_record()["id"],
        control_names=[spec[0] for spec in CONTROL_SPECS],
        origin="adapter_mock",
        provider_attempts=0,
        population_sessions=0,
        maximum_actions=12,
        maximum_submissions=32,
        maximum_mock_attempts_per_control=32,
        no_live_sender_patching=True,
        credentials_read=False,
        no_model_or_population_success_claim=True,
    )
    store.json("condition.json", condition)
    jobs = [
        (panel.adapter(spec[1]), directory / spec[0], config, condition, ordinal, spec)
        for ordinal, spec in enumerate(CONTROL_SPECS)
    ]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(_run_control, *job) for job in jobs]
        controls = [future.result() for future in futures]
    result = record(
        "offline_controls",
        condition_id=condition["id"],
        passed=all(control["passed"] for control in controls),
        control_count=len(controls),
        controls=controls,
        provider_attempts=0,
        population_sessions=0,
        mock_attempts=sum(control["mock_attempts"] for control in controls),
        runtime_submissions=sum(control["runtime_submissions"] for control in controls),
        exported_candidates=sum(control["exported_candidates"] for control in controls),
        maximum_actual_http_body_bytes=max(
            control["maximum_actual_http_body_bytes"] for control in controls
        ),
        maximum_input_admission_proxy=max(
            control["maximum_input_admission_proxy"] for control in controls
        ),
        observed_request_fit_does_not_prove_all_future_requests_fit=True,
        future_requests_still_require_per_attempt_guard=True,
        input_admission_proxy_is_exact_provider_tokens=False,
        student_parameter_loads=0,
        student_forward_calls=0,
        student_parameter_updates=0,
        gpu_jobs=0,
    )
    store.json("report.json", result)
    seal_directory(store, kind="offline_controls_manifest", report_id=result["id"])
    return result
