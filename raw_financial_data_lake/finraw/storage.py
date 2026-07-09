from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class RawObjectStore:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, relative_path: str, content: bytes) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def write_json(self, relative_path: str, payload: Any) -> Path:
        content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str).encode("utf-8")
        return self.write_bytes(relative_path, content)

    def write_manifest(self, prefix: str, manifest: dict[str, Any]) -> Path:
        return self.write_json(f"{prefix.rstrip('/')}/manifest.json", manifest)

    def write_checksums(self, prefix: str, objects: list[dict[str, Any]]) -> Path:
        lines = [
            f"{obj['content_sha256']}  {obj['storage_uri']}"
            for obj in sorted(objects, key=lambda item: item["storage_uri"])
        ]
        content = ("\n".join(lines) + "\n").encode("utf-8")
        return self.write_bytes(f"{prefix.rstrip('/')}/checksums.sha256", content)

