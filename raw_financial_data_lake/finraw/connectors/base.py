from __future__ import annotations

import hashlib
import json
import urllib.parse
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from finraw.db.client import MetadataDB
from finraw.storage import RawObjectStore, sha256_bytes, today_utc, utc_now


class RawSourceConnector(ABC):
    source_id: str

    def __init__(self, db: MetadataDB, store: RawObjectStore, config: dict[str, Any], dry_run: bool = False):
        self.db = db
        self.store = store
        self.config = config
        self.dry_run = dry_run
        self.snapshot_date = today_utc()

    @abstractmethod
    def run(self) -> None:
        raise NotImplementedError

    def begin_job(self, source_id: str, job_type: str, target_scope: Any, config: Any) -> str:
        job_id = f"job_{source_id}_{utc_now().replace(':', '').replace('-', '')}_{uuid.uuid4().hex[:8]}"
        if self.dry_run:
            return job_id
        self.db.insert_job(
            {
                "job_id": job_id,
                "source_id": source_id,
                "job_type": job_type,
                "target_scope": target_scope,
                "start_time": utc_now(),
                "status": "running",
                "records_found": 0,
                "records_saved": 0,
                "config": config,
            }
        )
        return job_id

    def finish_job(self, job_id: str, status: str, records_found: int, records_saved: int, error_message: str | None = None) -> None:
        if self.dry_run:
            return
        self.db.update_job(
            job_id,
            end_time=utc_now(),
            status=status,
            records_found=records_found,
            records_saved=records_saved,
            error_message=error_message,
        )

    def save_raw_bytes(
        self,
        *,
        source_id: str,
        job_id: str,
        relative_path: str,
        content: bytes,
        object_type: str,
        original_url: str,
        request_params: dict[str, Any] | None,
        response_headers: dict[str, str] | None,
        response_status: int | None,
        compression: str | None = None,
        validation_status: str = "unchecked",
        notes: str | None = None,
        source_publish_date: str | None = None,
        source_update_time: str | None = None,
    ) -> dict[str, Any]:
        request_params = request_params or {}
        effective_original_url = self._canonical_original_url(original_url, request_params)
        content_hash = sha256_bytes(content)
        if not self.dry_run:
            existing = self.db.find_existing_passed_object(source_id, effective_original_url, content_hash)
            if existing:
                raw_object = dict(existing)
                self._supersede_failed_objects(
                    source_id, effective_original_url, raw_object["raw_object_id"]
                )
                raw_object["duplicate_status"] = "duplicate_existing"
                return raw_object
            relative_path = self._collision_safe_relative_path(
                relative_path, content_hash
            )
            path = self.store.write_bytes(relative_path, content)
            storage_uri = str(path)
        else:
            storage_uri = str(Path(self.store.root) / relative_path)

        object_key_hash = hashlib.sha256(
            f"{source_id}|{effective_original_url}|{content_hash}".encode("utf-8")
        ).hexdigest()[:24]
        raw_object = {
            "raw_object_id": f"rawobj_{source_id}_{object_key_hash}",
            "source_id": source_id,
            "job_id": job_id,
            "object_type": object_type,
            "storage_uri": storage_uri,
            "original_url": effective_original_url,
            "request_params": request_params,
            "response_headers": response_headers or {},
            "response_status": response_status,
            "content_sha256": content_hash,
            "content_size_bytes": len(content),
            "compression": compression,
            "retrieval_time": utc_now(),
            "source_publish_date": source_publish_date,
            "source_update_time": source_update_time,
            "parse_status": "unparsed",
            "validation_status": validation_status,
            "notes": notes,
            "duplicate_status": "new",
        }
        if not self.dry_run:
            self.db.insert_raw_object(raw_object)
            if validation_status in {"passed", "warning"}:
                self._supersede_failed_objects(
                    source_id, effective_original_url, raw_object["raw_object_id"]
                )
        return raw_object

    def _collision_safe_relative_path(
        self, relative_path: str, content_hash: str
    ) -> str:
        requested = Path(self.store.root) / relative_path
        existing_hash: str | None = None
        row = self.db.fetchone(
            "SELECT content_sha256 FROM raw_objects WHERE storage_uri = ? "
            "ORDER BY retrieval_time DESC LIMIT 1",
            (str(requested),),
        )
        if row:
            existing_hash = str(row["content_sha256"])
        elif requested.exists():
            existing_hash = sha256_bytes(requested.read_bytes())
        if not existing_hash or existing_hash == content_hash:
            return relative_path
        path = Path(relative_path)
        suffix = "".join(path.suffixes)
        stem = path.name[: -len(suffix)] if suffix else path.name
        versioned_name = f"{stem}__sha256={content_hash[:12]}{suffix}"
        return str(path.with_name(versioned_name))

    def _supersede_failed_objects(
        self, source_id: str, original_url: str, replacement_id: str
    ) -> None:
        self.db.execute(
            "UPDATE raw_objects SET validation_status = ?, "
            "notes = COALESCE(notes, '') || ? "
            "WHERE source_id = ? AND original_url = ? "
            "AND validation_status = ? AND raw_object_id <> ?",
            (
                "superseded",
                f"; superseded by {replacement_id}",
                source_id,
                original_url,
                "failed",
                replacement_id,
            ),
        )

    def create_snapshot(self, *, source_id: str, prefix: str, objects: list[dict[str, Any]]) -> None:
        snapshot_id = f"snapshot_{source_id}_{self.snapshot_date}_{uuid.uuid4().hex[:8]}"
        manifest = {
            "snapshot_id": snapshot_id,
            "source_id": source_id,
            "snapshot_date": self.snapshot_date,
            "object_count": len(objects),
            "total_size_bytes": sum(int(obj["content_size_bytes"]) for obj in objects),
            "objects": objects,
            "created_at": utc_now(),
        }
        if self.dry_run:
            return
        manifest_path = self.store.write_manifest(prefix, manifest)
        checksum_path = self.store.write_checksums(prefix, objects)
        self.db.insert_snapshot(
            {
                "snapshot_id": snapshot_id,
                "source_id": source_id,
                "snapshot_date": self.snapshot_date,
                "storage_prefix": str(Path(self.store.root) / prefix),
                "object_count": manifest["object_count"],
                "total_size_bytes": manifest["total_size_bytes"],
                "manifest_uri": str(manifest_path),
                "checksum_uri": str(checksum_path),
            }
        )

    @staticmethod
    def _canonical_original_url(original_url: str, request_params: dict[str, Any]) -> str:
        if not request_params:
            return original_url
        clean_params = {key: value for key, value in request_params.items() if value is not None}
        if not clean_params:
            return original_url
        query = urllib.parse.urlencode(sorted(clean_params.items()), doseq=True)
        separator = "&" if "?" in original_url else "?"
        return f"{original_url}{separator}{query}"

    @staticmethod
    def json_bytes(payload: Any) -> bytes:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

def stable_raw_record_id(source_id: str, raw_object_id: str, record_type: str, record_key: Any) -> str:
    payload = json.dumps(
        {
            "source_id": source_id,
            "raw_object_id": raw_object_id,
            "record_type": record_type,
            "record_key": record_key,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:24]
    return f"rawrec_{digest}"
