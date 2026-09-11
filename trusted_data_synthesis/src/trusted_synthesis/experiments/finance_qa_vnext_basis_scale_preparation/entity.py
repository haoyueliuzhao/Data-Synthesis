"""Local SEC-submissions ticker evidence, not historical issuer certification.

Only the two named local snapshot dates are inspected. A current association
means the ticker occurs in the chosen stored snapshot, not that it is current
today or that an old FinQA report was filed by that legal entity. No name-based
or historical ticker inference silently completes an unmatched association.
"""

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SUBMISSIONS = "raw_financial_data_lake/data/fin_raw/sec/submissions"
SNAPSHOT_DATES = ("2026-07-22", "2026-07-08")


def _record(kind, **fields):
    body = {"schema_version": "basis_scale_preparation.v1." + kind, **fields}
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {**body, "id": kind + ":" + hashlib.sha256(raw).hexdigest()}


def _cik(value):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}", value) or int(value) == 0:
        raise ValueError("entity.invalid_submission_cik")
    return value.zfill(10)


def _tickers(tickers):
    if isinstance(tickers, (str, bytes)):
        raise ValueError("entity.ticker_collection_required")
    result = []
    for ticker in tickers:
        if not isinstance(ticker, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.\-]*", ticker):
            raise ValueError("entity.ticker_shape")
        result.append(ticker.upper())
    return sorted(set(result))


def _select_snapshots(root):
    directory = root / SUBMISSIONS
    if not directory.is_dir():
        return [], False
    by_cik = defaultdict(dict)
    for date in SNAPSHOT_DATES:
        for path in directory.glob(f"cik=*/snapshot_date={date}.json"):
            match = re.fullmatch(r"cik=([0-9]{10})", path.parent.name)
            if match:
                by_cik[match[1]][date] = path
    selected = []
    for directory_cik, paths in sorted(by_cik.items()):
        date = next(date for date in SNAPSHOT_DATES if date in paths)
        selected.append((directory_cik, date, paths[date], sorted(set(paths) - {date})))
    return selected, True


def _snapshot(root, directory_cik, date, path, unread_dates):
    if path.is_symlink() or not path.is_file():
        raise ValueError("entity.regular_local_snapshot_required")
    raw = path.read_bytes()
    reference = {
        "path": str(path.relative_to(root)),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    base = {
        "directory_cik": directory_cik,
        "snapshot_date": date,
        "fallback_because_preferred_snapshot_absent": date != SNAPSHOT_DATES[0],
        "available_older_dates_not_read": unread_dates,
        "source_reference": reference,
    }
    try:
        data = json.loads(raw)
        cik = _cik(data["cik"])
        name, tickers = data["name"], data["tickers"]
        if cik != directory_cik:
            raise ValueError("entity.directory_and_payload_cik_mismatch")
        if not isinstance(name, str) or not name.strip() or not isinstance(tickers, list):
            raise ValueError("entity.name_or_ticker_list_shape")
        if any(not isinstance(ticker, str) or not ticker for ticker in tickers):
            raise ValueError("entity.nontext_submission_ticker")
        former = data.get("formerNames", [])
        if not isinstance(former, list):
            raise ValueError("entity.former_names_shape")
        return {
            **base,
            "status": "USABLE_STORED_SUBMISSION",
            "cik": cik,
            "name": name,
            "cik_json_pointer": "/cik",
            "name_json_pointer": "/name",
            "cik_original_value": data["cik"],
            "tickers": [
                {"ticker": ticker, "json_pointer": f"/tickers/{index}"}
                for index, ticker in enumerate(tickers)
            ],
            "former_names": [
                {"value": item, "json_pointer": f"/formerNames/{index}"}
                for index, item in enumerate(former)
            ],
            "former_names_not_a_historical_report_binding": True,
        }
    except (ValueError, KeyError, TypeError) as error:
        return {
            **base,
            "status": "UNUSABLE_STORED_SUBMISSION",
            "reason": str(error),
            "older_snapshot_not_used_to_hide_preferred_snapshot_error": True,
        }


def runtime(root, tickers):
    """Return a deterministic, file-bound evidence map for requested ticker codes.

    For each CIK, prefer July 22 and use July 8 only if July 22 is absent. A
    ticker absent from the preferred snapshot is not restored from an older
    snapshot, and repeated issuer names never merge different CIKs. Every
    historical-report identity remains unresolved because this function does
    not inspect original annual-report cover pages or accession/CIK bindings.
    """
    root = Path(root)
    requested = _tickers(tickers)
    paths, directory_present = _select_snapshots(root)
    snapshots = [_snapshot(root, *selection) for selection in paths]
    usable = [item for item in snapshots if item["status"] == "USABLE_STORED_SUBMISSION"]
    names, by_ticker = defaultdict(set), defaultdict(list)
    for snapshot in usable:
        names[" ".join(snapshot["name"].casefold().split())].add(snapshot["cik"])
        for ticker in snapshot["tickers"]:
            by_ticker[ticker["ticker"].upper()].append((snapshot, ticker))
    name_ambiguities = {name: sorted(ciks) for name, ciks in sorted(names.items()) if len(ciks) > 1}
    rows = []
    for ticker in requested:
        matches = []
        for snapshot, occurrence in by_ticker.get(ticker, []):
            normalized_name = " ".join(snapshot["name"].casefold().split())
            matches.append(
                {
                    "cik": snapshot["cik"],
                    "name": snapshot["name"],
                    "snapshot_date": snapshot["snapshot_date"],
                    "source_reference": snapshot["source_reference"],
                    "ticker_original_value": occurrence["ticker"],
                    "ticker_json_pointer": occurrence["json_pointer"],
                    "cik_original_value": snapshot["cik_original_value"],
                    "cik_json_pointer": snapshot["cik_json_pointer"],
                    "name_json_pointer": snapshot["name_json_pointer"],
                    "same_normalized_name_other_ciks": sorted(
                        names[normalized_name] - {snapshot["cik"]}
                    ),
                    "same_name_not_used_as_identity_evidence": True,
                }
            )
        distinct_ciks = sorted({match["cik"] for match in matches})
        unique = len(distinct_ciks) == 1
        status = (
            "UNIQUE_STORED_SUBMISSION_ASSOCIATION"
            if unique
            else "AMBIGUOUS_MULTIPLE_CIKS"
            if distinct_ciks
            else "UNMATCHED_IN_USABLE_LOCAL_SNAPSHOTS"
        )
        rows.append(
            {
                "ticker": ticker,
                "status": status,
                "matched_ciks": distinct_ciks,
                "matches": matches,
                "verified_current_submission_association": unique,
                "current_means_chosen_stored_snapshot_not_today": True,
                "historical_report_company_identity_status": "UNRESOLVED",
                "historical_report_company_identity_certified": False,
                "reason": (
                    "The stored snapshot uniquely associates this exact ticker code with a CIK. "
                    "Historical FinQA issuer identity, renames, reorganizations and ticker reuse "
                    "need original-report evidence."
                    if unique
                    else "Multiple stored CIKs have this ticker; no match or name merge is chosen."
                    if distinct_ciks
                    else "No association was found in these usable local snapshots. This does not "
                    "establish that no issuer exists or that a historical ticker was invalid."
                ),
            }
        )
    lookup = {row["ticker"]: row for row in rows}
    shared_ua_ciks = sorted(
        set(lookup.get("UA", {}).get("matched_ciks", []))
        & set(lookup.get("UAA", {}).get("matched_ciks", []))
    )
    return _record(
        "basis_scale_entity_evidence_map",
        requested_tickers=requested,
        requested_ticker_count=len(requested),
        rows=rows,
        evidence_by_ticker=lookup,
        status_counts=dict(sorted(Counter(row["status"] for row in rows).items())),
        submissions_directory_present=directory_present,
        snapshot_selection_policy={
            "allowed_dates": list(SNAPSHOT_DATES),
            "priority": (
                "One snapshot per CIK; prefer 2026-07-22, fallback to 2026-07-08 only if absent."
            ),
            "fallback_after_missing_ticker_or_invalid_preferred_snapshot": False,
            "ticker_comparison": (
                "Case-insensitive exact code; no punctuation replacement or former-name inference."
            ),
        },
        selected_snapshot_count=len(snapshots),
        selected_snapshot_date_counts=dict(
            sorted(Counter(s["snapshot_date"] for s in snapshots).items())
        ),
        usable_snapshot_count=len(usable),
        snapshots=snapshots,
        same_normalized_name_multiple_ciks=name_ambiguities,
        conservative_alias_check={
            "tickers": ["UA", "UAA"],
            "conservative_grouping_exists_separately": True,
            "shared_stored_cik_evidence": shared_ua_ciks,
            "current_shared_cik_observed": bool(shared_ua_ciks),
            "historical_report_alias_identity_certified": False,
        },
        historical_company_identity_certified_count=0,
        real_company_disjoint_certified=False,
        source_scope=(
            "Only existing local SEC submissions at the two named dates; "
            "no network freshness or all-issuer coverage claim."
        ),
        source_references=[snapshot["source_reference"] for snapshot in snapshots],
        downloaded_files=0,
        Provider_calls=0,
        tokenizer_calls=0,
        Student_calls=0,
        GPU_calls=0,
        support_generation_allowed=False,
        training_allowed=False,
    )
