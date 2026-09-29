"""Exact second source transition for the single authorized final UNKNOWN retry.

The already applied funding revision and all initial registrations are preserved.
This exception covers one known absent response, never general retry permission.
"""

from pathlib import Path

from .calibration import now
from .contracts import digest
from .storage import read_json
from .v6_collection import bound, persist, require, sha
from .v10_execution_revision import (
    FUNDING_PATH,
    HISTORICAL_PATHS,
    source_maps,
)
from .v10_execution_revision import (
    REVISION_PATH as FUNDING_REVISION_PATH,
)
from .v10_execution_revision import (
    _check_maps as check_funding_maps,
)
from .v10_execution_revision import (
    extra_sources as funding_extra_sources,
)

REVISION_PATH = Path("final_retry_01/execution_revision/record.json")
AUTHORIZATION_PATH = Path("final_retry_01/authorization/record.json")
PARENT_FUNDING_EXECUTION_ID = "9156611ff4a06c74d6cbd76e0052823a46aca03ac926230ea791bdc55e7269b2"
PARENT_FUNDING_RECEIPT_ID = "b0660a06ea1e70f53f961c9d892857266c6c41f42749b145d2e3c35a3bfe74a9"
AUTHORIZATION = dict(
    question=(
        "“最后一轮重发”是否按以下范围执行：当前固定矩阵结束后，仅对此次停派期间的 "
        "1 项 UNKNOWN 补发一次；保留原 UNKNOWN 和全部预留，用预先登记的补发返回决定"
        "该槽位最终资格，不择优；补发若仍失败就不再重试，其他 UNKNOWN 不自动扩展？"
    ),
    user_reply="按此范围最后补发一次",
    date="2026-09-29",
)
ALLOWED_CHANGES = {
    "generation": {
        "probe_budget.py",
        "v10_budget.py",
        "v10_generation.py",
        "v10_review_provider.py",
    },
    "annotation": {
        "probe_budget.py",
        "v10_budget.py",
        "v10_production.py",
        "v10_review_provider.py",
    },
}
EXTRA_SOURCES = ("v10_retry_execution.py", "v10_final_retry.py", "v10_material.py")


def checked(path):
    value = read_json(path)
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "single final retry evidence identity changed",
    )
    return value


def extra_sources():
    root = Path(__file__).parent
    return {name: sha(root / name) for name in EXTRA_SOURCES}


def changed_sources(before, after):
    require(set(before) == set(after) == set(ALLOWED_CHANGES), "retry source scopes differ")
    result = {}
    for scope, allowed in ALLOWED_CHANGES.items():
        require(set(before[scope]) == set(after[scope]), "protected source list cannot change")
        changed = {name for name in before[scope] if before[scope][name] != after[scope][name]}
        require(changed and changed <= allowed, "retry cannot change policy/prompt/encoding rules")
        result[scope] = sorted(changed)
    return result


def parent_revision(output, plan):
    output = Path(output)
    parent = checked(output / FUNDING_REVISION_PATH)
    funding = checked(output / FUNDING_PATH)
    require(
        parent["id"] == PARENT_FUNDING_EXECUTION_ID
        and funding["id"] == PARENT_FUNDING_RECEIPT_ID
        and parent["funding_amendment_id"] == funding["id"]
        and parent["funding_receipt_sha256"] == sha(output / FUNDING_PATH)
        and parent["protocol_id"] == plan["id"]
        and parent["batch_id"] == plan["batch_id"]
        and parent["policy_id"] == plan["review_policy_id"]
        and parent["original_sources"]["generation"] == plan["protected_generation_sources"]
        and parent["additional_source_bindings"] == funding_extra_sources()
        and parent["changed_files"]
        == check_funding_maps(parent["original_sources"], parent["effective_sources"]),
        "the prior exact funding revision must remain intact",
    )
    require(set(parent["historical_records"]) == set(HISTORICAL_PATHS), "old source anchors lost")
    for relative, binding in parent["historical_records"].items():
        require(sha(output / relative) == binding["sha256"], "initial registration was rewritten")
    return parent, funding


def register_retry_execution_revision(output):
    """Bind the precise code and one permit while the original workers are drained."""
    output = Path(output).resolve()
    require(not (output / REVISION_PATH).exists(), "do not replace the final-retry source revision")
    plan = checked(output / "registration/protocol.json")
    parent, funding = parent_revision(output, plan)
    permit = checked(output / AUTHORIZATION_PATH)
    from .v10_final_retry import read_final_retry_permit
    from .v10_generation import ledger_for

    ledger = ledger_for(plan)
    require(read_final_retry_permit(ledger) == permit, "artifact must be the real wallet permit")
    state = ledger.snapshot()
    require(
        not state["pending_requests"]
        and not state["unacknowledged_unknown_requests"]
        and not state["halt"]
        and state["funding_overlay"]["id"] == funding["id"]
        and not (output / "review_seal/record.json").exists()
        and not (output / "mapping_registration/record.json").exists()
        and not (output / "material/result/record.json").exists(),
        "register once before joint qualification/mapping, with drained original workers",
    )
    after = source_maps()
    record = bound(
        dict(
            schema="v10_single_final_retry_execution_revision.v1",
            at=now(),
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            policy_id=plan["review_policy_id"],
            authorization=AUTHORIZATION,
            funding_execution_revision_id=parent["id"],
            funding_execution_revision_sha256=sha(output / FUNDING_REVISION_PATH),
            funding_amendment_id=funding["id"],
            retry_permit_id=permit["id"],
            retry_permit_sha256=sha(output / AUTHORIZATION_PATH),
            initial_sources=parent["original_sources"],
            previous_effective_sources=parent["effective_sources"],
            effective_sources=after,
            changed_files=changed_sources(parent["effective_sources"], after),
            additional_source_bindings=extra_sources(),
            preserved_requests_before_resume=state["requests_reserved"],
            original_matrix_denominator=11438,
            extra_HTTP_attempt_ceiling=1,
            requires_complete_original_matrix_before_extra_attempt=True,
            original_UNKNOWN_and_hold_preserved=True,
            no_other_UNKNOWN_retry_authorized=True,
            model_prompt_capacity_scoring_masks_and_five_arms_unchanged=True,
            original_record_overwrites=False,
        )
    )
    persist((output / REVISION_PATH).parent, record)
    return record


def validate_retry_source_transition(output, plan, *, scope, original, current):
    output = Path(output).resolve()
    record = checked(output / REVISION_PATH)
    parent, funding = parent_revision(output, plan)
    permit = checked(output / AUTHORIZATION_PATH)
    require(
        record["schema"] == "v10_single_final_retry_execution_revision.v1"
        and record["protocol_id"] == plan["id"]
        and record["batch_id"] == plan["batch_id"]
        and record["policy_id"] == plan["review_policy_id"]
        and record["authorization"] == AUTHORIZATION
        and record["funding_execution_revision_id"] == parent["id"]
        and record["funding_execution_revision_sha256"] == sha(output / FUNDING_REVISION_PATH)
        and record["funding_amendment_id"] == funding["id"]
        and record["retry_permit_id"] == permit["id"]
        and record["retry_permit_sha256"] == sha(output / AUTHORIZATION_PATH)
        and record["initial_sources"] == parent["original_sources"]
        and record["initial_sources"][scope] == original
        and record["previous_effective_sources"] == parent["effective_sources"]
        and record["effective_sources"][scope] == current
        and record["effective_sources"] == source_maps()
        and record["additional_source_bindings"] == extra_sources()
        and record["changed_files"]
        == changed_sources(record["previous_effective_sources"], record["effective_sources"]),
        "only the exact registered final single-retry implementation is accepted",
    )
    return record
