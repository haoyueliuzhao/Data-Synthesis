"""Read accepted historical evidence and bind representation inputs; never requalify."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from ..finance_qa_vnext_model_execution import representation as original
from ..finance_qa_vnext_model_execution.models import identity as old_identity
from ..finance_qa_vnext_model_execution.models import read_json, require, sha
from .core import record

PARENT_COMMIT = "9471c222b308e5de17b5aba1f9ceb673cb5186af"
HISTORICAL_ROOT = (
    "trusted_data_synthesis/artifacts/qa_vnext_action_branch/action_contract_branch_v1_20260906"
)
HISTORY_PREFIXES = (
    "qa_vnext_model_execution",
    "qa_vnext_update_calibration",
    "qa_vnext_repaired_full_task",
    "qa_vnext_action_branch",
)


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "length.regular_input_file")
    value = read_json(path.read_bytes())
    require(isinstance(value, dict), "length.input_object")
    return value


def source_anchor(root: Path) -> dict[str, Any]:
    """Verify the historical directory against its already-published Git objects."""
    tree = git(root, "ls-tree", "-r", "-z", PARENT_COMMIT, "--", HISTORICAL_ROOT)
    entries = []
    for item in tree.split(b"\0"):
        if not item:
            continue
        metadata, relative_raw = item.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        relative = relative_raw.decode()
        path = root / relative
        require(mode == "100644" and kind == "blob", "length.historical_git_file")
        require(path.is_file() and not path.is_symlink(), "length.historical_file_missing")
        data = path.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(actual == oid, "length.historical_published_bytes_changed")
        entries.append({"path": relative, "byte_count": len(data), "sha256": sha(data)})
    require(len(entries) == 701, "length.fixed_historical_directory")
    return record(
        "source_anchor",
        commit=PARENT_COMMIT,
        directory=HISTORICAL_ROOT,
        files=entries,
        file_count=len(entries),
        byte_count=sum(item["byte_count"] for item in entries),
    )


def history_inventory(root: Path) -> dict[str, Any]:
    entries = []
    base = root / "trusted_data_synthesis/artifacts"
    for prefix in HISTORY_PREFIXES:
        for path in sorted((base / prefix).rglob("*")):
            require(not path.is_symlink(), "length.history_symlink")
            if path.is_file():
                data = path.read_bytes()
                entries.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "byte_count": len(data),
                        "sha256": sha(data),
                    }
                )
    require(bool(entries), "length.history_empty")
    return record(
        "history_inventory",
        files=entries,
        file_count=len(entries),
        byte_count=sum(item["byte_count"] for item in entries),
    )


def source_snapshot(root: Path) -> dict[str, Any]:
    paths = sorted(
        path
        for subdir in ("src", "tests")
        for path in (root / "trusted_data_synthesis" / subdir).rglob("*.py")
    )
    files = [
        {"path": path.relative_to(root).as_posix(), "sha256": sha(path.read_bytes())}
        for path in paths
    ]
    return record(
        "implementation",
        git_commit=git(root, "rev-parse", "HEAD").decode().strip(),
        files=files,
        file_count=len(files),
    )


def read_source(root: Path) -> dict[str, Any]:
    base = root / HISTORICAL_ROOT
    analysis = base / "execution/analysis"
    dataset = load(analysis / "supervision_candidates.json")
    old_tokens = load(analysis / "token_representations.json")
    old_identity(dataset, "supervision_dataset")
    old_identity(old_tokens, "token_representation_dataset")
    binding = load(base / "preparation/tokenizer_binding.json")
    source = {
        "root": root,
        "dataset": dataset,
        "old_tokens": old_tokens,
        "binding": binding,
        "teacher_condition": load(base / "preparation/condition.json"),
        "qualifications": [],
        "sessions": [],
        "exports": [],
        "transport_directories": [],
    }
    for label in ("B01", "B02"):
        source["qualifications"].append(load(analysis / f"qualifications/{label}.json"))
        source["sessions"].append(load(base / f"execution/sessions/{label}/runtime/session.json"))
        source["exports"].append(load(analysis / f"exports/{label}.json"))
        source["transport_directories"].append(base / f"execution/sessions/{label}/transport")
    require(
        dataset["candidate_count"] == len(dataset["rows"]) == 34
        and old_tokens["candidate_count"] == len(old_tokens["records"]) == 34
        and old_tokens["fit_count"] == 32
        and old_tokens["not_fit_count"] == 2
        and old_tokens["status"] == "contains_not_fit"
        and old_tokens["positive_representation_validated"] is False
        and old_tokens["maximum_sequence_length"] == 24_576
        and old_tokens["tokenizer_binding_id"] == binding["id"],
        "length.fixed_source_population",
    )
    require(
        [item["row_id"] for item in old_tokens["records"]]
        == [row["id"] for row in dataset["rows"]],
        "length.old_token_candidate_binding",
    )
    validate_candidates(source, dataset["rows"])
    return source


def validate_candidates(source: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Check accepted parent/content bindings, not numerical or model eligibility again."""
    expected = [row for exported in source["exports"] for row in exported["rows"]]
    require(
        canonical_json_bytes(rows) == canonical_json_bytes(expected),
        "length.original_candidate_content_or_order_changed",
    )
    require(len({row["id"] for row in rows}) == len(rows) == 34, "length.fixed_candidate_identity")
    checked = []
    for session, qualification, exported, directory in zip(
        source["sessions"],
        source["qualifications"],
        source["exports"],
        source["transport_directories"],
        strict=True,
    ):
        old_identity(qualification, "qualification")
        old_identity(exported, "supervision_export")
        original._session_binding(session, qualification)
        require(
            qualification["qualified"] is True
            and qualification["status"] == "success"
            and qualification["evidence_complete"] is True
            and qualification["export_eligible"] is True
            and exported["session_id"] == session["id"]
            and exported["qualification_id"] == qualification["id"],
            "length.existing_accepted_qualification_binding",
        )
        events, turns = session["events"], qualification["verified_turns"]
        require(
            len(events) == len(turns) == len(exported["rows"]) == 17
            and [event["sequence"] for event in events] == list(range(17))
            and [turn["turn_index"] for turn in turns] == list(range(17)),
            "length.complete_existing_session_binding",
        )
        for row, event, turn in zip(exported["rows"], events, turns, strict=True):
            original._candidate(row)
            messages, target = original._original_turn(session, event, turn, directory)
            require(
                row["messages"] == messages
                and row["target_text"] == target
                and row["session_id"] == session["id"]
                and row["qualification_id"] == qualification["id"]
                and row["turn_index"] == event["sequence"]
                and row["submission_kind"] == event["parsed"]["kind"]
                and all(row[name] == turn[name] for name in original.TURN_IDS)
                and event["receipt"]["admitted"] is True,
                "length.original_http_and_parent_binding",
            )
            checked.append(
                {
                    "candidate_id": row["id"],
                    "session_id": session["id"],
                    "turn_index": row["turn_index"],
                    "submission_kind": row["submission_kind"],
                    "public_request_id": row["public_request_id"],
                    "qualification_id": qualification["id"],
                    "messages_sha256": sha(canonical_json_bytes(messages)),
                    "target_raw_sha256": sha(target.encode("utf-8")),
                    "original_http_and_parent_binding_verified": True,
                }
            )
    return record("original_binding_checks", rows=checked, qualification_recomputed=False)
