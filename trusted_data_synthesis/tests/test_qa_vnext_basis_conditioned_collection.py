"""New collection boundaries: local scripted workers and mocked collectors, no live models."""

import copy
import os
import subprocess
from collections import Counter
from concurrent.futures import Future
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support import collect as c
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.core import Store
from trusted_synthesis.experiments.finance_qa_vnext_basis_conditioned_support.plan import (
    BASIS_INSTRUCTIONS,
    COMMON_SYSTEM,
    DOCUMENT,
    GENERATION_CONDITIONS,
    LABELS,
    MODEL,
    OUTPUT,
    PREVIOUS,
    SOURCE,
    SYSTEMS,
    TASKS,
    TESTS,
    WORKER_PYTHON,
    encode,
    read_json,
    record,
    registrations,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import write

ROOT = Path(__file__).resolve().parents[2]


def public_tasks():
    return {task: read_json(ROOT / SOURCE / f"preparation/public/{task}.json") for task in TASKS}


def minimal_preparation(root):
    public = public_tasks()
    rows = registrations(public)
    prep = root / OUTPUT / "preparation"
    for task in TASKS:
        write(prep, f"public/{task}.json", encode(public[task]))
    write(prep, "registrations.json", encode(rows))
    return rows


@pytest.mark.parametrize("guidance", GENERATION_CONDITIONS)
def test_capsule_changes_only_public_common_suffix(guidance):
    files = c.capsule_files(ROOT, guidance)
    for name, raw in files.items():
        original = (ROOT / SOURCE / "preparation/worker_code/N" / name).read_bytes()
        if name == "common.py":
            suffix = "\n\n" + BASIS_INSTRUCTIONS[guidance]
            assert raw == original + ("\n\nSYSTEM = SYSTEM + " + repr(suffix) + "\n").encode()
        else:
            assert raw == original
    assert SYSTEMS[guidance] == COMMON_SYSTEM + "\n\n" + BASIS_INSTRUCTIONS[guidance]


@pytest.mark.parametrize("guidance", GENERATION_CONDITIONS)
@pytest.mark.parametrize("kind", ["first_Final", "response_cap", "tool_cap"])
def test_public_only_scripted_worker_contract(tmp_path, guidance, kind):
    code = tmp_path / "code"
    for name, raw in c.capsule_files(ROOT, guidance).items():
        write(code, name, raw)
    document = public_tasks()["X1" if guidance == "endpoint" else "X2"]
    write(tmp_path, "public.json", encode(document))
    for name in c.PRIVATE_FILES:
        write(tmp_path / "private", name, b"private fixture")
    if kind == "first_Final":
        script = [{"final": "ungraded"}, {"tool": "calculate", "arguments": {"expression": "1+1"}}]
    elif kind == "response_cap":
        script = [{"message": "fixture message"}] * 33
    else:
        script = [{"tool": "calculate", "arguments": {"expression": "1+1"}}] * 33
    write(tmp_path, "script.json", encode(script))
    command = [
        WORKER_PYTHON,
        "-I",
        "-S",
        "-B",
        str(code / "worker.py"),
        "--public",
        str(tmp_path / "public.json"),
        "--output",
        str(tmp_path / "result"),
        "--script",
        str(tmp_path / "script.json"),
        "--model",
        MODEL,
    ]
    for name in c.PRIVATE_FILES:
        command.extend(["--forbidden", str(tmp_path / "private" / name)])
    completed = subprocess.run(command, cwd=code, capture_output=True, check=False, timeout=30)
    assert completed.returncode == 0, completed.stderr.decode()
    result = read_json(tmp_path / "result/result.json")
    isolation = read_json(tmp_path / "result/isolation.json")
    assert result["provider_attempts"] == 0 and result["origin"] == "scripted_control"
    assert isolation["private_read_denied_before_provider"]
    assert not isolation["repository_modules_loaded"]
    assert len(isolation["private_read_probes"]) == len(c.PRIVATE_FILES)
    assert all(item["read_denied"] for item in isolation["private_read_probes"])
    initial = read_json(tmp_path / "result/turns/000_http_request.body")
    assert initial["messages"] == [
        {"role": "system", "content": SYSTEMS[guidance]},
        {"role": "user", "content": encode({"task": document}).decode()},
    ]
    assert initial["model"] == MODEL and initial["thinking"] == {"type": "enabled"}
    assert "temperature" not in initial and "top_p" not in initial
    assert result["first_final_stops"] and not result["history_truncated"]
    if kind == "first_Final":
        assert result["model_requests"] == 1 and result["tool_calls"] == 0
        assert result["terminal"] == "model_final"
    else:
        assert result["model_requests"] == 32
        assert result["tool_calls"] == (32 if kind == "tool_cap" else 0)
    assert manifest(tmp_path / "result")["result_id"] == result["id"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("replicate", 8),
        ("task_key", "X2"),
        ("arm", "movement"),
        ("response_budget", 33),
        ("requested_model", "other-model"),
    ],
)
def test_registration_metadata_cannot_be_swapped(field, value):
    public = public_tasks()
    rows = registrations(public)
    rows[0][field] = value
    with pytest.raises(ValueError, match="exact_new_registrations"):
        c.validate_registrations(rows, public)


def test_registration_order_and_balanced_waves_are_fixed():
    public = public_tasks()
    rows = c.validate_registrations(registrations(public), public)
    assert [row["label"] for row in rows] == list(LABELS)
    for selected, count in ((rows[:24], 6), (rows[24:], 2)):
        assert Counter((row["task_key"], row["arm"]) for row in selected) == {
            (task, guidance): count for task in TASKS for guidance in GENERATION_CONDITIONS
        }
    with pytest.raises(ValueError, match="exact_new_registrations"):
        c.validate_registrations(list(reversed(rows)), public)
    rows[0]["label"] = "E_X2_B2_01"
    with pytest.raises(ValueError, match="exact_new_registrations"):
        c.validate_registrations(rows, public)


def test_financial_prototypes_drop_all_old_class_identities():
    public = public_tasks()
    private = read_json(ROOT / SOURCE / "preparation/private/evaluation_targets.json")
    original = read_json(ROOT / SOURCE / "preparation/private/target_class_prototypes.json")
    reduced = c.financial_prototypes(public, private, original)
    assert set(reduced) == set(TASKS)
    for task in TASKS:
        for route in ("D", "R"):
            item = reduced[task][route]
            assert set(item) == {"signature"}
            assert set(item["signature"]) == set(c.SIGNATURE_CONTENT_FIELDS)
            assert "fixed_condition" not in item["signature"]
    altered = copy.deepcopy(original)
    altered["tasks"]["E"]["X1"]["D"]["signature"]["active_support"] = []
    with pytest.raises(ValueError, match="same_financial_content"):
        c.financial_prototypes(public, private, altered)


def test_launch_credential_uses_fd_and_exact_capsule_with_no_retry(tmp_path, monkeypatch):
    row = minimal_preparation(tmp_path)[3]
    observed = {}

    def failed_worker(command, **kwargs):
        observed.update(command=command, options=kwargs)
        descriptor = kwargs["pass_fds"][0]
        observed["fd"] = descriptor
        assert os.read(descriptor, 2048) == b"fixture-secret"
        assert "fixture-secret" not in repr(command) + repr(kwargs)
        assert kwargs["env"] == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
        assert command[1:4] == ["-I", "-S", "-B"]
        assert command[4].endswith("worker_code/movement/worker.py")
        assert command[command.index("--public") + 1].endswith("public/X2.json")
        assert command.count("--forbidden") == len(c.PRIVATE_FILES)
        assert "--script" not in command
        return subprocess.CompletedProcess(command, 9, b"", b"fixture failure")

    monkeypatch.setattr(c.subprocess, "run", failed_worker)
    result = c.launch_worker(tmp_path, row, "fixture-secret")
    assert result["terminal"] == "unknown_worker_failure" and result["exit_code"] == 9
    assert result["condition_id"] == row["condition_id"]
    with pytest.raises(OSError):
        os.fstat(observed["fd"])
    (tmp_path / OUTPUT / "online/sessions" / row["label"]).mkdir(parents=True)
    with pytest.raises(ValueError, match="no_session_retry"):
        c.launch_worker(tmp_path, row, "fixture-secret")


def test_launch_timeout_retains_unknown_and_closes_fd(tmp_path, monkeypatch):
    row = minimal_preparation(tmp_path)[0]
    descriptors = []

    def expired(command, **kwargs):
        descriptors.extend(kwargs["pass_fds"])
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"partial", stderr=b"")

    monkeypatch.setattr(c.subprocess, "run", expired)
    outcome = c.launch_worker(tmp_path, row, "fixture-secret")
    assert outcome["terminal"] == "unknown_worker_timeout"
    assert (
        tmp_path / OUTPUT / "online/collector_logs" / (row["label"] + ".stdout")
    ).read_bytes() == b"partial"
    with pytest.raises(OSError):
        os.fstat(descriptors[0])


def test_reservation_cap_counts_partial_unknown_sessions(tmp_path):
    label = LABELS[0]
    turns = tmp_path / "sessions" / label / "turns"
    for index in range(32):
        write(
            turns,
            f"{index:03d}_reservation.json",
            encode(
                {
                    "index": index,
                    "provider_call": True,
                    "requested_model": MODEL,
                }
            ),
        )
        write(turns, f"{index:03d}_tool.json", b"{}")
    requests, tools = c.reservation_counts(tmp_path)
    assert requests[label] == tools[label] == 32
    assert sum(requests.values()) == 32
    write(turns, "032_reservation.json", b"{}")
    with pytest.raises(ValueError, match="session_request_cap"):
        c.reservation_counts(tmp_path)


@pytest.mark.parametrize(
    "case", ["historical_session", "scripted_request", "gap", "tool_without_request"]
)
def test_reservation_accounting_rejects_out_of_scope_or_inconsistent_files(tmp_path, case):
    label = "E_X2_B2_01" if case == "historical_session" else LABELS[0]
    turns = tmp_path / "sessions" / label / "turns"
    if case == "tool_without_request":
        write(turns, "000_tool.json", b"{}")
    else:
        index = 1 if case == "gap" else 0
        write(
            turns,
            f"{index:03d}_reservation.json",
            encode(
                {
                    "index": index,
                    "provider_call": case != "scripted_request",
                    "requested_model": MODEL,
                }
            ),
        )
    with pytest.raises(ValueError):
        c.reservation_counts(tmp_path)


def test_mocked_collection_finishes_both_waves_once_before_review(tmp_path, monkeypatch):
    rows = minimal_preparation(tmp_path)
    entered, submitted, exited = [], [], []
    monkeypatch.setattr(c, "history_guard", lambda root: {"unchanged": True})
    monkeypatch.setattr(c, "verify_preparation", lambda root: {})
    monkeypatch.setattr(c, "credential", lambda path: "fixture-secret")

    class InlinePool:
        def __init__(self, max_workers):
            assert max_workers == 24
            self.wave = len(entered) + 1

        def __enter__(self):
            if self.wave == 2:
                assert exited == [1] and len(submitted) == 24
            entered.append(self.wave)
            return self

        def __exit__(self, *args):
            exited.append(self.wave)

        def submit(self, function, root, row, secret):
            assert secret == "fixture-secret" and row["wave"] == self.wave
            submitted.append(row["label"])
            future = Future()
            if row["label"] == LABELS[0]:
                future.set_exception(OSError("fixture worker startup failure"))
            else:
                future.set_result({**c._base(row), "terminal": "unknown_worker_failure"})
            return future

    monkeypatch.setattr(c, "ThreadPoolExecutor", InlinePool)
    monkeypatch.setattr(c, "as_completed", lambda futures: list(reversed(list(futures))))
    result = c.collect(tmp_path)
    assert submitted == list(LABELS) and entered == exited == [1, 2]
    assert [row["label"] for row in result["rows"]] == list(LABELS)
    assert result["rows"][0]["terminal"] == "unknown_collector_failure"
    assert result["registered"] == 32 and result["all_workers_terminated"]
    assert result["model_requests"] == result["Student_runs"] == result["tokenizer_calls"] == 0
    assert result["retries_replacements_or_topups"] == 0
    assert result["training_allowed"] is False
    assert result["waves"][0]["submitted"] == [r["label"] for r in rows[:24]]
    assert result["waves"][1]["submitted"] == [r["label"] for r in rows[24:]]
    manifest(tmp_path / OUTPUT / "online")
    with pytest.raises(ValueError, match="once_no_overwrite_or_resume"):
        c.collect(tmp_path)


def prepare_fixture(root, monkeypatch):
    paths = [SOURCE + f"/preparation/public/{task}.json" for task in TASKS]
    paths += [
        SOURCE + "/preparation/private/evaluation_targets.json",
        SOURCE + "/preparation/private/target_class_prototypes.json",
        SOURCE + "/preparation/conditions.json",
        PREVIOUS + "/closeout/support_selection.json",
        c.BINDING_PATH,
        c.PARENT_POLICY_PATH,
    ]
    files = {guidance: c.capsule_files(ROOT, guidance) for guidance in GENERATION_CONDITIONS}
    paths += [SOURCE + "/preparation/worker_code/N/" + name for name in files["endpoint"]]
    for path in paths:
        write(root, path, (ROOT / path).read_bytes())
    write(root, DOCUMENT, b"fixture frozen design\n")
    for path in TESTS:
        write(root, path, b"# fixture test reference\n")
    audit = b"fixture accepted support audit\n"
    write(root, "audit.txt", audit)
    monkeypatch.setattr(c, "AUDIT", str(root / "audit.txt"))
    monkeypatch.setattr(c, "AUDIT_SHA", sha(audit))
    monkeypatch.setattr(c, "history_guard", lambda root: {"unchanged": True})
    monkeypatch.setattr(
        c, "implementation", lambda root: record("fixture_implementation", references=[])
    )
    monkeypatch.setattr(c, "capsule_files", lambda root, guidance: files[guidance])


def test_prepare_freezes_metadata_and_new_sources_without_execution(tmp_path, monkeypatch):
    prepare_fixture(tmp_path, monkeypatch)
    controls = []

    def controlled_pytest(command, **kwargs):
        assert command[-len(TESTS) :] == list(TESTS)
        assert kwargs["cwd"] == tmp_path
        controls.append(command)
        return subprocess.CompletedProcess(command, 0, b"mocked controls\n", b"")

    monkeypatch.setattr(c.subprocess, "run", controlled_pytest)
    monkeypatch.setattr(c, "credential", lambda *args: pytest.fail("preparation read a credential"))
    result = c.prepare(tmp_path)
    prep = tmp_path / OUTPUT / "preparation"
    assert len(controls) == 1 and result["registrations"] == 32
    assert (
        result["new_model_requests"] == result["new_tokenizer_calls"] == result["Student_runs"] == 0
    )
    assert result["training_allowed"] is False
    assert read_json(prep / "execution_guards.json")["all_zero"]
    assert set(read_json(prep / "private/evaluation_targets.json")) == set(TASKS)
    assert set(read_json(prep / "private/target_class_prototypes.json")) == set(TASKS)
    assert len(read_json(prep / "private/review_identity_map.json")) == 32
    assert read_json(prep / "private/x2_cross_quantity_context.json")["task_key"] == "X2"
    assert set(read_json(prep / "conditions.json")) == set(GENERATION_CONDITIONS)
    for task in TASKS:
        assert (prep / f"public/{task}.json").read_bytes() == (
            ROOT / SOURCE / f"preparation/public/{task}.json"
        ).read_bytes()
    manifest(prep)
    assert not (tmp_path / OUTPUT / "online").exists()
    with pytest.raises(ValueError, match="new_fixed_batch_only"):
        c.prepare(tmp_path)


def test_prepare_rejects_tokenizer_instantiation(tmp_path, monkeypatch):
    prepare_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(c, "read_bound_metadata", lambda root: c.assets.load_tokenizer({}))
    with pytest.raises(RuntimeError, match="tokenizer_loading_forbidden"):
        c.prepare(tmp_path)
    assert not (tmp_path / OUTPUT / "preparation/manifest.json").exists()


def test_failed_preparation_controls_do_not_seal_or_start_collection(tmp_path, monkeypatch):
    prepare_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        c.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            1,
            b"fixture control failure\n",
            b"",
        ),
    )
    with pytest.raises(ValueError, match="new_controls_before_calls"):
        c.prepare(tmp_path)
    assert not (tmp_path / OUTPUT / "preparation/manifest.json").exists()
    assert not (tmp_path / OUTPUT / "online").exists()


def test_store_does_not_resume_or_mutate_a_sealed_batch(tmp_path):
    store = Store(tmp_path / "stage")
    store.json("report.json", {"fixture": True})
    store.seal()
    with pytest.raises(ValueError, match="already_sealed"):
        store.json("late.json", {})
    with pytest.raises(ValueError, match="once_no_overwrite_or_resume"):
        Store(tmp_path / "stage")
