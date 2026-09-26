"""Finite unit-encoding correction; preserve the completed stage04 experiment.

No new source/anchor scan. Reuse the exact twenty saved supplementary anchors
through explicit provenance-bound cache views, then qualify the same 9,533
anchors once. Only the unit representation handler changes.
"""

import argparse
import copy
import subprocess
from pathlib import Path

import cross_market_repaired_geometry_execution_20260926 as adapter
import run_cross_market_evidence_revision_04_20260926 as prior

base = prior.base
RAW = prior.ROOT / "financial_unit_encoding_revision_05"
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_unit_encoding_revision_05_20260927.py"
UNIT_SCRIPT = "trusted_data_synthesis/scripts/cross_market_unit_encoding_revision_20260927.py"


def save(path, value):
    base.require(Path(path).resolve().is_relative_to(RAW.resolve()), "unit05_output_root")
    base.write(path, value)


def register(root):
    if (RAW / "protocol.json").exists():
        return protocol(root)
    parent = prior.protocol(root)
    references = dict(parent["parent_references"])
    references.update(
        unit_parent_protocol=prior.ref(prior.RAW / "protocol.json"),
        unit_parent_completion=prior.ref(prior.RAW / "summary.json"),
        unit_parent_candidates=prior.ref(prior.RAW / "candidate_tasks.json"),
        frozen_anchor_scan=prior.ref(prior.RAW / "scan_summary.json"),
    )
    done = base.checked(prior.read_ref(references["unit_parent_completion"]), prior.COMPLETION)
    scan = base.checked(prior.read_ref(references["frozen_anchor_scan"]), prior.SCAN_DONE)
    base.require(
        done["protocol_id"] == scan["protocol_id"] == parent["id"]
        and done["documents"] == scan["documents"] == 440
        and done["input_candidates"] == scan["total_anchors"] == 9533
        and scan["original_anchors"] == 9513
        and scan["added_anchors"] == 20
        and done["candidate_counts"]
        == dict(dual_sufficient=68, composition_required=323, other_financial=127),
        "unit05_exact_parent_execution",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(parent["sources"])
    for name in (SCRIPT, UNIT_SCRIPT):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "unit05_committed_code",
        )
        sources[name] = base.sha(payload)
    body = {k: copy.deepcopy(v) for k, v in parent.items() if k not in {"id", "schema_version"}}
    body.update(
        at=base.now(),
        code_commit=head,
        sources=sources,
        evidence_revision_number=5,
        parent_protocol_id=parent["id"],
        parent_completion=references["unit_parent_completion"],
        parent_completion_id=done["id"],
        parent_references=references,
        authorization="Continue requested repairs: isolate the unit representation regression "
        "without modifying stage04, source facts, anchor membership or semantic gates.",
        maximum_anchor_scan_documents=0,
        maximum_cached_anchor_view_derivations=440,
        fixed_supplementary_anchors=20,
        fixed_total_candidate_anchors=9533,
        maximum_rederived_observations=19066,
        maximum_new_anchors_this_revision=0,
        maximum_new_anchors=0,
        maximum_new_anchors_per_document=0,
        maximum_total_candidate_anchors=9533,
        maximum_cached_document_passes=440,
        maximum_enumerations=1,
        maximum_API_calls=0,
        maximum_additional_PDF_opens=0,
        anchor_pool_extended_in_this_revision=False,
        unit_only_execution_revision=True,
        unit_encoding_policy="Exact Chinese unit+currency declarations; apostrophe-prefixed "
        "million scale; currency-only in RMB/HK$/US$ is a unit-one fallback only if no "
        "explicit scale exists. Explicit 元 versus million still conflicts. All other "
        "header, Notes, scope, restatement and financial predicates unchanged.",
        inspected_before_registration="Stage04 actual failures and cached unit-header "
        "families. Not value-blind. No requalification tests on original documents.",
    )
    value = base.record(prior.PROTOCOL, **body)
    save(RAW / "protocol.json", value)
    base.emit(dict(event="unit05_registered", id=value["id"]))
    return value


def protocol(root):
    value = base.checked(base.read(RAW / "protocol.json"), prior.PROTOCOL)
    base.require(
        value["evidence_revision_number"] == 5
        and value["fixed_supplementary_anchors"] == 20
        and value["fixed_total_candidate_anchors"] == 9533
        and value["maximum_anchor_scan_documents"] == 0
        and value["maximum_new_anchors"] == value["maximum_new_anchors_per_document"] == 0
        and value["maximum_total_candidate_anchors"] == 9533
        and value["maximum_cached_anchor_view_derivations"] == 440
        and value["maximum_cached_document_passes"] == 440
        and value["maximum_enumerations"] == 1
        and value["maximum_rederived_observations"] == 19066
        and value["maximum_additional_PDF_opens"] == value["maximum_API_calls"] == 0,
        "unit05_finite_scope",
    )
    for path, digest in value["sources"].items():
        base.require(base.sha(root / path) == digest, "unit05_frozen_code")
    for reference in value["parent_references"].values():
        prior.read_ref(reference)
    parent = prior.read_ref(value["parent_references"]["unit_parent_protocol"])
    base.require(
        value["documents"] == parent["documents"] and value["quotas"] == parent["quotas"],
        "unit05_same_inputs_and_quotas",
    )
    return value


def derived_anchor_record(plan, original, source_ref):
    base.checked(original, prior.SCAN)
    base.require(
        original["protocol_id"] == plan["parent_protocol_id"], "unit05_original_scan_parent"
    )
    body = {k: copy.deepcopy(v) for k, v in original.items() if k not in {"id", "schema_version"}}
    body.update(
        protocol_id=plan["id"],
        status="FROZEN_LITERAL_ANCHORS_REUSED_NOT_RESCANNED",
        parent_scan_result=source_ref,
        parent_scan_status=original["status"],
        cache_view_not_rescan=True,
        original_anchor_ids_and_content_unchanged=True,
    )
    result = base.record(prior.SCAN, **body)
    base.require(
        result["new_anchors"] == original["new_anchors"]
        and result["mechanical_reviews"] == original["mechanical_reviews"],
        "unit05_exact_anchor_reuse",
    )
    return result


def reuse_anchors(root):
    plan = protocol(root)
    with base.locked(RAW / "anchor_view.lock"):
        if (RAW / "scan_summary.json").exists():
            value = base.checked(base.read(RAW / "scan_summary.json"), prior.SCAN_DONE)
            base.require(value["protocol_id"] == plan["id"], "unit05_existing_view_parent")
            return value
        frozen_ref = plan["parent_references"]["frozen_anchor_scan"]
        original = base.checked(prior.read_ref(frozen_ref), prior.SCAN_DONE)
        base.require(
            original["protocol_id"] == plan["parent_protocol_id"]
            and original["added_anchors"] == 20
            and original["total_anchors"] == 9533
            and len(original["results"]) == 440,
            "unit05_frozen_twenty_anchors",
        )
        ns = adapter.isolated_namespace(prior, RAW=RAW)
        results, count = [], 0
        for reference in original["results"]:
            key = Path(reference["path"]).stem
            destination = RAW / "anchors" / (key + ".json")
            expected = derived_anchor_record(plan, prior.read_ref(reference), reference)
            if destination.exists():
                value = base.checked(base.read(destination), prior.SCAN)
                base.require(value == expected, "unit05_existing_anchor_view_exact_content")
            else:
                ns["reserve"](plan, "anchor_view_attempts", key)
                value = expected
                save(destination, value)
            count += len(value["new_anchors"])
            results.append(prior.ref(destination))
        base.require(count == 20, "unit05_exact_reused_anchor_count")
        value = base.record(
            prior.SCAN_DONE,
            at=base.now(),
            protocol_id=plan["id"],
            status="FROZEN_LITERAL_ANCHORS_REUSED_NO_NEW_SCAN",
            documents=440,
            original_anchors=9513,
            added_anchors=20,
            total_anchors=9533,
            results=results,
            source_scan_reference=frozen_ref,
            new_original_source_scans=0,
            explicit_cached_view=True,
            original_PDF_opens=0,
            parser_calls=0,
            qa_eligible=False,
        )
        save(RAW / "scan_summary.json", value)
        base.emit({k: v for k, v in value.items() if k != "results"})
        return value


def financial_namespace():
    import cross_market_unit_encoding_revision_20260927 as units

    return units.install_unit_namespace(prior.namespace())


def validate_reused_scan(plan, scanned, original):
    base.checked(scanned, prior.SCAN_DONE)
    base.checked(original, prior.SCAN_DONE)
    base.require(
        scanned["protocol_id"] == plan["id"]
        and original["protocol_id"] == plan["parent_protocol_id"]
        and scanned["documents"] == original["documents"] == 440
        and scanned["original_anchors"] == original["original_anchors"] == 9513
        and scanned["added_anchors"] == original["added_anchors"] == 20
        and scanned["total_anchors"] == original["total_anchors"] == 9533
        and scanned["status"] == "FROZEN_LITERAL_ANCHORS_REUSED_NO_NEW_SCAN"
        and scanned["new_original_source_scans"] == 0
        and scanned["explicit_cached_view"] is True
        and scanned["source_scan_reference"] == plan["parent_references"]["frozen_anchor_scan"],
        "unit05_exact_reused_scan",
    )
    expected_keys = {prior.key_for(item) for item in plan["documents"]}
    base.require(
        len(scanned["results"]) == len(original["results"]) == len(expected_keys) == 440
        and {Path(r["path"]).stem for r in scanned["results"]}
        == {Path(r["path"]).stem for r in original["results"]}
        == expected_keys
        and all(Path(r["path"]).parent == RAW / "anchors" for r in scanned["results"]),
        "unit05_exact_reused_document_membership",
    )


def qualify(root):
    plan = protocol(root)
    validate_reused_scan(
        plan,
        base.read(RAW / "scan_summary.json"),
        prior.read_ref(plan["parent_references"]["frozen_anchor_scan"]),
    )
    ns = adapter.isolated_namespace(prior, RAW=RAW, MAX_OBSERVATIONS=19066)
    ns["protocol"] = protocol
    ns["namespace"] = financial_namespace
    return ns["qualify"](root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "reuse-anchors", "qualify"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    {"register": register, "reuse-anchors": reuse_anchors, "qualify": qualify}[args.action](
        args.root.resolve()
    )


if __name__ == "__main__":
    main()
