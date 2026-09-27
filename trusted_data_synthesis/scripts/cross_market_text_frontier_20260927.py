"""Pure composition-review frontier under the original PDF panel selection order.

No file I/O, model call, review creation or semantic promotion occurs here.
Eligibility excludes ONLY the existing nonsemantic identity/public-view failures.
Missing review evidence remains optimistic pending, never an implicit rejection.
"""

from collections import Counter, defaultdict

import cross_market_panel_20260926 as panel

base = panel.base
SCRIPT = "trusted_data_synthesis/scripts/cross_market_text_frontier_20260927.py"
GROUP = "composition_required"
QUOTA = panel.QUOTAS[GROUP]


def require(condition, reason):
    base.require(condition, "text_frontier." + reason)


def eligible_items(candidates, documents, mapping, metric_universe):
    """Return (items, preflight_rejections), not admitted or reviewed tasks.

    The original issuer join, complete public-window projection, ambiguity rule and
latest-publication/raw-object rank are reused verbatim for all three groups.
No financial facts are requalified. Composition source-review gates stay pending.
    """
    facts = {row["fact_id"]: row for doc in documents.values() for row in doc["qualified_facts"]}
    document_facts = {key: row["qualified_facts"] for key, row in documents.items()}
    accepted, rejected = {}, []
    for task in candidates:
        try:
            panel.require(task["group"] in panel.GROUPS and task["quantity"] in panel.QUANTITIES,
                          "registered_task_structure")
            panel.require(set(task["fact_ids"]) <= set(facts), "task_fact_join")
            issuer = panel.issuer_join(task, documents, mapping)
            spec = panel.public_spec(task, issuer, documents)
            public, visible = panel.public_sources(spec, document_facts, metric_universe)
            panel.require(
                set(task["fact_ids"]) <= {row["fact_id"] for row in visible},
                "target_facts_not_all_public",
            )
            rank = tuple(
                sorted(
                    (facts[key]["source_publish_date"], facts[key]["raw_object_id"])
                    for key in task["fact_ids"]
                )
            )
            item = dict(task=task, spec=spec, public=public, visible=visible, rank=rank)
            previous = accepted.get(spec["task_id"])
            if previous is None or (rank, task["security_id"], task["task_id"]) > (
                previous["rank"],
                previous["task"]["security_id"],
                previous["task"]["task_id"],
            ):
                accepted[spec["task_id"]] = item
        except (ValueError, KeyError, TypeError) as error:
            rejected.append(
                dict(
                    candidate_task_id=task.get("task_id"),
                    group=task.get("group"),
                    reason=str(error),
                )
            )
    return list(accepted.values()), rejected


def ordered(items):
    """Original issuer-hash round robin, then actual endperiod/public task ID."""
    items = list(items)
    require(
        all(item["task"]["group"] == item["spec"]["group"] == GROUP for item in items),
        "composition_items_only",
    )
    require(
        len({item["task"]["task_id"] for item in items}) == len(items)
        and len({item["spec"]["task_id"] for item in items}) == len(items),
        "unique_candidate_and_public_target_ids",
    )
    buckets = defaultdict(list)
    for item in items:
        buckets[item["spec"]["issuer_cluster_id"]].append(item)
    for rows in buckets.values():
        rows.sort(key=lambda item: (item["task"]["periods"][-1][1], item["spec"]["task_id"]))
    issuers = sorted(buckets, key=lambda cluster: base.sha(panel.SALT + cluster))
    result, offset = [], 0
    while any(offset < len(buckets[key]) for key in issuers):
        result.extend(buckets[key][offset] for key in issuers if offset < len(buckets[key]))
        offset += 1
    return result


def explicit_ids(values, universe, name):
    require(
        isinstance(values, (list, tuple, set, frozenset))
        and all(isinstance(value, str) and bool(value) for value in values),
        name + "_explicit_ID_collection",
    )
    require(
        len(values) == len(set(values)) and set(values) <= universe,
        name + "_unique_known_candidate_IDs",
    )
    return set(values)


def next_selected(items, rejected_task_ids):
    """Optimistic original next60 after ONLY explicit, externally validated rejects.

    Rebuild buckets after rejections: filtering a previously interleaved global list
    would incorrectly advance later issuers ahead of an earlier issuer's next task.
    """
    items = ordered(items)
    universe = {item["task"]["task_id"] for item in items}
    rejected = explicit_ids(rejected_task_ids, universe, "rejected")
    return ordered(item for item in items if item["task"]["task_id"] not in rejected)[:QUOTA]


def closure(items, reviews):
    """Selection-order closure only, over explicit already-validated verdict IDs.

    Input contract: {passed_task_ids: [...], rejected_task_ids: [...]}. The caller
    MUST derive these sets from genuine content-bound reviews, not provider HTTP or
    locator schema success. This helper neither creates nor validates a semantic
    certificate. Missing IDs remain pending even if another sixty have passed.
    """
    require(
        isinstance(reviews, dict) and set(reviews) == {"passed_task_ids", "rejected_task_ids"},
        "explicit_pass_and_reject_sets_required",
    )
    items = ordered(items)
    universe = {item["task"]["task_id"] for item in items}
    passed = explicit_ids(reviews["passed_task_ids"], universe, "passed")
    rejected = explicit_ids(reviews["rejected_task_ids"], universe, "rejected")
    require(not passed & rejected, "contradictory_review_verdicts")
    optimistic = next_selected(items, rejected)
    optimistic_ids = [item["task"]["task_id"] for item in optimistic]
    pending = [task_id for task_id in optimistic_ids if task_id not in passed]
    closed = len(optimistic) == QUOTA and not pending
    status = (
        "SELECTION_CLOSED_FIXED_SIXTY"
        if closed
        else (
            "PREDECLARED_POOL_EXHAUSTED_BELOW_QUOTA"
            if len(optimistic) < QUOTA
            else "PENDING_EARLIER_OPTIMISTIC_CANDIDATES"
        )
    )
    return dict(
        status=status,
        closed=closed,
        quota=QUOTA,
        preflight_candidate_count=len(items),
        explicit_pass_count=len(passed),
        explicit_reject_count=len(rejected),
        optimistic_task_ids=optimistic_ids,
        pending_task_ids=pending,
        selected_task_ids=optimistic_ids if closed else [],
        selected_public_task_ids=[item["spec"]["task_id"] for item in optimistic] if closed else [],
        optimistic_issuer_counts=dict(
            Counter(item["spec"]["issuer_cluster_id"] for item in optimistic)
        ),
        explicit_rejected_task_ids=sorted(rejected),
        passed_outside_optimistic_frontier=sorted(passed - set(optimistic_ids)),
        caller_must_validate_original_review_evidence=True,
        semantic_certificate_created=False,
        missing_review_is_not_rejection=True,
    )
