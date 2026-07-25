from __future__ import annotations

import hashlib
import json
from typing import Any


SCOPE_CONTRACT_VERSION = "qa_scope_contract.v1"


def build_scope_contract(
    *,
    display_name: str,
    source: str,
    effective_date: Any,
    membership_rule: str,
    data_eligibility: str,
    size: int,
    entity_ids: list[str] | None = None,
    authoritative_membership: bool = False,
) -> dict[str, Any]:
    contract = {
        "version": SCOPE_CONTRACT_VERSION,
        "display_name": str(display_name).strip(),
        "source": str(source).strip(),
        "effective_date": str(effective_date).strip(),
        "membership_rule": str(membership_rule).strip(),
        "data_eligibility": str(data_eligibility).strip(),
        "size": max(int(size), 0),
        "entity_ids": sorted(str(item) for item in entity_ids or []),
        "authoritative_membership": bool(authoritative_membership),
    }
    contract["scope_membership_hash"] = hashlib.sha256(
        json.dumps(
            contract["entity_ids"], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return contract


def scope_contract_from_semantics(semantics: dict[str, Any]) -> dict[str, Any]:
    contract = semantics.get("scope_contract")
    if isinstance(contract, dict) and contract.get("display_name"):
        return dict(contract)
    scope = semantics.get("entity_scope")
    if not isinstance(scope, dict):
        scope = {}
    entity_ids = list(
        scope.get("entity_ids") or semantics.get("scope_entity_ids") or []
    )
    label = str(
        semantics.get("industry")
        or semantics.get("scope_label")
        or semantics.get("scope_definition")
        or "configured entities"
    )
    return build_scope_contract(
        display_name=label,
        source=str(
            semantics.get("scope_source") or "project canonical entity registry"
        ),
        effective_date=(
            semantics.get("scope_effective_date")
            or semantics.get("period")
            or "the stated period"
        ),
        membership_rule=str(
            semantics.get("scope_membership_rule")
            or "entities sharing the registered canonical scope label"
        ),
        data_eligibility=str(
            semantics.get("scope_data_eligibility")
            or "entities with every comparable input required by this question"
        ),
        size=int(semantics.get("scope_size") or len(entity_ids)),
        entity_ids=entity_ids,
        authoritative_membership=bool(semantics.get("scope_authoritative")),
    )


def render_scope_contract(contract: dict[str, Any], language: str = "en") -> str:
    display_name = str(contract.get("display_name") or "configured entities")
    source = str(contract.get("source") or "project canonical entity registry")
    effective_date = str(contract.get("effective_date") or "the stated period")
    eligibility = str(
        contract.get("data_eligibility")
        or "entities with every comparable input required by this question"
    )
    size = int(contract.get("size") or 0)
    authoritative = bool(contract.get("authoritative_membership"))
    if language == "zh":
        scope_kind = "成员范围" if authoritative else "完整数据样本"
        return (
            f"截至{effective_date}，按{source}归入{display_name}、并满足“{eligibility}”"
            f"条件的{size}个实体所构成的{scope_kind}"
        )
    scope_kind = (
        "membership universe"
        if authoritative
        else "complete-case universe (dataset eligibility, not authoritative membership)"
    )
    return (
        f"the {size}-entity {display_name} {scope_kind} as of {effective_date}, "
        f"defined from {source} and restricted to {eligibility}"
    )
