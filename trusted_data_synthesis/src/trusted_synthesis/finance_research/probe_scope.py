"""Prospective, source-conditioned Probe scope; never outcome-based filtering.

The original 1000 SFT candidates and every static exclusion remain recorded.
Author references are used only in this offline scope construction, not copied
into the scope's per-task rows or sent as Probe prompts. Static support is not
material qualification, and no surviving task may later be dropped for failure.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from .contracts import PrivateReference, TaskBundle, digest
from .planning import task_key, verify_role_plan
from .qualification import qualification_rules, task_support_check
from .state_mapping import mapper_rules
from .storage import load_public_snapshot

SCHEMA = "finqa_conditional_probe_scope.v1"
SLOT_COUNTS = {"total": 8, "train": 6, "sealed": 2}
EVIDENCE_BOUNDARY = "static_evidence_contains_private_author_derivation_and_is_not_a_Probe_prompt"
AUTHOR_SOURCE_ASSUMPTION = (
    "Author program/gold evidence is trusted private task-semantics evidence, subject to "
    "the frozen qualification rule's unique original-source, period and unit bindings. "
    "This selects a source-verifiable conditional subpopulation before any Probe outcome. "
    "It neither proves universal FinQA support nor qualifies any generated material. "
    "All original 1000 candidates and exclusions remain; the retained scope has no "
    "outcome-based backfill or second deletion/renormalization."
)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_conditional_scope(scope, qualification_rule_id, mapper_rule_id):
    """Validate recorded scope structure/identity only; read no source or outcome."""
    if not isinstance(scope, dict):
        raise ValueError("conditional scope must be a JSON object")
    body = {key: value for key, value in scope.items() if key != "scope_id"}
    if scope.get("scope_id") != "finqa_conditional_scope:" + digest(body):
        raise ValueError("conditional scope content identity mismatch")
    if scope.get("schema") != SCHEMA or scope.get("dataset") != "finqa":
        raise ValueError("unsupported conditional FinQA scope schema")
    if (
        not isinstance(qualification_rule_id, str)
        or not qualification_rule_id
        or not isinstance(mapper_rule_id, str)
        or not mapper_rule_id
        or scope.get("qualification_rule_id") != qualification_rule_id
        or scope.get("mapper_rule_id") != mapper_rule_id
    ):
        raise ValueError("conditional scope uses different frozen qualification/Mapper rules")
    original, selected, rows = (
        scope.get("original_task_ids"),
        scope.get("task_ids"),
        scope.get("coverage_rows"),
    )
    if (
        type(scope.get("original_denominator")) is not int
        or scope["original_denominator"] != 1000
        or not isinstance(original, list)
        or len(original) != 1000
        or any(not isinstance(task, str) or not task.strip() for task in original)
        or len(set(original)) != 1000
    ):
        raise ValueError("all original 1000 unique SFT task IDs must be retained")
    if (
        not isinstance(selected, list)
        or type(scope.get("scoped_task_count")) is not int
        or not 0 < scope["scoped_task_count"] < 1000
        or len(selected) != scope["scoped_task_count"]
        or any(not isinstance(task, str) or not task.strip() for task in selected)
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("conditional scope requires a nonempty strict task subset")
    if not isinstance(rows, list) or len(rows) != 1000:
        raise ValueError("conditional scope must retain all 1000 static coverage rows")
    derived = []
    for task, row in zip(original, rows, strict=True):
        if (
            not isinstance(row, dict)
            or row.get("task_id") != task
            or type(row.get("included")) is not bool
            or row.get("status") not in {"author_anchored_supported", "unknown"}
            or row["included"] != (row["status"] == "author_anchored_supported")
            or not isinstance(row.get("reason"), str)
            or not row["reason"].strip()
            or not _hash(row.get("evidence_sha256"))
        ):
            raise ValueError("coverage row identity/status/inclusion/evidence is inconsistent")
        if row["included"]:
            derived.append(task)
    if selected != derived:
        raise ValueError("selected tasks must be exactly the supported original-order subsequence")
    if (
        scope.get("selection_uses_probe_outcomes") is not False
        or scope.get("static_support_is_material_qualification") is not False
        or scope.get("slot_counts") != SLOT_COUNTS
        or any(type(value) is not int for value in scope["slot_counts"].values())
        or not isinstance(scope.get("author_source_assumption"), str)
        or not scope["author_source_assumption"].strip()
        or not isinstance(scope.get("snapshot_id"), str)
        or not scope["snapshot_id"]
        or not _hash(scope.get("source_manifest_sha256"))
        or not _hash(scope.get("private_sha256"))
    ):
        raise ValueError("scope provenance, non-outcome policy or 8/6/2 slots changed")
    return copy.deepcopy(scope)


def build_conditional_scope(previous_protocol):
    """Apply the frozen static check once to the original 1000 SFT tasks.

    Hash the whole immutable private-reference member, but deserialize only the
    selected SFT rows. No dev/test/feedback/calibration reference object is opened
    for interpretation, and no Probe episodes or scores are accessed.
    """
    if not isinstance(previous_protocol, dict) or previous_protocol.get("id") != digest(
        {key: value for key, value in previous_protocol.items() if key != "id"}
    ):
        raise ValueError("previous registered protocol identity mismatch")
    snapshot = Path(previous_protocol["snapshot"]).resolve()
    manifest, tasks, lineages = load_public_snapshot(snapshot)
    if manifest["id"] != previous_protocol["snapshot_id"]:
        raise ValueError("conditional scope must retain the original H2 snapshot")
    roles = previous_protocol["role_plan"]
    verify_role_plan(roles, tasks, lineages)
    positions = [
        index for index, task in enumerate(tasks) if roles["assignments"][task_key(task)] == "sft"
    ]
    if len(positions) != 1000 or any(
        tasks[index].dataset != "finqa" or lineages[index].original_split != "train"
        for index in positions
    ):
        raise ValueError("exact original 1000 train-split FinQA SFT candidates required")
    manifest_raw = (snapshot / "manifest.json").read_bytes()
    if json.loads(manifest_raw) != manifest:
        raise ValueError("snapshot manifest changed while constructing scope")
    private_raw = (snapshot / "private.references.jsonl").read_bytes()
    private_sha256 = _sha(private_raw)
    if manifest["files"]["private.references.jsonl"] != {
        "sha256": private_sha256,
        "bytes": len(private_raw),
    }:
        raise ValueError("original private-reference member bytes changed")
    lines = [line for line in private_raw.splitlines() if line.strip()]
    if len(lines) != len(tasks):
        raise ValueError("private member row count differs from original public task order")
    rules, mapper = qualification_rules(), mapper_rules()
    original, included, coverage = [], [], []
    for index in positions:
        task = tasks[index]
        reference = PrivateReference.model_validate_json(lines[index])
        bundle = TaskBundle(public=task, reference=reference, lineage=lineages[index])
        evidence = task_support_check(bundle)
        if (
            evidence.get("task_id") != task.task_id
            or evidence.get("qualification_rule_id") != rules["id"]
            or evidence.get("material_admission") is not False
            or evidence.get("no_probe_outcome_examined") is not True
            or evidence.get("status") not in {"author_anchored_supported", "unknown"}
        ):
            raise ValueError(
                "static support checker did not return the frozen non-outcome contract"
            )
        accepted = evidence["status"] == "author_anchored_supported"
        original.append(task.task_id)
        if accepted:
            included.append(task.task_id)
        coverage.append(
            {
                "task_id": task.task_id,
                "included": accepted,
                "status": evidence["status"],
                "reason": evidence.get("reason", "author_anchored_static_source_support"),
                "evidence_sha256": digest(evidence),
                "public_structure_status": evidence.get("public_structure", {}).get("status"),
                EVIDENCE_BOUNDARY: True,
            }
        )
    body = {
        "schema": SCHEMA,
        "dataset": "finqa",
        "previous_protocol_id": previous_protocol["id"],
        "snapshot": str(snapshot),
        "snapshot_id": manifest["id"],
        "role_plan_id": roles["id"],
        "source_manifest_sha256": _sha(manifest_raw),
        "manifest_content_digest": digest(manifest),
        "private_sha256": private_sha256,
        "qualification_rule_id": rules["id"],
        "mapper_rule_id": mapper["id"],
        "original_denominator": 1000,
        "original_task_ids": original,
        "task_ids": included,
        "scoped_task_count": len(included),
        "coverage_rows": coverage,
        "selection_uses_probe_outcomes": False,
        "static_support_is_material_qualification": False,
        "slot_counts": copy.deepcopy(SLOT_COUNTS),
        "author_source_assumption": AUTHOR_SOURCE_ASSUMPTION,
        "private_reference_objects_inspected": len(positions),
        "private_reference_roles_inspected": ["sft"],
        "excluded_tasks_are_not_claimed_inherently_invalid_or_unsolvable": True,
        "no_post_generation_task_deletion_or_backfill": True,
    }
    scope = {**body, "scope_id": "finqa_conditional_scope:" + digest(body)}
    return validate_conditional_scope(scope, rules["id"], mapper["id"])
