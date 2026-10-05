"""CPU/mock-only V24 population audit contracts; no saved outcomes accessed."""

import importlib.util
import json
import socket
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/finqa_v24_public_population_audit.py"
SPEC = importlib.util.spec_from_file_location("v24_public_population_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


@pytest.fixture(autouse=True)
def forbid_network_and_private_reads(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network/API call forbidden in CPU public audit")

    monkeypatch.setattr(socket, "socket", forbidden)
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        assert "private.references" not in str(path)
        assert "v23_confirmation" not in str(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)


def sample(question="What percentage increase occurred?"):
    task = {
        "dataset": "finqa",
        "task_id": "ACME/2018/page_1.pdf-1",
        "question": question,
        "sources": [
            {"kind": "text", "content": "public text"},
            {"kind": "table", "content": [["header", "2018"], ["sales", "20"]]},
        ],
    }
    lineage = {
        "dataset": "finqa",
        "original_id": task["task_id"],
        "original_split": "train",
        "company": "ACME",
        "year": "2018",
        "report": "ACME/2018",
        "source_group": "finqa:report:ACME/2018",
    }
    return task, lineage


def test_freeze_is_immutable_and_id_bound(tmp_path):
    first = audit.freeze(tmp_path)
    assert first == audit.freeze(tmp_path)
    assert first["rules_id"] == audit.digest(first["rules"])
    assert first["id"] == audit.digest({k: v for k, v in first.items() if k != "id"})
    with pytest.raises(ValueError, match="immutable"):
        audit.write_once(tmp_path / "grouping_protocol.json", {"replaced": True})


def test_public_only_features_and_priority():
    task, lineage = sample()
    row = audit.task_features(task, lineage, "sft")
    assert row["intent_proxy"] == "percent_change"
    assert row["intent_flags"] == ["percent_change", "difference_change", "ratio_percentage"]
    assert row["input_chars"] == len(task["question"]) + sum(
        len(json.dumps(s["content"], ensure_ascii=False, separators=(",", ":")))
        for s in task["sources"]
    )
    assert row["table_rows"] == 2 and row["table_columns"] == 2
    assert row["report_group"] == "finqa:report:ACME/2018"
    assert "question" not in row and "sources" not in row and "strata" not in row


def test_lineage_projection_never_accesses_strata_or_unlisted_metadata():
    _, lineage = sample()

    class GuardedLineage(dict):
        def __getitem__(self, key):
            assert key in audit.LINEAGE_WHITELIST
            return super().__getitem__(key)

        def items(self):
            raise AssertionError("do not iterate arbitrary lineage values")

    guarded = GuardedLineage({**lineage, "strata": object(), "private_gold": object()})
    assert audit.public_lineage_metadata(guarded) == lineage


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What is the difference in total revenue?", "difference_change"),
        ("What is the ratio of total revenue?", "ratio_percentage"),
        ("What is the total average revenue?", "sum_total"),
        ("What is the average revenue?", "average"),
        ("What is the highest value?", "minmax"),
        ("How many outstanding units?", "count"),
        ("What was revenue in 2018?", "other"),
    ],
)
def test_fixed_intent_lexical_rules(question, expected):
    task, lineage = sample(question)
    assert audit.task_features(task, lineage, "sft")["intent_proxy"] == expected


@pytest.mark.parametrize(
    "size,expected",
    [
        (0, "<=2000"),
        (2000, "<=2000"),
        (2001, "2001-5000"),
        (5000, "2001-5000"),
        (5001, "5001-10000"),
        (10000, "5001-10000"),
        (10001, ">10000"),
    ],
)
def test_input_bin_boundaries(size, expected):
    assert audit.size_bin(size, audit.INPUT_BINS) == expected


@pytest.mark.parametrize(
    "size,expected",
    [
        (79, "<=79"),
        (80, "80-119"),
        (119, "80-119"),
        (120, "120-199"),
        (199, "120-199"),
        (200, ">=200"),
    ],
)
def test_question_bin_boundaries(size, expected):
    assert audit.size_bin(size, audit.QUESTION_BINS) == expected


def test_lineage_taxonomy_mismatch_rejected():
    task, lineage = sample()
    lineage["source_group"] = "other"
    with pytest.raises(ValueError, match="taxonomy"):
        audit.task_features(task, lineage, "sft")


def test_malformed_public_table_recorded_not_inferred():
    task, lineage = sample()
    task["sources"].append({"kind": "table", "content": "not rows"})
    row = audit.task_features(task, lineage, "sft")
    assert row["invalid_table_count"] == 1
    assert row["table_rows"] == 2


def test_concentration_and_distances_are_task_weighted():
    row = audit.concentration({"a": 3, "b": 1})
    assert row["hhi"] == 0.625
    assert row["equivalent_source_diversity"] == 1.6
    assert row["not_statistical_ESS"] is True
    assert row["top1_mass"] == 0.75
    assert row["group_size_quantiles"]["0.5"] == 2
    assert audit.distance({"a": 1}, {"b": 1}) == {"tv": 1.0, "js_base2": 1.0}
    assert audit.distance({"a": 1}, {"a": 2}) == {"tv": 0.0, "js_base2": 0.0}


def test_overlap_reports_bidirectional_task_mass_not_only_source_count():
    features = {
        "a": {"company": "X"},
        "b": {"company": "X"},
        "c": {"company": "Y"},
        "d": {"company": "X"},
        "e": {"company": "Z"},
    }
    result = audit.overlap(["a", "b", "c"], ["d", "e"], features, "company")
    assert result["shared_sources"] == 1
    assert result["left_task_mass_in_shared_sources"] == 2 / 3
    assert result["right_task_mass_in_shared_sources"] == 1 / 2
    assert result["task_id_intersection"] == 0


def test_private_and_running_experiment_paths_forbidden():
    with pytest.raises(ValueError, match="private"):
        audit.read_json(Path("private.references.jsonl"))
    with pytest.raises(ValueError, match="V23"):
        audit.read_json(Path("v23_confirmation_shrink_01/result.json"))


def test_script_import_does_not_load_models_or_network_clients():
    import ast

    tree = ast.parse(SCRIPT.read_text())
    imports = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imports |= {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not imports & {
        "torch",
        "transformers",
        "requests",
        "httpx",
        "openai",
        "trusted_synthesis",
    }
