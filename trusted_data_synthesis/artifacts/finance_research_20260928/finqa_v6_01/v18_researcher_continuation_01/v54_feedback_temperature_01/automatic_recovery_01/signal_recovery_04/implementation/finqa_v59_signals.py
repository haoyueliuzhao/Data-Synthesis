"""Own-experiment SI_USER SIGTERM filtering, with unchanged legal stop paths.

Only the kernel sigwaitinfo receiver makes the filtering decision. It does not
change system policy, permissions, CUDA, scientific resources or STOP handling.
SIGKILL cannot be intercepted; another person using the owner UID is not
distinguishable from the owner. Original bounded receipt/identity logging is
privately reused from the byte-bound control03 implementation.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys

OWNER_UID = 1004
SOURCE_ROOT = Path("/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/signal_recovery_03/implementation")
SOURCE_IMPLEMENTATION_ID = "63525be8d361117a8dd0ee2f10265d9fa97e675da969e622580fadece8060e6f"
SOURCE_SIGNAL_SHA256 = "3c9cdc1133003fa8cd1c2a3324c0443bc471b3695fae73965b4a159376eb2230"
SOURCE_OBSERVER_SHA256 = "1431a463064cf5c0aa0e86a455ae0cf3d9f662ff7142cd953807604406fbc55b"
_OBSERVER = None


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _load_frozen_signals():
    manifest = json.loads((SOURCE_ROOT/"record.json").read_bytes())
    if (manifest.get("id") != SOURCE_IMPLEMENTATION_ID
            or manifest["id"] != _digest({k: v for k, v in manifest.items() if k != "id"})):
        raise RuntimeError("registered control03 signal implementation changed")
    for filename, expected in (("finqa_v58_signals.py", SOURCE_SIGNAL_SHA256),
                               ("finqa_v58_observer.py", SOURCE_OBSERVER_SHA256)):
        if (manifest["files"].get(filename) != expected
                or hashlib.sha256((SOURCE_ROOT/filename).read_bytes()).hexdigest() != expected):
            raise RuntimeError("registered control03 observation source changed: "+filename)
    name = "_v59_frozen03_signals_private"
    spec = importlib.util.spec_from_file_location(name, SOURCE_ROOT/"finqa_v58_signals.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_FROZEN = _load_frozen_signals()
_BASE_POLICY = _FROZEN.signals_policy()


def signals_policy():
    return dict(schema="v59_owner_uid_scoped_sigterm_filter.v1", owner_uid=OWNER_UID,
        owner_must_equal_current_real_nonroot_uid=True, effective_uid_must_equal_owner=True,
        protected_scope="only this process and this experiment's installed observers",
        filtered_signal=int(signal.SIGTERM), required_sender_pid_positive=True,
        filtered_sender_uid_relation="known kernel UID different from owner UID",
        filtered_si_codes=[0], SI_QUEUE_minus_one_is_not_filtered=True,
        decision_source="kernel_sigwaitinfo_only", owner_SIGTERM_dispatches_original_stop=True,
        every_SIGINT_dispatches_original_stop=True, unknown_or_kernel_semantics_dispatch_original_stop=True,
        explicit_STOP_unchanged=True, original_resource_gates_unchanged=True,
        source_implementation_id=SOURCE_IMPLEMENTATION_ID,
        source_signal_sha256=SOURCE_SIGNAL_SHA256, source_observer_sha256=SOURCE_OBSERVER_SHA256,
        observation_policy=dict(_BASE_POLICY), filtered_receipts_include_kernel_fields_and_decision=True,
        logging_failure_does_not_turn_filtered_signal_into_stop=True,
        receipt_persistence_best_effort_under_storage_failure=True,
        no_system_permission_or_configuration_change=True, SIGKILL_capturable=False,
        same_UID_different_people_distinguishable=False)


def signal_decision(number, sender_pid, sender_uid, si_code, *, owner_uid=OWNER_UID):
    """Pure policy; production inputs come directly from sigwaitinfo, not /proc."""
    if owner_uid != OWNER_UID or owner_uid <= 0:
        raise ValueError("V59 signal owner is fixed to registered nonroot UID1004")
    known = (isinstance(number, int) and type(sender_pid) is int and type(sender_uid) is int
             and type(si_code) is int and 0 <= sender_uid < 4294967295)
    filtered = bool(known and number == signal.SIGTERM and sender_pid > 0
                    and sender_uid != owner_uid and si_code == 0)
    return dict(action="FILTER_FOREIGN_UID_SI_USER_SIGTERM" if filtered else "DISPATCH_ORIGINAL_STOP",
        filtered=filtered, dispatch_original_stop=not filtered, owner_uid=owner_uid,
        reason="all registered foreign-UID SI_USER TERM conditions match" if filtered
               else "owner, INT, unknown/kernel semantics or non-admitted signal code")


# Only the private instance's startup policy is redirected. Source bytes and
# public signal modules remain unchanged; inherited handlers/storage stay frozen.
_FROZEN.signals_policy = signals_policy


class SignalObserver(_FROZEN.SignalObserver):
    def __init__(self, directory, *, role, context=None):
        if os.getuid() != OWNER_UID or os.geteuid() != OWNER_UID or OWNER_UID == 0:
            raise RuntimeError("V59 filter only runs as its registered experiment owner UID1004")
        self.receipt_queue_drops = 0
        super().__init__(directory, role=role, context=context)

    def _accept_siginfo(self, info):
        number, sender_pid, sender_uid, code = map(int,
            (info.si_signo, info.si_pid, info.si_uid, info.si_code))
        decision = signal_decision(number, sender_pid, sender_uid, code)
        receipt = dict(schema="v59_received_signal_kernel_receipt.v1", pid=os.getpid(),
            receipt_id=f"{os.getpid()}-{self.time.time_ns()}", role=self.role,
            context=self.context, at_epoch=self.time.time(), signal=number,
            signal_name=signal.Signals(number).name, si_pid=sender_pid, si_uid=sender_uid,
            si_code=code, provenance="kernel_sigwaitinfo", decision=decision,
            receipt_queue_drops_before=self.receipt_queue_drops,
            sender_birth_at_signal_time_known=False, SIGKILL_capturable=False)
        acknowledged = self.threading.Event()
        try:
            self.records.put_nowait((receipt, acknowledged, True))
            if decision["dispatch_original_stop"]:
                acknowledged.wait(timeout=0.05)
        except self.queue.Full:
            self.receipt_queue_drops += 1
        finally:
            if decision["dispatch_original_stop"]:
                self.pending.put(("signal", number))
                os.kill(os.getpid(), signal.SIGUSR2)
        return decision

    def _receive(self):
        while not self.closed.is_set():
            try:
                info = signal.sigtimedwait(self.numbers, 0.2)
            except InterruptedError:
                continue
            except BaseException:
                self.pending.put(("receiver_failure", None))
                os.kill(os.getpid(), signal.SIGUSR2)
                return
            if info is not None:
                try:
                    self._accept_siginfo(info)
                except BaseException:
                    # Unexpected receiver failures must not leave owner stops
                    # masked indefinitely. Ordinary logging failures occur in
                    # the independent writer and never take this path.
                    self.pending.put(("receiver_failure", None))
                    os.kill(os.getpid(), signal.SIGUSR2)
                    return


def install(log_directory, *, role, context=None):
    global _OBSERVER
    if _OBSERVER is not None:
        raise RuntimeError("V59 signal observer already installed")
    _OBSERVER = SignalObserver(log_directory, role=role, context=context)
    return _OBSERVER
