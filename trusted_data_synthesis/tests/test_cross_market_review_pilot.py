"""Finite pilot execution on synthetic packets and injected senders only.

No credential file, network, original PDF, production registration or model is used.
"""

import json
import urllib.error
from copy import deepcopy

import cross_market_review_transport_20260927 as transport
import cross_market_source_review_20260926 as core
import pytest
import run_cross_market_review_pilot_20260927 as pilot


def packet(number):
    return core.build_packets(
        dict(
            raw_object_id=f"synthetic-{number}",
            sha256="a" * 64,
            original_url="https://example.invalid/source.pdf",
        ),
        dict(path="/unused-text.json", sha256="b" * 64, bytes=1),
        [dict(page=1, text=f"Synthetic original revenue text {number}. 全部原文。")],
    )[0]


def envelope(body, *, content=None, request_id="synthetic-provider-id"):
    view = json.loads(body["messages"][1]["content"])
    payload = dict(
        packet_id=view["packet_id"],
        segments_reviewed=[s["segment_id"] for s in view["segments"]],
        findings=[],
        uncertainties=[],
    )
    return core.base.encode(
        dict(
            id=request_id,
            model=body["model"],
            usage=dict(prompt_tokens=8, completion_tokens=4, total_tokens=12),
            choices=[
                dict(
                    finish_reason="stop",
                    message=dict(content=json.dumps(payload) if content is None else content),
                )
            ],
        )
    )


@pytest.fixture
def setup_pilot(tmp_path, monkeypatch):
    output = tmp_path / "new-pilot"
    parent_root = tmp_path / "untouched-parent"
    monkeypatch.setattr(core.base, "RAW", tmp_path)
    monkeypatch.setattr(pilot, "RAW", output)
    monkeypatch.setattr(pilot.materials, "ref", core.ref)
    packets = [packet(i) for i in range(6)]
    rows = []
    for i, value in enumerate(packets):
        path = parent_root / "packets" / f"{i}.json"
        core.base.write(path, value)
        rows.append(dict(packet_id=value["id"], reference=core.ref(path)))
    parent = core.base.record("cross_market_source_review_protocol", API_authorized=False)
    manifest = core.base.record(
        "cross_market_source_review_packet_manifest",
        protocol_id=parent["id"],
        packets=rows,
        proposed_attempt_cap=24,
        API_authorized=False,
    )
    approval = core.base.record(
        "cross_market_source_review_budget_approval",
        protocol_id=parent["id"],
        packet_manifest_id=manifest["id"],
        approved=True,
        approved_by="synthetic-test",
        approval_record="Synthetic bounded fixture, not actual API permission",
        maximum_API_attempts=10,
        maximum_attempts_per_job=core.MAX_ATTEMPTS_PER_JOB,
        maximum_output_tokens_per_attempt=4096,
        model_by_lane=transport.MODELS,
        provider_contract_verified=True,
        provider_contract_evidence={"synthetic": True},
    )
    references = {}
    for name, value in (("material_protocol", parent), ("material_manifest", manifest)):
        path = parent_root / f"{name}.json"
        core.base.write(path, value)
        references[name] = core.ref(path)
    requests = []
    for value, row in zip(packets[:5], rows[:5], strict=False):
        for lane in core.LANES:
            view, rendered, _ = pilot.request_for(value, row["reference"], lane)
            requests.append(
                dict(
                    packet_id=value["id"],
                    lane=lane,
                    projection_id=view["id"],
                    request_sha256=core.base.sha(rendered.body),
                    request_bytes=len(rendered.body),
                )
            )
    plan = dict(
        id="synthetic-pilot-plan",
        selected_packets=rows[:5],
        requests=requests,
        references=references,
    )
    return dict(
        output=output,
        parent_root=parent_root,
        packets=packets,
        rows=rows,
        parent=parent,
        manifest=manifest,
        approval=approval,
        plan=plan,
    )


def inject_sender(monkeypatch, sender):
    real_provider = transport.Provider
    monkeypatch.setattr(
        transport, "Provider", lambda output, key: real_provider(output, key, sender=sender)
    )


def call_job(data, number=0, lane="discovery"):
    return pilot.run_job(
        data["plan"],
        data["parent"],
        data["manifest"],
        data["approval"],
        data["rows"][number],
        lane,
        "SYNTHETIC_SECRET_NOT_A_REAL_KEY",
    )


def test_fixed_selection_is_four_lowest_ids_plus_largest_packet_not_outcomes():
    rows = [dict(packet_id=f"p:{i:05}", reference=dict(bytes=i + 1)) for i in range(6099)]
    assert [r["packet_id"] for r in pilot.select_packets(dict(packets=list(reversed(rows))))] == [
        "p:00000",
        "p:00001",
        "p:00002",
        "p:00003",
        "p:06098",
    ]
    with pytest.raises(ValueError, match="fixed_five"):
        pilot.select_packets(dict(packets=rows[:-1]))
    rows[0]["reference"]["bytes"] = 10000
    with pytest.raises(ValueError, match="fixed_five"):
        pilot.select_packets(dict(packets=rows))


def test_request_exact_final_wire_body_includes_guarded_options(setup_pilot):
    data = setup_pilot
    _, frozen, body = pilot.request_for(
        data["packets"][0], data["rows"][0]["reference"], "discovery"
    )
    assert frozen.body == transport.request_bytes(body) == core.base.encode(body)
    assert body["thinking"] == {"type": "disabled"} and body["stream"] is False
    assert len(frozen.body) <= transport.MAX_REQUEST_BYTES
    assert body["max_tokens"] == 4096


@pytest.mark.parametrize("mutation", ["model", "stream", "thinking", "extra", "oversize"])
def test_transport_contract_rejects_undeclared_or_oversized_body(setup_pilot, mutation):
    data = setup_pilot
    _, _, body = pilot.request_for(data["packets"][0], data["rows"][0]["reference"], "discovery")
    if mutation == "extra":
        body["temperature"] = 0
    elif mutation == "oversize":
        body["messages"][1]["content"] = "汉" * transport.MAX_REQUEST_BYTES
    else:
        body[mutation] = {"model": "undeclared", "stream": True, "thinking": {"type": "enabled"}}[
            mutation
        ]
    with pytest.raises(ValueError, match="review_transport_"):
        transport.request_bytes(body)


def test_ten_jobs_reserve_before_send_once_and_leave_parent_namespace_unchanged(
    setup_pilot,
    monkeypatch,
):
    data = setup_pilot
    parent_before = {p: p.read_bytes() for p in data["parent_root"].rglob("*.json")}
    original_raw, original_payload = core.RAW, core.request_payload
    sent = []

    def sender(raw, key):
        assert key == "SYNTHETIC_SECRET_NOT_A_REAL_KEY"
        assert len(list((data["output"] / "API_attempts").glob("*.json"))) == len(sent) + 1
        assert core.base.sha(raw) in {r["request_sha256"] for r in data["plan"]["requests"]}
        sent.append(raw)
        return envelope(json.loads(raw)), "safe-header-id"

    inject_sender(monkeypatch, sender)
    results = [call_job(data, i, lane) for i in range(5) for lane in core.LANES]
    assert len(sent) == len(results) == 10
    assert len(list((data["output"] / "API_attempts").glob("*.json"))) == 10
    assert all(r["attempt"] == 1 and r["passed"] is False for r in results)
    assert all(r["status"] == "ASSISTANCE_RESPONSE_SAVED_NOT_ADMITTED" for r in results)
    for i in range(5):
        for lane in core.LANES:
            assert call_job(data, i, lane)["attempt"] == 1
    assert len(sent) == 10
    ns = pilot.isolated.isolated_namespace(core, RAW=data["output"])
    with pytest.raises(ValueError, match="attempt_budget_exhausted"):
        ns["run_scan_attempt"](
            data["parent"],
            data["manifest"],
            data["packets"][5],
            "discovery",
            data["approval"],
            lambda _: pytest.fail("eleventh send"),
        )
    assert core.RAW == original_raw and core.request_payload is original_payload
    assert all(p.read_bytes() == value for p, value in parent_before.items())
    assert not list(data["parent_root"].rglob("*attempt*"))


@pytest.mark.parametrize("failure", ["HTTP", "invalid_JSON", "invalid_locator"])
def test_failed_physical_attempt_is_charged_and_never_replayed(setup_pilot, monkeypatch, failure):
    data = setup_pilot
    sent = []

    def sender(raw, key):
        sent.append(raw)
        if failure == "HTTP":
            raise urllib.error.HTTPError("https://example.invalid/" + key, 429, key, {}, None)
        if failure == "invalid_JSON":
            return b"not JSON", "safe-id"
        return envelope(json.loads(raw), content="{}"), "safe-id"

    inject_sender(monkeypatch, sender)
    first = call_job(data)
    second = call_job(data)
    assert first == second and first["status"] == "SCAN_ATTEMPT_FAILED_NOT_REFUNDED"
    assert len(sent) == 1 and len(list((data["output"] / "API_attempts").glob("*.json"))) == 1
    assert "SYNTHETIC_SECRET_NOT_A_REAL_KEY" not in "".join(
        p.read_text() for p in data["output"].rglob("*.json")
    )


def test_unsettled_reservation_cannot_replay_after_process_interruption(setup_pilot, monkeypatch):
    data = setup_pilot
    key = core.job_key(data["packets"][0]["id"], "discovery")
    core.base.write(data["output"] / "API_attempts" / (key + ".1.json"), {"reserved": True})
    inject_sender(monkeypatch, lambda *_: pytest.fail("unsettled attempt must not send"))
    with pytest.raises(ValueError, match="unsettled_attempt_no_replay"):
        call_job(data)


def test_changed_packet_bytes_fail_before_transport(setup_pilot, monkeypatch):
    data = setup_pilot
    changed = deepcopy(data["rows"][0])
    changed["reference"]["sha256"] = "wrong"
    inject_sender(monkeypatch, lambda *_: pytest.fail("changed parent must not send"))
    with pytest.raises(ValueError, match="parent_bytes"):
        pilot.run_job(
            data["plan"],
            data["parent"],
            data["manifest"],
            data["approval"],
            changed,
            "discovery",
            "synthetic",
        )
    assert not list(data["output"].rglob("*attempt*"))


def test_save_cannot_escape_pilot_root(setup_pilot):
    with pytest.raises(ValueError, match="output_root"):
        pilot.save(setup_pilot["parent_root"] / "forbidden.json", {})


def test_redirect_is_rejected_without_followup_request():
    with pytest.raises(ValueError, match="redirect_forbidden"):
        transport.NoRedirect().redirect_request(
            None, None, 307, "redirect", {}, "https://example.invalid/other"
        )


def test_provider_redacts_credential_in_response_body_and_request_header(setup_pilot, monkeypatch):
    data = setup_pilot

    def sender(raw, key):
        return envelope(json.loads(raw), request_id="body-echo-" + key), "header-echo-" + key

    inject_sender(monkeypatch, sender)
    result = call_job(data)
    assert result["status"] == "ASSISTANCE_RESPONSE_SAVED_NOT_ADMITTED"
    persisted = "".join(p.read_text() for p in data["output"].rglob("*.json"))
    assert "SYNTHETIC_SECRET_NOT_A_REAL_KEY" not in persisted
    assert "[REDACTED_CREDENTIAL]" in persisted


def test_sender_receives_exact_bytes_once_and_no_proxy_or_redirect_retry(monkeypatch):
    calls = []

    class Response:
        status = 200
        headers = {"x-request-id": "test-id"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, maximum):
            assert maximum == transport.MAX_RESPONSE_BYTES + 1
            return b"{}"

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            assert request.full_url == transport.ENDPOINT and request.get_method() == "POST"
            assert request.data == b"synthetic exact bytes" and timeout == 120
            return Response()

    def build(*handlers):
        assert handlers[0].proxies == {} and isinstance(handlers[1], transport.NoRedirect)
        return Opener()

    monkeypatch.setattr(transport.urllib.request, "build_opener", build)
    assert transport.one_post(b"synthetic exact bytes", "fake") == (b"{}", "test-id")
    assert len(calls) == 1
