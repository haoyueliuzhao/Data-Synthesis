from __future__ import annotations

import uuid
from typing import Any

from finraw.connectors.base import RawSourceConnector
from finraw.http import get_url


class CninfoConnector(RawSourceConnector):
    source_id = "cninfo_announcements"

    def run(self) -> None:
        announcements = self.config.get("cninfo", {}).get("announcements", [])
        job_id = self.begin_job(
            source_id=self.source_id,
            job_type="incremental",
            target_scope={"announcements": announcements},
            config={"dry_run": self.dry_run},
        )
        objects = []
        records_saved = 0
        try:
            for ann in announcements:
                url = ann["url"]
                stock_code = ann.get("stock_code", "unknown")
                year = ann.get("year", "unknown")
                report_type = ann.get("report_type", "announcement")
                filename = ann.get("filename") or f"{stock_code}_{year}_{report_type}.pdf"
                relative_path = f"cninfo/reports/stock_code={stock_code}/year={year}/report_type={report_type}/{filename}"
                if self.dry_run:
                    print(f"[dry-run] CNInfo GET {url} -> {relative_path}")
                    continue
                resp = get_url(url, headers=ann.get("headers", {}))
                validation_status, notes = self._validate_pdf(resp.content, resp.status, resp.headers)
                obj = self.save_raw_bytes(
                    source_id=self.source_id,
                    job_id=job_id,
                    relative_path=relative_path,
                    content=resp.content,
                    object_type="pdf",
                    original_url=url,
                    request_params={k: v for k, v in ann.items() if k != "headers"},
                    response_headers=resp.headers,
                    response_status=resp.status,
                    validation_status=validation_status,
                    notes=notes,
                    source_publish_date=ann.get("publish_date"),
                )
                objects.append(obj)
                self.db.upsert_source_entity(
                    source_id=self.source_id,
                    source_code=stock_code,
                    source_name=ann.get("company_name"),
                    aliases=[],
                    market="CN",
                    raw_metadata={"kind": "listed_company", **ann},
                )
                if validation_status == "passed":
                    self.db.insert_raw_records([
                        {
                            "raw_record_id": f"rawrec_cninfo_{stock_code}_{uuid.uuid4().hex[:8]}",
                            "raw_object_id": obj["raw_object_id"],
                            "source_id": self.source_id,
                            "record_key": ann.get("announcement_id") or url,
                            "record_type": "cninfo_pdf_announcement",
                            "record_json": ann | {"storage_uri": obj["storage_uri"]},
                            "entity_hint": stock_code,
                            "metric_hint": report_type,
                            "period_hint": str(year),
                        }
                    ])
                    records_saved += 1
            self.create_snapshot(source_id=self.source_id, prefix=f"cninfo/announcements/snapshot_date={self.snapshot_date}", objects=objects)
            self.finish_job(job_id, "success", records_found=len(announcements), records_saved=records_saved)
        except Exception as exc:
            self.finish_job(job_id, "failed", records_found=len(announcements), records_saved=records_saved, error_message=str(exc))
            raise

    @staticmethod
    def _validate_pdf(content: bytes, status: int, headers: dict[str, str]) -> tuple[str, str]:
        if status != 200:
            return "failed", f"HTTP status {status}"
        if not content:
            return "failed", "empty PDF response"
        if content.lstrip().lower().startswith(b"<html"):
            return "failed", "downloaded HTML instead of PDF"
        content_type = " ".join([headers.get("Content-Type", ""), headers.get("content-type", "")]).lower()
        if b"%PDF" not in content[:1024] and "pdf" not in content_type:
            return "warning", "PDF marker/content-type not found"
        return "passed", "PDF response saved"
