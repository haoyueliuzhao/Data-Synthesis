"""Bounded CPU/controller controls: no tokenizer, CUDA, model or API calls."""

from types import SimpleNamespace

import pytest

from trusted_synthesis.finance_research import calibration as c
from trusted_synthesis.finance_research.contracts import ModelIdentity, RunConfig


def test_gate_prompt_length_counts_ids_not_batch_encoding_fields():
    from transformers import BatchEncoding

    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs["tokenize"] is False
            assert kwargs["tools"] and kwargs["add_generation_prompt"] is True
            return "rendered"

        def __call__(self, rendered, **kwargs):
            assert rendered == "rendered"
            assert kwargs == dict(add_special_tokens=False, truncation=False, padding=False)
            return BatchEncoding({"input_ids": [11] * 19, "attention_mask": [1] * 19})

    assert c.gate_prompt_length(Tokenizer(), []) == 19


def test_gate_prompt_length_matches_installed_real_tokenizer():
    from pathlib import Path

    from transformers import AutoTokenizer

    from trusted_synthesis.finance_research.tools import TOOL_SPECS

    directory = Path(
        "/data1/zhuxinrui/models/Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28"
    )
    if not directory.is_dir():
        pytest.skip("local Qwen tokenizer unavailable")
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True)
    messages = [{"role": "user", "content": "List the available financial sources."}]
    actual = tokenizer.apply_chat_template(
        messages, tools=TOOL_SPECS, tokenize=True, return_dict=True, add_generation_prompt=True
    )
    expected = len(actual["input_ids"])
    assert expected > 2
    assert c.gate_prompt_length(tokenizer, messages) == expected


def _plan():
    jobs = []
    for start in range(0, 120, 30):
        for model in ("base", "static11_step240"):
            for harness in ("H0", "H1"):
                config = RunConfig(
                    harness_id=(
                        "fixed-kernel-finqa-compat-v1"
                        if harness == "H0"
                        else "bigfinance-derived-vtdo-v2"
                    ),
                    local_tool_protocol=(
                        "legacy-json-v1" if harness == "H0" else "qwen2.5-native-tool-call-v1"
                    ),
                    submission_profile="finqa_program_v1",
                    role="calibration",
                    temperature=0,
                )
                jobs.append(
                    dict(
                        key=f"{model}_{harness}_{start:03d}",
                        model=model,
                        harness=harness,
                        config=config.model_dump(mode="json"),
                        task_keys=[f"finqa:{i}" for i in range(start, start + 30)],
                    )
                )
    return dict(
        id="fixture-plan", jobs=jobs, initial_leases=[], snapshot="fixture-only", role_plan={}
    )


def test_worker_started_and_outcome_paths_match_parent_latest(tmp_path, monkeypatch):
    plan = _plan()
    c.publish(tmp_path / "gate_complete", {"eval_native_passed": True})
    monkeypatch.setattr(c, "checked_plan", lambda _: plan)
    monkeypatch.setattr(c, "identity", lambda _: "fixture-birth")
    provider = SimpleNamespace(identity=ModelIdentity(backend="scripted", model_id="no-model"))
    monkeypatch.setattr(c, "load_provider", lambda *_: provider)
    prepared = []
    monkeypatch.setattr(c, "prepare_run", lambda *args, **kwargs: prepared.append(kwargs))

    async def execute(root, actual_provider):
        assert actual_provider is provider
        return {"id": "fixture-seal"}

    monkeypatch.setattr(c, "execute_run", execute)
    key = plan["jobs"][0]["key"]
    assert c.worker(tmp_path, key, 1, "GPU-fixture") == 0
    record = c.latest(tmp_path, key)
    assert record["attempt"] == 1 and record["alive"]
    assert record["process"]["gpu"] == "GPU-fixture"
    assert record["outcome"]["generation_seal_id"] == "fixture-seal"
    assert prepared[0]["config"].temperature == 0
    assert len(prepared[0]["task_keys"]) == 30


def test_missing_birth_is_never_live_process(tmp_path, monkeypatch):
    c.publish(
        tmp_path / "jobs/example/attempts/01/launched",
        dict(pid=99999999, process_identity=None, gpu="GPU-fixture"),
    )
    monkeypatch.setattr(c, "identity", lambda _: None)
    assert c.latest(tmp_path, "example")["alive"] is False


@pytest.mark.parametrize("live_worker", [True, False])
def test_private_scores_wait_for_all_480_and_last_worker_exit(tmp_path, monkeypatch, live_worker):
    plan = _plan()
    c.publish(tmp_path / "gate_complete", {"eval_native_passed": True})
    monkeypatch.setattr(c, "checked_plan", lambda _: plan)

    def latest(_, key):
        alive = live_worker and key == plan["jobs"][-1]["key"]
        return dict(
            attempt=1, alive=alive, process={"gpu": "GPU-fixture"}, outcome={"status": "COMPLETE"}
        )

    monkeypatch.setattr(c, "latest", latest)
    monkeypatch.setattr(c, "gpu_inventory", lambda: [])
    monkeypatch.setattr(c, "status", lambda *_: None)
    timeline = []
    monkeypatch.setattr(
        c, "publish", lambda directory, value: timeline.append((directory.name, value))
    )

    def score_run(root, output):
        assert any(name == "generation_seal" for name, _ in timeline)
        timeline.append(("private_score", str(root)))
        return {"denominator": 30}

    monkeypatch.setattr(c, "score_run", score_run)

    class StopLoop(Exception):
        pass

    monkeypatch.setattr(c.time, "sleep", lambda _: (_ for _ in ()).throw(StopLoop()))
    if live_worker:
        with pytest.raises(StopLoop):
            c.coordinate(tmp_path)
        assert timeline == []
    else:
        c.coordinate(tmp_path)
        assert timeline[0][0] == "generation_seal"
        assert timeline[0][1]["denominator"] == 480
        assert timeline[0][1]["all_workers_exited"] is True
        assert sum(name == "private_score" for name, _ in timeline) == 16
        assert timeline[-1][0] == "complete"


def test_holder_handoff_never_signals_pid_with_wrong_birth(tmp_path, monkeypatch):
    plan = dict(initial_leases=[dict(gpu="GPU-fixture", pid=12345, process_identity="old")])
    monkeypatch.setattr(c, "identity", lambda _: "new-birth")
    monkeypatch.setattr(c.os, "kill", lambda *_: pytest.fail("must not signal reused PID"))
    c.release_owned_holder("GPU-fixture", plan)
