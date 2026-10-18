"""Best-effort Linux signal provenance without suppressing cooperative stops.

Install in the main thread before scientific imports or any other threads. Only
SIGTERM/SIGINT are observed; SIGUSR2 is reserved as the main-thread wakeup. The
current original Python stop handler still runs in the main thread. SIGKILL
cannot be captured, attributed or deferred by this observer.
"""

import os
import signal
import sys


_OBSERVER = None


def _error(error):
    return {"type": type(error).__name__, "errno": getattr(error, "errno", None)}


def _sender(pid):
    """Read identity, never environ, command line, open files or credentials."""
    result = {"pid": pid, "executable": None, "ppid": None, "birth": None,
              "cgroup": None, "read_errors": {},
              "proc_observation_is_after_signal_delivery": True,
              "sender_birth_at_send_time_known": False}
    if pid <= 0:
        result["status"] = "KERNEL_OR_SENDER_UNAVAILABLE"
        return result
    try:
        result["executable"] = os.readlink(f"/proc/{pid}/exe")
    except OSError as error:
        result["read_errors"]["executable"] = _error(error)
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as stream:
            fields = stream.read().rsplit(")", 1)[1].split()
        result["ppid"], result["birth"] = int(fields[1]), fields[19]
    except (OSError, IndexError, ValueError) as error:
        result["read_errors"]["process_identity"] = _error(error)
    try:
        with open(f"/proc/{pid}/cgroup", encoding="utf-8") as stream:
            result["cgroup"] = stream.read(65536).splitlines()
    except OSError as error:
        result["read_errors"]["cgroup"] = _error(error)
    result["status"] = "OBSERVED" if not result["read_errors"] else "PARTIAL_OR_UNKNOWN"
    return result


class SignalObserver:
    def __init__(self, directory, *, role, context=None):
        # This block precedes threading, torch and all scientific imports. New
        # threads inherit the mask; only sigwaitinfo consumes the stop signals.
        self.numbers = {signal.SIGTERM, signal.SIGINT}
        self.previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, self.numbers)
        try:
            import json
            import queue
            import threading
            import time
            from pathlib import Path

            if threading.current_thread() is not threading.main_thread() or threading.active_count() != 1:
                raise RuntimeError("signal observer must precede other threads in the main thread")
            if "torch" in sys.modules:
                raise RuntimeError("signal observer must precede torch initialization")
            if signal.getsignal(signal.SIGUSR2) != signal.SIG_DFL:
                raise RuntimeError("SIGUSR2 is already owned; signal observer cannot replace it")
            self.json, self.queue, self.time = json, queue, time
            self.pending = queue.SimpleQueue()
            self.closed = threading.Event()
            self.directory = Path(directory).resolve()
            self.directory.mkdir(parents=True, exist_ok=True)
            self.context, self.role = dict(context or {}), str(role)
            self.fd = os.open(self.directory / "received.jsonl",
                              os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_CLOEXEC, 0o600)
            self.wakeup_handler = signal.signal(signal.SIGUSR2, self._dispatch)
            self._write(dict(schema="v57_signal_observer_started.v1", pid=os.getpid(),
                role=self.role, context=self.context, at_epoch=time.time(),
                mechanism="pthread_sigmask+sigwaitinfo+main_thread_SIGUSR2",
                captured_signals=sorted(int(s) for s in self.numbers),
                SIGKILL_capturable=False, original_stop_handlers_preserved=True,
                environment_or_command_line_recorded=False))
            self.thread = threading.Thread(target=self._receive, name="v57-signal-observer", daemon=True)
            self.thread.start()
        except BaseException:
            if hasattr(self, "wakeup_handler"):
                signal.signal(signal.SIGUSR2, self.wakeup_handler)
            if hasattr(self, "fd"):
                os.close(self.fd)
            signal.pthread_sigmask(signal.SIG_SETMASK, self.previous_mask)
            raise

    def _write(self, record):
        data = (self.json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n").encode()
        # One append-only write, no peak resets, CUDA operations or model state.
        if os.write(self.fd, data) != len(data):
            raise OSError("short signal telemetry write")

    def _receive(self):
        while not self.closed.is_set():
            try:
                info = signal.sigtimedwait(self.numbers, 0.2)
            except InterruptedError:
                continue
            except BaseException as error:
                self.pending.put(("receiver_failure", _error(error)))
                os.kill(os.getpid(), signal.SIGUSR2)
                return
            if info is None:
                continue
            signum = int(info.si_signo)
            try:
                self._write(dict(schema="v57_actual_received_signal.v1", pid=os.getpid(),
                    role=self.role, context=self.context, at_epoch=self.time.time(),
                    signal=signum, signal_name=signal.Signals(signum).name,
                    si_pid=int(info.si_pid), si_uid=int(info.si_uid), si_code=int(info.si_code),
                    sender=_sender(int(info.si_pid)), provenance="kernel_sigwaitinfo",
                    original_handler_dispatch_required=True, SIGKILL_capturable=False))
            except BaseException as error:
                # Observability is best effort. An I/O/proc read failure must
                # never turn a legitimate stop into continued scientific work.
                try:
                    os.write(2, ("V57 signal telemetry unavailable: " + type(error).__name__ + "\n").encode())
                except BaseException:
                    pass
            finally:
                self.pending.put(("signal", signum))
                os.kill(os.getpid(), signal.SIGUSR2)

    def _dispatch(self, _wakeup, frame):
        while True:
            try:
                kind, value = self.pending.get_nowait()
            except self.queue.Empty:
                return
            if kind == "receiver_failure":
                # Fail closed if the observer itself fails. Native stop
                # delivery is restored before aborting the scientific entry.
                signal.pthread_sigmask(signal.SIG_UNBLOCK, self.numbers)
                raise RuntimeError("signal observer receiver failed: " + value["type"])
            handler = signal.getsignal(value)
            if callable(handler):
                handler(value, frame)
            else:
                # SIG_DFL keeps its OS exit status. A later SIG_IGN must not
                # disable TERM/INT safety in this explicitly stop-aware entry.
                signal.signal(value, signal.SIG_DFL)
                signal.pthread_sigmask(signal.SIG_UNBLOCK, {value})
                os.kill(os.getpid(), value)

    def close(self):
        """End observation at process shutdown, restoring native delivery."""
        self.closed.set()
        self.thread.join(timeout=0.5)
        self._dispatch(signal.SIGUSR2, None)
        signal.signal(signal.SIGUSR2, self.wakeup_handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, self.previous_mask)
        os.close(self.fd)


def install(log_directory, *, role, context=None):
    global _OBSERVER
    if _OBSERVER is not None:
        raise RuntimeError("signal observer already installed in this process")
    _OBSERVER = SignalObserver(log_directory, role=role, context=context)
    return _OBSERVER
