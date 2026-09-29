"""Exact source transition from one final retry to all primary network absences.

Initial generation, funding and single-retry registrations remain immutable.
Only the new registered group may supersede the unactivated single-retry queue.
"""

from pathlib import Path

from .calibration import now
from .contracts import digest
from .storage import read_json
from .v6_collection import bound, persist, require, sha
from .v10_execution_revision import source_maps
from .v10_retry_execution import (
    REVISION_PATH as SINGLE_REVISION_PATH,
)
from .v10_retry_execution import (
    changed_sources as single_changed_sources,
)
from .v10_retry_execution import (
    parent_revision as funding_parent_revision,
)

REVISION_PATH = Path("network_retry_01/execution_revision/record.json")
AUTHORIZATION_PATH = Path("network_retry_01/authorization/record.json")
PARENT_SINGLE_EXECUTION_ID = "4ed277d18fe16d7c811de60946a111b4907ad8b2e4f9c222916db25c1c2fbd95"
AUTHORIZATION = dict(
    initial_request="补发网络异常造成的审阅",
    user_reply="批准上述本批全部网络 UNKNOWN 补发范围",
    question=(
        "请确认撤销此前仅指定1项的未来补发限制：本批原11438项A/B审阅中所有已确认网络UNKNOWN，"
        "含当前24项及原矩阵结束前新增项，待全原矩阵终态后各仅一次attempt2；原指定项并入不重复，"
        "正常返回、旧批、映射不补发，原UNKNOWN和预留保留，按原规则使用结果、不再第三次，"
        "预算仍为2000元总额和1300元审阅映射子额。"
    ),
    scope=(
        "this original 11438 A/B matrix only; one final attempt2 "
        "for every acknowledged primary network absence"
    ),
    timing="after the entire primary matrix; before final joint qualification and mapping",
    supersedes_unactivated_single_queue=True,
    historical_batches_mapping_returned_annotations_and_attempt3_excluded=True,
    original_UNKNOWN_and_holds_preserved=True,
    money_and_request_caps_unchanged=True,
    date="2026-09-29",
)
ALLOWED_CHANGES = {
    "generation": {"v10_budget.py", "v10_generation.py", "v10_review_provider.py"},
    "annotation": {"v10_budget.py", "v10_production.py", "v10_review_provider.py"},
}
EXTRA_SOURCES = (
    "v10_network_retry_execution.py",
    "v10_network_retry.py",
    "v10_material.py",
)


def checked(path):
    value = read_json(path)
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "network retry evidence identity changed",
    )
    return value


def extra_sources():
    root = Path(__file__).parent
    return {name: sha(root / name) for name in EXTRA_SOURCES}


def changed_sources(before, after):
    require(
        set(before) == set(after) == set(ALLOWED_CHANGES), "network retry source scopes changed"
    )
    result = {}
    for scope, allowed in ALLOWED_CHANGES.items():
        require(set(before[scope]) == set(after[scope]), "protected source list cannot change")
        changed = {name for name in before[scope] if before[scope][name] != after[scope][name]}
        require(changed and changed <= allowed, "network retry cannot change policy/scoring/kernel")
        result[scope] = sorted(changed)
    return result


def parent_revision(output, plan):
    output = Path(output)
    funding_revision, funding = funding_parent_revision(output, plan)
    parent = checked(output / SINGLE_REVISION_PATH)
    require(
        parent["id"] == PARENT_SINGLE_EXECUTION_ID
        and parent["protocol_id"] == plan["id"]
        and parent["batch_id"] == plan["batch_id"]
        and parent["policy_id"] == plan["review_policy_id"]
        and parent["funding_execution_revision_id"] == funding_revision["id"]
        and parent["funding_amendment_id"] == funding["id"]
        and parent["initial_sources"] == funding_revision["original_sources"]
        and parent["previous_effective_sources"] == funding_revision["effective_sources"]
        and parent["changed_files"]
        == single_changed_sources(
            parent["previous_effective_sources"], parent["effective_sources"]
        ),
        "prior exact funding and single-retry revisions must remain intact",
    )
    from .v10_retry_execution import AUTHORIZATION_PATH as SINGLE_AUTHORIZATION_PATH

    single_permit = checked(output / SINGLE_AUTHORIZATION_PATH)
    require(
        single_permit["id"] == parent["retry_permit_id"]
        and sha(output / SINGLE_AUTHORIZATION_PATH) == parent["retry_permit_sha256"],
        "original single-retry permission cannot be rewritten",
    )
    root = Path(__file__).parent
    for name, original_sha in parent["additional_source_bindings"].items():
        if name != "v10_material.py":
            require(
                sha(root / name) == original_sha, "prior retry implementation/authority changed"
            )
    return parent, single_permit


def register_network_retry_execution(output):
    output = Path(output).resolve()
    require(not (output / REVISION_PATH).exists(), "network retry source revision already exists")
    plan = checked(output / "registration/protocol.json")
    parent, single_permit = parent_revision(output, plan)
    permit = checked(output / AUTHORIZATION_PATH)
    require(
        permit.get("superseded_single_permit_id") == single_permit["id"]
        and permit.get("authorization", {}).get("user_reply") == AUTHORIZATION["user_reply"],
        "the expanded queue must explicitly supersede this preserved single permission",
    )
    from .v10_generation import ledger_for
    from .v10_network_retry import read_network_retry_permit

    ledger = ledger_for(plan)
    require(
        read_network_retry_permit(ledger) == permit,
        "group artifact must match real wallet authority",
    )
    state = ledger.snapshot()
    require(
        not state["pending_requests"]
        and not state["unacknowledged_unknown_requests"]
        and not state["halt"]
        and not (output / "final_retry_01/activation/record.json").exists()
        and not (output / "review_seal/record.json").exists()
        and not (output / "mapping_registration/record.json").exists(),
        "register the expanded future queue while drained, before prior retry/joint/mapping",
    )
    after = source_maps()
    record = bound(
        dict(
            schema="v10_primary_network_retry_execution_revision.v1",
            at=now(),
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            policy_id=plan["review_policy_id"],
            authorization=AUTHORIZATION,
            previous_execution_revision_id=parent["id"],
            previous_execution_revision_sha256=sha(output / SINGLE_REVISION_PATH),
            preserved_single_permit_id=single_permit["id"],
            network_retry_permit_id=permit["id"],
            network_retry_permit_sha256=sha(output / AUTHORIZATION_PATH),
            initial_sources=parent["initial_sources"],
            previous_effective_sources=parent["effective_sources"],
            effective_sources=after,
            changed_files=changed_sources(parent["effective_sources"], after),
            additional_source_bindings=extra_sources(),
            preserved_requests_before_resume=state["requests_reserved"],
            original_matrix_denominator=11438,
            eligible_target_count=None,
            target_set_frozen_once_after_all_primary_terminals=True,
            original_UNKNOWN_and_holds_preserved=True,
            max_attempt_index=2,
            no_returned_annotation_resampling=True,
            scoring_masks_policy_and_five_arms_unchanged=True,
        )
    )
    persist((output / REVISION_PATH).parent, record)
    return record


def validate_network_retry_source_transition(output, plan, *, scope, original, current):
    output = Path(output).resolve()
    record = checked(output / REVISION_PATH)
    parent, single_permit = parent_revision(output, plan)
    permit = checked(output / AUTHORIZATION_PATH)
    require(
        record["schema"] == "v10_primary_network_retry_execution_revision.v1"
        and record["protocol_id"] == plan["id"]
        and record["batch_id"] == plan["batch_id"]
        and record["policy_id"] == plan["review_policy_id"]
        and record["authorization"] == AUTHORIZATION
        and record["previous_execution_revision_id"] == parent["id"]
        and record["previous_execution_revision_sha256"] == sha(output / SINGLE_REVISION_PATH)
        and record["preserved_single_permit_id"] == single_permit["id"]
        and record["network_retry_permit_id"] == permit["id"]
        and permit.get("superseded_single_permit_id") == single_permit["id"]
        and permit.get("authorization", {}).get("user_reply") == AUTHORIZATION["user_reply"]
        and record["network_retry_permit_sha256"] == sha(output / AUTHORIZATION_PATH)
        and record["initial_sources"] == parent["initial_sources"]
        and record["initial_sources"][scope] == original
        and record["previous_effective_sources"] == parent["effective_sources"]
        and record["effective_sources"][scope] == current
        and record["effective_sources"] == source_maps()
        and record["additional_source_bindings"] == extra_sources()
        and record["changed_files"]
        == changed_sources(record["previous_effective_sources"], record["effective_sources"]),
        "only the exact registered primary-network retry implementation may resume",
    )
    return record
