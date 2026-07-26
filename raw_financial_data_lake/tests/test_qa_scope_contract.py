from finraw.qa.scope_contract import (
    build_scope_contract,
    render_scope_contract,
    scope_contract_from_semantics,
    validate_scope_contract,
)


def test_scope_contract_distinguishes_complete_case_from_authoritative_universe() -> (
    None
):
    contract = build_scope_contract(
        display_name="Information Technology peer companies",
        source="project canonical entity registry",
        effective_date="FY2023",
        membership_rule="same registered industry label",
        data_eligibility="complete FY2022 and FY2023 revenue and profit inputs",
        size=18,
        entity_ids=["B_US", "A_US"],
        authoritative_membership=False,
    )
    english = render_scope_contract(contract, "en")
    chinese = render_scope_contract(contract, "zh")
    assert "18 U.S.-listed companies" in english
    assert "Information Technology peer group" in english
    assert "U.S.-listed" in english
    assert "complete comparable data for FY2023" in english
    assert "dataset" not in english
    assert "project canonical entity registry" not in english
    assert "complete FY2022 and FY2023 revenue and profit inputs" not in english
    assert "2023财年" in chinese
    assert "美国上市" in chinese
    assert "完整可比数据" in chinese
    assert "共18家" in chinese
    assert "项目规范实体登记表" not in chinese
    assert contract["entity_ids"] == ["A_US", "B_US"]
    assert contract["market_label"] == "us_listed"
    assert contract["scope_membership_hash"]


def test_legacy_scope_is_promoted_to_structured_contract() -> None:
    contract = scope_contract_from_semantics(
        {
            "industry": "Software",
            "period": "FY2023",
            "scope_entity_ids": ["A", "B"],
        }
    )
    assert contract["display_name"] == "Software"
    assert contract["size"] == 2
    assert contract["authoritative_membership"] is False


def test_legacy_scope_infers_market_from_entity_ids() -> None:
    contract = scope_contract_from_semantics(
        {
            "industry": "医药制造业",
            "period": "FY2023",
            "scope_entity_ids": ["000001_CN", "000002_CN"],
        }
    )
    assert contract["market_label"] == "mainland_china_listed"
    rendered = render_scope_contract(contract, "zh")
    assert (
        rendered == "2023财年具备完整可比数据的中国内地上市医药制造业同行公司（共2家）"
    )


def test_scope_market_inference_supports_exchange_suffixes() -> None:
    mainland = scope_contract_from_semantics(
        {
            "industry": "制造业",
            "period": "FY2024",
            "scope_entity_ids": ["600000_SSE", "000001_SZSE", "430001_BSE"],
        }
    )
    hong_kong = scope_contract_from_semantics(
        {
            "industry": "金融业",
            "period": "FY2024",
            "scope_entity_ids": ["00005_HKEX", "00939_HKEX"],
        }
    )
    assert mainland["market_label"] == "mainland_china_listed"
    assert hong_kong["market_label"] == "hong_kong_listed"


def test_scope_contract_validation_is_fail_closed_for_membership_changes() -> None:
    contract = build_scope_contract(
        display_name="Software peer companies",
        source="canonical entity master data",
        effective_date="FY2023",
        membership_rule="same normalized industry label",
        data_eligibility="complete comparable revenue and profit inputs",
        size=2,
        entity_ids=["A", "B"],
    )
    assert (
        validate_scope_contract(contract, expected_entity_ids=["B", "A"])["passed"]
        is True
    )
    tampered = {**contract, "entity_ids": ["A", "C"]}
    result = validate_scope_contract(tampered, expected_entity_ids=["A", "B"])
    assert result["passed"] is False
    assert "scope_entity_set_mismatch" in result["errors"]
    assert "scope_membership_hash_mismatch" in result["errors"]
    assert contract["scope_id"].startswith("scope_")
    assert contract["scope_eligibility_policy_hash"]
