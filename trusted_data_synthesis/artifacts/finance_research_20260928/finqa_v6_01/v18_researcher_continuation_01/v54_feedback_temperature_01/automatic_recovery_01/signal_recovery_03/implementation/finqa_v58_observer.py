"""Bounded unprivileged CPU observations, never argv/env or signal attribution."""
import argparse
import collections
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import signal
import threading
import time

MIB = 1024 ** 2


def observer_policy():
    return dict(schema="v58_bounded_public_process_observer.v1", poll_seconds=0.5,
        snapshot_seconds=5.0, parent_depth=3, root_userspace_only=True,
        skip_ppid2_kernel_threads=True, initial_root_processes_not_dumped=True,
        root_identity_refresh_seconds=5.0, root_identity_cache_entries=4096,
        event_file_max_bytes=16*MIB, event_file_total_count=4,
        event_log_total_max_bytes=64*MIB, fixed_metadata_max_bytes=65536,
        writer_queue_max_events=256, identity_before_after_birth_check=True,
        tracked_scope="current namespace launch records and active journal only",
        terminal_and_all_tracked_gone_stops_observer=True,
        own_TERM_INT_stops_without_relaunch=True, scientific_processes_signaled=False,
        environment_argv_credentials_history_read=False, system_configuration_changed=False,
        cached_identity_is_not_sender_attribution=True, shorter_than_poll_can_be_missed=True,
        SIGKILL_capturable=False, independent_session_can_share_login_cgroup=True)


def _error(error):
    return dict(type=type(error).__name__, errno=getattr(error, "errno", None))


def _read(path, limit=16384):
    with Path(path).open(encoding="utf-8", errors="replace") as stream:
        return stream.read(limit)


def _stat(pid, proc_root="/proc"):
    raw = _read(Path(proc_root)/str(pid)/"stat", 8192)
    fields = raw.rsplit(")", 1)[1].split()
    return dict(pid=int(pid), comm=raw.split("(", 1)[1].rsplit(")", 1)[0][:256],
        state=fields[0], ppid=int(fields[1]), birth=fields[19])


def process_identity(pid, *, proc_root="/proc", expected_birth=None):
    row = dict(pid=int(pid), observed_at_epoch=time.time(), identity_consistent=False,
        expected_birth=expected_birth, birth_at_signal_time_known=False, read_errors={},
        comm=None, executable=None, ppid=None, birth=None, loginuid=None, sessionid=None,
        ruid=None, euid=None, cgroup=None)
    base = Path(proc_root)/str(pid)
    try:
        before = _stat(pid, proc_root)
        if expected_birth is not None and before["birth"] != str(expected_birth):
            row.update(status="PID_BIRTH_MISMATCH", observed_birth=before["birth"])
            return row
        row.update(before)
    except (OSError, ValueError, IndexError) as error:
        row.update(status="UNKNOWN_OR_GONE", read_errors={"stat": _error(error)})
        return row
    for name in ("loginuid", "sessionid"):
        try:
            value = int(_read(base/name, 64).strip())
            row[name] = None if value == 4294967295 else value
        except (OSError, ValueError) as error:
            row["read_errors"][name] = _error(error)
    try:
        for line in _read(base/"status").splitlines():
            if line.startswith("Uid:"):
                row["ruid"], row["euid"] = map(int, line.split()[1:3])
                break
    except (OSError, ValueError) as error:
        row["read_errors"]["uid"] = _error(error)
    try:
        row["executable"] = os.readlink(base/"exe")
    except OSError as error:
        row["read_errors"]["executable"] = _error(error)
    try:
        row["cgroup"] = _read(base/"cgroup", 4096).splitlines()
    except OSError as error:
        row["read_errors"]["cgroup"] = _error(error)
    try:
        after = _stat(pid, proc_root)
        if (after["birth"], after["ppid"], after["comm"]) != (before["birth"], before["ppid"], before["comm"]):
            return dict(pid=int(pid), observed_at_epoch=row["observed_at_epoch"],
                identity_consistent=False, status="IDENTITY_CHANGED_DURING_READ",
                before=before, after=after, metadata_discarded=True)
    except (OSError, ValueError, IndexError) as error:
        row.update(status="DISAPPEARED_DURING_READ")
        row["read_errors"]["stat_recheck"] = _error(error)
        return row
    row.update(identity_consistent=True, status="PARTIAL" if row["read_errors"] else "OBSERVED")
    return row


def parent_chain(pid, *, expected_birth=None, depth=3, proc_root="/proc"):
    rows, seen = [], set()
    for _ in range(depth+1):
        if int(pid) <= 0 or int(pid) in seen:
            break
        seen.add(int(pid))
        row = process_identity(pid, proc_root=proc_root, expected_birth=expected_birth)
        rows.append(row)
        if not row["identity_consistent"]:
            break
        pid, expected_birth = row["ppid"], None
    for child, parent in zip(rows, rows[1:]):
        try:
            current = _stat(child["pid"], proc_root)
            child["parent_link_rechecked"] = (current["birth"] == child["birth"]
                and current["ppid"] == parent["pid"] and parent["identity_consistent"])
        except (OSError, ValueError, IndexError):
            child["parent_link_rechecked"] = False
    return dict(processes=rows, max_parent_depth=depth, snapshot_is_not_atomic=True,
                observed_identity_is_not_signal_attribution=True)


def cgroup_snapshot(identity, *, cgroup_root="/sys/fs/cgroup"):
    result, root = [], Path(cgroup_root).resolve()
    for line in identity.get("cgroup") or []:
        if not line.startswith("0::"):
            continue
        relative = line.split(":", 2)[2]
        target = (root/relative.lstrip("/")).resolve()
        if not target.is_relative_to(root):
            continue
        row = dict(path=relative, observed_at_epoch=time.time(), files={}, read_errors={})
        for name in ("memory.events", "memory.current", "memory.max", "memory.peak", "cgroup.events", "pids.current"):
            try:
                row["files"][name] = _read(target/name, 4096).strip()
            except OSError as error:
                row["read_errors"][name] = _error(error)
        result.append(row)
    return result


def host_snapshot():
    result = dict(at_epoch=time.time(), memory={}, pressure={}, read_errors={})
    try:
        for line in _read("/proc/meminfo").splitlines():
            key, value = line.split(":", 1)
            if key in ("MemTotal", "MemAvailable", "MemFree", "SwapTotal", "SwapFree"):
                result["memory"][key] = value.strip()
        for name in ("memory", "cpu", "io"):
            result["pressure"][name] = _read(Path("/proc/pressure")/name, 2048).strip()
    except (OSError, ValueError) as error:
        result["read_errors"]["snapshot"] = _error(error)
    return result


class RotatingJSONLog:
    def __init__(self, path, *, max_bytes=16*MIB, total_files=4):
        self.path, self.max_bytes, self.total_files = Path(path), int(max_bytes), int(total_files)

    def append(self, record, *, durable=False):
        data = (json.dumps(record, sort_keys=True, ensure_ascii=True)+"\n").encode()
        if len(data) > self.max_bytes:
            raise ValueError("telemetry record exceeds file limit")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size+len(data) > self.max_bytes:
            for index in range(self.total_files-1, 0, -1):
                source = self.path if index == 1 else Path(str(self.path)+f".{index-1}")
                if source.exists():
                    os.replace(source, Path(str(self.path)+f".{index}"))
            if self.total_files == 1:
                self.path.unlink()
        descriptor = os.open(self.path, os.O_CREAT|os.O_APPEND|os.O_WRONLY|os.O_CLOEXEC, 0o600)
        try:
            if os.write(descriptor, data) != len(data):
                raise OSError("short telemetry write")
            if durable:
                os.fsync(descriptor)
        finally:
            os.close(descriptor)


class AsyncWriter:
    def __init__(self, directory):
        self.directory, self.pending, self.dropped = Path(directory), queue.Queue(maxsize=256), 0
        self.log = RotatingJSONLog(self.directory/"events.jsonl")
        threading.Thread(target=self._run, daemon=True, name="v58-observer-writer").start()

    def submit(self, record, *, status=None, launch=None):
        try:
            self.pending.put_nowait((record, status, launch))
        except queue.Full:
            self.dropped += 1

    def _metadata(self, path, value, *, immutable=False):
        raw = json.dumps(value, sort_keys=True).encode()
        if len(raw) > 16384:
            raise ValueError("observer metadata exceeds bound")
        path.parent.mkdir(parents=True, exist_ok=True)
        if immutable:
            with path.open("xb") as stream:
                stream.write(raw)
        else:
            temporary = path.with_suffix(".pending.json")
            with temporary.open("wb") as stream:
                stream.write(raw)
            os.replace(temporary, path)

    def _run(self):
        while True:
            record, status, launch = self.pending.get()
            try:
                self.log.append(record, durable=status is not None)
                if launch is not None:
                    self._metadata(self.directory/"launch/record.json", launch, immutable=True)
                if status is not None:
                    self._metadata(self.directory/"queue/status.json", status)
            except Exception:
                self.dropped += 1
            finally:
                self.pending.task_done()


class Observer:
    def __init__(self, root, science_root):
        self.root, self.science_root = Path(root).resolve(), Path(science_root).resolve()
        self.writer = AsyncWriter(self.root/"observer")
        self.stop, self.stop_signals, self.last_snapshot = False, [], 0.0
        self.known_files, self.tracked, self.finished = set(), {}, set()
        self.discovery_ok = True
        self.seen = {entry.name for entry in Path("/proc").iterdir() if entry.name.isdigit()}
        self.root_cache = collections.OrderedDict()
        self.identity = process_identity(os.getpid())

    def _emit(self, event, **fields):
        self.writer.submit(dict(schema="v58_public_process_observation.v1", event=event,
                                observed_at_epoch=time.time(), **fields))

    def discover(self):
        self.discovery_ok = True
        paths = [self.root/"supervisor/launch/record.json"]
        paths.extend((self.root/"controllers").glob("attempt*/launch/record.json"))
        for path in paths:
            if path in self.known_files or not path.is_file():
                continue
            try:
                row = json.loads(_read(path, 65536))
                self.tracked[(int(row["pid"]), str(row["birth"]))] = dict(source=str(path))
                self.known_files.add(path)
            except (OSError, ValueError, KeyError, TypeError):
                self.discovery_ok = False
        try:
            journal = self.root/"journal/state.json"
            for row in json.loads(_read(journal, 4*MIB)).get("active_jobs", []):
                key = (int(row["pid"]), str(row["birth"]))
                if key not in self.finished:
                    self.tracked[key] = dict(source=str(journal), job_id=row.get("job_id"))
        except FileNotFoundError:
            if self.known_files or self.tracked:
                self.discovery_ok = False
        except (OSError, ValueError, KeyError, TypeError):
            self.discovery_ok = False

    def poll_root_processes(self, now):
        present = {entry.name for entry in Path("/proc").iterdir() if entry.name.isdigit()}
        for pid in present-self.seen:
            try:
                if (Path("/proc")/pid).stat().st_uid != 0:
                    continue
                basic = _stat(pid)
                if basic["ppid"] == 2:
                    continue
            except (OSError, ValueError, IndexError):
                continue
            identity = process_identity(pid, expected_birth=basic["birth"])
            if identity.get("euid") != 0 or not identity["identity_consistent"]:
                continue
            self.root_cache[(int(pid), identity["birth"])] = dict(identity=identity, refreshed=now)
            self._emit("NEW_ROOT_USERSPACE_IDENTITY", identity=identity, signal_sender_attribution=False)
            while len(self.root_cache) > 4096:
                self.root_cache.popitem(last=False)
        self.seen = present
        for key, cached in list(self.root_cache.items()):
            if str(key[0]) not in present:
                self.root_cache.pop(key, None)
                self._emit("ROOT_CANDIDATE_DISAPPEARED", pid=key[0], birth=key[1],
                           observed_exit_code=None, signal_sender_attribution=False)
            elif now-cached["refreshed"] >= 5.0:
                fresh = process_identity(key[0], expected_birth=key[1])
                if fresh["identity_consistent"]:
                    if (fresh["comm"], fresh["executable"], fresh["euid"]) != (
                            cached["identity"]["comm"], cached["identity"]["executable"], cached["identity"]["euid"]):
                        self._emit("ROOT_CANDIDATE_IDENTITY_CHANGED", previous=cached["identity"],
                                   identity=fresh, signal_sender_attribution=False)
                    cached.update(identity=fresh, refreshed=now)
                else:
                    self.root_cache.pop(key, None)
                    self.seen.discard(str(key[0]))

    def poll_experiment(self):
        live = []
        for key, binding in list(self.tracked.items()):
            identity = process_identity(key[0], expected_birth=key[1])
            gone = (not (Path("/proc")/str(key[0])).exists()
                or identity.get("status") == "PID_BIRTH_MISMATCH"
                or identity.get("state") in ("Z", "X", "x"))
            if gone:
                self._emit("EXPERIMENT_IDENTITY_GONE", pid=key[0], birth=key[1],
                    binding=binding, observation=identity, actual_waitpid_observed=False,
                    actual_exit_code=None, cause_unknown=True)
                self.tracked.pop(key, None)
                self.finished.add(key)
            else:
                live.append((key, identity, binding))
        return live

    def terminal(self):
        return any(path.exists() for path in (self.root/"STOP",
            self.root/"control/stop_requested/record.json", self.root/"supervisor/closeout/record.json"))

    def status(self, state, **fields):
        return dict(schema="v58_independent_observer_heartbeat.v1", status=state,
            pid=os.getpid(), birth=self.identity.get("birth"), root=str(self.root),
            at_epoch=time.time(), last_snapshot_epoch=self.last_snapshot,
            tracked_identities=[dict(pid=key[0], birth=key[1]) for key in self.tracked],
            current_discovery_readable=self.discovery_ok,
            dropped_events=self.writer.dropped, **fields)

    def run(self):
        def stop(signum, _frame):
            self.stop = True
            self.stop_signals.append(signum)
        previous = {number: signal.signal(number, stop) for number in (signal.SIGTERM, signal.SIGINT)}
        launch = dict(schema="v58_independent_observer_launch.v1", pid=os.getpid(),
            birth=self.identity.get("birth"), started_epoch=time.time(), root=str(self.root),
            science_root=str(self.science_root), self_identity=self.identity,
            parent_chain=parent_chain(os.getpid()), policy=observer_policy())
        self.writer.submit(launch, launch=launch, status=self.status("STARTING"))
        try:
            while not self.stop:
                now = time.time()
                self.discover()
                self.poll_root_processes(now)
                live = self.poll_experiment()
                if now-self.last_snapshot >= 5.0:
                    self.last_snapshot = now
                    chains = [parent_chain(key[0], expected_birth=key[1]) for key, _, _ in live]
                    cgroups = [dict(pid=item["pid"], birth=item.get("birth"), values=cgroup_snapshot(item))
                        for chain in chains for item in chain["processes"] if item["identity_consistent"]]
                    self.writer.submit(dict(schema="v58_periodic_system_experiment_snapshot.v1",
                        at_epoch=now, host=host_snapshot(), experiment_parent_chains=chains, cgroups=cgroups),
                        status=self.status("RUNNING", root_candidates_cached=len(self.root_cache)))
                if self.terminal() and self.discovery_ok and not live:
                    break
                time.sleep(0.5)
            status = self.status("STOPPED", own_stop_signals=self.stop_signals,
                terminal_marker_observed=self.terminal(), scientific_processes_signaled=False,
                automatic_restart=False)
            self.writer.submit({**status, "schema": "v58_observer_closeout.v1"}, status=status)
            until = time.monotonic()+0.5
            while self.writer.pending.unfinished_tasks and time.monotonic() < until:
                time.sleep(0.01)
            return status
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)


def checked_control(root, science_root):
    root, science_root = Path(root).resolve(), Path(science_root).resolve()
    expected_science = Path("/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01")
    if science_root != expected_science or root != science_root/"signal_recovery_03":
        raise ValueError("observer requires registered control03/scientific roots")
    value = json.loads(_read(root/"protocol/record.json", 4*MIB))
    body = {key: item for key, item in value.items() if key != "id"}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if value.get("id") != digest:
        raise ValueError("observer control protocol identity changed")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--science-root", type=Path, required=True)
    args = parser.parse_args()
    checked_control(args.root, args.science_root)
    directory = args.root/"observer"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/"owner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (directory/"launch/record.json").exists():
            raise ValueError("observer is single-use; no automatic relaunch")
        print(json.dumps(Observer(args.root, args.science_root).run(), sort_keys=True))


if __name__ == "__main__":
    main()
