from __future__ import annotations

from finraw.connectors.official_publications import OfficialPublicationConnector


def test_official_publication_validation_is_fail_closed() -> None:
    passed_pdf = OfficialPublicationConnector.validate_publication(
        b"%PDF-1.7 public data",
        200,
        {"Content-Type": "application/pdf"},
        "pdf",
    )
    assert passed_pdf[0] == "passed"
    failed_waf = OfficialPublicationConnector.validate_publication(
        "<html>安全验证：异常行为</html>".encode(),
        200,
        {"Content-Type": "text/html"},
        "html",
    )
    assert failed_waf[0] == "failed"
    failed_xlsx = OfficialPublicationConnector.validate_publication(
        b"<html>not a workbook</html>",
        200,
        {"Content-Type": "text/html"},
        "xlsx",
    )
    assert failed_xlsx[0] == "failed"


def test_official_publication_storage_path_is_deterministic() -> None:
    path = OfficialPublicationConnector._relative_path(
        "safe_official_statistics",
        {
            "publication_id": "official_reserves_2025",
            "period_hint": "2025",
            "format": "xlsx",
        },
    )
    assert path == (
        "safe_official_statistics/publications/period=2025/"
        "official_reserves_2025.xlsx"
    )
