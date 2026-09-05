"""Real-source paths and adversarial judgments through the single public QA runtime."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import catalog as domain
from trusted_synthesis.domains.finance.qa_vnext.callbacks import (
    ExternalJSONCallback,
    PublicFixtureCallback,
    action_response,
    update_response,
)
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import (
    ProgramTaskAdapter,
    public_program_answer,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, contract, parse
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore, PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import (
    SHARE_FAMILY,
    SHARE_OPERATIONS,
    ShareTaskAdapter,
    add_share_operations,
    load_share_source,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import PARENT

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ACTION_COUNTS = {
    "fact_retrieval": 1,
    "registered_cross_metric_comparison": 1,
    "temporal_growth": 3,
    "temporal_average": 4,
    "temporal_absolute_change": 3,
    "registered_ratio": 3,
    "derived_growth_absolute_spread": 8,
    "share_disclosed_total": 2,
    "share_reconstructed_total": 3,
}


def test_durability_includes_new_directory_entries_not_only_the_leaf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[Path] = []
    actual_sync = DurableStore._sync

    def sync(path: Path) -> None:
        actual_sync(path)
        synced.append(path)

    monkeypatch.setattr(DurableStore, "_sync", staticmethod(sync))
    root = tmp_path / "new_parent" / "session"
    store = DurableStore(root)
    assert synced == [tmp_path, root.parent]
    synced.clear()
    store.write("turns/nested/response.txt", b"callback-owned bytes")
    assert synced == [root, root / "turns", root / "turns/nested"]
    assert (root / "turns/nested/response.txt").read_bytes() == b"callback-owned bytes"


@pytest.fixture(scope="module")
def registered_sources() -> Iterator[tuple[Any, dict[str, Any]]]:
    paths = [ROOT / domain.ARCHIVE_PATH]
    for directory in (domain.FROZEN_SOURCE_DIRECTORY, PARENT):
        paths.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())
    snapshots = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    registry = domain.catalog_operation_registry()
    add_share_operations(registry)
    catalog = domain.FinanceQACatalog(registry)
    _, legacy, _ = load_share_source(ROOT)
    catalog.register_adapter_family(
        SHARE_FAMILY,
        "source_explicit_share_obligations.v2",
        SHARE_OPERATIONS,
        contract_id=legacy["id"],
        version="2.0.0",
    )
    cases, _ = catalog.frozen_source_cases(ROOT)
    by_type = {case.task_type: case for case in cases}
    assert set(by_type) == {key for key in SOURCE_ACTION_COUNTS if not key.startswith("share_")}
    yield catalog, by_type
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths} == snapshots


def adapter_for(sources: tuple[Any, dict[str, Any]], path: str) -> Any:
    catalog, cases = sources
    if path.startswith("share_"):
        return ShareTaskAdapter(ROOT, catalog.registry, catalog.resolve(SHARE_FAMILY).receipt)
    return ProgramTaskAdapter(cases[path], catalog.registry)


def runtime_for(
    sources: tuple[Any, dict[str, Any]],
    directory: Path,
    path: str = "share_disclosed_total",
    **bounds: int,
) -> PublicQARuntime:
    preference = path.removeprefix("share_") if path.startswith("share_") else "disclosed_total"
    return PublicQARuntime(
        adapter_for(sources, path),
        PublicFixtureCallback(support_preference=preference),
        directory,
        **bounds,
    )


def fixture_step(runtime: PublicQARuntime) -> dict[str, Any]:
    return runtime.step(runtime.callback.generate(runtime.request()))


def assert_rejected(
    runtime: PublicQARuntime, raw: bytes, error: str, *, actions: int = 0
) -> dict[str, Any]:
    claims, pending = copy.deepcopy(runtime.claims), copy.deepcopy(runtime.pending)
    event = runtime.step(raw)
    assert event["receipt"]["admitted"] is False
    assert event["receipt"]["error_code"] == error
    assert event["submission"]["host_repairs"] == []
    assert event["receipt"]["no_host_semantic_repair"] is True
    assert not {"execution", "observation", "claim", "final"} & set(event)
    assert runtime.actions == actions
    assert runtime.claims == claims and runtime.pending == pending
    assert (runtime.store.root / f"turns/{event['sequence']:03d}_response.txt").read_bytes() == raw
    return event


@pytest.mark.parametrize("path,action_count", SOURCE_ACTION_COUNTS.items())
def test_all_nine_real_source_paths_use_the_same_callback_runtime(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path, path: str, action_count: int
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session", path)
    result = runtime.run()
    assert result["final"] is not None
    assert result["final"]["qa_validation"]["qa_valid"] is True
    assert result["final"]["qa_validation"]["source_valid"] is True
    assert result["final"]["qa_validation"]["reference_program_used_for_callback"] is False
    assert result["terminal_state"]["last_feedback"]["code"] == "complete"
    assert result["terminal_state"]["action_count"] == action_count
    assert result["terminal_state"]["update_count"] == action_count
    assert len(result["claims"]) == action_count
    assert len(result["events"]) == 2 * action_count + 1
    assert [event["parsed"]["kind"] for event in result["events"]] == [
        item for _ in range(action_count) for item in ("action", "update")
    ] + ["final"]
    assert result["callback_binding"]["origin"] == "fixture"
    assert result["callback_binding"]["model_sample"] is False
    assert result["callback_binding"]["provider_calls"] == 0
    assert result["accepted_claim_revision_supported"] is False
    for event in result["events"]:
        assert event["receipt"]["admitted"] is True
        assert event["submission"]["host_repairs"] == []
        kind = event["parsed"]["kind"]
        if kind == "action":
            assert "claim" not in event
            assert (
                event["post_state"]["accepted_claims"]
                == event["request"]["state"]["accepted_claims"]
            )
            assert event["post_state"]["pending_observation"] == event["observation"]
            assert event["observation"]["execution_id"] == event["execution"]["id"]
            assert event["execution"]["receipt_id"] == event["receipt"]["id"]
            assert event["observation"]["action_submission_id"] == event["submission"]["id"]
            assert (
                event["parsed"]["decision"]["expected_effect"]
                == event["observation"]["selected_action"]["expected_effect"]
            )
        elif kind == "update":
            observation = event["request"]["state"]["pending_observation"]
            assert event["parsed"]["proposed_claim"] == observation["proposition"]
            assert event["claim"]["observation_id"] == observation["id"]
            assert event["post_state"]["pending_observation"] is None
    if path.startswith("share_"):
        assert result["final"]["answer"]["result"] == {"value": "93.508458", "unit": "percent"}
        source = runtime.adapter.source["evidence"]
        names = {"freight", "total"} if action_count == 2 else {"freight", "other", "part_whole"}
        assert set(result["final"]["answer"]["citations"]) == {source[name]["id"] for name in names}
    manifest = json.loads((runtime.store.root / "manifest.json").read_bytes())
    assert manifest["self_excluding"] is True
    assert "manifest.json" not in {member["path"] for member in manifest["members"]}
    for member in manifest["members"]:
        content = (runtime.store.root / member["path"]).read_bytes()
        assert member["sha256"] == hashlib.sha256(content).hexdigest()
        assert member["bytes"] == len(content)


def test_dispatch_observes_exact_persisted_raw_action_and_admission_receipt(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session")
    # Noncanonical spacing is deliberately retained as the callback's original bytes.
    raw = json.dumps(json.loads(runtime.callback.generate(runtime.request())), indent=3).encode()
    execute = runtime.adapter.execute
    calls = []

    def inspect_then_execute(prepared: Any) -> dict[str, Any]:
        assert (runtime.store.root / "turns/000_response.txt").read_bytes() == raw
        receipt = json.loads((runtime.store.root / "turns/000_receipt.json").read_bytes())
        assert receipt["admitted"] is True
        assert runtime.claims == [] and runtime.pending is None
        kinds = [event["kind"] for event in runtime.store.events]
        assert kinds[-2:] == ["pre_dispatch_readback", "execution_dispatch"]
        receipt_events = [
            event["kind"]
            for event in runtime.store.events
            if event.get("path") == "turns/000_receipt.json"
        ]
        assert receipt_events == ["file_fsync", "directory_fsync"]
        calls.append(prepared)
        return execute(prepared)

    monkeypatch.setattr(runtime.adapter, "execute", inspect_then_execute)
    event = runtime.step(raw)
    assert len(calls) == 1 and event["receipt"]["admitted"] is True
    assert event["submission"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert event["submission"]["raw_bytes"] == len(raw)
    markers = [event["kind"] for event in runtime.store.events if event.get("sequence") == 0]
    assert markers == ["pre_dispatch_readback", "execution_dispatch", "execution_return"]


@pytest.mark.parametrize("path", SOURCE_ACTION_COUNTS)
def test_request_and_admission_preparation_do_not_execute_numeric_kernels(
    registered_sources: tuple[Any, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session", path)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("numeric executor called while preparing public choices")

    for row in runtime.adapter.registry.manifest():
        monkeypatch.setattr(
            runtime.adapter.registry.require(row["operator_id"]).executor, "execute", forbidden
        )
    request = runtime.request()
    assert request["available_actions"]
    for option in request["available_actions"]:
        admitted = runtime._admit(action_response(request, option), request)
        assert admitted["option"] == option
    assert runtime.actions == 0 and runtime.claims == []


ACTION_MUTATIONS = [
    (("state_id",), "stale", "admission.current_state"),
    (("decision", "candidate_action_ids"), "subset", "admission.alternative_set"),
    (("decision", "candidate_action_ids"), "duplicate", "admission.alternative_set"),
    (("decision", "selected_action_id"), "invented", "admission.selected_action"),
    (("operation",), "registered_compare", "admission.selected_action_content"),
    (("inputs",), [], "admission.selected_action_content"),
    (("parameters",), {"host_must_fill": True}, "admission.selected_action_content"),
    (("decision", "obligation_id"), "percent", "admission.public_judgment"),
    (("decision", "subgoal"), "derive_quantity", "admission.public_judgment"),
    (("decision", "selection_rule"), "dependency_ready", "admission.public_judgment"),
    (("decision", "basis", "evidence_refs"), [], "admission.public_judgment"),
    (("decision", "basis", "claim_refs"), ["invented_claim"], "admission.public_judgment"),
    (
        ("decision", "expected_effect", "establishes_obligation"),
        "percent",
        "admission.public_judgment",
    ),
    (("decision", "expected_effect", "output_schema"), "comparison", "admission.public_judgment"),
    (("decision", "unresolved_uncertainty_refs"), ["invented"], "admission.public_judgment"),
    (("decision", "private_chain_of_thought"), "not requested", "submission.schema"),
    (("decision", "basis", "relation"), "I believe this is useful", "submission.schema"),
    (("decision",), None, "submission.schema"),
]


def replace_path(value: dict[str, Any], keys: tuple[str, ...], replacement: Any) -> None:
    parent = value
    for key in keys[:-1]:
        parent = parent[key]
    parent[keys[-1]] = replacement


@pytest.mark.parametrize("keys,replacement,error", ACTION_MUTATIONS)
def test_callback_action_judgments_are_checked_before_any_dispatch(
    registered_sources: tuple[Any, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    keys: tuple[str, ...],
    replacement: Any,
    error: str,
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session")
    payload = json.loads(runtime.callback.generate(runtime.request()))
    if replacement == "subset":
        replacement = payload["decision"]["candidate_action_ids"][:1]
    elif replacement == "duplicate":
        replacement = payload["decision"]["candidate_action_ids"] * 2
    replace_path(payload, keys, replacement)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("rejected Action reached numeric dispatch")

    monkeypatch.setattr(runtime.adapter, "execute", forbidden)
    assert_rejected(runtime, canonical_json_bytes(payload), error)
    assert not any(event["kind"] == "execution_dispatch" for event in runtime.store.events)


@pytest.mark.parametrize(
    "raw,error",
    [
        (b'{"kind":"action","kind":"final"}', "json.duplicate_key"),
        (b'{"kind":"action","parameters":{"x":1,"x":2}}', "json.duplicate_key"),
        (b'{"kind":"action","parameters":{"x":NaN}}', "json.non_finite_number"),
        (b'{"kind":"action","parameters":{"x":Infinity}}', "json.non_finite_number"),
        (b"[]", "submission.object"),
        (b'{"kind":"retract"}', "submission.kind"),
        (b"not JSON", "submission.schema"),
        (b"\xff", "submission.schema"),
        (b" " * 1_048_577, "submission.byte_bound"),
    ],
)
def test_raw_invalid_submissions_remain_unrepaired_and_have_no_execution(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path, raw: bytes, error: str
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session")
    assert_rejected(runtime, raw, error)


def test_pending_observation_cannot_unlock_dependency_or_be_submitted_as_final(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session")
    action = json.loads(runtime.callback.generate(runtime.request()))
    fixture_step(runtime)
    request = runtime.request()
    assert runtime.claims == []
    assert request["available_actions"] == [] and request["final_claim_ids"] == []
    assert request["state"]["phase"] == "update"
    assert not any(
        option["operation"] == "scale_percent" for option in runtime.adapter.offers(runtime.claims)
    )
    action["state_id"] = request["state"]["id"]
    assert_rejected(
        runtime, canonical_json_bytes(action), "admission.action_phase_budget", actions=1
    )
    final = {
        "kind": "final",
        "state_id": runtime.state()["id"],
        "answer_claim_id": runtime.pending["id"],
        "result": {"value": "93.508458", "unit": "percent"},
        "citations": runtime.pending["proposition"]["lineage"],
    }
    assert_rejected(
        runtime, canonical_json_bytes(final), "admission.final_accepted_claim", actions=1
    )
    fixture_step(runtime)
    assert len(runtime.claims) == 1 and runtime.pending is None
    assert [option["operation"] for option in runtime.request()["available_actions"]] == [
        "scale_percent"
    ]


UPDATE_MUTATIONS = [
    (("observation_id",), "invented", "admission.observation_parent"),
    (("proposed_claim",), None, "admission.exact_observation_acceptance"),
    (("proposed_claim", "output", "value"), "0", "admission.exact_observation_acceptance"),
    (("proposed_claim", "lineage"), [], "admission.exact_observation_acceptance"),
    (("proposed_claim", "operation"), "scale_percent", "admission.exact_observation_acceptance"),
    (
        ("proposed_claim", "operation_contract_id"),
        "invented",
        "admission.exact_observation_acceptance",
    ),
    (("proposed_claim", "extra"), True, "admission.exact_observation_acceptance"),
    (("assessment", "evidence_refs"), [], "admission.observation_assessment"),
    (("assessment", "observation_refs"), [], "admission.observation_assessment"),
    (("assessment", "fulfills_obligation"), "percent", "admission.observation_assessment"),
    (("assessment", "relation"), "declines_observation", "admission.observation_assessment"),
    (("remaining_uncertainty_refs",), ["invented"], "admission.update_effect"),
    (("newly_enabled_obligation_ids",), [], "admission.update_effect"),
    (("next_subgoal",), "submit_final", "admission.update_effect"),
    (("disposition",), "retract", "submission.schema"),
    (("replacement_claim_id",), "invented", "submission.schema"),
]


@pytest.mark.parametrize("keys,replacement,error", UPDATE_MUTATIONS)
def test_update_requires_complete_exact_observation_and_correct_public_effect(
    registered_sources: tuple[Any, dict[str, Any]],
    tmp_path: Path,
    keys: tuple[str, ...],
    replacement: Any,
    error: str,
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session")
    fixture_step(runtime)
    payload = update_response(runtime.request())
    replace_path(payload, keys, replacement)
    assert_rejected(runtime, canonical_json_bytes(payload), error, actions=1)
    assert runtime.updates == 0


def test_real_reject_discards_only_pending_observation_and_preserves_accepted_ancestor(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session", "share_reconstructed_total")
    fixture_step(runtime)
    fixture_step(runtime)
    ancestor = copy.deepcopy(runtime.claims[0])
    assert ancestor["obligation_id"] == "total"
    fixture_step(runtime)
    rejected_observation = runtime.pending["id"]
    event = runtime.step(canonical_json_bytes(update_response(runtime.request(), "reject")))
    assert event["receipt"]["admitted"] is True and "claim" not in event
    assert runtime.claims == [ancestor] and runtime.pending is None
    assert runtime.feedback["code"] == "observation_declined"
    assert not any(
        option["operation"] == "scale_percent" for option in runtime.request()["available_actions"]
    )
    result = runtime.run()
    assert result["final"]["qa_validation"]["qa_valid"] is True
    assert len(result["claims"]) == 3
    assert result["claims"][0] == ancestor
    assert rejected_observation not in {claim["observation_id"] for claim in result["claims"]}
    assert result["terminal_state"]["action_count"] == 4
    assert result["terminal_state"]["update_count"] == 4


@pytest.mark.parametrize("field", ["result", "citations", "answer_claim_id"])
@pytest.mark.parametrize("path", ["share_disclosed_total", "registered_ratio"])
def test_final_requires_correct_answer_complete_citations_and_accepted_answer_claim(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path, path: str, field: str
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session", path)
    while not runtime.request()["final_claim_ids"]:
        fixture_step(runtime)
    payload = json.loads(runtime.callback.generate(runtime.request()))
    payload[field] = (
        {"value": "-12345"} if field == "result" else [] if field == "citations" else "invented"
    )
    error = "admission.final_accepted_claim" if field == "answer_claim_id" else "admission.final_qa"
    assert_rejected(
        runtime, canonical_json_bytes(payload), error, actions=SOURCE_ACTION_COUNTS[path]
    )
    assert runtime.final is None and not runtime.terminal


def test_independent_numeric_check_failure_never_creates_observation_or_claim(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session")
    execute = runtime.adapter.execute

    def corrupt(prepared: Any) -> dict[str, Any]:
        proposition = execute(prepared)
        proposition["output"]["value"] = "0"
        return proposition

    monkeypatch.setattr(runtime.adapter, "execute", corrupt)
    event = fixture_step(runtime)
    assert event["receipt"]["admitted"] is True
    assert event["execution_error"] == "execution.independent_output"
    assert not {"observation", "claim", "final"} & set(event)
    assert runtime.terminal and runtime.pending is None and runtime.claims == []
    assert runtime.feedback["code"] == "execution_failed"


def test_external_callback_uses_same_language_without_claiming_model_origin_or_filling_fields(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path
) -> None:
    fixture = PublicFixtureCallback()
    seen = []

    def external(request: dict[str, Any]) -> bytes:
        seen.append(copy.deepcopy(request))
        raw = fixture.generate(request)
        request["context"]["task_type"] = "mutated_client_copy"
        request["state"]["accepted_claims"].clear()
        return raw

    callback = ExternalJSONCallback(external, client_id="test-local-json-no-provider")
    runtime = PublicQARuntime(
        adapter_for(registered_sources, "share_disclosed_total"), callback, tmp_path / "session"
    )
    result = runtime.run()
    assert result["final"]["qa_validation"]["qa_valid"] is True
    assert len(seen) == 5
    assert runtime.adapter.context["task_type"] == SHARE_FAMILY
    assert len(result["claims"]) == 2
    assert result["callback_binding"]["origin"] == "external_callback"
    assert result["callback_binding"]["verified_model_origin"] is False
    assert result["callback_binding"]["model_sample"] is False
    assert result["callback_binding"]["host_semantic_field_fill"] is False
    assert all(event["submission"]["host_repairs"] == [] for event in result["events"])


def test_missing_external_semantic_fields_are_not_filled_by_host(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path
) -> None:
    def incomplete(request: dict[str, Any]) -> bytes:
        payload = action_response(request, request["available_actions"][0])
        del payload["decision"]
        return canonical_json_bytes(payload)

    runtime = PublicQARuntime(
        adapter_for(registered_sources, "share_disclosed_total"),
        ExternalJSONCallback(incomplete, client_id="test-incomplete"),
        tmp_path / "session",
        max_submissions=1,
        max_actions=1,
    )
    result = runtime.run()
    assert result["final"] is None and result["claims"] == []
    assert result["events"][0]["receipt"]["error_code"] == "submission.schema"
    assert result["terminal_state"]["action_count"] == 0
    assert result["terminal_state"]["last_feedback"]["code"] == "submission_budget_exhausted"


def test_callback_nonbytes_failure_is_not_reinterpreted_as_a_submission(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path
) -> None:
    callback = ExternalJSONCallback(lambda request: {}, client_id="test-not-raw")
    runtime = PublicQARuntime(
        adapter_for(registered_sources, "share_disclosed_total"), callback, tmp_path / "session"
    )
    result = runtime.run()
    assert result["events"] == [] and result["claims"] == [] and result["final"] is None
    assert result["terminal_state"]["last_feedback"]["code"] == "callback_failure"
    assert result["terminal_state"]["action_count"] == 0


def test_action_budget_prevents_extra_execution_without_fabricating_completion(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path
) -> None:
    runtime = runtime_for(
        registered_sources, tmp_path / "session", max_actions=1, max_submissions=3
    )
    result = runtime.run()
    assert result["final"] is None and len(result["claims"]) == 1
    assert result["terminal_state"]["action_count"] == 1
    assert result["events"][-1]["receipt"]["error_code"] == "admission.action_phase_budget"
    assert result["terminal_state"]["last_feedback"]["code"] == "submission_budget_exhausted"
    with pytest.raises(ProtocolError, match="runtime.submission_bound"):
        runtime.step(b"{}")


def test_protocol_explicitly_does_not_claim_retraction_or_hidden_plan_inference() -> None:
    rules = contract()
    assert rules["supported_update_dispositions"] == ["accept", "reject"]
    assert (
        rules["accepted_claim_retraction_replacement_or_descendant_invalidation_supported"] is False
    )
    assert rules["plan_given_is_not_autonomous_hidden_plan_inference"] is True
    assert rules["private_chain_of_thought_required"] is False
    assert rules["training_or_production_release"] is False
    with pytest.raises(ProtocolError, match="submission.kind"):
        parse(b'{"kind":"replace_accepted_claim"}')


def test_existing_session_directory_is_never_overwritten(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session")
    context = (runtime.store.root / "context.json").read_bytes()
    with pytest.raises(FileExistsError):
        runtime_for(registered_sources, tmp_path / "session")
    assert (runtime.store.root / "context.json").read_bytes() == context


@pytest.mark.parametrize(
    "path", [name for name in SOURCE_ACTION_COUNTS if not name.startswith("share_")]
)
def test_callback_actions_updates_and_final_projection_do_not_read_private_case(
    registered_sources: tuple[Any, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session", path)

    class PrivateCaseUnavailable:
        def __getattribute__(self, name: str) -> Any:
            raise AssertionError("private case accessed before post-execution QA: " + name)

    def keys_in(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {key for child in value.values() for key in keys_in(child)}
        if isinstance(value, list):
            return {key for child in value for key in keys_in(child)}
        return set()

    assert not {
        "oracle",
        "task_program",
        "expected_output",
        "gold_evidence_ids",
        "proof_graph",
        "reference_program",
    } & keys_in(runtime.request())
    private_case = runtime.adapter.case
    monkeypatch.setattr(runtime.adapter, "case", PrivateCaseUnavailable())
    for _ in range(2 * SOURCE_ACTION_COUNTS[path]):
        assert fixture_step(runtime)["receipt"]["admitted"] is True
    assert runtime.request()["final_claim_ids"]
    final = runtime.callback.generate(runtime.request())
    assert parse(final)["kind"] == "final"
    monkeypatch.setattr(runtime.adapter, "case", private_case)
    assert runtime.step(final)["receipt"]["admitted"] is True
    assert runtime.final["qa_validation"]["qa_valid"] is True


def test_qa_recomputes_oracle_independently_of_public_projection_and_candidate_executor(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = runtime_for(registered_sources, tmp_path / "session", "registered_ratio")
    for _ in range(2 * SOURCE_ACTION_COUNTS["registered_ratio"]):
        fixture_step(runtime)
    final = parse(runtime.callback.generate(runtime.request()))
    forged_claims = copy.deepcopy(runtime.claims)
    forged_claims[-1]["proposition"]["output"]["value"] = "0"
    final["result"] = public_program_answer(runtime.adapter.context, forged_claims)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("candidate executor used to produce independent QA reference")

    for row in runtime.adapter.registry.manifest():
        monkeypatch.setattr(
            runtime.adapter.registry.require(row["operator_id"]).executor, "execute", forbidden
        )
    verification = runtime.adapter.verify_final(final, forged_claims)
    assert verification["source_valid"] is True
    assert verification["answer_valid"] is True
    assert verification["schema_valid"] is True
    assert verification["citation_valid"] is True
    assert verification["qa_valid"] is False
    # The original accepted result still validates through Oracle verifiers only.
    original = parse(runtime.callback.generate(runtime.request()))
    assert runtime.adapter.verify_final(original, runtime.claims)["qa_valid"] is True


def test_branch_ready_order_can_change_without_changing_source_task_or_answer(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path
) -> None:
    results = []
    for reverse in (False, True):
        runtime = PublicQARuntime(
            adapter_for(registered_sources, "derived_growth_absolute_spread"),
            PublicFixtureCallback(reverse_ready_order=reverse),
            tmp_path / str(reverse),
        )
        results.append(runtime.run())
    assert all(result["final"]["qa_validation"]["qa_valid"] for result in results)
    assert results[0]["context_id"] == results[1]["context_id"]
    assert results[0]["final"]["answer"]["result"] == results[1]["final"]["answer"]["result"]
    orders = [
        [
            event["parsed"]["decision"]["obligation_id"]
            for event in result["events"]
            if event["parsed"]["kind"] == "action"
        ]
        for result in results
    ]
    assert orders[0] != orders[1] and set(orders[0]) == set(orders[1])


def test_run_persists_the_exact_request_before_calling_external_callback(
    registered_sources: tuple[Any, dict[str, Any]], tmp_path: Path
) -> None:
    output = tmp_path / "session"
    fixture = PublicFixtureCallback()
    seen = []

    def complete(request: dict[str, Any]) -> bytes:
        index = request["state"]["submission_count"]
        saved = output / f"turns/{index:03d}_request.json"
        assert saved.is_file()
        assert saved.read_bytes() == canonical_json_bytes(request)
        assert not (output / f"turns/{index:03d}_response.txt").exists()
        seen.append(copy.deepcopy(request))
        return fixture.generate(request)

    runtime = PublicQARuntime(
        adapter_for(registered_sources, "share_disclosed_total"),
        ExternalJSONCallback(complete, client_id="test-request-durable-before-callback"),
        output,
    )
    result = runtime.run()
    assert result["final"]["qa_validation"]["qa_valid"] is True
    assert len(seen) == 5
    assert seen == [event["request"] for event in result["events"]]
    for index, request in enumerate(seen):
        name = f"turns/{index:03d}_request.json"
        writes = [event["kind"] for event in runtime.store.events if event.get("path") == name]
        assert writes == ["file_fsync", "directory_fsync"]
        assert result["events"][index]["submission"]["request_id"] == request["id"]
