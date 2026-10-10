"""Nonblocking, result-aware process draining around unchanged V35 mathematics.

The owning controller supplies ``lifecycle_api = base`` and may additionally
define ``lifecycle_result_validator(stage, result)``. A COMPLETE result is not
a free GPU slot: only an actually reaped, successfully validated child releases
its original lock. Process observations are evidence, never synthetic zeros.
"""

from __future__ import annotations

import hashlib
import json
import signal
import time
from pathlib import Path

RUNNING = "RUNNING"
DRAINING = "RESULT_COMMITTED_DRAINING"
EXITED = "EXITED_PENDING_VALIDATION"
SUCCEEDED = "SUCCEEDED"
PF_EXITING = 0x00000004
DRAIN_SECONDS = 600


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_proc_snapshot(pid):
    """Keep the actual stat/status/cmdline readings and their individual errors.

    In particular a Z state retains its readable start tick. A missing file,
    missing RSS, and a zombie are not collapsed into one ``birth=None`` value.
    Stat is sampled around the other reads to detect a changed PID identity.
    """
    snapshot = dict(pid=pid, read_errors={})

    def read(name, *, binary=False):
        try:
            path = Path(f"/proc/{pid}/{name}")
            return path.read_bytes() if binary else path.read_text()
        except (FileNotFoundError, ProcessLookupError, PermissionError) as error:
            snapshot["read_errors"][name] = dict(type=type(error).__name__, errno=error.errno)
            return None

    def stat(raw):
        if raw is None:
            return None
        fields = raw.rsplit(")", 1)[1].split()
        return dict(state=fields[0], birth=fields[19], flags=int(fields[6]))

    snapshot["stat_before_raw"] = read("stat")
    before = stat(snapshot["stat_before_raw"])
    snapshot["status_raw"] = read("status")
    command_raw = read("cmdline", binary=True)
    snapshot["command"] = (
        [part.decode(errors="replace") for part in command_raw.split(b"\0") if part]
        if command_raw is not None
        else None
    )
    snapshot["stat_after_raw"] = read("stat")
    after = stat(snapshot["stat_after_raw"])
    current = after or before
    snapshot.update(
        state=current["state"] if current else None,
        flags=current["flags"] if current else None,
        birth_observations=[item["birth"] for item in (before, after) if item is not None],
        stat_before=before,
        stat_after=after,
    )
    values = {}
    for line in (snapshot["status_raw"] or "").splitlines():
        key, _, value = line.partition(":")
        if key in {"VmRSS", "VmHWM"}:
            values[key] = int(value.split()[0]) * 1024
    snapshot["rss_bytes"] = values.get("VmRSS")
    snapshot["peak_rss_bytes"] = values.get("VmHWM")
    return snapshot


class LifecycleMixin:
    """Mixin for controllers with V35's active/process/launch/lock contract."""

    lifecycle_proc_reader = staticmethod(read_proc_snapshot)

    def _lifecycle_setup(self):
        if not hasattr(self, "_lifecycle_event_count"):
            self._lifecycle_event_count = 0
            self._lifecycle_episode = None
            self._lifecycle_episode_count = 0
            self._lifecycle_stopping = False
        for item in self.active.values():
            item.setdefault("lifecycle_state", RUNNING)

    def _lifecycle_event(self, kind, **body):
        self._lifecycle_setup()
        api = self.lifecycle_api
        path = self.root / "lifecycle" / f"event{self._lifecycle_event_count:06d}/record.json"
        self._lifecycle_event_count += 1
        return api.publish(
            path,
            dict(
                schema="v36_result_aware_process_lifecycle.v1",
                at=api.now(),
                protocol_id=self.protocol["id"],
                kind=kind,
                **body,
            ),
        )

    def _lifecycle_transition(self, stage, item, state, **details):
        previous = item["lifecycle_state"]
        item["lifecycle_state"] = state
        self._lifecycle_event(
            "state_transition",
            stage=stage,
            pid=item["launch"]["pid"],
            registered_birth=item["launch"]["birth"],
            previous_state=previous,
            state=state,
            worker_slot_retained=stage in self.active,
            gpu_lock_retained=stage in self.active,
            **details,
        )

    def _lifecycle_result(self, stage, *, process_alive):
        """Read a sealed COMPLETE once; partial JSON is not a committed result."""
        path = self.root / stage / "result/record.json"
        if not path.exists():
            return None
        raw = path.read_bytes()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            if process_alive:
                self._lifecycle_event(
                    "result_not_committed_yet",
                    stage=stage,
                    reason="JSON write still incomplete",
                    observed_bytes=len(raw),
                )
                return None
            raise ValueError("exited worker has an incomplete result: " + stage) from None
        # The original immutable writer writes a final newline before flush and
        # fsync. Do not capture a different byte SHA between '}' and that newline.
        if not raw.endswith(b"\n"):
            if process_alive:
                self._lifecycle_event(
                    "result_not_committed_yet",
                    stage=stage,
                    reason="final writer newline not observed",
                    observed_bytes=len(raw),
                )
                return None
            raise ValueError("exited worker result lacks its complete writer boundary: " + stage)
        api = self.lifecycle_api
        require(
            result.get("id") == api.digest({k: v for k, v in result.items() if k != "id"}),
            "result identity changed: " + stage,
        )
        # This is the original complete numerical AND resource validator, not
        # a replacement based on the word COMPLETE or a trusted-looking flag.
        api.check_result(self.protocol, stage, result, self.task_plan)
        extra = getattr(self, "lifecycle_result_validator", None)
        if extra is not None:
            extra(stage, result)
        observations = result["resources"]["observations"]
        require(
            result.get("model_released") is True and bool(observations),
            "draining requires an explicitly released model and real resource observations",
        )
        final = observations[-1]
        require(
            final["label"] == "model_released.after_cleanup"
            and final["boundary"] is True
            and final["passed"] is True
            and final["allocated_pass"] is True
            and final["free_pass"] is True,
            "draining requires the original final model-release resource gate",
        )
        return result, dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), id=result["id"])

    def _lifecycle_enter_draining(self, stage, item, trusted):
        result, reference = trusted
        if self._lifecycle_episode is None:
            started = time.monotonic()
            self._lifecycle_episode_count += 1
            self._lifecycle_episode = dict(
                episode=self._lifecycle_episode_count,
                first_draining_monotonic=started,
                deadline_monotonic=started + DRAIN_SECONDS,
                first_draining_epoch=time.time(),
                duration_seconds=DRAIN_SECONDS,
                deadline_epoch=time.time() + DRAIN_SECONDS,
            )
            self._lifecycle_event(
                "draining_episode_started",
                **self._lifecycle_episode,
                shared_by_concurrent_drainers=True,
                does_not_extend_global_deadline=True,
            )
        item["lifecycle_result"] = result
        item["lifecycle_result_ref"] = reference
        item["lifecycle_draining_started_monotonic"] = time.monotonic()
        item["lifecycle_draining_deadline"] = self._lifecycle_episode["deadline_monotonic"]
        self._lifecycle_transition(
            stage, item, DRAINING, result=reference, draining_episode=dict(self._lifecycle_episode)
        )

    def _lifecycle_close_episode(self):
        if self._lifecycle_episode is not None and not any(
            item["lifecycle_state"] in {DRAINING, EXITED} for item in self.active.values()
        ):
            self._lifecycle_event(
                "draining_episode_ended",
                **self._lifecycle_episode,
                all_drainers_actually_exited=True,
            )
            self._lifecycle_episode = None

    def _lifecycle_drain_gate(self):
        if self._lifecycle_episode is not None and any(
            item["lifecycle_state"] == DRAINING for item in self.active.values()
        ):
            require(
                time.monotonic() < self._lifecycle_episode["deadline_monotonic"],
                "fixed shared draining episode exceeded 600 seconds",
            )

    def _lifecycle_accept_exit(self, stage, item, code, *, stopped=False):
        self._lifecycle_transition(stage, item, EXITED, actual_returncode=code)
        try:
            require(code == 0, "worker exited unsuccessfully: " + stage)
            trusted = self._lifecycle_result(stage, process_alive=False)
            require(trusted is not None, "worker exited without a committed result: " + stage)
            result, reference = trusted
            old = item.get("lifecycle_result_ref")
            require(
                old is None or reference == old, "committed result changed while draining: " + stage
            )
        except BaseException as error:
            self.record_exit(stage, stopped=stopped)
            self._lifecycle_event(
                "exit_validation_failed",
                stage=stage,
                actual_returncode=code,
                error_type=type(error).__name__,
                error=str(error),
            )
            raise
        self.record_exit(stage, stopped=stopped)
        self.results[stage] = result
        self._lifecycle_transition(stage, item, SUCCEEDED, actual_returncode=code, result=reference)
        self.update("SAFE_BOUNDARY_STOP_REQUESTED" if stopped else "RUNNING")

    def collect_finished(self):
        self._lifecycle_setup()
        for stage in tuple(self.active):
            item = self.active[stage]
            require(
                not (self.root / stage / "failure/record.json").exists(),
                "worker reported failure: " + stage,
            )
            code = item["process"].poll()
            if item["lifecycle_state"] == RUNNING:
                trusted = self._lifecycle_result(stage, process_alive=code is None)
                if trusted is not None:
                    self._lifecycle_enter_draining(stage, item, trusted)
            if code is not None:
                self._lifecycle_accept_exit(stage, item, code)
        self._lifecycle_close_episode()
        self._lifecycle_drain_gate()

    def _lifecycle_process_gate(self, stage, item, snapshot):
        gaps = []
        expected_birth = item["launch"]["birth"]
        births = snapshot["birth_observations"]
        require(all(value == expected_birth for value in births), "live worker ownership changed")
        draining = item["lifecycle_state"] == DRAINING
        if not births:
            require(draining, "uncommitted worker identity unavailable; no draining exemption")
            gaps.append("birth")
        exiting = snapshot["state"] in {"Z", "X", "x"} or bool(
            (snapshot["flags"] or 0) & PF_EXITING
        )
        command = snapshot["command"]
        if command and not exiting:
            require(
                item["launch"]["worker"] in command
                and "--stage" in command
                and command.index("--stage") + 1 < len(command)
                and command[command.index("--stage") + 1] == stage,
                "non-exiting worker command differs from owned launch",
            )
        elif not command:
            require(draining, "uncommitted worker command unavailable; no draining exemption")
            gaps.append("command")
        rss, peak = snapshot["rss_bytes"], snapshot["peak_rss_bytes"]
        limit = self.lifecycle_api.HOST_RAM[
            "coordinator_rss_limit_bytes" if stage == "coordinator" else "shard_rss_limit_bytes"
        ]
        # Even a partially readable status file cannot conceal a high-water
        # violation in the field that IS still available during teardown.
        if rss is not None:
            require(0 <= rss <= limit, "observed worker RSS hard gate failed")
        if peak is not None:
            require(0 <= peak <= limit, "observed worker RSS hard gate failed")
        if rss is None or peak is None:
            require(draining, "uncommitted worker RSS unavailable; no draining exemption")
            gaps.append("RSS")
        else:
            require(0 <= rss <= peak <= limit, "observed worker RSS hard gate failed")
        return dict(
            rss_limit_bytes=limit,
            observation_gaps=gaps,
            missing_values_are_not_zero=True,
            previously_validated_result_required=draining,
        )

    def observe_host(self):
        self._lifecycle_setup()
        self._lifecycle_drain_gate()
        api = self.lifecycle_api
        host = api.host_memory()
        gpu_rows = {row["index"]: row for row in api.inventory()}
        observed = []
        failure = None
        try:
            require(
                host["available_bytes"] >= api.HOST_RAM["reserve_bytes"],
                "observed host MemAvailable hard gate failed",
            )
            for stage, item in self.active.items():
                if item["process"].poll() is not None:
                    continue
                # Publication can finish between collect_finished and this
                # exact RSS observation. Admit a now-trusted result first.
                if item["lifecycle_state"] == RUNNING:
                    trusted = self._lifecycle_result(stage, process_alive=True)
                    if trusted is not None:
                        self._lifecycle_enter_draining(stage, item, trusted)
                snapshot = self.lifecycle_proc_reader(item["launch"]["pid"])
                # Result publication and address-space teardown are separate
                # reads. If publication finished while /proc was sampled, give
                # that now-complete result its strict validation before using
                # an observation gap as evidence of an uncommitted failure.
                code_after_snapshot = item["process"].poll()
                if code_after_snapshot is not None:
                    observed.append(
                        dict(
                            stage=stage,
                            state=item["lifecycle_state"],
                            proc=snapshot,
                            actual_exit_observed_during_snapshot=code_after_snapshot,
                            pending_final_result_validation=True,
                            worker_slot_retained=True,
                            gpu_lock_retained=True,
                        )
                    )
                    continue
                if item["lifecycle_state"] == RUNNING and (
                    not snapshot["birth_observations"]
                    or not snapshot["command"]
                    or snapshot["rss_bytes"] is None
                    or snapshot["peak_rss_bytes"] is None
                ):
                    trusted = self._lifecycle_result(stage, process_alive=True)
                    if trusted is not None:
                        self._lifecycle_enter_draining(stage, item, trusted)
                row = dict(
                    stage=stage,
                    state=item["lifecycle_state"],
                    proc=snapshot,
                    worker_slot_retained=True,
                    gpu_lock_retained=True,
                )
                observed.append(row)
                row.update(self._lifecycle_process_gate(stage, item, snapshot))
                gpu = gpu_rows.get(item["launch"]["gpu_index"])
                row["gpu"] = gpu
                require(
                    gpu is not None and gpu["uuid"] == item["launch"]["gpu_uuid"],
                    "owned physical GPU observation missing or identity changed",
                )
                # RUNNING may be sampled mid-row: its unchanged worker still
                # enforces the physical-free gate at the registered boundaries.
                # DRAINING is after model release, hence a real final boundary.
                if item["lifecycle_state"] == DRAINING:
                    require(
                        gpu["free_mib"] * 1024**2 >= api.MINIMUM_DEVICE_FREE_BYTES,
                        "draining GPU physical-free boundary gate failed",
                    )
                row["external_free_boundary_gate_applied"] = item["lifecycle_state"] == DRAINING
        except BaseException as error:
            failure = error
        self._lifecycle_event(
            "host_gpu_process_observation",
            host=host,
            gpu_observation=list(gpu_rows.values()),
            workers=observed,
            all_observable_resource_gates_passed=failure is None,
            unobservable_draining_RSS_is_not_a_measurement=True,
            error=None
            if failure is None
            else dict(type=type(failure).__name__, message=str(failure)),
        )
        if failure is not None:
            raise failure

    def _lifecycle_launch_gate(self):
        self._lifecycle_setup()
        require(not self._lifecycle_stopping, "global shutdown grace cannot dispatch new work")
        require(
            not any(item["lifecycle_state"] in {DRAINING, EXITED} for item in self.active.values()),
            "draining grace cannot dispatch new work",
        )
        self.time_gate()

    def run_group(self, stages):
        self._lifecycle_launch_gate()
        rows, locks = self.acquire(stages)
        try:
            for stage in stages:
                self._lifecycle_launch_gate()
                index = self.lifecycle_api.STAGE_GPU[stage]
                try:
                    self.launch(stage, rows[index], locks[index])
                finally:
                    if stage in self.active:
                        del locks[index]
            while self.active:
                self.time_gate()
                self.collect_finished()
                if self.active:
                    self.observe_host()
                    self.collect_finished()
                if self.active:
                    delay = min(
                        self.lifecycle_api.POLL_SECONDS, max(0, self.deadline - time.monotonic())
                    )
                    if self._lifecycle_episode is not None:
                        delay = min(
                            delay,
                            max(
                                0, self._lifecycle_episode["deadline_monotonic"] - time.monotonic()
                            ),
                        )
                    time.sleep(delay)
            self.time_gate()
        finally:
            for lock in locks.values():
                lock.close()

    def drain_stopped(self):
        """One global stop window, never extending an active drain episode."""
        self._lifecycle_setup()
        self._lifecycle_stopping = True
        api = self.lifecycle_api
        stop_at = time.monotonic()
        deadline = stop_at + api.TERM_GRACE_SECONDS
        if self._lifecycle_episode is not None:
            deadline = min(deadline, self._lifecycle_episode["deadline_monotonic"])
        errors = []

        def signal_group(sig, *, running_only=False):
            for stage, item in self.active.items():
                if item["process"].poll() is None and (
                    not running_only or item["lifecycle_state"] == RUNNING
                ):
                    try:
                        sent = api.signal_owned(item["launch"], sig)
                        self._lifecycle_event(
                            "owned_stop_signal", stage=stage, signal=int(sig), sent=sent
                        )
                    except BaseException as error:
                        errors.append(dict(stage=stage, signal=int(sig), error=str(error)))

        signal_group(signal.SIGTERM, running_only=True)
        self._lifecycle_event(
            "global_stop_window",
            started_monotonic=stop_at,
            deadline_monotonic=deadline,
            active_draining_episode_not_extended=True,
        )
        self.update("SAFE_BOUNDARY_STOP_REQUESTED")
        killed = False
        while self.active:
            for stage in tuple(self.active):
                item = self.active[stage]
                code = item["process"].poll()
                if code is not None:
                    if item["lifecycle_state"] == DRAINING and code == 0:
                        try:
                            self._lifecycle_accept_exit(stage, item, code, stopped=True)
                        except BaseException as error:
                            errors.append(dict(stage=stage, error=str(error)))
                    else:
                        self._lifecycle_transition(stage, item, EXITED, actual_returncode=code)
                        self.record_exit(stage, stopped=True)
            if not self.active:
                break
            if time.monotonic() >= deadline and not killed:
                signal_group(signal.SIGKILL)
                killed = True
            require(
                not killed or time.monotonic() < deadline + 60,
                "owned process still alive after shared stop window; manual inspection required",
            )
            time.sleep(min(api.POLL_SECONDS, 1 if killed else max(0, deadline - time.monotonic())))
        self._lifecycle_close_episode()
        require(not errors, "one or more lifecycle stop/exit guards failed: " + str(errors))
