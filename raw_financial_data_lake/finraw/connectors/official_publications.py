from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from finraw.connectors.base import RawSourceConnector, stable_raw_record_id
from finraw.http import get_url


class OfficialPublicationConnector(RawSourceConnector):
    """Archive immutable publications from registered official authorities."""

    source_id = "official_publications"

    def run(self) -> None:
        targets = list(self.config.get("official_publications", {}).get("targets", []))
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for target in targets:
            source_id = str(target.get("source_id") or "").strip()
            if not source_id:
                raise ValueError("official publication target requires source_id")
            grouped[source_id].append(dict(target))
        for source_id in sorted(grouped):
            self._run_source(source_id, grouped[source_id])

    def _run_source(
        self,
        source_id: str,
        targets: list[dict[str, Any]],
    ) -> None:
        job_id = self.begin_job(
            source_id=source_id,
            job_type="incremental",
            target_scope={"publication_ids": [row["publication_id"] for row in targets]},
            config={"dry_run": self.dry_run, "target_count": len(targets)},
        )
        objects: list[dict[str, Any]] = []
        records_saved = 0
        statuses: Counter[str] = Counter()
        bse_client = None
        if source_id == "bse_market_statistics":
            from finraw.bse_discovery import BsePublicSession

            bse_client = BsePublicSession()
        try:
            for target in targets:
                url = str(target["url"])
                relative_path = self._relative_path(source_id, target)
                if self.dry_run:
                    print(f"[dry-run] {source_id} GET {url} -> {relative_path}")
                    continue
                existing = self.db.fetchone(
                    "SELECT * FROM raw_objects WHERE source_id = ? "
                    "AND original_url = ? AND validation_status = ? "
                    "ORDER BY retrieval_time DESC LIMIT 1",
                    (source_id, url, "passed"),
                )
                if existing and not bool(target.get("mutable")):
                    raw_object = dict(existing)
                    status = "passed"
                else:
                    if bse_client is not None:
                        bse_response = bse_client.get(
                            url,
                            referer=str(
                                target.get("referer")
                                or "https://www.bse.cn/index.html"
                            ),
                        )
                        response_content = bse_response.content
                        response_status = bse_response.status_code
                        response_headers = dict(bse_response.headers)
                    else:
                        response = get_url(
                            url,
                            headers={
                                "Accept": "*/*",
                                "Referer": str(target.get("referer") or url),
                                "User-Agent": "Mozilla/5.0 RawFinancialDataLake/0.1",
                            },
                            retries=int(target.get("retries") or 3),
                            backoff_seconds=float(
                                target.get("backoff_seconds") or 2.0
                            ),
                            polite_delay_seconds=float(
                                target.get("polite_delay_seconds") or 0.25
                            ),
                        )
                        response_content = response.content
                        response_status = response.status
                        response_headers = response.headers
                    object_type = str(target.get("format") or "html").lower()
                    status, notes = self.validate_publication(
                        response_content,
                        response_status,
                        response_headers,
                        object_type,
                    )
                    raw_object = self.save_raw_bytes(
                        source_id=source_id,
                        job_id=job_id,
                        relative_path=relative_path,
                        content=response_content,
                        object_type=object_type,
                        original_url=url,
                        request_params={},
                        response_headers=response_headers,
                        response_status=response_status,
                        validation_status=status,
                        notes=notes,
                        source_publish_date=target.get("publish_date"),
                        source_update_time=target.get("source_update_time"),
                    )
                statuses[status] += 1
                objects.append(raw_object)
                if status != "passed":
                    continue
                publication_id = str(target["publication_id"])
                self.db.insert_raw_records(
                    [
                        {
                            "raw_record_id": stable_raw_record_id(
                                source_id,
                                raw_object["raw_object_id"],
                                "official_publication",
                                publication_id,
                            ),
                            "raw_object_id": raw_object["raw_object_id"],
                            "source_id": source_id,
                            "record_key": publication_id,
                            "record_type": "official_publication",
                            "record_json": target
                            | {"storage_uri": raw_object["storage_uri"]},
                            "entity_hint": target.get("entity_code"),
                            "metric_hint": target.get("publication_category"),
                            "period_hint": target.get("period_hint"),
                        }
                    ]
                )
                if target.get("entity_code"):
                    self.db.upsert_source_entity(
                        source_id=source_id,
                        source_code=str(target["entity_code"]),
                        source_name=target.get("entity_name"),
                        aliases=list(target.get("entity_aliases") or []),
                        market=target.get("market"),
                        raw_metadata={
                            "kind": target.get("entity_type") or "publication_scope",
                            "authority": target.get("authority"),
                        },
                    )
                records_saved += 1
            self.create_snapshot(
                source_id=source_id,
                prefix=f"{source_id}/publications/snapshot_date={self.snapshot_date}",
                objects=objects,
            )
            complete = statuses.get("passed", 0) == len(targets)
            self.finish_job(
                job_id,
                "success" if complete else "partial",
                records_found=len(targets),
                records_saved=records_saved,
                error_message=None if complete else f"validation_status_counts={dict(statuses)}",
            )
        except Exception as exc:
            self.finish_job(
                job_id,
                "failed",
                records_found=len(targets),
                records_saved=records_saved,
                error_message=str(exc),
            )
            raise

    @staticmethod
    def _relative_path(source_id: str, target: dict[str, Any]) -> str:
        publication_id = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            str(target["publication_id"]),
        ).strip("_")
        object_type = str(target.get("format") or "html").lower()
        filename = str(target.get("filename") or f"{publication_id}.{object_type}")
        period = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            str(target.get("period_hint") or "undated"),
        ).strip("_")
        return str(
            Path(source_id)
            / "publications"
            / f"period={period}"
            / filename
        )

    @staticmethod
    def validate_publication(
        content: bytes,
        status: int,
        headers: dict[str, str],
        object_type: str,
    ) -> tuple[str, str]:
        if status != 200:
            return "failed", f"HTTP status {status}"
        if not content:
            return "failed", "empty official publication response"
        sample = content[:8192].lower()
        if any(
            marker in sample
            for marker in (
                b"urlacl",
                b"captcha",
                "异常行为".encode("utf-8"),
                "安全验证".encode("utf-8"),
            )
        ):
            return "failed", "official endpoint returned an access-control page"
        content_type = " ".join(
            [headers.get("Content-Type", ""), headers.get("content-type", "")]
        ).lower()
        if object_type == "pdf":
            if b"%pdf" not in content[:1024].lower() and "pdf" not in content_type:
                return "failed", "PDF marker/content-type not found"
        elif object_type in {"xlsx", "xls"}:
            if not content.startswith(b"PK") and "spreadsheet" not in content_type:
                return "failed", "spreadsheet container/content-type not found"
        elif object_type == "html":
            html_content_type = "html" in content_type
            has_html_marker = any(
                marker in sample for marker in (b"<html", b"<!doctype")
            )
            if len(content) < 500 or not (
                html_content_type or has_html_marker
            ):
                return "failed", "HTML marker or minimum content missing"
        return "passed", "official authority publication archived"
