"""Prospective wire-byte capacity correction; no semantic or sample change.

The inherited text execution and all saved reviews retain their identity. This
separate operational receipt changes only the serialized request guard. Exact
wire bodies, reservations, response checking, API ceilings and selection stay.
"""

import argparse
import subprocess
import types
from pathlib import Path

import cross_market_repaired_geometry_execution_20260926 as isolation
import run_cross_market_text_mainline_20260927 as original

base = original.base
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_text_capacity_revision_20260927.py"
RECORD = original.RAW / "request_capacity_revision_01.json"
KIND = "cross_market_text_request_capacity_revision"
MAX_REQUEST_BYTES = 262144


def transport_namespace(revision_reference):
    old = original.transport
    globals_copy = {**vars(old), "MAX_REQUEST_BYTES": MAX_REQUEST_BYTES}
    request_bytes = types.FunctionType(
        old.request_bytes.__code__,
        globals_copy,
        old.request_bytes.__name__,
        old.request_bytes.__defaults__,
    )
    globals_copy["request_bytes"] = request_bytes
    invoke = types.FunctionType(old.Provider.__call__.__code__, globals_copy, "__call__")

    class CapacityProvider(old.Provider):
        def __call__(self, request):
            base.write(self.output / "capacity_revision_binding.json", revision_reference)
            return invoke(self, request)

    return types.SimpleNamespace(
        **{**vars(old), "request_bytes": request_bytes, "Provider": CapacityProvider}
    )


def register(root):
    if RECORD.exists():
        return revision(root)
    parent = original.protocol(root)
    prior_stop = base.read(original.RAW / "status.json")
    base.require(
        prior_stop["state"] == "TEXT_REVIEW_TECHNICAL_PENDING"
        and prior_stop["saved_packet_reviews"] == 39
        and len(prior_stop["failed_packet_ids"]) == 1,
        "request_capacity.exact_preserved_pretransport_stop",
    )
    failed = prior_stop["failed_packet_ids"][0]
    base.require(
        not (original.RAW / "attempts" / original.key_for(failed)).exists(),
        "request_capacity.stopped_packet_not_sent_or_reserved",
    )
    saved = sorted((original.RAW / "packet_reviews").glob("*.json"))
    base.require(len(saved) == 39, "request_capacity.exact_saved_semantic_credit")
    stop_path = original.RAW / "request_capacity_prior_stop_01.json"
    base.write(stop_path, prior_stop)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    payload = (root / SCRIPT).read_bytes()
    base.require(
        payload == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "request_capacity.committed_operational_revision",
    )
    value = base.record(
        KIND,
        at=base.now(),
        code_commit=head,
        sources={SCRIPT: base.sha(payload)},
        parent_protocol=original.ref(original.RAW / "protocol.json"),
        parent_protocol_id=parent["id"],
        prior_stop=original.ref(stop_path),
        preserved_packet_reviews=[original.ref(path) for path in saved],
        previous_maximum_request_bytes=original.transport.MAX_REQUEST_BYTES,
        maximum_request_bytes=MAX_REQUEST_BYTES,
        reason="A lossless source packet with 2,267 real lines serializes to 144,747 bytes; "
        "the old 131,072-byte engineering guard rejected it before any HTTP request.",
        full_universe_size_check=dict(
            packets=5663,
            maximum_actual_request_bytes=182575,
            over_old_guard=108,
            over_revised_guard=0,
            API_calls=0,
            source_characters_changed=False,
        ),
        unchanged="All original characters, line IDs, semantic prompt, fixed model, response "
        "schema, output/context usage guards, attempts, 16-way concurrency, deterministic "
        "source frontier, financial eligibility, panel controls and scientific design.",
        additional_API_budget=0,
        refunded_attempts=0,
        old_results_rewritten=False,
        original_transport_module_mutated=False,
        operational_scope="New future Provider calls use one isolated code namespace with "
        "the larger wire-byte guard; every attempt gets this revision reference before POST.",
    )
    base.write(RECORD, value)
    base.emit(
        dict(
            event="text_request_capacity_registered",
            revision_id=value["id"],
            preserved_reviews=39,
            maximum_request_bytes=MAX_REQUEST_BYTES,
        )
    )
    return value


def revision(root):
    value = base.checked(base.read(RECORD), KIND)
    parent = original.protocol(root)
    base.require(
        value["parent_protocol_id"] == parent["id"]
        and value["parent_protocol"] == original.ref(original.RAW / "protocol.json")
        and value["maximum_request_bytes"] == MAX_REQUEST_BYTES,
        "request_capacity.exact_parent_and_guard",
    )
    for name, digest in value["sources"].items():
        base.require(base.sha(root / name) == digest, "request_capacity.frozen_code")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "start", "run", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action == "register":
        register(root)
        return
    revision(root)
    namespace = isolation.isolated_namespace(
        original, transport=transport_namespace(original.ref(RECORD)), SCRIPT=SCRIPT
    )
    if args.action == "status":
        base.emit(base.read(original.RAW / "status.json"))
    else:
        namespace[args.action](root)


if __name__ == "__main__":
    main()
