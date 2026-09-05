"""Replay the one stored public session; every callback and dispatch is forbidden."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol import engine, fixture, models
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.independent import (
    audit_records,
    audit_registration,
    audit_session,
    read_session_records,
)

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / (
    "trusted_data_synthesis/artifacts/qa_reasoning_part_whole_share/"
    "finance_qa_vnext_part_whole_share_dual_support_preflight_v1_20260905"
)
FORMAL = ROOT / (
    "trusted_data_synthesis/artifacts/qa_reasoning_share_public_protocol/"
    "finance_qa_vnext_share_public_state_proposal_action_observation_update_"
    "protocol_preflight_v1_20260905"
)


@pytest.fixture(autouse=True)
def forbid_callback_dispatch_and_host_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("independent tests may only read and replay stored session bytes")

    monkeypatch.setattr(engine.ProtocolEngine, "exchange", forbidden)
    monkeypatch.setattr(fixture.PublicRequestFixture, "generate", forbidden)
    monkeypatch.setattr(engine, "prepare", forbidden)
    monkeypatch.setattr(engine, "preview", forbidden)
    monkeypatch.setattr(engine, "admit_inputs", forbidden)
    monkeypatch.setattr(models, "parse_submission", forbidden)
    for executor in (
        engine.RelationSumExecutor,
        engine.ShareRatioExecutor,
        engine.ScalePercentExecutor,
    ):
        monkeypatch.setattr(executor, "execute", forbidden)


@pytest.fixture(scope="module")
def frozen() -> dict[str, Any]:
    def read(root: Path, name: str) -> Any:
        return json.loads((root / name).read_bytes())

    actual = read_session_records(FORMAL / "session")
    return {
        "context": read(FORMAL, "public_context.json"),
        "protocol": read(FORMAL, "protocol_contract.json"),
        "source": read(PARENT, "source_binding.json"),
        "legacy": read(PARENT, "contract.json"),
        "binding": read(FORMAL, "generator_binding.json"),
        "authority": read(FORMAL, "source_authority.json"),
        "registration": read(FORMAL, "generator_registration.json"),
        "registration_audit": read(FORMAL, "registration_audit.json"),
        "independent": read(FORMAL, "independent_validation.json"),
        **actual,
    }


def _arguments(frozen: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(frozen[key] for key in ("context", "protocol", "source", "legacy", "binding"))


def _renew(kind: str, obj: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return models.record(
        kind,
        **(
            {key: value for key, value in obj.items() if key not in {"id", "schema_version"}}
            | changes
        ),
    )


def _rehash_changed_exchange(bundle: dict[str, Any], regenerate_raw: bool = True) -> dict[str, Any]:
    """Prospective record control only: renew changed objects and producer references."""
    result = copy.deepcopy(bundle)
    replacements: dict[str, dict[str, Any]] = {}
    identifiers: dict[str, str] = {}

    def renew(name: str, **changes: Any) -> None:
        old = result[name]
        kind = {"post_state": "public_state", "request": "generator_request"}.get(name, name)
        new = _renew(kind, old, **changes)
        replacements[old["id"]] = new
        identifiers[old["id"]] = new["id"]
        result[name] = new

    renew("request")
    submission = result["submission"]
    raw = (
        canonical_json_bytes(submission["parsed"]).decode("utf-8")
        if regenerate_raw
        else submission["raw_public_json"]
    )
    payload = raw.encode("utf-8")
    renew(
        "generator_turn",
        request_id=result["request"]["id"],
        response_sha256=hashlib.sha256(payload).hexdigest(),
        response_byte_count=len(payload),
    )
    renew(
        "submission",
        request_id=result["request"]["id"],
        generator_turn_id=result["generator_turn"]["id"],
        raw_public_json=raw,
        response_sha256=result["generator_turn"]["response_sha256"],
        response_byte_count=result["generator_turn"]["response_byte_count"],
    )
    payload = canonical_json_bytes(result["submission"])
    renew(
        "receipt",
        request_id=result["request"]["id"],
        submission_id=result["submission"]["id"],
        submission_sha256=hashlib.sha256(payload).hexdigest(),
        submission_byte_count=len(payload),
    )
    if result["execution"] is not None:
        renew(
            "execution",
            submission_id=result["submission"]["id"],
            generator_turn_id=result["generator_turn"]["id"],
        )
    if result["observation"] is not None:
        renew(
            "observation",
            execution_id=result["execution"]["id"],
            action_submission_id=result["submission"]["id"],
        )
    if result["claim"] is not None:
        observation_id = result["claim"]["observation_id"]
        renew(
            "claim",
            observation_id=identifiers.get(observation_id, observation_id),
            update_submission_id=result["submission"]["id"],
            generator_turn_id=result["generator_turn"]["id"],
        )
    if result["final"] is not None:
        renew(
            "final",
            submission_id=result["submission"]["id"],
            generator_turn_id=result["generator_turn"]["id"],
        )

    def replace(value: Any) -> Any:
        if isinstance(value, dict):
            if value.get("id") in replacements:
                return copy.deepcopy(replacements[value["id"]])
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        return identifiers.get(value, value) if isinstance(value, str) else value

    state = replace(result["post_state"])
    result["post_state"] = _renew("public_state", state)
    renew(
        "event",
        post_state_id=result["post_state"]["id"],
        **{
            name + "_id": result[name]["id"] if result[name] is not None else None
            for name in (
                "request",
                "generator_turn",
                "submission",
                "receipt",
                "execution",
                "observation",
                "claim",
                "final",
            )
        },
    )
    return result


def test_actual_session_and_registration_replay_exactly(frozen: dict[str, Any]) -> None:
    report = audit_session(*_arguments(frozen), FORMAL / "session")
    assert canonical_json_bytes(report) == canonical_json_bytes(frozen["independent"])
    assert report["protocol_valid"] and report["qa_valid"] and report["qualified"]
    assert report["generator_callbacks"] == report["raw_public_responses_replayed"] == 7
    assert report["observed_action_count"] == report["observed_update_count"] == 3
    assert report["accepted_claim_count"] == 3
    assert report["candidate_runtime_executions"] == report["provider_calls"] == 0
    assert report["old_quotient_recomputed"] is False
    assert report["model_reachability"] == "NOT_MEASURED"
    registration = audit_registration(
        frozen["authority"], frozen["binding"], frozen["registration"]
    )
    assert canonical_json_bytes(registration) == canonical_json_bytes(frozen["registration_audit"])
    assert registration["passed"] is True
    assert registration["callback_executed_by_this_check"] is False
    assert registration["full_runtime_closure_asserted"] is False


def test_claims_remain_pending_until_separate_generator_update(frozen: dict[str, Any]) -> None:
    events = frozen["events"]
    assert [event["submission"]["parsed"]["kind"] for event in events] == [
        "action",
        "update",
        "action",
        "update",
        "action",
        "update",
        "final",
    ]
    for position in (0, 2, 4):
        action, update = events[position : position + 2]
        assert action["claim"] is None
        assert action["post_state"]["phase"] == "update"
        assert action["post_state"]["pending_observation"] == action["observation"]
        assert len(action["post_state"]["accepted_claims"]) == position // 2
        assert update["generator_turn"]["id"] != action["generator_turn"]["id"]
        assert update["request"]["state"] == action["post_state"]
        assert update["request"]["allowed_submission_kinds"] == ["update"]
        submitted = update["submission"]["parsed"]
        assert submitted["observation_id"] == action["observation"]["id"]
        assert submitted["proposed_claim"] == action["observation"]["output"]
        assert update["claim"]["proposition"] == submitted["proposed_claim"]
        assert update["claim"]["generator_turn_id"] == update["generator_turn"]["id"]
        assert update["post_state"]["pending_observation"] is None
    for event in events:
        assert event["submission"]["host_repairs"] == []
        assert event["generator_turn"]["host_supplied_response"] is False
        assert event["generator_turn"]["generator_binding_id"] == frozen["binding"]["id"]


@pytest.mark.parametrize(
    "field", ["source_authority_id", "generator_binding_id", "fixture_source_member"]
)
def test_rehashed_registration_tampering_is_rejected(frozen: dict[str, Any], field: str) -> None:
    registration = copy.deepcopy(frozen["registration"])
    if field == "fixture_source_member":
        registration[field]["sha256"] = "0" * 64
    else:
        registration[field] = "unknown:" + "0" * 64
    registration = _renew("generator_registration", registration)
    report = audit_registration(frozen["authority"], frozen["binding"], registration)
    assert report["passed"] is False
    assert report["errors"][0]["stage"] == "independent.generator_registration"


@pytest.mark.parametrize(
    ("attack", "expected_stage"),
    [
        ("wrong_proposed_claim", "independent.admission_receipt"),
        ("cross_observation", "independent.admission_receipt"),
        ("silent_parser_repair", "independent.raw_response"),
        ("caller_model_origin", "independent.generator_turn"),
        ("substituted_execution_input", "independent.actual_execution"),
        ("host_automatic_accept", "independent.actual_claim"),
        ("hidden_next_action", "independent.generator_request"),
    ],
)
def test_rehashed_semantic_tampering_fails_beyond_content_ids(
    frozen: dict[str, Any], attack: str, expected_stage: str
) -> None:
    index = (
        1 if attack in {"wrong_proposed_claim", "cross_observation", "silent_parser_repair"} else 0
    )
    events = copy.deepcopy(frozen["events"][: index + 1])
    changed = events[index]
    parsed = changed["submission"]["parsed"]
    if attack == "wrong_proposed_claim":
        parsed["proposed_claim"]["value"] = "21814"
    elif attack == "cross_observation":
        parsed["observation_id"] = "public_share_protocol_observation:" + "0" * 64
        parsed["public_basis"]["observation_refs"] = [parsed["observation_id"]]
    elif attack == "silent_parser_repair":
        parsed["proposed_claim"]["value"] = "21814"
    elif attack == "caller_model_origin":
        changed["generator_turn"]["origin"] = "model"
    elif attack == "substituted_execution_input":
        changed["execution"]["inputs"][1]["ref_id"] = frozen["source"]["evidence"]["total"]["id"]
    elif attack == "host_automatic_accept":
        changed["claim"] = copy.deepcopy(frozen["events"][1]["claim"])
        changed["post_state"]["accepted_claims"] = [copy.deepcopy(changed["claim"])]
    else:
        changed["request"]["instructions"] += " Host selected next action: relation_sum."
    events[index] = _rehash_changed_exchange(
        changed, regenerate_raw=attack != "silent_parser_repair"
    )
    report = audit_records(*_arguments(frozen), frozen["initial_state"], events)
    assert report["protocol_valid"] is False and report["qualified"] is False
    assert report["first_failure"]["stage"] == expected_stage
    assert report["first_failure"]["stage"] != "independent.record_identity"


@pytest.mark.parametrize("attack", ["missing_member", "extra_file", "fsync_order"])
def test_actual_file_membership_and_fsync_order_fail_closed(
    frozen: dict[str, Any], tmp_path: Path, attack: str
) -> None:
    target = tmp_path / "session"
    shutil.copytree(FORMAL / "session", target)
    manifest = json.loads((target / "session_manifest.json").read_bytes())
    if attack == "missing_member":
        (target / manifest["events"][0]["receipt"]).unlink()
    elif attack == "extra_file":
        (target / "unregistered.json").write_bytes(b"{}")
    else:
        writes = manifest["write_events"]
        writes[6:8], writes[10:12] = writes[10:12], writes[6:8]
        for ordinal, event in enumerate(writes, 1):
            event["event_ordinal"] = ordinal
        manifest = _renew("session_manifest", manifest)
        (target / "session_manifest.json").write_bytes(canonical_json_bytes(manifest))
    report = audit_session(*_arguments(frozen), target)
    assert report["protocol_valid"] is False and report["persisted_artifact_validation"] is False
    if attack == "fsync_order":
        assert report["first_failure"]["stage"] == "independent.pre_dispatch_order"
    elif attack == "extra_file":
        assert report["first_failure"]["stage"] == "independent.artifact_inventory"


def test_empty_initial_state_replay_is_not_a_qualified_solution(frozen: dict[str, Any]) -> None:
    report = audit_records(*_arguments(frozen), frozen["initial_state"], [])
    assert report["protocol_valid"] is True
    assert report["qa_valid"] is None and report["qualified"] is False
    assert report["generator_callbacks"] == report["accepted_claim_count"] == 0


def test_missing_actual_observation_cannot_be_backfilled(frozen: dict[str, Any]) -> None:
    events = copy.deepcopy(frozen["events"][:1])
    events[0]["observation"] = None
    events[0] = _rehash_changed_exchange(events[0])
    report = audit_records(*_arguments(frozen), frozen["initial_state"], events)
    assert report["protocol_valid"] is False
    assert report["first_failure"]["stage"] == "independent.actual_observation"
