from __future__ import annotations

from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

from finraw.connectors.base import RawSourceConnector, stable_raw_record_id
from finraw.http import HttpResponse, get_url


class CninfoConnector(RawSourceConnector):
    source_id = "cninfo_announcements"

    def run(self) -> None:
        settings = dict(self.config.get("cninfo") or {})
        announcements = list(settings.get("announcements") or [])
        workers = max(int(settings.get("download_workers", 8)), 1)
        progress_interval = max(int(settings.get("progress_interval", 50)), 1)
        job_id = self.begin_job(
            source_id=self.source_id,
            job_type="incremental",
            target_scope={"announcements": announcements},
            config={
                "dry_run": self.dry_run,
                "download_workers": workers,
                "progress_interval": progress_interval,
            },
        )
        objects: list[dict[str, Any]] = []
        records_saved = 0
        status_counts: Counter[str] = Counter()
        errors: list[str] = []
        try:
            pending: list[dict[str, Any]] = []
            for announcement in announcements:
                if self.dry_run:
                    print(
                        f"[dry-run] CNInfo GET {announcement['url']} -> "
                        f"{self._relative_path(announcement)}"
                    )
                    continue
                existing = self._existing_object(announcement)
                if existing:
                    objects.append(existing)
                    self._register_record(existing, announcement)
                    records_saved += 1
                    status_counts["resumed"] += 1
                else:
                    pending.append(announcement)

            if self.dry_run:
                self.finish_job(
                    job_id,
                    "success",
                    records_found=len(announcements),
                    records_saved=0,
                )
                return

            completed = len(objects)
            if completed:
                print(
                    f"CNInfo resume: {completed}/{len(announcements)} objects "
                    "already passed validation",
                    flush=True,
                )
            with ThreadPoolExecutor(
                max_workers=workers, thread_name_prefix="cninfo-download"
            ) as executor:
                futures: dict[Future[HttpResponse], dict[str, Any]] = {
                    executor.submit(
                        get_url,
                        str(announcement["url"]),
                        headers=announcement.get("headers", {}),
                    ): announcement
                    for announcement in pending
                }
                for future in as_completed(futures):
                    announcement = futures[future]
                    try:
                        response = future.result()
                        raw_object, validation_status = self._save_response(
                            job_id, announcement, response
                        )
                        objects.append(raw_object)
                        status_counts[validation_status] += 1
                        if validation_status == "passed":
                            self._register_record(raw_object, announcement)
                            records_saved += 1
                    except Exception as exc:
                        status_counts["download_failed"] += 1
                        errors.append(
                            f"{announcement.get('announcement_id') or announcement['url']}: "
                            f"{type(exc).__name__}: {exc}"
                        )
                    completed += 1
                    if completed % progress_interval == 0 or completed == len(
                        announcements
                    ):
                        print(
                            f"CNInfo progress: {completed}/{len(announcements)}; "
                            f"status={dict(status_counts)}",
                            flush=True,
                        )

            objects.sort(key=lambda row: str(row["raw_object_id"]))
            self.create_snapshot(
                source_id=self.source_id,
                prefix=f"cninfo/announcements/snapshot_date={self.snapshot_date}",
                objects=objects,
            )
            failed = status_counts.get("download_failed", 0) + status_counts.get(
                "failed", 0
            )
            status = "success" if failed == 0 else "partial"
            error_message = None
            if failed:
                error_message = (
                    f"status_counts={dict(status_counts)}; errors={errors[:20]}"
                )
            self.finish_job(
                job_id,
                status,
                records_found=len(announcements),
                records_saved=records_saved,
                error_message=error_message,
            )
        except BaseException as exc:
            self.finish_job(
                job_id,
                "failed",
                records_found=len(announcements),
                records_saved=records_saved,
                error_message=f"{type(exc).__name__}: {exc}",
            )
            raise

    def _existing_object(self, announcement: dict[str, Any]) -> dict[str, Any] | None:
        request_params = {
            key: value for key, value in announcement.items() if key != "headers"
        }
        effective_url = self._canonical_original_url(
            str(announcement["url"]), request_params
        )
        row = self.db.fetchone(
            "SELECT * FROM raw_objects WHERE source_id = ? "
            "AND original_url = ? AND validation_status = ? "
            "ORDER BY retrieval_time DESC LIMIT 1",
            (self.source_id, effective_url, "passed"),
        )
        return dict(row) if row else None

    def _save_response(
        self,
        job_id: str,
        announcement: dict[str, Any],
        response: HttpResponse,
    ) -> tuple[dict[str, Any], str]:
        validation_status, notes = self._validate_pdf(
            response.content, response.status, response.headers
        )
        raw_object = self.save_raw_bytes(
            source_id=self.source_id,
            job_id=job_id,
            relative_path=self._relative_path(announcement),
            content=response.content,
            object_type="pdf",
            original_url=str(announcement["url"]),
            request_params={
                key: value for key, value in announcement.items() if key != "headers"
            },
            response_headers=response.headers,
            response_status=response.status,
            validation_status=validation_status,
            notes=notes,
            source_publish_date=announcement.get("publish_date"),
        )
        return raw_object, validation_status

    def _register_record(
        self, raw_object: dict[str, Any], announcement: dict[str, Any]
    ) -> None:
        stock_code = str(announcement.get("stock_code") or "unknown")
        report_type = str(announcement.get("report_type") or "announcement")
        key = announcement.get("announcement_id") or announcement["url"]
        self.db.upsert_source_entity(
            source_id=self.source_id,
            source_code=stock_code,
            source_name=announcement.get("company_name"),
            aliases=[],
            market="CN",
            raw_metadata={"kind": "listed_company", **announcement},
        )
        self.db.insert_raw_records(
            [
                {
                    "raw_record_id": stable_raw_record_id(
                        self.source_id,
                        raw_object["raw_object_id"],
                        "cninfo_pdf_announcement",
                        key,
                    ),
                    "raw_object_id": raw_object["raw_object_id"],
                    "source_id": self.source_id,
                    "record_key": key,
                    "record_type": "cninfo_pdf_announcement",
                    "record_json": announcement
                    | {"storage_uri": raw_object["storage_uri"]},
                    "entity_hint": stock_code,
                    "metric_hint": report_type,
                    "period_hint": str(announcement.get("year") or "unknown"),
                }
            ]
        )

    @staticmethod
    def _relative_path(announcement: dict[str, Any]) -> str:
        stock_code = str(announcement.get("stock_code") or "unknown")
        year = str(announcement.get("year") or "unknown")
        report_type = str(announcement.get("report_type") or "announcement")
        filename = str(
            announcement.get("filename") or f"{stock_code}_{year}_{report_type}.pdf"
        )
        return (
            f"cninfo/reports/stock_code={stock_code}/year={year}/"
            f"report_type={report_type}/{filename}"
        )

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
        return "passed", "PDF response saved"
