"""Post-run, zero-HTTP replay; not a preregistered or independent evaluator.

This script never imports a training runner or changes the frozen Probe code.
It may create one explicitly requested, append-only audit record after verifying
all original public records, original qualifications, and token diagnostics.
"""

import argparse
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from multiprocessing import get_context
from pathlib import Path
from unittest.mock import patch

import httpx

from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage import (
    assessment,
    budget,
    metrics,
    study,
    transport,
)
from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage import protocol as p


def no_http(*args, **kwargs):
    raise AssertionError("postrun_replay_forbids_HTTP")


def reassess(job):
    with patch.object(httpx.Client, "send", no_http):
        with patch.object(transport.Provider, "__call__", no_http):
            return assessment.assess(*job)


def read(output, name, kind=None):
    value = json.loads((output / name).read_bytes())
    return p.checked(value, kind) if kind else value


def verify(code_root, data_root):
    code_root, data_root, output, _ = study.guarded_roots(code_root, data_root)
    freeze = read(output, "freeze.json", "coverage_freeze")
    report = read(output, "report.json", "probe_coverage_report")
    registry = read(output, "registry.json")
    p.validate_registry(registry, freeze["selected_tasks"], freeze["id"])
    study.verify_code(
        code_root,
        read(output, "code_snapshot.json", "probe_code_snapshot"),
        read(output, "original_code_dependencies.json", "original_code_dependencies"),
    )
    p.require(report["complete_registered_collection"], "audit_full_fixed_registry")
    ledger = budget.CoverageLedger(data_root / p.WALLET, freeze["id"])
    wallet = read(output, "wallet_after_generation.json", "probe_wallet_snapshot")
    finalization = read(output, "budget_finalization.json", "probe_budget_finalization")
    closed_wallet = p.record(
        "probe_wallet_snapshot",
        **{k: v for k, v in wallet.items() if k not in {"id", "schema_version", "persisted_stops"}},
        persisted_stops={
            **wallet["persisted_stops"],
            budget.FINAL: p.encode(finalization).decode(),
        },
    )
    p.require(ledger.snapshot() == closed_wallet, "audit_exact_postfinalization_wallet")
    journal = ledger.requests()
    p.require(journal == read(output, "probe_request_journal.json"), "audit_exact_request_journal")
    p.require(ledger.sessions() == read(output, "terminal_registry.json"), "audit_exact_terminals")
    before = read(output, "legacy_wallet_before.json", "legacy_wallet_snapshot")
    with ledger.connection(readonly=True) as db:
        db.execute("BEGIN")
        p.require(budget.legacy_snapshot(db, before) == before, "audit_legacy_rows_and_SQL")
        db.execute("COMMIT")
    p.require(
        finalization["purpose_closed"] and finalization["report_id"] == report["id"],
        "audit_closed_probe_purpose",
    )
    p.require(
        len(journal) == report["new_probe_requests"]
        and all(row["state"] == "settled" for row in journal),
        "audit_all_requests_known_and_settled",
    )
    requests, empty, usage_total = [], [], Counter()
    for row in journal:
        directory = "requests/" + row["request_id"]
        request = read(output, directory + "/request.json", "probe_public_request")
        response = read(output, directory + "/public_response.json", "probe_public_response")
        receipt = read(output, directory + "/receipt.json", "probe_request_receipt")
        body, raw = transport.render(request["body"]["messages"])
        usage = response["usage"]
        p.require(
            request["request_id"]
            == response["request_id"]
            == receipt["request_id"]
            == row["request_id"]
            and request["body"] == body
            and request["body_json"] == raw.decode()
            and request["body_sha256"] == p.sha(raw)
            and request["live_http_sender"] is True
            and request["freeze_id"] == freeze["id"]
            and request["session_id"] == row["session_id"]
            and request["attempt"] == row["attempt"]
            and response["http_status"] == 200
            and response["received_complete"] is True
            and response["response_model"] == row["response_model"] == p.MODEL
            and response["private_reasoning_text_saved"] is False
            and response["public_content_redacted"] is False
            and response["public_content_sha256"] == p.sha(response["public_content"])
            and response["original_public_content_bytes"]
            == len(response["public_content"].encode())
            and receipt["known_usage"] is True
            and receipt["live_http_sender"] is True
            and receipt["response_id"] == response["id"]
            and receipt["outcome"] == row["outcome"]
            and usage["prompt_tokens"] == row["prompt_tokens"]
            and usage["completion_tokens"] == row["completion_tokens"]
            and usage["total_tokens"] == row["charged_tokens"] == row["reported_total_tokens"]
            and usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"],
            "audit_every_HTTP200_including_rejected_public_content",
        )
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage_total[key] += usage[key]
        requests.append({"request_id": row["request_id"], "response_id": response["id"]})
        if not response["original_public_content_nonempty"]:
            p.require(
                response["public_content"] == ""
                and receipt["outcome"] == "response_contract_failure",
                "audit_empty_content_not_hidden_retry",
            )
            empty.append(
                {
                    "registered_session_id": row["session_id"],
                    "request_id": row["request_id"],
                    "attempt": row["attempt"],
                    "finish_reason": response["finish_reason"],
                    "public_bytes": response["original_public_content_bytes"],
                    "private_reasoning_present": response["private_reasoning_present"],
                    "usage": usage,
                }
            )
    p.require(usage_total["total_tokens"] == wallet["probe_conservative_debit"], "audit_debit_sum")
    pairs, results, mapping_pending, failed_semantics = [], [], [], []
    with ExitStack() as stack:
        selected, fixtures, dependencies = study._fixtures(stack, data_root)
        p.require(
            selected == freeze["selected_tasks"]
            and dependencies["id"] == freeze["parent_catalog_dependencies_id"],
            "audit_original_selection_sources_and_private_bundles",
        )
        jobs = []
        for reg in registry:
            directory = "sessions/" + reg["session_id"]
            session = read(output, directory + "/session.json", "probe_session")
            qualification = read(output, directory + "/qualification.json", "probe_qualification")
            origin = transport.verify_origin(session, ledger, output / "requests")
            p.require(origin == qualification["origin_verification"], "audit_exact_origin_replay")
            pairs.append((session, qualification))
            jobs.append((session, fixtures[reg["task_id"]], origin))
            results.append(
                {
                    "registered_session_id": reg["session_id"],
                    "session": session,
                    "qualification": qualification,
                    "status": "recorded",
                }
            )
            old = qualification["original_semantic_assessment"]
            if (
                qualification["actual_method"] == "movement"
                and not qualification["token_diagnostic_eligible"]
            ):
                mapping_pending.append(
                    {
                        "ordinal": reg["ordinal"],
                        "registered_session_id": reg["session_id"],
                        "task_id": reg["task_id"],
                        "financial_valid": qualification["financial_valid"],
                        "origin_status": origin["status"],
                        "full_mapping_status": qualification["full_mapping_status"],
                        "pending_reasons": old.get("full_mapping_pending_reasons", []),
                    }
                )
            if (
                reg["profile"] == "P2_method_delivery"
                and reg["basis"] == "movement"
                and not qualification["financial_valid"]
            ):
                failed_semantics.append(
                    {
                        "ordinal": reg["ordinal"],
                        "registered_session_id": reg["session_id"],
                        "task_id": reg["task_id"],
                        "reason": qualification["reason"],
                    }
                )
        with ProcessPoolExecutor(max_workers=4, mp_context=get_context("spawn")) as pool:
            for (_, expected), actual in zip(pairs, pool.map(reassess, jobs), strict=True):
                p.require(actual == expected, "audit_every_original_qualification_rebuilt")
    tokens = assessment.token_diagnostics(pairs, data_root, complete_registry=True)
    p.require(tokens == read(output, "token_diagnostics.json"), "audit_all_token_packages_rebuilt")
    summary = metrics.summarize(registry, results, tokens)
    p.require(
        summary == read(output, "coverage_metrics.json"), "audit_all_registered_metrics_rebuilt"
    )
    protected = [study.source_snapshot(Path(root)) for root in study.PROTECTED]
    p.require(
        protected
        == read(output, "protected_sources_before.json")
        == read(output, "protected_sources_after.json"),
        "audit_original_four_worktrees_unchanged",
    )
    p.require(
        ledger.snapshot() == closed_wallet and ledger.requests() == journal,
        "audit_zero_wallet_writes",
    )
    return p.record(
        "postrun_replay_audit",
        report_id=report["id"],
        freeze_id=freeze["id"],
        script_sha256=p.sha(Path(__file__).resolve()),
        preregistered_evaluator_or_independent_review=False,
        same_frozen_implementation_recomputed_without_new_HTTP=True,
        HTTP_requests_during_audit=0,
        wallet_writes_during_audit=0,
        Student_or_GPU_operations=0,
        verified_request_count=len(requests),
        request_identities_sha256=p.sha(p.encode(requests)),
        usage_totals=dict(usage_total),
        empty_content_terminals=empty,
        original_qualification_replays=len(pairs),
        token_packages_rebuilt=len(tokens["packages"]),
        token_response_checks_rebuilt=sum(len(x["checks"]) for x in tokens["packages"]),
        metrics_byte_identical=True,
        movement_financial_but_mapping_pending=mapping_pending,
        P2_movement_guidance_financial_failures=failed_semantics,
        original_four_worktrees_unchanged=True,
        original_wallet_rows_and_trigger_SQL_unchanged=True,
        postfinalization_wallet_id=closed_wallet["id"],
        postfinalization_only_added_exact_purpose_closure_marker=True,
        training_admitted=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    with patch.object(httpx.Client, "send", no_http):
        with patch.object(transport.Provider, "__call__", no_http):
            value = verify(args.code_root, args.data_root)
    path = args.code_root / p.OUTPUT / "postrun_replay_audit.json"
    if path.exists():
        p.require(read(path.parent, path.name) == value, "same_existing_postrun_audit")
    elif args.write_report:
        p.write_once(path, value)
    print(
        json.dumps(
            {
                "id": value["id"],
                "requests": value["verified_request_count"],
                "sessions": value["original_qualification_replays"],
                "HTTP_requests_during_audit": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
