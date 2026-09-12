"""Acquire one targeted earlier issuer report, before any new task output."""

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from lxml import html

from ..finance_qa_vnext_task_build.archive import OUTPUT as PARENT
from ..finance_qa_vnext_task_build.archive import record, require, write_json

OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_surface_build/task_surface_20260912"
WORK = "trusted_data_synthesis/artifacts/qa_vnext_surface_build/runtime_20260912"
ORACLE_2020_URL = (
    "https://www.sec.gov/Archives/edgar/data/1341439/000156459020030125/orcl-10k_20200531.htm"
)
PUBLISHER_PAGE = (
    "https://investor.oracle.com/sec-filings/sec-filings-details/default.aspx?FilingId=14231203"
)
PUBLISHER_HTML = (
    "https://d18rn0p25nwr6d.cloudfront.net/CIK-0001341439/dea701a4-6b8c-44d4-a7a6-efc93169882a.html"
)
SOURCE_PATH = (
    OUTPUT + "/inputs/filings/cik=0001341439/form=10-K/"
    "accession=0001564590-20-030125/orcl-10k_20200531.htm"
)


def acquire(root, *, publisher_mirror=False, inspect_only=False, reuse_download=False):
    root = Path(root).resolve()
    name = "source_acquisition_publisher.json" if publisher_mirror else "source_acquisition.json"
    if inspect_only:
        name = "source_publisher_download.json"
    elif reuse_download:
        name = "source_acquisition_publisher_validated.json"
    destination = root / OUTPUT / "inputs" / name
    require(not destination.exists(), "new source acquisition record only")
    inventory = json.loads((root / PARENT / "native_source_inventory.json").read_bytes())
    entity = next(row["entity"] for row in inventory if row["entity"]["entity_id"] == "ORCL_US")
    requested_at = datetime.now(timezone.utc).isoformat()
    source_url = PUBLISHER_HTML if publisher_mirror else ORACLE_2020_URL
    request = urllib.request.Request(
        source_url,
        headers={
            "User-Agent": "Data-Synthesis academic research https://github.com/haoyueliuzhao/Data-Synthesis",
            "Accept": "text/html",
        },
    )
    try:
        if reuse_download:
            downloaded = json.loads(
                (root / OUTPUT / "inputs/source_publisher_download.json").read_bytes()
            )
            data = (root / SOURCE_PATH).read_bytes()
            require(
                hashlib.sha256(data).hexdigest() == downloaded["sha256"], "pinned downloaded bytes"
            )
            response_url, status = downloaded["url"], downloaded["status_code"]
        else:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read(12_000_001)
                response_url, status = response.geturl(), response.status
        require(status == 200 and response_url == source_url, "exact official source response")
        require(100_000 < len(data) <= 12_000_000, "bounded complete annual report")
        dom = html.fromstring(data)
        if inspect_only:
            path = root / SOURCE_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
            value = record(
                "source_publisher_download",
                url=source_url,
                status_code=status,
                request_count=1,
                requested_at=requested_at,
                sha256=hashlib.sha256(data).hexdigest(),
                bytes=len(data),
                path=SOURCE_PATH,
                validated_source=False,
            )
            write_json(destination, value)
            print(
                json.dumps(
                    {
                        "header_text": " ".join(" ".join(dom.itertext()).split())[:1800],
                        "DEI_fields": [
                            {
                                "name": node.get("name"),
                                "format": node.get("format"),
                                "text": " ".join(" ".join(node.itertext()).split()),
                            }
                            for node in dom.iter()
                            if str(node.get("name") or "").lower()
                            in {
                                "dei:entitycentralindexkey",
                                "dei:documentperiodenddate",
                                "dei:documenttype",
                            }
                        ],
                    }
                )
            )
            return {"status": "downloaded_for_source_validation", "id": value["id"]}
        dei = {}
        for node in dom.iter():
            name = str(node.get("name") or "").lower()
            if name in {
                "dei:entitycentralindexkey",
                "dei:documentperiodenddate",
                "dei:documenttype",
            }:
                value = " ".join(" ".join(node.itertext()).split())
                dei.setdefault(name, set()).add(value)
        require(
            dei.get("dei:documentperiodenddate") == {"2020-05-31"}, "source native report period"
        )
        require(dei.get("dei:documenttype") == {"10-K"}, "source native report type")
        require(
            {str(value).zfill(10) for value in dei.get("dei:entitycentralindexkey", set())}
            == {"0001341439"},
            "source native issuer identity",
        )
        digest = hashlib.sha256(data).hexdigest()
        path = root / SOURCE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        if not reuse_download:
            with path.open("xb") as stream:
                stream.write(data)
        raw_id = "rawobj_surface_" + digest[:24]
        raw = {
            "raw_object_id": raw_id,
            "source_id": "sec_filings",
            "object_type": "html",
            "storage_uri": SOURCE_PATH,
            "original_url": source_url,
            "content_sha256": digest,
            "content_size_bytes": len(data),
            "retrieval_time": requested_at,
            "response_status": status,
            "parse_status": "unparsed",
            "validation_status": "passed",
            "notes": json.dumps(
                {
                    "new_acquisition": True,
                    "native_DEI_checked": True,
                    "original_filing_url": ORACLE_2020_URL,
                    "publisher_download_link_page": PUBLISHER_PAGE if publisher_mirror else None,
                }
            ),
        }
        source = {
            "entity": entity,
            "raw_object": raw,
            "document": {
                "document_id": "acquired_document_" + digest[:24],
                "source_id": "sec_filings",
                "entity_id": entity["entity_id"],
                "raw_object_id": raw_id,
                "form_type": "10-K",
                "period_end": "2020-05-31",
                "filing_date": "2020-06-22",
                "original_url": source_url,
                "document_status": "acquired_pending_source_binding",
                "filing_date_authority": "same-accession native companyfacts occurrence",
            },
        }
        result = record(
            "surface_source_acquisition",
            status="acquired",
            requested_at=requested_at,
            url=source_url,
            sources=[source],
            request_count=0 if reuse_download else 1,
            original_filing_url=ORACLE_2020_URL,
            publisher_download_link_page=PUBLISHER_PAGE if publisher_mirror else None,
            task_outputs_created=False,
            source_rule="one targeted preceding Oracle annual report",
        )
    except (OSError, ValueError, urllib.error.HTTPError) as exc:
        result = record(
            "surface_source_acquisition",
            status="unavailable",
            requested_at=requested_at,
            url=source_url,
            sources=[],
            request_count=1,
            error_type=type(exc).__name__,
            error_code=str(exc) if isinstance(exc, ValueError) else None,
            status_code=getattr(exc, "code", None),
            task_outputs_created=False,
        )
    write_json(destination, result)
    return {"id": result["id"], "status": result["status"], "source_count": len(result["sources"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--publisher-mirror", action="store_true")
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--reuse-download", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            acquire(
                args.root,
                publisher_mirror=args.publisher_mirror,
                inspect_only=args.inspect_only,
                reuse_download=args.reuse_download,
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
