from __future__ import annotations

from typing import Any

from finraw.connectors.base import RawSourceConnector, stable_raw_record_id
from finraw.http import get_url


class ImfSdmxConnector(RawSourceConnector):
    source_id = "imf_sdmx"

    def run(self) -> None:
        targets = self.config.get("imf", {}).get("targets", [])
        job_id = self.begin_job(
            source_id=self.source_id,
            job_type="full_refresh",
            target_scope={"targets": targets},
            config={"dry_run": self.dry_run},
        )
        objects = []
        records_saved = 0
        try:
            for target in targets:
                url = target["url"]
                params = target.get("params", {})
                dataset = target.get("dataset", "unknown")
                object_type = target.get("object_type", "json")
                relative_path = target.get(
                    "relative_path",
                    f"imf/sdmx/dataset={dataset}/snapshot_date={self.snapshot_date}/{target.get('name', 'response')}.{object_type}",
                ).format(snapshot_date=self.snapshot_date, dataset=dataset)
                if self.dry_run:
                    print(f"[dry-run] IMF GET {url} params={params} -> {relative_path}")
                    continue
                resp = get_url(url, params=params, headers=target.get("headers", {}))
                validation_status, notes = self._validate(resp.content, resp.status, object_type)
                obj = self.save_raw_bytes(
                    source_id=self.source_id,
                    job_id=job_id,
                    relative_path=relative_path,
                    content=resp.content,
                    object_type=object_type,
                    original_url=url,
                    request_params=params,
                    response_headers=resp.headers,
                    response_status=resp.status,
                    validation_status=validation_status,
                    notes=notes,
                )
                objects.append(obj)
                if validation_status in {"passed", "warning"}:
                    self.db.insert_raw_records([
                        {
                            "raw_record_id": stable_raw_record_id(self.source_id, obj["raw_object_id"], "imf_sdmx_response", target.get("name") or dataset),
                            "raw_object_id": obj["raw_object_id"],
                            "source_id": self.source_id,
                            "record_key": target.get("name") or dataset,
                            "record_type": "imf_sdmx_response",
                            "record_json": {"dataset": dataset, "target": target, "storage_uri": obj["storage_uri"]},
                            "entity_hint": dataset,
                            "metric_hint": target.get("name"),
                            "period_hint": None,
                        }
                    ])
                    records_saved += 1
            self.create_snapshot(source_id=self.source_id, prefix=f"imf/sdmx/snapshot_date={self.snapshot_date}", objects=objects)
            self.finish_job(job_id, "success", records_found=len(targets), records_saved=records_saved)
        except Exception as exc:
            self.finish_job(job_id, "failed", records_found=len(targets), records_saved=records_saved, error_message=str(exc))
            raise

    @staticmethod
    def _validate(content: bytes, status: int, object_type: str) -> tuple[str, str]:
        if status != 200:
            return "failed", f"HTTP status {status}"
        if not content:
            return "failed", "empty response"
        stripped = content.strip()[:1]
        if object_type == "json" and stripped not in {b"{", b"["}:
            return "warning", "non-JSON response for json object_type"
        if object_type in {"xml", "sdmx"} and not content.lstrip().startswith(b"<"):
            return "warning", "non-XML response for SDMX/XML object_type"
        return "passed", "IMF response saved"
