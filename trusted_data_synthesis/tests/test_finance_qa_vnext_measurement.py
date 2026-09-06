"""Hand-authored persisted traces test the reader without running any QA Runtime."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.domains.finance.qa_vnext.measurement import (
    _depths,
    _isomorphism,
    audit_session,
    compare_sessions,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract, record
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import (
    publish_update_contract,
)


class _StaticAdapter:
    """An immutable tiny source with a separately specified answer, never executed."""

    def __init__(self, *, alternative: bool = True):
        self.registry = default_registry()
        self.alternative = alternative
        self.values = {"source:left": "3", "source:alternative": "3", "source:right": "2"}
        self.context = record(
            "context",
            task_id="two_inputs_sum",
            task_type="temporal_average",
            evidence=self.values,
            alternative=alternative,
        )
        self.output_checks = 0

    def offers(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_goal = {claim["obligation_id"]: claim for claim in claims}
        result = []
        for goal in ("left", "right", "sum"):
            if goal in by_goal or (goal == "sum" and not {"left", "right"} <= set(by_goal)):
                continue
            sources = (
                (["source:left", "source:alternative"] if self.alternative else ["source:left"])
                if goal == "left"
                else ["source:right"]
            )
            if goal == "sum":
                sources = ["sum"]
            for source in sources:
                if goal == "sum":
                    inputs = [
                        {
                            "kind": "claim",
                            "ref_id": by_goal[name]["id"],
                            "role": name,
                            "selector": "payload.value",
                        }
                        for name in ("left", "right")
                    ]
                    lineage = sorted(
                        {ref for claim in claims for ref in claim["proposition"]["lineage"]}
                    )
                else:
                    inputs = [
                        {
                            "kind": "evidence",
                            "ref_id": source,
                            "role": "selected_evidence",
                            "selector": None,
                        }
                    ]
                    lineage = [source]
                operation = "aggregate" if goal == "sum" else "lookup"
                result.append(
                    record(
                        "offered_action",
                        obligation_id=goal,
                        subgoal="derive_quantity" if goal == "sum" else "resolve_evidence",
                        operation=operation,
                        operation_contract_id="test:" + operation,
                        inputs=inputs,
                        parameters={"method": "sum"} if goal == "sum" else {},
                        basis={
                            "relation": "requires",
                            "evidence_refs": lineage,
                            "claim_refs": sorted(
                                item["ref_id"] for item in inputs if item["kind"] == "claim"
                            ),
                        },
                        expected_effect={
                            "establishes_obligation": goal,
                            "output_schema": "scalar" if goal == "sum" else "payload",
                        },
                        selection_rules=["dependency_ready", "registered_semantic_preconditions"],
                        alternative_group=goal,
                        semantic_choice=[source],
                        input_order_policy=self.registry.require(operation).input_order_policy,
                    )
                )
        return result

    def prepare(self, offer: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
        by_id = {claim["id"]: claim for claim in claims}
        inputs = []
        for item in offer["inputs"]:
            if item["kind"] == "claim":
                claim = by_id[item["ref_id"]]
                assert claim["status"] == "accepted"
                value = claim["proposition"]["output"]["payload"]["value"]
                ref = claim["obligation_id"]
            else:
                value = {"value": self.values[item["ref_id"]]}
                ref = item["ref_id"]
            inputs.append(OperationInput(ref_id=ref, value=value))
        if offer["obligation_id"] == "sum":
            output = {"method": "sum", "value": "5"}
        else:
            output = {"selected_ref": inputs[0].ref_id, "payload": inputs[0].value}
        return {
            "operation": offer["operation"],
            "inputs": tuple(inputs),
            "lineage": offer["basis"]["evidence_refs"],
            "slot": offer["obligation_id"],
            "specified_proposition": {
                "output": output,
                "lineage": offer["basis"]["evidence_refs"],
                "operation": offer["operation"],
            },
        }

    def execute(self, prepared: Any) -> Any:
        raise AssertionError("The independent audit must never execute a task")

    def verify_execution(self, prepared: dict[str, Any], proposition: dict[str, Any]) -> bool:
        self.output_checks += 1
        return proposition == prepared["specified_proposition"]

    def final_claims(self, claims: list[dict[str, Any]]) -> list[str]:
        return [claim["id"] for claim in claims if claim["obligation_id"] == "sum"]

    def verify_final(self, final: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
        claim = next(item for item in claims if item["id"] == final["answer_claim_id"])
        return record(
            "qa_validation",
            qa_valid=(
                final["result"] == {"value": "5"}
                and set(final["citations"]) == set(claim["proposition"]["lineage"])
            ),
        )


class _WrittenTrace:
    """Serialize independently specified observations; this is not a task executor."""

    def __init__(self, path: Path, adapter: _StaticAdapter, *, name: str):
        self.path, self.adapter = path, adapter
        path.mkdir()
        self.rules = contract()
        self.binding = record("callback_binding", origin="fixture", fixture_id=name)
        self.bounds = {"actions": 16, "submissions": 40}
        self.journal: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.claims: list[dict[str, Any]] = []
        self.pending = self.final = self.feedback = None
        self.actions = self.updates = 0
        for filename, value in (
            ("protocol.json", self.rules),
            ("context.json", adapter.context),
            ("callback_binding.json", self.binding),
            ("registry.json", record("registry", members=adapter.registry.manifest())),
            ("bounds.json", self.bounds),
        ):
            self.write(filename, value)

    def write(self, name: str, value: Any, *, raw: bool = False) -> None:
        path = self.path / name
        path.parent.mkdir(exist_ok=True, parents=True)
        with path.open("xb") as stream:
            stream.write(value if raw else canonical_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.journal.extend(
            ({"kind": "file_fsync", "path": name}, {"kind": "directory_fsync", "path": name})
        )

    @staticmethod
    def claim(observation: dict[str, Any]) -> dict[str, Any]:
        return record(
            "claim",
            observation_id=observation["id"],
            action_submission_id=observation["action_submission_id"],
            obligation_id=observation["obligation_id"],
            proposition=observation["proposition"],
            status="accepted",
        )

    def state(self, *, after: bool = False) -> dict[str, Any]:
        return record(
            "state",
            context_id=self.adapter.context["id"],
            protocol_id=self.rules["id"],
            accepted_claims=self.claims,
            pending_observation=self.pending,
            phase="terminal" if self.final else "update" if self.pending else "action",
            submission_count=len(self.events) + int(after),
            action_count=self.actions,
            update_count=self.updates,
            last_feedback=self.feedback,
            unresolved_uncertainties=[],
            terminal=self.final is not None,
        )

    def request(self) -> dict[str, Any]:
        transitions = {}
        if self.pending:
            before = {offer["obligation_id"] for offer in self.adapter.offers(self.claims)}
            for disposition in ("accept", "reject"):
                preview = self.claims + (
                    [self.claim(self.pending)] if disposition == "accept" else []
                )
                after = {offer["obligation_id"] for offer in self.adapter.offers(preview)}
                transitions[disposition] = {
                    "newly_enabled_obligation_ids": sorted(after - before),
                    "remaining_uncertainty_refs": [],
                    "allowed_next_subgoals": sorted(
                        after | ({"submit_final"} if self.adapter.final_claims(preview) else set())
                    ),
                }
        return publish_update_contract(
            record(
                "request",
                protocol_id=self.rules["id"],
                context=self.adapter.context,
                state=self.state(),
                available_actions=[] if self.pending else self.adapter.offers(self.claims),
                final_claim_ids=[] if self.pending else self.adapter.final_claims(self.claims),
                update_transition_options=transitions,
                response_schemas=self.rules["submission_schemas"],
            )
        )

    def append(
        self,
        value: dict[str, Any],
        *,
        raw_override: bytes | None = None,
        wrong_output: bool = False,
    ) -> None:
        index = len(self.events)
        prefix = f"turns/{index:03d}_"
        request = self.request()
        value = {**value, "state_id": request["state"]["id"]}
        raw = raw_override if raw_override is not None else json.dumps(value, indent=2).encode()
        submission = record(
            "submission",
            request_id=request["id"],
            raw_sha256=hashlib.sha256(raw).hexdigest(),
            raw_bytes=len(raw),
            callback_binding=self.binding,
            host_repairs=[],
        )
        receipt = record(
            "receipt",
            submission_id=submission["id"],
            request_id=request["id"],
            state_id=request["state"]["id"],
            admitted=True,
            error_code=None,
            no_host_semantic_repair=True,
        )
        self.write(prefix + "request.json", request)
        self.write(prefix + "response.txt", raw, raw=True)
        self.write(prefix + "submission.json", submission)
        self.write(prefix + "receipt.json", receipt)
        event = {
            "sequence": index,
            "request": request,
            "submission": submission,
            "parsed": value,
            "receipt": receipt,
        }
        if value["kind"] == "action":
            self.journal.extend(
                (
                    {
                        "kind": "pre_dispatch_readback",
                        "sequence": index,
                        "response_path": prefix + "response.txt",
                        "receipt_path": prefix + "receipt.json",
                    },
                    {
                        "kind": "execution_dispatch",
                        "sequence": index,
                        "submission_id": submission["id"],
                    },
                    {
                        "kind": "execution_return",
                        "sequence": index,
                        "submission_id": submission["id"],
                    },
                )
            )
            offer = next(
                item
                for item in request["available_actions"]
                if item["id"] == value["decision"]["selected_action_id"]
            )
            prepared = self.adapter.prepare(offer, self.claims)
            proposition = copy.deepcopy(prepared["specified_proposition"])
            if wrong_output:
                proposition["output"]["payload"]["value"] = "999"
            execution = record(
                "execution",
                action_submission_id=submission["id"],
                receipt_id=receipt["id"],
                operation=offer["operation"],
                selected_action=offer,
                resolved_inputs=[item.model_dump(mode="json") for item in prepared["inputs"]],
                proposition=proposition,
                success=True,
            )
            self.write(prefix + "execution.json", execution)
            observation = record(
                "observation",
                action_submission_id=submission["id"],
                execution_id=execution["id"],
                receipt_id=receipt["id"],
                obligation_id=offer["obligation_id"],
                selected_action=offer,
                proposition=proposition,
                independent_output_valid=True,
            )
            self.write(prefix + "observation.json", observation)
            self.pending = observation
            self.actions += 1
            self.feedback = {
                "code": "pending_observation_requires_callback_update",
                "admitted": True,
            }
            event.update(execution=execution, observation=observation)
        elif value["kind"] == "update":
            assert self.pending is not None
            if value["disposition"] == "accept":
                claim = self.claim(self.pending)
                self.write(prefix + "claim.json", claim)
                self.claims.append(claim)
                event["claim"] = claim
            self.pending = None
            self.updates += 1
            self.feedback = {
                "code": "claim_accepted"
                if value["disposition"] == "accept"
                else "observation_declined",
                "admitted": True,
            }
        else:
            self.final = record(
                "final",
                submission_id=submission["id"],
                answer=value,
                qa_validation=self.adapter.verify_final(value, self.claims),
            )
            self.write(prefix + "final.json", self.final)
            self.feedback = {"code": "complete", "admitted": True}
        event["post_state"] = self.state(after=True)
        self.write(prefix + "event.json", event)
        self.events.append(copy.deepcopy(event))

    def action(
        self,
        goal: str,
        *,
        alternative: bool = False,
        wrong_output: bool = False,
        rule: str = "dependency_ready",
        duplicate_json_key: bool = False,
    ) -> None:
        request = self.request()
        options = [
            offer for offer in request["available_actions"] if offer["obligation_id"] == goal
        ]
        offer = options[-1] if alternative else options[0]
        value = {
            "kind": "action",
            "operation": offer["operation"],
            "inputs": offer["inputs"],
            "parameters": offer["parameters"],
            "decision": {
                "obligation_id": offer["obligation_id"],
                "subgoal": offer["subgoal"],
                "candidate_action_ids": [item["id"] for item in request["available_actions"]],
                "selected_action_id": offer["id"],
                "selection_rule": rule,
                "basis": offer["basis"],
                "unresolved_uncertainty_refs": [],
                "expected_effect": offer["expected_effect"],
            },
        }
        raw = None
        if duplicate_json_key:
            complete = {**value, "state_id": request["state"]["id"]}
            raw = ('{"kind":"action",' + json.dumps(complete)[1:]).encode()
        self.append(value, raw_override=raw, wrong_output=wrong_output)

    def update(self, disposition: str = "accept") -> None:
        assert self.pending is not None
        accepted = disposition == "accept"
        options = self.request()["update_transition_options"][disposition]
        self.append(
            {
                "kind": "update",
                "observation_id": self.pending["id"],
                "disposition": disposition,
                "proposed_claim": self.pending["proposition"] if accepted else None,
                "assessment": {
                    "relation": "accepts_observed_proposition"
                    if accepted
                    else "declines_observation",
                    "observation_refs": [self.pending["id"]],
                    "evidence_refs": self.pending["proposition"]["lineage"],
                    "fulfills_obligation": self.pending["obligation_id"] if accepted else None,
                },
                "remaining_uncertainty_refs": [],
                "newly_enabled_obligation_ids": options["newly_enabled_obligation_ids"],
                "next_subgoal": options["allowed_next_subgoals"][0],
            }
        )

    def finish(self) -> dict[str, Any]:
        self.append(
            {
                "kind": "final",
                "answer_claim_id": self.claims[-1]["id"],
                "result": {"value": "5"},
                "citations": self.claims[-1]["proposition"]["lineage"],
            }
        )
        session = record(
            "session",
            context_id=self.adapter.context["id"],
            protocol_id=self.rules["id"],
            callback_binding=self.binding,
            bounds=self.bounds,
            registry_hash=strict_canonical_hash(self.adapter.registry.manifest()),
            events=self.events,
            claims=self.claims,
            final=self.final,
            terminal_state=self.state(),
            accepted_claim_revision_supported=False,
        )
        self.write("session.json", session)
        _seal(self.path, session["id"], self.journal)
        return session


def _seal(path: Path, session_id: str, journal: list[dict[str, Any]]) -> None:
    members = []
    for file in sorted(path.rglob("*")):
        if not file.is_file() or file.name == "manifest.json":
            continue
        data = file.read_bytes()
        members.append(
            {
                "path": file.relative_to(path).as_posix(),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest = record(
        "manifest",
        session_id=session_id,
        members=members,
        write_events=journal,
        self_excluding=True,
    )
    (path / "manifest.json").write_bytes(canonical_json_bytes(manifest))


def _complete(
    path: Path,
    adapter: _StaticAdapter,
    *,
    order: tuple[str, ...] = ("left", "right"),
    alternative: bool = False,
    reject: bool = False,
    wrong_output: bool = False,
    duplicate_json_key: bool = False,
    rule: str = "dependency_ready",
) -> dict[str, Any]:
    trace = _WrittenTrace(path, adapter, name=path.name)
    if reject:
        trace.action("left")
        trace.update("reject")
        assert trace.claims == []
    for goal in order:
        trace.action(
            goal,
            alternative=alternative and goal == "left",
            wrong_output=wrong_output and goal == "left",
            rule=rule,
            duplicate_json_key=duplicate_json_key and goal == "left",
        )
        trace.update()
    trace.action("sum")
    trace.update()
    return trace.finish()


def test_audit_reads_raw_bytes_and_never_calls_executor(tmp_path: Path) -> None:
    adapter = _StaticAdapter()
    session = _complete(tmp_path / "trace", adapter)
    audit = audit_session(adapter, session, tmp_path / "trace")
    assert audit["errors"] == []
    assert audit["qualified"] and audit["projection_supported"]
    graph = audit["actual_decision_graph"]
    assert graph == record(
        "actual_decision_graph",
        nodes=graph["nodes"],
        event_bindings=graph["event_bindings"],
        non_accept_event_ledger=graph["non_accept_event_ledger"],
    )
    assert graph["id"].startswith("finance_qa_vnext_actual_decision_graph:")
    assert graph["nodes"] == audit["finite_projection"]["nodes"]
    assert [binding["action_submission_id"] for binding in graph["event_bindings"]] == [
        event["submission"]["id"]
        for event in session["events"]
        if event["parsed"]["kind"] == "action"
    ]
    assert adapter.output_checks == 3
    assert audit["runtime_executions_by_audit"] == audit["adapter_execute_calls_by_audit"] == 0
    assert audit["origin"] == "fixture"
    depth = audit["depth_metrics"]
    assert depth["actual_action_dependency_structural_depth"] == 2
    assert depth["actual_action_dependency_semantic_depth"] == 1
    assert depth["observable_choice_dependency_depth"] == 1
    assert depth["observable_choice_count"] == 1
    assert not depth["model_hidden_or_critical_reasoning_depth_measured"]


def test_independent_branch_schedule_and_runtime_ids_do_not_change_relation(tmp_path: Path) -> None:
    adapter = _StaticAdapter()
    left = _complete(tmp_path / "left", adapter)
    right = _complete(tmp_path / "right", adapter, order=("right", "left"))
    assert left["id"] != right["id"]
    result = compare_sessions(
        audit_session(adapter, left, tmp_path / "left"),
        audit_session(adapter, right, tmp_path / "right"),
    )
    assert result["relation"] == "equivalent", result
    assert result["correspondence"] == {
        "action:0": "action:1",
        "action:1": "action:0",
        "action:2": "action:2",
    }
    assert not result["content_hash_is_relation_authority"]


@pytest.mark.parametrize("change", ["evidence", "judgment"])
def test_equal_final_values_do_not_erase_actual_evidence_or_judgment(
    tmp_path: Path, change: str
) -> None:
    adapter = _StaticAdapter()
    left = _complete(tmp_path / "left", adapter)
    right = _complete(
        tmp_path / "right",
        adapter,
        alternative=change == "evidence",
        rule="registered_semantic_preconditions" if change == "judgment" else "dependency_ready",
    )
    assert left["final"]["answer"]["result"] == right["final"]["answer"]["result"]
    result = compare_sessions(
        audit_session(adapter, left, tmp_path / "left"),
        audit_session(adapter, right, tmp_path / "right"),
    )
    assert result["relation"] == "not_equivalent", result
    assert result["retained_difference_witness"]["kind"] == "retained_action_semantics"


def test_two_ready_obligations_are_not_two_alternative_semantic_choices(tmp_path: Path) -> None:
    adapter = _StaticAdapter(alternative=False)
    session = _complete(tmp_path / "trace", adapter)
    assert len(session["events"][0]["request"]["available_actions"]) == 2
    audit = audit_session(adapter, session, tmp_path / "trace")
    assert audit["qualified"], audit
    assert audit["depth_metrics"]["observable_choice_count"] == 0
    assert audit["depth_metrics"]["observable_choice_dependency_depth"] == 0


def test_declined_observation_creates_no_claim_and_relation_remains_undetermined(
    tmp_path: Path,
) -> None:
    adapter = _StaticAdapter()
    session = _complete(tmp_path / "trace", adapter, reject=True)
    assert "claim" not in session["events"][1]
    assert session["events"][1]["post_state"]["accepted_claims"] == []
    audit = audit_session(adapter, session, tmp_path / "trace")
    assert audit["qualified"], audit
    assert not audit["projection_supported"]
    assert audit["actual_decision_graph"]["non_accept_event_ledger"][0]["claim_created"] is False
    result = compare_sessions(audit, audit)
    assert result["relation"] == "undetermined"
    assert result["reason"] == "comparison.unsupported_reject_or_revision_effect"


@pytest.mark.parametrize("attack", ["raw_whitespace", "dispatch_before_receipt_fsync"])
def test_resealed_manifest_does_not_launder_raw_binding_or_pre_dispatch_order(
    tmp_path: Path,
    attack: str,
) -> None:
    adapter = _StaticAdapter()
    path = tmp_path / "trace"
    session = _complete(path, adapter)
    manifest = json.loads((path / "manifest.json").read_bytes())
    if attack == "raw_whitespace":
        response = path / "turns/000_response.txt"
        response.write_bytes(response.read_bytes() + b"\n")
    else:
        journal = manifest["write_events"]
        dispatch = next(item for item in journal if item["kind"] == "execution_dispatch")
        journal.remove(dispatch)
        receipt_sync = next(
            index
            for index, item in enumerate(journal)
            if item == {"kind": "file_fsync", "path": "turns/000_receipt.json"}
        )
        journal.insert(receipt_sync, dispatch)
    _seal(path, session["id"], manifest["write_events"])
    audit = audit_session(adapter, session, path)
    assert not audit["validation_passed"]
    assert audit["errors"][0]["code"] == (
        "event.raw_submission_binding"
        if attack == "raw_whitespace"
        else "artifacts.durability_dispatch_order"
    )


@pytest.mark.parametrize("attack", ["wrong_output", "duplicate_json_key"])
def test_fully_bound_bad_output_and_ambiguous_raw_json_reject(tmp_path: Path, attack: str) -> None:
    adapter = _StaticAdapter()
    session = _complete(
        tmp_path / "trace",
        adapter,
        wrong_output=attack == "wrong_output",
        duplicate_json_key=attack == "duplicate_json_key",
    )
    audit = audit_session(adapter, session, tmp_path / "trace")
    assert not audit["validation_passed"]
    assert audit["errors"][0]["code"] == (
        "execution.independent_output"
        if attack == "wrong_output"
        else "event.raw_parsed_disagreement"
    )
    assert compare_sessions(audit, audit)["relation"] == "undetermined"


def test_same_success_cannot_compare_across_context_or_registry(tmp_path: Path) -> None:
    adapter = _StaticAdapter()
    session = _complete(tmp_path / "trace", adapter)
    audit = audit_session(adapter, session, tmp_path / "trace")
    for field in ("context_id", "task_id", "registry_hash", "protocol_id"):
        body = {key: value for key, value in audit.items() if key not in {"id", "schema_version"}}
        other = record("session_audit", **{**body, field: "different"})
        result = compare_sessions(audit, other)
        assert result["relation"] == "undetermined"
        assert result["reason"] == "comparison.context_task_protocol_registry_mismatch"


def test_exact_graph_comparison_preserves_shared_producer_structure() -> None:
    def graph(second_parent: str) -> dict[str, Any]:
        nodes = []
        for key, parent in (("a", None), ("b", None), ("c", "a"), ("d", second_parent)):
            nodes.append(
                {
                    "node_id": key,
                    "operation": "lookup" if parent is None else "ratio",
                    "inputs": [] if parent is None else [{"producer_action": parent}],
                    "input_dependencies": [] if parent is None else [parent],
                    "decision_dependencies": [] if parent is None else [parent],
                }
            )
        return {"nodes": nodes, "final": None}

    # Local node colors/counts match; one graph shares a producer and the other does not.
    correspondence, witness = _isomorphism(graph("a"), graph("b"))
    assert correspondence is None
    assert witness["kind"] == "retained_dependency_or_final_structure"


def test_three_depth_measures_separate_parallel_choices_and_transparent_projections() -> None:
    # Two parallel growth branches merge into difference, then absolute. Choices
    # in the parallel branches contribute one level; the dependent final choice
    # contributes the second. Lookup layers contribute no semantic weight.
    layout = [
        ("left_lookup", [], "transparent_projection", True),
        ("right_lookup", [], "transparent_projection", False),
        ("left_growth", ["left_lookup"], "semantic", False),
        ("right_growth", ["right_lookup"], "semantic", True),
        ("difference", ["left_growth", "right_growth"], "semantic", False),
        ("absolute", ["difference"], "semantic", True),
    ]
    nodes = [
        {
            "node_id": name,
            "input_dependencies": parents,
            "decision_dependencies": parents,
            "program_role": role,
            "observable_choice": choice,
        }
        for name, parents, role, choice in layout
    ]
    depths = _depths(nodes)
    assert depths["actual_action_dependency_structural_depth"] == 4
    assert depths["actual_action_dependency_semantic_depth"] == 3
    assert depths["observable_choice_count"] == 3
    assert depths["observable_choice_dependency_depth"] == 2


def test_different_action_counts_retain_actual_source_and_producer_witness() -> None:
    direct = {
        "nodes": [
            {
                "node_id": "ratio",
                "operation": "share_ratio",
                "input_dependencies": [],
                "inputs": [
                    {"role": "numerator", "reference": {"evidence_id": "freight"}},
                    {"role": "denominator", "reference": {"evidence_id": "disclosed_total"}},
                ],
            }
        ],
        "final": None,
    }
    reconstructed = {
        "nodes": [
            {
                "node_id": "sum",
                "operation": "relation_sum",
                "input_dependencies": [],
                "inputs": [
                    {"role": "member", "reference": {"evidence_id": "freight"}},
                    {"role": "member", "reference": {"evidence_id": "other"}},
                ],
            },
            {
                "node_id": "ratio",
                "operation": "share_ratio",
                "input_dependencies": ["sum"],
                "inputs": [
                    {"role": "numerator", "reference": {"evidence_id": "freight"}},
                    {"role": "denominator", "reference": {"producer_action": "sum"}},
                ],
            },
        ],
        "final": None,
    }
    correspondence, witness = _isomorphism(direct, reconstructed)
    assert correspondence is None
    assert witness["kind"] == "actual_action_count"
    assert witness["left_support"][0]["inputs"][1] == {
        "role": "denominator",
        "reference": {"evidence_id": "disclosed_total"},
    }
    assert [node["operation"] for node in witness["right_support"]] == [
        "relation_sum",
        "share_ratio",
    ]
    assert witness["right_support"][1]["accepted_input_dependencies"] == ["sum"]
    assert witness["right_support"][1]["inputs"][1] == {
        "role": "denominator",
        "reference": {"producer_action": "sum"},
    }
