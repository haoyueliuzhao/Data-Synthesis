"""Load sealed prior bindings and twelve Final-ready public states, without replay.

Only explicitly selected files are hash-checked against anchored manifests. This
does not scan the archive, reload sources from FinQA, rebuild an old Runtime,
requalify a trajectory, execute an Operation or repeat quotient measurement.
"""

from __future__ import annotations

import copy
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.final_published_share_adapter import (
    FinalPublishedShareTaskAdapter,
)

from ..finance_qa_vnext_cross_binding.source import CONTEXT_FIELDS, BoundShareSource
from ..finance_qa_vnext_model_execution.models import identity, read_json, record, require

SOURCE_ROOT = (
    "trusted_data_synthesis/artifacts/qa_vnext_cross_binding/cross_binding_dual_support_v1_20260907"
)
OLD_CONDITION_ID = (
    "qa_vnext_model_execution_cross_binding_condition:"
    "8fccc95f4a8f40e9b41f6332043b1cc3f0e9498c1648f830ecd26f518480ce30"
)
PREPARATION_MANIFEST_ID = (
    "qa_vnext_model_execution_cross_binding_preparation_manifest:"
    "88c315661c95b8870ea57309e9042343dc0ce5e23b435e311c953005bb8bddcb"
)
EXECUTION_MANIFEST_ID = (
    "qa_vnext_model_execution_cross_binding_execution_manifest:"
    "9f6057103efb442e9787d12f6c7f59ddfde557d19d5b746f1f2a66a2a966ae35"
)
OLD_REPORT_ID = (
    "qa_vnext_model_execution_cross_binding_report:"
    "67925903b401e608d51540b1528ff189070df673446988298cd5ed6c9312441b"
)
PROTECTED_SOURCES = (
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/qa_vnext/bound_share_adapter.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/qa_vnext/share_adapter.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_cross_binding/source.py",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identified(value: dict[str, Any]) -> None:
    ref = value.get("id")
    require(isinstance(ref, str) and ":" in ref, "final_source.identity")
    assert isinstance(ref, str)
    require(
        ref
        == strict_canonical_hash(
            {key: item for key, item in value.items() if key != "id"},
            prefix=ref.split(":", 1)[0] + ":",
        ),
        "final_source.identity",
    )


class _SealedSubset:
    def __init__(self, directory: Path, kind: str, expected_id: str):
        self.directory = directory.resolve()
        manifest_path = self.directory / "manifest.json"
        require(not manifest_path.is_symlink(), "final_source.manifest_symlink")
        raw = manifest_path.read_bytes()
        self.manifest = read_json(raw)
        identity(self.manifest, kind)
        require(
            self.manifest["id"] == expected_id
            and self.manifest["self_excluding"] is True
            and raw == canonical_json_bytes(self.manifest),
            "final_source.sealed_manifest_anchor",
        )
        self.members = {item["path"]: item for item in self.manifest["members"]}
        require(len(self.members) == len(self.manifest["members"]), "final_source.member_inventory")
        self.read_members: dict[str, dict[str, Any]] = {}

    def json(self, name: str) -> Any:
        require(
            name in self.members and not Path(name).is_absolute() and ".." not in Path(name).parts,
            "final_source.sealed_member",
        )
        path = self.directory / name
        require(
            not path.is_symlink() and path.resolve().is_relative_to(self.directory),
            "final_source.member_escape",
        )
        raw = path.read_bytes()
        member = self.members[name]
        require(
            len(raw) == member["bytes"] and _sha(raw) == member["sha256"],
            "final_source.original_member_bytes",
        )
        self.read_members[name] = member
        return read_json(raw)


def _one(items, predicate, code):
    selected = [item for item in items if predicate(item)]
    require(len(selected) == 1, "final_source." + code)
    return selected[0]


def _accepted_producer(session, claim):
    action = _one(
        session["events"],
        lambda event: event["submission"]["id"] == claim["action_submission_id"],
        "claim_actual_action",
    )
    update = _one(
        session["events"],
        lambda event: event.get("claim", {}).get("id") == claim["id"],
        "claim_explicit_accept",
    )
    require(
        action["receipt"]["admitted"] is True
        and action["parsed"]["kind"] == "action"
        and action["execution"]["success"] is True
        and action["parsed"]["operation"]
        == action["execution"]["operation"]
        == claim["proposition"]["operation"]
        and action["observation"]["id"] == claim["observation_id"]
        and action["observation"]["proposition"] == claim["proposition"]
        and update["receipt"]["admitted"] is True
        and update["parsed"]["kind"] == "update"
        and update["parsed"]["disposition"] == "accept"
        and update["claim"] == claim
        and action["sequence"] < update["sequence"],
        "final_source.actual_action_observation_accept",
    )
    return action, update


def _consumed_claim(session, consumer, role, operation):
    original = _one(
        consumer["parsed"]["inputs"], lambda item: item["role"] == role, "actual_input_role"
    )
    resolved = _one(
        consumer["execution"]["resolved_inputs"],
        lambda item: item["value"]["role"] == role,
        "actual_resolved_input_role",
    )
    require(
        original["kind"] == resolved["value"]["kind"] == "claim"
        and original["ref_id"] == resolved["ref_id"] == resolved["value"]["ref_id"],
        "final_source.actual_claim_input_identity",
    )
    claim = _one(
        consumer["request"]["state"]["accepted_claims"],
        lambda item: item["id"] == original["ref_id"],
        "claim_previously_accepted",
    )
    producer, update = _accepted_producer(session, claim)
    require(
        claim["proposition"]["operation"] == operation
        and update["sequence"] < consumer["sequence"]
        and resolved["value"]["producer_operation"] == operation,
        "final_source.prior_producer_consumption",
    )
    return claim, producer, update


def _select_ready(registration, session, qualification):
    events = session["events"]
    accepts = [
        event
        for event in events
        if event.get("claim", {}).get("obligation_id") == "percent"
        and event.get("claim", {}).get("proposition", {}).get("operation") == "scale_percent"
        and event["receipt"]["admitted"] is True
        and event["parsed"]["kind"] == "update"
        and event["parsed"]["disposition"] == "accept"
    ]
    require(bool(accepts), "final_source.percent_accept_exists")
    accept = min(accepts, key=lambda event: event["sequence"])
    finals = [
        event
        for event in events
        if event["sequence"] > accept["sequence"]
        and (event.get("parsed") or {}).get("kind") == "final"
    ]
    require(bool(finals), "final_source.first_final_request_exists")
    event = min(finals, key=lambda item: item["sequence"])
    request, claim = event["request"], accept["claim"]
    require(
        request["state"]["pending_observation"] is None
        and request["state"]["terminal"] is False
        and claim in request["state"]["accepted_claims"]
        and claim["id"] in request["final_claim_ids"]
        and request["context"]["task_id"] == qualification["task_id"]
        and request["state"]["submission_count"] == event["sequence"],
        "final_source.ready_state_binding",
    )
    percent_action, percent_update = _accepted_producer(session, claim)
    require(percent_update == accept, "final_source.first_percent_accept_parent")
    ratio_claim, ratio_action, ratio_update = _consumed_claim(
        session, percent_action, "ratio", "share_ratio"
    )
    denominator = _one(
        ratio_action["parsed"]["inputs"],
        lambda item: item["role"] == "denominator",
        "ratio_denominator_role",
    )
    resolved = _one(
        ratio_action["execution"]["resolved_inputs"],
        lambda item: item["value"]["role"] == "denominator",
        "ratio_resolved_denominator",
    )
    evidence = request["context"]["evidence"]
    total_claim = total_action = total_update = None
    if denominator["kind"] == "evidence":
        require(
            resolved["value"]["kind"] == "evidence"
            and denominator["ref_id"]
            == resolved["ref_id"]
            == resolved["value"]["ref_id"]
            == evidence["disclosed_total"]["id"],
            "final_source.actual_disclosed_denominator",
        )
        support = "disclosed_total"
        lineage = {evidence[key]["id"] for key in ("target_component", "disclosed_total")}
    else:
        total_claim, total_action, total_update = _consumed_claim(
            session, ratio_action, "denominator", "relation_sum"
        )
        require(total_claim["obligation_id"] == "total", "final_source.actual_reconstructed_total")
        support = "reconstructed_total"
        lineage = {
            evidence[key]["id"]
            for key in ("target_component", "other_component", "composition_relation")
        }
    require(
        set(claim["proposition"]["lineage"])
        == set(ratio_claim["proposition"]["lineage"])
        == lineage,
        "final_source.actual_prefix_lineage",
    )
    return record(
        "final_publication_ready_state",
        label=registration["label"],
        task_group=registration["task_group"],
        profile=registration["profile"],
        task_id=registration["task_id"],
        context_id=registration["context_id"],
        old_registration_id=registration["id"],
        old_qualification_id=qualification["id"],
        old_session_id=session["id"],
        old_status=qualification["status"],
        old_qualified=qualification["qualified"],
        source_event_sequence=event["sequence"],
        source_event_sha256=_sha(canonical_json_bytes(event)),
        source_request_id=request["id"],
        source_request_sha256=_sha(canonical_json_bytes(request)),
        source_state_id=request["state"]["id"],
        source_state_sha256=_sha(canonical_json_bytes(request["state"])),
        percent_accept_sequence=accept["sequence"],
        percent_accept_event_sha256=_sha(canonical_json_bytes(accept)),
        before_accept_state_id=accept["request"]["state"]["id"],
        percent_claim_id=claim["id"],
        percent_claim_sha256=_sha(canonical_json_bytes(claim)),
        prefix_support=support,
        actual_prefix_support_proof={
            "ratio_action_submission_id": ratio_action["submission"]["id"],
            "ratio_claim_id": ratio_claim["id"],
            "ratio_accept_sequence": ratio_update["sequence"],
            "percent_action_submission_id": percent_action["submission"]["id"],
            "percent_claim_id": claim["id"],
            "denominator": denominator,
            "resolved_denominator": resolved,
            "total_claim_id": total_claim["id"] if total_claim else None,
            "total_action_submission_id": total_action["submission"]["id"]
            if total_action
            else None,
            "total_accept_sequence": total_update["sequence"] if total_update else None,
            "actual_lineage": sorted(lineage),
            "support_inferred_from_action_count": False,
            "complete_session_success_claimed": False,
        },
        request=request,
        selection_rule="first accepted percent Claim, then first actual Final request",
        old_session_resumed=False,
        old_final_appended=False,
        qualification_recomputed=False,
    )


def load_inputs(root: Path) -> dict[str, Any]:
    """Restore exact source objects from the frozen source report, not source discovery."""
    root = root.resolve()
    base = root / SOURCE_ROOT
    preparation = _SealedSubset(
        base / "preparation", "cross_binding_preparation_manifest", PREPARATION_MANIFEST_ID
    )
    execution = _SealedSubset(
        base / "execution", "cross_binding_execution_manifest", EXECUTION_MANIFEST_ID
    )
    condition = preparation.json("condition.json")
    identity(condition, "cross_binding_condition")
    require(
        condition["id"] == OLD_CONDITION_ID
        and condition["task_count"] == 3
        and condition["registered_session_count"] == 12,
        "final_source.original_population_condition",
    )
    source_report = preparation.json("source_report.json")
    evaluation = preparation.json("evaluation_separation.json")
    implementation = preparation.json("implementation.json")
    registrations = preparation.json("registrations.json")
    require(
        registrations == execution.json("registrations.json"), "final_source.registration_copies"
    )
    report = execution.json("report.json")
    require(
        report["id"] == OLD_REPORT_ID
        and report["condition_id"] == condition["id"]
        and report["registered_session_count"] == 12
        and report["provider_attempt_count"] == 384
        and report["status_counts"] == {"known_failure": 12},
        "final_source.original_failure_report",
    )
    for value in (source_report, evaluation, implementation, report):
        _identified(value)
    require(
        source_report["contamination_registry"] == evaluation
        and evaluation["clean_evaluation_task_count"] == 0
        and evaluation["evaluation_readiness"] == "not_ready",
        "final_source.original_evaluation_policy",
    )
    old_members = {item["path"]: item for item in implementation["members"]}
    protected = []
    for name in PROTECTED_SOURCES:
        require(name in old_members, "final_source.protected_source_binding")
        raw = (root / name).read_bytes()
        member = old_members[name]
        require(
            _sha(raw) == member["sha256"] and len(raw) == member["bytes"],
            "final_source.source_adapter_or_strict_verifier_changed",
        )
        protected.append(member)
    require(
        FinalPublishedShareTaskAdapter.verify_final is BoundShareTaskAdapter.verify_final,
        "final_source.original_strict_final_verifier_inherited",
    )
    bindings = {item["id"]: item for item in source_report["bindings"]}
    tasks = {item["id"]: item for item in source_report["tasks"]}
    semantics = {item["task_id"]: item for item in source_report["semantic_contracts"]}
    require(
        len(bindings) == len(tasks) == len(semantics) == 3, "final_source.three_frozen_bindings"
    )
    sources, adapters, source_rows = {}, {}, []
    for descriptor in sorted(condition["tasks"], key=lambda item: item["task_group"]):
        task, binding = tasks[descriptor["task_id"]], bindings[descriptor["source_binding_id"]]
        source = BoundShareSource(
            source_key=binding["source_key"],
            task_id=task["id"],
            source_binding_id=binding["id"],
            context={key: binding[key] for key in CONTEXT_FIELDS},
            evidence=copy.deepcopy(binding["evidence"]),
            binding_record=copy.deepcopy(binding),
            task=copy.deepcopy(task),
            semantic_contract=copy.deepcopy(semantics[task["id"]]),
        )
        adapter = FinalPublishedShareTaskAdapter(source)
        require(
            adapter.context["id"] == descriptor["context_id"]
            and strict_canonical_hash(adapter.registry.manifest()) == descriptor["registry_hash"]
            and adapter.context["task_id"] == descriptor["task_id"]
            and adapter.context["semantic_contract"]["id"] == source.semantic_contract["id"],
            "final_source.original_task_context_registry_semantics",
        )
        group = descriptor["task_group"]
        sources[group], adapters[group] = source, adapter
        source_rows.append(
            {
                "task_group": group,
                "source_key": source.source_key,
                "task_id": source.task_id,
                "context_id": adapter.context["id"],
                "source_binding_id": source.source_binding_id,
                "semantic_contract_id": source.semantic_contract["id"],
                "registry_hash": descriptor["registry_hash"],
                "evidence_ids": {key: item["id"] for key, item in source.evidence.items()},
                "source_restored_from_sealed_report": True,
                "source_scanned_or_reselected": False,
            }
        )
    require(
        len(registrations) == len({reg["id"] for reg in registrations}) == 12
        and {reg["label"] for reg in registrations} == set(condition["registered_labels"]),
        "final_source.original_registration_inventory",
    )
    ready_states, qualifications = [], []
    for registration in registrations:
        identity(registration, "session_registration")
        label = registration["label"]
        require(
            label in condition["registered_labels"] and "/" not in label and ".." not in label,
            "final_source.registered_session_label",
        )
        qual = execution.json(f"sessions/{label}/qualification.json")
        session = execution.json(f"sessions/{label}/runtime/session.json")
        identity(qual, "qualification")
        _identified(session)
        require(
            qual["registration_id"] == registration["id"]
            and qual["registered_session_id"] == registration["session_id"]
            and qual["session_id"] == session["id"]
            and qual["qualified"] is False
            and qual["end_to_end_success"] is False
            and qual["evidence_complete"] is True
            and qual["status"] == "known_failure"
            and qual["reason"] == "submission_budget_exhausted"
            and qual["provider_attempt_count"]
            == qual["runtime_submission_count"]
            == len(session["events"])
            == 32
            and session["final"] is None,
            "final_source.old_twelve_failures_unchanged",
        )
        ready = _select_ready(registration, session, qual)
        adapter = adapters[registration["task_group"]]
        require(
            canonical_json_bytes(ready["request"]["context"])
            == canonical_json_bytes(adapter.context)
            and ready["request"]["context"]["evidence"]
            == sources[registration["task_group"]].evidence,
            "final_source.original_context_evidence_bytes",
        )
        ready_states.append(ready)
        qualifications.append(qual)
    support_counts = Counter(row["prefix_support"] for row in ready_states)
    require(
        len(ready_states) == 12
        and support_counts == {"disclosed_total": 7, "reconstructed_total": 5},
        "final_source.twelve_ready_actual_prefix_supports",
    )
    checks = record(
        "final_publication_source_checks",
        original_condition_id=condition["id"],
        original_report_id=report["id"],
        preparation_manifest_id=preparation.manifest["id"],
        execution_manifest_id=execution.manifest["id"],
        original_source_report_id=source_report["id"],
        evaluation_policy_id=evaluation["id"],
        source_bindings=source_rows,
        protected_source_files=protected,
        original_registration_ids=[reg["id"] for reg in registrations],
        original_qualification_ids=[qual["id"] for qual in qualifications],
        original_session_ids=[qual["session_id"] for qual in qualifications],
        ready_state_ids=[row["id"] for row in ready_states],
        selected_ready_state_count=12,
        original_known_failure_count=12,
        original_qualified_count=0,
        actual_failed_prefix_support_counts=dict(support_counts),
        task_context_evidence_registry_semantic_contracts_unchanged=True,
        original_strict_final_verifier_inherited=True,
        source_adapter_and_verifier_files_byte_unchanged=True,
        archived_members_read={
            "preparation": list(preparation.read_members.values()),
            "execution": list(execution.read_members.values()),
        },
        verification_scope=(
            "only the explicitly read members of anchored sealed manifests; "
            "no repeat transport or semantic audit"
        ),
        archive_scans=0,
        source_reselection_calls=0,
        runtime_constructions=0,
        runtime_executions=0,
        operation_executions=0,
        qualifier_calls=0,
        quotient_calls=0,
        tokenizer_calls=0,
        provider_calls=0,
        old_requests_or_states_rewritten=False,
        old_sessions_resumed=False,
        old_outcomes_reclassified=False,
    )
    return {
        "sources": sources,
        "adapters": adapters,
        "old_condition": condition,
        "old_registrations": registrations,
        "old_qualifications": qualifications,
        "ready_states": ready_states,
        "source_checks": checks,
        "evaluation_policy": evaluation,
        "source_report": source_report,
        "old_report": report,
    }
