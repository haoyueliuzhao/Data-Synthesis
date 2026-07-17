from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from finraw.db.client import DBProtocol
from finraw.fact_standardization import (
    TIME_NORMALIZATION_VERSION,
    UNIT_NORMALIZATION_VERSION,
)
from finraw.qa.comparability import comparability_policy
from finraw.qa.operators import operation_operator_manifest
from finraw.qa.pattern_mining import (
    get_approved_mining_run,
    load_published_proposals,
)
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.semantic_constraints import semantic_operator_manifest
from finraw.qa.store import insert_rows, json_value
from finraw.source_definitions import (
    SEASONAL_ADJUSTMENT_POLICY_VERSION,
    SOURCE_DEFINITION_SCHEMA_VERSION,
)


CATALOG_VERSION = "1.2.0"

_ENTRY_JSON_COLUMNS = {
    "pattern_spec",
    "operator_dag_template",
    "answer_schema",
    "binding_examples",
    "heldout_bindings",
}
_ENTRY_LIST_COLUMNS = {"binding_examples", "heldout_bindings"}
_METRIC_COMPATIBILITY_FIELDS = (
    "metric_category",
    "statement_type",
    "period_type",
    "aggregation_rule",
)
_RUNTIME_COMPATIBILITY_FIELDS = (
    "semantic_operator_manifest_hash",
    "operation_operator_manifest_hash",
    "comparability_policy_hash",
    "unit_normalization_version",
    "time_normalization_version",
    "source_definition_schema_version",
    "seasonal_adjustment_policy_version",
)


def catalog_runtime_contract(
    comparability_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deployment-independent semantic runtime contract."""
    effective_policy = comparability_policy(comparability_config)
    semantic_manifest = semantic_operator_manifest()
    operation_manifest = operation_operator_manifest()
    return {
        "semantic_operator_manifest_hash": _digest(semantic_manifest),
        "operation_operator_manifest_hash": _digest(operation_manifest),
        "comparability_policy_hash": _digest(effective_policy),
        "unit_normalization_version": UNIT_NORMALIZATION_VERSION,
        "time_normalization_version": TIME_NORMALIZATION_VERSION,
        "source_definition_schema_version": SOURCE_DEFINITION_SCHEMA_VERSION,
        "seasonal_adjustment_policy_version": (
            SEASONAL_ADJUSTMENT_POLICY_VERSION
        ),
        "semantic_operator_manifest": semantic_manifest,
        "operation_operator_manifest": operation_manifest,
        "comparability_policy": effective_policy,
    }


def publish_mining_run_to_catalog(
    db: DBProtocol,
    mining_run_id: str,
    *,
    publisher: str,
    notes: str | None = None,
) -> dict[str, Any]:
    """Publish immutable Proposal snapshots from one approved Mining Run."""
    ensure_qa_schema(db)
    run_row = db.fetchone(
        "SELECT kg_build_id FROM qa_pattern_mining_runs WHERE mining_run_id = ?",
        (mining_run_id,),
    )
    if not run_row:
        raise ValueError(f"Unknown QA pattern Mining Run: {mining_run_id}")
    source_kg_build_id = str(run_row["kg_build_id"])
    run = get_approved_mining_run(db, source_kg_build_id, mining_run_id)
    source_manifest_hash = str(run["published_proposal_manifest_hash"])
    proposals = load_published_proposals(
        db,
        source_kg_build_id,
        mining_run_id,
        limit=max(int(run.get("approved_count") or 0), 1),
    )
    if not proposals:
        raise RuntimeError("A Pattern Catalog release requires published Proposals")

    source_kg_row = db.fetchone(
        "SELECT * FROM kg_builds WHERE kg_build_id = ?",
        (source_kg_build_id,),
    )
    if not source_kg_row:
        raise RuntimeError(
            f"Source KG disappeared before Catalog publication: {source_kg_build_id}"
        )
    compatibility_contract = _build_compatibility_contract(
        db,
        dict(source_kg_row),
        proposals,
        catalog_runtime_contract(
            json_value(run.get("notes"), {}).get("semantic_policy")
        ),
    )

    release_id = "qacatrelease_" + _digest(
        CATALOG_VERSION,
        mining_run_id,
        source_manifest_hash,
        compatibility_contract,
    )[:24]
    existing = db.fetchone(
        "SELECT catalog_release_id FROM qa_pattern_catalog_releases "
        "WHERE catalog_release_id = ?",
        (release_id,),
    )
    if existing:
        return load_pattern_catalog_release(db, release_id)

    published_at = _now()
    entries = [
        _catalog_entry(
            proposal,
            release_id=release_id,
            published_at=published_at,
        )
        for proposal in proposals
    ]
    manifest = _catalog_manifest(
        release_id,
        mining_run_id,
        source_kg_build_id,
        source_manifest_hash,
        compatibility_contract,
        entries,
    )
    release = {
        "catalog_release_id": release_id,
        "catalog_version": CATALOG_VERSION,
        "source_mining_run_id": mining_run_id,
        "source_kg_build_id": source_kg_build_id,
        "source_manifest_hash": source_manifest_hash,
        "catalog_manifest": manifest,
        "catalog_manifest_hash": _digest(manifest),
        "entry_count": len(entries),
        "status": "published",
        "published_at": published_at,
        "published_by": publisher,
        "notes": {"publication_notes": notes} if notes else {},
    }
    with db.transaction():
        insert_rows(
            db,
            "qa_pattern_catalog_releases",
            [release],
            list(release),
            {"catalog_manifest", "notes"},
        )
        insert_rows(
            db,
            "qa_pattern_catalog_entries",
            entries,
            list(entries[0]),
            _ENTRY_JSON_COLUMNS,
        )
    return load_pattern_catalog_release(db, release_id)


def load_pattern_catalog_release(
    db: DBProtocol,
    catalog_release_id: str,
) -> dict[str, Any]:
    """Load and fail closed on any release or entry snapshot drift."""
    ensure_qa_schema(db)
    raw_release = db.fetchone(
        "SELECT * FROM qa_pattern_catalog_releases WHERE catalog_release_id = ?",
        (catalog_release_id,),
    )
    if not raw_release:
        raise ValueError(f"Unknown Pattern Catalog release: {catalog_release_id}")
    release = dict(raw_release)
    release["catalog_manifest"] = json_value(
        release.get("catalog_manifest"), {}
    )
    release["notes"] = json_value(release.get("notes"), {})
    if release.get("status") != "published":
        raise RuntimeError(
            f"Pattern Catalog release is not published: {catalog_release_id}"
        )

    entries = _load_entries(db, catalog_release_id)
    errors: list[str] = []
    if release.get("catalog_version") != CATALOG_VERSION:
        errors.append("catalog version is unsupported")
    for entry in entries:
        observed_hash = str(entry.get("catalog_entry_hash") or "")
        expected_hash = _digest(_entry_hash_payload(entry))
        if observed_hash != expected_hash:
            errors.append(f"{entry['catalog_entry_id']}: catalog entry hash changed")
        if entry.get("status") != "published":
            errors.append(f"{entry['catalog_entry_id']}: entry is not published")
        if entry.get("catalog_release_id") != catalog_release_id:
            errors.append(f"{entry['catalog_entry_id']}: release identity mismatch")
        if entry.get("source_mining_run_id") != release.get(
            "source_mining_run_id"
        ):
            errors.append(f"{entry['catalog_entry_id']}: source run mismatch")
        if entry.get("source_kg_build_id") != release.get("source_kg_build_id"):
            errors.append(f"{entry['catalog_entry_id']}: source KG mismatch")

    compatibility_contract = json_value(
        release["catalog_manifest"].get("compatibility_contract"), {}
    )
    if compatibility_contract.get("contract_version") != 2:
        errors.append("catalog compatibility contract is missing or unsupported")
    errors.extend(
        _runtime_contract_payload_errors(
            compatibility_contract,
            prefix="catalog",
        )
    )
    expected_manifest = _catalog_manifest(
        catalog_release_id,
        str(release["source_mining_run_id"]),
        str(release["source_kg_build_id"]),
        str(release["source_manifest_hash"]),
        compatibility_contract,
        entries,
    )
    expected_manifest_hash = _digest(expected_manifest)
    if int(release.get("entry_count") or 0) != len(entries):
        errors.append("catalog entry_count changed")
    if release.get("catalog_manifest") != expected_manifest:
        errors.append("catalog manifest changed")
    if release.get("catalog_manifest_hash") != expected_manifest_hash:
        errors.append("catalog manifest hash changed")
    if errors:
        raise RuntimeError(
            f"Pattern Catalog release {catalog_release_id} failed validation: "
            + "; ".join(errors)
        )
    release["compatibility_contract"] = compatibility_contract
    release["entries"] = entries
    return release


def load_catalog_patterns(
    db: DBProtocol,
    catalog_release_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return self-contained Catalog entries in the compiler Proposal shape."""
    release = load_pattern_catalog_release(db, catalog_release_id)
    ordered = sorted(
        release["entries"],
        key=lambda item: (
            -float(item.get("total_score") or 0.0),
            -int(item.get("support_count") or 0),
            str(item["catalog_entry_id"]),
        ),
    )
    return [_proposal_view(entry) for entry in ordered[: max(limit, 0)]]


def validate_catalog_target_compatibility(
    db: DBProtocol,
    release: dict[str, Any],
    target_kg: dict[str, Any],
    *,
    target_runtime_contract: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed when a Catalog release cannot preserve its target semantics."""
    contract = json_value(release.get("compatibility_contract"), {})
    errors: list[str] = []
    if contract.get("contract_version") != 2:
        errors.append("catalog compatibility contract version must be 2")
    errors.extend(_runtime_contract_payload_errors(contract, prefix="catalog"))
    errors.extend(
        _runtime_contract_payload_errors(
            target_runtime_contract,
            prefix="target",
        )
    )
    runtime_mismatches: list[dict[str, Any]] = []
    for field_name in _RUNTIME_COMPATIBILITY_FIELDS:
        expected_value = contract.get(field_name)
        observed_value = target_runtime_contract.get(field_name)
        if expected_value != observed_value:
            runtime_mismatches.append(
                {
                    "field": field_name,
                    "expected": expected_value,
                    "observed": observed_value,
                }
            )
    if runtime_mismatches:
        errors.append(
            "target semantic runtime mismatch: "
            + ", ".join(item["field"] for item in runtime_mismatches)
        )
    scan_kinds = sorted(str(value) for value in contract.get("scan_kinds") or [])
    unsupported_scan_kinds = sorted(set(scan_kinds) - {"fact", "graph"})
    if unsupported_scan_kinds:
        errors.append(
            "unsupported scan kinds: " + ", ".join(unsupported_scan_kinds)
        )
    ir_versions = sorted(int(value) for value in contract.get("ir_versions") or [])
    unsupported_ir_versions = sorted(set(ir_versions) - {1})
    if unsupported_ir_versions:
        errors.append(
            "unsupported IR versions: "
            + ", ".join(str(value) for value in unsupported_ir_versions)
        )
    source_schema = str(contract.get("graph_schema_version") or "")
    target_schema = str(target_kg.get("graph_schema_version") or "")
    if source_schema != target_schema:
        errors.append(
            f"graph_schema_version expected {source_schema}, observed {target_schema}"
        )

    metric_contracts = list(contract.get("metric_contracts") or [])
    required_metric_ids = [
        str(item["metric_id"]) for item in metric_contracts if item.get("metric_id")
    ]
    target_metrics: dict[str, dict[str, Any]] = {}
    if required_metric_ids:
        placeholders = ",".join("?" for _ in required_metric_ids)
        for raw in db.fetchall(
            f"SELECT * FROM metrics WHERE build_id = ? "
            f"AND metric_id IN ({placeholders}) ORDER BY metric_id",
            [target_kg["input_metric_build_id"], *required_metric_ids],
        ):
            metric = dict(raw)
            target_metrics[str(metric["metric_id"])] = metric

    missing_metrics = sorted(set(required_metric_ids) - set(target_metrics))
    if missing_metrics:
        errors.append("missing target metrics: " + ", ".join(missing_metrics))
    metric_mismatches: list[dict[str, Any]] = []
    for expected in metric_contracts:
        metric_id = str(expected.get("metric_id") or "")
        observed = target_metrics.get(metric_id)
        if observed is None:
            continue
        for field_name in _METRIC_COMPATIBILITY_FIELDS:
            expected_value = expected.get(field_name)
            observed_value = observed.get(field_name)
            if expected_value is not None and observed_value != expected_value:
                metric_mismatches.append(
                    {
                        "metric_id": metric_id,
                        "field": field_name,
                        "expected": expected_value,
                        "observed": observed_value,
                    }
                )
    if metric_mismatches:
        errors.append(
            "target metric ontology mismatch: "
            + ", ".join(
                f"{item['metric_id']}.{item['field']}"
                for item in metric_mismatches
            )
        )

    report = {
        "contract_version": contract.get("contract_version"),
        "catalog_release_id": release.get("catalog_release_id"),
        "source_kg_build_id": release.get("source_kg_build_id"),
        "target_kg_build_id": target_kg.get("kg_build_id"),
        "source_graph_schema_version": source_schema,
        "target_graph_schema_version": target_schema,
        "scan_kinds": scan_kinds,
        "ir_versions": ir_versions,
        "target_metric_build_id": target_kg.get("input_metric_build_id"),
        "required_metric_ids": required_metric_ids,
        "missing_metric_ids": missing_metrics,
        "metric_mismatches": metric_mismatches,
        "runtime_contract": {
            field_name: contract.get(field_name)
            for field_name in _RUNTIME_COMPATIBILITY_FIELDS
        },
        "target_runtime_contract": {
            field_name: target_runtime_contract.get(field_name)
            for field_name in _RUNTIME_COMPATIBILITY_FIELDS
        },
        "runtime_mismatches": runtime_mismatches,
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }
    if errors:
        raise RuntimeError(
            f"Pattern Catalog release {release.get('catalog_release_id')} is "
            f"incompatible with target KG {target_kg.get('kg_build_id')}: "
            + "; ".join(errors)
        )
    return report


def _build_compatibility_contract(
    db: DBProtocol,
    source_kg: dict[str, Any],
    proposals: list[dict[str, Any]],
    runtime_contract: dict[str, Any],
) -> dict[str, Any]:
    specs = [json_value(proposal.get("pattern_spec"), {}) for proposal in proposals]
    metric_ids = sorted(
        {
            metric_id
            for spec in specs
            for metric_id in _pattern_metric_ids(spec)
        }
    )
    metrics: dict[str, dict[str, Any]] = {}
    if metric_ids:
        placeholders = ",".join("?" for _ in metric_ids)
        for raw in db.fetchall(
            f"SELECT * FROM metrics WHERE build_id = ? "
            f"AND metric_id IN ({placeholders}) ORDER BY metric_id",
            [source_kg["input_metric_build_id"], *metric_ids],
        ):
            metric = dict(raw)
            metrics[str(metric["metric_id"])] = metric
    missing = sorted(set(metric_ids) - set(metrics))
    if missing:
        raise RuntimeError(
            "Catalog publication cannot freeze missing source metrics: "
            + ", ".join(missing)
        )

    binding_queries = [
        json_value(spec.get("binding_query"), {}) for spec in specs
    ]
    return {
        "contract_version": 2,
        "graph_schema_version": str(source_kg.get("graph_schema_version") or ""),
        "scan_kinds": sorted(
            {str(query.get("scan_kind") or "fact") for query in binding_queries}
        ),
        "ir_versions": sorted(
            {int(query.get("ir_version") or 1) for query in binding_queries}
        ),
        "metric_contracts": [
            {
                "metric_id": metric_id,
                **{
                    field_name: metrics[metric_id].get(field_name)
                    for field_name in _METRIC_COMPATIBILITY_FIELDS
                },
            }
            for metric_id in metric_ids
        ],
        **runtime_contract,
    }


def _runtime_contract_payload_errors(
    contract: dict[str, Any],
    *,
    prefix: str,
) -> list[str]:
    errors: list[str] = []
    payloads = (
        (
            "semantic_operator_manifest",
            "semantic_operator_manifest_hash",
        ),
        (
            "operation_operator_manifest",
            "operation_operator_manifest_hash",
        ),
        ("comparability_policy", "comparability_policy_hash"),
    )
    for payload_field, hash_field in payloads:
        payload = contract.get(payload_field)
        observed_hash = str(contract.get(hash_field) or "")
        if not isinstance(payload, dict):
            errors.append(f"{prefix} {payload_field} is missing")
        elif observed_hash != _digest(payload):
            errors.append(f"{prefix} {hash_field} does not match its payload")
    for field_name in (
        "unit_normalization_version",
        "time_normalization_version",
        "source_definition_schema_version",
        "seasonal_adjustment_policy_version",
    ):
        if not str(contract.get(field_name) or "").strip():
            errors.append(f"{prefix} {field_name} is missing")
    return errors


def _pattern_metric_ids(spec: dict[str, Any]) -> list[str]:
    metric_ids: set[str] = set()
    for constraint in spec.get("node_constraints") or []:
        if constraint.get("variable") == "metrics":
            metric_ids.update(
                str(value) for value in constraint.get("values") or []
            )
    query = json_value(spec.get("binding_query"), {})
    for operation in query.get("relational_ops") or []:
        if operation.get("metric_id"):
            metric_ids.add(str(operation["metric_id"]))
        metric_ids.update(
            str(role["metric_id"])
            for role in operation.get("roles") or []
            if role.get("metric_id")
        )
    return sorted(metric_ids)


def _catalog_entry(
    proposal: dict[str, Any],
    *,
    release_id: str,
    published_at: str,
) -> dict[str, Any]:
    semantic_id = str(proposal["proposal_semantic_id"])
    catalog_pattern_id = "qacatpat_" + _digest(semantic_id)[:24]
    entry = {
        "catalog_entry_id": "qacatentry_"
        + _digest(release_id, proposal["proposal_id"])[:24],
        "catalog_release_id": release_id,
        "catalog_pattern_id": catalog_pattern_id,
        "catalog_entry_hash": "",
        "source_proposal_id": str(proposal["proposal_id"]),
        "source_proposal_hash": str(proposal["proposal_hash"]),
        "source_mining_run_id": str(proposal["mining_run_id"]),
        "source_kg_build_id": str(proposal["kg_build_id"]),
        "proposal_semantic_id": semantic_id,
        "proposal_snapshot_id": str(proposal["proposal_snapshot_id"]),
        "motif_family": str(proposal["motif_family"]),
        "motif_signature": str(proposal["motif_signature"]),
        "pattern_semantic_digest": str(proposal["pattern_semantic_digest"]),
        "static_pattern_id": proposal.get("static_pattern_id"),
        "static_pattern_version": proposal.get("static_pattern_version"),
        "static_pattern_hash": proposal.get("static_pattern_hash"),
        "binding_mode": str(proposal["binding_mode"]),
        "pattern_spec": json_value(proposal.get("pattern_spec"), {}),
        "operator_dag_template": json_value(
            proposal.get("operator_dag_template"), {}
        ),
        "answer_schema": json_value(proposal.get("answer_schema"), {}),
        "binding_examples": json_value(proposal.get("binding_examples"), []),
        "heldout_bindings": json_value(proposal.get("heldout_bindings"), []),
        "support_count": int(proposal.get("support_count") or 0),
        "total_score": float(proposal.get("total_score") or 0.0),
        "semantic_constraint_pass_rate": float(
            proposal.get("semantic_constraint_pass_rate") or 0.0
        ),
        "operation_execution_pass_rate": float(
            proposal.get("operation_execution_pass_rate") or 0.0
        ),
        "example_binding_pass_rate": float(
            proposal.get("example_binding_pass_rate") or 0.0
        ),
        "heldout_binding_pass_rate": float(
            proposal.get("heldout_binding_pass_rate") or 0.0
        ),
        "static_pattern_overlap": float(
            proposal.get("static_pattern_overlap") or 0.0
        ),
        "status": "published",
        "published_at": published_at,
    }
    entry["catalog_entry_hash"] = _digest(_entry_hash_payload(entry))
    return entry


def _entry_hash_payload(entry: dict[str, Any]) -> dict[str, Any]:
    payload = {
        key: entry.get(key)
        for key in (
            "catalog_entry_id",
            "catalog_release_id",
            "catalog_pattern_id",
            "source_proposal_id",
            "source_proposal_hash",
            "source_mining_run_id",
            "source_kg_build_id",
            "proposal_semantic_id",
            "proposal_snapshot_id",
            "motif_family",
            "motif_signature",
            "pattern_semantic_digest",
            "static_pattern_id",
            "static_pattern_version",
            "static_pattern_hash",
            "binding_mode",
            "pattern_spec",
            "operator_dag_template",
            "answer_schema",
            "binding_examples",
            "heldout_bindings",
            "support_count",
            "total_score",
            "semantic_constraint_pass_rate",
            "operation_execution_pass_rate",
            "example_binding_pass_rate",
            "heldout_binding_pass_rate",
            "static_pattern_overlap",
            "status",
        )
    }
    payload["published_at"] = _canonical_timestamp(entry.get("published_at"))
    return payload


def _canonical_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _catalog_manifest(
    release_id: str,
    source_mining_run_id: str,
    source_kg_build_id: str,
    source_manifest_hash: str,
    compatibility_contract: dict[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "manifest_version": 2,
        "catalog_version": CATALOG_VERSION,
        "catalog_release_id": release_id,
        "source_mining_run_id": source_mining_run_id,
        "source_kg_build_id": source_kg_build_id,
        "source_manifest_hash": source_manifest_hash,
        "compatibility_contract": compatibility_contract,
        "entry_count": len(entries),
        "entries": [
            {
                "catalog_entry_id": str(entry["catalog_entry_id"]),
                "catalog_pattern_id": str(entry["catalog_pattern_id"]),
                "catalog_entry_hash": str(entry["catalog_entry_hash"]),
                "source_proposal_id": str(entry["source_proposal_id"]),
                "source_proposal_hash": str(entry["source_proposal_hash"]),
                "proposal_semantic_id": str(entry["proposal_semantic_id"]),
            }
            for entry in sorted(
                entries, key=lambda item: str(item["catalog_entry_id"])
            )
        ],
    }


def _load_entries(
    db: DBProtocol,
    catalog_release_id: str,
) -> list[dict[str, Any]]:
    rows = db.fetchall(
        "SELECT * FROM qa_pattern_catalog_entries "
        "WHERE catalog_release_id = ? ORDER BY catalog_entry_id",
        (catalog_release_id,),
    )
    output = []
    for raw in rows:
        entry = dict(raw)
        for column in _ENTRY_JSON_COLUMNS:
            entry[column] = json_value(
                entry.get(column), [] if column in _ENTRY_LIST_COLUMNS else {}
            )
        output.append(entry)
    return output


def _proposal_view(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": entry["source_proposal_id"],
        "proposal_hash": entry["source_proposal_hash"],
        "mining_run_id": entry["source_mining_run_id"],
        "kg_build_id": entry["source_kg_build_id"],
        "proposal_semantic_id": entry["proposal_semantic_id"],
        "proposal_snapshot_id": entry["proposal_snapshot_id"],
        "motif_family": entry["motif_family"],
        "motif_signature": entry["motif_signature"],
        "pattern_semantic_digest": entry["pattern_semantic_digest"],
        "static_pattern_id": entry.get("static_pattern_id"),
        "static_pattern_version": entry.get("static_pattern_version"),
        "static_pattern_hash": entry.get("static_pattern_hash"),
        "static_pattern_overlap": entry.get("static_pattern_overlap"),
        "binding_mode": entry["binding_mode"],
        "pattern_spec": entry["pattern_spec"],
        "operator_dag_template": entry["operator_dag_template"],
        "answer_schema": entry["answer_schema"],
        "binding_examples": entry["binding_examples"],
        "heldout_bindings": entry["heldout_bindings"],
        "support_count": entry["support_count"],
        "total_score": entry["total_score"],
        "semantic_constraint_pass_rate": entry[
            "semantic_constraint_pass_rate"
        ],
        "operation_execution_pass_rate": entry[
            "operation_execution_pass_rate"
        ],
        "example_binding_pass_rate": entry["example_binding_pass_rate"],
        "heldout_binding_pass_rate": entry["heldout_binding_pass_rate"],
        "status": "published",
        "pattern_catalog_release_id": entry["catalog_release_id"],
        "pattern_catalog_entry_id": entry["catalog_entry_id"],
        "pattern_catalog_entry_hash": entry["catalog_entry_hash"],
        "catalog_pattern_id": entry["catalog_pattern_id"],
    }


def _digest(*values: Any) -> str:
    payload: Any = values[0] if len(values) == 1 else values
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
