"""Synthetic CPU-only diagnostic contracts; never scan the 813 real outputs."""
import copy
import hashlib
import math
from pathlib import Path

import pytest

import finqa_v63_diagnostics as diagnostics


def native(state, task="finqa/task"):
    return dict(task_key="draw20260928/" + task, original_task_key=task, source_group="source",
        stop_reason="no_tool_call", actual_model_calls=2,
        native=dict(status="unknown" if state == "UNKNOWN" else "invalid_prediction" if state == "I" else "scored",
            program_executable=None if state == "UNKNOWN" else state != "I",
            native=dict(execution_accuracy=None if state == "UNKNOWN" else int(state == "R"))))


def mock_original_parser(raw, *, call_prefix):
    if raw == "A":
        return "", []
    if raw == "B":
        return "", []
    if raw == "C":
        return "", []
    if raw == "D":
        return "", []
    if raw == "E":
        return "", []
    if raw == "F":
        return "", []
    return "", [dict(call_id=call_prefix, name="submit_program", raw_arguments="{}")]


def episode(raws=("A", "G")):
    turns = []
    for ordinal, raw in enumerate(raws):
        call_id = "call" + str(ordinal)
        turns.append(dict(raw_text=raw, tool_calls=mock_original_parser(raw, call_prefix=call_id)[1],
            receipt=dict(call_id=call_id, raw_response_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                raw_generated_token_ids=[10, 11], actual_eos=True, finish_reason="stop")))
    return dict(dataset="finqa", task_id="task", stop_reason="no_tool_call",
        actual_model_calls=2, turns=turns, tool_events=[], final_answer=None)


def test_policy_freezes_posthoc_scope_without_additional_qualitative_or_science_budget():
    rule = diagnostics.policy()
    assert rule["old_results_already_seen"] is True
    assert rule["old_invalid_population"]["expected_total"] == 813
    assert rule["old_invalid_population"]["expected_invalid_by_arm"] == dict(C05=271, C1=247, Hold=295)
    assert rule["qualitative"]["maximum_total"] == 36
    assert rule["qualitative"]["maximum_per_parent_per_direction"] == 6
    assert rule["qualitative"]["new_batch_additional_qualitative_pairs"] == 0
    assert rule["original_B_remaining_72_examples_read"] is False
    assert rule["parser"]["saved_parser_disagreement_blocks_diagnostic_acceptance"] is True
    assert rule["directions"]["old_draw_replay_Tensor_opened"] is False
    assert rule["coefficients"]["window"] == [597, 894]
    assert rule["coefficients"]["retokenize_or_reclassify_original_text"] is False
    assert not rule["coefficients"]["loss_or_gradient_contribution_claimed"]
    assert rule["new_model_calls"] == rule["new_backward_passes"] == rule["external_API_calls"] == 0


@pytest.mark.parametrize("raw,index", [(letter, index) for index, letter in enumerate("ABCDEFG")])
def test_parser_labels_only_original_return_without_repair(raw, index):
    classifier = diagnostics.classified_parser(mock_original_parser)
    category, original_value = classifier(raw, call_prefix="same-prefix")
    assert category == diagnostics.PARSER_BRANCHES[index]
    assert original_value == mock_original_parser(raw, call_prefix="same-prefix")


def test_terminal_exclusive_category_is_not_first_rejected_turn_or_native_rescore():
    result = diagnostics.inspect_episode(episode(), native("I"), diagnostics.classified_parser(mock_original_parser))
    assert result["terminal_parser_category"] == "G_accepted_tool_envelopes"
    assert result["first_rejected_turn"]["turn"] == 1
    assert result["first_rejected_turn"]["category"] == "A_no_opening_envelope"
    assert result["native_state"] == "I"
    assert result["native_rescored"] is False and result["tools_reexecuted"] == 0
    assert result["saved_parser_disagreement"] is False


def test_raw_receipt_mismatch_is_not_silently_classified_or_repaired():
    value = episode()
    value["turns"][0]["raw_text"] = "G"
    with pytest.raises(ValueError, match="does not match"):
        diagnostics.inspect_episode(value, native("I"), diagnostics.classified_parser(mock_original_parser))


def test_missing_receipt_and_zero_turns_are_not_complete_parser_evidence():
    value = episode()
    value["turns"][-1]["receipt"] = None
    result = diagnostics.inspect_episode(value, native("I"), diagnostics.classified_parser(mock_original_parser))
    assert result["terminal_parser_category"] == "NA_missing_original_receipt"
    assert not result["original_receipts_complete"]
    value["turns"] = []
    result = diagnostics.inspect_episode(value, native("I"), diagnostics.classified_parser(mock_original_parser))
    assert result["terminal_parser_category"] == "NA_no_returned_turn"
    assert not result["original_receipts_complete"]


@pytest.mark.parametrize("disagreements,missing,expected", [
    (0, 0, "COMPLETE"), (0, 1, "INCOMPLETE"), (1, 0, "BLOCKED_PARSER_DISAGREEMENT"),
])
def test_parser_disagreement_blocks_diagnostic_acceptance(disagreements, missing, expected):
    assert diagnostics.invalid_acceptance_status(missing=missing, incomplete=0, unknowns=0,
        missing_pairs=0, disagreements=disagreements) == expected


def test_old_draw_fields_are_referenced_without_opening_values_and_absence_is_inspected(tmp_path):
    class ForbiddenTensor:
        def __getattribute__(self, _name):
            pytest.fail("old gradient Tensor values must not be inspected")
    source = dict(path="/bound/old_outer/record.json", sha256="old-sha")
    fields = diagnostics._draw_field_references(
        dict(evidence=dict(feedback_report=dict(draw_components={"11": ForbiddenTensor()}))), source)
    assert fields == [dict(source=source, field="evidence.feedback_report.draw_components", numerical_value_read=False)]
    present = diagnostics._old_draw_components(tmp_path, {}, "C1", {}, [source], fields)
    assert present["status"] == "PRESENT_REFERENCED_NOT_NUMERICALLY_RECOMPUTED"
    assert not present["old_draw_numerical_agreement_recomputed"]
    absent = diagnostics._old_draw_components(tmp_path, {}, "C1", {}, [source], [])
    assert absent["status"] == "NA_NO_DRAW_FIELDS_IN_FORMAL_METADATA"
    assert absent["inspection_complete"] and absent["inspected_sources"] == [source]


@pytest.mark.parametrize("checkpoint_present", [True, False])
def test_old_C05_draw_check_uses_only_final_bound_checkpoint_and_missing_is_not_NA(tmp_path, monkeypatch,
                                                                                checkpoint_present):
    replay_root = tmp_path / "stages/seed137/replay_C05"
    result_path = replay_root / "result/record.json"
    checkpoint_path = replay_root / "checkpoints/response000016/record.json"
    saved_binding = dict(response_count=16, point_id="same-point")
    table = {
        result_path: dict(status="COMPLETE", parent_id="parent", stage="replay_C05",
            complete_replay=True, denominator=700, responses=16),
        checkpoint_path: dict(cursor=16, full_replay_complete=True, binding=saved_binding,
            draw_components_schema="saved-component-schema"),
    }
    reads = []
    def read(path):
        path = Path(path)
        reads.append(path)
        if path == checkpoint_path and not checkpoint_present:
            raise FileNotFoundError(path)
        return table[path]
    monkeypatch.setattr(diagnostics.binding, "checked", read)
    monkeypatch.setattr(diagnostics.binding, "entry", lambda path: dict(path=str(path), sha256="bound-sha"))
    args = (tmp_path, dict(seed=137, id="parent"), "C05",
            dict(response_checkpoint_binding=saved_binding), [dict(path="/bound/distribution")], [])
    if checkpoint_present:
        result = diagnostics._old_draw_components(*args)
        assert result["status"] == "PRESENT_REFERENCED_NOT_NUMERICALLY_RECOMPUTED"
        assert result["existing_component_fields"][0]["field"] == "draw_components_schema"
    else:
        with pytest.raises(FileNotFoundError):
            diagnostics._old_draw_components(*args)
    assert reads == [result_path, checkpoint_path]


def pair_inputs(forward=10, backward=10):
    reports, indexes = {}, {}
    for seed in diagnostics.SEEDS:
        left, right, reference = [], [], {}
        for index in range(883):
            task = f"finqa/task{index:04d}"
            states = ("I", "R") if index < forward else ("R", "I") if index < forward+backward else ("W", "W")
            left.append(native(states[0], task))
            right.append(native(states[1], task))
            reference[task] = dict(path=f"/synthetic/{seed}/{index}.json",
                                  sha256=hashlib.sha256(f"{seed}-{index}".encode()).hexdigest())
        for arm, rows in (("C1", left), ("C05", right)):
            coordinate = f"seed{seed}/{arm}"
            reports[coordinate] = dict(denominator=883, results=rows)
            indexes[coordinate] = {task: {**row, "path": row["path"]+arm} for task, row in reference.items()}
    return reports, indexes


def test_pair_selection_is_digest_fixed_balanced_and_capped():
    reports, indexes = pair_inputs()
    first = diagnostics.select_pairs(reports, indexes, policy_id="frozen-policy")
    assert first["count"] == 36
    assert all(sum(row["seed"] == seed for row in first["selected"]) == 12 for seed in diagnostics.SEEDS)
    assert all(sum(row["seed"] == seed and row["transition"] == direction for row in first["selected"]) == 6
               for seed in diagnostics.SEEDS for direction in ("I->R", "R->I"))
    reversed_reports = {key: {**value, "results": list(reversed(value["results"]))} for key, value in reports.items()}
    assert diagnostics.select_pairs(reversed_reports, indexes, policy_id="frozen-policy")["selected"] == first["selected"]
    assert first["manual_reading_completed"] is False


def test_pair_selection_does_not_transfer_unused_stratum_quota():
    reports, indexes = pair_inputs(forward=2, backward=20)
    result = diagnostics.select_pairs(reports, indexes, policy_id="frozen-policy")
    assert result["count"] == 24
    assert result["unused_stratum_quota_redistributed"] is False


def test_UNKNOWN_is_not_invalid_zero_or_selected_I_R_pair():
    reports, indexes = pair_inputs(forward=1, backward=1)
    reports["seed137/C1"]["results"][0] = native("UNKNOWN", "finqa/task0000")
    result = diagnostics.select_pairs(reports, indexes, policy_id="frozen-policy")
    assert result["count"] == 5
    assert diagnostics.native_state(native("UNKNOWN")) == "UNKNOWN"


def test_actual_C_direction_does_not_multiply_mu_twice():
    parent = dict(A=dict(z1="1/2", z2="1/2"), B=dict(z1="1/2", z2="1/2"))
    q = dict(A=dict(z1="3/4", z2="1/4"), B=dict(z1="1/2", z2="1/2"))
    C = dict(A=dict(z1=2.0, z2=-2.0), B=dict(z1=0.0, z2=0.0))
    assert diagnostics.direction_score(C, q, parent) == 1.0
    distance = diagnostics.q_distance(q, parent, dict(A="1/2", B="1/2"))
    assert distance["weighted_TV"] == 0.125
    assert distance["weighted_KL_left_right"] > 0
    with pytest.raises(TypeError):
        diagnostics.direction_score(C, q, parent, mu=dict(A="1/2", B="1/2"))


def test_direction_rejects_support_probability_or_nonfinite_changes():
    parent = dict(A=dict(z1="1/2", z2="1/2"))
    with pytest.raises(ValueError, match="state support"):
        diagnostics.direction_score(dict(A=dict(z1=2)), parent, parent)
    with pytest.raises(ValueError, match="non-finite"):
        diagnostics.direction_score(dict(A=dict(z1=math.inf, z2=0)), parent, parent)
    with pytest.raises(ValueError, match="not normalized"):
        diagnostics.q_distance(dict(A=dict(z1="1/2", z2="1/4")), parent, dict(A=1))


def test_original_encoded_partition_preserves_zero_target_context_and_EOS_layer():
    package = dict(package_id="p", task_id="A", state_id="z", whole_package_target_tokens=3)
    rows = [
        dict(row_sha256="context", target_positions=[], target_ids=[],
             layer_target_positions=dict(reason=[], tool=[], final=[])),
        dict(row_sha256="actual", target_positions=[2, 3, 4], target_ids=[101, 102, 999],
             layer_target_positions=dict(reason=[2], tool=[3, 4], final=[])),
    ]
    result = diagnostics.encoding_summary(package, rows)
    assert result["row_count"] == 2
    assert result["layer_tokens"] == dict(reason=1, tool=2, final=0)
    # The existing action EOS stays tool; this diagnosis never guesses final EOS.
    rows[1]["layer_target_positions"]["final"] = [4]
    with pytest.raises(ValueError, match="partition"):
        diagnostics.encoding_summary(package, rows)


def packages():
    return [
        dict(package_id="a1", task_id="A", state_id="z1", L_P=2, layer_tokens=dict(reason=2, tool=0, final=0)),
        dict(package_id="a2", task_id="A", state_id="z1", L_P=4, layer_tokens=dict(reason=1, tool=3, final=0)),
        dict(package_id="a3", task_id="A", state_id="z2", L_P=1, layer_tokens=dict(reason=0, tool=0, final=1)),
        dict(package_id="b", task_id="B", state_id="z1", L_P=1, layer_tokens=dict(reason=0, tool=0, final=1)),
    ]


def test_coefficients_use_each_branch_q_actual_batch_size_state_count_and_whole_LP():
    q = dict(A=dict(z1="4/5", z2="1/5"), B=dict(z1=1))
    batches = [dict(task_ids=["A", "B"]), dict(task_ids=["A"])]
    result = diagnostics.coefficient_mass(packages(), q, batches, expected_updates=2)
    assert result["coefficient_mass"] == pytest.approx(dict(reason=0.75, tool=0.45, final=0.8))
    assert result["total_coefficient_mass"] == pytest.approx(2)
    assert result["per_task"]["A"]["exposure"] == "3/2"
    parent = dict(A=dict(z1="1/2", z2="1/2"), B=dict(z1=1))
    held = diagnostics.coefficient_mass(packages(), parent, batches, expected_updates=2)
    assert held["coefficient_mass"] != result["coefficient_mass"]
    assert not result["actual_loss_or_gradient_contribution"]


@pytest.mark.parametrize("problem", ["duplicate_package", "wrong_LP", "duplicate_task_batch"])
def test_coefficient_mass_cannot_drop_or_duplicate_supervision(problem):
    material = packages()
    batches = [dict(task_ids=["A", "B"]), dict(task_ids=["A"])]
    if problem == "duplicate_package":
        material.append(copy.deepcopy(material[0]))
    elif problem == "wrong_LP":
        material[0]["L_P"] = 3
    else:
        batches[0]["task_ids"] = ["A", "A"]
    with pytest.raises(ValueError):
        diagnostics.coefficient_mass(material, dict(A=dict(z1="1/2", z2="1/2"), B=dict(z1=1)),
                                     batches, expected_updates=2)


def test_feedback_coverage_keeps_700_and_distinguishes_episode_task_and_source_counts():
    scores = [dict(task_id=f"task{i % 350}") for i in range(700)]
    rewards = [int(i in (0, 1, 350, 351)) for i in range(700)]
    result = diagnostics.feedback_coverage(rewards, scores, {f"task{i}": "one-source" for i in range(350)})
    assert result["denominator"] == 700
    assert result["successful_episodes"] == 4 and result["successful_unique_tasks"] == 2
    assert result["successful_source_groups"] == 1
    assert result["successful_episodes_by_draw"] == [2, 2]


def test_metadata_refuses_tensor_conversion():
    class FakeTensor:
        def item(self):
            pytest.fail("a gradient tensor must not be accessed")
        def tolist(self):
            pytest.fail("a gradient tensor must not be accessed")
    with pytest.raises(ValueError, match="cannot access Tensor"):
        diagnostics._plain_metadata(dict(C=FakeTensor()))


def test_workspace_cannot_run_formal_diagnostic_before_frozen_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics.binding, "checked", lambda path: {"sha256": {}})
    with pytest.raises(ValueError, match="byte-frozen V63 entry"):
        diagnostics._frozen_entry(tmp_path)


@pytest.mark.parametrize("active,complete", [([{"pid": 1}], True), ([], False)])
def test_postrun_gate_prevents_reading_scores_before_all_real_exits(tmp_path, monkeypatch, active, complete):
    jobs = {f"j{i}": dict(job_id=f"j{i}") for i in range(24)}
    table = {
        "protocol/record.json": dict(id="protocol"),
        "evaluations/registration/record.json": dict(id="plan", protocol_id="protocol", jobs=jobs),
        "evaluation_barrier/record.json": dict(protocol_id="protocol",
            all_24_generation_jobs_complete=complete, all_dispatched_evaluation_workers_exited=complete,
            active_children=active, job_results=jobs),
    }
    reads = []
    def read(path):
        relative = str(Path(path).relative_to(tmp_path))
        reads.append(relative)
        assert relative in table, "an early diagnostic must not open partial score records"
        return table[relative]
    monkeypatch.setattr(diagnostics.binding, "checked", read)
    with pytest.raises(ValueError, match="all-24-generation"):
        diagnostics._postrun_admission(tmp_path)
    assert len(reads) == 3


@pytest.mark.parametrize("changed", [None, "path", "sha256"])
def test_postrun_uses_controller_barrier_result_bindings_and_all_scored_panels(tmp_path, monkeypatch, changed):
    jobs = {f"j{i}": dict(job_id=f"j{i}") for i in range(24)}
    def reference(path):
        return dict(path=str(path.resolve()), sha256=path.parts[-3] + "-sha")
    barrier = dict(protocol_id="protocol", all_24_generation_jobs_complete=True,
        all_dispatched_evaluation_workers_exited=True, active_children=[],
        job_results={key: reference(tmp_path / "evaluations/jobs" / key / "result/record.json") for key in jobs})
    if changed:
        barrier["job_results"]["j0"][changed] = "changed"
    table = {
        "protocol/record.json": dict(id="protocol"),
        "evaluations/registration/record.json": dict(id="plan", protocol_id="protocol", jobs=jobs),
        "evaluation_barrier/record.json": barrier,
    }
    for panel in (diagnostics.PRIMARY_PANEL, "step894_calibration120_greedy", "step894_calibration120_random_T1"):
        table[f"evaluations/panels/{panel}/summary/record.json"] = dict(registration_id="plan", panel=panel)
    reads = []
    def read(path):
        relative = str(Path(path).relative_to(tmp_path))
        reads.append(relative)
        return table[relative]
    monkeypatch.setattr(diagnostics.binding, "checked", read)
    monkeypatch.setattr(diagnostics.binding, "file_ref", reference)
    if changed:
        with pytest.raises(ValueError, match="result path or SHA"):
            diagnostics._postrun_admission(tmp_path)
        assert len(reads) == 3
    else:
        assert diagnostics._postrun_admission(tmp_path) == barrier
        assert len(reads) == 6


def test_cross_batch_table_keeps_new_utility_separate_and_checks_actual_same_parent():
    inputs = []
    parent = dict(A=dict(z1="1/2", z2="1/2"))
    for seed in diagnostics.SEEDS:
        for batch in (0, 1):
            for arm in diagnostics.NEW_ARMS:
                correct = (100 if arm == "C1" else 101) if not batch else (120 if arm == "C1" else 119)
                inputs.append(dict(seed=seed, arm=arm, feedback_batch=batch, id=f"{seed}-{arm}-{batch}",
                    parent_state_digest=f"parent{seed}", parent_pi=parent, mu=dict(A=1),
                    C=dict(A=dict(z1=2, z2=-2)), q=dict(A=dict(z1="3/5", z2="2/5")),
                    utility=dict(correct=correct, unknown=0)))
    result = diagnostics.cross_batch_table(inputs)
    assert len(result["same_temperature_across_batches"]) == 6
    assert all(row["utility_C05_minus_C1_correct"] == -1 for row in result["same_batch_across_temperatures"]
               if row["feedback_batch"] == 1)
    assert result["batches_pooled_into_new_primary"] is False
    inputs[0]["parent_state_digest"] = "wrong-parent"
    with pytest.raises(ValueError, match="identical real parent"):
        diagnostics.cross_batch_table(inputs)
