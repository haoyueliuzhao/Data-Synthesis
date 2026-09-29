"""Exact, user-authorized funding-only source transition after whole generation.

Old protocol/policy/runtime/matrix and paid bytes remain immutable. This accepts
only the registered before/after hashes, never an unrestricted source override.
"""

from pathlib import Path

from .calibration import now
from .contracts import digest
from .storage import read_json
from .v6_collection import bound, persist, require, sha

REVISION_PATH = Path("funding/execution_revision_01/record.json")
FUNDING_PATH = Path("funding/amendment_01/record.json")
BATCH_ID = "finqa-v10-20260929-new8000-01"
USER_REPLY = "总上限提高到 2000 元，审阅／映射子额 1300 元"
MIGRATION_AUTHORIZATION = dict(
    question=(
        "是否批准为落实 2000 元总上限／1300 元审阅子额，进行一次受控预算实现迁移？"
        "安全审查要求明确授权：先停止新派发并等在途结算，备份原钱包；"
        "保留旧源码和原哈希记录，另登记预算模块及其版本校验接线的精确新旧哈希，"
        "仅接受该次指定迁移，再恢复原矩阵未发送项。"
        "不会关闭通用完整性校验、修改实验规则或重发已调用请求。"
    ),
    user_reply="批准预算提升，减少冗余校验",
    date="2026-09-29",
)
ALLOWED_CHANGES = {
    "generation": {"probe_budget.py", "v10_budget.py", "v10_generation.py"},
    "annotation": {"probe_budget.py", "v10_budget.py", "v10_production.py"},
}
EXTRA_SOURCES = ("v10_execution_revision.py", "v10_funding.py")
HISTORICAL_PATHS = (
    "registration/protocol.json",
    "runtime/concurrency_revision_01/record.json",
    "review_registration/record.json",
    "generation_seal/record.json",
    "native_support/record.json",
)


def checked(path):
    value = read_json(path)
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
        "funding execution evidence identity changed",
    )
    return value


def source_maps():
    from .v10_generation import source_binding
    from .v10_production import phase_sources

    return dict(generation=source_binding(), annotation=phase_sources())


def extra_sources():
    root = Path(__file__).parent
    return {name: sha(root / name) for name in EXTRA_SOURCES}


def _check_maps(before, after):
    require(set(before) == set(after) == set(ALLOWED_CHANGES), "funding source scopes changed")
    differences = {}
    for scope, allowed in ALLOWED_CHANGES.items():
        old, new = before[scope], after[scope]
        require(set(old) == set(new), "funding transition cannot add/remove protected sources")
        changed = {name for name in old if old[name] != new[name]}
        require(changed and changed <= allowed, "non-funding policy/provider/source change")
        differences[scope] = sorted(changed)
    return differences


def _funding(output, plan):
    receipt = checked(Path(output) / FUNDING_PATH)
    authorization = receipt.get("authorization", {})
    require(
        receipt.get("run_id") == plan["budget_config"]["run_id"]
        and receipt.get("config_sha256") == plan["budget_config_sha256"]
        and receipt.get("batch_id") == plan["batch_id"] == BATCH_ID
        and authorization.get("user_reply") == USER_REPLY
        and receipt.get("effective_hard_cap_microcny") == 2_000_000_000
        and receipt.get("effective_review_mapping_microcny") == 1_300_000_000,
        "exact approved funding receipt required, not a new research protocol",
    )
    return receipt


def register_execution_revision(output):
    """After quiescent financial application, before any resumed dispatch."""
    output = Path(output).resolve()
    require(not (output / REVISION_PATH).exists(), "funding execution revision already exists")
    records = {relative: checked(output / relative) for relative in HISTORICAL_PATHS}
    plan = records["registration/protocol.json"]
    runtime = records["runtime/concurrency_revision_01/record.json"]
    phase = records["review_registration/record.json"]
    generation = records["generation_seal/record.json"]
    native = records["native_support/record.json"]
    receipt = _funding(output, plan)
    require(
        generation["protocol_id"] == native["protocol_id"] == plan["id"]
        and generation["denominator"] == len(generation["slots"]) == 8000
        and native["generation_seal_id"] == generation["id"]
        and native["slot_denominator"] == len(native["rows"]) == 8000
        and [r["slot"] for r in generation["slots"]]
        == [r["slot"] for r in native["rows"]]
        == plan["slots"],
        "funding transition only after complete same-roster generation/native scoring",
    )
    require(
        runtime["protocol_id"] == phase["protocol_id"] == plan["id"]
        and runtime["source_bindings"] == phase["source_bindings"]
        and runtime["effective_concurrency"] == dict(generation=8, review=16, mapping=16),
        "original registered annotation/concurrency evidence changed",
    )
    before = dict(
        generation=plan["protected_generation_sources"],
        annotation=phase["source_bindings"],
    )
    after = source_maps()
    differences = _check_maps(before, after)
    from .probe_budget import read_budget_snapshot

    state = read_budget_snapshot(plan["budget_database"])["snapshot"]
    require(
        not state["pending_requests"]
        and not state["unacknowledged_unknown_requests"]
        and not state["halt"]
        and state["effective_hard_cap_microcny"] == 2_000_000_000
        and state.get("funding_overlay") == receipt
        and state["requests_reserved"] == receipt["applied_after_requests"],
        "financial/source transition must precede resumed HTTP and preserve settled history",
    )
    body = bound(
        dict(
            schema="v10_funding_execution_revision.v1",
            at=now(),
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            policy_id=plan["review_policy_id"],
            authorization=receipt["authorization"],
            migration_authorization=MIGRATION_AUTHORIZATION,
            funding_amendment_id=receipt["id"],
            funding_receipt_sha256=sha(output / FUNDING_PATH),
            effective_after_requests=receipt["applied_after_requests"],
            original_sources=before,
            effective_sources=after,
            changed_files=differences,
            additional_source_bindings=extra_sources(),
            historical_records={
                path: dict(id=value["id"], sha256=sha(output / path))
                for path, value in records.items()
            },
            semantics_model_prompts_outputs_roster_native_and_masks_unchanged=True,
            old_source_records_rewritten=False,
            old_paid_calls_resent=False,
            generation_already_complete=True,
            effective_concurrency=runtime["effective_concurrency"],
        )
    )
    persist((output / REVISION_PATH).parent, body)
    return body


def validate_source_transition(output, plan, *, scope, original, current):
    """Require this cohort's exact funded before/after pair, not just file names."""
    output = Path(output).resolve()
    record = checked(output / REVISION_PATH)
    receipt = _funding(output, plan)
    require(
        record["schema"] == "v10_funding_execution_revision.v1"
        and record["protocol_id"] == plan["id"]
        and record["batch_id"] == plan["batch_id"] == BATCH_ID
        and record["policy_id"] == plan["review_policy_id"]
        and record["authorization"] == receipt["authorization"]
        and record["migration_authorization"] == MIGRATION_AUTHORIZATION
        and record["funding_amendment_id"] == receipt["id"]
        and record["funding_receipt_sha256"] == sha(output / FUNDING_PATH)
        and record["effective_after_requests"] == receipt["applied_after_requests"]
        and record["additional_source_bindings"] == extra_sources()
        and record["original_sources"][scope] == original
        and record["effective_sources"][scope] == current
        and record["effective_sources"] == source_maps()
        and record["changed_files"]
        == _check_maps(record["original_sources"], record["effective_sources"]),
        "funding source transition missing or different; frozen semantics must not change",
    )
    require(set(record["historical_records"]) == set(HISTORICAL_PATHS), "historical evidence lost")
    for relative, binding in record["historical_records"].items():
        require(sha(output / relative) == binding["sha256"], "old registration was rewritten")
    return record
