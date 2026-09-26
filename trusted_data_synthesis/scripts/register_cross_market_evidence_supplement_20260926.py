"""User-approved, bounded original-evidence supplement; not a GPU evaluation permit.

Freeze the same source bytes and a single geometry/qualification pass, preserving
every prior failure. No model, network client, PDF parser or GPU is imported here.
"""

import argparse
import subprocess
from pathlib import Path

import prepare_cross_market_sources_20260926 as base

RAW = base.RAW / "original_evidence_revision_02"
SCRIPT = "trusted_data_synthesis/scripts/register_cross_market_evidence_supplement_20260926.py"
CHILD_SCRIPTS = (
    "trusted_data_synthesis/scripts/cross_market_geometry_20260926.py",
    "trusted_data_synthesis/scripts/cross_market_layout_qualification_20260926.py",
    "trusted_data_synthesis/scripts/cross_market_source_review_20260926.py",
)
PARENTS = {
    "source": ("protocol.json", "cross_market_source_qualification_protocol"),
    "candidate_extraction": (
        "period_metadata_revision_01/extraction_summary.json",
        "cross_market_source_qualification_completed",
    ),
    "text_audit": ("evidence_audit_01/summary.json", "cross_market_evidence_audit_completed"),
    "issuer": ("issuer_admission_01/admission.json", "cross_market_issuer_admission"),
    "financial_first": (
        "financial_qualification_01/summary.json",
        "cross_market_financial_qualification_completed",
    ),
    "financial_revision": (
        "financial_header_revision_01/summary.json",
        "cross_market_financial_qualification_completed",
    ),
    "blocked_panel": ("panel_01/summary.json", "cross_market_panel_compilation_completed"),
}


def reference(path, kind):
    value = base.checked(base.read(path), kind)
    return dict(
        path=str(path), sha256=base.sha(path), bytes=path.stat().st_size, kind=kind, id=value["id"]
    ), value


def verify_invariants(values):
    source, candidates, audit, panel = (
        values[k] for k in ("source", "candidate_extraction", "text_audit", "blocked_panel")
    )
    roster = source["metadata_inventory"]["roster"]
    docs = [d for s in roster for d in s["documents"]]
    base.require(len(roster) == 64 and len(docs) == 440, "supplement_same_sources")
    base.require(len({d["raw_object_id"] for d in docs}) == 440, "supplement_unique_originals")
    base.require(
        candidates["candidate_count"] == audit["candidates_reviewed"] == 9513,
        "supplement_original_candidate_universe",
    )
    base.require(
        audit["pages"] == 104439 and audit["empty_text_pages"] == 420,
        "supplement_known_original_page_inventory",
    )
    base.require(
        panel["passed"] is False
        and panel["panel_ready"] is False
        and panel["evaluation_started"] is False
        and panel["evaluation_panel_references"] is None
        and panel["candidate_admission_counts"]
        == dict(dual_sufficient=14, composition_required=0, other_financial=25),
        "supplement_preserved_blocked_panel",
    )
    return roster, docs


def register(root):
    destination = RAW / "protocol.json"
    if destination.exists():
        return protocol(root)
    references, values = {}, {}
    for key, (name, kind) in PARENTS.items():
        references[key], values[key] = reference(base.RAW / name, kind)
    roster, docs = verify_invariants(values)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in (SCRIPT, base.SCRIPT, *CHILD_SCRIPTS):
        payload = (root / name).read_bytes()
        base.require(
            payload == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "supplement_committed_sources",
        )
        sources[name] = base.sha(payload)
    value = base.record(
        "cross_market_original_evidence_supplement_protocol",
        at=base.now(),
        code_commit=head,
        authorization="2026-09-26用户同意另行登记一次有界原文补证修订，保持名单、种子和60x3配额",
        parent_references=references,
        sources=sources,
        fixed_security_ids=[s["security_id"] for s in roster],
        fixed_original_documents=[
            dict(
                raw_object_id=d["raw_object_id"],
                sha256=d["sha256"],
                bytes=d["bytes"],
                path=d["path"],
            )
            for d in docs
        ],
        seeds=[11, 29, 47],
        model_points=9,
        checkpoint_step=240,
        quotas=dict.fromkeys(("dual_sufficient", "composition_required", "other_financial"), 60),
        maximum_additional_PDF_open_attempts=440,
        maximum_attempts_per_PDF=1,
        maximum_CPU_workers=8,
        maximum_pages_per_PDF=1200,
        maximum_full_page_image_inventory=104439,
        maximum_empty_page_renders=420,
        geometry_page_selection="all existing candidate/table/period/unit/statement anchor pages "
        "plus fixed +/-4 physical pages; saved empty-text pages additionally",
        geometry_subprotocol_required_before_PDF_open=True,
        maximum_financial_cached_document_passes=440,
        maximum_anchored_candidates=9513,
        maximum_rederived_source_observations=19026,
        maximum_task_enumerations=1,
        source_review_planner_passes=1,
        current_source_review_API_calls=0,
        actual_student_calls=0,
        actual_model_scoring_cases=0,
        new_training_updates=0,
        GPU_processes=0,
        new_financial_source_requests=0,
        evaluation_authorized=False,
        new_source_roster=False,
        source_observation_policy=(
            "Re-derive at most two explicit annual/instant column observations for each unique "
            "original candidate-anchored semantic row. Original PDF is authority, not a faulty "
            "parser field. Preserve every old candidate; each correction gets new identity, "
            "before/after bindings and source-word geometry. Never choose by amount, closure, "
            "model Q or quota. Unresolved scope/year/currency/column remains rejected."
        ),
        observation_end_years=[2010, 2025],
        unchanged_science="same15 registered concepts, three task families, native currency, "
        "actual-period rules, signed relations, fixed seeds/models/dose and quotas",
        source_exhaustion_policy=(
            "Plan all-source coverage separately. Saved text, regex absence, API JSON or "
            "image inventory alone cannot certify full semantic review. Unreviewed visual/"
            "semantic gaps remain pending. Any later API-assisted review needs its own finite "
            "registered requests/token/coverage plan before dispatch."
        ),
        preserved_attempts=dict(
            financial_parser=880,
            original_text_extraction=440,
            financial_cache_passes=880,
            panel_compilations=1,
        ),
        previous_failures_and_original_bytes_immutable=True,
        no_unbounded_repairs_or_retries_until_quota=True,
        completion_rule="report actual coverage and eligible tasks; insufficient gates keep "
        "evaluation disabled, never patch Q or quotas",
    )
    base.write(destination, value)
    return value


def protocol(root):
    value = base.checked(
        base.read(RAW / "protocol.json"), "cross_market_original_evidence_supplement_protocol"
    )
    for name, digest in value["sources"].items():
        base.require(base.sha(root / name) == digest, "supplement_frozen_source:" + name)
    values = {}
    for key, ref in value["parent_references"].items():
        actual, values[key] = reference(Path(ref["path"]), ref["kind"])
        base.require(actual == ref, "supplement_preserved_parent:" + key)
    verify_invariants(values)
    base.require(
        value["evaluation_authorized"] is False
        and value["maximum_additional_PDF_open_attempts"] == 440
        and value["maximum_rederived_source_observations"] == 19026
        and value["current_source_review_API_calls"] == 0,
        "supplement_only_registered_evidence_scope",
    )
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "status"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    value = (
        register(args.root.resolve())
        if args.action == "register"
        else protocol(args.root.resolve())
    )
    base.emit(
        dict(
            event="bounded_original_evidence_supplement_" + args.action,
            id=value["id"],
            PDF_attempt_cap=value["maximum_additional_PDF_open_attempts"],
            evaluation_authorized=False,
        )
    )


if __name__ == "__main__":
    main()
