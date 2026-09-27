"""Synthetic task clarification, isolated transport and ready-source scheduling.

No real credential file, API, source document, Student or GPU is accessed.
"""

import copy
import json
import threading

import pytest
import run_cross_market_text_task_resolution_20260927 as m

KEY = "SYNTHETIC_TEST_KEY_DO_NOT_USE"


def request(text="Synthetic original financial text"):
    return dict(
        model=m.original.MODEL,
        messages=[
            dict(role="system", content="Synthetic task clarification"),
            dict(role="user", content=text),
        ],
        max_tokens=16384,
        response_format={"type": "json_object"},
        thinking={"type": "disabled"},
        stream=False,
    )


def response(content='{"judgments":[]}', *, finish="stop", output=7):
    return m.base.encode(
        dict(
            model=m.original.MODEL,
            id="synthetic-response",
            usage=dict(prompt_tokens=13, completion_tokens=output, total_tokens=13 + output),
            choices=[dict(finish_reason=finish, message=dict(content=content))],
        )
    ), "synthetic-request-id"


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "ROOT", tmp_path / "task_adjudication")
    monkeypatch.setattr(m, "RECORD", m.ROOT / "protocol.json")
    task = dict(task_id="task:A", group="composition_required")
    initial = m.base.record(
        m.original.semantic.REVIEW_KIND,
        task_id=task["task_id"],
        status="PENDING_TASK_EVIDENCE",
        passed=False,
        specific_original_doubt="Original source uncertainty is retained",
    )
    plan = dict(id="synthetic-task-protocol", eligible_candidate_task_ids=[task["task_id"]])
    m.base.write(m.RECORD, plan)
    calls, resolutions = [], []
    frozen_request = request()
    monkeypatch.setattr(m.adjudication, "request_for", lambda *args: copy.deepcopy(frozen_request))

    def resolve(original, payload, execution):
        resolutions.append(
            (copy.deepcopy(original), copy.deepcopy(payload), copy.deepcopy(execution))
        )
        return m.base.record(
            m.original.semantic.REVIEW_KIND,
            task_id=task["task_id"],
            status="PASS_TEXT_TABLE_SCOPE",
            passed=True,
            baseline_review_id=original["id"],
            adjudication_protocol_id=execution["protocol_id"],
        )

    monkeypatch.setattr(m.adjudication, "resolve_task", resolve)
    real_provider = m.provider_class()

    def provider(sender):
        def wrapped(raw, key):
            assert key == KEY
            calls.append(raw)
            return sender(raw, key)

        monkeypatch.setattr(
            m,
            "provider_class",
            lambda: lambda output, key: real_provider(output, key, sender=wrapped),
        )

    provider(lambda raw, key: response())
    return dict(
        task=task,
        initial=initial,
        plan=plan,
        calls=calls,
        resolutions=resolutions,
        provider=provider,
        request=frozen_request,
        directory=m.ROOT / "tasks" / m.base.sha(task["task_id"]),
    )


def test_provider_task_limits_preserve_old_packet_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    original, token_limit, byte_limit = (
        m.original.transport.Provider.__call__,
        m.original.transport.core.MAX_OUTPUT_TOKENS,
        m.original.transport.MAX_REQUEST_BYTES,
    )
    body = request("文" * 100000)
    assert 262144 < len(m.base.encode(body)) < m.MAX_REQUEST_BYTES == 900000
    calls = []

    def sender(raw, key):
        calls.append(json.loads(raw))
        return response(output=10000)

    result = m.provider_class()(tmp_path / "isolated", KEY, sender=sender)(body)
    assert result["usage"]["completion_tokens"] == 10000
    assert calls[0]["max_tokens"] == 16384
    assert m.original.transport.Provider.__call__ is original
    assert m.original.transport.core.MAX_OUTPUT_TOKENS == token_limit == 4096
    assert m.original.transport.MAX_REQUEST_BYTES == byte_limit == 131072
    assert m.recovery.capacity.MAX_REQUEST_BYTES == 262144
    old = dict(body, max_tokens=4096)
    with pytest.raises(ValueError, match="request_bytes"):
        m.original.transport.request_bytes(old)


def test_wire_bound_is_real_and_rejects_before_sender(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)

    def forbidden(*args):
        raise AssertionError("oversized request must never reach transport")

    with pytest.raises(ValueError, match="request_bytes"):
        m.provider_class()(tmp_path / "isolated", KEY, sender=forbidden)(
            request("x" * m.MAX_REQUEST_BYTES)
        )
    assert not list(tmp_path.rglob("request.json"))


def test_complete_resolution_saves_initial_once_and_cache_never_calls_again(case, monkeypatch):
    first = m.resolve_one(case["plan"], case["task"], case["initial"], {}, KEY)
    original_bytes = (case["directory"] / "initial_review.json").read_bytes()

    def forbidden(*args):
        raise AssertionError("cached resolution must not make another request")

    monkeypatch.setattr(m.adjudication, "request_for", forbidden)
    again = m.resolve_one(case["plan"], case["task"], case["initial"], {}, KEY)
    assert again == first
    assert len(case["calls"]) == len(case["resolutions"]) == 1
    assert m.base.read(case["directory"] / "initial_review.json") == case["initial"]
    assert (case["directory"] / "initial_review.json").read_bytes() == original_bytes
    execution = case["resolutions"][0][2]
    assert execution["baseline_review_id"] == case["initial"]["id"]
    assert execution["protocol_id"] == case["plan"]["id"]
    assert execution["independent_of_Student_and_Q"] is True
    for path in case["directory"].rglob("*.json"):
        assert KEY not in path.read_text()


@pytest.mark.parametrize("status", ["PASS_TEXT_TABLE_SCOPE", "PENDING_TECHNICAL_REVIEW"])
def test_already_pass_or_incomplete_source_never_uses_adjudication_provider(
    case, monkeypatch, status
):
    initial = {**case["initial"], "status": status}

    def forbidden():
        raise AssertionError("this branch may not invoke provider")

    monkeypatch.setattr(m, "provider_class", forbidden)
    assert m.resolve_one(case["plan"], case["task"], initial, {}, KEY) is initial
    assert not case["directory"].exists()


def test_unregistered_pending_candidate_refused_before_provider(case):
    with pytest.raises(ValueError, match="fixed_candidate"):
        m.resolve_one(case["plan"], dict(task_id="outside"), case["initial"], {}, KEY)
    assert case["calls"] == []


@pytest.mark.parametrize("fault", ["invalid_json", "length"])
def test_two_failed_attempts_are_preserved_never_repaired_or_refunded(case, fault):
    case["provider"](
        lambda raw, key: response(
            "{BROKEN ORIGINAL", finish="length" if fault == "length" else "stop"
        )
    )
    before = copy.deepcopy(case["initial"])
    for _ in range(2):
        with pytest.raises(ValueError, match="exhausted_technical_attempts"):
            m.resolve_one(case["plan"], case["task"], case["initial"], {}, KEY)
    assert len(case["calls"]) == 2
    assert case["resolutions"] == []
    assert case["initial"] == before
    assert not (case["directory"] / "resolved_review.json").exists()
    assert len(list(case["directory"].glob("attempts/*/reservation.json"))) == 2
    for path in case["directory"].glob("attempts/*/physical_requests/*/raw_response.json"):
        assert "{BROKEN ORIGINAL" in m.base.read(path)["body_utf8"]
    assert all(
        m.base.read(path)["status"] == "TECHNICAL_FAILURE_NOT_REFUNDED"
        for path in case["directory"].glob("attempts/*/outcome.json")
    )


def test_reserved_interrupted_attempt_is_not_replayed(case):
    path = case["directory"] / "attempts/1/reservation.json"
    reservation = dict(original_unsettled_attempt=True)
    m.base.write(path, reservation)
    result = m.resolve_one(case["plan"], case["task"], case["initial"], {}, KEY)
    assert result["passed"] is True
    assert len(case["calls"]) == 1
    assert m.base.read(path) == reservation
    assert (
        m.base.read(path.with_name("outcome.json"))["status"]
        == "INTERRUPTED_UNSETTLED_NOT_REFUNDED"
    )
    assert (case["directory"] / "attempts/2/reservation.json").exists()


def test_request_is_reserved_before_transport(case):
    def sender(raw, key):
        rows = list(case["directory"].glob("attempts/*/reservation.json"))
        assert len(rows) == 1
        saved = m.base.read(rows[0])
        assert saved["request_sha256"] == m.base.sha(raw)
        assert saved["baseline_review_id"] == case["initial"]["id"]
        return response()

    case["provider"](sender)
    m.resolve_one(case["plan"], case["task"], case["initial"], {}, KEY)


@pytest.mark.parametrize("broken", ["hash", "protocol", "baseline"])
def test_tampered_or_wrong_revision_cached_resolution_refused(case, broken):
    value = m.resolve_one(case["plan"], case["task"], case["initial"], {}, KEY)
    if broken == "hash":
        changed = {**value, "passed": False}
    else:
        body = {k: v for k, v in value.items() if k not in {"id", "schema_version"}}
        body["adjudication_protocol_id" if broken == "protocol" else "baseline_review_id"] = (
            "different"
        )
        changed = m.base.record(m.original.semantic.REVIEW_KIND, **body)
    m.base.write(case["directory"] / "resolved_review.json", changed, immutable=False)
    with pytest.raises(ValueError):
        m.resolve_one(case["plan"], case["task"], case["initial"], {}, KEY)
    assert len(case["calls"]) == 1


def test_execution_namespace_uses_only_complete_original_source_coverage(case, monkeypatch):
    monkeypatch.setattr(m.recovery, "RECORD", m.ROOT / "recovery.json")
    m.base.write(m.recovery.RECORD, dict(id="synthetic-schema-recovery"))
    packets = {
        key: dict(id=key, source=source) for key, source in (("A1", "A"), ("A2", "A"), ("B1", "B"))
    }
    loaded_packets, loaded_texts, assessed, resolved = [], [], [], []
    lock = threading.Lock()

    def packet_at(path, digest):
        with lock:
            loaded_packets.append((path, digest))
        return packets[path]

    monkeypatch.setattr(m.recovery, "execution_namespace", lambda *args: {"packet_at": packet_at})
    credentials = []
    monkeypatch.setattr(m.original.transport, "credential", lambda: credentials.append(True) or KEY)

    def frozen(reference):
        with lock:
            loaded_texts.append(reference["path"])
        return dict(pages=[dict(page=1, text="Source " + reference["path"])])

    monkeypatch.setattr(m.original, "frozen", frozen)

    def assess(task, material_plan, manifest, material, reviews, texts, *, review_protocol_id):
        with lock:
            assessed.append(
                dict(
                    task=task["task_id"],
                    packets=set(material),
                    texts=set(texts),
                    review_protocol_id=review_protocol_id,
                )
            )
        return dict(
            id="initial:" + task["task_id"],
            status="PASS_TEXT_TABLE_SCOPE" if task["task_id"] == "tA" else "PENDING_TASK_EVIDENCE",
        )

    def resolve(plan, task, initial, material, key):
        assert key == KEY
        with lock:
            resolved.append((task["task_id"], initial["id"], set(material)))
        return initial

    monkeypatch.setattr(m.original.semantic, "assess_task", assess)
    monkeypatch.setattr(m, "resolve_one", resolve)
    tasks = [
        dict(task_id=tid, source_exhaustion_review_raw_objects=ids)
        for tid, ids in (("tA", ["A"]), ("tB", ["B"]), ("tAB", ["A", "B"]), ("outside", ["A"]))
    ]
    plan = dict(id="task-adjudication-plan", eligible_candidate_task_ids=["tA", "tB", "tAB"])
    material_plan = dict(
        tasks=tasks,
        documents=[
            dict(
                document=dict(raw_object_id=key),
                page_text_reference=dict(path=key, sha256="text:" + key),
            )
            for key in ("A", "B")
        ],
    )
    manifest = dict(
        packets=[
            dict(
                raw_object_id=source,
                packet_id=key,
                reference=dict(path=key, sha256="digest:" + key),
            )
            for key, source in (("A1", "A"), ("A2", "A"), ("B1", "B"))
        ]
    )
    reviews = {key: {} for key in ("A1", "A2")}
    namespace, pool = m.execution_namespace(plan)
    try:
        assert pool._max_workers == 8
        first = namespace["semantic"].assess_task(
            tasks[0],
            material_plan,
            manifest,
            {"UNTRUSTED_CALLER_PACKET": {}},
            reviews,
            {"UNTRUSTED_CALLER_TEXT": {}},
            review_protocol_id="original-parent",
        )
        assert first["id"] == "initial:tA"
        assert [row["task"] for row in assessed] == ["tA"]
        reviews["B1"] = {}
        namespace["semantic"].assess_task(
            tasks[1], material_plan, manifest, {}, reviews, {}, review_protocol_id="original-parent"
        )
    finally:
        pool.shutdown(wait=True)
    by_task = {row["task"]: row for row in assessed}
    assert set(by_task) == {"tA", "tB", "tAB"}
    assert by_task["tA"]["packets"] == {"A1", "A2"}
    assert by_task["tB"]["packets"] == {"B1"}
    assert by_task["tAB"]["packets"] == {"A1", "A2", "B1"}
    assert by_task["tAB"]["texts"] == {"A", "B"}
    assert all(row["review_protocol_id"] == "original-parent" for row in assessed)
    assert all(pair[1] == "digest:" + pair[0] for pair in loaded_packets)
    assert set(loaded_texts) == {"A", "B"}
    assert credentials == [True]
    assert len(resolved) == 3
    assert m.original.semantic.assess_task is assess
    bundle = namespace["base"].record(m.original.semantic.BUNDLE_KIND, original_field=True)
    assert bundle["task_adjudication_protocol_id"] == plan["id"]
    assert namespace["base"].record("unrelated", marker=1) == m.base.record("unrelated", marker=1)
