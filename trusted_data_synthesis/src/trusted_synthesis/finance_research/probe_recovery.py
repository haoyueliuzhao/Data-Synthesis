"""Read-only association of durable Probe episodes with the existing paid ledger.

Never create/reinitialize a database here. This check is for a quiescent collector
at restart or a generation/qualification barrier, not an in-flight status poll.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .contracts import Episode, digest, invocation_identity
from .probe_budget import (
    HARD_CAP_MICROCNY,
    PURPOSE,
    REQUEST_CAP,
    WARNING_MICROCNY,
    ProbePriceSheet,
)
from .providers import _json, parse_tool_calls
from .settlement import episode_is_complete


class ProbeRecoveryError(ValueError):
    """The existing paid evidence cannot safely authorize continuation or freezing."""


def _require(value, message):
    if not value:
        raise ProbeRecoveryError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path):
    return json.loads(Path(path).read_bytes())


def _configuration(connection, plan):
    stored = connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
    _require(stored is not None, "existing paid ledger has no registered configuration")
    stored = json.loads(stored[0])
    sheet = ProbePriceSheet(**plan["price_sheet"])
    output_limit = plan["inventory"]["slot_config"]["max_new_tokens"]
    reservation = sheet.cost_microcny(
        hit=0, miss=sheet.context_input_token_ceiling, output=output_limit
    )
    expected = {
        "run_id": plan["id"],
        "purpose": PURPOSE,
        "price_sheet": asdict(sheet),
        "price_sheet_id": sheet.id,
        "max_output_tokens": output_limit,
        "hard_cap_microcny": HARD_CAP_MICROCNY,
        "warning_microcny": WARNING_MICROCNY,
        "request_cap": REQUEST_CAP,
        "reservation_microcny_per_request": reservation,
    }
    _require(
        all(stored.get(key) == value for key, value in expected.items()),
        "existing paid ledger run/purpose/tariff/output configuration mismatch",
    )
    _require(
        connection.execute("SELECT value FROM metadata WHERE key='halt'").fetchone() is None,
        "halted paid ledger requires explicit disposition, not automatic recovery",
    )
    return sheet, output_limit, reservation


def _validate_turn(connection, *, turn, index, slot_id, plan, sheet, output_limit, reservation):
    metadata = turn.provider_metadata
    coordinates = invocation_identity(
        {"run_id": plan["id"], "episode_id": slot_id, "attempt_index": 1}, turn_index=index
    )
    invocation_id = coordinates["invocation_id"]
    _require(
        metadata.get("budget_invocation_id") == invocation_id
        and metadata.get("budget_coordinates") == coordinates,
        "episode contains a different run/slot/turn/attempt budget invocation",
    )
    harness = metadata.get("harness_invocation", {})
    _require(
        all(harness.get(k) == v for k, v in coordinates.items()),
        "harness and paid invocation coordinates disagree",
    )
    row = connection.execute(
        "SELECT * FROM requests WHERE invocation_id=?", (invocation_id,)
    ).fetchone()
    _require(row is not None, "completed episode has no corresponding paid ledger row")
    _require(
        row["state"] == "SETTLED"
        and row["dispatched_at"] is not None
        and row["response_classification"] == "model_response"
        and type(row["http_status"]) is int
        and 200 <= row["http_status"] < 300,
        "completed episode is not backed by a settled successful service response",
    )
    _require(
        json.loads(row["coordinates_json"]) == coordinates,
        "paid ledger invocation coordinates differ from the completed episode",
    )
    request = metadata.get("public_request")
    _require(isinstance(request, dict), "completed API turn has no original public request")
    request_hash = digest(request)
    _require(
        row["request_sha256"] == metadata.get("request_sha256") == request_hash
        and isinstance(row["request_body"], bytes)
        and _sha(row["request_body"]) == metadata.get("public_request_body_sha256") == request_hash,
        "paid request bytes/hash differ from the completed API turn",
    )
    _require(
        request.get("model") == "deepseek-flash"
        and request.get("thinking") == {"type": "disabled"}
        and request.get("max_tokens") == output_limit
        and request.get("temperature") == 1
        and request.get("top_p") == 1
        and request.get("stream") is False,
        "completed API request differs from the frozen model/decoder contract",
    )
    response_body = row["response_body"]
    raw_response = metadata.get("api_response_raw")
    _require(
        isinstance(response_body, bytes)
        and isinstance(raw_response, str)
        and response_body == raw_response.encode("utf-8")
        and _sha(response_body)
        == row["response_sha256"]
        == metadata.get("raw_api_response_sha256"),
        "paid raw response bytes/hash differ from the completed API turn",
    )
    response = json.loads(response_body)
    _require(
        response == metadata.get("api_response") and response.get("model") == "deepseek-flash",
        "completed API response/model differs from original paid evidence",
    )
    choices = response.get("choices")
    _require(
        isinstance(choices, list) and len(choices) == 1,
        "completed paid API response has no unique original choice",
    )
    message = choices[0]["message"]
    _require(
        turn.receipt is None
        and turn.raw_text == (message.get("content") or "")
        and turn.finish_reason == choices[0].get("finish_reason"),
        "completed turn text/finish differs from the original paid API response",
    )
    try:
        parsed = parse_tool_calls(
            _json({"tool_calls": message.get("tool_calls") or []}), call_prefix=response["id"]
        )
    except (ValueError, TypeError, IndexError, RecursionError):
        parsed = ()
    _require(
        tuple(turn.tool_calls) == parsed,
        "completed parsed tool calls differ from their paid raw response",
    )
    usage = response["usage"]
    counters = sheet.usage(usage, output_limit=output_limit)
    _require(
        json.loads(row["usage_json"]) == usage
        and turn.usage == {key: value for key, value in usage.items() if type(value) is int},
        "episode and paid usage/cache token counts disagree",
    )
    cost = sheet.cost_microcny(
        hit=counters["prompt_cache_hit_tokens"],
        miss=counters["prompt_cache_miss_tokens"],
        output=counters["completion_tokens"],
    )
    _require(
        row["settled_microcny"] == metadata.get("peak_tariff_upper_bound_microcny") == cost
        and row["reserved_microcny"] == metadata.get("budget_reserved_microcny") == reservation
        and metadata.get("price_sheet_id") == sheet.id,
        "completed episode and paid peak-tariff amount/reservation disagree",
    )
    return invocation_id, cost, counters


def validate_ledger_recovery(output, plan, completed=None):
    """Require paid-call/complete-slot conservation without changing any artifacts.

    Fresh output with no slots or seals and no database returns ``None``. Existing
    in-flight/unknown rows, incomplete slots, stale databases, or unclaimed settled
    calls are blocking; no new network call or automatic state repair is performed.
    """
    output = Path(output).resolve()
    database = output / "budget.sqlite3"
    traces = any(
        (output / name).exists()
        for name in ("slots", "generation_seal", "qualification", "inventory_complete")
    )
    if not database.is_file():
        _require(
            not traces and not completed,
            "existing Probe artifacts require their original budget.sqlite3; never reset paid cost",
        )
        return None
    connection = None
    try:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        sheet, output_limit, reservation = _configuration(connection, plan)
        states = list(connection.execute("SELECT invocation_id,state FROM requests"))
        _require(
            all(row["state"] == "SETTLED" for row in states),
            "existing ledger contains pending/unknown calls; automatic recovery is forbidden",
        )
        ledger_ids = {row["invocation_id"] for row in states}
        slots = plan["inventory"]["slots"]
        registered = {slot["slot_id"]: slot for slot in slots}
        _require(len(registered) == len(slots), "registered Probe slot identities are not unique")
        if completed is not None:
            _require(
                isinstance(completed, dict) and set(completed) <= set(registered),
                "completed-slot mapping contains unregistered slots",
            )
        seen, complete_slots, spent = set(), 0, 0
        tokens = {
            key: 0
            for key in (
                "prompt_tokens",
                "prompt_cache_hit_tokens",
                "prompt_cache_miss_tokens",
                "completion_tokens",
            )
        }
        discovered, durable_outcomes = set(), {}
        for slot_id, slot in registered.items():
            directory = output / "slots" / slot_id.split(":", 1)[1]
            if not directory.exists():
                _require(
                    completed is None or slot_id not in completed,
                    "claimed completed slot has no durable slot directory",
                )
                continue
            outcome_path = directory / "outcome" / "record.json"
            episode_path = directory / "episode" / "episode.json"
            _require(
                outcome_path.is_file() and episode_path.is_file(),
                "existing incomplete slot cannot be automatically resampled",
            )
            outcome = _read(outcome_path)
            _require(
                outcome.get("status") == "COMPLETE" and outcome.get("slot") == slot,
                "slot outcome is not the registered complete slot",
            )
            if completed is not None:
                _require(
                    completed.get(slot_id) == outcome,
                    "in-memory completed-slot mapping differs from durable outcomes",
                )
            _require(
                Path(outcome["episode_path"]).resolve() == episode_path,
                "slot outcome points outside its original episode path",
            )
            raw = episode_path.read_bytes()
            _require(
                _sha(raw) == outcome.get("episode_file_sha256"),
                "completed original episode file hash changed",
            )
            episode = Episode.model_validate_json(raw)
            _require(
                digest(episode) == outcome.get("episode_sha256")
                and episode_is_complete(episode)
                and episode.all_provider_calls_settled
                and episode.provider.backend == "deepseek_api"
                and episode.provider.model_id == "deepseek-flash"
                and episode.task_id == slot["task_id"]
                and episode.config.model_dump(mode="json") == plan["inventory"]["slot_config"]
                and episode.actual_model_calls == episode.provider_attempts == len(episode.turns)
                and 0 < len(episode.turns) <= episode.config.max_steps
                and outcome.get("actual_model_calls") == len(episode.turns)
                and outcome.get("all_provider_calls_settled") is True,
                "completed episode identity/configuration/call settlement is inconsistent",
            )
            for index, turn in enumerate(episode.turns):
                invocation_id, amount, usage = _validate_turn(
                    connection,
                    turn=turn,
                    index=index,
                    slot_id=slot_id,
                    plan=plan,
                    sheet=sheet,
                    output_limit=output_limit,
                    reservation=reservation,
                )
                _require(
                    invocation_id not in seen,
                    "one paid invocation was reused by multiple completed turns",
                )
                seen.add(invocation_id)
                spent += amount
                for key in tokens:
                    tokens[key] += usage[key]
            complete_slots += 1
            discovered.add(slot_id)
            durable_outcomes[slot_id] = outcome
        if completed is not None:
            _require(discovered == set(completed), "completed-slot mapping is not conserved")
        _require(
            seen == ledger_ids,
            "settled ledger calls and completed slot calls are not conserved (orphan/missing rows)",
        )
        counters = connection.execute("SELECT * FROM counters WHERE singleton=1").fetchone()
        _require(counters is not None, "existing paid ledger lacks its atomic counters")
        expected_counters = {
            "requests": len(seen),
            "dispatched": len(seen),
            "spent": spent,
            "held": 0,
            "unknown": 0,
            "pending": 0,
            "prompt_tokens": tokens["prompt_tokens"],
            "hit_tokens": tokens["prompt_cache_hit_tokens"],
            "miss_tokens": tokens["prompt_cache_miss_tokens"],
            "completion_tokens": tokens["completion_tokens"],
        }
        _require(
            all(counters[key] == value for key, value in expected_counters.items()),
            "paid ledger counters do not conserve the original completed calls/cost/tokens",
        )
        _require(
            0 <= spent <= HARD_CAP_MICROCNY
            and len(seen)
            <= min(REQUEST_CAP, len(slots) * plan["inventory"]["slot_config"]["max_steps"]),
            "paid evidence exceeds the authorized cost or registered request cap",
        )
        if (output / "generation_seal" / "record.json").exists():
            seal = _read(output / "generation_seal" / "record.json")
            _require(
                seal.get("id") == digest({k: v for k, v in seal.items() if k != "id"})
                and seal.get("protocol_id") == plan["id"]
                and seal.get("complete") is True
                and seal.get("denominator") == len(slots)
                and complete_slots == len(slots)
                and len(seal.get("slots", [])) == len(slots)
                and {row["slot"]["slot_id"]: row for row in seal["slots"]} == durable_outcomes,
                "generation seal is not the full registered paid inventory",
            )
        return {
            "schema": "probe_ledger_recovery_check.v1",
            "protocol_id": plan["id"],
            "completed_slots": complete_slots,
            "registered_slots": len(slots),
            "settled_requests": len(seen),
            "settled_peak_tariff_upper_bound_microcny": spent,
            "actual_usage": tokens,
            "all_paid_calls_bound_to_completed_slots": True,
            "read_only": True,
            "new_model_calls": 0,
        }
    except ProbeRecoveryError:
        raise
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError, IndexError) as error:
        raise ProbeRecoveryError(
            "existing paid evidence is unreadable or inconsistent: " + type(error).__name__
        ) from error
    finally:
        if connection is not None:
            connection.close()
