from finraw.qa.scope_contract import (
    build_scope_contract,
    render_scope_contract,
    scope_contract_from_semantics,
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
        entity_ids=["B", "A"],
        authoritative_membership=False,
    )
    english = render_scope_contract(contract, "en")
    chinese = render_scope_contract(contract, "zh")
    assert "18-entity" in english
    assert "complete-case universe" in english
    assert "membership universe" not in english
    assert "18个实体" in chinese
    assert "完整数据样本" in chinese
    assert contract["entity_ids"] == ["A", "B"]
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
