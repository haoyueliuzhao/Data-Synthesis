"""Synthetic boundary tests; no live API calls or production task selection."""

import json
import socket
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import get_context

import pytest
from finraw.llm_client import LLMClientError, OpenAICompatibleJsonClient

from trusted_synthesis.experiments.finance_qa_vnext_surface_build.budget import (
    INPUT_RESERVATION,
    OUTPUT_CAP,
    BudgetRejected,
    Ledger,
)
from trusted_synthesis.experiments.finance_qa_vnext_surface_build.guards import rewrite_guard
from trusted_synthesis.experiments.finance_qa_vnext_surface_build.protocol import qa_config
from trusted_synthesis.experiments.finance_qa_vnext_surface_build.transport import (
    MODEL,
    Provider,
    credential,
)


def test_registered_project_credential_path_not_repository_root(tmp_path):
    directory = tmp_path / "trusted_data_synthesis"
    directory.mkdir()
    (directory / ".env").write_text("UNRELATED=ignored\nDEEPSEEK_API_KEY='SYNTHETIC_KEY'\n")
    assert credential(tmp_path) == "SYNTHETIC_KEY"
    assert not (tmp_path / ".env").exists()


@pytest.mark.parametrize("state", ["empty", "reserved", "native", "resumed"])
def test_environment_continuation_cannot_replay_any_production_work(tmp_path, state):
    from trusted_synthesis.experiments.finance_qa_vnext_surface_build.sources import OUTPUT, WORK
    from trusted_synthesis.experiments.finance_qa_vnext_surface_build.stage import (
        require_pristine_pre_model,
    )

    output = tmp_path / OUTPUT
    output.mkdir(parents=True)
    ledger = Ledger(tmp_path / WORK / "budget.sqlite", "fixture")
    if state == "reserved":
        ledger.reserve("task")
    elif state == "native":
        (tmp_path / WORK / "native_fact_qa.sqlite3").touch()
    elif state == "resumed":
        (output / "run_resumed.json").touch()
    if state == "empty":
        assert require_pristine_pre_model(tmp_path, output, ledger)["request_reservations"] == 0
    else:
        with pytest.raises(ValueError):
            require_pristine_pre_model(tmp_path, output, ledger)


def process_reserve(args):
    path, task = args
    try:
        return Ledger(path, "fixture", request_cap=5).reserve(task)["request_id"]
    except BudgetRejected:
        return None


def test_atomic_thread_cap_and_no_replay(tmp_path):
    ledger = Ledger(tmp_path / "budget.sqlite", "fixture", request_cap=9)

    def attempt(index):
        try:
            return ledger.reserve(str(index))
        except BudgetRejected:
            return None

    with ThreadPoolExecutor(max_workers=16) as pool:
        rows = list(pool.map(attempt, range(40)))
    assert sum(row is not None for row in rows) == 9
    assert ledger.snapshot()["conservative_charged_tokens"] == 9 * (INPUT_RESERVATION + OUTPUT_CAP)
    row = next(row for row in rows if row)
    ledger.mark_sent(row["request_id"])
    with pytest.raises(BudgetRejected, match="only_once"):
        ledger.mark_sent(row["request_id"])
    with pytest.raises(BudgetRejected):
        ledger.reserve(row["task_id"], repair=True)


def test_atomic_process_cap_survives_reopening(tmp_path):
    path = str(tmp_path / "budget.sqlite")
    Ledger(path, "fixture", request_cap=5)
    with ProcessPoolExecutor(max_workers=4, mp_context=get_context("spawn")) as pool:
        rows = list(pool.map(process_reserve, [(path, str(i)) for i in range(24)]))
    assert len({row for row in rows if row}) == 5
    assert Ledger(path, "fixture", request_cap=5).snapshot()["request_reservations"] == 5


@pytest.mark.parametrize("outcome", ["no_returned_text", "TimeoutError", "ValueError"])
def test_http_success_alone_does_not_authorize_repair(tmp_path, outcome):
    ledger = Ledger(tmp_path / "budget.sqlite", "fixture")
    row = ledger.reserve("task")
    ledger.mark_sent(row["request_id"])
    ledger.settle(
        row["request_id"],
        usage={"prompt_tokens": 10, "completion_tokens": 20},
        http_success=True,
        outcome=outcome,
    )
    with pytest.raises(BudgetRejected, match="returned_contract"):
        ledger.reserve("task", repair=True)


def test_one_contract_repair_and_no_transferred_attempts(tmp_path):
    ledger = Ledger(tmp_path / "budget.sqlite", "fixture")
    for repair in (False, True):
        row = ledger.reserve("task", repair=repair)
        ledger.mark_sent(row["request_id"])
        ledger.settle(
            row["request_id"],
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            http_success=True,
            outcome="response_received",
        )
    with pytest.raises(BudgetRejected):
        ledger.reserve("task", repair=True)
    assert ledger.snapshot()["conservative_charged_tokens"] == 60


@pytest.mark.parametrize("usage", [None, [], {}, {"prompt_tokens": True, "completion_tokens": 20}])
def test_unknown_usage_is_not_zero_or_reclaimable(tmp_path, usage):
    ledger = Ledger(tmp_path / "budget.sqlite", "fixture")
    row = ledger.reserve("task")
    ledger.mark_sent(row["request_id"])
    assert not ledger.settle(row["request_id"], usage=usage, outcome="response_received")
    assert ledger.snapshot()["conservative_charged_tokens"] == INPUT_RESERVATION + OUTPUT_CAP
    with pytest.raises(BudgetRejected):
        ledger.reserve("task", repair=True)


@pytest.mark.parametrize("prompt,completion", [(INPUT_RESERVATION + 1, 1), (1, OUTPUT_CAP + 1)])
def test_usage_overrun_charges_actual_and_closes_global_budget(tmp_path, prompt, completion):
    ledger = Ledger(tmp_path / "budget.sqlite", "fixture")
    row = ledger.reserve("task")
    ledger.mark_sent(row["request_id"])
    assert not ledger.settle(
        row["request_id"],
        usage={"prompt_tokens": prompt, "completion_tokens": completion},
        http_success=True,
        outcome="response_received",
    )
    assert ledger.snapshot()["conservative_charged_tokens"] == prompt + completion
    assert ledger.snapshot()["budget_breach_count"] == 1
    with pytest.raises(BudgetRejected, match="exceeded_reservation"):
        ledger.reserve("another-task")


def test_global_token_reservation_and_policy_identity(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = Ledger(path, "fixture", token_cap=INPUT_RESERVATION + OUTPUT_CAP)
    ledger.reserve("task")
    with pytest.raises(BudgetRejected, match="global_request_or_token_cap"):
        ledger.reserve("another")
    with pytest.raises(BudgetRejected, match="policy_identity"):
        Ledger(path, "different")


def request():
    return {
        "generation_strategy": "protected_rewrite",
        "variant_count": 2,
        "protected_question": "What changed in [[metric]]?",
        "required_placeholders": ["[[metric]]"],
    }


def envelope(payload, model=MODEL, usage=None):
    return json.dumps(
        {
            "model": model,
            "choices": [{"message": {"content": json.dumps(payload)}}],
            "usage": usage or {"prompt_tokens": 10, "completion_tokens": 20},
        }
    ).encode()


def test_real_provider_closed_fields_identity_and_persistent_receipts(tmp_path):
    bodies = []

    def sender(body, key):
        bodies.append(body)
        assert key == "SECRET_TEST_KEY"
        return envelope({"rewrites": [{"question_template": "SECRET_TEST_KEY"}]})

    ledger = Ledger(tmp_path / "budget.sqlite", "fixture")
    provider = Provider("task", ledger, tmp_path, "SECRET_TEST_KEY", sender=sender)
    result = provider.generate(request())
    assert result == [{"question_template": "[REDACTED_CREDENTIAL]"}]
    assert len(bodies) == 1
    assert set(bodies[0]) == {
        "model",
        "messages",
        "thinking",
        "response_format",
        "max_tokens",
        "stream",
    }
    assert bodies[0]["model"] == MODEL and bodies[0]["thinking"] == {"type": "disabled"}
    assert (
        provider.last_telemetry["request_count"]
        == provider.last_telemetry["http_success_count"]
        == 1
    )
    assert ledger.snapshot()["conservative_charged_tokens"] == 30
    assert all("SECRET_TEST_KEY" not in path.read_text() for path in tmp_path.rglob("*.json"))


def test_transport_failure_does_not_retry(tmp_path):
    count = []

    def sender(body, key):
        count.append(1)
        raise TimeoutError("synthetic transport failure")

    ledger = Ledger(tmp_path / "budget.sqlite", "fixture")
    provider = Provider("task", ledger, tmp_path, "SECRET_TEST_KEY", sender=sender)
    with pytest.raises(LLMClientError):
        provider.generate(request())
    assert count == [1]
    assert ledger.snapshot()["sent_request_count"] == 1
    assert ledger.snapshot()["http_success_count"] == 0
    assert ledger.snapshot()["unsettled_or_unknown_count"] == 1


def test_response_model_mismatch_is_charged_without_fallback(tmp_path):
    ledger = Ledger(tmp_path / "budget.sqlite", "fixture")
    provider = Provider(
        "task",
        ledger,
        tmp_path,
        "SECRET_TEST_KEY",
        sender=lambda *_: envelope({"rewrites": [{}]}, model="unexpected-model"),
    )
    with pytest.raises(LLMClientError):
        provider.generate(request())
    assert ledger.snapshot()["known_prompt_tokens"] == 10
    assert ledger.snapshot()["http_success_count"] == 1
    assert ledger.snapshot()["request_reservations"] == 1
    assert next(tmp_path.rglob("failure.json")).exists()


@pytest.mark.parametrize(
    "payload", [{"rewrites": []}, {"rewrites": [{}, {}, {}]}, [], {"wrong": True}]
)
def test_invalid_structure_is_one_returned_contract_failure(tmp_path, payload):
    ledger = Ledger(tmp_path / "budget.sqlite", "fixture")
    provider = Provider(
        "task", ledger, tmp_path, "SECRET_TEST_KEY", sender=lambda *_: envelope(payload)
    )
    assert provider.generate(request()) == [{"invalid_response_schema": True}]
    assert ledger.snapshot()["reservations"][0]["outcome"] == "rewrite_structure_failure"
    assert ledger.reserve("task", repair=True)["attempt"] == 2


def test_empty_text_is_not_a_repair(tmp_path):
    ledger = Ledger(tmp_path / "budget.sqlite", "fixture")
    response = json.loads(envelope({}))
    response["choices"][0]["message"]["content"] = ""
    provider = Provider(
        "task", ledger, tmp_path, "SECRET_TEST_KEY", sender=lambda *_: json.dumps(response).encode()
    )
    assert provider.generate(request()) == []
    with pytest.raises(BudgetRejected):
        ledger.reserve("task", repair=True)


def test_scoped_guard_blocks_generic_models_and_unregistered_network():
    with rewrite_guard() as counters:
        with pytest.raises(RuntimeError, match="unregistered_network"):
            socket.create_connection(("example.invalid", 443))
        with pytest.raises(RuntimeError, match="generic_model"):
            OpenAICompatibleJsonClient.complete_json(None)
    assert counters["forbidden"]["socket_create_connection"] == 1
    assert counters["forbidden"]["generic_LLM_client"] == 1


def test_frozen_realization_config_has_no_generic_enable_shortcut():
    config = qa_config()["qa"]
    generation = config["question_generation"]
    assert generation["mode"] == "controlled_llm" and generation["strategy"] == "protected_rewrite"
    assert generation["variants"] == generation["max_attempts"] == 2
    assert generation["variant_order"] == "response_order"
    assert generation["surface_variation"] == {"enabled": False, "llm_selects_variants": False}
    assert generation["api_quality_gate"]["observational_only"]
