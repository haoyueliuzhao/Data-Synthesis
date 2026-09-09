"""New fixed-population and finite measurement controls; synthetic observations only."""

from collections import Counter
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration import measurement
from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.plan import (
    LABELS,
    MODEL,
    OUTPUT,
    STRUCTURES,
    SYSTEM,
    TASKS,
    condition,
    encode,
    policy,
    record,
    registrations,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import SYSTEMS

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def wired_panel():
    from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.panel import Panel

    return Panel(ROOT)


@pytest.fixture
def byte_backed_session(tmp_path):
    """Construct a non-Provider archive; never present the fixture as a live model sample."""
    from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
        request_body,
        strict_json,
    )

    label = "T_G1_synthetic_control"
    directory = tmp_path / OUTPUT / "online/sessions" / label
    directory.mkdir(parents=True)
    public = record(
        "synthetic_public", task_id="synthetic-question", question="Add two stated values."
    )
    row = record(
        "synthetic_valid_row",
        label=label,
        arm="T",
        task_key="G1",
        formula_driven_trace_verified=True,
        terminal="model_final",
    )

    def tool(call_index, name, arguments, result, status="ok"):
        call_id = "tool:" + str(call_index)
        return {
            "id": call_id,
            "name": name,
            "arguments": arguments,
            "output": {"call_id": call_id, "tool": name, "status": status, "result": result},
        }

    read = tool(1, "read_source", {"locators": ["source:x"]}, {"exact_value": "2"})
    notebook = tool(
        2,
        "notebook",
        {"operation": "write", "key": "plan", "text": "Add the stated inputs."},
        {"key": "plan", "text": "Add the stated inputs.", "author": "model"},
    )
    failed = tool(
        3,
        "calculate",
        {"expression": "missing + 1"},
        {"error": "undefined_variable:missing"},
        "error",
    )
    calculated = tool(4, "calculate", {"expression": "2 + 3"}, {"exact_value": "5"})
    final = {"answer": "5", "value": "5", "result_id": "tool:4"}
    specifications = [
        (b'{"tool":"calculate","arguments":{"expression":}}', "synthetic_json_error", None, False),
        (
            (
                ' { "message" : "I will compare the stated inputs, then calculate. 中文说明。" } '
            ).encode(),
            None,
            None,
            False,
        ),
        (encode({"tool": read["name"], "arguments": read["arguments"]}), None, read, False),
        (
            encode({"tool": notebook["name"], "arguments": notebook["arguments"]}),
            None,
            notebook,
            False,
        ),
        (encode({"tool": failed["name"], "arguments": failed["arguments"]}), None, failed, False),
        (
            encode({"tool": calculated["name"], "arguments": calculated["arguments"]}),
            None,
            calculated,
            False,
        ),
        (b" " + encode({"final": final}) + b"\n", None, None, True),
    ]
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": encode({"task": public}).decode()},
    ]
    turns = []
    for index, (raw, error, call, is_final) in enumerate(specifications):
        event = {
            "response_index": index,
            "raw_sha256": sha(raw),
            "protocol_error": error,
            "tool_call": call,
            "final": is_final,
        }
        prefix = directory / f"turns/{index:03d}"
        values = {
            "request_bytes": encode(request_body(messages, MODEL)),
            "projection_bytes": encode(
                {
                    "is_original_http_response": False,
                    "choices": [{"message": {"role": "assistant", "content": raw.decode()}}],
                }
            ),
            "event_bytes": encode(event),
            "raw": raw,
        }
        for field, suffix in (
            ("request_bytes", "_http_request.body"),
            ("projection_bytes", "_response_projection.json"),
            ("event_bytes", "_event.json"),
            ("raw", "_assistant.raw"),
        ):
            path = prefix.with_name(prefix.name + suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(values[field])
        turns.append(
            {
                **values,
                "event": event,
                "parsed": None if error else strict_json(raw),
                "input_messages": deepcopy(messages),
                "prefix": prefix,
            }
        )
        messages.append({"role": "assistant", "content": raw.decode()})
        if error:
            messages.append(
                {"role": "user", "content": encode({"interface_error": error}).decode()}
            )
        elif call:
            messages.append(
                {"role": "user", "content": encode({"tool_result": call["output"]}).decode()}
            )
        elif not is_final:
            messages.append(
                {"role": "user", "content": encode({"receipt": "model_message_recorded"}).decode()}
            )
    result = record(
        "synthetic_session_result",
        origin="scripted_control",
        provider_attempts=0,
        events=[turn["event"] for turn in turns],
        final=final,
    )
    result_bytes = encode(result)
    (directory / "result.json").write_bytes(result_bytes)
    members = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            members.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "bytes": len(raw),
                    "sha256": sha(raw),
                }
            )
    manifest = record("synthetic_session_manifest", members=members, result_id=result["id"])
    (directory / "manifest.json").write_bytes(encode(manifest))
    for index, turn in enumerate(turns):
        call = turn["event"]["tool_call"]
        turn["binding"] = record(
            "new_support_interaction_binding",
            session_label=label,
            population="T",
            task_key="G1",
            task_id=public["task_id"],
            source_document_id=public["id"],
            source_closeout_id=row["id"],
            session_result_id=result["id"],
            session_manifest_id=manifest["id"],
            request_sha256=sha(turn["request_bytes"]),
            response_projection_sha256=sha(turn["projection_bytes"]),
            raw_response_sha256=sha(turn["raw"]),
            event_sha256=sha(turn["event_bytes"]),
            response_index=index,
            actual_tool_call_id=call["id"] if call else None,
            session_result_file_sha256=sha(result_bytes),
        )
    return {
        "root": tmp_path,
        "row": row,
        "result": result,
        "result_bytes": result_bytes,
        "public": public,
        "directory": directory,
        "session_manifest_id": manifest["id"],
        "turns": turns,
    }


def source_row(label, task="G1", valid=True):
    return {
        "id": "synthetic-reviewed:" + label,
        "label": label,
        "arm": "T",
        "task_key": task,
        "condition_id": condition()["id"],
        "formula_driven_trace_verified": valid,
        "terminal": "model_final" if valid else "unknown_worker_failure",
        "answer": {"task_answer_status": "PASS" if valid else "UNDETERMINED"},
    }


def projection_for(row, support=("source:disclosed",), *, revision=None, checks=None, mapped=True):
    task = row["task_key"]
    signature = {
        "fixed_condition": condition()["id"],
        "task_version": "synthetic-task-version:" + task,
        "source_document_id": "synthetic-document:" + task,
        "goal_scope": {"quantity": "constructed task quantity", "period": "one explicit period"},
        "answer_source_normal_form": {
            "schema": "source_rational_polynomial.v1",
            "numerator": [{"coefficient": "1", "powers": [[sid, 1]]} for sid in sorted(support)],
            "denominator": [{"coefficient": "1", "powers": []}],
        },
        "active_support": sorted(support),
        "substantive_revision_path": revision or [],
        "evidenced_independent_cross_checks": checks or [],
    }
    return {
        "id": "synthetic-projection:" + row["label"],
        "session_label": row["label"],
        "task_key": task,
        "task_version": signature["task_version"],
        "source_document_id": signature["source_document_id"],
        "source_closeout_id": row["id"],
        "status": "MAPPED" if mapped else "UNDETERMINED",
        "behavior_signature": signature if mapped else None,
        "behavior_key": sha(encode(signature)) if mapped else None,
        "reason": None if mapped else "synthetic_unresolved_public_revision",
    }


def task_result(report, key="G1"):
    return report["populations"]["T"]["tasks"][key]


def test_new_registration_is_exactly_six_tasks_four_fresh_repeats_and_fixed_t():
    assert TASKS == ("G1", "G2", "F1", "F2", "L1", "L2")
    assert LABELS == tuple(f"T_{task}_{rep:02d}" for rep in range(1, 5) for task in TASKS)
    assert len(LABELS) == len(set(LABELS)) == 24
    assert MODEL == "deepseek-v4-flash" and SYSTEM.encode() == SYSTEMS["T"].encode()
    assert sorted(Counter(STRUCTURES.values()).values()) == [2, 2, 2]
    rows = registrations(
        {
            key: {"task_id": "synthetic-task:" + key, "id": "synthetic-public:" + key}
            for key in TASKS
        }
    )
    assert [row["label"] for row in rows] == list(LABELS)
    assert {row["arm"] for row in rows} == {"T"}
    assert {row["requested_model"] for row in rows} == {MODEL}
    for task in TASKS:
        selected = [row for row in rows if row["task_key"] == task]
        assert [row["replicate"] for row in selected] == [1, 2, 3, 4]
        assert all(
            row["fresh_independent_session"] and row["system_sha256"] == sha(SYSTEM.encode())
            for row in selected
        )
    assert sum(row["response_budget"] for row in rows) == 768
    assert all(row["tool_budget"] == 32 for row in rows)


def test_condition_preserves_open_harness_without_route_or_class_count_control():
    config = condition()
    assert config["model"] == MODEL and config["system"] == SYSTEMS["T"]
    assert config["thinking"] == "enabled" and config["reasoning_effort"] == "high"
    assert config["limits"]["output_tokens"] == 16384
    assert config["maximum_model_requests"] == 768
    assert config["maximum_reserved_token_allowance"] == 768 * 115712
    assert config["task_marginal"] == {key: "1/6" for key in TASKS}
    assert config["original_worker_calculator_projection_isolate_bytes"]
    assert config["complete_original_question_and_source_visible"]
    assert config["private_route_options_never_in_model_input"]
    assert not config["force_reconstruction"] and not config["hide_disclosure"]
    assert config["first_Final_terminal_even_if_incorrect_or_no_calculation"]
    assert config["fixed_allocation_no_adaptive_prompt_or_resampling"]
    assert config["no_retries_no_fallback_no_budget_increase"]
    assert config["success_does_not_require_multiple_classes"]
    assert not config["old_trajectories_in_new_frequency_denominator"]


def test_new_positive_policy_explicitly_keeps_public_messages_and_error_history():
    rules = policy()
    positive = rules["positive_targets"]
    assert "every original structurally legal message-only response" in positive
    assert "successful calculate/read_source/notebook request and actual Final" in positive
    assert "JSON/protocol errors and failed tool requests" in positive
    assert "retained in the full session and subsequent inputs but not positive targets" in positive
    assert rules["no_host_merge_rewrite_or_inserted_annotations"]
    assert rules["training_weights"] is None
    assert "single-class outcomes accepted" in rules["stopping"]


def test_identical_finite_signature_is_equivalent_despite_external_metadata():
    rows = [source_row("synthetic-one"), source_row("synthetic-two")]
    first, second = [projection_for(row) for row in rows]
    second["raw_expression"] = "a different variable name; outside the canonical signature"
    second["model_token_count"] = 1234
    assert measurement.compare(first, second) == "EQUIVALENT"
    report = measurement.measure([first, second], rows)
    task = task_result(report)
    assert task["known_class_count"] == 1
    assert list(task["conditional_distribution"].values()) == ["1"]
    assert task["original_full_trajectory_yield"] == {
        "numerator": 2,
        "denominator": 4,
        "fraction": "1/2",
    }
    assert report["primary_pair_status_counts"] == {"EQUIVALENT": 1}
    assert report["class_probability_degrees_of_freedom"] == 0


def test_same_published_number_different_actual_support_is_distinct():
    rows = [source_row("synthetic-direct"), source_row("synthetic-reconstructed")]
    first = projection_for(rows[0])
    second = projection_for(rows[1], ("source:component-a", "source:component-b"))
    first["published_value"] = second["published_value"] = "42"
    assert measurement.compare(first, second) == "DISTINCT"
    report = measurement.measure([first, second], rows)
    task = task_result(report)
    assert task["known_class_count"] == 2
    assert sorted(task["conditional_distribution"].values()) == ["1/2", "1/2"]
    assert task["local_two_support_witness"]
    assert report["local_two_support_witness_tasks"] == ["G1"]
    assert report["class_probability_degrees_of_freedom"] == 1


@pytest.mark.parametrize(
    "field", ("substantive_revision_path", "evidenced_independent_cross_checks")
)
def test_real_revision_and_evidenced_cross_check_remain_part_of_behavior_identity(field):
    rows = [source_row("synthetic-before"), source_row("synthetic-after")]
    first, second = [projection_for(row) for row in rows]
    second["behavior_signature"][field] = [
        {"kind": "synthetic evidenced substantive difference", "source_support": ["source:other"]}
    ]
    second["behavior_key"] = sha(encode(second["behavior_signature"]))
    assert measurement.compare(first, second) == "DISTINCT"
    assert task_result(measurement.measure([first, second], rows))["known_class_count"] == 2


def test_partial_mapping_retains_mass_and_local_witness_without_complete_distribution():
    rows = [
        source_row("synthetic-direct"),
        source_row("synthetic-rebuild"),
        source_row("synthetic-valid-unmapped"),
        source_row("synthetic-no-result", valid=False),
    ]
    projections = [
        projection_for(rows[0]),
        projection_for(rows[1], ("source:component-a", "source:component-b")),
        projection_for(rows[2], mapped=False),
    ]
    original = deepcopy(rows)
    report = measurement.measure(projections, rows)
    task = task_result(report)
    assert task["valid_denominator"] == 3 and task["mapped_count"] == 2
    assert task["original_full_trajectory_yield"]["fraction"] == "3/4"
    assert sorted(task["known_class_masses"].values()) == ["1/3", "1/3"]
    assert task["unresolved_mass"] == "1/3" and task["conditional_distribution"] is None
    assert task["distribution_state"] == "PARTIALLY_MAPPED"
    assert task["valid_pair_count"] == 3
    assert task["valid_pair_status_counts"] == {"DISTINCT": 1, "UNDETERMINED": 2}
    assert task["local_two_support_witness"]
    assert report["class_probability_degrees_of_freedom"] is None
    assert report["known_class_probability_degrees_of_freedom_lower_bound"] == 1
    assert report["complete_supported_task_degrees_of_freedom"] == 0
    assert report["session_class_ids"][rows[2]["label"]] is None
    assert (
        rows[3]["label"] not in report["session_class_ids"]
        and report["original_invalid_records_retained"] == 1
    )
    assert rows == original


def test_missing_projection_retains_original_valid_mass_and_all_valid_pairs():
    rows = [source_row("synthetic-" + str(index)) for index in range(4)]
    report = measurement.measure([projection_for(row) for row in rows[:3]], rows)
    task = task_result(report)
    assert task["valid_denominator"] == 4 and task["unresolved_count"] == 1
    assert list(task["known_class_masses"].values()) == ["3/4"]
    assert task["unresolved_mass"] == "1/4" and task["conditional_distribution"] is None
    assert task["unresolved_records"][0]["reason"] == "missing_projection"
    assert task["valid_pair_count"] == 6
    assert task["valid_pair_status_counts"] == {"EQUIVALENT": 3, "UNDETERMINED": 3}
    assert not task["local_two_support_witness"]


def test_zero_valid_includes_unknown_registrations_without_claiming_no_possible_behavior():
    rows = [source_row("synthetic-unknown-" + str(index), valid=False) for index in range(4)]
    report = measurement.measure([], rows)
    task = task_result(report)
    assert task["registered_count"] == task["planned_registered_count"] == 4
    assert task["original_invalid_count"] == 4
    assert task["original_full_trajectory_yield"]["fraction"] == "0"
    assert task["conditional_distribution"] is None and task["unresolved_mass"] is None
    assert task["distribution_state"] == "NO_VALID_SUPPORT"
    assert task["no_valid_support_does_not_establish_no_behavior"]
    assert task["valid_pair_count"] == 0 and not task["local_two_support_witness"]
    assert report["class_probability_degrees_of_freedom"] == 0
    assert report["source_row_count"] == report["original_invalid_records_retained"] == 4


def test_single_valid_session_has_one_class_but_no_pair_or_probability_dimension():
    row = source_row("synthetic-only-valid")
    task = task_result(measurement.measure([projection_for(row)], [row]))
    assert task["valid_pair_count"] == 0 and task["known_class_count"] == 1
    assert task["original_full_trajectory_yield"]["fraction"] == "1/4"
    assert list(task["conditional_distribution"].values()) == ["1"]
    assert task["observed_class_probability_degrees_of_freedom"] == 0


def test_four_equivalent_valid_sessions_produce_six_pairs_and_one_accepted_class():
    rows = [source_row("synthetic-repeat-" + str(index)) for index in range(4)]
    report = measurement.measure([projection_for(row) for row in rows], rows)
    task = task_result(report)
    assert task["valid_pair_count"] == 6
    assert task["valid_pair_status_counts"] == {"EQUIVALENT": 6}
    assert task["original_full_trajectory_yield"]["fraction"] == "1"
    assert task["known_class_count"] == 1 and not task["local_two_support_witness"]
    assert report["class_probability_degrees_of_freedom"] == 0


def test_full_synthetic_population_has_36_within_task_pairs_and_taskwise_dimensions():
    rows, projections = [], []
    for task in TASKS:
        for rep in range(4):
            row = source_row(f"synthetic-{task}-{rep}", task=task)
            rows.append(row)
            projections.append(
                projection_for(row, ("source:disclosed",) if rep < 2 else ("source:parts",))
            )
    report = measurement.measure(projections, rows)
    assert set(report["populations"]) == {"T"}
    assert report["complete_registered_population"] and report["source_row_count"] == 24
    assert len(report["primary_pairs"]) == report["maximum_planned_valid_pairs"] == 36
    assert report["primary_pair_status_counts"] == {"DISTINCT": 24, "EQUIVALENT": 12}
    assert report["class_probability_degrees_of_freedom"] == 6
    assert report["known_class_probability_degrees_of_freedom_lower_bound"] == 6
    assert report["local_two_support_witness_tasks"] == list(TASKS)
    assert report["original_task_marginal"] == {task: "1/6" for task in TASKS}
    assert not report["condition_pooling"] and not report["training_weights_assigned"]
    assert not report["six_task_training_distribution_implemented"]
    assert len(set(report["session_class_ids"].values())) == 12


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("arm", "A", "only_new_T_population"),
        ("task_key", "N1", "registered_task"),
        ("condition_id", "historical-batch", "only_new_fixed_condition"),
        ("formula_driven_trace_verified", 1, "original_boolean_validity"),
    ],
)
def test_old_conditions_tasks_or_nonboolean_validity_cannot_enter_new_population(
    field, value, error
):
    row = source_row("synthetic-invalid-source")
    row[field] = value
    with pytest.raises(ValueError, match=error):
        measurement.measure([], [row])


def test_duplicate_sources_extra_repeats_and_unregistered_or_invalid_projections_are_rejected():
    row = source_row("synthetic-duplicate")
    with pytest.raises(ValueError, match="unique_source_labels"):
        measurement.measure([], [row, deepcopy(row)])
    with pytest.raises(ValueError, match="no_extra_replicates"):
        measurement.measure([], [source_row("synthetic-extra-" + str(index)) for index in range(5)])
    projection = projection_for(row)
    with pytest.raises(ValueError, match="unique_registered_projection"):
        measurement.measure([projection, deepcopy(projection)], [row])
    with pytest.raises(ValueError, match="unique_registered_projection"):
        measurement.measure([projection], [])
    row["formula_driven_trace_verified"] = False
    with pytest.raises(ValueError, match="original_validity_required"):
        measurement.measure([projection], [row])


def test_projection_source_identity_and_signature_hash_are_checked():
    row = source_row("synthetic-binding")
    for field, value, error in (
        ("source_closeout_id", "other-review", "original_source_row_id"),
        ("task_key", "G2", "task_not_reassigned"),
        ("behavior_key", "forged-key", "behavior_key_matches_complete_signature"),
    ):
        projection = projection_for(row)
        projection[field] = value
        with pytest.raises(ValueError, match=error):
            measurement.measure([projection], [row])
    projection = projection_for(row)
    projection["behavior_signature"]["fixed_condition"] = "old-T-batch"
    projection["behavior_key"] = sha(encode(projection["behavior_signature"]))
    with pytest.raises(ValueError, match="only_new_fixed_condition"):
        measurement.measure([projection], [row])


def test_different_full_signatures_cannot_merge_under_a_constructed_hash_collision(monkeypatch):
    rows = [source_row("synthetic-collision-a"), source_row("synthetic-collision-b")]
    projections = [projection_for(rows[0]), projection_for(rows[1], ("source:other",))]
    monkeypatch.setattr(measurement, "sha", lambda value: "synthetic-collision")
    for projection in projections:
        projection["behavior_key"] = "synthetic-collision"
    assert measurement.compare(*projections) == "DISTINCT"
    with pytest.raises(ValueError, match="no_hash_only_equivalence"):
        measurement.measure(projections, rows)


def test_task_version_or_document_mixing_is_not_a_within_task_distinction():
    rows = [source_row("synthetic-version-a"), source_row("synthetic-version-b")]
    first, second = [projection_for(row) for row in rows]
    second["task_version"] = second["behavior_signature"]["task_version"] = (
        "a-different-task-version"
    )
    second["behavior_key"] = sha(encode(second["behavior_signature"]))
    assert measurement.compare(first, second) == "NOT_COMPARABLE"
    with pytest.raises(ValueError, match="one_version_and_document_per_task"):
        measurement.measure([first, second], rows)


def test_unmapped_record_cannot_smuggle_a_class_key_and_inputs_remain_unchanged():
    rows = [source_row("synthetic-mapped"), source_row("synthetic-unmapped")]
    projections = [projection_for(rows[0]), projection_for(rows[1], mapped=False)]
    before_rows, before_projections = deepcopy(rows), deepcopy(projections)
    result = measurement.measure(projections, rows)
    assert rows == before_rows and projections == before_projections
    assert measurement.measure(list(reversed(projections)), list(reversed(rows))) == result
    projections[1]["behavior_key"] = "not-an-unknown-class"
    with pytest.raises(ValueError, match="unknown_is_not_a_class"):
        measurement.measure(projections, rows)


def test_three_new_real_tasks_have_two_exact_sufficient_routes_and_unchanged_anchor_documents(
    wired_panel,
):
    from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import evaluate
    from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.stage import public_document

    def support(tree):
        if isinstance(tree, str):
            return {tree} if tree.startswith("source:") else set()
        return set().union(*(support(child) for child in tree["args"]))

    for key, exact in {
        "G2": Fraction(1204, 103),
        "F2": Fraction(282),
        "L2": Fraction(17, 10),
    }.items():
        task = wired_panel.tasks[key]
        routes = list(task["sufficient_routes"].values())
        assert len(routes) == 2
        assert all(evaluate(route, task["facts"]) == exact for route in routes)
        assert support(routes[0]) != support(routes[1])
        for sid, relation in task["relations"].items():
            assert evaluate(sid, task["facts"]) == evaluate(relation, task["facts"])
    old_public = (
        ROOT
        / "trusted_data_synthesis/artifacts/qa_vnext_trace_delivery"
        / "flash_high_at_2rep_20260909/preparation/public"
    )
    for key, old_key in {"G1": "N1", "F1": "N4", "L1": "N5"}.items():
        assert (
            encode(public_document(wired_panel.tasks[key]))
            == (old_public / (old_key + ".json")).read_bytes()
        )


def test_real_panel_public_material_is_complete_and_route_free_for_all_24_registrations(
    wired_panel,
):
    from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.stage import public_document

    forbidden = {
        "sufficient_routes",
        "target",
        "relations",
        "selected",
        "goal_scope",
        "interpretation",
        "precision_policy",
        "structure",
        "arm",
        "route_menu",
    }

    def inspect_public(value):
        if isinstance(value, dict):
            assert not set(value) & forbidden
            for child in value.values():
                inspect_public(child)
        elif isinstance(value, list):
            for child in value:
                inspect_public(child)

    public = {key: public_document(task) for key, task in wired_panel.tasks.items()}
    for key, document in public.items():
        task = wired_panel.tasks[key]
        assert document["question"] == task["entry"]["qa"]["question"]
        assert document["source"] == {
            name: task["entry"][name] for name in ("pre_text", "post_text", "table")
        }
        assert document["numeric_catalog"] == list(task["facts"].values())
        inspect_public(document)
    rows = registrations(public)
    assert Counter(row["task_key"] for row in rows) == {key: 4 for key in TASKS}
    assert all(row["public_document_id"] == public[row["task_key"]]["id"] for row in rows)


def test_new_capsule_is_byte_identical_to_the_frozen_original_t_capsule():
    from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration import stage
    from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import (
        capsule_files,
    )

    assert stage.capsule_files is capsule_files
    files = stage.capsule_files(ROOT, "T")
    previous = (
        ROOT
        / "trusted_data_synthesis/artifacts/qa_vnext_trace_delivery"
        / "flash_high_at_2rep_20260909/preparation/worker_code/T"
    )
    assert set(files) == {"worker.py", "common.py", "calculator.py", "projection.py", "isolate.py"}
    assert all(raw == (previous / name).read_bytes() for name, raw in files.items())
    assert stage.SYSTEM == SYSTEMS["T"] and stage.MODEL == MODEL


def test_new_byte_backed_positive_policy_keeps_five_response_types_and_literal_error_history(
    byte_backed_session,
):
    from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration import source

    session = byte_backed_session
    candidates = [source.positive_candidate(session, turn) for turn in session["turns"]]
    assert [candidate["response_kind"] if candidate else None for candidate in candidates] == [
        None,
        "message",
        "read_source",
        "notebook",
        None,
        "calculate",
        "Final",
    ]
    assert (
        session["result"]["origin"] == "scripted_control"
        and session["result"]["provider_attempts"] == 0
    )
    for turn, candidate in zip(session["turns"], candidates, strict=True):
        if candidate is None:
            continue
        assert candidate["input_messages"] == turn["input_messages"]
        assert candidate["target_response"].encode() == turn["raw"]
        assert candidate["public_messages_not_merged_into_tool_or_Final"]
        assert candidate["input_messages"][0] == {"role": "system", "content": SYSTEM}
    final_messages = candidates[-1]["input_messages"]
    assert {"role": "assistant", "content": session["turns"][0]["raw"].decode()} in final_messages
    assert {"role": "assistant", "content": session["turns"][4]["raw"].decode()} in final_messages
    assert {
        "role": "user",
        "content": encode(
            {"tool_result": session["turns"][4]["event"]["tool_call"]["output"]}
        ).decode(),
    } in final_messages


def test_new_same_turn_swap_and_self_rehashed_source_rewrite_are_rejected(byte_backed_session):
    from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration import source
    from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
        strict_json,
    )

    session = byte_backed_session
    for field in ("request_bytes", "projection_bytes", "raw", "input_messages", "event_bytes"):
        exchanged = deepcopy(session["turns"][1])
        exchanged[field] = session["turns"][0][field]
        with pytest.raises(ValueError, match="new_export"):
            source.positive_candidate(session, exchanged)
    forged = deepcopy(session)
    turn = forged["turns"][1]
    turn["raw"] = turn["raw"].replace(b"compare", b"rewrite")
    turn["parsed"] = strict_json(turn["raw"])
    turn["event"]["raw_sha256"] = sha(turn["raw"])
    turn["event_bytes"] = encode(turn["event"])
    envelope = strict_json(turn["projection_bytes"])
    envelope["choices"][0]["message"]["content"] = turn["raw"].decode()
    turn["projection_bytes"] = encode(envelope)
    forged["result"] = record(
        "synthetic_session_result",
        **{
            key: value
            for key, value in forged["result"].items()
            if key not in {"id", "schema_version"}
        },
    )
    forged["result_bytes"] = encode(forged["result"])
    fields = {
        key: value for key, value in turn["binding"].items() if key not in {"id", "schema_version"}
    }
    fields.update(
        raw_response_sha256=sha(turn["raw"]),
        event_sha256=sha(turn["event_bytes"]),
        response_projection_sha256=sha(turn["projection_bytes"]),
        session_result_id=forged["result"]["id"],
        session_result_file_sha256=sha(forged["result_bytes"]),
    )
    turn["binding"] = record("new_support_interaction_binding", **fields)
    with pytest.raises(ValueError, match="persisted_turn_bytes"):
        source.positive_candidate(forged, turn)


def test_new_export_preserves_independent_message_target_and_unknown_archive(
    byte_backed_session, monkeypatch
):
    from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration import materialize

    session = byte_backed_session
    root = session["root"]
    binding = {
        "chat_template": "synthetic-export-adapter",
        "directory": str(root / "synthetic-tokenizer"),
        "members": [],
    }
    tokenizer = SimpleNamespace(chat_template=binding["chat_template"])
    monkeypatch.setattr(materialize, "load_bound_assets", lambda _: (binding, {}, tokenizer))
    monkeypatch.setattr(materialize.assets, "_read_members", lambda _: ([], None))
    encoded_kinds = []

    def synthetic_token_adapter(candidate, *args):
        # Export wiring only: the following separate test performs the one real
        # local-tokenizer boundary check on a NEW synthetic public message.
        encoded_kinds.append(candidate["response_kind"])
        return record(
            "synthetic_token_adapter",
            response_index=candidate["response_index"],
            sequence_length=3,
            prompt_token_count=1,
            target_token_count=1,
            consumable_token_representation=True,
        )

    monkeypatch.setattr(materialize, "encode_candidate", synthetic_token_adapter)
    unknown = record(
        "synthetic_unknown_row",
        label="T_G2_synthetic_not_started",
        arm="T",
        task_key="G2",
        formula_driven_trace_verified=False,
        terminal="unknown_worker_failure",
    )
    projection = record(
        "synthetic_unknown_projection",
        session_label=session["row"]["label"],
        source_closeout_id=session["row"]["id"],
        task_key="G1",
        population="T",
        status="UNDETERMINED",
        behavior_key=None,
    )
    destination = root / OUTPUT / "synthetic_materialization"
    index = materialize.export(
        root,
        destination,
        {session["row"]["label"]: session},
        [session["row"], unknown],
        [projection],
        {"session_class_ids": {session["row"]["label"]: None}},
    )
    assert encoded_kinds == ["message", "read_source", "notebook", "calculate", "Final"]
    assert index["positive_row_count"] == 5 and index["valid_package_count"] == 1
    assert index["by_population"]["T"]["nonpositive_by_reason"] == {
        "failed_tool_request": 1,
        "protocol_or_json_error": 1,
    }
    assert index["by_population"]["T"]["partial_or_not_started_archives"] == 1
    assert index["excluded_sessions"] == [unknown]
    assert (
        destination / "positive" / session["row"]["label"] / "001.target.raw"
    ).read_bytes() == session["turns"][1]["raw"]
    assert [row["response_index"] for row in index["rows"]] == [1, 2, 3, 5, 6]
    assert not (root / OUTPUT / "online/sessions" / unknown["label"]).exists()


def test_one_new_synthetic_message_target_has_exact_token_boundary_and_prompt_mask(
    byte_backed_session,
):
    from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration import (
        source,
        tokens,
    )

    session = byte_backed_session
    candidate = source.positive_candidate(session, session["turns"][1])
    binding, token_policy, tokenizer = tokens.load_bound_assets(ROOT)
    representation = tokens.encode_candidate(candidate, binding, token_policy, tokenizer)
    assert representation["response_kind"] == "message"
    assert representation["consumable_token_representation"] and not representation["truncated"]
    start, end = representation["target_token_start"], representation["target_token_end"]
    ids, labels, mask = (representation[key] for key in ("input_ids", "labels", "target_mask"))
    assert mask == [0] * start + [1] * (end - start) + [0] * (len(ids) - end)
    assert labels == [
        value if selected else -100 for value, selected in zip(ids, mask, strict=True)
    ]
    assert (
        tokenizer.decode(
            ids[start:end], skip_special_tokens=False, clean_up_tokenization_spaces=False
        ).encode()
        == session["turns"][1]["raw"]
    )
    assert (
        representation["prompt_token_count"] == start
        and representation["target_token_count"] == end - start
    )
    assert representation["causal_target_token_start"] == start - 1
    assert representation["sequence_length"] <= 32768
    assert token_policy["independent_public_message_targets_preserved"]
    assert token_policy["historical_token_rows_retokenized"] is False
