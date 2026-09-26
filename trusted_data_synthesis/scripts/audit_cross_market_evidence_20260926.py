"""Finite offline PDF evidence audit; neither fact promotion nor model evaluation.

Keep the two completed financial-parser passes immutable. This separately
registered pass reads each original PDF once for page text and checks cached
candidates against it. Identity snippets, period phrases and arithmetic closure
are review aids, NOT an issuer registry, financial certificate or scoring gold.
"""

import argparse
import importlib.metadata
import multiprocessing
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import prepare_cross_market_sources_20260926 as base

RAW = base.RAW / "evidence_audit_01"
REVISION = base.RAW / "period_metadata_revision_01"
SCRIPT = "trusted_data_synthesis/scripts/audit_cross_market_evidence_20260926.py"
HISTORY = base.ROOT_DATA / (
    "trusted_data_synthesis/artifacts/qa_vnext_eval_readiness/"
    "eval_readiness_20260912/panels/source_metadata.json"
)
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
MEAN_METRICS = (
    "revenue",
    "net_income",
    "operating_income",
    "net_cash_provided_by_used_in_operating_activities",
)
SCALES = {
    "元": 1,
    "千元": 1000,
    "万元": 10000,
    "百万元": 1000000,
    "thousand": 1000,
    "million": 1000000,
    "unit": 1,
}
IDENTITY = re.compile(
    r"公司(?:的)?(?:中文|英文|名称|名称变更)|编制单位|统一社会信用|注册(?:号码|编号)|"
    r"证券代码|股份代[碼码]|股票代[碼码]|stock\s*code|company\s*(?:name|information)|"
    r"corporate\s*information|incorporated|formerly\s*known",
    re.I,
)


def norm(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value))).lower()


def ref(path):
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)


def save(path, value, immutable=True):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "audit_output_root")
    base.write(path, value, immutable=immutable)


def original_refs():
    parent = base.checked(
        base.read(base.RAW / "protocol.json"), "cross_market_source_qualification_protocol"
    )
    revision = base.checked(
        base.read(REVISION / "protocol.json"), "cross_market_period_metadata_revision"
    )
    complete = base.checked(
        base.read(REVISION / "extraction_summary.json"),
        "cross_market_source_qualification_completed",
    )
    base.require(
        revision["parent_protocol_id"] == parent["id"]
        and complete["protocol_id"] == revision["id"]
        and complete["documents"] == parent["document_count"] == 440
        and complete["candidate_count"] == 9513
        and complete["panel_ready"] is False,
        "audit_original_completed_inputs",
    )
    base.require(
        base.read(base.RAW / "budget.json")["parser_attempts"] == 440
        and base.read(REVISION / "budget.json")["parser_attempts"] == 440,
        "audit_does_not_reset_880_parser_attempts",
    )
    return parent, revision, complete


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    parent, revision, complete = original_refs()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in (SCRIPT, base.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "audit_committed_code",
        )
        sources[name] = base.sha(payload)
    documents = []
    for security in revision["metadata_inventory"]["roster"]:
        for doc in security["documents"]:
            key = base.sha(doc["raw_object_id"])[:24]
            documents.append(
                dict(document=doc, extraction=ref(REVISION / "documents" / (key + ".json")))
            )
    plan = base.record(
        "cross_market_evidence_audit_protocol",
        at=base.now(),
        code_commit=head,
        sources=sources,
        parent_protocol_id=parent["id"],
        revision_protocol_id=revision["id"],
        extraction_completion_id=complete["id"],
        extraction_completion=ref(REVISION / "extraction_summary.json"),
        historical_source_metadata=ref(HISTORY),
        documents=documents,
        document_count=len(documents),
        workers=8,
        maximum_pages_per_PDF=1200,
        maximum_text_bytes_per_PDF=32 * 2**20,
        maximum_attempts_per_PDF=1,
        maximum_text_extraction_attempts=len(documents),
        prior_financial_parser_attempts_preserved=880,
        new_financial_parser_calls=0,
        operation="one PyMuPDF page-text pass over exactly the original 440 PDFs; no OCR",
        package_version=importlib.metadata.version("PyMuPDF"),
        python_version=sys.version,
        model_calls=0,
        scoring_calls=0,
        new_training_updates=0,
        network_requests=0,
        GPU_processes=0,
        evaluation_authorized=False,
        quotas=dict.fromkeys(GROUPS, 60),
        issuer_clusters_admitted=False,
        selection_by_model_outcomes=False,
        source_replacement=False,
        policy={
            "candidate_checks": "raw Decimal, page/table/row identity, unit/period evidence; "
            "any success is mechanical review only, not gold",
            "cost_sign": "preserve original signed amount; negative HK cost-of-sales "
            "is added to revenue, never silently abs all costs",
            "period": "annual header evidence recorded separately from inferred start; "
            "no certification from anniversary arithmetic alone",
            "identity": "official-PDF identity snippets plus old-name screen; no fuzzy merge, "
            "no claim that different security codes or no name match prove novelty",
            "capacity": "optimistic structural ceilings from cached candidates; no task "
            "selection, gold values, public manifests or generation permit",
            "scope": "issuer/year dedup is only a security-level capacity bound, not issuer "
            "independence or proof of accounting comparability",
            "recovery": "reuse immutable completed documents; reserved missing result consumes "
            "the one attempt and remains unresolved, never silently retried",
        },
        pre_registration_inspection="source metadata and cached extraction examples inspected; "
        "no model outputs or Q consulted; not claimed value-blind",
    )
    save(RAW / "protocol.json", plan)
    base.emit(
        dict(
            event="cross_market_evidence_audit_registered", id=plan["id"], documents=len(documents)
        )
    )
    return plan


def protocol(root):
    value = base.checked(base.read(RAW / "protocol.json"), "cross_market_evidence_audit_protocol")
    parent, revision, complete = original_refs()
    base.require(
        value["parent_protocol_id"] == parent["id"]
        and value["revision_protocol_id"] == revision["id"]
        and value["extraction_completion_id"] == complete["id"]
        and value["document_count"] == len(value["documents"]) == 440
        and value["maximum_attempts_per_PDF"] == 1
        and value["maximum_text_extraction_attempts"] == 440
        and value["evaluation_authorized"] is False
        and value["package_version"] == importlib.metadata.version("PyMuPDF")
        and value["python_version"] == sys.version,
        "audit_fixed_execution",
    )
    expected = [d for s in revision["metadata_inventory"]["roster"] for d in s["documents"]]
    base.require(
        [r["document"] for r in value["documents"]] == expected, "audit_same_frozen_roster"
    )
    for name, digest in value["sources"].items():
        base.require(base.sha(root / name) == digest, "audit_frozen_code:" + name)
    for reference in (value["historical_source_metadata"], value["extraction_completion"]):
        base.require(
            base.sha(Path(reference["path"])) == reference["sha256"], "audit_frozen_parent"
        )
    return value


def raw_decimal(text):
    text = norm(text).replace(",", "").replace("−", "-").replace("－", "-")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        raise ValueError("ambiguous_raw_number")
    value = Decimal(text)
    if not value.is_finite():
        raise ValueError("nonfinite_raw_number")
    return value


def candidate_review(candidate, parsed, pages):
    """Necessary mechanical checks only. No result from this function is QA gold."""
    c = candidate
    m = c["extraction_metadata"]
    reasons = []
    page = pages.get(c["page_number"], "")
    tables = {t["table_id"]: t for t in parsed["tables"]}
    table = tables.get(c["table_id"], {})
    rows = table.get("raw_table_json", {}).get("rows", [])
    spans = m.get("table_row_span", [c["row_index"]])
    row_text = "".join(
        "".join(str(v or "") for v in rows[i])
        for i in spans
        if isinstance(i, int) and 0 <= i < len(rows)
    )
    checks = {
        "parser_evidence": c["evidence_status"] == "verified" and not c["_validation_errors"],
        "consolidated_scope": c["financial_scope_type"] == "consolidated_entity",
        "table_parent": table.get("raw_object_id") == c["raw_object_id"]
        and table.get("page_number") == c["page_number"],
        "label_in_page": norm(c["source_field_name"]) in norm(page),
        "raw_token_in_page": norm(c["_raw_value_text"]) in norm(page),
        "label_in_cached_table_row": norm(c["source_field_name"]) in norm(row_text),
        "registered_currency_scale": c["currency"] in {"CNY", "HKD", "USD"}
        and c["value_scale"] in SCALES,
        "unit_evidence_page_present": bool(pages.get(c["_unit_source_page"])),
        "period_evidence_page_present": bool(pages.get(c["_period_source_page"])),
    }
    try:
        checks["raw_numeric_roundtrip"] = raw_decimal(c["_raw_value_text"]) == Decimal(c["value"])
    except (ValueError, InvalidOperation):
        checks["raw_numeric_roundtrip"] = False
    reasons.extend(name for name, passed in checks.items() if not passed)
    period_text = norm(pages.get(c["_period_source_page"], ""))
    year = c.get("fiscal_year")
    annual_phrase = bool(
        re.search(r"(?:forthe)?yearended", period_text)
        or re.search(r"20\d{2}年1[—－–\-~至]12月", period_text)
        or (year and f"{year}年度" in period_text)
    )
    signed_cost = (
        c["matched_metric_id"] == "cost_of_revenue"
        and c["_source_id"] == "hkex_disclosures"
        and norm(c["source_field_name"]) == "costofsales"
        and Decimal(c["value"]) < 0
    )
    return dict(
        candidate_id=c["candidate_id"],
        checks=checks,
        failures=reasons,
        mechanical_checks_passed=not reasons,
        annual_phrase_observed=annual_phrase,
        period_start_independently_certified=False,
        period_inference=m["period_inference"],
        signed_HK_cost_presentation=signed_cost,
        issuer_identity_admitted=False,
        qa_eligible=False,
        status="MECHANICAL_REVIEW_ONLY_NOT_FINANCIAL_ADMISSION",
    )


def identity_snippets(pages, statement_pages):
    result = []
    for number, text in pages.items():
        if number > 40 and number not in statement_pages:
            continue
        lines = text.splitlines()
        indices = [i for i, line in enumerate(lines) if IDENTITY.search(line)]
        for i in indices[:12]:
            result.append(
                dict(
                    page=number,
                    text="\n".join(lines[max(0, i - 1) : i + 5])[:1600],
                    kind="IDENTITY_LOCATOR_NOT_ADJUDICATED",
                )
            )
    return result


def reserve(plan, key, doc):
    """A reservation is durable before PDF open; missing completion never refunds it."""
    path = RAW / "attempts" / (key + ".json")
    with base.locked(RAW / "budget.lock", blocking=True):
        if path.exists():
            old = base.read(path)
            base.require(
                old["protocol_id"] == plan["id"] and old["raw_object_id"] == doc["raw_object_id"],
                "audit_attempt_identity",
            )
            return False
        used = len(list((RAW / "attempts").glob("*.json")))
        base.require(used < plan["maximum_text_extraction_attempts"], "audit_text_attempt_cap")
        save(
            path,
            dict(
                protocol_id=plan["id"], raw_object_id=doc["raw_object_id"], attempt=1, at=base.now()
            ),
        )
        return True


def document_job(plan, item):
    doc = item["document"]
    key = base.sha(doc["raw_object_id"])[:24]
    destination = RAW / "documents" / (key + ".json")
    with base.locked(RAW / "locks" / (key + ".lock")):
        if destination.exists():
            old = base.checked(base.read(destination), "cross_market_PDF_evidence_audit")
            base.require(
                old["protocol_id"] == plan["id"]
                and old["document"] == doc
                and old["extraction"] == item["extraction"],
                "audit_cached_identity",
            )
            return dict(key=key, status=old["status"])
        if not reserve(plan, key, doc):
            return dict(key=key, status="UNSETTLED_ATTEMPT_NO_AUTOMATIC_RETRY")
        try:
            source = Path(doc["path"])
            base.require(
                source.is_file()
                and not source.is_symlink()
                and source.resolve().is_relative_to(base.LAKE.resolve())
                and source.stat().st_size == doc["bytes"]
                and base.sha(source) == doc["sha256"],
                "audit_original_PDF_bytes",
            )
            extraction_path = Path(item["extraction"]["path"])
            base.require(
                base.sha(extraction_path) == item["extraction"]["sha256"], "audit_frozen_extraction"
            )
            extraction = base.checked(base.read(extraction_path), "PDF_extraction_result")
            base.require(
                extraction["document"] == doc
                and extraction["protocol_id"] == plan["revision_protocol_id"],
                "audit_extraction_parent",
            )
            import pymupdf

            pages, size = {}, 0
            with pymupdf.open(source) as pdf:
                base.require(
                    not pdf.needs_pass and 0 < len(pdf) <= plan["maximum_pages_per_PDF"],
                    "audit_PDF_page_cap_or_encryption",
                )
                for index in range(len(pdf)):
                    text = pdf[index].get_text("text", sort=False)
                    size += len(text.encode("utf-8"))
                    base.require(size <= plan["maximum_text_bytes_per_PDF"], "audit_text_byte_cap")
                    pages[index + 1] = text
            parsed = extraction["parsed"]
            checks = [candidate_review(c, parsed, pages) for c in parsed["candidates"]]
            text_bundle = base.record(
                "cross_market_original_PDF_page_text",
                protocol_id=plan["id"],
                raw_object_id=doc["raw_object_id"],
                raw_sha256=doc["sha256"],
                pages=[dict(page=n, text=t) for n, t in pages.items()],
                original_url=doc["original_url"],
            )
            text_path = RAW / "page_text" / (key + ".json")
            save(text_path, text_bundle)
            history = base.read(Path(plan["historical_source_metadata"]["path"]))
            # An exact normalized substring hit is only a review alert: reports can
            # name customers/subsidiaries. Absence cannot certify historical novelty.
            identity_text = norm("\n".join(t for n, t in pages.items() if n <= 40))
            hits = [
                dict(source_cluster=r["source_cluster"], name=r["entity"]["canonical_name"])
                for r in history["rows"]
                if len(norm(r["entity"]["canonical_name"])) >= 8
                and norm(r["entity"]["canonical_name"]) in identity_text
            ]
            result = dict(
                status="TEXT_AUDITED_NOT_ADMITTED",
                text_bundle=ref(text_path),
                pages=len(pages),
                text_bytes=size,
                empty_text_pages=[n for n, t in pages.items() if not t.strip()],
                candidate_reviews=checks,
                historical_name_alerts=hits,
                identity_snippets=identity_snippets(
                    pages, {c["page_number"] for c in parsed["candidates"]}
                ),
                issuer_identity_admitted=False,
                source_novelty_admitted=False,
            )
        except Exception as error:
            result = dict(status="EVIDENCE_AUDIT_FAILED", error=repr(error))
        save(
            destination,
            base.record(
                "cross_market_PDF_evidence_audit",
                protocol_id=plan["id"],
                document=doc,
                extraction=item["extraction"],
                at=base.now(),
                attempt=1,
                qa_eligible=False,
                **result,
            ),
        )
        return dict(key=key, status=result["status"])


def structural_capacity(extractions):
    """Optimistic ceilings: ignore unresolved issuer/period/scope/version gates.

    All cached observations, including mechanically failed ones, are included in
    the ceiling. A shortage here cannot be repaired by relaxing later admission;
    a surplus never proves admission. Tasks are deduplicated by security/target.
    """
    dual, dual_diagnostics, series = set(), [], defaultdict(set)
    complete_by_security = defaultdict(set)
    for extraction in extractions:
        doc = extraction["document"]
        security = doc["security_id"]
        by_period = defaultdict(lambda: defaultdict(list))
        for c in extraction.get("parsed", {}).get("candidates", []):
            metric = c["matched_metric_id"]
            if c.get("period_start") and metric in MEAN_METRICS:
                series[security, metric].add((c["period_start"], c["period_end"]))
            if metric in {"gross_profit", "revenue", "cost_of_revenue"}:
                by_period[c["period_start"], c["period_end"]][metric].append(c)
        complete = {
            p
            for p, metrics in by_period.items()
            if all(metrics.get(m) for m in ("gross_profit", "revenue", "cost_of_revenue"))
        }
        complete_by_security[security].update(complete)
        if complete:
            dual_diagnostics.append(
                dict(
                    security_id=security,
                    raw_object_id=doc["raw_object_id"],
                    periods=sorted(complete),
                    status="COMPONENT_PRESENCE_ONLY_NOT_CERTIFICATE",
                )
            )
    for security, complete in sorted(complete_by_security.items()):
        for previous in sorted(complete):
            for current in sorted(complete):
                if consecutive(previous, current):
                    # Permit both quantities and different endpoint reports in this ceiling.
                    for quantity in ("difference", "relative_change"):
                        dual.add((security, previous, current, quantity))
    composition, other = set(), set()
    for (security, metric), periods in sorted(series.items()):
        periods = sorted(periods)
        windows = [
            (first, middle, last)
            for first in periods
            for middle in periods
            if consecutive(first, middle)
            for last in periods
            if consecutive(middle, last)
        ]
        for window in windows:
            composition.add((security, metric, window))
            if metric == "revenue":
                for secondary in ("net_income", "operating_income"):
                    if set(window) <= series.get((security, secondary), set()):
                        other.add((security, secondary, window))
    return dict(
        optimistic_security_level_counts={
            GROUPS[0]: len(dual),
            GROUPS[1]: len(composition),
            GROUPS[2]: len(other),
        },
        dual_component_presence=dual_diagnostics,
        ignored_gates=[
            "issuer_and_exposure",
            "financial_semantics",
            "actual_periods",
            "row_column_alignment",
            "common_vintage",
            "source_aggregate_screen",
            "unique_argmax",
            "positive_growth_base",
            "public_runtime",
        ],
        cash_dual_candidates=0,
        cash_reason="existing parser has no typed FX/change bridge candidates; no invention",
        task_manifest_created=False,
        admitted_tasks=0,
    )


def consecutive(first, second):
    try:
        return (
            first[0] is not None
            and second[0] is not None
            and date.fromisoformat(first[1]) + timedelta(days=1) == date.fromisoformat(second[0])
            and all(
                350 <= (date.fromisoformat(p[1]) - date.fromisoformat(p[0])).days <= 380
                for p in (first, second)
            )
        )
    except (ValueError, TypeError):
        return False


def summarize(plan):
    docs, missing = [], []
    for item in plan["documents"]:
        key = base.sha(item["document"]["raw_object_id"])[:24]
        path = RAW / "documents" / (key + ".json")
        if not path.exists():
            missing.append(key)
            continue
        row = base.checked(base.read(path), "cross_market_PDF_evidence_audit")
        base.require(
            row["protocol_id"] == plan["id"]
            and row["document"] == item["document"]
            and row["extraction"] == item["extraction"],
            "audit_summary_identity",
        )
        docs.append(row)
    extractions = []
    for item in plan["documents"]:
        path = Path(item["extraction"]["path"])
        base.require(base.sha(path) == item["extraction"]["sha256"], "audit_capacity_frozen_input")
        extractions.append(base.read(path))
    capacity = structural_capacity(extractions)
    save(
        RAW / "structural_capacity.json",
        base.record("cross_market_structural_capacity", protocol_id=plan["id"], **capacity),
    )
    checks = [c for row in docs for c in row.get("candidate_reviews", [])]
    failures = Counter(reason for row in checks for reason in row["failures"])
    summary = base.record(
        "cross_market_evidence_audit_completed",
        protocol_id=plan["id"],
        at=base.now(),
        status="EVIDENCE_AUDIT_COMPLETE_NOT_EVALUATION_READY"
        if not missing
        else "EVIDENCE_AUDIT_INCOMPLETE_NO_AUTOMATIC_RETRY",
        documents=len(docs),
        status_counts=dict(Counter(row["status"] for row in docs)),
        missing_results=missing,
        pages=sum(row.get("pages", 0) for row in docs),
        text_bytes=sum(row.get("text_bytes", 0) for row in docs),
        empty_text_pages=sum(len(row.get("empty_text_pages", [])) for row in docs),
        candidates_reviewed=len(checks),
        mechanical_checks_passed=sum(c["mechanical_checks_passed"] for c in checks),
        mechanical_failure_counts=dict(failures),
        inferred_periods=dict(Counter(c["period_inference"] for c in checks)),
        signed_HK_cost_candidates=sum(c["signed_HK_cost_presentation"] for c in checks),
        historical_name_alert_documents=sum(
            bool(row.get("historical_name_alerts")) for row in docs
        ),
        structural_capacity=capacity["optimistic_security_level_counts"],
        structural_capacity_is_not_admission=True,
        admitted_tasks=0,
        independent_issuers=None,
        panel_ready=False,
        evaluation_started=False,
        text_extraction_attempts=len(list((RAW / "attempts").glob("*.json"))),
        prior_financial_parser_attempts_preserved=880,
        new_financial_parser_calls=0,
        model_calls=0,
        network_requests=0,
        GPU_processes=0,
        remaining_gates=[
            "adjudicated_issuer_identity_and_exposure",
            "financial_semantics_and_periods",
            "PDF_native_relations_and_three_group_180_panel",
            "public_source_runtime",
            "private_scoring_barrier",
            "issuer_cluster_statistics",
            "evaluation_plan",
        ],
    )
    save(RAW / "summary.json", summary)
    base.emit(dict(event="cross_market_evidence_audit_completed", **summary))
    return summary


def run(root):
    plan = protocol(root)
    with base.locked(RAW / "run.lock"):
        if (RAW / "summary.json").exists():
            return base.checked(
                base.read(RAW / "summary.json"), "cross_market_evidence_audit_completed"
            )
        with ProcessPoolExecutor(
            max_workers=plan["workers"], mp_context=multiprocessing.get_context("spawn")
        ) as executor:
            futures = [executor.submit(document_job, plan, item) for item in plan["documents"]]
            for number, future in enumerate(as_completed(futures), 1):
                result = future.result()
                if number % 20 == 0 or result["status"] != "TEXT_AUDITED_NOT_ADMITTED":
                    base.emit(
                        dict(
                            event="cross_market_evidence_audit_progress",
                            completed=number,
                            total=len(futures),
                            **result,
                        )
                    )
        return summarize(plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("register", "run", "start"), required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.mode == "register":
        register(root)
    elif args.mode == "run":
        run(root)
    else:
        protocol(root)
        with base.locked(RAW / "start.lock"):
            launch_path = RAW / "launch.json"
            if launch_path.exists():
                launch = base.read(launch_path)
                proc = Path("/proc") / str(launch["pid"]) / "stat"
                if (
                    proc.exists()
                    and proc.read_text().rsplit(")", 1)[1].split()[19] == launch["ticks"]
                ):
                    base.emit(dict(event="audit_already_running", pid=launch["pid"]))
                    return
            env = dict(
                os.environ,
                CUDA_VISIBLE_DEVICES="",
                OMP_NUM_THREADS="1",
                OPENBLAS_NUM_THREADS="1",
                MKL_NUM_THREADS="1",
            )
            with (RAW / "run.log").open("ab") as stream:
                child = subprocess.Popen(
                    [sys.executable, str(root / SCRIPT), "--root", str(root), "--mode", "run"],
                    cwd=root,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            ticks = (
                (Path("/proc") / str(child.pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]
            )
            save(launch_path, dict(pid=child.pid, ticks=ticks, at=base.now()), immutable=False)
            base.emit(dict(event="cross_market_evidence_audit_started", pid=child.pid))


if __name__ == "__main__":
    main()
