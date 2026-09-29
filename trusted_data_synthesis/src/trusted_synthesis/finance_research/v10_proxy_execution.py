"""Exact authorized transport-only transition; original research/finance stay fixed."""

from pathlib import Path

from .calibration import identity, now
from .v6_collection import bound, persist, require, sha
from .v10_execution_revision import source_maps
from .v10_network_retry_execution import (
    AUTHORIZATION_PATH as NETWORK_AUTHORIZATION_PATH,
)
from .v10_network_retry_execution import (
    REVISION_PATH as NETWORK_REVISION_PATH,
)
from .v10_network_retry_execution import checked
from .v10_network_retry_execution import parent_revision as single_parent_revision

REVISION_PATH = Path("transport_proxy_01/execution_revision/record.json")
AUTHORIZATION_PATH = Path("transport_proxy_01/authorization/record.json")
PARENT_EXECUTION_ID = "466d07ee54b3b57e10fc72a1b479802a14afc703b4bd87f696485e94c0b2af26"
AUTHORIZATION = dict(
    question=(
        "已确认当前直连的 api.deepseek.com DNS 连续失败，恢复尝试又产生一波网络 UNKNOWN。"
        "是否允许仅将本批 DeepSeek 调用改用你现有的代理：先做不带密钥、无计费的连通性验证，"
        "验证通过后按原矩阵恢复；不改全局网络配置、模型、预算或审阅规则？"
    ),
    user_reply="授权现有代理验证并恢复",
    date="2026-09-30",
)
ALLOWED_CHANGES = {
    "generation": {"v10_generation.py", "v10_review_provider.py"},
    "annotation": {"v10_production.py", "v10_review_provider.py"},
}
EXTRA_SOURCES = ("v10_proxy_execution.py", "v10_transport.py")


def extra_sources():
    return {name: sha(Path(__file__).parent / name) for name in EXTRA_SOURCES}


def changed_sources(before, after):
    require(set(before) == set(after) == set(ALLOWED_CHANGES), "proxy source scopes changed")
    result = {}
    for scope, allowed in ALLOWED_CHANGES.items():
        require(set(before[scope]) == set(after[scope]), "protected source list cannot change")
        changed = {name for name in before[scope] if before[scope][name] != after[scope][name]}
        require(
            changed and changed <= allowed,
            "proxy transition cannot change research or budget rules",
        )
        result[scope] = sorted(changed)
    return result


def parent_revision(output, plan):
    output = Path(output)
    single, _ = single_parent_revision(output, plan)
    parent = checked(output / NETWORK_REVISION_PATH)
    permit = checked(output / NETWORK_AUTHORIZATION_PATH)
    require(
        parent["id"] == PARENT_EXECUTION_ID
        and parent["protocol_id"] == plan["id"]
        and parent["batch_id"] == plan["batch_id"]
        and parent["policy_id"] == plan["review_policy_id"]
        and parent["previous_execution_revision_id"] == single["id"]
        and parent["initial_sources"] == single["initial_sources"]
        and parent["network_retry_permit_id"] == permit["id"]
        and parent["network_retry_permit_sha256"] == sha(output / NETWORK_AUTHORIZATION_PATH),
        "preserve the exact original network retry authority and source history",
    )
    for name, original_sha in parent["additional_source_bindings"].items():
        require(
            sha(Path(__file__).parent / name) == original_sha,
            "retry/material implementation changed",
        )
    return parent


def register_proxy_execution(output, *, stopped_processes, probe_evidence):
    """Append a source/route receipt after drainage; does not mutate the wallet."""
    from .v10_generation import ledger_for
    from .v10_transport import checked_proxy

    output = Path(output).resolve()
    plan = checked(output / "registration/protocol.json")
    parent = parent_revision(output, plan)
    require(not (output / REVISION_PATH).exists(), "proxy source revision already exists")
    require(
        stopped_processes and all(identity(p["pid"]) != p["birth"] for p in stopped_processes),
        "previous owned workers must exit before changing transport",
    )
    state = ledger_for(plan).snapshot()
    require(
        not state["pending_requests"]
        and not state["unacknowledged_unknown_requests"]
        and not state["halt"]
        and not (output / "review_seal/record.json").exists(),
        "resume the same incomplete matrix only after settlement",
    )
    require(
        probe_evidence["model_calls"] == 0
        and probe_evidence["http_status"] == 401
        and probe_evidence["TLS_verified"] is True
        and probe_evidence["authorization_header_sent"] is False,
        "one unauthenticated verified transport probe required",
    )
    authorization = bound(
        dict(
            schema="v10_explicit_proxy_authorization.v1",
            at=now(),
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            authorization=AUTHORIZATION,
            proxy_url_sha256="813477bf51a0efb3b5926c3759f01d02cdf25cd70e6cfc7fa186d9d5e1e1d118",
            proxy_source_env="HTTPS_PROXY",
            proxy_host="127.0.0.1",
            proxy_port=7897,
            proxy_scheme="http",
            proxy_credentials_present=False,
            probe_evidence=probe_evidence,
            stopped_processes=stopped_processes,
            scope="remaining same-batch review, authorized network attempt2 and task mapping",
            trust_env=False,
            TLS_verified=True,
            automatic_transport_retries=0,
            global_configuration_changed=False,
            direct_fallback=False,
            model_prompt_budget_and_review_rules_unchanged=True,
            original_UNKNOWN_and_holds_preserved=True,
        )
    )
    persist((output / AUTHORIZATION_PATH).parent, authorization)
    require(checked_proxy(output, plan) is not None, "approved explicit proxy must resolve")
    after = source_maps()
    record = bound(
        dict(
            schema="v10_proxy_execution_revision.v1",
            at=now(),
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            policy_id=plan["review_policy_id"],
            authorization=AUTHORIZATION,
            transport_authorization_id=authorization["id"],
            transport_authorization_sha256=sha(output / AUTHORIZATION_PATH),
            previous_execution_revision_id=parent["id"],
            previous_execution_revision_sha256=sha(output / NETWORK_REVISION_PATH),
            initial_sources=parent["initial_sources"],
            previous_effective_sources=parent["effective_sources"],
            effective_sources=after,
            changed_files=changed_sources(parent["effective_sources"], after),
            additional_source_bindings=extra_sources(),
            preserved_requests_before_resume=state["requests_reserved"],
            no_wallet_mutation=True,
            original_matrix_denominator=11438,
        )
    )
    persist((output / REVISION_PATH).parent, record)
    return record


def validate_proxy_source_transition(output, plan, *, scope, original, current):
    output = Path(output).resolve()
    record = checked(output / REVISION_PATH)
    parent = parent_revision(output, plan)
    authority = checked(output / AUTHORIZATION_PATH)
    require(
        record["schema"] == "v10_proxy_execution_revision.v1"
        and record["protocol_id"] == plan["id"]
        and record["batch_id"] == plan["batch_id"]
        and record["policy_id"] == plan["review_policy_id"]
        and record["authorization"] == authority["authorization"] == AUTHORIZATION
        and record["transport_authorization_id"] == authority["id"]
        and record["transport_authorization_sha256"] == sha(output / AUTHORIZATION_PATH)
        and record["previous_execution_revision_id"] == parent["id"]
        and record["previous_execution_revision_sha256"] == sha(output / NETWORK_REVISION_PATH)
        and record["initial_sources"] == parent["initial_sources"]
        and record["initial_sources"][scope] == original
        and record["previous_effective_sources"] == parent["effective_sources"]
        and record["effective_sources"][scope] == current
        and record["effective_sources"] == source_maps()
        and record["additional_source_bindings"] == extra_sources()
        and record["changed_files"]
        == changed_sources(record["previous_effective_sources"], record["effective_sources"]),
        "only the exact authorized transport source revision may resume",
    )
    return record
