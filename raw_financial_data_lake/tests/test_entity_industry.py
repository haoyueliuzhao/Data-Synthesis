from finraw.entity_normalization import _add_cninfo_companies, _add_sec_companies


def test_configured_sec_company_inherits_official_sic_description() -> None:
    entities = {}
    aliases = {}
    config = {
        "sec": {
            "sample_companies": [
                {"ticker": "AAPL", "cik": "320193", "name": "Apple Inc."}
            ]
        }
    }
    raw_records = [
        {
            "record_type": "sec_submissions_json",
            "record_json": {
                "cik": "0000320193",
                "name": "Apple Inc.",
                "sic": "3571",
                "sicDescription": "Electronic Computers",
            },
            "entity_hint": "AAPL",
        }
    ]
    _add_sec_companies(entities, aliases, [], raw_records, config)
    assert entities["AAPL_US"]["industry"] == "Electronic Computers"


def test_configured_bse_company_has_stable_exchange_and_industry() -> None:
    entities = {}
    aliases = {}
    config = {
        "bse": {
            "stock_pool": [
                {
                    "stock_code": "920001",
                    "company_name": "纬达光电",
                    "market": "BSE",
                    "industry": "计算机、通信和其他电子设备制造业",
                }
            ]
        }
    }

    _add_cninfo_companies(entities, aliases, [], [], config)

    assert entities["920001_BSE"]["exchange"] == "BSE"
    assert entities["920001_BSE"]["industry"] == "计算机、通信和其他电子设备制造业"
    assert any(
        row["source_id"] == "bse_disclosures"
        and row["entity_id"] == "920001_BSE"
        for row in aliases.values()
    )
