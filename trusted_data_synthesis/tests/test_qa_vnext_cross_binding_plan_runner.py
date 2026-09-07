"""Actual new source/request wiring and mocked-worker scheduling, zero Provider calls.

Worker records in scheduling controls are explicitly fabricated test metadata.
The named constructed-HTTP integration separately exercises six new-source
fixture sessions, never real Provider/model samples. No historical outcome is
counted as a new sample.
"""

from __future__ import annotations

import copy
import socket
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import share_adapter
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore, PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding import plan, runner
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding.rules import quotient_rule
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding.source import load_sources
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
        "test_actual_worker_six_new_source_sessions_with_constructed_http_only",
        "test_full_twelve_worker_export_and_analysis_constructed_http_only",
    }:
        monkeypatch.setattr(PublicQARuntime, "run", forbidden)
        monkeypatch.setattr(BoundShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(share_adapter, "load_share_source", forbidden)
    monkeypatch.setattr(share_adapter.ShareTaskAdapter, "__init__", forbidden)
    monkeypatch.setattr(runner.online_runner, "_credential", forbidden)


@pytest.fixture(scope="module")
def source_inputs():
    sources = load_sources(ROOT)
    adapters = [BoundShareTaskAdapter(source) for source in sources]
    bindings = [source.binding_record for source in sources]
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
            "cross_binding_comparison_contract", isolated_scheduling_test=True
        ),
        "history_inventory": record(
            "cross_binding_history_inventory", isolated_scheduling_test=True
        ),
        "manifest": record("preparation_manifest", isolated_scheduling_test=True),
        "report": record("cross_binding_preparation", isolated_scheduling_test=True),
    }


def test_three_real_bindings_twelve_frozen_sessions_and_uniform_task_marginal(prepared_plan):
    condition, rows = prepared_plan["condition"], prepared_plan["registrations"]
    assert condition["task_count"] == 3 and condition["registered_session_count"] == 12
    assert condition["source_keys"] == ["unp_2016", "jpm_2014", "jpm_2015"]
    assert [row["label"] for row in rows] == list(plan.LABELS)
    assert len({row["id"] for row in rows}) == len({row["session_id"] for row in rows}) == 12
    assert len({row["task_id"] for row in rows}) == len({row["context_id"] for row in rows}) == 3
    assert Counter((row["task_group"], row["profile"]) for row in rows) == {
        (task, profile): 2 for task in plan.TASK_KEYS for profile in ("N", "E")
    }
    assert all(
        row["numerator"] == 1 and row["denominator"] == 3 for row in condition["task_marginal"]
    )
    assert [len(wave) for wave in condition["waves"]] == [6, 6]
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
    assert condition["maximum_provider_attempts"] == 12 * 32 == 384
    assert condition["maximum_reserved_token_allowance"] == 384 * 107520 == 41287680
    for profile in ("N", "E"):
        config = plan.configuration(profile).as_record()
        assert config["maximum_pilot_attempts"] == 384 and config["attempts_per_session"] == 32
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


def test_all_twelve_initial_requests_keep_full_legal_space_and_exact_profile_prompts(prepared_plan):
    control, requests = plan.wiring_controls(
        prepared_plan["panel"], prepared_plan["condition"], prepared_plan["registrations"]
    )
    assert control["all_expected_outcomes"] and len(requests) == len(control["rows"]) == 12
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
    from trusted_synthesis.experiments.finance_qa_vnext_cross_binding import stage

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
            "cross_binding_report",
            statuses=dict(Counter(item["status"] for item in values)),
            registered_session_count=len(values),
            synthetic_scheduling_control=True,
        )

    monkeypatch.setattr(runner, "analyze_new", analyze)
    return launched, active


@pytest.mark.parametrize("behavior", ["success", "known_failure", "unknown"])
def test_frozen_six_worker_waves_failure_nonreplacement_and_unknown_denominator(
    tmp_path, monkeypatch, prepared_plan, behavior
):
    launched, active = install_scheduling_controls(tmp_path, monkeypatch, prepared_plan, behavior)
    report = runner.run(ROOT, tmp_path)
    assert report["registered_session_count"] == 12
    assert active["maximum"] <= 6
    schedule = read_json((tmp_path / "execution/schedule.json").read_bytes())
    assert [event["label"] for event in schedule["events"]] == list(plan.LABELS)
    if behavior == "success":
        assert report["statuses"] == {"success": 12} and active["maximum"] == 6
        assert set(launched[:6]) == set(prepared_plan["condition"]["waves"][0])
        assert set(launched[6:]) == set(prepared_plan["condition"]["waves"][1])
    elif behavior == "known_failure":
        assert report["statuses"] == {"success": 11, "known_failure": 1}
        assert len(launched) == len(set(launched)) == 12 and schedule["halt_reason"] is None
    else:
        assert report["statuses"] == {"success": 5, "unknown": 1, "not_started": 6}
        assert set(launched) == set(prepared_plan["condition"]["waves"][0])
        assert all(event["status"] == "not_started" for event in schedule["events"][6:])
    with pytest.raises(ProtocolError, match="population_already_started"):
        runner.run(ROOT, tmp_path)


def test_attempt_metrics_preserve_unknown_instead_of_fabricating_total_zero():
    measured = runner._transport_report([{"attempts": 32}, {"attempts": None}], [])
    assert measured["provider_attempt_count"] is None
    assert measured["known_attempt_count_lower_bound"] == 32
    assert measured["reserved_allowance_used"] is None
    assert measured["usage"]["total_tokens"]["observed_total"] is None
    assert measured["maximum_registered_attempts"] == 384
    with pytest.raises(ProtocolError, match="session_attempt_bound"):
        runner._transport_report([{"attempts": 33}], [])
    with pytest.raises(ProtocolError, match="total_attempt_bound"):
        runner._transport_report([{"attempts": 32}] * 13, [])


def test_actual_worker_six_new_source_sessions_with_constructed_http_only(
    tmp_path, monkeypatch, prepared_plan
):
    """Real transport/Runtime/qualifier wiring; HTTP content is fixture-generated, not a model."""
    registrations = prepared_plan["registrations"][:6]
    by_session = {row["session_id"]: row for row in registrations}
    observed, lock = [], threading.Lock()

    def send(sender, http, *, api_key):
        assert api_key == "constructed-http-unit-key-not-a-provider-credential"
        registration = by_session[http["session_id"]]
        public = read_json(http["messages"][1]["content"].encode())
        profile = registration["profile"]
        assert public["context"]["id"] == registration["context_id"]
        assert public["context"]["task_id"] == registration["task_id"]
        assert (
            http["messages"][0]["content"]
            == prepared_plan["condition"]["profiles"][profile]["system_prompt"]
        )
        callback = PublicFixtureCallback(
            support_preference="disclosed_total" if profile == "N" else "reconstructed_total"
        )
        content = callback.generate(public)
        with lock:
            observed.append(
                {
                    "label": registration["label"],
                    "task_id": registration["task_id"],
                    "profile": profile,
                    "body_byte_count": http["body_byte_count"],
                }
            )
        return HTTPResponse(
            200,
            canonical_json_bytes(
                {
                    "id": (
                        f"constructed-cross-binding-never-provider-{registration['label']}-"
                        f"{http['attempt_index']}"
                    ),
                    "object": "chat.completion",
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": content.decode()},
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 10,
                        "total_tokens": 110,
                        "completion_tokens_details": {"reasoning_tokens": 0},
                    },
                }
            ),
        )

    monkeypatch.setattr(HttpxSender, "send", send)
    futures = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        for registration in registrations:
            child = DurableStore(tmp_path / registration["label"])
            child.json("registration.json", registration)
            start = runner.online_runner._session_start(
                registration, started=True, reason="constructed_http_integration_not_model_evidence"
            )
            child.json("start.json", start)
            futures.append(
                (
                    registration,
                    executor.submit(
                        runner.online_runner._run_session,
                        prepared_plan["panel"],
                        prepared_plan["configurations"][registration["profile"]],
                        registration,
                        child,
                        start,
                        "constructed-http-unit-key-not-a-provider-credential",
                    ),
                )
            )
        results = [(registration, future.result()) for registration, future in futures]
    assert len(results) == 6 and len(observed) == 36
    assert len({row["task_id"] for row in observed}) == 3
    assert max(row["body_byte_count"] for row in observed) <= 98304
    for registration, result in results:
        assert result["status"] == "success" and result["qualified"] is True, result.get("errors")
        assert result["evidence_complete"] is result["model_origin_verified"] is True
        assert result["task_id"] == registration["task_id"]
        assert result["context_id"] == registration["context_id"]
        assert result["registry_hash"] == registration["registry_hash"]
        assert result["model_configuration_id"] == registration["model_configuration_id"]
        assert result["provider_attempt_count"] == (5 if registration["profile"] == "N" else 7)
        assert result["runtime_submission_count"] == result["provider_attempt_count"]
        assert (tmp_path / registration["label"] / "transport/manifest.json").is_file()
        assert (tmp_path / registration["label"] / "runtime/session.json").is_file()


def test_full_twelve_worker_export_and_analysis_constructed_http_only(
    tmp_path, monkeypatch, source_inputs, prepared_plan
):
    """All twelve real worker/analysis paths, with only new in-memory tokenizer assets.

    The character codec tests interface wiring, not production tokenizer lengths
    or training feasibility. Its not-fit records must not invalidate QA/classes.
    """
    from test_qa_vnext_cross_binding_representation import CharacterTokenizer

    from trusted_synthesis.experiments.finance_qa_vnext_cross_binding import (
        measurement,
        representation,
    )

    binding = {
        "id": "constructed-full-twelve-in-memory-tokenizer-reference",
        "maximum_sequence_length": 24576,
        "chat_template": CharacterTokenizer.chat_template,
        "chat_template_sha256": "constructed-character-codec-template-hash",
        "software_versions": {"test": "in-memory-codec-not-production-assets"},
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
        adapters,
        source_records,
        implementation,
        policy,
        rule,
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
    by_session = {registration["session_id"]: registration for registration in registrations}
    observed, lock = [], threading.Lock()

    def send(sender, http, *, api_key):
        assert api_key == "full-twelve-constructed-http-never-provider"
        registration = by_session[http["session_id"]]
        public = read_json(http["messages"][1]["content"].encode())
        profile = registration["profile"]
        assert public["context"]["id"] == registration["context_id"]
        assert http["messages"][0]["content"] == condition["profiles"][profile]["system_prompt"]
        raw = PublicFixtureCallback(
            support_preference="disclosed_total" if profile == "N" else "reconstructed_total"
        ).generate(public)
        with lock:
            observed.append(registration["label"])
        return HTTPResponse(
            200,
            canonical_json_bytes(
                {
                    "id": f"constructed-full12-{registration['label']}-{http['attempt_index']}",
                    "object": "chat.completion",
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": raw.decode()},
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 10,
                        "total_tokens": 110,
                        "completion_tokens_details": {"reasoning_tokens": 0},
                    },
                }
            ),
        )

    monkeypatch.setattr(HttpxSender, "send", send)
    execution = tmp_path / "execution"
    store = DurableStore(execution)
    store.json("registrations.json", registrations)
    qualifications = []
    for wave in (1, 2):
        futures = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            for registration in (row for row in registrations if row["wave"] == wave):
                child = DurableStore(execution / "sessions" / registration["label"])
                child.json("registration.json", registration)
                start = runner.online_runner._session_start(
                    registration,
                    started=True,
                    reason="full_population_constructed_http_control",
                )
                child.json("start.json", start)
                futures.append(
                    executor.submit(
                        runner.online_runner._run_session,
                        panel,
                        preparation["configurations"][registration["profile"]],
                        registration,
                        child,
                        start,
                        "full-twelve-constructed-http-never-provider",
                    )
                )
            qualifications.extend(future.result() for future in futures)
    assert len(qualifications) == 12 and all(value["qualified"] is True for value in qualifications)
    assert len(observed) == 72 and len(set(observed)) == 12
    store.json("qualifications.json", qualifications)
    # Only fixture source/history verification is substituted; all analysis producers are real.
    monkeypatch.setattr(runner, "verify_source_snapshot", lambda root, snapshot: None)
    monkeypatch.setattr(runner, "history_inventory", lambda root: preparation["history_inventory"])
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(runner.online_runner, "_run_session", forbidden)
    monkeypatch.setattr(runner, "qualify_session", forbidden)
    report = runner.analyze_new(ROOT, preparation, execution)
    measured = report["measurement"]
    assert report["candidate_count"] == 72 and report["provider_attempt_count"] == 72
    assert report["status_counts"] == {"success": 12}
    assert measured["qualified_count"] == measured["assigned_qualified_count"] == 12
    assert measured["pair_count"] == 18 and measured["cross_task_state_comparisons"] == 0
    assert measured["tasks_with_DR_witness"] == 3
    assert measured["panel_success_fraction"] == {"numerator": 12, "denominator": 12}
    assert len(measured["classes"]) == 6 and len(measured["task_rows"]) == 3
    assert all(
        row["W_support"] and row["complete_class_count"] == 2 for row in measured["task_rows"]
    )
    assert all(
        member["package_id"] is not None
        and type(member["target_token_count"]) is int
        and member["target_token_count"] > 0
        for ref in measured["classes"]
        for member in ref["member_representation_references"]
    )
    assert len(tokenizer_loads) == 1
    assert report["token_fit_count"] + report["token_not_fit_count"] == 72
    assert report["execution_guards"]["all_zero"] is True
    sizes = [
        (path.relative_to(execution).as_posix(), path.stat().st_size)
        for path in (execution / "analysis").rglob("*")
        if path.is_file()
    ]
    largest = max(sizes, key=lambda item: item[1])
    print(
        "FULL12_CONSTRUCTED_ANALYSIS_FILE_SIZES",
        {
            "largest_file": largest[0],
            "largest_bytes": largest[1],
            "report_bytes": (execution / "analysis/report.json").stat().st_size,
            "measurement_bytes": (execution / "analysis/measurement.json").stat().st_size,
            "projections_bytes": (execution / "analysis/projections.json").stat().st_size,
            "production_tokenizer_used": False,
        },
    )
