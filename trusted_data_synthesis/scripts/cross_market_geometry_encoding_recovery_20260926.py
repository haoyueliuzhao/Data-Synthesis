"""Losslessly preserve four cached encoding failures; never reopen source PDFs.

The old 421/19 geometry outcome and complete-source gate remain unchanged.
Recovered ASCII-escaped JSON is a new, explicitly encoded evidence payload,
not an original successful geometry record or an evaluation permit.
"""

import argparse
import ast
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import prepare_cross_market_sources_20260926 as base

PARENT = base.RAW / "original_evidence_revision_02" / "geometry"
RAW = base.RAW / "original_evidence_revision_02" / "geometry_encoding_recovery_01"
SCRIPT = "trusted_data_synthesis/scripts/cross_market_geometry_encoding_recovery_20260926.py"
PROTOCOL = "cross_market_geometry_encoding_recovery_protocol"
RESULT = "cross_market_geometry_encoding_recovery_result"
COMPLETION = "cross_market_geometry_encoding_recovery_completed"
FILES = {
    "29b58e8200c548acaeddf027": 2019,
    "73f4f06a1129d829a58a3017": 2020,
    "2d85fd5acf468b4c17d59a92": 2021,
    "d963642a9bb06c92692ce727": 2022,
}
ENCODING = "ASCII_JSON_SORTED_COMPACT_ENSURE_ASCII_TRUE_NO_NAN.v1"
MAX_ERROR_CHARS = 2 * 2**20
MAX_PAYLOAD_BYTES = 8 * 2**20
PAYLOAD_FIELDS = {
    "status",
    "pages",
    "selected_page_count",
    "word_count",
    "original_page_count",
    "page_coverage_inventory",
    "coverage_word_count",
    "image_placement_count",
    "blank_page_images",
    "all_original_blank_pages_rendered",
    "empty_selected_pages",
}


def ref(path):
    path = Path(path)
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)


def read_ref(reference):
    path = Path(reference["path"])
    base.require(
        path.resolve().is_relative_to(PARENT.resolve())
        and not path.is_symlink()
        and path.stat().st_size == reference["bytes"]
        and base.sha(path) == reference["sha256"],
        "encoding_frozen_cache_reference",
    )
    return base.read(path)


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "encoding_output_root")
    base.write(path, value)


def parent_inputs():
    geometry_ref, summary_ref = ref(PARENT / "protocol.json"), ref(PARENT / "summary.json")
    geometry = base.checked(read_ref(geometry_ref), "cross_market_original_geometry_protocol")
    summary = base.checked(read_ref(summary_ref), "cross_market_original_geometry_completed")
    base.require(
        summary["protocol_id"] == geometry["id"]
        and summary["status"] == "GEOMETRY_INCOMPLETE_NO_AUTOMATIC_RETRY"
        and summary["status_counts"]
        == {"GEOMETRY_COLLECTED_NOT_ADMITTED": 421, "GEOMETRY_ACQUISITION_FAILED": 19}
        and summary["reserved_original_PDF_attempts"] == 440,
        "encoding_preserved_failed_parent",
    )
    references = {Path(r["path"]).stem: r for r in summary["results"]}
    items = {
        base.sha(item["document"]["raw_object_id"])[:24]: item for item in geometry["documents"]
    }
    documents = []
    for key, year in sorted(FILES.items()):
        failure_ref = references[key]
        base.require(
            Path(failure_ref["path"]) == PARENT / "documents" / (key + ".json"),
            "encoding_exact_failure_path",
        )
        failure = base.checked(read_ref(failure_ref), "cross_market_original_PDF_geometry")
        base.require(
            failure["protocol_id"] == geometry["id"]
            and failure["status"] == "GEOMETRY_ACQUISITION_FAILED"
            and failure["error"].startswith("UnicodeEncodeError(")
            and failure["document"]["security_id"] == "hkex_disclosures:00857"
            and failure["document"]["year"] == year
            and all(failure[name] == items[key][name] for name in items[key]),
            "encoding_exact_four_failure_identities",
        )
        documents.append(dict(key=key, failure=failure_ref, original_item=items[key]))
    return geometry_ref, summary_ref, geometry, documents


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)[0]
    geometry_ref, summary_ref, geometry, documents = parent_inputs()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(geometry["sources"])
    for name in (SCRIPT, base.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "encoding_committed_code",
        )
        sources[name] = base.sha(payload)
    for name, digest in sources.items():
        base.require(base.sha(root / name) == digest, "encoding_preserved_frozen_code")
    plan = base.record(
        PROTOCOL,
        at=base.now(),
        code_commit=head,
        sources=sources,
        python_version=sys.version,
        parent_protocol=geometry_ref,
        parent_summary=summary_ref,
        parent_protocol_id=geometry["id"],
        documents=documents,
        maximum_cached_attempts=4,
        maximum_attempts_per_cache=1,
        workers=1,
        maximum_error_characters=MAX_ERROR_CHARS,
        maximum_ASCII_payload_bytes=MAX_PAYLOAD_BYTES,
        payload_encoding=ENCODING,
        PDF_opens=0,
        network_requests=0,
        API_calls=0,
        GPU_processes=0,
        model_calls=0,
        scoring_calls=0,
        training_updates=0,
        old_geometry_outcome_unchanged=True,
        geometry_complete=False,
        evaluation_authorized=False,
        downstream_authorized=False,
        policy="Only four frozen UnicodeEncodeError payloads; strict five AST "
        "constants, exact repr and canonical JSON, surrogate only in image cs-name; "
        "ASCII-escaped payload preserves every original code point. No replace, "
        "ignore, normalization, new geometry, PDF access or budget refund. "
        "Missing reserved output stays unsettled without automatic retry.",
    )
    save(RAW / "protocol.json", plan)
    base.emit(dict(event="geometry_encoding_recovery_registered", id=plan["id"], caches=4))
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), PROTOCOL)
    geometry_ref, summary_ref, geometry, documents = parent_inputs()
    base.require(
        plan["documents"] == documents
        and plan["parent_protocol"] == geometry_ref
        and plan["parent_summary"] == summary_ref
        and plan["parent_protocol_id"] == geometry["id"]
        and plan["maximum_cached_attempts"] == 4
        and plan["maximum_attempts_per_cache"] == 1
        and plan["payload_encoding"] == ENCODING
        and plan["python_version"] == sys.version
        and plan["PDF_opens"] == 0
        and plan["downstream_authorized"] is False,
        "encoding_exact_registered_execution",
    )
    for name, digest in plan["sources"].items():
        base.require(base.sha(root / name) == digest, "encoding_frozen_source:" + name)
    return plan, geometry


def decode_error(error):
    base.require(type(error) is str and len(error) <= MAX_ERROR_CHARS, "encoding_error_bound")
    call = ast.parse(error, mode="eval").body
    base.require(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "UnicodeEncodeError"
        and not call.keywords
        and len(call.args) == 5
        and all(isinstance(a, ast.Constant) for a in call.args),
        "encoding_AST_constant_allowlist",
    )
    args = [ast.literal_eval(a) for a in call.args]
    encoding, source, start, end, reason = args
    base.require(
        encoding == "utf-8"
        and type(source) is str
        and type(start) is int
        and type(end) is int
        and 0 <= start < end <= len(source)
        and reason == "surrogates not allowed",
        "encoding_exact_exception_arguments",
    )
    expected = UnicodeEncodeError(*args)
    base.require(repr(expected) == error, "encoding_exact_exception_repr")
    try:
        source.encode("utf-8")
    except UnicodeEncodeError as actual:
        base.require(actual.args == expected.args, "encoding_reproduced_exception")
    else:
        raise ValueError("cross_market.encoding_claimed_failure_did_not_reproduce")
    result = json.loads(source)
    base.require(
        json.dumps(
            result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        == source,
        "encoding_complete_canonical_embedded_JSON",
    )
    return result


def surrogate_inventory(value):
    locations = []

    def visit(node, path=()):
        if isinstance(node, str):
            codes = [ord(c) for c in node if 0xD800 <= ord(c) <= 0xDFFF]
            if codes:
                base.require(
                    len(path) == 5
                    and path[0] == "page_coverage_inventory"
                    and type(path[1]) is int
                    and path[2] == "image_placements"
                    and type(path[3]) is int
                    and path[4] == "cs-name",
                    "encoding_surrogate_outside_image_colorspace",
                )
                locations.append(dict(path=list(path), codepoints=codes))
        elif isinstance(node, list):
            for i, child in enumerate(node):
                visit(child, path + (i,))
        elif isinstance(node, dict):
            for key, child in node.items():
                base.require(
                    not any(0xD800 <= ord(c) <= 0xDFFF for c in key), "encoding_surrogate_in_key"
                )
                visit(child, path + (key,))

    visit(value)
    base.require(bool(locations), "encoding_no_surrogate_found")
    return locations


def finite_coordinates(values, count):
    return (
        isinstance(values, (list, tuple))
        and len(values) == count
        and all(type(v) in (int, float) and math.isfinite(v) for v in values)
    )


def verify_PNG(image, key, page, geometry):
    reference = image["image"]
    path = Path(reference["path"])
    expected = PARENT / "images" / key / f"page-{page:04d}.png"
    base.require(
        path == expected
        and not path.is_symlink()
        and path.resolve().is_relative_to((PARENT / "images" / key).resolve())
        and reference["bytes"] <= geometry["maximum_PNG_bytes_per_page"]
        and path.stat().st_size == reference["bytes"]
        and base.sha(path) == reference["sha256"],
        "encoding_saved_PNG_reference",
    )
    with path.open("rb") as stream:
        header = stream.read(24)
    base.require(
        header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR" and len(header) == 24,
        "encoding_saved_PNG_header",
    )
    width, height = struct.unpack(">II", header[16:24])
    base.require(
        (width, height) == (image["pixel_width"], image["pixel_height"])
        and 0 < max(width, height) <= geometry["render_maximum_edge_pixels"] + 1
        and image["requested_dpi"] == geometry["render_requested_dpi"]
        and 0 < image["effective_dpi"] <= geometry["render_requested_dpi"]
        and image["status"] == "ORIGINAL_BLANK_TEXT_PAGE_RENDERED_NOT_REVIEWED"
        and image["OCR_performed"] is False,
        "encoding_saved_PNG_dimensions",
    )


def validate_payload(result, item, geometry, verify_images=True):
    selection = item["original_item"]["page_selection"]
    base.require(
        set(result) == PAYLOAD_FIELDS
        and result["status"] == "GEOMETRY_COLLECTED_NOT_ADMITTED"
        and result["original_page_count"] == selection["page_count"]
        and 0 < selection["page_count"] <= geometry["maximum_pages_per_PDF"]
        and [p["page_number"] for p in result["pages"]] == selection["selected_pages"]
        and result["selected_page_count"] == len(result["pages"]),
        "encoding_frozen_geometry_pages",
    )
    locations = surrogate_inventory(result)
    words = 0
    for page in result["pages"]:
        base.require(len(page["words"]) <= geometry["maximum_words_per_page"], "encoding_word_cap")
        words += len(page["words"])
        for word in page["words"]:
            base.require(
                finite_coordinates([word[k] for k in ("x0", "y0", "x1", "y1")], 4)
                and word["x0"] <= word["x1"]
                and word["y0"] <= word["y1"]
                and type(word["text"]) is str
                and all(type(word[k]) is int and word[k] >= 0 for k in ("block", "line", "word")),
                "encoding_preserved_word_schema",
            )
        expected_order = sorted(
            range(len(page["words"])),
            key=lambda i: (
                page["words"][i]["y0"],
                page["words"][i]["x0"],
                page["words"][i]["y1"],
                page["words"][i]["x1"],
                i,
            ),
        )
        base.require(page["reading_order"] == expected_order, "encoding_preserved_geometric_order")
    coverage = result["page_coverage_inventory"]
    base.require(
        [p["page_number"] for p in coverage] == list(range(1, selection["page_count"] + 1)),
        "encoding_complete_coverage_pages",
    )
    total_images, total_words = 0, 0
    for page in coverage:
        count = page["extracted_word_count"]
        base.require(
            type(count) is int
            and 0 <= count <= geometry["maximum_words_per_page"]
            and page["image_placement_count"]
            == len(page["image_placements"])
            <= geometry["maximum_image_placements_per_page"]
            and page["image_semantics_reviewed"] is False
            and page["vector_semantics_reviewed"] is False,
            "encoding_coverage_caps_and_unreviewed_status",
        )
        total_images += page["image_placement_count"]
        total_words += count
        for image in page["image_placements"]:
            base.require(
                finite_coordinates(image["bbox"], 4) and finite_coordinates(image["transform"], 6),
                "encoding_image_geometry",
            )
    base.require(
        words == result["word_count"] <= geometry["maximum_words_per_PDF"]
        and total_words
        == result["coverage_word_count"]
        <= geometry["maximum_coverage_words_per_PDF"]
        and total_images
        == result["image_placement_count"]
        <= geometry["maximum_image_placements_per_PDF"]
        and result["empty_selected_pages"]
        == [p["page_number"] for p in result["pages"] if not p["words"]],
        "encoding_original_aggregate_counts",
    )
    images = result["blank_page_images"]
    base.require(
        result["all_original_blank_pages_rendered"] is True
        and [image["page_number"] for image in images] == selection["empty_text_pages_to_render"],
        "encoding_fixed_blank_page_images",
    )
    for image in images:
        if verify_images:
            verify_PNG(image, item["key"], image["page_number"], geometry)
    payload = json.dumps(
        result, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")
    base.require(
        len(payload) <= MAX_PAYLOAD_BYTES and json.loads(payload) == result,
        "encoding_lossless_ASCII_payload",
    )
    return payload, dict(
        geometry_pages=len(result["pages"]),
        coverage_pages=len(coverage),
        words=words,
        saved_images=len(images),
        surrogate_fields=len(locations),
        surrogate_characters=sum(len(p["codepoints"]) for p in locations),
        surrogate_locations=locations,
    )


def write_payload(path, payload):
    base.require(
        path.resolve().is_relative_to(RAW.resolve()) and ".." not in path.parts,
        "encoding_payload_output_root",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        base.require(path.read_bytes() == payload, "encoding_immutable_payload")
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
            base.require(path.read_bytes() == payload, "encoding_concurrent_payload")
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return ref(path)


def reserve(plan, item):
    path = RAW / "attempts" / (item["key"] + ".json")
    with base.locked(RAW / "budget.lock", blocking=True):
        if path.exists():
            old = base.read(path)
            base.require(
                old["protocol_id"] == plan["id"] and old["failure"] == item["failure"],
                "encoding_attempt_identity",
            )
            return False
        base.require(
            len(list((RAW / "attempts").glob("*.json"))) < plan["maximum_cached_attempts"],
            "encoding_cache_attempt_cap",
        )
        save(path, dict(protocol_id=plan["id"], failure=item["failure"], at=base.now(), attempt=1))
        return True


def verify_cached_result(plan, item, value):
    base.require(
        value["protocol_id"] == plan["id"]
        and value["failure"] == item["failure"]
        and value["original_item"] == item["original_item"],
        "encoding_cached_result_identity",
    )
    if value["status"] == "LOSSLESS_CACHED_PAYLOAD_PRESERVED_NOT_ADMITTED":
        reference = value["payload_file"]
        path = Path(reference["path"])
        base.require(
            path == RAW / "payloads" / (item["key"] + ".json")
            and path.is_file()
            and not path.is_symlink()
            and path.resolve().is_relative_to(RAW.resolve())
            and reference["bytes"] <= MAX_PAYLOAD_BYTES
            and path.stat().st_size == reference["bytes"]
            and base.sha(path) == reference["sha256"]
            and value["payload_encoding"] == ENCODING,
            "encoding_cached_payload_integrity",
        )


def recover_one(plan, item, geometry):
    destination = RAW / "documents" / (item["key"] + ".json")
    if destination.exists():
        old = base.checked(base.read(destination), RESULT)
        verify_cached_result(plan, item, old)
        return old
    if not reserve(plan, item):
        return dict(status="UNSETTLED_CACHE_ATTEMPT_NO_AUTOMATIC_RETRY", key=item["key"])
    try:
        failure = base.checked(read_ref(item["failure"]), "cross_market_original_PDF_geometry")
        payload, counts = validate_payload(decode_error(failure["error"]), item, geometry)
        payload_ref = write_payload(RAW / "payloads" / (item["key"] + ".json"), payload)
        fields = dict(
            status="LOSSLESS_CACHED_PAYLOAD_PRESERVED_NOT_ADMITTED",
            payload_file=payload_ref,
            payload_encoding=ENCODING,
            counts=counts,
        )
    except Exception as error:
        fields = dict(status="CACHE_ENCODING_RECOVERY_FAILED", error=ascii(error)[:1024])
    value = base.record(
        RESULT,
        at=base.now(),
        protocol_id=plan["id"],
        failure=item["failure"],
        original_item=item["original_item"],
        attempt=1,
        PDF_opens=0,
        original_failure_unchanged=True,
        geometry_complete=False,
        downstream_authorized=False,
        qa_eligible=False,
        **fields,
    )
    save(destination, value)
    return value


def run(root):
    plan, geometry = protocol(root)
    with base.locked(RAW / "run.lock"):
        if (RAW / "summary.json").exists():
            old = base.checked(base.read(RAW / "summary.json"), COMPLETION)
            base.require(old["protocol_id"] == plan["id"], "encoding_cached_completion_identity")
            items = {item["key"]: item for item in plan["documents"]}
            base.require(len(old["results"]) <= 4, "encoding_cached_completion_bound")
            for reference in old["results"]:
                path = Path(reference["path"])
                base.require(
                    path.stem in items
                    and path == RAW / "documents" / (path.stem + ".json")
                    and ref(path) == reference,
                    "encoding_cached_wrapper_integrity",
                )
                verify_cached_result(plan, items[path.stem], base.checked(base.read(path), RESULT))
            return old
        rows = [recover_one(plan, item, geometry) for item in plan["documents"]]
        statuses = dict(Counter(row["status"] for row in rows))
        complete = statuses == {"LOSSLESS_CACHED_PAYLOAD_PRESERVED_NOT_ADMITTED": 4}
        totals = Counter()
        for row in rows:
            totals.update({k: v for k, v in row.get("counts", {}).items() if type(v) is int})
        # Recheck the unchanged parent files, never touching original PDFs.
        protocol(root)
        value = base.record(
            COMPLETION,
            at=base.now(),
            protocol_id=plan["id"],
            status="FOUR_CACHE_PAYLOADS_PRESERVED_NOT_ADMITTED"
            if complete
            else "CACHE_RECOVERY_INCOMPLETE_NO_AUTOMATIC_RETRY",
            status_counts=statuses,
            counts=dict(totals),
            results=[
                ref(RAW / "documents" / (item["key"] + ".json"))
                for item in plan["documents"]
                if (RAW / "documents" / (item["key"] + ".json")).exists()
            ],
            cached_attempts=len(list((RAW / "attempts").glob("*.json"))),
            PDF_opens=0,
            network_requests=0,
            API_calls=0,
            GPU_processes=0,
            model_calls=0,
            scoring_calls=0,
            training_updates=0,
            original_geometry_status_counts={
                "GEOMETRY_COLLECTED_NOT_ADMITTED": 421,
                "GEOMETRY_ACQUISITION_FAILED": 19,
            },
            geometry_complete=False,
            source_review_complete=False,
            downstream_authorized=False,
            evaluation_started=False,
        )
        save(RAW / "summary.json", value)
        base.emit({key: value for key, value in value.items() if key != "results"})
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("register", "run"), required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    (register if args.mode == "register" else run)(args.root.resolve())


if __name__ == "__main__":
    main()
