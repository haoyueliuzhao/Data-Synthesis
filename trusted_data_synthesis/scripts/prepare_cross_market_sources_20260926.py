"""Offline cross-market source qualification, not an evaluation execution permit.

Freeze metadata-only security/document choices before opening PDF contents. Parse
only the fixed local bytes with the existing evidence parser. Preserve all errors
and do not turn parser candidates into financial ground truth or SEC companyfacts.
"""

import argparse
import contextlib
import dataclasses
import fcntl
import hashlib
import importlib.metadata
import json
import multiprocessing
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT_DATA = Path("/data1/zhuxinrui/projects/Data-Synthesis")
ARTIFACTS = ROOT_DATA / "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value"
LAKE = ROOT_DATA / "raw_financial_data_lake/data/fin_raw"
PARENT = ARTIFACTS / "direction_calibration_cache_20260926"
RAW = ARTIFACTS / "cross_market_calibration_cache_20260926"
SCRIPT = "trusted_data_synthesis/scripts/prepare_cross_market_sources_20260926.py"
SOURCES = {
    "cninfo_announcements": ("cninfo/announcements", "static.cninfo.com.cn", 6),
    "hkex_disclosures": ("hkex/disclosures", "www1.hkexnews.hk", 5),
}
CODE = (
    SCRIPT,
    "raw_financial_data_lake/finraw/cn_financial_statements.py",
    "raw_financial_data_lake/finraw/metric_ontology.py",
)
SALT = "cross_market_source_qualification_20260926.v1:"
YEARS = tuple(range(2019, 2026))
SECURITIES_PER_SOURCE = 32
PDF_PACKAGES = (
    "PyMuPDF",
    "pdfplumber",
    "pdfminer.six",
    "Pillow",
    "pypdfium2",
    "charset-normalizer",
    "cryptography",
    "cffi",
    "pycparser",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def require(value, reason):
    if not value:
        raise ValueError("cross_market." + reason)


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(value):
    if isinstance(value, Path):
        with value.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def record(kind, **fields):
    body = dict(schema_version="cross_market_calibration.v1." + kind, **fields)
    return dict(**body, id=kind + ":" + sha(encode(body)))


def checked(value, kind):
    body = {k: v for k, v in value.items() if k != "id"}
    require(
        body.get("schema_version") == "cross_market_calibration.v1." + kind
        and value["id"] == kind + ":" + sha(encode(body)),
        "record_identity",
    )
    return value


def emit(value):
    print(json.dumps({"at": now(), **value}, ensure_ascii=False), flush=True)


def write(path, value, immutable=True):
    path = Path(path)
    require(
        path.resolve().is_relative_to(RAW.resolve()) and ".." not in path.parts, "confined_output"
    )
    payload = encode(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and immutable:
        require(path.read_bytes() == payload, "immutable_conflict")
        return
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".partial.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                require(path.read_bytes() == payload, "concurrent_immutable_conflict")
        else:
            os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def locked(path, blocking=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield


def local_path(uri):
    marker = "raw_financial_data_lake/data/fin_raw/"
    require(marker in uri, "registered_lake_path")
    tail = Path(uri.split(marker, 1)[1])
    path = LAKE / tail
    require(
        not tail.is_absolute()
        and ".." not in tail.parts
        and path.is_file()
        and not path.is_symlink()
        and path.resolve().is_relative_to(LAKE.resolve()),
        "regular_confined_PDF",
    )
    return path.resolve()


def metadata_inventory():
    """Only manifest metadata/stat; never read PDF, numeric facts, tasks or model Q."""
    inputs, rejected, versions = [], [], defaultdict(list)
    for source, (directory, host, width) in SOURCES.items():
        for path in sorted((LAKE / directory).glob("snapshot_date=*/manifest.json")):
            manifest = read(path)
            inputs.append(dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size))
            for obj in manifest["objects"]:
                params = obj.get("request_params") or {}
                try:
                    require(
                        obj["source_id"] == source
                        and obj["object_type"] == "pdf"
                        and obj["validation_status"] == "passed"
                        and obj["response_status"] == 200,
                        "original_successful_PDF_receipt",
                    )
                    require(params.get("report_type") == "annual", "annual_only")
                    code = str(params.get("stock_code", ""))
                    require(code.isdigit() and len(code) <= width, "security_code")
                    code = code.zfill(width)
                    year = int(params["year"])
                    require(year in YEARS, "registered_year_window")
                    name = str(params["company_name"]).strip()
                    require(bool(name), "issuer_label_present")
                    url = str(params.get("url") or obj["original_url"])
                    require(
                        urlsplit(url).scheme == "https" and urlsplit(url).hostname == host,
                        "original_official_host",
                    )
                    local = local_path(obj["storage_uri"])
                    digest, size = obj["content_sha256"], obj["content_size_bytes"]
                    require(
                        bool(re.fullmatch("[0-9a-f]{64}", digest))
                        and type(size) is int
                        and size > 0
                        and local.stat().st_size == size,
                        "receipt_size_and_hash_descriptor",
                    )
                    metadata = {
                        k: params.get(k)
                        for k in (
                            "stock_code",
                            "company_name",
                            "year",
                            "report_type",
                            "publish_date",
                            "announcement_id",
                            "language",
                            "market",
                            "exchange",
                        )
                    }
                    row = dict(
                        source_id=source,
                        security_code=code,
                        security_id=source + ":" + code,
                        year=year,
                        company_name=name,
                        path=str(local),
                        sha256=digest,
                        bytes=size,
                        original_url=url,
                        raw_object_id=obj["raw_object_id"],
                        metadata={
                            **metadata,
                            "source_id": source,
                            "source_publish_date": obj.get("source_publish_date"),
                        },
                        publish_date=str(
                            obj.get("source_publish_date") or params.get("publish_date") or ""
                        ),
                        announcement_id=str(params.get("announcement_id") or ""),
                        receipt_manifest=str(path),
                        receipt_id=obj["raw_object_id"],
                    )
                    versions[(source, code, year)].append(row)
                except (ValueError, KeyError, TypeError, OSError) as error:
                    rejected.append(
                        dict(
                            manifest=str(path),
                            raw_object_id=obj.get("raw_object_id"),
                            reason=str(error),
                        )
                    )
    selected, older = [], []
    for key, rows in sorted(versions.items()):
        rank = max((r["publish_date"], r["announcement_id"]) for r in rows)
        latest = [r for r in rows if (r["publish_date"], r["announcement_id"]) == rank]
        if len({r["sha256"] for r in latest}) != 1:
            rejected.append(dict(identity=key, reason="same_vintage_conflicting_receipts"))
            continue
        choice = sorted(latest, key=lambda r: (r["receipt_manifest"], r["raw_object_id"]))[-1]
        selected.append(choice)
        older.extend(
            dict(identity=key, sha256=r["sha256"], reason="older_or_duplicate_metadata_receipt")
            for r in rows
            if r is not choice
        )
    by_hash = defaultdict(set)
    for row in selected:
        by_hash[row["sha256"]].add(row["security_id"])
    clean = []
    for row in selected:
        if len(by_hash[row["sha256"]]) > 1:
            rejected.append(
                dict(
                    security_id=row["security_id"],
                    year=row["year"],
                    reason="same_PDF_multiple_securities",
                )
            )
        else:
            clean.append(row)
    grouped = defaultdict(list)
    for row in clean:
        grouped[row["security_id"]].append(row)
    eligible = {key: rows for key, rows in grouped.items() if len({r["year"] for r in rows}) >= 5}
    roster = []
    for source in SOURCES:
        keys = sorted(
            (key for key in eligible if key.startswith(source + ":")),
            key=lambda key: (sha(SALT + key), key),
        )
        require(
            len(keys) >= SECURITIES_PER_SOURCE, "at_least32_metadata_eligible_securities:" + source
        )
        for key in keys[:SECURITIES_PER_SOURCE]:
            docs = sorted(eligible[key], key=lambda row: (row["year"], row["sha256"]))
            roster.append(
                dict(
                    security_id=key,
                    source_id=source,
                    company_names=sorted({r["company_name"] for r in docs}),
                    issuer_cluster_status="UNRESOLVED_DO_NOT_COUNT_AS_INDEPENDENT_ISSUER",
                    documents=docs,
                )
            )
    return dict(
        inputs=inputs,
        eligible_counts={s: sum(k.startswith(s + ":") for k in eligible) for s in SOURCES},
        roster=roster,
        rejected=rejected,
        older_or_duplicate=older,
        no_PDF_or_financial_value_read=True,
    )


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    inventory = metadata_inventory()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    code = {}
    for name in CODE:
        data = (root / name).read_bytes()
        require(
            data == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "committed_source:" + name,
        )
        code[name] = sha(data)
    completed = read(PARENT / "training_stage_20260926/complete.json")
    body = {key: value for key, value in completed.items() if key != "id"}
    require(
        completed["schema_version"]
        == "fixed_kernel_value.v1.B_direction_calibration_training_completed"
        and completed["id"] == "B_direction_calibration_training_completed:" + sha(encode(body))
        and sorted(row["seed"] for row in completed["seeds"]) == [11, 29, 47],
        "bound_training_completion_identity",
    )
    require(
        completed["complete"]
        and completed["committed_optimizer_updates"] == 120
        and completed["reused_step240_models"] == 6,
        "nine_fixed_model_endpoints",
    )
    docs = [row for sec in inventory["roster"] for row in sec["documents"]]
    require(len({r["raw_object_id"] for r in docs}) == len(docs) <= 448, "finite_unique_documents")
    plan = record(
        "cross_market_source_qualification_protocol",
        authorization="2026-09-26 用户选择第二项：本地CNInfo/HKEX材料，独立跨市场校准",
        code_commit=head,
        sources=code,
        metadata_inventory=inventory,
        training_completion_id=completed["id"],
        training_completion_sha256=sha(PARENT / "training_stage_20260926/complete.json"),
        nine_model_endpoints_unchanged=True,
        new_training_updates=0,
        source_policy=dict(
            salt=SALT,
            securities_per_source=32,
            years=list(YEARS),
            minimum_annual_documents_per_security=5,
            selection="metadata-only hash; latest publication/announcement per security-year",
            no_replacement_or_expansion=True,
            final_independent_issuer_count="NOT_ESTABLISHED",
        ),
        document_count=len(docs),
        total_registered_PDF_bytes=sum(r["bytes"] for r in docs),
        workers=8,
        parser_attempts_per_document=2,
        total_parser_attempt_cap=2 * len(docs),
        maximum_statement_pages=20,
        maximum_unit_carry_pages=12,
        maximum_statement_carry_pages=4,
        maximum_result_bytes=32 * 2**20,
        package_versions={name: importlib.metadata.version(name) for name in PDF_PACKAGES},
        python_version=sys.version,
        no_API_calls=True,
        no_network=True,
        no_GPU=True,
        new_Probe_materials=0,
        source_novelty=(
            "NOT_YET_ADMITTED; cross-listing and old exposure linkage require separate evidence"
        ),
        extraction_is_not_fact_promotion=True,
        evaluation_authorized=False,
        prospective_evaluation=dict(
            tasks_per_group=60,
            groups=["dual_sufficient", "composition_required", "other_financial"],
            seeds=[11, 29, 47],
            arms=["static", "positive", "negative"],
            stochastic_repeats=2,
            greedy_repeats=1,
            total_sessions=4860,
            current_generation_budget=0,
            current_scoring_budget=0,
            preserve_English_task_templates=True,
            no_cross_currency_arithmetic=True,
            require_new_PDF_native_relation_and_runtime_contract=True,
            never_relabel_CN_HK_as_US_GAAP_or_CIK=True,
        ),
        readiness_gates=[
            "issuer_identity_and_exposure",
            "original_PDF_evidence",
            "financial_semantics_and_periods",
            "fixed_three_group_180_tasks",
            "public_source_runtime",
            "private_scoring_barrier",
            "issuer_cluster_statistics",
            "separate_evaluation_execution_registration",
        ],
        at=now(),
    )
    write(RAW / "protocol.json", plan)
    emit(
        dict(
            event="cross_market_sources_registered",
            id=plan["id"],
            securities=64,
            documents=len(docs),
        )
    )
    return plan


def protocol(root):
    plan = checked(read(RAW / "protocol.json"), "cross_market_source_qualification_protocol")
    require(
        plan["evaluation_authorized"] is False
        and plan["new_training_updates"] == 0
        and plan["no_network"]
        and plan["no_GPU"]
        and plan["workers"] == 8
        and plan["parser_attempts_per_document"] == 2
        and plan["total_parser_attempt_cap"] == 2 * plan["document_count"]
        and plan["source_policy"]["securities_per_source"] == 32
        and plan["source_policy"]["years"] == list(YEARS)
        and plan["prospective_evaluation"]["current_generation_budget"] == 0
        and plan["prospective_evaluation"]["current_scoring_budget"] == 0
        and plan["python_version"] == sys.version,
        "source_qualification_only",
    )
    for name, digest in plan["sources"].items():
        require(sha(root / name) == digest, "frozen_code:" + name)
    for ref in plan["metadata_inventory"]["inputs"]:
        require(sha(Path(ref["path"])) == ref["sha256"], "frozen_metadata")
    for name, version in plan["package_versions"].items():
        require(importlib.metadata.version(name) == version, "frozen_parser_dependency:" + name)
    require(
        sha(PARENT / "training_stage_20260926/complete.json") == plan["training_completion_sha256"],
        "frozen_training_completion",
    )
    return plan


def document_job(plan, doc):
    key = sha(doc["raw_object_id"])[:24]
    destination = RAW / "documents" / (key + ".json")
    try:
        with locked(RAW / "document_locks" / (key + ".lock")):
            path = Path(doc["path"])
            require(
                path.stat().st_size == doc["bytes"] and sha(path) == doc["sha256"],
                "actual_PDF_bytes",
            )
            if destination.exists():
                value = checked(read(destination), "PDF_extraction_result")
                require(
                    value["protocol_id"] == plan["id"] and value["document"] == doc,
                    "cached_document_identity",
                )
                return dict(key=key, status=value["status"])
            attempts = RAW / "attempts" / key
            used = max((int(path.stem) for path in attempts.glob("*.json")), default=0)
            require(used < plan["parser_attempts_per_document"], "document_attempt_cap")
            with locked(RAW / "budget.lock", blocking=True):
                state = (
                    read(RAW / "budget.json")
                    if (RAW / "budget.json").exists()
                    else {"parser_attempts": 0}
                )
                require(
                    state["parser_attempts"] < plan["total_parser_attempt_cap"],
                    "parser_attempt_cap",
                )
                state["parser_attempts"] += 1
                write(RAW / "budget.json", state, immutable=False)
                write(
                    attempts / f"{used + 1:02d}.json",
                    dict(protocol_id=plan["id"], raw_object_id=doc["raw_object_id"], at=now()),
                )
            from finraw import cn_financial_statements as parser
            from finraw import metric_ontology as ontology

            aliases = (
                ontology.CNINFO_STRICT_ALIASES
                if doc["source_id"] == "cninfo_announcements"
                else ontology.HKEX_STRICT_ALIASES
            )
            alias_map = {
                parser._normalize_label(label): metric
                for metric, labels in aliases.items()
                for label in labels
            }
            statement_types = {
                row["metric_id"]: row["statement_type"] for row in ontology.SEC_METRICS
            }
            try:
                parsed = parser.parse_cninfo_pdf(
                    path,
                    raw_object_id=doc["raw_object_id"],
                    entity_id="unresolved_security:" + doc["security_id"],
                    metadata=doc["metadata"],
                    metric_aliases=alias_map,
                    metric_statement_types=statement_types,
                    source_id=doc["source_id"],
                    maximum_statement_pages=plan["maximum_statement_pages"],
                    maximum_unit_carry_pages=plan["maximum_unit_carry_pages"],
                    maximum_statement_carry_pages=plan["maximum_statement_carry_pages"],
                )
                result = dict(
                    status="PARSED_CANDIDATES_NOT_ADMITTED", parsed=dataclasses.asdict(parsed)
                )
            except MemoryError as error:
                write(
                    RAW / "resource_errors" / key / f"{used + 1:02d}.json",
                    dict(protocol_id=plan["id"], error=repr(error), at=now()),
                )
                return dict(key=key, status="RESOURCE_RETRY", error=repr(error))
            except Exception as error:
                result = dict(status="PARSE_FAILED", error=repr(error))
            value = record(
                "PDF_extraction_result",
                protocol_id=plan["id"],
                document=doc,
                attempt=used + 1,
                at=now(),
                candidates_are_not_gold=True,
                **result,
            )
            require(len(encode(value)) <= plan["maximum_result_bytes"], "bounded_result_size")
            write(destination, value)
            return dict(key=key, status=value["status"])
    except BlockingIOError:
        return dict(key=key, status="ALREADY_RUNNING")


def summarize(plan):
    results = [
        checked(read(path), "PDF_extraction_result")
        for path in sorted((RAW / "documents").glob("*.json"))
    ]
    require(
        len(results) == plan["document_count"]
        and all(r["protocol_id"] == plan["id"] for r in results),
        "complete_fixed_document_inventory",
    )
    expected = {
        doc["raw_object_id"]: doc
        for sec in plan["metadata_inventory"]["roster"]
        for doc in sec["documents"]
    }
    require(
        {r["document"]["raw_object_id"]: r["document"] for r in results} == expected,
        "exact_completed_document_identities",
    )
    status = Counter(r["status"] for r in results)
    candidates = [c for r in results if "parsed" in r for c in r["parsed"]["candidates"]]
    summary = record(
        "cross_market_source_qualification_completed",
        protocol_id=plan["id"],
        documents=plan["document_count"],
        status_counts=dict(status),
        candidate_count=len(candidates),
        parser_evidence_verified_candidates=sum(
            c["evidence_status"] == "verified" for c in candidates
        ),
        metric_candidate_counts=dict(Counter(c["metric_hint"] for c in candidates)),
        currencies=dict(Counter(c["currency"] for c in candidates)),
        securities=64,
        independent_issuer_count=None,
        issuer_identity_admitted=False,
        panel_ready=False,
        evaluation_started=False,
        model_calls=0,
        new_training_updates=0,
        status="EXTRACTION_COMPLETE_NOT_EVALUATION_READY",
        remaining_gates=plan["readiness_gates"],
        budget=read(RAW / "budget.json"),
        at=now(),
    )
    write(RAW / "extraction_summary.json", summary)
    emit(
        dict(
            event="cross_market_extraction_completed",
            documents=len(results),
            candidates=len(candidates),
            panel_ready=False,
        )
    )
    return summary


def run(root):
    plan = protocol(root)
    with locked(RAW / "run.lock"):
        if (RAW / "extraction_summary.json").exists():
            return checked(
                read(RAW / "extraction_summary.json"), "cross_market_source_qualification_completed"
            )
        docs = [doc for row in plan["metadata_inventory"]["roster"] for doc in row["documents"]]
        for round_number in range(2):
            pending = [
                doc
                for doc in docs
                if not (RAW / "documents" / (sha(doc["raw_object_id"])[:24] + ".json")).exists()
            ]
            if not pending:
                break
            with ProcessPoolExecutor(
                max_workers=plan["workers"], mp_context=multiprocessing.get_context("spawn")
            ) as pool:
                futures = [pool.submit(document_job, plan, doc) for doc in pending]
                for future in as_completed(futures):
                    row = future.result()
                    completed = len(list((RAW / "documents").glob("*.json")))
                    write(
                        RAW / "heartbeat.json",
                        dict(
                            protocol_id=plan["id"],
                            at=now(),
                            completed_documents=completed,
                            target_documents=len(docs),
                            last_result=row,
                            evaluation_started=False,
                        ),
                        immutable=False,
                    )
                    emit(
                        dict(
                            event="cross_market_document_saved",
                            completed=completed,
                            total=len(docs),
                            **row,
                        )
                    )
            if round_number == 0:
                time.sleep(2)
        return summarize(plan)


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
        with locked(RAW / "start.lock"):
            launch = read(RAW / "launch.json") if (RAW / "launch.json").exists() else None
            if launch:
                proc = Path("/proc") / str(launch["pid"]) / "stat"
                if (
                    proc.exists()
                    and proc.read_text().rsplit(")", 1)[1].split()[19] == launch["start_ticks"]
                ):
                    emit(dict(event="cross_market_already_started", pid=launch["pid"]))
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
            write(
                RAW / "launch.json",
                dict(pid=child.pid, start_ticks=ticks, at=now()),
                immutable=False,
            )
            emit(dict(event="cross_market_source_qualification_started", pid=child.pid))
    else:
        try:
            run(root)
        except Exception as error:
            write(RAW / "needs_attention.json", dict(error=repr(error), at=now()), immutable=False)
            raise


if __name__ == "__main__":
    main()
