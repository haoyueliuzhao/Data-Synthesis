"""Generator callbacks submit semantic choices; Host admits but never selects a route."""

from __future__ import annotations

import copy
import hashlib
import inspect
import sys
from collections.abc import Callable
from decimal import Decimal, localcontext
from pathlib import Path
from types import CodeType
from typing import Any, Protocol

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter
from trusted_synthesis.experiments.qa_reasoning_part_whole_share.models import admit_inputs
from trusted_synthesis.experiments.qa_reasoning_part_whole_share.runtime import (
    RelationSumExecutor,
    ScalePercentExecutor,
    ShareRatioExecutor,
)

from .models import (
    CONTEXT_FIELDS,
    DYNAMIC_FIELDS,
    ProtocolError,
    initial_dynamic,
    parse_submission,
    record,
    require,
)
from .public_view import make_state, request_for


class PublicGenerator(Protocol):
    binding: dict[str, Any]

    def generate(self, request: dict[str, Any]) -> bytes: ...


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_callback(
    generator: PublicGenerator, binding: dict[str, Any]
) -> Callable[[dict[str, Any]], bytes]:
    """Bind the actual callable to admitted source bytes, not an origin label."""
    module = sys.modules.get(binding["module"])
    require(module is not None, "generator.loaded_module")
    cls = getattr(module, binding["class_name"], None)
    require(type(generator) is cls, "generator.actual_class")
    callback = getattr(generator, binding["method_name"])
    function = getattr(callback, "__func__", None)
    require(
        function is not None
        and getattr(callback, "__self__", None) is generator
        and function is getattr(cls, binding["method_name"])
        and function.__globals__ is vars(module)
        and function.__closure__ is None,
        "generator.bound_method",
    )
    assert cls is not None and function is not None
    path_name = inspect.getsourcefile(cls)
    require(path_name is not None, "generator.source_path")
    assert path_name is not None
    path = Path(path_name).resolve()
    require(str(path).endswith("/" + binding["source_path"]), "generator.source_path")
    payload = path.read_bytes()
    require(_sha(payload) == binding["source_sha256"], "generator.source_bytes")
    # Compilation inspects definitions without running module or callback code.
    code = compile(payload, function.__code__.co_filename, "exec")
    classes = [
        c for c in code.co_consts if isinstance(c, CodeType) and c.co_name == binding["class_name"]
    ]
    require(len(classes) == 1, "generator.compiled_class")
    methods = [
        c
        for c in classes[0].co_consts
        if isinstance(c, CodeType) and c.co_name == binding["method_name"]
    ]
    require(len(methods) == 1 and function.__code__ == methods[0], "generator.compiled_method")
    return callback


def _same_ids(submitted: list[str], expected: list[str]) -> bool:
    return len(submitted) == len(set(submitted)) and sorted(submitted) == sorted(set(expected))


def resolve_inputs(
    parsed: dict[str, Any], state: dict[str, Any], source: dict[str, Any]
) -> list[dict[str, Any]]:
    evidence = {e["id"]: e for e in source["evidence"].values()}
    claims = {c["id"]: c for c in state["accepted_claims"]}
    result = []
    for ref in parsed["inputs"]:
        base = {key: ref[key] for key in ("role", "kind", "ref_id")}
        if ref["kind"] == "evidence":
            require(ref["ref_id"] in evidence, "admission.visible_evidence")
            item = evidence[ref["ref_id"]]
            if item["kind"] == "part_whole":
                result.append({**base, "relation": copy.deepcopy(item), "lineage": [item["id"]]})
            else:
                result.append(
                    {
                        **base,
                        **{
                            key: item[key]
                            for key in ("value", "metric", "definition", *CONTEXT_FIELDS)
                        },
                        "lineage": [item["id"]],
                        "producer_operation": None,
                    }
                )
        else:
            require(ref["ref_id"] in claims, "admission.accepted_claim")
            claim = claims[ref["ref_id"]]
            require(claim["status"] == "accepted", "admission.accepted_claim")
            result.append(
                {
                    **base,
                    **copy.deepcopy(claim["proposition"]),
                    "producer_operation": claim["producer_operation"],
                }
            )
    return result


def prepare(
    parsed: dict[str, Any],
    state: dict[str, Any],
    protocol: dict[str, Any],
    source: dict[str, Any],
    legacy_contract: dict[str, Any],
) -> dict[str, Any]:
    """Pure admission; no execution, mutation, Oracle, route plan or automatic repair."""
    require(parsed["state_id"] == state["id"], "admission.current_state")
    require(state["phase"] != "terminal", "admission.terminal")
    require(
        state["submission_count"] < protocol["bounds"]["submissions"], "admission.submission_budget"
    )
    kind = parsed["kind"]
    if kind == "action":
        require(
            state["phase"] == "action" and state["pending_observation"] is None,
            "admission.pending_update",
        )
        require(state["action_count"] < protocol["bounds"]["actions"], "admission.action_budget")
        inputs = resolve_inputs(parsed, state, source)
        try:
            checks = admit_inputs(
                parsed["operation"], inputs, parsed["parameters"], legacy_contract, source
            )
        except ValueError as error:
            raise ProtocolError(getattr(error, "stage", "admission.operation_semantics")) from error
        basis = parsed["public_basis"]
        require(
            _same_ids(basis["evidence_refs"], [r for item in inputs for r in item["lineage"]])
            and _same_ids(
                basis["claim_refs"], [item["ref_id"] for item in inputs if item["kind"] == "claim"]
            )
            and basis["intended_metric"]
            == legacy_contract["operations"][parsed["operation"]]["output_metric"],
            "admission.public_basis",
        )
        return {"kind": kind, "inputs": inputs, "checks": checks}
    if kind == "update":
        require(
            state["phase"] == "update" and state["pending_observation"] is not None,
            "admission.no_pending_observation",
        )
        require(state["update_count"] < protocol["bounds"]["updates"], "admission.update_budget")
        observation = state["pending_observation"]
        basis = parsed["public_basis"]
        require(
            parsed["observation_id"] == observation["id"]
            and basis["observation_refs"] == [observation["id"]],
            "admission.observation_parent",
        )
        require(
            _same_ids(basis["evidence_refs"], observation["output"]["lineage"]),
            "admission.update_basis",
        )
        if parsed["disposition"] == "accept":
            require(
                basis["relation"] == "supports" and parsed["proposed_claim"] is not None,
                "admission.explicit_proposed_claim",
            )
            require(
                canonical_json_bytes(parsed["proposed_claim"])
                == canonical_json_bytes(observation["output"]),
                "admission.observed_claim_content",
            )
        else:
            require(
                basis["relation"] == "declines" and parsed["proposed_claim"] is None,
                "admission.reject_creates_no_claim",
            )
        return {
            "kind": kind,
            "disposition": parsed["disposition"],
            "observation": copy.deepcopy(observation),
        }
    require(
        kind == "final" and state["phase"] == "action" and state["pending_observation"] is None,
        "admission.final_phase",
    )
    claims = {c["id"]: c for c in state["accepted_claims"]}
    require(parsed["answer_claim_id"] in claims, "admission.final_accepted_claim")
    claim = claims[parsed["answer_claim_id"]]
    require(
        claim["status"] == "accepted"
        and claim["producer_operation"] == "scale_percent"
        and claim["proposition"]["metric"] == "freight_share_percent"
        and claim["proposition"]["unit"] == "percent",
        "admission.final_percent_claim",
    )
    with localcontext() as context:
        context.prec = legacy_contract["numeric"]["precision"]
        context.rounding = legacy_contract["numeric"]["rounding"]
        value = str(
            Decimal(claim["proposition"]["value"]).quantize(
                Decimal(legacy_contract["numeric"]["final_quantum"])
            )
        )
    require(
        parsed["answer"] == {"value": value, "unit": "percent"}
        and _same_ids(parsed["citations"], claim["grounding"])
        and parsed["public_basis"]["claim_refs"] == [claim["id"]]
        and _same_ids(parsed["public_basis"]["evidence_refs"], claim["grounding"]),
        "admission.final_grounding",
    )
    return {"kind": kind, "answer_claim": copy.deepcopy(claim)}


def preview(
    state: dict[str, Any],
    payload: bytes,
    protocol: dict[str, Any],
    source: dict[str, Any],
    legacy_contract: dict[str, Any],
) -> dict[str, Any]:
    """Direct interface control, never an executed candidate or committed update."""
    try:
        parsed = parse_submission(payload)
        admitted = prepare(parsed, state, protocol, source, legacy_contract)
    except ProtocolError as error:
        return {"admitted": False, "code": error.stage, "kernel_calls": 0, "committed_updates": 0}
    return {
        "admitted": True,
        "code": "admitted." + parsed["kind"],
        "kind": admitted["kind"],
        "would_create_claim": parsed["kind"] == "update" and parsed["disposition"] == "accept",
        "would_clear_pending": parsed["kind"] == "update",
        "kernel_calls": 0,
        "committed_updates": 0,
    }


class ProtocolEngine:
    """One host environment; external callback responses alone choose operations/updates."""

    def __init__(
        self,
        context: dict[str, Any],
        protocol: dict[str, Any],
        source: dict[str, Any],
        legacy_contract: dict[str, Any],
        generator_binding: dict[str, Any],
        output_directory: Path,
    ) -> None:
        require(
            protocol["public_context_id"] == context["id"]
            and context["task"]["id"] == legacy_contract["task"]["id"]
            and source["id"] == legacy_contract["source_binding_id"],
            "session.frozen_context",
        )
        require(generator_binding["kind"] == "deterministic_fixture", "session.generator_origin")
        self.context, self.protocol, self.source, self.legacy_contract, self.generator_binding = (
            copy.deepcopy((context, protocol, source, legacy_contract, generator_binding))
        )
        self.writer = DurableArtifactWriter(output_directory)
        self.writer.create_root()
        self.state = make_state(self.context, self.protocol, initial_dynamic())
        self.writer.write_json("initial_state.json", self.state)
        self.events: list[dict[str, Any]] = []
        self.event_paths: list[dict[str, str]] = []
        self.kernel_calls = 0

    def current_state(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)

    def exchange(self, generator: PublicGenerator) -> dict[str, Any]:
        require(generator.binding == self.generator_binding, "generator.unregistered_binding")
        callback = verify_callback(generator, self.generator_binding)
        require(self.state["phase"] != "terminal", "session.terminal")
        request = request_for(self.state, self.protocol)
        index = len(self.events)
        paths: dict[str, str] = {}

        def persist(name: str, obj: dict[str, Any]) -> bytes:
            relative = f"turns/{index:02d}_{name}.json"
            paths[name] = relative
            return self.writer.write_json(relative, obj)

        request_bytes = persist("request", request)
        raw: bytes | None = None
        callback_error = None
        try:
            raw = callback(copy.deepcopy(request))
            require(isinstance(raw, bytes), "generator.response_bytes")
        except Exception:
            callback_error = "generator.callback_failure"
            raw = None
        require(
            self.writer.read_bytes(paths["request"]) == request_bytes, "generator.request_mutation"
        )
        turn = record(
            "generator_turn",
            request_id=request["id"],
            state_id=self.state["id"],
            generator_binding_id=self.generator_binding["id"],
            origin="deterministic_fixture",
            response_sha256=_sha(raw) if raw is not None else None,
            response_byte_count=len(raw) if raw is not None else 0,
            callback_error=callback_error,
            provider_calls=0,
            host_supplied_response=False,
        )
        persist("generator_turn", turn)
        parsed = None
        admission = None
        code = callback_error
        if raw is not None:
            try:
                parsed = parse_submission(raw)
            except ProtocolError as error:
                code = error.stage
        # Only the exact typed public grammar is retained as raw text. A malformed
        # response is bound by hash/count, not serialized as arbitrary private text.
        submission = record(
            "submission",
            generator_turn_id=turn["id"],
            request_id=request["id"],
            state_id=self.state["id"],
            parsed=parsed,
            raw_public_json=raw.decode("utf-8") if parsed is not None and raw is not None else None,
            response_sha256=turn["response_sha256"],
            response_byte_count=turn["response_byte_count"],
            field_origin="deterministic_fixture",
            host_repairs=[],
        )
        submission_bytes = persist("submission", submission)
        if parsed is not None:
            try:
                admission = prepare(
                    parsed, self.state, self.protocol, self.source, self.legacy_contract
                )
                code = "admitted." + parsed["kind"]
            except ProtocolError as error:
                code = error.stage
        receipt = record(
            "receipt",
            submission_id=submission["id"],
            request_id=request["id"],
            pre_state_id=self.state["id"],
            admitted=admission is not None,
            code=code,
            dispatch_permitted=admission is not None
            and parsed is not None
            and parsed["kind"] == "action",
            submission_sha256=_sha(submission_bytes),
            submission_byte_count=len(submission_bytes),
            no_replace=True,
            missing_fields_filled=False,
            response_rewritten=False,
        )
        receipt_bytes = persist("receipt", receipt)
        require(
            self.writer.read_bytes(paths["submission"]) == submission_bytes
            and self.writer.read_bytes(paths["receipt"]) == receipt_bytes,
            "dispatch.precommit_bytes",
        )
        before = copy.deepcopy(self.state)
        dynamic = copy.deepcopy({k: before[k] for k in DYNAMIC_FIELDS})
        dynamic["submission_count"] += 1
        execution = observation = claim = final = None
        if admission is None:
            dynamic["last_feedback"] = {"code": code}
        else:
            assert parsed is not None
            kind = parsed["kind"]
            if kind == "action":
                operation = parsed["operation"]
                inputs = admission["inputs"]
                kernels = {
                    "relation_sum": RelationSumExecutor,
                    "share_ratio": ShareRatioExecutor,
                    "scale_percent": ScalePercentExecutor,
                }
                with localcontext() as context:
                    context.prec = self.legacy_contract["numeric"]["precision"]
                    context.rounding = self.legacy_contract["numeric"]["rounding"]
                    value = kernels[operation]().execute(inputs)
                self.kernel_calls += 1
                require(value.is_finite(), "dispatch.nonfinite")
                op = self.legacy_contract["operations"][operation]
                definitions = {
                    "relation_sum": self.source["evidence"]["total"]["definition"],
                    "share_ratio": "freight divided by legitimate operating revenue total",
                    "scale_percent": "freight share in percent",
                }
                output = {
                    **{k: self.source["evidence"]["freight"][k] for k in CONTEXT_FIELDS},
                    "value": str(value),
                    "metric": op["output_metric"],
                    "unit": op["output_unit"],
                    "definition": definitions[operation],
                    "lineage": sorted({r for item in inputs for r in item["lineage"]}),
                }
                execution = record(
                    "execution",
                    submission_id=submission["id"],
                    generator_turn_id=turn["id"],
                    operation=operation,
                    operation_contract_id=op["id"],
                    parameters=parsed["parameters"],
                    inputs=inputs,
                    output=output,
                    field_origin="host_derived",
                )
                persist("execution", execution)
                observation = record(
                    "observation",
                    execution_id=execution["id"],
                    action_submission_id=submission["id"],
                    operation=operation,
                    output=output,
                    success=True,
                    field_origin="host_derived",
                )
                persist("observation", observation)
                dynamic.update(
                    phase="update",
                    pending_observation=observation,
                    action_count=dynamic["action_count"] + 1,
                    last_feedback={"code": "observation_ready"},
                )
            elif kind == "update":
                pending = before["pending_observation"]
                if parsed["disposition"] == "accept":
                    claim = record(
                        "claim",
                        task_id=self.context["task"]["id"],
                        observation_id=pending["id"],
                        update_submission_id=submission["id"],
                        generator_turn_id=turn["id"],
                        proposition=copy.deepcopy(parsed["proposed_claim"]),
                        grounding=copy.deepcopy(parsed["proposed_claim"]["lineage"]),
                        producer_operation=pending["operation"],
                        status="accepted",
                        field_origin="deterministic_fixture",
                    )
                    persist("claim", claim)
                    dynamic["accepted_claims"].append(claim)
                dynamic.update(
                    phase="action",
                    pending_observation=None,
                    update_count=dynamic["update_count"] + 1,
                    last_feedback={
                        "code": "claim_accepted" if claim is not None else "observation_rejected"
                    },
                )
            else:
                final = record(
                    "final",
                    task_id=self.context["task"]["id"],
                    submission_id=submission["id"],
                    generator_turn_id=turn["id"],
                    answer=copy.deepcopy(parsed["answer"]),
                    answer_claim_id=parsed["answer_claim_id"],
                    citations=copy.deepcopy(parsed["citations"]),
                    field_origin="deterministic_fixture",
                )
                persist("final", final)
                dynamic.update(
                    phase="terminal",
                    terminal="final_submitted",
                    last_feedback={"code": "final_submitted"},
                )
        if (
            dynamic["submission_count"] >= self.protocol["bounds"]["submissions"]
            and dynamic["phase"] != "terminal"
        ):
            dynamic.update(
                phase="terminal",
                terminal="submission_budget_exhausted",
                pending_observation=None,
                last_feedback={"code": "submission_budget_exhausted"},
            )
        after = make_state(self.context, self.protocol, dynamic)
        persist("post_state", after)
        event = record(
            "event",
            sequence=index,
            pre_state_id=before["id"],
            post_state_id=after["id"],
            request_id=request["id"],
            generator_turn_id=turn["id"],
            submission_id=submission["id"],
            receipt_id=receipt["id"],
            execution_id=execution["id"] if execution else None,
            observation_id=observation["id"] if observation else None,
            claim_id=claim["id"] if claim else None,
            final_id=final["id"] if final else None,
        )
        persist("event", event)
        bundle = {
            "event": event,
            "request": request,
            "generator_turn": turn,
            "submission": submission,
            "receipt": receipt,
            "execution": execution,
            "observation": observation,
            "claim": claim,
            "final": final,
            "post_state": after,
        }
        self.events.append(copy.deepcopy(bundle))
        self.event_paths.append(paths)
        self.state = copy.deepcopy(after)
        return copy.deepcopy(bundle)

    def finish(self) -> dict[str, Any]:
        members = []
        for path in sorted(self.writer.root.rglob("*.json")):
            data = path.read_bytes()
            members.append(
                {
                    "relative_path": path.relative_to(self.writer.root).as_posix(),
                    "sha256": _sha(data),
                    "byte_count": len(data),
                }
            )
        manifest = record(
            "session_manifest",
            protocol_id=self.protocol["id"],
            public_context_id=self.context["id"],
            generator_binding_id=self.generator_binding["id"],
            initial_state="initial_state.json",
            events=self.event_paths,
            members=members,
            kernel_calls=self.kernel_calls,
            generator_callbacks=len(self.events),
            write_events=list(self.writer.events),
            positive_protocol_sessions=1,
            Provider_calls=0,
        )
        self.writer.write_json("session_manifest.json", manifest)
        return manifest
