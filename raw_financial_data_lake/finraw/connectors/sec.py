from __future__ import annotations

import zipfile
from io import BytesIO

from finraw.connectors.base import RawSourceConnector
from finraw.http import get_url


class SecBulkConnector(RawSourceConnector):
    source_id = "sec_bulk"

    def run(self) -> None:
        datasets = self.config["sec"]["bulk_datasets"]
        user_agent = self.config["sec"]["user_agent"]
        objects = []

        job_id = self.begin_job(
            source_id="sec_companyfacts",
            job_type="full_refresh",
            target_scope={"datasets": [item["name"] for item in datasets]},
            config={"dry_run": self.dry_run},
        )

        try:
            for dataset in datasets:
                relative_path = dataset["relative_path"].format(snapshot_date=self.snapshot_date)
                if self.dry_run:
                    print(f"[dry-run] SEC download {dataset['url']} -> {relative_path}")
                    continue

                resp = get_url(dataset["url"], headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
                validation_status, notes = self._validate_zip(resp.content, resp.status)
                obj = self.save_raw_bytes(
                    source_id=dataset["source_id"],
                    job_id=job_id,
                    relative_path=relative_path,
                    content=resp.content,
                    object_type=dataset["object_type"],
                    original_url=dataset["url"],
                    request_params={},
                    response_headers=resp.headers,
                    response_status=resp.status,
                    compression="zip",
                    validation_status=validation_status,
                    notes=notes,
                )
                objects.append(obj)

            for dataset in datasets:
                source_objects = [obj for obj in objects if obj["source_id"] == dataset["source_id"]]
                prefix = f"sec/{dataset['name']}/snapshot_date={self.snapshot_date}"
                self.create_snapshot(source_id=dataset["source_id"], prefix=prefix, objects=source_objects)

            self.finish_job(job_id, "success", records_found=len(datasets), records_saved=len(objects))
        except Exception as exc:
            self.finish_job(job_id, "failed", records_found=len(datasets), records_saved=len(objects), error_message=str(exc))
            raise

    @staticmethod
    def _validate_zip(content: bytes, status: int) -> tuple[str, str]:
        if status != 200:
            return "failed", f"HTTP status {status}"
        if not content:
            return "failed", "empty content"
        try:
            with zipfile.ZipFile(BytesIO(content)) as zf:
                if not zf.namelist():
                    return "failed", "zip has no entries"
        except zipfile.BadZipFile:
            return "failed", "not a valid zip"
        return "passed", "zip opened successfully"

