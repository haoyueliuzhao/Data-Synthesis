"""One bounded original-PDF geometry pass; never financial admission or parsing.

Preserve both previous financial passes, full-page text, and rejected panels.
Word boxes are original evidence for a separately registered qualification step.
The page set is frozen from ALL existing candidate/table anchors before opening
any PDF; it is not expanded according to yield or the target task quota.
"""

import argparse
import importlib.metadata
import math
import multiprocessing
import os
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import prepare_cross_market_sources_20260926 as base
import register_cross_market_evidence_supplement_20260926 as umbrella

RAW = base.RAW / "original_evidence_revision_02" / "geometry"
REVISION = base.RAW / "period_metadata_revision_01"
AUDIT = base.RAW / "evidence_audit_01"
SCRIPT = "trusted_data_synthesis/scripts/cross_market_geometry_20260926.py"
RADIUS = 4
KIND = "cross_market_original_PDF_geometry"
PROTOCOL = "cross_market_original_geometry_protocol"
COMPLETION = "cross_market_original_geometry_completed"


def ref(path):
    path = Path(path)
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "geometry_output_root")
    base.write(path, value)


def key_for(doc):
    return base.sha(doc["raw_object_id"])[:24]


def checked_ref(reference):
    path = Path(reference["path"])
    base.require(
        path.is_file()
        and path.stat().st_size == reference["bytes"]
        and base.sha(path) == reference["sha256"],
        "geometry_bound_input",
    )
    return base.read(path)


def page_selection(parsed, page_count, empty_text_pages=()):
    """Uniform, finite +/-4 around all cached anchors, including failed ones."""
    base.require(isinstance(page_count, int) and 0 < page_count <= 1200, "geometry_page_cap")
    reasons = defaultdict(set)

    def add(value, reason):
        if value is None:
            return
        base.require(type(value) is int and 1 <= value <= page_count, "geometry_anchor_page")
        reasons[value].add(reason)

    for candidate in parsed.get("candidates", []):
        for name in (
            "page_number",
            "_period_source_page",
            "_unit_source_page",
            "_statement_source_page",
        ):
            add(candidate.get(name), "candidate." + name)
        metadata = candidate.get("extraction_metadata", {})
        for name in ("period_source_page", "unit_source_page", "statement_source_page"):
            add(metadata.get(name), "candidate.extraction_metadata." + name)
    for table in parsed.get("tables", []):
        add(table.get("page_number"), "table.page_number")
    anchors = sorted(reasons)
    empty_text_pages = sorted(set(empty_text_pages))
    base.require(
        all(type(p) is int and 1 <= p <= page_count for p in empty_text_pages),
        "geometry_empty_page_ordinal",
    )
    selected = sorted(
        {
            page
            for anchor in anchors
            for page in range(max(1, anchor - RADIUS), min(page_count, anchor + RADIUS) + 1)
        }
        | set(empty_text_pages)
    )
    return dict(
        anchor_pages=anchors,
        reasons={str(page): sorted(reasons[page]) for page in anchors},
        selected_pages=selected,
        radius=RADIUS,
        page_count=page_count,
        empty_text_pages_to_render=empty_text_pages,
        selection="all_cached_candidate_and_table_anchors_plus_uniform_neighbors",
        candidates_filtered_by_prior_admission=False,
        model_outcomes_consulted=False,
    )


def frozen_inputs():
    revision = base.checked(
        base.read(REVISION / "protocol.json"), "cross_market_period_metadata_revision"
    )
    extraction = base.checked(
        base.read(REVISION / "extraction_summary.json"),
        "cross_market_source_qualification_completed",
    )
    audit = base.checked(base.read(AUDIT / "protocol.json"), "cross_market_evidence_audit_protocol")
    audited = base.checked(
        base.read(AUDIT / "summary.json"), "cross_market_evidence_audit_completed"
    )
    base.require(
        extraction["protocol_id"] == revision["id"]
        and extraction["candidate_count"] == 9513
        and extraction["documents"] == audited["documents"] == 440
        and audited["protocol_id"] == audit["id"]
        and audit["revision_protocol_id"] == revision["id"]
        and audited["status_counts"] == {"TEXT_AUDITED_NOT_ADMITTED": 440},
        "geometry_frozen_completed_inputs",
    )
    documents = []
    for security in revision["metadata_inventory"]["roster"]:
        for doc in security["documents"]:
            key = key_for(doc)
            extraction_ref = ref(REVISION / "documents" / (key + ".json"))
            parsed = base.checked(checked_ref(extraction_ref), "PDF_extraction_result")
            evidence_ref = ref(AUDIT / "documents" / (key + ".json"))
            evidence = base.checked(checked_ref(evidence_ref), "cross_market_PDF_evidence_audit")
            text_ref = evidence["text_bundle"]
            text = base.checked(checked_ref(text_ref), "cross_market_original_PDF_page_text")
            base.require(
                parsed["document"] == evidence["document"] == doc
                and parsed["protocol_id"] == revision["id"]
                and evidence["protocol_id"] == text["protocol_id"] == audit["id"]
                and text["raw_object_id"] == doc["raw_object_id"]
                and text["raw_sha256"] == doc["sha256"]
                and [p["page"] for p in text["pages"]] == list(range(1, evidence["pages"] + 1)),
                "geometry_document_identity",
            )
            documents.append(
                dict(
                    document=doc,
                    extraction=extraction_ref,
                    evidence_audit=evidence_ref,
                    original_page_text=text_ref,
                    page_selection=page_selection(
                        parsed["parsed"],
                        evidence["pages"],
                        [p["page"] for p in text["pages"] if not p["text"].strip()],
                    ),
                )
            )
    base.require(
        len(documents) == 440 and len({key_for(d["document"]) for d in documents}) == 440,
        "geometry_exact_440_documents",
    )
    base.require(
        sum(len(d["page_selection"]["empty_text_pages_to_render"]) for d in documents)
        == audited["empty_text_pages"]
        == 420,
        "geometry_fixed_420_blank_pages",
    )
    base.require(
        sum(d["page_selection"]["page_count"] for d in documents) == audited["pages"] == 104439,
        "geometry_fixed_104439_pages",
    )
    return revision, extraction, audit, audited, documents


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    umbrella_plan = umbrella.protocol(root)
    revision, extraction, audit, audited, documents = frozen_inputs()
    bind_umbrella(umbrella_plan, documents)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in (SCRIPT, base.SCRIPT, umbrella.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "geometry_committed_code",
        )
        sources[name] = base.sha(payload)
    preserved_paths = {
        "source_protocol": base.RAW / "protocol.json",
        "period_revision_protocol": REVISION / "protocol.json",
        "period_revision_completion": REVISION / "extraction_summary.json",
        "evidence_protocol": AUDIT / "protocol.json",
        "evidence_completion": AUDIT / "summary.json",
        "financial_header_revision_completion": base.RAW
        / "financial_header_revision_01/summary.json",
        "failed_panel_completion": base.RAW / "panel_01/summary.json",
    }
    plan = base.record(
        PROTOCOL,
        at=base.now(),
        code_commit=head,
        sources=sources,
        authorization="user approved one new bounded original-evidence revision "
        "after panel_01 failure",
        prior_references={name: ref(path) for name, path in preserved_paths.items()},
        umbrella_protocol_id=umbrella_plan["id"],
        umbrella_protocol=ref(umbrella.RAW / "protocol.json"),
        revision_protocol_id=revision["id"],
        extraction_completion_id=extraction["id"],
        evidence_protocol_id=audit["id"],
        evidence_completion_id=audited["id"],
        documents=documents,
        document_count=440,
        cached_candidates=9513,
        workers=8,
        maximum_attempts_per_PDF=1,
        maximum_original_PDF_opens=440,
        maximum_pages_per_PDF=1200,
        maximum_words_per_page=25000,
        maximum_words_per_PDF=1000000,
        maximum_result_bytes_per_PDF=192 * 2**20,
        maximum_coverage_pages=104439,
        maximum_coverage_words_per_PDF=5000000,
        maximum_image_placements_per_page=1000,
        maximum_image_placements_per_PDF=20000,
        maximum_blank_page_renders=420,
        maximum_renders_per_blank_page=1,
        render_requested_dpi=120,
        render_maximum_edge_pixels=1800,
        maximum_PNG_bytes_per_page=10 * 2**20,
        render_OCR_calls=0,
        selected_pages=sum(len(d["page_selection"]["selected_pages"]) for d in documents),
        package_version=importlib.metadata.version("PyMuPDF"),
        python_version=sys.version,
        prior_financial_parser_attempts_preserved=880,
        prior_fulltext_attempts_preserved=440,
        financial_parser_calls=0,
        new_candidates=0,
        financial_values_changed=False,
        network_requests=0,
        model_calls=0,
        scoring_calls=0,
        new_training_updates=0,
        GPU_processes=0,
        qa_eligible=False,
        evaluation_authorized=False,
        quotas=dict.fromkeys(("dual_sufficient", "composition_required", "other_financial"), 60),
        policies={
            "pages": "Freeze union of +/-4 physical PDF pages around every cached candidate/table "
            "page and candidate unit/period/statement page; no filtering by prior admission. "
            "Include every one of the 420 pre-existing empty-text pages without expanding their "
            "neighbors. No pages are added in response to yield; zero-anchor documents retained.",
            "coverage_inventory": "All 104439 original physical pages in the same open: "
            "get_image_info(hashes=False,xrefs=False), original image placement bbox/size metadata "
            "and current word count. Textchar count comes from bound saved fulltext. Inventory is "
            "not a source-exhaustion certificate: raster and vector semantics remain unreviewed. "
            "No drawing traversal, OCR, model, extra render, or additional source.",
            "blank_page_images": "Render each pre-registered empty-text physical page once in the "
            "same PDF open, PNG RGB, annotations included, requested 120dpi reduced if maxedge "
            "exceeds 1800 pixels; maximum 10MiB/image. No OCR/model. Keep failures unresolved "
            "instead of claiming blank text proves source absence. Save dimensions/dpi/hash/path.",
            "geometry": "PyMuPDF get_text(words,sort=False), original bbox/text/block/line/word "
            "plus a geometric y0/x0 index view. Neither PDF stream nor geometric order is asserted "
            "to be the true semantic reading order. Page ordinal is 1-based physical PDF page.",
            "bounds": "Exceeded page/word/result bounds fail the whole document with a preserved "
            "reason; no truncation or silently partial successful result.",
            "resume": "Reserve exactly one attempt before PDF open. Immutable completed results "
            "are reused; reserved missing results remain unsettled with no refund or retry.",
            "meaning": "Original geometry only. No candidate reparsing, financial gold, corrected "
            "periods, issuer promotion or model execution permission; separately registered "
            "qualification must justify any revised binding and preserve original candidates.",
        },
    )
    save(RAW / "protocol.json", plan)
    base.emit(
        dict(
            event="cross_market_geometry_registered",
            id=plan["id"],
            documents=440,
            selected_pages=plan["selected_pages"],
        )
    )
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), PROTOCOL)
    umbrella_plan = umbrella.protocol(root)
    base.require(
        plan["umbrella_protocol_id"] == umbrella_plan["id"]
        and checked_ref(plan["umbrella_protocol"]) == umbrella_plan,
        "geometry_registered_umbrella",
    )
    bind_umbrella(umbrella_plan, plan["documents"])
    base.require(
        plan["document_count"] == len(plan["documents"]) == 440
        and plan["maximum_original_PDF_opens"] == 440
        and plan["maximum_attempts_per_PDF"] == 1
        and plan["evaluation_authorized"] is False
        and plan["package_version"] == importlib.metadata.version("PyMuPDF")
        and plan["python_version"] == sys.version,
        "geometry_fixed_execution",
    )
    for name, digest in plan["sources"].items():
        base.require(base.sha(root / name) == digest, "geometry_frozen_code:" + name)
    for reference in plan["prior_references"].values():
        checked_ref(reference)
    original = base.read(REVISION / "protocol.json")
    expected = [d for s in original["metadata_inventory"]["roster"] for d in s["documents"]]
    base.require(
        [item["document"] for item in plan["documents"]] == expected, "geometry_original_roster"
    )
    return plan


def bind_umbrella(value, documents):
    expected = [
        {name: item["document"][name] for name in ("raw_object_id", "sha256", "bytes", "path")}
        for item in documents
    ]
    base.require(
        value["fixed_original_documents"] == expected
        and len(expected) == 440
        and value["maximum_additional_PDF_open_attempts"] == 440
        and value["maximum_attempts_per_PDF"] == 1
        and value["maximum_CPU_workers"] == 8
        and value["maximum_pages_per_PDF"] == 1200
        and value["maximum_full_page_image_inventory"] == 104439
        and value["maximum_empty_page_renders"] == 420
        and value["evaluation_authorized"] is False,
        "geometry_same_umbrella_sources_and_budgets",
    )


def reserve(plan, key, doc):
    path = RAW / "attempts" / (key + ".json")
    with base.locked(RAW / "budget.lock", blocking=True):
        if path.exists():
            old = base.read(path)
            base.require(
                old["protocol_id"] == plan["id"] and old["raw_object_id"] == doc["raw_object_id"],
                "geometry_attempt_identity",
            )
            return False
        base.require(
            len(list((RAW / "attempts").glob("*.json"))) < plan["maximum_original_PDF_opens"],
            "geometry_attempt_cap",
        )
        save(
            path,
            dict(
                protocol_id=plan["id"], raw_object_id=doc["raw_object_id"], attempt=1, at=base.now()
            ),
        )
        return True


def geometry_page(page, number, maximum_words, raw_words=None):
    if raw_words is None:
        raw_words = page.get_text("words", sort=False)
    base.require(len(raw_words) <= maximum_words, "geometry_page_word_cap")
    words = []
    for values in raw_words:
        base.require(len(values) == 8, "geometry_word_schema")
        x0, y0, x1, y1, text, block, line, word = values
        base.require(
            all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x0, y0, x1, y1))
            and x0 <= x1
            and y0 <= y1
            and isinstance(text, str)
            and all(type(v) is int and v >= 0 for v in (block, line, word)),
            "geometry_word_values",
        )
        words.append(dict(x0=x0, y0=y0, x1=x1, y1=y1, text=text, block=block, line=line, word=word))
    order = sorted(
        range(len(words)),
        key=lambda i: (words[i]["y0"], words[i]["x0"], words[i]["y1"], words[i]["x1"], i),
    )
    return dict(
        page_number=number,
        width=page.rect.width,
        height=page.rect.height,
        rotation=page.rotation,
        words=words,
        reading_order=order,
        reading_order_is_only_geometric_not_semantic=True,
    )


def save_PNG(path, payload):
    path = Path(path)
    base.require(
        path.resolve().is_relative_to(RAW.resolve()) and ".." not in path.parts,
        "geometry_image_output_root",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        base.require(path.read_bytes() == payload, "geometry_immutable_image_conflict")
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
            base.require(path.read_bytes() == payload, "geometry_concurrent_image_conflict")
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return ref(path)


def render_blank_page(page, number, plan, item):
    import pymupdf

    requested_scale = plan["render_requested_dpi"] / 72
    scale = min(
        requested_scale, plan["render_maximum_edge_pixels"] / max(page.rect.width, page.rect.height)
    )
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False, annots=True)
    base.require(
        max(pixmap.width, pixmap.height) <= plan["render_maximum_edge_pixels"] + 1,
        "geometry_render_edge_cap",
    )
    payload = pixmap.tobytes("png")
    base.require(len(payload) <= plan["maximum_PNG_bytes_per_page"], "geometry_render_byte_cap")
    path = RAW / "images" / key_for(item["document"]) / f"page-{number:04d}.png"
    return dict(
        page_number=number,
        status="ORIGINAL_BLANK_TEXT_PAGE_RENDERED_NOT_REVIEWED",
        image=save_PNG(path, payload),
        format="PNG",
        requested_dpi=plan["render_requested_dpi"],
        effective_dpi=72 * scale,
        pixel_width=pixmap.width,
        pixel_height=pixmap.height,
        page_width=page.rect.width,
        page_height=page.rect.height,
        rotation=page.rotation,
        annotations_included=True,
        OCR_performed=False,
    )


def page_coverage(page, number, raw_words, saved_text, plan):
    images = page.get_image_info(hashes=False, xrefs=False)
    base.require(
        len(images) <= plan["maximum_image_placements_per_page"],
        "geometry_page_image_inventory_cap",
    )
    fields = ("number", "width", "height", "colorspace", "cs-name", "xres", "yres", "bpc", "size")
    placements = []
    for info in images:
        value = {key: info[key] for key in fields if key in info}
        value["bbox"] = list(info["bbox"])
        value["transform"] = list(info["transform"])
        placements.append(value)
    return dict(
        page_number=number,
        width=page.rect.width,
        height=page.rect.height,
        rotation=page.rotation,
        extracted_word_count=len(raw_words),
        saved_text_character_count=len(saved_text),
        saved_text_empty=not saved_text.strip(),
        image_placement_count=len(placements),
        image_placements=placements,
        image_semantics_reviewed=False,
        vector_semantics_reviewed=False,
        text_extraction_is_not_complete_visual_coverage=True,
    )


def extract_geometry(plan, item, opener, renderer=render_blank_page, saved_pages=None):
    """Opener injectable for synthetic tests; production invokes PyMuPDF once."""
    pages, words, images, coverage = [], 0, [], []
    total_words, total_images = 0, 0
    if saved_pages is None:
        text = checked_ref(item["original_page_text"])
        saved_pages = {p["page"]: p["text"] for p in text["pages"]}
    with opener(Path(item["document"]["path"])) as pdf:
        base.require(
            not pdf.needs_pass
            and 0 < len(pdf) <= plan["maximum_pages_per_PDF"]
            and len(pdf) == item["page_selection"]["page_count"],
            "geometry_PDF_page_count_or_encryption",
        )
        for number in range(1, len(pdf) + 1):
            original_page = pdf[number - 1]
            raw_words = original_page.get_text("words", sort=False)
            base.require(len(raw_words) <= plan["maximum_words_per_page"], "geometry_page_word_cap")
            total_words += len(raw_words)
            base.require(
                total_words <= plan["maximum_coverage_words_per_PDF"], "geometry_coverage_word_cap"
            )
            page_inventory = page_coverage(
                original_page, number, raw_words, saved_pages[number], plan
            )
            total_images += page_inventory["image_placement_count"]
            base.require(
                total_images <= plan["maximum_image_placements_per_PDF"],
                "geometry_document_image_inventory_cap",
            )
            coverage.append(page_inventory)
            if number in item["page_selection"]["selected_pages"]:
                page = geometry_page(
                    original_page, number, plan["maximum_words_per_page"], raw_words
                )
                words += len(page["words"])
                base.require(words <= plan["maximum_words_per_PDF"], "geometry_document_word_cap")
                pages.append(page)
            if number in item["page_selection"]["empty_text_pages_to_render"]:
                try:
                    images.append(renderer(original_page, number, plan, item))
                except Exception as error:
                    images.append(
                        dict(
                            page_number=number,
                            status="BLANK_PAGE_RENDER_FAILED_UNRESOLVED",
                            error=repr(error),
                            OCR_performed=False,
                        )
                    )
    result = dict(
        status="GEOMETRY_COLLECTED_NOT_ADMITTED",
        pages=pages,
        selected_page_count=len(pages),
        word_count=words,
        original_page_count=item["page_selection"]["page_count"],
        page_coverage_inventory=coverage,
        coverage_word_count=total_words,
        image_placement_count=total_images,
        blank_page_images=images,
        all_original_blank_pages_rendered=all(
            p["status"] == "ORIGINAL_BLANK_TEXT_PAGE_RENDERED_NOT_REVIEWED" for p in images
        ),
        empty_selected_pages=[p["page_number"] for p in pages if not p["words"]],
    )
    base.require(
        len(base.encode(result)) <= plan["maximum_result_bytes_per_PDF"], "geometry_result_byte_cap"
    )
    return result


def document_job(plan, item):
    doc = item["document"]
    key = key_for(doc)
    destination = RAW / "documents" / (key + ".json")
    with base.locked(RAW / "locks" / (key + ".lock")):
        if destination.exists():
            old = base.checked(base.read(destination), KIND)
            base.require(
                old["protocol_id"] == plan["id"] and all(old[name] == item[name] for name in item),
                "geometry_cached_identity",
            )
            return dict(key=key, status=old["status"])
        if not reserve(plan, key, doc):
            return dict(key=key, status="UNSETTLED_ATTEMPT_NO_AUTOMATIC_RETRY")
        try:
            source = Path(doc["path"])
            base.require(
                source.is_file()
                and not source.is_symlink()
                and source.resolve().is_relative_to(base.LAKE.resolve())
                and source.stat().st_size == doc["bytes"]
                and base.sha(source) == doc["sha256"],
                "geometry_original_PDF_bytes",
            )
            extraction = base.checked(checked_ref(item["extraction"]), "PDF_extraction_result")
            checked_ref(item["evidence_audit"])
            text = base.checked(
                checked_ref(item["original_page_text"]), "cross_market_original_PDF_page_text"
            )
            base.require(
                extraction["document"] == doc
                and text["raw_object_id"] == doc["raw_object_id"]
                and text["raw_sha256"] == doc["sha256"]
                and page_selection(
                    extraction["parsed"],
                    len(text["pages"]),
                    [p["page"] for p in text["pages"] if not p["text"].strip()],
                )
                == item["page_selection"],
                "geometry_unchanged_page_selection",
            )
            import pymupdf

            result = extract_geometry(
                plan, item, pymupdf.open, saved_pages={p["page"]: p["text"] for p in text["pages"]}
            )
        except Exception as error:
            result = dict(status="GEOMETRY_ACQUISITION_FAILED", error=repr(error))
        value = base.record(
            KIND,
            protocol_id=plan["id"],
            at=base.now(),
            attempt=1,
            qa_eligible=False,
            financial_values_changed=False,
            **item,
            **result,
        )
        if len(base.encode(value)) > plan["maximum_result_bytes_per_PDF"]:
            value = base.record(
                KIND,
                protocol_id=plan["id"],
                at=base.now(),
                attempt=1,
                qa_eligible=False,
                financial_values_changed=False,
                **item,
                status="GEOMETRY_ACQUISITION_FAILED",
                error="cross_market.geometry_result_byte_cap_including_metadata",
            )
        save(destination, value)
        return dict(key=key, status=value["status"])


def summarize(plan):
    rows, missing, references = [], [], []
    for item in plan["documents"]:
        path = RAW / "documents" / (key_for(item["document"]) + ".json")
        if not path.exists():
            missing.append(key_for(item["document"]))
            continue
        row = base.checked(base.read(path), KIND)
        base.require(
            row["protocol_id"] == plan["id"] and all(row[name] == item[name] for name in item),
            "geometry_summary_identity",
        )
        rows.append(
            {
                name: row[name]
                for name in (
                    "status",
                    "selected_page_count",
                    "word_count",
                    "empty_selected_pages",
                    "image_placement_count",
                    "blank_page_images",
                )
                if name in row
            }
            | dict(coverage_page_count=len(row.get("page_coverage_inventory", [])))
        )
        references.append(ref(path))
    statuses = dict(Counter(row["status"] for row in rows))
    images = [image for row in rows for image in row.get("blank_page_images", [])]
    rendered = [
        image
        for image in images
        if image["status"] == "ORIGINAL_BLANK_TEXT_PAGE_RENDERED_NOT_REVIEWED"
    ]
    coverage_pages = sum(row["coverage_page_count"] for row in rows)
    complete = (
        not missing
        and statuses == {"GEOMETRY_COLLECTED_NOT_ADMITTED": 440}
        and len(rendered) == plan["maximum_blank_page_renders"]
        and coverage_pages == plan["maximum_coverage_pages"]
    )
    summary = base.record(
        COMPLETION,
        at=base.now(),
        protocol_id=plan["id"],
        status="GEOMETRY_COMPLETE_NOT_ADMITTED"
        if complete
        else "GEOMETRY_INCOMPLETE_NO_AUTOMATIC_RETRY",
        documents=len(rows),
        status_counts=statuses,
        missing_results=missing,
        selected_pages=sum(row.get("selected_page_count", 0) for row in rows),
        selected_words=sum(row.get("word_count", 0) for row in rows),
        empty_selected_pages=sum(len(row.get("empty_selected_pages", [])) for row in rows),
        output_bytes=sum(r["bytes"] for r in references),
        results=references,
        coverage_pages=coverage_pages,
        image_placements=sum(row.get("image_placement_count", 0) for row in rows),
        blank_page_render_records=len(images),
        original_blank_pages_rendered=len(rendered),
        unresolved_blank_page_images=len(images) - len(rendered),
        blank_page_image_bytes=sum(image["image"]["bytes"] for image in rendered),
        blank_page_images_are_not_review_certificates=True,
        reserved_original_PDF_attempts=len(list((RAW / "attempts").glob("*.json"))),
        financial_parser_calls=0,
        new_candidates=0,
        financial_values_changed=False,
        model_calls=0,
        scoring_calls=0,
        new_training_updates=0,
        network_requests=0,
        GPU_processes=0,
        qa_eligible=False,
        panel_ready=False,
        evaluation_started=False,
    )
    save(RAW / "summary.json", summary)
    base.emit({key: value for key, value in summary.items() if key != "results"})
    return summary


def run(root):
    plan = protocol(root)
    with base.locked(RAW / "run.lock"):
        if (RAW / "summary.json").exists():
            return base.checked(base.read(RAW / "summary.json"), COMPLETION)
        with ProcessPoolExecutor(
            max_workers=plan["workers"], mp_context=multiprocessing.get_context("spawn")
        ) as executor:
            futures = [executor.submit(document_job, plan, item) for item in plan["documents"]]
            for number, future in enumerate(as_completed(futures), 1):
                result = future.result()
                if number % 20 == 0 or result["status"] != "GEOMETRY_COLLECTED_NOT_ADMITTED":
                    base.emit(
                        dict(
                            event="cross_market_geometry_progress",
                            completed=number,
                            total=len(futures),
                            **result,
                        )
                    )
        return summarize(plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("register", "run"), required=True)
    args = parser.parse_args()
    (register if args.mode == "register" else run)(args.root.resolve())


if __name__ == "__main__":
    main()
