"""Signal callbacks are called directly by CPU mocks; no process receives an OS signal."""

import importlib
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v40_signals")


class Request:
    requested = False
    reason = None

    def request(self, reason="requested"):
        self.requested = True
        self.reason = reason

    def signal_handler(self, signum, _frame):
        self.request(f"signal:{signum}")


def test_legal_sigterm_is_not_ignored_and_sender_is_not_fabricated():
    original = Request()
    audited = subject.AuditedPauseRequest(original, clock=lambda: 100, monotonic=lambda: 20)
    audited.signal_handler(signal.SIGTERM, None)
    assert original.requested and audited.requested
    assert audited.reason == "signal:15"
    evidence = audited.evidence()
    assert evidence["received_signals"] == [
        dict(
            signal_number=15,
            signal_name="SIGTERM",
            received_epoch=100,
            received_monotonic=20,
            sender_identity_available=False,
            sender_pid=None,
            source="python_signal_handler_receipt",
        )
    ]
    assert evidence["sender_attribution"] == "unknown"
    assert evidence["signal_handler_performed_IO"] is False


def test_programmatic_stop_does_not_invent_signal_receipt():
    request = subject.AuditedPauseRequest(Request())
    request.request("original_budget")
    assert request.requested and request.reason == "original_budget"
    assert request.evidence()["received_signals"] == []
    assert request.evidence()["sender_attribution"] == "not_observed"


@pytest.fixture
def fake_signals(monkeypatch):
    handlers = {signal.SIGTERM: object(), signal.SIGINT: object()}
    original = dict(handlers)

    def install(number, handler):
        old = handlers[number]
        handlers[number] = handler
        return old

    fake = SimpleNamespace(
        SIGTERM=signal.SIGTERM,
        SIGINT=signal.SIGINT,
        Signals=signal.Signals,
        signal=install,
        getsignal=handlers.__getitem__,
    )
    monkeypatch.setattr(subject, "signal", fake)
    return fake, handlers, original, install


def test_pause_handler_scope_restores_original_handlers_on_error(fake_signals):
    fake, handlers, original, install = fake_signals
    request = subject.AuditedPauseRequest(Request())
    with pytest.raises(RuntimeError):
        with request.signals():
            handlers[fake.SIGINT](fake.SIGINT, None)
            raise RuntimeError("already stopping")
    assert request.reason == "signal:2" and handlers == original
    assert fake.signal is install


def test_existing_controller_handler_runs_before_receipt_and_sink_outside_callback(fake_signals):
    fake, handlers, original, install = fake_signals
    calls, sinks = [], []

    def prior_stop(signum, _frame):
        calls.append(signum)
        assert sinks == []

    with subject.audit_signal_installations(
        sink=sinks.append, clock=lambda: 100, monotonic=lambda: 20
    ) as audit:
        fake.signal(fake.SIGTERM, prior_stop)
        handlers[fake.SIGTERM](fake.SIGTERM, None)
        assert calls == [15] and sinks == []
        assert audit.evidence()["received_signals"][0]["signal_number"] == 15
    assert len(sinks) == 1 and sinks[0]["sender_attribution"] == "unknown"
    assert handlers == original and fake.signal is install


def test_original_raising_signal_handler_is_not_suppressed(fake_signals):
    fake, handlers, original, install = fake_signals
    sinks = []

    def stop(_signum, _frame):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        with subject.audit_signal_installations(sink=sinks.append):
            fake.signal(fake.SIGINT, stop)
            handlers[fake.SIGINT](fake.SIGINT, None)
    assert sinks[0]["received_signals"][0]["signal_number"] == 2
    assert handlers == original and fake.signal is install
