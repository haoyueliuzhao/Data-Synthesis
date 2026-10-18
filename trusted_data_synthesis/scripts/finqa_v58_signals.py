"""Kernel-first, bounded-delay signal observations; legal stops stay effective."""
import os
import signal
import sys

_OBSERVER = None


def signals_policy():
    return dict(schema="v58_kernel_first_signal_observation.v1",
        captured_signals=[int(signal.SIGTERM), int(signal.SIGINT)],
        minimal_kernel_receipt_before_proc_reads=True, minimal_receipt_fsync=True,
        maximum_receipt_wait_before_original_stop_seconds=0.05,
        storage_failure_or_stall_never_suppresses_stop=True,
        enrichment_after_successful_receipt_fsync=True, parent_depth=3,
        receipt_and_proc_observation_timestamps_separate=True,
        original_stop_handler_runs_on_main_thread=True, SIGUSR2_reserved_for_dispatch=True,
        signal_log_file_max_bytes=16*1024**2, signal_log_file_total_count=4,
        pending_telemetry_max_events=64, SIGKILL_capturable=False,
        environment_argv_credentials_history_read=False,
        kernel_sender_birth_unknown=True, proc_cache_does_not_prove_sender_identity=True)


class SignalObserver:
    def __init__(self, directory, *, role, context=None):
        self.numbers = {signal.SIGTERM, signal.SIGINT}
        self.previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, self.numbers)
        try:
            import queue
            import threading
            import time
            from pathlib import Path
            import importlib.util
            # Bind the adjacent frozen monitoring helper before scientific
            # path configuration can give workspace scripts import precedence.
            helper_path = Path(__file__).resolve().with_name("finqa_v58_observer.py")
            spec = importlib.util.spec_from_file_location("_v58_bound_signal_observer", helper_path)
            helper = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = helper
            spec.loader.exec_module(helper)
            if threading.current_thread() is not threading.main_thread() or threading.active_count() != 1:
                raise RuntimeError("signal observer must precede other threads")
            if "torch" in sys.modules or signal.getsignal(signal.SIGUSR2) != signal.SIG_DFL:
                raise RuntimeError("signal observer must precede torch and own unused SIGUSR2")
            self.queue, self.threading, self.time = queue, threading, time
            self.parent_chain, self.cgroup_snapshot = helper.parent_chain, helper.cgroup_snapshot
            self.pending, self.records = queue.SimpleQueue(), queue.Queue(maxsize=64)
            self.closed = threading.Event()
            self.role, self.context = str(role), dict(context or {})
            self.log = helper.RotatingJSONLog(Path(directory)/"received.jsonl")
            self.wakeup_handler = signal.signal(signal.SIGUSR2, self._dispatch)
            self.writer = threading.Thread(target=self._write_loop, daemon=True, name="v58-signal-writer")
            self.receiver = threading.Thread(target=self._receive, daemon=True, name="v58-signal-receiver")
            self.writer.start()
            self.receiver.start()
            self.records.put_nowait((dict(schema="v58_signal_observer_started.v1", pid=os.getpid(),
                role=self.role, context=self.context, at_epoch=time.time(), policy=signals_policy()), None, False))
        except BaseException:
            if hasattr(self, "wakeup_handler"):
                signal.signal(signal.SIGUSR2, self.wakeup_handler)
            signal.pthread_sigmask(signal.SIG_SETMASK, self.previous_mask)
            raise

    def _write_loop(self):
        while not self.closed.is_set():
            try:
                record, acknowledged, enrich = self.records.get(timeout=0.2)
            except self.queue.Empty:
                continue
            durable = False
            try:
                self.log.append(record, durable=True)
                durable = True
            except BaseException:
                pass
            finally:
                if acknowledged is not None:
                    acknowledged.set()
            if durable and enrich:
                try:
                    sender = self.parent_chain(record["si_pid"], depth=3)
                    receiver = self.parent_chain(os.getpid(), depth=3)
                    cgroups = [dict(pid=row["pid"], values=self.cgroup_snapshot(row))
                        for chain in (sender, receiver) for row in chain["processes"]
                        if row["identity_consistent"]]
                    self.log.append(dict(schema="v58_received_signal_identity_enrichment.v1",
                        receipt_id=record["receipt_id"], receipt_at_epoch=record["at_epoch"],
                        observed_at_epoch=self.time.time(), pid=os.getpid(), role=self.role,
                        kernel_receipt_fsynced_before_proc_reads=True,
                        sender_parent_chain=sender, receiver_parent_chain=receiver, cgroups=cgroups,
                        identities_are_post_signal_observations=True), durable=True)
                except BaseException:
                    pass
            self.records.task_done()

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
            if info is None:
                continue
            number = int(info.si_signo)
            receipt = dict(schema="v58_received_signal_kernel_receipt.v1", pid=os.getpid(),
                receipt_id=f"{os.getpid()}-{self.time.time_ns()}", role=self.role,
                context=self.context, at_epoch=self.time.time(), signal=number,
                signal_name=signal.Signals(number).name, si_pid=int(info.si_pid),
                si_uid=int(info.si_uid), si_code=int(info.si_code), provenance="kernel_sigwaitinfo",
                sender_birth_at_signal_time_known=False, SIGKILL_capturable=False)
            acknowledged = self.threading.Event()
            try:
                self.records.put_nowait((receipt, acknowledged, True))
                acknowledged.wait(timeout=0.05)
            except self.queue.Full:
                pass
            finally:
                self.pending.put(("signal", number))
                os.kill(os.getpid(), signal.SIGUSR2)

    def _dispatch(self, _wakeup, frame):
        while True:
            try:
                kind, number = self.pending.get_nowait()
            except self.queue.Empty:
                return
            if kind == "receiver_failure":
                signal.pthread_sigmask(signal.SIG_UNBLOCK, self.numbers)
                raise RuntimeError("signal receiver failed; native stop delivery restored")
            handler = signal.getsignal(number)
            if callable(handler):
                handler(number, frame)
            else:
                signal.signal(number, signal.SIG_DFL)
                signal.pthread_sigmask(signal.SIG_UNBLOCK, {number})
                os.kill(os.getpid(), number)

    def close(self):
        self.closed.set()
        self.receiver.join(timeout=0.25)
        self._dispatch(signal.SIGUSR2, None)
        signal.signal(signal.SIGUSR2, self.wakeup_handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, self.previous_mask)


def install(log_directory, *, role, context=None):
    global _OBSERVER
    if _OBSERVER is not None:
        raise RuntimeError("signal observer already installed")
    _OBSERVER = SignalObserver(log_directory, role=role, context=context)
    return _OBSERVER
