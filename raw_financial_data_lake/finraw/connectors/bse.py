from __future__ import annotations

from collections import Counter

from finraw.bse_discovery import BSE_DISCLOSURE_REFERER, BsePublicSession
from finraw.connectors.base import RawSourceConnector, stable_raw_record_id


class BseConnector(RawSourceConnector):
    source_id = "bse_disclosures"

    def run(self) -> None:
        announcements = self.config.get("bse", {}).get("announcements", [])
        job_id = self.begin_job(
            source_id=self.source_id,
            job_type="incremental",
            target_scope={"announcements": announcements},
            config={"dry_run": self.dry_run},
        )
        objects = []
        records_saved = 0
        status_counts: Counter[str] = Counter()
        client = BsePublicSession()
        try:
            for announcement in announcements:
                code = str(announcement.get("stock_code") or "unknown")
                year = str(announcement.get("year") or "unknown")
                report_type = str(
                    announcement.get("report_type") or "announcement"
                )
                filename = str(
                    announcement.get("filename")
                    or f"{code}_{year}_{report_type}.pdf"
                )
                relative_path = (
                    f"bse/reports/stock_code={code}/year={year}/"
                    f"report_type={report_type}/{filename}"
                )
                if self.dry_run:
                    print(
                        f"[dry-run] BSE GET {announcement['url']} -> {relative_path}"
                    )
                    continue
                effective_url = self._canonical_original_url(
                    str(announcement["url"]), announcement
                )
                existing = self.db.fetchone(
                    "SELECT * FROM raw_objects WHERE source_id = ? "
                    "AND original_url = ? AND validation_status = ? "
                    "ORDER BY retrieval_time DESC LIMIT 1",
                    (self.source_id, effective_url, "passed"),
                )
                if existing:
                    objects.append(dict(existing))
                    status_counts["passed"] += 1
                    records_saved += 1
                    continue
                response = client.get(
                    str(announcement["url"]),
                    referer=BSE_DISCLOSURE_REFERER,
                )
                status, notes = self._validate_pdf(
                    response.content, response.status_code, dict(response.headers)
                )
                status_counts[status] += 1
                raw_object = self.save_raw_bytes(
                    source_id=self.source_id,
                    job_id=job_id,
                    relative_path=relative_path,
                    content=response.content,
                    object_type="pdf",
                    original_url=str(announcement["url"]),
                    request_params=announcement,
                    response_headers=dict(response.headers),
                    response_status=response.status_code,
                    validation_status=status,
                    notes=notes,
                    source_publish_date=announcement.get("publish_date"),
                )
                objects.append(raw_object)
                self.db.upsert_source_entity(
                    source_id=self.source_id,
                    source_code=code,
                    source_name=announcement.get("company_name"),
                    aliases=[],
                    market="CN",
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
                                    "bse_pdf_announcement",
                                    key,
                                ),
                                "raw_object_id": raw_object["raw_object_id"],
                                "source_id": self.source_id,
                                "record_key": key,
                                "record_type": "bse_pdf_announcement",
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
                prefix=f"bse/disclosures/snapshot_date={self.snapshot_date}",
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
        return "passed", "BSE PDF response saved"
