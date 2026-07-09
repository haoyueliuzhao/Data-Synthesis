from __future__ import annotations

import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol

TEXT_OBJECT_TYPES = {"html", "htm", "txt"}
DOCUMENT_SOURCES = {"sec_filings", "cninfo_announcements"}


def refresh_document_extraction(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None) -> dict[str, Any]:
    for table in ["candidate_facts", "raw_extracted_tables", "document_text_chunks"]:
        db.execute(f"DELETE FROM {table}")
    objects = [dict(row) for row in db.fetchall(
        """
        SELECT raw_object_id, source_id, object_type, storage_uri, original_url, request_params,
               content_size_bytes, source_publish_date, validation_status
        FROM raw_objects
        WHERE source_id IN ('sec_filings', 'cninfo_announcements')
          AND validation_status IN ('passed', 'warning')
        """
    )]
    raw_records = [dict(row) for row in db.fetchall("SELECT raw_object_id, record_type, record_json, entity_hint, metric_hint, period_hint FROM raw_records WHERE source_id IN ('sec_filings', 'cninfo_announcements')")]
    record_by_object = {row.get("raw_object_id"): row for row in raw_records}
    alias_map = _entity_alias_map(db)
    metric_alias_map = _metric_alias_map(db)
    report = {
        "object_count": len(objects),
        "chunk_count": 0,
        "table_placeholder_count": 0,
        "extracted_table_count": 0,
        "candidate_count": 0,
        "inline_xbrl_candidate_count": 0,
        "source_counts": Counter(),
        "notes": [
            "HTML/TXT filing documents are chunked as text evidence for later retrieval and QA evidence grounding.",
            "SEC HTML tables and inline XBRL numeric tags are extracted into raw_extracted_tables/candidate_facts, not promoted directly to atomic_facts.",
            "PDF documents currently receive metadata chunks only because no local PDF text/table parser is installed; numeric table extraction is not promoted to atomic_facts.",
            "raw_extracted_tables placeholder rows remain for documents where table extraction was not available.",
        ],
    }
    for obj in objects:
        source_id = obj.get("source_id")
        record = record_by_object.get(obj.get("raw_object_id"), {})
        metadata = _json_value(record.get("record_json")) if record else {}
        if not isinstance(metadata, dict):
            metadata = {}
        chunks = _chunks_for_object(obj, metadata)
        for chunk in chunks:
            db.execute(
                """
                INSERT INTO document_text_chunks (
                    chunk_id, raw_object_id, source_id, page_number, section_title, text,
                    char_start, char_end, extraction_method, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [chunk[k] for k in ["chunk_id", "raw_object_id", "source_id", "page_number", "section_title", "text", "char_start", "char_end", "extraction_method", "confidence_score"]],
            )
            report["chunk_count"] += 1
        tables = _tables_for_object(obj)
        if not tables:
            tables = [_table_placeholder(obj)]
        first_table_id = tables[0]["table_id"]
        for table in tables:
            db.execute(
                """
                INSERT INTO raw_extracted_tables (
                    table_id, raw_object_id, source_id, page_number, table_index,
                    raw_table_json, extraction_method, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [table["table_id"], table["raw_object_id"], table["source_id"], table["page_number"], table["table_index"], json.dumps(table["raw_table_json"], ensure_ascii=False, sort_keys=True), table["extraction_method"], table["confidence_score"]],
            )
            if table["extraction_method"] == "not_run":
                report["table_placeholder_count"] += 1
            else:
                report["extracted_table_count"] += 1
        candidates = []
        candidate = _candidate_for_document(obj, record, metadata, alias_map, first_table_id)
        if candidate:
            candidates.append(candidate)
        inline_candidates = _inline_xbrl_candidates(obj, metadata, alias_map, metric_alias_map, first_table_id)
        candidates.extend(inline_candidates)
        report["inline_xbrl_candidate_count"] += len(inline_candidates)
        for candidate in candidates:
            db.execute(
                """
                INSERT INTO candidate_facts (
                    candidate_id, raw_object_id, table_id, entity_id, metric_hint, value,
                    unit, period_hint, evidence_text, confidence_score, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [candidate[k] for k in ["candidate_id", "raw_object_id", "table_id", "entity_id", "metric_hint", "value", "unit", "period_hint", "evidence_text", "confidence_score", "review_status"]],
            )
            report["candidate_count"] += 1
        report["source_counts"][source_id] += 1
    final_report = {
        "object_count": report["object_count"],
        "chunk_count": report["chunk_count"],
        "table_placeholder_count": report["table_placeholder_count"],
        "extracted_table_count": report["extracted_table_count"],
        "candidate_count": report["candidate_count"],
        "inline_xbrl_candidate_count": report["inline_xbrl_candidate_count"],
        "source_counts": dict(sorted(report["source_counts"].items())),
        "notes": report["notes"],
    }
    if output_dir:
        paths = write_document_extraction_report(final_report, output_dir)
        final_report["written_files"] = [str(path) for path in paths]
    return final_report


def _chunks_for_object(obj: dict[str, Any], metadata: dict[str, Any]) -> list[dict[str, Any]]:
    object_type = str(obj.get("object_type") or "").lower()
    if object_type in TEXT_OBJECT_TYPES:
        text = _read_text(obj.get("storage_uri"))
        if text:
            text = _clean_html(text) if object_type in {"html", "htm"} else _clean_text(text)
            return _split_chunks(obj, text, metadata, "html_text" if object_type in {"html", "htm"} else "plain_text")
    title = metadata.get("title") or metadata.get("form") or metadata.get("report_type") or obj.get("original_url")
    summary = json.dumps({
        "title": title,
        "storage_uri": obj.get("storage_uri"),
        "original_url": obj.get("original_url"),
        "source_publish_date": str(obj.get("source_publish_date") or ""),
        "content_size_bytes": obj.get("content_size_bytes"),
    }, ensure_ascii=False, sort_keys=True, default=str)
    return [_chunk(obj, summary, 0, len(summary), "document_metadata", title, 0.65)]


def _split_chunks(obj: dict[str, Any], text: str, metadata: dict[str, Any], method: str) -> list[dict[str, Any]]:
    max_chars = 3000
    chunks = []
    title = metadata.get("title") or metadata.get("form") or metadata.get("report_type") or "document"
    for start in range(0, len(text), max_chars):
        piece = text[start:start + max_chars].strip()
        if not piece:
            continue
        chunks.append(_chunk(obj, piece, start, start + len(piece), method, title, 0.82))
        if len(chunks) >= 20:
            break
    return chunks


def _chunk(obj: dict[str, Any], text: str, start: int, end: int, method: str, title: Any, confidence: float) -> dict[str, Any]:
    return {
        "chunk_id": _id("chunk", obj.get("raw_object_id"), start, end, method),
        "raw_object_id": obj.get("raw_object_id"),
        "source_id": obj.get("source_id"),
        "page_number": None,
        "section_title": str(title or "")[:500],
        "text": text,
        "char_start": start,
        "char_end": end,
        "extraction_method": method,
        "confidence_score": confidence,
    }


def _tables_for_object(obj: dict[str, Any]) -> list[dict[str, Any]]:
    object_type = str(obj.get("object_type") or "").lower()
    if object_type not in {"html", "htm"}:
        return []
    raw = _read_text(obj.get("storage_uri"))
    if not raw or "<table" not in raw.lower():
        return []
    tables = []
    for idx, match in enumerate(re.finditer(r"(?is)<table\b.*?</table>", raw)):
        if idx >= 25:
            break
        table_html = match.group(0)
        rows = _html_table_rows(table_html)
        if not rows:
            continue
        payload = {"rows": rows[:80], "truncated_rows": max(0, len(rows) - 80), "char_start": match.start(), "char_end": match.end()}
        tables.append({
            "table_id": _id("table", obj.get("raw_object_id"), idx, match.start(), match.end()),
            "raw_object_id": obj.get("raw_object_id"),
            "source_id": obj.get("source_id"),
            "page_number": None,
            "table_index": idx,
            "raw_table_json": payload,
            "extraction_method": "html_table_regex",
            "confidence_score": 0.58,
        })
    return tables


def _html_table_rows(table_html: str) -> list[list[str]]:
    rows = []
    for tr in re.finditer(r"(?is)<tr\b.*?</tr>", table_html):
        cells = []
        for cell in re.finditer(r"(?is)<t[dh]\b.*?</t[dh]>", tr.group(0)):
            text = _clean_html(cell.group(0))
            if text:
                cells.append(text[:500])
        if cells:
            rows.append(cells)
    return rows


def _inline_xbrl_candidates(
    obj: dict[str, Any],
    metadata: dict[str, Any],
    alias_map: dict[tuple[str, str], str],
    metric_alias_map: dict[str, str],
    table_id: str,
) -> list[dict[str, Any]]:
    if str(obj.get("object_type") or "").lower() not in {"html", "htm"}:
        return []
    raw = _read_text(obj.get("storage_uri"))
    if not raw or "ix:" not in raw[:200000].lower() and "ix:" not in raw.lower():
        return []
    context_map = _inline_context_map(raw)
    unit_map = _inline_unit_map(raw)
    entity_id = _entity_for_document(obj, metadata, alias_map)
    if not entity_id:
        return []
    candidates = []
    seen = set()
    pattern = re.compile(r"(?is)<ix:nonfraction\b([^>]*)>(.*?)</ix:nonfraction>")
    for match in pattern.finditer(raw):
        attrs = _html_attrs(match.group(1))
        concept = attrs.get("name")
        metric_id = metric_alias_map.get(concept or "")
        if not concept or not metric_id:
            continue
        value = _numeric_text(match.group(2))
        if value is None:
            continue
        unit_ref = attrs.get("unitref")
        unit = _candidate_unit(unit_ref, unit_map, attrs)
        context_ref = attrs.get("contextref")
        period_hint = _candidate_period_hint(context_ref, context_map, metadata)
        key = (metric_id, concept, value, unit, period_hint)
        if key in seen:
            continue
        seen.add(key)
        evidence = _clean_html(match.group(0))[:1000]
        candidates.append({
            "candidate_id": _id("cand", obj.get("raw_object_id"), concept, value, unit, period_hint),
            "raw_object_id": obj.get("raw_object_id"),
            "table_id": table_id,
            "entity_id": entity_id,
            "metric_hint": metric_id,
            "value": value,
            "unit": unit or "inline_xbrl_unit",
            "period_hint": str(period_hint or ""),
            "evidence_text": evidence,
            "confidence_score": 0.86,
            "review_status": "inline_xbrl_candidate",
        })
        if len(candidates) >= 300:
            break
    return candidates


def _inline_context_map(raw: str) -> dict[str, dict[str, str]]:
    contexts = {}
    for match in re.finditer(r"(?is)<xbrli:context\b([^>]*)>(.*?)</xbrli:context>", raw):
        attrs = _html_attrs(match.group(1))
        context_id = attrs.get("id")
        if not context_id:
            continue
        body = match.group(2)
        item = {}
        for key in ["startdate", "enddate", "instant"]:
            date_match = re.search(rf"(?is)<xbrli:{key}>(.*?)</xbrli:{key}>", body)
            if date_match:
                item[key] = _clean_text(date_match.group(1))
        if item:
            contexts[context_id] = item
    return contexts


def _inline_unit_map(raw: str) -> dict[str, str]:
    units = {}
    for match in re.finditer(r"(?is)<xbrli:unit\b([^>]*)>(.*?)</xbrli:unit>", raw):
        attrs = _html_attrs(match.group(1))
        unit_id = attrs.get("id")
        if not unit_id:
            continue
        body = match.group(2)
        measures = re.findall(r"(?is)<xbrli:measure>(.*?)</xbrli:measure>", body)
        if measures:
            clean = [m.split(":")[-1].strip() for m in measures]
            units[unit_id] = "/".join(clean)
    return units


def _candidate_unit(unit_ref: str | None, unit_map: dict[str, str], attrs: dict[str, str]) -> str:
    base = unit_map.get(unit_ref or "") or unit_ref or "inline_xbrl_unit"
    details = []
    for key in ["scale", "decimals", "format"]:
        if attrs.get(key):
            details.append(f"{key}={attrs[key]}")
    return base if not details else f"{base}; " + "; ".join(details)


def _candidate_period_hint(context_ref: str | None, context_map: dict[str, dict[str, str]], metadata: dict[str, Any]) -> str:
    context = context_map.get(context_ref or "")
    if context:
        payload = {"context_ref": context_ref, **context}
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    fallback = metadata.get("reportDate") or metadata.get("filingDate") or context_ref or ""
    return str(fallback)


def _html_attrs(value: str) -> dict[str, str]:
    attrs = {}
    for match in re.finditer(r"([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(['\"])(.*?)\2", value):
        attrs[match.group(1).lower()] = html.unescape(match.group(3))
    return attrs


def _numeric_text(value: str) -> str | None:
    text = _clean_html(value)
    if not text:
        return None
    neg = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = text.replace(",", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text or text in {"-", "."}:
        return None
    if text.count(".") > 1:
        return None
    if neg and not text.startswith("-"):
        text = "-" + text
    return text


def _metric_alias_map(db: DBProtocol) -> dict[str, str]:
    mapping = {}
    for row in db.fetchall("SELECT raw_concept_name, metric_id FROM metric_alias_map WHERE source_id = 'sec_companyfacts'"):
        concept = row.get("raw_concept_name")
        metric_id = row.get("metric_id")
        if concept and metric_id:
            mapping[str(concept)] = metric_id
    return mapping


def _entity_for_document(obj: dict[str, Any], metadata: dict[str, Any], alias_map: dict[tuple[str, str], str]) -> str | None:
    source_id = obj.get("source_id")
    source_code = str(metadata.get("stock_code") or metadata.get("cik") or "")
    candidates = [source_code]
    if source_code.isdigit():
        candidates.append(source_code.zfill(10))
    for source in [source_id, "sec_submissions", "sec_companyfacts"]:
        for code in candidates:
            entity_id = alias_map.get((source, code))
            if entity_id:
                return entity_id
    return None


def _table_placeholder(obj: dict[str, Any]) -> dict[str, Any]:
    payload = {"status": "not_run", "reason": "table extraction requires source-specific parser and validation", "storage_uri": obj.get("storage_uri")}
    return {
        "table_id": _id("table", obj.get("raw_object_id"), "not_run"),
        "raw_object_id": obj.get("raw_object_id"),
        "source_id": obj.get("source_id"),
        "page_number": None,
        "table_index": 0,
        "raw_table_json": payload,
        "extraction_method": "not_run",
        "confidence_score": 0.0,
    }


def _candidate_for_document(obj: dict[str, Any], record: dict[str, Any], metadata: dict[str, Any], alias_map: dict[tuple[str, str], str], table_id: str) -> dict[str, Any] | None:
    source_id = obj.get("source_id")
    source_code = str(metadata.get("stock_code") or metadata.get("cik") or record.get("entity_hint") or "")
    entity_id = alias_map.get((source_id, source_code)) or alias_map.get(("sec_submissions", source_code.zfill(10) if source_code.isdigit() else source_code))
    if not entity_id:
        return None
    metric_hint = metadata.get("report_type") or metadata.get("form") or record.get("metric_hint")
    period_hint = str(metadata.get("year") or metadata.get("reportDate") or metadata.get("filingDate") or record.get("period_hint") or "")
    evidence = metadata.get("title") or metadata.get("primaryDocument") or metadata.get("document_url") or obj.get("original_url")
    return {
        "candidate_id": _id("cand", obj.get("raw_object_id"), entity_id, metric_hint, period_hint),
        "raw_object_id": obj.get("raw_object_id"),
        "table_id": table_id,
        "entity_id": entity_id,
        "metric_hint": str(metric_hint or "document"),
        "value": "1",
        "unit": "document",
        "period_hint": period_hint,
        "evidence_text": str(evidence or "")[:2000],
        "confidence_score": 0.72,
        "review_status": "document_metadata_only",
    }


def _entity_alias_map(db: DBProtocol) -> dict[tuple[str, str], str]:
    mapping = {}
    for row in db.fetchall("SELECT source_id, source_code, alias, entity_id FROM entity_alias_map"):
        source_id = row.get("source_id")
        entity_id = row.get("entity_id")
        for key in [row.get("source_code"), row.get("alias")]:
            if source_id and key and entity_id:
                mapping[(source_id, str(key))] = entity_id
    return mapping


def _read_text(path: Any) -> str | None:
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def _clean_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?</\\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return _clean_text(html.unescape(value))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def write_document_extraction_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "document_extraction_report.json"
    md_path = out / "document_extraction_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    lines = ["# Document Extraction Report", "", f"Objects: {report['object_count']}", f"Chunks: {report['chunk_count']}", f"Extracted tables: {report.get('extracted_table_count', 0)}", f"Table placeholders: {report['table_placeholder_count']}", f"Candidates: {report['candidate_count']}", f"Inline XBRL candidates: {report.get('inline_xbrl_candidate_count', 0)}", "", "## Sources", ""]
    for key, value in report.get("source_counts", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Notes", ""])
    for note in report.get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return [json_path, md_path]


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"
