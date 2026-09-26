"""Bind the frozen manifest year to the existing parser's documented metadata key.

The first complete pass is preserved. Every one of the same 440 PDFs receives one
corrected pass, not only documents selected because they yielded zero candidates.
No source, parser numerical rule, model, task quota or financial gate changes.
"""

import argparse
import copy
import os
import subprocess
import sys
from pathlib import Path
from types import FunctionType, SimpleNamespace

import prepare_cross_market_sources_20260926 as base

SCRIPT = "trusted_data_synthesis/scripts/repair_cross_market_period_metadata_20260926.py"
RAW = base.RAW / "period_metadata_revision_01"
_namespace = None


def corrected_inventory(inventory):
    result = copy.deepcopy(inventory)
    for security in result["roster"]:
        for doc in security["documents"]:
            base.require(
                str(doc["metadata"]["year"]) == str(doc["year"]), "same_original_manifest_year"
            )
            base.require("record_period_hint" not in doc["metadata"], "only_missing_key_repaired")
            doc["metadata"]["record_period_hint"] = str(doc["year"])
    return result


def helpers():
    global _namespace
    if _namespace is None:
        namespace = {**vars(base), "RAW": RAW, "protocol": protocol, "document_job": document_job}
        for name in ("write", "summarize", "run"):
            function = getattr(base, name)
            namespace[name] = FunctionType(
                function.__code__,
                namespace,
                function.__name__,
                function.__defaults__,
                function.__closure__,
            )
        function = base.document_job
        namespace["corrected_document_job"] = FunctionType(
            function.__code__,
            namespace,
            function.__name__,
            function.__defaults__,
            function.__closure__,
        )
        _namespace = SimpleNamespace(**namespace)
    return _namespace


def document_job(plan, doc):
    # This top-level function remains pickleable for spawn ProcessPool workers.
    return helpers().corrected_document_job(plan, doc)


def protocol(root):
    parent = base.protocol(root)
    value = base.checked(base.read(RAW / "protocol.json"), "cross_market_period_metadata_revision")
    base.require(
        value["parent_protocol_id"] == parent["id"]
        and value["metadata_inventory"] == corrected_inventory(parent["metadata_inventory"])
        and value["parser_attempts_per_document"] == 1
        and value["total_parser_attempt_cap"] == value["document_count"] == parent["document_count"]
        and value["workers"] == parent["workers"] == 8
        and value["evaluation_authorized"] is False
        and value["new_training_updates"] == 0
        and base.read(base.RAW / "budget.json")["parser_attempts"] == parent["document_count"]
        and value["first_pass_summary_sha256"] == base.sha(base.RAW / "extraction_summary.json")
        and value["adapter_sha256"] == base.sha(root / SCRIPT),
        "frozen_period_metadata_execution_revision",
    )
    for key in (
        "sources",
        "package_versions",
        "python_version",
        "readiness_gates",
        "prospective_evaluation",
        "maximum_statement_pages",
        "maximum_unit_carry_pages",
        "maximum_statement_carry_pages",
        "maximum_result_bytes",
        "source_policy",
        "training_completion_sha256",
    ):
        base.require(value[key] == parent[key], "unchanged_revision_field:" + key)
    return value


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    parent = base.protocol(root)
    previous = base.checked(
        base.read(base.RAW / "extraction_summary.json"),
        "cross_market_source_qualification_completed",
    )
    base.require(
        previous["protocol_id"] == parent["id"]
        and previous["documents"] == parent["document_count"]
        and base.read(base.RAW / "budget.json")["parser_attempts"] == parent["document_count"],
        "first_complete_pass_only_one_attempt_per_document",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    payload = (root / SCRIPT).read_bytes()
    base.require(
        payload == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "committed_execution_repair",
    )
    fields = {k: v for k, v in parent.items() if k not in ("id", "schema_version")}
    fields.update(
        parent_protocol_id=parent["id"],
        first_pass_summary_id=previous["id"],
        first_pass_summary_sha256=base.sha(base.RAW / "extraction_summary.json"),
        code_commit=head,
        adapter_sha256=base.sha(payload),
        repair=(
            "manifest year -> parser record_period_hint; "
            "all same documents; no numerical rule change"
        ),
        metadata_inventory=corrected_inventory(parent["metadata_inventory"]),
        parser_attempts_per_document=1,
        total_parser_attempt_cap=parent["document_count"],
        cumulative_parser_attempt_cap=parent["total_parser_attempt_cap"],
        first_pass_attempts_preserved=parent["document_count"],
        at=base.now(),
    )
    plan = base.record("cross_market_period_metadata_revision", **fields)
    helpers().write(RAW / "protocol.json", plan)
    base.emit(
        dict(
            event="cross_market_period_metadata_revision_registered",
            id=plan["id"],
            documents=plan["document_count"],
        )
    )
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("register", "start", "run"), required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "register":
        register(root)
    elif args.mode == "start":
        protocol(root)
        with base.locked(RAW / "start.lock"):
            launch = base.read(RAW / "launch.json") if (RAW / "launch.json").exists() else None
            if launch:
                proc = Path("/proc") / str(launch["pid"]) / "stat"
                if (
                    proc.exists()
                    and proc.read_text().rsplit(")", 1)[1].split()[19] == launch["start_ticks"]
                ):
                    base.emit(
                        dict(event="cross_market_revision_already_running", pid=launch["pid"])
                    )
                    return
            env = dict(
                os.environ,
                CUDA_VISIBLE_DEVICES="",
                OMP_NUM_THREADS="1",
                OPENBLAS_NUM_THREADS="1",
                MKL_NUM_THREADS="1",
            )
            with (RAW / "run.log").open("ab") as log:
                child = subprocess.Popen(
                    [sys.executable, str(root / SCRIPT), "--root", str(root), "--mode", "run"],
                    cwd=root,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            ticks = (
                (Path("/proc") / str(child.pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]
            )
            helpers().write(
                RAW / "launch.json",
                dict(pid=child.pid, start_ticks=ticks, at=base.now()),
                immutable=False,
            )
            base.emit(dict(event="cross_market_period_metadata_revision_started", pid=child.pid))
    else:
        try:
            helpers().run(root)
        except Exception as error:
            helpers().write(
                RAW / "needs_attention.json",
                dict(error=repr(error), at=base.now()),
                immutable=False,
            )
            raise


if __name__ == "__main__":
    main()
