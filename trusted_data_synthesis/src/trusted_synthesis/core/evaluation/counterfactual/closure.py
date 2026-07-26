from __future__ import annotations

from collections import defaultdict, deque

from trusted_synthesis.core.evaluation.contracts.schema import QualityContract


def failure_closure(
    contract: QualityContract,
    root_clause_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Return roots and every transitively blocked dependent clause."""

    known = {item.clause_id for item in contract.clauses}
    unknown = set(root_clause_ids) - known
    if unknown:
        raise ValueError(f"failure closure received unknown clauses: {sorted(unknown)}")
    dependents: dict[str, list[str]] = defaultdict(list)
    order = {item.clause_id: index for index, item in enumerate(contract.clauses)}
    for clause in contract.clauses:
        for dependency in clause.dependencies:
            dependents[dependency].append(clause.clause_id)
    seen = set(root_clause_ids)
    queue = deque(root_clause_ids)
    while queue:
        current = queue.popleft()
        for dependent in dependents.get(current, ()):
            if dependent in seen:
                continue
            seen.add(dependent)
            queue.append(dependent)
    return tuple(sorted(seen, key=order.__getitem__))


def resolve_root_clause(
    contract: QualityContract,
    source_clause_id: str,
    root_clause_kind: str | None,
) -> str:
    source = next(
        (item for item in contract.clauses if item.clause_id == source_clause_id),
        None,
    )
    if source is None:
        raise ValueError(f"unknown source clause: {source_clause_id}")
    if root_clause_kind is None or root_clause_kind == source.clause_kind:
        return source.clause_id
    matches = tuple(
        item
        for item in contract.clauses
        if item.clause_kind == root_clause_kind
        and item.target.target_ref == source.target.target_ref
    )
    if len(matches) != 1:
        raise ValueError(
            "mutation root clause is not uniquely resolvable: "
            f"kind={root_clause_kind}, target={source.target.target_ref}, matches={len(matches)}"
        )
    return matches[0].clause_id
