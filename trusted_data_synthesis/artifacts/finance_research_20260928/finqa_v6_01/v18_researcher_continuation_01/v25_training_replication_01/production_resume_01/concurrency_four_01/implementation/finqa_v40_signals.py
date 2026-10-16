"""Audit cooperative stop receipts without doing filesystem or CUDA work in handlers."""

from __future__ import annotations

import signal
import time
from contextlib import contextmanager


class SignalReceipts:
    def __init__(self, *, clock=None, monotonic=None):
        self.clock = time.time if clock is None else clock
        self.monotonic = time.monotonic if monotonic is None else monotonic
        self.receipts = []

    def received(self, signum):
        self.receipts.append(
            dict(
                signal_number=int(signum),
                signal_name=signal.Signals(signum).name,
                received_epoch=self.clock(),
                received_monotonic=self.monotonic(),
                sender_identity_available=False,
                sender_pid=None,
                source="python_signal_handler_receipt",
            )
        )

    def evidence(self):
        return dict(
            received_signals=[dict(receipt) for receipt in self.receipts],
            sender_attribution="unknown" if self.receipts else "not_observed",
            signals_ignored=False,
            automatic_restart=False,
            signal_handler_performed_IO=False,
        )


@contextmanager
def audit_signal_installations(*, sink=None, clock=None, monotonic=None):
    """Observe original callable handlers without changing their stop behavior.

    This process-local scope is for controller/evaluation entry points. Original
    handlers remain responsible for stopping. Receipts are emitted by the caller's
    sink on context exit, outside the signal callback. SIG_DFL/SIG_IGN are not
    reinterpreted and unavailable sender information is never inferred.
    """
    audit = SignalReceipts(clock=clock, monotonic=monotonic)
    installer = signal.signal
    numbers = (signal.SIGTERM, signal.SIGINT)
    previous = {number: signal.getsignal(number) for number in numbers}

    def install(number, handler):
        if number not in numbers or not callable(handler):
            return installer(number, handler)

        def observed(signum, frame):
            try:
                return handler(signum, frame)
            finally:
                audit.received(signum)

        return installer(number, observed)

    signal.signal = install
    try:
        yield audit
    finally:
        signal.signal = installer
        for number, handler in previous.items():
            installer(number, handler)
        if sink is not None and audit.receipts:
            sink(audit.evidence())


class AuditedPauseRequest:
    """Keep legitimate stop behavior; Python signal callbacks cannot identify a sender."""

    def __init__(self, original_request, *, clock=None, monotonic=None):
        self.original = original_request
        self.audit = SignalReceipts(clock=clock, monotonic=monotonic)

    @property
    def receipts(self):
        return self.audit.receipts

    @property
    def requested(self):
        return self.original.requested

    @property
    def reason(self):
        return self.original.reason

    def request(self, reason="requested"):
        return self.original.request(reason)

    def signal_handler(self, signum, frame):
        # Set the original stop flag first. No write, checkpoint, GPU operation,
        # sender attribution, restart or suppression occurs in this callback.
        try:
            self.original.signal_handler(signum, frame)
        finally:
            self.audit.received(signum)

    @contextmanager
    def signals(self, numbers=(signal.SIGTERM, signal.SIGINT)):
        previous = {number: signal.getsignal(number) for number in numbers}
        try:
            for number in numbers:
                signal.signal(number, self.signal_handler)
            yield self
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)

    def evidence(self):
        return dict(
            self.audit.evidence(),
            stop_requested=self.requested,
            stop_reason=self.reason,
        )
