"""New six-session controls and one complete constructed-HTTP worker/analysis test.

No real Provider, production tokenizer, old financial replay or historical
success relabeling is permitted. Fixture model envelopes are not model evidence.
"""

from __future__ import annotations

import copy
import socket
import threading
from collections import Counter
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import share_adapter
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.final_public_contract import public_final_contract
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore, PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding.rules import quotient_rule
from trusted_synthesis.experiments.finance_qa_vnext_final_publication import plan, runner
from trusted_synthesis.experiments.finance_qa_vnext_final_publication.source import load_inputs
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import read_json, record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    HTTPResponse,
    HttpxSender,
)

ROOT = Path(__file__).resolve().parents[2]


def forbidden(*args, **kwargs):
    pytest.fail(
        "focused plan/scheduling test attempted Provider, Runtime, Operation, or old Share source"
    )


@pytest.fixture(autouse=True)
def no_execution_or_legacy_source(monkeypatch, request):
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    if request.node.name not in {
        "test_full_six_worker_and_analysis_constructed_http_only",
    }:
        monkeypatch.setattr(PublicQARuntime, "run", forbidden)
        monkeypatch.setattr(BoundShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(share_adapter, "load_share_source", forbidden)
    monkeypatch.setattr(share_adapter.ShareTaskAdapter, "__init__", forbidden)
    monkeypatch.setattr(runner.online_runner, "_credential", forbidden)


@pytest.fixture(scope="module")
def sealed_inputs():
    return load_inputs(ROOT)


@pytest.fixture(scope="module")
def source_inputs(sealed_inputs):
    inputs = sealed_inputs
    adapters = [inputs["adapters"][key] for key in plan.TASK_KEYS]
    bindings = [adapter.source.binding_record for adapter in adapters]
    implementation = record(
        "implementation", source_commit="isolated-plan-test-no-commit-claim", synthetic_control=True
    )
    policy = record(
        "task_panel_representation_policy",
        maximum_sequence_length=32768,
        truncation=False,
        isolated_plan_metadata_not_tokenizer_check=True,
    )
    return adapters, bindings, implementation, policy, quotient_rule()


@pytest.fixture
def prepared_plan(source_inputs):
    condition, registrations, panel = plan.freeze_condition(*source_inputs)
    return {
        "condition": condition,
        "registrations": registrations,
        "panel": panel,
        "implementation": source_inputs[2],
        "representation_policy": source_inputs[3],
        "quotient_rule": source_inputs[4],
        "configurations": {profile: plan.configuration(profile) for profile in ("N", "E")},
        "comparison_contract": record(
            "final_publication_comparison_contract", isolated_scheduling_test=True
        ),
        "history_inventory": record(
            "final_publication_history_inventory", isolated_scheduling_test=True
        ),
        "manifest": record("preparation_manifest", isolated_scheduling_test=True),
        "report": record("final_publication_preparation", isolated_scheduling_test=True),
    }


def test_three_real_bindings_six_frozen_sessions_and_uniform_task_marginal(prepared_plan):
    condition, rows = prepared_plan["condition"], prepared_plan["registrations"]
    assert condition["task_count"] == 3 and condition["registered_session_count"] == 6
    assert condition["source_keys"] == ["unp_2016", "jpm_2014", "jpm_2015"]
    assert [row["label"] for row in rows] == list(plan.LABELS)
    assert len({row["id"] for row in rows}) == len({row["session_id"] for row in rows}) == 6
    assert len({row["task_id"] for row in rows}) == len({row["context_id"] for row in rows}) == 3
    assert Counter((row["task_group"], row["profile"]) for row in rows) == {
        (task, profile): 1 for task in plan.TASK_KEYS for profile in ("N", "E")
    }
    assert all(
        row["numerator"] == 1 and row["denominator"] == 3 for row in condition["task_marginal"]
    )
    assert [len(wave) for wave in condition["waves"]] == [6]
    assert [label for wave in condition["waves"] for label in wave] == list(plan.LABELS)
    assert all(
        row["run_condition_id"] == condition["id"]
        and not row["replacement_allowed"]
        and row["reference_route"] is None
        for row in rows
    )
    assert condition["independent_evaluation_bound_and_ready"] is False
    assert condition["old_panel_task_marginal_modified"] is False


def test_same_fixed_per_request_per_session_and_exact_new_cohort_budget(prepared_plan):
    condition = prepared_plan["condition"]
    assert condition["maximum_provider_attempts"] == 6 * 32 == 192
    assert condition["maximum_reserved_token_allowance"] == 192 * 107520 == 20643840
    for profile in ("N", "E"):
        config = plan.configuration(profile).as_record()
        assert config["maximum_pilot_attempts"] == 192 and config["attempts_per_session"] == 32
        assert config["max_tokens"] == 8192 and config["maximum_serialized_request_bytes"] == 98304
        assert config["maximum_request_reserved_tokens"] == 107520
        assert config["system_prompt"] == condition["profiles"][profile]["system_prompt"]
        assert config["automatic_retries"] == config["model_fallbacks"] == 0
    assert condition["maximum_actions_per_session"] == 12
    assert condition["maximum_submissions_per_session"] == 32
    assert (
        condition["student_forward_calls"]
        == condition["student_parameter_updates"]
        == condition["gpu_jobs"]
        == 0
    )


def test_each_worker_adapter_is_fresh_and_bound_to_its_registered_new_task(prepared_plan):
    panel = prepared_plan["panel"]
    for task in prepared_plan["condition"]["tasks"]:
        first, second = panel.adapter(task["task_key"]), panel.adapter(task["task_key"])
        assert first is not second and first.registry is not second.registry
        assert first.source.source_key == task["source_key"]
        assert first.context["id"] == second.context["id"] == task["context_id"]
        assert first.context["task_id"] == task["task_id"]
    with pytest.raises(ProtocolError, match="registered_adapter_key"):
        panel.adapter("S")


def test_all_six_initial_requests_keep_full_legal_space_and_exact_profile_prompts(prepared_plan):
    control, requests = plan.wiring_controls(
        prepared_plan["panel"], prepared_plan["condition"], prepared_plan["registrations"]
    )
    assert control["all_expected_outcomes"] and len(requests) == len(control["rows"]) == 6
    assert control["provider_calls"] == control["runtime_calls"] == control["operation_calls"] == 0
    assert control["maximum_initial_body_bytes"] <= 98304
    for task in plan.TASK_KEYS:
        neutral, guided = requests[f"{task}_N01"], requests[f"{task}_E01"]
        assert canonical_json_bytes(neutral["public"]) == canonical_json_bytes(guided["public"])
        assert neutral["http"]["messages"][0] != guided["http"]["messages"][0]
        assert neutral["http"]["messages"][1] == guided["http"]["messages"][1]
        assert len(neutral["public"]["available_actions"]) == 2
    assert len({requests[f"{task}_N01"]["public"]["context"]["id"] for task in plan.TASK_KEYS}) == 3


@pytest.mark.parametrize(
    "change",
    [
        "missing_source",
        "source_order",
        "source_record",
        "duplicate_source",
        "changed_policy",
        "changed_run_tag",
    ],
)
def test_no_silent_source_substitution_or_smaller_panel(source_inputs, change):
    adapters, bindings, implementation, policy, rule = source_inputs
    adapters, bindings, policy = list(adapters), copy.deepcopy(bindings), copy.deepcopy(policy)
    kwargs = {}
    if change == "missing_source":
        adapters.pop()
        bindings.pop()
    elif change == "source_order":
        adapters.reverse()
        bindings.reverse()
    elif change == "source_record":
        bindings[0]["id"] = "not-the-actual-bound-source"
    elif change == "duplicate_source":
        adapters[1] = adapters[0]
        bindings[1] = bindings[0]
    elif change == "changed_policy":
        policy = record(
            "task_panel_representation_policy", maximum_sequence_length=65536, truncation=False
        )
    else:
        kwargs["run_tag"] = "changed-after-observing-a-result"
    with pytest.raises(ProtocolError):
        plan.freeze_condition(adapters, bindings, implementation, policy, rule, **kwargs)


def install_scheduling_controls(tmp_path, monkeypatch, preparation, behavior):
    from trusted_synthesis.experiments.finance_qa_vnext_final_publication import stage

    monkeypatch.setattr(stage, "_target", lambda root, output: (root, output))
    monkeypatch.setattr(stage, "prepared", lambda root, output: preparation)
    monkeypatch.setattr(runner, "verify_source_snapshot", lambda root, implementation: None)
    monkeypatch.setattr(runner, "history_inventory", lambda root: preparation["history_inventory"])
    monkeypatch.setattr(
        runner.online_runner, "_credential", lambda path: "isolated-unit-key-not-provider"
    )
    launched, lock, active = [], threading.Lock(), {"current": 0, "maximum": 0}
    barrier = threading.Barrier(6) if behavior == "success" else None

    def qualification_record(registration, status):
        missing = status == "unknown"
        return record(
            "qualification",
            registration_id=registration["id"],
            registered_session_id=registration["session_id"],
            label=registration["label"],
            status=status,
            reason="synthetic_worker_exception" if missing else None,
            provider_attempt_count=None if missing else 0,
            runtime_submission_count=None if missing else 0,
            synthetic_scheduler_control_not_model_evidence=True,
        )

    def worker(panel, config, registration, child, start, api_key):
        assert api_key == "isolated-unit-key-not-provider"
        adapter = panel.adapter(registration["task_group"])
        assert adapter.context["id"] == registration["context_id"]
        assert adapter.context["task_id"] == registration["task_id"]
        assert config.as_record()["id"] == registration["model_configuration_id"]
        with lock:
            launched.append(registration["label"])
            active["current"] += 1
            active["maximum"] = max(active["maximum"], active["current"])
        try:
            if behavior == "unknown" and registration["label"] == "T01_N01":
                raise RuntimeError("isolated worker failure before any Runtime")
            if barrier:
                barrier.wait(timeout=10)
            status = (
                "known_failure"
                if behavior == "known_failure" and registration["label"] == "T01_N01"
                else "success"
            )
            result = qualification_record(registration, status)
            child.json("qualification.json", result)
            seal_directory(
                child, kind="online_session_manifest", registration_id=registration["id"]
            )
            return result
        finally:
            with lock:
                active["current"] -= 1

    def unfinished(
        adapter, registration, session, runtime_directory, transport_directory, *, start_record
    ):
        assert adapter.context["id"] == registration["context_id"] and session is None
        return qualification_record(
            registration, "unknown" if start_record["status"] == "started" else "not_started"
        )

    monkeypatch.setattr(runner.online_runner, "_run_session", worker)
    monkeypatch.setattr(runner, "qualify_session", unfinished)

    def analyze(root, prepared, directory):
        values = read_json((directory / "qualifications.json").read_bytes())
        return record(
            "final_publication_report",
            statuses=dict(Counter(item["status"] for item in values)),
            registered_session_count=len(values),
            synthetic_scheduling_control=True,
        )

    monkeypatch.setattr(runner, "analyze_new", analyze)
    return launched, active


@pytest.mark.parametrize("behavior", ["success", "known_failure", "unknown"])
def test_single_frozen_six_worker_wave_failure_nonreplacement_and_unknown_denominator(
    tmp_path, monkeypatch, prepared_plan, behavior
):
    launched, active = install_scheduling_controls(tmp_path, monkeypatch, prepared_plan, behavior)
    report = runner.run(ROOT, tmp_path)
    assert report["registered_session_count"] == 6
    assert active["maximum"] <= 6
    schedule = read_json((tmp_path / "execution/schedule.json").read_bytes())
    assert [event["label"] for event in schedule["events"]] == list(plan.LABELS)
    if behavior == "success":
        assert report["statuses"] == {"success": 6} and active["maximum"] == 6
        assert set(launched[:6]) == set(prepared_plan["condition"]["waves"][0])
    elif behavior == "known_failure":
        assert report["statuses"] == {"success": 5, "known_failure": 1}
        assert len(launched) == len(set(launched)) == 6 and schedule["halt_reason"] is None
    else:
        assert report["statuses"] == {"success": 5, "unknown": 1}
        assert set(launched) == set(prepared_plan["condition"]["waves"][0])
        assert all(event["status"] == "started" for event in schedule["events"])
    with pytest.raises(ProtocolError, match="population_already_started"):
        runner.run(ROOT, tmp_path)


def test_attempt_metrics_preserve_unknown_instead_of_fabricating_total_zero():
    measured = runner._transport_report([{"attempts": 32}, {"attempts": None}], [])
    assert measured["provider_attempt_count"] is None
    assert measured["known_attempt_count_lower_bound"] == 32
    assert measured["reserved_allowance_used"] is None
    assert measured["usage"]["total_tokens"]["observed_total"] is None
    assert measured["maximum_registered_attempts"] == 192
    with pytest.raises(ProtocolError, match="session_attempt_bound"):
        runner._transport_report([{"attempts": 33}], [])
    with pytest.raises(ProtocolError, match="total_attempt_bound"):
        runner._transport_report([{"attempts": 32}] * 7, [])


def test_initial_artifact_runtime_and_independent_request_are_identical(tmp_path, prepared_plan):
    from trusted_synthesis.domains.finance.qa_vnext.measurement import _request
    from trusted_synthesis.domains.finance.qa_vnext.protocol import contract

    for task_key in plan.TASK_KEYS:
        adapter = prepared_plan["panel"].adapter(task_key)
        runtime = PublicQARuntime(
            adapter,
            PublicFixtureCallback(),
            tmp_path / task_key,
            max_actions=12,
            max_submissions=32,
        )
        frozen = plan.initial_request(adapter)
        independent = _request(adapter, runtime.state(), contract())
        assert canonical_json_bytes(frozen) == canonical_json_bytes(runtime.request())
        assert canonical_json_bytes(frozen) == canonical_json_bytes(independent)
        assert frozen["public_final_contract"] == public_final_contract()
        assert frozen["state"]["accepted_claims"] == []
        assert frozen["final_claim_ids"] == []
        assert (
            frozen["response_schemas"]["final"]["properties"]["result"]["additionalProperties"]
            is False
        )
        old_adapter = BoundShareTaskAdapter(adapter.source)
        assert old_adapter.context == adapter.context
        assert old_adapter.registry.manifest() == adapter.registry.manifest()


def test_frozen_final_contract_source_commit_and_new_population_bindings(prepared_plan):
    from trusted_synthesis.experiments.finance_qa_vnext_final_publication.measurement import (
        measurement_application,
    )

    condition = prepared_plan["condition"]
    assert condition["final_public_contract_id"] == public_final_contract()["id"]
    assert condition["measurement_application_id"] == measurement_application()["id"]
    assert condition["rule_id"] == quotient_rule()["id"]
    assert condition["source_commit"] == prepared_plan["implementation"]["source_commit"]
    assert condition["sessions_per_task"] == 2 and condition["sessions_per_task_profile"] == 1
    assert condition["maximum_total_same_task_pairs"] == 3
    assert not condition["concurrent_old_presentation_control"]
    assert not condition["precise_causal_effect_of_publication_claimed"]
    assert not condition["historical_twelve_session_denominator_imported"]
    assert not condition["financial_verification_standard_changed"]
    assert not condition["final_response_host_repair_allowed"]


def _progress_event(sequence, kind, admitted, *, claim=None, diagnostic=None, parsed=True):
    submitted = {"kind": kind, "fixture": "descriptive-not-a-real-model-result"}
    return {
        "sequence": sequence,
        "request": {
            "id": f"constructed-request:{sequence}",
            "state": {"id": f"constructed-state:{sequence}"},
            "public_final_contract": public_final_contract(),
        },
        "submission": {"id": f"constructed-submission:{sequence}"},
        "parsed": (
            {**submitted, **({"disposition": "accept"} if kind == "update" else {})}
            if parsed
            else None
        ),
        "receipt": {
            "id": f"constructed-receipt:{sequence}",
            "admitted": admitted,
            "error_code": None if admitted else "admission.final_qa",
        },
        "claim": claim,
        "post_state": {
            "last_feedback": None
            if admitted
            else {
                "admitted": False,
                "code": "admission.final_qa",
                "public_diagnostic": diagnostic,
            }
        },
    }


def test_progress_preserves_first_final_rejection_then_later_success(monkeypatch):
    monkeypatch.setattr(BoundShareTaskAdapter, "verify_final", forbidden)
    claim = {
        "id": "constructed-claim:percent",
        "observation_id": "constructed-observation:percent",
        "status": "accepted",
        "obligation_id": "percent",
        "proposition": {"operation": "scale_percent", "output": {"value": "raw-precision"}},
    }
    diagnostic = {"extra_fields": ["metric"], "response_rewritten": False}
    session = {
        "id": "constructed-session:not-model-evidence",
        "events": [
            _progress_event(0, "update", True, claim=claim),
            _progress_event(1, "final", False, diagnostic=diagnostic),
            _progress_event(2, "final", True),
        ],
    }
    qualification = record(
        "qualification",
        status="success",
        qualified=True,
        qa_valid=True,
        evidence_complete=True,
        constructed_control=True,
    )
    before = canonical_json_bytes(session)
    measured = runner._final_progress(session, qualification)
    assert canonical_json_bytes(session) == before
    assert measured["first_accepted_percent_claim"]["claim_id"] == claim["id"]
    assert measured["first_final"]["sequence"] == 1
    assert measured["first_final_admitted"] is False
    assert measured["final_submission_count"] == 2 and measured["final_qualified"] is True
    assert measured["final_public_diagnostics"] == [
        {"sequence": 1, "public_diagnostic": diagnostic}
    ]
    assert measured["qualification_recomputed"] is False
    assert measured["final_verification_recomputed"] is False


def test_schema_rejected_raw_final_is_not_skipped_by_first_final_metric(tmp_path):
    session = {
        "id": "constructed-session:raw-final",
        "events": [
            _progress_event(0, "final", False, parsed=False),
            _progress_event(1, "final", True),
        ],
    }
    DurableStore(tmp_path / "runtime").json(
        "turns/000_response.txt", {"kind": "final", "result": {}}
    )
    measured = runner._final_progress(
        session, record("qualification", status="success", qualified=True), tmp_path / "runtime"
    )
    assert measured["first_final"]["sequence"] == 0
    assert measured["first_final_admitted"] is False
    assert measured["first_final"]["protocol_parsed"] is False
    assert measured["final_submission_count"] == 2


def test_unclassifiable_prefix_keeps_first_final_certainty_unknown(tmp_path):
    session = {
        "id": "constructed-session:malformed-prefix",
        "events": [
            _progress_event(0, "unknown", False, parsed=False),
            _progress_event(1, "final", True),
        ],
    }
    DurableStore(tmp_path / "runtime").write("turns/000_response.txt", b"{not-valid-json")
    measured = runner._final_progress(
        session, record("qualification", status="unknown", qualified=False), tmp_path / "runtime"
    )
    assert measured["unclassified_raw_submission_count"] == 1
    assert measured["first_final"]["admitted"] is True
    assert measured["first_final_admitted"] is None
    assert measured["first_final_kind_certain"] is False


class CharacterTokenizer:
    """Fresh in-memory codec fixture, not a production tokenizer or length validation."""

    chat_template = "test-only-final-publication-character-codec"
    all_special_ids = [151645, 151643]

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize is False
        prefix = "S:" + messages[0]["content"] + "U:" + messages[1]["content"] + "A:"
        return (
            prefix if add_generation_prompt else prefix + messages[-1]["content"] + "<|im_end|>\n"
        )

    def __call__(self, value, **kwargs):
        assert kwargs.get("truncation") is False and kwargs.get("padding") is False
        suffix = value.endswith("<|im_end|>\n")
        text = value[:-11] if suffix else value
        ids = [ord(character) + 1000 for character in text]
        offsets = [(index, index + 1) for index in range(len(text))]
        if suffix:
            ids += [151645, 198]
            offsets += [(len(text), len(value) - 1), (len(value) - 1, len(value))]
        return {"input_ids": ids, "attention_mask": [1] * len(ids), "offset_mapping": offsets}

    def decode(self, ids, **kwargs):
        return "".join(
            "<|im_end|>" if value == 151645 else "\n" if value == 198 else chr(value - 1000)
            for value in ids
        )


def test_full_six_worker_and_analysis_constructed_http_only(
    tmp_path, monkeypatch, source_inputs, prepared_plan
):
    """Actual runner/worker/qualifier/root-analysis wiring with fixture HTTP only."""
    from trusted_synthesis.experiments.finance_qa_vnext_final_publication import (
        measurement,
        representation,
        stage,
    )

    binding = {
        "id": "constructed-six-in-memory-tokenizer-reference",
        "maximum_sequence_length": 24576,
        "chat_template": CharacterTokenizer.chat_template,
        "chat_template_sha256": "constructed-character-codec-template-hash",
        "software_versions": {"test": "in-memory-not-production-assets"},
        "pad_token_id": 151643,
    }
    asset = representation.panel.length_core.record(
        "tokenizer_assets",
        actual_max_position_embeddings=32768,
        actual_rope_scaling=None,
        members=[{"fixture": index} for index in range(5)],
    )
    monkeypatch.setattr(representation.panel.length_core, "asset_binding", lambda value: asset)
    tokenizer, tokenizer_loads = CharacterTokenizer(), []
    monkeypatch.setattr(
        representation.panel.assets,
        "load_tokenizer",
        lambda value: tokenizer_loads.append(value["id"]) or tokenizer,
    )
    policy = representation.representation_policy(binding)
    adapters, source_records, implementation, _, rule = source_inputs
    condition, registrations, panel = plan.freeze_condition(
        adapters, source_records, implementation, policy, rule
    )
    preparation = {
        **prepared_plan,
        "condition": condition,
        "registrations": registrations,
        "panel": panel,
        "tokenizer_binding": binding,
        "representation_policy": policy,
        "comparison_contract": measurement.comparison_contract(condition, rule),
    }
    by_session = {row["session_id"]: row for row in registrations}
    observed, qualification_calls, lock = [], [], threading.Lock()
    injected_final_errors, observed_correction_feedback = [], []
    original_qualify = runner.online_runner.qualify_session

    def qualify_once(*args, **kwargs):
        with lock:
            qualification_calls.append(args[1]["id"])
        return original_qualify(*args, **kwargs)

    def send(sender, http, *, api_key):
        assert api_key == "full-six-constructed-http-never-provider"
        registration = by_session[http["session_id"]]
        public = read_json(http["messages"][1]["content"].encode())
        profile = registration["profile"]
        assert public["public_final_contract"] == public_final_contract()
        assert public["context"]["id"] == registration["context_id"]
        assert http["messages"][0]["content"] == condition["profiles"][profile]["system_prompt"]
        if http["attempt_index"] == 0:
            assert public["state"]["accepted_claims"] == []
            assert canonical_json_bytes(public) == canonical_json_bytes(
                plan.initial_request(panel.adapter(registration["task_key"]))
            )
        raw = PublicFixtureCallback(
            support_preference="disclosed_total" if profile == "N" else "reconstructed_total"
        ).generate(public)
        constructed_response = read_json(raw)
        if registration["label"] == "T01_N01" and constructed_response["kind"] == "final":
            if not injected_final_errors:
                selected = next(
                    claim
                    for claim in public["state"]["accepted_claims"]
                    if claim["id"] == constructed_response["answer_claim_id"]
                )
                constructed_response["result"]["metric"] = selected["proposition"]["output"][
                    "metric"
                ]
                raw = canonical_json_bytes(constructed_response)
                injected_final_errors.append(http["attempt_index"])
            else:
                diagnostic = public["state"]["last_feedback"]["public_diagnostic"]
                assert "metric" in str(diagnostic)
                assert set(constructed_response["result"]) == {"value", "unit"}
                observed_correction_feedback.append(diagnostic)
        with lock:
            observed.append(registration["label"])
        return HTTPResponse(
            200,
            canonical_json_bytes(
                {
                    "id": f"constructed-full6-{registration['label']}-{http['attempt_index']}",
                    "object": "chat.completion",
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": raw.decode()},
                        }
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
                }
            ),
        )

    monkeypatch.setattr(HttpxSender, "send", send)
    monkeypatch.setattr(stage, "_target", lambda root, output: (root, output))
    monkeypatch.setattr(stage, "prepared", lambda root, output: preparation)
    monkeypatch.setattr(
        runner.online_runner, "_credential", lambda path: "full-six-constructed-http-never-provider"
    )
    monkeypatch.setattr(runner.online_runner, "qualify_session", qualify_once)
    monkeypatch.setattr(runner, "qualify_session", forbidden)
    monkeypatch.setattr(runner, "verify_source_snapshot", lambda root, snapshot: None)
    monkeypatch.setattr(runner, "history_inventory", lambda root: preparation["history_inventory"])

    report = runner.run(ROOT, tmp_path)
    measured = report["measurement"]
    assert len(observed) == report["provider_attempt_count"] == 37
    assert report["candidate_count"] == 36
    assert len(injected_final_errors) == len(observed_correction_feedback) == 1
    assert len(set(observed)) == len(qualification_calls) == len(set(qualification_calls)) == 6
    assert report["status_counts"] == {"success": 6}
    assert report["registered_session_count"] == 6
    assert report["accepted_percent_claim_session_count"] == 6
    assert report["first_final_admitted_count"] == 5
    for row in report["session_rows"]:
        if row["label"] == "T01_N01":
            assert row["first_final_admitted"] is False and row["final_submission_count"] == 2
            assert row["final_public_diagnostics"]
        else:
            assert row["first_final_admitted"] is True and row["final_submission_count"] == 1
    assert measured["qualified_count"] == measured["assigned_qualified_count"] == 6
    assert measured["pair_count"] == 3 and measured["cross_task_state_comparisons"] == 0
    assert measured["tasks_with_DR_witness"] == 3
    assert measured["panel_success_fraction"] == {"numerator": 6, "denominator": 6}
    assert len(measured["classes"]) == 6 and len(measured["task_rows"]) == 3
    assert len(tokenizer_loads) == 1
    assert report["token_fit_count"] + report["token_not_fit_count"] == 36
    assert report["execution_guards"]["all_zero"] is True
    assert all(
        row["provider_attempt_count"] < 32
        for row in read_json((tmp_path / "execution/qualifications.json").read_bytes())
    )
    assert (tmp_path / "execution/manifest.json").is_file()


def test_prior_tasks_contexts_sources_and_sampling_parameters_are_unchanged(
    sealed_inputs, prepared_plan
):
    old = sealed_inputs["old_condition"]
    new = prepared_plan["condition"]
    preserved_fields = (
        "task_key",
        "source_key",
        "source_binding_id",
        "source_record_id",
        "task_id",
        "context_id",
        "registry_hash",
        "source_binding",
        "context",
    )
    for previous, current in zip(old["tasks"], new["tasks"], strict=True):
        assert all(previous[field] == current[field] for field in preserved_fields)
    assert old["profiles"] == new["profiles"]
    changed_budget_fields = {"id", "maximum_pilot_attempts", "maximum_pilot_reserved_tokens"}
    for profile in ("N", "E"):
        old_config, new_config = old["configurations"][profile], new["configurations"][profile]
        assert set(old_config) == set(new_config)
        assert {
            key: value for key, value in old_config.items() if key not in changed_budget_fields
        } == {key: value for key, value in new_config.items() if key not in changed_budget_fields}
    old_ids = {row["session_id"] for row in sealed_inputs["old_registrations"]}
    assert not old_ids & {row["session_id"] for row in prepared_plan["registrations"]}
    assert old["registered_session_count"] == 12 and new["registered_session_count"] == 6
