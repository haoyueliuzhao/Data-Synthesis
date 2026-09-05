"""Stdlib-only dynamic observer for the detached candidate builder.

This module is executed as a script.  It delegates every syscall to the real
``os`` implementation while recording the exact no-replace/fsync/callback
ordering for the twenty own-trajectory Envelopes.  It does not import candidate
helpers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import sys
from pathlib import Path
from types import FrameType
from typing import Any

CANDIDATE_MODULE = "trusted_synthesis.experiments.qa_reasoning_multitrajectory.preflight"
RUNTIME_MODULE = "trusted_synthesis.experiments.qa_reasoning_multitrajectory.runtime"
PREREGISTERED_FILES = ("quotient_contract.json", "preregistration.json")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class Observer:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root.resolve()
        self.events: list[dict[str, Any]] = []
        self.callbacks: list[dict[str, Any]] = []
        self.fd_paths: dict[int, Path] = {}
        self.in_profile = False
        self.real_open = os.open
        self.real_fsync = os.fsync
        self.real_close = os.close

    def _relative(self, path: Path) -> str | None:
        try:
            return path.resolve().relative_to(self.output_root).as_posix()
        except ValueError:
            return None

    @staticmethod
    def _special(relative: str | None) -> bool:
        return bool(
            relative
            and (
                relative in PREREGISTERED_FILES
                or (
                    relative.startswith("runtime/")
                    and relative.endswith(("_envelope.json", "_preaction_commit_receipt.json"))
                )
            )
        )

    @staticmethod
    def _runtime_directory(relative: str | None) -> bool:
        return relative == "." or bool(
            relative and relative.startswith("runtime/") and "." not in Path(relative).name
        )

    def _record(self, kind: str, relative: str, **values: Any) -> int:
        ordinal = len(self.events) + 1
        self.events.append(
            {"event_ordinal": ordinal, "kind": kind, "relative_path": relative, **values}
        )
        return ordinal

    def open(self, path: Any, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
        descriptor = self.real_open(path, flags, mode, dir_fd=dir_fd)
        path_value = Path(os.fspath(path))
        if not path_value.is_absolute():
            path_value = Path.cwd() / path_value
        relative = self._relative(path_value)
        if relative is not None:
            self.fd_paths[descriptor] = path_value
        if self._special(relative):
            self._record(
                "open",
                str(relative),
                create=bool(flags & os.O_CREAT),
                exclusive=bool(flags & os.O_EXCL),
                write_only=bool(flags & os.O_WRONLY),
            )
        return descriptor

    def fsync(self, descriptor: int) -> None:
        self.real_fsync(descriptor)
        path = self.fd_paths.get(descriptor)
        if path is None:
            return
        relative = self._relative(path)
        if self._special(relative):
            self._record("file_fsync", str(relative))
        elif self._runtime_directory(relative):
            self._record("directory_fsync", str(relative))

    def close(self, descriptor: int) -> None:
        try:
            self.real_close(descriptor)
        finally:
            self.fd_paths.pop(descriptor, None)

    def profile(self, frame: FrameType, event: str, arg: Any) -> None:
        del arg
        if (
            self.in_profile
            or event != "call"
            or frame.f_code.co_name != "execute_action"
            or frame.f_globals.get("__name__") != RUNTIME_MODULE
            or not frame.f_code.co_filename.endswith(
                "trusted_synthesis/experiments/qa_reasoning_multitrajectory/runtime.py"
            )
        ):
            return
        self.in_profile = True
        try:
            caller = frame.f_back
            if caller is None:
                raise RuntimeError("candidate callback caller is absent")
            receipt = caller.f_locals.get("expected_receipt")
            receipt_relative = caller.f_locals.get("receipt_relative_path")
            if receipt is None or not isinstance(receipt_relative, str):
                raise RuntimeError("candidate callback receipt authority is absent")
            envelope_relative = str(receipt.envelope_relative_path)
            envelope_path = self.output_root / envelope_relative
            receipt_path = self.output_root / receipt_relative
            envelope_bytes = envelope_path.read_bytes()
            receipt_bytes = receipt_path.read_bytes()
            receipt_object = json.loads(receipt_bytes)
            if (
                _sha(envelope_bytes) != receipt_object["envelope_sha256"]
                or len(envelope_bytes) != receipt_object["envelope_byte_count"]
                or receipt_object["envelope_relative_path"] != envelope_relative
                or receipt_object["envelope_id"] != str(receipt.envelope_id)
                or receipt_object["receipt_id"]
                != "durable_preaction_commit_receipt:"
                + _sha(_canonical({k: v for k, v in receipt_object.items() if k != "receipt_id"}))
            ):
                raise RuntimeError("candidate callback disk bytes or Receipt identity differ")
            envelope_object = json.loads(envelope_bytes)
            if envelope_object["envelope_id"] != receipt_object["envelope_id"]:
                raise RuntimeError("candidate callback Envelope identity differs")
            matching = self.events
            envelope_open = max(
                item["event_ordinal"]
                for item in matching
                if item["kind"] == "open" and item["relative_path"] == envelope_relative
            )
            envelope_fsync = max(
                item["event_ordinal"]
                for item in matching
                if item["kind"] == "file_fsync" and item["relative_path"] == envelope_relative
            )
            receipt_open = max(
                item["event_ordinal"]
                for item in matching
                if item["kind"] == "open" and item["relative_path"] == receipt_relative
            )
            receipt_fsync = max(
                item["event_ordinal"]
                for item in matching
                if item["kind"] == "file_fsync" and item["relative_path"] == receipt_relative
            )
            parent = Path(envelope_relative).parent.as_posix()
            envelope_directory_fsync = max(
                item["event_ordinal"]
                for item in matching
                if item["kind"] == "directory_fsync"
                and item["relative_path"] == parent
                and envelope_fsync < item["event_ordinal"] < receipt_open
            )
            receipt_directory_fsync = max(
                item["event_ordinal"]
                for item in matching
                if item["kind"] == "directory_fsync"
                and item["relative_path"] == parent
                and item["event_ordinal"] > receipt_fsync
            )
            open_rows = [
                item
                for item in matching
                if item["kind"] == "open"
                and item["relative_path"] in {envelope_relative, receipt_relative}
            ]
            if (
                len(open_rows) < 2
                or not all(
                    item["create"] and item["exclusive"] and item["write_only"]
                    for item in open_rows[-2:]
                )
                or not (
                    envelope_open
                    < envelope_fsync
                    < envelope_directory_fsync
                    < receipt_open
                    < receipt_fsync
                    < receipt_directory_fsync
                )
                or not (
                    receipt_object["envelope_file_fsync_event"]
                    < receipt_object["envelope_directory_fsync_event"]
                    < receipt_object["receipt_file_fsync_event"]
                    < receipt_object["receipt_directory_fsync_event"]
                    < receipt_object["dispatch_event"]
                )
                or receipt_object["preaction_commit_sequence"]
                >= receipt_object["execution_sequence"]
            ):
                raise RuntimeError("candidate callback durable preaction order differs")
            preregistration = []
            for registered_path in PREREGISTERED_FILES:
                disk = (self.output_root / registered_path).read_bytes()
                opened = [
                    e
                    for e in self.events
                    if e["kind"] == "open" and e["relative_path"] == registered_path
                ]
                synced = [
                    e
                    for e in self.events
                    if e["kind"] == "file_fsync" and e["relative_path"] == registered_path
                ]
                if (
                    len(opened) != 1
                    or len(synced) != 1
                    or not opened[0]["exclusive"]
                    or not opened[0]["create"]
                ):
                    raise RuntimeError("predeclared rules not durably created exactly once")
                directory_sync = min(
                    e["event_ordinal"]
                    for e in self.events
                    if e["kind"] == "directory_fsync"
                    and e["relative_path"] == "."
                    and e["event_ordinal"] > synced[0]["event_ordinal"]
                )
                if (
                    not opened[0]["event_ordinal"]
                    < synced[0]["event_ordinal"]
                    < directory_sync
                    < envelope_open
                ):
                    raise RuntimeError("predeclaration is not prior to trajectory execution")
                preregistration.append(
                    {
                        "relative_path": registered_path,
                        "sha256": _sha(disk),
                        "byte_count": len(disk),
                        "open_event": opened[0]["event_ordinal"],
                        "file_fsync_event": synced[0]["event_ordinal"],
                        "directory_fsync_event": directory_sync,
                    }
                )
            callback_event = self._record("callback_entry", receipt_relative)
            self.callbacks.append(
                {
                    "envelope_relative_path": envelope_relative,
                    "receipt_relative_path": receipt_relative,
                    "envelope_sha256": _sha(envelope_bytes),
                    "envelope_byte_count": len(envelope_bytes),
                    "receipt_sha256": _sha(receipt_bytes),
                    "receipt_byte_count": len(receipt_bytes),
                    "envelope_open_event": envelope_open,
                    "envelope_file_fsync_event": envelope_fsync,
                    "envelope_directory_fsync_event": envelope_directory_fsync,
                    "receipt_open_event": receipt_open,
                    "receipt_file_fsync_event": receipt_fsync,
                    "receipt_directory_fsync_event": receipt_directory_fsync,
                    "callback_event": callback_event,
                    "open_flags_verified": True,
                    "disk_reread_verified": True,
                    "receipt_identity_verified": True,
                    "preregistration": preregistration,
                    "passed": True,
                }
            )
        finally:
            self.in_profile = False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--external-audit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output-dir", required=True)
    arguments = parser.parse_args()
    observer = Observer(Path(arguments.output_dir))
    os.open = observer.open  # type: ignore[assignment]
    os.fsync = observer.fsync  # type: ignore[assignment]
    os.close = observer.close  # type: ignore[assignment]
    sys.setprofile(observer.profile)
    sys.argv = [
        CANDIDATE_MODULE,
        "--repo-root",
        arguments.repo_root,
        "--external-audit",
        arguments.external_audit,
        "--source-commit",
        arguments.source_commit,
        "--source-tree",
        arguments.source_tree,
        "--output-dir",
        arguments.output_dir,
    ]
    try:
        runpy.run_module(CANDIDATE_MODULE, run_name="__main__")
    finally:
        sys.setprofile(None)
        os.open = observer.real_open
        os.fsync = observer.real_fsync
        os.close = observer.real_close
        Path(arguments.trace).write_bytes(
            _canonical(
                {
                    "callbacks": observer.callbacks,
                    "callback_count": len(observer.callbacks),
                    "all_callbacks_passed": all(bool(row["passed"]) for row in observer.callbacks),
                    "observed_event_count": len(observer.events),
                    "schema_version": "qa_reasoning_multitrajectory_independent_dynamic_probe.v1",
                }
            )
        )


if __name__ == "__main__":
    main()
