"""One frozen 24-call calibration; bounded parallel pairs, no feedback retries."""

from __future__ import annotations

import argparse
import importlib.metadata
import platform
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification as proof
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import sha
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.runner import _credential
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    OnlineModelCallback,
    OnlineTransportError,
    render_http_request,
)

from .evidence import audit_call, summarize
from .models import configuration, read, record
from .plan import prepare, prepared


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unknown(reg: dict[str, Any], *, started: bool, code: str) -> dict[str, Any]:
    return record(
        "unscored_call",
        label=reg["label"],
        registration_id=reg["id"],
        started=started,
        status="unknown" if started else "not_started",
        Y=None,
        evidence_complete=False,
        code=code,
    )


def _call(
    root: Path, prep: Path, store: DurableStore, reg: dict[str, Any], key: str
) -> dict[str, Any]:
    label = reg["label"]
    public = read(prep / f"requests/{label}.json")
    http = read(prep / f"http/{label}.json")
    require(
        sha(canonical_json_bytes(public)) == reg["public_request_sha256"]
        and public["id"] == reg["public_request_id"]
        and http
        == render_http_request(
            public, configuration(), session_id=reg["session_id"], attempt_index=0
        ),
        "calibration.immediate_precall_frozen_request",
    )
    directory = store.root / "calls" / label
    call_store = DurableStore(directory)
    call_store.json(
        "start.json",
        record("call_start", registration_id=reg["id"], label=label, started_at_utc=_now()),
    )
    callback = None
    error_type = None
    returned = None
    try:
        callback = OnlineModelCallback(
            configuration(),
            session_id=reg["session_id"],
            evidence_directory=directory / "transport",
            api_key=key,
        )
        returned = callback.generate(public)
        call_store.write("returned_content.txt", returned)
    except OnlineTransportError:
        pass  # The actual failure is reconstructed independently from the saved HTTP evidence.
    except Exception as error:
        error_type = type(error).__name__  # Never serialize exception text (may contain secrets).
    finally:
        if callback is not None:
            try:
                callback.finalize()
            except Exception as error:
                error_type = type(error).__name__
    try:
        require(error_type is None, "calibration.internal_implementation_failure")
        audit = audit_call(
            root,
            directory / "transport",
            reg,
            public,
            http,
        )
        evaluation = audit["evaluation"]
        require((evaluation is None) == (returned is None), "calibration.callback_return_binding")
        if returned is not None:
            require(
                sha(returned) == evaluation["raw_sha256"], "calibration.original_response_binding"
            )
    except Exception as error:
        audit = _unknown(reg, started=True, code="calibration.evidence_or_internal_failure")
        audit = record(
            "unscored_call_detail",
            unscored=audit,
            **{
                key_: value for key_, value in audit.items() if key_ not in {"id", "schema_version"}
            },
            exception_type=error_type or type(error).__name__,
        )
    call_store.json("audit.json", audit)
    call_store.json(
        "completion.json",
        record(
            "call_completion",
            registration_id=reg["id"],
            completed_at_utc=_now(),
            audit_id=audit["id"],
        ),
    )
    seal_directory(call_store, kind="update_calibration_call_manifest", audit_id=audit["id"])
    return audit


def run(root: Path, prep: Path) -> dict[str, Any]:
    frozen = prepared(root, prep)
    registrations = frozen["registrations"]
    directory = prep.parent / "execution"
    require(not directory.exists(), "calibration.no_resume_or_replacement")
    key = _credential(root / "trusted_data_synthesis/.env")
    store = DurableStore(directory)
    store.json(
        "run_binding.json",
        record(
            "run_binding",
            preparation_manifest_id=frozen["manifest"]["id"],
            condition_id=frozen["condition"]["id"],
            implementation_id=frozen["implementation"]["id"],
            started_at_utc=_now(),
            python_version=platform.python_version(),
            software={name: importlib.metadata.version(name) for name in ("pydantic", "httpx")},
            origin="live_http",
            authorized_stage_only=True,
        ),
    )
    audits: dict[str, dict[str, Any]] = {}
    halt = False

    def pair(regs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        results = {}
        failed = False
        for reg in regs:
            if failed:
                audit = _unknown(reg, started=False, code="calibration.pair_integrity_halt")
                store.json(f"not_started/{reg['label']}.json", audit)
            else:
                try:
                    audit = _call(root, prep, store, reg, key)
                except Exception as error:
                    audit = _unknown(reg, started=True, code="calibration.call_storage_failure")
                    store.json(
                        f"unknown/{reg['label']}.json",
                        {
                            **audit,
                            "exception_type": type(error).__name__,
                        },
                    )
                failed = not audit["evidence_complete"] or audit.get(
                    "implementation_failure", False
                )
            results[reg["label"]] = audit
        return results

    for round_ in range(1, 5):
        rows = [reg for reg in registrations if reg["round"] == round_]
        if halt:
            for reg in rows:
                audit = _unknown(reg, started=False, code="calibration.future_round_integrity_halt")
                store.json(f"not_started/{reg['label']}.json", audit)
                audits[reg["label"]] = audit
            continue
        # Recheck source, historical immutability, and exact frozen HTTP bytes before each round.
        try:
            prepared(root, prep)
        except Exception:
            halt = True
            for reg in rows:
                audit = _unknown(reg, started=False, code="calibration.precall_integrity_halt")
                store.json(f"not_started/{reg['label']}.json", audit)
                audits[reg["label"]] = audit
            continue
        store.json(
            f"rounds/{round_:02d}_start.json",
            record(
                "round_start",
                round=round_,
                started_at_utc=_now(),
                labels=[reg["label"] for reg in rows],
            ),
        )
        pairs = [[reg for reg in rows if reg["task_group"] == group] for group in "CBS"]
        with ThreadPoolExecutor(max_workers=3) as pool:
            for results in pool.map(pair, pairs):
                audits.update(results)
        halt = any(
            not audits[reg["label"]]["evidence_complete"]
            or audits[reg["label"]].get("implementation_failure", False)
            for reg in rows
        )
        store.json(
            f"rounds/{round_:02d}_completion.json",
            record(
                "round_completion",
                round=round_,
                completed_at_utc=_now(),
                halt_future_rounds=halt,
                audit_ids=[audits[reg["label"]]["id"] for reg in rows],
            ),
        )
        print(f"calibration round {round_}/4 complete; integrity_halt={halt}", flush=True)
    report = summarize(registrations, audits)
    store.json("audits.json", audits)
    store.json("report.json", report)
    seal_directory(store, kind="update_calibration_execution_manifest", report_id=report["id"])
    return report


def analyze(root: Path, prep: Path, output: Path) -> dict[str, Any]:
    """Read-only rebuild: no model, credential, Action executor or Runtime construction."""
    frozen = prepared(root, prep)
    execution = prep.parent / "execution"
    files = proof._Artifacts(execution)
    binding = files.json("run_binding.json")
    require(
        binding["preparation_manifest_id"] == frozen["manifest"]["id"]
        and binding["implementation_id"] == frozen["implementation"]["id"],
        "calibration.run_preparation_binding",
    )
    audits = read(execution / "audits.json")
    for reg in frozen["registrations"]:
        label = reg["label"]
        saved = audits[label]
        if saved["evidence_complete"]:
            call = proof._Artifacts(execution / "calls" / label)
            computed = audit_call(
                root,
                execution / "calls" / label / "transport",
                reg,
                read(prep / f"requests/{label}.json"),
                read(prep / f"http/{label}.json"),
            )
            require(saved == computed == call.json("audit.json"), "calibration.audit_reproduction")
            if computed["evaluation"] is not None:
                require(
                    call.raw("returned_content.txt")
                    == (
                        execution / "calls" / label / "transport/attempts/000_public_content.txt"
                    ).read_bytes(),
                    "calibration.returned_content_readback",
                )
            start, completed = call.json("start.json"), call.json("completion.json")
            require(
                start["registration_id"] == completed["registration_id"] == reg["id"]
                and start["started_at_utc"] <= completed["completed_at_utc"],
                "calibration.call_lifecycle",
            )
        else:
            require(saved["Y"] is None, "calibration.unknown_not_false")
            proof._identity(saved)
    for group in "CBS":
        for round_ in range(1, 5):
            pair = [
                r
                for r in frozen["registrations"]
                if r["task_group"] == group and r["round"] == round_
            ]
            if all(audits[r["label"]]["evidence_complete"] for r in pair):
                first = read(execution / "calls" / pair[0]["label"] / "completion.json")
                second = read(execution / "calls" / pair[1]["label"] / "start.json")
                require(
                    first["completed_at_utc"] <= second["started_at_utc"],
                    "calibration.counterbalanced_sequential_pair",
                )
    report = summarize(frozen["registrations"], audits)
    require(report == files.json("report.json"), "calibration.summary_reproduction")
    store = DurableStore(output)
    store.json("report.json", report)
    store.json("audits.json", audits)
    seal_directory(store, kind="update_calibration_reanalysis_manifest", report_id=report["id"])
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "analyze"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--design", type=Path)
    parser.add_argument("--run-tag", default="update_public_contract_v1_20260906")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        require(args.design is not None, "calibration.design_required")
        result = prepare(args.root, args.preparation, args.design, run_tag=args.run_tag)
    elif args.command == "run":
        result = run(args.root, args.preparation)
    else:
        require(args.output is not None, "calibration.analysis_output_required")
        result = analyze(args.root, args.preparation, args.output)
    print(canonical_json_bytes(result).decode())


if __name__ == "__main__":
    main()
