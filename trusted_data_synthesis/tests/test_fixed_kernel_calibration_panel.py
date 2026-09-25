"""Synthetic CPU controls only; never download or open production task bodies."""

import copy
import hashlib
import json

import fixed_kernel_calibration_panel_20260926 as m
import pytest
from finraw.db.schema import SOURCE_REGISTRY_SEED
from finraw.metric_ontology import SEC_METRICS
from test_qa_vnext_catalog_bridge_panels import fixture


def dev_ciks(count=64):
    return [
        str(i).zfill(10)
        for i in range(1, 10000)
        if m.source_split("cik:" + str(i).zfill(10)) == "dev"
    ][:count]


def registration(tmp_path):
    return {
        "id": "synthetic_registered_sources:test",
        "selection_rule": {"mode": "synthetic_metadata_only_fixed_inventory"},
        "sources": [
            {
                "cik": cik,
                "ticker": "SYN" + str(i),
                "title": "Synthetic " + str(i),
                "path": str(tmp_path / (cik + ".json")),
                "sha256": "1" * 64,
                "bytes": 100,
            }
            for i, cik in enumerate(dev_ciks())
        ],
    }


def synthetic_snapshot(tmp_path, cik):
    _facts, _bindings, _usage, payloads = fixture()
    payload = copy.deepcopy(next(iter(payloads.values())))
    payload["cik"] = int(cik)
    payload["entityName"] = "Synthetic " + cik
    path = tmp_path / (cik + ".json")
    raw = json.dumps(payload, sort_keys=True).encode()
    path.write_bytes(raw)
    return {
        "cik": cik,
        "ticker": "SYN" + cik,
        "title": payload["entityName"],
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def test_registration_exact_frozen_inventory_without_source_reads(tmp_path):
    value = registration(tmp_path)
    assert m._registered_rows(value, set()) == value["sources"]
    assert not list(tmp_path.iterdir())
    assert m.policy()["source_acquisition_or_model_calls"] == 0
    assert m.policy()["native_annual_years"] == [2010, 2025]


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("count", "exact64"),
        ("duplicate", "unique64"),
        ("old", "no_old_CIK"),
        ("history", "historical_confirmation_ticker"),
        ("split", "original_dev_source_split"),
        ("relative", "exact_absolute_source"),
        ("bytes", "byte_identity"),
        ("rule", "selection_rule"),
    ],
)
def test_metadata_rejections_precede_snapshot_reads(tmp_path, mutation, code):
    value = registration(tmp_path)
    old = set()
    if mutation == "count":
        value["sources"].pop()
    elif mutation == "duplicate":
        value["sources"][1] = copy.deepcopy(value["sources"][0])
    elif mutation == "old":
        old.add("cik:" + value["sources"][0]["cik"])
    elif mutation == "history":
        value["sources"][0]["ticker"] = "AAPL"
    elif mutation == "split":
        value["sources"][0]["cik"] = next(
            str(i).zfill(10)
            for i in range(1, 100)
            if m.source_split("cik:" + str(i).zfill(10)) == "train"
        )
    elif mutation == "relative":
        value["sources"][0]["path"] = "relative.json"
    elif mutation == "bytes":
        value["sources"][0]["bytes"] = True
    elif mutation == "rule":
        value["selection_rule"] = {}
    with pytest.raises(ValueError, match=code):
        m._registered_rows(value, old)


def test_narrow_resolver_preserves_original_numeric_selection(tmp_path):
    row = synthetic_snapshot(tmp_path, dev_ciks(1)[0])
    item, payload = m._read_source(row)
    expected = m.panel_native.select_native(
        payload, item["entity"], item["raw_object"], expected_split="dev"
    )
    assert (item["observations"], item["definitions"], item["selection_exclusions"]) == expected
    assert len(item["observations"]) == 18
    assert item["entity"]["fiscal_year_end"] is None
    assert item["source_cluster"] == "cik:" + row["cik"]


def test_narrow_resolver_rejects_changed_bytes_and_symlink(tmp_path):
    row = synthetic_snapshot(tmp_path, dev_ciks(1)[0])
    wrong = {**row, "sha256": "0" * 64}
    with pytest.raises(ValueError, match="source_bytes_unchanged"):
        m._read_source(wrong)
    linked = tmp_path / "alias.json"
    linked.symlink_to(row["path"])
    with pytest.raises(ValueError, match="no_symlink"):
        m._read_source({**row, "path": str(linked)})


def test_new_enumeration_uses_no_old_priority_and_is_input_order_independent():
    facts, bindings, usage, payloads = fixture()
    first, rejected = m.panel_rules.enumerate_all(facts, bindings, usage, "dev", payloads, [])
    second, _ = m.panel_rules.enumerate_all(
        dict(reversed(list(facts.items()))), bindings, usage, "dev", payloads, []
    )
    assert not rejected
    assert first == second
    assert all(first[group] for group in m.GROUPS)


class SyntheticOntology:
    def __init__(self, _path):
        self.closed = False

    def fetchall(self, sql, _params=()):
        if sql == "SELECT * FROM metrics":
            return copy.deepcopy(SEC_METRICS)
        if sql == "SELECT * FROM source_metric_definitions":
            return []
        raise AssertionError("Unexpected archive read: " + sql)

    def fetchone(self, sql, _params=()):
        assert "source_registry" in sql and "sec_companyfacts" in sql
        source = next(row for row in SOURCE_REGISTRY_SEED if row["source_id"] == "sec_companyfacts")
        return {"properties_json": json.dumps(source)}

    def close(self):
        self.closed = True


class SyntheticTokenizer:
    def apply_chat_template(self, messages, **_kwargs):
        return messages

    def __call__(self, _rendered, **_kwargs):
        return {"input_ids": [1] * 100}


def test_real_synthetic_fact_kg_qa_and_compact_view_pipeline(tmp_path, monkeypatch):
    """Real builders and real private reference logic; only archived ontology is synthetic."""
    monkeypatch.setattr(m, "_ReadOnlyOntology", SyntheticOntology)
    monkeypatch.setattr(m, "_tokenizer", lambda _root: SyntheticTokenizer())
    rows = [synthetic_snapshot(tmp_path, cik) for cik in dev_ciks(2)]
    loaded = [m._read_source(row) for row in rows]
    inputs = [item for item, _payload in loaded]
    payloads = {item["raw_object"]["raw_object_id"]: payload for item, payload in loaded}
    private = tmp_path / "private"
    private.mkdir()
    db, bindings, native = m._build_native(tmp_path, private, inputs)
    try:
        kg = native["kg_build"]
        assert kg["quality_status"] == "passed"
        assert len(bindings) == 36
        facts = m.pipeline._load_facts_by_id(
            db, list(bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
        )
        usage = {
            key: {k: row[k] for k in ("split", "allowed_uses", "source_cluster")}
            for key, row in bindings.items()
        }
        candidates, failures = m.panel_rules.enumerate_all(
            facts, bindings, usage, "dev", payloads, []
        )
        assert not failures
        sources = m.original.public_source_index(inputs, facts, bindings, private)
        selected, rejected = m._compile_candidates(
            db, kg, candidates, facts, bindings, usage, sources, private, "synthetic:registration"
        )
        assert not rejected
        assert all(any(row["family"] == group for row in selected) for group in m.GROUPS)
        assert len(selected) < 180  # shortage is retained, never replenished
        compiled, checks, failures = m._views(
            tmp_path,
            tmp_path / "public",
            private,
            selected,
            sources,
            payloads,
            {"id": "synthetic:registration"},
            m.policy(),
        )
        assert not failures
        assert len(compiled) == len(selected)
        assert all(row["passed"] for row in checks)
        assert all("private" not in row for row in compiled)
        assert json.loads((private / "uncompiled_overflow.json").read_text()) == dict.fromkeys(
            m.GROUPS, []
        )
        m.dump_parents(db, private)
        assert (private / "parent_table_inventory.json").is_file()
    finally:
        db.close()


def test_top_level_shortage_is_blocked_and_private_assets_remain_isolated(tmp_path, monkeypatch):
    """Two-source synthetic inventory exercises shortage; production count stays 64."""
    monkeypatch.setattr(m, "SOURCE_COUNT", 2)
    monkeypatch.setattr(m, "_source_root", lambda _root: tmp_path)
    monkeypatch.setattr(m, "_ReadOnlyOntology", SyntheticOntology)
    monkeypatch.setattr(m, "_tokenizer", lambda _root: SyntheticTokenizer())
    m.write_json(
        tmp_path / m.HISTORICAL_METADATA,
        {"rows": [{"source_cluster": "cik:" + str(9000000000 + i)} for i in range(100)]},
    )
    value = {
        "id": "synthetic_registered_sources:shortage",
        "selection_rule": {"mode": "synthetic_only"},
        "sources": [synthetic_snapshot(tmp_path, cik) for cik in dev_ciks(2)],
    }
    output = tmp_path / "panel"
    result = m.build(tmp_path, value, output)
    assert result["admission"]["passed"] is False
    assert result["admission"]["status"] == "BLOCKED_PANEL_CONTRACT"
    assert sum(result["admission"]["shortages"].values()) > 0
    assert result["admission"]["model_calls"] == 0
    assert result["private_assets"]["private_scoring_authorized"] is False
    assert all("/private/" in row["path"] for row in result["private_assets"]["bundles"])
    assert all("/public/views/" in row["path"] for row in result["manifest"]["tasks"])
    assert (output / "admission.json").is_file()
    assert not (output / "failure.json").exists()
    with pytest.raises(ValueError, match="new_absolute_output"):
        m.build(tmp_path, value, output)
