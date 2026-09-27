"""Synthetic rate-only extra budgets and shared paced transport injection.

No live HTTP, environment credential, production registration or model execution.
"""

import json
from types import SimpleNamespace

import pytest
import run_cross_market_paced_mainline_20260927 as m
from test_cross_market_review_pilot import packet as synthetic_packet
from test_cross_market_text_schema_recovery import response as packet_response

KEY = "SYNTHETIC_PACED_KEY"


@pytest.fixture(autouse=True)
def no_credentials_or_network(monkeypatch):
    monkeypatch.setattr(m.original.transport, "credential", lambda: KEY)

    def forbidden(*args, **kwargs):
        raise AssertionError("No live network in wrapper tests")

    monkeypatch.setattr(m.original.transport.urllib.request, "build_opener", forbidden)


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m.original, "RAW", tmp_path / "old-mainline")
    monkeypatch.setattr(m, "ROOT", m.original.RAW / "paced_recovery")
    monkeypatch.setattr(m, "RECORD", m.ROOT / "protocol.json")
    monkeypatch.setattr(m.resolution, "ROOT", m.original.RAW / "task-adjudication")
    monkeypatch.setattr(m.resolution, "RECORD", m.resolution.ROOT / "protocol.json")
    monkeypatch.setattr(m.recovery, "RECORD", m.original.RAW / "schema.json")
    monkeypatch.setattr(m.recovery.capacity, "RECORD", m.original.RAW / "capacity.json")
    packet = synthetic_packet(9)
    path = tmp_path / "materials/packet.json"
    m.base.write(path, packet)
    row = dict(
        packet_id=packet["id"],
        raw_object_id=packet["raw_object_id"],
        reference=m.original.ref(path),
    )
    parent = dict(
        id="synthetic-parent", packet_universe=[row], eligible_candidate_task_ids=["task:A"]
    )
    rate = dict(id="synthetic-rate", parent_protocol_id=parent["id"])
    resolution = dict(id="synthetic-resolution", eligible_candidate_task_ids=["task:A"])
    for target, value in (
        (m.RECORD, rate),
        (m.original.RAW / "protocol.json", parent),
        (m.resolution.RECORD, resolution),
        (m.recovery.RECORD, {"id": "synthetic-schema"}),
        (m.recovery.capacity.RECORD, {"id": "synthetic-capacity"}),
    ):
        m.base.write(target, value)
    transport = m.recovery.capacity.transport_namespace(m.original.ref(m.recovery.capacity.RECORD))
    original_provider = transport.Provider
    calls = []

    def sender(raw, key):
        assert key == KEY
        calls.append(raw)
        return packet_response(raw)

    transport.Provider = lambda output, key: original_provider(output, key, sender=sender)
    namespace = m.recovery.capacity.isolation.isolated_namespace(m.original, transport=transport)
    return dict(
        tmp=tmp_path,
        packet=packet,
        row=row,
        parent=parent,
        rate=rate,
        resolution=resolution,
        namespace=namespace,
        transport=transport,
        original_provider=original_provider,
        calls=calls,
    )


def old_receipt(
    case, code=429, *, branch="recovery_attempts", attempt=2, at="2026-09-27T02:00:00+00:00"
):
    path = (
        m.original.RAW
        / branch
        / m.original.key_for(case["row"]["packet_id"])
        / str(attempt)
        / "physical_requests/request/receipt.json"
    )
    m.base.write(path, dict(at=at, http_status=code, status="ATTEMPT_FAILED_NOT_REFUNDED"))
    return path


def call(case):
    return m.rate_recover(case["namespace"], case["parent"], case["row"], KEY, case["rate"])


def test_latest_original_receipt_is_required_not_any_historical429(case):
    assert m.rate_evidence(case["row"]["packet_id"]) is None
    earlier = old_receipt(case, branch="attempts", attempt=1, at="2026-09-27T01:00:00+00:00")
    assert m.rate_evidence(case["row"]["packet_id"]) == m.original.ref(earlier)
    old_receipt(case, 500, at="2026-09-27T03:00:00+00:00")
    assert m.rate_evidence(case["row"]["packet_id"]) is None
    assert call(case) is None
    assert case["calls"] == []
    assert not list((m.ROOT / "attempts").glob("*/*/reservation.json"))


@pytest.mark.parametrize("code", [200, 400, 401, 403, 500, None])
def test_non429_old_failure_cannot_spend_rate_only_budget(case, code):
    old_receipt(case, code)
    assert call(case) is None
    assert case["calls"] == []


def test_success_preserves_old_attempt_and_semantic_contract(case):
    receipt = old_receipt(case)
    before = receipt.read_bytes()
    result = call(case)
    assert len(case["calls"]) == 1
    assert result["protocol_id"] == case["parent"]["id"]
    assert result["packet_id"] == case["packet"]["id"]
    assert result["packet_sha256"] == case["row"]["reference"]["sha256"]
    assert result["execution"]["pacing_protocol_id"] == case["rate"]["id"]
    assert result["execution"]["exhausted429_reference"] == m.original.ref(receipt)
    assert receipt.read_bytes() == before
    saved = (
        m.original.RAW / "packet_reviews" / (m.original.key_for(case["row"]["packet_id"]) + ".json")
    )
    assert m.base.read(saved) == result
    assert json.loads(case["calls"][0])["max_tokens"] == 4096
    assert m.recovery.MAX_EXTRA_POSTS == 128
    assert m.recovery.EXTRA_ATTEMPTS_PER_PACKET == m.original.ATTEMPTS == 2


def test_only_registered_packet_and_parent_can_recover(case):
    old_receipt(case)
    altered = dict(case["row"], raw_object_id="changed")
    with pytest.raises(ValueError, match="registered_parent_packet"):
        m.rate_recover(case["namespace"], case["parent"], altered, KEY, case["rate"])
    with pytest.raises(ValueError, match="registered_parent_packet"):
        m.rate_recover(
            case["namespace"],
            case["parent"],
            case["row"],
            KEY,
            {**case["rate"], "parent_protocol_id": "other"},
        )
    assert case["calls"] == []


def fail_sender(case):
    def sender(raw, key):
        case["calls"].append(raw)
        return packet_response(raw, fault="invalid_JSON")

    case["transport"].Provider = lambda output, key: case["original_provider"](
        output, key, sender=sender
    )


def test_rate_packet_stops_after_three_and_rerun_never_resets_budget(case):
    receipt = old_receipt(case)
    original_bytes = receipt.read_bytes()
    fail_sender(case)
    assert call(case) is None
    assert call(case) is None
    assert len(case["calls"]) == 3
    reservations = list((m.ROOT / "attempts").glob("*/*/reservation.json"))
    assert len(reservations) == 3
    assert {m.base.read(path)["attempt"] for path in reservations} == {1, 2, 3}
    assert all(
        m.base.read(path.with_name("outcome.json"))["status"] == "FAILED_NOT_REFUNDED"
        for path in reservations
    )
    assert receipt.read_bytes() == original_bytes
    assert not list((m.original.RAW / "packet_reviews").glob("*.json"))


@pytest.mark.parametrize("already,expected_calls", [(64, 0), (62, 2)])
def test_global64_extra_reservations_cannot_reset(case, already, expected_calls):
    old_receipt(case)
    fail_sender(case)
    for index in range(already):
        m.base.write(
            m.ROOT / "attempts" / f"occupied-{index}" / "1/reservation.json", dict(attempt=index)
        )
    assert call(case) is None
    assert call(case) is None
    assert len(case["calls"]) == expected_calls
    assert len(list((m.ROOT / "attempts").glob("*/*/reservation.json"))) == 64


def test_unsettled_rate_attempt_is_charged_and_not_replayed(case):
    old_receipt(case)
    directory = m.ROOT / "attempts" / m.original.key_for(case["row"]["packet_id"])
    m.base.write(directory / "1/reservation.json", dict(original_unsettled=True))
    assert call(case) is not None
    assert len(case["calls"]) == 1
    assert m.base.read(directory / "1/reservation.json") == dict(original_unsettled=True)
    assert (
        m.base.read(directory / "1/outcome.json")["status"] == "INTERRUPTED_UNSETTLED_NOT_REFUNDED"
    )
    assert (directory / "2/reservation.json").exists()


def test_reservation_precedes_any_packet_transport(case):
    receipt = old_receipt(case)

    def sender(raw, key):
        paths = list((m.ROOT / "attempts").glob("*/*/reservation.json"))
        assert len(paths) == 1
        value = m.base.read(paths[0])
        assert value["request_sha256"] == m.base.sha(raw)
        assert value["prior429"] == m.original.ref(receipt)
        return packet_response(raw)

    case["transport"].Provider = lambda output, key: case["original_provider"](
        output, key, sender=sender
    )
    assert call(case) is not None


def test_registration_freezes_64_three_and_original_five_minute_cooldown(case, monkeypatch):
    # Registration has not happened in this isolated namespace; use a fresh file.
    monkeypatch.setattr(m, "RECORD", m.ROOT / "registered-plan.json")
    rows = [case["row"]]
    for index in (10, 11):
        packet = synthetic_packet(index)
        rows.append(
            dict(
                packet_id=packet["id"],
                reference={"path": str(case["tmp"] / "unused"), "sha256": "a" * 64},
            )
        )
    parent = {**case["parent"], "packet_universe": rows}
    m.base.write(
        m.original.RAW / "status.json",
        dict(
            state="TEXT_REVIEW_TECHNICAL_PENDING",
            saved_packet_reviews=2042,
            failed_packet_ids=[row["packet_id"] for row in rows],
        ),
    )
    for index, row in enumerate(rows):
        path = (
            m.original.RAW
            / "recovery_attempts"
            / m.original.key_for(row["packet_id"])
            / "2/physical_requests/request/receipt.json"
        )
        m.base.write(path, dict(at=f"2026-09-27T02:00:0{index}+00:00", http_status=429))
    monkeypatch.setattr(m.original, "protocol", lambda root: parent)
    monkeypatch.setattr(m.resolution, "protocol", lambda root: case["resolution"])
    source_root = case["tmp"] / "source"
    sources = {name: b"synthetic committed source\n" for name in (m.SCRIPT, m.pacing.SCRIPT)}
    for name, payload in sources.items():
        path = source_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        # This runtime fixture is an artifact, not a project source edit.
        m.base.write(path, {"synthetic": payload.decode()})
        sources[name] = path.read_bytes()

    def git(command, **kwargs):
        if command[1] == "rev-parse":
            return "synthetic-head\n"
        return sources[command[2].split(":", 1)[1]]

    monkeypatch.setattr(m.subprocess, "check_output", git)
    result = m.register(source_root)
    assert result["maximum_additional_POSTs"] == 64
    assert result["maximum_extra_attempts_per_rate_packet"] == 3
    assert result["pacing"] == m.pacing.expected_pacing("2026-09-27T02:05:02+00:00")
    assert result["pacing"]["max_concurrency"] == 4
    assert result["old_budgets_unchanged"] is True
    assert result["old_attempts_refunded"] == 0
    assert result["model"] == m.original.MODEL


def test_shared_sender_injected_into_packet_and_task_with_correct_restart_script(case, monkeypatch):
    original_provider = m.original.transport.Provider
    original_task_factory = m.resolution.provider_class
    original_packet_review = m.original.review_packet
    original_semantic_builder = m.original.semantic.build_packet_review
    sender_calls, preflights, make_calls = [], [], []

    class Sender:
        def preflight(self, key, model):
            assert key == KEY and model == m.original.MODEL
            preflights.append((key, model))

        def __call__(self, raw, key):
            body = json.loads(raw)
            sender_calls.append(body["max_tokens"])
            if body["max_tokens"] == 4096:
                return packet_response(raw)
            return m.base.encode(
                dict(
                    model=m.original.MODEL,
                    id="synthetic-task-response",
                    usage=dict(prompt_tokens=3, completion_tokens=5, total_tokens=8),
                    choices=[dict(finish_reason="stop", message=dict(content='{"judgments":[]}'))],
                )
            ), "synthetic-id"

    sender = Sender()

    def make_sender(root, reference):
        make_calls.append((root, reference))
        return sender

    monkeypatch.setattr(m.pacing, "make_sender", make_sender)
    monkeypatch.setattr(m.resolution, "protocol", lambda root: case["resolution"])
    monkeypatch.setattr(m.original, "protocol", lambda root: case["parent"])
    namespace = m.recovery.capacity.isolation.isolated_namespace(
        m.original,
        transport=m.recovery.capacity.transport_namespace(
            m.original.ref(m.recovery.capacity.RECORD)
        ),
    )
    parent_value = {"saved": "existing parent review"}
    namespace["review_packet"] = lambda *args: parent_value
    monkeypatch.setattr(m.recovery, "execution_namespace", lambda *args: namespace)
    initial = m.base.record(
        m.original.semantic.REVIEW_KIND,
        task_id="task:A",
        status="PENDING_TASK_EVIDENCE",
        passed=False,
    )
    monkeypatch.setattr(m.original.semantic, "assess_task", lambda *args, **kwargs: initial)
    monkeypatch.setattr(m.original, "frozen", lambda ref: dict(pages=[]))
    monkeypatch.setattr(
        m.resolution.adjudication,
        "request_for",
        lambda *args: dict(
            model=m.original.MODEL,
            messages=[
                dict(role="system", content="Task scope"),
                dict(role="user", content="Original source"),
            ],
            max_tokens=16384,
            response_format={"type": "json_object"},
            thinking={"type": "disabled"},
            stream=False,
        ),
    )
    monkeypatch.setattr(
        m.resolution.adjudication,
        "resolve_task",
        lambda initial, payload, execution: m.base.record(
            m.original.semantic.REVIEW_KIND,
            baseline_review_id=initial["id"],
            adjudication_protocol_id=execution["protocol_id"],
            status="PASS_TEXT_TABLE_SCOPE",
            passed=True,
        ),
    )
    rate_calls = []
    monkeypatch.setattr(m, "rate_recover", lambda *args: rate_calls.append(args) or None)
    ns, pool = m.execution_namespace(case["tmp"], case["rate"])
    try:
        assert ns["CONCURRENCY"] == 4
        assert ns["SCRIPT"] == m.SCRIPT
        assert ns["review_packet"](case["parent"], case["row"], KEY) is parent_value
        assert rate_calls == []
        projection, request = ns["request_for"](case["packet"], case["row"]["reference"])
        ns["transport"].Provider(m.ROOT / "direct_packet", KEY)(request)
        raw_id = case["packet"]["raw_object_id"]
        task = dict(task_id="task:A", source_exhaustion_review_raw_objects=[raw_id])
        material_plan = dict(
            tasks=[task],
            documents=[
                dict(
                    document=dict(raw_object_id=raw_id),
                    page_text_reference=dict(path="synthetic-text"),
                )
            ],
        )
        manifest = dict(packets=[case["row"]])
        result = ns["semantic"].assess_task(
            task,
            material_plan,
            manifest,
            {},
            {case["row"]["packet_id"]: {}},
            {},
            review_protocol_id=case["parent"]["id"],
        )
        assert result["passed"] is True
        launched = []
        monkeypatch.setattr(
            m.original.subprocess,
            "Popen",
            lambda args, **kwargs: launched.append(args) or SimpleNamespace(pid=1234),
        )
        ns["protocol"] = lambda root: case["parent"]
        ns["start"](case["tmp"])
        assert launched[0][1] == str(case["tmp"] / m.SCRIPT)
    finally:
        pool.shutdown(wait=True)
    assert make_calls == [(m.ROOT / "pacing", m.original.ref(m.RECORD))]
    assert sender_calls == [4096, 16384]
    assert len(preflights) == 2
    assert m.original.transport.Provider is original_provider
    assert m.resolution.provider_class is original_task_factory
    assert m.original.review_packet is original_packet_review
    assert m.original.semantic.build_packet_review is original_semantic_builder
    assert m.original.CONCURRENCY == 16 and m.resolution.CONCURRENCY == 8
