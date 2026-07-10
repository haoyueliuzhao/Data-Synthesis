from __future__ import annotations

from typing import Any

from finraw.connectors.base import RawSourceConnector, stable_raw_record_id
from finraw.http import get_url


class SecCompanyJsonConnector(RawSourceConnector):
    source_id = "sec_sample"

    def run(self) -> None:
        companies = self.config["sec"].get("sample_companies", [])
        user_agent = self.config["sec"]["user_agent"]
        if not companies:
            print("No SEC sample companies configured.")
            return

        source_configs = [
            {
                "source_id": "sec_companyfacts",
                "record_type": "sec_companyfacts_json",
                "url_template": "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json",
                "relative_path": "sec/companyfacts/cik={cik10}/snapshot_date={snapshot_date}.json",
                "required_keys": ["cik", "entityName", "facts"],
            },
            {
                "source_id": "sec_submissions",
                "record_type": "sec_submissions_json",
                "url_template": "https://data.sec.gov/submissions/CIK{cik10}.json",
                "relative_path": "sec/submissions/cik={cik10}/snapshot_date={snapshot_date}.json",
                "required_keys": ["cik", "name", "filings"],
            },
        ]

        for source_config in source_configs:
            self._run_source(companies, source_config, user_agent)

    def _run_source(self, companies: list[dict[str, Any]], source_config: dict[str, Any], user_agent: str) -> None:
        source_id = source_config["source_id"]
        job_id = self.begin_job(
            source_id=source_id,
            job_type="sample_refresh",
            target_scope={"companies": companies},
            config={"dry_run": self.dry_run, "connector": "sec_sample"},
        )
        objects = []
        records_saved = 0

        try:
            for company in companies:
                cik10 = str(company["cik"]).zfill(10)
                url = source_config["url_template"].format(cik10=cik10)
                relative_path = source_config["relative_path"].format(cik10=cik10, snapshot_date=self.snapshot_date)
                if self.dry_run:
                    print(f"[dry-run] SEC sample GET {url} -> {relative_path}")
                    continue

                resp = get_url(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
                validation_status, notes = self._validate_json_response(resp.content, resp.status, source_config["required_keys"])
                obj = self.save_raw_bytes(
                    source_id=source_id,
                    job_id=job_id,
                    relative_path=relative_path,
                    content=resp.content,
                    object_type="json",
                    original_url=url,
                    request_params={"cik": cik10, "ticker": company.get("ticker")},
                    response_headers=resp.headers,
                    response_status=resp.status,
                    validation_status=validation_status,
                    notes=notes,
                )
                objects.append(obj)

                if validation_status == "passed":
                    payload = resp.json()
                    self.db.insert_raw_records([
                        {
                            "raw_record_id": stable_raw_record_id(source_id, obj["raw_object_id"], source_config["record_type"], cik10),
                            "raw_object_id": obj["raw_object_id"],
                            "source_id": source_id,
                            "record_key": cik10,
                            "record_type": source_config["record_type"],
                            "record_json": payload,
                            "entity_hint": company.get("ticker") or cik10,
                            "metric_hint": None,
                            "period_hint": None,
                        }
                    ])
                    records_saved += 1

            self.create_snapshot(
                source_id=source_id,
                prefix=f"sec/{source_id}/snapshot_date={self.snapshot_date}",
                objects=objects,
            )
            self.finish_job(job_id, "success", records_found=len(companies), records_saved=records_saved)
        except Exception as exc:
            self.finish_job(job_id, "failed", records_found=len(companies), records_saved=records_saved, error_message=str(exc))
            raise

    @staticmethod
    def _validate_json_response(content: bytes, status: int, required_keys: list[str]) -> tuple[str, str]:
        if status != 200:
            return "failed", f"HTTP status {status}"
        if not content.strip().startswith(b"{"):
            return "failed", "response is not a JSON object"
        try:
            import json

            payload = json.loads(content.decode("utf-8"))
        except Exception as exc:
            return "failed", f"invalid JSON: {exc}"
        missing = [key for key in required_keys if key not in payload]
        if missing:
            return "failed", f"missing required keys: {missing}"
        return "passed", "required JSON keys found"
