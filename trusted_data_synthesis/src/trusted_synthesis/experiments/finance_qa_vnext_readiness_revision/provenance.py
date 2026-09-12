"""Verify historical code honestly while consuming unchanged scientific parents."""

import hashlib
import subprocess
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.catalog import Parent, safe_path
from ..finance_qa_vnext_task_build.archive import record, require, sha, validate_record
from .protocol import (
    CHANGED_PARENT_CODE,
    PARENT,
    PARENT_AUDIT_MANIFEST,
    PARENT_AUDITS,
    PARENT_CODE,
    PARENT_MANIFEST,
)


def check_original_code(root, frozen, *, git_reader=None):
    root = Path(root).resolve()
    require(frozen["git_commit"] == PARENT_CODE, "revision.original_production_commit")
    allowed = set(CHANGED_PARENT_CODE)
    require(
        len({row["path"] for row in frozen["code"]}) == len(frozen["code"]),
        "revision.unique_original_code_pins",
    )
    require(
        allowed <= {row["path"] for row in frozen["code"]},
        "revision.every_changed_consumer_was_originally_pinned",
    )
    changed = []
    for row in frozen["code"]:
        path = safe_path(root, row["path"])
        current = sha(path)
        if current == row["sha256"]:
            continue
        require(row["path"] in allowed, "revision.unregistered_old_dependency_change")
        original = (
            git_reader(PARENT_CODE, row["path"])
            if git_reader is not None
            else subprocess.check_output(["git", "show", PARENT_CODE + ":" + row["path"]], cwd=root)
        )
        require(
            hashlib.sha256(original).hexdigest() == row["sha256"],
            "revision.original_Git_blob_matches_old_freeze",
        )
        changed.append(
            {
                "path": row["path"],
                "old_sha256": row["sha256"],
                "new_sha256": current,
                "old_verified_at_commit": PARENT_CODE,
            }
        )
    return record(
        "readiness_code_compatibility",
        parent_commit=PARENT_CODE,
        original_dependency_count=len(frozen["code"]),
        changed_registered_consumers=changed,
        original_dependency_hash_checks_disabled=False,
    )


def parents(root, *, verify_members=True):
    prepared = Parent(root, PARENT, PARENT_MANIFEST)
    audited = Parent(root, PARENT_AUDITS, PARENT_AUDIT_MANIFEST)
    if verify_members:
        prepared.verify_all()
        audited.verify_all()
    frozen = prepared.read("stage_freeze.json")
    validate_record(frozen, "eval_readiness_freeze")
    gate = audited.read("admission_gate.json")
    validate_record(gate, "fixed_study_admission")
    panel_audit = audited.read("panels.json")
    validate_record(panel_audit, "readiness_independent_audit")
    require(
        gate["preparation_manifest_id"] == prepared.manifest["id"]
        and gate["freeze_id"] == frozen["id"]
        and gate["status"] == "BLOCKED_FOR_FORMAL_COLLECTION"
        and gate["failed_gates"] == ["complete_trajectory_qualification_passed"],
        "revision.exact_preserved_failed_gate",
    )
    require(
        panel_audit["id"] == gate["independent_audit_ids"]["panels"]
        and panel_audit["stage_manifest_id"] == prepared.manifest["id"]
        and panel_audit["status"] == "PASS_AS_SCOPED",
        "revision.inherited_panel_audit_exact_parent",
    )
    report = prepared.read("report.json")
    require(
        report["evaluation_tasks"] == 900
        and report["panel_quota_complete"]
        and report["training_candidates"] == 243
        and report["new_training_candidates"] == 0,
        "revision.exact_prior_panel_and_training_denominators",
    )
    require(
        report["budget"]["request_reservations"] == 0
        and report["budget"]["cumulative_conservative_debit"] == 221538,
        "revision.prior_supplement_zero_is_not_new_allowance",
    )
    return prepared, audited, frozen
