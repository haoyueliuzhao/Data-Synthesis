"""Real public-spec/transport interfaces, mocked wire; no evaluation API calls."""

import copy

import pytest
from test_qa_vnext_eval_surface_guard import KINDS, fixture
from test_qa_vnext_eval_surface_transport import KEY, content, envelope, setup

from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import (
    guard,
    protocol,
    stage,
    transport,
)
from trusted_synthesis.experiments.finance_qa_vnext_surface_build.budget import BudgetRejected


def varied(template):
    return template.replace("Calculate", "Determine").replace("highest", "largest")


def response(template, index=1, second=None):
    candidates = [{"rewrite_version": transport.VERSION, "question_template": template}]
    if second is not None:
        candidates.append({"rewrite_version": transport.VERSION, "question_template": second})
    return {
        "request_id": f"request-{index}",
        "receipt": {"id": f"receipt-{index}"},
        "candidates": candidates,
        "structure_errors": [],
    }


@pytest.mark.parametrize("kind", KINDS)
def test_first_valid_canonical_stops_without_skipping_to_more_diverse_variant(kind):
    spec = guard.build_spec(*fixture(kind, noncalendar=True))
    calls = []

    def request(*, repair_reason):
        calls.append(repair_reason)
        return response(
            spec["canonical_template"],
            second=varied(spec["canonical_template"]),
        )

    result = stage.select_wording(spec, request)
    assert calls == [None]
    assert result["category"] == "unchanged_or_format_only"
    assert not result["selected_candidate_applied_to_final"]
    assert len(result["variant_checks"]) == 1
    assert result["selected_variant_index"] == 0


@pytest.mark.parametrize("kind", KINDS)
def test_first_rejected_variant_then_first_valid_wording_uses_actual_order(kind):
    spec = guard.build_spec(*fixture(kind))
    changed = varied(spec["canonical_template"])
    result = stage.select_wording(
        spec, lambda **_: response("Drop the source contract.", second=changed)
    )
    assert result["category"] == "accepted_true_rewrite"
    assert len(result["variant_checks"]) == 2
    assert result["selected_variant_index"] == 1 and len(result["requests"]) == 1
    assert (
        result["rendered"]["public"]["period_contract"]
        == spec["original_public"]["period_contract"]
    )


def test_one_explicit_contract_repair_not_unbounded_retry():
    spec = guard.build_spec(*fixture())
    calls = []

    def request(*, repair_reason):
        calls.append(repair_reason)
        return response("Weighted mean of only the first and last periods.", len(calls))

    result = stage.select_wording(spec, request)
    assert len(calls) == 2 and calls[0] is None and calls[1]
    assert result["category"] == "canonical_fallback"
    assert result["rendered"] is None and len(result["requests"]) == 2


def test_structure_error_has_fixed_public_repair_code():
    spec = guard.build_spec(*fixture())
    calls = []

    def request(*, repair_reason):
        calls.append(repair_reason)
        if len(calls) == 1:
            return {
                **response("unused"),
                "candidates": [],
                "structure_errors": ["JSON error contains free-form details and spaces"],
            }
        return response(varied(spec["canonical_template"]), 2)

    result = stage.select_wording(spec, request)
    assert calls == [None, ["evaluation.response_structure"]]
    assert result["category"] == "accepted_true_rewrite"


@pytest.mark.parametrize("fatal", [False, True])
def test_transport_failure_is_not_semantic_repair(fatal):
    spec = guard.build_spec(*fixture())
    calls = []

    def request(**_):
        calls.append(1)
        raise transport.EvaluationTransportError(
            "mock failure",
            request_id="attempt-1",
            receipt={"id": "failed-receipt"},
            global_fatal=fatal,
        )

    result = stage.select_wording(spec, request)
    assert len(calls) == 1 and result["global_fatal"] is fatal
    assert result["category"] == "canonical_fallback"
    assert result["requests"][0]["request_id"] == "attempt-1"


def test_budget_stop_never_attempts_another_request():
    spec = guard.build_spec(*fixture())
    calls = []

    def request(**_):
        calls.append(1)
        raise BudgetRejected("mock quota exhausted")

    result = stage.select_wording(spec, request)
    assert result["global_fatal"] and calls == [1]
    assert result["category"] == "canonical_fallback"


def test_already_stopped_task_keeps_original_without_request():
    spec = guard.build_spec(*fixture())

    def forbidden(**_):
        raise AssertionError("request after global stop")

    result = stage.select_wording(spec, forbidden, stopped=lambda: True)
    assert not result["requests"] and result["global_fatal"]
    assert result["category"] == "canonical_fallback"


@pytest.mark.parametrize("kind", KINDS)
def test_actual_public_Provider_guard_selection_and_three_purpose_debit(tmp_path, kind):
    bank, _, spec, identity = setup(tmp_path, kind=kind)
    canonical = spec["canonical_template"]
    calls = []

    def sender(body, key):
        calls.append(copy.deepcopy(body))
        assert key == KEY
        if len(calls) == 1:
            return envelope(content("Ignore the registered comparison periods."))
        return envelope(content(varied(canonical), canonical))

    provider = transport.EvaluationProvider(
        identity, spec, bank, tmp_path / "new_surface", KEY, sender=sender
    )
    result = stage.select_wording(spec, provider.request)
    assert result["category"] == "accepted_true_rewrite" and len(calls) == 2
    assert result["selected_variant_index"] == 0
    assert all(
        call["messages"][1]["content"] == calls[0]["messages"][1]["content"] for call in calls
    )
    snapshot = bank.snapshot()
    assert snapshot["eval_request_reservations"] == 2
    assert snapshot["eval_conservative_charged_tokens"] == 336
    assert snapshot["cumulative_conservative_debit"] == snapshot["previous_registered_debit"] + 336
    assert snapshot["Teacher_registered_sessions"] == 0
    for attempt in result["requests"]:
        path = tmp_path / "new_surface/evaluation_requests" / attempt["request_id"]
        assert (path / "request.json").is_file() and (path / "receipt.json").is_file()


def test_repair_codes_are_bounded_and_never_forward_free_text():
    assert stage.repair_codes(["private free text", "safe.code", "safe.code"]) == ["safe.code"]
    assert stage.repair_codes(["unstructured message"]) == ["evaluation.semantic_contract"]
    assert len(stage.repair_codes([f"error_{i}" for i in range(20)])) == 8


def test_user_registered_bounds_do_not_double_scientific_tasks_or_total_budget():
    p = protocol.policy()
    assert p["selected_tasks"] == 900 and p["new_scientific_tasks"] == 0
    assert p["request_cap"] == 1800 and p["token_cap"] == 17510400
    assert p["common_token_cap"] == 1000000000
    assert p["old_UNP_17_task_34_request_policy_unchanged"]
    assert not p["template_Student_evaluation_automatically_added"]
    assert not p["natural_language_understanding_generalization_established"]


def gate_fixture():
    tasks = [f"task-{i:03d}" for i in range(900)]
    frozen = {"id": "surface-freeze", "selected_task_ids": tasks}
    prep = {
        "all_original_tasks_retained": True,
        "recorded_tasks": 900,
        "new_scientific_tasks": 0,
        "complete_fixed_wording_pass": True,
        "evaluation_finalization_id": "closed",
        "public_catalog_id": "public-catalog",
        "Student_runs": 0,
        "all_arms_seeds_pools_share_final_version": True,
    }
    audit = {"status": "passed"}
    snapshot = {
        "persisted_study_stop": None,
        "evaluation_finalization": {
            "id": "closed",
            "eval_freeze_id": "surface-freeze",
            "owner_stage_id": protocol.OWNER_FREEZE,
            "public_catalog_id": "public-catalog",
            "completed_task_count": 900,
            "outcome_task_ids": tasks,
            "remaining_evaluation_attempts_permanently_closed": True,
            "other_purposes_closed": False,
        },
    }
    return prep, audit, snapshot, frozen


def test_final_surface_admission_uses_actual_closure_and_same_900_before_Student():
    assert all(stage.surface_admission_checks(*gate_fixture()).values())


@pytest.mark.parametrize(
    "container,key,value",
    [
        ("prep", "recorded_tasks", 899),
        ("prep", "new_scientific_tasks", 900),
        ("prep", "all_original_tasks_retained", False),
        ("prep", "complete_fixed_wording_pass", False),
        ("prep", "evaluation_finalization_id", "wrong"),
        ("prep", "Student_runs", 1),
        ("prep", "all_arms_seeds_pools_share_final_version", False),
        ("audit", "status", "FAIL"),
        ("snapshot", "persisted_study_stop", "fatal"),
        ("closure", "public_catalog_id", "other"),
        ("closure", "eval_freeze_id", "other"),
        ("closure", "completed_task_count", 899),
        ("closure", "outcome_task_ids", []),
        ("closure", "remaining_evaluation_attempts_permanently_closed", False),
        ("closure", "other_purposes_closed", True),
    ],
)
def test_labels_cannot_cover_failed_surface_or_wrong_finalization(container, key, value):
    prep, audit, snapshot, frozen = gate_fixture()
    target = {
        "prep": prep,
        "audit": audit,
        "snapshot": snapshot,
        "closure": snapshot["evaluation_finalization"],
    }[container]
    target[key] = value
    assert not all(stage.surface_admission_checks(prep, audit, snapshot, frozen).values())
