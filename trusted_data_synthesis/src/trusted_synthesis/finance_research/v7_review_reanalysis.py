"""Immutable, offline correction of typed-review binding checks; never a paid retry.

Original requests, responses, assessments, stop records and the shared budget are
read-only. Publication creates a separate no-replace evidence directory. Bundled
original request/response objects make the corrected assessments replayable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pydantic

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from .contracts import digest
from .semantic_review import _strict_json
from .storage import encode
from .v7_slot_review import _checked_request, inspect_slot_review

SCHEMA = "v7_typed_review_offline_binding_correction.v1"
DEFAULT_NAME = "offline_binding_correction_01"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _bound(value):
    return value | {"id": digest(value)}


def _check_bound(value):
    _require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "original artifact identity mismatch",
    )


def source_binding(*, require_committed=False):
    """Exact validator closure and current checkout commit; no package/API calls."""
    here = Path(__file__).resolve().parent
    root = here.parents[3]
    names = (
        "v7_review_reanalysis.py",
        "v7_slot_review.py",
        "v6_slot_review.py",
        "v6_compact_review.py",
        "semantic_review.py",
        "contracts.py",
        "storage.py",
    )
    paths = [here / name for name in names]
    paths.append(here.parent / "core/immutable_artifacts.py")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    files, committed = {}, {}
    for path in paths:
        relative = str(path.relative_to(root))
        raw = path.read_bytes()
        files[relative] = _sha(raw)
        checked = subprocess.run(
            ["git", "show", f"{head}:{relative}"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        committed[relative] = checked.returncode == 0 and checked.stdout == raw
    if require_committed:
        _require(
            all(committed.values()), "commit exact offline-correction source before publication"
        )
    return _bound(
        dict(
            source_commit=head,
            file_sha256=files,
            files_match_commit=committed,
            all_source_files_committed=all(committed.values()),
            python=sys.version,
            pydantic=pydantic.__version__,
        )
    )


def _wire_check(request, response, registered_request_sha256):
    """Reconstruct the original documented transport body without sending it."""
    _require(
        digest(request) == registered_request_sha256 == response["semantic_review_request_sha256"],
        "original request differs from registration or response binding",
    )
    _require(
        request["wire_protocol"] == response["wire_protocol"] == "v6_slot_review.v4",
        "offline correction only handles original typed v4 slot requests",
    )
    _checked_request(request)
    body = dict(
        model="deepseek-flash",
        messages=request["messages"],
        temperature=0,
        top_p=1,
        max_tokens=request["max_output_tokens"],
        thinking={"type": "disabled"},
        stream=False,
        tools=[request["strict_tool"]],
        tool_choice={"type": "function", "function": {"name": "submit_review"}},
    )
    _require(response["public_request"] == body, "rebuilt wire body differs from actual sent body")
    wire_hash = digest(body)
    _require(
        response["public_request_body_sha256"] == response["request_sha256"] == wire_hash,
        "original wire-body hash mismatch",
    )
    raw_response = response["api_response_raw"]
    _require(
        _sha(raw_response.encode()) == response["raw_api_response_sha256"],
        "original API response bytes changed",
    )
    envelope = _strict_json(raw_response)
    _require(envelope == response["api_response"], "raw/parsed API response differs")
    choices = envelope["choices"]
    _require(len(choices) == 1, "original response has ambiguous choices")
    calls = choices[0]["message"]["tool_calls"]
    _require(
        len(calls) == 1
        and calls[0]["function"]["name"] == "submit_review"
        and calls[0]["function"]["arguments"] == response["review_text"]
        and choices[0]["finish_reason"] == response["finish_reason"],
        "corrected review text is not the original function arguments",
    )
    return dict(
        rebuilt_wire_same=True,
        original_typed_locators_same=True,
        registered_request_sha256=registered_request_sha256,
        original_wire_sha256=wire_hash,
        original_raw_api_response_sha256=response["raw_api_response_sha256"],
        original_raw_arguments_sha256=_sha(response["review_text"].encode()),
        no_model_call_or_argument_repair=True,
    )


def semantic_diagnostics(assessment):
    """Report literal model-record inconsistencies; do not repair or rejudge them."""
    validation = assessment.get("validation")
    if validation is None:
        return None
    slot, terms = validation["parsed"]["slot"], validation["parsed"]["terms"]
    docs = validation["document_index"]
    props = {p["proposition_id"]: p for p in slot["propositions"]}
    nodes = {n["node_id"]: n for n in slot["semantic_graph"]["nodes"]}
    term_ids = {t["term_id"] for t in terms}
    unbound_spans = []
    for span in slot["mask"]:
        if span["label"] == "approved" and not span["proposition_ids"]:
            unbound_spans.append(
                dict(
                    doc_id=span["doc_id"],
                    start=span["start"],
                    end=span["end"],
                    quote=span["quote"],
                    kind=docs[span["doc_id"]]["kind"],
                    proposition_ids=[],
                )
            )
    return dict(
        approved_spans_without_proposition_ids=unbound_spans,
        graph_edges_naming_absent_nodes=sorted(
            {
                edge[key]
                for edge in slot["semantic_graph"]["edges"]
                for key in ("from_node", "to_node")
                if edge[key] not in nodes
            }
        ),
        graph_nodes_naming_absent_terms=sorted(
            {name for node in nodes.values() for name in node["term_ids"] if name not in term_ids}
        ),
        graph_nodes_without_terms=[n["node_id"] for n in nodes.values() if not n["term_ids"]],
        terms_without_public_source_anchors=[
            t["term_id"] for t in terms if not t["source_doc_ids"]
        ],
        approved_spans_citing_unresolved_or_retracted_propositions=[
            dict(
                doc_id=s["doc_id"],
                start=s["start"],
                end=s["end"],
                proposition_ids=[
                    key
                    for key in s["proposition_ids"]
                    if key in props
                    and (
                        props[key]["judgment"] != "supported" or props[key]["status"] == "retracted"
                    )
                ],
            )
            for s in slot["mask"]
            if s["label"] == "approved"
            and any(
                key in props
                and (props[key]["judgment"] != "supported" or props[key]["status"] == "retracted")
                for key in s["proposition_ids"]
            )
        ],
        diagnostic_not_a_new_semantic_verdict=True,
        no_positive_qualification_relaxed=True,
    )


def _summary(cases):
    errors = Counter(
        (c["corrected_assessment"].get("error_kind"), c["corrected_assessment"].get("error"))
        for c in cases
    )
    count = len(cases)
    passed = sum(c["corrected_assessment"]["interface_admitted"] for c in cases)
    return dict(
        original_response_denominator=count,
        interface_admitted=passed,
        interface_admission_fraction=passed / count if count else None,
        semantic_consistent=sum(c["corrected_assessment"]["semantic_consistent"] for c in cases),
        output_truncated=sum(c["original_response"]["finish_reason"] == "length" for c in cases),
        actual_api_calls_added=0,
        GPU_calls_added=0,
        original_spend_or_unknown_reservations_changed=False,
        original_gate_or_halt_superseded=False,
        training_admitted=False,
        errors=[
            dict(kind=key[0], error=key[1], count=value)
            for key, value in sorted(errors.items(), key=lambda x: str(x[0]))
        ],
    )


def analyze_revision(revision_root, *, require_committed=False):
    root = Path(revision_root).resolve()
    binding = source_binding(require_committed=require_committed)
    originals = {}

    def original(relative):
        path = root / relative
        raw = path.read_bytes()
        originals[str(relative)] = dict(sha256=_sha(raw), bytes=len(raw))
        return _strict_json(raw.decode())

    protocol = original("registration/protocol.json")
    _check_bound(protocol)
    job_map = {j["key"]: j for j in protocol["jobs"]}
    requests, request_sources = {}, {}
    for path in sorted((root / "slot_inputs").glob("*/record.json")):
        relative = str(path.relative_to(root))
        value = original(relative)
        _check_bound(value)
        registered = protocol["slot_inputs"][value["task_id"]]
        _require(
            registered == dict(id=value["id"], sha256=originals[relative]["sha256"]),
            "original slot-input artifact differs from protocol",
        )
        for key, request in value["requests"].items():
            _require(key not in requests, "duplicate original review request")
            requests[key], request_sources[key] = request, relative
    controls = {}
    for relative in ("technical_gate/record.json", "dispatch_stop/record.json"):
        if (root / relative).exists():
            controls[relative] = original(relative)
            if "id" in controls[relative]:
                _check_bound(controls[relative])
    gate = controls["technical_gate/record.json"]
    _require(gate["protocol_id"] == protocol["id"], "original gate names another protocol")
    cases = []
    for path in sorted((root / "jobs").glob("slot_*/response/record.json")):
        directory = path.parent.parent
        key = directory.name.replace("slot_", "slot:", 1)
        job, request = job_map[key], requests[key]
        relative = str(path.relative_to(root))
        response = original(relative)
        _require(
            gate["actual_review_hashes"].get(key) == digest(response),
            "original response differs from the original sealed gate",
        )
        old_assessment_relative = str((directory / "assessment/record.json").relative_to(root))
        old_assessment = original(old_assessment_relative)
        started = directory / "started/record.json"
        if started.exists():
            original(str(started.relative_to(root)))
        wire = _wire_check(request, response, job["request_sha256"])
        corrected = inspect_slot_review(response["review_text"], request)
        cases.append(
            _bound(
                dict(
                    key=key,
                    task_id=job["task_id"],
                    slot_id=job["slot_id"],
                    reviewer=job["reviewer"],
                    original_request=request,
                    original_response=response,
                    original_assessment=old_assessment,
                    original_artifacts=dict(
                        input=request_sources[key],
                        response=relative,
                        assessment=old_assessment_relative,
                    ),
                    wire_binding=wire,
                    corrected_assessment=corrected,
                    semantic_diagnostics=semantic_diagnostics(corrected),
                )
            )
        )
    _require(cases, "no original typed slot responses to correct")
    _require(
        {case["key"] for case in cases} == set(gate["actual_review_hashes"]),
        "offline correction must retain every original gate response, without selection",
    )
    # Protect the audit against concurrently changed originals or validator files.
    for relative, info in originals.items():
        _require(
            _sha((root / relative).read_bytes()) == info["sha256"],
            "original audit artifact changed during offline read",
        )
    _require(
        source_binding(require_committed=require_committed) == binding,
        "offline validator source changed during reanalysis",
    )
    return dict(
        schema=SCHEMA,
        revision_root=str(root),
        source_binding=binding,
        original_protocol=protocol,
        original_protocol_id=protocol["id"],
        original_registration_source_commit=protocol["source_commit"],
        original_artifact_files=originals,
        original_control_records=controls,
        correction_scope="host-only deterministic persisted-catalog order restoration",
        no_original_artifact_modified=True,
        no_paid_retry=True,
        budget_not_opened=True,
        no_halt_release=True,
        summary=_summary(cases),
        cases=cases,
    )


def publish_correction(revision_root, output=None):
    root = Path(revision_root).resolve()
    output = Path(output).resolve() if output is not None else root / DEFAULT_NAME
    _require(
        output.parent == root and output.name.startswith("offline_binding_correction_"),
        "publish only a separate offline_binding_correction_* sibling directory",
    )
    _require(not output.exists(), "never overwrite an original or prior correction artifact")
    result = analyze_revision(root, require_committed=True)
    cases = result.pop("cases")
    cases_bytes = encode(cases)
    result["corrected_cases_file"] = dict(
        path="corrected_cases.json", sha256=_sha(cases_bytes), bytes=len(cases_bytes)
    )
    record = _bound(result)
    write_immutable_artifact_directory(
        output,
        {
            "record.json": encode(record),
            "corrected_cases.json": cases_bytes,
        },
    )
    return record


def replay_correction(output, *, verify_original_files=True):
    path = Path(output)
    record = _strict_json((path / "record.json").read_text())
    _check_bound(record)
    current = source_binding()
    for name in ("file_sha256", "python", "pydantic"):
        _require(
            current[name] == record["source_binding"][name],
            "replay requires the recorded validator sources/runtime",
        )
    raw = (path / record["corrected_cases_file"]["path"]).read_bytes()
    _require(_sha(raw) == record["corrected_cases_file"]["sha256"], "corrected-case file changed")
    cases = _strict_json(raw.decode())
    for case in cases:
        _check_bound(case)
        request, response = case["original_request"], case["original_response"]
        wire = _wire_check(request, response, case["wire_binding"]["registered_request_sha256"])
        actual = inspect_slot_review(response["review_text"], request)
        _require(
            wire == case["wire_binding"]
            and actual == case["corrected_assessment"]
            and semantic_diagnostics(actual) == case["semantic_diagnostics"],
            "corrected result does not replay from the original request/response",
        )
    _require(_summary(cases) == record["summary"], "corrected summary changed")
    if verify_original_files:
        root = Path(record["revision_root"])
        for relative, info in record["original_artifact_files"].items():
            _require(
                _sha((root / relative).read_bytes()) == info["sha256"],
                "an original artifact no longer matches the correction evidence",
            )
    return dict(
        correction_id=record["id"],
        replayed=True,
        summary=record["summary"],
        original_files_verified=verify_original_files,
        actual_api_calls_added=0,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "publish", "replay"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.action == "inspect":
        value = analyze_revision(args.path)
        print(json.dumps(dict(summary=value["summary"], source_binding=value["source_binding"])))
    elif args.action == "publish":
        value = publish_correction(args.path, args.output)
        print(json.dumps(dict(correction_id=value["id"], summary=value["summary"])))
    else:
        print(json.dumps(replay_correction(args.path)))


if __name__ == "__main__":
    main()
