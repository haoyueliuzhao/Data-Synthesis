from finraw.entity_normalization import _add_sec_companies


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
