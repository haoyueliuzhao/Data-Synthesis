"""One callback-driven runtime for every registered Finance QA adapter."""

from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
from typing import Any, Protocol

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.operations.registry import OperationRegistry

from .protocol import ProtocolError, contract, parse, record, require


class Callback(Protocol):
    binding: dict[str, Any]

    def generate(self, request: dict[str, Any]) -> bytes: ...


class TaskAdapter(Protocol):
    registry: OperationRegistry
    context: dict[str, Any]

    def offers(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]: ...

    def prepare(self, offer: dict[str, Any], claims: list[dict[str, Any]]) -> Any: ...

    def execute(self, prepared: Any) -> dict[str, Any]: ...

    def verify_execution(self, prepared: Any, proposition: dict[str, Any]) -> bool: ...

    def final_claims(self, claims: list[dict[str, Any]]) -> list[str]: ...

    def verify_final(
        self, final: dict[str, Any], claims: list[dict[str, Any]]
    ) -> dict[str, Any]: ...


class DurableStore:
    """Exclusive files, file+directory fsync, and pre-dispatch byte readback."""

    def __init__(self, root: Path):
        self._mkdir(root, exclusive=True)
        self.root = root
        self.events: list[dict[str, Any]] = []

    @staticmethod
    def _sync(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @classmethod
    def _mkdir(cls, path: Path, *, exclusive: bool = False) -> None:
        missing = []
        ancestor = path
        while not ancestor.exists():
            missing.append(ancestor)
            ancestor = ancestor.parent
        path.mkdir(parents=True, exist_ok=not exclusive)
        # A synced file and leaf directory do not persist newly created ancestor
        # directory entries. Flush each creating parent before any dispatch.
        for created in reversed(missing):
            cls._sync(created.parent)

    def write(self, path: str, data: bytes) -> None:
        target = self.root / path
        require(
            not Path(path).is_absolute() and ".." not in Path(path).parts, "store.relative_path"
        )
        self._mkdir(target.parent)
        with target.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        self.events.append({"kind": "file_fsync", "path": path})
        self._sync(target.parent)
        self.events.append({"kind": "directory_fsync", "path": path})
        require(target.read_bytes() == data, "store.readback")

    def json(self, path: str, value: Any) -> None:
        self.write(path, canonical_json_bytes(value))


class PublicQARuntime:
    """Host validates callback-owned judgments; only accepted Updates unlock dependencies."""

    def __init__(
        self,
        adapter: TaskAdapter,
        callback: Callback,
        output_directory: Path,
        *,
        max_submissions: int = 96,
        max_actions: int = 32,
    ):
        require(1 <= max_actions <= max_submissions <= 256, "runtime.bounds")
        self.adapter, self.callback = adapter, callback
        self.rules = contract()
        self.store = DurableStore(output_directory)
        self.bounds = {"submissions": max_submissions, "actions": max_actions}
        self.claims: list[dict[str, Any]] = []
        self.pending: dict[str, Any] | None = None
        self.submissions = self.actions = self.updates = 0
        self.events: list[dict[str, Any]] = []
        self.feedback: dict[str, Any] | None = None
        self.terminal = False
        self.final: dict[str, Any] | None = None
        self.store.json("protocol.json", self.rules)
        self.store.json("context.json", adapter.context)
        self.store.json("callback_binding.json", callback.binding)
        self.store.json("registry.json", record("registry", members=adapter.registry.manifest()))
        self.store.json("bounds.json", self.bounds)

    def state(self) -> dict[str, Any]:
        return record(
            "state",
            context_id=self.adapter.context["id"],
            protocol_id=self.rules["id"],
            accepted_claims=self.claims,
            pending_observation=self.pending,
            phase="terminal" if self.terminal else "update" if self.pending else "action",
            submission_count=self.submissions,
            action_count=self.actions,
            update_count=self.updates,
            last_feedback=self.feedback,
            unresolved_uncertainties=[],
            terminal=self.terminal,
        )

    def request(self) -> dict[str, Any]:
        state = self.state()
        offered = [] if self.pending or self.terminal else self.adapter.offers(self.claims)
        transition_options = {}
        if self.pending:
            for disposition in ("accept", "reject"):
                preview = self.claims + (
                    [self._claim(self.pending)] if disposition == "accept" else []
                )
                before = {item["obligation_id"] for item in self.adapter.offers(self.claims)}
                after = {item["obligation_id"] for item in self.adapter.offers(preview)}
                finals = self.adapter.final_claims(preview)
                transition_options[disposition] = {
                    "newly_enabled_obligation_ids": sorted(after - before),
                    "remaining_uncertainty_refs": [],
                    "allowed_next_subgoals": sorted(
                        after | ({"submit_final"} if finals else set())
                    ),
                }
        return record(
            "request",
            protocol_id=self.rules["id"],
            context=self.adapter.context,
            state=state,
            available_actions=offered,
            final_claim_ids=self.adapter.final_claims(self.claims) if not self.pending else [],
            update_transition_options=transition_options,
            response_schemas=self.rules["submission_schemas"],
        )

    def _claim(self, observation: dict[str, Any]) -> dict[str, Any]:
        return record(
            "claim",
            observation_id=observation["id"],
            action_submission_id=observation["action_submission_id"],
            obligation_id=observation["obligation_id"],
            proposition=observation["proposition"],
            status="accepted",
        )

    def _admit(self, submitted: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        require(submitted["state_id"] == request["state"]["id"], "admission.current_state")
        require(not self.terminal, "admission.terminal")
        if submitted["kind"] == "action":
            require(
                self.pending is None and self.actions < self.bounds["actions"],
                "admission.action_phase_budget",
            )
            decision = submitted["decision"]
            options = {item["id"]: item for item in request["available_actions"]}
            require(len(options) == len(request["available_actions"]), "admission.duplicate_offer")
            require(
                len(decision["candidate_action_ids"]) == len(set(decision["candidate_action_ids"]))
                and set(decision["candidate_action_ids"]) == set(options),
                "admission.alternative_set",
            )
            require(decision["selected_action_id"] in options, "admission.selected_action")
            option = options[decision["selected_action_id"]]
            require(
                all(
                    canonical_json_bytes(submitted[field]) == canonical_json_bytes(option[field])
                    for field in ("operation", "inputs", "parameters")
                ),
                "admission.selected_action_content",
            )
            require(
                decision["obligation_id"] == option["obligation_id"]
                and decision["subgoal"] == option["subgoal"]
                and decision["selection_rule"] in option["selection_rules"]
                and canonical_json_bytes(decision["expected_effect"])
                == canonical_json_bytes(option["expected_effect"])
                and canonical_json_bytes(decision["basis"]) == canonical_json_bytes(option["basis"])
                and decision["unresolved_uncertainty_refs"] == [],
                "admission.public_judgment",
            )
            accepted = {claim["id"] for claim in self.claims if claim["status"] == "accepted"}
            refs = set(decision["basis"]["claim_refs"])
            for item in submitted["inputs"]:
                require(item["kind"] in {"claim", "evidence"}, "admission.input_kind")
                if item["kind"] == "claim":
                    refs.add(item["ref_id"])
            require(refs <= accepted, "admission.previously_accepted_dependency")
            return {"option": option, "prepared": self.adapter.prepare(option, self.claims)}
        if submitted["kind"] == "update":
            require(self.pending is not None, "admission.pending_observation")
            assert self.pending is not None
            accepted = submitted["disposition"] == "accept"
            require(
                submitted["observation_id"] == self.pending["id"], "admission.observation_parent"
            )
            require(
                canonical_json_bytes(submitted["proposed_claim"])
                == canonical_json_bytes(self.pending["proposition"] if accepted else None),
                "admission.exact_observation_acceptance",
            )
            assessment = {
                "relation": "accepts_observed_proposition" if accepted else "declines_observation",
                "observation_refs": [self.pending["id"]],
                "evidence_refs": self.pending["proposition"]["lineage"],
                "fulfills_obligation": self.pending["obligation_id"] if accepted else None,
            }
            require(
                canonical_json_bytes(submitted["assessment"]) == canonical_json_bytes(assessment),
                "admission.observation_assessment",
            )
            expected = request["update_transition_options"][submitted["disposition"]]
            require(
                submitted["remaining_uncertainty_refs"] == expected["remaining_uncertainty_refs"]
                and submitted["newly_enabled_obligation_ids"]
                == expected["newly_enabled_obligation_ids"]
                and submitted["next_subgoal"] in expected["allowed_next_subgoals"],
                "admission.update_effect",
            )
            return {"observation": copy.deepcopy(self.pending)}
        require(
            self.pending is None and submitted["answer_claim_id"] in request["final_claim_ids"],
            "admission.final_accepted_claim",
        )
        validation = self.adapter.verify_final(submitted, self.claims)
        require(validation["qa_valid"], "admission.final_qa")
        return {"validation": validation}

    def step(self, raw: bytes) -> dict[str, Any]:
        request = self._persist_request()
        return self._consume(raw, request)

    def _persist_request(self) -> dict[str, Any]:
        require(
            not self.terminal and self.submissions < self.bounds["submissions"],
            "runtime.submission_bound",
        )
        request = self.request()
        self.store.json(f"turns/{self.submissions:03d}_request.json", request)
        return request

    def _consume(self, raw: bytes, request: dict[str, Any]) -> dict[str, Any]:
        index = self.submissions
        prefix = f"turns/{index:03d}_"
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
        submitted = None
        code: str | None
        try:
            submitted = parse(raw)
            prepared = self._admit(submitted, request)
        except (ProtocolError, ValueError, KeyError, TypeError) as error:
            prepared = None
            code = str(error)
        else:
            code = None
        receipt = record(
            "receipt",
            submission_id=submission["id"],
            request_id=request["id"],
            state_id=request["state"]["id"],
            admitted=prepared is not None,
            error_code=code,
            no_host_semantic_repair=True,
        )
        self.store.json(prefix + "receipt.json", receipt)
        event: dict[str, Any] = {
            "sequence": index,
            "request": request,
            "submission": submission,
            "parsed": submitted,
            "receipt": receipt,
        }
        self.submissions += 1
        if prepared is None:
            self.feedback = {"code": code, "admitted": False}
        elif submitted is not None and submitted["kind"] == "action":
            # These exact persisted bytes must exist before any numeric executor runs.
            require(
                (self.store.root / (prefix + "receipt.json")).read_bytes()
                == canonical_json_bytes(receipt)
                and (self.store.root / (prefix + "response.txt")).read_bytes() == raw,
                "runtime.pre_dispatch_readback",
            )
            self.store.events.append(
                {
                    "kind": "pre_dispatch_readback",
                    "sequence": index,
                    "response_path": prefix + "response.txt",
                    "receipt_path": prefix + "receipt.json",
                }
            )
            self.store.events.append(
                {"kind": "execution_dispatch", "sequence": index, "submission_id": submission["id"]}
            )
            self.actions += 1
            try:
                proposition = self.adapter.execute(prepared["prepared"])
                self.store.events.append(
                    {
                        "kind": "execution_return",
                        "sequence": index,
                        "submission_id": submission["id"],
                    }
                )
                output_valid = self.adapter.verify_execution(prepared["prepared"], proposition)
                require(output_valid, "execution.independent_output")
            except (ValueError, ArithmeticError, KeyError, TypeError) as error:
                self.terminal = True
                self.feedback = {"code": "execution_failed", "detail": str(error), "admitted": True}
                event["execution_error"] = str(error)
            else:
                option = prepared["option"]
                execution = record(
                    "execution",
                    action_submission_id=submission["id"],
                    receipt_id=receipt["id"],
                    operation=option["operation"],
                    selected_action=option,
                    resolved_inputs=[
                        item.model_dump(mode="json") for item in prepared["prepared"]["inputs"]
                    ],
                    proposition=proposition,
                    success=True,
                )
                self.store.json(prefix + "execution.json", execution)
                event["execution"] = execution
                observation = record(
                    "observation",
                    action_submission_id=submission["id"],
                    execution_id=execution["id"],
                    receipt_id=receipt["id"],
                    obligation_id=option["obligation_id"],
                    selected_action=option,
                    proposition=proposition,
                    independent_output_valid=output_valid,
                )
                self.store.json(prefix + "observation.json", observation)
                self.pending = observation
                event["observation"] = observation
                self.feedback = {
                    "code": "pending_observation_requires_callback_update",
                    "admitted": True,
                }
        elif submitted is not None and submitted["kind"] == "update":
            self.updates += 1
            if submitted["disposition"] == "accept":
                claim = self._claim(prepared["observation"])
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
        elif submitted is not None:
            self.final = record(
                "final",
                submission_id=submission["id"],
                answer=submitted,
                qa_validation=prepared["validation"],
            )
            self.store.json(prefix + "final.json", self.final)
            self.terminal = True
            self.feedback = {"code": "complete", "admitted": True}
        event["post_state"] = self.state()
        self.store.json(prefix + "event.json", event)
        self.events.append(event)
        return copy.deepcopy(event)

    def run(self) -> dict[str, Any]:
        while not self.terminal and self.submissions < self.bounds["submissions"]:
            request = self._persist_request()
            try:
                raw = self.callback.generate(copy.deepcopy(request))
                require(isinstance(raw, bytes), "callback.raw_bytes")
            except Exception as error:
                self.terminal = True
                self.feedback = {"code": "callback_failure", "detail": type(error).__name__}
                break
            self._consume(raw, request)
        if not self.terminal:
            self.terminal = True
            self.feedback = {"code": "submission_budget_exhausted"}
        result = record(
            "session",
            context_id=self.adapter.context["id"],
            protocol_id=self.rules["id"],
            callback_binding=self.callback.binding,
            bounds=self.bounds,
            registry_hash=strict_canonical_hash(self.adapter.registry.manifest()),
            events=self.events,
            claims=self.claims,
            final=self.final,
            terminal_state=self.state(),
            accepted_claim_revision_supported=False,
        )
        self.store.json("session.json", result)
        files = {
            str(path.relative_to(self.store.root)): path.read_bytes()
            for path in self.store.root.rglob("*")
            if path.is_file()
        }
        self.store.json(
            "manifest.json",
            record(
                "manifest",
                session_id=result["id"],
                members=[
                    {"path": path, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                    for path, data in sorted(files.items())
                ],
                write_events=self.store.events,
                self_excluding=True,
            ),
        )
        return result
