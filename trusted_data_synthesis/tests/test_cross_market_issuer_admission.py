import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cross_market_issuer_admission_20260926 as issuer


def pages(text):
    return [{"page": 1, "text": text}]


def test_chinese_self_field_not_body_mention():
    name = "示例股份有限公司"
    assert (
        issuer.identity_evidence(pages("客户包括" + name), [name], "cninfo_announcements") is None
    )
    result = issuer.identity_evidence(
        pages("公司的中文名称\n" + name), [name], "cninfo_announcements"
    )
    assert result["legal_name"] == name
    assert result["method"] == "explicit_issuer_name_field"


def test_hk_auditor_addressee_and_header():
    name = "Example Holdings Limited"
    result = issuer.identity_evidence(
        pages("TO THE MEMBERS OF\nEXAMPLE HOLDINGS LIMITED"), [name], "hkex_disclosures"
    )
    assert result["method"] == "auditor_addressee"
    assert (
        issuer.identity_evidence(
            pages("Our supplier is Example Holdings Limited."), [name], "hkex_disclosures"
        )
        is None
    )
    assert issuer.identity_evidence(pages(name + " Annual Report 2025"), [name], "hkex_disclosures")


def test_stock_code_is_not_arbitrary_numeric_mention():
    assert issuer.code_evidence(pages("Revenue increased by 762 million"), "00762") is None
    assert issuer.code_evidence(pages("Stock code: 762"), "00762")
    assert issuer.code_evidence(pages("Stock code: 1762"), "00762") is None
    assert issuer.code_evidence(pages("股票代码\n600036"), "600036")
    assert issuer.code_evidence(
        pages("STOCK SHORT NAMES AND CODES\nA share 601318\nH share Ping An 2318"), "02318"
    )


def test_explicit_foreign_name_handles_wrapped_label_and_value():
    result = issuer.foreign_name_evidence(
        pages(
            "公司的外文名称（如\n有）\nEXAMPLE COMMERCIAL\nGROUP CO.,LTD.\n公司的外文名称缩写\nEX"
        )
    )
    assert [e["legal_name"] for e in result] == ["EXAMPLE COMMERCIAL GROUP CO.,LTD."]
    assert not issuer.foreign_name_evidence(pages("客户名称 EXAMPLE COMMERCIAL GROUP CO.,LTD."))


def test_foreign_name_does_not_include_next_numbered_label():
    result = issuer.foreign_name_evidence(
        pages("法定英文名称：Example Bank Co., Ltd.\n1.1.2 法定代表人：某人")
    )
    assert result[0]["legal_name"] == "Example Bank Co., Ltd."
    assert issuer.identity_key("EXAMPLE, Inc.") == issuer.identity_key("Example Inc")


def test_rename_requires_both_names_and_explicit_change_context():
    doc = {"raw_object_id": "test"}
    assert not issuer.rename_evidence(
        [(doc, {"pages": pages("Old Company\nNew Company")})], ["New Company", "Old Company"]
    )
    result = issuer.rename_evidence(
        [(doc, {"pages": pages("公司名称由 Old Company 变更为 New Company")})],
        ["New Company", "Old Company"],
    )
    assert len(result) == 1


def test_identity_hash_uses_name_not_ticker():
    assert issuer.norm("Example   Holdings LIMITED") == issuer.norm("example holdings limited")
    assert issuer.base.sha(issuer.norm("Example Holdings Limited")) != issuer.base.sha("00001")


def test_reviewed_roster_exact_size_and_no_collision():
    assert len(issuer.CN_NAMES) == len(issuer.HK_NAMES) == 32
    names = [names[0] for roster in [issuer.CN_NAMES, issuer.HK_NAMES] for names in roster.values()]
    assert len(set(map(issuer.norm, names))) == 64
