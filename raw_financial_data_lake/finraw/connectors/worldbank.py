from __future__ import annotations

import json
import time
from typing import Any

from finraw.connectors.base import RawSourceConnector, stable_raw_record_id
from finraw.http import get_url


class WorldBankConnector(RawSourceConnector):
    source_id = "worldbank_indicators"

    def run(self) -> None:
        cfg = self.config["worldbank"]
        countries = cfg["countries"]
        indicators = cfg["indicators"]
        date_range = cfg["date_range"]
        targets = [(country, indicator) for country in countries for indicator in indicators]
        objects = []
        records_saved = 0
        job_id = self.begin_job(
            source_id=self.source_id,
            job_type="full_refresh",
            target_scope={"countries": countries, "indicators": indicators, "date_range": date_range},
            config={"dry_run": self.dry_run},
        )

        try:
            if cfg.get("include_country_metadata", True):
                for country in countries:
                    result = self._fetch_json(job_id, f"{cfg['base_url']}/country/{country}", {"format": "json"}, f"worldbank/country_metadata/country={country}/snapshot_date={self.snapshot_date}.json", f"WorldBank country metadata {country}")
                    if result:
                        objects.append(result["object"])
                        rows = result["payload"][1] if len(result["payload"]) > 1 else []
                        if rows:
                            row = rows[0]
                            self.db.upsert_source_entity(source_id=self.source_id, source_code=country, source_name=row.get("name"), market="Global", raw_metadata={"kind": "country", **row})
                            self.db.insert_raw_records([self._record(result["object"], country, "wb_country_metadata", row, country, None, None)])
                            records_saved += 1

            if cfg.get("include_indicator_metadata", True):
                for indicator in indicators:
                    result = self._fetch_json(job_id, f"{cfg['base_url']}/indicator/{indicator}", {"format": "json"}, f"worldbank/indicator_metadata/indicator={indicator}/snapshot_date={self.snapshot_date}.json", f"WorldBank indicator metadata {indicator}")
                    if result:
                        objects.append(result["object"])
                        rows = result["payload"][1] if len(result["payload"]) > 1 else []
                        if rows:
                            row = rows[0]
                            self.db.upsert_source_entity(source_id=self.source_id, source_code=indicator, source_name=row.get("name"), market="Global", raw_metadata={"kind": "indicator", **row})
                            self.db.insert_raw_records([self._record(result["object"], indicator, "wb_indicator_metadata", row, None, indicator, None)])
                            records_saved += 1

            for country, indicator in targets:
                pages = self._fetch_observation_pages(job_id, cfg["base_url"], country, indicator, date_range)
                for result in pages:
                    objects.append(result["object"])
                    rows = result["payload"][1] if len(result["payload"]) > 1 else []
                    raw_records = [
                        self._record(result["object"], f"{country}:{indicator}:{item.get('date')}", "wb_observation", item, country, indicator, item.get("date"))
                        for item in rows or []
                    ]
                    self.db.insert_raw_records(raw_records)
                    records_saved += len(raw_records)

            self.create_snapshot(
                source_id=self.source_id,
                prefix=f"worldbank/snapshot_date={self.snapshot_date}",
                objects=objects,
            )
            self.finish_job(job_id, "success", records_found=len(targets), records_saved=records_saved)
        except Exception as exc:
            self.finish_job(job_id, "failed", records_found=len(targets), records_saved=records_saved, error_message=str(exc))
            raise

    def _fetch_observation_pages(self, job_id: str, base_url: str, country: str, indicator: str, date_range: str) -> list[dict[str, Any]]:
        results = []
        page = 1
        while True:
            params = {"format": "json", "date": date_range, "per_page": 1000, "page": page}
            relative_path = (
                f"worldbank/indicators/country={country}/indicator={indicator}/"
                f"snapshot_date={self.snapshot_date}/page={page}.json"
            )
            result = self._fetch_json(job_id, f"{base_url}/country/{country}/indicator/{indicator}", params, relative_path, f"WorldBank observations {country} {indicator} page {page}")
            if not result:
                break
            results.append(result)
            meta = result["payload"][0] if result["payload"] else {}
            pages = int(meta.get("pages") or 1)
            if page >= pages:
                break
            page += 1
        return results

    def _fetch_json(self, job_id: str, url: str, params: dict[str, Any], relative_path: str, dry_run_label: str) -> dict[str, Any] | None:
        if self.dry_run:
            print(f"[dry-run] {dry_run_label} GET {url} params={params} -> {relative_path}")
            return None

        canonical_url = self._canonical_original_url(url, params)
        existing = self.db.fetchone(
            "SELECT * FROM raw_objects WHERE source_id = ? AND original_url = ? AND validation_status = ?",
            (self.source_id, canonical_url, "passed"),
        )
        if existing:
            return {"object": dict(existing), "payload": [], "skipped_existing": True}

        print(f"[worldbank] fetch {dry_run_label}", flush=True)
        content = b""
        headers: dict[str, str] = {}
        status = 0
        validation_status = "failed"
        notes = "request not attempted"
        for attempt in range(3):
            try:
                resp = get_url(url, params=params, retries=1, timeout_seconds=25)
                validation_status, notes = self._validate_payload(
                    resp.content, resp.status
                )
                content = resp.content
                headers = resp.headers
                status = resp.status
                if validation_status == "passed":
                    break
                retryable = resp.status in {400, 408, 429, 500, 502, 503, 504}
                if not retryable or attempt == 2:
                    break
            except Exception as exc:
                content = self.json_bytes({"error": str(exc), "url": canonical_url})
                headers = {}
                status = 0
                validation_status = "failed"
                notes = f"request failed: {exc}"
                if attempt == 2:
                    break
            time.sleep(attempt + 1)
        obj = self.save_raw_bytes(
            source_id=self.source_id,
            job_id=job_id,
            relative_path=relative_path,
            content=content,
            object_type="json",
            original_url=url,
            request_params=params,
            response_headers=headers,
            response_status=status,
            validation_status=validation_status,
            notes=notes,
        )
        payload = json.loads(content.decode("utf-8")) if validation_status == "passed" else []
        return {"object": obj, "payload": payload}

    @staticmethod
    def _record(obj: dict[str, Any], key: str, record_type: str, payload: Any, entity: str | None, metric: str | None, period: str | None) -> dict[str, Any]:
        return {
            "raw_record_id": stable_raw_record_id("worldbank_indicators", obj["raw_object_id"], record_type, key),
            "raw_object_id": obj["raw_object_id"],
            "source_id": "worldbank_indicators",
            "record_key": key,
            "record_type": record_type,
            "record_json": payload,
            "entity_hint": entity,
            "metric_hint": metric,
            "period_hint": period,
        }

    @staticmethod
    def _validate_payload(content: bytes, status: int) -> tuple[str, str]:
        if status != 200:
            return "failed", f"HTTP status {status}"
        if not content.strip().startswith(b"["):
            return "failed", "World Bank response is not JSON array"
        return "passed", "World Bank JSON array response"
