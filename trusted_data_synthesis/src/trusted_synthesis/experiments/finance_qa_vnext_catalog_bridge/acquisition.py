"""Two prelisted original SEC HTML attempts, before incremental task production."""

import hashlib
import http.client
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from lxml import html

from ..finance_qa_vnext_task_build.archive import record, require, write_json
from .catalog import Parent
from .protocol import EXTRA_REPORTS, OUTPUT, PARENT, PARENT_MANIFEST


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def acquire(root):
    root = Path(root).resolve()
    started = root / OUTPUT / "inputs/acquisition_started.json"
    require(not started.exists(), "acquisition.one_bounded_attempt_set")
    write_json(
        started,
        record("acquisition_start", sources=EXTRA_REPORTS, HTTP_attempt_cap=2, redirects=False),
    )
    parent = Parent(root, PARENT, PARENT_MANIFEST)
    inventory = parent.read("native_source_inventory.json")
    entity = next(row["entity"] for row in inventory if row["entity"]["entity_id"] == "ORCL_US")
    bindings = parent.read("native_bindings.json")
    attempts, sources = [], []
    for spec in EXTRA_REPORTS:
        matching = [
            row
            for row in bindings.values()
            if row["entity_id"] == "ORCL_US"
            and any(
                x["record"].get("accn") == spec["accession"]
                and x["record"].get("filed") == spec["filed"]
                and x["record"].get("form") == "10-K"
                for x in row.get("all_equal_source_occurrences", [])
            )
        ]
        require(bool(matching), "acquisition.prelisted_native_filing_identity")
        entry = {
            **spec,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "HTTP_attempts": 1,
            "admitted": False,
        }
        write_json(
            root / OUTPUT / "inputs" / ("attempt_" + spec["period_end"] + ".json"),
            record("source_HTTP_reservation", **entry),
        )
        try:
            request = urllib.request.Request(
                spec["url"],
                headers={
                    "User-Agent": "Data-Synthesis research https://github.com/haoyueliuzhao/Data-Synthesis",
                    "Accept": "text/html",
                },
            )
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=40) as response:
                entry["status_code"] = response.status
                declared_length = response.headers.get("Content-Length")
                data, status, url = response.read(12_000_001), response.status, response.geturl()
            require(status == 200 and url == spec["url"], "acquisition.exact_registered_SEC_URL")
            digest = hashlib.sha256(data).hexdigest()
            relative = (
                OUTPUT
                + "/inputs/filings/cik=0001341439/form=10-K/accession="
                + spec["accession"]
                + "/report.htm"
            )
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
            entry.update(
                status_code=status,
                raw_sha256=digest,
                path=relative,
                bounded_bytes=len(data),
                complete_download=False,
            )
            require(100_000 < len(data) <= 12_000_000, "acquisition.complete_bounded_HTML")
            require(
                declared_length is None or int(declared_length) == len(data),
                "acquisition.complete_declared_Content_Length",
            )
            entry["complete_download"] = True
            dom = html.fromstring(data)
            cover = re.sub(r"\s+", " ", " ".join(dom.itertext()))[:15000]
            require(
                re.search(r"FORM\s+10.?K", cover, re.I) is not None
                and re.search(r"ORACLE\s+CORPORATION", cover, re.I) is not None,
                "acquisition.original_SEC_cover_entity_and_form",
            )
            year = spec["period_end"][:4]
            require(
                re.search(r"For the fiscal year ended May\s+31,\s*" + year, cover, re.I)
                is not None,
                "acquisition.original_cover_report_period",
            )
            raw_id = "rawobj_bridge_" + digest[:24]
            raw = {
                "raw_object_id": raw_id,
                "source_id": "sec_filings",
                "object_type": "html",
                "storage_uri": relative,
                "original_url": spec["url"],
                "content_sha256": digest,
                "content_size_bytes": len(data),
                "retrieval_time": entry["requested_at"],
                "response_status": 200,
                "parse_status": "unparsed",
                "validation_status": "passed",
            }
            source = {
                "entity": entity,
                "raw_object": raw,
                "document": {
                    "document_id": "bridge_document_" + digest[:24],
                    "source_id": "sec_filings",
                    "entity_id": entity["entity_id"],
                    "raw_object_id": raw_id,
                    "form_type": "10-K",
                    "period_end": spec["period_end"],
                    "filing_date": spec["filed"],
                    "original_url": spec["url"],
                    "document_status": "acquired",
                },
            }
            sources.append(source)
            entry.update(admitted=True)
        except (OSError, ValueError, http.client.HTTPException) as error:
            entry.update(
                error_type=type(error).__name__,
                status_code=getattr(error, "code", entry.get("status_code")),
                reason=str(error) if isinstance(error, ValueError) else None,
            )
        attempts.append(entry)
    result = record(
        "bounded_source_acquisition",
        attempts=attempts,
        sources=sources,
        request_count=len(attempts),
        extra_hosts_or_retries=0,
        previously_rejected_publisher_bytes_used=False,
    )
    write_json(root / OUTPUT / "inputs/source_acquisition.json", result)
    return result
