"""Direct admission controls, not extra financial Runtime trajectories."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes

from .models import CONTEXT_FIELDS, ShareError, admit_inputs, record
from .validation import validate_records


def _replace_ids(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {k: _replace_ids(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_ids(v, mapping) for v in value]
    if isinstance(value, str):
        return mapping.get(value, value)
    return value


def rehash_records(records: dict[str, Any]) -> dict[str, Any]:
    """Recompute all prospective IDs/parents and preaction receipt byte bindings."""
    out = copy.deepcopy(records)
    mapping: dict[str, str] = {}

    def renew(obj: dict[str, Any]) -> dict[str, Any]:
        old = obj["id"]
        kind = obj["schema_version"].removeprefix("part_whole_share_").removesuffix(".v1")
        body = _replace_ids(
            {k: v for k, v in obj.items() if k not in ("id", "schema_version")}, mapping
        )
        new = record(kind, **body)
        mapping[old] = new["id"]
        return new

    out["candidate"] = renew(out["candidate"])
    out["initial_state"] = renew(out["initial_state"])
    for step in out["steps"]:
        step["proposal"] = renew(step["proposal"])
        payload = canonical_json_bytes(step["proposal"])
        step["receipt"]["proposal_sha256"] = hashlib.sha256(payload).hexdigest()
        step["receipt"]["proposal_byte_count"] = len(payload)
        for kind in ("receipt", "execution", "observation", "claim", "update", "state"):
            step[kind] = renew(step[kind])
    out["final"] = renew(out["final"])
    return out


def forged_disclosed_denominator(source: dict[str, Any], records: dict[str, Any]) -> dict[str, Any]:
    """Retain the sum but actually bypass it; answer remains unchanged, lineage does not."""
    forged = copy.deepcopy(records)
    total = source["evidence"]["total"]
    freight = source["evidence"]["freight"]
    lineage = sorted([total["id"], freight["id"]])
    ratio = next(n for n in forged["candidate"]["nodes"] if n["operation"] == "share_ratio")
    ratio["inputs"][1] = {"role": "denominator", "kind": "evidence", "ref": total["id"]}
    for step in forged["steps"]:
        op = step["execution"]["operation"]
        if op == "relation_sum":
            continue
        if op == "share_ratio":
            step["proposal"]["inputs"][1] = {
                "role": "denominator",
                "kind": "evidence",
                "ref_id": total["id"],
            }
            step["execution"]["inputs"][1] = {
                "role": "denominator",
                "kind": "evidence",
                "ref_id": total["id"],
                **{key: total[key] for key in ("value", "metric", "definition", *CONTEXT_FIELDS)},
                "lineage": [total["id"]],
                "producer_operation": None,
            }
        else:
            step["execution"]["inputs"][0]["lineage"] = lineage
        step["proposal"]["requires_basis"] = lineage
        step["execution"]["output"]["lineage"] = lineage
        step["observation"]["output"]["lineage"] = lineage
        step["claim"]["proposition"]["lineage"] = lineage
        step["claim"]["grounding"] = lineage
    forged["final"]["citations"] = lineage
    return rehash_records(forged)


def run_controls(
    contract: dict[str, Any], source: dict[str, Any], records: dict[str, Any]
) -> dict[str, Any]:
    inputs = records["steps"][0]["execution"]["inputs"]
    rows: list[dict[str, Any]] = []
    for name in (
        "missing_component",
        "duplicate_component",
        "wrong_period",
        "wrong_unit",
        "wrong_scope",
        "missing_sum",
        "mean_parameter",
    ):
        candidate = copy.deepcopy(inputs)
        params = {"method": "sum"}
        if name == "missing_component":
            candidate.pop(1)
        elif name == "duplicate_component":
            candidate[1] = copy.deepcopy(candidate[0])
        elif name.startswith("wrong_"):
            candidate[1][name.removeprefix("wrong_")] = "outside_frozen_source_context"
        else:
            params = {} if name == "missing_sum" else {"method": "mean"}
        try:
            admit_inputs("relation_sum", candidate, params, contract, source)
        except ShareError as error:
            rows.append(
                {
                    "name": name,
                    "rejected": True,
                    "stage": error.stage,
                    "reason_sha256": hashlib.sha256(str(error).encode()).hexdigest(),
                }
            )
        else:
            rows.append({"name": name, "rejected": False, "stage": None})
    forged = forged_disclosed_denominator(source, records)
    report = validate_records(contract, source, forged)
    rows.append(
        {
            "name": "claimed_reconstruction_consumes_disclosed_total",
            "rejected": not report["qualified"],
            "validation": report,
            "all_prospective_objects_rehashed": True,
            "answer_bytes_retained": forged["final"]["answer"] == records["final"]["answer"],
            "candidate_records": forged,
        }
    )
    swapped = copy.deepcopy(inputs)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    swap_checks = admit_inputs("relation_sum", swapped, {"method": "sum"}, contract, source)
    return record(
        "controls",
        controls=rows,
        attempted=len(rows),
        rejected=sum(bool(row["rejected"]) for row in rows),
        all_rejected=all(row["rejected"] for row in rows),
        legal_member_permutation_admission=all(swap_checks.values()),
        candidate_runtime_executions=0,
        extra_formal_semantic_pairs=0,
        control_kind="direct_admission_and_prospective_record_replay_not_executed_candidates",
    )
