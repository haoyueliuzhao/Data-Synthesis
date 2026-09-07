"""Versioned ownership-aware runtime with raw-response, expansion and receipt separation."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import parse, record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime

from .adapters import OpenAdapter
from .interface import (
    VERSION,
    References,
    binding_record,
    expand_acceptance,
    expand_selection,
    feedback,
    final_rules,
    parse_compact,
    result_schema,
    schemas,
)


class StudyRuntime(PublicQARuntime):
    """Reuse H0/H1 admission exactly; keep compact raw bytes as the only model output."""

    def __init__(self, base, group, condition, callback, output_directory: Path):
        require(group in {"S", "B"} and condition in {"H0", "H1", "H2"}, "study.condition")
        self.base, self.group, self.condition = base, group, condition
        self.refs = References(base, group)
        adapter = OpenAdapter(base, group) if condition == "H2" else base
        super().__init__(adapter, callback, output_directory, max_submissions=32, max_actions=12)
        self.compact_contract = record(
            "compact_protocol",
            version=VERSION,
            condition=condition,
            schemas=schemas(group, condition),
            acceptance=(
                "Explicit accept means accepting the ENTIRE selected observation proposition."
            ),
            reference_rule=(
                "Exact current-session aliases only. No fuzzy matching or inferred reference."
            ),
            ownership="Raw model response and SYSTEM-derived expansion are separately recorded.",
        )
        self.store.json("study_protocol.json", self.compact_contract)
        self.store.json("base_context.json", base.context)

    def structured_request(self):
        request = super().request()
        fields = {
            key: value for key, value in request.items() if key not in {"id", "schema_version"}
        }
        fields["response_schemas"]["final"]["properties"]["result"] = result_schema(self.group)
        fields["public_final_contract"] = final_rules(self.group, False)
        return record("request", **fields)

    def request(self):
        original = self.structured_request()
        if self.condition == "H0":
            return original
        for claim in self.claims:
            self.refs.add(claim["id"], "C")
        if self.pending:
            self.refs.add(self.pending["id"], "O")
        for offer in original["available_actions"]:
            self.refs.add(offer["id"], "A")
        context = self.refs.render(copy.deepcopy(self.adapter.context))
        context = record(
            "compact_context",
            base_context_id=context.pop("id"),
            **{key: value for key, value in context.items() if key != "schema_version"},
        )
        state = self.refs.render(self.state())
        state = record(
            "compact_state",
            **{
                key: value
                for key, value in state.items()
                if key not in {"id", "schema_version", "protocol_id", "context_id"}
            },
            context_id=context["id"],
            protocol_id=self.compact_contract["id"],
        )
        fields = {
            "protocol_id": self.compact_contract["id"],
            "context": context,
            "state": state,
            "response_state_id": f"T{self.submissions}",
            "response_schemas": schemas(self.group, self.condition),
            "public_final_contract": final_rules(self.group, True),
            "language": {
                "acceptance": self.compact_contract["acceptance"],
                "reference_rule": self.compact_contract["reference_rule"],
                "state_id": "Copy response_state_id into every submission's state_id.",
                "system_derived_fields": "Reference expansion, observation contents and H1 "
                "state-implied transition fields are SYSTEM bindings, "
                "not model-generated decisions.",
                "next_action": "Acceptance executes no next action. "
                "You must choose/propose it separately.",
            },
            "final_claim_ids": self.refs.render(original["final_claim_ids"]),
        }
        if self.condition == "H1":
            fields["available_actions"] = self.refs.render(original["available_actions"])
            fields["system_derived_transition_options"] = self.refs.render(
                original["update_transition_options"]
            )
            fields["language"]["action"] = "Choose exactly one available_actions id in action."
        else:
            fields["language"]["action"] = (
                "Propose a short subgoal and reason tied to your selected operation and ordered "
                "input references. Tools are an unordered catalogue, not a next-step list. "
                "Use only raw Evidence or accepted Claims; Observations are not inputs."
            )
        return record("compact_request", **fields)

    def bind_and_admit(self, raw, request):
        if self.condition == "H0":
            submitted = parse(raw)
            return submitted, submitted, PublicQARuntime._admit(self, submitted, request)
        submitted = parse_compact(raw, self.condition)
        require(submitted["state_id"] == request["response_state_id"], "admission.current_state")
        original = self.structured_request()
        kind = submitted["kind"]
        if kind == "action":
            require(
                self.pending is None and not self.terminal and self.actions < 12,
                "admission.action_phase_budget",
            )
            if self.condition == "H1":
                selected = self.refs.decode(submitted["action"], "A")
                expanded = expand_selection(selected, original)
                admitted = PublicQARuntime._admit(self, expanded, original)
            else:
                expanded = copy.deepcopy(submitted)
                expanded["state_id"] = self.state()["id"]
                expanded["inputs"] = [
                    self.refs.decode(key, ("E", "C")) for key in submitted["inputs"]
                ]
                option = self.adapter.proposal(expanded, self.claims)
                admitted = {"option": option, "prepared": self.adapter.prepare(option, self.claims)}
        elif kind == "update":
            require(self.pending is not None, "admission.pending_observation")
            observation = self.refs.decode(submitted["observation"], "O")
            require(observation == self.pending["id"], "admission.observation_parent")
            if self.condition == "H1":
                expanded = expand_acceptance(self.pending, submitted["disposition"], original)
                admitted = PublicQARuntime._admit(self, expanded, original)
            else:
                expanded = {
                    "kind": "update",
                    "state_id": self.state()["id"],
                    "observation_id": observation,
                    "disposition": submitted["disposition"],
                    "proposed_claim": copy.deepcopy(self.pending["proposition"])
                    if submitted["disposition"] == "accept"
                    else None,
                }
                admitted = {"observation": copy.deepcopy(self.pending)}
        else:
            expanded = copy.deepcopy(submitted)
            expanded["state_id"] = self.state()["id"]
            expanded["answer_claim_id"] = self.refs.decode(submitted["answer_claim_id"], "C")
            expanded["citations"] = [self.refs.decode(key, "E") for key in submitted["citations"]]
            admitted = PublicQARuntime._admit(self, expanded, original)
        return submitted, expanded, admitted

    def _consume(self, raw, request):
        index, prefix = self.submissions, f"turns/{self.submissions:03d}_"
        self.store.write(prefix + "response.txt", raw)
        submission = record(
            "submission",
            request_id=request["id"],
            raw_sha256=hashlib.sha256(raw).hexdigest(),
            raw_bytes=len(raw),
            callback_binding=self.callback.binding,
            host_repairs=[],
        )
        self.store.json(prefix + "submission.json", submission)
        submitted = expanded = admitted = None
        try:
            # Preserve syntactically valid model objects even if later admission fails.
            submitted = parse(raw) if self.condition == "H0" else parse_compact(raw, self.condition)
            submitted, expanded, admitted = self.bind_and_admit(raw, request)
        except (ValueError, KeyError, TypeError, ArithmeticError) as error:
            code = str(error)
        else:
            code = None
        binding = binding_record(self.condition, raw, submitted, expanded, self.refs)
        self.store.json(prefix + "language_binding.json", binding)
        receipt = record(
            "receipt",
            submission_id=submission["id"],
            request_id=request["id"],
            state_id=request["state"]["id"],
            admitted=admitted is not None,
            error_code=code,
            language_binding_id=binding["id"],
            no_host_semantic_repair=True,
        )
        self.store.json(prefix + "receipt.json", receipt)
        event = {
            "sequence": index,
            "request": request,
            "submission": submission,
            "parsed": submitted,
            "language_binding": binding,
            "receipt": receipt,
        }
        self.submissions += 1
        if admitted is None:
            self.feedback = feedback(code, request, submitted, self.group, self.condition)
        elif submitted["kind"] == "action":
            require(
                (self.store.root / (prefix + "receipt.json")).read_bytes()
                == canonical_json_bytes(receipt)
                and (self.store.root / (prefix + "response.txt")).read_bytes() == raw
                and (self.store.root / (prefix + "language_binding.json")).read_bytes()
                == canonical_json_bytes(binding),
                "runtime.pre_dispatch_readback",
            )
            self.store.events.append({"kind": "pre_dispatch_readback", "sequence": index})
            self.store.events.append({"kind": "execution_dispatch", "sequence": index})
            self.actions += 1
            try:
                proposition = self.adapter.execute(admitted["prepared"])
                require(
                    self.adapter.verify_execution(admitted["prepared"], proposition),
                    "execution.independent_output",
                )
            except (ValueError, KeyError, TypeError, ArithmeticError) as error:
                self.terminal = True
                self.feedback = {"code": "execution_failed", "detail": str(error)}
                event["execution_error"] = str(error)
            else:
                option = admitted["option"]
                execution = record(
                    "execution",
                    action_submission_id=submission["id"],
                    receipt_id=receipt["id"],
                    selected_action=option,
                    resolved_inputs=[
                        item.model_dump(mode="json") for item in admitted["prepared"]["inputs"]
                    ],
                    proposition=proposition,
                    success=True,
                )
                self.store.json(prefix + "execution.json", execution)
                observation = record(
                    "observation",
                    action_submission_id=submission["id"],
                    execution_id=execution["id"],
                    receipt_id=receipt["id"],
                    obligation_id=option["obligation_id"],
                    selected_action=option,
                    proposition=proposition,
                    independent_output_valid=True,
                )
                self.store.json(prefix + "observation.json", observation)
                event.update(execution=execution, observation=observation)
                self.pending = observation
                self.feedback = {
                    "code": "pending_observation_requires_callback_update",
                    "admitted": True,
                }
        elif submitted["kind"] == "update":
            self.updates += 1
            if submitted["disposition"] == "accept":
                claim = self._claim(admitted["observation"])
                self.store.json(prefix + "claim.json", claim)
                self.claims.append(claim)
                event["claim"] = claim
            self.pending = None
            self.feedback = {
                "code": "claim_accepted"
                if submitted["disposition"] == "accept"
                else "observation_declined",
                "admitted": True,
            }
        else:
            self.final = record(
                "final",
                submission_id=submission["id"],
                answer=expanded,
                model_answer=submitted,
                qa_validation=admitted["validation"],
            )
            self.store.json(prefix + "final.json", self.final)
            event["final"] = self.final
            self.terminal = True
            self.feedback = {"code": "complete", "admitted": True}
        event["post_state"] = self.state()
        self.store.json(prefix + "event.json", event)
        self.events.append(event)
        return copy.deepcopy(event)

    # The inherited run() persists original callback bytes, termination and manifests.
    # Its protocol.json is the internal H0 execution contract. study_protocol.json and
    # each actual public Request are the authority for the compact model language.
