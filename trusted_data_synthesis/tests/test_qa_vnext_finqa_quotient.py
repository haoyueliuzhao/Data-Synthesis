"""Only the new finite quotient/materialization boundary; no old qualification rerun."""

import copy
import json
from pathlib import Path

import pytest

from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.experiments.finance_qa_vnext_finqa_quotient import (
    judgments,
    measurement,
    source,
    stage,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_quotient import projection as graph
from trusted_synthesis.experiments.finance_qa_vnext_finqa_quotient.rules import VALID

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def data():
    with stage.zero_execution() as counts:
        pop = source.population(ROOT)
        sessions = {
            r["label"]: source.load_session(ROOT, r) for r in pop["rows"] if r["complete_valid"]
        }
        reviews = {label: judgments.review_session(s) for label, s in sessions.items()}
        projections = {label: graph.project(s, reviews[label]) for label, s in sessions.items()}
        assert not any(counts.values())
    return pop, sessions, reviews, projections


def test_existing_population_keeps_eight_failures_and_condition_weights(data):
    pop, sessions, _, _ = data
    assert len(pop["rows"]) == 8 and len(sessions) == 3
    assert sum(not r["complete_valid"] for r in pop["rows"]) == 5
    assert {r["label"] for r in pop["rows"] if r["complete_valid"]} == set(VALID)
    assert pop["original_task_weights"] == {v: {"E1": "1/2", "J2": "1/2"} for v in ("V0", "V1")}
    assert sum(r["submissions"] for r in pop["rows"]) == 212


def test_failure_cannot_export_successful_prefix(data):
    failure = next(r for r in data[0]["rows"] if not r["complete_valid"])
    with pytest.raises(ProtocolError, match="success_only"):
        source.load_session(ROOT, failure)


def test_all_52_original_bindings_and_49_exact_candidates(data):
    rows = []
    for session in data[1].values():
        for turn in session["turns"]:
            if not turn["event"]["admitted"]:
                with pytest.raises(ProtocolError, match="admitted_only"):
                    source.candidate(session, turn)
                continue
            row = source.candidate(session, turn)
            assert row["target_text"].encode() == turn["raw"]
            assert row["messages"] == json.loads(turn["contents"]["http_request"])["messages"]
            assert row["host_display_is_target"] is False
            assert ("accepted_result_bindings" in json.loads(row["messages"][1]["content"])) == (
                row["view_condition"] == "V1"
            )
            rows.append(row)
    assert sum(len(s["turns"]) for s in data[1].values()) == 52
    assert len(rows) == 49
    assert sum(r["disposition"] == "reject" for r in rows) == 1
    assert sum(r["submission_kind"] == "action" for r in rows) == 23
    assert sum(r["submission_kind"] == "update" for r in rows) == 23
    assert sum(r["submission_kind"] == "final" for r in rows) == 3


@pytest.mark.parametrize(
    "name", ["raw_response", "http_request", "http_response", "outcome", "request"]
)
def test_cross_turn_bytes_or_host_rewrite_rejected(data, tmp_path, name):
    session = data[1]["J2_E_V1_01"]
    original, replacement = session["turns"][0], session["turns"][2]
    for key, binding in original["binding"]["files"].items():
        path = tmp_path / binding["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(replacement["contents"][key] if key == name else original["contents"][key])
    with pytest.raises(ProtocolError):
        source.bind_turn(tmp_path, 0, session["row"]["registration"])


def test_all_26_public_action_reviews_and_unspecified_current_object(data):
    assert sum(len(r["annotations"]) for r in data[2].values()) == 26
    annotation = next(a for a in data[2]["J2_E_V1_01"]["annotations"] if a["submission"] == 6)
    assert "current_period:unspecified" in annotation["public_commitments"]
    assert "assert:price:2016=26.93,2017=33.32" in annotation["public_commitments"]
    assert annotation["status"] == "REVIEWED"  # not an invented current-year intent-MATCH


@pytest.mark.parametrize("mutation", ["quote", "missing", "duplicate"])
def test_judgment_quote_and_full_denominator(data, mutation):
    label = "J2_E_V1_01"
    review = copy.deepcopy(data[2][label])
    if mutation == "quote":
        review["annotations"][0]["reason_quote"] = "invented justification"
    elif mutation == "missing":
        review["annotations"].pop()
    else:
        review["annotations"].append(review["annotations"][0])
    with pytest.raises(ProtocolError):
        graph.project(data[1][label], review)


def test_unused_duplicate_is_not_actual_final_ancestor(data):
    p = data[3]["J2_E_V1_01"]
    assert p["status"] == "MAPPED" and p["actual_operations"] == 8
    assert p["retained_unadmitted"] == 2 and p["final_support_operations"] == 7
    assert p["retained_actual_off_support"] == ["action:13"]
    assert p["evidence"]["action:11"]["in_actual_final_ancestry"]
    assert not p["evidence"]["action:13"]["in_actual_final_ancestry"]
    assert p["evidence"]["action:13"]["duplicate_of"] == "action:11"
    assert "action:13" not in p["support_graph"]["nodes"]


def test_real_reject_and_proposal_remain_distinct_from_clean_support(data):
    p = data[3]["J2_E_V0_02"]
    assert p["graph"]["nodes"]["action:6"]["disposition"] == "reject"
    assert p["graph"]["nodes"]["action:6"]["output"]["exact_value"] == "-2"
    assert p["retained_actual_off_support"] == ["action:6"]
    assert p["evidence"]["action:6"]["accepted_claim_id"] is None
    assert p["graph"]["nodes"]["action:5"]["kind"] == "unadmitted_action"
    assert ["action:5", "action:6", "adjustment_order"] in p["graph"]["edges"]
    assert ["action:6", "action:8", "adjustment_order"] in p["graph"]["edges"]


def renamed(g):
    ids = {old: f"renamed:{i}" for i, old in enumerate(reversed(g["nodes"]))}
    return {
        "binding": g["binding"],
        "nodes": {ids[n]: label for n, label in reversed(list(g["nodes"].items()))},
        "edges": [[ids[a], ids[b], role] for a, b, role in reversed(g["edges"])],
    }


def test_id_renaming_independent_serialization_and_explicit_bijection(data):
    p = data[3]["J2_E_V1_02"]["graph"]
    result = graph.compare(p, renamed(p))
    assert result["relation"] == "EQUIVALENT"
    assert len(result["mapping"]) == len(p["nodes"]) and result["edge_multiset_checked"]


def test_multiply_commutes_but_subtraction_does_not():
    a, b = "source:2017_price", "source:2016_price"
    assert graph.expression({"op": "multiply", "args": [a, b]}) == graph.expression(
        {"op": "multiply", "args": [b, a]}
    )
    assert graph.expression({"op": "subtract", "args": [a, b]}) != graph.expression(
        {"op": "subtract", "args": [b, a]}
    )


@pytest.mark.parametrize(
    "change", ["year_source", "raw_claim", "subtract_order", "public_judgment"]
)
def test_different_source_same_number_and_wrong_input_not_commutation(data, change):
    original = data[3]["J2_E_V1_02"]["graph"]
    mutated = copy.deepcopy(original)
    if change == "year_source":
        for edge in mutated["edges"]:
            if edge[0] == "source:q0n2" and edge[1] == "action:1":
                edge[0] = "source:q0n3"
    elif change == "raw_claim":
        for edge in mutated["edges"]:
            if edge[1] == "action:9" and edge[2] == "factor:accepted_claim":
                edge[2] = "factor:raw_source"
                break
    elif change == "subtract_order":
        for edge in mutated["edges"]:
            if edge[1] == "action:13" and edge[2].startswith("input:"):
                edge[2] = (
                    edge[2]
                    .replace("input:0", "input:X")
                    .replace("input:1", "input:0")
                    .replace("input:X", "input:1")
                )
    else:
        mutated["nodes"]["action:9"]["public_commitments"] = ["assert:price:2017=26.93"]
    assert graph.compare(original, mutated)["relation"] == "DIFFERENT"


def test_same_value_source_identity_is_not_erased():
    original = {
        "binding": {"task": "synthetic"},
        "nodes": {
            "a": {"kind": "source", "identity": "2017", "value": 7},
            "b": {"kind": "source", "identity": "2016", "value": 7},
            "read": {"kind": "read"},
        },
        "edges": [["a", "read", "input:0"]],
    }
    changed = copy.deepcopy(original)
    changed["edges"][0][0] = "b"
    assert graph.compare(original, changed)["relation"] == "DIFFERENT"


def test_adjustment_chronology_not_silently_erased(data):
    original = data[3]["J2_E_V0_02"]["graph"]
    altered = copy.deepcopy(original)
    altered["edges"] = [e for e in altered["edges"] if e[2] != "adjustment_order"]
    assert graph.compare(original, altered)["relation"] == "DIFFERENT"


def test_common_answer_support_is_not_full_behavior(data):
    ps = data[3]
    result = graph.compare(ps["J2_E_V1_01"]["graph"], ps["J2_E_V1_02"]["graph"])
    assert result["relation"] == "DIFFERENT" and result["reason"] == "labeled_node_multiplicity"
    mechanisms = measurement.mechanism_comparisons(ps)
    assert mechanisms["all_mapped_support_graphs_same"]
    assert len(mechanisms["pairs"]) == 2
    assert all(len(p["mapping"]) == 12 for p in mechanisms["pairs"])


def test_v0_v1_laws_and_only_one_within_condition_pair(data):
    measured = measurement.measure(data[0], data[3])
    assert len(measured["within_condition_pairs"]) == 1
    assert measured["within_condition_pairs"][0]["view_condition"] == "V1"
    assert [r["mass"] for r in measured["by_view"]["V0"]["J2"]["full_pi"]] == ["1"]
    assert [r["mass"] for r in measured["by_view"]["V1"]["J2"]["full_pi"]] == ["1/2", "1/2"]
    assert measured["pooled_success_law"] is None
    assert all(v["E1"]["full_pi"] is None for v in measured["by_view"].values())


def test_unknown_keeps_valid_mass_and_raw_materialization(data):
    label = "J2_E_V1_01"
    review = copy.deepcopy(data[2][label])
    review["annotations"][0]["status"] = "UNDETERMINED"
    changed = dict(data[3])
    changed[label] = graph.project(data[1][label], review)
    assert changed[label]["status"] == "UNDETERMINED"
    measured = measurement.measure(data[0], changed)
    law = measured["by_view"]["V1"]["J2"]
    assert law["valid_denominator"] == 2 and law["full_pi"] is None
    assert law["unresolved_valid_mass"] == "1/2" and law["known_state_mass"][0]["mass"] == "1/2"
    assert (
        len(
            [
                source.candidate(data[1][label], t)
                for t in data[1][label]["turns"]
                if t["event"]["admitted"]
            ]
        )
        == 17
    )


def test_two_equivalent_v1_observations_would_form_one_class(data):
    changed = copy.deepcopy(data[3])
    changed["J2_E_V1_01"]["graph"] = changed["J2_E_V1_02"]["graph"]
    measured = measurement.measure(data[0], changed)
    law = measured["by_view"]["V1"]["J2"]["full_pi"]
    assert len(law) == 1 and law[0]["count"] == 2 and law[0]["mass"] == "1"
    assert measured["within_condition_pairs"][0]["relation"] == "EQUIVALENT"


def test_unsupported_operation_preserves_unresolved_projection(data):
    label = "J2_E_V1_02"
    session = copy.deepcopy(data[1][label])
    session["turns"][0]["event"]["model_submission"]["operation"] = "unsupported_control"
    result = graph.project(session, data[2][label])
    assert result["status"] == "UNDETERMINED" and result["raw_and_validity_retained"]


def test_every_original_submission_has_one_projection_occurrence(data):
    for projection in data[3].values():
        assert projection["covered_original_submissions"] == list(
            range(1, projection["original_interaction_count"] + 1)
        )


class CharacterTokenizer:
    """In-memory boundary control only, not the formal Qwen tokenizer result."""

    all_special_ids = [151645, 151643]

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        prefix = "S:" + messages[0]["content"] + "U:" + messages[1]["content"] + "A:"
        return (
            prefix
            if add_generation_prompt
            else prefix + messages[-1]["content"] + stage.assets.CHAT_SUFFIX
        )

    def __call__(self, value, **kwargs):
        assert kwargs.get("truncation") is False and kwargs.get("padding") is False
        suffix = value.endswith(stage.assets.CHAT_SUFFIX)
        plain = value[: -len(stage.assets.CHAT_SUFFIX)] if suffix else value
        ids = [ord(c) + 1000 for c in plain]
        offsets = [(i, i + 1) for i in range(len(plain))]
        if suffix:
            ids += stage.assets.SUFFIX_TOKEN_IDS
            offsets += [(len(plain), len(value) - 1), (len(value) - 1, len(value))]
        return {"input_ids": ids, "attention_mask": [1] * len(ids), "offset_mapping": offsets}

    def decode(self, ids, **kwargs):
        return "".join(chr(i - 1000) for i in ids)


def test_exact_token_mask_and_overlength_preserve_original_candidate(data):
    session = data[1]["J2_E_V1_02"]
    row = source.candidate(session, session["turns"][-1])
    saved = copy.deepcopy(row)
    token = stage.encode_original_candidate(
        row, {"id": "synthetic_binding"}, CharacterTokenizer(), maximum_sequence_length=100000
    )
    assert token["consumable_token_representation"]
    start, end = token["target_token_start"], token["target_token_end"]
    assert all(v == -100 for v in token["labels"][:start] + token["labels"][end:])
    assert token["labels"][start:end] == token["input_ids"][start:end]
    short = stage.encode_original_candidate(
        row, {"id": "synthetic_binding"}, CharacterTokenizer(), maximum_sequence_length=1
    )
    assert not short["consumable_token_representation"] and short["input_ids"] is None
    assert short["truncated"] is False and row == saved


def test_package_not_unit_sampling_and_one_not_fit_blocks_whole_package(data):
    session = data[1]["J2_E_V1_02"]
    rows = [source.candidate(session, t) for t in session["turns"] if t["event"]["admitted"]]
    tokens = [
        {
            "row_id": r["id"],
            "id": f"token:{i}",
            "consumable_token_representation": i != 2,
            "sequence_length": 100,
            "target_token_count": 10,
        }
        for i, r in enumerate(rows)
    ]
    result = measurement.package_index(session, rows, tokens, {"state_id": "test_state"})
    assert result["admitted_unit_count"] == 15 and not result["whole_package_token_fit"]
    assert (
        result["assigned_training_weight"] is None and not result["uniform_row_sampling_authorized"]
    )


def test_zero_execution_guards_block_numeric_runtime_and_provider():
    with stage.zero_execution() as counts:
        with pytest.raises(RuntimeError, match="numeric_runtime_construction"):
            stage.Runtime(None)
        assert counts["numeric_runtime_construction"] == 1
