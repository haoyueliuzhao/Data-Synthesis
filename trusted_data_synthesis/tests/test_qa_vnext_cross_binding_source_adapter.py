"""Fresh three-source adapter controls; no provider or historical session replay."""

from __future__ import annotations

import copy
import socket
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.measurement import audit_session
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, record
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import public_share_answer
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding import source

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("source/adapter tests must not call a provider")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(scope="module")
def sources():
    return source.load_sources(ROOT)


def _claim(adapter, claims, operation, choice=None):
    offer = next(
        item
        for item in adapter.offers(claims)
        if item["operation"] == operation and (choice is None or item["semantic_choice"] == choice)
    )
    prepared = adapter.prepare(offer, claims)
    proposition = adapter.execute(prepared)
    assert adapter.verify_execution(prepared, proposition)
    claim = record(
        "claim",
        observation_id="fresh-test-observation",
        action_submission_id=offer["id"],
        obligation_id=offer["obligation_id"],
        proposition=proposition,
        status="accepted",
    )
    return claim


def _route(adapter, route):
    claims = []
    if route == "S":
        claims.append(_claim(adapter, claims, "relation_sum"))
    claims.append(
        _claim(
            adapter,
            claims,
            "share_ratio",
            "disclosed_total" if route == "D" else "reconstructed_total",
        )
    )
    claims.append(_claim(adapter, claims, "scale_percent"))
    final = {
        "answer_claim_id": claims[-1]["id"],
        "result": public_share_answer(adapter.context, claims[-1]),
        "citations": claims[-1]["proposition"]["lineage"],
    }
    assert adapter.verify_final(final, claims)["qa_valid"]
    return claims, final


def test_three_fixed_source_bindings_actual_years_metrics_and_cells(sources):
    expected = [
        ("unp_2016", "2016", "total_freight_revenues", ("18601", "1340", "19941")),
        ("jpm_2014", "2014", "noninterest_revenue", ("50571", "43634", "94205")),
        ("jpm_2015", "2015", "noninterest_revenue", ("50033", "43510", "93543")),
    ]
    for item, (key, period, metric, values) in zip(sources, expected, strict=True):
        assert item.source_key == key and item.context["period"] == period
        assert item.evidence["target_component"]["metric"] == metric
        assert tuple(item.evidence[role]["value"] for role in source.ROLES) == values
        binding = item.binding_record
        assert binding["selected_column"]["index"] == 1
        assert binding["selected_column"]["report_directory_used_as_period"] is False
        assert binding["arithmetic"] == {
            "sum_computed": False,
            "share_answer_computed": False,
            "candidate_executions": 0,
        }
        assert binding["access_log"]["qa_semantic_access"] is False
        assert (
            binding["evidence"]["composition_relation"]["numeric_sum_computed_for_admission"]
            is False
        )
        assert item.context["currency"] == "dollar_as_disclosed"
        for raw in binding["raw_source_records"]:
            assert set(raw["source_fields"]) == set(source.SOURCE_FIELDS)
        for reference in binding["source_references"]:
            assert reference["archive_sha256"] == source.ARCHIVE_SHA256
        if key.startswith("jpm"):
            assert "freight" not in canonical_json_bytes(item.evidence).decode().lower()


def test_distinct_new_identity_and_deterministic_fresh_adapter(sources):
    adapters = [BoundShareTaskAdapter(item) for item in sources]
    assert len({item.task_id for item in sources}) == 3
    assert len({item.source_binding_id for item in sources}) == 3
    assert len({item.semantic_contract["id"] for item in sources}) == 3
    assert len({item.context["adapter_id"] for item in adapters}) == 3
    for adapter in adapters:
        fresh = BoundShareTaskAdapter(adapter.source)
        assert canonical_json_bytes(adapter.context) == canonical_json_bytes(fresh.context)
        assert adapter.registry is not fresh.registry
        assert adapter.registry.manifest() == fresh.registry.manifest()
        assert "source_explicit_share_obligations.v2" != adapter.context["adapter_id"]


def test_bound_source_mutable_metadata_drift_rejected(sources):
    changed = copy.deepcopy(sources[1])
    changed.evidence["target_component"]["metric"] = "freight_revenue"
    with pytest.raises(ProtocolError, match="bound_identity"):
        BoundShareTaskAdapter(changed)


@pytest.mark.parametrize(
    "index,preference",
    [(i, p) for i in range(3) for p in ("disclosed_total", "reconstructed_total")],
)
def test_fresh_common_runtime_round_trip_and_readonly_audit(sources, index, preference, tmp_path):
    adapter = BoundShareTaskAdapter(sources[index])
    directory = tmp_path / "fresh_new_binding_session"
    session = PublicQARuntime(
        adapter,
        PublicFixtureCallback(support_preference=preference),
        directory,
        max_submissions=8,
        max_actions=3,
    ).run()
    audit = audit_session(adapter, session, directory)
    assert audit["validation_passed"] and audit["qa_valid"] and audit["trajectory_valid"]
    assert audit["provider_calls_by_audit"] == audit["runtime_executions_by_audit"] == 0
    assert audit["adapter_execute_calls_by_audit"] == 0


@pytest.mark.parametrize("index", range(3))
def test_actual_disclosed_and_derived_support_differ_but_answer_matches(sources, index):
    adapter = BoundShareTaskAdapter(sources[index])
    d_claims, d_final = _route(adapter, "D")
    s_claims, s_final = _route(adapter, "S")
    assert d_final["result"] == s_final["result"]
    evidence = sources[index].evidence
    assert set(d_final["citations"]) == {
        evidence["target_component"]["id"],
        evidence["disclosed_total"]["id"],
    }
    assert set(s_final["citations"]) == {
        evidence[role]["id"]
        for role in ("target_component", "other_component", "composition_relation")
    }
    assert len(d_claims) == 2 and len(s_claims) == 3
    assert adapter.offers(s_claims) == []


@pytest.mark.parametrize("left,right", [(0, 1), (1, 2), (2, 1)])
def test_cross_task_accepted_claim_rejected_before_arithmetic(sources, left, right):
    first = BoundShareTaskAdapter(sources[left])
    second = BoundShareTaskAdapter(sources[right])
    total = _claim(first, [], "relation_sum")
    with pytest.raises(ProtocolError, match="cross_task_claim"):
        second.offers([total])


def test_claim_period_or_metric_rewriting_is_rejected(sources):
    adapter = BoundShareTaskAdapter(sources[1])
    total = _claim(adapter, [], "relation_sum")
    for key, value in (("period", "2015"), ("metric", "total_operating_revenues")):
        changed = copy.deepcopy(total)
        changed["proposition"]["output"][key] = value
        with pytest.raises(ProtocolError, match="claim_metadata"):
            adapter.offers([changed])


def test_disclosed_total_cannot_be_laundered_into_reconstructed_support(sources):
    adapter = BoundShareTaskAdapter(sources[2])
    total = _claim(adapter, [], "relation_sum")
    bad = copy.deepcopy(total)
    wrong_lineage = [sources[2].evidence["disclosed_total"]["id"]]
    bad["proposition"]["lineage"] = wrong_lineage
    bad["proposition"]["output"]["lineage"] = wrong_lineage
    offered = next(
        item
        for item in adapter.offers([bad])
        if item["operation"] == "share_ratio" and item["semantic_choice"] == "reconstructed_total"
    )
    with pytest.raises(ProtocolError, match="actual_reconstructed_support"):
        adapter.prepare(offered, [bad])


def test_action_metadata_rewrite_cannot_change_actual_evidence(sources):
    adapter = BoundShareTaskAdapter(sources[0])
    before = canonical_json_bytes(sources[0].binding_record)
    offer = copy.deepcopy(adapter.offers([])[0])
    offer["inputs"][0]["ref_id"] = sources[1].evidence["target_component"]["id"]
    with pytest.raises(ProtocolError, match="offer_not_current"):
        adapter.prepare(offer, [])
    assert canonical_json_bytes(sources[0].binding_record) == before


def test_sum_then_disclosed_path_keeps_actual_final_citations_not_unused_sum(sources):
    adapter = BoundShareTaskAdapter(sources[1])
    claims = [_claim(adapter, [], "relation_sum")]
    claims.append(_claim(adapter, claims, "share_ratio", "disclosed_total"))
    claims.append(_claim(adapter, claims, "scale_percent"))
    assert set(claims[-1]["proposition"]["lineage"]) == {
        sources[1].evidence["target_component"]["id"],
        sources[1].evidence["disclosed_total"]["id"],
    }


def test_wrong_numeric_output_and_extra_citation_fail(sources):
    adapter = BoundShareTaskAdapter(sources[0])
    offered = adapter.offers([])[0]
    prepared = adapter.prepare(offered, [])
    proposition = adapter.execute(prepared)
    proposition["output"]["value"] = "1"
    assert not adapter.verify_execution(prepared, proposition)
    claims, final = _route(adapter, "D")
    final["citations"] = [*final["citations"], sources[0].evidence["other_component"]["id"]]
    assert not adapter.verify_final(final, claims)["qa_valid"]


def test_contamination_alias_and_fact_overlap_are_not_independent_tasks(sources):
    ledger = source.contamination_registry(sources)
    assert ledger == source.contamination_registry(list(reversed(sources)))
    assert ledger["source_group_count"] == 4
    assert ledger["same_page_alias_record_count"] == 12
    assert len(ledger["exact_repeated_fact_links"]) == 8
    assert len(ledger["comparative_value_differences"]) == 4
    assert ledger["evaluation_readiness"] == "not_ready"
    assert ledger["clean_evaluation_task_count"] == 0
    assert all(row["exact_task_duplicate"] is False for row in ledger["exact_repeated_fact_links"])
    jpm_repeat = [
        row
        for row in ledger["exact_repeated_fact_links"]
        if row["left"]["subject"].startswith("JPMorgan")
    ]
    assert {row["left"]["metric"] for row in jpm_repeat} == {"Net interest income"}
    assert {row["left"]["period"] for row in jpm_repeat} == {"2013", "2014"}
    assert "not established" in ledger["difference_cause"]


def test_archive_identity_tamper_is_rejected_before_binding(monkeypatch):
    read = Path.read_bytes

    def changed(path):
        payload = read(path)
        return payload + b" " if path == ROOT / source.ARCHIVE_PATH else payload

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ProtocolError, match="archive_identity"):
        source.load_sources(ROOT)
