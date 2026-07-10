from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from finraw.connectors.base import RawSourceConnector, stable_raw_record_id
from finraw.http import get_url


class SecFilingsConnector(RawSourceConnector):
    source_id = "sec_filings"

    def run(self) -> None:
        sec_config = self.config["sec"]
        companies = sec_config.get("filing_companies") or sec_config.get("sample_companies", [])
        forms = set(sec_config.get("filing_forms", ["10-K", "10-Q", "8-K"]))
        limit_per_company = int(sec_config.get("filing_limit_per_company", 5))
        user_agent = sec_config["user_agent"]
        job_id = self.begin_job(
            source_id=self.source_id,
            job_type="incremental",
            target_scope={"companies": companies, "forms": sorted(forms), "limit_per_company": limit_per_company},
            config={"dry_run": self.dry_run},
        )
        objects = []
        records_saved = 0
        records_found = 0

        try:
            for company in companies:
                cik10 = str(company["cik"]).zfill(10)
                cik_int = str(int(cik10))
                self.db.upsert_source_entity(
                    source_id="sec_submissions",
                    source_code=cik10,
                    source_name=company.get("name") or company.get("ticker"),
                    aliases=[company.get("ticker")] if company.get("ticker") else [],
                    market="US",
                    raw_metadata=company,
                )
                submissions_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
                submissions = get_url(
                    submissions_url,
                    headers={"User-Agent": user_agent, "Accept-Encoding": "identity"},
                    polite_delay_seconds=0.1,
                )
                if submissions.status != 200:
                    continue
                payload = submissions.json()
                recent = payload.get("filings", {}).get("recent", {})
                filings = self._recent_filings(recent)
                selected = [filing for filing in filings if filing.get("form") in forms][:limit_per_company]
                records_found += len(selected)

                for filing in selected:
                    accession = filing.get("accessionNumber")
                    primary_doc = filing.get("primaryDocument")
                    if not accession or not primary_doc:
                        continue
                    accession_nodash = accession.replace("-", "")
                    doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{primary_doc}"
                    year = (filing.get("filingDate") or "unknown")[:4]
                    form = (filing.get("form") or "unknown").replace("/", "_")
                    relative_path = (
                        f"sec/filings/cik={cik10}/form={form}/year={year}/"
                        f"accession={accession}/{primary_doc}"
                    )
                    if self.dry_run:
                        print(f"[dry-run] SEC filing GET {doc_url} -> {relative_path}")
                        continue
                    resp = get_url(
                        doc_url,
                        headers={"User-Agent": user_agent, "Accept-Encoding": "identity"},
                        polite_delay_seconds=0.1,
                    )
                    object_type = self._object_type(primary_doc)
                    validation_status, notes = self._validate_document(resp.content, resp.status, object_type)
                    obj = self.save_raw_bytes(
                        source_id=self.source_id,
                        job_id=job_id,
                        relative_path=relative_path,
                        content=resp.content,
                        object_type=object_type,
                        original_url=doc_url,
                        request_params={"cik": cik10, "accession_number": accession, "form": filing.get("form")},
                        response_headers=resp.headers,
                        response_status=resp.status,
                        validation_status=validation_status,
                        notes=notes,
                        source_publish_date=filing.get("filingDate"),
                    )
                    objects.append(obj)
                    if validation_status == "passed":
                        self.db.insert_raw_records([
                            {
                                "raw_record_id": stable_raw_record_id(self.source_id, obj["raw_object_id"], "sec_filing_document", f"{cik10}:{accession}"),
                                "raw_object_id": obj["raw_object_id"],
                                "source_id": self.source_id,
                                "record_key": f"{cik10}:{accession}",
                                "record_type": "sec_filing_document",
                                "record_json": filing | {"document_url": doc_url, "cik": cik10, "ticker": company.get("ticker")},
                                "entity_hint": company.get("ticker") or cik10,
                                "metric_hint": filing.get("form"),
                                "period_hint": filing.get("reportDate") or filing.get("filingDate"),
                            }
                        ])
                        records_saved += 1

            self.create_snapshot(
                source_id=self.source_id,
                prefix=f"sec/filings/snapshot_date={self.snapshot_date}",
                objects=objects,
            )
            self.finish_job(job_id, "success", records_found=records_found, records_saved=records_saved)
        except Exception as exc:
            self.finish_job(job_id, "failed", records_found=records_found, records_saved=records_saved, error_message=str(exc))
            raise

    @staticmethod
    def _recent_filings(recent: dict[str, list[Any]]) -> list[dict[str, Any]]:
        keys = list(recent.keys())
        if not keys:
            return []
        length = max(len(recent.get(key, [])) for key in keys)
        filings = []
        for i in range(length):
            item = {}
            for key in keys:
                values = recent.get(key, [])
                item[key] = values[i] if i < len(values) else None
            filings.append(item)
        return filings

    @staticmethod
    def _object_type(filename: str) -> str:
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix in {"htm", "html"}:
            return "html"
        if suffix in {"xml", "xsd", "xbrl"}:
            return "xbrl"
        if suffix == "txt":
            return "txt"
        return suffix or "document"

    @staticmethod
    def _validate_document(content: bytes, status: int, object_type: str) -> tuple[str, str]:
        if status != 200:
            return "failed", f"HTTP status {status}"
        if not content:
            return "failed", "empty document"
        if object_type in {"html", "txt", "xbrl"} and b"<html" not in content[:1000].lower() and object_type == "html":
            return "warning", "HTML extension but no html tag found in first bytes"
        return "passed", "document downloaded"
