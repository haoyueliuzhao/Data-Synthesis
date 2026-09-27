"""Virtual-time/injected-wire tests; no real HTTP, key read or cooldown sleep."""

import io
import threading
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import format_datetime

import cross_market_review_pacing_20260927 as m
import pytest

KEY = "SYNTHETIC_NOT_A_REAL_API_KEY"


class Clock:
    def __init__(self):
        self.wall = m.epoch("2026-09-27T01:56:33.973906+00:00")
        self.elapsed = 0.0
        self.waits = []

    def time(self):
        return self.wall + self.elapsed

    def monotonic(self):
        return self.elapsed

    def wait(self, condition, seconds):
        assert 0 < seconds <= 30
        self.waits.append(seconds)
        self.elapsed += seconds


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    clock = Clock()
    plan = m.base.record(
        "synthetic_pacing_protocol",
        model=m.MODEL,
        pacing=m.expected_pacing(m.iso(clock.time() + 300)),
    )
    path = tmp_path / "protocol.json"
    m.base.write(path, plan)
    reference = dict(path=str(path), bytes=path.stat().st_size, sha256=m.base.sha(path))
    return dict(root=tmp_path / "pacing", clock=clock, plan=plan, reference=reference)


def coordinator(case, sender):
    clock = case["clock"]
    return m._Coordinator(
        case["root"],
        case["reference"],
        case["plan"],
        sender,
        clock=clock.time,
        monotonic=clock.monotonic,
        wait=clock.wait,
    )


def payload(model=m.MODEL):
    return m.base.encode(dict(model=model, marker="original unchanged source bytes"))


def test_exact_pacing_policy_and_initial_not_before_without_real_sleep(case):
    calls = []
    sender = coordinator(case, lambda body, key: calls.append((case["clock"].time(), body, key)))
    sender(payload(), KEY)
    assert len(calls) == 1 and calls[0][0] == m.epoch(case["plan"]["pacing"]["not_before"])
    assert calls[0][1:] == (payload(), KEY)
    assert case["clock"].waits == [30.0] * 10
    assert m.expected_pacing(case["plan"]["pacing"]["not_before"]) == case["plan"]["pacing"]


def test_successive_wire_starts_have_at_least_two_seconds(case):
    starts = []
    sender = coordinator(case, lambda *_: starts.append(case["clock"].time()))
    for _ in range(4):
        sender(payload(), KEY)
    assert all(b - a >= 2 for a, b in zip(starts, starts[1:], strict=False))
    assert len(list((case["root"] / "wire_attempts").glob("*/start.json"))) == 4
    assert len(list((case["root"] / "wire_attempts").glob("*/outcome.json"))) == 4


def test_429_backoff_300_600_1200_and_six_event_persistent_circuit(case):
    calls = []

    def wire(body, key):
        calls.append(case["clock"].elapsed)
        raise urllib.error.HTTPError(m.transport.ENDPOINT, 429, "rate limited", {}, None)

    sender = coordinator(case, wire)
    for _ in range(6):
        with pytest.raises(urllib.error.HTTPError):
            sender(payload(), KEY)
    assert calls == [300, 600, 1200, 2400, 3600, 4800]
    assert sender.state["total_429_events"] == 6 and sender.state["circuit_open"]
    with pytest.raises(m.PacingCircuitOpen):
        sender(payload(), KEY)
    assert len(calls) == 6
    restored = coordinator(case, lambda *_: pytest.fail("restart must not reset circuit"))
    with pytest.raises(m.PacingCircuitOpen):
        restored(payload(), KEY)
    assert len(list((case["root"] / "wire_attempts").glob("*/start.json"))) == 6


def test_longer_retry_after_is_respected_and_success_does_not_clear_cooldown(case):
    calls = []

    def wire(body, key):
        calls.append(case["clock"].elapsed)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                m.transport.ENDPOINT, 429, "limited", {"Retry-After": "900"}, None
            )
        return b"body", "request"

    sender = coordinator(case, wire)
    with pytest.raises(urllib.error.HTTPError):
        sender(payload(), KEY)
    deadline = sender.state["cooldown_until"]
    sender(payload(), KEY)
    assert calls == [300, 1200]
    assert sender.state["cooldown_until"] == deadline
    assert sender.state["total_429_events"] == 1
    assert sender.state["consecutive_429_since_success"] == 0


def test_retry_after_HTTP_date_and_invalid_values(case):
    now = case["clock"].time()
    date = format_datetime(datetime.fromtimestamp(now + 901, timezone.utc), usegmt=True)
    assert 900 <= m.retry_after_seconds({"retry-after": date}, KEY, now) <= 901
    for value in ("NaN", "inf", "-20", "not a date", KEY):
        assert m.retry_after_seconds({"Retry-After": value}, KEY, now) is None


def test_error_headers_are_whitelisted_key_redacted_and_body_never_read(case):
    class NeverRead(io.BytesIO):
        def read(self, *_):
            pytest.fail("HTTP error body must not be read")

    body = NeverRead(b"sensitive error body " + KEY.encode())

    def wire(*_):
        raise urllib.error.HTTPError(
            m.transport.ENDPOINT,
            429,
            KEY,
            {
                "Retry-After": "300",
                "RateLimit": KEY,
                "RateLimit-Policy": '"policy";q=500',
                "Authorization": "Bearer " + KEY,
                "Set-Cookie": "secret",
                "X-RateLimit-Reset-Requests": "300\r\nSecret:yes",
            },
            body,
        )

    sender = coordinator(case, wire)
    with pytest.raises(urllib.error.HTTPError):
        sender(payload(), KEY)
    records = "".join(p.read_text() for p in case["root"].rglob("*.json") if p.is_file())
    assert KEY not in records and "sensitive error body" not in records
    assert "Authorization" not in records and "Set-Cookie" not in records
    outcome = m.base.read(next((case["root"] / "wire_attempts").glob("*/outcome.json")))
    assert outcome["HTTP_error_code"] == 429 and outcome["hidden_retries"] == 0
    assert outcome["safe_rate_headers"]["RateLimit"]["value_withheld"]
    assert body.closed


def test_timeout_is_one_wire_call_without_429_backoff_or_hidden_retry(case):
    calls = []

    def wire(*_):
        calls.append(True)
        raise TimeoutError(KEY)

    sender = coordinator(case, wire)
    with pytest.raises(TimeoutError):
        sender(payload(), KEY)
    assert len(calls) == 1 and sender.active == 0 and sender.state["total_429_events"] == 0
    assert KEY not in "".join(p.read_text() for p in case["root"].rglob("*.json") if p.is_file())


def test_key_or_model_change_rejected_before_wire(case):
    calls = []
    sender = coordinator(case, lambda *_: calls.append(True))
    sender(payload(), KEY)
    with pytest.raises(ValueError, match="credential_change"):
        sender(payload(), "OTHER_SYNTHETIC_KEY")
    with pytest.raises(ValueError, match="same_model"):
        sender(payload("deepseek-flash"), KEY)
    assert len(calls) == 1


def test_provider_preflight_circuit_rejection_does_not_mint_old_physical_receipt(case):
    sender = coordinator(case, lambda *_: pytest.fail("no wire"))
    sender.state["circuit_open"] = True
    calls = []

    class OldProvider:
        def __init__(self, output, key, sender):
            self.key, self.sender = key, sender

        def __call__(self, request):
            calls.append("old provider would write a physical receipt")

    provider = m.paced_provider_class(OldProvider, sender)(case["root"], KEY)
    with pytest.raises(m.PacingCircuitOpen):
        provider({"model": m.MODEL})
    assert not calls and not list((case["root"] / "wire_attempts").glob("*/start.json"))


def test_make_sender_shares_coordinator_and_rejects_changed_protocol(case):
    def wire(*_):
        pytest.fail("factory must not send")

    first = m.make_sender(case["root"], case["reference"], wire)
    second = m.make_sender(case["root"], case["reference"], wire)
    assert first is second
    bad = dict(case["reference"], sha256="f" * 64)
    with pytest.raises(ValueError, match="exact_protocol_reference"):
        m.make_sender(case["root"], bad, wire)


def test_no_more_than_four_concurrent_real_sender_calls(case):
    clock = case["clock"]

    def wait(condition, seconds):
        clock.elapsed += seconds
        condition.wait(timeout=0.002)

    lock = threading.Lock()
    release, reached_four = threading.Event(), threading.Event()
    running, maximum, calls = 0, 0, 0

    def wire(*_):
        nonlocal running, maximum, calls
        with lock:
            running += 1
            calls += 1
            maximum = max(maximum, running)
            if running == 4:
                reached_four.set()
        assert release.wait(timeout=5)
        with lock:
            running -= 1
        return b"ok", None

    sender = m._Coordinator(
        case["root"],
        case["reference"],
        case["plan"],
        wire,
        clock=clock.time,
        monotonic=clock.monotonic,
        wait=wait,
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(sender, payload(), KEY) for _ in range(8)]
        assert reached_four.wait(timeout=3)
        assert calls == maximum == 4
        release.set()
        assert all(f.result(timeout=5) == (b"ok", None) for f in futures)
    assert calls == 8 and maximum == 4 and sender.active == 0
