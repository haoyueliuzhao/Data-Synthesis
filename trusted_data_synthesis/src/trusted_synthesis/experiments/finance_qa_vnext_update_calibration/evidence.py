"""Independent one-attempt HTTP proof and read-only Update score, no Runtime run."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.domains.finance.qa_vnext.runtime import evaluate_update_readonly
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification as proof
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import sha
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    SOURCE_RELATIVE_PATH,
)

from .models import configuration, record


def audit_call(
    root: Path,
    directory: Path,
    registration: dict[str, Any],
    public: dict[str, Any],
    expected_http: dict[str, Any],
    *,
    require_live: bool = True,
) -> dict[str, Any]:
    """Raises on missing/inconsistent evidence; callers retain this as unknown, never false."""
    files = proof._Artifacts(directory)
    config = files.json("config.json")
    binding = files.json("binding.json")
    ledger = files.json("ledger.json")
    require(config == configuration().as_record(), "calibration.actual_config")
    proof._configuration(config, registration)
    session_id = registration["session_id"]
    require(
        binding["session_id"] == ledger["session_id"] == files.manifest["session_id"] == session_id
        and binding["model_configuration_id"] == ledger["model_configuration_id"] == config["id"]
        and ledger["callback_binding_id"] == binding["id"]
        and files.manifest["ledger_id"] == ledger["id"],
        "calibration.transport_parents",
    )
    source = (root / SOURCE_RELATIVE_PATH).read_bytes()
    module = "trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport"
    require(
        binding["implementation"]
        == {
            "module": module,
            "class": "OnlineModelCallback",
            "method": "generate",
            "source_relative_path": SOURCE_RELATIVE_PATH,
            "source_sha256": sha(source),
            "source_byte_count": len(source),
        },
        "calibration.transport_source",
    )
    require(
        binding["host_semantic_field_fill"] is False
        and binding["automatic_retries"] == binding["model_fallbacks"] == 0
        and binding["model_origin_requires_attempt_response_evidence"] is True
        and ledger["transport_kind"] == binding["transport_kind"],
        "calibration.no_hidden_repair",
    )
    live = binding["origin"] == "model" and binding["transport_kind"] == "live_http"
    if require_live:
        require(live, "calibration.live_http_required")
    if live:
        require(
            binding["sender_implementation"]
            == {
                "module": module,
                "class": "HttpxSender",
                "method": "send",
                "httpx_version": importlib.metadata.version("httpx"),
            },
            "calibration.sender_source",
        )
    require(
        len(ledger["attempts"]) == ledger["provider_attempt_count"] == 1
        and ledger["stops"] == []
        and ledger["reserved_tokens"] == 107520,
        "calibration.exactly_one_attempt",
    )
    row = ledger["attempts"][0]
    turn = registration["historical_update_turn"]
    require(
        row["attempt_index"] == 0 and row["turn_index"] == turn,
        "calibration.attempt_vs_historical_turn",
    )
    paths = {key: path for key, path in row["paths"].items() if path is not None}
    require(
        set(files.files) == {"config.json", "binding.json", "ledger.json"} | set(paths.values()),
        "calibration.exact_evidence_members",
    )
    actual_public, http, body = proof._http_request(files, paths, registration, config, turn, 0)
    require(
        actual_public == public
        and http == expected_http
        and body == expected_http["body_json"].encode()
        and sha(canonical_json_bytes(public)) == registration["public_request_sha256"],
        "calibration.frozen_actual_request",
    )
    reservation = files.json(paths["reservation"])
    parents = {
        key: http[key]
        for key in (
            "session_id",
            "attempt_index",
            "turn_index",
            "public_request_id",
            "public_runtime_state_id",
            "context_id",
            "task_id",
            "protocol_id",
            "model_configuration_id",
        )
    }
    parents.update(http_request_id=http["id"], callback_binding_id=binding["id"])
    expected = {
        **parents,
        "reserved_tokens": 107520,
        "session_reserved_tokens_after": 107520,
        "attempt_consumed": True,
        "reserved_before_send": True,
    }
    require(
        all(reservation[key] == value for key, value in expected.items()),
        "calibration.reservation_parents",
    )
    journal = ledger["write_events"]
    require(
        files.manifest["write_events"]
        == journal
        + [
            {"kind": "file_fsync", "path": "ledger.json"},
            {"kind": "directory_fsync", "path": "ledger.json"},
        ],
        "calibration.manifest_journal",
    )
    proof._whole_journal(files, ledger)
    proof._reservation_order(journal, paths, http, reservation)
    outcome = files.json(paths["outcome"])
    require(row["outcome_id"] == outcome["id"], "calibration.outcome_ledger")
    expected = {
        **parents,
        "reservation_id": reservation["id"],
        "transport_kind": binding["transport_kind"],
        "provider_attempt_consumed": True,
        "automatic_retries": 0,
        "host_repairs": [],
    }
    require(
        all(outcome[key] == value for key, value in expected.items()), "calibration.outcome_parents"
    )
    content, checks, model = proof._response(
        files, paths, http, reservation, outcome, config, journal
    )
    evaluation = evaluate_update_readonly(content, public) if content is not None else None
    # Condition deviations are retained, not replaced. Semantic score remains separately visible.
    accepted = evaluation is not None and evaluation["complete_accept"] and all(checks.values())
    return record(
        "call_audit",
        registration_id=registration["id"],
        label=registration["label"],
        pair_label=registration["pair_label"],
        arm=registration["arm"],
        task_group=registration["task_group"],
        shape=registration["shape"],
        evidence_complete=True,
        model_origin_verified=live,
        provider_attempts=1,
        transport_manifest_id=files.manifest["id"],
        provider_outcome_id=outcome["id"],
        observed_model=model,
        condition_checks=checks,
        condition_flags=outcome["condition_flags"],
        usage=outcome["usage"],
        outcome_status=outcome["status"],
        outcome_code=outcome["code"],
        evaluation=evaluation,
        Y=bool(accepted),
        readonly=True,
        host_repairs=[],
        action_executions=0,
        update_commits=0,
        model_sample=live,
        implementation_failure=outcome["code"]
        in {
            "transport.unclassified_failure",
            "transport.credential_unavailable",
        },
    )


def summarize(
    registrations: list[dict[str, Any]], audits: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    require(
        len(registrations) == 24 and set(audits) == {r["label"] for r in registrations},
        "calibration.summary_fixed_population",
    )
    by_pair: dict[str, dict[str, Any]] = {}
    for reg in registrations:
        by_pair.setdefault(reg["pair_label"], {})[reg["arm"]] = audits[reg["label"]]["Y"]

    def rates(selected: list[dict[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for arm in ("O", "R"):
            values = [audits[r["label"]]["Y"] for r in selected if r["arm"] == arm]
            result[arm] = {
                "denominator": len(values),
                "successes": values.count(True),
                "known_failures": values.count(False),
                "unknown_or_not_started": values.count(None),
                "rate": sum(values) / len(values) if values and None not in values else None,
            }
        result["delta_R_minus_O"] = (
            result["R"]["rate"] - result["O"]["rate"]
            if result["R"]["rate"] is not None and result["O"]["rate"] is not None
            else None
        )
        return result

    cells = {"R_only": 0, "O_only": 0, "both": 0, "neither": 0, "unknown": 0}
    for pair in by_pair.values():
        cell = (
            "unknown"
            if None in pair.values()
            else "both"
            if pair["O"] and pair["R"]
            else "O_only"
            if pair["O"]
            else "R_only"
            if pair["R"]
            else "neither"
        )
        cells[cell] += 1
    main = rates(registrations)
    groups = {
        group: rates([r for r in registrations if r["task_group"] == group]) for group in "CBS"
    }
    shapes = {
        shape: rates([r for r in registrations if r["shape"] == shape])
        for shape in sorted({r["shape"] for r in registrations})
    }
    complete = all(a["evidence_complete"] for a in audits.values())
    gate = (
        complete
        and main["R"]["successes"] >= 10
        and all(groups[group]["R"]["successes"] >= 3 for group in "CBS")
    )
    return record(
        "summary",
        fixed_pairs=12,
        fixed_calls=24,
        overall=main,
        paired_cells=cells,
        by_task_group=groups,
        by_proposition_shape=shapes,
        execution_evidence_complete=complete,
        engineering_gate_passed=gate,
        statistical_lower_bound_claimed=False,
        whole_session_success_not_measured=True,
        feedback_correction_effect_not_measured=True,
        historical_q_unchanged="1/12",
        action_executions=0,
        update_commits=0,
        qualified_training_rows=0,
        student_jobs=0,
    )
