from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, NoReturn, TypeVar

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_contract_freeze import models as reasoning_models

from .models import DurablePreactionCommitReceipt

ResultT = TypeVar("ResultT")


class FixedFixtureRuntimeError(ValueError):
    """A fixed-Fixture write or pre-action dispatch boundary failed closed."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise FixedFixtureRuntimeError(stage, reason)


class DurableArtifactWriter:
    """No-replace writer whose event log is deterministic and testable.

    Runtime objects are written directly into the final formal directory.  Every
    file is fsynced before its containing directory, and a pre-action dispatcher
    rereads the actual bytes before invoking its callback.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.events: list[dict[str, Any]] = []

    def create_root(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=False)
        except FileExistsError as error:
            raise FixedFixtureRuntimeError(
                "runtime.output_directory_no_replace",
                "fixed-Fixture output directory already exists",
            ) from error
        self._fsync_directory(self.root.parent)

    def ensure_directory(self, relative: str) -> Path:
        directory = self._resolve(relative)
        directory.mkdir(parents=True, exist_ok=True)
        self._fsync_directory(directory)
        return directory

    def _resolve(self, relative: str) -> Path:
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            _fail("runtime.relative_path", "runtime artifact path escapes the output root")
        path = self.root / relative
        if self.root.resolve() not in path.resolve().parents:
            _fail("runtime.relative_path", "runtime artifact path escapes the output root")
        return path

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _event(self, kind: str, relative_path: str) -> int:
        ordinal = len(self.events) + 1
        self.events.append({"event_ordinal": ordinal, "kind": kind, "relative_path": relative_path})
        return ordinal

    def write_bytes(self, relative: str, payload: bytes) -> tuple[int, int]:
        path = self._resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError as error:
            raise FixedFixtureRuntimeError(
                "runtime.no_replace", f"runtime artifact already exists:{relative}"
            ) from error
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    _fail("runtime.write", f"runtime artifact write stalled:{relative}")
                view = view[written:]
            os.fsync(descriptor)
            file_event = self._event("file_fsync", relative)
        finally:
            os.close(descriptor)
        self._fsync_directory(path.parent)
        directory_event = self._event("directory_fsync", relative)
        return file_event, directory_event

    def write_json(self, relative: str, value: Any) -> bytes:
        payload = canonical_json_bytes(value)
        self.write_bytes(relative, payload)
        return payload

    def read_bytes(self, relative: str) -> bytes:
        return self._resolve(relative).read_bytes()

    def commit_envelope(
        self,
        *,
        envelope: reasoning_models.ReasoningActionEnvelopeV1,
        envelope_relative_path: str,
        receipt_relative_path: str,
        execution_sequence: int,
    ) -> tuple[DurablePreactionCommitReceipt, bytes, bytes]:
        envelope_bytes = canonical_json_bytes(envelope)
        file_event, directory_event = self.write_bytes(envelope_relative_path, envelope_bytes)
        receipt_file_event = len(self.events) + 1
        receipt_directory_event = receipt_file_event + 1
        dispatch_event = receipt_directory_event + 1
        values: dict[str, Any] = {
            "task_instance_id": envelope.task_instance_id,
            "state_id": envelope.state_id,
            "decision_id": envelope.decision_id,
            "envelope_id": envelope.envelope_id,
            "envelope_relative_path": envelope_relative_path,
            "envelope_sha256": hashlib.sha256(envelope_bytes).hexdigest(),
            "envelope_byte_count": len(envelope_bytes),
            "preaction_commit_sequence": envelope.preaction_commit_sequence,
            "execution_sequence": execution_sequence,
            "envelope_file_fsync_event": file_event,
            "envelope_directory_fsync_event": directory_event,
            "receipt_file_fsync_event": receipt_file_event,
            "receipt_directory_fsync_event": receipt_directory_event,
            "dispatch_event": dispatch_event,
            "no_replace": True,
            "envelope_file_fsync_complete": True,
            "envelope_directory_fsync_complete": True,
            "schema_version": "durable_preaction_commit_receipt.v1",
        }
        values["receipt_id"] = strict_canonical_hash(
            values, prefix="durable_preaction_commit_receipt:"
        )
        receipt = DurablePreactionCommitReceipt.model_validate(values)
        receipt_bytes = canonical_json_bytes(receipt)
        actual_file, actual_directory = self.write_bytes(receipt_relative_path, receipt_bytes)
        if (actual_file, actual_directory) != (
            receipt.receipt_file_fsync_event,
            receipt.receipt_directory_fsync_event,
        ):
            _fail("runtime.receipt_fsync_order", "receipt fsync order differs")
        return receipt, envelope_bytes, receipt_bytes

    def guard_and_dispatch(
        self,
        *,
        expected_envelope: reasoning_models.ReasoningActionEnvelopeV1,
        expected_receipt: DurablePreactionCommitReceipt,
        receipt_relative_path: str,
        callback: Callable[[], ResultT],
    ) -> ResultT:
        envelope_bytes = self.read_bytes(expected_receipt.envelope_relative_path)
        receipt_bytes = self.read_bytes(receipt_relative_path)
        admit_preaction_commit(
            expected_envelope=expected_envelope,
            expected_receipt=expected_receipt,
            actual_envelope_bytes=envelope_bytes,
            actual_receipt_bytes=receipt_bytes,
            events=tuple(self.events),
        )
        if len(self.events) + 1 != expected_receipt.dispatch_event:
            _fail("runtime.dispatch_order", "dispatch event does not immediately follow receipt")
        self._event("action_dispatch", receipt_relative_path)
        return callback()


def admit_preaction_commit(
    *,
    expected_envelope: reasoning_models.ReasoningActionEnvelopeV1,
    expected_receipt: DurablePreactionCommitReceipt,
    actual_envelope_bytes: bytes,
    actual_receipt_bytes: bytes,
    events: tuple[Mapping[str, Any], ...],
) -> None:
    expected_envelope_bytes = canonical_json_bytes(expected_envelope)
    expected_receipt_bytes = canonical_json_bytes(expected_receipt)
    if actual_envelope_bytes != expected_envelope_bytes:
        _fail("runtime.expected_envelope_bytes", "durable Envelope bytes differ")
    if actual_receipt_bytes != expected_receipt_bytes:
        _fail("runtime.expected_receipt_bytes", "durable receipt bytes differ")
    if (
        expected_receipt.envelope_id != expected_envelope.envelope_id
        or expected_receipt.task_instance_id != expected_envelope.task_instance_id
        or expected_receipt.state_id != expected_envelope.state_id
        or expected_receipt.decision_id != expected_envelope.decision_id
        or expected_receipt.envelope_sha256 != hashlib.sha256(expected_envelope_bytes).hexdigest()
        or expected_receipt.envelope_byte_count != len(expected_envelope_bytes)
    ):
        _fail("runtime.receipt_envelope_binding", "receipt does not bind exact Envelope")
    by_ordinal = {int(item["event_ordinal"]): item for item in events}
    required = (
        (expected_receipt.envelope_file_fsync_event, "file_fsync"),
        (expected_receipt.envelope_directory_fsync_event, "directory_fsync"),
        (expected_receipt.receipt_file_fsync_event, "file_fsync"),
        (expected_receipt.receipt_directory_fsync_event, "directory_fsync"),
    )
    if any(by_ordinal.get(ordinal, {}).get("kind") != kind for ordinal, kind in required):
        _fail("runtime.observed_fsync_order", "observed fsync events differ from receipt")
    if expected_receipt.dispatch_event != len(events) + 1:
        _fail("runtime.preaction_before_dispatch", "receipt was not durable before dispatch")
