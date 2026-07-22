from __future__ import annotations

import hashlib
import heapq
import json
import re
from collections import Counter, defaultdict
from typing import Any

from finraw.qa.comparability import fact_frequency, period_label
from finraw.qa.store import chunks, json_value


LITERAL_BINDING_KEY = "__literal__"
GRAPH_ROOT_SAMPLING_VERSION = "2"
GRAPH_SCAN_STRATUM_FIELDS = (
    "node_type",
    "source",
    "entity_type",
    "year_bucket",
    "relation_density",
)


def scan_pinned_graph_nodes(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "uninitialized", operation)
    role = _required_text(operation, "role")
    node_type = _required_text(operation, "node_type")
    predicates = [
        "n.kg_build_id = ?",
        "n.node_type = ?",
        "COALESCE(n.is_active, 1) = 1",
    ]
    parameters: list[Any] = [state.kg["kg_build_id"], node_type]
    source_table = operation.get("source_table")
    if source_table:
        predicates.append("n.source_table = ?")
        parameters.append(str(source_table))
    limit = _graph_scan_limit(state, operation)
    evaluation_limit = _graph_evaluation_limit(state, operation)
    rows, audit = _scan_graph_roots(
        state,
        predicates,
        parameters,
        limit=limit,
        evaluation_limit=evaluation_limit,
    )
    state.graph_scan_audit = audit
    state.relation = [
        {
            "roles": {role: _node(dict(row))},
            "graph_node_ids": [str(row["node_id"])],
            "graph_edges": [],
        }
        for row in rows
    ]
    state.candidate_limit = max(
        int(getattr(state, "limit", 0)),
        int(state.policy["max_candidates_per_proposal"])
        * int(state.policy["compiled_scan_multiplier"]),
    )
    state.relation_kind = "graph_rows"


def _graph_scan_limit(state: Any, operation: dict[str, Any]) -> int:
    candidates = (
        (operation, "limit"),
        (state.plan.get("sampling", {}), "graph_scan_rows"),
        (state.policy, "compiled_graph_scan_rows"),
    )
    for container, key in candidates:
        if key in container and container[key] is not None:
            return max(int(container[key]), 0)
    return 5000


def _graph_evaluation_limit(state: Any, operation: dict[str, Any]) -> int:
    candidates = (
        (operation, "evaluation_limit"),
        (state.plan.get("sampling", {}), "graph_evaluation_rows"),
        (state.policy, "compiled_graph_evaluation_rows"),
    )
    for container, key in candidates:
        if key in container and container[key] is not None:
            return max(int(container[key]), 0)
    return 0


def _scan_graph_roots(
    state: Any,
    predicates: list[str],
    parameters: list[Any],
    *,
    limit: int,
    evaluation_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    count_row = state.db.fetchone(
        "SELECT COUNT(*) AS root_count FROM kg_nodes n WHERE "
        + " AND ".join(predicates),
        parameters,
    )
    total_root_count = int(count_row["root_count"] if count_row else 0)
    full_scan = limit == 0
    selection_limit = evaluation_limit if full_scan else limit
    materialize_all = full_scan and selection_limit == 0
    entity_types = _graph_entity_types(state)
    global_heap: list[tuple[int, str, dict[str, Any]]] = []
    stratum_representatives: dict[str, tuple[int, str, dict[str, Any]]] = {}
    stratum_details: dict[str, dict[str, str]] = {}
    stratum_totals: Counter[str] = Counter()
    all_rows: list[dict[str, Any]] = []

    for row in _graph_root_pages(state, predicates, parameters):
        item = dict(row)
        stratum_key, stratum = _graph_root_stratum(item, entity_types)
        stratum_totals[stratum_key] += 1
        stratum_details[stratum_key] = stratum
        if materialize_all:
            all_rows.append(item)
            continue
        score = _graph_root_score(item)
        heap_item = (-score, str(item["node_id"]), item)
        if len(global_heap) < selection_limit:
            heapq.heappush(global_heap, heap_item)
        elif score < -global_heap[0][0]:
            heapq.heapreplace(global_heap, heap_item)
        current = stratum_representatives.get(stratum_key)
        if current is None or (score, str(item["node_id"])) < (
            current[0],
            current[1],
        ):
            stratum_representatives[stratum_key] = (
                score,
                str(item["node_id"]),
                item,
            )

    if materialize_all:
        selected = all_rows
        selection_method = "full"
    else:
        representatives = sorted(
            stratum_representatives.items(),
            key=lambda value: (
                _stable_hash_score("stratum", value[0]),
                value[0],
            ),
        )
        selected = [value[1][2] for value in representatives[:selection_limit]]
        selected_ids = {str(row["node_id"]) for row in selected}
        global_rows = sorted(
            global_heap,
            key=lambda value: (-value[0], value[1]),
        )
        for _, node_id, row in global_rows:
            if len(selected) >= selection_limit:
                break
            if node_id not in selected_ids:
                selected.append(row)
                selected_ids.add(node_id)
        selection_method = (
            "full_scan_deterministic_hash_stratified_evaluation"
            if full_scan
            else "deterministic_hash_stratified"
        )

    selected_strata = Counter(
        _graph_root_stratum(row, entity_types)[0] for row in selected
    )
    stratum_coverage = [
        {
            **stratum_details[key],
            "total_root_count": count,
            "scanned_root_count": count if full_scan else selected_strata.get(key, 0),
            "coverage_rate": (
                1.0 if full_scan or not count else selected_strata.get(key, 0) / count
            ),
            "evaluated_root_count": selected_strata.get(key, 0),
            "evaluation_coverage_rate": (
                selected_strata.get(key, 0) / count if count else 1.0
            ),
        }
        for key, count in sorted(stratum_totals.items())
    ]
    scanned_root_count = total_root_count if full_scan else len(selected)
    evaluated_root_count = len(selected)
    total_stratum_count = len(stratum_totals)
    scanned_stratum_count = sum(bool(value) for value in selected_strata.values())
    return selected, {
        "scan_mode": "full" if full_scan else "bounded",
        "selection_method": selection_method,
        "sampling_version": GRAPH_ROOT_SAMPLING_VERSION,
        "configured_limit": limit,
        "configured_evaluation_limit": evaluation_limit,
        "stratum_dimensions": list(GRAPH_SCAN_STRATUM_FIELDS),
        "total_root_count": total_root_count,
        "scanned_root_count": scanned_root_count,
        "root_coverage_rate": (
            scanned_root_count / total_root_count if total_root_count else 1.0
        ),
        "evaluated_root_count": evaluated_root_count,
        "evaluation_coverage_rate": (
            evaluated_root_count / total_root_count if total_root_count else 1.0
        ),
        "total_stratum_count": total_stratum_count,
        "scanned_stratum_count": scanned_stratum_count,
        "stratum_coverage_rate": (
            scanned_stratum_count / total_stratum_count if total_stratum_count else 1.0
        ),
        "stratum_coverage": stratum_coverage,
    }


def _graph_root_pages(
    state: Any,
    predicates: list[str],
    parameters: list[Any],
    *,
    page_size: int = 2000,
) -> Any:
    cursor: str | None = None
    while True:
        page_predicates = list(predicates)
        page_parameters = list(parameters)
        if cursor is not None:
            page_predicates.append("n.node_id > ?")
            page_parameters.append(cursor)
        rows = state.db.fetchall(
            "SELECT n.node_id, n.stable_node_id, n.node_type, "
            "n.source_table, n.source_pk, n.properties_json "
            "FROM kg_nodes n WHERE "
            + " AND ".join(page_predicates)
            + " ORDER BY n.node_id LIMIT ?",
            (*page_parameters, page_size),
        )
        if not rows:
            break
        node_ids = [str(row["node_id"]) for row in rows]
        placeholders = ",".join("?" for _ in node_ids)
        density_rows = state.db.fetchall(
            "SELECT e.src_node_id, COUNT(*) AS relation_density "
            "FROM kg_edges e WHERE e.kg_build_id = ? "
            f"AND e.src_node_id IN ({placeholders}) "
            "AND COALESCE(e.is_active, 1) = 1 GROUP BY e.src_node_id",
            (state.kg["kg_build_id"], *node_ids),
        )
        density_by_node = {
            str(row["src_node_id"]): int(row["relation_density"] or 0)
            for row in density_rows
        }
        for row in rows:
            item = dict(row)
            item["relation_density"] = density_by_node.get(str(item["node_id"]), 0)
            yield item
        cursor = str(rows[-1]["node_id"])
        if len(rows) < page_size:
            break


def _graph_root_stratum(
    row: dict[str, Any],
    entity_types: dict[str, str] | None = None,
) -> tuple[str, dict[str, str]]:
    properties = json_value(row.get("properties_json"), {})
    source = str(
        properties.get("source_id")
        or properties.get("scope_source")
        or row.get("source_table")
        or "unknown"
    )
    entity_type = str(
        properties.get("entity_type")
        or (entity_types or {}).get(str(properties.get("entity_id") or ""))
        or properties.get("financial_scope_type")
        or "unknown"
    )
    year = _graph_root_year(properties)
    year_bucket = (
        f"{(year // 5) * 5}-{(year // 5) * 5 + 4}" if year is not None else "unknown"
    )
    density = int(row.get("relation_density") or 0)
    stratum = {
        "node_type": str(row.get("node_type") or "unknown"),
        "source": source,
        "entity_type": entity_type,
        "year_bucket": year_bucket,
        "relation_density": _relation_density_bucket(density),
    }
    return json.dumps(stratum, sort_keys=True, separators=(",", ":")), stratum


def _graph_entity_types(state: Any) -> dict[str, str]:
    entity_build_id = state.kg.get("input_entity_build_id")
    if not entity_build_id:
        return {}
    rows = state.db.fetchall(
        "SELECT entity_id, entity_type FROM canonical_entities "
        "WHERE build_id = ? AND COALESCE(is_active, 1) = 1",
        (entity_build_id,),
    )
    return {
        str(row["entity_id"]): str(row["entity_type"] or "unknown")
        for row in rows
        if row["entity_id"]
    }


def _graph_root_year(properties: dict[str, Any]) -> int | None:
    time_scope = json_value(properties.get("time_scope"), {})
    values = [
        properties.get("calendar_year"),
        properties.get("fiscal_year"),
        properties.get("year"),
        properties.get("period_end"),
        properties.get("as_of_date"),
        time_scope.get("year"),
        time_scope.get("derived_year"),
        time_scope.get("end_year"),
        time_scope.get("period_end"),
    ]
    for value in values:
        match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", str(value or ""))
        if match:
            return int(match.group(1))
    return None


def _relation_density_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    if value <= 3:
        return "2-3"
    if value <= 7:
        return "4-7"
    if value <= 15:
        return "8-15"
    return "16+"


def _stable_hash_score(*parts: Any) -> int:
    payload = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest(), 16)


def _graph_root_score(row: dict[str, Any]) -> int:
    stable_identity = str(
        row.get("stable_node_id") or f"{row.get('source_table')}:{row.get('source_pk')}"
    )
    return _stable_hash_score(GRAPH_ROOT_SAMPLING_VERSION, stable_identity)


def expand_graph_edges(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "graph_rows", operation)
    from_role = _required_text(operation, "from_role")
    to_role = _required_text(operation, "to_role")
    relations = operation.get("relations") or [operation.get("relation")]
    relation_types = [str(value) for value in relations if value]
    if not relation_types:
        raise ValueError("expand_graph_edges requires relation or relations")
    direction = str(operation.get("direction") or "out")
    if direction not in {"out", "in"}:
        raise ValueError("expand_graph_edges direction must be out or in")
    mode = str(operation.get("mode") or "one")
    if mode not in {"one", "collect"}:
        raise ValueError("expand_graph_edges mode must be one or collect")
    required = bool(operation.get("required", True))
    expected_types = {
        str(value)
        for value in operation.get("to_node_types")
        or ([operation["to_node_type"]] if operation.get("to_node_type") else [])
    }

    source_ids = sorted(
        {
            str(node["node_id"])
            for row in state.relation
            for node in _role_nodes(row, from_role)
        }
    )
    matches: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    source_column = "src_node_id" if direction == "out" else "dst_node_id"
    target_column = "dst_node_id" if direction == "out" else "src_node_id"
    for batch in chunks(source_ids, 500):
        source_placeholders = ",".join("?" for _ in batch)
        relation_placeholders = ",".join("?" for _ in relation_types)
        rows = state.db.fetchall(
            f"SELECT e.edge_id, e.stable_edge_id, e.src_node_id, e.dst_node_id, "
            f"e.relation_type, n.node_id, n.stable_node_id, n.node_type, "
            f"n.source_table, n.source_pk, n.properties_json "
            f"FROM kg_edges e JOIN kg_nodes n ON n.kg_build_id = e.kg_build_id "
            f"AND n.node_id = e.{target_column} "
            f"WHERE e.kg_build_id = ? AND e.{source_column} IN ({source_placeholders}) "
            f"AND e.relation_type IN ({relation_placeholders}) "
            "AND COALESCE(e.is_active, 1) = 1 "
            "AND COALESCE(n.is_active, 1) = 1 "
            f"ORDER BY e.{source_column}, e.relation_type, e.edge_id",
            [state.kg["kg_build_id"], *batch, *relation_types],
        )
        for raw in rows:
            item = dict(raw)
            node = _node(item)
            if expected_types and str(node["node_type"]) not in expected_types:
                continue
            edge = {
                "edge_id": str(item["edge_id"]),
                "src_node_id": str(item["src_node_id"]),
                "dst_node_id": str(item["dst_node_id"]),
                "relation_type": str(item["relation_type"]),
            }
            matches[str(item[source_column])].append((edge, node))

    expanded: list[dict[str, Any]] = []
    for row in state.relation:
        selected = [
            match
            for source in _role_nodes(row, from_role)
            for match in matches.get(str(source["node_id"]), [])
        ]
        minimum_related = int(operation.get("minimum_related") or 1)
        maximum_related = int(operation.get("maximum_related") or 0)
        if selected and (
            len(selected) < minimum_related
            or (maximum_related and len(selected) > maximum_related)
        ):
            continue
        if not selected:
            if not required:
                copied = _copy_graph_row(row)
                copied["roles"][to_role] = [] if mode == "collect" else None
                expanded.append(copied)
            continue
        if mode == "collect":
            copied = _copy_graph_row(row)
            copied["roles"][to_role] = _unique_nodes(node for _, node in selected)
            _extend_evidence(copied, selected)
            expanded.append(copied)
        else:
            for edge, node in selected:
                copied = _copy_graph_row(row)
                copied["roles"][to_role] = node
                _extend_evidence(copied, [(edge, node)])
                expanded.append(copied)
    state.relation = expanded[: state.candidate_limit]
    state.relation_kind = "graph_rows"


def filter_graph_role(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "graph_rows", operation)
    role = _required_text(operation, "role")
    predicates = list(operation.get("predicates") or [])
    if not predicates:
        raise ValueError("filter_graph_role requires predicates")
    required = bool(operation.get("required", True))
    filtered: list[dict[str, Any]] = []
    for row in state.relation:
        original = row.get("roles", {}).get(role)
        nodes = [
            node for node in _role_nodes(row, role) if _node_matches(node, predicates)
        ]
        if not nodes and required:
            continue
        copied = _copy_graph_row(row)
        copied["roles"][role] = (
            nodes if isinstance(original, list) else (nodes[0] if nodes else None)
        )
        filtered.append(copied)
    state.relation = filtered[: state.candidate_limit]
    state.relation_kind = "graph_rows"


def deduplicate_graph_role(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "graph_rows", operation)
    role = _required_text(operation, "role")
    keys = [str(value) for value in operation.get("keys") or []]
    selection = str(operation.get("selection") or "min_source_pk")
    if not keys or selection != "min_source_pk":
        raise ValueError(
            "deduplicate_graph_role requires keys and min_source_pk selection"
        )
    accepted: list[dict[str, Any]] = []
    for row in state.relation:
        original = row.get("roles", {}).get(role)
        grouped = _nodes_by_key(row, role, keys)
        if not grouped:
            continue
        selected = [
            min(
                nodes,
                key=lambda node: (
                    str(node.get("source_pk") or ""),
                    str(node.get("node_id") or ""),
                ),
            )
            for _, nodes in sorted(grouped.items(), key=lambda item: str(item[0]))
        ]
        copied = _copy_graph_row(row)
        copied["roles"][role] = selected if isinstance(original, list) else selected[0]
        copied.setdefault("join_metadata", {})[
            str(operation.get("dedup_id") or f"deduplicate_{role}")
        ] = {
            "relation": "deduplicate",
            "role": role,
            "keys": keys,
            "selection": selection,
            "input_count": sum(len(nodes) for nodes in grouped.values()),
            "selected_count": len(selected),
        }
        accepted.append(copied)
    state.relation = accepted[: state.candidate_limit]
    state.relation_kind = "graph_rows"


def require_graph_roles_contiguous(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "graph_rows", operation)
    roles = [str(value) for value in operation.get("roles") or []]
    group_keys = [str(value) for value in operation.get("group_keys") or []]
    period_key = _required_text(operation, "period_key")
    minimum = max(int(operation.get("minimum_observations") or 2), 2)
    if not roles or not group_keys:
        raise ValueError("require_graph_roles_contiguous requires roles and group_keys")
    accepted: list[dict[str, Any]] = []
    for row in state.relation:
        role_periods: dict[str, dict[tuple[Any, ...], set[int]]] = {}
        valid = True
        for role in roles:
            grouped: dict[tuple[Any, ...], set[int]] = defaultdict(set)
            for node in _role_nodes(row, role):
                group = tuple(_node_value(node, key) for key in group_keys)
                try:
                    period = int(_node_value(node, period_key))
                except (TypeError, ValueError):
                    valid = False
                    break
                if any(value in {None, ""} for value in group):
                    valid = False
                    break
                grouped[group].add(period)
            if not valid or not grouped:
                valid = False
                break
            if any(
                len(periods) < minimum
                or sorted(periods) != list(range(min(periods), max(periods) + 1))
                for periods in grouped.values()
            ):
                valid = False
                break
            role_periods[role] = grouped
        if not valid:
            continue
        group_sets = [set(grouped) for grouped in role_periods.values()]
        if any(groups != group_sets[0] for groups in group_sets[1:]):
            continue
        if any(
            role_periods[role][group] != role_periods[roles[0]][group]
            for role in roles[1:]
            for group in group_sets[0]
        ):
            continue
        copied = _copy_graph_row(row)
        copied.setdefault("join_metadata", {})[
            str(operation.get("constraint_id") or "roles_contiguous")
        ] = {
            "relation": "contiguous",
            "roles": roles,
            "period_key": period_key,
            "minimum_observations": minimum,
        }
        accepted.append(copied)
    state.relation = accepted[: state.candidate_limit]
    state.relation_kind = "graph_rows"


def assert_role_key_equal(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "graph_rows", operation)
    roles = [str(value) for value in operation.get("roles") or []]
    keys = [str(value) for value in operation.get("keys") or []]
    if len(roles) < 2 or not keys:
        raise ValueError("assert_role_key_equal requires at least two roles and keys")
    use_intersection = bool(operation.get("intersection", False))
    minimum_common = max(int(operation.get("minimum_common") or 1), 1)
    accepted: list[dict[str, Any]] = []
    for row in state.relation:
        keyed = {role: _nodes_by_key(row, role, keys) for role in roles}
        if any(not values for values in keyed.values()):
            continue
        key_sets = [set(values) for values in keyed.values()]
        common = set.intersection(*key_sets)
        if len(common) < minimum_common:
            continue
        if not use_intersection and any(
            values != key_sets[0] for values in key_sets[1:]
        ):
            continue
        selected_keys = common if use_intersection else key_sets[0]
        if any(
            any(len(keyed[role][key]) != 1 for key in selected_keys) for role in roles
        ):
            continue
        copied = _copy_graph_row(row)
        for role in roles:
            original = row.get("roles", {}).get(role)
            nodes = [keyed[role][key][0] for key in sorted(selected_keys, key=str)]
            copied["roles"][role] = nodes if isinstance(original, list) else nodes[0]
        copied.setdefault("join_metadata", {})[
            str(operation.get("join_id") or "role_key_equal")
        ] = {
            "relation": "equal",
            "roles": roles,
            "keys": keys,
            "matched_key_count": len(selected_keys),
            "intersection": use_intersection,
        }
        accepted.append(copied)
    state.relation = accepted[: state.candidate_limit]
    state.relation_kind = "graph_rows"


def assert_role_key_relation(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "graph_rows", operation)
    left_role = _required_text(operation, "left_role")
    right_role = _required_text(operation, "right_role")
    match_keys = [str(value) for value in operation.get("match_keys") or []]
    period_key = _required_text(operation, "key")
    relation = str(operation.get("relation") or "")
    distance = int(operation.get("value") or 1)
    if relation != "previous_by" or distance <= 0 or not match_keys:
        raise ValueError(
            "assert_role_key_relation supports previous_by with match_keys"
        )
    accepted: list[dict[str, Any]] = []
    for row in state.relation:
        left = _period_nodes_by_group(row, left_role, match_keys, period_key)
        right = _period_nodes_by_group(row, right_role, match_keys, period_key)
        common_groups = sorted(set(left) & set(right), key=str)
        if not common_groups:
            continue
        available_periods = [
            {
                period
                for period in left[group]
                if period - distance in right[group]
                and len(left[group][period]) == 1
                and len(right[group][period - distance]) == 1
            }
            for group in common_groups
        ]
        shared_periods = (
            set.intersection(*available_periods) if available_periods else set()
        )
        if not shared_periods:
            continue
        selected_period = max(shared_periods)
        left_nodes = [left[group][selected_period][0] for group in common_groups]
        right_nodes = [
            right[group][selected_period - distance][0] for group in common_groups
        ]
        copied = _copy_graph_row(row)
        copied["roles"][left_role] = left_nodes
        copied["roles"][right_role] = right_nodes
        copied.setdefault("join_metadata", {})[
            str(operation.get("join_id") or "period_relation")
        ] = {
            "relation": relation,
            "distance": distance,
            "selected_period": selected_period,
            "group_count": len(common_groups),
        }
        accepted.append(copied)
    state.relation = accepted[: state.candidate_limit]
    state.relation_kind = "graph_rows"


def require_role_coverage(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "graph_rows", operation)
    scope_role = _required_text(operation, "scope_role")
    fact_roles = [str(value) for value in operation.get("fact_roles") or []]
    coverage = float(operation.get("coverage", 1.0))
    if not fact_roles or coverage != 1.0:
        raise ValueError("require_role_coverage currently requires exact 1.0 coverage")
    entity_source = str(operation.get("scope_entity_source") or "source_pk")
    fact_entity_source = str(
        operation.get("fact_entity_source") or "properties.entity_id"
    )
    accepted: list[dict[str, Any]] = []
    for row in state.relation:
        expected = {
            str(_node_value(node, entity_source))
            for node in _role_nodes(row, scope_role)
            if _node_value(node, entity_source) not in {None, ""}
        }
        represented = {
            role: {
                str(_node_value(node, fact_entity_source))
                for node in _role_nodes(row, role)
                if _node_value(node, fact_entity_source) not in {None, ""}
            }
            for role in fact_roles
        }
        if expected and all(values == expected for values in represented.values()):
            copied = _copy_graph_row(row)
            copied["scope_coverage"] = {
                "expected_entity_ids": sorted(expected),
                "represented_entity_ids": {
                    key: sorted(value) for key, value in represented.items()
                },
                "coverage": 1.0,
            }
            accepted.append(copied)
    state.relation = accepted[: state.candidate_limit]
    state.relation_kind = "graph_rows"


def project_graph_binding_v2(state: Any, operation: dict[str, Any]) -> None:
    if not operation.get("role_bindings"):
        raise ValueError("project_graph_binding_v2 requires role_bindings")
    if not operation.get("query_graph_hash"):
        raise ValueError("project_graph_binding_v2 requires query_graph_hash")
    enriched = {**operation, "projection_version": 2}
    project_graph_binding(state, enriched)


def _node_matches(node: dict[str, Any], predicates: list[dict[str, Any]]) -> bool:
    operators = {
        "eq": lambda left, right: left == right,
        "ne": lambda left, right: left != right,
        "in": lambda left, right: left in right,
        "not_in": lambda left, right: left not in right,
        "exists": lambda left, right: (left is not None) is bool(right),
        "truthy": lambda left, right: bool(left) is bool(right),
        "gt": lambda left, right: left is not None and left > right,
        "gte": lambda left, right: left is not None and left >= right,
        "lt": lambda left, right: left is not None and left < right,
        "lte": lambda left, right: left is not None and left <= right,
    }
    for predicate in predicates:
        operator = str(predicate.get("operator") or "")
        if operator not in operators:
            raise ValueError(f"Unsupported graph role predicate operator: {operator}")
        left = _node_value(node, str(predicate.get("field") or ""))
        right = predicate.get("value")
        if operator in {"in", "not_in"} and not isinstance(right, (list, tuple, set)):
            raise ValueError(f"Graph role predicate {operator} requires a collection")
        try:
            passed = operators[operator](left, right)
        except TypeError:
            passed = False
        if not passed:
            return False
    return True


def _nodes_by_key(
    row: dict[str, Any], role: str, keys: list[str]
) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    output: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for node in _role_nodes(row, role):
        key = tuple(_node_value(node, field) for field in keys)
        if all(value not in {None, ""} for value in key):
            output[key].append(node)
    return output


def _period_nodes_by_group(
    row: dict[str, Any], role: str, match_keys: list[str], period_key: str
) -> dict[tuple[Any, ...], dict[int, list[dict[str, Any]]]]:
    output: dict[tuple[Any, ...], dict[int, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for node in _role_nodes(row, role):
        group = tuple(_node_value(node, field) for field in match_keys)
        raw_period = _node_value(node, period_key)
        try:
            period = int(raw_period)
        except (TypeError, ValueError):
            continue
        if all(value not in {None, ""} for value in group):
            output[group][period].append(node)
    return output


def project_graph_binding(state: Any, operation: dict[str, Any]) -> None:
    _expect(state, "graph_rows", operation)
    fact_roles = [str(value) for value in operation.get("fact_roles") or []]
    if not fact_roles:
        raise ValueError("project_graph_binding requires fact_roles")
    all_fact_ids = sorted(
        {
            str(node.get("source_pk"))
            for row in state.relation
            for role in fact_roles
            for node in _role_nodes(row, role)
            if node.get("source_pk")
        }
    )
    fact_map, metrics = _load_facts(state, all_fact_ids)
    state.facts = list(fact_map.values())
    state.metrics = metrics

    answer_spec = dict(operation.get("answer") or {})
    answer_binding = str(answer_spec.get("binding") or "graph_answer")
    candidates: list[dict[str, Any]] = []
    for row in state.relation:
        fact_ids = sorted(
            {
                str(node.get("source_pk"))
                for role in fact_roles
                for node in _role_nodes(row, role)
                if node.get("source_pk")
            }
        )
        if not fact_ids or any(fact_id not in fact_map for fact_id in fact_ids):
            continue
        facts = [fact_map[fact_id] for fact_id in fact_ids]
        answer = _project_answer(row, answer_spec)
        if not answer:
            continue
        entity_ids = sorted(
            {str(fact["entity_id"]) for fact in facts if fact.get("entity_id")}
            | _source_pks(row, operation.get("entity_roles") or [])
        )
        metric_ids = sorted(
            {str(fact["metric_id"]) for fact in facts if fact.get("metric_id")}
            | _source_pks(row, operation.get("metric_roles") or [])
        )
        input_bindings = {
            answer_binding: {LITERAL_BINDING_KEY: answer},
        }
        if int(operation.get("projection_version") or 1) < 2:
            input_bindings["facts"] = fact_ids
        for binding_name, role_spec in dict(
            operation.get("role_bindings") or {}
        ).items():
            role = str(
                role_spec.get("role") if isinstance(role_spec, dict) else role_spec
            )
            role_fact_ids = sorted(
                {
                    str(node.get("source_pk"))
                    for node in _role_nodes(row, role)
                    if node.get("source_pk")
                }
            )
            if not role_fact_ids or any(
                value not in fact_map for value in role_fact_ids
            ):
                input_bindings = {}
                break
            input_bindings[str(binding_name)] = role_fact_ids
        if not input_bindings:
            continue
        provenance_spec = dict(operation.get("provenance_binding") or {})
        if provenance_spec:
            provenance_binding = str(provenance_spec.get("binding") or "provenance_map")
            input_bindings[provenance_binding] = {
                LITERAL_BINDING_KEY: _project_provenance_map(row, provenance_spec)
            }
        first = facts[0]
        binding = {
            "input_bindings": input_bindings,
            "fact_ids": fact_ids,
            "entity_ids": entity_ids,
            "metric_ids": metric_ids,
            "period": period_label(first),
            "frequency": fact_frequency(first),
            "scope_type": str(operation.get("scope_type") or "graph_topology"),
            "scope_definition": _role_property(
                row, operation.get("scope_role"), "scope_definition"
            ),
            "source_derived_ids": sorted(
                _source_pks(row, operation.get("derived_roles") or [])
            ),
            "source_document_ids": sorted(
                _source_pks(row, operation.get("document_roles") or [])
            ),
            "raw_object_ids": sorted(
                _source_pks(row, operation.get("raw_object_roles") or [])
            ),
            "scope_entity_ids": sorted(
                _source_pks(row, operation.get("entity_roles") or [])
            ),
            "query_graph_hash": operation.get("query_graph_hash"),
            "answer_target": dict(operation.get("answer_target") or {}),
            "projection_version": int(operation.get("projection_version") or 1),
            "walk_binding_trace": _walk_binding_trace(row),
            "join_metadata": dict(row.get("join_metadata") or {}),
            "scope_coverage": dict(row.get("scope_coverage") or {}),
            "evidence_policy": dict(operation.get("evidence_policy") or {}),
            "graph_node_ids": _projected_graph_node_ids(row),
            "graph_edge_ids": sorted(
                {str(edge["edge_id"]) for edge in _projected_walk_edges(row)}
            ),
            "graph_edges": sorted(
                _projected_walk_edges(row),
                key=lambda edge: (
                    str(edge["relation_type"]),
                    str(edge["edge_id"]),
                ),
            ),
        }
        for field_name, projection in dict(operation.get("context") or {}).items():
            binding[str(field_name)] = _project_value(row, projection)
        candidates.append(binding)
    state.discovered_count += len(candidates)
    state.relation = candidates[: state.candidate_limit]
    state.relation_kind = "binding_candidates"


def _project_answer(
    row: dict[str, Any],
    answer_spec: dict[str, Any],
) -> dict[str, Any]:
    role = str(answer_spec.get("role") or "")
    shape = str(answer_spec.get("shape") or "record")
    output_key = str(
        answer_spec.get("output_key") or ("records" if shape == "records" else "trace")
    )
    fields = dict(answer_spec.get("fields") or {})
    if shape == "fact_trace_records":
        return _project_fact_trace_records(row, answer_spec, output_key)
    if shape == "composite":
        record = {
            str(name): _project_value(row, projection)
            for name, projection in fields.items()
        }
        return {output_key: record, "count": 1}
    nodes = _role_nodes(row, role)
    if not nodes:
        return {}
    records = [
        {str(name): _node_value(node, str(source)) for name, source in fields.items()}
        for node in nodes
    ]
    records = sorted(records, key=_digest)
    value: Any = records if shape == "records" else records[0]
    return {output_key: value, "count": len(records)}


def _project_provenance_map(
    row: dict[str, Any], spec: dict[str, Any]
) -> dict[str, list[str]]:
    fact_nodes = {
        str(node["node_id"]): str(node["source_pk"])
        for node in _role_nodes(row, str(spec.get("fact_role") or ""))
        if node.get("source_pk")
    }
    raw_nodes = {
        str(node["node_id"]): str(node["source_pk"])
        for node in _role_nodes(row, str(spec.get("raw_object_role") or ""))
        if node.get("source_pk")
    }
    relation = str(spec.get("relation") or "TRACED_TO")
    output: dict[str, set[str]] = defaultdict(set)
    for edge in row.get("graph_edges") or []:
        if str(edge.get("relation_type")) != relation:
            continue
        src = str(edge.get("src_node_id"))
        dst = str(edge.get("dst_node_id"))
        if src in fact_nodes and dst in raw_nodes:
            output[fact_nodes[src]].add(raw_nodes[dst])
        elif dst in fact_nodes and src in raw_nodes:
            output[fact_nodes[dst]].add(raw_nodes[src])
    return {key: sorted(values) for key, values in sorted(output.items())}


def _walk_binding_trace(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "roles": {
            str(role): [
                {
                    "node_id": str(node["node_id"]),
                    "node_type": str(node["node_type"]),
                    "source_pk": node.get("source_pk"),
                }
                for node in _role_nodes(row, str(role))
            ]
            for role in sorted(row.get("roles") or {})
        },
        "edges": sorted(
            _projected_walk_edges(row),
            key=lambda edge: (
                str(edge.get("relation_type")),
                str(edge.get("src_node_id")),
                str(edge.get("dst_node_id")),
            ),
        ),
    }


def _projected_walk_edges(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep only edges whose endpoints survived role filtering and joins."""
    role_node_ids = {
        str(node.get("node_id"))
        for role in row.get("roles") or {}
        for node in _role_nodes(row, str(role))
        if node.get("node_id")
    }
    return [
        dict(edge)
        for edge in row.get("graph_edges") or []
        if str(edge.get("src_node_id")) in role_node_ids
        and str(edge.get("dst_node_id")) in role_node_ids
    ]


def _projected_graph_node_ids(row: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(node.get("node_id"))
            for role in row.get("roles") or {}
            for node in _role_nodes(row, str(role))
            if node.get("node_id")
        }
    )


def _project_fact_trace_records(
    row: dict[str, Any], spec: dict[str, Any], output_key: str
) -> dict[str, Any]:
    fact_nodes = _role_nodes(row, str(spec.get("fact_role") or ""))
    period_nodes = {
        str(node["node_id"]): node
        for node in _role_nodes(row, str(spec.get("period_role") or ""))
    }
    hierarchy_nodes = {
        str(node["node_id"]): node
        for node in _role_nodes(row, str(spec.get("hierarchy_role") or ""))
    }
    raw_nodes = {
        str(node["node_id"]): node
        for node in _role_nodes(row, str(spec.get("raw_object_role") or ""))
    }
    outgoing: dict[tuple[str, str], set[str]] = defaultdict(set)
    for edge in row.get("graph_edges") or []:
        outgoing[(str(edge.get("src_node_id")), str(edge.get("relation_type")))].add(
            str(edge.get("dst_node_id"))
        )
    records = []
    for fact in fact_nodes:
        fact_node_id = str(fact["node_id"])
        entity_id = _node_value(fact, "properties.entity_id")
        period_ids = outgoing.get((fact_node_id, "IN_PERIOD"), set()) & set(
            period_nodes
        )
        raw_ids = outgoing.get((fact_node_id, "TRACED_TO"), set()) & set(raw_nodes)
        fiscal_ids = {
            hierarchy_id
            for period_id in period_ids
            for hierarchy_id in outgoing.get((period_id, "IN_FISCAL_YEAR"), set())
            if hierarchy_id in hierarchy_nodes
        }
        fiscal_year_values = sorted(
            str(hierarchy_nodes[value].get("source_pk") or value)
            for value in fiscal_ids
        )
        entity_fiscal_year_values = [
            value
            for value in fiscal_year_values
            if entity_id and value.startswith(f"{entity_id}:")
        ]
        if entity_fiscal_year_values:
            fiscal_year_values = entity_fiscal_year_values
        raw_object_values = sorted(
            str(raw_nodes[value].get("source_pk") or value) for value in raw_ids
        )
        records.append(
            {
                "fact_id": fact.get("source_pk"),
                "entity_id": entity_id,
                "metric_id": _node_value(fact, "properties.metric_id"),
                "value": _node_value(fact, "properties.normalized_value"),
                "unit": _node_value(fact, "properties.normalized_unit"),
                "period_ids": sorted(
                    str(period_nodes[value].get("source_pk") or value)
                    for value in period_ids
                ),
                "fiscal_year_ids": fiscal_year_values,
                "fiscal_year": (
                    fiscal_year_values[0].rsplit(":", 1)[-1]
                    if len(fiscal_year_values) == 1
                    else None
                ),
                "raw_object_ids": raw_object_values,
                "raw_object_id": (
                    raw_object_values[0] if len(raw_object_values) == 1 else None
                ),
            }
        )
    records.sort(key=_digest)
    return {output_key: records, "count": len(records)} if records else {}


def _project_value(row: dict[str, Any], projection: Any) -> Any:
    if not isinstance(projection, dict):
        return projection
    role = str(projection.get("role") or "")
    source = str(projection.get("source") or "source_pk")
    values = [_node_value(node, source) for node in _role_nodes(row, role)]
    values = [value for value in values if value is not None]
    if projection.get("many"):
        return sorted(values, key=str)
    return values[0] if values else projection.get("default")


def _load_facts(
    state: Any,
    fact_ids: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    facts: dict[str, dict[str, Any]] = {}
    for batch in chunks(fact_ids, 500):
        placeholders = ",".join("?" for _ in batch)
        rows = state.db.fetchall(
            f"SELECT sf.*, ce.entity_type, ce.market, ce.country, ce.industry, "
            f"m.canonical_name AS metric_name, m.metric_category, "
            f"m.statement_type, m.period_type AS ontology_period_type, "
            f"m.aggregation_rule, m.revision_risk "
            f"FROM standardized_facts sf "
            f"JOIN canonical_entities ce ON ce.build_id = ? "
            f"AND ce.entity_id = sf.entity_id "
            f"JOIN metrics m ON m.build_id = ? AND m.metric_id = sf.metric_id "
            f"WHERE sf.build_id = ? AND sf.fact_id IN ({placeholders}) "
            "AND COALESCE(sf.graph_ready, 0) = 1 "
            "AND COALESCE(sf.is_forecast, 0) = 0",
            [
                state.kg["input_entity_build_id"],
                state.kg["input_metric_build_id"],
                state.kg["input_fact_build_id"],
                *batch,
            ],
        )
        for raw in rows:
            fact = dict(raw)
            fact["graph_ready"] = bool(fact.get("graph_ready"))
            facts[str(fact["fact_id"])] = fact
    metric_ids = sorted(
        {str(fact["metric_id"]) for fact in facts.values() if fact.get("metric_id")}
    )
    metrics: dict[str, dict[str, Any]] = {}
    for batch in chunks(metric_ids, 500):
        placeholders = ",".join("?" for _ in batch)
        rows = state.db.fetchall(
            f"SELECT * FROM metrics WHERE build_id = ? "
            f"AND metric_id IN ({placeholders})",
            [state.kg["input_metric_build_id"], *batch],
        )
        metrics.update({str(row["metric_id"]): dict(row) for row in rows})
    return facts, metrics


def _node(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": str(row["node_id"]),
        "stable_node_id": str(row.get("stable_node_id") or ""),
        "node_type": str(row["node_type"]),
        "source_table": str(row.get("source_table") or ""),
        "source_pk": (
            str(row["source_pk"]) if row.get("source_pk") is not None else None
        ),
        "properties": json_value(row.get("properties_json"), {}),
    }


def _node_value(node: dict[str, Any], source: str) -> Any:
    if source.startswith("properties."):
        value: Any = node.get("properties") or {}
        for part in source.split(".")[1:]:
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value
    return node.get(source)


def _role_nodes(row: dict[str, Any], role: str) -> list[dict[str, Any]]:
    value = row.get("roles", {}).get(role)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return [value] if isinstance(value, dict) else []


def _role_property(row: dict[str, Any], role: Any, property_name: str) -> Any:
    if not role:
        return None
    nodes = _role_nodes(row, str(role))
    return (nodes[0].get("properties") or {}).get(property_name) if nodes else None


def _source_pks(row: dict[str, Any], roles: Any) -> set[str]:
    return {
        str(node["source_pk"])
        for role in roles
        for node in _role_nodes(row, str(role))
        if node.get("source_pk")
    }


def _copy_graph_row(row: dict[str, Any]) -> dict[str, Any]:
    copied = {
        "roles": dict(row["roles"]),
        "graph_node_ids": list(row["graph_node_ids"]),
        "graph_edges": list(row["graph_edges"]),
    }
    for field in ("join_metadata", "scope_coverage"):
        if field in row:
            copied[field] = dict(row[field])
    return copied


def _extend_evidence(
    row: dict[str, Any],
    selected: list[tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    row["graph_edges"].extend(edge for edge, _ in selected)
    row["graph_node_ids"].extend(str(node["node_id"]) for _, node in selected)


def _unique_nodes(nodes: Any) -> list[dict[str, Any]]:
    by_id = {str(node["node_id"]): node for node in nodes}
    return [by_id[node_id] for node_id in sorted(by_id)]


def _required_text(operation: dict[str, Any], field: str) -> str:
    value = str(operation.get(field) or "")
    if not value:
        raise ValueError(f"{operation.get('op')} requires {field}")
    return value


def _expect(state: Any, expected: str, operation: dict[str, Any]) -> None:
    if state.relation_kind != expected:
        raise ValueError(
            f"{operation['op']} expected {expected}, found {state.relation_kind}"
        )


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
