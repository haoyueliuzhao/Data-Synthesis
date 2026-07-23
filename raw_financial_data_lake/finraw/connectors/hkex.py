from __future__ import annotations

from collections import Counter

from finraw.connectors.base import RawSourceConnector, stable_raw_record_id
from finraw.http import get_url


class HkexConnector(RawSourceConnector):
    source_id = "hkex_disclosures"

    def run(self) -> None:
        announcements = self.config.get("hkex", {}).get("announcements", [])
        job_id = self.begin_job(
            source_id=self.source_id,
            job_type="incremental",
            target_scope={"announcements": announcements},
            config={"dry_run": self.dry_run},
        )
        objects: list[dict] = []
        records_saved = 0
        status_counts: Counter[str] = Counter()
        try:
            for announcement in announcements:
                code = str(announcement.get("stock_code") or "unknown").zfill(5)
                year = str(announcement.get("year") or "unknown")
                report_type = str(announcement.get("report_type") or "annual")
                filename = str(
                    announcement.get("filename")
                    or f"{code}_{year}_{report_type}.pdf"
                )
                relative_path = (
                    f"hkex/reports/stock_code={code}/year={year}/"
                    f"report_type={report_type}/{filename}"
                )
                if self.dry_run:
                    print(
                        f"[dry-run] HKEX GET {announcement['url']} -> "
                        f"{relative_path}"
                    )
                    continue
                document_url = str(announcement["url"])
                existing = self.db.fetchone(
                    "SELECT * FROM raw_objects WHERE source_id = ? "
                    "AND validation_status = ? "
                    "AND (original_url = ? OR original_url LIKE ?) "
                    "ORDER BY retrieval_time DESC LIMIT 1",
                    (
                        self.source_id,
                        "passed",
                        document_url,
                        f"{document_url}?%",
                    ),
                )
                if existing:
                    raw_object = dict(existing)
                    status = "passed"
                else:
                    response = get_url(
                        document_url,
                        headers={
                            "Referer": "https://www.hkexnews.hk/index.htm",
                            "User-Agent": "Mozilla/5.0 RawFinancialDataLake/0.1",
                        },
                        polite_delay_seconds=0.1,
                    )
                    status, notes = self._validate_pdf(
                        response.content, response.status, response.headers
                    )
                    raw_object = self.save_raw_bytes(
                        source_id=self.source_id,
                        job_id=job_id,
                        relative_path=relative_path,
                        content=response.content,
                        object_type="pdf",
                        original_url=document_url,
                        request_params=announcement,
                        response_headers=response.headers,
                        response_status=response.status,
                        validation_status=status,
                        notes=notes,
                        source_publish_date=announcement.get("publish_date"),
                    )
                status_counts[status] += 1
                objects.append(raw_object)
                self.db.upsert_source_entity(
                    source_id=self.source_id,
                    source_code=code,
                    source_name=announcement.get("company_name"),
                    aliases=[],
                    market="HK",
                    raw_metadata={"kind": "listed_company", **announcement},
                )
                if status == "passed":
                    key = announcement.get("announcement_id") or announcement["url"]
                    self.db.insert_raw_records(
                        [
                            {
                                "raw_record_id": stable_raw_record_id(
                                    self.source_id,
                                    raw_object["raw_object_id"],
                                    "hkex_pdf_annual_report",
                                    key,
                                ),
                                "raw_object_id": raw_object["raw_object_id"],
                                "source_id": self.source_id,
                                "record_key": key,
                                "record_type": "hkex_pdf_annual_report",
                                "record_json": announcement
                                | {"storage_uri": raw_object["storage_uri"]},
                                "entity_hint": code,
                                "metric_hint": report_type,
                                "period_hint": year,
                            }
                        ]
                    )
                    records_saved += 1
            self.create_snapshot(
                source_id=self.source_id,
                prefix=f"hkex/disclosures/snapshot_date={self.snapshot_date}",
                objects=objects,
            )
            self.finish_job(
                job_id,
                "success" if status_counts.get("passed") == len(announcements) else "partial",
                records_found=len(announcements),
                records_saved=records_saved,
                error_message=(
                    None
                    if status_counts.get("passed") == len(announcements)
                    else f"validation_status_counts={dict(status_counts)}"
                ),
            )
        except Exception as exc:
            self.finish_job(
                job_id,
                "failed",
                records_found=len(announcements),
                records_saved=records_saved,
                error_message=str(exc),
            )
            raise

    @staticmethod
    def _validate_pdf(
        content: bytes, status: int, headers: dict[str, str]
    ) -> tuple[str, str]:
        if status != 200:
            return "failed", f"HTTP status {status}"
        if not content:
            return "failed", "empty PDF response"
        if content.lstrip().lower().startswith(b"<html"):
            return "failed", "downloaded HTML instead of PDF"
        content_type = " ".join(
            [headers.get("Content-Type", ""), headers.get("content-type", "")]
        ).lower()
        if b"%PDF" not in content[:1024] and "pdf" not in content_type:
            return "warning", "PDF marker/content-type not found"
        return "passed", "HKEX official annual-report PDF saved"
