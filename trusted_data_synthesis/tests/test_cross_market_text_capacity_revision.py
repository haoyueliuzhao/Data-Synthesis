"""Only wire capacity changes; original namespace and semantic body stay unchanged."""

import json

import pytest
import run_cross_market_text_capacity_revision_20260927 as m


def request(size):
    return dict(
        model="deepseek-v4-pro",
        messages=[dict(role="system", content="Review"), dict(role="user", content="x" * size)],
        max_tokens=4096,
        response_format={"type": "json_object"},
        thinking={"type": "disabled"},
        stream=False,
    )


def test_larger_wire_body_is_exact_and_original_guard_remains():
    source = request(144747)
    with pytest.raises(ValueError, match="request_bytes"):
        m.original.transport.request_bytes(source)
    transport = m.transport_namespace({"synthetic": True})
    assert transport.request_bytes(source) == m.base.encode(source)
    assert m.original.transport.MAX_REQUEST_BYTES == 131072
    with pytest.raises(ValueError, match="request_bytes"):
        transport.request_bytes(request(m.MAX_REQUEST_BYTES))


def test_other_request_contracts_are_not_relaxed():
    transport = m.transport_namespace({"synthetic": True})
    source = request(10)
    source["max_tokens"] = 8192
    with pytest.raises(ValueError, match="fixed_request_contract"):
        transport.request_bytes(source)


def test_provider_records_revision_and_exact_body_before_one_post(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    reference = {"synthetic": "capacity-only"}
    transport = m.transport_namespace(reference)
    source = request(144747)
    seen = []

    def sender(body, key):
        seen.append(body)
        assert m.base.read(tmp_path / "attempt/capacity_revision_binding.json") == reference
        return m.base.encode(
            dict(
                model="deepseek-v4-pro",
                id="synthetic",
                usage=dict(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                choices=[
                    dict(finish_reason="stop", message=dict(content=json.dumps({"ok": True})))
                ],
            )
        ), None

    result = transport.Provider(tmp_path / "attempt", "SYNTHETIC_ONLY", sender=sender)(source)
    assert result["finish_reason"] == "stop"
    assert seen == [m.base.encode(source)]
