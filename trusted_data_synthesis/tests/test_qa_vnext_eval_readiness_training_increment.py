"""Finite-source, cached-admission, zero-new-task and request-budget controls."""

import copy
import json
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.budget import IncrementLedger
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import source_policy as policy
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import (
    training_increment as increment,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import write_json
from trusted_synthesis.experiments.finance_qa_vnext_task_build.protocol import METRIC_TAGS


def source_fixture():
    return {
        "sources": [
            {
                "entity": {"entity_id": policy.ENTITY, "cik": "100885"},
                "document": {
                    "entity_id": policy.ENTITY,
                    "period_end": end,
                    "raw_object_id": raw,
                    "document_id": "doc_" + end,
                    "form_type": "10-K",
                },
                "raw_object": {"raw_object_id": raw},
            }
            for end, raw in policy.RAW_IDS.items()
        ]
    }


def cached_issuer():
    return {
        **source_fixture(),
        "observations": [{"entity_id": "CSCO_US", "source_cluster": "old", "payload": "untouched"}],
        "tables": [{"id": "old_table", "payload": "untouched"}],
        "failures": [{"reason": "prior_FAIL_preserved"}],
        "older_vintage_exclusions": [{"status": "prior_older_preserved"}],
        "counts": {},
    }


def new_observation(year=2024, *, filing="2025-02-07", table="new_table"):
    return {
        "entity_id": policy.ENTITY,
        "source_cluster": policy.CIK,
        "period_start": f"{year}-01-01",
        "period_end": f"{year}-12-31",
        "filing_date": filing,
        "document_id": "doc_" + filing,
        "table_id": table,
    }


def task(identifier, *, cluster=policy.CIK, family="company_defined_metric"):
    return {"task_id": identifier, "family": family, "target": {"source_cluster": cluster}}


def ledger(tmp_path, **kwargs):
    return IncrementLedger(
        tmp_path / "budget.sqlite",
        "freeze-test",
        prior_debits=[{"id": "old", "tokens": 221538}],
        request_cap=kwargs.get("request_cap", 34),
        token_cap=kwargs.get("token_cap", 330752),
    )


def test_policy_fixes_six_existing_sources_and_seventeen_real_tasks():
    value = policy.policy()
    assert value["new_task_cap"] == 17
    assert value["rewrite_request_cap"] == 34
    assert value["rewrite_token_cap"] == 34 * (8192 + 1536)
    assert value["previous_known_common_debit"] == 221538
    assert value["new_HTTP_requests"] == value["Oracle_403_retries"] == 0
    assert len(policy.select_sources(source_fixture())) == 6


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "wrong_raw",
        "wrong_date",
        "duplicate",
        "wrong_cik",
        "wrong_document_entity",
        "wrong_document_raw",
        "not_10k",
    ],
)
def test_source_metadata_requires_exact_fixed_original_parent(mutation):
    cached = source_fixture()
    first = cached["sources"][0]
    if mutation == "extra":
        cached["sources"].append(copy.deepcopy(first))
    elif mutation == "missing":
        cached["sources"].pop()
    elif mutation == "wrong_raw":
        first["raw_object"]["raw_object_id"] = "replacement"
    elif mutation == "wrong_date":
        first["document"]["period_end"] = "2019-12-31"
    elif mutation == "duplicate":
        cached["sources"][1] = copy.deepcopy(first)
    elif mutation == "wrong_cik":
        first["entity"]["cik"] = "100884"
    elif mutation == "wrong_document_entity":
        first["document"]["entity_id"] = "ORCL_US"
    elif mutation == "wrong_document_raw":
        first["document"]["raw_object_id"] = "replacement"
    else:
        first["document"]["form_type"] = "10-Q"
    with pytest.raises(ValueError):
        policy.select_sources(cached)


def test_cached_observations_not_reselected_from_current_taxonomy_units(tmp_path, monkeypatch):
    tag = METRIC_TAGS["revenue"][0]
    definition = {"label": "Revenue", "description": "Native revenue definition"}
    path = tmp_path / "source.json"
    path.write_text(
        json.dumps(
            {"facts": {"us-gaap": {tag: {**definition, "units": {"USD": [{"val": 999999}]}}}}}
        )
    )
    observations = {
        str(i): {
            "entity_id": "X",
            "raw_object_id": "raw",
            "tag": tag,
            "record": {"val": i},
            "native_definition": definition,
        }
        for i in range(1995)
    }
    inventory = [
        {
            "entity": {"entity_id": "X"},
            "raw_object": {"raw_object_id": "raw"},
            "selection_exclusions": {"old": 5},
        }
    ]
    parent = SimpleNamespace(
        read=lambda name: observations if name == "native_bindings.json" else inventory
    )
    monkeypatch.setattr(policy.native_facts, "resolve_raw", lambda root, raw: path)
    monkeypatch.setattr(
        policy.native_facts,
        "select_native",
        lambda *a: pytest.fail("old observation selector invoked"),
    )
    result = policy.cached_inputs(tmp_path, parent)
    assert result[0]["observations"] == list(observations.values())
    assert result[0]["selection_exclusions"] == {"old": 5}
    assert result[0]["definitions"][tag] == definition


def test_old_cache_unchanged_new_latest_legally_admitted_selected_once():
    cached = cached_issuer()
    before = copy.deepcopy(cached)
    results = [
        {
            "observations": [new_observation(filing="2025-02-07", table="newest")],
            "tables": [{"id": "newest"}],
            "failures": [{"reason": "new_rejection"}],
        },
        {
            "observations": [new_observation(filing="2024-02-07", table="older")],
            "tables": [{"id": "older"}],
            "failures": [],
        },
    ]
    result = increment.append_qualified_sources(cached, results)
    assert cached == before
    assert result["observations"][0] == before["observations"][0]
    assert result["tables"][0] == before["tables"][0]
    assert result["observations"][1]["table_id"] == "newest"
    assert result["older_vintage_exclusions"][-1]["table_id"] == "older"
    assert result["failures"] == [*before["failures"], {"reason": "new_rejection"}]


def test_unregistered_new_issuer_observation_rejected():
    bad = new_observation()
    bad["entity_id"] = "ORCL_US"
    with pytest.raises(ValueError, match="only_UNP"):
        increment.append_qualified_sources(cached_issuer(), [{"observations": [bad]}])


def test_six_failures_retained_without_replaying_old_sources(tmp_path, monkeypatch):
    cached = cached_issuer()
    monkeypatch.setattr(policy, "validate_metadata", lambda *a: None)
    monkeypatch.setattr(policy, "cache_parent", lambda *a: SimpleNamespace(read=lambda *a: cached))
    monkeypatch.setattr(
        policy,
        "cached_inputs",
        lambda *a: [{"entity": {"entity_id": policy.ENTITY}, "observations": []}],
    )
    calls = []

    def parse(root, source, observations):
        calls.append(source["document"]["document_id"])
        raise ValueError("synthetic fixed-source rejection")

    monkeypatch.setattr(increment.issuer_tables, "parse_document", parse)
    _, issuer = increment.prepared_context(tmp_path, None, {"selected_sources": cached["sources"]})
    assert len(calls) == len(set(calls)) == 6
    assert issuer["observations"] == cached["observations"]
    assert len(issuer["failures"]) == 7


@pytest.mark.parametrize("count", [0, 1, 16, 17, 18, 27, 54])
def test_only_seventeen_new_ids_selected_with_overflow_retained(count):
    selected = {"company_defined_metric": [task("old"), *[task(str(i)) for i in range(count)]]}
    new, overflow = increment.select_new_tasks(selected, {"old"})
    assert len(new) == min(17, count)
    assert len(overflow) == max(0, count - 17)
    assert "old" not in {row["task_id"] for row in new}


@pytest.mark.parametrize(
    "selected",
    [
        {"company_defined_metric": [task("a", cluster="cik:other")]},
        {"company_defined_metric": [task("a", family="control")]},
        {"company_defined_metric": [task("a"), task("a")]},
        {"control": [task("a")]},
    ],
)
def test_no_extra_source_family_or_duplicate_tasks(selected):
    with pytest.raises(ValueError):
        increment.select_new_tasks(selected, set())


def test_exact_new_ledger_preflight_and_existing_debit(tmp_path):
    value = ledger(tmp_path)
    increment.check_ledger(value, {"id": "freeze-test"})
    assert value.snapshot()["remaining_registered_global_allowance"] == 1000000000 - 221538


@pytest.mark.parametrize(
    "overrides",
    [{"request_cap": 54}, {"request_cap": 35}, {"token_cap": 525312}, {"token_cap": 330753}],
)
def test_wrong_suballocation_rejected_before_requests(tmp_path, overrides):
    with pytest.raises(ValueError, match="preallocated"):
        increment.check_ledger(ledger(tmp_path, **overrides), {"id": "freeze-test"})


def test_zero_new_tasks_seals_catalog_and_real_registry_without_provider(tmp_path, monkeypatch):
    metadata = {
        "old_task_ids": [str(i) for i in range(243)],
        "id": "metadata",
        "cache_parent": {"manifest_id": policy.CACHE_MANIFEST},
        "catalog_parent": {"manifest_id": policy.BRIDGE_MANIFEST},
    }
    frozen = {"id": "freeze-test", "git_commit": "git", "training_source_metadata": metadata}
    monkeypatch.setattr(policy, "validate_metadata", lambda *a: None)

    def native(root, output, **kwargs):
        assert callable(kwargs["prepared_context"])
        write_json(output / "native_bindings.json", {})
        return {"kg_build": {"input_fact_build_id": "fact", "input_entity_build_id": "entity"}}

    monkeypatch.setattr(increment.native_facts, "run", native)
    monkeypatch.setattr(increment, "RecordDB", lambda *a: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(increment.pipeline, "_load_facts_by_id", lambda *a: {})
    monkeypatch.setattr(increment.pipeline, "ensure_qa_schema", lambda *a: None)
    monkeypatch.setattr(increment.factory, "dump_parents", lambda *a: {"test_double_only": True})
    monkeypatch.setattr(
        increment.factory,
        "compile_batch",
        lambda *a, **kw: pytest.fail("zero-task compiler invoked"),
    )
    monkeypatch.setattr(
        increment, "Provider", lambda *a: pytest.fail("zero-task provider constructed")
    )
    monkeypatch.setattr(increment, "realization_stats", lambda *a: {"request_count": 0})
    value = ledger(tmp_path)
    report = increment.run(tmp_path, "output", "work", frozen, value, "test-not-a-key")
    assert report["tasks"] == report["registered_targets"] == 0
    assert json.loads((tmp_path / "output/new_tasks/pattern_compilations.json").read_text()) == []
    assert (tmp_path / "output/manifest.json").is_file()
    assert value.snapshot()["request_reservations"] == 0
    with pytest.raises(ValueError, match="one_new_output"):
        increment.run(tmp_path, "output", "work", frozen, value, "test-not-a-key")


@pytest.mark.parametrize("directory", ["../escape", "/tmp/escape", "."])
def test_unsafe_or_existing_output_rejected_before_state(tmp_path, directory):
    with pytest.raises(ValueError):
        increment.run(tmp_path, directory, "work", {}, None, "test-not-a-key")
