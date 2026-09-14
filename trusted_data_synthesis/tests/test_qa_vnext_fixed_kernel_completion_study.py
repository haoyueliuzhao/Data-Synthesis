"""Small composition controls; no API, wallet, tokenizer or GPU operations."""

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import completion as c
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p


def test_only_terminal_status_selects_original_slots():
    registry = {
        "sessions": [
            {"session_id": name}
            for name in ("valid", "transport_failure", "interrupted", "unrequested")
        ]
    }
    results = [
        {"session_id": name, "status": status}
        for name, status in (
            ("valid", "finished"),
            ("transport_failure", "finished"),
            ("interrupted", "budget_aborted"),
            ("unrequested", "not_run"),
        )
    ]
    slots = c.select_slots(registry, results, [])
    assert [row["registered_session"]["session_id"] for row in slots] == [
        "interrupted",
        "unrequested",
    ]
    assert [row["parent_status"] for row in slots] == ["budget_aborted", "not_run"]


def test_unknown_request_cannot_be_used_as_completion_prefix():
    registry = {"sessions": [{"session_id": "slot"}]}
    results = [{"session_id": "slot", "status": "budget_aborted"}]
    journal = [{"session_id": "slot", "attempt": 1, "state": "usage_unknown"}]
    with pytest.raises(ValueError, match="no_retry"):
        c.select_slots(registry, results, journal)


def test_old_qualification_identity_not_rewritten():
    results = [
        {
            "session_id": "slot",
            "status": "finished",
            "session": {"id": "old_session"},
            "qualification": {"id": "old_qualification"},
        },
        {"session_id": "unfinished", "status": "not_run"},
    ]
    bindings = c.lineage_bindings(results, "old_code")
    assert set(bindings) == {"slot"}
    binding = p.checked(bindings["slot"], "material_qualification_lineage_binding")
    assert binding["material_session_id"] == "old_session"
    assert binding["qualification_id"] == "old_qualification"
    assert binding["code_snapshot_id"] == "old_code"


def test_revised_cap_keeps_old_unknown_charges_and_common_limit():
    assert c.TOKEN_CAP + 1269703 + 239706046 == c.TOTAL_TOKEN_CAP == 350000000
    assert c.REQUEST_CAP == c.EXPECTED_SLOTS * p.MAX_RESPONSES - c.EXPECTED_PREFIXES
    assert p.COMMON_CAP == 1000000000
