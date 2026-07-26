from __future__ import annotations

import hashlib
import json
import re
from typing import Any


SCOPE_CONTRACT_VERSION = "qa_scope_contract.v3"


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
    market_label: str = "",
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
        "market_label": str(
            market_label or _infer_market_label(entity_ids or [])
        ).strip(),
        "scope_type": (
            "authoritative_membership"
            if authoritative_membership
            else "complete_case_dataset_universe"
        ),
    }
    identity = {
        key: contract[key]
        for key in (
            "version",
            "display_name",
            "source",
            "effective_date",
            "membership_rule",
            "scope_type",
            "market_label",
        )
    }
    contract["scope_id"] = (
        "scope_"
        + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
    )
    contract["scope_eligibility_policy_hash"] = hashlib.sha256(
        contract["data_eligibility"].encode("utf-8")
    ).hexdigest()
    contract["scope_membership_hash"] = hashlib.sha256(
        json.dumps(
            contract["entity_ids"], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return contract


def scope_contract_from_semantics(semantics: dict[str, Any]) -> dict[str, Any]:
    contract = semantics.get("scope_contract")
    if isinstance(contract, dict) and contract.get("display_name"):
        return build_scope_contract(
            display_name=str(contract.get("display_name") or ""),
            source=str(contract.get("source") or ""),
            effective_date=contract.get("effective_date"),
            membership_rule=str(contract.get("membership_rule") or ""),
            data_eligibility=str(contract.get("data_eligibility") or ""),
            size=int(contract.get("size") or 0),
            entity_ids=list(contract.get("entity_ids") or []),
            authoritative_membership=bool(contract.get("authoritative_membership")),
            market_label=str(
                contract.get("market_label")
                or _infer_market_label(list(contract.get("entity_ids") or []))
            ),
        )
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
        market_label=str(
            semantics.get("scope_market_label") or _infer_market_label(entity_ids)
        ),
    )


def validate_scope_contract(
    contract: dict[str, Any],
    *,
    expected_entity_ids: list[str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    required_text = (
        "display_name",
        "source",
        "effective_date",
        "membership_rule",
        "data_eligibility",
    )
    for field in required_text:
        if not str(contract.get(field) or "").strip():
            errors.append(f"missing_{field}")

    entity_ids = [str(item) for item in contract.get("entity_ids") or []]
    canonical_entity_ids = sorted(set(entity_ids))
    size = int(contract.get("size") or 0)
    if not canonical_entity_ids:
        errors.append("empty_scope_entity_ids")
    if len(entity_ids) != len(canonical_entity_ids):
        errors.append("duplicate_scope_entity_ids")
    if size != len(canonical_entity_ids):
        errors.append("scope_size_mismatch")

    expected = sorted(set(str(item) for item in expected_entity_ids or []))
    if expected and canonical_entity_ids != expected:
        errors.append("scope_entity_set_mismatch")

    expected_hash = hashlib.sha256(
        json.dumps(canonical_entity_ids, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    if str(contract.get("scope_membership_hash") or "") != expected_hash:
        errors.append("scope_membership_hash_mismatch")
    identity = {
        key: contract.get(key)
        for key in (
            "version",
            "display_name",
            "source",
            "effective_date",
            "membership_rule",
            "scope_type",
            "market_label",
        )
    }
    expected_scope_id = (
        "scope_"
        + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
    )
    if str(contract.get("scope_id") or "") != expected_scope_id:
        errors.append("scope_id_mismatch")
    expected_eligibility_hash = hashlib.sha256(
        str(contract.get("data_eligibility") or "").encode("utf-8")
    ).hexdigest()
    if (
        str(contract.get("scope_eligibility_policy_hash") or "")
        != expected_eligibility_hash
    ):
        errors.append("scope_eligibility_policy_hash_mismatch")

    return {
        "passed": not errors,
        "errors": sorted(set(errors)),
        "scope_contract_version": contract.get("version"),
        "scope_id": expected_scope_id,
        "scope_type": contract.get("scope_type"),
        "scope_eligibility_policy_hash": expected_eligibility_hash,
        "scope_size": size,
        "represented_entity_ids": canonical_entity_ids,
        "expected_entity_ids": expected,
        "scope_membership_hash": expected_hash,
        "authoritative_membership": bool(contract.get("authoritative_membership")),
    }


def render_scope_contract(contract: dict[str, Any], language: str = "en") -> str:
    display_name = _public_scope_name(
        str(contract.get("display_name") or "configured entities"), language
    )
    source = _public_scope_source(
        str(contract.get("source") or "project canonical entity registry"), language
    )
    effective_date = str(contract.get("effective_date") or "the stated period")
    size = int(contract.get("size") or 0)
    authoritative = bool(contract.get("authoritative_membership"))
    market_label = _public_market_label(
        str(contract.get("market_label") or ""), language
    )
    public_date = _public_effective_date(effective_date, language)
    if language == "zh":
        if authoritative:
            return f"截至{public_date}由{source}界定的{display_name}（共{size}个实体）"
        return (
            f"{public_date}具备完整可比数据的{market_label}{display_name}同行公司"
            f"（共{size}家）"
        )
    if authoritative:
        return (
            f"the {display_name} universe defined by {source} as of "
            f"{public_date} ({size} entities)"
        )
    return (
        f"the {size} {market_label}companies in the {display_name} peer group "
        f"with complete comparable data for {public_date}"
    )


def _public_scope_name(value: str, language: str) -> str:
    text = " ".join(value.split()).strip()
    canonical_match = re.search(
        r"canonical company industry\s+['\"]([^'\"]+)['\"]",
        text,
        re.IGNORECASE,
    )
    if canonical_match:
        text = canonical_match.group(1)
    text = re.sub(
        r"\s+within authoritative source\s+['\"].*$", "", text, flags=re.I
    ).strip(" '\"")
    text = re.sub(r"\s+(?:peer\s+)?companies$", "", text, flags=re.I).strip()
    text = re.sub(r"\s+(?:peer\s+)?entities$", "", text, flags=re.I).strip()
    if not text or text.casefold() == "configured entities":
        return "可比实体" if language == "zh" else "comparable entities"
    if language == "zh":
        return re.sub(r"(?:同行组|同行公司|范围)$", "", text).strip()
    return re.sub(r"\s+(?:peer group|universe)$", "", text, flags=re.I).strip()


def _infer_market_label(entity_ids: list[str]) -> str:
    suffixes = {
        str(entity_id).rsplit("_", 1)[-1].upper()
        for entity_id in entity_ids
        if "_" in str(entity_id)
    }
    if suffixes and suffixes <= {"US"}:
        return "us_listed"
    mainland_suffixes = {"CN", "SH", "SZ", "BJ", "SSE", "SZSE", "BSE"}
    if suffixes and suffixes <= mainland_suffixes:
        return "mainland_china_listed"
    if suffixes and suffixes <= {"HK", "HKEX"}:
        return "hong_kong_listed"
    if suffixes and suffixes <= mainland_suffixes | {"HK", "HKEX"}:
        return "greater_china_listed"
    return ""


def _public_market_label(value: str, language: str) -> str:
    normalized = str(value or "").casefold()
    if language == "zh":
        return {
            "us_listed": "美国上市",
            "mainland_china_listed": "中国内地上市",
            "hong_kong_listed": "香港上市",
            "greater_china_listed": "大中华区上市",
        }.get(normalized, "")
    return {
        "us_listed": "U.S.-listed ",
        "mainland_china_listed": "mainland China-listed ",
        "hong_kong_listed": "Hong Kong-listed ",
        "greater_china_listed": "Greater China-listed ",
    }.get(normalized, "")


def _public_effective_date(value: str, language: str) -> str:
    text = str(value or "the stated period").strip()
    fiscal = re.fullmatch(r"FY\s*(\d{4})", text, re.I)
    calendar = re.fullmatch(r"(?:CY\s*)?(\d{4})", text, re.I)
    if language == "zh":
        if fiscal:
            return f"{fiscal.group(1)}财年"
        if calendar:
            return f"{calendar.group(1)}自然年"
        if text == "the stated period":
            return "题目所述期间"
    return text


def _public_scope_source(value: str, language: str) -> str:
    normalized = value.strip().casefold()
    aliases = {
        "project canonical entity registry": (
            "the stated industry classification",
            "既定行业分类",
        ),
        "sec_companyfacts": ("SEC filing data", "SEC申报数据"),
        "hkex_disclosures": ("HKEX disclosures", "港交所披露资料"),
        "cninfo_reports": ("official CNInfo disclosures", "巨潮资讯官方披露资料"),
    }
    english, chinese = aliases.get(normalized, (value, value))
    return chinese if language == "zh" else english
