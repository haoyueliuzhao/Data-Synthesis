"""Prospectively fixed one-attempt OFFLINE material planner for evidence05.

Reuses the frozen full-composition-source union and all-page coverage machinery.
Only two legacy assumptions are replaced: literal roots and a fixed 9513 input
count. This explicit successor binds the frozen 9513 + 20 reused anchors, not
another scan or an automatic switch from the unregistered evidence04 draft.
No provider transport, semantic approval, PDF access or Student call is added.
"""

import argparse
import subprocess
from collections import Counter
from pathlib import Path

import cross_market_repaired_geometry_execution_20260926 as adapter
import cross_market_source_review_20260926 as core
import run_cross_market_evidence_revision_04_20260926 as financial

# Reuse frozen record-kind constants; actual roots and authority are fixed to 05 below.
base = core.base
RAW = financial.ROOT / "source_review_evidence_revision_05"
FINANCIAL = financial.ROOT / "financial_unit_encoding_revision_05"
FINANCIAL_RUNNER_SCRIPT = (
    "trusted_data_synthesis/scripts/run_cross_market_unit_encoding_revision_05_20260927.py"
)
GEOMETRY = financial.GEOMETRY
PRIOR_REVIEW = adapter.REVIEW
SCRIPT = "trusted_data_synthesis/scripts/cross_market_source_review_revision_05_20260927.py"
PROTOCOL = "cross_market_source_review_protocol"
GROUPS = financial.core.old.GROUPS


def require(condition, reason):
    base.require(condition, "source_review05." + reason)


def ref(path):
    path = Path(path)
    require(path.resolve().is_relative_to(base.RAW.resolve()) and path.is_absolute(), "input_root")
    return dict(path=str(path), sha256=base.sha(path), bytes=path.stat().st_size)


def validate_financial_state(plan, summary, scan, candidates):
    """The explicit unit-only successor reuses exactly the prior 20 anchors."""
    require(
        plan["evidence_revision_number"] == 5
        and plan["document_count"] == 440
        and len(plan["documents"]) == 440
        and plan["fixed_original_candidates"] == 9513
        and plan["fixed_supplementary_anchors"] == 20
        and plan["fixed_total_candidate_anchors"] == 9533
        and plan["maximum_anchor_scan_documents"] == 0
        and plan["maximum_new_review_plans"] == 0
        and plan["quotas"] == dict.fromkeys(GROUPS, 60),
        "fixed_registered_evidence05",
    )
    require(
        scan["protocol_id"] == plan["id"]
        and scan["documents"] == 440
        and scan["status"] == "FROZEN_LITERAL_ANCHORS_REUSED_NO_NEW_SCAN"
        and scan["original_anchors"] == 9513
        and type(scan["added_anchors"]) is int
        and scan["added_anchors"] == 20
        and scan["total_anchors"] == 9533
        and scan["new_original_source_scans"] == 0
        and scan["explicit_cached_view"] is True
        and scan["source_scan_reference"] == plan["parent_references"]["frozen_anchor_scan"],
        "complete_finite_registered_scan",
    )
    require(
        summary["protocol_id"] == plan["id"]
        and summary["documents"] == 440
        and summary["status"] == "FINANCIAL_ENUMERATION_COMPLETE_NOT_EVALUATION_READY"
        and summary["original_input_candidates"] == 9513
        and summary["supplementary_input_candidates"] == 20
        and summary["input_candidates"] == 9533
        and summary["original_candidates_unchanged"] is True,
        "complete_fixed_financial_parent",
    )
    require(candidates["protocol_id"] == plan["id"], "candidate_parent")
    counts = Counter(t["group"] for t in candidates["candidates"])
    require(
        set(counts) == set(GROUPS)
        and dict(counts) == summary["candidate_counts"]
        and all(type(summary["candidate_counts"][g]) is int and counts[g] >= 60 for g in GROUPS),
        "three_raw_group_counts_each_at_least_sixty",
    )
    return dict(counts)


def collect_binding(root):
    references = {
        "financial_protocol": ref(FINANCIAL / "protocol.json"),
        "financial_completion": ref(FINANCIAL / "summary.json"),
        "anchor_scan": ref(FINANCIAL / "scan_summary.json"),
        "financial_candidates": ref(FINANCIAL / "candidate_tasks.json"),
        "prior_material_protocol": ref(PRIOR_REVIEW / "protocol.json"),
        "prior_material_manifest": ref(PRIOR_REVIEW / "packet_manifest.json"),
    }
    kinds = {
        "financial_protocol": financial.PROTOCOL,
        "financial_completion": financial.COMPLETION,
        "anchor_scan": financial.SCAN_DONE,
        "financial_candidates": "cross_market_financial_task_candidates",
        "prior_material_protocol": PROTOCOL,
        "prior_material_manifest": "cross_market_source_review_packet_manifest",
    }
    records = {k: base.checked(base.read(r["path"]), kinds[k]) for k, r in references.items()}
    plan, summary, scan, candidates = (
        records[k]
        for k in (
            "financial_protocol",
            "financial_completion",
            "anchor_scan",
            "financial_candidates",
        )
    )
    counts = validate_financial_state(plan, summary, scan, candidates)
    frozen_scan_reference = plan["parent_references"]["frozen_anchor_scan"]
    require(
        ref(Path(frozen_scan_reference["path"])) == frozen_scan_reference,
        "unchanged_original_twenty_anchor_scan_reference",
    )
    frozen_scan = base.checked(base.read(frozen_scan_reference["path"]), financial.SCAN_DONE)
    require(
        frozen_scan["status"] == "DIRECT_LABEL_ANCHORS_SCANNED_NOT_ADMITTED"
        and frozen_scan["original_anchors"] == 9513
        and frozen_scan["added_anchors"] == 20
        and frozen_scan["total_anchors"] == 9533
        and frozen_scan["documents"] == 440,
        "unchanged_original_twenty_anchor_scan",
    )
    references["reused_evidence04_anchor_scan"] = frozen_scan_reference
    require(
        summary["anchor_scan"] == references["anchor_scan"]
        and summary["candidate_tasks"] == references["financial_candidates"],
        "exact_summary_scan_and_candidates",
    )
    prior, prior_manifest = records["prior_material_protocol"], records["prior_material_manifest"]
    require(
        prior_manifest["protocol_id"] == prior["id"]
        and prior_manifest["status"] == "PACKETS_PREPARED_NOT_SEMANTICALLY_REVIEWED"
        and prior_manifest["API_authorized"] is False
        and prior_manifest["any_source_review_certificate_created"] is False,
        "preserved_prior_materials_not_semantic_credit",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = dict(plan["sources"])
    for name in (SCRIPT, core.SCRIPT, FINANCIAL_RUNNER_SCRIPT, adapter.SCRIPT):
        payload = (root / name).read_bytes()
        require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "committed_planner_code",
        )
        require(
            name not in sources or sources[name] == base.sha(payload), "parent_code_hash_conflict"
        )
        sources[name] = base.sha(payload)
    for name, digest in sources.items():
        require(base.sha(root / name) == digest, "all_frozen_parent_sources")
    binding = dict(
        phase="separate_offline_material_preparation_after_evidence05.v1",
        sources=sources,
        references=references,
        financial_protocol_id=plan["id"],
        scan_id=scan["id"],
        original_input_candidates=9513,
        supplementary_input_candidates=scan["added_anchors"],
        registered_total_input_candidates=scan["total_anchors"],
        candidate_group_counts=counts,
        all_groups_meet_raw_quantity_gate_not_final_admission=True,
        prior_financial_phase_review_plan_budget_zero_preserved=True,
        additional_offline_planner_attempts=1,
        original_PDF_opens=0,
        image_reads=0,
        API_authorized=False,
        approved_API_attempts=0,
        Student_calls=0,
        source_exhaustion_certificates_authorized=False,
        all_composition_sources_included=True,
        geometry_root=str(GEOMETRY),
        financial_root=str(FINANCIAL),
        output_root=str(RAW),
    )
    return binding, records


def bind_protocol(value, binding):
    base.checked(value, PROTOCOL)
    body = {k: v for k, v in value.items() if k not in {"id", "schema_version"}}
    body.update(
        sources=binding["sources"],
        evidence05_offline_preparation=binding,
        maximum_planner_attempts=1,
        standalone_offline_preparation_phase=True,
        financial05_zero_review_budget_not_reused=True,
        approved_API_attempts=0,
        API_authorized=False,
        Student_calls=0,
    )
    value.clear()
    value.update(base.record(PROTOCOL, **body))
    return value


def validate_binding(value, binding):
    base.checked(value, PROTOCOL)
    require(
        value.get("evidence05_offline_preparation") == binding
        and value.get("sources") == binding["sources"]
        and value["maximum_planner_attempts"] == 1
        and value["API_authorized"] is False
        and value["approved_API_attempts"] == value["Student_calls"] == 0,
        "exact_offline_preparation_protocol",
    )
    return value


def namespace(binding, records):
    ns = adapter.isolated_namespace(core, RAW=RAW)
    original_require, original_save = ns["require"], ns["save"]

    def strict_require(condition, reason):
        if reason == "this_bounded_supplement_inputs_only":
            return original_require(ns.get("validated_exact_input_roots") is True, reason)
        if reason == "complete_fixed_financial_parent":
            for key in (
                "financial_protocol",
                "financial_completion",
                "anchor_scan",
                "financial_candidates",
            ):
                reference = binding["references"][key]
                require(ref(Path(reference["path"])) == reference, "frozen_financial_parent_bytes")
            validate_financial_state(
                *(
                    records[k]
                    for k in (
                        "financial_protocol",
                        "financial_completion",
                        "anchor_scan",
                        "financial_candidates",
                    )
                )
            )
            return None
        return original_require(condition, reason)

    def save(path, value):
        if Path(path).resolve() == (RAW / "protocol.json").resolve():
            bind_protocol(value, binding)
        return original_save(path, value)

    ns.update(require=strict_require, save=save)
    return ns


def prepare(root, financial_root=FINANCIAL, geometry_root=GEOMETRY):
    require(
        financial_root.resolve() == FINANCIAL.resolve()
        and geometry_root.resolve() == GEOMETRY.resolve(),
        "only_exact_evidence05_inputs",
    )
    binding, records = collect_binding(root)
    with base.locked(RAW / "prepare.lock"):
        path = RAW / "protocol.json"
        if path.exists():
            validate_binding(base.read(path), binding)
        ns = namespace(binding, records)
        ns["validated_exact_input_roots"] = True
        result = ns["prepare"](root, financial_root, geometry_root)
        plan = validate_binding(base.read(path), binding)
        require(
            result["protocol_id"] == plan["id"]
            and result["API_authorized"] is False
            and result["any_source_review_certificate_created"] is False,
            "new_manifest_is_only_offline_materials",
        )
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare",))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    value = prepare(args.root.resolve())
    base.emit(
        dict(
            event="evidence05_offline_materials_prepared",
            id=value["id"],
            status=value["status"],
            packet_count=value["packet_count"],
        )
    )


if __name__ == "__main__":
    main()
