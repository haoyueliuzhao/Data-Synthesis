from __future__ import annotations

import os
from typing import Any

from finraw.connectors.base import RawSourceConnector, stable_raw_record_id
from finraw.http import get_url


class FredConnector(RawSourceConnector):
    source_id = "fred_observations"

    def run(self) -> None:
        cfg = self.config["fred"]
        series_ids = cfg["series_ids"]
        api_key = os.environ.get("FRED_API_KEY") or cfg.get("api_key")
        vintage_excluded_series = {
            str(value) for value in cfg.get("vintage_excluded_series", [])
        }
        if not api_key:
            raise RuntimeError("FRED_API_KEY is not set and config/local_secrets.json does not contain fred.api_key")
        objects = []
        records_saved = 0
        job_id = self.begin_job(
            source_id=self.source_id,
            job_type="full_refresh",
            target_scope={"series_ids": series_ids},
            config={"dry_run": self.dry_run, "api_key_env": "FRED_API_KEY"},
        )

        try:
            for series_id in series_ids:
                metadata = self._fetch_json_object(
                    job_id=job_id,
                    source_id="fred_observations",
                    url=f"{cfg['base_url']}/series",
                    params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
                    relative_path=f"fred/series_metadata/series_id={series_id}/snapshot_date={self.snapshot_date}.json",
                    object_type="json",
                    required_key=b"seriess",
                    dry_run_label=f"FRED series metadata {series_id}",
                ) if cfg.get("include_metadata", True) else None
                if metadata:
                    objects.append(metadata["object"])
                    payload = metadata["payload"]
                    series_rows = payload.get("seriess", [])
                    if series_rows:
                        row = series_rows[0]
                        self.db.upsert_source_entity(
                            source_id=self.source_id,
                            source_code=series_id,
                            source_name=row.get("title"),
                            aliases=[],
                            market="US_Global",
                            raw_metadata=row,
                        )
                        self.db.insert_raw_records([
                            self._record(metadata["object"], series_id, "fred_series_metadata", row, series_id, series_id, None)
                        ])
                        records_saved += 1

                observations = self._fetch_json_object(
                    job_id=job_id,
                    source_id=self.source_id,
                    url=f"{cfg['base_url']}/series/observations",
                    params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
                    relative_path=f"fred/observations/series_id={series_id}/snapshot_date={self.snapshot_date}.json",
                    object_type="json",
                    required_key=b"observations",
                    dry_run_label=f"FRED observations {series_id}",
                )
                if observations:
                    objects.append(observations["object"])
                    raw_records = [
                        self._record(observations["object"], f"{series_id}:{item.get('date')}", "fred_observation", item, series_id, series_id, item.get("date"))
                        for item in observations["payload"].get("observations", [])
                    ]
                    self.db.insert_raw_records(raw_records)
                    records_saved += len(raw_records)

                if cfg.get("include_release", True):
                    release = self._fetch_json_object(
                        job_id=job_id,
                        source_id=self.source_id,
                        url=f"{cfg['base_url']}/series/release",
                        params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
                        relative_path=f"fred/release/series_id={series_id}/snapshot_date={self.snapshot_date}.json",
                        object_type="json",
                        required_key=b"releases",
                        dry_run_label=f"FRED release {series_id}",
                    )
                    if release:
                        objects.append(release["object"])
                        rows = release["payload"].get("releases", [])
                        self.db.insert_raw_records([
                            self._record(release["object"], f"{series_id}:release", "fred_release", rows, series_id, series_id, None)
                        ])
                        records_saved += 1

                if (
                    cfg.get("include_vintages", True)
                    and series_id not in vintage_excluded_series
                ):
                    vintage = self._fetch_json_object(
                        job_id=job_id,
                        source_id=self.source_id,
                        url=f"{cfg['base_url']}/series/vintagedates",
                        params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
                        relative_path=f"fred/vintages/series_id={series_id}/snapshot_date={self.snapshot_date}.json",
                        object_type="json",
                        required_key=b"vintage_dates",
                        dry_run_label=f"FRED vintage dates {series_id}",
                    )
                    if vintage:
                        objects.append(vintage["object"])
                        dates = vintage["payload"].get("vintage_dates", [])
                        self.db.insert_raw_records([
                            self._record(vintage["object"], f"{series_id}:vintages", "fred_vintage_dates", {"vintage_dates": dates}, series_id, series_id, None)
                        ])
                        records_saved += 1

            self.create_snapshot(
                source_id=self.source_id,
                prefix=f"fred/snapshot_date={self.snapshot_date}",
                objects=objects,
            )
            self.finish_job(job_id, "success", records_found=len(series_ids), records_saved=records_saved)
        except Exception as exc:
            self.finish_job(job_id, "failed", records_found=len(series_ids), records_saved=records_saved, error_message=str(exc))
            raise

    def _fetch_json_object(
        self,
        *,
        job_id: str,
        source_id: str,
        url: str,
        params: dict[str, Any],
        relative_path: str,
        object_type: str,
        required_key: bytes,
        dry_run_label: str,
    ) -> dict[str, Any] | None:
        safe_params = {k: v for k, v in params.items() if k != "api_key"}
        if self.dry_run:
            print(f"[dry-run] {dry_run_label} GET {url} params={safe_params} -> {relative_path}")
            return None
        resp = get_url(url, params=params)
        validation_status, notes = self._validate_payload(resp.content, resp.status, required_key)
        obj = self.save_raw_bytes(
            source_id=source_id,
            job_id=job_id,
            relative_path=relative_path,
            content=resp.content,
            object_type=object_type,
            original_url=url,
            request_params=safe_params,
            response_headers=resp.headers,
            response_status=resp.status,
            validation_status=validation_status,
            notes=notes,
        )
        payload = resp.json() if validation_status == "passed" else {}
        return {"object": obj, "payload": payload}

    @staticmethod
    def _record(obj: dict[str, Any], key: str, record_type: str, payload: Any, entity: str, metric: str, period: str | None) -> dict[str, Any]:
        return {
            "raw_record_id": stable_raw_record_id("fred_observations", obj["raw_object_id"], record_type, key),
            "raw_object_id": obj["raw_object_id"],
            "source_id": "fred_observations",
            "record_key": key,
            "record_type": record_type,
            "record_json": payload,
            "entity_hint": entity,
            "metric_hint": metric,
            "period_hint": period,
        }

    @staticmethod
    def _validate_payload(content: bytes, status: int, required_key: bytes) -> tuple[str, str]:
        if status != 200:
            return "failed", f"HTTP status {status}"
        if required_key not in content:
            return "failed", f"missing {required_key.decode()} key"
        return "passed", f"{required_key.decode()} found"
