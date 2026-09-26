"""One authorized, bounded geometry repair for exactly fifteen old cap failures.

Preserve the original 421/19 result and four cache-only encoding recoveries.
No source replacement, financial parsing, financial promotion or model permit.
New ASCII JSON payloads preserve all original code points without normalization.
"""

import argparse
import importlib.metadata
import json
import multiprocessing
import os
import struct
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import cross_market_geometry_20260926 as old

base = old.base
RAW = base.RAW / "original_evidence_revision_02" / "geometry_capacity_repair_01"
PARENT = old.RAW
RECOVERY = base.RAW / "original_evidence_revision_02" / "geometry_encoding_recovery_01"
SCRIPT = "trusted_data_synthesis/scripts/cross_market_geometry_capacity_repair_20260926.py"
PROTOCOL = "cross_market_geometry_capacity_repair_protocol"
RESULT = "cross_market_geometry_capacity_repair_result"
COMPLETION = "cross_market_geometry_capacity_repair_completed"
ENCODING = "ASCII_JSON_SORTED_COMPACT_ENSURE_ASCII_TRUE_NO_NAN.v1"
CAP_ERROR = "ValueError('cross_market.geometry_page_image_inventory_cap')"
KEYS = (
    "0e19057e777a38720bc62a00",
    "35b4801ca6732d2c3943a75b",
    "433f3f2bf98f894537435b40",
    "6e190c692786fe1278523cac",
    "6f96cbe8b339c04ee6d66e16",
    "726828e0e30e83b6b8106061",
    "786077561da526f02e831e17",
    "85bb002fa263baa067af2b45",
    "a89ab37ee2b914b8347e1005",
    "c887953b47d830411792e071",
    "d54e752c5746cc01dc4151fa",
    "d78385669c671bbfd9ec75ee",
    "e063706957f12717cb26e418",
    "e42aff1dcb7b8c16bc7d9e20",
    "edff6017481f455735bb61d4",
)
SUCCESS = "CAPACITY_REPAIRED_GEOMETRY_NOT_ADMITTED"


def ref(path):
    path = Path(path)
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)


def read_ref(reference):
    path = Path(reference["path"])
    base.require(
        path.resolve().is_relative_to(base.RAW.resolve())
        and not path.is_symlink()
        and path.stat().st_size == reference["bytes"]
        and base.sha(path) == reference["sha256"],
        "capacity_bound_cache_reference",
    )
    return base.read(path)


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "capacity_output_root")
    base.write(path, value)


def write_bytes(path, payload):
    path = Path(path)
    base.require(
        path.resolve().is_relative_to(RAW.resolve()) and ".." not in path.parts,
        "capacity_binary_output_root",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        base.require(path.read_bytes() == payload, "capacity_immutable_binary")
        return ref(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".partial.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            base.require(path.read_bytes() == payload, "capacity_concurrent_binary")
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return ref(path)


def png_inventory(path, maximum_bytes):
    path = Path(path)
    base.require(
        path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum_bytes,
        "capacity_PNG_regular_bounded",
    )
    with path.open("rb") as stream:
        header = stream.read(24)
    base.require(
        len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR",
        "capacity_PNG_header",
    )
    width, height = struct.unpack(">II", header[16:24])
    base.require(width > 0 and height > 0, "capacity_PNG_dimensions")
    return dict(image=ref(path), pixel_width=width, pixel_height=height)


def frozen_inputs():
    parent_protocol, parent_summary = ref(PARENT / "protocol.json"), ref(PARENT / "summary.json")
    recovery_summary = ref(RECOVERY / "summary.json")
    geometry = base.checked(read_ref(parent_protocol), old.PROTOCOL)
    summary = base.checked(read_ref(parent_summary), old.COMPLETION)
    recovery = base.checked(
        read_ref(recovery_summary), "cross_market_geometry_encoding_recovery_completed"
    )
    base.require(
        summary["protocol_id"] == geometry["id"]
        and summary["status_counts"]
        == {"GEOMETRY_COLLECTED_NOT_ADMITTED": 421, "GEOMETRY_ACQUISITION_FAILED": 19}
        and summary["reserved_original_PDF_attempts"] == 440
        and recovery["status"] == "FOUR_CACHE_PAYLOADS_PRESERVED_NOT_ADMITTED"
        and recovery["counts"]["coverage_pages"] == 1180
        and recovery["counts"]["saved_images"] == 19,
        "capacity_preserved_original_and_encoding_results",
    )
    references = {Path(r["path"]).stem: r for r in summary["results"]}
    original_items = {old.key_for(i["document"]): i for i in geometry["documents"]}
    documents = []
    for key in KEYS:
        failure_ref = references[key]
        base.require(
            Path(failure_ref["path"]) == PARENT / "documents" / (key + ".json"),
            "capacity_exact_old_failure_path",
        )
        failure = base.checked(read_ref(failure_ref), old.KIND)
        original = original_items[key]
        base.require(
            failure["status"] == "GEOMETRY_ACQUISITION_FAILED"
            and failure["error"] == CAP_ERROR
            and failure["protocol_id"] == geometry["id"]
            and all(failure[name] == original[name] for name in original),
            "capacity_only_fifteen_cap_failures",
        )
        reused, missing = [], []
        for number in original["page_selection"]["empty_text_pages_to_render"]:
            path = PARENT / "images" / key / f"page-{number:04d}.png"
            if path.exists():
                base.require(
                    path.resolve().is_relative_to((PARENT / "images" / key).resolve()),
                    "capacity_original_PNG_path",
                )
                image = png_inventory(path, geometry["maximum_PNG_bytes_per_page"])
                base.require(
                    max(image["pixel_width"], image["pixel_height"])
                    <= geometry["render_maximum_edge_pixels"] + 1,
                    "capacity_original_PNG_edge",
                )
                reused.append(dict(page_number=number, **image))
            else:
                missing.append(number)
        documents.append(
            dict(
                key=key,
                parent_failure=failure_ref,
                original_item=original,
                reused_blank_images=reused,
                missing_blank_pages=missing,
            )
        )
    base.require(
        len(documents) == 15
        and sum(len(i["reused_blank_images"]) for i in documents) == 10
        and sum(len(i["missing_blank_pages"]) for i in documents) == 6
        and sum(i["original_item"]["page_selection"]["page_count"] for i in documents) == 3385
        and sum(len(i["original_item"]["page_selection"]["selected_pages"]) for i in documents)
        == 256,
        "capacity_fixed_scope_totals",
    )
    return geometry, documents, parent_protocol, parent_summary, recovery_summary


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    geometry, documents, parent_protocol, parent_summary, recovery_summary = frozen_inputs()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(geometry["sources"])
    payload = (root / SCRIPT).read_bytes()
    base.require(
        payload == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "capacity_committed_repair",
    )
    sources[SCRIPT] = base.sha(payload)
    for name, digest in sources.items():
        base.require(base.sha(root / name) == digest, "capacity_preserved_code:" + name)
    unchanged = {
        name: geometry[name]
        for name in (
            "maximum_pages_per_PDF",
            "maximum_words_per_page",
            "maximum_words_per_PDF",
            "maximum_coverage_words_per_PDF",
            "maximum_PNG_bytes_per_page",
            "render_requested_dpi",
            "render_maximum_edge_pixels",
        )
    }
    plan = base.record(
        PROTOCOL,
        at=base.now(),
        code_commit=head,
        sources=sources,
        authorization="User approved at most fifteen new original-PDF opens, only the fifteen "
        "remaining image-cap failures, one attempt each; no reopening the other 425 PDFs.",
        parent_protocol=parent_protocol,
        parent_summary=parent_summary,
        parent_protocol_id=geometry["id"],
        encoding_recovery_summary=recovery_summary,
        documents=documents,
        document_count=15,
        maximum_original_PDF_opens=15,
        maximum_attempts_per_PDF=1,
        workers=8,
        maximum_image_placements_per_page=100000,
        maximum_image_placements_per_PDF=1000000,
        maximum_result_bytes_per_PDF=512 * 2**20,
        maximum_new_blank_page_renders=6,
        fixed_reused_blank_images=10,
        maximum_coverage_pages=3385,
        fixed_geometry_pages=256,
        payload_encoding=ENCODING,
        python_version=sys.version,
        package_version=importlib.metadata.version("PyMuPDF"),
        financial_parser_calls=0,
        financial_values_changed=False,
        new_source_documents=0,
        network_requests=0,
        API_calls=0,
        model_calls=0,
        scoring_calls=0,
        training_updates=0,
        GPU_processes=0,
        evaluation_authorized=False,
        source_exhaustion_review_completed=False,
        original_421_19_outcome_unchanged=True,
        policies={
            "scope": "Exactly original source bytes and page selections; no new financial rows.",
            "image_caps": "Fixed 100000/page and 1000000/PDF. Overflow fails, never truncates.",
            "encoding": "ASCII-escaped sorted compact JSON preserves every original code point; "
            "SHA256 binds exact ASCII bytes. No normalization or base.encode(payload).",
            "PNG": "Hash-register ten surviving original PNGs, verify original page/pixel "
            "dimensions while PDF is open. Render only the six registered missing empty pages, "
            "once, at unchanged dpi/size limits. Invalid reused image fails; no substitute render.",
            "recovery": "Reserve before any original PDF read; completed wrappers/payload hashes "
            "are reused, missing reserved results never refund or retry.",
            "meaning": "Geometry acquisition only, not issuer/financial/complete-source admission; "
            "image and vector semantics remain unreviewed. No downstream model permit.",
        },
        **unchanged,
    )
    save(RAW / "protocol.json", plan)
    base.emit(dict(event="geometry_capacity_repair_registered", id=plan["id"], documents=15))
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), PROTOCOL)
    geometry = base.checked(read_ref(plan["parent_protocol"]), old.PROTOCOL)
    summary = base.checked(read_ref(plan["parent_summary"]), old.COMPLETION)
    base.checked(
        read_ref(plan["encoding_recovery_summary"]),
        "cross_market_geometry_encoding_recovery_completed",
    )
    base.require(
        plan["parent_protocol_id"] == geometry["id"]
        and summary["status_counts"]
        == {"GEOMETRY_COLLECTED_NOT_ADMITTED": 421, "GEOMETRY_ACQUISITION_FAILED": 19}
        and [i["key"] for i in plan["documents"]] == list(KEYS)
        and plan["maximum_original_PDF_opens"] == 15
        and plan["maximum_attempts_per_PDF"] == 1
        and plan["maximum_image_placements_per_page"] == 100000
        and plan["maximum_image_placements_per_PDF"] == 1000000
        and plan["maximum_result_bytes_per_PDF"] == 512 * 2**20
        and plan["maximum_new_blank_page_renders"] == 6
        and plan["payload_encoding"] == ENCODING
        and plan["evaluation_authorized"] is False
        and plan["python_version"] == sys.version
        and plan["package_version"] == importlib.metadata.version("PyMuPDF"),
        "capacity_fixed_execution",
    )
    originals = {old.key_for(i["document"]): i for i in geometry["documents"]}
    for item in plan["documents"]:
        base.require(
            item["original_item"] == originals[item["key"]], "capacity_unchanged_original_item"
        )
        failure = base.checked(read_ref(item["parent_failure"]), old.KIND)
        base.require(
            failure["error"] == CAP_ERROR
            and failure["document"] == item["original_item"]["document"],
            "capacity_original_failure_unchanged",
        )
    for name, digest in plan["sources"].items():
        base.require(base.sha(root / name) == digest, "capacity_frozen_code:" + name)
    return plan


def raster_geometry(page, plan):
    import pymupdf

    scale = min(
        plan["render_requested_dpi"] / 72,
        plan["render_maximum_edge_pixels"] / max(page.rect.width, page.rect.height),
    )
    matrix = pymupdf.Matrix(scale, scale)
    bounds = (page.rect * matrix).irect
    return dict(
        matrix=matrix,
        effective_dpi=72 * scale,
        pixel_width=bounds.width,
        pixel_height=bounds.height,
    )


def image_record(page, number, plan, item, existing=None):
    raster = raster_geometry(page, plan)
    if existing is not None:
        expected = PARENT / "images" / item["key"] / f"page-{number:04d}.png"
        base.require(Path(existing["image"]["path"]) == expected, "capacity_reused_PNG_exact_path")
        actual = png_inventory(expected, plan["maximum_PNG_bytes_per_page"])
        base.require(
            actual == {k: existing[k] for k in ("image", "pixel_width", "pixel_height")},
            "capacity_reused_PNG_frozen_bytes",
        )
        mode = "REUSED_REGISTERED_ORIGINAL_ORPHAN_PNG_NO_RERENDER"
    else:
        base.require(number in item["missing_blank_pages"], "capacity_only_fixed_missing_render")
        pixmap = page.get_pixmap(matrix=raster["matrix"], alpha=False, annots=True)
        payload = pixmap.tobytes("png")
        base.require(len(payload) <= plan["maximum_PNG_bytes_per_page"], "capacity_render_byte_cap")
        destination = RAW / "images" / item["key"] / f"page-{number:04d}.png"
        actual = dict(
            image=write_bytes(destination, payload),
            pixel_width=pixmap.width,
            pixel_height=pixmap.height,
        )
        mode = "NEW_RENDER_OF_REGISTERED_MISSING_ORIGINAL_EMPTY_PAGE"
    base.require(
        (actual["pixel_width"], actual["pixel_height"])
        == (raster["pixel_width"], raster["pixel_height"])
        and max(actual["pixel_width"], actual["pixel_height"])
        <= plan["render_maximum_edge_pixels"] + 1,
        "capacity_PNG_matches_original_PDF_dimensions",
    )
    return dict(
        page_number=number,
        status="ORIGINAL_BLANK_TEXT_PAGE_RENDERED_NOT_REVIEWED",
        **actual,
        format="PNG",
        requested_dpi=plan["render_requested_dpi"],
        effective_dpi=raster["effective_dpi"],
        page_width=page.rect.width,
        page_height=page.rect.height,
        rotation=page.rotation,
        annotations_included=True,
        OCR_performed=False,
        acquisition_mode=mode,
        original_PDF_page_dimensions_verified=True,
    )


def collect(plan, item, opener, saved_pages, image_handler=image_record):
    """One open only; no old extract_geometry call or UTF-8 serialization."""
    original = item["original_item"]
    selection = original["page_selection"]
    pages, coverage, images = [], [], []
    words = total_words = total_images = 0
    reused = {row["page_number"]: row for row in item["reused_blank_images"]}
    base.require(
        set(reused).isdisjoint(item["missing_blank_pages"])
        and sorted([*reused, *item["missing_blank_pages"]])
        == selection["empty_text_pages_to_render"],
        "capacity_fixed_image_partition",
    )
    with opener(Path(original["document"]["path"])) as pdf:
        base.require(
            not pdf.needs_pass
            and 0 < len(pdf) <= plan["maximum_pages_per_PDF"]
            and len(pdf) == selection["page_count"],
            "capacity_PDF_pages_or_encryption",
        )
        for number in range(1, len(pdf) + 1):
            page = pdf[number - 1]
            raw_words = page.get_text("words", sort=False)
            base.require(len(raw_words) <= plan["maximum_words_per_page"], "capacity_page_word_cap")
            total_words += len(raw_words)
            base.require(
                total_words <= plan["maximum_coverage_words_per_PDF"], "capacity_coverage_word_cap"
            )
            inventory = old.page_coverage(page, number, raw_words, saved_pages[number], plan)
            total_images += inventory["image_placement_count"]
            base.require(
                total_images <= plan["maximum_image_placements_per_PDF"],
                "capacity_document_image_cap",
            )
            coverage.append(inventory)
            if number in selection["selected_pages"]:
                value = old.geometry_page(page, number, plan["maximum_words_per_page"], raw_words)
                words += len(value["words"])
                base.require(words <= plan["maximum_words_per_PDF"], "capacity_selected_word_cap")
                pages.append(value)
            if number in selection["empty_text_pages_to_render"]:
                images.append(image_handler(page, number, plan, item, reused.get(number)))
    result = dict(
        status="GEOMETRY_COLLECTED_NOT_ADMITTED",
        pages=pages,
        selected_page_count=len(pages),
        word_count=words,
        original_page_count=selection["page_count"],
        page_coverage_inventory=coverage,
        coverage_word_count=total_words,
        image_placement_count=total_images,
        blank_page_images=images,
        all_original_blank_pages_rendered=True,
        empty_selected_pages=[p["page_number"] for p in pages if not p["words"]],
    )
    payload = json.dumps(
        result, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")
    base.require(len(payload) <= plan["maximum_result_bytes_per_PDF"], "capacity_output_byte_cap")
    counts = dict(
        geometry_pages=len(pages),
        coverage_pages=len(coverage),
        words=words,
        saved_images=len(images),
        reused_images=len(reused),
        new_renders=len(item["missing_blank_pages"]),
        image_placements=total_images,
        coverage_words=total_words,
        payload_bytes=len(payload),
    )
    return payload, counts


def reserve(plan, item):
    path = RAW / "attempts" / (item["key"] + ".json")
    with base.locked(RAW / "budget.lock", blocking=True):
        if path.exists():
            attempt = base.read(path)
            base.require(
                attempt["protocol_id"] == plan["id"]
                and attempt["parent_failure"] == item["parent_failure"],
                "capacity_attempt_identity",
            )
            return False
        base.require(
            len(list((RAW / "attempts").glob("*.json"))) < plan["maximum_original_PDF_opens"],
            "capacity_attempt_cap",
        )
        save(
            path,
            dict(
                protocol_id=plan["id"],
                parent_failure=item["parent_failure"],
                raw_object_id=item["original_item"]["document"]["raw_object_id"],
                new_render_pages=item["missing_blank_pages"],
                at=base.now(),
                attempt=1,
            ),
        )
        return True


def cached_result(plan, item, path):
    value = base.checked(base.read(path), RESULT)
    base.require(
        value["protocol_id"] == plan["id"]
        and value["original_item"] == item["original_item"]
        and value["parent_failure"] == item["parent_failure"],
        "capacity_cached_identity",
    )
    if value["status"] == SUCCESS:
        payload = value["payload_file"]
        path = Path(payload["path"])
        base.require(
            path == RAW / "payloads" / (item["key"] + ".json")
            and path.is_file()
            and not path.is_symlink()
            and path.stat().st_size == payload["bytes"]
            and payload["bytes"] <= plan["maximum_result_bytes_per_PDF"]
            and base.sha(path) == payload["sha256"],
            "capacity_cached_payload_integrity",
        )
    return value


def document_job(plan, item):
    destination = RAW / "documents" / (item["key"] + ".json")
    with base.locked(RAW / "locks" / (item["key"] + ".lock")):
        if destination.exists():
            return cached_result(plan, item, destination)
        if not reserve(plan, item):
            return dict(status="UNSETTLED_ATTEMPT_NO_AUTOMATIC_RETRY", key=item["key"])
        original = item["original_item"]
        doc = original["document"]
        source_verified = False
        try:
            source = Path(doc["path"])
            base.require(
                source.is_file()
                and not source.is_symlink()
                and source.resolve().is_relative_to(base.LAKE.resolve())
                and source.stat().st_size == doc["bytes"]
                and base.sha(source) == doc["sha256"],
                "capacity_same_original_PDF_bytes",
            )
            source_verified = True
            text = base.checked(
                read_ref(original["original_page_text"]), "cross_market_original_PDF_page_text"
            )
            base.require(
                text["raw_object_id"] == doc["raw_object_id"]
                and text["raw_sha256"] == doc["sha256"]
                and [p["page"] for p in text["pages"]]
                == list(range(1, original["page_selection"]["page_count"] + 1)),
                "capacity_bound_original_text",
            )
            import pymupdf

            payload, counts = collect(
                plan, item, pymupdf.open, {p["page"]: p["text"] for p in text["pages"]}
            )
            reference = write_bytes(RAW / "payloads" / (item["key"] + ".json"), payload)
            fields = dict(
                status=SUCCESS, payload_file=reference, payload_encoding=ENCODING, counts=counts
            )
        except Exception as error:
            fields = dict(status="GEOMETRY_CAPACITY_REPAIR_FAILED", error=ascii(error)[:1024])
        value = base.record(
            RESULT,
            at=base.now(),
            protocol_id=plan["id"],
            document=doc,
            original_item=original,
            parent_failure=item["parent_failure"],
            registered_image_reuse=item["reused_blank_images"],
            registered_new_render_pages=item["missing_blank_pages"],
            attempt=1,
            source_bytes_modified=False,
            source_identity_verified=source_verified,
            old_failure_unchanged=True,
            qa_eligible=False,
            source_review_complete=False,
            downstream_authorized=False,
            **fields,
        )
        save(destination, value)
        return value


def run(root):
    plan = protocol(root)
    with base.locked(RAW / "run.lock"):
        if (RAW / "summary.json").exists():
            summary = base.checked(base.read(RAW / "summary.json"), COMPLETION)
            base.require(summary["protocol_id"] == plan["id"], "capacity_cached_summary_identity")
            items = {item["key"]: item for item in plan["documents"]}
            base.require(
                len(summary["results"]) == summary["documents"] <= 15,
                "capacity_cached_summary_result_count",
            )
            for reference in summary["results"]:
                path = Path(reference["path"])
                base.require(
                    path.stem in items
                    and path == RAW / "documents" / (path.stem + ".json")
                    and ref(path) == reference,
                    "capacity_cached_wrapper_integrity",
                )
                cached_result(plan, items[path.stem], path)
            return summary
        rows = []
        with ProcessPoolExecutor(
            max_workers=plan["workers"], mp_context=multiprocessing.get_context("spawn")
        ) as executor:
            futures = [executor.submit(document_job, plan, item) for item in plan["documents"]]
            for future in as_completed(futures):
                row = future.result()
                rows.append(row)
                base.emit(
                    dict(
                        event="geometry_capacity_repair_progress",
                        completed=len(rows),
                        total=15,
                        status=row["status"],
                    )
                )
        counts = Counter()
        for row in rows:
            counts.update(row.get("counts", {}))
        statuses = dict(Counter(row["status"] for row in rows))
        complete = (
            statuses == {SUCCESS: 15}
            and counts["geometry_pages"] == 256
            and counts["coverage_pages"] == 3385
            and counts["saved_images"] == 16
            and counts["reused_images"] == 10
            and counts["new_renders"] == 6
        )
        protocol(root)
        result = base.record(
            COMPLETION,
            at=base.now(),
            protocol_id=plan["id"],
            status="GEOMETRY_CAPACITY_REPAIR_COMPLETE_NOT_ADMITTED"
            if complete
            else "GEOMETRY_CAPACITY_REPAIR_INCOMPLETE_NO_AUTOMATIC_RETRY",
            documents=sum(
                (RAW / "documents" / (item["key"] + ".json")).exists() for item in plan["documents"]
            ),
            status_counts=statuses,
            counts=dict(counts),
            results=[
                ref(RAW / "documents" / (item["key"] + ".json"))
                for item in plan["documents"]
                if (RAW / "documents" / (item["key"] + ".json")).exists()
            ],
            reserved_original_PDF_attempts=len(list((RAW / "attempts").glob("*.json"))),
            financial_parser_calls=0,
            network_requests=0,
            API_calls=0,
            GPU_processes=0,
            model_calls=0,
            scoring_calls=0,
            training_updates=0,
            original_421_19_outcome_unchanged=True,
            four_cached_encoding_recoveries_unchanged=True,
            source_review_complete=False,
            downstream_authorized=False,
            evaluation_started=False,
        )
        save(RAW / "summary.json", result)
        base.emit({k: v for k, v in result.items() if k != "results"})
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("register", "run"), required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    (register if args.mode == "register" else run)(args.root.resolve())


if __name__ == "__main__":
    main()
