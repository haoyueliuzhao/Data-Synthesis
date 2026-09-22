"""Fake-model recovery tests; never import torch, load a model or open confirm text."""

import ast
import copy
import gzip
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/fixed_kernel_B_generation_20260922.py"


def pure_protocol():
    # Execute the actual record helpers without importing the experiment's
    # pyarrow/model dependency graph. This is code-only, never experiment data.
    path = (
        Path(__file__).parents[1]
        / "src/trusted_synthesis/experiments/finance_qa_vnext_fixed_kernel_value/protocol.py"
    )
    names = {"require", "encode", "sha", "record", "checked", "read_json", "write_once"}
    tree = ast.parse(path.read_text())
    tree.body = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = dict(copy=copy, hashlib=hashlib, json=json, os=os, Path=Path)
    exec(compile(tree, str(path), "exec"), namespace)
    return SimpleNamespace(**{name: namespace[name] for name in names})


p = pure_protocol()


class FakeOOM(Exception):
    pass


@pytest.fixture
def worker(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    state = SimpleNamespace(
        calls=[],
        loads=[],
        reserves=[],
        writes=[],
        commits={},
        events=[],
        reads=[],
        capacity=[],
        fail_indices=set(),
        call_counts={},
        fail_commit_once=False,
    )

    def write(path, value, *, immutable=True):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = p.encode(value)
        if path.exists() and immutable:
            p.require(path.read_bytes() == payload, "fake.immutable_conflict")
        else:
            path.write_bytes(payload)
        state.writes.append((path, copy.deepcopy(value)))
        return value

    def reserve(kind, key, attempt, unit):
        value = kind, key, attempt, unit
        assert value not in state.reserves
        state.reserves.append(value)

    def committed(point_id, index, record):
        if state.fail_commit_once:
            state.fail_commit_once = False
            raise RuntimeError("synthetic crash after completed JSON commit")
        key = point_id, index
        assert state.commits.get(key, record) == record
        state.commits[key] = record

    class FakeModel:
        current = None

        def named_parameters(self):
            return [("test.lora_A", object()), ("test.lora_B", object())]

        def generate(self, **kwargs):
            # Both the reservation and persisted intent precede the physical call.
            meter = next(
                value for _, value in reversed(state.writes) if "generate_call_intents" in value
            )
            assert meter["index"] == self.current
            assert meter["generate_call_intents"] == meter["generate_calls_returned"] + 1
            assert state.reserves[-1][-1] == f"{self.current}_{meter['generate_call_intents']}"
            assert kwargs == {"max_new_tokens": 2048}
            state.calls.append(self.current)
            if self.current in state.fail_indices:
                state.fail_indices.remove(self.current)
                raise FakeOOM("synthetic GPU capacity failure")
            return [2]

    model = FakeModel()
    state.model = model

    def load_model(base, seed, *, trainable, adapter_path, adapter_record):
        assert trainable is False
        assert adapter_path == raw / "point/adapter.safetensors"
        state.loads.append((base, seed, adapter_record))
        return model, None

    def read_session(root, item):
        state.reads.append(item["job"]["index"])
        data = (Path(root) / item["path"]).read_bytes()
        p.require(
            len(data) == item["bytes"] and p.sha(data) == item["sha256"], "fake.session_bytes"
        )
        session = json.loads(gzip.decompress(data))
        p.require(session["id"] == item["session_id"], "fake.session_id")
        return session

    def validate_receipts(session, item, point_id, stochastic):
        p.require(item["point_id"] == point_id, "fake.point")
        p.require(len(session["turns"]) == item["actual_generate_calls"], "fake.call_count")
        for turn in session["turns"]:
            receipt = p.checked(turn["provider_receipt"], "anchored_actual_callback")
            p.require(
                receipt["point_id"] == point_id
                and receipt["identity"] == session["identity"]
                and receipt["stochastic"] is stochastic,
                "fake.receipt_binding",
            )

    def generate_jobs(*, root, directory, jobs, point, assets, model, tokenizer, stochastic):
        assert len(jobs) == 1
        assert root == raw
        assert tokenizer == "synthetic-tokenizer"
        assert assets == state.plan["materials"]["assets"]
        unit = jobs[0]
        model.current = unit["index"]
        identity = dict(
            task_id=unit["task"]["task_id"],
            family=unit["task"]["group"],
            surface_version_id=unit["task"]["surface_version_id"],
            public_messages_sha256=unit["task"]["public_messages_sha256"],
            parent_manifest_id=point["source_manifest_id"],
        )
        turns = []
        path = directory / "sessions" / f"{unit['index']:04d}.json.gz"
        for response_index in range(state.call_counts.get(unit["index"], 1)):
            try:
                tokens = model.generate(max_new_tokens=2048)
            except FakeOOM as error:
                # Simulate an interrupted RAW session plus the old decoder's
                # conversion of the model exception into a provider ValueError.
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic incomplete gzip")
                raise ValueError("feedback.decoder_fault_not_zero_reward:FakeOOM") from error
            receipt = p.record(
                "anchored_actual_callback",
                identity=identity,
                point_id=point["id"],
                response_index=response_index,
                virtual_or_final_parameter_digest=point["parameter_digest"],
                stochastic=stochastic,
                original_greedy_backend=not stochastic,
                generated_token_ids=tokens,
                prompt_input_ids=[1],
            )
            turns.append(dict(response_index=response_index, provider_receipt=receipt))
        session = p.record("synthetic_session", identity=identity, turns=turns, terminal="done")
        data = gzip.compress(p.encode(session), mtime=0)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        item = p.record(
            "anchored_generated_trajectory",
            job=unit,
            point_id=point["id"],
            path=str(path.relative_to(root)),
            bytes=len(data),
            sha256=p.sha(data),
            session_id=session["id"],
            actual_generate_calls=len(turns),
            generated_tokens=len(turns),
            legal_context_rejection=False,
            elapsed_seconds=0,
            private_assessment_performed=False,
        )
        p.write_once(directory / "completed" / f"{unit['index']:04d}.json", item)
        return [item]

    old = SimpleNamespace(
        views=SimpleNamespace(binding=lambda: {"id": "runtime:synthetic"}),
        trajectory_training=SimpleNamespace(load_registered_student=load_model),
        components=SimpleNamespace(adapter_digest=lambda model: "adapter-digest"),
        gate=SimpleNamespace(tensor_digest=lambda values: "tensor-digest"),
        load_tokenizer=lambda binding: "synthetic-tokenizer",
        feedback=SimpleNamespace(
            generate_jobs=generate_jobs,
            read_session=read_session,
            validate_receipts=validate_receipts,
            torch=SimpleNamespace(OutOfMemoryError=FakeOOM),
        ),
    )
    common = SimpleNamespace(
        RAW=raw,
        p=p,
        old=old,
        write=write,
        reserve=reserve,
        generation_committed=committed,
        emit=state.events.append,
        read_protocol=lambda root: state.plan,
        capacity_boundary=lambda phase, required: state.capacity.append((phase, required)),
    )
    monkeypatch.setitem(sys.modules, "fixed_kernel_B_common_20260922", common)
    spec = importlib.util.spec_from_file_location("synthetic_B_generation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state.module, state.common = module, common
    state.plan = p.record(
        "B_confirm_protocol",
        materials=dict(
            assets=dict(base_binding={"id": "base:synthetic"}, tokenizer_binding={"id": "tok"}),
            runtime_binding={"id": "runtime:synthetic"},
        ),
    )
    state.point = p.record(
        "anchored_model_parameter_point",
        source_manifest_id="source:synthetic",
        base_binding_id="base:synthetic",
        adapter_directory="point",
        adapter=dict(path="adapter.safetensors", parameter_digest="adapter-digest"),
        parameter_digest="tensor-digest",
    )
    write(raw / "point/point.json", state.point)

    def job(*, phase="feedback", indices=(0, 1), key="synthetic_shard"):
        count = 360 if phase == "feedback" else 720
        jobs = []
        for index in range(count):
            task_index = index // 2 if phase == "feedback" else index
            task = dict(
                task_id=f"synthetic-task-{task_index}",
                group="composition_required",
                path=str(raw / "never-open-public-text" / f"{task_index}.json"),
                surface_version_id=f"synthetic-surface:{task_index}",
                public_messages_sha256=f"synthetic-public-digest:{task_index}",
            )
            jobs.append(
                dict(
                    index=index,
                    task=task,
                    repeat=index % 2 + 1 if phase == "feedback" else 0,
                    seed=100 + index,
                )
            )
        directory = raw / phase
        registration = p.record(
            "B_generation_registration",
            protocol_id=state.plan["id"],
            point_id=state.point["id"],
            source_manifest_id="source:synthetic",
            seed=11,
            condition="delayed_c",
            stochastic=phase == "feedback",
            jobs=jobs,
        )
        write(directory / "registration.json", registration)
        return dict(
            key=key,
            phase=phase,
            seed=11,
            condition="delayed_c",
            point_path=str(raw / "point/point.json"),
            directory=str(directory),
            source_manifest_id="source:synthetic",
            jobs=[jobs[index] for index in indices],
            registration_path=str(directory / "registration.json"),
        )

    state.job = job
    return state


@pytest.mark.parametrize("phase", ["feedback", "confirm"])
def test_complete_shard_reuses_commits_without_loading_or_regenerating(worker, phase):
    job = worker.job(phase=phase)
    original_generate, original_write = worker.model.generate, p.write_once
    report = worker.module.run(worker.common.RAW, job, 1)
    assert report["status"] == "COMPLETE"
    assert report["trajectory_count"] == report["total_generate_calls"] == 2
    assert report["stochastic"] is (phase == "feedback")
    assert worker.calls == [0, 1]
    assert len(worker.loads) == 1
    assert worker.capacity == [("generation", 57344)] * 2
    assert worker.model.generate == original_generate
    assert p.write_once is original_write
    assert worker.module.run(worker.common.RAW, job, 2) == report
    assert worker.calls == [0, 1]
    assert len(worker.loads) == 1
    assert len(worker.commits) == 2
    assert not (Path(job["directory"]) / "attempts/synthetic_shard_attempt0002").exists()
    meters = list(Path(job["directory"]).glob("attempts/*/meters/*.json"))
    assert all(p.read_json(path)["status"] == "COMMITTED" for path in meters)


def test_oom_preserves_original_type_and_incomplete_bytes_and_resumes_only_missing(worker):
    job = worker.job()
    worker.fail_indices.add(1)
    original_generate = worker.model.generate
    with pytest.raises(FakeOOM) as failure:
        worker.module.run(worker.common.RAW, job, 1)
    assert isinstance(failure.value.__cause__, ValueError)
    attempt = Path(job["directory"]) / "attempts/synthetic_shard_attempt0001"
    partial = attempt / "sessions/0001.json.gz"
    assert partial.read_bytes() == b"synthetic incomplete gzip"
    meter = p.read_json(attempt / "meters/0001.json")
    assert (meter["generate_call_intents"], meter["generate_calls_returned"]) == (1, 0)
    assert meter["status"] == "INTERRUPTED"
    assert meter["exception_type"] == "FakeOOM"
    assert worker.model.generate == original_generate
    report = worker.module.run(worker.common.RAW, job, 2)
    assert worker.calls == [0, 1, 1]
    assert report["total_generate_calls"] == 2
    assert len(worker.reserves) == 3
    assert partial.read_bytes() == b"synthetic incomplete gzip"
    assert "attempt0001" in report["trajectories"][0]["path"]
    assert "attempt0002" in report["trajectories"][1]["path"]


def test_completed_json_before_accounting_crash_is_reconciled_without_repeat(worker):
    job = worker.job(indices=(0,))
    worker.fail_commit_once = True
    with pytest.raises(RuntimeError, match="after completed JSON"):
        worker.module.run(worker.common.RAW, job, 1)
    report = worker.module.run(worker.common.RAW, job, 2)
    assert worker.calls == [0]
    assert len(worker.loads) == len(worker.commits) == 1
    assert report["total_generate_calls"] == 1


def test_changed_shard_task_is_rejected_before_loading(worker):
    job = worker.job(indices=(0,))
    job["jobs"][0]["task"]["task_id"] = "unregistered-task"
    with pytest.raises(ValueError, match="exact_preregistered_shard"):
        worker.module.run(worker.common.RAW, job, 1)
    assert worker.loads == worker.calls == []


@pytest.mark.parametrize(
    "tamper", ["point", "task", "bytes", "parameter_receipt", "source_identity"]
)
def test_committed_session_tampering_is_never_reused(worker, tamper):
    job = worker.job(indices=(0,))
    report = worker.module.run(worker.common.RAW, job, 1)
    item = report["trajectories"][0]
    session_path = worker.common.RAW / item["path"]
    record_path = session_path.parent.parent / "completed/0000.json"
    if tamper == "bytes":
        session_path.write_bytes(b"bad-gzip")
    else:
        body = {key: value for key, value in item.items() if key not in ("id", "schema_version")}
        if tamper == "point":
            body["point_id"] = "another-point"
        elif tamper == "task":
            body["job"] = copy.deepcopy(body["job"])
            body["job"]["task"]["task_id"] = "another-task"
        else:
            session = json.loads(gzip.decompress(session_path.read_bytes()))
            receipt = session["turns"][0]["provider_receipt"]
            receipt_body = {
                key: value for key, value in receipt.items() if key not in ("id", "schema_version")
            }
            if tamper == "parameter_receipt":
                receipt_body["virtual_or_final_parameter_digest"] = "wrong-parameters"
            else:
                session["identity"]["parent_manifest_id"] = "wrong-source"
                receipt_body["identity"] = session["identity"]
            session["turns"][0]["provider_receipt"] = p.record(
                "anchored_actual_callback", **receipt_body
            )
            session = p.record(
                "synthetic_session",
                **{
                    key: value
                    for key, value in session.items()
                    if key not in ("id", "schema_version")
                },
            )
            data = gzip.compress(p.encode(session), mtime=0)
            session_path.write_bytes(data)
            body.update(bytes=len(data), sha256=p.sha(data), session_id=session["id"])
        worker.common.write(
            record_path, p.record("anchored_generated_trajectory", **body), immutable=False
        )
    with pytest.raises(ValueError):
        worker.module.run(worker.common.RAW, job, 2)
    assert worker.calls == [0]


def test_other_shard_metadata_is_checked_without_decompressing_its_sessions(worker):
    first = worker.job(indices=(0,), key="first")
    worker.module.run(worker.common.RAW, first, 1)
    worker.reads.clear()
    second = worker.job(indices=(1,), key="second")
    worker.module.run(worker.common.RAW, second, 1)
    assert worker.reads == [1]
    assert worker.calls == [0, 1]


def test_one_shard_cannot_select_duplicate_committed_records(worker):
    job = worker.job(indices=(0,))
    report = worker.module.run(worker.common.RAW, job, 1)
    duplicate = Path(job["directory"]) / "attempts/duplicate/completed/0000.json"
    worker.common.write(duplicate, report["trajectories"][0])
    with pytest.raises(ValueError, match="one_committed_record_per_job"):
        worker.module.run(worker.common.RAW, job, 2)
    assert worker.calls == [0]


def test_physical_call_reservations_stop_at_32(worker):
    job = worker.job(indices=(0,))
    worker.call_counts[0] = 33
    with pytest.raises(ValueError, match="at_most_32_calls_per_session"):
        worker.module.run(worker.common.RAW, job, 1)
    assert len(worker.calls) == len(worker.reserves) == 32
    assert not list(Path(job["directory"]).glob("attempts/*/completed/*.json"))


def test_adapter_digest_mismatch_stops_before_generation(worker):
    job = worker.job(indices=(0,))
    worker.common.old.components.adapter_digest = lambda model: "wrong-adapter"
    with pytest.raises(ValueError, match="loaded_exact_adapter_digest"):
        worker.module.run(worker.common.RAW, job, 1)
    assert worker.calls == worker.reserves == []
