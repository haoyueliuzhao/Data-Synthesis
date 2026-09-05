"""Read-only validation and finite measurement of persisted public QA sessions.

No Runtime, callback, adapter executor, or legacy quotient is invoked here.  The
adapter's pure admission and independent output/answer verifiers remain the
task-specific authorities.  Durability evidence is a checked, persisted journal;
it is not an independent attestation that the operating system performed fsync.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash

from .protocol import Action, Final, ProtocolError, Update, contract, record, require


def _equal(left: Any, right: Any) -> bool:
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def _json(data: bytes) -> Any:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, "json.duplicate_key")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ProtocolError("json.non_finite_number")

    return json.loads(data, object_pairs_hook=unique_pairs, parse_constant=invalid_constant)


def _identity(value: dict[str, Any], kind: str) -> None:
    body = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    require(_equal(value, record(kind, **body)), "identity." + kind)


def _parse_public(data: bytes) -> dict[str, Any]:
    """Independent raw decoding against the shared public schema, not host parse()."""
    require(len(data) <= 1_048_576, "submission.byte_bound")
    try:
        value = _json(data)
        require(isinstance(value, dict), "submission.object")
        schemas: dict[str, type[BaseModel]] = {"action": Action, "update": Update, "final": Final}
        require(value.get("kind") in schemas, "submission.kind")
        return schemas[value["kind"]].model_validate(value).model_dump(mode="json")
    except (ValidationError, UnicodeError, json.JSONDecodeError) as error:
        raise ProtocolError("submission.schema") from error


class _SavedFiles:
    def __init__(self, directory: Path, session: dict[str, Any]):
        require(directory.is_dir() and not directory.is_symlink(), "artifacts.directory")
        self.directory = directory.resolve()
        manifest_path = directory / "manifest.json"
        require(not manifest_path.is_symlink(), "artifacts.symlink")
        manifest_raw = manifest_path.read_bytes()
        self.manifest = _json(manifest_raw)
        _identity(self.manifest, "manifest")
        require(manifest_raw == canonical_json_bytes(self.manifest), "artifacts.manifest_bytes")
        require(
            self.manifest["session_id"] == session["id"]
            and self.manifest["self_excluding"] is True,
            "artifacts.manifest_scope",
        )
        self.files: dict[str, bytes] = {}
        for member in self.manifest["members"]:
            require(set(member) == {"path", "sha256", "bytes"}, "artifacts.member_schema")
            name = member["path"]
            relative = Path(name)
            require(
                not relative.is_absolute()
                and ".." not in relative.parts
                and relative.as_posix() == name
                and name != "manifest.json"
                and name not in self.files,
                "artifacts.member_path",
            )
            path = directory / relative
            require(
                not path.is_symlink() and path.resolve().is_relative_to(self.directory),
                "artifacts.member_escape",
            )
            data = path.read_bytes()
            require(
                len(data) == member["bytes"]
                and hashlib.sha256(data).hexdigest() == member["sha256"],
                "artifacts.member_bytes:" + name,
            )
            self.files[name] = data
        require(
            set(self.files)
            == {
                path.relative_to(directory).as_posix()
                for path in directory.rglob("*")
                if path.is_file() and path != manifest_path
            },
            "artifacts.member_set",
        )
        self.used: set[str] = set()
        self.journal: list[dict[str, Any]] = []

    def use(self, name: str, expected: Any = None, *, raw: bool = False) -> bytes:
        require(name in self.files and name not in self.used, "artifacts.required_file:" + name)
        data = self.files[name]
        if not raw:
            require(data == canonical_json_bytes(expected), "artifacts.persisted_value:" + name)
        self.used.add(name)
        self.journal.extend(
            ({"kind": "file_fsync", "path": name}, {"kind": "directory_fsync", "path": name})
        )
        return data

    def complete(self) -> None:
        require(self.used == set(self.files), "artifacts.unconsumed_member")
        require(
            _equal(self.journal, self.manifest["write_events"]),
            "artifacts.durability_dispatch_order",
        )


def _claim(observation: dict[str, Any]) -> dict[str, Any]:
    return record(
        "claim",
        observation_id=observation["id"],
        action_submission_id=observation["action_submission_id"],
        obligation_id=observation["obligation_id"],
        proposition=observation["proposition"],
        status="accepted",
    )


def _state(
    context_id: str,
    claims: list[dict[str, Any]],
    pending: Any,
    counts: dict[str, int],
    feedback: Any,
    terminal: bool,
) -> dict[str, Any]:
    return record(
        "state",
        context_id=context_id,
        protocol_id=contract()["id"],
        accepted_claims=claims,
        pending_observation=pending,
        phase="terminal" if terminal else "update" if pending else "action",
        submission_count=counts["submissions"],
        action_count=counts["actions"],
        update_count=counts["updates"],
        last_feedback=feedback,
        unresolved_uncertainties=[],
        terminal=terminal,
    )


def _request(adapter: Any, state: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    claims, pending = state["accepted_claims"], state["pending_observation"]
    offers = [] if pending or state["terminal"] else adapter.offers(copy.deepcopy(claims))
    options = {}
    if pending:
        before = {offer["obligation_id"] for offer in adapter.offers(copy.deepcopy(claims))}
        for disposition in ("accept", "reject"):
            preview = copy.deepcopy(claims) + ([_claim(pending)] if disposition == "accept" else [])
            after = {offer["obligation_id"] for offer in adapter.offers(copy.deepcopy(preview))}
            final_ids = adapter.final_claims(copy.deepcopy(preview))
            options[disposition] = {
                "newly_enabled_obligation_ids": sorted(after - before),
                "remaining_uncertainty_refs": [],
                "allowed_next_subgoals": sorted(after | ({"submit_final"} if final_ids else set())),
            }
    return record(
        "request",
        protocol_id=rules["id"],
        context=adapter.context,
        state=state,
        available_actions=offers,
        final_claim_ids=adapter.final_claims(copy.deepcopy(claims)) if not pending else [],
        update_transition_options=options,
        response_schemas=rules["submission_schemas"],
    )


def _admission(
    adapter: Any, value: dict[str, Any], request: dict[str, Any], bounds: dict[str, int]
) -> dict[str, Any]:
    """Check public judgments without calling the Runtime admission implementation."""
    state = request["state"]
    claims, pending = state["accepted_claims"], state["pending_observation"]
    require(value["state_id"] == state["id"], "admission.current_state")
    require(not state["terminal"], "admission.terminal")
    if value["kind"] == "action":
        require(
            pending is None and state["action_count"] < bounds["actions"],
            "admission.action_phase_budget",
        )
        decision = value["decision"]
        options = {option["id"]: option for option in request["available_actions"]}
        require(len(options) == len(request["available_actions"]), "admission.duplicate_offer")
        candidate_ids = decision["candidate_action_ids"]
        require(
            len(candidate_ids) == len(set(candidate_ids)) and set(candidate_ids) == set(options),
            "admission.alternative_set",
        )
        require(decision["selected_action_id"] in options, "admission.selected_action")
        offer = options[decision["selected_action_id"]]
        require(
            all(
                _equal(value[field], offer[field])
                for field in ("operation", "inputs", "parameters")
            ),
            "admission.selected_action_content",
        )
        require(
            decision["obligation_id"] == offer["obligation_id"]
            and decision["subgoal"] == offer["subgoal"]
            and decision["selection_rule"] in offer["selection_rules"]
            and _equal(decision["expected_effect"], offer["expected_effect"])
            and _equal(decision["basis"], offer["basis"])
            and decision["unresolved_uncertainty_refs"] == [],
            "admission.public_judgment",
        )
        accepted = {claim["id"] for claim in claims if claim["status"] == "accepted"}
        refs = set(decision["basis"]["claim_refs"])
        for item in value["inputs"]:
            require(item["kind"] in {"claim", "evidence"}, "admission.input_kind")
            if item["kind"] == "claim":
                refs.add(item["ref_id"])
        require(refs <= accepted, "admission.previously_accepted_dependency")
        return {
            "offer": offer,
            "prepared": adapter.prepare(copy.deepcopy(offer), copy.deepcopy(claims)),
        }
    if value["kind"] == "update":
        require(pending is not None, "admission.pending_observation")
        accepted = value["disposition"] == "accept"
        require(value["observation_id"] == pending["id"], "admission.observation_parent")
        require(
            _equal(value["proposed_claim"], pending["proposition"] if accepted else None),
            "admission.exact_observation_acceptance",
        )
        assessment = {
            "relation": "accepts_observed_proposition" if accepted else "declines_observation",
            "observation_refs": [pending["id"]],
            "evidence_refs": pending["proposition"]["lineage"],
            "fulfills_obligation": pending["obligation_id"] if accepted else None,
        }
        require(_equal(value["assessment"], assessment), "admission.observation_assessment")
        transition = request["update_transition_options"][value["disposition"]]
        require(
            value["remaining_uncertainty_refs"] == transition["remaining_uncertainty_refs"]
            and value["newly_enabled_obligation_ids"] == transition["newly_enabled_obligation_ids"]
            and value["next_subgoal"] in transition["allowed_next_subgoals"],
            "admission.update_effect",
        )
        return {"observation": pending}
    require(
        pending is None and value["answer_claim_id"] in request["final_claim_ids"],
        "admission.final_accepted_claim",
    )
    validation = adapter.verify_final(copy.deepcopy(value), copy.deepcopy(claims))
    require(validation["qa_valid"] is True, "admission.final_qa")
    return {"validation": validation}


def _normalize_refs(value: Any, producers: dict[str, str]) -> Any:
    if isinstance(value, str) and value in producers:
        return {"producer_action": producers[value]}
    if isinstance(value, dict):
        return {key: _normalize_refs(item, producers) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_refs(item, producers) for item in value]
    return value


def _action_node(
    adapter: Any,
    value: dict[str, Any],
    offer: dict[str, Any],
    available: list[dict[str, Any]],
    observation: dict[str, Any],
    producers: dict[str, str],
    ordinal: int,
) -> dict[str, Any]:
    decision = value["decision"]
    inputs = []
    dependencies: set[str] = set()
    for item in value["inputs"]:
        ref = (
            {"evidence_id": item["ref_id"]}
            if item["kind"] == "evidence"
            else {"producer_action": producers[item["ref_id"]]}
        )
        if item["kind"] == "claim":
            dependencies.add(producers[item["ref_id"]])
        inputs.append(
            {**{key: content for key, content in item.items() if key != "ref_id"}, "reference": ref}
        )
    claim_basis = sorted({producers[item] for item in decision["basis"]["claim_refs"]})
    same_group = [
        item
        for item in available
        if offer.get("alternative_group") is not None
        and item.get("alternative_group") == offer["alternative_group"]
        and item.get("semantic_choice") is not None
    ]
    choices = {
        canonical_json_bytes(_normalize_refs(item["semantic_choice"], producers))
        for item in same_group
    }
    semantic_choices = [_json(item) for item in sorted(choices)]
    definition = adapter.registry.require(value["operation"])
    require(
        definition.program_role in {"semantic", "transparent_projection"},
        "measurement.registry_program_role",
    )
    return {
        "node_id": f"action:{ordinal}",
        "operation": value["operation"],
        "operation_contract_id": offer.get("operation_contract_id"),
        "program_role": definition.program_role,
        "input_order_policy": definition.input_order_policy,
        "inputs": inputs,
        "parameters": _normalize_refs(value["parameters"], producers),
        "judgment": {
            "obligation_id": decision["obligation_id"],
            "subgoal": decision["subgoal"],
            "selection_rule": decision["selection_rule"],
            "basis_relation": decision["basis"]["relation"],
            "evidence_basis": sorted(decision["basis"]["evidence_refs"]),
            "claim_basis": [{"producer_action": item} for item in claim_basis],
            "unresolved_uncertainty_refs": decision["unresolved_uncertainty_refs"],
            "expected_effect": decision["expected_effect"],
        },
        "alternative_group": offer.get("alternative_group"),
        "selected_semantic_choice": _normalize_refs(offer.get("semantic_choice"), producers),
        "available_group_semantic_choices": semantic_choices,
        "observable_choice": len(semantic_choices) >= 2,
        "proposition": _normalize_refs(observation["proposition"], producers),
        "input_dependencies": sorted(dependencies),
        "decision_dependencies": sorted(dependencies | set(claim_basis)),
        "observation_disposition": "pending",
    }


def _depths(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    structural: dict[str, int] = {}
    semantic: dict[str, int] = {}
    choices: dict[str, int] = {}
    for node in nodes:
        key = node["node_id"]
        inputs, decisions = node["input_dependencies"], node["decision_dependencies"]
        structural[key] = 1 + max((structural[parent] for parent in inputs), default=0)
        semantic[key] = int(node["program_role"] == "semantic") + max(
            (semantic[parent] for parent in inputs), default=0
        )
        choices[key] = int(node["observable_choice"]) + max(
            (choices[parent] for parent in decisions), default=0
        )
    return {
        "actual_action_dependency_structural_depth": max(structural.values(), default=0),
        "actual_action_dependency_semantic_depth": max(semantic.values(), default=0),
        "observable_choice_dependency_depth": max(choices.values(), default=0),
        "observable_choice_count": sum(node["observable_choice"] for node in nodes),
        "per_action": {
            node["node_id"]: {
                "structural": structural[node["node_id"]],
                "semantic": semantic[node["node_id"]],
                "observable_choice": choices[node["node_id"]],
            }
            for node in nodes
        },
        "scope": "actual admitted Actions and previously accepted input Claims",
        "model_hidden_or_critical_reasoning_depth_measured": False,
        "callback_count_used_as_depth": False,
        "independent_obligation_scheduling_is_choice": False,
        "transparent_projection_weight": 0,
    }


def _validate(adapter: Any, session: dict[str, Any], directory: Path) -> dict[str, Any]:
    _identity(session, "session")
    saved = _SavedFiles(directory, session)
    rules = contract()
    saved.use("protocol.json", rules)
    saved.use("context.json", adapter.context)
    saved.use("callback_binding.json", session["callback_binding"])
    saved.use("registry.json", record("registry", members=adapter.registry.manifest()))
    bounds = session["bounds"]
    require(
        set(bounds) == {"actions", "submissions"}
        and all(type(value) is int for value in bounds.values())
        and 1 <= bounds["actions"] <= bounds["submissions"] <= 256,
        "session.bounds",
    )
    saved.use("bounds.json", bounds)
    require(
        session["context_id"] == adapter.context["id"]
        and session["protocol_id"] == rules["id"]
        and session["registry_hash"] == strict_canonical_hash(adapter.registry.manifest()),
        "session.context_protocol_registry",
    )
    require(session["accepted_claim_revision_supported"] is False, "session.revision_unsupported")
    require(len(session["events"]) <= bounds["submissions"], "session.submission_bound")
    claims: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    event_bindings: list[dict[str, Any]] = []
    producers: dict[str, str] = {}
    observations: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    feedback: dict[str, Any] | None = None
    final: dict[str, Any] | None = None
    terminal = False
    counts = {"submissions": 0, "actions": 0, "updates": 0}
    for index, event in enumerate(session["events"]):
        require(not terminal and event["sequence"] == index, "event.sequence_after_terminal")
        prefix = f"turns/{index:03d}_"
        state = _state(adapter.context["id"], claims, pending, counts, feedback, terminal)
        request = _request(adapter, state, rules)
        require(_equal(event["request"], request), "event.actual_request")
        saved.use(prefix + "request.json", request)
        raw = saved.use(prefix + "response.txt", raw=True)
        submission = record(
            "submission",
            request_id=request["id"],
            raw_sha256=hashlib.sha256(raw).hexdigest(),
            raw_bytes=len(raw),
            callback_binding=session["callback_binding"],
            host_repairs=[],
        )
        require(_equal(event["submission"], submission), "event.raw_submission_binding")
        saved.use(prefix + "submission.json", submission)
        parsed: dict[str, Any] | None = None
        prepared: dict[str, Any] | None = None
        error_code: str | None = None
        try:
            parsed = _parse_public(raw)
            prepared = _admission(adapter, parsed, request, bounds)
        except (ProtocolError, ValueError, KeyError, TypeError) as error:
            error_code = str(error)
        else:
            error_code = None
        require(_equal(event["parsed"], parsed), "event.raw_parsed_disagreement")
        receipt = record(
            "receipt",
            submission_id=submission["id"],
            request_id=request["id"],
            state_id=state["id"],
            admitted=prepared is not None,
            error_code=error_code,
            no_host_semantic_repair=True,
        )
        require(_equal(event["receipt"], receipt), "event.independent_admission")
        saved.use(prefix + "receipt.json", receipt)
        expected_event = {
            "sequence": index,
            "request": request,
            "submission": submission,
            "parsed": parsed,
            "receipt": receipt,
        }
        counts["submissions"] += 1
        if prepared is None:
            feedback = {"code": error_code, "admitted": False}
            ledger.append(
                {
                    "sequence": index,
                    "effect": "no_state_change_except_feedback_and_budget",
                    "kind": "unadmitted_submission",
                    "error_code": error_code,
                    "raw_sha256": submission["raw_sha256"],
                    "parsed": parsed,
                }
            )
        elif parsed is not None and parsed["kind"] == "action":
            require(
                "execution_error" not in event, "execution.failure_not_independently_reexecuted"
            )
            saved.journal.extend(
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
            counts["actions"] += 1
            offer = prepared["offer"]
            proposition = event["execution"]["proposition"]
            require(
                adapter.verify_execution(prepared["prepared"], copy.deepcopy(proposition)) is True,
                "execution.independent_output",
            )
            execution = record(
                "execution",
                action_submission_id=submission["id"],
                receipt_id=receipt["id"],
                operation=offer["operation"],
                selected_action=offer,
                resolved_inputs=[
                    item.model_dump(mode="json") for item in prepared["prepared"]["inputs"]
                ],
                proposition=proposition,
                success=True,
            )
            require(_equal(event["execution"], execution), "execution.resolved_input_binding")
            saved.use(prefix + "execution.json", execution)
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
            require(_equal(event["observation"], observation), "observation.execution_binding")
            saved.use(prefix + "observation.json", observation)
            node = _action_node(
                adapter,
                parsed,
                offer,
                request["available_actions"],
                observation,
                producers,
                len(nodes),
            )
            nodes.append(node)
            event_bindings.append(
                {
                    "node_id": node["node_id"],
                    "sequence": index,
                    "action_submission_id": submission["id"],
                    "receipt_id": receipt["id"],
                    "execution_id": execution["id"],
                    "observation_id": observation["id"],
                    "update_submission_id": None,
                    "accepted_claim_id": None,
                }
            )
            for identity in (submission["id"], execution["id"], observation["id"]):
                producers[identity] = node["node_id"]
            observations[observation["id"]] = node
            pending = observation
            feedback = {"code": "pending_observation_requires_callback_update", "admitted": True}
            expected_event.update(execution=execution, observation=observation)
        elif parsed is not None and parsed["kind"] == "update":
            counts["updates"] += 1
            observation = prepared["observation"]
            node = observations[observation["id"]]
            event_binding = next(
                item for item in event_bindings if item["observation_id"] == observation["id"]
            )
            event_binding["update_submission_id"] = submission["id"]
            if parsed["disposition"] == "accept":
                claim = _claim(observation)
                require(claim["id"] not in producers, "claim.duplicate_acceptance")
                saved.use(prefix + "claim.json", claim)
                claims.append(claim)
                producers[claim["id"]] = node["node_id"]
                event_binding["accepted_claim_id"] = claim["id"]
                expected_event["claim"] = claim
            else:
                ledger.append(
                    {
                        "sequence": index,
                        "kind": "declined_pending_observation",
                        "producer_action": node["node_id"],
                        "claim_created": False,
                        "parsed": _normalize_refs(parsed, producers),
                        "effect": "pending_cleared; accepted_claims_unchanged",
                    }
                )
            node["observation_disposition"] = parsed["disposition"]
            pending = None
            feedback = {
                "code": "claim_accepted"
                if parsed["disposition"] == "accept"
                else "observation_declined",
                "admitted": True,
            }
        else:
            assert parsed is not None
            final = record(
                "final",
                submission_id=submission["id"],
                answer=parsed,
                qa_validation=prepared["validation"],
            )
            saved.use(prefix + "final.json", final)
            terminal = True
            feedback = {"code": "complete", "admitted": True}
        expected_event["post_state"] = _state(
            adapter.context["id"], claims, pending, counts, feedback, terminal
        )
        require(_equal(expected_event, event), "event.state_transition_or_unexpected_record")
        saved.use(prefix + "event.json", expected_event)
    if not terminal:
        require(
            counts["submissions"] == bounds["submissions"],
            "session.unwitnessed_early_stop_or_callback_failure",
        )
        terminal = True
        feedback = {"code": "submission_budget_exhausted"}
    expected_session = record(
        "session",
        context_id=adapter.context["id"],
        protocol_id=rules["id"],
        callback_binding=session["callback_binding"],
        bounds=bounds,
        registry_hash=strict_canonical_hash(adapter.registry.manifest()),
        events=session["events"],
        claims=claims,
        final=final,
        terminal_state=_state(adapter.context["id"], claims, pending, counts, feedback, terminal),
        accepted_claim_revision_supported=False,
    )
    require(_equal(session, expected_session), "session.terminal_claim_final_binding")
    saved.use("session.json", session)
    saved.complete()
    qualified = final is not None and final["qa_validation"]["qa_valid"] is True
    final_projection = None
    if final is not None and qualified:
        answer = final["answer"]
        final_projection = {
            "answer_producer": {"producer_action": producers[answer["answer_claim_id"]]},
            "result": _normalize_refs(answer["result"], producers),
            "citations": sorted(answer["citations"]),
        }
    projection = {"nodes": nodes, "final": final_projection}
    return {
        "validation_passed": True,
        "evidence_complete": True,
        "trajectory_valid": True,
        "qa_valid": qualified,
        "qualified": qualified,
        "errors": [],
        "manifest_id": saved.manifest["id"],
        "actual_decision_graph": record(
            "actual_decision_graph",
            nodes=nodes,
            event_bindings=event_bindings,
            non_accept_event_ledger=ledger,
        ),
        "depth_metrics": _depths(nodes),
        "finite_projection": projection,
        "projection_supported": qualified and not ledger,
        "projection_limits": []
        if qualified and not ledger
        else [
            "unqualified_session" if not qualified else "reject_or_unadmitted_effect_not_quotiented"
        ],
        "callback_count": counts["submissions"],
        "action_count": counts["actions"],
        "update_count": counts["updates"],
        "accepted_claim_count": len(claims),
        "independent_output_checks": counts["actions"],
    }


def audit_session(
    adapter: Any, session: dict[str, Any], artifact_directory: str | Path
) -> dict[str, Any]:
    """Validate saved bytes and transitions; never generate or execute an Action."""
    try:
        details = _validate(adapter, session, Path(artifact_directory))
    except (OSError, ValueError, TypeError, KeyError, IndexError, ArithmeticError) as error:
        details = {
            "validation_passed": False,
            "evidence_complete": False,
            "trajectory_valid": False,
            "qa_valid": False,
            "qualified": False,
            "errors": [{"code": str(error), "type": type(error).__name__}],
            "actual_decision_graph": None,
            "depth_metrics": None,
            "finite_projection": None,
            "projection_supported": False,
            "projection_limits": ["validation_failed"],
        }
    binding = session.get("callback_binding", {})
    if not isinstance(binding, dict):
        binding = {}
    return record(
        "session_audit",
        session_id=session.get("id"),
        context_id=session.get("context_id"),
        task_id=adapter.context.get("task_id"),
        task_type=adapter.context.get("task_type"),
        protocol_id=session.get("protocol_id"),
        registry_hash=session.get("registry_hash"),
        origin=binding.get("origin", binding.get("generator_origin", "unknown")),
        verified_model_origin=False,
        model_sample=False,
        model_attribution_allowed=False,
        provider_calls_by_audit=0,
        runtime_executions_by_audit=0,
        adapter_execute_calls_by_audit=0,
        historical_quotient_or_state_assignment_modified=False,
        private_reasoning_examined=False,
        accepted_claim_revision_supported=False,
        durability_evidence_scope="persisted bytes and recorded fsync/readback/dispatch chronology",
        **details,
    )


def _remap(value: Any, mapping: dict[str, str], *, anonymize: bool = False) -> Any:
    if isinstance(value, dict):
        if set(value) == {"producer_action"}:
            key = value["producer_action"]
            return {"producer_action": "*" if anonymize else mapping.get(key, key)}
        result = {
            key: _remap(item, mapping, anonymize=anonymize)
            for key, item in value.items()
            if key != "node_id"
        }
        for key in ("input_dependencies", "decision_dependencies"):
            if key in value:
                result[key] = sorted(
                    "*" if anonymize else mapping.get(item, item) for item in value[key]
                )
        if "node_id" in value and not anonymize:
            result["node_id"] = mapping.get(value["node_id"], value["node_id"])
        if "claim_basis" in result:
            result["claim_basis"] = sorted(result["claim_basis"], key=canonical_json_bytes)
        return result
    if isinstance(value, list):
        return [_remap(item, mapping, anonymize=anonymize) for item in value]
    return value


def _ordered_graph(graph: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    result = _remap(graph, mapping)
    result["nodes"] = sorted(result["nodes"], key=lambda node: node["node_id"])
    return result


def _support_summary(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose the operands/support behind a differing graph, not only its size."""
    return [
        {
            "node_id": node["node_id"],
            "operation": node["operation"],
            "inputs": copy.deepcopy(node["inputs"]),
            "parameters": copy.deepcopy(node.get("parameters", {})),
            "accepted_input_dependencies": list(node["input_dependencies"]),
            "public_judgment": copy.deepcopy(node.get("judgment")),
            "selected_semantic_choice": copy.deepcopy(node.get("selected_semantic_choice")),
            "observation_disposition": node.get("observation_disposition"),
        }
        for node in graph["nodes"]
    ]


def _isomorphism(left: dict[str, Any], right: dict[str, Any]) -> tuple[Any, Any]:
    """Find an exact labeled DAG correspondence, then compare full remapped content."""
    left_nodes = {node["node_id"]: node for node in left["nodes"]}
    right_nodes = {node["node_id"]: node for node in right["nodes"]}
    if len(left_nodes) != len(right_nodes):
        return None, {
            "kind": "actual_action_count",
            "left": len(left_nodes),
            "right": len(right_nodes),
            "left_support": _support_summary(left),
            "right_support": _support_summary(right),
            "difference_authority": "retained operations, typed operands and accepted dependencies",
        }
    colors_left = {
        key: canonical_json_bytes(_remap(node, {}, anonymize=True))
        for key, node in left_nodes.items()
    }
    colors_right = {
        key: canonical_json_bytes(_remap(node, {}, anonymize=True))
        for key, node in right_nodes.items()
    }
    if Counter(colors_left.values()) != Counter(colors_right.values()):
        difference = Counter(colors_left.values()) - Counter(colors_right.values())
        reverse = Counter(colors_right.values()) - Counter(colors_left.values())
        return None, {
            "kind": "retained_action_semantics",
            "left_only": [_json(value) for value in difference.elements()],
            "right_only": [_json(value) for value in reverse.elements()],
        }
    candidates = {
        key: [other for other in left_nodes if colors_left[other] == color]
        for key, color in colors_right.items()
    }
    order = sorted(right_nodes, key=lambda key: (len(candidates[key]), key))
    full_left = _ordered_graph(left, {})
    attempts = 0

    def search(mapping: dict[str, str], used: set[str]) -> dict[str, str] | None:
        nonlocal attempts
        attempts += 1
        require(attempts <= 100_000, "comparison.isomorphism_search_bound")
        if len(mapping) == len(order):
            return dict(mapping) if _equal(full_left, _ordered_graph(right, mapping)) else None
        key = order[len(mapping)]
        for target in candidates[key]:
            if target in used:
                continue
            mapping[key] = target
            compatible = True
            for source, mapped in mapping.items():
                for edge_kind in ("input_dependencies", "decision_dependencies"):
                    right_edges = set(right_nodes[source][edge_kind])
                    left_edges = set(left_nodes[mapped][edge_kind])
                    if any(
                        (peer in right_edges) != (destination in left_edges)
                        for peer, destination in mapping.items()
                    ):
                        compatible = False
                        break
                if not compatible:
                    break
            if compatible:
                result = search(mapping, used | {target})
                if result is not None:
                    return result
            del mapping[key]
        return None

    mapping = search({}, set())
    if mapping is not None:
        return mapping, None
    return None, {
        "kind": "retained_dependency_or_final_structure",
        "left": full_left,
        "right": _ordered_graph(right, {}),
    }


def compare_sessions(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Compare two independent audit reports in their shared, finite validated domain.

    Content hashes bind artifacts but do not decide equivalence.  An equivalent
    verdict includes a node correspondence whose complete remapped records match.
    Rejection/revision effects outside the accepted-Claim projection stay unknown.
    """
    result: dict[str, Any] = {
        "left_audit_id": left.get("id"),
        "right_audit_id": right.get("id"),
        "relation": "undetermined",
        "equivalent": None,
        "correspondence": None,
        "retained_difference_witness": None,
        "scope": "same task/context, protocol and registry; validated finite public event graphs",
        "historical_state_ids_or_assignments_reused": False,
        "content_hash_is_relation_authority": False,
    }
    try:
        _identity(left, "session_audit")
        _identity(right, "session_audit")
        require(
            all(
                item.get("validation_passed") is True
                and item.get("qualified") is True
                and item.get("trajectory_valid") is True
                and item.get("qa_valid") is True
                and item.get("errors") == []
                for item in (left, right)
            ),
            "comparison.unvalidated_or_unqualified",
        )
        require(
            all(
                left.get(key) is not None and left.get(key) == right.get(key)
                for key in ("context_id", "task_id", "protocol_id", "registry_hash")
            ),
            "comparison.context_task_protocol_registry_mismatch",
        )
        require(
            left.get("projection_supported") is True and right.get("projection_supported") is True,
            "comparison.unsupported_reject_or_revision_effect",
        )
        correspondence, witness = _isomorphism(
            left["finite_projection"], right["finite_projection"]
        )
        result.update(
            relation="equivalent" if correspondence is not None else "not_equivalent",
            equivalent=correspondence is not None,
            correspondence=correspondence,
            retained_difference_witness=witness,
        )
    except (ValueError, TypeError, KeyError, IndexError) as error:
        result["reason"] = str(error)
    return record("finite_comparison", **result)
