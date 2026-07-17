from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import product
from datetime import datetime, timezone
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.graph_binding_ir import (
    expand_graph_edges,
    project_graph_binding,
    scan_pinned_graph_nodes,
)
from finraw.qa.comparability import (
    annual_duration_valid,
    comparability_policy,
    fact_frequency,
    latest_contiguous_window,
    period_index,
    period_label,
)
from finraw.qa.pattern_mining import (
    _deduplicate_facts,
    _financial_scope,
    _period_key,
    _series_groups,
    _truthy,
    _unique_scope_entities,
)
from finraw.qa.plans import execute_plan, materialize_plan
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.semantic_constraints import validate_semantic_constraints
from finraw.qa.store import insert_rows, json_value


METRIC_FACT_SCAN_VERSION = "1"


@dataclass
class MetricFactCache:
    qa_build_id: str
    enabled: bool = True
    _facts_by_key: dict[tuple[str, ...], tuple[dict[str, Any], ...]] = field(
        default_factory=dict
    )
    _metrics_by_key: dict[tuple[str, str], dict[str, Any]] = field(
        default_factory=dict
    )
    _scanned_fact_keys: set[tuple[str, ...]] = field(default_factory=set)
    hit_count: int = 0
    miss_count: int = 0
    fact_query_count: int = 0
    loaded_fact_count: int = 0
    reused_fact_count: int = 0

    def fact_key(
        self,
        kg: dict[str, Any],
        metric_id: str,
        rows_per_metric: int,
    ) -> tuple[str, ...]:
        return (
            str(kg["kg_build_id"]),
            str(kg["input_fact_build_id"]),
            str(kg["input_entity_build_id"]),
            str(kg["input_metric_build_id"]),
            str(metric_id),
            metric_fact_scan_policy_hash(rows_per_metric),
        )

    def get_facts(
        self, key: tuple[str, ...]
    ) -> list[dict[str, Any]] | None:
        if not self.enabled:
            return None
        cached = self._facts_by_key.get(key)
        if cached is None:
            self.miss_count += 1
            return None
        self.hit_count += 1
        self.reused_fact_count += len(cached)
        return [dict(row) for row in cached]

    def put_facts(
        self, key: tuple[str, ...], rows: list[dict[str, Any]]
    ) -> None:
        snapshot = tuple(dict(row) for row in rows)
        self._scanned_fact_keys.add(key)
        self.fact_query_count += 1
        self.loaded_fact_count += len(snapshot)
        if self.enabled:
            self._facts_by_key[key] = snapshot

    def get_metric(self, metric_build_id: str, metric_id: str) -> dict[str, Any] | None:
        row = self._metrics_by_key.get((str(metric_build_id), str(metric_id)))
        return dict(row) if row is not None else None

    def put_metric(
        self, metric_build_id: str, metric_id: str, row: dict[str, Any]
    ) -> None:
        if self.enabled:
            self._metrics_by_key[(str(metric_build_id), str(metric_id))] = dict(row)

    def snapshot(self) -> dict[str, int]:
        return {
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "fact_query_count": self.fact_query_count,
            "loaded_fact_count": self.loaded_fact_count,
            "reused_fact_count": self.reused_fact_count,
        }

    def delta(self, before: dict[str, int]) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            **{
                key: value - int(before.get(key, 0))
                for key, value in self.snapshot().items()
            },
        }

    def summary(self) -> dict[str, Any]:
        keys = list(self._scanned_fact_keys)
        return {
            "enabled": self.enabled,
            "scope": "qa_build",
            "qa_build_id": self.qa_build_id,
            "scan_version": METRIC_FACT_SCAN_VERSION,
            "entry_count": len(self._facts_by_key),
            "scanned_key_count": len(keys),
            "metric_ids": sorted({key[4] for key in keys}),
            "scan_policy_hashes": sorted({key[5] for key in keys}),
            **self.snapshot(),
        }


def metric_fact_scan_policy_hash(rows_per_metric: int) -> str:
    return _digest(
        {
            "scan_version": METRIC_FACT_SCAN_VERSION,
            "rows_per_metric": int(rows_per_metric),
            "graph_ready": True,
            "is_forecast": False,
            "requires_value_and_unit": True,
            "blocked_comparability_levels": [
                "blocked",
                "incomparable",
                "not_comparable",
                "source_definition_mismatch",
            ],
            "order": ["entity_id", "period_end_desc", "fact_id"],
        }
    )


def execute_compiled_bindings(
    db: DBProtocol,
    kg: dict[str, Any],
    proposal: dict[str, Any],
    logical_plan: Any,
    *,
    qa_build_id: str,
    limit: int,
    policy: dict[str, Any],
    metric_fact_cache: MetricFactCache | None = None,
) -> list[dict[str, Any]]:
    ensure_qa_schema(db)
    plan_row = logical_plan.as_row()
    plan_hash = _digest(plan_row)
    compilation_id = (
        "qacomp_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")
        + uuid.uuid4().hex[:8]
    )
    started_at = _now()
    compilation = {
        "compilation_id": compilation_id,
        "qa_build_id": qa_build_id,
        "proposal_id": proposal["proposal_id"],
        "proposal_hash": proposal["proposal_hash"],
        "pattern_catalog_release_id": proposal.get("pattern_catalog_release_id"),
        "pattern_catalog_entry_id": proposal.get("pattern_catalog_entry_id"),
        "pattern_catalog_entry_hash": proposal.get("pattern_catalog_entry_hash"),
        "catalog_pattern_id": proposal.get("catalog_pattern_id"),
        "source_kg_build_id": proposal["kg_build_id"],
        "target_kg_build_id": kg["kg_build_id"],
        "fact_build_id": kg["input_fact_build_id"],
        "compiler_version": plan_row["compiler_version"],
        "logical_plan": plan_row,
        "logical_plan_hash": plan_hash,
        "status": "running",
        "started_at": started_at,
        "completed_at": None,
        "discovered_binding_count": 0,
        "semantic_valid_binding_count": 0,
        "execution_valid_binding_count": 0,
        "compiled_binding_count": 0,
        "rejected_binding_count": 0,
        "sampling_summary": {},
        "notes": {
            "binding_source": "compiled_query",
            "binding_executor": "declarative_ir_interpreter",
        },
    }
    insert_rows(
        db,
        "qa_pattern_compilations",
        [compilation],
        list(compilation),
        {"logical_plan", "sampling_summary", "notes"},
    )
    try:
        cache_before = (
            metric_fact_cache.snapshot() if metric_fact_cache is not None else {}
        )
        audit_hashes = {
            _digest(binding)
            for key in ("binding_examples", "heldout_bindings")
            for binding in json_value(proposal.get(key), [])
        }
        execution_state = execute_relational_ops(
            db,
            kg,
            plan_row,
            proposal,
            policy,
            audit_hashes=audit_hashes,
            limit=limit,
            metric_fact_cache=metric_fact_cache,
        )
        selected = execution_state.relation
        discovered = execution_state.discovered_count
        semantic_valid = execution_state.semantic_valid_count
        execution_valid = execution_state.execution_valid_count
        binding_rows = []
        matches = []
        semantic_identity = proposal.get("proposal_semantic_id") or proposal.get(
            "motif_signature"
        )
        pattern_id = str(
            proposal.get("static_pattern_id")
            or proposal.get("catalog_pattern_id")
            or "mined_" + str(semantic_identity)[:20]
        )
        for item in selected:
            compiled_binding_id = (
                "qacbind_" + _digest([compilation_id, item["binding_hash"]])[:24]
            )
            binding_rows.append(
                {
                    "compiled_binding_id": compiled_binding_id,
                    "compilation_id": compilation_id,
                    "qa_build_id": qa_build_id,
                    "proposal_id": proposal["proposal_id"],
                    "kg_build_id": kg["kg_build_id"],
                    "binding_hash": item["binding_hash"],
                    "binding": item["binding"],
                    "sampling_stratum": item["sampling_stratum"],
                    "semantic_status": "passed",
                    "execution_status": "passed",
                    "audit_example_overlap": item["audit_example_overlap"],
                    "rejection_reasons": [],
                    "created_at": _now(),
                }
            )
            matches.append(
                {
                    **item["binding"],
                    "pattern_id": pattern_id,
                    "pattern_proposal_id": proposal["proposal_id"],
                    "mining_run_id": proposal["mining_run_id"],
                    "pattern_proposal_hash": proposal["proposal_hash"],
                    "proposal_semantic_id": proposal.get("proposal_semantic_id"),
                    "pattern_catalog_release_id": proposal.get(
                        "pattern_catalog_release_id"
                    ),
                    "pattern_catalog_entry_id": proposal.get(
                        "pattern_catalog_entry_id"
                    ),
                    "pattern_catalog_entry_hash": proposal.get(
                        "pattern_catalog_entry_hash"
                    ),
                    "catalog_pattern_id": proposal.get("catalog_pattern_id"),
                    "pattern_score": float(proposal["total_score"]),
                    "pattern_compilation_id": compilation_id,
                    "logical_plan_hash": plan_hash,
                    "compiler_version": plan_row["compiler_version"],
                    "compiled_binding_id": compiled_binding_id,
                    "compiled_binding_hash": item["binding_hash"],
                    "binding_source": "compiled_query",
                    "audit_example_overlap": item["audit_example_overlap"],
                    "sampling_stratum": item["sampling_stratum"],
                }
            )
        if binding_rows:
            insert_rows(
                db,
                "qa_compiled_bindings",
                binding_rows,
                list(binding_rows[0]),
                {"binding", "sampling_stratum", "rejection_reasons"},
            )
        summary = {
            "selected_count": len(selected),
            "audit_overlap_count": sum(
                bool(item["audit_example_overlap"]) for item in selected
            ),
            "non_audit_count": sum(
                not bool(item["audit_example_overlap"]) for item in selected
            ),
            "stratum_count": len(
                {tuple(item["sampling_stratum"]) for item in selected}
            ),
            "candidate_record_count": execution_valid,
            "operator_trace": execution_state.operator_trace,
            "rejection_counts": dict(sorted(execution_state.rejection_counts.items())),
            "metric_fact_cache": (
                metric_fact_cache.delta(cache_before)
                if metric_fact_cache is not None
                else {"enabled": False}
            ),
        }
        db.execute(
            "UPDATE qa_pattern_compilations SET status = ?, completed_at = ?, "
            "discovered_binding_count = ?, semantic_valid_binding_count = ?, "
            "execution_valid_binding_count = ?, compiled_binding_count = ?, "
            "rejected_binding_count = ?, sampling_summary = ? "
            "WHERE compilation_id = ?",
            (
                "success",
                _now(),
                discovered,
                semantic_valid,
                execution_valid,
                len(selected),
                max(discovered - execution_valid, 0),
                _db_json(db, summary),
                compilation_id,
            ),
        )
        return matches
    except Exception as exc:
        db.execute(
            "UPDATE qa_pattern_compilations SET status = ?, completed_at = ?, "
            "notes = ? WHERE compilation_id = ?",
            (
                "failed",
                _now(),
                _db_json(
                    db,
                    {
                        "binding_source": "compiled_query",
                        "binding_executor": "declarative_ir_interpreter",
                        "error": str(exc),
                    },
                ),
                compilation_id,
            ),
        )
        raise


@dataclass
class RelationalExecutionState:
    db: DBProtocol
    kg: dict[str, Any]
    facts: list[dict[str, Any]]
    metrics: dict[str, dict[str, Any]]
    plan: dict[str, Any]
    pattern_spec: dict[str, Any]
    policy: dict[str, Any]
    audit_hashes: set[str]
    limit: int
    candidate_limit: int
    metric_fact_cache: MetricFactCache | None = None
    relation: list[Any] = field(default_factory=list)
    relation_kind: str = "uninitialized"
    discovered_count: int = 0
    semantic_valid_count: int = 0
    execution_valid_count: int = 0
    rejection_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    operator_trace: list[dict[str, Any]] = field(default_factory=list)


def execute_relational_ops(
    db: DBProtocol,
    kg: dict[str, Any],
    plan: dict[str, Any],
    proposal: dict[str, Any],
    policy: dict[str, Any],
    *,
    audit_hashes: set[str],
    limit: int,
    metric_fact_cache: MetricFactCache | None = None,
) -> RelationalExecutionState:
    operations = list(plan.get("relational_ops") or [])
    validate_relational_ops(operations)
    state = RelationalExecutionState(
        db=db,
        kg=kg,
        facts=[],
        metrics={},
        plan=plan,
        pattern_spec=json_value(proposal.get("pattern_spec"), {}),
        policy=policy,
        audit_hashes=audit_hashes,
        limit=max(limit, 0),
        candidate_limit=0,
        metric_fact_cache=metric_fact_cache,
    )
    for position, operation in enumerate(operations):
        operator = str(operation["op"])
        input_kind = state.relation_kind
        input_count = len(state.relation)
        RELATIONAL_OPERATOR_REGISTRY[operator](state, operation)
        state.operator_trace.append(
            {
                "position": position,
                "operator": operator,
                "input_kind": input_kind,
                "input_count": input_count,
                "output_kind": state.relation_kind,
                "output_count": len(state.relation),
            }
        )
    if state.relation_kind != "sampled_bindings":
        raise ValueError(
            "Relational plan did not terminate in sampled_bindings: "
            f"{state.relation_kind}"
        )
    return state


def validate_relational_ops(operations: list[dict[str, Any]]) -> None:
    if not operations:
        raise ValueError("Relational plan must contain at least one operator")
    malformed = [
        index
        for index, operation in enumerate(operations)
        if not isinstance(operation, dict) or not operation.get("op")
    ]
    if malformed:
        raise ValueError(f"Malformed relational operators at positions: {malformed}")
    names = [str(operation["op"]) for operation in operations]
    unknown = sorted(set(names) - set(RELATIONAL_OPERATOR_REGISTRY))
    if unknown:
        raise ValueError(f"Unsupported relational operators: {unknown}")

    fact_plan = names[:2] == [
        "scan_pinned_fact_nodes",
        "join_entity_metric_period",
    ]
    graph_plan = names[:1] == ["scan_pinned_graph_nodes"]
    if not fact_plan and not graph_plan:
        raise ValueError(
            "Relational plan must start with a registered pinned fact or graph scan"
        )
    prefix_length = 2 if fact_plan else 1
    if graph_plan and (
        names.count("project_graph_binding") != 1
        or "expand_graph_edges" not in names
    ):
        raise ValueError(
            "Graph plans require edge expansion and exactly one binding projection"
        )

    required_tail = [
        "semantic_constraint_gate",
        "operation_execution_gate",
        "sample",
    ]
    for operator in required_tail:
        if names.count(operator) != 1:
            raise ValueError(f"Relational plan must contain exactly one {operator}")
    positions = [names.index(operator) for operator in required_tail]
    if positions != sorted(positions) or positions[-1] != len(names) - 1:
        raise ValueError(
            "Relational gates must end in semantic, operation, sample order"
        )
    if positions[0] <= prefix_length:
        raise ValueError("Relational plan has no binding discovery operators")
    for operation in operations:
        if operation["op"] in {
            "join_metric_roles",
            "join_series_on_period",
            "complete_case_metric_join",
        }:
            roles = list(operation.get("roles") or [])
            if not roles or any(
                not role.get("binding") or not role.get("metric_id") for role in roles
            ):
                raise ValueError(f"{operation['op']} requires named metric roles")
        if operation["op"] == "group":
            if not operation.get("keys"):
                raise ValueError("group requires at least one key")
            if operation.get("shape") not in {
                None,
                "scope_metric_variants",
            }:
                raise ValueError(f"Unsupported group shape: {operation.get('shape')}")

def _op_scan_pinned_fact_nodes(
    state: RelationalExecutionState, operation: dict[str, Any]
) -> None:
    _expect_relation(state, "uninitialized", operation)
    facts, metrics = _load_execution_pool(
        state.db,
        state.kg,
        list(state.plan.get("metric_ids") or []),
        int(state.plan.get("sampling", {}).get("scan_rows_per_metric", 0)),
        cache=state.metric_fact_cache,
    )
    state.facts = facts
    state.metrics = metrics
    state.candidate_limit = max(
        len(facts),
        int(state.policy["max_candidates_per_proposal"])
        * int(state.policy["compiled_scan_multiplier"]),
    )
    metric_ids = set(str(value) for value in state.plan.get("metric_ids") or [])
    state.relation = [
        fact
        for fact in facts
        if str(fact.get("metric_id")) in metric_ids
        and bool(fact.get("graph_ready"))
        and not _truthy(fact.get("is_forecast"))
    ]
    state.relation_kind = "facts"


def _op_join_entity_metric_period(
    state: RelationalExecutionState, operation: dict[str, Any]
) -> None:
    _expect_relation(state, "facts", operation)
    state.relation = [
        fact
        for fact in state.relation
        if fact.get("entity_id")
        and str(fact.get("metric_id")) in state.metrics
        and any(value not in {None, ""} for value in _period_key(fact))
    ]
    state.relation_kind = "enriched_facts"


def _op_group(state: RelationalExecutionState, operation: dict[str, Any]) -> None:
    _expect_relation(state, "enriched_facts", operation)
    if operation.get("shape") == "scope_metric_variants":
        _op_group_scope(state, operation)
        return
    keys = [str(value) for value in operation["keys"]]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for fact in state.relation:
        key = tuple(_group_value(fact, field) for field in keys)
        groups[key].append(fact)
    state.relation = [
        {"key": key, "rows": groups[key]} for key in sorted(groups, key=_digest)
    ]
    state.relation_kind = "fact_groups"


def _op_join_metric_roles(
    state: RelationalExecutionState, operation: dict[str, Any]
) -> None:
    _expect_relation(state, "fact_groups", operation)
    roles = list(operation["roles"])
    candidates: list[dict[str, Any]] = []
    for group in state.relation:
        by_metric: dict[str, dict[str, Any]] = {}
        for fact in group["rows"]:
            by_metric[str(fact["metric_id"])] = fact
        if any(str(role["metric_id"]) not in by_metric for role in roles):
            continue
        role_rows = {
            str(role["binding"]): [by_metric[str(role["metric_id"])]] for role in roles
        }
        candidates.append(
            _binding_from_role_rows(
                state,
                roles,
                role_rows,
                scope_type="single_entity",
            )
        )
    _emit_candidates(state, candidates)


def _op_group_series(
    state: RelationalExecutionState, operation: dict[str, Any]
) -> None:
    _expect_relation(state, "enriched_facts", operation)
    groups = _series_groups(state.relation)
    state.relation = [
        {"key": key, "rows": rows}
        for key, rows in sorted(groups.items(), key=lambda item: item[0])
    ]
    state.relation_kind = "series_groups"


def _op_latest_contiguous_window(
    state: RelationalExecutionState, operation: dict[str, Any]
) -> None:
    _expect_relation(state, "series_groups", operation)
    windows: list[dict[str, Any]] = []
    for item in state.relation:
        key = item["key"]
        window = latest_contiguous_window(
            item["rows"],
            frequency=key.frequency,
            minimum=int(state.policy["minimum_temporal_observations"]),
            maximum=int(state.policy["maximum_temporal_observations"]),
            require_contiguous=bool(state.policy["require_contiguous_periods"]),
        )
        if not window:
            continue
        if operation.get("require_annual_duration") and any(
            not annual_duration_valid(row) for row in window
        ):
            continue
        windows.append({"key": key, "rows": window})
    binding_name = operation.get("binding")
    if binding_name:
        candidates = [
            _temporal_series_binding(str(binding_name), item["key"], item["rows"])
            for item in windows
        ]
        _emit_candidates(state, candidates)
    else:
        state.relation = windows
        state.relation_kind = "windowed_series"


def _op_join_series_on_period(
    state: RelationalExecutionState, operation: dict[str, Any]
) -> None:
    _expect_relation(state, "windowed_series", operation)
    roles = list(operation["roles"])
    coverage_required = float(operation.get("coverage", 1.0))
    by_context: dict[tuple[Any, ...], dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for item in state.relation:
        key = item["key"]
        by_context[_series_context(key)][key.metric_id].append(item)

    candidates: list[dict[str, Any]] = []
    for context in sorted(by_context, key=_digest):
        by_metric = by_context[context]
        role_options = [
            sorted(
                by_metric.get(str(role["metric_id"]), []),
                key=lambda item: item["key"],
            )
            for role in roles
        ]
        if any(not options for options in role_options):
            continue
        for selected in product(*role_options):
            primary = selected[0]
            frequency = primary["key"].frequency
            primary_indices = [period_index(row, frequency) for row in primary["rows"]]
            if not primary_indices or any(value is None for value in primary_indices):
                continue
            role_rows = {str(roles[0]["binding"]): list(primary["rows"])}
            valid = True
            for role, item in zip(roles[1:], selected[1:]):
                by_period = {period_index(row, frequency): row for row in item["rows"]}
                matched = [
                    by_period[index] for index in primary_indices if index in by_period
                ]
                coverage = len(matched) / len(primary_indices)
                if coverage < coverage_required:
                    valid = False
                    break
                role_rows[str(role["binding"])] = matched
            if not valid:
                continue
            candidates.append(
                _binding_from_series_roles(
                    roles,
                    selected,
                    role_rows,
                    coverage_required,
                )
            )
    _emit_candidates(state, candidates)


def _op_group_scope(state: RelationalExecutionState, operation: dict[str, Any]) -> None:
    _expect_relation(state, "enriched_facts", operation)
    keys = [str(value) for value in operation["keys"]]
    predicates = dict(operation.get("predicates") or {})
    required_fields = [str(value) for value in operation.get("required_fields") or []]
    groups: dict[
        tuple[Any, ...],
        dict[tuple[Any, ...], dict[str, list[dict[str, Any]]]],
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for fact in state.relation:
        if any(not fact.get(field_name) for field_name in required_fields):
            continue
        if not _scope_fact_matches(fact, predicates):
            continue
        entity_id = str(fact["entity_id"])
        context = tuple(_group_value(fact, field) for field in keys)
        variant = (
            str(fact["metric_id"]),
            str(fact.get("source_definition_id") or ""),
            str(fact.get("metric_period_type") or ""),
            str(fact.get("normalized_unit") or ""),
            str(fact.get("normalized_currency") or ""),
        )
        groups[context][variant][entity_id].append(fact)
    state.relation = [
        {
            "context": _scope_context_payload(context, keys),
            "variants": groups[context],
        }
        for context in sorted(groups, key=_digest)
    ]
    state.relation_kind = "scope_groups"


def _scope_fact_matches(fact: dict[str, Any], predicates: dict[str, Any]) -> bool:
    for field_name, expected in predicates.items():
        if field_name == "annual_duration_valid":
            observed = annual_duration_valid(fact)
        elif field_name == "entity_scope_matches_entity":
            observed = _financial_scope(fact)[0] == str(fact.get("entity_id") or "")
        elif field_name == "financial_scope_type":
            observed = _financial_scope(fact)[1]
        elif field_name == "frequency":
            observed = fact_frequency(fact)
        elif field_name == "is_forecast":
            observed = _truthy(fact.get("is_forecast"))
        elif field_name == "fiscal_quarter":
            observed = str(fact.get("fiscal_quarter") or "").upper()
            expected = str(expected).upper()
        else:
            observed = fact.get(field_name)
        if observed != expected:
            return False
    return True


def _op_complete_case_metric_join(
    state: RelationalExecutionState, operation: dict[str, Any]
) -> None:
    _expect_relation(state, "scope_groups", operation)
    roles = list(operation["roles"])
    minimum = int(state.policy["minimum_scope_entities"])
    candidates: list[dict[str, Any]] = []
    for group in state.relation:
        variants = group["variants"]
        role_options = [
            sorted(
                (
                    (variant, rows)
                    for variant, rows in variants.items()
                    if variant[0] == str(role["metric_id"])
                ),
                key=lambda item: item[0],
            )
            for role in roles
        ]
        if any(not options for options in role_options):
            continue
        for selected in product(*role_options):
            unique_by_role = [_unique_scope_entities(rows) for _, rows in selected]
            common = sorted(
                set.intersection(*(set(values) for values in unique_by_role))
            )
            if len(common) < minimum:
                continue
            role_rows = {
                str(role["binding"]): [
                    unique_by_role[index][entity_id] for entity_id in common
                ]
                for index, role in enumerate(roles)
            }
            candidates.append(
                _binding_from_scope_roles(
                    state,
                    roles,
                    selected,
                    role_rows,
                    common,
                    group["context"],
                )
            )
    _emit_candidates(state, candidates)


def _op_semantic_constraint_gate(
    state: RelationalExecutionState, operation: dict[str, Any]
) -> None:
    _expect_relation(state, "binding_candidates", operation)
    fact_map = {str(fact["fact_id"]): fact for fact in state.facts}
    semantic_policy = comparability_policy(state.policy.get("semantic_policy"))
    accepted: list[dict[str, Any]] = []
    for binding in state.relation:
        bound_facts = [
            fact_map[str(fact_id)]
            for fact_id in binding.get("fact_ids") or []
            if str(fact_id) in fact_map
        ]
        validation = validate_semantic_constraints(
            state.pattern_spec,
            binding,
            bound_facts,
            state.metrics,
            semantic_policy,
        )
        if validation.passed:
            accepted.append(binding)
        else:
            for error in validation.errors:
                state.rejection_counts[f"semantic:{error}"] += 1
    state.semantic_valid_count = len(accepted)
    state.relation = accepted
    state.relation_kind = "semantic_valid_bindings"


def _op_operation_execution_gate(
    state: RelationalExecutionState, operation: dict[str, Any]
) -> None:
    _expect_relation(state, "semantic_valid_bindings", operation)
    fact_map = {str(fact["fact_id"]): fact for fact in state.facts}
    accepted: list[dict[str, Any]] = []
    for binding in state.relation:
        operation_plan = materialize_plan(state.plan["operator_template"], binding)
        execution = execute_plan(
            operation_plan,
            binding["input_bindings"],
            fact_map,
        )
        if execution.status == "passed":
            accepted.append(binding)
        else:
            for error in execution.errors or ["unknown_execution_error"]:
                state.rejection_counts[f"operation:{error}"] += 1
    state.execution_valid_count = len(accepted)
    state.relation = accepted
    state.relation_kind = "execution_valid_bindings"


def _op_deterministic_stratified_sample(
    state: RelationalExecutionState, operation: dict[str, Any]
) -> None:
    _expect_relation(state, "execution_valid_bindings", operation)
    stratum_fields = list(state.plan.get("sampling", {}).get("stratum_fields") or [])
    candidates = []
    for binding in state.relation:
        binding_hash = _digest(binding)
        candidates.append(
            {
                "binding": binding,
                "binding_hash": binding_hash,
                "sampling_stratum": _sampling_stratum(binding, stratum_fields),
                "audit_example_overlap": binding_hash in state.audit_hashes,
            }
        )
    state.relation = _stratified_sample(
        candidates,
        state.limit,
        int(state.policy["compiled_max_per_stratum"]),
    )
    state.relation_kind = "sampled_bindings"


def _expect_relation(
    state: RelationalExecutionState,
    expected: str,
    operation: dict[str, Any],
) -> None:
    if state.relation_kind != expected:
        raise ValueError(
            f"{operation['op']} expected {expected}, found {state.relation_kind}"
        )


def _emit_candidates(
    state: RelationalExecutionState,
    candidates: list[dict[str, Any]],
) -> None:
    state.discovered_count += len(candidates)
    state.relation = candidates[: state.candidate_limit]
    state.relation_kind = "binding_candidates"


def _group_value(fact: dict[str, Any], field: str) -> Any:
    resolvers = {
        "entity": lambda row: str(row.get("entity_id") or ""),
        "period": _period_key,
        "source": lambda row: str(row.get("source_id") or ""),
        "frequency": fact_frequency,
        "time_basis": lambda row: str(row.get("time_basis") or ""),
        "metric_period_type": lambda row: str(row.get("metric_period_type") or ""),
        "statement_type": lambda row: str(row.get("statement_type") or ""),
        "financial_scope": _financial_scope,
        "unit": lambda row: str(row.get("normalized_unit") or ""),
        "currency": lambda row: str(row.get("normalized_currency") or ""),
        "industry": lambda row: str(row.get("industry") or ""),
        "entity_type": lambda row: str(row.get("entity_type") or ""),
        "source_definition": lambda row: str(row.get("source_definition_id") or ""),
        "seasonal_adjustment": lambda row: str(row.get("seasonal_adjustment") or ""),
        "vintage_policy": lambda row: str(row.get("vintage_policy") or ""),
        "comparability_level": lambda row: str(row.get("comparability_level") or ""),
    }
    if field not in resolvers:
        raise ValueError(f"Unsupported group key: {field}")
    return resolvers[field](fact)


def _binding_from_role_rows(
    state: RelationalExecutionState,
    roles: list[dict[str, Any]],
    role_rows: dict[str, list[dict[str, Any]]],
    *,
    scope_type: str,
) -> dict[str, Any]:
    all_rows = [row for role in roles for row in role_rows[str(role["binding"])]]
    first = all_rows[0]
    input_bindings = {
        str(role["binding"]): _binding_value(role_rows[str(role["binding"])])
        for role in roles
    }
    binding = {
        "input_bindings": input_bindings,
        "fact_ids": [str(row["fact_id"]) for row in all_rows],
        "entity_ids": sorted({str(row["entity_id"]) for row in all_rows}),
        "metric_ids": [str(role["metric_id"]) for role in roles],
        "period": period_label(first),
        "frequency": fact_frequency(first),
        "scope_type": scope_type,
        "scope_definition": str(first["entity_id"]),
    }
    first_step = next(
        iter(state.plan.get("operator_template", {}).get("operators") or []),
        {},
    )
    if first_step.get("params"):
        binding["operator_params"] = dict(first_step["params"])
    return binding


def _temporal_series_binding(
    binding_name: str,
    key: Any,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "input_bindings": {binding_name: [str(row["fact_id"]) for row in rows]},
        "fact_ids": [str(row["fact_id"]) for row in rows],
        "entity_ids": [str(key.entity_id)],
        "metric_ids": [str(key.metric_id)],
        "start_period": period_label(rows[0]),
        "end_period": period_label(rows[-1]),
        "observation_count": len(rows),
        "frequency": key.frequency,
        "scope_type": "single_entity_series",
        "scope_definition": str(key.entity_id),
        "financial_scope": {
            "entity_scope_id": key.financial_scope[0],
            "financial_scope_type": key.financial_scope[1],
        },
    }


def _series_context(key: Any) -> tuple[Any, ...]:
    return (
        key.entity_id,
        key.source_id,
        key.frequency,
        key.time_basis,
        key.financial_scope,
        key.normalized_unit,
        key.normalized_currency,
        key.seasonal_adjustment,
        key.vintage_policy,
        key.comparability_level,
    )


def _binding_from_series_roles(
    roles: list[dict[str, Any]],
    selected: tuple[dict[str, Any], ...],
    role_rows: dict[str, list[dict[str, Any]]],
    coverage_required: float,
) -> dict[str, Any]:
    primary = selected[0]
    key = primary["key"]
    primary_rows = role_rows[str(roles[0]["binding"])]
    all_rows = [row for role in roles for row in role_rows[str(role["binding"])]]
    source_definitions = {
        str(role["binding"]): item["key"].source_definition_id
        for role, item in zip(roles, selected)
    }
    binding = {
        "input_bindings": {
            str(role["binding"]): [
                str(row["fact_id"]) for row in role_rows[str(role["binding"])]
            ]
            for role in roles
        },
        "fact_ids": [str(row["fact_id"]) for row in all_rows],
        "entity_ids": [str(key.entity_id)],
        "metric_ids": [str(role["metric_id"]) for role in roles],
        "primary_metric_id": str(roles[0]["metric_id"]),
        "secondary_metric_id": str(roles[1]["metric_id"]),
        "start_period": period_label(primary_rows[0]),
        "end_period": period_label(primary_rows[-1]),
        "observation_count": len(primary_rows),
        "frequency": key.frequency,
        "scope_type": "single_entity_series",
        "scope_definition": str(key.entity_id),
        "source_definitions": source_definitions,
        "secondary_period_coverage": coverage_required,
        "financial_scope": {
            "entity_scope_id": key.financial_scope[0],
            "financial_scope_type": key.financial_scope[1],
        },
    }
    return binding


def _scope_context_payload(context: tuple[Any, ...], keys: list[str]) -> dict[str, Any]:
    payload = dict(zip(keys, context))
    if "period" in payload:
        payload["period_key"] = payload.pop("period")
    if "source" in payload:
        payload["source_id"] = payload.pop("source")
    if "financial_scope" in payload:
        financial_scope = payload.pop("financial_scope")
        payload["financial_scope_type"] = financial_scope[1]
    return payload


def _binding_from_scope_roles(
    state: RelationalExecutionState,
    roles: list[dict[str, Any]],
    selected: tuple[tuple[tuple[Any, ...], Any], ...],
    role_rows: dict[str, list[dict[str, Any]]],
    common: list[str],
    context: dict[str, Any],
) -> dict[str, Any]:
    all_rows = [row for role in roles for row in role_rows[str(role["binding"])]]
    first = all_rows[0]
    step_params = {}
    for step in state.plan.get("operator_template", {}).get("operators") or []:
        if step.get("operator") != "rank" or not step.get("step_id"):
            continue
        params = dict(step.get("params") or {})
        params["top_k"] = min(
            int(params.get("top_k") or state.policy["top_k"]),
            len(common),
        )
        step_params[str(step["step_id"])] = params
    return {
        "input_bindings": {
            str(role["binding"]): [
                str(row["fact_id"]) for row in role_rows[str(role["binding"])]
            ]
            for role in roles
        },
        "fact_ids": [str(row["fact_id"]) for row in all_rows],
        "entity_ids": common,
        "metric_ids": [str(role["metric_id"]) for role in roles],
        "primary_metric_id": str(roles[0]["metric_id"]),
        "secondary_metric_id": str(roles[1]["metric_id"]),
        "period": period_label(first),
        "frequency": context["frequency"],
        "scope_type": "canonical_industry_complete_case",
        "scope_definition": (
            f"the canonical '{context['industry']}' industry complete-case "
            f"universe ({len(common)} companies with unique consolidated "
            "comparable inputs)"
        ),
        "industry": context["industry"],
        "source_definitions": {
            str(role["binding"]): selected[index][0][1]
            for index, role in enumerate(roles)
        },
        "scope_input_coverage": 1.0,
        "financial_scope": {
            "financial_scope_type": "consolidated_entity",
            "entity_scope_ids": common,
        },
        "operator_step_params": step_params,
    }


def _binding_value(rows: list[dict[str, Any]]) -> Any:
    values = [str(row["fact_id"]) for row in rows]
    return values[0] if len(values) == 1 else values


RELATIONAL_OPERATOR_REGISTRY = {
    "scan_pinned_graph_nodes": scan_pinned_graph_nodes,
    "expand_graph_edges": expand_graph_edges,
    "project_graph_binding": project_graph_binding,
    "scan_pinned_fact_nodes": _op_scan_pinned_fact_nodes,
    "join_entity_metric_period": _op_join_entity_metric_period,
    "group": _op_group,
    "join_metric_roles": _op_join_metric_roles,
    "group_series": _op_group_series,
    "latest_contiguous_window": _op_latest_contiguous_window,
    "join_series_on_period": _op_join_series_on_period,
    "complete_case_metric_join": _op_complete_case_metric_join,
    "semantic_constraint_gate": _op_semantic_constraint_gate,
    "operation_execution_gate": _op_operation_execution_gate,
    "deterministic_stratified_sample": _op_deterministic_stratified_sample,
    "sample": _op_deterministic_stratified_sample,
}


def _load_execution_pool(
    db: DBProtocol,
    kg: dict[str, Any],
    metric_ids: list[str],
    rows_per_metric: int,
    cache: MetricFactCache | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    ordered_metric_ids = list(dict.fromkeys(str(value) for value in metric_ids))
    metric_build_id = str(kg["input_metric_build_id"])
    metrics: dict[str, dict[str, Any]] = {}
    missing_metric_ids: list[str] = []
    for metric_id in ordered_metric_ids:
        cached_metric = (
            cache.get_metric(metric_build_id, metric_id) if cache is not None else None
        )
        if cached_metric is None:
            missing_metric_ids.append(metric_id)
        else:
            metrics[metric_id] = cached_metric
    if missing_metric_ids:
        placeholders = ",".join("?" for _ in missing_metric_ids)
        rows = db.fetchall(
            f"SELECT * FROM metrics WHERE build_id = ? "
            f"AND metric_id IN ({placeholders}) ORDER BY metric_id",
            [metric_build_id, *missing_metric_ids],
        )
        for raw in rows:
            metric = dict(raw)
            metric_id = str(metric["metric_id"])
            metrics[metric_id] = metric
            if cache is not None:
                cache.put_metric(metric_build_id, metric_id, metric)

    facts: list[dict[str, Any]] = []
    for metric_id in ordered_metric_ids:
        cache_key = (
            cache.fact_key(kg, metric_id, rows_per_metric)
            if cache is not None
            else None
        )
        cached_facts = cache.get_facts(cache_key) if cache_key is not None else None
        if cached_facts is not None:
            facts.extend(cached_facts)
            continue

        limit_clause = "LIMIT ?" if rows_per_metric > 0 else ""
        parameters: list[Any] = [
            kg["kg_build_id"],
            kg["input_entity_build_id"],
            kg["input_metric_build_id"],
            kg["input_fact_build_id"],
            metric_id,
        ]
        if rows_per_metric > 0:
            parameters.append(rows_per_metric)
        rows = db.fetchall(
            f"""
            SELECT sf.*, ce.entity_type, ce.market, ce.country, ce.industry,
                   m.canonical_name AS metric_name, m.metric_category,
                   m.statement_type, m.period_type AS ontology_period_type,
                   m.aggregation_rule, m.revision_risk
            FROM standardized_facts sf
            JOIN kg_nodes n ON n.kg_build_id = ? AND n.node_type = 'Fact'
                           AND n.source_pk = sf.fact_id
            JOIN canonical_entities ce ON ce.build_id = ?
                                      AND ce.entity_id = sf.entity_id
            JOIN metrics m ON m.build_id = ? AND m.metric_id = sf.metric_id
            WHERE sf.build_id = ? AND sf.metric_id = ? AND sf.graph_ready = 1
              AND sf.normalized_value IS NOT NULL
              AND sf.normalized_unit IS NOT NULL
              AND COALESCE(sf.is_forecast, 0) = 0
              AND LOWER(COALESCE(sf.comparability_level, 'comparable'))
                  NOT IN ('blocked', 'incomparable', 'not_comparable',
                          'source_definition_mismatch')
            ORDER BY sf.entity_id, sf.period_end DESC, sf.fact_id
            {limit_clause}
            """,
            parameters,
        )
        loaded = _deduplicate_facts(dict(row) for row in rows)
        if cache is not None and cache_key is not None:
            cache.put_facts(cache_key, loaded)
        facts.extend(dict(row) for row in loaded)
    return facts, metrics


def _sampling_stratum(binding: dict[str, Any], fields: list[str]) -> list[str]:
    values: list[str] = []
    for field_name in fields:
        if field_name == "entity_hash_bucket":
            values.append(
                "entity_bucket_"
                + str(
                    int(
                        _digest(sorted(binding.get("entity_ids") or []))[:8],
                        16,
                    )
                    % 8
                )
            )
            continue
        value = binding.get(field_name)
        if isinstance(value, list):
            values.extend(str(item or "unknown") for item in value)
        else:
            values.append(str(value or "unknown"))
    return values


def _stratified_sample(
    candidates: list[dict[str, Any]], limit: int, max_per_stratum: int
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        groups[tuple(candidate["sampling_stratum"])].append(candidate)
    for rows in groups.values():
        rows.sort(
            key=lambda item: (
                bool(item["audit_example_overlap"]),
                item["binding_hash"],
            )
        )
    selected = []
    for index in range(max_per_stratum):
        for key in sorted(groups, key=lambda value: _digest(value)):
            if index < len(groups[key]):
                selected.append(groups[key][index])
                if len(selected) >= limit:
                    return selected
    return selected


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_json(db: DBProtocol, value: Any) -> Any:
    if db.__class__.__name__ == "PostgresMetadataDB":
        from psycopg.types.json import Jsonb

        return Jsonb(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
