"""Shared bounded pacing around one unchanged DeepSeek POST; never retries.

The outer execution owns/reserves physical-attempt budgets. This helper records
wire entry separately: a prewire circuit rejection is not a real HTTP request.
No credentials, response body, proxy change, user_id change or alternate route.
"""

import json
import math
import threading
import time
import urllib.error
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import cross_market_review_transport_20260927 as transport

base = transport.base
SCRIPT = "trusted_data_synthesis/scripts/cross_market_review_pacing_20260927.py"
MODEL = "deepseek-v4-pro"
STATE_KIND = "cross_market_review_pacing_state"
RATE_HEADERS = (
    "Retry-After",
    "RateLimit",
    "RateLimit-Policy",
    "RateLimit-Limit",
    "RateLimit-Remaining",
    "RateLimit-Reset",
    "X-RateLimit-Limit-Requests",
    "X-RateLimit-Remaining-Requests",
    "X-RateLimit-Reset-Requests",
    "X-RateLimit-Limit-Tokens",
    "X-RateLimit-Remaining-Tokens",
    "X-RateLimit-Reset-Tokens",
)
_REGISTRY_LOCK = threading.Lock()
_SENDERS = {}


class PacingCircuitOpen(RuntimeError):
    """No POST occurs for this exception; an outer reservation is not refunded."""


def require(condition, reason):
    base.require(condition, "review_pacing." + reason)


def epoch(value):
    date = datetime.fromisoformat(value)
    require(date.tzinfo is not None, "timezone_required")
    return date.timestamp()


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def expected_pacing(not_before):
    return dict(
        not_before=iso(epoch(not_before)),
        max_concurrency=4,
        min_start_interval_seconds=2,
        base_cooldown_seconds=300,
        backoff_seconds=[300, 600, 1200, 1200, 1200, 1200],
        maximum_429_events=6,
    )


def safe_headers(headers, key):
    values = {str(name).lower(): str(value) for name, value in (headers.items() if headers else [])}
    result = {}
    for name in RATE_HEADERS:
        if name.lower() not in values:
            continue
        value = values[name.lower()]
        if key and key in value:
            result[name] = dict(value_withheld=True, reason="credential_redacted")
        elif (
            len(value) > 512
            or any(ord(c) < 32 or ord(c) >= 127 for c in value)
            or any(part in value.lower() for part in ("https://", "http://", "bearer "))
        ):
            result[name] = dict(value_withheld=True, reason="unsafe_or_oversized_header")
        else:
            result[name] = dict(value=value, diagnostic_only=True)
    return result


def retry_after_seconds(headers, key, now):
    safe = safe_headers(headers, key).get("Retry-After", {})
    value = safe.get("value")
    if not value:
        return None
    try:
        seconds = float(value)
        if math.isfinite(seconds) and seconds >= 0:
            return seconds
        return None
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return None
            return max(0.0, date.timestamp() - now)
        except (ValueError, TypeError, OverflowError):
            return None


def checked_protocol(reference):
    path = Path(reference["path"])
    require(
        path.is_absolute() and path.resolve().is_relative_to(base.RAW.resolve()),
        "local_registered_protocol",
    )
    require(
        path.stat().st_size == reference["bytes"] and base.sha(path) == reference["sha256"],
        "exact_protocol_reference",
    )
    plan = base.read(path)
    require(
        bool(plan.get("id")) and plan["pacing"] == expected_pacing(plan["pacing"]["not_before"]),
        "fixed_pacing_contract",
    )
    require(plan.get("model", MODEL) == MODEL, "unchanged_registered_model")
    return plan


class _Coordinator:
    def __init__(
        self,
        root,
        reference,
        plan,
        real_sender,
        *,
        clock=time.time,
        monotonic=time.monotonic,
        wait=None,
    ):
        self.root, self.reference, self.plan = Path(root), reference, plan
        require(
            not self.root.is_symlink() and self.root.resolve().is_relative_to(base.RAW.resolve()),
            "confined_pacing_root",
        )
        self.real_sender, self.clock, self.monotonic = real_sender, clock, monotonic
        self.wait = wait if wait is not None else lambda condition, seconds: condition.wait(seconds)
        self.condition = threading.Condition(threading.RLock())
        self.active, self.key = 0, None
        self.last_monotonic = monotonic()
        self.state_path = self.root / "state.json"
        if self.state_path.exists():
            self.state = base.checked(base.read(self.state_path), STATE_KIND)
            require(
                self.state["protocol_reference"] == reference
                and self.state["protocol_id"] == plan["id"],
                "same_persistent_pacing_state",
            )
        else:
            require(
                not any((self.root / "wire_attempts").glob("*/start.json")),
                "missing_state_cannot_reset_existing_wire_budget",
            )
            self.state = dict(
                protocol_id=plan["id"],
                protocol_reference=reference,
                total_429_events=0,
                consecutive_429_since_success=0,
                circuit_open=False,
                cooldown_until=plan["pacing"]["not_before"],
                last_wire_start=None,
                next_serial=1,
            )
            self._persist()

    def _persist(self):
        body = {k: v for k, v in self.state.items() if k not in {"id", "schema_version"}}
        self.state = base.record(STATE_KIND, **body)
        base.write(self.state_path, self.state, immutable=False)

    def _check(self, key=None, model=None):
        if self.state["circuit_open"] or self.state["total_429_events"] >= 6:
            raise PacingCircuitOpen("review_pacing.six_429_events_no_future_POST")
        if model is not None:
            require(model == MODEL, "same_model_no_fallback")
        if key is not None:
            require(isinstance(key, str) and bool(key), "credential_present_not_logged")
            if self.key is None:
                self.key = key
            else:
                require(key == self.key, "credential_change_forbidden_in_pacing_process")

    def preflight(self, key=None, model=None):
        # Called by provider before its old receipt logic whenever possible.
        with self.condition:
            self._check(key, model)

    def _enter(self, payload, key):
        request = json.loads(payload)
        with self.condition:
            self._check(key, request.get("model"))
            while True:
                self._check()
                now = self.clock()
                delay = max(
                    0.0,
                    epoch(self.state["cooldown_until"]) - now,
                    epoch(self.plan["pacing"]["not_before"]) - now,
                    2 - (self.monotonic() - self.last_monotonic),
                )
                if self.state["last_wire_start"] is not None:
                    delay = max(delay, 2 - (now - epoch(self.state["last_wire_start"])))
                if self.active < 4 and delay <= 0:
                    break
                self.wait(self.condition, min(30.0, max(delay, 0.001)) if delay > 0 else 30.0)
            serial = self.state["next_serial"]
            directory = self.root / "wire_attempts" / f"{serial:06d}"
            require(not (directory / "start.json").exists(), "wire_serial_not_reused")
            start = base.record(
                "cross_market_review_wire_start",
                protocol_id=self.plan["id"],
                protocol_reference=self.reference,
                at=iso(now),
                serial=serial,
                endpoint=transport.ENDPOINT,
                model=MODEL,
                request_sha256=base.sha(payload),
                request_bytes=len(payload),
                caller_budget_unchanged=True,
                status="ONE_POST_DISPATCH_ENTERED_OUTCOME_PENDING",
                unsettled_dispatch_is_not_proof_of_received_HTTP=True,
            )
            base.write(directory / "start.json", start)
            self.state["next_serial"] = serial + 1
            self.state["last_wire_start"] = iso(now)
            self._persist()
            self.last_monotonic = self.monotonic()
            self.active += 1
            return directory, start

    def _finish(
        self, directory, start, *, status, http_code=None, headers=None, key=None, error_type=None
    ):
        with self.condition:
            now = self.clock()
            retry_after = retry_after_seconds(headers, key, now) if http_code == 429 else None
            if http_code == 429:
                self.state["total_429_events"] += 1
                self.state["consecutive_429_since_success"] += 1
                index = min(self.state["consecutive_429_since_success"], 6) - 1
                seconds = max(self.plan["pacing"]["backoff_seconds"][index], retry_after or 0)
                self.state["cooldown_until"] = iso(
                    max(epoch(self.state["cooldown_until"]), now + seconds)
                )
                if self.state["total_429_events"] >= 6:
                    self.state["circuit_open"] = True
            elif status == "HTTP_RESPONSE_RETURNED":
                self.state["consecutive_429_since_success"] = 0
            # Never clear an already-observed cooldown because an in-flight call succeeded.
            outcome = base.record(
                "cross_market_review_wire_outcome",
                protocol_id=self.plan["id"],
                start_record_id=start["id"],
                at=iso(now),
                serial=start["serial"],
                status=status,
                HTTP_error_code=http_code,
                error_type=error_type,
                safe_rate_headers=safe_headers(headers, key),
                retry_after_seconds=retry_after,
                total_429_events=self.state["total_429_events"],
                consecutive_429_since_success=self.state["consecutive_429_since_success"],
                cooldown_until=self.state["cooldown_until"],
                circuit_open=self.state["circuit_open"],
                hidden_retries=0,
                response_body_persisted_by_pacer=False,
            )
            try:
                # Persist stop/cooldown before releasing another waiting sender.
                self._persist()
                base.write(directory / "outcome.json", outcome)
            finally:
                self.active -= 1
                self.condition.notify_all()

    def __call__(self, payload, key):
        directory, start = self._enter(payload, key)
        try:
            result = self.real_sender(payload, key)  # Exactly one unchanged underlying POST.
        except urllib.error.HTTPError as error:
            try:
                self._finish(
                    directory,
                    start,
                    status="HTTP_ERROR_RETURNED",
                    http_code=error.code,
                    headers=error.headers,
                    key=key,
                    error_type=type(error).__name__,
                )
            finally:
                error.close()  # Never read or persist the HTTP error body.
            raise
        except BaseException as error:
            self._finish(
                directory,
                start,
                status="TRANSPORT_ERROR_OR_INTERRUPTION",
                key=key,
                error_type=type(error).__name__,
            )
            raise
        self._finish(directory, start, status="HTTP_RESPONSE_RETURNED", key=key)
        return result


def make_sender(root, protocol_reference, real_sender=None):
    """root is an independent state directory under base.RAW, not the worktree.

    Repeated calls in one process share the same lock, semaphore-like active count,
    cooldown and circuit. State survives process restart; the outer controller's
    single-run lock remains responsible for excluding a second controller process.
    """
    root = Path(root).resolve()
    plan = checked_protocol(protocol_reference)
    identity = str(root)
    real_sender = transport.one_post if real_sender is None else real_sender
    with _REGISTRY_LOCK:
        if identity in _SENDERS:
            sender = _SENDERS[identity]
            require(
                sender.reference == protocol_reference and sender.real_sender is real_sender,
                "same_process_shared_pacing_and_route",
            )
            return sender
        sender = _Coordinator(root, protocol_reference, plan, real_sender)
        _SENDERS[identity] = sender
        return sender


def paced_provider_class(old_provider, sender):
    """Keep original provider behavior, adding only a prewire circuit guard/injection."""

    class PacedProvider(old_provider):
        def __init__(self, output, key):
            super().__init__(output, key, sender=sender)

        def __call__(self, request):
            sender.preflight(self.key, request.get("model"))
            return super().__call__(request)

    return PacedProvider
