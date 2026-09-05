"""Model submissions cross unchanged admission; Provider attempts have their own ledger."""

from __future__ import annotations

import copy
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, cast

from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter
from trusted_synthesis.experiments.qa_reasoning_part_whole_share.runtime import (
    RelationSumExecutor,
    ScalePercentExecutor,
    ShareRatioExecutor,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.engine import (
    prepare,
    verify_callback,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import (
    CONTEXT_FIELDS,
    DYNAMIC_FIELDS,
    ProtocolError,
    initial_dynamic,
    parse_submission,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import (
    record as core_record,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.public_view import (
    make_state,
    request_for,
)

from .adapter import render_http_request
from .models import record, require, sha


class ModelProtocolEngine:
    def __init__(
        self,
        *,
        context: dict[str, Any],
        protocol: dict[str, Any],
        source: dict[str, Any],
        legacy_contract: dict[str, Any],
        adapter_binding: dict[str, Any],
        model_config: dict[str, Any],
        session_registration: dict[str, Any],
        output_directory: Path,
    ) -> None:
        (
            self.context,
            self.protocol,
            self.source,
            self.legacy_contract,
            self.binding,
            self.config,
            self.registration,
        ) = copy.deepcopy(
            (
                context,
                protocol,
                source,
                legacy_contract,
                adapter_binding,
                model_config,
                session_registration,
            )
        )
        require(
            self.registration["protocol_id"] == self.protocol["id"]
            and self.registration["model_configuration_id"] == self.config["id"],
            "pilot.session_registration",
        )
        self.origin = self.registration["generator_origin"]
        require(self.origin in {"model", "adapter_mock"}, "pilot.generator_origin")
        require(self.binding["origin"] == self.origin, "pilot.adapter_origin")
        require(
            self.binding["model_configuration_id"] == self.config["id"]
            and self.protocol["model_configuration_id"] == self.config["id"]
            and self.protocol["public_context_id"] == self.context["id"]
            and self.context["task"]["id"] == self.legacy_contract["task"]["id"]
            and self.source["id"] == self.legacy_contract["source_binding_id"],
            "pilot.source_context_binding",
        )
        self.session_id = self.registration["id"]
        self.writer = DurableArtifactWriter(output_directory)
        self.writer.create_root()
        self.state = make_state(self.context, self.protocol, initial_dynamic())
        self.writer.write_json("initial_state.json", self.state)
        self.events: list[dict[str, Any]] = []
        self.event_paths: list[dict[str, str]] = []
        self.attempts: list[dict[str, Any]] = []
        self.kernel_calls = 0

    def current_state(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)

    def exchange(self, adapter: Any, *, api_key: str | None = None) -> dict[str, Any]:
        require(adapter.binding == self.binding, "pilot.registered_adapter")
        callback = cast(Any, verify_callback(adapter, self.binding["adapter_callback"]))
        require(self.state["phase"] != "terminal", "pilot.session_terminal")
        require(len(self.attempts) < self.config["attempts_per_session"], "pilot.attempt_budget")
        index = len(self.events)
        paths: dict[str, str] = {}

        def persist(name: str, obj: dict[str, Any]) -> bytes:
            relative = f"turns/{index:02d}_{name}.json"
            paths[name] = relative
            return self.writer.write_json(relative, obj)

        request = request_for(self.state, self.protocol)
        persist("request", request)
        call = record(
            "call_declaration",
            session_id=self.session_id,
            turn_index=index,
            public_request_id=request["id"],
            state_id=self.state["id"],
            adapter_binding_id=self.binding["id"],
        )
        http_request = render_http_request(
            request,
            self.config,
            session_id=self.session_id,
            turn_index=index,
            call_id=call["id"],
        )
        persist("call_declaration", call)
        http_bytes = persist("provider_request", http_request)

        def reserve(actual_request: dict[str, Any]) -> dict[str, Any]:
            require(actual_request == http_request, "pilot.actual_request_binding")
            require(len(self.attempts) == index, "pilot.no_second_send_same_turn")
            require(
                self.writer.read_bytes(paths["provider_request"]) == http_bytes,
                "pilot.pre_attempt_request_bytes",
            )
            attempt = record(
                "provider_attempt",
                session_id=self.session_id,
                ordinal=len(self.attempts) + 1,
                turn_index=index,
                call_id=call["id"],
                request_id=http_request["id"],
                public_request_id=request["id"],
                state_id=self.state["id"],
                phase=self.state["phase"],
                adapter_binding_id=self.binding["id"],
                model_configuration_id=self.config["id"],
                origin=self.origin,
                provider_attempts_consumed=1 if self.origin == "model" else 0,
                mock_attempts_consumed=1 if self.origin == "adapter_mock" else 0,
                reserved_token_allowance=self.config["maximum_request_reserved_tokens"],
                cumulative_reserved_tokens=(len(self.attempts) + 1)
                * self.config["maximum_request_reserved_tokens"],
                request_artifact_sha256=sha(http_bytes),
                request_artifact_bytes=len(http_bytes),
                counted_before_send=True,
                automatic_retries=0,
            )
            saved = persist("provider_attempt", attempt)
            require(
                self.writer.read_bytes(paths["provider_attempt"]) == saved, "pilot.attempt_commit"
            )
            self.attempts.append(copy.deepcopy(attempt))
            return attempt

        result = callback(copy.deepcopy(http_request), api_key=api_key, reserve=reserve)
        require(result["request"] == http_request, "pilot.returned_request_binding")
        require(
            len(self.attempts) == index + 1 and result["reservation"] == self.attempts[-1],
            "pilot.actual_attempt_binding",
        )
        response = result["response"]
        require(
            response["request_id"] == http_request["id"]
            and response["attempt_id"] == self.attempts[-1]["id"]
            and response["session_id"] == self.session_id
            and response["state_id"] == self.state["id"]
            and response["phase"] == self.state["phase"]
            and response["public_request_id"] == request["id"]
            and response["call_id"] == call["id"]
            and response["turn_index"] == index
            and response["model_configuration_id"] == self.config["id"]
            and response["transport_binding_id"] == self.binding["transport_binding"]["id"]
            and response["generator_origin"] == self.origin,
            "pilot.provider_response_parents",
        )
        persist("provider_response", response)
        raw = result["public_content"]
        require(raw is None or isinstance(raw, bytes), "pilot.public_response_type")
        require(
            response["public_content_sha256"] == (sha(raw) if raw is not None else None)
            and response["public_content_bytes"] == (len(raw) if raw is not None else None),
            "pilot.public_content_binding",
        )
        turn = core_record(
            "generator_turn",
            request_id=request["id"],
            state_id=self.state["id"],
            generator_binding_id=self.binding["id"],
            origin=self.origin,
            response_sha256=sha(raw) if raw is not None else None,
            response_byte_count=len(raw) if raw is not None else 0,
            callback_error=response["code"] if raw is None else None,
            provider_calls=1 if self.origin == "model" else 0,
            host_supplied_response=False,
            session_id=self.session_id,
            provider_attempt_id=self.attempts[-1]["id"],
            provider_response_id=response["id"],
        )
        persist("generator_turn", turn)
        before = copy.deepcopy(self.state)
        dynamic = copy.deepcopy({k: before[k] for k in DYNAMIC_FIELDS})
        submission = receipt = execution = observation = claim = final = None
        if raw is None:
            code = response["code"] or "provider.public_content_unavailable"
            dynamic.update(
                phase="terminal",
                pending_observation=None,
                terminal=code,
                last_feedback={"code": code},
            )
        else:
            parsed = admission = None
            try:
                parsed = parse_submission(raw)
                parse_code = "schema.valid"
            except ProtocolError as error:
                parse_code = error.stage
            except RecursionError:
                parse_code = "schema.public_submission"
            require(
                response["parser_status"] == ("valid" if parsed is not None else "invalid")
                and response["parser_code"] == parse_code,
                "pilot.parser_diagnosis_consistency",
            )
            submission = core_record(
                "submission",
                generator_turn_id=turn["id"],
                request_id=request["id"],
                state_id=before["id"],
                parsed=parsed,
                raw_public_json=raw.decode("utf-8") if parsed is not None else None,
                response_sha256=sha(raw),
                response_byte_count=len(raw),
                field_origin=self.origin,
                host_repairs=[],
            )
            submission_bytes = persist("submission", submission)
            code = parse_code
            if parsed is not None:
                try:
                    admission = prepare(
                        parsed, before, self.protocol, self.source, self.legacy_contract
                    )
                    code = "admitted." + parsed["kind"]
                except ProtocolError as error:
                    code = error.stage
            receipt = core_record(
                "receipt",
                submission_id=submission["id"],
                request_id=request["id"],
                pre_state_id=before["id"],
                admitted=admission is not None,
                code=code,
                dispatch_permitted=admission is not None
                and parsed is not None
                and parsed["kind"] == "action",
                submission_sha256=sha(submission_bytes),
                submission_byte_count=len(submission_bytes),
                no_replace=True,
                missing_fields_filled=False,
                response_rewritten=False,
            )
            receipt_bytes = persist("receipt", receipt)
            require(
                self.writer.read_bytes(paths["submission"]) == submission_bytes
                and self.writer.read_bytes(paths["receipt"]) == receipt_bytes,
                "pilot.pre_dispatch_bytes",
            )
            dynamic["submission_count"] += 1
            if admission is None:
                dynamic["last_feedback"] = {"code": code}
            else:
                assert parsed is not None
                kind = parsed["kind"]
                if kind == "action":
                    operation, inputs = parsed["operation"], admission["inputs"]
                    kernels = {
                        "relation_sum": RelationSumExecutor,
                        "share_ratio": ShareRatioExecutor,
                        "scale_percent": ScalePercentExecutor,
                    }
                    with localcontext() as numeric_context:
                        numeric_context.prec = self.legacy_contract["numeric"]["precision"]
                        numeric_context.rounding = self.legacy_contract["numeric"]["rounding"]
                        value: Decimal = kernels[operation]().execute(inputs)
                    self.kernel_calls += 1
                    require(value.is_finite(), "pilot.nonfinite_output")
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
                    execution = core_record(
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
                    observation = core_record(
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
                        claim = core_record(
                            "claim",
                            task_id=self.context["task"]["id"],
                            observation_id=pending["id"],
                            update_submission_id=submission["id"],
                            generator_turn_id=turn["id"],
                            proposition=copy.deepcopy(parsed["proposed_claim"]),
                            grounding=copy.deepcopy(parsed["proposed_claim"]["lineage"]),
                            producer_operation=pending["operation"],
                            status="accepted",
                            field_origin=self.origin,
                        )
                        persist("claim", claim)
                        dynamic["accepted_claims"].append(claim)
                    dynamic.update(
                        phase="action",
                        pending_observation=None,
                        update_count=dynamic["update_count"] + 1,
                        last_feedback={
                            "code": "claim_accepted"
                            if claim is not None
                            else "observation_rejected"
                        },
                    )
                else:
                    final = core_record(
                        "final",
                        task_id=self.context["task"]["id"],
                        submission_id=submission["id"],
                        generator_turn_id=turn["id"],
                        answer=copy.deepcopy(parsed["answer"]),
                        answer_claim_id=parsed["answer_claim_id"],
                        citations=copy.deepcopy(parsed["citations"]),
                        field_origin=self.origin,
                    )
                    persist("final", final)
                    dynamic.update(
                        phase="terminal",
                        terminal="final_submitted",
                        last_feedback={"code": "final_submitted"},
                    )
            if dynamic["phase"] != "terminal" and (
                dynamic["submission_count"] >= self.protocol["bounds"]["submissions"]
                or len(self.attempts) >= self.config["attempts_per_session"]
            ):
                code = (
                    "submission_budget_exhausted"
                    if dynamic["submission_count"] >= self.protocol["bounds"]["submissions"]
                    else "provider_attempt_budget_exhausted"
                )
                dynamic.update(
                    phase="terminal",
                    terminal=code,
                    pending_observation=None,
                    last_feedback={"code": code},
                )
        after = make_state(self.context, self.protocol, dynamic)
        persist("post_state", after)
        event = core_record(
            "event",
            sequence=index,
            pre_state_id=before["id"],
            post_state_id=after["id"],
            request_id=request["id"],
            generator_turn_id=turn["id"],
            submission_id=submission["id"] if submission else None,
            receipt_id=receipt["id"] if receipt else None,
            execution_id=execution["id"] if execution else None,
            observation_id=observation["id"] if observation else None,
            claim_id=claim["id"] if claim else None,
            final_id=final["id"] if final else None,
        )
        persist("event", event)
        bundle = dict(
            event=event,
            request=request,
            call_declaration=call,
            provider_request=http_request,
            provider_attempt=self.attempts[-1],
            provider_response=response,
            generator_turn=turn,
            submission=submission,
            receipt=receipt,
            execution=execution,
            observation=observation,
            claim=claim,
            final=final,
            post_state=after,
        )
        self.events.append(copy.deepcopy(bundle))
        self.event_paths.append(paths)
        self.state = copy.deepcopy(after)
        return copy.deepcopy(bundle)

    def finish(self) -> dict[str, Any]:
        stop = record(
            "session_stop",
            session_id=self.session_id,
            state_id=self.state["id"],
            terminal=self.state["terminal"],
            terminal_recorded=self.state["phase"] == "terminal",
            callback_attempts=len(self.attempts),
            provider_attempts=len(self.attempts) if self.origin == "model" else 0,
            public_submission_attempts=self.state["submission_count"],
            completed_events=len(self.events),
            automatic_retries=0,
            session_replacements=0,
        )
        self.writer.write_json("session_stop.json", stop)
        members = []
        for path in sorted(self.writer.root.rglob("*.json")):
            payload = path.read_bytes()
            members.append(
                {
                    "relative_path": path.relative_to(self.writer.root).as_posix(),
                    "sha256": sha(payload),
                    "byte_count": len(payload),
                }
            )
        manifest = core_record(
            "session_manifest",
            protocol_id=self.protocol["id"],
            public_context_id=self.context["id"],
            generator_binding_id=self.binding["id"],
            initial_state="initial_state.json",
            events=self.event_paths,
            members=members,
            kernel_calls=self.kernel_calls,
            generator_callbacks=len(self.attempts),
            write_events=list(self.writer.events),
            session_id=self.session_id,
            model_configuration_id=self.config["id"],
            origin=self.origin,
            provider_attempts=len(self.attempts) if self.origin == "model" else 0,
            public_submission_attempts=self.state["submission_count"],
            stop_record="session_stop.json",
        )
        self.writer.write_json("session_manifest.json", manifest)
        return manifest
