"""Assemble a new, provenance-bound 440-document geometry view from saved evidence.

No PDF opens or acquisition retries. Original 421/19 outcome stays immutable.
The existing geometry schema is reused with new IDs and explicit derivation;
image colorspace names use reversible ASCII JSON literals, never replacement.
"""

import argparse
import copy
import json
import subprocess
from collections import Counter
from pathlib import Path

import cross_market_geometry_encoding_recovery_20260926 as encoding
import prepare_cross_market_sources_20260926 as base

ROOT = base.RAW / "original_evidence_revision_02"
RAW = ROOT / "geometry_reconciled_01"
ORIGINAL = ROOT / "geometry"
CAPACITY = ROOT / "geometry_capacity_repair_01"
SCRIPT = "trusted_data_synthesis/scripts/cross_market_geometry_reconciliation_20260926.py"
CAPACITY_SCRIPT = "trusted_data_synthesis/scripts/cross_market_geometry_capacity_repair_20260926.py"
PROTOCOL = "cross_market_original_geometry_protocol"
RESULT = "cross_market_original_PDF_geometry"
COMPLETION = "cross_market_original_geometry_completed"
ROUTES = {"original_success": 421, "encoding_cache_recovery": 4, "capacity_repair": 15}
MAX_RESULT_BYTES = 512 * 2**20


def ref(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=base.sha(path))


def read_ref(reference):
    path = Path(reference["path"])
    base.require(
        path.resolve().is_relative_to(ROOT.resolve())
        and not path.is_symlink()
        and ref(path) == reference,
        "reconciled_frozen_evidence_reference",
    )
    return base.read(path)


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "reconciled_output_root")
    base.write(path, value)


def parents():
    specs = {
        "original_protocol": (ORIGINAL / "protocol.json", PROTOCOL),
        "original_completion": (ORIGINAL / "summary.json", COMPLETION),
        "encoding_protocol": (encoding.RAW / "protocol.json", encoding.PROTOCOL),
        "encoding_completion": (encoding.RAW / "summary.json", encoding.COMPLETION),
        "capacity_protocol": (
            CAPACITY / "protocol.json",
            "cross_market_geometry_capacity_repair_protocol",
        ),
        "capacity_completion": (
            CAPACITY / "summary.json",
            "cross_market_geometry_capacity_repair_completed",
        ),
    }
    references = {k: ref(p) for k, (p, _) in specs.items()}
    values = {k: base.checked(read_ref(references[k]), kind) for k, (_, kind) in specs.items()}
    original, cached, repaired = (
        values[k] for k in ("original_completion", "encoding_completion", "capacity_completion")
    )
    for prefix in ("original", "encoding", "capacity"):
        base.require(
            values[prefix + "_completion"]["protocol_id"] == values[prefix + "_protocol"]["id"],
            "reconciled_parent_identity",
        )
    base.require(
        original["status_counts"]
        == {"GEOMETRY_COLLECTED_NOT_ADMITTED": 421, "GEOMETRY_ACQUISITION_FAILED": 19}
        and original["reserved_original_PDF_attempts"] == 440,
        "reconciled_preserved_original_failure",
    )
    base.require(
        cached["status"] == "FOUR_CACHE_PAYLOADS_PRESERVED_NOT_ADMITTED"
        and cached["cached_attempts"] == 4
        and cached["PDF_opens"] == 0,
        "reconciled_four_cache_recoveries_required",
    )
    base.require(
        repaired["status"] == "GEOMETRY_CAPACITY_REPAIR_COMPLETE_NOT_ADMITTED"
        and len(repaired["results"]) == 15
        and repaired["reserved_original_PDF_attempts"] == 15
        and values["capacity_protocol"]["maximum_original_PDF_opens"] == 15
        and values["capacity_protocol"]["maximum_attempts_per_PDF"] == 1,
        "reconciled_all_fifteen_repairs_required",
    )
    return references, values


def index_results(summary):
    result = {Path(r["path"]).stem: r for r in summary["results"]}
    base.require(len(result) == len(summary["results"]), "reconciled_unique_result_keys")
    return result


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    references, values = parents()
    source_plan = values["original_protocol"]
    prior = index_results(values["original_completion"])
    recovered = index_results(values["encoding_completion"])
    repaired = index_results(values["capacity_completion"])
    base.require(
        len(prior) == 440
        and len(recovered) == 4
        and len(repaired) == 15
        and not set(recovered) & set(repaired),
        "reconciled_exact_partitions",
    )
    documents = []
    for item in source_plan["documents"]:
        key = base.sha(item["document"]["raw_object_id"])[:24]
        route = (
            "encoding_cache_recovery"
            if key in recovered
            else "capacity_repair"
            if key in repaired
            else "original_success"
        )
        selected = (
            recovered[key] if key in recovered else repaired[key] if key in repaired else prior[key]
        )
        documents.append(
            dict(item, evidence_route=route, evidence=selected, original_result=prior[key])
        )
    base.require(
        dict(Counter(d["evidence_route"] for d in documents)) == ROUTES,
        "reconciled_fixed_route_counts",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in ("original_protocol", "encoding_protocol", "capacity_protocol"):
        for path, digest in values[name]["sources"].items():
            base.require(
                path not in sources or sources[path] == digest, "reconciled_source_agreement"
            )
            sources[path] = digest
    for name in (SCRIPT, CAPACITY_SCRIPT, encoding.SCRIPT, base.SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "reconciled_committed_code",
        )
        sources[name] = base.sha(payload)
    for name, digest in sources.items():
        base.require(base.sha(root / name) == digest, "reconciled_unchanged_parent_code")
    plan = base.record(
        PROTOCOL,
        at=base.now(),
        code_commit=head,
        sources=sources,
        derived_geometry_view=True,
        parent_references=references,
        documents=documents,
        document_count=440,
        evidence_route_counts=ROUTES,
        maximum_cached_derivations=440,
        maximum_attempts_per_cache=1,
        maximum_result_bytes=MAX_RESULT_BYTES,
        original_PDF_opens=0,
        original_440_attempts_unchanged=True,
        additional_PDF_attempts_authorized=15,
        planned_selected_pages=7530,
        planned_coverage_pages=104439,
        planned_blank_pages=420,
        roster_replacement=False,
        image_colorspace_representation="cs-name_ascii_json is json.loads reversible; "
        "unmodified original payload remains bound by evidence reference",
        financial_words_unchanged=True,
        financial_values_changed=False,
        model_calls=0,
        scoring_calls=0,
        GPU_processes=0,
        network_requests=0,
        evaluation_authorized=False,
    )
    save(RAW / "protocol.json", plan)
    base.emit(dict(event="geometry_reconciliation_registered", id=plan["id"]))
    return plan


def protocol(root):
    plan = base.checked(base.read(RAW / "protocol.json"), PROTOCOL)
    base.require(
        plan["derived_geometry_view"] is True
        and plan["document_count"] == len(plan["documents"]) == 440
        and plan["evidence_route_counts"] == ROUTES
        and plan["original_PDF_opens"] == 0,
        "reconciled_fixed_plan",
    )
    for name, digest in plan["sources"].items():
        base.require(base.sha(root / name) == digest, "reconciled_frozen_source")
    for reference in plan["parent_references"].values():
        read_ref(reference)
    return plan


def represent_payload(value):
    """Lossless representation change restricted to non-financial image metadata."""
    output = copy.deepcopy(value)
    for page in output["page_coverage_inventory"]:
        for placement in page["image_placements"]:
            base.require("cs-name_ascii_json" not in placement, "reconciled_no_encoding_collision")
            if "cs-name" in placement:
                name = placement.pop("cs-name")
                base.require(isinstance(name, str), "reconciled_colorspace_string")
                placement["cs-name_ascii_json"] = json.dumps(
                    name, ensure_ascii=True, allow_nan=False
                )
                base.require(
                    json.loads(placement["cs-name_ascii_json"]) == name,
                    "reconciled_lossless_colorspace",
                )
    base.require(output["pages"] == value["pages"], "reconciled_original_financial_words")
    # Any surrogate outside those metadata values must still fail, never be ignored.
    base.require(len(base.encode(output)) <= MAX_RESULT_BYTES, "reconciled_output_size")
    return output


def load_payload(item):
    source = read_ref(item["evidence"])
    original = base.checked(read_ref(item["original_result"]), RESULT)
    original_item = {
        k: item[k]
        for k in (
            "document",
            "extraction",
            "evidence_audit",
            "original_page_text",
            "page_selection",
        )
    }
    base.require(
        all(original[k] == v for k, v in original_item.items()), "reconciled_original_item"
    )
    route = item["evidence_route"]
    if route == "original_success":
        base.require(
            item["evidence"] == item["original_result"]
            and original["status"] == "GEOMETRY_COLLECTED_NOT_ADMITTED",
            "reconciled_original_success_only",
        )
        value = {k: source[k] for k in encoding.PAYLOAD_FIELDS}
    else:
        kind = (
            encoding.RESULT
            if route == "encoding_cache_recovery"
            else "cross_market_geometry_capacity_repair_result"
        )
        source = base.checked(source, kind)
        failure_key = "failure" if route == "encoding_cache_recovery" else "parent_failure"
        expected = (
            "LOSSLESS_CACHED_PAYLOAD_PRESERVED_NOT_ADMITTED"
            if route == "encoding_cache_recovery"
            else "CAPACITY_REPAIRED_GEOMETRY_NOT_ADMITTED"
        )
        base.require(
            source["status"] == expected
            and source["original_item"] == original_item
            and source[failure_key] == item["original_result"]
            and original["status"] == "GEOMETRY_ACQUISITION_FAILED",
            "reconciled_recovery_identity",
        )
        value = read_ref(source["payload_file"])
    selection = item["page_selection"]
    base.require(
        set(value) == encoding.PAYLOAD_FIELDS
        and value["status"] == "GEOMETRY_COLLECTED_NOT_ADMITTED"
        and [p["page_number"] for p in value["pages"]] == selection["selected_pages"]
        and value["selected_page_count"] == len(value["pages"])
        and value["original_page_count"] == selection["page_count"]
        and [p["page_number"] for p in value["page_coverage_inventory"]]
        == list(range(1, selection["page_count"] + 1))
        and value["all_original_blank_pages_rendered"] is True
        and [p["page_number"] for p in value["blank_page_images"]]
        == selection["empty_text_pages_to_render"]
        and all(
            p["status"] == "ORIGINAL_BLANK_TEXT_PAGE_RENDERED_NOT_REVIEWED"
            for p in value["blank_page_images"]
        ),
        "reconciled_complete_original_page_scope",
    )
    return represent_payload(value)


def derive(plan, item):
    key = base.sha(item["document"]["raw_object_id"])[:24]
    destination = RAW / "documents" / (key + ".json")
    if destination.exists():
        result = base.checked(base.read(destination), RESULT)
        base.require(
            result["protocol_id"] == plan["id"]
            and result["document"] == item["document"]
            and result["evidence"] == item["evidence"],
            "reconciled_existing_document",
        )
        return result
    attempt = RAW / "attempts" / (key + ".json")
    base.require(not attempt.exists(), "reconciled_unsettled_derivation_no_retry")
    base.require(
        len(list((RAW / "attempts").glob("*.json"))) < plan["maximum_cached_derivations"],
        "reconciled_derivation_budget",
    )
    save(attempt, dict(protocol_id=plan["id"], key=key, at=base.now(), attempt=1))
    payload = load_payload(item)
    result = base.record(
        RESULT,
        protocol_id=plan["id"],
        at=base.now(),
        **item,
        **payload,
        derived_geometry_view=True,
        original_PDF_opens=0,
        original_geometry_failure_unchanged=True,
        financial_words_unchanged=True,
        image_colorspace_representation="ASCII_JSON_LITERAL",
        qa_eligible=False,
        financial_values_changed=False,
    )
    save(destination, result)
    return result


def run(root):
    plan = protocol(root)
    with base.locked(RAW / "run.lock"):
        if (RAW / "summary.json").exists():
            value = base.checked(base.read(RAW / "summary.json"), COMPLETION)
            base.require(value["protocol_id"] == plan["id"], "reconciled_cached_completion")
            return value
        counts = Counter()
        results = []
        for index, item in enumerate(plan["documents"], 1):
            row = derive(plan, item)
            counts.update(
                dict(
                    selected_pages=row["selected_page_count"],
                    coverage_pages=row["original_page_count"],
                    selected_words=row["word_count"],
                    original_blank_pages_rendered=len(row["blank_page_images"]),
                )
            )
            key = base.sha(item["document"]["raw_object_id"])[:24]
            results.append(ref(RAW / "documents" / (key + ".json")))
            if index % 80 == 0:
                base.emit(dict(event="geometry_reconciled", documents=index))
        base.require(
            len(results) == 440
            and counts["selected_pages"] == 7530
            and counts["coverage_pages"] == 104439
            and counts["original_blank_pages_rendered"] == 420,
            "reconciled_complete_440_required",
        )
        value = base.record(
            COMPLETION,
            at=base.now(),
            protocol_id=plan["id"],
            derived_geometry_view=True,
            status="GEOMETRY_COMPLETE_NOT_ADMITTED",
            documents=440,
            **dict(counts),
            status_counts={"GEOMETRY_COLLECTED_NOT_ADMITTED": 440},
            results=results,
            evidence_route_counts=ROUTES,
            original_failure_status_counts={
                "GEOMETRY_COLLECTED_NOT_ADMITTED": 421,
                "GEOMETRY_ACQUISITION_FAILED": 19,
            },
            original_PDF_opens=0,
            original_geometry_failed_completion_unchanged=True,
            qa_eligible=False,
            panel_ready=False,
            evaluation_started=False,
            network_requests=0,
            GPU_processes=0,
            model_calls=0,
            scoring_calls=0,
            new_training_updates=0,
            source_semantic_review_complete=False,
        )
        save(RAW / "summary.json", value)
        base.emit({k: v for k, v in value.items() if k != "results"})
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("register", "run"), required=True)
    args = parser.parse_args()
    (register if args.mode == "register" else run)(args.root.resolve())


if __name__ == "__main__":
    main()
